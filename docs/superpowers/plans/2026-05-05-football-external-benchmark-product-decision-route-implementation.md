# Football External Benchmark Product Decision Route Implementation Plan

> **For agentic workers:** Use TDD for implementation. Keep each step checked as it is completed.

**Goal:** Serve the external benchmark decision surface through read-only FastAPI routes without detector evaluation, data/video download, training, promotion, normal match storage mutation, candidate readiness, or runtime-default mutation.

**Architecture:** Add `/api/external/benchmark/decision` and `/external/benchmark/decision` to `backend/app/main.py`, backed only by `football_external_benchmark_product_decision_surface_v1` saved artifacts. Add a route-smoke batch that exercises both routes via ASGI and writes generated route truth.

**Failsafes:**
- Attempt 1 `external_benchmark_product_decision_route_smoke`: smoke API/HTML routes from saved artifacts.
- Attempt 2 `external_benchmark_product_decision_route_contract_repair`: repair only route lookup/contract binding if source surface is valid.
- Attempt 3 `external_benchmark_product_decision_route_blocker_summary`: write blocker truth and select exactly one next family.

---

### Task 1: Decision Surface Routes

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_run_football_external_benchmark_product_decision_surface_route_implementation.py`
- Create: `backend/scripts/run_football_external_benchmark_product_decision_surface_route_implementation.py`

- [x] **Step 1: Write failing tests**
- [x] **Step 2: Run tests red**
- [x] **Step 3: Implement route and script**
- [x] **Step 4: Run live batch and focused verification**
- [x] **Step 5: Update status surfaces**
