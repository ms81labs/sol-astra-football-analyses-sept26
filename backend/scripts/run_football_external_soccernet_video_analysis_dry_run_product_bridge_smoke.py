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
DEFAULT_DRY_RUN_DIR_NAME = "football_external_soccernet_video_analysis_dry_run_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_video_analysis_dry_run_product_bridge_smoke_v1"

BLOCKER_DRY_RUN_MISSING = "football_external_soccernet_video_analysis_dry_run_missing"
BLOCKER_BRIDGE_GAP = "football_external_soccernet_video_analysis_dry_run_product_bridge_gap"

NEXT_DRY_RUN = "football_external_soccernet_video_analysis_dry_run"
NEXT_BRIDGE_REPAIR = "football_external_soccernet_video_analysis_dry_run_product_bridge_repair"
NEXT_BOUNDED_ANALYSIS_APPROVAL = "football_external_soccernet_bounded_analysis_execution_approval"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_dry_run_product_bridge_smoke",
            "successCriteria": [
                "load the bounded dry-run artifact manifest",
                "verify referenced sampled frames exist",
                "write a product-facing dry-run payload without full analysis readiness",
            ],
            "failureAdaptation": "If manifest fields are incomplete, repair only from dry-run truth.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_dry_run_product_bridge_manifest_repair",
            "successCriteria": [
                "repair sampled-frame paths or product payload fields from dry-run artifacts",
                "keep full analysis and runtime mutation blocked",
            ],
            "failureAdaptation": "If dry-run artifacts are missing, route back to dry run.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_dry_run_product_bridge_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before bounded analysis approval if product bridge smoke is unsafe",
            ],
            "failureAdaptation": "Route to dry-run rerun or product bridge repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str, dry_run_dir_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    dry_run_root = candidate_root / dry_run_dir_name
    return {
        "candidateRoot": candidate_root,
        "dryRunRoot": dry_run_root,
        "dryRunSummary": _load_json(dry_run_root / "video_analysis_dry_run_summary.json"),
        "artifactManifest": _load_json(dry_run_root / "dry_run_artifact_manifest.json"),
    }


