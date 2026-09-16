# Project Brief

## Project Identity

`fotball-analyst` is a local-first football video analysis platform. Its job is to take match video, turn it into structured tracking and event data, and make that data useful through review surfaces, search, export, and proof-oriented engineering workflows.

## Core Goal

Build a trustworthy grassroots football analytics stack that can:

- process raw match video into structured artifacts
- support tactical review and reporting workflows
- run locally by default, with optional RunPod-backed remote execution
- produce proof artifacts that make pipeline quality inspectable rather than mysterious

## Current Source Of Truth

The current project truth lives in:

- `backend/`
- `frontend/`
- `docs/`
- generated artifacts under `backend/storage/`

The canonical product spine is `origin/main`. The live product tree is this repo root. `research-addon/` remains a sidecar, not the mainline product path.

## What Is In Scope

- video upload and match/job orchestration
- player/ball detection, recovery, and proof-style benchmarking
- saved artifacts for truth layers, pipeline traces, proof summaries, and benchmark suites
- React-based review surfaces for playback, insights, trust crops, and analysis
- local and RunPod pod-based execution paths
- tactical reporting, exports, and search over processed matches

## What Is Explicitly Out Of Scope Right Now

- turning the project into a cloud-first SaaS
- multi-camera capture and stitching
- live match inference
- reopening retired fork or worktree-era development paths
- endless tuning of already falsified post-acceptance repair families

## Current Product Constraint

The single-clip canonical proof floor is real, but multi-source robustness is not. The mainline engineering problem is no longer “can one clip finish coherently?” It is “can the same baseline stay trustworthy across distinct source clips?”

## Success Conditions

The project is moving in the right direction when:

- canonical proof artifacts stay reproducible
- benchmark suites and saved artifacts agree on one truth surface
- remote pod runs finish cleanly with no pod leaks
- the failing source clip stops collapsing product viability
- docs and handoff material match generated artifacts, not wishful interpretation
