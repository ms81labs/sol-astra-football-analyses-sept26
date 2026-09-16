# Football External Benchmark Harness Prep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `football_external_benchmark_harness_prep` batch that turns the clean v7.2 non-promotion pipeline signal into a safe external-benchmark readiness contract without training, promotion, candidate evaluation readiness, or runtime-default mutation.

**Architecture:** Add a saved-artifact prep script that reads the latest v7.2 full-pipeline non-promotion truth and the local research-report context, then writes a benchmark source inventory, adapter contract, stage-gate contract, split plan, and adaptive three-attempt decision matrix. This batch prepares the next external dataset access/review step; it does not download datasets or run model evaluation.

**Tech Stack:** Python batch script under `backend/scripts`, pytest focused tests, JSON/Markdown artifacts under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1`.

---

## File Structure

- Create: `backend/scripts/run_football_external_benchmark_harness_prep.py`
  - Reads v7.2 full-pipeline summary and optional local research report.
  - Writes source inventory, adapter contract, stage gates, split plan, attempt plan, decision matrix, summary, and batch outcome.
- Create: `backend/tests/test_run_football_external_benchmark_harness_prep.py`
  - Covers success, missing/failed v7.2 pipeline truth, insufficient resource inventory, missing stage coverage, and safety invariants.
- Create: `docs/superpowers/plans/2026-05-03-football-external-benchmark-harness-prep.md`
  - This executable plan.
- Later generated/updated files:
  - `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/*`
  - `backend/storage/automation/unattended_roadmap_loop_status.json`
  - `memorybank/activeContext.md`
  - `memorybank/currentRoadmap.md`
  - `memorybank/progress.md`
  - `memorybank/features/source-robustness-lane.md`
  - `SESSION-HANDOFF.md`
  - `docs/superpowers/plans/2026-04-23-promoted-v6-failing-source-robustness-validation.md`

## Batch Contract

- Active batch: `football_external_benchmark_harness_prep`
- Attempt budget: `3`
- Attempt 1 family: `external_benchmark_contract_prep`
- Inputs:
  - `v7_2_full_pipeline_non_promotion_eval_v1/v7_2_full_pipeline_non_promotion_summary.json`
  - optional local report: `backend/storage/trained_detector_candidates/deep-research-report (1).md`
- Outputs:
  - `external_benchmark_harness_summary.json`
  - `benchmark_resource_inventory.json`
  - `dataset_adapter_contract.json`
  - `benchmark_split_plan.json`
  - `stage_gate_contract.json`
  - `failsafe_attempt_plan.json`
  - `benchmark_harness_readiness_audit.json`
  - `decision_matrix.json`
  - `batch_outcome_analysis.json/md`
- Frozen invariants:
  - `trainingAllowed = false`
  - `trainingExecuted = false`
  - `promotionReady = false`
  - `candidateReadyForEvaluation = false`
  - `runtimeDefaultMutationAllowed = false`
  - `datasetDownloadExecuted = false`
  - `externalBenchmarkExecutionReady = false`

## Attempt Flow With Adaptive Failsafes

- Attempt 1: `external_benchmark_contract_prep`
  - Build benchmark source inventory from the local research context and built-in safe defaults.
  - Build adapter contracts for `frame_state`, `game_state`, `event_stream`, `calibration`, `tracking`, and `ball_action`.
  - Build stage gates for shot gating, calibration, tracking, ball localization, possession/event semantics, and coach-report outputs.
  - Success if v7.2 pipeline truth is clean, resource inventory has at least five sources, core stages are covered, adapter contract is complete, and safety invariants are frozen.
  - On success: `nextRecommendedNextLever = football_external_dataset_access_review`.

- Attempt 2: `benchmark_adapter_contract_repair`
  - Use only if attempt 1 fails from schema/resource completeness:
    - missing adapter fields
    - missing stage coverage
    - local research report missing but defaults are available
    - dataset-source metadata too sparse
  - Allowed repairs:
    - add missing adapter fields
    - mark license/access validation as pending instead of asserting final legality
    - split high-risk resources into evidence-only rows
    - add stage coverage notes
  - Not allowed:
    - downloading datasets
    - training/retraining
    - model evaluation against external data
    - promotion or runtime-default mutation.

- Attempt 3: `benchmark_harness_blocker_summary`
  - If readiness still fails, write blocker truth and stop.
  - Select exactly one next family:
    - `football_external_source_research_refresh`
    - `football_external_dataset_access_review`
    - `football_external_adapter_contract_fix`
    - `football_external_manual_source_selection`
    - `manual_review_required`

## Tasks

### Task 1: Write Failing Tests

**Files:**
- Create: `backend/tests/test_run_football_external_benchmark_harness_prep.py`

- [x] **Step 1: Add tests**

Create tests that synthesize a v7.2 full-pipeline summary in a temp storage root. Test:
- clean prep writes all required artifacts, freezes all safety flags, and routes to `football_external_dataset_access_review`.
- missing or failed v7.2 full-pipeline truth fails closed to `v7_2_full_pipeline_non_promotion_eval`.
- insufficient resource inventory routes to `football_external_source_research_refresh`.
- missing required stage coverage routes to `football_external_adapter_contract_fix`.
- attempt plan contains exactly three adaptive attempts.

- [x] **Step 2: Run red test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_benchmark_harness_prep.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `backend.scripts.run_football_external_benchmark_harness_prep`.

### Task 2: Implement Prep Script

**Files:**
- Create: `backend/scripts/run_football_external_benchmark_harness_prep.py`

- [x] **Step 1: Implement artifact helpers and default resources**

Define a default resource inventory for:
- SoccerTrack v2
- SoccerNet broadcast tasks
- SkillCorner Open Data
- Metrica Sports sample data
- StatsBomb Open Data / 360

Mark license/access validation as `requires_current_manual_verification`; do not assert training/promotion readiness.

- [x] **Step 2: Implement adapter and stage contracts**

Write adapter specs for:
- `FrameState`
- `GameState`
- `CalibrationFrame`
- `TrackFrame`
- `BallActionEvent`
- `EventStream`

Write stage gates for:
- camera shot gate
- pitch calibration
- player tracking
- ball localization
- possession/event semantics
- tactical report metrics.

- [x] **Step 3: Implement classification and attempt matrix**

Classify blockers in this order:
- `football_external_v7_2_pipeline_truth_missing`
- `football_external_benchmark_resource_inventory_insufficient`
- `football_external_adapter_stage_coverage_gap`
- `football_external_runtime_mutation_violation`

On clean prep, return:
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `nextRecommendedNextLever = football_external_dataset_access_review`

- [x] **Step 4: Write artifacts and CLI**

Write all required artifacts under `football_external_benchmark_harness_prep_v1/` and expose a CLI with `--storage-root`, `--candidate-name`, `--attempt-number`, and `--attempt-approach-family`.

### Task 3: Verify, Generate, Document, Commit

**Files:**
- Modify generated status/docs listed above.

- [x] **Step 1: Run focused tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  backend/tests/test_run_football_external_benchmark_harness_prep.py \
  backend/tests/test_run_v7_2_full_pipeline_non_promotion_eval.py \
  backend/tests/test_unattended_roadmap_loop.py -q
```

- [x] **Step 2: Compile scripts**

Run:

```bash
python3 -m py_compile \
  backend/scripts/run_football_external_benchmark_harness_prep.py \
  backend/scripts/run_v7_2_full_pipeline_non_promotion_eval.py
```

- [x] **Step 3: Generate artifacts**

Run:

```bash
python3 backend/scripts/run_football_external_benchmark_harness_prep.py
python3 backend/scripts/run_source_robustness_batch.py
runpodctl pod list --all -o json
```

Expected RunPod output: `[]`.

- [x] **Step 4: Update docs/status**

Update roadmap/memorybank/handoff/status from generated artifacts only.

- [x] **Step 5: Commit**

Run:

```bash
git add backend/scripts/run_football_external_benchmark_harness_prep.py \
  backend/tests/test_run_football_external_benchmark_harness_prep.py \
  docs/superpowers/plans/2026-05-03-football-external-benchmark-harness-prep.md \
  docs/superpowers/plans/2026-04-23-promoted-v6-failing-source-robustness-validation.md \
  memorybank/activeContext.md memorybank/currentRoadmap.md memorybank/progress.md \
  memorybank/features/source-robustness-lane.md SESSION-HANDOFF.md
git add -f backend/storage/automation/unattended_roadmap_loop_status.json \
  backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1
git diff --cached --check
git commit -m "Build football external benchmark harness prep"
```

## Self-Review

- Spec coverage: The plan implements the next generated lever after v7.2 full-pipeline success and explicitly preserves no training, no promotion, no candidate evaluation readiness, and no runtime-default mutation.
- Failsafes: The three attempts adapt to missing pipeline truth, resource inventory gaps, adapter coverage gaps, and final blocker-summary routing.
- Placeholder scan: No placeholders remain.
- Type consistency: Batch names, artifact names, blocker names, and next levers consistently use `football_external_*` or v7.2 source-batch names.
