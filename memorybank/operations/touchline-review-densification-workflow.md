# Touchline Review Densification Workflow

## Purpose

This note records the completed Phase 1B workflow that turned the seeded export into the review-gated dataset used for `touchline_detector_candidate_v2`.

## Canonical Batch

Entrypoint:

- `backend/scripts/run_touchline_review_densification_batch.py`

Canonical output root:

- `backend/storage/training_prep/touchline_review_densification_v1/`

## What Phase 1B Delivered

- persistent `reviewed_label_overlay.json`
- densified failing-source window set
- regenerated `yolo_export/`
- idempotent review bundles and issues
- generated English closeout artifacts
- an explicit roadmap gate for retraining

## Live Completed Result

- failing source: `trimed-5min.mp4`
- failing match: `1c8136cda03240aa8324f676c9bbf99a`
- control match: `1d67fa87080446a0a777901aace43809`
- failing units: `2`
- control units: `1`
- `reviewItemCount = 73`
- `pendingFailingReviewCount = 0`
- `pendingControlReviewCount = 13`
- `readyForRetraining = true`
- batch goal achieved: `true`
- roadmap advance allowed: `true`

## Current Meaning

Phase 1B is no longer the active lane.

Its job was to unblock retraining, and it succeeded. The remaining control-side pending items are follow-up quality work, not the current roadmap gate.

## Ongoing Rule

The closeout rule introduced here is still active for every later batch:

- every batch must end with a generated English achieved/not-achieved artifact
- failed batches do not advance the roadmap
- failed batches must include concrete brainstormed fixes
