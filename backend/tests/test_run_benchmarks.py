import base64
import hashlib
import json
from pathlib import Path
import pytest

from backend.app.run_benchmarks import (
    probe_selected_cluster_benchmarks,
    recommend_selected_cluster_benchmark,
    promote_selected_cluster_benchmark,
    summarize_match_benchmark,
)
from backend.app.schemas import BallOwnership, ColorClusterSummary, DetectedEvent, FrameData, HomographyPoint, MatchConfig, MatchSummary, ShotAnalytics
from backend.app.storage import Storage
from backend.app.runtime_options import ProofRuntimeOptions
from backend.app.settings import ProcessingSettings, SettingsError
import backend.scripts.run_trimmed_ball_recovery_matrix as run_trimmed_ball_recovery_matrix
import backend.scripts.run_trimmed_clip_benchmark as run_trimmed_clip_benchmark
import backend.scripts.run_remote_video_benchmark as run_remote_video_benchmark
import backend.app.run_benchmarks as run_benchmarks_module


def test_benchmark_remote_artifact_reader_prefers_neutral_name_and_falls_back_to_runpod(
    tmp_path: Path,
) -> None:
    storage = Storage(tmp_path)
    match = storage.create_match(
        name="artifact names",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=storage.save_upload("clip.mp4", b"video"),
        config=MatchConfig(autoHomography=True),
    )
    storage.save_analysis_artifact(match.id, "runpod_worker_progress", {"source": "legacy"})
    assert run_benchmarks_module._load_remote_artifact(
        storage, match.id, "remote_worker_progress", "runpod_worker_progress"
    ) == {"source": "legacy"}

    storage.save_analysis_artifact(match.id, "remote_worker_progress", {"source": "neutral"})
    assert run_benchmarks_module._load_remote_artifact(
        storage, match.id, "remote_worker_progress", "runpod_worker_progress"
    ) == {"source": "neutral"}


def test_benchmark_remote_artifact_does_not_fall_back_when_neutral_is_corrupt(
    tmp_path: Path,
) -> None:
    storage = Storage(tmp_path)
    match = storage.create_match(
        name="corrupt neutral",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=storage.save_upload("clip.mp4", b"video"),
        config=MatchConfig(autoHomography=True),
    )
    storage.save_analysis_artifact(match.id, "runpod_worker_progress", {"source": "stale"})
    (storage._match_dir(match.id) / "remote_worker_progress.json").write_text(
        "not-json", encoding="utf-8"
    )

    assert run_benchmarks_module._load_remote_artifact(
        storage, match.id, "remote_worker_progress", "runpod_worker_progress"
    ) is None


@pytest.mark.parametrize(
    ("transport_mode", "use_runsync"),
    [("auto", None), (None, True)],
)
def test_benchmark_remote_dispatch_rejects_provider_specific_options(
    tmp_path: Path,
    monkeypatch,
    transport_mode,
    use_runsync,
) -> None:
    dispatched: list[object] = []
    monkeypatch.setattr(
        "backend.app.remote_worker.run_remote_job",
        lambda *args, **kwargs: dispatched.append((args, kwargs)),
    )

    with pytest.raises(ValueError, match="provider-specific"):
        run_benchmarks_module.run_remote_job(
            tmp_path,
            "job-1",
            settings=ProcessingSettings(),
            transport_mode=transport_mode,
            use_runsync=use_runsync,
        )

    assert dispatched == []


def test_benchmark_summary_reads_neutral_progress_contract_fields(tmp_path: Path) -> None:
    storage = Storage(tmp_path)
    match = storage.create_match(
        name="neutral progress",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=storage.save_upload("clip.mp4", b"video"),
        config=MatchConfig(autoHomography=True),
    )
    job = storage.create_job(match.id)
    storage.update_job(job.id, status="failed", progress=1.0, message="failed")
    storage.save_analysis_artifact(
        match.id,
        "remote_worker_progress",
        {
            "schemaVersion": 1,
            "jobId": job.id,
            "sequence": 1,
            "progress": 98,
            "stage": "resultSerialize",
            "message": "completed",
            "timestamp": "2026-09-02T00:00:00Z",
        },
    )

    summary = summarize_match_benchmark(storage, match.id)

    assert summary.workerCurrentStage == "resultSerialize"
    assert summary.workerStageStatus == "completed"
    assert summary.workerLastHeartbeatAt == "2026-09-02T00:00:00Z"


def _summary() -> MatchSummary:
    return MatchSummary(
        possession=55,
        myTeamDistance=1000,
        enemyDistance=950,
        myTeamAvgPos={"x": 52.0, "y": 48.0},
        enemyAvgPos={"x": 48.0, "y": 52.0},
        myTeamTopSpeed=30.1,
        enemyTopSpeed=29.0,
        myTeamSprints=10,
        enemySprints=9,
        formation="4-3-3",
    )


def _write_artifact_backed_match(
    storage: Storage,
    match_id: str,
    *,
    video_path: str,
    detector_model_name: str = "yolov10n.pt",
    proof_job_id: str = "proof-job-123",
    truth_ready: bool = False,
    long_gap_outcome: str = "long_gap_treatment_partial",
    control_assignment_outcome: str = "controlled_possession_assignment_weak",
) -> None:
    storage.save_raw_rows(
        match_id,
        [
            {"Frame_ID": index, "Timestamp": index * 0.2, "Entity_Type": "ball", "Track_ID": -1, "X": 20 + index, "Y": 30.0}
            for index in range(6)
        ],
    )
    storage.save_frames(
        match_id,
        [
            FrameData(
                frameId=index,
                timestamp=index * 0.2,
                ball={"x": 20 + index, "y": 30.0 + (index % 2), "confidence": 0.9},
            )
            for index in range(6)
        ],
    )
    storage.save_analytics(
        match_id,
        _summary(),
        assignments=[
            BallOwnership(frameId=index, timestamp=index * 0.2, team="my_team", trackId=7, distance=1.0)
            for index in range(4)
        ],
        formation_timeline=[],
        shots=[
            ShotAnalytics(
                frameId=3,
                timestamp=0.6,
                team="my_team",
                playerId=7,
                x=42.0,
                y=18.0,
                onTarget=True,
                inBox=False,
                distanceToGoal=18.5,
                angleDegrees=24.0,
                xg=0.2,
            )
        ],
    )
    storage.save_events(
        match_id,
        [
            DetectedEvent(type="pass", frameId=1, timestamp=0.2, description="pass"),
            DetectedEvent(type="shot", frameId=2, timestamp=0.4, description="shot"),
            DetectedEvent(type="recovery", frameId=3, timestamp=0.6, description="recovery"),
        ],
    )
    storage.save_analysis_artifact(
        match_id,
        "ball_truth_layers",
        {
            "observedBall": {"summary": {"frameCount": 5}},
            "inferredBall": {"summary": {"frameCount": 1}},
            "acceptedBall": {
                "summary": {"frameCount": 6},
                "rows": [
                    {"frameId": index, "timestamp": index * 0.2, "x": 20 + index, "y": 30.0 + (index % 2)}
                    for index in range(6)
                ],
            },
            "acceptedSegments": [{"frameCount": 6}],
            "unknownGaps": [],
            "directObservationBreakdown": {
                "longGapTreatmentOutcome": long_gap_outcome,
                "controlledPossessionAssignmentOutcome": control_assignment_outcome,
                "frozenPrimaryAcquisitionMode": "anchored_player_ranked_context_960",
                "frozenDetectorModelPath": detector_model_name,
            },
            "summary": {
                "fiveMinuteTruthReady": truth_ready,
                "truthGateReasons": [] if truth_ready else ["Need controlled possession frames/frameCount >= 20%"],
            },
        },
    )
    storage.save_analysis_artifact(
        match_id,
        "accepted_match_state",
        {
            "stateContinuityAppliedFrames": 1,
            "frames": [
                {
                    "frameId": index,
                    "timestamp": index * 0.2,
                    "mode": "controlled_possession",
                    "controllingTeam": "my_team",
                    "controllingTrackId": 7,
                    "ballVisibility": "visible",
                    "ballEstimate": None,
                    "source": "observed_ball",
                    "confidence": 0.9,
                    "reasonCodes": ["accepted_ball"],
                }
                for index in range(4)
            ],
        },
    )
    storage.save_analysis_artifact(
        match_id,
        "ball_pipeline_trace",
        {
            "matchId": match_id,
            "jobId": proof_job_id,
            "inputMode": "video",
            "videoPath": video_path,
            "runtimeFingerprint": {"workerFile": "run_guerilla.py"},
        },
    )
    storage.save_analysis_artifact(
        match_id,
        "selected_cluster_delta",
        {
            "after": {
                "matchId": match_id,
                "jobId": proof_job_id,
                "inputMode": "video",
                "matchStatus": "ready",
                "requiresTeamSelection": False,
            }
        },
    )
    storage.save_analysis_artifact(
        match_id,
        "proof_summary",
        {
            "matchId": match_id,
            "savedMatchId": match_id,
            "jobId": proof_job_id,
            "detectorModelName": detector_model_name,
            "detectorModelPath": detector_model_name,
            "acceptedBallFrames": 6,
            "controlledPossessionFrames": 4,
            "ballTrackViable": True,
            "ballTrackEdgeFrameShare": 0.1,
            "fiveMinuteTruthReady": truth_ready,
            "truthGateReasons": [] if truth_ready else ["Need controlled possession frames/frameCount >= 20%"],
            "longGapTreatmentOutcome": long_gap_outcome,
            "controlledPossessionAssignmentOutcome": control_assignment_outcome,
        },
    )


def test_run_remote_video_benchmark_imports_and_summarizes_remote_result(tmp_path, monkeypatch):
    from backend.app.run_benchmarks import run_remote_video_benchmark as run_remote_video_benchmark_helper

    monkeypatch.chdir(tmp_path)
    clip_path = Path("clip-5min.mp4")
    storage_root = Path("storage")
    clip_path.write_bytes(b"video")
    captured: dict[str, object] = {}

    def fake_run_remote_job(storage_root, job_id, settings=None, use_runsync=False):  # noqa: ANN001
        captured["storage_root"] = storage_root
        captured["job_id"] = job_id
        captured["settings"] = settings
        captured["use_runsync"] = use_runsync
        storage = Storage(storage_root)
        job = storage.get_job(job_id)
        captured["input_path"] = storage.get_match_input_path(job.matchId)
        storage.save_raw_rows(
            job.matchId,
            [
                {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 4, "X": 51.0, "Y": 50.0, "Conf": 0.9},
                {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 52.0, "Y": 50.0, "Conf": 0.95},
            ],
        )
        storage.save_frames(
            job.matchId,
            [FrameData(frameId=0, timestamp=0.0, ball={"x": 52.0, "y": 50.0, "confidence": 0.95})],
        )
        storage.save_analytics(
            job.matchId,
            _summary(),
            assignments=[BallOwnership(frameId=0, timestamp=0.0, team="my_team", trackId=4, distance=1.0)],
            formation_timeline=[],
            shots=[],
        )
        storage.save_events(job.matchId, [DetectedEvent(type="recovery", frameId=0, timestamp=0.0, description="recovery")])
        storage.update_match_status(job.matchId, status="ready", requires_team_selection=False, team_clusters=[])
        storage.update_job(job_id, status="completed", progress=1.0, message="remote complete", remote_run_id="runpod-123")

    monkeypatch.setattr("backend.app.run_benchmarks.run_remote_job", fake_run_remote_job)

    summary = run_remote_video_benchmark_helper(
        storage_root=storage_root,
        clip_path=clip_path,
        name="remote proof",
    )

    assert captured["storage_root"] == (tmp_path / storage_root).resolve()
    assert captured["input_path"] == (tmp_path / clip_path).resolve()
    assert captured["use_runsync"] is False
    assert summary.matchStatus == "ready"
    assert summary.jobStatus == "completed"
    assert summary.rawRowCount == 2
    assert summary.frameCount == 1
    assert summary.withBallFrames == 1
    assert summary.eventTypes == {"recovery": 1}
    proof_summary = Storage(storage_root).load_analysis_artifact(summary.matchId, "proof_summary")
    assert proof_summary["acceptedBallFrames"] == 1
    assert proof_summary["controlledPossessionFrames"] == 1
    assert proof_summary["eventFamilyCount"] == 1


