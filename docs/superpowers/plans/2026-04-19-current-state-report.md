# Current State Report

Date: 2026-04-22  
Project: `fotball-analyst`

## Goal

The product goal is still:

1. upload football match video
2. process it into stable structured match data
3. persist artifacts trustworthy enough for later football analysis workflows

The end-to-end platform path already exists:

- uploads and match/job state persist through [backend/app/storage.py](/root/WorkSpace/fotball-analyst/backend/app/storage.py)
- processing can run locally or remotely
- proof artifacts, truth layers, pipeline traces, and benchmark summaries are persisted
- remote pod runs can be completed and cleaned up without leaving paid infrastructure behind

## Executive Summary

We are no longer blocked by basic ingestion or Runpod lifecycle plumbing.

The current project truth is:

- the frozen viable single-clip baseline is real
- the single-clip proof is still not truth-ready
- the first real multi-source suite is now visible
- the current multi-source verdict is `baseline_not_robust`
- the regenerated source-conditioned lane is currently `source_robustness_partial`

That means the active problem has shifted from “can we make one proof coherent?” to “does the same baseline remain stable across distinct source clips?”

## Canonical Proof Floor

The repaired single-clip proof bundle is:

- [proof_summary.json](/root/WorkSpace/fotball-analyst/backend/storage/pod_cycles/controlled-possession-assignment-treatment-20260420-rerun3/proof_summary.json)
- [selected_cluster_delta.json](/root/WorkSpace/fotball-analyst/backend/storage/pod_cycles/controlled-possession-assignment-treatment-20260420-rerun3/selected_cluster_delta.json)
- [ball_truth_layers.json](/root/WorkSpace/fotball-analyst/backend/storage/pod_cycles/controlled-possession-assignment-treatment-20260420-rerun3/ball_truth_layers.json)
- [ball_pipeline_trace.json](/root/WorkSpace/fotball-analyst/backend/storage/pod_cycles/controlled-possession-assignment-treatment-20260420-rerun3/ball_pipeline_trace.json)

Frozen baseline:

- detector `yolov10n.pt`
- primary mode `anchored_player_ranked_context_960`
- kept cleanup lane `recent_ball_plus_inward_anchor_center_bias35_960`

Current single-clip floor:

- `acceptedBallFrames = 174`
- `controlledPossessionFrames = 137`
- `ballTrackViable = true`
- `ballTrackEdgeFrameShare = 0.586`
- `longGapTreatmentOutcome = long_gap_treatment_partial`
- `controlledPossessionAssignmentOutcome = controlled_possession_assignment_weak`

Interpretation:

- viability is solved on the canonical proof clip
- truth-ready coverage is not
- same-clip long-gap and control-conversion treatments no longer look like the highest-value active lane

## Multi-Source Expansion Status

The first live clip-expansion batch is:

- [import_summary.json](/root/WorkSpace/fotball-analyst/backend/storage/benchmark_suites/clip_manifest_expansion_20260421Tpod001/import_summary.json)

It produced:

- `successfulImports = 1`
- `totalAttempts = 2`
- `outcome = clip_manifest_expansion_partial`

The successful new-source imported match is:

- [1d67fa87080446a0a777901aace43809](/root/WorkSpace/fotball-analyst/backend/storage/matches/1d67fa87080446a0a777901aace43809)

This batch was completed with pod cleanup; no pod was intentionally left live after the run.

## Current Suite Verdict

The refreshed saved-slice suite is:

- [suite_summary.json](/root/WorkSpace/fotball-analyst/backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/suite_summary.json)
- [active_lane_snapshot.json](/root/WorkSpace/fotball-analyst/backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/active_lane_snapshot.json)
- [suite_rows.csv](/root/WorkSpace/fotball-analyst/backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/suite_rows.csv)
- [primary_source_robustness_matrix.json](/root/WorkSpace/fotball-analyst/backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/primary_source_robustness_matrix.json)
- [primary_source_robustness_source_audit.json](/root/WorkSpace/fotball-analyst/backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/primary_source_robustness_source_audit.json)
- [primary_source_robustness_frontier.json](/root/WorkSpace/fotball-analyst/backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/primary_source_robustness_frontier.json)
- [primary_source_robustness_failure_audit.json](/root/WorkSpace/fotball-analyst/backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/primary_source_robustness_failure_audit.json)
- [detector_breadth_matrix.json](/root/WorkSpace/fotball-analyst/backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/detector_breadth_matrix.json)

