from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from math import ceil, floor
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_SUITE_NAME = "frozen-viable-baseline-slice-suite"
DEFAULT_OUTPUT_DIR_NAME = "v7_2_default_path_edge_share_reduction_v1"
FAILING_SOURCE_CLIP_ID = "trimed-5min.mp4"

BASELINE_CONFIG_NAME = "source_robustness_baseline_current"
BEST_QUALIFYING_CONFIG_NAME = "source_robustness_shadow_edge_run_keep_every_2_min10"
BEST_EXPLORATORY_CONFIG_NAME = "source_robustness_shadow_edge_run_keep_every_3_min10"

MIN_RETENTION_RATIO = 0.60
NEAR_VIABLE_EDGE_SHARE = 0.65
VIABLE_EDGE_SHARE = 0.60

BLOCKER_ARTIFACTS_MISSING = "v7_2_default_path_edge_share_artifacts_missing"
BLOCKER_INBOARD_RECOVERY_REQUIRED = "v7_2_default_path_inboard_ball_recovery_required"
BLOCKER_RETENTION_GUARDRAIL = "v7_2_default_path_retention_guardrail_blocks_edge_reduction"

NEXT_INSTRUMENTATION = "v7_2_default_path_edge_share_instrumentation"
NEXT_INBOARD_RECOVERY = "v7_2_default_path_inboard_ball_recovery"
NEXT_RETENTION_REPAIR = "v7_2_default_path_retention_guardrail_repair"
NEXT_RUNTIME_DEFAULT_CHANGE = "v7_2_runtime_default_change_validation"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()






def _suite_root(storage_root: Path) -> Path:
    return Path(storage_root) / "benchmark_suites" / DEFAULT_SUITE_NAME


def _safe_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _frame_id(row: dict[str, Any]) -> int | None:
    value = row.get("Frame_ID", row.get("frameId"))
    frame_id = _safe_int(value, -1)
    return frame_id if frame_id >= 0 else None


def _row_center(row: dict[str, Any]) -> tuple[float, float] | None:
    if "X" in row and "Y" in row:
        return _safe_float(row.get("X")), _safe_float(row.get("Y"))
    if "x" in row and "y" in row:
        return _safe_float(row.get("x")), _safe_float(row.get("y"))
    x1 = row.get("Source_X1", row.get("sourceX1"))
    y1 = row.get("Source_Y1", row.get("sourceY1"))
    x2 = row.get("Source_X2", row.get("sourceX2"))
    y2 = row.get("Source_Y2", row.get("sourceY2"))
    if any(value is None for value in (x1, y1, x2, y2)):
        return None
    return (_safe_float(x1) + _safe_float(x2)) / 2.0, (_safe_float(y1) + _safe_float(y2)) / 2.0


def _is_edge_row(row: dict[str, Any]) -> bool:
    center = _row_center(row)
    if center is None:
        return False
    x, y = center
    return x <= 5.0 or x >= 95.0 or y <= 5.0 or y >= 95.0


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


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "default_path_edge_share_failure_slice_audit",
            "successCriteria": [
                "read current source-robustness default blocker artifacts",
                "quantify baseline, best qualifying, and best exploratory edge/retention tradeoffs",
                "identify failing slices and current blocker class",
            ],
            "failureAdaptation": "If artifacts are missing, stop at edge-share instrumentation instead of mutating defaults.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "edge_reduction_feasibility_adaptation",
            "successCriteria": [
                "prove whether edge-only thinning can clear the near-viable edge-share gate while preserving retention",
                "compute minimum additional inboard frames needed per failing slice",
                "select inboard recovery if edge-only reduction is infeasible",
            ],
            "failureAdaptation": "If edge-only is feasible but retention is the limiting factor, move to retention guardrail repair.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "default_path_edge_share_blocker_summary",
            "successCriteria": [
                "write exactly one primary blocker",
                "write exactly one next corrective family",
                "keep training, promotion, and runtime-default mutation frozen",
            ],
            "failureAdaptation": "Stop after blocker summary; do not force a runtime-default switch.",
        },
    ]