def test_run_remote_video_benchmark_pins_explicit_frozen_baseline_runtime_options(tmp_path, monkeypatch):
    from backend.app.run_benchmarks import run_remote_video_benchmark as run_remote_video_benchmark_helper

    clip_path = tmp_path / "clip-5min.mp4"
    clip_path.write_bytes(b"video")
    captured: dict[str, object] = {}

    def fake_run_remote_job(storage_root, job_id, settings=None, use_runsync=False):  # noqa: ANN001
        storage = Storage(storage_root)
        job = storage.get_job(job_id)
        captured["proof_runtime_options"] = storage.load_analysis_artifact(job.matchId, "proof_runtime_options")
        storage.save_raw_rows(
            job.matchId,
            [
                {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 4, "X": 51.0, "Y": 50.0, "Conf": 0.9},
                {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 52.0, "Y": 50.0, "Conf": 0.95},
            ],
        )
        storage.save_frames(
            job.matchId,
            [FrameData(frameId=0, timestamp=0.0, ball={"x": 52.0, "y": 50.0, "confidence": 0.95})],
        )
        storage.save_analytics(
            job.matchId,
            _summary(),
            assignments=[BallOwnership(frameId=0, timestamp=0.0, team="my_team", trackId=4, distance=1.0)],
            formation_timeline=[],
            shots=[],
        )
        storage.save_events(job.matchId, [DetectedEvent(type="recovery", frameId=0, timestamp=0.0, description="recovery")])
        storage.save_analysis_artifact(
            job.matchId,
            "ball_truth_layers",
            {
                "observedBall": {"summary": {"frameCount": 1}},
                "inferredBall": {"summary": {"frameCount": 0}},
                "acceptedBall": {"summary": {"frameCount": 1}},
                "acceptedSegments": [{"frameCount": 1}],
                "unknownGaps": [],
                "directObservationBreakdown": {
                    "frozenPrimaryAcquisitionMode": "anchored_player_ranked_context_960",
                    "frozenDetectorModelPath": "yolov10n.pt",
                },
                "summary": {"fiveMinuteTruthReady": False, "truthGateReasons": ["Need more frames"]},
            },
        )
        storage.save_analysis_artifact(
            job.matchId,
            "proof_summary",
            {
                "matchId": job.matchId,
                "savedMatchId": job.matchId,
                "jobId": job.id,
                "detectorModelName": "yolov10n.pt",
                "detectorModelPath": "yolov10n.pt",
                "acceptedBallFrames": 1,
                "controlledPossessionFrames": 1,
                "ballTrackViable": True,
                "ballTrackEdgeFrameShare": 0.1,
                "fiveMinuteTruthReady": False,
                "truthGateReasons": ["Need more frames"],
            },
        )
        storage.update_match_status(job.matchId, status="ready", requires_team_selection=False, team_clusters=[])
        storage.update_job(job.id, status="completed", progress=1.0, message="remote complete", remote_run_id="runpod-123")

    monkeypatch.setattr("backend.app.run_benchmarks.run_remote_job", fake_run_remote_job)

    summary = run_remote_video_benchmark_helper(
        storage_root=tmp_path,
        clip_path=clip_path,
        name="remote proof",
        model_path="yolov10n.pt",
        primary_acquisition_mode="anchored_player_ranked_context_960",
        edge_share_repair_profile="source_robustness_shadow_supported_edge_run_keep_every_3_min10_guard2",
    )

    assert captured["proof_runtime_options"] == {
        "primary_model": {"artifactId": "yolov10n.pt"},
        "auxiliary_ball_model": None,
        "auxiliary_ball_model_profile": None,
        "primary_acquisition_mode": "anchored_player_ranked_context_960",
        "edge_share_repair_profile": "source_robustness_shadow_supported_edge_run_keep_every_3_min10_guard2",
        "baseline_guided_rescue_reference": None,
        "proposal_selection_truth_seed": None,
        "reviewed_positive_anchor_seed": None,
    }
    assert summary.detectorModelName == "yolov10n.pt"
    assert summary.frozenDetectorModelPath == "yolov10n.pt"
    assert summary.frozenPrimaryAcquisitionMode == "anchored_player_ranked_context_960"


def test_run_remote_video_benchmark_cli_serializes_summary(tmp_path, monkeypatch, capsys):
    clip_path = tmp_path / "clip-5min.mp4"
    clip_path.write_bytes(b"video")
    monkeypatch.setenv("PROCESSING_BACKEND", "daytona")
    monkeypatch.setenv("DAYTONA_API_KEY", "secret")

    def fake_run_remote_video_benchmark_helper(**kwargs):  # noqa: ANN003
        assert kwargs["storage_root"] == tmp_path
        assert kwargs["clip_path"] == clip_path
        assert kwargs["name"] == "remote proof"
        return type(
            "FakeSummary",
            (),
            {
                "model_dump": lambda self, mode="json": {
                    "matchId": "match-123",
                    "jobId": "job-123",
                    "rawRowCount": 2,
                    "frameCount": 1,
                    "playerFrames": 1,
                    "withBallFrames": 1,
                    "eventTypes": {"recovery": 1},
                    "ballSignalStatus": "trusted",
                    "ballTrackViable": True,
                    "recoveryProfileName": "edge_margin_40_upper_078",
                    "recoveryApplied": True,
                    "recoveredSelectedFrames": 20,
                    "dominantAnchorCoord": [12.5, 19.5],
                    "dominantAnchorCount": 3,
                    "dominantAnchorShare": 0.75,
                    "meanSourceCenterY": 173.33,
                    "meanSourceBoxArea": 800.0,
                    "corridorCandidateFrames": 6,
                    "corridorFramesWithTwoAnchors": 4,
                    "corridorFramesWithSingleAnchor": 2,
                    "corridorMeanWidth": 11.5,
                    "collapsedCandidateFrames": 7,
                    "collapsedSegmentCount": 2,
                    "collapsedLongestSegmentFrames": 4,
                    "continuityPreferredFrames": 3,
                    "continuityRejectedFrames": 5,
                    "midfieldCollapsedFrames": 6,
                    "candidateEdgeShare": 0.35,
                    "selectedEdgeFrameShare": 0.15,
                    "warmProofMode": True,
                    "warmReadyObserved": True,
                    "warmupWaitSeconds": 15.0,
                    "truthGateReasons": ["Need at least 3 event families"],
                }
            },
        )()

    monkeypatch.setattr(
        "backend.scripts.run_remote_video_benchmark.run_remote_video_benchmark",
        fake_run_remote_video_benchmark_helper,
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_remote_video_benchmark.py",
            "--storage-root",
            str(tmp_path),
            "--video-path",
            str(clip_path),
            "--name",
            "remote proof",
        ],
    )

    run_remote_video_benchmark.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["savedMatchId"] == "match-123"
    assert payload["jobId"] == "job-123"
    assert payload["rawRows"] == 2
    assert payload["frameCount"] == 1
    assert payload["playerFrames"] == 1
    assert payload["ballFrames"] == 1
    assert payload["eventTypes"] == {"recovery": 1}
    assert payload["ballSignalStatus"] == "trusted"
    assert payload["ballTrackViable"] is True
    assert payload["recoveryProfile"] == "edge_margin_40_upper_078"
    assert payload["recoveryApplied"] is True
    assert payload["recoveredSelectedFrames"] == 20
    assert payload["dominantAnchorCoord"] == [12.5, 19.5]
    assert payload["dominantAnchorCount"] == 3
    assert payload["dominantAnchorShare"] == 0.75
    assert payload["meanSourceCenterY"] == 173.33
    assert payload["meanSourceBoxArea"] == 800.0
    assert payload["candidateEdgeShare"] == 0.35
    assert payload["selectedEdgeFrameShare"] == 0.15
    assert payload["warmProofMode"] is True
    assert payload["warmReadyObserved"] is True
    assert payload["warmupWaitSeconds"] == 15.0
    assert payload["truthGateReasons"] == ["Need at least 3 event families"]


def test_run_remote_video_benchmark_cli_accepts_manual_points_json(tmp_path, monkeypatch, capsys):
    clip_path = tmp_path / "clip-5min.mp4"
    clip_path.write_bytes(b"video")
    captured: dict[str, object] = {}
    monkeypatch.setenv("PROCESSING_BACKEND", "daytona")
    monkeypatch.setenv("DAYTONA_API_KEY", "secret")

    def fake_run_remote_video_benchmark_helper(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        return type(
            "FakeSummary",
            (),
            {
                "model_dump": lambda self, mode="json": {
                    "matchId": "match-123",
                    "rawRowCount": 0,
                    "frameCount": 0,
                    "withBallFrames": 0,
                    "eventTypes": {},
                    "truthGateReasons": [],
                }
            },
        )()

    monkeypatch.setattr(
        "backend.scripts.run_remote_video_benchmark.run_remote_video_benchmark",
        fake_run_remote_video_benchmark_helper,
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_remote_video_benchmark.py",
            "--video-path",
            str(clip_path),
            "--manual-points-json",
            "[[1,2],[3,4],[5,6],[7,8]]",
        ],
    )

    run_remote_video_benchmark.main()

    manual_points = captured["manual_points"]
    assert [point.model_dump() for point in manual_points] == [
        {"x": 1.0, "y": 2.0},
        {"x": 3.0, "y": 4.0},
        {"x": 5.0, "y": 6.0},
        {"x": 7.0, "y": 8.0},
    ]
    assert json.loads(capsys.readouterr().out)["savedMatchId"] == "match-123"


def test_run_remote_video_benchmark_cli_fails_before_match_creation_without_credentials(tmp_path, monkeypatch):
    clip_path = tmp_path / "clip-5min.mp4"
    clip_path.write_bytes(b"video")
    monkeypatch.setenv("PROCESSING_BACKEND", "daytona")
    monkeypatch.delenv("DAYTONA_API_KEY", raising=False)

    def fail_if_called(**kwargs):  # noqa: ANN003
        raise AssertionError("benchmark helper should not run without Daytona credentials")

    monkeypatch.setattr(
        "backend.scripts.run_remote_video_benchmark.run_remote_video_benchmark",
        fail_if_called,
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_remote_video_benchmark.py",
            "--storage-root",
            str(tmp_path),
            "--video-path",
            str(clip_path),
        ],
    )

    with pytest.raises(SettingsError, match="DAYTONA_API_KEY"):
        run_remote_video_benchmark.main()


def test_summarize_match_benchmark_falls_back_to_artifacts_when_match_row_is_missing(tmp_path):
    storage = Storage(tmp_path)
    _write_artifact_backed_match(
        storage,
        "artifact-only-match",
        video_path="/workspace/fotball-analyst/videos/trimed-5min.mp4",
        detector_model_name="yolov10n.pt",
        proof_job_id="artifact-job-123",
    )

    summary = summarize_match_benchmark(storage, "artifact-only-match")

    assert summary.matchId == "artifact-only-match"
    assert summary.jobId == "artifact-job-123"
    assert summary.artifactOnly is True
    assert summary.inputMode == "video"
    assert summary.matchStatus == "ready"
    assert summary.requiresTeamSelection is False
    assert summary.videoPath == str(Path(__file__).resolve().parents[2] / "videos" / "trimed-5min.mp4")
    assert summary.detectorModelName == "yolov10n.pt"
    assert summary.longGapTreatmentOutcome == "long_gap_treatment_partial"
    assert summary.controlledPossessionAssignmentOutcome == "controlled_possession_assignment_weak"


def test_summarize_match_benchmark_redacts_inline_primary_model_content(tmp_path):
    storage = Storage(tmp_path)
    match_id = "inline-primary-model-match"
    _write_artifact_backed_match(
        storage,
        match_id,
        video_path="videos/clip.mp4",
    )
    content = b"sensitive-inline-model"
    encoded = base64.b64encode(content).decode("ascii")
    options = ProofRuntimeOptions.from_mapping(
        {
            "primary_model": {
                "inline": {
                    "name": "primary.pt",
                    "contentBase64": encoded,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "sizeBytes": len(content),
                }
            },
            "auxiliary_ball_model": None,
            "auxiliary_ball_model_profile": None,
            "primary_acquisition_mode": "inline-proof",
            "edge_share_repair_profile": None,
            "baseline_guided_rescue_reference": None,
            "proposal_selection_truth_seed": None,
            "reviewed_positive_anchor_seed": None,
        }
    )
    storage.save_analysis_artifact(match_id, "proof_runtime_options", options.to_mapping())
    truth_layers = storage.load_analysis_artifact(match_id, "ball_truth_layers")
    truth_layers["directObservationBreakdown"]["frozenDetectorModelPath"] = json.dumps(
        options.primary_model.to_mapping()
    )
    storage.save_analysis_artifact(match_id, "ball_truth_layers", truth_layers)

    summary = summarize_match_benchmark(storage, match_id)

    assert encoded not in summary.frozenDetectorModelPath
    assert json.loads(summary.frozenDetectorModelPath) == options.primary_model.to_provenance_mapping()


def test_summarize_match_benchmark_uses_artifact_job_metadata_when_job_row_is_missing(tmp_path):
    storage = Storage(tmp_path)
    upload_path = storage.save_upload("clip.mp4", b"video")
    match = storage.create_match(
        name="artifact-fallback",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=upload_path,
        config=MatchConfig(autoHomography=True),
    )
    storage.update_match_status(match.id, status="ready", requires_team_selection=False, team_clusters=[])
    _write_artifact_backed_match(
        storage,
        match.id,
        video_path=str(upload_path),
        detector_model_name="yolov10n.pt",
        proof_job_id="proof-only-job",
    )

    summary = summarize_match_benchmark(storage, match.id)

    assert summary.matchId == match.id
    assert summary.artifactOnly is False
    assert summary.jobId == "proof-only-job"
    assert summary.detectorModelName == "yolov10n.pt"
    assert summary.videoPath == str(upload_path)


