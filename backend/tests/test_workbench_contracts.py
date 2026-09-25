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
    TypedQuery,
    execute_typed_query,
    parse_typed_query,
    validate_query_proposal,
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


def test_iter_bgr_frames_wraps_payload_in_frame_buffer_and_releases_previous(tmp_path: Path) -> None:
    from backend.app.workbench.media import FrameBuffer, iter_bgr_frames

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
    iterator = iter_bgr_frames(source, adapter)
    first = next(iterator)
    assert isinstance(first.buffer, FrameBuffer)
    assert first.buffer.device == "cpu"
    assert first.buffer.lifetime == "borrowed"
    assert first.buffer.as_array() == b"aa"
    second = next(iterator)
    with pytest.raises(RuntimeError, match="use after buffer reuse"):
        first.buffer.as_array()
    assert second.buffer.as_array() == b"bb"
    assert second.buffer.device == "cpu"


def test_pixels_from_decoded_frame_uses_live_buffer_and_rejects_reuse() -> None:
    import numpy as np

    from backend.app.workbench.media import pixels_from_decoded_frame, wrap_decoded_frame
    from dataclasses import replace

    payload = bytes(range(12))
    frame = DecodedFrame(0, 0, 0.0, 2, 2, "bgr", 0, payload, "fixture", image=object())
    live = replace(frame, buffer=wrap_decoded_frame(frame))
    pixels = pixels_from_decoded_frame(live)
    assert isinstance(pixels, np.ndarray)
    assert pixels.shape == (2, 2, 3)
    assert pixels.tobytes() == payload
    live.buffer.release()
    with pytest.raises(RuntimeError, match="use after buffer reuse"):
        pixels_from_decoded_frame(live)


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

        if Path(command[0]).name == "ffmpeg":
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


def test_ffmpeg_export_refuses_unconstrained_network_decoder(tmp_path: Path) -> None:
    from backend.app.workbench.media import FfmpegProbe

    probe = FfmpegProbe()
    with pytest.raises(ValueError, match="unconstrained decoder"):
        probe.export_clip(
            Path("http://evil.test/clip.mp4"),
            tmp_path / "out.mp4",
            start_seconds=0.0,
            duration_seconds=1.0,
            runner=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("ffmpeg must not run")),
        )


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
    from backend.app.workbench.perception import IouAssociationFallback

    adapter = IouAssociationFallback()
    tracks = adapter.associate(detections[:1])
    assert tracks[0]["trackId"].startswith("iou_fallback")
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
    bounded = execute_typed_query([
        {"id": "bounded", "type": "turnover", "team": "my_team", "period": 2,
         "timestamp": 70.2, "frameId": 351, "intervalStart": 70.0, "intervalEnd": 71.0,
         "reviewStatus": "accepted", "evidenceIds": ["event:bounded"]},
    ], parse_typed_query("our second-half turnovers"), match_id="m1")
    assert bounded[0].model_dump(mode="json") == {
        "eventId": "bounded", "matchId": "m1", "timestamp": 70.2, "frameId": 351,
        "intervalStart": 70.0, "intervalEnd": 71.0,
        "reviewStatus": "accepted", "evidenceIds": ["event:bounded"], "label": "turnover",
    }
    refused = parse_typed_query("select * from events; drop table matches")
    assert refused.unanswerable is True
    assert refused.reason == "refused_code_execution"
    unknown = parse_typed_query("how many fouls did the referee invent")
    assert unknown.unanswerable is True
    assert execute_typed_query(events, unknown, match_id="m1") == []
    rejected = [
        {**events[0], "reviewStatus": "rejected"},
        events[1],
        events[2],
    ]
    assert [hit.eventId for hit in execute_typed_query(rejected, query, match_id="m1")] == []
    rejected_successor = [
        events[0],
        {**events[1], "reviewStatus": "rejected"},
        events[2],
    ]
    assert [hit.eventId for hit in execute_typed_query(rejected_successor, query, match_id="m1")] == []


def test_search_does_not_execute_a_broader_fragment_when_terms_are_unsupported() -> None:
    rows = [{"id": "r1", "type": "recovery", "team": "my_team", "timestamp": 3.0}]
    query = parse_typed_query("show our recoveries near the left flank")
    assert query.unanswerable is True
    assert query.reason == "unsupported_terms"
    assert query.unsupportedTerms == ["near", "the", "left", "flank"]
    assert execute_typed_query(rows, query, match_id="m1") == []


def test_natural_and_typed_recovery_filters_return_the_same_evidence() -> None:
    rows = [
        {"id": "wanted", "type": "recovery", "team": "my_team", "timestamp": 12.0,
         "fromTrackId": 7, "reviewStatus": "accepted"},
        {"id": "wrong-player", "type": "recovery", "team": "my_team", "timestamp": 12.0,
         "fromTrackId": 9, "reviewStatus": "accepted"},
        {"id": "unreviewed", "type": "recovery", "team": "my_team", "timestamp": 12.0,
         "fromTrackId": 7, "reviewStatus": "unreviewed"},
        {"id": "outside", "type": "recovery", "team": "my_team", "timestamp": 22.0,
         "fromTrackId": 7, "reviewStatus": "accepted"},
    ]
    direct = TypedQuery(eventFamily="recovery", team="my_team", playerTrackId=7,
        reviewStatus="accepted", timeStartSeconds=10, timeEndSeconds=20)
    natural = parse_typed_query("show our accepted recoveries by player 7 between 10 and 20 seconds")
    assert natural.unanswerable is False
    assert [hit.eventId for hit in execute_typed_query(rows, direct, match_id="m1")] == ["wanted"]
    assert [hit.eventId for hit in execute_typed_query(rows, natural, match_id="m1")] == ["wanted"]


@pytest.mark.parametrize("spoken,kind", [
    ("passes", "pass"), ("progressive passes", "progressive_pass"),
    ("through balls", "through_ball"), ("crosses", "cross"),
    ("shots", "shot"), ("goals", "goal"), ("turnovers", "turnover"),
    ("recoveries", "recovery"), ("tackles", "tackle"),
    ("interceptions", "interception"), ("carries", "carry"),
    ("box entries", "box_entry"), ("final third entries", "final_third_entry"),
])
def test_every_supported_event_family_has_matching_natural_and_typed_evidence(spoken, kind) -> None:
    rows = [{"id": "wanted", "type": kind, "team": "my_team", "fromTrackId": 7, "timestamp": 1.0},
            {"id": "other", "type": kind, "team": "enemy", "fromTrackId": 7, "timestamp": 2.0}]
    natural = parse_typed_query(f"show our {spoken} by player 7")
    direct = TypedQuery(eventFamily=kind, team="my_team", playerTrackId=7)
    assert natural.unanswerable is False
    assert natural.eventFamily == kind
    assert [hit.eventId for hit in execute_typed_query(rows, natural, match_id="m1")] == [
        hit.eventId for hit in execute_typed_query(rows, direct, match_id="m1")] == ["wanted"]


def test_supported_successor_family_keeps_exact_follow_up_scope() -> None:
    query = parse_typed_query("our turnovers followed by opponent tackles within 10 seconds")
    rows = [{"id": "start", "type": "turnover", "team": "my_team", "timestamp": 1.0},
            {"id": "wrong", "type": "tackle", "team": "my_team", "timestamp": 2.0},
            {"id": "wanted", "type": "tackle", "team": "enemy", "timestamp": 4.0}]
    assert query.unanswerable is False
    assert query.successorEvent == "tackle"
    assert [hit.eventId for hit in execute_typed_query(rows, query, match_id="m1")] == ["start"]


def test_calibrated_pitch_third_uses_the_same_typed_executor() -> None:
    rows = [{"id": "right", "type": "recovery", "timestamp": 1.0, "pitchRegion": "right_third"},
            {"id": "left", "type": "recovery", "timestamp": 2.0, "pitchRegion": "left_third"}]
    direct = TypedQuery(eventFamily="recovery", pitchRegion="right_third")
    natural = parse_typed_query("recoveries in the right third")
    assert natural.unanswerable is False
    assert natural.interpreted["pitchRegion"] == "right_third"
    assert [hit.eventId for hit in execute_typed_query(rows, direct, match_id="m1")] == ["right"]
    assert [hit.eventId for hit in execute_typed_query(rows, natural, match_id="m1")] == ["right"]


@pytest.mark.integration
@pytest.mark.real_media
def test_pitch_region_search_requires_measured_calibration_and_reports_missing_actor(tmp_path, monkeypatch) -> None:
    from backend.app.schemas import DetectedEvent
    from backend.app.storage import Storage
    from backend.tests.test_audit_v3_final_journey import _install_video

    storage = Storage(tmp_path / "store")
    match_id = _install_video(storage, tmp_path)
    frame = storage.load_frames(match_id)[0]
    assert any(player.id == 7 and player.x > 67 for player in frame.myTeam)
    storage.save_events(match_id, [
        DetectedEvent(eventId="located", type="recovery", frameId=frame.frameId,
            timestamp=frame.timestamp, fromTrackId=7, team="my_team", description="Located recovery"),
        DetectedEvent(eventId="unknown", type="recovery", frameId=frame.frameId,
            timestamp=frame.timestamp, team="my_team", description="Unknown actor"),
    ])
    located_id = next(event.eventId for event in storage.load_events(match_id)
                      if event.description == "Located recovery")
    result = storage.query_match_events(match_id, "our recoveries in the right third")
    assert [hit["eventId"] for hit in result["results"]] == [located_id]
    assert result["coverageState"] == "partial"
    assert result["unknownLocationCount"] == 1
    monkeypatch.setattr(storage, "_stored_calibration_accepted", lambda _match_id: False)
    withheld = storage.query_match_events(match_id, "our recoveries in the right third")
    assert withheld["results"] == []
    assert withheld["coverageState"] == "insufficient"
    assert withheld["unknownLocationCount"] == 2
    monkeypatch.setattr(storage, "_stored_calibration_accepted", lambda _match_id: True)
    monkeypatch.setattr(storage, "load_frames", lambda _match_id: [frame.model_copy(update={"geometryAvailable": False})])
    frame_unavailable = storage.query_match_events(match_id, "our recoveries in the right third")
    assert frame_unavailable["coverageState"] == "insufficient"
    assert frame_unavailable["unknownLocationCount"] == 2


def test_typed_query_rejects_unsupported_or_invalid_predicates() -> None:
    from pydantic import ValidationError
    from backend.app.workbench.assistance import SuccessorConstraint
    for fields in (
        {"eventFamily": "foul"}, {"eventFamily": "recovery", "period": -1},
        {"eventFamily": "recovery", "playerTrackId": -1},
        {"eventFamily": "recovery", "timeStartSeconds": 20, "timeEndSeconds": 10},
        {"eventFamily": "recovery", "timeStartSeconds": float("nan")},
        {"eventFamily": "recovery", "successor": SuccessorConstraint(kind="sql")},
        {"eventFamily": "recovery", "pitchRegion": "left_flank"},
        {"eventFamily": "recovery", "period": 99},
        {"eventFamily": "recovery", "playerTrackId": 1_000_001},
        {"eventFamily": "recovery", "timeEndSeconds": 86_401},
    ):
        with pytest.raises(ValidationError):
            TypedQuery(**fields)
    invalid_time = parse_typed_query("recoveries between 20 and 10 seconds")
    assert invalid_time.unanswerable is True
    assert invalid_time.reason == "invalid_time_range"
    assert parse_typed_query("period 99 recoveries").reason == "invalid_period"
    assert parse_typed_query("recoveries by player 1000001").reason == "invalid_player"
    assert parse_typed_query("recoveries between 0 and 86401 seconds").reason == "invalid_time_range"
    assert parse_typed_query("x" * 513).reason == "query_too_long"


def test_model_query_proposal_is_scope_bound_and_uses_existing_python_search() -> None:
    proposal = {"matchId": "m1", "generationId": "g1", "query": {
        "eventFamily": "recovery", "team": "my_team", "playerTrackId": 7}}
    query = validate_query_proposal(proposal, match_id="m1", generation_id="g1")
    assert validate_query_proposal(
        {**proposal, "query": {**proposal["query"], "pitchRegion": "right_third"}},
        match_id="m1", generation_id="g1",
    ).pitchRegion == "right_third"
    rows = [
        {"id": "wanted", "type": "recovery", "team": "my_team", "fromTrackId": 7, "timestamp": 1.0},
        {"id": "other", "type": "recovery", "team": "my_team", "fromTrackId": 8, "timestamp": 2.0},
    ]
    assert [hit.eventId for hit in execute_typed_query(rows, query, match_id="m1")] == ["wanted"]
    for invalid in (
        {**proposal, "generationId": "g0"},
        {**proposal, "matchId": "m2"},
        {**proposal, "sql": "SELECT * FROM events"},
        {**proposal, "query": {"eventFamily": "recovery", "pitchRegion": "left"}},
        {**proposal, "query": {"eventFamily": "recovery", "includeUnknown": True}},
        {**proposal, "query": {"eventFamily": "recovery", "unanswerable": False}},
        {**proposal, "query": {"eventFamily": "recovery", "period": 99}},
    ):
        with pytest.raises(ValueError):
            validate_query_proposal(invalid, match_id="m1", generation_id="g1")


