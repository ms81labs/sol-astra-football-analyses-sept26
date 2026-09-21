from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from math import ceil
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_SUITE_NAME = "frozen-viable-baseline-slice-suite"
DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_OUTPUT_DIR_NAME = "v7_2_default_path_inboard_ball_recovery_v1"
SOURCE_CLIP_ID = "trimed-5min.mp4"

SOURCE_FRAME_WIDTH = 3840.0
SOURCE_FRAME_HEIGHT = 2160.0
MIN_RETENTION_RATIO = 0.60
NEAR_VIABLE_EDGE_SHARE = 0.65
VIABLE_EDGE_SHARE = 0.60

BLOCKER_ARTIFACTS_MISSING = "v7_2_default_path_inboard_recovery_artifacts_missing"
BLOCKER_GUARDRAIL = "v7_2_default_path_inboard_recovery_guardrail_blocked"
BLOCKER_COVERAGE = "v7_2_default_path_inboard_candidate_coverage_gap"

NEXT_INSTRUMENTATION = "v7_2_default_path_inboard_recovery_instrumentation"
NEXT_GUARDRAIL_REPAIR = "v7_2_default_path_inboard_guardrail_repair"
NEXT_CANDIDATE_MINING = "v7_2_default_path_inboard_candidate_mining"
NEXT_RUNTIME_DEFAULT_CHANGE = "v7_2_runtime_default_change_validation"


def _safe_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _suite_root(storage_root: Path) -> Path:
    return Path(storage_root) / "benchmark_suites" / DEFAULT_SUITE_NAME


def _candidate_pipeline_root(storage_root: Path, candidate_name: str) -> Path:
    return (
        Path(storage_root)
        / "trained_detector_candidates"
        / candidate_name
        / "v7_2_full_pipeline_non_promotion_eval_v1"
    )


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "default_path_inboard_candidate_source_audit",
            "successCriteria": [
                "read edge-share reduction inboard requirements",
                "audit v7.2 reviewed-positive full-pipeline rows, probe-safe rows, and existing accepted rows",
                "count safe non-edge candidate frames per failing slice",
            ],
            "failureAdaptation": "If source artifacts are missing, stop at instrumentation; do not relax runtime-default criteria.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "v7_2_controlled_inboard_recovery_profile",
            "successCriteria": [
                "cover each near-viable inboard deficit with safe candidate frames",
                "preserve top-left, canary, sampled-frame, giant-box, projection, checkpoint, and trained-weight guardrails",
                "write a source-robustness regeneration contract for the controlled profile",
            ],
            "failureAdaptation": "If candidate coverage is short, select inboard candidate mining instead of changing defaults.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "inboard_recovery_blocker_summary",
            "successCriteria": [
                "write exactly one primary blocker or clear it",
                "write exactly one next corrective family",
                "keep training, promotion mutation, and runtime-default mutation unexecuted",
            ],
            "failureAdaptation": "Stop after blocker summary; only a later runtime-default validation may mutate defaults.",
        },
    ]


def _frame_id(row: dict[str, Any]) -> int | None:
    value = row.get("Frame_ID", row.get("frameId", row.get("frameIndex")))
    frame_id = _safe_int(value, -1)
    return frame_id if frame_id >= 0 else None


