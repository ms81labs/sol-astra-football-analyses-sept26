# Football External SoccerNet Full Analysis Report Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the full extracted SoccerNet 224p analysis payload into a product-facing report smoke.

**Architecture:** The runner reads the full-analysis execution summary and product payload, validates that all approved frames were processed, writes a markdown report plus report payload, and routes to full-analysis lane closeout. Training, promotion, candidate-evaluation readiness, runtime-default mutation, 720p download, and archive download remain blocked.

**Tech Stack:** Python, pytest, JSON generated truth, markdown artifacts.

---

### Task 1: Full Analysis Report Smoke

**Files:**
- Create: `backend/scripts/run_football_external_soccernet_full_analysis_report_smoke.py`
- Test: `backend/tests/test_run_football_external_soccernet_full_analysis_report_smoke.py`

- [x] **Step 1: Write failing tests**
- [x] **Step 2: Implement report runner**
- [x] **Step 3: Execute real report smoke**

Generated truth:

- `goalAchieved = true`
- `primaryBlocker = null`
- `fullAnalysisReportReady = true`
- `reportedFrameCount = 146893`
- `segmentCount = 196`
- `nextRecommendedNextLever = football_external_soccernet_full_analysis_lane_closeout`
