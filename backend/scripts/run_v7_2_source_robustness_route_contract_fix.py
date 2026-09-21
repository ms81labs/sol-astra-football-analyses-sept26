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
DEFAULT_OUTPUT_DIR_NAME = "v7_2_source_robustness_route_contract_fix_v1"

BLOCKER_ROUTE_STALE = "v7_2_source_robustness_route_contract_stale"
BLOCKER_EVIDENCE_GAP = "v7_2_source_robustness_route_contract_evidence_gap"

NEXT_ROUTE_FIX = "v7_2_source_robustness_route_contract_fix"
NEXT_DEFAULT_EDGE_FIX = "v7_2_default_path_edge_share_reduction"
NEXT_DEFAULT_CHANGE = "v7_2_runtime_default_change_validation"
NEXT_MANUAL = "manual_review_required"

STALE_EVALUATION_ROUTE = "evaluate_touchline_detector_candidate"


def _suite_root(storage_root: Path) -> Path:
    return storage_root / "benchmark_suites" / DEFAULT_SUITE_NAME


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "source_robustness_route_contract_refresh",
            "successCriteria": [
                "source robustness no longer recommends stale detector-candidate evaluation",
                "promoted-v7.2 validation route mismatch is false",
                "runtime-default mutation remains unexecuted",
            ],
            "failureAdaptation": "If routing is still stale, repair the route resolver before another default analysis.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "source_robustness_default_gate_contract_repair",
            "successCriteria": [
                "default-blocker analysis consumes the repaired route",
                "exactly one default-gate corrective family is selected",
            ],
            "failureAdaptation": "If evidence is incomplete, write a route/default-gate evidence blocker.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "source_robustness_route_contract_blocker_summary",
            "successCriteria": [
                "blocker summary written",
                "runtime-default mutation remains unexecuted",
            ],
            "failureAdaptation": "Stop after blocker summary; do not flip runtime defaults.",
        },
    ]


def _default_next_lever(default_summary: dict[str, Any] | None) -> str:
    if not isinstance(default_summary, dict):
        return NEXT_MANUAL
    next_lever = str(default_summary.get("nextRecommendedNextLever") or "").strip()
    if next_lever:
        return next_lever
    if default_summary.get("primaryBlocker") == "v7_2_default_path_performance_blocker":
        return NEXT_DEFAULT_EDGE_FIX
    if default_summary.get("primaryBlocker") is None and default_summary.get("runtimeDefaultMutationReady"):
        return NEXT_DEFAULT_CHANGE
    return NEXT_MANUAL


