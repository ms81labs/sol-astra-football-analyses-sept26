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
DEFAULT_BRIDGE_DIR_NAME = "football_external_soccernet_video_to_analysis_bridge_prep_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_video_analysis_dry_run_approval_v1"

BLOCKER_BRIDGE_MISSING = "football_external_soccernet_video_to_analysis_bridge_missing"
BLOCKER_SCOPE_GAP = "football_external_soccernet_video_analysis_dry_run_scope_gap"

NEXT_BRIDGE_PREP = "football_external_soccernet_video_to_analysis_bridge_prep"
NEXT_SCOPE_REPAIR = "football_external_soccernet_video_analysis_dry_run_scope_repair"
NEXT_DRY_RUN = "football_external_soccernet_video_analysis_dry_run"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_video_analysis_dry_run_approval",
            "successCriteria": [
                "approve only a bounded dry run on the extracted SoccerNet 224p video",
                "write explicit frame, stage, and no-mutation limits",
                "do not execute analysis in the approval batch",
            ],
            "failureAdaptation": "If the bridge is ready but scope is incomplete, repair the dry-run scope contract.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_video_analysis_dry_run_scope_repair",
            "successCriteria": [
                "repair bounded-frame, selected-video, and allowed-stage fields from bridge truth",
                "keep analysisExecutionExecuted false",
            ],
            "failureAdaptation": "If bridge truth is missing, route back to bridge prep.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_video_analysis_dry_run_approval_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before analysis if the bounded dry-run contract is unsafe",
            ],
            "failureAdaptation": "Route to bridge prep or dry-run scope repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str, bridge_dir_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    bridge_root = candidate_root / bridge_dir_name
    return {
        "candidateRoot": candidate_root,
        "bridgeSummary": _load_json(bridge_root / "video_to_analysis_bridge_prep_summary.json"),
        "bridgeContract": _load_json(bridge_root / "analysis_bridge_contract.json"),
        "ingestionManifest": _load_json(bridge_root / "external_video_ingestion_manifest.json"),
    }


def _bridge_ready(
    summary: dict[str, Any] | None,
    contract: dict[str, Any] | None,
    manifest: dict[str, Any] | None,
) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("analysisBridgePrepReady") is True
        and summary.get("analysisExecutionApproved") is False
        and summary.get("analysisExecutionExecuted") is False
        and summary.get("videoExists") is True
        and (summary.get("sampledFrameCount") or 0) > 0
        and summary.get("trainingExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(contract, dict)
        and contract.get("analysisBridgePrepReady") is True
        and contract.get("analysisExecutionApproved") is False
        and contract.get("analysisExecutionExecuted") is False
        and contract.get("runtimeDefaultMutationAllowed") is False
        and isinstance(manifest, dict)
        and manifest.get("safeForDryRunApproval") is True
        and manifest.get("analysisExecutionApproved") is False
        and manifest.get("analysisExecutionExecuted") is False
        and manifest.get("video", {}).get("exists") is True
    )


