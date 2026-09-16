# Housekeeping Direction Snapshot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the next worker a clean, artifact-backed view of where the project is, what is dirty, and which lane should move next.

**Architecture:** This is a repo-state and roadmap-orientation plan, not model training. It separates the core v7.2 runtime/default lane from the SoccerNet external product/data lane, because both are live but at different maturity points.

**Tech Stack:** Python scripts and pytest for verification, generated JSON truth under `backend/storage`, roadmap docs under `memorybank`, and operational state in `SESSION-HANDOFF.md`.

---

## Current Truth

### Core v7.2 Runtime/Detector Lane

Authoritative generated artifacts show the v7.2 detector/runtime lane reached and closed runtime-default rollout:

- `v7_2_promotion_readiness_validation_v1`
  - `goalAchieved = true`
  - `primaryBlocker = null`
  - `promotionReady = true`
  - `candidateReadyForEvaluation = true`
  - `runtimeDefaultMutationExecuted = false`
  - next was `promoted_v7_2_source_robustness_validation`
- `promoted_v7_2_source_robustness_validation_v1`
  - failed safely on `v7_2_source_robustness_default_mutation_blocked`
  - routed to default-path blocker analysis
- `v7_2_default_path_inboard_ball_recovery_v1`
  - `goalAchieved = true`
  - `primaryBlocker = null`
  - `safeInboardCandidateFrameCount = 133`
  - `runtimeDefaultMutationReady = true`
  - `runtimeDefaultMutationExecuted = false`
- `v7_2_runtime_default_change_validation_v1`
  - `goalAchieved = true`
  - `primaryBlocker = null`
  - `runtimeDefaultMutationReady = true`
  - `runtimeDefaultMutationExecuted = true`
- `v7_2_post_runtime_default_source_robustness_validation_v1`
  - `goalAchieved = true`
  - `primaryBlocker = null`
  - old failing-source blocker stayed cleared
  - `runtimeDefaultMutationExecuted = true`
- `v7_2_runtime_default_rollout_closeout_v1`
  - `goalAchieved = true`
  - `primaryBlocker = null`
  - `runtimeDefaultMutationExecuted = true`
  - next was `football_external_dataset_access_review`

Interpretation: v7.2 is no longer only a candidate. The controlled default-path rollout closed. Do not regress this lane by treating the project as still stuck at v7.2 training or promotion readiness.

### SoccerNet External Product/Data Lane

The SoccerNet lane has now advanced from NDA/API access to product-facing full 224p analysis payload:

- `football_external_soccernet_full_analysis_execution_v1`
  - processed `146893 / 146893` frames
  - `unreadableFrameCount = 0`
  - `segmentCount = 196`
- `football_external_soccernet_full_analysis_lane_closeout_v1`
  - `goalAchieved = true`
  - `fullAnalysisLaneClosed = true`
  - `fullAnalysisProductIntegrationReady = true`
- `football_external_soccernet_full_analysis_product_integration_v1`
  - `goalAchieved = true`
  - `primaryBlocker = null`
  - `productFullAnalysisReady = true`
  - `reportedFrameCount = 146893`
  - `segmentCount = 196`
  - `trainingExecuted = false`
  - `promotionReady = false`
  - `candidateReadyForEvaluation = false`
  - `runtimeDefaultMutationExecuted = false`
  - next is `football_external_soccernet_analysis_product_api_smoke`

Interpretation: the next active lane should verify product/API consumption of the full-analysis payload. This is external-data/product integration, not detector training.

## Housekeeping State

Current worktree inventory from `git status --short`:

- modified tracked files: `14`
- untracked files/directories: `137`
- untracked scripts: `50`
- untracked tests: `50`
- untracked plans: `34`
- untracked `.vscode/`: present and untouched

Do not delete untracked files blindly. Most of them are real roadmap batch scripts/tests/plans from the SoccerNet and v7.2 lanes. The practical cleanup is to group/commit/review them in slices, not to remove them.

## Immediate Direction

### Next Batch

`football_external_soccernet_analysis_product_api_smoke`

Purpose:

- Verify that the product-facing/API layer can consume `football_external_soccernet_full_analysis_product_integration_v1/product_full_analysis_payload.json`.
- Confirm UI/API-ready payload fields, limitations banner, readiness flags, report path, and frame/segment counts.
- Preserve the safety flags:
  - `trainingExecuted = false`
  - `promotionReady = false`
  - `candidateReadyForEvaluation = false`
  - `runtimeDefaultMutationExecuted = false`

Success next lever should probably be one of:

