from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_promoted_v6_manual_review_followthrough_batch as manual_review_batch


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _seed_bbox(frame_id: int) -> dict[str, float]:
    return {
        "x1": float(frame_id),
        "y1": float(frame_id + 1),
        "x2": float(frame_id + 10),
        "y2": float(frame_id + 11),
    }


def _lineage() -> dict[str, str]:
    return {
        "baselineBallTruthLayersPath": "/baseline/ball_truth_layers.json",
        "baselineSelectedClusterDeltaPath": "/baseline/selected_cluster_delta.json",
        "promotedBallTruthLayersPath": "/promoted/ball_truth_layers.json",
        "promotedSelectedClusterDeltaPath": "/promoted/selected_cluster_delta.json",
    }


def _write_inputs(
    root: Path,
    *,
    frame_ids: list[int],
    with_video: bool = True,
    drop_seed_bbox_for: set[int] | None = None,
    drop_lineage_for: set[int] | None = None,
) -> dict[str, Path]:
    output_root = root / "output"
    followthrough_root = root / "followthrough"
    gold_root = root / "gold_truth"
    proof_root = root / "proof"
    runtime_root = root / "runtime"
    source_manifest_path = root / "frozen_source_manifest.json"
    video_path = root / "videos" / "trimed-5min.mp4"
    if with_video:
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"not-a-real-video")

    missing_bbox = drop_seed_bbox_for or set()
    missing_lineage = drop_lineage_for or set()
    overlay_items = []
    candidate_frames = []
    seed_rows = []
    for index, frame_id in enumerate(frame_ids):
        candidate_frame_id = f"candidate-{frame_id}"
        window_id = f"window-{index // 5}"
        seed_bbox = None if frame_id in missing_bbox else _seed_bbox(frame_id)
        lineage = {} if frame_id in missing_lineage else _lineage()
        overlay_items.append(
            {
                "reviewStatus": "pending_review",
                "frameId": frame_id,
                "candidateFrameId": candidate_frame_id,
                "windowId": window_id,
                "gapClass": "candidate_rows_collapsed_but_segment_selection_zero",
                "evidenceSource": "profile_selection_funnel_audit",
            }
        )
        candidate_frames.append(
            {
                "candidateFrameId": candidate_frame_id,
                "windowId": window_id,
                "sourceClipId": "trimed-5min.mp4",
                "frameId": frame_id,
                "timestampSeconds": round(frame_id / 25.0, 3),
                "seedBBox": seed_bbox,
                "lineage": lineage,
                "lineageComplete": bool(lineage),
                "promotedSignalSources": ["promoted_recovery_profile_proposal"],
            }
        )
        seed_rows.append(
            {
                "candidateFrameId": candidate_frame_id,
                "windowId": window_id,
                "frameId": frame_id,
                "decision": "accept_seed",
                "seedSource": "baseline_current_accepted_ball",
                "row": {
                    "Frame_ID": frame_id,
                    "Timestamp": round(frame_id / 25.0, 3),
                    "Source_X1": seed_bbox["x1"] if isinstance(seed_bbox, dict) else None,
                    "Source_Y1": seed_bbox["y1"] if isinstance(seed_bbox, dict) else None,
                    "Source_X2": seed_bbox["x2"] if isinstance(seed_bbox, dict) else None,
                    "Source_Y2": seed_bbox["y2"] if isinstance(seed_bbox, dict) else None,
                },
                "lineage": lineage,
            }
        )

    _write_json(
        followthrough_root / "manual_review_followthrough_overlay.json",
        {
            "reviewItemCount": len(overlay_items),
            "reviewPurpose": "Resolve proposal follow-through frames.",
            "reviewItems": overlay_items,
        },
    )
    _write_json(
        followthrough_root / "blocker_summary.json",
        {
            "batchStatus": "exhausted",
            "dominantBlockerClass": "candidate_rows_collapsed_but_segment_selection_zero",
            "nextCorrectiveFamily": "manual_review_required",
            "proposalDiagnostics": {
                "proposalCandidateFrames": 110,
                "proposalRawDetectedFrames": 93,
                "proposalCollapsedFrames": 93,
                "selectedFrames": 0,
            },
        },
    )
    _write_json(
        gold_root / "candidate_frame_truth_manifest.json",
        {
            "candidateFrameCount": len(candidate_frames),
            "representedBootstrapWindowCount": max(1, len({item["windowId"] for item in candidate_frames})),
            "representedMissingAcceptedFrameCount": len(candidate_frames),
            "candidateFrames": candidate_frames,
        },
    )
    _write_json(
        gold_root / "accepted_controlled_truth_seed.json",
        {
            "acceptedSeedRowCount": len(seed_rows),
            "acceptedBallSeedRows": seed_rows,
            "controlledPossessionCandidateRows": [],
        },
    )
    _write_json(
        proof_root / "recovery_profile_matrix.json",
        {
            "selectedProfileName": None,
            "profiles": [
                {
                    "name": "proposal_windows_075",
                    "proposalCandidateFrames": 110,
                    "proposalRawDetectedFrames": 93,
                    "proposalCollapsedFrames": 93,
                    "selectedFrames": 0,
                }
            ],
        },
    )
    _write_json(
        proof_root / "proof_summary.json",
        {
            "bestProposalCandidateFrames": 110,
            "bestProposalRawDetectedFrames": 93,
            "bestProposalAfterSeedCollapseFrames": 93,
            "bestProposalSelectedFrames": 0,
        },
    )
    _write_json(runtime_root / "promoted_touchline_detector_candidate.json", {"candidate": "v6"})
    _write_json(source_manifest_path, {"sources": [{"clipId": "trimed-5min.mp4"}]})
    return {
        "output_root": output_root,
        "followthrough_root": followthrough_root,
        "gold_truth_root": gold_root,
        "promoted_proof_root": proof_root,
        "video_path": video_path,
        "runtime_default_path": runtime_root / "promoted_touchline_detector_candidate.json",
        "source_manifest_path": source_manifest_path,
    }


