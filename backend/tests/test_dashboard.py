from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.storage import Storage
from backend.app.schemas import MatchSummary, MetricAvailabilityRecord


def _seed_dashboard_storage(storage_root: Path, configs: list[dict]) -> list[str]:
    """Write completed match records + analytics directly into storage for testing.

    Each entry: {name, possession, myTeamXg, enemyXg, myTeamSprints, enemySprints, formation}
    """
    Storage(storage_root)  # Initialize schema
    ids = []
    for i, cfg in enumerate(configs):
        mid = uuid.uuid4().hex
        cfg_json = json.dumps({"attackDirection": "left_to_right", "manualHomographyPoints": []})
        db_path = storage_root / "guerilla.sqlite3"
        conn = sqlite3.connect(str(db_path))
        status = cfg.get("status", "completed")
        conn.execute(
            "INSERT INTO matches (id,name,input_mode,status,original_filename,input_path,config_json,requires_team_selection,created_at,updated_at) VALUES (?,?,'tracking_json',?, ?,?,?,'0',datetime('now',?||' seconds'),datetime('now',?||' seconds'))",
            (mid, cfg["name"], status, f"{cfg['name']}.json", str(storage_root / f"{mid}.json"), cfg_json, str(i), str(i)),
        )
        conn.commit()
        conn.close()

        summary = MatchSummary(
            possession=cfg["possession"],
            myTeamDistance=5000, enemyDistance=5000,
            myTeamAvgPos={}, enemyAvgPos={},
            myTeamTopSpeed=7.0, enemyTopSpeed=7.0,
            myTeamSprints=cfg["myTeamSprints"], enemySprints=cfg["enemySprints"],
            myTeamXg=cfg["myTeamXg"], enemyXg=cfg["enemyXg"],
            formation=cfg["formation"],
            myTeamDefensiveLineHeight=0.5, enemyDefensiveLineHeight=0.5,
            myTeamDefensiveTeamLength=45.0, enemyDefensiveTeamLength=45.0,
        )
        match_dir = storage_root / "matches" / mid
        match_dir.mkdir(parents=True, exist_ok=True)
        (match_dir / "analytics.json").write_text(json.dumps({
            "summary": summary.model_dump(mode="json"),
            "ballAssignments": cfg.get("ballAssignments", [
                {"frameId": frame, "timestamp": frame / 5, "team": "my_team" if frame < cfg["possession"] else "enemy", "trackId": 7}
                for frame in range(100)
            ]),
            "formationTimeline": [],
            "shots": [],
        }))
        (match_dir / "events.json").write_text("[]")
        ids.append(mid)
    return ids


@pytest.fixture
def client():
    app = create_app(storage_root=":memory:", run_jobs_inline=True)
    return TestClient(app, base_url="http://127.0.0.1")


@pytest.fixture
def client_with_data(tmp_path: Path) -> TestClient:
    _seed_dashboard_storage(tmp_path, [
        {"name": "Match Alpha", "possession": 55, "myTeamXg": 1.2, "enemyXg": 0.8, "myTeamSprints": 12, "enemySprints": 8, "formation": "4-3-3"},
        {"name": "Match Beta",  "possession": 48, "myTeamXg": 0.9, "enemyXg": 1.1, "myTeamSprints": 9,  "enemySprints": 11, "formation": "4-4-2"},
    ])
    app = create_app(storage_root=str(tmp_path), run_jobs_inline=True)
    return TestClient(app, base_url="http://127.0.0.1")