def _dry_run_scope(manifest: dict[str, Any] | None) -> dict[str, Any]:
    manifest = manifest or {}
    video = manifest.get("video") if isinstance(manifest.get("video"), dict) else {}
    frame_count = int(video.get("frameCount") or 0)
    max_frames = 300
    sample_every_n_frames = max(1, frame_count // max_frames) if frame_count else 1
    return {
        "schemaVersion": "soccernet_external_video_analysis_dry_run_scope_v1",
        "generatedAt": utc_now_iso(),
        "selectedVideoPath": video.get("path"),
        "videoExists": video.get("exists") is True,
        "videoWidth": video.get("width"),
        "videoHeight": video.get("height"),
        "videoFps": video.get("fps"),
        "sourceFrameCount": frame_count,
        "maxDryRunFrames": max_frames,
        "sampleEveryNFrames": sample_every_n_frames,
        "estimatedSampledFrameCount": min(max_frames, frame_count) if frame_count else 0,
        "boundedDryRunOnly": True,
        "fullAnalysisAllowed": False,
        "allowedStages": [
            "video_open",
            "bounded_frame_sampling",
            "external_video_product_path_ingestion_smoke",
            "dry_run_artifact_manifest",
        ],
        "disallowedStages": [
            "training",
            "promotion",
            "runtime_default_mutation",
            "candidate_evaluation_readiness",
            "full_match_analysis",
            "full_archive_download",
            "video_720p_member_download",
        ],
        "analysisExecutionApproved": True,
        "analysisExecutionExecuted": False,
        "dryRunExecutionApprovalScope": "next_batch_only",
    }


def _dry_run_contract(scope: dict[str, Any]) -> dict[str, Any]:
    return {
        "contractName": "football_external_soccernet_video_analysis_dry_run",
        "sourceBatch": "football_external_soccernet_video_analysis_dry_run_approval",
        "selectedVideoPath": scope.get("selectedVideoPath"),
        "videoExists": scope.get("videoExists") is True,
        "maxDryRunFrames": scope.get("maxDryRunFrames"),
        "sampleEveryNFrames": scope.get("sampleEveryNFrames"),
        "allowedStages": scope.get("allowedStages"),
        "boundedDryRunOnly": True,
        "fullAnalysisAllowed": False,
        "analysisDryRunApproved": True,
        "analysisExecutionApproved": True,
        "analysisExecutionExecuted": False,
        "trainingUseAllowed": False,
        "promotionUseAllowed": False,
        "candidateEvaluationUseAllowed": False,
        "runtimeDefaultMutationAllowed": False,
        "requiresSeparateFullAnalysisApproval": True,
    }


def _classify(bridge_ready: bool, contract: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not bridge_ready:
        return (
            BLOCKER_BRIDGE_MISSING,
            NEXT_BRIDGE_PREP,
            False,
            "SoccerNet video-to-analysis bridge prep is missing or unsafe; rerun bridge prep before dry-run approval.",
        )
    if (
        contract.get("analysisDryRunApproved") is not True
        or contract.get("analysisExecutionApproved") is not True
        or contract.get("analysisExecutionExecuted") is not False
        or contract.get("boundedDryRunOnly") is not True
        or contract.get("fullAnalysisAllowed") is not False
        or not contract.get("selectedVideoPath")
    ):
        return (
            BLOCKER_SCOPE_GAP,
            NEXT_SCOPE_REPAIR,
            False,
            "SoccerNet dry-run approval scope is incomplete or unsafe; repair scope before execution.",
        )
    return (
        None,
        NEXT_DRY_RUN,
        True,
        "Bounded SoccerNet video analysis dry run is approved for the next batch only. No analysis executed in this approval batch.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "video_to_analysis_bridge_missing", "selected": primary_blocker == BLOCKER_BRIDGE_MISSING, "primaryBlocker": BLOCKER_BRIDGE_MISSING, "nextRecommendedNextLever": NEXT_BRIDGE_PREP},
            {"condition": "video_analysis_dry_run_scope_gap", "selected": primary_blocker == BLOCKER_SCOPE_GAP, "primaryBlocker": BLOCKER_SCOPE_GAP, "nextRecommendedNextLever": NEXT_SCOPE_REPAIR},
            {"condition": "video_analysis_dry_run_approved", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_DRY_RUN},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Video Analysis Dry Run Approval",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Dry run approved: `{summary.get('analysisDryRunApproved')}`",
            f"- Analysis execution approved: `{summary.get('analysisExecutionApproved')}`",
            f"- Analysis execution executed: `{summary.get('analysisExecutionExecuted')}`",
            f"- Max dry-run frames: `{summary.get('maxDryRunFrames')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_video_analysis_dry_run_approval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    bridge_dir_name: str = DEFAULT_BRIDGE_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_video_analysis_dry_run_approval",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name, bridge_dir_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _bridge_ready(inputs["bridgeSummary"], inputs["bridgeContract"], inputs["ingestionManifest"])
    scope = _dry_run_scope(inputs["ingestionManifest"])
    contract = _dry_run_contract(scope)
    primary_blocker, next_lever, goal_achieved, english = _classify(ready, contract)
    if not goal_achieved:
        contract["analysisDryRunApproved"] = False
        contract["analysisExecutionApproved"] = False
        scope["analysisExecutionApproved"] = False
    attempts = _attempt_plan()
    generated_at = utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_video_analysis_dry_run_approval",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_video_to_analysis_bridge_prep",
        "analysisDryRunApproved": goal_achieved,
        "analysisExecutionApproved": goal_achieved,
        "analysisExecutionExecuted": False,
        "selectedVideoPath": scope.get("selectedVideoPath"),
        "videoExists": scope.get("videoExists"),
        "maxDryRunFrames": scope.get("maxDryRunFrames"),
        "sampleEveryNFrames": scope.get("sampleEveryNFrames"),
        "estimatedSampledFrameCount": scope.get("estimatedSampledFrameCount"),
        "boundedDryRunOnly": True,
        "fullAnalysisAllowed": False,
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
    decision_matrix = _decision_matrix(primary_blocker, goal_achieved)
    batch_outcome = {
        "summary": summary,
        "videoAnalysisDryRunContract": contract,
        "dryRunScopeAudit": scope,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "video_analysis_dry_run_approval_summary.json", summary)
    _write_json(output_root / "video_analysis_dry_run_contract.json", contract)
    _write_json(output_root / "dry_run_scope_audit.json", scope)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--bridge-dir-name", default=DEFAULT_BRIDGE_DIR_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_video_analysis_dry_run_approval")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_video_analysis_dry_run_approval(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        bridge_dir_name=args.bridge_dir_name,
        output_dir_name=args.output_dir_name,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("goalAchieved") else 1


if __name__ == "__main__":
    raise SystemExit(main())
