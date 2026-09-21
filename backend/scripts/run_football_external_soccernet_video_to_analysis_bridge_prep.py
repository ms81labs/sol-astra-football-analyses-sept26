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
DEFAULT_PRODUCT_DIR_NAME = "football_external_soccernet_video_product_path_smoke_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_video_to_analysis_bridge_prep_v1"

BLOCKER_PRODUCT_PATH_MISSING = "football_external_soccernet_video_product_path_missing"
BLOCKER_BRIDGE_CONTRACT_GAP = "football_external_soccernet_video_to_analysis_bridge_contract_gap"

NEXT_PRODUCT_PATH_SMOKE = "football_external_soccernet_video_product_path_smoke"
NEXT_BRIDGE_REPAIR = "football_external_soccernet_video_to_analysis_bridge_contract_repair"
NEXT_DRY_RUN_APPROVAL = "football_external_soccernet_video_analysis_dry_run_approval"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_video_to_analysis_bridge_contract",
            "successCriteria": [
                "create a contract for staging the external SoccerNet video into the analysis pipeline",
                "do not execute analysis or mutate runtime defaults",
                "carry explicit full-analysis limitations",
            ],
            "failureAdaptation": "If bridge fields are incomplete, repair from product bundle truth.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_video_to_analysis_bridge_contract_repair",
            "successCriteria": [
                "repair video path, sample frame, and readiness fields from saved product bundle",
                "keep analysis execution approval false",
            ],
            "failureAdaptation": "If product path smoke is missing, route back to product path smoke.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_video_to_analysis_bridge_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before analysis dry run if bridge contract is unsafe",
            ],
            "failureAdaptation": "Route to product path smoke or bridge contract repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    product_root = candidate_root / DEFAULT_PRODUCT_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "productSummary": _load_json(product_root / "video_product_path_smoke_summary.json"),
        "productBundle": _load_json(product_root / "external_video_product_bundle.json"),
    }


def _product_ready(summary: dict[str, Any] | None, bundle: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("externalVideoProductPathReady") is True
        and summary.get("fullAnalysisReady") is False
        and summary.get("trainingExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(bundle, dict)
        and bundle.get("readiness", {}).get("externalVideoProductPathReady") is True
        and bundle.get("readiness", {}).get("fullAnalysisReady") is False
    )


def _ingestion_manifest(bundle: dict[str, Any] | None) -> dict[str, Any]:
    bundle = bundle or {}
    video = bundle.get("video") if isinstance(bundle.get("video"), dict) else {}
    sampled = bundle.get("sampledFrames") if isinstance(bundle.get("sampledFrames"), list) else []
    return {
        "schemaVersion": "soccernet_external_video_ingestion_manifest_v1",
        "generatedAt": utc_now_iso(),
        "sourceBundleSchemaVersion": bundle.get("schemaVersion"),
        "video": video,
        "sampledFrames": sampled,
        "sampledFrameCount": len(sampled),
        "pipelineInputMode": "external_video_path",
        "analysisExecutionApproved": False,
        "analysisExecutionExecuted": False,
        "expectedManualHomographyRequired": True,
        "safeForDryRunApproval": bool(video.get("exists")) and len(sampled) > 0,
        "limitations": [
            "bridge prep only",
            "does not run analysis",
            "does not produce ball localization truth",
            "does not train",
            "does not promote",
            "does not mutate runtime defaults",
        ],
    }


def _bridge_contract(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "contractName": "football_external_soccernet_video_analysis_dry_run_approval",
        "sourceBatch": "football_external_soccernet_video_to_analysis_bridge_prep",
        "videoPath": manifest.get("video", {}).get("path"),
        "videoExists": manifest.get("video", {}).get("exists") is True,
        "sampledFrameCount": manifest.get("sampledFrameCount"),
        "analysisBridgePrepReady": manifest.get("safeForDryRunApproval") is True,
        "analysisExecutionApproved": False,
        "analysisExecutionExecuted": False,
        "trainingUseAllowed": False,
        "promotionUseAllowed": False,
        "candidateEvaluationUseAllowed": False,
        "runtimeDefaultMutationAllowed": False,
        "requiresSeparateDryRunApproval": True,
    }


def _classify(product_ready: bool, contract: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not product_ready:
        return (
            BLOCKER_PRODUCT_PATH_MISSING,
            NEXT_PRODUCT_PATH_SMOKE,
            False,
            "SoccerNet video product path smoke is missing or unsafe; rerun it before bridge prep.",
        )
    if contract.get("analysisBridgePrepReady") is not True or contract.get("analysisExecutionApproved") is not False:
        return (
            BLOCKER_BRIDGE_CONTRACT_GAP,
            NEXT_BRIDGE_REPAIR,
            False,
            "SoccerNet video-to-analysis bridge contract is incomplete or over-approves execution.",
        )
    return (
        None,
        NEXT_DRY_RUN_APPROVAL,
        True,
        "SoccerNet video-to-analysis bridge prep is ready. A separate dry-run approval is required before running analysis.",
    )


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "video_product_path_missing", "selected": primary_blocker == BLOCKER_PRODUCT_PATH_MISSING, "primaryBlocker": BLOCKER_PRODUCT_PATH_MISSING, "nextRecommendedNextLever": NEXT_PRODUCT_PATH_SMOKE},
            {"condition": "video_to_analysis_bridge_contract_gap", "selected": primary_blocker == BLOCKER_BRIDGE_CONTRACT_GAP, "primaryBlocker": BLOCKER_BRIDGE_CONTRACT_GAP, "nextRecommendedNextLever": NEXT_BRIDGE_REPAIR},
            {"condition": "video_analysis_dry_run_approval_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_DRY_RUN_APPROVAL},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Video To Analysis Bridge Prep",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Bridge prep ready: `{summary.get('analysisBridgePrepReady')}`",
            f"- Analysis execution approved: `{summary.get('analysisExecutionApproved')}`",
            f"- Video exists: `{summary.get('videoExists')}`",
            f"- Sampled frames: `{summary.get('sampledFrameCount')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_video_to_analysis_bridge_prep(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_video_to_analysis_bridge_contract",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _product_ready(inputs["productSummary"], inputs["productBundle"])
    manifest = _ingestion_manifest(inputs["productBundle"])
    contract = _bridge_contract(manifest)
    primary_blocker, next_lever, goal_achieved, english = _classify(ready, contract)
    attempts = _attempt_plan()
    generated_at = utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_video_to_analysis_bridge_prep",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_video_product_path_smoke",
        "analysisBridgePrepReady": goal_achieved,
        "analysisExecutionApproved": False,
        "analysisExecutionExecuted": False,
        "videoExists": contract.get("videoExists"),
        "sampledFrameCount": contract.get("sampledFrameCount"),
        "archiveDownloadExecuted": False,
        "video720pMemberDownloadExecuted": False,
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
        "externalVideoIngestionManifest": manifest,
        "analysisBridgeContract": contract,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "video_to_analysis_bridge_prep_summary.json", summary)
    _write_json(output_root / "external_video_ingestion_manifest.json", manifest)
    _write_json(output_root / "analysis_bridge_contract.json", contract)
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
    parser.add_argument("--attempt-approach-family", default="soccernet_video_to_analysis_bridge_contract")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_video_to_analysis_bridge_prep(
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
