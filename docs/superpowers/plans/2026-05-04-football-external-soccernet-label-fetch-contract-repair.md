# Football External SoccerNet Label Fetch Contract Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Approve and attempt the smallest SoccerNet ball-label fetch, then diagnose and repair the contract if the per-game label path is not served.

**Architecture:** The approval batch narrows access to one `Labels.json` for one `spotting-ball` game ref. The fetch batch uses runtime-only SoccerNet credentials and the artifact-local package downloader. If the real fetch fails, the repair batch records root cause and routes to split archive access review without expanding scope automatically.

**Tech Stack:** Python batch scripts, pytest, SoccerNet package downloader, JSON artifacts.

---

### Task 1: Single Label Fetch Approval

**Files:**
- Create: `backend/scripts/run_football_external_soccernet_controlled_label_sample_fetch_approval.py`
- Create: `backend/tests/test_run_football_external_soccernet_controlled_label_sample_fetch_approval.py`

- [x] **Step 1: TDD the approval gate**

Approve only one `Labels.json` for one `spotting-ball` game ref.

- [x] **Step 2: Generate real approval artifact**

Run:

```bash
python3 backend/scripts/run_football_external_soccernet_controlled_label_sample_fetch_approval.py
```

### Task 2: Single Label Fetch

**Files:**
- Create: `backend/scripts/run_football_external_soccernet_controlled_label_sample_fetch.py`
- Create: `backend/tests/test_run_football_external_soccernet_controlled_label_sample_fetch.py`

- [x] **Step 1: TDD the label-only fetch**

Require approval and `SOCCERNET_PASSWORD`, then fetch only the approved `Labels.json`.

- [x] **Step 2: Run real fetch**

The real fetch failed safely with HTTP 404 and no downloaded files.

### Task 3: Contract Repair Diagnosis

**Files:**
- Create: `backend/scripts/run_football_external_soccernet_label_fetch_contract_repair.py`
- Create: `backend/tests/test_run_football_external_soccernet_label_fetch_contract_repair.py`

- [x] **Step 1: Diagnose root cause**

Record `soccernet_spotting_ball_per_game_labels_json_not_served`.

- [x] **Step 2: Route next lever**

Select `football_external_soccernet_split_archive_access_review` before any archive download.

### Task 4: Roadmap And Verification

**Files:**
- Modify: `memorybank/currentRoadmap.md`
- Modify: `memorybank/activeContext.md`
- Modify: `SESSION-HANDOFF.md`
- Modify: `backend/storage/automation/unattended_roadmap_loop_status.json`

- [x] **Step 1: Update generated-truth pointers**

Make contract repair the latest completed batch.

- [ ] **Step 2: Run focused verification**

Run external-lane pytest, py_compile, secret scan, and RunPod hygiene.