def test_query_result_distinguishes_no_match_from_missing_event_coverage(tmp_path, monkeypatch) -> None:
    from backend.app.storage import Storage
    storage = Storage(tmp_path / "store")
    source = tmp_path / "empty.json"
    source.write_text("[]")
    match = storage.create_match("empty", "tracking_json", source.name, source, MatchConfig())
    monkeypatch.setattr(storage, "load_events", lambda *_: [])
    assert storage.query_match_events(match.id, "recoveries")["coverageState"] == "no_match"
    def missing(*_):
        raise FileNotFoundError
    monkeypatch.setattr(storage, "load_events", missing)
    assert storage.query_match_events(match.id, "recoveries")["coverageState"] == "insufficient"


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
    unknown = ledger.timeout_before_response("req-1", owner_id="legacy")
    assert unknown.status == "outcome_unknown"
    with pytest.raises(RuntimeError, match="reconcile"):
        ledger.retry("req-1")
    ledger.reconcile_attempt(
        unknown.attemptId,
        provider_outcome="not_found",
        settled_cost=0.0,
    )
    second = ledger.retry("req-1")
    assert second.attemptId != first.attemptId
    ledger.cancel("req-1")
    assert ledger.receipt("req-1").status == "cancelling"
    assert ledger.invalidate_for("calibration") == ["pitch_positions", "physical_metrics", "tactical_metrics", "report"]
    failed_cleanup = ledger.confirm_cleanup(
        "req-1", owner_id=f"job:{request.requestId}", ok=False
    )
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
        owner_id="legacy",
        sha256="deadbeef",
        expected_sha256="cafebabe",
        schema_ok=True,
        complete=False,
    )
    assert quarantined.status == "failed"
    assert quarantined.error == "quarantined_partial_or_corrupt"
    attempt = ledger.retry("req-q")
    ledger.transition(
        attempt.attemptId,
        expected_revision=attempt.revision,
        owner_id=f"job:{request.requestId}",
        status="failed",
        error="reconciled",
    )
    attempt = ledger.retry("req-q")
    ledger.transition(
        attempt.attemptId,
        expected_revision=attempt.revision,
        owner_id=f"job:{request.requestId}",
        status="failed",
        error="reconciled",
    )
    with pytest.raises(RuntimeError, match="retry budget"):
        ledger.retry("req-q")
    exhausted = ledger.disk_exhaustion("req-q", owner_id=f"job:{request.requestId}")
    assert exhausted.error == "disk_exhaustion"
    assert exhausted.status == "failed"


def test_evaluation_gate_fails_closed_without_independent_labels() -> None:
    current = current_repository_evaluation_gate()
    assert current.status == "unknown"
    assert current.completeTasks is None
    assert current.requiredTasks == FROZEN_TASK_COUNT
    assert current.accepted is False
    assert current.reasonCodes == ["EVALUATION_MANIFEST_MISSING"]
    passing = evaluate_protocol_prerequisites(
        complete_tasks=18,
        complete_minutes=30.0,
        locked_labels_present=True,
        native_predictions_present=True,
        team_declarations_present=True,
        scorer_replayable=True,
    )
    assert passing.accepted is False
    assert passing.status == "prerequisites_ok"


def test_ground_contact_is_not_box_centre_and_aerial_ball_is_not_on_the_pitch() -> None:
    from backend.app.workbench.geometry import ground_contact_point, project_to_pitch

    contact = ground_contact_point((10.0, 20.0, 30.0, 80.0))
    assert contact["boxCentreIsFoot"] is False
    assert contact["imageX"] == 20.0
    assert contact["imageY"] == 80.0
    aerial = project_to_pitch(kind="ball", airborne=True, bbox=(10.0, 20.0, 30.0, 80.0))
    assert aerial["measuredGroundLocation"] is False
    assert "AERIAL_NOT_GROUND_PLANE" in aerial["reasonCodes"]
    player = project_to_pitch(kind="player", airborne=False, bbox=(10.0, 20.0, 30.0, 80.0))
    assert player["boxCentreIsFoot"] is False
    assert player["imageY"] == 80.0


def test_vid_stride_is_not_added_alone_and_target_fps_is_not_inference_fps() -> None:
    from backend.app.workbench.media import vid_stride_policy

    policy = vid_stride_policy()
    assert policy["addsVidStrideAlone"] is False
    assert policy["targetFpsEqualsInferenceFps"] is False
    assert policy["explicitFrameContractRequired"] is True
    assert policy["oldEvidenceCompatible"] is True


def test_identity_resets_across_a_camera_cut_instead_of_silently_reconnecting() -> None:
    from backend.app.workbench.identity import reconnect_across_cut

    reset = reconnect_across_cut(cut_detected=True)
    assert reset["reset"] is True
    assert reset["silentlyReconnected"] is False
    assert "CAMERA_CUT" in reset["reasonCodes"]
    continuous = reconnect_across_cut(cut_detected=False)
    assert continuous["reset"] is False
    assert continuous["silentlyReconnected"] is False


def test_cuda_visibility_is_not_video_engine_capability() -> None:
    from backend.app.workbench.native import cuda_visibility_is_not_video_capability

    probe = cuda_visibility_is_not_video_capability(cuda_visible=True)
    assert probe["cudaVisible"] is True
    assert probe["videoEngineCapability"] is False
    assert probe["nvencRequiredForDecodeOnly"] is False
    assert probe["daytonaVideoEngineVerified"] is False
    assert "CUDA_VISIBILITY_IS_NOT_VIDEO_CAPABILITY" in probe["reasonCodes"]


def test_appearance_embeddings_are_selective_and_tracklets_are_not_forced_into_players() -> None:
    from backend.app.workbench.identity import (
        appearance_embedding_policy,
        assign_tracklet,
        candidate_rejoin,
        tracker_chunk,
    )

    policy = appearance_embedding_policy()
    assert policy["everyDetection"] is False
    assert policy["afterOcclusion"] is True
    assert policy["afterRejoin"] is True
    assert policy["cameraCutDefeatsAppearance"] is True
    unreviewed = assign_tracklet(roster_id="shirt-9", reviewed=False)
    assert unreviewed["kind"] == "tracklet"
    assert unreviewed["forced"] is False
    assert unreviewed["rosterId"] is None
    rejoin = candidate_rejoin()
    assert rejoin["preserveCompetingHypotheses"] is True
    assert rejoin["autoAccepted"] is False
    cut = tracker_chunk(scene_discontinuity=True, broadcast_replay=False)
    assert cut["reset"] is True
    assert cut["silentlyReconnected"] is False
    replay = tracker_chunk(scene_discontinuity=False, broadcast_replay=True)
    assert replay["reset"] is True
    assert replay["silentlyReconnected"] is False
    overlap = tracker_chunk(scene_discontinuity=False, broadcast_replay=False)
    assert overlap["carryForwardBoundedState"] is True
    assert overlap["silentlyReconnected"] is False


def test_derived_distance_does_not_bridge_camera_cuts_or_identity_gaps() -> None:
    from backend.app.workbench.geometry import derived_distance

    bridged = derived_distance(delta_m=12.0, uncertainty_m=0.4, cut_bridged=True, identity_gap=False)
    assert bridged["availability"] == "withheld"
    assert bridged["value"] is None
    assert "CAMERA_CUT" in bridged["reasonCodes"]
    gap = derived_distance(delta_m=12.0, uncertainty_m=0.4, cut_bridged=False, identity_gap=True)
    assert gap["availability"] == "withheld"
    assert gap["value"] is None
    assert "IDENTITY_DISCONTINUITY" in gap["reasonCodes"]
    missing = derived_distance(
        delta_m=12.0,
        uncertainty_m=0.4,
        cut_bridged=False,
        identity_gap=False,
        calibration_missing=True,
    )
    assert missing["availability"] == "withheld"
    assert missing["value"] is None
    assert "CALIBRATION_UNAVAILABLE" in missing["reasonCodes"]
    assert "IDENTITY_DISCONTINUITY" not in missing["reasonCodes"]
    ok = derived_distance(delta_m=12.0, uncertainty_m=0.4, cut_bridged=False, identity_gap=False)
    assert ok["availability"] == "available"
    assert ok["value"] == 12.0
    assert ok["uncertaintyM"] == 0.4
    assert ok["bridged"] is False


def test_shadowed_metrics_stay_off_defaults_and_new_artifacts_are_written_alongside(tmp_path: Path) -> None:
    from backend.app.workbench.artifacts import ArtifactStore, write_alongside
    from backend.app.workbench.flags import shadow_metric

    shadowed = shadow_metric("experimental_shot_quality")
    assert shadowed["default"] is False
    assert shadowed["shadowed"] is True
    assert shadowed["published"] is False
    store = ArtifactStore(tmp_path / "cas")
    previous = store.put(b"report-v1", namespace="reports")
    published = write_alongside(store, previous_digest=previous, payload=b"report-v2", namespace="reports")
    assert published["mutatedHistorical"] is False
    assert published["previousDigest"] == previous
    assert published["digest"] != previous
    assert store.get(previous, namespace="reports") == b"report-v1"
    assert store.get(published["digest"], namespace="reports") == b"report-v2"


def test_shot_tree_challenger_and_learned_temporal_stay_gated_until_justified() -> None:
    from backend.app.workbench.events import learned_temporal
    from backend.app.workbench.shot_model import missing_shot_features, tree_challenger

    missing = missing_shot_features({"y": 50.0})
    assert missing["recorded"] is True
    assert "x" in missing["missing"]
    assert missing["imputedAsCalibrated"] is False
    tree = tree_challenger(logistic_calibrated=False)
    assert tree["enabled"] is False
    assert tree["comparedAfterLogisticBaseline"] is True
    temporal = learned_temporal(labelled_errors_justify=False)
    assert temporal["enabled"] is False
    assert temporal["replacesStateMachine"] is False


def test_network_failure_preserves_unknown_metrics_and_budget_variance_alerts() -> None:
    from backend.app.workbench.assistance import network_failure_preserves_unknown
    from backend.app.workbench.costs import reconcile_spend, reserve_budget
    from backend.app.workbench.quantities import transform_legacy_display

    preserved = network_failure_preserves_unknown(metric_value=None, generated_number=4.2)
    assert preserved["value"] is None
    assert preserved["availability"] == "unknown"
    assert preserved["replacedWithGenerated"] is False
    reserved = reserve_budget(estimate=10.0, conservative_factor=1.5)
    assert reserved["reserved"] == 15.0
    assert reserved["authorised"] is False
    variance = reconcile_spend(reserved=15.0, actual=22.0)
    assert variance["alert"] is True
    assert variance["exceeded"] is True
    display = transform_legacy_display(x=10.0, y=20.0, from_display=True)
    assert display["xAxis"] == "longitudinal"
    assert display["yAxis"] == "lateral"
    assert display["transformedExplicitly"] is True


def test_tracker_resets_across_cuts_and_identity_repairs_preview_before_commit() -> None:
    from backend.app.workbench.perception import Detection, IdentityRepair, IouAssociationFallback, preview_identity_change

    detections = [
        Detection(frameId=0, bbox=(10.0, 20.0, 30.0, 80.0), score=0.9, kind="player", stratum="near"),
        Detection(frameId=1, bbox=(12.0, 20.0, 32.0, 80.0), score=0.9, kind="player", stratum="near"),
    ]
    adapter = IouAssociationFallback()
    continuous = adapter.associate(detections, cut_detected=False)
    assert all(track["silentlyReconnected"] is False for track in continuous)
    cut = adapter.associate(detections, cut_detected=True, previous_tracks=continuous)
    assert all(track["reset"] is True for track in cut)
    assert all(track["silentlyReconnected"] is False for track in cut)
    replay = adapter.associate(detections, broadcast_replay=True, previous_tracks=continuous)
    assert all(track["reset"] is True for track in replay)
    preview = preview_identity_change(kind="track_split", track_id="t-1", at_frame=4)
    assert preview["preview"] is True
    assert preview["committed"] is False
    assert preview["affectedIntervals"]
    assert "player_events" in preview["invalidates"]
    repair = IdentityRepair()
    split = repair.split("t-1", 4, author="analyst")
    assert split["kind"] == "track_split"
    team = preview_identity_change(kind="team_mapping", interval_start=12.0, interval_end=40.0)
    assert team["visionRerun"] is False
    assert team["newMappingShown"] is True


