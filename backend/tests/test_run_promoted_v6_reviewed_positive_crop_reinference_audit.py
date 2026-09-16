from __future__ import annotations

import json
from pathlib import Path

from backend.scripts import run_promoted_v6_reviewed_positive_crop_reinference_audit


def test_crop_reinference_audit_selects_geometry_fix_when_expanded_crops_detect(tmp_path: Path):
    proposal_root = tmp_path / "reviewed_positive_proposal_generation_fix_v1"
    output_root = tmp_path / "reviewed_positive_crop_reinference_audit_v1"
    proposal_root.mkdir(parents=True)
    (proposal_root / "reviewed_positive_proposal_coverage.json").write_text(
        json.dumps(
            {
                "reviewedPositiveFrames": [
                    {
                        "reviewItemId": "review-240",
                        "candidateFrameId": "candidate-240",
                        "windowId": "window",
                        "sourceClipId": "trimed-5min.mp4",
                        "frameIndex": 240,
                        "reviewedBBox": {"x1": 381, "y1": 688, "x2": 397, "y2": 704},
                        "windowGenerated": True,
                        "zeroDetect": True,
                        "rawDetected": False,
                        "candidateGenerated": False,
                        "collapsed": False,
                        "selected": False,
                        "accepted": False,
                        "diagnosticClass": "reviewed_positive_anchor_window_zero_detect",
                    },
                    {
                        "reviewItemId": "review-245",
                        "candidateFrameId": "candidate-245",
                        "windowId": "window",
                        "sourceClipId": "trimed-5min.mp4",
                        "frameIndex": 245,
                        "reviewedBBox": {"x1": 390, "y1": 684, "x2": 406, "y2": 701},
                        "windowGenerated": True,
                        "zeroDetect": True,
                        "rawDetected": False,
                        "candidateGenerated": False,
                        "collapsed": False,
                        "selected": False,
                        "accepted": False,
                        "diagnosticClass": "reviewed_positive_anchor_window_zero_detect",
                    },
                    {
                        "reviewItemId": "review-265",
                        "candidateFrameId": "candidate-265",
                        "windowId": "window",
                        "sourceClipId": "trimed-5min.mp4",
                        "frameIndex": 265,
                        "reviewedBBox": {"x1": 440, "y1": 660, "x2": 456, "y2": 676},
                        "windowGenerated": True,
                        "zeroDetect": False,
                        "rawDetected": True,
                        "candidateGenerated": True,
                        "collapsed": True,
                        "selected": False,
                        "accepted": False,
                        "diagnosticClass": "reviewed_positive_collapsed_not_selected",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (proposal_root / "reviewed_positive_proposal_fix_summary.json").write_text(
        json.dumps(
            {
                "retentionTruth": {
                    "acceptedRetentionRatio": 0.069,
                    "controlledRetentionRatio": 0.102,
                    "primaryRetentionBlockerClass": "accepted_signal_retention_collapse",
                }
            }
        ),
        encoding="utf-8",
    )

    def fake_frame_loader(frame_index: int):
        return {
            "frameIndex": frame_index,
            "frameShape": [720, 1280, 3],
            "frameAvailable": True,
            "frame": object(),
        }

    def fake_predictor(*, crop, attempt, model_path):
        if attempt["frameIndex"] in {240, 245} and attempt["contextRatio"] == 4.0:
            return [{"confidence": 0.72, "bbox": [10, 10, 18, 18], "classId": 0}]
        return []

    payload = (
        run_promoted_v6_reviewed_positive_crop_reinference_audit
        .run_promoted_v6_reviewed_positive_crop_reinference_audit(
            proposal_generation_root=proposal_root,
            output_root=output_root,
            video_path=tmp_path / "missing.mp4",
            predictor=fake_predictor,
            frame_loader=fake_frame_loader,
            model_path=tmp_path / "model.pt",
            context_ratios=[1.0, 2.0, 4.0],
            imgsz_values=[960],
        )
    )

    summary = payload["reviewedPositiveCropReinferenceSummary"]
    matrix = payload["reviewedPositiveCropReinferenceMatrix"]
    assert summary["reviewedPositiveFrameCount"] == 3
    assert summary["zeroDetectFrameCount"] == 2
    assert summary["reinferenceDetectedFrameCount"] == 2
    assert summary["dominantBlockerClass"] == "reviewed_positive_crop_geometry_scale_rescue_available"
    assert summary["nextCorrectiveFamily"] == "reviewed_positive_crop_geometry_scale_fix"
    by_frame = {row["frameIndex"]: row for row in matrix["reviewedPositiveCropRows"]}
    assert by_frame[240]["diagnosticClass"] == "reviewed_positive_crop_geometry_scale_rescue_available"
    assert by_frame[240]["bestAttempt"]["contextRatio"] == 4.0
    assert by_frame[265]["diagnosticClass"] == "reviewed_positive_existing_proposal_followthrough_gap"
    assert (output_root / "crop_reinference_scale_audit.json").exists()
    assert (output_root / "batch_outcome_analysis.md").exists()
