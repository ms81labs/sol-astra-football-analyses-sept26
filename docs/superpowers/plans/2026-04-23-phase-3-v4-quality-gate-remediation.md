# Phase 3 V4 Quality-Gate Remediation

## Blocker
- `touchline_detector_candidate_v4` is blocked by the training-quality gate: `validation_split_has_no_positive_labels`.
- Validation images: `3`
- Validation positive label images: `0`
- Validation empty label images: `3`

## Acceptance Criteria
- [x] Strict checklist exists at `docs/superpowers/plans/2026-04-23-phase-3-v4-quality-gate-remediation.md`.
- [x] Repaired validation split is informative.
- [x] Repaired split is leakage-safe at the curation-unit level.
- [x] New v5 candidate passes the training-quality gate.
- [x] Bounded detector evaluation may remain blocked until the gate passes.

## Ordered Tasks
- [x] Reclassify v4 with a candidate-local training-quality gate artifact.
- [x] Repair the proposal-signal validation split by moving `8eef9457362a9fea` into val beside the control negative unit.
- [x] Retrain one new candidate lineage `touchline_detector_candidate_v5`.
- [x] Require the training-quality gate to pass before treating v5 as evaluation-ready.
- [x] Keep the roadmap pinned to `evaluate_touchline_detector_candidate`.

## Iteration Rule
- If any blocker remains, append the next corrective sub-batch to this file and stay inside Phase 3 until the gate passes.
