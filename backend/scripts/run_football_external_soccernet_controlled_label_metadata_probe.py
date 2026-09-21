from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_LISTING_DIR_NAME = "football_external_soccernet_api_listing_probe_v1"
DEFAULT_APPROVAL_DIR_NAME = "football_external_soccernet_nda_api_access_approval_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_controlled_label_metadata_probe_v1"

BLOCKER_LISTING_MISSING = "football_external_soccernet_api_listing_probe_missing"
BLOCKER_BALL_SURFACE_MISSING = "football_external_soccernet_ball_label_surface_missing"

NEXT_LISTING_PROBE = "football_external_soccernet_api_listing_probe"
NEXT_LISTING_REPAIR = "football_external_soccernet_api_listing_contract_repair"
NEXT_LABEL_SAMPLE_FETCH_APPROVAL = "football_external_soccernet_controlled_label_sample_fetch_approval"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_controlled_label_metadata_surface_probe",
            "successCriteria": [
                "read SoccerNet listing probe output",
                "find the smallest SoccerNet ball-label task/split surface",
                "write a label-only fetch contract for a later approval batch",
                "do not download labels, videos, features, datasets, or train models",
            ],
            "failureAdaptation": "If ball-label surface is missing, repair the SoccerNet listing/task contract.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_label_metadata_contract_repair",
            "successCriteria": [
                "repair task/split selection or fetch-contract metadata",
                "keep original-video download disallowed",
            ],
            "failureAdaptation": "If no ball-label surface exists, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_label_metadata_blocker_summary",
            "successCriteria": [
                "select exactly one next corrective family",
                "do not download SoccerNet data",
            ],
            "failureAdaptation": "Stop before label access.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    listing_root = candidate_root / DEFAULT_LISTING_DIR_NAME
    approval_root = candidate_root / DEFAULT_APPROVAL_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "listingSummary": _load_json(listing_root / "soccernet_api_listing_probe_summary.json"),
        "listingAudit": _load_json(listing_root / "soccernet_api_listing_audit.json"),
        "accessContract": _load_json(approval_root / "soccernet_api_access_contract.json"),
    }


def _listing_ready(listing_summary: dict[str, Any] | None, listing_audit: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(listing_summary, dict)
        and listing_summary.get("goalAchieved") is True
        and listing_summary.get("apiListingExecuted") is True
        and listing_summary.get("networkApiCallExecuted") is False
        and listing_summary.get("datasetDownloadExecuted") is False
        and isinstance(listing_audit, dict)
        and int(listing_audit.get("totalListedGameRefs") or 0) > 0
    )


def _ball_surface(listing_audit: dict[str, Any] | None) -> dict[str, Any]:
    task_split_counts = (listing_audit or {}).get("taskSplitCounts")
    sample_game_refs = (listing_audit or {}).get("sampleGameRefs")
    if not isinstance(task_split_counts, dict):
        task_split_counts = {}
    if not isinstance(sample_game_refs, dict):
        sample_game_refs = {}
    ball_counts = task_split_counts.get("spotting-ball")
    ball_samples = sample_game_refs.get("spotting-ball")
    if not isinstance(ball_counts, dict):
        ball_counts = {}
    if not isinstance(ball_samples, dict):
        ball_samples = {}
    split_priority = ("valid", "train", "test", "challenge")
    selected_split = None
    selected_count = 0
    selected_refs: list[str] = []
    for split in split_priority:
        count = int(ball_counts.get(split) or 0)
        refs = ball_samples.get(split)
        if not isinstance(refs, list):
            refs = []
        if count > 0 and refs:
            selected_split = split
            selected_count = min(count, 1)
            selected_refs = [str(refs[0])]
            break
    total_ball_refs = sum(int(value or 0) for value in ball_counts.values())
    return {
        "ballTaskAvailable": total_ball_refs > 0,
        "task": "spotting-ball",
        "taskSplitCounts": ball_counts,
        "totalBallGameRefs": total_ball_refs,
        "selectedSplit": selected_split,
        "selectedGameRefCount": selected_count,
        "selectedGameRefs": selected_refs,
        "selectionPolicy": "smallest_single_game_valid_split_first",
        "candidateFiles": ["Labels.json"],
    }


def _fetch_contract(
    *,
    ball_surface: dict[str, Any],
    access_contract: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "contractName": "football_external_soccernet_controlled_label_sample_fetch",
        "sourceBatch": "football_external_soccernet_controlled_label_metadata_probe",
        "resourceId": "soccernet_broadcast_tasks",
        "task": ball_surface.get("task"),
        "split": ball_surface.get("selectedSplit"),
        "gameRefs": ball_surface.get("selectedGameRefs") or [],
        "files": ball_surface.get("candidateFiles") or ["Labels.json"],
        "maxGameCount": int(ball_surface.get("selectedGameRefCount") or 0),
        "fetchScope": "single_game_label_metadata_only",
        "approvalRequiredBeforeDownload": True,
        "labelDownloadApprovedByPreviousContract": bool((access_contract or {}).get("labelDownloadApproved")),
        "credentialEnvVar": (access_contract or {}).get("credentialEnvVar") or "SOCCERNET_PASSWORD",
        "credentialPersisted": False,
        "passwordRedacted": True,
        "fullOriginalVideoDownloadApproved": False,
        "videoDownloadAllowed": False,
        "featureDownloadAllowed": False,
        "datasetBulkDownloadAllowed": False,
        "trainingUseAllowed": False,
    }