Current suite truth:

- `suiteEntryCount = 10`
- `successfulEntryCount = 10`
- `distinctSourceClipCount = 2`
- `viableEntryCount = 1`
- `truthReadyEntryCount = 0`
- `suiteVerdict = baseline_not_robust`
- `suiteRecommendedNextLever = multi_match_robustness_repair`
- `sourceRobustnessActiveConfigName = source_robustness_baseline_current`
- `sourceRobustnessBestConfigName = source_robustness_shadow_edge_run_keep_every_2_min10`
- `sourceRobustnessBestExploratoryConfigName = source_robustness_shadow_edge_run_keep_every_3_min10`
- `sourceRobustnessOutcome = source_robustness_partial`
- `sourceRobustnessDominantFailureSignal = high_ball_track_edge_frame_share`
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
- `sourceRobustnessDiagnosis.acquisitionCandidateBeatsBestThinCandidate = false`
- `sourceRobustnessDiagnosis.acquisitionCandidateFalsified = true`
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
- `trainingPrepDiagnosis.sourceAwareSplitLeakageDetected = false`
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
- `sourceRobustnessDiagnosis.selectedConfigTruthGateCounts = {accepted sparse: 9, controlled sparse: 9, viable track: 8}`

Important nuance:

- the suite no longer fails because of selector bugs or stale dataset accounting
- it now truthfully shows two sources
- but the slice mix is still skewed toward `trimed-5min.mp4`
- that is why source-level rollups are now required for clean robustness decisions

## Main Problems Right Now

### 1. Multi-Source Robustness Is the Active Blocker

The live question is no longer whether the baseline can produce one viable proof.

The live question is whether the same frozen baseline remains stable across source clips. Right now the answer is no.

### 2. Source-Conditioned Edge Share Is Now the Live Repair Lane

The current suite plus the new source-robustness batch now say:

- `trimed-5min.mp4` remains edge-heavy and non-viable
- `trimed-football-2-1minute.mp4` is viable
- the best qualifying candidate improves `trimed-5min.mp4` median edge share from `0.822` to `0.714`
- that qualifying candidate holds `0.624` median accepted retention and `0.612` median controlled retention, but is still blocked by `failing_source_not_viable`
- the best exploratory candidate pushes edge share lower to `0.647`
- that exploratory candidate drops median accepted retention to `0.505` and median controlled retention to `0.500`
- the best non-catalog frontier candidate is `source_robustness_frontier_keep_every_4_min14`, but it still does not strictly beat the best qualifying catalog candidate across improvement plus both retention ratios
- the new support-aware shadow family stays `source_robustness_weak` with `0.0` failing-source edge-share improvement and `edge_share_improvement_insufficient` blockers
- the new touchline probe-replacement shadow mechanism is also falsified end to end:
  the local suite records `25` runs considered, `0` accepted, and only `candidate_edge_share_improvement_insufficient` rejection blockers
- the remote proof at [touchline-probe-replace-v1-acceptance-20260421](/root/WorkSpace/fotball-analyst/backend/storage/pod_cycles/touchline-probe-replace-v1-acceptance-20260421) hits the dominant failing windows directly and still accepts `0 / 3` replacements
- the new touchline acquisition-upgrade shadow mechanism is also falsified locally:
  the regenerated suite still records empty acquisition window counts and only `candidate_edge_share_improvement_insufficient` blocker counts
- the remote acquisition proof at [touchline-acquisition-upgrade-v1-acceptance-20260421](/root/WorkSpace/fotball-analyst/backend/storage/pod_cycles/touchline-acquisition-upgrade-v1-acceptance-20260421) ran on `yolov10n.pt` and still ended at `101 / 98 / false / 0.812`
- the real proof did not route through a new touchline-escape acquisition path:
  `sourceConditionedAcquisitionDiagnostics.touchlineEscapeCandidateFrames = 0`
  `sourceConditionedAcquisitionDiagnostics.touchlineEscapeSelectedFrames = 0`
