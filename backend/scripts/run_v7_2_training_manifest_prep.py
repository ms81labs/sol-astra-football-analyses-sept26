from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.run_v7_1_crop_manifest_consistency_refresh import (  # noqa: E402
    _apply_group_split_policy,
    _build_positive_crops,
    _split_leakage_audit,
)

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
OUTPUT_DIR_NAME = "v7_2_training_manifest_prep_v1"
NEXT_EXPORT_AUDIT = "v7_2_export_label_overlay_audit"
NEXT_POSITIVE_MINING = "v7_1_positive_candidate_mining_expansion_v3_pitch_filtered"
NEXT_NEGATIVE_FIX = "v7_negative_crop_conversion_plan"


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _load_json(path: Path, *, required: bool = False) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _safe_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _bbox(value: object) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    try:
        x1 = float(value["x1"])
        y1 = float(value["y1"])
        x2 = float(value["x2"])
        y2 = float(value["y2"])
    except (KeyError, TypeError, ValueError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


def _source_key(row: dict[str, Any]) -> tuple[str, int]:
    return str(row.get("sourceClipId") or "trimed-5min.mp4"), _safe_int(row.get("frameIndex"), -1)


def _normal_positive(row: dict[str, Any], *, source_name: str) -> dict[str, Any] | None:
    bbox = _bbox(row.get("sourceFrameBbox") or row.get("bbox"))
    frame = _safe_int(row.get("frameIndex"), -1)
    if bbox is None or frame < 0:
        return None
    source_clip_id = str(row.get("sourceClipId") or "trimed-5min.mp4")
    return {
        "exampleId": str(row.get("candidateId") or row.get("sourcePositiveExampleId") or row.get("exampleId") or f"{source_name}-{source_clip_id}-{frame}"),
        "sourceClipId": source_clip_id,
        "frameIndex": frame,
        "bbox": bbox,
        "sourceFrameBbox": bbox,
        "truthUse": "reviewed_positive_training_seed",
        "sourceTruthBatch": source_name,
        "splitGroupId": row.get("splitGroupId") or f"{source_clip_id}-cluster-{frame // 60:04d}",
        "visibilityClass": row.get("visibilityClass") or "clear",
        "contextTags": row.get("contextTags") if isinstance(row.get("contextTags"), list) else ["small_ball"],
    }


def _positive_rows_from_crop_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    by_source: dict[tuple[str, int], dict[str, Any]] = {}
    for row in manifest.get("positiveCropExamples") or []:
        if not isinstance(row, dict):
            continue
        normalized = _normal_positive(row, source_name="v7_1_crop_manifest_consistency_refresh")
        if normalized:
            by_source.setdefault(_source_key(normalized), normalized)
    return list(by_source.values())


def _positive_rows_from_review_file(path: Path, *, source_name: str) -> list[dict[str, Any]]:
    payload = _load_json(path)
    rows = payload.get("rows") or payload.get("reviewItems") or []
    positives = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("reviewStatus") and row.get("reviewStatus") != "reviewed_positive_ball":
            continue
        normalized = _normal_positive(row, source_name=source_name)
        if normalized:
            positives.append(normalized)
    return positives


def _collect_positive_sources(candidate_root: Path) -> list[dict[str, Any]]:
    local_manifest = _load_json(candidate_root / "v7_1_crop_manifest_consistency_refresh_v1" / "v7_1_local_crop_training_manifest.json")
    sources = _positive_rows_from_crop_manifest(local_manifest)
    sources.extend(
        _positive_rows_from_review_file(
            candidate_root / "v7_1_positive_diversity_manual_review_resolution_v1" / "reviewed_positive_truth_additions.json",
            source_name="v7_1_positive_diversity_manual_review_resolution_v1",
        )
    )
    sources.extend(
        _positive_rows_from_review_file(
            candidate_root / "v7_1_positive_candidate_mining_expansion_v1" / "corrected_label_overlay.json",
            source_name="v7_1_positive_candidate_mining_expansion_v1",
        )
    )
    sources.extend(
        _positive_rows_from_review_file(
            candidate_root / "v7_1_positive_diversity_manual_review_resolution_v2" / "reviewed_positive_truth_additions.json",
            source_name="v7_1_positive_diversity_manual_review_resolution_v2",
        )
    )
    by_key: dict[tuple[str, int], dict[str, Any]] = {}
    for row in sources:
        by_key[_source_key(row)] = row
    return [by_key[key] for key in sorted(by_key, key=lambda item: (item[0], item[1]))]


def _safe_crop_window(value: object) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        x1, y1, x2, y2 = [float(part) for part in value]
    except (TypeError, ValueError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return [round(x1, 3), round(y1, 3), round(x2, 3), round(y2, 3)]


def _normal_negative(row: dict[str, Any], *, heldout: bool = False) -> dict[str, Any] | None:
    window = _safe_crop_window(row.get("cropWindow") or row.get("sourceFalsePositiveBbox") or row.get("cropBbox"))
    has_explicit_local_crop_flag = row.get("sourceFullFrameNegativeExported") is False
    is_local_empty_label_crop = (
        row.get("truthUse") == "local_hard_negative_crop_only"
        and row.get("exportUse") == "yolo_empty_label_crop"
        and row.get("ballFreeStatus") == "deterministic_artifact_region_ball_free"
    )
    if window is None or row.get("sourceFullFrameNegativeExported") is True or not (has_explicit_local_crop_flag or is_local_empty_label_crop):
        return None
    return {
        **row,
        "exampleId": row.get("exampleId") or f"v7-2-hard-negative-{row.get('frameIndex')}",
        "label": "no_ball",
        "truthUse": "local_hard_negative_crop_only",
        "exportUse": "yolo_empty_label_crop",
        "cropWindow": window,
        "sourceFullFrameNegativeExported": False,
        "split": "heldout" if heldout else row.get("split", "train"),
    }


def _collect_negative_sets(candidate_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    local_manifest = _load_json(candidate_root / "v7_1_crop_manifest_consistency_refresh_v1" / "v7_1_local_crop_training_manifest.json")
    negatives = []
    heldout = []
    unsafe = 0
    for row in local_manifest.get("negativeCropExamples") or []:
        if not isinstance(row, dict):
            continue
        normalized = _normal_negative(row)
        if normalized is None:
            unsafe += 1
        else:
            negatives.append(normalized)
    for row in local_manifest.get("heldoutHardNegativeCanary") or []:
        if not isinstance(row, dict):
            continue
        normalized = _normal_negative(row, heldout=True)
        if normalized is None:
            unsafe += 1
        else:
            heldout.append(normalized)
    return negatives, heldout, unsafe


def _quality_gate(
    *,
    positive_sources: list[dict[str, Any]],
    positive_crops: list[dict[str, Any]],
    negatives: list[dict[str, Any]],
    heldout: list[dict[str, Any]],
    unsafe_negative_count: int,
    split_leakage_count: int,
) -> dict[str, Any]:
    weak = []
    if len(positive_sources) < 120:
        weak.append("reviewed_positive_source_count_below_minimum")
    if len(positive_crops) < 360:
        weak.append("positive_crop_example_count_below_minimum")
    if len(negatives) < 100:
        weak.append("local_hard_negative_count_below_minimum")
    if len(heldout) < 20:
        weak.append("heldout_canary_count_below_minimum")
    if unsafe_negative_count:
        weak.append("unsafe_negative_leak")
    if split_leakage_count:
        weak.append("split_leakage")
    return {
        "generatedAt": _utc_now_iso(),
        "trainingPrepReady": not weak,
        "reviewedPositiveSourceCount": len(positive_sources),
        "positiveCropExampleCount": len(positive_crops),
        "localHardNegativeCropCount": len(negatives),
        "heldoutHardNegativeCanaryCount": len(heldout),
        "unsafeFullFrameNegativeExportCount": unsafe_negative_count,
        "splitLeakageCount": split_leakage_count,
        "weakEvidenceReasons": weak,
    }


def _classify(quality: dict[str, Any]) -> tuple[str | None, str, bool]:
    weak = set(quality.get("weakEvidenceReasons") or [])
    if not weak:
        return None, NEXT_EXPORT_AUDIT, True
    if "unsafe_negative_leak" in weak:
        return "v7_2_manifest_unsafe_negative_leak", NEXT_NEGATIVE_FIX, False
    if "reviewed_positive_source_count_below_minimum" in weak or "positive_crop_example_count_below_minimum" in weak:
        return "v7_2_manifest_positive_diversity_gap", NEXT_POSITIVE_MINING, False
    return "v7_2_manifest_artifact_gap", "manual_review_required", False


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V7.2 Training Manifest Prep",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Reviewed positives: `{summary.get('reviewedPositiveSourceCount')}`",
            f"- Positive crop examples: `{summary.get('positiveCropExampleCount')}`",
            f"- Local hard negatives: `{summary.get('localHardNegativeCropCount')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
        ]
    )


def run_v7_2_training_manifest_prep(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    candidate_root = _candidate_root(Path(storage_root), candidate_name)
    output_root = candidate_root / output_dir_name
    positive_sources = _collect_positive_sources(candidate_root)
    positive_crops, positive_audit = _build_positive_crops(positive_sources, crop_sizes=(192, 256, 384))
    negatives, heldout, unsafe_negative_count = _collect_negative_sets(candidate_root)
    _apply_group_split_policy([*positive_crops, *negatives])
    split_audit = _split_leakage_audit(positive_crops, negatives, repair_applied=True)
    quality = _quality_gate(
        positive_sources=positive_sources,
        positive_crops=positive_crops,
        negatives=negatives,
        heldout=heldout,
        unsafe_negative_count=unsafe_negative_count,
        split_leakage_count=split_audit["splitLeakageCount"],
    )
    primary_blocker, next_lever, ready = _classify(quality)
    manifest = {
        "batchName": "v7_2_training_manifest_prep",
        "generatedAt": _utc_now_iso(),
        "trainingCandidateName": "touchline_detector_candidate_v7_2",
        "positiveTruthPolicy": "reviewed_positive_only",
        "negativeTruthPolicy": "local_crop_negative_only_ball_free",
        "unsafeNegativePolicy": "preserved_as_evidence_excluded_from_training_export",
        "reviewedPositiveSourceCount": len(positive_sources),
        "positiveCropExampleCount": len(positive_crops),
        "localHardNegativeCropCount": len(negatives),
        "heldoutHardNegativeCanaryCount": len(heldout),
        "fullFrameEmptyLabelNegativeExportCount": 0,
        "refutedSeedsReusedAsPositiveEvidence": False,
        "runtimeDefaultMutationAllowed": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "manifestReadyForExportAudit": ready,
        "positiveSourceExamples": positive_sources,
        "positiveCropExamples": positive_crops,
        "negativeCropExamples": negatives,
        "heldoutHardNegativeCanary": heldout,
    }
    summary = {
        "batchName": "v7_2_training_manifest_prep",
        "generatedAt": _utc_now_iso(),
        "goalAchieved": ready,
        "roadmapAdvanceAllowed": ready,
        "primaryBlocker": primary_blocker,
        "nextRecommendedNextLever": next_lever,
        "trainingPrepReady": ready,
        "trainingExecuted": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationAllowed": False,
        "reviewedPositiveSourceCount": len(positive_sources),
        "positiveCropExampleCount": len(positive_crops),
        "localHardNegativeCropCount": len(negatives),
        "heldoutHardNegativeCanaryCount": len(heldout),
        "unsafeFullFrameNegativeExportCount": unsafe_negative_count,
        "splitLeakageCount": split_audit["splitLeakageCount"],
        "weakEvidenceReasons": quality["weakEvidenceReasons"],
        "englishDecision": "v7.2 manifest is ready for export/overlay audit; do not train or promote yet." if ready else "v7.2 manifest prep is blocked; do not train.",
    }
    decision_matrix = {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "training_prep_ready", "observed": ready, "selected": ready, "nextFamily": NEXT_EXPORT_AUDIT},
            {"condition": "unsafe_negative_leak", "observed": unsafe_negative_count > 0, "selected": primary_blocker == "v7_2_manifest_unsafe_negative_leak", "nextFamily": NEXT_NEGATIVE_FIX},
        ],
    }
    _write_json(output_root / "v7_2_training_manifest_prep_summary.json", summary)
    _write_json(output_root / "v7_2_training_manifest.json", manifest)
    _write_json(output_root / "v7_2_manifest_quality_gate.json", quality)
    _write_json(output_root / "v7_2_positive_crop_transform_audit.json", positive_audit)
    _write_json(output_root / "v7_2_split_leakage_audit.json", split_audit)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "batch_outcome_analysis.json", {"summary": summary, "qualityGate": quality})
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build v7.2 reviewed-positive local-crop training manifest prep artifacts.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    args = parser.parse_args()
    payload = run_v7_2_training_manifest_prep(storage_root=args.storage_root, candidate_name=args.candidate_name)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
