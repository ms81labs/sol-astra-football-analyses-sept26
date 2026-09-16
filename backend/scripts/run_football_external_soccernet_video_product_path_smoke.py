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
DEFAULT_FRAME_PROBE_DIR_NAME = "football_external_soccernet_video_frame_probe_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_video_product_path_smoke_v1"

BLOCKER_FRAME_PROBE_MISSING = "football_external_soccernet_video_frame_probe_missing"
BLOCKER_PRODUCT_BUNDLE_GAP = "football_external_soccernet_video_product_bundle_gap"

NEXT_FRAME_PROBE = "football_external_soccernet_video_frame_probe"
NEXT_BUNDLE_REPAIR = "football_external_soccernet_video_product_bundle_repair"
NEXT_BRIDGE_PREP = "football_external_soccernet_video_to_analysis_bridge_prep"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_video_product_path_smoke",
            "successCriteria": [
                "build a product-facing external video bundle from extracted video and sampled frames",
                "preserve explicit not-full-analysis limitations",
                "do not train, promote, evaluate candidates, or mutate runtime defaults",
            ],
            "failureAdaptation": "If bundle fields are incomplete, repair from saved frame-probe truth.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_video_product_bundle_repair",
            "successCriteria": [
                "repair video/frame paths and readiness flags from saved artifacts",
                "keep full analysis readiness false",
            ],
            "failureAdaptation": "If frame probe is missing, route back to frame probe.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_video_product_path_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before video-to-analysis bridge prep if product path is unsafe",
            ],
            "failureAdaptation": "Route to frame probe or bundle repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    frame_root = candidate_root / DEFAULT_FRAME_PROBE_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "frameRoot": frame_root,
        "frameSummary": _load_json(frame_root / "video_frame_probe_summary.json"),
        "frameAudit": _load_json(frame_root / "video_frame_probe_audit.json"),
    }


def _frame_probe_ready(summary: dict[str, Any] | None, audit: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("videoFrameProbePassed") is True
        and summary.get("videoOpenable") is True
        and int(summary.get("sampledFrameCount") or 0) > 0
        and summary.get("trainingExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(audit, dict)
        and audit.get("videoOpenable") is True
    )


def _bundle(frame_root: Path, summary: dict[str, Any] | None, audit: dict[str, Any] | None) -> dict[str, Any]:
    audit = audit or {}
    video_path = Path(str(audit.get("videoPath") or ""))
    sampled_frames = []
    for row in audit.get("sampledFrames") or []:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("relativePath") or "")
        path = frame_root / rel
        sampled_frames.append(
            {
                "frameIndex": row.get("frameIndex"),
                "path": str(path),
                "exists": path.exists(),
                "width": row.get("width"),
                "height": row.get("height"),
            }
        )
    return {
        "schemaVersion": "soccernet_external_video_product_bundle_v1",
        "generatedAt": _utc_now_iso(),
        "sourceBatch": "football_external_soccernet_video_frame_probe",
        "video": {
            "path": str(video_path),
            "exists": video_path.exists(),
            "width": summary.get("width") if isinstance(summary, dict) else audit.get("width"),
            "height": summary.get("height") if isinstance(summary, dict) else audit.get("height"),
            "fps": summary.get("fps") if isinstance(summary, dict) else audit.get("fps"),
            "frameCount": summary.get("frameCount") if isinstance(summary, dict) else audit.get("frameCount"),
        },
        "sampledFrames": sampled_frames,
        "readiness": {
            "externalVideoProductPathReady": video_path.exists() and any(row["exists"] for row in sampled_frames),
            "frameSamplingReady": any(row["exists"] for row in sampled_frames),
            "fullAnalysisReady": False,
            "trainingReady": False,
            "promotionReady": False,
            "candidateEvaluationReady": False,
            "runtimeDefaultMutationReady": False,
        },
        "limitations": [
            "external sample video only",
            "not full tactical analysis",
            "not ball localization ground truth",
            "not training truth",
            "not promotion truth",
        ],
    }


def _classify(frame_ready: bool, bundle: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not frame_ready:
        return (
            BLOCKER_FRAME_PROBE_MISSING,
            NEXT_FRAME_PROBE,
            False,
            "SoccerNet video frame probe is missing or unsafe; rerun frame probe before product path smoke.",
        )
    if bundle.get("readiness", {}).get("externalVideoProductPathReady") is not True:
        return (
            BLOCKER_PRODUCT_BUNDLE_GAP,
            NEXT_BUNDLE_REPAIR,
            False,
            "SoccerNet external video product bundle is incomplete.",
        )
    return (
        None,
        NEXT_BRIDGE_PREP,
        True,
        "SoccerNet external video product path smoke passed. Advance to video-to-analysis bridge prep without training or promotion.",
    )


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "video_frame_probe_missing", "selected": primary_blocker == BLOCKER_FRAME_PROBE_MISSING, "primaryBlocker": BLOCKER_FRAME_PROBE_MISSING, "nextRecommendedNextLever": NEXT_FRAME_PROBE},
            {"condition": "video_product_bundle_gap", "selected": primary_blocker == BLOCKER_PRODUCT_BUNDLE_GAP, "primaryBlocker": BLOCKER_PRODUCT_BUNDLE_GAP, "nextRecommendedNextLever": NEXT_BUNDLE_REPAIR},
            {"condition": "video_to_analysis_bridge_prep_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_BRIDGE_PREP},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Video Product Path Smoke",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- External video product path ready: `{summary.get('externalVideoProductPathReady')}`",
            f"- Frame count: `{summary.get('frameCount')}`",
            f"- Sampled frames: `{summary.get('sampledFrameCount')}`",
            f"- Full analysis ready: `{summary.get('fullAnalysisReady')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_video_product_path_smoke(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_video_product_path_smoke",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _frame_probe_ready(inputs["frameSummary"], inputs["frameAudit"])
    bundle = _bundle(inputs["frameRoot"], inputs["frameSummary"], inputs["frameAudit"])
    primary_blocker, next_lever, goal_achieved, english = _classify(ready, bundle)
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_video_product_path_smoke",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_video_frame_probe",
        "externalVideoProductPathReady": goal_achieved,
        "frameCount": bundle["video"]["frameCount"],
        "fps": bundle["video"]["fps"],
        "width": bundle["video"]["width"],
        "height": bundle["video"]["height"],
        "sampledFrameCount": len(bundle["sampledFrames"]),
        "fullAnalysisReady": False,
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
        "externalVideoProductBundle": bundle,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "video_product_path_smoke_summary.json", summary)
    _write_json(output_root / "external_video_product_bundle.json", bundle)
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
    parser.add_argument("--attempt-approach-family", default="soccernet_video_product_path_smoke")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_video_product_path_smoke(
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
