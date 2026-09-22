"""Historical data-quality recipe, retired with its RunPod execution path."""

from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

if __name__ == "__main__":
    from backend.scripts.runpod_session import require_retired_runpod_disabled

    require_retired_runpod_disabled()

import hashlib
import json
import os
from pathlib import Path
import shlex
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.app.schemas import CreateIssueRequest, ReviewBundleItem  # noqa: E402
from backend.app.storage import Storage  # noqa: E402
import backend.scripts.run_touchline_training_data_curation_batch as phase1  # noqa: E402
import backend.scripts.runpod_session as runpod_session  # noqa: E402
import backend.train_custom as train_custom  # noqa: E402


DEFAULT_BATCH_NAME = "touchline_model_data_quality_fix_v1"
DEFAULT_TRAINING_BATCH_NAME = "touchline_detector_candidate_model_data_quality_fix_v1"
DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v3"
DEFAULT_FAILURE_ANALYSIS_CANDIDATE_NAME = "touchline_detector_candidate_v2"
DEFAULT_PHASE1B_BATCH_NAME = "touchline_review_densification_v1"
DEFAULT_BASELINE_CONTROL_PROOF_BUNDLE = (
    "yolov10n-pt-baseline-full-detector-baseline-control-20260422224502"
)
DEFAULT_FAILING_SOURCE_CLIP_ID = "trimed-5min.mp4"
DEFAULT_COMPARISON_SOURCE_CLIP_ID = "trimed-football-2-1minute.mp4"
DEFAULT_FAILING_MATCH_ID = "1c8136cda03240aa8324f676c9bbf99a"
DEFAULT_CONTROL_MATCH_ID = "1d67fa87080446a0a777901aace43809"
DEFAULT_MAX_NEW_FAILING_WINDOWS = 3
DEFAULT_SEGMENT_MAX_GAP = 5
DEFAULT_MIN_SEGMENT_SIZE = 3
DEFAULT_WINDOW_PADDING = 40
DEFAULT_BASE_MODEL_PATH = "yolov10n.pt"
DEFAULT_IMGSZ = 640
DEFAULT_EPOCHS = 12
DEFAULT_BATCH_SIZE = 8
DEFAULT_DEVICE = "0"
DEFAULT_WORKERS = 4
DEFAULT_SEED = 42
DEFAULT_EXECUTION_MODE = "remote_gpu"
DEFAULT_MAX_NEGATIVE_FRAMES_PER_UNIT = phase1.DEFAULT_MAX_NEGATIVE_FRAMES_PER_UNIT
SEEDED_ISSUE_NOTE_PREFIX = f"[model-data-quality-fix:{DEFAULT_BATCH_NAME}]"
REVIEW_BUNDLE_TAG = f"model-data-quality-fix:{DEFAULT_BATCH_NAME}"
NEXT_LEVER_EVALUATE = "evaluate_touchline_detector_candidate"
NEXT_LEVER_RETRAIN = "retrain_touchline_detector_candidate"
PLATEAU_BASELINE = {
    "acceptedBallFrames": 101,
    "controlledPossessionFrames": 98,
    "ballTrackViable": False,
    "ballTrackEdgeFrameShare": 0.812,
}

_safe_int = phase1._safe_int
_safe_float = phase1._safe_float
_row_bbox = phase1._row_bbox
_write_dataset_yaml = phase1._write_dataset_yaml
_extract_frame_image = phase1._extract_frame_image
_resolve_video_path = phase1._resolve_video_path


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _json_safe_metrics(metrics: object) -> dict[str, object]:
    if not isinstance(metrics, dict):
        return {}
    normalized: dict[str, object] = {}
    for key, value in metrics.items():
        if isinstance(value, bool):
            normalized[str(key)] = value
        elif isinstance(value, (int, float, str)) or value is None:
            normalized[str(key)] = value
        else:
            try:
                normalized[str(key)] = float(value)
            except (TypeError, ValueError):
                normalized[str(key)] = str(value)
    return normalized


def _requested_gpu_id() -> str | None:
    env_gpu_id = os.environ.get("RUNPOD_GPU_ID", "").strip()
    if env_gpu_id:
        return env_gpu_id
    loader = getattr(runpod_session, "_load_saved_runpod_gpu_id", None)
    if callable(loader):
        saved_gpu_id = str(loader()).strip()
        if saved_gpu_id:
            return saved_gpu_id
    return None


def _should_retry_without_requested_gpu(error_message: str, requested_gpu_id: str | None) -> bool:
    requested = str(requested_gpu_id or "").strip()
    if not requested:
        return False
    normalized = error_message.lower()
    return (
        f"requested gpu_id {requested!r}".lower() in normalized
        or f"requested gpu_id '{requested}'" in normalized
    ) and (
        "no longer any instances available" in normalized
        or "unable to create a runpod pod with requested gpu_id" in normalized
    )


def _create_remote_training_session(
    *,
    requested_gpu_id: str | None,
) -> tuple[dict[str, object], str | None]:
    try:
        session = runpod_session.create_runpod_session(
            local_repo_root=REPO_ROOT,
            clip_path=None,
            gpu_id=requested_gpu_id,
        )
        return session, None
    except Exception as error:
        error_message = str(error)
        if not _should_retry_without_requested_gpu(error_message, requested_gpu_id):
            raise
        session = runpod_session.create_runpod_session(
            local_repo_root=REPO_ROOT,
            clip_path=None,
            gpu_id=None,
        )
        return session, error_message


