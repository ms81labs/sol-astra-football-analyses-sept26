from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from backend.app.main import create_app
from backend.app.processor import process_match, reprocess_video_match
from backend.app.report_export import render_match_report_html
from backend.app.schemas import ColorClusterSummary, MatchConfig
from backend.app.storage import Storage
from backend.app.workbench.review import CorrectionLog


FIXTURE = Path(__file__).parent / "fixtures" / "raw_rows_two_teams.json"
LEGACY_CORRECTIONS = Path(__file__).parent / "fixtures" / "corrections_v1.json"
TRACKING_FIXTURE = Path(__file__).parent / "fixtures" / "sample_tracking.json"


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


def install_tracking_match(storage: Storage) -> str:
    match = storage.create_match(
        "Tracking review",
        "tracking_json",
        TRACKING_FIXTURE.name,
        TRACKING_FIXTURE,
        MatchConfig(),
    )
    process_match(storage, storage.create_job(match.id).id)
    return match.id


def _team_for_track(storage: Storage, match_id: str, track_id: int) -> str | None:
    frame = storage.load_frames(match_id)[0]
    if any(player.id == track_id for player in frame.myTeam):
        return "my_team"
    if any(player.id == track_id for player in frame.enemies):
        return "enemy"
    return None


@pytest.mark.integration
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


def test_t02_tracking_match_without_raw_rows_rebuilds_from_immutable_frames(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "storage")
    match_id = install_tracking_match(storage)
    assert not (storage.storage_root / "matches" / match_id / "raw_rows.json").exists()
    assert _team_for_track(storage, match_id, 7) == "my_team"

    correction = storage.submit_correction(match_id, kind="team_mapping", payload={"swap": True})
    assert correction.applyState == "applied"
    assert _team_for_track(storage, match_id, 7) == "enemy"

    undone = storage.undo_correction(match_id, correction.correctionId)
    assert undone.kind == "undo"
    assert undone.applyState == "applied"
    assert _team_for_track(Storage(storage.storage_root), match_id, 7) == "my_team"


def test_t05_split_join_and_undo_keep_all_track_references_resolvable(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "storage")
    match_id = install_tracking_match(storage)

    split = storage.submit_correction(
        match_id,
        kind="track_split",
        payload={"trackId": "7", "atFrame": 1, "newTrackId": 70},
    )
    assert split.applyState == "applied"
    assert 70 in {player.id for frame in storage.load_frames(match_id)[1:] for player in frame.myTeam}
    _assert_track_references_resolve(storage, match_id)
    process_match(storage, storage.create_job(match_id).id)
    assert 70 in {player.id for frame in storage.load_frames(match_id)[1:] for player in frame.myTeam}

    joined = storage.submit_correction(
        match_id,
        kind="track_join",
        payload={"leftTrackId": "7", "rightTrackId": "70"},
    )
    assert joined.applyState == "applied"
    assert 70 not in {player.id for frame in storage.load_frames(match_id) for player in frame.myTeam}
    _assert_track_references_resolve(storage, match_id)

    storage.undo_correction(match_id, joined.correctionId)
    assert 70 in {player.id for frame in storage.load_frames(match_id)[1:] for player in frame.myTeam}
    _assert_track_references_resolve(storage, match_id)

    storage.undo_correction(match_id, split.correctionId)
    assert 70 not in {player.id for frame in storage.load_frames(match_id) for player in frame.myTeam}
    _assert_track_references_resolve(storage, match_id)


def _assert_track_references_resolve(storage: Storage, match_id: str) -> None:
    frames = storage.load_frames(match_id)
    known = {
        player.id
        for frame in frames
        for player in [*frame.myTeam, *frame.enemies, *frame.unassignedPlayers]
    }
    events = storage.load_events(match_id)
    summary, assignments, _formations, shots = storage.load_analytics(match_id)
    del summary
    references = [
        *(event.fromTrackId for event in events),
        *(event.toTrackId for event in events),
        *(assignment.trackId for assignment in assignments),
        *(shot.playerId for shot in shots),
    ]
    assert {reference for reference in references if reference is not None} <= known


