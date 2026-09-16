# Football External Benchmark Real Evaluation Chain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the next five roadmap batches after `football_external_benchmark_real_evaluation_design`: governance, approval, bounded real execution, report/product binding, and finish-line integration planning.

**Architecture:** Each batch is a saved-artifact script under `backend/scripts/` that reads the previous batch's generated truth and writes a versioned directory under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/`. The chain remains bounded and non-mutating: no detector training, no promotion, no runtime-default mutation, and no normal match storage mutation.

**Tech Stack:** Python stdlib scripts, pytest, generated JSON/Markdown artifacts.

---

### Task 1: Chain Contract Tests

**Files:**
- Create: `backend/tests/test_run_football_external_benchmark_real_evaluation_chain.py`

- [x] **Step 1: Write the failing tests**
- [x] **Step 2: Run tests to verify missing modules fail**
- [x] **Step 3: Implement all five saved-artifact scripts**
- [x] **Step 4: Run the chain locally**
- [x] **Step 5: Run focused and full backend verification**

### Task 2: Roadmap State

**Files:**
- Modify: `memorybank/activeContext.md`
- Modify: `memorybank/progress.md`
- Modify: `SESSION-HANDOFF.md`
- Modify: `backend/storage/automation/unattended_roadmap_loop_status.json`

- [x] **Step 1: Update current truth to the finish-line integration plan**
- [x] **Step 2: Point the active queue at the next execution lever**
- [x] **Step 3: Verify generated truth and tests before final response**
