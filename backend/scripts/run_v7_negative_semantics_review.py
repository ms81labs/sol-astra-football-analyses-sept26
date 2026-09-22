from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_INPUT_BATCH_NAME = "v7_training_data_quality_refresh_v1"
DEFAULT_OUTPUT_DIR_NAME = "v7_negative_semantics_review_v1"
DEFAULT_SUITE_NAME = "frozen-viable-baseline-slice-suite"
DEFAULT_TRAINING_PREP_BATCH_NAME = "touchline_detector_candidate_v7_training_prep_v1"

BLOCKER_VISIBLE_BALL_REVIEW_REQUIRED = "v7_full_frame_negative_visible_ball_review_required"
BLOCKER_CLEAR = "v7_negative_semantics_review_clear"
BLOCKER_ARTIFACT_GAP = "v7_negative_semantics_artifact_gap"

NEXT_CROP_CONVERSION = "v7_negative_crop_conversion_plan"
NEXT_MANIFEST_PREP = "v7_1_training_manifest_prep"
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


def _suite_root(storage_root: Path) -> Path:
    return Path(storage_root) / "benchmark_suites" / DEFAULT_SUITE_NAME


def _training_manifest_path(storage_root: Path) -> Path:
    return _suite_root(storage_root) / DEFAULT_TRAINING_PREP_BATCH_NAME / "v7_training_manifest.json"


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


def _negative_examples_by_id(training_manifest: dict[str, object]) -> dict[str, dict[str, object]]:
    examples: dict[str, dict[str, object]] = {}
    for row in training_manifest.get("negativeExamples") or []:
        if isinstance(row, dict) and row.get("exampleId") is not None:
            examples[str(row.get("exampleId"))] = row
    return examples


def _build_review_manifest(
    *,
    unsafe_rows: list[dict[str, object]],
    training_manifest: dict[str, object],
    data_quality_root: Path,
) -> dict[str, object]:
    negative_by_id = _negative_examples_by_id(training_manifest)
    review_items = []
    for unsafe in unsafe_rows:
        example_id = str(unsafe.get("exampleId") or "")
        source = negative_by_id.get(example_id, {})
        frame_index = _safe_int(unsafe.get("frameIndex", source.get("frameIndex")), -1)
        review_items.append(
            {
                "reviewItemId": f"v7-negative-semantics-{example_id or frame_index}",
                "exampleId": example_id,
                "frameIndex": frame_index,
                "sourceClipId": source.get("sourceClipId") or "trimed-5min.mp4",
                "candidateFrameId": source.get("candidateFrameId"),
                "originalReviewItemId": source.get("reviewItemId"),
                "originalDecision": source.get("reviewDecision"),
                "truthUse": source.get("truthUse"),
                "decision": "pending_review",
                "reviewTask": "confirm_no_visible_ball_in_full_frame",
                "allowedDecisions": [
                    "confirm_no_visible_ball",
                    "visible_ball_present_needs_positive_label",
                    "convert_to_local_hard_negative_crop",
                    "reject_from_training",
                ],
                "reason": unsafe.get("reason") or "empty_full_frame_negative_visible_ball_unknown",
                "notes": (
                    "This example was exported as a full-frame empty-label negative. "
                    "It is unsafe for YOLO training until a reviewer confirms no visible ball "
                    "exists anywhere in the frame, or it is converted into a local hard-negative crop."
                ),
                "lineage": {
                    "trainingManifestPath": str(_training_manifest_path(Path(DEFAULT_STORAGE_ROOT))),
                    "negativeSemanticsAuditPath": str(data_quality_root / "negative_semantics_audit.json"),
                    "sourceBatch": DEFAULT_INPUT_BATCH_NAME,
                },
            }
        )
    return {
        "generatedAt": _utc_now_iso(),
        "reviewItemCount": len(review_items),
        "pendingReviewCount": len(review_items),
        "reviewPolicy": "human_or_tool_review_required_before_full_frame_empty_negative_training",
        "reviewItems": review_items,
    }


def _normalize_crop_window(value: object) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    window = [_safe_float(part) for part in value]
    if window[2] <= window[0] or window[3] <= window[1]:
        return None
    return [round(part, 3) for part in window]