def test_t04_event_review_rebuilds_shots_metrics_and_report_inputs(tmp_path: Path) -> None:
    rows = []
    for frame_id, ball_x in enumerate((91.0, 92.0, 50.0, 48.0)):
        timestamp = frame_id * 0.2
        rows.extend(
            [
                {"Frame_ID": frame_id, "Timestamp": timestamp, "Entity_Type": "ball", "Track_ID": -1, "X": ball_x, "Y": 34.0, "Conf": 0.95},
                {"Frame_ID": frame_id, "Timestamp": timestamp, "Entity_Type": "my_team", "Track_ID": 9, "X": 90.0, "Y": 34.0, "Conf": 0.9},
                {"Frame_ID": frame_id, "Timestamp": timestamp, "Entity_Type": "enemy", "Track_ID": 4, "X": 10.0, "Y": 34.0, "Conf": 0.9},
            ]
        )
    source = tmp_path / "shot.json"
    source.write_text(json.dumps(rows), encoding="utf-8")
    storage = Storage(tmp_path / "storage")
    match = storage.create_match("Shot review", "tracking_json", source.name, source, MatchConfig())
    process_match(storage, storage.create_job(match.id).id)
    shot_event = next(event for event in storage.load_events(match.id) if event.type == "shot")
    assert len(storage.load_analytics(match.id)[3]) == 1
    event_reference = f"event:{shot_event.frameId}:{shot_event.type}:{shot_event.timestamp}"

    rejected = storage.submit_correction(
        match.id,
        kind="event_reject",
        payload={"eventId": event_reference},
    )
    assert rejected.applyState == "applied"
    summary, _assignments, _formations, shots = storage.load_analytics(match.id)
    assert shots == []
    assert summary.myTeamXg is None
    assert next(event for event in storage.load_events(match.id) if event.type == "shot").reviewStatus == "rejected"
    rejected_html = _report_html(summary)
    assert "Unavailable experimental shot quality for my team" in rejected_html

    accepted = storage.submit_correction(
        match.id,
        kind="event_accept",
        payload={"eventId": event_reference},
    )
    assert accepted.applyState == "applied"
    accepted_summary, _assignments, _formations, accepted_shots = storage.load_analytics(match.id)
    assert len(accepted_shots) == 1
    assert accepted_summary.myTeamXg is not None
    assert next(event for event in storage.load_events(match.id) if event.type == "shot").reviewStatus == "accepted"
    assert "Unavailable experimental shot quality for my team" not in _report_html(accepted_summary)
    process_match(storage, storage.create_job(match.id).id)
    assert next(event for event in storage.load_events(match.id) if event.type == "shot").reviewStatus == "accepted"
    assert len(storage.load_analytics(match.id)[3]) == 1

    storage.undo_correction(match.id, accepted.correctionId)
    undone_summary, _assignments, _formations, undone_shots = storage.load_analytics(match.id)
    assert undone_shots == []
    assert undone_summary.myTeamXg is None
    manifest_path = (
        storage.storage_root
        / "matches"
        / match.id
        / "generations"
        / storage.current_generation(match.id).generationId
        / "manifest.json"
    )
    assert "tactical_report" in json.loads(manifest_path.read_text(encoding="utf-8"))["stale"]


def _report_html(summary) -> str:
    return render_match_report_html(
        match_name="Shot review",
        input_mode="tracking_json",
        exported_at="2026-09-18T00:00:00Z",
        summary=summary.model_dump(mode="json"),
        formation_timeline=[],
        event_summary={"eventCounts": {}},
        tactical_report=None,
        drills=None,
    )


