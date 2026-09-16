# GPU Adoption Execution Plan

> **For agentic workers:** Keep local truth contracts stable. This plan is about moving heavy execution only, not redefining product behavior.

## Goal

Adopt serverless GPU execution for heavy video inference while preserving the local upload/review contract already proven on the trimmed clip.

## Local Truth That Must Not Change

The following are now fixed product behavior and must remain invariant during GPU adoption:

- upload flow and payload shape:
  - `POST /api/matches`
  - multipart `name`, `inputMode`, `config`, `file`
- manual calibration recovery:
  - auto-detect failure stays operator-visible
  - manual 4-corner fallback stays available
  - retrying the same selected file stays possible
- job lifecycle semantics:
  - `queued`
  - `processing`
  - `completed`
  - `failed`
- terminal job payload fields:
  - `logPath`
  - `startedAt`
  - `completedAt`
  - `durationSeconds`
- review gating behavior:
  - unresolved team selection remains unresolved
  - operators review neutral `unassignedPlayers` until a team is chosen
- artifact layout:
  - `frames.json`
  - `analytics.json`
  - `events.json`
  - `raw_rows.json`
- trimmed-clip benchmark command:
  - `PYTHONPATH=. python3 backend/scripts/run_trimmed_clip_benchmark.py --match-id <match_id>`

## What May Move To GPU

These concerns can move behind a remote adapter:

- YOLO / BoT-SORT execution
- heavy frame processing runtime
- detector / tracker configuration profiles
- remote worker packaging and deployment
- remote job orchestration and polling

These concerns must not move into the frontend:

- truth gating decisions
- upload recovery behavior
- review-surface semantics
- artifact interpretation logic

## Adapter Seam

Preferred seam:

- keep `POST /api/matches` unchanged
- keep `GET /api/jobs/{jobId}` unchanged
- keep saved workspace artifact layout unchanged
- swap job execution behind `backend/app/jobs.py`

Target shape:

1. local API creates match + job exactly as today
2. job runner submits work to remote GPU worker instead of local subprocess
3. remote worker returns normalized tracking payload or saved artifact bundle
4. local backend imports results into the same storage contract
5. frontend continues polling the same local job endpoint

## First GPU Lane

### Phase 1: Remote execution adapter

- introduce a backend adapter module for remote submission
- preserve local runner as fallback/dev path
- record remote identifiers in job message/log context if useful

Shipped baseline:

- template: `r4e1k0irw9`
- endpoint: `pfp9xpb3df1haw`
- backend adapter files:
  - `backend/app/settings.py`
  - `backend/app/runpod.py`
  - `backend/app/runpod_worker.py`
  - `backend/runpod_handler/handler.py`

Current upgraded baseline:

- historical template: `aw37g71srz`
- historical endpoint: `k7lorgvsa017bv`
- historical image: `docker.io/ms81vs/fotball-analyst-runpod-handler:neutral-events-v1`
- real API-backed remote proof now completes through the live endpoint and persists local artifacts
- cost-control reality:
  - all Runpod pods/endpoints from this lane were intentionally deleted to avoid idle spend
  - do not assume any Runpod endpoint is alive between sessions
  - spin up one small serverless endpoint only when remote proof is needed
  - after the proof run, scale workers to zero or delete the endpoint again
- latest recovery-matrix proof:
  - remote Runpod L4 run completed for match `1736b72a36ca4fb7913632adb5a88a92`
  - saved result: `backend/storage/matches/1736b72a36ca4fb7913632adb5a88a92/runpod_recovery_matrix_2026-04-10_l4.json`
  - all tested profiles were non-viable because selected tracks stayed edge dominated
  - width-capping the player-window crop is not the fix
  - all endpoints from that proof were deleted after result capture
  - production fallback merge now rejects non-viable recovered ball tracks before they enter app data
- latest candidate-generation proof:
  - remote Runpod L4 run completed for the widened six-profile matrix
  - saved result: `backend/storage/matches/1736b72a36ca4fb7913632adb5a88a92/runpod_recovery_matrix_quality_v2_2026-04-10_l4.json`
  - `upper_crop_band_075` and `edge_margin_40_upper_075` were viable with `11` selected frames and `edgeFrameShare 0.091`
  - production recovery now uses the trusted combined gate:
    - `crop_edge_margin = 40`
    - `max_crop_center_y_ratio = 0.75`
  - final pushed handler image: `docker.io/ms81vs/fotball-analyst-runpod-handler:recovery-matrix-trusted-v1`
  - final image digest: `sha256:0ba612e9305c7e6c2dd0bfc0152f3df3488e52f0be1a849da54220d6055f3ba3`
  - all Runpod endpoints from the proof were deleted after result capture
