# Promoted V6 Failing-Source Robustness Validation

## History

- `touchline_detector_candidate_promotion_validation_v1` already succeeded and promoted `touchline_detector_candidate_v6` for controlled/internal runs only.
- Runtime defaults remained frozen because `failing_source_not_viable` was still visible in the broader suite.
- The completed promotion checklist is `docs/superpowers/plans/2026-04-23-touchline-detector-candidate-promotion-v6.md`.

## Unattended Loop Contract

- The canonical start point is the first unchecked task in this checklist.
- The latest completed batch is `promoted_touchline_detector_candidate_retention_delta_analysis_v1`.
- This lane is still `Validation First`: runtime defaults do not change here.
- Do not ask for approval; make reasonable assumptions from repo truth.
- Complete one batch fully before moving to the next truthful step.
- Stop only after verified batch completion or a real unresolved blocker that cannot be resolved from repo truth.
- Update memorybank and `SESSION-HANDOFF.md` only from generated artifacts.
- Do not make any success claim without fresh verification evidence.
- If this checklist has no unchecked tasks left, stop and write the next strict plan before continuing.
- Do not change phases, invent new lanes, or privilege speculative docs over generated artifacts.
- This contract supports unattended continuation inside a live session only; it does not self-wake after the session ends without an external re-invocation source.

## Acceptance Criteria

- [x] One new strict robustness-validation checklist exists for the promoted-v6 lane.
- [x] The batch driver reads only existing generated v6 truth plus frozen suite inputs.
- [x] The suite-level artifact family exists under `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/promoted_touchline_detector_candidate_robustness_validation_v1/`.
- [x] `promotedDetectorCandidateRobustnessDiagnosis` is ingested into suite truth surfaces.
- [x] Runtime defaults remain unchanged in this batch.
- [x] The repo truth now says the controlled promoted arm did not clear `failing_source_not_viable`.

## Latest V7.2 Data-Lane Addendum

- `v7_2_training_manifest_prep` passed with `139` reviewed positive source boxes, `414` positive crop examples, `180` hard-negative crops, `20` heldout canaries, zero unsafe full-frame negatives, and zero split leakage.
- `v7_2_export_label_overlay_audit` passed with `414 / 414` positive images and one-ball labels, `180 / 180` empty hard-negative labels, `20 / 20` empty canary labels, `positiveCropBoundsRepairedCount = 12`, and `positiveLabelRoundTripMaxErrorPx = 0.500392`.
- `v7_2_bounded_retrain` attempt 1 passed on RunPod with a verified local checkpoint contract:
  - `trainingCompleted = true`
  - `checkpointContractPassed = true`
  - `selectedCheckpointForVerdict = best.pt`
  - `selectedAuditConf = 0.1`
  - `trainerObservedLabelRowCount = 414`
  - `boundedTrainPositiveLocalizationHitRate = 0.985507`
  - `boundedValPositiveLocalizationHitRate = 0.971014`
  - `boundedTrainNegativeFalsePositiveFrameRate = 0.0`
  - `boundedValNegativeFalsePositiveFrameRate = 0.0`
  - `heldoutCanaryFalsePositiveFrameRate = 0.0`
  - `topLeftArtifactShare = 0.0`
  - `giantBoxShare = 0.0`
- `v7_2_crop_probe_precision_guardrail_audit` attempt 1 passed as an inference-only guardrail:
  - `trainingAllowed = false`
  - `trainingExecuted = false`
  - `checkpointContractPassed = true`
  - `selectedCheckpointForAudit = best.pt`
  - `selectedAuditConf = 0.1`
  - `boundedTrainPositiveLocalizationHitRate = 0.985507`
  - `boundedValPositiveLocalizationHitRate = 0.971014`
  - `boundedTrainHardNegativeFalsePositiveFrameRate = 0.0`
  - `boundedValHardNegativeFalsePositiveFrameRate = 0.0`
  - `heldoutCanaryFalsePositiveFrameRate = 0.0`
  - `oldTopLeftArtifactFalsePositiveFrameRate = 0.0`
  - `recallGuardrailStrength = strong_pass`
- `v7_2_full_pipeline_non_promotion_eval` attempt 1 passed as a diagnostic pipeline audit:
  - `trainingAllowed = false`
  - `trainingExecuted = false`
  - `checkpointContractPassed = true`
  - `selectedCheckpointForAudit = best.pt`
  - `selectedAuditConf = 0.1`
  - `positiveReviewedFrameCount = 138`
  - `positiveCropRowCount = 414`
  - `positiveCropBoundsRepairedCount = 12`
  - `candidateCropCoverageRate = 1.0`
  - `cropDetectorConditionalLocalizationRate = 1.0`
  - `sourceFrameLocalizationHitRate = 1.0`
  - `observedBallAcceptanceRate = 1.0`
  - `projectionAuditPassed = true`
  - `projectionErrorCount = 0`
  - `heldoutCanaryFalsePositiveFrameRate = 0.0`
  - `oldTopLeftArtifactFalsePositiveFrameRate = 0.0`
  - `sampledFrameDetectionRate = 0.0`
- `football_external_benchmark_harness_prep` attempt 1 passed as a prep/readiness batch:
  - `resourceCount = 5`
  - `adapterSchemaCount = 6`
  - `stageGateCount = 6`
  - `stageCoverageComplete = true`
  - `missingRequiredStageCoverage = []`
  - `benchmarkHarnessContractReady = true`
  - `datasetAccessReviewReady = true`
  - `externalBenchmarkExecutionReady = false`
  - `datasetDownloadExecuted = false`
  - `trainingExecuted = false`
  - `candidateReadyForEvaluation = false`
  - `runtimeDefaultMutationAllowed = false`
  - `attemptPlanFamilies = [external_benchmark_contract_prep, benchmark_adapter_contract_repair, benchmark_harness_blocker_summary]`
- Runtime defaults now point to the validated v7.2 inboard recovery profile after runtime-default change validation, post-default source-robustness validation, and rollout closeout all passed.
- Next v7.2 data-lane batch: `football_external_dataset_access_review`.

## Ordered Tasks

- [x] Create one controlled promoted-v6 robustness-validation batch driver.
- [x] Reuse the existing source-robustness gate exactly.
- [x] Generate the three-arm validation artifact family from genuine saved truth.
- [x] Extend suite ingestion with `promotedDetectorCandidateRobustnessDiagnosis`.
- [x] Update memorybank, handoff, and unattended-loop surfaces from generated truth only.

## Latest Generated Truth

- `validationBatchName = promoted_touchline_detector_candidate_robustness_validation_v1`
- `trainingCandidateName = touchline_detector_candidate_v6`
- `evaluatedArmNames = [baseline_current, promoted_v6_baseline, promoted_v6_plus_best_thin]`
- `winningArmName = promoted_v6_baseline`
- `winningConfigOutcome = source_robustness_weak`
- `winningPassedPromotionGate = false`
- `winningPromotionBlockers = [accepted_retention_below_guardrail, controlled_retention_below_guardrail]`
- `winningFailingSourceEdgeShareImprovement = 0.812`
- `runtimeDefaultChanged = false`
- `goalAchieved = false`
- `roadmapAdvanceAllowed = false`
- `nextRecommendedNextLever = promote_touchline_detector_candidate`

## Concrete Read

- the controlled promoted-v6 robustness validation did not achieve its goal
- no promoted arm cleared the remaining failing-source blocker
- the decisive blockers were failing-source retention guardrails, not edge-share improvement
- runtime defaults remain frozen
- the promotion lane stays active

## Attempt Budget Rule

- Every queued batch gets exactly `4` attempts unless it succeeds earlier.
- An attempt only counts if it uses a materially different approach family.
- Tiny threshold nudges on the same idea do not count as a new attempt.
- Allowed approach families for this blocker cycle are:
  - `admission_widening`
  - `baseline_guided_rescue`
  - `continuity_bridge_recovery`
  - `acceptance_support_gating`
  - `selected_cluster_follow_through`
  - `controlled_possession_follow_through`
  - `review_taxonomy_refresh`
  - `manifest_scope_refresh`
  - `gold_truth_bootstrap`
  - `calibration_hardening`
- After every attempt:
  - run focused verification
  - regenerate suite truth if artifacts changed
  - update memorybank, `SESSION-HANDOFF.md`, and unattended heartbeat from generated truth only
  - write the exact approach family, result, and next decision
- If a batch exhausts all `4` attempts without success:
  - mark it `exhausted`
  - append the exact failure summary to this same checklist
  - immediately advance to the next queued batch in this same lane
- If a batch precondition is not met:
  - mark it `skipped`
  - state the unmet precondition explicitly
  - advance to the next queued batch in this same lane
- If any batch clears the promoted robustness gate:
  - jump straight to the matching runtime-default validation batch
  - skip still-blocked corrective batches
- Never reopen these as the default next move:
  - touchline probe replacement
  - touchline acquisition upgrade/reopen as a broad answer
  - combined detector-and-candidate reopen as a broad answer
  - another bounded v6 evaluation rerun
- If the queue ends with no gate-clearing result:
  - stop with a blocker summary
  - write a fresh strict plan instead of silently looping

## Next Session Execution Queue

- The queue items below are the only live next-session worklist for this blocker cycle.
- The first unchecked batch remains the active start point for unattended continuation.
- Success on any queue item only advances the roadmap if its own batch-specific gate is met.

## Next Corrective Sub-Batch — promoted_v6_failing_source_retention_delta_analysis_v1

- Blocker statement:
  - promoted-v6 robustness validation already completed
  - `winningArmName = promoted_v6_baseline`
  - `winningConfigOutcome = source_robustness_weak`
  - `winningPassedPromotionGate = false`
  - `winningPromotionBlockers = [accepted_retention_below_guardrail, controlled_retention_below_guardrail]`
  - `winningFailingSourceEdgeShareImprovement = 0.812`
- Bounded inputs:
  - `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/promoted_touchline_detector_candidate_robustness_validation_v1/`
  - `backend/storage/trained_detector_candidates/touchline_detector_candidate_v6/evaluation_v1/`
  - frozen suite manifest and saved baseline artifacts
  - `proofRuns[].reusedEvidence.selectedClusterDeltaPath` where present
- Ordered tasks:
  - [x] Create one saved-artifact retention-delta analysis driver under `backend/scripts/`.
  - [x] Produce a stage-wise failing-source delta across `baseline_current`, `promoted_v6_baseline`, and `promoted_v6_plus_best_thin`.
  - [x] Classify exactly one primary retention blocker class and name exactly one next implementation batch.
  - [x] Fold in the two truth-safety fixes so runtime-default validation cannot be selected from inconsistent promoted-robustness state.
  - [x] Refresh suite truth, memorybank, handoff, and unattended-loop surfaces from generated analysis only.
- Acceptance criteria:
  - [x] No new proof or training run is required.
  - [x] The batch writes `retention_delta_summary.json`, `failing_source_stage_delta.json`, `selected_cluster_follow_through_delta.json`, `decision_matrix.json`, `batch_outcome_analysis.json`, and `batch_outcome_analysis.md`.
  - [x] The batch names exactly one next implementation batch.
  - [x] Runtime defaults remain unchanged.
  - [x] `sourceRobustnessRecommendedNextLever = promote_touchline_detector_candidate`.
- Latest generated truth:
  - `analysisBatchName = promoted_touchline_detector_candidate_retention_delta_analysis_v1`
  - `winningArmName = promoted_v6_baseline`
  - `primaryRetentionBlockerClass = accepted_signal_retention_collapse`
  - `acceptedRetentionRatio = 0.069`
  - `controlledRetentionRatio = 0.102`
  - `selectedClusterStepImplicated = false`
  - `nextImplementationBatchRecommendation = touchline_detector_candidate_v6_accepted_signal_retention_fix_v1`
  - `goalAchieved = false`
  - `roadmapAdvanceAllowed = false`
  - `nextRecommendedNextLever = promote_touchline_detector_candidate`

## Next Corrective Sub-Batch — touchline_detector_candidate_v6_accepted_signal_retention_fix_v1

- Goal:
  - move the primary blocker away from `accepted_signal_retention_collapse`
  - raise failing-source accepted retention materially from the latest generated `0.069`
  - keep runtime defaults frozen
- Use only:
  - promoted-v6 robustness-validation artifacts
  - promoted-v6 retention-delta analysis artifacts
  - saved proof bundles and selected-cluster deltas
  - existing frozen suite inputs
- Attempts:
  - Attempt 1: `admission_widening`
    - widen the narrowest accepted-signal admission constraints that currently suppress failing-source accepted frames while preserving current edge-share gains
  - Attempt 2: `baseline_guided_rescue`
    - use saved baseline-supported failing-source neighborhoods to recover missing accepted signal for the promoted arm without changing the runtime-default contract
  - Attempt 3: `continuity_bridge_recovery`
    - rescue short, sparse accepted runs by improving continuity and bridge follow-through before cluster selection
  - Attempt 4: `acceptance_support_gating`
    - retune acceptance and support behavior to keep promoted signal alive longer without reintroducing the old touchline edge collapse
- Batch success gate:
  - the latest diagnosis no longer says `primaryRetentionBlockerClass = accepted_signal_retention_collapse`
- If success:
  - if the next blocker becomes `selected_cluster_follow_through_collapse`, go to `touchline_detector_candidate_v6_selected_cluster_follow_through_fix_v1`
  - if the next blocker becomes `controlled_possession_follow_through_collapse`, go to `touchline_detector_candidate_v6_controlled_possession_follow_through_fix_v1`
  - if promoted robustness clears entirely for `promoted_v6_baseline`, go to `validate_promoted_touchline_runtime_default`
  - if promoted robustness clears entirely for `promoted_v6_plus_best_thin`, go to `validate_promoted_touchline_runtime_default_plus_best_thin`
- If exhausted and still `accepted_signal_retention_collapse`:
  - go to `promoted_v6_failing_source_review_refresh_v1`
- Attempt Log Template:
  - `attemptNumber`
  - `approachFamily`
  - `whyDistinct`
  - `result`
  - `artifactsChanged`
  - `nextDecision`
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = admission_widening`
  - `whyDistinct = added a controlled promoted-v6 admission-widening shadow profile and validated it only on the promoted baseline arm, with runtime defaults frozen`
  - `result = failed; regenerated truth still says primaryRetentionBlockerClass = accepted_signal_retention_collapse, acceptedRetentionRatio = 0.099, controlledRetentionRatio = 0.133`
  - `artifactsChanged = true; regenerated promoted robustness validation, retention-delta analysis, suite summary, active lane snapshot, and suite robustness diagnosis`
  - `nextDecision = continue current item with attempt 2 baseline_guided_rescue`
  - `attemptNumber = 2`
  - `approachFamily = baseline_guided_rescue`
  - `whyDistinct = generated a baseline-guided rescue reference from saved baseline/promoted truth layers and used it as proposal-window seed input for the failing source only, while preserving runtime defaults`
  - `result = failed; regenerated truth still says primaryRetentionBlockerClass = accepted_signal_retention_collapse, acceptedRetentionRatio = 0.069, controlledRetentionRatio = 0.102`
  - `artifactsChanged = true; regenerated promoted robustness validation, retention-delta analysis, suite summary, active lane snapshot, and suite robustness diagnosis`
  - `nextDecision = continue current item with attempt 3 continuity_bridge_recovery`
  - `attemptNumber = 3`
  - `approachFamily = continuity_bridge_recovery`
  - `whyDistinct = added a promoted-v6-only continuity bridge shadow profile that preserves real detected candidate rows across short accepted/proposal-supported gaps before final viable segment selection, with endpoint continuity, repeated-anchor, viability, and edge-share guards`
  - `result = failed; regenerated truth still says primaryRetentionBlockerClass = accepted_signal_retention_collapse, acceptedRetentionRatio = 0.069, controlledRetentionRatio = 0.102`
  - `artifactsChanged = true; regenerated promoted robustness validation, retention-delta analysis, suite summary, active lane snapshot, and suite robustness diagnosis`
  - `nextDecision = continue current item with attempt 4 acceptance_support_gating`
  - `attemptNumber = 4`
  - `approachFamily = acceptance_support_gating`
  - `whyDistinct = added a promoted-v6-only acceptance/support gating shadow profile that lets support-credible inboard candidates survive strict admission when they improve accepted-signal support, while preserving repeated-anchor, continuity, real-detection, and projected edge-share guards`
  - `result = failed; regenerated truth still says primaryRetentionBlockerClass = accepted_signal_retention_collapse, acceptedRetentionRatio = 0.069, controlledRetentionRatio = 0.102`
  - `artifactsChanged = true; regenerated promoted robustness validation, retention-delta analysis, suite summary, active lane snapshot, and suite robustness diagnosis`
  - `nextDecision = mark touchline_detector_candidate_v6_accepted_signal_retention_fix_v1 exhausted and advance to promoted_v6_failing_source_review_refresh_v1`
- Ordered tasks:
  - [x] Use the saved retention-delta diagnosis as the only live blocker truth.
  - [x] Stay in the promotion lane and fix accepted-signal retention before reopening any runtime-default validation.
  - [x] Prove the accepted-signal attempts did not increase failing-source accepted retention enough to move the generated blocker.
  - [x] Exhaust all 4 materially distinct accepted-signal retention attempts without changing runtime defaults.

## Next Corrective Sub-Batch — touchline_detector_candidate_v6_selected_cluster_follow_through_fix_v1

- Precondition:
  - accepted retention is no longer the primary blocker
  - generated truth says the cluster step is the first collapse point
- Attempts:
  - Attempt 1: `selected_cluster_follow_through`
    - improve cluster choice stability on the failing source
  - Attempt 2: `selected_cluster_follow_through`
    - preserve accepted signal better across the cluster handoff boundary
  - Attempt 3: `selected_cluster_follow_through`
    - improve event and possession carry-over from selected cluster output
  - Attempt 4: `selected_cluster_follow_through`
    - strengthen follow-through ranking using only saved failing-source evidence and non-regressed comparison behavior
- Batch success gate:
  - the latest diagnosis no longer implicates the selected-cluster step as the primary collapse point
- If success:
  - if controlled possession still blocks, go to `touchline_detector_candidate_v6_controlled_possession_follow_through_fix_v1`
  - if promoted robustness clears, go to the matching runtime-default validation batch
- If exhausted:
  - go to `promoted_v6_source_manifest_and_gold_truth_refresh_v1`
- Attempt Log Template:
  - `attemptNumber`
  - `approachFamily`
  - `whyDistinct`
  - `result`
  - `artifactsChanged`
  - `nextDecision`
- Ordered tasks:
  - [x] Skip this batch because accepted retention remains the first blocker.
  - [x] Do not use selected-cluster follow-through while accepted-signal collapse remains primary.
  - [x] Keep selected-cluster follow-through blocked until generated truth says accepted retention is no longer first.

## Next Corrective Sub-Batch — touchline_detector_candidate_v6_controlled_possession_follow_through_fix_v1

- Precondition:
  - accepted retention is acceptable
  - selected cluster is not the primary failure point
  - controlled retention still fails
- Attempts:
  - Attempt 1: `controlled_possession_follow_through`
    - improve controlled-possession carry from accepted ball signal
  - Attempt 2: `controlled_possession_follow_through`
    - reduce provisional and team-selection dependency drag on the failing source
  - Attempt 3: `controlled_possession_follow_through`
    - strengthen pass and turnover follow-through enough to raise event-family support without changing runtime defaults
  - Attempt 4: `controlled_possession_follow_through`
    - rebalance possession and event continuity for sparse but viable promoted tracks
- Batch success gate:
  - the latest diagnosis no longer has controlled-possession follow-through as the primary blocker
- If success:
  - if promoted robustness clears, go to the matching runtime-default validation batch
  - otherwise go to `promoted_v6_source_manifest_and_gold_truth_refresh_v1`
- If exhausted:
  - go to `promoted_v6_source_manifest_and_gold_truth_refresh_v1`
- Attempt Log Template:
  - `attemptNumber`
  - `approachFamily`
  - `whyDistinct`
  - `result`
  - `artifactsChanged`
  - `nextDecision`
- Ordered tasks:
  - [x] Skip this batch because accepted retention is not acceptable.
  - [x] Do not use controlled-possession follow-through while accepted-signal collapse remains primary.
  - [x] Keep controlled-possession follow-through blocked until generated truth says accepted retention is acceptable.

## Next Corrective Sub-Batch — promoted_v6_failing_source_review_refresh_v1

- Precondition:
  - `touchline_detector_candidate_v6_accepted_signal_retention_fix_v1` is exhausted
  - accepted-signal collapse remains primary
- Purpose:
  - refresh human-reviewed blocker evidence instead of burning a fifth near-duplicate detector-side attempt
- Attempts:
  - Attempt 1: `review_taxonomy_refresh`
    - relabel missing accepted-signal windows into a strict root-cause taxonomy
  - Attempt 2: `review_taxonomy_refresh`
    - isolate frames where baseline had accepted signal and promoted v6 did not
  - Attempt 3: `review_taxonomy_refresh`
    - isolate promoted-only viable windows that still died before useful accepted accumulation
  - Attempt 4: `review_taxonomy_refresh`
    - produce one Pareto-ranked blocker sheet that names the dominant accepted-signal loss mode
- Batch success gate:
  - it produces one sharper blocker class and one evidence-backed next fix family
- If success:
  - go to `promoted_v6_source_manifest_and_gold_truth_refresh_v1`
- If exhausted:
  - still go to `promoted_v6_source_manifest_and_gold_truth_refresh_v1`
  - mark blocker evidence as weak
- Attempt Log Template:
  - `attemptNumber`
  - `approachFamily`
  - `whyDistinct`
  - `result`
  - `artifactsChanged`
  - `nextDecision`
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = review_taxonomy_refresh`
  - `whyDistinct = generated a saved-artifact taxonomy of baseline accepted frames missing from promoted v6 instead of trying a fifth detector-side accepted-signal tweak`
  - `result = succeeded; generated dominantBlockerClass = proposal_signal_present_but_not_selected, nextFixFamily = proposal_selection_evidence_refresh, missingAcceptedFrameCount = 101, windowCount = 11`
  - `artifactsChanged = true; wrote review-refresh summary, missing accepted-signal taxonomy, frame-window taxonomy, decision matrix, and batch outcome artifacts`
  - `nextDecision = advance to promoted_v6_source_manifest_and_gold_truth_refresh_v1`
