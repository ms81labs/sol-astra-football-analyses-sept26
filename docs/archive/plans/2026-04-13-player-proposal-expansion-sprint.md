# Player Proposal Expansion Sprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve 5-minute truth quality by expanding recovery candidate generation through bounded player-centric proposal windows before recovery scoring.

**Architecture:** Keep `observedBall`, `inferredBall`, `acceptedBall`, truth gates, and explicit selected-cluster promotion unchanged. Improve only the recovery-generation path in `backend/run_guerilla.py` by deriving multiple small proposal crops from individual player boxes, ranking them by anchor continuity and support, and exposing proposal diagnostics in the existing proof summaries. Final validation stays on the managed serverless proof lane.

**Tech Stack:** Python, OpenCV, Ultralytics YOLO, pytest, Ruff, Runpod serverless.

---

### Task 1: Add player-centric recovery proposal generation

**Files:**
- Modify: `backend/run_guerilla.py`
- Test: `backend/tests/test_run_guerilla.py`

- [x] Add helpers that collect per-frame individual player source boxes from rows and rank proposal windows using observed-anchor continuity first, then non-edge / support signals.
- [x] Extend `recover_ball_rows(...)` so `crop_windows_by_frame` can provide multiple crop windows per sampled frame without changing the observed/inferred contract.
- [x] Add a new bounded recovery crop mode that builds up to a small number of player-centric proposal windows per frame.
- [x] Add proposal diagnostics to the selected recovery profile summary.
- [x] Cover with focused tests for ranking, multi-window inference, and diagnostics.

### Task 2: Surface proposal diagnostics in proof summaries

**Files:**
- Modify: `backend/app/run_benchmarks.py`
- Modify: `backend/scripts/run_local_app_path_proof.py`
- Modify: `backend/scripts/run_remote_app_path_proof.py`
- Test: `backend/tests/test_run_benchmarks.py`
- Test: `backend/tests/test_run_local_app_path_proof.py`
- Test: `backend/tests/test_run_remote_app_path_proof.py`

- [x] Add compact summary fields for the new proposal diagnostics.
- [x] Keep existing summary shape backward-compatible.
- [x] Add tests proving the new fields appear without breaking selected-cluster payloads.

### Task 3: Serverless validation and roadmap update

**Files:**
- Modify: `SESSION-HANDOFF.md`
- Modify: `docs/superpowers/plans/2026-04-11-active-now-systematic-roadmap.md`

- [x] Run focused pytest and Ruff on touched files.
- [ ] Run one managed remote 5-minute proof on serverless.
- [ ] Run explicit selected-cluster promotion on the saved remote match.
- [ ] Update handoff and roadmap with one binary outcome.

### Success Bar

After selected-cluster promotion, count this sprint as a win if any of these happen:
- `acceptedBallFrames >= 120` with `supportedAcceptedBallRatio >= 0.95`
- `recoveredSelectedFrames >= 35`
- `controlledPossessionFrames >= 110`
- `ballTrackViable == true`

### Binary Outcome

Record exactly one:
- `player proposal expansion materially improved truthful coverage`
- `player proposal expansion did not materially improve the 5-minute truth gates`

## 2026-04-13 Checkpoint

Code and focused verification are complete.

- Task 1 shipped in:
  - `backend/run_guerilla.py`
  - `backend/tests/test_run_guerilla.py`
- Task 2 shipped in:
  - `backend/app/run_benchmarks.py`
  - `backend/app/runpod.py`
  - `backend/runpod_handler/handler.py`
  - `backend/tests/test_run_benchmarks.py`
  - `backend/tests/test_runpod.py`
  - `backend/tests/test_runpod_handler.py`
  - `backend/tests/test_run_remote_app_path_proof.py`
