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

DEFAULT_SUITE_NAME = "frozen-viable-baseline-slice-suite"
DEFAULT_OUTPUT_DIR_NAME = "v7_2_source_robustness_default_blocker_analysis_v1"

BLOCKER_PROMOTION_TRUTH = "v7_2_controlled_promotion_truth_missing"
BLOCKER_ROUTE_STALE = "v7_2_source_robustness_route_contract_stale"
BLOCKER_PERFORMANCE = "v7_2_default_path_performance_blocker"
BLOCKER_EVIDENCE = "v7_2_default_blocker_evidence_gap"

NEXT_PROMOTION = "v7_2_promotion_readiness_validation"
NEXT_ROUTE_FIX = "v7_2_source_robustness_route_contract_fix"
NEXT_EDGE_FIX = "v7_2_default_path_edge_share_reduction"
NEXT_DEFAULT_CHANGE = "v7_2_runtime_default_change_validation"
NEXT_MANUAL = "manual_review_required"


def _suite_root(storage_root: Path) -> Path:
    return storage_root / "benchmark_suites" / DEFAULT_SUITE_NAME


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "default_blocker_truth_delta_analysis",
            "successCriteria": [
                "controlled v7.2 promotion truth is validated",
                "source-robustness route mismatch is identified or ruled out",
                "default-mutation blocker class is named",
            ],
            "failureAdaptation": "If route mismatch dominates, move to source_robustness_route_contract_repair.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "source_robustness_route_contract_repair",
            "successCriteria": [
                "route-contract mismatch is written as a concrete blocker",
                "runtime-default mutation remains unexecuted",
            ],
            "failureAdaptation": "If route is current but performance fails, move to default path edge-share reduction.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "default_blocker_summary",
            "successCriteria": [
                "blocker summary written",
                "exactly one next corrective family selected",
            ],
            "failureAdaptation": "Stop after blocker summary; do not flip runtime defaults.",
        },
    ]


def _blockers_from(*payloads: dict[str, Any] | None) -> list[str]:
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        for key in (
            "runtimeDefaultMutationBlockers",
            "sourceRobustnessPromotionBlockers",
            "promotionBlockers",
        ):
            value = payload.get(key)
            if isinstance(value, list):
                return [str(item) for item in value if str(item).strip()]
    return []


def _nested(payload: dict[str, Any] | None, key: str) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get(key)
    return value if isinstance(value, dict) else None


def _truth_audit(
    *,
    validation_summary: dict[str, Any] | None,
    source_gate_audit: dict[str, Any] | None,
    suite_summary: dict[str, Any] | None,
    suite_diagnosis: dict[str, Any] | None,
    promotion_readiness: dict[str, Any] | None,
) -> dict[str, Any]:
    promotion_diagnosis = _nested(suite_diagnosis, "detectorCandidatePromotionDiagnosis")
    source_audit = _nested(source_gate_audit, "sourceAudit")
    blockers = _blockers_from(validation_summary, source_audit, suite_summary, suite_diagnosis)
    controlled_valid = bool(
        validation_summary
        and validation_summary.get("controlledPromotionValid")
        and promotion_readiness
        and promotion_readiness.get("promotionReady")
        and (not promotion_diagnosis or promotion_diagnosis.get("promotionValidated"))
    )
    suite_next = str((suite_summary or {}).get("sourceRobustnessRecommendedNextLever") or "")
    validation_next = str((validation_summary or {}).get("nextRecommendedNextLever") or "")
    route_mismatch = bool(
        (validation_summary or {}).get("sourceRobustnessRouteMismatchDetected")
        or (source_audit or {}).get("routeMismatchDetected")
        or (
            controlled_valid
            and suite_next == "evaluate_touchline_detector_candidate"
            and validation_next in {"v7_2_source_robustness_default_blocker_analysis", "promoted_v7_2_source_robustness_validation"}
        )
    )
    passed_source_gate = bool(
        (source_audit or {}).get("passedPromotionGate")
        or (suite_summary or {}).get("passedPromotionGate")
    )
    runtime_ready = bool(
        controlled_valid
        and not blockers
        and (
            (validation_summary or {}).get("runtimeDefaultMutationReady")
            or (source_audit or {}).get("runtimeDefaultMutationReady")
            or passed_source_gate
        )
    )
    return {
        "controlledPromotionValid": controlled_valid,
        "promotionDiagnosisPresent": isinstance(promotion_diagnosis, dict),
        "runtimeDefaultMutationBlockers": blockers,
        "runtimeDefaultMutationReady": runtime_ready,
        "sourceRobustnessRouteMismatchDetected": route_mismatch,
        "sourceRobustnessRecommendedNextLever": suite_next or None,
        "validationRecommendedNextLever": validation_next or None,
        "passedPromotionGate": passed_source_gate,
        "sourceRobustnessOutcome": (suite_summary or {}).get("sourceRobustnessOutcome")
        or (source_audit or {}).get("sourceRobustnessOutcome"),
        "sourceRobustnessDominantFailureSignal": (suite_summary or {}).get(
            "sourceRobustnessDominantFailureSignal"
        )
        or (source_audit or {}).get("sourceRobustnessDominantFailureSignal"),
    }


