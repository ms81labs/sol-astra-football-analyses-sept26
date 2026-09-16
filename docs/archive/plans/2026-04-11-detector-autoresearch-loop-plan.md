# Detector Autoresearch Loop Plan

> **For agentic workers:** Parked future lane. Do not implement until the current GPU/app integration work is stable. When activated, use superpowers:subagent-driven-development or superpowers:executing-plans and follow the task-by-task plan that should be derived from this design.

**Goal:** Adopt the useful parts of Karpathy's `autoresearch` loop to improve football detector quality through bounded, measured experiments.

**Architecture:** Treat `autoresearch` as an operating pattern, not code to vendor. Freeze our football benchmark, restrict experiments to a narrow detector/profile surface, run short local or Runpod trials, log each trial, and keep only measured improvements.

**Tech Stack:** Existing Python backend, YOLO/Ultralytics, benchmark helpers, Runpod L4 serverless, TSV/JSON experiment ledgers.

---

## Summary

Use Karpathy's `autoresearch` as an experiment-loop pattern, not as code to import: freeze our football benchmark, allow agents to change one bounded experiment surface, run short local/Runpod GPU trials, log results, and keep only measured improvements.

The first target is ball detection/recovery quality, because our current Runpod proof works but only returns `20` ball rows on the 1-minute clip. Success means improving viable in-field ball coverage without regressing edge-noise gates.

## Key Changes

- Create an internal research loop around `backend/run_guerilla.py`, but keep production behavior protected behind tests.
- Add an agent instruction file, probably `docs/superpowers/specs/2026-04-11-detector-autoresearch-program.md`, that says agents may only edit the experiment profile surface and must not change app APIs, storage contracts, truth gates, or Runpod secrets.
- Add a result ledger, probably `backend/research/detector_results.tsv`, with columns: `commit`, `profile_name`, `match_id`, `with_ball_frames`, `edge_frame_share`, `ball_track_viable`, `event_count`, `status`, `description`.
- Add a repeatable command, probably `backend/scripts/run_detector_autoresearch_trial.py`, that runs the trimmed benchmark and emits one compact JSON/TSV-ready result.
- Keep public API unchanged: `POST /api/matches`, job polling, artifact layout, and frontend behavior stay exactly as they are.

## Experiment Rules

- Baseline is the current proven state: `edge_margin_40_upper_078`, `20` app-path ball rows, `ballTrackViable: true`, Runpod full-pipeline proof returned `2265` rows with `20` ball rows.
- A trial is `keep` only if it improves viable ball coverage or event richness while keeping `ballTrackViable: true` and `edgeFrameShare <= 0.60`.
- A trial is `discard` if it increases raw ball frames by hugging pitch edges, breaks benchmark tests, changes public contracts, or requires manual hidden interpretation.
- Runpod use stays small: L4, `workersMin=0`, `workersMax=1`, delete endpoint after proof.

## Test Plan

- Add unit tests for the result parser and keep/discard classification.
- Add a script-level test that feeds a synthetic benchmark JSON and verifies the TSV row output.
- Keep running existing focused checks: `python3 -m pytest backend/tests/test_run_guerilla.py backend/tests/test_run_benchmarks.py backend/tests/test_runpod.py backend/tests/test_runpod_worker.py backend/tests/test_runpod_handler.py -q`.
- Run Ruff on touched Python files.
- For real proof, run the 1-minute trimmed clip locally first, then Runpod only after local trial passes.

## Assumptions

- We are not fine-tuning YOLO weights yet; that becomes the next lane once we have labeled review crops.
- We are borrowing `autoresearch`'s discipline: fixed metric, narrow edit surface, results ledger, autonomous keep/discard loop.
- We are not cloning or vendoring `karpathy/autoresearch` into this repo unless a later plan specifically needs it.

## Active-Learning Seed Path

The current app lane can save uncertain trust-crop windows as `trust_eval` match issues. Those saved records carry match ID, frame range, timestamps, reason labels, and score in the note. When this future detector lane is activated, treat those issues as the first review queue for labeling/export, not as finished training labels.

Do not start fine-tuning from these records until a later plan defines the label schema, export format, reviewer workflow, and acceptance gates.

## Parked Future Improvements Triage

These came from `Guerilla Analytics_ Future Improvements.md` and belong near this autoresearch lane, not in the current GPU/app integration sprint.

**Likely v2 after the 5-10 minute proof is stable:**

- TrackNetV2 or another specialized ball detector, evaluated through the detector autoresearch loop.
- YOLOv11 / ONNX / TensorRT exploration, after we know whether quality or speed is the main bottleneck.
- Auto homography / pitch keypoint calibration, after the manual-calibrated Runpod path is stable.
- Player Re-ID and jersey OCR, after tracking quality and review data are strong enough to justify identity work.
- xT, VAEP, and pitch-control style models, after ball, possession, team, and event data become reliable.

**Longer-horizon product/platform work:**

- Dual-camera stitching and panoramic capture workflows.
- Vector-database semantic search over match sequences.
- AR overlays on the original video using inverse homography.
- Three.js or 3D tactical rendering.
- League/roster integrations for Luxembourg/club operations.
- GDPR/RBAC/retention policy hardening before real club/youth deployment.

**Do not chase until the core proof is trustworthy:**

- 3D Gaussian splatting / volumetric replay.
- Full broadcast-style automated highlight production.
- Broad “commercial platform parity” work that is not tied to a measured benchmark improvement.
