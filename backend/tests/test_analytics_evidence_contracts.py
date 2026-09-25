"""Compatibility at the match-state evidence parsing boundary."""
from copy import deepcopy
from decimal import Decimal

import pytest

from backend.app.analytics import (
    _ball_rows_by_frame,
    _normalize_match_state_evidence,
    build_accepted_match_state,
)
from backend.app.schemas import BallOwnership, FrameData


class _IntValue:
    def __int__(self):
        return 7


class _FloatValue:
    def __float__(self):
        return 12.5


class _LegacySequence:
    """Python's index-based iteration fallback, without __iter__."""
    def __init__(self, values):
        self.values = values

    def __getitem__(self, index):
        return self.values[index]


def _ball_rows(rows):
    return _ball_rows_by_frame({"observedBall": {"rows": rows}}, "observedBall")


@pytest.mark.parametrize("payload", [None, [], "bad", {}, {"observedBall": None},
                                    {"observedBall": []}, {"observedBall": {}},
                                    {"observedBall": {"rows": ()}}])
def test_ball_parser_ignores_unsupported_container_shapes(payload):
    assert _ball_rows_by_frame(payload, "observedBall") == {}


@pytest.mark.parametrize("field", ["Frame_ID", "X", "Y", "Conf"])
@pytest.mark.parametrize("value", [None, "bad", [], {}])
def test_ball_parser_skips_only_the_invalid_row(field, value):
    row = {"Frame_ID": 7, "X": 12.5, "Y": 45, "Conf": 0.7}
    invalid = {**row, field: value}
    rows = [None, invalid, row]
    snapshot = deepcopy(rows)
    assert _ball_rows(rows) == {7: {"x": 12.5, "y": 45.0, "confidence": 0.7}}
    assert rows == snapshot


@pytest.mark.parametrize("field", ["Frame_ID", "X", "Y"])
def test_ball_parser_skips_missing_required_values(field):
    row = {"Frame_ID": 7, "X": 12.5, "Y": 45}
    row.pop(field)
    assert _ball_rows([row]) == {}


@pytest.mark.parametrize("value,expected", [(7, 7), ("7", 7), (b"7", 7),
                                          (7.9, 7), (True, 1), (Decimal("7.9"), 7),
                                          (_IntValue(), 7)])
def test_frame_id_keeps_builtin_coercion_in_both_parsers(value, expected):
    assert _ball_rows([{"Frame_ID": value, "X": 1, "Y": 2}]) == {
        expected: {"x": 1.0, "y": 2.0, "confidence": 0.0}
    }
    evidence = {"frameId": value, "extra": "retained"}
    normalized = _normalize_match_state_evidence({"frames": [evidence]})
    assert normalized == {expected: evidence}
    assert normalized[expected] is not evidence


@pytest.mark.parametrize("value,expected", [(12, 12.0), ("12.5", 12.5), (b"12.5", 12.5),
                                          (True, 1.0), (Decimal("12.5"), 12.5),
                                          (_FloatValue(), 12.5), (float("inf"), float("inf"))])
def test_ball_coordinates_keep_float_coercion_without_new_range_policy(value, expected):
    assert _ball_rows([{"Frame_ID": 7, "X": value, "Y": value, "Conf": value}]) == {
        7: {"x": expected, "y": expected, "confidence": expected}
    }


def test_ball_parser_retains_nonfinite_coordinates_and_last_duplicate():
    rows = [{"Frame_ID": 7, "X": 1, "Y": 2},
            {"Frame_ID": "7", "X": "nan", "Y": "-inf", "Conf": -1}]
    result = _ball_rows(rows)[7]
    assert result["x"] != result["x"]
    assert result["y"] == float("-inf")
    assert result["confidence"] == -1.0


@pytest.mark.parametrize("error_type", [TypeError, ValueError, OverflowError, RuntimeError])
def test_conversion_exceptions_keep_the_existing_catch_boundary(error_type):
    error = error_type("controlled conversion failure")

    class BadInteger:
        def __int__(self):
            raise error

    for parse in (
        lambda: _ball_rows([{"Frame_ID": BadInteger(), "X": 1, "Y": 2}]),
        lambda: _normalize_match_state_evidence({"frames": [{"frameId": BadInteger()}]}),
    ):
        if error_type in (TypeError, ValueError):
            assert parse() == {}
        else:
            with pytest.raises(error_type) as caught:
                parse()
            assert caught.value is error


