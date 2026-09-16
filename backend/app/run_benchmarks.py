from __future__ import annotations

import json
from collections import Counter
from math import hypot
from pathlib import Path
from statistics import median

from pydantic import BaseModel, Field

from .proof_summary import save_canonical_proof_summary
from .proof_runtime import (
    DEFAULT_PRIMARY_ACQUISITION_MODE,
    load_proof_runtime_options,
    save_proof_runtime_options,
)
from .schemas import HomographyPoint, MatchConfig
from .settings import ProcessingSettings
from .storage import Storage
from .runtime_options import ArtifactReference, RuntimeOptionsError

RUNTIME_MANIFEST_PATH = Path(__file__).resolve().parents[1] / "release" / "v7.3.json"


def _redacted_runtime_reference_identity(value: str) -> str:
    normalized = value.strip()
    if "contentBase64" not in normalized:
        return normalized
    try:
        payload = json.loads(normalized)
        if not isinstance(payload, dict):
            raise RuntimeOptionsError("runtime reference identity must be an object")
        reference = ArtifactReference.from_mapping(payload)
    except (json.JSONDecodeError, RuntimeOptionsError):
        return "redacted-inline-runtime-reference"
    return json.dumps(reference.to_provenance_mapping(), sort_keys=True)


def reprocess_video_match(storage: Storage, match_id: str) -> None:
    from .processor import reprocess_video_match as execute_reprocess_video_match

    execute_reprocess_video_match(storage, match_id)


def run_remote_job(
    storage_root: Path,
    job_id: str,
    settings: ProcessingSettings | None = None,
    *,
    transport_mode: str | None = None,
    use_runsync: bool | None = None,
) -> None:
    if transport_mode is not None or use_runsync not in (None, False):
        raise ValueError("provider-specific remote transport options are unavailable")
    from .remote_worker import run_remote_job as execute_remote_job

    execute_remote_job(
        storage_root,
        job_id,
        settings,
    )


def run_job(storage_root: Path, job_id: str) -> None:
    from .worker import run_job as execute_job

    execute_job(storage_root, job_id)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STORAGE_ROOT = REPO_ROOT / "backend" / "storage"
DEFAULT_TRIMMED_CLIP_PATH = REPO_ROOT / "videos" / "trimed-football-2-1minute.mp4"
DEFAULT_MANUAL_POINTS = [
    HomographyPoint(x=10, y=10),
    HomographyPoint(x=1270, y=10),
    HomographyPoint(x=1270, y=710),
    HomographyPoint(x=10, y=710),
]

MIN_FIVE_MINUTE_SAMPLE_SIZE = 60
MIN_FORTY_FIVE_MINUTE_SAMPLE_SIZE = 300
BALL_EDGE_MARGIN = 5.0
MAX_VIABLE_BALL_EDGE_FRAME_SHARE = 0.6
MIN_MEANINGFUL_BALL_FRAMES = 3
MIN_MEANINGFUL_BALL_SPAN = 4.0
MIN_MEANINGFUL_BALL_PATH = 12.0
NEED_VIABLE_BALL_TRACK_REASON = "Need viable ball track: meaningful motion and edgeFrameShare <= 60%"


class MatchBenchmarkSummary(BaseModel):
    matchId: str
    jobId: str | None = None
    detectorModelPath: str | None = None
    detectorModelName: str | None = None
    artifactOnly: bool = False
    videoPath: str | None = None
    directSeedRetryPolicy: str | None = None
    directSeedRetryScales: list[int] = Field(default_factory=list)
    inputMode: str
    matchStatus: str
    jobStatus: str | None = None
    requiresTeamSelection: bool
    rawRowCount: int = 0
    frameCount: int = 0
    playerFrames: int = 0
    withBallFrames: int = 0
    withBallRatio: float = 0.0
    observedBallFrames: int = 0
    inferredBallFrames: int = 0
    acceptedBallFrames: int = 0
    trackingObservedBallFrames: int = 0
    rawProbeObservedBallFrames: int = 0
    filteredProbeObservedBallFrames: int = 0
    suppressedProbeObservedBallFrames: int = 0
    anchoredProbeObservedBallFrames: int = 0
    bridgeProbeObservedBallFrames: int = 0
    probeObservedBallFrames: int = 0
    probeOnlyObservedBallFrames: int = 0
    acceptedFromObservedFrames: int = 0
    acceptedFromObservedRatio: float = 0.0
    supportedObservedBallFrames: int = 0
    supportedAcceptedBallFrames: int = 0
    supportedAcceptedBallRatio: float = 0.0
    unsupportedAcceptedEdgeFrames: int = 0
    acceptedMatchStateFrames: int = 0
    acceptedMatchStateCoverageRatio: float = 0.0
    visibleStateFrames: int = 0
    inferredStateFrames: int = 0
    hiddenStateFrames: int = 0
    controlledStateFrames: int = 0
    hiddenControlledStateFrames: int = 0
    restartOrOutStateFrames: int = 0
    stateContinuityAppliedFrames: int = 0
    matchStateModeCounts: dict[str, int] = Field(default_factory=dict)
    acceptedBallRatio: float = 0.0
    acceptedSegmentCount: int = 0
    unknownGapCount: int = 0
    longestUnknownGapFrames: int = 0
    trackedPossessionFrames: int = 0
    trackedPossessionRatio: float = 0.0
    controlledPossessionFrames: int = 0
    controlledPossessionRatio: float = 0.0
    eventCount: int = 0
    eventTypes: dict[str, int] = Field(default_factory=dict)
    eventFamilyCount: int = 0
    dominantEventShare: float = 0.0
    shotCount: int = 0
    ballSignalStatus: str | None = None
    ballTrackPathLength: float = 0.0
    ballTrackEdgeFrameShare: float = 0.0
    ballTrackShowsMeaningfulMotion: bool = False
    ballTrackViable: bool = False
    recoveryProfileName: str | None = None
    recoveryApplied: bool = False
    recoveredSelectedFrames: int = 0
    dominantAnchorCoord: list[float] | None = None
    dominantAnchorCount: int = 0
    dominantAnchorShare: float = 0.0
    meanSourceCenterY: float = 0.0
    meanSourceBoxArea: float = 0.0
    recoveredSupportedFrames: int = 0
    recoveredAnchoredFrames: int = 0
    recoveredBridgeFrames: int = 0
    recoveredUnsupportedEdgeFrameShare: float = 0.0
    recoveredAnchoredPathLength: float = 0.0
    corridorCandidateFrames: int = 0
    corridorFramesWithTwoAnchors: int = 0
    corridorFramesWithSingleAnchor: int = 0
    corridorMeanWidth: float = 0.0
    proposalCandidateFrames: int = 0
    proposalWindowCount: int = 0
    proposalFramesWithAnchorSeed: int = 0
    proposalFramesWithoutAnchorSeed: int = 0
    proposalExactSeedFrames: int = 0
    proposalInterpolatedSeedFrames: int = 0
    proposalSingleSeedFrames: int = 0
    proposalUnseededFrames: int = 0
    acceptedMatchStateFrames: int = 0
    acceptedMatchStateCoverageRatio: float = 0.0
    visibleStateFrames: int = 0
    inferredStateFrames: int = 0
    hiddenStateFrames: int = 0
    controlledStateFrames: int = 0
    hiddenControlledStateFrames: int = 0
    restartOrOutStateFrames: int = 0
    stateContinuityAppliedFrames: int = 0
    matchStateModeCounts: dict[str, int] = Field(default_factory=dict)
    proposalMeanWindowWidth: float = 0.0
    bestProposalRawDetectedFrames: int = 0
    bestProposalAfterSeedCollapseFrames: int = 0
    bestProposalAfterFalseBallSuppressionFrames: int = 0
    bestProposalDirectSeedDetectedFrames: int = 0
    bestProposalDirectSeedTightDetectedFrames: int = 0
    bestProposalDirectSeedContextDetectedFrames: int = 0
    bestProposalDirectSeedHiResRetryFrames: int = 0
    bestProposalDirectSeedHiResRetryDetectedFrames: int = 0
    bestProposalDirectSeedZeroDetectFrames: int = 0
    bestProposalDirectSeedScale1600RawDetectionFrames: int = 0
    bestProposalDirectSeedScale960RawDetectionFrames: int = 0
    bestProposalDirectSeedScale1920RawDetectionFrames: int = 0
    bestProposalDirectSeedScale1600CandidateFrames: int = 0
    bestProposalDirectSeedScale960CandidateFrames: int = 0
    bestProposalDirectSeedScale1920CandidateFrames: int = 0
    bestProposalDirectSeedMultiScaleRetryFrames: int = 0
    bestProposalDirectSeedMultiScaleDetectedFrames: int = 0
    bestProposalDirectSeedRawHitFilteredOutFrames: int = 0
    bestProposalDirectSeedCropEdgeRejectedFrames: int = 0
    bestProposalDirectSeedCropCenterYRejectedFrames: int = 0
    bestProposalDirectSeedPitchPolygonRejectedFrames: int = 0
    bestProposalDirectSeedMeanCropArea: float = 0.0
    bestProposalDirectSeedTightMeanCropArea: float = 0.0
    bestProposalDirectSeedContextMeanCropArea: float = 0.0
    bestProposalPlayerRankedMeanCropArea: float = 0.0
    bestProposalDirectSeedMeanDetectedBallBoxArea: float = 0.0
    bestProposalPlayerRankedMeanDetectedBallBoxArea: float = 0.0
    bestProposalDirectSeedContextWindowFrames: int = 0
    bestProposalDirectSeedContextEligibleFrames: int = 0
    bestProposalDirectSeedContextMeanSeedToBoxDistance: float = 0.0
    bestProposalDirectSeedContextExpandedFrames: int = 0
    bestProposalDirectSeedContextMeanExpansionPx: float = 0.0
    bestProposalPlayerRankedDetectedFrames: int = 0
    bestProposalExactSeedDetectedFrames: int = 0
    bestProposalInterpolatedSeedDetectedFrames: int = 0
    bestProposalSingleSeedDetectedFrames: int = 0
    bestProposalProfileName: str | None = None
    bestProposalCandidateFrames: int = 0
    bestProposalSelectedFrames: int = 0
    bestProposalViable: bool = False
    collapsedCandidateFrames: int = 0
    collapsedSegmentCount: int = 0
    collapsedLongestSegmentFrames: int = 0
    continuityPreferredFrames: int = 0
    continuityRejectedFrames: int = 0
    midfieldCollapsedFrames: int = 0
    candidateEdgeShare: float = 0.0
    selectedEdgeFrameShare: float = 0.0
    runtimeFingerprint: dict[str, object] | None = None
    requestedTransport: str | None = None
    resolvedTransport: str | None = None
    remoteRunId: str | None = None
    usedObjectStorage: bool = False
    transportTimedOut: bool = False
    runtimeOutcome: str | None = None
    stageDownloadSeconds: float = 0.0
    stageProcessVideoSeconds: float = 0.0
    stageReturnSeconds: float = 0.0
    workerStartedProcessing: bool = False
    workerReturnedResult: bool = False
    workerHeartbeatEnabled: bool = False
    workerCurrentStage: str | None = None
    workerStageStatus: str | None = None
    workerLastHeartbeatAt: str | None = None
    workerHeartbeatAgeSeconds: float = 0.0
    workerTrackingFramesSeen: int = 0
    workerBlockingStage: str | None = None
    warmProofMode: bool = False
    warmReadyObserved: bool = False
    warmupWaitSeconds: float = 0.0
    longGapTreatmentOutcome: str | None = None
    controlledPossessionAssignmentOutcome: str | None = None
    frozenPrimaryAcquisitionMode: str | None = None
    frozenDetectorModelPath: str | None = None
    fiveMinuteTruthReady: bool = False
    fortyFiveMinuteTruthReady: bool = False
    truthGateReasons: list[str] = Field(default_factory=list)
    artifactPresence: dict[str, bool] = Field(default_factory=dict)


