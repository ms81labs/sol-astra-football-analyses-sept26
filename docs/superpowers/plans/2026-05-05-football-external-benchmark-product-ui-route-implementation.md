# Football External Benchmark Product UI Route Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for this batch. Keep each step checked as it is completed.

**Goal:** Serve the external benchmark product view model and HTML report through read-only FastAPI routes without detector evaluation, downloads, training, promotion, normal match storage mutation, or runtime-default mutation.

**Architecture:** Add `/api/external/benchmark/report` and `/external/benchmark/report` to `backend/app/main.py`, plus a saved-artifact route-smoke script that exercises both routes through ASGI and writes route truth.

**Tech Stack:** FastAPI, httpx ASGI transport, Python scripts, pytest, JSON/HTML artifacts under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/`.

---

### Task 1: Product UI Route Implementation

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_run_football_external_benchmark_product_ui_route_implementation.py`
- Create: `backend/scripts/run_football_external_benchmark_product_ui_route_implementation.py`

- [x] **Step 1: Write failing tests**

Create tests that verify:
- route script requires a passed product UI binding,
- API route returns the saved benchmark product view model,
- HTML route returns the saved render smoke,
- all mutation/training/evaluation flags remain false,
- next lever is `football_external_benchmark_lane_closeout`.

- [x] **Step 2: Run tests red**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_benchmark_product_ui_route_implementation.py -q
```

Expected before implementation: import failure for `backend.scripts.run_football_external_benchmark_product_ui_route_implementation`.

- [x] **Step 3: Implement minimal route and script**

Implement:
- FastAPI route loaders in `backend/app/main.py`
- `run_football_external_benchmark_product_ui_route_implementation(...)`
- `external_benchmark_product_ui_route_implementation_summary.json`
- `external_benchmark_product_ui_route_smoke_audit.json`
- `external_benchmark_product_ui_route_response_fixture.json`
- `external_benchmark_product_ui_route_rendered.html`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`
- `batch_outcome_analysis.json/md`

- [x] **Step 4: Verify tests green and run live batch**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_benchmark_product_ui_route_implementation.py backend/tests/test_run_football_external_benchmark_product_ui_binding.py -q
python3 -m py_compile backend/app/main.py backend/scripts/run_football_external_benchmark_product_ui_route_implementation.py
python3 backend/scripts/run_football_external_benchmark_product_ui_route_implementation.py
```

- [x] **Step 5: Update handoff/status surfaces**

Update from generated truth only:
- `SESSION-HANDOFF.md`
- `memorybank/activeContext.md`
- `memorybank/progress.md`
- `backend/storage/automation/unattended_roadmap_loop_status.json`
