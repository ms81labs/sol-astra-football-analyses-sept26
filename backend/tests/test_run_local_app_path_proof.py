from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_local_app_path_proof as run_local_app_path_proof
from backend.app.schemas import BallOwnership, DetectedEvent, FrameData, MatchSummary
from backend.app.settings import ProcessingSettings
from backend.app.storage import Storage


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


def test_run_local_app_path_proof_imports_saved_local_result(tmp_path, monkeypatch):
    clip_path = tmp_path / "clip-5min.mp4"
    clip_path.write_bytes(b"video")
    settings = ProcessingSettings(processing_backend="local")
    captured: dict[str, object] = {}

    class FakeJobRunner:
        def __init__(self, storage_root, run_jobs_inline=False, settings=None):  # noqa: ANN001
            captured["storage_root"] = storage_root
            captured["run_jobs_inline"] = run_jobs_inline
            captured["settings"] = settings
            self.storage_root = Path(storage_root)

        def start(self, job_id):  # noqa: ANN001
            captured["job_id"] = job_id
            storage = Storage(self.storage_root)
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
                [
                    FrameData(
                        frameId=0,
                        timestamp=0.0,
                        ball={"x": 52.0, "y": 50.0, "confidence": 0.95},
                        myTeam=[{"id": 4, "x": 51.0, "y": 50.0, "confidence": 0.9}],
                    )
                ],
            )
            storage.save_analytics(
                job.matchId,
                _summary(),
                assignments=[BallOwnership(frameId=0, timestamp=0.0, team="my_team", trackId=4, distance=1.0)],
                formation_timeline=[],
                shots=[],
            )
            storage.save_events(
                job.matchId,
                [DetectedEvent(type="recovery", frameId=0, timestamp=0.0, description="recovery")],
            )
            storage.save_analysis_artifact(
                job.matchId,
                "recovery_debug",
                {
                    "primaryBallFrames": 1,
                    "recoveryAttempted": True,
                    "recoveryProfileName": "baseline_player_window",
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
                job.matchId,
                "ball_truth_layers",
                {
                    "sampleInterval": 5,
                    "observedBall": {
                        "rows": [
                            {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 52.0, "Y": 50.0, "Conf": 0.95},
                        ],
                        "summary": {
                            "rowCount": 1,
                            "frameCount": 1,
                            "pathLength": 0.0,
                            "edgeFrameShare": 0.0,
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
                            {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 52.0, "Y": 50.0, "Conf": 0.95},
                        ],
                        "summary": {
                            "rowCount": 1,
                            "frameCount": 1,
                            "pathLength": 0.0,
                            "edgeFrameShare": 0.0,
                            "segmentCount": 1,
                            "firstFrame": 0,
                            "lastFrame": 0,
                        },
                    },
                    "acceptedSegments": [
                        {"startFrame": 0, "endFrame": 0, "frameCount": 1, "source": "observed"},
                    ],
                    "unknownGaps": [],
                    "acceptedSourceBreakdown": {"observed": 1, "inferred": 0},
                    "directObservationBreakdown": {
                        "trackingObservedBallFrames": 1,
                        "rawProbeObservedBallFrames": 2,
                        "filteredProbeObservedBallFrames": 1,
                        "suppressedProbeObservedBallFrames": 1,
                        "anchoredProbeObservedBallFrames": 1,
                        "bridgeProbeObservedBallFrames": 0,
                        "probeObservedBallFrames": 1,
                        "probeOnlyObservedBallFrames": 0,
                        "acceptedFromObservedFrames": 1,
                        "acceptedFromObservedRatio": 1.0,
                    },
                    "supportDiagnostics": {
                        "supportedObservedBallFrames": 1,
                        "supportedAcceptedBallFrames": 1,
                        "supportedAcceptedBallRatio": 1.0,
                        "unsupportedAcceptedEdgeFrames": 0,
                    },
                },
            )
            storage.save_analysis_artifact(
                job.matchId,
                "accepted_match_state",
                {
                    "stateContinuityAppliedFrames": 1,
                    "frames": [
                        {
                            "frameId": 0,
                            "timestamp": 0.0,
                            "mode": "controlled_possession",
                            "controllingTeam": "my_team",
                            "controllingTrackId": 4,
                            "ballVisibility": "visible",
                            "ballEstimate": {"x": 52.0, "y": 50.0, "confidence": 0.95, "radius": 0.0},
                            "source": "observed_ball",
                            "confidence": 0.90,
                            "reasonCodes": ["accepted_ball", "observed_ball"],
                        }
                    ],
                },
            )
            storage.save_analysis_artifact(
                job.matchId,
                "ball_pipeline_trace",
                {
                    "traceVersion": 1,
                    "matchId": job.matchId,
                    "jobId": job_id,
                    "processingBackend": "local",
                    "inputMode": "video",
                    "videoPath": str(self.storage_root / "clip-5min.mp4"),
                    "workerPath": "local",
                    "detectorModelPath": "/workspace/weights/yolo11s.pt",
                    "detectorModelName": "yolo11s.pt",
                    "stages": [],
                },
            )
            storage.update_match_status(job.matchId, status="ready", requires_team_selection=False, team_clusters=[])
            storage.update_job(job_id, status="completed", progress=1.0, message="local complete")

    monkeypatch.setattr(run_local_app_path_proof, "JobRunner", FakeJobRunner)

    summary = run_local_app_path_proof.run_local_app_path_proof(
        storage_root=tmp_path,
        clip_path=clip_path,
        settings=settings,
        name="app path proof",
        model_path="yolo11s.pt",
        poll_interval_seconds=0,
        timeout_seconds=1,
    )

    assert captured["storage_root"] == tmp_path
    assert captured["run_jobs_inline"] is False
    assert captured["settings"] == settings
    assert captured["proof_runtime_options"] == {
        "primary_model": {"artifactId": "yolo11s.pt"},
        "auxiliary_ball_model": None,
        "auxiliary_ball_model_profile": None,
        "primary_acquisition_mode": "anchored_player_ranked_context_960",
        "edge_share_repair_profile": None,
        "baseline_guided_rescue_reference": None,
        "proposal_selection_truth_seed": None,
        "reviewed_positive_anchor_seed": None,
    }
    assert summary.rawRowCount == 2
    assert summary.frameCount == 1
    assert summary.playerFrames == 1
    assert summary.withBallFrames == 1
    assert summary.observedBallFrames == 1
    assert summary.inferredBallFrames == 0
    assert summary.acceptedBallFrames == 1
    assert summary.acceptedBallRatio == 1.0
    assert summary.acceptedSegmentCount == 1
    assert summary.unknownGapCount == 0
    assert summary.longestUnknownGapFrames == 0
    assert summary.trackingObservedBallFrames == 1
    assert summary.rawProbeObservedBallFrames == 2
    assert summary.filteredProbeObservedBallFrames == 1
    assert summary.suppressedProbeObservedBallFrames == 1
    assert summary.anchoredProbeObservedBallFrames == 1
    assert summary.bridgeProbeObservedBallFrames == 0
    assert summary.probeObservedBallFrames == 1
    assert summary.probeOnlyObservedBallFrames == 0
    assert summary.acceptedFromObservedFrames == 1
    assert summary.acceptedFromObservedRatio == 1.0
    assert summary.supportedObservedBallFrames == 1
    assert summary.supportedAcceptedBallFrames == 1
    assert summary.supportedAcceptedBallRatio == 1.0
    assert summary.unsupportedAcceptedEdgeFrames == 0
    assert summary.acceptedMatchStateFrames == 1
    assert summary.acceptedMatchStateCoverageRatio == 1.0
    assert summary.visibleStateFrames == 1
    assert summary.inferredStateFrames == 0
    assert summary.hiddenStateFrames == 0
    assert summary.controlledStateFrames == 1
    assert summary.hiddenControlledStateFrames == 0
    assert summary.restartOrOutStateFrames == 0
    assert summary.stateContinuityAppliedFrames == 1
    assert summary.matchStateModeCounts == {"controlled_possession": 1}
    assert summary.controlledPossessionFrames == 1
    assert summary.eventTypes == {"recovery": 1}
    assert summary.detectorModelPath == "/workspace/weights/yolo11s.pt"
    assert summary.detectorModelName == "yolo11s.pt"
    proof_summary = Storage(tmp_path).load_analysis_artifact(summary.matchId, "proof_summary")
    assert proof_summary["acceptedBallFrames"] == 1
    assert proof_summary["controlledPossessionFrames"] == 1
    assert proof_summary["eventFamilyCount"] == 1


def test_run_local_app_path_proof_cli_serializes_compact_summary(tmp_path, monkeypatch, capsys):
    clip_path = tmp_path / "clip-5min.mp4"
    clip_path.write_bytes(b"video")

    def fake_run_local_app_path_proof(**kwargs):  # noqa: ANN003
        assert kwargs["storage_root"] == tmp_path
        assert kwargs["clip_path"] == clip_path
        assert kwargs["name"] == "app path proof"
        assert kwargs["model_path"] == "/workspace/weights/yolo11s.pt"
        return type(
            "FakeSummary",
            (),
            {
                "model_dump": lambda self, mode="json": {
                    "matchId": "match-123",
                    "jobId": "job-123",
                    "detectorModelPath": "/workspace/weights/yolo11s.pt",
                    "detectorModelName": "yolo11s.pt",
                    "rawRowCount": 2,
                    "frameCount": 1,
                    "playerFrames": 1,
                    "withBallFrames": 1,
                    "trackedPossessionFrames": 1,
                    "controlledPossessionFrames": 1,
                    "observedBallFrames": 1,
                    "inferredBallFrames": 0,
                    "acceptedBallFrames": 1,
                    "acceptedBallRatio": 1.0,
                    "acceptedSegmentCount": 1,
                    "unknownGapCount": 0,
                    "longestUnknownGapFrames": 0,
                    "trackingObservedBallFrames": 1,
                    "rawProbeObservedBallFrames": 2,
                    "filteredProbeObservedBallFrames": 1,
                    "suppressedProbeObservedBallFrames": 1,
                    "anchoredProbeObservedBallFrames": 1,
                    "bridgeProbeObservedBallFrames": 0,
                    "probeObservedBallFrames": 1,
                    "probeOnlyObservedBallFrames": 0,
                    "acceptedFromObservedFrames": 1,
                    "acceptedFromObservedRatio": 1.0,
                    "supportedObservedBallFrames": 1,
                    "supportedAcceptedBallFrames": 1,
                    "supportedAcceptedBallRatio": 1.0,
                    "unsupportedAcceptedEdgeFrames": 0,
                    "acceptedMatchStateFrames": 1,
                    "acceptedMatchStateCoverageRatio": 1.0,
                    "visibleStateFrames": 1,
                    "inferredStateFrames": 0,
                    "hiddenStateFrames": 0,
                    "controlledStateFrames": 1,
                    "hiddenControlledStateFrames": 0,
                    "restartOrOutStateFrames": 0,
                    "stateContinuityAppliedFrames": 1,
                    "matchStateModeCounts": {"controlled_possession": 1},
                    "recoveredSupportedFrames": 4,
                    "recoveredAnchoredFrames": 3,
                    "recoveredBridgeFrames": 2,
                    "recoveredUnsupportedEdgeFrameShare": 0.125,
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
                    "bestProposalRawDetectedFrames": 22,
                    "bestProposalAfterSeedCollapseFrames": 18,
                    "bestProposalAfterFalseBallSuppressionFrames": 11,
                    "bestProposalDirectSeedDetectedFrames": 7,
                    "bestProposalDirectSeedTightDetectedFrames": 3,
                    "bestProposalDirectSeedContextDetectedFrames": 4,
                    "bestProposalDirectSeedHiResRetryFrames": 2,
                    "bestProposalDirectSeedHiResRetryDetectedFrames": 1,
                    "bestProposalDirectSeedZeroDetectFrames": 5,
                    "bestProposalDirectSeedMeanCropArea": 1500.0,
                    "bestProposalPlayerRankedMeanCropArea": 2100.0,
                    "bestProposalDirectSeedMeanDetectedBallBoxArea": 42.0,
                    "bestProposalPlayerRankedMeanDetectedBallBoxArea": 75.0,
                    "bestProposalDirectSeedContextWindowFrames": 2,
                    "bestProposalDirectSeedContextEligibleFrames": 5,
                    "bestProposalDirectSeedContextMeanSeedToBoxDistance": 17.5,
                    "bestProposalDirectSeedContextExpandedFrames": 2,
                    "bestProposalDirectSeedContextMeanExpansionPx": 11.5,
                    "bestProposalPlayerRankedDetectedFrames": 15,
                    "bestProposalExactSeedDetectedFrames": 9,
                    "bestProposalInterpolatedSeedDetectedFrames": 8,
                    "bestProposalSingleSeedDetectedFrames": 5,
                    "bestProposalProfileName": "proposal_windows_075",
                    "bestProposalCandidateFrames": 18,
                    "bestProposalSelectedFrames": 6,
                    "bestProposalViable": True,
                    "collapsedCandidateFrames": 7,
                        "collapsedSegmentCount": 2,
                        "collapsedLongestSegmentFrames": 4,
                    "continuityPreferredFrames": 3,
                    "continuityRejectedFrames": 5,
                    "midfieldCollapsedFrames": 6,
                    "eventTypes": {"recovery": 1},
                    "eventFamilyCount": 1,
                    "ballSignalStatus": "trusted",
                    "ballTrackViable": True,
                    "recoveryProfileName": "baseline_player_window",
                    "recoveryApplied": True,
                    "recoveredSelectedFrames": 4,
                    "dominantAnchorCoord": [12.5, 19.5],
                    "dominantAnchorCount": 3,
                    "dominantAnchorShare": 0.75,
                    "meanSourceCenterY": 173.33,
                    "meanSourceBoxArea": 800.0,
                    "candidateEdgeShare": 0.25,
                    "selectedEdgeFrameShare": 0.1,
                    "warmProofMode": False,
                    "warmReadyObserved": False,
                    "warmupWaitSeconds": 0.0,
                    "fiveMinuteTruthReady": False,
                    "truthGateReasons": ["Need at least 3 event families"],
                }
            },
        )()

    monkeypatch.setattr(
        "backend.scripts.run_local_app_path_proof.run_local_app_path_proof",
        fake_run_local_app_path_proof,
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_local_app_path_proof.py",
            "--storage-root",
            str(tmp_path),
            "--video-path",
            str(clip_path),
            "--name",
            "app path proof",
            "--model-path",
            "/workspace/weights/yolo11s.pt",
        ],
    )

    run_local_app_path_proof.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["savedMatchId"] == "match-123"
    assert payload["jobId"] == "job-123"
    assert payload["detectorModelPath"] == "/workspace/weights/yolo11s.pt"
    assert payload["detectorModelName"] == "yolo11s.pt"
    assert payload["rawRows"] == 2
    assert payload["frameCount"] == 1
    assert payload["playerFrames"] == 1
    assert payload["ballFrames"] == 1
    assert payload["observedBallFrames"] == 1
    assert payload["inferredBallFrames"] == 0
    assert payload["acceptedBallFrames"] == 1
    assert payload["acceptedBallRatio"] == 1.0
    assert payload["acceptedSegmentCount"] == 1
    assert payload["unknownGapCount"] == 0
    assert payload["longestUnknownGapFrames"] == 0
    assert payload["trackingObservedBallFrames"] == 1
    assert payload["rawProbeObservedBallFrames"] == 2
    assert payload["filteredProbeObservedBallFrames"] == 1
    assert payload["suppressedProbeObservedBallFrames"] == 1
    assert payload["anchoredProbeObservedBallFrames"] == 1
    assert payload["bridgeProbeObservedBallFrames"] == 0
    assert payload["probeObservedBallFrames"] == 1
    assert payload["probeOnlyObservedBallFrames"] == 0
    assert payload["acceptedFromObservedFrames"] == 1
    assert payload["acceptedFromObservedRatio"] == 1.0
    assert payload["supportedObservedBallFrames"] == 1
    assert payload["supportedAcceptedBallFrames"] == 1
    assert payload["supportedAcceptedBallRatio"] == 1.0
    assert payload["unsupportedAcceptedEdgeFrames"] == 0
    assert payload["acceptedMatchStateFrames"] == 1
    assert payload["acceptedMatchStateCoverageRatio"] == 1.0
    assert payload["visibleStateFrames"] == 1
    assert payload["inferredStateFrames"] == 0
    assert payload["hiddenStateFrames"] == 0
    assert payload["controlledStateFrames"] == 1
    assert payload["hiddenControlledStateFrames"] == 0
    assert payload["restartOrOutStateFrames"] == 0
    assert payload["stateContinuityAppliedFrames"] == 1
    assert payload["matchStateModeCounts"] == {"controlled_possession": 1}
    assert payload["recoveredSupportedFrames"] == 4
    assert payload["recoveredAnchoredFrames"] == 3
    assert payload["recoveredBridgeFrames"] == 2
    assert payload["recoveredUnsupportedEdgeFrameShare"] == 0.125
    assert payload["recoveredAnchoredPathLength"] == 18.5
    assert payload["corridorCandidateFrames"] == 6
    assert payload["corridorFramesWithTwoAnchors"] == 4
    assert payload["corridorFramesWithSingleAnchor"] == 2
    assert payload["corridorMeanWidth"] == 11.5
    assert payload["proposalCandidateFrames"] == 11
    assert payload["proposalWindowCount"] == 4
    assert payload["proposalFramesWithAnchorSeed"] == 7
    assert payload["proposalFramesWithoutAnchorSeed"] == 4
    assert payload["proposalExactSeedFrames"] == 2
    assert payload["proposalInterpolatedSeedFrames"] == 3
    assert payload["proposalSingleSeedFrames"] == 2
    assert payload["proposalUnseededFrames"] == 4
    assert payload["proposalMeanWindowWidth"] == 13.5
    assert payload["bestProposalRawDetectedFrames"] == 22
    assert payload["bestProposalAfterSeedCollapseFrames"] == 18
    assert payload["bestProposalAfterFalseBallSuppressionFrames"] == 11
    assert payload["bestProposalDirectSeedDetectedFrames"] == 7
    assert payload["bestProposalDirectSeedTightDetectedFrames"] == 3
    assert payload["bestProposalDirectSeedContextDetectedFrames"] == 4
    assert payload["bestProposalDirectSeedHiResRetryFrames"] == 2
    assert payload["bestProposalDirectSeedHiResRetryDetectedFrames"] == 1
    assert payload["bestProposalDirectSeedZeroDetectFrames"] == 5
    assert payload["bestProposalDirectSeedMeanCropArea"] == 1500.0
    assert payload["bestProposalPlayerRankedMeanCropArea"] == 2100.0
    assert payload["bestProposalDirectSeedMeanDetectedBallBoxArea"] == 42.0
    assert payload["bestProposalPlayerRankedMeanDetectedBallBoxArea"] == 75.0
    assert payload["bestProposalDirectSeedContextWindowFrames"] == 2
    assert payload["bestProposalDirectSeedContextEligibleFrames"] == 5
    assert payload["bestProposalDirectSeedContextMeanSeedToBoxDistance"] == 17.5
    assert payload["bestProposalDirectSeedContextExpandedFrames"] == 2
    assert payload["bestProposalDirectSeedContextMeanExpansionPx"] == 11.5
    assert payload["bestProposalPlayerRankedDetectedFrames"] == 15
    assert payload["bestProposalExactSeedDetectedFrames"] == 9
    assert payload["bestProposalInterpolatedSeedDetectedFrames"] == 8
    assert payload["bestProposalSingleSeedDetectedFrames"] == 5
    assert payload["bestProposalProfileName"] == "proposal_windows_075"
    assert payload["bestProposalCandidateFrames"] == 18
    assert payload["bestProposalSelectedFrames"] == 6
    assert payload["bestProposalViable"] is True
    assert payload["collapsedCandidateFrames"] == 7
    assert payload["collapsedSegmentCount"] == 2
    assert payload["collapsedLongestSegmentFrames"] == 4
    assert payload["continuityPreferredFrames"] == 3
    assert payload["continuityRejectedFrames"] == 5
    assert payload["midfieldCollapsedFrames"] == 6
    assert payload["controlledPossessionFrames"] == 1
    assert payload["eventTypes"] == {"recovery": 1}
    assert payload["eventFamilyCount"] == 1
    assert payload["warmProofMode"] is False
    assert payload["warmReadyObserved"] is False
    assert payload["warmupWaitSeconds"] == 0.0
    assert payload["truthGateReasons"] == ["Need at least 3 event families"]


