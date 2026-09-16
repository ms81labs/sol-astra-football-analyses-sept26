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
DEFAULT_HARNESS_DIR_NAME = "football_external_benchmark_harness_prep_v1"
DEFAULT_CLOSEOUT_DIR_NAME = "v7_2_runtime_default_rollout_closeout_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_dataset_access_review_v1"
DEFAULT_SUITE_NAME = "frozen-viable-baseline-slice-suite"

BLOCKER_HARNESS_PREP_MISSING = "football_external_dataset_access_harness_prep_missing"
BLOCKER_RUNTIME_CLOSEOUT_MISSING = "football_external_dataset_access_runtime_closeout_missing"
BLOCKER_NO_SAFE_SMOKE_RESOURCES = "football_external_dataset_access_no_safe_smoke_resources"

NEXT_HARNESS_PREP = "football_external_benchmark_harness_prep"
NEXT_RUNTIME_CLOSEOUT = "v7_2_runtime_default_rollout_closeout"
NEXT_MANUAL_ACCESS = "football_external_manual_dataset_access_setup"
NEXT_SAFE_SMOKE = "football_external_safe_source_adapter_smoke_test"

OFFICIAL_ACCESS_REVIEW: dict[str, dict[str, Any]] = {
    "soccertrack_v2": {
        "accessDecision": "approved_smoke_only",
        "accessRiskClass": "low_with_attribution",
        "downloadAllowedByThisBatch": False,
        "officialSourceUrls": [
            "https://github.com/SoccerTrack/SoccerTrack",
        ],
        "reviewNotes": "Report and official repository metadata indicate open dataset/code terms; keep attribution and license files with any future fetch.",
    },
    "skillcorner_open_data": {
        "accessDecision": "approved_smoke_only",
        "accessRiskClass": "low_with_license_notice",
        "downloadAllowedByThisBatch": False,
        "officialSourceUrls": [
            "https://github.com/SkillCorner/opendata",
        ],
        "reviewNotes": "Open-data repository can drive broadcast tracking smoke adapters; preserve MIT/license notices and do not treat as raw-video CV supervision.",
    },
    "statsbomb_open_data_360": {
        "accessDecision": "approved_smoke_only",
        "accessRiskClass": "open_with_attribution",
        "downloadAllowedByThisBatch": False,
        "officialSourceUrls": [
            "https://github.com/statsbomb/open-data",
        ],
        "reviewNotes": "Useful for event/360 semantics smoke tests only; attribution and logo-use terms must stay attached.",
    },
    "soccernet_broadcast_tasks": {
        "accessDecision": "manual_or_gated",
        "accessRiskClass": "research_gated_non_commercial",
        "downloadAllowedByThisBatch": False,
        "officialSourceUrls": [
            "https://www.soccer-net.org/",
        ],
        "reviewNotes": "Broadcast videos/tasks require SoccerNet access flow and can carry NDA/research-only restrictions; do not download unattended.",
    },
    "metrica_sample_data": {
        "accessDecision": "manual_or_gated",
        "accessRiskClass": "terms_unclear",
        "downloadAllowedByThisBatch": False,
        "officialSourceUrls": [
            "https://github.com/metrica-sports/sample-data",
        ],
        "reviewNotes": "Sample data is useful but the retrieved report did not surface a standard permissive dataset license; require manual terms review before fetch.",
    },
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _suite_root(storage_root: Path) -> Path:
    return Path(storage_root) / "benchmark_suites" / DEFAULT_SUITE_NAME






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "external_dataset_access_license_review",
            "successCriteria": [
                "classify every prepared external resource as smoke-approved or manual/gated",
                "do not download datasets",
                "select safe-source adapter smoke only if at least one low-risk source is available",
            ],
            "failureAdaptation": "If saved access metadata is incomplete, route to access-contract repair or manual setup.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "dataset_access_contract_repair",
            "successCriteria": [
                "repair missing resource metadata without changing runtime defaults or detector weights",
                "preserve source URLs and license notes for manual review",
            ],
            "failureAdaptation": "If safe-source smoke remains impossible, write a manual access blocker summary.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "external_dataset_access_blocker_summary",
            "successCriteria": [
                "name exactly one external access blocker",
                "keep all resources evidence-only until reviewed",
            ],
            "failureAdaptation": "Stop before any dataset download if legal/access state is not clear.",
        },
    ]


def _resources_from_inventory(inventory: dict[str, Any] | None) -> list[dict[str, Any]]:
    resources = (inventory or {}).get("resources")
    if not isinstance(resources, list):
        return []
    return [dict(row) for row in resources if isinstance(row, dict)]


