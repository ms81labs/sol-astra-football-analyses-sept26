# Active Roadmap — Touchline Detector Candidate Evaluation

> **Canonical product spine:** use `origin/main` as the baseline and treat `/root/WorkSpace/fotball-analyst` as the live product tree. Archived fork-specific material from the cleanup pass lives under `archive/2026-04-21-mainline-reset/`.

## Summary

- The single-clip proof floor is now coherent and reproducible.
- The active problem is no longer detector/plumbing churn on one clip.
- The active problem is still multi-source robustness on the frozen viable baseline.
- The current truthful suite verdict is `baseline_not_robust`.
- The regenerated source-conditioned lane currently reads as `source_robustness_partial`.

Frozen baseline:

- detector: `yolov10n.pt`
- primary mode: `anchored_player_ranked_context_960`
- kept cleanup lane: `recent_ball_plus_inward_anchor_center_bias35_960`

## Current Truth

Canonical proof floor from the repaired single-clip bundle:

- artifact: [proof_summary.json](/root/WorkSpace/fotball-analyst/backend/storage/pod_cycles/controlled-possession-assignment-treatment-20260420-rerun3/proof_summary.json)
- `acceptedBallFrames = 174`
- `controlledPossessionFrames = 137`
- `ballTrackViable = true`
- `ballTrackEdgeFrameShare = 0.586`
- `longGapTreatmentOutcome = long_gap_treatment_partial`
- `controlledPossessionAssignmentOutcome = controlled_possession_assignment_weak`

Canonical multi-source status:

- partial import batch: [import_summary.json](/root/WorkSpace/fotball-analyst/backend/storage/benchmark_suites/clip_manifest_expansion_20260421Tpod001/import_summary.json)
- refreshed suite: [suite_summary.json](/root/WorkSpace/fotball-analyst/backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/suite_summary.json)
- generated lane snapshot: [active_lane_snapshot.json](/root/WorkSpace/fotball-analyst/backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/active_lane_snapshot.json)
- source robustness matrix: [primary_source_robustness_matrix.json](/root/WorkSpace/fotball-analyst/backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/primary_source_robustness_matrix.json)
- frontier diagnosis: [primary_source_robustness_frontier.json](/root/WorkSpace/fotball-analyst/backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/primary_source_robustness_frontier.json)
- failure audit: [primary_source_robustness_failure_audit.json](/root/WorkSpace/fotball-analyst/backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/primary_source_robustness_failure_audit.json)
- detector breadth: [detector_breadth_matrix.json](/root/WorkSpace/fotball-analyst/backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/detector_breadth_matrix.json)
- `successfulImports = 1`
- `distinctSourceClipCount = 2`
- `suiteVerdict = baseline_not_robust`
- `sourceRobustnessActiveConfigName = source_robustness_baseline_current`
- `sourceRobustnessBestConfigName = source_robustness_shadow_edge_run_keep_every_2_min10`
- `sourceRobustnessBestExploratoryConfigName = source_robustness_shadow_edge_run_keep_every_3_min10`
- `sourceRobustnessOutcome = source_robustness_partial`
- `sourceRobustnessImprovedSourceClipId = trimed-5min.mp4`
- `sourceRobustnessPromotionBlockers = [failing_source_not_viable]`
- `sourceRobustnessRecommendedNextLever = start_phase_1b_review_densification`
- `sourceRobustnessDiagnosis.plateauDetected = true`
- `sourceRobustnessDiagnosis.bestFrontierConfigName = source_robustness_frontier_keep_every_4_min14`
- `sourceRobustnessDiagnosis.exploratoryStrongConfigCount = 0`
- `sourceRobustnessDiagnosis.touchlineReplacementCandidateName = source_robustness_shadow_touchline_probe_replace_v1`
- `sourceRobustnessDiagnosis.touchlineReplacementFalsified = true`
- `sourceRobustnessDiagnosis.touchlineReplacementRunsConsidered = 25`
- `sourceRobustnessDiagnosis.touchlineReplacementRunsAccepted = 0`
- `sourceRobustnessDiagnosis.touchlineReplacementMedianCoverageRatio = 0.6`
- `sourceRobustnessDiagnosis.acquisitionCandidateName = source_robustness_shadow_touchline_candidate_admission_reopen_v3`
- `sourceRobustnessDiagnosis.acquisitionCandidateFalsified = true`
- `sourceRobustnessDiagnosis.acquisitionCandidateBeatsBestThinCandidate = false`
- `sourceRobustnessDiagnosis.acquisitionCandidateTouchlineModeEntered = true`
- `sourceRobustnessDiagnosis.acquisitionCandidateTouchlineEscapeWindowFrames = 7473`
- `sourceRobustnessDiagnosis.acquisitionCandidateTouchlineInboardWindowFrames = 0`
- `sourceRobustnessDiagnosis.acquisitionCandidateWindowKindCounts = {touchline_escape: 6829}`
- `sourceRobustnessDiagnosis.acquisitionCandidateRejectionBlockerCounts = {edge_share_not_improved: 7473}`
- `sourceRobustnessDiagnosis.acquisitionCandidateZeroTouchlineCandidateReasonCounts = {no_touchline_candidates_available: 109}`
- `sourceRobustnessDiagnosis.acquisitionCandidateReopenedRawCandidateFrames = 6803`
- `sourceRobustnessDiagnosis.acquisitionCandidateReopenedRawCandidateSelectedFrames = 6723`
- `sourceRobustnessDiagnosis.combinedReopenDiagnosis.localWinningDetectorModelPath = yolov10n.pt`
- `sourceRobustnessDiagnosis.combinedReopenDiagnosis.localWinningAcquisitionStrategyName = source_robustness_shadow_touchline_acquisition_upgrade_v1`
- `sourceRobustnessDiagnosis.combinedReopenDiagnosis.combinedReopenFalsified = true`
- `detectorBreadthDiagnosis.screenWinningDetectorModelPath = yolov10n.pt`
- `detectorBreadthDiagnosis.remoteWinningDetectorModelPath = yolov10n.pt`
- `detectorBreadthDiagnosis.baselineRemoteBeatsPlateau = false`
- `detectorBreadthDiagnosis.compoundThinRemoteBeatsPlateau = false`
- `detectorBreadthDiagnosis.detectorBreadthFalsified = true`
- `trainingPrepDiagnosis.trainingPrepBatchName = touchline_training_data_curation_foundation`
- `trainingPrepDiagnosis.representativeFailingMatchId = 1c8136cda03240aa8324f676c9bbf99a`
- `trainingPrepDiagnosis.representativeControlMatchId = 1d67fa87080446a0a777901aace43809`
- `trainingPrepDiagnosis.curationUnitCount = 2`
- `trainingPrepDiagnosis.seededIssueCount = 2`
- `trainingPrepDiagnosis.positiveSeedExampleCount = 37`
- `trainingPrepDiagnosis.negativeSeedExampleCount = 6`
- `trainingPrepDiagnosis.yoloExportReady = true`
- `trainingPrepDiagnosis.readyForDetectorTraining = true`
- `detectorTrainingDiagnosis.trainingCandidateName = touchline_detector_candidate_v1`
- `detectorTrainingDiagnosis.trainingBatchName = touchline_detector_candidate_training_v1`
- `detectorTrainingDiagnosis.trainingCompleted = true`
- `detectorTrainingDiagnosis.weightsReady = true`
- `detectorTrainingDiagnosis.evaluationContractReady = true`
- `detectorTrainingDiagnosis.readyForDetectorEvaluation = true`
- `detectorTrainingDiagnosis.baseModelPath = yolov10n.pt`
- `detectorTrainingDiagnosis.heldOutSplitAssessment = limited_single_control_source`

