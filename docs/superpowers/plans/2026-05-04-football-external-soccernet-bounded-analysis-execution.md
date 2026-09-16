# Football External SoccerNet Bounded Analysis Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the approved 300-frame SoccerNet bounded analysis and produce product-ready frame-stat signal artifacts without running full match analysis.

**Architecture:** The batch reads the bounded execution approval plus the dry-run product bridge payload, resolves the 300 sampled frame images, computes lightweight per-frame visual statistics, writes a bounded analysis product payload, and routes to a report smoke. It never trains, promotes, mutates runtime defaults, or marks candidate evaluation ready.

**Tech Stack:** Python, OpenCV, pytest, JSON generated truth artifacts.

---

### Task 1: Bounded Execution Runner

**Files:**
- Create: `backend/scripts/run_football_external_soccernet_bounded_analysis_execution.py`
- Test: `backend/tests/test_run_football_external_soccernet_bounded_analysis_execution.py`

- [x] **Step 1: Write failing tests**

Cover the happy path, missing approval blocker, and three adaptive attempt families.

- [x] **Step 2: Verify red**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_soccernet_bounded_analysis_execution.py -q
```

Expected initial result: import failure for missing runner.

- [x] **Step 3: Implement runner**

The runner consumes:

- `football_external_soccernet_bounded_analysis_execution_approval_v1/bounded_analysis_execution_approval_summary.json`
- `football_external_soccernet_bounded_analysis_execution_approval_v1/bounded_analysis_execution_contract.json`
- `football_external_soccernet_video_analysis_dry_run_product_bridge_smoke_v1/dry_run_product_bridge_payload.json`

The runner writes:

- `bounded_analysis_execution_summary.json`
- `bounded_frame_analysis.json`
- `bounded_analysis_product_payload.json`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`
- `batch_outcome_analysis.json/md`

- [x] **Step 4: Verify green**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_soccernet_bounded_analysis_execution.py -q
```

Expected result: `3 passed`.

### Task 2: Generate Real Artifacts

- [x] **Step 1: Execute real bounded analysis**

Run:

```bash
python3 backend/scripts/run_football_external_soccernet_bounded_analysis_execution.py
```

Expected result:

- `goalAchieved = true`
- `primaryBlocker = null`
- `boundedAnalysisExecutionExecuted = true`
- `requestedFrameCount = 300`
- `analyzedFrameCount = 300`
- `missingFrameCount = 0`
- `unreadableFrameCount = 0`
- `nextRecommendedNextLever = football_external_soccernet_bounded_analysis_report_smoke`

### Task 3: Roadmap And Verification

- [ ] **Step 1: Update `memorybank/currentRoadmap.md`, `memorybank/activeContext.md`, `SESSION-HANDOFF.md`, and unattended status from generated truth.**

- [ ] **Step 2: Run focused verification.**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  backend/tests/test_run_football_external_soccernet_bounded_analysis_execution.py \
  backend/tests/test_run_football_external_soccernet_bounded_analysis_execution_approval.py \
  backend/tests/test_unattended_roadmap_loop.py -q

python3 -m py_compile \
  backend/scripts/run_football_external_soccernet_bounded_analysis_execution.py \
  backend/scripts/run_football_external_soccernet_bounded_analysis_execution_approval.py

runpodctl pod list --all -o json
```
