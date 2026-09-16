from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

import backend.app.unattended_roadmap_loop as unattended_roadmap_loop


REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_active_checklist_contains_unattended_loop_contract_and_current_batch() -> None:
    checklist_path = REPO_ROOT / unattended_roadmap_loop.ACTIVE_CHECKLIST_RELATIVE_PATH

    text = checklist_path.read_text(encoding="utf-8")

    assert "## Unattended Loop Contract" in text
    assert "first unchecked task in this checklist" in text
    assert "Do not ask for approval" in text
    assert "generated artifacts" in text
    assert (
        unattended_roadmap_loop.find_first_unchecked_batch(checklist_path)
        == "v7_1_positive_diversity_manual_review_expansion_v2"
    )


def test_unattended_spec_documents_prompt_and_limitations() -> None:
    spec_path = REPO_ROOT / unattended_roadmap_loop.UNATTENDED_SPEC_RELATIVE_PATH

    text = spec_path.read_text(encoding="utf-8")

    assert "Continue from docs/superpowers/plans/2026-04-23-promoted-v6-failing-source-robustness-validation.md." in text
    assert "Read memorybank/README.md for the memorybank reading order." in text
    assert "Read memorybank/activeContext.md, memorybank/currentRoadmap.md, and memorybank/progress.md." in text
    assert "generated artifacts first" in text
    assert "Do not trust top-level summary shortcuts over the generated diagnosis surfaces." in text
    assert "Work the first unchecked batch in order." in text
    assert "Do not ask for approval; make reasonable assumptions." in text
    assert "promoted_touchline_detector_candidate_retention_delta_analysis_v1" in text
    assert "touchline_detector_candidate_v6_accepted_signal_retention_fix_v1" in text
    assert "accepted_signal_retention_collapse" in text
    assert "acceptedRetentionRatio = 0.099" in text
    assert "controlledRetentionRatio = 0.133" in text
    assert "admission_widening" in text
    assert "backend/scripts/runpod_session.py" in text
    assert "/root/.agents/skills/runpodctl/SKILL.md" in text
    assert "does not let the agent self-wake after the session ends" in text
    assert "external re-invocation source" in text


def test_archived_session_handoff_preserves_bootstrap_and_runpod_chronology() -> None:
    handoff_path = REPO_ROOT / "docs/archive/2026-08-19/SESSION-HANDOFF.md"

    text = handoff_path.read_text(encoding="utf-8")

    assert "## Clean Session Bootstrap" in text
    assert "## Authoritative Source Order" in text
    assert "generated artifacts first" in text
    assert "convenience summaries must never override generated truth" in text
    assert "[README.md](/root/WorkSpace/fotball-analyst/memorybank/README.md)" in text
    assert "[activeContext.md](/root/WorkSpace/fotball-analyst/memorybank/activeContext.md)" in text
    assert "[currentRoadmap.md](/root/WorkSpace/fotball-analyst/memorybank/currentRoadmap.md)" in text
    assert "[progress.md](/root/WorkSpace/fotball-analyst/memorybank/progress.md)" in text
    assert "[unattended_roadmap_loop_status.json](/root/WorkSpace/fotball-analyst/backend/storage/automation/unattended_roadmap_loop_status.json)" in text
    assert "Do not trust top-level summary shortcuts over the generated diagnosis surfaces." in text
    assert "[runpod_session.py](/root/WorkSpace/fotball-analyst/backend/scripts/runpod_session.py)" in text
    assert "`/root/.agents/skills/runpodctl/SKILL.md`" in text
    assert "`RUNPOD_API_KEY`" in text
    assert "`~/.runpod/config.toml`" in text
    assert "`~/.config/fotball-analyst/runpod.env`" in text
    assert "always end with `runpodctl pod list --all -o json`" in text


def test_find_first_unchecked_batch_advances_to_the_next_open_batch(tmp_path: Path) -> None:
    checklist_path = tmp_path / "docs" / "superpowers" / "plans" / "active.md"
    _write_text(
        checklist_path,
        "\n".join(
            [
                "# Active Checklist",
                "",
                "## Next Corrective Sub-Batch — completed_batch",
                "",
                "- [x] Finished task",
                "",
                "## Next Corrective Sub-Batch — canonical_proof_summary_contract_v1",
                "",
                "- [ ] First unchecked task",
                "",
            ]
        )
        + "\n",
    )

    assert unattended_roadmap_loop.find_first_unchecked_batch(checklist_path) == "canonical_proof_summary_contract_v1"