def _paths(storage_root: Path) -> dict[str, Path]:
    suite_root = storage_root / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
    phase1b_root = storage_root / "training_prep" / DEFAULT_PHASE1B_BATCH_NAME
    failure_root = (
        storage_root
        / "trained_detector_candidates"
        / DEFAULT_FAILURE_ANALYSIS_CANDIDATE_NAME
        / "failure_analysis_v1"
    )
    artifact_root = storage_root / "training_prep" / DEFAULT_BATCH_NAME
    candidate_root = storage_root / "trained_detector_candidates" / DEFAULT_CANDIDATE_NAME
    return {
        "suiteSummaryPath": suite_root / "suite_summary.json",
        "activeLaneSnapshotPath": suite_root / "active_lane_snapshot.json",
        "suiteRobustnessDiagnosisPath": suite_root / "suite_robustness_diagnosis.json",
        "phase1bManifestPath": phase1b_root / "review_densification_manifest.json",
        "phase1bOverlayPath": phase1b_root / "reviewed_label_overlay.json",
        "phase1bReviewBundleReportPath": phase1b_root / "review_bundle_report.json",
        "phase1bSplitManifestPath": phase1b_root / "split_manifest.json",
        "failureAnalysisSummaryPath": failure_root / "failure_analysis_summary.json",
        "candidateVsBaselineDeltaPath": failure_root / "candidate_vs_baseline_delta.json",
        "frameLevelProbeDeltaPath": failure_root / "frame_level_probe_delta.json",
        "artifactRoot": artifact_root,
        "manifestPath": artifact_root / "data_quality_fix_manifest.json",
        "overlayPath": artifact_root / "reviewed_label_overlay.json",
        "reviewBundleReportPath": artifact_root / "review_bundle_report.json",
        "splitManifestPath": artifact_root / "split_manifest.json",
        "batchOutcomeJsonPath": artifact_root / "batch_outcome_analysis.json",
        "batchOutcomeMarkdownPath": artifact_root / "batch_outcome_analysis.md",
        "exportRoot": artifact_root / "yolo_export",
        "candidateRoot": candidate_root,
        "trainingConfigPath": candidate_root / "training_config.json",
        "trainingSummaryPath": candidate_root / "training_run_summary.json",
        "evaluationContractPath": candidate_root / "evaluation_contract.json",
        "candidateBatchOutcomeJsonPath": candidate_root / "batch_outcome_analysis.json",
        "candidateBatchOutcomeMarkdownPath": candidate_root / "batch_outcome_analysis.md",
        "remoteTrainingResultPath": candidate_root / "remote_training_result.json",
    }