def _review_resource(resource: dict[str, Any]) -> dict[str, Any]:
    resource_id = str(resource.get("resourceId", "")).strip()
    policy = OFFICIAL_ACCESS_REVIEW.get(
        resource_id,
        {
            "accessDecision": "manual_or_gated",
            "accessRiskClass": "unknown_terms",
            "downloadAllowedByThisBatch": False,
            "officialSourceUrls": [],
            "reviewNotes": "No current saved access decision exists; require manual verification before use.",
        },
    )
    reviewed = dict(resource)
    reviewed.update(policy)
    reviewed["evidenceOnlyUntilReviewed"] = True
    reviewed["executionStatus"] = "not_downloaded"
    reviewed["licenseReviewStatus"] = (
        "reviewed_for_smoke_no_download" if policy["accessDecision"] == "approved_smoke_only" else "manual_review_required"
    )
    reviewed["trainingUseAllowed"] = False
    reviewed["benchmarkSmokeUseAllowed"] = policy["accessDecision"] == "approved_smoke_only"
    return reviewed


def _stage_coverage(resources: list[dict[str, Any]]) -> list[str]:
    stages: set[str] = set()
    for resource in resources:
        for stage in resource.get("coveredStages") or []:
            if str(stage).strip():
                stages.add(str(stage))
    return sorted(stages)


def _load_inputs(storage_root: Path) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, DEFAULT_CANDIDATE_NAME)
    harness_root = candidate_root / DEFAULT_HARNESS_DIR_NAME
    closeout_root = _suite_root(storage_root) / DEFAULT_CLOSEOUT_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "outputRoot": candidate_root / DEFAULT_OUTPUT_DIR_NAME,
        "harnessRoot": harness_root,
        "harnessSummary": _load_json(harness_root / "external_benchmark_harness_summary.json"),
        "resourceInventory": _load_json(harness_root / "benchmark_resource_inventory.json"),
        "adapterContract": _load_json(harness_root / "dataset_adapter_contract.json"),
        "stageGateContract": _load_json(harness_root / "stage_gate_contract.json"),
        "closeoutSummary": _load_json(closeout_root / "runtime_default_rollout_closeout_summary.json"),
    }