def test_manual_review_batch_converts_followthrough_items_to_repo_native_overlay(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, frame_ids=list(range(100, 178)), with_video=False)

    payload = manual_review_batch.run_promoted_v6_manual_review_followthrough_batch(**paths)

    summary = payload["summary"]
    assert summary["goalAchieved"] is True
    assert summary["successfulApproach"] == "B_json_only_review_package_fallback"
    assert summary["reviewItemCount"] == 78
    assert summary["pendingReviewCount"] == 78
    assert summary["lineageCompleteCount"] == 78
    overlay = json.loads((paths["output_root"] / "reviewed_label_overlay.json").read_text())
    assert overlay["reviewItemCount"] == 78
    assert overlay["pendingReviewCount"] == 78
    first = overlay["reviewItems"][0]
    assert first["decision"] == "pending_review"
    assert first["sourceClipId"] == "trimed-5min.mp4"
    assert first["frameIndex"] == 100
    assert first["candidateFrameId"] == "candidate-100"
    assert first["windowId"] == "window-0"
    assert first["seedBBox"] == _seed_bbox(100)
    assert first["lineage"]["promotedBallTruthLayersPath"] == "/promoted/ball_truth_layers.json"
    assert "candidate_rows_collapsed_but_segment_selection_zero" in first["notes"]


def test_manual_review_batch_writes_deterministic_manifests(tmp_path: Path) -> None:
    frame_ids = [20, 10, 30] + list(range(100, 175))
    paths = _write_inputs(tmp_path, frame_ids=frame_ids, with_video=False)

    payload = manual_review_batch.run_promoted_v6_manual_review_followthrough_batch(**paths)

    frame_manifest = json.loads((paths["output_root"] / "review_frame_manifest.json").read_text())
    assert [item["frameIndex"] for item in frame_manifest["reviewFrames"]][:3] == [10, 20, 30]
    assert all(item["imageExtracted"] is False for item in frame_manifest["reviewFrames"])
    assert frame_manifest["imageExtractionStatus"] == "json_only_no_video"
    bundle = json.loads((paths["output_root"] / "review_bundle_manifest.json").read_text())
    assert bundle["reviewedLabelOverlayPath"].endswith("reviewed_label_overlay.json")
    assert bundle["reviewFrameManifestPath"].endswith("review_frame_manifest.json")
    assert bundle["reviewerInstructions"][0].startswith("Resolve every pending_review item")
    assert payload["decisionMatrix"]["nextCorrectiveFamily"] == "manual_review_pending"


def test_manual_review_batch_marks_weak_evidence_when_seed_boxes_or_lineage_missing(tmp_path: Path) -> None:
    paths = _write_inputs(
        tmp_path,
        frame_ids=list(range(200, 278)),
        with_video=False,
        drop_seed_bbox_for={205},
        drop_lineage_for={210},
    )

    payload = manual_review_batch.run_promoted_v6_manual_review_followthrough_batch(**paths)

    summary = payload["summary"]
    assert summary["goalAchieved"] is False
    assert summary["nextCorrectiveFamily"] == "manual_review_lineage_refresh"
    assert "missing_seed_bbox_count_nonzero" in summary["weakEvidenceReasons"]
    assert "lineage_incomplete_count_nonzero" in summary["weakEvidenceReasons"]
    blocker = json.loads((paths["output_root"] / "blocker_summary.json").read_text())
    assert blocker["batchStatus"] == "blocked"


def test_manual_review_batch_does_not_mutate_runtime_or_source_manifest(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, frame_ids=list(range(300, 378)), with_video=False)
    runtime_before = paths["runtime_default_path"].read_text()
    source_manifest_before = paths["source_manifest_path"].read_text()

    manual_review_batch.run_promoted_v6_manual_review_followthrough_batch(**paths)

    assert paths["runtime_default_path"].read_text() == runtime_before
    assert paths["source_manifest_path"].read_text() == source_manifest_before
