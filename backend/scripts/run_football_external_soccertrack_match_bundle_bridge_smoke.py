from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_ADAPTER_DIR_NAME = "football_external_soccertrack_adapter_smoke_test_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccertrack_match_bundle_bridge_smoke_v1"

BLOCKER_ADAPTER_MISSING = "football_external_soccertrack_adapter_smoke_missing"
BLOCKER_BUNDLE_CONTRACT = "football_external_soccertrack_match_bundle_contract_gap"

NEXT_ADAPTER = "football_external_soccertrack_adapter_smoke_test"
NEXT_REPAIR = "football_external_soccertrack_match_bundle_bridge_repair"
NEXT_PRODUCT_ROUTE = "football_external_soccertrack_product_route_smoke"


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccertrack_external_match_bundle_bridge",
            "successCriteria": [
                "wrap canonical SoccerTrack fixture in match_bundle_v1-compatible JSON",
                "preserve external dataset provenance",
                "do not write into normal match storage or mutate runtime defaults",
            ],
            "failureAdaptation": "If the contract audit fails, repair only bridge mapping fields.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccertrack_match_bundle_bridge_contract_repair",
            "successCriteria": [
                "repair missing match_bundle_v1 top-level fields from canonical external fixture",
                "preserve no training, no promotion, and no runtime mutation",
            ],
            "failureAdaptation": "If bridge still cannot satisfy the contract, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccertrack_match_bundle_bridge_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before product route smoke until bridge bundle is valid",
            ],
            "failureAdaptation": "Route to adapter smoke or bridge repair depending on missing truth.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    adapter_root = candidate_root / DEFAULT_ADAPTER_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "adapterRoot": adapter_root,
        "adapterSummary": _load_json(adapter_root / "soccertrack_adapter_smoke_summary.json"),
        "canonicalFixture": _load_json(adapter_root / "canonical_external_match_fixture.json"),
        "bridgePlan": _load_json(adapter_root / "match_bundle_bridge_plan.json"),
    }


def _adapter_ready(summary: dict[str, Any] | None, canonical: dict[str, Any] | None, bridge_plan: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("canonicalExternalFixtureReady") is True
        and summary.get("trainingExecuted") is False
        and summary.get("runtimeDefaultMutationAllowed") is False
        and isinstance(canonical, dict)
        and canonical.get("schemaVersion") == "canonical_external_match_fixture_v1"
        and canonical.get("sourceDataset") == "soccertrack_v2"
        and isinstance(canonical.get("normalizedEvents"), list)
        and isinstance(canonical.get("gsrFrames"), list)
        and len(canonical["gsrFrames"]) > 0
        and isinstance(bridge_plan, dict)
        and bridge_plan.get("bridgeSmokeReady") is True
    )


def _event_to_bundle_event(event: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "id": event.get("eventId") or f"soccertrack-event-{index:06d}",
        "type": event.get("eventType") or "unknown",
        "frameId": None,
        "timestamp": float(event.get("positionMs") or 0) / 1000.0,
        "team": event.get("team") or "",
        "description": f"{event.get('eventType') or 'event'} at {event.get('positionMs')}ms",
        "source": "soccertrack_bas",
        "period": event.get("period"),
        "positionMs": event.get("positionMs"),
        "playerId": event.get("playerId") or "",
    }


def _frame_to_bundle_frame(frame: dict[str, Any]) -> dict[str, Any]:
    half = int(frame["half"])
    frame_index = int(frame["frameIndex"])
    timestamp = float(frame["timestampSecondsInHalf"])
    players = [
        {
            "id": int(entity["trackId"]),
            "x": float(entity["pitchPositionNormalized"]["x"]),
            "y": float(entity["pitchPositionNormalized"]["y"]),
            "confidence": 1.0,
            "playerId": entity.get("playerId"),
            "sourceTeam": entity.get("teamSide"),
            "role": entity.get("role"),
            "jerseyNumber": entity.get("jerseyNumber"),
            "pitchPositionMeters": entity["pitchPositionMeters"],
        }
        for entity in frame.get("entities") or []
        if isinstance(entity, dict)
    ]
    return {
        "frameId": half * 1_000_000 + frame_index,
        "timestamp": timestamp,
        "timestampSecondsInHalf": timestamp,
        "half": half,
        "ball": None,
        "players": players,
        "source": "soccertrack_gsr_ground_truth",
        "referenceOnly": True,
    }