def _source_center_percent(row: dict[str, Any]) -> tuple[float, float] | None:
    if "X" in row and "Y" in row:
        return _safe_float(row.get("X")), _safe_float(row.get("Y"))
    if "x" in row and "y" in row:
        return _safe_float(row.get("x")), _safe_float(row.get("y"))
    bbox = row.get("sourceFrameBbox")
    if not isinstance(bbox, dict):
        bbox = {
            "x1": row.get("Source_X1", row.get("sourceX1")),
            "y1": row.get("Source_Y1", row.get("sourceY1")),
            "x2": row.get("Source_X2", row.get("sourceX2")),
            "y2": row.get("Source_Y2", row.get("sourceY2")),
        }
    if any(value is None for value in (bbox.get("x1"), bbox.get("y1"), bbox.get("x2"), bbox.get("y2"))):
        return None
    width = _safe_float(row.get("sourceFrameWidth", row.get("frameWidth")), SOURCE_FRAME_WIDTH)
    height = _safe_float(row.get("sourceFrameHeight", row.get("frameHeight")), SOURCE_FRAME_HEIGHT)
    if width <= 0.0 or height <= 0.0:
        return None
    center_x = (_safe_float(bbox.get("x1")) + _safe_float(bbox.get("x2"))) / 2.0
    center_y = (_safe_float(bbox.get("y1")) + _safe_float(bbox.get("y2"))) / 2.0
    return center_x / width * 100.0, center_y / height * 100.0


def _is_inboard_row(row: dict[str, Any]) -> bool:
    center = _source_center_percent(row)
    if center is None:
        return False
    x, y = center
    return 5.0 < x < 95.0 and 5.0 < y < 95.0


def _best_rows_by_frame(rows: list[Any]) -> list[dict[str, Any]]:
    best_by_frame: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        frame_id = _frame_id(row)
        if frame_id is None:
            continue
        existing = best_by_frame.get(frame_id)
        confidence = _safe_float(row.get("Conf", row.get("confidence")), 0.0)
        existing_confidence = _safe_float(existing.get("Conf", existing.get("confidence")), 0.0) if existing else -1.0
        if existing is None or confidence >= existing_confidence:
            best_by_frame[frame_id] = dict(row)
    return [best_by_frame[frame_id] for frame_id in sorted(best_by_frame)]


def _accepted_frame_ids(storage_root: Path, match_id: str) -> set[int]:
    payload = _load_json(Path(storage_root) / "matches" / match_id / "ball_truth_layers.json") or {}
    accepted_ball = payload.get("acceptedBall") if isinstance(payload.get("acceptedBall"), dict) else {}
    rows = accepted_ball.get("rows") if isinstance(accepted_ball.get("rows"), list) else []
    return {frame_id for row in _best_rows_by_frame(rows) if (frame_id := _frame_id(row)) is not None}


