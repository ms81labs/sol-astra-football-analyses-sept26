from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_INPUT_BATCH_NAME = "v7_negative_semantics_review_v1"
DEFAULT_OUTPUT_DIR_NAME = "v7_negative_crop_conversion_plan_v1"
DEFAULT_SUITE_NAME = "frozen-viable-baseline-slice-suite"
DEFAULT_TRAINING_PREP_BATCH_NAME = "touchline_detector_candidate_v7_training_prep_v1"

BLOCKER_READY = "v7_negative_crop_conversion_ready"
BLOCKER_NO_SAFE_CROPS = "v7_negative_crop_conversion_no_safe_crops"
BLOCKER_ARTIFACT_GAP = "v7_negative_crop_conversion_artifact_gap"

NEXT_MANIFEST_PREP = "v7_1_training_manifest_prep"
NEXT_VISIBLE_BALL_REVIEW = "v7_negative_visible_ball_review"
NEXT_MANUAL_REVIEW = "manual_review_required"


def _load_json(path: Path, *, required: bool = True) -> dict[str, object]:
    if not path.exists():
        if required:
            raise FileNotFoundError(str(path))
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _training_manifest_path(storage_root: Path) -> Path:
    return (
        Path(storage_root)
        / "benchmark_suites"
        / DEFAULT_SUITE_NAME
        / DEFAULT_TRAINING_PREP_BATCH_NAME
        / "v7_training_manifest.json"
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


def _normalize_crop_window(value: object) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    window = [_safe_float(part) for part in value]
    if window[2] <= window[0] or window[3] <= window[1]:
        return None
    return [round(part, 3) for part in window]


def _build_crop_manifest(hard_negative_manifest: dict[str, object]) -> dict[str, object]:
    crops = []
    seen: set[tuple[int, tuple[float, float, float, float]]] = set()
    for index, row in enumerate(hard_negative_manifest.get("candidates") or []):
        if not isinstance(row, dict):
            continue
        window = _normalize_crop_window(row.get("cropWindow"))
        frame_index = _safe_int(row.get("frameIndex"), -1)
        if window is None or frame_index < 0:
            continue
        key = (frame_index, tuple(window))
        if key in seen:
            continue
        seen.add(key)
        crops.append(
            {
                "exampleId": f"v7-1-hard-negative-top-left-{frame_index}-{index}",
                "sourceHardNegativeId": row.get("hardNegativeId") or f"top-left-artifact-{index:04d}",
                "frameIndex": frame_index,
                "sourceClipId": row.get("sourceClipId") or "trimed-5min.mp4",
                "cropWindow": window,
                "truthUse": "local_hard_negative_top_left_artifact",
                "labelPolicy": "empty_label_crop_only",
                "sourceFullFrameNegativeExported": False,
                "visibleBallAbsencePolicy": "crop_region_assumed_from_artifact_source_pending_final_manifest_gate",
                "lineage": {
                    "sourceBatch": DEFAULT_INPUT_BATCH_NAME,
                    "sourceTruthUse": row.get("truthUse"),
                },
            }
        )
    return {
        "generatedAt": _utc_now_iso(),
        "cropCount": len(crops),
        "sourceCandidateCount": _safe_int(hard_negative_manifest.get("sourceCandidateCount"), len(crops)),
        "policy": "local_crop_hard_negatives_only_no_full_frame_empty_labels",
        "crops": crops,
    }


def _excluded_full_frame_negatives(review_manifest: dict[str, object]) -> list[dict[str, object]]:
    excluded = []
    for row in review_manifest.get("reviewItems") or []:
        if not isinstance(row, dict):
            continue
        excluded.append(
            {
                "exampleId": row.get("exampleId"),
                "frameIndex": row.get("frameIndex"),
                "sourceClipId": row.get("sourceClipId"),
                "reason": "unsafe_full_frame_empty_label_negative_excluded_until_reviewed",
            }
        )
    return excluded


def _classify(*, has_required_artifacts: bool, crop_count: int) -> tuple[str, str, list[str]]:
    if not has_required_artifacts:
        return (
            BLOCKER_ARTIFACT_GAP,
            NEXT_MANUAL_REVIEW,
            ["Required negative-semantics review artifacts are missing."],
        )
    if crop_count <= 0:
        return (
            BLOCKER_NO_SAFE_CROPS,
            NEXT_VISIBLE_BALL_REVIEW,
            ["No safe local hard-negative crop candidates were available."],
        )
    return (
        BLOCKER_READY,
        NEXT_MANIFEST_PREP,
        ["Unsafe full-frame negatives can be excluded and local artifact crops can seed v7.1 manifest prep."],
    )


def _markdown_summary(summary: dict[str, object]) -> str:
    return "\n".join(
        [
            "# V7 Negative Crop Conversion Plan",
            "",
            f"- Dominant blocker: `{summary.get('dominantBlockerClass')}`",
            f"- Unsafe full-frame negatives excluded: `{summary.get('unsafeFullFrameNegativeExcludedCount')}`",
            f"- Local hard-negative crops: `{summary.get('localHardNegativeCropCount')}`",
            f"- Next corrective family: `{summary.get('nextCorrectiveFamily')}`",
            "",
            str(summary.get("englishSummary") or ""),
            "",
        ]
    )


def run_v7_negative_crop_conversion_plan(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, object]:
    storage_root = Path(storage_root)
    candidate_root = _candidate_root(storage_root, candidate_name)
    input_root = candidate_root / DEFAULT_INPUT_BATCH_NAME
    output_root = candidate_root / output_dir_name
    training_manifest = _load_json(_training_manifest_path(storage_root), required=False)
    review_summary = _load_json(input_root / "v7_negative_semantics_review_summary.json", required=False)
    review_manifest = _load_json(input_root / "full_frame_negative_review_manifest.json", required=False)
    hard_negative_manifest = _load_json(input_root / "top_left_artifact_hard_negative_manifest.json", required=False)

    crop_manifest = _build_crop_manifest(hard_negative_manifest)
    excluded = _excluded_full_frame_negatives(review_manifest)
    positive_examples = [row for row in training_manifest.get("positiveExamples") or [] if isinstance(row, dict)]
    original_negative_examples = [row for row in training_manifest.get("negativeExamples") or [] if isinstance(row, dict)]
    has_required_artifacts = bool(training_manifest and review_manifest and hard_negative_manifest)
    blocker, next_family, weak_reasons = _classify(
        has_required_artifacts=has_required_artifacts,
        crop_count=int(crop_manifest.get("cropCount") or 0),
    )

    manifest_delta = {
        "generatedAt": _utc_now_iso(),
        "deltaType": "proposed_only",
        "positiveExamplesPreserved": len(positive_examples),
        "originalNegativeExamples": len(original_negative_examples),
        "unsafeFullFrameNegativesExcluded": len(excluded),
        "localHardNegativeCropsAdded": int(crop_manifest.get("cropCount") or 0),
        "containsUnsafeFullFrameEmptyNegatives": False,
        "refutedSeedsReusedAsPositiveEvidence": False,
        "groupedSplitRequired": True,
        "readyForV7_1ManifestPrep": blocker == BLOCKER_READY,
    }
    summary = {
        "batchName": "v7_negative_crop_conversion_plan",
        "attemptNumber": 1,
        "attemptApproachFamily": "top_left_artifact_crop_manifest",
        "generatedAt": _utc_now_iso(),
        "trainingCandidateName": candidate_name,
        "dominantBlockerClass": blocker,
        "nextCorrectiveFamily": next_family,
        "goalAchieved": has_required_artifacts and blocker != BLOCKER_ARTIFACT_GAP,
        "roadmapAdvanceAllowed": blocker == BLOCKER_READY,
        "positiveExamplesPreserved": len(positive_examples),
        "originalNegativeExampleCount": len(original_negative_examples),
        "unsafeFullFrameNegativeExcludedCount": len(excluded),
        "localHardNegativeCropCount": int(crop_manifest.get("cropCount") or 0),
        "inputDominantBlockerClass": review_summary.get("dominantBlockerClass"),
        "runtimeDefaultMutationAllowed": False,
        "weakEvidenceReasons": weak_reasons,
        "englishSummary": (
            "The v7.1 data path can stop exporting unsafe full-frame empty-label negatives and instead "
            "use local top-left artifact crop negatives as proposed hard negatives. This is still data prep, "
            "not retraining or promotion."
            if blocker == BLOCKER_READY
            else "Negative crop conversion could not produce safe local crop candidates."
        ),
    }
    decision_matrix = {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {
                "condition": "local_hard_negative_crops_available",
                "observed": int(crop_manifest.get("cropCount") or 0),
                "selected": blocker == BLOCKER_READY,
                "nextFamily": NEXT_MANIFEST_PREP,
            },
            {
                "condition": "no_crop_candidates_available",
                "observed": int(crop_manifest.get("cropCount") or 0) == 0,
                "selected": blocker == BLOCKER_NO_SAFE_CROPS,
                "nextFamily": NEXT_VISIBLE_BALL_REVIEW,
            },
        ],
    }
    outcome = {
        "summary": summary,
        "manifestDelta": manifest_delta,
        "excludedFullFrameNegatives": excluded,
        "cropManifest": crop_manifest,
    }

    _write_json(output_root / "v7_negative_crop_conversion_summary.json", summary)
    _write_json(output_root / "local_hard_negative_crop_manifest.json", crop_manifest)
    _write_json(output_root / "excluded_full_frame_negative_manifest.json", {"generatedAt": _utc_now_iso(), "excluded": excluded})
    _write_json(output_root / "v7_1_training_manifest_delta.json", manifest_delta)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "batch_outcome_analysis.json", outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    args = parser.parse_args()
    payload = run_v7_negative_crop_conversion_plan(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