def _external_match_bundle(canonical: dict[str, Any]) -> dict[str, Any]:
    match_id = str(canonical.get("sourceMatchId") or "")
    events = [
        _event_to_bundle_event(event, index)
        for index, event in enumerate(canonical.get("normalizedEvents") or [])
        if isinstance(event, dict)
    ]
    frames = [
        _frame_to_bundle_frame(frame)
        for frame in canonical.get("gsrFrames") or []
        if isinstance(frame, dict)
    ]
    exported_at = _utc_now_iso()
    return {
        "schemaVersion": "match_bundle_v1",
        "exportedAt": exported_at,
        "match": {
            "id": f"soccertrack:{match_id}",
            "name": f"SoccerTrack {match_id}",
            "status": "external_ready",
            "inputMode": "external_soccertrack_fixture",
            "originalFilename": None,
            "createdAt": exported_at,
            "updatedAt": exported_at,
        },
        "provenance": {
            "deterministicCore": True,
            "llmGenerated": False,
            "storageArtifactsAreSourceOfTruth": True,
            "externalDataset": "soccertrack_v2",
            "externalSourceMatchId": match_id,
            "runtimeDefaultMutationAllowed": False,
            "groundTruthReferenceOnly": True,
            "referenceLabelsUsedForInference": False,
        },
        "artifactAvailability": {
            "externalCanonicalFixture": True,
            "gsrGroundTruth": bool(frames),
            "frames": bool(frames),
            "analytics": True,
            "events": bool(events),
            "acceptedMatchState": False,
            "ballTruthLayers": False,
            "ballPipelineTrace": False,
            "proofRuntimeOptions": False,
            "recoveryDebug": False,
            "benchmark": False,
        },
        "exports": {
            "matchJson": f"/api/external/soccertrack/{match_id}/export/match.json",
            "sourceDataset": "soccertrack_v2",
        },
        "frames": frames,
        "analytics": {
            "summary": {
                "source": "soccertrack_gsr_ground_truth_adapter",
                "basEventCount": canonical.get("basEventCount"),
                "gsrHalfCount": canonical.get("gsrHalfCount"),
                "gsrFrameCount": len(frames),
                "motFrameCount": canonical.get("motFrameCount"),
                "motSampledFrameCount": canonical.get("motSampledFrameCount"),
            },
            "ballAssignments": [],
            "formationTimeline": [],
            "shots": [],
        },
        "events": events,
        "externalCanonicalFixture": {
            "schemaVersion": canonical.get("schemaVersion"),
            "sourceDataset": canonical.get("sourceDataset"),
            "sourceMatchId": match_id,
        },
        "benchmark": None,
    }


def _contract_audit(bundle: dict[str, Any] | None) -> dict[str, Any]:
    frames = bundle.get("frames") if isinstance(bundle, dict) else None
    reference_frames = isinstance(frames, list) and bool(frames) and all(
        isinstance(frame, dict)
        and frame.get("source") == "soccertrack_gsr_ground_truth"
        and frame.get("referenceOnly") is True
        for frame in frames
    )
    positioned_player = isinstance(frames, list) and any(
        isinstance(player, dict)
        and isinstance(player.get("pitchPositionMeters"), dict)
        and isinstance(player.get("x"), (int, float))
        and isinstance(player.get("y"), (int, float))
        for frame in frames
        if isinstance(frame, dict)
        for player in frame.get("players") or []
    )
    checks = {
        "bundlePresent": isinstance(bundle, dict),
        "schemaVersionPresent": bool(isinstance(bundle, dict) and bundle.get("schemaVersion") == "match_bundle_v1"),
        "matchPresent": bool(isinstance(bundle, dict) and isinstance(bundle.get("match"), dict)),
        "provenancePresent": bool(isinstance(bundle, dict) and isinstance(bundle.get("provenance"), dict)),
        "externalDatasetProvenancePresent": bool(
            isinstance(bundle, dict)
            and isinstance(bundle.get("provenance"), dict)
            and bundle["provenance"].get("externalDataset") == "soccertrack_v2"
        ),
        "artifactAvailabilityPresent": bool(isinstance(bundle, dict) and isinstance(bundle.get("artifactAvailability"), dict)),
        "exportsPresent": bool(isinstance(bundle, dict) and isinstance(bundle.get("exports"), dict)),
        "framesPresent": bool(isinstance(bundle, dict) and isinstance(bundle.get("frames"), list) and len(bundle["frames"]) > 0),
        "analyticsPresent": bool(isinstance(bundle, dict) and isinstance(bundle.get("analytics"), dict)),
        "eventsPresent": bool(isinstance(bundle, dict) and isinstance(bundle.get("events"), list) and len(bundle["events"]) > 0),
        "deterministicProvenancePresent": bool(
            isinstance(bundle, dict)
            and isinstance(bundle.get("provenance"), dict)
            and bundle["provenance"].get("deterministicCore") is True
            and bundle["provenance"].get("llmGenerated") is False
        ),
        "groundTruthReferenceOnly": bool(
            isinstance(bundle, dict)
            and isinstance(bundle.get("provenance"), dict)
            and bundle["provenance"].get("groundTruthReferenceOnly") is True
            and bundle["provenance"].get("referenceLabelsUsedForInference") is False
            and reference_frames
        ),
        "positionedPlayerPresent": positioned_player,
    }
    return {
        "schemaVersion": "soccertrack_match_bundle_bridge_contract_audit_v1",
        "generatedAt": _utc_now_iso(),
        "checks": checks,
        "bundleContractPassed": all(checks.values()),
    }