def test_run_local_app_path_proof_persists_edge_share_repair_profile(tmp_path, monkeypatch):
    clip_path = tmp_path / "clip-5min.mp4"
    clip_path.write_bytes(b"video")
    captured: dict[str, object] = {}

    class FakeJobRunner:
        def __init__(self, storage_root, run_jobs_inline=False, settings=None):  # noqa: ANN001
            self.storage_root = Path(storage_root)

        def start(self, job_id):  # noqa: ANN001
            storage = Storage(self.storage_root)
            job = storage.get_job(job_id)
            captured["proof_runtime_options"] = storage.load_analysis_artifact(job.matchId, "proof_runtime_options")
            storage.update_match_status(job.matchId, status="ready", requires_team_selection=False, team_clusters=[])
            storage.update_job(job_id, status="completed", progress=1.0, message="local complete")

    monkeypatch.setattr(run_local_app_path_proof, "JobRunner", FakeJobRunner)

    run_local_app_path_proof.run_local_app_path_proof(
        storage_root=tmp_path,
        clip_path=clip_path,
        edge_share_repair_profile="source_robustness_shadow_touchline_probe_replace_v1",
        poll_interval_seconds=0,
        timeout_seconds=1,
    )

    assert captured["proof_runtime_options"]["edge_share_repair_profile"] == (
        "source_robustness_shadow_touchline_probe_replace_v1"
    )