def test_write_unattended_roadmap_status_tracks_lifecycle_events(tmp_path: Path) -> None:
    checklist_path = tmp_path / "docs" / "superpowers" / "plans" / "active.md"
    _write_text(
        checklist_path,
        "\n".join(
            [
                "# Active Checklist",
                "",
                "## Next Corrective Sub-Batch — canonical_proof_summary_contract_v1",
                "",
                "- [ ] First unchecked task",
                "",
            ]
        )
        + "\n",
    )
    status_path = tmp_path / "backend" / "storage" / "automation" / "unattended_roadmap_loop_status.json"

    loop_started = unattended_roadmap_loop.write_unattended_roadmap_status(
        repo_root=tmp_path,
        active_checklist_path=checklist_path,
        queue_item_name="canonical_proof_summary_contract_v1",
        attempt_number=0,
        attempt_budget=4,
        item_status="ready",
        queue_decision="begin_current_item",
        loop_status="loop_started",
        current_step="Opened the active checklist.",
        next_expected_action="Start canonical_proof_summary_contract_v1.",
        status_path=status_path,
    )
    batch_started = unattended_roadmap_loop.write_unattended_roadmap_status(
        repo_root=tmp_path,
        active_checklist_path=checklist_path,
        queue_item_name="canonical_proof_summary_contract_v1",
        attempt_number=1,
        attempt_budget=4,
        attempt_approach_family="admission_widening",
        item_status="in_progress",
        queue_decision="continue_current_item",
        loop_status="batch_started",
        current_step="Executing canonical_proof_summary_contract_v1.",
        next_expected_action="Finish the active batch before moving on.",
        status_path=status_path,
    )
    verifying = unattended_roadmap_loop.write_unattended_roadmap_status(
        repo_root=tmp_path,
        active_checklist_path=checklist_path,
        queue_item_name="canonical_proof_summary_contract_v1",
        attempt_number=1,
        attempt_budget=4,
        attempt_approach_family="admission_widening",
        item_status="verifying",
        queue_decision="await_verification",
        loop_status="verifying",
        current_step="Running long verification.",
        next_expected_action="Read verification output before making a success claim.",
        last_verification_summary={"command": "pytest -q", "result": "running"},
        status_path=status_path,
    )
    batch_completed = unattended_roadmap_loop.write_unattended_roadmap_status(
        repo_root=tmp_path,
        active_checklist_path=checklist_path,
        queue_item_name="canonical_proof_summary_contract_v1",
        attempt_number=1,
        attempt_budget=4,
        attempt_approach_family="admission_widening",
        item_status="attempt_completed",
        queue_decision="continue_current_item",
        loop_status="batch_completed",
        current_step="Verified the active batch.",
        next_expected_action="Advance to the next unchecked batch in the same checklist.",
        last_verification_summary={"command": "pytest -q", "exitCode": 0, "summary": "4 passed"},
        status_path=status_path,
    )
    blocked = unattended_roadmap_loop.write_unattended_roadmap_status(
        repo_root=tmp_path,
        active_checklist_path=checklist_path,
        queue_item_name="canonical_proof_summary_contract_v1",
        attempt_number=4,
        attempt_budget=4,
        attempt_approach_family="acceptance_support_gating",
        item_status="exhausted",
        queue_decision="advance_to_next_queue_item",
        loop_status="blocked",
        current_step="Stopped on an unresolved blocker.",
        stop_reason="missing_generated_artifact",
        next_expected_action="Resolve the missing generated artifact before continuing.",
        status_path=status_path,
    )

    payload = json.loads(status_path.read_text(encoding="utf-8"))

    assert status_path.exists()
    assert payload["activeChecklistPath"] == "docs/superpowers/plans/active.md"
    assert payload["activeBatchName"] == "canonical_proof_summary_contract_v1"
    assert payload["queueItemName"] == "canonical_proof_summary_contract_v1"
    assert payload["attemptNumber"] == 4
    assert payload["attemptBudget"] == 4
    assert payload["attemptApproachFamily"] == "acceptance_support_gating"
    assert payload["itemStatus"] == "exhausted"
    assert payload["queueDecision"] == "advance_to_next_queue_item"
    assert payload["loopStatus"] == "blocked"
    assert payload["currentStep"] == "Stopped on an unresolved blocker."
    assert payload["stopReason"] == "missing_generated_artifact"
    assert payload["nextExpectedAction"] == "Resolve the missing generated artifact before continuing."
    assert payload["lastVerificationSummary"] == {"command": "pytest -q", "exitCode": 0, "summary": "4 passed"}

    assert loop_started["startedAt"] == batch_started["startedAt"] == verifying["startedAt"] == batch_completed["startedAt"] == blocked["startedAt"]
    datetime.fromisoformat(payload["startedAt"])
    datetime.fromisoformat(payload["updatedAt"])