- Focused verification completed:
  - `python3 -m pytest backend/tests/test_run_guerilla.py backend/tests/test_run_benchmarks.py backend/tests/test_runpod.py backend/tests/test_runpod_handler.py backend/tests/test_run_remote_app_path_proof.py -q`
  - `./backend/venv/bin/python -m ruff check backend/run_guerilla.py backend/app/run_benchmarks.py backend/app/runpod.py backend/runpod_handler/handler.py backend/tests/test_run_guerilla.py backend/tests/test_run_benchmarks.py backend/tests/test_runpod.py backend/tests/test_runpod_handler.py backend/tests/test_run_remote_app_path_proof.py`

Fresh managed serverless validation did not produce a valid proof result yet.

- fresh serverless endpoint: `4yjzmmia8bzcv0`
- fresh serverless worker: `xevd1rlrv168pq`
- fresh local app job: `87babc3c08b34635a6a6c8cd7485055e`
- fresh proof match: `d0a49e9e758b40b28133621c2beda778`
- fresh Runpod run id: `7fba347c-8f70-4d56-a61e-e6f047fa0245-e2`
- runtime fingerprint used the newly deployed handler image:
  - `docker.io/ms81vs/fotball-analyst-runpod-handler:parity-20260413140117-6991eddf`

Observed blocker on the first fresh proof:

- transport reached `IN_PROGRESS`
- `workerHeartbeatEnabled=true`
- no worker heartbeat object was ever written
- `workerStartedProcessing` never flipped true
- after more than 8 minutes in `IN_PROGRESS`, the run still had no `modelLoad` heartbeat

Operational decision:

- deleted endpoint `4yjzmmia8bzcv0` to stop H100 spend
- killed the hanging local managed-proof wrappers after endpoint cleanup
- confirmed `runpodctl serverless list -o json` returned `[]`

Current status:

- the sprint is **not** closed
- there is **no** fresh valid remote proof result for the player-proposal batch yet
- the next continuation should resume from this blocked checkpoint, not write the binary roadmap outcome

Immediate retry after cleanup also failed before useful work began:

- retry endpoint: `4p1ub7r488q8o6`
- retry worker: `hywk2a3ptqopwj`
- retry local app job: `80411c54649843628e603d0bcca04795`
- retry match: `aea9cd9daee94802b14137fe18a45299`
- retry Runpod run id: `b3d0db9f-2a55-487d-9a49-47647110fe74-e2`
- the first rented worker exited immediately
- the run stayed in `IN_QUEUE`
- no worker heartbeat object was ever written
- the endpoint was deleted to stop additional spend

Revised status:

- the player-proposal code path is shipped and focused verification is green
- managed serverless validation is now blocked by reproducible pre-heartbeat startup failures on the fresh image
- do **not** claim the sprint is closed until one fresh valid remote proof exists

## 2026-04-13 Pod Completion Outcome

The blocked proof was completed on the cheaper pod-first lane instead of spending more on serverless retries.

Pod proof contract:
- pod id `37n9f2lf2uq390`
- GPU `NVIDIA RTX PRO 4500 Blackwell`
- pod match `6b8d61c4921348a8b82f86d23e789751`
- pod job `e58f3adaecb04f989cb85d5627c3636c`

Fresh valid pod proof result before team selection:
- `proposalCandidateFrames=0`
- `proposalWindowCount=0`
- `acceptedBallFrames=101`
- `controlledPossessionFrames=0`
- `ballTrackEdgeFrameShare=0.812`
- `ballTrackViable=false`
- recommended cluster `1`

Fresh valid pod proof result after explicit selected-cluster promotion:
- selected cluster `1`
- `acceptedBallFrames=101`
- `controlledPossessionFrames=98`
- `eventFamilyCount=5`
- `ballTrackEdgeFrameShare=0.812`
- `ballTrackViable=false`
- remaining truth-gate reasons:
  - sparse accepted ball layer
  - non-viable ball track
  - controlled possession ratio still below the 20% gate

Binary outcome:
- `player proposal expansion did not materially improve the 5-minute truth gates`

Decision:
- do **not** spend for a serverless confirmation run
- move the roadmap deeper into anchor-seed / false-negative suppression before proposal window construction
