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
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_video_member_extract_approval_v1"

BLOCKER_PROBE_MISSING = "football_external_soccernet_video_sample_probe_missing"
BLOCKER_CONTRACT_GAP = "football_external_soccernet_video_member_extract_contract_gap"

NEXT_SAMPLE_PROBE = "football_external_soccernet_video_sample_probe"
NEXT_CONTRACT_REPAIR = "football_external_soccernet_video_member_extract_contract_repair"
NEXT_MEMBER_EXTRACT = "football_external_soccernet_video_member_extract"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "scoped_video_member_extract_approval",
            "successCriteria": [
                "approve extraction of exactly one selected encrypted video member",
                "require runtime-only credential and forbid credential persistence",
                "do not execute extraction in approval batch",
            ],
            "failureAdaptation": "If the selected member contract is incomplete, repair from saved approval truth.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "video_member_extract_contract_repair",
            "successCriteria": [
                "repair member path and size fields from saved video sample approval contract",
                "preserve full archive download block",
            ],
            "failureAdaptation": "If sample probe is missing, route back to probe.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "video_member_extract_approval_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before extraction, training, promotion, or runtime mutation",
            ],
            "failureAdaptation": "Route to sample probe or contract repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    return {
        "candidateRoot": candidate_root,
        "probeSummary": _load_json(candidate_root / "football_external_soccernet_video_sample_probe_v1/video_sample_probe_summary.json"),
        "sampleApprovalContract": _load_json(candidate_root / "football_external_soccernet_video_sample_download_approval_v1/video_sample_download_approval_contract.json"),
    }


def _probe_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("sampleProbeCompleted") is True
        and summary.get("sampleIsEncryptedZipMember") is True
        and summary.get("sampleIsPlayableVideo") is False
        and summary.get("trainingExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
    )


def _extract_contract(sample_contract: dict[str, Any] | None) -> dict[str, Any]:
    sample_contract = sample_contract or {}
    return {
        "contractName": "football_external_soccernet_video_member_extract",
        "sourceBatch": "football_external_soccernet_video_member_extract_approval",
        "videoMemberExtractionApproved": bool(sample_contract.get("selectedVideoMemberPath")),
        "approvedVideoMemberPath": sample_contract.get("selectedVideoMemberPath"),
        "approvedCompressedSizeBytes": sample_contract.get("selectedCompressedSizeBytes"),
        "approvedUncompressedSizeBytes": sample_contract.get("selectedUncompressedSizeBytes"),
        "approvedLocalHeaderOffset": sample_contract.get("selectedLocalHeaderOffset"),
        "fullArchiveDownloadApproved": False,
        "videoMemberExtractionExecuted": False,
        "requiresRuntimeCredential": True,
        "credentialEnvVar": "SOCCERNET_PASSWORD",
        "credentialPersistenceAllowed": False,
        "trainingUseAllowed": False,
        "promotionUseAllowed": False,
        "runtimeDefaultMutationAllowed": False,
    }


def _classify(probe_ready: bool, contract: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not probe_ready:
        return (
            BLOCKER_PROBE_MISSING,
            NEXT_SAMPLE_PROBE,
            False,
            "SoccerNet video sample probe is missing or unsafe; rerun probe before member extraction approval.",
        )
    if contract.get("videoMemberExtractionApproved") is not True or not contract.get("approvedVideoMemberPath"):
        return (
            BLOCKER_CONTRACT_GAP,
            NEXT_CONTRACT_REPAIR,
            False,
            "Scoped SoccerNet video member extraction contract is incomplete.",
        )
    return (
        None,
        NEXT_MEMBER_EXTRACT,
        True,
        "Scoped encrypted SoccerNet video member extraction is approved. Extraction still requires runtime-only credential and remains non-training/non-promotion.",
    )


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "video_sample_probe_missing", "selected": primary_blocker == BLOCKER_PROBE_MISSING, "primaryBlocker": BLOCKER_PROBE_MISSING, "nextRecommendedNextLever": NEXT_SAMPLE_PROBE},
            {"condition": "video_member_extract_contract_gap", "selected": primary_blocker == BLOCKER_CONTRACT_GAP, "primaryBlocker": BLOCKER_CONTRACT_GAP, "nextRecommendedNextLever": NEXT_CONTRACT_REPAIR},
            {"condition": "video_member_extract_approved", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_MEMBER_EXTRACT},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Video Member Extract Approval",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Video member extraction approved: `{summary.get('videoMemberExtractionApproved')}`",
            f"- Approved member: `{summary.get('approvedVideoMemberPath')}`",
            f"- Extraction executed: `{summary.get('videoMemberExtractionExecuted')}`",
            f"- Full archive approved: `{summary.get('fullArchiveDownloadApproved')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_video_member_extract_approval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "scoped_video_member_extract_approval",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _probe_ready(inputs["probeSummary"])
    contract = _extract_contract(inputs["sampleApprovalContract"])
    primary_blocker, next_lever, goal_achieved, english = _classify(ready, contract)
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_video_member_extract_approval",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_video_sample_probe",
        "videoMemberExtractionApproved": goal_achieved,
        "approvedVideoMemberPath": contract["approvedVideoMemberPath"],
        "approvedCompressedSizeBytes": contract["approvedCompressedSizeBytes"],
        "approvedUncompressedSizeBytes": contract["approvedUncompressedSizeBytes"],
        "fullArchiveDownloadApproved": False,
        "archiveDownloadExecuted": False,
        "videoMemberExtractionExecuted": False,
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
    batch_outcome = {
        "summary": summary,
        "videoMemberExtractApprovalContract": contract,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "video_member_extract_approval_summary.json", summary)
    _write_json(output_root / "video_member_extract_approval_contract.json", contract)
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
    parser.add_argument("--attempt-approach-family", default="scoped_video_member_extract_approval")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_video_member_extract_approval(
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
