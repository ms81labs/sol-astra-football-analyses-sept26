# Pod-First Proof Recovery Sprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover a reliable GPU proof lane on the upgraded Runpod pod, finish the blocked player-proposal validation there, and only return to serverless for one final confirmation if the pod proof is promising.

**Architecture:** Treat the pod as the primary execution lane for heavy 5-minute proofs and selected-cluster promotion while serverless remains a later confirmation lane. Keep detector logic unchanged at first; use the pod to finish the currently blocked `Player Proposal Expansion Sprint`, then let the resulting football metrics decide whether we continue detector-side proposal work or move on.

**Tech Stack:** Runpod pod + SSH, Python 3.11 venv, PyTorch 2.10.0+cu128, Ultralytics 8.4.14, pytest, Ruff, existing backend proof scripts.

---

## Pod Facts Collected From Runpod

- Pod ID: `37n9f2lf2uq390`
- Name: `neighbouring_white_crab`
- Cost: `$0.64/hr`
- GPU: `NVIDIA RTX PRO 4500 Blackwell`
- GPU memory: `~32 GB`
- RAM: `62 GB`
- vCPU: `28`
- Volume: `100 GB`
- Volume mount: `/workspace`
- Current image: `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04`
- Preferred SSH route: `ssh 37n9f2lf2uq390-644120e6@ssh.runpod.io -i ~/.ssh/id_ed25519`
- Raw SSH port from Runpod metadata: `15476`

## Current Access / Runtime Reality

- The original raw SSH route the user gave (`port 48596`) rotated after the pod resize.
- The raw port route reported by Runpod changed to `15476`.
- The stable path is the Runpod proxy SSH route:
  - `ssh 37n9f2lf2uq390-644120e6@ssh.runpod.io -i ~/.ssh/id_ed25519`
- The proxy route is working and should be preferred over chasing changing raw ports.
- Earlier on the pre-resize pod, the stock image had a broken GPU stack for Blackwell:
  - `torch 2.4.1+cu124`
  - CUDA error: `no kernel image is available for execution on the device`
- A temporary fix was proven on the old port by creating `/root/fotball-venv` and installing:
  - `torch==2.10.0+cu128`
  - `torchvision==0.25.0+cu128`
  - `ultralytics==8.4.14`
- After reconnecting through the proxy route, the stock runtime is still broken:
  - `torch 2.4.1+cu124`
  - `ultralytics` not installed
- So the pod still needs the repaired venv/bootstrap step on the current live instance.

Live storage layout from inside the pod:

- `/workspace` is a network-backed mount with effectively enormous headroom
- `/` is the local overlay and currently reports `100G`
- this means the pod no longer has the earlier 21 GB storage pressure
- use `/workspace` for repo, artifacts, venv, and weights

## Success Criteria

This batch is successful if all of these happen:

- pod SSH access is restored on the current port
- a pod-local proof environment is bootstrapped under the 100 GB volume
- one full 5-minute proof completes on the pod
- explicit selected-cluster promotion completes on that proof
- the result is written into the roadmap/handoff as one of:
  - `player proposal expansion materially improved truthful coverage`
  - `player proposal expansion did not materially improve the 5-minute truth gates`

Secondary success:

- if the pod proof is promising, run exactly one serverless confirmation proof afterward
- if the pod proof is not promising, do **not** spend on a confirmation run

## 2026-04-13 Completion Outcome

The pod-first recovery lane worked and closed the blocked proof loop.

- Pod bootstrap succeeded on `37n9f2lf2uq390`
- the 5-minute proof completed on the pod as match `6b8d61c4921348a8b82f86d23e789751`
- explicit selected-cluster promotion completed with recommended cluster `1`
- result after promotion:
  - `acceptedBallFrames=101`
  - `controlledPossessionFrames=98`
  - `eventFamilyCount=5`
  - `ballTrackEdgeFrameShare=0.812`
  - `ballTrackViable=false`
- player-proposal diagnostics stayed at:
  - `proposalCandidateFrames=0`
  - `proposalWindowCount=0`

Decision:
- the pod lane is now a valid heavy-proof execution path
- the blocked player-proposal sprint is closed as a miss
- no serverless confirmation run is justified from this result

## Constraints

