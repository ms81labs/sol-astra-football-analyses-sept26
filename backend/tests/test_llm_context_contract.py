"""Provider schema dispatch and local prompt context contracts; no provider calls."""
from copy import deepcopy
import json

import pytest
from pydantic import ValidationError

from backend.app.llm import _build_match_context, _validate_provider_output, build_prompt
from backend.app.schemas import DetectedEvent, FormationSegment, FrameData, MatchSummary, ShotAnalytics


def _summary(possession):
    return MatchSummary(possession=possession, formation="4-3-3",
                        myTeamDistance=None, enemyDistance=None,
                        myTeamTopSpeed=None, enemyTopSpeed=None,
                        myTeamSprints=None, enemySprints=None)


def _report():
    return {"attacking": "attack", "defensive": "defend", "pressing": "press",
            "key_player": 0, "weaknesses": "unknown", "rating": 5.0, "summary": "review"}


@pytest.mark.parametrize("kind,payload", [
    ("tactical_report", _report()),
    ("drills", {"drills": [], "focus_area": "shape"}),
    ("drills", {"drills": [{"name": "one", "objective": "control", "setup": "pairs", "duration": "5 min"}],
                "focus_area": "control", "evidence": [], "player_focus": {}}),
])
def test_validation_keeps_only_explicit_fields_without_mutating_input(kind, payload):
    before = deepcopy(payload)
    result = _validate_provider_output(kind, payload)
    assert result == before and payload == before
    assert result is not payload
    assert "event_summary" not in result


@pytest.mark.parametrize("field,value", [
    ("rating", "5"), ("rating", True), ("rating", -0.1), ("rating", 10.1),
    ("rating", float("inf")), ("rating", float("nan")), ("key_player", True),
    ("attacking", 3), ("unexpected", "discard me"),
    ("player_focus", {"topCreator": {"trackId": 1, "team": "my_team", "extra": True}}),
    ("event_summary", {"eventCounts": {"pass": "1"}}),
])
def test_tactical_validation_does_not_coerce_or_silently_drop_bad_fields(field, value):
    payload = _report()
    payload[field] = value
    with pytest.raises(ValidationError):
        _validate_provider_output("tactical_report", payload)


@pytest.mark.parametrize("kind,payload", [
    ("tactical_report", {}), ("drills", _report()),
    ("drills", {"focus_area": "control"}), ("drills", {"drills": [], "focus_area": None}),
    ("tactical_report", None), ("drills", []),
])
def test_schema_choice_and_required_fields_remain_enforced(kind, payload):
    with pytest.raises(ValidationError):
        _validate_provider_output(kind, payload)


def test_unknown_legacy_schema_is_a_key_error_not_a_default_report():
    with pytest.raises(KeyError) as caught:
        _validate_provider_output("unsupported", _report())
    assert caught.value.args == ("unsupported",)


@pytest.mark.parametrize("kind", ["tactical_report", "drills", "unsupported"])
def test_versioned_draft_is_validated_before_legacy_task_dispatch(kind):
    draft = {"schemaVersion": "report_draft_v1", "matchId": "match", "generationId": "gen",
             "taskType": "tactical_report", "interpretation": "opinion"}
    assert _validate_provider_output(kind, draft) == draft
    with pytest.raises(ValidationError):
        _validate_provider_output(kind, {**draft, "unexpected": True})


@pytest.mark.parametrize("size,selected", [
    (0, []), (1, [0]), (6, [0, 1, 2, 3, 4, 5]),
    (7, [0, 1, 2, 3, 4, 5, 6]), (12, [0, 2, 4, 6, 8, 10]),
    (13, [0, 2, 4, 6, 8, 10, 12]), (20, [0, 3, 6, 9, 12, 15, 18]),
])
def test_frame_sampling_keeps_existing_stride_and_omits_absent_context(size, selected):
    frames = [FrameData(frameId=i, timestamp=i / 2) for i in range(size)]
    before = deepcopy(frames)
    context = _build_match_context(frames, None, None, None, None)
    assert list(context) == ["sampledFrames"]
    assert [frame["frameId"] for frame in context["sampledFrames"]] == selected
    assert frames == before
    if frames:
        context["sampledFrames"][0]["frameId"] = 10000
        assert frames[0].frameId == 0


def test_empty_context_collections_are_present_but_do_not_invent_player_focus():
    context = _build_match_context([], None, [], [], [])
    assert list(context) == ["sampledFrames", "eventSummary", "recentEvents", "formationTimeline", "shots"]
    assert context["recentEvents"] == context["formationTimeline"] == context["shots"] == []
    assert context["eventSummary"]["eventCounts"] == {}
    assert "summary" not in context and "matchSignals" not in context and "playerFocus" not in context


def test_full_context_keeps_input_order_limits_and_independent_serialized_values():
    events = [DetectedEvent(type="pass", frameId=i, timestamp=float(30 - i), team="my_team",
                            fromTrackId=0, toTrackId=7, description=f"pass-{i}") for i in range(15)]
    shots = [ShotAnalytics(frameId=i, timestamp=float(i), team="my_team", playerId=7,
                           x=90.0, y=50.0, inBox=True, xg=0.1, distanceToGoal=10.0, angleDegrees=30.0)
             for i in range(12)]
    formations = [FormationSegment(startFrameId=i, endFrameId=i + 1, startTimestamp=float(i),
                                   endTimestamp=float(i + 1), formation="4-3-3") for i in range(5)]
    summary = _summary(0)
    before = deepcopy((events, shots, formations, summary))
    context = _build_match_context([], summary, events, formations, shots)
    assert list(context) == ["sampledFrames", "summary", "eventSummary", "recentEvents", "formationTimeline",
                             "shots", "playerFocus", "matchSignals"]
    assert [event["frameId"] for event in context["recentEvents"]] == list(range(12))
    assert [shot["frameId"] for shot in context["shots"]] == list(range(10))
    assert len(context["formationTimeline"]) == 5
    assert context["matchSignals"]["recentFormations"] == [
        {"formation": "4-3-3", "startTimestamp": float(i), "endTimestamp": float(i + 1)} for i in [2, 3, 4]]
    assert context["eventSummary"]["eventCounts"]["pass"] == 15
    assert context["summary"]["possession"] == 0
    assert (events, shots, formations, summary) == before
    context["recentEvents"][0]["description"] = "caller edit"
    context["summary"]["possession"] = 99
    assert events[0].description == "pass-0" and summary.possession == 0


@pytest.mark.parametrize("kind", ["tactical_report", "drills"])
@pytest.mark.parametrize("direction,word", [("left_to_right", "increasing"), ("right_to_left", "decreasing")])
def test_legacy_prompts_preserve_direction_explanation_and_context(kind, direction, word):
    prompt = build_prompt(kind, [], attack_direction=direction)
    assert f"My team attacks {direction} toward {word} x" in prompt
    context = json.loads(prompt.split("Context: ", 1)[1])
    assert context == {"sampledFrames": [], "attackDirection": direction}


def test_approved_evidence_prompt_does_not_pick_up_legacy_context():
    evidence = {"matchId": "match", "generationId": "gen", "aliases": {"frame-a": {"kind": "frame"}}}
    before = deepcopy(evidence)
    prompt = build_prompt("tactical_report", [], summary=_summary(97), approved_evidence=evidence)
    assert json.loads(prompt.split("Approved evidence (including source-bound sampled frames): ", 1)[1]) == evidence
    assert "My team attacks" not in prompt and '"possession": 97' not in prompt
    assert evidence == before