def _config_source_summary(source_audit: dict[str, Any], config_name: str) -> dict[str, Any]:
    configs = source_audit.get("configs") if isinstance(source_audit.get("configs"), dict) else {}
    config = configs.get(config_name) if isinstance(configs, dict) else None
    if not isinstance(config, dict):
        return {}
    summaries = config.get("sourceSummaries") if isinstance(config.get("sourceSummaries"), dict) else {}
    summary = summaries.get(FAILING_SOURCE_CLIP_ID) if isinstance(summaries, dict) else None
    return dict(summary) if isinstance(summary, dict) else {}


def _config_matrix_summary(matrix: dict[str, Any], config_name: str) -> dict[str, Any]:
    configs = matrix.get("configs") if isinstance(matrix.get("configs"), dict) else {}
    config = configs.get(config_name) if isinstance(configs, dict) else None
    return dict(config) if isinstance(config, dict) else {}


def _slice_diagnostics(failure_audit: dict[str, Any], config_name: str) -> dict[str, dict[str, Any]]:
    configs = failure_audit.get("configs") if isinstance(failure_audit.get("configs"), dict) else {}
    config = configs.get(config_name) if isinstance(configs, dict) else None
    if not isinstance(config, dict):
        return {}
    rows = config.get("sliceDiagnostics") if isinstance(config.get("sliceDiagnostics"), list) else []
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        match_id = str(row.get("matchId") or "").strip()
        if match_id:
            result[match_id] = dict(row)
    return result


def _accepted_row_counts(storage_root: Path, match_id: str) -> dict[str, Any]:
    path = Path(storage_root) / "matches" / match_id / "ball_truth_layers.json"
    if not path.exists():
        return {
            "matchId": match_id,
            "truthLayersPath": str(path),
            "truthLayersPresent": False,
            "acceptedFrameCount": 0,
            "acceptedEdgeFrameCount": 0,
            "acceptedNonEdgeFrameCount": 0,
        }
    payload = _load_json(path) or {}
    accepted_ball = payload.get("acceptedBall") if isinstance(payload.get("acceptedBall"), dict) else {}
    rows = _best_rows_by_frame(accepted_ball.get("rows") if isinstance(accepted_ball.get("rows"), list) else [])
    edge_count = sum(1 for row in rows if _is_edge_row(row))
    return {
        "matchId": match_id,
        "truthLayersPath": str(path),
        "truthLayersPresent": True,
        "acceptedFrameCount": len(rows),
        "acceptedEdgeFrameCount": edge_count,
        "acceptedNonEdgeFrameCount": len(rows) - edge_count,
        "baselineEdgeFrameShareFromRows": round(edge_count / len(rows), 3) if rows else 0.0,
    }


def _edge_only_feasibility(
    *,
    accepted_frame_count: int,
    accepted_non_edge_frame_count: int,
    edge_share_threshold: float,
) -> dict[str, Any]:
    if accepted_frame_count <= 0:
        return {
            "edgeShareThreshold": edge_share_threshold,
            "minRetainedFrameCountForRetention": 0,
            "maxRetainedFrameCountAllowedByExistingNonEdgeRows": 0,
            "edgeOnlyCanClearGate": False,
            "additionalInboardFramesNeededAtRetentionFloor": 0,
        }
    min_retained = ceil(MIN_RETENTION_RATIO * accepted_frame_count)
    non_edge_fraction_required = max(0.0, 1.0 - edge_share_threshold)
    max_retained_allowed = (
        floor(accepted_non_edge_frame_count / non_edge_fraction_required)
        if non_edge_fraction_required > 0
        else accepted_frame_count
    )
    additional_inboard_needed = max(
        0,
        ceil(non_edge_fraction_required * min_retained) - accepted_non_edge_frame_count,
    )
    return {
        "edgeShareThreshold": edge_share_threshold,
        "minRetainedFrameCountForRetention": min_retained,
        "maxRetainedFrameCountAllowedByExistingNonEdgeRows": max_retained_allowed,
        "edgeOnlyCanClearGate": max_retained_allowed >= min_retained,
        "additionalInboardFramesNeededAtRetentionFloor": additional_inboard_needed,
    }


