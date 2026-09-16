# Football External SoccerNet Bounded Analysis Execution Approval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Approve the next bounded SoccerNet analysis execution using the validated 300-frame product bridge payload, without executing analysis in this approval batch.

**Architecture:** The batch is a saved-artifact approval gate. It reads only generated truth from `football_external_soccernet_video_analysis_dry_run_product_bridge_smoke_v1`, verifies the product bridge payload is complete and bounded to 300 frames, writes a next-batch execution contract, and leaves full analysis plus all mutation paths blocked.

**Tech Stack:** Python, pytest, JSON generated truth artifacts, repo-local storage under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7`.

---

### Task 1: Approval Runner And Contract

**Files:**
- Create: `backend/scripts/run_football_external_soccernet_bounded_analysis_execution_approval.py`
- Test: `backend/tests/test_run_football_external_soccernet_bounded_analysis_execution_approval.py`

- [x] **Step 1: Write failing tests**

Test the happy path, missing product bridge blocker, and the three adaptive attempt families.

- [x] **Step 2: Run tests to verify red**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_soccernet_bounded_analysis_execution_approval.py -q
```

Expected initial result: import failure for missing script.

- [x] **Step 3: Implement the approval runner**

The runner reads:

- `dry_run_product_bridge_smoke_summary.json`
- `dry_run_product_bridge_payload.json`
- `sampled_frame_existence_audit.json`

It writes:

- `bounded_analysis_execution_approval_summary.json`
- `bounded_analysis_scope_audit.json`
- `bounded_analysis_execution_contract.json`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`
- `batch_outcome_analysis.json/md`

- [x] **Step 4: Run tests to verify green**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_soccernet_bounded_analysis_execution_approval.py -q
```

Expected result: `3 passed`.

### Task 2: Generate Real Batch Artifacts

**Files:**
- Generated: `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_soccernet_bounded_analysis_execution_approval_v1/`

- [x] **Step 1: Run the approval batch**

Run:

```bash
python3 backend/scripts/run_football_external_soccernet_bounded_analysis_execution_approval.py
```

Expected result:

- `goalAchieved = true`
- `primaryBlocker = null`
- `boundedAnalysisExecutionApproved = true`
- `boundedAnalysisExecutionExecuted = false`
- `approvedFrameCount = 300`
- `nextRecommendedNextLever = football_external_soccernet_bounded_analysis_execution`

### Task 3: Roadmap And Verification

**Files:**
- Modify: `backend/storage/automation/unattended_roadmap_loop_status.json`
- Modify: `memorybank/currentRoadmap.md`
- Modify: `memorybank/activeContext.md`
- Modify: `SESSION-HANDOFF.md`

- [ ] **Step 1: Update roadmap and handoff docs from generated truth**

- [ ] **Step 2: Run focused verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  backend/tests/test_run_football_external_soccernet_bounded_analysis_execution_approval.py \
  backend/tests/test_run_football_external_soccernet_video_analysis_dry_run_product_bridge_smoke.py \
  backend/tests/test_unattended_roadmap_loop.py -q

python3 -m py_compile \
  backend/scripts/run_football_external_soccernet_bounded_analysis_execution_approval.py \
  backend/scripts/run_football_external_soccernet_video_analysis_dry_run_product_bridge_smoke.py

runpodctl pod list --all -o json
```

Expected result: tests pass, compile passes, pods `[]`.