def test_summarize_match_benchmark_counts_events_and_artifacts(tmp_path):
    storage = Storage(tmp_path)
    upload_path = storage.save_upload("clip.mp4", b"video")
    match = storage.create_match(
        name="trimmed-demo",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=upload_path,
        config=MatchConfig(
            autoHomography=False,
            manualHomographyPoints=[
                HomographyPoint(x=0, y=0),
                HomographyPoint(x=100, y=0),
                HomographyPoint(x=100, y=100),
                HomographyPoint(x=0, y=100),
            ],
        ),
    )
    job = storage.create_job(match.id)
    storage.update_job(job.id, status="completed", progress=1.0, message="done")
    storage.save_raw_rows(match.id, [{"Frame_ID": 1}, {"Frame_ID": 2}, {"Frame_ID": 3}])
    storage.save_frames(
        match.id,
        [
            FrameData(frameId=1, timestamp=0.1, ball=None),
            FrameData(
                frameId=2,
                timestamp=0.2,
                ball={"x": 10, "y": 20, "confidence": 0.8},
                myTeam=[{"id": 7, "x": 40, "y": 50, "confidence": 0.9}],
            ),
        ],
    )
    storage.save_analytics(
        match.id,
        _summary(),
        assignments=[
            BallOwnership(frameId=1, timestamp=0.1, team="my_team", trackId=7, distance=1.0),
            BallOwnership(frameId=2, timestamp=0.2, team="enemy", trackId=18, distance=1.2),
        ],
        formation_timeline=[],
        shots=[
            ShotAnalytics(
                frameId=2,
                timestamp=0.2,
                team="my_team",
                playerId=9,
                x=90,
                y=50,
                inBox=True,
                xg=0.3,
                distanceToGoal=12.0,
                angleDegrees=25.0,
            )
        ],
    )
    analytics_path = storage.storage_root / "matches" / match.id / "analytics.json"
    analytics_payload = json.loads(analytics_path.read_text(encoding="utf-8"))
    analytics_payload["summary"]["ballSignalStatus"] = "trusted"
    analytics_path.write_text(json.dumps(analytics_payload), encoding="utf-8")
    storage.save_analysis_artifact(
        match.id,
        "recovery_debug",
        {
            "primaryBallFrames": 1,
            "recoveryAttempted": True,
            "recoveryProfileName": "edge_margin_40_upper_078",
            "recoveredCandidateRows": 12,
            "recoveredUniqueFrames": 9,
            "recoveredSelectedFrames": 4,
            "dominantAnchorCoord": [12.5, 19.5],
            "dominantAnchorCount": 3,
            "dominantAnchorShare": 0.75,
            "meanSourceCenterY": 173.33,
            "meanSourceBoxArea": 800.0,
            "candidateEdgeShare": 0.25,
            "nearPlayerWindowShare": 0.5,
            "proposalCandidateFrames": 11,
            "proposalWindowCount": 4,
            "proposalFramesWithAnchorSeed": 7,
            "proposalFramesWithoutAnchorSeed": 4,
            "proposalMeanWindowWidth": 13.5,
            "segmentCount": 2,
            "longestSegmentFrames": 3,
            "selectedEdgeFrameShare": 0.1,
            "selectedPathLength": 18.2,
            "selectedViable": True,
            "recoveryDecision": "applied_profile",
            "recoveryApplied": True,
        },
    )
    storage.save_analysis_artifact(
        match.id,
        "runpod_worker_progress",
        {
            "workerStage": "resultSerialize",
            "stageStatus": "started",
            "heartbeatAt": "2026-04-12T02:30:00+00:00",
            "trackingFramesSeen": 321,
            "workerStartedProcessing": True,
            "workerReturnedResult": False,
        },
    )
    storage.save_events(
        match.id,
        [
            DetectedEvent(type="pass", frameId=1, timestamp=0.1, description="pass"),
            DetectedEvent(type="shot", frameId=2, timestamp=0.2, description="shot"),
            DetectedEvent(type="pass", frameId=3, timestamp=0.3, description="pass"),
        ],
    )
    storage.save_analysis_artifact(
        match.id,
        "accepted_match_state",
        {
            "stateContinuityAppliedFrames": 1,
            "frames": [
                {
                    "frameId": 1,
                    "timestamp": 0.1,
                    "mode": "controlled_possession",
                    "controllingTeam": "my_team",
                    "controllingTrackId": 7,
                    "ballVisibility": "hidden",
                    "ballEstimate": None,
                    "source": "player_conditioned",
                    "confidence": 0.65,
                    "reasonCodes": ["player_conditioned"],
                },
                {
                    "frameId": 2,
                    "timestamp": 0.2,
                    "mode": "controlled_possession",
                    "controllingTeam": "enemy",
                    "controllingTrackId": 18,
                    "ballVisibility": "visible",
                    "ballEstimate": {"x": 10.0, "y": 20.0, "confidence": 0.8, "radius": 0.0},
                    "source": "observed_ball",
                    "confidence": 0.90,
                    "reasonCodes": ["accepted_ball", "observed_ball"],
                },
            ],
        },
    )
    storage.save_analysis_artifact(
        match.id,
        "runpod_transport_debug",
        {
            "requestedTransport": "auto",
            "resolvedTransport": "async",
            "usedObjectStorage": True,
            "initialRunId": "runpod-123",
            "pollCount": 4,
            "finalTerminalStatus": "COMPLETED",
            "transportTimedOut": False,
            "runtimeOutcome": "worker_compute_bottleneck",
            "stageDownloadSeconds": 0.25,
            "stageProcessVideoSeconds": 1.5,
            "stageReturnSeconds": 0.1,
            "workerStartedProcessing": True,
            "workerReturnedResult": True,
            "workerHeartbeatEnabled": True,
            "workerCurrentStage": "resultSerialize",
            "workerStageStatus": "started",
            "workerLastHeartbeatAt": "2026-04-12T02:30:00+00:00",
            "workerHeartbeatAgeSeconds": 0.25,
            "workerTrackingFramesSeen": 321,
            "workerBlockingStage": None,
            "workerProgress": {
                "workerStage": "resultSerialize",
                "stageStatus": "started",
                "heartbeatAt": "2026-04-12T02:30:00+00:00",
                "trackingFramesSeen": 321,
                "workerStartedProcessing": True,
                "workerReturnedResult": False,
            },
        },
    )
    storage.update_job(job.id, status="completed", progress=1.0, message="done", remote_run_id="runpod-123")
    storage.update_match_status(match.id, status="ready", requires_team_selection=True, team_clusters=[])

    summary = summarize_match_benchmark(storage, match.id)

    assert summary.matchId == match.id
    assert summary.jobId == job.id
    assert summary.jobStatus == "completed"
    assert summary.inputMode == "video"
    assert summary.matchStatus == "ready"
    assert summary.requiresTeamSelection is True
    assert summary.rawRowCount == 3
    assert summary.frameCount == 2
    assert summary.playerFrames == 1
    assert summary.withBallFrames == 1
    assert summary.withBallRatio == 0.5
    assert summary.trackedPossessionFrames == 2
    assert summary.trackedPossessionRatio == 1.0
    assert summary.controlledPossessionFrames == 2
    assert summary.controlledPossessionRatio == 1.0
    assert summary.eventCount == 3
    assert summary.eventTypes == {"pass": 2, "shot": 1}
    assert summary.eventFamilyCount == 2
    assert summary.dominantEventShare == 0.67
    assert summary.fiveMinuteTruthReady is False
    assert "Need at least 3 event families" in summary.truthGateReasons
    assert summary.shotCount == 1
    assert summary.ballSignalStatus == "untrusted"
    assert summary.recoveryProfileName == "edge_margin_40_upper_078"
    assert summary.recoveryApplied is True
    assert summary.recoveredSelectedFrames == 4
    assert summary.dominantAnchorCoord == [12.5, 19.5]
    assert summary.dominantAnchorCount == 3
    assert summary.dominantAnchorShare == 0.75
    assert summary.meanSourceCenterY == 173.33
    assert summary.meanSourceBoxArea == 800.0
    assert summary.candidateEdgeShare == 0.25
    assert summary.selectedEdgeFrameShare == 0.1
    assert summary.requestedTransport == "auto"
    assert summary.resolvedTransport == "async"
    assert summary.remoteRunId == "runpod-123"
    assert summary.usedObjectStorage is True
    assert summary.transportTimedOut is False
    assert summary.runtimeOutcome == "worker_compute_bottleneck"
    assert summary.stageDownloadSeconds == 0.25
    assert summary.stageProcessVideoSeconds == 1.5
    assert summary.stageReturnSeconds == 0.1
    assert summary.workerStartedProcessing is True
    assert summary.workerReturnedResult is True
    assert summary.workerHeartbeatEnabled is True
    assert summary.workerCurrentStage == "resultSerialize"
    assert summary.workerStageStatus == "started"
    assert summary.workerTrackingFramesSeen == 321
    assert summary.workerBlockingStage is None
    assert summary.workerHeartbeatAgeSeconds >= 0.0
    assert summary.acceptedMatchStateFrames == 2
    assert summary.acceptedMatchStateCoverageRatio == 1.0
    assert summary.visibleStateFrames == 1
    assert summary.inferredStateFrames == 0
    assert summary.hiddenStateFrames == 1
    assert summary.controlledStateFrames == 2
    assert summary.hiddenControlledStateFrames == 1
    assert summary.restartOrOutStateFrames == 0
    assert summary.stateContinuityAppliedFrames == 1
    assert summary.matchStateModeCounts == {"controlled_possession": 2}
    assert summary.artifactPresence == {
        "frames": True,
        "analytics": True,
        "events": True,
        "rawRows": True,
    }


def test_summarize_match_benchmark_includes_warm_proof_lifecycle_fields(tmp_path):
    storage = Storage(tmp_path)
    upload_path = storage.save_upload("clip.mp4", b"video")
    match = storage.create_match(
        name="warm-proof-demo",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=upload_path,
        config=MatchConfig(
            autoHomography=False,
            manualHomographyPoints=[
                HomographyPoint(x=0, y=0),
                HomographyPoint(x=100, y=0),
                HomographyPoint(x=100, y=100),
                HomographyPoint(x=0, y=100),
            ],
        ),
    )
    job = storage.create_job(match.id)
    storage.update_job(job.id, status="completed", progress=1.0, message="done", remote_run_id="runpod-123")
    storage.update_match_status(match.id, status="ready", requires_team_selection=False, team_clusters=[])
    storage.save_analysis_artifact(
        match.id,
        "endpoint_lifecycle_debug",
        {
            "templateId": "r4e1k0irw9",
            "endpointId": "endpoint-123",
            "gpuId": "NVIDIA H100 80GB HBM3",
            "workersMin": 1,
            "workersMax": 1,
            "createStartedAt": "2026-04-12T09:00:00+00:00",
            "createCompletedAt": "2026-04-12T09:00:05+00:00",
            "proofStartedAt": "2026-04-12T09:00:20+00:00",
            "proofFinishedAt": "2026-04-12T09:05:20+00:00",
            "deleteCompletedAt": "2026-04-12T09:05:30+00:00",
            "lifecycleOutcome": "completed",
            "warmProofMode": True,
            "warmReadyObserved": True,
            "warmupWaitSeconds": 15.0,
        },
    )

    summary = summarize_match_benchmark(storage, match.id)

    assert summary.warmProofMode is True
    assert summary.warmReadyObserved is True
    assert summary.warmupWaitSeconds == 15.0


def test_summarize_match_benchmark_handles_missing_artifacts(tmp_path):
    storage = Storage(tmp_path)
    upload_path = storage.save_upload("clip.mp4", b"video")
    match = storage.create_match(
        name="trimmed-demo",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=upload_path,
        config=MatchConfig(autoHomography=True),
    )
    job = storage.create_job(match.id)
    storage.update_job(job.id, status="failed", progress=1.0, message="no pitch", error="no pitch")
    storage.update_match_status(match.id, status="failed")

    summary = summarize_match_benchmark(storage, match.id)

    assert summary.jobId == job.id
    assert summary.jobStatus == "failed"
    assert summary.matchStatus == "failed"
    assert summary.rawRowCount == 0
    assert summary.frameCount == 0
    assert summary.withBallFrames == 0
    assert summary.withBallRatio == 0.0
    assert summary.trackedPossessionFrames == 0
    assert summary.trackedPossessionRatio == 0.0
    assert summary.controlledPossessionFrames == 0
    assert summary.controlledPossessionRatio == 0.0
    assert summary.eventCount == 0
    assert summary.eventTypes == {}
    assert summary.eventFamilyCount == 0
    assert summary.dominantEventShare == 0.0
    assert summary.fiveMinuteTruthReady is False
    assert summary.fortyFiveMinuteTruthReady is False
    assert summary.shotCount == 0
    assert summary.ballSignalStatus is None
    assert summary.recoveryProfileName is None
    assert summary.recoveryApplied is False
    assert summary.recoveredSelectedFrames == 0
    assert summary.dominantAnchorCoord is None
    assert summary.dominantAnchorCount == 0
    assert summary.dominantAnchorShare == 0.0
    assert summary.meanSourceCenterY == 0.0
    assert summary.meanSourceBoxArea == 0.0
    assert summary.candidateEdgeShare == 0.0
    assert summary.selectedEdgeFrameShare == 0.0
    assert summary.corridorCandidateFrames == 0
    assert summary.corridorFramesWithTwoAnchors == 0
    assert summary.corridorFramesWithSingleAnchor == 0
    assert summary.corridorMeanWidth == 0.0
    assert summary.collapsedCandidateFrames == 0
    assert summary.collapsedSegmentCount == 0
    assert summary.collapsedLongestSegmentFrames == 0
    assert summary.continuityPreferredFrames == 0
    assert summary.continuityRejectedFrames == 0
    assert summary.midfieldCollapsedFrames == 0
    assert summary.artifactPresence == {
        "frames": False,
        "analytics": False,
        "events": False,
        "rawRows": False,
    }


