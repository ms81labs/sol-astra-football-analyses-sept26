# Football External Benchmark Harness Prep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare a saved-artifact benchmark harness contract that joins the closed SoccerNet and SoccerTrack external lanes without running detector evaluation, training, promotion, video download, normal match storage mutation, or runtime-default mutation.

**Architecture:** Add a single saved-artifact batch script that reads only generated truth summaries from the existing external lanes, writes a cross-source harness manifest/capability matrix/remaining-gap analysis, and routes to a future smoke execution batch. Keep this as contract prep only; no benchmark execution happens here.

**Tech Stack:** Python scripts, pytest, JSON artifacts under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/`.

---

### Task 1: Benchmark Harness Prep Script

**Files:**
- Create: `backend/tests/test_run_football_external_benchmark_harness_prep.py`
- Create: `backend/scripts/run_football_external_benchmark_harness_prep.py`

- [x] **Step 1: Write failing tests**

Create tests that verify the script:
- requires SoccerTrack lane closeout truth,
- requires SoccerNet analysis product lane closeout truth,
- requires SoccerNet event lane closeout truth,
- writes a benchmark source manifest with both external sources,
- keeps all mutation/training/evaluation flags false,
- advances to `football_external_benchmark_harness_smoke`.

- [x] **Step 2: Run tests red**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_benchmark_harness_prep.py -q
```

Expected before implementation: import failure for `backend.scripts.run_football_external_benchmark_harness_prep`.

- [x] **Step 3: Implement minimal script**

Implement:
- `run_football_external_benchmark_harness_prep(...)`
- `external_benchmark_source_manifest.json`
- `external_benchmark_capability_matrix.json`
- `remaining_gap_analysis.json`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`
- `batch_outcome_analysis.json/md`

- [x] **Step 4: Verify tests green and run live batch**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_benchmark_harness_prep.py -q
python3 -m py_compile backend/scripts/run_football_external_benchmark_harness_prep.py
python3 backend/scripts/run_football_external_benchmark_harness_prep.py
```

- [x] **Step 5: Update handoff/status surfaces**

Update from generated truth only:
- `SESSION-HANDOFF.md`
- `memorybank/activeContext.md`
- `memorybank/progress.md`
- `backend/storage/automation/unattended_roadmap_loop_status.json`