@pytest.mark.parametrize("stop_field", ["Frame_ID", "X", "Y", None])
def test_ball_parser_preserves_lookup_and_conversion_order(stop_field):
    calls = []

    class Integer:
        def __int__(self):
            calls.append("int")
            return 7

    class Number:
        def __float__(self):
            calls.append("float")
            return 2.0

    class Row(dict):
        def get(self, key, default=None):
            calls.append(key)
            return None if key == stop_field else super().get(key, default)

    row = Row(Frame_ID=Integer(), X=Number(), Y=Number(), Conf=Number())
    result = _ball_rows([row])
    expected = ["Frame_ID", "int", "X", "float", "Y", "float", "Conf", "float"]
    if stop_field is not None:
        expected = expected[:expected.index(stop_field) + 1]
        assert result == {}
    else:
        assert result == {7: {"x": 2.0, "y": 2.0, "confidence": 2.0}}
    assert calls == expected


@pytest.mark.parametrize("payload", [None, [], {}, {"frames": None}, {"frames": ()},
                                    {"frames": [None, {}, {"frameId": None}, {"frameId": "bad"}]}])
def test_evidence_parser_ignores_unsupported_shapes(payload):
    assert _normalize_match_state_evidence(payload) == {}


def test_evidence_parser_preserves_last_duplicate_and_shallow_copy():
    nested = {"untouched": [1, 2]}
    row = {"frameId": "7", "reasonCodes": [" a "], "extra": nested}
    result = _normalize_match_state_evidence({"frames": [{"frameId": 7}, row]})
    assert result == {7: row}
    assert result[7] is not row
    assert result[7]["extra"] is nested


def _state_with_codes(codes):
    return build_accepted_match_state(
        [FrameData(frameId=7, timestamp=0)],
        [BallOwnership(frameId=7, timestamp=0, team="unassigned")],
        match_state_evidence={"frames": [{"frameId": 7, "reasonCodes": codes}]},
    )[0]


@pytest.mark.parametrize("factory,expected", [
    (lambda: [" a ", "", " ", 0, None, "b", "b"], [" a ", "b", "b"]),
    (lambda: (" a ", "", "b"), [" a ", "b"]),
    (lambda: {" a ": 1, "": 2, "b": 3}, [" a ", "b"]),
    (lambda: "ab c", ["a", "b", "c"]),
    (lambda: b"abc", []),
    (lambda: iter([" a ", None, "b"]), [" a ", "b"]),
    (lambda: _LegacySequence([" a ", None, "b"]), [" a ", "b"]),
])
def test_reason_codes_preserve_iteration_filtering_order_and_duplicates(factory, expected):
    assert _state_with_codes(factory()).reasonCodes == expected


@pytest.mark.parametrize("codes", [None, 1, 1.5, True, object()])
def test_noniterable_reason_codes_remain_errors_not_empty_evidence(codes):
    with pytest.raises(TypeError) as caught:
        _state_with_codes(codes)
    assert str(caught.value) == f"'{type(codes).__name__}' object is not iterable"


def test_broken_reason_code_iterator_propagates_original_exception():
    error = RuntimeError("controlled iterator failure")

    class Broken:
        def __iter__(self):
            raise error

    with pytest.raises(RuntimeError) as caught:
        _state_with_codes(Broken())
    assert caught.value is error


def test_reason_code_iterator_is_consumed_once_without_rewriting_strings():
    codes = iter([" keep spaces ", "again"])
    assert _state_with_codes(codes).reasonCodes == [" keep spaces ", "again"]
    assert list(codes) == []


def test_reason_code_iterator_matches_native_iteration_protocol():
    class ObservedIterator:
        def __init__(self):
            self.iterations = 0
            self.values = iter(["a", "b"])

        def __iter__(self):
            self.iterations += 1
            return self

        def __next__(self):
            return next(self.values)

    reference = ObservedIterator()
    expected = [str(code) for code in reference if isinstance(code, str) and code.strip()]
    codes = ObservedIterator()
    assert _state_with_codes(codes).reasonCodes == expected
    assert codes.iterations == reference.iterations
