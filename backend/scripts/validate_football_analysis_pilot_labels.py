"""Validate locked, independently produced labels for one frozen pilot task."""

from __future__ import annotations

from backend.app.pilot_labels import (
    SCHEMA_VERSION as SCHEMA_VERSION,
    TEAMS as TEAMS,
    _RFC3339_UTC as _RFC3339_UTC,
    parse_unique_json as parse_unique_json,
    _mapping as _mapping,
    _exact_keys as _exact_keys,
    _bbox as _bbox,
    _pitch_position as _pitch_position,
    parse_utc_timestamp as parse_utc_timestamp,
    validate_label_payload as validate_label_payload,
)

import argparse
import json
from pathlib import Path
from typing import Mapping


















def audit_label_set(tasks_payload: Mapping[str, object], *, repo_root: Path) -> dict[str, object]:
    """Validate every declared task and count only complete locked label files."""

    tasks = tasks_payload.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("annotation task manifest must contain a tasks array")
    completed_tasks = completed_frames = 0
    completed_seconds = 0.0
    errors: list[dict[str, str]] = []
    root = repo_root.resolve()
    for raw_task in tasks:
        task = _mapping(raw_task, "task")
        task_id = str(task.get("taskId", ""))
        relative = task.get("labelOutputPath")
        if not isinstance(relative, str) or not relative:
            errors.append({"taskId": task_id, "error": "labelOutputPath is missing"})
            continue
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            errors.append({"taskId": task_id, "error": "labelOutputPath must stay inside repo root"})
            continue
        if not path.is_file():
            errors.append({"taskId": task_id, "error": f"label file is missing: {relative}"})
            continue
        try:
            payload = parse_unique_json(path.read_bytes())
            result = validate_label_payload(task, _mapping(payload, "label payload"))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append({"taskId": task_id, "error": str(exc)})
            continue
        completed_tasks += 1
        completed_frames += int(result["frameCount"])
        completed_seconds += float(result["durationSeconds"])
    completed_seconds = round(completed_seconds, 9)
    return {
        "taskCount": len(tasks),
        "completedTaskCount": completed_tasks,
        "completedFrameCount": completed_frames,
        "completedDurationSeconds": completed_seconds,
        "completedMinutes": round(completed_seconds / 60, 9),
        "allTasksComplete": completed_tasks == len(tasks) and not errors,
        "errors": errors,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tasks",
        type=Path,
        default=Path("backend/benchmark_suites/football_analysis_pilot_annotation_tasks.json"),
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    summary = audit_label_set(
        json.loads(args.tasks.read_text(encoding="utf-8")),
        repo_root=args.repo_root,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["allTasksComplete"] else 1)