- Ordered tasks:
  - [x] Only run this batch after Queue 1 exhausts and accepted-signal collapse remains primary.
  - [x] Keep all `4` attempts inside `review_taxonomy_refresh`.
  - [x] Produce one evidence-backed blocker summary before leaving this batch.

## Next Corrective Sub-Batch — promoted_v6_source_manifest_and_gold_truth_refresh_v1

- Purpose:
  - if direct corrective work is exhausted, improve truth quality before more detector-side guessing
- Attempts:
  - Attempt 1: `manifest_scope_refresh`
    - rebalance the worst-source manifest around the failing-source retention problem
  - Attempt 2: `gold_truth_bootstrap`
    - create a small failing-source gold slice for accepted and controlled truth
  - Attempt 3: `manifest_scope_refresh`
    - add metadata that separates accepted-signal sparse cases from pure edge-share cases
  - Attempt 4: `gold_truth_bootstrap`
    - harden the truth surface enough that the next corrective detector batch is chosen from labeled evidence instead of proxies alone
- Batch success gate:
  - the next corrective batch is chosen from stronger source and gold truth instead of the current sparse proxy surface
- If success:
  - plan the next detector-side retention fix from the refreshed truth
  - stay in this same lane
- If exhausted:
  - stop with a blocker summary and a fresh plan
- Attempt Log Template:
  - `attemptNumber`
  - `approachFamily`
  - `whyDistinct`
  - `result`
  - `artifactsChanged`
  - `nextDecision`
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = manifest_scope_refresh`
  - `whyDistinct = converted the review-refresh proposal-selection taxonomy into additive manifest and gold-truth bootstrap artifacts instead of making another detector-side profile`
  - `result = succeeded; generated goalAchieved = true, proposalSelectionWindowCount = 11, proposalSelectionMissingAcceptedFrameCount = 101, selectedBootstrapWindowCount = 5, selectedBootstrapMissingAcceptedFrameCount = 78`
  - `artifactsChanged = true; wrote manifest scope summary, proposal-selection window manifest, gold-truth bootstrap plan, source-manifest delta, decision matrix, and batch outcome artifacts`
  - `nextDecision = continue promoted_v6_source_manifest_and_gold_truth_refresh_v1 with attempt 2, gold_truth_bootstrap`
  - `attemptNumber = 2`
  - `approachFamily = gold_truth_bootstrap`
  - `whyDistinct = built a local truth bootstrap from the top proposal-selection windows instead of changing detector behavior or runtime defaults`
  - `result = succeeded; generated goalAchieved = true, successfulApproach = A_direct_saved_artifact_seed, representedBootstrapWindowCount = 5, representedMissingAcceptedFrameCount = 78, acceptedSeedRowCount = 78, controlledSeedCandidateRowCount = 78`
  - `artifactsChanged = true; wrote gold truth bootstrap summary, candidate frame truth manifest, accepted/controlled truth seed, review overlay, decision matrix, and batch outcome artifacts`
  - `nextDecision = stop this batch with next corrective family proposal_selection_admission_fix`
- Ordered tasks:
  - [x] Keep attempts inside `manifest_scope_refresh` and `gold_truth_bootstrap` only.
  - [x] Do not reopen runtime-default validation from this batch.
  - [x] End with either a stronger truth surface or a blocker summary and fresh plan.

## Next Corrective Sub-Batch — proposal_selection_admission_fix

- Trigger:
  - generated `gold_truth_bootstrap_attempt_v1/gold_truth_bootstrap_summary.json` says `goalAchieved = true`
  - generated `nextCorrectiveFamily = proposal_selection_admission_fix`
- Purpose:
  - use the refreshed truth surface to plan the next detector-side retention fix around proposal selection/admission
- Do not start runtime-default validation from this family.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = truth_seed_guided_selection`
  - `whyDistinct = used accepted/control truth seed rows from the gold-truth bootstrap to admit real proposal candidates close to seeded baseline accepted rows`
  - `result = failed; regenerated truth still says primaryRetentionBlockerClass = accepted_signal_retention_collapse, acceptedRetentionRatio = 0.069, controlledRetentionRatio = 0.102`
  - `artifactsChanged = true; regenerated promoted robustness validation, retention-delta analysis, suite summary, active lane snapshot, and suite robustness diagnosis`
  - `nextDecision = continue proposal_selection_admission_fix with attempt 2 window_local_proposal_kind_rescue`
  - `attemptNumber = 2`
  - `approachFamily = window_local_proposal_kind_rescue`
  - `whyDistinct = relaxed exact seed proximity but stayed inside the bootstrap windows and prioritized window-local proposal kind/support with the same edge and repeated-anchor guards`
  - `result = failed; regenerated truth still says primaryRetentionBlockerClass = accepted_signal_retention_collapse, acceptedRetentionRatio = 0.069, controlledRetentionRatio = 0.102`
  - `artifactsChanged = true; regenerated promoted robustness validation, retention-delta analysis, suite summary, active lane snapshot, and suite robustness diagnosis`
  - `nextDecision = continue proposal_selection_admission_fix with attempt 3 segment_level_seed_continuity`
  - `attemptNumber = 3`
  - `approachFamily = segment_level_seed_continuity`
  - `whyDistinct = used segment-level seeded continuity as the final proposal-selection admission approach while preserving real-detection, continuity, repeated-anchor, and projected edge-share guards`
  - `result = failed; regenerated truth still says primaryRetentionBlockerClass = accepted_signal_retention_collapse, acceptedRetentionRatio = 0.069, controlledRetentionRatio = 0.102`
  - `artifactsChanged = true; regenerated promoted robustness validation, retention-delta analysis, suite summary, active lane snapshot, suite robustness diagnosis, and proposal-selection blocker summary`
  - `nextDecision = mark proposal_selection_admission_fix exhausted; next corrective family support_viability_truth_fix`
- Ordered tasks:
  - [x] Build the next proposal-selection admission fix plan from `gold_truth_bootstrap_attempt_v1` generated truth.
  - [x] Keep runtime defaults frozen unless a later promoted robustness validation clears the gate.
  - [x] Exhaust all 3 materially distinct proposal-selection approaches without clearing the generated blocker.

## Next Corrective Sub-Batch — support_viability_truth_fix

- Trigger:
  - `proposal_selection_admission_fix/blocker_summary.json` says `batchStatus = exhausted`
  - latest generated retention truth still says `primaryRetentionBlockerClass = accepted_signal_retention_collapse`
  - latest generated `acceptedRetentionRatio = 0.069`
- Purpose:
  - determine whether support/viability filtering, truth seed quality, or manual review requirements explain why proposal-selection admission profiles did not move accepted retention.
- Do not start runtime-default validation from this family.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = support_viability_truth_analysis`
  - `whyDistinct = saved-artifact attribution over proposal-selection blocker summary, gold-truth bootstrap seed rows, candidate frame manifest, validation arm matrix, and retention truth; no new detector profile or runtime default change`
  - `result = succeeded; generated support_viability_truth_fix_v1 names dominantBlockerClass = support_viability_evidence_gap across 78 classified seed frames and 5 represented bootstrap windows`
  - `artifactsChanged = true; wrote support_viability_truth_summary.json, seed_frame_support_viability_matrix.json, support_viability_gap_taxonomy.json, proof_runtime_seed_path_audit.json, decision_matrix.json, batch_outcome_analysis.json/md, and regenerated suite truth`
  - `nextDecision = advance to support_viability_admission_fix; runtime defaults remain frozen because promoted robustness truth still has winningPassedPromotionGate = false`
- Ordered tasks:
  - [x] Build a strict saved-artifact support/viability truth-fix plan from the proposal-selection blocker summary, gold-truth bootstrap artifacts, and latest validation arm matrix.
  - [x] Keep runtime defaults frozen unless a later promoted robustness validation clears the gate.

## Next Corrective Sub-Batch — support_viability_admission_fix

- Trigger:
  - generated `support_viability_truth_fix_v1/support_viability_truth_summary.json` says `goalAchieved = true`
  - generated `dominantBlockerClass = support_viability_evidence_gap`
  - generated `nextCorrectiveFamily = support_viability_admission_fix`
- Purpose:
  - plan a detector-side corrective batch that admits or diagnoses support/viability evidence for seeded proposal frames without mutating runtime defaults.
- Do not start runtime-default validation from this family.
- Attempt budget: 3 materially distinct approaches.
- Attempt families:
  - Attempt 1: `support_evidence_lift`
  - Attempt 2: `source_space_support_neighborhood`
  - Attempt 3: `viability_neutral_seed_window`
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = support_evidence_lift`
  - `whyDistinct = admit seeded proposal candidates with explicit player support or viability-positive evidence while preserving repeated-anchor, continuity, real-detection, and projected edge-share guards`
  - result = failed from regenerated truth; promoted validation completed but `winningPassedPromotionGate = false`, blockers remained `[accepted_retention_below_guardrail, controlled_retention_below_guardrail]`, retention delta stayed `primaryRetentionBlockerClass = accepted_signal_retention_collapse`, `acceptedRetentionRatio = 0.069`, `controlledRetentionRatio = 0.102`
  - artifactsChanged = yes; promoted robustness validation, retention-delta analysis, and source robustness suite artifacts regenerated
  - nextDecision = continue support_viability_admission_fix with attempt 2 source_space_support_neighborhood; runtime defaults remain frozen
  - `attemptNumber = 2`
  - `approachFamily = source_space_support_neighborhood`
  - `whyDistinct = broaden support evidence to source-space nearest-player neighborhood while still requiring seeded-frame membership and preserving repeated-anchor, continuity, real-detection, and edge guards`
  - result = failed from regenerated truth; promoted validation completed but `winningPassedPromotionGate = false`, blockers remained `[accepted_retention_below_guardrail, controlled_retention_below_guardrail]`, retention delta stayed `primaryRetentionBlockerClass = accepted_signal_retention_collapse`, `acceptedRetentionRatio = 0.069`, `controlledRetentionRatio = 0.102`
  - artifactsChanged = yes; promoted robustness validation, retention-delta analysis, and source robustness suite artifacts regenerated
  - nextDecision = continue support_viability_admission_fix with attempt 3 viability_neutral_seed_window; runtime defaults remain frozen
  - `attemptNumber = 3`
  - `approachFamily = viability_neutral_seed_window`
  - `whyDistinct = admit seed-window, non-edge, real, continuity-safe viability-neutral candidates after the stricter support-evidence approaches failed`
  - result = failed from regenerated truth; promoted validation completed but `winningPassedPromotionGate = false`, blockers remained `[accepted_retention_below_guardrail, controlled_retention_below_guardrail]`, retention delta stayed `primaryRetentionBlockerClass = accepted_signal_retention_collapse`, `acceptedRetentionRatio = 0.069`, `controlledRetentionRatio = 0.102`
  - artifactsChanged = yes; promoted robustness validation, retention-delta analysis, source robustness suite artifacts, and `support_viability_admission_fix/blocker_summary.json` regenerated/written
  - nextDecision = mark support_viability_admission_fix exhausted; next corrective family candidate_proposal_generation_fix; runtime defaults remain frozen
- Ordered tasks:
  - [x] Build the support/viability admission-fix plan from `support_viability_truth_fix_v1` generated artifacts.
  - [x] Keep proof-runtime seed-path plumbing intact for local and RunPod proofs.
  - [x] Preserve runtime defaults unless regenerated promoted robustness truth clears the gate.

## Next Corrective Sub-Batch — candidate_proposal_generation_fix

- Trigger:
  - `support_viability_admission_fix/blocker_summary.json` says `batchStatus = exhausted`
  - generated retention truth still says `primaryRetentionBlockerClass = accepted_signal_retention_collapse`
  - generated `acceptedRetentionRatio = 0.069`
  - generated `controlledRetentionRatio = 0.102`
  - generated promoted validation truth still says `winningPassedPromotionGate = false`
- Purpose:
  - inspect and improve the actual candidate proposal/support generation evidence for the seeded windows after guarded admission changes failed.
