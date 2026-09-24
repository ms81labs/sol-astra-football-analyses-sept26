"""Preserve runtime conversion and unknown-clock behavior while tightening types."""
from decimal import Decimal

import pytest

from backend.app.run_benchmarks import _safe_float, _safe_int, _safe_suite_metric
from backend.app.workbench.media import DecodedFrame, map_decoded_to_sample, sample_decode_anchors
from backend.app.workbench.money import money


class NumericValue:
    def __int__(self):
        return 7

    def __float__(self):
        return 7.5


@pytest.mark.parametrize("value,integer,real", [
    (None, -1, -1.0), (True, -1, -1.0), (object(), -1, -1.0),
    (b"3", 3, 3.0), ("3", 3, 3.0), (Decimal("3.5"), 3, 3.5),
    (NumericValue(), 7, 7.5), ("bad", -1, -1.0),
])
def test_safe_converters_keep_existing_coercions(value, integer, real):
    assert _safe_int(value, -1) == integer
    assert _safe_float(value, -1.0) == real


@pytest.mark.parametrize("value,expected", [(True, 1.0), (None, 0.0), ("bad", 0.0), (NumericValue(), 7.5)])
def test_suite_conversion_retains_boolean_and_custom_numeric_behavior(value, expected):
    assert _safe_suite_metric(value) == expected


def frame(index, timestamp):
    return DecodedFrame(index, None, timestamp, 1, 1, "bgr", 0, b"\0\0\0", "test")


def test_missing_clock_does_not_publish_an_invented_sample():
    assert map_decoded_to_sample(frame(0, None), frame_interval=1) is None


def test_missing_anchor_clock_is_preserved_without_bridging_unknown_gap():
    anchors = sample_decode_anchors([frame(0, 0.0), frame(1, None), frame(2, 3.0), frame(3, 4.0)])
    assert anchors == {"beginning": 0.0, "middle": 3.0, "end": 4.0, "discontinuities": [3]}


@pytest.mark.parametrize("value", [True, "NaN", "Infinity", "-1", "0.0000000000001", "-Infinity"])
def test_typed_money_still_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        money(value)
