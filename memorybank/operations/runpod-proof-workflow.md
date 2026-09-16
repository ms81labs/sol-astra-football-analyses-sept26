# RunPod Proof Workflow

## Local Auth Defaults

RunPod auth should live in home-directory config, never repo-tracked files:

- `~/.runpod/config.toml`
- `~/.config/fotball-analyst/runpod.env`

The local `runpodctl` wrapper is expected to source the env file automatically, and the proof/session scripts also read `~/.runpod/config.toml` directly.

## Default Stance

Use RunPod only when the batch truly benefits from remote GPU compute. When it is used, prefer the pod workflow, not serverless.

## Core Rules

- read secrets from `RUNPOD_API_KEY` or `~/.runpod/config.toml`
- use one reusable pod session when a batch has multiple remote steps
- sync repo and clip once per shared session
- bootstrap once per shared session
- stage model weights explicitly
- stop and delete the pod at the end
- verify `runpodctl pod list --all -o json` returns `[]`

## Important Scripts

- `backend/scripts/run_pod_proof_cycle.py`
- `backend/scripts/runpod_session.py`
- `backend/scripts/run_detector_breadth_batch.py`

## Typical Remote Flow

1. create or resolve a pod
2. wait for SSH info
3. run transport smoke checks
4. sync repo and relevant clip to `/workspace/fotball-analyst`
5. bootstrap the remote venv and runtime
6. stage the requested model path under `/workspace/weights/`
7. run the proof or batch command remotely
8. pull proof summaries and supporting artifacts back into local `backend/storage/`
9. stop and delete the pod

## Current Operational Lesson

Heavy detector breadth screening should happen remotely, not on the local CPU. The shared-session path was added for exactly that reason.

## Closeout Check

Always end remote work with:

```bash
runpodctl pod list --all -o json
```

Expected closeout in the normal case:

```json
[]
```
