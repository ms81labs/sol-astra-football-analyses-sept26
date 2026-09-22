from __future__ import annotations
from backend.scripts.football_external_real_eval_chain_common import load_json_object_strict as _load_json
from backend.scripts.football_external_real_eval_chain_common import write_json_unsorted_no_newline as _write_json


from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.app.proof_summary import build_canonical_proof_summary  # noqa: E402

DEFAULT_CANDIDATE_NAME: str | None = None
DEFAULT_PREVIOUS_CANDIDATE_NAME: str | None = None
DEFAULT_FAILURE_ANALYSIS_DIR_NAME = "failure_analysis_v1"
DEFAULT_EVALUATION_DIR_NAME = "evaluation_v1"
DEFAULT_FAILURE_ANALYSIS_BATCH_NAME = "touchline_detector_candidate_failure_analysis_v1"
DEFAULT_CANDIDATE_PROOF_BUNDLE_NAMES = {
    "touchline_detector_candidate_v2": "touchline-detector-candidate-v2-probe-assist-baseline-20260422223225",
    "touchline_detector_candidate_v3": "touchline-detector-candidate-v3-probe-assist-baseline-20260423045031",
}
DEFAULT_BASELINE_CONTROL_PROOF_BUNDLE_NAME = "yolov10n-pt-baseline-full-detector-baseline-control-20260422224502"
NEXT_RECOMMENDED_NEXT_LEVER = "evaluate_touchline_detector_candidate"
BASELINE_DETECTOR_LABEL = "yolov10n.pt_baseline_full_detector"

SCREEN_EXECUTION_FAILURE = "screen_execution_failure"
ROOT_CAUSE_AUXILIARY_PROBE_ZERO_RAW_ROWS = "auxiliary_probe_zero_raw_rows"
ROOT_CAUSE_AUXILIARY_PROBE_ROWS_FILTERED_OUT = "auxiliary_probe_rows_filtered_out"
ROOT_CAUSE_ACCEPTED_LAYER_COLLAPSE_AFTER_PROBE = "accepted_layer_collapse_after_probe"
ROOT_CAUSE_INSUFFICIENT_PRODUCT_LIFT = "insufficient_product_lift"

RECOMMENDED_FIX_EXECUTION_PLUMBING = "execution_plumbing"
RECOMMENDED_FIX_MODEL_DATA_QUALITY = "model_data_quality"
RECOMMENDED_FIX_PROBE_INTEGRATION_BEHAVIOR = "probe_integration_behavior"
RECOMMENDED_FIX_ACCEPTANCE_PIPELINE_BEHAVIOR = "acceptance_pipeline_behavior"

CHANGE_FROM_PREVIOUS_NO_OBSERVABLE_IMPROVEMENT = "no_observable_improvement"
CHANGE_FROM_PREVIOUS_PROPOSAL_GENERATION_IMPROVEMENT_ONLY = "proposal_generation_improvement_only"
CHANGE_FROM_PREVIOUS_PROBE_LAYER_IMPROVEMENT_ONLY = "probe_layer_improvement_only"
CHANGE_FROM_PREVIOUS_ACCEPTED_LAYER_IMPROVEMENT_ONLY = "accepted_layer_improvement_only"
CHANGE_FROM_PREVIOUS_PRODUCT_IMPROVEMENT = "product_improvement"

RECOMMENDED_FIX_FOCUS_PROPOSAL_SIGNAL_GENERATION = "proposal_signal_generation"
RECOMMENDED_FIX_FOCUS_RAW_PROBE_MATERIALIZATION = "raw_probe_materialization"
RECOMMENDED_FIX_FOCUS_PROBE_FILTERING_BEHAVIOR = "probe_filtering_behavior"
RECOMMENDED_FIX_FOCUS_ACCEPTED_LAYER_BEHAVIOR = "accepted_layer_behavior"
RECOMMENDED_FIX_FOCUS_PRODUCT_LIFT_GAP = "product_lift_gap"
REQUIRED_JUDGE_FIELDS = (
    "acceptedBallFrames",
    "supportedAcceptedBallRatio",
    "controlledPossessionFrames",
    "eventFamilyCount",
    "truthGateReasons",
)






def _write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _extract_frame_id(row: object) -> int | None:
    if not isinstance(row, dict):
        return None
    if "frameId" in row:
        return _safe_int(row.get("frameId"), default=-1)
    if "Frame_ID" in row:
        return _safe_int(row.get("Frame_ID"), default=-1)
    return None


def _rows_from_payload(payload: object) -> list[dict[str, object]]:
    if not isinstance(payload, list):
        return []
    rows = [dict(row) for row in payload if isinstance(row, dict) and _extract_frame_id(row) is not None]
    rows.sort(key=lambda row: _extract_frame_id(row) or -1)
    return rows


def _frame_ids(rows: list[dict[str, object]]) -> list[int]:
    return sorted(
        {
            frame_id
            for frame_id in (_extract_frame_id(row) for row in rows)
            if frame_id is not None and frame_id >= 0
        }
    )


def _candidate_version(candidate_name: str) -> int:
    match = re.search(r"_v(\d+)$", candidate_name)
    if match is None:
        return -1
    return _safe_int(match.group(1), -1)


def _candidate_roots_with_evaluation(storage_root: Path) -> list[tuple[int, str, Path]]:
    candidates_root = storage_root / "trained_detector_candidates"
    candidate_roots: list[tuple[int, str, Path]] = []
    if not candidates_root.exists():
        return candidate_roots
    for child in candidates_root.iterdir():
        if not child.is_dir():
            continue
        version = _candidate_version(child.name)
        if version <= 0:
            continue
        if not (child / DEFAULT_EVALUATION_DIR_NAME / "evaluation_summary.json").exists():
            continue
        candidate_roots.append((version, child.name, child))
    candidate_roots.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidate_roots


def resolve_active_candidate_name(storage_root: Path, requested_candidate_name: str | None = None) -> str:
    if isinstance(requested_candidate_name, str) and requested_candidate_name.strip():
        return requested_candidate_name.strip()
    candidate_roots = _candidate_roots_with_evaluation(storage_root)
    if not candidate_roots:
        raise FileNotFoundError(
            f"No evaluated detector candidate found under {storage_root / 'trained_detector_candidates'}"
        )
    return candidate_roots[0][1]


def resolve_previous_candidate_name(
    storage_root: Path,
    active_candidate_name: str,
    requested_previous_candidate_name: str | None = None,
) -> str:
    if isinstance(requested_previous_candidate_name, str) and requested_previous_candidate_name.strip():
        return requested_previous_candidate_name.strip()
    active_version = _candidate_version(active_candidate_name)
    candidate_roots = _candidate_roots_with_evaluation(storage_root)
    for version, candidate_name, _candidate_root in candidate_roots:
        if version < active_version:
            return candidate_name
    raise FileNotFoundError(
        f"No previous evaluated detector candidate found before {active_candidate_name}"
    )


def _artifact_paths(storage_root: Path, candidate_name: str) -> dict[str, Path]:
    candidate_root = storage_root / "trained_detector_candidates" / candidate_name
    evaluation_root = candidate_root / DEFAULT_EVALUATION_DIR_NAME
    failure_analysis_root = candidate_root / DEFAULT_FAILURE_ANALYSIS_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "evaluationRoot": evaluation_root,
        "failureAnalysisRoot": failure_analysis_root,
        "evaluationSummaryPath": evaluation_root / "evaluation_summary.json",
        "screenMatrixPath": evaluation_root / "screen_matrix.json",
        "proofReportPath": evaluation_root / "proof_report.json",
        "evaluationBatchOutcomePath": evaluation_root / "batch_outcome_analysis.json",
    }


