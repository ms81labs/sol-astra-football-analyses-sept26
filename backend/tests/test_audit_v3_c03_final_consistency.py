"""C03 publication validates relationships, not merely valid individual JSON files."""
from __future__ import annotations

import copy

import pytest

from backend.app.generations import GenerationRecoveryRequired
from backend.tests.test_audit_v3_c03_reports import _store

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("mismatch", ["other_known_controller", "missing_controller", "assignment_clock", "missing_assignment", "noncontrolled_team"])
def test_inconsistent_accepted_state_cannot_become_current(tmp_path, mismatch):
    storage, mid = _store(tmp_path)
    old = storage.current_generation(mid).generationId
    frames = storage.load_frames(mid)
    summary, assignments, formations, shots = storage.load_analytics(mid)
    events = storage.load_events(mid)
    state = copy.deepcopy(storage.load_analysis_artifact(mid, "accepted_match_state"))
    index = next(i for i, item in enumerate(state["frames"]) if item["mode"] == "controlled_possession")
    if mismatch == "other_known_controller":
        frame = frames[index]
        alternatives = [(p.id, team) for team, players in (("my_team", frame.myTeam), ("enemy", frame.enemies))
                        for p in players if p.id != state["frames"][index]["controllingTrackId"]]
        assert alternatives, "The counterexample needs another real, published identity"
        track, team = alternatives[0]
        state["frames"][index].update(controllingTrackId=track, controllingTeam=team)
    elif mismatch == "missing_controller":
        state["frames"][index]["controllingTrackId"] = None
    elif mismatch == "assignment_clock":
        assignments[index] = assignments[index].model_copy(update={"timestamp": assignments[index].timestamp + 0.25})
    elif mismatch == "noncontrolled_team":
        state["frames"][index].update(mode="unknown", controllingTrackId=None, controllingTeam="my_team")
        assignments[index] = assignments[index].model_copy(update={"team": "unassigned", "trackId": None})
    else:
        assignments = assignments[:-1]

    with pytest.raises(GenerationRecoveryRequired, match="schema validation"):
        storage.publish_generation(mid, frames=frames, summary=summary, assignments=assignments,
                                   formation_timeline=formations, shots=shots, events=events,
                                   correction_head="consistency-probe", accepted_match_state=state,
                                   expected_parent=old)
    assert storage.current_generation(mid).generationId == old
