# V7.2 Route Contract Review Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the v7.2 source-robustness route/default closeout against the two review findings before starting edge-share reduction.

**Architecture:** Add regression tests for stale default-blocker artifacts and default-route early-return precedence, then patch the route-fix closeout and source-robustness resolver. Regenerate the affected truth artifacts and update docs from generated truth.

**Tech Stack:** Python batch scripts under `backend/scripts`, pytest, JSON/Markdown generated artifacts under `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite`.

---

## File Structure

- Modify: `backend/scripts/run_v7_2_source_robustness_route_contract_fix.py`
  - Fail closed if the downstream default-blocker artifact still names `v7_2_source_robustness_route_contract_stale`.
- Modify: `backend/scripts/run_source_robustness_batch.py`
  - Include `promoted_v7_2_source_robustness_validation` in phase override handling before source-conditioned early returns.
- Modify: `backend/tests/test_run_v7_2_source_robustness_route_contract_fix.py`
  - Add stale downstream default-blocker regression test.
- Modify: `backend/tests/test_run_source_robustness_batch.py`
  - Add default early-return precedence regression test.

## Tasks

### Task 1: Write Failing Tests

- [x] **Step 1: Add route-fix stale default-blocker test**

Test that the route-fix script does not pass when source route is no longer stale but the default-blocker summary still says `v7_2_source_robustness_route_contract_stale`.

- [x] **Step 2: Add source-robustness early-return test**

Test that `promoted_v7_2_source_robustness_validation` beats `promote_source_conditioned_edge_share_repair` even when stale evaluation evidence is absent.

- [x] **Step 3: Run red tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  backend/tests/test_run_v7_2_source_robustness_route_contract_fix.py::test_route_contract_fix_blocks_when_default_blocker_analysis_still_names_route_stale \
  backend/tests/test_run_source_robustness_batch.py::test_source_robustness_route_prefers_v7_2_promoted_validation_over_default_source_conditioned_return -q
```

Expected: both tests fail before implementation.

### Task 2: Patch Code

- [x] **Step 1: Harden route-fix classification**

Treat default-blocker route stale, route-fix next lever, or stale default route mismatch as a route-stale failure.

- [x] **Step 2: Harden phase override handling**

Add `RECOMMENDED_NEXT_LEVER_PROMOTED_V7_2_SOURCE_ROBUSTNESS_VALIDATION` to the source-robustness phase override set.

- [x] **Step 3: Run green tests**

Run the two focused tests and confirm they pass.

### Task 3: Verify, Regenerate, Document, Commit

- [x] **Step 1: Run focused verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  backend/tests/test_run_source_robustness_batch.py \
  backend/tests/test_run_v7_2_source_robustness_route_contract_fix.py \
  backend/tests/test_unattended_roadmap_loop.py -q
```

- [x] **Step 2: Regenerate route-fix truth**

Run:

```bash
python3 backend/scripts/run_v7_2_source_robustness_route_contract_fix.py
```

- [x] **Step 3: Compile, validate JSON, close RunPod, commit**

Run compile and JSON validation commands, check `runpodctl pod list --all -o json`, update docs/status if generated truth changes, and commit.

## Self-Review

- Spec coverage: Both code-review findings are covered by failing tests.
- Failsafes: The closeout now refuses false success when downstream truth remains stale.
- Placeholder scan: No placeholders remain.
- Type consistency: Route names match the existing generated truth constants.