## Active Lane

The active engineering lane is:

`Frozen-Baseline Phase 1B Review Densification`

That means:

- keep the frozen baseline fixed
- keep the regenerated suite, diagnosis, and active-lane snapshot canonical
- keep the regenerated frontier and failure-audit artifacts canonical too
- diagnose why `trimed-5min.mp4` remains edge-heavy and non-viable while `trimed-football-2-1minute.mp4` is viable
- treat the thinning family as falsified on the current saved suite
- hold the active runtime config at the baseline until a candidate clears promotion blockers
- treat both the touchline probe-replacement and touchline acquisition-upgrade mechanisms as falsified
- treat the combined detector/candidate-source reopen attempt as falsified too
- treat the touchline candidate-admission reopen attempt as falsified too
- treat the bounded detector-breadth batch as falsified on the current failing-source reference
- treat touchline training-data curation foundation and the first detector training batch as complete
- treat the first detector-candidate evaluation batch as complete and falsified
- move into Phase 1B review densification instead of another round of post-acceptance repair, acquisition-window retuning, or immediate detector reevaluation

Current source-level read:

- `trimed-5min.mp4` still dominates the non-robust side of the baseline suite
- `source_robustness_shadow_edge_run_keep_every_2_min10` is now the best qualifying candidate, but it is still blocked by `failing_source_not_viable`
- `source_robustness_shadow_edge_run_keep_every_3_min10` is now the best exploratory candidate, but it still fails accepted and controlled retention guardrails
- `source_robustness_frontier_keep_every_4_min14` is the best non-catalog frontier candidate, but it still does not strictly beat the best qualifying catalog candidate across improvement plus both retention ratios
- the new support-aware shadow family stayed `source_robustness_weak` with `0.0` failing-source edge-share improvement
- the new touchline probe-replacement shadow mechanism is now also falsified:
  the local suite records `25` runs considered, `0` accepted, and only `candidate_edge_share_improvement_insufficient` rejection blockers