- Keep using the current 5-minute clip only.
- Do not open 10-minute or 45-minute proofs.
- Do not relax truth-gate thresholds.
- Do not reopen team-selection tuning.
- Do not introduce new detector families in this batch.
- Keep storage disciplined even with 100 GB:
  - one repo checkout
  - one venv
  - one weights copy
  - one active proof clip
  - no bulk sync of historical `backend/storage`

### Task 1: Repair Pod Access And Record The Live Pod Contract

**Files:**
- Modify: `SESSION-HANDOFF.md`
- Modify: `docs/superpowers/plans/2026-04-11-active-now-systematic-roadmap.md`

- [ ] Confirm the pod is still the active target:

Run:
```bash
python3 - <<'PY'
import os, tomllib, subprocess
from pathlib import Path
cfg = tomllib.loads(Path('/root/.runpod/config.toml').read_text())
os.environ['RUNPOD_API_KEY'] = cfg['api_key']
subprocess.run(['runpodctl', 'pod', 'get', '37n9f2lf2uq390', '--include-machine', '-o', 'json'], check=True)
PY
```

Expected:
- returns the pod metadata with current SSH port, volume size, and GPU type

- [ ] Restore SSH access on the current port.

Primary command to test:
```bash
ssh -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519 37n9f2lf2uq390-644120e6@ssh.runpod.io
```

If that proxy route fails:
```bash
python3 - <<'PY'
import os, tomllib, subprocess
from pathlib import Path
cfg = tomllib.loads(Path('/root/.runpod/config.toml').read_text())
os.environ['RUNPOD_API_KEY'] = cfg['api_key']
subprocess.run(['runpodctl', 'ssh', 'add-key'], check=False)
PY
```

Then re-run:
```bash
python3 - <<'PY'
import os, tomllib, subprocess
from pathlib import Path
cfg = tomllib.loads(Path('/root/.runpod/config.toml').read_text())
os.environ['RUNPOD_API_KEY'] = cfg['api_key']
subprocess.run(['runpodctl', 'ssh', 'info', '37n9f2lf2uq390', '-o', 'json'], check=False)
PY
```

Expected:
- SSH succeeds through the Runpod proxy and returns a shell prompt

- [ ] Record the post-resize pod facts in the handoff and roadmap.

Add:
- current SSH port
- current volume size
- whether the user key had to be re-added
- whether the old pre-resize venv survived or not

### Task 2: Rebuild A Minimal Working Pod Runtime

**Files:**
- Modify: `SESSION-HANDOFF.md`

- [ ] Inspect disk and decide workspace paths.

Run over SSH:
```bash
hostname
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
df -h /workspace /
free -h
nproc
```

Expected:
- confirms `/workspace` is the main working volume and `/` is the 100G local overlay

- [ ] Create the pod workspace layout.

Run over SSH:
```bash
mkdir -p /workspace/fotball-analyst
mkdir -p /workspace/artifacts
mkdir -p /workspace/cache
mkdir -p /workspace/weights
```

- [ ] Create or recreate the isolated venv.

Run over SSH:
```bash
python3 -m venv /workspace/fotball-venv
source /workspace/fotball-venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --index-url https://download.pytorch.org/whl/cu128 torch==2.10.0 torchvision==0.25.0
python -m pip install ultralytics==8.4.14
mkdir -p /workspace/.config/Ultralytics
```

- [ ] Verify the repaired torch stack before installing the rest of the proof environment.

Run over SSH:
```bash
source /workspace/fotball-venv/bin/activate
python - <<'PY'
import torch
print('torch', torch.__version__)
print('cuda', torch.cuda.is_available())
print('device', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')
x = torch.randn((2, 2), device='cuda')
print((x @ x).cpu().tolist())
PY
```

Expected:
- a CUDA tensor op completes successfully on the Blackwell GPU

- [ ] Prove the GPU stack works on the current resized pod.

Run over SSH:
```bash
source /workspace/fotball-venv/bin/activate
YOLO_CONFIG_DIR=/workspace/.config/Ultralytics python - <<'PY'
import torch, ultralytics
print('torch', torch.__version__)
print('ultralytics', ultralytics.__version__)
print('cuda', torch.cuda.is_available())
print('device', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')
x = torch.randn((2, 2), device='cuda')
print((x @ x).cpu().tolist())
PY
```

Expected:
- CUDA tensor op completes successfully

- [ ] Write the pod bootstrap result to the handoff.

Record:
- actual free disk after bootstrap
- actual torch / ultralytics versions
- actual GPU test output summary

### Task 3: Sync Only The Minimum Repo And Assets