def _hard_negative_manifest(hard_negative_plan: dict[str, object]) -> dict[str, object]:
    candidates = []
    for index, row in enumerate(hard_negative_plan.get("sampledHardNegativeCandidates") or []):
        if not isinstance(row, dict):
            continue
        crop_window = _normalize_crop_window(row.get("cropWindow"))
        if crop_window is None:
            continue
        candidates.append(
            {
                "hardNegativeId": f"top-left-artifact-{index:04d}",
                "frameIndex": _safe_int(row.get("frameIndex"), -1),
                "sourceClipId": row.get("sourceClipId") or "trimed-5min.mp4",
                "cropWindow": crop_window,
                "truthUse": "local_hard_negative_top_left_artifact",
                "requiresVisibleBallAbsenceReview": True,
                "lineage": {
                    "sourceTruthUse": row.get("truthUse"),
                    "sourceBatch": "v7_training_data_quality_refresh_v1",
                },
            }
        )
    return {
        "generatedAt": _utc_now_iso(),
        "candidateCount": len(candidates),
        "sourceCandidateCount": _safe_int(hard_negative_plan.get("dedupedTopLeftArtifactCandidateCount"), len(candidates)),
        "hardNegativePolicy": (
            "Use as local crop negatives only after confirming the crop does not contain a true ball; "
            "do not export full frames as empty-label negatives from this source."
        ),
        "candidates": candidates,
    }


def _crop_conversion_plan(
    *,
    review_manifest: dict[str, object],
    hard_negative_manifest: dict[str, object],
    training_manifest: dict[str, object],
) -> dict[str, object]:
    positive_count = len([row for row in training_manifest.get("positiveExamples") or [] if isinstance(row, dict)])
    negative_count = len([row for row in training_manifest.get("negativeExamples") or [] if isinstance(row, dict)])
    return {
        "generatedAt": _utc_now_iso(),
        "conversionPolicy": "proposed_only_no_training_export_mutation",
        "positiveExamplesPreserved": positive_count,
        "originalNegativeExamples": negative_count,
        "fullFrameNegativesExcludedUntilReviewed": int(review_manifest.get("pendingReviewCount") or 0),
        "proposedTopLeftArtifactCropCount": int(hard_negative_manifest.get("candidateCount") or 0),
        "refutedSeedsRemainNegativeOnly": True,
        "allowedRepairs": [
            "review_full_frame_visible_ball_absence",
            "convert_refuted_seed_or_artifact_region_to_local_hard_negative_crop",
            "drop_unreviewed_full_frame_empty_label_negative",
        ],
        "blockedRepairs": [
            "reuse_refuted_seed_as_positive",
            "train_full_frame_empty_label_negative_with_unknown_visible_ball_status",
            "retrain_before_negative_semantics_gate_clears",
        ],
    }


def _manifest_delta(
    *,
    training_manifest: dict[str, object],
    review_manifest: dict[str, object],
    hard_negative_manifest: dict[str, object],
) -> dict[str, object]:
    positive_examples = [row for row in training_manifest.get("positiveExamples") or [] if isinstance(row, dict)]
    negative_examples = [row for row in training_manifest.get("negativeExamples") or [] if isinstance(row, dict)]
    return {
        "generatedAt": _utc_now_iso(),
        "deltaType": "proposed_only",
        "positiveExamplesPreserved": len(positive_examples),
        "originalNegativeExamples": len(negative_examples),
        "removeUnsafeFullFrameNegativesFromV7_1": int(review_manifest.get("pendingReviewCount") or 0),
        "addTopLeftArtifactHardNegativeCrops": int(hard_negative_manifest.get("candidateCount") or 0),
        "groupedSplitRequired": True,
        "negativeSemanticsGateRequired": True,
        "v7_1TrainingAllowed": int(review_manifest.get("pendingReviewCount") or 0) == 0,
        "refutedSeedsReusedAsPositiveEvidence": False,
    }


def _classify(
    *,
    unsafe_count: int,
    hard_negative_count: int,
    has_required_artifacts: bool,
) -> tuple[str, str, list[str]]:
    if not has_required_artifacts:
        return (
            BLOCKER_ARTIFACT_GAP,
            NEXT_MANUAL_REVIEW,
            ["Required v7 training manifest or data-quality audit artifacts are missing."],
        )
    if unsafe_count > 0:
        next_family = NEXT_CROP_CONVERSION if hard_negative_count > 0 else NEXT_MANUAL_REVIEW
        return (
            BLOCKER_VISIBLE_BALL_REVIEW_REQUIRED,
            next_family,
            ["Full-frame empty-label negatives require visible-ball review or local crop conversion."],
        )
    return (
        BLOCKER_CLEAR,
        NEXT_MANIFEST_PREP,
        ["Negative semantics gate is clear; v7.1 manifest prep can proceed."],
    )


def _markdown_summary(summary: dict[str, object]) -> str:
    return "\n".join(
        [
            "# V7 Negative Semantics Review",
            "",
            f"- Dominant blocker: `{summary.get('dominantBlockerClass')}`",
            f"- Unsafe full-frame negatives: `{summary.get('unsafeFullFrameNegativeCount')}`",
            f"- Pending visible-ball reviews: `{summary.get('pendingVisibleBallReviewCount')}`",
            f"- Top-left hard-negative candidates: `{summary.get('topLeftArtifactHardNegativeCandidateCount')}`",
            f"- Next corrective family: `{summary.get('nextCorrectiveFamily')}`",
            "",
            str(summary.get("englishSummary") or ""),
            "",
        ]
    )