def _dry_run_ready(summary: dict[str, Any] | None, manifest: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("analysisExecutionExecuted") is True
        and summary.get("fullAnalysisExecuted") is False
        and (summary.get("sampledFrameCount") or 0) > 0
        and summary.get("trainingExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(manifest, dict)
        and manifest.get("schemaVersion") == "soccernet_external_video_analysis_dry_run_manifest_v1"
        and manifest.get("fullAnalysisExecuted") is False
        and isinstance(manifest.get("sampledFrames"), list)
        and len(manifest.get("sampledFrames") or []) > 0
    )


def _frame_existence_audit(dry_run_root: Path, manifest: dict[str, Any] | None) -> dict[str, Any]:
    frames = manifest.get("sampledFrames") if isinstance(manifest, dict) else []
    rows: list[dict[str, Any]] = []
    missing = 0
    if not isinstance(frames, list):
        frames = []
    for row in frames:
        if not isinstance(row, dict):
            continue
        relative = row.get("relativePath")
        exists = bool(relative and (dry_run_root / str(relative)).exists())
        missing += 0 if exists else 1
        rows.append({**row, "exists": exists})
    return {
        "sampledFrameCount": len(rows),
        "missingSampledFrameCount": missing,
        "sampledFrames": rows,
        "allSampledFramesExist": missing == 0 and len(rows) > 0,
    }


def _product_payload(manifest: dict[str, Any] | None, frame_audit: dict[str, Any]) -> dict[str, Any]:
    manifest = manifest or {}
    return {
        "schemaVersion": "soccernet_external_video_dry_run_product_bridge_v1",
        "generatedAt": utc_now_iso(),
        "sourceBatch": "football_external_soccernet_video_analysis_dry_run",
        "selectedVideoPath": manifest.get("selectedVideoPath"),
        "frames": frame_audit.get("sampledFrames", []),
        "frameCount": frame_audit.get("sampledFrameCount", 0),
        "readiness": {
            "productBridgeSmokePassed": frame_audit.get("allSampledFramesExist") is True,
            "boundedDryRunFrameManifestReady": frame_audit.get("allSampledFramesExist") is True,
            "fullAnalysisReady": False,
            "trainingReady": False,
            "promotionReady": False,
            "candidateEvaluationReady": False,
            "runtimeDefaultMutationReady": False,
        },
        "limitations": [
            "bounded dry-run frame manifest only",
            "not a full match analysis",
            "not a detector evaluation",
            "not training evidence",
            "does not mutate runtime defaults",
        ],
    }


def _classify(dry_run_ready: bool, frame_audit: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not dry_run_ready:
        return (
            BLOCKER_DRY_RUN_MISSING,
            NEXT_DRY_RUN,
            False,
            "SoccerNet bounded dry-run artifacts are missing or unsafe; rerun the dry run before product bridge smoke.",
        )
    if frame_audit.get("allSampledFramesExist") is not True:
        return (
            BLOCKER_BRIDGE_GAP,
            NEXT_BRIDGE_REPAIR,
            False,
            "SoccerNet dry-run product bridge cannot verify all sampled frame artifacts.",
        )
    return (
        None,
        NEXT_BOUNDED_ANALYSIS_APPROVAL,
        True,
        "SoccerNet bounded dry-run product bridge smoke passed. A separate bounded analysis execution approval is required before more analysis.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "dry_run_missing", "selected": primary_blocker == BLOCKER_DRY_RUN_MISSING, "primaryBlocker": BLOCKER_DRY_RUN_MISSING, "nextRecommendedNextLever": NEXT_DRY_RUN},
            {"condition": "product_bridge_gap", "selected": primary_blocker == BLOCKER_BRIDGE_GAP, "primaryBlocker": BLOCKER_BRIDGE_GAP, "nextRecommendedNextLever": NEXT_BRIDGE_REPAIR},
            {"condition": "bounded_analysis_execution_approval_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_BOUNDED_ANALYSIS_APPROVAL},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Video Analysis Dry Run Product Bridge Smoke",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Product bridge smoke passed: `{summary.get('productBridgeSmokePassed')}`",
            f"- Product payload frame count: `{summary.get('productPayloadFrameCount')}`",
            f"- Full analysis ready: `{summary.get('fullAnalysisReady')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_video_analysis_dry_run_product_bridge_smoke(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    dry_run_dir_name: str = DEFAULT_DRY_RUN_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_dry_run_product_bridge_smoke",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name, dry_run_dir_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _dry_run_ready(inputs["dryRunSummary"], inputs["artifactManifest"])
    frame_audit = _frame_existence_audit(inputs["dryRunRoot"], inputs["artifactManifest"])
    payload = _product_payload(inputs["artifactManifest"], frame_audit)
    primary_blocker, next_lever, goal_achieved, english = _classify(ready, frame_audit)
    attempts = _attempt_plan()
    generated_at = utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_video_analysis_dry_run_product_bridge_smoke",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_video_analysis_dry_run",
        "productBridgeSmokePassed": goal_achieved,
        "productPayloadFrameCount": payload.get("frameCount"),
        "missingSampledFrameCount": frame_audit.get("missingSampledFrameCount"),
        "fullAnalysisReady": False,
        "fullAnalysisExecuted": False,
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
        "sampledFrameExistenceAudit": frame_audit,
        "dryRunProductBridgePayload": payload,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "dry_run_product_bridge_smoke_summary.json", summary)
    _write_json(output_root / "sampled_frame_existence_audit.json", frame_audit)
    _write_json(output_root / "dry_run_product_bridge_payload.json", payload)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--dry-run-dir-name", default=DEFAULT_DRY_RUN_DIR_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_dry_run_product_bridge_smoke")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_video_analysis_dry_run_product_bridge_smoke(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        dry_run_dir_name=args.dry_run_dir_name,
        output_dir_name=args.output_dir_name,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("goalAchieved") else 1


if __name__ == "__main__":
    raise SystemExit(main())