class SelectedClusterBenchmarkSummary(BaseModel):
    clusterId: int
    detectorModelPath: str | None = None
    detectorModelName: str | None = None
    directSeedRetryPolicy: str | None = None
    directSeedRetryScales: list[int] = Field(default_factory=list)
    rawRowCount: int = 0
    frameCount: int = 0
    requiresTeamSelection: bool
    withBallFrames: int = 0
    withBallRatio: float = 0.0
    trackedPossessionFrames: int = 0
    trackedPossessionRatio: float = 0.0
    controlledPossessionFrames: int = 0
    controlledPossessionRatio: float = 0.0
    eventCount: int = 0
    eventTypes: dict[str, int] = Field(default_factory=dict)
    eventFamilyCount: int = 0
    dominantEventShare: float = 0.0
    ballTrackPathLength: float = 0.0
    ballTrackEdgeFrameShare: float = 0.0
    ballTrackShowsMeaningfulMotion: bool = False
    ballTrackViable: bool = False
    corridorCandidateFrames: int = 0
    corridorFramesWithTwoAnchors: int = 0
    corridorFramesWithSingleAnchor: int = 0
    corridorMeanWidth: float = 0.0
    proposalCandidateFrames: int = 0
    proposalWindowCount: int = 0
    proposalFramesWithAnchorSeed: int = 0
    proposalFramesWithoutAnchorSeed: int = 0
    proposalExactSeedFrames: int = 0
    proposalInterpolatedSeedFrames: int = 0
    proposalSingleSeedFrames: int = 0
    proposalUnseededFrames: int = 0
    proposalMeanWindowWidth: float = 0.0
    bestProposalRawDetectedFrames: int = 0
    bestProposalAfterSeedCollapseFrames: int = 0
    bestProposalAfterFalseBallSuppressionFrames: int = 0
    bestProposalDirectSeedDetectedFrames: int = 0
    bestProposalDirectSeedTightDetectedFrames: int = 0
    bestProposalDirectSeedContextDetectedFrames: int = 0
    bestProposalDirectSeedHiResRetryFrames: int = 0
    bestProposalDirectSeedHiResRetryDetectedFrames: int = 0
    bestProposalDirectSeedZeroDetectFrames: int = 0
    bestProposalDirectSeedScale1600RawDetectionFrames: int = 0
    bestProposalDirectSeedScale960RawDetectionFrames: int = 0
    bestProposalDirectSeedScale1920RawDetectionFrames: int = 0
    bestProposalDirectSeedScale1600CandidateFrames: int = 0
    bestProposalDirectSeedScale960CandidateFrames: int = 0
    bestProposalDirectSeedScale1920CandidateFrames: int = 0
    bestProposalDirectSeedMultiScaleRetryFrames: int = 0
    bestProposalDirectSeedMultiScaleDetectedFrames: int = 0
    bestProposalDirectSeedRawHitFilteredOutFrames: int = 0
    bestProposalDirectSeedCropEdgeRejectedFrames: int = 0
    bestProposalDirectSeedCropCenterYRejectedFrames: int = 0
    bestProposalDirectSeedPitchPolygonRejectedFrames: int = 0
    bestProposalDirectSeedMeanCropArea: float = 0.0
    bestProposalDirectSeedTightMeanCropArea: float = 0.0
    bestProposalDirectSeedContextMeanCropArea: float = 0.0
    bestProposalPlayerRankedMeanCropArea: float = 0.0
    bestProposalDirectSeedMeanDetectedBallBoxArea: float = 0.0
    bestProposalPlayerRankedMeanDetectedBallBoxArea: float = 0.0
    bestProposalDirectSeedContextWindowFrames: int = 0
    bestProposalDirectSeedContextEligibleFrames: int = 0
    bestProposalDirectSeedContextMeanSeedToBoxDistance: float = 0.0
    bestProposalDirectSeedContextExpandedFrames: int = 0
    bestProposalDirectSeedContextMeanExpansionPx: float = 0.0
    bestProposalPlayerRankedDetectedFrames: int = 0
    bestProposalExactSeedDetectedFrames: int = 0
    bestProposalInterpolatedSeedDetectedFrames: int = 0
    bestProposalSingleSeedDetectedFrames: int = 0
    bestProposalProfileName: str | None = None
    bestProposalCandidateFrames: int = 0
    bestProposalSelectedFrames: int = 0
    bestProposalViable: bool = False
    collapsedCandidateFrames: int = 0
    collapsedSegmentCount: int = 0
    collapsedLongestSegmentFrames: int = 0
    continuityPreferredFrames: int = 0
    continuityRejectedFrames: int = 0
    midfieldCollapsedFrames: int = 0
    fiveMinuteTruthReady: bool = False
    fortyFiveMinuteTruthReady: bool = False
    truthGateReasons: list[str] = Field(default_factory=list)


def _selected_cluster_summary_from_benchmark(
    cluster_id: int,
    summary: MatchBenchmarkSummary,
) -> SelectedClusterBenchmarkSummary:
    return SelectedClusterBenchmarkSummary(
        clusterId=cluster_id,
        detectorModelPath=summary.detectorModelPath,
        detectorModelName=summary.detectorModelName,
        directSeedRetryPolicy=summary.directSeedRetryPolicy,
        directSeedRetryScales=summary.directSeedRetryScales,
        rawRowCount=summary.rawRowCount,
        frameCount=summary.frameCount,
        requiresTeamSelection=summary.requiresTeamSelection,
        withBallFrames=summary.withBallFrames,
        withBallRatio=summary.withBallRatio,
        trackedPossessionFrames=summary.trackedPossessionFrames,
        trackedPossessionRatio=summary.trackedPossessionRatio,
        controlledPossessionFrames=summary.controlledPossessionFrames,
        controlledPossessionRatio=summary.controlledPossessionRatio,
        eventCount=summary.eventCount,
        eventTypes=summary.eventTypes,
        eventFamilyCount=summary.eventFamilyCount,
        dominantEventShare=summary.dominantEventShare,
        ballTrackPathLength=summary.ballTrackPathLength,
        ballTrackEdgeFrameShare=summary.ballTrackEdgeFrameShare,
        ballTrackShowsMeaningfulMotion=summary.ballTrackShowsMeaningfulMotion,
        ballTrackViable=summary.ballTrackViable,
        corridorCandidateFrames=summary.corridorCandidateFrames,
        corridorFramesWithTwoAnchors=summary.corridorFramesWithTwoAnchors,
        corridorFramesWithSingleAnchor=summary.corridorFramesWithSingleAnchor,
        corridorMeanWidth=summary.corridorMeanWidth,
        proposalCandidateFrames=summary.proposalCandidateFrames,
        proposalWindowCount=summary.proposalWindowCount,
        proposalFramesWithAnchorSeed=summary.proposalFramesWithAnchorSeed,
        proposalFramesWithoutAnchorSeed=summary.proposalFramesWithoutAnchorSeed,
        proposalExactSeedFrames=summary.proposalExactSeedFrames,
        proposalInterpolatedSeedFrames=summary.proposalInterpolatedSeedFrames,
        proposalSingleSeedFrames=summary.proposalSingleSeedFrames,
        proposalUnseededFrames=summary.proposalUnseededFrames,
        acceptedMatchStateFrames=summary.acceptedMatchStateFrames,
        acceptedMatchStateCoverageRatio=summary.acceptedMatchStateCoverageRatio,
        visibleStateFrames=summary.visibleStateFrames,
        inferredStateFrames=summary.inferredStateFrames,
        hiddenStateFrames=summary.hiddenStateFrames,
        controlledStateFrames=summary.controlledStateFrames,
        hiddenControlledStateFrames=summary.hiddenControlledStateFrames,
        restartOrOutStateFrames=summary.restartOrOutStateFrames,
        stateContinuityAppliedFrames=summary.stateContinuityAppliedFrames,
        matchStateModeCounts=summary.matchStateModeCounts,
        proposalMeanWindowWidth=summary.proposalMeanWindowWidth,
        bestProposalRawDetectedFrames=summary.bestProposalRawDetectedFrames,
        bestProposalAfterSeedCollapseFrames=summary.bestProposalAfterSeedCollapseFrames,
        bestProposalAfterFalseBallSuppressionFrames=summary.bestProposalAfterFalseBallSuppressionFrames,
        bestProposalDirectSeedDetectedFrames=summary.bestProposalDirectSeedDetectedFrames,
        bestProposalDirectSeedTightDetectedFrames=summary.bestProposalDirectSeedTightDetectedFrames,
        bestProposalDirectSeedContextDetectedFrames=summary.bestProposalDirectSeedContextDetectedFrames,
        bestProposalDirectSeedHiResRetryFrames=summary.bestProposalDirectSeedHiResRetryFrames,
        bestProposalDirectSeedHiResRetryDetectedFrames=summary.bestProposalDirectSeedHiResRetryDetectedFrames,
        bestProposalDirectSeedZeroDetectFrames=summary.bestProposalDirectSeedZeroDetectFrames,
        bestProposalDirectSeedScale1600RawDetectionFrames=summary.bestProposalDirectSeedScale1600RawDetectionFrames,
        bestProposalDirectSeedScale960RawDetectionFrames=summary.bestProposalDirectSeedScale960RawDetectionFrames,
        bestProposalDirectSeedScale1920RawDetectionFrames=summary.bestProposalDirectSeedScale1920RawDetectionFrames,
        bestProposalDirectSeedScale1600CandidateFrames=summary.bestProposalDirectSeedScale1600CandidateFrames,
        bestProposalDirectSeedScale960CandidateFrames=summary.bestProposalDirectSeedScale960CandidateFrames,
        bestProposalDirectSeedScale1920CandidateFrames=summary.bestProposalDirectSeedScale1920CandidateFrames,
        bestProposalDirectSeedMultiScaleRetryFrames=summary.bestProposalDirectSeedMultiScaleRetryFrames,
        bestProposalDirectSeedMultiScaleDetectedFrames=summary.bestProposalDirectSeedMultiScaleDetectedFrames,
        bestProposalDirectSeedRawHitFilteredOutFrames=summary.bestProposalDirectSeedRawHitFilteredOutFrames,
        bestProposalDirectSeedCropEdgeRejectedFrames=summary.bestProposalDirectSeedCropEdgeRejectedFrames,
        bestProposalDirectSeedCropCenterYRejectedFrames=summary.bestProposalDirectSeedCropCenterYRejectedFrames,
        bestProposalDirectSeedPitchPolygonRejectedFrames=summary.bestProposalDirectSeedPitchPolygonRejectedFrames,
        bestProposalDirectSeedMeanCropArea=summary.bestProposalDirectSeedMeanCropArea,
        bestProposalDirectSeedTightMeanCropArea=summary.bestProposalDirectSeedTightMeanCropArea,
        bestProposalDirectSeedContextMeanCropArea=summary.bestProposalDirectSeedContextMeanCropArea,
        bestProposalPlayerRankedMeanCropArea=summary.bestProposalPlayerRankedMeanCropArea,
        bestProposalDirectSeedMeanDetectedBallBoxArea=summary.bestProposalDirectSeedMeanDetectedBallBoxArea,
        bestProposalPlayerRankedMeanDetectedBallBoxArea=summary.bestProposalPlayerRankedMeanDetectedBallBoxArea,
        bestProposalDirectSeedContextWindowFrames=summary.bestProposalDirectSeedContextWindowFrames,
        bestProposalDirectSeedContextEligibleFrames=summary.bestProposalDirectSeedContextEligibleFrames,
        bestProposalDirectSeedContextMeanSeedToBoxDistance=summary.bestProposalDirectSeedContextMeanSeedToBoxDistance,
        bestProposalDirectSeedContextExpandedFrames=summary.bestProposalDirectSeedContextExpandedFrames,
        bestProposalDirectSeedContextMeanExpansionPx=summary.bestProposalDirectSeedContextMeanExpansionPx,
        bestProposalPlayerRankedDetectedFrames=summary.bestProposalPlayerRankedDetectedFrames,
        bestProposalExactSeedDetectedFrames=summary.bestProposalExactSeedDetectedFrames,
        bestProposalInterpolatedSeedDetectedFrames=summary.bestProposalInterpolatedSeedDetectedFrames,
        bestProposalSingleSeedDetectedFrames=summary.bestProposalSingleSeedDetectedFrames,
        bestProposalProfileName=summary.bestProposalProfileName,
        bestProposalCandidateFrames=summary.bestProposalCandidateFrames,
        bestProposalSelectedFrames=summary.bestProposalSelectedFrames,
        bestProposalViable=summary.bestProposalViable,
        collapsedCandidateFrames=summary.collapsedCandidateFrames,
        collapsedSegmentCount=summary.collapsedSegmentCount,
        collapsedLongestSegmentFrames=summary.collapsedLongestSegmentFrames,
        continuityPreferredFrames=summary.continuityPreferredFrames,
        continuityRejectedFrames=summary.continuityRejectedFrames,
        midfieldCollapsedFrames=summary.midfieldCollapsedFrames,
        fiveMinuteTruthReady=summary.fiveMinuteTruthReady,
        fortyFiveMinuteTruthReady=summary.fortyFiveMinuteTruthReady,
        truthGateReasons=summary.truthGateReasons,
    )


def _summarize_frame_ball_track(frames: list[object]) -> tuple[float, float, bool, bool]:
    ball_positions = [
        (float(frame.ball.x), float(frame.ball.y))
        for frame in frames
        if getattr(frame, "ball", None) is not None
    ]
    if not ball_positions:
        return 0.0, 0.0, False, False

    xs = [position[0] for position in ball_positions]
    ys = [position[1] for position in ball_positions]
    path_length = sum(
        hypot(xs[index] - xs[index - 1], ys[index] - ys[index - 1])
        for index in range(1, len(ball_positions))
    )
    edge_frame_count = sum(
        1
        for x, y in ball_positions
        if (
            x <= BALL_EDGE_MARGIN
            or x >= (100.0 - BALL_EDGE_MARGIN)
            or y <= BALL_EDGE_MARGIN
            or y >= (100.0 - BALL_EDGE_MARGIN)
        )
    )
    edge_frame_share = edge_frame_count / len(ball_positions)
    shows_meaningful_motion = (
        len(ball_positions) >= MIN_MEANINGFUL_BALL_FRAMES
        and (
            max(max(xs) - min(xs), max(ys) - min(ys)) >= MIN_MEANINGFUL_BALL_SPAN
            or path_length >= MIN_MEANINGFUL_BALL_PATH
        )
    )
    return (
        round(path_length, 2),
        round(edge_frame_share, 3),
        shows_meaningful_motion,
        shows_meaningful_motion and edge_frame_share <= MAX_VIABLE_BALL_EDGE_FRAME_SHARE,
    )


