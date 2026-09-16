# SoccerNet Real Sample Training Decision Cascade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bind the current SoccerNet validation report, verify/materialize the controlled real sample, run or bind the product pipeline, and decide from evidence whether v7.3 detector training is actually needed.

**Architecture:** Add two saved-artifact batches. The first turns the existing bounded product-validation execution truth into an operator-facing report binding. The second verifies the already materialized real SoccerNet 224p sample and fresh product-pipeline artifacts, then emits a fail-closed training decision: retrain only if real detector miss truth exists.

**Tech Stack:** Python saved-artifact scripts, pytest, generated JSON/Markdown truth under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/`.

---

### Task 1: Storage Hygiene

**Files:**
- Read: filesystem usage and RunPod state
- No source edits

- [x] **Step 1: Measure disk and artifact usage**

Run: `df -h . /root /tmp`

Expected: enough free space for controlled samples.

- [x] **Step 2: Remove safe cache-only directories**

Run: `find backend docs memorybank -depth -type d \( -name '__pycache__' -o -name '.pytest_cache' \) -print -exec rm -rf {} +`

Expected: no generated truth, videos, labels, or model artifacts are deleted.

### Task 2: Validation Report Binding

**Files:**
- Create: `backend/scripts/run_football_external_soccernet_bounded_product_validation_report_binding.py`
- Create: `backend/tests/test_run_football_external_soccernet_bounded_product_validation_report_binding.py`
- Write artifacts: `football_external_soccernet_bounded_product_validation_report_binding_v1/`

- [x] **Step 1: Write tests for successful report binding and fail-closed missing execution**
- [x] **Step 2: Verify tests fail because the script does not exist**
- [x] **Step 3: Implement the report-binding script**
- [x] **Step 4: Verify focused tests pass**
- [x] **Step 5: Run the script against real artifacts**

### Task 3: Real Sample Product Pipeline Training Decision

**Files:**
- Create: `backend/scripts/run_football_external_soccernet_real_sample_product_pipeline_training_decision.py`
- Create: `backend/tests/test_run_football_external_soccernet_real_sample_product_pipeline_training_decision.py`
- Write artifacts: `football_external_soccernet_real_sample_product_pipeline_training_decision_v1/`

- [x] **Step 1: Write tests for materialized sample/product pass/no-training-needed decision**
- [x] **Step 2: Write tests for missing sample and missing product-pipeline blocker paths**
- [x] **Step 3: Verify tests fail because the script does not exist**
- [x] **Step 4: Implement the decision script**
- [x] **Step 5: Verify focused tests pass**

### Task 4: Execute The Real Pipeline Cascade

**Files:**
- Existing product pipeline scripts:
  - `backend/scripts/run_football_external_soccernet_full_analysis_execution.py`
  - `backend/scripts/run_football_external_soccernet_full_analysis_product_integration.py`
  - `backend/scripts/run_football_external_soccernet_analysis_product_api_smoke.py`
- New binding/decision scripts from Tasks 2-3

- [x] **Step 1: Run report binding**
- [x] **Step 2: Re-run full 224p product pipeline on the controlled sample**
- [x] **Step 3: Run real-sample product-pipeline training decision**
- [x] **Step 4: If detector miss truth exists and says training is needed, route to v7.3 manifest prep; otherwise block retrain and route to miss capture**

### Task 5: Verification And Direction

**Files:**
- Focused tests
- Py compile targets
- Generated artifacts

- [x] **Step 1: Run focused pytest suite**
- [x] **Step 2: Run py_compile for touched scripts**
- [x] **Step 3: Re-check disk and RunPod state**
- [x] **Step 4: Summarize whether v7.3 training is justified by evidence**