def test_run_local_app_path_proof_persists_baseline_guided_rescue_reference_path(tmp_path, monkeypatch):
    clip_path = tmp_path / "clip-5min.mp4"
    clip_path.write_bytes(b"video")
    captured: dict[str, object] = {}

    class FakeJobRunner:
        def __init__(self, storage_root, run_jobs_inline=False, settings=None):  # noqa: ANN001
            self.storage_root = Path(storage_root)

        def start(self, job_id):  # noqa: ANN001
            storage = Storage(self.storage_root)
            job = storage.get_job(job_id)
            captured["proof_runtime_options"] = storage.load_analysis_artifact(job.matchId, "proof_runtime_options")
            storage.update_match_status(job.matchId, status="ready", requires_team_selection=False, team_clusters=[])
            storage.update_job(job_id, status="completed", progress=1.0, message="local complete")

    monkeypatch.setattr(run_local_app_path_proof, "JobRunner", FakeJobRunner)

    run_local_app_path_proof.run_local_app_path_proof(
        storage_root=tmp_path,
        clip_path=clip_path,
        baseline_guided_rescue_reference_path="baseline-guided-reference",
        poll_interval_seconds=0,
        timeout_seconds=1,
    )

    assert captured["proof_runtime_options"]["baseline_guided_rescue_reference"] == {
        "artifactId": "baseline-guided-reference"
    }