- latest app-path benchmark correction:
  - old saved trimmed match `1736b72a36ca4fb7913632adb5a88a92` has higher raw coverage (`withBallFrames 45`) but is now flagged `ballTrackViable false` because `ballTrackEdgeFrameShare` is `0.844`
  - fresh trusted local rerun `839a4bb67c4b4f3d8206ea2402fdf8c1` has lower coverage (`withBallFrames 10`) but is flagged `ballTrackViable true` with `ballTrackEdgeFrameShare 0.1`
  - benchmark truth gates now reject edge-hugging false ball coverage via `Need viable ball track: meaningful motion and edgeFrameShare <= 60%`
  - next detector target is viable in-field ball coverage, not raw ball-frame count
- latest local threshold promotion:
  - direct sweep found `max_crop_center_y_ratio = 0.78` as the best local middle ground before edge noise returns
  - `0.78` produced `21` direct selected frames with `edgeFrameShare 0.333` and `viable true`
  - `0.80` produced more selected frames but crossed into `edgeFrameShare 0.732` and `viable false`
  - production fallback now uses `crop_edge_margin = 40` plus `max_crop_center_y_ratio = 0.78`
  - current pushed handler image: `docker.io/ms81vs/fotball-analyst-runpod-handler:recovery-matrix-trusted-078-v1`
  - current image digest: `sha256:ef133cbe6fe1c45d51996e73223aa8621d3c05966ba8d7cdff75c2cfe10ea337`
  - container smoke proof confirmed the `0.78` gate and the `edge_margin_40_upper_078` quality-matrix profile inside the pushed image
  - Runpod L4 proof on endpoint `4md59idwemb9fj` completed as run `b0178257-8d4f-4bb7-b1ba-390ec285557a-e2`
  - saved remote result: `backend/storage/matches/664bb52fd4294eb98341ea7b6a012f76/runpod_recovery_matrix_trusted_078_2026-04-11_l4.json`
  - remote `edge_margin_40_upper_078` matched the local direct sweep: `frames 21`, `edgeFrameShare 0.333`, and `viable true`
  - endpoint `4md59idwemb9fj` was deleted after result capture, and `runpodctl serverless list` returned `[]`
  - normal Runpod handler smoke also completed on endpoint `j0gr8mqqmu6537` as run `ebbc3db4-e060-4b49-8106-1329c439189c-e1`
  - saved normal handler result: `backend/storage/matches/664bb52fd4294eb98341ea7b6a012f76/runpod_full_pipeline_trusted_078_2026-04-11_l4.json`
  - normal handler returned `2265` rows across `360` unique frames with entity counts `player: 2245`, `ball: 20`, and `trackColors: 195`
  - endpoint `j0gr8mqqmu6537` was deleted after result capture, and `runpodctl serverless list` plus `runpodctl pod list` returned `[]`
  - fresh app-path rerun `664bb52fd4294eb98341ea7b6a012f76` produced `20` with-ball frames, `eventTypes {"pass": 1, "recovery": 4}`, `ballTrackEdgeFrameShare 0.35`, and `ballTrackViable true`
  - manual non-headless homography fallback was also fixed after Ruff caught an undefined `selected_points` reference

### Phase 2: Result import

- import remote output into local storage
- continue writing:
  - `raw_rows.json`
  - `frames.json`
  - `analytics.json`
  - `events.json`

### Phase 3: Validation against trimmed-clip benchmark

- run the same trimmed clip through the GPU path
- summarize with:
  - `PYTHONPATH=. python3 backend/scripts/run_trimmed_clip_benchmark.py --match-id <gpu_match_id>`