- the real pod-backed acceptance proof at [touchline-probe-replace-v1-acceptance-20260421](/root/WorkSpace/fotball-analyst/backend/storage/pod_cycles/touchline-probe-replace-v1-acceptance-20260421) considered `3` dominant failing windows and accepted `0` replacements
- the new touchline acquisition-upgrade shadow mechanism is now also falsified:
  the local suite records `acquisitionCandidateFalsified = true`, empty acquisition window counts, and only `candidate_edge_share_improvement_insufficient` blocker counts
- the real pod-backed acquisition proof at [touchline-acquisition-upgrade-v1-acceptance-20260421](/root/WorkSpace/fotball-analyst/backend/storage/pod_cycles/touchline-acquisition-upgrade-v1-acceptance-20260421) ran on `yolov10n.pt` and still ended at `101 / 98 / false / 0.812`
- that proof did not surface any touchline-escape acquisition path:
  `sourceConditionedAcquisitionDiagnostics.touchlineEscapeCandidateFrames = 0`
  `sourceConditionedAcquisitionDiagnostics.touchlineEscapeSelectedFrames = 0`
- the combined reopen proof at [combined-reopen-yolov10n-reopen-v2-acceptance-20260421](/root/WorkSpace/fotball-analyst/backend/storage/pod_cycles/combined-reopen-yolov10n-reopen-v2-acceptance-20260421) also lands at `101 / 98 / false / 0.812`
- that proof records `comparison.mechanismBeatsPlateau = true` but `comparison.productBeatsPlateau = false`
- the generated combined detector/candidate-source surface now records `combinedReopenFalsified = true`
- the new touchline candidate-admission reopen shadow mechanism is now falsified locally:
  the regenerated snapshot records `touchlineCandidateModeEntered = true`, `touchlineEscapeWindowFrames = 7473`, `touchlineInboardWindowFrames = 0`, `reopenedRawCandidateFrames = 6803`, `reopenedRawCandidateSelectedFrames = 6723`, and `zeroTouchlineCandidateReasonCounts = {no_touchline_candidates_available: 109}`
- the authoritative remote rerun at [touchline-candidate-admission-reopen-v3-acceptance-20260421-rerun1](/root/WorkSpace/fotball-analyst/backend/storage/pod_cycles/touchline-candidate-admission-reopen-v3-acceptance-20260421-rerun1) still lands at `101 / 98 / false / 0.812`
- that rerun shows the broadened upstream path never entered touchline candidate mode remotely:
  `sourceConditionedAcquisitionDiagnostics.touchlineCandidateModeEntered = false`
  `sourceConditionedAcquisitionDiagnostics.touchlineEscapeWindowFrames = 0`
  `sourceConditionedAcquisitionDiagnostics.touchlineInboardWindowFrames = 0`
  `sourceConditionedAcquisitionDiagnostics.reopenedRawCandidateFrames = 0`
  `sourceConditionedAcquisitionDiagnostics.reopenedRawCandidateSelectedFrames = 0`
- the new detector-breadth batch at [detector_breadth_matrix.json](/root/WorkSpace/fotball-analyst/backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/detector_breadth_matrix.json) also resolves to a falsification result:
  remote screen winner `yolov10n.pt`
  remote baseline proof `101 / 98 / false / 0.812`
  `baselineRemoteBeatsPlateau = false`
  `compoundThinRemoteBeatsPlateau = false`
  `detectorBreadthFalsified = true`
- inference from the regenerated artifact fields: the failing-source accepted rows are already overwhelmingly player-supported, so support-guarded thinning does not change the real blocker
- the selected qualifying config still fails accepted-ball sparsity on `9` slices, controlled-possession coverage on `9` slices, and viable-ball-track truth on `8` slices
- the current dominant failure signal is still failing-source acquisition weakness, not another post-acceptance repair gap
- the next honest follow-on batch now needs bounded evaluation of `touchline_detector_candidate_v1` on the failing source, not more post-acceptance repair or touchline-acquisition retuning

## Explicitly Parked

Do not reopen these by default:

- generic window-family exploration
- new long-gap treatment variants
- new controlled-possession assignment variants
- archived-lane reactivation

Do not keep iterating these falsified lanes:

- touchline probe-replacement variants
- touchline acquisition-upgrade retuning
- more edge-share thinning/profile search

Do not require a third source clip before starting robustness repair. A third import is useful follow-up, not the active gate.

## Runpod Discipline

- Use the `runpodctl` pod workflow when remote work is necessary; do not default this lane to serverless.
- Read credentials from `RUNPOD_API_KEY` or `~/.runpod/config.toml`; do not commit secrets.
- Keep GPU selection as an operator override instead of hardcoding it in product code.
- Stop the pod when done; do not leave it running between sessions.
- Verify the provider state before ending a session.
- Current cleanup standard is: `runpodctl pod list --all -o json` should come back empty unless there is an explicitly active run.
