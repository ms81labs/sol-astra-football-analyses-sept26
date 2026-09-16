# Football External SoccerNet Full Analysis Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the approved full-frame analysis pass over the extracted SoccerNet 224p video member.

**Architecture:** The runner reads the full-analysis approval contract, opens the approved 224p MP4, processes every approved frame, writes aggregate frame-signal metrics and 30-second timeline segment summaries, then routes to report smoke. It does not train, promote, mark candidate evaluation ready, mutate runtime defaults, download 720p, or download the archive.

**Tech Stack:** Python, OpenCV, pytest, JSON generated truth artifacts.

---

### Task 1: Full Analysis Execution Runner

**Files:**
- Create: `backend/scripts/run_football_external_soccernet_full_analysis_execution.py`
- Test: `backend/tests/test_run_football_external_soccernet_full_analysis_execution.py`

- [x] **Step 1: Write failing tests**

Cover all-frame execution, approval blocker, and three adaptive attempt families.

- [x] **Step 2: Verify red**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_soccernet_full_analysis_execution.py -q
```

Expected initial result: import failure for missing runner.

- [x] **Step 3: Implement runner**

Write:

- `full_analysis_execution_summary.json`
- `full_video_frame_signal_summary.json`
- `full_analysis_timeline_segments.json`
- `full_analysis_product_payload.json`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`
- `batch_outcome_analysis.json/md`

- [x] **Step 4: Execute real full-video pass**

Run:

```bash
python3 backend/scripts/run_football_external_soccernet_full_analysis_execution.py
```

Expected generated truth:

- `goalAchieved = true`
- `primaryBlocker = null`
- `processedFrameCount = 146893`
- `unreadableFrameCount = 0`
- `segmentCount = 196`
- `nextRecommendedNextLever = football_external_soccernet_full_analysis_report_smoke`