def test_summarize_match_benchmark_ignores_malformed_recovery_debug_values(tmp_path):
    storage = Storage(tmp_path)
    upload_path = storage.save_upload("clip.mp4", b"video")
    match = storage.create_match(
        name="trimmed-demo",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=upload_path,
        config=MatchConfig(autoHomography=True),
    )
    job = storage.create_job(match.id)
    storage.update_job(job.id, status="completed", progress=1.0, message="done")
    storage.save_analysis_artifact(
        match.id,
        "recovery_debug",
        {
            "primaryBallFrames": "abc",
            "recoveryAttempted": ["not", "a", "bool"],
            "recoveryProfileName": ["bad", "type"],
            "recoveredSelectedFrames": None,
            "dominantAnchorCoord": ["bad", None],
            "dominantAnchorCount": "abc",
            "dominantAnchorShare": ["nope"],
            "meanSourceCenterY": None,
            "meanSourceBoxArea": {"bad": "type"},
            "corridorCandidateFrames": "abc",
            "corridorFramesWithTwoAnchors": "abc",
            "corridorFramesWithSingleAnchor": "abc",
            "corridorMeanWidth": "abc",
            "proposalCandidateFrames": "abc",
            "proposalWindowCount": "abc",
            "proposalFramesWithAnchorSeed": "abc",
            "proposalFramesWithoutAnchorSeed": "abc",
            "proposalMeanWindowWidth": "abc",
            "candidateEdgeShare": "abc",
            "selectedEdgeFrameShare": ["still", "bad"],
        },
    )

    summary = summarize_match_benchmark(storage, match.id)

    assert summary.recoveryProfileName is None
    assert summary.recoveryApplied is False
    assert summary.recoveredSelectedFrames == 0
    assert summary.dominantAnchorCoord is None
    assert summary.dominantAnchorCount == 0
    assert summary.dominantAnchorShare == 0.0
    assert summary.meanSourceCenterY == 0.0
    assert summary.meanSourceBoxArea == 0.0
    assert summary.corridorCandidateFrames == 0
    assert summary.corridorFramesWithTwoAnchors == 0
    assert summary.corridorFramesWithSingleAnchor == 0
    assert summary.corridorMeanWidth == 0.0
    assert summary.proposalCandidateFrames == 0
    assert summary.proposalWindowCount == 0
    assert summary.proposalFramesWithAnchorSeed == 0
    assert summary.proposalFramesWithoutAnchorSeed == 0
    assert summary.proposalMeanWindowWidth == 0.0
    assert summary.candidateEdgeShare == 0.0
    assert summary.selectedEdgeFrameShare == 0.0


def test_summarize_match_benchmark_ignores_malformed_recovery_debug_file(tmp_path):
    storage = Storage(tmp_path)
    upload_path = storage.save_upload("clip.mp4", b"video")
    match = storage.create_match(
        name="trimmed-demo",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=upload_path,
        config=MatchConfig(autoHomography=True),
    )
    job = storage.create_job(match.id)
    storage.update_job(job.id, status="completed", progress=1.0, message="done")
    (storage._match_dir(match.id) / "recovery_debug.json").write_text("{not-json", encoding="utf-8")

    summary = summarize_match_benchmark(storage, match.id)

    assert summary.recoveryProfileName is None
    assert summary.recoveryApplied is False
    assert summary.recoveredSelectedFrames == 0
    assert summary.corridorCandidateFrames == 0
    assert summary.proposalCandidateFrames == 0
    assert summary.collapsedCandidateFrames == 0
    assert summary.candidateEdgeShare == 0.0
    assert summary.selectedEdgeFrameShare == 0.0


def test_summarize_match_benchmark_sets_truth_readiness_when_objective_gates_pass(tmp_path):
    storage = Storage(tmp_path)
    upload_path = storage.save_upload("clip.mp4", b"video")
    match = storage.create_match(
        name="benchmark-ready",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=upload_path,
        config=MatchConfig(autoHomography=True),
    )
    job = storage.create_job(match.id)
    storage.update_job(job.id, status="completed", progress=1.0, message="done")
    storage.save_raw_rows(match.id, [{"Frame_ID": index} for index in range(300)])
    storage.save_frames(
        match.id,
        [
            FrameData(
                frameId=index,
                timestamp=index * 0.2,
                ball={
                    "x": 20 + (index % 60) * 0.5,
                    "y": 40 + (index % 20) * 0.2,
                    "confidence": 0.8,
                },
            )
            for index in range(300)
        ],
    )
    storage.save_analytics(
        match.id,
        _summary(),
        assignments=[
            BallOwnership(frameId=index, timestamp=index * 0.2, team="my_team", trackId=7, distance=1.0)
            for index in range(150)
        ]
        + [
            BallOwnership(frameId=index + 150, timestamp=(index + 150) * 0.2, team="enemy", trackId=18, distance=1.2)
            for index in range(130)
        ]
        + [
            BallOwnership(frameId=index + 280, timestamp=(index + 280) * 0.2, team="dead_ball", trackId=None, distance=None)
            for index in range(20)
        ],
        formation_timeline=[],
        shots=[],
    )
    storage.save_events(
        match.id,
        [
            DetectedEvent(type="pass", frameId=1, timestamp=0.1, team="my_team", fromTrackId=7, toTrackId=8, description="pass"),
            DetectedEvent(type="turnover", frameId=2, timestamp=0.2, team="enemy", fromTrackId=8, toTrackId=18, description="turnover"),
            DetectedEvent(type="interception", frameId=3, timestamp=0.3, team="enemy", fromTrackId=7, toTrackId=18, description="interception"),
        ],
    )
    storage.update_match_status(match.id, status="ready", requires_team_selection=False, team_clusters=[])

    summary = summarize_match_benchmark(storage, match.id)

    assert summary.frameCount == 300
    assert summary.rawRowCount == 300
    assert summary.withBallFrames == 300
    assert summary.withBallRatio == 1.0
    assert summary.trackedPossessionFrames == 280
    assert summary.trackedPossessionRatio == 280 / 300
    assert summary.controlledPossessionFrames == 280
    assert summary.controlledPossessionRatio == 280 / 300
    assert summary.ballTrackEdgeFrameShare == 0.0
    assert summary.ballTrackShowsMeaningfulMotion is True
    assert summary.ballTrackViable is True
    assert summary.eventFamilyCount == 3
    assert summary.dominantEventShare == 0.33
    assert summary.fiveMinuteTruthReady is True
    assert summary.fortyFiveMinuteTruthReady is True
    assert summary.truthGateReasons == []


def test_summarize_match_benchmark_rejects_edge_hugging_ball_track_even_when_coverage_is_high(tmp_path):
    storage = Storage(tmp_path)
    upload_path = storage.save_upload("clip.mp4", b"video")
    match = storage.create_match(
        name="benchmark-edge-ball",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=upload_path,
        config=MatchConfig(autoHomography=True),
    )
    storage.update_job(storage.create_job(match.id).id, status="completed", progress=1.0, message="done")
    storage.save_raw_rows(match.id, [{"Frame_ID": index} for index in range(300)])
    storage.save_frames(
        match.id,
        [
            FrameData(
                frameId=index,
                timestamp=index * 0.2,
                ball={"x": 3.0, "y": 20 + (index % 50) * 0.4, "confidence": 0.8},
            )
            for index in range(300)
        ],
    )
    storage.save_analytics(
        match.id,
        _summary(),
        assignments=[
            BallOwnership(frameId=index, timestamp=index * 0.2, team="my_team", trackId=7, distance=1.0)
            for index in range(150)
        ]
        + [
            BallOwnership(frameId=index + 150, timestamp=(index + 150) * 0.2, team="enemy", trackId=18, distance=1.2)
            for index in range(150)
        ],
        formation_timeline=[],
        shots=[],
    )
    storage.save_events(
        match.id,
        [
            DetectedEvent(type="pass", frameId=1, timestamp=0.1, team="my_team", fromTrackId=7, toTrackId=8, description="pass"),
            DetectedEvent(type="turnover", frameId=2, timestamp=0.2, team="enemy", fromTrackId=8, toTrackId=18, description="turnover"),
            DetectedEvent(type="interception", frameId=3, timestamp=0.3, team="enemy", fromTrackId=7, toTrackId=18, description="interception"),
        ],
    )
    storage.update_match_status(match.id, status="ready", requires_team_selection=False, team_clusters=[])

    summary = summarize_match_benchmark(storage, match.id)

    assert summary.withBallRatio == 1.0
    assert summary.ballTrackEdgeFrameShare == 1.0
    assert summary.ballTrackShowsMeaningfulMotion is True
    assert summary.ballTrackViable is False
    assert summary.fiveMinuteTruthReady is False
    assert "Need viable ball track: meaningful motion and edgeFrameShare <= 60%" in summary.truthGateReasons


