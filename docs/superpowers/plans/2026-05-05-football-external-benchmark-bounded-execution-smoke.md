# Football External Benchmark Bounded Execution Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for this batch. Keep each step checked as it is completed.

**Goal:** Execute the approved generated-truth bounded benchmark smoke and produce a cross-source result table for SoccerNet and SoccerTrack without detector evaluation, downloads, training, promotion, normal match storage mutation, or runtime-default mutation.

**Architecture:** Add a saved-artifact execution script that reads the execution approval contract, smoke case manifest, and source summary artifacts, then writes normalized benchmark smoke results and a report-ready payload. It executes only generated-truth aggregation, not detector inference.

**Tech Stack:** Python scripts, pytest, JSON artifacts under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/`.

---

### Task 1: Bounded Execution Smoke Script

**Files:**
- Create: `backend/tests/test_run_football_external_benchmark_bounded_execution_smoke.py`
- Create: `backend/scripts/run_football_external_benchmark_bounded_execution_smoke.py`

- [x] **Step 1: Write failing tests**

Create tests that verify the script:
- requires passed execution approval truth,
- reads both source smoke cases,
- emits normalized results for SoccerNet and SoccerTrack,
- writes a report-ready payload,
- keeps detector evaluation, training, promotion, downloads, normal storage mutation, and runtime mutation false,
- advances to `football_external_benchmark_report_smoke`.

- [x] **Step 2: Run tests red**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_benchmark_bounded_execution_smoke.py -q
```

Expected before implementation: import failure for `backend.scripts.run_football_external_benchmark_bounded_execution_smoke`.

- [x] **Step 3: Implement minimal script**

Implement:
- `run_football_external_benchmark_bounded_execution_smoke(...)`
- `external_benchmark_bounded_execution_summary.json`
- `bounded_execution_result_table.json`
- `cross_source_comparison_audit.json`
- `benchmark_report_payload.json`
- `execution_guardrail_audit.json`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`
- `batch_outcome_analysis.json/md`

- [x] **Step 4: Verify tests green and run live batch**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_benchmark_bounded_execution_smoke.py backend/tests/test_run_football_external_benchmark_execution_approval.py -q
python3 -m py_compile backend/scripts/run_football_external_benchmark_bounded_execution_smoke.py
python3 backend/scripts/run_football_external_benchmark_bounded_execution_smoke.py
```

- [x] **Step 5: Update handoff/status surfaces**

Update from generated truth only:
- `SESSION-HANDOFF.md`
- `memorybank/activeContext.md`
- `memorybank/progress.md`
- `backend/storage/automation/unattended_roadmap_loop_status.json`
