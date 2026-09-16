# Candidate Hygiene Promotion Sprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve 5-minute truth quality by pruning obvious false-ball probe candidates earlier and by applying profile-specific recovery crop hygiene during candidate generation, then rerun the same local and remote selected-cluster proof loop.

**Architecture:** Keep the truth-layer contract unchanged and move the next lever earlier in the pipeline. Reuse the existing false-ball cluster suppression idea on the probe-observed path, and make recovery profiles differ at candidate-generation time instead of only after generation.

**Tech Stack:** Python, pytest, Ruff, existing local proof runner, existing managed Runpod proof runner.

---

### Task 1: Promote Candidate Hygiene Into `run_guerilla.py`

**Files:**
- Modify: `backend/run_guerilla.py`
- Test: `backend/tests/test_run_guerilla.py`

- [ ] **Step 1: Write failing tests for probe false-ball suppression and generation-time recovery hygiene**

Add tests that prove:
- a repeated static edge-heavy probe cluster is suppressed before probe rows feed `observedBall`
- recovery profiles with `cropEdgeMargin` / `maxCropCenterYRatio` apply those checks during candidate generation, not only afterward
- existing bridge-friendly or mid-field candidates still survive

- [ ] **Step 2: Run the new targeted tests to verify they fail for the right reason**

Run:

```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst python3 -m pytest \
  backend/tests/test_run_guerilla.py -k "probe_false_ball or recovery_generation_hygiene" -q
```

Expected: failing assertions showing the current probe path keeps the false cluster or that generation-time profile hygiene is not yet applied.

- [ ] **Step 3: Implement the minimal production changes**

In `backend/run_guerilla.py`:
- apply repeated false-ball suppression to probe-observed candidates before `_filter_probe_observed_ball_rows(...)`
- thread `crop_edge_margin` and `max_crop_center_y_ratio` from recovery profiles into `recover_ball_rows(...)` at generation time
- update the recovery cache key if needed so rows generated with different crop hygiene are not incorrectly reused across profiles
- keep observed / inferred / accepted semantics unchanged

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run:

```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst python3 -m pytest \
  backend/tests/test_run_guerilla.py -k "probe_false_ball or recovery_generation_hygiene" -q
```

Expected: all targeted tests pass.

- [ ] **Step 5: Run the focused file-level verification**

Run:

```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst python3 -m pytest backend/tests/test_run_guerilla.py -q
./backend/venv/bin/python -m ruff check backend/run_guerilla.py backend/tests/test_run_guerilla.py
```

Expected: test file passes and Ruff reports no issues.

### Task 2: Verify Proof Outputs Still Surface the Right State

**Files:**
- Inspect/Modify: `backend/app/run_benchmarks.py`
- Inspect/Modify: `backend/scripts/run_local_app_path_proof.py`
- Inspect/Modify: `backend/scripts/run_remote_app_path_proof.py`
- Test: `backend/tests/test_run_benchmarks.py`
- Test: `backend/tests/test_run_local_app_path_proof.py`
- Test: `backend/tests/test_run_remote_app_path_proof.py`

- [ ] **Step 1: Add or update tests only if the new hygiene changes any persisted debug surface**

If the new behavior changes debug or proof summary shape, write the failing tests first in the touched summary test files.

- [ ] **Step 2: Run the summary tests to verify the failure**

Run:

```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst python3 -m pytest \
  backend/tests/test_run_benchmarks.py \
  backend/tests/test_run_local_app_path_proof.py \
  backend/tests/test_run_remote_app_path_proof.py -q
```

Expected: only new expectations fail if summary shape changed; otherwise this step is a no-op and the next step should keep them green.

- [ ] **Step 3: Make any necessary summary wiring changes**

Only if needed:
- preserve existing proof summary compatibility
- expose any new candidate-hygiene diagnostics needed to interpret the proof loop

- [ ] **Step 4: Run focused summary verification**

Run:

```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst python3 -m pytest \
  backend/tests/test_run_benchmarks.py \
  backend/tests/test_run_local_app_path_proof.py \
  backend/tests/test_run_remote_app_path_proof.py -q
./backend/venv/bin/python -m ruff check \
  backend/app/run_benchmarks.py \
  backend/scripts/run_local_app_path_proof.py \
  backend/scripts/run_remote_app_path_proof.py \
  backend/tests/test_run_benchmarks.py \
  backend/tests/test_run_local_app_path_proof.py \
  backend/tests/test_run_remote_app_path_proof.py
```

Expected: focused summary tests pass and Ruff is clean.

### Task 3: Run the Real 5-Minute Proof Loop And Save The Outcome

**Files:**
- Run: `backend/scripts/run_local_app_path_proof.py`
- Run: `backend/scripts/promote_selected_cluster_for_proof.py`
- Run: `backend/scripts/run_managed_remote_app_path_proof.py`
- Run: `backend/scripts/compare_ball_pipeline_trace.py`
- Modify: `SESSION-HANDOFF.md`
- Modify: `docs/superpowers/plans/2026-04-11-active-now-systematic-roadmap.md`

- [ ] **Step 1: Run the parity-safe local 5-minute proof**

Run:

```bash
QT_QPA_PLATFORM=offscreen ./backend/venv/bin/python \
  backend/scripts/run_local_app_path_proof.py \
  --include-selected-clusters \
  --timeout-seconds 5400
```

Expected: completed local match artifact with compact summary output.

- [ ] **Step 2: Run explicit selected-cluster promotion on the new local match**

Run:

```bash
QT_QPA_PLATFORM=offscreen ./backend/venv/bin/python \
  backend/scripts/promote_selected_cluster_for_proof.py \
  --match-id <LOCAL_MATCH_ID>
```

Expected: `selected_cluster_delta.json` is written and the promoted summary is printed.

- [ ] **Step 3: Run the managed warm remote 5-minute proof**

Run with the existing object-storage-backed environment and current template line:

```bash
python3 backend/scripts/run_managed_remote_app_path_proof.py --timeout-seconds 7200
```

Expected: completed remote match artifact and no leaked endpoint.

- [ ] **Step 4: Run explicit selected-cluster promotion on the new remote match**

Run:

```bash
python3 backend/scripts/promote_selected_cluster_for_proof.py --match-id <REMOTE_MATCH_ID>
```

Expected: promoted remote delta artifact is written.

- [ ] **Step 5: Compare local and remote traces**

Run:

```bash
python3 backend/scripts/compare_ball_pipeline_trace.py \
  --local-match-id <LOCAL_MATCH_ID> \
  --remote-match-id <REMOTE_MATCH_ID>
```

Expected: either parity holds through possession or any divergence is clearly classified.

- [ ] **Step 6: Verify cleanup and save the binary outcome**

Run:

```bash
runpodctl serverless list -o json
```

Expected: `[]`

Then update:
- `SESSION-HANDOFF.md`
- `docs/superpowers/plans/2026-04-11-active-now-systematic-roadmap.md`

Record exactly one outcome:
- `candidate hygiene materially improved the 5-minute truth gates`
- or `candidate hygiene did not materially improve the 5-minute truth gates`