def test_summarize_match_benchmark_rejects_short_time_samples_even_when_raw_detections_are_dense(tmp_path):
    storage = Storage(tmp_path)
    upload_path = storage.save_upload("clip.mp4", b"video")
    match = storage.create_match(
        name="benchmark-short-clip",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=upload_path,
        config=MatchConfig(autoHomography=True),
    )
    job = storage.create_job(match.id)
    storage.update_job(job.id, status="completed", progress=1.0, message="done")
    storage.save_raw_rows(match.id, [{"Frame_ID": index} for index in range(1000)])
    storage.save_frames(
        match.id,
        [
            FrameData(
                frameId=index,
                timestamp=index * 0.2,
                ball={"x": 20 + (index * 0.5), "y": 30 + (index * 0.2), "confidence": 0.8},
            )
            for index in range(10)
        ],
    )
    storage.save_analytics(
        match.id,
        _summary(),
        assignments=[
            BallOwnership(frameId=index, timestamp=index * 0.2, team="my_team", trackId=7, distance=1.0)
            for index in range(10)
        ],
        formation_timeline=[],
        shots=[],
    )
    storage.save_events(
        match.id,
        [
            DetectedEvent(type="pass", frameId=1, timestamp=0.1, team="my_team", fromTrackId=7, toTrackId=8, description="pass"),
            DetectedEvent(type="turnover", frameId=2, timestamp=0.2, team="enemy", fromTrackId=8, toTrackId=18, description="turnover"),
            DetectedEvent(type="interception", frameId=3, timestamp=0.3, team="enemy", fromTrackId=7, toTrackId=18, description="interception"),
        ],
    )
    storage.update_match_status(match.id, status="ready", requires_team_selection=False, team_clusters=[])
    storage.save_analysis_artifact(
        match.id,
        "recovery_debug",
        {
            "recoveryProfileName": "baseline_player_window",
            "recoveryApplied": True,
            "recoveredSelectedFrames": 4,
            "dominantAnchorCoord": [12.5, 19.5],
            "dominantAnchorCount": 3,
            "dominantAnchorShare": 0.75,
            "meanSourceCenterY": 173.33,
            "meanSourceBoxArea": 800.0,
            "recoveredSupportedFrames": 5,
            "recoveredAnchoredFrames": 4,
            "recoveredBridgeFrames": 2,
            "recoveredUnsupportedEdgeFrameShare": 0.25,
            "recoveredAnchoredPathLength": 18.5,
                "corridorCandidateFrames": 6,
                "corridorFramesWithTwoAnchors": 4,
                "corridorFramesWithSingleAnchor": 2,
                "corridorMeanWidth": 11.5,
                "proposalCandidateFrames": 11,
                "proposalWindowCount": 4,
                "proposalFramesWithAnchorSeed": 7,
                "proposalFramesWithoutAnchorSeed": 4,
                "proposalExactSeedFrames": 2,
                "proposalInterpolatedSeedFrames": 3,
                "proposalSingleSeedFrames": 2,
                "proposalUnseededFrames": 4,
                "proposalMeanWindowWidth": 13.5,
                "collapsedCandidateFrames": 8,
            "collapsedSegmentCount": 2,
            "collapsedLongestSegmentFrames": 5,
            "continuityPreferredFrames": 3,
            "continuityRejectedFrames": 6,
            "midfieldCollapsedFrames": 7,
            "candidateEdgeShare": 0.25,
            "selectedEdgeFrameShare": 0.1,
        },
    )
    storage.save_analysis_artifact(
        match.id,
        "recovery_profile_matrix",
        {
            "selectedProfileName": "baseline_player_window",
            "profiles": [
                {
                    "name": "baseline_player_window",
                    "cropMode": "player_window",
                    "viable": True,
                    "candidateFrames": 8,
                    "selectedFrames": 4,
                    "candidateSegmentCount": 2,
                    "selectedSegmentCount": 1,
                    "corridorCandidateFrames": 6,
                    "corridorFramesWithTwoAnchors": 4,
                    "corridorFramesWithSingleAnchor": 2,
                    "corridorMeanWidth": 11.5,
                    "proposalCandidateFrames": 11,
                    "proposalWindowCount": 4,
                    "proposalFramesWithAnchorSeed": 7,
                    "proposalFramesWithoutAnchorSeed": 4,
                    "proposalExactSeedFrames": 2,
                    "proposalInterpolatedSeedFrames": 3,
                    "proposalSingleSeedFrames": 2,
                    "proposalUnseededFrames": 4,
                    "proposalMeanWindowWidth": 13.5,
                },
                {
                    "name": "proposal_windows_075",
                    "cropMode": "proposal_windows",
                    "viable": True,
                    "candidateFrames": 14,
                    "selectedFrames": 6,
                    "candidateSegmentCount": 3,
                    "selectedSegmentCount": 2,
                    "corridorCandidateFrames": 0,
                    "corridorFramesWithTwoAnchors": 0,
                    "corridorFramesWithSingleAnchor": 0,
                    "corridorMeanWidth": 0.0,
                    "proposalCandidateFrames": 18,
                    "proposalWindowCount": 6,
                    "proposalFramesWithAnchorSeed": 10,
                    "proposalFramesWithoutAnchorSeed": 2,
                    "proposalExactSeedFrames": 4,
                    "proposalInterpolatedSeedFrames": 4,
                    "proposalSingleSeedFrames": 2,
                    "proposalUnseededFrames": 2,
                    "proposalMeanWindowWidth": 12.25,
                    "proposalDirectSeedWindowFrames": 6,
                    "proposalDirectSeedTightWindowFrames": 4,
                    "proposalDirectSeedContextWindowFrames": 2,
                    "proposalDirectSeedContextEligibleFrames": 5,
                    "proposalDirectSeedContextDuplicateFrames": 1,
                    "proposalDirectSeedContextMeanSeedToBoxDistance": 17.5,
                    "proposalDirectSeedContextExpandedFrames": 2,
                    "proposalDirectSeedContextMeanExpansionPx": 11.5,
                    "proposalPlayerRankedWindowFrames": 6,
                    "proposalRawDetectedFrames": 22,
                    "proposalAfterSeedCollapseFrames": 18,
                    "proposalAfterPlayerWindowFrames": 14,
                    "proposalAfterFalseBallSuppressionFrames": 11,
                    "proposalCollapsedFrames": 9,
                    "proposalCollapsedSegmentCount": 3,
                    "proposalDirectSeedDetectedFrames": 7,
                    "proposalDirectSeedTightDetectedFrames": 3,
                    "proposalDirectSeedContextDetectedFrames": 4,
                    "proposalDirectSeedHiResRetryFrames": 2,
                    "proposalDirectSeedHiResRetryDetectedFrames": 1,
                    "proposalDirectSeedZeroDetectFrames": 5,
                    "proposalDirectSeedScale1600RawDetectionFrames": 4,
                    "proposalDirectSeedScale960RawDetectionFrames": 2,
                    "proposalDirectSeedScale1920RawDetectionFrames": 1,
                    "proposalDirectSeedScale1600CandidateFrames": 3,
                    "proposalDirectSeedScale960CandidateFrames": 1,
                    "proposalDirectSeedScale1920CandidateFrames": 1,
                    "proposalDirectSeedMultiScaleRetryFrames": 3,
                    "proposalDirectSeedMultiScaleDetectedFrames": 2,
                    "proposalDirectSeedRawHitFilteredOutFrames": 2,
                    "proposalDirectSeedCropEdgeRejectedFrames": 1,
                    "proposalDirectSeedCropCenterYRejectedFrames": 2,
                    "proposalDirectSeedPitchPolygonRejectedFrames": 1,
                    "proposalDirectSeedMeanCropArea": 1500.0,
                    "proposalDirectSeedTightMeanCropArea": 1300.0,
                    "proposalDirectSeedContextMeanCropArea": 1700.0,
                    "proposalPlayerRankedMeanCropArea": 2100.0,
                    "proposalDirectSeedMeanDetectedBallBoxArea": 42.0,
                    "proposalPlayerRankedMeanDetectedBallBoxArea": 75.0,
                    "proposalPlayerRankedDetectedFrames": 15,
                    "proposalExactSeedDetectedFrames": 9,
                    "proposalInterpolatedSeedDetectedFrames": 8,
                    "proposalSingleSeedDetectedFrames": 5,
                },
            ],
        },
    )
    storage.save_analysis_artifact(
        match.id,
        "ball_truth_layers",
        {
            "sampleInterval": 5,
            "observedBall": {
                "rows": [
                    {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 20.0, "Y": 30.0, "Conf": 0.8},
                    {"Frame_ID": 5, "Entity_Type": "ball", "Track_ID": -1, "X": 22.5, "Y": 31.0, "Conf": 0.8},
                ],
                "summary": {
                    "rowCount": 2,
                    "frameCount": 2,
                    "pathLength": 2.69,
                    "edgeFrameShare": 0.0,
                    "segmentCount": 1,
                    "firstFrame": 0,
                    "lastFrame": 5,
                },
            },
            "inferredBall": {
                "rows": [
                    {"Frame_ID": 10, "Entity_Type": "ball", "Track_ID": -1, "X": 25.0, "Y": 32.0, "Conf": 0.7},
                    {"Frame_ID": 15, "Entity_Type": "ball", "Track_ID": -1, "X": 27.5, "Y": 33.0, "Conf": 0.7},
                    {"Frame_ID": 20, "Entity_Type": "ball", "Track_ID": -1, "X": 30.0, "Y": 34.0, "Conf": 0.7},
                ],
                "summary": {
                    "rowCount": 3,
                    "frameCount": 3,
                    "pathLength": 5.39,
                    "edgeFrameShare": 0.0,
                    "segmentCount": 1,
                    "firstFrame": 10,
                    "lastFrame": 20,
                },
            },
            "acceptedBall": {
                "rows": [
                    {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 20.0, "Y": 30.0, "Conf": 0.8},
                    {"Frame_ID": 1, "Entity_Type": "ball", "Track_ID": -1, "X": 20.5, "Y": 30.2, "Conf": 0.8},
                    {"Frame_ID": 2, "Entity_Type": "ball", "Track_ID": -1, "X": 21.0, "Y": 30.4, "Conf": 0.8},
                    {"Frame_ID": 3, "Entity_Type": "ball", "Track_ID": -1, "X": 21.5, "Y": 30.6, "Conf": 0.8},
                    {"Frame_ID": 4, "Entity_Type": "ball", "Track_ID": -1, "X": 22.0, "Y": 30.8, "Conf": 0.8},
                    {"Frame_ID": 5, "Entity_Type": "ball", "Track_ID": -1, "X": 22.5, "Y": 31.0, "Conf": 0.8},
                    {"Frame_ID": 6, "Entity_Type": "ball", "Track_ID": -1, "X": 23.0, "Y": 31.2, "Conf": 0.8},
                    {"Frame_ID": 7, "Entity_Type": "ball", "Track_ID": -1, "X": 23.5, "Y": 31.4, "Conf": 0.8},
                    {"Frame_ID": 8, "Entity_Type": "ball", "Track_ID": -1, "X": 24.0, "Y": 31.6, "Conf": 0.8},
                    {"Frame_ID": 9, "Entity_Type": "ball", "Track_ID": -1, "X": 24.5, "Y": 31.8, "Conf": 0.8},
                ],
                "summary": {
                    "rowCount": 10,
                    "frameCount": 10,
                    "pathLength": 5.5,
                    "edgeFrameShare": 0.0,
                    "segmentCount": 1,
                    "firstFrame": 0,
                    "lastFrame": 9,
                },
            },
            "acceptedSegments": [
                {"startFrame": 0, "endFrame": 9, "frameCount": 10, "source": "mixed"},
            ],
            "unknownGaps": [],
            "acceptedSourceBreakdown": {"observed": 2, "inferred": 8},
            "directObservationBreakdown": {
                "trackingObservedBallFrames": 2,
                "rawProbeObservedBallFrames": 4,
                "filteredProbeObservedBallFrames": 3,
                "suppressedProbeObservedBallFrames": 1,
                "anchoredProbeObservedBallFrames": 2,
                "bridgeProbeObservedBallFrames": 1,
                "probeObservedBallFrames": 3,
                "probeOnlyObservedBallFrames": 2,
                "acceptedFromObservedFrames": 2,
                "acceptedFromObservedRatio": 0.2,
            },
            "supportDiagnostics": {
                "supportedObservedBallFrames": 1,
                "supportedAcceptedBallFrames": 6,
                "supportedAcceptedBallRatio": 0.6,
                "unsupportedAcceptedEdgeFrames": 2,
            },
            "recoveredSupportedFrames": 5,
            "recoveredAnchoredFrames": 4,
            "recoveredBridgeFrames": 2,
            "recoveredUnsupportedEdgeFrameShare": 0.25,
            "recoveredAnchoredPathLength": 18.5,
            "collapsedCandidateFrames": 8,
            "collapsedSegmentCount": 2,
            "collapsedLongestSegmentFrames": 5,
            "continuityPreferredFrames": 3,
            "continuityRejectedFrames": 6,
            "midfieldCollapsedFrames": 7,
        },
    )
    storage.save_analysis_artifact(
        match.id,
        "ball_pipeline_trace",
        {
            "detectorModelPath": "yolo11s.pt",
            "detectorModelName": "yolo11s.pt",
            "directSeedRetryPolicy": "bounded_multiscale_fallback",
            "directSeedRetryScales": [1600, 960, 1920],
            "stages": [],
        },
    )

    summary = summarize_match_benchmark(storage, match.id)

    assert summary.frameCount == 10
    assert summary.rawRowCount == 1000
    assert summary.withBallFrames == 10
    assert summary.withBallRatio == 1.0
    assert summary.observedBallFrames == 2
    assert summary.inferredBallFrames == 3
    assert summary.acceptedBallFrames == 10
    assert summary.acceptedBallRatio == 1.0
    assert summary.acceptedSegmentCount == 1
    assert summary.unknownGapCount == 0
    assert summary.longestUnknownGapFrames == 0
    assert summary.trackingObservedBallFrames == 2
    assert summary.rawProbeObservedBallFrames == 4
    assert summary.filteredProbeObservedBallFrames == 3
    assert summary.suppressedProbeObservedBallFrames == 1
    assert summary.anchoredProbeObservedBallFrames == 2
    assert summary.bridgeProbeObservedBallFrames == 1
    assert summary.probeObservedBallFrames == 3
    assert summary.probeOnlyObservedBallFrames == 2
    assert summary.acceptedFromObservedFrames == 2
    assert summary.acceptedFromObservedRatio == 0.2
    assert summary.supportedObservedBallFrames == 1
    assert summary.supportedAcceptedBallFrames == 6
    assert summary.supportedAcceptedBallRatio == 0.6
    assert summary.unsupportedAcceptedEdgeFrames == 2
    assert summary.recoveredSupportedFrames == 5
    assert summary.recoveredAnchoredFrames == 4
    assert summary.recoveredBridgeFrames == 2
    assert summary.recoveredUnsupportedEdgeFrameShare == 0.25
    assert summary.recoveredAnchoredPathLength == 18.5
    assert summary.corridorCandidateFrames == 6
    assert summary.corridorFramesWithTwoAnchors == 4
    assert summary.corridorFramesWithSingleAnchor == 2
    assert summary.corridorMeanWidth == 11.5
    assert summary.proposalCandidateFrames == 11
    assert summary.proposalWindowCount == 4
    assert summary.proposalFramesWithAnchorSeed == 7
    assert summary.proposalFramesWithoutAnchorSeed == 4
    assert summary.proposalExactSeedFrames == 2
    assert summary.proposalInterpolatedSeedFrames == 3
    assert summary.proposalSingleSeedFrames == 2
    assert summary.proposalUnseededFrames == 4
    assert summary.proposalMeanWindowWidth == 13.5
    assert summary.bestProposalRawDetectedFrames == 22
    assert summary.bestProposalAfterSeedCollapseFrames == 18
    assert summary.bestProposalAfterFalseBallSuppressionFrames == 11
    assert summary.bestProposalDirectSeedDetectedFrames == 7
    assert summary.bestProposalDirectSeedTightDetectedFrames == 3
    assert summary.bestProposalDirectSeedContextDetectedFrames == 4
    assert summary.bestProposalDirectSeedHiResRetryFrames == 2
    assert summary.bestProposalDirectSeedHiResRetryDetectedFrames == 1
    assert summary.bestProposalDirectSeedZeroDetectFrames == 5
    assert summary.bestProposalDirectSeedScale1600RawDetectionFrames == 4
    assert summary.bestProposalDirectSeedScale960RawDetectionFrames == 2
    assert summary.bestProposalDirectSeedScale1920RawDetectionFrames == 1
    assert summary.bestProposalDirectSeedScale1600CandidateFrames == 3
    assert summary.bestProposalDirectSeedScale960CandidateFrames == 1
    assert summary.bestProposalDirectSeedScale1920CandidateFrames == 1
    assert summary.bestProposalDirectSeedMultiScaleRetryFrames == 3
    assert summary.bestProposalDirectSeedMultiScaleDetectedFrames == 2
    assert summary.bestProposalDirectSeedRawHitFilteredOutFrames == 2
    assert summary.bestProposalDirectSeedCropEdgeRejectedFrames == 1
    assert summary.bestProposalDirectSeedCropCenterYRejectedFrames == 2
    assert summary.bestProposalDirectSeedPitchPolygonRejectedFrames == 1
    assert summary.bestProposalDirectSeedMeanCropArea == 1500.0
    assert summary.bestProposalDirectSeedTightMeanCropArea == 1300.0
    assert summary.bestProposalDirectSeedContextMeanCropArea == 1700.0
    assert summary.bestProposalPlayerRankedMeanCropArea == 2100.0
    assert summary.bestProposalDirectSeedMeanDetectedBallBoxArea == 42.0
    assert summary.bestProposalPlayerRankedMeanDetectedBallBoxArea == 75.0
    assert summary.bestProposalDirectSeedContextWindowFrames == 2
    assert summary.bestProposalDirectSeedContextEligibleFrames == 5
    assert summary.bestProposalDirectSeedContextMeanSeedToBoxDistance == 17.5
    assert summary.bestProposalDirectSeedContextExpandedFrames == 2
    assert summary.bestProposalDirectSeedContextMeanExpansionPx == 11.5
    assert summary.bestProposalPlayerRankedDetectedFrames == 15
    assert summary.bestProposalExactSeedDetectedFrames == 9
    assert summary.bestProposalInterpolatedSeedDetectedFrames == 8
    assert summary.bestProposalSingleSeedDetectedFrames == 5
    assert summary.bestProposalProfileName == "proposal_windows_075"
    assert summary.bestProposalCandidateFrames == 18
    assert summary.bestProposalSelectedFrames == 6
    assert summary.bestProposalViable is True
    assert summary.collapsedCandidateFrames == 8
    assert summary.collapsedSegmentCount == 2
    assert summary.collapsedLongestSegmentFrames == 5
    assert summary.continuityPreferredFrames == 3
    assert summary.continuityRejectedFrames == 6
    assert summary.midfieldCollapsedFrames == 7
    assert summary.trackedPossessionFrames == 10
    assert summary.trackedPossessionRatio == 1.0
    assert summary.controlledPossessionFrames == 10
    assert summary.controlledPossessionRatio == 1.0
    assert summary.eventFamilyCount == 3
    assert summary.dominantEventShare == 0.33
    assert summary.fiveMinuteTruthReady is False
    assert summary.fortyFiveMinuteTruthReady is False
    assert "Need at least 60 frame time samples for truthful 5-minute analysis" in summary.truthGateReasons
    assert "Direct observed ball remains too sparse for truthful 5-10 minute analysis" in summary.truthGateReasons
    assert summary.detectorModelPath == "yolo11s.pt"
    assert summary.detectorModelName == "yolo11s.pt"
    assert summary.directSeedRetryPolicy == "bounded_multiscale_fallback"
    assert summary.directSeedRetryScales == [1600, 960, 1920]


