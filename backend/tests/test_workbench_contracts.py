from __future__ import annotations

import hashlib
import json
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
from backend.app.workbench.evidence import EvidenceRecord, EvidenceStore, evaluate_metric_spec, metric_dictionary, round_trip_unknown, summarize_legacy_match
from backend.app.workbench.geometry import CalibrationProfile, Landmark, detect_zoom_or_cut, evaluate_landmarks, from_legacy_four_points, review_incident_geometry, withhold_if_invalid
from backend.app.workbench.jobs import DurableJobLedger, JobRequest
from backend.app.workbench.media import (
    DecodedFrame,
    FfmpegFrameSource,
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
from backend.app.workbench.store import WorkbenchStore
from backend.app.workbench.native import native_gate, probe_gpu
from backend.app.workbench.perception import Detection, IdentityRepair, Label, TrackerAdapter, score_detections, score_detections_by_stratum, separate_ball_states
from backend.app.workbench.review import CorrectionLog, new_correction, playlist_export_interval


def test_match_config_defaults_to_declared_panoramic_profile() -> None:
    config = MatchConfig()
    assert config.cameraProfile == "stitched_panoramic_view"
    assert config.pitchLengthM is None
    assert config.periods == []
    assert config.rights.processingScope == "local_only"
    assert config.rights.cloudPermission is False
    assert config.rights.retentionClass == "unknown"


def test_match_config_records_periods_dimensions_and_rights() -> None:
    config = MatchConfig(
        pitchLengthM=105,
        pitchWidthM=68,
        periods=[{"name": "first_half", "startSeconds": 0, "endSeconds": 2700}],
        rights={"processingScope": "local_only", "cloudPermission": False, "retentionClass": "review"},
    )
    assert config.pitchLengthM == 105
    assert config.periods[0].name == "first_half"
    assert config.rights.retentionClass == "review"


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


def test_iter_bgr_frames_uses_injected_frame_source_as_production_decode_path(tmp_path: Path) -> None:
    from backend.app.workbench.media import iter_bgr_frames

    frames = [
        DecodedFrame(0, 0, 0.0, 2, 2, "bgr", 0, b"aa", "fixture", image=object()),
        DecodedFrame(1, 1, 0.04, 2, 2, "bgr", 0, b"bb", "fixture", image=object()),
    ]
    source = tmp_path / "clip.bin"
    source.write_bytes(b"src")
    adapter = FixtureFrameSource(
        frames,
        identity=__import__("backend.app.workbench.contracts", fromlist=["SourceClockIdentity"]).SourceClockIdentity(
            sourceSha256="a" * 64,
            byteSize=3,
        ),
    )
    decoded = list(iter_bgr_frames(source, adapter))
    assert [frame.source_frame_index for frame in decoded] == [0, 1]
    assert all(frame.image is not None for frame in decoded)


def test_recover_ball_rows_uses_injected_frame_source_without_opening_video(tmp_path: Path) -> None:
    import numpy as np

    from backend.app.workbench.contracts import SourceClockIdentity
    from backend.run_guerilla import recover_ball_rows

    class ClosedSource:
        name = "fixture"

        def probe(self, path):
            return SourceClockIdentity(sourceSha256="a" * 64, byteSize=path.stat().st_size, decodeErrors=["opencv_open_failed"])

        def iter_frames(self, path, *, cancel_event=None):
            del path, cancel_event
            if False:
                yield None

    video = tmp_path / "clip.bin"
    video.write_bytes(b"src")
    rows = recover_ball_rows(
        str(video),
        model=object(),
        H=np.eye(3),
        pitch_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        fps=25,
        frame_interval=5,
        frame_source=ClosedSource(),
    )
    assert rows == []


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


def test_durable_jobs_quarantine_partial_output_and_cap_retries() -> None:
    ledger = DurableJobLedger()
    request = JobRequest(
        requestId="req-q",
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
    ledger.submit(request)
    quarantined = ledger.import_attempt(
        "req-q",
        sha256="deadbeef",
        expected_sha256="cafebabe",
        schema_ok=True,
        complete=False,
    )
    assert quarantined.status == "failed"
    assert quarantined.error == "quarantined_partial_or_corrupt"
    ledger.retry("req-q")
    ledger.transition("req-q", "failed", error="reconciled")
    ledger.retry("req-q")
    ledger.transition("req-q", "failed", error="reconciled")
    with pytest.raises(RuntimeError, match="retry budget"):
        ledger.retry("req-q")
    exhausted = ledger.disk_exhaustion("req-q")
    assert exhausted.error == "disk_exhaustion"
    assert exhausted.status == "failed"


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


def test_metric_specs_withhold_physical_totals_and_unknown_ppda() -> None:
    dictionary = metric_dictionary()
    assert dictionary["experimental_shot_quality"]["publishedLabel"] == "experimental_shot_quality"
    assert "xg" in dictionary["experimental_shot_quality"]["compatibilityFields"]
    withheld = evaluate_metric_spec(
        "my_team_distance_m",
        value=412.0,
        denominator=18.0,
        identity_continuous=False,
        calibration_accepted=True,
    )
    assert withheld.availability == "withheld"
    assert withheld.published_value() is None
    unknown = evaluate_metric_spec(
        "my_team_ppda",
        value=0.0,
        denominator=0.0,
        identity_continuous=True,
        calibration_accepted=True,
    )
    assert unknown.availability == "unknown"
    assert "ZERO_DENOMINATOR" in unknown.reasonCodes


def test_cache_identity_is_incompatible_when_decoder_or_model_changes() -> None:
    from backend.app.workbench.cache import cache_compatible, cache_identity

    opencv = cache_identity(
        source_sha256="a" * 64,
        interval_start=0.0,
        interval_end=60.0,
        decoder_version="opencv",
        model_hash="weights-v1",
        temporal_policy="clip_local_index_modulo",
        output_schema="evidence_v1",
        crop=None,
        colour_order="bgr",
    )
    ffmpeg = cache_identity(
        source_sha256="a" * 64,
        interval_start=0.0,
        interval_end=60.0,
        decoder_version="ffmpeg",
        model_hash="weights-v1",
        temporal_policy="clip_local_index_modulo",
        output_schema="evidence_v1",
        crop=None,
        colour_order="bgr",
    )
    assert opencv != ffmpeg
    assert cache_compatible(opencv, opencv) is True
    assert cache_compatible(opencv, ffmpeg) is False


def test_ffmpeg_frame_source_is_a_cancellable_decoder_challenger(tmp_path: Path) -> None:
    frames = [
        DecodedFrame(0, 0, 0.0, 2, 2, "bgr", 0, b"aa", "ffmpeg", image=object()),
        DecodedFrame(1, 1, 0.04, 2, 2, "bgr", 0, b"bb", "ffmpeg", image=object()),
    ]
    source = tmp_path / "clip.bin"
    source.write_bytes(b"src")
    adapter = FfmpegFrameSource(
        frames=frames,
        identity=__import__("backend.app.workbench.contracts", fromlist=["SourceClockIdentity"]).SourceClockIdentity(
            sourceSha256="a" * 64,
            byteSize=3,
            codec="h264",
        ),
    )
    assert adapter.name == "ffmpeg"
    assert list(adapter.iter_frames(source))[0].backend == "ffmpeg"
    cancel = threading.Event()
    cancel.set()
    assert list(adapter.iter_frames(source, cancel_event=cancel)) == []
    assert cpu_fallback("ffmpeg", {"opencv", "ffmpeg"}) == "ffmpeg"


def test_incident_geometry_does_not_publish_a_validated_offside_decision() -> None:
    review = review_incident_geometry(
        my_team=[{"id": 7, "x": 8.0, "y": 50.0}],
        enemies=[{"id": 18, "x": 12.0, "y": 48.0}, {"id": 19, "x": 14.0, "y": 52.0}],
        ball={"x": 20.0, "y": 50.0},
        attack_direction="left_to_right",
    )
    assert review["decision"] is None
    assert review["availability"] == "review_only"
    assert review["validatedMeasurement"] is False
    assert "IFAB_LAW_11_NOT_APPLIED" in review["reasonCodes"]
    assert review["secondLastOpponentX"] == 12.0


def test_tiling_benchmark_reports_far_stratum_separately() -> None:
    detections = [
        Detection(frameId=0, bbox=(0, 0, 10, 10), score=0.9, kind="player", stratum="near"),
        Detection(frameId=0, bbox=(80, 80, 90, 90), score=0.2, kind="player", stratum="far"),
    ]
    labels = [
        Label(frameId=0, bbox=(0, 0, 10, 10), kind="player", stratum="near"),
        Label(frameId=0, bbox=(40, 40, 42, 42), kind="player", stratum="far"),
    ]
    receipt = score_detections_by_stratum(
        detections,
        labels,
        task="player_coverage",
        configuration="tiles_1280",
        labels_independent=False,
    )
    assert receipt.byStratum["near"].recall == 1.0
    assert receipt.byStratum["far"].falseNegatives == 1
    assert receipt.labelsIndependent is False


def test_ai_policy_grounds_outputs_and_refuses_fabricated_evidence() -> None:
    from backend.app.ai_policy import ground_output, select_evidence

    assert select_evidence(["e1", "e2"], known_ids={"e1", "e2"}) == ["e1", "e2"]
    rejected = ground_output({"summary": "ok", "evidence": ["missing"]}, known_ids={"e1"})
    assert rejected["route"] == "rejected"
    assert "FABRICATED_EVIDENCE" in rejected["reasonCodes"]
    grounded = ground_output({"summary": "ok", "evidence": ["e1"]}, known_ids={"e1"})
    assert grounded["route"] == "template"
    assert grounded["output"]["evidence"] == ["e1"]


def test_job_receipt_includes_cache_identity_and_treats_cancel_as_a_request() -> None:
    from backend.app.workbench.cache import cache_identity

    ledger = DurableJobLedger()
    request = JobRequest(
        requestId="req-cache",
        matchId="m1",
        sourceSha256="d" * 64,
        intervalStart=0.0,
        intervalEnd=30.0,
        temporalPolicy="clip_local_index_modulo",
        decoderVersion="opencv",
        modelHash="weights-v1",
        outputSchema="evidence_v1",
        budget=2.0,
        authorisedLocation="local",
    )
    ledger.submit(request)
    receipt = ledger.receipt("req-cache")
    expected = cache_identity(
        source_sha256="d" * 64,
        interval_start=0.0,
        interval_end=30.0,
        decoder_version="opencv",
        model_hash="weights-v1",
        temporal_policy="clip_local_index_modulo",
        output_schema="evidence_v1",
    )
    assert receipt.cacheIdentity == expected
    cancelled = ledger.cancel("req-cache")
    assert cancelled.status == "cancelling"
    assert ledger.cancel_requested("req-cache") is True
    assert ledger.terminated("req-cache") is False


def test_atomic_artifact_publication_leaves_no_accepted_partial(tmp_path: Path) -> None:
    store = WorkbenchStore(tmp_path)
    with pytest.raises(RuntimeError, match="interrupted"):
        store.publish_artifact("observations.json", {"rows": [1]}, interrupt=True)
    assert store.accepted_artifact("observations.json") is None
    published = store.publish_artifact("observations.json", {"rows": [1]})
    assert published.exists()
    restored = store.restore_to(tmp_path / "disposable-restore")
    assert (restored / "artifacts" / "observations.json").exists()
    assert json.loads((restored / "artifacts" / "observations.json").read_text(encoding="utf-8")) == {"rows": [1]}


def test_evidence_interval_query_is_half_open_and_cursor_bounded() -> None:
    store = EvidenceStore()
    store.put(
        EvidenceRecord(
            evidenceId="e-early",
            observationSource="observed",
            reviewStatus="unreviewed",
            intervalStart=0.0,
            intervalEnd=10.0,
        )
    )
    store.put(
        EvidenceRecord(
            evidenceId="e-late",
            observationSource="inferred",
            reviewStatus="unreviewed",
            intervalStart=10.0,
            intervalEnd=20.0,
        )
    )
    window = store.query(interval_start=0.0, interval_end=10.0)
    assert [item.evidenceId for item in window.items] == ["e-early"]
    page = store.query(interval_start=0.0, interval_end=20.0, limit=1)
    assert [item.evidenceId for item in page.items] == ["e-early"]
    assert page.nextCursor == "e-late"
    next_page = store.query(interval_start=0.0, interval_end=20.0, cursor=page.nextCursor, limit=10)
    assert [item.evidenceId for item in next_page.items] == ["e-late"]
    assert INTERVAL_ENDPOINT == "half_open"


def test_feature_flags_keep_experimental_metrics_and_native_code_shadowed() -> None:
    from backend.app.workbench.flags import feature_enabled

    assert feature_enabled("experimental_shot_quality", env={}) is False
    assert feature_enabled("gpu_default", env={}) is False
    assert feature_enabled("native_code", env={}) is False
    assert feature_enabled("experimental_shot_quality", env={"GA_FLAG_EXPERIMENTAL_SHOT_QUALITY": "1"}) is True


def test_frame_buffer_refuses_use_after_reuse() -> None:
    from backend.app.workbench.media import FrameBuffer

    buffer = FrameBuffer(
        device="cpu",
        shape=(2, 2, 3),
        strides=(12, 6, 2),
        dtype="uint8",
        lifetime="borrowed",
        batch_index=0,
        sync_required=False,
        payload=b"frame",
    )
    assert buffer.as_array() == b"frame"
    buffer.release()
    with pytest.raises(RuntimeError, match="use after buffer reuse"):
        buffer.as_array()


def test_nearest_player_alone_is_not_controlled_possession() -> None:
    from backend.app.workbench.ownership import classify_ownership

    nearest_only = classify_ownership(
        ball_visible=True,
        nearest_team="my_team",
        nearest_distance=2.0,
        relative_motion=None,
        persistence_frames=1,
        calibrated=False,
    )
    assert nearest_only.mode == "unknown"
    assert "NEAREST_PLAYER_INSUFFICIENT" in nearest_only.reasonCodes
    asserted = classify_ownership(
        ball_visible=True,
        nearest_team="my_team",
        nearest_distance=2.0,
        relative_motion="closing",
        persistence_frames=4,
        calibrated=True,
    )
    assert asserted.mode == "controlled_possession"
    assert asserted.controllingTeam == "my_team"


def test_ownership_hysteresis_avoids_alternating_owners() -> None:
    from backend.app.workbench.ownership import OwnershipHysteresis

    hyst = OwnershipHysteresis(min_persistence=3)
    first = hyst.observe("my_team")
    second = hyst.observe("enemy")
    third = hyst.observe("enemy")
    held = hyst.observe("enemy")
    assert first == "unknown"
    assert second == "unknown"
    assert third == "unknown"
    assert held == "enemy"


def test_possession_discloses_unknown_duration_instead_of_full_match_certainty() -> None:
    from backend.app.workbench.ownership import possession_from_states

    summary = possession_from_states(
        [
            {"mode": "controlled_possession", "controllingTeam": "my_team", "seconds": 10.0},
            {"mode": "unknown", "controllingTeam": "none", "seconds": 20.0},
            {"mode": "controlled_possession", "controllingTeam": "enemy", "seconds": 10.0},
        ],
        requested_seconds=40.0,
    )
    assert summary.availability == "insufficient_coverage"
    assert summary.unknownSeconds == 20.0
    assert summary.published_value() is None
    assert "UNKNOWN_INTERVALS_EXCLUDED" in summary.reasonCodes


def test_pass_candidate_is_an_interval_and_stays_unaccepted() -> None:
    from backend.app.workbench.events import propose_event

    withheld = propose_event(
        family="pass",
        release={"playerId": 7, "team": "my_team", "time": 12.0},
        receipt=None,
    )
    assert withheld.status == "withheld"
    candidate = propose_event(
        family="pass",
        release={"playerId": 7, "team": "my_team", "time": 12.0},
        receipt={"playerId": 11, "team": "my_team", "time": 13.4},
    )
    assert candidate.status == "candidate"
    assert candidate.intervalStart == 12.0
    assert candidate.intervalEnd == 13.4
    assert candidate.timingUncertainty is not None
    assert candidate.accepted is False


def test_event_scorer_uses_frozen_tolerances_and_reports_boundary_error() -> None:
    from backend.app.workbench.events import score_events

    receipt = score_events(
        predictions=[{"family": "shot", "intervalStart": 8.0, "intervalEnd": 9.2}],
        labels=[{"family": "shot", "intervalStart": 8.0, "intervalEnd": 8.4}],
        labels_independent=False,
    )
    assert receipt.byClass["shot"].boundaryErrors == 1
    assert receipt.toleranceSeconds == 0.5
    assert receipt.labelsIndependent is False


def test_shot_model_rejects_post_outcome_features_and_stays_experimental() -> None:
    from backend.app.workbench.shot_model import experimental_shot_quality, extract_shot_features

    with pytest.raises(ValueError, match="post-outcome"):
        extract_shot_features({"x": 88.0, "y": 50.0, "goal": True})
    features = extract_shot_features({"x": 88.0, "y": 50.0, "inBox": True})
    score = experimental_shot_quality(features)
    assert score.publishedLabel == "experimental_shot_quality"
    assert score.availability == "experimental"
    assert "xg" in score.compatibilityFields


def test_tracklet_is_not_promoted_to_a_roster_identity() -> None:
    from backend.app.workbench.identity import IdentityRecord, promote_identity

    tracklet = IdentityRecord(kind="tracklet", trackId="t-4", intervalStart=0.0, intervalEnd=3.0)
    assert promote_identity(tracklet, target="roster_player", reviewed=False).kind == "tracklet"
    match_id = promote_identity(tracklet, target="match_identity", reviewed=True)
    assert match_id.kind == "match_identity"
    roster = promote_identity(match_id, target="roster_player", reviewed=True, rosterId="shirt-9")
    assert roster.kind == "roster_player"
    assert roster.rosterId == "shirt-9"


def test_match_package_omits_credentials_and_keeps_limitations() -> None:
    from backend.app.workbench.package import assemble_match_package

    package = assemble_match_package(
        playlist=[{"start": 3.0, "end": 5.0, "evidenceIds": ["e1"]}],
        events=[{"eventId": "event-52", "status": "accepted", "family": "turnover"}],
        metrics=[{"metric": "possession_pct", "availability": "unknown", "value": None}],
        corrections=[{"correctionId": "edit-8"}],
        cost={"reservedTotal": 1.5, "actualTotal": 0.0},
        secrets={"DAYTONA_API_KEY": "must-not-leak"},
    )
    blob = str(package)
    assert "must-not-leak" not in blob
    assert "DAYTONA_API_KEY" not in blob
    assert package["analyst"]["limitations"]
    assert package["operator"]["cleanupStatus"]


def test_uncertain_commercial_permission_blocks_use() -> None:
    from backend.app.workbench.rights import evaluate_rights

    blocked = evaluate_rights({"asset": "soccernet_clip", "commercialPermission": "uncertain", "licence": "research"})
    assert blocked.allowed is False
    assert "UNCERTAIN_COMMERCIAL_PERMISSION" in blocked.reasonCodes
    local = evaluate_rights({"asset": "club_upload", "commercialPermission": "granted", "licence": "club_agreement", "cloudPermitted": False})
    assert local.allowed is True
    assert local.cloudPermitted is False


def test_gpu_benchmark_receipts_stay_experimental_without_hardware() -> None:
    from backend.app.workbench.benchmarks import experiment_receipt

    b0 = experiment_receipt("B0", hardware_verified=False)
    assert b0.promoted is False
    assert b0.exportFpsEqualsInferenceFps is False
    b2 = experiment_receipt("B2", hardware_verified=False)
    assert b2.status == "experimental"
    assert "HARDWARE_UNAVAILABLE" in b2.reasonCodes
    native = experiment_receipt("B5", hardware_verified=True, bottleneck_documented=False)
    assert native.status == "inert"
    assert "NATIVE_GATE_CLOSED" in native.reasonCodes


def test_assistance_caps_survive_spend_timeout_and_malformed_output() -> None:
    from backend.app.workbench.assistance import AssistancePolicy, AssistanceRouter

    metrics = [{"metric": "possession_pct", "availability": "unknown", "value": None, "reasonCodes": ["ZERO_DENOMINATOR"]}]

    def boom(**kwargs):
        raise TimeoutError("provider timeout")

    timed_out = AssistanceRouter(providers_enabled=True, provider=boom).run(
        policy=AssistancePolicy(taskType="report", spendCap=1.0, allowedModelIds=["local-1"]),
        metrics=metrics,
        events=[],
    )
    assert timed_out.route == "template"
    assert "PROVIDER_TIMEOUT" in timed_out.reasonCodes
    assert timed_out.output["availableMetrics"] == []

    def malformed(**kwargs):
        return "not-json"

    broken = AssistanceRouter(providers_enabled=True, provider=malformed).run(
        policy=AssistancePolicy(taskType="report", spendCap=1.0, allowedModelIds=["local-1"]),
        metrics=metrics,
        events=[],
    )
    assert broken.route == "template"
    assert "MALFORMED_PROVIDER_OUTPUT" in broken.reasonCodes

    def echo_metric(**kwargs):
        return {"possession_pct": 57, "evidence": []}

    guarded = AssistanceRouter(providers_enabled=True, provider=echo_metric).run(
        policy=AssistancePolicy(taskType="report", spendCap=1.0, allowedModelIds=["local-1"]),
        metrics=metrics,
        events=[],
    )
    assert guarded.output.get("possession_pct") != 57
    assert metrics[0]["value"] is None

    router = AssistanceRouter(providers_enabled=True, provider=lambda **kwargs: {"ok": True, "evidence": []})
    policy = AssistancePolicy(taskType="report", spendCap=0.4, allowedModelIds=["local-1"], reservedCallCost=0.3, maxCalls=10)
    first = router.run(policy=policy, metrics=metrics, events=[])
    second = router.run(policy=policy, metrics=metrics, events=[])
    assert first.route in {"local", "template"}
    assert second.route == "template"
    assert "SPEND_CAP" in second.reasonCodes or second.spend >= policy.spendCap

