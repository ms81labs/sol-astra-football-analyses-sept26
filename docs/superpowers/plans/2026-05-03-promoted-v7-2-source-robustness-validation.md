# Promoted V7.2 Source Robustness Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run `promoted_v7_2_source_robustness_validation`, the gate that decides whether the controlled-promoted v7.2 candidate can move toward runtime-default validation or remains blocked by source robustness.

**Architecture:** Add a saved-artifact validation script that reads the v7.2 promotion-readiness truth, controlled runtime registry, suite-level source-robustness truth, and suite-level v7.2 promotion-readiness artifact. It writes a source-robustness/default-change verdict without retraining, without changing runtime defaults, and without running a new external benchmark.

**Tech Stack:** Python batch script under `backend/scripts`, focused pytest coverage, JSON/Markdown artifacts under `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/promoted_v7_2_source_robustness_validation_v1`.

---

## File Structure

- Create: `backend/scripts/run_promoted_v7_2_source_robustness_validation.py`
  - Reads v7.2 controlled-promotion truth and current source-robustness truth.
  - Writes source-robustness validation artifacts and a next-lever decision.
- Create: `backend/tests/test_run_promoted_v7_2_source_robustness_validation.py`
  - Covers blocker, clear-to-default-validation, stale registry, and three-attempt failsafe outcomes.
- Create: `docs/superpowers/plans/2026-05-03-promoted-v7-2-source-robustness-validation.md`
  - This executable plan.
- Update after generation:
  - `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/promoted_v7_2_source_robustness_validation_v1/*`
  - `backend/storage/automation/unattended_roadmap_loop_status.json`
  - `memorybank/activeContext.md`
  - `memorybank/currentRoadmap.md`
  - `memorybank/progress.md`
  - `memorybank/features/source-robustness-lane.md`
  - `SESSION-HANDOFF.md`
  - `docs/superpowers/plans/2026-04-23-promoted-v6-failing-source-robustness-validation.md`

## Batch Contract

- Active batch: `promoted_v7_2_source_robustness_validation`
- Attempt budget: `3`
- Attempt 1 family: `promoted_v7_2_controlled_source_robustness_validation`
- Inputs:
  - `trained_detector_candidates/touchline_detector_candidate_v7/v7_2_promotion_readiness_validation_v1/v7_2_promotion_readiness_summary.json`
  - `runtime/promoted_touchline_detector_candidate.json`
  - `benchmark_suites/frozen-viable-baseline-slice-suite/v7_2_detector_candidate_promotion_readiness.json`
  - `benchmark_suites/frozen-viable-baseline-slice-suite/suite_summary.json`
- Outputs:
  - `promoted_v7_2_source_robustness_validation_summary.json`
  - `controlled_registry_audit.json`
  - `source_robustness_gate_audit.json`
  - `runtime_default_blocker_audit.json`
  - `failsafe_attempt_plan.json`
  - `decision_matrix.json`
  - `batch_outcome_analysis.json/md`

## Attempt Flow With Adaptive Failsafes

- Attempt 1: `promoted_v7_2_controlled_source_robustness_validation`
  - Validate that the controlled runtime registry points to v7.2 and that v7.2 promotion-readiness truth passed.
  - Read current source-robustness truth.
  - If no source-robustness blockers remain, select `v7_2_runtime_default_change_validation`.
  - If blockers remain, select `v7_2_source_robustness_default_blocker_analysis`.

- Attempt 2: `v7_2_source_robustness_route_repair`
  - Use only if the source-robustness suite has stale routing but the registry/promotion artifacts are valid.
  - Allowed repairs:
    - write explicit route-mismatch diagnostics
    - preserve v7.2 controlled-promotion truth as authoritative for this validation batch
  - Not allowed:
    - runtime-default mutation
    - retraining
    - external benchmark execution.

- Attempt 3: `v7_2_runtime_default_blocker_summary`
  - If source robustness still blocks, write blocker summary and stop.
  - Select exactly one next family:
    - `v7_2_source_robustness_default_blocker_analysis`
    - `v7_2_runtime_default_change_validation`
    - `v7_2_runtime_registry_contract_fix`
    - `manual_review_required`

