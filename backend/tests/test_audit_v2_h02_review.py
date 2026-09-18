from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.processor import reprocess_video_match
from backend.app.schemas import ColorClusterSummary, MatchConfig
from backend.app.storage import Storage
from backend.app.workbench.review import CorrectionLog


FIXTURE = Path(__file__).parent / "fixtures" / "raw_rows_two_teams.json"
LEGACY_CORRECTIONS = Path(__file__).parent / "fixtures" / "corrections_v1.json"


def install_raw_row_match(storage: Storage, tmp_path: Path) -> str:
    rows = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len({row["Frame_ID"] for row in rows}) >= 40
    source = tmp_path / "two-teams.mp4"
    source.write_bytes(b"fixture")
    match = storage.create_match(
        "Raw row team mapping",
        "video",
        source.name,
        source,
        MatchConfig(myTeamCluster=0),
    )
    storage.save_raw_rows(match.id, rows)
    storage.update_match_status(
        match.id,
        status="ready",
        team_clusters=[
            ColorClusterSummary(clusterId=0, rgbCentroid=[255.0, 0.0, 0.0], trackIds=[7]),
            ColorClusterSummary(clusterId=1, rgbCentroid=[0.0, 0.0, 255.0], trackIds=[18]),
        ],
    )
    reprocess_video_match(storage, match.id)
    return match.id


def _team_for_track(storage: Storage, match_id: str, track_id: int) -> str | None:
    frame = storage.load_frames(match_id)[0]
    if any(player.id == track_id for player in frame.myTeam):
        return "my_team"
    if any(player.id == track_id for player in frame.enemies):
        return "enemy"
    return None


def test_t02_raw_row_team_swap_survives_rebuild_and_restart(tmp_path: Path) -> None:
    """B04 / T02: corrections must change the effective config before raw-row classification."""
    storage_root = tmp_path / "storage"
    storage = Storage(storage_root)
    match_id = install_raw_row_match(storage, tmp_path)
    assert _team_for_track(storage, match_id, 7) == "my_team"

    storage.submit_correction(match_id, kind="team_mapping", payload={"swap": True})
    assert _team_for_track(storage, match_id, 7) == "enemy"

    reprocess_video_match(storage, match_id)
    assert _team_for_track(storage, match_id, 7) == "enemy"

    restarted = Storage(storage_root)
    assert _team_for_track(restarted, match_id, 7) == "enemy"
    check = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; from backend.app.storage import Storage; "
                "s=Storage(sys.argv[1]); f=s.load_frames(sys.argv[2])[0]; "
                "print('enemy' if any(p.id == 7 for p in f.enemies) else 'not-enemy')"
            ),
            str(storage_root),
            match_id,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert check.stdout.strip() == "enemy"


def test_t28_idempotency_payload_mismatch_is_a_stable_conflict(tmp_path: Path) -> None:
    """B35 / T28: a reused request ID cannot mutate attempts, reservations, or the original request."""
    app = create_app(storage_root=tmp_path / "api", run_jobs_inline=False)
    storage: Storage = app.state.storage
    source = tmp_path / "tracking.json"
    source.write_text("[]", encoding="utf-8")
    match = storage.create_match("Idempotency", "tracking_json", source.name, source, MatchConfig())

    workbench_payload = {
        "requestId": "workbench-conflict",
        "matchId": match.id,
        "sourceSha256": "c" * 64,
        "budget": 1.0,
    }
    with TestClient(app, base_url="http://127.0.0.1", raise_server_exceptions=False) as client:
        first = client.post("/api/workbench/jobs", json=workbench_payload)
        assert first.status_code == 200
        original = storage.job_ledger.requests["workbench-conflict"]
        attempt_count = len(storage.job_ledger.attempts["workbench-conflict"])
        reservation_count = len(
            [item for item in storage.job_ledger.costs if item.requestId == "workbench-conflict"]
        )

        repeat = client.post("/api/workbench/jobs", json=workbench_payload)
        assert repeat.status_code == 200
        assert repeat.json()["attemptId"] == first.json()["attemptId"]

        conflict = client.post("/api/workbench/jobs", json={**workbench_payload, "budget": 9.0})
        assert conflict.status_code == 409
        assert conflict.json() == {
            "error": "IDEMPOTENCY_CONFLICT",
            "requestId": "workbench-conflict",
        }
        assert storage.job_ledger.requests["workbench-conflict"] == original
        assert len(storage.job_ledger.attempts["workbench-conflict"]) == attempt_count
        assert len([item for item in storage.job_ledger.costs if item.requestId == "workbench-conflict"]) == reservation_count

        normal = client.post(
            f"/api/matches/{match.id}/jobs",
            json={"requestId": "normal-conflict", "budget": 1.25},
        )
        assert normal.status_code == 202
        normal_repeat = client.post(
            f"/api/matches/{match.id}/jobs",
            json={"requestId": "normal-conflict", "budget": 1.25},
        )
        assert normal_repeat.status_code == 202
        assert normal_repeat.json()["attemptId"] == normal.json()["attemptId"]
        normal_conflict = client.post(
            f"/api/matches/{match.id}/jobs",
            json={"requestId": "normal-conflict", "budget": 4.0},
        )
        assert normal_conflict.status_code == 409
        assert normal_conflict.json() == {
            "error": "IDEMPOTENCY_CONFLICT",
            "requestId": "normal-conflict",
        }
        assert len(storage.job_ledger.attempts["normal-conflict"]) == 1
        assert len([item for item in storage.job_ledger.costs if item.requestId == "normal-conflict"]) == 1


def test_legacy_correction_log_migrates_application_state() -> None:
    log = CorrectionLog.from_payload(json.loads(LEGACY_CORRECTIONS.read_text(encoding="utf-8")))
    saved = log.history("match-legacy")[0]
    pending = log.pending("match-legacy")[0]

    assert saved.commandId == saved.correctionId == "legacy-saved"
    assert saved.applyState == "applied"
    assert saved.migrationNotes == ["APPLICATION_STATE_INFERRED_FROM_SAVE_STATE"]
    assert pending.commandId == pending.correctionId == "legacy-pending"
    assert pending.applyState == "received"