def test_summarize_match_benchmark_uses_accepted_ball_layer_for_viability_when_truth_layers_exist(tmp_path):
    storage = Storage(tmp_path)
    upload_path = storage.save_upload("clip.mp4", b"video")
    match = storage.create_match(
        name="benchmark-accepted-viability",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=upload_path,
        config=MatchConfig(autoHomography=True),
    )
    storage.update_job(storage.create_job(match.id).id, status="completed", progress=1.0, message="done")
    storage.save_raw_rows(match.id, [{"Frame_ID": index} for index in range(100)])
    storage.save_frames(
        match.id,
        [
            FrameData(
                frameId=index,
                timestamp=index * 0.2,
                ball={"x": 3.0, "y": 20 + (index % 50) * 0.4, "confidence": 0.8},
            )
            for index in range(100)
        ],
    )
    storage.save_analytics(
        match.id,
        _summary(),
        assignments=[
            BallOwnership(frameId=index, timestamp=index * 0.2, team="my_team", trackId=7, distance=1.0)
            for index in range(50)
        ]
        + [
            BallOwnership(frameId=index + 50, timestamp=(index + 50) * 0.2, team="enemy", trackId=18, distance=1.2)
            for index in range(50)
        ],
        formation_timeline=[],
        shots=[],
    )
    storage.save_events(
        match.id,
        [
            DetectedEvent(type="pass", frameId=1, timestamp=0.1, team="my_team", fromTrackId=7, toTrackId=8, description="pass"),
            DetectedEvent(type="turnover", frameId=2, timestamp=0.2, team="enemy", fromTrackId=8, toTrackId=18, description="turnover"),
            DetectedEvent(type="interception", frameId=3, timestamp=0.3, team="enemy", fromTrackId=7, toTrackId=18, description="interception"),
        ],
    )
    storage.update_match_status(match.id, status="ready", requires_team_selection=False, team_clusters=[])
    storage.save_analysis_artifact(
        match.id,
        "ball_truth_layers",
        {
            "sampleInterval": 1,
            "observedBall": {
                "rows": [
                    {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 3.0, "Y": 20.0, "Conf": 0.8},
                ],
                "summary": {
                    "rowCount": 1,
                    "frameCount": 1,
                    "pathLength": 0.0,
                    "edgeFrameShare": 1.0,
                    "segmentCount": 1,
                    "firstFrame": 0,
                    "lastFrame": 0,
                },
            },
            "inferredBall": {
                "rows": [],
                "summary": {
                    "rowCount": 0,
                    "frameCount": 0,
                    "pathLength": 0.0,
                    "edgeFrameShare": 0.0,
                    "segmentCount": 0,
                    "firstFrame": None,
                    "lastFrame": None,
                },
            },
            "acceptedBall": {
                "rows": [
                    {"Frame_ID": index, "Entity_Type": "ball", "Track_ID": -1, "X": 20.0 + (index * 0.5), "Y": 30.0 + (index * 0.2), "Conf": 0.8}
                    for index in range(100)
                ],
                "summary": {
                    "rowCount": 100,
                    "frameCount": 100,
                    "pathLength": 54.95,
                    "edgeFrameShare": 0.0,
                    "segmentCount": 1,
                    "firstFrame": 0,
                    "lastFrame": 99,
                },
            },
            "acceptedSegments": [
                {"startFrame": 0, "endFrame": 99, "frameCount": 100, "source": "mixed"},
            ],
            "unknownGaps": [],
        },
    )

    summary = summarize_match_benchmark(storage, match.id)

    assert summary.frameCount == 100
    assert summary.ballTrackEdgeFrameShare == 0.0
    assert summary.ballTrackShowsMeaningfulMotion is True
    assert summary.ballTrackViable is True
    assert summary.fiveMinuteTruthReady is True
    assert summary.truthGateReasons == []


def test_summarize_match_benchmark_reports_provisional_tracked_control_when_team_selection_is_unresolved(tmp_path):
    storage = Storage(tmp_path)
    upload_path = storage.save_upload("clip.mp4", b"video")
    match = storage.create_match(
        name="benchmark-unresolved",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=upload_path,
        config=MatchConfig(autoHomography=True),
    )
    job = storage.create_job(match.id)
    storage.update_job(job.id, status="completed", progress=1.0, message="done")
    storage.save_frames(
        match.id,
        [
            FrameData(frameId=index, timestamp=index * 0.2, ball={"x": 10 + index, "y": 20, "confidence": 0.8})
            for index in range(4)
        ],
    )
    storage.save_analytics(
        match.id,
        _summary(),
        assignments=[
            BallOwnership(frameId=index, timestamp=index * 0.2, team="unassigned", trackId=9, distance=1.0)
            for index in range(4)
        ],
        formation_timeline=[],
        shots=[],
    )
    storage.save_events(
        match.id,
        [DetectedEvent(type="recovery", frameId=1, timestamp=0.2, team="unassigned", toTrackId=9, description="recovery")],
    )
    storage.update_match_status(match.id, status="ready", requires_team_selection=True, team_clusters=[])

    summary = summarize_match_benchmark(storage, match.id)

    assert summary.trackedPossessionFrames == 4
    assert summary.trackedPossessionRatio == 1.0
    assert summary.controlledPossessionFrames == 0
    assert summary.controlledPossessionRatio == 0.0
    assert summary.fiveMinuteTruthReady is False
    assert "Team selection unresolved; controlled possession is provisional until myTeamCluster is chosen" in summary.truthGateReasons


def test_summarize_match_benchmark_includes_detector_model_provenance(tmp_path):
    storage = Storage(tmp_path)
    upload_path = storage.save_upload("clip.mp4", b"video")
    match = storage.create_match(
        name="benchmark-detector-model",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=upload_path,
        config=MatchConfig(autoHomography=True),
    )
    job = storage.create_job(match.id)
    storage.update_job(job.id, status="completed", progress=1.0, message="done")
    storage.save_frames(match.id, [FrameData(frameId=0, timestamp=0.0)])
    storage.save_analytics(match.id, _summary(), assignments=[], formation_timeline=[], shots=[])
    storage.save_events(match.id, [])
    storage.save_analysis_artifact(
        match.id,
        "ball_pipeline_trace",
        {
            "traceVersion": 1,
            "matchId": match.id,
            "jobId": job.id,
            "processingBackend": "local",
            "inputMode": "video",
            "videoPath": str(upload_path),
            "workerPath": "local",
            "detectorModelPath": "/workspace/weights/yolo11s.pt",
            "detectorModelName": "yolo11s.pt",
            "stages": [],
        },
    )

    summary = summarize_match_benchmark(storage, match.id)

    assert summary.detectorModelPath == "/workspace/weights/yolo11s.pt"
    assert summary.detectorModelName == "yolo11s.pt"