def _proof_bundle_root_from_summary_path(summary_path: str | None) -> Path | None:
    if not isinstance(summary_path, str) or not summary_path.strip():
        return None
    path = Path(summary_path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.parent


def _candidate_proof_bundle_root(
    proof_report: dict[str, object],
    storage_root: Path,
    candidate_name: str,
) -> Path:
    candidate_baseline_result = (
        dict(proof_report.get("candidateBaselineResult"))
        if isinstance(proof_report.get("candidateBaselineResult"), dict)
        else {}
    )
    summary_path = candidate_baseline_result.get("summaryPath")
    bundle_root = _proof_bundle_root_from_summary_path(summary_path if isinstance(summary_path, str) else None)
    if bundle_root is None:
        fallback_bundle_name = DEFAULT_CANDIDATE_PROOF_BUNDLE_NAMES.get(candidate_name)
        if fallback_bundle_name is not None:
            bundle_root = storage_root / "pod_cycles" / fallback_bundle_name
    if bundle_root is None or not bundle_root.exists():
        raise FileNotFoundError(f"Candidate proof bundle not found for {candidate_name}")
    return bundle_root


def _baseline_control_proof_bundle_root(proof_report: dict[str, object], storage_root: Path) -> Path:
    baseline_control_result = (
        dict(proof_report.get("baselineControlResult"))
        if isinstance(proof_report.get("baselineControlResult"), dict)
        else {}
    )
    summary_path = baseline_control_result.get("summaryPath")
    bundle_root = _proof_bundle_root_from_summary_path(summary_path if isinstance(summary_path, str) else None)
    if bundle_root is None:
        discarded_bundles = proof_report.get("discardedIntermediateProofBundles")
        if isinstance(discarded_bundles, list):
            for bundle in discarded_bundles:
                if not isinstance(bundle, dict):
                    continue
                if str(bundle.get("proofKind") or "") != "baseline_control":
                    continue
                bundle_root = _proof_bundle_root_from_summary_path(
                    bundle.get("proofSummaryPath") if isinstance(bundle.get("proofSummaryPath"), str) else None
                )
                if bundle_root is not None:
                    break
    if bundle_root is None:
        bundle_root = storage_root / "pod_cycles" / DEFAULT_BASELINE_CONTROL_PROOF_BUNDLE_NAME
    if not bundle_root.exists():
        raise FileNotFoundError(f"Baseline control proof bundle not found at {bundle_root}")
    return bundle_root


def classify_failure_root_cause(
    *,
    screen_completed: bool,
    candidate_screen_succeeded: bool,
    candidate_raw_probe_row_count: int,
    candidate_filtered_probe_row_count: int,
    candidate_accepted_ball_frame_count: int,
) -> str:
    if not screen_completed or not candidate_screen_succeeded:
        return SCREEN_EXECUTION_FAILURE
    if candidate_raw_probe_row_count <= 0:
        return ROOT_CAUSE_AUXILIARY_PROBE_ZERO_RAW_ROWS
    if candidate_filtered_probe_row_count <= 0:
        return ROOT_CAUSE_AUXILIARY_PROBE_ROWS_FILTERED_OUT
    if candidate_accepted_ball_frame_count <= 0:
        return ROOT_CAUSE_ACCEPTED_LAYER_COLLAPSE_AFTER_PROBE
    return ROOT_CAUSE_INSUFFICIENT_PRODUCT_LIFT


def recommended_fix_class_for_root_cause(root_cause_class: str) -> str:
    if root_cause_class == SCREEN_EXECUTION_FAILURE:
        return RECOMMENDED_FIX_EXECUTION_PLUMBING
    if root_cause_class == ROOT_CAUSE_AUXILIARY_PROBE_ZERO_RAW_ROWS:
        return RECOMMENDED_FIX_MODEL_DATA_QUALITY
    if root_cause_class == ROOT_CAUSE_AUXILIARY_PROBE_ROWS_FILTERED_OUT:
        return RECOMMENDED_FIX_PROBE_INTEGRATION_BEHAVIOR
    if root_cause_class == ROOT_CAUSE_ACCEPTED_LAYER_COLLAPSE_AFTER_PROBE:
        return RECOMMENDED_FIX_ACCEPTANCE_PIPELINE_BEHAVIOR
    return RECOMMENDED_FIX_MODEL_DATA_QUALITY


def classify_change_from_previous_candidate(
    *,
    candidate_max_proposal_detected_frames: int,
    previous_candidate_max_proposal_detected_frames: int,
    candidate_raw_probe_row_count: int,
    previous_candidate_raw_probe_row_count: int,
    candidate_filtered_probe_row_count: int,
    previous_candidate_filtered_probe_row_count: int,
    candidate_accepted_ball_frame_count: int,
    previous_candidate_accepted_ball_frame_count: int,
    candidate_controlled_possession_frames: int,
    previous_candidate_controlled_possession_frames: int,
    candidate_ball_track_viable: bool,
    previous_candidate_ball_track_viable: bool,
) -> str:
    if (
        candidate_ball_track_viable != previous_candidate_ball_track_viable
        or candidate_controlled_possession_frames > previous_candidate_controlled_possession_frames
    ):
        return CHANGE_FROM_PREVIOUS_PRODUCT_IMPROVEMENT
    if candidate_accepted_ball_frame_count > previous_candidate_accepted_ball_frame_count:
        return CHANGE_FROM_PREVIOUS_ACCEPTED_LAYER_IMPROVEMENT_ONLY
    if (
        candidate_filtered_probe_row_count > previous_candidate_filtered_probe_row_count
        or candidate_raw_probe_row_count > previous_candidate_raw_probe_row_count
    ):
        return CHANGE_FROM_PREVIOUS_PROBE_LAYER_IMPROVEMENT_ONLY
    if candidate_max_proposal_detected_frames > previous_candidate_max_proposal_detected_frames:
        return CHANGE_FROM_PREVIOUS_PROPOSAL_GENERATION_IMPROVEMENT_ONLY
    return CHANGE_FROM_PREVIOUS_NO_OBSERVABLE_IMPROVEMENT


def recommended_fix_focus_for_failure(
    *,
    candidate_max_proposal_detected_frames: int,
    candidate_raw_probe_row_count: int,
    candidate_filtered_probe_row_count: int,
    candidate_accepted_ball_frame_count: int,
) -> str:
    if candidate_max_proposal_detected_frames <= 0:
        return RECOMMENDED_FIX_FOCUS_PROPOSAL_SIGNAL_GENERATION
    if candidate_raw_probe_row_count <= 0:
        return RECOMMENDED_FIX_FOCUS_RAW_PROBE_MATERIALIZATION
    if candidate_filtered_probe_row_count <= 0:
        return RECOMMENDED_FIX_FOCUS_PROBE_FILTERING_BEHAVIOR
    if candidate_accepted_ball_frame_count <= 0:
        return RECOMMENDED_FIX_FOCUS_ACCEPTED_LAYER_BEHAVIOR
    return RECOMMENDED_FIX_FOCUS_PRODUCT_LIFT_GAP


def _event_family_count(summary: dict[str, object]) -> int:
    if "eventFamilyCount" in summary:
        return _safe_int(summary.get("eventFamilyCount"), 0)
    event_types = summary.get("eventTypes")
    if not isinstance(event_types, dict):
        return 0
    return sum(1 for count in event_types.values() if _safe_int(count, 0) > 0)


def _truth_gate_reasons(summary: dict[str, object]) -> list[str]:
    return _string_list(summary.get("truthGateReasons"))


def _summary_surface_field_value(
    *,
    field_name: str,
    proof_summary: dict[str, object],
    selected_cluster_summary: dict[str, object],
    ball_truth_layers: dict[str, object],
) -> dict[str, object]:
    accepted_ball_summary = (
        dict(ball_truth_layers.get("acceptedBall"))
        if isinstance(ball_truth_layers.get("acceptedBall"), dict)
        else {}
    )
    accepted_ball_rows_summary = (
        dict(accepted_ball_summary.get("summary"))
        if isinstance(accepted_ball_summary.get("summary"), dict)
        else {}
    )
    support_diagnostics = (
        dict(ball_truth_layers.get("supportDiagnostics"))
        if isinstance(ball_truth_layers.get("supportDiagnostics"), dict)
        else {}
    )
    if field_name == "acceptedBallFrames":
        return {
            "proofSummary": _safe_int(proof_summary.get("acceptedBallFrames"), 0),
            "selectedClusterSummary": _safe_int(selected_cluster_summary.get("acceptedBallFrames"), 0),
            "ballTruthLayers": _safe_int(accepted_ball_rows_summary.get("frameCount"), 0),
        }
    if field_name == "supportedAcceptedBallRatio":
        return {
            "proofSummary": _safe_float(proof_summary.get("supportedAcceptedBallRatio"), 0.0),
            "selectedClusterSummary": _safe_float(selected_cluster_summary.get("supportedAcceptedBallRatio"), 0.0),
            "ballTruthLayers": _safe_float(support_diagnostics.get("supportedAcceptedBallRatio"), 0.0),
        }
    if field_name == "controlledPossessionFrames":
        return {
            "proofSummary": _safe_int(proof_summary.get("controlledPossessionFrames"), 0),
            "selectedClusterSummary": _safe_int(selected_cluster_summary.get("controlledPossessionFrames"), 0),
        }
    if field_name == "eventFamilyCount":
        return {
            "proofSummary": _event_family_count(proof_summary),
            "selectedClusterSummary": _event_family_count(selected_cluster_summary),
        }
    if field_name == "truthGateReasons":
        return {
            "proofSummary": _truth_gate_reasons(proof_summary),
            "selectedClusterSummary": _truth_gate_reasons(selected_cluster_summary),
        }
    return {}


def _values_differ(left: object, right: object) -> bool:
    if isinstance(left, float) or isinstance(right, float):
        return abs(_safe_float(left, 0.0) - _safe_float(right, 0.0)) > 1e-6
    if isinstance(left, list) or isinstance(right, list):
        return _string_list(left) != _string_list(right)
    return left != right


def analyze_summary_surface_drift(
    *,
    proof_summary: dict[str, object],
    selected_cluster_summary: dict[str, object],
    ball_truth_layers: dict[str, object],
) -> dict[str, object]:
    reasons: list[str] = []
    missing_required_fields = [
        field_name
        for field_name in REQUIRED_JUDGE_FIELDS
        if field_name not in proof_summary and field_name in selected_cluster_summary
    ]
    for field_name in missing_required_fields:
        reasons.append(f"missing_proof_summary_required_field:{field_name}")

    field_values: dict[str, dict[str, object]] = {}
    for field_name in REQUIRED_JUDGE_FIELDS:
        values = _summary_surface_field_value(
            field_name=field_name,
            proof_summary=proof_summary,
            selected_cluster_summary=selected_cluster_summary,
            ball_truth_layers=ball_truth_layers,
        )
        if not values:
            continue
        field_values[field_name] = values
        if "proofSummary" in values and "selectedClusterSummary" in values and _values_differ(
            values["proofSummary"],
            values["selectedClusterSummary"],
        ):
            reasons.append(f"proof_summary_vs_selected_cluster_mismatch:{field_name}")
        if "proofSummary" in values and "ballTruthLayers" in values and _values_differ(
            values["proofSummary"],
            values["ballTruthLayers"],
        ):
            reasons.append(f"proof_summary_vs_ball_truth_layers_mismatch:{field_name}")

    return {
        "detected": bool(reasons),
        "reasons": reasons,
        "requiredJudgeFields": list(REQUIRED_JUDGE_FIELDS),
        "missingProofSummaryRequiredFields": missing_required_fields,
        "fieldValues": field_values,
    }


def analyze_calibration_suspicion(
    *,
    candidate_max_proposal_detected_frames: int,
    candidate_raw_probe_row_count: int,
    candidate_filtered_probe_row_count: int,
    candidate_accepted_ball_frame_count: int,
    candidate_pitch_polygon_rejected_frames: int,
) -> dict[str, object]:
    reasons: list[str] = []
    if (
        candidate_max_proposal_detected_frames > 0
        and candidate_raw_probe_row_count <= 0
        and candidate_filtered_probe_row_count <= 0
        and candidate_accepted_ball_frame_count <= 0
        and candidate_pitch_polygon_rejected_frames > 0
    ):
        reasons.append("pitch_polygon_rejected_after_upstream_proposals")
    return {
        "detected": bool(reasons),
        "reasons": reasons,
    }


def next_implementation_batch_recommendation(
    *,
    candidate_name: str,
    summary_surface_drift_detected: bool,
    calibration_suspicion_detected: bool,
    recommended_fix_focus: str,
) -> str:
    if summary_surface_drift_detected:
        return "canonical_proof_summary_contract_v1"
    if calibration_suspicion_detected:
        return "pitch_homography_hardening_v1"
    if recommended_fix_focus == RECOMMENDED_FIX_FOCUS_PROPOSAL_SIGNAL_GENERATION:
        return f"{candidate_name}_proposal_signal_generation_fix_v1"
    if recommended_fix_focus == RECOMMENDED_FIX_FOCUS_RAW_PROBE_MATERIALIZATION:
        return f"{candidate_name}_raw_probe_materialization_fix_v1"
    if recommended_fix_focus == RECOMMENDED_FIX_FOCUS_PROBE_FILTERING_BEHAVIOR:
        return f"{candidate_name}_probe_filtering_behavior_fix_v1"
    if recommended_fix_focus == RECOMMENDED_FIX_FOCUS_ACCEPTED_LAYER_BEHAVIOR:
        return f"{candidate_name}_accepted_layer_behavior_fix_v1"
    return f"{candidate_name}_product_lift_gap_fix_v1"


def _bundle_layer_rows(bundle_root: Path) -> dict[str, list[dict[str, object]]]:
    ball_truth_layers = _load_json(bundle_root / "ball_truth_layers.json")
    accepted_ball = (
        dict(ball_truth_layers.get("acceptedBall")) if isinstance(ball_truth_layers.get("acceptedBall"), dict) else {}
    )
    probe_observed = (
        dict(ball_truth_layers.get("probeObservedBall"))
        if isinstance(ball_truth_layers.get("probeObservedBall"), dict)
        else {}
    )
    return {
        "acceptedBallRows": _rows_from_payload(accepted_ball.get("rows")),
        "filteredProbeRows": _rows_from_payload(probe_observed.get("filteredRows")),
        "rawProbeRows": _rows_from_payload(probe_observed.get("rawRows")),
    }


def _load_selected_cluster_delta(bundle_root: Path) -> dict[str, object]:
    path = bundle_root / "selected_cluster_delta.json"
    if not path.exists():
        return {}
    return _load_json(path)


def _load_recovery_profile_matrix(bundle_root: Path) -> dict[str, object]:
    payload = _load_json(bundle_root / "recovery_profile_matrix.json")
    normalized_profiles: list[dict[str, object]] = []
    raw_profiles = payload.get("profiles")
    if isinstance(raw_profiles, list):
        for raw_profile in raw_profiles:
            if not isinstance(raw_profile, dict):
                continue
            proposal_player_ranked_detected_frames = _safe_int(
                raw_profile.get("proposalPlayerRankedDetectedFrames"),
                0,
            )
            proposal_direct_seed_detected_frames = _safe_int(
                raw_profile.get("proposalDirectSeedDetectedFrames"),
                0,
            )
            normalized_profiles.append(
                {
                    "name": str(raw_profile.get("name") or ""),
                    "selectedFrames": _safe_int(raw_profile.get("selectedFrames"), 0),
                    "selectedScore": raw_profile.get("selectedScore"),
                    "selectedEdgeFrameShare": raw_profile.get("selectedEdgeFrameShare"),
                    "proposalPlayerRankedDetectedFrames": proposal_player_ranked_detected_frames,
                    "proposalDirectSeedDetectedFrames": proposal_direct_seed_detected_frames,
                    "proposalDirectSeedRawHitFilteredOutFrames": _safe_int(
                        raw_profile.get("proposalDirectSeedRawHitFilteredOutFrames"),
                        0,
                    ),
                    "proposalDetectedFrames": (
                        proposal_player_ranked_detected_frames + proposal_direct_seed_detected_frames
                    ),
                }
            )
    normalized_profiles.sort(key=lambda profile: str(profile.get("name") or ""))
    return {
        "selectedProfileName": payload.get("selectedProfileName"),
        "profiles": normalized_profiles,
        "maxProposalDetectedFramesAcrossProfiles": max(
            (_safe_int(profile.get("proposalDetectedFrames"), 0) for profile in normalized_profiles),
            default=0,
        ),
    }


def _bundle_summary(bundle_root: Path) -> dict[str, object]:
    raw_proof_summary = _load_json(bundle_root / "proof_summary.json")
    ball_pipeline_trace = _load_json(bundle_root / "ball_pipeline_trace.json")
    ball_truth_layers = _load_json(bundle_root / "ball_truth_layers.json")
    selected_cluster_delta = _load_selected_cluster_delta(bundle_root)
    selected_cluster_after = (
        dict(selected_cluster_delta.get("after"))
        if isinstance(selected_cluster_delta.get("after"), dict)
        else {}
    )
    proof_summary = build_canonical_proof_summary(raw_proof_summary, selected_cluster_after)
    layer_rows = _bundle_layer_rows(bundle_root)
    recovery_profile_matrix = _load_recovery_profile_matrix(bundle_root)
    return {
        "bundleRoot": str(bundle_root),
        "bundleName": bundle_root.name,
        "proofSummary": proof_summary,
        "ballTruthLayers": ball_truth_layers,
        "ballPipelineTrace": ball_pipeline_trace,
        "selectedClusterDelta": selected_cluster_delta,
        "recoveryProfileMatrix": recovery_profile_matrix,
        **layer_rows,
    }


def _frame_level_layer_delta(
    *,
    candidate_rows: list[dict[str, object]],
    baseline_rows: list[dict[str, object]],
) -> dict[str, object]:
    candidate_frame_ids = _frame_ids(candidate_rows)
    baseline_frame_ids = _frame_ids(baseline_rows)
    candidate_frame_set = set(candidate_frame_ids)
    baseline_frame_set = set(baseline_frame_ids)
    return {
        "candidateFrameIds": candidate_frame_ids,
        "baselineFrameIds": baseline_frame_ids,
        "sharedFrameIds": sorted(candidate_frame_set & baseline_frame_set),
        "candidateOnlyFrameIds": sorted(candidate_frame_set - baseline_frame_set),
        "baselineOnlyFrameIds": sorted(baseline_frame_set - candidate_frame_set),
    }


def _profile_lookup(matrix_summary: dict[str, object]) -> dict[str, dict[str, object]]:
    profiles = matrix_summary.get("profiles")
    if not isinstance(profiles, list):
        return {}
    lookup: dict[str, dict[str, object]] = {}
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        profile_name = str(profile.get("name") or "")
        if profile_name:
            lookup[profile_name] = dict(profile)
    return lookup


def _build_profile_matrix_delta(
    *,
    candidate_name: str,
    previous_candidate_name: str,
    candidate_matrix: dict[str, object],
    previous_candidate_matrix: dict[str, object],
    baseline_matrix: dict[str, object],
) -> dict[str, object]:
    candidate_lookup = _profile_lookup(candidate_matrix)
    previous_lookup = _profile_lookup(previous_candidate_matrix)
    baseline_lookup = _profile_lookup(baseline_matrix)
    profile_names = sorted(set(candidate_lookup) | set(previous_lookup) | set(baseline_lookup))
    profiles: list[dict[str, object]] = []
    for profile_name in profile_names:
        candidate_profile = candidate_lookup.get(profile_name, {})
        previous_profile = previous_lookup.get(profile_name, {})
        baseline_profile = baseline_lookup.get(profile_name, {})
        candidate_detected_frames = _safe_int(candidate_profile.get("proposalDetectedFrames"), 0)
        previous_detected_frames = _safe_int(previous_profile.get("proposalDetectedFrames"), 0)
        baseline_detected_frames = _safe_int(baseline_profile.get("proposalDetectedFrames"), 0)
        profiles.append(
            {
                "profileName": profile_name,
                "candidateProposalDetectedFrames": candidate_detected_frames,
                "previousCandidateProposalDetectedFrames": previous_detected_frames,
                "baselineProposalDetectedFrames": baseline_detected_frames,
                "candidateSelectedFrames": _safe_int(candidate_profile.get("selectedFrames"), 0),
                "previousCandidateSelectedFrames": _safe_int(previous_profile.get("selectedFrames"), 0),
                "baselineSelectedFrames": _safe_int(baseline_profile.get("selectedFrames"), 0),
                "candidateProposalDetectedFrameDeltaVsPrevious": (
                    candidate_detected_frames - previous_detected_frames
                ),
                "candidateProposalDetectedFrameDeltaVsBaseline": (
                    candidate_detected_frames - baseline_detected_frames
                ),
            }
        )
    return {
        "generatedAt": _utc_now_iso(),
        "trainingCandidateName": candidate_name,
        "previousCandidateName": previous_candidate_name,
        "candidateSelectedProfileName": candidate_matrix.get("selectedProfileName"),
        "previousCandidateSelectedProfileName": previous_candidate_matrix.get("selectedProfileName"),
        "baselineSelectedProfileName": baseline_matrix.get("selectedProfileName"),
        "candidateMaxProposalDetectedFramesAcrossProfiles": _safe_int(
            candidate_matrix.get("maxProposalDetectedFramesAcrossProfiles"),
            0,
        ),
        "previousCandidateMaxProposalDetectedFramesAcrossProfiles": _safe_int(
            previous_candidate_matrix.get("maxProposalDetectedFramesAcrossProfiles"),
            0,
        ),
        "baselineMaxProposalDetectedFramesAcrossProfiles": _safe_int(
            baseline_matrix.get("maxProposalDetectedFramesAcrossProfiles"),
            0,
        ),
        "profiles": profiles,
    }


def _unsupported_edge_share(proof_summary: dict[str, object]) -> float:
    accepted_ball_frames = _safe_int(proof_summary.get("acceptedBallFrames"), 0)
    if accepted_ball_frames <= 0:
        return 0.0
    return _safe_int(proof_summary.get("unsupportedAcceptedEdgeFrames"), 0) / accepted_ball_frames


def _stage_count_delta(candidate_value: int, previous_value: int, baseline_value: int) -> dict[str, object]:
    return {
        "candidateValue": candidate_value,
        "previousCandidateValue": previous_value,
        "baselineValue": baseline_value,
        "candidateDeltaVsPrevious": candidate_value - previous_value,
        "candidateDeltaVsBaseline": candidate_value - baseline_value,
    }


def _stage_float_delta(candidate_value: float, previous_value: float, baseline_value: float) -> dict[str, object]:
    return {
        "candidateValue": candidate_value,
        "previousCandidateValue": previous_value,
        "baselineValue": baseline_value,
        "candidateDeltaVsPrevious": round(candidate_value - previous_value, 6),
        "candidateDeltaVsBaseline": round(candidate_value - baseline_value, 6),
    }


def _build_stage_wise_delta(
    *,
    candidate_bundle: dict[str, object],
    previous_candidate_bundle: dict[str, object],
    baseline_bundle: dict[str, object],
    candidate_max_proposal_detected_frames: int,
    previous_candidate_max_proposal_detected_frames: int,
    baseline_max_proposal_detected_frames: int,
    candidate_raw_probe_row_count: int,
    previous_candidate_raw_probe_row_count: int,
    baseline_raw_probe_row_count: int,
    candidate_filtered_probe_row_count: int,
    previous_candidate_filtered_probe_row_count: int,
    baseline_filtered_probe_row_count: int,
    candidate_accepted_ball_frame_count: int,
    previous_candidate_accepted_ball_frame_count: int,
    baseline_accepted_ball_frame_count: int,
) -> dict[str, object]:
    candidate_proof_summary = dict(candidate_bundle.get("proofSummary") or {})
    previous_candidate_proof_summary = dict(previous_candidate_bundle.get("proofSummary") or {})
    baseline_proof_summary = dict(baseline_bundle.get("proofSummary") or {})
    return {
        "proposalDetectionsAcrossRecoveryProfiles": _stage_count_delta(
            candidate_max_proposal_detected_frames,
            previous_candidate_max_proposal_detected_frames,
            baseline_max_proposal_detected_frames,
        ),
        "rawProbeRows": _stage_count_delta(
            candidate_raw_probe_row_count,
            previous_candidate_raw_probe_row_count,
            baseline_raw_probe_row_count,
        ),
        "filteredProbeRows": _stage_count_delta(
            candidate_filtered_probe_row_count,
            previous_candidate_filtered_probe_row_count,
            baseline_filtered_probe_row_count,
        ),
        "acceptedBallFrames": _stage_count_delta(
            candidate_accepted_ball_frame_count,
            previous_candidate_accepted_ball_frame_count,
            baseline_accepted_ball_frame_count,
        ),
        "supportedAcceptedRatio": _stage_float_delta(
            _safe_float(candidate_proof_summary.get("supportedAcceptedBallRatio"), 0.0),
            _safe_float(previous_candidate_proof_summary.get("supportedAcceptedBallRatio"), 0.0),
            _safe_float(baseline_proof_summary.get("supportedAcceptedBallRatio"), 0.0),
        ),
        "rawEdgeShare": _stage_float_delta(
            _safe_float(candidate_proof_summary.get("candidateEdgeShare"), 0.0),
            _safe_float(previous_candidate_proof_summary.get("candidateEdgeShare"), 0.0),
            _safe_float(baseline_proof_summary.get("candidateEdgeShare"), 0.0),
        ),
        "unsupportedEdgeShare": _stage_float_delta(
            _unsupported_edge_share(candidate_proof_summary),
            _unsupported_edge_share(previous_candidate_proof_summary),
            _unsupported_edge_share(baseline_proof_summary),
        ),
        "gapProfile": {
            "candidateUnknownGapCount": _safe_int(candidate_proof_summary.get("unknownGapCount"), 0),
            "candidateLongestUnknownGapFrames": _safe_int(
                candidate_proof_summary.get("longestUnknownGapFrames"),
                0,
            ),
            "previousCandidateUnknownGapCount": _safe_int(
                previous_candidate_proof_summary.get("unknownGapCount"),
                0,
            ),
            "previousCandidateLongestUnknownGapFrames": _safe_int(
                previous_candidate_proof_summary.get("longestUnknownGapFrames"),
                0,
            ),
            "baselineUnknownGapCount": _safe_int(baseline_proof_summary.get("unknownGapCount"), 0),
            "baselineLongestUnknownGapFrames": _safe_int(
                baseline_proof_summary.get("longestUnknownGapFrames"),
                0,
            ),
        },
        "controlledPossessionFrames": _stage_count_delta(
            _safe_int(candidate_proof_summary.get("controlledPossessionFrames"), 0),
            _safe_int(previous_candidate_proof_summary.get("controlledPossessionFrames"), 0),
            _safe_int(baseline_proof_summary.get("controlledPossessionFrames"), 0),
        ),
        "eventFamilyCoverage": _stage_count_delta(
            _event_family_count(candidate_proof_summary),
            _event_family_count(previous_candidate_proof_summary),
            _event_family_count(baseline_proof_summary),
        ),
    }


def _brainstorm_fixes(
    *,
    recommended_fix_class: str,
    recommended_fix_focus: str,
    change_from_previous_candidate_class: str,
    candidate_name: str,
    previous_candidate_name: str,
    candidate_max_proposal_detected_frames: int,
    previous_candidate_max_proposal_detected_frames: int,
    baseline_max_proposal_detected_frames: int,
    candidate_raw_probe_row_count: int,
    baseline_raw_probe_row_count: int,
    summary_surface_drift_detected: bool,
    calibration_suspicion_detected: bool,
    next_implementation_batch_recommendation: str,
) -> list[str]:
    if summary_surface_drift_detected:
        return [
            (
                f"Run {next_implementation_batch_recommendation} next because the saved proof surfaces still drift on required judge-facing fields."
            ),
            (
                f"Do not treat the summary-contract repair as a lane change. Keep the roadmap on evaluate_touchline_detector_candidate while preserving {recommended_fix_focus} as the underlying blocker focus."
            ),
        ]
    if calibration_suspicion_detected:
        return [
            (
                f"Run {next_implementation_batch_recommendation} next because upstream proposal signal exists but collapses at projection or pitch-polygon handling."
            ),
            "Do not spend the next batch on new detector training until calibration behavior is verified against the saved proof artifacts.",
        ]
    if recommended_fix_focus == RECOMMENDED_FIX_FOCUS_PROPOSAL_SIGNAL_GENERATION:
        return [
            (
                f"Keep the roadmap on evaluate_touchline_detector_candidate and stay in {recommended_fix_class}, "
                f"but narrow the next corrective batch to {recommended_fix_focus}."
            ),
            (
                f"Compare the v3 training export against the diagnostic baseline-control proposal frames because "
                f"{candidate_name} still produced {candidate_max_proposal_detected_frames} proposal-detected frames "
                f"across recovery profiles while {previous_candidate_name} produced "
                f"{previous_candidate_max_proposal_detected_frames} and the diagnostic baseline produced "
                f"{baseline_max_proposal_detected_frames}."
            ),
            (
                f"Do not spend the next batch on filtering or acceptance logic yet. The saved artifacts still show "
                f"{candidate_name} at {candidate_raw_probe_row_count} raw probe rows versus "
                f"{baseline_raw_probe_row_count} for the diagnostic baseline, so the missing signal starts before row materialization."
            ),
        ]
    if recommended_fix_focus == RECOMMENDED_FIX_FOCUS_RAW_PROBE_MATERIALIZATION:
        return [
            (
                f"Keep the fix lane in {recommended_fix_class}, but target {recommended_fix_focus} because proposals exist "
                "and still do not become raw probe rows."
            ),
            "Inspect how proposal detections are converted into raw observed-ball rows before touching filtering or acceptance logic.",
        ]
    if recommended_fix_focus == RECOMMENDED_FIX_FOCUS_PROBE_FILTERING_BEHAVIOR:
        return [
            "Keep the model fixed for the next batch and inspect the probe filtering gates that removed raw auxiliary detections.",
            "Use the saved raw-versus-filtered frame deltas to target the exact filter that suppresses the auxiliary detector output.",
        ]
    if recommended_fix_focus == RECOMMENDED_FIX_FOCUS_ACCEPTED_LAYER_BEHAVIOR:
        return [
            "Focus the next corrective batch on accepted-layer behavior because filtered probe rows exist but still collapse before acceptance.",
            "Inspect acceptance merge behavior before spending another batch on dataset or training changes.",
        ]
    return [
        (
            f"Treat the next corrective batch as {recommended_fix_class} and target product lift directly because the auxiliary detector now reaches the accepted layer."
        ),
        (
            f"Use the saved delta artifacts to explain why {candidate_name} still loses even after the observable improvement class {change_from_previous_candidate_class}."
        ),
    ]


def _build_markdown_batch_outcome(batch_outcome_analysis: dict[str, object]) -> str:
    brainstorm_fixes = batch_outcome_analysis.get("brainstormFixes")
    brainstorm_fixes = brainstorm_fixes if isinstance(brainstorm_fixes, list) else []
    lines = [
        "# Batch Outcome Analysis",
        "",
        f"- Batch goal: {batch_outcome_analysis.get('batchGoal')}",
        f"- Goal achieved: {bool(batch_outcome_analysis.get('goalAchieved'))}",
        f"- Roadmap advance allowed: {bool(batch_outcome_analysis.get('roadmapAdvanceAllowed'))}",
        f"- Next recommended next lever: {batch_outcome_analysis.get('nextRecommendedNextLever')}",
        f"- Primary blocker: {batch_outcome_analysis.get('primaryBlocker')}",
        f"- Root cause class: {batch_outcome_analysis.get('rootCauseClass')}",
        f"- Change from previous candidate class: {batch_outcome_analysis.get('changeFromPreviousCandidateClass')}",
        f"- Recommended fix class: {batch_outcome_analysis.get('recommendedFixClass')}",
        f"- Recommended fix focus: {batch_outcome_analysis.get('recommendedFixFocus')}",
        f"- Summary surface drift detected: {bool(batch_outcome_analysis.get('summarySurfaceDriftDetected'))}",
        f"- Calibration suspicion detected: {bool(batch_outcome_analysis.get('calibrationSuspicionDetected'))}",
        f"- Next implementation batch recommendation: {batch_outcome_analysis.get('nextImplementationBatchRecommendation')}",
        "",
        "## English Summary",
        "",
        str(batch_outcome_analysis.get("englishSummary") or ""),
        "",
        "## English Decision",
        "",
        str(batch_outcome_analysis.get("englishDecision") or ""),
        "",
        "## Brainstorm Fixes",
        "",
    ]
    for fix in brainstorm_fixes:
        lines.append(f"- {fix}")
    return "\n".join(lines).strip() + "\n"


def run_touchline_detector_candidate_failure_analysis(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str | None = DEFAULT_CANDIDATE_NAME,
    previous_candidate_name: str | None = DEFAULT_PREVIOUS_CANDIDATE_NAME,
) -> dict[str, object]:
    storage_root = Path(storage_root)
    resolved_candidate_name = resolve_active_candidate_name(storage_root, candidate_name)
    resolved_previous_candidate_name = resolve_previous_candidate_name(
        storage_root,
        resolved_candidate_name,
        previous_candidate_name,
    )

    paths = _artifact_paths(storage_root, resolved_candidate_name)
    previous_paths = _artifact_paths(storage_root, resolved_previous_candidate_name)
    evaluation_summary = _load_json(paths["evaluationSummaryPath"])
    screen_matrix = _load_json(paths["screenMatrixPath"])
    proof_report = _load_json(paths["proofReportPath"])
    evaluation_batch_outcome = _load_json(paths["evaluationBatchOutcomePath"])
    previous_evaluation_summary = _load_json(previous_paths["evaluationSummaryPath"])
    previous_screen_matrix = _load_json(previous_paths["screenMatrixPath"])
    previous_proof_report = _load_json(previous_paths["proofReportPath"])
    previous_failure_analysis_summary = None
    previous_failure_analysis_path = (
        previous_paths["failureAnalysisRoot"] / "failure_analysis_summary.json"
    )
    if previous_failure_analysis_path.exists():
        previous_failure_analysis_summary = _load_json(previous_failure_analysis_path)

    candidate_bundle_root = _candidate_proof_bundle_root(proof_report, storage_root, resolved_candidate_name)
    previous_candidate_bundle_root = _candidate_proof_bundle_root(
        previous_proof_report,
        storage_root,
        resolved_previous_candidate_name,
    )
    baseline_control_bundle_root = _baseline_control_proof_bundle_root(proof_report, storage_root)
    candidate_bundle = _bundle_summary(candidate_bundle_root)
    previous_candidate_bundle = _bundle_summary(previous_candidate_bundle_root)
    baseline_bundle = _bundle_summary(baseline_control_bundle_root)

    candidate_detector_label = str(
        (
            dict(proof_report.get("candidateBaselineResult"))
            if isinstance(proof_report.get("candidateBaselineResult"), dict)
            else {}
        ).get("detectorLabel")
        or f"{resolved_candidate_name}_probe_assist"
    )
    previous_candidate_detector_label = str(
        (
            dict(previous_proof_report.get("candidateBaselineResult"))
            if isinstance(previous_proof_report.get("candidateBaselineResult"), dict)
            else {}
        ).get("detectorLabel")
        or f"{resolved_previous_candidate_name}_probe_assist"
    )

    screen_cells = [dict(cell) for cell in (screen_matrix.get("cells") or []) if isinstance(cell, dict)]
    previous_screen_cells = [
        dict(cell) for cell in (previous_screen_matrix.get("cells") or []) if isinstance(cell, dict)
    ]
    candidate_screen_cell = next(
        (cell for cell in screen_cells if str(cell.get("detectorLabel") or "") == candidate_detector_label),
        {},
    )
    previous_candidate_screen_cell = next(
        (
            cell
            for cell in previous_screen_cells
            if str(cell.get("detectorLabel") or "") == previous_candidate_detector_label
        ),
        {},
    )
    baseline_screen_cell = next(
        (cell for cell in screen_cells if str(cell.get("detectorLabel") or "") == BASELINE_DETECTOR_LABEL),
        {},
    )

    candidate_raw_probe_row_count = len(candidate_bundle["rawProbeRows"])
    candidate_filtered_probe_row_count = len(candidate_bundle["filteredProbeRows"])
    candidate_accepted_ball_frame_count = len(candidate_bundle["acceptedBallRows"])
    candidate_controlled_possession_frames = _safe_int(
        candidate_bundle["proofSummary"].get("controlledPossessionFrames"),
        0,
    )
    candidate_ball_track_viable = bool(candidate_bundle["proofSummary"].get("ballTrackViable"))
    candidate_max_proposal_detected_frames = _safe_int(
        candidate_bundle["recoveryProfileMatrix"].get("maxProposalDetectedFramesAcrossProfiles"),
        0,
    )
    candidate_selected_cluster_summary = (
        dict(candidate_bundle["selectedClusterDelta"].get("before"))
        if isinstance(candidate_bundle.get("selectedClusterDelta"), dict)
        and isinstance(candidate_bundle["selectedClusterDelta"].get("before"), dict)
        else {}
    )

    previous_candidate_raw_probe_row_count = len(previous_candidate_bundle["rawProbeRows"])
    previous_candidate_filtered_probe_row_count = len(previous_candidate_bundle["filteredProbeRows"])
    previous_candidate_accepted_ball_frame_count = len(previous_candidate_bundle["acceptedBallRows"])
    previous_candidate_controlled_possession_frames = _safe_int(
        previous_candidate_bundle["proofSummary"].get("controlledPossessionFrames"),
        0,
    )
    previous_candidate_ball_track_viable = bool(previous_candidate_bundle["proofSummary"].get("ballTrackViable"))
    previous_candidate_max_proposal_detected_frames = _safe_int(
        previous_candidate_bundle["recoveryProfileMatrix"].get("maxProposalDetectedFramesAcrossProfiles"),
        0,
    )

    baseline_raw_probe_row_count = len(baseline_bundle["rawProbeRows"])
    baseline_filtered_probe_row_count = len(baseline_bundle["filteredProbeRows"])
    baseline_accepted_ball_frame_count = len(baseline_bundle["acceptedBallRows"])
    baseline_max_proposal_detected_frames = _safe_int(
        baseline_bundle["recoveryProfileMatrix"].get("maxProposalDetectedFramesAcrossProfiles"),
        0,
    )

    root_cause_class = classify_failure_root_cause(
        screen_completed=bool(evaluation_summary.get("screenCompleted")),
        candidate_screen_succeeded=bool(candidate_screen_cell.get("screenSucceeded", True)),
        candidate_raw_probe_row_count=candidate_raw_probe_row_count,
        candidate_filtered_probe_row_count=candidate_filtered_probe_row_count,
        candidate_accepted_ball_frame_count=candidate_accepted_ball_frame_count,
    )
    change_from_previous_candidate_class = classify_change_from_previous_candidate(
        candidate_max_proposal_detected_frames=candidate_max_proposal_detected_frames,
        previous_candidate_max_proposal_detected_frames=previous_candidate_max_proposal_detected_frames,
        candidate_raw_probe_row_count=candidate_raw_probe_row_count,
        previous_candidate_raw_probe_row_count=previous_candidate_raw_probe_row_count,
        candidate_filtered_probe_row_count=candidate_filtered_probe_row_count,
        previous_candidate_filtered_probe_row_count=previous_candidate_filtered_probe_row_count,
        candidate_accepted_ball_frame_count=candidate_accepted_ball_frame_count,
        previous_candidate_accepted_ball_frame_count=previous_candidate_accepted_ball_frame_count,
        candidate_controlled_possession_frames=candidate_controlled_possession_frames,
        previous_candidate_controlled_possession_frames=previous_candidate_controlled_possession_frames,
        candidate_ball_track_viable=candidate_ball_track_viable,
        previous_candidate_ball_track_viable=previous_candidate_ball_track_viable,
    )
    recommended_fix_class = recommended_fix_class_for_root_cause(root_cause_class)
    recommended_fix_focus = recommended_fix_focus_for_failure(
        candidate_max_proposal_detected_frames=candidate_max_proposal_detected_frames,
        candidate_raw_probe_row_count=candidate_raw_probe_row_count,
        candidate_filtered_probe_row_count=candidate_filtered_probe_row_count,
        candidate_accepted_ball_frame_count=candidate_accepted_ball_frame_count,
    )
    summary_surface_drift_analysis = analyze_summary_surface_drift(
        proof_summary=dict(candidate_bundle["proofSummary"]),
        selected_cluster_summary=candidate_selected_cluster_summary,
        ball_truth_layers=dict(candidate_bundle["ballTruthLayers"]),
    )
    calibration_suspicion_analysis = analyze_calibration_suspicion(
        candidate_max_proposal_detected_frames=candidate_max_proposal_detected_frames,
        candidate_raw_probe_row_count=candidate_raw_probe_row_count,
        candidate_filtered_probe_row_count=candidate_filtered_probe_row_count,
        candidate_accepted_ball_frame_count=candidate_accepted_ball_frame_count,
        candidate_pitch_polygon_rejected_frames=_safe_int(
            candidate_selected_cluster_summary.get("bestProposalDirectSeedPitchPolygonRejectedFrames"),
            _safe_int(candidate_bundle["proofSummary"].get("bestProposalDirectSeedPitchPolygonRejectedFrames"), 0),
        ),
    )
    next_batch_recommendation = next_implementation_batch_recommendation(
        candidate_name=resolved_candidate_name,
        summary_surface_drift_detected=bool(summary_surface_drift_analysis.get("detected")),
        calibration_suspicion_detected=bool(calibration_suspicion_analysis.get("detected")),
        recommended_fix_focus=recommended_fix_focus,
    )
    stage_wise_delta = _build_stage_wise_delta(
        candidate_bundle=candidate_bundle,
        previous_candidate_bundle=previous_candidate_bundle,
        baseline_bundle=baseline_bundle,
        candidate_max_proposal_detected_frames=candidate_max_proposal_detected_frames,
        previous_candidate_max_proposal_detected_frames=previous_candidate_max_proposal_detected_frames,
        baseline_max_proposal_detected_frames=baseline_max_proposal_detected_frames,
        candidate_raw_probe_row_count=candidate_raw_probe_row_count,
        previous_candidate_raw_probe_row_count=previous_candidate_raw_probe_row_count,
        baseline_raw_probe_row_count=baseline_raw_probe_row_count,
        candidate_filtered_probe_row_count=candidate_filtered_probe_row_count,
        previous_candidate_filtered_probe_row_count=previous_candidate_filtered_probe_row_count,
        baseline_filtered_probe_row_count=baseline_filtered_probe_row_count,
        candidate_accepted_ball_frame_count=candidate_accepted_ball_frame_count,
        previous_candidate_accepted_ball_frame_count=previous_candidate_accepted_ball_frame_count,
        baseline_accepted_ball_frame_count=baseline_accepted_ball_frame_count,
    )

    frame_level_probe_delta = {
        "generatedAt": _utc_now_iso(),
        "trainingCandidateName": resolved_candidate_name,
        "previousCandidateName": resolved_previous_candidate_name,
        "candidateDetectorLabel": candidate_detector_label,
        "baselineDetectorLabel": BASELINE_DETECTOR_LABEL,
        "layers": {
            "rawProbe": _frame_level_layer_delta(
                candidate_rows=candidate_bundle["rawProbeRows"],
                baseline_rows=baseline_bundle["rawProbeRows"],
            ),
            "filteredProbe": _frame_level_layer_delta(
                candidate_rows=candidate_bundle["filteredProbeRows"],
                baseline_rows=baseline_bundle["filteredProbeRows"],
            ),
            "acceptedBall": _frame_level_layer_delta(
                candidate_rows=candidate_bundle["acceptedBallRows"],
                baseline_rows=baseline_bundle["acceptedBallRows"],
            ),
        },
    }
    candidate_vs_baseline_delta = {
        "generatedAt": _utc_now_iso(),
        "trainingCandidateName": resolved_candidate_name,
        "evaluationBatchName": evaluation_summary.get("evaluationBatchName"),
        "screen": {
            "winningDetectorLabel": screen_matrix.get("screenWinningDetectorLabel"),
            "candidateDetectorLabel": candidate_detector_label,
            "candidateScreenViable": bool(candidate_screen_cell.get("viable")),
            "candidateScreenRecommendedProfileName": candidate_screen_cell.get("recommendedProfileName"),
            "baselineDetectorLabel": BASELINE_DETECTOR_LABEL,
            "baselineScreenViable": bool(baseline_screen_cell.get("viable")),
            "baselineScreenRecommendedProfileName": baseline_screen_cell.get("recommendedProfileName"),
        },
        "proof": {
            "candidateAcceptedBallFrames": _safe_int(
                candidate_bundle["proofSummary"].get("acceptedBallFrames"),
                candidate_accepted_ball_frame_count,
            ),
            "candidateControlledPossessionFrames": candidate_controlled_possession_frames,
            "candidateBallTrackViable": candidate_ball_track_viable,
            "candidateBallTrackEdgeFrameShare": _safe_float(
                candidate_bundle["proofSummary"].get("ballTrackEdgeFrameShare"),
                1.0,
            ),
            "baselineAcceptedBallFrames": _safe_int(
                baseline_bundle["proofSummary"].get("acceptedBallFrames"),
                baseline_accepted_ball_frame_count,
            ),
            "baselineControlledPossessionFrames": _safe_int(
                baseline_bundle["proofSummary"].get("controlledPossessionFrames"),
                0,
            ),
            "baselineBallTrackViable": bool(baseline_bundle["proofSummary"].get("ballTrackViable")),
            "baselineBallTrackEdgeFrameShare": _safe_float(
                baseline_bundle["proofSummary"].get("ballTrackEdgeFrameShare"),
                1.0,
            ),
        },
        "probeContributionDelta": {
            "rawProbeRowDelta": candidate_raw_probe_row_count - baseline_raw_probe_row_count,
            "filteredProbeRowDelta": candidate_filtered_probe_row_count - baseline_filtered_probe_row_count,
            "acceptedBallFrameDelta": candidate_accepted_ball_frame_count - baseline_accepted_ball_frame_count,
            "proposalDetectedFrameDelta": candidate_max_proposal_detected_frames - baseline_max_proposal_detected_frames,
        },
        "stageWiseDelta": stage_wise_delta,
        "candidateMaxProposalDetectedFramesAcrossProfiles": candidate_max_proposal_detected_frames,
        "baselineMaxProposalDetectedFramesAcrossProfiles": baseline_max_proposal_detected_frames,
        "baselineControlDiagnosticEvidenceOnly": True,
        "baselineControlIncludedInOfficialPromotionLogic": False,
    }
    candidate_vs_previous_candidate_delta = {
        "generatedAt": _utc_now_iso(),
        "trainingCandidateName": resolved_candidate_name,
        "previousCandidateName": resolved_previous_candidate_name,
        "currentEvaluationBatchName": evaluation_summary.get("evaluationBatchName"),
        "previousEvaluationBatchName": previous_evaluation_summary.get("evaluationBatchName"),
        "screen": {
            "candidateDetectorLabel": candidate_detector_label,
            "candidateScreenViable": bool(candidate_screen_cell.get("viable")),
            "candidateScreenRecommendedProfileName": candidate_screen_cell.get("recommendedProfileName"),
            "previousCandidateDetectorLabel": previous_candidate_detector_label,
            "previousCandidateScreenViable": bool(previous_candidate_screen_cell.get("viable")),
            "previousCandidateScreenRecommendedProfileName": previous_candidate_screen_cell.get(
                "recommendedProfileName"
            ),
        },
        "proof": {
            "candidateAcceptedBallFrames": _safe_int(
                candidate_bundle["proofSummary"].get("acceptedBallFrames"),
                candidate_accepted_ball_frame_count,
            ),
            "candidateControlledPossessionFrames": candidate_controlled_possession_frames,
            "candidateBallTrackViable": candidate_ball_track_viable,
            "previousCandidateAcceptedBallFrames": _safe_int(
                previous_candidate_bundle["proofSummary"].get("acceptedBallFrames"),
                previous_candidate_accepted_ball_frame_count,
            ),
            "previousCandidateControlledPossessionFrames": previous_candidate_controlled_possession_frames,
            "previousCandidateBallTrackViable": previous_candidate_ball_track_viable,
        },
        "probeContributionDelta": {
            "rawProbeRowDelta": candidate_raw_probe_row_count - previous_candidate_raw_probe_row_count,
            "filteredProbeRowDelta": (
                candidate_filtered_probe_row_count - previous_candidate_filtered_probe_row_count
            ),
            "acceptedBallFrameDelta": (
                candidate_accepted_ball_frame_count - previous_candidate_accepted_ball_frame_count
            ),
            "proposalDetectedFrameDelta": (
                candidate_max_proposal_detected_frames - previous_candidate_max_proposal_detected_frames
            ),
        },
        "proposalContributionDelta": {
            "proposalDetectedFrameDelta": (
                candidate_max_proposal_detected_frames - previous_candidate_max_proposal_detected_frames
            ),
            "candidateMaxProposalDetectedFramesAcrossProfiles": candidate_max_proposal_detected_frames,
            "previousCandidateMaxProposalDetectedFramesAcrossProfiles": (
                previous_candidate_max_proposal_detected_frames
            ),
        },
        "candidateMaxProposalDetectedFramesAcrossProfiles": candidate_max_proposal_detected_frames,
        "previousCandidateMaxProposalDetectedFramesAcrossProfiles": (
            previous_candidate_max_proposal_detected_frames
        ),
        "changeFromPreviousCandidateClass": change_from_previous_candidate_class,
        "stageWiseDelta": stage_wise_delta,
    }
    profile_matrix_delta = _build_profile_matrix_delta(
        candidate_name=resolved_candidate_name,
        previous_candidate_name=resolved_previous_candidate_name,
        candidate_matrix=candidate_bundle["recoveryProfileMatrix"],
        previous_candidate_matrix=previous_candidate_bundle["recoveryProfileMatrix"],
        baseline_matrix=baseline_bundle["recoveryProfileMatrix"],
    )

    brainstorm_fixes = _brainstorm_fixes(
        recommended_fix_class=recommended_fix_class,
        recommended_fix_focus=recommended_fix_focus,
        change_from_previous_candidate_class=change_from_previous_candidate_class,
        candidate_name=resolved_candidate_name,
        previous_candidate_name=resolved_previous_candidate_name,
        candidate_max_proposal_detected_frames=candidate_max_proposal_detected_frames,
        previous_candidate_max_proposal_detected_frames=previous_candidate_max_proposal_detected_frames,
        baseline_max_proposal_detected_frames=baseline_max_proposal_detected_frames,
        candidate_raw_probe_row_count=candidate_raw_probe_row_count,
        baseline_raw_probe_row_count=baseline_raw_probe_row_count,
        summary_surface_drift_detected=bool(summary_surface_drift_analysis.get("detected")),
        calibration_suspicion_detected=bool(calibration_suspicion_analysis.get("detected")),
        next_implementation_batch_recommendation=next_batch_recommendation,
    )
    batch_goal = (
        f"Produce a decision-complete diagnosis for why {resolved_candidate_name} still loses versus "
        f"{resolved_previous_candidate_name} and name exactly one corrective fix focus."
    )
    english_summary = (
        "This batch achieved its diagnostic goal. "
        f"It proved that {resolved_candidate_name} showed {change_from_previous_candidate_class} relative to "
        f"{resolved_previous_candidate_name}. The loss remains classified as {root_cause_class}, and the saved proof "
        f"artifacts show {candidate_max_proposal_detected_frames} proposal-detected frames across recovery profiles, "
        f"{candidate_raw_probe_row_count} raw probe rows, {candidate_filtered_probe_row_count} filtered probe rows, "
        f"and {candidate_accepted_ball_frame_count} accepted ball frames for {resolved_candidate_name}. "
        f"The diagnostic baseline still produced {baseline_max_proposal_detected_frames} proposal-detected frames "
        f"across profiles, {baseline_raw_probe_row_count} raw probe rows, {baseline_filtered_probe_row_count} filtered probe rows, "
        f"and {baseline_accepted_ball_frame_count} accepted ball frames. "
        f"Summary surface drift detected: {bool(summary_surface_drift_analysis.get('detected'))}. "
        f"Calibration suspicion detected: {bool(calibration_suspicion_analysis.get('detected'))}."
    )
    english_decision = (
        "The roadmap may not advance beyond evaluate_touchline_detector_candidate. "
        f"The next corrective batch recommendation is {next_batch_recommendation}. "
        f"The underlying fix class remains {recommended_fix_class}, with focus {recommended_fix_focus} before rerunning the bounded evaluation."
    )
    batch_outcome_analysis = {
        "generatedAt": _utc_now_iso(),
        "batchGoal": batch_goal,
        "goalAchieved": True,
        "roadmapAdvanceAllowed": False,
        "englishSummary": english_summary,
        "englishDecision": english_decision,
        "primaryBlocker": root_cause_class,
        "rootCauseClass": root_cause_class,
        "changeFromPreviousCandidateClass": change_from_previous_candidate_class,
        "recommendedFixClass": recommended_fix_class,
        "recommendedFixFocus": recommended_fix_focus,
        "summarySurfaceDriftDetected": bool(summary_surface_drift_analysis.get("detected")),
        "summarySurfaceDriftAnalysis": summary_surface_drift_analysis,
        "calibrationSuspicionDetected": bool(calibration_suspicion_analysis.get("detected")),
        "calibrationSuspicionAnalysis": calibration_suspicion_analysis,
        "nextImplementationBatchRecommendation": next_batch_recommendation,
        "stageWiseDelta": stage_wise_delta,
        "screenCompleted": bool(evaluation_summary.get("screenCompleted")),
        "candidateScreenViable": bool(candidate_screen_cell.get("viable")),
        "candidateRawProbeRowCount": candidate_raw_probe_row_count,
        "candidateFilteredProbeRowCount": candidate_filtered_probe_row_count,
        "candidateAcceptedBallFrameCount": candidate_accepted_ball_frame_count,
        "candidateMaxProposalDetectedFramesAcrossProfiles": candidate_max_proposal_detected_frames,
        "previousCandidateName": resolved_previous_candidate_name,
        "previousCandidateRawProbeRowCount": previous_candidate_raw_probe_row_count,
        "previousCandidateFilteredProbeRowCount": previous_candidate_filtered_probe_row_count,
        "previousCandidateAcceptedBallFrameCount": previous_candidate_accepted_ball_frame_count,
        "previousCandidateMaxProposalDetectedFramesAcrossProfiles": previous_candidate_max_proposal_detected_frames,
        "baselineRawProbeRowCount": baseline_raw_probe_row_count,
        "baselineFilteredProbeRowCount": baseline_filtered_probe_row_count,
        "baselineAcceptedBallFrameCount": baseline_accepted_ball_frame_count,
        "baselineMaxProposalDetectedFramesAcrossProfiles": baseline_max_proposal_detected_frames,
        "nextRecommendedNextLever": NEXT_RECOMMENDED_NEXT_LEVER,
        "brainstormFixes": brainstorm_fixes,
    }
    failure_analysis_summary = {
        "generatedAt": _utc_now_iso(),
        "trainingCandidateName": resolved_candidate_name,
        "previousCandidateName": resolved_previous_candidate_name,
        "failureAnalysisBatchName": DEFAULT_FAILURE_ANALYSIS_BATCH_NAME,
        "evaluationBatchName": evaluation_summary.get("evaluationBatchName"),
        "previousEvaluationBatchName": previous_evaluation_summary.get("evaluationBatchName"),
        "evaluationArtifactRoot": str(paths["evaluationRoot"]),
        "previousCandidateEvaluationArtifactRoot": str(previous_paths["evaluationRoot"]),
        "candidateProofBundleName": candidate_bundle_root.name,
        "previousCandidateProofBundleName": previous_candidate_bundle_root.name,
        "baselineControlProofBundleName": baseline_control_bundle_root.name,
        "screenWinningDetectorLabel": screen_matrix.get("screenWinningDetectorLabel"),
        "candidateScreenViable": bool(candidate_screen_cell.get("viable")),
        "candidateScreenSucceeded": bool(candidate_screen_cell.get("screenSucceeded", True)),
        "candidateScreenRecommendedProfileName": candidate_screen_cell.get("recommendedProfileName"),
        "previousCandidateScreenViable": bool(previous_candidate_screen_cell.get("viable")),
        "previousCandidateScreenRecommendedProfileName": previous_candidate_screen_cell.get(
            "recommendedProfileName"
        ),
        "candidateRawProbeRowCount": candidate_raw_probe_row_count,
        "candidateFilteredProbeRowCount": candidate_filtered_probe_row_count,
        "candidateAcceptedBallFrameCount": candidate_accepted_ball_frame_count,
        "previousCandidateRawProbeRowCount": previous_candidate_raw_probe_row_count,
        "previousCandidateFilteredProbeRowCount": previous_candidate_filtered_probe_row_count,
        "previousCandidateAcceptedBallFrameCount": previous_candidate_accepted_ball_frame_count,
        "baselineRawProbeRowCount": baseline_raw_probe_row_count,
        "baselineFilteredProbeRowCount": baseline_filtered_probe_row_count,
        "baselineAcceptedBallFrameCount": baseline_accepted_ball_frame_count,
        "candidateMaxProposalDetectedFramesAcrossProfiles": candidate_max_proposal_detected_frames,
        "previousCandidateMaxProposalDetectedFramesAcrossProfiles": previous_candidate_max_proposal_detected_frames,
        "baselineMaxProposalDetectedFramesAcrossProfiles": baseline_max_proposal_detected_frames,
        "rootCauseClass": root_cause_class,
        "changeFromPreviousCandidateClass": change_from_previous_candidate_class,
        "recommendedFixClass": recommended_fix_class,
        "recommendedFixFocus": recommended_fix_focus,
        "summarySurfaceDriftDetected": bool(summary_surface_drift_analysis.get("detected")),
        "summarySurfaceDriftAnalysis": summary_surface_drift_analysis,
        "calibrationSuspicionDetected": bool(calibration_suspicion_analysis.get("detected")),
        "calibrationSuspicionAnalysis": calibration_suspicion_analysis,
        "nextImplementationBatchRecommendation": next_batch_recommendation,
        "stageWiseDelta": stage_wise_delta,
        "baselineControlDiagnosticEvidenceOnly": True,
        "goalAchieved": bool(batch_outcome_analysis["goalAchieved"]),
        "roadmapAdvanceAllowed": bool(batch_outcome_analysis["roadmapAdvanceAllowed"]),
        "nextRecommendedNextLever": NEXT_RECOMMENDED_NEXT_LEVER,
        "previousCandidateFailureAnalysisSummary": previous_failure_analysis_summary,
        "batchOutcomeAnalysis": batch_outcome_analysis,
        "evaluationBatchOutcomeAnalysis": evaluation_batch_outcome,
    }

    failure_analysis_root = paths["failureAnalysisRoot"]
    _write_json(failure_analysis_root / "failure_analysis_summary.json", failure_analysis_summary)
    _write_json(failure_analysis_root / "candidate_vs_baseline_delta.json", candidate_vs_baseline_delta)
    _write_json(
        failure_analysis_root / "candidate_vs_previous_candidate_delta.json",
        candidate_vs_previous_candidate_delta,
    )
    _write_json(failure_analysis_root / "profile_matrix_delta.json", profile_matrix_delta)
    _write_json(failure_analysis_root / "frame_level_probe_delta.json", frame_level_probe_delta)
    _write_json(failure_analysis_root / "batch_outcome_analysis.json", batch_outcome_analysis)
    _write_markdown(
        failure_analysis_root / "batch_outcome_analysis.md",
        _build_markdown_batch_outcome(batch_outcome_analysis),
    )
    return failure_analysis_summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze why the active touchline detector candidate evaluation still loses."
    )
    parser.add_argument(
        "--storage-root",
        type=Path,
        default=DEFAULT_STORAGE_ROOT,
        help="Storage root containing trained detector candidate and pod cycle artifacts.",
    )
    parser.add_argument(
        "--candidate-name",
        type=str,
        default=DEFAULT_CANDIDATE_NAME,
        help="Detector candidate name to analyze. Defaults to the newest evaluated candidate.",
    )
    parser.add_argument(
        "--previous-candidate-name",
        type=str,
        default=DEFAULT_PREVIOUS_CANDIDATE_NAME,
        help="Previous detector candidate name to compare against. Defaults to the newest evaluated candidate version below the active one.",
    )
    args = parser.parse_args()
    payload = run_touchline_detector_candidate_failure_analysis(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        previous_candidate_name=args.previous_candidate_name,
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