def test_track_split_renames_stored_tracklets_from_the_cut_frame() -> None:
    from backend.app.schemas import FrameData, PlayerData
    from backend.app.workbench.identity import apply_track_split, next_available_track_id

    frames = [
        FrameData(frameId=0, timestamp=0.0, myTeam=[PlayerData(id=7, x=21.0, y=50.0)]),
        FrameData(frameId=1, timestamp=0.2, myTeam=[PlayerData(id=7, x=23.0, y=50.0)]),
        FrameData(frameId=2, timestamp=0.4, myTeam=[PlayerData(id=7, x=26.0, y=50.0)]),
    ]
    new_id = next_available_track_id(frames)
    split = apply_track_split(frames, track_id="7", at_frame=1, new_track_id=new_id)
    assert [player.id for player in split[0].myTeam] == [7]
    assert [player.id for player in split[1].myTeam] == [new_id]
    assert [player.id for player in split[2].myTeam] == [new_id]
    assert frames[1].myTeam[0].id == 7


def test_evaluation_measures_require_compatible_labels_and_do_not_treat_health_as_the_label_gate() -> None:
    from backend.app.workbench.evaluation import evaluation_measures

    measures = evaluation_measures()
    assert measures["hotaIdf1RequiresCompatibleImageSpaceLabels"] is True
    assert measures["officialPitchPositionsAreNotHotaLabels"] is True
    assert measures["trackevalIsGroundTruth"] is False
    assert measures["annotationServiceHealthSatisfiesLabelGate"] is False
    assert measures["pooledAverageOnly"] is False
    assert measures["handEditedSummaryIsResult"] is False


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
    assert review["availability"] == "unknown"
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


def test_query_match_evidence_pages_interval_with_coordinate_version() -> None:
    from backend.app.schemas import BallData, DetectedEvent, FrameData, PlayerData
    from backend.app.workbench.evidence import query_match_evidence

    frames = [
        FrameData(
            frameId=0,
            timestamp=0.0,
            ball=BallData(x=10, y=20, confidence=0.9),
            myTeam=[PlayerData(id=7, x=8, y=20, confidence=0.9)],
        ),
        FrameData(frameId=1, timestamp=0.2, ball=BallData(x=12, y=20, confidence=0.9)),
        FrameData(frameId=2, timestamp=1.0),
    ]
    events = [
        DetectedEvent(type="pass", frameId=1, timestamp=0.2, team="my_team", description="Pass completed"),
    ]
    page = query_match_evidence(frames, events, interval_start=0.0, interval_end=0.5, limit=10)
    assert page.intervalEndpoint == "half_open"
    assert page.coordinateSpace == "pitch"
    assert page.definitionVersion == "1"
    kinds = {item.payload.get("kind") for item in page.items}
    assert kinds == {"frame", "event"}
    assert all(item.schemaVersion == "evidence_v1" for item in page.items)
    assert all(item.payload.get("coordinateSpace") == "pitch" for item in page.items)
    assert all(item.intervalStart < 0.5 and item.intervalEnd > 0.0 for item in page.items)
    bounded = query_match_evidence(frames, events, interval_start=0.0, interval_end=2.0, limit=2)
    assert len(bounded.items) == 2
    assert bounded.nextCursor is not None
    nxt = query_match_evidence(frames, events, interval_start=0.0, interval_end=2.0, cursor=bounded.nextCursor, limit=10)
    assert nxt.items
    assert nxt.items[0].evidenceId == bounded.nextCursor
    outside = query_match_evidence(frames, events, interval_start=5.0, interval_end=6.0, limit=10)
    assert outside.items == []


def test_feature_flags_keep_experimental_metrics_and_native_code_shadowed() -> None:
    from backend.app.workbench.flags import feature_enabled

    assert feature_enabled("experimental_shot_quality", env={}) is False
    assert feature_enabled("gpu_default", env={}) is False
    assert feature_enabled("native_code", env={}) is False
    assert feature_enabled("experimental_ui", env={}) is False
    assert feature_enabled("embeddings_search", env={}) is False
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
    assert package["operator"]["secretsAdmitted"] is False
    assert "SECRET_IN_ARTIFACT" in package["operator"]["reasonCodes"]


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

    uncertain = AssistanceRouter(providers_enabled=True, provider=lambda **kwargs: {"ok": True}).run(
        policy=AssistancePolicy(taskType="report", spendCap=1.0, allowedModelIds=["frontier-1"], cloudPermitted=True),
        metrics=metrics,
        events=[],
        model_uncertain=True,
        measured_quality_gap=False,
    )
    assert uncertain.route != "cloud"
    assert "ESCALATION_REQUIRES_MEASURED_QUALITY_GAP" in uncertain.reasonCodes


def test_extraction_boundaries_exist_and_native_directory_stays_absent() -> None:
    import backend.evaluation as evaluation_pkg
    import backend.media as media_pkg
    import backend.vision as vision_pkg
    from backend.app.workbench.native import native_gate

    repo = Path(__file__).resolve().parents[2]
    assert media_pkg.FrameSource is not None
    assert vision_pkg.TrackerAdapter is not None
    assert vision_pkg.DetectorAdapter is not None
    assert vision_pkg.PreprocessPlan is not None
    assert vision_pkg.ground_contact_point((10.0, 20.0, 30.0, 80.0))["boxCentreIsFoot"] is False
    assert evaluation_pkg.current_repository_evaluation_gate().accepted is False
    assert not (repo / "native").exists()
    gate = native_gate(repo_root=repo, approval_env={})
    assert gate.approved is False
    assert "NATIVE_GATE_CLOSED" in gate.reasonCodes


def test_model_roster_keeps_every_upgrade_unpromoted() -> None:
    from backend.app.workbench.roster import model_roster, promotion_gate

    roster = model_roster()
    tasks = {item["task"] for item in roster}
    assert "geometry_metrics" in tasks
    assert "shot_probability" in tasks
    assert all(item["promoted"] is False for item in roster)
    gate = promotion_gate(task="player_ball", independent_accepted=False, licence_recorded=True)
    assert gate["promoted"] is False
    assert "INDEPENDENT_ACCEPTANCE_MISSING" in gate["reasonCodes"]


def test_report_assembly_rejects_fabricated_evidence_and_invented_numbers() -> None:
    from backend.app.workbench.reports import assemble_report

    metrics = [{"metric": "possession_pct", "availability": "unknown", "value": None}]
    rejected = assemble_report(
        metrics=metrics,
        events=[{"eventId": "e1", "evidenceIds": ["ev-1"]}],
        claimed_evidence_ids=["missing"],
        known_evidence_ids={"ev-1"},
    )
    assert rejected["publication"]["accepted"] is False
    assert "FABRICATED_EVIDENCE" in rejected["factualCheck"]["reasonCodes"]
    invented = assemble_report(
        metrics=metrics,
        events=[],
        claimed_evidence_ids=[],
        known_evidence_ids=set(),
        narrative={"possession_pct": 61, "text": "possession was 61"},
    )
    assert invented["factualCheck"]["accepted"] is False
    assert "INVENTED_NUMBER" in invented["factualCheck"]["reasonCodes"]
    ok = assemble_report(
        metrics=metrics,
        events=[{"eventId": "e1", "evidenceIds": ["ev-1"]}],
        claimed_evidence_ids=["ev-1"],
        known_evidence_ids={"ev-1"},
    )
    assert ok["evidenceSelection"]["evidenceIds"] == ["ev-1"]
    assert ok["factPackage"]["metrics"] == metrics
    assert ok["narrativeDraft"]["optional"] is True
    assert ok["publication"]["wholeMatchFrequency"] is False
    assert ok["publication"]["frequencyRequiresDenominator"] is True


def test_locked_evaluation_labels_cannot_enter_training() -> None:
    from backend.app.workbench.training import admit_example, data_pools

    assert data_pools() == (
        "operational_corrections",
        "training",
        "development_validation",
        "locked_evaluation",
    )
    blocked = admit_example(
        {"id": "lab-1", "rights": "granted"},
        source_pool="locked_evaluation",
        destination="training",
    )
    assert blocked.admitted is False
    assert "LOCKED_EVALUATION_ISOLATION" in blocked.reasonCodes
    allowed = admit_example(
        {"id": "corr-1", "rights": "granted", "quality": "reviewed"},
        source_pool="operational_corrections",
        destination="training",
    )
    assert allowed.admitted is True


def test_experiment_cycle_isolates_pools_and_rejects_pseudo_labels_as_truth() -> None:
    from backend.app.workbench.training import (
        drill_library,
        experiment_cycle,
        experiment_ledger,
        promote_candidate,
        pseudo_label,
        sampling_policy,
    )

    diagnose = experiment_cycle("diagnose", measurable_failure=False)
    assert diagnose["proceed"] is False
    train = experiment_cycle("train", budget_remaining=0.0, development_benefit=False)
    assert train["proceed"] is False
    label = pseudo_label(suggestion="player", human_change=None, approved=False)
    assert label["independentGroundTruth"] is False
    ledger = experiment_ledger()
    first = ledger.append({"run": "exp-1", "config": "baseline"})
    second = ledger.append({"run": "exp-2", "config": "candidate"})
    assert [item["run"] for item in ledger.entries] == ["exp-1", "exp-2"]
    assert first != second
    policy = sampling_policy()
    assert policy["uncertaintyOnly"] is False
    assert "random_representative" in policy["mix"]
    drills = drill_library()
    assert drills["prescribesMedicalLoad"] is False
    assert drills["diagnosesFatigueOrInjury"] is False
    promotion = promote_candidate(independent_accepted=False, rollback_artifact=True)
    assert promotion["promoted"] is False


def test_coverage_aware_selector_and_held_out_questions_include_unanswerable() -> None:
    from backend.app.workbench.reports import coverage_aware_selector, held_out_questions

    selected = coverage_aware_selector(
        frames=[{"t": 1.0}, {"t": 45.0}, {"t": 89.0}],
        events=[{"id": "e1", "t": 12.0, "evidenceIds": ["ev-1"]}],
        max_frames=2,
    )
    assert selected["representsWholeMatch"] is False
    assert selected["coverageAware"] is True
    questions = held_out_questions()
    assert any(item["unanswerable"] for item in questions)
    assert all("expectedFilter" in item for item in questions)


def test_milestones_are_planning_estimates_and_progress_counts_gates_not_files() -> None:
    from backend.app.workbench.milestones import milestone_plan, owners, progress_signal

    plan = milestone_plan()
    ids = [item["id"] for item in plan]
    assert ids == ["M0", "M1", "M2", "M3", "M4", "M5"]
    m1 = next(item for item in plan if item["id"] == "M1")
    assert m1["analystAccepted"] is False
    assert m1["llmRequired"] is False
    assert plan[0]["planningEstimateNotCommitment"] is True
    named = owners()
    assert set(named) >= {"backend_media", "frontend", "cv", "independent_evaluation", "operations"}
    signal = progress_signal(completed_analyst_tasks=0, validated_capability_gates=0, merged_files=400)
    assert signal["complete"] is False
    assert signal["usesMergedFilesAsSuccess"] is False


def test_detected_event_carries_evidence_version_and_half_open_interval() -> None:
    from backend.app.schemas import DetectedEvent

    event = DetectedEvent(
        type="shot",
        frameId=12,
        timestamp=12.4,
        description="provisional shot",
        evidenceVersion="evidence_v1",
        intervalStart=12.0,
        intervalEnd=13.0,
    )
    dumped = event.model_dump()
    assert dumped["reviewStatus"] == "unreviewed"
    assert dumped["evidenceVersion"] == "evidence_v1"
    assert dumped["intervalStart"] == 12.0
    assert dumped["intervalEnd"] == 13.0


def test_metadata_api_p95_is_a_planning_target_not_a_measurement() -> None:
    from backend.app.workbench.targets import metadata_api_targets

    target = metadata_api_targets()
    assert target["p95MetadataApiReadMs"] == 500
    assert target["measured"] is False
    assert target["planningTargetNotMeasurement"] is True
    assert target["doesNotPromiseVideoDecodeLatency"] is True
    assert target["timelineLoadsAllFrameRecords"] is False


def test_selective_recompute_reuses_identical_cache_identity() -> None:
    from backend.app.workbench.cache import cache_identity, recompute_plan

    identity = cache_identity(
        source_sha256="a" * 64,
        interval_start=0.0,
        interval_end=10.0,
        decoder_version="opencv",
        model_hash="weights-v1",
        temporal_policy="clip_local_index_modulo",
        output_schema="evidence_v1",
    )
    reused = recompute_plan(previous_identity=identity, current_identity=identity, change="calibration")
    assert reused["reuse"] is True
    assert reused["rebuild"] == []
    rebuilt = recompute_plan(previous_identity=None, current_identity=identity, change="calibration")
    assert rebuilt["reuse"] is False
    assert "pitch_positions" in rebuilt["rebuild"]


