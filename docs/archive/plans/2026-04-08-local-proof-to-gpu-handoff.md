# Local Proof To GPU Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish one truthful manual-calibrated local video run to completion, freeze the portable job/artifact contract around that proof, and then use the same contract as the handoff point for serverless GPU execution.

**Architecture:** Treat local processing as the truth-establishing environment and GPU execution as the scale/performance environment. First prove the 1-minute trimmed clip can complete with manual calibration and produce reviewable artifacts under the existing local API. Then codify the exact upload config, job lifecycle, artifact outputs, and error semantics so a remote GPU backend can swap in without changing the frontend or the review workflow.

**Tech Stack:** FastAPI, SQLite/JSON artifact storage, Python pytest, React, TypeScript, Vitest, Uvicorn, Playwright, Ultralytics YOLO/BoT-SORT, future serverless GPU adapter.

---

## Current Truth

- Auto-homography failure is now honest and operator-visible.
- Manual calibration recovery is live:
  - switch to manual mode
  - ordered corner inputs
  - click-to-fill first-frame picker
  - retry the same failed video without reopening the chooser
- The previous tracker dependency wall is closed:
  - repo-root `lap.py` shim satisfies Ultralytics' `lap` import in externally managed environments
- Live retry of the trimmed clip now enters real YOLO/BoT-SORT processing instead of failing immediately.
- The trimmed clip is still the active canonical repro asset:
  - `/root/WorkSpace/fotball-analyst/.worktrees/videos/trimed-football-2-1minute.mp4`
- One manual-calibrated local run is now fully proven:
  - job: `c04b728f765644fe91a188cfdb5bb24a`
  - match: `e4795c0bf5274072851cc6478cb0dd2d`
  - `jobStatus: completed`
  - `matchStatus: ready`
  - `durationSeconds: 117.840114`
  - `rawRowCount: 306`
  - `frameCount: 124`
  - `withBallFrames: 0`
  - `eventCount: 0`
  - `requiresTeamSelection: true`
  - artifacts present: `frames.json`, `analytics.json`, `events.json`, `raw_rows.json`
- The canonical trimmed-clip benchmark command now exists:
  - `PYTHONPATH=. python3 backend/scripts/run_trimmed_clip_benchmark.py --match-id e4795c0bf5274072851cc6478cb0dd2d`
- The portable handoff contract is now frozen in:
  - `docs/superpowers/specs/2026-04-08-gpu-handoff-contract.md`
- The GPU adoption execution plan now exists:
  - `docs/superpowers/plans/2026-04-08-gpu-adoption-execution-plan.md`
- The contract test slice is now real:
  - `PYTHONPATH=. python3 -m pytest backend/tests/test_gpu_contract.py -q`
  - result: `2 passed`
- Frontend job typing now includes the persisted metadata fields:
  - `logPath`
  - `startedAt`
  - `completedAt`
  - `durationSeconds`

## Exit Criteria

This lane is complete when all of the following are true:

1. One manual-calibrated local run of the trimmed clip reaches a terminal state (`completed` or `failed`) with logs and artifacts captured.
2. The canonical local benchmark for that run is scripted and repeatable.
3. The backend/frontend contract that must remain stable during GPU migration is written down and test-covered.
4. A GPU-handoff plan exists that clearly states what moves to remote execution and what must remain unchanged.

## File Map

### Backend

- Modify: `backend/app/main.py`
- Modify: `backend/app/jobs.py`
- Modify: `backend/app/processor.py`
- Modify: `backend/app/storage.py`
- Modify: `backend/app/schemas.py`
- Create: `backend/app/run_benchmarks.py`
- Create: `backend/tests/test_run_benchmarks.py`
- Create: `backend/tests/test_gpu_contract.py`
- Create: `backend/scripts/run_trimmed_clip_benchmark.py`

### Frontend

- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/utils/api.ts`
- Modify: `frontend/src/types/index.ts`
- Test: `frontend/src/components/UploadCalibrationPanel.test.tsx`

### Docs

- Modify: `docs/superpowers/plans/2026-04-07-local-video-upload-reliability-plan.md`
- Modify: `SESSION-HANDOFF.md`
- Create: `docs/superpowers/specs/2026-04-08-gpu-handoff-contract.md`
- Create: `docs/superpowers/plans/2026-04-08-gpu-adoption-execution-plan.md`

---

## Task 1: Finish One Manual-Calibrated Local Run To Completion

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `backend/app/main.py`
- Modify: `backend/app/jobs.py`
- Modify: `backend/app/storage.py`
- Modify: `docs/superpowers/plans/2026-04-07-local-video-upload-reliability-plan.md`

- [x] **Step 1: Capture the active retry job state and current terminal behavior**

Run:

```bash
cd /root/WorkSpace/fotball-analyst
PYTHONPATH=. python3 -m uvicorn backend.app.main:create_app --factory --host 127.0.0.1 --port 8000
```

In a second terminal:

```bash
cd /root/WorkSpace/fotball-analyst/frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Use the trimmed clip and a manual 4-corner calibration retry. Record:
- `jobId`
- `matchId`
- terminal job status
- wall-clock duration
- log path
- whether `frames.json`, `analytics.json`, and `events.json` were written

- [x] **Step 2: Make terminal job metadata easier to inspect after long runs**

Extend job persistence so the terminal record includes:
- `startedAt`
- `completedAt`
- `durationSeconds`
- `logPath`

Touch:
- `backend/app/schemas.py`
- `backend/app/jobs.py`
- `backend/app/storage.py`

- [x] **Step 3: Re-run the trimmed clip and confirm one full local terminal run with persisted metadata**

Expected proof:
- no hidden crash
- operator-facing status transitions stay honest
- job record retains enough metadata to inspect the run after the UI reloads

- [x] **Step 4: Sync the reliability plan with the actual result**

Update:
- `docs/superpowers/plans/2026-04-07-local-video-upload-reliability-plan.md`

Record:
- whether the manual run completed or failed
- if failed, the exact next blocker
- if completed, the artifact paths and metric snapshot

---

## Task 2: Script The Canonical Trimmed-Clip Benchmark

**Files:**
- Create: `backend/app/run_benchmarks.py`
- Create: `backend/scripts/run_trimmed_clip_benchmark.py`
- Create: `backend/tests/test_run_benchmarks.py`
- Modify: `SESSION-HANDOFF.md`

- [x] **Step 1: Create a small benchmark summary helper**

Implement a backend helper that reads a finished match workspace and emits:
- `matchId`
- `jobId` if available
- `inputMode`
- `status`
- `frameCount`
- `withBallFrames`
- `eventCount`
- `eventTypes`
- `ballSignalStatus`
- `requiresTeamSelection`
- artifact presence booleans

- [x] **Step 2: Add a CLI wrapper for the trimmed clip benchmark**

Create:
- `backend/scripts/run_trimmed_clip_benchmark.py`

It should support:
- summarizing an existing `matchId`
- optionally rerunning the trimmed clip if given `--rerun-manual`
- printing compact JSON only

- [x] **Step 3: Write narrow benchmark tests**

Test:
- summary logic with fixture-like stored payloads
- missing artifact handling
- event type counting

- [x] **Step 4: Run the real benchmark against the trimmed clip match**

Run:

```bash
cd /root/WorkSpace/fotball-analyst
PYTHONPATH=. python3 backend/scripts/run_trimmed_clip_benchmark.py --match-id <match_id>
```

Save the result into `SESSION-HANDOFF.md`.

Observed result:

