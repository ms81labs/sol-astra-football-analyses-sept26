# Football External SoccerNet Bounded Analysis Report Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the bounded 300-frame SoccerNet analysis payload into a product-facing report smoke without claiming full analysis readiness.

**Architecture:** The report smoke reads the bounded execution summary and product payload, validates the 300-frame bounded result, writes a concise markdown report and JSON report payload, and routes to bounded lane closeout.

**Tech Stack:** Python, pytest, JSON generated truth, markdown artifacts.

---

### Task 1: Report Smoke Runner

**Files:**
- Create: `backend/scripts/run_football_external_soccernet_bounded_analysis_report_smoke.py`
- Test: `backend/tests/test_run_football_external_soccernet_bounded_analysis_report_smoke.py`

- [x] **Step 1: Write failing tests**

Cover report rendering, missing execution blocker, and three failsafe families.

- [x] **Step 2: Verify red**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_soccernet_bounded_analysis_report_smoke.py -q
```

Expected initial result: import failure for missing runner.

- [x] **Step 3: Implement runner**

Write:

- `bounded_analysis_report_smoke_summary.json`
- `bounded_analysis_report_payload.json`
- `bounded_analysis_report.md`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`
- `batch_outcome_analysis.json/md`

- [x] **Step 4: Verify green and execute real batch**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_soccernet_bounded_analysis_report_smoke.py -q
python3 backend/scripts/run_football_external_soccernet_bounded_analysis_report_smoke.py
```

Expected generated truth:

- `goalAchieved = true`
- `primaryBlocker = null`
- `boundedAnalysisReportReady = true`
- `reportedFrameCount = 300`
- `fullAnalysisReady = false`
- `nextRecommendedNextLever = football_external_soccernet_bounded_analysis_lane_closeout`
