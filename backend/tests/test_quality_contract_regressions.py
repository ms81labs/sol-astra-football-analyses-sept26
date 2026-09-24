"""Regression coverage for the independently reproduced September quality review."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from backend.app.llm import build_prompt
from backend.app.run_benchmarks import (
    MatchBenchmarkSummary,
    SelectedClusterBenchmarkSummary,
    _selected_cluster_summary_from_benchmark,
)


MATCH_STATE_METRICS = {
    "acceptedMatchStateFrames": 13,
    "acceptedMatchStateCoverageRatio": 0.65,
    "visibleStateFrames": 4,
    "inferredStateFrames": 3,
    "hiddenStateFrames": 2,
    "controlledStateFrames": 5,
    "hiddenControlledStateFrames": 1,
    "restartOrOutStateFrames": 6,
    "stateContinuityAppliedFrames": 7,
    "matchStateModeCounts": {"visible": 4, "hidden": 2},
}


@pytest.mark.parametrize("field,expected", MATCH_STATE_METRICS.items())
def test_selected_cluster_conversion_preserves_match_state_metrics_in_json(field, expected):
    summary = MatchBenchmarkSummary(
        matchId="quality-regression", inputMode="video", matchStatus="ready",
        requiresTeamSelection=False, **MATCH_STATE_METRICS,
    )
    selected = _selected_cluster_summary_from_benchmark(2, summary)
    payload = json.loads(selected.model_dump_json())
    assert payload.get(field) == expected
    restored = SelectedClusterBenchmarkSummary.model_validate_json(selected.model_dump_json())
    assert getattr(restored, field) == expected


@pytest.mark.parametrize("model,required", [
    (MatchBenchmarkSummary, {"matchId": "quality-regression", "inputMode": "video",
                             "matchStatus": "ready", "requiresTeamSelection": False}),
    (SelectedClusterBenchmarkSummary, {"clusterId": 2, "requiresTeamSelection": False}),
])
def test_benchmark_contract_rejects_undeclared_metric_names(model, required):
    with pytest.raises(ValidationError) as error:
        model(**required, acceptedMatchStateFramez=5)
    assert error.value.errors()[0]["type"] == "extra_forbidden"


def test_selected_cluster_match_state_defaults_are_zero_and_not_shared():
    first = SelectedClusterBenchmarkSummary(clusterId=1, requiresTeamSelection=False)
    second = SelectedClusterBenchmarkSummary(clusterId=2, requiresTeamSelection=False)
    for field in MATCH_STATE_METRICS:
        if field != "matchStateModeCounts":
            assert getattr(first, field) == 0
    first.matchStateModeCounts["visible"] = 1
    assert second.matchStateModeCounts == {}


@pytest.mark.parametrize("analysis_type", ["tactical_report", "drills"])
@pytest.mark.parametrize("direction,coordinate_change", [
    ("left_to_right", "increasing"), ("right_to_left", "decreasing"),
])
def test_legacy_prompt_explains_attack_direction_coordinates(analysis_type, direction, coordinate_change):
    prompt = build_prompt(analysis_type, [], attack_direction=direction)
    assert f"My team attacks {direction} toward {coordinate_change} x" in prompt
    assert "the opponent attacks the opposite direction" in prompt
    context = json.loads(prompt.split("Context: ", 1)[1])
    assert context["attackDirection"] == direction


def test_approved_evidence_prompt_keeps_its_source_bound_contract():
    prompt = build_prompt("tactical_report", [], attack_direction="right_to_left", approved_evidence={})
    assert "Attack direction: right_to_left." in prompt
    assert "server-approved aliases" in prompt
    assert "My team attacks" not in prompt
