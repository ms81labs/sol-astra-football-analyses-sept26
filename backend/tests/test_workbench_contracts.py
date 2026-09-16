from __future__ import annotations

import hashlib
import threading
from pathlib import Path

import pytest

from backend.app.schemas import MatchConfig
from backend.app.workbench.assistance import (
    AssistancePolicy,
    AssistanceRouter,
    execute_typed_query,
    parse_typed_query,
    template_report,
)
from backend.app.workbench.contracts import CAPABILITY_IDS, INTERVAL_ENDPOINT, migrate_legacy_zero, unknown_metric
from backend.app.workbench.dossier import build_baseline_dossier, build_release_dossier, default_capabilities
from backend.app.workbench.evaluation import FROZEN_TASK_COUNT, current_repository_evaluation_gate, evaluate_protocol_prerequisites
from backend.app.workbench.evidence import EvidenceRecord, EvidenceStore, round_trip_unknown, summarize_legacy_match
from backend.app.workbench.geometry import CalibrationProfile, Landmark, detect_zoom_or_cut, evaluate_landmarks, from_legacy_four_points, withhold_if_invalid
from backend.app.workbench.jobs import DurableJobLedger, JobRequest
from backend.app.workbench.media import (
    DecodedFrame,
    FfmpegProbe,
    FixtureFrameSource,
    SamplingAudit,
    align_clip_start_to_grid,
    apply_crop_and_rotation,
    cpu_fallback,
    detect_camera_cuts,
    map_decoded_to_sample,
    pts_to_seconds,
)
from backend.app.workbench.native import native_gate, probe_gpu
from backend.app.workbench.perception import Detection, IdentityRepair, Label, TrackerAdapter, score_detections, separate_ball_states
from backend.app.workbench.review import CorrectionLog, new_correction, playlist_export_interval


def test_match_config_defaults_to_declared_panoramic_profile() -> None:
    config = MatchConfig()
    assert config.cameraProfile == "stitched_panoramic_view"
    assert config.pitchLengthM is None


def test_baseline_dossier_names_inspected_source_and_capability_matrix() -> None:
    dossier = build_baseline_dossier(selected_commit="5099e1fd50d856a7cd0449f1ef4b1695d8f930c3")
    assert dossier.selectedCommit == "5099e1fd50d856a7cd0449f1ef4b1695d8f930c3"
    assert dossier.declaredCameraProfile == "stitched_panoramic_view"
    ids = [entry.id for entry in dossier.capabilities]
    assert ids == list(CAPABILITY_IDS)
    assert "independent_labels_0_of_18" in dossier.unresolvedGates
    assert any("cloud" in action.lower() or "Daytona" in action for action in dossier.forbiddenActions)
    status = {entry.id: entry.status for entry in default_capabilities()}
    assert status["manual_review"] == "usable"
    assert status["physical_metrics"] == "unavailable"
    assert status["player_attribution"] == "unproven"


def test_release_dossier_keeps_loopback_boundary() -> None:
    release = build_release_dossier(build_baseline_dossier(selected_commit="abc"))
    assert release["deploymentBoundary"] == "loopback"
    assert release["gNetworkRequiredForNonLocal"] is True
    assert release["nativeCode"] == "gated_inert"


def test_unknown_metric_survives_json_round_trip() -> None:
    metric = unknown_metric(
        "possession_pct",
        definition_version="1",
        reason_codes=["ZERO_DENOMINATOR"],
        unit="percent",
    )
    restored = round_trip_unknown(metric)
    assert restored.value is None
    assert restored.published_value() is None
    assert restored.availability == "unknown"


def test_legacy_zero_is_not_promoted_to_a_measurement() -> None:
    metric = migrate_legacy_zero(
        "my_team_distance_m",
        0,
        definition_version="1",
        measured=False,
        reason_if_unmeasured="IDENTITY_DISCONTINUITY",
        unit="metres",
    )
    assert metric.value is None
    assert "LEGACY_ZERO_DEFAULT" in metric.reasonCodes
    assert metric.published_value() is None


def test_possession_none_stays_unknown_when_denominator_is_zero() -> None:
    metrics = summarize_legacy_match(
        {"possession": None, "myTeamDistance": 0},
        identity_continuous=False,
        calibration_accepted=False,
        controlled_frames=0,
    )
    possession = next(item for item in metrics if item.metric == "possession_pct")
    distance = next(item for item in metrics if item.metric == "my_team_distance_m")
    assert possession.availability == "unknown"
    assert distance.availability == "unknown"
    assert INTERVAL_ENDPOINT == "half_open"


