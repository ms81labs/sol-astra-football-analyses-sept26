# V7.2 Source Robustness Default Blocker Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run `v7_2_source_robustness_default_blocker_analysis`, a saved-truth batch that separates real v7.2 default-path performance failure from stale source-robustness routing/evidence gaps.

**Architecture:** Add a compact analysis script that reads promoted-v7.2 validation artifacts, suite robustness truth, and detector-candidate promotion diagnosis. It writes a route/blocker/evidence classification and selects the next corrective family without retraining or changing runtime defaults.

**Tech Stack:** Python batch script under `backend/scripts`, focused pytest coverage, JSON/Markdown artifacts under `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/v7_2_source_robustness_default_blocker_analysis_v1`.

---

## File Structure

- Create: `backend/scripts/run_v7_2_source_robustness_default_blocker_analysis.py`
  - Reads promoted-v7.2 source-robustness validation, suite summary, suite robustness diagnosis, and suite promotion readiness.
  - Writes blocker-analysis artifacts.
- Create: `backend/tests/test_run_v7_2_source_robustness_default_blocker_analysis.py`
  - Covers stale route, real performance blocker, clear-to-default, and missing promotion truth.
- Create: `docs/superpowers/plans/2026-05-03-v7-2-source-robustness-default-blocker-analysis.md`
  - This executable plan.

## Batch Contract

- Active batch: `v7_2_source_robustness_default_blocker_analysis`
- Attempt budget: `3`
- Attempt 1 family: `default_blocker_truth_delta_analysis`
- Inputs:
  - `promoted_v7_2_source_robustness_validation_v1/promoted_v7_2_source_robustness_validation_summary.json`
  - `promoted_v7_2_source_robustness_validation_v1/source_robustness_gate_audit.json`
  - `suite_summary.json`
  - `suite_robustness_diagnosis.json`
  - `v7_2_detector_candidate_promotion_readiness.json`
- Outputs:
  - `default_blocker_analysis_summary.json`
  - `route_mismatch_audit.json`
  - `default_mutation_evidence_audit.json`
  - `source_robustness_delta_audit.json`
  - `failsafe_attempt_plan.json`
  - `decision_matrix.json`
  - `batch_outcome_analysis.json/md`

## Attempt Flow With Adaptive Failsafes

- Attempt 1: `default_blocker_truth_delta_analysis`
  - Determine whether the default blocker is real performance, stale route, or evidence gap.
  - Success if one blocker class and next family are named.

- Attempt 2: `source_robustness_route_contract_repair`
  - Use only if route mismatch is dominant.
  - Allowed next action is a source-robustness router/contract fix, not retraining.

- Attempt 3: `default_blocker_summary`
  - If evidence remains incomplete, write blocker summary and stop.
  - Select exactly one next family:
    - `v7_2_source_robustness_route_contract_fix`
    - `v7_2_default_path_edge_share_reduction`
    - `v7_2_runtime_default_change_validation`
    - `manual_review_required`

## Tasks

### Task 1: Write Failing Tests

**Files:**
- Create: `backend/tests/test_run_v7_2_source_robustness_default_blocker_analysis.py`

- [x] **Step 1: Add tests**

Create tests that synthesize source-robustness truth. Test:
- route mismatch with v7.2 controlled promotion valid selects `v7_2_source_robustness_route_contract_fix`.
- no route mismatch but blocker remains selects `v7_2_default_path_edge_share_reduction`.
- no blockers and source gate passed selects `v7_2_runtime_default_change_validation`.
- missing controlled-promotion truth selects `v7_2_promotion_readiness_validation`.
- attempt plan contains exactly three adaptive attempts.

- [x] **Step 2: Run red test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_v7_2_source_robustness_default_blocker_analysis.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `backend.scripts.run_v7_2_source_robustness_default_blocker_analysis`.

### Task 2: Implement Analysis Script

**Files:**
- Create: `backend/scripts/run_v7_2_source_robustness_default_blocker_analysis.py`

- [x] **Step 1: Implement artifact loading and audits**

Load promoted-v7.2 validation, source gate audit, suite summary, suite robustness diagnosis, and promotion readiness.

- [x] **Step 2: Implement classification**

Classify:
- missing/invalid v7.2 controlled promotion -> `v7_2_controlled_promotion_truth_missing`
- runtime mutation ready -> pass to `v7_2_runtime_default_change_validation`
- route mismatch -> `v7_2_source_robustness_route_contract_stale`
- no route mismatch but blockers remain -> `v7_2_default_path_performance_blocker`
- incomplete evidence -> `v7_2_default_blocker_evidence_gap`

- [x] **Step 3: Write artifacts and CLI**

Write all required artifacts and expose `--storage-root`, `--attempt-number`, and `--attempt-approach-family`.

### Task 3: Verify, Generate, Document, Commit

**Files:**
- Modify generated status/docs listed above.

- [x] **Step 1: Run focused tests and compile**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  backend/tests/test_run_v7_2_source_robustness_default_blocker_analysis.py \
  backend/tests/test_run_promoted_v7_2_source_robustness_validation.py \
  backend/tests/test_unattended_roadmap_loop.py -q

python3 -m py_compile \
  backend/scripts/run_v7_2_source_robustness_default_blocker_analysis.py \
  backend/scripts/run_promoted_v7_2_source_robustness_validation.py
```

- [x] **Step 2: Generate artifacts**

Run:

```bash
python3 backend/scripts/run_v7_2_source_robustness_default_blocker_analysis.py
runpodctl pod list --all -o json
```

- [x] **Step 3: Update docs/status and commit**

Update roadmap/memorybank/handoff/status from generated artifacts only, then commit.

## Self-Review

- Spec coverage: This plan diagnoses the exact blocker after promoted-v7.2 source-robustness validation.
- Failsafes: Three attempts route to contract fix, performance fix, default-change validation, or manual review.
- Placeholder scan: No placeholders remain.
- Type consistency: Artifact names and blocker names consistently use `v7_2_source_robustness_*` naming.