def test_t01_normal_routes_persist_and_compatibility_authorities_are_retired(tmp_path: Path) -> None:
    root = tmp_path / "api"
    app = create_app(storage_root=root, run_jobs_inline=False)
    storage: Storage = app.state.storage
    first = install_tracking_match(storage)
    second = install_tracking_match(storage)

    with TestClient(app, base_url="http://127.0.0.1") as client:
        query = client.post(
            f"/api/matches/{first}/queries",
            json={"query": "turnovers", "events": [{"type": "shot", "id": "forged"}]},
        )
        assert query.status_code == 200
        assert query.json()["results"]
        assert {item["matchId"] for item in query.json()["results"]} == {first}

        foreign_evidence = client.get(f"/api/matches/{second}/evidence").json()["items"][0]["evidenceId"]
        report = client.post(
            f"/api/matches/{first}/reports",
            json={"claimedEvidenceIds": [foreign_evidence, "fabricated"], "events": [{"id": "forged"}]},
        )
        assert report.status_code == 200
        assert report.json()["factualCheck"]["accepted"] is False
        assert report.json()["evidenceSelection"]["evidenceIds"] == []

        correction = client.post(
            f"/api/matches/{first}/corrections",
            json={"kind": "team_mapping", "payload": {"swap": True}},
        )
        assert correction.status_code == 200
        assert correction.json()["applyState"] == "applied"

        retired_calls = [
            ("get", f"/api/workbench/matches/{first}/corrections", None),
            ("post", f"/api/workbench/matches/{first}/queries", {"query": "turnovers", "matchId": first}),
            ("post", f"/api/workbench/matches/{first}/reports", {"claimedEvidenceIds": []}),
            ("post", "/api/workbench/search", {"query": "turnovers", "matchId": first}),
            ("post", "/api/workbench/assistance/report", {"claimedEvidenceIds": []}),
            ("post", f"/api/workbench/matches/{first}/metrics", {}),
            ("get", f"/api/workbench/matches/{first}/evidence", None),
            (
                "post",
                "/api/workbench/jobs",
                {"requestId": "retired", "matchId": first, "sourceSha256": "a" * 64, "budget": 0.0},
            ),
        ]
        for method, path, payload in retired_calls:
            response = getattr(client, method)(path, json=payload) if payload is not None else getattr(client, method)(path)
            assert response.status_code == 410, path
            assert response.json()["error"] == "ROUTE_RETIRED"

    restarted_app = create_app(storage_root=root, run_jobs_inline=False)
    with TestClient(restarted_app, base_url="http://127.0.0.1") as client:
        history = client.get(f"/api/matches/{first}/corrections")
        assert history.status_code == 200
        assert history.json()["items"][0]["applyState"] == "applied"
        assert _team_for_track(restarted_app.state.storage, first, 7) == "enemy"


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
        retired = client.post("/api/workbench/jobs", json=workbench_payload)
        assert retired.status_code == 410
        assert retired.json() == {
            "error": "ROUTE_RETIRED",
            "replacement": f"/api/matches/{match.id}/jobs",
        }
        retired_match = client.post(f"/api/workbench/matches/{match.id}/jobs", json=workbench_payload)
        assert retired_match.status_code == 410
        assert retired_match.json()["replacement"] == f"/api/matches/{match.id}/jobs"

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


