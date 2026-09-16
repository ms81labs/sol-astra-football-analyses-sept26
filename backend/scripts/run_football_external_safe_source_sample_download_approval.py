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
DEFAULT_PLAN_DIR_NAME = "football_external_safe_source_sample_ingestion_plan_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_safe_source_sample_download_approval_v1"

BLOCKER_PLAN_MISSING = "football_external_sample_download_approval_plan_missing"
BLOCKER_UNKNOWN_SOURCE = "football_external_sample_download_approval_unknown_source"

NEXT_SAMPLE_INGESTION_PLAN = "football_external_safe_source_sample_ingestion_plan"
NEXT_CONTROLLED_FETCH = "football_external_safe_source_controlled_sample_fetch"

SOCCERTRACK_V2_EVIDENCE = {
    "resourceId": "soccertrack_v2",
    "correctedOfficialSourceUrl": "https://github.com/AtomScott/SoccerTrack-v2",
    "datasetLandingPageUrl": "https://atomscott.github.io/SoccerTrack-v2/",
    "huggingFaceDatasetUrl": "https://huggingface.co/datasets/atomscott/soccertrack-v2",
    "arxivUrl": "https://arxiv.org/abs/2508.01802",
    "licenseEvidence": [
        "GitHub README lists code as MIT and dataset videos/annotations as CC BY 4.0.",
        "Dataset landing page describes open access and research citation requirements.",
        "Hugging Face mirror currently reports apache-2.0 metadata and appears empty, so it is not selected as the first fetch target.",
    ],
    "licenseUseClass": "controlled_sample_allowed_with_attribution",
    "approvalLimitations": [
        "Full dataset download is not approved by this batch.",
        "Training use is not approved by this batch.",
        "Any fetch must preserve license, attribution, source URL, and version/provenance metadata.",
    ],
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "safe_source_sample_download_approval",
            "successCriteria": [
                "verify the selected source has saved current access evidence",
                "correct stale source URLs before any fetch",
                "approve only controlled sample/metadata fetch scope",
            ],
            "failureAdaptation": "If source evidence is incomplete, move to access evidence repair.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "sample_source_access_evidence_repair",
            "successCriteria": [
                "repair official source URL and license evidence",
                "keep full dataset download and training disallowed",
            ],
            "failureAdaptation": "If approval cannot be granted safely, write a blocker summary.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "sample_download_approval_blocker_summary",
            "successCriteria": [
                "select exactly one next corrective family",
                "do not fetch external bytes",
            ],
            "failureAdaptation": "Stop before controlled fetch until source access is approved.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    plan_root = candidate_root / DEFAULT_PLAN_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "planRoot": plan_root,
        "planSummary": _load_json(plan_root / "safe_source_sample_ingestion_plan_summary.json"),
        "approvalChecklist": _load_json(plan_root / "sample_download_approval_checklist.json"),
        "guardrailAudit": _load_json(plan_root / "sample_ingestion_guardrail_audit.json"),
    }


def _selected_resource_id(plan_summary: dict[str, Any] | None, approval_checklist: dict[str, Any] | None) -> str | None:
    selected = (plan_summary or {}).get("selectedFirstSampleResourceId")
    if selected:
        return str(selected)
    selected = (approval_checklist or {}).get("selectedFirstSampleResourceId")
    return str(selected) if selected else None


def _classify(plan_summary: dict[str, Any] | None, selected_resource_id: str | None) -> tuple[str | None, str, bool, str]:
    if not (
        isinstance(plan_summary, dict)
        and plan_summary.get("goalAchieved") is True
        and plan_summary.get("sampleIngestionPlanReady") is True
        and plan_summary.get("sampleDownloadExecuted") is False
        and plan_summary.get("datasetDownloadExecuted") is False
    ):
        return (
            BLOCKER_PLAN_MISSING,
            NEXT_SAMPLE_INGESTION_PLAN,
            False,
            "Safe-source sample ingestion plan is missing or did not preserve no-download guardrails.",
        )
    if selected_resource_id != "soccertrack_v2":
        return (
            BLOCKER_UNKNOWN_SOURCE,
            NEXT_SAMPLE_INGESTION_PLAN,
            False,
            "The selected sample source is not covered by the current saved approval evidence.",
        )
    return (
        None,
        NEXT_CONTROLLED_FETCH,
        True,
        "SoccerTrack v2 is approved for a controlled smallest-sample or metadata fetch with attribution; full dataset download, training, promotion, and runtime mutation remain disallowed.",
    )