def _classify(adapter_ready: bool, contract_passed: bool) -> tuple[str | None, str, bool, bool, str]:
    if not adapter_ready:
        return (
            BLOCKER_ADAPTER_MISSING,
            NEXT_ADAPTER,
            False,
            False,
            "SoccerTrack MatchBundle bridge requires a passing adapter smoke artifact first.",
        )
    if not contract_passed:
        return (
            BLOCKER_BUNDLE_CONTRACT,
            NEXT_REPAIR,
            False,
            True,
            "SoccerTrack external bundle failed the match_bundle_v1 bridge contract; repair bridge mapping before product route smoke.",
        )
    return (
        None,
        NEXT_PRODUCT_ROUTE,
        True,
        True,
        "SoccerTrack external match bundle bridge passed. Advance to product route smoke; no training, promotion, candidate evaluation, or runtime mutation was executed.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "adapter_smoke_missing", "selected": primary_blocker == BLOCKER_ADAPTER_MISSING, "primaryBlocker": BLOCKER_ADAPTER_MISSING, "nextRecommendedNextLever": NEXT_ADAPTER},
            {"condition": "match_bundle_contract_gap", "selected": primary_blocker == BLOCKER_BUNDLE_CONTRACT, "primaryBlocker": BLOCKER_BUNDLE_CONTRACT, "nextRecommendedNextLever": NEXT_REPAIR},
            {"condition": "product_route_smoke_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_PRODUCT_ROUTE},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerTrack MatchBundle Bridge Smoke",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Selected match ID: `{summary.get('selectedMatchId')}`",
            f"- MatchBundle bridge ready: `{summary.get('matchBundleBridgeReady')}`",
            f"- External bundle event count: `{summary.get('externalBundleEventCount')}`",
            f"- External bundle frame count: `{summary.get('externalBundleFrameCount')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation allowed: `{summary.get('runtimeDefaultMutationAllowed')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccertrack_match_bundle_bridge_smoke(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccertrack_external_match_bundle_bridge",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    adapter_ready = _adapter_ready(inputs.get("adapterSummary"), inputs.get("canonicalFixture"), inputs.get("bridgePlan"))
    bundle = _external_match_bundle(inputs["canonicalFixture"]) if isinstance(inputs.get("canonicalFixture"), dict) else None
    audit = _contract_audit(bundle)
    primary_blocker, next_lever, goal_achieved, roadmap_advance_allowed, english = _classify(
        adapter_ready,
        audit["bundleContractPassed"],
    )
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    selected_match_id = (inputs.get("canonicalFixture") or {}).get("sourceMatchId") if isinstance(inputs.get("canonicalFixture"), dict) else None
    event_count = len(bundle.get("events", [])) if isinstance(bundle, dict) else 0
    frame_count = len(bundle.get("frames", [])) if isinstance(bundle, dict) else 0
    summary: dict[str, Any] = {
        "batchName": "football_external_soccertrack_match_bundle_bridge_smoke",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": roadmap_advance_allowed,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccertrack_adapter_smoke_test",
        "selectedSampleResourceId": "soccertrack_v2",
        "selectedMatchId": selected_match_id,
        "matchBundleBridgeReady": goal_achieved,
        "externalBundleSchemaVersion": bundle.get("schemaVersion") if isinstance(bundle, dict) else None,
        "externalBundleEventCount": event_count,
        "externalBundleFrameCount": frame_count,
        "trainingAllowed": False,
        "trainingExecuted": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationAllowed": False,
        "runtimeDefaultMutationExecuted": False,
        "promotionMutationExecuted": False,
        "candidateEvaluationExecuted": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = _decision_matrix(primary_blocker, goal_achieved)
    batch_outcome = {
        "summary": summary,
        "matchBundleBridgeContractAudit": audit,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "soccertrack_match_bundle_bridge_summary.json", summary)
    if bundle is not None:
        _write_json(output_root / "soccertrack_external_match_bundle.json", bundle)
    _write_json(output_root / "match_bundle_bridge_contract_audit.json", audit)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bridge SoccerTrack canonical external fixture into match_bundle_v1-compatible JSON.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccertrack_external_match_bundle_bridge")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccertrack_match_bundle_bridge_smoke(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