def test_legacy_outputs_import_as_one_complete_generation_and_recover_pointer(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "storage")
    match_id = install_raw_row_match(storage, tmp_path)
    match_dir = storage.storage_root / "matches" / match_id
    generated = storage.current_generation(match_id)
    generated_dir = match_dir / "generations" / generated.generationId
    for filename in ("frames.json", "events.json", "analytics.json"):
        shutil.copy2(generated_dir / filename, match_dir / filename)
    shutil.rmtree(match_dir / "generations")
    (match_dir / "current_generation.json").unlink()

    # This is deliberately a pre-versioned legacy fixture, not a versioned
    # store whose authority has vanished. C01 never repairs the latter by guessing.
    (match_dir / ".generation-format.json").unlink(missing_ok=True)
    storage.recover_generations(match_id)
    imported = storage.current_generation(match_id)
    assert imported.generationId.startswith("gen_legacy_")
    generation_dir = storage.storage_root / "matches" / match_id / "generations" / imported.generationId
    manifest = json.loads((generation_dir / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["files"]) == {
        "frames.json",
        "events.json",
        "analytics.json",
        "shots.json",
        "summary.json",
    }
    assert all((generation_dir / filename).is_file() for filename in manifest["files"])

    orphan = generation_dir.parent / "gen_orphan"
    orphan.mkdir()
    complete_orphan = generation_dir.parent / "gen_orphan_complete"
    shutil.copytree(generation_dir, complete_orphan)
    orphan_manifest = json.loads((complete_orphan / "manifest.json").read_text(encoding="utf-8"))
    orphan_manifest["generationId"] = complete_orphan.name
    Storage._write_json(complete_orphan / "manifest.json", orphan_manifest)
    recovered = Storage(storage.storage_root).current_generation(match_id)
    assert recovered.generationId == imported.generationId
    assert orphan.exists()
    assert complete_orphan.exists()

    Storage._write_json(
        storage.storage_root / "matches" / match_id / "current_generation.json",
        {"generationId": "gen_missing", "publishedAt": "2026-09-18T00:00:00Z", "correctionHead": "none"},
    )
    from backend.app.generations import GenerationRecoveryRequired
    with pytest.raises(GenerationRecoveryRequired):
        Storage(storage.storage_root).current_generation(match_id)
    assert generation_dir.exists() and complete_orphan.exists()


def test_stale_correction_revision_returns_stable_409(tmp_path: Path) -> None:
    app = create_app(storage_root=tmp_path / "api", run_jobs_inline=False)
    match_id = install_tracking_match(app.state.storage)
    with TestClient(app, base_url="http://127.0.0.1", raise_server_exceptions=False) as client:
        response = client.post(
            f"/api/matches/{match_id}/corrections",
            json={"kind": "team_mapping", "payload": {"swap": True}, "expectedVersion": 99},
        )
    assert response.status_code == 409
    assert response.json() == {"error": "STALE_REVISION", "expected": 99, "actual": 0}


def test_correction_application_error_returns_command_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.review_service import ReviewService

    app = create_app(storage_root=tmp_path / "api", run_jobs_inline=False)
    match_id = install_tracking_match(app.state.storage)
    original_config = app.state.storage.get_match(match_id).config

    def fail_rebuild(*_args, **_kwargs):
        raise RuntimeError("deliberate failure")

    monkeypatch.setattr(ReviewService, "rebuild_generation", fail_rebuild)
    with TestClient(app, base_url="http://127.0.0.1", raise_server_exceptions=False) as client:
        response = client.post(
            f"/api/matches/{match_id}/corrections",
            json={"kind": "team_mapping", "payload": {"swap": True}},
        )
    assert response.status_code == 500
    assert response.json()["error"] == "CORRECTION_APPLICATION_FAILED"
    command_id = response.json()["commandId"]
    assert command_id
    assert app.state.storage.get_match(match_id).config == original_config

    monkeypatch.undo()
    with TestClient(app, base_url="http://127.0.0.1", raise_server_exceptions=False) as client:
        recovered = client.post(f"/api/matches/{match_id}/corrections/{command_id}/recover")
    assert recovered.status_code == 200
    assert recovered.json()["applyState"] == "applied"


def test_generation_reader_cannot_delete_in_progress_publish(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = Storage(tmp_path / "storage")
    match_id = install_tracking_match(storage)
    frames = storage.load_frames(match_id)
    summary, assignments, formations, shots = storage.load_analytics(match_id)
    events = storage.load_events(match_id)
    started = threading.Event()
    release = threading.Event()
    reader_done = threading.Event()
    errors: list[BaseException] = []
    original_write = storage._write_json

    def paused_write(path: Path, payload: object) -> None:
        if path.name == "events.json" and path.parent.name.startswith("gen_"):
            started.set()
            assert release.wait(5)
        original_write(path, payload)

    monkeypatch.setattr(storage, "_write_json", paused_write)

    def publish() -> None:
        try:
            storage.publish_generation(
                match_id,
                frames=frames,
                summary=summary,
                assignments=assignments,
                formation_timeline=formations,
                shots=shots,
                events=events,
                correction_head="none",
            )
        except BaseException as exc:
            errors.append(exc)

    writer = threading.Thread(target=publish)
    writer.start()
    assert started.wait(5)

    def read() -> None:
        storage.current_generation(match_id)
        reader_done.set()

    reader = threading.Thread(target=read)
    reader.start()
    assert reader_done.wait(5), "A reader of committed N must not wait for candidate N+1"
    release.set()
    writer.join(5)
    reader.join(5)
    assert not writer.is_alive() and not reader.is_alive()
    assert errors == []
    current = storage.current_generation(match_id)
    assert (storage._match_dir(match_id) / "generations" / current.generationId / "manifest.json").is_file()


def test_pointer_publish_failure_restores_semantic_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = Storage(tmp_path / "storage")
    match_id = install_tracking_match(storage)
    frames = storage.load_frames(match_id)
    summary, assignments, formations, shots = storage.load_analytics(match_id)
    events = storage.load_events(match_id)
    with storage._connect() as connection:
        before = connection.execute(
            "SELECT analytics_summary_json FROM matches WHERE id = ?", (match_id,)
        ).fetchone()["analytics_summary_json"]
    def fail_pointer(*_args, **_kwargs) -> None:
        raise OSError("pointer unavailable")

    # Inject before the sole pointer commit, not the generic artifact writer.
    monkeypatch.setattr(storage.generations, "_commit_pointer", fail_pointer)
    with pytest.raises(OSError, match="pointer unavailable"):
        storage.publish_generation(
            match_id,
            frames=frames,
            summary=summary.model_copy(update={"formation": "9-0-1"}),
            assignments=assignments,
            formation_timeline=formations,
            shots=shots,
            events=events,
            correction_head="none",
        )
    with storage._connect() as connection:
        after = connection.execute(
            "SELECT analytics_summary_json FROM matches WHERE id = ?", (match_id,)
        ).fetchone()["analytics_summary_json"]
    assert after == before


def test_concurrent_storage_instances_do_not_lose_corrections(tmp_path: Path) -> None:
    root = tmp_path / "storage"
    first = Storage(root)
    match_id = install_tracking_match(first)
    second = Storage(root)
    errors: list[BaseException] = []

    def submit(storage: Storage, kind: str, payload: dict) -> None:
        try:
            storage.submit_correction(match_id, kind=kind, payload=payload)
        except BaseException as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=submit, args=(first, "team_mapping", {"swap": True})),
        threading.Thread(target=submit, args=(second, "identity_validate", {"reviewed": True})),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert all(not thread.is_alive() for thread in threads)
    assert errors == []
    history = Storage(root).list_corrections(match_id)
    assert len(history) == 2
    assert [item["version"] for item in history] == [1, 2]
    assert all(item["applyState"] == "applied" for item in history)


@pytest.mark.integration
@pytest.mark.parametrize(
    "fault_point",
    ["after_log_commit", "during_generation_write", "before_pointer_publish"],
)
def test_t03_crashed_correction_and_undo_recover_once(tmp_path: Path, fault_point: str) -> None:
    storage_root = tmp_path / fault_point
    storage = Storage(storage_root)
    match_id = install_raw_row_match(storage, tmp_path)
    initial = storage.current_generation(match_id)
    storage.close()

    env = {**os.environ, "GA_TEST_FAULTS": "1", "GA_TEST_FAULT_POINT": fault_point}
    submit = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys, types; m=types.ModuleType('ultralytics'); m.YOLO=object; sys.modules['ultralytics']=m; "
                "from backend.app.storage import Storage; "
                "Storage(sys.argv[1]).submit_correction(sys.argv[2], kind='team_mapping', payload={'swap': True})"
            ),
            str(storage_root),
            match_id,
        ],
        env=env,
        check=False,
    )
    assert submit.returncode == 1

    restarted = Storage(storage_root)
    applied = [item for item in restarted.list_corrections(match_id) if item["applyState"] == "applied"]
    assert len(applied) == 1
    assert _team_for_track(restarted, match_id, 7) == "enemy"
    recovered = restarted.current_generation(match_id)
    assert recovered.generationId != initial.generationId
    generation_dir = storage_root / "matches" / match_id / "generations" / recovered.generationId
    assert (generation_dir / "manifest.json").is_file()
    from backend.app.review_service import ReviewService

    assert ReviewService(restarted).apply_pending(match_id) == []
    assert restarted.current_generation(match_id).generationId == recovered.generationId
    correction_id = applied[0]["correctionId"]
    restarted.close()

    undo = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys, types; m=types.ModuleType('ultralytics'); m.YOLO=object; sys.modules['ultralytics']=m; "
                "from backend.app.storage import Storage; "
                "Storage(sys.argv[1]).undo_correction(sys.argv[2], sys.argv[3])"
            ),
            str(storage_root),
            match_id,
            correction_id,
        ],
        env=env,
        check=False,
    )
    assert undo.returncode == 1
    after_undo = Storage(storage_root)
    history = after_undo.list_corrections(match_id)
    assert len([item for item in history if item["kind"] == "undo" and item["applyState"] == "applied"]) == 1
    assert _team_for_track(after_undo, match_id, 7) == "my_team"
    undo_generation = after_undo.current_generation(match_id).generationId
    assert undo_generation != recovered.generationId
    assert ReviewService(after_undo).apply_pending(match_id) == []
    assert after_undo.current_generation(match_id).generationId == undo_generation