- the best proposal surface on that proof is still `proposal_windows_075`, so the new upstream candidate does not beat the existing thin-family reference in product terms
- the combined reopen proof at [combined-reopen-yolov10n-reopen-v2-acceptance-20260421](/root/WorkSpace/fotball-analyst/backend/storage/pod_cycles/combined-reopen-yolov10n-reopen-v2-acceptance-20260421) also lands at `101 / 98 / false / 0.812`
- that proof records `comparison.mechanismBeatsPlateau = true` but `comparison.productBeatsPlateau = false`
- the generated combined detector/candidate-source surface now records `combinedReopenFalsified = true`
- the new touchline candidate-admission reopen shadow mechanism is also falsified locally:
  the regenerated snapshot records `touchlineCandidateModeEntered = true`, `touchlineEscapeWindowFrames = 7473`, `touchlineInboardWindowFrames = 0`, `reopenedRawCandidateFrames = 6803`, `reopenedRawCandidateSelectedFrames = 6723`, and `zeroTouchlineCandidateReasonCounts = {no_touchline_candidates_available: 109}`
- the authoritative remote rerun at [touchline-candidate-admission-reopen-v3-acceptance-20260421-rerun1](/root/WorkSpace/fotball-analyst/backend/storage/pod_cycles/touchline-candidate-admission-reopen-v3-acceptance-20260421-rerun1) still lands at `101 / 98 / false / 0.812`
- that rerun shows the broadened upstream path never entered touchline candidate mode remotely:
  `sourceConditionedAcquisitionDiagnostics.touchlineCandidateModeEntered = false`
  `sourceConditionedAcquisitionDiagnostics.touchlineEscapeWindowFrames = 0`
  `sourceConditionedAcquisitionDiagnostics.touchlineInboardWindowFrames = 0`
  `sourceConditionedAcquisitionDiagnostics.reopenedRawCandidateFrames = 0`
  `sourceConditionedAcquisitionDiagnostics.reopenedRawCandidateSelectedFrames = 0`
- inference from the regenerated artifact fields: the failing-source accepted rows are already mostly player-supported, so support-guarded thinning does not relieve the real edge-share blocker
- the thinning-only family now reads as falsified on this saved suite rather than merely under-searched
- the canonical proof floor remains intact at `174 / 137 / true / 0.586`

That means the next lane is no longer another post-acceptance repair pass, another touchline-acquisition tweak, or another bounded detector-breadth reopen. Phase 1A and the first detector training batch are complete, Phase 3 detector-candidate evaluation is now complete and falsified, and the honest next move is Phase 1B review densification.

### 3. Active Status Surfaces Needed a Reset

Before this cleanup, active docs and handoffs were still mixing:

- old plateau-era detector stories
- dead fork instructions
- newer live-lane artifact truth

That made the project look more confused than it actually was. Active docs now need to tell the same story as the live artifacts.

## Active Next Lever

The active engineering lane is:

`Frozen-Baseline Phase 1B Review Densification`

That lane is intentionally scoped to:

- stay in the live product tree
- keep the frozen baseline unchanged
- use the regenerated source-robustness artifacts, `active_lane_snapshot.json`, `primary_source_robustness_frontier.json`, `primary_source_robustness_failure_audit.json`, and `detector_breadth_matrix.json` as the decision surface
- treat the completed touchline replacement milestone as a falsification result
- treat the completed touchline acquisition milestone as a falsification result too
- treat the completed combined reopen milestone as a falsification result too
- treat the completed touchline candidate-admission milestone as a falsification result too
- treat the completed bounded detector-breadth batch as a falsification result too
- treat touchline training-data curation foundation and the first detector training batch as complete
- treat the first detector-candidate evaluation batch as complete and falsified
- move into Phase 1B review densification instead of another round of post-acceptance repair, acquisition-window retuning, or immediate detector reevaluation

## Operational Defaults

- Use `/root/WorkSpace/fotball-analyst` as the live product tree and `origin/main` as the canonical spine.
- Treat `archive/2026-04-21-mainline-reset/` as reference-only archived material.
- Use the `runpodctl` pod workflow only when the batch truly needs remote compute.
- Read credentials from `RUNPOD_API_KEY` or `~/.runpod/config.toml`; do not commit secrets.
- Keep GPU selection as an operator override instead of hardcoding it into product code.
- Stop pods when the run is done and verify provider state before ending a session.
