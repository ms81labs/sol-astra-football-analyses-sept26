from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.app.schemas import CreateIssueRequest, ReviewBundleItem  # noqa: E402
from backend.app.storage import Storage  # noqa: E402
from backend.app.trust_crops import TrustCrop, compute_trust_crops  # noqa: E402
import backend.scripts.run_touchline_training_data_curation_batch as phase1  # noqa: E402


DEFAULT_BATCH_NAME = "touchline_review_densification_v1"
DEFAULT_PHASE1_BATCH_NAME = "touchline_training_data_curation_foundation"
DEFAULT_CURATION_ROOT = "touchline_review_densification_v1"
DEFAULT_MAX_FAILING_WINDOWS = 5
DEFAULT_MAX_ADDITIONAL_FAILING_WINDOWS = 4
DEFAULT_MAX_TRUST_CROP_CANDIDATES = 20
DEFAULT_MAX_NEGATIVE_FRAMES_PER_UNIT = phase1.DEFAULT_MAX_NEGATIVE_FRAMES_PER_UNIT
SEEDED_ISSUE_NOTE_PREFIX = f"[review-densification:{DEFAULT_BATCH_NAME}]"
REVIEW_BUNDLE_TAG = f"review-densification:{DEFAULT_BATCH_NAME}"
NEXT_LEVER_PHASE1B = "start_phase_1b_review_densification"
NEXT_LEVER_RETRAIN = "retrain_touchline_detector_candidate"
REVIEW_DECISIONS = {
    "pending_review",
    "accept_seed",
    "adjust_bbox",
    "reject_seed",
    "confirm_hard_negative",
}

_safe_int = phase1._safe_int
_safe_float = phase1._safe_float
_resolve_video_path = phase1._resolve_video_path
_load_optional_analysis_artifact = phase1._load_optional_analysis_artifact
_truth_gate_reason_lookup = phase1._truth_gate_reason_lookup
_group_rows_by_frame = phase1._group_rows_by_frame
_select_seed_row = phase1._select_seed_row
_row_bbox = phase1._row_bbox
_write_dataset_yaml = phase1._write_dataset_yaml
_extract_frame_image = phase1._extract_frame_image


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object payload in {path}")
    return payload


def _stable_curation_unit_id(*, match_id: str, frame_start: int, frame_end: int) -> str:
    raw = f"{DEFAULT_BATCH_NAME}:{match_id}:{frame_start}:{frame_end}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _stable_review_item_id(*, curation_unit_id: str, frame_index: int, seed_source: str) -> str:
    raw = f"{DEFAULT_BATCH_NAME}:{curation_unit_id}:{frame_index}:{seed_source}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def _paths(storage_root: Path) -> dict[str, Path]:
    suite_dir = storage_root / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
    phase1_root = storage_root / "training_prep" / DEFAULT_PHASE1_BATCH_NAME
    candidate_eval_root = (
        storage_root
        / "trained_detector_candidates"
        / "touchline_detector_candidate_v1"
        / "evaluation_v1"
    )
    artifact_root = storage_root / "training_prep" / DEFAULT_CURATION_ROOT
    return {
        "activeLaneSnapshotPath": suite_dir / "active_lane_snapshot.json",
        "suiteSummaryPath": suite_dir / "suite_summary.json",
        "suiteRobustnessDiagnosisPath": suite_dir / "suite_robustness_diagnosis.json",
        "failureAuditPath": suite_dir / "primary_source_robustness_failure_audit.json",
        "sliceProjectionPath": suite_dir / "primary_source_robustness_slice_projection.json",
        "detectorBreadthMatrixPath": suite_dir / "detector_breadth_matrix.json",
        "phase1ManifestPath": phase1_root / "curation_manifest.json",
        "phase1SplitManifestPath": phase1_root / "split_manifest.json",
        "phase1SeededIssueReportPath": phase1_root / "seeded_issue_report.json",
        "candidateEvaluationSummaryPath": candidate_eval_root / "evaluation_summary.json",
        "artifactRoot": artifact_root,
        "reviewDensificationManifestPath": artifact_root / "review_densification_manifest.json",
        "reviewedLabelOverlayPath": artifact_root / "reviewed_label_overlay.json",
        "reviewBundleReportPath": artifact_root / "review_bundle_report.json",
        "splitManifestPath": artifact_root / "split_manifest.json",
        "batchOutcomeAnalysisPath": artifact_root / "batch_outcome_analysis.json",
        "batchOutcomeAnalysisMarkdownPath": artifact_root / "batch_outcome_analysis.md",
        "exportRoot": artifact_root / "yolo_export",
    }


def _load_phase1_payloads(paths: dict[str, Path]) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    return (
        _load_json(paths["phase1ManifestPath"]),
        _load_json(paths["phase1SplitManifestPath"]),
        _load_json(paths["phase1SeededIssueReportPath"]),
    )


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
        if not review_item_id:
            continue
        lookup[review_item_id] = dict(item)
    return lookup


def _bbox_payload_from_row(row: dict[str, object] | None) -> dict[str, float] | None:
    if not isinstance(row, dict):
        return None
    bbox = _row_bbox(row)
    if bbox is None:
        return None
    x1, y1, x2, y2 = bbox
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


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


