# Coverage Quality Sprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the trimmed real-video benchmark from `event taxonomy now good enough` to `coverage quality strong enough for truthful 5-10 minute promotion`.

**Architecture:** Keep the current upload, storage, and Runpod contract fixed. Improve only the coverage-quality seams around possession continuity, benchmark visibility, and app-facing access to the saved benchmark/probe truth. The sprint is intentionally bounded: no new infra, no longer clips, and no speculative LLM layers.

**Tech Stack:** Python, FastAPI, SQLite, pytest, JSON artifact storage, existing benchmark CLI

---

## Current Truth

- Saved trimmed benchmark match: `217d5baf5cdb40dd985d8b466c126264`
- Current saved summary:
  - `rawRowCount: 2291`
  - `frameCount: 360`
  - `withBallFrames: 46`
  - `withBallRatio: 0.12777777777777777`
  - `trackedPossessionFrames: 33`
  - `trackedPossessionRatio: 0.09166666666666666`
  - `controlledPossessionFrames: 33`
  - `controlledPossessionRatio: 0.09166666666666666`
  - `eventCount: 7`
  - `eventTypes: {"recovery": 4, "pass": 2, "carry": 1}`
  - `eventFamilyCount: 3`
  - `fiveMinuteTruthReady: false`
  - `fortyFiveMinuteTruthReady: false`
- Remaining blockers are now coverage ratios:
  - `withBallFrames / frameCount`
  - `controlledPossessionFrames / frameCount`

## Sprint Rules

- Do not widen into longer clips until the trimmed benchmark gate changes for honest reasons.
- Do not touch Runpod provisioning unless a regression proves the adapter broke.
- Do not fake passes/turnovers from unrelated track swaps.
- Keep unresolved-team honesty intact.
- Prefer small, test-first changes that can be benchmarked immediately.

## Progress

- Task 1 is done:
  - benchmark ratio fields landed
  - selected-cluster probe now mirrors the saved benchmark shape closely enough for CLI/API use
- Task 3 is done:
  - read-only benchmark endpoint landed at `GET /api/matches/{match_id}/benchmark`
  - optional `includeSelectedClusterProbe=true` adds the current selected-cluster projection without recomputation
- Task 2 concluded with a verified no-go:
  - no safe analytics-only continuity bridge remains on this trimmed clip
  - same-owner loose gaps are backward, stationary, or too borderline to justify lowering thresholds honestly
- Verification now on record:
  - `PYTHONPATH=. python3 -m pytest backend/tests/test_analytics.py backend/tests/test_run_benchmarks.py backend/tests/test_export_flatteners.py backend/tests/test_api.py -k 'benchmark or test_analytics or flatten' -q` -> `47 passed, 10 deselected`

## Task 1: Coverage Continuity Diagnostics

**Files:**
- Modify: `backend/app/run_benchmarks.py`
- Modify: `backend/scripts/run_trimmed_clip_benchmark.py`
- Modify: `backend/tests/test_run_benchmarks.py`

- [ ] Add explicit ratio fields to the benchmark output:
  - `withBallRatio`
  - `trackedPossessionRatio`
  - `controlledPossessionRatio`
- [ ] Keep the selected-cluster probe output aligned with the saved summary fields.
- [ ] Add tests that prove the new ratio fields are populated and stable.
- [ ] Verify:
  - `PYTHONPATH=. python3 -m pytest backend/tests/test_run_benchmarks.py -q`

## Task 2: Controlled Possession Continuity

**Files:**
- Modify: `backend/app/analytics.py`
- Modify: `backend/tests/test_analytics.py`

- [ ] Write failing tests for the smallest honest controlled-possession continuity seam:
  - same resolved owner
  - tiny loose gap
  - meaningful forward continuity
  - no event inflation on stationary/backward/noisy seams
- [ ] Implement the minimal continuity improvement.
- [ ] Keep suppression narrow and evidence-based.
- [ ] Verify:
  - `PYTHONPATH=. python3 -m pytest backend/tests/test_analytics.py -q`

## Task 3: Benchmark API Surface

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_api.py`
- Reuse: `backend/app/run_benchmarks.py`

- [ ] Add a read-only benchmark endpoint for a saved match.
- [ ] Add an option to include the selected-cluster probe in the response.
- [ ] Keep this endpoint local/state-reading only; no recomputation side effects.
- [ ] Verify:
  - `PYTHONPATH=. python3 -m pytest backend/tests/test_api.py -k 'benchmark' -q`

## Task 4: Truth Sync

**Files:**
- Modify: `SESSION-HANDOFF.md`
- Modify: `docs/superpowers/plans/2026-04-08-event-richness-and-scale-up-plan.md`
- Modify: `docs/superpowers/plans/2026-04-08-gpu-adoption-execution-plan.md`

- [ ] Update docs only after the code and benchmark outputs are verified.
- [ ] Replace stale ratio assumptions with the fresh trimmed benchmark truth.
- [ ] Explicitly state whether the sprint moved coverage gates or only observability.

## Execution Order

1. Task 1 and Task 2 can run in parallel.
2. Task 3 can run in parallel with Task 2 once Task 1’s benchmark fields are stable enough to consume.
3. Task 4 happens after verification, not before.

## Success Condition

This sprint is a success if all of the following are true:

- the trimmed benchmark exposes coverage ratios explicitly
- the app/backend can fetch benchmark truth without shelling into the server
- controlled-possession continuity improves honestly or is proven not to improve
- docs reflect the live trimmed benchmark after the changes

## No-Go Reminder

Do **not** jump to a `5-10 minute` or `45 minute` clip just because event richness improved. Promotion only happens when the trimmed benchmark itself says coverage is good enough.

## Next Queue

1. Improve upstream ball/owner coverage quality rather than squeezing more semantics out of analytics.
2. Use the benchmark endpoint/CLI as the canonical truth surface while iterating.
3. Only reopen longer-duration validation after the trimmed benchmark coverage ratios move for honest reasons.
