from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_SMOKE_DIR_NAME = "football_external_benchmark_harness_smoke_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_benchmark_execution_approval_v1"

BLOCKER_HARNESS_SMOKE_MISSING = "football_external_benchmark_harness_smoke_missing"
BLOCKER_EXECUTION_SCOPE_GAP = "football_external_benchmark_execution_scope_gap"

NEXT_HARNESS_SMOKE = "football_external_benchmark_harness_smoke"
NEXT_SCOPE_REPAIR = "football_external_benchmark_execution_scope_repair"
NEXT_BOUNDED_EXECUTION_SMOKE = "football_external_benchmark_bounded_execution_smoke"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "external_benchmark_execution_approval",
            "successCriteria": [
                "approve only a generated-truth bounded smoke execution",
                "carry forward SoccerNet and SoccerTrack smoke cases",
                "keep detector evaluation, training, promotion, video download, normal match storage mutation, and runtime-default mutation false",
            ],
            "failureAdaptation": "If harness smoke truth is missing, rerun harness smoke.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "external_benchmark_execution_scope_repair",
            "successCriteria": [
                "repair execution scope from smoke artifacts only",
                "do not expand to detector evaluation or downloads",
            ],
            "failureAdaptation": "If scope still cannot be bounded, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "external_benchmark_execution_approval_blocker_summary",
            "successCriteria": [
                "write blocker truth",
                "select exactly one next family",
            ],
            "failureAdaptation": "Route to harness smoke, scope repair, or bounded execution smoke.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str, smoke_dir_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    smoke_root = candidate_root / smoke_dir_name
    return {
        "candidateRoot": candidate_root,
        "smokeSummary": _load_json(smoke_root / "external_benchmark_smoke_summary.json"),
        "smokeCaseManifest": _load_json(smoke_root / "benchmark_smoke_case_manifest.json"),
        "stageGateSmokeAudit": _load_json(smoke_root / "stage_gate_smoke_audit.json"),
    }


