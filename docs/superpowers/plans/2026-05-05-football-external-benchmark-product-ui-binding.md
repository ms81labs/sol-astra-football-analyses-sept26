# Football External Benchmark Product UI Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for this batch. Keep each step checked as it is completed.

**Goal:** Convert the external benchmark report smoke output into a product UI view model, route contract, and static render smoke without detector evaluation, downloads, training, promotion, normal match storage mutation, or runtime-default mutation.

**Architecture:** Add a saved-artifact UI binding script that reads `football_external_benchmark_report_smoke_v1`, writes a richer product view model and HTML smoke artifact, and routes to API/UI route implementation.

**Tech Stack:** Python scripts, pytest, HTML/JSON artifacts under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/`.

---

### Task 1: Product UI Binding Script

**Files:**
- Create: `backend/tests/test_run_football_external_benchmark_product_ui_binding.py`
- Create: `backend/scripts/run_football_external_benchmark_product_ui_binding.py`

- [x] **Step 1: Write failing tests**

Create tests that verify the script:
- requires passed report smoke truth,
- writes product view model, static HTML render, and route contract,
- keeps all mutation/training/evaluation flags false,
- advances to `football_external_benchmark_product_ui_route_implementation`.

- [x] **Step 2: Run tests red**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_benchmark_product_ui_binding.py -q
```

Expected before implementation: import failure for `backend.scripts.run_football_external_benchmark_product_ui_binding`.

- [x] **Step 3: Implement minimal script**

Implement:
- `run_football_external_benchmark_product_ui_binding(...)`
- `external_benchmark_product_ui_binding_summary.json`
- `external_benchmark_product_ui_view_model.json`
- `external_benchmark_product_ui_render_smoke.html`
- `external_benchmark_product_ui_route_contract.json`
- `product_ui_binding_audit.json`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`
- `batch_outcome_analysis.json/md`

- [x] **Step 4: Verify tests green and run live batch**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_benchmark_product_ui_binding.py backend/tests/test_run_football_external_benchmark_report_smoke.py -q
python3 -m py_compile backend/scripts/run_football_external_benchmark_product_ui_binding.py
python3 backend/scripts/run_football_external_benchmark_product_ui_binding.py
```

- [x] **Step 5: Update handoff/status surfaces**

Update from generated truth only:
- `SESSION-HANDOFF.md`
- `memorybank/activeContext.md`
- `memorybank/progress.md`
- `backend/storage/automation/unattended_roadmap_loop_status.json`
