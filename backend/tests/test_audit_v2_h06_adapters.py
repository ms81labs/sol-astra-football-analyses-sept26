from types import SimpleNamespace
from fractions import Fraction

import numpy as np

from backend.app.workbench.perception import (
    Capabilities,
    Detection,
    IouAssociationFallback,
    Preprocessor,
    TrackerAdapter,
    select_inference_device,
)


def test_preprocessor_transforms_pixels_and_maps_boxes_back_to_source() -> None:
    source = np.arange(4 * 4 * 3, dtype=np.uint8).reshape(4, 4, 3)

    pixels, inverse = Preprocessor().transform(
        {
            "pixels": source.tobytes(),
            "width": 4,
            "height": 4,
            "colourOrder": "rgb",
        },
        crop=(1, 1, 3, 3),
        resize=(4, 4),
    )

    expected = source[1:3, 1:3, ::-1].repeat(2, axis=0).repeat(2, axis=1)
    np.testing.assert_array_equal(pixels, expected)
    assert inverse.map_box((0.0, 0.0, 4.0, 4.0)) == (1.0, 1.0, 3.0, 3.0)


def test_tracker_preserves_ids_emitted_by_core_tracker() -> None:
    results = [
        SimpleNamespace(boxes=[SimpleNamespace(id=[41], xyxy=[[frame, 2.0, frame + 10.0, 22.0]])])
        for frame in range(10)
    ]

    tracks = [TrackerAdapter().from_ultralytics(result)[0] for result in results]

    assert [track["trackId"] for track in tracks] == ["41"] * 10
    assert all(track["productionPath"] == "botsort" for track in tracks)


def test_iou_association_is_explicitly_a_non_production_fallback() -> None:
    detection = Detection(frameId=3, bbox=(1, 2, 11, 22), score=0.9, kind="player", stratum="near")

    track = IouAssociationFallback().associate([detection])[0]

    assert track["trackId"].startswith("iou_fallback:")
    assert track["productionPath"] == "iou_fallback"
    assert track["productionEligible"] is False


def test_cuda_inference_selection_does_not_depend_on_hardware_decode() -> None:
    available = select_inference_device(
        "cuda",
        Capabilities(hw_decode=False, cuda_inference=True, hw_encode=False),
    )
    unprobed = select_inference_device(
        "cuda",
        Capabilities(hw_decode=True, cuda_inference=None, hw_encode=True),
    )

    assert available == {"device": "cuda", "reasonCodes": []}
    assert unprobed == {"device": "cpu", "reasonCodes": ["CUDA_UNPROBED"]}


def test_observed_device_is_only_reported_from_runtime_tensor() -> None:
    from backend.app.workbench.perception import DetectorAdapter

    receipt = DetectorAdapter().detect(
        {"frameId": 1},
        capabilities=Capabilities(False, True, False),
        requested_backend="cuda",
    )
    assert receipt["selectedBackend"] == "cuda"
    assert receipt["observedDevice"] is None

    class Boxes(list):
        data = SimpleNamespace(device="cuda:0")

    boxes = Boxes()
    observed = DetectorAdapter().from_ultralytics(SimpleNamespace(boxes=boxes))
    assert observed["observedDevice"] == "cuda:0"


def test_tracking_artifact_retains_canonical_pts_and_time_base() -> None:
    from backend.run_guerilla import build_tracking_row

    row = build_tracking_row(
        frame_id=3,
        timestamp=float(Fraction(3003, 30_000)),
        entity_type="player",
        track_id=7,
        pitch_x=1,
        pitch_y=2,
        detection_conf=0.9,
        source_box=(0, 0, 2, 2),
        pts=3003,
        time_base=(1, 30_000),
    )
    assert row["Timestamp"] == float(Fraction(3003, 30_000))
    assert (row["PTS"], row["TimeBaseNum"], row["TimeBaseDen"]) == (3003, 1, 30_000)