def _classify(
    *,
    listing_ready: bool,
    ball_surface: dict[str, Any],
) -> tuple[str | None, str, bool, str]:
    if not listing_ready:
        return (
            BLOCKER_LISTING_MISSING,
            NEXT_LISTING_PROBE,
            False,
            "SoccerNet listing probe truth is missing or not passed.",
        )
    if not (ball_surface.get("ballTaskAvailable") and ball_surface.get("selectedGameRefs")):
        return (
            BLOCKER_BALL_SURFACE_MISSING,
            NEXT_LISTING_REPAIR,
            False,
            "SoccerNet listing did not expose a usable spotting-ball label surface.",
        )
    return (
        None,
        NEXT_LABEL_SAMPLE_FETCH_APPROVAL,
        True,
        "SoccerNet ball-label metadata surface is identified. Advance to a label-sample fetch approval batch before downloading labels.",
    )


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Controlled Label Metadata Probe",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Selected task: `{summary.get('selectedTask')}`",
            f"- Selected split: `{summary.get('selectedSplit')}`",
            f"- Selected game refs: `{summary.get('selectedGameRefCount')}`",
            f"- Label download executed: `{summary.get('labelDownloadExecuted')}`",
            f"- Full original video download executed: `{summary.get('fullOriginalVideoDownloadExecuted')}`",
            f"- Dataset download executed: `{summary.get('datasetDownloadExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_controlled_label_metadata_probe(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_controlled_label_metadata_surface_probe",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    listing_ready = _listing_ready(inputs["listingSummary"], inputs["listingAudit"])
    ball_surface = _ball_surface(inputs["listingAudit"])
    fetch_contract = _fetch_contract(ball_surface=ball_surface, access_contract=inputs["accessContract"])
    primary_blocker, next_lever, goal_achieved, english = _classify(
        listing_ready=listing_ready,
        ball_surface=ball_surface,
    )
    generated_at = utc_now_iso()
    attempts = _attempt_plan()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_controlled_label_metadata_probe",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_api_listing_probe",
        "apiListingProbeReady": listing_ready,
        "labelMetadataProbeReady": goal_achieved,
        "selectedTask": ball_surface.get("task") if goal_achieved else None,
        "selectedSplit": ball_surface.get("selectedSplit") if goal_achieved else None,
        "selectedGameRefCount": ball_surface.get("selectedGameRefCount") if goal_achieved else 0,
        "totalBallGameRefs": ball_surface.get("totalBallGameRefs"),
        "labelDownloadApprovedByPreviousContract": fetch_contract.get("labelDownloadApprovedByPreviousContract"),
        "labelDownloadApprovalRequired": True,
        "labelDownloadExecuted": False,
        "sampleDownloadExecuted": False,
        "datasetDownloadAllowedByThisBatch": False,
        "datasetDownloadExecuted": False,
        "fullOriginalVideoDownloadExecuted": False,
        "videoDownloadAllowed": False,
        "featureDownloadAllowed": False,
        "trainingAllowed": False,
        "trainingExecuted": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationAllowed": False,
        "runtimeDefaultMutationExecuted": False,
        "promotionMutationExecuted": False,
        "candidateEvaluationExecuted": False,
        "credentialPersisted": False,
        "passwordRedacted": True,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "generatedAt": generated_at,
        "decisions": [
            {"condition": "api_listing_probe_missing", "selected": primary_blocker == BLOCKER_LISTING_MISSING, "nextRecommendedNextLever": NEXT_LISTING_PROBE},
            {"condition": "ball_label_surface_missing", "selected": primary_blocker == BLOCKER_BALL_SURFACE_MISSING, "nextRecommendedNextLever": NEXT_LISTING_REPAIR},
            {"condition": "label_sample_fetch_approval_ready", "selected": goal_achieved, "nextRecommendedNextLever": NEXT_LABEL_SAMPLE_FETCH_APPROVAL},
        ],
    }
    batch_outcome = {
        "summary": summary,
        "soccernetBallLabelSurfaceAudit": ball_surface,
        "controlledLabelSampleFetchContract": fetch_contract,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }
    _write_json(output_root / "soccernet_controlled_label_metadata_probe_summary.json", summary)
    _write_json(output_root / "soccernet_ball_label_surface_audit.json", ball_surface)
    _write_json(output_root / "controlled_label_sample_fetch_contract.json", fetch_contract)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare a controlled SoccerNet label-metadata fetch contract without downloads.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_controlled_label_metadata_surface_probe")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccernet_controlled_label_metadata_probe(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