def test_match_cost_includes_review_labour_and_does_not_use_export_fps() -> None:
    from backend.app.workbench.costs import historical_capacity_seconds, match_cost

    cost = match_cost(
        allocated_compute=2.0,
        retained_storage=0.2,
        transfer=0.1,
        model_api=0.04,
        retry_overhead=0.0,
        review_labour=10.0,
        fixed_share=5.0,
        export_fps=5.0,
        inference_fps=None,
    )
    assert cost.total == 17.34
    assert cost.exportFpsEqualsInferenceFps is False
    assert cost.rateCardDate
    historical = historical_capacity_seconds()
    assert historical["seconds"] == 16523.971
    assert historical["billableCurrentSource"] is False


def test_score_quantities_and_pitch_axes_stay_distinct() -> None:
    from backend.app.workbench.quantities import attack_direction_for, pitch_axes, split_scores

    axes = pitch_axes()
    assert axes["x"] == "longitudinal"
    assert axes["y"] == "lateral"
    scores = split_scores(detector_score=0.81, calibrated_probability=0.22, interval=(0.1, 0.4))
    assert "confidence" not in scores
    assert scores["detectorScore"] == 0.81
    assert scores["calibratedProbability"] == 0.22
    assert attack_direction_for(team="my_team", period=1, mapping={( "my_team", 1): "left_to_right"}) == "left_to_right"


def test_level0_incident_package_has_no_offside_decision() -> None:
    from backend.app.workbench.incidents import level0_incident_package

    package = level0_incident_package(
        clips=[{"start": 12.0, "end": 14.0, "source": "asset-A"}],
        notes=["near-side defender advanced"],
        bookmarks=[12.4],
    )
    assert package["level"] == 0
    assert package["decision"] is None
    assert package["validatedMeasurement"] is False
    assert "IFAB_LAW_11_NOT_APPLIED" in package["reasonCodes"]


def test_dpia_blocks_cloud_for_youth_or_missing_permission() -> None:
    from backend.app.workbench.privacy import dpia_screen

    blocked = dpia_screen(youth_footage=True, identifiable_faces=True, cloud_requested=True, cloud_permitted=False)
    assert blocked.cloudAllowed is False
    assert "YOUTH_FOOTAGE" in blocked.reasonCodes
    local = dpia_screen(youth_footage=False, identifiable_faces=True, cloud_requested=False, cloud_permitted=False)
    assert local.cloudAllowed is False
    assert local.localProcessingRequired is True


def test_sample_decode_anchors_cover_beginning_middle_and_end() -> None:
    from backend.app.workbench.media import sample_decode_anchors

    frames = [
        DecodedFrame(0, 0, 0.0, 2, 2, "bgr", 0, b"a", "opencv"),
        DecodedFrame(1, 1, 0.04, 2, 2, "bgr", 0, b"b", "opencv"),
        DecodedFrame(2, 2, 0.08, 2, 2, "bgr", 0, b"c", "opencv"),
        DecodedFrame(3, 50, 2.0, 2, 2, "bgr", 0, b"d", "opencv"),
    ]
    anchors = sample_decode_anchors(frames)
    assert anchors["beginning"] == 0.0
    assert anchors["middle"] == 0.08
    assert anchors["end"] == 2.0
    assert anchors["discontinuities"]


def test_camera_admission_withholds_physical_metrics_for_handheld() -> None:
    from backend.app.workbench.admission import admit_camera

    handheld = admit_camera("handheld_low_angle")
    assert handheld.automation == "manual_tagging"
    assert "physical_metrics" in handheld.withhold
    broadcast = admit_camera("broadcast_cuts_zoom")
    assert "distance_totals" in broadcast.withhold
    pan = admit_camera("stitched_panoramic_view")
    assert pan.certified is False


def test_stage_timing_does_not_add_overlapped_stages() -> None:
    from backend.app.workbench.timing import stage_timing

    receipt = stage_timing(
        decode=10.0,
        preprocess=4.0,
        transfer=2.0,
        inference=20.0,
        association=3.0,
        recovery=1.0,
        serialisation=1.0,
        wall_time=28.0,
        overlapped=True,
    )
    assert receipt.wallTime == 28.0
    assert receipt.stageSum == 41.0
    assert receipt.overlappedStagesAreAdditive is False


def test_retention_does_not_delete_frozen_evaluation_or_originals() -> None:
    from backend.app.workbench.retention import may_delete

    assert may_delete("frozen_evaluation", authorised_policy=False) is False
    assert may_delete("user_owned_original_media", authorised_policy=False) is False
    assert may_delete("working_cache", authorised_policy=True) is True
    assert may_delete("frozen_evaluation", authorised_policy=True) is False


def test_cluster_ids_are_suggestions_not_home_away_labels() -> None:
    from backend.app.workbench.identity import cluster_mapping

    suggestion = cluster_mapping(cluster_id=2, selected_semantic=None)
    assert suggestion.semanticTeam is None
    assert suggestion.suggestion is True
    confirmed = cluster_mapping(cluster_id=2, selected_semantic="my_team")
    assert confirmed.semanticTeam == "my_team"
    assert confirmed.suggestion is False


def test_formation_is_withheld_for_a_single_frame() -> None:
    from backend.app.workbench.quantities import formation_availability

    withheld = formation_availability(eligible_windows=1, role_context=False)
    assert withheld["availability"] == "withheld"
    assert "SINGLE_FRAME_FORMATION" in withheld["reasonCodes"]


def test_stale_correction_version_is_conflicted_not_silently_replaced() -> None:
    log = CorrectionLog()
    first = log.submit(new_correction("m1", "team_mapping", {"cluster": 1}))
    assert first.saveState == "saved"
    stale = log.submit(new_correction("m1", "team_mapping", {"cluster": 2}), expected_version=0)
    assert stale.saveState == "conflicted"
    fresh = log.submit(new_correction("m1", "team_mapping", {"cluster": 2}), expected_version=first.version)
    assert fresh.saveState == "saved"
    assert fresh.version == first.version + 1


def test_credit_envelope_is_illustrative_and_not_an_authorisation() -> None:
    from backend.app.workbench.costs import credit_allocation

    envelope = credit_allocation()
    assert envelope["illustrativeUsd"] == 1200
    assert envelope["authorised"] is False
    assert envelope["accountBalance"] is None
    assert envelope["gpuCreditsDoNotPayForLabels"] is True


def test_player_observations_stay_interval_limited_without_identity_continuity() -> None:
    from backend.app.workbench.identity import player_observations

    rows = player_observations(
        [{"trackId": "t-4", "t": 1.0}, {"trackId": "t-4", "t": 40.0}],
        identity_continuous=False,
    )
    assert rows["intervalLimited"] is True
    assert rows["totalsWithheld"] is True
    assert "IDENTITY_DISCONTINUITY" in rows["reasonCodes"]


def test_derived_proxy_assets_keep_the_original_and_map_presentation_time(tmp_path: Path) -> None:
    from backend.app.workbench.media import derive_proxy_assets, map_original_to_proxy_pts, resolve_declared_interval

    original = tmp_path / "match.bin"
    original.write_bytes(b"immutable-original")
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    derived = derive_proxy_assets(
        original,
        original_sha256=digest,
        original_pts=[0, 3000, 6000],
        time_base=(1, 90000),
        proxy_height=720,
    )
    assert derived["replacesOriginal"] is False
    assert derived["originalRetained"] is True
    assert derived["originalSha256"] == digest
    assert original.read_bytes() == b"immutable-original"
    assert set(derived["assets"]) == {"proxy", "thumbnails", "waveform"}
    assert derived["assets"]["proxy"]["height"] == 720
    mapping = map_original_to_proxy_pts(
        original_pts=[0, 3000, 6000],
        proxy_pts=[0, 3000, 6000],
        time_base=(1, 90000),
    )
    assert mapping[1]["originalSeconds"] == mapping[1]["proxySeconds"]
    assert mapping[1]["originalPts"] == 3000
    original_interval = resolve_declared_interval("original", 0.0, 1.0, mapping)
    proxy_interval = resolve_declared_interval("proxy", 0.0, 1.0, mapping)
    export_interval = resolve_declared_interval("export", 0.0, 1.0, mapping)
    assert original_interval == proxy_interval == export_interval == (0.0, 1.0)
    assert derived["frameExactExport"]["validatedDecodeReencode"] is True
    assert derived["frameExactExport"]["keyframeSeekIsExact"] is False


def test_admit_media_rejects_unsafe_unsupported_duplicate_interrupted_and_missing_audio() -> None:
    from backend.app.workbench.admission import admit_media
    from backend.app.workbench.contracts import SourceClockIdentity

    supported = SourceClockIdentity(
        sourceSha256="a" * 64,
        byteSize=1024,
        codec="h264",
        audioTracks=1,
    )
    ok = admit_media(supported, existing_digests=set())
    assert ok["admitted"] is True
    assert ok["reasonCodes"] == []

    unsafe = supported.model_copy(update={"decodeErrors": ["unsafe_container"]})
    assert admit_media(unsafe)["admitted"] is False
    assert "UNSAFE_MEDIA" in admit_media(unsafe)["reasonCodes"]

    unsupported = supported.model_copy(update={"codec": "unknown_codec"})
    assert admit_media(unsupported)["admitted"] is False
    assert "UNSUPPORTED_CODEC" in admit_media(unsupported)["reasonCodes"]

    duplicate = admit_media(supported, existing_digests={"a" * 64})
    assert duplicate["admitted"] is False
    assert "DUPLICATE_CONTENT" in duplicate["reasonCodes"]

    interrupted = supported.model_copy(update={"decodeErrors": ["truncated_file"]})
    assert admit_media(interrupted)["admitted"] is False
    assert "INTERRUPTED_FILE" in admit_media(interrupted)["reasonCodes"]

    silent = supported.model_copy(update={"audioTracks": 0})
    missing = admit_media(silent, require_audio=True)
    assert missing["admitted"] is False
    assert "MISSING_AUDIO" in missing["reasonCodes"]
    video_only = admit_media(silent, require_audio=False)
    assert video_only["admitted"] is True
    assert "MISSING_AUDIO" in video_only["warnings"]

    vfr = supported.model_copy(update={"variableFrameRate": True, "rotation": 90})
    rotated = admit_media(vfr)
    assert rotated["admitted"] is True
    assert rotated["variableFrameRate"] is True
    assert rotated["rotation"] == 90
    remote = admit_media(supported, source_url="https://example.com/footage.mp4")
    assert remote["admitted"] is False
    assert "PROTOCOL_OR_NETWORK_NOT_ALLOWLISTED" in remote["reasonCodes"]
    local = admit_media(supported, source_url="file:///tmp/match.mp4")
    assert local["admitted"] is True


def test_pyav_and_torchcodec_stubs_are_challengers_not_defaults(tmp_path: Path) -> None:
    from backend.app.workbench.media import (
        OpenCvFrameSource,
        PyAvFrameSource,
        TorchCodecFrameSource,
        iter_bgr_frames,
    )

    source = tmp_path / "clip.bin"
    source.write_bytes(b"src")
    pyav = PyAvFrameSource()
    torchcodec = TorchCodecFrameSource()
    assert pyav.name == "pyav"
    assert torchcodec.name == "torchcodec"
    with pytest.raises(RuntimeError, match="not a default decoder"):
        list(pyav.iter_frames(source))
    with pytest.raises(RuntimeError, match="not a default decoder"):
        list(torchcodec.iter_frames(source))
    with pytest.raises(RuntimeError, match="challenger"):
        pyav.probe(source)
    assert iter_bgr_frames.__defaults__[0] is None
    assert OpenCvFrameSource.name == "opencv"
    assert cpu_fallback("pyav", {"opencv", "pyav"}) == "pyav"
    assert cpu_fallback("torchcodec", {"opencv"}) == "opencv"


def test_four_rates_receipt_never_equates_export_fps_with_inference_fps() -> None:
    from backend.app.workbench.media import SamplingAudit, four_rates_receipt

    audit = SamplingAudit(
        source_sha256="b" * 64,
        declared_target_fps=5.0,
        nominal_fps=25.0,
        frame_interval=5,
        selected_backend="ultralytics_track",
    )
    for _ in range(25):
        audit.record_decoded_frame()
        audit.record_primary_inference()
        audit.record_tracker_update()
    for _ in range(3):
        audit.record_recovery_inference()
    for _ in range(5):
        audit.record_export_sample()
    rates = four_rates_receipt(audit)
    assert rates.decodeCount == 25
    assert rates.detectorPrimaryCount == 25
    assert rates.detectorRecoveryCount == 3
    assert rates.trackerUpdateCount == 25
    assert rates.exportCount == 5
    assert rates.exportFpsEqualsInferenceFps is False
    assert rates.decodeFpsEqualsExportFps is False
    assert "EXPORT_FPS_IS_NOT_INFERENCE_FPS" in rates.notes
    wired = audit.four_rates()
    assert wired == rates


def test_edit_list_renders_on_demand_instead_of_reencoding_the_match() -> None:
    from backend.app.workbench.media import render_on_demand, store_edit_list

    edits = store_edit_list(
        source_sha256="c" * 64,
        intervals=[{"start": 12.0, "end": 14.0}, {"start": 40.0, "end": 42.5}],
    )
    assert edits["reencodeFullMatch"] is False
    assert edits["renderOnDemand"] is True
    clip = render_on_demand(edits, start=12.0, end=14.0)
    assert clip["sourceSha256"] == "c" * 64
    assert clip["interval"] == (12.0, 14.0)
    assert clip["reencodedFullMatch"] is False


