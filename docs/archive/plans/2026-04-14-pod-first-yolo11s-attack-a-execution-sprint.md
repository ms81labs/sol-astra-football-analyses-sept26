# Pod-First YOLOv11s Attack A Execution Sprint

## Status

Code path implemented and verified locally. Runtime A/B proof on pod `8ju4l0eo9ynw32` is still blocked by the pod transport lane, not by detector logic yet.

## What Landed

- `backend/scripts/run_pod_proof_cycle.py`
  - added `--pod-id`
  - added `--ssh-target`
  - added `--model-path`
  - added `--remote-model-path`
  - added detector provenance to returned cycle payload
  - added plateau comparison with:
    - `mechanismSuccess`
    - `productSuccess`
    - `beatsPlateau`
- hardened direct Runpod proxy handling:
  - proxy SSH target now uses `ssh -tt`
  - remote command parsing now extracts the last JSON object from noisy stdout
- model staging:
  - named asset path `yolo11s.pt` stages to `/workspace/weights/yolo11s.pt`
  - local file model staging is also supported
- sync path narrowed to runtime essentials only:
  - `backend/app`
  - `backend/scripts`
  - `backend/runpod_handler`
  - `backend/run_guerilla.py`
  - `backend/pitch_detector.py`
  - `backend/requirements.txt`
  - `backend/__init__.py`
  - the exact proof clip

## Verification

- `PYTHONPATH=/root/WorkSpace/fotball-analyst pytest -q backend/tests/test_run_pod_proof_cycle.py backend/tests/test_run_local_app_path_proof.py backend/tests/test_run_remote_app_path_proof.py`
  - `18 passed`
- `./backend/venv/bin/python -m ruff check backend/scripts/run_pod_proof_cycle.py backend/tests/test_run_pod_proof_cycle.py`
  - clean

## Runtime Truth

The direct Runpod proxy target behaves like an interactive shell, not a normal command-exec SSH endpoint.

Observed facts:

- `ssh <target> "cmd"` is ignored by the proxy route
- `scp` to the proxy route fails with `subsystem request failed on channel 0`
- `ssh -tt <target>` plus commands over stdin works
- because of that, the pod-cycle had to be adapted away from normal SSH command execution

Fresh live attempts:

- `yolo11s-attack-a-pod-proof`
  - failed during model staging because the helper assumed the last stdout line was raw JSON
- `yolo11s-attack-a-pod-proof-v2`
  - blocked by transport semantics discovered after the parser fix
- `yolo11s-attack-a-pod-proof-v3`
  - still blocked because syncing the whole `backend/` tree dragged the giant local venv into the tar walk
- `yolo11s-attack-a-pod-proof-v4`
  - after narrowing the sync set, the proxy-shell upload still spent 7+ minutes without materializing `/workspace/fotball-analyst` or `/workspace/fotball-venv`

So the honest state is:

- `YOLOv11s` proof-only override is implemented
- pod-cycle reuse and stop-on-exit are implemented
- the actual `Attack A` football proof has **not** completed yet
- current blocker is the proxy-shell upload path for repo + clip staging on this specific pod access route

## Pod State

Pod `8ju4l0eo9ynw32` was stopped again after the blocked attempts to avoid idle cost.

## Next Move

Do not schedule `Attack B` yet. The next step is to unblock one reliable pod transport lane first, with one of:

1. a pod path that supports normal SSH command execution / SCP
2. a prebuilt pod image or pre-synced workspace so we stop pushing the repo + clip through the proxy shell
3. a smaller transfer strategy for the clip itself, separate from repo sync

Only after that should we rerun the real `YOLOv11s` Attack A proof and compare against the plateau:

- `acceptedBallFrames=101`
- `controlledPossessionFrames=98`
- `ballTrackViable=false`
- `ballTrackEdgeFrameShare=0.812`
