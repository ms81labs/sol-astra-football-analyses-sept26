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
DEFAULT_RANGE_INDEX_DIR_NAME = "football_external_soccernet_split_archive_range_index_probe_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_zip_label_member_extract_approval_v1"

BLOCKER_RANGE_INDEX_MISSING = "football_external_soccernet_zip_label_member_range_index_missing"
BLOCKER_LABEL_MEMBER_MISSING = "football_external_soccernet_zip_label_member_missing"

NEXT_RANGE_INDEX = "football_external_soccernet_split_archive_range_index_probe"
NEXT_MANUAL_CONTENT_REVIEW = "football_external_soccernet_split_archive_manual_content_review"
NEXT_LABEL_MEMBER_EXTRACT = "football_external_soccernet_zip_label_member_extract"


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_label_member_extract_approval",
            "successCriteria": [
                "approve only ZIP label-member range extraction",
                "keep full archive and video member downloads disallowed",
                "require runtime-only SoccerNet credential for encrypted member extraction",
            ],
            "failureAdaptation": "If label members are missing, return to content review.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_encrypted_label_member_contract_repair",
            "successCriteria": [
                "include central-directory offsets and compression metadata needed for encrypted label extraction",
                "do not permit video extraction",
            ],
            "failureAdaptation": "If encrypted label extraction cannot be scoped safely, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_label_member_extract_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "do not approve full archive download",
            ],
            "failureAdaptation": "Stop before any archive/video fetch.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    range_root = candidate_root / DEFAULT_RANGE_INDEX_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "rangeSummary": _load_json(range_root / "split_archive_range_index_probe_summary.json"),
        "centralDirectoryAudit": _load_json(range_root / "zip_central_directory_audit.json"),
        "approvalSeedContract": _load_json(range_root / "zip_label_member_extract_approval_contract.json"),
    }


def _range_index_ready(range_summary: dict[str, Any] | None, seed_contract: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(range_summary, dict)
        and range_summary.get("goalAchieved") is True
        and range_summary.get("primaryBlocker") is None
        and range_summary.get("zipCentralDirectoryParsed") is True
        and int(range_summary.get("labelMemberCount") or 0) > 0
        and range_summary.get("archiveDownloadExecuted") is False
        and range_summary.get("videoMemberDownloadExecuted") is False
        and range_summary.get("trainingExecuted") is False
        and isinstance(seed_contract, dict)
        and seed_contract.get("contractName") == "football_external_soccernet_zip_label_member_extract_approval"
        and seed_contract.get("approvalRequiredBeforeLabelMemberExtraction") is True
        and seed_contract.get("fullArchiveDownloadApproved") is False
        and seed_contract.get("videoMemberDownloadAllowed") is False
        and seed_contract.get("labelMemberRangeExtractionOnly") is True
    )


def _label_member_entries(central_directory_audit: dict[str, Any] | None, label_paths: list[Any]) -> list[dict[str, Any]]:
    wanted = {str(path) for path in label_paths if path}
    entries = (central_directory_audit or {}).get("zipEntries")
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict) and str(entry.get("path") or "") in wanted]


def _classify(range_ready: bool, label_member_entries: list[dict[str, Any]]) -> tuple[str | None, str, bool, str]:
    if not range_ready:
        return (
            BLOCKER_RANGE_INDEX_MISSING,
            NEXT_RANGE_INDEX,
            False,
            "ZIP range-index truth is missing or unsafe; rerun the range-index probe before approving label extraction.",
        )
    if not label_member_entries:
        return (
            BLOCKER_LABEL_MEMBER_MISSING,
            NEXT_MANUAL_CONTENT_REVIEW,
            False,
            "No label member entry is available for extraction approval; manually review archive contents.",
        )
    return (
        None,
        NEXT_LABEL_MEMBER_EXTRACT,
        True,
        "Approved a label-member-only range extraction contract. Full archive and video member downloads remain blocked.",
    )


