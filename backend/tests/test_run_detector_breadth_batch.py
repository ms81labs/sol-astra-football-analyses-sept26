from __future__ import annotations

from pathlib import Path

import backend.scripts.run_detector_breadth_batch as run_detector_breadth_batch


def _screen_result(
    *,
    video_path: Path,
    recommended_profile: str,
    selected_score: float,
    viable: bool,
    edge_frame_share: float,
    dominant_anchor_share: float,
) -> dict[str, object]:
    return {
        "videoPath": str(video_path),
        "recommendedProfile": recommended_profile,
        "profiles": [
            {
                "name": recommended_profile,
                "candidateSummary": {
                    "dominantAnchorShare": dominant_anchor_share,
                },
                "selectedSummary": {
                    "frames": 7,
                    "edgeFrameShare": edge_frame_share,
                },
                "selectedScore": selected_score,
                "viable": viable,
                "dominantAnchorShare": dominant_anchor_share,
                "meanSourceCenterY": 172.2,
            }
        ],
    }


def test_finalize_detector_breadth_screen_ranks_models_deterministically(tmp_path):
    clip_path = tmp_path / "trimed-5min.mp4"
    clip_path.write_bytes(b"video")
    results_by_model = {
        "yolov10n.pt": _screen_result(
            video_path=clip_path,
            recommended_profile="edge_margin_40_upper_075",
            selected_score=151.0,
            viable=True,
            edge_frame_share=0.30,
            dominant_anchor_share=0.40,
        ),
        "yolo11s.pt": _screen_result(
            video_path=clip_path,
            recommended_profile="edge_margin_40_upper_078",
            selected_score=158.0,
            viable=True,
            edge_frame_share=0.24,
            dominant_anchor_share=0.52,
        ),
        "yolov8n.pt": _screen_result(
            video_path=clip_path,
            recommended_profile="edge_margin_40_upper_079",
            selected_score=158.0,
            viable=True,
            edge_frame_share=0.24,
            dominant_anchor_share=0.52,
        ),
        "yolov8s.pt": _screen_result(
            video_path=clip_path,
            recommended_profile="edge_margin_40_upper_080",
            selected_score=149.0,
            viable=False,
            edge_frame_share=0.41,
            dominant_anchor_share=0.28,
        ),
    }

    cells = [
        {
            **run_detector_breadth_batch._screen_result_cell(
                detector_model_path=model_path,
                payload=results_by_model[model_path],
            ),
            "inputOrder": index,
        }
        for index, model_path in enumerate(run_detector_breadth_batch.DETECTOR_BREADTH_MODELS)
    ]
    payload = run_detector_breadth_batch._finalize_screen_payload(
        video_path=clip_path,
        detector_models=run_detector_breadth_batch.DETECTOR_BREADTH_MODELS,
        cells=cells,
        screen_execution_mode=run_detector_breadth_batch.SCREEN_EXECUTION_MODE_LOCAL_CPU,
    )

    ranked_models = [cell["detectorModelPath"] for cell in payload["cells"]]
    assert ranked_models == ["yolo11s.pt", "yolov8n.pt", "yolov10n.pt", "yolov8s.pt"]
    assert payload["screenWinningDetectorModelPath"] == "yolo11s.pt"
    assert payload["cells"][0]["qualifiesForRemoteProof"] is True
    assert all(cell["qualifiesForRemoteProof"] is False for cell in payload["cells"][1:])
