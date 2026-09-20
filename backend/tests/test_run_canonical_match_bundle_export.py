from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_canonical_match_bundle_export as bundle_batch
from backend.app.schemas import BallOwnership, DetectedEvent, FrameData, MatchConfig, MatchSummary, PlayerData
from backend.app.storage import Storage


def _seed_ready_match(storage_root: Path, *, published_state: bool = True) -> str:
    storage = Storage(storage_root)
    upload_path = storage.save_upload("sample.json", b"[]")
    match = storage.create_match(
        name="Bundle Match",
        input_mode="tracking_json",
        original_filename="sample.json",
        input_path=upload_path,
        config=MatchConfig(),
    )
    storage.update_match_status(match.id, status="ready")
    storage.save_frames(
        match.id,
        [FrameData(frameId=0, timestamp=0.0, ball={"x": 22.0, "y": 50.0, "confidence": 0.95})],
    )
    storage.save_analytics(
        match.id,
        MatchSummary(
            possession=67,
            myTeamDistance=100,
            enemyDistance=90,
            myTeamAvgPos={"x": 45.0, "y": 50.0},
            enemyAvgPos={"x": 55.0, "y": 50.0},
            myTeamTopSpeed=30.0,
            enemyTopSpeed=29.0,
            myTeamSprints=4,
            enemySprints=3,
            formation="4-3-3",
        ),
        [BallOwnership(frameId=0, timestamp=0.0, team="my_team", trackId=7, distance=1.0)],
        [],
        [],
    )
    storage.save_events(
        match.id,
        [DetectedEvent(type="turnover", frameId=0, timestamp=0.0, team="enemy", description="turnover")],
    )
    storage.save_analysis_artifact(match.id, "accepted_match_state", {"frames": [{"frameId": 0}]})
    storage.save_analysis_artifact(match.id, "ball_pipeline_trace", {"traceVersion": 1})
    if published_state:
        # C03 requires accepted state in the validated generation, not merely
        # a flat file with an incomplete frame. Keep that legacy file as a
        # negative control: it must not override this coherent publication.
        frames = storage.load_frames(match.id)
        frames[0] = frames[0].model_copy(update={
            "myTeam": [PlayerData(id=7, x=21.0, y=50.0, confidence=0.95)],
        })
        summary, assignments, formations, shots = storage.load_analytics(match.id)
        storage.publish_generation(
            match.id, frames=frames, summary=summary, assignments=assignments,
            formation_timeline=formations, shots=shots,
            events=storage.load_events(match.id), correction_head="bundle-fixture",
            accepted_match_state={"frames": [{
                "frameId": 0, "timestamp": 0.0, "mode": "controlled_possession",
                "controllingTeam": "my_team", "controllingTrackId": 7,
                "ballVisibility": "visible", "source": "observed_ball", "confidence": 0.95,
            }]},
        )
    return match.id


def test_canonical_match_bundle_export_writes_sample_bundle_and_truth(tmp_path: Path) -> None:
    match_id = _seed_ready_match(tmp_path)

    payload = bundle_batch.run_canonical_match_bundle_export(storage_root=tmp_path)

    output_root = (
        tmp_path
        / "benchmark_suites"
        / "frozen-viable-baseline-slice-suite"
        / "canonical_match_bundle_export_v1"
    )
    sample_bundle = json.loads((output_root / "sample_match_bundle.json").read_text(encoding="utf-8"))
    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["bundleExportReady"] is True
    assert payload["readyMatchCount"] == 1
    assert payload["sampleMatchId"] == match_id
    assert payload["nextRecommendedNextLever"] == "product_video_to_analysis_smoke_v1"
    assert sample_bundle["schemaVersion"] == "match_bundle_v1"
    assert sample_bundle["match"]["id"] == match_id
    assert sample_bundle["artifactAvailability"]["acceptedMatchState"] is True
    assert (output_root / "canonical_match_bundle_export_summary.json").exists()
    assert (output_root / "bundle_contract_audit.json").exists()
    assert (output_root / "decision_matrix.json").exists()
    assert (output_root / "batch_outcome_analysis.md").exists()


def test_canonical_match_bundle_export_blocks_when_no_ready_match_artifacts(tmp_path: Path) -> None:
    payload = bundle_batch.run_canonical_match_bundle_export(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "canonical_match_bundle_no_ready_match_artifacts"
    assert payload["nextRecommendedNextLever"] == "product_video_to_analysis_smoke_v1"
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False


def test_canonical_match_bundle_export_attempt_plan_has_three_failsafes(tmp_path: Path) -> None:
    _seed_ready_match(tmp_path)

    payload = bundle_batch.run_canonical_match_bundle_export(storage_root=tmp_path)

    assert [item["attemptApproachFamily"] for item in payload["attemptPlan"]] == [
        "persisted_artifact_bundle_contract",
        "bundle_schema_or_api_contract_repair",
        "bundle_export_blocker_summary",
    ]


def test_canonical_bundle_preserves_unverified_flat_state_without_promoting_it(tmp_path: Path) -> None:
    match_id = _seed_ready_match(tmp_path, published_state=False)
    legacy = tmp_path / "matches" / match_id / "accepted_match_state.json"
    original = legacy.read_bytes()

    payload = bundle_batch.run_canonical_match_bundle_export(storage_root=tmp_path)
    sample_path = (tmp_path / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
                   / "canonical_match_bundle_export_v1" / "sample_match_bundle.json")
    bundle = json.loads(sample_path.read_text(encoding="utf-8"))

    assert payload["bundleExportReady"] is True  # Unknown optional state does not erase valid core data.
    assert bundle["artifactAvailability"]["acceptedMatchState"] is False
    assert bundle["acceptedMatchState"]["availability"] == "unknown"
    assert bundle["acceptedMatchState"]["reasonCodes"]
    assert bundle["generationId"] == bundle["acceptedMatchState"]["generationId"]
    assert bundle["events"][0]["description"] == "turnover"
    assert legacy.read_bytes() == original