def _build_slice_audit(
    *,
    storage_root: Path,
    failure_audit: dict[str, Any],
) -> list[dict[str, Any]]:
    baseline_rows = _slice_diagnostics(failure_audit, BASELINE_CONFIG_NAME)
    best_rows = _slice_diagnostics(failure_audit, BEST_QUALIFYING_CONFIG_NAME)
    exploratory_rows = _slice_diagnostics(failure_audit, BEST_EXPLORATORY_CONFIG_NAME)
    match_ids = sorted(set(baseline_rows) | set(best_rows) | set(exploratory_rows))
    audits: list[dict[str, Any]] = []
    for match_id in match_ids:
        row_counts = _accepted_row_counts(storage_root, match_id)
        near_feasibility = _edge_only_feasibility(
            accepted_frame_count=_safe_int(row_counts.get("acceptedFrameCount"), 0),
            accepted_non_edge_frame_count=_safe_int(row_counts.get("acceptedNonEdgeFrameCount"), 0),
            edge_share_threshold=NEAR_VIABLE_EDGE_SHARE,
        )
        viable_feasibility = _edge_only_feasibility(
            accepted_frame_count=_safe_int(row_counts.get("acceptedFrameCount"), 0),
            accepted_non_edge_frame_count=_safe_int(row_counts.get("acceptedNonEdgeFrameCount"), 0),
            edge_share_threshold=VIABLE_EDGE_SHARE,
        )
        baseline = baseline_rows.get(match_id, {})
        best = best_rows.get(match_id, {})
        exploratory = exploratory_rows.get(match_id, {})
        audits.append(
            {
                "matchId": match_id,
                **row_counts,
                "baselineBallTrackEdgeFrameShare": _safe_float(baseline.get("ballTrackEdgeFrameShare"), 0.0),
                "bestQualifyingBallTrackEdgeFrameShare": _safe_float(best.get("ballTrackEdgeFrameShare"), 0.0),
                "bestQualifyingAcceptedRetentionRatio": _safe_float(best.get("acceptedRetentionRatio"), 0.0),
                "bestQualifyingControlledRetentionRatio": _safe_float(best.get("controlledRetentionRatio"), 0.0),
                "bestExploratoryBallTrackEdgeFrameShare": _safe_float(exploratory.get("ballTrackEdgeFrameShare"), 0.0),
                "bestExploratoryAcceptedRetentionRatio": _safe_float(exploratory.get("acceptedRetentionRatio"), 0.0),
                "bestExploratoryControlledRetentionRatio": _safe_float(exploratory.get("controlledRetentionRatio"), 0.0),
                "nearViableEdgeOnlyFeasibility": near_feasibility,
                "viableEdgeOnlyFeasibility": viable_feasibility,
                "needsInboardRecoveryForNearViable": not bool(near_feasibility["edgeOnlyCanClearGate"]),
                "needsInboardRecoveryForViable": not bool(viable_feasibility["edgeOnlyCanClearGate"]),
            }
        )
    return audits


