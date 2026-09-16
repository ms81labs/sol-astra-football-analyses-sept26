# Football External SoccerNet Full Analysis Lane Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the full extracted SoccerNet 224p analysis lane and prepare product integration as the next step.

**Architecture:** The closeout reads the full-analysis report smoke truth, writes a capability matrix, remaining gap analysis, and product-integration prep contract, then routes to full-analysis product integration. It does not train, promote, mark candidate evaluation ready, mutate runtime defaults, download 720p, or download the archive.

**Tech Stack:** Python, pytest, JSON generated truth.

---

### Task 1: Full Analysis Lane Closeout

**Files:**
- Create: `backend/scripts/run_football_external_soccernet_full_analysis_lane_closeout.py`
- Test: `backend/tests/test_run_football_external_soccernet_full_analysis_lane_closeout.py`

- [x] **Step 1: Write failing tests**
- [x] **Step 2: Implement closeout runner**
- [x] **Step 3: Execute real closeout**

Generated truth:

- `goalAchieved = true`
- `primaryBlocker = null`
- `fullAnalysisLaneClosed = true`
- `reportedFrameCount = 146893`
- `segmentCount = 196`
- `fullAnalysisProductIntegrationReady = true`
- `nextRecommendedNextLever = football_external_soccernet_full_analysis_product_integration`