def test_probe_selected_cluster_benchmarks_summarizes_each_cluster_and_restores_config(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    upload_path = storage.save_upload("clip.mp4", b"video")
    match = storage.create_match(
        name="benchmark-cluster-probe",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=upload_path,
        config=MatchConfig(autoHomography=True),
    )
    storage.save_raw_rows(match.id, [{"Frame_ID": index} for index in range(10)])
    storage.save_frames(
        match.id,
        [
            FrameData(frameId=index, timestamp=index * 0.2, ball={"x": 10 + index, "y": 20, "confidence": 0.8})
            for index in range(10)
        ],
    )
    storage.save_analytics(
        match.id,
        _summary(),
        assignments=[BallOwnership(frameId=index, timestamp=index * 0.2, team="unassigned", trackId=7, distance=1.0) for index in range(10)],
        formation_timeline=[],
        shots=[],
    )
    storage.save_events(
        match.id,
        [DetectedEvent(type="recovery", frameId=1, timestamp=0.2, team="unassigned", toTrackId=7, description="recovery")],
    )
    storage.save_analysis_artifact(
        match.id,
        "recovery_debug",
        {
            "proposalCandidateFrames": 11,
            "proposalWindowCount": 4,
            "proposalFramesWithAnchorSeed": 7,
            "proposalFramesWithoutAnchorSeed": 4,
            "proposalMeanWindowWidth": 13.5,
        },
    )
    storage.save_analysis_artifact(
        match.id,
        "recovery_profile_matrix",
        {
            "selectedProfileName": "baseline_player_window",
            "profiles": [
                {
                    "name": "baseline_player_window",
                    "cropMode": "player_window",
                    "viable": True,
                    "candidateFrames": 8,
                    "selectedFrames": 4,
                    "proposalCandidateFrames": 11,
                    "proposalWindowCount": 4,
                    "proposalFramesWithAnchorSeed": 7,
                    "proposalFramesWithoutAnchorSeed": 4,
                    "proposalExactSeedFrames": 2,
                    "proposalInterpolatedSeedFrames": 3,
                    "proposalSingleSeedFrames": 2,
                    "proposalUnseededFrames": 4,
                    "proposalMeanWindowWidth": 13.5,
                },
                {
                    "name": "proposal_windows_075",
                    "cropMode": "proposal_windows",
                    "viable": True,
                    "candidateFrames": 14,
                    "selectedFrames": 6,
                    "proposalCandidateFrames": 18,
                    "proposalWindowCount": 6,
                    "proposalFramesWithAnchorSeed": 10,
                    "proposalFramesWithoutAnchorSeed": 2,
                    "proposalExactSeedFrames": 4,
                    "proposalInterpolatedSeedFrames": 4,
                    "proposalSingleSeedFrames": 2,
                    "proposalUnseededFrames": 2,
                    "proposalMeanWindowWidth": 12.25,
                    "proposalDirectSeedWindowFrames": 6,
                    "proposalDirectSeedTightWindowFrames": 4,
                    "proposalDirectSeedContextWindowFrames": 2,
                    "proposalDirectSeedContextEligibleFrames": 5,
                    "proposalDirectSeedContextDuplicateFrames": 1,
                    "proposalDirectSeedContextMeanSeedToBoxDistance": 17.5,
                    "proposalDirectSeedContextExpandedFrames": 2,
                    "proposalDirectSeedContextMeanExpansionPx": 11.5,
                    "proposalPlayerRankedWindowFrames": 6,
                    "proposalRawDetectedFrames": 22,
                    "proposalAfterSeedCollapseFrames": 18,
                    "proposalAfterPlayerWindowFrames": 14,
                    "proposalAfterFalseBallSuppressionFrames": 11,
                    "proposalCollapsedFrames": 9,
                    "proposalCollapsedSegmentCount": 3,
                    "proposalDirectSeedDetectedFrames": 7,
                    "proposalDirectSeedTightDetectedFrames": 3,
                    "proposalDirectSeedContextDetectedFrames": 4,
                    "proposalDirectSeedHiResRetryFrames": 2,
                    "proposalDirectSeedHiResRetryDetectedFrames": 1,
                    "proposalDirectSeedZeroDetectFrames": 5,
                    "proposalDirectSeedScale1600RawDetectionFrames": 4,
                    "proposalDirectSeedScale960RawDetectionFrames": 2,
                    "proposalDirectSeedScale1920RawDetectionFrames": 1,
                    "proposalDirectSeedScale1600CandidateFrames": 3,
                    "proposalDirectSeedScale960CandidateFrames": 1,
                    "proposalDirectSeedScale1920CandidateFrames": 1,
                    "proposalDirectSeedMultiScaleRetryFrames": 3,
                    "proposalDirectSeedMultiScaleDetectedFrames": 2,
                    "proposalDirectSeedRawHitFilteredOutFrames": 2,
                    "proposalDirectSeedCropEdgeRejectedFrames": 1,
                    "proposalDirectSeedCropCenterYRejectedFrames": 2,
                    "proposalDirectSeedPitchPolygonRejectedFrames": 1,
                    "proposalDirectSeedMeanCropArea": 1500.0,
                    "proposalDirectSeedTightMeanCropArea": 1300.0,
                    "proposalDirectSeedContextMeanCropArea": 1700.0,
                    "proposalPlayerRankedMeanCropArea": 2100.0,
                    "proposalDirectSeedMeanDetectedBallBoxArea": 42.0,
                    "proposalPlayerRankedMeanDetectedBallBoxArea": 75.0,
                    "proposalPlayerRankedDetectedFrames": 15,
                    "proposalExactSeedDetectedFrames": 9,
                    "proposalInterpolatedSeedDetectedFrames": 8,
                    "proposalSingleSeedDetectedFrames": 5,
                },
            ],
        },
    )
    storage.update_match_status(
        match.id,
        status="ready",
        requires_team_selection=True,
        team_clusters=[
            ColorClusterSummary(clusterId=0, rgbCentroid=[10.0, 20.0, 30.0], trackIds=[7]),
            ColorClusterSummary(clusterId=1, rgbCentroid=[40.0, 50.0, 60.0], trackIds=[18]),
        ],
    )

    def fake_reprocess_video_match(inner_storage: Storage, match_id: str) -> None:
        refreshed = inner_storage.get_match(match_id)
        selected_cluster = refreshed.config.myTeamCluster
        if selected_cluster is None:
            inner_storage.save_analytics(
                match_id,
                _summary(),
                assignments=[BallOwnership(frameId=index, timestamp=index * 0.2, team="unassigned", trackId=7, distance=1.0) for index in range(10)],
                formation_timeline=[],
                shots=[],
            )
            inner_storage.save_events(
                match_id,
                [DetectedEvent(type="recovery", frameId=1, timestamp=0.2, team="unassigned", toTrackId=7, description="recovery")],
            )
            inner_storage.update_match_status(
                match_id,
                status="ready",
                requires_team_selection=True,
                team_clusters=refreshed.teamClusters,
            )
            return

        team = "my_team" if selected_cluster == 0 else "enemy"
        track_id = 7 if selected_cluster == 0 else 18
        event_type = "carry" if selected_cluster == 0 else "recovery"
        inner_storage.save_analytics(
            match_id,
            _summary(),
            assignments=[BallOwnership(frameId=index, timestamp=index * 0.2, team=team, trackId=track_id, distance=1.0) for index in range(10)],
            formation_timeline=[],
            shots=[],
        )
        inner_storage.save_events(
            match_id,
            [DetectedEvent(type=event_type, frameId=1, timestamp=0.2, team=team, toTrackId=track_id, description=event_type)],
        )
        inner_storage.update_match_status(
            match_id,
            status="ready",
            requires_team_selection=False,
            team_clusters=refreshed.teamClusters,
        )

    monkeypatch.setattr("backend.app.run_benchmarks.reprocess_video_match", fake_reprocess_video_match)

    probes = probe_selected_cluster_benchmarks(storage, match.id)

    assert [probe.clusterId for probe in probes] == [0, 1]
    assert probes[0].requiresTeamSelection is False
    assert probes[0].rawRowCount == 10
    assert probes[0].frameCount == 10
    assert probes[0].withBallFrames == 10
    assert probes[0].controlledPossessionFrames == 10
    assert probes[0].withBallRatio == 1.0
    assert probes[0].trackedPossessionFrames == 10
    assert probes[0].trackedPossessionRatio == 1.0
    assert probes[0].controlledPossessionRatio == 1.0
    assert probes[0].eventTypes == {"carry": 1}
    assert probes[0].proposalCandidateFrames == 11
    assert probes[0].proposalWindowCount == 4
    assert probes[0].proposalFramesWithAnchorSeed == 7
    assert probes[0].proposalFramesWithoutAnchorSeed == 4
    assert probes[0].proposalMeanWindowWidth == 13.5
    assert probes[0].bestProposalRawDetectedFrames == 22
    assert probes[0].bestProposalAfterSeedCollapseFrames == 18
    assert probes[0].bestProposalAfterFalseBallSuppressionFrames == 11
    assert probes[0].bestProposalDirectSeedDetectedFrames == 7
    assert probes[0].bestProposalDirectSeedTightDetectedFrames == 3
    assert probes[0].bestProposalDirectSeedContextDetectedFrames == 4
    assert probes[0].bestProposalDirectSeedHiResRetryFrames == 2
    assert probes[0].bestProposalDirectSeedHiResRetryDetectedFrames == 1
    assert probes[0].bestProposalDirectSeedZeroDetectFrames == 5
    assert probes[0].bestProposalDirectSeedScale1600RawDetectionFrames == 4
    assert probes[0].bestProposalDirectSeedScale960RawDetectionFrames == 2
    assert probes[0].bestProposalDirectSeedScale1920RawDetectionFrames == 1
    assert probes[0].bestProposalDirectSeedScale1600CandidateFrames == 3
    assert probes[0].bestProposalDirectSeedScale960CandidateFrames == 1
    assert probes[0].bestProposalDirectSeedScale1920CandidateFrames == 1
    assert probes[0].bestProposalDirectSeedMultiScaleRetryFrames == 3
    assert probes[0].bestProposalDirectSeedMultiScaleDetectedFrames == 2
    assert probes[0].bestProposalDirectSeedRawHitFilteredOutFrames == 2
    assert probes[0].bestProposalDirectSeedCropEdgeRejectedFrames == 1
    assert probes[0].bestProposalDirectSeedCropCenterYRejectedFrames == 2
    assert probes[0].bestProposalDirectSeedPitchPolygonRejectedFrames == 1
    assert probes[0].bestProposalDirectSeedMeanCropArea == 1500.0
    assert probes[0].bestProposalDirectSeedTightMeanCropArea == 1300.0
    assert probes[0].bestProposalDirectSeedContextMeanCropArea == 1700.0
    assert probes[0].bestProposalPlayerRankedMeanCropArea == 2100.0
    assert probes[0].bestProposalDirectSeedMeanDetectedBallBoxArea == 42.0
    assert probes[0].bestProposalPlayerRankedMeanDetectedBallBoxArea == 75.0
    assert probes[0].bestProposalDirectSeedContextWindowFrames == 2
    assert probes[0].bestProposalDirectSeedContextEligibleFrames == 5
    assert probes[0].bestProposalDirectSeedContextMeanSeedToBoxDistance == 17.5
    assert probes[0].bestProposalDirectSeedContextExpandedFrames == 2
    assert probes[0].bestProposalDirectSeedContextMeanExpansionPx == 11.5
    assert probes[0].bestProposalPlayerRankedDetectedFrames == 15
    assert probes[0].bestProposalExactSeedDetectedFrames == 9
    assert probes[0].bestProposalInterpolatedSeedDetectedFrames == 8
    assert probes[0].bestProposalSingleSeedDetectedFrames == 5
    assert probes[1].rawRowCount == 10
    assert probes[1].frameCount == 10
    assert probes[1].withBallFrames == 10
    assert probes[1].trackedPossessionFrames == 10
    assert probes[1].trackedPossessionRatio == 1.0
    assert probes[1].eventTypes == {"recovery": 1}
    assert probes[1].proposalCandidateFrames == 11
    assert probes[1].proposalWindowCount == 4
    assert probes[1].proposalFramesWithAnchorSeed == 7
    assert probes[1].proposalFramesWithoutAnchorSeed == 4
    assert probes[1].proposalMeanWindowWidth == 13.5
    assert probes[1].bestProposalRawDetectedFrames == 22
    assert probes[1].bestProposalAfterSeedCollapseFrames == 18
    assert probes[1].bestProposalAfterFalseBallSuppressionFrames == 11
    assert probes[1].bestProposalDirectSeedDetectedFrames == 7
    assert probes[1].bestProposalDirectSeedTightDetectedFrames == 3
    assert probes[1].bestProposalDirectSeedContextDetectedFrames == 4
    assert probes[1].bestProposalDirectSeedHiResRetryFrames == 2
    assert probes[1].bestProposalDirectSeedHiResRetryDetectedFrames == 1
    assert probes[1].bestProposalDirectSeedZeroDetectFrames == 5
    assert probes[1].bestProposalDirectSeedScale1600RawDetectionFrames == 4
    assert probes[1].bestProposalDirectSeedScale960RawDetectionFrames == 2
    assert probes[1].bestProposalDirectSeedScale1920RawDetectionFrames == 1
    assert probes[1].bestProposalDirectSeedScale1600CandidateFrames == 3
    assert probes[1].bestProposalDirectSeedScale960CandidateFrames == 1
    assert probes[1].bestProposalDirectSeedScale1920CandidateFrames == 1
    assert probes[1].bestProposalDirectSeedMultiScaleRetryFrames == 3
    assert probes[1].bestProposalDirectSeedMultiScaleDetectedFrames == 2
    assert probes[1].bestProposalDirectSeedRawHitFilteredOutFrames == 2
    assert probes[1].bestProposalDirectSeedCropEdgeRejectedFrames == 1
    assert probes[1].bestProposalDirectSeedCropCenterYRejectedFrames == 2
    assert probes[1].bestProposalDirectSeedPitchPolygonRejectedFrames == 1
    assert probes[1].bestProposalDirectSeedMeanCropArea == 1500.0
    assert probes[1].bestProposalDirectSeedTightMeanCropArea == 1300.0
    assert probes[1].bestProposalDirectSeedContextMeanCropArea == 1700.0
    assert probes[1].bestProposalPlayerRankedMeanCropArea == 2100.0
    assert probes[1].bestProposalDirectSeedMeanDetectedBallBoxArea == 42.0
    assert probes[1].bestProposalPlayerRankedMeanDetectedBallBoxArea == 75.0
    assert probes[1].bestProposalDirectSeedContextWindowFrames == 2
    assert probes[1].bestProposalDirectSeedContextEligibleFrames == 5
    assert probes[1].bestProposalDirectSeedContextMeanSeedToBoxDistance == 17.5
    assert probes[1].bestProposalDirectSeedContextExpandedFrames == 2
    assert probes[1].bestProposalDirectSeedContextMeanExpansionPx == 11.5
    assert probes[1].bestProposalPlayerRankedDetectedFrames == 15
    assert probes[1].bestProposalExactSeedDetectedFrames == 9
    assert probes[1].bestProposalInterpolatedSeedDetectedFrames == 8
    assert probes[1].bestProposalSingleSeedDetectedFrames == 5

    restored_match = storage.get_match(match.id)
    assert restored_match.config.myTeamCluster is None
    assert restored_match.requiresTeamSelection is True


def test_recommend_selected_cluster_benchmark_prefers_controlled_possession_then_event_families_then_with_ball():
    recommended = recommend_selected_cluster_benchmark(
        [
            type(
                "Probe",
                (),
                {
                    "clusterId": 3,
                    "controlledPossessionFrames": 12,
                    "eventFamilyCount": 2,
                    "withBallFrames": 140,
                },
            )(),
            type(
                "Probe",
                (),
                {
                    "clusterId": 1,
                    "controlledPossessionFrames": 12,
                    "eventFamilyCount": 3,
                    "withBallFrames": 120,
                },
            )(),
            type(
                "Probe",
                (),
                {
                    "clusterId": 2,
                    "controlledPossessionFrames": 12,
                    "eventFamilyCount": 3,
                    "withBallFrames": 160,
                },
            )(),
            type(
                "Probe",
                (),
                {
                    "clusterId": 0,
                    "controlledPossessionFrames": 12,
                    "eventFamilyCount": 3,
                    "withBallFrames": 160,
                },
            )(),
        ]
    )

    assert recommended is not None
    assert recommended.clusterId == 0


def test_promote_selected_cluster_benchmark_persists_selected_cluster_and_delta_artifact(tmp_path, monkeypatch):
    storage = Storage(tmp_path)
    upload_path = storage.save_upload("clip.mp4", b"video")
    match = storage.create_match(
        name="promote-selected-cluster",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=upload_path,
        config=MatchConfig(autoHomography=True),
    )
    storage.save_raw_rows(match.id, [{"Frame_ID": index} for index in range(10)])
    storage.save_frames(
        match.id,
        [FrameData(frameId=index, timestamp=index * 0.2, ball={"x": 10 + index, "y": 20, "confidence": 0.8}) for index in range(10)],
    )
    storage.save_analytics(
        match.id,
        _summary(),
        assignments=[BallOwnership(frameId=index, timestamp=index * 0.2, team="unassigned", trackId=7, distance=1.0) for index in range(10)],
        formation_timeline=[],
        shots=[],
    )
    storage.save_events(
        match.id,
        [DetectedEvent(type="recovery", frameId=1, timestamp=0.2, team="unassigned", toTrackId=7, description="recovery")],
    )
    storage.update_match_status(
        match.id,
        status="ready",
        requires_team_selection=True,
        team_clusters=[
            ColorClusterSummary(clusterId=0, rgbCentroid=[10.0, 20.0, 30.0], trackIds=[7]),
            ColorClusterSummary(clusterId=1, rgbCentroid=[40.0, 50.0, 60.0], trackIds=[18]),
        ],
    )

    def fake_reprocess_video_match(inner_storage: Storage, match_id: str) -> None:
        refreshed = inner_storage.get_match(match_id)
        selected_cluster = refreshed.config.myTeamCluster
        if selected_cluster is None:
            return

        team = "my_team" if selected_cluster == 0 else "enemy"
        track_id = 7 if selected_cluster == 0 else 18
        inner_storage.save_analytics(
            match_id,
            _summary(),
            assignments=[BallOwnership(frameId=index, timestamp=index * 0.2, team=team, trackId=track_id, distance=1.0) for index in range(10)],
            formation_timeline=[],
            shots=[],
        )
        inner_storage.save_events(
            match_id,
            [
                DetectedEvent(type="pass" if selected_cluster == 0 else "recovery", frameId=1, timestamp=0.2, team=team, toTrackId=track_id, description="probe"),
                DetectedEvent(type="carry" if selected_cluster == 0 else "recovery", frameId=2, timestamp=0.4, team=team, toTrackId=track_id, description="probe"),
            ],
        )
        inner_storage.update_match_status(
            match_id,
            status="ready",
            requires_team_selection=False,
            team_clusters=refreshed.teamClusters,
        )

    monkeypatch.setattr("backend.app.run_benchmarks.reprocess_video_match", fake_reprocess_video_match)

    result = promote_selected_cluster_benchmark(storage, match.id, cluster_id=0)

    assert result["selectedClusterId"] == 0
    assert result["before"]["controlledPossessionFrames"] == 0
    assert result["after"]["controlledPossessionFrames"] == 10
    assert "controlledPossessionFrames" in result["improvedFields"]
    assert storage.get_match(match.id).config.myTeamCluster == 0

    delta_artifact = storage.load_analysis_artifact(match.id, "selected_cluster_delta")
    assert delta_artifact["savedMatchId"] == match.id
    assert delta_artifact["selectedClusterId"] == 0
    assert delta_artifact["after"]["controlledPossessionFrames"] == 10


def test_run_trimmed_clip_benchmark_serializes_saved_and_probe_ratios(tmp_path, monkeypatch, capsys):
    storage_root = tmp_path / "storage"
    storage = Storage(storage_root)
    upload_path = storage.save_upload("clip.mp4", b"video")
    match = storage.create_match(
        name="benchmark-cli",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=upload_path,
        config=MatchConfig(autoHomography=True),
    )
    storage.save_raw_rows(match.id, [{"Frame_ID": index} for index in range(4)])
    storage.save_frames(
        match.id,
        [
            FrameData(frameId=1, timestamp=0.1, ball={"x": 1, "y": 2, "confidence": 0.9}),
            FrameData(frameId=2, timestamp=0.2, ball={"x": 2, "y": 3, "confidence": 0.9}),
            FrameData(frameId=3, timestamp=0.3, ball=None),
            FrameData(frameId=4, timestamp=0.4, ball=None),
        ],
    )
    storage.save_analytics(
        match.id,
        _summary(),
        assignments=[
            BallOwnership(frameId=1, timestamp=0.1, team="my_team", trackId=7, distance=1.0),
            BallOwnership(frameId=2, timestamp=0.2, team="enemy", trackId=18, distance=1.2),
            BallOwnership(frameId=3, timestamp=0.3, team="enemy", trackId=18, distance=1.2),
            BallOwnership(frameId=4, timestamp=0.4, team="unassigned", trackId=None, distance=None),
        ],
        formation_timeline=[],
        shots=[],
    )
    storage.save_events(
        match.id,
        [
            DetectedEvent(type="pass", frameId=1, timestamp=0.1, team="my_team", fromTrackId=7, toTrackId=8, description="pass"),
            DetectedEvent(type="turnover", frameId=2, timestamp=0.2, team="enemy", fromTrackId=8, toTrackId=18, description="turnover"),
            DetectedEvent(type="shot", frameId=3, timestamp=0.3, team="my_team", fromTrackId=7, toTrackId=7, description="shot"),
        ],
    )
    storage.update_match_status(
        match.id,
        status="ready",
        requires_team_selection=True,
        team_clusters=[
            ColorClusterSummary(clusterId=0, rgbCentroid=[10.0, 20.0, 30.0], trackIds=[7]),
            ColorClusterSummary(clusterId=1, rgbCentroid=[40.0, 50.0, 60.0], trackIds=[18]),
        ],
    )

    def fake_reprocess_video_match(inner_storage: Storage, match_id: str) -> None:
        refreshed = inner_storage.get_match(match_id)
        selected_cluster = refreshed.config.myTeamCluster
        team = "my_team" if selected_cluster == 0 else "enemy"
        track_id = 7 if selected_cluster == 0 else 18
        inner_storage.save_analytics(
            match_id,
            _summary(),
            assignments=[
                BallOwnership(frameId=index, timestamp=index * 0.1, team=team, trackId=track_id, distance=1.0)
                for index in range(4)
            ],
            formation_timeline=[],
            shots=[],
        )
        inner_storage.save_events(
            match_id,
            [
                DetectedEvent(
                    type="recovery" if selected_cluster == 1 else "carry",
                    frameId=1,
                    timestamp=0.1,
                    team=team,
                    toTrackId=track_id,
                    description="probe",
                )
            ],
        )
        inner_storage.update_match_status(
            match_id,
            status="ready",
            requires_team_selection=False,
            team_clusters=refreshed.teamClusters,
        )

    monkeypatch.setattr("backend.app.run_benchmarks.reprocess_video_match", fake_reprocess_video_match)
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_trimmed_clip_benchmark.py",
            "--match-id",
            match.id,
            "--storage-root",
            str(storage_root),
            "--probe-clusters",
        ],
    )

    run_trimmed_clip_benchmark.main()
    payload = json.loads(capsys.readouterr().out)

    assert payload["saved"]["withBallRatio"] == 0.5
    assert payload["saved"]["trackedPossessionRatio"] == 0.75
    assert payload["saved"]["controlledPossessionRatio"] == 0.75
    assert payload["selectedClusters"][0]["withBallRatio"] == 0.5
    assert payload["selectedClusters"][0]["trackedPossessionRatio"] == 1.0
    assert payload["selectedClusters"][0]["controlledPossessionRatio"] == 1.0
    assert payload["selectedClusters"][1]["withBallRatio"] == 0.5
    assert payload["selectedClusters"][1]["trackedPossessionRatio"] == 1.0


