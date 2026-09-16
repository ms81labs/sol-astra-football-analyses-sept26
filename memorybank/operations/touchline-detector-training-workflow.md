# Touchline Detector Training Workflow

## Purpose

This note captures the current training workflow that turns the latest approved export into the active detector candidate.

## Canonical Batch

Entrypoint:

- `backend/scripts/run_touchline_validation_gate_remediation.py`

Canonical current output roots:

- `backend/storage/training_prep/touchline_validation_gate_remediation_v1/`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v5/`

## Inputs

The current batch consumed:

- `backend/storage/training_prep/touchline_model_data_quality_fix_v1/data_quality_fix_manifest.json`
- `backend/storage/training_prep/touchline_model_data_quality_fix_v1/reviewed_label_overlay.json`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v4/results.csv`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v4/training_quality_gate_v1/quality_gate_summary.json`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v4/training_quality_gate_v1/batch_outcome_analysis.json`
- current suite summary and active lane snapshot
- strict checklist file `docs/superpowers/plans/2026-04-23-phase-3-v4-quality-gate-remediation.md`

## Runtime Contract

The real training run is pod-backed:

- prefer the saved RunPod GPU first
- if that exact GPU has no stock, fall back to an available compatible GPU
- sync repo once
- sync dataset export once
- bootstrap the pod runtime
- train one candidate only
- pull back weights before cleanup
- always attempt pod stop and delete

Operationally important improvement:

- training-only RunPod sessions now skip syncing the full proof clip, so training batches do not pay the `trimed-5min.mp4` transfer cost before the actual work starts

## Current Recipe

- base model: `yolov10n.pt`
- image size: `640`
- epochs: `12`
- batch: `8`
- device: GPU `0`
- workers: `4`
- seed: `42`
- augmentation policy: conservative and effectively disabled

## Outputs

The batch writes:

- `validation_gate_remediation_manifest.json`
- `split_manifest.json`
- `batch_outcome_analysis.json`
- `batch_outcome_analysis.md`
- `training_config.json`
- `training_run_summary.json`
- `training_quality_gate_v1/quality_gate_summary.json`
- `training_quality_gate_v1/batch_outcome_analysis.json`
- `evaluation_contract.json`
- `remote_training_result.json`
- `weights/best.pt`
- `weights/last.pt`
- `results.csv`

## Current Result

Current live result:

- blocked historical candidate: `touchline_detector_candidate_v4`
- blocked v4 gate blocker: `validation_split_has_no_positive_labels`
- `validationGateRemediationBatchName = touchline_validation_gate_remediation_v1`
- `trainingCandidateName = touchline_detector_candidate_v5`
- `selectedValidationPositiveCurationUnitId = 8eef9457362a9fea`
- `validationImageCount = 33`
- `validationPositiveLabelImageCount = 27`
- `validationEmptyLabelImageCount = 6`
- `validationInformative = true`
- `sourceAwareSplitLeakageDetected = false`
- `trainingCompleted = true`
- `weightsReady = true`
- `evaluationContractReady = true`
- `readyForDetectorEvaluation = true`
- `trainingQualityGatePassed = true`
- `maxValidationPrecision = 1.0`
- `maxValidationRecall = 0.90323`
- `maxValidationMap50 = 0.77661`
- `requestedGpuId = <redacted; credential-shaped value removed>`
- `allocatedGpuId = NVIDIA GeForce RTX 5090`
- `requestedGpuFallbackTriggered = true`
- generated batch outcome: achieved

## Critical Operational Lessons

- include `backend/train_custom.py` in pod repo sync targets or remote training will fail on import
- pull remote weights before pod cleanup or the training may finish but the artifact will still fail
- a successful training batch means the candidate is evaluation-ready, not product-ready
- training readiness and roadmap advance are different truths: a training batch can legitimately end with `readyForDetectorEvaluation = true` while `roadmapAdvanceAllowed = false`
- a candidate must now clear the training-quality gate before it can be treated as evaluation-ready
- a validation split with zero positive labels is a hard blocker even if weights, provenance, and evaluation contract all exist
- every training batch must end with a generated English achieved/not-achieved artifact before the roadmap moves