def test_colour_fixture_keeps_bgr_torso_evidence_and_source_box_round_trip() -> None:
    from backend.app.workbench.media import colour_round_trip, torso_colour_pixels

    rgb = bytes([10, 200, 30])
    converted = torso_colour_pixels(rgb, colour_order="rgb")
    native = torso_colour_pixels(bytes([30, 200, 10]), colour_order="bgr")
    assert converted == native
    with pytest.raises(ValueError, match="rgb decoder without conversion"):
        torso_colour_pixels(rgb, colour_order="rgb", convert=False)
    box = colour_round_trip(source_box=(10, 20, 40, 50), crop=(10, 20, 40, 50), rotation=0)
    assert box == (10, 20, 40, 50)


def test_xt_and_vaep_stay_deferred_until_events_map_to_spadl() -> None:
    from backend.app.workbench.xt import xt_deferred_plan

    plan = xt_deferred_plan()
    assert plan["enabled"] is False
    assert plan["imported"] is False
    assert "SPADL" in plan["blockedUntil"]
    assert plan["socceractionImportDoesNotValidateExtraction"] is True


def test_report_claims_carry_a_provenance_chain_to_evidence() -> None:
    from backend.app.workbench.reports import claim_provenance

    chain = claim_provenance(
        claims=[{"text": "second-half turnover then shot", "evidenceIds": ["e1", "e2"]}],
        known_evidence_ids={"e1", "e2"},
    )
    assert chain["accepted"] is True
    assert chain["claims"][0]["evidenceIds"] == ["e1", "e2"]
    broken = claim_provenance(
        claims=[{"text": "invented goal", "evidenceIds": ["missing"]}],
        known_evidence_ids={"e1"},
    )
    assert broken["accepted"] is False
    assert "FABRICATED_EVIDENCE" in broken["reasonCodes"]


def test_provider_adapters_are_split_from_llm_and_stay_disabled_by_default() -> None:
    from backend.app.workbench.providers import cloud_adapter, local_adapter, provider_roster

    roster = provider_roster()
    assert roster["default"] == "disabled"
    assert "llm.py" not in roster["adapters"]
    assert set(roster["adapters"]) == {"local", "cloud"}
    assert local_adapter(enabled=False)["route"] == "disabled"
    assert cloud_adapter(enabled=False)["route"] == "disabled"
    with pytest.raises(RuntimeError, match="not authorised"):
        cloud_adapter(enabled=True)


def test_rejected_automation_still_offers_manual_tagging() -> None:
    from backend.app.workbench.setup import assess_match_setup

    handheld = assess_match_setup(
        camera_profile="handheld_low_angle",
        pitch_length_m=None,
        rights={"processingScope": "local_only", "cloudPermission": False},
        periods=[{"name": "first_half", "startSeconds": 0, "endSeconds": 2700}],
    )
    assert handheld["automationAdmitted"] is False
    assert handheld["manualTaggingPermitted"] is True
    assert "physical_metrics" in handheld["cannotMeasure"]
    assert handheld["costEstimateRequiresAuthorisation"] is True
    wide = assess_match_setup(
        camera_profile="stable_elevated_wide",
        pitch_length_m=105,
        rights={"processingScope": "local_only", "cloudPermission": False},
        periods=[{"name": "first_half", "startSeconds": 0, "endSeconds": 2700}],
    )
    assert wide["automationAdmitted"] is True
    assert wide["certified"] is False


def test_metric_inspector_exposes_definition_and_renders_unknown_as_unavailable() -> None:
    from backend.app.workbench.evidence import inspect_metric

    inspected = inspect_metric(
        "my_team_distance_m",
        value=None,
        availability="unknown",
        eligible_duration=0.0,
        exclusions=["IDENTITY_DISCONTINUITY"],
    )
    assert inspected["unit"] == "metres"
    assert inspected["denominator"] == "identity_continuous_eligible_seconds"
    assert inspected["definitionVersion"] == "1"
    assert inspected["eligibleDuration"] == 0.0
    assert inspected["rendered"] == "unavailable"
    assert inspected["rendered"] != "0"
    assert inspected["publishedValue"] is None


def test_content_addressed_artifacts_restore_and_keep_evaluation_cache_isolated(tmp_path: Path) -> None:
    from backend.app.workbench.artifacts import ArtifactStore, object_storage_adapter

    store = ArtifactStore(tmp_path / "cas")
    digest = store.put(b"observation-bytes", namespace="production")
    assert digest == store.put(b"observation-bytes", namespace="production")
    assert store.get(digest, namespace="production") == b"observation-bytes"
    with pytest.raises(KeyError):
        store.get(digest, namespace="held_out_evaluation")
    restored = store.restore_to(tmp_path / "disposable")
    assert (restored / digest).read_bytes() == b"observation-bytes"
    hosted = object_storage_adapter(hosted_approved=False)
    assert hosted["enabled"] is False
    assert hosted["mandatoryDuckDb"] is False


def test_worker_import_rejects_traversal_unrecognised_and_oversized_archives(tmp_path: Path) -> None:
    from backend.app.workbench.artifacts import import_worker_output

    allowed = import_worker_output(
        {"path": "observations.parquet", "bytes": 12, "kind": "observations", "jobSucceeded": True},
        quality_accepted=False,
    )
    assert allowed["imported"] is True
    assert allowed["productQualityPass"] is False
    traversal = import_worker_output({"path": "../secrets.env", "bytes": 12, "kind": "observations"})
    assert traversal["imported"] is False
    assert "PATH_TRAVERSAL" in traversal["reasonCodes"]
    unknown = import_worker_output({"path": "notes.txt", "bytes": 12, "kind": "unexpected_blob"})
    assert unknown["imported"] is False
    assert "UNRECOGNISED_WORKER_OUTPUT" in unknown["reasonCodes"]
    huge = import_worker_output({"path": "observations.parquet", "bytes": 10_000_000_000, "kind": "observations"})
    assert huge["imported"] is False
    assert "OVERSIZED_ARCHIVE" in huge["reasonCodes"]


def test_object_access_ignores_client_tenant_and_expires_sharing_links() -> None:
    from backend.app.workbench.access import authorize_object, mint_sharing_link, object_access_decision, upload_quota

    decision = authorize_object(object_id="match-1", session_tenant="club-a", client_tenant="club-b")
    assert decision["allowed"] is True
    assert decision["tenant"] == "club-a"
    denied = authorize_object(object_id="match-1", session_tenant="club-a", client_tenant="club-b", object_tenant="club-b")
    assert denied["allowed"] is False
    loopback = object_access_decision(
        object_id="match-1",
        object_tenant="club-a",
        authorization=None,
        object_scope=None,
        deployment_boundary="loopback",
        client_tenant="club-b",
    )
    assert loopback["allowed"] is True
    assert loopback["sessionTenant"] == "club-a"
    hosted_unsigned = object_access_decision(
        object_id="match-1",
        object_tenant="club-a",
        authorization=None,
        object_scope=None,
        deployment_boundary="hosted",
        client_tenant="club-a",
    )
    assert hosted_unsigned["allowed"] is False
    assert "UNSIGNED_OR_UNSCOPED_OBJECT_ACCESS" in hosted_unsigned["reasonCodes"]
    hosted_spoofed = object_access_decision(
        object_id="match-1",
        object_tenant="club-a",
        authorization="club-b",
        object_scope="match-1",
        deployment_boundary="hosted",
        client_tenant="club-a",
    )
    assert hosted_spoofed["allowed"] is False
    assert hosted_spoofed["sessionTenant"] is None
    hosted_ok = object_access_decision(
        object_id="match-1",
        object_tenant="club-a",
        authorization="club-a",
        object_scope="match-1",
        deployment_boundary="hosted",
        client_tenant="club-b",
    )
    assert hosted_ok["allowed"] is False
    assert hosted_ok["admitted"] is False
    assert "HOSTED_SIGNED_ACCESS_UNIMPLEMENTED" in hosted_ok["reasonCodes"] or "UNSIGNED_OR_UNSCOPED_OBJECT_ACCESS" in hosted_ok["reasonCodes"]
    link = mint_sharing_link(object_id="clip-1", now=100, ttl_seconds=10)
    assert link["expired"](100) is False
    assert link["expired"](111) is True
    quota = upload_quota(byte_size=9_000_000_000, duration_seconds=12_000)
    assert quota["admitted"] is False
    assert "DURATION_QUOTA" in quota["reasonCodes"] or "SIZE_QUOTA" in quota["reasonCodes"]


def test_face_recognition_cross_season_identity_and_unproven_eu_residency_stay_blocked() -> None:
    from backend.app.workbench.privacy import dpia_screen, residency_claim
    from backend.app.workbench.identity import cross_season_identity, face_recognition

    screen = dpia_screen(
        youth_footage=False,
        identifiable_faces=True,
        cloud_requested=True,
        cloud_permitted=True,
        face_recognition_requested=True,
        cross_season_requested=True,
    )
    assert screen.faceRecognition is False
    assert screen.crossSeasonIdentity is False
    assert face_recognition(requested=True)["enabled"] is False
    assert cross_season_identity(requested=True)["enabled"] is False
    claim = residency_claim(requested_region="eu", provider="daytona")
    assert claim["euProcessingProven"] is False
    assert "REQUESTED_REGION_IS_NOT_PROOF" in claim["reasonCodes"]


def test_licence_dataset_and_incident_registers_are_explicit() -> None:
    from backend.app.workbench.rights import dataset_manifest, incident_response, licence_register

    licences = licence_register()
    assert "ultralytics" in licences
    assert licences["ultralytics"]["generalisedToEveryYoloNamedModel"] is False
    data = dataset_manifest()
    assert data["soccernet"]["commercialProduct"] is False
    incident = incident_response()
    assert incident["path"]
    assert incident["faceRecognition"] is False


def test_challenger_adapters_stay_fail_closed_and_are_not_defaults() -> None:
    from backend.app.workbench.challengers import (
        gstreamer_adapter,
        kloppy_boundary,
        mcbyte_adapter,
        onnx_runtime_adapter,
        pynv_adapter,
        roboflow_trackers_adapter,
        tensorrt_adapter,
    )

    for adapter in (
        onnx_runtime_adapter,
        tensorrt_adapter,
        pynv_adapter,
        gstreamer_adapter,
        roboflow_trackers_adapter,
        mcbyte_adapter,
    ):
        result = adapter()
        assert result["default"] is False
        assert result["enabled"] is False
    kloppy = kloppy_boundary()
    assert kloppy["replacesInternalProvenance"] is False
    assert kloppy["role"] == "import_export_boundary"


def test_legacy_absent_null_and_rollback_readers_do_not_invent_zeros() -> None:
    from backend.app.workbench.evidence import migrate_legacy_record, rollback_reader

    absent = migrate_legacy_record({})
    assert absent["possession_pct"]["value"] is None
    assert absent["possession_pct"]["availability"] == "unknown"
    nulls = migrate_legacy_record({"possession": None, "myTeamDistance": None})
    assert nulls["my_team_distance_m"]["value"] is None
    rolled = rollback_reader(nulls)
    assert "possession" in rolled
    assert rolled["possession"] is None
    assert rolled.get("myTeamDistance") is None


def test_incident_ladder_keeps_geometry_indeterminate_and_3d_schematic() -> None:
    from backend.app.workbench.incidents import level1_positional_aid, level2_schematic_replay, level3_multiview

    aid = level1_positional_aid(
        touch_interval=(12.04, 12.16),
        attacker_x=10.0,
        offside_line_x=10.0,
        uncertainty_m=0.4,
    )
    assert aid["level"] == 1
    assert aid["decision"] is None
    assert aid["indeterminate"] is True
    assert aid["validatedMeasurement"] is False
    assert aid["touchInterval"] == (12.04, 12.16)
    schematic = level2_schematic_replay(coordinates=[{"x": 10, "y": 20}])
    assert schematic["level"] == 2
    assert schematic["photorealistic"] is False
    assert schematic["decision"] is None
    blocked = level3_multiview()
    assert blocked["level"] == 3
    assert blocked["enabled"] is False
    assert "NEW_DATASET_REQUIRED" in blocked["reasonCodes"]


