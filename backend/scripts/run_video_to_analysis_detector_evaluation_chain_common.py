from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from backend.scripts.football_external_real_eval_chain_common import (
    DEFAULT_CANDIDATE_NAME,
    candidate_root,
    load_json,
    reset_output,
    standard_false_flags,
    utc_now_iso,
    write_json,
    write_outcome,
)


def attempt_plan(name: str, repair: str, blocker: str) -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {"attemptNumber": 1, "attemptApproachFamily": name, "successCriteria": ["write generated truth for this gated step"], "failureAdaptation": "If source truth is missing, route back to the source batch."},
            {"attemptNumber": 2, "attemptApproachFamily": repair, "successCriteria": ["repair only evidence references and contracts"], "failureAdaptation": "If still unsafe, write blocker truth."},
            {"attemptNumber": 3, "attemptApproachFamily": blocker, "successCriteria": ["write blocker truth", "select exactly one next family"], "failureAdaptation": "Route to source, repair, or next gated step."},
        ],
    }


def false_summary(**extra: Any) -> dict[str, Any]:
    return {**standard_false_flags(), **extra}


def root_for(storage_root: Path, candidate_name: str = DEFAULT_CANDIDATE_NAME) -> Path:
    return candidate_root(Path(storage_root), candidate_name)


def ready_summary(payload: dict[str, Any] | None, *, required_true: tuple[str, ...]) -> bool:
    return bool(
        isinstance(payload, dict)
        and payload.get("goalAchieved") is True
        and payload.get("primaryBlocker") is None
        and all(payload.get(key) is True for key in required_true)
    )


def write_simple_outcome(
    *,
    output_root: Path,
    summary_filename: str,
    summary: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
    title: str,
) -> dict[str, Any]:
    return write_outcome(
        output_root=output_root,
        summary_filename=summary_filename,
        summary=summary,
        artifacts=artifacts,
        markdown_title=title,
    )


def render_report_html(view_model: dict[str, Any]) -> str:
    rows = "\n".join(
        f"<li><strong>{escape(str(row.get('label')))}</strong>: {escape(str(row.get('value')))}</li>"
        for row in view_model.get("scoreboard", [])
        if isinstance(row, dict)
    )
    return "\n".join(
        [
            "<!doctype html>",
            "<html lang=\"en\">",
            "<head><meta charset=\"utf-8\"><title>Detector Evaluation Report</title></head>",
            "<body>",
            "<h1>Detector Evaluation Report</h1>",
            f"<p>{escape(str(view_model.get('subtitle', '')))}</p>",
            f"<ul>{rows}</ul>",
            "</body>",
            "</html>",
            "",
        ]
    )


def write_json_artifact(path: Path, payload: dict[str, Any]) -> None:
    write_json(path, payload)


__all__ = [
    "DEFAULT_CANDIDATE_NAME",
    "attempt_plan",
    "false_summary",
    "load_json",
    "ready_summary",
    "render_report_html",
    "reset_output",
    "root_for",
    "utc_now_iso",
    "write_json_artifact",
    "write_simple_outcome",
]
