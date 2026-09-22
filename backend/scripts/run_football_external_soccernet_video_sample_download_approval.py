from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_video_sample_download_approval_v1"
DEFAULT_MAX_APPROVED_BYTES = 50_000_000

BLOCKER_PRODUCT_MISSING = "football_external_soccernet_event_report_product_integration_missing"
BLOCKER_VIDEO_MEMBER_MISSING = "football_external_soccernet_video_member_selection_gap"

NEXT_PRODUCT_INTEGRATION = "football_external_soccernet_event_report_product_integration"
NEXT_MEMBER_REPAIR = "football_external_soccernet_video_member_selection_contract_repair"
NEXT_CONTROLLED_FETCH = "football_external_soccernet_controlled_video_sample_fetch"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "controlled_video_sample_download_approval",
            "successCriteria": [
                "select one smallest SoccerNet video member for a future controlled sample fetch",
                "cap approved bytes and preserve full archive download block",
                "do not download video in this approval batch",
            ],
            "failureAdaptation": "If no suitable member is found, repair video member selection contract.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "video_member_selection_contract_repair",
            "successCriteria": [
                "repair selected member from ZIP index metadata only",
                "keep product report and event-only truth unchanged",
            ],
            "failureAdaptation": "If product integration is missing, route back to product integration.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "video_sample_approval_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before any video bytes, training, promotion, or runtime mutation",
            ],
            "failureAdaptation": "Route to product integration or member selection repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    return {
        "candidateRoot": candidate_root,
        "productSummary": _load_json(candidate_root / "football_external_soccernet_event_report_product_integration_v1/soccernet_event_report_product_integration_summary.json"),
        "zipAudit": _load_json(candidate_root / "football_external_soccernet_split_archive_range_index_probe_v1/zip_central_directory_audit.json"),
    }


def _product_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("productEventReportReady") is True
        and summary.get("fullMatchAnalysisReady") is False
        and summary.get("trainingExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
    )


def _video_members(zip_audit: dict[str, Any] | None) -> list[dict[str, Any]]:
    entries = zip_audit.get("zipEntries") if isinstance(zip_audit, dict) else []
    members: list[dict[str, Any]] = []
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict) or entry.get("isDirectory"):
            continue
        path = str(entry.get("path") or "")
        if not path.lower().endswith(".mp4"):
            continue
        members.append(
            {
                "path": path,
                "compressionMethod": entry.get("compressionMethod"),
                "compressedSizeBytes": int(entry.get("compressedSizeBytes") or 0),
                "uncompressedSizeBytes": int(entry.get("uncompressedSizeBytes") or 0),
                "localHeaderOffset": int(entry.get("localHeaderOffset") or 0),
            }
        )
    return sorted(members, key=lambda row: (row["uncompressedSizeBytes"], row["path"]))


def _approval_contract(selected: dict[str, Any] | None, members: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "contractName": "football_external_soccernet_controlled_video_sample_fetch",
        "sourceBatch": "football_external_soccernet_video_sample_download_approval",
        "videoSampleDownloadApproved": selected is not None,
        "selectedVideoMemberPath": selected.get("path") if selected else None,
        "selectedCompressionMethod": selected.get("compressionMethod") if selected else None,
        "selectedCompressedSizeBytes": selected.get("compressedSizeBytes") if selected else None,
        "selectedUncompressedSizeBytes": selected.get("uncompressedSizeBytes") if selected else None,
        "selectedLocalHeaderOffset": selected.get("localHeaderOffset") if selected else None,
        "availableVideoMembers": members,
        "maxApprovedBytes": DEFAULT_MAX_APPROVED_BYTES,
        "fullArchiveDownloadApproved": False,
        "videoMemberDownloadExecuted": False,
        "requiresRuntimeCredential": True,
        "credentialPersistenceAllowed": False,
        "trainingUseAllowed": False,
        "promotionUseAllowed": False,
        "runtimeDefaultMutationAllowed": False,
    }


def _classify(product_ready: bool, selected: dict[str, Any] | None) -> tuple[str | None, str, bool, str]:
    if not product_ready:
        return (
            BLOCKER_PRODUCT_MISSING,
            NEXT_PRODUCT_INTEGRATION,
            False,
            "SoccerNet event report product integration is missing or unsafe; rerun it before video sample approval.",
        )
    if selected is None:
        return (
            BLOCKER_VIDEO_MEMBER_MISSING,
            NEXT_MEMBER_REPAIR,
            False,
            "No SoccerNet video member could be selected from ZIP metadata; repair member selection before fetch.",
        )
    return (
        None,
        NEXT_CONTROLLED_FETCH,
        True,
        "Controlled SoccerNet video-sample fetch is approved for the smallest video member with a byte cap. This batch did not download video.",
    )


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "event_report_product_integration_missing", "selected": primary_blocker == BLOCKER_PRODUCT_MISSING, "primaryBlocker": BLOCKER_PRODUCT_MISSING, "nextRecommendedNextLever": NEXT_PRODUCT_INTEGRATION},
            {"condition": "video_member_selection_gap", "selected": primary_blocker == BLOCKER_VIDEO_MEMBER_MISSING, "primaryBlocker": BLOCKER_VIDEO_MEMBER_MISSING, "nextRecommendedNextLever": NEXT_MEMBER_REPAIR},
            {"condition": "controlled_video_sample_fetch_approved", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_CONTROLLED_FETCH},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Video Sample Download Approval",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Video sample download approved: `{summary.get('videoSampleDownloadApproved')}`",
            f"- Selected video member: `{summary.get('selectedVideoMemberPath')}`",
            f"- Full archive download approved: `{summary.get('fullArchiveDownloadApproved')}`",
            f"- Video member download executed: `{summary.get('videoMemberDownloadExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_video_sample_download_approval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "controlled_video_sample_download_approval",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _product_ready(inputs["productSummary"])
    members = _video_members(inputs["zipAudit"])
    selected = members[0] if members else None
    contract = _approval_contract(selected, members)
    primary_blocker, next_lever, goal_achieved, english = _classify(ready, selected)
    attempts = _attempt_plan()
    generated_at = utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_video_sample_download_approval",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_event_report_product_integration",
        "videoSampleDownloadApproved": goal_achieved,
        "selectedVideoMemberPath": contract["selectedVideoMemberPath"],
        "selectedCompressedSizeBytes": contract["selectedCompressedSizeBytes"],
        "selectedUncompressedSizeBytes": contract["selectedUncompressedSizeBytes"],
        "maxApprovedBytes": contract["maxApprovedBytes"],
        "fullArchiveDownloadApproved": False,
        "archiveDownloadExecuted": False,
        "videoMemberDownloadExecuted": False,
        "datasetDownloadExecuted": False,
        "fullOriginalVideoDownloadExecuted": False,
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
    batch_outcome = {
        "summary": summary,
        "videoSampleDownloadApprovalContract": contract,
        "videoMemberSelectionAudit": {"selected": selected, "availableVideoMembers": members},
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "video_sample_download_approval_summary.json", summary)
    _write_json(output_root / "video_sample_download_approval_contract.json", contract)
    _write_json(output_root / "video_member_selection_audit.json", {"selected": selected, "availableVideoMembers": members})
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
    parser.add_argument("--attempt-approach-family", default="controlled_video_sample_download_approval")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_video_sample_download_approval(
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
