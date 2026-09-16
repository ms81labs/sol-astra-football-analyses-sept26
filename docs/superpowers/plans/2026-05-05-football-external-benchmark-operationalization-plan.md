# Football External Benchmark Operationalization Plan

> **For agentic workers:** Use TDD for implementation. Keep each step checked as it is completed.

**Goal:** Convert the closed external benchmark lane into an actionable product/engineering operationalization plan without executing detector evaluation, downloading data/video, training, promotion, normal match storage mutation, candidate readiness, or runtime-default mutation.

**Architecture:** Read `football_external_benchmark_lane_closeout_v1` generated truth. Write a product decision contract, stage-gate transition plan, roadmap milestones, risk register, and closeout-derived summary under `football_external_benchmark_operationalization_plan_v1`.

**Failsafes:**
- Attempt 1 `external_benchmark_operationalization_plan`: produce the plan from closed lane truth.
- Attempt 2 `external_benchmark_operationalization_contract_repair`: repair only plan/contract derivation if the closeout is valid but derived artifacts are incomplete.
- Attempt 3 `external_benchmark_operationalization_blocker_summary`: write blocker truth and route to exactly one next family.

---

### Task 1: Operationalization Planning

**Files:**
- Create: `backend/tests/test_run_football_external_benchmark_operationalization_plan.py`
- Create: `backend/scripts/run_football_external_benchmark_operationalization_plan.py`

- [x] **Step 1: Write failing tests**

Verify:
- closed lane truth is required,
- operationalization artifacts are written,
- source count and product routes are preserved,
- no evaluation/training/download/promotion/runtime mutation flags flip,
- next lever is `football_external_benchmark_product_decision_surface`.

- [x] **Step 2: Run tests red**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_benchmark_operationalization_plan.py -q
```

- [x] **Step 3: Implement saved-artifact script**

Write:
- `external_benchmark_operationalization_summary.json`
- `benchmark_operationalization_plan.json`
- `product_decision_surface_contract.json`
- `stage_gate_transition_plan.json`
- `risk_register.json`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`
- `batch_outcome_analysis.json/md`

- [x] **Step 4: Verify and run live batch**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_benchmark_operationalization_plan.py -q
python3 -m py_compile backend/scripts/run_football_external_benchmark_operationalization_plan.py
python3 backend/scripts/run_football_external_benchmark_operationalization_plan.py
```

- [x] **Step 5: Update status surfaces**

Update:
- `SESSION-HANDOFF.md`
- `memorybank/activeContext.md`
- `memorybank/progress.md`
- `backend/storage/automation/unattended_roadmap_loop_status.json`
