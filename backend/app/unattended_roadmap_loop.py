from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ACTIVE_CHECKLIST_RELATIVE_PATH = "docs/superpowers/plans/2026-04-23-promoted-v6-failing-source-robustness-validation.md"
UNATTENDED_SPEC_RELATIVE_PATH = "docs/superpowers/specs/2026-04-23-unattended-roadmap-loop.md"
STATUS_ARTIFACT_RELATIVE_PATH = "backend/storage/automation/unattended_roadmap_loop_status.json"

_BATCH_HEADING_PREFIXES = (
    "Next Bounded Sub-Batch — ",
    "Next Bounded Sub-Batch - ",
    "Next Corrective Sub-Batch — ",
    "Next Corrective Sub-Batch - ",
    "Next Implementation Batch — ",
    "Next Implementation Batch - ",
    "Current Batch — ",
    "Current Batch - ",
    "Batch — ",
    "Batch - ",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_json_dict(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _relative_path_text(path: Path, *, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _batch_name_from_heading(heading: str) -> str | None:
    normalized_heading = heading.strip()
    for prefix in _BATCH_HEADING_PREFIXES:
        if normalized_heading.startswith(prefix):
            return normalized_heading[len(prefix) :].strip()
    return None


def find_first_unchecked_batch(checklist_path: Path) -> str | None:
    current_heading: str | None = None
    for raw_line in Path(checklist_path).read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("## "):
            current_heading = stripped[3:].strip()
            continue
        if current_heading is None or not stripped.startswith("- [ ]"):
            continue
        batch_name = _batch_name_from_heading(current_heading)
        if batch_name:
            return batch_name
    return None


def write_unattended_roadmap_status(
    *,
    repo_root: Path = REPO_ROOT,
    active_checklist_path: Path | None = None,
    active_batch_name: str | None = None,
    queue_item_name: str | None = None,
    attempt_number: int | None = None,
    attempt_budget: int | None = None,
    attempt_approach_family: str | None = None,
    item_status: str | None = None,
    queue_decision: str | None = None,
    loop_status: str,
    current_step: str,
    stop_reason: str | None = None,
    next_expected_action: str | None = None,
    last_verification_summary: object | None = None,
    status_path: Path | None = None,
) -> dict[str, object]:
    repo_root = Path(repo_root)
    resolved_checklist_path = Path(active_checklist_path or repo_root / ACTIVE_CHECKLIST_RELATIVE_PATH)
    resolved_status_path = Path(status_path or repo_root / STATUS_ARTIFACT_RELATIVE_PATH)
    existing = _load_json_dict(resolved_status_path) if resolved_status_path.exists() else {}

    resolved_batch_name = active_batch_name or find_first_unchecked_batch(resolved_checklist_path)
    if next_expected_action is None:
        if resolved_batch_name:
            next_expected_action = f"Continue with {resolved_batch_name} from the active checklist."
        else:
            next_expected_action = "Inspect the active checklist and choose the next truthful action."

    payload: dict[str, object] = {
        "activeChecklistPath": _relative_path_text(resolved_checklist_path, repo_root=repo_root),
        "activeBatchName": resolved_batch_name,
        "queueItemName": queue_item_name or existing.get("queueItemName") or resolved_batch_name,
        "attemptNumber": (
            attempt_number
            if attempt_number is not None
            else existing.get("attemptNumber")
        ),
        "attemptBudget": (
            attempt_budget
            if attempt_budget is not None
            else existing.get("attemptBudget")
        ),
        "attemptApproachFamily": (
            attempt_approach_family
            if attempt_approach_family is not None
            else existing.get("attemptApproachFamily")
        ),
        "itemStatus": item_status or existing.get("itemStatus"),
        "queueDecision": queue_decision or existing.get("queueDecision"),
        "loopStatus": loop_status,
        "currentStep": current_step,
        "startedAt": existing.get("startedAt") or _utc_now_iso(),
        "updatedAt": _utc_now_iso(),
        "stopReason": stop_reason,
        "nextExpectedAction": next_expected_action,
        "lastVerificationSummary": (
            last_verification_summary
            if last_verification_summary is not None
            else existing.get("lastVerificationSummary")
        ),
    }
    _write_json(resolved_status_path, payload)
    return payload


__all__ = [
    "ACTIVE_CHECKLIST_RELATIVE_PATH",
    "REPO_ROOT",
    "STATUS_ARTIFACT_RELATIVE_PATH",
    "UNATTENDED_SPEC_RELATIVE_PATH",
    "find_first_unchecked_batch",
    "write_unattended_roadmap_status",
]