def _tradeoff_audit(
    *,
    source_audit: dict[str, Any],
    matrix: dict[str, Any],
) -> dict[str, Any]:
    configs = []
    for config_name in [BASELINE_CONFIG_NAME, BEST_QUALIFYING_CONFIG_NAME, BEST_EXPLORATORY_CONFIG_NAME]:
        source_summary = _config_source_summary(source_audit, config_name)
        matrix_summary = _config_matrix_summary(matrix, config_name)
        configs.append(
            {
                "configName": config_name,
                "medianBallTrackEdgeFrameShare": _safe_float(
                    source_summary.get("medianBallTrackEdgeFrameShare"),
                    0.0,
                ),
                "medianAcceptedRetentionRatio": _safe_float(
                    source_summary.get("medianAcceptedRetentionRatio"),
                    0.0,
                ),
                "medianControlledRetentionRatio": _safe_float(
                    source_summary.get("medianControlledRetentionRatio"),
                    0.0,
                ),
                "sourceViable": bool(source_summary.get("sourceViable")),
                "configOutcome": matrix_summary.get("configOutcome") or source_summary.get("configOutcome"),
                "passedPromotionGate": bool(matrix_summary.get("passedPromotionGate")),
                "promotionBlockers": list(matrix_summary.get("promotionBlockers") or []),
                "failingSourceEdgeShareImprovement": _safe_float(
                    matrix_summary.get("failingSourceEdgeShareImprovement"),
                    0.0,
                ),
            }
        )
    return {
        "configs": configs,
        "bestQualifyingConfigName": BEST_QUALIFYING_CONFIG_NAME,
        "bestExploratoryConfigName": BEST_EXPLORATORY_CONFIG_NAME,
        "interpretation": (
            "The qualifying profile preserves retention but remains edge-heavy; "
            "the exploratory profile reduces edge share further but falls below retention guardrails."
        ),
    }