def test_run_trimmed_ball_recovery_matrix_serializes_profiles_and_recommendation(tmp_path, monkeypatch, capsys):
    clip_path = tmp_path / "clip-5min.mp4"
    clip_path.write_bytes(b"video")
    monkeypatch.setattr(
        "backend.scripts.run_trimmed_ball_recovery_matrix.run_local_ball_recovery_matrix",
        lambda **kwargs: {
            "videoPath": str(kwargs["video_path"]),
            "profiles": [
                {
                    "name": "edge_margin_40_upper_075",
                    "candidateSummary": {"candidateRows": 18},
                    "selectedSummary": {"frames": 7},
                    "selectedScore": 155.0,
                    "viable": True,
                    "dominantAnchorCoord": [11.0, 21.0],
                    "dominantAnchorShare": 0.5,
                    "meanSourceCenterY": 172.2,
                },
                {
                    "name": "edge_margin_40_upper_078",
                    "candidateSummary": {"candidateRows": 12},
                    "selectedSummary": {"frames": 4},
                    "selectedScore": 149.0,
                    "viable": True,
                    "dominantAnchorCoord": [14.0, 24.0],
                    "dominantAnchorShare": 0.25,
                    "meanSourceCenterY": 168.4,
                },
            ],
            "recommendedProfile": "edge_margin_40_upper_075",
        },
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_trimmed_ball_recovery_matrix.py",
            "--video-path",
            str(clip_path),
            "--name",
            "real proof",
            "--manual-points-json",
            "[[1,2],[3,4],[5,6],[7,8]]",
        ],
    )

    run_trimmed_ball_recovery_matrix.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["videoPath"] == str(clip_path)
    assert payload["recommendedProfile"] == "edge_margin_40_upper_075"
    assert payload["profiles"][0]["name"] == "edge_margin_40_upper_075"
    assert payload["profiles"][0]["selectedScore"] == 155.0
    assert payload["profiles"][0]["dominantAnchorCoord"] == [11.0, 21.0]
    assert payload["profiles"][0]["dominantAnchorShare"] == 0.5
    assert payload["profiles"][0]["meanSourceCenterY"] == 172.2


def test_run_local_ball_recovery_matrix_detector_breadth_screen_uses_reduced_profiles(tmp_path, monkeypatch):
    clip_path = tmp_path / "clip-5min.mp4"
    clip_path.write_bytes(b"video")

    class FakeCapture:
        def __init__(self, _path):
            pass

        def isOpened(self):
            return True

        def get(self, prop):
            return 25 if prop == 5 else 0

        def release(self):
            return None

    captured: dict[str, object] = {}

    monkeypatch.setattr(run_trimmed_ball_recovery_matrix.cv2, "VideoCapture", FakeCapture)
    monkeypatch.setattr(
        run_trimmed_ball_recovery_matrix,
        "build_homography_from_points",
        lambda _points: "homography",
    )
    monkeypatch.setattr(run_trimmed_ball_recovery_matrix, "YOLO", lambda model_path: {"model_path": model_path})
    monkeypatch.setattr(
        run_trimmed_ball_recovery_matrix,
        "collect_primary_player_windows",
        lambda *args, **kwargs: {"windows": True},
    )
    monkeypatch.setattr(
        run_trimmed_ball_recovery_matrix,
        "build_detector_breadth_screen_ball_recovery_profiles",
        lambda: [
            {"name": "baseline_player_window", "settings": {"imgsz": 1600, "conf": 0.08}, "usePlayerWindows": True},
            {"name": "proposal_windows_075", "settings": {"imgsz": 1600, "conf": 0.08}, "usePlayerWindows": True},
        ],
    )

    def fake_run_ball_recovery_experiment(**kwargs):
        captured["profiles"] = kwargs["profiles"]
        return [
            {
                "name": "proposal_windows_075",
                "settings": {"imgsz": 1600, "conf": 0.08},
                "usePlayerWindows": True,
                "candidateSummary": {"dominantAnchorShare": 0.5, "meanSourceCenterY": 160.0},
                "selectedSummary": {"frames": 8, "edgeFrameShare": 0.2},
                "selectedScore": 155.0,
                "viable": True,
            },
            {
                "name": "baseline_player_window",
                "settings": {"imgsz": 1600, "conf": 0.08},
                "usePlayerWindows": True,
                "candidateSummary": {"dominantAnchorShare": 0.4, "meanSourceCenterY": 165.0},
                "selectedSummary": {"frames": 6, "edgeFrameShare": 0.3},
                "selectedScore": 149.0,
                "viable": True,
            },
        ]

    monkeypatch.setattr(
        run_trimmed_ball_recovery_matrix,
        "run_ball_recovery_experiment",
        fake_run_ball_recovery_experiment,
    )
    monkeypatch.setattr(
        run_trimmed_ball_recovery_matrix,
        "select_best_ball_recovery_profile",
        lambda results: next(result for result in results if result["name"] == "proposal_windows_075"),
    )

    payload = run_trimmed_ball_recovery_matrix.run_local_ball_recovery_matrix(
        video_path=clip_path,
        profile_mode="detector_breadth_screen",
    )

    assert payload["profileMode"] == "detector_breadth_screen"
    assert [profile["name"] for profile in captured["profiles"]] == [
        "baseline_player_window",
        "proposal_windows_075",
    ]
    assert payload["recommendedProfile"] == "proposal_windows_075"