def run_v7_negative_semantics_review(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, object]:
    storage_root = Path(storage_root)
    candidate_root = _candidate_root(storage_root, candidate_name)
    data_quality_root = candidate_root / DEFAULT_INPUT_BATCH_NAME
    training_manifest_path = _training_manifest_path(storage_root)
    training_manifest = _load_json(training_manifest_path, required=False)
    data_quality_summary = _load_json(data_quality_root / "v7_training_data_quality_summary.json", required=False)
    negative_audit = _load_json(data_quality_root / "negative_semantics_audit.json", required=False)
    hard_negative_plan = _load_json(data_quality_root / "hard_negative_mining_plan.json", required=False)

    unsafe_rows = [dict(row) for row in negative_audit.get("unsafeRows") or [] if isinstance(row, dict)]
    review_manifest = _build_review_manifest(
        unsafe_rows=unsafe_rows,
        training_manifest=training_manifest,
        data_quality_root=data_quality_root,
    )
    hard_negative_candidates = _hard_negative_manifest(hard_negative_plan)
    crop_plan = _crop_conversion_plan(
        review_manifest=review_manifest,
        hard_negative_manifest=hard_negative_candidates,
        training_manifest=training_manifest,
    )
    manifest_delta = _manifest_delta(
        training_manifest=training_manifest,
        review_manifest=review_manifest,
        hard_negative_manifest=hard_negative_candidates,
    )

    has_required_artifacts = bool(training_manifest and negative_audit)
    blocker, next_family, weak_reasons = _classify(
        unsafe_count=len(unsafe_rows),
        hard_negative_count=int(hard_negative_candidates.get("candidateCount") or 0),
        has_required_artifacts=has_required_artifacts,
    )
    summary = {
        "batchName": "v7_negative_semantics_review",
        "attemptNumber": 1,
        "attemptApproachFamily": "negative_visible_ball_review_package",
        "generatedAt": _utc_now_iso(),
        "trainingCandidateName": candidate_name,
        "dominantBlockerClass": blocker,
        "nextCorrectiveFamily": next_family,
        "goalAchieved": has_required_artifacts and blocker != BLOCKER_ARTIFACT_GAP,
        "roadmapAdvanceAllowed": blocker == BLOCKER_CLEAR,
        "positiveExampleCount": len([row for row in training_manifest.get("positiveExamples") or [] if isinstance(row, dict)]),
        "negativeExampleCount": len([row for row in training_manifest.get("negativeExamples") or [] if isinstance(row, dict)]),
        "unsafeFullFrameNegativeCount": len(unsafe_rows),
        "pendingVisibleBallReviewCount": int(review_manifest.get("pendingReviewCount") or 0),
        "topLeftArtifactHardNegativeCandidateCount": int(hard_negative_candidates.get("candidateCount") or 0),
        "sourceHardNegativeCandidateCount": _safe_int(
            hard_negative_candidates.get("sourceCandidateCount"),
            int(hard_negative_candidates.get("candidateCount") or 0),
        ),
        "inputDominantBlockerClass": data_quality_summary.get("dominantBlockerClass"),
        "runtimeDefaultMutationAllowed": False,
        "weakEvidenceReasons": weak_reasons,
        "englishSummary": (
            "The v7 positive labels are not the immediate export problem. The current blocker is that "
            "full-frame empty-label negatives have unknown visible-ball status. The safe next move is "
            "to review those full frames or convert available artifact regions into local hard-negative crops."
            if blocker == BLOCKER_VISIBLE_BALL_REVIEW_REQUIRED
            else "Negative semantics are clear enough to continue v7.1 manifest prep."
        ),
    }
    decision_matrix = {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {
                "condition": "unsafe_full_frame_empty_label_negatives_present",
                "observed": len(unsafe_rows),
                "selected": blocker == BLOCKER_VISIBLE_BALL_REVIEW_REQUIRED,
                "nextFamily": NEXT_CROP_CONVERSION,
            },
            {
                "condition": "negative_semantics_clear",
                "observed": len(unsafe_rows) == 0,
                "selected": blocker == BLOCKER_CLEAR,
                "nextFamily": NEXT_MANIFEST_PREP,
            },
        ],
    }
    outcome = {
        "summary": summary,
        "reviewManifest": review_manifest,
        "cropConversionPlan": crop_plan,
        "manifestDelta": manifest_delta,
    }

    output_root = candidate_root / output_dir_name
    _write_json(output_root / "v7_negative_semantics_review_summary.json", summary)
    _write_json(output_root / "full_frame_negative_review_manifest.json", review_manifest)
    _write_json(output_root / "negative_crop_conversion_plan.json", crop_plan)
    _write_json(output_root / "top_left_artifact_hard_negative_manifest.json", hard_negative_candidates)
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
    payload = run_v7_negative_semantics_review(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
