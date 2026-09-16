from __future__ import annotations

import argparse
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.run_v7_1_positive_candidate_mining_expansion import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_VIDEO_PATH,
    _attach_review_evidence,
    _candidate_root,
    _load_json,
    _load_v2_reviewed_positive_rows,
    _mine_new_group_candidates,
    _safe_bbox,
    _safe_int,
    _write_json,
)

OUTPUT_DIR_NAME = "v7_1_positive_candidate_mining_expansion_v3_pitch_filtered_v1"
V2_DIR_NAME = "v7_1_positive_candidate_mining_expansion_v2"
RESOLUTION_DIR_NAME = "v7_1_positive_diversity_manual_review_resolution_v2"
NEXT_REVIEW = "v7_1_positive_diversity_manual_review_expansion_v2"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _review_items(overlay: dict[str, Any]) -> list[dict[str, Any]]:
    items = overlay.get("reviewItems") or overlay.get("items") or []
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _pitch_region(row: dict[str, Any], *, width: int = 4096, height: int = 1080) -> tuple[str, str, str]:
    bbox = _safe_bbox(row)
    if not bbox:
        return "central_pitch_unknown_bbox", "reviewable_in_play_candidate", "low"
    cx = (bbox["x1"] + bbox["x2"]) / 2.0
    cy = (bbox["y1"] + bbox["y2"]) / 2.0
    x_pct = cx / float(width)
    y_pct = cy / float(height)
    horizontal = "left" if x_pct < 0.33 else "right" if x_pct > 0.67 else "center"
    vertical = "top_edge" if y_pct < 0.12 else "bottom_edge" if y_pct > 0.88 else "middle"
    pitch_region = f"{horizontal}_{vertical}"
    replacement_risk = "high" if x_pct < 0.03 or x_pct > 0.97 or y_pct < 0.08 or y_pct > 0.92 else "medium" if vertical != "middle" else "low"
    playability = "evidence_only_probable_replacement_or_off_pitch_ball" if replacement_risk == "high" else "reviewable_in_play_candidate"
    return pitch_region, playability, replacement_risk