- one-command remote proof command now available:
  - `PYTHONPATH=. PROCESSING_BACKEND=runpod RUNPOD_API_KEY=<redacted> RUNPOD_ENDPOINT_ID=<endpoint_id> python3 backend/scripts/run_remote_video_benchmark.py --runsync --video-path <clip.mp4> --name <proof-name>`
  - optional manual calibration override if the exported trim has different dimensions:
    - `--manual-points-json '[[10,10],[1270,10],[1270,710],[10,710]]'`
  - the command fails before creating a match if `PROCESSING_BACKEND=runpod`, `RUNPOD_API_KEY`, or `RUNPOD_ENDPOINT_ID` are missing
  - the command creates a local match, uploads the video via Runpod object storage when needed, submits the Runpod job, imports the result into normal match artifacts, and prints compact JSON with `savedMatchId`, `jobId`, `rawRows`, `frameCount`, `playerFrames`, `ballFrames`, `eventTypes`, `ballSignalStatus`, `ballTrackViable`, and `truthGateReasons`
  - current 2026-04-11 note: prefer `--runsync` for benchmark proofs because current Runpod async `/run` can return run ids whose `/status/<id>` comes back as `job not found`
- compare against the current proof snapshots:
  - old local proof floor:
    - `rawRowCount: 306`
    - `frameCount: 124`
    - `withBallFrames: 0`
    - `eventCount: 0`
    - `requiresTeamSelection: true`
  - newer local tracker/ball proof:
    - `rawRowCount: 2290`
    - `frameCount: 360`
    - `withBallFrames: 45`
    - `eventCount: 4`
    - `requiresTeamSelection: true`
  - current remote proof:
    - `rawRowCount: 2291`
    - `frameCount: 360`
    - `withBallFrames: 46`
    - `trackedPossessionFrames: 33`
    - `controlledPossessionFrames: 33`
    - `eventCount: 7`
    - `eventTypes: {"recovery": 4, "pass": 2, "carry": 1}`
    - `fiveMinuteTruthReady: false`
    - `fortyFiveMinuteTruthReady: false`
    - `requiresTeamSelection: false`
  - current local post-guardrail truth:
    - saved trimmed benchmark now improves to `4 recoveries + 2 passes + 1 carry`
    - neutral carry / identity-resolution safety fixes are kept for honesty
    - resolved same-player controlled segments can now emit a bounded `carry`
    - short same-track dead-ball gaps are now bridged at the possession layer
    - repeated static-cluster neutral recoveries are now suppressed across a longer recent window
    - selected-cluster probe now reports both cluster outcomes from one command
    - richer event families are no longer the main blocker on cluster `0`

The GPU path does not need to match every intermediate metric exactly. It does need to:

- preserve job / artifact contract
- preserve failure semantics
- avoid regressing operator trust surfaces
- move from all-zero output into non-zero ball/event activation on the trimmed clip

## Now TODO From Future-Improvements Triage

These are the pieces from `Guerilla Analytics_ Future Improvements.md` that help the current sprint and should be folded into the active lane:

1. Capture discipline:
   - Use exact MP4 files, not YouTube or re-encoded public hosts, for benchmark inputs.
   - Prefer S3 / Runpod object storage references for clips larger than inline upload limits.
   - For laptop-exported trims, keep resolution stable when possible and pass `--manual-points-json` when calibration differs.
2. Runpod serverless proof:
   - Keep using one small L4 endpoint at a time with `workersMin=0`, `workersMax=1`.
   - Delete endpoints after each proof and verify `runpodctl serverless list` plus `runpodctl pod list` return `[]`.
3. Operator trust UX:
   - Surface low ball coverage, non-viable ball tracks, and unresolved team selection as operator-visible cautions.
   - Do not let LLM output present low-confidence metrics as fully trustworthy.
4. LLM context engineering:
   - Keep prompts grounded in derived artifacts and truth gates only.
   - Use LLMs for explanation and coaching language, not for inventing physical-load or Catapult-style metrics.
5. Active-learning preparation:
   - Keep collecting/reviewing uncertain windows via trust crops.
   - Do not start YOLO fine-tuning until reviewed crops/labels exist and the detector autoresearch loop is ready.

## Recommended Next Implementation Order

Superseded on 2026-04-11 by `docs/superpowers/plans/2026-04-11-active-now-systematic-roadmap.md`. Keep the historical notes above for evidence, but follow the active roadmap for current task order.

1. Add a remote execution adapter interface behind `JobRunner`
2. Add a remote-worker stub implementation with deterministic fake success/failure for tests
3. Add local import logic for remote results into `Storage`
4. Add one end-to-end API test for remote-path job completion
5. Improve remote output quality beyond neutral recoveries on the trimmed clip

## Go / No-Go Rule

Go to GPU adoption now if:

- local proof remains stable
- benchmark helper remains green
- contract tests remain green

Do not widen into new product behavior during GPU adoption. Treat GPU as an execution swap, not a redesign project.