def _smoke_ready(summary: dict[str, Any] | None, cases: dict[str, Any] | None, stage: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("externalBenchmarkHarnessSmokePassed") is True
        and summary.get("externalBenchmarkExecutionApprovalReady") is True
        and summary.get("externalBenchmarkExecutionReady") is False
        and summary.get("detectorEvaluationExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("promotionReady") is False
        and summary.get("candidateReadyForEvaluation") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("normalMatchStorageMutationExecuted") is False
        and isinstance(cases, dict)
        and cases.get("schemaVersion") == "football_external_benchmark_smoke_case_manifest_v1"
        and isinstance(cases.get("smokeCases"), list)
        and len(cases["smokeCases"]) >= 2
        and isinstance(stage, dict)
        and stage.get("stageGateSmokePassed") is True
    )


def _execution_scope(cases: dict[str, Any] | None) -> dict[str, Any]:
    smoke_cases = [row for row in (cases or {}).get("smokeCases") or [] if isinstance(row, dict)]
    approved_source_ids = [str(row.get("sourceId")) for row in smoke_cases]
    return {
        "schemaVersion": "football_external_benchmark_execution_scope_audit_v1",
        "generatedAt": _utc_now_iso(),
        "approvedExecutionMode": "generated_truth_bounded_smoke",
        "approvedSourceIds": approved_source_ids,
        "approvedSmokeCaseCount": len(smoke_cases),
        "detectorBenchmarkAllowed": False,
        "fullBenchmarkExecutionAllowed": False,
        "datasetDownloadAllowed": False,
        "videoDownloadAllowed": False,
        "normalMatchStorageMutationAllowed": False,
        "trainingAllowed": False,
        "promotionAllowed": False,
        "runtimeDefaultMutationAllowed": False,
        "executionScopeValid": len(smoke_cases) >= 2 and set(approved_source_ids) >= {"soccernet", "soccertrack"},
    }


def _approval_contract(scope: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "football_external_benchmark_execution_approval_contract_v1",
        "contractName": NEXT_BOUNDED_EXECUTION_SMOKE,
        "sourceBatch": "football_external_benchmark_harness_smoke",
        "externalBenchmarkExecutionApproved": bool(scope.get("executionScopeValid")),
        "approvedExecutionMode": scope.get("approvedExecutionMode"),
        "approvedSourceIds": scope.get("approvedSourceIds"),
        "approvedSmokeCaseCount": scope.get("approvedSmokeCaseCount"),
        "detectorBenchmarkAllowed": False,
        "fullBenchmarkExecutionAllowed": False,
        "datasetDownloadAllowed": False,
        "videoDownloadAllowed": False,
        "normalMatchStorageMutationAllowed": False,
        "trainingAllowed": False,
        "promotionAllowed": False,
        "runtimeDefaultMutationAllowed": False,
        "executionMayWriteOnly": [
            "football_external_benchmark_bounded_execution_smoke_v1/*",
            "backend/storage/automation/unattended_roadmap_loop_status.json",
            "memorybank/activeContext.md",
            "memorybank/progress.md",
            "SESSION-HANDOFF.md",
        ],
    }


def _guardrail_audit(smoke_ready: bool, scope: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "smokeReady": smoke_ready,
        "executionScopeValid": scope.get("executionScopeValid") is True,
        "detectorBenchmarkStillBlocked": contract.get("detectorBenchmarkAllowed") is False,
        "downloadStillBlocked": contract.get("datasetDownloadAllowed") is False and contract.get("videoDownloadAllowed") is False,
        "trainingStillBlocked": contract.get("trainingAllowed") is False,
        "promotionStillBlocked": contract.get("promotionAllowed") is False,
        "runtimeMutationStillBlocked": contract.get("runtimeDefaultMutationAllowed") is False,
        "normalStorageMutationStillBlocked": contract.get("normalMatchStorageMutationAllowed") is False,
    }
    return {
        "schemaVersion": "football_external_benchmark_execution_guardrail_audit_v1",
        "generatedAt": _utc_now_iso(),
        **checks,
        "executionApprovalGuardrailPassed": all(checks.values()),
    }


def _classify(smoke_ready: bool, scope: dict[str, Any], guardrail: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not smoke_ready:
        return (
            BLOCKER_HARNESS_SMOKE_MISSING,
            NEXT_HARNESS_SMOKE,
            False,
            "External benchmark harness smoke truth is missing or unsafe; rerun harness smoke before approval.",
        )
    if scope.get("executionScopeValid") is not True or guardrail.get("executionApprovalGuardrailPassed") is not True:
        return (
            BLOCKER_EXECUTION_SCOPE_GAP,
            NEXT_SCOPE_REPAIR,
            False,
            "External benchmark execution scope is not safely bounded; repair the scope before execution.",
        )
    return (
        None,
        NEXT_BOUNDED_EXECUTION_SMOKE,
        True,
        "External benchmark bounded smoke execution is approved for generated-truth cases only. This approval did not run detector evaluation, download data, train, promote, mutate normal match storage, or mutate runtime defaults.",
    )


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "harness_smoke_missing", "selected": primary_blocker == BLOCKER_HARNESS_SMOKE_MISSING, "primaryBlocker": BLOCKER_HARNESS_SMOKE_MISSING, "nextRecommendedNextLever": NEXT_HARNESS_SMOKE},
            {"condition": "execution_scope_gap", "selected": primary_blocker == BLOCKER_EXECUTION_SCOPE_GAP, "primaryBlocker": BLOCKER_EXECUTION_SCOPE_GAP, "nextRecommendedNextLever": NEXT_SCOPE_REPAIR},
            {"condition": "bounded_execution_smoke_approved", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_BOUNDED_EXECUTION_SMOKE},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External Benchmark Execution Approval",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Execution approved: `{summary.get('externalBenchmarkExecutionApproved')}`",
            f"- Approved smoke cases: `{summary.get('approvedSmokeCaseCount')}`",
            f"- External benchmark execution ready: `{summary.get('externalBenchmarkExecutionReady')}`",
            f"- Detector evaluation executed: `{summary.get('detectorEvaluationExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime-default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_benchmark_execution_approval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    smoke_dir_name: str = DEFAULT_SMOKE_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "external_benchmark_execution_approval",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name, smoke_dir_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _smoke_ready(inputs["smokeSummary"], inputs["smokeCaseManifest"], inputs["stageGateSmokeAudit"])
    scope = _execution_scope(inputs["smokeCaseManifest"])
    contract = _approval_contract(scope)
    guardrail = _guardrail_audit(ready, scope, contract)
    primary_blocker, next_lever, goal_achieved, english = _classify(ready, scope, guardrail)
    attempts = _attempt_plan()
    summary: dict[str, Any] = {
        "batchName": "football_external_benchmark_execution_approval",
        "generatedAt": _utc_now_iso(),
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_benchmark_harness_smoke",
        "externalBenchmarkExecutionApproved": goal_achieved,
        "externalBenchmarkExecutionReady": False,
        "approvedExecutionMode": contract.get("approvedExecutionMode"),
        "approvedSmokeCaseCount": contract.get("approvedSmokeCaseCount"),
        "approvedSourceIds": contract.get("approvedSourceIds"),
        "detectorEvaluationExecuted": False,
        "candidateEvaluationExecuted": False,
        "candidateReadyForEvaluation": False,
        "datasetDownloadExecuted": False,
        "videoDownloadExecuted": False,
        "normalMatchStorageMutationExecuted": False,
        "trainingAllowed": False,
        "trainingExecuted": False,
        "promotionReady": False,
        "promotionMutationExecuted": False,
        "runtimeDefaultMutationAllowed": False,
        "runtimeDefaultMutationExecuted": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = _decision_matrix(primary_blocker, next_lever, goal_achieved)
    failsafe = {"attemptBudget": 3, "attempts": attempts}
    outcome = {
        "summary": summary,
        "externalBenchmarkExecutionApprovalContract": contract,
        "executionScopeAudit": scope,
        "executionGuardrailAudit": guardrail,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": failsafe,
    }
    _write_json(output_root / "external_benchmark_execution_approval_summary.json", summary)
    _write_json(output_root / "external_benchmark_execution_approval_contract.json", contract)
    _write_json(output_root / "execution_scope_audit.json", scope)
    _write_json(output_root / "execution_guardrail_audit.json", guardrail)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", failsafe)
    _write_json(output_root / "batch_outcome_analysis.json", outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--smoke-dir-name", default=DEFAULT_SMOKE_DIR_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    args = parser.parse_args()
    summary = run_football_external_benchmark_execution_approval(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        smoke_dir_name=args.smoke_dir_name,
        output_dir_name=args.output_dir_name,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary.get("goalAchieved") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
