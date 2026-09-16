# V7.2 Promotion Readiness Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run `v7_2_promotion_readiness_validation`, a generated-truth gate that decides whether v7.2 can graduate from diagnostic non-promotion probe to controlled promotion-ready candidate.

**Architecture:** Add a saved-artifact validation script that reads v7.2 export, bounded retrain, crop guardrail, full-pipeline, and source-robustness truth. If the evidence clears strict gates, it writes candidate-local promotion-readiness artifacts, a suite-level readiness artifact, and a controlled runtime registry entry for v7.2; runtime-default mutation is evaluated separately and not executed by this batch.

**Tech Stack:** Python batch script under `backend/scripts`, focused pytest coverage, JSON/Markdown artifacts under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_promotion_readiness_validation_v1`.

---

## File Structure

- Create: `backend/scripts/run_v7_2_promotion_readiness_validation.py`
  - Reads generated v7.2 truth only.
  - Writes promotion-readiness artifacts and, on pass, a controlled runtime registry entry.
- Create: `backend/tests/test_run_v7_2_promotion_readiness_validation.py`
  - Covers clean pass, missing upstream truth, metric failures, source-robustness runtime-default blocker handling, and three-attempt failsafe plan.
- Create: `docs/superpowers/plans/2026-05-03-v7-2-promotion-readiness-validation.md`
  - This executable plan.
- Update after generation:
  - `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_promotion_readiness_validation_v1/*`
  - `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/v7_2_detector_candidate_promotion_readiness.json`
  - `backend/storage/runtime/promoted_touchline_detector_candidate.json`
  - `backend/storage/automation/unattended_roadmap_loop_status.json`
  - `memorybank/activeContext.md`
  - `memorybank/currentRoadmap.md`
  - `memorybank/progress.md`
  - `memorybank/features/source-robustness-lane.md`
  - `SESSION-HANDOFF.md`
  - `docs/superpowers/plans/2026-04-23-promoted-v6-failing-source-robustness-validation.md`

## Batch Contract

- Active batch: `v7_2_promotion_readiness_validation`
- Attempt budget: `3`
- Attempt 1 family: `controlled_candidate_promotion_readiness_validation`
- Inputs:
  - `v7_2_export_label_overlay_audit_v1/v7_2_label_overlay_audit.json`
  - `v7_2_bounded_retrain_v1/v7_2_bounded_retrain_summary.json`
  - `v7_2_crop_probe_precision_guardrail_audit_v1/v7_2_crop_probe_precision_guardrail_summary.json`
  - `v7_2_full_pipeline_non_promotion_eval_v1/v7_2_full_pipeline_non_promotion_summary.json`
  - `benchmark_suites/frozen-viable-baseline-slice-suite/suite_summary.json`
- Outputs:
  - `v7_2_promotion_readiness_summary.json`
  - `promotion_gate_audit.json`
  - `runtime_contract_audit.json`
  - `candidate_evaluation_readiness_contract.json`
  - `controlled_runtime_registry_entry.json`
  - `runtime_default_mutation_audit.json`
  - `failsafe_attempt_plan.json`
  - `decision_matrix.json`
  - `batch_outcome_analysis.json/md`
- Pass outcome:
  - `candidateReadyForEvaluation = true`
  - `promotionReady = true`
  - `promotionValidated = true`
  - `promotedForControlledRuns = true`
  - `controlledRuntimeRegistryUpdated = true`
  - `runtimeDefaultMutationEvaluated = true`
  - `runtimeDefaultMutationExecuted = false`
- Runtime-default mutation:
  - This batch may allow it only if source robustness has no blockers.
  - It never executes the runtime-default switch.

## Attempt Flow With Adaptive Failsafes

- Attempt 1: `controlled_candidate_promotion_readiness_validation`
  - Validate export, bounded retrain, guardrail, full-pipeline, checkpoint, and source-robustness evidence.
  - Success if all promotion metrics clear and no old v7 flood/artifact signatures return.
  - On success: write controlled registry entry and select `promoted_v7_2_source_robustness_validation` if runtime-default mutation remains blocked, otherwise `v7_2_runtime_default_change_validation`.

- Attempt 2: `promotion_readiness_contract_repair`
  - Use only if attempt 1 fails from generated-artifact contract problems:
    - missing summary path
    - renamed summary artifact
    - missing local checkpoint path
    - incomplete runtime contract fields
  - Allowed repairs:
    - normalize summary path lookup
    - normalize checkpoint keys
    - write blocker truth with exact missing inputs
  - Not allowed:
    - retraining
    - changing model labels
    - weakening metric thresholds
    - executing a runtime-default switch.

- Attempt 3: `promotion_readiness_blocker_summary`
  - If validation still fails, stop with blocker truth.
  - Select exactly one next family:
    - `v7_2_runtime_integration_fix`
    - `v7_2_source_robustness_refresh`
    - `v7_2_positive_diversity_refresh`
    - `v7_2_hard_negative_expansion`
    - `v7_2_training_signal_regression_debug`
    - `manual_review_required`

## Gate Criteria

- Export:
  - `goalAchieved = true`
  - `positiveCropExampleCount >= 414`
  - `positiveLabelFilesWithExactlyOneBall = positiveCropExampleCount`
  - `localHardNegativeCropCount >= 180`
  - `heldoutHardNegativeCanaryCount >= 20`
  - `splitLeakageCount = 0`
  - `canaryLeakageCount = 0`
  - `unsafeFullFrameNegativeExportCount = 0`
  - `positiveLabelRoundTripMaxErrorPx <= 1.0`
- Bounded retrain:
  - `trainingCompleted = true`
  - `checkpointContractPassed = true`
  - `inferenceUsedTrainedWeights = true`
  - `boundedTrainPositiveLocalizationHitRate >= 0.85`
  - `boundedValPositiveLocalizationHitRate >= 0.70`
  - `boundedValNegativeFalsePositiveFrameRate <= 0.05`
  - `heldoutCanaryFalsePositiveFrameRate <= 0.10`
  - `medianValPositiveConfidence > 0.10`
  - `topLeftArtifactShare = 0.0`
  - `giantBoxShare = 0.0`
- Guardrail:
  - `precisionGuardrailPassed = true`
  - `boundedValPositiveLocalizationHitRate >= 0.70`
  - `oldTopLeftArtifactFalsePositiveFrameRate = 0.0`
  - `heldoutCanaryFalsePositiveFrameRate = 0.0`
  - `nearConstantLowConfidenceFlood = false`
- Full pipeline:
  - `goalAchieved = true`
  - `checkpointContractPassed = true`
  - `pipelineCropContractMatchesTraining = true`
  - `projectionAuditPassed = true`
  - `candidateCropCoverageRate >= 0.90`
  - `sourceFrameLocalizationHitRate >= 0.90`
  - `observedBallAcceptanceRate >= 0.90`
  - `oldTopLeftArtifactFalsePositiveFrameRate = 0.0`
  - `heldoutCanaryFalsePositiveFrameRate = 0.0`
  - `sampledFrameDetectionRate <= 0.25`
  - `topLeftArtifactShare = 0.0`
  - `giantBoxShare = 0.0`

## Tasks

### Task 1: Write Failing Tests

**Files:**
- Create: `backend/tests/test_run_v7_2_promotion_readiness_validation.py`

- [x] **Step 1: Add tests**

Create tests that synthesize all required generated truth under a temp storage root. Test:
- clean v7.2 truth validates promotion readiness, updates controlled registry, and does not execute runtime-default mutation.
- source-robustness blockers keep `runtimeDefaultMutationAllowed = false` while still allowing controlled promotion.
- missing full-pipeline truth blocks with `v7_2_promotion_readiness_missing_upstream_truth`.
- full-pipeline flood regression routes to `v7_2_runtime_integration_fix`.
- validation recall failure routes to `v7_2_positive_diversity_refresh`.
- failsafe plan contains exactly three adaptive attempts.

- [x] **Step 2: Run red test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_v7_2_promotion_readiness_validation.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `backend.scripts.run_v7_2_promotion_readiness_validation`.

### Task 2: Implement Promotion Readiness Script

**Files:**
- Create: `backend/scripts/run_v7_2_promotion_readiness_validation.py`

- [x] **Step 1: Implement artifact loading and gate checks**

Implement helper functions to load required summaries, check local `best.pt`, and collect blocker strings without mutating runtime defaults.

- [x] **Step 2: Implement classification**

Classify blockers in this order:
- missing upstream truth -> `v7_2_promotion_readiness_missing_upstream_truth`
- checkpoint contract failure -> `v7_2_promotion_checkpoint_contract_failure`
- export contract failure -> `v7_2_promotion_export_contract_failure`
- bounded metric failure -> `v7_2_promotion_bounded_metric_failure`
- guardrail metric failure -> `v7_2_promotion_guardrail_metric_failure`
- full-pipeline runtime/flood failure -> `v7_2_runtime_integration_fix`
- positive recall failure -> `v7_2_positive_diversity_refresh`

- [x] **Step 3: Write artifacts and registry**

On pass, write the candidate-local output artifacts, suite-level readiness artifact, and `backend/storage/runtime/promoted_touchline_detector_candidate.json` with v7.2 controlled-run metadata. Always set `runtimeDefaultMutationExecuted = false`.

- [x] **Step 4: Add CLI**

Expose `--storage-root`, `--candidate-name`, `--attempt-number`, and `--attempt-approach-family`.

### Task 3: Verify, Generate, Document, Commit

**Files:**
- Modify generated status/docs listed above.

- [x] **Step 1: Run focused tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  backend/tests/test_run_v7_2_promotion_readiness_validation.py \
  backend/tests/test_run_v7_2_full_pipeline_non_promotion_eval.py \
  backend/tests/test_unattended_roadmap_loop.py -q
```

- [x] **Step 2: Compile scripts**

Run:

```bash
python3 -m py_compile \
  backend/scripts/run_v7_2_promotion_readiness_validation.py \
  backend/scripts/run_v7_2_full_pipeline_non_promotion_eval.py
```

- [x] **Step 3: Generate artifacts**

Run:

```bash
python3 backend/scripts/run_v7_2_promotion_readiness_validation.py
python3 backend/scripts/run_source_robustness_batch.py
runpodctl pod list --all -o json
```

Expected RunPod output: `[]`.

- [x] **Step 4: Update docs/status**

Update roadmap/memorybank/handoff/status from generated artifacts only.

- [x] **Step 5: Commit**

Run:

```bash
git add backend/scripts/run_v7_2_promotion_readiness_validation.py \
  backend/tests/test_run_v7_2_promotion_readiness_validation.py \
  docs/superpowers/plans/2026-05-03-v7-2-promotion-readiness-validation.md \
  docs/superpowers/plans/2026-04-23-promoted-v6-failing-source-robustness-validation.md \
  memorybank/activeContext.md memorybank/currentRoadmap.md memorybank/progress.md \
  memorybank/features/source-robustness-lane.md SESSION-HANDOFF.md
git add -f backend/storage/automation/unattended_roadmap_loop_status.json \
  backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_promotion_readiness_validation_v1 \
  backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/v7_2_detector_candidate_promotion_readiness.json \
  backend/storage/runtime/promoted_touchline_detector_candidate.json
git diff --cached --check
git commit -m "Validate v7.2 promotion readiness"
```

## Self-Review

- Spec coverage: The plan lifts the prior artificial freeze by validating v7.2 for controlled promotion if generated truth clears, while keeping runtime-default mutation as a separate executed gate.
- Failsafes: Three attempts adapt to contract repair, runtime integration failures, metric failures, and final blocker-summary routing.
- Placeholder scan: No placeholders remain.
- Type consistency: Artifact names, batch names, blocker names, and next levers use consistent `v7_2_*` or `promoted_v7_2_*` naming.