def _stable_curation_unit_id(*, match_id: str, frame_start: int, frame_end: int) -> str:
    raw = f"{DEFAULT_BATCH_NAME}:{match_id}:{frame_start}:{frame_end}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _stable_review_item_id(*, curation_unit_id: str, frame_index: int, seed_source: str) -> str:
    raw = f"{DEFAULT_BATCH_NAME}:{curation_unit_id}:{frame_index}:{seed_source}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def _load_existing_overlay(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    try:
        payload = _load_json(path)
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    items = payload.get("reviewItems")
    if not isinstance(items, list):
        return {}
    lookup: dict[str, dict[str, object]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        review_item_id = str(item.get("reviewItemId") or "").strip()
        if review_item_id:
            lookup[review_item_id] = dict(item)
    return lookup


def _rows_from_payload(payload: object) -> list[dict[str, object]]:
    if not isinstance(payload, list):
        return []
    rows = [dict(row) for row in payload if isinstance(row, dict)]
    rows.sort(key=lambda row: (_safe_int(row.get("Frame_ID"), -1), _safe_float(row.get("Timestamp"), 0.0)))
    return rows


def _group_rows_by_frame(rows: list[dict[str, object]]) -> dict[int, list[dict[str, object]]]:
    grouped: dict[int, list[dict[str, object]]] = {}
    for row in rows:
        frame_id = _safe_int(row.get("Frame_ID"), -1)
        if frame_id < 0:
            continue
        grouped.setdefault(frame_id, []).append(row)
    return grouped


def _seed_source_from_example_seed_source(seed_source: str) -> str:
    mapping = {
        "accepted_ball": "baseline_control_accepted_ball",
        "probe_filtered": "baseline_control_filtered_probe",
        "probe_raw": "baseline_control_raw_probe",
    }
    return mapping.get(seed_source, seed_source)


def _segment_frame_ids(
    frame_ids: list[int],
    *,
    max_frame_gap: int = DEFAULT_SEGMENT_MAX_GAP,
    minimum_segment_size: int = DEFAULT_MIN_SEGMENT_SIZE,
) -> list[list[int]]:
    sorted_ids = sorted({frame_id for frame_id in frame_ids if frame_id >= 0})
    if not sorted_ids:
        return []
    segments: list[list[int]] = []
    current = [sorted_ids[0]]
    for frame_id in sorted_ids[1:]:
        if frame_id - current[-1] <= max_frame_gap:
            current.append(frame_id)
        else:
            if len(current) >= minimum_segment_size:
                segments.append(current)
            current = [frame_id]
    if len(current) >= minimum_segment_size:
        segments.append(current)
    return segments


def _ranges_overlap(left_start: int, left_end: int, right_start: int, right_end: int) -> bool:
    return not (left_end < right_start or right_end < left_start)


def _window_from_segment(segment: list[int], *, clip_max_frame: int) -> dict[str, object]:
    frame_start = max(segment[0] - DEFAULT_WINDOW_PADDING, 0)
    frame_end = min(segment[-1] + DEFAULT_WINDOW_PADDING, clip_max_frame)
    return {
        "frameStart": frame_start,
        "frameEnd": frame_end,
        "evidenceFrameIds": list(segment),
        "evidenceCount": len(segment),
    }


def _layers_from_frame_level_probe_delta(frame_level_probe_delta: dict[str, object]) -> dict[str, dict[str, object]]:
    layers = frame_level_probe_delta.get("layers")
    return dict(layers) if isinstance(layers, dict) else {}


def _candidate_windows_for_layer(
    *,
    layer_name: str,
    frame_ids: list[int],
    existing_ranges: list[tuple[int, int]],
    selected_ranges: list[tuple[int, int]],
    clip_max_frame: int,
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for segment in _segment_frame_ids(frame_ids):
        window = _window_from_segment(segment, clip_max_frame=clip_max_frame)
        if any(
            _ranges_overlap(window["frameStart"], window["frameEnd"], start, end)
            for start, end in [*existing_ranges, *selected_ranges]
        ):
            continue
        candidates.append(
            {
                **window,
                "selectionSourceLayer": layer_name,
            }
        )
    candidates.sort(key=lambda item: (-_safe_int(item.get("evidenceCount"), 0), _safe_int(item.get("frameStart"), 0)))
    return candidates


def _select_new_failing_windows(
    *,
    frame_level_probe_delta: dict[str, object],
    existing_failing_units: list[dict[str, object]],
    clip_max_frame: int,
) -> list[dict[str, object]]:
    layers = _layers_from_frame_level_probe_delta(frame_level_probe_delta)
    existing_ranges = [
        (_safe_int(unit.get("frameStart"), 0), _safe_int(unit.get("frameEnd"), 0))
        for unit in existing_failing_units
    ]
    selected_windows: list[dict[str, object]] = []
    selected_ranges: list[tuple[int, int]] = []
    for layer_name in ("filteredProbe", "rawProbe"):
        layer = dict(layers.get(layer_name) or {})
        candidates = _candidate_windows_for_layer(
            layer_name=layer_name,
            frame_ids=[_safe_int(frame_id, -1) for frame_id in list(layer.get("baselineOnlyFrameIds") or [])],
            existing_ranges=existing_ranges,
            selected_ranges=selected_ranges,
            clip_max_frame=clip_max_frame,
        )
        for candidate in candidates:
            if len(selected_windows) >= DEFAULT_MAX_NEW_FAILING_WINDOWS:
                break
            selected_windows.append(candidate)
            selected_ranges.append(
                (_safe_int(candidate.get("frameStart"), 0), _safe_int(candidate.get("frameEnd"), 0))
            )
        if len(selected_windows) >= DEFAULT_MAX_NEW_FAILING_WINDOWS:
            break
    return selected_windows


def _phase1b_units_for_source(
    *,
    curation_manifest: dict[str, object],
    source_clip_id: str,
    match_id: str,
) -> list[dict[str, object]]:
    units = curation_manifest.get("curationUnits")
    if not isinstance(units, list):
        return []
    filtered = [
        dict(unit)
        for unit in units
        if isinstance(unit, dict)
        and str(unit.get("sourceClipId") or "") == source_clip_id
        and str(unit.get("matchId") or "") == match_id
    ]
    filtered.sort(
        key=lambda unit: (
            _safe_int(unit.get("frameStart"), 0),
            _safe_int(unit.get("frameEnd"), 0),
            str(unit.get("curationUnitId") or ""),
        )
    )
    return filtered


def _bbox_payload_from_row(row: dict[str, object] | None) -> dict[str, float] | None:
    if not isinstance(row, dict):
        return None
    bbox = _row_bbox(row)
    if bbox is None:
        return None
    x1, y1, x2, y2 = bbox
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


def _select_seed_row(
    *,
    frame_id: int,
    accepted_by_frame: dict[int, list[dict[str, object]]],
    filtered_by_frame: dict[int, list[dict[str, object]]],
    raw_by_frame: dict[int, list[dict[str, object]]],
) -> tuple[str, dict[str, object]] | None:
    for seed_source, lookup in (
        ("accepted_ball", accepted_by_frame),
        ("probe_filtered", filtered_by_frame),
        ("probe_raw", raw_by_frame),
    ):
        rows = lookup.get(frame_id) or []
        if rows:
            return seed_source, dict(rows[0])
    return None


def _new_unit_from_window(
    *,
    match_id: str,
    source_clip_id: str,
    frame_start: int,
    frame_end: int,
    split_name: str,
    frames: list[dict[str, object]],
    video_path: Path,
    truth_gate_reasons: list[str],
    detector_config_provenance: dict[str, object],
    artifact_lineage_paths: dict[str, str],
    accepted_by_frame: dict[int, list[dict[str, object]]],
    filtered_by_frame: dict[int, list[dict[str, object]]],
    raw_by_frame: dict[int, list[dict[str, object]]],
) -> dict[str, object]:
    curation_unit_id = _stable_curation_unit_id(
        match_id=match_id,
        frame_start=frame_start,
        frame_end=frame_end,
    )
    frame_records = [
        frame
        for frame in frames
        if frame_start <= _safe_int(frame.get("frameId"), -1) <= frame_end
    ]
    examples: list[dict[str, object]] = []
    positive_count = 0
    negative_count = 0
    seed_sources_seen: list[str] = []
    for frame_record in frame_records:
        frame_id = _safe_int(frame_record.get("frameId"), -1)
        if frame_id < 0:
            continue
        selected = _select_seed_row(
            frame_id=frame_id,
            accepted_by_frame=accepted_by_frame,
            filtered_by_frame=filtered_by_frame,
            raw_by_frame=raw_by_frame,
        )
        file_stem = f"{match_id}__{frame_start}__f{frame_id:04d}"
        if selected is None:
            if negative_count >= DEFAULT_MAX_NEGATIVE_FRAMES_PER_UNIT:
                continue
            examples.append(
                {
                    "split": split_name,
                    "fileStem": file_stem,
                    "frameId": frame_id,
                    "timestampSeconds": _safe_float(frame_record.get("timestamp"), 0.0),
                    "videoPath": str(video_path),
                    "seedSource": "hard_negative",
                    "seedBBox": None,
                    "row": None,
                }
            )
            negative_count += 1
            if "hard_negative" not in seed_sources_seen:
                seed_sources_seen.append("hard_negative")
            continue
        raw_seed_source, row = selected
        seed_source = _seed_source_from_example_seed_source(raw_seed_source)
        seed_bbox = _bbox_payload_from_row(row)
        examples.append(
            {
                "split": split_name,
                "fileStem": file_stem,
                "frameId": frame_id,
                "timestampSeconds": _safe_float(frame_record.get("timestamp"), 0.0),
                "videoPath": str(video_path),
                "seedSource": seed_source,
                "seedBBox": seed_bbox,
                "row": row,
            }
        )
        positive_count += 1
        if seed_source not in seed_sources_seen:
            seed_sources_seen.append(seed_source)
    return {
        "curationUnitId": curation_unit_id,
        "batchName": DEFAULT_BATCH_NAME,
        "sourceClipId": source_clip_id,
        "matchId": match_id,
        "split": split_name,
        "frameStart": frame_start,
        "frameEnd": frame_end,
        "timestampStart": round(frame_start / 25.0, 3),
        "timestampEnd": round(frame_end / 25.0, 3),
        "trustCropScore": float(len(examples)),
        "trustCropReasons": ["baseline_control_probe_delta"],
        "truthGateReasons": list(truth_gate_reasons),
        "detectorConfigProvenance": detector_config_provenance,
        "artifactLineagePaths": artifact_lineage_paths,
        "labelStatus": "hybrid_label_gate",
        "seedSource": seed_sources_seen[0] if len(seed_sources_seen) == 1 else "mixed_sources",
        "positiveSeedExampleCount": positive_count,
        "negativeSeedExampleCount": negative_count,
        "examples": examples,
    }


def _build_new_overlay_item(
    *,
    curation_unit: dict[str, object],
    example: dict[str, object],
    existing_overlay_lookup: dict[str, dict[str, object]],
) -> dict[str, object]:
    seed_source = str(example.get("seedSource") or "")
    review_item_id = _stable_review_item_id(
        curation_unit_id=str(curation_unit["curationUnitId"]),
        frame_index=_safe_int(example["frameId"], -1),
        seed_source=seed_source,
    )
    existing = existing_overlay_lookup.get(review_item_id, {})
    if seed_source == "baseline_control_accepted_ball":
        default_decision = "accept_seed"
        default_label_status = "auto_accepted_pseudo_label"
        default_notes = f"[model-data-quality-fix:{DEFAULT_BATCH_NAME}: auto-accepted pseudo label]"
    elif seed_source in {"baseline_control_filtered_probe", "baseline_control_raw_probe"}:
        default_decision = "pending_review"
        default_label_status = "seeded_review_required"
        default_notes = f"[model-data-quality-fix:{DEFAULT_BATCH_NAME}: review required]"
    else:
        default_decision = "confirm_hard_negative"
        default_label_status = "auto_confirmed_hard_negative"
        default_notes = f"[model-data-quality-fix:{DEFAULT_BATCH_NAME}: hard negative]"
    reviewed_bbox = existing.get("reviewedBBox")
    if not isinstance(reviewed_bbox, dict):
        reviewed_bbox = None
    return {
        "reviewItemId": review_item_id,
        "curationUnitId": curation_unit["curationUnitId"],
        "matchId": curation_unit["matchId"],
        "sourceClipId": curation_unit["sourceClipId"],
        "frameIndex": _safe_int(example["frameId"], -1),
        "timestampSeconds": _safe_float(example["timestampSeconds"], 0.0),
        "seedSource": seed_source,
        "seedBBox": example.get("seedBBox"),
        "decision": str(existing.get("decision") or default_decision),
        "reviewedBBox": reviewed_bbox,
        "notes": str(existing.get("notes") or default_notes),
        "split": curation_unit["split"],
        "fileStem": example["fileStem"],
        "labelStatus": str(existing.get("labelStatus") or default_label_status),
        "sourceProofBundle": DEFAULT_BASELINE_CONTROL_PROOF_BUNDLE,
    }


def _seed_issue_note(curation_unit: dict[str, object]) -> str:
    return (
        f"{SEEDED_ISSUE_NOTE_PREFIX} unit={curation_unit['curationUnitId']} "
        f"source={curation_unit['sourceClipId']} "
        f"frames={curation_unit['frameStart']}-{curation_unit['frameEnd']}"
    )


def _seed_backlog_and_bundles(storage: Storage, *, new_curation_units: list[dict[str, object]]) -> dict[str, object]:
    match_ids = sorted({str(unit["matchId"]) for unit in new_curation_units})
    removed_issue_count = 0
    seeded_issue_count = 0
    removed_bundle_count = 0
    bundle_count = 0
    report_matches: dict[str, dict[str, object]] = {}
    for match_id in match_ids:
        existing_issues = storage.list_issues(match_id)
        report_matches[match_id] = {
            "removedIssueIds": [],
            "seededIssueIds": [],
            "curationUnitIds": [],
            "bundleId": None,
            "bundleItemCount": 0,
            "removedBundleIds": [],
        }
        for issue in existing_issues:
            if issue.note.startswith(SEEDED_ISSUE_NOTE_PREFIX):
                storage.delete_issue(match_id, issue.id)
                removed_issue_count += 1
                report_matches[match_id]["removedIssueIds"].append(issue.id)

    for unit in new_curation_units:
        match_id = str(unit["matchId"])
        record = storage.create_issue(
            match_id,
            CreateIssueRequest(
                frameStart=_safe_int(unit["frameStart"]),
                frameEnd=_safe_int(unit["frameEnd"]),
                timestampStart=_safe_float(unit["timestampStart"]),
                timestampEnd=_safe_float(unit["timestampEnd"]),
                bucket="tracking_failure",
                processingBackend="unknown",
                evidenceTarget="trust_eval",
                note=_seed_issue_note(unit),
            ),
        )
        seeded_issue_count += 1
        report_matches[match_id]["seededIssueIds"].append(record.id)
        report_matches[match_id]["curationUnitIds"].append(unit["curationUnitId"])

    existing_bundles = storage.list_review_bundles()
    for match_id in match_ids:
        match_units = [unit for unit in new_curation_units if str(unit["matchId"]) == match_id]
        bundle_items = [
            ReviewBundleItem(
                annotationId=str(unit["curationUnitId"]),
                matchId=match_id,
                frameStart=_safe_int(unit["frameStart"]),
                frameEnd=_safe_int(unit["frameEnd"]),
                timestampStart=_safe_float(unit["timestampStart"]),
                timestampEnd=_safe_float(unit["timestampEnd"]),
                label="model_data_quality_fix_window",
                description=f"Model/data-quality fix window for {unit['sourceClipId']}",
            )
            for unit in match_units
        ]
        batch_bundles = [
            bundle
            for bundle in existing_bundles
            if REVIEW_BUNDLE_TAG in bundle.tags and f"match:{match_id}" in bundle.tags
        ]
        if batch_bundles:
            primary_bundle = batch_bundles[0]
            for extra_bundle in batch_bundles[1:]:
                storage.delete_review_bundle(extra_bundle.id)
                removed_bundle_count += 1
                report_matches[match_id]["removedBundleIds"].append(extra_bundle.id)
            bundle = storage.update_review_bundle(
                primary_bundle.id,
                name=f"Model/Data Quality Fix - {match_id}",
                description=f"Review backlog for {match_id} from {DEFAULT_BATCH_NAME}",
                items=bundle_items,
                tags=[REVIEW_BUNDLE_TAG, f"match:{match_id}"],
            )
        else:
            bundle = storage.create_review_bundle(
                name=f"Model/Data Quality Fix - {match_id}",
                description=f"Review backlog for {match_id} from {DEFAULT_BATCH_NAME}",
                items=bundle_items,
                tags=[REVIEW_BUNDLE_TAG, f"match:{match_id}"],
            )
        bundle_count += 1
        report_matches[match_id]["bundleId"] = bundle.id
        report_matches[match_id]["bundleItemCount"] = len(bundle_items)

    return {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "seededIssueCount": seeded_issue_count,
        "removedPriorSeededIssueCount": removed_issue_count,
        "reviewBundleCount": bundle_count,
        "removedPriorBundleCount": removed_bundle_count,
        "matches": report_matches,
    }


def _yolo_label_line_from_bbox(bbox: dict[str, object], *, frame_width: int, frame_height: int) -> str:
    x1 = _safe_float(bbox.get("x1"), -1.0)
    y1 = _safe_float(bbox.get("y1"), -1.0)
    x2 = _safe_float(bbox.get("x2"), -1.0)
    y2 = _safe_float(bbox.get("y2"), -1.0)
    x_center = ((x1 + x2) / 2.0) / frame_width
    y_center = ((y1 + y2) / 2.0) / frame_height
    width = (x2 - x1) / frame_width
    height = (y2 - y1) / frame_height
    return f"0 {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"


def _label_line_for_export(frame_items: list[dict[str, object]], *, frame_width: int, frame_height: int) -> str:
    positive_candidates: list[tuple[int, dict[str, object]]] = []
    for item in frame_items:
        decision = str(item.get("decision") or "")
        if decision == "adjust_bbox" and isinstance(item.get("reviewedBBox"), dict):
            positive_candidates.append((0, dict(item["reviewedBBox"])))
        elif decision == "accept_seed" and isinstance(item.get("seedBBox"), dict):
            positive_candidates.append((1, dict(item["seedBBox"])))
    if not positive_candidates:
        return ""
    positive_candidates.sort(key=lambda item: item[0])
    return _yolo_label_line_from_bbox(
        positive_candidates[0][1],
        frame_width=frame_width,
        frame_height=frame_height,
    )


def _write_yolo_export(
    *,
    export_root: Path,
    curation_units: list[dict[str, object]],
    review_items: list[dict[str, object]],
) -> dict[str, object]:
    images_root = export_root / "images"
    labels_root = export_root / "labels"
    for split_name in ("train", "val"):
        (images_root / split_name).mkdir(parents=True, exist_ok=True)
        (labels_root / split_name).mkdir(parents=True, exist_ok=True)

    items_by_unit_frame: dict[tuple[str, int], list[dict[str, object]]] = {}
    for item in review_items:
        items_by_unit_frame.setdefault(
            (str(item.get("curationUnitId") or ""), _safe_int(item.get("frameIndex"), -1)),
            [],
        ).append(item)

    positive_count = 0
    negative_count = 0
    exported_examples: list[dict[str, object]] = []
    for unit in curation_units:
        for example in list(unit.get("examples") or []):
            split_name = str(example["split"])
            output_image = images_root / split_name / f"{example['fileStem']}.jpg"
            frame_width, frame_height = _extract_frame_image(
                video_path=Path(str(example["videoPath"])),
                frame_id=_safe_int(example["frameId"], -1),
                output_path=output_image,
            )
            label_line = _label_line_for_export(
                items_by_unit_frame.get((str(unit["curationUnitId"]), _safe_int(example["frameId"], -1)), []),
                frame_width=frame_width,
                frame_height=frame_height,
            )
            output_label = labels_root / split_name / f"{example['fileStem']}.txt"
            output_label.write_text(label_line, encoding="utf-8")
            if label_line:
                positive_count += 1
            else:
                negative_count += 1
            exported_examples.append(
                {
                    "curationUnitId": unit["curationUnitId"],
                    "split": split_name,
                    "fileStem": example["fileStem"],
                    "frameId": _safe_int(example["frameId"], -1),
                    "imagePath": str(output_image),
                    "labelPath": str(output_label),
                }
            )
    _write_dataset_yaml(export_root)
    return {
        "positiveSeedExampleCount": positive_count,
        "negativeSeedExampleCount": negative_count,
        "yoloExportReady": bool(exported_examples),
        "exportedExamples": exported_examples,
    }


def _build_split_manifest(
    *,
    curation_units: list[dict[str, object]],
    positive_seed_example_count: int,
    negative_seed_example_count: int,
    yolo_export_ready: bool,
    training_completed: bool = False,
    weights_ready: bool = False,
    ready_for_detector_evaluation: bool = False,
) -> dict[str, object]:
    splits: dict[str, dict[str, object]] = {
        "train": {"curationUnitIds": [], "sourceClipIds": set()},
        "val": {"curationUnitIds": [], "sourceClipIds": set()},
    }
    seen_units: set[str] = set()
    leakage_detected = False
    for unit in curation_units:
        split_name = str(unit.get("split") or "train")
        unit_id = str(unit.get("curationUnitId") or "")
        if unit_id in seen_units:
            leakage_detected = True
        seen_units.add(unit_id)
        splits[split_name]["curationUnitIds"].append(unit_id)
        splits[split_name]["sourceClipIds"].add(str(unit.get("sourceClipId") or ""))
    normalized_splits = {
        split_name: {
            "curationUnitIds": list(payload["curationUnitIds"]),
            "sourceClipIds": sorted(payload["sourceClipIds"]),
            "curationUnitCount": len(payload["curationUnitIds"]),
        }
        for split_name, payload in splits.items()
    }
    return {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "policy": "source_clip_window_level_deterministic_split",
        "sourceAwareSplitLeakageDetected": leakage_detected,
        "positiveSeedExampleCount": positive_seed_example_count,
        "negativeSeedExampleCount": negative_seed_example_count,
        "yoloExportReady": yolo_export_ready,
        "trainingCompleted": training_completed,
        "weightsReady": weights_ready,
        "readyForDetectorEvaluation": ready_for_detector_evaluation and not leakage_detected,
        "splits": normalized_splits,
    }


def _training_recipe() -> dict[str, object]:
    return {
        "baseModelPath": DEFAULT_BASE_MODEL_PATH,
        "imgsz": DEFAULT_IMGSZ,
        "epochs": DEFAULT_EPOCHS,
        "batch": DEFAULT_BATCH_SIZE,
        "device": DEFAULT_DEVICE,
        "workers": DEFAULT_WORKERS,
        "seed": DEFAULT_SEED,
        "augmentationPolicy": dict(train_custom.DEFAULT_AUGMENTATION_POLICY),
        "patience": DEFAULT_EPOCHS,
    }


def _build_training_config(
    *,
    dataset_yaml_path: Path,
    artifact_root: Path,
    suite_summary: dict[str, object],
    active_lane_snapshot: dict[str, object],
    manifest: dict[str, object],
    review_bundle_report: dict[str, object],
    requested_gpu_id: str | None,
    execution_mode: str,
) -> dict[str, object]:
    return {
        "generatedAt": _utc_now_iso(),
        "trainingBatchName": DEFAULT_TRAINING_BATCH_NAME,
        "trainingCandidateName": DEFAULT_CANDIDATE_NAME,
        "artifactRoot": str(artifact_root),
        "datasetYamlPath": str(dataset_yaml_path),
        "executionMode": execution_mode,
        "requestedGpuId": requested_gpu_id,
        "datasetLineage": {
            "dataQualityFixBatchName": DEFAULT_BATCH_NAME,
            "failingSourceClipId": manifest.get("failingSourceClipId"),
            "comparisonSourceClipId": manifest.get("comparisonSourceClipId"),
            "representativeFailingMatchId": manifest.get("representativeFailingMatchId"),
            "representativeControlMatchId": manifest.get("representativeControlMatchId"),
            "curationUnitCount": _safe_int(manifest.get("curationUnitCount"), 0),
            "failingCurationUnitCount": _safe_int(manifest.get("failingCurationUnitCount"), 0),
            "controlCurationUnitCount": _safe_int(manifest.get("controlCurationUnitCount"), 0),
            "selectedNewFailingWindowCount": _safe_int(manifest.get("selectedNewFailingWindowCount"), 0),
            "autoAcceptedPseudoLabelCount": _safe_int(manifest.get("autoAcceptedPseudoLabelCount"), 0),
            "pendingFilteredReviewItemCount": _safe_int(manifest.get("pendingFilteredReviewItemCount"), 0),
            "pendingRawReviewItemCount": _safe_int(manifest.get("pendingRawReviewItemCount"), 0),
            "seededIssueCount": _safe_int(review_bundle_report.get("seededIssueCount"), 0),
        },
        "trainingRecipe": _training_recipe(),
        "baselineReference": {
            "suiteVerdict": suite_summary.get("suiteVerdict"),
            "sourceRobustnessOutcome": suite_summary.get("sourceRobustnessOutcome"),
            "sourceRobustnessActiveConfigName": suite_summary.get("sourceRobustnessActiveConfigName"),
            "sourceRobustnessBestConfigName": suite_summary.get("sourceRobustnessBestConfigName"),
            "sourceRobustnessRecommendedNextLever": suite_summary.get("sourceRobustnessRecommendedNextLever"),
            "baselineFingerprint": active_lane_snapshot.get("baselineFingerprint", {}),
        },
        "seededLabelPolicy": "hybrid_auto_accept_plus_review_gate",
        "notes": [
            "Existing Phase 1B reviewed labels stay higher-precedence truth.",
            "New baseline-control accepted-ball rows are auto-accepted pseudo labels.",
            "New baseline-control filtered/raw-only probe rows stay excluded from export until reviewed.",
        ],
    }


def _build_evaluation_contract(
    *,
    active_lane_snapshot: dict[str, object],
    best_weights_path: str | None,
    last_weights_path: str | None,
    candidate_ready: bool,
) -> dict[str, object]:
    baseline_fingerprint = dict(active_lane_snapshot.get("baselineFingerprint") or {})
    return {
        "generatedAt": _utc_now_iso(),
        "trainingCandidateName": DEFAULT_CANDIDATE_NAME,
        "trainingBatchName": DEFAULT_TRAINING_BATCH_NAME,
        "candidateReadyForEvaluation": candidate_ready,
        "localScreenTargetClipPath": str(REPO_ROOT / "videos" / DEFAULT_FAILING_SOURCE_CLIP_ID),
        "remoteProofComparisonBaseline": dict(PLATEAU_BASELINE),
        "activeFrozenBaseline": {
            "detectorModelPath": baseline_fingerprint.get("detectorModelPath") or DEFAULT_BASE_MODEL_PATH,
            "primaryMode": baseline_fingerprint.get("primaryMode") or "anchored_player_ranked_context_960",
            "cleanupLane": baseline_fingerprint.get("cleanupLane") or "recent_ball_plus_inward_anchor_center_bias35_960",
        },
        "candidateWeights": {
            "bestWeightsPath": best_weights_path,
            "lastWeightsPath": last_weights_path,
        },
    }


def _rewrite_dataset_yaml_for_remote(dataset_yaml_path: Path, *, remote_export_root: str) -> str:
    rewritten_lines: list[str] = []
    replaced_path = False
    for raw_line in dataset_yaml_path.read_text(encoding="utf-8").splitlines():
        if raw_line.startswith("path:"):
            rewritten_lines.append(f"path: {remote_export_root}")
            replaced_path = True
        else:
            rewritten_lines.append(raw_line)
    if not replaced_path:
        rewritten_lines.insert(0, f"path: {remote_export_root}")
    rewritten_lines.append("")
    return "\n".join(rewritten_lines)


def _stage_dataset_on_pod(
    *,
    session: dict[str, object],
    dataset_export_root: Path,
    dataset_yaml_path: Path,
) -> str:
    remote_export_root = f"{session['remoteStorageRoot']}/training_prep/{DEFAULT_BATCH_NAME}/yolo_export"
    runpod_session.copy_directory_to_pod(
        ssh_command=list(session["sshCommand"]),
        local_path=dataset_export_root,
        remote_path=remote_export_root,
    )
    rewritten_dataset_yaml = _rewrite_dataset_yaml_for_remote(
        dataset_yaml_path,
        remote_export_root=remote_export_root,
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_dataset_yaml = Path(tmpdir) / "dataset.yaml"
        temp_dataset_yaml.write_text(rewritten_dataset_yaml, encoding="utf-8")
        runpod_session.copy_file_to_pod(
            list(session["sshCommand"]),
            local_path=temp_dataset_yaml,
            remote_path=f"{remote_export_root}/dataset.yaml",
        )
    return f"{remote_export_root}/dataset.yaml"


def _build_remote_training_command(
    *,
    session: dict[str, object],
    remote_dataset_yaml_path: str,
    staged_model_path: str,
    training_recipe: dict[str, object],
    requested_gpu_id: str | None,
) -> str:
    remote_repo_root = str(session["remoteRepoRoot"])
    remote_project_root = (
        f"{session['remoteStorageRoot']}/trained_detector_candidates/{DEFAULT_CANDIDATE_NAME}/ultralytics_run"
    )
    augmentation_policy = dict(training_recipe.get("augmentationPolicy") or {})
    remote_command = f"""
set -euo pipefail
cd {shlex.quote(remote_repo_root)}
source {shlex.quote(runpod_session.DEFAULT_POD_VENV_PATH)}/bin/activate
export PYTHONPATH={shlex.quote(remote_repo_root)}
export YOLO_CONFIG_DIR={shlex.quote(runpod_session.DEFAULT_POD_YOLO_CONFIG_DIR)}
mkdir -p {shlex.quote(remote_project_root)} {shlex.quote(runpod_session.DEFAULT_POD_YOLO_CONFIG_DIR)}
python - <<'PY'
import json
import torch
import backend.train_custom as train_custom

result = train_custom.fine_tune(
    data_yaml={remote_dataset_yaml_path!r},
    model_path={staged_model_path!r},
    epochs={_safe_int(training_recipe.get("epochs"), DEFAULT_EPOCHS)},
    imgsz={_safe_int(training_recipe.get("imgsz"), DEFAULT_IMGSZ)},
    batch={_safe_int(training_recipe.get("batch"), DEFAULT_BATCH_SIZE)},
    device={str(training_recipe.get("device") or DEFAULT_DEVICE)!r},
    project={remote_project_root!r},
    name="training",
    patience={_safe_int(training_recipe.get("patience"), DEFAULT_EPOCHS)},
    workers={_safe_int(training_recipe.get("workers"), DEFAULT_WORKERS)},
    seed={_safe_int(training_recipe.get("seed"), DEFAULT_SEED)},
    augmentation_policy={augmentation_policy!r},
)
payload = dict(result)
payload["trainingCompleted"] = True
payload["remoteDatasetYamlPath"] = {remote_dataset_yaml_path!r}
payload["remoteModelPath"] = {staged_model_path!r}
payload["requestedGpuId"] = {requested_gpu_id!r}
payload["remoteDeviceName"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
payload["allocatedGpuId"] = payload["remoteDeviceName"]
print(json.dumps(payload))
PY
"""
    return f"bash -lc {shlex.quote(remote_command)}"


def _pull_remote_artifact(
    *,
    session: dict[str, object],
    remote_path: str | None,
    local_path: Path,
) -> str | None:
    runpod_session.require_retired_runpod_disabled()


def _candidate_ready_for_evaluation(
    *,
    weights_ready: bool,
    evaluation_contract_ready: bool,
    remote_training_result: dict[str, object],
) -> tuple[bool, str | None]:
    if not weights_ready:
        return False, "weights_unusable"
    if not evaluation_contract_ready:
        return False, "evaluation_contract_incomplete"
    if not str(remote_training_result.get("remoteDatasetYamlPath") or "").strip():
        return False, "training_provenance_incomplete"
    if not str(remote_training_result.get("remoteModelPath") or "").strip():
        return False, "training_provenance_incomplete"
    return True, None


def _allocated_gpu_id(session: dict[str, object], remote_training_result: dict[str, object]) -> str | None:
    for value in (
        remote_training_result.get("allocatedGpuId"),
        remote_training_result.get("remoteDeviceName"),
        (session.get("podPayload") or {}).get("gpuId") if isinstance(session.get("podPayload"), dict) else None,
    ):
        text = str(value or "").strip()
        if text:
            return text
    return None


def _candidate_batch_brainstorm_fixes(primary_blocker: str | None, error_message: str | None) -> list[str]:
    if primary_blocker == "remote_training_failed":
        fixes = [
            "Inspect the remote training error and rerun the v3 batch after fixing the pod-side training command or runtime dependency issue.",
            "Confirm the data-quality-fix dataset staged correctly on the pod and that the remote dataset.yaml path points at the pod copy.",
        ]
        if error_message:
            fixes.append(f"Start with the captured training error: {error_message}")
        return fixes
    if primary_blocker == "weights_unusable":
        return [
            "Verify the remote Ultralytics run produced best.pt and last.pt, then rerun the v3 batch.",
            "Confirm the pull-back paths match the remote training output paths.",
        ]
    return [
        "Inspect the latest v3 training_run_summary.json and batch_outcome_analysis.json before rerunning the batch.",
        "Fix the primary training blocker and rerun the same data-quality batch without changing the evaluation contract.",
    ]


def _build_candidate_batch_outcome(
    *,
    training_completed: bool,
    weights_ready: bool,
    evaluation_contract_ready: bool,
    ready_for_detector_evaluation: bool,
    primary_blocker: str | None,
    error_message: str | None,
) -> dict[str, object]:
    goal_achieved = ready_for_detector_evaluation
    roadmap_advance_allowed = goal_achieved
    if goal_achieved:
        english_summary = (
            "This batch trained a refreshed v3 detector candidate from the targeted data-quality dataset and prepared it for bounded evaluation."
        )
        english_decision = (
            "The training part of the batch achieved its goal, so the new candidate is ready for the next bounded evaluation run."
        )
    else:
        blocker_text = str(primary_blocker or "unknown_blocker").replace("_", " ")
        english_summary = (
            "This batch was trying to produce a complete, evaluation-ready v3 detector candidate, but the training artifact is still incomplete."
        )
        english_decision = (
            f"The training part of the batch did not achieve its goal because of the current blocker: {blocker_text}."
        )
    return {
        "batchGoal": "Train one refreshed v3 detector candidate from the targeted model/data-quality export and make it evaluation-ready.",
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": roadmap_advance_allowed,
        "englishSummary": english_summary,
        "englishDecision": english_decision,
        "primaryBlocker": primary_blocker,
        "trainingCompleted": training_completed,
        "weightsReady": weights_ready,
        "evaluationContractReady": evaluation_contract_ready,
        "readyForDetectorEvaluation": ready_for_detector_evaluation,
        "nextRecommendedNextLever": NEXT_LEVER_EVALUATE if goal_achieved else NEXT_LEVER_RETRAIN,
        "brainstormFixes": [] if goal_achieved else _candidate_batch_brainstorm_fixes(primary_blocker, error_message),
    }


def _candidate_batch_outcome_markdown(batch_outcome_analysis: dict[str, object]) -> str:
    fixes = list(batch_outcome_analysis.get("brainstormFixes") or [])
    fix_lines = "\n".join(f"- {fix}" for fix in fixes) if fixes else "- None"
    return "\n".join(
        [
            "# Batch Outcome Analysis",
            "",
            f"Batch goal: {batch_outcome_analysis.get('batchGoal')}",
            f"Goal achieved: {batch_outcome_analysis.get('goalAchieved')}",
            f"Roadmap advance allowed: {batch_outcome_analysis.get('roadmapAdvanceAllowed')}",
            "",
            f"Summary: {batch_outcome_analysis.get('englishSummary')}",
            f"Decision: {batch_outcome_analysis.get('englishDecision')}",
            f"Primary blocker: {batch_outcome_analysis.get('primaryBlocker')}",
            "",
            f"Training completed: {batch_outcome_analysis.get('trainingCompleted')}",
            f"Weights ready: {batch_outcome_analysis.get('weightsReady')}",
            f"Evaluation contract ready: {batch_outcome_analysis.get('evaluationContractReady')}",
            f"Ready for detector evaluation: {batch_outcome_analysis.get('readyForDetectorEvaluation')}",
            f"Next recommended next lever: {batch_outcome_analysis.get('nextRecommendedNextLever')}",
            "",
            "Brainstormed fixes:",
            fix_lines,
            "",
        ]
    )


def _overall_brainstorm_fixes(
    *,
    primary_blocker: str | None,
    selected_new_failing_window_count: int,
    training_error_message: str | None,
) -> list[str]:
    if primary_blocker == "no_new_failing_windows_selected":
        return [
            "Inspect the current frame_level_probe_delta.json and relax the candidate-window shortage only if the saved evidence proves there are still non-overlapping failing-source windows to add.",
            "If no additional non-overlapping windows exist, use the generated diagnosis to choose a different model/data fix inside the same evaluation lane.",
        ]
    if primary_blocker == "yolo_export_empty":
        return [
            "Inspect the generated overlay and confirm the new accepted pseudo labels are actually present in the export.",
            "Keep the batch on the data-fix lane until at least one new accepted pseudo label is exportable.",
        ]
    if primary_blocker in {"remote_training_failed", "weights_unusable", "training_provenance_incomplete", "evaluation_contract_incomplete"}:
        fixes = [
            "Keep the roadmap pinned on evaluate_touchline_detector_candidate and fix the v3 training artifact before rerunning evaluation.",
            f"The targeted data-fix windows were selected successfully ({selected_new_failing_window_count}), so do not reopen the selector or label-gate logic first.",
        ]
        if training_error_message:
            fixes.append(f"Start with the captured remote training error: {training_error_message}")
        return fixes
    return [
        "Inspect the latest batch_outcome_analysis.json and training_run_summary.json before rerunning this batch.",
        "Fix the current blocker without changing the bounded evaluation policy or reopening earlier lanes.",
    ]


def _build_batch_outcome_analysis(
    *,
    selected_new_failing_window_count: int,
    auto_accepted_pseudo_label_count: int,
    pending_filtered_review_item_count: int,
    pending_raw_review_item_count: int,
    yolo_export_ready: bool,
    training_completed: bool,
    weights_ready: bool,
    ready_for_detector_evaluation: bool,
    primary_blocker: str | None,
    training_error_message: str | None,
) -> dict[str, object]:
    goal_achieved = (
        selected_new_failing_window_count > 0
        and yolo_export_ready
        and training_completed
        and weights_ready
        and ready_for_detector_evaluation
    )
    roadmap_advance_allowed = False
    if goal_achieved:
        english_summary = (
            "This batch added targeted failing-source windows from the live failure diagnosis, generated a cleaner hybrid-label export, and trained an evaluation-ready v3 candidate."
        )
        english_decision = (
            "The batch achieved its goal, but the suite stays pinned on evaluate_touchline_detector_candidate until v3 wins a later bounded evaluation."
        )
    else:
        blocker_text = str(primary_blocker or "unknown_blocker").replace("_", " ")
        english_summary = (
            "This batch was trying to produce a targeted model/data-quality fix and a complete v3 candidate, but it did not get all the way there."
        )
        english_decision = (
            f"The batch did not achieve its goal, so the roadmap must stay on evaluate_touchline_detector_candidate while we fix the current blocker: {blocker_text}."
        )
    return {
        "batchGoal": "Create a targeted failing-source data-quality fix artifact and retrain one evaluation-ready touchline_detector_candidate_v3.",
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": roadmap_advance_allowed,
        "englishSummary": english_summary,
        "englishDecision": english_decision,
        "primaryBlocker": primary_blocker,
        "selectedNewFailingWindowCount": selected_new_failing_window_count,
        "autoAcceptedPseudoLabelCount": auto_accepted_pseudo_label_count,
        "pendingFilteredReviewItemCount": pending_filtered_review_item_count,
        "pendingRawReviewItemCount": pending_raw_review_item_count,
        "yoloExportReady": yolo_export_ready,
        "trainingCompleted": training_completed,
        "weightsReady": weights_ready,
        "readyForDetectorEvaluation": ready_for_detector_evaluation,
        "nextRecommendedNextLever": NEXT_LEVER_EVALUATE,
        "brainstormFixes": (
            []
            if goal_achieved
            else _overall_brainstorm_fixes(
                primary_blocker=primary_blocker,
                selected_new_failing_window_count=selected_new_failing_window_count,
                training_error_message=training_error_message,
            )
        ),
    }


def _batch_outcome_markdown(batch_outcome_analysis: dict[str, object]) -> str:
    fixes = list(batch_outcome_analysis.get("brainstormFixes") or [])
    fix_lines = "\n".join(f"- {fix}" for fix in fixes) if fixes else "- None"
    return "\n".join(
        [
            "# Batch Outcome Analysis",
            "",
            f"Batch goal: {batch_outcome_analysis.get('batchGoal')}",
            f"Goal achieved: {batch_outcome_analysis.get('goalAchieved')}",
            f"Roadmap advance allowed: {batch_outcome_analysis.get('roadmapAdvanceAllowed')}",
            "",
            f"Summary: {batch_outcome_analysis.get('englishSummary')}",
            f"Decision: {batch_outcome_analysis.get('englishDecision')}",
            f"Primary blocker: {batch_outcome_analysis.get('primaryBlocker')}",
            "",
            f"Selected new failing window count: {batch_outcome_analysis.get('selectedNewFailingWindowCount')}",
            f"Auto-accepted pseudo-label count: {batch_outcome_analysis.get('autoAcceptedPseudoLabelCount')}",
            f"Pending filtered review item count: {batch_outcome_analysis.get('pendingFilteredReviewItemCount')}",
            f"Pending raw review item count: {batch_outcome_analysis.get('pendingRawReviewItemCount')}",
            f"YOLO export ready: {batch_outcome_analysis.get('yoloExportReady')}",
            f"Training completed: {batch_outcome_analysis.get('trainingCompleted')}",
            f"Weights ready: {batch_outcome_analysis.get('weightsReady')}",
            f"Ready for detector evaluation: {batch_outcome_analysis.get('readyForDetectorEvaluation')}",
            f"Next recommended next lever: {batch_outcome_analysis.get('nextRecommendedNextLever')}",
            "",
            "Brainstormed fixes:",
            fix_lines,
            "",
            "Roadmap rule: even a successful data-quality fix batch keeps the suite on evaluate_touchline_detector_candidate until a later bounded evaluation batch wins.",
            "",
        ]
    )


def run_touchline_detector_candidate_model_data_quality_fix(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    execution_mode: str = DEFAULT_EXECUTION_MODE,
) -> dict[str, object]:
    runpod_session.require_retired_runpod_disabled()


def main() -> None:
    runpod_session.require_retired_runpod_disabled()


if __name__ == "__main__":
    main()
