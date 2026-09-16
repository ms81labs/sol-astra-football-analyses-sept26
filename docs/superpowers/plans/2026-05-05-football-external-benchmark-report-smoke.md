# Football External Benchmark Report Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for this batch. Keep each step checked as it is completed.

**Goal:** Render a report smoke from the bounded external benchmark result payload and produce a UI-ready view model without detector evaluation, downloads, training, promotion, normal match storage mutation, or runtime-default mutation.

**Architecture:** Add a saved-artifact report script that reads `football_external_benchmark_bounded_execution_smoke_v1/benchmark_report_payload.json`, writes markdown plus a compact report view model, and routes to product UI binding.

**Tech Stack:** Python scripts, pytest, Markdown/JSON artifacts under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/`.

---

### Task 1: Benchmark Report Smoke Script

**Files:**
- Create: `backend/tests/test_run_football_external_benchmark_report_smoke.py`
- Create: `backend/scripts/run_football_external_benchmark_report_smoke.py`

- [x] **Step 1: Write failing tests**

Create tests that verify the script:
- requires report-ready bounded execution payload,
- writes markdown and view-model artifacts,
- keeps all mutation/training/evaluation flags false,
- advances to `football_external_benchmark_product_ui_binding`.

- [x] **Step 2: Run tests red**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_benchmark_report_smoke.py -q
```

Expected before implementation: import failure for `backend.scripts.run_football_external_benchmark_report_smoke`.

- [x] **Step 3: Implement minimal script**

Implement:
- `run_football_external_benchmark_report_smoke(...)`
- `external_benchmark_report_smoke_summary.json`
- `external_benchmark_report.md`
- `external_benchmark_report_view_model.json`
- `report_payload_audit.json`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`
- `batch_outcome_analysis.json/md`

- [x] **Step 4: Verify tests green and run live batch**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_benchmark_report_smoke.py backend/tests/test_run_football_external_benchmark_bounded_execution_smoke.py -q
python3 -m py_compile backend/scripts/run_football_external_benchmark_report_smoke.py
python3 backend/scripts/run_football_external_benchmark_report_smoke.py
```

- [x] **Step 5: Update handoff/status surfaces**

Update from generated truth only:
- `SESSION-HANDOFF.md`
- `memorybank/activeContext.md`
- `memorybank/progress.md`
- `backend/storage/automation/unattended_roadmap_loop_status.json`
