# Football External Benchmark Real Evaluation Design Plan

> **For agentic workers:** Use TDD for implementation. Keep each step checked as it is completed.

**Goal:** Turn the live read-only benchmark decision route into a finite real-evaluation design contract without executing the benchmark, downloading more data, training, promotion, candidate readiness, normal match storage mutation, or runtime-default mutation.

**Architecture:** Read `football_external_benchmark_product_decision_surface_route_implementation_v1`. Write the finite source scope, metric contract, approval gate, storage budget, cleanup audit, and next-five-step roadmap under `football_external_benchmark_real_evaluation_design_v1`.

**Failsafes:**
- Attempt 1 `external_benchmark_real_evaluation_design`: write finite design contracts from decision-route truth.
- Attempt 2 `external_benchmark_real_evaluation_design_contract_repair`: repair only design-contract derivation if route truth is valid.
- Attempt 3 `external_benchmark_real_evaluation_design_blocker_summary`: write blocker truth and select exactly one next family.

---

### Task 1: Real Evaluation Design

**Files:**
- Create: `backend/tests/test_run_football_external_benchmark_real_evaluation_design.py`
- Create: `backend/scripts/run_football_external_benchmark_real_evaluation_design.py`

- [x] **Step 1: Write failing tests**
- [x] **Step 2: Run tests red**
- [x] **Step 3: Implement saved-artifact design script**
- [x] **Step 4: Run live batch and focused verification**
- [x] **Step 5: Update status surfaces**
