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
DEFAULT_METADATA_DIR_NAME = "football_external_soccernet_controlled_label_metadata_probe_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_controlled_label_sample_fetch_approval_v1"

BLOCKER_METADATA_MISSING = "football_external_soccernet_label_metadata_probe_missing"
BLOCKER_SCOPE_UNSAFE = "football_external_soccernet_label_fetch_scope_unsafe"

NEXT_METADATA_PROBE = "football_external_soccernet_controlled_label_metadata_probe"
NEXT_LABEL_FETCH = "football_external_soccernet_controlled_label_sample_fetch"

SAFE_LABEL_FILES = {"Labels.json"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_label_sample_fetch_scope_approval",
            "successCriteria": [
                "approve exactly one SoccerNet spotting-ball game",
                "approve exactly one Labels.json file",
                "keep original-video, feature, bulk dataset, training, promotion, and runtime mutation disallowed",
            ],
            "failureAdaptation": "If scope is unsafe, return to metadata probe/contract repair.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_label_fetch_contract_repair",
            "successCriteria": [
                "repair game count, task, split, or file list to a single label-only fetch",
                "do not broaden scope to videos or bulk datasets",
            ],
            "failureAdaptation": "If contract remains unsafe, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_label_fetch_approval_blocker_summary",
            "successCriteria": [
                "select exactly one next corrective family",
                "do not download SoccerNet data",
            ],
            "failureAdaptation": "Stop before label fetch.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    metadata_root = candidate_root / DEFAULT_METADATA_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "metadataSummary": _load_json(metadata_root / "soccernet_controlled_label_metadata_probe_summary.json"),
        "fetchContract": _load_json(metadata_root / "controlled_label_sample_fetch_contract.json"),
    }


def _metadata_ready(metadata_summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(metadata_summary, dict)
        and metadata_summary.get("goalAchieved") is True
        and metadata_summary.get("labelMetadataProbeReady") is True
        and metadata_summary.get("labelDownloadExecuted") is False
        and metadata_summary.get("fullOriginalVideoDownloadExecuted") is False
        and metadata_summary.get("datasetDownloadExecuted") is False
    )


def _scope_safe(contract: dict[str, Any] | None) -> bool:
    if not isinstance(contract, dict):
        return False
    files = contract.get("files")
    games = contract.get("gameRefs")
    return bool(
        contract.get("task") == "spotting-ball"
        and contract.get("split") in {"train", "valid", "test", "challenge"}
        and isinstance(files, list)
        and set(str(row) for row in files) == SAFE_LABEL_FILES
        and isinstance(games, list)
        and len(games) == 1
        and int(contract.get("maxGameCount") or 0) == 1
        and contract.get("fetchScope") == "single_game_label_metadata_only"
        and contract.get("approvalRequiredBeforeDownload") is True
        and contract.get("fullOriginalVideoDownloadApproved") is False
        and contract.get("videoDownloadAllowed") is False
        and contract.get("featureDownloadAllowed") is False
        and contract.get("datasetBulkDownloadAllowed") is False
        and contract.get("trainingUseAllowed") is False
    )


def _approval_contract(contract: dict[str, Any] | None, approved: bool) -> dict[str, Any]:
    contract = contract or {}
    return {
        "contractName": "football_external_soccernet_controlled_label_sample_fetch_approval",
        "sourceBatch": "football_external_soccernet_controlled_label_metadata_probe",
        "labelSampleFetchApproved": approved,
        "resourceId": "soccernet_broadcast_tasks",
        "task": contract.get("task"),
        "split": contract.get("split"),
        "gameRefs": contract.get("gameRefs") if isinstance(contract.get("gameRefs"), list) else [],
        "files": contract.get("files") if isinstance(contract.get("files"), list) else [],
        "maxGameCount": int(contract.get("maxGameCount") or 0),
        "fetchScope": contract.get("fetchScope"),
        "credentialEnvVar": contract.get("credentialEnvVar") or "SOCCERNET_PASSWORD",
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
    metadata_ready: bool,
    scope_safe: bool,
) -> tuple[str | None, str, bool, str]:
    if not metadata_ready:
        return (
            BLOCKER_METADATA_MISSING,
            NEXT_METADATA_PROBE,
            False,
            "SoccerNet controlled label metadata probe truth is missing or not passed.",
        )
    if not scope_safe:
        return (
            BLOCKER_SCOPE_UNSAFE,
            NEXT_METADATA_PROBE,
            False,
            "SoccerNet label fetch scope is unsafe; only one Labels.json for one spotting-ball game can be approved.",
        )
    return (
        None,
        NEXT_LABEL_FETCH,
        True,
        "Single-game SoccerNet Labels.json fetch is approved. Proceed to controlled label sample fetch; original videos remain disallowed.",
    )


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Controlled Label Sample Fetch Approval",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Label sample fetch approved: `{summary.get('labelSampleFetchApproved')}`",
            f"- Approved task: `{summary.get('approvedTask')}`",
            f"- Approved split: `{summary.get('approvedSplit')}`",
            f"- Approved game refs: `{summary.get('approvedGameRefCount')}`",
            f"- Approved files: `{summary.get('approvedFiles')}`",
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


def run_football_external_soccernet_controlled_label_sample_fetch_approval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_label_sample_fetch_scope_approval",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    metadata_ready = _metadata_ready(inputs["metadataSummary"])
    scope_safe = _scope_safe(inputs["fetchContract"])
    primary_blocker, next_lever, goal_achieved, english = _classify(
        metadata_ready=metadata_ready,
        scope_safe=scope_safe,
    )
    generated_at = _utc_now_iso()
    attempts = _attempt_plan()
    approved_contract = _approval_contract(inputs["fetchContract"], goal_achieved)
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_controlled_label_sample_fetch_approval",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_controlled_label_metadata_probe",
        "labelSampleFetchApproved": goal_achieved,
        "approvedTask": approved_contract.get("task") if goal_achieved else None,
        "approvedSplit": approved_contract.get("split") if goal_achieved else None,
        "approvedGameRefCount": len(approved_contract.get("gameRefs") or []) if goal_achieved else 0,
        "approvedFiles": approved_contract.get("files") if goal_achieved else [],
        "credentialPersisted": False,
        "passwordRedacted": True,
        "labelDownloadExecuted": False,
        "sampleDownloadExecuted": False,
        "datasetDownloadAllowedByThisBatch": False,
        "datasetDownloadExecuted": False,
        "fullOriginalVideoDownloadApproved": False,
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
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "generatedAt": generated_at,
        "decisions": [
            {"condition": "label_metadata_probe_missing", "selected": primary_blocker == BLOCKER_METADATA_MISSING, "nextRecommendedNextLever": NEXT_METADATA_PROBE},
            {"condition": "label_fetch_scope_unsafe", "selected": primary_blocker == BLOCKER_SCOPE_UNSAFE, "nextRecommendedNextLever": NEXT_METADATA_PROBE},
            {"condition": "single_label_fetch_approved", "selected": goal_achieved, "nextRecommendedNextLever": NEXT_LABEL_FETCH},
        ],
    }
    batch_outcome = {
        "summary": summary,
        "labelSampleFetchApprovalContract": approved_contract,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }
    _write_json(output_root / "label_sample_fetch_approval_summary.json", summary)
    _write_json(output_root / "label_sample_fetch_approval_contract.json", approved_contract)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Approve a single-game SoccerNet Labels.json fetch.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_label_sample_fetch_scope_approval")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccernet_controlled_label_sample_fetch_approval(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