def test_correction_creates_a_new_version_and_keeps_the_parent() -> None:
    store = EvidenceStore()
    original = store.put(
        EvidenceRecord(
            evidenceId="obs-1",
            observationSource="observed",
            reviewStatus="unreviewed",
            payload={"team": "unassigned"},
        )
    )
    corrected = store.correct("obs-1", new_id="obs-1b", payload={"team": "my_team"})
    assert store.get("obs-1").reviewStatus == "superseded"
    assert store.get("obs-1").supersededBy == "obs-1b"
    assert corrected.parentIds[0] == original.evidenceId
    assert corrected.observationSource == "observed"


def test_vfr_pts_mapping_is_not_frame_index_over_nominal_fps() -> None:
    times = [pts_to_seconds(pts, 1, 90000) for pts in (0, 3000, 9000, 18000)]
    assert times[0] == 0.0
    assert times[1] == pytest.approx(3000 / 90000)
    assert times != [index / 25 for index in range(4)]


def test_off_grid_clip_start_is_explicit(tmp_path: Path) -> None:
    alignment = align_clip_start_to_grid(clip_start_source_frame=13, evaluation_step=5)
    assert alignment["onGrid"] is False
    assert alignment["remainder"] == 3
    assert alignment["policy"] == "source_global_grid"


def test_camera_cut_and_export_sample_contract(tmp_path: Path) -> None:
    frames = [
        DecodedFrame(i, i, t, 8, 8, "bgr", 0, b"\x00", "fixture")
        for i, t in enumerate([0.0, 0.04, 0.08, 5.0, 5.04])
    ]
    identity_bytes = b"fixture-source"
    source = tmp_path / "clip.bin"
    source.write_bytes(identity_bytes)
    adapter = FixtureFrameSource(
        frames,
        identity=__import__("backend.app.workbench.contracts", fromlist=["SourceClockIdentity"]).SourceClockIdentity(
            sourceSha256=hashlib.sha256(identity_bytes).hexdigest(),
            byteSize=len(identity_bytes),
            variableFrameRate=True,
        ),
    )
    probed = adapter.probe(source)
    assert probed.variableFrameRate is True
    decoded = list(adapter.iter_frames(source))
    cuts = detect_camera_cuts([frame.presentation_time_seconds for frame in decoded], jump_seconds=0.5)
    assert cuts == [3]
    exported = [map_decoded_to_sample(frame, frame_interval=2) for frame in decoded]
    assert [item.sourceFrameIndex for item in exported if item] == [0, 2, 4]


def test_sampling_audit_does_not_equate_export_fps_with_inference_fps() -> None:
    audit = SamplingAudit(
        source_sha256="a" * 64,
        declared_target_fps=5.0,
        nominal_fps=25.0,
        frame_interval=5,
        selected_backend="ultralytics_track",
    )
    for _ in range(25):
        audit.record_decoded_frame()
        audit.record_primary_inference()
        audit.record_tracker_update()
    for _ in range(5):
        audit.record_export_sample()
    receipt = audit.receipt()
    assert receipt.primaryInferenceCount == 25
    assert receipt.exportedSampleCount == 5
    assert receipt.export_fps_equals_inference_fps() is False
    assert "EXPORT_FPS_IS_NOT_INFERENCE_FPS" in receipt.notes


def test_ffmpeg_probe_and_cpu_fallback_and_cancellation(tmp_path: Path) -> None:
    clip = tmp_path / "a.mp4"
    clip.write_bytes(b"not-a-real-mp4")

    def runner(command, **kwargs):
        class Result:
            stdout = """{"streams":[{"codec_type":"video","codec_name":"h264","width":1280,"height":720,"avg_frame_rate":"25/1","r_frame_rate":"30/1","time_base":"1/90000","pix_fmt":"yuv420p","tags":{"rotate":"90"}}],"format":{"duration":"2.0"}}"""

        if command[0] == "ffmpeg":
            raise AssertionError("export should have been cancelled")
        return Result()

    probe = FfmpegProbe()
    identity = probe.probe_identity(clip, runner=runner)
    assert identity.variableFrameRate is True
    assert identity.rotation == 90
    assert identity.codec == "h264"
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(RuntimeError, match="cancelled"):
        probe.export_clip(clip, tmp_path / "out.mp4", start_seconds=1.0, duration_seconds=1.0, cancel_event=cancel, runner=runner)
    assert cpu_fallback("torchcodec", {"opencv", "fixture"}) == "opencv"
    transformed = apply_crop_and_rotation(100, 50, crop=(10, 5, 20, 10), rotation=90, colour_order="bgr")
    assert transformed["width"] == 10
    assert transformed["height"] == 20
    assert transformed["colourOrder"] == "bgr"