def _ranges_overlap(
    left_start: int,
    left_end: int,
    right_start: int,
    right_end: int,
) -> bool:
    return not (left_end < right_start or right_end < left_start)


def _sorted_phase1_units(
    *,
    curation_manifest: dict[str, object],
    source_clip_id: str,
    match_id: str,
) -> list[dict[str, object]]:
    units = curation_manifest.get("curationUnits")
    if not isinstance(units, list):
        return []
    return sorted(
        [
            dict(unit)
            for unit in units
            if isinstance(unit, dict)
            and str(unit.get("sourceClipId") or "") == source_clip_id
            and str(unit.get("matchId") or "") == match_id
        ],
        key=lambda unit: (
            _safe_int(unit.get("frameStart"), 0),
            _safe_int(unit.get("frameEnd"), 0),
            str(unit.get("curationUnitId") or ""),
        ),
    )


def _select_additional_failing_crops(
    *,
    existing_units: list[dict[str, object]],
    trust_crops: list[TrustCrop],
) -> tuple[list[TrustCrop], int]:
    selected_ranges = [
        (_safe_int(unit.get("frameStart"), 0), _safe_int(unit.get("frameEnd"), 0))
        for unit in existing_units
    ]
    additional: list[TrustCrop] = []
    for crop in sorted(trust_crops, key=lambda item: (-float(item.score), int(item.frameStart), int(item.frameEnd))):
        if any(
            _ranges_overlap(crop.frameStart, crop.frameEnd, range_start, range_end)
            for range_start, range_end in selected_ranges
        ):
            continue
        additional.append(crop)
        selected_ranges.append((crop.frameStart, crop.frameEnd))
        if len(selected_ranges) >= DEFAULT_MAX_FAILING_WINDOWS:
            break
    shortage = max(0, DEFAULT_MAX_ADDITIONAL_FAILING_WINDOWS - len(additional))
    return additional, shortage


