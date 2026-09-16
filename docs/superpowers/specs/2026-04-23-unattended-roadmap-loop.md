# Unattended Roadmap Loop

## Purpose

This spec defines the repo-local continuation contract for long-running roadmap work inside a live session.

It is meant to keep the agent strict, checklist-bound, and truth-driven while continuing through the active roadmap lane without approval prompts.

## Active Checklist

- `docs/superpowers/plans/2026-04-23-promoted-v6-failing-source-robustness-validation.md`

## Clean Session Rehydration Order

Before acting in a fresh session:

1. Read `memorybank/README.md` for the memorybank reading order.
2. Read `memorybank/activeContext.md`, `memorybank/currentRoadmap.md`, and `memorybank/progress.md`.
3. Open the active checklist and treat it as the only live todo source.
4. Read the current blocker truth from:
   - `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/promoted_touchline_detector_candidate_retention_delta_analysis_v1/retention_delta_summary.json`
   - `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/suite_summary.json`
5. Read `backend/storage/automation/unattended_roadmap_loop_status.json` to confirm the active queue item, attempt budget, and next expected action.
6. Only consult remote-compute workflow references if the chosen attempt genuinely requires pod-backed work:
   - `memorybank/operations/touchline-detector-training-workflow.md`
   - `memorybank/operations/touchline-detector-evaluation-workflow.md`
   - `backend/scripts/runpod_session.py`
   - `/root/.agents/skills/runpodctl/SKILL.md`

## Authoritative Source Order

- generated artifacts first
- active checklist second
- memorybank third
- `SESSION-HANDOFF.md` fourth
- archived or historical plans last

Warning:
- convenience summaries and top-level shortcuts must not override generated diagnosis surfaces

## Reusable Continuation Prompt

```text
Continue from docs/superpowers/plans/2026-04-23-promoted-v6-failing-source-robustness-validation.md.

Before touching code, rehydrate context in this order:
1. Read memorybank/README.md for the memorybank reading order.
2. Read memorybank/activeContext.md, memorybank/currentRoadmap.md, and memorybank/progress.md.
3. Read the active checklist and treat it as the only live todo source.
4. Read backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/promoted_touchline_detector_candidate_retention_delta_analysis_v1/retention_delta_summary.json and backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/suite_summary.json as the current blocker truth.
5. Read backend/storage/automation/unattended_roadmap_loop_status.json to confirm the active queue item, attempt budget, and next expected action.

Authoritative source order:
- generated artifacts first
- active checklist second
- memorybank third
- SESSION-HANDOFF.md fourth
- archived or historical plans last

Do not trust top-level summary shortcuts over the generated diagnosis surfaces. If docs disagree with generated artifacts, follow the generated artifacts and then refresh the docs.

Work the first unchecked batch in order.
Do not ask for approval; make reasonable assumptions.

Current grounded truth:
- active lane: promote_touchline_detector_candidate
- active queue item: touchline_detector_candidate_v6_accepted_signal_retention_fix_v1
- current blocker class: accepted_signal_retention_collapse
- acceptedRetentionRatio = 0.099
- controlledRetentionRatio = 0.133
- runtime defaults stay frozen
- first attempt family: admission_widening

Execution rules:
- each queued batch gets 4 materially distinct attempts
- after each attempt, run focused verification, regenerate suite truth if artifacts changed, update memorybank and SESSION-HANDOFF.md from generated truth only, and update backend/storage/automation/unattended_roadmap_loop_status.json
- if all 4 attempts fail, mark the item exhausted and move to the next queued batch in the same lane
- do not phase-jump
- do not reopen already falsified families
- do not validate runtime defaults unless the promoted robustness gate is actually cleared by generated truth

Only consult memorybank/operations/touchline-detector-training-workflow.md, memorybank/operations/touchline-detector-evaluation-workflow.md, backend/scripts/runpod_session.py, or /root/.agents/skills/runpodctl/SKILL.md if the chosen attempt genuinely requires remote compute or pod-backed work.

Only stop if:
1. the batch is fully complete and verified, or
2. you hit a real blocker that cannot be resolved from repo truth.
Update memorybank and SESSION-HANDOFF.md from generated truth only.
Run verification before any success claim.
```

