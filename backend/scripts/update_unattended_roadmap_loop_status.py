# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.unattended_roadmap_loop import ACTIVE_CHECKLIST_RELATIVE_PATH
from backend.app.unattended_roadmap_loop import STATUS_ARTIFACT_RELATIVE_PATH
from backend.app.unattended_roadmap_loop import write_unattended_roadmap_status


def _resolve_repo_path(value: str, *, repo_root: Path) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return repo_root / candidate


def _parse_verification_summary(raw_value: str | None) -> object | None:
    if raw_value is None:
        return None
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        return raw_value


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the unattended roadmap loop heartbeat artifact.")
    parser.add_argument("--loop-status", required=True)
    parser.add_argument("--current-step", required=True)
    parser.add_argument("--active-checklist-path", default=ACTIVE_CHECKLIST_RELATIVE_PATH)
    parser.add_argument("--active-batch-name")
    parser.add_argument("--queue-item-name")
    parser.add_argument("--attempt-number", type=int)
    parser.add_argument("--attempt-budget", type=int)
    parser.add_argument("--attempt-approach-family")
    parser.add_argument("--item-status")
    parser.add_argument("--queue-decision")
    parser.add_argument("--stop-reason")
    parser.add_argument("--next-expected-action")
    parser.add_argument("--last-verification-summary")
    parser.add_argument("--status-path", default=STATUS_ARTIFACT_RELATIVE_PATH)
    args = parser.parse_args()

    payload = write_unattended_roadmap_status(
        repo_root=REPO_ROOT,
        active_checklist_path=_resolve_repo_path(args.active_checklist_path, repo_root=REPO_ROOT),
        active_batch_name=args.active_batch_name,
        queue_item_name=args.queue_item_name,
        attempt_number=args.attempt_number,
        attempt_budget=args.attempt_budget,
        attempt_approach_family=args.attempt_approach_family,
        item_status=args.item_status,
        queue_decision=args.queue_decision,
        loop_status=args.loop_status,
        current_step=args.current_step,
        stop_reason=args.stop_reason,
        next_expected_action=args.next_expected_action,
        last_verification_summary=_parse_verification_summary(args.last_verification_summary),
        status_path=_resolve_repo_path(args.status_path, repo_root=REPO_ROOT),
    )
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
