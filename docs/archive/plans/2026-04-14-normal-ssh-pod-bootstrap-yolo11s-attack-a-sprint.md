# 2026-04-14 Normal-SSH Pod Bootstrap + YOLOv11s Attack A Sprint

## Summary

This sprint completed the first valid promoted `YOLOv11s` pod proof on a normal SSH/SCP lane.

What changed:

- `backend/scripts/run_pod_proof_cycle.py` was hardened around a real normal-SSH contract:
  - prefer `ip` / `port` from `runpodctl ssh info`
  - add noninteractive SSH flags
  - retry transport smoke until SSH is actually ready
  - stage only the runtime subset plus the 5-minute clip
- proof-only model override was exercised on pod with:
  - `--model-path /workspace/weights/yolo11s.pt`

Execution lane:

- pod: `x5ipivwjawhrwa`
- GPU: `NVIDIA GeForce RTX 5090`
- image: `runpod/pytorch:1.0.3-cu1281-torch291-ubuntu2404`

## Verification

- `PYTHONPATH=/root/WorkSpace/fotball-analyst pytest -q backend/tests/test_run_pod_proof_cycle.py backend/tests/test_run_local_app_path_proof.py backend/tests/test_run_remote_app_path_proof.py backend/tests/test_run_managed_remote_app_path_proof.py`
  - `33 passed`
- `./backend/venv/bin/python -m ruff check backend/scripts/run_pod_proof_cycle.py backend/tests/test_run_pod_proof_cycle.py backend/scripts/run_local_app_path_proof.py backend/scripts/run_remote_app_path_proof.py backend/scripts/run_managed_remote_app_path_proof.py`
  - clean

## Fresh Proof

Fresh proof:

- match: `870511294b8d4038880385fef7322e9a`
- job: `56aa6dea8380470b9a484d727796218c`
- detector: `yolo11s.pt`
- selected cluster after promotion: `0`

Pulled artifacts:

- `backend/storage/pod_artifacts/model-tier-upgrade-yolo11s-attack-a-pod-local-proof.json`
- `backend/storage/pod_artifacts/model-tier-upgrade-yolo11s-attack-a-pod-selected-cluster-delta.json`
- `backend/storage/pod_artifacts/model-tier-upgrade-yolo11s-attack-a-recovery-profile-matrix.json`

## Result

Pre-promotion summary:

- `acceptedBallFrames=88`
- `controlledPossessionFrames=0`
- `bestProposalDirectSeedDetectedFrames=10`
- `bestProposalDirectSeedHiResRetryDetectedFrames=10`
- `bestProposalPlayerRankedDetectedFrames=0`
- `bestProposalProfileName=proposal_windows_075`
- `bestProposalSelectedFrames=10`

After explicit selected-cluster promotion:

- `acceptedBallFrames=88`
- `controlledPossessionFrames=52`
- `eventFamilyCount=4`
- `ballTrackEdgeFrameShare=0.727`
- `ballTrackViable=false`

Interpretation:

- `YOLOv11s` is a real mechanism success:
  - direct-seed detections woke up
  - hi-res retry contributed
  - proposal detections shifted away from `player_ranked`
- but it is not a product success on the 5-minute truth gates:
  - accepted ball coverage regressed versus the `101` plateau
  - controlled possession regressed versus the `98` plateau
  - ball track remains non-viable

Binary outcome:

- `YOLOv11s Attack A achieved mechanism success but did not materially improve the 5-minute truth gates`

## Decision

Next batch is now locked:

- `Attack B: multi-scale direct-seed ensemble`

Do not do next:

- more proposal geometry micro-tweaks
- more activation-only work
- more team-selection tuning
- serverless confirmation for this exact result

Reason:

- Attack A completed cleanly enough to make the detector-model lane decision
- it gave real mechanism evidence, but not enough product lift to justify confirmation-first spending

## Repeatable Runbook

Use this exact path next time instead of re-discovering it:

1. Create or reuse a **public-IP pod with normal SSH/SCP**, not `ssh.runpod.io` proxy-shell routing.
2. Verify transport before any proof work:
   - `ssh root@<ip> -p <port> 'printf ok'`
   - `scp` a tiny smoke file
3. Use noninteractive SSH flags:
   - `-o IdentitiesOnly=yes`
   - `-o StrictHostKeyChecking=no`
   - `-o UserKnownHostsFile=/dev/null`
   - `-i ~/.ssh/id_ed25519`
4. Stage only the runtime subset plus the 5-minute clip:
   - `backend/app`
   - `backend/scripts`
   - `backend/runpod_handler`
   - `backend/run_guerilla.py`
   - `backend/pitch_detector.py`
   - `backend/requirements.txt`
   - `backend/__init__.py`
   - `videos/trimed-5min.mp4`
5. Reuse `/workspace` as the persistent root:
   - repo: `/workspace/fotball-analyst`
   - venv: `/workspace/fotball-venv`
   - weights: `/workspace/weights/yolo11s.pt`
6. Bootstrap once, then reuse:
   - venv requirements hash file: `/workspace/fotball-venv/.requirements.sha256`
   - model verified by loading `YOLO('/workspace/weights/yolo11s.pt')`
7. Run the proof from the warmed pod workspace:
   - `python backend/scripts/run_local_app_path_proof.py ... --model-path /workspace/weights/yolo11s.pt`
8. Promotion is a second explicit step:
   - `python backend/scripts/promote_selected_cluster_for_proof.py --storage-root ... --match-id <match-id>`
9. Pull back exactly these artifacts:
   - proof summary
   - `selected_cluster_delta.json`
   - `recovery_profile_matrix.json`
10. Stop the pod immediately after artifact pullback:
   - `runpodctl pod stop <pod-id>`

## Known Gotchas

- Do **not** reuse `ssh.runpod.io` proxy-shell routing for this workload.
- Do **not** trust `runpodctl pod start <old-pod>` to succeed forever; an exited pod can fail to restart if its original host has no free GPUs.
- The earlier model-stage failure came from emitting non-JSON remote output; the fixed path now:
  - imports `json`
  - prints raw `json.dumps(payload)`
- The earlier SSH stall came from host-key prompts; the fixed path now always disables interactive host-key confirmation.
- `run_local_app_path_proof.py` looks quiet because it polls while the real work happens in `backend.app.worker`; if it seems idle, inspect:
  - `/workspace/fotball-analyst/backend/storage/logs/job_<job-id>.log`
