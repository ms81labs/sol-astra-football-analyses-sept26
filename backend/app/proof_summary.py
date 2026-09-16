from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .storage import Storage


REQUIRED_JUDGE_FIELDS = (
    "acceptedBallFrames",
    "supportedAcceptedBallRatio",
    "controlledPossessionFrames",
    "eventFamilyCount",
    "truthGateReasons",
)


def _normalize_source(source: object) -> dict[str, object]:
    if source is None:
        return {}
    if hasattr(source, "model_dump"):
        payload = source.model_dump(mode="json")
        return dict(payload) if isinstance(payload, Mapping) else {}
    if isinstance(source, Mapping):
        return dict(source)
    return {}


def _first_present(sources: list[dict[str, object]], *aliases: str) -> object | None:
    for source in sources:
        for alias in aliases:
            if alias in source and source.get(alias) is not None:
                return source.get(alias)
    return None


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
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n", ""}:
            return False
    return default


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _int_dict(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    payload: dict[str, int] = {}
    for key, raw_value in value.items():
        payload[str(key)] = _safe_int(raw_value, 0)
    return payload


def _event_family_count(explicit_value: object, event_types: dict[str, int]) -> int:
    if explicit_value is not None:
        return _safe_int(explicit_value, 0)
    return sum(1 for count in event_types.values() if count > 0)


def build_canonical_proof_summary(*sources: object) -> dict[str, object]:
    normalized_sources = [_normalize_source(source) for source in sources]
    event_types = _int_dict(_first_present(normalized_sources, "eventTypes"))
    truth_gate_reasons = _string_list(_first_present(normalized_sources, "truthGateReasons"))
    saved_match_id = _string_or_none(_first_present(normalized_sources, "savedMatchId", "matchId"))

    payload = {
        "savedMatchId": saved_match_id,
        "jobId": _string_or_none(_first_present(normalized_sources, "jobId")),
        "detectorModelPath": _string_or_none(_first_present(normalized_sources, "detectorModelPath")),
        "detectorModelName": _string_or_none(_first_present(normalized_sources, "detectorModelName")),
        "rawRows": _safe_int(_first_present(normalized_sources, "rawRows", "rawRowCount"), 0),
        "frameCount": _safe_int(_first_present(normalized_sources, "frameCount"), 0),
        "playerFrames": _safe_int(_first_present(normalized_sources, "playerFrames"), 0),
        "ballFrames": _safe_int(_first_present(normalized_sources, "ballFrames", "withBallFrames"), 0),
        "observedBallFrames": _safe_int(_first_present(normalized_sources, "observedBallFrames"), 0),
        "inferredBallFrames": _safe_int(_first_present(normalized_sources, "inferredBallFrames"), 0),
        "acceptedBallFrames": _safe_int(_first_present(normalized_sources, "acceptedBallFrames"), 0),
        "trackingObservedBallFrames": _safe_int(_first_present(normalized_sources, "trackingObservedBallFrames"), 0),
        "rawProbeObservedBallFrames": _safe_int(_first_present(normalized_sources, "rawProbeObservedBallFrames"), 0),
        "filteredProbeObservedBallFrames": _safe_int(_first_present(normalized_sources, "filteredProbeObservedBallFrames"), 0),
        "suppressedProbeObservedBallFrames": _safe_int(_first_present(normalized_sources, "suppressedProbeObservedBallFrames"), 0),
        "anchoredProbeObservedBallFrames": _safe_int(_first_present(normalized_sources, "anchoredProbeObservedBallFrames"), 0),
        "bridgeProbeObservedBallFrames": _safe_int(_first_present(normalized_sources, "bridgeProbeObservedBallFrames"), 0),
        "probeObservedBallFrames": _safe_int(_first_present(normalized_sources, "probeObservedBallFrames"), 0),
        "probeOnlyObservedBallFrames": _safe_int(_first_present(normalized_sources, "probeOnlyObservedBallFrames"), 0),
        "acceptedFromObservedFrames": _safe_int(_first_present(normalized_sources, "acceptedFromObservedFrames"), 0),
        "acceptedFromObservedRatio": _safe_float(_first_present(normalized_sources, "acceptedFromObservedRatio"), 0.0),
        "supportedObservedBallFrames": _safe_int(_first_present(normalized_sources, "supportedObservedBallFrames"), 0),
        "supportedAcceptedBallFrames": _safe_int(_first_present(normalized_sources, "supportedAcceptedBallFrames"), 0),
        "supportedAcceptedBallRatio": _safe_float(_first_present(normalized_sources, "supportedAcceptedBallRatio"), 0.0),
        "unsupportedAcceptedEdgeFrames": _safe_int(_first_present(normalized_sources, "unsupportedAcceptedEdgeFrames"), 0),
        "acceptedMatchStateFrames": _safe_int(_first_present(normalized_sources, "acceptedMatchStateFrames"), 0),
        "acceptedMatchStateCoverageRatio": _safe_float(_first_present(normalized_sources, "acceptedMatchStateCoverageRatio"), 0.0),
        "visibleStateFrames": _safe_int(_first_present(normalized_sources, "visibleStateFrames"), 0),
        "inferredStateFrames": _safe_int(_first_present(normalized_sources, "inferredStateFrames"), 0),
        "hiddenStateFrames": _safe_int(_first_present(normalized_sources, "hiddenStateFrames"), 0),
        "controlledStateFrames": _safe_int(_first_present(normalized_sources, "controlledStateFrames"), 0),
        "hiddenControlledStateFrames": _safe_int(_first_present(normalized_sources, "hiddenControlledStateFrames"), 0),
        "restartOrOutStateFrames": _safe_int(_first_present(normalized_sources, "restartOrOutStateFrames"), 0),
        "stateContinuityAppliedFrames": _safe_int(_first_present(normalized_sources, "stateContinuityAppliedFrames"), 0),
        "matchStateModeCounts": _int_dict(_first_present(normalized_sources, "matchStateModeCounts")),
        "recoveredSupportedFrames": _safe_int(_first_present(normalized_sources, "recoveredSupportedFrames"), 0),
        "recoveredAnchoredFrames": _safe_int(_first_present(normalized_sources, "recoveredAnchoredFrames"), 0),
        "recoveredBridgeFrames": _safe_int(_first_present(normalized_sources, "recoveredBridgeFrames"), 0),
        "recoveredUnsupportedEdgeFrameShare": _safe_float(_first_present(normalized_sources, "recoveredUnsupportedEdgeFrameShare"), 0.0),
        "recoveredAnchoredPathLength": _safe_float(_first_present(normalized_sources, "recoveredAnchoredPathLength"), 0.0),
        "corridorCandidateFrames": _safe_int(_first_present(normalized_sources, "corridorCandidateFrames"), 0),
        "corridorFramesWithTwoAnchors": _safe_int(_first_present(normalized_sources, "corridorFramesWithTwoAnchors"), 0),
        "corridorFramesWithSingleAnchor": _safe_int(_first_present(normalized_sources, "corridorFramesWithSingleAnchor"), 0),
        "corridorMeanWidth": _safe_float(_first_present(normalized_sources, "corridorMeanWidth"), 0.0),
        "proposalCandidateFrames": _safe_int(_first_present(normalized_sources, "proposalCandidateFrames"), 0),
        "proposalWindowCount": _safe_int(_first_present(normalized_sources, "proposalWindowCount"), 0),
        "proposalFramesWithAnchorSeed": _safe_int(_first_present(normalized_sources, "proposalFramesWithAnchorSeed"), 0),
        "proposalFramesWithoutAnchorSeed": _safe_int(_first_present(normalized_sources, "proposalFramesWithoutAnchorSeed"), 0),
        "proposalExactSeedFrames": _safe_int(_first_present(normalized_sources, "proposalExactSeedFrames"), 0),
        "proposalInterpolatedSeedFrames": _safe_int(_first_present(normalized_sources, "proposalInterpolatedSeedFrames"), 0),
        "proposalSingleSeedFrames": _safe_int(_first_present(normalized_sources, "proposalSingleSeedFrames"), 0),
        "proposalUnseededFrames": _safe_int(_first_present(normalized_sources, "proposalUnseededFrames"), 0),
        "proposalMeanWindowWidth": _safe_float(_first_present(normalized_sources, "proposalMeanWindowWidth"), 0.0),
        "bestProposalRawDetectedFrames": _safe_int(_first_present(normalized_sources, "bestProposalRawDetectedFrames"), 0),
        "bestProposalAfterSeedCollapseFrames": _safe_int(_first_present(normalized_sources, "bestProposalAfterSeedCollapseFrames"), 0),
        "bestProposalAfterFalseBallSuppressionFrames": _safe_int(_first_present(normalized_sources, "bestProposalAfterFalseBallSuppressionFrames"), 0),
        "bestProposalDirectSeedDetectedFrames": _safe_int(_first_present(normalized_sources, "bestProposalDirectSeedDetectedFrames"), 0),
        "bestProposalDirectSeedTightDetectedFrames": _safe_int(_first_present(normalized_sources, "bestProposalDirectSeedTightDetectedFrames"), 0),
        "bestProposalDirectSeedContextDetectedFrames": _safe_int(_first_present(normalized_sources, "bestProposalDirectSeedContextDetectedFrames"), 0),
        "bestProposalDirectSeedHiResRetryFrames": _safe_int(_first_present(normalized_sources, "bestProposalDirectSeedHiResRetryFrames"), 0),
        "bestProposalDirectSeedHiResRetryDetectedFrames": _safe_int(_first_present(normalized_sources, "bestProposalDirectSeedHiResRetryDetectedFrames"), 0),
        "bestProposalDirectSeedZeroDetectFrames": _safe_int(_first_present(normalized_sources, "bestProposalDirectSeedZeroDetectFrames"), 0),
        "bestProposalDirectSeedMeanCropArea": _safe_float(_first_present(normalized_sources, "bestProposalDirectSeedMeanCropArea"), 0.0),
        "bestProposalPlayerRankedMeanCropArea": _safe_float(_first_present(normalized_sources, "bestProposalPlayerRankedMeanCropArea"), 0.0),
        "bestProposalDirectSeedMeanDetectedBallBoxArea": _safe_float(_first_present(normalized_sources, "bestProposalDirectSeedMeanDetectedBallBoxArea"), 0.0),
        "bestProposalPlayerRankedMeanDetectedBallBoxArea": _safe_float(_first_present(normalized_sources, "bestProposalPlayerRankedMeanDetectedBallBoxArea"), 0.0),
        "bestProposalDirectSeedContextWindowFrames": _safe_int(_first_present(normalized_sources, "bestProposalDirectSeedContextWindowFrames"), 0),
        "bestProposalDirectSeedContextEligibleFrames": _safe_int(_first_present(normalized_sources, "bestProposalDirectSeedContextEligibleFrames"), 0),
        "bestProposalDirectSeedContextMeanSeedToBoxDistance": _safe_float(_first_present(normalized_sources, "bestProposalDirectSeedContextMeanSeedToBoxDistance"), 0.0),
        "bestProposalDirectSeedContextExpandedFrames": _safe_int(_first_present(normalized_sources, "bestProposalDirectSeedContextExpandedFrames"), 0),
        "bestProposalDirectSeedContextMeanExpansionPx": _safe_float(_first_present(normalized_sources, "bestProposalDirectSeedContextMeanExpansionPx"), 0.0),
        "bestProposalPlayerRankedDetectedFrames": _safe_int(_first_present(normalized_sources, "bestProposalPlayerRankedDetectedFrames"), 0),
        "bestProposalExactSeedDetectedFrames": _safe_int(_first_present(normalized_sources, "bestProposalExactSeedDetectedFrames"), 0),
        "bestProposalInterpolatedSeedDetectedFrames": _safe_int(_first_present(normalized_sources, "bestProposalInterpolatedSeedDetectedFrames"), 0),
        "bestProposalSingleSeedDetectedFrames": _safe_int(_first_present(normalized_sources, "bestProposalSingleSeedDetectedFrames"), 0),
        "bestProposalProfileName": _string_or_none(_first_present(normalized_sources, "bestProposalProfileName")),
        "bestProposalCandidateFrames": _safe_int(_first_present(normalized_sources, "bestProposalCandidateFrames"), 0),
        "bestProposalSelectedFrames": _safe_int(_first_present(normalized_sources, "bestProposalSelectedFrames"), 0),
        "bestProposalViable": _safe_bool(_first_present(normalized_sources, "bestProposalViable"), False),
        "collapsedCandidateFrames": _safe_int(_first_present(normalized_sources, "collapsedCandidateFrames"), 0),
        "collapsedSegmentCount": _safe_int(_first_present(normalized_sources, "collapsedSegmentCount"), 0),
        "collapsedLongestSegmentFrames": _safe_int(_first_present(normalized_sources, "collapsedLongestSegmentFrames"), 0),
        "continuityPreferredFrames": _safe_int(_first_present(normalized_sources, "continuityPreferredFrames"), 0),
        "continuityRejectedFrames": _safe_int(_first_present(normalized_sources, "continuityRejectedFrames"), 0),
        "midfieldCollapsedFrames": _safe_int(_first_present(normalized_sources, "midfieldCollapsedFrames"), 0),
        "acceptedBallRatio": _safe_float(_first_present(normalized_sources, "acceptedBallRatio"), 0.0),
        "acceptedSegmentCount": _safe_int(_first_present(normalized_sources, "acceptedSegmentCount"), 0),
        "unknownGapCount": _safe_int(_first_present(normalized_sources, "unknownGapCount"), 0),
        "longestUnknownGapFrames": _safe_int(_first_present(normalized_sources, "longestUnknownGapFrames"), 0),
        "trackedPossessionFrames": _safe_int(_first_present(normalized_sources, "trackedPossessionFrames"), 0),
        "controlledPossessionFrames": _safe_int(_first_present(normalized_sources, "controlledPossessionFrames"), 0),
        "eventCount": _safe_int(_first_present(normalized_sources, "eventCount"), 0),
        "eventTypes": event_types,
        "eventFamilyCount": _event_family_count(_first_present(normalized_sources, "eventFamilyCount"), event_types),
        "shotCount": _safe_int(_first_present(normalized_sources, "shotCount"), 0),
        "ballSignalStatus": _string_or_none(_first_present(normalized_sources, "ballSignalStatus")),
        "ballTrackViable": _safe_bool(_first_present(normalized_sources, "ballTrackViable"), False),
        "ballTrackEdgeFrameShare": _safe_float(_first_present(normalized_sources, "ballTrackEdgeFrameShare"), 0.0),
        "recoveryProfile": _string_or_none(_first_present(normalized_sources, "recoveryProfile", "recoveryProfileName")),
        "recoveryApplied": _safe_bool(_first_present(normalized_sources, "recoveryApplied"), False),
        "recoveredSelectedFrames": _safe_int(_first_present(normalized_sources, "recoveredSelectedFrames"), 0),
        "dominantAnchorCoord": _first_present(normalized_sources, "dominantAnchorCoord"),
        "dominantAnchorCount": _safe_int(_first_present(normalized_sources, "dominantAnchorCount"), 0),
        "dominantAnchorShare": _safe_float(_first_present(normalized_sources, "dominantAnchorShare"), 0.0),
        "meanSourceCenterY": _safe_float(_first_present(normalized_sources, "meanSourceCenterY"), 0.0),
        "meanSourceBoxArea": _safe_float(_first_present(normalized_sources, "meanSourceBoxArea"), 0.0),
        "candidateEdgeShare": _safe_float(_first_present(normalized_sources, "candidateEdgeShare"), 0.0),
        "selectedEdgeFrameShare": _safe_float(_first_present(normalized_sources, "selectedEdgeFrameShare"), 0.0),
        "runtimeFingerprint": _first_present(normalized_sources, "runtimeFingerprint"),
        "warmProofMode": _safe_bool(_first_present(normalized_sources, "warmProofMode"), False),
        "warmReadyObserved": _safe_bool(_first_present(normalized_sources, "warmReadyObserved"), False),
        "warmupWaitSeconds": _safe_float(_first_present(normalized_sources, "warmupWaitSeconds"), 0.0),
        "fiveMinuteTruthReady": _safe_bool(_first_present(normalized_sources, "fiveMinuteTruthReady"), False),
        "truthGateReasons": truth_gate_reasons,
        "bestProposalDirectSeedPitchPolygonRejectedFrames": _safe_int(
            _first_present(normalized_sources, "bestProposalDirectSeedPitchPolygonRejectedFrames"),
            0,
        ),
    }
    return payload


def save_canonical_proof_summary(storage: Storage, match_id: str, *sources: object) -> dict[str, object]:
    payload = build_canonical_proof_summary(*sources)
    storage.save_analysis_artifact(match_id, "proof_summary", payload)
    return payload