def test_run_local_app_path_proof_persists_proposal_selection_truth_seed_path(tmp_path, monkeypatch):
    clip_path = tmp_path / "clip-5min.mp4"
    clip_path.write_bytes(b"video")
    captured: dict[str, object] = {}

    class FakeJobRunner:
        def __init__(self, storage_root, run_jobs_inline=False, settings=None):  # noqa: ANN001
            self.storage_root = Path(storage_root)

        def start(self, job_id):  # noqa: ANN001
            storage = Storage(self.storage_root)
            job = storage.get_job(job_id)
            captured["proof_runtime_options"] = storage.load_analysis_artifact(job.matchId, "proof_runtime_options")
            storage.update_match_status(job.matchId, status="ready", requires_team_selection=False, team_clusters=[])
            storage.update_job(job_id, status="completed", progress=1.0, message="local complete")

    monkeypatch.setattr(run_local_app_path_proof, "JobRunner", FakeJobRunner)

    run_local_app_path_proof.run_local_app_path_proof(
        storage_root=tmp_path,
        clip_path=clip_path,
        proposal_selection_truth_seed_path="proposal-selection-truth-seed",
        poll_interval_seconds=0,
        timeout_seconds=1,
    )

    assert captured["proof_runtime_options"]["proposal_selection_truth_seed"] == {
        "artifactId": "proposal-selection-truth-seed"
    }


