from __future__ import annotations

from copy import deepcopy
import json

import pytest

from backend.scripts.validate_football_analysis_pilot_labels import audit_label_set, validate_label_payload


TASK = {
    "taskId": "match-01",
    "videoSha256": "a" * 64,
    "sourceWidth": 100,
    "sourceHeight": 50,
    "sourceFps": 25.0,
    "sourceStartFrame": 10,
    "sourceEndFrameExclusive": 13,
    "evaluationFrameStep": 1,
    "evaluationFrameCount": 3,
}


def _frame(frame_id: int) -> dict[str, object]:
    return {
        "frameId": frame_id,
        "ball": {"visibility": "visible", "bbox": [40, 20, 42, 22], "pitchPositionMeters": None},
        "entities": [
            {"trackId": "home-7", "kind": "player", "team": "home", "bbox": [10, 5, 20, 30], "pitchPositionMeters": None},
            {"trackId": "ref-1", "kind": "referee", "team": "unknown", "bbox": [50, 5, 60, 30], "pitchPositionMeters": None},
        ],
        "possession": {"state": "observed", "team": "home", "trackId": "home-7"},
    }


def _payload() -> dict[str, object]:
    return {
        "schemaVersion": "football_analysis_pilot_labels_v3",
        "taskId": "match-01",
        "sourceVideoSha256": "a" * 64,
        "independentAnnotation": True,
        "pipelineOutputUsed": False,
        "annotatorId": "reviewer-1",
        "lockedAt": "2026-09-14T23:00:00Z",
        "pitchReference": None,
        "frames": [_frame(frame_id) for frame_id in range(10, 13)],
        "events": [
            {
                "eventId": "pass-1",
                "type": "pass",
                "startFrame": 10,
                "endFrameExclusive": 12,
                "team": "home",
            }
        ],
    }


def test_accepts_complete_independent_locked_task_labels() -> None:
    assert validate_label_payload(TASK, _payload()) == {
        "frameCount": 3,
        "eventCount": 1,
        "pitchPositionCount": 0,
        "durationSeconds": 0.12,
    }


@pytest.mark.parametrize("locked_at", ["20260914T230000Z", "2026-09-14Z"])
def test_rejects_a_non_rfc3339_label_lock_timestamp(locked_at: str) -> None:
    payload = _payload()
    payload["lockedAt"] = locked_at
    with pytest.raises(ValueError, match="RFC3339"):
        validate_label_payload(TASK, payload)


def test_rejects_a_future_label_lock_timestamp() -> None:
    payload = _payload()
    payload["lockedAt"] = "9999-01-01T00:00:00Z"
    with pytest.raises(ValueError, match="future"):
        validate_label_payload(TASK, payload)


def test_accepts_only_declared_evaluation_frames_and_keeps_full_task_duration() -> None:
    task = {
        **TASK,
        "sourceStartFrame": 10,
        "sourceEndFrameExclusive": 25,
        "evaluationFrameStep": 5,
        "evaluationFrameCount": 3,
    }
    payload = _payload()
    payload["frames"] = [_frame(frame_id) for frame_id in (10, 15, 20)]

    assert validate_label_payload(task, payload) == {
        "frameCount": 3,
        "eventCount": 1,
        "pitchPositionCount": 0,
        "durationSeconds": 0.6,
    }


def test_accepts_pitch_positions_only_with_independent_reference_provenance() -> None:
    payload = _payload()
    payload["pitchReference"] = {
        "sourceId": "official-gsr-match-117092",
        "sha256": "b" * 64,
        "associationMethod": "predeclared_identity",
    }
    payload["frames"][0]["ball"]["pitchPositionMeters"] = [52.5, 34.0]
    payload["frames"][0]["entities"][0]["pitchPositionMeters"] = [30.0, 20.0]

    assert validate_label_payload(TASK, payload)["pitchPositionCount"] == 2


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda payload: payload.update(taskId="other"), "taskId"),
        (lambda payload: payload.update(sourceVideoSha256="b" * 64), "sourceVideoSha256"),
        (lambda payload: payload.update(independentAnnotation=False), "independentAnnotation"),
        (lambda payload: payload.update(pipelineOutputUsed=True), "pipelineOutputUsed"),
        (lambda payload: payload["frames"].pop(), "declared evaluation frames"),
        (lambda payload: payload["frames"][0]["ball"].update(bbox=None), "visible ball requires bbox"),
        (lambda payload: payload["frames"][0]["entities"][0].update(bbox=[-1, 0, 2, 3]), "inside 100x50"),
        (lambda payload: payload["frames"][0]["possession"].update(trackId="missing"), "possession trackId"),
        (lambda payload: payload["frames"][0]["ball"].update(pitchPositionMeters=[1.0, 2.0]), "pitchReference"),
        (lambda payload: payload.update(pitchReference={"sourceId": "x", "sha256": "bad", "associationMethod": "predeclared_identity"}), "pitchReference sha256"),
        (lambda payload: payload["events"][0].update(endFrameExclusive=14), "event frame range"),
    ],
)
def test_rejects_labels_that_cannot_support_acceptance_metrics(mutate, message: str) -> None:
    payload = deepcopy(_payload())
    mutate(payload)

    with pytest.raises(ValueError, match=message):
        validate_label_payload(TASK, payload)


def test_audits_missing_and_valid_tasks_without_counting_partial_minutes(tmp_path) -> None:
    valid_path = tmp_path / "valid.json"
    valid_path.write_text(json.dumps(_payload()), encoding="utf-8")
    tasks = {
        "tasks": [
            {**TASK, "labelOutputPath": "valid.json"},
            {**TASK, "taskId": "match-02", "labelOutputPath": "missing.json"},
        ]
    }

    assert audit_label_set(tasks, repo_root=tmp_path) == {
        "taskCount": 2,
        "completedTaskCount": 1,
        "completedFrameCount": 3,
        "completedDurationSeconds": 0.12,
        "completedMinutes": 0.002,
        "allTasksComplete": False,
        "errors": [{"taskId": "match-02", "error": "label file is missing: missing.json"}],
    }


def test_audit_does_not_count_a_label_with_duplicate_attestation_keys(tmp_path) -> None:
    raw = json.dumps(_payload()).replace('"pipelineOutputUsed": false', '"pipelineOutputUsed": true, "pipelineOutputUsed": false')
    (tmp_path / "label.json").write_text(raw, encoding="utf-8")
    summary = audit_label_set({"tasks": [{**TASK, "labelOutputPath": "label.json"}]}, repo_root=tmp_path)
    assert summary["completedTaskCount"] == 0
    assert "duplicate" in summary["errors"][0]["error"]


def test_audit_rejects_label_path_outside_repository(tmp_path) -> None:
    tasks = {"tasks": [{**TASK, "labelOutputPath": "../escape.json"}]}

    assert audit_label_set(tasks, repo_root=tmp_path)["errors"] == [
        {"taskId": "match-01", "error": "labelOutputPath must stay inside repo root"}
    ]