## Operational Meaning Of “Continue”

1. Open the active checklist.
2. Find the first unchecked task in the current checklist.
3. Treat the first unchecked batch section as the active batch.
4. Execute that batch end-to-end before touching a later batch.
5. Run the full verification needed for any success claim.
6. Refresh suite truth if the batch changes generated artifacts.
7. Update memorybank and `SESSION-HANDOFF.md` only from generated truth.
8. Mark the finished batch in the same checklist and append the next corrective sub-batch there if needed.
9. If more unchecked work remains in the same checklist and there is no real blocker, continue immediately.

The latest completed unattended batch is `promoted_touchline_detector_candidate_retention_delta_analysis_v1`.

The current active batch is `touchline_detector_candidate_v6_accepted_signal_retention_fix_v1`.

The current blocker-cycle policy is:

- each queued batch gets exactly `4` materially distinct attempts
- if all `4` attempts fail, the session marks that batch exhausted and moves to the next queued batch in the same source-robustness lane
- runtime-default validation remains blocked unless generated truth explicitly clears the promoted robustness gate

## What Counts As A Blocker

A blocker is real only when the next truthful step cannot be completed from repo-local source of truth, generated artifacts, or bounded implementation work already in scope.

Examples:
- required artifacts are missing or contradictory in a way the repo cannot resolve
- verification exposes a failure that demands a new human decision or unavailable external input
- a plan assumption is no longer true and generated evidence does not identify the safe next move

Non-blockers:
- a batch fails honestly and names the next corrective batch
- implementation requires routine code edits or test repair inside the same lane
- documentation needs to be refreshed from already-generated truth

## Required Batch-Boundary Refreshes

At each batch boundary, refresh the artifacts that truthfully changed:
- candidate-local batch artifacts
- suite truth surfaces if regenerated
- `memorybank/activeContext.md`
- `memorybank/currentRoadmap.md`
- `memorybank/progress.md`
- `memorybank/features/source-robustness-lane.md`
- `SESSION-HANDOFF.md`

## Heartbeat Artifact

Use the lightweight status file at:

- `backend/storage/automation/unattended_roadmap_loop_status.json`

It is a progress heartbeat only. The active checklist, generated batch artifacts, memorybank, and `SESSION-HANDOFF.md` remain authoritative.

Per-attempt fields that should now be recorded when applicable:

- `queueItemName`
- `attemptNumber`
- `attemptBudget`
- `attemptApproachFamily`
- `itemStatus`
- `queueDecision`

Recommended update points:
- loop start
- batch start
- before long verification runs
- batch completion
- blocker stop

Helper command:

```bash
python3 backend/scripts/update_unattended_roadmap_loop_status.py \
  --loop-status batch_started \
  --current-step "Beginning touchline_detector_candidate_v6_accepted_signal_retention_fix_v1." \
  --queue-item-name touchline_detector_candidate_v6_accepted_signal_retention_fix_v1 \
  --attempt-number 1 \
  --attempt-budget 4 \
  --attempt-approach-family admission_widening \
  --item-status in_progress \
  --queue-decision continue_current_item \
  --next-expected-action "Lift failing-source accepted retention from the saved diagnosis before any runtime-default validation."
```

## Guardrails

Explicitly forbidden:
- opening a new todo file when the active checklist already governs the lane
- changing phases without generated evidence
- skipping verification to save time
- inventing a new lane because a batch failed
- treating speculative docs as truth when generated artifacts disagree

Explicitly allowed:
- continuing across multiple corrective batches in the same checklist
- making reasonable assumptions when repo truth is sufficient
- stopping only after a truthful closeout or a real unresolved blocker

## Limitation

This contract supports unattended continuation inside a live session only.

It does not let the agent self-wake after the session ends, and no self-resume happens without an external re-invocation source.
