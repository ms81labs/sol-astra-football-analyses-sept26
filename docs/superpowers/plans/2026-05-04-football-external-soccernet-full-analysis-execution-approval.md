# Football External SoccerNet Full Analysis Execution Approval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Approve a future full-frame analysis pass on the extracted SoccerNet 224p video member without executing full analysis in this batch.

**Architecture:** The batch reads the bounded lane closeout truth plus the existing product video bundle, validates that the bounded lane is closed and that the extracted 224p video path is known/openable, then writes a full-analysis execution contract. The contract permits only the next full-analysis execution batch and keeps training, promotion, candidate-evaluation readiness, runtime-default mutation, 720p download, and archive download blocked.

**Tech Stack:** Python, pytest, JSON generated truth, repo-local storage artifacts.

---

### Task 1: Full Analysis Approval Runner

**Files:**
- Create: `backend/scripts/run_football_external_soccernet_full_analysis_execution_approval.py`
- Test: `backend/tests/test_run_football_external_soccernet_full_analysis_execution_approval.py`

- [x] **Step 1: Write failing tests**

Test the happy path, missing bounded closeout blocker, and three adaptive attempt families.

- [x] **Step 2: Verify red**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_soccernet_full_analysis_execution_approval.py -q
```

Expected initial result: import failure for missing runner.

- [ ] **Step 3: Implement runner**

Read:

- `football_external_soccernet_bounded_analysis_lane_closeout_v1/bounded_analysis_lane_closeout_summary.json`
- `football_external_soccernet_bounded_analysis_lane_closeout_v1/full_analysis_execution_approval_contract_prep.json`
- `football_external_soccernet_video_product_path_smoke_v1/external_video_product_bundle.json`

Write:

- `full_analysis_execution_approval_summary.json`
- `full_analysis_scope_audit.json`
- `full_analysis_execution_contract.json`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`
- `batch_outcome_analysis.json/md`

- [ ] **Step 4: Execute real batch**

Run:

```bash
python3 backend/scripts/run_football_external_soccernet_full_analysis_execution_approval.py
```

Expected generated truth:

- `goalAchieved = true`
- `primaryBlocker = null`
- `fullAnalysisExecutionApproved = true`
- `fullAnalysisExecutionExecuted = false`
- `selectedVideoPath` points at the extracted 224p MP4
- `approvedFrameCount = 146893`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_full_analysis_execution`

### Task 2: Roadmap And Verification

**Files:**
- Modify: `backend/storage/automation/unattended_roadmap_loop_status.json`
- Modify: `memorybank/currentRoadmap.md`
- Modify: `memorybank/activeContext.md`
- Modify: `SESSION-HANDOFF.md`

- [ ] **Step 1: Update docs/status from generated truth**

- [ ] **Step 2: Run focused verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  backend/tests/test_run_football_external_soccernet_full_analysis_execution_approval.py \
  backend/tests/test_run_football_external_soccernet_bounded_analysis_lane_closeout.py \
  backend/tests/test_unattended_roadmap_loop.py -q

python3 -m py_compile \
  backend/scripts/run_football_external_soccernet_full_analysis_execution_approval.py \
  backend/scripts/run_football_external_soccernet_bounded_analysis_lane_closeout.py

runpodctl pod list --all -o json
```
