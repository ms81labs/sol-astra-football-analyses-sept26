"""Historical validation recipe, retired with its RunPod execution path."""

from __future__ import annotations


if __name__ == "__main__":
    from backend.scripts.runpod_session import require_retired_runpod_disabled

    require_retired_runpod_disabled()

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.app.run_benchmarks import build_selected_cluster_payload  # noqa: E402
from backend.app.run_benchmarks import summarize_match_benchmark  # noqa: E402
from backend.app.storage import Storage  # noqa: E402
import backend.scripts.run_detector_breadth_batch as run_detector_breadth_batch  # noqa: E402
import backend.scripts.run_local_app_path_proof as run_local_app_path_proof  # noqa: E402
import backend.scripts.runpod_session as runpod_session  # noqa: E402
import backend.scripts.run_source_robustness_batch as run_source_robustness_batch  # noqa: E402

DEFAULT_MANIFEST_PATH = REPO_ROOT / "backend" / "benchmark_suites" / "frozen_viable_baseline_slice_suite.json"
DEFAULT_SUITE_ROOT = DEFAULT_STORAGE_ROOT / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
DEFAULT_VALIDATION_BATCH_NAME = "promoted_touchline_detector_candidate_robustness_validation_v1"
DEFAULT_VALIDATION_ROOT = DEFAULT_SUITE_ROOT / DEFAULT_VALIDATION_BATCH_NAME
DEFAULT_PROMOTED_REGISTRY_PATH = DEFAULT_STORAGE_ROOT / "runtime" / "promoted_touchline_detector_candidate.json"
DEFAULT_FAILING_SOURCE_CLIP_ID = "trimed-5min.mp4"
DEFAULT_COMPARISON_SOURCE_CLIP_ID = "trimed-football-2-1minute.mp4"
BEST_THIN_PROFILE_NAME = "source_robustness_shadow_edge_run_keep_every_2_min10"
BASELINE_GUIDED_RESCUE_PROFILE_NAME = "source_robustness_shadow_promoted_v6_baseline_guided_rescue_v1"
PROPOSAL_SELECTION_ADMISSION_FIX_PROFILE_NAME = (
    "source_robustness_shadow_promoted_v6_proposal_selection_admission_fix_v1"
)
PROPOSAL_SELECTION_ADMISSION_FIX_PROFILE_NAMES = {
    PROPOSAL_SELECTION_ADMISSION_FIX_PROFILE_NAME,
    "source_robustness_shadow_promoted_v6_proposal_selection_admission_fix_v2",
    "source_robustness_shadow_promoted_v6_proposal_selection_admission_fix_v3",
}
SUPPORT_VIABILITY_ADMISSION_FIX_PROFILE_NAMES = {
    "source_robustness_shadow_promoted_v6_support_viability_admission_fix_v1",
    "source_robustness_shadow_promoted_v6_support_viability_admission_fix_v2",
    "source_robustness_shadow_promoted_v6_support_viability_admission_fix_v3",
}
PROPOSAL_CROP_GEOMETRY_FIX_PROFILE_NAMES = {
    "source_robustness_shadow_promoted_v6_proposal_crop_geometry_fix_v1",
    "source_robustness_shadow_promoted_v6_proposal_crop_geometry_fix_v2",
    "source_robustness_shadow_promoted_v6_proposal_crop_geometry_fix_v3",
}
SELECTION_SEGMENT_VIABILITY_FIX_PROFILE_NAMES = {
    "source_robustness_shadow_promoted_v6_selection_segment_viability_fix_v1",
}
PROFILES_REQUIRING_TRUTH_SEED_PATH = (
    PROPOSAL_SELECTION_ADMISSION_FIX_PROFILE_NAMES
    | SUPPORT_VIABILITY_ADMISSION_FIX_PROFILE_NAMES
    | PROPOSAL_CROP_GEOMETRY_FIX_PROFILE_NAMES
    | SELECTION_SEGMENT_VIABILITY_FIX_PROFILE_NAMES
)
DEFAULT_PROPOSAL_SELECTION_TRUTH_SEED_PATH = (
    DEFAULT_SUITE_ROOT
    / "promoted_v6_source_manifest_and_gold_truth_refresh_v1"
    / "gold_truth_bootstrap_attempt_v1"
    / "accepted_controlled_truth_seed.json"
)
ARM_NAME_BASELINE_CURRENT = "baseline_current"
ARM_NAME_PROMOTED_V6_BASELINE = "promoted_v6_baseline"
ARM_NAME_PROMOTED_V6_PLUS_BEST_THIN = "promoted_v6_plus_best_thin"
BALL_EDGE_MARGIN = 5.0
PITCH_WIDTH = 100.0
PITCH_HEIGHT = 100.0