def _unit_from_window(
    *,
    match_id: str,
    source_clip_id: str,
    split_name: str,
    frame_start: int,
    frame_end: int,
    timestamp_start: float,
    timestamp_end: float,
    trust_crop_score: float,
    trust_crop_reasons: list[str],
    truth_gate_reasons: list[str],
    detector_config_provenance: dict[str, object],
    artifact_lineage_paths: dict[str, str],
    frames: list[dict[str, object]],
    video_path: Path,
    accepted_by_frame: dict[int, list[dict[str, object]]],
    probe_filtered_by_frame: dict[int, list[dict[str, object]]],
    probe_raw_by_frame: dict[int, list[dict[str, object]]],
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
    negative_count = 0
    seed_sources_seen: list[str] = []
    for frame_record in frame_records:
        frame_id = _safe_int(frame_record.get("frameId"), -1)
        if frame_id < 0:
            continue
        selected = _select_seed_row(
            frame_id=frame_id,
            accepted_by_frame=accepted_by_frame,
            probe_filtered_by_frame=probe_filtered_by_frame,
            probe_raw_by_frame=probe_raw_by_frame,
        )
        file_stem = f"{match_id}__{frame_start}__f{frame_id:04d}"
        if selected is None:
            if negative_count >= DEFAULT_MAX_NEGATIVE_FRAMES_PER_UNIT:
                continue
            negative_count += 1
            seed_source = "hard_negative"
            row = None
        else:
            seed_source, row = selected
        seed_sources_seen.append(seed_source)
        examples.append(
            {
                "split": split_name,
                "fileStem": file_stem,
                "frameId": frame_id,
                "timestampSeconds": _safe_float(frame_record.get("timestamp"), 0.0),
                "videoPath": str(video_path),
                "seedSource": seed_source,
                "seedBBox": _bbox_payload_from_row(row),
                "row": row,
            }
        )
    positive_count = sum(1 for example in examples if example["seedSource"] != "hard_negative")
    negative_count = sum(1 for example in examples if example["seedSource"] == "hard_negative")
    primary_seed_source = next((source for source in seed_sources_seen if source != "hard_negative"), "hard_negative")
    return {
        "curationUnitId": curation_unit_id,
        "batchName": DEFAULT_BATCH_NAME,
        "sourceClipId": source_clip_id,
        "matchId": match_id,
        "split": split_name,
        "frameStart": frame_start,
        "frameEnd": frame_end,
        "timestampStart": timestamp_start,
        "timestampEnd": timestamp_end,
        "trustCropScore": trust_crop_score,
        "trustCropReasons": list(trust_crop_reasons),
        "truthGateReasons": list(truth_gate_reasons),
        "detectorConfigProvenance": detector_config_provenance,
        "artifactLineagePaths": artifact_lineage_paths,
        "labelStatus": "seeded_review_required",
        "seedSource": primary_seed_source,
        "positiveSeedExampleCount": positive_count,
        "negativeSeedExampleCount": negative_count,
        "examples": examples,
    }


def _overlay_item_from_example(
    *,
    curation_unit: dict[str, object],
    example: dict[str, object],
    existing_overlay_lookup: dict[str, dict[str, object]],
) -> dict[str, object]:
    review_item_id = _stable_review_item_id(
        curation_unit_id=str(curation_unit["curationUnitId"]),
        frame_index=_safe_int(example["frameId"]),
        seed_source=str(example["seedSource"]),
    )
    existing = existing_overlay_lookup.get(review_item_id, {})
    decision = str(existing.get("decision") or "pending_review")
    reviewed_bbox = existing.get("reviewedBBox")
    if not isinstance(reviewed_bbox, dict):
        reviewed_bbox = None
    return {
        "reviewItemId": review_item_id,
        "curationUnitId": curation_unit["curationUnitId"],
        "matchId": curation_unit["matchId"],
        "sourceClipId": curation_unit["sourceClipId"],
        "frameIndex": _safe_int(example["frameId"]),
        "timestampSeconds": _safe_float(example["timestampSeconds"]),
        "seedSource": example["seedSource"],
        "seedBBox": example["seedBBox"],
        "decision": decision,
        "reviewedBBox": reviewed_bbox,
        "notes": str(existing.get("notes") or ""),
        "split": curation_unit["split"],
        "fileStem": example["fileStem"],
    }


def _overlay_counts(review_items: list[dict[str, object]]) -> dict[str, int]:
    pending = sum(str(item.get("decision") or "") == "pending_review" for item in review_items)
    reviewed_positive = sum(
        str(item.get("decision") or "") in {"accept_seed", "adjust_bbox"} for item in review_items
    )
    reviewed_negative = sum(
        str(item.get("decision") or "") in {"reject_seed", "confirm_hard_negative"} for item in review_items
    )
    return {
        "reviewItemCount": len(review_items),
        "pendingReviewCount": pending,
        "reviewedPositiveCount": reviewed_positive,
        "reviewedNegativeCount": reviewed_negative,
    }


def _count_pending_by_source(
    *,
    review_items: list[dict[str, object]],
    failing_source_clip_id: str,
    comparison_source_clip_id: str,
) -> dict[str, object]:
    pending_failing = sum(
        str(item.get("sourceClipId") or "") == failing_source_clip_id
        and str(item.get("decision") or "") == "pending_review"
        for item in review_items
    )
    pending_control = sum(
        str(item.get("sourceClipId") or "") == comparison_source_clip_id
        and str(item.get("decision") or "") == "pending_review"
        for item in review_items
    )
    return {
        "pendingFailingReviewCount": pending_failing,
        "pendingControlReviewCount": pending_control,
        "failingSourceReviewComplete": pending_failing == 0,
        "controlReviewComplete": pending_control == 0,
    }


def _valid_bbox_payload(bbox: object) -> bool:
    if not isinstance(bbox, dict):
        return False
    x1 = _safe_float(bbox.get("x1"), float("nan"))
    y1 = _safe_float(bbox.get("y1"), float("nan"))
    x2 = _safe_float(bbox.get("x2"), float("nan"))
    y2 = _safe_float(bbox.get("y2"), float("nan"))
    return x2 > x1 and y2 > y1


def _validate_review_items(review_items: list[dict[str, object]]) -> list[dict[str, object]]:
    errors: list[dict[str, object]] = []
    for item in review_items:
        decision = str(item.get("decision") or "").strip()
        if decision not in REVIEW_DECISIONS:
            errors.append(
                {
                    "reviewItemId": item.get("reviewItemId"),
                    "curationUnitId": item.get("curationUnitId"),
                    "sourceClipId": item.get("sourceClipId"),
                    "frameIndex": _safe_int(item.get("frameIndex"), -1),
                    "decision": decision,
                    "reason": "unknown_review_decision",
                }
            )
            continue
        if decision == "adjust_bbox" and not _valid_bbox_payload(item.get("reviewedBBox")):
            errors.append(
                {
                    "reviewItemId": item.get("reviewItemId"),
                    "curationUnitId": item.get("curationUnitId"),
                    "sourceClipId": item.get("sourceClipId"),
                    "frameIndex": _safe_int(item.get("frameIndex"), -1),
                    "decision": decision,
                    "reason": "adjust_bbox_requires_reviewed_bbox",
                }
            )
        if decision == "accept_seed" and not _valid_bbox_payload(item.get("seedBBox")):
            errors.append(
                {
                    "reviewItemId": item.get("reviewItemId"),
                    "curationUnitId": item.get("curationUnitId"),
                    "sourceClipId": item.get("sourceClipId"),
                    "frameIndex": _safe_int(item.get("frameIndex"), -1),
                    "decision": decision,
                    "reason": "accept_seed_requires_seed_bbox",
                }
            )
    return errors


def _review_primary_blocker(
    *,
    failing_review_items: list[dict[str, object]],
    split_leakage_detected: bool,
    lineage_complete: bool,
    overlay_validation_errors: list[dict[str, object]] | None = None,
) -> str | None:
    if overlay_validation_errors:
        return "overlay_validation_failed"
    if split_leakage_detected:
        return "source_aware_split_leakage_detected"
    if not lineage_complete:
        return "overlay_lineage_incomplete"
    if any(str(item.get("decision") or "") == "pending_review" for item in failing_review_items):
        return "pending_review_items_remaining"
    return None


def _seed_issue_note(curation_unit: dict[str, object]) -> str:
    reasons = ",".join(str(reason) for reason in curation_unit.get("trustCropReasons", []))
    return (
        f"{SEEDED_ISSUE_NOTE_PREFIX} unit={curation_unit['curationUnitId']} "
        f"source={curation_unit['sourceClipId']} "
        f"frames={curation_unit['frameStart']}-{curation_unit['frameEnd']} "
        f"score={curation_unit['trustCropScore']} "
        f"reasons={reasons}"
    )


def _seed_backlog_and_bundles(
    storage: Storage,
    *,
    curation_units: list[dict[str, object]],
) -> dict[str, object]:
    match_ids = sorted({str(unit["matchId"]) for unit in curation_units})
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

    for unit in curation_units:
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
        match_units = [unit for unit in curation_units if str(unit["matchId"]) == match_id]
        bundle_items = [
            ReviewBundleItem(
                annotationId=str(unit["curationUnitId"]),
                matchId=match_id,
                frameStart=_safe_int(unit["frameStart"]),
                frameEnd=_safe_int(unit["frameEnd"]),
                timestampStart=_safe_float(unit["timestampStart"]),
                timestampEnd=_safe_float(unit["timestampEnd"]),
                label="phase1b_review_window",
                description=f"Phase 1B review window for {unit['sourceClipId']}",
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
                name=f"Phase 1B Review Densification - {match_id}",
                description=f"Review backlog for {match_id} from {DEFAULT_BATCH_NAME}",
                items=bundle_items,
                tags=[REVIEW_BUNDLE_TAG, f"match:{match_id}"],
            )
        else:
            bundle = storage.create_review_bundle(
                name=f"Phase 1B Review Densification - {match_id}",
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


def _label_line_for_frame_items(
    frame_items: list[dict[str, object]],
    *,
    frame_width: int,
    frame_height: int,
) -> str:
    positive_candidates: list[tuple[int, dict[str, object]]] = []
    for item in frame_items:
        decision = str(item.get("decision") or "")
        if decision == "adjust_bbox" and isinstance(item.get("reviewedBBox"), dict):
            positive_candidates.append((0, dict(item["reviewedBBox"])))
        elif decision == "accept_seed" and isinstance(item.get("seedBBox"), dict):
            positive_candidates.append((1, dict(item["seedBBox"])))
        elif decision == "pending_review" and isinstance(item.get("seedBBox"), dict):
            positive_candidates.append((2, dict(item["seedBBox"])))
    if not positive_candidates:
        return ""
    positive_candidates.sort(key=lambda item: item[0])
    return _yolo_label_line_from_bbox(
        positive_candidates[0][1],
        frame_width=frame_width,
        frame_height=frame_height,
    )


def _review_priority_key(item: dict[str, object]) -> tuple[int, int, str]:
    source_priority = {
        "hard_negative": 0,
        "probe_raw": 1,
        "probe_filtered": 2,
        "accepted_ball": 3,
    }.get(str(item.get("seedSource") or ""), 4)
    return (
        source_priority,
        _safe_int(item.get("frameIndex"), 0),
        str(item.get("reviewItemId") or ""),
    )


def _build_split_manifest(
    *,
    curation_units: list[dict[str, object]],
    positive_seed_example_count: int,
    negative_seed_example_count: int,
    ready_for_retraining: bool,
    primary_blocker: str | None,
) -> dict[str, object]:
    splits: dict[str, dict[str, object]] = {
        "train": {"curationUnitIds": [], "sourceClipIds": set()},
        "val": {"curationUnitIds": [], "sourceClipIds": set()},
    }
    seen_units: set[str] = set()
    leakage_detected = False
    for unit in curation_units:
        split_name = str(unit["split"])
        unit_id = str(unit["curationUnitId"])
        if unit_id in seen_units:
            leakage_detected = True
        seen_units.add(unit_id)
        splits[split_name]["curationUnitIds"].append(unit_id)
        splits[split_name]["sourceClipIds"].add(str(unit["sourceClipId"]))
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
        "readyForRetraining": ready_for_retraining and not leakage_detected,
        "reviewDensificationPrimaryBlocker": (
            "source_aware_split_leakage_detected" if leakage_detected else primary_blocker
        ),
        "splits": normalized_splits,
    }


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
            (str(item["curationUnitId"]), _safe_int(item["frameIndex"])),
            [],
        ).append(item)

    positive_count = 0
    negative_count = 0
    exported_examples: list[dict[str, object]] = []
    for unit in curation_units:
        for example in unit.get("examples", []):
            split_name = str(example["split"])
            output_image = images_root / split_name / f"{example['fileStem']}.jpg"
            frame_width, frame_height = _extract_frame_image(
                video_path=Path(str(example["videoPath"])),
                frame_id=_safe_int(example["frameId"]),
                output_path=output_image,
            )
            label_line = _label_line_for_frame_items(
                items_by_unit_frame.get((str(unit["curationUnitId"]), _safe_int(example["frameId"])), []),
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
                    "frameId": _safe_int(example["frameId"]),
                    "imagePath": str(output_image),
                    "labelPath": str(output_label),
                }
            )
    _write_dataset_yaml(export_root)
    return {
        "positiveSeedExampleCount": positive_count,
        "negativeSeedExampleCount": negative_count,
        "exportedExamples": exported_examples,
        "yoloExportRegenerated": bool(exported_examples),
    }