def _classify(
    *,
    harness_summary: dict[str, Any] | None,
    closeout_summary: dict[str, Any] | None,
    safe_resources: list[dict[str, Any]],
) -> tuple[str | None, str, bool, bool, str]:
    if not (
        isinstance(harness_summary, dict)
        and harness_summary.get("goalAchieved") is True
        and harness_summary.get("datasetAccessReviewReady") is True
    ):
        return (
            BLOCKER_HARNESS_PREP_MISSING,
            NEXT_HARNESS_PREP,
            False,
            False,
            "External benchmark harness prep is missing or not access-review-ready.",
        )
    if not (
        isinstance(closeout_summary, dict)
        and closeout_summary.get("goalAchieved") is True
        and closeout_summary.get("runtimeDefaultRolloutClosed") is True
    ):
        return (
            BLOCKER_RUNTIME_CLOSEOUT_MISSING,
            NEXT_RUNTIME_CLOSEOUT,
            False,
            False,
            "Runtime-default rollout closeout is missing; close the v7.2 default rollout before external access work.",
        )
    if not safe_resources:
        return (
            BLOCKER_NO_SAFE_SMOKE_RESOURCES,
            NEXT_MANUAL_ACCESS,
            False,
            False,
            "No prepared external resource is safe enough for unattended adapter smoke work.",
        )
    return (
        None,
        NEXT_SAFE_SMOKE,
        True,
        True,
        "External dataset access review found safe smoke-test resources while keeping gated/manual resources blocked from download.",
    )


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External Dataset Access Review",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Safe source adapter smoke ready: `{summary.get('safeSourceAdapterSmokeReady')}`",
            f"- Full external benchmark execution ready: `{summary.get('fullExternalBenchmarkExecutionReady')}`",
            f"- Dataset download executed: `{summary.get('datasetDownloadExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_dataset_access_review(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "external_dataset_access_license_review",
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    inputs = _load_inputs(storage_root)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    resources = [_review_resource(row) for row in _resources_from_inventory(inputs["resourceInventory"])]
    safe_resources = [row for row in resources if row.get("accessDecision") == "approved_smoke_only"]
    manual_resources = [row for row in resources if row.get("accessDecision") != "approved_smoke_only"]
    primary_blocker, next_lever, goal_achieved, smoke_ready, english = _classify(
        harness_summary=inputs["harnessSummary"],
        closeout_summary=inputs["closeoutSummary"],
        safe_resources=safe_resources,
    )
    generated_at = _utc_now_iso()
    attempts = _attempt_plan()
    resource_decision_counts = {
        "approved_smoke_only": len(safe_resources),
        "manual_or_gated": len(manual_resources),
        "download_approved": 0,
    }
    safe_stage_coverage = _stage_coverage(safe_resources)
    all_stage_coverage = _stage_coverage(resources)
    summary: dict[str, Any] = {
        "batchName": "football_external_dataset_access_review",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [item["attemptApproachFamily"] for item in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": True,
        "primaryBlocker": primary_blocker,
        "sourceHarnessBatch": "football_external_benchmark_harness_prep",
        "sourceRuntimeCloseoutBatch": "v7_2_runtime_default_rollout_closeout",
        "resourceCount": len(resources),
        "safeSmokeResourceCount": len(safe_resources),
        "manualOrGatedResourceCount": len(manual_resources),
        "safeSmokeResourceIds": [row["resourceId"] for row in safe_resources],
        "manualOrGatedResourceIds": [row["resourceId"] for row in manual_resources],
        "safeSmokeStageCoverage": safe_stage_coverage,
        "allResourceStageCoverage": all_stage_coverage,
        "safeSourceAdapterSmokeReady": smoke_ready,
        "fullExternalBenchmarkExecutionReady": False,
        "datasetDownloadAllowedByThisBatch": False,
        "datasetDownloadExecuted": False,
        "trainingAllowed": False,
        "trainingExecuted": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationAllowed": False,
        "runtimeDefaultMutationExecuted": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }

    decision_matrix = {
        "generatedAt": generated_at,
        "resourceDecisionCounts": resource_decision_counts,
        "decisions": [
            {
                "condition": "harness_prep_missing",
                "selected": primary_blocker == BLOCKER_HARNESS_PREP_MISSING,
                "nextRecommendedNextLever": NEXT_HARNESS_PREP,
            },
            {
                "condition": "runtime_rollout_closeout_missing",
                "selected": primary_blocker == BLOCKER_RUNTIME_CLOSEOUT_MISSING,
                "nextRecommendedNextLever": NEXT_RUNTIME_CLOSEOUT,
            },
            {
                "condition": "no_safe_smoke_resources",
                "selected": primary_blocker == BLOCKER_NO_SAFE_SMOKE_RESOURCES,
                "nextRecommendedNextLever": NEXT_MANUAL_ACCESS,
            },
            {
                "condition": "safe_source_adapter_smoke_ready",
                "selected": goal_achieved,
                "nextRecommendedNextLever": NEXT_SAFE_SMOKE,
            },
        ],
    }
    manual_plan = {
        "generatedAt": generated_at,
        "manualReviewRequiredBeforeDownload": True,
        "resources": manual_resources,
        "recommendedNextActions": [
            "Do not download gated or unclear-term resources unattended.",
            "Confirm SoccerNet NDA/research terms before any use.",
            "Confirm Metrica sample-data redistribution/training terms before any use.",
            "Run safe-source adapter smoke only on approved smoke resources first.",
        ],
    }
    smoke_manifest = {
        "generatedAt": generated_at,
        "datasetDownloadExecuted": False,
        "approvedSmokeResources": safe_resources,
        "safeSmokeStageCoverage": safe_stage_coverage,
        "nextRecommendedNextLever": NEXT_SAFE_SMOKE if safe_resources else NEXT_MANUAL_ACCESS,
    }
    access_policy = {
        "generatedAt": generated_at,
        "policy": "No dataset download, training, or redistribution is allowed from this batch. Approved resources are adapter-smoke candidates only.",
        "officialAccessReview": OFFICIAL_ACCESS_REVIEW,
    }

    _write_json(output_root / "external_dataset_access_review_summary.json", summary)
    _write_json(output_root / "dataset_access_decision_matrix.json", decision_matrix)
    _write_json(output_root / "approved_smoke_resource_manifest.json", smoke_manifest)
    _write_json(
        output_root / "manual_or_gated_access_audit.json",
        {"generatedAt": generated_at, "manualOrGatedResources": manual_resources},
    )
    _write_json(output_root / "dataset_access_policy.json", access_policy)
    _write_json(output_root / "manual_access_followup_plan.json", manual_plan)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(
        output_root / "batch_outcome_analysis.json",
        {
            "summary": summary,
            "decisionMatrix": decision_matrix,
            "approvedSmokeResourceManifest": smoke_manifest,
            "manualAccessFollowupPlan": manual_plan,
        },
    )
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review access/licensing posture for prepared external benchmark datasets.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="external_dataset_access_license_review")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_dataset_access_review(
        storage_root=args.storage_root,
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