def test_incident_review_does_not_invent_origin_geometry_when_players_are_missing(tmp_path: Path) -> None:
    from backend.app.schemas import FrameData
    from backend.app.storage import Storage

    storage = Storage(tmp_path)
    source = tmp_path / "empty.json"
    source.write_text("[]")
    match = storage.create_match(
        "empty geometry",
        "tracking_json",
        "empty.json",
        source,
        MatchConfig(),
    )
    storage.save_frames(
        match.id,
        [FrameData(frameId=0, timestamp=3.5, myTeam=[], enemies=[], unassignedPlayers=[])],
    )
    review = storage.incident_review_for_match(match.id)
    assert review["decision"] is None
    assert review["validatedMeasurement"] is False
    assert review["samples"] == []
    assert "IFAB_LAW_11_NOT_APPLIED" in review["reasonCodes"]
    blob = json.dumps(review)
    assert "attackerX=0" not in blob
    assert all(sample.get("attackerX") not in (0, 0.0) for sample in review["samples"])


def test_recovery_corrupted_full_disk_interrupted_upload_and_restore(tmp_path: Path) -> None:
    from backend.app.workbench.recovery import (
        corrupted_import,
        full_disk,
        interrupted_upload,
        restore_exercise,
        support_bundle,
    )

    corrupt = corrupted_import(expected_sha256="a" * 64, actual_sha256="b" * 64)
    assert corrupt["accepted"] is False
    disk = full_disk()
    assert disk["status"] == "failed"
    assert disk["acceptedPartial"] is False
    upload = interrupted_upload(tmp_path / "partial.bin")
    assert upload["accepted"] is False
    assert not (tmp_path / "partial.bin").exists() or upload["quarantined"] is True
    restored = restore_exercise(tmp_path / "backup", tmp_path / "disposable-restore")
    assert restored["destination"] != restored["source"]
    assert restored["tested"] is True
    bundle = support_bundle(consented=True, ttl_seconds=600, now=0)
    assert bundle["expired"](601) is True
    assert support_bundle(consented=False, ttl_seconds=600, now=0)["released"] is False


def test_scale_scenarios_keep_gb_gib_and_planning_assumptions_explicit() -> None:
    from backend.app.workbench.costs import deployment_choice, decimal_gb_to_gib, scale_scenario

    ten = scale_scenario(matches_per_month=10)
    assert ten["variableTechnical"] == 23.4
    assert ten["reviewLabour"] == 100.0
    assert ten["totalIncludingFixed"] == 173.4
    assert ten["measuredApplicationPerformance"] is False
    assert abs(decimal_gb_to_gib(5.4) - (5.4 * 1e9 / (1024**3))) < 1e-9
    local = deployment_choice(privacy_required=True, irregular_usage=False, suitable_local_hardware=True)
    assert local["selected"] == "local"
    burst = deployment_choice(privacy_required=False, irregular_usage=True, suitable_local_hardware=False)
    assert burst["selected"] == "cloud_burst"
    assert burst["alwaysOnGpuCommitted"] is False


def test_repository_adapter_does_not_replace_storage_and_http_cannot_run_gpu() -> None:
    from backend.app.workbench.repository import RepositoryAdapter, http_may_run_gpu, vector_broker_required
    from backend.app import storage as storage_mod

    adapter = RepositoryAdapter()
    assert adapter.backend_name == "sqlite_plus_artifacts"
    assert adapter.replaces_storage_module is False
    assert storage_mod.Storage is not None
    assert http_may_run_gpu() is False
    assert vector_broker_required() is False


def test_repository_page_frames_bounds_payload_and_preserves_count() -> None:
    from backend.app.schemas import FrameData
    from backend.app.workbench.repository import DEFAULT_FRAME_PAGE_LIMIT, RepositoryAdapter

    frames = [FrameData(frameId=index, timestamp=index / 5) for index in range(500)]
    adapter = RepositoryAdapter()
    page = adapter.page_frames(frames, limit=10)
    assert [item.frameId for item in page["frames"]] == list(range(10))
    assert page["nextCursor"] == "10"
    assert page["frameCount"] == 500
    assert page["intervalEndpoint"] == "half_open"
    assert DEFAULT_FRAME_PAGE_LIMIT == 240

    next_page = adapter.page_frames(frames, cursor=page["nextCursor"], limit=10)
    assert [item.frameId for item in next_page["frames"]] == list(range(10, 20))
    assert next_page["nextCursor"] == "20"

    after = adapter.page_frames(frames, after_frame=100, limit=5)
    assert [item.frameId for item in after["frames"]] == list(range(100, 105))
    assert after["nextCursor"] == "105"

    capped = adapter.page_frames(frames, limit=10_000)
    assert len(capped["frames"]) == DEFAULT_FRAME_PAGE_LIMIT
    assert capped["nextCursor"] == str(DEFAULT_FRAME_PAGE_LIMIT)


def test_repository_page_frames_reports_source_frame_bound_for_sparse_samples() -> None:
    from backend.app.schemas import FrameData
    from backend.app.workbench.repository import RepositoryAdapter

    frames = [FrameData(frameId=index, timestamp=index / 25) for index in (0, 5, 10, 15)]
    page = RepositoryAdapter().page_frames(frames, limit=2)
    assert page["frameCount"] == 4
    assert page["lastFrameId"] == 15


def test_llm_execution_is_delegated_to_provider_adapters() -> None:
    from backend.app import llm
    from backend.app import provider_adapters

    assert llm.execute_local is provider_adapters.execute_local
    assert llm.execute_cloud is provider_adapters.execute_cloud
    assert provider_adapters.CONFIGURED_DEFAULT == "disabled_until_policy"


def test_trackeval_cvat_and_video_models_stay_unpromoted() -> None:
    from backend.app.workbench.challengers import trackeval_adapter
    from backend.app.workbench.roster import label_products, video_model_roster
    from backend.app.workbench.adoption import dependency_register

    assert trackeval_adapter()["enabled"] is False
    products = label_products()
    assert products["cvat"]["role"] == "independent_labelling"
    assert products["in_app_corrections"]["role"] == "analyst_repair"
    assert products["cvat"]["sameProductAsCorrections"] is False
    roster = video_model_roster()
    assert roster["qwen3_5_4b"]["promoted"] is False
    assert roster["mvitv2"]["promoted"] is False
    assert roster["videomae_v2"]["promoted"] is False
    register = dependency_register()
    assert "ultralytics" in register
    assert register["ultralytics"]["rollbackPath"]


def test_job_manifest_records_namespace_and_excludes_host_credentials() -> None:
    from backend.app.workbench.jobs import JobRequest, cleanup_failure_is_complete, pause_experiment, worker_environment

    request = JobRequest(
        requestId="run-17",
        matchId="m1",
        sourceSha256="e" * 64,
        intervalStart=0.0,
        intervalEnd=90.0,
        temporalPolicy="source_global_grid",
        decoderVersion="opencv",
        modelHash="weights-v1",
        outputSchema="evidence_v1",
        budget=4.0,
        authorisedLocation="local",
        pixelFormat="bgr24",
        precision="fp32",
        namespace="held_out_evaluation",
        cameraProfile="stitched_panoramic_view",
    )
    assert request.namespace == "held_out_evaluation"
    env = worker_environment(request, host_secret="DAYTONA_API_KEY=super-secret")
    assert "super-secret" not in str(env)
    assert "DAYTONA_API_KEY" not in env
    assert cleanup_failure_is_complete("failed") is False
    assert pause_experiment(remaining=1.0, termination_and_recovery=2.5) is True


def test_deployment_modes_embeddings_and_dual_budgets_stay_gated() -> None:
    from backend.app.workbench.jobs import deployment_mode
    from backend.app.workbench.assistance import dual_budgets, embeddings_retrieve, policy_log, preemptible_allowed

    local = deployment_mode("local_only")
    assert local["silentCloudFallback"] is False
    hosted = deployment_mode("hosted_collaboration")
    assert hosted["requiresGNetwork"] is True
    assert hosted["admitted"] is False
    retrieved = embeddings_retrieve("pressing weakness", passages=[{"id": "p1", "text": "maybe a press"}])
    assert retrieved["provesTacticalWeakness"] is False
    assert retrieved["enabled"] is False
    budgets = dual_budgets(vision=2.0, language=0.1)
    assert budgets["vision"] != budgets["language"]
    log = policy_log(route="template", evidence_hash="abc", secret="sk-live-secret")
    assert "sk-live-secret" not in str(log)
    assert preemptible_allowed(checkpoints=False, restart_semantics=False) is False


def test_risk_register_worked_flow_and_independent_reviewer_stay_honest() -> None:
    from backend.app.workbench.risks import independent_reviewer, risk_register, telestration_before_3d, worked_match_flow

    register = risk_register()
    ids = {item["id"] for item in register}
    assert "labels_incomplete" in ids
    assert "false_precision" in ids
    flow = worked_match_flow()
    assert flow["illustrative"] is True
    assert flow["jobId"] == "run-17"
    assert flow["assetId"] == "asset-A"
    assert flow["correctionInvalidatesReportWithoutRerun"] is True
    reviewer = independent_reviewer(developer="alice", reviewer="alice", inspected_held_out=True)
    assert reviewer["accepted"] is False
    assert telestration_before_3d()["blenderEnabled"] is False
    assert telestration_before_3d()["pitchView"] == "2d"


def test_architecture_decisions_record_alternatives_owner_and_reconsideration() -> None:
    from backend.app.workbench.decisions import architecture_decisions

    records = architecture_decisions()
    ids = [item["id"] for item in records]
    assert ids == [
        "camera_support",
        "coordinate_conventions",
        "persistence",
        "detector_licensing",
        "ai_routing",
        "cloud_region",
        "capability_release",
    ]
    for item in records:
        assert item["alternatives"]
        assert item["evidence"]
        assert item["owner"]
        assert item["reversible"] is True
        assert item["reconsiderWhen"]
    camera = next(item for item in records if item["id"] == "camera_support")
    assert camera["decision"] == "stitched_panoramic_view_declared_initial"
    cloud = next(item for item in records if item["id"] == "cloud_region")
    assert cloud["euGpuProven"] is False


def test_promotion_receipt_is_not_complete_match_acceptance() -> None:
    from backend.app.workbench.receipts import promotion_receipt

    receipt = promotion_receipt(
        source_sha256="a" * 64,
        weights="weights-v1",
        configuration="evidence_v1",
        hardware="cpu",
        native_builds=[],
        selected_backend="opencv+ultralytics_track",
        frame_count=10,
        call_count=10,
        cold_timing_ms=100,
        warm_timing_ms=40,
        peak_memory_bytes=1024,
        transferred_bytes=0,
        output_quality="unproven",
        accepted_coverage=0.0,
        failure_cases=["labels_incomplete"],
        allocated_spend=1.0,
        fallback_event="cpu_local",
    )
    assert receipt["stageBenchmarkIsCompleteMatchAcceptance"] is False
    assert receipt["completeMatchAccepted"] is False
    assert receipt["fallbackEvent"] == "cpu_local"
    assert receipt["sourceSha256"] == "a" * 64


def test_rollback_stops_admission_and_does_not_rewrite_past_outcomes() -> None:
    from backend.app.workbench.rollback import rollback_release

    rolled = rollback_release(flag_name="gpu_default", affected_outputs=["run-17-report"])
    assert rolled["flagReverted"] is True
    assert rolled["flagName"] == "gpu_default"
    assert rolled["newJobsAdmitted"] is False
    assert rolled["artifactsPreserved"] is True
    assert "run-17-report" in rolled["staleOutputs"]
    assert rolled["rewrotePastTrialOutcomes"] is False


def test_calibration_team_and_track_edits_reuse_image_space_detections() -> None:
    from backend.app.video_pipeline import reprocess_for_change

    calls: list[str] = []
    for change in ("calibration", "team_mapping", "track_edit", "ownership"):
        result = reprocess_for_change(
            change=change,
            previous_identity="old-cal",
            current_identity="new-cal",
            vision=lambda change=change: calls.append(change) or {"rows": [{"Frame_ID": 1}]},
        )
        assert result["visionInvoked"] is False
        assert result["kind"] == "plan"
        assert result["imageSpaceDetectionsReused"] is False
        assert result["reused"] is False
    assert calls == []


def test_tile_to_source_transform_merges_overlaps_deterministically() -> None:
    from backend.app.workbench.perception import merge_tiled_detections, tile_to_source

    mapped = tile_to_source(bbox=(10.0, 20.0, 30.0, 40.0), origin=(100.0, 50.0), scale=2.0)
    assert mapped == (120.0, 90.0, 160.0, 130.0)
    merged = merge_tiled_detections(
        [
            {"bbox": (0.0, 0.0, 10.0, 10.0), "score": 0.4, "tileId": "b"},
            {"bbox": (1.0, 1.0, 11.0, 11.0), "score": 0.9, "tileId": "a"},
            {"bbox": (80.0, 80.0, 90.0, 90.0), "score": 0.5, "tileId": "c"},
        ],
        iou_threshold=0.3,
    )
    assert len(merged) == 2
    assert merged[0]["score"] == 0.9
    assert merged[0]["tileId"] == "a"
    assert all(item["sourceCoordinates"] is True for item in merged)


