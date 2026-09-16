# Source Robustness Lane

## Latest V7.2 Promotion Readiness Truth

- latest external dataset access review result: `goalAchieved = true`, `primaryBlocker = null`, `safeSourceAdapterSmokeReady = true`, `safeSmokeResourceCount = 3`, `safeSmokeResourceIds = [soccertrack_v2, skillcorner_open_data, statsbomb_open_data_360]`, `manualOrGatedResourceIds = [soccernet_broadcast_tasks, metrica_sample_data]`, `fullExternalBenchmarkExecutionReady = false`, `datasetDownloadExecuted = false`, `trainingExecuted = false`, `runtimeDefaultMutationAllowed = false`, `nextRecommendedNextLever = football_external_safe_source_adapter_smoke_test`
- latest runtime-default rollout closeout result: `goalAchieved = true`, `primaryBlocker = null`, `runtimeDefaultRolloutClosed = true`, `runtimeDefaultMutationExecuted = true`, `runtimeDefaultProfileName = source_robustness_shadow_v7_2_default_path_inboard_recovery_v1`, `postRuntimeDefaultSourceRobustnessValidated = true`, `activeFailingSourceNotViableBlockerPresent = false`, `historicalSuiteBlockerArchived = true`, `legacySuiteBlockerStillPresent = true`, `sourceRobustnessOutcome = source_robustness_viable_by_validated_inboard_recovery`, `trainingExecuted = false`, `promotionMutationExecuted = false`, `nextRecommendedNextLever = football_external_dataset_access_review`
- latest post-runtime-default source-robustness validation result: `goalAchieved = true`, `primaryBlocker = null`, `postRuntimeDefaultSourceRobustnessValidated = true`, `runtimeDefaultMutationExecuted = true`, `runtimeDefaultProfileName = source_robustness_shadow_v7_2_default_path_inboard_recovery_v1`, `failingSourceNotViableBlockerPresent = false`, `legacySuiteBlockerStillPresent = true`, `sourceRobustnessOutcome = source_robustness_viable_by_validated_inboard_recovery`, `trainingExecuted = false`, `promotionMutationExecuted = false`, `nextRecommendedNextLever = v7_2_runtime_default_rollout_closeout`
- latest runtime-default change validation result: `goalAchieved = true`, `primaryBlocker = null`, `runtimeDefaultChanged = true`, `runtimeDefaultMutationExecuted = true`, `runtimeDefaultProfileName = source_robustness_shadow_v7_2_default_path_inboard_recovery_v1`, `sourceRobustnessDefaultChangeGatePassed = true`, `sourceRobustnessOutcome = source_robustness_viable_by_validated_inboard_recovery`, `trainingExecuted = false`, `promotionMutationExecuted = false`, `nextRecommendedNextLever = v7_2_post_runtime_default_source_robustness_validation`
- latest default-path inboard recovery result: `goalAchieved = true`, `primaryBlocker = null`, `safeInboardCandidateFrameCount = 133`, `sliceCount = 9`, `allSliceNearViableDeficitsCovered = true`, `allSliceProjectedNearViableEdgeShareClearsGate = true`, `allSliceViableDeficitsCovered = true`, `allSliceProjectedViableEdgeShareClearsGate = true`, `inboardRecoveryProfileReady = true`, `sourceRobustnessGeneratedTruthCleared = true`, `runtimeDefaultMutationReady = true`, `runtimeDefaultMutationAllowed = true`, `runtimeDefaultMutationExecuted = false`, `trainingExecuted = false`, `promotionMutationExecuted = false`, `nextRecommendedNextLever = v7_2_runtime_default_change_validation`
- latest default-path edge-share reduction result: `goalAchieved = true`, `primaryBlocker = v7_2_default_path_inboard_ball_recovery_required`, `edgeOnlyReductionCanClearNearViableGate = false`, `edgeOnlyReductionCanClearViableGate = false`, `sliceCount = 9`, `slicesNeedingInboardRecoveryForNearViable = 8`, `minimumAdditionalInboardFramesNeededForNearViable = 5`, `minimumAdditionalInboardFramesNeededForViable = 8`, `trainingExecuted = false`, `runtimeDefaultMutationExecuted = false`, `nextRecommendedNextLever = v7_2_default_path_inboard_ball_recovery`
- latest v7/v7.1/v7.2 data-lane batch: `v7_2_training_manifest_prep`
- latest v7.2 prep result: `trainingPrepReady = true`, `reviewedPositiveSourceCount = 139`, `positiveCropExampleCount = 414`, `localHardNegativeCropCount = 180`, `heldoutHardNegativeCanaryCount = 20`, `unsafeFullFrameNegativeExportCount = 0`, `splitLeakageCount = 0`
- latest v7.2 export/overlay audit result: `exportOverlayAuditPassed = true`, `positiveLabelFilesWithExactlyOneBall = 414`, `negativeLabelFilesEmpty = 180`, `heldoutCanaryLabelFilesEmpty = 20`, `positiveCropBoundsRepairedCount = 12`, `positiveLabelRoundTripMaxErrorPx = 0.500392`, `splitLeakageCount = 0`, `canaryLeakageCount = 0`
- latest v7.2 bounded retrain result: `goalAchieved = true`, `trainingCompleted = true`, `checkpointContractPassed = true`, `trainerObservedLabelRowCount = 414`, `selectedCheckpointForVerdict = best.pt`, `selectedAuditConf = 0.1`
- latest bounded retrain metrics: `boundedTrainPositiveLocalizationHitRate = 0.985507`, `boundedValPositiveLocalizationHitRate = 0.971014`, `boundedTrainNegativeFalsePositiveFrameRate = 0.0`, `boundedValNegativeFalsePositiveFrameRate = 0.0`, `heldoutCanaryFalsePositiveFrameRate = 0.0`, `medianTrainPositiveConfidence = 0.83083`, `medianValPositiveConfidence = 0.810916`, `topLeftArtifactShare = 0.0`, `giantBoxShare = 0.0`
- latest v7.2 crop-probe precision guardrail result: `goalAchieved = true`, `trainingExecuted = false`, `checkpointContractPassed = true`, `selectedCheckpointForAudit = best.pt`, `selectedAuditConf = 0.1`, `boundedTrainPositiveLocalizationHitRate = 0.985507`, `boundedValPositiveLocalizationHitRate = 0.971014`, `boundedTrainHardNegativeFalsePositiveFrameRate = 0.0`, `boundedValHardNegativeFalsePositiveFrameRate = 0.0`, `heldoutCanaryFalsePositiveFrameRate = 0.0`, `oldTopLeftArtifactFalsePositiveFrameRate = 0.0`, `recallGuardrailStrength = strong_pass`
- latest v7.2 full-pipeline non-promotion result: `goalAchieved = true`, `trainingExecuted = false`, `checkpointContractPassed = true`, `positiveReviewedFrameCount = 138`, `positiveCropRowCount = 414`, `positiveCropBoundsRepairedCount = 12`, `candidateCropCoverageRate = 1.0`, `cropDetectorConditionalLocalizationRate = 1.0`, `sourceFrameLocalizationHitRate = 1.0`, `observedBallAcceptanceRate = 1.0`, `projectionAuditPassed = true`, `projectionErrorCount = 0`, `heldoutCanaryFalsePositiveFrameRate = 0.0`, `oldTopLeftArtifactFalsePositiveFrameRate = 0.0`, `sampledFrameDetectionRate = 0.0`, `topLeftArtifactShare = 0.0`, `giantBoxShare = 0.0`
- latest external benchmark harness prep result: `goalAchieved = true`, `resourceCount = 5`, `adapterSchemaCount = 6`, `stageGateCount = 6`, `stageCoverageComplete = true`, `benchmarkHarnessContractReady = true`, `datasetAccessReviewReady = true`, `externalBenchmarkExecutionReady = false`, `datasetDownloadExecuted = false`, `attemptPlanFamilies = [external_benchmark_contract_prep, benchmark_adapter_contract_repair, benchmark_harness_blocker_summary]`
- latest v7.2 promotion-readiness result: `promotionValidated = true`, `promotionReady = true`, `candidateReadyForEvaluation = true`, `promotedForControlledRuns = true`, `controlledRuntimeRegistryUpdated = true`, `runtimeDefaultMutationEvaluated = true`, `runtimeDefaultMutationAllowed = false`, `runtimeDefaultMutationExecuted = false`, `runtimeDefaultMutationBlockers = [failing_source_not_viable]`
- latest promoted-v7.2 source-robustness validation result: `validationCompleted = true`, `goalAchieved = false`, `primaryBlocker = v7_2_source_robustness_default_mutation_blocked`, `controlledPromotionValid = true`, `runtimeDefaultMutationReady = false`, `runtimeDefaultMutationExecuted = false`, `runtimeDefaultMutationBlockers = [failing_source_not_viable]`, `sourceRobustnessOutcome = source_robustness_partial`, `sourceRobustnessDominantFailureSignal = high_ball_track_edge_frame_share`, `sourceRobustnessRouteMismatchDetected = false`
- latest v7.2 source-robustness default-blocker analysis result: `goalAchieved = false`, `roadmapAdvanceAllowed = true`, `primaryBlocker = v7_2_default_path_performance_blocker`, `controlledPromotionValid = true`, `realDefaultPerformanceFailureProven = true`, `sourceRobustnessRouteMismatchDetected = false`, `sourceRobustnessRecommendedNextLever = promoted_v7_2_source_robustness_validation`, `runtimeDefaultMutationReady = false`, `runtimeDefaultMutationExecuted = false`, `runtimeDefaultMutationBlockers = [failing_source_not_viable]`
- latest v7.2 source-robustness route-contract fix result: `goalAchieved = true`, `primaryBlocker = null`, `routeContractFixed = true`, `defaultBlockerAfterRouteFix = v7_2_default_path_performance_blocker`, `realDefaultPerformanceFailureProven = true`, `nextRecommendedNextLever = v7_2_default_path_edge_share_reduction`
- next corrective family: `football_external_safe_source_adapter_smoke_test`
- runtime defaults changed: `true`
- training executed in latest diagnostic batch: `false`
- promotion ready: `true`

