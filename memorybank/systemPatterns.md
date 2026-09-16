# System Patterns

## High-Level Architecture

The repo has three main layers:

1. backend processing and APIs
2. frontend review and analysis UI
3. generated artifact surfaces used for proof and robustness decisions

The backend does the heavy work. The frontend consumes structured outputs. The proof tooling exists to make engineering decisions traceable.

## Core Backend Pattern

The backend pattern is:

- ingest video and match config
- create match/job records in storage
- process video into raw rows, frames, analytics, and events
- materialize proof artifacts such as `ball_truth_layers`, `ball_pipeline_trace`, and `proof_summary`
- reuse saved matches for benchmark suites and robustness analysis

Important implementation paths:

- `backend/app/main.py` for HTTP/API orchestration
- `backend/app/storage.py` for SQLite metadata plus JSON artifact persistence
- `backend/run_guerilla.py` for the main proof and recovery pipeline
- `backend/scripts/` for batch drivers, proof runners, and benchmark entrypoints

## Storage Pattern

Storage is hybrid:

- SQLite for match/job metadata
- JSON files for large or structured artifacts
- CSV/JSON summary files for benchmark suites

Important persistent roots:

- `backend/storage/matches/`
- `backend/storage/pod_cycles/`
- `backend/storage/benchmark_suites/`

## Truth-Surface Pattern

This codebase uses generated artifacts as decision surfaces. The intended pattern is:

- product and engineering truth is written to artifacts first
- docs and handoffs consume those artifacts
- manual status text should not diverge from generated state

That is why files like `active_lane_snapshot.json`, `suite_summary.json`, and proof summaries matter so much.

## Proof And Robustness Pattern

There are two related but distinct loops:

1. proof loop
   - runs a real local or remote processing job on a clip
   - emits `proof_summary`, `ball_truth_layers`, `selected_cluster_delta`, and other match artifacts

2. robustness loop
   - reuses saved matches and manifests
   - computes suite-level summaries and diagnoses
   - compares source-conditioned configs and detector breadth surfaces

The robustness loop should not fabricate wins from replay counts. Product decisions should come from product metrics.

## Remote Execution Pattern

RunPod usage is pod-based and session-oriented:

- create or reuse one pod
- sync repo and clip once
- bootstrap runtime once
- run remote commands over SSH
- stage model weights explicitly
- pull artifacts back to local storage
- stop and delete the pod

This pattern now also applies to detector breadth screening, not just proof cycles.

## Frontend Pattern

The frontend is a React/Vite app that sits on top of saved backend outputs. It is oriented around:

- match selection
- pitch and timeline review
- analysis overlays
- trust-crop and issue surfaces
- AI-assisted insight panels

It is a consumer of persisted state, not the owner of processing truth.

## Important Architectural Constraints

- local-first remains the default product shape
- remote compute is optional acceleration, not a different architecture
- benchmark and proof tooling are first-class, not temporary debugging code
- the repo still carries a research sidecar, but that sidecar should not steer mainline cleanup or architecture choices