def _load_json_dict(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object at {path}")
    return payload


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
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


def _pitch_coordinates_are_edge(x: object, y: object) -> bool:
    pitch_x = _safe_float(x, 0.0)
    pitch_y = _safe_float(y, 0.0)
    return (
        pitch_x <= BALL_EDGE_MARGIN
        or pitch_x >= (PITCH_WIDTH - BALL_EDGE_MARGIN)
        or pitch_y <= BALL_EDGE_MARGIN
        or pitch_y >= (PITCH_HEIGHT - BALL_EDGE_MARGIN)
    )


def _ball_truth_accepted_rows(path: Path) -> list[dict[str, object]]:
    payload = _load_json_dict(path)
    accepted_ball = payload.get("acceptedBall")
    if not isinstance(accepted_ball, dict):
        return []
    rows = accepted_ball.get("rows")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _source_center_from_row(row: dict[str, object]) -> tuple[float, float] | None:
    source_keys = ("Source_X1", "Source_Y1", "Source_X2", "Source_Y2")
    if not all(key in row for key in source_keys):
        return None
    return (
        (_safe_float(row.get("Source_X1"), 0.0) + _safe_float(row.get("Source_X2"), 0.0)) / 2.0,
        (_safe_float(row.get("Source_Y1"), 0.0) + _safe_float(row.get("Source_Y2"), 0.0)) / 2.0,
    )


def _write_baseline_guided_rescue_reference(
    *,
    baseline_truth_layers_path: Path,
    promoted_truth_layers_path: Path,
    output_path: Path,
    source_clip_id: str,
) -> dict[str, object]:
    baseline_rows = _ball_truth_accepted_rows(Path(baseline_truth_layers_path))
    promoted_rows = _ball_truth_accepted_rows(Path(promoted_truth_layers_path))
    promoted_frame_ids = {_safe_int(row.get("Frame_ID"), -1) for row in promoted_rows}
    anchors: list[dict[str, object]] = []
    skipped_existing = 0
    skipped_edge = 0
    skipped_missing_source = 0
    missing_baseline_frames = 0
    for row in sorted(baseline_rows, key=lambda item: _safe_int(item.get("Frame_ID"), 0)):
        frame_id = _safe_int(row.get("Frame_ID"), -1)
        if frame_id < 0:
            continue
        if frame_id in promoted_frame_ids:
            skipped_existing += 1
            continue
        missing_baseline_frames += 1
        if _pitch_coordinates_are_edge(row.get("X"), row.get("Y")):
            skipped_edge += 1
            continue
        source_center = _source_center_from_row(row)
        if source_center is None:
            skipped_missing_source += 1
            continue
        anchors.append(
            {
                "frameId": frame_id,
                "sourceCenterX": round(float(source_center[0]), 3),
                "sourceCenterY": round(float(source_center[1]), 3),
                "pitchX": round(_safe_float(row.get("X"), 0.0), 3),
                "pitchY": round(_safe_float(row.get("Y"), 0.0), 3),
            }
        )
    payload = {
        "schemaVersion": 1,
        "referenceKind": "baseline_guided_rescue_v1",
        "sourceClipId": source_clip_id,
        "baselineTruthLayersPath": str(baseline_truth_layers_path),
        "promotedTruthLayersPath": str(promoted_truth_layers_path),
        "anchors": anchors,
        "diagnostics": {
            "baselineAcceptedFrameCount": len({ _safe_int(row.get("Frame_ID"), -1) for row in baseline_rows }),
            "promotedAcceptedFrameCount": len(promoted_frame_ids),
            "missingBaselineFrameCount": missing_baseline_frames,
            "skippedPromotedExistingFrames": skipped_existing,
            "skippedEdgeFrames": skipped_edge,
            "skippedMissingSourceBoxFrames": skipped_missing_source,
            "anchorFrameCount": len(anchors),
        },
    }
    _write_json(output_path, payload)
    return payload


def _summary_field(summary: object, field_name: str, default: object) -> object:
    if isinstance(summary, dict):
        return summary.get(field_name, default)
    return getattr(summary, field_name, default)


def _source_clip_id_from_summary(summary: object, fallback: str) -> str:
    source_clip_id = str(_summary_field(summary, "sourceClipId", "") or "").strip()
    if source_clip_id:
        return source_clip_id
    video_path = str(_summary_field(summary, "videoPath", "") or "").strip()
    if video_path:
        return Path(video_path).name
    return fallback


def _resolve_entry_by_source_clip_id(
    manifest: dict[str, object],
    *,
    source_clip_id: str,
) -> dict[str, object]:
    for entry in manifest.get("entries", []):
        if not isinstance(entry, dict):
            continue
        if str(entry.get("sourceClipId") or "") != source_clip_id:
            continue
        video_path = Path(str(entry.get("videoPath") or "")).expanduser()
        if video_path.exists():
            return {
                "entryId": entry.get("entryId") or source_clip_id,
                "matchId": entry.get("matchId"),
                "label": entry.get("label") or source_clip_id,
                "sourceClipId": source_clip_id,
                "videoPath": video_path,
            }
    raise FileNotFoundError(f"Could not resolve an existing video path for source clip {source_clip_id}")


def _load_canonical_proof_floor_intact(suite_root: Path) -> bool:
    active_lane_snapshot_path = suite_root / "active_lane_snapshot.json"
    if not active_lane_snapshot_path.exists():
        return True
    payload = _load_json_dict(active_lane_snapshot_path)
    canonical_proof_floor = payload.get("canonicalProofFloor")
    if not isinstance(canonical_proof_floor, dict):
        return True
    return bool(canonical_proof_floor.get("intact", True))


def _build_arm_specs(
    runtime_registry: dict[str, object],
    *,
    baseline_fingerprint: dict[str, object] | None = None,
    promoted_baseline_edge_share_repair_profile: str | None = None,
    promoted_baseline_baseline_guided_rescue_reference_path: str | None = None,
    promoted_baseline_proposal_selection_truth_seed_path: str | None = None,
    promoted_baseline_reviewed_positive_anchor_seed_path: str | None = None,
) -> list[dict[str, object]]:
    runtime_contract = (
        dict(runtime_registry.get("runtimeContract"))
        if isinstance(runtime_registry.get("runtimeContract"), dict)
        else {}
    )
    baseline_fingerprint = dict(baseline_fingerprint or {})
    primary_detector_model_path = str(runtime_contract.get("primaryDetectorModelPath") or "yolov10n.pt")
    baseline_detector_model_path = str(
        baseline_fingerprint.get("detectorModelPath") or primary_detector_model_path or "yolov10n.pt"
    )
    auxiliary_ball_model_path = runtime_contract.get("auxiliaryBallModelPath")
    auxiliary_ball_model_profile = runtime_contract.get("auxiliaryBallModelProfile") or "ball_probe_only_v1"

    return [
        {
            "armName": ARM_NAME_BASELINE_CURRENT,
            "forceFreshProof": False,
            "runtimeOptions": {
                "primaryModelPath": baseline_detector_model_path,
                "auxiliaryBallModelPath": None,
                "auxiliaryBallModelProfile": None,
                "edgeShareRepairProfile": None,
                "baselineGuidedRescueReferencePath": None,
                "proposalSelectionTruthSeedPath": None,
                "reviewedPositiveAnchorSeedPath": None,
            },
        },
        {
            "armName": ARM_NAME_PROMOTED_V6_BASELINE,
            "forceFreshProof": bool(
                promoted_baseline_edge_share_repair_profile
                and (
                    promoted_baseline_baseline_guided_rescue_reference_path
                    or promoted_baseline_proposal_selection_truth_seed_path
                    or promoted_baseline_reviewed_positive_anchor_seed_path
                )
            ),
            "runtimeOptions": {
                "primaryModelPath": primary_detector_model_path,
                "auxiliaryBallModelPath": auxiliary_ball_model_path,
                "auxiliaryBallModelProfile": auxiliary_ball_model_profile,
                "edgeShareRepairProfile": promoted_baseline_edge_share_repair_profile,
                "baselineGuidedRescueReferencePath": promoted_baseline_baseline_guided_rescue_reference_path,
                "proposalSelectionTruthSeedPath": promoted_baseline_proposal_selection_truth_seed_path,
                "reviewedPositiveAnchorSeedPath": promoted_baseline_reviewed_positive_anchor_seed_path,
            },
        },
        {
            "armName": ARM_NAME_PROMOTED_V6_PLUS_BEST_THIN,
            "forceFreshProof": False,
            "runtimeOptions": {
                "primaryModelPath": primary_detector_model_path,
                "auxiliaryBallModelPath": auxiliary_ball_model_path,
                "auxiliaryBallModelProfile": auxiliary_ball_model_profile,
                "edgeShareRepairProfile": BEST_THIN_PROFILE_NAME,
                "baselineGuidedRescueReferencePath": None,
                "proposalSelectionTruthSeedPath": None,
                "reviewedPositiveAnchorSeedPath": None,
            },
        },
    ]


def _proof_row_from_summary(
    *,
    summary: object,
    arm_name: str,
    entry: dict[str, object],
    acquisition_diagnostics: dict[str, object] | None,
) -> dict[str, object]:
    acquisition_diagnostics = dict(acquisition_diagnostics or {})
    return {
        "configName": arm_name,
        "entryId": entry.get("entryId"),
        "matchId": _summary_field(summary, "matchId", None),
        "label": entry.get("label"),
        "sourceClipId": entry.get("sourceClipId"),
        "status": "success",
        "acceptedBallFrames": _safe_int(_summary_field(summary, "acceptedBallFrames", 0), 0),
        "acceptedBallRatio": round(_safe_float(_summary_field(summary, "acceptedBallRatio", 0.0), 0.0), 3),
        "controlledPossessionFrames": _safe_int(_summary_field(summary, "controlledPossessionFrames", 0), 0),
        "controlledPossessionRatio": round(
            _safe_float(_summary_field(summary, "controlledPossessionRatio", 0.0), 0.0),
            3,
        ),
        "ballTrackViable": bool(_summary_field(summary, "ballTrackViable", False)),
        "ballTrackEdgeFrameShare": round(
            _safe_float(_summary_field(summary, "ballTrackEdgeFrameShare", 0.0), 0.0),
            3,
        ),
        "fiveMinuteTruthReady": bool(_summary_field(summary, "fiveMinuteTruthReady", False)),
        "truthGateReasons": list(_summary_field(summary, "truthGateReasons", [])),
        "acceptedRetentionRatio": 1.0,
        "controlledRetentionRatio": 1.0,
        "edgeShareImprovement": 0.0,
        "supportedAcceptedBallRatio": round(
            _safe_float(_summary_field(summary, "supportedAcceptedBallRatio", 0.0), 0.0),
            3,
        ),
        "unsupportedAcceptedEdgeFrames": _safe_int(
            _summary_field(summary, "unsupportedAcceptedEdgeFrames", 0),
            0,
        ),
        "acquisitionWindowKindCounts": dict(
            acquisition_diagnostics.get("proposalWindowKindSelectedCounts")
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


def _proof_run_from_summary(
    *,
    summary: object,
    entry: dict[str, object],
    match_id: str | None = None,
    reusedEvidence: dict[str, object] | None = None,
) -> dict[str, object]:
    payload = {
        "matchId": match_id or _summary_field(summary, "matchId", None),
        "sourceClipId": _source_clip_id_from_summary(summary, str(entry.get("sourceClipId") or "")),
        "videoPath": str(_summary_field(summary, "videoPath", entry.get("videoPath"))),
        "acceptedBallFrames": _safe_int(_summary_field(summary, "acceptedBallFrames", 0), 0),
        "controlledPossessionFrames": _safe_int(_summary_field(summary, "controlledPossessionFrames", 0), 0),
        "ballTrackViable": bool(_summary_field(summary, "ballTrackViable", False)),
        "ballTrackEdgeFrameShare": round(
            _safe_float(_summary_field(summary, "ballTrackEdgeFrameShare", 0.0), 0.0),
            3,
        ),
    }
    if isinstance(reusedEvidence, dict) and reusedEvidence:
        payload["reusedEvidence"] = reusedEvidence
    return payload


def _load_selected_cluster_after_summary(path: Path) -> tuple[dict[str, object], str | None]:
    payload = _load_json_dict(path)
    after = payload.get("after")
    if not isinstance(after, dict):
        raise ValueError(f"Expected selected cluster delta with 'after' summary at {path}")
    saved_match_id = str(payload.get("savedMatchId") or after.get("matchId") or "").strip() or None
    return dict(after), saved_match_id


def _load_saved_match_summary(
    *,
    storage_root: Path,
    entry: dict[str, object],
) -> tuple[dict[str, object], dict[str, object], str]:
    match_id = str(entry.get("matchId") or "").strip()
    if not match_id:
        raise ValueError(f"Saved suite entry is missing matchId for {entry.get('sourceClipId')}")
    storage = Storage(storage_root)
    summary = summarize_match_benchmark(storage, match_id).model_dump(mode="json")
    acquisition_diagnostics = run_source_robustness_batch._load_source_conditioned_acquisition_diagnostics(
        storage,
        match_id,
    )
    return summary, acquisition_diagnostics, match_id


def _load_evaluation_bundle_selected_cluster_summary(
    *,
    storage_root: Path,
    proof_bundle: dict[str, object],
    entry: dict[str, object],
) -> tuple[dict[str, object], dict[str, object], str | None]:
    selected_cluster_delta_path = Path(str(proof_bundle.get("selectedClusterDeltaPath") or "")).expanduser()
    if not selected_cluster_delta_path.exists():
        raise FileNotFoundError(f"Missing selected cluster delta for proof bundle: {selected_cluster_delta_path}")
    summary, saved_match_id = _load_selected_cluster_after_summary(selected_cluster_delta_path)
    summary.setdefault("videoPath", str(entry.get("videoPath") or ""))
    summary.setdefault("sourceClipId", str(entry.get("sourceClipId") or ""))
    acquisition_diagnostics: dict[str, object] = {}
    if saved_match_id:
        acquisition_diagnostics = run_source_robustness_batch._load_source_conditioned_acquisition_diagnostics(
            Storage(storage_root),
            saved_match_id,
        )
    return summary, acquisition_diagnostics, saved_match_id


def _apply_same_batch_baseline_retention(
    arm_rows: list[dict[str, object]],
    *,
    baseline_rows_by_source: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    normalized_rows: list[dict[str, object]] = []
    for row in arm_rows:
        normalized = dict(row)
        source_clip_id = str(normalized.get("sourceClipId") or "")
        baseline_row = baseline_rows_by_source.get(source_clip_id)
        if isinstance(baseline_row, dict):
            baseline_accepted_frames = max(_safe_int(baseline_row.get("acceptedBallFrames"), 0), 1)
            baseline_controlled_frames = max(_safe_int(baseline_row.get("controlledPossessionFrames"), 0), 1)
            normalized["acceptedRetentionRatio"] = round(
                _safe_int(normalized.get("acceptedBallFrames"), 0) / baseline_accepted_frames,
                3,
            )
            normalized["controlledRetentionRatio"] = round(
                _safe_int(normalized.get("controlledPossessionFrames"), 0) / baseline_controlled_frames,
                3,
            )
            normalized["edgeShareImprovement"] = round(
                _safe_float(baseline_row.get("ballTrackEdgeFrameShare"), 0.0)
                - _safe_float(normalized.get("ballTrackEdgeFrameShare"), 0.0),
                3,
            )
        normalized_rows.append(normalized)
    return normalized_rows


def _copy_entry_clip_to_remote_session(
    *,
    remote_session: dict[str, object],
    clip_path: Path,
) -> dict[str, object]:
    remote_repo_root = str(remote_session["remoteRepoRoot"])
    remote_clip_path = f"{remote_repo_root}/videos/{clip_path.name}"
    if str(remote_session.get("remoteClipPath") or "") == remote_clip_path:
        return dict(remote_session)
    runpod_session.copy_file_to_pod(
        list(remote_session["sshCommand"]),
        local_path=clip_path,
        remote_path=remote_clip_path,
    )
    return {**remote_session, "remoteClipPath": remote_clip_path}


def _run_proof_for_entry(
    *,
    storage_root: Path,
    storage: Storage,
    arm_name: str,
    entry: dict[str, object],
    runtime_options: dict[str, object],
    remote_session: dict[str, object] | None,
) -> dict[str, object]:
    clip_path = Path(entry["videoPath"])
    proof_name = f"{arm_name}-{entry['sourceClipId']}-robustness-validation"
    if isinstance(remote_session, dict):
        entry_session = _copy_entry_clip_to_remote_session(
            remote_session=remote_session,
            clip_path=clip_path,
        )
        remote_payload = run_detector_breadth_batch._run_remote_proof_on_session(
            session=entry_session,
            storage_root=storage_root,
            proof_name=proof_name,
            model_path=str(runtime_options.get("primaryModelPath") or "yolov10n.pt"),
            primary_model_path=(
                str(runtime_options.get("primaryModelPath"))
                if runtime_options.get("primaryModelPath")
                else None
            ),
            auxiliary_ball_model_path=(
                str(runtime_options.get("auxiliaryBallModelPath"))
                if runtime_options.get("auxiliaryBallModelPath")
                else None
            ),
            auxiliary_ball_model_profile=(
                str(runtime_options.get("auxiliaryBallModelProfile"))
                if runtime_options.get("auxiliaryBallModelProfile")
                else None
            ),
            edge_share_repair_profile=(
                str(runtime_options.get("edgeShareRepairProfile"))
                if runtime_options.get("edgeShareRepairProfile")
                else None
            ),
            baseline_guided_rescue_reference_path=(
                str(runtime_options.get("baselineGuidedRescueReferencePath"))
                if runtime_options.get("baselineGuidedRescueReferencePath")
                else None
            ),
            proposal_selection_truth_seed_path=(
                str(runtime_options.get("proposalSelectionTruthSeedPath"))
                if runtime_options.get("proposalSelectionTruthSeedPath")
                else None
            ),
            reviewed_positive_anchor_seed_path=(
                str(runtime_options.get("reviewedPositiveAnchorSeedPath"))
                if runtime_options.get("reviewedPositiveAnchorSeedPath")
                else None
            ),
        )
        summary = dict(remote_payload.get("summary") or {})
        return {
            "authoritativeSummary": summary,
            "matchId": str(remote_payload.get("matchId") or _summary_field(summary, "matchId", "")),
            "acquisitionDiagnostics": {},
            "reusedEvidence": {
                "kind": "remote_runpod_proof",
                "selectedClusterDeltaPath": str(remote_payload.get("selectedClusterDeltaPath") or ""),
                "proofSummaryPath": str(remote_payload.get("summaryPath") or ""),
            },
        }

    summary = run_local_app_path_proof.run_local_app_path_proof(
        storage_root=storage_root,
        clip_path=clip_path,
        name=proof_name,
        primary_model_path=runtime_options.get("primaryModelPath"),
        auxiliary_ball_model_path=runtime_options.get("auxiliaryBallModelPath"),
        auxiliary_ball_model_profile=runtime_options.get("auxiliaryBallModelProfile"),
        edge_share_repair_profile=runtime_options.get("edgeShareRepairProfile"),
        baseline_guided_rescue_reference_path=runtime_options.get("baselineGuidedRescueReferencePath"),
        proposal_selection_truth_seed_path=runtime_options.get("proposalSelectionTruthSeedPath"),
        reviewed_positive_anchor_seed_path=runtime_options.get("reviewedPositiveAnchorSeedPath"),
        timeout_seconds=7200.0,
    )
    match_id = str(_summary_field(summary, "matchId", ""))
    selected_cluster_payload = build_selected_cluster_payload(storage, match_id)
    selected_cluster_after = (
        dict(selected_cluster_payload.get("after"))
        if isinstance(selected_cluster_payload.get("after"), dict)
        else None
    )
    authoritative_summary = selected_cluster_after or summary
    acquisition_diagnostics = run_source_robustness_batch._load_source_conditioned_acquisition_diagnostics(
        storage,
        match_id,
    )
    return {
        "authoritativeSummary": authoritative_summary,
        "matchId": match_id,
        "acquisitionDiagnostics": acquisition_diagnostics,
    }


def _run_validation_suite_for_arm(
    *,
    storage_root: Path,
    arm_spec: dict[str, object],
    entries: list[dict[str, object]],
    suite_name: str,
    suite_type: str,
    baseline_fingerprint: dict[str, object],
    failing_source_clip_id: str,
    comparison_source_clip_id: str,
    baseline_suite_summary: dict[str, object],
    baseline_source_summaries: dict[str, dict[str, object]],
    canonical_proof_floor_intact: bool,
    precomputed_rows_by_source_clip_id: dict[str, dict[str, object]] | None = None,
    remote_session: dict[str, object] | None = None,
) -> dict[str, object]:
    storage = Storage(storage_root)
    arm_name = str(arm_spec["armName"])
    runtime_options = dict(arm_spec.get("runtimeOptions") or {})
    precomputed_rows_by_source_clip_id = dict(precomputed_rows_by_source_clip_id or {})
    rows: list[dict[str, object]] = []
    proof_runs: list[dict[str, object]] = []

    for entry in entries:
        source_clip_id = str(entry["sourceClipId"])
        precomputed_payload = precomputed_rows_by_source_clip_id.get(source_clip_id)
        if isinstance(precomputed_payload, dict):
            rows.append(dict(precomputed_payload.get("row") or {}))
            proof_runs.append(dict(precomputed_payload.get("proofRun") or {}))
            continue
        proof_payload = _run_proof_for_entry(
            storage_root=storage_root,
            storage=storage,
            arm_name=arm_name,
            entry=entry,
            runtime_options=runtime_options,
            remote_session=remote_session,
        )
        authoritative_summary = proof_payload["authoritativeSummary"]
        match_id = str(proof_payload["matchId"])
        acquisition_diagnostics = dict(proof_payload.get("acquisitionDiagnostics") or {})
        reused_evidence = (
            dict(proof_payload.get("reusedEvidence"))
            if isinstance(proof_payload.get("reusedEvidence"), dict)
            else None
        )
        proof_runs.append(
            _proof_run_from_summary(
                summary=authoritative_summary,
                entry=entry,
                match_id=match_id,
                reusedEvidence=reused_evidence,
            )
        )
        rows.append(
            _proof_row_from_summary(
                summary=authoritative_summary,
                arm_name=arm_name,
                entry=entry,
                acquisition_diagnostics=acquisition_diagnostics,
            )
        )

    config_summary, source_summaries, _robustness_diagnosis = run_source_robustness_batch._suite_summary_from_rows(
        suite_name=suite_name,
        suite_type=suite_type,
        baseline_fingerprint=baseline_fingerprint,
        rows=rows,
    )
    source_summaries = run_source_robustness_batch._extend_source_summaries_with_retention(rows, source_summaries)
    outcome = run_source_robustness_batch.evaluate_source_robustness_outcome(
        baseline_suite_verdict=str(baseline_suite_summary["suiteVerdict"]),
        candidate_suite_verdict=str(config_summary["suiteVerdict"]),
        canonical_proof_floor_intact=canonical_proof_floor_intact,
        failing_source_baseline=baseline_source_summaries.get(failing_source_clip_id, {}),
        failing_source_candidate=source_summaries.get(failing_source_clip_id, {}),
    )
    return {
        "armName": arm_name,
        "suiteSummary": config_summary,
        "sourceSummaries": source_summaries,
        "outcome": outcome,
        "proofRuns": proof_runs,
        "rows": rows,
    }


def _build_failing_source_short_circuit_payload(
    *,
    arm_name: str,
    failing_row: dict[str, object],
    proof_run: dict[str, object],
    suite_name: str,
    suite_type: str,
    baseline_fingerprint: dict[str, object],
    failing_source_clip_id: str,
    baseline_suite_summary: dict[str, object],
    baseline_source_summaries: dict[str, dict[str, object]],
    baseline_rows: list[dict[str, object]],
    canonical_proof_floor_intact: bool,
) -> dict[str, object] | None:
    if not failing_row:
        return None

    failing_rows = _apply_same_batch_baseline_retention(
        [dict(failing_row)],
        baseline_rows_by_source={
            str(row.get("sourceClipId") or ""): dict(row)
            for row in baseline_rows
        },
    )

    candidate_suite_summary, candidate_source_summaries, _ = run_source_robustness_batch._suite_summary_from_rows(
        suite_name=suite_name,
        suite_type=suite_type,
        baseline_fingerprint=baseline_fingerprint,
        rows=failing_rows,
    )
    candidate_source_summaries = run_source_robustness_batch._extend_source_summaries_with_retention(
        failing_rows,
        candidate_source_summaries,
    )
    optimistic_outcome = run_source_robustness_batch.evaluate_source_robustness_outcome(
        baseline_suite_verdict=str(baseline_suite_summary["suiteVerdict"]),
        candidate_suite_verdict=str(baseline_suite_summary["suiteVerdict"]),
        canonical_proof_floor_intact=canonical_proof_floor_intact,
        failing_source_baseline=baseline_source_summaries.get(failing_source_clip_id, {}),
        failing_source_candidate=candidate_source_summaries.get(failing_source_clip_id, {}),
    )
    if bool(optimistic_outcome.get("passedPromotionGate")):
        return None

    blocking_reasons = {
        "accepted_retention_below_guardrail",
        "controlled_retention_below_guardrail",
        "failing_source_not_viable",
        "failing_source_edge_share_improvement_below_guardrail",
    }
    promotion_blockers = {
        str(item)
        for item in optimistic_outcome.get("promotionBlockers", [])
        if str(item).strip()
    }
    if not promotion_blockers or not promotion_blockers.issubset(blocking_reasons):
        return None

    candidate_suite_summary["comparisonSourceExecutionSkipped"] = True
    candidate_suite_summary["comparisonSourceExecutionSkipReason"] = (
        "failing_source_gate_already_failed_before_comparison_source_runtime"
    )
    return {
        "armName": arm_name,
        "suiteSummary": candidate_suite_summary,
        "sourceSummaries": candidate_source_summaries,
        "outcome": optimistic_outcome,
        "proofRuns": [dict(proof_run)],
        "rows": failing_rows,
        "comparisonSourceExecutionSkipped": True,
    }


def _run_promoted_arm_with_baseline_reference(
    *,
    storage_root: Path,
    arm_spec: dict[str, object],
    entries: list[dict[str, object]],
    suite_name: str,
    suite_type: str,
    baseline_fingerprint: dict[str, object],
    failing_source_clip_id: str,
    comparison_source_clip_id: str,
    baseline_suite_summary: dict[str, object],
    baseline_source_summaries: dict[str, dict[str, object]],
    canonical_proof_floor_intact: bool,
    baseline_rows: list[dict[str, object]],
    precomputed_rows_by_source_clip_id: dict[str, dict[str, object]] | None = None,
    remote_session: dict[str, object] | None = None,
) -> dict[str, object]:
    storage = Storage(storage_root)
    arm_name = str(arm_spec["armName"])
    runtime_options = dict(arm_spec.get("runtimeOptions") or {})
    precomputed_rows_by_source_clip_id = dict(precomputed_rows_by_source_clip_id or {})
    baseline_rows_by_source = {
        str(row.get("sourceClipId") or ""): dict(row)
        for row in baseline_rows
    }
    rows: list[dict[str, object]] = []
    proof_runs: list[dict[str, object]] = []
    attempt_runtime_active = bool(
        runtime_options.get("edgeShareRepairProfile")
        or runtime_options.get("baselineGuidedRescueReferencePath")
        or runtime_options.get("proposalSelectionTruthSeedPath")
        or runtime_options.get("reviewedPositiveAnchorSeedPath")
    )
    for entry in entries:
        source_clip_id = str(entry["sourceClipId"])
        precomputed_payload = precomputed_rows_by_source_clip_id.get(source_clip_id)
        force_fresh_attempt_proof = (
            arm_name == ARM_NAME_PROMOTED_V6_BASELINE
            and source_clip_id == failing_source_clip_id
            and attempt_runtime_active
        )
        if isinstance(precomputed_payload, dict) and not force_fresh_attempt_proof:
            rows.append(dict(precomputed_payload.get("row") or {}))
            proof_runs.append(dict(precomputed_payload.get("proofRun") or {}))
            continue
        proof_payload = _run_proof_for_entry(
            storage_root=storage_root,
            storage=storage,
            arm_name=arm_name,
            entry=entry,
            runtime_options=runtime_options,
            remote_session=remote_session,
        )
        authoritative_summary = proof_payload["authoritativeSummary"]
        match_id = str(proof_payload["matchId"])
        acquisition_diagnostics = dict(proof_payload.get("acquisitionDiagnostics") or {})
        reused_evidence = (
            dict(proof_payload.get("reusedEvidence"))
            if isinstance(proof_payload.get("reusedEvidence"), dict)
            else None
        )
        proof_run = _proof_run_from_summary(
            summary=authoritative_summary,
            entry=entry,
            match_id=match_id,
            reusedEvidence=reused_evidence,
        )
        row = _proof_row_from_summary(
            summary=authoritative_summary,
            arm_name=arm_name,
            entry=entry,
            acquisition_diagnostics=acquisition_diagnostics,
        )
        proof_runs.append(proof_run)
        rows.append(row)
        if force_fresh_attempt_proof:
            short_circuit_payload = _build_failing_source_short_circuit_payload(
                arm_name=arm_name,
                failing_row=row,
                proof_run=proof_run,
                suite_name=suite_name,
                suite_type=suite_type,
                baseline_fingerprint=baseline_fingerprint,
                failing_source_clip_id=failing_source_clip_id,
                baseline_suite_summary=baseline_suite_summary,
                baseline_source_summaries=baseline_source_summaries,
                baseline_rows=baseline_rows,
                canonical_proof_floor_intact=canonical_proof_floor_intact,
            )
            if short_circuit_payload is not None:
                return short_circuit_payload

    rows = _apply_same_batch_baseline_retention(rows, baseline_rows_by_source=baseline_rows_by_source)
    config_summary, source_summaries, _robustness_diagnosis = run_source_robustness_batch._suite_summary_from_rows(
        suite_name=suite_name,
        suite_type=suite_type,
        baseline_fingerprint=baseline_fingerprint,
        rows=rows,
    )
    source_summaries = run_source_robustness_batch._extend_source_summaries_with_retention(rows, source_summaries)
    outcome = run_source_robustness_batch.evaluate_source_robustness_outcome(
        baseline_suite_verdict=str(baseline_suite_summary["suiteVerdict"]),
        candidate_suite_verdict=str(config_summary["suiteVerdict"]),
        canonical_proof_floor_intact=canonical_proof_floor_intact,
        failing_source_baseline=baseline_source_summaries.get(failing_source_clip_id, {}),
        failing_source_candidate=source_summaries.get(failing_source_clip_id, {}),
    )
    return {
        "armName": arm_name,
        "suiteSummary": config_summary,
        "sourceSummaries": source_summaries,
        "outcome": outcome,
        "proofRuns": proof_runs,
        "rows": rows,
    }


def _arm_rank(arm_payload: dict[str, object]) -> tuple[object, ...]:
    outcome = dict(arm_payload.get("outcome") or {})
    source_summaries = dict(arm_payload.get("sourceSummaries") or {})
    failing_source_summary = dict(source_summaries.get(DEFAULT_FAILING_SOURCE_CLIP_ID) or {})
    arm_name = str(arm_payload.get("armName") or "")
    return (
        run_source_robustness_batch.SOURCE_ROBUSTNESS_OUTCOME_ORDER.get(str(outcome.get("configOutcome")), -1),
        _safe_float(outcome.get("failingSourceEdgeShareImprovement"), 0.0),
        _safe_float(failing_source_summary.get("medianAcceptedRetentionRatio"), 0.0),
        _safe_float(failing_source_summary.get("medianControlledRetentionRatio"), 0.0),
        1 if arm_name == ARM_NAME_PROMOTED_V6_BASELINE else 0,
        arm_name,
    )


def _build_short_circuit_promoted_arm_payload(
    *,
    arm_name: str,
    precomputed_rows_by_source_clip_id: dict[str, dict[str, object]],
    suite_name: str,
    suite_type: str,
    baseline_fingerprint: dict[str, object],
    failing_source_clip_id: str,
    baseline_suite_summary: dict[str, object],
    baseline_source_summaries: dict[str, dict[str, object]],
    baseline_rows: list[dict[str, object]],
    canonical_proof_floor_intact: bool,
) -> dict[str, object] | None:
    failing_source_payload = precomputed_rows_by_source_clip_id.get(failing_source_clip_id)
    if not isinstance(failing_source_payload, dict):
        return None
    failing_row = dict(failing_source_payload.get("row") or {})
    proof_run = dict(failing_source_payload.get("proofRun") or {})
    return _build_failing_source_short_circuit_payload(
        arm_name=arm_name,
        failing_row=failing_row,
        proof_run=proof_run,
        suite_name=suite_name,
        suite_type=suite_type,
        baseline_fingerprint=baseline_fingerprint,
        failing_source_clip_id=failing_source_clip_id,
        baseline_suite_summary=baseline_suite_summary,
        baseline_source_summaries=baseline_source_summaries,
        baseline_rows=baseline_rows,
        canonical_proof_floor_intact=canonical_proof_floor_intact,
    )


def _select_winning_arm_payload(arm_payloads: list[dict[str, object]]) -> dict[str, object]:
    by_name = {str(payload.get("armName") or ""): payload for payload in arm_payloads}
    for preferred_name in (ARM_NAME_PROMOTED_V6_BASELINE, ARM_NAME_PROMOTED_V6_PLUS_BEST_THIN):
        candidate = by_name.get(preferred_name)
        if isinstance(candidate, dict) and bool(dict(candidate.get("outcome") or {}).get("passedPromotionGate")):
            return candidate
    promoted_candidates = [
        payload
        for payload in arm_payloads
        if str(payload.get("armName") or "") in {ARM_NAME_PROMOTED_V6_BASELINE, ARM_NAME_PROMOTED_V6_PLUS_BEST_THIN}
    ]
    return max(promoted_candidates, key=_arm_rank)


def _write_batch_outcome_markdown(path: Path, payload: dict[str, object]) -> None:
    lines = [
        f"# {payload['validationBatchName']}",
        "",
        f"- `trainingCandidateName = {payload['trainingCandidateName']}`",
        f"- `winningArmName = {payload['winningArmName']}`",
        f"- `winningConfigOutcome = {payload['winningConfigOutcome']}`",
        f"- `winningPassedPromotionGate = {str(payload['winningPassedPromotionGate']).lower()}`",
        f"- `runtimeDefaultChanged = {str(payload['runtimeDefaultChanged']).lower()}`",
        f"- `goalAchieved = {str(payload['goalAchieved']).lower()}`",
        f"- `nextRecommendedNextLever = {payload['nextRecommendedNextLever']}`",
        "",
        payload["englishSummary"],
        "",
        payload["englishDecision"],
    ]
    _write_text(path, "\n".join(lines) + "\n")


def _resolve_default_manifest_path(storage_root: Path) -> Path:
    return storage_root / "benchmark_suites" / "frozen_viable_baseline_slice_suite.json"


def _resolve_default_promoted_registry_path(storage_root: Path) -> Path:
    return storage_root / "runtime" / "promoted_touchline_detector_candidate.json"


def _resolve_default_validation_root(storage_root: Path) -> Path:
    return storage_root / "benchmark_suites" / "frozen-viable-baseline-slice-suite" / DEFAULT_VALIDATION_BATCH_NAME


def run_promoted_touchline_detector_candidate_source_robustness_validation(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    promoted_registry_path: Path = DEFAULT_PROMOTED_REGISTRY_PATH,
    validation_root: Path = DEFAULT_VALIDATION_ROOT,
    failing_source_clip_id: str = DEFAULT_FAILING_SOURCE_CLIP_ID,
    comparison_source_clip_id: str = DEFAULT_COMPARISON_SOURCE_CLIP_ID,
    promoted_baseline_edge_share_repair_profile: str | None = None,
    promoted_baseline_baseline_guided_rescue_reference_path: str | None = None,
    promoted_baseline_proposal_selection_truth_seed_path: str | None = None,
    promoted_baseline_reviewed_positive_anchor_seed_path: str | None = None,
    use_runpod: bool = False,
    runpod_gpu_id: str | None = None,
) -> dict[str, object]:
    runpod_session.require_retired_runpod_disabled()


def main() -> None:
    runpod_session.require_retired_runpod_disabled()


if __name__ == "__main__":
    main()