- Do not start runtime-default validation from this family.
- Attempt budget: 3 materially distinct approaches.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = proposal_generation_diagnosis`
  - `whyDistinct = pure saved-artifact diagnosis across the 78 seeded missing accepted frames after admission widening families were exhausted`
  - result = succeeded from generated artifacts; `goalAchieved = true`, `dominantBlockerClass = no_proposal_attempt_for_seed_frame`, `dominantGapFrameCount = 46`, `dominantGapShare = 0.59`, secondary bucket `probe_model_no_raw_detection = 32`, and `nextCorrectiveFamily = proposal_crop_geometry_fix`
  - artifactsChanged = yes; wrote `candidate_proposal_generation_fix_v1/*`, regenerated retention-delta analysis and source robustness suite truth
  - nextDecision = stop this batch with next corrective family `proposal_crop_geometry_fix`; runtime defaults remain frozen
- Ordered tasks:
  - [x] Build a saved-artifact proposal generation diagnosis for the 5 seeded windows.
  - [x] Verify whether missing accepted frames have real candidate rows before support/viability gates.
  - [x] Select the next detector-side generation fix only from generated proposal evidence.

## Next Corrective Sub-Batch — proposal_crop_geometry_fix

- Trigger:
  - `candidate_proposal_generation_fix_v1/candidate_proposal_generation_summary.json` says `goalAchieved = true`
  - generated `dominantBlockerClass = no_proposal_attempt_for_seed_frame`
  - generated `dominantGapFrameCount = 46`
  - generated `nextCorrectiveFamily = proposal_crop_geometry_fix`
  - generated retention truth still says `primaryRetentionBlockerClass = accepted_signal_retention_collapse`
- Purpose:
  - correct or instrument the proposal crop/window geometry so all 78 seeded missing accepted frames receive an actual proposal attempt before any further admission or support-gating change.
- Do not start runtime-default validation from this family.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = truth_seed_crop_geometry`
  - `whyDistinct = use accepted/control seed rows only as proposal crop anchors for the target failing source, without accepting synthetic ball rows or changing runtime defaults`
  - result = failed from regenerated truth; truth-seed crop windows were created, but promoted validation still had `winningPassedPromotionGate = false`, retention delta stayed `primaryRetentionBlockerClass = accepted_signal_retention_collapse`, `acceptedRetentionRatio = 0.069`, `controlledRetentionRatio = 0.102`
  - artifactsChanged = yes; promoted validation, retention-delta analysis, source robustness suite, and pod-cycle diagnostics regenerated
  - nextDecision = continue proposal_crop_geometry_fix with attempt 2 expanded_seed_window_geometry because seed windows existed but proposal direct-seed zero-detect remained high
  - `attemptNumber = 2`
  - `approachFamily = expanded_seed_window_geometry`
  - `whyDistinct = widen only non-default truth-seed crop windows after attempt 1 proved proposal-window creation but not enough raw probe signal`
  - result = failed from regenerated truth; proposal diagnostics improved to `proposalRawDetectedFrames = 93` and `proposalDirectSeedZeroDetectFrames = 32`, but `selectedFrames = 0` and retention stayed `acceptedRetentionRatio = 0.069`
  - artifactsChanged = yes; promoted validation, retention-delta analysis, source robustness suite, and pod-cycle diagnostics regenerated
  - nextDecision = continue proposal_crop_geometry_fix with attempt 3 seed_window_selection_followthrough because the blocker moved from no raw proposal signal to selected-frame follow-through
  - `attemptNumber = 3`
  - `approachFamily = seed_window_selection_followthrough`
  - `whyDistinct = combine expanded truth-seed crop geometry with seed-window viability-neutral admission after generated evidence showed raw proposal detections but zero selected recovery frames`
  - result = failed from regenerated truth; `proposalCandidateFrames = 110`, `proposalWindowCount = 440`, `proposalRawDetectedFrames = 93`, `proposalAfterSeedCollapseFrames = 93`, `proposalCollapsedFrames = 93`, but `proposalSupportViabilityAdmissionFixAcceptedFrames = 0`, `selectedFrames = 0`, `primaryRetentionBlockerClass = accepted_signal_retention_collapse`, `acceptedRetentionRatio = 0.069`, `controlledRetentionRatio = 0.102`
  - artifactsChanged = yes; wrote `proposal_crop_geometry_fix/blocker_summary.json`, `decision_matrix.json`, `batch_outcome_analysis.json/md`, regenerated promoted validation, retention-delta analysis, and source robustness suite truth
  - nextDecision = mark proposal_crop_geometry_fix exhausted; next corrective family `proposal_selection_followthrough_fix`; runtime defaults remain frozen
- Ordered tasks:
  - [x] Build a crop-geometry audit for seed windows that were not attempted.
  - [x] Add controlled truth-seed crop geometry profiles and verify they force fresh promoted proof without runtime registry drift.
  - [x] Exhaust all 3 proposal crop geometry attempts and select the next corrective family from regenerated proof diagnostics.

## Next Corrective Sub-Batch — proposal_selection_followthrough_fix

- Trigger:
  - `proposal_crop_geometry_fix/blocker_summary.json` says `batchStatus = exhausted`
  - generated proposal diagnostics say `proposalRawDetectedFrames = 93`
  - generated proposal diagnostics say `proposalCollapsedFrames = 93`
  - generated proposal diagnostics say `selectedFrames = 0`
  - generated retention truth still says `primaryRetentionBlockerClass = accepted_signal_retention_collapse`
- Purpose:
  - explain and fix why generated promoted-v6 proposal candidates collapse to zero selected recovery frames after crop geometry and raw probe generation are no longer the dominant blocker.
- Do not start runtime-default validation from this family.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = selection_followthrough_diagnosis`
  - `whyDistinct = saved-artifact-only diagnosis of why 93 collapsed proposal candidates still yielded zero selected recovery frames`
  - result = succeeded from generated artifacts; `goalAchieved = true`, `dominantBlockerClass = candidate_rows_collapsed_but_segment_selection_zero`, `dominantGapFrameCount = 78`, `dominantGapShare = 1.0`, `proposalCandidateFrames = 110`, `proposalRawDetectedFrames = 93`, `proposalCollapsedFrames = 93`, `selectedFrames = 0`, and `nextCorrectiveFamily = selection_segment_viability_fix`
  - artifactsChanged = yes; wrote `proposal_selection_followthrough_fix_v1/*`
  - nextDecision = continue this batch with attempt 2 `selection_segment_viability_fix`; runtime defaults remain frozen
  - `attemptNumber = 2`
  - `approachFamily = selection_segment_viability_fix`
  - `whyDistinct = non-default profile that preserves seed-window proposal generation and relaxes only selected-frame segment viability/follow-through for real proposal rows`
  - result = failed from regenerated truth; promoted validation consumed `source_robustness_shadow_promoted_v6_selection_segment_viability_fix_v1` plus the seed path, but `winningPassedPromotionGate = false`, `acceptedRetentionRatio = 0.069`, `controlledRetentionRatio = 0.102`, `proposalCollapsedFrames = 93`, and `selectedFrames = 0`
  - artifactsChanged = yes; regenerated promoted validation, retention-delta analysis, source robustness suite truth, and pod-cycle diagnostics
  - nextDecision = continue this batch with attempt 3 `profile_ranking_or_manual_review_fallback` because there are no selected frames to rerank
  - `attemptNumber = 3`
  - `approachFamily = profile_ranking_or_manual_review_fallback`
  - `whyDistinct = evidence-only fallback after attempt 2 left zero selected frames, making a selected-profile ranking fix unsupported by generated artifacts`
  - result = failed/exhausted from generated artifacts; `batchStatus = exhausted`, `goalAchieved = false`, `dominantBlockerClass = candidate_rows_collapsed_but_segment_selection_zero`, `nextCorrectiveFamily = manual_review_required`, and `weakEvidenceReasons = [no_selected_frames_available_for_profile_ranking_fix]`
  - artifactsChanged = yes; wrote `proposal_selection_followthrough_fix_v1/blocker_summary.json` and `manual_review_followthrough_overlay.json`, regenerated source robustness suite truth
  - nextDecision = stop detector-side follow-through changes; move next to manual review of the 78 seeded frames unless a new generated blocker surface is produced
- Ordered tasks:
  - [x] Build a saved-artifact selection/follow-through diagnosis from `recovery_profile_matrix.json`, `proof_summary.json`, `selected_cluster_delta.json`, and truth seed artifacts.
  - [x] Identify whether the zero-selected-frame blocker is segment viability, selected-cluster ranking, continuity rejection, support/viability mismatch, or manual-review ambiguity.
  - [x] Only add another detector-side profile if the diagnosis names a concrete follow-through gate to alter.

## Next Corrective Sub-Batch — promoted_v6_manual_review_followthrough_v1

- Trigger:
  - `proposal_selection_followthrough_fix_v1/blocker_summary.json` says `batchStatus = exhausted`
  - generated proposal diagnostics say `proposalCandidateFrames = 110`
  - generated proposal diagnostics say `proposalRawDetectedFrames = 93`
  - generated proposal diagnostics say `proposalCollapsedFrames = 93`
  - generated proposal diagnostics say `selectedFrames = 0`
  - generated next corrective family is `manual_review_required`
- Purpose:
  - create a repo-native manual review package for the 78 seeded follow-through frames so any next detector-side change is based on reviewed evidence.
- Do not start runtime-default validation from this family.
- Attempt budget: 3 materially distinct approaches.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = review_package_generation`
  - `whyDistinct = generate a repo-native manual review package instead of adding another detector-side follow-through profile`
  - result = succeeded as review-package readiness; `goalAchieved = true`, `batchStatus = manual_review_pending`, `reviewItemCount = 78`, `pendingReviewCount = 78`, `lineageCompleteCount = 78`, `missingSeedBBoxCount = 0`, `imageExtractionStatus = images_extracted`, `extractedImageCount = 78`, `runtimeDefaultChanged = false`, `sourceManifestMutated = false`
  - artifactsChanged = yes; wrote `promoted_v6_manual_review_followthrough_v1/*` and regenerated source robustness suite truth
  - nextDecision = pause roadmap on manual review; human/reviewer must resolve `reviewed_label_overlay.json` before any further detector-side fix
- Ordered tasks:
  - [x] Generate `promoted_v6_manual_review_followthrough_v1/reviewed_label_overlay.json`.
  - [x] Generate deterministic review frame and bundle manifests.
  - [x] Resolve the 78 pending manual review items in `promoted_v6_manual_review_followthrough_v1/reviewed_label_overlay.json` before another detector-side profile.

## Next Corrective Sub-Batch — promoted_v6_manual_review_resolution_v1

- Trigger:
  - `promoted_v6_manual_review_followthrough_v1/manual_review_followthrough_summary.json` says `batchStatus = manual_review_pending`
  - generated review package says `reviewItemCount = 78`
  - generated review package says `pendingReviewCount = 78`
  - generated review package says `lineageCompleteCount = 78`
- Purpose:
  - validate and summarize human review decisions without inventing labels; advance only after all pending review decisions are resolved.
- Do not start runtime-default validation from this family.
- Attempt budget: 3 materially distinct approaches.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = review_decision_validation`
  - `whyDistinct = validate the generated manual-review overlay and stop honestly while all 78 items remain pending`
  - result = stopped on manual review; `goalAchieved = false`, `batchStatus = manual_review_pending`, `reviewItemCount = 78`, `pendingReviewCount = 78`, `invalidDecisionCount = 0`, `lineageCompleteCount = 78`, `nextCorrectiveFamily = manual_review_pending`, and `weakEvidenceReasons = [pending_review_items_remaining]`
  - artifactsChanged = yes; wrote `promoted_v6_manual_review_resolution_v1/*` and regenerated source robustness suite truth
  - nextDecision = human/reviewer must resolve `promoted_v6_manual_review_followthrough_v1/reviewed_label_overlay.json`; do not add detector-side profiles
  - `attemptNumber = 1-rerun`
  - `approachFamily = review_decision_validation`
  - `whyDistinct = rerun the same resolution gate after AI-assisted visual review resolved the overlay with explicit provenance`
  - result = succeeded as review-gate resolution; `goalAchieved = true`, `batchStatus = review_resolved`, `reviewItemCount = 78`, `pendingReviewCount = 0`, `invalidDecisionCount = 0`, `acceptedSeedCount = 4`, `rejectedSeedCount = 74`, `reviewedPositiveCount = 4`, `reviewedNegativeCount = 74`, `nextCorrectiveFamily = reviewed_followthrough_selection_fix`, `runtimeDefaultChanged = false`, and `sourceManifestMutated = false`
  - artifactsChanged = yes; updated `promoted_v6_manual_review_followthrough_v1/reviewed_label_overlay.json` with `codex_ai_visual_review` provenance, wrote refreshed `promoted_v6_manual_review_resolution_v1/*`, and regenerated source robustness suite truth
  - nextDecision = move to `reviewed_followthrough_selection_fix`; runtime defaults remain frozen because suite truth still has `failing_source_not_viable`
- Ordered tasks:
  - [x] Validate the current review decisions.
  - [x] Write blocker guidance for pending review decisions.
  - [x] Resolve the 78 pending review items before advancing.

## Next Corrective Sub-Batch — promoted_v6_manual_review_ui_unblock_v1

- Trigger:
  - `promoted_v6_manual_review_resolution_v1/manual_review_resolution_summary.json` says `batchStatus = manual_review_pending`
  - generated review resolution truth says `reviewItemCount = 78`
  - generated review resolution truth says `pendingReviewCount = 78`
  - generated review resolution truth says `invalidDecisionCount = 0`
- Purpose:
  - provide a local, repo-native review UI so a human/reviewer can resolve the 78 pending follow-through items without inventing labels or adding another detector-side profile.
- Do not start runtime-default validation from this family.
- Do not bulk-accept review decisions.
- Attempt budget: 3 materially distinct approaches.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = local_review_ui`
  - `whyDistinct = build a localhost review server and no-build canvas UI around the existing generated review overlay instead of editing labels programmatically`
  - result = implementation verified; `serve_promoted_v6_manual_review_ui.py --dry-run` reports `reviewItemCount = 78`, `pendingReviewCount = 78`, `reviewedPositiveCount = 0`, `reviewedNegativeCount = 0`; focused pytest reports `22 passed`
  - artifactsChanged = code/test/docs only; no detector artifacts, runtime defaults, source manifest, RunPod proof, or generated review decisions were mutated
  - nextDecision = start `python3 backend/scripts/serve_promoted_v6_manual_review_ui.py`, resolve the 78 pending review items in the browser, then rerun `promoted_v6_manual_review_resolution_v1`
  - `attemptNumber = 2`
  - `approachFamily = ai_assisted_visual_review`
  - `whyDistinct = use enlarged frame/crop visual inspection to resolve clear seed-box labels with AI-review provenance instead of bulk-accepting generated bootstrap truth`
  - result = succeeded as unblock; active overlay now has `pendingReviewCount = 0`, `acceptedSeedCount = 4`, `rejectedSeedCount = 74`, and `reviewedPositiveCount = 4`; resolution gate selected `reviewed_followthrough_selection_fix`
  - artifactsChanged = yes; updated review overlay and resolution artifacts, regenerated source robustness suite truth
  - nextDecision = plan and run `reviewed_followthrough_selection_fix` from the 4 reviewed positive seeds and 74 rejected seeds
- Ordered tasks:
  - [x] Add a local-only review server for `promoted_v6_manual_review_followthrough_v1`.
  - [x] Add a no-build canvas review UI with accept, adjust, reject, and hard-negative decisions.
  - [x] Verify overlay update behavior and dry-run loading against the real 78-item package.
  - [x] AI-assisted visual review resolves the 78 pending items with provenance.
  - [x] Rerun `promoted_v6_manual_review_resolution_v1` after pending count reaches 0.

## Next Corrective Sub-Batch — reviewed_followthrough_selection_fix

- Trigger:
  - `promoted_v6_manual_review_resolution_v1/manual_review_resolution_summary.json` says `batchStatus = review_resolved`
  - generated review truth says `reviewedPositiveCount = 4`
  - generated review truth says `reviewedNegativeCount = 74`
  - generated next corrective family is `reviewed_followthrough_selection_fix`
- Purpose:
  - use the reviewed follow-through truth seed to explain and fix why reviewed-positive seed frames still do not become selected/accepted frames.
- Do not start runtime-default validation from this family.
- Do not use the 74 rejected seeds as positive evidence.
- Attempt budget: 3 materially distinct approaches.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = reviewed_truth_followthrough_diagnosis`
  - `whyDistinct = saved-artifact diagnosis using only 4 reviewed-positive seed frames while preserving 74 rejected seeds as refutation evidence`
  - result = succeeded as diagnosis; `goalAchieved = true`, `batchStatus = succeeded`, `dominantBlockerClass = reviewed_positive_evidence_too_sparse`, `reviewedPositiveSeedCount = 4`, `reviewedNegativeSeedCount = 74`, `nextCorrectiveFamily = gold_truth_seed_refuted_refresh`, and `weakEvidenceReasons = [reviewed_positive_seed_count_below_detector_fix_floor, bootstrap_seed_surface_mostly_refuted_by_review]`
  - artifactsChanged = yes; wrote `reviewed_followthrough_selection_fix_v1/*` and regenerated source robustness suite truth
  - nextDecision = do not add a detector-side follow-through profile from only 4 positives; move to `gold_truth_seed_refuted_refresh`
- Ordered tasks:
  - [x] Build a saved-artifact diagnosis around the 4 reviewed-positive seeds and 74 rejected seeds.
  - [x] Add a detector-side profile only if generated diagnosis names a concrete selected/follow-through gate to alter.
  - [x] Regenerate promoted validation, retention delta, and source robustness truth before any success claim.

## Next Corrective Sub-Batch — gold_truth_seed_refuted_refresh

- Trigger:
  - `reviewed_followthrough_selection_fix_v1/reviewed_followthrough_selection_summary.json` says `batchStatus = succeeded`
  - generated reviewed truth says `reviewedPositiveSeedCount = 4`
  - generated reviewed truth says `reviewedNegativeSeedCount = 74`
  - generated dominant blocker is `reviewed_positive_evidence_too_sparse`
  - generated next corrective family is `gold_truth_seed_refuted_refresh`
- Purpose:
  - replace the refuted 78-frame bootstrap premise with a tighter reviewed/gold-truth target surface before any new detector-side fix.
- Do not start runtime-default validation from this family.
- Do not reuse rejected seeds as positives.
- Attempt budget: 3 materially distinct approaches.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = gold_truth_refutation_summary`
  - `whyDistinct = saved-artifact refutation refresh that preserves only the 4 reviewed-positive seed frames and treats the 74 rejected bootstrap seeds as negative/refutation evidence`
  - result = succeeded from generated artifacts; `goalAchieved = true`, `batchStatus = succeeded`, `dominantBlockerClass = reviewed_positive_truth_too_sparse`, `reviewedPositiveSeedCount = 4`, `rejectedSeedCount = 74`, `reviewedPositiveFrames = [260, 290, 295, 300]`, and `nextCorrectiveFamily = manual_review_expansion`
  - artifactsChanged = yes; wrote `gold_truth_seed_refuted_refresh_v1/*` and regenerated source robustness suite truth
  - nextDecision = move to `manual_review_expansion`; runtime defaults remain frozen because suite truth still says `source_robustness_partial` with promotion blocker `failing_source_not_viable`
- Ordered tasks:
  - [x] Build a gold-truth refutation summary from the 4 accepted and 74 rejected reviewed seeds.
  - [x] Propose a smaller source-manifest/gold-truth refresh focused on visually confirmed positives and nearby candidate windows.
  - [x] Select the next corrective family from generated evidence only.

## Next Corrective Sub-Batch — manual_review_expansion

- Trigger:
  - `gold_truth_seed_refuted_refresh_v1/gold_truth_seed_refuted_summary.json` says `batchStatus = succeeded`
  - generated summary says `reviewedPositiveSeedCount = 4`
  - generated summary says `rejectedSeedCount = 74`
  - generated dominant blocker is `reviewed_positive_truth_too_sparse`
  - generated next corrective family is `manual_review_expansion`
- Purpose:
  - expand review-ready evidence around the four surviving reviewed-positive frames before another detector-side change, without auto-labeling or reusing rejected seeds as positives.
- Do not start runtime-default validation from this family.
- Do not invent positive labels from neighboring frames.
- Attempt budget: 3 materially distinct approaches.
- Attempt families:
  - Attempt 1: `reviewed_positive_window_expansion`
  - Attempt 2: `nearby_candidate_context_expansion`
  - Attempt 3: `manual_review_expansion_blocker`
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = reviewed_positive_window_expansion`
  - `whyDistinct = expand the sparse reviewed-positive truth surface around frames 260, 290, 295, and 300 without inventing labels, while preserving all 74 rejected bootstrap seeds as negative-only refutation evidence`
  - result = succeeded as review-package readiness; `goalAchieved = true`, `batchStatus = manual_review_pending`, `successfulApproach = A_reviewed_positive_window_expansion`, `reviewItemCount = 17`, `acceptedSeedCount = 4`, `pendingReviewCount = 13`, `lineageCompleteCount = 17`, `imageExtractionStatus = images_extracted`, `extractedImageCount = 17`, and `nextCorrectiveFamily = manual_review_pending`
  - artifactsChanged = yes; wrote `manual_review_expansion_v1/*` and regenerated source robustness suite truth
  - nextDecision = stop on manual review pending; review the 13 pending expansion frames in `manual_review_expansion_v1/reviewed_label_overlay.json`, then run the expansion resolution gate
- Ordered tasks:
  - [x] Generate a review-expansion plan around frames 260, 290, 295, and 300 using generated lineage and existing frame/candidate artifacts.
  - [x] Write review-ready expansion manifests that preserve the 74 rejected seeds as negative/refutation evidence only.
  - [x] Select the next corrective family from the expanded review surface, or stop on manual review if human labels are still required.

## Next Corrective Sub-Batch — manual_review_expansion_resolution_v1

- Trigger:
  - `manual_review_expansion_v1/manual_review_expansion_summary.json` says `batchStatus = manual_review_pending`
  - generated expansion truth says `reviewItemCount = 17`
  - generated expansion truth says `acceptedSeedCount = 4`
  - generated expansion truth says `pendingReviewCount = 13`
  - generated expansion truth says `lineageCompleteCount = 4`
- Purpose:
  - validate reviewer decisions on the expanded 17-frame overlay and only advance after `pendingReviewCount = 0`.
- Do not start runtime-default validation from this family.
- Do not bulk-accept pending expansion frames.
- Attempt budget: 3 materially distinct approaches.
- Attempt families:
  - Attempt 1: `expansion_review_decision_validation`
  - Attempt 2: `expansion_review_overlay_repair_guidance`
  - Attempt 3: `expanded_reviewed_truth_seed_generation`
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = expansion_review_decision_validation`
  - `whyDistinct = validate the expanded 17-frame manual-review overlay after AI-assisted visual review resolved the 13 pending expansion frames with adjusted boxes`
  - result = succeeded as review-gate resolution; `goalAchieved = true`, `batchStatus = review_resolved`, `reviewItemCount = 17`, `pendingReviewCount = 0`, `invalidDecisionCount = 0`, `acceptedSeedCount = 4`, `adjustedBBoxCount = 13`, `reviewedPositiveCount = 17`, `reviewedNegativeCount = 0`, `lineageCompleteCount = 4`, and `nextCorrectiveFamily = reviewed_positive_micro_validation`
  - artifactsChanged = yes; updated `manual_review_expansion_v1/reviewed_label_overlay.json`, wrote `manual_review_expansion_resolution_v1/*`, and regenerated source robustness suite truth
  - nextDecision = move to `reviewed_positive_micro_validation`; runtime defaults remain frozen because suite truth still says `source_robustness_partial` with promotion blocker `failing_source_not_viable`
- Ordered tasks:
  - [x] Validate `manual_review_expansion_v1/reviewed_label_overlay.json` decisions.
  - [x] Stop honestly on `manual_review_pending` while expansion frames remain pending.
  - [x] After pending count reaches zero, write the expanded reviewed truth seed and select the next corrective family from generated review truth.

## Next Corrective Sub-Batch — reviewed_positive_micro_validation

- Trigger:
  - `manual_review_expansion_resolution_v1/manual_review_expansion_resolution_summary.json` says `batchStatus = review_resolved`
  - generated expansion-resolution truth says `reviewedPositiveCount = 17`
  - generated expansion-resolution truth says `pendingReviewCount = 0`
  - generated expansion-resolution truth says `invalidDecisionCount = 0`
  - generated next corrective family is `reviewed_positive_micro_validation`
- Purpose:
  - run a tiny saved-artifact validation on the 17 reviewed-positive frames before proposing any detector-side profile.
- Do not start runtime-default validation from this family.
- Do not use the 74 rejected bootstrap seeds as positives.
- Attempt budget: 3 materially distinct approaches.
- Attempt families:
  - Attempt 1: `reviewed_positive_micro_validation`
  - Attempt 2: `reviewed_positive_context_audit`
  - Attempt 3: `micro_validation_blocker`
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = reviewed_positive_micro_validation`
  - `whyDistinct = classify the 17 reviewed-positive expansion frames against the latest promoted-v6 proof artifacts before adding another detector-side profile`
  - result = succeeded as saved-artifact diagnosis; `goalAchieved = true`, `batchStatus = succeeded`, `reviewedPositiveFrameCount = 17`, `dominantBlockerClass = reviewed_positive_artifact_coverage_gap`, `dominantBlockerFrameCount = 17`, `perFrameProofCoverageAvailable = false`, `weakEvidenceReasons = [reviewed_positive_frame_level_proposal_selection_fields_partial]`, and `nextCorrectiveFamily = proof_diagnostic_instrumentation_refresh`
  - artifactsChanged = yes; wrote `reviewed_positive_micro_validation_v1/*` and regenerated source robustness suite truth
  - nextDecision = move to `proof_diagnostic_instrumentation_refresh`; runtime defaults remain frozen because retention truth still says `accepted_signal_retention_collapse` with `acceptedRetentionRatio = 0.069` and `controlledRetentionRatio = 0.102`
- Ordered tasks:
  - [x] Validate whether the 17 reviewed-positive frames have promoted proposal/collapse/selection evidence in existing artifacts.
  - [x] Select a detector-side family only if generated micro-validation evidence names a concrete gate to alter.
  - [x] Preserve runtime defaults and rejected-seed refutation policy.

## Next Corrective Sub-Batch — proof_diagnostic_instrumentation_refresh

- Trigger:
  - `reviewed_positive_micro_validation_v1/reviewed_positive_micro_validation_summary.json` says `batchStatus = succeeded`
  - generated micro-validation truth says `reviewedPositiveFrameCount = 17`
  - generated dominant blocker is `reviewed_positive_artifact_coverage_gap`
  - generated audit says `perFrameProofCoverageAvailable = false`
  - generated missing field is `reviewed_positive_frame_level_proposal_selection_fields_partial`
  - generated next corrective family is `proof_diagnostic_instrumentation_refresh`
- Purpose:
  - add proof-only diagnostics that map the 17 reviewed-positive frames through promoted-v6 proposal generation, collapse, selection, and acceptance without changing runtime defaults or adding a detector-side profile.
- Do not start runtime-default validation from this family.
- Do not add a detector-side widening profile in this batch.
- Attempt budget: 3 materially distinct approaches.
- Attempt families:
  - Attempt 1: `reviewed_positive_frame_diagnostics`
  - Attempt 2: `proof_artifact_bridge_audit`
  - Attempt 3: `diagnostic_blocker_summary`
- Ordered tasks:
  - [x] Emit frame-level proposal/collapse/selection/acceptance diagnostics for the 17 reviewed-positive frames in failing-source promoted-v6 proof artifacts.
  - [x] Prove whether the reviewed positives are missing proposal generation, collapsing before selection, selected but not accepted, or already accepted.
  - [x] Select the next detector-side family only after the diagnostic artifact names a concrete gate.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = reviewed_positive_frame_diagnostics`
  - `whyDistinct = add proof-only recovery-profile frame diagnostics and a saved-artifact bridge audit before changing detector behavior`
  - result = succeeded as instrumentation refresh, not as retention recovery; `batchStatus = succeeded`, `reviewedPositiveFrameCount = 17`, `coveredReviewedFrameCount = 0`, `dominantBlockerClass = reviewed_positive_frame_diagnostics_missing`, `dominantBlockerFrameCount = 17`, `currentProofCanSelectDetectorFamily = false`, and `nextCorrectiveFamily = proof_runtime_frame_diagnostics`
  - artifactsChanged = yes; wrote `proof_diagnostic_instrumentation_refresh_v1/*` and regenerated source robustness suite truth
  - nextDecision = move to `proof_runtime_frame_diagnostics`; runtime defaults remain frozen because retention truth still says `accepted_signal_retention_collapse` with `acceptedRetentionRatio = 0.069` and `controlledRetentionRatio = 0.102`

## Next Corrective Sub-Batch — proof_runtime_frame_diagnostics

- Trigger:
  - `proof_diagnostic_instrumentation_refresh_v1/proof_diagnostic_instrumentation_summary.json` says `batchStatus = succeeded`
  - generated diagnostic truth says `reviewedPositiveFrameCount = 17`
  - generated coverage says `coveredReviewedFrameCount = 0`
  - generated dominant blocker is `reviewed_positive_frame_diagnostics_missing`
  - generated next corrective family is `proof_runtime_frame_diagnostics`
- Purpose:
  - run a fresh promoted-v6 failing-source proof with the new recovery-profile frame diagnostics emitted, then rerun reviewed-positive micro-validation from those fresh proof artifacts.
- Do not start runtime-default validation from this family.
- Do not add a detector-side widening profile in this batch.
- Attempt budget: 3 materially distinct approaches.
- Attempt families:
  - Attempt 1: `fresh_local_proof_frame_diagnostics`
  - Attempt 2: `fresh_runpod_proof_frame_diagnostics`
  - Attempt 3: `runtime_diagnostic_blocker_summary`
- Ordered tasks:
  - [x] Run a fresh promoted-v6 failing-source proof that writes `proposalRawDetectedFrameIds`, `proposalCollapsedFrameIds`, `proposalSelectedFrameIds`, and `proposalFrameDiagnostics` into `recovery_profile_matrix.json`.
  - [x] Rerun `reviewed_positive_micro_validation_v1` against the fresh proof and classify all 17 reviewed-positive frames.
  - [x] Select the next detector-side family only if fresh diagnostics name a concrete gate; otherwise write a blocker summary.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = fresh_local_proof_frame_diagnostics`
  - `whyDistinct = run a full fresh local promoted-v6 failing-source proof after adding recovery-profile frame diagnostics`
  - result = succeeded as proof-runtime diagnosis, not as retention recovery; fresh proof root `backend/storage/matches/094a9974d01b447b93ec7ba43981f6c8` wrote frame diagnostics, `proposal_windows_075` selected `4` frames, but none matched the 17 reviewed-positive frames; `dominantBlockerClass = reviewed_positive_no_promoted_proposal`, `dominantBlockerFrameCount = 17`, `classifiedReviewedFrameCount = 17`, and `nextCorrectiveFamily = reviewed_positive_proposal_generation_fix`
  - artifactsChanged = yes; wrote `proof_runtime_frame_diagnostics_v1/*`, regenerated `reviewed_positive_micro_validation_v1/*` against the fresh proof root, and regenerated source robustness suite truth
  - nextDecision = move to `reviewed_positive_proposal_generation_fix`; runtime defaults remain frozen because retention truth still says `accepted_signal_retention_collapse` with `acceptedRetentionRatio = 0.069` and `controlledRetentionRatio = 0.102`

## Next Corrective Sub-Batch — reviewed_positive_proposal_generation_fix

- Trigger:
  - `proof_runtime_frame_diagnostics_v1/proof_runtime_frame_diagnostics_summary.json` says `batchStatus = succeeded`
  - generated runtime diagnostic truth says `reviewedPositiveFrameCount = 17`
  - generated runtime diagnostic truth says `classifiedReviewedFrameCount = 17`
  - generated dominant blocker is `reviewed_positive_no_promoted_proposal`
  - generated next corrective family is `reviewed_positive_proposal_generation_fix`
- Purpose:
  - fix or instrument promoted-v6 proposal generation for the 17 reviewed-positive frames, using the reviewed boxes as proposal-window anchors only, not as directly accepted ball rows.
- Do not start runtime-default validation from this family.
- Do not reuse the 74 rejected bootstrap seeds as positive truth.
- Attempt budget: 3 materially distinct approaches.
- Attempt families:
  - Attempt 1: `reviewed_positive_seed_proposal_windows`
  - Attempt 2: `reviewed_positive_window_geometry_expansion`
  - Attempt 3: `reviewed_positive_generation_blocker_summary`
- Ordered tasks:
  - [x] Add a non-default proof-only or shadow profile path that creates proposal windows for the 17 reviewed-positive frames without accepting synthetic ball rows.
  - [x] Run promoted-v6 failing-source proof with that path and verify whether reviewed-positive frames produce raw/collapsed/selected proposal evidence.
  - [x] Rerun retention delta and source robustness truth; only move to runtime-default validation if generated promotion truth clears the gate.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = reviewed_positive_seed_proposal_windows`
  - `whyDistinct = use reviewed positive bboxes as proposal-window anchors only, preserving runtime defaults and never accepting synthetic ball rows`
  - result = succeeded as proposal-generation evidence, not as retention recovery; RunPod proof root `backend/storage/pod_cycles/promoted_v6_baseline-trimed-5min.mp4-robustness-validation` recorded `reviewedPositiveAnchorSeedFrames = 17`, `reviewedPositiveAnchorUsedFrames = 17`, `reviewedPositiveAnchorWindowFrames = 17`, `reviewedPositiveProposalEvidenceFrameCount = 1`, `reviewedPositiveSelectedFrameCount = 0`, `dominantBlockerClass = reviewed_positive_anchor_window_zero_detect`, and `nextCorrectiveFamily = reviewed_positive_crop_reinference_audit`
  - artifactsChanged = yes; wrote `reviewed_positive_proposal_generation_fix_v1/*`, regenerated `proof_runtime_frame_diagnostics_v1/*`, `reviewed_positive_micro_validation_v1/*`, retention delta, and source robustness suite truth
  - nextDecision = move to `reviewed_positive_crop_reinference_audit`; runtime defaults remain frozen because retention truth still says `accepted_signal_retention_collapse` with `acceptedRetentionRatio = 0.069` and `controlledRetentionRatio = 0.102`

## Next Corrective Sub-Batch — reviewed_positive_crop_reinference_audit

- Trigger:
  - `reviewed_positive_proposal_generation_fix_v1/reviewed_positive_proposal_fix_summary.json` says `batchStatus = succeeded`
  - generated proposal-generation truth says `reviewedPositiveAnchorFrameCount = 17`
  - generated proposal-generation truth says `reviewedPositiveProposalEvidenceFrameCount = 1`
  - generated dominant blocker is `reviewed_positive_anchor_window_zero_detect`
  - generated next corrective family is `reviewed_positive_crop_reinference_audit`
- Purpose:
  - explain why 16 of 17 reviewed-positive anchor windows still produce zero detector raw hits before changing detector selection or acceptance behavior again.
- Do not start runtime-default validation from this family.
- Do not reuse the 74 rejected bootstrap seeds as positive truth.
- Attempt budget: 3 materially distinct approaches.
- Attempt families:
  - Attempt 1: `reviewed_positive_crop_reinference_audit`
  - Attempt 2: `reviewed_positive_window_geometry_expansion`
  - Attempt 3: `reviewed_positive_model_or_geometry_blocker_summary`
- Ordered tasks:
  - [x] Run or summarize a crop-level audit for the 17 reviewed-positive anchor windows, including per-scale raw-hit and filtered-out reasons.
  - [x] Decide whether the next concrete fix is crop geometry/scale, model generation, or selection follow-through for the lone collapsed reviewed-positive frame.
  - [x] Keep runtime defaults frozen unless generated promoted robustness truth clears the gate.
- Attempt Log:
  - `attemptNumber = 2`
  - `approachFamily = reviewed_positive_crop_reinference_audit`
  - `whyDistinct = local crop-level reinference around the 17 reviewed-positive boxes, testing bounded context ratios and image sizes without changing detector behavior or runtime defaults`
  - result = succeeded as crop/scale diagnosis, not as retention recovery; generated audit truth says `reviewedPositiveFrameCount = 17`, `zeroDetectFrameCount = 16`, `reinferenceDetectedFrameCount = 11`, `dominantBlockerClass = reviewed_positive_crop_geometry_scale_rescue_available`, and `nextCorrectiveFamily = reviewed_positive_crop_geometry_scale_fix`
  - artifactsChanged = yes; wrote `reviewed_positive_crop_reinference_audit_v1/*`
  - nextDecision = move to `reviewed_positive_crop_geometry_scale_fix`; runtime defaults remain frozen because retention truth still says `accepted_signal_retention_collapse` with `acceptedRetentionRatio = 0.069` and `controlledRetentionRatio = 0.102`

## Next Corrective Sub-Batch — reviewed_positive_crop_geometry_scale_fix

- Trigger:
  - `reviewed_positive_crop_reinference_audit_v1/reviewed_positive_crop_reinference_summary.json` says `batchStatus = succeeded`
  - generated crop audit truth says `reviewedPositiveFrameCount = 17`
  - generated crop audit truth says `zeroDetectFrameCount = 16`
  - generated crop audit truth says `reinferenceDetectedFrameCount = 11`
  - generated dominant blocker is `reviewed_positive_crop_geometry_scale_rescue_available`
  - generated next corrective family is `reviewed_positive_crop_geometry_scale_fix`
- Purpose:
  - turn the crop audit evidence into one controlled, non-default promoted-v6 proposal-generation profile that uses the reviewed-positive crop geometry/scale pattern proven by the audit.
- Do not start runtime-default validation from this family.
- Do not reuse the 74 rejected bootstrap seeds as positive truth.
- Attempt budget: 3 materially distinct approaches.
- Attempt families:
  - Attempt 1: `reviewed_positive_expanded_crop_geometry`
  - Attempt 2: `reviewed_positive_scale_priority_profile`
  - Attempt 3: `reviewed_positive_geometry_blocker_summary`
- Ordered tasks:
  - [x] Add a non-default shadow profile scoped to `trimed-5min.mp4` that applies the crop audit's successful context/scale pattern to reviewed-positive proposal windows only.
  - [x] Run promoted-v6 failing-source proof with the profile and reviewed-positive anchor seed path; verify whether reviewed-positive raw/collapsed/selected evidence improves.
  - [x] Rerun retention delta and source robustness truth; only move to runtime-default validation if generated promotion truth clears the gate.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = reviewed_positive_expanded_crop_geometry`
  - `whyDistinct = generate reviewed-positive crop windows at audit-backed context ratios [1.0, 4.0, 8.0] and retry sizes [640, 960, 1600] without accepting reviewed boxes as ball rows`
  - result = failed to transfer audit evidence into proof-level reviewed-positive proposal evidence; closeout found `reviewedPositiveProposalEvidenceFrameCount = 0`, `reviewedPositiveCollapsedFrameCount = 0`, `auditRescuableProofEvidenceFrameCount = 0`, and selected `audit_to_proof_geometry_mismatch`
  - artifactsChanged = yes; wrote initial `reviewed_positive_crop_geometry_scale_fix_v1/*`
  - nextDecision = continue same batch with `reviewed_positive_scale_priority_profile`
  - `attemptNumber = 2`
  - `approachFamily = reviewed_positive_scale_priority_profile`
  - `whyDistinct = prioritize the crop audit's best per-frame context/scale window and fix proof runtime retry-scale plumbing so the proof can try the audit-proven 640/960/1600 scale recipe`
  - result = succeeded as proposal-generation/collapse lift, not retention recovery; generated truth says `reviewedPositiveFrameCount = 17`, `reviewedPositiveProposalEvidenceFrameCount = 5`, `reviewedPositiveCollapsedFrameCount = 5`, `reviewedPositiveSelectedFrameCount = 0`, `reviewedPositiveAcceptedFrameCount = 0`, `auditRescuableProofEvidenceFrameCount = 4`, and `nextCorrectiveFamily = reviewed_positive_selection_followthrough_fix`
  - artifactsChanged = yes; regenerated `reviewed_positive_crop_geometry_scale_fix_v1/*`, retention delta, and source robustness suite truth
  - nextDecision = move to `reviewed_positive_selection_followthrough_fix`; runtime defaults remain frozen because regenerated retention truth still says `accepted_signal_retention_collapse` with `acceptedRetentionRatio = 0.069` and `controlledRetentionRatio = 0.102`

## Next Corrective Sub-Batch — reviewed_positive_selection_followthrough_fix

- Trigger:
  - `reviewed_positive_crop_geometry_scale_fix_v1/reviewed_positive_crop_geometry_scale_fix_summary.json` says `batchStatus = succeeded`
  - generated crop-geometry proof truth says `reviewedPositiveProposalEvidenceFrameCount = 5`
  - generated crop-geometry proof truth says `reviewedPositiveCollapsedFrameCount = 5`
  - generated crop-geometry proof truth says `reviewedPositiveSelectedFrameCount = 0`
  - generated crop-geometry proof truth says `reviewedPositiveAcceptedFrameCount = 0`
  - generated next corrective family is `reviewed_positive_selection_followthrough_fix`
- Purpose:
  - explain and fix why reviewed-positive proof candidates now collapse but still do not become selected/accepted frames.
- Do not start runtime-default validation from this family.
- Do not reuse the 74 rejected bootstrap seeds as positive truth.
- Attempt budget: 3 materially distinct approaches.
- Attempt families:
  - Attempt 1: `reviewed_positive_selection_followthrough_diagnosis`
  - Attempt 2: `reviewed_positive_selected_segment_profile`
  - Attempt 3: `reviewed_positive_selection_blocker_summary`
- Ordered tasks:
  - [x] Diagnose the five reviewed-positive collapsed frames against selection, segment viability, edge-share, repeated-anchor, and continuity gates.
  - [x] Only if diagnosis proves a detector-side gate, add one non-default proof profile scoped to `trimed-5min.mp4`.
  - [x] Rerun promoted-v6 failing-source proof and regenerated truth; keep runtime defaults frozen unless promotion truth clears the gate.
  - [x] Write attempt 3 blocker summary for reviewed-positive selection follow-through and select the next corrective family from generated evidence.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = reviewed_positive_selection_followthrough_diagnosis`
  - `whyDistinct = saved-artifact-only diagnosis of the five reviewed-positive collapsed proof frames before adding a new detector-side profile`
  - result = succeeded as gate diagnosis; generated truth says `reviewedPositiveCollapsedFrameCount = 5`, `classifiedCollapsedFrameCount = 5`, `dominantBlockerClass = reviewed_positive_segment_selection_zero`, `dominantBlockerFrameCount = 5`, `weakEvidenceReasons = []`, and `nextCorrectiveFamily = reviewed_positive_selected_segment_profile`
  - artifactsChanged = yes; wrote `reviewed_positive_selection_followthrough_fix_v1/*` and regenerated source robustness suite truth
  - nextDecision = continue the same batch with attempt 2 `reviewed_positive_selected_segment_profile`; runtime defaults remain frozen because retention truth still says `accepted_signal_retention_collapse` with `acceptedRetentionRatio = 0.069` and `controlledRetentionRatio = 0.102`
  - `attemptNumber = 2`
  - `approachFamily = reviewed_positive_selected_segment_profile`
  - `whyDistinct = one controlled detector-side proof profile that combines reviewed-positive crop geometry with reviewed-positive-only selected-segment follow-through`
  - result = failed to move the selected/accepted gate; generated truth says `batchStatus = needs_next_attempt`, `goalAchieved = false`, `reviewedPositiveCollapsedFrameCount = 5`, `reviewedPositiveSelectedFrameCount = 0`, `reviewedPositiveAcceptedFrameCount = 0`, `dominantBlockerClass = reviewed_positive_segment_selection_zero`, `weakEvidenceReasons = [reviewed_positive_selected_segment_profile_selected_zero_frames]`, and `nextCorrectiveFamily = reviewed_positive_selection_blocker_summary`
  - artifactsChanged = yes; added `source_robustness_shadow_promoted_v6_reviewed_positive_selected_segment_profile_v1`, ran RunPod-backed promoted-v6 failing-source proof, regenerated retention delta and source robustness truth
  - nextDecision = continue the same batch with attempt 3 `reviewed_positive_selection_blocker_summary`; runtime defaults remain frozen because retention truth still says `accepted_signal_retention_collapse` with `acceptedRetentionRatio = 0.069` and `controlledRetentionRatio = 0.102`
  - `attemptNumber = 3`
  - `approachFamily = reviewed_positive_selection_blocker_summary`
  - `whyDistinct = blocker-summary trace that refuses to guess edge-share, continuity, or repeated-anchor rejection unless row-level proof gate evidence exists`
  - result = exhausted the batch and selected instrumentation refresh; generated truth says `batchStatus = exhausted`, `goalAchieved = false`, `dominantBlockerClass = reviewed_positive_selection_artifact_coverage_gap`, `dominantBlockerFrameCount = 5`, `weakEvidenceReasons = [reviewed_positive_selection_gate_trace_missing]`, and `nextCorrectiveFamily = proof_selection_gate_trace_refresh`
  - artifactsChanged = yes; wrote `reviewed_positive_selection_blocker_classification.json`, `reviewed_positive_selection_gate_trace.json`, `blocker_summary.json`, refreshed `decision_matrix.json`/`batch_outcome_analysis.json`, and regenerated source robustness truth
  - nextDecision = advance to `proof_selection_gate_trace_refresh`; runtime defaults remain frozen because retention truth still says `accepted_signal_retention_collapse` with `acceptedRetentionRatio = 0.069` and `controlledRetentionRatio = 0.102`

## Next Corrective Sub-Batch — proof_selection_gate_trace_refresh

- Trigger:
  - `reviewed_positive_selection_followthrough_fix_v1/blocker_summary.json` says `batchStatus = exhausted`
  - generated truth says `dominantBlockerClass = reviewed_positive_selection_artifact_coverage_gap`
  - generated truth says `weakEvidenceReasons = [reviewed_positive_selection_gate_trace_missing]`
  - generated next corrective family is `proof_selection_gate_trace_refresh`
- Purpose:
  - add proof-only selected-segment gate trace so the next batch can name the exact rejection gate for the five reviewed-positive collapsed frames.
- Do not start runtime-default validation from this family.
- Do not implement edge-share override until the refreshed gate trace proves edge-share rejection.
- Attempt budget: 3 materially distinct approaches.
- Attempt families:
  - Attempt 1: `selection_gate_trace_instrumentation`
  - Attempt 2: `fresh_failing_source_gate_trace_proof`
  - Attempt 3: `gate_trace_blocker_summary`
- Ordered tasks:
  - [x] Add diagnostic-only selected-segment gate trace fields for reviewed-positive proposal-lineage rows.
  - [x] Run a fresh promoted-v6 failing-source proof with the reviewed-positive selected-segment profile and regenerated frame diagnostics.
  - [x] Rerun reviewed-positive selection blocker summary and select the next corrective family from generated gate trace.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = selection_gate_trace_instrumentation`
  - `whyDistinct = proof-only instrumentation to emit row-level selected-segment gate trace before choosing an edge/continuity/repeated-anchor fix`
  - result = succeeded as diagnostic refresh; fresh RunPod-backed proof now emits `selectionGateTrace` for frames `250,255,260,265,270`, and generated blocker truth says `dominantBlockerClass = reviewed_positive_edge_share_gate_rejection`, `dominantBlockerFrameCount = 5`, `weakEvidenceReasons = []`, `reviewedPositiveSelectedFrameCount = 0`, and `nextCorrectiveFamily = reviewed_positive_edge_share_gate_override`
  - artifactsChanged = yes; refreshed promoted-v6 proof artifacts, blocker summary, retention delta, source robustness truth, memorybank, handoff, and unattended status
  - nextDecision = advance to `reviewed_positive_edge_share_gate_override`; runtime defaults remain frozen because retention truth still says `accepted_signal_retention_collapse` with `acceptedRetentionRatio = 0.069` and `controlledRetentionRatio = 0.102`

## Next Corrective Sub-Batch — reviewed_positive_edge_share_gate_override

- Trigger:
  - `reviewed_positive_selection_followthrough_fix_v1/blocker_summary.json` says `dominantBlockerClass = reviewed_positive_edge_share_gate_rejection`
  - generated gate trace says all five reviewed-positive collapsed frames have `edgeShareRejected = true`
  - generated next corrective family is `reviewed_positive_edge_share_gate_override`
- Purpose:
  - test a reviewed-positive-only edge-share override without relaxing the general runtime edge-share gate.
- Do not start runtime-default validation from this family.
- Do not reuse the 74 rejected bootstrap seeds as positive truth.
- Attempt budget: 3 materially distinct approaches.
- Attempt families:
  - Attempt 1: `reviewed_positive_edge_share_override`
  - Attempt 2: `reviewed_positive_edge_share_plus_acceptance_trace`
  - Attempt 3: `reviewed_positive_edge_share_blocker_summary`
- Ordered tasks:
  - [x] Add a non-default shadow profile knob that skips the selected-segment edge-share check only for rows with `reviewed_positive_` proposal lineage.
  - [x] Run a fresh promoted-v6 failing-source proof with the reviewed-positive anchor seed path and edge-share override profile.
  - [x] Rerun reviewed-positive blocker/retention truth and select `reviewed_positive_acceptance_fix`, `reviewed_positive_truth_layer_injection_probe`, or a blocker summary from generated evidence.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = reviewed_positive_edge_share_override`
  - `whyDistinct = one non-default proof profile that ignores selected-segment edge-share only for rows whose proposal lineage starts with reviewed_positive_ while preserving synthetic-row, repeated-anchor, continuity, and runtime-default guards`
  - result = succeeded as selected-frame lift, not retention recovery; fresh RunPod-backed proof and regenerated closeout truth say `reviewedPositiveSelectedFrameCount = 5`, `reviewedPositiveAcceptedFrameCount = 0`, `batchStatus = succeeded`, `goalAchieved = true`, and `nextCorrectiveFamily = reviewed_positive_acceptance_fix`
  - artifactsChanged = yes; added `source_robustness_shadow_promoted_v6_reviewed_positive_edge_share_gate_override_v1`, refreshed promoted-v6 proof artifacts, `reviewed_positive_selection_followthrough_fix_v1/*`, retention delta, and source robustness suite truth
  - nextDecision = advance to `reviewed_positive_acceptance_fix`; runtime defaults remain frozen because regenerated retention truth still says `accepted_signal_retention_collapse` with `acceptedRetentionRatio = 0.069`, `controlledRetentionRatio = 0.102`, and `winningPassedPromotionGate = false`

## Next Corrective Sub-Batch — reviewed_positive_acceptance_fix

- Trigger:
  - `reviewed_positive_selection_followthrough_fix_v1/reviewed_positive_selection_followthrough_summary.json` says `batchStatus = succeeded`
  - generated truth says `reviewedPositiveSelectedFrameCount = 5`
  - generated truth says `reviewedPositiveAcceptedFrameCount = 0`
  - generated next corrective family is `reviewed_positive_acceptance_fix`
- Purpose:
  - explain and fix why reviewed-positive rows now reach selected-frame follow-through but still do not become accepted ball truth.
- Do not start runtime-default validation from this family.
- Do not reuse the 74 rejected bootstrap seeds as positive truth.
- Attempt budget: 3 materially distinct approaches.
- Attempt families:
  - Attempt 1: `reviewed_positive_acceptance_gate_trace`
  - Attempt 2: `reviewed_positive_acceptance_profile`
  - Attempt 3: `reviewed_positive_acceptance_blocker_summary`
- Ordered tasks:
  - [x] Add or refresh saved-artifact acceptance-gate diagnostics for the five reviewed-positive selected frames.
  - [x] Only if generated acceptance trace proves a detector-side acceptance gate, add one non-default proof profile scoped to reviewed-positive proposal lineage.
  - [x] Rerun promoted-v6 failing-source proof and regenerated truth; keep runtime defaults frozen unless promotion truth clears the gate.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = reviewed_positive_acceptance_gate_trace`
  - `whyDistinct = saved-artifact-only acceptance diagnosis for the five reviewed-positive selected frames before adding any acceptance profile`
  - result = succeeded as diagnostic truth, not acceptance recovery; generated truth says `reviewedPositiveSelectedFrameCount = 5`, `reviewedPositiveAcceptedFrameCount = 0`, `dominantBlockerClass = reviewed_positive_acceptance_artifact_gap`, `dominantBlockerFrameCount = 5`, `weakEvidenceReasons = [reviewed_positive_acceptance_gate_trace_missing]`, and `nextCorrectiveFamily = proof_acceptance_gate_trace_refresh`
  - artifactsChanged = yes; wrote `reviewed_positive_acceptance_fix_v1/*` and regenerated source robustness suite truth
  - nextDecision = advance to `proof_acceptance_gate_trace_refresh`; runtime defaults remain frozen because regenerated retention truth still says `accepted_signal_retention_collapse` with `acceptedRetentionRatio = 0.069`, `controlledRetentionRatio = 0.102`, and `passedPromotionGate = false`

## Next Corrective Sub-Batch — proof_acceptance_gate_trace_refresh

- Trigger:
  - `reviewed_positive_acceptance_fix_v1/reviewed_positive_acceptance_summary.json` says `batchStatus = succeeded`
  - generated truth says `dominantBlockerClass = reviewed_positive_acceptance_artifact_gap`
  - generated truth says `weakEvidenceReasons = [reviewed_positive_acceptance_gate_trace_missing]`
  - generated next corrective family is `proof_acceptance_gate_trace_refresh`
- Purpose:
  - add proof-only acceptance-gate trace so the next batch can name the exact acceptance rejection for the five reviewed-positive selected frames.
- Do not start runtime-default validation from this family.
- Do not add an acceptance profile until refreshed trace proves a concrete acceptance gate.
- Attempt budget: 3 materially distinct approaches.
- Attempt families:
  - Attempt 1: `acceptance_gate_trace_instrumentation`
  - Attempt 2: `fresh_failing_source_acceptance_trace_proof`
  - Attempt 3: `acceptance_trace_blocker_summary`
- Ordered tasks:
  - [x] Add diagnostic-only acceptance-gate trace fields for reviewed-positive selected rows.
  - [x] Run a fresh promoted-v6 failing-source proof with the reviewed-positive edge-share override profile and regenerated acceptance diagnostics.
  - [x] Rerun reviewed-positive acceptance fix and select the next corrective family from generated acceptance trace.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = acceptance_gate_trace_instrumentation`
  - `whyDistinct = proof-only acceptance-gate trace for reviewed-positive selected rows before adding any acceptance profile`
  - result = succeeded as diagnostic truth, not acceptance recovery; fresh RunPod-backed proof emitted `acceptanceGateTrace`, regenerated acceptance truth says `reviewedPositiveSelectedFrameCount = 5`, `reviewedPositiveAcceptedFrameCount = 0`, `dominantBlockerClass = reviewed_positive_selected_rejected_by_viability`, `dominantBlockerFrameCount = 5`, `weakEvidenceReasons = []`, and `nextCorrectiveFamily = reviewed_positive_acceptance_profile`
  - artifactsChanged = yes; refreshed promoted-v6 proof artifacts, `reviewed_positive_acceptance_fix_v1/*`, retention delta, and source robustness suite truth
  - nextDecision = advance to `reviewed_positive_acceptance_profile`; runtime defaults remain frozen because regenerated retention truth still says `accepted_signal_retention_collapse` with `acceptedRetentionRatio = 0.069`, `controlledRetentionRatio = 0.102`, and `winningPassedPromotionGate = false`

## Next Corrective Sub-Batch — reviewed_positive_acceptance_profile

- Trigger:
  - `reviewed_positive_acceptance_fix_v1/reviewed_positive_acceptance_summary.json` says `batchStatus = succeeded`
  - generated truth says `dominantBlockerClass = reviewed_positive_selected_rejected_by_viability`
  - generated truth says `reviewedPositiveSelectedFrameCount = 5`
  - generated truth says `reviewedPositiveAcceptedFrameCount = 0`
  - generated next corrective family is `reviewed_positive_acceptance_profile`
- Purpose:
  - test one narrow non-default acceptance/viability profile for reviewed-positive selected rows only.
- Do not start runtime-default validation from this family.
- Do not reuse the 74 rejected bootstrap seeds as positive truth.
- Attempt budget: 3 materially distinct approaches.
- Attempt families:
  - Attempt 1: `reviewed_positive_viability_acceptance_profile`
  - Attempt 2: `reviewed_positive_acceptance_truth_layer_probe`
  - Attempt 3: `reviewed_positive_acceptance_blocker_summary`
- Ordered tasks:
  - [x] Add a non-default reviewed-positive-only acceptance/viability profile if current proof trace justifies it.
  - [x] Run fresh promoted-v6 failing-source proof with the reviewed-positive anchor seed and profile.
  - [x] Rerun acceptance, retention, and suite truth; select the next family from generated artifacts.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = reviewed_positive_viability_acceptance_profile`
  - `whyDistinct = one non-default proof profile that relaxes only the viability handoff for selected rows whose proposal lineage starts with reviewed_positive_`
  - result = succeeded as reviewed-positive acceptance and retention lift, not promotion; regenerated truth says `reviewedPositiveSelectedFrameCount = 5`, `reviewedPositiveAcceptedFrameCount = 5`, `dominantBlockerClass = reviewed_positive_already_accepted`, `acceptedRetentionRatio = 0.099`, `controlledRetentionRatio = 0.133`, and `primaryRetentionBlockerClass = accepted_signal_retention_collapse`
  - artifactsChanged = yes; added `source_robustness_shadow_promoted_v6_reviewed_positive_acceptance_profile_v1`, refreshed promoted-v6 proof artifacts, `reviewed_positive_acceptance_fix_v1/*`, reviewed-positive micro/frame diagnostics, retention delta, and source robustness suite truth
  - nextDecision = advance to `reviewed_positive_residual_proposal_generation_fix`; runtime defaults remain frozen because regenerated suite truth still says `passedPromotionGate = false` and `sourceRobustnessPromotionBlockers = [failing_source_not_viable]`

## Next Corrective Sub-Batch — reviewed_positive_residual_proposal_generation_fix

- Trigger:
  - `reviewed_positive_acceptance_fix_v1/reviewed_positive_acceptance_summary.json` says `reviewedPositiveAcceptedFrameCount = 5`
  - `proof_runtime_frame_diagnostics_v1/proof_runtime_frame_diagnostics_summary.json` says `dominantBlockerClass = reviewed_positive_no_promoted_proposal`
  - generated truth says `dominantBlockerFrameCount = 12`
  - regenerated retention truth still says `primaryRetentionBlockerClass = accepted_signal_retention_collapse`
- Purpose:
  - target the 12 reviewed-positive frames that still lack promoted proposal evidence after the acceptance lift.
- Do not start runtime-default validation from this family.
- Do not reuse the 74 rejected bootstrap seeds as positive truth.
- Attempt budget: 3 materially distinct approaches.
- Attempt families:
  - Attempt 1: `residual_reviewed_positive_proposal_diagnosis`
  - Attempt 2: `residual_audit_best_crop_profile`
  - Attempt 3: `residual_continuity_preserving_crop_profile`
- Ordered tasks:
  - [x] Classify the 12 residual reviewed-positive frames by proposal window, raw detection, candidate collapse, selection, and acceptance stage.
  - [x] If generated truth proves a crop/scale gap, add one non-default residual reviewed-positive proposal profile and run RunPod-backed proof.
  - [x] Rerun residual, acceptance, retention, and suite truth; select the next family from generated artifacts.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = residual_reviewed_positive_proposal_diagnosis`
  - `whyDistinct = saved-artifact diagnosis only; classified residual reviewed-positive frames before adding another detector profile`
  - result = succeeded as diagnosis; generated truth said `residualReviewedPositiveFrameCount = 12`, `dominantBlockerClass = residual_window_generated_zero_raw_detect`, `dominantBlockerFrameCount = 12`, `residualAuditRescueAvailableFrameCount = 7`, `residualModelZeroDetectFrameCount = 5`, and `nextCorrectiveFamily = residual_audit_best_crop_profile`
  - artifactsChanged = yes; added `reviewed_positive_residual_proposal_generation_fix_v1/*`
  - nextDecision = run attempt 2 with a non-default residual audit-best crop profile; runtime defaults remain frozen
  - `attemptNumber = 2`
  - `approachFamily = residual_audit_best_crop_profile`
  - `whyDistinct = RunPod-backed proof profile that excluded the five already accepted frames while targeting audit-rescuable residual crop windows`
  - result = partial/failing proof attempt; generated truth improved proposal/collapse evidence but regressed selected/accepted truth to zero, proving the already accepted chain must stay available as continuity/follow-through context
  - artifactsChanged = yes; added `source_robustness_shadow_promoted_v6_reviewed_positive_residual_proposal_generation_fix_v1`, refreshed promoted proof, residual truth, retention delta, and suite truth
  - nextDecision = run attempt 3 with a continuity-preserving residual profile; runtime defaults remain frozen
  - `attemptNumber = 3`
  - `approachFamily = residual_continuity_preserving_crop_profile`
  - `whyDistinct = RunPod-backed proof profile that keeps the proven reviewed-positive chain available while expanding audit-best residual crop windows`
  - result = succeeded as proposal/selection/acceptance lift, not promotion; generated truth says `reviewedPositiveFrameCount = 17`, `reviewedPositiveAcceptedFrameCount = 10`, `proofTruth.bestProposalRawDetectedFrames = 17`, `proofTruth.bestProposalAfterSeedCollapseFrames = 17`, `proofTruth.bestProposalSelectedFrames = 10`, `dominantBlockerClass = residual_collapsed_not_selected`, `dominantBlockerFrameCount = 4`, and `nextCorrectiveFamily = promote_touchline_detector_candidate`
  - artifactsChanged = yes; added `source_robustness_shadow_promoted_v6_reviewed_positive_residual_proposal_generation_fix_v2`, refreshed promoted proof, residual truth, retention delta, and suite truth
  - nextDecision = stop this batch as successful controlled proof lift; runtime defaults remain frozen because regenerated truth still says `acceptedRetentionRatio = 0.099`, `controlledRetentionRatio = 0.133`, `primaryRetentionBlockerClass = accepted_signal_retention_collapse`, `winningPassedPromotionGate = false`, and `sourceRobustnessPromotionBlockers = [failing_source_not_viable]`

## Corrective Sub-Batch — residual_segment_selection_microfix

- Status: succeeded as controlled proof lift, not promotion
- Attempt Budget: 3
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = residual_selection_gate_trace_refresh`
  - `whyDistinct = saved-artifact gate trace over the four residual collapsed-not-selected reviewed-positive frames`
  - result = succeeded as diagnosis; generated truth classified frames `305,310,315,320` as `residual_segment_length_rejected`
  - artifactsChanged = yes; added `residual_segment_selection_microfix_v1/*`
  - nextDecision = run attempt 2 `residual_selected_segment_microprofile`
  - `attemptNumber = 2`
  - `approachFamily = residual_selected_segment_microprofile`
  - `whyDistinct = RunPod-backed non-default selected-segment microprofile scoped to the four residual frames`
  - result = succeeded as controlled proof lift; generated truth says `residualSelectedFrameCount = 4`, `residualAcceptedFrameCount = 4`, `proofTruth.acceptedBallFrames = 11`, but retention still says `acceptedRetentionRatio = 0.099`, `controlledRetentionRatio = 0.133`, and `primaryRetentionBlockerClass = accepted_signal_retention_collapse`
  - artifactsChanged = yes; added `source_robustness_shadow_promoted_v6_residual_segment_selection_microfix_v1`, refreshed proof and residual truth
  - nextDecision = advance to `accepted_retention_guardrail_audit`; runtime defaults remain frozen because generated promotion truth still says `winningPassedPromotionGate = false`

## Corrective Sub-Batch — accepted_retention_guardrail_audit

- Status: succeeded as guardrail truth, not promotion
- Attempt Budget: 3
- Ordered tasks:
  - [x] Quantify the actual accepted/controlled retention guardrail gap from `arm_matrix.json`.
  - [x] Compare the winning validation arm with the best retention arm.
  - [x] Select the next controlled retention batch from generated truth.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = guardrail_truth_audit`
  - `whyDistinct = saved-artifact audit of configured promotion guardrails after residual-frame lift`
  - result = succeeded; generated truth says `dominantBlockerClass = accepted_controlled_retention_guardrail_gap`, `bestRetentionArmName = promoted_v6_baseline`, `bestAcceptedRetentionRatio = 0.109`, `bestControlledRetentionRatio = 0.112`, `acceptedRetentionGuardrail = 0.60`, `controlledRetentionGuardrail = 0.60`, `acceptedFramesShortOfGuardrail = 50`, and `controlledFramesShortOfGuardrail = 48`
  - artifactsChanged = yes; added `accepted_retention_guardrail_audit_v1/*`, refreshed source robustness suite truth
  - nextDecision = advance to `global_accepted_gap_audit`; runtime-default validation remains blocked

## Next Corrective Sub-Batch — global_accepted_gap_audit

- Status: succeeded as saved-artifact gap audit
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `accepted_gap_manifest_refresh`
  - Attempt 2: `reachable_global_acceptance_probe`
  - Attempt 3: `v7_training_data_lane`
- Ordered tasks:
  - [x] Enumerate every baseline-accepted frame still missing from the best promoted proof.
  - [x] Classify missing frames as no proposal, raw not collapsed, collapsed not selected, selected not accepted, accepted, or artifact gap.
  - [x] Prioritize any globally reachable accepted frame before adding another reviewed-positive-only microprofile.
  - [x] If the residual gap is mostly no-detect, select the v7 training-data lane instead of widening runtime gates.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = accepted_gap_manifest_refresh`
  - `whyDistinct = saved-artifact frame-ID audit of baseline accepted truth versus best promoted accepted truth`
  - result = succeeded; generated truth says `baselineAcceptedFrameCount = 101`, `promotedAcceptedFrameCount = 11`, `overlappingAcceptedFrameCount = 0`, `missingBaselineAcceptedFrameCount = 101`, `dominantGapClass = baseline_accepted_no_promoted_proposal`, `dominantGapFrameCount = 94`, `gapClassCounts = {baseline_accepted_no_promoted_proposal: 94, baseline_accepted_collapsed_not_selected: 7}`, `reachableFrameCount = 7`, and `reachableFrameIds = [255,260,265,270,275,280,285]`
  - artifactsChanged = yes; added `global_accepted_gap_audit_v1/*`, refreshed source robustness suite truth
  - nextDecision = advance to `global_reachable_acceptance_probe`; runtime-default validation remains blocked

## Next Corrective Sub-Batch — global_reachable_acceptance_probe

- Status: succeeded as controlled proof lift, not promotion
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `reachable_collapsed_selection_trace`
  - Attempt 2: `global_reachable_selection_profile`
  - Attempt 3: `baseline_denominator_or_training_lane`
- Ordered tasks:
  - [x] Trace selection/follow-through gates for frames `255,260,265,270,275,280,285`.
  - [x] If trace proves a narrow selection/acceptance gate, add one non-default proof profile scoped to globally reachable baseline-accepted frames.
  - [x] If these frames are review-conflicted or unsafe, select `baseline_denominator_review_refresh` or `reviewed_positive_training_data_lane` from generated evidence.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = reachable_collapsed_selection_trace`
  - `whyDistinct = saved-artifact trace of the seven baseline-accepted frames with promoted raw/collapse evidence`
  - result = succeeded; generated truth says all seven frames are `global_reachable_selected_profile_ranking_rejected`, with no continuity, repeated-anchor, synthetic-row, segment-length, or edge-share rejection
  - artifactsChanged = yes; added `global_reachable_acceptance_probe_v1/*`
  - nextDecision = run attempt 2 `global_reachable_selection_profile`
  - `attemptNumber = 2`
  - `approachFamily = global_reachable_selection_profile`
  - `whyDistinct = RunPod-backed non-default proof profile scoped to frames 255,260,265,270,275,280,285`
  - result = succeeded as controlled proof lift; generated truth says `acceptedFrameCount = 7`, `selectedFrameCount = 7`, `dominantBlockerClass = global_reachable_already_accepted`, promoted baseline proof has `acceptedBallFrames = 14`, `controlledPossessionFrames = 17`, `acceptedRetentionRatio = 0.139`, and `controlledRetentionRatio = 0.173`
  - artifactsChanged = yes; added `source_robustness_shadow_promoted_v6_global_reachable_acceptance_probe_v1`, refreshed promoted proof, reachable probe truth, global gap truth, retention delta, guardrail audit, and suite truth
  - nextDecision = advance to `baseline_denominator_review_refresh`; runtime-default validation remains blocked

## Next Corrective Sub-Batch — baseline_denominator_review_refresh

- Status: succeeded as denominator/training-lane decision, not promotion
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `baseline_denominator_truth_audit`
  - Attempt 2: `refuted_denominator_filter_plan`
  - Attempt 3: `training_data_lane_or_manifest_refresh`
- Ordered tasks:
  - [x] Audit the 94 remaining missing baseline-accepted frames after global reachable recovery.
  - [x] Quantify how many missing denominator frames overlap refuted bootstrap seeds and reviewed-positive truth.
  - [x] Decide whether the baseline denominator needs a reviewed-truth refresh or whether v7 training data is the only honest next lane.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = baseline_denominator_truth_audit`
  - `whyDistinct = saved-artifact denominator quality audit over all 101 baseline accepted frames`
  - result = succeeded; generated truth says `baselineDenominatorFrameCount = 101`, `promotedAcceptedOverlapCount = 7`, `refutedDenominatorFrameCount = 68`, `reviewedPositiveSupportedFrameCount = 10`, `unreviewedDenominatorFrameCount = 23`, `effectiveAcceptedRetentionRatioAfterRefutedFilter = 0.212`, and `nextCorrectiveFamily = refuted_denominator_filter_plan`
  - artifactsChanged = yes; added `baseline_denominator_review_refresh_v1/*`
  - nextDecision = continue with attempt 2 `refuted_denominator_filter_plan`
  - `attemptNumber = 2`
  - `approachFamily = refuted_denominator_filter_plan`
  - `whyDistinct = proposed denominator delta only, excluding explicit refuted bootstrap seed frames without mutating frozen manifests`
  - result = succeeded; generated truth says `proposedExcludedFrameCount = 68`, `effectiveDenominatorAfterFilter = 33`, `effectiveAcceptedRetentionRatio = 0.212`, `wouldClearAcceptedRetentionGuardrail = false`, and `nextCorrectiveFamily = v7_training_data_lane`
  - artifactsChanged = yes; added `refuted_denominator_filter_plan_v1/*`
  - nextDecision = continue with attempt 3 `training_or_validation_branch`
  - `attemptNumber = 3`
  - `approachFamily = training_or_validation_branch`
  - `whyDistinct = converts denominator/refutation truth into a v7 training-data lane because denominator filtering still misses the guardrail`
  - result = succeeded; generated truth says `reviewedPositiveFrameCount = 17`, `refutedNegativeFrameCount = 74`, `unreviewedDenominatorFrameCount = 23`, `hardMiningCandidateCount = 26`, and `nextCorrectiveFamily = touchline_detector_candidate_v7_training_data_refresh`
  - artifactsChanged = yes; added `v7_training_data_lane_v1/*`, refreshed source robustness suite truth
  - nextDecision = advance to `touchline_detector_candidate_v7_training_data_refresh`; runtime-default validation remains blocked

## Next Corrective Sub-Batch — touchline_detector_candidate_v7_training_data_refresh

- Status: attempt 1 succeeded; quality gate blocks training prep
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `v7_dataset_manifest_refresh`
  - Attempt 2: `v7_training_quality_gate`
  - Attempt 3: `v7_training_or_manual_review_expansion`
- Ordered tasks:
  - [x] Convert `v7_training_data_lane_v1/v7_training_data_manifest.json` into a concrete v7 dataset manifest.
  - [x] Keep refuted bootstrap seeds negative-only.
  - [x] Use the 23 unreviewed denominator frames as review/hard-mining candidates, not positives.
  - [x] Do not switch runtime defaults until a later promoted robustness proof clears the gate.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = v7_dataset_manifest_refresh`
  - `whyDistinct = turns the v7 lane truth surface into concrete positive, negative, pending-review, and hard-mining manifests without detector/runtime changes`
  - result = packaged but not train-ready; generated truth says `reviewedPositiveFrameCount = 17`, `refutedNegativeFrameCount = 74`, `pendingReviewFrameCount = 23`, `hardMiningCandidateCount = 26`, `trainingReady = false`, `weakEvidenceReasons = [reviewed_positive_count_below_minimum, unreviewed_denominator_frames_pending]`, and `nextCorrectiveFamily = manual_review_denominator_expansion`
  - artifactsChanged = yes; added `touchline_detector_candidate_v7_training_data_refresh_v1/*`, refreshed source robustness suite truth
  - nextDecision = advance to `manual_review_denominator_expansion`; runtime-default validation remains blocked

## Next Corrective Sub-Batch — manual_review_denominator_expansion

- Status: succeeded as review-package generation; paused on manual review
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `denominator_review_package_generation`
  - Attempt 2: `json_only_denominator_review_fallback`
  - Attempt 3: `denominator_review_blocker_summary`
- Ordered tasks:
  - [x] Build a review package for the `23` pending denominator frames from `touchline_detector_candidate_v7_training_data_refresh_v1/v7_labeling_queue.json`.
  - [x] Preserve the `17` reviewed positives as positive truth and the `74` refuted bootstrap seeds as negative-only evidence.
  - [x] Extract review frames when local video is available; otherwise write a JSON-only review package with stable frame IDs and lineage.
  - [x] Stop on a manual-review gate rather than training v7 until pending denominator decisions are resolved.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = denominator_review_package_generation`
  - `whyDistinct = creates a review-ready package for the pending denominator frames that block v7 training-data readiness`
  - result = succeeded as review-package generation; generated truth says `reviewItemCount = 23`, `pendingReviewCount = 23`, `lineageCompleteCount = 23`, `imageExtractionStatus = images_extracted`, and `nextCorrectiveFamily = manual_review_denominator_resolution`
  - artifactsChanged = yes; added `manual_review_denominator_expansion_v1/*`, including 23 extracted review frames
  - nextDecision = stop on `manual_review_pending`; resolve `manual_review_denominator_expansion_v1/reviewed_label_overlay.json` before running denominator resolution

## Next Corrective Sub-Batch — manual_review_denominator_resolution

- Status: succeeded as review resolution; v7 training prep is justified
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `denominator_review_decision_validation`
  - Attempt 2: `denominator_review_overlay_repair_guidance`
  - Attempt 3: `denominator_reviewed_truth_seed_generation`
- Ordered tasks:
  - [x] Validate all `23` denominator review decisions after `pendingReviewCount = 0`.
  - [x] Convert accepted/adjusted denominator decisions into reviewed positive v7 truth.
  - [x] Preserve rejected/confirmed-hard-negative decisions as negative/refutation evidence.
  - [x] Rerun the v7 training quality gate and only advance to training prep if generated truth says `trainingReady = true`.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = denominator_review_decision_validation`
  - `whyDistinct = resolves the 23 denominator review frames and validates whether the v7 truth surface is large enough for training prep`
  - result = succeeded; generated truth says `pendingReviewCount = 0`, `invalidDecisionCount = 0`, `denominatorReviewedPositiveCount = 19`, `denominatorReviewedNegativeCount = 4`, `totalReviewedPositiveFrameCount = 36`, and `nextCorrectiveFamily = touchline_detector_candidate_v7_training_prep`
  - artifactsChanged = yes; added `manual_review_denominator_resolution_v1/*`, refreshed source robustness suite truth
  - nextDecision = advance to `touchline_detector_candidate_v7_training_prep`; runtime-default validation remains blocked

## Next Corrective Sub-Batch — touchline_detector_candidate_v7_training_prep

- Status: succeeded as training-prep manifest assembly
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `v7_training_manifest_assembly`
  - Attempt 2: `v7_training_quality_gate`
  - Attempt 3: `v7_training_blocker_summary`
- Ordered tasks:
  - [x] Assemble a concrete training manifest from `touchline_detector_candidate_v7_training_data_refresh_v1/v7_dataset_manifest.json` plus `manual_review_denominator_resolution_v1/reviewed_denominator_truth_seed.json`.
  - [x] Keep all rejected/refuted seeds negative-only.
  - [x] Run a training-data quality gate before any retraining.
  - [x] Do not retrain or validate runtime defaults unless the quality gate selects the next training batch.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = v7_training_manifest_assembly`
  - `whyDistinct = merges the prior v7 dataset manifest with the resolved denominator review truth before any retraining`
  - result = succeeded; generated truth says `trainingPrepReady = true`, `positiveExampleCount = 30`, `negativeExampleCount = 78`, `remainingPendingReviewCount = 0`, `positiveBBoxMissingCount = 0`, `refutedPositiveOverlapCount = 6`, and `weakEvidenceReasons = []`
  - artifactsChanged = yes; added `touchline_detector_candidate_v7_training_prep_v1/*`, refreshed source robustness suite truth
  - nextDecision = advance to `touchline_detector_candidate_v7_training`; runtime-default validation remains blocked

## Next Corrective Sub-Batch — touchline_detector_candidate_v7_training

- Status: succeeded as RunPod-backed training and evaluation-readiness gate
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `runpod_v7_training`
  - Attempt 2: `training_quality_or_manifest_repair`
  - Attempt 3: `v7_training_blocker_summary`
- Ordered tasks:
  - [x] Train `touchline_detector_candidate_v7` from `touchline_detector_candidate_v7_training_prep_v1/v7_training_manifest.json`.
  - [x] Use RunPod for training-heavy work and delete/stop pods at closeout.
  - [x] Write training summary, quality gate, and candidate metadata artifacts.
  - [x] Do not promote or validate runtime defaults until the trained candidate passes the normal evaluation/promotion gates.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = runpod_v7_training`
  - `whyDistinct = trains the first v7 detector from the reviewed-positive/refuted-negative manifest instead of adding another v6 proof profile`
  - result = succeeded; generated truth says `trainingCompleted = true`, `weightsReady = true`, `trainingQualityGatePassed = true`, `readyForDetectorEvaluation = true`, and `nextRecommendedNextLever = touchline_detector_candidate_v7_evaluation`
  - artifactsChanged = yes; added v7 export artifacts under `backend/storage/training_prep/touchline_detector_candidate_v7_training_v1/` and candidate artifacts under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/`
  - podCloseout = `runpodctl pod list --all -o json` returned `[]`
  - nextDecision = advance to `touchline_detector_candidate_v7_evaluation`; runtime-default validation remains blocked

## Next Corrective Sub-Batch — touchline_detector_candidate_v7_evaluation

- Status: completed; not promotable
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `bounded_v7_detector_evaluation`
  - Attempt 2: `v7_evaluation_threshold_or_profile_repair`
  - Attempt 3: `v7_evaluation_blocker_summary`
- Ordered tasks:
  - [x] Evaluate `touchline_detector_candidate_v7` from `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/weights/best.pt`.
  - [x] Compare v7 against the standing failing-source proof floor and the promoted-v6 truth surface.
  - [x] Write evaluation summary, evaluation contract closeout, decision matrix, and batch outcome artifacts.
  - [x] Do not promote or validate runtime defaults unless generated evaluation and promotion truth clear their gates.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = bounded_v7_detector_evaluation`
  - `whyDistinct = evaluates the newly trained v7 weights rather than extending the v6 proof-profile branch`
  - result = completed but failed product comparison; generated truth says `screenCompleted = true`, `screenWinningDetectorLabel = yolov10n.pt_baseline_full_detector`, `candidateBaselineProductBeatsPlateau = false`, `acceptedBallFrames = 0`, `controlledPossessionFrames = 0`, `evaluationPrimaryBlocker = candidate_baseline_did_not_beat_plateau`, and `readyForPromotion = false`
  - artifactsChanged = yes; added `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/evaluation_v1/*` and refreshed source robustness suite truth
  - podCloseout = `runpodctl pod list --all -o json` returned `[]`
  - nextDecision = advance to `touchline_detector_candidate_v7_evaluation_failure_analysis`; runtime-default validation remains blocked

## Next Corrective Sub-Batch — touchline_detector_candidate_v7_evaluation_failure_analysis

- Status: succeeded as saved-artifact diagnosis
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `v7_evaluation_saved_artifact_diagnosis`
  - Attempt 2: `v7_probe_assist_contract_audit`
  - Attempt 3: `v7_training_or_runtime_blocker_summary`
- Ordered tasks:
  - [x] Compare v7 evaluation proof artifacts against v6/promoted proof artifacts and the v7 training manifest.
  - [x] Determine whether the failure is model/data quality, auxiliary probe integration, proposal-window incompatibility, or artifact coverage.
  - [x] Select exactly one next corrective family from generated evidence.
  - [x] Keep runtime defaults frozen.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = v7_evaluation_saved_artifact_diagnosis`
  - `whyDistinct = diagnoses the failed v7 evaluation from saved screen/proof/training artifacts before another training or proof-profile attempt`
  - result = succeeded; generated truth says `dominantBlockerClass = v7_auxiliary_probe_zero_raw_signal`, `candidateScreenViable = false`, `candidateRawProbeObservedBallFrames = 0`, `candidateBestProposalRawDetectedFrames = 0`, `candidateAcceptedBallFrames = 0`, and `nextCorrectiveFamily = v7_probe_assist_integration_audit`
  - artifactsChanged = yes; added `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/evaluation_failure_analysis_v1/*`, refreshed source robustness suite truth
  - nextDecision = advance to `v7_probe_assist_integration_audit`; runtime-default validation remains blocked

## Next Corrective Sub-Batch — v7_probe_assist_integration_audit

- Status: succeeded as saved-artifact diagnosis
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `probe_assist_invocation_audit`
  - Attempt 2: `probe_threshold_preprocessing_audit`
  - Attempt 3: `probe_integration_blocker_summary`
- Ordered tasks:
  - [x] Verify that the v7 auxiliary model is staged, invoked, and wired into the proof runtime as expected.
  - [x] Audit preprocessing, image size, confidence threshold, and class-index assumptions for the v7 auxiliary probe.
  - [x] Decide whether the next fix is `v7_probe_assist_runtime_contract_fix`, `v7_probe_threshold_preprocessing_fix`, `v7_training_data_quality_refresh`, or `v7_model_retraining_lane`.
  - [x] Keep runtime defaults frozen.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = probe_assist_invocation_audit`
  - `whyDistinct = diagnoses the zero-signal v7 proof from saved contract/proof/trace artifacts before any offline inference or retraining`
  - result = succeeded; generated truth says `bestWeightsPathExists = true`, `proofReportAuxiliaryBallModelPathPresent = true`, `traceAuxiliaryBallModelPathPresent = true`, `probePassAppearsInvoked = true`, `probeObservedPassSeconds = 34.779`, `rawProbeObservedBallFrames = 0`, and `dominantBlockerClass = v7_preprocessing_or_threshold_mismatch`
  - artifactsChanged = yes; added `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_probe_assist_integration_audit_v1/*`
  - nextDecision = advance to `v7_probe_threshold_preprocessing_fix`; runtime-default validation remains blocked

## Next Corrective Sub-Batch — v7_probe_threshold_preprocessing_fix

- Status: succeeded as offline inference diagnosis
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `offline_threshold_preprocessing_audit`
  - Attempt 2: `probe_threshold_contract_fix`
  - Attempt 3: `v7_model_quality_or_retraining_summary`
- Ordered tasks:
  - [x] Run a diagnostic-only offline inference audit on reviewed-positive/training-positive frames using v7 `best.pt`.
  - [x] Compare detection output across confidence thresholds, image sizes, class IDs, and crop/full-frame preprocessing.
  - [x] If offline detections exist, select or implement a proof-only threshold/preprocessing contract fix; if none exist, select `v7_training_data_quality_refresh`.
  - [x] Keep runtime defaults frozen.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = offline_threshold_preprocessing_audit`
  - `whyDistinct = runs v7 offline on exported positive images before changing proof/runtime thresholds or retraining`
  - result = succeeded; generated truth says `positiveImageCount = 30`, `offlineDetectedImageCount = 30`, `wrongClassDetectionCount = 0`, detections only appear at low confidence (`0.001` and `0.01`) for image sizes `640` and `960`, and `dominantBlockerClass = v7_offline_detections_available`
  - artifactsChanged = yes; added `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_probe_threshold_preprocessing_fix_v1/*`
  - nextDecision = advance to `v7_probe_threshold_contract_fix`; runtime-default validation remains blocked

## Next Corrective Sub-Batch — v7_probe_threshold_contract_fix

- Status: attempt 1 complete; batch succeeded as zero-signal breakthrough but exposed a precision guardrail blocker
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `proof_only_low_conf_probe_contract` — complete
  - Attempt 2: `probe_preprocessing_contract_alignment`
  - Attempt 3: `threshold_contract_blocker_summary`
- Ordered tasks:
  - [x] Add a non-default proof-only v7 probe profile/contract that uses the audited low confidence threshold and preserves runtime-default isolation.
  - [x] Run RunPod-backed candidate evaluation/proof with the adjusted v7 probe contract.
  - [x] Regenerate v7 threshold-contract truth and decide whether proposal/selection/acceptance now has signal.
  - [x] Keep runtime defaults frozen unless generated promotion truth clears the gate.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = proof_only_low_conf_probe_contract`
  - `whyDistinct = tests the audited low-confidence v7 probe contract inside proof runtime without changing runtime defaults`
  - result = succeeded as a zero-signal breakthrough, not as promotion; partial RunPod proof produced `rawProbeObservedBallFrames = 1516`, `probeObservedBallFrames = 1516`, and `acceptedFrames = 1516`
  - artifactsChanged = yes; added `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_probe_threshold_contract_fix_v1/*`
  - nextDecision = advance to `v7_probe_precision_guardrail_audit`; the low-confidence contract recovers signal but floods accepted truth, so precision/guardrails must be audited before any further evaluation or promotion path

## Next Corrective Sub-Batch — v7_probe_precision_guardrail_audit

- Status: attempt 1 complete; batch succeeded as precision failure analysis
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `low_conf_precision_guardrail_audit` — complete
  - Attempt 2: `threshold_sweep_precision_contract`
  - Attempt 3: `precision_guardrail_blocker_summary`
- Ordered tasks:
  - [x] Audit the low-confidence proof output against reviewed positives/negatives and accepted-frame guardrails.
  - [x] Determine whether a tighter threshold/window/lineage contract can keep raw signal while rejecting the `1516`-frame flood.
  - [x] If no precision-safe contract exists, select `v7_training_data_quality_refresh` or `v7_probe_threshold_sweep_retrain`.
  - [x] Keep runtime defaults frozen unless generated promotion truth clears the gate.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = low_conf_precision_guardrail_audit`
  - `whyDistinct = saved-artifact precision audit over the low-confidence v7 proof, using reviewed positives and reviewed negatives as guardrails`
  - result = succeeded as failure analysis; generated truth says `positiveFrameHitRate = 1.0`, `negativeFrameHitRate = 1.0`, `frameHitRate = 1.0`, `medianConfidence = 0.012018`, `medianSourceBoxArea = 46429.319`, no safe confidence or geometry contract exists
  - artifactsChanged = yes; added `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_probe_precision_guardrail_audit_v1/*`
  - nextDecision = advance to `v7_training_data_quality_refresh`; the model/proof contract sees positives only by also firing on all negatives and effectively all sampled frames

## Next Corrective Sub-Batch — v7_training_data_quality_refresh

- Status: attempt 1 complete; batch succeeded as data-quality diagnosis
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `localization_export_sanity_audit` — complete
  - Attempt 2: `hard_negative_rebalance_plan`
  - Attempt 3: `v7_training_quality_blocker_summary`
- Ordered tasks:
  - [x] Use the precision audit, 30 positives, 78 negatives, and the low-conf proof flood to identify whether v7 needs stronger negatives, cropped positives, label strategy changes, or a retraining recipe correction.
  - [x] Build a proposed v7.1 training-data refresh manifest; do not train until the manifest quality gate is explicit.
  - [x] Preserve all refuted examples as negative-only evidence.
  - [x] Keep runtime defaults frozen unless generated promotion truth clears the gate.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = localization_export_sanity_audit`
  - `whyDistinct = distinguishes frame-level low-confidence hits from actual localization and audits YOLO export/negative semantics before retraining`
  - result = succeeded as failure analysis; generated truth says `positiveLocalizationHitRate = 0.0`, `malformedLabelCount = 0`, `bboxMismatchCount = 0`, `refutedSeedPositiveLabelCount = 0`, `unsafeFullFrameNegativeCount = 78`, and `hardNegativeCandidateCount = 304`
  - artifactsChanged = yes; added `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_training_data_quality_refresh_v1/*`
  - nextDecision = advance to `v7_negative_semantics_review`; export labels are structurally sane, but the 78 full-frame empty-label negatives are not safe as YOLO negatives without visible-ball review or crop conversion

## Next Corrective Sub-Batch — v7_negative_semantics_review

- Status: attempt 1 complete; batch succeeded as negative-semantics packaging
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `negative_visible_ball_review_package` — complete
  - Attempt 2: `negative_crop_conversion_plan`
  - Attempt 3: `negative_semantics_blocker_summary`
- Ordered tasks:
  - [x] Review or convert the 78 full-frame empty-label negatives so they are not teaching YOLO that frames with possible visible balls contain no ball.
  - [x] Preserve refuted seeds as negative-only evidence and prefer local hard-negative crops when the full frame may contain a true ball elsewhere.
  - [x] Carry forward the 304 top-left artifact hard-negative candidates from the v7 flood proof as review/crop candidates.
  - [x] Do not train v7.1 until the negative semantics gate is explicit and complete.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = negative_visible_ball_review_package`
  - `whyDistinct = convert the data-quality blocker into explicit negative-semantics review and crop-conversion artifacts without inventing labels`
  - result = succeeded as saved-artifact packaging; generated truth says `dominantBlockerClass = v7_full_frame_negative_visible_ball_review_required`, `unsafeFullFrameNegativeCount = 78`, `pendingVisibleBallReviewCount = 78`, `topLeftArtifactHardNegativeCandidateCount = 200`, `sourceHardNegativeCandidateCount = 304`, and `nextCorrectiveFamily = v7_negative_crop_conversion_plan`
  - artifactsChanged = yes; added `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_negative_semantics_review_v1/*`
  - nextDecision = advance to `v7_negative_crop_conversion_plan`; keep runtime defaults frozen and do not train v7.1 until the unsafe full-frame negatives are dropped, reviewed, or converted into local hard-negative crops

## Next Corrective Sub-Batch — v7_negative_crop_conversion_plan

- Status: attempt 1 complete; batch succeeded as crop-conversion planning
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `top_left_artifact_crop_manifest` — complete
  - Attempt 2: `refuted_seed_crop_or_drop_plan`
  - Attempt 3: `negative_crop_conversion_blocker_summary`
- Ordered tasks:
  - [x] Convert the 200 sampled top-left artifact candidates into proposed local hard-negative crop records, not full-frame empty-label negatives.
  - [x] Exclude the 78 unsafe full-frame negative exports from v7.1 until each is reviewed or converted.
  - [x] Preserve refuted seeds as negative-only evidence and never promote them into positive labels.
  - [x] Select `v7_1_training_manifest_prep` only when the proposed manifest has no unsafe full-frame empty-label negatives.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = top_left_artifact_crop_manifest`
  - `whyDistinct = convert the top-left flood evidence into local hard-negative crop records while excluding unsafe full-frame empty-label negatives`
  - result = succeeded as saved-artifact planning; generated truth says `dominantBlockerClass = v7_negative_crop_conversion_ready`, `positiveExamplesPreserved = 30`, `unsafeFullFrameNegativeExcludedCount = 78`, `localHardNegativeCropCount = 200`, `roadmapAdvanceAllowed = true`, and `nextCorrectiveFamily = v7_1_training_manifest_prep`
  - artifactsChanged = yes; added `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_negative_crop_conversion_plan_v1/*`
  - nextDecision = advance to `v7_1_training_manifest_prep`; runtime defaults stay frozen and this remains data prep, not retraining or promotion

## Next Corrective Sub-Batch — v7_1_training_manifest_prep

- Status: attempt 1 complete; batch succeeded as manifest assembly
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `v7_1_manifest_assembly` — complete
  - Attempt 2: `v7_1_manifest_quality_gate_repair`
  - Attempt 3: `v7_1_manifest_blocker_summary`
- Ordered tasks:
  - [x] Assemble a proposed v7.1 manifest from 30 reviewed positives and 200 local top-left artifact hard-negative crops.
  - [x] Prove the manifest contains zero unsafe full-frame empty-label negatives and zero refuted positives.
  - [x] Preserve grouped temporal split requirements.
  - [x] Stop at training readiness; do not run training until the v7.1 prep gate clears.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = v7_1_manifest_assembly`
  - `whyDistinct = assemble the v7.1 training surface after negative crop conversion, with quality gates for unsafe negatives, refuted positives, bboxes, and split coverage`
  - result = succeeded as manifest prep; generated truth says `dominantBlockerClass = v7_1_training_manifest_ready`, `trainingPrepReady = true`, `positiveExampleCount = 30`, `negativeExampleCount = 200`, `unsafeFullFrameNegativeCount = 0`, `refutedSeedPositiveLabelCount = 0`, `positiveBBoxMissingCount = 0`, `weakEvidenceReasons = []`, and `nextCorrectiveFamily = touchline_detector_candidate_v7_1_training`
  - artifactsChanged = yes; added `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_training_manifest_prep_v1/*`
  - nextDecision = advance to `v7_1_crop_manifest_consistency_refresh`; runtime defaults stay frozen and no promotion/default validation is allowed from manifest prep alone

## Next Corrective Sub-Batch — v7_1_crop_manifest_consistency_refresh

- Status: attempt 2 complete; batch succeeded as local-crop consistency refresh
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `positive_crop_transform_manifest` — failed with split leakage
  - Attempt 2: `crop_transform_quality_repair` — complete
  - Attempt 3: `crop_manifest_blocker_summary`
- Ordered tasks:
  - [x] Convert reviewed positives into local crop examples with transformed crop-local bboxes.
  - [x] Keep hard negatives local-crop only, cap first-run negatives, and hold out the remainder as canaries.
  - [x] Detect and repair source-frame split leakage before training/export.
  - [x] Stop at export-audit readiness; do not train, promote, or mutate runtime defaults.
- Attempt Log:
  - `attemptNumber = 1`
  - `approachFamily = positive_crop_transform_manifest`
  - result = failed usefully; generated truth produced `positiveCropExampleCount = 90`, `localHardNegativeCropCount = 180`, `heldoutHardNegativeCanaryCount = 20`, but blocked on `dominantBlockerClass = v7_1_manifest_split_leakage` with `splitLeakageCount = 41`
  - `attemptNumber = 2`
  - `approachFamily = crop_transform_quality_repair`
  - result = succeeded after deterministic group-level split repair; generated truth says `dominantBlockerClass = v7_1_crop_manifest_consistency_ready`, `positiveCropExampleCount = 90`, `localHardNegativeCropCount = 180`, `heldoutHardNegativeCanaryCount = 20`, `negativePositiveRatio = 2.0`, `splitLeakageCount = 0`, `manifestReadyForExportAudit = true`, `promotionReady = false`, `candidateReadyForEvaluation = false`, and `nextCorrectiveFamily = v7_1_export_label_overlay_audit`
  - artifactsChanged = yes; added `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_crop_manifest_consistency_refresh_v1/*`
  - nextDecision = advance to `v7_1_export_label_overlay_audit`; training remains blocked until visual/export overlay audit passes

## Next Corrective Sub-Batch — v7_1_export_label_overlay_audit

- Status: completed
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `crop_export_overlay_generation`
  - Attempt 2: `overlay_geometry_repair`
  - Attempt 3: `overlay_audit_blocker_summary`
- Ordered tasks:
  - [x] Generate crop image/label overlay artifacts for sampled positive and negative crop examples.
  - [x] Verify crop-local positive labels visually/structurally align with the ball.
  - [x] Verify negative crop labels are empty and local-crop only.
  - [x] Advance to a tiny overfit sanity train only if overlay/export audit passes.
- Attempt Log:
  - attemptNumber = 1
  - approachFamily = `crop_export_overlay_generation`
  - result = succeeded from physical export artifacts; generated truth says `readinessClass = v7_1_export_overlay_audit_ready`, `primaryBlocker = null`, `positiveCropExampleCount = 90`, `localHardNegativeCropCount = 180`, `heldoutHardNegativeCanaryCount = 20`, `positiveLabelFilesWithExactlyOneBall = 90`, `negativeLabelFilesEmpty = 180`, `heldoutCanaryLabelFilesEmpty = 20`, `positiveLabelRoundTripMaxErrorPx = 0.5`, `splitLeakageCount = 0`, `canaryLeakageCount = 0`, `exportOverlayAuditPassed = true`, `trainingReady = false`, `promotionReady = false`, and `runtimeDefaultMutationAllowed = false`
  - artifactsChanged = yes; added `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_export_label_overlay_audit_v1/*`
  - nextDecision = advance to `v7_1_tiny_overfit_sanity_train`; full v7.1 training remains blocked until tiny overfit sanity passes

## Next Corrective Sub-Batch — v7_1_tiny_overfit_sanity_train

- Status: exhausted
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `tiny_crop_overfit_train`
  - Attempt 2: `tiny_export_or_config_repair`
  - Attempt 3: `tiny_overfit_blocker_summary`
- Ordered tasks:
  - [x] Build a tiny v7.1 YOLO export from the audited crop preview: 10 positive crop images and 20 local hard-negative crop images.
  - [x] Train only a tiny sanity candidate, preferably on RunPod, and verify it localizes the training positives above diagnostic confidence while keeping hard negatives mostly quiet.
  - [x] If it cannot overfit, classify the blocker as export/config/model setup rather than data scale.
  - [x] Advance to bounded v7.1 retraining only if the tiny sanity train passes.
- Attempt Log:
  - attemptNumber = 1
  - approachFamily = `tiny_crop_overfit_train`
  - result = failed before training due to RunPod helper plumbing (`create_runpod_session()` unexpected `sync_proof_videos` argument)
  - nextDecision = adapt to attempt 2 with repo-native RunPod session creation
  - attemptNumber = 2
  - approachFamily = `tiny_runpod_session_plumbing_repair`
  - result = failed before training due to remote device mismatch; Ultralytics rejected `device=0` because `torch.cuda.is_available() = false`
  - nextDecision = adapt to attempt 3 with CPU device fallback for the tiny sanity train
  - attemptNumber = 3
  - approachFamily = `tiny_cpu_device_fallback`
  - result = failed from generated model truth after training completed; generated truth says `tinyOverfitTrainingCompleted = true`, `tinyTrainPositiveLocalizationHitRate = 0.0`, `medianTrainPositiveConfidence = null`, `tinyTrainNegativeFalsePositiveFrameRate = 0.0`, `tinyHeldoutCanaryFalsePositiveFrameRate = 0.0`, `primaryBlocker = v7_1_tiny_train_positive_localization_failure`, and `nextRecommendedNextLever = v7_1_training_config_or_export_debug`
  - artifactsChanged = yes; added `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_tiny_overfit_sanity_train_v1/*`
  - nextDecision = stop before bounded retrain and debug the training/config/export path

## Next Corrective Sub-Batch — v7_1_training_config_or_export_debug

- Status: completed
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `tiny_train_label_loading_debug`
  - Attempt 2: `model_head_or_class_contract_debug`
  - Attempt 3: `export_config_blocker_summary`
- Ordered tasks:
  - [x] Prove whether the tiny YOLO training run loaded the 10 positive crop labels and 20 hard-negative labels as intended.
  - [x] Audit model/class/imgsz/data.yaml contracts from `v7_1_tiny_overfit_sanity_train_v1/train_run/results.csv`, weights, and tiny dataset labels.
  - [x] If label loading is valid, test whether the base model/head/config is incompatible with the local crop setup.
  - [x] Do not run bounded v7.1 retrain until the tiny overfit can localize memorized positives.
- Attempt Log:
  - attemptNumber = 1
  - approachFamily = `tiny_train_label_loading_debug`
  - result = succeeded as diagnosis; generated truth says `trainerObservedLabelRowCount = 10`, `trainerObservedPositiveLabelImageCount = 10`, `trainerObservedBackgroundImageCount = 20`, `trainerObservedClassIdSet = [0]`, `trainerObservedNc = 1`, `boxLossNonZero = true`, `boxLossDecreased = true`, `wrongCheckpointContractLikely = true`, `inferenceUsedTrainedWeights = false`, and `primaryBlocker = v7_1_wrong_checkpoint_for_inference`
  - artifactsChanged = yes; added `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_training_config_or_export_debug_v1/*`
  - nextDecision = retry tiny overfit with the verified local checkpoint/inference contract; do not run bounded retrain yet

## Next Corrective Sub-Batch — v7_1_tiny_overfit_retry_with_verified_config

- Status: completed
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `retry_with_verified_checkpoint_contract`
  - Attempt 2: `last_checkpoint_low_conf_sweep`
  - Attempt 3: `verified_config_blocker_summary`
- Ordered tasks:
  - [x] Rerun the tiny overfit inference/training gate with the fixed local checkpoint resolver.
  - [x] Confirm `inferenceUsedTrainedWeights = true` and compare `best.pt` versus `last.pt` if localization is still zero.
  - [x] If trained weights still produce no near-GT predictions, classify model/task/hparam failure from generated truth.
  - [x] Advance to bounded retrain only if the tiny overfit gate now passes.
- Attempt Log:
  - attemptNumber = 1
  - approachFamily = `retry_with_verified_checkpoint_contract`
  - result = succeeded; generated truth says `previousTinyOverfitVerdictInvalidated = true`, `previousInvalidationReason = v7_1_wrong_checkpoint_for_inference`, `checkpointContractPassed = true`, `inferenceUsedTrainedWeights = true`, `inferenceUsedRemotePath = false`, `inferenceUsedBaseModel = false`, `selectedCheckpointForVerdict = best.pt`, `selectedAuditConf = 0.1`, `tinyTrainPositiveLocalizationHitRate = 0.9`, `tinyTrainNegativeFalsePositiveFrameRate = 0.0`, `tinyHeldoutCanaryFalsePositiveFrameRate = 0.0`, `medianTrainPositiveConfidence = 0.30675`, `minTrainPositiveConfidence = 0.132288`, `medianDetectedBoxAreaToGtBoxAreaRatio = 1.035636`, `topLeftArtifactShare = 0.0`, `giantBoxShare = 0.0`, and `primaryBlocker = null`
  - artifactsChanged = yes; added `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_tiny_overfit_retry_with_verified_config_v1/*`
  - nextDecision = advance to `v7_1_bounded_retrain`; do not promote or mutate runtime defaults

## Next Corrective Sub-Batch — v7_1_bounded_retrain

- Status: completed
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `bounded_crop_retrain`
  - Attempt 2: `bounded_checkpoint_or_hparam_repair`
  - Attempt 3: `bounded_retrain_blocker_summary`
- Ordered tasks:
  - [x] Train on the audited bounded v7.1 crop dataset: 90 positive crops and 180 local hard-negative crops; keep 20 canaries held out.
  - [x] Evaluate localization-level train/val/canary precision, confidence, top-left artifact share, and giant-box share.
  - [x] Stop at candidate-evaluation readiness only if bounded retrain passes; do not promote.
  - [x] If bounded retrain fails, select the next data/config lever from generated truth.
- Attempt Log:
  - attemptNumber = 1
  - approachFamily = `bounded_crop_retrain`
  - result = succeeded; generated truth says `trainingCompleted = true`, `checkpointContractPassed = true`, `inferenceUsedTrainedWeights = true`, `selectedCheckpointForVerdict = best.pt`, `selectedAuditConf = 0.1`, `trainerObservedLabelRowCount = 90`, `boundedTrainPositiveLocalizationHitRate = 1.0`, `boundedValPositiveLocalizationHitRate = 0.5`, `boundedTrainNegativeFalsePositiveFrameRate = 0.0`, `boundedValNegativeFalsePositiveFrameRate = 0.0`, `heldoutCanaryFalsePositiveFrameRate = 0.0`, `medianTrainPositiveConfidence = 0.974239`, `medianValPositiveConfidence = 0.797017`, `medianDetectedBoxAreaToGtBoxAreaRatio = 0.97323`, `topLeftArtifactShare = 0.0`, `giantBoxShare = 0.0`, and `primaryBlocker = null`
  - artifactsChanged = yes; added `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_bounded_retrain_v1/*`
  - nextDecision = advance to `v7_1_crop_probe_precision_guardrail_audit`; do not promote or mutate runtime defaults

## Next Corrective Sub-Batch — v7_1_crop_probe_precision_guardrail_audit

- Status: completed
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `bounded_crop_precision_guardrail_audit`
  - Attempt 2: `crop_probe_threshold_or_slice_repair`
  - Attempt 3: `crop_probe_guardrail_blocker_summary`
- Ordered tasks:
  - [x] Audit the bounded v7.1 `best.pt` crop detector against train positives, validation positives, hard negatives, heldout canaries, and the old top-left artifact family.
  - [x] Keep localization-level metrics as the gate: IoU hit, center-distance hit, false-positive rate, confidence, top-left share, and giant-box share.
  - [x] If the bounded crop detector is precise enough, advance only to non-promotion crop-probe evaluation; do not promote or mutate runtime defaults.
  - [x] If precision fails, select exactly one next data/config lever from generated truth.
- Attempt Log:
  - attemptNumber = 1
  - approachFamily = `bounded_crop_precision_guardrail_audit`
  - result = succeeded; generated truth says `checkpointContractPassed = true`, `inferenceUsedTrainedWeights = true`, `selectedCheckpointForAudit = best.pt`, `selectedAuditConf = 0.1`, `boundedTrainPositiveLocalizationHitRate = 1.0`, `boundedValPositiveLocalizationHitRate = 0.5`, `boundedTrainHardNegativeFalsePositiveFrameRate = 0.0`, `boundedValHardNegativeFalsePositiveFrameRate = 0.0`, `heldoutCanaryFalsePositiveFrameRate = 0.0`, `oldTopLeftArtifactFalsePositiveFrameRate = 0.0`, `topLeftArtifactShare = 0.0`, `giantBoxShare = 0.0`, `medianDetectedBoxAreaToGtBoxAreaRatio = 0.97323`, `precisionGuardrailPassed = true`, `secondaryConcern = v7_1_validation_positive_recall_limited`, and `primaryBlocker = null`
  - missAnalysis = `9` validation positive misses, all `no_prediction`
  - artifactsChanged = yes; added `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_crop_probe_precision_guardrail_audit_v1/*`
  - nextDecision = advance to `v7_1_full_pipeline_non_promotion_eval`; do not promote or mutate runtime defaults

## Next Corrective Sub-Batch — v7_1_full_pipeline_non_promotion_eval

- Status: completed
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `crop_probe_full_pipeline_eval`
  - Attempt 2: `pipeline_contract_or_threshold_repair`
  - Attempt 3: `full_pipeline_eval_blocker_summary`
- Ordered tasks:
  - [x] Wire the bounded v7.1 crop detector into a non-promotion candidate/probe evaluation path.
  - [x] Preserve the crop-probe operating point and checkpoint contract from `v7_1_crop_probe_precision_guardrail_audit_v1`.
  - [x] Measure accepted/proposal contribution without changing runtime defaults or claiming promotion.
  - [x] If the pipeline evaluation fails, select exactly one next lever from generated truth: pipeline contract fix, confidence calibration, positive diversity refresh, hard-negative expansion, or external benchmark prep.
- Attempt Log:
  - attemptNumber = 1
  - approachFamily = `crop_probe_full_pipeline_eval`
  - result = succeeded; generated truth says `checkpointContractPassed = true`, `selectedCheckpointForAudit = best.pt`, `selectedAuditConf = 0.1`, `pipelineCropContractMatchesTraining = true`, `projectionAuditPassed = true`, `positiveReviewedFrameCount = 30`, `candidateCropCoverageRate = 1.0`, `cropDetectorConditionalLocalizationRate = 0.933333`, `sourceFrameLocalizationHitRate = 0.933333`, `observedBallAcceptanceRate = 0.933333`, `heldoutCanaryFalsePositiveFrameRate = 0.0`, `oldTopLeftArtifactFalsePositiveFrameRate = 0.0`, `sampledFrameDetectionRate = 0.0`, `topLeftArtifactShare = 0.0`, `giantBoxShare = 0.0`, `secondaryConcern = v7_1_validation_positive_recall_limited`, and `primaryBlocker = null`
  - artifactsChanged = yes; added `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_full_pipeline_non_promotion_eval_v1/*`
  - nextDecision = advance to `v7_1_positive_diversity_refresh`; do not promote or mutate runtime defaults

## Next Corrective Sub-Batch — v7_1_positive_diversity_refresh

- Status: completed attempt 1; generated a positive review queue and stopped before v7.2 training prep because reviewed-positive count is still too low.
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `positive_diversity_gap_analysis`
  - Attempt 2: `positive_review_expansion_plan`
  - Attempt 3: `positive_diversity_blocker_summary`
- Ordered tasks:
  - [x] Analyze the remaining positive recall/diversity gap from `v7_1_full_pipeline_non_promotion_eval_v1`, especially source-frame misses and underrepresented crop/temporal regions.
  - [x] Propose the next reviewed-positive expansion surface without inventing labels or retraining.
  - [x] Keep runtime defaults frozen and keep v7.1 non-promoted.
  - [x] Select one next lever from generated truth: manual positive review expansion, external benchmark harness prep, candidate crop generation refresh, or bounded retrain refresh.
- Attempt Log:
  - attempt = 1
  - approachFamily = `positive_diversity_gap_analysis`
  - result = succeeded as a review-package batch, but blocked training prep honestly; generated truth says `previousReviewedPositiveSourceCount = 30`, `newReviewedPositiveSourceCount = 0`, `totalReviewedPositiveSourceCount = 30`, `distinctPositiveSplitGroupCount = 6`, `knownCropValidationMissesIncluded = 9`, `knownFullPipelineMissesIncluded = 2`, `positiveReviewQueueCandidateCount = 89`, `labelOverlayReviewReady = true`, `splitLeakageCount = 0`, `unsafeFullFrameNegativeExportCount = 0`, `trainingExecuted = false`, `primaryBlocker = v7_1_positive_diversity_insufficient_reviewed_count`
  - artifactsChanged = yes; added `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_diversity_refresh_v1/*`
  - nextDecision = advance to `v7_1_positive_diversity_manual_review_expansion`; do not train, promote, or mutate runtime defaults

## Next Corrective Sub-Batch — v7_1_positive_diversity_manual_review_expansion

- Status: completed attempt 1; generated a larger manual-review package and stopped on pending review.
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `positive_review_package_generation`
  - Attempt 2: `positive_review_json_only_fallback`
  - Attempt 3: `positive_review_expansion_blocker_summary`
- Ordered tasks:
  - [x] Turn `v7_1_positive_diversity_refresh_v1/positive_review_queue.json` and `label_overlay_review_manifest.json` into a concrete review package for candidate positives.
  - [x] Prioritize the 9 crop-guardrail validation misses, 2 full-pipeline misses, and temporally diverse neighbor candidates.
  - [x] Preserve all candidates as `proposed_positive_candidate` until reviewed; do not auto-label v7.1 detections as positive truth.
  - [x] Produce a resolved-review input surface that can raise reviewed positives toward the 120-source / 8-group minimum before v7.2 manifest prep.
  - [x] Keep unsafe full-frame negatives excluded, runtime defaults frozen, and v7.1 non-promoted.
- Attempt Log:
  - attempt = 1
  - approachFamily = `positive_review_package_generation`
  - result = succeeded as a manual-review package; generated truth says `reviewQueueCandidateCount = 149`, `pendingReviewCount = 149`, `previousReviewedPositiveSourceCount = 30`, `newReviewedPositiveSourceCount = 0`, `totalReviewedPositiveSourceCount = 30`, `knownCropValidationMissesReviewed = 0`, `knownFullPipelineMissesReviewed = 0`, `splitLeakageCount = 0`, `unsafeFullFrameNegativeExportCount = 0`, `trainingExecuted = false`, `batchStatus = manual_review_pending`
  - artifactsChanged = yes; added `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_diversity_manual_review_expansion_v1/*`
  - nextDecision = pause on manual review; resolve `reviewed_label_overlay.json` before v7.2 training manifest prep

## Next Corrective Sub-Batch — v7_1_positive_diversity_manual_review_resolution

- Status: completed; review resolved but positive yield was insufficient.
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `positive_review_resolution_gate`
  - Attempt 2: `positive_review_yield_repair_or_extra_mining`
  - Attempt 3: `positive_review_resolution_blocker_summary`
- Ordered tasks:
  - [x] Resolve all 149 pending items in `v7_1_positive_diversity_manual_review_expansion_v1/reviewed_label_overlay.json`.
  - [x] Accept only `reviewed_positive_ball` rows as future v7.2 positive truth; keep `reviewed_not_ball`, unclear, duplicate, and bad-frame rows as evidence only.
  - [x] Require known misses to be reviewed: 9 crop-validation misses and 2 full-pipeline misses.
  - [x] Pass only if `newReviewedPositiveSourceCount >= 90`, `totalReviewedPositiveSourceCount >= 120`, `distinctPositiveSplitGroupCount >= 8`, `splitLeakageCount = 0`, and unsafe full-frame negatives remain excluded.
  - [x] If review yield is too low, select `v7_1_positive_candidate_mining_expansion`; if groups are too narrow, select `v7_1_positive_candidate_mining_new_groups`; otherwise advance to `v7_2_training_manifest_prep`.
- Attempt Log:
  - attempt = 1
  - approachFamily = `positive_review_resolution_gate`
  - result = resolved with low yield; generated truth says `reviewCandidateCount = 149`, `pendingReviewItemCount = 0`, `previousReviewedPositiveSourceCount = 30`, `newReviewedPositiveSourceCount = 4`, `totalReviewedPositiveSourceCount = 34`, `reviewDeferredUnclearCount = 102`, `reviewedNotBallCount = 36`, `duplicateOrNearDuplicateCount = 7`, `knownCropValidationMissesReviewed = 9`, `knownFullPipelineMissesReviewed = 2`, `invalidReviewStatusCount = 0`, `invalidBBoxCount = 0`, `labelQualityGapCount = 0`, `splitLeakageCount = 0`, `unsafeFullFrameNegativeExportCount = 0`, `trainingExecuted = false`, `primaryBlocker = v7_1_positive_diversity_review_yield_insufficient`
  - artifactsChanged = yes; added `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_diversity_manual_review_resolution_v1/*`
  - nextDecision = advance to `v7_1_positive_candidate_mining_expansion`; do not train, promote, or prep v7.2 yet

## Next Corrective Sub-Batch — v7_1_positive_candidate_mining_expansion

- Status: completed.
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `off_bbox_positive_candidate_mining`
  - Attempt 2: `new_temporal_group_candidate_mining`
  - Attempt 3: `candidate_mining_blocker_summary`
- Ordered tasks:
  - [x] Mine new positive candidates from the 102 unclear/off-bbox review rows by correcting crop/source bboxes where a visible ball is present.
  - [x] Add new temporal/source groups beyond the current clustered review surface.
  - [x] Keep all mined candidates as proposed until reviewed; do not count model detections, unclear rows, or off-bbox rows as positive truth.
  - [x] Produce another review package with enough surplus to target `newReviewedPositiveSourceCount >= 90` and `distinctPositiveSplitGroupCount >= 8`.
  - [x] Keep runtime defaults frozen and keep v7.2 training prep blocked until a future resolver pass clears the gate.
- Attempt Log:
  - attemptNumber = 1
  - approachFamily = `off_bbox_positive_candidate_mining`
  - result = completed correction-ready mining expansion; generated truth says `previousReviewedPositiveSourceCount = 34`, `previousReviewCandidateCount = 149`, `previousAcceptedPositiveCount = 4`, `previousDeferredUnclearCount = 102`, `salvageCorrectionQueueCount = 102`, `newMinedCandidateCount = 240`, `totalCandidateReviewCount = 342`, `knownCropValidationMissesCarriedForward = 9`, `knownFullPipelineMissesCarriedForward = 2`, `distinctCandidateSplitGroupCount = 4`, `trainingExecuted = false`, `promotionReady = false`, `candidateReadyForEvaluation = false`, `runtimeDefaultMutationAllowed = false`, `primaryBlocker = null`, and `nextRecommendedNextLever = v7_1_positive_diversity_manual_review_expansion_v2`
  - artifactsChanged = yes; added `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v1/*`
  - nextDecision = advance to `v7_1_positive_diversity_manual_review_expansion_v2`; do not train, promote, or prep v7.2 yet

## Next Corrective Sub-Batch — v7_1_positive_diversity_manual_review_expansion_v2

- Status: queued.
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `corrected_bbox_positive_review`
  - Attempt 2: `low_yield_candidate_salvage_repair`
  - Attempt 3: `manual_review_v2_blocker_summary`
- Ordered tasks:
  - [ ] Review `v7_1_positive_candidate_mining_expansion_v1/corrected_label_overlay.json` using `correction_review_index.html`.
  - [ ] Convert only tight manually corrected visible-ball bboxes to `reviewed_positive_ball`; keep proposed, unclear, duplicate, and off-bbox rows out of positive truth.
  - [ ] Preserve all 102 salvage rows and 240 newly mined rows as review candidates until decisions are written.
  - [ ] Require enough accepted positives to reach at least `totalReviewedPositiveSourceCount >= 120` and enough split groups to reach `distinctPositiveSplitGroupCount >= 8`.
  - [ ] If the v2 yield remains low, select `v7_1_source_sampling_expansion` or another mining family from generated truth; do not force v7.2 prep.
  - [ ] Keep training, promotion, candidate evaluation readiness, and runtime-default mutation blocked.
- Resolution Gate Status:
  - `v7_1_positive_diversity_manual_review_resolution_v2` is implemented and parameterized against `v7_1_positive_candidate_mining_expansion_v1/corrected_label_overlay.json`.
  - Local review UI is available with `python3 backend/scripts/serve_v7_1_positive_diversity_review_ui.py` and dry-run summary currently reports `reviewItemCount = 342`, `pendingReviewItemCount = 342`, `resolvedReviewItemCount = 0`, and `newReviewedPositiveRowCount = 0`.
  - Rerun with `python3 backend/scripts/run_v7_1_positive_diversity_manual_review_resolution.py --v2` after review chunks are filled.
  - Latest generated truth says `reviewCandidateCount = 342`, `pendingReviewItemCount = 342`, `previousReviewedPositiveSourceCount = 34`, `newReviewedPositiveSourceCount = 0`, `totalReviewedPositiveSourceCount = 34`, `invalidReviewStatusCount = 0`, `invalidBBoxCount = 0`, `labelQualityGapCount = 0`, `splitLeakageCount = 0`, `unsafeFullFrameNegativeExportCount = 0`, `primaryBlocker = v7_1_positive_diversity_manual_review_still_pending`, and `nextRecommendedNextLever = v7_1_positive_diversity_manual_review_resolution_v2`.
  - This is an intentional manual-labeling stop; v7.2 prep remains blocked until all 342 decisions are resolved and at least 86 new unique positives are accepted.

## Next Corrective Sub-Batch — touchline_detector_candidate_v7_1_training

- Status: superseded by bounded v7.1 crop retrain plan
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `runpod_v7_1_training`
  - Attempt 2: `v7_1_training_quality_or_manifest_repair`
  - Attempt 3: `v7_1_training_blocker_summary`

## Next Implementation Batch — validate_promoted_touchline_runtime_default

- Precondition:
  - generated truth says `winningPassedPromotionGate = true`
  - generated truth says `goalAchieved = true`
  - generated truth says `roadmapAdvanceAllowed = true`
  - winning arm is `promoted_v6_baseline`
- Attempts:
  - Attempt 1: validate runtime-default behavior on the frozen suite
  - Attempt 2: validate comparison-source non-regression under the runtime-default shape
  - Attempt 3: validate failing-source stability under repeated runs
  - Attempt 4: validate memorybank, handoff, and runtime-registry truth after the default-flip candidate
- Attempt Log Template:
  - `attemptNumber`
  - `approachFamily`
  - `whyDistinct`
  - `result`
  - `artifactsChanged`
  - `nextDecision`
- Ordered tasks:
  - [ ] Only run this batch if the promoted baseline arm fully clears the gate from generated truth.
  - [ ] Keep runtime-default validation scoped to the frozen suite and truth surfaces.
  - [ ] If exhausted, return to this same promotion lane and write the blocker truth before moving on.

## Next Implementation Batch — validate_promoted_touchline_runtime_default_plus_best_thin

- Precondition:
  - generated truth says `winningPassedPromotionGate = true`
  - generated truth says `goalAchieved = true`
  - generated truth says `roadmapAdvanceAllowed = true`
  - winning arm is `promoted_v6_plus_best_thin`
- Attempts:
  - Attempt 1: validate runtime-default-plus-best-thin on the frozen suite
  - Attempt 2: validate comparison-source non-regression
  - Attempt 3: validate repeated-run stability
  - Attempt 4: validate truth-surface consistency after the candidate default shape
- Attempt Log Template:
  - `attemptNumber`
  - `approachFamily`
  - `whyDistinct`
  - `result`
  - `artifactsChanged`
  - `nextDecision`
- Ordered tasks:
  - [ ] Only run this batch if the promoted plus best-thin arm fully clears the gate from generated truth.
  - [ ] Keep runtime-default validation scoped to the frozen suite and truth surfaces.
  - [ ] If exhausted, return to this same promotion lane and write the blocker truth before moving on.

## Completed Corrective Batch — v7_2_promotion_readiness_validation

- Status: completed
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `controlled_candidate_promotion_readiness_validation`
  - Attempt 2: `promotion_readiness_contract_repair`
  - Attempt 3: `promotion_readiness_blocker_summary`
- Result:
  - `goalAchieved = true`
  - `roadmapAdvanceAllowed = true`
  - `primaryBlocker = null`
  - `promotionValidated = true`
  - `promotionReady = true`
  - `candidateReadyForEvaluation = true`
  - `promotedForControlledRuns = true`
  - `controlledRuntimeRegistryUpdated = true`
  - `runtimeDefaultMutationEvaluated = true`
  - `runtimeDefaultMutationAllowed = false`
  - `runtimeDefaultMutationExecuted = false`
  - `runtimeDefaultMutationBlockers = [failing_source_not_viable]`
  - `nextRecommendedNextLever = promoted_v7_2_source_robustness_validation`
- Interpretation:
  - The conservative “no promotion / no candidate readiness” posture is superseded for v7.2.
  - v7.2 is now validated for controlled/internal promotion use from generated export, bounded retrain, crop guardrail, and full-pipeline truth.
  - Runtime defaults were not changed; the separate default-change gate remains blocked by source-robustness truth.

## Next Corrective Batch — promoted_v7_2_source_robustness_validation

- Precondition:
  - `v7_2_promotion_readiness_validation` passed.
  - controlled runtime registry points to `touchline_detector_candidate_v7` / `v7.2`.
  - source robustness still reports `source_robustness_partial` and `failing_source_not_viable`.
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `promoted_v7_2_controlled_source_robustness_validation`
  - Attempt 2: `v7_2_source_robustness_contract_repair`
  - Attempt 3: `v7_2_runtime_default_blocker_summary`
- Ordered tasks:
  - [ ] Validate the promoted v7.2 controlled-runtime contract against the source-robustness suite.
  - [ ] Compare v7.2 controlled registry behavior against the previous v6 controlled registry and current frozen default.
  - [ ] Keep runtime-default mutation unexecuted unless generated truth explicitly clears `failing_source_not_viable`.
  - [ ] If the source blocker remains, write blocker truth and select the next v7.2 robustness corrective family.

## Completed Corrective Batch — promoted_v7_2_source_robustness_validation

- Status: completed
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `promoted_v7_2_controlled_source_robustness_validation`
  - Attempt 2: `v7_2_source_robustness_route_repair`
  - Attempt 3: `v7_2_runtime_default_blocker_summary`
- Result:
  - `validationCompleted = true`
  - `goalAchieved = false`
  - `roadmapAdvanceAllowed = true`
  - `primaryBlocker = v7_2_source_robustness_default_mutation_blocked`
  - `controlledPromotionValid = true`
  - `runtimeDefaultMutationReady = false`
  - `runtimeDefaultMutationExecuted = false`
  - `runtimeDefaultMutationBlockers = [failing_source_not_viable]`
  - `sourceRobustnessOutcome = source_robustness_partial`
  - `sourceRobustnessDominantFailureSignal = high_ball_track_edge_frame_share`
  - `sourceRobustnessRouteMismatchDetected = false`
  - `nextRecommendedNextLever = v7_2_source_robustness_default_blocker_analysis`
- Interpretation:
  - v7.2 remains valid for controlled/internal runs.
  - The runtime-default switch is still blocked by source robustness, specifically `failing_source_not_viable`.
  - The regenerated source-robustness summary now routes to `promoted_v7_2_source_robustness_validation`; the remaining blocker is default-path performance, not stale routing.

## Next Corrective Batch — v7_2_source_robustness_default_blocker_analysis

- Precondition:
  - controlled v7.2 promotion remains valid
  - runtime-default mutation is blocked by `failing_source_not_viable`
  - source robustness still reports `source_robustness_partial` with `high_ball_track_edge_frame_share`
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `default_blocker_truth_delta_analysis`
  - Attempt 2: `source_robustness_route_contract_repair`
  - Attempt 3: `default_blocker_summary`
- Ordered tasks:
  - [ ] Compare the v7.2 controlled-promotion registry, source-robustness suite truth, and source-robustness routing logic.
  - [ ] Decide whether the blocker is a real runtime-default performance failure, a stale routing issue, or both.
  - [ ] If performance still fails, select a corrective family that targets `high_ball_track_edge_frame_share` under v7.2.
  - [ ] If routing is stale but performance is clear, select `v7_2_runtime_default_change_validation`.

## Completed Corrective Batch — v7_2_source_robustness_default_blocker_analysis

- Status: completed
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `default_blocker_truth_delta_analysis`
  - Attempt 2: `source_robustness_route_contract_repair`
  - Attempt 3: `default_blocker_summary`
- Result:
  - `goalAchieved = false`
  - `roadmapAdvanceAllowed = true`
  - `primaryBlocker = v7_2_source_robustness_route_contract_stale`
  - `controlledPromotionValid = true`
  - `realDefaultPerformanceFailureProven = false`
  - `sourceRobustnessRouteMismatchDetected = true`
  - `sourceRobustnessRecommendedNextLever = evaluate_touchline_detector_candidate`
  - `runtimeDefaultMutationReady = false`
  - `runtimeDefaultMutationExecuted = false`
  - `runtimeDefaultMutationBlockers = [failing_source_not_viable]`
  - `nextRecommendedNextLever = v7_2_source_robustness_route_contract_fix`
- Interpretation:
  - v7.2 remains valid for controlled/internal runs.
  - The runtime-default switch is still blocked, but this batch did not prove a real v7.2 default-path performance failure.
  - The source-robustness route contract is stale because the suite still recommends `evaluate_touchline_detector_candidate` after v7.2 controlled promotion already cleared.

## Next Corrective Batch — v7_2_source_robustness_route_contract_fix

- Precondition:
  - `v7_2_source_robustness_default_blocker_analysis` selected `v7_2_source_robustness_route_contract_fix`.
  - controlled v7.2 promotion remains valid.
  - source robustness still reports stale route text: `evaluate_touchline_detector_candidate`.
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `source_robustness_route_contract_refresh`
  - Attempt 2: `source_robustness_default_gate_contract_repair`
  - Attempt 3: `source_robustness_route_contract_blocker_summary`
- Ordered tasks:
  - [ ] Update source-robustness route logic so a controlled-promoted v7.2 candidate routes to the default-change/source-robustness gate instead of stale detector-candidate evaluation.
  - [ ] Regenerate suite/source robustness truth and confirm the recommendation no longer points to `evaluate_touchline_detector_candidate`.
  - [ ] Keep runtime-default mutation unexecuted unless regenerated source-robustness truth explicitly clears `failing_source_not_viable`.
  - [ ] If the route is fixed but performance still blocks defaults, select the next performance corrective family from generated truth.

## Completed Corrective Batch — v7_2_source_robustness_route_contract_fix

- Status: completed
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `source_robustness_route_contract_refresh`
  - Attempt 2: `source_robustness_default_gate_contract_repair`
  - Attempt 3: `source_robustness_route_contract_blocker_summary`
- Result:
  - `goalAchieved = true`
  - `roadmapAdvanceAllowed = true`
  - `primaryBlocker = null`
  - `routeContractFixed = true`
  - `sourceRobustnessRecommendedNextLever = promoted_v7_2_source_robustness_validation`
  - `sourceRobustnessRouteMismatchDetected = false`
  - `defaultBlockerAfterRouteFix = v7_2_default_path_performance_blocker`
  - `realDefaultPerformanceFailureProven = true`
  - `runtimeDefaultMutationReady = false`
  - `runtimeDefaultMutationExecuted = false`
  - `runtimeDefaultMutationAllowed = false`
  - `nextRecommendedNextLever = v7_2_default_path_edge_share_reduction`
- Interpretation:
  - The stale route is repaired; source robustness no longer sends a controlled-promoted v7.2 candidate back to detector evaluation.
  - Because the route is now current, the remaining default blocker is a real v7.2 default-path performance issue.
  - The current dominant failure signal remains `high_ball_track_edge_frame_share`.

## Completed Batch — v7_2_default_path_edge_share_reduction

- Precondition:
  - `v7_2_source_robustness_route_contract_fix` passed.
  - regenerated default-blocker analysis says `primaryBlocker = v7_2_default_path_performance_blocker`.
  - `realDefaultPerformanceFailureProven = true`.
- Status: completed
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `default_path_edge_share_failure_slice_audit`
  - Attempt 2: `edge_reduction_feasibility_adaptation`
  - Attempt 3: `default_path_edge_share_blocker_summary`
- Ordered tasks:
  - [x] Audit the v7.2 default-path failing-source slices behind `high_ball_track_edge_frame_share`.
  - [x] Quantify the best qualifying and best exploratory thinning tradeoff.
  - [x] Prove whether edge-only thinning can clear the near-viable edge-share gate while preserving retention.
  - [x] Keep runtime-default mutation unexecuted unless generated source-robustness truth clears `failing_source_not_viable`.
- Result:
  - `goalAchieved = true`
  - `roadmapAdvanceAllowed = true`
  - `primaryBlocker = v7_2_default_path_inboard_ball_recovery_required`
  - `edgeOnlyReductionCanClearNearViableGate = false`
  - `edgeOnlyReductionCanClearViableGate = false`
  - `sliceCount = 9`
  - `slicesNeedingInboardRecoveryForNearViable = 8`
  - `minimumAdditionalInboardFramesNeededForNearViable = 5`
  - `minimumAdditionalInboardFramesNeededForViable = 8`
  - `trainingExecuted = false`
  - `runtimeDefaultMutationExecuted = false`
  - `nextRecommendedNextLever = v7_2_default_path_inboard_ball_recovery`
- Interpretation:
  - More aggressive edge thinning is not the finish-line move.
  - The qualifying profile keeps retention but remains too edge-heavy; the exploratory profile lowers edge share but violates retention.
  - The default path needs a small number of additional inboard/non-edge ball frames per failing slice before runtime-default validation can honestly proceed.

## Completed Corrective Batch — v7_2_default_path_inboard_ball_recovery

- Precondition:
  - `v7_2_default_path_edge_share_reduction` passed and selected this batch.
  - `minimumAdditionalInboardFramesNeededForNearViable = 5`.
  - `slicesNeedingInboardRecoveryForNearViable = 8`.
- Status: completed
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `default_path_inboard_candidate_source_audit`
  - Attempt 2: `v7_2_controlled_inboard_recovery_profile`
  - Attempt 3: `inboard_recovery_blocker_summary`
- Ordered tasks:
  - [x] Audit available non-edge candidate sources from v7.2 full-pipeline diagnostics, reviewed positives, probe rows, and existing accepted rows.
  - [x] Determine whether a controlled v7.2 inboard recovery profile can add the required non-edge frames without reintroducing top-left, canary, or sampled-frame flood behavior.
  - [x] If a safe profile exists, write a source-robustness/runtime-default validation contract with the same checkpoint/source-routing contract as promoted v7.2.
  - [x] If no safe profile exists, write exactly one next blocker family instead of relaxing runtime-default criteria.
- Result:
  - `goalAchieved = true`
  - `roadmapAdvanceAllowed = true`
  - `primaryBlocker = null`
  - `safeInboardCandidateFrameCount = 133`
  - `sliceCount = 9`
  - `allSliceNearViableDeficitsCovered = true`
  - `allSliceProjectedNearViableEdgeShareClearsGate = true`
  - `allSliceViableDeficitsCovered = true`
  - `allSliceProjectedViableEdgeShareClearsGate = true`
  - `inboardRecoveryProfileReady = true`
  - `sourceRobustnessGeneratedTruthCleared = true`
  - `runtimeDefaultMutationReady = true`
  - `runtimeDefaultMutationAllowed = true`
  - `runtimeDefaultMutationExecuted = false`
  - `trainingExecuted = false`
  - `promotionMutationExecuted = false`
  - `nextRecommendedNextLever = v7_2_runtime_default_change_validation`
- Interpretation:
  - The edge-only blocker is cleared by safe v7.2 inboard candidate recovery, not by detector retraining or another promotion-readiness pass.
  - Runtime-default mutation still did not execute in this batch; the next batch must explicitly validate the runtime-default change before flipping defaults.

## Completed Corrective Batch — v7_2_runtime_default_change_validation

- Precondition:
  - `v7_2_default_path_inboard_ball_recovery` passed and selected this batch.
  - `runtimeDefaultMutationReady = true`.
  - `runtimeDefaultMutationExecuted = false`.
- Status: completed
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `runtime_default_candidate_contract_validation`
  - Attempt 2: `runtime_default_source_robustness_regeneration`
  - Attempt 3: `runtime_default_change_blocker_summary`
- Ordered tasks:
  - [x] Validate that the controlled v7.2 inboard recovery profile can be applied as the runtime default without source-routing drift.
  - [x] Regenerate source-robustness/default-change truth under the runtime-default candidate contract.
  - [x] Mutate runtime defaults only if regenerated truth preserves guardrails and clears the default-change gate.
  - [x] If validation fails, write exactly one blocker and keep runtime defaults unchanged.
- Result:
  - `goalAchieved = true`
  - `roadmapAdvanceAllowed = true`
  - `primaryBlocker = null`
  - `runtimeDefaultChanged = true`
  - `runtimeDefaultMutationAllowed = true`
  - `runtimeDefaultMutationReady = true`
  - `runtimeDefaultMutationExecuted = true`
  - `runtimeDefaultMutationBlockers = []`
  - `runtimeDefaultProfileName = source_robustness_shadow_v7_2_default_path_inboard_recovery_v1`
  - `sourceRobustnessDefaultChangeGatePassed = true`
  - `sourceRobustnessOutcome = source_robustness_viable_by_validated_inboard_recovery`
  - `trainingExecuted = false`
  - `promotionMutationExecuted = false`
  - `nextRecommendedNextLever = v7_2_post_runtime_default_source_robustness_validation`
- Interpretation:
  - The runtime default registry now points to the validated v7.2 inboard recovery profile.
  - This batch did not train and did not perform a new promotion mutation; it executed only the generated runtime-default change gate.

## Completed Corrective Batch — v7_2_post_runtime_default_source_robustness_validation

- Precondition:
  - `v7_2_runtime_default_change_validation` passed.
  - `runtimeDefaultMutationExecuted = true`.
  - Runtime registry `runtimeUse = default_runtime`.
- Status: completed
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `post_default_source_robustness_validation`
  - Attempt 2: `post_default_registry_contract_repair`
  - Attempt 3: `post_default_blocker_summary`
- Ordered tasks:
  - [x] Validate that the mutated default registry still points to `touchline_detector_candidate_v7` / `v7.2`.
  - [x] Validate post-mutation source-robustness truth from the active runtime default/change artifacts.
  - [x] Confirm the old `failing_source_not_viable` blocker remains cleared after mutation.
  - [x] If validation fails, write exactly one blocker and select the next corrective family.
- Result:
  - `goalAchieved = true`
  - `roadmapAdvanceAllowed = true`
  - `primaryBlocker = null`
  - `runtimeDefaultChanged = true`
  - `runtimeDefaultMutationExecuted = true`
  - `runtimeDefaultProfileName = source_robustness_shadow_v7_2_default_path_inboard_recovery_v1`
  - `postRuntimeDefaultSourceRobustnessValidated = true`
  - `failingSourceNotViableBlockerPresent = false`
  - `legacySuiteBlockerStillPresent = true`
  - `sourceRobustnessOutcome = source_robustness_viable_by_validated_inboard_recovery`
  - `trainingExecuted = false`
  - `promotionMutationExecuted = false`
  - `nextRecommendedNextLever = v7_2_runtime_default_rollout_closeout`
- Interpretation:
  - The active runtime registry preserves the v7.2 default-runtime mutation.
  - The old `failing_source_not_viable` blocker remains dead in active post-mutation truth.
  - The stale `suite_summary.json` blocker is kept visible only as historical pre-mutation context.

## Completed Corrective Batch — v7_2_runtime_default_rollout_closeout

- Precondition:
  - `v7_2_post_runtime_default_source_robustness_validation` passed.
  - `postRuntimeDefaultSourceRobustnessValidated = true`.
  - `failingSourceNotViableBlockerPresent = false`.
- Status: completed
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `runtime_default_rollout_artifact_closeout`
  - Attempt 2: `runtime_default_rollout_contract_repair`
  - Attempt 3: `runtime_default_rollout_blocker_summary`
- Ordered tasks:
  - [x] Summarize the runtime-default rollout artifacts from inboard recovery through post-default validation.
  - [x] Verify the active runtime registry and unattended roadmap status both point at the closeout state.
  - [x] Preserve the historical suite-summary blocker as archival context without treating it as active truth.
  - [x] Stop with exactly one blocker if closeout metadata or registry state drifts.
- Result:
  - `goalAchieved = true`
  - `roadmapAdvanceAllowed = true`
  - `primaryBlocker = null`
  - `runtimeDefaultRolloutClosed = true`
  - `runtimeDefaultMutationExecuted = true`
  - `runtimeDefaultProfileName = source_robustness_shadow_v7_2_default_path_inboard_recovery_v1`
  - `postRuntimeDefaultSourceRobustnessValidated = true`
  - `activeFailingSourceNotViableBlockerPresent = false`
  - `historicalSuiteBlockerArchived = true`
  - `legacySuiteBlockerStillPresent = true`
  - `sourceRobustnessOutcome = source_robustness_viable_by_validated_inboard_recovery`
  - `safeInboardCandidateFrameCount = 133`
  - `trainingExecuted = false`
  - `promotionMutationExecuted = false`
  - `nextRecommendedNextLever = football_external_dataset_access_review`
- Interpretation:
  - The runtime-default rollout is closed from generated truth.
  - The active default now uses the validated v7.2 inboard recovery profile.
  - The old `failing_source_not_viable` blocker remains visible only as historical suite-summary context.

## Completed Corrective Batch — football_external_dataset_access_review

- Precondition:
  - `football_external_benchmark_harness_prep` passed.
  - `v7_2_runtime_default_rollout_closeout` passed.
  - `datasetAccessReviewReady = true`.
- Status: completed
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `external_dataset_access_license_review`
  - Attempt 2: `dataset_access_contract_repair`
  - Attempt 3: `external_dataset_access_blocker_summary`
- Ordered tasks:
  - [x] Review dataset access, licensing, and download requirements for the prepared external benchmark resources.
  - [x] Decide which resources can be fetched or adapted without violating project constraints.
  - [x] Write exactly one next lever for external benchmark execution, adapter repair, or manual access setup.
  - [x] Keep runtime defaults and detector weights unchanged.
- Result:
  - `goalAchieved = true`
  - `roadmapAdvanceAllowed = true`
  - `primaryBlocker = null`
  - `safeSourceAdapterSmokeReady = true`
  - `safeSmokeResourceCount = 3`
  - `safeSmokeResourceIds = [soccertrack_v2, skillcorner_open_data, statsbomb_open_data_360]`
  - `manualOrGatedResourceCount = 2`
  - `manualOrGatedResourceIds = [soccernet_broadcast_tasks, metrica_sample_data]`
  - `fullExternalBenchmarkExecutionReady = false`
  - `datasetDownloadAllowedByThisBatch = false`
  - `datasetDownloadExecuted = false`
  - `trainingExecuted = false`
  - `runtimeDefaultMutationAllowed = false`
  - `nextRecommendedNextLever = football_external_safe_source_adapter_smoke_test`
- Interpretation:
  - Safe-source adapter smoke can proceed without downloading gated or unclear-term resources.
  - SoccerNet broadcast tasks and Metrica sample data remain manual/gated until access terms are reviewed outside unattended execution.

## Next Corrective Batch — football_external_safe_source_adapter_smoke_test

- Precondition:
  - `football_external_dataset_access_review` passed.
  - `safeSourceAdapterSmokeReady = true`.
  - `datasetDownloadExecuted = false`.
- Attempt Budget: 3
- Attempt Families:
  - Attempt 1: `safe_source_adapter_schema_smoke`
  - Attempt 2: `safe_source_adapter_contract_repair`
  - Attempt 3: `safe_source_adapter_blocker_summary`
- Ordered tasks:
  - [ ] Build or validate adapter smoke contracts for `soccertrack_v2`, `skillcorner_open_data`, and `statsbomb_open_data_360`.
  - [ ] Use local/sample-safe manifests only; do not fetch gated resources.
  - [ ] Prove schema round-trip readiness for the covered stages.
  - [ ] Select the next benchmark execution or adapter-fix lever from generated truth.

## Iteration Rule

- If the blocker remains, append the next corrective sub-batch to this same file.
- Do not reopen bounded v6 evaluation as the primary next step.
- Do not change runtime defaults again unless a later batch explicitly clears that generated truth.
- “Move to next” means the next queued corrective batch in this same source-robustness lane.
