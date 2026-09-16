# Football External SoccerNet Bounded Analysis Lane Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the 300-frame bounded SoccerNet analysis lane and prepare the next full-analysis execution approval gate without executing full analysis.

**Architecture:** The closeout reads the bounded report smoke truth, writes a capability matrix, remaining gap analysis, and full-analysis approval prep artifact. It marks the bounded lane closed while keeping full analysis unapproved and unexecuted.

**Tech Stack:** Python, pytest, JSON generated truth.

---

### Task 1: Lane Closeout Runner

**Files:**
- Create: `backend/scripts/run_football_external_soccernet_bounded_analysis_lane_closeout.py`
- Test: `backend/tests/test_run_football_external_soccernet_bounded_analysis_lane_closeout.py`

- [x] **Step 1: Write failing tests**

Cover successful closeout, missing report blocker, and three adaptive attempt families.

- [x] **Step 2: Verify red**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_soccernet_bounded_analysis_lane_closeout.py -q
```

Expected initial result: import failure for missing runner.

- [x] **Step 3: Implement runner**

Write:

- `bounded_analysis_lane_closeout_summary.json`
- `bounded_analysis_capability_matrix.json`
- `remaining_gap_analysis.json`
- `full_analysis_execution_approval_contract_prep.json`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`
- `batch_outcome_analysis.json/md`

- [x] **Step 4: Execute real batch**

Run:

```bash
python3 backend/scripts/run_football_external_soccernet_bounded_analysis_lane_closeout.py
```

Expected:

- `goalAchieved = true`
- `primaryBlocker = null`
- `boundedAnalysisLaneClosed = true`
- `reportedFrameCount = 300`
- `fullAnalysisExecutionApprovalReady = true`
- `fullAnalysisExecutionApproved = false`
- `fullAnalysisExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_full_analysis_execution_approval`
