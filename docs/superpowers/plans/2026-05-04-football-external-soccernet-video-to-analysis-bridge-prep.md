# SoccerNet Video To Analysis Bridge Prep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a saved-artifact bridge-prep batch that proves the extracted SoccerNet 224p video can be staged for the existing analysis pipeline without executing full analysis, training, promotion, candidate evaluation, or runtime-default mutation.

**Architecture:** Follow the existing generated-truth batch pattern: a script reads the latest `football_external_soccernet_video_product_path_smoke_v1` bundle, writes bridge contract artifacts under `football_external_soccernet_video_to_analysis_bridge_prep_v1`, and updates roadmap status after the real run. The bridge outputs a product/import contract, not a processing job.

**Tech Stack:** Python scripts under `backend/scripts`, pytest tests under `backend/tests`, JSON/Markdown artifacts under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7`, roadmap docs under `docs/superpowers/plans` and `memorybank`.

---

### Task 1: Bridge Prep Batch Script

**Files:**
- Create: `backend/tests/test_run_football_external_soccernet_video_to_analysis_bridge_prep.py`
- Create: `backend/scripts/run_football_external_soccernet_video_to_analysis_bridge_prep.py`

- [ ] **Step 1: Write failing tests**

Create tests that verify:
- product-path smoke readiness is required
- bridge contract points at the extracted MP4 and sampled frames
- `analysisExecutionApproved = false`
- `trainingExecuted = false`, `promotionReady = false`, `candidateReadyForEvaluation = false`, `runtimeDefaultMutationExecuted = false`
- three adaptive attempt families are present

- [ ] **Step 2: Run test and verify red**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_soccernet_video_to_analysis_bridge_prep.py -q`
Expected: module import failure before script exists.

- [ ] **Step 3: Implement script**

Create script that reads:
- `football_external_soccernet_video_product_path_smoke_v1/video_product_path_smoke_summary.json`
- `football_external_soccernet_video_product_path_smoke_v1/external_video_product_bundle.json`

Write:
- `video_to_analysis_bridge_prep_summary.json`
- `analysis_bridge_contract.json`
- `external_video_ingestion_manifest.json`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`
- `batch_outcome_analysis.json/md`

- [ ] **Step 4: Run tests and real script**

Run focused test, then `python3 backend/scripts/run_football_external_soccernet_video_to_analysis_bridge_prep.py`.

### Task 2: Roadmap And Verification

**Files:**
- Create: `docs/superpowers/plans/2026-05-04-football-external-soccernet-video-to-analysis-bridge-prep.md`
- Modify: `memorybank/currentRoadmap.md`
- Modify: `memorybank/activeContext.md`
- Modify: `SESSION-HANDOFF.md`
- Modify: `backend/storage/automation/unattended_roadmap_loop_status.json`

- [ ] **Step 1: Write generated-truth plan note**

Record the real summary metrics and next lever.

- [ ] **Step 2: Update roadmap and status files**

Set current next lever from generated truth.

- [ ] **Step 3: Verify**

Run focused tests for bridge and upstream video lane, `py_compile`, JSON validation, secret scan, and `runpodctl pod list --all -o json`.


## Generated Truth

- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `analysisBridgePrepReady = true`
- `analysisExecutionApproved = false`
- `analysisExecutionExecuted = false`
- `videoExists = true`
- `sampledFrameCount = 5`
- `archiveDownloadExecuted = false`
- `video720pMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionReady = false`
- `candidateReadyForEvaluation = false`
- `runtimeDefaultMutationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_video_analysis_dry_run_approval`

## Artifacts

- `video_to_analysis_bridge_prep_summary.json`
- `analysis_bridge_contract.json`
- `external_video_ingestion_manifest.json`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`
- `batch_outcome_analysis.json/md`

## Interpretation

The extracted SoccerNet 224p video now has a bridge contract for entering the
existing analysis pipeline. This batch does not execute analysis; it requires a
separate dry-run approval before processing the external video.