```json
{"matchId":"e4795c0bf5274072851cc6478cb0dd2d","jobId":"c04b728f765644fe91a188cfdb5bb24a","inputMode":"video","matchStatus":"ready","jobStatus":"completed","requiresTeamSelection":true,"rawRowCount":306,"frameCount":124,"withBallFrames":0,"eventCount":0,"eventTypes":{},"shotCount":0,"ballSignalStatus":null,"artifactPresence":{"frames":true,"analytics":true,"events":true,"rawRows":true}}
```

---

## Task 3: Freeze The Portable Frontend/Backend Contract

**Files:**
- Create: `docs/superpowers/specs/2026-04-08-gpu-handoff-contract.md`
- Create: `backend/tests/test_gpu_contract.py`
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/utils/api.ts`

- [x] **Step 1: Write down the non-negotiable contract**

Document:
- upload payload shape
- manual calibration payload shape
- job lifecycle states
- terminal error semantics
- artifact endpoint expectations
- review-surface truth gates

- [x] **Step 2: Add backend tests that lock the contract**

Cover:
- video upload config shape
- job terminal payload shape
- unresolved-team and untrusted-ball fields remaining present

- [x] **Step 3: Align frontend types to the frozen contract**

Do not expand features here. Only make the types explicit and stable.

- [x] **Step 4: Verify the contract test slice**

Run:

```bash
cd /root/WorkSpace/fotball-analyst
PYTHONPATH=. python3 -m pytest backend/tests/test_gpu_contract.py -q
cd frontend
npm run build
```

---

## Task 4: Separate Local Truth From GPU Execution Concerns

**Files:**
- Create: `docs/superpowers/plans/2026-04-08-gpu-adoption-execution-plan.md`
- Modify: `SESSION-HANDOFF.md`

- [x] **Step 1: Define what stays local truth**

Must stay invariant:
- upload calibration UX
- job states shown to operators
- error messaging
- artifact layout
- review truth gates

- [x] **Step 2: Define what moves to serverless GPU**

Can move:
- heavy video inference
- tracking runtime
- detector configuration
- worker packaging/deployment

- [x] **Step 3: Write the first GPU execution plan**

Include:
- target adapter seam
- remote submission path
- result import path
- validation against the trimmed-clip benchmark

---

## Task 5: Close The Lane With A Go/No-Go Decision

**Files:**
- Modify: `SESSION-HANDOFF.md`
- Modify: `docs/superpowers/plans/2026-04-07-local-video-upload-reliability-plan.md`

- [x] **Step 1: Evaluate the local manual proof result**

Decision options:
- `Go local complete -> start GPU adoption`
- `Stay local -> one more blocker remains`

- [x] **Step 2: Write the explicit recommendation**

The closing note must say one of:
- `Local proof is strong enough; start serverless GPU execution lane now.`
- `Do not start GPU lane yet; fix the remaining local blocker first.`

Closing recommendation:

- `Local proof is strong enough; start serverless GPU execution lane now.`
- Reason:
  - upload / retry / failure semantics are now honest
  - one manual-calibrated local run reached terminal completion with persisted metadata
  - the trimmed-clip benchmark is scripted and repeatable
  - the portable contract is frozen
  - the remaining blocker is output quality / runtime scale, which is exactly the right boundary for GPU adoption

---

## Verification Checklist

Run at minimum before claiming this plan complete:

```bash
cd /root/WorkSpace/fotball-analyst
PYTHONPATH=. python3 -m pytest backend/tests/test_lap_shim.py backend/tests/test_run_benchmarks.py backend/tests/test_gpu_contract.py -q

cd /root/WorkSpace/fotball-analyst/frontend
npm test -- --run src/components/UploadCalibrationPanel.test.tsx src/utils/uploadErrors.test.ts src/components/StatsPanel.test.tsx src/components/TeamSelectionBanner.test.tsx
npm run build
```

And one real run:

```bash
cd /root/WorkSpace/fotball-analyst
PYTHONPATH=. python3 backend/scripts/run_trimmed_clip_benchmark.py --match-id <match_id>
```