## Tasks

### Task 1: Write Failing Tests

**Files:**
- Create: `backend/tests/test_run_promoted_v7_2_source_robustness_validation.py`

- [x] **Step 1: Add tests**

Create tests that synthesize v7.2 promotion readiness, registry, and source-robustness truth. Test:
- blocker case: `failing_source_not_viable` keeps default mutation blocked and routes to `v7_2_source_robustness_default_blocker_analysis`.
- clean case: no blockers and passed source gate routes to `v7_2_runtime_default_change_validation`.
- stale registry case: registry not v7.2 routes to `v7_2_runtime_registry_contract_fix`.
- attempt plan contains exactly three adaptive attempts.

- [x] **Step 2: Run red test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_promoted_v7_2_source_robustness_validation.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `backend.scripts.run_promoted_v7_2_source_robustness_validation`.

### Task 2: Implement Validation Script

**Files:**
- Create: `backend/scripts/run_promoted_v7_2_source_robustness_validation.py`

- [x] **Step 1: Implement artifact loading and audits**

Read v7.2 promotion readiness, controlled runtime registry, suite promotion readiness, and suite summary. Audit registry identity, promotion readiness, source-robustness blockers, and default-mutation status.

- [x] **Step 2: Implement classification**

Classify:
- stale registry -> `v7_2_runtime_registry_contract_gap`
- missing promotion truth -> `v7_2_promotion_readiness_truth_missing`
- source blockers present -> `v7_2_source_robustness_default_mutation_blocked`
- no blockers -> pass to `v7_2_runtime_default_change_validation`

- [x] **Step 3: Write artifacts and CLI**

Write all required artifacts under `promoted_v7_2_source_robustness_validation_v1/` and expose `--storage-root`, `--attempt-number`, and `--attempt-approach-family`.

### Task 3: Verify, Generate, Document, Commit

**Files:**
- Modify generated status/docs listed above.

- [x] **Step 1: Run focused tests and compile**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  backend/tests/test_run_promoted_v7_2_source_robustness_validation.py \
  backend/tests/test_run_v7_2_promotion_readiness_validation.py \
  backend/tests/test_unattended_roadmap_loop.py -q

python3 -m py_compile \
  backend/scripts/run_promoted_v7_2_source_robustness_validation.py \
  backend/scripts/run_v7_2_promotion_readiness_validation.py
```

- [x] **Step 2: Generate artifacts**

Run:

```bash
python3 backend/scripts/run_promoted_v7_2_source_robustness_validation.py
python3 backend/scripts/run_source_robustness_batch.py
runpodctl pod list --all -o json
```

Expected RunPod output: `[]`.

- [x] **Step 3: Update docs/status and commit**

Update roadmap/memorybank/handoff/status from generated artifacts only, then commit:

```bash
git add backend/scripts/run_promoted_v7_2_source_robustness_validation.py \
  backend/tests/test_run_promoted_v7_2_source_robustness_validation.py \
  docs/superpowers/plans/2026-05-03-promoted-v7-2-source-robustness-validation.md \
  docs/superpowers/plans/2026-04-23-promoted-v6-failing-source-robustness-validation.md \
  memorybank/activeContext.md memorybank/currentRoadmap.md memorybank/progress.md \
  memorybank/features/source-robustness-lane.md SESSION-HANDOFF.md
git add -f backend/storage/automation/unattended_roadmap_loop_status.json \
  backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/promoted_v7_2_source_robustness_validation_v1
git diff --cached --check
git commit -m "Validate promoted v7.2 source robustness"
```

## Self-Review

- Spec coverage: This plan continues after v7.2 controlled promotion and determines the default-change blocker from generated source-robustness truth.
- Failsafes: Three attempts adapt to registry contract gaps, route mismatches, and persistent source blockers.
- Placeholder scan: No placeholders remain.
- Type consistency: Batch names, blockers, next levers, and artifact paths consistently use `promoted_v7_2_*` and `v7_2_*` naming.