- `football_external_soccernet_analysis_product_ui_binding`
- `football_external_soccernet_720p_member_analysis_approval`
- `football_external_benchmark_detector_truth_alignment`

The safest next choice after API smoke is product UI binding if the goal is “video -> data to analyze” in-app. If the goal is better benchmark fidelity, then 720p approval or detector truth alignment becomes the next branch.

## Execution Tasks

### Task 1: Product API Smoke

**Files:**

- Create: `backend/scripts/run_football_external_soccernet_analysis_product_api_smoke.py`
- Create: `backend/tests/test_run_football_external_soccernet_analysis_product_api_smoke.py`
- Write artifacts under: `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_soccernet_analysis_product_api_smoke_v1/`

- [ ] **Step 1: Write tests for consuming the product payload**

Expected assertions:

- input product integration summary has `goalAchieved = true`
- product payload has `frameCount = 146893`
- product payload readiness has `productFullAnalysisReady = true`
- API smoke output preserves `candidateReadyForEvaluation = false`
- output next lever is selected from the product-facing branch

- [ ] **Step 2: Implement the smoke script**

The script should read only saved generated truth:

- `full_analysis_product_integration_summary.json`
- `product_full_analysis_payload.json`
- `product_ui_copy.json`
- `product_integration_contract.json`

It should write:

- `analysis_product_api_smoke_summary.json`
- `analysis_product_api_payload_contract_audit.json`
- `analysis_product_api_response_fixture.json`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`
- `batch_outcome_analysis.json`
- `batch_outcome_analysis.md`

- [ ] **Step 3: Execute and verify**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  backend/tests/test_run_football_external_soccernet_analysis_product_api_smoke.py \
  backend/tests/test_run_football_external_soccernet_full_analysis_product_integration.py \
  backend/tests/test_unattended_roadmap_loop.py -q

python3 backend/scripts/run_football_external_soccernet_analysis_product_api_smoke.py
python3 -m py_compile backend/scripts/run_football_external_soccernet_analysis_product_api_smoke.py
runpodctl pod list --all -o json
```

### Task 2: Worktree Cleanup Slicing

**Files:** no code changes required unless a specific slice fails verification.

- [ ] **Step 1: Keep generated artifacts out of Git unless intentionally versioned**

Run:

```bash
git ls-files backend/storage | wc -l
git status --short
```

- [ ] **Step 2: Prepare commit slice 1: product/core API changes**

Candidate slice:

- `backend/app/match_bundle.py`
- `backend/app/main.py`
- `backend/tests/test_api.py`
- `backend/scripts/run_canonical_match_bundle_export.py`
- `backend/tests/test_run_canonical_match_bundle_export.py`
- `backend/scripts/run_product_video_to_analysis_smoke.py`
- `backend/tests/test_run_product_video_to_analysis_smoke.py`
- `backend/scripts/run_v7_2_runtime_registry_product_path_binding.py`
- `backend/tests/test_run_v7_2_runtime_registry_product_path_binding.py`

- [ ] **Step 3: Prepare commit slice 2: v7.2 runtime/default rollout**

Candidate slice:

- `backend/app/proof_runtime.py`
- `backend/app/runpod.py`
- `backend/app/runpod_worker.py`
- `backend/runpod_handler/handler.py`
- related tests in `backend/tests/test_processor.py`, `test_runpod.py`, `test_runpod_worker.py`, `test_runpod_handler.py`

- [ ] **Step 4: Prepare commit slice 3: SoccerNet external lane**

Candidate slice:

- all `backend/scripts/run_football_external_soccernet_*.py`
- all matching `backend/tests/test_run_football_external_soccernet_*.py`
- all `docs/superpowers/plans/2026-05-04-football-external-soccernet-*.md`
- `docs/superpowers/plans/2026-05-05-football-external-soccernet-full-analysis-product-integration.md`

- [ ] **Step 5: Prepare commit slice 4: roadmap/handoff**

Candidate slice:

- `SESSION-HANDOFF.md`
- `memorybank/activeContext.md`
- `memorybank/currentRoadmap.md`
- `backend/storage/automation/unattended_roadmap_loop_status.json`
- this housekeeping direction snapshot

## Do Not Do During Housekeeping

- Do not delete `.vscode/` without explicit user confirmation.
- Do not reset or checkout modified files.
- Do not rerun training.
- Do not mutate runtime defaults again unless a new generated batch explicitly requires it.
- Do not treat SoccerNet frame-stat analysis as ball-localization truth.
- Do not claim detector benchmark generalization from the 224p product payload.
