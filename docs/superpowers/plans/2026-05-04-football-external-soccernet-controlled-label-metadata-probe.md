# Football External SoccerNet Controlled Label Metadata Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Identify the smallest safe SoccerNet ball-label metadata surface and write the next label-only fetch approval contract without downloading labels or original videos.

**Architecture:** The batch consumes `football_external_soccernet_api_listing_probe_v1`, chooses the smallest `spotting-ball` task/split surface from package-local listing metadata, and writes a single-game `Labels.json` fetch contract for a later approval batch. It preserves the existing no-video/no-training/no-runtime-mutation constraints.

**Tech Stack:** Python batch script, pytest, JSON artifacts, SoccerNet package-local listing output.

---

### Task 1: Add Controlled Label Metadata Tests

**Files:**
- Create: `backend/tests/test_run_football_external_soccernet_controlled_label_metadata_probe.py`

- [x] **Step 1: Write failing tests**

Cover successful `spotting-ball` valid-split selection, missing listing truth, missing ball-label surface, and three adaptive attempt families.

- [x] **Step 2: Verify red**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_soccernet_controlled_label_metadata_probe.py -q
```

Expected initial result: import failure for missing script.

### Task 2: Implement Controlled Label Metadata Probe

**Files:**
- Create: `backend/scripts/run_football_external_soccernet_controlled_label_metadata_probe.py`

- [x] **Step 1: Read listing and access contract artifacts**

Use `soccernet_api_listing_probe_summary.json`, `soccernet_api_listing_audit.json`, and `soccernet_api_access_contract.json`.

- [x] **Step 2: Select smallest ball-label surface**

Prefer `spotting-ball` `valid` with one game ref, then train/test/challenge fallback if needed.

- [x] **Step 3: Write a fetch approval contract**

Write `controlled_label_sample_fetch_contract.json` with `files = ["Labels.json"]`, `maxGameCount = 1`, `approvalRequiredBeforeDownload = true`, and original-video download disallowed.

### Task 3: Execute And Verify

**Files:**
- Modify: `memorybank/currentRoadmap.md`
- Modify: `memorybank/activeContext.md`
- Modify: `SESSION-HANDOFF.md`
- Modify: `backend/storage/automation/unattended_roadmap_loop_status.json`

- [x] **Step 1: Generate real artifacts**

Run:

```bash
python3 backend/scripts/run_football_external_soccernet_controlled_label_metadata_probe.py
```

- [x] **Step 2: Update roadmap truth**

Set next lever to `football_external_soccernet_controlled_label_sample_fetch_approval`.

- [x] **Step 3: Verify**

Run focused pytest, py_compile, secret scan, and RunPod hygiene.
