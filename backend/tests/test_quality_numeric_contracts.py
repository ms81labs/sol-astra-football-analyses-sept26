"""Characterize existing numeric guards and cancellation-view payloads."""

from decimal import Decimal
import math
from types import SimpleNamespace

import pytest

from backend.app.insight_routes import _dashboard_metric_value
from backend.app.review_routes import _trust_crop_geometry
from backend.app.workbench.jobs import cancellation_does_not_erase_charges


class _IntSubclass(int):
    pass


class _FloatSubclass(float):
    pass


@pytest.mark.parametrize(
    "value,expected",
    [
        (0, 0.0),
        (7, 7.0),
        (1.25, 1.25),
        (-2, -2.0),
        (None, None),
        (True, None),
        (False, None),
        ("1.25", None),
        (float("nan"), None),
        (float("inf"), None),
        (float("-inf"), None),
        (_IntSubclass(7), None),
        (_FloatSubclass(1.25), None),
        (Decimal("1.25"), None),
        ([], None),
        ({}, None),
    ],
)
@pytest.mark.parametrize("recorded", [False, True])
def test_dashboard_accepts_only_existing_finite_builtin_measurements(
    value, expected, recorded
):
    summary = {"myTeamXg": value}
    if recorded:
        summary["metricAvailability"] = [
            {
                "metric": "my_team_experimental_shot_quality_sum",
                "availability": "available",
                "value": value,
            }
        ]
    result = _dashboard_metric_value(
        summary, field="myTeamXg", metric="my_team_experimental_shot_quality_sum"
    )
    assert result == expected
    if result is not None:
        assert type(result) is float


@pytest.mark.parametrize(
    "availability,expected",
    [
        ("available", 2.5),
        ("experimental", 2.5),
        ("withheld", None),
        ("unavailable", None),
        (None, None),
    ],
)
def test_dashboard_keeps_measurement_availability_policy(availability, expected):
    summary = {
        "myTeamXg": 99,
        "metricAvailability": [
            {
                "metric": "my_team_experimental_shot_quality_sum",
                "availability": availability,
                "value": 2.5,
            }
        ],
    }
    assert (
        _dashboard_metric_value(
            summary, field="myTeamXg", metric="my_team_experimental_shot_quality_sum"
        )
        == expected
    )


@pytest.mark.parametrize(
    "length,width,allowed",
    [
        (105, 68, True),
        (105.5, 68.5, True),
        (None, 68, False),
        (105, None, False),
        (True, 68, False),
        (105, False, False),
        ("105", 68, False),
        (_IntSubclass(105), 68, False),
        (105, _FloatSubclass(68), False),
        (Decimal("105"), 68, False),
    ],
)
def test_geometry_preserves_exact_numeric_type_policy(length, width, allowed):
    manifest = SimpleNamespace(
        effectiveConfig={"pitchLengthM": length, "pitchWidthM": width},
        calibrationData=None,
    )
    frame = SimpleNamespace(
        geometryAvailable=True,
        coordinateSpace="pitch_normalized_0_100",
        coordinateProvenance={
            "outputConvention": "pitch_normalized_0_100",
            "inputConvention": {"space": "pitch_normalized_0_100"},
        },
    )
    result = _trust_crop_geometry(manifest, [frame])
    assert result == (
        (float(length), float(width), [])
        if allowed
        else (None, None, ["CALIBRATION_UNAVAILABLE"])
    )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1.0, 0.0])
def test_geometry_typing_refactor_does_not_add_new_value_validation(value):
    manifest = SimpleNamespace(
        effectiveConfig={"pitchLengthM": value, "pitchWidthM": 68.0},
        calibrationData=None,
    )
    frame = SimpleNamespace(
        geometryAvailable=True,
        coordinateSpace="pitch_normalized_0_100",
        coordinateProvenance={
            "outputConvention": "pitch_normalized_0_100",
            "inputConvention": {"space": "pitch_normalized_0_100"},
        },
    )
    length, width, reasons = _trust_crop_geometry(manifest, [frame])
    assert width == 68.0 and reasons == []
    assert math.isnan(length) if math.isnan(value) else length == value


@pytest.mark.parametrize("cancelled", [True, False])
@pytest.mark.parametrize("incurred", [0.0, 1.2, None])
def test_cancellation_view_preserves_known_and_unknown_amounts(cancelled, incurred):
    result = cancellation_does_not_erase_charges(cancelled=cancelled, incurred=incurred)
    assert result == {
        "cancelled": cancelled,
        "incurred": incurred,
        "chargesErased": False,
        "reasonCodes": ["CANCELLATION_DOES_NOT_ERASE_INCURRED_CHARGES"]
        if cancelled
        else [],
    }
    assert result["incurred"] is incurred
    other = cancellation_does_not_erase_charges(cancelled=cancelled, incurred=incurred)
    result["reasonCodes"].append("test-only")
    assert "test-only" not in other["reasonCodes"]