def _candidate_evaluation_summary(storage_root: Path) -> dict[str, object]:
    path = (
        Path(storage_root)
        / "trained_detector_candidates"
        / "touchline_detector_candidate_v1"
        / "evaluation_v1"
        / "evaluation_summary.json"
    )
    return _load_json(path)


def _brainstorm_fixes(
    *,
    primary_blocker: str | None,
    validation_errors: list[dict[str, object]],
    pending_failing_review_count: int,
) -> list[str]:
    if primary_blocker == "overlay_validation_failed":
        fixes = ["Fix the invalid review decisions listed in overlayValidationErrors and rerun the Phase 1B batch."]
        reasons = {str(error.get("reason") or "") for error in validation_errors}
        if "adjust_bbox_requires_reviewed_bbox" in reasons:
            fixes.append("For every `adjust_bbox` item, add a reviewedBBox with x1 < x2 and y1 < y2.")
        if "accept_seed_requires_seed_bbox" in reasons:
            fixes.append("Change any `accept_seed` item without a seed box to `reject_seed` or provide a valid seeded source.")
        if "unknown_review_decision" in reasons:
            fixes.append(
                "Replace unknown decision values with one of: pending_review, accept_seed, adjust_bbox, reject_seed, confirm_hard_negative."
            )
        return fixes
    if primary_blocker == "pending_review_items_remaining":
        fixes = [
            "Complete the remaining failing-source review items in reviewed_label_overlay.json before rerunning the batch.",
            "Review the failing-source items in order: hard negatives first, then probe_raw positives, then accepted_ball positives.",
        ]
        if pending_failing_review_count > 0:
            fixes.append(f"Resolve the {pending_failing_review_count} remaining failing-source pending_review items.")
        return fixes
    if primary_blocker == "source_aware_split_leakage_detected":
        return [
            "Fix the curation-unit split leakage so no window appears in both train and val.",
            "Regenerate the Phase 1B export after the split manifest is clean.",
        ]
    if primary_blocker == "overlay_lineage_incomplete":
        return [
            "Restore missing lineage paths in the densification manifest before rerunning the export.",
            "Rerun the Phase 1B batch once every curation unit has complete artifact provenance.",
        ]
    return [
        "Inspect the latest batch_outcome_analysis.json and reviewed_label_overlay.json for the unresolved gate condition.",
        "Fix the remaining Phase 1B blocker and rerun the densification batch before moving the roadmap forward.",
    ]


