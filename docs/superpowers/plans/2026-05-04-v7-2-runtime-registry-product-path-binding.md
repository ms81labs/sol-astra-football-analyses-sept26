# V7.2 Runtime Registry Product Path Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ordinary local and RunPod-backed video jobs consume the active v7.2 runtime registry by default, then write a generated truth artifact proving the product path is bound.

**Architecture:** Per-match `proof_runtime_options.json` remains the highest-priority override. If a match has no override, `backend/app/proof_runtime.py` resolves the active `backend/storage/runtime/promoted_touchline_detector_candidate.json` default registry when `runtimeDefaultMutationExecuted` is true. RunPod payloads forward the same auxiliary model/profile fields that local jobs already use.

**Tech Stack:** Python, FastAPI backend storage artifacts, RunPod handler payloads, pytest, generated JSON truth artifacts.

---

### Task 1: Product Runtime Registry Resolver

**Files:**
- Modify: `backend/app/proof_runtime.py`
- Test: `backend/tests/test_processor.py`

- [ ] Add a failing test showing `process_match()` uses the active runtime registry when no per-match `proof_runtime_options.json` exists.
- [ ] Implement registry loading in `load_proof_runtime_options()`.
- [ ] Preserve per-match overrides as higher priority than the registry.
- [ ] Verify focused processor tests pass.

### Task 2: RunPod Auxiliary Runtime Payload

**Files:**
- Modify: `backend/app/runpod.py`
- Modify: `backend/app/runpod_worker.py`
- Modify: `backend/runpod_handler/handler.py`
- Test: `backend/tests/test_runpod.py`
- Test: `backend/tests/test_runpod_worker.py`
- Test: `backend/tests/test_runpod_handler.py`

- [ ] Add failing tests for auxiliary model/profile payload inclusion and handler forwarding.
- [ ] Add `auxiliaryBallModelPath` and `auxiliaryBallModelProfile` to RunPod payloads.
- [ ] Load those fields in `run_remote_job()`.
- [ ] Forward them from the RunPod handler into `process_video_input()`.
- [ ] Verify focused RunPod tests pass.

### Task 3: Generated Binding Truth

**Files:**
- Create: `backend/scripts/run_v7_2_runtime_registry_product_path_binding.py`
- Test: `backend/tests/test_run_v7_2_runtime_registry_product_path_binding.py`

- [ ] Add tests for summary generation from real or temporary runtime registry state.
- [ ] Write the script to emit `v7_2_runtime_registry_product_path_binding_v1/` artifacts.
- [ ] Include three failsafe families: `product_path_runtime_registry_binding`, `runpod_auxiliary_runtime_payload_repair`, `runtime_registry_product_binding_blocker_summary`.
- [ ] Verify script and tests pass.

### Task 4: Verification

**Files:**
- No source edits unless verification exposes a failure.

- [ ] Run focused tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  backend/tests/test_processor.py \
  backend/tests/test_runpod.py \
  backend/tests/test_runpod_worker.py \
  backend/tests/test_runpod_handler.py \
  backend/tests/test_run_v7_2_runtime_registry_product_path_binding.py -q
```

- [ ] Run py_compile:

```bash
python3 -m py_compile \
  backend/app/proof_runtime.py \
  backend/app/runpod.py \
  backend/app/runpod_worker.py \
  backend/runpod_handler/handler.py \
  backend/scripts/run_v7_2_runtime_registry_product_path_binding.py
```

- [ ] Generate artifacts:

```bash
python3 backend/scripts/run_v7_2_runtime_registry_product_path_binding.py
```

- [ ] Confirm RunPod hygiene:

```bash
runpodctl pod list --all -o json
```