def test_run_local_app_path_proof_persists_reviewed_positive_anchor_seed_path(tmp_path, monkeypatch):
    clip_path = tmp_path / "clip-5min.mp4"
    clip_path.write_bytes(b"video")
    captured: dict[str, object] = {}

    class FakeJobRunner:
        def __init__(self, storage_root, run_jobs_inline=False, settings=None):  # noqa: ANN001
            self.storage_root = Path(storage_root)

        def start(self, job_id):  # noqa: ANN001
            storage = Storage(self.storage_root)
            job = storage.get_job(job_id)
            captured["proof_runtime_options"] = storage.load_analysis_artifact(job.matchId, "proof_runtime_options")
            storage.update_match_status(job.matchId, status="ready", requires_team_selection=False, team_clusters=[])
            storage.update_job(job_id, status="completed", progress=1.0, message="local complete")

    monkeypatch.setattr(run_local_app_path_proof, "JobRunner", FakeJobRunner)

    run_local_app_path_proof.run_local_app_path_proof(
        storage_root=tmp_path,
        clip_path=clip_path,
        reviewed_positive_anchor_seed_path="reviewed-positive-anchor-seed",
        poll_interval_seconds=0,
        timeout_seconds=1,
    )

    assert captured["proof_runtime_options"]["reviewed_positive_anchor_seed"] == {
        "artifactId": "reviewed-positive-anchor-seed"
    }