**Files:**
- Modify: `SESSION-HANDOFF.md`

- [ ] Copy a minimal repo snapshot to the pod instead of full historical storage.

Recommended archive from local machine:
```bash
cd /root/WorkSpace
tar \
  --exclude='fotball-analyst/backend/storage' \
  --exclude='fotball-analyst/frontend/node_modules' \
  --exclude='fotball-analyst/.git' \
  --exclude='fotball-analyst/backend/__pycache__' \
  --exclude='fotball-analyst/backend/tests/__pycache__' \
  -czf /tmp/fotball-analyst-pod-sync.tgz fotball-analyst
```

Copy:
```bash
scp -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519 /tmp/fotball-analyst-pod-sync.tgz 37n9f2lf2uq390-644120e6@ssh.runpod.io:/workspace/
```

Unpack over SSH:
```bash
cd /workspace
tar -xzf fotball-analyst-pod-sync.tgz
rm -f fotball-analyst-pod-sync.tgz
```

- [ ] Copy only the one active clip and required weights.

Copy:
```bash
scp -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519 /root/WorkSpace/fotball-analyst/videos/trimed-5min.mp4 37n9f2lf2uq390-644120e6@ssh.runpod.io:/workspace/fotball-analyst/videos/
scp -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519 /root/WorkSpace/yolov10n.pt 37n9f2lf2uq390-644120e6@ssh.runpod.io:/workspace/weights/
```

- [ ] Install the repo’s Python dependencies into the pod venv.

Run over SSH:
```bash
cd /workspace/fotball-analyst
source /workspace/fotball-venv/bin/activate
python -m pip install -r backend/requirements.txt
```

Expected:
- the modern torch stack remains installed and compatible

- [ ] Set environment defaults for the pod session.

Recommended shell exports:
```bash
export QT_QPA_PLATFORM=offscreen
export YOLO_CONFIG_DIR=/workspace/.config/Ultralytics
export PYTHONPATH=/workspace/fotball-analyst
```

### Task 4: Run The Blocked Player-Proposal Proof On The Pod

**Files:**
- Modify: `SESSION-HANDOFF.md`
- Modify: `docs/superpowers/plans/2026-04-11-active-now-systematic-roadmap.md`

- [ ] Run the focused proof-related test slice on the pod first.

Run over SSH:
```bash
cd /workspace/fotball-analyst
source /workspace/fotball-venv/bin/activate
export PYTHONPATH=/workspace/fotball-analyst
python3 -m pytest \
  backend/tests/test_run_guerilla.py \
  backend/tests/test_run_benchmarks.py \
  backend/tests/test_run_local_app_path_proof.py \
  backend/tests/test_run_remote_app_path_proof.py -q
```

Expected:
- focused proof tests pass on the pod runtime

- [ ] Run the current batch’s proof on the pod-local lane.

Run over SSH:
```bash
cd /workspace/fotball-analyst
source /workspace/fotball-venv/bin/activate
export QT_QPA_PLATFORM=offscreen
export YOLO_CONFIG_DIR=/workspace/.config/Ultralytics
export PYTHONPATH=/workspace/fotball-analyst
python backend/scripts/run_local_app_path_proof.py \
  --video-path /workspace/fotball-analyst/videos/trimed-5min.mp4
```

Expected:
- one saved 5-minute proof match artifact is created

- [ ] Promote the selected cluster explicitly on the pod proof result.

Run over SSH:
```bash
cd /workspace/fotball-analyst
source /workspace/fotball-venv/bin/activate
export QT_QPA_PLATFORM=offscreen
export PYTHONPATH=/workspace/fotball-analyst
python backend/scripts/promote_selected_cluster_for_proof.py --match-id <fresh_pod_match_id>
```

Expected:
- `selected_cluster_delta.json` exists for the fresh pod match

- [ ] Extract the key metrics from the promoted pod result.

Record:
- `acceptedBallFrames`
- `recoveredSelectedFrames`
- `controlledPossessionFrames`
- `supportedAcceptedBallRatio`
- `ballTrackEdgeFrameShare`
- `ballTrackViable`
- selected cluster id

### Task 5: Decide The Batch Outcome From Pod Evidence

**Files:**
- Modify: `SESSION-HANDOFF.md`
- Modify: `docs/superpowers/plans/2026-04-11-active-now-systematic-roadmap.md`

- [ ] Compare the promoted pod result against the current success bar.

