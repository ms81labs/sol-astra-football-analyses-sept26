# Football External Benchmark Execution Approval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for this batch. Keep each step checked as it is completed.

**Goal:** Approve one bounded external benchmark smoke execution from the passed cross-source harness smoke without running detector evaluation, downloading data, training, promotion, normal match storage mutation, or runtime-default mutation.

**Architecture:** Add a saved-artifact approval script that reads `football_external_benchmark_harness_smoke_v1`, verifies the smoke contract is clean, writes an explicit bounded execution approval contract, and routes to the future execution-smoke batch. This is an approval gate only.

**Tech Stack:** Python scripts, pytest, JSON artifacts under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/`.

---

### Task 1: Execution Approval Script

**Files:**
- Create: `backend/tests/test_run_football_external_benchmark_execution_approval.py`
- Create: `backend/scripts/run_football_external_benchmark_execution_approval.py`

- [x] **Step 1: Write failing tests**

Create tests that verify the script:
- requires passed harness smoke truth,
- approves only bounded generated-truth smoke execution,
- writes execution approval contract and scope audit,
- keeps detector evaluation, training, promotion, downloads, normal storage mutation, and runtime mutation false,
- advances to `football_external_benchmark_bounded_execution_smoke`.

- [x] **Step 2: Run tests red**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_benchmark_execution_approval.py -q
```

Expected before implementation: import failure for `backend.scripts.run_football_external_benchmark_execution_approval`.

- [x] **Step 3: Implement minimal script**

Implement:
- `run_football_external_benchmark_execution_approval(...)`
- `external_benchmark_execution_approval_summary.json`
- `external_benchmark_execution_approval_contract.json`
- `execution_scope_audit.json`
- `execution_guardrail_audit.json`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`
- `batch_outcome_analysis.json/md`

- [x] **Step 4: Verify tests green and run live batch**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_benchmark_execution_approval.py backend/tests/test_run_football_external_benchmark_harness_smoke.py -q
python3 -m py_compile backend/scripts/run_football_external_benchmark_execution_approval.py
python3 backend/scripts/run_football_external_benchmark_execution_approval.py
```

- [x] **Step 5: Update handoff/status surfaces**

Update from generated truth only:
- `SESSION-HANDOFF.md`
- `memorybank/activeContext.md`
- `memorybank/progress.md`
- `backend/storage/automation/unattended_roadmap_loop_status.json`