def _summarize_ball_rows(ball_rows: list[object]) -> tuple[float, float, bool, bool]:
    ball_positions: list[tuple[float, float]] = []
    for row in ball_rows:
        if not isinstance(row, dict) or row.get("Entity_Type") != "ball":
            continue
        x = _safe_float(row.get("X"), default=float("nan"))
        y = _safe_float(row.get("Y"), default=float("nan"))
        if x != x or y != y:
            continue
        ball_positions.append((x, y))
    if not ball_positions:
        return 0.0, 0.0, False, False

    xs = [position[0] for position in ball_positions]
    ys = [position[1] for position in ball_positions]
    path_length = sum(
        hypot(xs[index] - xs[index - 1], ys[index] - ys[index - 1])
        for index in range(1, len(ball_positions))
    )
    edge_frame_count = sum(
        1
        for x, y in ball_positions
        if (
            x <= BALL_EDGE_MARGIN
            or x >= (100.0 - BALL_EDGE_MARGIN)
            or y <= BALL_EDGE_MARGIN
            or y >= (100.0 - BALL_EDGE_MARGIN)
        )
    )
    edge_frame_share = edge_frame_count / len(ball_positions)
    shows_meaningful_motion = (
        len(ball_positions) >= MIN_MEANINGFUL_BALL_FRAMES
        and (
            max(max(xs) - min(xs), max(ys) - min(ys)) >= MIN_MEANINGFUL_BALL_SPAN
            or path_length >= MIN_MEANINGFUL_BALL_PATH
        )
    )
    return (
        round(path_length, 2),
        round(edge_frame_share, 3),
        shows_meaningful_motion,
        shows_meaningful_motion and edge_frame_share <= MAX_VIABLE_BALL_EDGE_FRAME_SHARE,
    )


def _assess_truth_gates(
    *,
    requires_team_selection: bool,
    tracked_possession_frames: int,
    frame_count: int,
    raw_row_count: int,
    with_ball_frames: int,
    ball_track_viable: bool,
    controlled_possession_frames: int,
    event_types: dict[str, int],
    observed_ball_frames: int,
    inferred_ball_frames: int,
    accepted_ball_frames: int,
    accepted_from_observed_frames: int,
    accepted_from_observed_ratio: float,
    direct_observation_breakdown_present: bool,
    accepted_ball_ratio: float,
    ball_truth_layers_present: bool,
) -> tuple[bool, bool, list[str], float]:
    event_count = sum(event_types.values())
    event_family_count = len(event_types)
    dominant_event_share = round(max(event_types.values()) / event_count, 2) if event_count else 0.0
    reasons: list[str] = []

    sample_size = frame_count
    with_ball_ratio = (with_ball_frames / frame_count) if frame_count else 0.0
    controlled_possession_ratio = (controlled_possession_frames / frame_count) if frame_count else 0.0
    accepted_ball_coverage_ratio = accepted_ball_ratio if ball_truth_layers_present else with_ball_ratio
    coverage_frames_for_viability = accepted_ball_frames if ball_truth_layers_present else with_ball_frames
    ball_signal_present = observed_ball_frames > 0 or inferred_ball_frames > 0

    if sample_size < MIN_FIVE_MINUTE_SAMPLE_SIZE:
        reasons.append(
            f"Need at least {MIN_FIVE_MINUTE_SAMPLE_SIZE} frame time samples for truthful 5-minute analysis"
        )
    if ball_truth_layers_present:
        if ball_signal_present and accepted_ball_coverage_ratio < 0.25:
            reasons.append("Accepted ball layer is still too sparse for truthful 5-10 minute analysis")
        if (
            direct_observation_breakdown_present
            and inferred_ball_frames > 0
            and ball_signal_present
            and accepted_ball_frames > 0
            and accepted_from_observed_frames < accepted_ball_frames
            and accepted_from_observed_ratio < 0.25
        ):
            reasons.append("Direct observed ball remains too sparse for truthful 5-10 minute analysis")
    elif with_ball_ratio < 0.25:
        reasons.append("Need withBallFrames/frameCount >= 25% for truthful 5-10 minute analysis")
    if coverage_frames_for_viability > 0 and not ball_track_viable:
        reasons.append(NEED_VIABLE_BALL_TRACK_REASON)
    if controlled_possession_ratio < 0.20:
        reasons.append("Need controlled possession frames/frameCount >= 20% for truthful 5-10 minute analysis")
    if requires_team_selection and tracked_possession_frames > 0 and controlled_possession_frames == 0:
        reasons.append("Team selection unresolved; controlled possession is provisional until myTeamCluster is chosen")
    if event_family_count < 3:
        reasons.append("Need at least 3 event families")
    if not any(event_type in event_types for event_type in {"pass", "turnover"}):
        reasons.append("Need at least one pass or turnover event")
    if dominant_event_share > 0.80:
        reasons.append("No single event type should exceed 80% of total events")

    five_minute_truth_ready = not reasons

    forty_five_reasons = list(reasons)
    if sample_size < MIN_FORTY_FIVE_MINUTE_SAMPLE_SIZE:
        forty_five_reasons.append(
            f"Need at least {MIN_FORTY_FIVE_MINUTE_SAMPLE_SIZE} frame time samples for a truthful 45-minute half"
        )
    if ball_truth_layers_present:
        if ball_signal_present and accepted_ball_coverage_ratio < 0.40:
            forty_five_reasons.append("Need acceptedBallFrames/frameCount >= 40% for a truthful 45-minute half")
        if (
            direct_observation_breakdown_present
            and inferred_ball_frames > 0
            and ball_signal_present
            and accepted_ball_frames > 0
            and accepted_from_observed_frames < accepted_ball_frames
            and accepted_from_observed_ratio < 0.40
        ):
            forty_five_reasons.append("Direct observed ball remains too sparse for a truthful 45-minute half")
    elif with_ball_ratio < 0.40:
        forty_five_reasons.append("Need withBallFrames/frameCount >= 40% for a truthful 45-minute half")
    if controlled_possession_ratio < 0.30:
        forty_five_reasons.append("Need controlled possession frames/frameCount >= 30% for a truthful 45-minute half")
    if not (
        "pass" in event_types
        and "turnover" in event_types
        and any(event_type in event_types for event_type in {"shot", "tackle", "interception"})
    ):
        forty_five_reasons.append("Need pass + turnover + one of shot/tackle/interception before a truthful 45-minute half")

    forty_five_truth_ready = len(forty_five_reasons) == 0
    return five_minute_truth_ready, forty_five_truth_ready, reasons, dominant_event_share


def _artifact_paths(storage: Storage, match_id: str) -> dict[str, Path]:
    match_dir = storage._match_dir(match_id)
    return {
        "frames": match_dir / "frames.json",
        "analytics": match_dir / "analytics.json",
        "events": match_dir / "events.json",
        "rawRows": match_dir / "raw_rows.json",
    }


def _safe_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_bool(value: object, default: bool = False) -> bool:
    return value if isinstance(value, bool) else default


def _safe_anchor_coord(value: object) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    x = _safe_float(value[0], default=float("nan"))
    y = _safe_float(value[1], default=float("nan"))
    if x != x or y != y:
        return None
    return [x, y]


def _load_ball_truth_layers(storage: Storage, match_id: str) -> dict[str, object] | None:
    ball_truth_layers_path = storage._match_dir(match_id) / "ball_truth_layers.json"
    if not ball_truth_layers_path.exists():
        return None
    payload = storage.load_analysis_artifact(match_id, "ball_truth_layers")
    return payload if isinstance(payload, dict) else None


def _load_remote_artifact(
    storage: Storage,
    match_id: str,
    neutral_name: str,
    historical_name: str,
) -> dict[str, object] | None:
    neutral_path = storage._match_dir(match_id) / f"{neutral_name}.json"
    if neutral_path.exists():
        try:
            payload = storage.load_analysis_artifact(match_id, neutral_name)
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            return None
        return payload if isinstance(payload, dict) else None
    historical_path = storage._match_dir(match_id) / f"{historical_name}.json"
    if not historical_path.exists():
        return None
    try:
        payload = storage.load_analysis_artifact(match_id, historical_name)
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _load_remote_worker_progress(storage: Storage, match_id: str) -> dict[str, object] | None:
    return _load_remote_artifact(
        storage,
        match_id,
        "remote_worker_progress",
        "runpod_worker_progress",
    )


def _load_recovery_profile_matrix(storage: Storage, match_id: str) -> dict[str, object] | None:
    recovery_profile_matrix_path = storage._match_dir(match_id) / "recovery_profile_matrix.json"
    if not recovery_profile_matrix_path.exists():
        return None
    try:
        payload = storage.load_analysis_artifact(match_id, "recovery_profile_matrix")
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _load_accepted_match_state(storage: Storage, match_id: str) -> dict[str, object] | None:
    accepted_match_state_path = storage._match_dir(match_id) / "accepted_match_state.json"
    if not accepted_match_state_path.exists():
        return None
    try:
        payload = storage.load_analysis_artifact(match_id, "accepted_match_state")
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _ball_truth_layer_frame_count(ball_truth_layers: dict[str, object], layer_name: str) -> int:
    layer_payload = ball_truth_layers.get(layer_name)
    if not isinstance(layer_payload, dict):
        return 0
    summary_payload = layer_payload.get("summary")
    if not isinstance(summary_payload, dict):
        return 0
    return _safe_int(summary_payload.get("frameCount"), 0)


def _latest_job_for_match(storage: Storage, match_id: str) -> str | None:
    with storage._connect() as connection:
        row = connection.execute(
            """
            SELECT id
            FROM jobs
            WHERE match_id = ?
            ORDER BY created_at DESC, updated_at DESC, id DESC
            LIMIT 1
            """,
            (match_id,),
        ).fetchone()
    if row is None:
        return None
    return str(row["id"])


def canonicalize_benchmark_video_path(video_path: str | None) -> str | None:
    if not isinstance(video_path, str):
        return None
    normalized = video_path.strip()
    if not normalized:
        return None
    normalized = normalized.replace(
        "/workspace/fotball-analyst/",
        f"{REPO_ROOT}/",
    )
    normalized = normalized.replace(
        f"{REPO_ROOT}/.worktrees/",
        f"{REPO_ROOT}/",
    )
    return normalized


def derive_saved_match_source_clip_id(video_path: str | None) -> str:
    canonical_video_path = canonicalize_benchmark_video_path(video_path)
    if canonical_video_path is None:
        return "unknown-source-clip"
    clip_name = Path(canonical_video_path).name
    return clip_name or canonical_video_path


