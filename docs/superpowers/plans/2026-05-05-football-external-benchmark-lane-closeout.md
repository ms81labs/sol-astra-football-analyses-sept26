# Football External Benchmark Lane Closeout Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for this batch. Keep each step checked as it is completed.

**Goal:** Close the external benchmark lane from generated truth after the benchmark report product API/HTML routes are live, without detector evaluation, data/video download, training, promotion, normal match storage mutation, candidate readiness, or runtime-default mutation.

**Architecture:** Read the closed SoccerNet and SoccerTrack source-lane truth plus the benchmark harness/report/UI-route truth. Write a capability matrix, evidence index, remaining-gap analysis, and closeout summary under `football_external_benchmark_lane_closeout_v1`.

**Tech Stack:** Python saved-artifact scripts, pytest, JSON/Markdown truth artifacts.

---

### Task 1: Benchmark Lane Closeout

**Files:**
- Create: `backend/tests/test_run_football_external_benchmark_lane_closeout.py`
- Create: `backend/scripts/run_football_external_benchmark_lane_closeout.py`

- [x] **Step 1: Write failing tests**

Verify the closeout:
- requires both source lanes and all benchmark chain summaries,
- writes a capability matrix and evidence index,
- preserves all no-mutation/no-training/no-evaluation flags,
- selects `football_external_benchmark_operationalization_plan` after success,
- includes three adaptive attempt families.

- [x] **Step 2: Run tests red**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_benchmark_lane_closeout.py -q
```

- [x] **Step 3: Implement closeout script**

Write:
- `external_benchmark_lane_closeout_summary.json`
- `external_benchmark_capability_matrix.json`
- `external_benchmark_evidence_index.json`
- `remaining_gap_analysis.json`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`
- `batch_outcome_analysis.json/md`

- [x] **Step 4: Verify and run live batch**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_benchmark_lane_closeout.py -q
python3 -m py_compile backend/scripts/run_football_external_benchmark_lane_closeout.py
python3 backend/scripts/run_football_external_benchmark_lane_closeout.py
```

- [x] **Step 5: Update handoff/status surfaces**

Update from generated truth only:
- `SESSION-HANDOFF.md`
- `memorybank/activeContext.md`
- `memorybank/progress.md`
- `backend/storage/automation/unattended_roadmap_loop_status.json`