def _approval_contract(selected_resource_id: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "selectedSampleResourceId": selected_resource_id,
        "approvedFetchScope": "smallest_official_sample_or_metadata_only" if goal_achieved else None,
        "sampleDownloadApproved": goal_achieved,
        "sampleDownloadExecuted": False,
        "fullDatasetDownloadApproved": False,
        "trainingUseApproved": False,
        "requiredFetchMetadata": [
            "sourceUrl",
            "sourceCommitOrVersion",
            "licenseFilePath",
            "attributionText",
            "fetchedFileList",
            "sha256ByFile",
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External Safe Source Sample Download Approval",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Selected sample resource: `{summary.get('selectedSampleResourceId')}`",
            f"- Official source URL corrected: `{summary.get('officialSourceUrlCorrected')}`",
            f"- Sample download approved: `{summary.get('sampleDownloadApproved')}`",
            f"- Sample download executed: `{summary.get('sampleDownloadExecuted')}`",
            f"- Dataset download executed: `{summary.get('datasetDownloadExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation allowed: `{summary.get('runtimeDefaultMutationAllowed')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_safe_source_sample_download_approval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "safe_source_sample_download_approval",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    selected_resource_id = _selected_resource_id(inputs["planSummary"], inputs["approvalChecklist"])
    primary_blocker, next_lever, goal_achieved, english = _classify(inputs["planSummary"], selected_resource_id)
    generated_at = _utc_now_iso()
    attempts = _attempt_plan()
    evidence = dict(SOCCERTRACK_V2_EVIDENCE) if selected_resource_id == "soccertrack_v2" else {
        "resourceId": selected_resource_id,
        "licenseUseClass": "not_approved",
    }
    contract = _approval_contract(selected_resource_id, goal_achieved)
    summary: dict[str, Any] = {
        "batchName": "football_external_safe_source_sample_download_approval",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_safe_source_sample_ingestion_plan",
        "selectedSampleResourceId": selected_resource_id,
        "officialSourceUrlCorrected": selected_resource_id == "soccertrack_v2",
        "correctedOfficialSourceUrl": evidence.get("correctedOfficialSourceUrl"),
        "licenseUseClass": evidence.get("licenseUseClass"),
        "sampleDownloadApproved": goal_achieved,
        "sampleDownloadExecuted": False,
        "fullDatasetDownloadApproved": False,
        "datasetDownloadAllowedByThisBatch": False,
        "datasetDownloadExecuted": False,
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
    decision_matrix = {
        "generatedAt": generated_at,
        "decisions": [
            {"condition": "sample_ingestion_plan_missing", "selected": primary_blocker == BLOCKER_PLAN_MISSING, "nextRecommendedNextLever": NEXT_SAMPLE_INGESTION_PLAN},
            {"condition": "unknown_selected_source", "selected": primary_blocker == BLOCKER_UNKNOWN_SOURCE, "nextRecommendedNextLever": NEXT_SAMPLE_INGESTION_PLAN},
            {"condition": "controlled_sample_fetch_approved", "selected": goal_achieved, "nextRecommendedNextLever": NEXT_CONTROLLED_FETCH},
        ],
    }
    batch_outcome = {
        "summary": summary,
        "selectedSourceAccessEvidenceAudit": evidence,
        "controlledSampleFetchApprovalContract": contract,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }
    _write_json(output_root / "sample_download_approval_summary.json", summary)
    _write_json(output_root / "selected_source_access_evidence_audit.json", evidence)
    _write_json(output_root / "controlled_sample_fetch_approval_contract.json", contract)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Approve a controlled safe-source sample fetch without executing downloads.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="safe_source_sample_download_approval")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_safe_source_sample_download_approval(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