class TestDashboardEndpoint:
    def test_empty_returns_empty_response(self, client: TestClient) -> None:
        response = client.get("/api/aggregate/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["matchCount"] == 0
        assert data["summary"]["avgPossession"] is None
        assert data["summary"]["mostUsedFormation"] is None
        assert data["summary"]["avgMyTeamXg"] is None
        assert data["summary"]["avgEnemyXg"] is None
        assert data["summary"]["avgXgDiff"] is None
        assert data["comparison"] is None
        assert data["trends"] == []

    def test_summary_fields_present(self, client: TestClient) -> None:
        response = client.get("/api/aggregate/dashboard")
        assert response.status_code == 200
        summary = response.json()["summary"]
        assert "matchCount" in summary
        assert "avgPossession" in summary
        assert "avgMyTeamXg" in summary
        assert "avgEnemyXg" in summary
        assert "avgXgDiff" in summary
        assert "avgMyTeamSprints" in summary
        assert "avgEnemySprints" in summary
        assert "mostUsedFormation" in summary

    def test_response_structure(self, client: TestClient) -> None:
        response = client.get("/api/aggregate/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "comparison" in data
        assert "trends" in data
        assert isinstance(data["trends"], list)

    def test_comparison_is_none_when_empty(self, client: TestClient) -> None:
        response = client.get("/api/aggregate/dashboard")
        assert response.status_code == 200
        assert response.json()["comparison"] is None

    def test_with_data_aggregates_correctly(self, client_with_data: TestClient) -> None:
        """2 matches aggregate to expected averages."""
        response = client_with_data.get("/api/aggregate/dashboard")
        assert response.status_code == 200
        s = response.json()["summary"]
        assert s["matchCount"] == 2
        assert s["avgPossession"] == 51.5      # (55+48)/2
        assert s["avgMyTeamXg"] == 1.05           # (1.2+0.9)/2
        assert s["avgEnemyXg"] == 0.95           # (0.8+1.1)/2
        assert s["avgXgDiff"] == 0.1              # 1.05-0.95
        assert s["avgMyTeamSprints"] == 10.5       # (12+9)/2
        assert s["mostUsedFormation"] in ("4-3-3", "4-4-2")

    def test_ready_matches_are_included_in_dashboard_aggregation(self, tmp_path: Path) -> None:
        _seed_dashboard_storage(
            tmp_path,
            [
                {"name": "Ready Match", "status": "ready", "possession": 60, "myTeamXg": 1.4, "enemyXg": 0.6, "myTeamSprints": 10, "enemySprints": 7, "formation": "3-5-2"},
                {"name": "Completed Match", "status": "completed", "possession": 40, "myTeamXg": 0.6, "enemyXg": 1.4, "myTeamSprints": 6, "enemySprints": 11, "formation": "4-4-2"},
            ],
        )
        app = create_app(storage_root=str(tmp_path), run_jobs_inline=True)
        client = TestClient(app, base_url="http://127.0.0.1")

        response = client.get("/api/aggregate/dashboard")
        assert response.status_code == 200
        summary = response.json()["summary"]
        assert summary["matchCount"] == 2
        assert summary["avgPossession"] == 50.0
        assert summary["mostUsedFormation"] in ("3-5-2", "4-4-2")

    def test_historical_zero_denominator_possession_is_unknown_on_every_read_surface(self, tmp_path: Path) -> None:
        match_id = _seed_dashboard_storage(tmp_path, [{
            "name": "Unresolved Teams", "possession": 50, "myTeamXg": 0,
            "enemyXg": 0, "myTeamSprints": 0, "enemySprints": 0,
            "formation": "-", "ballAssignments": [],
        }])[0]
        client = TestClient(create_app(storage_root=str(tmp_path), run_jobs_inline=True), base_url="http://127.0.0.1")

        analytics = client.get(f"/api/matches/{match_id}/analytics")
        dashboard = client.get("/api/aggregate/dashboard")
        report = client.get(f"/api/matches/{match_id}/report/html")

        assert analytics.status_code == dashboard.status_code == report.status_code == 200
        assert analytics.json()["summary"]["possession"] is None
        assert dashboard.json()["summary"]["avgPossession"] is None
        assert dashboard.json()["trends"][0]["summary"]["possession"] is None
        assert "Possession was not measured" in report.text
        assert "50% possession" not in report.text

    def test_comparison_deltas(self, client_with_data: TestClient) -> None:
        """Latest vs previous match comparison has correct deltas."""
        response = client_with_data.get("/api/aggregate/dashboard")
        assert response.status_code == 200
        comp = response.json()["comparison"]
        assert comp is not None
        assert comp["latestMatchName"] == "Match Beta"
        assert comp["previousMatchName"] == "Match Alpha"
        # Beta (48%) vs Alpha (55%): -7 possession
        assert comp["possessionDelta"] == -7.0
        # Beta xG diff: 0.9-1.1=-0.2; Alpha xG diff: 1.2-0.8=0.4; delta = -0.6
        assert comp["xgDiffDelta"] == -0.6

    def test_trends_chronological_order(self, client_with_data: TestClient) -> None:
        """Trends array is oldest-first for chart display."""
        response = client_with_data.get("/api/aggregate/dashboard")
        assert response.status_code == 200
        trends = response.json()["trends"]
        assert len(trends) == 2
        assert trends[0]["name"] == "Match Alpha"
        assert trends[1]["name"] == "Match Beta"


def _withheld_sprint_availability() -> list[MetricAvailabilityRecord]:
    return [
        MetricAvailabilityRecord(
            metric="my_team_sprints",
            value=None,
            availability="withheld",
            reasonCodes=["IDENTITY_DISCONTINUITY"],
            denominator="identity_continuous_eligible_seconds",
        ),
        MetricAvailabilityRecord(
            metric="enemy_sprints",
            value=None,
            availability="withheld",
            reasonCodes=["IDENTITY_DISCONTINUITY"],
            denominator="identity_continuous_eligible_seconds",
        ),
    ]


def test_dashboard_withholds_sprint_averages_when_physical_metrics_are_withheld(tmp_path: Path) -> None:
    storage_root = tmp_path
    Storage(storage_root)
    mid = uuid.uuid4().hex
    cfg_json = json.dumps({"attackDirection": "left_to_right", "manualHomographyPoints": []})
    db_path = storage_root / "guerilla.sqlite3"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO matches (id,name,input_mode,status,original_filename,input_path,config_json,requires_team_selection,created_at,updated_at) VALUES (?,?,'video','ready', ?,?,?,'0',datetime('now'),datetime('now'))",
        (mid, "Withheld Sprints", f"{mid}.mp4", str(storage_root / f"{mid}.mp4"), cfg_json),
    )
    conn.commit()
    conn.close()
    summary = MatchSummary(
        possession=55,
        myTeamDistance=0,
        enemyDistance=0,
        myTeamAvgPos={"x": 50, "y": 50},
        enemyAvgPos={"x": 50, "y": 50},
        myTeamTopSpeed=0.0,
        enemyTopSpeed=0.0,
        myTeamSprints=12,
        enemySprints=10,
        myTeamXg=1.2,
        enemyXg=0.8,
        formation="4-3-3",
        myTeamDefensiveLineHeight=0.5,
        enemyDefensiveLineHeight=0.5,
        myTeamDefensiveTeamLength=45.0,
        enemyDefensiveTeamLength=45.0,
        metricAvailability=_withheld_sprint_availability(),
    )
    match_dir = storage_root / "matches" / mid
    match_dir.mkdir(parents=True, exist_ok=True)
    (match_dir / "analytics.json").write_text(json.dumps({
        "summary": summary.model_dump(mode="json"),
        "ballAssignments": [],
        "formationTimeline": [],
        "shots": [],
    }))
    (match_dir / "events.json").write_text("[]")
    client = TestClient(create_app(storage_root=str(tmp_path), run_jobs_inline=True), base_url="http://127.0.0.1")

    data = client.get("/api/aggregate/dashboard").json()
    assert data["summary"]["avgMyTeamSprints"] is None
    assert data["summary"]["avgEnemySprints"] is None
    assert data["summary"]["avgMyTeamSprints"] != 12
    assert data["summary"]["avgEnemySprints"] != 10