def test_preview_landmark_fit_does_not_commit_or_rerun_vision() -> None:
    from backend.app.workbench.geometry import preview_landmark_fit

    preview = preview_landmark_fit(residual_p95_m=4.2, max_p95_m=3.0)
    assert preview["preview"] is True
    assert preview["committed"] is False
    assert preview["accepted"] is False
    assert preview["visionRerun"] is False
    assert "pitch_positions" in preview["rebuild"]


def test_hosted_collaboration_requires_explicit_lock_and_does_not_silently_replace() -> None:
    from backend.app.workbench.review import collaboration_lock

    local = collaboration_lock(mode="local_only")
    assert local["required"] is False
    assert local["silentlyReplaced"] is False
    hosted = collaboration_lock(mode="hosted_collaboration", lock_holder="analyst-a", requester="analyst-b")
    assert hosted["required"] is True
    assert hosted["admitted"] is False
    assert hosted["acquired"] is False
    assert hosted["silentlyReplaced"] is False


def test_retries_cannot_exceed_declared_spend() -> None:
    from backend.app.workbench.jobs import DurableJobLedger, JobRequest, MAX_ATTEMPTS

    ledger = DurableJobLedger()
    request = JobRequest(
        requestId="spend-1",
        matchId="m1",
        sourceSha256="a" * 64,
        intervalStart=0.0,
        intervalEnd=10.0,
        temporalPolicy="source_global_grid",
        decoderVersion="opencv",
        modelHash="weights-v1",
        outputSchema="evidence_v1",
        budget=1.25,
        authorisedLocation="local",
    )
    attempt = ledger.submit(request)
    ledger.transition(
        attempt.attemptId,
        expected_revision=attempt.revision,
        owner_id="legacy",
        status="failed",
        error="worker",
    )
    attempt = ledger.retry("spend-1")
    ledger.transition(
        attempt.attemptId,
        expected_revision=attempt.revision,
        owner_id=f"job:{request.requestId}",
        status="failed",
        error="worker",
    )
    summary = ledger.cost_summary()
    assert summary["reservedTotal"] <= request.budget
    assert summary["actualTotal"] <= request.budget
    with pytest.raises(RuntimeError, match="retry budget exhausted"):
        while True:
            attempt = ledger.latest_attempt("spend-1")
            ledger.transition(
                attempt.attemptId,
                expected_revision=attempt.revision,
                owner_id=attempt.ownerId or "legacy",
                status="failed",
                error="worker",
            )
            ledger.retry("spend-1")
            if len(ledger.attempts["spend-1"]) > MAX_ATTEMPTS + 2:
                break


def test_analyst_workflow_measures_stay_unmeasured_until_a_real_reviewed_match() -> None:
    from backend.app.workbench.evaluation import analyst_workflow_measures

    measures = analyst_workflow_measures()
    assert measures["measured"] is False
    assert measures["analystCompletedReviewedMatch"] is False
    assert measures["correctionTimeSeconds"] is None
    assert measures["missedUsefulPassages"] is None
    assert measures["exportUsefulness"] is None
    assert measures["trust"] is None
    assert "ANALYST_ACCEPTANCE_MISSING" in measures["reasonCodes"]


def test_rejected_events_leave_accepted_views_but_retain_the_candidate_and_reason() -> None:
    from backend.app.workbench.events import partition_events

    partitioned = partition_events(
        [
            {"id": "e1", "reviewStatus": "accepted", "label": "shot"},
            {"id": "e2", "reviewStatus": "rejected", "label": "pass", "rejectionReason": "ambiguous deflection"},
            {"id": "e3", "reviewStatus": "unreviewed", "label": "turnover"},
        ]
    )
    assert [item["id"] for item in partitioned["acceptedViews"]] == ["e1"]
    assert partitioned["retainedCandidates"][0]["id"] == "e2"
    assert partitioned["retainedCandidates"][0]["rejectionReason"] == "ambiguous deflection"
    assert partitioned["rejectedRemovedFromAcceptedViews"] is True


def test_event_review_applies_to_stored_candidates_and_ignores_unknown_ids() -> None:
    from backend.app.schemas import DetectedEvent
    from backend.app.workbench.events import apply_event_review, restore_event_review

    events = [
        DetectedEvent(type="pass", frameId=1, timestamp=0.2, description="Pass"),
        DetectedEvent(type="recovery", frameId=2, timestamp=0.4, description="Recovery"),
    ]
    forged, previous = apply_event_review(
        events,
        kind="event_accept",
        payload={"eventId": "forged", "frame": 99},
        match_id="m1",
    )
    assert previous == []
    assert [event.reviewStatus for event in forged] == ["unreviewed", "unreviewed"]
    accepted, previous = apply_event_review(
        events,
        kind="event_accept",
        payload={"frame": 1, "type": "pass"},
        match_id="m1",
    )
    assert [event.reviewStatus for event in accepted] == ["accepted", "unreviewed"]
    assert previous[0]["reviewStatus"] == "unreviewed"
    restored = restore_event_review(accepted, previous)
    assert [event.reviewStatus for event in restored] == ["unreviewed", "unreviewed"]


def test_level1_touch_interval_samples_change_without_publishing_an_offside_ruling() -> None:
    from backend.app.workbench.incidents import level1_positional_aid

    aid = level1_positional_aid(
        touch_interval=(12.04, 12.16),
        attacker_x=10.0,
        offside_line_x=10.0,
        uncertainty_m=0.4,
        attacker_x_by_time=((12.04, 9.7), (12.10, 10.0), (12.16, 10.3)),
    )
    assert aid["touchInterval"] == (12.04, 12.16)
    assert aid["singleExactFrame"] is False
    assert len(aid["samples"]) == 3
    assert all(sample["decision"] is None for sample in aid["samples"])
    assert aid["indeterminate"] is True
    assert aid["decision"] is None


def test_cross_tenant_cache_and_columnar_store_stay_gated() -> None:
    from backend.app.workbench.artifacts import columnar_observation_store, cross_tenant_cache_reuse

    blocked = cross_tenant_cache_reuse(source_tenant="club-a", requester_tenant="club-b", explicit_privacy_design=False)
    assert blocked["allowed"] is False
    assert "CROSS_TENANT_CACHE_BLOCKED" in blocked["reasonCodes"]
    permitted = cross_tenant_cache_reuse(source_tenant="club-a", requester_tenant="club-a", explicit_privacy_design=False)
    assert permitted["allowed"] is True
    columnar = columnar_observation_store()
    assert columnar["enabled"] is False
    assert columnar["mandatoryDuckDb"] is False
    assert columnar["justifiedByMeasurement"] is False


def test_preprocessor_and_detector_adapters_keep_source_coordinates_and_fail_closed() -> None:
    from backend.vision import DetectorAdapter, PreprocessPlan

    pre = PreprocessPlan()
    frame = pre.transform(
        pixels=bytes([10, 200, 30] * 4),
        width=2,
        height=2,
        colour_order="rgb",
        crop=(0, 0, 2, 2),
        resize=(2, 2),
    )
    assert frame["colourOrder"] == "bgr"
    assert frame["sourceCoordinatesUnchanged"] is True
    assert frame["silentlyChangedColour"] is False
    assert frame["footballRulesApplied"] is False

    detector = DetectorAdapter()
    receipt = detector.detect(frame, requested_backend="cuda", video_engine_capability=False)
    assert receipt["selectedBackend"] != "cuda"
    assert receipt["fallback"] == "cpu"
    assert receipt["silentlyChangedColour"] is False
    assert receipt["exportFpsEqualsInferenceFps"] is False
    assert receipt["counts"]["primary"] >= 0


def test_research_lane_keeps_planned_tracks_inert_and_cannot_write_product_paths() -> None:
    from backend.app.workbench.research import execute_track, may_write_product_paths, research_lane

    lane = research_lane()
    assert lane["isolated"] is True
    assert lane["supportedCoverageExecutable"] is True
    assert lane["autonomousProductionChanges"] is False
    tracks = {item["id"]: item for item in lane["tracks"]}
    assert tracks["supported-coverage"]["executable"] is True
    assert tracks["supported-coverage"]["inert"] is False
    for name in ("possession/events", "trust-crops", "gpu-bounded-loops", "later-training"):
        assert tracks[name]["executable"] is False
        assert tracks[name]["inert"] is True
    blocked = execute_track("possession/events")
    assert blocked["executed"] is False
    assert "PLANNED_TRACK_INERT" in blocked["reasonCodes"]
    production = execute_track("supported-coverage", in_production=True)
    assert production["executed"] is False
    assert production["productionMutation"] is False
    assert "RESEARCH_ADDON_ONLY" in production["reasonCodes"]
    assert may_write_product_paths(["backend/app/main.py", "frontend/src/App.tsx"]) is False
    assert may_write_product_paths(["research-addon/research_addon/cli.py"]) is True


def test_change_history_is_undoable_and_does_not_rewrite_past_outcomes() -> None:
    from backend.app.workbench.review import change_history

    log = CorrectionLog()
    first = log.submit(new_correction("m1", "team_mapping", {"cluster": 1}))
    undone = log.undo(first.correctionId, author="analyst")
    history = change_history(log.history("m1"))
    assert history["undoable"] is True
    assert history["rewrotePastOutcomes"] is False
    ids = [item["correctionId"] for item in history["items"]]
    assert first.correctionId in ids
    assert undone.correctionId in ids
    assert any(item.get("undoOf") == first.correctionId for item in history["items"])
    original = next(item for item in history["items"] if item["correctionId"] == first.correctionId)
    assert original["payload"]["cluster"] == 1


def test_disabled_providers_leave_review_metrics_and_template_reports_operational() -> None:
    from backend.app.workbench.assistance import providers_disabled_fallback

    fallback = providers_disabled_fallback(
        metrics=[{"metric": "ppda", "availability": "unknown", "reasonCodes": ["ZERO_DENOMINATOR"]}],
        events=[{"id": "e1", "reviewStatus": "accepted", "label": "shot"}],
    )
    assert fallback["reviewOperational"] is True
    assert fallback["metricsOperational"] is True
    assert fallback["templateReportOperational"] is True
    assert fallback["route"] == "template"
    assert "PROVIDER_DISABLED" in fallback["reasonCodes"]
    assert fallback["output"]["kind"] == "deterministic_template"
    assert fallback["output"]["eventCount"] == 1
    assert fallback["concealedPartialProcessing"] is False


def test_decode_memory_policy_bounds_queues_and_fails_closed_without_gpu_capability() -> None:
    from backend.app.workbench.media import decode_memory_policy

    offline = decode_memory_policy(mode="offline", hardware_decode_ok=False, cuda_visible=True)
    assert offline["retainAllDecodedFrames"] is False
    assert offline["backpressure"] is True
    assert offline["reportsMissingSourceEvidence"] is True
    assert offline["gpuResident"] is False
    assert offline["mayDrop"] is False
    assert "HW_DECODE_UNAVAILABLE" in offline["reasonCodes"]
    live = decode_memory_policy(mode="live", hardware_decode_ok=False, cuda_visible=False, drop_policy="declared")
    assert live["mayDrop"] is True
    assert live["dropPolicy"] == "declared"
    assert live["gpuResident"] is False
    undeclared = decode_memory_policy(mode="live", hardware_decode_ok=False, cuda_visible=False, drop_policy=None)
    assert undeclared["mayDrop"] is False
    gpu_ok = decode_memory_policy(mode="offline", hardware_decode_ok=True, cuda_visible=True, video_engine_capability=True)
    assert gpu_ok["gpuResident"] is False
    assert gpu_ok["canPromoteDefault"] is False


def test_held_out_evaluation_cache_is_not_reusable_as_development_cache() -> None:
    from backend.app.workbench.cache import cache_compatible, cache_identity

    shared = dict(
        source_sha256="a" * 64,
        interval_start=0.0,
        interval_end=30.0,
        decoder_version="opencv",
        model_hash="weights-v1",
        temporal_policy="clip_local_index_modulo",
        output_schema="evidence_v1",
    )
    development = cache_identity(**shared, namespace="development")
    held_out = cache_identity(**shared, namespace="held_out_evaluation")
    assert cache_compatible(development, held_out) is False


def test_hota_idf1_refuses_pitch_space_labels_and_hand_edited_summaries() -> None:
    from backend.app.workbench.evaluation import score_hota_idf1

    pitch = score_hota_idf1(label_space="official_pitch", hand_edited_summary=False, native_predictions_present=True)
    assert pitch["scored"] is False
    assert pitch["hota"] is None
    assert pitch["idf1"] is None
    assert pitch["trackevalIsGroundTruth"] is False
    assert "INCOMPATIBLE_HOTA_LABEL_SPACE" in pitch["reasonCodes"]
    edited = score_hota_idf1(label_space="image_space", hand_edited_summary=True, native_predictions_present=True)
    assert edited["scored"] is False
    assert "HANDEDITED_SUMMARY_IS_NOT_A_RESULT" in edited["reasonCodes"]
    missing = score_hota_idf1(label_space="image_space", hand_edited_summary=False, native_predictions_present=False)
    assert missing["scored"] is False
    assert "NATIVE_PREDICTIONS_REQUIRED" in missing["reasonCodes"]