def _classify(
    *,
    suite_summary: dict[str, Any] | None,
    promoted_validation: dict[str, Any] | None,
    default_summary: dict[str, Any] | None,
) -> tuple[bool, str | None, str, str]:
    suite_next = str((suite_summary or {}).get("sourceRobustnessRecommendedNextLever") or "").strip()
    default_blocker = str((default_summary or {}).get("primaryBlocker") or "").strip()
    default_next = str((default_summary or {}).get("nextRecommendedNextLever") or "").strip()
    default_route_mismatch = bool((default_summary or {}).get("sourceRobustnessRouteMismatchDetected"))
    route_mismatch = bool(
        (promoted_validation or {}).get("sourceRobustnessRouteMismatchDetected")
        or suite_next == STALE_EVALUATION_ROUTE
        or default_route_mismatch
        or default_blocker == BLOCKER_ROUTE_STALE
        or default_next == NEXT_ROUTE_FIX
    )
    if route_mismatch:
        return (
            False,
            BLOCKER_ROUTE_STALE,
            NEXT_ROUTE_FIX,
            "Source robustness still routes a controlled-promoted v7.2 candidate to stale detector-candidate evaluation.",
        )
    if not suite_next or not isinstance(default_summary, dict):
        return (
            False,
            BLOCKER_EVIDENCE_GAP,
            NEXT_MANUAL,
            "Route mismatch is no longer obvious, but default-gate evidence is incomplete.",
        )
    return (
        True,
        None,
        _default_next_lever(default_summary),
        "Source-robustness routing no longer points at stale detector-candidate evaluation.",
    )


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V7.2 Source Robustness Route Contract Fix",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Route contract fixed: `{summary.get('routeContractFixed')}`",
            f"- Source next lever: `{summary.get('sourceRobustnessRecommendedNextLever')}`",
            f"- Route mismatch detected: `{summary.get('sourceRobustnessRouteMismatchDetected')}`",
            f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_v7_2_source_robustness_route_contract_fix(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "source_robustness_route_contract_refresh",
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    suite_root = _suite_root(storage_root)
    output_root = reset_output(suite_root, output_dir_name)

    suite_summary = _load_json(suite_root / "suite_summary.json")
    promoted_validation = _load_json(
        suite_root
        / "promoted_v7_2_source_robustness_validation_v1"
        / "promoted_v7_2_source_robustness_validation_summary.json"
    )
    default_summary = _load_json(
        suite_root
        / "v7_2_source_robustness_default_blocker_analysis_v1"
        / "default_blocker_analysis_summary.json"
    )
    goal_achieved, primary_blocker, next_lever, english = _classify(
        suite_summary=suite_summary,
        promoted_validation=promoted_validation,
        default_summary=default_summary,
    )
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    source_next = (suite_summary or {}).get("sourceRobustnessRecommendedNextLever")
    route_mismatch = bool(
        (promoted_validation or {}).get("sourceRobustnessRouteMismatchDetected")
        or source_next == STALE_EVALUATION_ROUTE
    )
    summary: dict[str, Any] = {
        "batchName": "v7_2_source_robustness_route_contract_fix",
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "generatedAt": generated_at,
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": True,
        "primaryBlocker": primary_blocker,
        "routeContractFixed": goal_achieved,
        "sourceRobustnessRecommendedNextLever": source_next,
        "sourceRobustnessRouteMismatchDetected": route_mismatch,
        "defaultBlockerAfterRouteFix": (default_summary or {}).get("primaryBlocker"),
        "realDefaultPerformanceFailureProven": bool(
            (default_summary or {}).get("realDefaultPerformanceFailureProven")
        ),
        "runtimeDefaultMutationReady": bool((default_summary or {}).get("runtimeDefaultMutationReady")),
        "runtimeDefaultMutationAllowed": False,
        "runtimeDefaultMutationExecuted": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    route_audit = {
        "generatedAt": generated_at,
        "routeContractFixed": summary["routeContractFixed"],
        "sourceRobustnessRecommendedNextLever": source_next,
        "staleEvaluationRoute": STALE_EVALUATION_ROUTE,
        "sourceRobustnessRouteMismatchDetected": route_mismatch,
        "promotedValidationNextLever": (promoted_validation or {}).get("nextRecommendedNextLever"),
    }
    default_gate_audit = {
        "generatedAt": generated_at,
        "defaultBlockerAfterRouteFix": summary["defaultBlockerAfterRouteFix"],
        "realDefaultPerformanceFailureProven": summary["realDefaultPerformanceFailureProven"],
        "runtimeDefaultMutationReady": summary["runtimeDefaultMutationReady"],
        "runtimeDefaultMutationExecuted": False,
        "nextRecommendedNextLever": next_lever,
    }

    _write_json(output_root / "route_contract_fix_summary.json", summary)
    _write_json(output_root / "route_contract_audit.json", route_audit)
    _write_json(output_root / "default_gate_after_route_fix_audit.json", default_gate_audit)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "decision_matrix.json", {"generatedAt": generated_at, "summary": summary, "attempts": attempts})
    _write_json(
        output_root / "batch_outcome_analysis.json",
        {
            "summary": summary,
            "routeContractAudit": route_audit,
            "defaultGateAfterRouteFixAudit": default_gate_audit,
        },
    )
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Close out the v7.2 source-robustness route-contract fix.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="source_robustness_route_contract_refresh")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_v7_2_source_robustness_route_contract_fix(
        storage_root=args.storage_root,
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
