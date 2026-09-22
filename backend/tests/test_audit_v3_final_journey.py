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
from backend.tests.test_audit_v3_c01_generations import children as children
from backend.tests.final_journey_process import guarded_journey_child
from backend.tests.test_audit_v3_c02_journey import _snapshot
from backend.tests.test_audit_v3_c02_projection import profile
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


def _team_for_track(storage: Storage, match_id: str, track_id: int) -> str | None:
    frame = storage.load_frames(match_id)[0]
    if any(player.id == track_id for player in frame.myTeam):
        return "my_team"
    if any(player.id == track_id for player in frame.enemies):
        return "enemy"
    return None


def _cost_round_trip(storage: Storage, match_id: str, mode: str) -> str:
    from backend.app.provider_gateway import ProviderGateway, ProviderBudgetLedger
    from backend.app.settings import ProcessingSettings
    from backend.app.workbench.errors import ReconciliationRequired
    from backend.tests.test_audit_v3_c04_providers import fake_policy

    # Only this explicitly fake adapter may dispatch. Its pricing is synthetic.
    config = storage.get_match(match_id).config.model_copy(deep=True)
    permitted = config.model_copy(deep=True)
    permitted.rights.cloudPermission = True
    permitted.rights.processingScope = "local_plus_burst"
    storage.update_match_config(match_id, permitted)
    calls = []

    def adapter(*args, **kwargs):
        calls.append((kwargs["request_id"], kwargs["reservation_id"]))
        assert kwargs["execution_bound"]["maxOutputTokens"] == 25
        raise TimeoutError("synthetic post-dispatch outcome unknown")

    adapter.billing_contract_id = "synthetic-byte-token-v1"
    gateway = ProviderGateway(
        storage,
        ProcessingSettings(
            cloud_provider_enabled=True, cloud_provider_api_key="test-only",
            allowed_model_ids=("test-model",), cloud_model_id="test-model",
            provider_call_reservation=1.0, provider_budget_limit=1.0,
            provider_spend_policy=fake_policy(),
        ),
        adapter_factory=lambda: adapter,
        budget_ledger=ProviderBudgetLedger(storage.job_ledger.db_path, 1.0),
    )
    body = {"requireProvider": True, "requestId": f"v3t50-cost-{mode}"}
    try:
        with pytest.raises(TimeoutError, match="post-dispatch"):
            gateway.execute(match_id, "tactical_report", requested_provider="cloud", body=body)
        assert len(calls) == 1
        request_id, attempt_id = calls[0]
        assert storage.job_ledger.latest_attempt(request_id).status == "outcome_unknown"
        storage.job_ledger.record_charge(attempt_id, kind="settled", amount=0.1, evidence_id="partial")
        unknown = storage.job_ledger.cost_for(request_id)
        assert unknown["actualTotal"] is None and unknown["settledTotal"] == 0.1
        with pytest.raises(ReconciliationRequired):
            gateway.execute(match_id, "tactical_report", requested_provider="cloud", body=body)
        storage.job_ledger.reconcile_attempt(
            attempt_id, provider_outcome="complete", settled_cost=0.2, receipt_id="final",
        )
        charges = storage.job_ledger.charges_for(attempt_id)
        storage.job_ledger.reconcile_attempt(
            attempt_id, provider_outcome="complete", settled_cost=0.2, receipt_id="final",
        )
        # The timed-out report has no cached result. Replay must refuse, not buy it again.
        with pytest.raises(ReconciliationRequired):
            gateway.execute(match_id, "tactical_report", requested_provider="cloud", body=body)
        assert storage.job_ledger.charges_for(attempt_id) == charges and len(calls) == 1
        receipt = storage.job_ledger.receipt(request_id)
        assert receipt.actualTotal == 0.2 and receipt.attemptCount == 1
        assert storage.job_ledger.cost_for(request_id)["authorisedBudget"] == 1.0
        return request_id
    finally:
        storage.update_match_config(match_id, config)


def _fresh_state(root, match_id, pipe):
    try:
        storage = Storage(Path(root))
        costs = {
            request.requestId: storage.job_ledger.receipt(request.requestId).model_dump(mode="json")
            for request in storage.job_ledger.requests.values()
            if request.matchId == match_id and request.scope == "provider"
        }
        pipe.send({"pid": os.getpid(), "snapshot": _snapshot(storage, match_id),
                   "inventory": _source_inventory(storage, match_id), "costs": costs})
    finally:
        pipe.close()