def discover_saved_match_slice_suite_entries(storage_root: Path, max_entries: int = 10) -> list[dict[str, object]]:
    if max_entries <= 0:
        return []

    matches_root = Path(storage_root) / "matches"
    if not matches_root.exists():
        return []

    required_artifacts = (
        "ball_pipeline_trace.json",
        "ball_truth_layers.json",
        "selected_cluster_delta.json",
        "frames.json",
    )
    entries: list[dict[str, object]] = []
    for match_dir in sorted(path for path in matches_root.iterdir() if path.is_dir()):
        if not all((match_dir / artifact_name).exists() for artifact_name in required_artifacts):
            continue
        try:
            trace_payload = json.loads((match_dir / "ball_pipeline_trace.json").read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            continue
        if trace_payload.get("inputMode") != "video":
            continue
        canonical_video_path = canonicalize_benchmark_video_path(trace_payload.get("videoPath"))
        source_clip_id = derive_saved_match_source_clip_id(canonical_video_path)
        entries.append(
            {
                "entryId": match_dir.name,
                "label": f"Saved slice {match_dir.name[:8]}",
                "sourceType": "saved_match_artifacts",
                "matchId": match_dir.name,
                "sourceClipId": source_clip_id,
                "videoPath": canonical_video_path,
                "notes": "Auto-discovered from saved match artifacts.",
                "tags": ["slice", "saved-artifacts", "frozen-viable-baseline"],
            }
        )
    entries.sort(key=lambda entry: (str(entry["sourceClipId"]), str(entry["matchId"])))

    entries_by_source: dict[str, list[dict[str, object]]] = {}
    for entry in entries:
        source_clip_id = str(entry["sourceClipId"])
        entries_by_source.setdefault(source_clip_id, []).append(entry)

    selected_entries: list[dict[str, object]] = []
    source_order = sorted(entries_by_source)
    source_indices = {source_clip_id: 0 for source_clip_id in source_order}

    while len(selected_entries) < max_entries:
        progress_made = False
        for source_clip_id in source_order:
            source_entries = entries_by_source[source_clip_id]
            source_index = source_indices[source_clip_id]
            if source_index >= len(source_entries):
                continue
            selected_entries.append(source_entries[source_index])
            source_indices[source_clip_id] = source_index + 1
            progress_made = True
            if len(selected_entries) >= max_entries:
                break
        if not progress_made:
            break

    return selected_entries


def _safe_suite_metric(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _suite_metric_stats(values: list[float]) -> tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    return round(float(median(values)), 3), round(min(values), 3), round(max(values), 3)


def _source_failure_signal(summary: dict[str, object]) -> str:
    if _safe_suite_metric(summary.get("medianBallTrackEdgeFrameShare")) > MAX_VIABLE_BALL_EDGE_FRAME_SHARE:
        return "high_ball_track_edge_frame_share"
    if _safe_suite_metric(summary.get("medianAcceptedBallRatio")) < 0.25:
        return "low_accepted_ball_ratio"
    if _safe_suite_metric(summary.get("medianControlledPossessionRatio")) < 0.2:
        return "low_controlled_possession_ratio"
    return "no_material_failure_signal"


def build_benchmark_suite_source_summaries(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    source_rows: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        if row.get("status") != "success":
            continue
        raw_source_clip_id = row.get("sourceClipId")
        source_clip_id = (
            raw_source_clip_id.strip()
            if isinstance(raw_source_clip_id, str) and raw_source_clip_id.strip()
            else "unknown-source-clip"
        )
        source_rows.setdefault(source_clip_id, []).append(row)

    source_summaries: dict[str, dict[str, object]] = {}
    for source_clip_id in sorted(source_rows):
        clip_rows = source_rows[source_clip_id]
        accepted_ratios = [_safe_suite_metric(row.get("acceptedBallRatio")) for row in clip_rows]
        controlled_ratios = [_safe_suite_metric(row.get("controlledPossessionRatio")) for row in clip_rows]
        edge_shares = [_safe_suite_metric(row.get("ballTrackEdgeFrameShare")) for row in clip_rows]
        viable_entry_count = sum(bool(row.get("ballTrackViable")) for row in clip_rows)
        truth_ready_entry_count = sum(bool(row.get("fiveMinuteTruthReady")) for row in clip_rows)
        entry_count = len(clip_rows)
        source_viable = (viable_entry_count / entry_count) >= 0.6 if entry_count else False
        median_accepted_ball_ratio, min_accepted_ball_ratio, max_accepted_ball_ratio = _suite_metric_stats(
            accepted_ratios
        )
        (
            median_controlled_possession_ratio,
            min_controlled_possession_ratio,
            max_controlled_possession_ratio,
        ) = _suite_metric_stats(controlled_ratios)
        median_ball_track_edge_frame_share, _, _ = _suite_metric_stats(edge_shares)
        summary = {
            "sourceClipId": source_clip_id,
            "entryCount": entry_count,
            "viableEntryCount": viable_entry_count,
            "truthReadyEntryCount": truth_ready_entry_count,
            "medianAcceptedBallRatio": median_accepted_ball_ratio,
            "medianControlledPossessionRatio": median_controlled_possession_ratio,
            "medianBallTrackEdgeFrameShare": median_ball_track_edge_frame_share,
            "minAcceptedBallRatio": min_accepted_ball_ratio,
            "maxAcceptedBallRatio": max_accepted_ball_ratio,
            "minControlledPossessionRatio": min_controlled_possession_ratio,
            "maxControlledPossessionRatio": max_controlled_possession_ratio,
            "sourceViable": source_viable,
        }
        summary["sourceFailureSignal"] = _source_failure_signal(summary)
        source_summaries[source_clip_id] = summary
    return source_summaries


def diagnose_benchmark_suite_robustness(
    *,
    suite_summary: dict[str, object],
    source_summaries: dict[str, dict[str, object]],
) -> dict[str, object]:
    distinct_source_clip_count = int(suite_summary.get("distinctSourceClipCount", 0) or 0)
    if distinct_source_clip_count < 2:
        return {
            "robustnessOutcome": "dataset_still_too_narrow",
            "robustnessDominantFailureSignal": "insufficient_source_diversity",
            "robustnessRecommendedNextLever": "expand_clip_manifest",
        }

    viable_sources = [
        summary
        for summary in source_summaries.values()
        if bool(summary.get("sourceViable"))
    ]
    non_viable_sources = [
        summary
        for summary in source_summaries.values()
        if not bool(summary.get("sourceViable"))
    ]

    if viable_sources and len(non_viable_sources) == 1:
        dominant_source = non_viable_sources[0]
        return {
            "robustnessOutcome": "single_source_dominant_failure",
            "robustnessDominantFailureSignal": dominant_source.get(
                "sourceFailureSignal",
                "no_material_failure_signal",
            ),
            "robustnessRecommendedNextLever": "multi_match_robustness_repair",
            "robustnessDominantFailureSourceClipId": dominant_source.get("sourceClipId"),
        }

    diagnosis_pool = non_viable_sources or list(source_summaries.values())
    signal_counts = Counter(
        str(summary.get("sourceFailureSignal", "no_material_failure_signal"))
        for summary in diagnosis_pool
    )
    dominant_failure_signal = signal_counts.most_common(1)[0][0] if signal_counts else "no_material_failure_signal"
    return {
        "robustnessOutcome": "shared_multi_source_failure",
        "robustnessDominantFailureSignal": dominant_failure_signal,
        "robustnessRecommendedNextLever": "multi_match_robustness_repair",
    }


def _load_optional_artifact_payload(
    storage: Storage,
    match_id: str,
    artifact_name: str,
) -> dict[str, object] | None:
    artifact_path = storage._match_dir(match_id) / f"{artifact_name}.json"
    if not artifact_path.exists():
        return None
    try:
        payload = storage.load_analysis_artifact(match_id, artifact_name)
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _artifact_metadata_sources(storage: Storage, match_id: str) -> list[dict[str, object]]:
    sources: list[dict[str, object]] = []

    trace_payload = _load_optional_artifact_payload(storage, match_id, "ball_pipeline_trace")
    if trace_payload is not None:
        sources.append(trace_payload)

    selected_cluster_delta = _load_optional_artifact_payload(storage, match_id, "selected_cluster_delta")
    if selected_cluster_delta is not None:
        delta_after = selected_cluster_delta.get("after")
        if isinstance(delta_after, dict):
            sources.append(delta_after)
        else:
            sources.append(selected_cluster_delta)

    proof_summary = _load_optional_artifact_payload(storage, match_id, "proof_summary")
    if proof_summary is not None:
        sources.append(proof_summary)

    return sources


def _artifact_metadata_string(sources: list[dict[str, object]], key: str) -> str | None:
    for source in sources:
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _artifact_metadata_bool(
    sources: list[dict[str, object]],
    key: str,
    default: bool = False,
) -> bool:
    for source in sources:
        if key in source:
            return _safe_bool(source.get(key), default)
    return default


def summarize_match_benchmark(storage: Storage, match_id: str) -> MatchBenchmarkSummary:
    artifact_metadata_sources = _artifact_metadata_sources(storage, match_id)
    artifact_only = False
    try:
        match = storage.get_match(match_id)
    except KeyError:
        match = None
        artifact_only = True
    job_id = _latest_job_for_match(storage, match_id)
    latest_job = storage.get_job(job_id) if job_id is not None else None
    job_status = latest_job.status if latest_job is not None else None
    summary_job_id = job_id or _artifact_metadata_string(artifact_metadata_sources, "jobId")
    artifact_paths = _artifact_paths(storage, match_id)
    artifact_presence = {name: path.exists() for name, path in artifact_paths.items()}
    summary_video_path = canonicalize_benchmark_video_path(
        _artifact_metadata_string(artifact_metadata_sources, "videoPath")
    )
    if match is not None and match.inputMode == "video":
        try:
            summary_video_path = canonicalize_benchmark_video_path(str(storage.get_match_input_path(match_id)))
        except KeyError:
            pass
    summary_match_id = (
        match.id
        if match is not None
        else (
            _artifact_metadata_string(artifact_metadata_sources, "savedMatchId")
            or _artifact_metadata_string(artifact_metadata_sources, "matchId")
            or match_id
        )
    )
    summary_input_mode = (
        match.inputMode
        if match is not None
        else (_artifact_metadata_string(artifact_metadata_sources, "inputMode") or ("video" if summary_video_path is not None else "unknown"))
    )
    summary_match_status = (
        match.status
        if match is not None
        else (_artifact_metadata_string(artifact_metadata_sources, "matchStatus") or "artifact_only")
    )
    summary_requires_team_selection = (
        match.requiresTeamSelection
        if match is not None
        else _artifact_metadata_bool(artifact_metadata_sources, "requiresTeamSelection", False)
    )

    raw_row_count = 0
    frame_count = 0
    player_frames = 0
    with_ball_frames = 0
    tracked_possession_frames = 0
    controlled_possession_frames = 0
    event_count = 0
    event_types: dict[str, int] = {}
    event_family_count = 0
    dominant_event_share = 0.0
    shot_count = 0
    ball_signal_status = None
    ball_track_path_length = 0.0
    ball_track_edge_frame_share = 0.0
    ball_track_shows_meaningful_motion = False
    ball_track_viable = False
    recovery_profile_name = None
    recovery_applied = False
    recovered_selected_frames = 0
    dominant_anchor_coord: list[float] | None = None
    dominant_anchor_count = 0
    dominant_anchor_share = 0.0
    mean_source_center_y = 0.0
    mean_source_box_area = 0.0
    recovered_supported_frames = 0
    recovered_anchored_frames = 0
    recovered_bridge_frames = 0
    recovered_unsupported_edge_frame_share = 0.0
    recovered_anchored_path_length = 0.0
    corridor_candidate_frames = 0
    corridor_frames_with_two_anchors = 0
    corridor_frames_with_single_anchor = 0
    corridor_mean_width = 0.0
    proposal_candidate_frames = 0
    proposal_window_count = 0
    proposal_frames_with_anchor_seed = 0
    proposal_frames_without_anchor_seed = 0
    proposal_exact_seed_frames = 0
    proposal_interpolated_seed_frames = 0
    proposal_single_seed_frames = 0
    proposal_unseeded_frames = 0
    proposal_mean_window_width = 0.0
    best_proposal_raw_detected_frames = 0
    best_proposal_after_seed_collapse_frames = 0
    best_proposal_after_false_ball_suppression_frames = 0
    best_proposal_direct_seed_detected_frames = 0
    best_proposal_direct_seed_tight_detected_frames = 0
    best_proposal_direct_seed_context_detected_frames = 0
    best_proposal_direct_seed_hi_res_retry_frames = 0
    best_proposal_direct_seed_hi_res_retry_detected_frames = 0
    best_proposal_direct_seed_zero_detect_frames = 0
    best_proposal_direct_seed_scale_1600_raw_detection_frames = 0
    best_proposal_direct_seed_scale_960_raw_detection_frames = 0
    best_proposal_direct_seed_scale_1920_raw_detection_frames = 0
    best_proposal_direct_seed_scale_1600_candidate_frames = 0
    best_proposal_direct_seed_scale_960_candidate_frames = 0
    best_proposal_direct_seed_scale_1920_candidate_frames = 0
    best_proposal_direct_seed_multi_scale_retry_frames = 0
    best_proposal_direct_seed_multi_scale_detected_frames = 0
    best_proposal_direct_seed_raw_hit_filtered_out_frames = 0
    best_proposal_direct_seed_crop_edge_rejected_frames = 0
    best_proposal_direct_seed_crop_center_y_rejected_frames = 0
    best_proposal_direct_seed_pitch_polygon_rejected_frames = 0
    best_proposal_direct_seed_mean_crop_area = 0.0
    best_proposal_direct_seed_tight_mean_crop_area = 0.0
    best_proposal_direct_seed_context_mean_crop_area = 0.0
    best_proposal_player_ranked_mean_crop_area = 0.0
    best_proposal_direct_seed_mean_detected_ball_box_area = 0.0
    best_proposal_player_ranked_mean_detected_ball_box_area = 0.0
    best_proposal_direct_seed_context_window_frames = 0
    best_proposal_direct_seed_context_eligible_frames = 0
    best_proposal_direct_seed_context_mean_seed_to_box_distance = 0.0
    best_proposal_direct_seed_context_expanded_frames = 0
    best_proposal_direct_seed_context_mean_expansion_px = 0.0
    best_proposal_player_ranked_detected_frames = 0
    best_proposal_exact_seed_detected_frames = 0
    best_proposal_interpolated_seed_detected_frames = 0
    best_proposal_single_seed_detected_frames = 0
    best_proposal_profile_name: str | None = None
    best_proposal_candidate_frames = 0
    best_proposal_selected_frames = 0
    best_proposal_viable = False
    collapsed_candidate_frames = 0
    collapsed_segment_count = 0
    collapsed_longest_segment_frames = 0
    continuity_preferred_frames = 0
    continuity_rejected_frames = 0
    midfield_collapsed_frames = 0
    candidate_edge_share = 0.0
    selected_edge_frame_share = 0.0
    accepted_match_state_frames = 0
    accepted_match_state_coverage_ratio = 0.0
    visible_state_frames = 0
    inferred_state_frames = 0
    hidden_state_frames = 0
    controlled_state_frames = 0
    hidden_controlled_state_frames = 0
    restart_or_out_state_frames = 0
    state_continuity_applied_frames = 0
    match_state_mode_counts: dict[str, int] = {}
    runtime_fingerprint: dict[str, object] | None = None
    detector_model_path: str | None = None
    detector_model_name: str | None = None
    direct_seed_retry_policy: str | None = None
    direct_seed_retry_scales: list[int] = []
    requested_transport: str | None = None
    resolved_transport: str | None = None
    remote_run_id = latest_job.remoteRunId if latest_job is not None else None
    used_object_storage = False
    transport_timed_out = False
    runtime_outcome: str | None = None
    stage_download_seconds = 0.0
    stage_process_video_seconds = 0.0
    stage_return_seconds = 0.0
    worker_started_processing = False
    worker_returned_result = False
    worker_heartbeat_enabled = False
    worker_current_stage: str | None = None
    worker_stage_status: str | None = None
    worker_last_heartbeat_at: str | None = None
    worker_heartbeat_age_seconds = 0.0
    worker_tracking_frames_seen = 0
    worker_blocking_stage: str | None = None
    warm_proof_mode = False
    warm_ready_observed = False
    warmup_wait_seconds = 0.0
    long_gap_treatment_outcome: str | None = None
    controlled_possession_assignment_outcome: str | None = None
    proof_runtime_options = load_proof_runtime_options(
        storage, match_id, manifest_path=RUNTIME_MANIFEST_PATH
    )
    frozen_primary_acquisition_mode = proof_runtime_options.primary_acquisition_mode
    frozen_detector_model_path = (
        proof_runtime_options.primary_model.artifact_id
        if proof_runtime_options.primary_model.kind == "artifact"
        else json.dumps(proof_runtime_options.primary_model.to_provenance_mapping(), sort_keys=True)
    )
    truth_gate_reasons: list[str] = []
    five_minute_truth_ready = False
    forty_five_minute_truth_ready = False

    if artifact_presence["rawRows"]:
        raw_row_count = len(storage.load_raw_rows(match_id))
    if artifact_presence["frames"]:
        frames = storage.load_frames(match_id)
        frame_count = len(frames)
        player_frames = sum(
            1
            for frame in frames
            if frame.myTeam or frame.enemies or frame.unassignedPlayers
        )
        with_ball_frames = sum(1 for frame in frames if frame.ball is not None)
        (
            ball_track_path_length,
            ball_track_edge_frame_share,
            ball_track_shows_meaningful_motion,
            ball_track_viable,
        ) = _summarize_frame_ball_track(frames)
    if artifact_presence["events"]:
        events = storage.load_events(match_id)
        event_count = len(events)
        event_types = dict(sorted(Counter(event.type for event in events).items()))
        event_family_count = len(event_types)
    if artifact_presence["analytics"]:
        analytics_payload = json.loads(artifact_paths["analytics"].read_text(encoding="utf-8"))
        shot_count = len(analytics_payload.get("shots", []))
        summary, assignments, _, _ = storage.load_analytics(match_id)
        ball_signal_status = summary.ballSignalStatus
        tracked_possession_frames = sum(1 for assignment in assignments if assignment.team in {"my_team", "enemy", "unassigned"} and assignment.trackId is not None)
        controlled_possession_frames = sum(1 for assignment in assignments if assignment.team in {"my_team", "enemy"})
    accepted_match_state = _load_accepted_match_state(storage, match_id)
    if accepted_match_state is not None:
        raw_state_frames = accepted_match_state.get("frames")
        if isinstance(raw_state_frames, list):
            accepted_match_state_frames = len(raw_state_frames)
            state_mode_counter: Counter[str] = Counter()
            for item in raw_state_frames:
                if not isinstance(item, dict):
                    continue
                mode = item.get("mode")
                if isinstance(mode, str):
                    state_mode_counter[mode] += 1
                visibility = item.get("ballVisibility")
                if visibility == "visible":
                    visible_state_frames += 1
                elif visibility == "inferred":
                    inferred_state_frames += 1
                elif visibility == "hidden":
                    hidden_state_frames += 1
                if mode == "controlled_possession":
                    controlled_state_frames += 1
                    if visibility == "hidden":
                        hidden_controlled_state_frames += 1
                if mode == "restart_or_out":
                    restart_or_out_state_frames += 1
            match_state_mode_counts = dict(sorted(state_mode_counter.items()))
            accepted_match_state_coverage_ratio = round(
                (sum(count for mode, count in state_mode_counter.items() if mode != "unknown") / accepted_match_state_frames)
                if accepted_match_state_frames
                else 0.0,
                3,
            )
        state_continuity_applied_frames = _safe_int(
            accepted_match_state.get("stateContinuityAppliedFrames", 0),
            0,
        )
    recovery_debug_path = storage._match_dir(match_id) / "recovery_debug.json"
    recovery_debug: dict[str, object] | None = None
    if recovery_debug_path.exists():
        try:
            loaded_recovery_debug = storage.load_analysis_artifact(match_id, "recovery_debug")
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            loaded_recovery_debug = None
        if isinstance(loaded_recovery_debug, dict):
            recovery_debug = loaded_recovery_debug
    if recovery_debug is not None:
        raw_recovery_profile_name = recovery_debug.get("recoveryProfileName")
        recovery_profile_name = raw_recovery_profile_name if isinstance(raw_recovery_profile_name, str) else None
        recovery_applied = _safe_bool(recovery_debug.get("recoveryApplied", False))
        recovered_selected_frames = _safe_int(recovery_debug.get("recoveredSelectedFrames", 0))
        dominant_anchor_coord = _safe_anchor_coord(recovery_debug.get("dominantAnchorCoord"))
        dominant_anchor_count = _safe_int(recovery_debug.get("dominantAnchorCount", 0))
        dominant_anchor_share = round(_safe_float(recovery_debug.get("dominantAnchorShare", 0.0)), 3)
        mean_source_center_y = round(_safe_float(recovery_debug.get("meanSourceCenterY", 0.0)), 2)
        mean_source_box_area = round(_safe_float(recovery_debug.get("meanSourceBoxArea", 0.0)), 2)
        recovered_supported_frames = _safe_int(recovery_debug.get("recoveredSupportedFrames", 0), 0)
        recovered_anchored_frames = _safe_int(recovery_debug.get("recoveredAnchoredFrames", 0), 0)
        recovered_bridge_frames = _safe_int(recovery_debug.get("recoveredBridgeFrames", 0), 0)
        recovered_unsupported_edge_frame_share = round(
            _safe_float(recovery_debug.get("recoveredUnsupportedEdgeFrameShare", 0.0), 0.0),
            3,
        )
        recovered_anchored_path_length = round(
            _safe_float(recovery_debug.get("recoveredAnchoredPathLength", 0.0), 0.0),
            2,
        )
        corridor_candidate_frames = _safe_int(recovery_debug.get("corridorCandidateFrames", 0), 0)
        corridor_frames_with_two_anchors = _safe_int(recovery_debug.get("corridorFramesWithTwoAnchors", 0), 0)
        corridor_frames_with_single_anchor = _safe_int(
            recovery_debug.get("corridorFramesWithSingleAnchor", 0),
            0,
        )
        corridor_mean_width = round(_safe_float(recovery_debug.get("corridorMeanWidth", 0.0)), 2)
        proposal_candidate_frames = _safe_int(recovery_debug.get("proposalCandidateFrames", 0), 0)
        proposal_window_count = _safe_int(recovery_debug.get("proposalWindowCount", 0), 0)
        proposal_frames_with_anchor_seed = _safe_int(
            recovery_debug.get("proposalFramesWithAnchorSeed", 0),
            0,
        )
        proposal_frames_without_anchor_seed = _safe_int(
            recovery_debug.get("proposalFramesWithoutAnchorSeed", 0),
            0,
        )
        proposal_exact_seed_frames = _safe_int(recovery_debug.get("proposalExactSeedFrames", 0), 0)
        proposal_interpolated_seed_frames = _safe_int(
            recovery_debug.get("proposalInterpolatedSeedFrames", 0),
            0,
        )
        proposal_single_seed_frames = _safe_int(recovery_debug.get("proposalSingleSeedFrames", 0), 0)
        proposal_unseeded_frames = _safe_int(recovery_debug.get("proposalUnseededFrames", 0), 0)
        proposal_mean_window_width = round(_safe_float(recovery_debug.get("proposalMeanWindowWidth", 0.0)), 2)
        collapsed_candidate_frames = _safe_int(recovery_debug.get("collapsedCandidateFrames", 0), 0)
        collapsed_segment_count = _safe_int(recovery_debug.get("collapsedSegmentCount", 0), 0)
        collapsed_longest_segment_frames = _safe_int(
            recovery_debug.get("collapsedLongestSegmentFrames", 0),
            0,
        )
        continuity_preferred_frames = _safe_int(recovery_debug.get("continuityPreferredFrames", 0), 0)
        continuity_rejected_frames = _safe_int(recovery_debug.get("continuityRejectedFrames", 0), 0)
        midfield_collapsed_frames = _safe_int(recovery_debug.get("midfieldCollapsedFrames", 0), 0)
        candidate_edge_share = round(_safe_float(recovery_debug.get("candidateEdgeShare", 0.0)), 3)
        selected_edge_frame_share = round(_safe_float(recovery_debug.get("selectedEdgeFrameShare", 0.0)), 3)
    recovery_profile_matrix = _load_recovery_profile_matrix(storage, match_id)
    if recovery_profile_matrix is not None:
        raw_profiles = recovery_profile_matrix.get("profiles")
        if isinstance(raw_profiles, list):
            proposal_profiles = [
                profile
                for profile in raw_profiles
                if isinstance(profile, dict) and profile.get("cropMode") == "proposal_windows"
            ]
            if proposal_profiles:
                best_proposal_profile = sorted(
                    proposal_profiles,
                    key=lambda profile: (
                        -int(_safe_bool(profile.get("viable"), False)),
                        -_safe_int(profile.get("selectedFrames", 0), 0),
                        -_safe_int(profile.get("candidateFrames", 0), 0),
                        str(profile.get("name", "")),
                    ),
                )[0]
                raw_best_proposal_profile_name = best_proposal_profile.get("name")
                if isinstance(raw_best_proposal_profile_name, str) and raw_best_proposal_profile_name.strip():
                    best_proposal_profile_name = raw_best_proposal_profile_name.strip()
                best_proposal_candidate_frames = _safe_int(
                    best_proposal_profile.get("proposalCandidateFrames", best_proposal_profile.get("candidateFrames", 0)),
                    0,
                )
                best_proposal_raw_detected_frames = _safe_int(
                    best_proposal_profile.get("proposalRawDetectedFrames", 0),
                    0,
                )
                best_proposal_after_seed_collapse_frames = _safe_int(
                    best_proposal_profile.get("proposalAfterSeedCollapseFrames", 0),
                    0,
                )
                best_proposal_after_false_ball_suppression_frames = _safe_int(
                    best_proposal_profile.get("proposalAfterFalseBallSuppressionFrames", 0),
                    0,
                )
                best_proposal_direct_seed_detected_frames = _safe_int(
                    best_proposal_profile.get("proposalDirectSeedDetectedFrames", 0),
                    0,
                )
                best_proposal_direct_seed_tight_detected_frames = _safe_int(
                    best_proposal_profile.get("proposalDirectSeedTightDetectedFrames", 0),
                    0,
                )
                best_proposal_direct_seed_context_detected_frames = _safe_int(
                    best_proposal_profile.get("proposalDirectSeedContextDetectedFrames", 0),
                    0,
                )
                best_proposal_direct_seed_hi_res_retry_frames = _safe_int(
                    best_proposal_profile.get("proposalDirectSeedHiResRetryFrames", 0),
                    0,
                )
                best_proposal_direct_seed_hi_res_retry_detected_frames = _safe_int(
                    best_proposal_profile.get("proposalDirectSeedHiResRetryDetectedFrames", 0),
                    0,
                )
                best_proposal_direct_seed_zero_detect_frames = _safe_int(
                    best_proposal_profile.get("proposalDirectSeedZeroDetectFrames", 0),
                    0,
                )
                best_proposal_direct_seed_scale_1600_raw_detection_frames = _safe_int(
                    best_proposal_profile.get("proposalDirectSeedScale1600RawDetectionFrames", 0),
                    0,
                )
                best_proposal_direct_seed_scale_960_raw_detection_frames = _safe_int(
                    best_proposal_profile.get("proposalDirectSeedScale960RawDetectionFrames", 0),
                    0,
                )
                best_proposal_direct_seed_scale_1920_raw_detection_frames = _safe_int(
                    best_proposal_profile.get("proposalDirectSeedScale1920RawDetectionFrames", 0),
                    0,
                )
                best_proposal_direct_seed_scale_1600_candidate_frames = _safe_int(
                    best_proposal_profile.get("proposalDirectSeedScale1600CandidateFrames", 0),
                    0,
                )
                best_proposal_direct_seed_scale_960_candidate_frames = _safe_int(
                    best_proposal_profile.get("proposalDirectSeedScale960CandidateFrames", 0),
                    0,
                )
                best_proposal_direct_seed_scale_1920_candidate_frames = _safe_int(
                    best_proposal_profile.get("proposalDirectSeedScale1920CandidateFrames", 0),
                    0,
                )
                best_proposal_direct_seed_multi_scale_retry_frames = _safe_int(
                    best_proposal_profile.get("proposalDirectSeedMultiScaleRetryFrames", 0),
                    0,
                )
                best_proposal_direct_seed_multi_scale_detected_frames = _safe_int(
                    best_proposal_profile.get("proposalDirectSeedMultiScaleDetectedFrames", 0),
                    0,
                )
                best_proposal_direct_seed_raw_hit_filtered_out_frames = _safe_int(
                    best_proposal_profile.get("proposalDirectSeedRawHitFilteredOutFrames", 0),
                    0,
                )
                best_proposal_direct_seed_crop_edge_rejected_frames = _safe_int(
                    best_proposal_profile.get("proposalDirectSeedCropEdgeRejectedFrames", 0),
                    0,
                )
                best_proposal_direct_seed_crop_center_y_rejected_frames = _safe_int(
                    best_proposal_profile.get("proposalDirectSeedCropCenterYRejectedFrames", 0),
                    0,
                )
                best_proposal_direct_seed_pitch_polygon_rejected_frames = _safe_int(
                    best_proposal_profile.get("proposalDirectSeedPitchPolygonRejectedFrames", 0),
                    0,
                )
                best_proposal_direct_seed_mean_crop_area = round(
                    _safe_float(best_proposal_profile.get("proposalDirectSeedMeanCropArea", 0.0), 0.0),
                    2,
                )
                best_proposal_direct_seed_tight_mean_crop_area = round(
                    _safe_float(best_proposal_profile.get("proposalDirectSeedTightMeanCropArea", 0.0), 0.0),
                    2,
                )
                best_proposal_direct_seed_context_mean_crop_area = round(
                    _safe_float(best_proposal_profile.get("proposalDirectSeedContextMeanCropArea", 0.0), 0.0),
                    2,
                )
                best_proposal_player_ranked_mean_crop_area = round(
                    _safe_float(best_proposal_profile.get("proposalPlayerRankedMeanCropArea", 0.0), 0.0),
                    2,
                )
                best_proposal_direct_seed_mean_detected_ball_box_area = round(
                    _safe_float(best_proposal_profile.get("proposalDirectSeedMeanDetectedBallBoxArea", 0.0), 0.0),
                    2,
                )
                best_proposal_player_ranked_mean_detected_ball_box_area = round(
                    _safe_float(best_proposal_profile.get("proposalPlayerRankedMeanDetectedBallBoxArea", 0.0), 0.0),
                    2,
                )
                best_proposal_direct_seed_context_window_frames = _safe_int(
                    best_proposal_profile.get("proposalDirectSeedContextWindowFrames", 0),
                    0,
                )
                best_proposal_direct_seed_context_eligible_frames = _safe_int(
                    best_proposal_profile.get("proposalDirectSeedContextEligibleFrames", 0),
                    0,
                )
                best_proposal_direct_seed_context_mean_seed_to_box_distance = round(
                    _safe_float(best_proposal_profile.get("proposalDirectSeedContextMeanSeedToBoxDistance", 0.0), 0.0),
                    2,
                )
                best_proposal_direct_seed_context_expanded_frames = _safe_int(
                    best_proposal_profile.get("proposalDirectSeedContextExpandedFrames", 0),
                    0,
                )
                best_proposal_direct_seed_context_mean_expansion_px = round(
                    _safe_float(best_proposal_profile.get("proposalDirectSeedContextMeanExpansionPx", 0.0), 0.0),
                    2,
                )
                best_proposal_player_ranked_detected_frames = _safe_int(
                    best_proposal_profile.get("proposalPlayerRankedDetectedFrames", 0),
                    0,
                )
                best_proposal_exact_seed_detected_frames = _safe_int(
                    best_proposal_profile.get("proposalExactSeedDetectedFrames", 0),
                    0,
                )
                best_proposal_interpolated_seed_detected_frames = _safe_int(
                    best_proposal_profile.get("proposalInterpolatedSeedDetectedFrames", 0),
                    0,
                )
                best_proposal_single_seed_detected_frames = _safe_int(
                    best_proposal_profile.get("proposalSingleSeedDetectedFrames", 0),
                    0,
                )
                best_proposal_selected_frames = _safe_int(best_proposal_profile.get("selectedFrames", 0), 0)
                best_proposal_viable = _safe_bool(best_proposal_profile.get("viable"), False)
    ball_pipeline_trace_path = storage._match_dir(match_id) / "ball_pipeline_trace.json"
    if ball_pipeline_trace_path.exists():
        ball_pipeline_trace = storage.load_analysis_artifact(match_id, "ball_pipeline_trace")
        raw_video_path = ball_pipeline_trace.get("videoPath")
        if summary_video_path is None and isinstance(raw_video_path, str) and raw_video_path.strip():
            summary_video_path = canonicalize_benchmark_video_path(raw_video_path)
        raw_detector_model_path = ball_pipeline_trace.get("detectorModelPath")
        if isinstance(raw_detector_model_path, str) and raw_detector_model_path.strip():
            detector_model_path = raw_detector_model_path.strip()
        raw_detector_model_name = ball_pipeline_trace.get("detectorModelName")
        if isinstance(raw_detector_model_name, str) and raw_detector_model_name.strip():
            detector_model_name = raw_detector_model_name.strip()
        raw_direct_seed_retry_policy = ball_pipeline_trace.get("directSeedRetryPolicy")
        if isinstance(raw_direct_seed_retry_policy, str) and raw_direct_seed_retry_policy.strip():
            direct_seed_retry_policy = raw_direct_seed_retry_policy.strip()
        raw_direct_seed_retry_scales = ball_pipeline_trace.get("directSeedRetryScales")
        if isinstance(raw_direct_seed_retry_scales, list):
            direct_seed_retry_scales = [
                int(scale)
                for scale in raw_direct_seed_retry_scales
                if isinstance(scale, (int, float))
            ]
        raw_runtime_fingerprint = ball_pipeline_trace.get("runtimeFingerprint")
        if isinstance(raw_runtime_fingerprint, dict):
            normalized_runtime_fingerprint: dict[str, object] = {}
            for key in ("configuredImageName", "imageTag", "gitSha", "buildLabel"):
                value = raw_runtime_fingerprint.get(key)
                if isinstance(value, str) and value.strip():
                    normalized_runtime_fingerprint[key] = value.strip()
            raw_dependencies = raw_runtime_fingerprint.get("handlerDependencyVersions")
            if isinstance(raw_dependencies, dict):
                normalized_dependencies: dict[str, str] = {}
                for dependency_name in ("python", "opencv", "ultralytics"):
                    dependency_version = raw_dependencies.get(dependency_name)
                    if isinstance(dependency_version, str) and dependency_version.strip():
                        normalized_dependencies[dependency_name] = dependency_version.strip()
                if normalized_dependencies:
                    normalized_runtime_fingerprint["handlerDependencyVersions"] = normalized_dependencies
            runtime_fingerprint = normalized_runtime_fingerprint or None
    if detector_model_path is None:
        detector_model_path = (
            _artifact_metadata_string(artifact_metadata_sources, "detectorModelPath")
            or frozen_detector_model_path
        )
    if detector_model_name is None:
        detector_model_name = (
            _artifact_metadata_string(artifact_metadata_sources, "detectorModelName")
            or detector_model_path
        )
    transport_debug = _load_remote_artifact(
        storage,
        match_id,
        "remote_transport_debug",
        "runpod_transport_debug",
    )
    if transport_debug is not None:
        raw_requested_transport = transport_debug.get("requestedTransport")
        if isinstance(raw_requested_transport, str) and raw_requested_transport.strip():
            requested_transport = raw_requested_transport.strip()
        raw_resolved_transport = transport_debug.get("resolvedTransport")
        if isinstance(raw_resolved_transport, str) and raw_resolved_transport.strip():
            resolved_transport = raw_resolved_transport.strip()
        raw_initial_run_id = transport_debug.get("initialRunId")
        if remote_run_id is None and isinstance(raw_initial_run_id, str) and raw_initial_run_id.strip():
            remote_run_id = raw_initial_run_id.strip()
        used_object_storage = _safe_bool(transport_debug.get("usedObjectStorage"), False)
        transport_timed_out = _safe_bool(transport_debug.get("transportTimedOut"), False)
        raw_runtime_outcome = transport_debug.get("runtimeOutcome")
        if isinstance(raw_runtime_outcome, str) and raw_runtime_outcome.strip():
            runtime_outcome = raw_runtime_outcome.strip()
        stage_download_seconds = round(_safe_float(transport_debug.get("stageDownloadSeconds"), 0.0), 6)
        stage_process_video_seconds = round(_safe_float(transport_debug.get("stageProcessVideoSeconds"), 0.0), 6)
        stage_return_seconds = round(_safe_float(transport_debug.get("stageReturnSeconds"), 0.0), 6)
        worker_started_processing = _safe_bool(transport_debug.get("workerStartedProcessing"), False)
        worker_returned_result = _safe_bool(transport_debug.get("workerReturnedResult"), False)
        worker_heartbeat_enabled = _safe_bool(transport_debug.get("workerHeartbeatEnabled"), False)
        worker_current_stage = transport_debug.get("workerCurrentStage") if isinstance(transport_debug.get("workerCurrentStage"), str) else None
        worker_stage_status = transport_debug.get("workerStageStatus") if isinstance(transport_debug.get("workerStageStatus"), str) else None
        raw_worker_last_heartbeat_at = transport_debug.get("workerLastHeartbeatAt")
        if isinstance(raw_worker_last_heartbeat_at, str) and raw_worker_last_heartbeat_at.strip():
            worker_last_heartbeat_at = raw_worker_last_heartbeat_at.strip()
        worker_heartbeat_age_seconds = round(_safe_float(transport_debug.get("workerHeartbeatAgeSeconds"), 0.0), 3)
        worker_tracking_frames_seen = _safe_int(transport_debug.get("workerTrackingFramesSeen"), 0)
        raw_worker_blocking_stage = transport_debug.get("workerBlockingStage")
        if isinstance(raw_worker_blocking_stage, str) and raw_worker_blocking_stage.strip():
            worker_blocking_stage = raw_worker_blocking_stage.strip()
        raw_worker_progress = transport_debug.get("workerProgress")
        if isinstance(raw_worker_progress, dict):
            worker_heartbeat_enabled = True
            if worker_current_stage is None:
                raw_worker_stage = raw_worker_progress.get(
                    "workerStage", raw_worker_progress.get("stage")
                )
                if isinstance(raw_worker_stage, str) and raw_worker_stage.strip():
                    worker_current_stage = raw_worker_stage.strip()
            if worker_stage_status is None:
                raw_worker_stage_status = raw_worker_progress.get(
                    "stageStatus", raw_worker_progress.get("message")
                )
                if isinstance(raw_worker_stage_status, str) and raw_worker_stage_status.strip():
                    worker_stage_status = raw_worker_stage_status.strip()
            if worker_last_heartbeat_at is None:
                raw_worker_last_heartbeat_at = raw_worker_progress.get(
                    "heartbeatAt", raw_worker_progress.get("timestamp")
                )
                if isinstance(raw_worker_last_heartbeat_at, str) and raw_worker_last_heartbeat_at.strip():
                    worker_last_heartbeat_at = raw_worker_last_heartbeat_at.strip()
            worker_heartbeat_age_seconds = max(
                worker_heartbeat_age_seconds,
                round(_safe_float(raw_worker_progress.get("workerHeartbeatAgeSeconds"), worker_heartbeat_age_seconds), 3),
            )
            worker_tracking_frames_seen = max(
                worker_tracking_frames_seen,
                _safe_int(raw_worker_progress.get("trackingFramesSeen"), worker_tracking_frames_seen),
            )
    worker_progress = _load_remote_worker_progress(storage, match_id)
    if worker_progress is not None:
        worker_heartbeat_enabled = True
        raw_worker_stage = worker_progress.get("workerStage", worker_progress.get("stage"))
        if worker_current_stage is None and isinstance(raw_worker_stage, str) and raw_worker_stage.strip():
            worker_current_stage = raw_worker_stage.strip()
        raw_worker_stage_status = worker_progress.get(
            "stageStatus", worker_progress.get("message")
        )
        if worker_stage_status is None and isinstance(raw_worker_stage_status, str) and raw_worker_stage_status.strip():
            worker_stage_status = raw_worker_stage_status.strip()
        raw_worker_last_heartbeat_at = worker_progress.get(
            "heartbeatAt", worker_progress.get("timestamp")
        )
        if worker_last_heartbeat_at is None and isinstance(raw_worker_last_heartbeat_at, str) and raw_worker_last_heartbeat_at.strip():
            worker_last_heartbeat_at = raw_worker_last_heartbeat_at.strip()
        worker_heartbeat_age_seconds = max(
            worker_heartbeat_age_seconds,
            round(_safe_float(worker_progress.get("workerHeartbeatAgeSeconds"), worker_heartbeat_age_seconds), 3),
        )
        worker_tracking_frames_seen = max(
            worker_tracking_frames_seen,
            _safe_int(worker_progress.get("trackingFramesSeen"), worker_tracking_frames_seen),
        )
    endpoint_lifecycle_debug_path = storage._match_dir(match_id) / "endpoint_lifecycle_debug.json"
    if endpoint_lifecycle_debug_path.exists():
        endpoint_lifecycle_debug = storage.load_analysis_artifact(match_id, "endpoint_lifecycle_debug")
        warm_proof_mode = _safe_bool(endpoint_lifecycle_debug.get("warmProofMode"), False)
        warm_ready_observed = _safe_bool(endpoint_lifecycle_debug.get("warmReadyObserved"), False)
        warmup_wait_seconds = round(_safe_float(endpoint_lifecycle_debug.get("warmupWaitSeconds"), 0.0), 3)

    ball_truth_layers = _load_ball_truth_layers(storage, match_id)
    ball_truth_layers_present = ball_truth_layers is not None
    observed_ball_frames = 0
    inferred_ball_frames = 0
    accepted_ball_frames = with_ball_frames
    tracking_observed_ball_frames = 0
    raw_probe_observed_ball_frames = 0
    filtered_probe_observed_ball_frames = 0
    suppressed_probe_observed_ball_frames = 0
    anchored_probe_observed_ball_frames = 0
    bridge_probe_observed_ball_frames = 0
    probe_observed_ball_frames = 0
    probe_only_observed_ball_frames = 0
    accepted_from_observed_frames = 0
    accepted_from_observed_ratio = 0.0
    supported_observed_ball_frames = 0
    supported_accepted_ball_frames = 0
    supported_accepted_ball_ratio = 0.0
    unsupported_accepted_edge_frames = 0
    direct_observation_breakdown_present = False
    accepted_ball_ratio = (with_ball_frames / frame_count) if frame_count else 0.0
    accepted_segment_count = 0
    unknown_gap_count = 0
    longest_unknown_gap_frames = 0
    accepted_ball_rows: list[object] | None = None
    if ball_truth_layers_present:
        observed_ball_frames = _ball_truth_layer_frame_count(ball_truth_layers, "observedBall")
        inferred_ball_frames = _ball_truth_layer_frame_count(ball_truth_layers, "inferredBall")
        accepted_ball_frames = _ball_truth_layer_frame_count(ball_truth_layers, "acceptedBall")
        accepted_ball_ratio = (accepted_ball_frames / frame_count) if frame_count else 0.0
        accepted_layer_payload = ball_truth_layers.get("acceptedBall")
        if isinstance(accepted_layer_payload, dict):
            raw_accepted_rows = accepted_layer_payload.get("rows")
            if isinstance(raw_accepted_rows, list):
                accepted_ball_rows = raw_accepted_rows
        accepted_segments = ball_truth_layers.get("acceptedSegments")
        if isinstance(accepted_segments, list):
            accepted_segment_count = len(accepted_segments)
        unknown_gaps = ball_truth_layers.get("unknownGaps")
        if isinstance(unknown_gaps, list):
            unknown_gap_count = len(unknown_gaps)
            longest_unknown_gap_frames = max(
                (_safe_int(gap.get("frameCount"), 0) for gap in unknown_gaps if isinstance(gap, dict)),
                default=0,
            )
        if accepted_ball_rows is not None:
            (
                ball_track_path_length,
                ball_track_edge_frame_share,
                ball_track_shows_meaningful_motion,
                ball_track_viable,
            ) = _summarize_ball_rows(accepted_ball_rows)
        direct_observation_breakdown = ball_truth_layers.get("directObservationBreakdown")
        if isinstance(direct_observation_breakdown, dict):
            direct_observation_breakdown_present = True
            raw_long_gap_treatment_outcome = direct_observation_breakdown.get("longGapTreatmentOutcome")
            if isinstance(raw_long_gap_treatment_outcome, str) and raw_long_gap_treatment_outcome.strip():
                long_gap_treatment_outcome = raw_long_gap_treatment_outcome.strip()
            raw_controlled_assignment_outcome = direct_observation_breakdown.get(
                "controlledPossessionAssignmentOutcome"
            )
            if (
                isinstance(raw_controlled_assignment_outcome, str)
                and raw_controlled_assignment_outcome.strip()
            ):
                controlled_possession_assignment_outcome = raw_controlled_assignment_outcome.strip()
            raw_frozen_primary_acquisition_mode = direct_observation_breakdown.get(
                "frozenPrimaryAcquisitionMode"
            )
            if (
                isinstance(raw_frozen_primary_acquisition_mode, str)
                and raw_frozen_primary_acquisition_mode.strip()
            ):
                frozen_primary_acquisition_mode = raw_frozen_primary_acquisition_mode.strip()
            raw_frozen_detector_model_path = direct_observation_breakdown.get("frozenDetectorModelPath")
            if (
                isinstance(raw_frozen_detector_model_path, str)
                and raw_frozen_detector_model_path.strip()
            ):
                frozen_detector_model_path = _redacted_runtime_reference_identity(
                    raw_frozen_detector_model_path
                )
            tracking_observed_ball_frames = _safe_int(
                direct_observation_breakdown.get("trackingObservedBallFrames"),
                observed_ball_frames,
            )
            raw_probe_observed_ball_frames = _safe_int(
                direct_observation_breakdown.get("rawProbeObservedBallFrames"),
                _safe_int(
                    direct_observation_breakdown.get("probeObservedBallFrames"),
                    observed_ball_frames,
                ),
            )
            filtered_probe_observed_ball_frames = _safe_int(
                direct_observation_breakdown.get("filteredProbeObservedBallFrames"),
                _safe_int(
                    direct_observation_breakdown.get("probeObservedBallFrames"),
                    observed_ball_frames,
                ),
            )
            suppressed_probe_observed_ball_frames = _safe_int(
                direct_observation_breakdown.get("suppressedProbeObservedBallFrames"),
                max(raw_probe_observed_ball_frames - filtered_probe_observed_ball_frames, 0),
            )
            anchored_probe_observed_ball_frames = _safe_int(
                direct_observation_breakdown.get("anchoredProbeObservedBallFrames"),
                0,
            )
            bridge_probe_observed_ball_frames = _safe_int(
                direct_observation_breakdown.get("bridgeProbeObservedBallFrames"),
                0,
            )
            probe_observed_ball_frames = _safe_int(
                direct_observation_breakdown.get("probeObservedBallFrames"),
                filtered_probe_observed_ball_frames,
            )
            probe_only_observed_ball_frames = _safe_int(
                direct_observation_breakdown.get("probeOnlyObservedBallFrames"),
                max(probe_observed_ball_frames - tracking_observed_ball_frames, 0),
            )
            accepted_from_observed_frames = _safe_int(
                direct_observation_breakdown.get("acceptedFromObservedFrames"),
                observed_ball_frames,
            )
            accepted_from_observed_ratio = round(
                _safe_float(
                    direct_observation_breakdown.get("acceptedFromObservedRatio"),
                    (accepted_from_observed_frames / accepted_ball_frames) if accepted_ball_frames else 0.0,
                ),
                3,
            )
        else:
            tracking_observed_ball_frames = observed_ball_frames
            raw_probe_observed_ball_frames = observed_ball_frames
            filtered_probe_observed_ball_frames = observed_ball_frames
            suppressed_probe_observed_ball_frames = 0
            anchored_probe_observed_ball_frames = 0
            bridge_probe_observed_ball_frames = 0
            probe_observed_ball_frames = observed_ball_frames
            probe_only_observed_ball_frames = 0
            accepted_from_observed_frames = observed_ball_frames
            accepted_from_observed_ratio = round(
                (accepted_from_observed_frames / accepted_ball_frames) if accepted_ball_frames else 0.0,
                3,
            )
        support_diagnostics = ball_truth_layers.get("supportDiagnostics")
        if isinstance(support_diagnostics, dict):
            supported_observed_ball_frames = _safe_int(
                support_diagnostics.get("supportedObservedBallFrames"),
                0,
            )
            supported_accepted_ball_frames = _safe_int(
                support_diagnostics.get("supportedAcceptedBallFrames"),
                0,
            )
            supported_accepted_ball_ratio = round(
                _safe_float(
                    support_diagnostics.get("supportedAcceptedBallRatio"),
                    (supported_accepted_ball_frames / accepted_ball_frames) if accepted_ball_frames else 0.0,
                ),
                3,
            )
            unsupported_accepted_edge_frames = _safe_int(
                support_diagnostics.get("unsupportedAcceptedEdgeFrames"),
                0,
            )
    if long_gap_treatment_outcome is None:
        long_gap_treatment_outcome = _artifact_metadata_string(
            artifact_metadata_sources,
            "longGapTreatmentOutcome",
        )
    if controlled_possession_assignment_outcome is None:
        controlled_possession_assignment_outcome = _artifact_metadata_string(
            artifact_metadata_sources,
            "controlledPossessionAssignmentOutcome",
        )

    five_minute_truth_ready, forty_five_minute_truth_ready, truth_gate_reasons, dominant_event_share = _assess_truth_gates(
        requires_team_selection=summary_requires_team_selection,
        tracked_possession_frames=tracked_possession_frames,
        frame_count=frame_count,
        raw_row_count=raw_row_count,
        with_ball_frames=with_ball_frames,
        ball_track_viable=ball_track_viable,
        controlled_possession_frames=controlled_possession_frames,
        event_types=event_types,
        observed_ball_frames=observed_ball_frames,
        inferred_ball_frames=inferred_ball_frames,
        accepted_ball_frames=accepted_ball_frames,
        accepted_from_observed_frames=accepted_from_observed_frames,
        accepted_from_observed_ratio=accepted_from_observed_ratio,
        direct_observation_breakdown_present=direct_observation_breakdown_present,
        accepted_ball_ratio=accepted_ball_ratio,
        ball_truth_layers_present=ball_truth_layers_present,
    )

    return MatchBenchmarkSummary(
        matchId=summary_match_id,
        jobId=summary_job_id,
        detectorModelPath=detector_model_path,
        detectorModelName=detector_model_name,
        artifactOnly=artifact_only,
        videoPath=summary_video_path,
        directSeedRetryPolicy=direct_seed_retry_policy,
        directSeedRetryScales=direct_seed_retry_scales,
        inputMode=summary_input_mode,
        matchStatus=summary_match_status,
        jobStatus=job_status,
        requiresTeamSelection=summary_requires_team_selection,
        rawRowCount=raw_row_count,
        frameCount=frame_count,
        playerFrames=player_frames,
        withBallFrames=with_ball_frames,
        withBallRatio=(with_ball_frames / frame_count) if frame_count else 0.0,
        observedBallFrames=observed_ball_frames,
        inferredBallFrames=inferred_ball_frames,
        acceptedBallFrames=accepted_ball_frames,
        trackingObservedBallFrames=tracking_observed_ball_frames,
        rawProbeObservedBallFrames=raw_probe_observed_ball_frames,
        filteredProbeObservedBallFrames=filtered_probe_observed_ball_frames,
        suppressedProbeObservedBallFrames=suppressed_probe_observed_ball_frames,
        anchoredProbeObservedBallFrames=anchored_probe_observed_ball_frames,
        bridgeProbeObservedBallFrames=bridge_probe_observed_ball_frames,
        probeObservedBallFrames=probe_observed_ball_frames,
        probeOnlyObservedBallFrames=probe_only_observed_ball_frames,
        acceptedFromObservedFrames=accepted_from_observed_frames,
        acceptedFromObservedRatio=accepted_from_observed_ratio,
        supportedObservedBallFrames=supported_observed_ball_frames,
        supportedAcceptedBallFrames=supported_accepted_ball_frames,
        supportedAcceptedBallRatio=supported_accepted_ball_ratio,
        unsupportedAcceptedEdgeFrames=unsupported_accepted_edge_frames,
        acceptedMatchStateFrames=accepted_match_state_frames,
        acceptedMatchStateCoverageRatio=accepted_match_state_coverage_ratio,
        visibleStateFrames=visible_state_frames,
        inferredStateFrames=inferred_state_frames,
        hiddenStateFrames=hidden_state_frames,
        controlledStateFrames=controlled_state_frames,
        hiddenControlledStateFrames=hidden_controlled_state_frames,
        restartOrOutStateFrames=restart_or_out_state_frames,
        stateContinuityAppliedFrames=state_continuity_applied_frames,
        matchStateModeCounts=match_state_mode_counts,
        acceptedBallRatio=accepted_ball_ratio,
        acceptedSegmentCount=accepted_segment_count,
        unknownGapCount=unknown_gap_count,
        longestUnknownGapFrames=longest_unknown_gap_frames,
        trackedPossessionFrames=tracked_possession_frames,
        trackedPossessionRatio=(tracked_possession_frames / frame_count) if frame_count else 0.0,
        controlledPossessionFrames=controlled_possession_frames,
        controlledPossessionRatio=(controlled_possession_frames / frame_count) if frame_count else 0.0,
        eventCount=event_count,
        eventTypes=event_types,
        eventFamilyCount=event_family_count,
        dominantEventShare=dominant_event_share,
        shotCount=shot_count,
        ballSignalStatus=ball_signal_status,
        ballTrackPathLength=ball_track_path_length,
        ballTrackEdgeFrameShare=ball_track_edge_frame_share,
        ballTrackShowsMeaningfulMotion=ball_track_shows_meaningful_motion,
        ballTrackViable=ball_track_viable,
        recoveryProfileName=recovery_profile_name,
        recoveryApplied=recovery_applied,
        recoveredSelectedFrames=recovered_selected_frames,
        dominantAnchorCoord=dominant_anchor_coord,
        dominantAnchorCount=dominant_anchor_count,
        dominantAnchorShare=dominant_anchor_share,
        meanSourceCenterY=mean_source_center_y,
        meanSourceBoxArea=mean_source_box_area,
        recoveredSupportedFrames=recovered_supported_frames,
        recoveredAnchoredFrames=recovered_anchored_frames,
        recoveredBridgeFrames=recovered_bridge_frames,
        recoveredUnsupportedEdgeFrameShare=recovered_unsupported_edge_frame_share,
        recoveredAnchoredPathLength=recovered_anchored_path_length,
        corridorCandidateFrames=corridor_candidate_frames,
        corridorFramesWithTwoAnchors=corridor_frames_with_two_anchors,
        corridorFramesWithSingleAnchor=corridor_frames_with_single_anchor,
        corridorMeanWidth=corridor_mean_width,
        proposalCandidateFrames=proposal_candidate_frames,
        proposalWindowCount=proposal_window_count,
        proposalFramesWithAnchorSeed=proposal_frames_with_anchor_seed,
        proposalFramesWithoutAnchorSeed=proposal_frames_without_anchor_seed,
        proposalExactSeedFrames=proposal_exact_seed_frames,
        proposalInterpolatedSeedFrames=proposal_interpolated_seed_frames,
        proposalSingleSeedFrames=proposal_single_seed_frames,
        proposalUnseededFrames=proposal_unseeded_frames,
        proposalMeanWindowWidth=proposal_mean_window_width,
        bestProposalRawDetectedFrames=best_proposal_raw_detected_frames,
        bestProposalAfterSeedCollapseFrames=best_proposal_after_seed_collapse_frames,
        bestProposalAfterFalseBallSuppressionFrames=best_proposal_after_false_ball_suppression_frames,
        bestProposalDirectSeedDetectedFrames=best_proposal_direct_seed_detected_frames,
        bestProposalDirectSeedTightDetectedFrames=best_proposal_direct_seed_tight_detected_frames,
        bestProposalDirectSeedContextDetectedFrames=best_proposal_direct_seed_context_detected_frames,
        bestProposalDirectSeedHiResRetryFrames=best_proposal_direct_seed_hi_res_retry_frames,
        bestProposalDirectSeedHiResRetryDetectedFrames=best_proposal_direct_seed_hi_res_retry_detected_frames,
        bestProposalDirectSeedZeroDetectFrames=best_proposal_direct_seed_zero_detect_frames,
        bestProposalDirectSeedScale1600RawDetectionFrames=best_proposal_direct_seed_scale_1600_raw_detection_frames,
        bestProposalDirectSeedScale960RawDetectionFrames=best_proposal_direct_seed_scale_960_raw_detection_frames,
        bestProposalDirectSeedScale1920RawDetectionFrames=best_proposal_direct_seed_scale_1920_raw_detection_frames,
        bestProposalDirectSeedScale1600CandidateFrames=best_proposal_direct_seed_scale_1600_candidate_frames,
        bestProposalDirectSeedScale960CandidateFrames=best_proposal_direct_seed_scale_960_candidate_frames,
        bestProposalDirectSeedScale1920CandidateFrames=best_proposal_direct_seed_scale_1920_candidate_frames,
        bestProposalDirectSeedMultiScaleRetryFrames=best_proposal_direct_seed_multi_scale_retry_frames,
        bestProposalDirectSeedMultiScaleDetectedFrames=best_proposal_direct_seed_multi_scale_detected_frames,
        bestProposalDirectSeedRawHitFilteredOutFrames=best_proposal_direct_seed_raw_hit_filtered_out_frames,
        bestProposalDirectSeedCropEdgeRejectedFrames=best_proposal_direct_seed_crop_edge_rejected_frames,
        bestProposalDirectSeedCropCenterYRejectedFrames=best_proposal_direct_seed_crop_center_y_rejected_frames,
        bestProposalDirectSeedPitchPolygonRejectedFrames=best_proposal_direct_seed_pitch_polygon_rejected_frames,
        bestProposalDirectSeedMeanCropArea=best_proposal_direct_seed_mean_crop_area,
        bestProposalDirectSeedTightMeanCropArea=best_proposal_direct_seed_tight_mean_crop_area,
        bestProposalDirectSeedContextMeanCropArea=best_proposal_direct_seed_context_mean_crop_area,
        bestProposalPlayerRankedMeanCropArea=best_proposal_player_ranked_mean_crop_area,
        bestProposalDirectSeedMeanDetectedBallBoxArea=best_proposal_direct_seed_mean_detected_ball_box_area,
        bestProposalPlayerRankedMeanDetectedBallBoxArea=best_proposal_player_ranked_mean_detected_ball_box_area,
        bestProposalDirectSeedContextWindowFrames=best_proposal_direct_seed_context_window_frames,
        bestProposalDirectSeedContextEligibleFrames=best_proposal_direct_seed_context_eligible_frames,
        bestProposalDirectSeedContextMeanSeedToBoxDistance=best_proposal_direct_seed_context_mean_seed_to_box_distance,
        bestProposalDirectSeedContextExpandedFrames=best_proposal_direct_seed_context_expanded_frames,
        bestProposalDirectSeedContextMeanExpansionPx=best_proposal_direct_seed_context_mean_expansion_px,
        bestProposalPlayerRankedDetectedFrames=best_proposal_player_ranked_detected_frames,
        bestProposalExactSeedDetectedFrames=best_proposal_exact_seed_detected_frames,
        bestProposalInterpolatedSeedDetectedFrames=best_proposal_interpolated_seed_detected_frames,
        bestProposalSingleSeedDetectedFrames=best_proposal_single_seed_detected_frames,
        bestProposalProfileName=best_proposal_profile_name,
        bestProposalCandidateFrames=best_proposal_candidate_frames,
        bestProposalSelectedFrames=best_proposal_selected_frames,
        bestProposalViable=best_proposal_viable,
        collapsedCandidateFrames=collapsed_candidate_frames,
        collapsedSegmentCount=collapsed_segment_count,
        collapsedLongestSegmentFrames=collapsed_longest_segment_frames,
        continuityPreferredFrames=continuity_preferred_frames,
        continuityRejectedFrames=continuity_rejected_frames,
        midfieldCollapsedFrames=midfield_collapsed_frames,
        candidateEdgeShare=candidate_edge_share,
        selectedEdgeFrameShare=selected_edge_frame_share,
        runtimeFingerprint=runtime_fingerprint,
        requestedTransport=requested_transport,
        resolvedTransport=resolved_transport,
        remoteRunId=remote_run_id,
        usedObjectStorage=used_object_storage,
        transportTimedOut=transport_timed_out,
        runtimeOutcome=runtime_outcome,
        stageDownloadSeconds=stage_download_seconds,
        stageProcessVideoSeconds=stage_process_video_seconds,
        stageReturnSeconds=stage_return_seconds,
        workerStartedProcessing=worker_started_processing,
        workerReturnedResult=worker_returned_result,
        workerHeartbeatEnabled=worker_heartbeat_enabled,
        workerCurrentStage=worker_current_stage,
        workerStageStatus=worker_stage_status,
        workerLastHeartbeatAt=worker_last_heartbeat_at,
        workerHeartbeatAgeSeconds=worker_heartbeat_age_seconds,
        workerTrackingFramesSeen=worker_tracking_frames_seen,
        workerBlockingStage=worker_blocking_stage,
        warmProofMode=warm_proof_mode,
        warmReadyObserved=warm_ready_observed,
        warmupWaitSeconds=warmup_wait_seconds,
        longGapTreatmentOutcome=long_gap_treatment_outcome,
        controlledPossessionAssignmentOutcome=controlled_possession_assignment_outcome,
        frozenPrimaryAcquisitionMode=frozen_primary_acquisition_mode,
        frozenDetectorModelPath=frozen_detector_model_path,
        fiveMinuteTruthReady=five_minute_truth_ready,
        fortyFiveMinuteTruthReady=forty_five_minute_truth_ready,
        truthGateReasons=truth_gate_reasons,
        artifactPresence=artifact_presence,
    )


def probe_selected_cluster_benchmarks(storage: Storage, match_id: str) -> list[SelectedClusterBenchmarkSummary]:
    match = storage.get_match(match_id)
    if not match.teamClusters:
        return []

    original_config = match.config.model_copy(deep=True)
    cluster_ids = sorted(cluster.clusterId for cluster in match.teamClusters)
    probes: list[SelectedClusterBenchmarkSummary] = []

    try:
        for cluster_id in cluster_ids:
            storage.update_match_config(
                match_id,
                MatchConfig(**{**original_config.model_dump(), "myTeamCluster": cluster_id}),
            )
            reprocess_video_match(storage, match_id)
            summary = summarize_match_benchmark(storage, match_id)
            probes.append(_selected_cluster_summary_from_benchmark(cluster_id, summary))
    finally:
        storage.update_match_config(match_id, original_config)
        reprocess_video_match(storage, match_id)

    return probes


def recommend_selected_cluster_benchmark(
    probes: list[SelectedClusterBenchmarkSummary],
) -> SelectedClusterBenchmarkSummary | None:
    if not probes:
        return None
    return sorted(
        probes,
        key=lambda probe: (
            -probe.controlledPossessionFrames,
            -probe.eventFamilyCount,
            -probe.withBallFrames,
            probe.clusterId,
        ),
    )[0]


def build_selected_cluster_payload(storage: Storage, match_id: str) -> dict[str, object]:
    match = storage.get_match(match_id)
    probes = probe_selected_cluster_benchmarks(storage, match_id)
    recommended = recommend_selected_cluster_benchmark(probes)

    selected_cluster_probe: dict[str, object] | None = None
    if match.config.myTeamCluster is not None:
        summary = summarize_match_benchmark(storage, match_id)
        selected_cluster_probe = _selected_cluster_summary_from_benchmark(
            match.config.myTeamCluster,
            summary,
        ).model_dump(mode="json")

    return {
        "selectedClusterProbe": selected_cluster_probe,
        "selectedClusters": [probe.model_dump(mode="json") for probe in probes],
        "recommendedCluster": recommended.model_dump(mode="json") if recommended is not None else None,
    }


def promote_selected_cluster_benchmark(
    storage: Storage,
    match_id: str,
    *,
    cluster_id: int | None = None,
) -> dict[str, object]:
    before = summarize_match_benchmark(storage, match_id)
    selected_cluster_id = cluster_id
    if selected_cluster_id is None:
        recommended = recommend_selected_cluster_benchmark(probe_selected_cluster_benchmarks(storage, match_id))
        if recommended is None:
            raise ValueError(f"Match {match_id} has no detected team clusters to promote.")
        selected_cluster_id = recommended.clusterId

    match = storage.get_match(match_id)
    updated_config = MatchConfig(**{**match.config.model_dump(), "myTeamCluster": selected_cluster_id})
    storage.update_match_config(match_id, updated_config)
    reprocess_video_match(storage, match_id)
    after = summarize_match_benchmark(storage, match_id)

    improved_fields: list[str] = []
    for field_name in (
        "withBallFrames",
        "trackedPossessionFrames",
        "controlledPossessionFrames",
        "eventCount",
        "eventFamilyCount",
    ):
        if getattr(after, field_name) > getattr(before, field_name):
            improved_fields.append(field_name)
    if after.fiveMinuteTruthReady and not before.fiveMinuteTruthReady:
        improved_fields.append("fiveMinuteTruthReady")

    payload = {
        "savedMatchId": match_id,
        "selectedClusterId": selected_cluster_id,
        "before": before.model_dump(mode="json"),
        "after": after.model_dump(mode="json"),
        "improvedFields": improved_fields,
        "remainingTruthGateReasons": after.truthGateReasons,
    }
    storage.save_analysis_artifact(match_id, "selected_cluster_delta", payload)
    return payload


def rerun_trimmed_clip_manual(
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    clip_path: Path = DEFAULT_TRIMMED_CLIP_PATH,
    manual_points: list[HomographyPoint] | None = None,
) -> MatchBenchmarkSummary:
    storage = Storage(storage_root)
    config = MatchConfig(
        attackDirection="left_to_right",
        manualHomographyPoints=manual_points or DEFAULT_MANUAL_POINTS,
        autoHomography=False,
    )
    match = storage.create_match(
        name=f"{clip_path.stem}-manual-benchmark",
        input_mode="video",
        original_filename=clip_path.name,
        input_path=clip_path,
        config=config,
    )
    save_proof_runtime_options(
        storage,
        match.id,
        model_path=None,
        primary_acquisition_mode=DEFAULT_PRIMARY_ACQUISITION_MODE,
    )
    job = storage.create_job(match.id)
    run_job(storage_root, job.id)
    summary = summarize_match_benchmark(storage, match.id)
    save_canonical_proof_summary(storage, match.id, summary)
    return summary


def run_remote_video_benchmark(
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    clip_path: Path = DEFAULT_TRIMMED_CLIP_PATH,
    manual_points: list[HomographyPoint] | None = None,
    settings: ProcessingSettings | None = None,
    name: str | None = None,
    use_runsync: bool = False,
    model_path: str | None = None,
    primary_acquisition_mode: str = DEFAULT_PRIMARY_ACQUISITION_MODE,
    edge_share_repair_profile: str | None = None,
) -> MatchBenchmarkSummary:
    clip_path = clip_path.resolve(strict=True)
    storage_root = storage_root.resolve()
    storage = Storage(storage_root)
    config = MatchConfig(
        attackDirection="left_to_right",
        manualHomographyPoints=manual_points or DEFAULT_MANUAL_POINTS,
        autoHomography=False,
    )
    match = storage.create_match(
        name=name or f"{clip_path.stem}-remote-benchmark",
        input_mode="video",
        original_filename=clip_path.name,
        input_path=clip_path,
        config=config,
    )
    save_proof_runtime_options(
        storage,
        match.id,
        model_path=model_path,
        primary_acquisition_mode=primary_acquisition_mode,
        edge_share_repair_profile=edge_share_repair_profile,
    )
    job = storage.create_job(match.id)
    run_remote_job(storage_root, job.id, settings=settings, use_runsync=use_runsync)
    summary = summarize_match_benchmark(storage, match.id)
    save_canonical_proof_summary(storage, match.id, summary)
    return summary