def test_distributed_broker_and_vector_database_stay_unadmitted() -> None:
    from backend.app.workbench.jobs import distributed_broker, vector_database

    broker = distributed_broker(measured_workload_needs=False)
    assert broker["enabled"] is False
    assert broker["admitted"] is False
    assert broker["renamesCurrentQueue"] is False
    vectors = vector_database(measured_recall_benefit=True)
    assert vectors["enabled"] is False
    assert vectors["admitted"] is False
    assert vectors["embeddingsProveTacticalWeakness"] is False


def test_access_deletion_stale_permissions_and_unresolved_incidents_stay_honest() -> None:
    from backend.app.workbench.access import access_deletion_procedure, stale_permissions
    from backend.app.workbench.recovery import recovery_objectives, unresolved_incidents

    missing_roles = access_deletion_procedure(requested=True, controller_recorded=False)
    assert missing_roles["executed"] is False
    assert missing_roles["trackIdsDoNotAnonymise"] is True
    assert "CONTROLLER_PROCESSOR_ROLES_REQUIRED" in missing_roles["reasonCodes"]
    ready = access_deletion_procedure(requested=True, controller_recorded=True)
    assert ready["available"] is True
    assert ready["executed"] is True
    stale = stale_permissions(permission_expires_at=10.0, now=11.0)
    assert stale["stale"] is True
    assert stale["admitted"] is False
    assert "STALE_PERMISSION" in stale["reasonCodes"]
    current = stale_permissions(permission_expires_at=20.0, now=11.0)
    assert current["admitted"] is True
    incidents = unresolved_incidents()
    assert incidents["operatorVisible"] is True
    assert incidents["enterpriseUptimePromised"] is False
    assert incidents["syntheticTestsAreNotDeploymentAssessment"] is True
    objectives = recovery_objectives(data_volume_measured=False, disruption_measured=False)
    assert objectives["defined"] is False
    assert objectives["enterpriseUptimePromised"] is False
    assert "RECOVERY_OBJECTIVES_UNMEASURED" in objectives["reasonCodes"]


def test_untrusted_outputs_secrets_and_unsigned_jobs_stay_fail_closed() -> None:
    from backend.app.workbench.access import deployment_encryption, untrusted_model_output
    from backend.app.workbench.artifacts import secrets_in_artifacts
    from backend.app.workbench.jobs import signed_scoped_job_access

    blocked = untrusted_model_output(
        claimed_actions=["execute_sql"],
        allowed_actions=frozenset({"open_interval", "draft_report"}),
        evidence_ids=["e-missing"],
        known_ids={"e1"},
    )
    assert blocked["trusted"] is False
    assert blocked["admitted"] is False
    assert "ACTION_NOT_ALLOWLISTED" in blocked["reasonCodes"]
    assert "UNKNOWN_EVIDENCE_REFERENCE" in blocked["reasonCodes"]
    ok = untrusted_model_output(
        claimed_actions=["open_interval"],
        allowed_actions=frozenset({"open_interval", "draft_report"}),
        evidence_ids=["e1"],
        known_ids={"e1"},
    )
    assert ok["admitted"] is True
    assert ok["trusted"] is False
    leak = secrets_in_artifacts("DAYTONA_API_KEY=super-secret")
    assert leak["containsSecrets"] is True
    assert leak["admitted"] is False
    clean = secrets_in_artifacts("cleanupResult=unknown")
    assert clean["admitted"] is True
    hosted = deployment_encryption(boundary="hosted")
    assert hosted["hostedEncryptionProven"] is False
    unsigned = signed_scoped_job_access(token=None, job_id="job-1", token_job_id=None)
    assert unsigned["admitted"] is False
    assert "UNSIGNED_OR_UNSCOPED_JOB_ACCESS" in unsigned["reasonCodes"]
    scoped = signed_scoped_job_access(token="t", job_id="job-1", token_job_id="job-2")
    assert scoped["admitted"] is False


def test_network_allowlist_constrained_decoder_and_egress_stay_fail_closed() -> None:
    from backend.app.workbench.access import (
        constrained_decoder,
        least_privilege_storage,
        protocol_network_allowlist,
        public_exposure_gate,
    )
    from backend.app.workbench.jobs import egress_policy

    public = protocol_network_allowlist(url="https://example.com/footage.mp4")
    assert public["admitted"] is False
    assert "PROTOCOL_OR_NETWORK_NOT_ALLOWLISTED" in public["reasonCodes"]
    lan = protocol_network_allowlist(url="http://192.168.1.10/clip.mp4")
    assert lan["admitted"] is False
    loopback = protocol_network_allowlist(url="http://127.0.0.1:8000/local.mp4")
    assert loopback["admitted"] is True
    file_url = protocol_network_allowlist(url="file:///tmp/match.mp4")
    assert file_url["admitted"] is True

    unsafe = constrained_decoder(argv=["ffmpeg", "-i", "http://evil.test", "-c", "copy", "out.mp4"], network_enabled=True)
    assert unsafe["admitted"] is False
    assert "UNCONSTRAINED_DECODER" in unsafe["reasonCodes"]
    from backend.app.workbench.executables import resolve_trusted_executable

    safe = constrained_decoder(
        argv=[
            str(resolve_trusted_executable("ffmpeg")),
            "-i",
            "/tmp/match.mp4",
            "-c",
            "copy",
            "/tmp/out.mp4",
        ],
        network_enabled=False,
    )
    assert safe["admitted"] is True

    open_net = egress_policy(destination="https://attacker.test", authorised_hosts=frozenset())
    assert open_net["admitted"] is False
    assert open_net["defaultDeny"] is True
    assert "WORKER_EGRESS_DENIED" in open_net["reasonCodes"]
    allowed = egress_policy(destination="https://worker.internal/artifacts", authorised_hosts=frozenset({"worker.internal"}))
    assert allowed["admitted"] is True

    broad = least_privilege_storage(credential_scope="account")
    assert broad["admitted"] is False
    assert "LEAST_PRIVILEGE_REQUIRED" in broad["reasonCodes"]
    object_scoped = least_privilege_storage(credential_scope="object")
    assert object_scoped["admitted"] is True

    public_host = public_exposure_gate(security_review_accepted=False, bound="public")
    assert public_host["admitted"] is False
    assert public_host["publicExposureAllowed"] is False
    assert "SECURITY_REVIEW_REQUIRED" in public_host["reasonCodes"]
    loopback_ok = public_exposure_gate(security_review_accepted=False, bound="loopback")
    assert loopback_ok["admitted"] is True
    assert loopback_ok["publicExposureAllowed"] is False


def test_gpu_timing_quality_gates_and_incident_overlays_stay_honest() -> None:
    from backend.app.workbench.benchmarks import quality_gate_holds
    from backend.app.workbench.incidents import (
        broadcast_replay_not_simultaneous,
        elevated_body_part_homography,
        invisible_entity_not_repaired_by_larger_model,
        vlm_confidence_is_not_referee,
    )
    from backend.app.workbench.native import quantized_weight_memory
    from backend.app.workbench.roster import frontier_provider_role
    from backend.app.workbench.timing import gpu_timing_scope

    submission = gpu_timing_scope(submission_ms=12.0, completed_ms=None, device_aware=False)
    assert submission["usesSubmissionAsCompletedWork"] is False
    assert submission["admitted"] is False
    assert "GPU_TIMING_SUBMISSION_IS_NOT_COMPLETED_WORK" in submission["reasonCodes"]
    completed = gpu_timing_scope(submission_ms=12.0, completed_ms=40.0, device_aware=True)
    assert completed["completedMs"] == 40.0
    assert completed["usesSubmissionAsCompletedWork"] is False

    faster = quality_gate_holds(
        faster=True,
        quality_passed=False,
        viewed_results=True,
        original_threshold=0.8,
        proposed_threshold=0.5,
    )
    assert faster["status"] == "experimental"
    assert faster["promoted"] is False
    assert faster["threshold"] == 0.8
    assert "QUALITY_GATE_NOT_REDUCED_AFTER_VIEWING" in faster["reasonCodes"]

    vlm = vlm_confidence_is_not_referee(confidence=0.99)
    assert vlm["refereeGroundTruth"] is False
    assert vlm["decision"] is None
    replay = broadcast_replay_not_simultaneous(same_timestamp=False)
    assert replay["simultaneous"] is False
    assert "SIMULTANEOUS_EVIDENCE_UNPROVEN" in replay["reasonCodes"]
    shoulder = elevated_body_part_homography(part="shoulder")
    assert shoulder["preciseOffsideLine"] is False
    assert "GROUND_PLANE_NOT_BODY_PART" in shoulder["reasonCodes"]
    hidden = invisible_entity_not_repaired_by_larger_model(visible=False)
    assert hidden["repaired"] is False
    assert hidden["admitted"] is False

    quant = quantized_weight_memory(weight_bytes=1_000_000)
    assert quant["completeRuntimeMemory"] is False
    assert "QUANTIZED_WEIGHT_SIZE_IS_NOT_RUNTIME_MEMORY" in quant["reasonCodes"]
    frontier = frontier_provider_role(model_id="gemini-flash")
    assert frontier["role"] == "frontier"
    assert frontier["hardCodedModelName"] is False


def test_native_wheels_os_profiles_and_ffmpeg_builds_stay_unportable() -> None:
    from backend.app.workbench.native import (
        custom_native_justification,
        ffmpeg_build_review,
        no_rpc_fleet,
        pinned_native_artifacts,
        qualified_os_profiles,
    )

    wheels = pinned_native_artifacts()
    assert wheels["universallyPortable"] is False
    assert wheels["admitted"] is False
    assert "NATIVE_WHEELS_NOT_UNIVERSALLY_PORTABLE" in wheels["reasonCodes"]
    macos = qualified_os_profiles(profile="macos")
    ubuntu = qualified_os_profiles(profile="ubuntu")
    assert macos["independentlyTested"] is False
    assert ubuntu["independentlyTested"] is False
    assert macos["admitted"] is False
    windows = qualified_os_profiles(profile="windows")
    assert windows["admitted"] is False
    ffmpeg = ffmpeg_build_review()
    assert ffmpeg["exactConfigurationReviewed"] is False
    assert ffmpeg["wrapperRemovesLicenceObligations"] is False
    assert "FFMPEG_BUILD_UNREVIEWED" in ffmpeg["reasonCodes"]
    rpc = no_rpc_fleet()
    assert rpc["enabled"] is False
    assert rpc["movesFullResolutionFrames"] is False
    native = custom_native_justification(measured_savings=False, required_capability=False)
    assert native["approved"] is False
    assert native["pythonPlusDependenciesAcceptable"] is True
    assert "CUSTOM_NATIVE_UNJUSTIFIED" in native["reasonCodes"]


def test_escalation_json_repair_and_cancellation_charges_stay_bounded() -> None:
    from backend.app.workbench.assistance import escalation_requires_quality_gap, json_repair_chain
    from backend.app.workbench.jobs import cancellation_does_not_erase_charges

    uncertain = escalation_requires_quality_gap(model_uncertain=True, measured_gap=False)
    assert uncertain["escalate"] is False
    assert "ESCALATION_REQUIRES_MEASURED_QUALITY_GAP" in uncertain["reasonCodes"]
    gap = escalation_requires_quality_gap(model_uncertain=False, measured_gap=True)
    assert gap["escalate"] is True
    unbounded = json_repair_chain(attempts=2, max_repair=1)
    assert unbounded["admitted"] is False
    assert "UNBOUNDED_JSON_REPAIR" in unbounded["reasonCodes"]
    one = json_repair_chain(attempts=1, max_repair=1)
    assert one["admitted"] is True
    billed = cancellation_does_not_erase_charges(cancelled=True, incurred=1.2)
    assert billed["chargesErased"] is False
    assert billed["incurred"] == 1.2


def test_frontend_types_are_compatible_with_backend_schemas() -> None:
    from backend.app.schemas import DetectedEvent, JobRecord, MatchConfig, MatchRecord, MetricAvailabilityRecord, ShotAnalytics

    types_path = Path(__file__).resolve().parents[2] / "frontend" / "src" / "types" / "index.ts"
    types_text = types_path.read_text(encoding="utf-8")
    contracts = {
        "BackendEvent": DetectedEvent,
        "ProcessingJob": JobRecord,
        "UploadConfig": MatchConfig,
        "MatchRecord": MatchRecord,
        "ShotMarker": ShotAnalytics,
    }
    for interface_name, model in contracts.items():
        assert f"export interface {interface_name}" in types_text, interface_name
        missing = [name for name in model.model_fields if name not in types_text]
        assert missing == [], f"{interface_name} missing backend fields: {missing}"
    availability_fields = list(MetricAvailabilityRecord.model_fields)
    missing_availability = [name for name in availability_fields if name not in types_text]
    assert missing_availability == [], f"metricAvailability missing backend fields: {missing_availability}"
