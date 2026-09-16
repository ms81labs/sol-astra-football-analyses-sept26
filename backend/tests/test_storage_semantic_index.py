from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
import time

from backend.app.schemas import MatchConfig, MatchSummary
from backend.app.storage import Storage


def _summary(*, possession: int | None = 50) -> MatchSummary:
    return MatchSummary(
        possession=possession,
        myTeamDistance=1,
        enemyDistance=2,
        myTeamAvgPos={"x": 50, "y": 50},
        enemyAvgPos={"x": 50, "y": 50},
        myTeamTopSpeed=1,
        enemyTopSpeed=2,
        myTeamSprints=3,
        enemySprints=4,
        formation="4-3-3",
    )


def test_existing_database_adds_analytics_summary_index_column(tmp_path) -> None:
    with sqlite3.connect(tmp_path / "guerilla.sqlite3") as connection:
        connection.execute(
            """
            CREATE TABLE matches (
                id TEXT PRIMARY KEY, admission_token TEXT, name TEXT NOT NULL,
                input_mode TEXT NOT NULL, status TEXT NOT NULL,
                original_filename TEXT NOT NULL, input_path TEXT NOT NULL,
                config_json TEXT NOT NULL, requires_team_selection INTEGER NOT NULL DEFAULT 0,
                team_clusters_json TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )
            """
        )

    storage = Storage(tmp_path)

    with storage._connect() as connection:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(matches)")}
    assert "analytics_summary_json" in columns


def test_saved_analytics_summary_is_indexed_with_read_truth_normalization(tmp_path, monkeypatch) -> None:
    storage = Storage(tmp_path)
    match = storage.create_match("indexed", "video", "clip.mp4", tmp_path / "clip.mp4", MatchConfig())
    storage.save_analytics(match.id, _summary(), [], [], [])
    storage.update_match_status(match.id, status="ready")
    artifact_reads = 0

    def reject_artifact_read(_path):
        nonlocal artifact_reads
        artifact_reads += 1
        raise AssertionError("full analytics read")

    monkeypatch.setattr(storage, "_read_json", reject_artifact_read)

    results = storage.list_matches_with_analytics()

    assert len(results) == 1
    assert results[0]["summary"]["possession"] is None
    assert results[0]["summary"]["ballSignalStatus"] == "untrusted"
    assert artifact_reads == 0


def test_historical_analytics_summary_is_backfilled_once(tmp_path, monkeypatch) -> None:
    storage = Storage(tmp_path)
    match = storage.create_match("legacy", "tracking_json", "tracks.json", tmp_path / "tracks.json", MatchConfig())
    storage._write_json(
        storage._match_dir(match.id) / "analytics.json",
        {
            "summary": _summary(possession=None).model_dump(mode="json"),
            "ballAssignments": [],
            "formationTimeline": [],
            "shots": [],
        },
    )
    storage.update_match_status(match.id, status="completed")

    assert storage.list_matches_with_analytics()[0]["matchId"] == match.id
    monkeypatch.setattr(storage, "load_analytics", lambda _match_id: (_ for _ in ()).throw(AssertionError("legacy summary was not backfilled")))
    assert storage.list_matches_with_analytics()[0]["summary"]["formation"] == "4-3-3"


def test_indexed_match_listing_scales_without_reading_full_analytics(tmp_path, monkeypatch) -> None:
    storage = Storage(tmp_path)
    count = 2_000
    now = datetime.now(timezone.utc).isoformat()
    summary_json = _summary(possession=None).model_dump_json()
    config_json = MatchConfig().model_dump_json()
    with storage._connect() as connection:
        connection.executemany(
            """
            INSERT INTO matches (
                id, name, input_mode, status, original_filename, input_path,
                config_json, analytics_summary_json, created_at, updated_at
            ) VALUES (?, ?, 'tracking_json', 'completed', 'tracks.json', ?, ?, ?, ?, ?)
            """,
            (
                (f"match-{index}", f"Match {index}", str(tmp_path / "tracks.json"), config_json, summary_json, now, now)
                for index in range(count)
            ),
        )
    artifact_reads = 0

    def reject_artifact_read(_path):
        nonlocal artifact_reads
        artifact_reads += 1
        raise AssertionError("full analytics read")

    monkeypatch.setattr(storage, "_read_json", reject_artifact_read)

    started = time.perf_counter()
    results = storage.list_matches_with_analytics()
    elapsed = time.perf_counter() - started

    assert len(results) == count
    assert elapsed < 2.0
    assert artifact_reads == 0
