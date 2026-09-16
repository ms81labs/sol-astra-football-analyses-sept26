# V7.2 Source Robustness Route Contract Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the stale source-robustness route so a controlled-promoted v7.2 candidate no longer routes back to detector-candidate evaluation.

**Architecture:** Patch the source-robustness route resolver to let newer validated promotion truth supersede stale evaluation truth. Add a saved-artifact route-fix closeout script that records the before/after route state, then regenerate source robustness, promoted-v7.2 validation, and default-blocker analysis to prove the route is no longer stale.

**Tech Stack:** Python batch scripts under `backend/scripts`, focused pytest coverage, JSON/Markdown artifacts under `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/v7_2_source_robustness_route_contract_fix_v1`.

---

## File Structure

- Modify: `backend/scripts/run_source_robustness_batch.py`
  - Add v7.2 promoted-source-robustness route constant.
  - Let validated candidate promotion truth route before stale evaluation truth.
- Create: `backend/scripts/run_v7_2_source_robustness_route_contract_fix.py`
  - Reads regenerated source robustness/default-blocker truth and writes route-fix closeout artifacts.
- Modify: `backend/tests/test_run_source_robustness_batch.py`
  - Add focused resolver and run-level regression tests.
- Create: `backend/tests/test_run_v7_2_source_robustness_route_contract_fix.py`
  - Cover route-fix closeout classification.

## Batch Contract

- Active batch: `v7_2_source_robustness_route_contract_fix`
- Attempt budget: `3`
- Attempt 1 family: `source_robustness_route_contract_refresh`
- Attempt 2 family: `source_robustness_default_gate_contract_repair`
- Attempt 3 family: `source_robustness_route_contract_blocker_summary`
- No training.
- No runtime-default mutation.
- No promotion-readiness reclassification.

## Tasks

### Task 1: Write Failing Route Tests

**Files:**
- Modify: `backend/tests/test_run_source_robustness_batch.py`

- [x] **Step 1: Add stale-route regression tests**

Add one direct resolver test and one generated-suite test proving v7.2 promotion-readiness truth beats stale `evaluate_touchline_detector_candidate` evaluation truth.

- [x] **Step 2: Run red tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  backend/tests/test_run_source_robustness_batch.py::test_source_robustness_route_prefers_v7_2_promoted_validation_over_stale_evaluation \
  backend/tests/test_run_source_robustness_batch.py::test_run_source_robustness_batch_routes_v7_2_promotion_readiness_before_stale_v7_evaluation -q
```

Expected: FAIL because the current resolver still returns `evaluate_touchline_detector_candidate`.

### Task 2: Patch Route Resolver

**Files:**
- Modify: `backend/scripts/run_source_robustness_batch.py`

- [x] **Step 1: Add v7.2 route constant**

Add `RECOMMENDED_NEXT_LEVER_PROMOTED_V7_2_SOURCE_ROBUSTNESS_VALIDATION = "promoted_v7_2_source_robustness_validation"`.

- [x] **Step 2: Prefer validated promotion truth**

Before stale evaluation routing, return the v7.2 promoted-source-robustness route when promotion truth is validated and the promoted candidate version is at least the stale evaluation candidate version.

- [x] **Step 3: Run green tests**

Run the two focused route tests and confirm they pass.

### Task 3: Add Route-Fix Closeout Script

**Files:**
- Create: `backend/scripts/run_v7_2_source_robustness_route_contract_fix.py`
- Create: `backend/tests/test_run_v7_2_source_robustness_route_contract_fix.py`

- [x] **Step 1: Write closeout tests**

Test that route-fix truth passes when source robustness no longer recommends `evaluate_touchline_detector_candidate` and promoted-v7.2 validation no longer reports route mismatch.

- [x] **Step 2: Implement closeout script**

Write summary, route-contract audit, decision matrix, failsafe attempt plan, and batch outcome artifacts.

- [x] **Step 3: Run closeout tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_v7_2_source_robustness_route_contract_fix.py -q
```

### Task 4: Regenerate Truth, Document, Commit

**Files:**
- Modify generated source robustness artifacts.
- Modify memorybank/handoff/status docs from generated truth.

- [x] **Step 1: Regenerate source robustness route truth**

Run:

```bash
python3 backend/scripts/run_source_robustness_batch.py
python3 backend/scripts/run_promoted_v7_2_source_robustness_validation.py
python3 backend/scripts/run_v7_2_source_robustness_default_blocker_analysis.py
python3 backend/scripts/run_v7_2_source_robustness_route_contract_fix.py
```

- [x] **Step 2: Verify**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  backend/tests/test_run_source_robustness_batch.py \
  backend/tests/test_run_promoted_v7_2_source_robustness_validation.py \
  backend/tests/test_run_v7_2_source_robustness_default_blocker_analysis.py \
  backend/tests/test_run_v7_2_source_robustness_route_contract_fix.py \
  backend/tests/test_unattended_roadmap_loop.py -q

python3 -m py_compile \
  backend/scripts/run_source_robustness_batch.py \
  backend/scripts/run_promoted_v7_2_source_robustness_validation.py \
  backend/scripts/run_v7_2_source_robustness_default_blocker_analysis.py \
  backend/scripts/run_v7_2_source_robustness_route_contract_fix.py

runpodctl pod list --all -o json
```

- [x] **Step 3: Update docs/status and commit**

Update active docs from generated artifacts only and commit.

## Self-Review

- Spec coverage: The plan fixes the exact route blocker and proves it through regenerated suite truth.
- Failsafes: Three attempts route to route refresh, default-gate repair, or blocker summary.
- Placeholder scan: No placeholders remain.
- Type consistency: Route names match generated blocker-analysis truth.