def _candidate_rows_from_pipeline(pipeline_audit: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(pipeline_audit, dict):
        return []
    frame_rows = pipeline_audit.get("frameRows") if isinstance(pipeline_audit.get("frameRows"), list) else []
    candidates: dict[int, dict[str, Any]] = {}
    for frame in frame_rows:
        if not isinstance(frame, dict):
            continue
        frame_id = _frame_id(frame)
        if frame_id is None:
            continue
        if str(frame.get("sourceClipId") or "") != SOURCE_CLIP_ID:
            continue
        if not (
            frame.get("candidateCropCoversGtBall")
            and frame.get("cropDetectorLocalized")
            and frame.get("sourceFrameLocalized")
            and frame.get("acceptedAsObservedBall")
        ):
            continue
        row = {
            "sourceClipId": frame.get("sourceClipId"),
            "frameIndex": frame_id,
            "sourceFrameBbox": frame.get("sourceFrameBbox"),
            "cropRowCount": len(frame.get("cropRows") or []) if isinstance(frame.get("cropRows"), list) else 0,
            "maxConfidence": max(
                [_safe_float(crop.get("confidence"), 0.0) for crop in frame.get("cropRows", []) if isinstance(crop, dict)]
                or [0.0]
            ),
            "sourceFrameLocalized": True,
            "acceptedAsObservedBall": True,
        }
        if not _is_inboard_row(row):
            continue
        candidates[frame_id] = row
    return [candidates[frame_id] for frame_id in sorted(candidates)]


def _guardrail_audit(summary: dict[str, Any] | None, candidate_rows: list[dict[str, Any]]) -> dict[str, Any]:
    required_present = isinstance(summary, dict) and bool(candidate_rows)
    checks = {
        "fullPipelineSummaryPresent": isinstance(summary, dict),
        "candidateRowsPresent": bool(candidate_rows),
        "fullPipelineGoalAchieved": bool((summary or {}).get("goalAchieved")),
        "checkpointContractPassed": bool((summary or {}).get("checkpointContractPassed")),
        "inferenceUsedTrainedWeights": bool((summary or {}).get("inferenceUsedTrainedWeights")),
        "missingArtifactCountClear": _safe_int((summary or {}).get("missingArtifactCount"), 1) == 0,
        "projectionAuditPassed": bool((summary or {}).get("projectionAuditPassed")),
        "sourceFrameLocalizationStrong": _safe_float((summary or {}).get("sourceFrameLocalizationHitRate"), 0.0) >= 0.90,
        "observedBallAcceptanceStrong": _safe_float((summary or {}).get("observedBallAcceptanceRate"), 0.0) >= 0.90,
        "oldTopLeftArtifactClear": _safe_float(
            (summary or {}).get("oldTopLeftArtifactFalsePositiveFrameRate"),
            1.0,
        )
        <= 0.05,
        "topLeftArtifactShareClear": _safe_float((summary or {}).get("topLeftArtifactShare"), 1.0) == 0.0,
        "heldoutCanaryClear": _safe_float((summary or {}).get("heldoutCanaryFalsePositiveFrameRate"), 1.0) <= 0.10,
        "sampledFrameFloodClear": _safe_float((summary or {}).get("sampledFrameDetectionRate"), 1.0) < 0.80,
        "giantBoxClear": _safe_float((summary or {}).get("giantBoxShare"), 1.0) == 0.0,
        "inputRuntimeDefaultMutationAllowedFalse": not bool((summary or {}).get("runtimeDefaultMutationAllowed")),
    }
    return {
        "requiredInputsPresent": required_present,
        "checks": checks,
        "guardrailsPassed": required_present and all(checks.values()),
        "sourceSummary": {
            "sourceFrameLocalizationHitRate": (summary or {}).get("sourceFrameLocalizationHitRate"),
            "observedBallAcceptanceRate": (summary or {}).get("observedBallAcceptanceRate"),
            "oldTopLeftArtifactFalsePositiveFrameRate": (summary or {}).get(
                "oldTopLeftArtifactFalsePositiveFrameRate"
            ),
            "heldoutCanaryFalsePositiveFrameRate": (summary or {}).get("heldoutCanaryFalsePositiveFrameRate"),
            "sampledFrameDetectionRate": (summary or {}).get("sampledFrameDetectionRate"),
            "topLeftArtifactShare": (summary or {}).get("topLeftArtifactShare"),
            "giantBoxShare": (summary or {}).get("giantBoxShare"),
        },
    }


def _build_recovery_profile(
    *,
    storage_root: Path,
    requirements: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    slice_profiles = []
    for requirement in requirements:
        match_id = str(requirement.get("matchId") or "")
        accepted_frames = _accepted_frame_ids(storage_root, match_id)
        available_rows = [
            row for row in candidate_rows if _safe_int(row.get("frameIndex"), -1) not in accepted_frames
        ]
        near_deficit = _safe_int(requirement.get("nearViableAdditionalInboardFramesNeeded"), 0)
        viable_deficit = _safe_int(requirement.get("viableAdditionalInboardFramesNeeded"), 0)
        selected_near = available_rows[:near_deficit]
        selected_viable = available_rows[:viable_deficit]
        accepted_count = _safe_int(requirement.get("acceptedFrameCount"), 0)
        accepted_non_edge = _safe_int(requirement.get("acceptedNonEdgeFrameCount"), 0)
        min_retained_count = ceil(MIN_RETENTION_RATIO * accepted_count) if accepted_count > 0 else 0
        near_projected_inboard_count = accepted_non_edge + len(selected_near)
        viable_projected_inboard_count = accepted_non_edge + len(selected_viable)
        near_projected_edge_count = max(0, min_retained_count - near_projected_inboard_count)
        viable_projected_edge_count = max(0, min_retained_count - viable_projected_inboard_count)
        near_projected_share = (
            round(near_projected_edge_count / min_retained_count, 6)
            if min_retained_count > 0
            else 0.0
        )
        viable_projected_share = (
            round(viable_projected_edge_count / min_retained_count, 6)
            if min_retained_count > 0
            else 0.0
        )
        slice_profiles.append(
            {
                "matchId": match_id,
                "acceptedFrameCount": accepted_count,
                "acceptedNonEdgeFrameCount": accepted_non_edge,
                "minRetainedFrameCountForRetention": min_retained_count,
                "nearViableAdditionalInboardFramesNeeded": near_deficit,
                "viableAdditionalInboardFramesNeeded": viable_deficit,
                "availableInboardCandidateFrameCount": len(available_rows),
                "selectedNearViableCandidateFrameIds": [row["frameIndex"] for row in selected_near],
                "selectedViableCandidateFrameIds": [row["frameIndex"] for row in selected_viable],
                "nearViableDeficitCovered": len(selected_near) >= near_deficit,
                "viableDeficitCovered": len(selected_viable) >= viable_deficit,
                "projectedNearViableInboardFrameCountAtRetentionFloor": near_projected_inboard_count,
                "projectedViableInboardFrameCountAtRetentionFloor": viable_projected_inboard_count,
                "projectedNearViableEdgeShareAfterRecovery": near_projected_share,
                "projectedViableEdgeShareAfterRecovery": viable_projected_share,
                "projectedNearViableEdgeShareClearsGate": near_projected_share <= NEAR_VIABLE_EDGE_SHARE,
                "projectedViableEdgeShareClearsGate": viable_projected_share <= VIABLE_EDGE_SHARE,
            }
        )
    return {
        "controlledRecoveryProfileName": "source_robustness_shadow_v7_2_default_path_inboard_recovery_v1",
        "sourceClipId": SOURCE_CLIP_ID,
        "candidateFrameCount": len(candidate_rows),
        "sliceProfiles": slice_profiles,
        "allSliceNearViableDeficitsCovered": bool(slice_profiles)
        and all(bool(row["nearViableDeficitCovered"]) for row in slice_profiles),
        "allSliceViableDeficitsCovered": bool(slice_profiles)
        and all(bool(row["viableDeficitCovered"]) for row in slice_profiles),
        "allSliceProjectedNearViableEdgeShareClearsGate": bool(slice_profiles)
        and all(bool(row["projectedNearViableEdgeShareClearsGate"]) for row in slice_profiles),
        "allSliceProjectedViableEdgeShareClearsGate": bool(slice_profiles)
        and all(bool(row["projectedViableEdgeShareClearsGate"]) for row in slice_profiles),
    }


def _classify(
    *,
    edge_summary: dict[str, Any] | None,
    requirement: dict[str, Any] | None,
    guardrail: dict[str, Any],
    profile: dict[str, Any],
) -> tuple[str | None, str, bool, str]:
    if not isinstance(edge_summary, dict) or not isinstance(requirement, dict) or not guardrail["requiredInputsPresent"]:
        return (
            BLOCKER_ARTIFACTS_MISSING,
            NEXT_INSTRUMENTATION,
            False,
            "Inboard recovery inputs are incomplete; add instrumentation before changing defaults.",
        )
    if edge_summary.get("nextRecommendedNextLever") != "v7_2_default_path_inboard_ball_recovery":
        return (
            BLOCKER_ARTIFACTS_MISSING,
            NEXT_INSTRUMENTATION,
            False,
            "Edge-share generated truth does not currently select inboard recovery.",
        )
    if not guardrail["guardrailsPassed"]:
        return (
            BLOCKER_GUARDRAIL,
            NEXT_GUARDRAIL_REPAIR,
            True,
            "v7.2 inboard candidates do not preserve the required full-pipeline safety guardrails.",
        )
    if not profile["allSliceNearViableDeficitsCovered"]:
        return (
            BLOCKER_COVERAGE,
            NEXT_CANDIDATE_MINING,
            True,
            "Safe inboard candidate rows exist, but they do not cover every near-viable slice deficit.",
        )
    return (
        None,
        NEXT_RUNTIME_DEFAULT_CHANGE,
        True,
        "Safe v7.2 inboard candidate rows cover the default-path near-viable deficits; advance to runtime-default validation without mutating defaults here.",
    )


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V7.2 Default Path Inboard Ball Recovery",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Inboard recovery profile ready: `{summary.get('inboardRecoveryProfileReady')}`",
            f"- All near-viable deficits covered: `{summary.get('allSliceNearViableDeficitsCovered')}`",
            f"- Runtime default mutation ready: `{summary.get('runtimeDefaultMutationReady')}`",
            f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Promotion mutation executed: `{summary.get('promotionMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_v7_2_default_path_inboard_ball_recovery(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "default_path_inboard_candidate_source_audit",
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    suite_root = _suite_root(storage_root)
    output_root = reset_output(suite_root, output_dir_name)

    edge_root = suite_root / "v7_2_default_path_edge_share_reduction_v1"
    edge_summary = _load_json(edge_root / "edge_share_reduction_summary.json")
    requirement = _load_json(edge_root / "inboard_recovery_requirement.json")
    pipeline_root = _candidate_pipeline_root(storage_root, candidate_name)
    pipeline_summary = _load_json(pipeline_root / "v7_2_full_pipeline_non_promotion_summary.json")
    pipeline_audit = _load_json(pipeline_root / "reviewed_positive_pipeline_audit.json")

    candidate_rows = _candidate_rows_from_pipeline(pipeline_audit)
    requirements = requirement.get("sliceRequirements") if isinstance(requirement, dict) else []
    requirements = [dict(row) for row in requirements if isinstance(row, dict)]
    guardrail = _guardrail_audit(pipeline_summary, candidate_rows)
    profile = _build_recovery_profile(
        storage_root=storage_root,
        requirements=requirements,
        candidate_rows=candidate_rows,
    )

    primary_blocker, next_lever, roadmap_advance_allowed, english = _classify(
        edge_summary=edge_summary,
        requirement=requirement,
        guardrail=guardrail,
        profile=profile,
    )
    runtime_ready = (
        primary_blocker is None
        and profile["allSliceNearViableDeficitsCovered"]
        and profile["allSliceProjectedNearViableEdgeShareClearsGate"]
        and guardrail["guardrailsPassed"]
    )
    generated_at = _utc_now_iso()

    summary = {
        "batchName": "v7_2_default_path_inboard_ball_recovery",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlan": _attempt_plan(),
        "attemptPlanFamilies": [item["attemptApproachFamily"] for item in _attempt_plan()],
        "sourceSuiteName": DEFAULT_SUITE_NAME,
        "trainingCandidateName": candidate_name,
        "sourceClipId": SOURCE_CLIP_ID,
        "sourceEdgeShareReductionPrimaryBlocker": (edge_summary or {}).get("primaryBlocker"),
        "sourceEdgeShareReductionNextLever": (edge_summary or {}).get("nextRecommendedNextLever"),
        "safeInboardCandidateFrameCount": len(candidate_rows),
        "sliceCount": len(profile["sliceProfiles"]),
        "allSliceNearViableDeficitsCovered": profile["allSliceNearViableDeficitsCovered"],
        "allSliceViableDeficitsCovered": profile["allSliceViableDeficitsCovered"],
        "allSliceProjectedNearViableEdgeShareClearsGate": profile[
            "allSliceProjectedNearViableEdgeShareClearsGate"
        ],
        "allSliceProjectedViableEdgeShareClearsGate": profile["allSliceProjectedViableEdgeShareClearsGate"],
        "inboardRecoveryProfileReady": runtime_ready,
        "sourceRobustnessGeneratedTruthCleared": runtime_ready,
        "runtimeDefaultMutationReady": runtime_ready,
        "runtimeDefaultMutationAllowed": runtime_ready,
        "runtimeDefaultMutationExecuted": False,
        "trainingAllowed": False,
        "trainingExecuted": False,
        "promotionMutationAllowed": False,
        "promotionMutationExecuted": False,
        "goalAchieved": roadmap_advance_allowed,
        "roadmapAdvanceAllowed": roadmap_advance_allowed,
        "primaryBlocker": primary_blocker,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    candidate_source_audit = {
        "batchName": summary["batchName"],
        "generatedAt": generated_at,
        "sourceClipId": SOURCE_CLIP_ID,
        "candidateFrameCount": len(candidate_rows),
        "candidateRows": candidate_rows,
    }
    controlled_profile_audit = {
        "batchName": summary["batchName"],
        "generatedAt": generated_at,
        **profile,
    }
    source_regeneration_contract = {
        "batchName": summary["batchName"],
        "generatedAt": generated_at,
        "shouldRegenerateSourceRobustness": runtime_ready,
        "controlledRecoveryProfileName": profile["controlledRecoveryProfileName"],
        "sourceRobustnessGeneratedTruthCleared": runtime_ready,
        "runtimeDefaultMutationReady": runtime_ready,
        "runtimeDefaultMutationExecuted": False,
        "nextRecommendedNextLever": next_lever,
        "requiredGuardrails": {
            "checkpointContractPassed": True,
            "inferenceUsedTrainedWeights": True,
            "projectionAuditPassed": True,
            "topLeftArtifactShare": 0.0,
            "heldoutCanaryFalsePositiveFrameRateMax": 0.10,
            "sampledFrameDetectionRateMaxExclusive": 0.80,
            "runtimeDefaultMutationExecutedInThisBatch": False,
        },
    }
    decision_matrix = {
        "batchName": summary["batchName"],
        "generatedAt": generated_at,
        "decisions": [
            {
                "condition": "inboard_recovery_artifacts_missing",
                "selected": primary_blocker == BLOCKER_ARTIFACTS_MISSING,
                "nextRecommendedNextLever": NEXT_INSTRUMENTATION,
            },
            {
                "condition": "full_pipeline_guardrail_regression",
                "selected": primary_blocker == BLOCKER_GUARDRAIL,
                "nextRecommendedNextLever": NEXT_GUARDRAIL_REPAIR,
            },
            {
                "condition": "safe_candidates_do_not_cover_near_viable_deficit",
                "selected": primary_blocker == BLOCKER_COVERAGE,
                "nextRecommendedNextLever": NEXT_CANDIDATE_MINING,
            },
            {
                "condition": "safe_inboard_profile_covers_near_viable_deficit",
                "selected": primary_blocker is None and next_lever == NEXT_RUNTIME_DEFAULT_CHANGE,
                "nextRecommendedNextLever": NEXT_RUNTIME_DEFAULT_CHANGE,
            },
        ],
    }

    _write_json(output_root / "inboard_ball_recovery_summary.json", summary)
    _write_json(output_root / "candidate_source_audit.json", candidate_source_audit)
    _write_json(output_root / "controlled_recovery_profile_audit.json", controlled_profile_audit)
    _write_json(output_root / "guardrail_audit.json", guardrail)
    _write_json(output_root / "source_robustness_regeneration_contract.json", source_regeneration_contract)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "batch_outcome_analysis.json", summary)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument(
        "--attempt-approach-family",
        default="default_path_inboard_candidate_source_audit",
    )
    args = parser.parse_args()
    payload = run_v7_2_default_path_inboard_ball_recovery(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        output_dir_name=args.output_dir_name,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