def _extract_contract(seed_contract: dict[str, Any] | None, label_member_entries: list[dict[str, Any]]) -> dict[str, Any]:
    seed_contract = seed_contract or {}
    compression_methods = sorted({int(row.get("compressionMethod") or 0) for row in label_member_entries})
    return {
        "contractName": NEXT_LABEL_MEMBER_EXTRACT,
        "sourceBatch": "football_external_soccernet_zip_label_member_extract_approval",
        "selectedArchiveTask": seed_contract.get("selectedArchiveTask"),
        "selectedArchivePath": seed_contract.get("selectedArchivePath"),
        "labelMemberExtractionApproved": True,
        "labelMemberRangeExtractionOnly": True,
        "approvedLabelMemberCount": len(label_member_entries),
        "labelMembers": label_member_entries,
        "compressionMethodSet": compression_methods,
        "encryptedZipMemberLikely": 99 in compression_methods,
        "credentialRequired": 99 in compression_methods,
        "credentialEnvVar": "SOCCERNET_PASSWORD" if 99 in compression_methods else None,
        "credentialPersisted": False,
        "fullArchiveDownloadApproved": False,
        "videoMemberDownloadAllowed": False,
        "videoMemberDownloadExecuted": False,
        "trainingUseAllowed": False,
    }


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {
                "condition": "zip_range_index_missing",
                "selected": primary_blocker == BLOCKER_RANGE_INDEX_MISSING,
                "primaryBlocker": BLOCKER_RANGE_INDEX_MISSING,
                "nextRecommendedNextLever": NEXT_RANGE_INDEX,
            },
            {
                "condition": "label_member_missing",
                "selected": primary_blocker == BLOCKER_LABEL_MEMBER_MISSING,
                "primaryBlocker": BLOCKER_LABEL_MEMBER_MISSING,
                "nextRecommendedNextLever": NEXT_MANUAL_CONTENT_REVIEW,
            },
            {
                "condition": "label_member_extract_ready",
                "selected": goal_achieved,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_LABEL_MEMBER_EXTRACT,
            },
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet ZIP Label Member Extract Approval",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Label member extraction approved: `{summary.get('labelMemberExtractionApproved')}`",
            f"- Approved label members: `{summary.get('approvedLabelMemberCount')}`",
            f"- Credential required: `{summary.get('credentialRequired')}`",
            f"- Full archive download approved: `{summary.get('fullArchiveDownloadApproved')}`",
            f"- Video member download allowed: `{summary.get('videoMemberDownloadAllowed')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_zip_label_member_extract_approval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_label_member_extract_approval",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    seed_contract = inputs["approvalSeedContract"]
    label_paths = seed_contract.get("labelMemberPaths") if isinstance(seed_contract, dict) else []
    label_entries = _label_member_entries(inputs["centralDirectoryAudit"], label_paths if isinstance(label_paths, list) else [])
    range_ready = _range_index_ready(inputs["rangeSummary"], seed_contract)
    primary_blocker, next_lever, goal_achieved, english = _classify(range_ready, label_entries)
    extract_contract = _extract_contract(seed_contract, label_entries) if goal_achieved else {"contractName": NEXT_LABEL_MEMBER_EXTRACT, "labelMemberExtractionApproved": False}
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    compression_methods = extract_contract.get("compressionMethodSet") if isinstance(extract_contract, dict) else []

    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_zip_label_member_extract_approval",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_split_archive_range_index_probe",
        "labelMemberExtractionApproved": bool(goal_achieved),
        "approvedLabelMemberCount": len(label_entries) if goal_achieved else 0,
        "compressionMethodSet": compression_methods if goal_achieved else [],
        "encryptedZipMemberLikely": 99 in compression_methods if isinstance(compression_methods, list) else False,
        "credentialRequired": bool(extract_contract.get("credentialRequired")) if goal_achieved else False,
        "credentialPersisted": False,
        "fullArchiveDownloadApproved": False,
        "archiveDownloadExecuted": False,
        "videoMemberDownloadAllowed": False,
        "videoMemberDownloadExecuted": False,
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
    decision_matrix = _decision_matrix(primary_blocker, next_lever, goal_achieved)
    approval_audit = {
        "labelMemberPaths": [row.get("path") for row in label_entries],
        "labelMemberExtractionApproved": goal_achieved,
        "fullArchiveDownloadApproved": False,
        "videoMemberDownloadAllowed": False,
        "credentialRequired": summary["credentialRequired"],
        "credentialPersisted": False,
    }
    batch_outcome = {
        "summary": summary,
        "labelMemberExtractionApprovalAudit": approval_audit,
        "zipLabelMemberExtractContract": extract_contract,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "zip_label_member_extract_approval_summary.json", summary)
    _write_json(output_root / "label_member_extraction_approval_audit.json", approval_audit)
    _write_json(output_root / "zip_label_member_extract_contract.json", extract_contract)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_label_member_extract_approval")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_zip_label_member_extract_approval(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        output_dir_name=args.output_dir_name,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("goalAchieved") else 1


if __name__ == "__main__":
    raise SystemExit(main())
