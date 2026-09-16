# V7.2 Full Pipeline Non-Promotion Eval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run the `v7_2_full_pipeline_non_promotion_eval` batch, proving whether the v7.2 bounded crop detector remains safe and informative when interpreted through the real pipeline-stage contracts.

**Architecture:** Reuse the proven v7.1 full-pipeline audit shape, but bind it to v7.2 artifacts: `v7_2_training_manifest_prep_v1`, `v7_2_bounded_retrain_v1`, and `v7_2_crop_probe_precision_guardrail_audit_v1`. The batch remains inference-only and derives stage metrics from saved guardrail predictions plus crop/source geometry; it does not train, promote, or alter runtime defaults.

**Tech Stack:** Python scripts under `backend/scripts`, pytest, JSON artifacts under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7`, existing v7.1/v7.2 detector audit helpers.

---

## File Structure

- Create: `backend/scripts/run_v7_2_full_pipeline_non_promotion_eval.py`
  - Owns v7.2 full-pipeline stage metrics, blocker classification, artifact writing, and CLI entrypoint.
- Create: `backend/tests/test_run_v7_2_full_pipeline_non_promotion_eval.py`
  - Covers pass, checkpoint failure, candidate crop coverage gap, projection error, and old top-left artifact regression.
- Modify: `docs/superpowers/plans/2026-05-03-v7-2-full-pipeline-non-promotion-eval.md`
  - This execution plan.
- Later generated/updated files after the script passes:
  - `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_full_pipeline_non_promotion_eval_v1/*`
  - `backend/storage/automation/unattended_roadmap_loop_status.json`
  - `memorybank/activeContext.md`
  - `memorybank/currentRoadmap.md`
  - `memorybank/progress.md`
  - `memorybank/features/source-robustness-lane.md`
  - `SESSION-HANDOFF.md`
  - `docs/superpowers/plans/2026-04-23-promoted-v6-failing-source-robustness-validation.md`

## Batch Contract

- Active batch: `v7_2_full_pipeline_non_promotion_eval`
- Attempt budget: `3`
- Attempt 1 family: `crop_probe_full_pipeline_eval`
- Inputs:
  - `v7_2_training_manifest_prep_v1/v7_2_training_manifest.json`
  - `v7_2_bounded_retrain_v1/v7_2_bounded_retrain_summary.json`
  - `v7_2_crop_probe_precision_guardrail_audit_v1/*`
- Outputs:
  - `checkpoint_contract_audit.json`
  - `pipeline_crop_contract_audit.json`
  - `candidate_crop_coverage_audit.json`
  - `crop_to_source_projection_audit.json`
  - `confidence_sweep_audit.json`
  - `reviewed_positive_pipeline_audit.json`
  - `refuted_seed_evidence_audit.json`
  - `heldout_canary_pipeline_audit.json`
  - `old_top_left_artifact_pipeline_audit.json`
  - `sampled_frame_flood_regression_audit.json`
  - `observed_ball_acceptance_audit.json`
  - `positive_miss_analysis.json`
  - `false_positive_analysis.json`
  - `v7_2_full_pipeline_non_promotion_summary.json`
  - `decision_matrix.json`
  - `batch_outcome_analysis.json/md`
  - copied contact sheets for worst misses, false positives, and old top-left artifacts.
- Safety invariants:
  - `trainingAllowed = false`
  - `trainingExecuted = false`
  - `promotionReady = false`
  - `candidateReadyForEvaluation = false`
  - `runtimeDefaultMutationAllowed = false`
  - no remote/base checkpoint fallback.

## Attempt Failsafes

- Attempt 1, `crop_probe_full_pipeline_eval`:
  - Compute stage metrics from saved v7.2 guardrail predictions and v7.2 manifest geometry.
  - Pass if checkpoint contract, crop contract, crop coverage, projection, artifact, canary, sampled-frame, and source localization gates pass.
  - Next lever on pass: `football_external_benchmark_harness_prep` if the source-frame localization is strong enough, otherwise `v7_2_positive_diversity_refresh`.
- Attempt 2, `pipeline_contract_repair`:
  - Use only if attempt 1 fails due to plumbing: missing artifact path, v7.2 manifest path mismatch, checkpoint key mismatch, or copied contact sheet gap.
  - Allowed repairs: path/key normalization and artifact copy fixes.
  - Not allowed: changing labels, retraining, promotion, runtime default edits, threshold tuning.
- Attempt 3, `pipeline_eval_blocker_summary`:
  - If behavior fails after plumbing is valid, write blocker truth and stop.
  - Select exactly one next family:
    - `v7_2_training_config_or_export_debug`
    - `v7_2_candidate_crop_generation_refresh`
    - `v7_2_crop_projection_contract_fix`
    - `v7_2_artifact_regression_debug`
    - `v7_2_positive_diversity_refresh`
    - `v7_2_hard_negative_expansion`
    - `v7_2_confidence_operating_point_calibration`

## Tasks

### Task 1: Write Failing Tests

**Files:**
- Create: `backend/tests/test_run_v7_2_full_pipeline_non_promotion_eval.py`

- [x] **Step 1: Add focused tests**

Create pytest helpers that synthesize:
- v7.2 local manifest rows with crop bounds and source-frame bboxes.
- v7.2 guardrail positive/negative prediction audits.
- v7.2 bounded retrain summary with a local `best.pt`.

Add tests:
- pass path reports stage metrics and routes to `football_external_benchmark_harness_prep` for strong source localization.
- missing checkpoint fails closed to `v7_2_training_config_or_export_debug`.
- crop coverage gap routes to `v7_2_candidate_crop_generation_refresh`.
- projection error routes to `v7_2_crop_projection_contract_fix`.
- old top-left artifact regression routes to `v7_2_artifact_regression_debug`.

- [x] **Step 2: Run red test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_v7_2_full_pipeline_non_promotion_eval.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `backend.scripts.run_v7_2_full_pipeline_non_promotion_eval`.

### Task 2: Implement V7.2 Full-Pipeline Batch Script

**Files:**
- Create: `backend/scripts/run_v7_2_full_pipeline_non_promotion_eval.py`

- [x] **Step 1: Implement artifact loading and helper functions**

Use the v7.1 full-pipeline script as the local pattern. Load v7.2 guardrail, bounded summary, and manifest. Enforce local checkpoint identity through the v7.2 guardrail summary.

- [x] **Step 2: Implement stage metrics**

Compute:
- `positiveReviewedFrameCount`
- `positiveFramesWithCandidateCropCoveringGtBall`
- `candidateCropCoverageRate`
- `positiveFramesWithCropDetectorPredictionNearGt`
- `cropDetectorConditionalLocalizationRate`
- `positiveFramesWithSourceFrameLocalizedBall`
- `sourceFrameLocalizationHitRate`
- `positiveFramesAcceptedAsObservedBall`
- `observedBallAcceptanceRate`
- `projectionAuditPassed`
- negative/canary/top-left/sample flood metrics.

- [x] **Step 3: Implement blocker classification**

Block in this order:
- runtime mutation violation
- checkpoint contract failure
- crop contract mismatch
- candidate crop coverage gap
- crop projection error
- old top-left artifact regression
- canary flood
- sampled-frame flood
- giant box regression
- low-confidence flood regression
- source localization insufficient

On clean, strong pass choose `football_external_benchmark_harness_prep`; otherwise choose `v7_2_positive_diversity_refresh`.

- [x] **Step 4: Write artifacts and CLI**

Write all required JSON/MD artifacts under `v7_2_full_pipeline_non_promotion_eval_v1/`, copy guardrail contact sheets, and expose a CLI with `--storage-root`, `--candidate-name`, `--attempt-number`, and `--attempt-approach-family`.

### Task 3: Verify, Generate, Document, Commit

**Files:**
- Modify generated status/docs listed above.

- [x] **Step 1: Run focused tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  backend/tests/test_run_v7_2_full_pipeline_non_promotion_eval.py \
  backend/tests/test_run_v7_2_crop_probe_precision_guardrail_audit.py \
  backend/tests/test_run_v7_2_bounded_retrain.py \
  backend/tests/test_unattended_roadmap_loop.py -q
```

- [x] **Step 2: Compile scripts**

Run:

```bash
python3 -m py_compile \
  backend/scripts/run_v7_2_full_pipeline_non_promotion_eval.py \
  backend/scripts/run_v7_2_crop_probe_precision_guardrail_audit.py \
  backend/scripts/run_v7_2_bounded_retrain.py
```

- [x] **Step 3: Generate artifacts**

Run:

```bash
python3 backend/scripts/run_v7_2_full_pipeline_non_promotion_eval.py
python3 backend/scripts/run_source_robustness_batch.py
runpodctl pod list --all -o json
```

Expected RunPod output: `[]`.

- [x] **Step 4: Update docs/status from generated truth**

Update memorybank, handoff, roadmap plan notes, and unattended status JSON to the generated next lever.

- [x] **Step 5: Commit**

Run:

```bash
git add -f backend/storage/automation/unattended_roadmap_loop_status.json \
  backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_full_pipeline_non_promotion_eval_v1
git add backend/scripts/run_v7_2_full_pipeline_non_promotion_eval.py \
  backend/tests/test_run_v7_2_full_pipeline_non_promotion_eval.py \
  docs/superpowers/plans/2026-05-03-v7-2-full-pipeline-non-promotion-eval.md \
  docs/superpowers/plans/2026-04-23-promoted-v6-failing-source-robustness-validation.md \
  memorybank/activeContext.md memorybank/currentRoadmap.md memorybank/progress.md \
  memorybank/features/source-robustness-lane.md SESSION-HANDOFF.md
git diff --cached --check
git commit -m "Build v7.2 full pipeline non-promotion eval"
```

## Self-Review

- Spec coverage: The plan covers the next generated lever from v7.2 crop guardrail, adds an inference-only batch, protects checkpoint/runtime/promote invariants, writes required stage/failure artifacts, and routes to adaptive next families.
- Placeholder scan: No placeholders or deferred implementation instructions remain.
- Type consistency: Script/test names, artifact names, blocker names, and next levers use the v7.2 prefix consistently.