def test_run_local_app_path_proof_persists_primary_and_auxiliary_ball_model_runtime_options(tmp_path, monkeypatch):
    clip_path = tmp_path / "clip-5min.mp4"
    clip_path.write_bytes(b"video")
    captured: dict[str, object] = {}

    class FakeJobRunner:
        def __init__(self, storage_root, run_jobs_inline=False, settings=None):  # noqa: ANN001
            self.storage_root = Path(storage_root)

        def start(self, job_id):  # noqa: ANN001
            storage = Storage(self.storage_root)
            job = storage.get_job(job_id)
            captured["proof_runtime_options"] = storage.load_analysis_artifact(job.matchId, "proof_runtime_options")
            storage.update_match_status(job.matchId, status="ready", requires_team_selection=False, team_clusters=[])
            storage.update_job(job_id, status="completed", progress=1.0, message="local complete")

    monkeypatch.setattr(run_local_app_path_proof, "JobRunner", FakeJobRunner)

    run_local_app_path_proof.run_local_app_path_proof(
        storage_root=tmp_path,
        clip_path=clip_path,
        model_path="primary-model",
        primary_model_path="primary-model",
        auxiliary_ball_model_path="auxiliary-ball-model",
        auxiliary_ball_model_profile="ball_probe_only_v1",
        poll_interval_seconds=0,
        timeout_seconds=1,
    )

    runtime_options = captured["proof_runtime_options"]
    assert runtime_options["primary_model"] == {"artifactId": "primary-model"}
    assert runtime_options["auxiliary_ball_model"] == {"artifactId": "auxiliary-ball-model"}
    assert runtime_options["auxiliary_ball_model_profile"] == "ball_probe_only_v1"


