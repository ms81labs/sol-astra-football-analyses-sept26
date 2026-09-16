# Canonical Match Bundle Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose a deterministic `match_bundle_v1` JSON package so a processed video becomes one analysis-ready data artifact.

**Architecture:** Build the bundle from persisted artifacts only: match metadata, frames, analytics, events, optional accepted state, optional ball/proof provenance, optional benchmark, and stable export links. The API route and saved-artifact batch share the same builder.

**Tech Stack:** Python, FastAPI, Pydantic models, repo-local storage artifacts, pytest.

---

### Task 1: Bundle API Contract

**Files:**
- Create: `backend/app/match_bundle.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api.py`

- [x] Add a failing API test for `GET /api/matches/{match_id}/export/match.json`.
- [x] Build `match_bundle_v1` from persisted artifacts.
- [x] Return 404 when core match artifacts are not ready.
- [x] Verify the route returns match metadata, frames, analytics, events, artifact availability, provenance, and export links.

### Task 2: Saved Batch Truth

**Files:**
- Create: `backend/scripts/run_canonical_match_bundle_export.py`
- Test: `backend/tests/test_run_canonical_match_bundle_export.py`

- [x] Add failing tests for generated truth artifacts.
- [x] Write `canonical_match_bundle_export_v1/` outputs.
- [x] Include failsafe families: `persisted_artifact_bundle_contract`, `bundle_schema_or_api_contract_repair`, and `bundle_export_blocker_summary`.
- [x] Route success to `product_video_to_analysis_smoke_v1`.

### Task 3: Verification And Handoff

**Files:**
- Modify: `memorybank/currentRoadmap.md`
- Modify: `memorybank/activeContext.md`
- Modify: `SESSION-HANDOFF.md`
- Modify: `backend/storage/automation/unattended_roadmap_loop_status.json`

- [x] Run focused API and batch tests.
- [x] Run `py_compile` on touched modules.
- [x] Generate real `canonical_match_bundle_export_v1` artifacts.
- [x] Update roadmap and handoff surfaces from generated truth.