def _classify(
    *,
    suite_summary: dict[str, Any] | None,
    source_audit: dict[str, Any] | None,
    failure_audit: dict[str, Any] | None,
    matrix: dict[str, Any] | None,
    slice_audit: list[dict[str, Any]],
) -> tuple[str | None, str, bool, str]:
    blockers = suite_summary.get("sourceRobustnessPromotionBlockers") if isinstance(suite_summary, dict) else None
    if isinstance(suite_summary, dict) and bool(suite_summary.get("passedPromotionGate")) and not blockers:
        return (
            None,
            NEXT_RUNTIME_DEFAULT_CHANGE,
            True,
            "Source robustness is already clear; advance to runtime-default change validation.",
        )
    if not all(isinstance(payload, dict) for payload in (source_audit, failure_audit, matrix)) or not slice_audit:
        return (
            BLOCKER_ARTIFACTS_MISSING,
            NEXT_INSTRUMENTATION,
            False,
            "Source-robustness edge-share artifacts are incomplete; add instrumentation before changing defaults.",
        )
    edge_only_near_viable = all(
        bool(row.get("nearViableEdgeOnlyFeasibility", {}).get("edgeOnlyCanClearGate"))
        for row in slice_audit
        if row.get("truthLayersPresent")
    )
    if not edge_only_near_viable:
        return (
            BLOCKER_INBOARD_RECOVERY_REQUIRED,
            NEXT_INBOARD_RECOVERY,
            True,
            (
                "Edge-only thinning cannot clear the near-viable edge-share gate while preserving retention. "
                "Recover additional inboard/non-edge ball frames in the default source path."
            ),
        )
    return (
        BLOCKER_RETENTION_GUARDRAIL,
        NEXT_RETENTION_REPAIR,
        True,
        "Edge-only reduction is feasible on frame composition, but the existing exploratory profile violates retention guardrails.",
    )


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V7.2 Default Path Edge-Share Reduction",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Edge-only can clear near-viable gate: `{summary.get('edgeOnlyReductionCanClearNearViableGate')}`",
            f"- Additional inboard frames needed for near-viable gate: `{summary.get('minimumAdditionalInboardFramesNeededForNearViable')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_v7_2_default_path_edge_share_reduction(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "default_path_edge_share_failure_slice_audit",
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    suite_root = _suite_root(storage_root)
    output_root = reset_output(suite_root, output_dir_name)

    suite_summary = _load_json(suite_root / "suite_summary.json")
    source_audit = _load_json(suite_root / "primary_source_robustness_source_audit.json")
    failure_audit = _load_json(suite_root / "primary_source_robustness_failure_audit.json")
    matrix = _load_json(suite_root / "primary_source_robustness_matrix.json")
    default_blocker = _load_json(
        suite_root
        / "v7_2_source_robustness_default_blocker_analysis_v1"
        / "default_blocker_analysis_summary.json"
    )

    slice_audit = _build_slice_audit(storage_root=storage_root, failure_audit=failure_audit or {}) if failure_audit else []
    tradeoff = _tradeoff_audit(source_audit=source_audit or {}, matrix=matrix or {})

    primary_blocker, next_lever, roadmap_advance_allowed, english = _classify(
        suite_summary=suite_summary,
        source_audit=source_audit,
        failure_audit=failure_audit,
        matrix=matrix,
        slice_audit=slice_audit,
    )

    inboard_deficits_near = [
        _safe_int(row.get("nearViableEdgeOnlyFeasibility", {}).get("additionalInboardFramesNeededAtRetentionFloor"), 0)
        for row in slice_audit
    ]
    inboard_deficits_viable = [
        _safe_int(row.get("viableEdgeOnlyFeasibility", {}).get("additionalInboardFramesNeededAtRetentionFloor"), 0)
        for row in slice_audit
    ]
    minimum_inboard_near = max(inboard_deficits_near) if inboard_deficits_near else 0
    minimum_inboard_viable = max(inboard_deficits_viable) if inboard_deficits_viable else 0
    edge_only_near = bool(slice_audit) and all(
        bool(row.get("nearViableEdgeOnlyFeasibility", {}).get("edgeOnlyCanClearGate"))
        for row in slice_audit
        if row.get("truthLayersPresent")
    )
    edge_only_viable = bool(slice_audit) and all(
        bool(row.get("viableEdgeOnlyFeasibility", {}).get("edgeOnlyCanClearGate"))
        for row in slice_audit
        if row.get("truthLayersPresent")
    )
    generated_at = _utc_now_iso()
    summary = {
        "batchName": "v7_2_default_path_edge_share_reduction",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlan": _attempt_plan(),
        "attemptPlanFamilies": [item["attemptApproachFamily"] for item in _attempt_plan()],
        "sourceSuiteName": DEFAULT_SUITE_NAME,
        "sourceClipId": FAILING_SOURCE_CLIP_ID,
        "sourceDefaultBlocker": (default_blocker or {}).get("primaryBlocker"),
        "sourceDefaultBlockerNextLever": (default_blocker or {}).get("nextRecommendedNextLever"),
        "sourceRobustnessBestConfigName": (suite_summary or {}).get("sourceRobustnessBestConfigName"),
        "sourceRobustnessBestExploratoryConfigName": (suite_summary or {}).get(
            "sourceRobustnessBestExploratoryConfigName"
        ),
        "edgeOnlyReductionCanClearNearViableGate": edge_only_near,
        "edgeOnlyReductionCanClearViableGate": edge_only_viable,
        "minimumAdditionalInboardFramesNeededForNearViable": minimum_inboard_near,
        "minimumAdditionalInboardFramesNeededForViable": minimum_inboard_viable,
        "sliceCount": len(slice_audit),
        "slicesNeedingInboardRecoveryForNearViable": sum(
            1 for row in slice_audit if row.get("needsInboardRecoveryForNearViable")
        ),
        "slicesNeedingInboardRecoveryForViable": sum(
            1 for row in slice_audit if row.get("needsInboardRecoveryForViable")
        ),
        "goalAchieved": roadmap_advance_allowed,
        "roadmapAdvanceAllowed": roadmap_advance_allowed,
        "primaryBlocker": primary_blocker,
        "nextRecommendedNextLever": next_lever,
        "trainingAllowed": False,
        "trainingExecuted": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationAllowed": False,
        "runtimeDefaultMutationExecuted": False,
        "englishDecision": english,
    }
    feasibility_audit = {
        "batchName": summary["batchName"],
        "generatedAt": generated_at,
        "minRetentionRatio": MIN_RETENTION_RATIO,
        "nearViableEdgeShareThreshold": NEAR_VIABLE_EDGE_SHARE,
        "viableEdgeShareThreshold": VIABLE_EDGE_SHARE,
        "sliceAudits": slice_audit,
        "edgeOnlyReductionCanClearNearViableGate": edge_only_near,
        "edgeOnlyReductionCanClearViableGate": edge_only_viable,
        "minimumAdditionalInboardFramesNeededForNearViable": minimum_inboard_near,
        "minimumAdditionalInboardFramesNeededForViable": minimum_inboard_viable,
    }
    inboard_requirement = {
        "batchName": summary["batchName"],
        "generatedAt": generated_at,
        "inboardRecoveryRequired": primary_blocker == BLOCKER_INBOARD_RECOVERY_REQUIRED,
        "nextRecommendedNextLever": next_lever,
        "minimumAdditionalInboardFramesNeededForNearViable": minimum_inboard_near,
        "minimumAdditionalInboardFramesNeededForViable": minimum_inboard_viable,
        "sliceRequirements": [
            {
                "matchId": row.get("matchId"),
                "acceptedFrameCount": row.get("acceptedFrameCount"),
                "acceptedNonEdgeFrameCount": row.get("acceptedNonEdgeFrameCount"),
                "nearViableAdditionalInboardFramesNeeded": row.get(
                    "nearViableEdgeOnlyFeasibility",
                    {},
                ).get("additionalInboardFramesNeededAtRetentionFloor"),
                "viableAdditionalInboardFramesNeeded": row.get(
                    "viableEdgeOnlyFeasibility",
                    {},
                ).get("additionalInboardFramesNeededAtRetentionFloor"),
            }
            for row in slice_audit
        ],
    }
    decision_matrix = {
        "batchName": summary["batchName"],
        "generatedAt": generated_at,
        "decisions": [
            {
                "condition": "source_robustness_gate_already_clear",
                "selected": primary_blocker is None and next_lever == NEXT_RUNTIME_DEFAULT_CHANGE,
                "nextRecommendedNextLever": NEXT_RUNTIME_DEFAULT_CHANGE,
            },
            {
                "condition": "edge_share_artifacts_missing",
                "selected": primary_blocker == BLOCKER_ARTIFACTS_MISSING,
                "nextRecommendedNextLever": NEXT_INSTRUMENTATION,
            },
            {
                "condition": "edge_only_reduction_infeasible_without_inboard_recovery",
                "selected": primary_blocker == BLOCKER_INBOARD_RECOVERY_REQUIRED,
                "nextRecommendedNextLever": NEXT_INBOARD_RECOVERY,
            },
            {
                "condition": "edge_only_feasible_but_retention_guardrail_blocks",
                "selected": primary_blocker == BLOCKER_RETENTION_GUARDRAIL,
                "nextRecommendedNextLever": NEXT_RETENTION_REPAIR,
            },
        ],
    }

    _write_json(output_root / "edge_share_reduction_summary.json", summary)
    _write_json(output_root / "edge_share_feasibility_audit.json", feasibility_audit)
    _write_json(output_root / "edge_thinning_tradeoff_audit.json", tradeoff)
    _write_json(output_root / "inboard_recovery_requirement.json", inboard_requirement)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "batch_outcome_analysis.json", summary)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument(
        "--attempt-approach-family",
        default="default_path_edge_share_failure_slice_audit",
    )
    args = parser.parse_args()
    payload = run_v7_2_default_path_edge_share_reduction(
        storage_root=args.storage_root,
        output_dir_name=args.output_dir_name,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
