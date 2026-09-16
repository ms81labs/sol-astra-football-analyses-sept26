# Football External Benchmark Harness Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for this batch. Keep each step checked as it is completed.

**Goal:** Execute a saved-artifact-only smoke of the cross-source external benchmark harness prepared from SoccerNet and SoccerTrack generated truth. Do not run detector evaluation, download data, train, promote, mutate normal match storage, or mutate runtime defaults.

**Architecture:** Add one script that reads `football_external_benchmark_harness_prep_v1`, verifies source artifact presence/schema, builds normalized smoke cases for both sources, emits common metric-family placeholders, and routes to an explicit execution-approval batch.

**Tech Stack:** Python scripts, pytest, JSON artifacts under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/`.

---

### Task 1: Harness Smoke Script

**Files:**
- Create: `backend/tests/test_run_football_external_benchmark_harness_smoke.py`
- Create: `backend/scripts/run_football_external_benchmark_harness_smoke.py`

- [x] **Step 1: Write failing tests**

Create tests that verify the smoke script:
- requires the prep manifest and readiness audit,
- fails closed if source artifact paths are missing,
- writes normalized smoke cases for SoccerNet and SoccerTrack,
- keeps all mutation/training/evaluation flags false,
- advances to `football_external_benchmark_execution_approval` on pass.

- [x] **Step 2: Run tests red**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_benchmark_harness_smoke.py -q
```

Expected before implementation: import failure for `backend.scripts.run_football_external_benchmark_harness_smoke`.

- [x] **Step 3: Implement minimal script**

Implement:
- `run_football_external_benchmark_harness_smoke(...)`
- `external_benchmark_smoke_summary.json`
- `source_artifact_presence_audit.json`
- `schema_version_smoke_audit.json`
- `benchmark_smoke_case_manifest.json`
- `cross_source_metric_family_smoke.json`
- `stage_gate_smoke_audit.json`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`
- `batch_outcome_analysis.json/md`

- [x] **Step 4: Verify tests green and run live batch**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_benchmark_harness_smoke.py backend/tests/test_run_football_external_benchmark_harness_prep.py -q
python3 -m py_compile backend/scripts/run_football_external_benchmark_harness_smoke.py
python3 backend/scripts/run_football_external_benchmark_harness_smoke.py
```

- [x] **Step 5: Update handoff/status surfaces**

Update from generated truth only:
- `SESSION-HANDOFF.md`
- `memorybank/activeContext.md`
- `memorybank/progress.md`
- `backend/storage/automation/unattended_roadmap_loop_status.json`
