from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from math import gcd
from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import (  # noqa: E402
    DEFAULT_STORAGE_ROOT,
    MAX_VIABLE_BALL_EDGE_FRAME_SHARE,
    assess_truth_gates,
    load_ball_truth_layers,
    load_accepted_match_state,
    summarize_ball_rows,
    build_benchmark_suite_source_summaries,
    diagnose_benchmark_suite_robustness,
    summarize_match_benchmark,
)
from backend.app.edge_share_repair import apply_source_conditioned_edge_share_repair  # noqa: E402
from backend.app.edge_share_repair_profiles import shadow_source_edge_share_repair_configs  # noqa: E402
from backend.app.proof_summary import build_canonical_proof_summary  # noqa: E402
from backend.app.storage import Storage  # noqa: E402
import backend.run_guerilla as run_guerilla  # noqa: E402
import backend.scripts.run_benchmark_suite as run_benchmark_suite  # noqa: E402

DEFAULT_MANIFEST_PATH = REPO_ROOT / "backend" / "benchmark_suites" / "frozen_viable_baseline_slice_suite.json"
DEFAULT_CANONICAL_PROOF_SUMMARY_PATH = (
    DEFAULT_STORAGE_ROOT / "pod_cycles" / "controlled-possession-assignment-treatment-20260420-rerun3" / "proof_summary.json"
)
BASELINE_CONFIG_NAME = "source_robustness_baseline_current"
SHADOW_CONFIGS = shadow_source_edge_share_repair_configs()
FRONTIER_KEEP_EVERY_VALUES = range(2, 6)
FRONTIER_MIN_RUN_LENGTH_VALUES = range(8, 15)
FRONTIER_CONFIG_NAME_PREFIX = "source_robustness_frontier_keep_every_"
VERDICT_ORDER = {
    "dataset_too_narrow": 0,
    "baseline_not_robust": 1,
    "viable_but_coverage_limited": 2,
    "truth_ready_on_suite": 3,
}
SOURCE_ROBUSTNESS_OUTCOME_ORDER = {
    "source_robustness_weak": 0,
    "source_robustness_partial": 1,
    "source_robustness_strong": 2,
}
PROMOTION_BLOCKER_CANONICAL_PROOF_FLOOR_NOT_INTACT = "canonical_proof_floor_not_intact"
PROMOTION_BLOCKER_SUITE_VERDICT_REGRESSED = "suite_verdict_regressed"
PROMOTION_BLOCKER_ACCEPTED_RETENTION_BELOW_GUARDRAIL = "accepted_retention_below_guardrail"
PROMOTION_BLOCKER_CONTROLLED_RETENTION_BELOW_GUARDRAIL = "controlled_retention_below_guardrail"
PROMOTION_BLOCKER_FAILING_SOURCE_NOT_VIABLE = "failing_source_not_viable"
PROMOTION_BLOCKER_EDGE_SHARE_IMPROVEMENT_INSUFFICIENT = "edge_share_improvement_insufficient"
RECOMMENDED_NEXT_LEVER_REOPEN = "reopen_detector_and_candidate_source_generation"
RECOMMENDED_NEXT_LEVER_PROMOTE_DETECTOR_MODEL_UPGRADE = "promote_detector_model_upgrade"
RECOMMENDED_NEXT_LEVER_PROMOTE_DETECTOR_PLUS_BEST_THIN = "promote_detector_plus_best_thin_candidate"
RECOMMENDED_NEXT_LEVER_PREPARE_TOUCHLINE_TRAINING_DATA = "prepare_touchline_training_data"
RECOMMENDED_NEXT_LEVER_TRAIN_TOUCHLINE_DETECTOR_CANDIDATE = "train_touchline_detector_candidate"
RECOMMENDED_NEXT_LEVER_EVALUATE_TOUCHLINE_DETECTOR_CANDIDATE = "evaluate_touchline_detector_candidate"
RECOMMENDED_NEXT_LEVER_PROMOTE_TOUCHLINE_DETECTOR_CANDIDATE = "promote_touchline_detector_candidate"
RECOMMENDED_NEXT_LEVER_PROMOTE_TOUCHLINE_DETECTOR_CANDIDATE_PLUS_BEST_THIN = (
    "promote_touchline_detector_candidate_plus_best_thin_candidate"
)
RECOMMENDED_NEXT_LEVER_PROMOTED_V7_2_SOURCE_ROBUSTNESS_VALIDATION = (
    "promoted_v7_2_source_robustness_validation"
)
RECOMMENDED_NEXT_LEVER_VALIDATE_PROMOTED_TOUCHLINE_RUNTIME_DEFAULT = (
    "validate_promoted_touchline_runtime_default"
)
RECOMMENDED_NEXT_LEVER_VALIDATE_PROMOTED_TOUCHLINE_RUNTIME_DEFAULT_PLUS_BEST_THIN = (
    "validate_promoted_touchline_runtime_default_plus_best_thin"
)
RECOMMENDED_NEXT_LEVER_START_PHASE_1B_REVIEW_DENSIFICATION = "start_phase_1b_review_densification"
RECOMMENDED_NEXT_LEVER_RETRAIN_TOUCHLINE_DETECTOR_CANDIDATE = "retrain_touchline_detector_candidate"
COMBINED_REOPEN_DETECTOR_MODELS = ("yolov10n.pt", "yolo11s.pt")
COMBINED_REOPEN_STRATEGIES = (
    BASELINE_CONFIG_NAME,
    "source_robustness_shadow_touchline_acquisition_upgrade_v1",
    "source_robustness_shadow_touchline_acquisition_reopen_v2",
    "source_robustness_shadow_touchline_candidate_admission_reopen_v3",
)
COMBINED_REOPEN_PLATEAU_BASELINE = {
    "acceptedBallFrames": 101,
    "controlledPossessionFrames": 98,
    "ballTrackViable": False,
    "ballTrackEdgeFrameShare": 0.812,
}
COMPACT_SOURCE_ROBUSTNESS_FIELDS = (
    "sourceRobustnessActiveConfigName",
    "sourceRobustnessBestConfigName",
    "sourceRobustnessBestExploratoryConfigName",
    "sourceRobustnessOutcome",
    "sourceRobustnessDominantFailureSignal",
    "sourceRobustnessImprovedSourceClipId",
    "sourceRobustnessRecommendedNextLever",
    "sourceRobustnessPromotionBlockers",
)
RETENTION_DIAGNOSTIC_ONLY_NEXT_LEVER = RECOMMENDED_NEXT_LEVER_PROMOTE_TOUCHLINE_DETECTOR_CANDIDATE


def _candidate_version(candidate_name: object) -> int:
    raw_name = str(candidate_name or "").strip()
    if not raw_name:
        return 0
    marker = "_v"
    if marker not in raw_name:
        return 0
    suffix = raw_name.rsplit(marker, 1)[-1]
    digits = []
    for char in suffix:
        if char.isdigit():
            digits.append(char)
        else:
            break
    if not digits:
        return 0
    return int("".join(digits))
TRUTH_GATE_REASON_ACCEPTED_BALL_SPARSE = "Accepted ball layer is still too sparse for truthful 5-10 minute analysis"
TRUTH_GATE_REASON_VIABLE_BALL_TRACK = "Need viable ball track: meaningful motion and edgeFrameShare <= 60%"
TRUTH_GATE_REASON_CONTROLLED_POSSESSION_SPARSE = (
    "Need controlled possession frames/frameCount >= 20% for truthful 5-10 minute analysis"
)


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


def _extract_frame_id(row: object) -> int | None:
    if not isinstance(row, dict):
        return None
    if "frameId" in row:
        return _safe_int(row.get("frameId"), default=-1)
    if "Frame_ID" in row:
        return _safe_int(row.get("Frame_ID"), default=-1)
    return None


def _is_edge_ball_row(row: object) -> bool:
    if not isinstance(row, dict):
        return False
    x = _safe_float(row.get("X", row.get("x")), default=float("nan"))
    y = _safe_float(row.get("Y", row.get("y")), default=float("nan"))
    if x != x or y != y:
        return False
    return (
        x <= 5.0
        or x >= 95.0
        or y <= 5.0
        or y >= 95.0
    )


def _frontier_config_name(keep_every: int, min_run_length: int) -> str:
    return f"{FRONTIER_CONFIG_NAME_PREFIX}{keep_every}_min{min_run_length}"


def _grid_candidate_name(keep_every: int, min_run_length: int) -> str:
    for config_name, config in SHADOW_CONFIGS.items():
        if (
            _safe_int(config.get("keepEvery"), 0) == keep_every
            and _safe_int(config.get("minRunLength"), 0) == min_run_length
        ):
            return config_name
    return _frontier_config_name(keep_every, min_run_length)


def _parse_config_preference_spec(config_name: str | None) -> tuple[int, int]:
    if not isinstance(config_name, str):
        return (0, 0)
    config = SHADOW_CONFIGS.get(config_name)
    if isinstance(config, dict):
        return (
            _safe_int(config.get("keepEvery"), 0),
            _safe_int(config.get("minRunLength"), 0),
        )
    match = re.search(r"keep_every_(\d+)_min(\d+)$", config_name.strip())
    if match is None:
        return (0, 0)
    return (_safe_int(match.group(1), 0), _safe_int(match.group(2), 0))


def _suite_verdict(
    *,
    successful_entry_count: int,
    distinct_source_clip_count: int,
    viable_entry_count: int,
    truth_ready_entry_count: int,
) -> str:
    if successful_entry_count < 5 or distinct_source_clip_count < 2:
        return "dataset_too_narrow"
    if viable_entry_count / successful_entry_count < 0.6:
        return "baseline_not_robust"
    if truth_ready_entry_count == 0:
        return "viable_but_coverage_limited"
    return "truth_ready_on_suite"


def _recommended_next_lever(verdict: str) -> str:
    if verdict == "dataset_too_narrow":
        return "expand_clip_manifest"
    if verdict == "baseline_not_robust":
        return "multi_match_robustness_repair"
    if verdict == "viable_but_coverage_limited":
        return "batch_safe_proof_loop_runner"
    return "analysis_ready_match_data_contract"


def _load_accepted_ball_rows(storage: Storage, match_id: str) -> list[dict[str, object]]:
    ball_truth_layers = load_ball_truth_layers(storage, match_id)
    if not isinstance(ball_truth_layers, dict):
        return []
    accepted_ball = ball_truth_layers.get("acceptedBall")
    if not isinstance(accepted_ball, dict):
        return []
    raw_rows = accepted_ball.get("rows")
    if not isinstance(raw_rows, list):
        return []
    rows = [dict(row) for row in raw_rows if isinstance(row, dict) and _extract_frame_id(row) is not None]
    rows.sort(key=lambda row: _extract_frame_id(row) or -1)
    return rows


def _load_probe_observed_rows(storage: Storage, match_id: str) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    ball_truth_layers = load_ball_truth_layers(storage, match_id)
    if not isinstance(ball_truth_layers, dict):
        return [], []
    probe_observed_ball = ball_truth_layers.get("probeObservedBall")
    if not isinstance(probe_observed_ball, dict):
        return [], []
    filtered_rows = [
        dict(row)
        for row in (probe_observed_ball.get("filteredRows") or [])
        if isinstance(row, dict) and _extract_frame_id(row) is not None
    ]
    raw_rows = [
        dict(row)
        for row in (probe_observed_ball.get("rawRows") or [])
        if isinstance(row, dict) and _extract_frame_id(row) is not None
    ]
    filtered_rows.sort(key=lambda row: _extract_frame_id(row) or -1)
    raw_rows.sort(key=lambda row: _extract_frame_id(row) or -1)
    return filtered_rows, raw_rows


def _load_observed_ball_rows(storage: Storage, match_id: str) -> list[dict[str, object]]:
    ball_truth_layers = load_ball_truth_layers(storage, match_id)
    if not isinstance(ball_truth_layers, dict):
        return []
    observed_ball = ball_truth_layers.get("observedBall")
    if not isinstance(observed_ball, dict):
        return []
    rows = [
        dict(row)
        for row in (observed_ball.get("rows") or [])
        if isinstance(row, dict) and _extract_frame_id(row) is not None
    ]
    rows.sort(key=lambda row: _extract_frame_id(row) or -1)
    return rows


def _load_source_conditioned_acquisition_diagnostics(
    storage: Storage,
    match_id: str,
) -> dict[str, object] | None:
    ball_truth_layers = load_ball_truth_layers(storage, match_id)
    if not isinstance(ball_truth_layers, dict):
        return None
    acquisition_diagnostics = ball_truth_layers.get("sourceConditionedAcquisitionDiagnostics")
    return dict(acquisition_diagnostics) if isinstance(acquisition_diagnostics, dict) else None


def _candidate_row_fingerprint(row: dict[str, object]) -> tuple[object, ...]:
    frame_id = _extract_frame_id(row)
    return (
        frame_id,
        round(_safe_float(row.get("Conf"), 0.0), 6),
        round(_safe_float(row.get("X", row.get("x")), 0.0), 3),
        round(_safe_float(row.get("Y", row.get("y")), 0.0), 3),
        round(_safe_float(row.get("Source_X1"), 0.0), 2),
        round(_safe_float(row.get("Source_Y1"), 0.0), 2),
        round(_safe_float(row.get("Source_X2"), 0.0), 2),
        round(_safe_float(row.get("Source_Y2"), 0.0), 2),
    )


def _synthetic_proposal_crop_size(row: dict[str, object]) -> tuple[float, float]:
    width = max(_safe_float(row.get("Source_X2"), 0.0) - _safe_float(row.get("Source_X1"), 0.0), 0.0)
    height = max(_safe_float(row.get("Source_Y2"), 0.0) - _safe_float(row.get("Source_Y1"), 0.0), 0.0)
    if width > 0.0 and height > 0.0:
        return (round(width, 2), round(height, 2))
    return (58.0, 58.0)


def _replayed_touchline_candidate_kind(
    *,
    source_clip_id: str,
    config_name: str,
    baseline_row: dict[str, object] | None,
    candidate_row: dict[str, object],
) -> str | None:
    if source_clip_id != "trimed-5min.mp4":
        return None
    config_mode = str(SHADOW_CONFIGS.get(config_name, {}).get("mode") or "")
    if config_mode not in {
        "touchline_acquisition_upgrade",
        "touchline_acquisition_reopen",
        "touchline_candidate_admission_reopen",
    }:
        return None
    baseline_touchline_adjacent = bool(isinstance(baseline_row, dict) and _is_edge_ball_row(baseline_row))
    candidate_touchline_adjacent = _is_edge_ball_row(candidate_row)
    if not (baseline_touchline_adjacent or candidate_touchline_adjacent):
        return None
    if config_mode == "touchline_acquisition_upgrade":
        return "touchline_escape"
    return "touchline_escape" if candidate_touchline_adjacent else "touchline_inboard_context"


def _replayed_acquisition_candidate_row(
    row: dict[str, object],
    *,
    proposal_seed_center: tuple[float, float] | None,
    proposal_seed_mode: str,
    proposal_window_kind: str,
    reopened_raw_candidate: bool,
) -> dict[str, object]:
    candidate_row = dict(row)
    if proposal_seed_center is not None:
        candidate_row["ProposalSeedX"] = round(float(proposal_seed_center[0]), 2)
        candidate_row["ProposalSeedY"] = round(float(proposal_seed_center[1]), 2)
    candidate_row["ProposalCropWidth"], candidate_row["ProposalCropHeight"] = _synthetic_proposal_crop_size(candidate_row)
    candidate_row["ProposalWindowKind"] = proposal_window_kind
    candidate_row["ProposalSeedMode"] = proposal_seed_mode
    candidate_row.setdefault("ProposalInferenceMode", "saved_artifact_replay")
    if reopened_raw_candidate:
        candidate_row["TouchlineRawCandidateReopened"] = True
        candidate_row["TouchlineRawCandidateReopenReason"] = "raw_candidate_reopened"
    return candidate_row


