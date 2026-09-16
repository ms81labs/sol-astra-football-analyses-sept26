# Football External Benchmark Product Decision Surface Plan

> **For agentic workers:** Use TDD for implementation. Keep each step checked as it is completed.

**Goal:** Produce a route-ready, read-only product decision surface from the external benchmark operationalization plan. It must help humans understand what the external benchmark lane proves, what it does not prove, and which next gates are allowed.

**Architecture:** Read `football_external_benchmark_operationalization_plan_v1`. Write a view model, render smoke, recommendation matrix, guardrail audit, route contract, and generated summary under `football_external_benchmark_product_decision_surface_v1`.

**Failsafes:**
- Attempt 1 `external_benchmark_product_decision_surface`: build the read-only surface from operationalization truth.
- Attempt 2 `external_benchmark_product_decision_surface_contract_repair`: repair only derived view model/contract if source truth is valid.
- Attempt 3 `external_benchmark_product_decision_surface_blocker_summary`: write blocker truth and select exactly one next family.

---

### Task 1: Decision Surface Artifact

**Files:**
- Create: `backend/tests/test_run_football_external_benchmark_product_decision_surface.py`
- Create: `backend/scripts/run_football_external_benchmark_product_decision_surface.py`

- [x] **Step 1: Write failing tests**

Verify:
- operationalization truth is required,
- route-ready view model and HTML are written,
- recommendation matrix carries the correct next design/governance levers,
- guardrails remain false for detector evaluation, training, promotion, runtime mutation, downloads, candidate readiness, and normal match storage mutation,
- next lever is `football_external_benchmark_product_decision_surface_route_implementation`.

- [x] **Step 2: Run tests red**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_benchmark_product_decision_surface.py -q
```

- [x] **Step 3: Implement saved-artifact script**

Write:
- `external_benchmark_product_decision_surface_summary.json`
- `product_decision_surface_view_model.json`
- `product_decision_surface_render_smoke.html`
- `product_decision_surface_route_contract.json`
- `benchmark_decision_recommendation_matrix.json`
- `guardrail_status_audit.json`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`
- `batch_outcome_analysis.json/md`

- [x] **Step 4: Verify and run live batch**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_benchmark_product_decision_surface.py -q
python3 -m py_compile backend/scripts/run_football_external_benchmark_product_decision_surface.py
python3 backend/scripts/run_football_external_benchmark_product_decision_surface.py
```

- [x] **Step 5: Update status surfaces**

Update from generated truth:
- `SESSION-HANDOFF.md`
- `memorybank/activeContext.md`
- `memorybank/progress.md`
- `backend/storage/automation/unattended_roadmap_loop_status.json`
