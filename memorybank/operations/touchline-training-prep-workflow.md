# Touchline Training Prep Workflow

## Purpose

This note describes the current Phase 1A training-prep workflow that turns the live robustness truth surfaces into a seeded detector-training dataset.

## Canonical Batch

Entrypoint:

- `backend/scripts/run_touchline_training_data_curation_batch.py`

Canonical output root:

- `backend/storage/training_prep/touchline_training_data_curation_foundation/`

## Inputs

The batch reads the live generated steering surfaces:

- `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/active_lane_snapshot.json`
- `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/primary_source_robustness_failure_audit.json`
- `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/primary_source_robustness_slice_projection.json`
- `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/detector_breadth_matrix.json`

It also reads match-level saved artifacts and trust crops from the selected representative matches.

## Scope

Fixed scope for the current foundation batch:

- failing source: `trimed-5min.mp4`
- control source: `trimed-football-2-1minute.mp4`
- max 1 representative match per source
- max 5 trust-crop windows per selected match

## Deterministic Selection

Representative match selection is artifact-derived:

- failing match = baseline slice-projection row for `trimed-5min.mp4` with the worst failing-source signal
- control match = viable baseline slice-projection row for `trimed-football-2-1minute.mp4`

Current resolved representatives:

- failing: `1c8136cda03240aa8324f676c9bbf99a`
- control: `1d67fa87080446a0a777901aace43809`

## Outputs

The batch writes:

- `curation_manifest.json`
- `split_manifest.json`
- `seeded_issue_report.json`
- `yolo_export/dataset.yaml`
- `yolo_export/images/`
- `yolo_export/labels/`

Each curation unit includes:

- stable `curationUnitId`
- source clip and match provenance
- frame and timestamp spans
- truth-gate reasons
- trust-crop score and reasons
- detector/config lineage
- `labelStatus = seeded_review_required`

## Label Seeding Rules

Positive example priority:

1. `acceptedBall.rows`
2. `probeObservedBall.filteredRows`
3. `probeObservedBall.rawRows`

Bounding boxes come from saved source coordinates:

- `Source_X1`
- `Source_Y1`
- `Source_X2`
- `Source_Y2`

Hard negatives:

- frames inside curated windows with no seeded positive
- capped at 3 per curation unit
- written as empty YOLO label files

## Split Policy

- split at curation-unit level, never frame level
- do not allow a curation unit to span multiple splits
- keep source-aware bookkeeping explicit
- if held-out confidence is weak, report it honestly instead of faking confidence

Current held-out assessment:

- `limited_single_control_source`

## Issue Seeding

Seed issues through existing storage-compatible issue records:

- `bucket = tracking_failure`
- `evidenceTarget = trust_eval`
- seeded notes prefixed with `[training-prep:touchline_training_data_curation_foundation]`

Reruns replace prior seeded items for the same batch instead of duplicating them.

## Current Result

The current foundation batch resolved to:

- `curationUnitCount = 2`
- `seededIssueCount = 2`
- `positiveSeedExampleCount = 37`
- `negativeSeedExampleCount = 6`
- `sourceAwareSplitLeakageDetected = false`
- `yoloExportReady = true`
- `readyForDetectorTraining = true`

## Definition Of Done

Phase 1A is done when:

- the manifests exist
- the issue backlog is seeded idempotently
- the YOLO export is loadable by `backend/train_custom.py`
- `trainingPrepDiagnosis` is ingested into the live suite surfaces
- the memory bank matches the generated truth
