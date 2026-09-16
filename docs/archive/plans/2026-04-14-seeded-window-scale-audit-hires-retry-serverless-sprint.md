# Seeded Window Scale Audit + Hi-Res Retry Serverless Sprint

## Summary

This batch implemented the detector-side hi-res retry path and the serverless automation needed to validate it without pod babysitting.

The code side is complete and verified. The remote proof side is still blocked on cheap serverless worker allocation/startup before first heartbeat, so there is no fresh football-quality result from this batch yet.

## What Landed

- direct-seed hi-res retry support and summary plumbing were already present in:
  - `backend/run_guerilla.py`
  - `backend/app/run_benchmarks.py`
  - `backend/scripts/run_local_app_path_proof.py`
  - `backend/scripts/run_remote_app_path_proof.py`
  - `backend/scripts/run_pod_proof_cycle.py`
- serverless wrapper/runtime hardening landed in:
  - `backend/scripts/run_managed_remote_app_path_proof.py`
  - `backend/tests/test_run_managed_remote_app_path_proof.py`
- serverless handler build/runtime changes landed in:
  - `.dockerignore`
  - `backend/runpod_handler/Dockerfile`

## Key Runtime Fixes

- `run_managed_remote_app_path_proof.py` now forces `QT_QPA_PLATFORM=offscreen` before backend imports.
- the same script now hydrates object-storage settings and AWS creds from the Runpod template when the parent shell does not export them.
- `_wait_for_endpoint_ready(...)` no longer treats a bare HTTP `200` with zero workers as "warm ready".
- default managed proof GPU was changed from H100 to `NVIDIA GeForce RTX 5090`.
- `.dockerignore` now sends only the handler-required files into Docker build context.
- the serverless handler base image moved to `runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404` to align with the newer CUDA/Torch stack needed for Blackwell-class GPUs.

## Verification

- `PYTHONPATH=/root/WorkSpace/fotball-analyst python3 -m pytest -q backend/tests/test_run_managed_remote_app_path_proof.py backend/tests/test_run_pod_proof_cycle.py backend/tests/test_run_remote_app_path_proof.py` -> `17 passed`
- `./backend/venv/bin/python -m ruff check backend/scripts/run_managed_remote_app_path_proof.py backend/tests/test_run_managed_remote_app_path_proof.py backend/scripts/run_pod_proof_cycle.py` -> `All checks passed!`

## Fresh Serverless Evidence

### 5090 attempt on new CUDA 12.8 image

- proof name: `seeded-window-scale-audit-hires-retry-serverless-5090-cu128`
- endpoint: `zsnzyrv8qim3d0`
- match: `b2354005f6ad4c69ad6ecfbcca94d9dd`
- result:
  - `usedObjectStorage=true`
  - async job was submitted successfully
  - worker never reached first heartbeat
  - transport stayed `IN_QUEUE`
  - endpoint health showed a worker stuck in initialization
  - endpoint was manually deleted after the low-cost lane stayed pre-heartbeat too long

### 3090 attempt after template-env hydration fix

- proof name: `seeded-window-scale-audit-hires-retry-serverless-3090-cu128`
- endpoint: `rcfc9e028dutia`
- match: `dd00ac1d1adf456bb86c21eaa273a967`
- result:
  - `usedObjectStorage=true`
  - async job was submitted successfully
  - transport stayed `IN_QUEUE`
  - endpoint health showed `jobs.inQueue=1` and zero workers allocated for the whole wait window
  - no worker heartbeat ever appeared
  - endpoint was manually deleted after the queue stayed workerless

### Earlier 3090 launcher failure now fixed

- match: `51b33c9259a945f3993ccf0d11e3985b`
- cause: local wrapper lacked object-storage env and failed back to inline upload
- error:
  - `Video file is too large for inline Runpod upload`
- this is the exact seam fixed by template-env hydration

## Honest Outcome

- code/automation outcome:
  - `implemented and verified`
- detector outcome:
  - `not yet measured on a fresh successful remote proof`
- runtime outcome:
  - `cheap serverless allocation/startup remains the blocker`

There is still no valid fresh remote football result from this batch, so do not write a detector-quality binary win/loss for the hi-res retry experiment yet.

## Next Exact Move

- keep the new serverless wrapper/runtime fixes
- keep endpoints deleted when idle
- do not spend on H100 for this lane
- before more detector cooking, get one valid remote proof on a non-H100 serverless GPU that actually starts
- once a cheap/acceptable serverless worker reaches first heartbeat, rerun:
  1. fresh remote proof
  2. explicit selected-cluster promotion
  3. proof summary + `selected_cluster_delta.json` + `recovery_profile_matrix.json`
- only after that should the roadmap record whether hi-res direct-seed retry helped the truth gates
