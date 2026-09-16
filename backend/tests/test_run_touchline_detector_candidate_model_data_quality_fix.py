from __future__ import annotations

import backend.scripts.run_touchline_detector_candidate_model_data_quality_fix as run_touchline_detector_candidate_model_data_quality_fix


def test_select_new_failing_windows_prefers_filtered_probe_and_rejects_overlap() -> None:
    frame_level_probe_delta = {
        "layers": {
            "filteredProbe": {
                "baselineOnlyFrameIds": [90, 95, 100, 220, 225, 230, 235],
            },
            "rawProbe": {
                "baselineOnlyFrameIds": [92, 97, 102, 320, 325, 330],
            },
        }
    }
    existing_units = [
        {"frameStart": 50, "frameEnd": 120},
        {"frameStart": 400, "frameEnd": 450},
    ]

    windows = run_touchline_detector_candidate_model_data_quality_fix._select_new_failing_windows(
        frame_level_probe_delta=frame_level_probe_delta,
        existing_failing_units=existing_units,
        clip_max_frame=500,
    )

    assert [window["selectionSourceLayer"] for window in windows] == [
        "filteredProbe",
        "rawProbe",
    ]
    assert windows[0]["frameStart"] == 180
    assert windows[0]["frameEnd"] == 275
    assert windows[1]["frameStart"] == 280
    assert windows[1]["frameEnd"] == 370