def test_correction_crash_is_recoverable_and_playlist_opens_source_interval() -> None:
    log = CorrectionLog()
    pending = log.submit(new_correction("m1", "team_mapping", {"cluster": 1}), crash_before_commit=True)
    assert pending.saveState == "pending"
    recovered = log.recover(pending.correctionId)
    assert recovered.saveState == "saved"
    undone = log.undo(recovered.correctionId, author="analyst")
    assert undone.undoOf == recovered.correctionId
    interval = playlist_export_interval(
        {"timestampStart": 12.0, "timestampEnd": 15.2},
        source_fps=25.0,
    )
    assert interval["sourceStartSeconds"] == 12.0
    assert interval["sourceEndFrameExclusive"] == 380


def test_calibration_holdout_and_wrong_landmark_withhold_metrics() -> None:
    identity = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    profile = CalibrationProfile(
        calibrationId="cal-1",
        cameraModel="planar_homography",
        homography=identity,
        landmarks=[
            Landmark(name="near", imageX=10, imageY=10, pitchX=10, pitchY=10, independentHoldout=True),
            Landmark(name="far", imageX=90, imageY=60, pitchX=90, pitchY=60, independentHoldout=True),
            Landmark(name="wrong", imageX=20, imageY=20, pitchX=80, pitchY=80, independentHoldout=True),
        ],
    )
    result = evaluate_landmarks(profile, max_p95_m=3.0)
    assert result["accepted"] is False
    withheld = withhold_if_invalid(profile, "team_width_m", max_p95_m=3.0)
    assert withheld["availability"] == "withheld"
    legacy = from_legacy_four_points(
        [{"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 1, "y": 1}, {"x": 0, "y": 1}],
        calibration_id="legacy",
    )
    assert legacy.compatibleWithFourPointV1 is True
    shifted = profile.model_copy(update={"homography": [[1.4, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]})
    assert detect_zoom_or_cut(profile, shifted) is True


def test_player_and_ball_benchmarks_keep_negatives_and_visibility() -> None:
    detections = [
        Detection(frameId=0, bbox=(0, 0, 10, 10), score=0.9, kind="player", stratum="near"),
        Detection(frameId=0, bbox=(80, 80, 90, 90), score=0.2, kind="player", stratum="far"),
        Detection(frameId=1, bbox=(1, 1, 3, 3), score=0.4, kind="ball", stratum="small", observationSource="observed"),
    ]
    labels = [
        Label(frameId=0, bbox=(0, 0, 10, 10), kind="player", stratum="near"),
        Label(frameId=0, bbox=(40, 40, 42, 42), kind="player", stratum="far"),
        Label(frameId=0, bbox=(80, 80, 90, 90), kind="negative", stratum="negative"),
        Label(frameId=1, bbox=(1, 1, 3, 3), kind="ball", stratum="small", visible=True),
        Label(frameId=2, bbox=(5, 5, 6, 6), kind="ball", stratum="small", visible=False),
    ]
    players = score_detections(detections[:2], labels, task="player_coverage", configuration="baseline_1280", labels_independent=False)
    balls = score_detections(detections[2:], labels, task="ball_detection", configuration="ball_baseline", labels_independent=False)
    assert players.falseNegatives == 1
    assert "negative_hit" in ",".join(players.failureExamples)
    assert balls.recall == 1.0
    assert "LABELS_INCOMPLETE" in players.notes
    assert separate_ball_states([{"source": "observed_ball"}, {"source": "inferred_ball"}, {"source": "unknown"}]) == {
        "visible": 1,
        "inferred": 1,
        "unknown": 1,
    }
    adapter = TrackerAdapter()
    tracks = adapter.associate(detections[:1])
    assert tracks[0]["trackId"].startswith("botsort_baseline")
    repair = IdentityRepair()
    repair.split(tracks[0]["trackId"], 4, author="analyst")
    repair.join("a", "b", author="analyst")
    assert [edit["kind"] for edit in repair.edits] == ["track_split", "track_join"]


def test_typed_search_answers_known_and_unanswerable_queries_without_sql() -> None:
    query = parse_typed_query("show our second-half turnovers followed by a shot within ten seconds")
    assert query.unanswerable is False
    assert query.team == "my_team"
    assert query.period == 2
    assert query.eventFamily == "turnover"
    assert query.successorEvent == "shot"
    assert query.maxGapSeconds == 10.0
    events = [
        {"id": "t1", "type": "turnover", "team": "my_team", "period": 2, "timestamp": 70.0, "evidenceIds": ["e1"]},
        {"id": "s1", "type": "shot", "team": "my_team", "period": 2, "timestamp": 76.0, "evidenceIds": ["e2"]},
        {"id": "t2", "type": "turnover", "team": "my_team", "period": 2, "timestamp": 90.0, "evidenceIds": ["e3"]},
    ]
    hits = execute_typed_query(events, query, match_id="m1")
    assert [hit.eventId for hit in hits] == ["t1"]
    refused = parse_typed_query("select * from events; drop table matches")
    assert refused.unanswerable is True
    assert refused.reason == "refused_code_execution"
    unknown = parse_typed_query("how many fouls did the referee invent")
    assert unknown.unanswerable is True
    assert execute_typed_query(events, unknown, match_id="m1") == []


def test_assistance_rejects_fabricated_evidence_and_falls_back_without_provider() -> None:
    router = AssistanceRouter(providers_enabled=False)
    metrics = [unknown_metric("possession_pct", definition_version="1", reason_codes=["ZERO_DENOMINATOR"]).model_dump(mode="json")]
    rejected = router.run(
        policy=AssistancePolicy(taskType="report"),
        metrics=metrics,
        events=[],
        claimed_evidence_ids=["missing"],
        known_evidence_ids=set(),
    )
    assert rejected.route == "rejected"
    fallback = router.run(policy=AssistancePolicy(taskType="report"), metrics=metrics, events=[])
    assert fallback.route == "template"
    assert fallback.reasonCodes == ["PROVIDER_DISABLED"]
    template = template_report(metrics, [])
    assert template["availableMetrics"] == []


def test_durable_jobs_timeout_cancel_and_refuse_blind_retry() -> None:
    ledger = DurableJobLedger()
    request = JobRequest(
        requestId="req-1",
        matchId="m1",
        sourceSha256="b" * 64,
        intervalStart=0,
        intervalEnd=60,
        temporalPolicy="clip_local_index_modulo",
        decoderVersion="opencv",
        modelHash="m",
        outputSchema="evidence_v1",
        budget=1.5,
        authorisedLocation="local",
    )
    first = ledger.submit(request)
    duplicate = ledger.submit(request)
    assert duplicate.attemptId == first.attemptId
    unknown = ledger.timeout_before_response("req-1")
    assert unknown.status == "outcome_unknown"
    with pytest.raises(RuntimeError, match="reconcile"):
        ledger.retry("req-1")
    ledger.transition("req-1", "failed", error="reconciled_missing")
    second = ledger.retry("req-1")
    assert second.attemptId != first.attemptId
    ledger.cancel("req-1")
    assert ledger.receipt("req-1").status == "cancelling"
    assert ledger.invalidate_for("calibration") == ["pitch_positions", "physical_metrics", "tactical_metrics", "report"]
    failed_cleanup = ledger.confirm_cleanup("req-1", ok=False)
    assert failed_cleanup.cleanupResult == "failed"


def test_evaluation_gate_fails_closed_without_independent_labels() -> None:
    current = current_repository_evaluation_gate()
    assert current.completeTasks == 0
    assert current.requiredTasks == FROZEN_TASK_COUNT
    assert current.accepted is False
    assert "LABELS_INCOMPLETE" in current.reasonCodes
    passing = evaluate_protocol_prerequisites(
        complete_tasks=18,
        complete_minutes=30.0,
        locked_labels_present=True,
        native_predictions_present=True,
        team_declarations_present=True,
        scorer_replayable=True,
    )
    assert passing.accepted is True


def test_gpu_and_native_gates_are_inert_by_default(tmp_path: Path) -> None:
    gpu = probe_gpu(nvidia_smi_ok=False, torch_cuda=False)
    assert gpu.available is False
    assert gpu.canPromoteDefault is False
    gate = native_gate(repo_root=tmp_path, approval_env={})
    assert gate.approved is False
    assert "NATIVE_GATE_CLOSED" in gate.reasonCodes
    assert not (tmp_path / "native").exists()