def _annotate_pitch_fields(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reviewable: list[dict[str, Any]] = []
    evidence_only: list[dict[str, Any]] = []
    for row in rows:
        updated = dict(row)
        pitch_region, playability, replacement_risk = _pitch_region(updated)
        updated["pitchRegionClass"] = pitch_region
        updated["playabilityClass"] = playability
        updated["replacementBallRisk"] = replacement_risk
        if replacement_risk == "high":
            updated["reviewStatus"] = "bad_crop_or_unusable_frame"
            updated["trainingEligibility"] = "evidence_only_not_positive_training_truth"
            updated["rejectionReason"] = "probable_replacement_or_off_pitch_ball"
            evidence_only.append(updated)
            continue
        updated["reviewStatus"] = "pending_review"
        updated["trainingEligibility"] = "pending_review"
        reviewable.append(updated)
    return reviewable, evidence_only


def _html(path: Path, rows: list[dict[str, Any]]) -> None:
    cards: list[str] = []
    for row in rows[:360]:
        title = html.escape(str(row.get("candidateId")))
        frame = html.escape(str(row.get("frameIndex")))
        region = html.escape(str(row.get("pitchRegionClass")))
        play = html.escape(str(row.get("playabilityClass")))
        risk = html.escape(str(row.get("replacementBallRisk")))
        frame_img = html.escape(Path(str(row.get("reviewFrameImagePath"))).name)
        crop_img = html.escape(Path(str(row.get("reviewCropImagePath"))).name)
        cards.append(
            "\n".join(
                [
                    "<section>",
                    f"<h2>{title}</h2>",
                    f"<p>frame {frame} | {region} | {play} | replacement risk {risk}</p>",
                    f'<img src="review_frames/{frame_img}" alt="{title} frame">',
                    f'<img src="review_crops/{crop_img}" alt="{title} crop">',
                    "</section>",
                ]
            )
        )
    path.write_text(
        "\n".join(
            [
                "<!doctype html><meta charset='utf-8'>",
                "<title>V7.1 Pitch-filtered Review Package</title>",
                "<style>body{font-family:sans-serif;margin:20px}section{border:1px solid #ccc;margin:14px 0;padding:10px}img{max-width:46%;margin:6px;border:1px solid #aaa}</style>",
                "<h1>V7.1 pitch-filtered positive candidates</h1>",
                *cards,
            ]
        ),
        encoding="utf-8",
    )


def run_v7_1_positive_candidate_mining_expansion_v3_pitch_filtered(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    video_path: Path = DEFAULT_VIDEO_PATH,
    candidate_target: int = 240,
    frame_bucket_size: int = 500,
) -> dict[str, Any]:
    candidate_root = _candidate_root(Path(storage_root), candidate_name)
    output_root = candidate_root / OUTPUT_DIR_NAME
    output_root.mkdir(parents=True, exist_ok=True)
    v2_root = candidate_root / V2_DIR_NAME
    resolution_root = candidate_root / RESOLUTION_DIR_NAME

    v2_overlay = _load_json(v2_root / "corrected_label_overlay.json", required=True)
    v2_summary = _load_json(v2_root / "v7_1_positive_candidate_mining_expansion_summary.json", required=True)
    resolution = _load_json(resolution_root / "v7_1_positive_diversity_manual_review_resolution_summary.json", required=True)
    reviewed_positive_rows = _load_v2_reviewed_positive_rows(candidate_root, RESOLUTION_DIR_NAME)
    mined_rows = _mine_new_group_candidates(
        reviewed_positive_rows,
        target=max(candidate_target, 120),
        video_path=Path(video_path),
        frame_bucket_size=frame_bucket_size,
    )

    candidate_by_id: dict[str, dict[str, Any]] = {}
    # The v2 overlay is evidence for prior review state, but its candidate boxes can point
    # at replacement balls. V3 deliberately starts from freshly mined editable boxes.
    for row in mined_rows:
        candidate_by_id.setdefault(str(row.get("candidateId")), row)
    annotated_reviewable, evidence_only = _annotate_pitch_fields(list(candidate_by_id.values()))
    evidenced_reviewable, missing_evidence = _attach_review_evidence(rows=annotated_reviewable, output_root=output_root, video_path=Path(video_path))
    evidenced_evidence_only, missing_evidence_only = _attach_review_evidence(rows=evidence_only, output_root=output_root / "evidence_only", video_path=Path(video_path))
    group_count = len({row.get("splitGroupId") for row in evidenced_reviewable if row.get("splitGroupId")})
    goal_achieved = len(evidenced_reviewable) >= 120 and group_count >= 8 and missing_evidence == 0
    primary_blocker = None if goal_achieved else "v7_1_positive_candidate_mining_pool_insufficient"
    next_lever = NEXT_REVIEW if goal_achieved else "v7_1_source_sampling_expansion"
    english = (
        "Pitch-filtered positive candidate package is ready for manual review; no training or promotion."
        if goal_achieved
        else "Pitch-filtered mining did not produce enough reviewable candidates; broaden source sampling."
    )
    summary = {
        "batchName": "v7_1_positive_candidate_mining_expansion_v3_pitch_filtered",
        "generatedAt": _utc_now_iso(),
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": True,
        "primaryBlocker": primary_blocker,
        "previousReviewedPositiveSourceCount": _safe_int(resolution.get("totalReviewedPositiveSourceCount"), _safe_int(v2_summary.get("previousReviewedPositiveSourceCount"), 103)),
        "previousReviewCandidateCount": _safe_int(v2_summary.get("totalCandidateReviewCount")),
        "newMinedCandidateCount": len(mined_rows),
        "totalCandidateReviewCount": len(evidenced_reviewable),
        "distinctCandidateSplitGroupCount": group_count,
        "reviewRowsExcludedMissingEvidenceCount": missing_evidence,
        "evidenceOnlyMissingEvidenceCount": missing_evidence_only,
        "replacementBallEvidenceOnlyCount": len(evidenced_evidence_only),
        "knownCropValidationMissesCarriedForward": _safe_int(resolution.get("knownCropValidationMissesReviewed")),
        "knownFullPipelineMissesCarriedForward": _safe_int(resolution.get("knownFullPipelineMissesReviewed")),
        "trainingExecuted": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationAllowed": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    overlay = {
        "batchName": summary["batchName"],
        "reviewItemCount": len(evidenced_reviewable),
        "pendingReviewCount": len(evidenced_reviewable),
        "reviewItems": evidenced_reviewable,
    }
    _write_json(output_root / "pitch_filtered_corrected_label_overlay.json", overlay)
    _write_json(output_root / "corrected_label_overlay.json", overlay)
    _write_json(output_root / "pitch_filtered_candidate_summary.json", summary)
    _write_json(output_root / "v7_1_positive_candidate_mining_expansion_summary.json", summary)
    _write_json(output_root / "pitch_region_candidate_audit.json", {"reviewableCount": len(evidenced_reviewable), "rows": evidenced_reviewable})
    _write_json(output_root / "replacement_ball_filter_audit.json", {"replacementBallEvidenceOnlyCount": len(evidenced_evidence_only), "rows": evidenced_evidence_only})
    _write_json(output_root / "new_group_candidate_manifest.json", {"newMinedCandidateCount": len(mined_rows), "rows": mined_rows})
    _write_json(output_root / "decision_matrix.json", {"generatedAt": _utc_now_iso(), "summary": summary})
    _write_json(output_root / "batch_outcome_analysis.json", {"summary": summary})
    (output_root / "batch_outcome_analysis.md").write_text(f"# V7.1 Pitch-filtered Candidate Mining\n\n{english}\n", encoding="utf-8")
    _html(output_root / "review_index.html", evidenced_reviewable)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build v7.1 pitch-filtered positive candidate review artifacts.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--video-path", type=Path, default=DEFAULT_VIDEO_PATH)
    parser.add_argument("--candidate-target", type=int, default=240)
    parser.add_argument("--frame-bucket-size", type=int, default=500)
    args = parser.parse_args()
    payload = run_v7_1_positive_candidate_mining_expansion_v3_pitch_filtered(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        video_path=args.video_path,
        candidate_target=args.candidate_target,
        frame_bucket_size=args.frame_bucket_size,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