def _build_batch_outcome_analysis(
    *,
    pending_failing_review_count: int,
    pending_control_review_count: int,
    ready_for_retraining: bool,
    next_lever: str,
    primary_blocker: str | None,
    validation_errors: list[dict[str, object]],
) -> dict[str, object]:
    goal_achieved = ready_for_retraining
    roadmap_advance_allowed = goal_achieved
    if goal_achieved:
        english_summary = (
            "This batch finished the failing-source review gate, regenerated the export, and left control review items as optional follow-up."
        )
        english_decision = (
            "The batch achieved its goal, so the roadmap may advance to retraining the touchline detector candidate."
        )
    else:
        blocker_text = str(primary_blocker or "unknown_blocker").replace("_", " ")
        english_summary = (
            "This batch was trying to finish the failing-source review gate, but it did not get there yet."
        )
        english_decision = (
            f"The batch did not achieve its goal, so the roadmap must stay in Phase 1B until we fix the current blocker: {blocker_text}."
        )
    return {
        "batchGoal": "Complete the failing-source review overlay for trimed-5min.mp4, regenerate the export, and unlock the retraining gate.",
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": roadmap_advance_allowed,
        "englishSummary": english_summary,
        "englishDecision": english_decision,
        "primaryBlocker": primary_blocker,
        "pendingFailingReviewCount": pending_failing_review_count,
        "pendingControlReviewCount": pending_control_review_count,
        "readyForRetraining": ready_for_retraining,
        "nextRecommendedNextLever": next_lever,
        "brainstormFixes": (
            []
            if goal_achieved
            else _brainstorm_fixes(
                primary_blocker=primary_blocker,
                validation_errors=validation_errors,
                pending_failing_review_count=pending_failing_review_count,
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
            f"Pending failing review count: {batch_outcome_analysis.get('pendingFailingReviewCount')}",
            f"Pending control review count: {batch_outcome_analysis.get('pendingControlReviewCount')}",
            f"Ready for retraining: {batch_outcome_analysis.get('readyForRetraining')}",
            f"Next recommended next lever: {batch_outcome_analysis.get('nextRecommendedNextLever')}",
            "",
            "Brainstormed fixes:",
            fix_lines,
            "",
            "Roadmap rule: the roadmap only advances when this generated batch outcome artifact says the batch goal was achieved.",
            "",
        ]
    )


def run_touchline_review_densification_batch(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
) -> dict[str, object]:
    storage_root = Path(storage_root)
    storage = Storage(storage_root)
    paths = _paths(storage_root)
    active_lane_snapshot = _load_json(paths["activeLaneSnapshotPath"])
    failure_audit = _load_json(paths["failureAuditPath"])
    detector_breadth_matrix = _load_json(paths["detectorBreadthMatrixPath"])
    phase1_manifest, _phase1_split_manifest, _phase1_seeded_issue_report = _load_phase1_payloads(paths)
    detector_candidate_evaluation_summary = _candidate_evaluation_summary(storage_root)

    failing_source_clip_id = str(phase1_manifest.get("failingSourceClipId") or active_lane_snapshot.get("failingSourceClipId"))
    comparison_source_clip_id = str(
        phase1_manifest.get("comparisonSourceClipId") or active_lane_snapshot.get("comparisonSourceClipId")
    )
    representative_failing_match_id = str(phase1_manifest.get("representativeFailingMatchId") or "")
    representative_control_match_id = str(phase1_manifest.get("representativeControlMatchId") or "")
    if not representative_failing_match_id or not representative_control_match_id:
        raise ValueError("Phase 1A manifest is missing representative match ids")

    existing_failing_units = _sorted_phase1_units(
        curation_manifest=phase1_manifest,
        source_clip_id=failing_source_clip_id,
        match_id=representative_failing_match_id,
    )
    existing_control_units = _sorted_phase1_units(
        curation_manifest=phase1_manifest,
        source_clip_id=comparison_source_clip_id,
        match_id=representative_control_match_id,
    )
    if not existing_failing_units:
        raise ValueError("Phase 1A manifest is missing the representative failing unit")
    if not existing_control_units:
        raise ValueError("Phase 1A manifest is missing the representative control unit")

    baseline_config_name = str(
        active_lane_snapshot.get("sourceRobustnessActiveConfigName") or "source_robustness_baseline_current"
    )
    truth_gate_lookup = _truth_gate_reason_lookup(failure_audit, config_name=baseline_config_name)

    failing_frames = [frame.model_dump() for frame in storage.load_frames(representative_failing_match_id)]
    _summary, failing_assignments, _formation, _shots = storage.load_analytics(representative_failing_match_id)
    additional_failing_crops, shortage = _select_additional_failing_crops(
        existing_units=existing_failing_units,
        trust_crops=compute_trust_crops(
            failing_frames,
            [assignment.model_dump() for assignment in failing_assignments],
            max_crops=DEFAULT_MAX_TRUST_CROP_CANDIDATES,
        ),
    )

    selected_windows = [
        {
            "matchId": representative_failing_match_id,
            "sourceClipId": failing_source_clip_id,
            "split": "train",
            "frameStart": _safe_int(unit.get("frameStart")),
            "frameEnd": _safe_int(unit.get("frameEnd")),
            "timestampStart": _safe_float(unit.get("timestampStart")),
            "timestampEnd": _safe_float(unit.get("timestampEnd")),
            "trustCropScore": _safe_float(unit.get("trustCropScore")),
            "trustCropReasons": list(unit.get("trustCropReasons", [])),
        }
        for unit in existing_failing_units
    ]
    selected_windows.extend(
        {
            "matchId": representative_failing_match_id,
            "sourceClipId": failing_source_clip_id,
            "split": "train",
            "frameStart": crop.frameStart,
            "frameEnd": crop.frameEnd,
            "timestampStart": crop.timestampStart,
            "timestampEnd": crop.timestampEnd,
            "trustCropScore": crop.score,
            "trustCropReasons": list(crop.reasons),
        }
        for crop in additional_failing_crops
    )
    selected_windows.extend(
        {
            "matchId": representative_control_match_id,
            "sourceClipId": comparison_source_clip_id,
            "split": str(unit.get("split") or "val"),
            "frameStart": _safe_int(unit.get("frameStart")),
            "frameEnd": _safe_int(unit.get("frameEnd")),
            "timestampStart": _safe_float(unit.get("timestampStart")),
            "timestampEnd": _safe_float(unit.get("timestampEnd")),
            "trustCropScore": _safe_float(unit.get("trustCropScore")),
            "trustCropReasons": list(unit.get("trustCropReasons", [])),
        }
        for unit in existing_control_units[:1]
    )

    existing_overlay_lookup = _load_existing_overlay(paths["reviewedLabelOverlayPath"])
    curation_units: list[dict[str, object]] = []
    review_items: list[dict[str, object]] = []
    for window in selected_windows:
        match_id = str(window["matchId"])
        source_clip_id = str(window["sourceClipId"])
        video_path = _resolve_video_path(storage, match_id, source_clip_id)
        frames = [frame.model_dump() for frame in storage.load_frames(match_id)]
        ball_truth_layers = storage.load_analysis_artifact(match_id, "ball_truth_layers")
        proof_summary = _load_optional_analysis_artifact(storage, match_id, "proof_summary")
        accepted_rows = list((ball_truth_layers.get("acceptedBall") or {}).get("rows") or [])
        probe_observed_ball = ball_truth_layers.get("probeObservedBall") or {}
        probe_filtered_rows = list(probe_observed_ball.get("filteredRows") or [])
        probe_raw_rows = list(probe_observed_ball.get("rawRows") or [])
        unit = _unit_from_window(
            match_id=match_id,
            source_clip_id=source_clip_id,
            split_name=str(window["split"]),
            frame_start=_safe_int(window["frameStart"]),
            frame_end=_safe_int(window["frameEnd"]),
            timestamp_start=_safe_float(window["timestampStart"]),
            timestamp_end=_safe_float(window["timestampEnd"]),
            trust_crop_score=_safe_float(window["trustCropScore"]),
            trust_crop_reasons=list(window["trustCropReasons"]),
            truth_gate_reasons=truth_gate_lookup.get(match_id, []),
            detector_config_provenance={
                "baselineConfigName": baseline_config_name,
                "sourceRobustnessRecommendedNextLever": active_lane_snapshot.get(
                    "sourceRobustnessRecommendedNextLever"
                ),
                "detectorModelPath": proof_summary.get("detectorModelPath"),
                "screenWinningDetectorModelPath": detector_breadth_matrix.get("screenWinningDetectorModelPath"),
                "detectorCandidateEvaluationNextLever": detector_candidate_evaluation_summary.get(
                    "nextRecommendedNextLever"
                ),
            },
            artifact_lineage_paths={
                "activeLaneSnapshotPath": str(paths["activeLaneSnapshotPath"]),
                "suiteSummaryPath": str(paths["suiteSummaryPath"]),
                "suiteRobustnessDiagnosisPath": str(paths["suiteRobustnessDiagnosisPath"]),
                "failureAuditPath": str(paths["failureAuditPath"]),
                "sliceProjectionPath": str(paths["sliceProjectionPath"]),
                "detectorBreadthMatrixPath": str(paths["detectorBreadthMatrixPath"]),
                "phase1ManifestPath": str(paths["phase1ManifestPath"]),
                "candidateEvaluationSummaryPath": str(paths["candidateEvaluationSummaryPath"]),
                "ballTruthLayersPath": str(storage._match_dir(match_id) / "ball_truth_layers.json"),
                "proofSummaryPath": str(storage._match_dir(match_id) / "proof_summary.json"),
            },
            frames=frames,
            video_path=video_path,
            accepted_by_frame=_group_rows_by_frame([dict(row) for row in accepted_rows if isinstance(row, dict)]),
            probe_filtered_by_frame=_group_rows_by_frame(
                [dict(row) for row in probe_filtered_rows if isinstance(row, dict)]
            ),
            probe_raw_by_frame=_group_rows_by_frame([dict(row) for row in probe_raw_rows if isinstance(row, dict)]),
        )
        curation_units.append(unit)
        review_items.extend(
            _overlay_item_from_example(
                curation_unit=unit,
                example=example,
                existing_overlay_lookup=existing_overlay_lookup,
            )
            for example in unit["examples"]
        )

    curation_units.sort(
        key=lambda unit: (
            0 if str(unit["sourceClipId"]) == failing_source_clip_id else 1,
            _safe_int(unit.get("frameStart"), 0),
            _safe_int(unit.get("frameEnd"), 0),
        )
    )
    review_items.sort(
        key=lambda item: (
            0 if str(item["sourceClipId"]) == failing_source_clip_id else 1,
            *_review_priority_key(item),
        )
    )
    counts = _overlay_counts(review_items)
    source_review_counts = _count_pending_by_source(
        review_items=review_items,
        failing_source_clip_id=failing_source_clip_id,
        comparison_source_clip_id=comparison_source_clip_id,
    )
    failing_review_items = [
        item for item in review_items if str(item["sourceClipId"]) == failing_source_clip_id
    ]
    lineage_complete = all(
        isinstance(unit.get("artifactLineagePaths"), dict) and unit["artifactLineagePaths"] for unit in curation_units
    )
    overlay_validation_errors = _validate_review_items(review_items)
    preliminary_blocker = _review_primary_blocker(
        failing_review_items=failing_review_items,
        split_leakage_detected=False,
        lineage_complete=lineage_complete,
        overlay_validation_errors=overlay_validation_errors,
    )

    export_summary = _write_yolo_export(
        export_root=paths["exportRoot"],
        curation_units=curation_units,
        review_items=review_items,
    )
    split_manifest = _build_split_manifest(
        curation_units=curation_units,
        positive_seed_example_count=_safe_int(export_summary["positiveSeedExampleCount"]),
        negative_seed_example_count=_safe_int(export_summary["negativeSeedExampleCount"]),
        ready_for_retraining=preliminary_blocker is None and bool(export_summary["yoloExportRegenerated"]),
        primary_blocker=preliminary_blocker,
    )
    final_blocker = _review_primary_blocker(
        failing_review_items=failing_review_items,
        split_leakage_detected=bool(split_manifest.get("sourceAwareSplitLeakageDetected")),
        lineage_complete=lineage_complete,
        overlay_validation_errors=overlay_validation_errors,
    )
    ready_for_retraining = final_blocker is None and bool(export_summary["yoloExportRegenerated"])
    next_lever = NEXT_LEVER_RETRAIN if ready_for_retraining else NEXT_LEVER_PHASE1B
    split_manifest["readyForRetraining"] = ready_for_retraining
    split_manifest["reviewDensificationPrimaryBlocker"] = final_blocker

    review_bundle_report = _seed_backlog_and_bundles(storage, curation_units=curation_units)

    overlay_payload = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        **counts,
        **source_review_counts,
        "reviewItems": review_items,
    }
    manifest_payload = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "reviewDensificationBatchName": DEFAULT_BATCH_NAME,
        "failingSourceClipId": failing_source_clip_id,
        "comparisonSourceClipId": comparison_source_clip_id,
        "representativeFailingMatchId": representative_failing_match_id,
        "representativeControlMatchId": representative_control_match_id,
        "curationUnitCount": len(curation_units),
        "failingCurationUnitCount": sum(
            str(unit["sourceClipId"]) == failing_source_clip_id for unit in curation_units
        ),
        "controlCurationUnitCount": sum(
            str(unit["sourceClipId"]) == comparison_source_clip_id for unit in curation_units
        ),
        "requestedAdditionalFailingWindowCount": DEFAULT_MAX_ADDITIONAL_FAILING_WINDOWS,
        "selectedAdditionalFailingWindowCount": len(additional_failing_crops),
        "additionalFailingWindowShortageCount": shortage,
        "positiveSeedExampleCount": _safe_int(export_summary["positiveSeedExampleCount"]),
        "negativeSeedExampleCount": _safe_int(export_summary["negativeSeedExampleCount"]),
        "reviewItemCount": counts["reviewItemCount"],
        "pendingReviewCount": counts["pendingReviewCount"],
        "pendingFailingReviewCount": source_review_counts["pendingFailingReviewCount"],
        "pendingControlReviewCount": source_review_counts["pendingControlReviewCount"],
        "failingSourceReviewComplete": source_review_counts["failingSourceReviewComplete"],
        "controlReviewComplete": source_review_counts["controlReviewComplete"],
        "reviewedPositiveCount": counts["reviewedPositiveCount"],
        "reviewedNegativeCount": counts["reviewedNegativeCount"],
        "overlayValidationErrorCount": len(overlay_validation_errors),
        "overlayValidationErrors": overlay_validation_errors,
        "yoloExportRegenerated": bool(export_summary["yoloExportRegenerated"]),
        "readyForRetraining": ready_for_retraining,
        "reviewDensificationPrimaryBlocker": final_blocker,
        "nextRecommendedNextLever": next_lever,
        "curationUnits": curation_units,
    }
    batch_outcome_analysis = _build_batch_outcome_analysis(
        pending_failing_review_count=_safe_int(source_review_counts["pendingFailingReviewCount"]),
        pending_control_review_count=_safe_int(source_review_counts["pendingControlReviewCount"]),
        ready_for_retraining=ready_for_retraining,
        next_lever=next_lever,
        primary_blocker=final_blocker,
        validation_errors=overlay_validation_errors,
    )

    paths["artifactRoot"].mkdir(parents=True, exist_ok=True)
    paths["reviewDensificationManifestPath"].write_text(
        json.dumps(manifest_payload, indent=2),
        encoding="utf-8",
    )
    paths["reviewedLabelOverlayPath"].write_text(
        json.dumps(overlay_payload, indent=2),
        encoding="utf-8",
    )
    paths["reviewBundleReportPath"].write_text(
        json.dumps(review_bundle_report, indent=2),
        encoding="utf-8",
    )
    paths["splitManifestPath"].write_text(
        json.dumps(split_manifest, indent=2),
        encoding="utf-8",
    )
    paths["batchOutcomeAnalysisPath"].write_text(
        json.dumps(batch_outcome_analysis, indent=2),
        encoding="utf-8",
    )
    paths["batchOutcomeAnalysisMarkdownPath"].write_text(
        _batch_outcome_markdown(batch_outcome_analysis),
        encoding="utf-8",
    )

    return {
        "reviewDensificationBatchName": DEFAULT_BATCH_NAME,
        "artifactRoot": str(paths["artifactRoot"]),
        "representativeFailingMatchId": representative_failing_match_id,
        "representativeControlMatchId": representative_control_match_id,
        "failingCurationUnitCount": manifest_payload["failingCurationUnitCount"],
        "controlCurationUnitCount": manifest_payload["controlCurationUnitCount"],
        "reviewItemCount": counts["reviewItemCount"],
        "pendingReviewCount": counts["pendingReviewCount"],
        "pendingFailingReviewCount": source_review_counts["pendingFailingReviewCount"],
        "pendingControlReviewCount": source_review_counts["pendingControlReviewCount"],
        "failingSourceReviewComplete": source_review_counts["failingSourceReviewComplete"],
        "controlReviewComplete": source_review_counts["controlReviewComplete"],
        "reviewedPositiveCount": counts["reviewedPositiveCount"],
        "reviewedNegativeCount": counts["reviewedNegativeCount"],
        "readyForRetraining": ready_for_retraining,
        "reviewDensificationPrimaryBlocker": final_blocker,
        "nextRecommendedNextLever": next_lever,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Phase 1B touchline review densification artifacts.")
    parser.add_argument(
        "--storage-root",
        type=Path,
        default=DEFAULT_STORAGE_ROOT,
        help="Storage root containing suite and training artifacts.",
    )
    args = parser.parse_args()
    payload = run_touchline_review_densification_batch(storage_root=args.storage_root)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
