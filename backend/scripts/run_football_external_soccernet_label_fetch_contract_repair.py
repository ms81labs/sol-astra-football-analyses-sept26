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
DEFAULT_FETCH_DIR_NAME = "football_external_soccernet_controlled_label_sample_fetch_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_label_fetch_contract_repair_v1"

BLOCKER_FAILURE_MISSING = "football_external_soccernet_label_fetch_failure_missing"

NEXT_LABEL_FETCH = "football_external_soccernet_controlled_label_sample_fetch"
NEXT_SPLIT_ARCHIVE_REVIEW = "football_external_soccernet_split_archive_access_review"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_label_fetch_failure_root_cause",
            "successCriteria": [
                "diagnose failed per-game Labels.json fetch",
                "preserve no-video/no-dataset/no-training guardrails",
            ],
            "failureAdaptation": "If failure evidence is missing, return to controlled label fetch.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_split_archive_contract_plan",
            "successCriteria": [
                "identify a safer package-supported SoccerNet ball-label access surface",
                "require separate approval before any split archive download",
            ],
            "failureAdaptation": "If archive access remains ambiguous, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_label_fetch_contract_blocker_summary",
            "successCriteria": [
                "select exactly one next corrective family",
                "do not download more SoccerNet data",
            ],
            "failureAdaptation": "Stop before broadening access.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    fetch_root = candidate_root / DEFAULT_FETCH_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "fetchSummary": _load_json(fetch_root / "controlled_label_fetch_summary.json"),
        "fetchProvenance": _load_json(fetch_root / "label_fetch_provenance_audit.json"),
    }


def _failure_ready(fetch_summary: dict[str, Any] | None, fetch_provenance: dict[str, Any] | None) -> bool:
    failures = (fetch_provenance or {}).get("failures")
    return bool(
        isinstance(fetch_summary, dict)
        and fetch_summary.get("goalAchieved") is False
        and fetch_summary.get("primaryBlocker") == "football_external_soccernet_label_fetch_failed"
        and fetch_summary.get("labelDownloadExecuted") is False
        and fetch_summary.get("fullOriginalVideoDownloadExecuted") is False
        and fetch_summary.get("datasetDownloadExecuted") is False
        and isinstance(fetch_provenance, dict)
        and isinstance(failures, list)
        and failures
    )


def _diagnosis(fetch_provenance: dict[str, Any] | None) -> dict[str, Any]:
    failures = (fetch_provenance or {}).get("failures")
    if not isinstance(failures, list):
        failures = []
    joined = "\n".join(str(row.get("stdoutTail") or "") + "\n" + str(row.get("stderrTail") or "") for row in failures if isinstance(row, dict))
    return {
        "failedFetchRootCause": "soccernet_spotting_ball_per_game_labels_json_not_served",
        "http404Observed": "404" in joined or "Not Found" in joined,
        "perGameLabelsJsonSupported": False,
        "failedFile": "Labels.json",
        "failedGameRefs": [row.get("gameRef") for row in failures if isinstance(row, dict) and row.get("gameRef")],
        "evidenceSummary": "SoccerNet package-local spotting-ball game refs are list metadata, but the generic per-game downloadGame Labels.json path returned HTTP 404.",
    }


def _repair_contract_plan() -> dict[str, Any]:
    return {
        "contractName": "football_external_soccernet_repaired_ball_label_access_plan",
        "sourceBatch": "football_external_soccernet_label_fetch_contract_repair",
        "recommendedAccessSurface": "spotting_ball_split_archive",
        "perGameLabelsJsonSupported": False,
        "candidatePackageTasks": [
            "spotting-ball-2023",
            "spotting-ball-2024",
            "spotting-ball-2025",
        ],
        "candidateFilesOrSplits": [
            "valid.zip",
            "train.zip",
            "test.zip",
            "challenge.zip",
        ],
        "approvalRequiredBeforeDownload": True,
        "inspectionRequiredBeforeTrainingUse": True,
        "fullOriginalVideoDownloadApproved": False,
        "videoDownloadAllowed": False,
        "trainingUseAllowed": False,
        "nextProbeGoal": "review archive contents and size/licensing before fetching any split archive",
    }


def _classify(failure_ready: bool) -> tuple[str | None, str, bool, str]:
    if not failure_ready:
        return (
            BLOCKER_FAILURE_MISSING,
            NEXT_LABEL_FETCH,
            False,
            "SoccerNet label fetch failure truth is missing; rerun the controlled label fetch before repair.",
        )
    return (
        None,
        NEXT_SPLIT_ARCHIVE_REVIEW,
        True,
        "Per-game Labels.json path is not served for the selected SoccerNet spotting-ball ref. Review package-supported split archive access before any broader download.",
    )


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Label Fetch Contract Repair",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Failed fetch root cause: `{summary.get('failedFetchRootCause')}`",
            f"- Per-game Labels.json supported: `{summary.get('perGameLabelsJsonSupported')}`",
            f"- Label download executed: `{summary.get('labelDownloadExecuted')}`",
            f"- Dataset download executed: `{summary.get('datasetDownloadExecuted')}`",
            f"- Full original video download executed: `{summary.get('fullOriginalVideoDownloadExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_label_fetch_contract_repair(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_label_fetch_failure_root_cause",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    failure_ready = _failure_ready(inputs["fetchSummary"], inputs["fetchProvenance"])
    diagnosis = _diagnosis(inputs["fetchProvenance"])
    repair_contract = _repair_contract_plan()
    primary_blocker, next_lever, goal_achieved, english = _classify(failure_ready)
    generated_at = utc_now_iso()
    attempts = _attempt_plan()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_label_fetch_contract_repair",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_controlled_label_sample_fetch",
        "failedFetchRootCause": diagnosis["failedFetchRootCause"] if goal_achieved else None,
        "perGameLabelsJsonSupported": False,
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
            {"condition": "label_fetch_failure_missing", "selected": primary_blocker == BLOCKER_FAILURE_MISSING, "nextRecommendedNextLever": NEXT_LABEL_FETCH},
            {"condition": "split_archive_access_review_ready", "selected": goal_achieved, "nextRecommendedNextLever": NEXT_SPLIT_ARCHIVE_REVIEW},
        ],
    }
    batch_outcome = {
        "summary": summary,
        "labelFetchFailureDiagnosis": diagnosis,
        "repairedAccessContractPlan": repair_contract,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }
    _write_json(output_root / "label_fetch_contract_repair_summary.json", summary)
    _write_json(output_root / "label_fetch_failure_diagnosis.json", diagnosis)
    _write_json(output_root / "repaired_access_contract_plan.json", repair_contract)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Diagnose and repair SoccerNet label fetch contract after failed per-game Labels.json fetch.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_label_fetch_failure_root_cause")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccernet_label_fetch_contract_repair(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
