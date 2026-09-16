import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from backend.scripts import evaluate_football_analysis_pilot_soccertrack_resolution as resolution


def test_tiled_detection_boxes_return_to_source_coordinates() -> None:
    class Detector:
        def predict(self, image, **_kwargs):
            assert image.shape == (6, 4, 3)
            return [SimpleNamespace(boxes=SimpleNamespace(
                xyxy=torch.tensor([[1, 1, 3, 4]]), conf=torch.tensor([0.25])
            ))]

    boxes = resolution._predict_boxes(Detector(), np.zeros((6, 8, 3), dtype=np.uint8), 1280, tile_width=4)

    np.testing.assert_array_equal(boxes, [[1, 1, 3, 4, 0.25], [5, 1, 7, 4, 0.25]])


def test_resolution_artifact_binds_all_scoring_inputs() -> None:
    artifact = json.loads(resolution.OUTPUT_PATH.read_text(encoding="utf-8"))
    for key, path in (
        ("calibrationSha256", resolution.CALIBRATION_PATH),
        ("intrinsicsSha256", resolution.INTRINSICS_PATH),
        ("referenceSha256", resolution.REFERENCE_PATH),
    ):
        assert artifact[key] == hashlib.sha256(path.read_bytes()).hexdigest()
