# GPU Handoff Contract

## Purpose

This document freezes the local frontend/backend contract that a future serverless GPU worker must preserve. GPU execution may replace where inference runs, but it must not change what the operator sees as job state, upload recovery behavior, or saved workspace layout.

## Current Local Truth

- canonical trimmed-clip proof match: `e4795c0bf5274072851cc6478cb0dd2d`
- canonical proof job: `c04b728f765644fe91a188cfdb5bb24a`
- canonical benchmark command:
  - `PYTHONPATH=. python3 backend/scripts/run_trimmed_clip_benchmark.py --match-id e4795c0bf5274072851cc6478cb0dd2d`

The current proof is good enough to freeze the contract even though the output quality is still weak (`withBallFrames: 0`, `eventCount: 0`, `requiresTeamSelection: true`).

## Upload Contract

`POST /api/matches`

Multipart fields:

- `name: string`
- `inputMode: "tracking_json" | "video"`
- `config: string` containing JSON
- `file: File`

Current video config shape:

```json
{
  "attackDirection": "left_to_right",
  "manualHomographyPoints": [
    { "x": 0.0, "y": 0.0 },
    { "x": 100.0, "y": 0.0 },
    { "x": 100.0, "y": 100.0 },
    { "x": 0.0, "y": 100.0 }
  ],
  "myTeamCluster": null,
  "llmProvider": "local",
  "autoHomography": false
}
```

Accepted response shape:

```json
{
  "matchId": "<id>",
  "jobId": "<id>",
  "status": "queued"
}
```

## Job Contract

`GET /api/jobs/{jobId}`

Required fields:

- `id`
- `matchId`
- `status`
- `progress`
- `message`
- `error`
- `logPath`
- `startedAt`
- `completedAt`
- `durationSeconds`
- `createdAt`
- `updatedAt`

Current job lifecycle states in operator-facing use:

- `queued`
- `processing`
- `completed`
- `failed`

Rules:

- GPU execution may not invent new terminal semantics without updating the frontend.
- Terminal failures must still surface `error` or `message`.
- `logPath` must remain stable for local debugging and remote-worker parity.

## Match / Review Contract

`GET /api/matches/{matchId}`

Required review-gating fields:

- `status`
- `requiresTeamSelection`
- `teamClusters`

`GET /api/matches/{matchId}/frames`

Required unresolved-team review fields:

- `myTeam`
- `enemies`
- `unassignedPlayers`
- `possession`

Current truth rule:

- if `requiresTeamSelection = true`, players must remain reviewable through `unassignedPlayers`
- GPU execution must not silently auto-pick a team cluster

## Artifact Contract

Per finished video match workspace:

- `frames.json`
- `analytics.json`
- `events.json`
- `raw_rows.json`

Current trimmed-clip benchmark summary reads:

- `rawRowCount`
- `frameCount`
- `withBallFrames`
- `eventCount`
- `eventTypes`
- `shotCount`
- artifact presence booleans

GPU execution may improve these metrics, but must continue writing the same artifact files.

## Known Gap To Preserve Honestly

The frontend already models:

- `ballSignalStatus`
- `ballSignalMessage`

But the backend in this repo snapshot does not yet emit those fields in `analytics.summary`. Until that becomes backend-native, GPU migration must not pretend the field is already part of the portable API contract.