def test_run_local_app_path_proof_cli_can_include_selected_clusters(tmp_path, monkeypatch, capsys):
    clip_path = tmp_path / "clip-5min.mp4"
    clip_path.write_bytes(b"video")

    def fake_run_local_app_path_proof(**kwargs):  # noqa: ANN003
        return type(
            "FakeSummary",
            (),
            {
                "matchId": "match-123",
                "model_dump": lambda self, mode="json": {
                    "matchId": "match-123",
                    "jobId": "job-123",
                    "rawRowCount": 2,
                    "frameCount": 1,
                    "playerFrames": 1,
                    "withBallFrames": 1,
                    "trackedPossessionFrames": 1,
                    "controlledPossessionFrames": 1,
                    "eventTypes": {"recovery": 1},
                    "recoveredSupportedFrames": 4,
                    "recoveredAnchoredFrames": 3,
                    "recoveredBridgeFrames": 2,
                    "recoveredUnsupportedEdgeFrameShare": 0.125,
                    "recoveredAnchoredPathLength": 18.5,
                    "corridorCandidateFrames": 6,
                    "corridorFramesWithTwoAnchors": 4,
                    "corridorFramesWithSingleAnchor": 2,
                    "corridorMeanWidth": 11.5,
                    "proposalCandidateFrames": 11,
                    "proposalWindowCount": 4,
                    "proposalFramesWithAnchorSeed": 7,
                    "proposalFramesWithoutAnchorSeed": 4,
                    "proposalMeanWindowWidth": 13.5,
                    "collapsedCandidateFrames": 7,
                    "collapsedSegmentCount": 2,
                    "collapsedLongestSegmentFrames": 4,
                    "continuityPreferredFrames": 3,
                    "continuityRejectedFrames": 5,
                    "midfieldCollapsedFrames": 6,
                    "fiveMinuteTruthReady": False,
                    "truthGateReasons": ["Need at least 3 event families"],
                },
            },
        )()

    monkeypatch.setattr(
        "backend.scripts.run_local_app_path_proof.run_local_app_path_proof",
        fake_run_local_app_path_proof,
    )
    monkeypatch.setattr(
        "backend.scripts.run_local_app_path_proof.build_selected_cluster_payload",
        lambda storage, match_id: {
            "selectedClusters": [
                {"clusterId": 0, "controlledPossessionFrames": 33, "eventFamilyCount": 3, "withBallFrames": 46},
                {"clusterId": 1, "controlledPossessionFrames": 33, "eventFamilyCount": 2, "withBallFrames": 46},
            ],
            "recommendedCluster": {"clusterId": 0, "controlledPossessionFrames": 33, "eventFamilyCount": 3, "withBallFrames": 46},
        },
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_local_app_path_proof.py",
            "--storage-root",
            str(tmp_path),
            "--video-path",
            str(clip_path),
            "--include-selected-clusters",
        ],
    )

    run_local_app_path_proof.main()
    payload = json.loads(capsys.readouterr().out)

    assert payload["selectedClusters"][0]["clusterId"] == 0
    assert payload["recommendedCluster"]["clusterId"] == 0
