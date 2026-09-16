from __future__ import annotations

# ruff: noqa: E402

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v6"
DEFAULT_SUITE_NAME = "frozen-viable-baseline-slice-suite"
PROMOTION_BATCH_NAME = "touchline_detector_candidate_promotion_validation_v1"
NEXT_LEVER = "promote_touchline_detector_candidate"
DEFAULT_RUNTIME_CHANGE_BLOCKERS = ["failing_source_not_viable"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_markdown(path: Path, payload: dict[str, object]) -> None:
    blockers = list(payload.get("promotionValidationBlockers") or [])
    runtime_blockers = list(payload.get("runtimeDefaultChangeBlockers") or [])
    lines = [
        "# Batch Outcome Analysis",
        "",
        f"- Batch goal: {payload.get('batchGoal')}",
        f"- Goal achieved: {bool(payload.get('goalAchieved'))}",
        f"- Roadmap advance allowed: {bool(payload.get('roadmapAdvanceAllowed'))}",
        f"- Promotion validated: {bool(payload.get('promotionValidated'))}",
        f"- Promoted for controlled runs: {bool(payload.get('promotedForControlledRuns'))}",
        f"- Runtime default changed: {bool(payload.get('runtimeDefaultChanged'))}",
        f"- Runtime default change allowed: {bool(payload.get('runtimeDefaultChangeAllowed'))}",
        f"- Next recommended next lever: {payload.get('nextRecommendedNextLever')}",
        "",
        "## English Summary",
        "",
        str(payload.get("englishSummary") or ""),
        "",
        "## English Decision",
        "",
        str(payload.get("englishDecision") or ""),
    ]
    if blockers:
        lines.extend(["", "## Promotion Validation Blockers", ""])
        lines.extend([f"- {blocker}" for blocker in blockers])
    if runtime_blockers:
        lines.extend(["", "## Runtime Default Change Blockers", ""])
        lines.extend([f"- {blocker}" for blocker in runtime_blockers])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _artifact_paths(storage_root: Path, candidate_name: str) -> dict[str, Path]:
    candidate_root = storage_root / "trained_detector_candidates" / candidate_name
    suite_root = storage_root / "benchmark_suites" / DEFAULT_SUITE_NAME
    promotion_root = candidate_root / "promotion_v1"
    return {
        "candidateRoot": candidate_root,
        "trainingRunSummaryPath": candidate_root / "training_run_summary.json",
        "evaluationContractPath": candidate_root / "evaluation_contract.json",
        "evaluationSummaryPath": candidate_root / "evaluation_v1" / "evaluation_summary.json",
        "evaluationBatchOutcomePath": candidate_root / "evaluation_v1" / "batch_outcome_analysis.json",
        "suiteSummaryPath": suite_root / "suite_summary.json",
        "activeLaneSnapshotPath": suite_root / "active_lane_snapshot.json",
        "suiteRobustnessDiagnosisPath": suite_root / "suite_robustness_diagnosis.json",
        "promotionRoot": promotion_root,
        "promotionSummaryPath": promotion_root / "promotion_summary.json",
        "promotionBatchOutcomePath": promotion_root / "batch_outcome_analysis.json",
        "promotionBatchMarkdownPath": promotion_root / "batch_outcome_analysis.md",
        "suitePromotionPath": suite_root / "detector_candidate_promotion.json",
        "runtimeRegistryPath": storage_root / "runtime" / "promoted_touchline_detector_candidate.json",
    }


def _validate_promotion(
    *,
    candidate_name: str,
    training_run_summary: dict[str, object],
    evaluation_contract: dict[str, object],
    evaluation_summary: dict[str, object],
    evaluation_batch_outcome: dict[str, object],
    suite_summary: dict[str, object],
) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    runtime_default_change_blockers: list[str] = []

    best_weights_path = Path(str(training_run_summary.get("bestWeightsPath") or "")).expanduser()
    if not best_weights_path.exists():
        blockers.append("candidate_weights_missing")
    if not bool(training_run_summary.get("trainingCompleted")):
        blockers.append("training_not_complete")
    if not bool(training_run_summary.get("weightsReady")):
        blockers.append("weights_not_ready")
    if not bool(training_run_summary.get("evaluationContractReady")):
        blockers.append("evaluation_contract_not_ready")
    if not bool(evaluation_contract.get("candidateReadyForEvaluation")):
        blockers.append("candidate_not_ready_for_evaluation")
    if not bool(evaluation_batch_outcome.get("goalAchieved")):
        blockers.append("evaluation_goal_not_achieved")
    if not bool(evaluation_batch_outcome.get("roadmapAdvanceAllowed")):
        blockers.append("evaluation_roadmap_advance_not_allowed")
    if not bool(evaluation_summary.get("readyForPromotion")):
        blockers.append("candidate_not_ready_for_promotion")
    if not bool(evaluation_summary.get("candidateBaselineProductBeatsPlateau")):
        blockers.append("candidate_baseline_did_not_beat_plateau")
    if not bool(evaluation_summary.get("baselineControlProofRan")):
        blockers.append("baseline_control_proof_not_run")
    if not bool(evaluation_summary.get("candidateBeatsSameBatchBaselineControl")):
        blockers.append("candidate_did_not_beat_same_batch_baseline_control")
    if str(suite_summary.get("sourceRobustnessRecommendedNextLever") or "").strip() != NEXT_LEVER:
        blockers.append("suite_active_lane_not_pinned_to_promotion")

    suite_runtime_blockers = suite_summary.get("sourceRobustnessPromotionBlockers")
    if isinstance(suite_runtime_blockers, list):
        runtime_default_change_blockers = [str(item) for item in suite_runtime_blockers if str(item).strip()]
    else:
        runtime_default_change_blockers = list(DEFAULT_RUNTIME_CHANGE_BLOCKERS)
    if not runtime_default_change_blockers:
        runtime_default_change_blockers = list(DEFAULT_RUNTIME_CHANGE_BLOCKERS)

    if str(evaluation_summary.get("trainingCandidateName") or "").strip() != candidate_name:
        blockers.append("evaluation_candidate_name_mismatch")
    return blockers, runtime_default_change_blockers


def run_touchline_detector_candidate_promotion_validation(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
) -> dict[str, object]:
    paths = _artifact_paths(storage_root, candidate_name)
    training_run_summary = _load_json(paths["trainingRunSummaryPath"])
    evaluation_contract = _load_json(paths["evaluationContractPath"])
    evaluation_summary = _load_json(paths["evaluationSummaryPath"])
    evaluation_batch_outcome = _load_json(paths["evaluationBatchOutcomePath"])
    suite_summary = _load_json(paths["suiteSummaryPath"])
    active_lane_snapshot = _load_json(paths["activeLaneSnapshotPath"])
    suite_robustness_diagnosis = _load_json(paths["suiteRobustnessDiagnosisPath"])

    validation_blockers, runtime_default_change_blockers = _validate_promotion(
        candidate_name=candidate_name,
        training_run_summary=training_run_summary,
        evaluation_contract=evaluation_contract,
        evaluation_summary=evaluation_summary,
        evaluation_batch_outcome=evaluation_batch_outcome,
        suite_summary=suite_summary,
    )
    promotion_validated = not validation_blockers
    promoted_for_controlled_runs = promotion_validated
    runtime_default_changed = False
    runtime_default_change_allowed = False
    roadmap_advance_allowed = promotion_validated

    best_weights_path = Path(str(training_run_summary.get("bestWeightsPath") or "")).expanduser()
    promotion_summary = {
        "generatedAt": _utc_now_iso(),
        "promotionBatchName": PROMOTION_BATCH_NAME,
        "trainingCandidateName": candidate_name,
        "evaluationBatchName": evaluation_summary.get("evaluationBatchName"),
        "promotionValidated": promotion_validated,
        "promotedForControlledRuns": promoted_for_controlled_runs,
        "runtimeDefaultChanged": runtime_default_changed,
        "runtimeDefaultChangeAllowed": runtime_default_change_allowed,
        "runtimeDefaultChangeBlockers": runtime_default_change_blockers,
        "promotionValidationBlockers": validation_blockers,
        "candidateBaselineProductBeatsPlateau": bool(
            evaluation_summary.get("candidateBaselineProductBeatsPlateau")
        ),
        "baselineControlProofRan": bool(evaluation_summary.get("baselineControlProofRan")),
        "candidateBeatsSameBatchBaselineControl": bool(
            evaluation_summary.get("candidateBeatsSameBatchBaselineControl")
        ),
        "readyForPromotion": bool(evaluation_summary.get("readyForPromotion")),
        "goalAchieved": promotion_validated,
        "roadmapAdvanceAllowed": roadmap_advance_allowed,
        "nextRecommendedNextLever": NEXT_LEVER,
        "runtimeContract": {
            "primaryDetectorModelPath": (
                evaluation_contract.get("activeFrozenBaseline", {}) or {}
            ).get("detectorModelPath")
            or "yolov10n.pt",
            "auxiliaryBallModelPath": str(best_weights_path),
            "auxiliaryBallModelProfile": evaluation_contract.get("auxiliaryBallModelProfile")
            or "ball_probe_only_v1",
            "primaryMode": (
                evaluation_contract.get("activeFrozenBaseline", {}) or {}
            ).get("primaryMode")
            or "anchored_player_ranked_context_960",
            "cleanupLane": (
                evaluation_contract.get("activeFrozenBaseline", {}) or {}
            ).get("cleanupLane")
            or "recent_ball_plus_inward_anchor_center_bias35_960",
        },
        "sourceRobustnessPromotionBlockers": runtime_default_change_blockers,
        "suiteVerdict": suite_summary.get("suiteVerdict"),
    }

    batch_outcome_analysis = {
        "batchGoal": f"Validate {candidate_name} for controlled promotion use without changing runtime defaults.",
        "goalAchieved": promotion_validated,
        "roadmapAdvanceAllowed": roadmap_advance_allowed,
        "englishSummary": (
            f"{PROMOTION_BATCH_NAME} achieved its goal: {candidate_name} is validated for controlled promotion use."
            if promotion_validated
            else f"{PROMOTION_BATCH_NAME} did not achieve its goal: {candidate_name} is not yet validated for controlled promotion use."
        ),
        "englishDecision": (
            "The candidate is promoted for controlled/internal runs only. Runtime defaults remain frozen because broader promotion blockers still exist."
            if promotion_validated
            else "Do not promote the candidate yet. Resolve the promotion-validation blockers before any promotion claim."
        ),
        "promotionValidated": promotion_validated,
        "promotedForControlledRuns": promoted_for_controlled_runs,
        "runtimeDefaultChanged": runtime_default_changed,
        "runtimeDefaultChangeAllowed": runtime_default_change_allowed,
        "runtimeDefaultChangeBlockers": runtime_default_change_blockers,
        "promotionValidationBlockers": validation_blockers,
        "nextRecommendedNextLever": NEXT_LEVER,
    }

    suite_promotion_payload = {
        **promotion_summary,
        "batchOutcomeAnalysis": batch_outcome_analysis,
    }
    runtime_registry_payload = {
        "generatedAt": _utc_now_iso(),
        "trainingCandidateName": candidate_name,
        "promotionBatchName": PROMOTION_BATCH_NAME,
        "promotionValidated": promotion_validated,
        "promotedForControlledRuns": promoted_for_controlled_runs,
        "runtimeDefaultChanged": runtime_default_changed,
        "runtimeDefaultChangeAllowed": runtime_default_change_allowed,
        "runtimeDefaultChangeBlockers": runtime_default_change_blockers,
        "runtimeContract": dict(promotion_summary["runtimeContract"]),
        "sourceRobustnessRecommendedNextLever": suite_summary.get("sourceRobustnessRecommendedNextLever"),
        "suiteVerdict": suite_summary.get("suiteVerdict"),
        "activeChecklistPath": "docs/superpowers/plans/2026-04-23-touchline-detector-candidate-promotion-v6.md",
        "evidence": {
            "candidatePromotionPath": str(paths["promotionSummaryPath"]),
            "suitePromotionPath": str(paths["suitePromotionPath"]),
            "evaluationSummaryPath": str(paths["evaluationSummaryPath"]),
        },
    }

    _write_json(paths["promotionSummaryPath"], promotion_summary)
    _write_json(paths["promotionBatchOutcomePath"], batch_outcome_analysis)
    _write_markdown(paths["promotionBatchMarkdownPath"], batch_outcome_analysis)
    _write_json(paths["suitePromotionPath"], suite_promotion_payload)
    _write_json(paths["runtimeRegistryPath"], runtime_registry_payload)

    return {
        **suite_promotion_payload,
        "activeLaneSnapshotPath": str(paths["activeLaneSnapshotPath"]),
        "suiteRobustnessDiagnosisPath": str(paths["suiteRobustnessDiagnosisPath"]),
        "activeLaneSnapshotGeneratedAt": active_lane_snapshot.get("generatedAt"),
        "suiteRobustnessDiagnosisGeneratedAt": suite_robustness_diagnosis.get("generatedAt"),
    }


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a promoted touchline detector candidate for controlled/internal use."
    )
    parser.add_argument(
        "--storage-root",
        type=Path,
        default=DEFAULT_STORAGE_ROOT,
        help="Storage root containing trained_detector_candidates and benchmark_suites.",
    )
    parser.add_argument(
        "--candidate-name",
        default=DEFAULT_CANDIDATE_NAME,
        help="Detector candidate name to validate for promotion.",
    )
    return parser


def main() -> None:
    parser = _build_argument_parser()
    args = parser.parse_args()
    payload = run_touchline_detector_candidate_promotion_validation(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