def _classify(audit: dict[str, Any]) -> tuple[str | None, str, bool, bool, str]:
    if not audit["controlledPromotionValid"]:
        return (
            BLOCKER_PROMOTION_TRUTH,
            NEXT_PROMOTION,
            False,
            False,
            "Controlled v7.2 promotion truth is missing or invalid; rerun promotion-readiness validation.",
        )
    if audit["runtimeDefaultMutationReady"]:
        return (
            None,
            NEXT_DEFAULT_CHANGE,
            True,
            False,
            "Source robustness no longer blocks runtime-default validation.",
        )
    if audit["sourceRobustnessRouteMismatchDetected"]:
        return (
            BLOCKER_ROUTE_STALE,
            NEXT_ROUTE_FIX,
            True,
            False,
            "The default blocker is not yet proven as v7.2 performance failure because source-robustness routing is stale.",
        )
    if audit["runtimeDefaultMutationBlockers"]:
        return (
            BLOCKER_PERFORMANCE,
            NEXT_EDGE_FIX,
            True,
            True,
            "Source robustness routing is current enough to treat the blocker as a real default-path performance issue.",
        )
    return (
        BLOCKER_EVIDENCE,
        NEXT_MANUAL,
        False,
        False,
        "Default-mutation evidence is incomplete; manual review is required.",
    )


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V7.2 Source Robustness Default Blocker Analysis",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Controlled promotion valid: `{summary.get('controlledPromotionValid')}`",
            f"- Real default performance failure proven: `{summary.get('realDefaultPerformanceFailureProven')}`",
            f"- Route mismatch detected: `{summary.get('sourceRobustnessRouteMismatchDetected')}`",
            f"- Runtime default mutation ready: `{summary.get('runtimeDefaultMutationReady')}`",
            f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_v7_2_source_robustness_default_blocker_analysis(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "default_blocker_truth_delta_analysis",
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    suite_root = _suite_root(storage_root)
    output_root = reset_output(suite_root, output_dir_name)

    validation_root = suite_root / "promoted_v7_2_source_robustness_validation_v1"
    validation_summary = _load_json(validation_root / "promoted_v7_2_source_robustness_validation_summary.json")
    source_gate_audit = _load_json(validation_root / "source_robustness_gate_audit.json")
    suite_summary = _load_json(suite_root / "suite_summary.json")
    suite_diagnosis = _load_json(suite_root / "suite_robustness_diagnosis.json")
    promotion_readiness = _load_json(suite_root / "v7_2_detector_candidate_promotion_readiness.json")

    audit = _truth_audit(
        validation_summary=validation_summary,
        source_gate_audit=source_gate_audit,
        suite_summary=suite_summary,
        suite_diagnosis=suite_diagnosis,
        promotion_readiness=promotion_readiness,
    )
    primary_blocker, next_lever, roadmap_advance_allowed, real_performance_failure, english = _classify(audit)
    generated_at = _utc_now_iso()
    attempts = _attempt_plan()
    summary: dict[str, Any] = {
        "batchName": "v7_2_source_robustness_default_blocker_analysis",
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "generatedAt": generated_at,
        "goalAchieved": primary_blocker is None,
        "roadmapAdvanceAllowed": roadmap_advance_allowed,
        "primaryBlocker": primary_blocker,
        "controlledPromotionValid": audit["controlledPromotionValid"],
        "realDefaultPerformanceFailureProven": real_performance_failure,
        "sourceRobustnessRouteMismatchDetected": audit["sourceRobustnessRouteMismatchDetected"],
        "runtimeDefaultMutationReady": audit["runtimeDefaultMutationReady"],
        "runtimeDefaultMutationExecuted": False,
        "runtimeDefaultMutationBlockers": audit["runtimeDefaultMutationBlockers"],
        "sourceRobustnessOutcome": audit["sourceRobustnessOutcome"],
        "sourceRobustnessDominantFailureSignal": audit["sourceRobustnessDominantFailureSignal"],
        "sourceRobustnessRecommendedNextLever": audit["sourceRobustnessRecommendedNextLever"],
        "validationRecommendedNextLever": audit["validationRecommendedNextLever"],
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    route_audit = {
        "generatedAt": generated_at,
        "sourceRobustnessRouteMismatchDetected": audit["sourceRobustnessRouteMismatchDetected"],
        "sourceRobustnessRecommendedNextLever": audit["sourceRobustnessRecommendedNextLever"],
        "validationRecommendedNextLever": audit["validationRecommendedNextLever"],
        "promotionDiagnosisPresent": audit["promotionDiagnosisPresent"],
    }
    mutation_audit = {
        "generatedAt": generated_at,
        "runtimeDefaultMutationReady": audit["runtimeDefaultMutationReady"],
        "runtimeDefaultMutationExecuted": False,
        "runtimeDefaultMutationBlockers": audit["runtimeDefaultMutationBlockers"],
        "realDefaultPerformanceFailureProven": real_performance_failure,
    }
    _write_json(output_root / "default_blocker_analysis_summary.json", summary)
    _write_json(output_root / "route_mismatch_audit.json", route_audit)
    _write_json(output_root / "default_mutation_evidence_audit.json", mutation_audit)
    _write_json(
        output_root / "source_robustness_delta_audit.json",
        {
            "generatedAt": generated_at,
            "truthAudit": audit,
            "validationSummary": validation_summary or {},
            "suiteSummary": suite_summary or {},
        },
    )
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "decision_matrix.json", {"generatedAt": generated_at, "summary": summary, "attempts": attempts})
    _write_json(
        output_root / "batch_outcome_analysis.json",
        {
            "summary": summary,
            "routeMismatchAudit": route_audit,
            "defaultMutationEvidenceAudit": mutation_audit,
        },
    )
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze the promoted v7.2 source-robustness default blocker.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="default_blocker_truth_delta_analysis")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_v7_2_source_robustness_default_blocker_analysis(
        storage_root=args.storage_root,
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
