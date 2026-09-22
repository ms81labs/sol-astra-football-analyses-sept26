"""V3T50 composed lifecycle using synthetic inputs and fake paid boundaries only."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading

import pytest
from fastapi.testclient import TestClient

from backend.app import processor
from backend.app.evaluation_verifier import verify_evaluation_manifest
from backend.app.main import create_app
from backend.app.report_store import ReportStore, StaleEvidenceGeneration
from backend.app.review_service import ReviewService
from backend.app.schemas import ColorClusterSummary, DetectedEvent, MatchConfig
from backend.app.semantic_commands import SemanticCommandError
from backend.app.storage import Storage
from backend.app.workbench.jobs import JobRequest
from backend.tests.test_audit_v3_c01_generations import children as children
from backend.tests.test_audit_v3_c02_journey import _held_reader, _snapshot
from backend.tests.test_audit_v3_c02_projection import profile
from backend.tests.test_audit_v3_c03_journey import _crashing_configuration
from backend.tests.test_audit_v3_c03_reports import _gateway, _interprets
from backend.tests.test_audit_v3_c05_evaluation import fixture as evaluation_fixture
from backend.tests.test_audit_v3_c05_evaluation import policy as evaluation_policy
from backend.tests.test_audit_v3_c06_media import clip


pytestmark = [pytest.mark.integration, pytest.mark.real_media]


def _install_video(storage: Storage, tmp_path: Path) -> str:
    source = clip(tmp_path / "journey.mp4", duration=1, rate=4, size="1000x600")
    match = storage.create_match(
        "V3T50 synthetic video observations", "video", source.name, source,
        MatchConfig(myTeamCluster=0, pitchLengthM=100.0, pitchWidthM=60.0),
    )
    rows = []
    ball_positions = (91.0, 92.0, 50.0, 48.0, 49.0, 50.0, 51.0, 52.0, 53.0, 54.0)
    for frame_id in range(10):
        for track_id, x, colour in ((7, 900.0, 0), (18, 100.0, 1)):
            rows.append({
                "Frame_ID": frame_id, "Timestamp": frame_id / 5,
                "Entity_Type": "player", "Track_ID": track_id,
                "X": 90.0 if track_id == 7 else 10.0,
                "Y": 34.0, "Conf": 0.9,
                "Source_X1": x - 20, "Source_Y1": 100.0,
                "Source_X2": x + 20, "Source_Y2": 300.0,
                "Source_Width": 1000, "Source_Height": 600, "Cluster_ID": colour,
            })
        rows.append({
            "Frame_ID": frame_id, "Timestamp": frame_id / 5,
            "Entity_Type": "ball", "Track_ID": -1,
            "X": ball_positions[frame_id], "Y": 34.0, "Conf": 0.95, "groundPlane": True,
            "Source_X1": ball_positions[frame_id] * 10 - 5, "Source_Y1": 330.0,
            "Source_X2": ball_positions[frame_id] * 10 + 5, "Source_Y2": 340.0,
            "Source_Width": 1000, "Source_Height": 600,
        })
    storage.save_raw_rows(match.id, rows)
    storage.update_match_status(match.id, status="ready", team_clusters=[
        ColorClusterSummary(clusterId=0, rgbCentroid=[255.0, 0.0, 0.0], trackIds=[7]),
        ColorClusterSummary(clusterId=1, rgbCentroid=[0.0, 0.0, 255.0], trackIds=[18]),
    ])
    processor.reprocess_video_match(storage, match.id)
    storage.commit_calibration_for_match(match.id, profile().model_dump(mode="json"))
    return match.id


def _install_tracking(storage: Storage, tmp_path: Path) -> str:
    source = tmp_path / "journey-tracking.json"
    source.write_text(json.dumps([{
        "frameId": frame_id, "timestamp": frame_id / 5,
        "myTeam": [{"id": 7, "x": 12.0 + frame_id, "y": 30.0, "confidence": 0.9}],
        "enemies": [{"id": 18, "x": 80.0 - frame_id, "y": 40.0, "confidence": 0.9}],
        "ball": {"x": 12.0 + frame_id, "y": 30.0, "confidence": 0.95},
    } for frame_id in range(10)]))
    match = storage.create_match(
        "V3T50 declared tracking import", "tracking_json", source.name, source,
        MatchConfig(pitchLengthM=100.0, pitchWidthM=60.0),
    )
    processor.process_match(storage, storage.create_job(match.id).id)
    storage.commit_calibration_for_match(match.id, profile().model_dump(mode="json"))
    return match.id


def _source_inventory(storage: Storage, match_id: str) -> dict[str, str]:
    paths = [storage.get_match_input_path(match_id)]
    if storage.get_match(match_id).inputMode == "video":
        paths.append(storage.generations.root(match_id) / "raw_rows.json")
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def _cost_round_trip(storage: Storage, match_id: str, mode: str) -> None:
    request = JobRequest(
        requestId=f"v3t50-cost-{mode}", matchId=match_id,
        sourceSha256=storage.source_sha256(match_id), intervalStart=0, intervalEnd=1,
        temporalPolicy="source_global_grid", decoderVersion="synthetic",
        modelHash="synthetic-fake-provider", outputSchema="report_draft_v1",
        budget=1.0, authorisedLocation="cloud",
    )
    attempt = storage.job_ledger.admit(request, mode="submit", owner_id="fake", lease_seconds=60)
    storage.job_ledger.record_charge(attempt.attemptId, kind="settled", amount=0.1, evidence_id="partial")
    storage.job_ledger.timeout_before_response(request.requestId, owner_id="fake")
    unknown = storage.job_ledger.cost_for(request.requestId)
    assert unknown["actualTotal"] is None and unknown["settledTotal"] == 0.1
    storage.job_ledger.reconcile_attempt(
        attempt.attemptId, provider_outcome="complete", settled_cost=0.2, receipt_id="final",
    )
    charges = storage.job_ledger.charges_for(attempt.attemptId)
    storage.job_ledger.reconcile_attempt(
        attempt.attemptId, provider_outcome="complete", settled_cost=0.2, receipt_id="final",
    )
    assert storage.job_ledger.charges_for(attempt.attemptId) == charges
    receipt = storage.job_ledger.receipt(request.requestId)
    assert receipt.actualTotal == 0.2 and receipt.attemptCount == 1


@pytest.mark.parametrize("mode", ["video", "tracking_json"])
def test_v3t50_composed_lifecycle(tmp_path, monkeypatch, children, mode):
    scorer_value = os.environ.get("C05_TRACKEVAL_ROOT")
    if not scorer_value:
        pytest.skip("dedicated V3T50 lane supplies the pinned real TrackEval source")
    monkeypatch.setattr(
        processor, "process_video_input",
        lambda *args, **kwargs: pytest.fail("unexpected perception/model execution"),
    )
    storage = Storage(tmp_path / "store")
    match_id = _install_video(storage, tmp_path) if mode == "video" else _install_tracking(storage, tmp_path)
    storage.promote_identity_for_match(match_id, {"reviewed": True})
    initial = _snapshot(storage, match_id)
    inventory = _source_inventory(storage, match_id)
    initial_report = _gateway(storage, _interprets).execute(match_id, "tactical_report")

    reader = children(_held_reader, str(storage.storage_root), match_id)
    assert reader.receive() == ("pinned", initial["generation"])

    ReviewService(storage).configure(match_id, {"attackDirection": "right_to_left"})
    mapping = storage.submit_correction(
        match_id, kind="team_mapping",
        payload={"swap": True, "pair": [0, 1]} if mode == "video" else {"targetRole": "enemy"},
    )
    assert mapping.applyState == "applied"

    split = storage.submit_correction(
        match_id, kind="track_split", payload={"trackId": "7", "atFrame": 5, "newTrackId": 99},
    )
    assert storage.identity_eligibility(match_id)["continuous"] is False
    assert storage.derived_distance_for_match(match_id)["availability"] == "withheld"
    joined = storage.submit_correction(
        match_id, kind="track_join", payload={"leftTrackId": "7", "rightTrackId": "99"},
    )
    with pytest.raises(SemanticCommandError, match="dependent"):
        storage.undo_correction(match_id, split.correctionId)
    storage.undo_correction(match_id, joined.correctionId)
    storage.undo_correction(match_id, split.correctionId)
    storage.promote_identity_for_match(match_id, {"reviewed": True})
    assert storage.identity_eligibility(match_id)["continuous"] is True

    storage.commit_calibration_for_match(match_id, profile(dx=5.0).model_dump(mode="json"))
    players = storage.load_frames(match_id)[0].myTeam + storage.load_frames(match_id)[0].enemies
    expected_x = 95.0 if mode == "video" else 12.0
    assert any(player.id == 7 and player.x == pytest.approx(expected_x) for player in players)

    if not storage.load_events(match_id):
        storage.save_events(match_id, [DetectedEvent(
            type="carry", frameId=9, timestamp=1.8, team="my_team",
            fromTrackId=7, toTrackId=7, description="Declared synthetic carry",
        )])
    event = storage.load_events(match_id)[0]
    event_id = f"event:{event.frameId}:{event.type}:{event.timestamp}"
    storage.submit_correction(match_id, kind="event_reject", payload={"eventId": event_id})
    assert storage.load_events(match_id)[0].reviewStatus == "rejected"
    storage.submit_correction(match_id, kind="event_accept", payload={"eventId": event_id})
    assert storage.load_events(match_id)[0].reviewStatus == "accepted"
    accepted_generation = storage.current_generation(match_id).generationId
    accepted_report = _gateway(storage, _interprets).execute(match_id, "tactical_report")
    assert accepted_report["generationId"] == accepted_generation

    entered, release, stale_calls = threading.Event(), threading.Event(), []

    def blocked_adapter(*args, **kwargs):
        stale_calls.append(kwargs["approved_evidence"]["generationId"])
        entered.set()
        assert release.wait(10)
        return _interprets(*args, **kwargs)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_gateway(storage, blocked_adapter).execute, match_id, "tactical_report")
        assert entered.wait(10)
        ReviewService(storage).configure(match_id, {"attackDirection": "left_to_right"})
        release.set()
        with pytest.raises(StaleEvidenceGeneration):
            future.result(timeout=10)
    assert len(stale_calls) == 1 and ReportStore(storage).view(match_id)["reports"] == {}

    _cost_round_trip(storage, match_id, mode)
    reuse = storage.execute_recompute(match_id, "team_mapping")
    assert reuse.kind == "executed" and reuse.detectorCalls == 0

    writer = children(_crashing_configuration, str(storage.storage_root), match_id)
    assert writer.receive() == ("committed", "after_pointer_publish")
    committed = json.loads((storage.generations.root(match_id) / "current_generation.json").read_text())["generationId"]
    writer.process.kill()
    writer.process.join(10)
    assert not writer.process.is_alive() and writer.process.exitcode != 0
    reopened = Storage(storage.storage_root)
    assert reopened.current_generation(match_id).generationId == committed
    command = next(item for item in reopened.list_corrections(match_id) if item["commandId"] == "c03-crash-command")
    for _ in range(2):
        reopened.recover_correction(match_id, command["correctionId"])
        assert reopened.current_generation(match_id).generationId == committed

    reopened.undo_correction(match_id, mapping.correctionId)
    final_generation = reopened.current_generation(match_id).generationId
    final_report = _gateway(reopened, _interprets).execute(match_id, "tactical_report")
    assert final_report["generationId"] == final_generation

    with TestClient(create_app(storage_root=reopened.storage_root), base_url="http://127.0.0.1") as client:
        current = client.get(f"/api/matches/{match_id}/export/match.json")
        historical = client.get(
            f"/api/matches/{match_id}/export/match.json", params={"generationId": initial["generation"]},
        )
        trust_current = client.get(
            f"/api/matches/{match_id}/trust-crops", params={"generationId": final_generation},
        )
        trust_old = client.get(
            f"/api/matches/{match_id}/trust-crops", params={"generationId": initial["generation"]},
        )
        assert current.status_code == historical.status_code == 200
        assert current.json()["generationId"] == final_generation
        assert historical.json()["generationId"] == initial["generation"]
        assert trust_current.status_code == trust_old.status_code == 200
        assert trust_current.json()["generationId"] == final_generation
        assert trust_old.json()["generationId"] == initial["generation"]
        assert client.get(f"/api/matches/{match_id}/report/html").headers["x-generation-id"] == final_generation
        for kind in ("frames", "events", "metrics"):
            response = client.get(f"/api/matches/{match_id}/export/{kind}.csv")
            assert response.status_code == 200 and response.headers["x-generation-id"] == final_generation

    source = reopened.get_match_input_path(match_id)
    if mode == "video":
        from backend.app.workbench.media import FfmpegFrameSource, FfmpegProbe

        identity = FfmpegFrameSource().probe(source)
        probe = FfmpegProbe()
        output = tmp_path / "journey-clip.mp4"
        probe.export_clip(source, output, start_seconds=0, duration_seconds=0.25)
        assert identity.width == 1000 and output.stat().st_size > 0
        assert hashlib.sha256(source.read_bytes()).hexdigest() == inventory[str(source)]
    else:
        assert reopened.get_match(match_id).inputMode == "tracking_json"

    scorer_root = Path(scorer_value)
    scorer_sha = subprocess.run(
        ["git", "-C", str(scorer_root), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert scorer_sha == "12c8791b303e0a0b50f753af204249e622d0281a"
    manifest_path, manifest, _save = evaluation_fixture(tmp_path / f"evaluation-{mode}")
    gate = verify_evaluation_manifest(
        manifest_path, trackeval_root=scorer_root, acceptance_policy=evaluation_policy(manifest),
    )
    assert gate.accepted and gate.executionStatus == "completed"
    assert gate.executionEvidence["modelInferenceExecuted"] is False

    reader.pipe.send("read")
    old_first, old_last = reader.receive()
    reader.finish()
    assert old_first == old_last == initial
    assert _snapshot(reopened, match_id)["generation"] == final_generation
    assert ReportStore(reopened).view(
        match_id, generation_id=initial_report["generationId"]
    )["status"] == "historical"
    assert _source_inventory(reopened, match_id) == inventory
    assert reopened.list_corrections(match_id)