def _replay_source_conditioned_acquisition_projection(
    *,
    storage: Storage,
    entry: dict[str, object],
    config_name: str,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    match_id = str(entry.get("matchId") or "")
    source_clip_id = str(entry.get("sourceClipId") or "")
    accepted_rows = _load_accepted_ball_rows(storage, match_id)
    observed_rows = _load_observed_ball_rows(storage, match_id)
    probe_filtered_rows, probe_raw_rows = _load_probe_observed_rows(storage, match_id)
    player_rows = _load_player_rows(storage, match_id)
    stored_acquisition_diagnostics = _load_source_conditioned_acquisition_diagnostics(storage, match_id)
    sample_interval = _infer_sample_interval_from_rows(
        accepted_rows or observed_rows or probe_filtered_rows or probe_raw_rows
    )
    if source_clip_id != "trimed-5min.mp4":
        return accepted_rows, dict(stored_acquisition_diagnostics or {})

    accepted_rows_by_frame = {
        int(row["Frame_ID"]): dict(row)
        for row in run_guerilla._best_ball_rows_by_frame(accepted_rows)
    }
    observed_source_anchors = run_guerilla.collect_observed_source_anchors(observed_rows or accepted_rows)
    filtered_rows_by_frame = run_guerilla._group_rows_by_frame(probe_filtered_rows)
    raw_rows_by_frame = run_guerilla._group_rows_by_frame(probe_raw_rows)
    replay_candidates: list[dict[str, object]] = []

    for frame_id in sorted(set(accepted_rows_by_frame) | set(filtered_rows_by_frame) | set(raw_rows_by_frame)):
        baseline_row = accepted_rows_by_frame.get(frame_id)
        fallback_seed_row = (
            baseline_row
            or next(
                (
                    row
                    for row in filtered_rows_by_frame.get(frame_id, [])
                    if isinstance(row, dict)
                ),
                None,
            )
            or next(
                (
                    row
                    for row in raw_rows_by_frame.get(frame_id, [])
                    if isinstance(row, dict)
                ),
                None,
            )
        )
        seed_center_x, seed_center_y, seed_mode = run_guerilla._player_proposal_seed_center_and_mode(
            frame_id,
            observed_source_anchors,
            frame_interval=sample_interval,
        )
        proposal_seed_center = (
            (float(seed_center_x), float(seed_center_y))
            if seed_center_x is not None and seed_center_y is not None
            else (
                run_guerilla._row_source_box_center(fallback_seed_row)
                if isinstance(fallback_seed_row, dict)
                else None
            )
        )
        if baseline_row is not None:
            replay_candidates.append(dict(baseline_row))

        filtered_fingerprints = {
            _candidate_row_fingerprint(row)
            for row in filtered_rows_by_frame.get(frame_id, [])
            if isinstance(row, dict)
        }
        for candidate_row in filtered_rows_by_frame.get(frame_id, []):
            if not isinstance(candidate_row, dict):
                continue
            proposal_window_kind = _replayed_touchline_candidate_kind(
                source_clip_id=source_clip_id,
                config_name=config_name,
                baseline_row=baseline_row,
                candidate_row=candidate_row,
            )
            if proposal_window_kind is None:
                continue
            replay_candidates.append(
                _replayed_acquisition_candidate_row(
                    candidate_row,
                    proposal_seed_center=proposal_seed_center,
                    proposal_seed_mode=seed_mode,
                    proposal_window_kind=proposal_window_kind,
                    reopened_raw_candidate=False,
                )
            )
        for candidate_row in raw_rows_by_frame.get(frame_id, []):
            if not isinstance(candidate_row, dict):
                continue
            if _candidate_row_fingerprint(candidate_row) in filtered_fingerprints:
                continue
            proposal_window_kind = _replayed_touchline_candidate_kind(
                source_clip_id=source_clip_id,
                config_name=config_name,
                baseline_row=baseline_row,
                candidate_row=candidate_row,
            )
            if proposal_window_kind is None:
                continue
            replay_candidates.append(
                _replayed_acquisition_candidate_row(
                    candidate_row,
                    proposal_seed_center=proposal_seed_center,
                    proposal_seed_mode=seed_mode,
                    proposal_window_kind=proposal_window_kind,
                    reopened_raw_candidate=True,
                )
            )

    if not replay_candidates:
        return accepted_rows, dict(stored_acquisition_diagnostics or {})

    collapsed = run_guerilla._collapse_proposal_recovered_ball_candidates(
        replay_candidates,
        player_rows=player_rows,
        max_frame_gap=sample_interval,
        source_clip_id=source_clip_id,
        edge_share_repair_profile=config_name,
    )
    acquisition_diagnostics = run_guerilla._build_source_conditioned_acquisition_diagnostics(
        profile_name=config_name,
        source_clip_id=source_clip_id,
        candidate_summary=collapsed,
    )
    return list(collapsed.get("rows") or []), acquisition_diagnostics


def resolve_source_robustness_recommended_next_lever(
    *,
    default_next_lever: str,
    source_robustness_diagnosis: dict[str, object],
    combined_reopen_diagnosis: dict[str, object] | None,
    detector_breadth_diagnosis: dict[str, object] | None = None,
    training_prep_diagnosis: dict[str, object] | None = None,
    detector_training_diagnosis: dict[str, object] | None = None,
    detector_training_quality_gate_diagnosis: dict[str, object] | None = None,
    detector_candidate_evaluation_diagnosis: dict[str, object] | None = None,
    detector_candidate_promotion_diagnosis: dict[str, object] | None = None,
    review_densification_diagnosis: dict[str, object] | None = None,
    detector_candidate_data_quality_fix_diagnosis: dict[str, object] | None = None,
    detector_candidate_proposal_signal_fix_diagnosis: dict[str, object] | None = None,
    detector_candidate_validation_gate_remediation_diagnosis: dict[str, object] | None = None,
    promoted_detector_candidate_robustness_diagnosis: dict[str, object] | None = None,
    promoted_detector_candidate_retention_delta_diagnosis: dict[str, object] | None = None,
) -> str:
    detector_training_version = _candidate_version(
        detector_training_diagnosis.get("trainingCandidateName") if isinstance(detector_training_diagnosis, dict) else None
    )
    detector_training_quality_gate_version = _candidate_version(
        detector_training_quality_gate_diagnosis.get("trainingCandidateName")
        if isinstance(detector_training_quality_gate_diagnosis, dict)
        else None
    )
    detector_candidate_evaluation_version = _candidate_version(
        detector_candidate_evaluation_diagnosis.get("trainingCandidateName")
        if isinstance(detector_candidate_evaluation_diagnosis, dict)
        else None
    )
    detector_candidate_promotion_version = _candidate_version(
        detector_candidate_promotion_diagnosis.get("trainingCandidateName")
        if isinstance(detector_candidate_promotion_diagnosis, dict)
        else None
    )
    detector_candidate_data_quality_fix_version = _candidate_version(
        detector_candidate_data_quality_fix_diagnosis.get("trainingCandidateName")
        if isinstance(detector_candidate_data_quality_fix_diagnosis, dict)
        else None
    )
    detector_candidate_proposal_signal_fix_version = _candidate_version(
        detector_candidate_proposal_signal_fix_diagnosis.get("trainingCandidateName")
        if isinstance(detector_candidate_proposal_signal_fix_diagnosis, dict)
        else None
    )
    detector_candidate_validation_gate_remediation_version = _candidate_version(
        detector_candidate_validation_gate_remediation_diagnosis.get("trainingCandidateName")
        if isinstance(detector_candidate_validation_gate_remediation_diagnosis, dict)
        else None
    )
    promoted_detector_candidate_robustness_version = _candidate_version(
        promoted_detector_candidate_robustness_diagnosis.get("trainingCandidateName")
        if isinstance(promoted_detector_candidate_robustness_diagnosis, dict)
        else None
    )
    promoted_detector_candidate_retention_delta_version = _candidate_version(
        promoted_detector_candidate_retention_delta_diagnosis.get("trainingCandidateName")
        if isinstance(promoted_detector_candidate_retention_delta_diagnosis, dict)
        else None
    )
    phase_roadmap_override_present = any(
        isinstance(diagnosis, dict)
        and str(diagnosis.get("nextRecommendedNextLever") or "").strip()
        in {
            RECOMMENDED_NEXT_LEVER_EVALUATE_TOUCHLINE_DETECTOR_CANDIDATE,
            RECOMMENDED_NEXT_LEVER_RETRAIN_TOUCHLINE_DETECTOR_CANDIDATE,
            RECOMMENDED_NEXT_LEVER_START_PHASE_1B_REVIEW_DENSIFICATION,
            RECOMMENDED_NEXT_LEVER_PROMOTE_TOUCHLINE_DETECTOR_CANDIDATE,
            RECOMMENDED_NEXT_LEVER_PROMOTE_TOUCHLINE_DETECTOR_CANDIDATE_PLUS_BEST_THIN,
            RECOMMENDED_NEXT_LEVER_PROMOTED_V7_2_SOURCE_ROBUSTNESS_VALIDATION,
        }
        for diagnosis in (
            detector_training_diagnosis,
            detector_training_quality_gate_diagnosis,
            detector_candidate_evaluation_diagnosis,
            detector_candidate_promotion_diagnosis,
            review_densification_diagnosis,
            detector_candidate_data_quality_fix_diagnosis,
            detector_candidate_proposal_signal_fix_diagnosis,
            detector_candidate_validation_gate_remediation_diagnosis,
        )
    )
    if default_next_lever == "promote_source_conditioned_edge_share_repair" and not phase_roadmap_override_present:
        return default_next_lever
    detector_training_supersedes_evaluation = detector_training_version > detector_candidate_evaluation_version
    if isinstance(detector_breadth_diagnosis, dict):
        if bool(detector_breadth_diagnosis.get("baselineRemoteBeatsPlateau")):
            return RECOMMENDED_NEXT_LEVER_PROMOTE_DETECTOR_MODEL_UPGRADE
        if bool(detector_breadth_diagnosis.get("compoundThinRemoteBeatsPlateau")):
            return RECOMMENDED_NEXT_LEVER_PROMOTE_DETECTOR_PLUS_BEST_THIN
    if isinstance(detector_candidate_promotion_diagnosis, dict):
        next_lever = str(detector_candidate_promotion_diagnosis.get("nextRecommendedNextLever") or "").strip()
        if (
            detector_candidate_promotion_version >= detector_candidate_evaluation_version
            and next_lever == RECOMMENDED_NEXT_LEVER_PROMOTED_V7_2_SOURCE_ROBUSTNESS_VALIDATION
            and bool(detector_candidate_promotion_diagnosis.get("promotionValidated"))
            and bool(detector_candidate_promotion_diagnosis.get("promotedForControlledRuns"))
        ):
            return next_lever
    if isinstance(detector_candidate_evaluation_diagnosis, dict):
        next_lever = str(detector_candidate_evaluation_diagnosis.get("nextRecommendedNextLever") or "").strip()
        if (
            not detector_training_supersedes_evaluation
            and next_lever in {
                RECOMMENDED_NEXT_LEVER_PROMOTE_TOUCHLINE_DETECTOR_CANDIDATE,
                RECOMMENDED_NEXT_LEVER_PROMOTE_TOUCHLINE_DETECTOR_CANDIDATE_PLUS_BEST_THIN,
            }
        ):
            return next_lever
        if (
            not detector_training_supersedes_evaluation
            and next_lever == RECOMMENDED_NEXT_LEVER_EVALUATE_TOUCHLINE_DETECTOR_CANDIDATE
        ):
            return next_lever
    if isinstance(promoted_detector_candidate_robustness_diagnosis, dict):
        next_lever = str(promoted_detector_candidate_robustness_diagnosis.get("nextRecommendedNextLever") or "").strip()
        promoted_runtime_default_validation_allowed = bool(
            promoted_detector_candidate_robustness_diagnosis.get("winningPassedPromotionGate")
        ) and bool(promoted_detector_candidate_robustness_diagnosis.get("goalAchieved")) and bool(
            promoted_detector_candidate_robustness_diagnosis.get("roadmapAdvanceAllowed")
        )
        if (
            promoted_detector_candidate_robustness_version >= detector_candidate_promotion_version
            and next_lever in {
                RECOMMENDED_NEXT_LEVER_VALIDATE_PROMOTED_TOUCHLINE_RUNTIME_DEFAULT,
                RECOMMENDED_NEXT_LEVER_VALIDATE_PROMOTED_TOUCHLINE_RUNTIME_DEFAULT_PLUS_BEST_THIN,
                RECOMMENDED_NEXT_LEVER_PROMOTE_TOUCHLINE_DETECTOR_CANDIDATE,
            }
        ):
            if (
                next_lever
                in {
                    RECOMMENDED_NEXT_LEVER_VALIDATE_PROMOTED_TOUCHLINE_RUNTIME_DEFAULT,
                    RECOMMENDED_NEXT_LEVER_VALIDATE_PROMOTED_TOUCHLINE_RUNTIME_DEFAULT_PLUS_BEST_THIN,
                }
                and not promoted_runtime_default_validation_allowed
            ):
                return RECOMMENDED_NEXT_LEVER_PROMOTE_TOUCHLINE_DETECTOR_CANDIDATE
            return next_lever
    if isinstance(promoted_detector_candidate_retention_delta_diagnosis, dict):
        next_lever = str(promoted_detector_candidate_retention_delta_diagnosis.get("nextRecommendedNextLever") or "").strip()
        if (
            promoted_detector_candidate_retention_delta_version >= promoted_detector_candidate_robustness_version
            and next_lever == RECOMMENDED_NEXT_LEVER_PROMOTE_TOUCHLINE_DETECTOR_CANDIDATE
        ):
            return next_lever
    if isinstance(detector_candidate_promotion_diagnosis, dict):
        next_lever = str(detector_candidate_promotion_diagnosis.get("nextRecommendedNextLever") or "").strip()
        if (
            detector_candidate_promotion_version >= detector_candidate_evaluation_version
            and next_lever in {
                RECOMMENDED_NEXT_LEVER_PROMOTE_TOUCHLINE_DETECTOR_CANDIDATE,
                RECOMMENDED_NEXT_LEVER_PROMOTE_TOUCHLINE_DETECTOR_CANDIDATE_PLUS_BEST_THIN,
            }
            and bool(detector_candidate_promotion_diagnosis.get("promotionValidated"))
        ):
            return next_lever
    if isinstance(detector_candidate_data_quality_fix_diagnosis, dict):
        next_lever = str(detector_candidate_data_quality_fix_diagnosis.get("nextRecommendedNextLever") or "").strip()
        if (
            detector_candidate_data_quality_fix_version > detector_candidate_evaluation_version
            and next_lever == RECOMMENDED_NEXT_LEVER_EVALUATE_TOUCHLINE_DETECTOR_CANDIDATE
        ):
            return next_lever
    if isinstance(detector_candidate_proposal_signal_fix_diagnosis, dict):
        next_lever = str(detector_candidate_proposal_signal_fix_diagnosis.get("nextRecommendedNextLever") or "").strip()
        if (
            detector_candidate_proposal_signal_fix_version > detector_candidate_evaluation_version
            and next_lever == RECOMMENDED_NEXT_LEVER_EVALUATE_TOUCHLINE_DETECTOR_CANDIDATE
        ):
            return next_lever
    if isinstance(detector_candidate_validation_gate_remediation_diagnosis, dict):
        next_lever = str(
            detector_candidate_validation_gate_remediation_diagnosis.get("nextRecommendedNextLever") or ""
        ).strip()
        if (
            detector_candidate_validation_gate_remediation_version > detector_candidate_evaluation_version
            and next_lever == RECOMMENDED_NEXT_LEVER_EVALUATE_TOUCHLINE_DETECTOR_CANDIDATE
        ):
            return next_lever
    if isinstance(detector_training_quality_gate_diagnosis, dict):
        next_lever = str(detector_training_quality_gate_diagnosis.get("nextRecommendedNextLever") or "").strip()
        if (
            detector_training_quality_gate_version >= detector_candidate_evaluation_version
            and next_lever == RECOMMENDED_NEXT_LEVER_EVALUATE_TOUCHLINE_DETECTOR_CANDIDATE
        ):
            return next_lever
    if isinstance(detector_training_diagnosis, dict):
        batch_outcome_analysis = (
            dict(detector_training_diagnosis.get("batchOutcomeAnalysis"))
            if isinstance(detector_training_diagnosis.get("batchOutcomeAnalysis"), dict)
            else {}
        )
        if bool(detector_training_diagnosis.get("readyForDetectorEvaluation")) and (
            not batch_outcome_analysis or bool(batch_outcome_analysis.get("roadmapAdvanceAllowed"))
        ):
            return RECOMMENDED_NEXT_LEVER_EVALUATE_TOUCHLINE_DETECTOR_CANDIDATE
        next_lever = str(detector_training_diagnosis.get("nextRecommendedNextLever") or "").strip()
        if next_lever == RECOMMENDED_NEXT_LEVER_RETRAIN_TOUCHLINE_DETECTOR_CANDIDATE:
            return next_lever
    if isinstance(review_densification_diagnosis, dict) and bool(
        review_densification_diagnosis.get("readyForRetraining")
    ):
        return RECOMMENDED_NEXT_LEVER_RETRAIN_TOUCHLINE_DETECTOR_CANDIDATE
    if isinstance(detector_candidate_evaluation_diagnosis, dict):
        next_lever = str(detector_candidate_evaluation_diagnosis.get("nextRecommendedNextLever") or "").strip()
        if (
            not detector_training_supersedes_evaluation
            and next_lever == RECOMMENDED_NEXT_LEVER_START_PHASE_1B_REVIEW_DENSIFICATION
        ):
            return next_lever
    if isinstance(training_prep_diagnosis, dict) and bool(training_prep_diagnosis.get("readyForDetectorTraining")):
        return RECOMMENDED_NEXT_LEVER_TRAIN_TOUCHLINE_DETECTOR_CANDIDATE
    if isinstance(review_densification_diagnosis, dict):
        next_lever = str(review_densification_diagnosis.get("nextRecommendedNextLever") or "").strip()
        if next_lever == RECOMMENDED_NEXT_LEVER_START_PHASE_1B_REVIEW_DENSIFICATION:
            return next_lever
    if isinstance(detector_breadth_diagnosis, dict):
        if bool(detector_breadth_diagnosis.get("detectorBreadthFalsified")) or bool(
            detector_breadth_diagnosis.get("nextTrainingCandidateNeeded")
        ):
            return RECOMMENDED_NEXT_LEVER_PREPARE_TOUCHLINE_TRAINING_DATA
    if isinstance(combined_reopen_diagnosis, dict):
        if bool(combined_reopen_diagnosis.get("combinedReopenFalsified")):
            return RECOMMENDED_NEXT_LEVER_REOPEN
        if bool(combined_reopen_diagnosis.get("winnerBeatsBestThinCandidate")):
            return RECOMMENDED_NEXT_LEVER_REOPEN
    if bool(source_robustness_diagnosis.get("touchlineReplacementFalsified")) and bool(
        source_robustness_diagnosis.get("acquisitionCandidateFalsified")
    ):
        return RECOMMENDED_NEXT_LEVER_REOPEN
    return default_next_lever


def _direct_observation_breakdown_present(storage: Storage, match_id: str) -> bool:
    ball_truth_layers = load_ball_truth_layers(storage, match_id)
    return isinstance(ball_truth_layers, dict) and isinstance(ball_truth_layers.get("directObservationBreakdown"), dict)


def _load_existing_detector_breadth_matrix(output_dir: Path) -> dict[str, object] | None:
    detector_breadth_matrix_path = output_dir / "detector_breadth_matrix.json"
    if not detector_breadth_matrix_path.exists():
        return None
    try:
        payload = json.loads(detector_breadth_matrix_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _build_detector_breadth_diagnosis(payload: dict[str, object] | None) -> dict[str, object] | None:
    if not isinstance(payload, dict):
        return None
    return {
        "screenWinningDetectorModelPath": payload.get("screenWinningDetectorModelPath"),
        "remoteWinningDetectorModelPath": payload.get("remoteWinningDetectorModelPath"),
        "baselineRemoteBeatsPlateau": bool(payload.get("baselineRemoteBeatsPlateau")),
        "compoundThinRemoteBeatsPlateau": bool(payload.get("compoundThinRemoteBeatsPlateau")),
        "detectorBreadthFalsified": bool(payload.get("detectorBreadthFalsified")),
        "nextTrainingCandidateNeeded": bool(payload.get("nextTrainingCandidateNeeded")),
    }


def _load_existing_training_prep_payload(storage_root: Path) -> tuple[dict[str, object] | None, dict[str, object] | None, dict[str, object] | None]:
    artifact_root = Path(storage_root) / "training_prep" / "touchline_training_data_curation_foundation"
    payloads: list[dict[str, object] | None] = []
    for filename in ("curation_manifest.json", "split_manifest.json", "seeded_issue_report.json"):
        path = artifact_root / filename
        if not path.exists():
            payloads.append(None)
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payloads.append(None)
            continue
        payloads.append(payload if isinstance(payload, dict) else None)
    return payloads[0], payloads[1], payloads[2]


def _build_training_prep_diagnosis(
    curation_manifest: dict[str, object] | None,
    split_manifest: dict[str, object] | None,
    seeded_issue_report: dict[str, object] | None,
) -> dict[str, object] | None:
    if not isinstance(curation_manifest, dict):
        return None
    split_manifest = dict(split_manifest or {})
    seeded_issue_report = dict(seeded_issue_report or {})
    return {
        "trainingPrepBatchName": curation_manifest.get("batchName"),
        "failingSourceClipId": curation_manifest.get("failingSourceClipId"),
        "comparisonSourceClipId": curation_manifest.get("comparisonSourceClipId"),
        "representativeFailingMatchId": curation_manifest.get("representativeFailingMatchId"),
        "representativeControlMatchId": curation_manifest.get("representativeControlMatchId"),
        "curationUnitCount": _safe_int(curation_manifest.get("curationUnitCount"), 0),
        "seededIssueCount": _safe_int(seeded_issue_report.get("seededIssueCount"), 0),
        "positiveSeedExampleCount": _safe_int(curation_manifest.get("positiveSeedExampleCount"), 0),
        "negativeSeedExampleCount": _safe_int(curation_manifest.get("negativeSeedExampleCount"), 0),
        "sourceAwareSplitLeakageDetected": bool(split_manifest.get("sourceAwareSplitLeakageDetected")),
        "yoloExportReady": bool(curation_manifest.get("yoloExportReady")),
        "readyForDetectorTraining": bool(curation_manifest.get("readyForDetectorTraining")),
        "trainingPrepPrimaryBlocker": curation_manifest.get("trainingPrepPrimaryBlocker"),
    }


def _load_existing_review_densification_payload(
    storage_root: Path,
) -> tuple[
    dict[str, object] | None,
    dict[str, object] | None,
    dict[str, object] | None,
    dict[str, object] | None,
]:
    artifact_root = Path(storage_root) / "training_prep" / "touchline_review_densification_v1"
    payloads: list[dict[str, object] | None] = []
    for filename in (
        "review_densification_manifest.json",
        "split_manifest.json",
        "review_bundle_report.json",
        "batch_outcome_analysis.json",
    ):
        path = artifact_root / filename
        if not path.exists():
            payloads.append(None)
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payloads.append(None)
            continue
        payloads.append(payload if isinstance(payload, dict) else None)
    return payloads[0], payloads[1], payloads[2], payloads[3]


def _build_review_densification_diagnosis(
    review_densification_manifest: dict[str, object] | None,
    split_manifest: dict[str, object] | None,
    review_bundle_report: dict[str, object] | None,
    batch_outcome_analysis: dict[str, object] | None,
) -> dict[str, object] | None:
    if not isinstance(review_densification_manifest, dict):
        return None
    split_manifest = dict(split_manifest or {})
    review_bundle_report = dict(review_bundle_report or {})
    batch_outcome_analysis = dict(batch_outcome_analysis or {})
    ready_for_retraining = bool(batch_outcome_analysis.get("roadmapAdvanceAllowed")) and bool(
        batch_outcome_analysis.get("readyForRetraining")
    )
    if not ready_for_retraining:
        ready_for_retraining = bool(review_densification_manifest.get("readyForRetraining"))
    if not ready_for_retraining:
        ready_for_retraining = bool(split_manifest.get("readyForRetraining"))
    if batch_outcome_analysis and not bool(batch_outcome_analysis.get("roadmapAdvanceAllowed")):
        ready_for_retraining = False
    primary_blocker = review_densification_manifest.get("reviewDensificationPrimaryBlocker")
    if primary_blocker is None:
        primary_blocker = split_manifest.get("reviewDensificationPrimaryBlocker")
    if batch_outcome_analysis.get("primaryBlocker") is not None:
        primary_blocker = batch_outcome_analysis.get("primaryBlocker")
    next_recommended_next_lever = (
        RECOMMENDED_NEXT_LEVER_RETRAIN_TOUCHLINE_DETECTOR_CANDIDATE
        if ready_for_retraining
        else RECOMMENDED_NEXT_LEVER_START_PHASE_1B_REVIEW_DENSIFICATION
    )
    if batch_outcome_analysis:
        candidate_next_lever = str(batch_outcome_analysis.get("nextRecommendedNextLever") or "").strip()
        if candidate_next_lever in {
            RECOMMENDED_NEXT_LEVER_RETRAIN_TOUCHLINE_DETECTOR_CANDIDATE,
            RECOMMENDED_NEXT_LEVER_START_PHASE_1B_REVIEW_DENSIFICATION,
        }:
            next_recommended_next_lever = candidate_next_lever
    return {
        "reviewDensificationBatchName": review_densification_manifest.get("reviewDensificationBatchName")
        or review_densification_manifest.get("batchName"),
        "representativeFailingMatchId": review_densification_manifest.get("representativeFailingMatchId"),
        "representativeControlMatchId": review_densification_manifest.get("representativeControlMatchId"),
        "failingCurationUnitCount": _safe_int(review_densification_manifest.get("failingCurationUnitCount"), 0),
        "controlCurationUnitCount": _safe_int(review_densification_manifest.get("controlCurationUnitCount"), 0),
        "reviewItemCount": _safe_int(review_densification_manifest.get("reviewItemCount"), 0),
        "pendingReviewCount": _safe_int(review_densification_manifest.get("pendingReviewCount"), 0),
        "pendingFailingReviewCount": _safe_int(review_densification_manifest.get("pendingFailingReviewCount"), 0),
        "pendingControlReviewCount": _safe_int(review_densification_manifest.get("pendingControlReviewCount"), 0),
        "failingSourceReviewComplete": bool(review_densification_manifest.get("failingSourceReviewComplete")),
        "controlReviewComplete": bool(review_densification_manifest.get("controlReviewComplete")),
        "reviewedPositiveCount": _safe_int(review_densification_manifest.get("reviewedPositiveCount"), 0),
        "reviewedNegativeCount": _safe_int(review_densification_manifest.get("reviewedNegativeCount"), 0),
        "overlayValidationErrorCount": _safe_int(review_densification_manifest.get("overlayValidationErrorCount"), 0),
        "overlayValidationErrors": list(review_densification_manifest.get("overlayValidationErrors") or []),
        "sourceAwareSplitLeakageDetected": bool(split_manifest.get("sourceAwareSplitLeakageDetected")),
        "yoloExportRegenerated": bool(review_densification_manifest.get("yoloExportRegenerated")),
        "readyForRetraining": ready_for_retraining,
        "reviewDensificationPrimaryBlocker": primary_blocker,
        "seededIssueCount": _safe_int(review_bundle_report.get("seededIssueCount"), 0),
        "reviewBundleCount": _safe_int(review_bundle_report.get("reviewBundleCount"), 0),
        "nextRecommendedNextLever": next_recommended_next_lever,
        "batchOutcomeAnalysis": batch_outcome_analysis or None,
    }


def _load_existing_detector_training_payload(
    storage_root: Path,
) -> tuple[
    dict[str, object] | None,
    dict[str, object] | None,
    dict[str, object] | None,
    dict[str, object] | None,
]:
    candidates_root = Path(storage_root) / "trained_detector_candidates"
    candidate_roots: list[tuple[int, str, Path]] = []
    if candidates_root.exists():
        for child in candidates_root.iterdir():
            if not child.is_dir():
                continue
            version = _candidate_version(child.name)
            if version <= 0:
                continue
            candidate_roots.append((version, child.name, child))
    candidate_roots.sort(key=lambda item: (item[0], item[1]), reverse=True)
    artifact_root = candidate_roots[0][2] if candidate_roots else candidates_root / "touchline_detector_candidate_v1"
    payloads: list[dict[str, object] | None] = []
    for filename in (
        "training_run_summary.json",
        "training_config.json",
        "evaluation_contract.json",
        "batch_outcome_analysis.json",
    ):
        path = artifact_root / filename
        if not path.exists():
            payloads.append(None)
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payloads.append(None)
            continue
        payloads.append(payload if isinstance(payload, dict) else None)
    return payloads[0], payloads[1], payloads[2], payloads[3]


def _build_detector_training_diagnosis(
    training_run_summary: dict[str, object] | None,
    training_config: dict[str, object] | None,
    evaluation_contract: dict[str, object] | None,
    batch_outcome_analysis: dict[str, object] | None,
) -> dict[str, object] | None:
    if not isinstance(training_run_summary, dict):
        return None
    training_config = dict(training_config or {})
    evaluation_contract = dict(evaluation_contract or {})
    batch_outcome_analysis = dict(batch_outcome_analysis or {})
    training_recipe = (
        dict(training_config.get("trainingRecipe"))
        if isinstance(training_config.get("trainingRecipe"), dict)
        else {}
    )
    ready_for_detector_evaluation = bool(training_run_summary.get("readyForDetectorEvaluation"))
    next_recommended_next_lever = (
        RECOMMENDED_NEXT_LEVER_EVALUATE_TOUCHLINE_DETECTOR_CANDIDATE
        if ready_for_detector_evaluation
        else RECOMMENDED_NEXT_LEVER_RETRAIN_TOUCHLINE_DETECTOR_CANDIDATE
    )
    batch_next_lever = str(batch_outcome_analysis.get("nextRecommendedNextLever") or "").strip()
    if batch_next_lever in {
        RECOMMENDED_NEXT_LEVER_EVALUATE_TOUCHLINE_DETECTOR_CANDIDATE,
        RECOMMENDED_NEXT_LEVER_RETRAIN_TOUCHLINE_DETECTOR_CANDIDATE,
    }:
        next_recommended_next_lever = batch_next_lever
    return {
        "trainingCandidateName": training_run_summary.get("trainingCandidateName"),
        "trainingBatchName": training_run_summary.get("trainingBatchName"),
        "trainingCompleted": bool(training_run_summary.get("trainingCompleted")),
        "weightsReady": bool(training_run_summary.get("weightsReady")),
        "evaluationContractReady": bool(training_run_summary.get("evaluationContractReady")),
        "trainingPrimaryBlocker": training_run_summary.get("trainingPrimaryBlocker"),
        "readyForDetectorEvaluation": ready_for_detector_evaluation,
        "baseModelPath": training_run_summary.get("baseModelPath") or training_recipe.get("baseModelPath"),
        "heldOutSplitAssessment": training_run_summary.get("heldOutSplitAssessment")
        or training_config.get("validationAssessment"),
        "bestWeightsPath": training_run_summary.get("bestWeightsPath"),
        "resultsCsvPath": training_run_summary.get("resultsCsvPath"),
        "evaluationContractPathReady": bool(evaluation_contract.get("candidateReadyForEvaluation")),
        "nextRecommendedNextLever": next_recommended_next_lever,
        "requestedGpuId": training_run_summary.get("requestedGpuId"),
        "allocatedGpuId": training_run_summary.get("allocatedGpuId"),
        "remoteDeviceName": training_run_summary.get("remoteDeviceName"),
        "batchOutcomeAnalysis": batch_outcome_analysis or None,
    }


def _load_existing_detector_training_quality_gate_payload(
    storage_root: Path,
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    candidates_root = Path(storage_root) / "trained_detector_candidates"
    candidate_roots: list[tuple[int, str, Path]] = []
    if candidates_root.exists():
        for child in candidates_root.iterdir():
            if not child.is_dir():
                continue
            version = _candidate_version(child.name)
            if version <= 0:
                continue
            gate_root = child / "training_quality_gate_v1"
            if not gate_root.exists():
                continue
            candidate_roots.append((version, child.name, child))
    candidate_roots.sort(key=lambda item: (item[0], item[1]), reverse=True)
    if not candidate_roots:
        return None, None
    gate_root = candidate_roots[0][2] / "training_quality_gate_v1"
    payloads: list[dict[str, object] | None] = []
    for filename in ("quality_gate_summary.json", "batch_outcome_analysis.json"):
        path = gate_root / filename
        if not path.exists():
            payloads.append(None)
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payloads.append(None)
            continue
        payloads.append(payload if isinstance(payload, dict) else None)
    return payloads[0], payloads[1]


def _build_detector_training_quality_gate_diagnosis(
    quality_gate_summary: dict[str, object] | None,
    batch_outcome_analysis: dict[str, object] | None,
) -> dict[str, object] | None:
    if not isinstance(quality_gate_summary, dict):
        return None
    batch_outcome_analysis = dict(batch_outcome_analysis or {})
    next_recommended_next_lever = RECOMMENDED_NEXT_LEVER_EVALUATE_TOUCHLINE_DETECTOR_CANDIDATE
    batch_next_lever = str(batch_outcome_analysis.get("nextRecommendedNextLever") or "").strip()
    if batch_next_lever == RECOMMENDED_NEXT_LEVER_EVALUATE_TOUCHLINE_DETECTOR_CANDIDATE:
        next_recommended_next_lever = batch_next_lever
    return {
        "trainingCandidateName": quality_gate_summary.get("trainingCandidateName"),
        "trainingQualityGatePassed": bool(quality_gate_summary.get("trainingQualityGatePassed")),
        "trainingQualityGatePrimaryBlocker": quality_gate_summary.get("trainingQualityGatePrimaryBlocker"),
        "validationImageCount": _safe_int(quality_gate_summary.get("validationImageCount"), 0),
        "validationPositiveLabelImageCount": _safe_int(
            quality_gate_summary.get("validationPositiveLabelImageCount"),
            0,
        ),
        "validationEmptyLabelImageCount": _safe_int(
            quality_gate_summary.get("validationEmptyLabelImageCount"),
            0,
        ),
        "validationInformative": bool(quality_gate_summary.get("validationInformative")),
        "maxValidationPrecision": _safe_float(quality_gate_summary.get("maxValidationPrecision"), 0.0),
        "maxValidationRecall": _safe_float(quality_gate_summary.get("maxValidationRecall"), 0.0),
        "maxValidationMap50": _safe_float(quality_gate_summary.get("maxValidationMap50"), 0.0),
        "localPositiveSanityImageCount": _safe_int(quality_gate_summary.get("localPositiveSanityImageCount"), 0),
        "localPositiveSanityDetectedImageCount": _safe_int(
            quality_gate_summary.get("localPositiveSanityDetectedImageCount"),
            0,
        ),
        "readyForDetectorEvaluation": bool(quality_gate_summary.get("readyForDetectorEvaluation")),
        "goalAchieved": bool(batch_outcome_analysis.get("goalAchieved")),
        "roadmapAdvanceAllowed": bool(batch_outcome_analysis.get("roadmapAdvanceAllowed")),
        "nextRecommendedNextLever": next_recommended_next_lever,
        "batchOutcomeAnalysis": batch_outcome_analysis or None,
    }


def _load_existing_detector_candidate_data_quality_fix_payload(
    storage_root: Path,
) -> tuple[
    dict[str, object] | None,
    dict[str, object] | None,
    dict[str, object] | None,
    dict[str, object] | None,
]:
    artifact_root = Path(storage_root) / "training_prep" / "touchline_model_data_quality_fix_v1"
    payloads: list[dict[str, object] | None] = []
    for filename in (
        "data_quality_fix_manifest.json",
        "split_manifest.json",
        "review_bundle_report.json",
        "batch_outcome_analysis.json",
    ):
        path = artifact_root / filename
        if not path.exists():
            payloads.append(None)
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payloads.append(None)
            continue
        payloads.append(payload if isinstance(payload, dict) else None)
    return payloads[0], payloads[1], payloads[2], payloads[3]


def _build_detector_candidate_data_quality_fix_diagnosis(
    data_quality_fix_manifest: dict[str, object] | None,
    split_manifest: dict[str, object] | None,
    review_bundle_report: dict[str, object] | None,
    batch_outcome_analysis: dict[str, object] | None,
) -> dict[str, object] | None:
    if not isinstance(data_quality_fix_manifest, dict):
        return None
    split_manifest = dict(split_manifest or {})
    review_bundle_report = dict(review_bundle_report or {})
    batch_outcome_analysis = dict(batch_outcome_analysis or {})
    next_recommended_next_lever = RECOMMENDED_NEXT_LEVER_EVALUATE_TOUCHLINE_DETECTOR_CANDIDATE
    batch_next_lever = str(batch_outcome_analysis.get("nextRecommendedNextLever") or "").strip()
    if batch_next_lever == RECOMMENDED_NEXT_LEVER_EVALUATE_TOUCHLINE_DETECTOR_CANDIDATE:
        next_recommended_next_lever = batch_next_lever
    return {
        "trainingCandidateName": data_quality_fix_manifest.get("trainingCandidateName"),
        "dataQualityFixBatchName": data_quality_fix_manifest.get("dataQualityFixBatchName")
        or data_quality_fix_manifest.get("batchName"),
        "selectedNewFailingWindowCount": _safe_int(
            data_quality_fix_manifest.get("selectedNewFailingWindowCount"),
            0,
        ),
        "autoAcceptedPseudoLabelCount": _safe_int(
            data_quality_fix_manifest.get("autoAcceptedPseudoLabelCount"),
            0,
        ),
        "pendingFilteredReviewItemCount": _safe_int(
            data_quality_fix_manifest.get("pendingFilteredReviewItemCount"),
            0,
        ),
        "pendingRawReviewItemCount": _safe_int(
            data_quality_fix_manifest.get("pendingRawReviewItemCount"),
            0,
        ),
        "yoloExportReady": bool(data_quality_fix_manifest.get("yoloExportReady")),
        "trainingCompleted": bool(data_quality_fix_manifest.get("trainingCompleted")),
        "weightsReady": bool(data_quality_fix_manifest.get("weightsReady")),
        "readyForDetectorEvaluation": bool(data_quality_fix_manifest.get("readyForDetectorEvaluation")),
        "sourceAwareSplitLeakageDetected": bool(split_manifest.get("sourceAwareSplitLeakageDetected")),
        "seededIssueCount": _safe_int(review_bundle_report.get("seededIssueCount"), 0),
        "reviewBundleCount": _safe_int(review_bundle_report.get("reviewBundleCount"), 0),
        "goalAchieved": bool(batch_outcome_analysis.get("goalAchieved")),
        "roadmapAdvanceAllowed": bool(batch_outcome_analysis.get("roadmapAdvanceAllowed")),
        "nextRecommendedNextLever": next_recommended_next_lever,
        "batchOutcomeAnalysis": batch_outcome_analysis or None,
    }


def _load_existing_detector_candidate_proposal_signal_fix_payload(
    storage_root: Path,
) -> tuple[
    dict[str, object] | None,
    dict[str, object] | None,
    dict[str, object] | None,
]:
    training_prep_root = Path(storage_root) / "training_prep"

    def _proposal_fix_version(path: Path) -> int:
        suffix = path.name.rsplit("_v", 1)[-1]
        return _safe_int(suffix, 0)

    artifact_roots = sorted(
        (
            path
            for path in training_prep_root.glob("touchline_proposal_signal_generation_fix_v*")
            if path.is_dir()
        ),
        key=_proposal_fix_version,
        reverse=True,
    )
    for artifact_root in artifact_roots:
        payloads: list[dict[str, object] | None] = []
        for filename in (
            "proposal_signal_fix_manifest.json",
            "split_manifest.json",
            "batch_outcome_analysis.json",
        ):
            path = artifact_root / filename
            if not path.exists():
                payloads.append(None)
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payloads.append(None)
                continue
            payloads.append(payload if isinstance(payload, dict) else None)
        if isinstance(payloads[0], dict):
            return payloads[0], payloads[1], payloads[2]
    return None, None, None


def _build_detector_candidate_proposal_signal_fix_diagnosis(
    proposal_signal_fix_manifest: dict[str, object] | None,
    split_manifest: dict[str, object] | None,
    batch_outcome_analysis: dict[str, object] | None,
) -> dict[str, object] | None:
    if not isinstance(proposal_signal_fix_manifest, dict):
        return None
    split_manifest = dict(split_manifest or {})
    batch_outcome_analysis = dict(batch_outcome_analysis or {})
    next_recommended_next_lever = RECOMMENDED_NEXT_LEVER_EVALUATE_TOUCHLINE_DETECTOR_CANDIDATE
    batch_next_lever = str(batch_outcome_analysis.get("nextRecommendedNextLever") or "").strip()
    if batch_next_lever == RECOMMENDED_NEXT_LEVER_EVALUATE_TOUCHLINE_DETECTOR_CANDIDATE:
        next_recommended_next_lever = batch_next_lever
    return {
        "trainingCandidateName": proposal_signal_fix_manifest.get("trainingCandidateName"),
        "proposalSignalFixBatchName": proposal_signal_fix_manifest.get("proposalSignalFixBatchName")
        or proposal_signal_fix_manifest.get("batchName"),
        "windowFamily": proposal_signal_fix_manifest.get("windowFamily"),
        "proposalPositiveExampleCount": _safe_int(
            proposal_signal_fix_manifest.get("proposalPositiveExampleCount"),
            0,
        ),
        "proposalNegativeExampleCount": _safe_int(
            proposal_signal_fix_manifest.get("proposalNegativeExampleCount"),
            0,
        ),
        "positiveWindowKindCounts": dict(proposal_signal_fix_manifest.get("positiveWindowKindCounts") or {}),
        "negativeWindowKindCounts": dict(proposal_signal_fix_manifest.get("negativeWindowKindCounts") or {}),
        "proposalWindowValidationPositiveImageCount": _safe_int(
            proposal_signal_fix_manifest.get("proposalWindowValidationPositiveImageCount"),
            0,
        ),
        "proposalWindowSanityDetectedImageCount": _safe_int(
            proposal_signal_fix_manifest.get("proposalWindowSanityDetectedImageCount"),
            0,
        ),
        "fullFrameMeanRelativeBallArea": _safe_float(
            proposal_signal_fix_manifest.get("fullFrameMeanRelativeBallArea"),
            0.0,
        ),
        "meanRelativeBallAreaInProposalCrops": _safe_float(
            proposal_signal_fix_manifest.get("meanRelativeBallAreaInProposalCrops"),
            0.0,
        ),
        "sourceAwareSplitLeakageDetected": bool(split_manifest.get("sourceAwareSplitLeakageDetected")),
        "trainingCompleted": bool(proposal_signal_fix_manifest.get("trainingCompleted")),
        "weightsReady": bool(proposal_signal_fix_manifest.get("weightsReady")),
        "readyForDetectorEvaluation": bool(proposal_signal_fix_manifest.get("readyForDetectorEvaluation")),
        "goalAchieved": bool(batch_outcome_analysis.get("goalAchieved")),
        "roadmapAdvanceAllowed": bool(batch_outcome_analysis.get("roadmapAdvanceAllowed")),
        "nextRecommendedNextLever": next_recommended_next_lever,
        "batchOutcomeAnalysis": batch_outcome_analysis or None,
    }


def _load_existing_detector_candidate_validation_gate_remediation_payload(
    storage_root: Path,
) -> tuple[
    dict[str, object] | None,
    dict[str, object] | None,
    dict[str, object] | None,
]:
    artifact_root = Path(storage_root) / "training_prep" / "touchline_validation_gate_remediation_v1"
    payloads: list[dict[str, object] | None] = []
    for filename in (
        "validation_gate_remediation_manifest.json",
        "split_manifest.json",
        "batch_outcome_analysis.json",
    ):
        path = artifact_root / filename
        if not path.exists():
            payloads.append(None)
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payloads.append(None)
            continue
        payloads.append(payload if isinstance(payload, dict) else None)
    return payloads[0], payloads[1], payloads[2]


def _build_detector_candidate_validation_gate_remediation_diagnosis(
    validation_gate_remediation_manifest: dict[str, object] | None,
    split_manifest: dict[str, object] | None,
    batch_outcome_analysis: dict[str, object] | None,
) -> dict[str, object] | None:
    if not isinstance(validation_gate_remediation_manifest, dict):
        return None
    split_manifest = dict(split_manifest or {})
    batch_outcome_analysis = dict(batch_outcome_analysis or {})
    next_recommended_next_lever = RECOMMENDED_NEXT_LEVER_EVALUATE_TOUCHLINE_DETECTOR_CANDIDATE
    batch_next_lever = str(batch_outcome_analysis.get("nextRecommendedNextLever") or "").strip()
    if batch_next_lever == RECOMMENDED_NEXT_LEVER_EVALUATE_TOUCHLINE_DETECTOR_CANDIDATE:
        next_recommended_next_lever = batch_next_lever
    return {
        "trainingCandidateName": validation_gate_remediation_manifest.get("trainingCandidateName"),
        "validationGateRemediationBatchName": validation_gate_remediation_manifest.get(
            "validationGateRemediationBatchName"
        )
        or validation_gate_remediation_manifest.get("batchName"),
        "blockedCandidateName": validation_gate_remediation_manifest.get("blockedCandidateName"),
        "trainingQualityGatePassed": bool(validation_gate_remediation_manifest.get("trainingQualityGatePassed")),
        "trainingQualityGatePrimaryBlocker": validation_gate_remediation_manifest.get(
            "trainingQualityGatePrimaryBlocker"
        ),
        "selectedValidationPositiveCurationUnitId": validation_gate_remediation_manifest.get(
            "selectedValidationPositiveCurationUnitId"
        ),
        "validationImageCount": _safe_int(
            validation_gate_remediation_manifest.get("validationImageCount", split_manifest.get("validationImageCount")),
            0,
        ),
        "validationPositiveLabelImageCount": _safe_int(
            validation_gate_remediation_manifest.get(
                "validationPositiveLabelImageCount",
                split_manifest.get("validationPositiveLabelImageCount"),
            ),
            0,
        ),
        "validationEmptyLabelImageCount": _safe_int(
            validation_gate_remediation_manifest.get(
                "validationEmptyLabelImageCount",
                split_manifest.get("validationEmptyLabelImageCount"),
            ),
            0,
        ),
        "validationInformative": bool(
            validation_gate_remediation_manifest.get(
                "validationInformative",
                split_manifest.get("validationInformative"),
            )
        ),
        "sourceAwareSplitLeakageDetected": bool(split_manifest.get("sourceAwareSplitLeakageDetected")),
        "trainingCompleted": bool(validation_gate_remediation_manifest.get("trainingCompleted")),
        "weightsReady": bool(validation_gate_remediation_manifest.get("weightsReady")),
        "readyForDetectorEvaluation": bool(validation_gate_remediation_manifest.get("readyForDetectorEvaluation")),
        "goalAchieved": bool(batch_outcome_analysis.get("goalAchieved")),
        "roadmapAdvanceAllowed": bool(batch_outcome_analysis.get("roadmapAdvanceAllowed")),
        "nextRecommendedNextLever": next_recommended_next_lever,
        "batchOutcomeAnalysis": batch_outcome_analysis or None,
    }


def _load_existing_detector_candidate_evaluation_payload(output_dir: Path) -> dict[str, object] | None:
    evaluation_path = output_dir / "detector_candidate_evaluation.json"
    if not evaluation_path.exists():
        return None
    try:
        payload = json.loads(evaluation_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _build_detector_candidate_evaluation_diagnosis(payload: dict[str, object] | None) -> dict[str, object] | None:
    if not isinstance(payload, dict):
        return None
    batch_outcome_analysis = (
        dict(payload.get("batchOutcomeAnalysis")) if isinstance(payload.get("batchOutcomeAnalysis"), dict) else {}
    )
    return {
        "trainingCandidateName": payload.get("trainingCandidateName"),
        "evaluationBatchName": payload.get("evaluationBatchName"),
        "candidateWeightsPath": payload.get("candidateWeightsPath"),
        "screenCompleted": bool(payload.get("screenCompleted")),
        "screenWinningDetectorLabel": payload.get("screenWinningDetectorLabel"),
        "candidateBaselineProofRan": bool(payload.get("candidateBaselineProofRan")),
        "candidateBaselineProductBeatsPlateau": bool(payload.get("candidateBaselineProductBeatsPlateau")),
        "baselineControlProofRan": bool(payload.get("baselineControlProofRan")),
        "candidateCompoundThinProofRan": bool(payload.get("candidateCompoundThinProofRan")),
        "candidateCompoundThinProductBeatsPlateau": bool(payload.get("candidateCompoundThinProductBeatsPlateau")),
        "candidateBeatsSameBatchBaselineControl": bool(payload.get("candidateBeatsSameBatchBaselineControl")),
        "evaluationPrimaryBlocker": payload.get("evaluationPrimaryBlocker"),
        "readyForPromotion": bool(payload.get("readyForPromotion")),
        "phase1BDensificationRecommended": bool(payload.get("phase1BDensificationRecommended")),
        "nextRecommendedNextLever": payload.get("nextRecommendedNextLever"),
        "batchOutcomeAnalysis": batch_outcome_analysis or None,
    }


def _load_existing_detector_candidate_promotion_payload(output_dir: Path) -> dict[str, object] | None:
    promotion_path = output_dir / "detector_candidate_promotion.json"
    if not promotion_path.exists():
        return None
    try:
        payload = json.loads(promotion_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _build_detector_candidate_promotion_diagnosis(payload: dict[str, object] | None) -> dict[str, object] | None:
    if not isinstance(payload, dict):
        return None
    batch_outcome_analysis = (
        dict(payload.get("batchOutcomeAnalysis")) if isinstance(payload.get("batchOutcomeAnalysis"), dict) else {}
    )
    return {
        "trainingCandidateName": payload.get("trainingCandidateName"),
        "promotionBatchName": payload.get("promotionBatchName"),
        "promotionValidated": bool(payload.get("promotionValidated")),
        "promotedForControlledRuns": bool(payload.get("promotedForControlledRuns")),
        "runtimeDefaultChanged": bool(payload.get("runtimeDefaultChanged")),
        "runtimeDefaultChangeAllowed": bool(payload.get("runtimeDefaultChangeAllowed")),
        "runtimeDefaultChangeBlockers": list(payload.get("runtimeDefaultChangeBlockers") or []),
        "candidateBaselineProductBeatsPlateau": bool(payload.get("candidateBaselineProductBeatsPlateau")),
        "baselineControlProofRan": bool(payload.get("baselineControlProofRan")),
        "candidateBeatsSameBatchBaselineControl": bool(payload.get("candidateBeatsSameBatchBaselineControl")),
        "nextRecommendedNextLever": payload.get("nextRecommendedNextLever"),
        "batchOutcomeAnalysis": batch_outcome_analysis or None,
    }


def _load_existing_promoted_detector_candidate_robustness_validation_payload(
    output_dir: Path,
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    validation_root = output_dir / "promoted_touchline_detector_candidate_robustness_validation_v1"
    payloads: list[dict[str, object] | None] = []
    for filename in ("validation_summary.json", "batch_outcome_analysis.json"):
        path = validation_root / filename
        if not path.exists():
            payloads.append(None)
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payloads.append(None)
            continue
        payloads.append(payload if isinstance(payload, dict) else None)
    return payloads[0], payloads[1]


def _build_promoted_detector_candidate_robustness_diagnosis(
    validation_summary: dict[str, object] | None,
    batch_outcome_analysis: dict[str, object] | None,
) -> dict[str, object] | None:
    if not isinstance(validation_summary, dict):
        return None
    batch_outcome_analysis = dict(batch_outcome_analysis or {})
    return {
        "validationBatchName": validation_summary.get("validationBatchName"),
        "trainingCandidateName": validation_summary.get("trainingCandidateName"),
        "evaluatedArmNames": list(validation_summary.get("evaluatedArmNames") or []),
        "winningArmName": validation_summary.get("winningArmName"),
        "winningConfigOutcome": validation_summary.get("winningConfigOutcome"),
        "winningPassedPromotionGate": bool(validation_summary.get("winningPassedPromotionGate")),
        "winningPromotionBlockers": list(validation_summary.get("winningPromotionBlockers") or []),
        "winningFailingSourceEdgeShareImprovement": _safe_float(
            validation_summary.get("winningFailingSourceEdgeShareImprovement"),
            0.0,
        ),
        "runtimeDefaultChanged": False,
        "goalAchieved": bool(batch_outcome_analysis.get("goalAchieved", validation_summary.get("goalAchieved"))),
        "roadmapAdvanceAllowed": bool(
            batch_outcome_analysis.get(
                "roadmapAdvanceAllowed",
                validation_summary.get("roadmapAdvanceAllowed"),
            )
        ),
        "nextRecommendedNextLever": batch_outcome_analysis.get("nextRecommendedNextLever")
        or validation_summary.get("nextRecommendedNextLever"),
        "batchOutcomeAnalysis": batch_outcome_analysis or None,
    }


def _load_existing_promoted_detector_candidate_retention_delta_analysis_payload(
    output_dir: Path,
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    analysis_root = output_dir / "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
    payloads: list[dict[str, object] | None] = []
    for filename in ("retention_delta_summary.json", "batch_outcome_analysis.json"):
        path = analysis_root / filename
        if not path.exists():
            payloads.append(None)
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payloads.append(None)
            continue
        payloads.append(payload if isinstance(payload, dict) else None)
    return payloads[0], payloads[1]


def _build_promoted_detector_candidate_retention_delta_diagnosis(
    retention_delta_summary: dict[str, object] | None,
    batch_outcome_analysis: dict[str, object] | None,
) -> dict[str, object] | None:
    if not isinstance(retention_delta_summary, dict):
        return None
    batch_outcome_analysis = dict(batch_outcome_analysis or {})
    return {
        "analysisBatchName": retention_delta_summary.get("analysisBatchName"),
        "trainingCandidateName": retention_delta_summary.get("trainingCandidateName"),
        "winningArmName": retention_delta_summary.get("winningArmName"),
        "primaryRetentionBlockerClass": retention_delta_summary.get("primaryRetentionBlockerClass"),
        "acceptedRetentionRatio": retention_delta_summary.get("acceptedRetentionRatio"),
        "controlledRetentionRatio": retention_delta_summary.get("controlledRetentionRatio"),
        "selectedClusterStepImplicated": bool(retention_delta_summary.get("selectedClusterStepImplicated")),
        "nextImplementationBatchRecommendation": retention_delta_summary.get(
            "nextImplementationBatchRecommendation"
        ),
        "goalAchieved": bool(batch_outcome_analysis.get("goalAchieved", retention_delta_summary.get("goalAchieved"))),
        "roadmapAdvanceAllowed": bool(
            batch_outcome_analysis.get(
                "roadmapAdvanceAllowed",
                retention_delta_summary.get("roadmapAdvanceAllowed"),
            )
        ),
        "nextRecommendedNextLever": batch_outcome_analysis.get("nextRecommendedNextLever")
        or retention_delta_summary.get("nextRecommendedNextLever"),
        "batchOutcomeAnalysis": batch_outcome_analysis or None,
    }


def _load_existing_detector_candidate_failure_analysis_payload(
    storage_root: Path,
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    candidates_root = Path(storage_root) / "trained_detector_candidates"
    candidate_roots: list[tuple[int, str, Path]] = []
    if candidates_root.exists():
        for child in candidates_root.iterdir():
            if not child.is_dir():
                continue
            version = _candidate_version(child.name)
            if version <= 0:
                continue
            candidate_roots.append((version, child.name, child))
    candidate_roots.sort(key=lambda item: (item[0], item[1]), reverse=True)
    artifact_root = candidate_roots[0][2] if candidate_roots else candidates_root / "touchline_detector_candidate_v1"
    failure_analysis_root = artifact_root / "failure_analysis_v1"
    payloads: list[dict[str, object] | None] = []
    for filename in ("failure_analysis_summary.json", "batch_outcome_analysis.json"):
        path = failure_analysis_root / filename
        if not path.exists():
            payloads.append(None)
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payloads.append(None)
            continue
        payloads.append(payload if isinstance(payload, dict) else None)
    return payloads[0], payloads[1]


def _build_detector_candidate_failure_analysis_diagnosis(
    failure_analysis_summary: dict[str, object] | None,
    batch_outcome_analysis: dict[str, object] | None,
) -> dict[str, object] | None:
    if not isinstance(failure_analysis_summary, dict):
        return None
    batch_outcome_analysis = dict(batch_outcome_analysis or {})
    return {
        "trainingCandidateName": failure_analysis_summary.get("trainingCandidateName"),
        "previousCandidateName": failure_analysis_summary.get("previousCandidateName"),
        "failureAnalysisBatchName": failure_analysis_summary.get("failureAnalysisBatchName"),
        "screenWinningDetectorLabel": failure_analysis_summary.get("screenWinningDetectorLabel"),
        "candidateScreenViable": bool(failure_analysis_summary.get("candidateScreenViable")),
        "candidateRawProbeRowCount": _safe_int(failure_analysis_summary.get("candidateRawProbeRowCount"), 0),
        "candidateFilteredProbeRowCount": _safe_int(
            failure_analysis_summary.get("candidateFilteredProbeRowCount"),
            0,
        ),
        "candidateAcceptedBallFrameCount": _safe_int(
            failure_analysis_summary.get("candidateAcceptedBallFrameCount"),
            0,
        ),
        "baselineRawProbeRowCount": _safe_int(failure_analysis_summary.get("baselineRawProbeRowCount"), 0),
        "baselineFilteredProbeRowCount": _safe_int(
            failure_analysis_summary.get("baselineFilteredProbeRowCount"),
            0,
        ),
        "baselineAcceptedBallFrameCount": _safe_int(
            failure_analysis_summary.get("baselineAcceptedBallFrameCount"),
            0,
        ),
        "candidateMaxProposalDetectedFramesAcrossProfiles": _safe_int(
            failure_analysis_summary.get("candidateMaxProposalDetectedFramesAcrossProfiles"),
            0,
        ),
        "previousCandidateMaxProposalDetectedFramesAcrossProfiles": _safe_int(
            failure_analysis_summary.get("previousCandidateMaxProposalDetectedFramesAcrossProfiles"),
            0,
        ),
        "baselineMaxProposalDetectedFramesAcrossProfiles": _safe_int(
            failure_analysis_summary.get("baselineMaxProposalDetectedFramesAcrossProfiles"),
            0,
        ),
        "rootCauseClass": failure_analysis_summary.get("rootCauseClass"),
        "changeFromPreviousCandidateClass": failure_analysis_summary.get("changeFromPreviousCandidateClass"),
        "recommendedFixClass": failure_analysis_summary.get("recommendedFixClass"),
        "recommendedFixFocus": (
            batch_outcome_analysis.get("recommendedFixFocus")
            or failure_analysis_summary.get("recommendedFixFocus")
        ),
        "summarySurfaceDriftDetected": bool(
            batch_outcome_analysis.get(
                "summarySurfaceDriftDetected",
                failure_analysis_summary.get("summarySurfaceDriftDetected"),
            )
        ),
        "calibrationSuspicionDetected": bool(
            batch_outcome_analysis.get(
                "calibrationSuspicionDetected",
                failure_analysis_summary.get("calibrationSuspicionDetected"),
            )
        ),
        "nextImplementationBatchRecommendation": (
            batch_outcome_analysis.get("nextImplementationBatchRecommendation")
            or failure_analysis_summary.get("nextImplementationBatchRecommendation")
        ),
        "goalAchieved": bool(
            batch_outcome_analysis.get("goalAchieved", failure_analysis_summary.get("goalAchieved"))
        ),
        "roadmapAdvanceAllowed": bool(
            batch_outcome_analysis.get(
                "roadmapAdvanceAllowed",
                failure_analysis_summary.get("roadmapAdvanceAllowed"),
            )
        ),
        "nextRecommendedNextLever": batch_outcome_analysis.get("nextRecommendedNextLever")
        or failure_analysis_summary.get("nextRecommendedNextLever"),
        "batchOutcomeAnalysis": batch_outcome_analysis or None,
    }


def _load_controlled_frame_ids(storage: Storage, match_id: str) -> set[int]:
    accepted_match_state = load_accepted_match_state(storage, match_id)
    if isinstance(accepted_match_state, dict):
        raw_state_frames = accepted_match_state.get("frames")
        if isinstance(raw_state_frames, list):
            controlled_frame_ids = {
                _safe_int(item.get("frameId"), default=-1)
                for item in raw_state_frames
                if isinstance(item, dict) and item.get("mode") == "controlled_possession"
            }
            controlled_frame_ids.discard(-1)
            if controlled_frame_ids:
                return controlled_frame_ids

    _, assignments, _, _ = storage.load_analytics(match_id)
    return {
        int(assignment.frameId)
        for assignment in assignments
        if assignment.team in {"my_team", "enemy"} and assignment.trackId is not None
    }


def _load_player_rows(storage: Storage, match_id: str) -> list[dict[str, object]]:
    return [
        dict(row)
        for row in storage.load_raw_rows(match_id)
        if isinstance(row, dict) and row.get("Entity_Type") != "ball" and _extract_frame_id(row) is not None
    ]


def _infer_sample_interval_from_rows(rows: list[dict[str, object]]) -> int:
    frame_ids = sorted(
        {
            frame_id
            for frame_id in (_extract_frame_id(row) for row in rows)
            if frame_id is not None and frame_id >= 0
        }
    )
    if len(frame_ids) < 2:
        return 1
    deltas = [
        current - previous
        for previous, current in zip(frame_ids, frame_ids[1:])
        if current > previous
    ]
    if not deltas:
        return 1
    interval = deltas[0]
    for delta in deltas[1:]:
        interval = delta if interval == 0 else gcd(interval, delta)
    return max(interval, 1)


def _build_projection_row(
    storage: Storage,
    entry: dict[str, object],
    summary: object,
    *,
    config_name: str,
    retained_rows: list[dict[str, object]],
    repair_diagnostics: dict[str, object],
    replacement_diagnostics: dict[str, object],
    acquisition_diagnostics: dict[str, object],
    controlled_frame_ids: set[int],
) -> dict[str, object]:
    source_clip_id = str(entry.get("sourceClipId") or "")
    retained_frame_ids = {
        frame_id
        for frame_id in (_extract_frame_id(row) for row in retained_rows)
        if frame_id is not None and frame_id >= 0
    }
    projected_controlled_frames = len(retained_frame_ids & controlled_frame_ids)
    accepted_ball_frames = len(retained_rows)
    accepted_ball_ratio = (accepted_ball_frames / int(summary.frameCount)) if int(summary.frameCount) else 0.0
    controlled_possession_ratio = (
        projected_controlled_frames / int(summary.frameCount)
        if int(summary.frameCount)
        else 0.0
    )
    baseline_accepted_ball_frames = max(int(summary.acceptedBallFrames), 1)
    baseline_controlled_frames = max(int(summary.controlledPossessionFrames), 1)
    accepted_retention_ratio = accepted_ball_frames / baseline_accepted_ball_frames
    controlled_retention_ratio = projected_controlled_frames / baseline_controlled_frames
    (
        _projected_path_length,
        edge_frame_share,
        _shows_meaningful_motion,
        ball_track_viable,
    ) = summarize_ball_rows(retained_rows)

    observed_ball_frames = min(
        int(summary.observedBallFrames) or accepted_ball_frames,
        accepted_ball_frames,
    )
    accepted_from_observed_baseline = int(summary.acceptedFromObservedFrames) or min(
        int(summary.observedBallFrames),
        int(summary.acceptedBallFrames),
    )
    accepted_from_observed_frames = min(accepted_from_observed_baseline or accepted_ball_frames, accepted_ball_frames)
    accepted_from_observed_ratio = (
        accepted_from_observed_frames / accepted_ball_frames if accepted_ball_frames else 0.0
    )
    inferred_ball_frames = max(0, accepted_ball_frames - observed_ball_frames)
    five_minute_truth_ready, _forty_five_minute_truth_ready, truth_gate_reasons, _dominant_event_share = assess_truth_gates(
        requires_team_selection=bool(summary.requiresTeamSelection),
        tracked_possession_frames=int(summary.trackedPossessionFrames),
        frame_count=int(summary.frameCount),
        raw_row_count=int(summary.rawRowCount),
        with_ball_frames=int(summary.withBallFrames),
        ball_track_viable=ball_track_viable,
        controlled_possession_frames=projected_controlled_frames,
        event_types=dict(summary.eventTypes),
        observed_ball_frames=observed_ball_frames,
        inferred_ball_frames=inferred_ball_frames,
        accepted_ball_frames=accepted_ball_frames,
        accepted_from_observed_frames=accepted_from_observed_frames,
        accepted_from_observed_ratio=accepted_from_observed_ratio,
        direct_observation_breakdown_present=_direct_observation_breakdown_present(storage, str(entry.get("matchId"))),
        accepted_ball_ratio=accepted_ball_ratio,
        ball_truth_layers_present=True,
    )

    return {
        "configName": config_name,
        "entryId": entry.get("entryId"),
        "matchId": entry.get("matchId"),
        "label": entry.get("label"),
        "sourceClipId": source_clip_id,
        "status": "success",
        "acceptedBallFrames": accepted_ball_frames,
        "acceptedBallRatio": round(float(accepted_ball_ratio), 3),
        "controlledPossessionFrames": projected_controlled_frames,
        "controlledPossessionRatio": round(float(controlled_possession_ratio), 3),
        "ballTrackViable": bool(ball_track_viable),
        "ballTrackEdgeFrameShare": round(float(edge_frame_share), 3),
        "fiveMinuteTruthReady": bool(five_minute_truth_ready),
        "truthGateReasons": truth_gate_reasons,
        "acceptedBallFrameDelta": accepted_ball_frames - int(summary.acceptedBallFrames),
        "controlledPossessionFrameDelta": projected_controlled_frames - int(summary.controlledPossessionFrames),
        "acceptedRetentionRatio": round(float(accepted_retention_ratio), 3),
        "controlledRetentionRatio": round(float(controlled_retention_ratio), 3),
        "edgeShareImprovement": round(float(summary.ballTrackEdgeFrameShare) - float(edge_frame_share), 3),
        "edgeRunThinningApplied": _safe_int(repair_diagnostics.get("thinnedEdgeRuns"), 0) > 0,
        "thinnedEdgeRuns": _safe_int(repair_diagnostics.get("thinnedEdgeRuns"), 0),
        "droppedAcceptedEdgeFrames": _safe_int(repair_diagnostics.get("droppedAcceptedEdgeFrames"), 0),
        "retainedAcceptedEdgeFrames": _safe_int(repair_diagnostics.get("retainedAcceptedEdgeFrames"), 0),
        "preservedBoundaryFrames": _safe_int(repair_diagnostics.get("preservedBoundaryFrames"), 0),
        "preservedSupportedFrames": _safe_int(repair_diagnostics.get("preservedSupportedFrames"), 0),
        "preservedBridgeFrames": _safe_int(repair_diagnostics.get("preservedBridgeFrames"), 0),
        "droppedInteriorUnsupportedFrames": _safe_int(
            repair_diagnostics.get("droppedInteriorUnsupportedFrames"),
            0,
        ),
        "supportedAcceptedBallRatio": round(
            _safe_float(repair_diagnostics.get("supportedAcceptedBallRatio"), 0.0),
            3,
        ),
        "unsupportedAcceptedEdgeFrames": _safe_int(repair_diagnostics.get("unsupportedAcceptedEdgeFrames"), 0),
        "replacementRunsConsidered": _safe_int(replacement_diagnostics.get("runsConsidered"), 0),
        "replacementRunsAccepted": _safe_int(replacement_diagnostics.get("runsAccepted"), 0),
        "replacementRunsRejected": _safe_int(replacement_diagnostics.get("runsRejected"), 0),
        "medianReplacementCoverageRatio": round(
            _safe_float(replacement_diagnostics.get("medianReplacementCoverageRatio"), 0.0),
            3,
        ),
        "replacementRejectionBlockerCounts": dict(
            replacement_diagnostics.get("replacementRejectionReasonCounts", {})
            if isinstance(replacement_diagnostics.get("replacementRejectionReasonCounts"), dict)
            else {}
        ),
        "acquisitionWindowKindCounts": dict(
            acquisition_diagnostics.get("proposalWindowKindSelectedCounts", {})
            if isinstance(acquisition_diagnostics.get("proposalWindowKindSelectedCounts"), dict)
            else {}
        ),
        "acquisitionTouchlineCandidateModeEntered": bool(
            acquisition_diagnostics.get("touchlineCandidateModeEntered", False)
        ),
        "acquisitionTouchlineEscapeWindowFrames": _safe_int(
            acquisition_diagnostics.get("touchlineEscapeWindowFrames"),
            0,
        ),
        "acquisitionTouchlineInboardWindowFrames": _safe_int(
            acquisition_diagnostics.get("touchlineInboardWindowFrames"),
            0,
        ),
        "acquisitionRejectionBlockerCounts": dict(
            acquisition_diagnostics.get("edgeStuckCandidateRejectionCounts", {})
            if isinstance(acquisition_diagnostics.get("edgeStuckCandidateRejectionCounts"), dict)
            else {}
        ),
        "acquisitionZeroTouchlineCandidateReasonCounts": dict(
            acquisition_diagnostics.get("zeroTouchlineCandidateReasonCounts", {})
            if isinstance(acquisition_diagnostics.get("zeroTouchlineCandidateReasonCounts"), dict)
            else {}
        ),
        "acquisitionTouchlineEscapeCandidateFrames": _safe_int(
            acquisition_diagnostics.get("touchlineEscapeCandidateFrames"),
            0,
        ),
        "acquisitionTouchlineEscapeSelectedFrames": _safe_int(
            acquisition_diagnostics.get("touchlineEscapeSelectedFrames"),
            0,
        ),
        "acquisitionReopenedRawCandidateFrames": _safe_int(
            acquisition_diagnostics.get("reopenedRawCandidateFrames"),
            0,
        ),
        "acquisitionReopenedRawCandidateSelectedFrames": _safe_int(
            acquisition_diagnostics.get("reopenedRawCandidateSelectedFrames"),
            0,
        ),
        "acquisitionRepeatedAnchorSuppressionCount": _safe_int(
            acquisition_diagnostics.get("repeatedAnchorSuppressionCount"),
            0,
        ),
        "acquisitionCandidateEdgeShareBeforeSelection": round(
            _safe_float(acquisition_diagnostics.get("candidateSourceEdgeShareBeforeSelection"), 0.0),
            3,
        ),
        "acquisitionCandidateEdgeShareAfterSelection": round(
            _safe_float(acquisition_diagnostics.get("candidateSourceEdgeShareAfterSelection"), 0.0),
            3,
        ),
    }


def _baseline_projection_row(storage: Storage, entry: dict[str, object], summary: object) -> dict[str, object]:
    match_id = str(entry.get("matchId"))
    accepted_rows = _load_accepted_ball_rows(storage, match_id)
    player_rows = _load_player_rows(storage, match_id)
    probe_filtered_rows, probe_raw_rows = _load_probe_observed_rows(storage, match_id)
    stored_acquisition_diagnostics = _load_source_conditioned_acquisition_diagnostics(storage, match_id)
    repair_diagnostics = {
        "thinnedEdgeRuns": 0,
        "droppedAcceptedEdgeFrames": 0,
        "retainedAcceptedEdgeFrames": 0,
        "preservedBoundaryFrames": 0,
        "preservedSupportedFrames": 0,
        "preservedBridgeFrames": 0,
        "droppedInteriorUnsupportedFrames": 0,
        "supportedAcceptedBallRatio": 0.0,
        "unsupportedAcceptedEdgeFrames": 0,
    }
    replacement_diagnostics = {
        "runsConsidered": 0,
        "runsAccepted": 0,
        "runsRejected": 0,
        "medianReplacementCoverageRatio": 0.0,
        "replacementRejectionReasonCounts": {},
    }
    acquisition_diagnostics = dict(stored_acquisition_diagnostics or {})
    retained_rows = accepted_rows
    if accepted_rows:
        retained_rows, repair_diagnostics, replacement_diagnostics = apply_source_conditioned_edge_share_repair(
            accepted_rows,
            source_clip_id=str(entry.get("sourceClipId") or ""),
            edge_share_repair_profile=None,
            player_rows=player_rows,
            sample_interval=_infer_sample_interval_from_rows(accepted_rows),
            probe_filtered_rows=probe_filtered_rows,
            probe_raw_rows=probe_raw_rows,
        )
    return _build_projection_row(
        storage,
        entry,
        summary,
        config_name=BASELINE_CONFIG_NAME,
        retained_rows=retained_rows,
        repair_diagnostics=repair_diagnostics,
        replacement_diagnostics=replacement_diagnostics,
        acquisition_diagnostics=acquisition_diagnostics,
        controlled_frame_ids=_load_controlled_frame_ids(storage, match_id),
    )


def _shadow_projection_row(
    storage: Storage,
    entry: dict[str, object],
    summary: object,
    *,
    config_name: str,
) -> dict[str, object]:
    match_id = str(entry.get("matchId"))
    accepted_rows = _load_accepted_ball_rows(storage, match_id)
    player_rows = _load_player_rows(storage, match_id)
    probe_filtered_rows, probe_raw_rows = _load_probe_observed_rows(storage, match_id)
    stored_acquisition_diagnostics = _load_source_conditioned_acquisition_diagnostics(storage, match_id)
    repair_diagnostics = {
        "thinnedEdgeRuns": 0,
        "droppedAcceptedEdgeFrames": 0,
        "retainedAcceptedEdgeFrames": 0,
        "preservedBoundaryFrames": 0,
        "preservedSupportedFrames": 0,
        "preservedBridgeFrames": 0,
        "droppedInteriorUnsupportedFrames": 0,
        "supportedAcceptedBallRatio": 0.0,
        "unsupportedAcceptedEdgeFrames": 0,
    }
    replacement_diagnostics = {
        "runsConsidered": 0,
        "runsAccepted": 0,
        "runsRejected": 0,
        "medianReplacementCoverageRatio": 0.0,
        "replacementRejectionReasonCounts": {},
    }
    config_mode = str(SHADOW_CONFIGS.get(config_name, {}).get("mode") or "")
    acquisition_diagnostics = (
        dict(stored_acquisition_diagnostics or {})
        if config_mode == "touchline_acquisition_upgrade"
        and isinstance(stored_acquisition_diagnostics, dict)
        and str(stored_acquisition_diagnostics.get("profileName") or "") == config_name
        else {
            "proposalWindowKindSelectedCounts": {},
            "touchlineCandidateModeEntered": False,
            "touchlineEscapeWindowFrames": 0,
            "touchlineInboardWindowFrames": 0,
            "edgeStuckCandidateRejectionCounts": {},
            "zeroTouchlineCandidateReasonCounts": {},
            "touchlineEscapeCandidateFrames": 0,
            "touchlineEscapeSelectedFrames": 0,
            "reopenedRawCandidateFrames": 0,
            "reopenedRawCandidateSelectedFrames": 0,
            "repeatedAnchorSuppressionCount": 0,
            "candidateSourceEdgeShareBeforeSelection": 0.0,
            "candidateSourceEdgeShareAfterSelection": 0.0,
        }
    )
    retained_rows = accepted_rows
    acquisition_mode = str(SHADOW_CONFIGS.get(config_name, {}).get("mode") or "")
    if accepted_rows and acquisition_mode not in {
        "touchline_acquisition_upgrade",
        "touchline_acquisition_reopen",
        "touchline_candidate_admission_reopen",
    }:
        retained_rows, repair_diagnostics, replacement_diagnostics = apply_source_conditioned_edge_share_repair(
            accepted_rows,
            source_clip_id=str(entry.get("sourceClipId") or ""),
            edge_share_repair_profile=config_name,
            player_rows=player_rows,
            sample_interval=_infer_sample_interval_from_rows(accepted_rows),
            probe_filtered_rows=probe_filtered_rows,
            probe_raw_rows=probe_raw_rows,
        )
    elif config_mode in {
        "touchline_acquisition_upgrade",
        "touchline_acquisition_reopen",
        "touchline_candidate_admission_reopen",
    }:
        replayed_rows, replayed_acquisition_diagnostics = _replay_source_conditioned_acquisition_projection(
            storage=storage,
            entry=entry,
            config_name=config_name,
        )
        stored_matches_profile = bool(
            isinstance(stored_acquisition_diagnostics, dict)
            and str(stored_acquisition_diagnostics.get("profileName") or "") == config_name
        )
        replay_has_touchline_signal = bool(
            _safe_int(replayed_acquisition_diagnostics.get("touchlineEscapeCandidateFrames"), 0) > 0
            or _safe_int(replayed_acquisition_diagnostics.get("touchlineInboardWindowFrames"), 0) > 0
            or _safe_int(replayed_acquisition_diagnostics.get("reopenedRawCandidateFrames"), 0) > 0
        )
        if stored_matches_profile and not replay_has_touchline_signal:
            retained_rows = accepted_rows
            acquisition_diagnostics = dict(stored_acquisition_diagnostics or {})
        else:
            retained_rows = replayed_rows
            acquisition_diagnostics = replayed_acquisition_diagnostics
    return _build_projection_row(
        storage,
        entry,
        summary,
        config_name=config_name,
        retained_rows=retained_rows,
        repair_diagnostics=repair_diagnostics,
        replacement_diagnostics=replacement_diagnostics,
        acquisition_diagnostics=acquisition_diagnostics,
        controlled_frame_ids=_load_controlled_frame_ids(storage, match_id),
    )


def _load_canonical_proof_floor(proof_summary_path: Path) -> dict[str, object]:
    payload = build_canonical_proof_summary(json.loads(Path(proof_summary_path).read_text(encoding="utf-8")))
    accepted_ball_frames = _safe_int(payload.get("acceptedBallFrames"), 0)
    controlled_possession_frames = _safe_int(payload.get("controlledPossessionFrames"), 0)
    ball_track_viable = bool(payload.get("ballTrackViable"))
    ball_track_edge_frame_share = round(_safe_float(payload.get("ballTrackEdgeFrameShare"), 0.0), 3)
    return {
        "acceptedBallFrames": accepted_ball_frames,
        "controlledPossessionFrames": controlled_possession_frames,
        "ballTrackViable": ball_track_viable,
        "ballTrackEdgeFrameShare": ball_track_edge_frame_share,
        "intact": (
            accepted_ball_frames >= 174
            and controlled_possession_frames >= 137
            and ball_track_viable
            and ball_track_edge_frame_share <= 0.586
        ),
    }


def _source_robustness_config_preference(config_name: str | None) -> tuple[int, int, str]:
    if not isinstance(config_name, str):
        return (0, 0, "")
    keep_every, min_run_length = _parse_config_preference_spec(config_name)
    return (
        min_run_length,
        -keep_every,
        config_name,
    )


def _config_truth_gate_counts(rows: list[dict[str, object]]) -> dict[str, int]:
    truth_gate_counts: Counter[str] = Counter()
    for row in rows:
        for reason in row.get("truthGateReasons", []):
            if isinstance(reason, str) and reason.strip():
                truth_gate_counts[reason] += 1
    return dict(sorted(truth_gate_counts.items(), key=lambda item: (-item[1], item[0])))


def _primary_truth_gate_reason(truth_gate_counts: dict[str, int]) -> str | None:
    if not truth_gate_counts:
        return None
    return min(
        truth_gate_counts.items(),
        key=lambda item: (-item[1], item[0]),
    )[0]


def _aggregate_count_mapping(rows: list[dict[str, object]], field_name: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        value = row.get(field_name)
        if not isinstance(value, dict):
            continue
        for key, raw_count in value.items():
            if not isinstance(key, str) or not key.strip():
                continue
            counts[key] += _safe_int(raw_count, 0)
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _top_edge_runs(edge_runs: list[dict[str, int]], *, limit: int = 3) -> list[dict[str, int]]:
    ranked_runs = sorted(
        (
            {
                "startFrame": _safe_int(run.get("startFrame"), 0),
                "endFrame": _safe_int(run.get("endFrame"), 0),
                "runLength": _safe_int(run.get("runLength"), 0),
                "keptFrameCount": _safe_int(run.get("keptFrameCount"), 0),
                "droppedFrameCount": _safe_int(run.get("droppedFrameCount"), 0),
            }
            for run in edge_runs
            if isinstance(run, dict)
        ),
        key=lambda run: (-run["runLength"], run["startFrame"], run["endFrame"]),
    )
    return ranked_runs[:limit]


def _build_compact_source_robustness_fields(
    *,
    source_robustness_active_config_name: str,
    source_robustness_best_config_name: str | None,
    source_robustness_best_exploratory_config_name: str | None,
    final_outcome: dict[str, object],
    dominant_failure_signal: str,
    improved_source_clip_id: str | None,
) -> dict[str, object]:
    return {
        "sourceRobustnessActiveConfigName": source_robustness_active_config_name,
        "sourceRobustnessBestConfigName": source_robustness_best_config_name,
        "sourceRobustnessBestExploratoryConfigName": source_robustness_best_exploratory_config_name,
        "sourceRobustnessOutcome": final_outcome["sourceRobustnessOutcome"],
        "sourceRobustnessDominantFailureSignal": dominant_failure_signal,
        "sourceRobustnessImprovedSourceClipId": improved_source_clip_id,
        "sourceRobustnessRecommendedNextLever": final_outcome["sourceRobustnessRecommendedNextLever"],
        "sourceRobustnessPromotionBlockers": list(final_outcome.get("promotionBlockers", [])),
    }


def _build_snapshot_config_payload(
    *,
    config_name: str,
    config_summaries: dict[str, dict[str, object]],
    config_source_summaries: dict[str, dict[str, dict[str, object]]],
    config_outcomes: dict[str, dict[str, object]],
    failing_source_clip_id: str,
    comparison_source_clip_id: str,
) -> dict[str, object]:
    config_summary = config_summaries[config_name]
    source_summaries = config_source_summaries[config_name]
    outcome = config_outcomes[config_name]
    return {
        "configName": config_name,
        "suiteVerdict": config_summary.get("suiteVerdict"),
        "suiteRecommendedNextLever": config_summary.get("suiteRecommendedNextLever"),
        "failingSourceSummary": dict(source_summaries.get(failing_source_clip_id, {})),
        "comparisonSourceSummary": dict(source_summaries.get(comparison_source_clip_id, {})),
        "failingSourceEdgeShareImprovement": _safe_float(
            outcome.get("failingSourceEdgeShareImprovement"),
            0.0,
        ),
        "configOutcome": outcome.get("configOutcome"),
        "passedPromotionGate": bool(outcome.get("passedPromotionGate")),
        "promotionBlockers": list(outcome.get("promotionBlockers", [])),
    }


def _build_active_lane_snapshot(
    *,
    suite_summary: dict[str, object],
    canonical_proof_floor: dict[str, object],
    compact_fields: dict[str, object],
    source_robustness_diagnosis: dict[str, object],
    detector_breadth_diagnosis: dict[str, object] | None,
    training_prep_diagnosis: dict[str, object] | None,
    detector_training_diagnosis: dict[str, object] | None,
    detector_training_quality_gate_diagnosis: dict[str, object] | None,
    detector_candidate_evaluation_diagnosis: dict[str, object] | None,
    detector_candidate_failure_analysis_diagnosis: dict[str, object] | None,
    detector_candidate_data_quality_fix_diagnosis: dict[str, object] | None,
    detector_candidate_proposal_signal_fix_diagnosis: dict[str, object] | None,
    detector_candidate_validation_gate_remediation_diagnosis: dict[str, object] | None,
    promoted_detector_candidate_robustness_diagnosis: dict[str, object] | None,
    review_densification_diagnosis: dict[str, object] | None,
    failing_source_clip_id: str,
    comparison_source_clip_id: str,
    config_summaries: dict[str, dict[str, object]],
    config_source_summaries: dict[str, dict[str, dict[str, object]]],
    config_outcomes: dict[str, dict[str, object]],
) -> dict[str, object]:
    active_config_name = str(compact_fields["sourceRobustnessActiveConfigName"])
    best_config_name = compact_fields.get("sourceRobustnessBestConfigName")
    best_exploratory_config_name = compact_fields.get("sourceRobustnessBestExploratoryConfigName")
    selected_config_name = best_config_name or active_config_name
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "suiteName": suite_summary.get("suiteName"),
        "suiteType": suite_summary.get("suiteType"),
        "baselineFingerprint": suite_summary.get("baselineFingerprint", {}),
        "suiteEntryCount": _safe_int(suite_summary.get("suiteEntryCount"), 0),
        "successfulEntryCount": _safe_int(suite_summary.get("successfulEntryCount"), 0),
        "failedEntryCount": _safe_int(suite_summary.get("failedEntryCount"), 0),
        "distinctSourceClipCount": _safe_int(suite_summary.get("distinctSourceClipCount"), 0),
        "viableEntryCount": _safe_int(suite_summary.get("viableEntryCount"), 0),
        "truthReadyEntryCount": _safe_int(suite_summary.get("truthReadyEntryCount"), 0),
        "suiteVerdict": suite_summary.get("suiteVerdict"),
        "suiteRecommendedNextLever": suite_summary.get("suiteRecommendedNextLever"),
        "canonicalProofFloor": canonical_proof_floor,
        "failingSourceClipId": failing_source_clip_id,
        "comparisonSourceClipId": comparison_source_clip_id,
        "sourceRobustnessDiagnosis": dict(source_robustness_diagnosis),
        "detectorBreadthDiagnosis": (
            dict(detector_breadth_diagnosis) if isinstance(detector_breadth_diagnosis, dict) else None
        ),
        "trainingPrepDiagnosis": (
            dict(training_prep_diagnosis) if isinstance(training_prep_diagnosis, dict) else None
        ),
        "detectorTrainingDiagnosis": (
            dict(detector_training_diagnosis) if isinstance(detector_training_diagnosis, dict) else None
        ),
        "detectorTrainingQualityGateDiagnosis": (
            dict(detector_training_quality_gate_diagnosis)
            if isinstance(detector_training_quality_gate_diagnosis, dict)
            else None
        ),
        "detectorCandidateEvaluationDiagnosis": (
            dict(detector_candidate_evaluation_diagnosis)
            if isinstance(detector_candidate_evaluation_diagnosis, dict)
            else None
        ),
        "detectorCandidateFailureAnalysisDiagnosis": (
            dict(detector_candidate_failure_analysis_diagnosis)
            if isinstance(detector_candidate_failure_analysis_diagnosis, dict)
            else None
        ),
        "detectorCandidateDataQualityFixDiagnosis": (
            dict(detector_candidate_data_quality_fix_diagnosis)
            if isinstance(detector_candidate_data_quality_fix_diagnosis, dict)
            else None
        ),
        "detectorCandidateProposalSignalFixDiagnosis": (
            dict(detector_candidate_proposal_signal_fix_diagnosis)
            if isinstance(detector_candidate_proposal_signal_fix_diagnosis, dict)
            else None
        ),
        "detectorCandidateValidationGateRemediationDiagnosis": (
            dict(detector_candidate_validation_gate_remediation_diagnosis)
            if isinstance(detector_candidate_validation_gate_remediation_diagnosis, dict)
            else None
        ),
        "promotedDetectorCandidateRobustnessDiagnosis": (
            dict(promoted_detector_candidate_robustness_diagnosis)
            if isinstance(promoted_detector_candidate_robustness_diagnosis, dict)
            else None
        ),
        "reviewDensificationDiagnosis": (
            dict(review_densification_diagnosis)
            if isinstance(review_densification_diagnosis, dict)
            else None
        ),
        "activeConfig": _build_snapshot_config_payload(
            config_name=active_config_name,
            config_summaries=config_summaries,
            config_source_summaries=config_source_summaries,
            config_outcomes=config_outcomes,
            failing_source_clip_id=failing_source_clip_id,
            comparison_source_clip_id=comparison_source_clip_id,
        ),
        "bestQualifyingConfig": (
            _build_snapshot_config_payload(
                config_name=str(best_config_name),
                config_summaries=config_summaries,
                config_source_summaries=config_source_summaries,
                config_outcomes=config_outcomes,
                failing_source_clip_id=failing_source_clip_id,
                comparison_source_clip_id=comparison_source_clip_id,
            )
            if isinstance(best_config_name, str)
            else None
        ),
        "bestExploratoryConfig": (
            _build_snapshot_config_payload(
                config_name=str(best_exploratory_config_name),
                config_summaries=config_summaries,
                config_source_summaries=config_source_summaries,
                config_outcomes=config_outcomes,
                failing_source_clip_id=failing_source_clip_id,
                comparison_source_clip_id=comparison_source_clip_id,
            )
            if isinstance(best_exploratory_config_name, str)
            else None
        ),
        "selectedConfig": _build_snapshot_config_payload(
            config_name=str(selected_config_name),
            config_summaries=config_summaries,
            config_source_summaries=config_source_summaries,
            config_outcomes=config_outcomes,
            failing_source_clip_id=failing_source_clip_id,
            comparison_source_clip_id=comparison_source_clip_id,
        ),
        **compact_fields,
    }


def _suite_summary_from_rows(
    *,
    suite_name: str,
    suite_type: str,
    baseline_fingerprint: dict[str, object],
    rows: list[dict[str, object]],
) -> tuple[dict[str, object], dict[str, dict[str, object]], dict[str, object]]:
    successful_rows = [row for row in rows if row.get("status", "success") == "success"]
    viable_entry_count = sum(bool(row.get("ballTrackViable")) for row in successful_rows)
    truth_ready_entry_count = sum(bool(row.get("fiveMinuteTruthReady")) for row in successful_rows)
    distinct_source_clip_count = len(
        {
            str(row.get("sourceClipId"))
            for row in successful_rows
            if isinstance(row.get("sourceClipId"), str) and str(row.get("sourceClipId")).strip()
        }
    )
    accepted_ratios = [float(row.get("acceptedBallRatio", 0.0)) for row in successful_rows]
    controlled_ratios = [float(row.get("controlledPossessionRatio", 0.0)) for row in successful_rows]
    edge_shares = [float(row.get("ballTrackEdgeFrameShare", 0.0)) for row in successful_rows]

    def _stats(values: list[float]) -> tuple[float, float, float]:
        if not values:
            return 0.0, 0.0, 0.0
        values = sorted(values)
        mid = len(values) // 2
        median_value = values[mid] if len(values) % 2 == 1 else (values[mid - 1] + values[mid]) / 2
        return round(float(median_value), 3), round(min(values), 3), round(max(values), 3)

    median_accepted_ball_ratio, min_accepted_ball_ratio, max_accepted_ball_ratio = _stats(accepted_ratios)
    median_controlled_possession_ratio, min_controlled_possession_ratio, max_controlled_possession_ratio = _stats(
        controlled_ratios
    )
    median_ball_track_edge_frame_share, _, _ = _stats(edge_shares)
    suite_verdict = _suite_verdict(
        successful_entry_count=len(successful_rows),
        distinct_source_clip_count=distinct_source_clip_count,
        viable_entry_count=viable_entry_count,
        truth_ready_entry_count=truth_ready_entry_count,
    )
    source_summaries = build_benchmark_suite_source_summaries(successful_rows)
    suite_summary = {
        "suiteName": suite_name,
        "suiteType": suite_type,
        "baselineFingerprint": baseline_fingerprint,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "suiteEntryCount": len(rows),
        "successfulEntryCount": len(successful_rows),
        "failedEntryCount": len(rows) - len(successful_rows),
        "distinctSourceClipCount": distinct_source_clip_count,
        "viableEntryCount": viable_entry_count,
        "truthReadyEntryCount": truth_ready_entry_count,
        "medianAcceptedBallRatio": median_accepted_ball_ratio,
        "medianControlledPossessionRatio": median_controlled_possession_ratio,
        "medianBallTrackEdgeFrameShare": median_ball_track_edge_frame_share,
        "minAcceptedBallRatio": min_accepted_ball_ratio,
        "maxAcceptedBallRatio": max_accepted_ball_ratio,
        "minControlledPossessionRatio": min_controlled_possession_ratio,
        "maxControlledPossessionRatio": max_controlled_possession_ratio,
        "suiteVerdict": suite_verdict,
        "suiteRecommendedNextLever": _recommended_next_lever(suite_verdict),
        "sourceSummaries": source_summaries,
    }
    robustness_diagnosis = diagnose_benchmark_suite_robustness(
        suite_summary=suite_summary,
        source_summaries=source_summaries,
    )
    return suite_summary, source_summaries, robustness_diagnosis


def _metric_stats(values: list[float]) -> tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    values = sorted(values)
    mid = len(values) // 2
    median_value = values[mid] if len(values) % 2 == 1 else (values[mid - 1] + values[mid]) / 2
    return round(float(median_value), 3), round(min(values), 3), round(max(values), 3)


def _extend_source_summaries_with_retention(
    rows: list[dict[str, object]],
    source_summaries: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    augmented: dict[str, dict[str, object]] = {}
    grouped_rows: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        if row.get("status") != "success":
            continue
        source_clip_id = str(row.get("sourceClipId") or "unknown-source-clip").strip() or "unknown-source-clip"
        grouped_rows.setdefault(source_clip_id, []).append(row)

    for source_clip_id, summary in source_summaries.items():
        clip_rows = grouped_rows.get(source_clip_id, [])
        accepted_retention = [_safe_float(row.get("acceptedRetentionRatio"), 1.0) for row in clip_rows]
        controlled_retention = [_safe_float(row.get("controlledRetentionRatio"), 1.0) for row in clip_rows]
        edge_improvement = [_safe_float(row.get("edgeShareImprovement"), 0.0) for row in clip_rows]
        preserved_boundary_frames = [_safe_float(row.get("preservedBoundaryFrames"), 0.0) for row in clip_rows]
        preserved_supported_frames = [_safe_float(row.get("preservedSupportedFrames"), 0.0) for row in clip_rows]
        preserved_bridge_frames = [_safe_float(row.get("preservedBridgeFrames"), 0.0) for row in clip_rows]
        dropped_interior_unsupported_frames = [
            _safe_float(row.get("droppedInteriorUnsupportedFrames"), 0.0) for row in clip_rows
        ]
        supported_accepted_ball_ratios = [
            _safe_float(row.get("supportedAcceptedBallRatio"), 0.0) for row in clip_rows
        ]
        unsupported_accepted_edge_frames = [
            _safe_float(row.get("unsupportedAcceptedEdgeFrames"), 0.0) for row in clip_rows
        ]
        replacement_runs_considered = [_safe_float(row.get("replacementRunsConsidered"), 0.0) for row in clip_rows]
        replacement_runs_accepted = [_safe_float(row.get("replacementRunsAccepted"), 0.0) for row in clip_rows]
        replacement_runs_rejected = [_safe_float(row.get("replacementRunsRejected"), 0.0) for row in clip_rows]
        replacement_coverage_ratios = [
            _safe_float(row.get("medianReplacementCoverageRatio"), 0.0) for row in clip_rows
        ]
        replacement_rejection_blocker_counts: Counter[str] = Counter()
        for row in clip_rows:
            raw_counts = row.get("replacementRejectionBlockerCounts")
            if not isinstance(raw_counts, dict):
                continue
            for reason, count in raw_counts.items():
                if isinstance(reason, str) and reason.strip():
                    replacement_rejection_blocker_counts[reason] += _safe_int(count, 0)
        median_accepted_retention, _, _ = _metric_stats(accepted_retention)
        median_controlled_retention, _, _ = _metric_stats(controlled_retention)
        median_edge_improvement, _, _ = _metric_stats(edge_improvement)
        median_preserved_boundary_frames, _, _ = _metric_stats(preserved_boundary_frames)
        median_preserved_supported_frames, _, _ = _metric_stats(preserved_supported_frames)
        median_preserved_bridge_frames, _, _ = _metric_stats(preserved_bridge_frames)
        median_dropped_interior_unsupported_frames, _, _ = _metric_stats(dropped_interior_unsupported_frames)
        median_supported_accepted_ball_ratio, _, _ = _metric_stats(supported_accepted_ball_ratios)
        median_unsupported_accepted_edge_frames, _, _ = _metric_stats(unsupported_accepted_edge_frames)
        median_replacement_coverage_ratio, _, _ = _metric_stats(replacement_coverage_ratios)
        augmented[source_clip_id] = {
            **summary,
            "medianAcceptedRetentionRatio": median_accepted_retention,
            "medianControlledRetentionRatio": median_controlled_retention,
            "medianEdgeShareImprovement": median_edge_improvement,
            "medianViabilityLift": round(float(bool(summary.get("sourceViable"))), 3),
            "medianPreservedBoundaryFrames": median_preserved_boundary_frames,
            "medianPreservedSupportedFrames": median_preserved_supported_frames,
            "medianPreservedBridgeFrames": median_preserved_bridge_frames,
            "medianDroppedInteriorUnsupportedFrames": median_dropped_interior_unsupported_frames,
            "medianSupportedAcceptedBallRatio": median_supported_accepted_ball_ratio,
            "medianUnsupportedAcceptedEdgeFrames": median_unsupported_accepted_edge_frames,
            "replacementRunsConsidered": int(sum(replacement_runs_considered)),
            "replacementRunsAccepted": int(sum(replacement_runs_accepted)),
            "replacementRunsRejected": int(sum(replacement_runs_rejected)),
            "medianReplacementCoverageRatio": median_replacement_coverage_ratio,
            "replacementRejectionBlockerCounts": dict(
                sorted(replacement_rejection_blocker_counts.items(), key=lambda item: (-item[1], item[0]))
            ),
        }
    return augmented


def _qualifying_candidate_rank(
    *,
    config_name: str,
    config_summary: dict[str, object],
    config_outcome: dict[str, object],
    failing_source_summary: dict[str, object],
) -> tuple[object, ...]:
    return (
        1 if bool(config_outcome.get("passedPromotionGate")) else 0,
        SOURCE_ROBUSTNESS_OUTCOME_ORDER.get(str(config_outcome.get("configOutcome")), -1),
        VERDICT_ORDER.get(str(config_summary.get("suiteVerdict")), -1),
        _safe_float(config_outcome.get("failingSourceEdgeShareImprovement"), 0.0),
        _safe_float(failing_source_summary.get("medianAcceptedRetentionRatio"), 0.0),
        _safe_float(failing_source_summary.get("medianControlledRetentionRatio"), 0.0),
        _source_robustness_config_preference(config_name),
    )


def _exploratory_candidate_rank(
    *,
    config_name: str,
    config_summary: dict[str, object],
    config_outcome: dict[str, object],
    failing_source_summary: dict[str, object],
) -> tuple[object, ...]:
    return (
        _safe_float(config_outcome.get("failingSourceEdgeShareImprovement"), 0.0),
        VERDICT_ORDER.get(str(config_summary.get("suiteVerdict")), -1),
        SOURCE_ROBUSTNESS_OUTCOME_ORDER.get(str(config_outcome.get("configOutcome")), -1),
        _safe_float(failing_source_summary.get("medianAcceptedRetentionRatio"), 0.0),
        _safe_float(failing_source_summary.get("medianControlledRetentionRatio"), 0.0),
        _source_robustness_config_preference(config_name),
    )


def evaluate_source_robustness_outcome(
    *,
    baseline_suite_verdict: str,
    candidate_suite_verdict: str,
    canonical_proof_floor_intact: bool,
    failing_source_baseline: dict[str, object],
    failing_source_candidate: dict[str, object],
) -> dict[str, object]:
    baseline_edge_share = _safe_float(failing_source_baseline.get("medianBallTrackEdgeFrameShare"), 0.0)
    candidate_edge_share = _safe_float(failing_source_candidate.get("medianBallTrackEdgeFrameShare"), 0.0)
    improvement = round(baseline_edge_share - candidate_edge_share, 3)
    accepted_retention_ratio = _safe_float(failing_source_candidate.get("medianAcceptedRetentionRatio"), 0.0)
    controlled_retention_ratio = _safe_float(failing_source_candidate.get("medianControlledRetentionRatio"), 0.0)
    suite_did_not_get_worse = VERDICT_ORDER.get(candidate_suite_verdict, -1) >= VERDICT_ORDER.get(
        baseline_suite_verdict,
        -1,
    )
    candidate_source_viable = bool(failing_source_candidate.get("sourceViable"))
    candidate_near_viable = candidate_edge_share <= (MAX_VIABLE_BALL_EDGE_FRAME_SHARE + 0.05)
    accepted_retention_ok = accepted_retention_ratio >= 0.60
    controlled_retention_ok = controlled_retention_ratio >= 0.60
    passed_retention_guardrail = accepted_retention_ok and controlled_retention_ok
    qualifies_for_partial = (
        canonical_proof_floor_intact
        and suite_did_not_get_worse
        and passed_retention_guardrail
        and improvement >= 0.05
    )

    if qualifies_for_partial:
        promotion_blockers: list[str] = []
        if improvement < 0.1:
            promotion_blockers.append(PROMOTION_BLOCKER_EDGE_SHARE_IMPROVEMENT_INSUFFICIENT)
        if not (candidate_source_viable or candidate_near_viable):
            promotion_blockers.append(PROMOTION_BLOCKER_FAILING_SOURCE_NOT_VIABLE)
        if not promotion_blockers:
            return {
                "configOutcome": "source_robustness_strong",
                "sourceRobustnessOutcome": "source_robustness_strong",
                "sourceRobustnessRecommendedNextLever": "promote_source_conditioned_edge_share_repair",
                "failingSourceEdgeShareImprovement": improvement,
                "passedPromotionGate": True,
                "promotionBlockers": [],
            }
        return {
            "configOutcome": "source_robustness_partial",
            "sourceRobustnessOutcome": "source_robustness_partial",
            "sourceRobustnessRecommendedNextLever": "iterate_source_conditioned_edge_share_repair",
            "failingSourceEdgeShareImprovement": improvement,
            "passedPromotionGate": False,
            "promotionBlockers": promotion_blockers,
        }

    promotion_blockers: list[str] = []
    if not canonical_proof_floor_intact:
        promotion_blockers.append(PROMOTION_BLOCKER_CANONICAL_PROOF_FLOOR_NOT_INTACT)
    if not suite_did_not_get_worse:
        promotion_blockers.append(PROMOTION_BLOCKER_SUITE_VERDICT_REGRESSED)
    if not accepted_retention_ok:
        promotion_blockers.append(PROMOTION_BLOCKER_ACCEPTED_RETENTION_BELOW_GUARDRAIL)
    if not controlled_retention_ok:
        promotion_blockers.append(PROMOTION_BLOCKER_CONTROLLED_RETENTION_BELOW_GUARDRAIL)
    if improvement < 0.05:
        promotion_blockers.append(PROMOTION_BLOCKER_EDGE_SHARE_IMPROVEMENT_INSUFFICIENT)
    if not promotion_blockers and not (candidate_source_viable or candidate_near_viable):
        promotion_blockers.append(PROMOTION_BLOCKER_FAILING_SOURCE_NOT_VIABLE)
    return {
        "configOutcome": "source_robustness_weak",
        "sourceRobustnessOutcome": "source_robustness_weak",
        "sourceRobustnessRecommendedNextLever": "iterate_source_conditioned_edge_share_repair",
        "failingSourceEdgeShareImprovement": improvement,
        "passedPromotionGate": False,
        "promotionBlockers": promotion_blockers,
    }


def _first_existing_failing_source_video_path(
    manifest: dict[str, object],
    *,
    failing_source_clip_id: str,
) -> Path | None:
    for entry in manifest.get("entries", []):
        if not isinstance(entry, dict):
            continue
        if str(entry.get("sourceClipId") or "") != failing_source_clip_id:
            continue
        video_path = entry.get("videoPath")
        if isinstance(video_path, str) and video_path.strip():
            candidate = Path(video_path).expanduser()
            try:
                if candidate.exists():
                    return candidate
            except OSError:
                continue
    return None


def _combined_reopen_strategy_profile_name(strategy_name: str) -> str | None:
    return None if strategy_name == BASELINE_CONFIG_NAME else strategy_name


def _combined_reopen_strategy_label(strategy_name: str) -> str:
    return "baseline_upstream_path" if strategy_name == BASELINE_CONFIG_NAME else strategy_name


def _combined_reopen_reference_from_summary(
    source_summary: dict[str, object] | None,
) -> dict[str, object]:
    summary = dict(source_summary or {})
    return {
        "acceptedBallFrames": _safe_int(
            summary.get("medianAcceptedBallFrames"),
            int(COMBINED_REOPEN_PLATEAU_BASELINE["acceptedBallFrames"]),
        ),
        "controlledPossessionFrames": _safe_int(
            summary.get("medianControlledPossessionFrames"),
            int(COMBINED_REOPEN_PLATEAU_BASELINE["controlledPossessionFrames"]),
        ),
        "ballTrackViable": bool(summary.get("sourceViable")),
        "ballTrackEdgeFrameShare": _safe_float(
            summary.get("medianBallTrackEdgeFrameShare"),
            float(COMBINED_REOPEN_PLATEAU_BASELINE["ballTrackEdgeFrameShare"]),
        ),
    }


def _combined_reopen_cell_beats_reference(
    cell: dict[str, object],
    reference: dict[str, object],
) -> bool:
    return bool(
        (
            bool(cell.get("ballTrackViable")) and not bool(reference.get("ballTrackViable"))
        )
        or (
            _safe_int(cell.get("acceptedBallFrames"), 0) > _safe_int(reference.get("acceptedBallFrames"), 0)
            and _safe_int(cell.get("controlledPossessionFrames"), 0) >= _safe_int(reference.get("controlledPossessionFrames"), 0)
        )
        or (
            _safe_float(cell.get("ballTrackEdgeFrameShare"), 1.0)
            < _safe_float(reference.get("ballTrackEdgeFrameShare"), 1.0)
            and _safe_int(cell.get("controlledPossessionFrames"), 0) >= _safe_int(reference.get("controlledPossessionFrames"), 0)
        )
    )


def _combined_reopen_cell_rank(cell: dict[str, object]) -> tuple[object, ...]:
    return (
        1 if bool(cell.get("eligibleForLocalWinner", True)) else 0,
        1 if bool(cell.get("productBeatsPlateau")) else 0,
        1 if _safe_float(cell.get("acceptedRetentionRatio"), 0.0) >= 0.60 else 0,
        1 if _safe_float(cell.get("controlledRetentionRatio"), 0.0) >= 0.60 else 0,
        1 if bool(cell.get("ballTrackViable")) else 0,
        SOURCE_ROBUSTNESS_OUTCOME_ORDER.get(str(cell.get("configOutcome")), -1),
        _safe_int(cell.get("acceptedBallFrames"), 0),
        -_safe_float(cell.get("ballTrackEdgeFrameShare"), 1.0),
        _safe_int(cell.get("controlledPossessionFrames"), 0),
        _safe_float(cell.get("acceptedRetentionRatio"), 0.0),
        _safe_float(cell.get("controlledRetentionRatio"), 0.0),
    )


def _combined_reopen_strategy_projection_bundle(
    *,
    strategy_name: str,
    baseline_projection_rows: list[dict[str, object]],
    baseline_config_summary: dict[str, object],
    baseline_source_summaries: dict[str, dict[str, object]],
    config_rows: dict[str, list[dict[str, object]]],
    config_summaries: dict[str, dict[str, object]],
    config_source_summaries: dict[str, dict[str, dict[str, object]]],
    config_outcomes: dict[str, dict[str, object]],
) -> tuple[list[dict[str, object]], dict[str, object], dict[str, dict[str, object]], dict[str, object]]:
    if strategy_name == BASELINE_CONFIG_NAME:
        return (
            baseline_projection_rows,
            baseline_config_summary,
            baseline_source_summaries,
            config_outcomes[BASELINE_CONFIG_NAME],
        )
    return (
        config_rows.get(strategy_name, []),
        config_summaries[strategy_name],
        config_source_summaries[strategy_name],
        config_outcomes[strategy_name],
    )


def _build_combined_reopen_replay_cell(
    *,
    detector_model_path: str,
    strategy_name: str,
    projection_rows: list[dict[str, object]],
    config_summary: dict[str, object],
    source_summaries: dict[str, dict[str, object]],
    outcome: dict[str, object],
    failing_source_clip_id: str,
    best_thin_reference: dict[str, object],
) -> dict[str, object]:
    failing_source_rows = [
        row
        for row in projection_rows
        if str(row.get("sourceClipId") or "") == failing_source_clip_id
    ]
    failing_source_summary = dict(source_summaries.get(failing_source_clip_id, {}))
    reference_metrics = _combined_reopen_reference_from_summary(failing_source_summary)
    selected_window_kind_counts = _aggregate_count_mapping(
        failing_source_rows,
        "acquisitionWindowKindCounts",
    )
    selected_candidate_source_kind = (
        max(selected_window_kind_counts.items(), key=lambda item: (int(item[1]), item[0]))[0]
        if selected_window_kind_counts
        else ("baseline_upstream_path" if strategy_name == BASELINE_CONFIG_NAME else strategy_name)
    )
    touchline_candidate_mode_entered = any(
        bool(row.get("acquisitionTouchlineCandidateModeEntered")) for row in failing_source_rows
    )
    touchline_escape_window_frames = sum(
        _safe_int(row.get("acquisitionTouchlineEscapeWindowFrames"), 0)
        for row in failing_source_rows
    )
    touchline_inboard_window_frames = sum(
        _safe_int(row.get("acquisitionTouchlineInboardWindowFrames"), 0)
        for row in failing_source_rows
    )
    reopened_raw_candidate_frames = sum(
        _safe_int(row.get("acquisitionReopenedRawCandidateFrames"), 0)
        for row in failing_source_rows
    )
    reopened_raw_candidate_selected_frames = sum(
        _safe_int(row.get("acquisitionReopenedRawCandidateSelectedFrames"), 0)
        for row in failing_source_rows
    )
    cell = {
        "detectorModelPath": detector_model_path,
        "detectorModelName": Path(detector_model_path).name,
        "acquisitionStrategyName": strategy_name,
        "edgeShareRepairProfile": _combined_reopen_strategy_profile_name(strategy_name),
        "suiteVerdict": config_summary.get("suiteVerdict"),
        "acceptedBallFrames": _safe_int(reference_metrics.get("acceptedBallFrames"), 0),
        "controlledPossessionFrames": _safe_int(reference_metrics.get("controlledPossessionFrames"), 0),
        "ballTrackViable": bool(reference_metrics.get("ballTrackViable")),
        "ballTrackEdgeFrameShare": _safe_float(reference_metrics.get("ballTrackEdgeFrameShare"), 1.0),
        "acceptedRetentionRatio": _safe_float(
            failing_source_summary.get("medianAcceptedRetentionRatio"),
            1.0 if strategy_name == BASELINE_CONFIG_NAME else 0.0,
        ),
        "controlledRetentionRatio": _safe_float(
            failing_source_summary.get("medianControlledRetentionRatio"),
            1.0 if strategy_name == BASELINE_CONFIG_NAME else 0.0,
        ),
        "proposalWindowKindCandidateCounts": {},
        "proposalWindowKindSelectedCounts": selected_window_kind_counts,
        "selectedCandidateSourceKind": selected_candidate_source_kind,
        "touchlineCandidateModeEntered": touchline_candidate_mode_entered,
        "touchlineEscapeWindowFrames": touchline_escape_window_frames,
        "touchlineInboardWindowFrames": touchline_inboard_window_frames,
        "reopenedRawCandidateFrames": reopened_raw_candidate_frames,
        "reopenedRawCandidateSelectedFrames": reopened_raw_candidate_selected_frames,
        "acquisitionRejectionBlockerCounts": _aggregate_count_mapping(
            failing_source_rows,
            "acquisitionRejectionBlockerCounts",
        ),
        "zeroTouchlineCandidateReasonCounts": _aggregate_count_mapping(
            failing_source_rows,
            "acquisitionZeroTouchlineCandidateReasonCounts",
        ),
        "acquisitionTouchlineEscapeCandidateFrames": sum(
            _safe_int(row.get("acquisitionTouchlineEscapeCandidateFrames"), 0)
            for row in failing_source_rows
        ),
        "acquisitionTouchlineEscapeSelectedFrames": sum(
            _safe_int(row.get("acquisitionTouchlineEscapeSelectedFrames"), 0)
            for row in failing_source_rows
        ),
        "configOutcome": str(outcome.get("configOutcome")),
        "sourceRobustnessOutcome": str(outcome.get("sourceRobustnessOutcome")),
        "promotionBlockers": list(outcome.get("promotionBlockers", [])),
        "evaluationMode": "saved_artifact_replay",
        "supportedBySavedArtifacts": True,
        "eligibleForLocalWinner": (
            strategy_name == BASELINE_CONFIG_NAME
            or str(outcome.get("configOutcome")) in {"source_robustness_partial", "source_robustness_strong"}
        ),
    }
    mechanism_success = bool(
        touchline_candidate_mode_entered
        and (
            touchline_escape_window_frames > 0
            or touchline_inboard_window_frames > 0
            or reopened_raw_candidate_frames > 0
        )
    )
    cell["productBeatsPlateau"] = _combined_reopen_cell_beats_reference(
        cell,
        COMBINED_REOPEN_PLATEAU_BASELINE,
    )
    cell["beatsBestThinCandidate"] = _combined_reopen_cell_beats_reference(cell, best_thin_reference)
    cell["comparison"] = {
        "baseline": dict(COMBINED_REOPEN_PLATEAU_BASELINE),
        "current": {
            "acceptedBallFrames": cell["acceptedBallFrames"],
            "controlledPossessionFrames": cell["controlledPossessionFrames"],
            "ballTrackViable": cell["ballTrackViable"],
            "ballTrackEdgeFrameShare": cell["ballTrackEdgeFrameShare"],
        },
        "mechanismSuccess": mechanism_success,
        "productSuccess": bool(cell["productBeatsPlateau"]),
        "mechanismBeatsPlateau": mechanism_success,
        "productBeatsPlateau": bool(cell["productBeatsPlateau"]),
        "beatsPlateau": bool(cell["productBeatsPlateau"]),
    }
    return cell


def _build_combined_reopen_unsupported_cell(
    *,
    detector_model_path: str,
    strategy_name: str,
) -> dict[str, object]:
    return {
        "detectorModelPath": detector_model_path,
        "detectorModelName": Path(detector_model_path).name,
        "acquisitionStrategyName": strategy_name,
        "edgeShareRepairProfile": _combined_reopen_strategy_profile_name(strategy_name),
        "suiteVerdict": None,
        "acceptedBallFrames": None,
        "controlledPossessionFrames": None,
        "ballTrackViable": False,
        "ballTrackEdgeFrameShare": None,
        "acceptedRetentionRatio": None,
        "controlledRetentionRatio": None,
        "proposalWindowKindCandidateCounts": {},
        "proposalWindowKindSelectedCounts": {},
        "selectedCandidateSourceKind": None,
        "touchlineCandidateModeEntered": False,
        "touchlineEscapeWindowFrames": 0,
        "touchlineInboardWindowFrames": 0,
        "reopenedRawCandidateFrames": 0,
        "reopenedRawCandidateSelectedFrames": 0,
        "acquisitionRejectionBlockerCounts": {},
        "zeroTouchlineCandidateReasonCounts": {"no_saved_detector_artifacts": 1},
        "acquisitionTouchlineEscapeCandidateFrames": 0,
        "acquisitionTouchlineEscapeSelectedFrames": 0,
        "configOutcome": None,
        "sourceRobustnessOutcome": None,
        "promotionBlockers": [],
        "evaluationMode": "missing_saved_detector_artifacts",
        "supportedBySavedArtifacts": False,
        "eligibleForLocalWinner": False,
        "productBeatsPlateau": False,
        "beatsBestThinCandidate": False,
        "skipReason": "no_saved_detector_artifacts_for_local_replay",
        "comparison": {
            "baseline": dict(COMBINED_REOPEN_PLATEAU_BASELINE),
            "current": None,
            "mechanismSuccess": False,
            "productSuccess": False,
            "mechanismBeatsPlateau": False,
            "productBeatsPlateau": False,
            "beatsPlateau": False,
        },
    }


def _run_combined_reopen_matrix(
    *,
    clip_path: Path | None,
    canonical_proof_floor: dict[str, object],
    baseline_fingerprint: dict[str, object],
    baseline_projection_rows: list[dict[str, object]],
    baseline_config_summary: dict[str, object],
    baseline_source_summaries: dict[str, dict[str, object]],
    config_rows: dict[str, list[dict[str, object]]],
    config_summaries: dict[str, dict[str, object]],
    config_source_summaries: dict[str, dict[str, dict[str, object]]],
    config_outcomes: dict[str, dict[str, object]],
    failing_source_clip_id: str,
    best_thin_reference: dict[str, object],
    best_thin_qualifying_config_name: str | None,
) -> dict[str, object] | None:
    cells: list[dict[str, object]] = []
    current_detector_model_path = str(
        baseline_fingerprint.get("detectorModelPath")
        or baseline_fingerprint.get("detectorModelName")
        or COMBINED_REOPEN_DETECTOR_MODELS[0]
    )
    current_detector_model_name = Path(current_detector_model_path).name
    for detector_model_path in COMBINED_REOPEN_DETECTOR_MODELS:
        for strategy_name in COMBINED_REOPEN_STRATEGIES:
            if Path(detector_model_path).name != current_detector_model_name:
                cells.append(
                    _build_combined_reopen_unsupported_cell(
                        detector_model_path=detector_model_path,
                        strategy_name=strategy_name,
                    )
                )
                continue
            projection_rows, config_summary, source_summaries, outcome = _combined_reopen_strategy_projection_bundle(
                strategy_name=strategy_name,
                baseline_projection_rows=baseline_projection_rows,
                baseline_config_summary=baseline_config_summary,
                baseline_source_summaries=baseline_source_summaries,
                config_rows=config_rows,
                config_summaries=config_summaries,
                config_source_summaries=config_source_summaries,
                config_outcomes=config_outcomes,
            )
            cells.append(
                _build_combined_reopen_replay_cell(
                    detector_model_path=detector_model_path,
                    strategy_name=strategy_name,
                    projection_rows=projection_rows,
                    config_summary=config_summary,
                    source_summaries=source_summaries,
                    outcome=outcome,
                    failing_source_clip_id=failing_source_clip_id,
                    best_thin_reference=best_thin_reference,
                )
            )

    if not cells:
        return None

    eligible_cells = [cell for cell in cells if bool(cell.get("eligibleForLocalWinner", True))]
    local_winner = max(eligible_cells, key=_combined_reopen_cell_rank) if eligible_cells else None
    baseline_yolov10n = next(
        (
            cell
            for cell in eligible_cells
            if cell["detectorModelPath"] == "yolov10n.pt" and cell["acquisitionStrategyName"] == BASELINE_CONFIG_NAME
        ),
        None,
    )
    baseline_yolo11s = next(
        (
            cell
            for cell in eligible_cells
            if cell["detectorModelPath"] == "yolo11s.pt" and cell["acquisitionStrategyName"] == BASELINE_CONFIG_NAME
        ),
        None,
    )
    reopen_yolov10n_candidates = [
        cell
        for cell in eligible_cells
        if cell["detectorModelPath"] == "yolov10n.pt"
        and cell["acquisitionStrategyName"] != BASELINE_CONFIG_NAME
    ]
    reopen_yolov10n = (
        max(reopen_yolov10n_candidates, key=_combined_reopen_cell_rank)
        if reopen_yolov10n_candidates
        else None
    )
    detector_uplift_alone_helped = bool(
        baseline_yolov10n is not None
        and baseline_yolo11s is not None
        and _combined_reopen_cell_rank(baseline_yolo11s) > _combined_reopen_cell_rank(baseline_yolov10n)
    )
    candidate_source_reopen_alone_helped = bool(
        baseline_yolov10n is not None
        and reopen_yolov10n is not None
        and _combined_reopen_cell_rank(reopen_yolov10n) > _combined_reopen_cell_rank(baseline_yolov10n)
    )
    combination_only_helped = bool(
        local_winner is not None
        and
        local_winner["detectorModelPath"] == "yolo11s.pt"
        and local_winner["acquisitionStrategyName"] != BASELINE_CONFIG_NAME
        and not detector_uplift_alone_helped
        and not candidate_source_reopen_alone_helped
    )
    winner_is_qualifying = bool(
        isinstance(local_winner, dict)
        and str(local_winner.get("configOutcome") or "") in {
            "source_robustness_partial",
            "source_robustness_strong",
        }
    )
    winner_beats_best_thin_candidate = bool(
        isinstance(local_winner, dict)
        and bool(local_winner.get("beatsBestThinCandidate"))
        and winner_is_qualifying
    )
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "clipPath": str(clip_path) if clip_path is not None else None,
        "canonicalProofFloor": canonical_proof_floor,
        "bestThinQualifyingConfigName": best_thin_qualifying_config_name,
        "bestThinReference": best_thin_reference,
        "cells": cells,
        "localWinner": local_winner,
        "localWinningDetectorModelPath": local_winner.get("detectorModelPath") if isinstance(local_winner, dict) else None,
        "localWinningAcquisitionStrategyName": (
            local_winner.get("acquisitionStrategyName") if isinstance(local_winner, dict) else None
        ),
        "winnerBeatsBestThinCandidate": winner_beats_best_thin_candidate,
        "touchlineCandidateModeEntered": bool(local_winner and local_winner.get("touchlineCandidateModeEntered")),
        "touchlineEscapeWindowFrames": _safe_int(local_winner.get("touchlineEscapeWindowFrames") if isinstance(local_winner, dict) else 0, 0),
        "touchlineInboardWindowFrames": _safe_int(local_winner.get("touchlineInboardWindowFrames") if isinstance(local_winner, dict) else 0, 0),
        "reopenedRawCandidateFrames": _safe_int(local_winner.get("reopenedRawCandidateFrames") if isinstance(local_winner, dict) else 0, 0),
        "reopenedRawCandidateSelectedFrames": _safe_int(
            local_winner.get("reopenedRawCandidateSelectedFrames") if isinstance(local_winner, dict) else 0,
            0,
        ),
        "zeroTouchlineCandidateReasonCounts": dict(
            local_winner.get("zeroTouchlineCandidateReasonCounts")
            if isinstance(local_winner, dict)
            and isinstance(local_winner.get("zeroTouchlineCandidateReasonCounts"), dict)
            else {}
        ),
        "unsupportedDetectorModels": [
            detector_model_path
            for detector_model_path in COMBINED_REOPEN_DETECTOR_MODELS
            if Path(detector_model_path).name != current_detector_model_name
        ],
        "detectorUpliftAloneHelped": detector_uplift_alone_helped,
        "candidateSourceReopenAloneHelped": candidate_source_reopen_alone_helped,
        "combinationOnlyHelped": combination_only_helped,
        "combinedReopenFalsified": not winner_beats_best_thin_candidate,
    }


def _evaluate_projection_bundle(
    *,
    suite_name: str,
    suite_type: str,
    baseline_fingerprint: dict[str, object],
    projection_rows: list[dict[str, object]],
    baseline_config_summary: dict[str, object],
    baseline_source_summaries: dict[str, dict[str, object]],
    canonical_proof_floor: dict[str, object],
    failing_source_clip_id: str,
) -> tuple[dict[str, object], dict[str, dict[str, object]], dict[str, object], dict[str, object]]:
    config_summary, source_summaries, robustness_diagnosis = _suite_summary_from_rows(
        suite_name=suite_name,
        suite_type=suite_type,
        baseline_fingerprint=baseline_fingerprint,
        rows=projection_rows,
    )
    source_summaries = _extend_source_summaries_with_retention(projection_rows, source_summaries)
    outcome = evaluate_source_robustness_outcome(
        baseline_suite_verdict=str(baseline_config_summary["suiteVerdict"]),
        candidate_suite_verdict=str(config_summary["suiteVerdict"]),
        canonical_proof_floor_intact=bool(canonical_proof_floor["intact"]),
        failing_source_baseline=baseline_source_summaries.get(failing_source_clip_id, {}),
        failing_source_candidate=source_summaries.get(failing_source_clip_id, {}),
    )
    return config_summary, source_summaries, robustness_diagnosis, outcome


def _select_best_config_name(
    *,
    candidate_names: list[str],
    config_summaries: dict[str, dict[str, object]],
    config_source_summaries: dict[str, dict[str, dict[str, object]]],
    config_outcomes: dict[str, dict[str, object]],
    failing_source_clip_id: str,
    qualifying_only: bool,
) -> str | None:
    if not candidate_names:
        return None
    if qualifying_only:
        return max(
            candidate_names,
            key=lambda config_name: _qualifying_candidate_rank(
                config_name=config_name,
                config_summary=config_summaries[config_name],
                config_outcome=config_outcomes[config_name],
                failing_source_summary=config_source_summaries[config_name].get(failing_source_clip_id, {}),
            ),
        )
    return max(
        candidate_names,
        key=lambda config_name: _exploratory_candidate_rank(
            config_name=config_name,
            config_summary=config_summaries[config_name],
            config_outcome=config_outcomes[config_name],
            failing_source_summary=config_source_summaries[config_name].get(failing_source_clip_id, {}),
        ),
    )


def _build_frontier_candidate_payload(
    *,
    config_name: str,
    keep_every: int,
    min_run_length: int,
    mode: str,
    guard_frame_count: int,
    is_active_catalog_config: bool,
    config_summaries: dict[str, dict[str, object]],
    config_source_summaries: dict[str, dict[str, dict[str, object]]],
    config_outcomes: dict[str, dict[str, object]],
    failing_source_clip_id: str,
) -> dict[str, object]:
    failing_source_summary = config_source_summaries[config_name].get(failing_source_clip_id, {})
    outcome = config_outcomes[config_name]
    return {
        "configName": config_name,
        "keepEvery": keep_every,
        "minRunLength": min_run_length,
        "mode": mode,
        "guardFrameCount": guard_frame_count,
        "isActiveCatalogConfig": is_active_catalog_config,
        "suiteVerdict": config_summaries[config_name]["suiteVerdict"],
        "configOutcome": outcome.get("configOutcome"),
        "passedPromotionGate": bool(outcome.get("passedPromotionGate")),
        "promotionBlockers": list(outcome.get("promotionBlockers", [])),
        "failingSourceMedianEdgeShare": _safe_float(failing_source_summary.get("medianBallTrackEdgeFrameShare"), 0.0),
        "failingSourceMedianAcceptedRetentionRatio": _safe_float(
            failing_source_summary.get("medianAcceptedRetentionRatio"),
            0.0,
        ),
        "failingSourceMedianControlledRetentionRatio": _safe_float(
            failing_source_summary.get("medianControlledRetentionRatio"),
            0.0,
        ),
        "failingSourceMedianPreservedBoundaryFrames": _safe_float(
            failing_source_summary.get("medianPreservedBoundaryFrames"),
            0.0,
        ),
        "failingSourceMedianPreservedSupportedFrames": _safe_float(
            failing_source_summary.get("medianPreservedSupportedFrames"),
            0.0,
        ),
        "failingSourceMedianPreservedBridgeFrames": _safe_float(
            failing_source_summary.get("medianPreservedBridgeFrames"),
            0.0,
        ),
        "failingSourceMedianDroppedInteriorUnsupportedFrames": _safe_float(
            failing_source_summary.get("medianDroppedInteriorUnsupportedFrames"),
            0.0,
        ),
        "failingSourceMedianSupportedAcceptedBallRatio": _safe_float(
            failing_source_summary.get("medianSupportedAcceptedBallRatio"),
            0.0,
        ),
        "failingSourceMedianUnsupportedAcceptedEdgeFrames": _safe_float(
            failing_source_summary.get("medianUnsupportedAcceptedEdgeFrames"),
            0.0,
        ),
        "failingSourceViable": bool(failing_source_summary.get("sourceViable")),
        "failingSourceEdgeShareImprovement": _safe_float(outcome.get("failingSourceEdgeShareImprovement"), 0.0),
    }


def _build_failure_slice_diagnostic(
    *,
    row: dict[str, object],
    edge_runs: list[dict[str, int]],
    replacement_diagnostics: dict[str, object],
) -> dict[str, object]:
    return {
        "matchId": row.get("matchId"),
        "sliceLabel": row.get("label"),
        "truthGateReasons": list(row.get("truthGateReasons", [])),
        "acceptedBallRatio": _safe_float(row.get("acceptedBallRatio"), 0.0),
        "controlledPossessionRatio": _safe_float(row.get("controlledPossessionRatio"), 0.0),
        "ballTrackEdgeFrameShare": _safe_float(row.get("ballTrackEdgeFrameShare"), 0.0),
        "ballTrackViable": bool(row.get("ballTrackViable")),
        "edgeShareImprovement": _safe_float(row.get("edgeShareImprovement"), 0.0),
        "acceptedRetentionRatio": _safe_float(row.get("acceptedRetentionRatio"), 0.0),
        "controlledRetentionRatio": _safe_float(row.get("controlledRetentionRatio"), 0.0),
        "thinnedEdgeRuns": _safe_int(row.get("thinnedEdgeRuns"), 0),
        "droppedAcceptedEdgeFrames": _safe_int(row.get("droppedAcceptedEdgeFrames"), 0),
        "retainedAcceptedEdgeFrames": _safe_int(row.get("retainedAcceptedEdgeFrames"), 0),
        "preservedBoundaryFrames": _safe_int(row.get("preservedBoundaryFrames"), 0),
        "preservedSupportedFrames": _safe_int(row.get("preservedSupportedFrames"), 0),
        "preservedBridgeFrames": _safe_int(row.get("preservedBridgeFrames"), 0),
        "droppedInteriorUnsupportedFrames": _safe_int(row.get("droppedInteriorUnsupportedFrames"), 0),
        "supportedAcceptedBallRatio": _safe_float(row.get("supportedAcceptedBallRatio"), 0.0),
        "unsupportedAcceptedEdgeFrames": _safe_int(row.get("unsupportedAcceptedEdgeFrames"), 0),
        "replacementRunsConsidered": _safe_int(row.get("replacementRunsConsidered"), 0),
        "replacementRunsAccepted": _safe_int(row.get("replacementRunsAccepted"), 0),
        "replacementRunsRejected": _safe_int(row.get("replacementRunsRejected"), 0),
        "medianReplacementCoverageRatio": _safe_float(row.get("medianReplacementCoverageRatio"), 0.0),
        "replacementRejectionBlockerCounts": dict(
            row.get("replacementRejectionBlockerCounts")
            if isinstance(row.get("replacementRejectionBlockerCounts"), dict)
            else {}
        ),
        "acquisitionWindowKindCounts": dict(
            row.get("acquisitionWindowKindCounts")
            if isinstance(row.get("acquisitionWindowKindCounts"), dict)
            else {}
        ),
        "acquisitionRejectionBlockerCounts": dict(
            row.get("acquisitionRejectionBlockerCounts")
            if isinstance(row.get("acquisitionRejectionBlockerCounts"), dict)
            else {}
        ),
        "acquisitionTouchlineEscapeCandidateFrames": _safe_int(
            row.get("acquisitionTouchlineEscapeCandidateFrames"),
            0,
        ),
        "acquisitionTouchlineEscapeSelectedFrames": _safe_int(
            row.get("acquisitionTouchlineEscapeSelectedFrames"),
            0,
        ),
        "acquisitionRepeatedAnchorSuppressionCount": _safe_int(
            row.get("acquisitionRepeatedAnchorSuppressionCount"),
            0,
        ),
        "acquisitionCandidateEdgeShareBeforeSelection": _safe_float(
            row.get("acquisitionCandidateEdgeShareBeforeSelection"),
            0.0,
        ),
        "acquisitionCandidateEdgeShareAfterSelection": _safe_float(
            row.get("acquisitionCandidateEdgeShareAfterSelection"),
            0.0,
        ),
        "replacementRunDiagnostics": list(
            replacement_diagnostics.get("runDiagnostics")
            if isinstance(replacement_diagnostics.get("runDiagnostics"), list)
            else []
        ),
        "topLongestEdgeRuns": _top_edge_runs(edge_runs),
    }


def run_source_robustness_batch(
    *,
    storage_root: Path,
    manifest_path: Path,
    failing_source_clip_id: str,
    comparison_source_clip_id: str,
    canonical_proof_summary_path: Path,
) -> dict[str, object]:
    storage_root = Path(storage_root)
    manifest_path = Path(manifest_path)
    canonical_proof_summary_path = Path(canonical_proof_summary_path)
    storage = Storage(storage_root)

    suite_result = run_benchmark_suite.run_benchmark_suite(
        storage_root=storage_root,
        manifest_path=manifest_path,
    )
    baseline_suite_summary = dict(suite_result["summary"])
    baseline_rows = [dict(row) for row in suite_result["rows"] if row.get("status") == "success"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    suite_name = str(baseline_suite_summary.get("suiteName", manifest.get("suiteName", "benchmark-suite")))
    suite_type = str(baseline_suite_summary.get("suiteType", manifest.get("suiteType", "saved_match_slice_suite")))
    baseline_fingerprint = dict(manifest.get("baselineFingerprint", {}))
    output_dir = Path(suite_result["outputDir"])

    successful_entries = {
        str(entry.get("matchId")): dict(entry)
        for entry in manifest.get("entries", [])
        if isinstance(entry, dict) and any(row.get("matchId") == entry.get("matchId") for row in baseline_rows)
    }
    summary_by_match_id = {
        match_id: summarize_match_benchmark(storage, match_id)
        for match_id in successful_entries
    }

    baseline_projection_rows = [
        _baseline_projection_row(storage, successful_entries[str(row["matchId"])], summary_by_match_id[str(row["matchId"])])
        for row in baseline_rows
    ]
    baseline_config_summary, baseline_source_summaries, baseline_robustness_diagnosis = _suite_summary_from_rows(
        suite_name=suite_name,
        suite_type=suite_type,
        baseline_fingerprint=baseline_fingerprint,
        rows=baseline_projection_rows,
    )
    baseline_source_summaries = _extend_source_summaries_with_retention(
        baseline_projection_rows,
        baseline_source_summaries,
    )

    canonical_proof_floor = _load_canonical_proof_floor(canonical_proof_summary_path)
    config_rows = {BASELINE_CONFIG_NAME: baseline_projection_rows}
    config_summaries = {BASELINE_CONFIG_NAME: baseline_config_summary}
    config_source_summaries = {BASELINE_CONFIG_NAME: baseline_source_summaries}
    config_robustness_diagnoses = {BASELINE_CONFIG_NAME: baseline_robustness_diagnosis}
    config_specs: dict[str, dict[str, object]] = {
        BASELINE_CONFIG_NAME: {
            "keepEvery": None,
            "minRunLength": None,
            "mode": None,
            "guardFrameCount": 0,
            "isActiveCatalogConfig": True,
        }
    }
    config_outcomes = {
        BASELINE_CONFIG_NAME: {
            "configOutcome": "source_robustness_weak",
            "sourceRobustnessOutcome": "source_robustness_weak",
            "sourceRobustnessRecommendedNextLever": "iterate_source_conditioned_edge_share_repair",
            "failingSourceEdgeShareImprovement": 0.0,
            "passedPromotionGate": False,
            "promotionBlockers": [],
        }
    }

    for config_name, config in SHADOW_CONFIGS.items():
        projection_rows = [
            _shadow_projection_row(
                storage,
                successful_entries[str(row["matchId"])],
                summary_by_match_id[str(row["matchId"])],
                config_name=config_name,
            )
            for row in baseline_rows
        ]
        config_summary, source_summaries, robustness_diagnosis, outcome = _evaluate_projection_bundle(
            suite_name=suite_name,
            suite_type=suite_type,
            baseline_fingerprint=baseline_fingerprint,
            projection_rows=projection_rows,
            baseline_config_summary=baseline_config_summary,
            baseline_source_summaries=baseline_source_summaries,
            canonical_proof_floor=canonical_proof_floor,
            failing_source_clip_id=failing_source_clip_id,
        )
        config_rows[config_name] = projection_rows
        config_summaries[config_name] = config_summary
        config_source_summaries[config_name] = source_summaries
        config_robustness_diagnoses[config_name] = robustness_diagnosis
        config_outcomes[config_name] = outcome
        config_specs[config_name] = {
            "keepEvery": _safe_int(config.get("keepEvery"), 0),
            "minRunLength": _safe_int(config.get("minRunLength"), 0),
            "mode": str(config.get("mode") or "uniform_edge_run_thin"),
            "guardFrameCount": _safe_int(config.get("guardFrameCount"), 0),
            "isActiveCatalogConfig": True,
        }

    frontier_candidate_names: list[str] = []
    frontier_candidate_payloads: list[dict[str, object]] = []
    for keep_every in FRONTIER_KEEP_EVERY_VALUES:
        for min_run_length in FRONTIER_MIN_RUN_LENGTH_VALUES:
            config_name = _grid_candidate_name(keep_every, min_run_length)
            if config_name not in config_rows:
                projection_rows = [
                    _shadow_projection_row(
                        storage,
                        successful_entries[str(row["matchId"])],
                        summary_by_match_id[str(row["matchId"])],
                        config_name=config_name,
                    )
                    for row in baseline_rows
                ]
                config_summary, source_summaries, robustness_diagnosis, outcome = _evaluate_projection_bundle(
                    suite_name=suite_name,
                    suite_type=suite_type,
                    baseline_fingerprint=baseline_fingerprint,
                    projection_rows=projection_rows,
                    baseline_config_summary=baseline_config_summary,
                    baseline_source_summaries=baseline_source_summaries,
                    canonical_proof_floor=canonical_proof_floor,
                    failing_source_clip_id=failing_source_clip_id,
                )
                config_rows[config_name] = projection_rows
                config_summaries[config_name] = config_summary
                config_source_summaries[config_name] = source_summaries
                config_robustness_diagnoses[config_name] = robustness_diagnosis
                config_outcomes[config_name] = outcome
                config_specs[config_name] = {
                    "keepEvery": keep_every,
                    "minRunLength": min_run_length,
                    "mode": "uniform_edge_run_thin",
                    "guardFrameCount": 0,
                    "isActiveCatalogConfig": False,
                }
            frontier_candidate_names.append(config_name)
            frontier_candidate_payloads.append(
                _build_frontier_candidate_payload(
                    config_name=config_name,
                    keep_every=keep_every,
                    min_run_length=min_run_length,
                    mode=str(config_specs[config_name].get("mode") or "uniform_edge_run_thin"),
                    guard_frame_count=_safe_int(config_specs[config_name].get("guardFrameCount"), 0),
                    is_active_catalog_config=bool(config_specs[config_name]["isActiveCatalogConfig"]),
                    config_summaries=config_summaries,
                    config_source_summaries=config_source_summaries,
                    config_outcomes=config_outcomes,
                    failing_source_clip_id=failing_source_clip_id,
                )
            )

    qualifying_candidates = [
        config_name
        for config_name, outcome in config_outcomes.items()
        if config_name != BASELINE_CONFIG_NAME
        and bool(config_specs.get(config_name, {}).get("isActiveCatalogConfig"))
        and SOURCE_ROBUSTNESS_OUTCOME_ORDER.get(str(outcome.get("configOutcome")), -1)
        >= SOURCE_ROBUSTNESS_OUTCOME_ORDER["source_robustness_partial"]
    ]
    exploratory_candidates = [
        config_name
        for config_name in config_outcomes
        if config_name != BASELINE_CONFIG_NAME
        and bool(config_specs.get(config_name, {}).get("isActiveCatalogConfig"))
    ]
    thin_qualifying_candidates = [
        config_name
        for config_name in qualifying_candidates
        if str(config_specs.get(config_name, {}).get("mode") or "") not in {
            "touchline_probe_replace",
            "touchline_acquisition_upgrade",
            "touchline_acquisition_reopen",
            "touchline_candidate_admission_reopen",
        }
    ]
    thin_exploratory_candidates = [
        config_name
        for config_name in exploratory_candidates
        if str(config_specs.get(config_name, {}).get("mode") or "") not in {
            "touchline_probe_replace",
            "touchline_acquisition_upgrade",
            "touchline_acquisition_reopen",
            "touchline_candidate_admission_reopen",
        }
    ]
    touchline_replacement_candidate_name = next(
        (
            config_name
            for config_name in exploratory_candidates
            if str(config_specs.get(config_name, {}).get("mode") or "") == "touchline_probe_replace"
        ),
        None,
    )
    acquisition_candidate_names = [
        config_name
        for config_name in exploratory_candidates
        if str(config_specs.get(config_name, {}).get("mode") or "") in {
            "touchline_acquisition_upgrade",
            "touchline_acquisition_reopen",
            "touchline_candidate_admission_reopen",
        }
    ]
    acquisition_qualifying_candidate_names = [
        config_name
        for config_name in qualifying_candidates
        if config_name in acquisition_candidate_names
    ]
    acquisition_candidate_name = (
        _select_best_config_name(
            candidate_names=acquisition_qualifying_candidate_names,
            config_summaries=config_summaries,
            config_source_summaries=config_source_summaries,
            config_outcomes=config_outcomes,
            failing_source_clip_id=failing_source_clip_id,
            qualifying_only=True,
        )
        if acquisition_qualifying_candidate_names
        else _select_best_config_name(
            candidate_names=acquisition_candidate_names,
            config_summaries=config_summaries,
            config_source_summaries=config_source_summaries,
            config_outcomes=config_outcomes,
            failing_source_clip_id=failing_source_clip_id,
            qualifying_only=False,
        )
    )
    best_thin_qualifying_config_name = _select_best_config_name(
        candidate_names=thin_qualifying_candidates,
        config_summaries=config_summaries,
        config_source_summaries=config_source_summaries,
        config_outcomes=config_outcomes,
        failing_source_clip_id=failing_source_clip_id,
        qualifying_only=True,
    )
    best_thin_exploratory_config_name = _select_best_config_name(
        candidate_names=thin_exploratory_candidates,
        config_summaries=config_summaries,
        config_source_summaries=config_source_summaries,
        config_outcomes=config_outcomes,
        failing_source_clip_id=failing_source_clip_id,
        qualifying_only=False,
    )

    source_robustness_best_config_name = _select_best_config_name(
        candidate_names=qualifying_candidates,
        config_summaries=config_summaries,
        config_source_summaries=config_source_summaries,
        config_outcomes=config_outcomes,
        failing_source_clip_id=failing_source_clip_id,
        qualifying_only=True,
    )
    source_robustness_best_exploratory_config_name = _select_best_config_name(
        candidate_names=exploratory_candidates,
        config_summaries=config_summaries,
        config_source_summaries=config_source_summaries,
        config_outcomes=config_outcomes,
        failing_source_clip_id=failing_source_clip_id,
        qualifying_only=False,
    )
    non_catalog_frontier_candidates = [
        config_name
        for config_name in frontier_candidate_names
        if not bool(config_specs.get(config_name, {}).get("isActiveCatalogConfig"))
    ]
    non_catalog_frontier_qualifying_candidates = [
        config_name
        for config_name in non_catalog_frontier_candidates
        if SOURCE_ROBUSTNESS_OUTCOME_ORDER.get(str(config_outcomes[config_name].get("configOutcome")), -1)
        >= SOURCE_ROBUSTNESS_OUTCOME_ORDER["source_robustness_partial"]
    ]
    best_frontier_config_name = (
        _select_best_config_name(
            candidate_names=non_catalog_frontier_qualifying_candidates,
            config_summaries=config_summaries,
            config_source_summaries=config_source_summaries,
            config_outcomes=config_outcomes,
            failing_source_clip_id=failing_source_clip_id,
            qualifying_only=True,
        )
        if non_catalog_frontier_qualifying_candidates
        else _select_best_config_name(
            candidate_names=non_catalog_frontier_candidates,
            config_summaries=config_summaries,
            config_source_summaries=config_source_summaries,
            config_outcomes=config_outcomes,
            failing_source_clip_id=failing_source_clip_id,
            qualifying_only=False,
        )
    )
    source_robustness_active_config_name = BASELINE_CONFIG_NAME
    final_outcome = (
        config_outcomes[str(source_robustness_best_config_name)]
        if isinstance(source_robustness_best_config_name, str)
        else (
            config_outcomes[str(source_robustness_best_exploratory_config_name)]
            if isinstance(source_robustness_best_exploratory_config_name, str)
            else config_outcomes[BASELINE_CONFIG_NAME]
        )
    )
    improved_source_clip_id = (
        failing_source_clip_id
        if isinstance(source_robustness_best_exploratory_config_name, str)
        and _safe_float(
            config_outcomes[source_robustness_best_exploratory_config_name].get("failingSourceEdgeShareImprovement"),
            0.0,
        ) > 0.0
        else None
    )
    dominant_failure_signal = str(
        baseline_robustness_diagnosis.get(
            "robustnessDominantFailureSignal",
            "high_ball_track_edge_frame_share",
        )
    )
    exploratory_strong_config_count = sum(
        1
        for config_name in frontier_candidate_names
        if str(config_outcomes[config_name].get("configOutcome")) == "source_robustness_strong"
    )
    exploratory_partial_config_count = sum(
        1
        for config_name in frontier_candidate_names
        if str(config_outcomes[config_name].get("configOutcome")) == "source_robustness_partial"
    )
    best_catalog_failing_source_summary = (
        config_source_summaries[str(source_robustness_best_config_name)].get(failing_source_clip_id, {})
        if isinstance(source_robustness_best_config_name, str)
        else {}
    )
    best_catalog_improvement = (
        _safe_float(config_outcomes[str(source_robustness_best_config_name)].get("failingSourceEdgeShareImprovement"), 0.0)
        if isinstance(source_robustness_best_config_name, str)
        else 0.0
    )
    frontier_strictly_beats_best_catalog = any(
        _safe_float(config_outcomes[config_name].get("failingSourceEdgeShareImprovement"), 0.0) > best_catalog_improvement
        and _safe_float(
            config_source_summaries[config_name].get(failing_source_clip_id, {}).get("medianAcceptedRetentionRatio"),
            0.0,
        )
        > _safe_float(best_catalog_failing_source_summary.get("medianAcceptedRetentionRatio"), 0.0)
        and _safe_float(
            config_source_summaries[config_name].get(failing_source_clip_id, {}).get("medianControlledRetentionRatio"),
            0.0,
        )
        > _safe_float(best_catalog_failing_source_summary.get("medianControlledRetentionRatio"), 0.0)
        for config_name in non_catalog_frontier_candidates
    )
    plateau_detected = exploratory_strong_config_count == 0 and (
        not isinstance(source_robustness_best_config_name, str) or not frontier_strictly_beats_best_catalog
    )

    compact_fields = _build_compact_source_robustness_fields(
        source_robustness_active_config_name=source_robustness_active_config_name,
        source_robustness_best_config_name=source_robustness_best_config_name,
        source_robustness_best_exploratory_config_name=source_robustness_best_exploratory_config_name,
        final_outcome=final_outcome,
        dominant_failure_signal=dominant_failure_signal,
        improved_source_clip_id=improved_source_clip_id,
    )
    selected_config_name = (
        str(source_robustness_best_config_name)
        if isinstance(source_robustness_best_config_name, str)
        else BASELINE_CONFIG_NAME
    )
    selected_config_truth_gate_counts = _config_truth_gate_counts(
        [
            row
            for row in config_rows[selected_config_name]
            if str(row.get("sourceClipId") or "") == failing_source_clip_id
        ]
    )
    touchline_replacement_failing_source_summary = (
        config_source_summaries[str(touchline_replacement_candidate_name)].get(failing_source_clip_id, {})
        if isinstance(touchline_replacement_candidate_name, str)
        else {}
    )
    touchline_replacement_beats_best_thin_candidate = bool(
        isinstance(touchline_replacement_candidate_name, str)
        and isinstance(best_thin_qualifying_config_name, str)
        and str(source_robustness_best_config_name or "") == str(touchline_replacement_candidate_name)
        and _safe_float(
            config_outcomes[touchline_replacement_candidate_name].get("failingSourceEdgeShareImprovement"),
            0.0,
        )
        >= _safe_float(
            config_outcomes[best_thin_qualifying_config_name].get("failingSourceEdgeShareImprovement"),
            0.0,
        )
    )
    touchline_replacement_falsified = bool(
        isinstance(touchline_replacement_candidate_name, str)
        and isinstance(best_thin_qualifying_config_name, str)
        and str(touchline_replacement_candidate_name) != str(best_thin_qualifying_config_name)
        and not touchline_replacement_beats_best_thin_candidate
    )
    acquisition_failing_source_rows = [
        row
        for row in config_rows.get(str(acquisition_candidate_name), [])
        if str(row.get("sourceClipId") or "") == failing_source_clip_id
    ] if isinstance(acquisition_candidate_name, str) else []
    acquisition_window_kind_counts = _aggregate_count_mapping(
        acquisition_failing_source_rows,
        "acquisitionWindowKindCounts",
    )
    acquisition_rejection_blocker_counts = _aggregate_count_mapping(
        acquisition_failing_source_rows,
        "acquisitionRejectionBlockerCounts",
    )
    acquisition_zero_touchline_candidate_reason_counts = _aggregate_count_mapping(
        acquisition_failing_source_rows,
        "acquisitionZeroTouchlineCandidateReasonCounts",
    )
    acquisition_candidate_beats_best_thin_candidate = bool(
        isinstance(acquisition_candidate_name, str)
        and isinstance(best_thin_qualifying_config_name, str)
        and str(source_robustness_best_config_name or "") == str(acquisition_candidate_name)
        and _safe_float(
            config_outcomes[acquisition_candidate_name].get("failingSourceEdgeShareImprovement"),
            0.0,
        )
        >= _safe_float(
            config_outcomes[best_thin_qualifying_config_name].get("failingSourceEdgeShareImprovement"),
            0.0,
        )
    )
    acquisition_candidate_falsified = bool(
        isinstance(acquisition_candidate_name, str)
        and isinstance(best_thin_qualifying_config_name, str)
        and str(acquisition_candidate_name) != str(best_thin_qualifying_config_name)
        and not acquisition_candidate_beats_best_thin_candidate
    )
    source_robustness_diagnosis = {
        "plateauDetected": plateau_detected,
        "bestFrontierConfigName": best_frontier_config_name,
        "exploratoryStrongConfigCount": exploratory_strong_config_count,
        "exploratoryPartialConfigCount": exploratory_partial_config_count,
        "selectedConfigTruthGateCounts": selected_config_truth_gate_counts,
        "selectedConfigPrimaryBlocker": _primary_truth_gate_reason(selected_config_truth_gate_counts),
        "bestThinQualifyingConfigName": best_thin_qualifying_config_name,
        "bestThinExploratoryConfigName": best_thin_exploratory_config_name,
        "touchlineReplacementCandidateName": touchline_replacement_candidate_name,
        "touchlineReplacementBeatsBestThinCandidate": touchline_replacement_beats_best_thin_candidate,
        "touchlineReplacementFalsified": touchline_replacement_falsified,
        "touchlineReplacementRunsConsidered": _safe_int(
            touchline_replacement_failing_source_summary.get("replacementRunsConsidered"),
            0,
        ),
        "touchlineReplacementRunsAccepted": _safe_int(
            touchline_replacement_failing_source_summary.get("replacementRunsAccepted"),
            0,
        ),
        "touchlineReplacementMedianCoverageRatio": _safe_float(
            touchline_replacement_failing_source_summary.get("medianReplacementCoverageRatio"),
            0.0,
        ),
        "touchlineReplacementRejectionBlockerCounts": dict(
            touchline_replacement_failing_source_summary.get("replacementRejectionBlockerCounts")
            if isinstance(touchline_replacement_failing_source_summary.get("replacementRejectionBlockerCounts"), dict)
            else {}
        ),
        "acquisitionCandidateName": acquisition_candidate_name,
        "acquisitionCandidateBeatsBestThinCandidate": acquisition_candidate_beats_best_thin_candidate,
        "acquisitionCandidateFalsified": acquisition_candidate_falsified,
        "acquisitionCandidateTouchlineModeEntered": any(
            bool(row.get("acquisitionTouchlineCandidateModeEntered")) for row in acquisition_failing_source_rows
        ),
        "acquisitionCandidateTouchlineEscapeWindowFrames": sum(
            _safe_int(row.get("acquisitionTouchlineEscapeWindowFrames"), 0)
            for row in acquisition_failing_source_rows
        ),
        "acquisitionCandidateTouchlineInboardWindowFrames": sum(
            _safe_int(row.get("acquisitionTouchlineInboardWindowFrames"), 0)
            for row in acquisition_failing_source_rows
        ),
        "acquisitionCandidateWindowKindCounts": acquisition_window_kind_counts,
        "acquisitionCandidateRejectionBlockerCounts": acquisition_rejection_blocker_counts,
        "acquisitionCandidateZeroTouchlineCandidateReasonCounts": acquisition_zero_touchline_candidate_reason_counts,
        "acquisitionCandidateReopenedRawCandidateFrames": sum(
            _safe_int(row.get("acquisitionReopenedRawCandidateFrames"), 0)
            for row in acquisition_failing_source_rows
        ),
        "acquisitionCandidateReopenedRawCandidateSelectedFrames": sum(
            _safe_int(row.get("acquisitionReopenedRawCandidateSelectedFrames"), 0)
            for row in acquisition_failing_source_rows
        ),
    }
    best_thin_reference = _combined_reopen_reference_from_summary(
        (
            config_source_summaries[str(best_thin_qualifying_config_name)].get(failing_source_clip_id, {})
            if isinstance(best_thin_qualifying_config_name, str)
            else baseline_source_summaries.get(failing_source_clip_id, {})
        )
    )
    combined_reopen_matrix_payload = _run_combined_reopen_matrix(
        clip_path=_first_existing_failing_source_video_path(
            manifest,
            failing_source_clip_id=failing_source_clip_id,
        ),
        canonical_proof_floor=canonical_proof_floor,
        baseline_fingerprint=dict(baseline_config_summary.get("baselineFingerprint", {})),
        baseline_projection_rows=baseline_projection_rows,
        baseline_config_summary=baseline_config_summary,
        baseline_source_summaries=baseline_source_summaries,
        config_rows=config_rows,
        config_summaries=config_summaries,
        config_source_summaries=config_source_summaries,
        config_outcomes=config_outcomes,
        failing_source_clip_id=failing_source_clip_id,
        best_thin_reference=best_thin_reference,
        best_thin_qualifying_config_name=best_thin_qualifying_config_name,
    )
    combined_reopen_diagnosis: dict[str, object] | None = None
    if isinstance(combined_reopen_matrix_payload, dict):
        combined_reopen_diagnosis = {
            "localWinningDetectorModelPath": combined_reopen_matrix_payload.get("localWinningDetectorModelPath"),
            "localWinningAcquisitionStrategyName": combined_reopen_matrix_payload.get(
                "localWinningAcquisitionStrategyName"
            ),
            "winnerBeatsBestThinCandidate": bool(
                combined_reopen_matrix_payload.get("winnerBeatsBestThinCandidate")
            ),
            "touchlineCandidateModeEntered": bool(
                combined_reopen_matrix_payload.get("touchlineCandidateModeEntered")
            ),
            "touchlineEscapeWindowFrames": _safe_int(
                combined_reopen_matrix_payload.get("touchlineEscapeWindowFrames"),
                0,
            ),
            "touchlineInboardWindowFrames": _safe_int(
                combined_reopen_matrix_payload.get("touchlineInboardWindowFrames"),
                0,
            ),
            "reopenedRawCandidateFrames": _safe_int(
                combined_reopen_matrix_payload.get("reopenedRawCandidateFrames"),
                0,
            ),
            "reopenedRawCandidateSelectedFrames": _safe_int(
                combined_reopen_matrix_payload.get("reopenedRawCandidateSelectedFrames"),
                0,
            ),
            "zeroTouchlineCandidateReasonCounts": dict(
                combined_reopen_matrix_payload.get("zeroTouchlineCandidateReasonCounts")
                if isinstance(combined_reopen_matrix_payload.get("zeroTouchlineCandidateReasonCounts"), dict)
                else {}
            ),
            "detectorUpliftAloneHelped": bool(combined_reopen_matrix_payload.get("detectorUpliftAloneHelped")),
            "candidateSourceReopenAloneHelped": bool(
                combined_reopen_matrix_payload.get("candidateSourceReopenAloneHelped")
            ),
            "combinationOnlyHelped": bool(combined_reopen_matrix_payload.get("combinationOnlyHelped")),
            "combinedReopenFalsified": bool(combined_reopen_matrix_payload.get("combinedReopenFalsified")),
        }
        source_robustness_diagnosis["combinedReopenDiagnosis"] = dict(combined_reopen_diagnosis)
    detector_breadth_matrix_payload = _load_existing_detector_breadth_matrix(output_dir)
    detector_breadth_diagnosis = _build_detector_breadth_diagnosis(detector_breadth_matrix_payload)
    if isinstance(detector_breadth_diagnosis, dict):
        source_robustness_diagnosis["detectorBreadthDiagnosis"] = dict(detector_breadth_diagnosis)
    training_prep_manifest, training_prep_split_manifest, training_prep_issue_report = _load_existing_training_prep_payload(
        storage_root
    )
    training_prep_diagnosis = _build_training_prep_diagnosis(
        training_prep_manifest,
        training_prep_split_manifest,
        training_prep_issue_report,
    )
    if isinstance(training_prep_diagnosis, dict):
        source_robustness_diagnosis["trainingPrepDiagnosis"] = dict(training_prep_diagnosis)
    (
        review_densification_manifest,
        review_densification_split_manifest,
        review_densification_bundle_report,
        review_densification_batch_outcome,
    ) = _load_existing_review_densification_payload(storage_root)
    review_densification_diagnosis = _build_review_densification_diagnosis(
        review_densification_manifest,
        review_densification_split_manifest,
        review_densification_bundle_report,
        review_densification_batch_outcome,
    )
    if isinstance(review_densification_diagnosis, dict):
        source_robustness_diagnosis["reviewDensificationDiagnosis"] = dict(review_densification_diagnosis)
    (
        detector_training_run_summary,
        detector_training_config,
        detector_training_evaluation_contract,
        detector_training_batch_outcome,
    ) = _load_existing_detector_training_payload(storage_root)
    detector_training_diagnosis = _build_detector_training_diagnosis(
        detector_training_run_summary,
        detector_training_config,
        detector_training_evaluation_contract,
        detector_training_batch_outcome,
    )
    if isinstance(detector_training_diagnosis, dict):
        source_robustness_diagnosis["detectorTrainingDiagnosis"] = dict(detector_training_diagnosis)
    (
        detector_training_quality_gate_summary,
        detector_training_quality_gate_batch_outcome,
    ) = _load_existing_detector_training_quality_gate_payload(storage_root)
    detector_training_quality_gate_diagnosis = _build_detector_training_quality_gate_diagnosis(
        detector_training_quality_gate_summary,
        detector_training_quality_gate_batch_outcome,
    )
    if isinstance(detector_training_quality_gate_diagnosis, dict):
        source_robustness_diagnosis["detectorTrainingQualityGateDiagnosis"] = dict(
            detector_training_quality_gate_diagnosis
        )
    detector_candidate_evaluation_payload = _load_existing_detector_candidate_evaluation_payload(output_dir)
    detector_candidate_evaluation_diagnosis = _build_detector_candidate_evaluation_diagnosis(
        detector_candidate_evaluation_payload
    )
    if isinstance(detector_candidate_evaluation_diagnosis, dict):
        source_robustness_diagnosis["detectorCandidateEvaluationDiagnosis"] = dict(
            detector_candidate_evaluation_diagnosis
        )
    detector_candidate_promotion_payload = _load_existing_detector_candidate_promotion_payload(output_dir)
    detector_candidate_promotion_diagnosis = _build_detector_candidate_promotion_diagnosis(
        detector_candidate_promotion_payload
    )
    if isinstance(detector_candidate_promotion_diagnosis, dict):
        source_robustness_diagnosis["detectorCandidatePromotionDiagnosis"] = dict(
            detector_candidate_promotion_diagnosis
        )
    (
        promoted_detector_candidate_robustness_validation_summary,
        promoted_detector_candidate_robustness_batch_outcome,
    ) = _load_existing_promoted_detector_candidate_robustness_validation_payload(output_dir)
    promoted_detector_candidate_robustness_diagnosis = (
        _build_promoted_detector_candidate_robustness_diagnosis(
            promoted_detector_candidate_robustness_validation_summary,
            promoted_detector_candidate_robustness_batch_outcome,
        )
    )
    if isinstance(promoted_detector_candidate_robustness_diagnosis, dict):
        source_robustness_diagnosis["promotedDetectorCandidateRobustnessDiagnosis"] = dict(
            promoted_detector_candidate_robustness_diagnosis
        )
    (
        promoted_detector_candidate_retention_delta_summary,
        promoted_detector_candidate_retention_delta_batch_outcome,
    ) = _load_existing_promoted_detector_candidate_retention_delta_analysis_payload(output_dir)
    promoted_detector_candidate_retention_delta_diagnosis = (
        _build_promoted_detector_candidate_retention_delta_diagnosis(
            promoted_detector_candidate_retention_delta_summary,
            promoted_detector_candidate_retention_delta_batch_outcome,
        )
    )
    if isinstance(promoted_detector_candidate_retention_delta_diagnosis, dict):
        source_robustness_diagnosis["promotedDetectorCandidateRetentionDeltaDiagnosis"] = dict(
            promoted_detector_candidate_retention_delta_diagnosis
        )
    (
        detector_candidate_failure_analysis_summary,
        detector_candidate_failure_analysis_batch_outcome,
    ) = _load_existing_detector_candidate_failure_analysis_payload(storage_root)
    detector_candidate_failure_analysis_diagnosis = _build_detector_candidate_failure_analysis_diagnosis(
        detector_candidate_failure_analysis_summary,
        detector_candidate_failure_analysis_batch_outcome,
    )
    if isinstance(detector_candidate_failure_analysis_diagnosis, dict):
        source_robustness_diagnosis["detectorCandidateFailureAnalysisDiagnosis"] = dict(
            detector_candidate_failure_analysis_diagnosis
        )
    (
        detector_candidate_data_quality_fix_manifest,
        detector_candidate_data_quality_fix_split_manifest,
        detector_candidate_data_quality_fix_review_bundle_report,
        detector_candidate_data_quality_fix_batch_outcome,
    ) = _load_existing_detector_candidate_data_quality_fix_payload(storage_root)
    detector_candidate_data_quality_fix_diagnosis = _build_detector_candidate_data_quality_fix_diagnosis(
        detector_candidate_data_quality_fix_manifest,
        detector_candidate_data_quality_fix_split_manifest,
        detector_candidate_data_quality_fix_review_bundle_report,
        detector_candidate_data_quality_fix_batch_outcome,
    )
    if isinstance(detector_candidate_data_quality_fix_diagnosis, dict):
        source_robustness_diagnosis["detectorCandidateDataQualityFixDiagnosis"] = dict(
            detector_candidate_data_quality_fix_diagnosis
        )
    (
        detector_candidate_proposal_signal_fix_manifest,
        detector_candidate_proposal_signal_fix_split_manifest,
        detector_candidate_proposal_signal_fix_batch_outcome,
    ) = _load_existing_detector_candidate_proposal_signal_fix_payload(storage_root)
    detector_candidate_proposal_signal_fix_diagnosis = _build_detector_candidate_proposal_signal_fix_diagnosis(
        detector_candidate_proposal_signal_fix_manifest,
        detector_candidate_proposal_signal_fix_split_manifest,
        detector_candidate_proposal_signal_fix_batch_outcome,
    )
    if isinstance(detector_candidate_proposal_signal_fix_diagnosis, dict):
        source_robustness_diagnosis["detectorCandidateProposalSignalFixDiagnosis"] = dict(
            detector_candidate_proposal_signal_fix_diagnosis
        )
    (
        detector_candidate_validation_gate_remediation_manifest,
        detector_candidate_validation_gate_remediation_split_manifest,
        detector_candidate_validation_gate_remediation_batch_outcome,
    ) = _load_existing_detector_candidate_validation_gate_remediation_payload(storage_root)
    detector_candidate_validation_gate_remediation_diagnosis = (
        _build_detector_candidate_validation_gate_remediation_diagnosis(
            detector_candidate_validation_gate_remediation_manifest,
            detector_candidate_validation_gate_remediation_split_manifest,
            detector_candidate_validation_gate_remediation_batch_outcome,
        )
    )
    if isinstance(detector_candidate_validation_gate_remediation_diagnosis, dict):
        source_robustness_diagnosis["detectorCandidateValidationGateRemediationDiagnosis"] = dict(
            detector_candidate_validation_gate_remediation_diagnosis
        )
    final_next_lever = resolve_source_robustness_recommended_next_lever(
        default_next_lever=str(final_outcome["sourceRobustnessRecommendedNextLever"]),
        source_robustness_diagnosis=source_robustness_diagnosis,
        combined_reopen_diagnosis=combined_reopen_diagnosis,
        detector_breadth_diagnosis=detector_breadth_diagnosis,
        training_prep_diagnosis=training_prep_diagnosis,
        detector_training_diagnosis=detector_training_diagnosis,
        detector_training_quality_gate_diagnosis=detector_training_quality_gate_diagnosis,
        detector_candidate_evaluation_diagnosis=detector_candidate_evaluation_diagnosis,
        detector_candidate_promotion_diagnosis=detector_candidate_promotion_diagnosis,
        review_densification_diagnosis=review_densification_diagnosis,
        detector_candidate_data_quality_fix_diagnosis=detector_candidate_data_quality_fix_diagnosis,
        detector_candidate_proposal_signal_fix_diagnosis=detector_candidate_proposal_signal_fix_diagnosis,
        detector_candidate_validation_gate_remediation_diagnosis=detector_candidate_validation_gate_remediation_diagnosis,
        promoted_detector_candidate_robustness_diagnosis=promoted_detector_candidate_robustness_diagnosis,
        promoted_detector_candidate_retention_delta_diagnosis=promoted_detector_candidate_retention_delta_diagnosis,
    )

    matrix_payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "failingSourceClipId": failing_source_clip_id,
        "comparisonSourceClipId": comparison_source_clip_id,
        "canonicalProofFloor": canonical_proof_floor,
        "combinedReopenDiagnosis": combined_reopen_diagnosis,
        "detectorBreadthDiagnosis": detector_breadth_diagnosis,
        "trainingPrepDiagnosis": training_prep_diagnosis,
        "reviewDensificationDiagnosis": review_densification_diagnosis,
        "detectorTrainingDiagnosis": detector_training_diagnosis,
        "detectorTrainingQualityGateDiagnosis": detector_training_quality_gate_diagnosis,
        "detectorCandidateEvaluationDiagnosis": detector_candidate_evaluation_diagnosis,
        "detectorCandidatePromotionDiagnosis": detector_candidate_promotion_diagnosis,
        "promotedDetectorCandidateRobustnessDiagnosis": promoted_detector_candidate_robustness_diagnosis,
        "promotedDetectorCandidateRetentionDeltaDiagnosis": promoted_detector_candidate_retention_delta_diagnosis,
        "detectorCandidateFailureAnalysisDiagnosis": detector_candidate_failure_analysis_diagnosis,
        "detectorCandidateDataQualityFixDiagnosis": detector_candidate_data_quality_fix_diagnosis,
        "detectorCandidateProposalSignalFixDiagnosis": detector_candidate_proposal_signal_fix_diagnosis,
        "detectorCandidateValidationGateRemediationDiagnosis": (
            detector_candidate_validation_gate_remediation_diagnosis
        ),
        "configs": {
            BASELINE_CONFIG_NAME: {
                "configName": BASELINE_CONFIG_NAME,
                "suiteVerdict": baseline_config_summary["suiteVerdict"],
                "suiteRecommendedNextLever": baseline_config_summary["suiteRecommendedNextLever"],
                "failingSourceMedianEdgeShare": _safe_float(
                    baseline_source_summaries.get(failing_source_clip_id, {}).get("medianBallTrackEdgeFrameShare"),
                    0.0,
                ),
                "failingSourceMedianAcceptedRetentionRatio": _safe_float(
                    baseline_source_summaries.get(failing_source_clip_id, {}).get("medianAcceptedRetentionRatio"),
                    1.0,
                ),
                "failingSourceMedianControlledRetentionRatio": _safe_float(
                    baseline_source_summaries.get(failing_source_clip_id, {}).get("medianControlledRetentionRatio"),
                    1.0,
                ),
                "failingSourceViable": bool(
                    baseline_source_summaries.get(failing_source_clip_id, {}).get("sourceViable")
                ),
                "canonicalProofFloorIntact": bool(canonical_proof_floor["intact"]),
                "configOutcome": config_outcomes[BASELINE_CONFIG_NAME]["configOutcome"],
                "failingSourceEdgeShareImprovement": 0.0,
                "passedPromotionGate": False,
                "promotionBlockers": list(config_outcomes[BASELINE_CONFIG_NAME]["promotionBlockers"]),
            },
        },
        **{**compact_fields, "sourceRobustnessRecommendedNextLever": final_next_lever},
    }
    for config_name, config_summary in config_summaries.items():
        if config_name == BASELINE_CONFIG_NAME or not bool(config_specs.get(config_name, {}).get("isActiveCatalogConfig")):
            continue
        source_summaries = config_source_summaries[config_name]
        outcome = config_outcomes[config_name]
        matrix_payload["configs"][config_name] = {
            "configName": config_name,
            "suiteVerdict": config_summary["suiteVerdict"],
            "suiteRecommendedNextLever": config_summary["suiteRecommendedNextLever"],
            "failingSourceMedianEdgeShare": _safe_float(
                source_summaries.get(failing_source_clip_id, {}).get("medianBallTrackEdgeFrameShare"),
                0.0,
            ),
            "failingSourceMedianAcceptedRetentionRatio": _safe_float(
                source_summaries.get(failing_source_clip_id, {}).get("medianAcceptedRetentionRatio"),
                0.0,
            ),
            "failingSourceMedianControlledRetentionRatio": _safe_float(
                source_summaries.get(failing_source_clip_id, {}).get("medianControlledRetentionRatio"),
                0.0,
            ),
            "failingSourceViable": bool(source_summaries.get(failing_source_clip_id, {}).get("sourceViable")),
            "canonicalProofFloorIntact": bool(canonical_proof_floor["intact"]),
            "configOutcome": outcome.get("configOutcome"),
            "failingSourceEdgeShareImprovement": _safe_float(
                outcome.get("failingSourceEdgeShareImprovement"),
                0.0,
            ),
            "passedPromotionGate": bool(outcome.get("passedPromotionGate")),
            "promotionBlockers": list(outcome.get("promotionBlockers", [])),
        }
    source_audit_payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "failingSourceClipId": failing_source_clip_id,
        "comparisonSourceClipId": comparison_source_clip_id,
        "combinedReopenDiagnosis": combined_reopen_diagnosis,
        "detectorBreadthDiagnosis": detector_breadth_diagnosis,
        "trainingPrepDiagnosis": training_prep_diagnosis,
        "reviewDensificationDiagnosis": review_densification_diagnosis,
        "detectorTrainingDiagnosis": detector_training_diagnosis,
        "detectorTrainingQualityGateDiagnosis": detector_training_quality_gate_diagnosis,
        "detectorCandidateEvaluationDiagnosis": detector_candidate_evaluation_diagnosis,
        "detectorCandidatePromotionDiagnosis": detector_candidate_promotion_diagnosis,
        "promotedDetectorCandidateRobustnessDiagnosis": promoted_detector_candidate_robustness_diagnosis,
        "promotedDetectorCandidateRetentionDeltaDiagnosis": promoted_detector_candidate_retention_delta_diagnosis,
        "detectorCandidateFailureAnalysisDiagnosis": detector_candidate_failure_analysis_diagnosis,
        "detectorCandidateDataQualityFixDiagnosis": detector_candidate_data_quality_fix_diagnosis,
        "detectorCandidateProposalSignalFixDiagnosis": detector_candidate_proposal_signal_fix_diagnosis,
        "detectorCandidateValidationGateRemediationDiagnosis": (
            detector_candidate_validation_gate_remediation_diagnosis
        ),
        "configs": {
            BASELINE_CONFIG_NAME: {
                "suiteVerdict": baseline_config_summary["suiteVerdict"],
                "suiteRecommendedNextLever": baseline_config_summary["suiteRecommendedNextLever"],
                "sourceSummaries": baseline_source_summaries,
                "robustnessDiagnosis": baseline_robustness_diagnosis,
                "configOutcome": config_outcomes[BASELINE_CONFIG_NAME]["configOutcome"],
                "passedPromotionGate": bool(config_outcomes[BASELINE_CONFIG_NAME]["passedPromotionGate"]),
                "promotionBlockers": list(config_outcomes[BASELINE_CONFIG_NAME]["promotionBlockers"]),
            },
        },
        **{**compact_fields, "sourceRobustnessRecommendedNextLever": final_next_lever},
    }
    for config_name, config_summary in config_summaries.items():
        if config_name == BASELINE_CONFIG_NAME or not bool(config_specs.get(config_name, {}).get("isActiveCatalogConfig")):
            continue
        source_audit_payload["configs"][config_name] = {
            "suiteVerdict": config_summary["suiteVerdict"],
            "suiteRecommendedNextLever": config_summary["suiteRecommendedNextLever"],
            "sourceSummaries": config_source_summaries[config_name],
            "robustnessDiagnosis": config_robustness_diagnoses[config_name],
            "configOutcome": config_outcomes[config_name]["configOutcome"],
            "passedPromotionGate": bool(config_outcomes[config_name]["passedPromotionGate"]),
            "promotionBlockers": list(config_outcomes[config_name]["promotionBlockers"]),
        }
    slice_projection_payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "failingSourceClipId": failing_source_clip_id,
        "comparisonSourceClipId": comparison_source_clip_id,
        "combinedReopenDiagnosis": combined_reopen_diagnosis,
        "detectorBreadthDiagnosis": detector_breadth_diagnosis,
        "trainingPrepDiagnosis": training_prep_diagnosis,
        "reviewDensificationDiagnosis": review_densification_diagnosis,
        "detectorTrainingDiagnosis": detector_training_diagnosis,
        "detectorTrainingQualityGateDiagnosis": detector_training_quality_gate_diagnosis,
        "detectorCandidateEvaluationDiagnosis": detector_candidate_evaluation_diagnosis,
        "detectorCandidatePromotionDiagnosis": detector_candidate_promotion_diagnosis,
        "promotedDetectorCandidateRobustnessDiagnosis": promoted_detector_candidate_robustness_diagnosis,
        "detectorCandidateFailureAnalysisDiagnosis": detector_candidate_failure_analysis_diagnosis,
        "detectorCandidateDataQualityFixDiagnosis": detector_candidate_data_quality_fix_diagnosis,
        "detectorCandidateProposalSignalFixDiagnosis": detector_candidate_proposal_signal_fix_diagnosis,
        "detectorCandidateValidationGateRemediationDiagnosis": (
            detector_candidate_validation_gate_remediation_diagnosis
        ),
        "configs": {
            BASELINE_CONFIG_NAME: {
                "rows": baseline_projection_rows,
                "configOutcome": config_outcomes[BASELINE_CONFIG_NAME]["configOutcome"],
                "passedPromotionGate": bool(config_outcomes[BASELINE_CONFIG_NAME]["passedPromotionGate"]),
                "promotionBlockers": list(config_outcomes[BASELINE_CONFIG_NAME]["promotionBlockers"]),
            },
        },
        **{**compact_fields, "sourceRobustnessRecommendedNextLever": final_next_lever},
    }
    for config_name, projection_rows in config_rows.items():
        if config_name == BASELINE_CONFIG_NAME or not bool(config_specs.get(config_name, {}).get("isActiveCatalogConfig")):
            continue
        slice_projection_payload["configs"][config_name] = {
            "rows": projection_rows,
            "configOutcome": config_outcomes[config_name]["configOutcome"],
            "passedPromotionGate": bool(config_outcomes[config_name]["passedPromotionGate"]),
            "promotionBlockers": list(config_outcomes[config_name]["promotionBlockers"]),
        }
    frontier_payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "failingSourceClipId": failing_source_clip_id,
        "comparisonSourceClipId": comparison_source_clip_id,
        "combinedReopenDiagnosis": combined_reopen_diagnosis,
        "detectorBreadthDiagnosis": detector_breadth_diagnosis,
        "trainingPrepDiagnosis": training_prep_diagnosis,
        "reviewDensificationDiagnosis": review_densification_diagnosis,
        "detectorTrainingDiagnosis": detector_training_diagnosis,
        "detectorTrainingQualityGateDiagnosis": detector_training_quality_gate_diagnosis,
        "detectorCandidateEvaluationDiagnosis": detector_candidate_evaluation_diagnosis,
        "detectorCandidatePromotionDiagnosis": detector_candidate_promotion_diagnosis,
        "detectorCandidateFailureAnalysisDiagnosis": detector_candidate_failure_analysis_diagnosis,
        "detectorCandidateDataQualityFixDiagnosis": detector_candidate_data_quality_fix_diagnosis,
        "detectorCandidateProposalSignalFixDiagnosis": detector_candidate_proposal_signal_fix_diagnosis,
        "detectorCandidateValidationGateRemediationDiagnosis": (
            detector_candidate_validation_gate_remediation_diagnosis
        ),
        "activeConfigName": source_robustness_active_config_name,
        "bestQualifyingConfigName": source_robustness_best_config_name,
        "bestExploratoryConfigName": source_robustness_best_exploratory_config_name,
        "bestFrontierConfigName": best_frontier_config_name,
        "selectedConfigName": selected_config_name,
        "exploratoryStrongConfigCount": exploratory_strong_config_count,
        "exploratoryPartialConfigCount": exploratory_partial_config_count,
        "exploratoryWeakConfigCount": max(
            len(frontier_candidate_names) - exploratory_strong_config_count - exploratory_partial_config_count,
            0,
        ),
        "plateauDetected": plateau_detected,
        "explicitShadowCandidates": [
            _build_frontier_candidate_payload(
                config_name=config_name,
                keep_every=_safe_int(config_specs[config_name].get("keepEvery"), 0),
                min_run_length=_safe_int(config_specs[config_name].get("minRunLength"), 0),
                mode=str(config_specs[config_name].get("mode") or "uniform_edge_run_thin"),
                guard_frame_count=_safe_int(config_specs[config_name].get("guardFrameCount"), 0),
                is_active_catalog_config=bool(config_specs[config_name].get("isActiveCatalogConfig")),
                config_summaries=config_summaries,
                config_source_summaries=config_source_summaries,
                config_outcomes=config_outcomes,
                failing_source_clip_id=failing_source_clip_id,
            )
            for config_name in SHADOW_CONFIGS
        ],
        "candidates": frontier_candidate_payloads,
        **{**compact_fields, "sourceRobustnessRecommendedNextLever": final_next_lever},
    }
    failure_audit_config_names = list(
        dict.fromkeys(
            [
                BASELINE_CONFIG_NAME,
                best_thin_qualifying_config_name,
                best_thin_exploratory_config_name,
                touchline_replacement_candidate_name,
                acquisition_candidate_name,
            ]
        )
    )
    failure_audit_payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "failingSourceClipId": failing_source_clip_id,
        "comparisonSourceClipId": comparison_source_clip_id,
        "combinedReopenDiagnosis": combined_reopen_diagnosis,
        "detectorBreadthDiagnosis": detector_breadth_diagnosis,
        "trainingPrepDiagnosis": training_prep_diagnosis,
        "reviewDensificationDiagnosis": review_densification_diagnosis,
        "detectorTrainingDiagnosis": detector_training_diagnosis,
        "detectorTrainingQualityGateDiagnosis": detector_training_quality_gate_diagnosis,
        "detectorCandidateEvaluationDiagnosis": detector_candidate_evaluation_diagnosis,
        "detectorCandidatePromotionDiagnosis": detector_candidate_promotion_diagnosis,
        "promotedDetectorCandidateRobustnessDiagnosis": promoted_detector_candidate_robustness_diagnosis,
        "detectorCandidateFailureAnalysisDiagnosis": detector_candidate_failure_analysis_diagnosis,
        "detectorCandidateDataQualityFixDiagnosis": detector_candidate_data_quality_fix_diagnosis,
        "detectorCandidateProposalSignalFixDiagnosis": detector_candidate_proposal_signal_fix_diagnosis,
        "detectorCandidateValidationGateRemediationDiagnosis": (
            detector_candidate_validation_gate_remediation_diagnosis
        ),
        "activeConfigName": source_robustness_active_config_name,
        "bestQualifyingConfigName": source_robustness_best_config_name,
        "bestExploratoryConfigName": source_robustness_best_exploratory_config_name,
        "bestThinQualifyingConfigName": best_thin_qualifying_config_name,
        "bestThinExploratoryConfigName": best_thin_exploratory_config_name,
        "touchlineReplacementCandidateName": touchline_replacement_candidate_name,
        "acquisitionCandidateName": acquisition_candidate_name,
        "bestFrontierConfigName": best_frontier_config_name,
        "selectedConfigName": selected_config_name,
        "configs": {},
        **{**compact_fields, "sourceRobustnessRecommendedNextLever": final_next_lever},
    }
    for config_name in failure_audit_config_names:
        if not isinstance(config_name, str):
            continue
        config_projection_rows = [
            row
            for row in config_rows[config_name]
            if str(row.get("sourceClipId") or "") == failing_source_clip_id
        ]
        slice_diagnostics: list[dict[str, object]] = []
        for row in sorted(config_projection_rows, key=lambda item: str(item.get("matchId") or "")):
            match_id = str(row.get("matchId") or "")
            accepted_rows = _load_accepted_ball_rows(storage, match_id)
            player_rows = _load_player_rows(storage, match_id)
            probe_filtered_rows, probe_raw_rows = _load_probe_observed_rows(storage, match_id)
            config_mode = str(config_specs.get(config_name, {}).get("mode") or "")
            if config_mode in {
                "touchline_acquisition_upgrade",
                "touchline_acquisition_reopen",
                "touchline_candidate_admission_reopen",
            }:
                repair_diagnostics = {
                    "edgeRuns": [],
                }
                replacement_diagnostics = {
                    "runDiagnostics": [],
                }
            else:
                _retained_rows, repair_diagnostics, replacement_diagnostics = apply_source_conditioned_edge_share_repair(
                    accepted_rows,
                    source_clip_id=str(row.get("sourceClipId") or ""),
                    edge_share_repair_profile=(
                        None if config_name == BASELINE_CONFIG_NAME else config_name
                    ),
                    player_rows=player_rows,
                    sample_interval=_infer_sample_interval_from_rows(accepted_rows),
                    probe_filtered_rows=probe_filtered_rows,
                    probe_raw_rows=probe_raw_rows,
                )
            slice_diagnostics.append(
                _build_failure_slice_diagnostic(
                    row=row,
                    edge_runs=list(repair_diagnostics.get("edgeRuns", [])),
                    replacement_diagnostics=replacement_diagnostics,
                )
            )
        truth_gate_counts = _config_truth_gate_counts(config_projection_rows)
        failing_source_summary = config_source_summaries[config_name].get(failing_source_clip_id, {})
        failure_audit_payload["configs"][config_name] = {
            "configName": config_name,
            "suiteVerdict": config_summaries[config_name]["suiteVerdict"],
            "configOutcome": config_outcomes[config_name]["configOutcome"],
            "passedPromotionGate": bool(config_outcomes[config_name]["passedPromotionGate"]),
            "promotionBlockers": list(config_outcomes[config_name]["promotionBlockers"]),
            "truthGateCounts": truth_gate_counts,
            "primaryTruthGateReason": _primary_truth_gate_reason(truth_gate_counts),
            "replacementRunsConsidered": _safe_int(failing_source_summary.get("replacementRunsConsidered"), 0),
            "replacementRunsAccepted": _safe_int(failing_source_summary.get("replacementRunsAccepted"), 0),
            "replacementRunsRejected": _safe_int(failing_source_summary.get("replacementRunsRejected"), 0),
            "medianReplacementCoverageRatio": _safe_float(
                failing_source_summary.get("medianReplacementCoverageRatio"),
                0.0,
            ),
            "replacementRejectionBlockerCounts": dict(
                failing_source_summary.get("replacementRejectionBlockerCounts")
                if isinstance(failing_source_summary.get("replacementRejectionBlockerCounts"), dict)
                else {}
            ),
            "acquisitionWindowKindCounts": _aggregate_count_mapping(
                config_projection_rows,
                "acquisitionWindowKindCounts",
            ),
            "acquisitionTouchlineCandidateModeEntered": any(
                bool(row.get("acquisitionTouchlineCandidateModeEntered")) for row in config_projection_rows
            ),
            "acquisitionTouchlineEscapeWindowFrames": sum(
                _safe_int(row.get("acquisitionTouchlineEscapeWindowFrames"), 0)
                for row in config_projection_rows
            ),
            "acquisitionTouchlineInboardWindowFrames": sum(
                _safe_int(row.get("acquisitionTouchlineInboardWindowFrames"), 0)
                for row in config_projection_rows
            ),
            "acquisitionRejectionBlockerCounts": _aggregate_count_mapping(
                config_projection_rows,
                "acquisitionRejectionBlockerCounts",
            ),
            "acquisitionZeroTouchlineCandidateReasonCounts": _aggregate_count_mapping(
                config_projection_rows,
                "acquisitionZeroTouchlineCandidateReasonCounts",
            ),
            "acquisitionTouchlineEscapeCandidateFrames": sum(
                _safe_int(row.get("acquisitionTouchlineEscapeCandidateFrames"), 0)
                for row in config_projection_rows
            ),
            "acquisitionTouchlineEscapeSelectedFrames": sum(
                _safe_int(row.get("acquisitionTouchlineEscapeSelectedFrames"), 0)
                for row in config_projection_rows
            ),
            "acquisitionReopenedRawCandidateFrames": sum(
                _safe_int(row.get("acquisitionReopenedRawCandidateFrames"), 0)
                for row in config_projection_rows
            ),
            "acquisitionReopenedRawCandidateSelectedFrames": sum(
                _safe_int(row.get("acquisitionReopenedRawCandidateSelectedFrames"), 0)
                for row in config_projection_rows
            ),
            "sliceDiagnostics": slice_diagnostics,
        }

    (output_dir / "primary_source_robustness_matrix.json").write_text(
        json.dumps(matrix_payload, indent=2),
        encoding="utf-8",
    )
    (output_dir / "primary_source_robustness_source_audit.json").write_text(
        json.dumps(source_audit_payload, indent=2),
        encoding="utf-8",
    )
    (output_dir / "primary_source_robustness_slice_projection.json").write_text(
        json.dumps(slice_projection_payload, indent=2),
        encoding="utf-8",
    )
    (output_dir / "primary_source_robustness_frontier.json").write_text(
        json.dumps(frontier_payload, indent=2),
        encoding="utf-8",
    )
    (output_dir / "primary_source_robustness_failure_audit.json").write_text(
        json.dumps(failure_audit_payload, indent=2),
        encoding="utf-8",
    )
    combined_reopen_matrix_path = output_dir / "combined_detector_candidate_source_matrix.json"
    combined_reopen_matrix_path.write_text(
        json.dumps(
            combined_reopen_matrix_payload
            if isinstance(combined_reopen_matrix_payload, dict)
            else {
                "generatedAt": datetime.now(timezone.utc).isoformat(),
                "failingSourceClipId": failing_source_clip_id,
                "comparisonSourceClipId": comparison_source_clip_id,
                "canonicalProofFloor": canonical_proof_floor,
                "skipped": True,
                "reason": "failing source clip path unavailable",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    suite_summary_path = output_dir / "suite_summary.json"
    suite_summary_payload = json.loads(suite_summary_path.read_text(encoding="utf-8"))
    compact_fields["sourceRobustnessRecommendedNextLever"] = final_next_lever
    suite_summary_payload.update(compact_fields)
    if isinstance(combined_reopen_diagnosis, dict):
        suite_summary_payload["combinedReopenDiagnosis"] = combined_reopen_diagnosis
    if isinstance(detector_breadth_diagnosis, dict):
        suite_summary_payload["detectorBreadthDiagnosis"] = detector_breadth_diagnosis
    if isinstance(training_prep_diagnosis, dict):
        suite_summary_payload["trainingPrepDiagnosis"] = training_prep_diagnosis
    if isinstance(review_densification_diagnosis, dict):
        suite_summary_payload["reviewDensificationDiagnosis"] = review_densification_diagnosis
    if isinstance(detector_training_diagnosis, dict):
        suite_summary_payload["detectorTrainingDiagnosis"] = detector_training_diagnosis
    if isinstance(detector_training_quality_gate_diagnosis, dict):
        suite_summary_payload["detectorTrainingQualityGateDiagnosis"] = detector_training_quality_gate_diagnosis
    if isinstance(detector_candidate_evaluation_diagnosis, dict):
        suite_summary_payload["detectorCandidateEvaluationDiagnosis"] = detector_candidate_evaluation_diagnosis
    if isinstance(detector_candidate_promotion_diagnosis, dict):
        suite_summary_payload["detectorCandidatePromotionDiagnosis"] = detector_candidate_promotion_diagnosis
    if isinstance(promoted_detector_candidate_robustness_diagnosis, dict):
        suite_summary_payload["promotedDetectorCandidateRobustnessDiagnosis"] = (
            promoted_detector_candidate_robustness_diagnosis
        )
    if isinstance(promoted_detector_candidate_retention_delta_diagnosis, dict):
        suite_summary_payload["promotedDetectorCandidateRetentionDeltaDiagnosis"] = (
            promoted_detector_candidate_retention_delta_diagnosis
        )
    if isinstance(detector_candidate_failure_analysis_diagnosis, dict):
        suite_summary_payload["detectorCandidateFailureAnalysisDiagnosis"] = (
            detector_candidate_failure_analysis_diagnosis
        )
    if isinstance(detector_candidate_data_quality_fix_diagnosis, dict):
        suite_summary_payload["detectorCandidateDataQualityFixDiagnosis"] = (
            detector_candidate_data_quality_fix_diagnosis
        )
    if isinstance(detector_candidate_proposal_signal_fix_diagnosis, dict):
        suite_summary_payload["detectorCandidateProposalSignalFixDiagnosis"] = (
            detector_candidate_proposal_signal_fix_diagnosis
        )
    if isinstance(detector_candidate_validation_gate_remediation_diagnosis, dict):
        suite_summary_payload["detectorCandidateValidationGateRemediationDiagnosis"] = (
            detector_candidate_validation_gate_remediation_diagnosis
        )
    suite_summary_path.write_text(json.dumps(suite_summary_payload, indent=2), encoding="utf-8")

    robustness_diagnosis_path = output_dir / "suite_robustness_diagnosis.json"
    robustness_diagnosis_payload = json.loads(robustness_diagnosis_path.read_text(encoding="utf-8"))
    robustness_diagnosis_payload.update(compact_fields)
    robustness_diagnosis_payload["sourceRobustnessDiagnosis"] = source_robustness_diagnosis
    if isinstance(combined_reopen_diagnosis, dict):
        robustness_diagnosis_payload["combinedReopenDiagnosis"] = combined_reopen_diagnosis
    if isinstance(detector_breadth_diagnosis, dict):
        robustness_diagnosis_payload["detectorBreadthDiagnosis"] = detector_breadth_diagnosis
    if isinstance(training_prep_diagnosis, dict):
        robustness_diagnosis_payload["trainingPrepDiagnosis"] = training_prep_diagnosis
    if isinstance(review_densification_diagnosis, dict):
        robustness_diagnosis_payload["reviewDensificationDiagnosis"] = review_densification_diagnosis
    if isinstance(detector_training_diagnosis, dict):
        robustness_diagnosis_payload["detectorTrainingDiagnosis"] = detector_training_diagnosis
    if isinstance(detector_training_quality_gate_diagnosis, dict):
        robustness_diagnosis_payload["detectorTrainingQualityGateDiagnosis"] = (
            detector_training_quality_gate_diagnosis
        )
    if isinstance(detector_candidate_evaluation_diagnosis, dict):
        robustness_diagnosis_payload["detectorCandidateEvaluationDiagnosis"] = detector_candidate_evaluation_diagnosis
    if isinstance(detector_candidate_promotion_diagnosis, dict):
        robustness_diagnosis_payload["detectorCandidatePromotionDiagnosis"] = detector_candidate_promotion_diagnosis
    if isinstance(promoted_detector_candidate_robustness_diagnosis, dict):
        robustness_diagnosis_payload["promotedDetectorCandidateRobustnessDiagnosis"] = (
            promoted_detector_candidate_robustness_diagnosis
        )
    if isinstance(promoted_detector_candidate_retention_delta_diagnosis, dict):
        robustness_diagnosis_payload["promotedDetectorCandidateRetentionDeltaDiagnosis"] = (
            promoted_detector_candidate_retention_delta_diagnosis
        )
    if isinstance(detector_candidate_failure_analysis_diagnosis, dict):
        robustness_diagnosis_payload["detectorCandidateFailureAnalysisDiagnosis"] = (
            detector_candidate_failure_analysis_diagnosis
        )
    if isinstance(detector_candidate_data_quality_fix_diagnosis, dict):
        robustness_diagnosis_payload["detectorCandidateDataQualityFixDiagnosis"] = (
            detector_candidate_data_quality_fix_diagnosis
        )
    if isinstance(detector_candidate_proposal_signal_fix_diagnosis, dict):
        robustness_diagnosis_payload["detectorCandidateProposalSignalFixDiagnosis"] = (
            detector_candidate_proposal_signal_fix_diagnosis
        )
    if isinstance(detector_candidate_validation_gate_remediation_diagnosis, dict):
        robustness_diagnosis_payload["detectorCandidateValidationGateRemediationDiagnosis"] = (
            detector_candidate_validation_gate_remediation_diagnosis
        )
    robustness_diagnosis_path.write_text(json.dumps(robustness_diagnosis_payload, indent=2), encoding="utf-8")

    active_lane_snapshot_payload = _build_active_lane_snapshot(
        suite_summary=suite_summary_payload,
        canonical_proof_floor=canonical_proof_floor,
        compact_fields=compact_fields,
        source_robustness_diagnosis=source_robustness_diagnosis,
        detector_breadth_diagnosis=detector_breadth_diagnosis,
        training_prep_diagnosis=training_prep_diagnosis,
        detector_training_diagnosis=detector_training_diagnosis,
        detector_training_quality_gate_diagnosis=detector_training_quality_gate_diagnosis,
        detector_candidate_evaluation_diagnosis=detector_candidate_evaluation_diagnosis,
        detector_candidate_failure_analysis_diagnosis=detector_candidate_failure_analysis_diagnosis,
        detector_candidate_data_quality_fix_diagnosis=detector_candidate_data_quality_fix_diagnosis,
        detector_candidate_proposal_signal_fix_diagnosis=detector_candidate_proposal_signal_fix_diagnosis,
        detector_candidate_validation_gate_remediation_diagnosis=(
            detector_candidate_validation_gate_remediation_diagnosis
        ),
        promoted_detector_candidate_robustness_diagnosis=promoted_detector_candidate_robustness_diagnosis,
        review_densification_diagnosis=review_densification_diagnosis,
        failing_source_clip_id=failing_source_clip_id,
        comparison_source_clip_id=comparison_source_clip_id,
        config_summaries=config_summaries,
        config_source_summaries=config_source_summaries,
        config_outcomes=config_outcomes,
    )
    (output_dir / "active_lane_snapshot.json").write_text(
        json.dumps(active_lane_snapshot_payload, indent=2),
        encoding="utf-8",
    )

    return {
        **compact_fields,
        "configOutcome": final_outcome["configOutcome"],
        "failingSourceEdgeShareImprovement": final_outcome["failingSourceEdgeShareImprovement"],
        "passedPromotionGate": bool(final_outcome.get("passedPromotionGate")),
        "promotionBlockers": list(final_outcome.get("promotionBlockers", [])),
        "outputDir": str(output_dir),
        "combinedDetectorCandidateSourceMatrixPath": str(combined_reopen_matrix_path),
        "detectorBreadthMatrixPath": (
            str(output_dir / "detector_breadth_matrix.json")
            if (output_dir / "detector_breadth_matrix.json").exists()
            else None
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a local source-conditioned edge-share robustness repair batch from saved suite artifacts."
    )
    parser.add_argument("--storage-root", default=str(DEFAULT_STORAGE_ROOT))
    parser.add_argument("--manifest-path", default=str(DEFAULT_MANIFEST_PATH))
    parser.add_argument("--failing-source-clip-id", default="trimed-5min.mp4")
    parser.add_argument("--comparison-source-clip-id", default="trimed-football-2-1minute.mp4")
    parser.add_argument("--canonical-proof-summary-path", default=str(DEFAULT_CANONICAL_PROOF_SUMMARY_PATH))
    args = parser.parse_args()

    result = run_source_robustness_batch(
        storage_root=Path(args.storage_root),
        manifest_path=Path(args.manifest_path),
        failing_source_clip_id=args.failing_source_clip_id,
        comparison_source_clip_id=args.comparison_source_clip_id,
        canonical_proof_summary_path=Path(args.canonical_proof_summary_path),
    )
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
