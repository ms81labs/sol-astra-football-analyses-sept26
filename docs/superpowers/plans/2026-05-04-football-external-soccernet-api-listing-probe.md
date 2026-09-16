# Football External SoccerNet API Listing Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove SoccerNet package-local listing readiness without downloading labels, videos, features, or datasets.

**Architecture:** The batch reads the secretless SoccerNet NDA/API approval and metadata-probe artifacts, requires `SOCCERNET_PASSWORD` only as a runtime environment credential, and uses the installed SoccerNet package's local `getListGames` indexes to enumerate task/split game references. Generated truth advances only to a controlled label-metadata probe.

**Tech Stack:** Python batch script, pytest, SoccerNet package-local metadata, JSON artifacts.

---

### Task 1: Add Listing Probe Test Contract

**Files:**
- Create: `backend/tests/test_run_football_external_soccernet_api_listing_probe.py`

- [x] **Step 1: Write failing tests**

Cover package-local listing success, missing runtime credential, missing metadata-probe truth, empty listing blocker, and three adaptive attempt families.

- [x] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_soccernet_api_listing_probe.py -q
```

Expected initial result: import failure for missing `backend.scripts.run_football_external_soccernet_api_listing_probe`.

### Task 2: Implement Listing Probe

**Files:**
- Create: `backend/scripts/run_football_external_soccernet_api_listing_probe.py`

- [x] **Step 1: Implement local-index listing only**

Use the artifact-local SoccerNet package Python executable from `football_external_soccernet_api_metadata_probe_v1/soccernet_api_package_audit.json`.

- [x] **Step 2: Preserve safety invariants**

Do not execute network API calls, label downloads, original-video downloads, training, promotion, candidate evaluation, or runtime-default mutation.

- [x] **Step 3: Write generated artifacts**

Write `soccernet_api_listing_probe_summary.json`, `soccernet_api_listing_audit.json`, `credential_runtime_audit.json`, `decision_matrix.json`, `failsafe_attempt_plan.json`, and `batch_outcome_analysis.json/md`.

### Task 3: Execute And Verify

**Files:**
- Modify: `memorybank/currentRoadmap.md`
- Modify: `memorybank/activeContext.md`
- Modify: `SESSION-HANDOFF.md`
- Modify: `backend/storage/automation/unattended_roadmap_loop_status.json`

- [x] **Step 1: Run real listing probe**

Use `SOCCERNET_PASSWORD` as runtime-only input and run:

```bash
python3 backend/scripts/run_football_external_soccernet_api_listing_probe.py
```

- [x] **Step 2: Update roadmap truth from generated artifacts**

Set the next lever to `football_external_soccernet_controlled_label_metadata_probe`.

- [x] **Step 3: Run focused verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  backend/tests/test_run_football_external_soccernet_api_listing_probe.py \
  backend/tests/test_run_football_external_soccernet_api_metadata_probe.py \
  backend/tests/test_run_football_external_soccernet_nda_api_access_approval.py \
  backend/tests/test_run_football_external_soccertrack_metadata_adapter_smoke.py \
  backend/tests/test_run_football_external_safe_source_controlled_sample_fetch.py \
  backend/tests/test_run_football_external_safe_source_sample_download_approval.py \
  backend/tests/test_run_football_external_safe_source_sample_ingestion_plan.py \
  backend/tests/test_run_football_external_safe_adapter_fixture_implementation.py \
  backend/tests/test_run_football_external_safe_source_adapter_smoke_test.py \
  backend/tests/test_run_football_external_dataset_access_review.py \
  backend/tests/test_run_football_external_benchmark_harness_prep.py \
  backend/tests/test_unattended_roadmap_loop.py -q
```

Expected final result: all focused tests pass and `runpodctl pod list --all -o json` returns `[]`.
