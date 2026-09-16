# Touchline Detector Evaluation Workflow

## Purpose

This note captures the bounded Phase 3 evaluation workflow and the current truth for the active detector-candidate lane.

## Canonical References

- `backend/scripts/run_touchline_detector_candidate_evaluation.py`
- `docs/superpowers/plans/2026-04-23-touchline-detector-candidate-evaluation-v5.md`
- `docs/superpowers/plans/2026-04-23-touchline-detector-candidate-promotion-v6.md`
- `docs/superpowers/plans/2026-04-23-promoted-v6-failing-source-robustness-validation.md`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v4/training_quality_gate_v1/quality_gate_summary.json`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v6/evaluation_contract.json`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v6/training_run_summary.json`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v6/training_quality_gate_v1/quality_gate_summary.json`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v6/promotion_v1/promotion_summary.json`
- `backend/storage/training_prep/touchline_validation_gate_remediation_v1/validation_gate_remediation_manifest.json`
- `backend/storage/training_prep/touchline_proposal_signal_generation_fix_v2/proposal_signal_fix_manifest.json`
- `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/suite_summary.json`
- `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/active_lane_snapshot.json`

## Workflow Shape

The evaluation batch should:

1. validate the active trained candidate artifact, weights, and evaluation contract
2. reuse one shared RunPod session for remote screen and capped proof work
3. persist a candidate-local evaluation bundle plus a suite-level evaluation artifact
4. rerun the source-robustness batch so the live truth surfaces ingest the new evaluation diagnosis
5. emit a generated English achieved/not-achieved closeout artifact before any roadmap move

## Current Active Candidate

The active evaluation target is:

- `trainingCandidateName = touchline_detector_candidate_v6`
- `trainingBatchName = touchline_detector_candidate_v5_proposal_signal_generation_fix_v1`
- `weightsReady = true`
- `evaluationContractReady = true`
- `readyForDetectorEvaluation = true`
- training batch goal achieved: `true`
- training roadmap advance allowed: `false`

Completed evaluation-cycle checklist:

- `docs/superpowers/plans/2026-04-23-touchline-detector-candidate-evaluation-v5.md`

Latest promotion-validation checklist:

- `docs/superpowers/plans/2026-04-23-touchline-detector-candidate-promotion-v6.md`

Active post-promotion robustness checklist:

- `docs/superpowers/plans/2026-04-23-promoted-v6-failing-source-robustness-validation.md`

Historical v4 gate blocker:

- `trainingCandidateName = touchline_detector_candidate_v4`
- `validationImageCount = 3`
- `validationPositiveLabelImageCount = 0`
- `validationEmptyLabelImageCount = 3`
- `trainingQualityGatePassed = false`
- `trainingQualityGatePrimaryBlocker = validation_split_has_no_positive_labels`

## Current Validation-Gate Remediation Truth

The corrective batch that produced the active candidate is now complete:

- `validationGateRemediationBatchName = touchline_validation_gate_remediation_v1`
- `blockedCandidateName = touchline_detector_candidate_v4`
- `selectedValidationPositiveCurationUnitId = 8eef9457362a9fea`
- `validationImageCount = 33`
- `validationPositiveLabelImageCount = 27`
- `validationEmptyLabelImageCount = 6`
- `validationInformative = true`
- `sourceAwareSplitLeakageDetected = false`
- `trainingCompleted = true`
- `weightsReady = true`
- `trainingQualityGatePassed = true`
- `readyForDetectorEvaluation = true`
- generated batch goal achieved: `true`
- generated roadmap advance allowed: `false`

Operationally important detail:

- training-only RunPod sessions now skip syncing the full proof clip, so corrective training batches do not waste time shipping `trimed-5min.mp4` before the actual training work starts

## Latest Proposal-Signal Corrective Truth

The latest detector-side corrective batch is now complete:

- `proposalSignalFixBatchName = touchline_proposal_signal_generation_fix_v2`
- `trainingCandidateName = touchline_detector_candidate_v6`
- `windowFamily = proposal_windows_075`
- `proposalPositiveExampleCount = 164`
- `proposalNegativeExampleCount = 220`
- `proposalWindowValidationPositiveImageCount = 44`
- `proposalWindowSanityDetectedImageCount = 31`
- `trainingCompleted = true`
- `weightsReady = true`
- `trainingQualityGatePassed = true`
- `readyForDetectorEvaluation = true`
- generated batch goal achieved: `true`
- generated roadmap advance allowed: `false`

## Latest Completed Evaluation Result

The latest completed bounded evaluation is now the successful v6 run:

- `evaluationBatchName = touchline_detector_candidate_evaluation_v6`
- `trainingCandidateName = touchline_detector_candidate_v6`
- `screenCompleted = true`
- `screenWinningDetectorLabel = yolov10n.pt_baseline_full_detector`
- `candidateBaselineProofRan = true`
- `candidateBaselineProductBeatsPlateau = true`
- `baselineControlProofRan = true`
- `candidateCompoundThinProofRan = true`
- `executionBlockersResolved = true`
- `evaluationReachedProductComparison = true`
- `evaluationPrimaryBlocker = null`
- `readyForPromotion = true`
- `nextRecommendedNextLever = promote_touchline_detector_candidate`
- generated batch goal achieved: `true`
- generated roadmap advance allowed: `true`

Concrete v6 success detail:

- `screen_matrix.json` records a truthful remote screen result where the baseline full detector still wins the raw screen cell
- `proof_report.json` records a truthful v6 candidate baseline proof with `acceptedBallFrames = 10`, `controlledPossessionFrames = 13`, and `ballTrackViable = true`
- the same-batch baseline control proof and the compound-thin proof both ran because v6 beat the plateau in the always-required baseline proof

## Latest Promotion-Validation Result

The latest completed promotion-validation batch is now the successful v6 controlled-promotion run:

- `promotionBatchName = touchline_detector_candidate_promotion_validation_v1`
- `trainingCandidateName = touchline_detector_candidate_v6`
- `promotionValidated = true`
- `promotedForControlledRuns = true`
- `runtimeDefaultChanged = false`
- `runtimeDefaultChangeAllowed = false`
- `runtimeDefaultChangeBlockers = [failing_source_not_viable]`
- `nextRecommendedNextLever = promote_touchline_detector_candidate`

## Latest Promoted-Robustness Validation Result

The latest completed post-promotion robustness-validation batch is now:

- `validationBatchName = promoted_touchline_detector_candidate_robustness_validation_v1`
- `trainingCandidateName = touchline_detector_candidate_v6`
- `winningArmName = promoted_v6_baseline`
- `winningConfigOutcome = source_robustness_weak`
- `winningPassedPromotionGate = false`
- `winningPromotionBlockers = [accepted_retention_below_guardrail, controlled_retention_below_guardrail]`
- `winningFailingSourceEdgeShareImprovement = 0.712`
- `runtimeDefaultChanged = false`
- `nextRecommendedNextLever = promote_touchline_detector_candidate`
- generated batch goal achieved: `false`
- generated roadmap advance allowed: `false`

Operational read:

- the promoted arms still do not clear the failing-source gate
- runtime defaults remain frozen
- the next corrective step is retention delta analysis, not runtime-default validation

## Latest Failure-Analysis Truth

The saved-artifact comparative failure-analysis batch for v5 is now the active corrective truth:

- `failureAnalysisBatchName = touchline_detector_candidate_failure_analysis_v1`
- `trainingCandidateName = touchline_detector_candidate_v5`
- `previousCandidateName = touchline_detector_candidate_v3`
- `rootCauseClass = auxiliary_probe_zero_raw_rows`
- `changeFromPreviousCandidateClass = no_observable_improvement`
- `recommendedFixClass = model_data_quality`
- `recommendedFixFocus = proposal_signal_generation`
- `candidateMaxProposalDetectedFramesAcrossProfiles = 0`
- `previousCandidateMaxProposalDetectedFramesAcrossProfiles = 0`
- `baselineMaxProposalDetectedFramesAcrossProfiles = 21`
- `summarySurfaceDriftDetected = false`
- `calibrationSuspicionDetected = false`
- `nextImplementationBatchRecommendation = touchline_detector_candidate_v5_proposal_signal_generation_fix_v1`
- generated batch goal achieved: `true`
- generated roadmap advance allowed: `false`

## Operational Rules

- keep `beatsPlateau` product-only
- do not promote runtime defaults from evaluation alone
- always stop and delete the pod after the run
- if the batch closeout says the goal was not achieved, the roadmap does not advance
- if evaluation fails, brainstorm fixes from generated truth instead of reopening falsified source-window families by reflex

## Next Honest Move

The bounded evaluation lane already achieved its goal, and the promotion-validation lane is now complete.

The next honest move is:

- work `touchline_detector_candidate_v6_accepted_signal_retention_fix_v1`
- keep the repaired proof-summary contract intact and the frozen runtime baseline unchanged
- preserve the truthful nuance that the broader suite still reads `baseline_not_robust`
- treat the v5 evaluation checklist and the promotion checklist as completed history