## Purpose

This note tracks the live multi-source robustness lane at a higher level than raw artifacts while staying anchored to generated truth.

## Canonical References

- `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/suite_summary.json`
- `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/active_lane_snapshot.json`
- `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/suite_robustness_diagnosis.json`
- `docs/superpowers/plans/2026-04-23-promoted-v6-failing-source-robustness-validation.md`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v4/training_quality_gate_v1/quality_gate_summary.json`
- `backend/storage/training_prep/touchline_validation_gate_remediation_v1/batch_outcome_analysis.json`
- `backend/storage/training_prep/touchline_proposal_signal_generation_fix_v2/batch_outcome_analysis.json`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v6/training_run_summary.json`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v6/promotion_v1/promotion_summary.json`
- `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/promoted_touchline_detector_candidate_robustness_validation_v1/validation_summary.json`
- `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/promoted_touchline_detector_candidate_robustness_validation_v1/batch_outcome_analysis.json`

## Current Robustness Read

- suite verdict: `baseline_not_robust`
- active config: `source_robustness_baseline_current`
- best qualifying config: `source_robustness_shadow_edge_run_keep_every_2_min10`
- best exploratory config: `source_robustness_shadow_edge_run_keep_every_3_min10`
- outcome: `source_robustness_partial`
- active-lane next lever: `football_external_safe_source_adapter_smoke_test`
- runtime-default rollout is closed; the old suite-summary blocker is historical pre-mutation context only
- latest promoted controlled-run candidate: `touchline_detector_candidate_v7` / `v7.2`
- runtime defaults changed: `true`
- latest promoted-robustness validation goal achieved: `false`
- latest default-blocker analysis primary blocker: `v7_2_default_path_performance_blocker`
- latest default-blocker analysis real default performance failure proven: `true`
- latest route-contract fix status: `routeContractFixed = true`
- latest default-path edge-share reduction status: `edge-only reduction infeasible; inboard ball recovery required`
- latest default-path inboard recovery status: `safe inboard recovery profile clears near-viable and viable edge-share gates`
- latest runtime-default validation status: `validated inboard recovery profile was written to the runtime default registry`
- latest post-default validation status: `active runtime registry preserves source robustness and failing_source_not_viable remains cleared`
- latest rollout closeout status: `runtime default rollout closed; external dataset access review is next`
- latest external dataset access status: `safe-source adapter smoke is ready; SoccerNet and Metrica remain manual/gated`
- latest accepted-signal fix attempt: `acceptance_support_gating`
- latest accepted-signal fix result: `failed`
- latest truth-refresh batch: `promoted_v6_source_manifest_and_gold_truth_refresh_v1`
- latest truth-refresh attempt: `gold_truth_bootstrap`
- latest truth-refresh result: `succeeded`
- latest proposal-selection follow-through batch: `proposal_selection_followthrough_fix`
- latest proposal-selection follow-through result: `exhausted`
- latest proposal-selection follow-through blocker summary: `candidate_rows_collapsed_but_segment_selection_zero`, `selectedFrames = 0`
- latest manual review package batch: `promoted_v6_manual_review_followthrough_v1`
- latest manual review package result: `manual_review_pending`, `reviewItemCount = 78`, `pendingReviewCount = 78`
- latest manual review resolution batch: `promoted_v6_manual_review_resolution_v1`
- latest manual review resolution result: `review_resolved`, `pendingReviewCount = 0`, `invalidDecisionCount = 0`, `acceptedSeedCount = 4`, `rejectedSeedCount = 74`
- latest manual review UI unblock batch: `promoted_v6_manual_review_ui_unblock_v1`
- latest manual review UI unblock result: local UI implemented; AI-assisted visual review resolved the overlay with provenance
- latest reviewed follow-through selection batch: `reviewed_followthrough_selection_fix_v1`
- latest reviewed follow-through selection result: `reviewed_positive_evidence_too_sparse`, `reviewedPositiveSeedCount = 4`, `reviewedNegativeSeedCount = 74`
- latest gold-truth refuted refresh batch: `gold_truth_seed_refuted_refresh_v1`
- latest gold-truth refuted refresh result: `reviewed_positive_truth_too_sparse`, `reviewedPositiveSeedCount = 4`, `rejectedSeedCount = 74`, `reviewedPositiveFrames = [260, 290, 295, 300]`
- latest manual review expansion batch: `manual_review_expansion_v1`
- latest manual review expansion result: `manual_review_pending`, `reviewItemCount = 17`, `acceptedSeedCount = 4`, `pendingReviewCount = 13`, `imageExtractionStatus = images_extracted`
- latest manual review expansion resolution batch: `manual_review_expansion_resolution_v1`
- latest manual review expansion resolution result: `review_resolved`, `reviewedPositiveCount = 17`, `pendingReviewCount = 0`, `lineageCompleteCount = 4`, `nextCorrectiveFamily = reviewed_positive_micro_validation`
- latest reviewed-positive micro-validation batch: `reviewed_positive_micro_validation_v1`
- latest reviewed-positive micro-validation result: `reviewed_positive_artifact_coverage_gap`, `reviewedPositiveFrameCount = 17`, `perFrameProofCoverageAvailable = false`, `weakEvidenceReasons = [reviewed_positive_frame_level_proposal_selection_fields_partial]`, `nextCorrectiveFamily = proof_diagnostic_instrumentation_refresh`
- latest proof diagnostic instrumentation batch: `proof_diagnostic_instrumentation_refresh_v1`
- latest proof diagnostic instrumentation result: `reviewed_positive_frame_diagnostics_missing`, `reviewedPositiveFrameCount = 17`, `coveredReviewedFrameCount = 0`, `currentProofCanSelectDetectorFamily = false`, `nextCorrectiveFamily = proof_runtime_frame_diagnostics`
- latest proof runtime frame diagnostics batch: `proof_runtime_frame_diagnostics_v1`
- latest proof runtime frame diagnostics result: `reviewed_positive_no_promoted_proposal`, `reviewedPositiveFrameCount = 17`, `classifiedReviewedFrameCount = 17`, `freshProofRoot = backend/storage/matches/094a9974d01b447b93ec7ba43981f6c8`, `nextCorrectiveFamily = reviewed_positive_proposal_generation_fix`
- latest reviewed-positive proposal generation batch: `reviewed_positive_proposal_generation_fix_v1`
- latest reviewed-positive proposal generation result: `reviewed_positive_anchor_window_zero_detect`, `reviewedPositiveAnchorFrameCount = 17`, `reviewedPositiveProposalEvidenceFrameCount = 1`, `reviewedPositiveSelectedFrameCount = 0`, `nextCorrectiveFamily = reviewed_positive_crop_reinference_audit`
- latest reviewed-positive crop reinference audit batch: `reviewed_positive_crop_reinference_audit_v1`
- latest reviewed-positive crop reinference audit result: `reviewed_positive_crop_geometry_scale_rescue_available`, `reviewedPositiveFrameCount = 17`, `zeroDetectFrameCount = 16`, `reinferenceDetectedFrameCount = 11`, `nextCorrectiveFamily = reviewed_positive_crop_geometry_scale_fix`
- latest v7 training-prep batch: `touchline_detector_candidate_v7_training_prep_v1`
- latest v7 training-prep result: `training_prep_ready`, `positiveExampleCount = 30`, `negativeExampleCount = 78`, `remainingPendingReviewCount = 0`, `positiveBBoxMissingCount = 0`, `refutedPositiveOverlapCount = 6`, `weakEvidenceReasons = []`, `nextCorrectiveFamily = touchline_detector_candidate_v7_training`
- latest v7 training batch: `touchline_detector_candidate_v7_training`
- latest v7 training result: `trainingCompleted = true`, `weightsReady = true`, `trainingQualityGatePassed = true`, `readyForDetectorEvaluation = true`, `nextRecommendedNextLever = touchline_detector_candidate_v7_evaluation`
- latest v7 evaluation batch: `touchline_detector_candidate_evaluation_v7`
- latest v7 evaluation result: `screenCompleted = true`, `screenWinningDetectorLabel = yolov10n.pt_baseline_full_detector`, `candidateBaselineProductBeatsPlateau = false`, `acceptedBallFrames = 0`, `controlledPossessionFrames = 0`, `evaluationPrimaryBlocker = candidate_baseline_did_not_beat_plateau`, `readyForPromotion = false`
- latest v7 evaluation failure analysis batch: `touchline_detector_candidate_v7_evaluation_failure_analysis`
- latest v7 evaluation failure analysis result: `dominantBlockerClass = v7_auxiliary_probe_zero_raw_signal`, `candidateScreenViable = false`, `candidateRawProbeObservedBallFrames = 0`, `candidateBestProposalRawDetectedFrames = 0`, `candidateAcceptedBallFrames = 0`, `nextCorrectiveFamily = v7_probe_assist_integration_audit`
- latest v7 probe-assist integration audit batch: `v7_probe_assist_integration_audit`
- latest v7 probe-assist integration audit result: `dominantBlockerClass = v7_preprocessing_or_threshold_mismatch`, `bestWeightsPathExists = true`, `probePassAppearsInvoked = true`, `probeObservedPassSeconds = 34.779`, `rawProbeObservedBallFrames = 0`, `nextCorrectiveFamily = v7_probe_threshold_preprocessing_fix`
- latest v7 threshold/preprocessing batch: `v7_probe_threshold_preprocessing_fix`
- latest v7 threshold/preprocessing result: `dominantBlockerClass = v7_offline_detections_available`, `positiveImageCount = 30`, `offlineDetectedImageCount = 30`, `wrongClassDetectionCount = 0`, detections appear at confidence `0.001`/`0.01`, `nextCorrectiveFamily = v7_probe_threshold_contract_fix`
- latest retention blocker summary: `accepted_signal_retention_collapse`, `acceptedRetentionRatio = 0.099`
- next corrective family: `v7_probe_threshold_contract_fix`

## Stable Signals

- the failing source is still `trimed-5min.mp4`
- the comparison source remains viable
- plateau detection is still true
- high edge-share and non-viable tracking remain the dominant blockers on the failing source

## Closed Lanes

These remain falsified unless genuinely new evidence appears:

- support-aware thinning as the primary fix
- touchline probe replacement
- touchline acquisition upgrade and reopen variants
- combined detector and candidate-source reopen
- touchline candidate-admission reopen v3
- bounded off-the-shelf detector breadth

## Data And Training Follow-Through

Phase 1A and Phase 1B still anchor the data path:

- failing representative match: `1c8136cda03240aa8324f676c9bbf99a`
- control representative match: `1d67fa87080446a0a777901aace43809`
- failing review gate complete
- `pendingFailingReviewCount = 0`
- `pendingControlReviewCount = 13`
- `readyForRetraining = true`

Historical blocked v4 gate truth:

- `trainingCandidateName = touchline_detector_candidate_v4`
- `validationImageCount = 3`
- `validationPositiveLabelImageCount = 0`
- `validationEmptyLabelImageCount = 3`
- `trainingQualityGatePassed = false`
- `trainingQualityGatePrimaryBlocker = validation_split_has_no_positive_labels`

Latest corrective training is now complete:

- `trainingCandidateName = touchline_detector_candidate_v6`
- `trainingBatchName = touchline_detector_candidate_v5_proposal_signal_generation_fix_v1`
- `trainingCompleted = true`
- `weightsReady = true`
- `evaluationContractReady = true`
- `readyForDetectorEvaluation = true`
- training batch goal achieved: `true`

Latest validation-gate remediation truth:

- `validationGateRemediationBatchName = touchline_validation_gate_remediation_v1`
- `blockedCandidateName = touchline_detector_candidate_v4`
- `selectedValidationPositiveCurationUnitId = 8eef9457362a9fea`
- `validationImageCount = 33`
- `validationPositiveLabelImageCount = 27`
- `validationEmptyLabelImageCount = 6`
- `validationInformative = true`
- `sourceAwareSplitLeakageDetected = false`
- `trainingQualityGatePassed = true`
- batch goal achieved: `true`
- roadmap advance allowed: `false`

Latest training-quality gate truth:

- `trainingCandidateName = touchline_detector_candidate_v6`
- `validationImageCount = 89`
- `validationPositiveLabelImageCount = 44`
- `validationEmptyLabelImageCount = 45`
- `validationInformative = true`
- `maxValidationPrecision = 0.9867`
- `maxValidationRecall = 0.61364`
- `maxValidationMap50 = 0.5973`
- `localPositiveSanityDetectedImageCount = 150`
- `proposalWindowSanityDetectedImageCount = 31`
- `trainingQualityGatePassed = true`

Latest proposal-signal fix truth:

- `proposalSignalFixBatchName = touchline_proposal_signal_generation_fix_v2`
- `windowFamily = proposal_windows_075`
- `proposalPositiveExampleCount = 164`
- `proposalNegativeExampleCount = 220`
- `proposalWindowValidationPositiveImageCount = 44`
- `proposalWindowSanityDetectedImageCount = 31`
- batch goal achieved: `true`
- roadmap advance allowed: `false`

## Latest Completed Evaluation Truth

The latest completed bounded evaluation is now the successful `touchline_detector_candidate_v6` run:

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

The important product read is simple:

- the bounded v6 batch achieved its goal under the standing failing-source reference `101 / 98 / false / 0.812`
- the v6 baseline proof beat the product plateau even though the baseline still won the raw screen cell
- the same-batch baseline control and compound-thin proof both ran because v6 earned them

## Latest Promotion-Validation Truth

The latest completed promotion-validation batch is now:

- `promotionBatchName = touchline_detector_candidate_promotion_validation_v1`
- `trainingCandidateName = touchline_detector_candidate_v6`
- `promotionValidated = true`
- `promotedForControlledRuns = true`
- `runtimeDefaultChanged = false`
- `runtimeDefaultChangeAllowed = false`
- `runtimeDefaultChangeBlockers = [failing_source_not_viable]`
- `nextRecommendedNextLever = promote_touchline_detector_candidate`

The important product read is:

- v6 is promoted for controlled/internal runs
- runtime defaults remain frozen
- the broader suite still truthfully reads `baseline_not_robust`

## Latest Promoted-Robustness Validation Truth

The latest completed post-promotion robustness-validation batch is now:

- `validationBatchName = promoted_touchline_detector_candidate_robustness_validation_v1`
- `trainingCandidateName = touchline_detector_candidate_v6`
- `winningArmName = promoted_v6_baseline`
- `winningConfigOutcome = source_robustness_weak`
- `winningPassedPromotionGate = false`
- `winningPromotionBlockers = [accepted_retention_below_guardrail, controlled_retention_below_guardrail]`
- `winningFailingSourceEdgeShareImprovement = 0.812`
- `runtimeDefaultChanged = false`
- `goalAchieved = false`
- `roadmapAdvanceAllowed = false`
- `nextRecommendedNextLever = promote_touchline_detector_candidate`

Important read:

- the promoted arms materially improved failing-source edge share
- that was not enough to clear the gate because accepted and controlled retention still collapsed relative to baseline
- runtime-default validation is not the next move

## Latest Accepted-Signal Fix Attempt

Generated truth after attempt 4:

- `activeBatchName = touchline_detector_candidate_v6_accepted_signal_retention_fix_v1`
- `approachFamily = acceptance_support_gating`
- `primaryRetentionBlockerClass = accepted_signal_retention_collapse`
- `acceptedRetentionRatio = 0.069`
- `controlledRetentionRatio = 0.102`
- `selectedClusterStepImplicated = false`
- `runtimeDefaultChanged = false`
- `runpodCleanup = {podStopSucceeded: true, podDeleteSucceeded: true, cleanupErrors: []}`
- `itemStatus = exhausted`
- `nextQueueItem = promoted_v6_failing_source_review_refresh_v1`

Generated review-refresh truth:

- `activeBatchName = promoted_v6_failing_source_review_refresh_v1`
- `attemptNumber = 1`
- `approachFamily = review_taxonomy_refresh`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `dominantBlockerClass = proposal_signal_present_but_not_selected`
- `nextFixFamily = proposal_selection_evidence_refresh`
- `missingAcceptedFrameCount = 101`
- `windowCount = 11`
- `nextQueueItem = promoted_v6_source_manifest_and_gold_truth_refresh_v1`

Generated source-manifest refresh truth:

- `activeBatchName = promoted_v6_source_manifest_and_gold_truth_refresh_v1`
- `attemptNumber = 2`
- `approachFamily = gold_truth_bootstrap`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `proposalSelectionWindowCount = 11`
- `proposalSelectionMissingAcceptedFrameCount = 101`
- `selectedBootstrapWindowCount = 5`
- `selectedBootstrapMissingAcceptedFrameCount = 78`
- `successfulApproach = A_direct_saved_artifact_seed`
- `representedBootstrapWindowCount = 5`
- `representedMissingAcceptedFrameCount = 78`
- `acceptedSeedRowCount = 78`
- `controlledSeedCandidateRowCount = 78`
- `sourceManifestMutationPolicy = not_mutated_delta_only`
- `nextCorrectiveFamily = proposal_selection_admission_fix`

Generated support/viability truth-fix truth:

- `activeBatchName = support_viability_truth_fix`
- `attemptNumber = 1`
- `approachFamily = support_viability_truth_analysis`
- `goalAchieved = true`
- `dominantBlockerClass = support_viability_evidence_gap`
- `nextCorrectiveFamily = support_viability_admission_fix`
- `classifiedSeedFrameCount = 78`
- `representedBootstrapWindowCount = 5`
- `proofRuntimeSeedPathAudit = passed`
- `primaryRetentionBlockerClass = accepted_signal_retention_collapse`
- `acceptedRetentionRatio = 0.069`
- `controlledRetentionRatio = 0.102`

Important read:

- acceptance-support gating did not recover the missing accepted signal
- the accepted-signal retention fix batch exhausted all 4 attempts
- review-refresh attempt 1 produced a strong blocker taxonomy
- source-manifest refresh attempt 1 converted that taxonomy into additive manifest and gold-truth bootstrap artifacts
- gold-truth bootstrap attempt 2 produced a stronger seed truth surface and selected `proposal_selection_admission_fix`
- proposal-selection admission fix exhausted all 3 approaches without moving retention truth
- support/viability truth fix showed the intended seed path was consumed and selected `support_viability_admission_fix`
- support/viability admission fix attempts 1, 2, and 3 (`support_evidence_lift`, `source_space_support_neighborhood`, `viability_neutral_seed_window`) completed and failed from regenerated truth; accepted retention remains `0.069`
- support/viability admission fix is exhausted and selects `candidate_proposal_generation_fix`
- candidate proposal generation fix attempt 1 succeeded from saved artifacts: `no_proposal_attempt_for_seed_frame = 46`, `probe_model_no_raw_detection = 32`, and next corrective family `proposal_crop_geometry_fix`
- proposal crop geometry fix attempts 1, 2, and 3 completed and failed from regenerated retention truth; they improved upstream proposal generation to `proposalRawDetectedFrames = 93` and `proposalCollapsedFrames = 93`, but `selectedFrames = 0`, so the next corrective family is `proposal_selection_followthrough_fix`
- reviewed-positive crop geometry scale fix attempt 2 succeeded as proof-level proposal/collapse lift: `reviewedPositiveProposalEvidenceFrameCount = 5`, `reviewedPositiveCollapsedFrameCount = 5`, `reviewedPositiveSelectedFrameCount = 0`, `reviewedPositiveAcceptedFrameCount = 0`, and next corrective family `reviewed_positive_selection_followthrough_fix`
- reviewed-positive selection follow-through fix attempt 1 succeeded as saved-artifact diagnosis: all 5 collapsed reviewed-positive frames are `reviewed_positive_segment_selection_zero`, so the next attempt family is `reviewed_positive_selected_segment_profile`
- reviewed-positive selection follow-through fix attempt 2 failed to move selection: the non-default selected-segment profile preserved proposal/collapse evidence but still yielded `reviewedPositiveSelectedFrameCount = 0`, `reviewedPositiveAcceptedFrameCount = 0`, and next corrective family `reviewed_positive_selection_blocker_summary`
- reviewed-positive selection follow-through fix attempt 3 exhausted the batch: saved proof artifacts lack row-level selected-segment gate trace for the 5 collapsed reviewed-positive frames, so generated truth selects `proof_selection_gate_trace_refresh`
- proof selection gate trace refresh attempt 1 succeeded: generated proof trace shows all 5 collapsed reviewed-positive frames are blocked by selected-segment edge share (`edgeShareRejected = true`, `edgeShareForSegment = 1.0`), so the next corrective family is `reviewed_positive_edge_share_gate_override`
- reviewed-positive edge-share gate override attempt 1 succeeded as selected-frame lift: the narrow non-default profile moved all 5 reviewed-positive collapsed frames into selected follow-through (`reviewedPositiveSelectedFrameCount = 5`) while accepted remained `0`, so the next corrective family is `reviewed_positive_acceptance_fix`
- reviewed-positive acceptance fix attempt 1 succeeded as diagnostic truth: all 5 selected reviewed-positive frames remain unaccepted and lack row-level acceptance-gate trace, so the next corrective family is `proof_acceptance_gate_trace_refresh`
- proof acceptance gate trace refresh attempt 1 succeeded as diagnostic truth: fresh proof now emits `acceptanceGateTrace`, all 5 selected reviewed-positive frames classify as `reviewed_positive_selected_rejected_by_viability`, and the next corrective family is `reviewed_positive_acceptance_profile`
- reviewed-positive acceptance profile attempt 1 succeeded as controlled proof lift: the first 5 reviewed-positive frames became accepted, accepted retention rose to `0.099`, and 12 reviewed-positive frames remained residual no-proposal targets
- reviewed-positive residual proposal generation fix attempts 1-3 succeeded as another controlled proof lift: v2 residual profile produced proof truth with `bestProposalRawDetectedFrames = 17`, `bestProposalAfterSeedCollapseFrames = 17`, `bestProposalSelectedFrames = 10`, and `reviewedPositiveAcceptedFrameCount = 10`; promotion still fails on `accepted_signal_retention_collapse`
- reviewed-positive acceptance profile attempt 1 succeeded as acceptance lift: the non-default profile moved all 5 selected reviewed-positive frames into accepted truth, retention improved to `acceptedRetentionRatio = 0.099`, but 12 reviewed-positive frames still have no promoted proposal evidence
- residual segment selection microfix and accepted-retention guardrail audit clarified the current blocker: a non-default microprofile can accept the four residual collapsed frames, but generated promotion truth still fails because the best promoted arm is only `0.109 / 0.112` accepted/controlled retention against `0.60 / 0.60` guardrails; next family is `global_accepted_gap_audit`
- global accepted gap audit clarified the deeper failure: promoted accepted-frame count improved, but the accepted frame IDs do not overlap the baseline accepted frame IDs. Current missing-frame taxonomy is `94` no-promoted-proposal frames plus `7` collapsed-not-selected reachable frames, so the next family is `global_reachable_acceptance_probe`.
- global reachable acceptance probe recovered the seven collapsed-not-selected baseline-aligned frames, improving promoted baseline retention to `0.139 / 0.173`; the remaining blocker is now denominator/truth quality because 68 of the 94 remaining missing baseline-accepted frames overlap old refuted bootstrap seeds.
- baseline denominator review refresh proved denominator filtering is not enough: excluding 68 refuted denominator frames leaves effective accepted retention at `0.212`, still below `0.60`, so the lane now moves to `touchline_detector_candidate_v7_training_data_refresh`.

## Latest Failure-Analysis Truth

The saved-artifact v5 diagnosis is now the active corrective truth:

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
- failure-analysis batch goal achieved: `true`
- roadmap advance allowed: `false`

## What Matters Next

- `touchline_detector_candidate_v7_training_data_refresh` attempt 1 completed and wrote the concrete v7 dataset manifest, but the local quality gate is not train-ready: `17` reviewed positives are below the `20`-frame minimum and `23` denominator frames remain pending review.
- `manual_review_denominator_expansion` attempt 1 completed and extracted all `23` pending denominator review frames; the lane is paused on `manual_review_pending`.
- `manual_review_denominator_resolution` attempt 1 completed after AI-assisted visual review: `19` denominator frames are reviewed positives, `4` are reviewed negatives, and total reviewed positives are now `36`.
- `touchline_detector_candidate_v7_training` attempt 1 completed on RunPod and produced evaluation-ready weights for `touchline_detector_candidate_v7`.
- `touchline_detector_candidate_v7_evaluation` attempt 1 completed, but v7 did not beat the plateau; next run `touchline_detector_candidate_v7_evaluation_failure_analysis`.
- `touchline_detector_candidate_v7_evaluation_failure_analysis` attempt 1 completed and proved the current v7 blocker is zero raw auxiliary-probe signal; next audit probe-assist integration before retraining.
- `v7_probe_assist_integration_audit` attempt 1 completed and proved the probe is staged/invoked but emits zero raw detections; next audit threshold/preprocessing/class assumptions before retraining.
- `v7_probe_threshold_preprocessing_fix` attempt 1 completed and proved v7 can detect all exported positive examples offline at low confidence.
- `v7_probe_threshold_contract_fix` attempt 1 completed and proved the proof-only low-confidence contract recovers v7 probe signal, but it floods the proof (`rawProbeObservedBallFrames = 1516`, `probeObservedBallFrames = 1516`, `acceptedFrames = 1516`); next audit precision guardrails before any promotion path.
- `v7_probe_precision_guardrail_audit` attempt 1 completed and found no safe threshold/geometry split: `positiveFrameHitRate = 1.0`, `negativeFrameHitRate = 1.0`, `positiveLocalizationHitRate = 0.0`, `topLeftBoxShare = 1.0`, `nearConstantConfidenceShare = 1.0`, and `medianDetectedBoxAreaToGtBoxAreaRatio = 170.912`.
- `v7_training_data_quality_refresh` attempt 1 completed and found sane positive labels but unsafe negative semantics: `malformedLabelCount = 0`, `bboxMismatchCount = 0`, `refutedSeedPositiveLabelCount = 0`, `unsafeFullFrameNegativeCount = 78`, and `hardNegativeCandidateCount = 304`; next move is `v7_negative_semantics_review`.
- `v7_negative_semantics_review` attempt 1 completed and packaged the unsafe negatives: `unsafeFullFrameNegativeCount = 78`, `pendingVisibleBallReviewCount = 78`, `topLeftArtifactHardNegativeCandidateCount = 200`, `sourceHardNegativeCandidateCount = 304`, and `nextCorrectiveFamily = v7_negative_crop_conversion_plan`.
- `v7_negative_crop_conversion_plan` attempt 1 completed and converted the data lane into a v7.1 manifest-prep surface: `positiveExamplesPreserved = 30`, `unsafeFullFrameNegativeExcludedCount = 78`, `localHardNegativeCropCount = 200`, `roadmapAdvanceAllowed = true`, and `nextCorrectiveFamily = v7_1_training_manifest_prep`.
- `v7_1_training_manifest_prep` attempt 1 completed and cleared the v7.1 prep gate: `trainingPrepReady = true`, `positiveExampleCount = 30`, `negativeExampleCount = 200`, `unsafeFullFrameNegativeCount = 0`, `refutedSeedPositiveLabelCount = 0`, `weakEvidenceReasons = []`, and `nextCorrectiveFamily = touchline_detector_candidate_v7_1_training`.
- `v7_1_crop_manifest_consistency_refresh` completed on attempt 2 after adapting to attempt-1 split leakage: generated truth says `positiveCropExampleCount = 90`, `localHardNegativeCropCount = 180`, `heldoutHardNegativeCanaryCount = 20`, `negativePositiveRatio = 2.0`, `splitLeakageCount = 0`, `manifestReadyForExportAudit = true`, and `nextCorrectiveFamily = v7_1_export_label_overlay_audit`.
- `v7_1_export_label_overlay_audit` completed on attempt 1: generated physical export truth says `readinessClass = v7_1_export_overlay_audit_ready`, `primaryBlocker = null`, `positiveLabelFilesWithExactlyOneBall = 90`, `negativeLabelFilesEmpty = 180`, `heldoutCanaryLabelFilesEmpty = 20`, `positiveLabelRoundTripMaxErrorPx = 0.5`, `splitLeakageCount = 0`, `canaryLeakageCount = 0`, and `nextRecommendedNextLever = v7_1_tiny_overfit_sanity_train`.
- `v7_1_tiny_overfit_sanity_train` exhausted its 3 attempts: RunPod helper plumbing was repaired, remote CUDA/device mismatch was bypassed with CPU fallback, but generated truth after completed training says `tinyTrainPositiveLocalizationHitRate = 0.0`, `tinyTrainNegativeFalsePositiveFrameRate = 0.0`, `tinyHeldoutCanaryFalsePositiveFrameRate = 0.0`, `primaryBlocker = v7_1_tiny_train_positive_localization_failure`, and `nextRecommendedNextLever = v7_1_training_config_or_export_debug`.
- `v7_1_training_config_or_export_debug` completed on attempt 1 and corrected the diagnosis: labels were loaded (`trainerObservedLabelRowCount = 10`, class set `[0]`, `trainerObservedNc = 1`) and losses were nonzero/decreasing, but inference used the wrong checkpoint contract (`bestWeightsPathLocal` existed while the old tiny inference path looked for `bestWeightsLocalPath`), selecting `v7_1_tiny_overfit_retry_with_verified_config`.
- `v7_1_tiny_overfit_retry_with_verified_config` completed on attempt 1 and passed: generated truth says `checkpointContractPassed = true`, `inferenceUsedTrainedWeights = true`, `selectedCheckpointForVerdict = best.pt`, `selectedAuditConf = 0.1`, `tinyTrainPositiveLocalizationHitRate = 0.9`, `medianTrainPositiveConfidence = 0.30675`, `tinyTrainNegativeFalsePositiveFrameRate = 0.0`, `tinyHeldoutCanaryFalsePositiveFrameRate = 0.0`, `topLeftArtifactShare = 0.0`, and `nextRecommendedNextLever = v7_1_bounded_retrain`.
- `v7_1_bounded_retrain` completed on attempt 1 and passed the bounded crop gate: generated truth says `checkpointContractPassed = true`, `inferenceUsedTrainedWeights = true`, `selectedCheckpointForVerdict = best.pt`, `selectedAuditConf = 0.1`, `trainerObservedLabelRowCount = 90`, `boundedTrainPositiveLocalizationHitRate = 1.0`, `boundedValPositiveLocalizationHitRate = 0.5`, `boundedTrainNegativeFalsePositiveFrameRate = 0.0`, `boundedValNegativeFalsePositiveFrameRate = 0.0`, `heldoutCanaryFalsePositiveFrameRate = 0.0`, `medianTrainPositiveConfidence = 0.974239`, `medianValPositiveConfidence = 0.797017`, `topLeftArtifactShare = 0.0`, `giantBoxShare = 0.0`, and `nextRecommendedNextLever = v7_1_crop_probe_precision_guardrail_audit`.
- `v7_1_crop_probe_precision_guardrail_audit` completed on attempt 1 and passed the inference-only crop-probe guardrail: generated truth says `checkpointContractPassed = true`, `selectedCheckpointForAudit = best.pt`, `selectedAuditConf = 0.1`, `boundedTrainPositiveLocalizationHitRate = 1.0`, `boundedValPositiveLocalizationHitRate = 0.5`, zero hard-negative/canary/top-left false positives, `precisionGuardrailPassed = true`, `secondaryConcern = v7_1_validation_positive_recall_limited`, and `nextRecommendedNextLever = v7_1_full_pipeline_non_promotion_eval`.
- `v7_1_full_pipeline_non_promotion_eval` completed on attempt 1 and passed as a diagnostic pipeline audit: generated truth says `candidateCropCoverageRate = 1.0`, `cropDetectorConditionalLocalizationRate = 0.933333`, `sourceFrameLocalizationHitRate = 0.933333`, `observedBallAcceptanceRate = 0.933333`, `projectionAuditPassed = true`, zero canary/top-left/sample flood regressions, `secondaryConcern = v7_1_validation_positive_recall_limited`, and `nextRecommendedNextLever = v7_1_positive_diversity_refresh`.
- `v7_1_positive_diversity_refresh` completed on attempt 1 as a review-package/data-expansion gate: generated truth says `previousReviewedPositiveSourceCount = 30`, `newReviewedPositiveSourceCount = 0`, `totalReviewedPositiveSourceCount = 30`, `distinctPositiveSplitGroupCount = 6`, `knownCropValidationMissesIncluded = 9`, `knownFullPipelineMissesIncluded = 2`, `positiveReviewQueueCandidateCount = 89`, `labelOverlayReviewReady = true`, `splitLeakageCount = 0`, `unsafeFullFrameNegativeExportCount = 0`, `primaryBlocker = v7_1_positive_diversity_insufficient_reviewed_count`, and `nextRecommendedNextLever = v7_1_positive_diversity_manual_review_expansion`.
- `v7_1_positive_diversity_manual_review_expansion` completed on attempt 1 as a manual-review package: generated truth says `reviewQueueCandidateCount = 149`, `pendingReviewCount = 149`, `previousReviewedPositiveSourceCount = 30`, `newReviewedPositiveSourceCount = 0`, `totalReviewedPositiveSourceCount = 30`, `splitLeakageCount = 0`, `unsafeFullFrameNegativeExportCount = 0`, `trainingExecuted = false`, and `batchStatus = manual_review_pending`.
- `v7_1_positive_diversity_manual_review_resolution` attempt 1 is resolved and selected more mining: generated truth says `reviewCandidateCount = 149`, `pendingReviewItemCount = 0`, `newReviewedPositiveSourceCount = 4`, `totalReviewedPositiveSourceCount = 34`, `reviewDeferredUnclearCount = 102`, `reviewedNotBallCount = 36`, `duplicateOrNearDuplicateCount = 7`, `invalidReviewStatusCount = 0`, `invalidBBoxCount = 0`, `labelQualityGapCount = 0`, `trainingExecuted = false`, `primaryBlocker = v7_1_positive_diversity_review_yield_insufficient`, and `nextRecommendedNextLever = v7_1_positive_candidate_mining_expansion`.
- `v7_1_positive_candidate_mining_expansion` attempt 1 completed as a correction-ready expansion: generated truth says `previousReviewedPositiveSourceCount = 34`, `previousReviewCandidateCount = 149`, `previousAcceptedPositiveCount = 4`, `previousDeferredUnclearCount = 102`, `salvageCorrectionQueueCount = 102`, `newMinedCandidateCount = 240`, `totalCandidateReviewCount = 342`, `knownCropValidationMissesCarriedForward = 9`, `knownFullPipelineMissesCarriedForward = 2`, `distinctCandidateSplitGroupCount = 4`, `trainingExecuted = false`, `promotionReady = false`, `candidateReadyForEvaluation = false`, `runtimeDefaultMutationAllowed = false`, `primaryBlocker = null`, and `nextRecommendedNextLever = v7_1_positive_diversity_manual_review_expansion_v2`.
- `v7_1_positive_diversity_manual_review_resolution_v2` has been run against the corrected overlay and is intentionally pending: generated truth says `reviewCandidateCount = 342`, `pendingReviewItemCount = 342`, `newReviewedPositiveSourceCount = 0`, `totalReviewedPositiveSourceCount = 34`, `invalidReviewStatusCount = 0`, `invalidBBoxCount = 0`, `labelQualityGapCount = 0`, `primaryBlocker = v7_1_positive_diversity_manual_review_still_pending`, and `nextRecommendedNextLever = v7_1_positive_diversity_manual_review_resolution_v2`.
- The reviewed-positive branch is useful proof/truth surface, but it is not large enough by itself to clear the retention guardrails.
- Runtime defaults stay frozen until generated promoted robustness truth says `winningPassedPromotionGate = true`.

The roadmap stays honest about the broader suite, but the bounded evaluation lane no longer needs another retry batch.

The next honest move should:

- resolve `v7_1_positive_candidate_mining_expansion_v1/corrected_label_overlay.json` in `v7_1_positive_diversity_manual_review_expansion_v2`; keep runtime defaults frozen
- use the low-confidence flood as model/data-quality evidence, not as a promotable probe contract
- use the verified tiny-overfit result before v7.1 bounded crop retrain
- use the generated promoted-v6 robustness-validation artifacts as the latest lane truth
- use the saved retention-delta diagnosis as the primary blocker truth
- keep the broader suite truth explicit: `suiteVerdict = baseline_not_robust` and `sourceRobustnessPromotionBlockers = [failing_source_not_viable]`
- keep the runtime-default switch blocked until failing-source viability is cleared
- follow the active checklist’s mega-queue contract:
  - `3` distinct approaches for the current manual-review unblock family unless the checklist says otherwise
  - advance within the same lane after exhaustion instead of phase-jumping

Useful future sequence now accepted into the roadmap:

- harden pitch homography only if the current delta analysis implicates calibration/projection
- build failure taxonomy review, source-manifest expansion, and a small gold set after the blocker class is explicit
- start semantics later in the order `team assignment -> owner assignment -> possession chains -> event layer`