Success bar:
- `acceptedBallFrames >= 120` with `supportedAcceptedBallRatio >= 0.95`
- or `recoveredSelectedFrames >= 35`
- or `controlledPossessionFrames >= 110`
- or `ballTrackViable == true`

- [ ] If the pod result misses the bar, close the current batch from pod evidence.

Write exactly:
- `player proposal expansion did not materially improve the 5-minute truth gates`

And record the fresh pod proof numbers as the closeout basis.

- [ ] If the pod result clears the bar, run one final serverless confirmation proof.

Only then:
```bash
cd /root/WorkSpace/fotball-analyst
export RUNPOD_API_KEY="$(python3 - <<'PY'
import tomllib
from pathlib import Path
cfg = tomllib.loads(Path('/root/.runpod/config.toml').read_text())
print(cfg['api_key'])
PY
)"
export AWS_ACCESS_KEY_ID='user_3BaoU7L715q2H6lTCM3S07kjQtL'
export AWS_SECRET_ACCESS_KEY='rps_YDDKQF2M4QJ9XER6BUL7X53Y8IKI7QTBL891XEO21x0igt'
export RUNPOD_OBJECT_STORAGE_BUCKET='c7d2d4q0ik'
export RUNPOD_OBJECT_STORAGE_ENDPOINT_URL='https://s3api-eur-is-1.runpod.io'
export RUNPOD_OBJECT_STORAGE_REGION='eur-is-1'
export QT_QPA_PLATFORM=offscreen
GPU_ID="$(python3 - <<'PY'
import os, tomllib, subprocess, json
from pathlib import Path
cfg = tomllib.loads(Path('/root/.runpod/config.toml').read_text())
os.environ['RUNPOD_API_KEY'] = cfg['api_key']
result = subprocess.run(['runpodctl', 'gpu', 'list', '-o', 'json'], check=True, capture_output=True, text=True)
gpus = json.loads(result.stdout)
preferred = ['NVIDIA GeForce RTX 5090', 'NVIDIA GeForce RTX 4090', 'NVIDIA RTX PRO 4500 Blackwell', 'NVIDIA H100 80GB HBM3']
available = {item['gpuId']: item for item in gpus if item.get('available')}
for gpu in preferred:
    if gpu in available:
        print(gpu)
        break
else:
    raise SystemExit('No preferred serverless GPU currently available')
PY
)"
./backend/venv/bin/python backend/scripts/run_managed_remote_app_path_proof.py \
  --transport auto \
  --gpu-id "$GPU_ID" \
  --workers-min 1 \
  --workers-max 1 \
  --warmup-wait-seconds 180 \
  --poll-interval-seconds 5 \
  --timeout-seconds 7200
```

- [ ] Write the final binary outcome only after the pod proof exists, and after serverless confirmation if the pod result is promising.

### Task 6: Keep The Pod Sustainable For Repeated Cooking

**Files:**
- Modify: `SESSION-HANDOFF.md`

- [ ] Measure disk use after the proof loop.

Run over SSH:
```bash
df -h /workspace /
du -sh /workspace/fotball-analyst 2>/dev/null
du -sh /workspace/fotball-venv 2>/dev/null
du -sh /workspace/weights 2>/dev/null
```

- [ ] Clear only low-value caches if the pod gets bloated.

Safe cleanup candidates:
```bash
rm -rf /root/.cache/pip
find /workspace/fotball-analyst/backend/storage -type f -name '*.log' -size +50M -delete 2>/dev/null || true
find /workspace/fotball-analyst/backend/storage/matches -maxdepth 1 -mindepth 1 -type d -printf '%T@ %p\n' | sort -n | head -n -5 | cut -d' ' -f2- | xargs -r rm -rf
```

Expected:
- the pod remains comfortably under the 100 GB ceiling after one proof cycle

## Binary Outcome

At the end of this batch, record exactly one:

- `pod proof succeeded; resume detector roadmap from pod evidence`
- `pod proof still blocked; next batch is pod runtime/bootstrap hardening`

## Recommended Execution Order

1. Repair SSH and confirm the resized pod facts.
2. Rebuild the minimal working Blackwell-compatible runtime.
3. Sync the repo and only the one active clip.
4. Run the current player-proposal proof batch on the pod.
5. Decide the player-proposal sprint outcome from pod evidence.
6. Use serverless only if the pod result is promising enough to justify a confirmation run.