def _recover_twice(root, match_id, pipe):
    storage = Storage(Path(root))
    command = next(item for item in storage.list_corrections(match_id)
                   if item["commandId"] == "c03-crash-command")
    expected = storage.current_generation(match_id).generationId
    history_size = len(storage.list_corrections(match_id))
    for _ in range(2):
        storage.recover_correction(match_id, command["correctionId"])
        assert storage.current_generation(match_id).generationId == expected
        history = storage.list_corrections(match_id)
        assert len(history) == history_size
        recovered = next(item for item in history if item["correctionId"] == command["correctionId"])
        assert recovered["applyState"] == "applied" and recovered["appliedGeneration"] == expected
    _fresh_state(root, match_id, pipe)


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
    assert _team_for_track(storage, match_id, 7) == "my_team"

    reader = children(guarded_journey_child, "held_reader", str(storage.storage_root), match_id)
    assert reader.receive() == ("pinned", initial["generation"])

    ReviewService(storage).configure(match_id, {"attackDirection": "right_to_left"})
    mapping = storage.submit_correction(
        match_id, kind="team_mapping",
        payload={"swap": True, "pair": [0, 1]} if mode == "video" else {"targetRole": "enemy"},
    )
    assert mapping.applyState == "applied"
    assert _team_for_track(storage, match_id, 7) == "enemy"

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

    cost_request_id = _cost_round_trip(storage, match_id, mode)
    reuse = storage.execute_recompute(match_id, "team_mapping")
    assert reuse.kind == "executed" and reuse.detectorCalls == 0

    writer = children(guarded_journey_child, "crashing_writer", str(storage.storage_root), match_id)
    assert writer.receive() == ("committed", "after_pointer_publish")
    committed = json.loads((storage.generations.root(match_id) / "current_generation.json").read_text())["generationId"]
    writer.process.kill()
    writer.process.join(10)
    assert not writer.process.is_alive() and writer.process.exitcode != 0
    # Recovery must not accidentally use this already-imported parent process.
    parent_pid = os.getpid()
    original_recover = Storage.recover_correction

    def require_fresh_recovery(self, *args, **kwargs):
        assert os.getpid() != parent_pid, "recovery must execute in a fresh process"
        return original_recover(self, *args, **kwargs)

    monkeypatch.setattr(Storage, "recover_correction", require_fresh_recovery)
    recovery = children(guarded_journey_child, "recover", str(storage.storage_root), match_id)
    recovered = recovery.receive()
    recovery.finish()
    assert recovered["pid"] not in {parent_pid, writer.process.pid, reader.process.pid}
    assert recovered["snapshot"]["generation"] == committed
    assert recovered["inventory"] == inventory
    assert recovered["costs"][cost_request_id]["actualTotal"] == 0.2
    assert recovered["costs"][cost_request_id]["attemptCount"] == 1
    reopened = Storage(storage.storage_root)
    assert reopened.current_generation(match_id).generationId == committed

    reopened.undo_correction(match_id, mapping.correctionId)
    assert _team_for_track(reopened, match_id, 7) == "my_team"
    persisted_cost = reopened.job_ledger.receipt(cost_request_id)
    assert persisted_cost.actualTotal == 0.2 and persisted_cost.attemptCount == 1
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
    rejected_path, rejected_manifest, _save = evaluation_fixture(
        tmp_path / f"evaluation-rejected-{mode}", prediction=False
    )
    rejected = verify_evaluation_manifest(
        rejected_path,
        trackeval_root=scorer_root,
        acceptance_policy=evaluation_policy(rejected_manifest),
    )
    assert rejected.executionStatus == "completed" and not rejected.accepted
    assert rejected.acceptanceStatus == "failed"

    reader.pipe.send("read")
    old_first, old_last = reader.receive()
    reader.finish()
    assert old_first == old_last == initial
    fresh = children(guarded_journey_child, "state", str(storage.storage_root), match_id)
    final_state = fresh.receive()
    fresh.finish()
    assert final_state["pid"] != parent_pid
    assert final_state["snapshot"] == _snapshot(reopened, match_id)
    assert final_state["snapshot"]["generation"] == final_generation
    assert final_state["inventory"] == inventory
    assert final_state["costs"][cost_request_id]["actualTotal"] == 0.2
    assert final_state["costs"][cost_request_id]["attemptCount"] == 1
    assert ReportStore(reopened).view(
        match_id, generation_id=initial_report["generationId"]
    )["status"] == "historical"
    assert _source_inventory(reopened, match_id) == inventory
    assert reopened.list_corrections(match_id)


def test_cost_round_trip_crosses_the_real_gateway_boundary(tmp_path, monkeypatch):
    from backend.app.provider_gateway import ProviderGateway

    storage = Storage(tmp_path / "cost-store")
    match_id = _install_tracking(storage, tmp_path)
    calls = []
    original = ProviderGateway.execute

    def observe(self, *args, **kwargs):
        calls.append(kwargs.get("requested_provider"))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(ProviderGateway, "execute", observe)
    _cost_round_trip(storage, match_id, "tracking_json")
    assert "cloud" in calls, "composed cost journey never reached the provider gateway"
