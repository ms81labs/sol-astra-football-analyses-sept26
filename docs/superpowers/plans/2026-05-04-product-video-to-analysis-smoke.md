# Product Video To Analysis Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify the product path can create a match through the API/job lane and export analysis-ready data surfaces.

**Architecture:** Use a fast deterministic API upload smoke for route coverage, then validate an existing ready video-backed match bundle if one exists. This avoids long GPU processing inside the smoke while proving the product export surfaces.

**Tech Stack:** Python, FastAPI ASGI app, httpx, persisted storage artifacts, pytest.

---

### Task 1: Smoke Batch Contract

**Files:**
- Create: `backend/scripts/run_product_video_to_analysis_smoke.py`
- Test: `backend/tests/test_run_product_video_to_analysis_smoke.py`

- [x] Add failing tests for API upload/export smoke and existing video bundle smoke.
- [x] Upload tracking fixture through the normal API/job path.
- [x] Verify job, frames, analytics, events, CSV exports, report HTML, and `match_bundle_v1`.
- [x] Validate an existing ready video-backed bundle when available.
- [x] Include three failsafe families: `api_upload_export_smoke`, `video_bundle_contract_repair`, and `product_smoke_blocker_summary`.

### Task 2: Generated Truth

**Files:**
- Create artifacts under `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/product_video_to_analysis_smoke_v1/`

- [x] Write `api_upload_job_smoke_audit.json`.
- [x] Write `existing_video_bundle_smoke_audit.json`.
- [x] Write `sample_exported_match_bundle.json` when a ready video bundle exists.
- [x] Write `decision_matrix.json`, `product_video_to_analysis_smoke_summary.json`, `batch_outcome_analysis.json/md`.

### Task 3: Verification And Handoff

**Files:**
- Modify: `memorybank/currentRoadmap.md`
- Modify: `memorybank/activeContext.md`
- Modify: `SESSION-HANDOFF.md`
- Modify: `backend/storage/automation/unattended_roadmap_loop_status.json`

- [x] Run focused smoke/API/bundle tests.
- [x] Run `py_compile`.
- [x] Generate live smoke artifacts.
- [x] Update roadmap and handoff surfaces to `football_external_safe_source_adapter_smoke_test`.
