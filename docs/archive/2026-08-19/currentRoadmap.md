# Current Roadmap

## Current Roadmap Position - Release Packaging Commit Plan

The latest generated truth is:

```text
video_to_analysis_v7_3_release_packaging_and_worktree_triage_v1
-> video_to_analysis_v7_3_release_packaging_commit_plan
```

The v7.3 milestone remains done. The active work is now codebase readiness without GPUs:

- classify and package the dirty worktree
- commit source/tests/docs needed to reproduce the milestone
- decide which generated truth should be committed vs archived
- keep large external artifacts out of normal source commits
- keep GPU/training/source-pool work closed unless explicitly reopened

Current triage:

```text
totalDirtyPathCount = 487
source_tests_docs = 458
generated_truth = 25
runtime_or_benchmark_state = 2
deletedTrackedPathCount = 14
largeArtifactCount = 5
```

Verification passed: focused pytest `10 passed in 1.31s`, py_compile passed, JSON sanity passed, disk remained `65G` free at `56%` used, and RunPod pods were `[]`.

## Current Roadmap Position - V7.3 Current Milestone Done

The latest generated truth is:

```text
video_to_analysis_manual_operator_release_decision_v1
-> video_to_analysis_current_milestone_done
```

The current milestone is now closed by operator decision:

- `releasedRuntimeVersion = v7.3`
- `selectedOperatorDecision = declare_current_milestone_done`
- `v7_3CurrentMilestoneDeclaredDone = true`
- `optionalCoverageLoopDeferred = true`
- `primaryBlocker = null`

This is a terminal state for the current milestone. Future work is an explicit new operator choice, not automatic continuation:

- resume source-pool replenishment as optional coverage
- acquire new real sources before more scaleout
- reopen training only from new reviewed miss truth
- keep the milestone done and move to product usage/support

Verification passed: focused pytest `8 passed in 1.34s`, py_compile passed, JSON sanity passed, disk remained `52G` free at `65%` used, and RunPod pods were `[]`.

## Current Roadmap Position - Manual Operator Release Decision

The latest generated truth is:

```text
video_to_analysis_current_release_acceptance_decision_surface_v2
-> manual_operator_release_decision_required
```

The current roadmap state is now explicit:

- v7.3 is the packaged runtime/release milestone.
- Product, release, dashboard, monitoring, and generated-truth surfaces are current.
- Source-pool replenishment is still possible, but only as optional coverage expansion.
- The autonomous next lever is stopped at `manual_operator_release_decision_required`.
- No training, promotion mutation, runtime-default mutation, video/data download, normal storage mutation, or cleanup deletion happened in this batch.

Verification passed: focused pytest `8 passed in 1.29s`, py_compile passed, JSON sanity passed, disk remained `52G` free at `65%` used, and RunPod pods were `[]`.

## Current Roadmap Position - Source Consolidation Reentry V2

The latest generated truth is:

```text
video_to_analysis_next_roadmap_direction_snapshot_v76
-> video_to_analysis_source_pool_replenishment_plan
```

The important interpretation is unchanged and now re-proven after deliberate reentry:

- v7.3 runtime/product path is operationally closed for the current milestone.
- External/source consolidation v2 succeeded.
- Scaleout v111 succeeded.
- The resulting sample queue repeated already-drained v80 candidates.
- The lane returned to source-pool replenishment through the expected exhaustion path.
- Further source-pool replenishment is optional coverage work, not finish-line work.

Verification passed: focused pytest `22 passed in 4.71s`, py_compile passed, JSON sanity passed for 14 summaries with v111 approval/execution pairing verified, disk remained `52G` free at `65%` used, and RunPod pods were `[]`.

## Current Roadmap Position - Strategic Closeout V2

The live heartbeat has moved from source-pool replenishment to:

```text
video_to_analysis_operator_dashboard_polish_v2
-> football_external_benchmark_real_source_path_consolidation
```

The current strategic chain is:

```text
growth_lane_closeout_readout_v66
-> next_strategic_lane_selection_v5
-> roadmap_state_reconciliation_v2
-> release_acceptance_archive_v2
-> steady_state_monitoring_cycle_v2
-> operational_backlog_prioritization_v2
-> storage_retention_and_artifact_hygiene_v2
-> operator_dashboard_polish_v2
```

Roadmap meaning:

- v7.3 is the active runtime default.
- Product, monitoring, detector, SoccerNet, and SoccerTrack lanes are closed.
- Repeated source-pool replenishment is now optional coverage, not a finish-line transition.
- The next deliberate source/data lever is `football_external_benchmark_real_source_path_consolidation`.

Verification passed: focused pytest `21 passed in 2.76s`, py_compile passed, JSON sanity passed for 8 strategic/operator summaries, disk remained `52G` free at `65%` used, and RunPod pods were `[]`.

## Current V7.3 Video-To-Analysis Position

The active generated truth is roadmap-direction snapshot v75 after source-pool replenishment v80 and v110 bounded queue drain:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_next_roadmap_direction_snapshot_v75/
    next_roadmap_direction_snapshot_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
sourceSamplingPoolExhausted = true
selectedNextFamily = video_to_analysis_source_pool_replenishment_plan
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalStorageMutationExecuted = false
nextRecommendedNextLever = video_to_analysis_source_pool_replenishment_plan
```

Current end state:

```text
v7.3 remains the active runtime.
Source-pool replenishment v80 approved five bounded cases.
Real-video scaleout v110 completed.
The v110 bounded queue is fully drained through v440-v442.
Generated source sampling is exhausted again.
The repeated v73-v75 shape is now a healthy cyclic coverage lane, not a new strategic finish-line transition.
The next concrete gate is still source-pool replenishment unless the operator chooses to close or redirect this lane.
Verification passed: focused pytest `21 passed in 4.92s`, py_compile passed, JSON sanity passed for 30 v80/v110/v75 summaries with expected exhaustion blockers verified and guardrails false, disk remained `52G` free, and RunPod pods were `[]`.
```

## Previous V7.3 Video-To-Analysis Position

The active generated truth is roadmap-direction snapshot v74 after source-pool replenishment v79 and v109 bounded queue drain:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_next_roadmap_direction_snapshot_v74/
    next_roadmap_direction_snapshot_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
sourceSamplingPoolExhausted = true
selectedNextFamily = video_to_analysis_source_pool_replenishment_plan
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalStorageMutationExecuted = false
nextRecommendedNextLever = video_to_analysis_source_pool_replenishment_plan
```

Current end state:

```text
v7.3 remains the active runtime.
Source-pool replenishment v79 approved five bounded cases.
Real-video scaleout v109 completed.
The v109 bounded queue is fully drained through v436-v438.
Generated source sampling is exhausted again.
The next concrete gate is another source-pool replenishment.
Verification passed: focused pytest `21 passed in 4.94s`, py_compile passed, JSON sanity passed for the v79/v109/v74 chain, disk remained `52G` free, and RunPod pods were `[]`.
```

## Previous V7.3 Video-To-Analysis Position

The active generated truth is roadmap-direction snapshot v73 after the v108 bounded queue drain:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_next_roadmap_direction_snapshot_v73/
    next_roadmap_direction_snapshot_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
sourceSamplingPoolExhausted = true
selectedNextFamily = video_to_analysis_source_pool_replenishment_plan
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalStorageMutationExecuted = false
nextRecommendedNextLever = video_to_analysis_source_pool_replenishment_plan
```

Current end state:

```text
v7.3 remains the active runtime.
Real-video scaleout v108 completed from the fresh base plan.
The v108 bounded queue is fully drained through v432-v434.
Generated source sampling is exhausted.
The next concrete gate is source-pool replenishment.
Verification passed: focused pytest `15 passed in 4.81s`, py_compile passed, JSON sanity passed for the final v108 drain and v73 snapshot, disk remained `52G` free, and RunPod pods were `[]`.
```

## Previous V7.3 Video-To-Analysis Position

The active generated truth is source/artifact cleanup map v432 after corrected real-video scaleout v108 and bounded sample v432:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_source_and_artifact_cleanup_map_v432/
    source_and_artifact_cleanup_map_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
cleanupMapReady = true
cleanupMutationExecuted = false
generatedTruthDeleteAllowed = false
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalStorageMutationExecuted = false
nextRecommendedNextLever = video_to_analysis_bounded_next_sample_execution_approval
```

Current end state:

```text
v7.3 remains the active runtime.
The stale scaleout plan-selector bug is covered by regression test.
Real-video scaleout v108 completed from the fresh base plan.
Bounded sample v432 completed for operator_selected_canary_video.
The next concrete gate is another bounded next-sample execution approval.
Verification passed: focused pytest `15 passed in 4.99s`, py_compile passed, JSON sanity passed, disk remained `52G` free, and RunPod pods were `[]`.
```

## Previous V7.3 Video-To-Analysis Position

The active generated truth is the growth-lane decision snapshot after the operator-selected operational sprint:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_growth_lane_decision_snapshot_v1/
    growth_lane_decision_snapshot_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
selectedGrowthLever = video_to_analysis_real_video_scaleout_execution_approval
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalStorageMutationExecuted = false
nextRecommendedNextLever = video_to_analysis_real_video_scaleout_execution_approval
```

Current end state:

```text
v7.3 remains the active runtime.
Operational sprint is closed.
The next concrete gate is bounded real-video scaleout execution approval.
Verification passed: focused pytest `9 passed in 2.58s`, py_compile passed, JSON sanity passed, disk remained `52G` free, and RunPod pods were `[]`.
```

## Current V7.3 Video-To-Analysis Position

The active generated truth is strategic-lane selection v4 after bounded growth closeout:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_next_strategic_lane_selection_v4/
    next_strategic_lane_selection_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
growthLaneClosedAtSnapshotDir = video_to_analysis_next_sample_selection_snapshot_v107
selectedStrategicLane = manual_strategic_lane_selection_required
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalStorageMutationExecuted = false
nextRecommendedNextLever = manual_strategic_lane_selection_required
```

Current end state:

```text
v7.3 remains the active runtime.
Autonomous bounded growth is closed.
The next gate is a human/operator strategic lane selection.
Verification passed for this closeout: focused continuation pytest `35 passed in 5.43s`, closeout/strategic pytest `12 passed in 1.44s`, py_compile passed, JSON sanity passed, disk remained `52G` free, and RunPod pods were `[]`.
```

## Previous V7.3 Video-To-Analysis Position

The active generated truth is roadmap-direction snapshot v72 after corrected paired-version source-pool replenishment v78 and bounded candidate drain:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_next_roadmap_direction_snapshot_v72/
    next_roadmap_direction_snapshot_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
sourceSamplingPoolExhausted = true
selectedNextFamily = video_to_analysis_source_pool_replenishment_plan
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalStorageMutationExecuted = false
nextRecommendedNextLever = video_to_analysis_source_pool_replenishment_plan
```

Current end state:

```text
v7.3 remains the active runtime.
The v78 replenishment wave and bounded candidates were drained.
The next gate is video_to_analysis_source_pool_replenishment_plan.
```

## Previous V7.3 Video-To-Analysis Position

The active generated truth is roadmap-direction snapshot v71 after source-pool replenishment v77 and bounded candidate drain:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_next_roadmap_direction_snapshot_v71/
    next_roadmap_direction_snapshot_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
sourceSamplingPoolExhausted = true
selectedNextFamily = video_to_analysis_source_pool_replenishment_plan
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalStorageMutationExecuted = false
nextRecommendedNextLever = video_to_analysis_source_pool_replenishment_plan
```

Current end state:

```text
v7.3 remains the active runtime.
The v77 replenishment wave and bounded candidates were drained.
The next gate is video_to_analysis_source_pool_replenishment_plan.
```

## Previous V7.3 Video-To-Analysis Position

The active generated truth is roadmap-direction snapshot v69 after draining bounded pools and proving source-sampling exhaustion:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_next_roadmap_direction_snapshot_v69/
    next_roadmap_direction_snapshot_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
sourceSamplingPoolExhausted = true
selectedNextFamily = video_to_analysis_source_pool_replenishment_plan
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalStorageMutationExecuted = false
nextRecommendedNextLever = video_to_analysis_source_pool_replenishment_plan
```

Current end state:

```text
v7.3 remains the active runtime.
The remaining bounded pools from this replenishment wave were drained.
The next gate is video_to_analysis_source_pool_replenishment_plan.
```

## Previous V7.3 Video-To-Analysis Position - Source And Artifact Cleanup Map V412

The active generated truth is cleanup map v412 after a successful bounded sample cycle:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_source_and_artifact_cleanup_map_v412/
    source_and_artifact_cleanup_map_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
cleanupMapReady = true
artifactInventoryRowCount = 2059
artifactInventoryTotalBytes = 8262705613
generatedTruthDeleteAllowed = false
cleanupMutationExecuted = false
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalStorageMutationExecuted = false
nextRecommendedNextLever = video_to_analysis_bounded_next_sample_execution_approval
```

Current end state:

```text
v7.3 remains the active runtime.
The latest cycle executed one bounded SoccerNet replenishment sample and wrote a non-destructive cleanup map.
The next gate is video_to_analysis_bounded_next_sample_execution_approval.
```

## Previous V7.3 Video-To-Analysis Position - Source And Artifact Cleanup Map V411

The active generated truth is now cleanup map v411 after a successful recovery, scaleout, and bounded sample cycle:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_source_and_artifact_cleanup_map_v411/
    source_and_artifact_cleanup_map_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
cleanupMapReady = true
artifactInventoryRowCount = 2053
artifactInventoryTotalBytes = 8261836488
generatedTruthDeleteAllowed = false
cleanupMutationExecuted = false
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalStorageMutationExecuted = false
nextRecommendedNextLever = video_to_analysis_bounded_next_sample_execution_approval
```

Current end state:

```text
v7.3 remains the active runtime.
The latest cycle safely replenished sources, ran bounded scaleout, selected and executed one bounded sample, and wrote a non-destructive cleanup map.
The next gate is video_to_analysis_bounded_next_sample_execution_approval.
```

## Previous V7.3 Video-To-Analysis Position - Source And Artifact Cleanup Map V376

Goal 1 autonomous continuation v4 reached its configured 250 generated-batch cap. The current active generated truth is:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_total_finishline_closeout_v4/
    total_finishline_closeout_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
stopReason = generated_batch_cap_reached
executedBatchCount = 250
preexistingSatisfiedBatchCount = 1
latestGeneratedTruthPath = backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/video_to_analysis_next_roadmap_direction_snapshot_v67/next_roadmap_direction_snapshot_summary.json
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalStorageMutationExecuted = false
normalMatchStorageMutationExecuted = false
cleanupMutationExecuted = false
cleanupDeletionExecuted = false
generatedTruthDeleteAllowed = false
nextRecommendedNextLever = video_to_analysis_source_pool_replenishment_plan
```

Current end state:

```text
v7.3 remains the active runtime.
The latest generated truth is next-roadmap-direction snapshot v67.
The next gate is video_to_analysis_source_pool_replenishment_plan.
The continuation cap, not a blocker, stopped this session.
Historical destructive cleanup v1 was not rerun.
```

Verification:

```text
checkpoint tests at 50/100/150/200/250: all 35 passed
final focused roadmap verification: 35 passed in 5.51s
storage-cleanup safety verification: 15 passed in 2.02s
post-heartbeat reentry verification: 15 passed in 1.88s
py_compile: passed
JSON sanity: heartbeat points to v4 closeout, primaryBlocker=null, next source-pool replenishment plan
df -h /: /dev/sda1 150G 93G 52G 65%
runpodctl pod list --all -o json: []
```

## Previous V7.3 Video-To-Analysis Position

The source/artifact cleanup-map batch v376 is now the active generated truth:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_source_and_artifact_cleanup_map_v376/
    source_and_artifact_cleanup_map_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
cleanupMapReady = true
artifactInventoryRowCount = 1788
artifactInventoryTotalBytes = 8238228037
generatedTruthDeleteAllowed = false
cleanupMutationExecuted = false
cleanupDeletionExecuted = false
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalStorageMutationExecuted = false
nextRecommendedNextLever = video_to_analysis_bounded_next_sample_execution_approval
```

Current end state:

```text
v7.3 remains the active runtime.
Cleanup mapping is ready and non-destructive.
The next gate is video_to_analysis_bounded_next_sample_execution_approval.
```

## Previous V7.3 Video-To-Analysis Position - Total Finishline Continuation V3

The total-finishline continuation v3 reached its configured 250 generated-batch cap. The current active generated truth is:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_total_finishline_closeout_v3/
    total_finishline_closeout_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
stopReason = generated_batch_cap_reached
executedBatchCount = 250
latestGeneratedTruthPath = backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/video_to_analysis_scaleout_or_backlog_decision_snapshot_v376/scaleout_or_backlog_decision_snapshot_summary.json
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalStorageMutationExecuted = false
cleanupDeletionExecuted = false
nextRecommendedNextLever = video_to_analysis_source_and_artifact_cleanup_map
```

Current end state:

```text
v7.3 remains the active runtime.
The latest generated truth is scaleout/backlog decision snapshot v376.
The next gate is video_to_analysis_source_and_artifact_cleanup_map.
The continuation cap, not a blocker, stopped this session.
```

Verification:

```text
checkpoint tests at 50/100/150/200/250: all 35 passed
final focused verification: 35 passed in 5.50s
post-heartbeat reentry verification: 15 passed in 1.90s
py_compile: passed at every checkpoint and final verification
JSON sanity: heartbeat points to v3 closeout, primaryBlocker=null, next source and artifact cleanup map
df -h /: /dev/sda1 150G 93G 52G 65%
runpodctl pod list --all -o json: []
git status --short: dirty worktree with pre-existing unrelated changes plus generated total-finishline continuation v3 artifacts
```

## Previous V7.3 Video-To-Analysis Position

The total-finishline continuation v2 reached its configured 250 generated-batch cap. The current active generated truth is:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_total_finishline_closeout_v2/
    total_finishline_closeout_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
stopReason = generated_batch_cap_reached
executedBatchCount = 250
latestGeneratedTruthPath = backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/video_to_analysis_bounded_next_sample_execution_approval_v343/bounded_next_sample_execution_approval_summary.json
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalStorageMutationExecuted = false
cleanupDeletionExecuted = false
nextRecommendedNextLever = video_to_analysis_bounded_next_sample_execution
```

Current end state:

```text
v7.3 remains the active runtime.
The latest generated truth is bounded next-sample execution approval v343.
The next gate is video_to_analysis_bounded_next_sample_execution.
The continuation cap, not a blocker, stopped this session.
```

Verification:

```text
checkpoint tests at 50/100/150/200/250: all 35 passed
py_compile: passed at every checkpoint
JSON sanity: closeout goalAchieved=true, primaryBlocker=null, next bounded next-sample execution
df -h /: /dev/sda1 150G 93G 52G 65%
runpodctl pod list --all -o json: []
git status --short: dirty worktree with pre-existing unrelated changes plus generated total-finishline continuation artifacts
```

## Previous V7.3 Video-To-Analysis Position

The total-finishline run reached its configured 250 generated-batch cap. The current active generated truth is:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_total_finishline_closeout_v1/
    total_finishline_closeout_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
stopReason = generated_batch_cap_reached
executedBatchCount = 250
latestGeneratedTruthPath = backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/video_to_analysis_real_video_scaleout_source_sampling_expansion_v73/real_video_scaleout_source_sampling_expansion_summary.json
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalStorageMutationExecuted = false
cleanupDeletionExecuted = false
nextRecommendedNextLever = video_to_analysis_next_roadmap_direction_snapshot
```

Current end state:

```text
v7.3 remains the active runtime.
The latest generated transition is source-sampling exhaustion v73.
The next gate is video_to_analysis_next_roadmap_direction_snapshot.
The total-finishline cap, not a blocker, stopped this session.
```

Verification:

```text
checkpoint tests at 50/100/150/200/250: all 35 passed
py_compile: passed at every checkpoint
JSON sanity: closeout goalAchieved=true, primaryBlocker=null, next roadmap direction snapshot
df -h /: /dev/sda1 150G 93G 52G 65%
runpodctl pod list --all -o json: []
git status --short: dirty worktree with pre-existing unrelated changes plus generated total-finishline artifacts
```

## Previous V7.3 Video-To-Analysis Position

The bounded-chain continuation v2 has reached its configured 50 generated-batch cap. The current active generated truth is:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_bounded_chain_continuation_closeout_v2/
    bounded_chain_continuation_closeout_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
stopReason = generated_batch_cap_reached
executedBatchCount = 50
latestGeneratedTruthPath = backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/video_to_analysis_real_video_scaleout_plan_refresh_v135/real_video_scaleout_plan_refresh_summary.json
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalStorageMutationExecuted = false
cleanupDeletionExecuted = false
nextRecommendedNextLever = video_to_analysis_real_video_scaleout_execution_approval
```

The shipped continuation v2 path:

```text
cleanup/approval/execution/report/closeout/decision/cleanup v269-v271
-> bounded next-sample pool exhaustion v272
-> plan refresh v132
-> source sampling exhaustion v64
-> roadmap direction snapshot v33
-> source-pool replenishment plan/approval v40
-> plan refresh v133
-> scaleout approval/execution/report/closeout/snapshot v69
-> bounded sample queue v273/v274/v275
-> bounded next-sample pool exhaustion v276
-> plan refresh v134
-> source sampling exhaustion v65
-> roadmap direction snapshot v34
-> source-pool replenishment plan/approval v41
-> plan refresh v135
-> closeout at 50-batch cap
```

Current end state:

```text
v7.3 remains the active runtime.
The latest refreshed scaleout plan is video_to_analysis_real_video_scaleout_plan_refresh_v135.
The next gate is video_to_analysis_real_video_scaleout_execution_approval.
The continuation cap, not a blocker, stopped this session.
```

Verification:

```text
focused tests: 25 passed in 4.87s
roadmap-direction reentry tests: 10 passed in 1.83s
py_compile: passed
JSON sanity: closeout goalAchieved=true, primaryBlocker=null, next scaleout approval
df -h .: /dev/sda1 150G 93G 52G 65%
runpodctl pod list --all -o json: []
git status --short: dirty worktree with pre-existing unrelated changes plus generated continuation artifacts
```

## Previous V7.3 Video-To-Analysis Position

The bounded-chain continuation has reached its configured 50 generated-batch cap. The current active generated truth is:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_bounded_chain_continuation_closeout_v1/
    bounded_chain_continuation_closeout_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
stopReason = generated_batch_cap_reached
executedBatchCount = 50
latestGeneratedTruthPath = backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/video_to_analysis_scaleout_or_backlog_decision_snapshot_v269/scaleout_or_backlog_decision_snapshot_summary.json
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalStorageMutationExecuted = false
cleanupDeletionExecuted = false
nextRecommendedNextLever = video_to_analysis_source_and_artifact_cleanup_map
```

The shipped continuation path:

```text
bounded closeout/decision/cleanup v263
-> bounded sample pool exhaustion v264
-> plan refresh v128
-> source sampling exhaustion v62
-> roadmap direction snapshot v31
-> source-pool replenishment plan/approval v38
-> plan refresh v129
-> scaleout approval/execution/report/closeout/snapshot v67
-> bounded sample queue v265/v266/v267
-> bounded next-sample pool exhaustion v268
-> plan refresh v130
-> source sampling exhaustion v63
-> roadmap direction snapshot v32
-> source-pool replenishment plan/approval v39
-> plan refresh v131
-> scaleout approval/execution/report/closeout/snapshot v68
-> bounded sample approval/execution/report/closeout/decision v269
-> closeout at 50-batch cap
```

Current end state:

```text
v7.3 remains the active runtime.
The latest generated truth before closeout is scaleout/backlog decision snapshot v269.
The next gate is video_to_analysis_source_and_artifact_cleanup_map.
The continuation cap, not a blocker, stopped this session.
```

Verification:

```text
focused tests: 25 passed in 4.89s
roadmap-direction reentry tests: 10 passed in 1.85s
py_compile: passed
JSON sanity: closeout goalAchieved=true, primaryBlocker=null, next cleanup map
df -h .: /dev/sda1 150G 93G 52G 65%
runpodctl pod list --all -o json: []
git status --short: dirty worktree with pre-existing unrelated changes plus generated continuation artifacts
```

## Previous V7.3 Video-To-Analysis Position

The autonomous scaleout follow-up has reached its configured 50 generated-batch cap. The current active generated truth is:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_autonomous_scaleout_followup_closeout_v1/
    autonomous_scaleout_followup_closeout_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
stopReason = generated_batch_cap_reached
executedBatchCount = 50
latestGeneratedTruthPath = backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/video_to_analysis_bounded_next_sample_report_route_binding_v263/bounded_next_sample_report_route_binding_summary.json
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalMatchStorageMutationExecuted = false
cleanupMutationExecuted = false
generatedTruthDeleteAllowed = false
nextRecommendedNextLever = video_to_analysis_bounded_next_sample_closeout
```

The shipped follow-up path:

```text
scaleout approval/execution/report/closeout/snapshot v65
-> bounded sample queue v257/v258/v259
-> bounded next-sample pool exhaustion v260
-> plan refresh v126
-> source sampling exhaustion v61
-> roadmap direction snapshot v30
-> source-pool replenishment plan/approval v37
-> plan refresh v127
-> scaleout approval/execution/report/closeout/snapshot v66
-> bounded sample queue v261/v262
-> bounded sample approval/execution/report v263
-> closeout at 50-batch cap
```

Current end state:

```text
v7.3 remains the active runtime.
The latest route-smoked generated truth is bounded next-sample report-route binding v263.
The next gate is video_to_analysis_bounded_next_sample_closeout.
The follow-up cap, not a blocker, stopped this session.
```

Verification:

```text
focused tests: 25 passed in 4.93s
roadmap-direction reentry tests: 10 passed in 1.82s
py_compile: passed
JSON sanity: closeout goalAchieved=true, primaryBlocker=null, next bounded sample closeout
df -h .: /dev/sda1 150G 93G 52G 65%
runpodctl pod list --all -o json: []
git status --short: dirty worktree with pre-existing unrelated changes plus generated follow-up artifacts
```

## Previous V7.3 Video-To-Analysis Position

The autonomous growth marathon has reached its configured 30 generated-batch cap. The current active generated truth is:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_autonomous_growth_marathon_closeout_v1/
    autonomous_growth_marathon_closeout_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
stopReason = generated_batch_cap_reached
executedBatchCount = 30
boundedNextSamplePoolExhausted = true
sourcePoolExhaustionOccurred = true
sourceSamplingPoolExhausted = true
sourcePoolReplenishmentExecuted = true
refreshedScaleoutCaseCount = 5
sourcePoolReplenishmentApprovalDir = video_to_analysis_source_pool_replenishment_approval_v36
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalMatchStorageMutationExecuted = false
cleanupMutationExecuted = false
nextRecommendedNextLever = video_to_analysis_real_video_scaleout_execution_approval
```

The shipped marathon path:

```text
scaleout approval/execution/report/closeout/snapshot v64
-> bounded sample v35 queue consumed through v253, v254, v255
-> bounded next-sample pool exhaustion v256
-> plan refresh v124
-> source sampling exhaustion v60
-> roadmap direction snapshot v29
-> source-pool replenishment plan/approval v36
-> plan refresh v125
-> closeout at 30-batch cap
```

Current end state:

```text
v7.3 remains the active runtime.
The latest refreshed scaleout plan is ready.
The next gate is video_to_analysis_real_video_scaleout_execution_approval.
The marathon cap, not a blocker, stopped this session.
```

Verification:

```text
focused tests: 25 passed in 4.81s
py_compile: passed
JSON sanity: closeout goalAchieved=True, primaryBlocker=None, next approval
df -h .: /dev/sda1 150G 93G 52G 65%
runpodctl pod list --all -o json: []
git status --short: dirty worktree with pre-existing unrelated changes plus generated marathon artifacts
```

## Previous V7.3 Video-To-Analysis Position

The operator dashboard and operational sprint finish-line chain has been shipped. The current active generated truth is:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_growth_lane_decision_snapshot_v1/
    growth_lane_decision_snapshot_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
growthLaneDecisionSnapshotReady = true
selectedGrowthLever = video_to_analysis_real_video_scaleout_execution_approval
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalMatchStorageMutationExecuted = false
nextRecommendedNextLever = video_to_analysis_real_video_scaleout_execution_approval
```

The shipped chain:

```text
video_to_analysis_operator_dashboard_polish
-> football_external_benchmark_real_source_path_consolidation
-> video_to_analysis_real_video_scaleout_plan
-> video_to_analysis_steady_state_monitoring_recurring_schedule
-> video_to_analysis_operational_sprint_closeout
-> video_to_analysis_growth_lane_decision_snapshot
```

Current end state:

```text
v7.3 remains the active runtime.
The operator dashboard is route-smoked and operator-facing v7.3 truth is bound.
The operational sprint is closed across four completed items.
The next gate is video_to_analysis_real_video_scaleout_execution_approval.
```

Verification:

```text
focused tests: 19 passed in 4.39s
py_compile: passed
JSON sanity: all six checkpoint summaries true/null, final next lever approval
df -h .: /dev/sda1 150G 93G 52G 64%
runpodctl pod list --all -o json: []
```

## Previous V7.3 Video-To-Analysis Position

The next-five post-archive cascade has been shipped. The current active generated truth is:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_storage_retention_and_artifact_hygiene_v1/
    storage_retention_and_artifact_hygiene_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
storageHygienePlanReady = true
artifactInventoryReady = true
retentionPolicyReady = true
cleanupExecutionReady = false
cleanupMutationExecuted = false
generatedTruthDeleteAllowed = false
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
nextRecommendedNextLever = video_to_analysis_operator_dashboard_polish
```

The shipped cascade:

```text
video_to_analysis_steady_state_monitoring_cycle
-> football_external_soccernet_broader_validation_choice
-> video_to_analysis_upload_to_analysis_walkthrough
-> v7_4_training_decision_from_real_misses
-> video_to_analysis_storage_retention_and_artifact_hygiene
```

Current end state:

```text
v7.3 is steady-state healthy.
SoccerNet broader validation is optional future growth.
v7.4 training is deferred because current real-miss truth does not justify it.
Storage hygiene policy is ready and no cleanup mutation was executed.
The next gate is video_to_analysis_operator_dashboard_polish.
```

## Previous V7.3 Video-To-Analysis Position

The current video-to-analysis release acceptance state is archived and finished for this module.

Latest completed batch:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_release_acceptance_archive_v1/
    release_acceptance_archive_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
videoToAnalysisReleaseAcceptanceArchived = true
currentReleaseFinished = true
manualStrategicSentinelResolved = true
activeRuntimeDefaultVersion = v7.3
runtimeDefaultMutationExecuted = true
runtimeDefaultMutationExecutedByThisBatch = false
runtimeDefaultMutationAllowed = false
trainingExecuted = false
promotionMutationExecuted = false
nextRecommendedNextLever = video_to_analysis_steady_state_monitoring_cycle
```

Current end state:

```text
The release/product/runtime path is finished for this module.
The bounded growth loop is intentionally not auto-resumed.
The next concrete lane is steady-state monitoring.
```

## Previous V7.3 Video-To-Analysis Position

v7.3 remains active as the runtime default. The bounded growth lane is now closed for this roadmap module; the recovered `v123` scaleout plan is optional future growth, not the next automatic task.

Latest completed batch:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_next_strategic_lane_selection_v2/
    next_strategic_lane_selection_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
selectedStrategicLane = manual_strategic_lane_selection_required
growthLaneCloseoutManualStrategicChoiceRequired = true
growthLaneClosedAtSnapshotDir = video_to_analysis_next_sample_selection_snapshot_v63
growthLaneClosedAtVersion = 63
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
nextRecommendedNextLever = manual_strategic_lane_selection_required
```

Current end state:

```text
The bounded growth loop has proven repeatability and has been closed.
The next gate is a deliberate manual strategic lane choice.
```

## Previous V7.3 Video-To-Analysis Position

v7.3 remains active as the runtime default, and the growth lane is replenished for the next bounded scaleout tranche after consuming the v29 sample queue.

Latest completed batch:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_real_video_scaleout_plan_refresh_v113/
    real_video_scaleout_plan_refresh_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
availableFreshScaleoutCaseCount = 7
requiredFreshScaleoutCaseCount = 5
refreshedScaleoutCaseCount = 5
sourcePoolReplenishmentApprovalDir = video_to_analysis_source_pool_replenishment_approval_v30
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
nextRecommendedNextLever = video_to_analysis_real_video_scaleout_execution_approval
```

Current end state:

```text
The bounded v29 sample tranche has been consumed and the source pool has been replenished again.
The next gate is video_to_analysis_real_video_scaleout_execution_approval.
```

## Previous V7.3 Video-To-Analysis Position

v7.3 is active as the runtime default, detector-evaluation report reentry is closed, and the growth lane is replenished for the next bounded scaleout tranche.

Latest completed batch:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_real_video_scaleout_plan_refresh_v111/
    real_video_scaleout_plan_refresh_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
availableFreshScaleoutCaseCount = 7
requiredFreshScaleoutCaseCount = 5
refreshedScaleoutCaseCount = 5
sourcePoolReplenishmentApprovalDir = video_to_analysis_source_pool_replenishment_approval_v29
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
nextRecommendedNextLever = video_to_analysis_real_video_scaleout_execution_approval
```

Current end state:

```text
The bounded v28 sample tranche has been consumed and the source pool has been replenished.
The next gate is video_to_analysis_real_video_scaleout_execution_approval.
```

## Previous V7.3 Video-To-Analysis Position

video-to-analysis post-release monitoring closeout is complete.

Latest completed batch:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_post_release_monitoring_closeout_v1/
    post_release_monitoring_closeout_summary.json
```

It reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
postReleaseMonitoringClosed = true
postReleaseMonitoringRouteReady = true
activeRuntimeDefaultVersion = v7.3
runtimeDefaultRolloutClosed = true
runtimeDefaultMutationExecuted = true
detectorEvaluationExecuted = false
trainingExecuted = false
promotionMutationExecuted = false
nextRecommendedNextLever = video_to_analysis_detector_evaluation_reentry_plan
```

Current end state:

```text
Post-release monitoring is closed against the active v7.3 runtime default.
The next gate is video_to_analysis_detector_evaluation_reentry_plan.
```

## Previous V7.2 Video-To-Analysis Position

The SoccerNet detector-miss resolver is now the active stop sign.

Update: the stop sign is cleared. The 120-row SoccerNet detector-miss review completed and unlocked v7.3 manifest prep.

Latest completed batch:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  football_external_soccernet_detector_miss_manual_review_resolution_v1/
    detector_miss_manual_review_resolution_summary.json
```

It now reports:

```text
goalAchieved = true
roadmapAdvanceAllowed = true
primaryBlocker = null
reviewCandidateCount = 120
pendingReviewItemCount = 0
reviewedRealDetectorMissPositiveCount = 65
realDetectorMissCount = 65
reviewedDetectorHitOrNotMissCount = 47
reviewedNotBallOrOutOfPlayCount = 8
distinctRealMissSplitGroupCount = 30
invalidReviewStatusCount = 0
invalidBBoxCount = 0
labelQualityGapCount = 0
missingEvidenceImageCount = 0
detectorTrainingNeededFromEvidence = true
v7_3TrainingDataReady = true
v7_3RetrainExecuted = false
nextRecommendedNextLever = v7_3_training_manifest_prep_from_soccernet_real_misses
```

Current end state:

```text
Reviewed real SoccerNet detector-miss boxes exist.
Prepare v7.3 manifest from these 65 real misses.
Do not train v7.3 before export/overlay audit.
```

## Previous V7.2 Video-To-Analysis Position

Review UI:

```text
python3 backend/scripts/serve_football_external_soccernet_detector_miss_review_ui.py --host 127.0.0.1 --port 8773
http://127.0.0.1:8773/
```

Latest completed batch:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  football_external_soccernet_detector_miss_manual_review_resolution_v1/
    detector_miss_manual_review_resolution_summary.json
```

It reports:

```text
goalAchieved = false
roadmapAdvanceAllowed = false
primaryBlocker = football_external_soccernet_detector_miss_manual_review_still_pending
reviewCandidateCount = 120
pendingReviewItemCount = 120
invalidReviewStatusCount = 0
invalidBBoxCount = 0
labelQualityGapCount = 0
missingEvidenceImageCount = 0
reviewedRealDetectorMissPositiveCount = 0
v7_3TrainingDataReady = false
v7_3RetrainExecuted = false
nextRecommendedNextLever = football_external_soccernet_detector_miss_manual_review_resolution
```

Current end state:

```text
The review queue is valid and evidence-backed.
The roadmap is blocked on manual SoccerNet detector-miss decisions.
If reviewed real detector-miss positives are accepted with tight bboxes, next is v7.3 manifest prep.
If no real misses are accepted, next is no-detector-training-needed closeout.
```

## Current V7.2 Video-To-Analysis Position

The SoccerNet detector-miss capture queue is ready for manual review, but v7.3 detector retraining is still not justified.

Latest completed batch:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  football_external_soccernet_detector_miss_capture_and_label_queue_v1/
    detector_miss_capture_summary.json
```

It reports:

```text
goalAchieved = true
primaryBlocker = null
soccerNetEventAnnotationCount = 1604
reviewItemCount = 120
pendingReviewItemCount = 120
missingEvidenceImageCount = 0
reviewedRealDetectorMissPositiveCount = 0
realDetectorMissCount = 0
v7_3TrainingDataReady = false
v7_3RetrainExecuted = false
nextRecommendedNextLever = football_external_soccernet_detector_miss_manual_review_resolution
```

Current end state:

```text
The product pipeline works on the real SoccerNet sample.
The next gap is human-reviewed real detector-miss bboxes.
Do not prepare v7.3 data or train until the miss-review resolver creates real miss truth.
```

## Current V7.2 Video-To-Analysis Position

The SoccerNet real-sample product pipeline has passed, but v7.3 detector retraining is not yet justified.

Latest completed batch:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  football_external_soccernet_real_sample_product_pipeline_training_decision_v1/
    soccernet_real_sample_product_pipeline_training_decision_summary.json
```

It reports:

```text
goalAchieved = true
primaryBlocker = null
controlledRealSampleMaterialized = true
actualProductPipelinePassed = true
processedFrameCount = 146893
reportedFrameCount = 146893
detectorTrainingNeededFromEvidence = false
realDetectorMissCount = 0
reviewedRealMissPositiveCount = 0
v7_3TrainingDataReady = false
v7_3RetrainExecuted = false
nextRecommendedNextLever = football_external_soccernet_detector_miss_capture_and_label_queue
```

Current end state:

```text
The controlled real SoccerNet 224p sample and actual product pipeline are working.
The next evidence gap is reviewed real detector misses.
Do not build v7.3 training data or retrain until miss capture produces reviewed bbox truth.
```

## Current V7.2 Video-To-Analysis Position

The bounded SoccerNet/external product validation execution has passed.

Latest completed batch:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  football_external_soccernet_bounded_product_validation_execution_v1/
    soccernet_bounded_product_validation_execution_summary.json
```

It reports:

```text
goalAchieved = true
primaryBlocker = null
productValidationExecutionApproved = true
productValidationExecutionExecuted = true
validatedProductSliceCount = 4
failedProductSliceCount = 0
bulkDownloadExecuted = false
nextRecommendedNextLever = football_external_soccernet_bounded_product_validation_report_binding
```

Current end state:

```text
Bounded SoccerNet/external product validation has run from existing artifacts.
The next move is binding the validation report into a route/readout.
No bulk downloads, training, promotion, runtime mutation, or normal storage mutation executed.
```

## Current V7.2 Video-To-Analysis Position

The bounded SoccerNet/external product validation execution approval is ready.

Latest completed batch:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  football_external_soccernet_bounded_product_validation_execution_approval_v1/
    soccernet_bounded_product_validation_execution_approval_summary.json
```

It reports:

```text
goalAchieved = true
primaryBlocker = null
productValidationExecutionApproved = true
productValidationExecutionExecuted = false
approvedProductValidationSliceCount = 4
executionMode = bounded_existing_artifact_product_validation
bulkDownloadApproved = false
trainingApproved = false
promotionApproved = false
runtimeDefaultMutationApproved = false
nextRecommendedNextLever = football_external_soccernet_bounded_product_validation_execution
```

Current end state:

```text
The next batch is allowed to execute bounded SoccerNet/external product validation from existing artifacts.
Execution is not done yet.
Bulk downloads, training, promotion, runtime mutation, and normal storage mutation remain blocked.
```

## Current V7.2 Video-To-Analysis Position

The bounded SoccerNet/external product validation plan is ready.

Latest completed batch:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  football_external_soccernet_bounded_product_validation_plan_v1/
    soccernet_bounded_product_validation_plan_summary.json
```

It reports:

```text
goalAchieved = true
primaryBlocker = null
existingArtifactReusePlanned = true
readyArtifactCount = 5
sourceGovernanceReady = true
storageBudgetReady = true
productValidationSlices = 4
bulkDownloadPlanned = false
executionApproved = false
executionApprovalRequired = true
nextRecommendedNextLever = football_external_soccernet_bounded_product_validation_execution_approval
```

Current end state:

```text
The current release/acceptance decision surface is packaged.
The SoccerNet/external validation plan is ready from existing artifacts.
The next move is an explicit execution approval gate, not automatic execution or bulk download.
```

Still frozen for product/runtime work: no detector evaluation, candidate readiness, training, promotion mutation, runtime-default mutation, video/data download, or normal-match-storage mutation.

## Current V7.2 Video-To-Analysis Position

The current release/acceptance/operator decision surface is packaged.

Latest completed batch:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_current_release_acceptance_decision_surface_v1/
    current_release_acceptance_decision_surface_summary.json
```

It reports:

```text
goalAchieved = true
primaryBlocker = null
currentReleaseDecisionSurfaceReady = true
releaseRuntimeComplete = true
operatorDashboardRouteReady = true
acceptanceReportRouteReady = true
releaseReadoutRouteReady = true
growthLaneClosedAtVersion = 57
selectedStrategicLane = manual_strategic_lane_selection_required
recommendedStrategicChoice = external_benchmark_soccernet_lane
nextRecommendedNextLever = football_external_soccernet_bounded_product_validation_plan
```

Current end state:

```text
The product/release lane is packaged enough for an operator to see the current state.
The bounded growth lane remains closed at v57.
The next recommended strategic lane is bounded SoccerNet/external product validation.
```

Still frozen for product/runtime work: no detector evaluation, candidate readiness, training, promotion mutation, runtime-default mutation, video/data download, or normal-match-storage mutation.

## Current V7.2 Video-To-Analysis Position

The bounded growth roadmap module is closed at v57.

Latest completed batch:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_growth_lane_closeout_readout_v57/
    growth_lane_closeout_readout_summary.json
```

It reports:

```text
goalAchieved = true
primaryBlocker = null
growthLaneCloseoutReady = true
growthLaneClosedAtSnapshotDir = video_to_analysis_next_sample_selection_snapshot_v57
growthLaneClosedAtVersion = 57
autoContinueBoundedGrowthRecommended = false
manualStrategicChoiceRequired = true
nextRecommendedNextLever = manual_strategic_lane_selection_required
```

The strategic selector was rerun after the closeout and now also stops at:

```text
selectedStrategicLane = manual_strategic_lane_selection_required
growthLaneCloseoutManualStrategicChoiceRequired = true
nextRecommendedNextLever = manual_strategic_lane_selection_required
```

The v57 queue remains optional future input:

```text
operator_uploaded_local_video_replenishment_candidate_v28
soccernet_bounded_224p_member_replenishment_candidate_v28
existing_normal_storage_video_replenishment_candidate_v28
```

Current end state:

```text
This roadmap module is done. More bounded growth is possible, but it is not unfinished work.
The next move is a manual strategic choice: continue coverage growth, product polish, external benchmark work, or a new operator goal.
```

Still frozen for product/runtime work: no training, no detector/candidate evaluation readiness, no promotion mutation, no runtime-default mutation, no video/data download, and no normal-match-storage mutation.

## Current V7.2 Video-To-Analysis Position

The roadmap continued bounded growth with a subagent audit sidecar and advanced to the v57 queue.

Latest completed chain:

- `video_to_analysis_next_sample_selection_snapshot_v53` was consumed.
- Bounded next-sample executions advanced through `video_to_analysis_bounded_next_sample_execution_v223`.
- Queue exhaustion proofs passed at v212, v216, v220, and v224.
- Source sampling expansions v49-v52 were exhausted as expected.
- Source-pool replenishment v25-v28 approved five bounded candidates per cycle.
- `video_to_analysis_real_video_scaleout_plan_refresh_v109` selected five cases from replenishment v28.
- `video_to_analysis_real_video_scaleout_bounded_execution_v57` passed `5 / 5`.
- `video_to_analysis_real_video_scaleout_report_route_binding_v57` smoked API/HTML `200 / 200`.
- `video_to_analysis_next_sample_selection_snapshot_v57` is now the active queue.

Latest active generated truth:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_next_sample_selection_snapshot_v57/
    next_sample_selection_snapshot_summary.json
```

It reports:

```text
goalAchieved = true
primaryBlocker = null
candidateSampleCount = 3
candidateSampleIds = [
  operator_uploaded_local_video_replenishment_candidate_v28,
  soccernet_bounded_224p_member_replenishment_candidate_v28,
  existing_normal_storage_video_replenishment_candidate_v28
]
nextRecommendedNextLever = video_to_analysis_bounded_next_sample_execution_approval
```

Next deterministic work:

```text
video_to_analysis_bounded_next_sample_execution_approval
```

Still frozen for product/runtime work: no training, no detector/candidate evaluation readiness, no promotion mutation, no runtime-default mutation, no video/data download, and no normal-match-storage mutation.

## Current V7.2 Video-To-Analysis Position

The roadmap resumed bounded growth after housekeeping and advanced to the v53 queue.

Latest completed chain:

- `video_to_analysis_next_strategic_lane_selection_v1` now resumes bounded growth after completed readout/dashboard/storage lanes.
- Bounded growth continued from `video_to_analysis_next_sample_selection_snapshot_v38`.
- Generated source sampling ran through `video_to_analysis_real_video_scaleout_source_sampling_expansion_v48`, where the generated pool was intentionally exhausted.
- `video_to_analysis_next_roadmap_direction_snapshot_v24` selected `video_to_analysis_source_pool_replenishment_plan`.
- `video_to_analysis_source_pool_replenishment_plan_v24` and `video_to_analysis_source_pool_replenishment_approval_v24` approved five bounded replenishment cases.
- `video_to_analysis_real_video_scaleout_plan_refresh_v101` selected five cases.
- `video_to_analysis_real_video_scaleout_bounded_execution_v53` passed `5 / 5`.
- `video_to_analysis_real_video_scaleout_report_route_binding_v53` smoked API/HTML `200 / 200`.
- `video_to_analysis_next_sample_selection_snapshot_v53` is now the active queue.

Latest active generated truth:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_next_sample_selection_snapshot_v53/
    next_sample_selection_snapshot_summary.json
```

It reports:

```text
goalAchieved = true
primaryBlocker = null
candidateSampleCount = 3
candidateSampleIds = [
  operator_uploaded_local_video_replenishment_candidate_v24,
  soccernet_bounded_224p_member_replenishment_candidate_v24,
  existing_normal_storage_video_replenishment_candidate_v24
]
nextRecommendedNextLever = video_to_analysis_bounded_next_sample_execution_approval
```

Next deterministic work:

```text
video_to_analysis_bounded_next_sample_execution_approval
```

Still frozen for product/runtime work: no training, no detector/candidate evaluation readiness, no promotion mutation, no runtime-default mutation, no video/data download, and no normal-match-storage mutation.

## Current V7.2 Video-To-Analysis Position

The roadmap completed the storage cleanup housekeeping lane.

Latest completed chain:

- `video_to_analysis_storage_cleanup_approval_v1`
- `video_to_analysis_storage_cleanup_dry_run_execution_v1`
- `video_to_analysis_storage_cleanup_execution_approval_v1`
- `video_to_analysis_storage_cleanup_bounded_execution_v1`
- `video_to_analysis_storage_cleanup_closeout_v1`

Latest active generated truth:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_storage_cleanup_closeout_v1/
    storage_cleanup_closeout_summary.json
```

It reports:

```text
goalAchieved = true
primaryBlocker = null
storageCleanupCloseoutReady = true
actualDeletedPathCount = 1012
actualReclaimedBytes = 23981092
latestVersionDeletionBlockedCount = 0
pathGuardrailFailureCount = 0
nextRecommendedNextLever = video_to_analysis_next_strategic_lane_selection
```

Next deterministic work:

```text
video_to_analysis_next_strategic_lane_selection
```

This should choose the next major lane after housekeeping rather than automatically resuming growth.

Still frozen for product/runtime work: no training, no detector/candidate evaluation readiness, no promotion mutation, no runtime-default mutation, no video/data download, and no normal-match-storage mutation.

## Current V7.2 Video-To-Analysis Position

The roadmap completed bounded storage cleanup execution.

Latest completed chain:

- `video_to_analysis_storage_cleanup_approval_v1` approved dry-run planning.
- `video_to_analysis_storage_cleanup_dry_run_execution_v1` simulated the cleanup candidates.
- `video_to_analysis_storage_cleanup_execution_approval_v1` approved the bounded execution scope.
- `video_to_analysis_storage_cleanup_bounded_execution_v1` deleted the approved old-version generated-truth candidates.

Latest active generated truth:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_storage_cleanup_bounded_execution_v1/
    storage_cleanup_bounded_execution_summary.json
```

It reports:

```text
goalAchieved = true
primaryBlocker = null
approvedCandidateCount = 1012
validatedTargetCount = 1012
actualDeletedPathCount = 1012
actualReclaimedBytes = 23981092
latestVersionDeletionBlockedCount = 0
pathGuardrailFailureCount = 0
nextRecommendedNextLever = video_to_analysis_storage_cleanup_closeout
```

Next deterministic work:

```text
video_to_analysis_storage_cleanup_closeout
```

This closeout should verify the storage cleanup lane, refresh docs/status, and select the next strategic lane after housekeeping.

Still frozen for product/runtime work: no training, no detector/candidate evaluation readiness, no promotion mutation, no runtime-default mutation, no video/data download, and no normal-match-storage mutation.

## Current V7.2 Video-To-Analysis Position

The roadmap completed storage cleanup execution approval. No cleanup mutation happened yet.

Latest completed chain:

- `video_to_analysis_storage_cleanup_approval_v1` approved only dry-run planning.
- `video_to_analysis_storage_cleanup_dry_run_execution_v1` simulated the cleanup candidates.
- `video_to_analysis_storage_cleanup_execution_approval_v1` approved the dry-run candidate scope for a future bounded runner.

Latest active generated truth:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_storage_cleanup_execution_approval_v1/
    storage_cleanup_execution_approval_summary.json
```

It reports:

```text
goalAchieved = true
primaryBlocker = null
cleanupExecutionApproved = true
approvedExecutionMode = bounded_generated_truth_archive_delete
approvedCandidateCount = 1012
approvedCandidateBytes = 23981092
cleanupMutationExecuted = false
generatedTruthDeleteAllowed = false
nextRecommendedNextLever = video_to_analysis_storage_cleanup_bounded_execution
```

Next deterministic work:

```text
video_to_analysis_storage_cleanup_bounded_execution
```

This next lane is the first one that may perform a bounded archive/delete mutation, and it must verify the approved scope, path existence, latest-version preservation, and final guardrails before touching files.

Still frozen in the approval batch: no training, no detector/candidate evaluation readiness, no promotion mutation, no runtime-default mutation, no video/data download, no normal-match-storage mutation, no cleanup mutation, and no generated-truth deletion.

## Current V7.2 Video-To-Analysis Position

The roadmap completed storage cleanup approval and dry-run execution. No deletion happened.

Latest completed chain:

- `video_to_analysis_storage_cleanup_approval_v1` approved only a dry-run cleanup plan.
- `video_to_analysis_storage_cleanup_dry_run_execution_v1` simulated the approved candidate set.

Latest active generated truth:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_storage_cleanup_dry_run_execution_v1/
    storage_cleanup_dry_run_execution_summary.json
```

It reports:

```text
goalAchieved = true
primaryBlocker = null
storageCleanupDryRunExecuted = true
simulatedDeletedPathCount = 1012
simulatedReclaimableBytes = 23981092
actualDeletedPathCount = 0
cleanupMutationExecuted = false
generatedTruthDeleteAllowed = false
nextRecommendedNextLever = video_to_analysis_storage_cleanup_execution_approval
```

Next deterministic work:

```text
video_to_analysis_storage_cleanup_execution_approval
```

This next lane must explicitly approve the exact archive/delete scope before any mutation. Do not infer deletion approval from the dry-run result.

Still frozen: no training, no detector/candidate evaluation readiness, no promotion mutation, no runtime-default mutation, no video/data download, no normal-match-storage mutation, no cleanup mutation, and no generated-truth deletion.

## Current V7.2 Video-To-Analysis Position

The roadmap completed the user-facing release/readout lane and the storage cleanup approval gate.

Latest completed chain:

- `video_to_analysis_user_facing_release_readout_v1` routed to storage cleanup approval.
- `video_to_analysis_storage_cleanup_approval_v1` wrote the approval package:
  - `storage_cleanup_approval_summary.json`
  - `storage_cleanup_approval_contract.json`
  - `cleanup_candidate_manifest.json`
  - `artifact_retention_decision_matrix.json`
  - `guardrail_audit.json`

Latest active generated truth:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_storage_cleanup_approval_v1/
    storage_cleanup_approval_summary.json
```

It reports:

```text
goalAchieved = true
primaryBlocker = null
storageCleanupApprovalReady = true
storageCleanupDryRunApproved = true
cleanupExecutionApproved = false
cleanupMutationExecuted = false
generatedTruthDeleteAllowed = false
nextRecommendedNextLever = video_to_analysis_storage_cleanup_dry_run_execution
```

Next deterministic work:

```text
video_to_analysis_storage_cleanup_dry_run_execution
```

This next lane should remain dry-run/planning first. Do not delete generated truth unless a later generated artifact explicitly approves a bounded execution scope.

Still frozen: no training, no detector/candidate evaluation readiness, no promotion mutation, no runtime-default mutation, no video/data download, no normal-match-storage mutation, no cleanup mutation, and no generated-truth deletion.

## Current V7.2 Video-To-Analysis Position

The roadmap selected and completed the user-facing release/readout lane.

Latest completed chain:

- `video_to_analysis_next_strategic_lane_selection_v1` selected `user_facing_release_readout`.
- `video_to_analysis_user_facing_release_readout_v1` wrote the shareable release readout:

```text
docs/video-to-analysis-user-facing-release-readout-2026-05-09.md
```

Latest active generated truth:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_user_facing_release_readout_v1/
    user_facing_release_readout_summary.json
```

It reports:

```text
goalAchieved = true
primaryBlocker = null
userFacingReleaseReadoutReady = true
nextRecommendedNextLever = video_to_analysis_storage_cleanup_approval
```

Next deterministic work:

```text
video_to_analysis_storage_cleanup_approval
```

This should be approval/planning first. Do not delete generated truth just because storage cleanup is the next lane.

Still frozen: no training, no detector/candidate evaluation readiness, no promotion mutation, no runtime-default mutation, no video/data download, no normal-match-storage mutation, no cleanup mutation, and no generated-truth deletion.

## Current V7.2 Video-To-Analysis Position

The current module has moved from v38 growth-lane closeout into release/readout product surfacing.

Latest completed chain:

- `video_to_analysis_release_readout_pack_v1` packaged the v38 closeout, external benchmark product binding, and runtime operational completion into an operator-facing readout.
- `video_to_analysis_release_readout_route_binding_v1` bound and smoked the release/readout routes:
  - `/api/video-to-analysis/release-readout`
  - `/video-to-analysis/release-readout`
  - API/HTML `200 / 200`

Latest active generated truth:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_release_readout_route_binding_v1/
    release_readout_route_binding_summary.json
```

It reports:

```text
goalAchieved = true
primaryBlocker = null
releaseReadoutRouteReady = true
nextRecommendedNextLever = video_to_analysis_next_strategic_lane_selection
```

Next deterministic work:

```text
video_to_analysis_next_strategic_lane_selection
```

That gate should choose one of the strategic lanes from:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_release_readout_pack_v1/
    next_strategic_lane_matrix.json
```

Still frozen: no training, no detector/candidate evaluation readiness, no promotion mutation, no runtime-default mutation, no video/data download, no normal-match-storage mutation, no cleanup mutation, and no generated-truth deletion.

## Current V7.2 Video-To-Analysis Position

The active growth lane reached the finite v38 stop gate defined in `docs/superpowers/plans/2026-05-09-video-to-analysis-growth-lane-finish-roadmap.md`.

Latest completed chain:

- Five deterministic growth cycles ran from `video_to_analysis_next_sample_selection_snapshot_v33` through `video_to_analysis_next_sample_selection_snapshot_v38`.
- v33-v37 next-sample queues were consumed through execution ranges v129-v131, v133-v135, v137-v139, v141-v143, and v145-v147.
- Exhaustion approvals v132, v136, v140, v144, and v148 proved each queue empty before replenishment.
- Cleanup maps v131, v135, v139, v143, and v147 ran without deletion.
- Source-pool replenishment v19-v23 approved five bounded candidates each.
- Real-video scaleouts v34-v38 each executed `5 / 5`, route-smoked, closed, and wrote the next snapshot.

Latest active generated truth:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_next_sample_selection_snapshot_v38/
    next_sample_selection_snapshot_summary.json
```

It reports:

```text
goalAchieved = true
primaryBlocker = null
candidateSampleCount = 3
candidateSampleIds =
  operator_uploaded_local_video_replenishment_candidate_v23
  soccernet_bounded_224p_member_replenishment_candidate_v23
  existing_normal_storage_video_replenishment_candidate_v23
nextRecommendedNextLever = video_to_analysis_bounded_next_sample_execution_approval
```

Next deterministic work for this module:

```text
write and verify docs/video-to-analysis-growth-lane-closeout-readout-2026-05-09.md
```

Do not continue the bounded growth loop from v38 until the closeout readout is complete and the operator chooses that strategic lane again.

Still frozen: no training, no detector/candidate evaluation readiness, no promotion mutation, no runtime-default mutation, no video/data download, no normal-match-storage mutation, and no generated-truth deletion.

## Current V7.2 Video-To-Analysis Position

The active growth lane has advanced another replenishment/scaleout cycle and now has a fresh v33 next-sample queue ready.

Latest completed chain:

- v32 next-sample queue consumed through `video_to_analysis_bounded_next_sample_execution_v125`, `v126`, and `v127`.
- v128 approval proved that queue exhausted.
- v127 cleanup map ran without deletion.
- v62 plan refresh plus v30 source-sampling expansion proved generated source sampling exhausted.
- v18 roadmap direction snapshot routed to source-pool replenishment.
- v18 source-pool replenishment generated five fresh bounded source candidates.
- v63 plan refresh selected five cases from the v18 approved pool.
- v33 real-video scaleout approved, executed `5 / 5`, route-smoked, closed, and wrote a new next-sample snapshot.

Latest active generated truth:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_next_sample_selection_snapshot_v33/
    next_sample_selection_snapshot_summary.json
```

It reports:

```text
goalAchieved = true
primaryBlocker = null
candidateSampleCount = 3
candidateSampleIds =
  operator_uploaded_local_video_replenishment_candidate_v18
  soccernet_bounded_224p_member_replenishment_candidate_v18
  existing_normal_storage_video_replenishment_candidate_v18
nextRecommendedNextLever = video_to_analysis_bounded_next_sample_execution_approval
```

Next deterministic work:

```text
video_to_analysis_bounded_next_sample_execution_approval
-> bounded next-sample execution/report/closeout for the v33 three-sample queue
-> pool exhaustion proof
-> cleanup map / scaleout refresh decision
```

Still frozen: no training, no detector/candidate evaluation readiness, no promotion mutation, no runtime-default mutation, no video/data download, and no normal-match-storage mutation.

## Current V7.2 Video-To-Analysis Position

The active growth lane has advanced another replenishment/scaleout cycle and now has a fresh v32 next-sample queue ready.

Latest completed chain:

- v31 next-sample queue consumed through `video_to_analysis_bounded_next_sample_execution_v121`, `v122`, and `v123`.
- v124 approval proved that queue exhausted.
- v123 cleanup map ran without deletion.
- v60 plan refresh plus v29 source-sampling expansion proved generated source sampling exhausted.
- v17 roadmap direction snapshot routed to source-pool replenishment.
- v17 source-pool replenishment generated five fresh bounded source candidates.
- v61 plan refresh selected five cases from the v17 approved pool.
- v32 real-video scaleout approved, executed `5 / 5`, route-smoked, closed, and wrote a new next-sample snapshot.

Latest active generated truth:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_next_sample_selection_snapshot_v32/
    next_sample_selection_snapshot_summary.json
```

It reports:

```text
goalAchieved = true
primaryBlocker = null
candidateSampleCount = 3
candidateSampleIds =
  operator_uploaded_local_video_replenishment_candidate_v17
  soccernet_bounded_224p_member_replenishment_candidate_v17
  existing_normal_storage_video_replenishment_candidate_v17
nextRecommendedNextLever = video_to_analysis_bounded_next_sample_execution_approval
```

Next deterministic work:

```text
video_to_analysis_bounded_next_sample_execution_approval
-> bounded next-sample execution/report/closeout for the v32 three-sample queue
-> pool exhaustion proof
-> cleanup map / scaleout refresh decision
```

Still frozen: no training, no detector/candidate evaluation readiness, no promotion mutation, no runtime-default mutation, no video/data download, and no normal-match-storage mutation.

## Current V7.2 Video-To-Analysis Position

The active growth lane advanced through five more replenishment/scaleout cycles and now has a fresh v31 next-sample queue ready.

Latest completed chain:

- v26-v30 next-sample queues were consumed through execution ranges v101-v103, v105-v107, v109-v111, v113-v115, and v117-v119.
- Exhaustion approvals v104, v108, v112, v116, and v120 proved each queue exhausted before replenishment.
- Cleanup maps v103, v107, v111, v115, and v119 ran without deletion.
- Source-sampling expansion v24-v28 proved generated source sampling exhausted each time.
- Roadmap direction snapshots v12-v16 routed each exhausted state to source-pool replenishment.
- Source-pool replenishment v12-v16 approved five bounded candidates each.
- Real-video scaleouts v27-v31 each executed `5 / 5`, route-smoked, closed, and wrote the next snapshot.

Latest active generated truth:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_next_sample_selection_snapshot_v31/
    next_sample_selection_snapshot_summary.json
```

It reports:

```text
goalAchieved = true
primaryBlocker = null
candidateSampleCount = 3
candidateSampleIds =
  operator_uploaded_local_video_replenishment_candidate_v16
  soccernet_bounded_224p_member_replenishment_candidate_v16
  existing_normal_storage_video_replenishment_candidate_v16
nextRecommendedNextLever = video_to_analysis_bounded_next_sample_execution_approval
```

Next deterministic work:

```text
video_to_analysis_bounded_next_sample_execution_approval
-> bounded next-sample execution/report/closeout for the v31 three-sample queue
-> pool exhaustion proof
-> cleanup map / scaleout refresh decision
```

Still frozen: no training, no detector/candidate evaluation readiness, no promotion mutation, no runtime-default mutation, no video/data download, and no normal-match-storage mutation.

## Current V7.2 Video-To-Analysis Position

The active growth lane advanced through five more replenishment/scaleout cycles and now has a fresh v26 next-sample queue ready.

Latest completed chain:

- v21-v25 next-sample queues were consumed through execution ranges v81-v83, v85-v87, v89-v91, v93-v95, and v97-v99.
- Exhaustion approvals v84, v88, v92, v96, and v100 proved each queue exhausted before replenishment.
- Cleanup maps v83, v87, v91, v95, and v99 ran without deletion.
- Source-sampling expansion v19-v23 proved generated source sampling exhausted each time.
- Roadmap direction snapshots v7-v11 routed each exhausted state to source-pool replenishment.
- Source-pool replenishment v7-v11 approved five bounded candidates each.
- Real-video scaleouts v22-v26 each executed `5 / 5`, route-smoked, closed, and wrote the next snapshot.

Latest active generated truth:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_next_sample_selection_snapshot_v26/
    next_sample_selection_snapshot_summary.json
```

It reports:

```text
goalAchieved = true
primaryBlocker = null
candidateSampleCount = 3
candidateSampleIds =
  operator_uploaded_local_video_replenishment_candidate_v11
  soccernet_bounded_224p_member_replenishment_candidate_v11
  existing_normal_storage_video_replenishment_candidate_v11
nextRecommendedNextLever = video_to_analysis_bounded_next_sample_execution_approval
```

Next deterministic work:

```text
video_to_analysis_bounded_next_sample_execution_approval
-> bounded next-sample execution/report/closeout for the v26 three-sample queue
-> pool exhaustion proof
-> cleanup map / scaleout refresh decision
```

Still frozen: no training, no detector/candidate evaluation readiness, no promotion mutation, no runtime-default mutation, no video/data download, and no normal-match-storage mutation.

## Current V7.2 Video-To-Analysis Position

The active growth lane has advanced another replenishment/scaleout cycle and now has a fresh v21 next-sample queue ready.

Latest completed chain:

- v20 next-sample queue consumed through `video_to_analysis_bounded_next_sample_execution_v77`, `v78`, and `v79`.
- v80 approval proved that queue exhausted.
- v79 cleanup map ran without deletion.
- v38 plan refresh plus v18 source-sampling expansion proved generated source sampling exhausted.
- v6 roadmap direction snapshot routed to source-pool replenishment.
- v6 source-pool replenishment generated five fresh bounded source candidates.
- v39 plan refresh selected five cases from the v6 approved pool.
- v21 real-video scaleout approved, executed `5 / 5`, route-smoked, closed, and wrote a new next-sample snapshot.

Latest active generated truth:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_next_sample_selection_snapshot_v21/
    next_sample_selection_snapshot_summary.json
```

It reports:

```text
goalAchieved = true
primaryBlocker = null
candidateSampleCount = 3
candidateSampleIds =
  operator_uploaded_local_video_replenishment_candidate_v6
  soccernet_bounded_224p_member_replenishment_candidate_v6
  existing_normal_storage_video_replenishment_candidate_v6
nextRecommendedNextLever = video_to_analysis_bounded_next_sample_execution_approval
```

Next deterministic work:

```text
video_to_analysis_bounded_next_sample_execution_approval
-> bounded next-sample execution/report/closeout for the v21 three-sample queue
-> pool exhaustion proof
-> cleanup map / scaleout refresh decision
```

Still frozen: no training, no detector/candidate evaluation readiness, no promotion mutation, no runtime-default mutation, no video/data download, and no normal-match-storage mutation.

## Current V7.2 Video-To-Analysis Position

The active growth lane has advanced another replenishment/scaleout cycle and now has a fresh v20 next-sample queue ready.

Latest completed chain:

- v19 next-sample queue consumed through `video_to_analysis_bounded_next_sample_execution_v73`, `v74`, and `v75`.
- v76 approval proved that queue exhausted.
- v75 cleanup map ran without deletion.
- v36 plan refresh plus v17 source-sampling expansion proved generated source sampling exhausted.
- v5 roadmap direction snapshot routed to source-pool replenishment.
- v5 source-pool replenishment generated five fresh bounded source candidates.
- v37 plan refresh selected five cases from the v5 approved pool.
- v20 real-video scaleout approved, executed `5 / 5`, route-smoked, closed, and wrote a new next-sample snapshot.

Latest active generated truth:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_next_sample_selection_snapshot_v20/
    next_sample_selection_snapshot_summary.json
```

It reports:

```text
goalAchieved = true
primaryBlocker = null
candidateSampleCount = 3
candidateSampleIds =
  operator_uploaded_local_video_replenishment_candidate_v5
  soccernet_bounded_224p_member_replenishment_candidate_v5
  existing_normal_storage_video_replenishment_candidate_v5
nextRecommendedNextLever = video_to_analysis_bounded_next_sample_execution_approval
```

Next deterministic work:

```text
video_to_analysis_bounded_next_sample_execution_approval
-> bounded next-sample execution/report/closeout for the v20 three-sample queue
-> pool exhaustion proof
-> cleanup map / scaleout refresh decision
```

Still frozen: no training, no detector/candidate evaluation readiness, no promotion mutation, no runtime-default mutation, no video/data download, and no normal-match-storage mutation.

## Current V7.2 Video-To-Analysis Position

The active growth lane has advanced another replenishment/scaleout cycle and now has a fresh v19 next-sample queue ready.

Latest completed chain:

- v18 next-sample queue consumed through `video_to_analysis_bounded_next_sample_execution_v69`, `v70`, and `v71`.
- v72 approval proved that queue exhausted.
- v71 cleanup map ran without deletion.
- v33 plan refresh plus v16 source-sampling expansion proved generated source sampling exhausted.
- v4 roadmap direction snapshot routed to source-pool replenishment.
- v4 source-pool replenishment generated five fresh bounded source candidates.
- v35 plan refresh selected five cases from the v4 approved pool.
- v19 real-video scaleout approved, executed `5 / 5`, route-smoked, closed, and wrote a new next-sample snapshot.

Latest active generated truth:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_next_sample_selection_snapshot_v19/
    next_sample_selection_snapshot_summary.json
```

It reports:

```text
goalAchieved = true
primaryBlocker = null
candidateSampleCount = 3
candidateSampleIds =
  operator_uploaded_local_video_replenishment_candidate_v4
  soccernet_bounded_224p_member_replenishment_candidate_v4
  existing_normal_storage_video_replenishment_candidate_v4
nextRecommendedNextLever = video_to_analysis_bounded_next_sample_execution_approval
```

Next deterministic work:

```text
video_to_analysis_bounded_next_sample_execution_approval
-> bounded next-sample execution/report/closeout for the v19 three-sample queue
-> pool exhaustion proof
-> cleanup map / scaleout refresh decision
```

Still frozen: no training, no detector/candidate evaluation readiness, no promotion mutation, no runtime-default mutation, no video/data download, and no normal-match-storage mutation.

## Current V7.2 Video-To-Analysis Position

The active growth lane has advanced one more replenishment/scaleout cycle and now has a fresh v18 next-sample queue ready.

Latest completed chain:

- v17 next-sample queue consumed through `video_to_analysis_bounded_next_sample_execution_v65`, `v66`, and `v67`.
- v68 approval proved that queue exhausted.
- v67 cleanup map ran without deletion.
- v31 plan refresh plus v15 source-sampling expansion proved generated source sampling exhausted.
- v3 roadmap direction snapshot routed to source-pool replenishment.
- v3 source-pool replenishment generated five fresh bounded source candidates.
- v32 plan refresh selected five cases.
- v18 real-video scaleout approved, executed `5 / 5`, route-smoked, closed, and wrote a new next-sample snapshot.

Latest active generated truth:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_next_sample_selection_snapshot_v18/
    next_sample_selection_snapshot_summary.json
```

It reports:

```text
goalAchieved = true
primaryBlocker = null
candidateSampleCount = 3
candidateSampleIds =
  operator_uploaded_local_video_replenishment_candidate_v3
  soccernet_bounded_224p_member_replenishment_candidate_v3
  existing_normal_storage_video_replenishment_candidate_v3
nextRecommendedNextLever = video_to_analysis_bounded_next_sample_execution_approval
```

Next deterministic work:

```text
video_to_analysis_bounded_next_sample_execution_approval
-> bounded next-sample execution/report/closeout for the v18 three-sample queue
-> pool exhaustion proof
-> cleanup map / scaleout refresh decision
```

Still frozen: no training, no detector/candidate evaluation readiness, no promotion mutation, no runtime-default mutation, no video/data download, and no normal-match-storage mutation.

## Current V7.2 Video-To-Analysis Position

The promoted/runtime lane remains operationally complete. The active growth lane has just been repaired and replenished again:

- v16 replenished next-sample queue: consumed through `video_to_analysis_bounded_next_sample_execution_v61`, `v62`, and `v63`.
- v64 approval: correctly proved the v16 next-sample queue exhausted.
- v29 plan refresh plus v14 source-sampling expansion: proved the generated source-sampling pool itself was exhausted.
- v2 roadmap direction snapshot: now routes source-sampling exhaustion to `video_to_analysis_source_pool_replenishment_plan`, not stale promotion-review design.
- v2 source-pool replenishment: generated five fresh tranche-specific bounded candidates.
- v30 scaleout plan refresh: selected five fresh cases.
- v17 real-video scaleout: approved, executed `5 / 5`, route-smoked, closed, and wrote a new next-sample snapshot.

Latest active generated truth:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_next_sample_selection_snapshot_v17/
    next_sample_selection_snapshot_summary.json
```

It reports:

```text
goalAchieved = true
primaryBlocker = null
candidateSampleCount = 3
candidateSampleIds =
  operator_uploaded_local_video_replenishment_candidate_v2
  soccernet_bounded_224p_member_replenishment_candidate_v2
  existing_normal_storage_video_replenishment_candidate_v2
nextRecommendedNextLever = video_to_analysis_bounded_next_sample_execution_approval
```

Next deterministic work:

```text
video_to_analysis_bounded_next_sample_execution_approval
-> bounded next-sample execution/report/closeout for the v17 three-sample queue
-> pool exhaustion proof
-> cleanup map / scaleout refresh decision
```

Still frozen: no training, no detector/candidate evaluation readiness, no promotion mutation, no runtime-default mutation, no video/data download, and no normal-match-storage mutation.

## Current V7.2 Video-To-Analysis Position

The v7.2 promoted runtime/product lane is now operationally complete. The growth lane is blocked only because generated bounded source-sampling inputs are exhausted.

Current terminal/health truth:

- `video_to_analysis_promoted_runtime_operational_completion_summary_v1`
  - `goalAchieved = true`
  - `primaryBlocker = null`
  - `videoToAnalysisPromotedRuntimeOperationallyComplete = true`
  - `releasedRuntimeVersion = v7.2`
  - `nextRecommendedNextLever = video_to_analysis_steady_state_monitoring_cycle`
- `video_to_analysis_steady_state_monitoring_cycle_v1`
  - `goalAchieved = true`
  - `primaryBlocker = null`
  - `steadyStateMonitoringCyclePassed = true`
  - `oldFailingSourceNotViableBlockerDead = true`
  - `nextRecommendedNextLever = video_to_analysis_operational_backlog_prioritization`
- `video_to_analysis_operational_sprint_closeout_v1`
  - `goalAchieved = true`
  - `operationalSprintClosed = true`
  - `nextRecommendedNextLever = video_to_analysis_growth_lane_decision_snapshot`
- Latest `video_to_analysis_real_video_scaleout_execution_approval_v1`
  - `goalAchieved = false`
  - `primaryBlocker = video_to_analysis_real_video_scaleout_plan_insufficient`
  - `sourcePlanDir = video_to_analysis_real_video_scaleout_plan_refresh_v27`
  - `sourceSamplingDir = video_to_analysis_real_video_scaleout_source_sampling_expansion_v13`
  - `sourceSamplingPoolExhausted = true`
  - `nextRecommendedNextLever = video_to_analysis_next_roadmap_direction_snapshot`

Next roadmap decision:

- Do not loop existing generated source sampling: it is exhausted.
- Do not rerun scaleout approval until a new approved source/sample pool exists.
- The next useful family should replenish or approve new bounded source samples, then re-enter scaleout.

## Current V7.2 Data-Lane Position

Generated truth now advances the video-to-analysis finish-line/product lane to:

`video_to_analysis_real_video_scaleout_source_sampling_expansion`

Latest completed batch:

- `video_to_analysis_real_video_scaleout_plan_refresh_v21`
- `goalAchieved = false`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = video_to_analysis_real_video_scaleout_candidate_pool_insufficient`
- `availableFreshScaleoutCaseCount = 3`
- `requiredFreshScaleoutCaseCount = 5`
- `detectorEvaluationExecuted = false`
- `normalMatchStorageMutationExecuted = false`
- `videoDownloadExecuted = false`
- `dataDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = video_to_analysis_real_video_scaleout_source_sampling_expansion`

Recently completed dynamic source-sampling expansion v8/v9 and scaleout v11/v12:

- `video_to_analysis_real_video_scaleout_source_sampling_expansion_v8`: generated `6` fresh candidates and unlocked v11 scaleout.
- `video_to_analysis_real_video_scaleout_bounded_execution_v11`: passed `5 / 5`.
- `video_to_analysis_next_sample_selection_snapshot_v11` selected and v41/v42/v43 consumed:
  - `operator_canary_tenth_followup_clip`
  - `soccernet_twenty_first_bounded_member`
  - `normal_storage_tenth_followup_upload`
- `video_to_analysis_real_video_scaleout_source_sampling_expansion_v9`: generated `6` more fresh candidates and unlocked v12 scaleout.
- `video_to_analysis_real_video_scaleout_bounded_execution_v12`: passed `5 / 5`.
- `video_to_analysis_next_sample_selection_snapshot_v12` selected and v45/v46/v47 consumed:
  - `operator_canary_eleventh_followup_clip`
  - `soccernet_twenty_third_bounded_member`
  - `normal_storage_eleventh_followup_upload`
- `video_to_analysis_bounded_next_sample_execution_approval_v48` exhausted the v12 bounded queue and routed to plan refresh.

Previously completed batch:

- `video_to_analysis_real_video_scaleout_plan_refresh_v17`
- `goalAchieved = false`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = video_to_analysis_real_video_scaleout_candidate_pool_insufficient`
- `availableFreshScaleoutCaseCount = 3`
- `requiredFreshScaleoutCaseCount = 5`
- `detectorEvaluationExecuted = false`
- `normalMatchStorageMutationExecuted = false`
- `videoDownloadExecuted = false`
- `dataDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = video_to_analysis_real_video_scaleout_source_sampling_expansion`

Recently completed dynamic source-sampling expansion v6/v7 and scaleout v9/v10:

- `video_to_analysis_real_video_scaleout_source_sampling_expansion_v6`: generated `6` fresh candidates and unlocked v9 scaleout.
- `video_to_analysis_real_video_scaleout_bounded_execution_v9`: passed `5 / 5`.
- `video_to_analysis_next_sample_selection_snapshot_v9` selected and v33/v34/v35 consumed:
  - `operator_canary_eighth_followup_clip`
  - `soccernet_seventeenth_bounded_member`
  - `normal_storage_eighth_followup_upload`
- `video_to_analysis_real_video_scaleout_source_sampling_expansion_v7`: generated `6` more fresh candidates and unlocked v10 scaleout.
- `video_to_analysis_real_video_scaleout_bounded_execution_v10`: passed `5 / 5`.
- `video_to_analysis_next_sample_selection_snapshot_v10` selected and v37/v38/v39 consumed:
  - `operator_canary_ninth_followup_clip`
  - `soccernet_nineteenth_bounded_member`
  - `normal_storage_ninth_followup_upload`
- `video_to_analysis_bounded_next_sample_execution_approval_v40` exhausted the v10 bounded queue and routed to plan refresh.

Previously completed batch:

- `video_to_analysis_real_video_scaleout_plan_refresh_v13`
- `goalAchieved = false`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = video_to_analysis_real_video_scaleout_candidate_pool_insufficient`
- `availableFreshScaleoutCaseCount = 3`
- `requiredFreshScaleoutCaseCount = 5`
- `detectorEvaluationExecuted = false`
- `normalMatchStorageMutationExecuted = false`
- `videoDownloadExecuted = false`
- `dataDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = video_to_analysis_real_video_scaleout_source_sampling_expansion`

Recently completed dynamic source-sampling expansion v4/v5 and scaleout v7/v8:

- `video_to_analysis_real_video_scaleout_source_sampling_expansion_v4`: generated `6` fresh candidates and unlocked v7 scaleout.
- `video_to_analysis_real_video_scaleout_bounded_execution_v7`: passed `5 / 5`.
- `video_to_analysis_next_sample_selection_snapshot_v7` selected and v25/v26/v27 consumed:
  - `operator_canary_sixth_followup_clip`
  - `soccernet_thirteenth_bounded_member`
  - `normal_storage_sixth_followup_upload`
- `video_to_analysis_real_video_scaleout_source_sampling_expansion_v5`: generated `6` more fresh candidates and unlocked v8 scaleout.
- `video_to_analysis_real_video_scaleout_bounded_execution_v8`: passed `5 / 5`.
- `video_to_analysis_next_sample_selection_snapshot_v8` selected and v29/v30/v31 consumed:
  - `operator_canary_seventh_followup_clip`
  - `soccernet_fifteenth_bounded_member`
  - `normal_storage_seventh_followup_upload`
- `video_to_analysis_bounded_next_sample_execution_approval_v32` exhausted the v8 bounded queue and routed to plan refresh.

Previously completed batch:

- `video_to_analysis_real_video_scaleout_plan_refresh_v9`
- `goalAchieved = false`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = video_to_analysis_real_video_scaleout_candidate_pool_insufficient`
- `availableFreshScaleoutCaseCount = 3`
- `requiredFreshScaleoutCaseCount = 5`
- `detectorEvaluationExecuted = false`
- `normalMatchStorageMutationExecuted = false`
- `videoDownloadExecuted = false`
- `dataDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = video_to_analysis_real_video_scaleout_source_sampling_expansion`

Recently completed source-sampling expansion v2/v3 and scaleout v5/v6:

- `video_to_analysis_real_video_scaleout_source_sampling_expansion_v2`: generated `6` fresh candidates and unlocked v5 scaleout.
- `video_to_analysis_real_video_scaleout_bounded_execution_v5`: passed `5 / 5`.
- `video_to_analysis_next_sample_selection_snapshot_v5` selected and v17/v18/v19 consumed:
  - `operator_canary_fourth_followup_clip`
  - `soccernet_ninth_bounded_member`
  - `normal_storage_fourth_followup_upload`
- `video_to_analysis_real_video_scaleout_source_sampling_expansion_v3`: generated `6` more fresh candidates and unlocked v6 scaleout.
- `video_to_analysis_real_video_scaleout_bounded_execution_v6`: passed `5 / 5`.
- `video_to_analysis_next_sample_selection_snapshot_v6` selected and v21/v22/v23 consumed:
  - `operator_canary_fifth_followup_clip`
  - `soccernet_eleventh_bounded_member`
  - `normal_storage_fifth_followup_upload`
- `video_to_analysis_bounded_next_sample_execution_approval_v24` exhausted the v6 bounded queue and routed to plan refresh.

Previously completed batch:

- `video_to_analysis_real_video_scaleout_plan_refresh_v5`
- `goalAchieved = false`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = video_to_analysis_real_video_scaleout_candidate_pool_insufficient`
- `availableFreshScaleoutCaseCount = 3`
- `requiredFreshScaleoutCaseCount = 5`
- `detectorEvaluationExecuted = false`
- `normalMatchStorageMutationExecuted = false`
- `videoDownloadExecuted = false`
- `dataDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = video_to_analysis_real_video_scaleout_source_sampling_expansion`

Recently completed source-sampling expansion and v4 scaleout:

- `video_to_analysis_real_video_scaleout_plan_refresh_v3`: detected candidate-pool insufficiency with only `2 / 5` fresh cases.
- `video_to_analysis_real_video_scaleout_source_sampling_expansion_v1`: generated `6` fresh bounded candidates.
- `video_to_analysis_real_video_scaleout_plan_refresh_v4`: selected `5` new cases.
- `video_to_analysis_real_video_scaleout_bounded_execution_v4`: passed `5 / 5`.
- `video_to_analysis_next_sample_selection_snapshot_v4`: selected:
  - `operator_canary_third_followup_clip`
  - `soccernet_seventh_bounded_member`
  - `normal_storage_third_followup_upload`
- v13/v14/v15 consumed those three samples.
- `video_to_analysis_bounded_next_sample_execution_approval_v16` exhausted the v4 bounded queue and routed to plan refresh.

Previously completed batch:

- `video_to_analysis_bounded_next_sample_execution_approval_v12`
- `goalAchieved = false`
- `primaryBlocker = video_to_analysis_bounded_next_sample_pool_exhausted`
- `remainingCandidateSampleCount = 0`
- `previouslyExecutedSampleIds = [normal_storage_followup_upload, normal_storage_recent_upload, normal_storage_second_followup_upload, operator_canary_followup_clip, operator_canary_second_followup_clip, operator_selected_canary_video, soccernet_fourth_bounded_member, soccernet_second_bounded_member, soccernet_third_bounded_member]`
- `detectorEvaluationExecuted = false`
- `normalMatchStorageMutationExecuted = false`
- `videoDownloadExecuted = false`
- `dataDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = video_to_analysis_real_video_scaleout_execution_approval`

Recently completed refreshed real-video scaleout:

- `video_to_analysis_real_video_scaleout_plan_refresh_v2`
- `video_to_analysis_real_video_scaleout_execution_approval_v3`
- `video_to_analysis_real_video_scaleout_bounded_execution_v3`
- `video_to_analysis_real_video_scaleout_report_route_binding_v3`
- `video_to_analysis_real_video_scaleout_lane_closeout_v3`
- `video_to_analysis_next_sample_selection_snapshot_v3`
- Second refreshed scaleout passed `5 / 5` bounded cases and generated three second-refresh next-sample candidates.

Recently completed refreshed bounded samples:

- `operator_canary_second_followup_clip`
- `soccernet_fourth_bounded_member`
- `normal_storage_second_followup_upload`

Already completed earlier bounded samples:

- `operator_selected_canary_video`
- `soccernet_second_bounded_member`
- `normal_storage_recent_upload`
- `operator_canary_followup_clip`
- `soccernet_third_bounded_member`
- `normal_storage_followup_upload`

Previously completed batch:

- `video_to_analysis_bounded_next_sample_execution_approval_v4`
- `goalAchieved = false`
- `primaryBlocker = video_to_analysis_bounded_next_sample_pool_exhausted`
- `remainingCandidateSampleCount = 0`
- `previouslyExecutedSampleIds = [normal_storage_recent_upload, operator_selected_canary_video, soccernet_second_bounded_member]`
- `detectorEvaluationExecuted = false`
- `normalMatchStorageMutationExecuted = false`
- `videoDownloadExecuted = false`
- `dataDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = video_to_analysis_real_video_scaleout_execution_approval`

Recently completed bounded next-sample candidates:

- `operator_selected_canary_video`
- `soccernet_second_bounded_member`
- `normal_storage_recent_upload`

Previously completed batch:

- `video_to_analysis_source_and_artifact_cleanup_map`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `cleanupMapReady = true`
- `artifactInventoryRowCount = 192`
- `artifactInventoryTotalBytes = 8103431631`
- `cleanupMutationExecuted = false`
- `generatedTruthDeleteAllowed = false`
- `detectorEvaluationExecuted = false`
- `normalMatchStorageMutationExecuted = false`
- `videoDownloadExecuted = false`
- `dataDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = video_to_analysis_bounded_next_sample_execution_approval`

Recently completed bounded next-sample chain:

- `video_to_analysis_bounded_next_sample_execution_approval_v1`
- `video_to_analysis_bounded_next_sample_execution_v1`
- `video_to_analysis_bounded_next_sample_report_route_binding_v1`
- `video_to_analysis_bounded_next_sample_closeout_v1`
- `video_to_analysis_scaleout_or_backlog_decision_snapshot_v1`
- `video_to_analysis_source_and_artifact_cleanup_map_v1`

Previously completed batch:

- `video_to_analysis_next_sample_selection_snapshot`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `nextSampleSelectionSnapshotReady = true`
- `selectedNextLever = video_to_analysis_bounded_next_sample_execution_approval`
- `detectorEvaluationExecuted = false`
- `normalMatchStorageMutationExecuted = false`
- `videoDownloadExecuted = false`
- `dataDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = video_to_analysis_bounded_next_sample_execution_approval`

Recently completed bounded real-video scaleout chain:

- `video_to_analysis_real_video_scaleout_execution_approval_v1`
- `video_to_analysis_real_video_scaleout_bounded_execution_v1`
- `video_to_analysis_real_video_scaleout_report_route_binding_v1`
- `video_to_analysis_real_video_scaleout_lane_closeout_v1`
- `video_to_analysis_next_sample_selection_snapshot_v1`

Previously completed batch:

- `video_to_analysis_growth_lane_decision_snapshot`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `growthLaneDecisionSnapshotReady = true`
- `selectedGrowthLever = video_to_analysis_real_video_scaleout_execution_approval`
- `detectorEvaluationExecuted = false`
- `normalMatchStorageMutationExecuted = false`
- `videoDownloadExecuted = false`
- `dataDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = video_to_analysis_real_video_scaleout_execution_approval`

Recently completed operational sprint:

- `football_external_benchmark_real_source_path_consolidation_v1`
- `video_to_analysis_real_video_scaleout_plan_v1`
- `video_to_analysis_steady_state_monitoring_recurring_schedule_v1`
- `video_to_analysis_operational_sprint_closeout_v1`
- `video_to_analysis_growth_lane_decision_snapshot_v1`

Previously completed batch:

- `video_to_analysis_operator_dashboard_polish`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `operatorDashboardPolished = true`
- `operatorDashboardRouteReady = true`
- `apiRoutePath = /api/video-to-analysis/operator-dashboard`
- `htmlRoutePath = /video-to-analysis/operator-dashboard`
- `apiRouteStatusCode = 200`
- `htmlRouteStatusCode = 200`
- `detectorEvaluationExecuted = false`
- `normalMatchStorageMutationExecuted = false`
- `videoDownloadExecuted = false`
- `dataDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = football_external_benchmark_real_source_path_consolidation`

Previously completed batch:

- `video_to_analysis_storage_retention_and_artifact_hygiene`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `storageHygienePlanReady = true`
- `artifactInventoryReady = true`
- `retentionPolicyReady = true`
- `cleanupExecutionReady = false`
- `cleanupMutationExecuted = false`
- `generatedTruthDeleteAllowed = false`
- `inventoryRowCount = 15`
- `totalInventoriedBytes = 9813341409`
- `cleanupCandidateCount = 0`
- `detectorEvaluationExecuted = false`
- `normalMatchStorageMutationExecuted = false`
- `videoDownloadExecuted = false`
- `dataDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = video_to_analysis_operator_dashboard_polish`

Previously completed batch:

- `video_to_analysis_operational_backlog_prioritization`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `operationalBacklogPrioritized = true`
- `selectedOperationalLever = video_to_analysis_storage_retention_and_artifact_hygiene`
- `backlogItemCount = 5`
- `sourceSteadyStateMonitoringCyclePassed = true`
- `detectorEvaluationExecuted = false`
- `normalMatchStorageMutationExecuted = false`
- `videoDownloadExecuted = false`
- `dataDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = video_to_analysis_storage_retention_and_artifact_hygiene`

Previously completed batch:

- `video_to_analysis_steady_state_monitoring_cycle`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `steadyStateMonitoringCyclePassed = true`
- `promotedRuntimeHealthy = true`
- `releasedRuntimeVersion = v7.2`
- `registryMatchesPromotedV7_2DefaultRuntime = true`
- `routeSmokePassedCount = 5`
- `oldFailingSourceNotViableBlockerDead = true`
- `detectorEvaluationExecuted = false`
- `normalMatchStorageMutationExecuted = false`
- `videoDownloadExecuted = false`
- `dataDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = video_to_analysis_operational_backlog_prioritization`

Previously completed batch:

- `video_to_analysis_promoted_runtime_operational_completion_summary`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `videoToAnalysisPromotedRuntimeOperationallyComplete = true`
- `releasedRuntimeVersion = v7.2`
- `steadyStateMonitoringReady = true`
- `detectorEvaluationExecuted = false`
- `normalMatchStorageMutationExecuted = false`
- `videoDownloadExecuted = false`
- `dataDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = video_to_analysis_steady_state_monitoring_cycle`

Recently completed promoted-runtime post-release monitoring and operational completion:

- `video_to_analysis_promoted_runtime_post_release_monitoring_plan_v1`
- `video_to_analysis_promoted_runtime_post_release_monitoring_execution_v1`
- `video_to_analysis_promoted_runtime_post_release_monitoring_route_binding_v1`
- `video_to_analysis_promoted_runtime_operational_completion_summary_v1`

Recently completed promoted-runtime release closeout:

- `video_to_analysis_promoted_runtime_release_closeout_v1`
- `video_to_analysis_release_completion_summary_v1`

Recently completed promoted-runtime acceptance:

- `video_to_analysis_promoted_runtime_operator_acceptance_trial_v1`

Recently completed promotion-review sweep:

- `video_to_analysis_promotion_review_design_v1`
- `video_to_analysis_promotion_review_execution_v1`
- `video_to_analysis_promotion_review_report_binding_v1`
- `video_to_analysis_promotion_review_report_route_binding_v1`
- `video_to_analysis_promotion_review_closeout_v1`

Recently completed ten-batch sweep:

- `video_to_analysis_post_release_monitoring_plan_v1`
- `video_to_analysis_post_release_monitoring_route_binding_v1`
- `video_to_analysis_post_release_monitoring_closeout_v1`
- `video_to_analysis_detector_evaluation_reentry_plan_v1`
- `video_to_analysis_detector_evaluation_reentry_approval_v1`
- `video_to_analysis_detector_evaluation_bounded_existing_artifact_execution_v1`
- `video_to_analysis_detector_evaluation_report_binding_v1`
- `video_to_analysis_detector_evaluation_report_route_binding_v1`
- `video_to_analysis_detector_evaluation_lane_closeout_v1`
- `video_to_analysis_next_roadmap_direction_snapshot_v1`

Previous generated truth advanced the v7.1/v7.2 crop-detector lane to:

`football_external_soccertrack_authenticated_fixture_credential_setup`

Older completed batch:

- `football_external_soccertrack_authenticated_fixture_access_approval`
- `goalAchieved = false`
- `roadmapAdvanceAllowed = false`
- `primaryBlocker = football_external_soccertrack_authenticated_fixture_credential_missing`
- `authenticatedFixtureAccessApproved = false`
- `credentialRuntimeAvailable = false`
- `credentialPersisted = false`
- `sampleDownloadExecuted = false`
- `datasetDownloadExecuted = false`
- `fullDatasetDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = football_external_soccertrack_authenticated_fixture_credential_setup`
- `football_external_soccertrack_fixture_source_access_review`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `fixtureSourceAccessReviewReady = true`
- `githubPublicFixtureAvailable = false`
- `huggingFaceAccessible = false`
- `huggingFaceAuthRequired = true`
- `huggingFaceStatusCode = 401`
- `credentialRuntimeAvailable = false`
- `sampleDownloadExecuted = false`
- `datasetDownloadExecuted = false`
- `fullDatasetDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = football_external_soccertrack_authenticated_fixture_access_approval`
- `football_external_soccertrack_controlled_sample_fetch`
- `goalAchieved = false`
- `roadmapAdvanceAllowed = false`
- `primaryBlocker = football_external_soccertrack_public_fixture_files_missing`
- `sourceTreeProbeExecuted = true`
- `completeOneMatchFixtureFound = false`
- `controlledSampleFetchExecuted = false`
- `downloadedFixtureFileCount = 0`
- `sampleDownloadExecuted = false`
- `datasetDownloadExecuted = false`
- `fullDatasetDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = football_external_soccertrack_fixture_source_access_review`
- `football_external_soccertrack_sample_fixture_materialization_approval`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `sampleFixtureMaterializationApproved = true`
- `sampleDownloadApproved = true`
- `sampleDownloadExecuted = false`
- `datasetDownloadApproved = false`
- `datasetDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = football_external_soccertrack_controlled_sample_fetch`
- `football_external_soccertrack_sample_ingestion_contract_prep`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `sampleIngestionContractReady = true`
- `selectedSampleResourceId = soccertrack_v2`
- `requiredTaskFixtures = [gsr, bas, mot]`
- `mappingCompletenessPassed = true`
- `sampleDownloadApprovalRequired = true`
- `sampleDownloadExecuted = false`
- `datasetDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = football_external_soccertrack_sample_fixture_materialization_approval`
- `football_external_soccertrack_schema_doc_parse`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `schemaDocParseReady = true`
- `parsedTaskIds = [gsr, bas, mot]`
- `fieldLevelParsedTaskIds = [gsr, bas]`
- `gsrParsedFieldCount = 10`
- `basParsedFieldCount = 9`
- `motParsedFieldCount = 6`
- `datasetDownloadExecuted = false`
- `sampleDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = football_external_soccertrack_sample_ingestion_contract_prep`
- `football_external_soccertrack_schema_doc_fetch`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `schemaDocFetchExecuted = true`
- `fetchedSchemaDocCount = 5`
- `fetchFailureCount = 0`
- `datasetDownloadExecuted = false`
- `sampleDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = football_external_soccertrack_schema_doc_parse`
- `football_external_soccertrack_schema_doc_fetch_approval`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `schemaDocFetchApproved = true`
- `schemaDocApprovedPathCount = 5`
- `schemaDocFetchExecuted = false`
- `datasetDownloadExecuted = false`
- `sampleDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = football_external_soccertrack_schema_doc_fetch`
- `football_external_soccertrack_sample_schema_probe`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `sampleSchemaProbeReady = true`
- `detectedTaskIds = [gsr, bas, mot]`
- `schemaDocCandidateCount = 5`
- `schemaDocFetchExecuted = false`
- `datasetDownloadExecuted = false`
- `sampleDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = football_external_soccertrack_schema_doc_fetch_approval`
- `football_external_soccernet_analysis_product_lane_closeout`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `analysisProductLaneClosed = true`
- `productUiRouteReady = true`
- `reportedFrameCount = 146893`
- `segmentCount = 196`
- `archiveDownloadExecuted = false`
- `video720pMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = football_external_safe_source_adapter_smoke_test`
- `football_external_soccernet_analysis_product_ui_route_implementation`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `productUiRouteReady = true`
- `apiRoutePath = /api/external/soccernet/full-analysis`
- `htmlRoutePath = /external/soccernet/full-analysis`
- `reportedFrameCount = 146893`
- `segmentCount = 196`
- `archiveDownloadExecuted = false`
- `video720pMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = football_external_soccernet_analysis_product_lane_closeout`
- `football_external_soccernet_analysis_product_ui_binding`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `productUiBindingReady = true`
- `reportedFrameCount = 146893`
- `segmentCount = 196`
- `archiveDownloadExecuted = false`
- `video720pMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = football_external_soccernet_analysis_product_ui_route_implementation`
- `football_external_soccernet_analysis_product_api_smoke`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `productApiSmokePassed = true`
- `reportedFrameCount = 146893`
- `segmentCount = 196`
- `archiveDownloadExecuted = false`
- `video720pMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = football_external_soccernet_analysis_product_ui_binding`
- `football_external_soccernet_full_analysis_product_integration`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `productFullAnalysisReady = true`
- `reportedFrameCount = 146893`
- `segmentCount = 196`
- `archiveDownloadExecuted = false`
- `video720pMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `candidateReadyForEvaluation = false`
- `nextRecommendedNextLever = football_external_soccernet_analysis_product_api_smoke`
- `football_external_soccernet_full_analysis_lane_closeout`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `fullAnalysisLaneClosed = true`
- `reportedFrameCount = 146893`
- `segmentCount = 196`
- `fullAnalysisProductIntegrationReady = true`
- `archiveDownloadExecuted = false`
- `video720pMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_full_analysis_product_integration`
- `football_external_soccernet_full_analysis_report_smoke`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `fullAnalysisReportReady = true`
- `reportedFrameCount = 146893`
- `segmentCount = 196`
- `archiveDownloadExecuted = false`
- `video720pMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_full_analysis_lane_closeout`
- `football_external_soccernet_full_analysis_execution`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `fullAnalysisExecutionApproved = true`
- `fullAnalysisExecutionExecuted = true`
- `approvedFrameCount = 146893`
- `processedFrameCount = 146893`
- `unreadableFrameCount = 0`
- `segmentCount = 196`
- `archiveDownloadExecuted = false`
- `video720pMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_full_analysis_report_smoke`
- `football_external_soccernet_full_analysis_execution_approval`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `fullAnalysisExecutionApproved = true`
- `fullAnalysisExecutionExecuted = false`
- `selectedVideoPath = /root/WorkSpace/fotball-analyst/backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_soccernet_video_member_extract_v1/extracted_video/england_efl/2019-2020/2019-10-01 - Middlesbrough - Preston North End/224p.mp4`
- `approvedFrameCount = 146893`
- `fps = 25.0`
- `resolution = 398x224`
- `archiveDownloadExecuted = false`
- `video720pMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_full_analysis_execution`
- `football_external_soccernet_bounded_analysis_lane_closeout`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `boundedAnalysisLaneClosed = true`
- `reportedFrameCount = 300`
- `fullAnalysisExecutionApprovalReady = true`
- `fullAnalysisExecutionApproved = false`
- `fullAnalysisExecuted = false`
- `archiveDownloadExecuted = false`
- `video720pMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_full_analysis_execution_approval`
- `football_external_soccernet_bounded_analysis_report_smoke`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `boundedAnalysisReportReady = true`
- `reportedFrameCount = 300`
- `fullAnalysisReady = false`
- `fullAnalysisExecuted = false`
- `archiveDownloadExecuted = false`
- `video720pMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_bounded_analysis_lane_closeout`
- `football_external_soccernet_bounded_analysis_execution`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `boundedAnalysisExecutionApproved = true`
- `boundedAnalysisExecutionExecuted = true`
- `requestedFrameCount = 300`
- `analyzedFrameCount = 300`
- `missingFrameCount = 0`
- `unreadableFrameCount = 0`
- `fullAnalysisReady = false`
- `fullAnalysisExecuted = false`
- `archiveDownloadExecuted = false`
- `video720pMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_bounded_analysis_report_smoke`
- `football_external_soccernet_bounded_analysis_execution_approval`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `boundedAnalysisExecutionApproved = true`
- `boundedAnalysisExecutionExecuted = false`
- `approvedFrameCount = 300`
- `maxApprovedFrameCount = 300`
- `fullAnalysisAllowed = false`
- `fullAnalysisExecuted = false`
- `archiveDownloadExecuted = false`
- `video720pMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_bounded_analysis_execution`
- `football_external_soccernet_video_analysis_dry_run_product_bridge_smoke`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `productBridgeSmokePassed = true`
- `productPayloadFrameCount = 300`
- `missingSampledFrameCount = 0`
- `fullAnalysisReady = false`
- `fullAnalysisExecuted = false`
- `archiveDownloadExecuted = false`
- `video720pMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_bounded_analysis_execution_approval`
- `football_external_soccernet_video_analysis_dry_run`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `analysisExecutionApproved = true`
- `analysisExecutionExecuted = true`
- `fullAnalysisExecuted = false`
- `videoOpenable = true`
- `frameCount = 146893`
- `fps = 25.0`
- `width = 398`
- `height = 224`
- `sampleEveryNFrames = 489`
- `sampledFrameCount = 300`
- `archiveDownloadExecuted = false`
- `video720pMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_video_analysis_dry_run_product_bridge_smoke`
- `football_external_soccernet_video_analysis_dry_run_approval`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `analysisDryRunApproved = true`
- `analysisExecutionApproved = true`
- `analysisExecutionExecuted = false`
- `selectedVideoPath = /root/WorkSpace/fotball-analyst/backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_soccernet_video_member_extract_v1/extracted_video/england_efl/2019-2020/2019-10-01 - Middlesbrough - Preston North End/224p.mp4`
- `maxDryRunFrames = 300`
- `sampleEveryNFrames = 489`
- `estimatedSampledFrameCount = 300`
- `boundedDryRunOnly = true`
- `fullAnalysisAllowed = false`
- `archiveDownloadExecuted = false`
- `video720pMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_video_analysis_dry_run`
- `football_external_soccernet_video_to_analysis_bridge_prep`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `analysisBridgePrepReady = true`
- `analysisExecutionApproved = false`
- `analysisExecutionExecuted = false`
- `videoExists = true`
- `sampledFrameCount = 5`
- `archiveDownloadExecuted = false`
- `video720pMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_video_analysis_dry_run_approval`
- `football_external_soccernet_video_product_path_smoke`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `externalVideoProductPathReady = true`
- `frameCount = 146893`
- `fps = 25.0`
- `width = 398`
- `height = 224`
- `sampledFrameCount = 5`
- `fullAnalysisReady = false`
- `archiveDownloadExecuted = false`
- `video720pMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_video_to_analysis_bridge_prep`
- `football_external_soccernet_video_frame_probe`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `videoFrameProbePassed = true`
- `videoOpenable = true`
- `frameCount = 146893`
- `fps = 25.0`
- `width = 398`
- `height = 224`
- `sampledFrameCount = 5`
- `archiveDownloadExecuted = false`
- `video720pMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_video_product_path_smoke`
- `football_external_soccernet_video_member_extract`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `approvedVideoMemberPath = england_efl/2019-2020/2019-10-01 - Middlesbrough - Preston North End/224p.mp4`
- `extractedVideoFileCount = 1`
- `credentialRuntimeAvailable = true`
- `credentialPersisted = false`
- `videoMemberExtractionExecuted = true`
- `videoMemberDownloadExecuted = true`
- `videoMemberFullDownloadExecuted = true`
- `video720pMemberDownloadExecuted = false`
- `archiveDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_video_frame_probe`
- `football_external_soccernet_video_member_extract_approval`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `videoMemberExtractionApproved = true`
- `approvedVideoMemberPath = england_efl/2019-2020/2019-10-01 - Middlesbrough - Preston North End/224p.mp4`
- `approvedCompressedSizeBytes = 236289867`
- `approvedUncompressedSizeBytes = 237589445`
- `fullArchiveDownloadApproved = false`
- `archiveDownloadExecuted = false`
- `videoMemberExtractionExecuted = false`
- `videoMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_video_member_extract`
- `football_external_soccernet_video_sample_probe`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `sampleProbeCompleted = true`
- `sampleSizeBytes = 50000000`
- `fileSignatureClass = zip_local_file_header`
- `sampleIsEncryptedZipMember = true`
- `sampleIsPlayableVideo = false`
- `videoMemberFullDownloadExecuted = false`
- `archiveDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_video_member_extract_approval`
- `football_external_soccernet_controlled_video_sample_fetch`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `selectedVideoMemberPath = england_efl/2019-2020/2019-10-01 - Middlesbrough - Preston North End/224p.mp4`
- `requestedByteCount = 50000000`
- `sampleBytesFetched = 50000000`
- `videoMemberFullDownloadExecuted = false`
- `fullArchiveDownloadApproved = false`
- `archiveDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_video_sample_probe`
- `football_external_soccernet_video_sample_download_approval`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `videoSampleDownloadApproved = true`
- `selectedVideoMemberPath = england_efl/2019-2020/2019-10-01 - Middlesbrough - Preston North End/224p.mp4`
- `maxApprovedBytes = 50000000`
- `fullArchiveDownloadApproved = false`
- `archiveDownloadExecuted = false`
- `videoMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_controlled_video_sample_fetch`
- `football_external_soccernet_event_report_product_integration`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `productEventReportReady = true`
- `eventCount = 1604`
- `distinctEventTypeCount = 12`
- `fullMatchAnalysisReady = false`
- `archiveDownloadExecuted = false`
- `videoMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_video_sample_download_approval`
- `football_external_soccernet_event_lane_closeout`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `eventOnlyLaneClosed = true`
- `eventCount = 1604`
- `distinctEventTypeCount = 12`
- `fullMatchAnalysisReady = false`
- `fullBenchmarkExecutionReady = false`
- `archiveDownloadExecuted = false`
- `videoMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_event_report_product_integration`
- `football_external_soccernet_event_report_smoke`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `eventReportSmokePassed = true`
- `eventCount = 1604`
- `distinctEventTypeCount = 12`
- `fullMatchAnalysisReady = false`
- `archiveDownloadExecuted = false`
- `videoMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_event_lane_closeout`
- `football_external_soccernet_event_report_contract_prep`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `reportContractReady = true`
- `eventCount = 1604`
- `distinctEventTypeCount = 12`
- `eventRatePerMinute = 16.393666`
- `fullMatchAnalysisReady = false`
- `trainingExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_event_report_smoke`
- `football_external_soccernet_event_benchmark_smoke`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `eventBenchmarkSmokePassed = true`
- `eventCount = 1604`
- `distinctEventTypeCount = 12`
- `eventRatePerMinute = 16.393666`
- `coveredStageIds = [possession_event_semantics]`
- `uncoveredStageIds = [camera_shot_gate, calibration, tracking, ball_localization, tactical_reporting]`
- `fullBenchmarkExecutionReady = false`
- `archiveDownloadExecuted = false`
- `videoMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_event_report_contract_prep`
- `football_external_soccernet_benchmark_adapter_contract_prep`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `eventStreamRowCount = 1604`
- `ballActionEventRowCount = 1604`
- `coveredStageIds = [possession_event_semantics]`
- `uncoveredStageIds = [camera_shot_gate, calibration, tracking, ball_localization, tactical_reporting]`
- `fullBenchmarkExecutionReady = false`
- `eventBenchmarkSmokeReady = true`
- `archiveDownloadExecuted = false`
- `videoMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_event_benchmark_smoke`
- `football_external_soccernet_event_adapter_smoke_test`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `adapterSmokePassed = true`
- `canonicalEventCount = 1604`
- `distinctEventTypeCount = 12`
- `eventIdUnique = true`
- `positionMsMonotonicNonDecreasing = true`
- `archiveDownloadExecuted = false`
- `videoMemberDownloadExecuted = false`
- `datasetDownloadAllowedByThisBatch = false`
- `datasetDownloadExecuted = false`
- `fullOriginalVideoDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_benchmark_adapter_contract_prep`
- `football_external_soccernet_event_adapter_fixture_materialization`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `canonicalEventCount = 1604`
- `distinctEventTypeCount = 12`
- `eventFixtureQualityPassed = true`
- `eventIdUnique = true`
- `archiveDownloadExecuted = false`
- `videoMemberDownloadExecuted = false`
- `datasetDownloadAllowedByThisBatch = false`
- `datasetDownloadExecuted = false`
- `fullOriginalVideoDownloadExecuted = false`
- `videoDownloadAllowed = false`
- `featureDownloadAllowed = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_event_adapter_smoke_test`
- `football_external_soccernet_label_schema_ingestion_probe`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `annotationCount = 1604`
- `distinctLabelCount = 12`
- `requiredAnnotationFieldsPresent = true`
- `positionParseRate = 1.0`
- `gameTimeParseRate = 1.0`
- `adapterReadyForFixtureMaterialization = true`
- `trainingExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_event_adapter_fixture_materialization`
- `football_external_soccernet_zip_label_member_extract`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `downloadedLabelFileCount = 1`
- `annotationCount = 1604`
- `labelJsonParseSucceeded = true`
- `credentialRuntimeAvailable = true`
- `credentialPersisted = false`
- `archiveDownloadExecuted = false`
- `videoMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_label_schema_ingestion_probe`
- `football_external_soccernet_zip_label_member_extract_approval`
- `goalAchieved = true`
- `primaryBlocker = null`
- `labelMemberExtractionApproved = true`
- `approvedLabelMemberCount = 1`
- `compressionMethodSet = [99]`
- `credentialRequired = true`
- `credentialPersisted = false`
- `fullArchiveDownloadApproved = false`
- `videoMemberDownloadAllowed = false`
- `trainingExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_zip_label_member_extract`
- `football_external_soccernet_split_archive_range_index_probe`
- `goalAchieved = true`
- `primaryBlocker = null`
- `zipCentralDirectoryParsed = true`
- `zipEntryCount = 6`
- `labelMemberCount = 1`
- `videoMemberCount = 2`
- `containsOriginalVideoFiles = true`
- `archiveDownloadExecuted = false`
- `videoMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_zip_label_member_extract_approval`
- `football_external_soccernet_split_archive_size_probe`
- `goalAchieved = true`
- `primaryBlocker = null`
- `selectedArchivePath = valid.zip`
- `selectedArchiveSizeBytes = 2042230928`
- `selectedArchiveSizeClass = large_archive`
- `labelsOnlyArchiveCandidateCount = 3`
- `metadataFetchExecuted = true`
- `archiveDownloadExecuted = false`
- `partialArchiveContentDownloadExecuted = false`
- `trainingExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_split_archive_range_index_probe`
- `football_external_soccernet_split_archive_access_review`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `failedFetchRootCause = soccernet_spotting_ball_per_game_labels_json_not_served`
- `packageSupportedArchiveSurfaceReady = true`
- `selectedArchiveTask = spotting-ball-2025`
- `selectedSplit = valid`
- `selectedAccessMode = huggingface_snapshot_allow_pattern`
- `selectedArchiveFileOrPattern = *valid.zip`
- `splitArchiveDownloadApproved = false`
- `labelDownloadExecuted = false`
- `sampleDownloadExecuted = false`
- `datasetDownloadAllowedByThisBatch = false`
- `datasetDownloadExecuted = false`
- `fullOriginalVideoDownloadExecuted = false`
- `videoDownloadAllowed = false`
- `featureDownloadAllowed = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_split_archive_size_probe`
- `football_external_soccernet_label_fetch_contract_repair`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `failedFetchRootCause = soccernet_spotting_ball_per_game_labels_json_not_served`
- `perGameLabelsJsonSupported = false`
- `labelDownloadExecuted = false`
- `sampleDownloadExecuted = false`
- `datasetDownloadAllowedByThisBatch = false`
- `datasetDownloadExecuted = false`
- `fullOriginalVideoDownloadExecuted = false`
- `videoDownloadAllowed = false`
- `featureDownloadAllowed = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_split_archive_access_review`
- `football_external_soccernet_controlled_label_sample_fetch`
- `goalAchieved = false`
- `roadmapAdvanceAllowed = false`
- `primaryBlocker = football_external_soccernet_label_fetch_failed`
- `credentialRuntimeAvailable = true`
- `labelDownloadExecuted = false`
- `downloadedLabelFileCount = 0`
- `fetchFailureCount = 1`
- `datasetDownloadAllowedByThisBatch = false`
- `datasetDownloadExecuted = false`
- `fullOriginalVideoDownloadExecuted = false`
- `videoDownloadAllowed = false`
- `featureDownloadAllowed = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_label_fetch_contract_repair`
- `football_external_soccernet_controlled_label_sample_fetch_approval`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `labelSampleFetchApproved = true`
- `approvedTask = spotting-ball`
- `approvedSplit = valid`
- `approvedGameRefCount = 1`
- `approvedFiles = [Labels.json]`
- `labelDownloadExecuted = false`
- `datasetDownloadAllowedByThisBatch = false`
- `datasetDownloadExecuted = false`
- `fullOriginalVideoDownloadExecuted = false`
- `videoDownloadAllowed = false`
- `featureDownloadAllowed = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_controlled_label_sample_fetch`
- `football_external_soccernet_controlled_label_metadata_probe`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `apiListingProbeReady = true`
- `labelMetadataProbeReady = true`
- `selectedTask = spotting-ball`
- `selectedSplit = valid`
- `selectedGameRefCount = 1`
- `totalBallGameRefs = 9`
- `labelDownloadApprovedByPreviousContract = false`
- `labelDownloadApprovalRequired = true`
- `labelDownloadExecuted = false`
- `sampleDownloadExecuted = false`
- `datasetDownloadAllowedByThisBatch = false`
- `datasetDownloadExecuted = false`
- `fullOriginalVideoDownloadExecuted = false`
- `videoDownloadAllowed = false`
- `featureDownloadAllowed = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_controlled_label_sample_fetch_approval`
- `football_external_soccernet_api_listing_probe`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `apiMetadataProbeReady = true`
- `credentialRuntimeAvailable = true`
- `credentialPersisted = false`
- `passwordRedacted = true`
- `apiListingExecuted = true`
- `listingSource = package_local_index`
- `networkApiCallExecuted = false`
- `listedTaskCount = 5`
- `totalListedGameRefs = 1765`
- `listingErrorCount = 0`
- `apiCallExecuted = false`
- `labelDownloadExecuted = false`
- `datasetDownloadAllowedByThisBatch = false`
- `datasetDownloadExecuted = false`
- `fullOriginalVideoDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_controlled_label_metadata_probe`
- `football_external_soccernet_api_metadata_probe`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `apiApprovalReady = true`
- `apiPackageInstallAttempted = true`
- `apiPackageImportReady = true`
- `apiDownloaderImportReady = true`
- `apiPackageVersion = 0.1.62`
- `credentialRuntimeAvailable = true`
- `credentialPersisted = false`
- `passwordRedacted = true`
- `apiCallExecuted = false`
- `apiListingExecuted = false`
- `datasetDownloadAllowedByThisBatch = false`
- `datasetDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_api_listing_probe`
- `football_external_soccernet_nda_api_access_approval`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `soccernetNdaAccessAvailable = true`
- `controlledApiMetadataProbeReady = true`
- `credentialPersisted = false`
- `passwordRedacted = true`
- `fullOriginalVideoDownloadApproved = false`
- `datasetDownloadAllowedByThisBatch = false`
- `datasetDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_api_metadata_probe`
- `football_external_soccertrack_metadata_adapter_smoke`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `soccertrackMetadataAdapterSmokePassed = true`
- `codeLicenseDetected = MIT`
- `dataLicenseDetected = CC-BY-4.0`
- `metadataSupportsAdapterProbe = true`
- `datasetDownloadExecuted = false`
- `fullDatasetDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccertrack_sample_schema_probe`
- `football_external_safe_source_controlled_sample_fetch`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `selectedSampleResourceId = soccertrack_v2`
- `fetchScope = metadata_only`
- `controlledMetadataFetchExecuted = true`
- `fetchedFileCount = 3`
- `fetchFailureCount = 0`
- `sampleDownloadExecuted = false`
- `datasetDownloadExecuted = false`
- `fullDatasetDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccertrack_metadata_adapter_smoke`
- `football_external_safe_source_sample_download_approval`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `selectedSampleResourceId = soccertrack_v2`
- `officialSourceUrlCorrected = true`
- `correctedOfficialSourceUrl = https://github.com/AtomScott/SoccerTrack-v2`
- `licenseUseClass = controlled_sample_allowed_with_attribution`
- `sampleDownloadApproved = true`
- `sampleDownloadExecuted = false`
- `fullDatasetDownloadApproved = false`
- `datasetDownloadAllowedByThisBatch = false`
- `datasetDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_safe_source_controlled_sample_fetch`
- `football_external_safe_source_sample_ingestion_plan`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `sampleIngestionPlanReady = true`
- `safeSourceResourceCount = 3`
- `safeSourceResourceIds = [soccertrack_v2, skillcorner_open_data, statsbomb_open_data_360]`
- `selectedFirstSampleResourceId = soccertrack_v2`
- `sampleDownloadApprovalRequired = true`
- `sampleDownloadExecuted = false`
- `datasetDownloadAllowedByThisBatch = false`
- `datasetDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_safe_source_sample_download_approval`
- `football_external_safe_adapter_fixture_implementation`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `adapterFixtureImplementationReady = true`
- `adapterImplementationMode = synthetic_fixture_only`
- `fixtureResourceCount = 3`
- `frameStateFixtureCount = 3`
- `gameStateFixtureCount = 3`
- `fixtureRoundTripPassed = true`
- `fullExternalBenchmarkExecutionReady = false`
- `datasetDownloadAllowedByThisBatch = false`
- `datasetDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_safe_source_sample_ingestion_plan`
- `football_external_safe_source_adapter_smoke_test`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `safeSourceAdapterSmokePassed = true`
- `safeSmokeResourceCount = 3`
- `safeSmokeResourceIds = [soccertrack_v2, skillcorner_open_data, statsbomb_open_data_360]`
- `syntheticFixtureRowCount = 3`
- `adapterSchemaCount = 6`
- `auditedSchemaNames = [FrameState, GameState]`
- `schemaSmokePassed = true`
- `safeSmokeCoveredStages = [ball_localization, calibration, possession_event_semantics, tactical_reporting, tracking]`
- `safeSmokeStageCoverageComplete = false`
- `missingSafeSmokeStages = [camera_shot_gate]`
- `fullExternalBenchmarkExecutionReady = false`
- `datasetDownloadAllowedByThisBatch = false`
- `datasetDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_safe_adapter_fixture_implementation`
- `product_video_to_analysis_smoke_v1`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `apiUploadJobSmokePassed = true`
- `apiUploadMatchId = 57feef6fbab84e5998a4e95f6d211df9`
- `existingVideoBundleSmokePassed = true`
- `existingVideoBundleMatchId = 094a9974d01b447b93ec7ba43981f6c8`
- `secondaryConcern = null`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_safe_source_adapter_smoke_test`
- `canonical_match_bundle_export_v1`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `bundleExportReady = true`
- `readyMatchCount = 2`
- `sampleMatchId = 094a9974d01b447b93ec7ba43981f6c8`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = product_video_to_analysis_smoke_v1`
- `v7_2_runtime_registry_product_path_binding`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `localProductPathRegistryBindingPassed = true`
- `runpodAuxiliaryRuntimePayloadPassed = true`
- `trainingExecuted = false`
- `promotionMutationExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = canonical_match_bundle_export_v1`
- `football_external_dataset_access_review`
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
- `v7_2_runtime_default_rollout_closeout`
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
- `v7_2_post_runtime_default_source_robustness_validation`
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
- `v7_2_runtime_default_change_validation`
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
- `v7_2_default_path_inboard_ball_recovery`
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
- `v7_2_default_path_edge_share_reduction`
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
- `v7_2_training_manifest_prep`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `reviewedPositiveSourceCount = 139`
- `positiveCropExampleCount = 414`
- `localHardNegativeCropCount = 180`
- `heldoutHardNegativeCanaryCount = 20`
- `unsafeFullFrameNegativeExportCount = 0`
- `splitLeakageCount = 0`
- `nextRecommendedNextLever = v7_2_export_label_overlay_audit`
- `v7_2_export_label_overlay_audit`
- `goalAchieved = true`
- `exportOverlayAuditPassed = true`
- `positiveLabelFilesWithExactlyOneBall = 414`
- `negativeLabelFilesEmpty = 180`
- `heldoutCanaryLabelFilesEmpty = 20`
- `positiveCropBoundsRepairedCount = 12`
- `positiveLabelRoundTripMaxErrorPx = 0.500392`
- `splitLeakageCount = 0`
- `canaryLeakageCount = 0`
- `nextRecommendedNextLever = v7_2_bounded_retrain`
- `v7_2_bounded_retrain`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `trainingCompleted = true`
- `checkpointContractPassed = true`
- `inferenceUsedTrainedWeights = true`
- `selectedCheckpointForVerdict = best.pt`
- `selectedAuditConf = 0.1`
- `trainerObservedLabelRowCount = 414`
- `boundedTrainPositiveLocalizationHitRate = 0.985507`
- `boundedValPositiveLocalizationHitRate = 0.971014`
- `boundedTrainNegativeFalsePositiveFrameRate = 0.0`
- `boundedValNegativeFalsePositiveFrameRate = 0.0`
- `heldoutCanaryFalsePositiveFrameRate = 0.0`
- `medianTrainPositiveConfidence = 0.83083`
- `medianValPositiveConfidence = 0.810916`
- `topLeftArtifactShare = 0.0`
- `giantBoxShare = 0.0`
- `nextRecommendedNextLever = v7_2_crop_probe_precision_guardrail_audit`
- `v7_2_crop_probe_precision_guardrail_audit`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `trainingAllowed = false`
- `trainingExecuted = false`
- `checkpointContractPassed = true`
- `inferenceUsedTrainedWeights = true`
- `selectedCheckpointForAudit = best.pt`
- `selectedAuditConf = 0.1`
- `boundedTrainPositiveLocalizationHitRate = 0.985507`
- `boundedValPositiveLocalizationHitRate = 0.971014`
- `boundedTrainHardNegativeFalsePositiveFrameRate = 0.0`
- `boundedValHardNegativeFalsePositiveFrameRate = 0.0`
- `heldoutCanaryFalsePositiveFrameRate = 0.0`
- `oldTopLeftArtifactFalsePositiveFrameRate = 0.0`
- `recallGuardrailStrength = strong_pass`
- `topLeftArtifactShare = 0.0`
- `giantBoxShare = 0.0`
- `nextRecommendedNextLever = v7_2_full_pipeline_non_promotion_eval`
- `v7_2_full_pipeline_non_promotion_eval`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `trainingAllowed = false`
- `trainingExecuted = false`
- `checkpointContractPassed = true`
- `inferenceUsedTrainedWeights = true`
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
- `topLeftArtifactShare = 0.0`
- `giantBoxShare = 0.0`
- `nextRecommendedNextLever = football_external_benchmark_harness_prep`
- `football_external_benchmark_harness_prep`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `resourceCount = 5`
- `adapterSchemaCount = 6`
- `stageGateCount = 6`
- `stageCoverageComplete = true`
- `missingRequiredStageCoverage = []`
- `benchmarkHarnessContractReady = true`
- `datasetAccessReviewReady = true`
- `externalBenchmarkExecutionReady = false`
- `datasetDownloadExecuted = false`
- `trainingAllowed = false`
- `trainingExecuted = false`
- `promotionReady = false`
- `candidateReadyForEvaluation = false`
- `runtimeDefaultMutationAllowed = false`
- `attemptPlanFamilies = [external_benchmark_contract_prep, benchmark_adapter_contract_repair, benchmark_harness_blocker_summary]`
- `nextRecommendedNextLever = football_external_dataset_access_review`
- `v7_2_promotion_readiness_validation`
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
- `positiveCropExampleCount = 414`
- `boundedValPositiveLocalizationHitRate = 0.971014`
- `sourceFrameLocalizationHitRate = 1.0`
- `observedBallAcceptanceRate = 1.0`
- `oldTopLeftArtifactFalsePositiveFrameRate = 0.0`
- `sampledFrameDetectionRate = 0.0`
- `nextRecommendedNextLever = promoted_v7_2_source_robustness_validation`
- `promoted_v7_2_source_robustness_validation`
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
- `v7_2_source_robustness_default_blocker_analysis`
- `goalAchieved = false`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = v7_2_default_path_performance_blocker`
- `controlledPromotionValid = true`
- `realDefaultPerformanceFailureProven = true`
- `sourceRobustnessRouteMismatchDetected = false`
- `sourceRobustnessRecommendedNextLever = promoted_v7_2_source_robustness_validation`
- `runtimeDefaultMutationReady = false`
- `runtimeDefaultMutationExecuted = false`
- `runtimeDefaultMutationBlockers = [failing_source_not_viable]`
- `nextRecommendedNextLever = v7_2_default_path_edge_share_reduction`
- `v7_2_source_robustness_route_contract_fix`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `routeContractFixed = true`
- `sourceRobustnessRouteMismatchDetected = false`
- `sourceRobustnessRecommendedNextLever = promoted_v7_2_source_robustness_validation`
- `defaultBlockerAfterRouteFix = v7_2_default_path_performance_blocker`
- `realDefaultPerformanceFailureProven = true`
- `runtimeDefaultMutationReady = false`
- `runtimeDefaultMutationExecuted = false`
- `runtimeDefaultMutationAllowed = false`
- `nextRecommendedNextLever = v7_2_default_path_edge_share_reduction`

Current hard constraints:

- controlled promotion is allowed and now points at v7.2
- runtime defaults now point at the validated v7.2 inboard recovery profile
- post-default source-robustness validation passed from the active runtime registry
- runtime-default rollout closeout passed and marked the old blocker as archival only
- the old `failing_source_not_viable` blocker is dead in active post-mutation truth; the legacy suite summary still carries it only as historical pre-mutation context
- the next active work is safe-source external adapter smoke testing, not dataset download, promotion-readiness, detector retrain, or inboard mining
- stale source-robustness routing is fixed; real v7.2 default-path performance failure is now proven in generated truth
- external dataset access/license review remains useful later, but it is no longer the immediate v7.2 unlock
- no auto-positive model labels

## Purpose

This is the current valid roadmap for moving `fotball-analyst` toward trustworthy football-video analysis, usable review workflows, and reproducible truth surfaces.

It is grounded in generated artifacts, not intent or archived plans.

## Verified Starting Point

Current verified state:

- canonical proof floor: `174 / 137 / true / 0.586`
- multi-source suite: `baseline_not_robust`
- active config: `source_robustness_baseline_current`
- best qualifying fallback: `source_robustness_shadow_edge_run_keep_every_2_min10`
- overall outcome: `source_robustness_partial`
- active-lane next lever: `football_external_safe_source_adapter_smoke_test`
- active post-mutation blocker status: `failing_source_not_viable` is cleared

Current falsified lanes:

- edge-share thinning as the primary answer
- touchline probe replacement
- touchline acquisition upgrade
- combined detector and candidate-source reopen
- touchline candidate-admission reopen v3
- bounded detector breadth on the off-the-shelf detector set
- `touchline_detector_candidate_v1` evaluation

## Roadmap Rules

The roadmap must optimize for:

1. product truth over motion
2. one coherent truth surface across artifacts, memory bank, and handoff
3. explicit English batch closeouts before any roadmap advance
4. one strict checklist file per blocker cycle
5. no drift back into already falsified families

Hard gate:

- if a generated batch closeout says the goal was not achieved, the roadmap does not advance

## Current Phases

### Phase 1A — Curation Foundation

Status:

- complete

Delivered:

- deterministic representative match selection
- canonical training-prep artifact root
- initial YOLO export
- issue seeding and split manifests

### Phase 1B — Review Densification

Status:

- failing-source gate complete
- control review follow-up optional for now

Current live outputs:

- failing windows: `2`
- control windows: `1`
- `pendingFailingReviewCount = 0`
- `pendingControlReviewCount = 13`
- `readyForRetraining = true`

### Phase 2 — Detector Retraining

Status:

- complete

Historical artifacts for this completed phase:

- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v2/`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v3/`

Important caveat:

- those phases succeeded because they produced evaluation-ready artifacts, not because they already proved product lift

### Phase 3 — Corrective Training, Bounded Evaluation, And Promotion Validation

Status:

- active
- v4 was reclassified as blocked by the training-quality gate
- Phase 3A validation-gate remediation completed successfully
- the runtime-aligned proposal-signal corrective batch completed successfully
- the bounded v6 evaluation completed successfully and produced a promotable result
- the promotion-validation lane completed successfully for controlled/internal use
- the post-promotion promoted-v6 robustness validation completed honestly and did not clear the remaining blocker
- the first accepted-signal retention fix attempt, `admission_widening`, completed honestly and did not move the generated blocker
- the second accepted-signal retention fix attempt, `baseline_guided_rescue`, completed honestly and still did not move the generated blocker
- the third accepted-signal retention fix attempt, `continuity_bridge_recovery`, completed honestly and still did not move the generated blocker
- the fourth accepted-signal retention fix attempt, `acceptance_support_gating`, completed honestly and exhausted that batch
- the failing-source review refresh completed successfully and classified the dominant missing accepted-signal blocker as `proposal_signal_present_but_not_selected`
- source manifest refresh attempt 1 completed successfully and produced a gold-truth bootstrap target
- gold-truth bootstrap attempt 2 completed successfully and selected `proposal_selection_admission_fix` as the next corrective family
- proposal-selection admission fix exhausted three materially distinct approaches and did not move generated retention truth
- proposal crop geometry fixed part of the upstream proposal surface but left `selectedFrames = 0`
- proposal selection follow-through exhausted three attempts and selected `manual_review_required`
- manual review follow-through package generated review assets and paused the roadmap on `manual_review_pending`
- manual review resolution initially confirmed all 78 items were pending
- manual review UI unblock added a local-only server and no-build canvas UI, then an AI-assisted visual review pass resolved the overlay with 4 accepted seeds and 74 rejected seeds
- manual review resolution rerun selected `reviewed_followthrough_selection_fix`
- reviewed follow-through selection fix completed saved-artifact diagnosis and selected `gold_truth_seed_refuted_refresh`
- gold-truth seed refuted refresh completed saved-artifact truth refresh and selected `manual_review_expansion`
- manual review expansion generated a 17-frame review package around the four positive anchors and paused on `manual_review_pending`
- manual review expansion resolution validated all 17 reviewed-positive frames and selected `reviewed_positive_micro_validation`
- manual review expansion resolution lineage was corrected from the stale package shortcut to generated truth: `lineageCompleteCount = 4`
- reviewed-positive micro-validation completed saved-artifact diagnosis and selected `proof_diagnostic_instrumentation_refresh`
- proof diagnostic instrumentation refresh completed proof-only instrumentation/readiness and selected `proof_runtime_frame_diagnostics`
- proof runtime frame diagnostics completed a fresh local promoted-v6 failing-source proof and selected `reviewed_positive_proposal_generation_fix`
- reviewed-positive proposal generation fix completed a RunPod proof with reviewed bbox anchors as proposal windows only; generated truth now says 17 anchor windows were used, 1 reviewed-positive frame produced proposal evidence, 0 reviewed-positive frames were selected, and the next corrective family is `reviewed_positive_crop_reinference_audit`
- reviewed-positive crop reinference audit completed local crop-level inference around the 17 reviewed boxes; generated truth says 11 of the 16 zero-detect frames can be rescued by crop geometry/scale, and the next corrective family is `reviewed_positive_crop_geometry_scale_fix`
- reviewed-positive crop geometry scale fix completed attempt 2 with an audit-priority proof profile; generated truth now says 5 reviewed-positive frames have proposal/collapse evidence, 0 are selected/accepted, and the next corrective family is `reviewed_positive_selection_followthrough_fix`
- reviewed-positive selection follow-through fix completed attempt 1 as saved-artifact gate diagnosis; generated truth classifies all 5 reviewed-positive collapsed frames as `reviewed_positive_segment_selection_zero` and selects `reviewed_positive_selected_segment_profile`
- reviewed-positive selection follow-through fix completed attempt 2 with a non-default selected-segment proof profile; generated truth still says `reviewedPositiveSelectedFrameCount = 0`, `reviewedPositiveAcceptedFrameCount = 0`, `goalAchieved = false`, and selects `reviewed_positive_selection_blocker_summary`
- reviewed-positive selection follow-through fix completed attempt 3 as blocker summary; generated truth says the five reviewed-positive collapsed frames lack row-level selected-segment gate trace and selects `proof_selection_gate_trace_refresh`
- proof selection gate trace refresh completed attempt 1; generated truth now proves all five reviewed-positive collapsed frames are rejected by the selected-segment edge-share gate and selects `reviewed_positive_edge_share_gate_override`
- reviewed-positive edge-share gate override completed attempt 1 with a non-default reviewed-positive-only profile; generated truth now says the five reviewed-positive collapsed frames become selected (`reviewedPositiveSelectedFrameCount = 5`) but not accepted (`reviewedPositiveAcceptedFrameCount = 0`), and selects `reviewed_positive_acceptance_fix`
- reviewed-positive acceptance fix completed attempt 1 as saved-artifact diagnosis; generated truth says all five selected reviewed-positive frames lack acceptance-gate trace (`reviewed_positive_acceptance_artifact_gap`) and selects `proof_acceptance_gate_trace_refresh`
- proof acceptance gate trace refresh completed attempt 1; fresh RunPod-backed proof now emits row-level `acceptanceGateTrace`, generated truth classifies all five selected reviewed-positive frames as `reviewed_positive_selected_rejected_by_viability`, and selects `reviewed_positive_acceptance_profile`
- reviewed-positive acceptance profile completed attempt 1; generated proof accepted the first five reviewed-positive frames and improved retention to `acceptedRetentionRatio = 0.099`, but 12 reviewed-positive frames still lacked proposal evidence
- reviewed-positive residual proposal generation fix completed attempts 1-3; attempt 3 with `source_robustness_shadow_promoted_v6_reviewed_positive_residual_proposal_generation_fix_v2` lifted proof truth to all 17 reviewed-positive frames raw/collapsed and 10 reviewed-positive selected/accepted frames, while promotion remains blocked by `accepted_signal_retention_collapse`
- residual segment selection microfix completed attempt 2; the non-default residual segment profile selected/accepted frames `305,310,315,320`, and `accepted_retention_guardrail_audit_v1` then proved the active blocker is the global retention guardrail gap (`bestAcceptedRetentionRatio = 0.109`, `bestControlledRetentionRatio = 0.112`, guardrails `0.60 / 0.60`, `acceptedFramesShortOfGuardrail = 50`)
- global accepted gap audit completed attempt 1; it proved promoted accepted frames do not overlap baseline accepted frame IDs (`overlappingAcceptedFrameCount = 0`, `missingBaselineAcceptedFrameCount = 101`), with `94` missing frames having no promoted proposal evidence and `7` reachable collapsed-not-selected frames (`255,260,265,270,275,280,285`), so the next queued batch is `global_reachable_acceptance_probe`
- global reachable acceptance probe completed attempt 2; the non-default profile selected/accepted frames `255,260,265,270,275,280,285`, improving promoted baseline retention to `0.139 / 0.173`, but the promotion guardrail remains far away (`acceptedFramesShortOfGuardrail = 47`, `controlledFramesShortOfGuardrail = 42`) and refreshed global gap truth selects `baseline_denominator_review_refresh`
- baseline denominator review refresh completed attempts 1-3; `68 / 101` denominator frames are refuted contaminants, but filtering them only yields effective accepted retention `0.212`, so generated truth selects `touchline_detector_candidate_v7_training_data_refresh` with `17` reviewed positives, `74` refuted negatives, `23` unreviewed denominator frames, and `26` hard-mining candidates
- touchline detector candidate v7 training-data refresh attempt 1 completed; generated truth wrote a concrete v7 dataset manifest with `17` reviewed positives, `74` refuted negatives, `23` pending denominator review frames, and `26` hard-mining candidates, but the quality gate says `trainingReady = false` and selects `manual_review_denominator_expansion`
- manual review denominator expansion attempt 1 completed; generated truth wrote `23` denominator review items, extracted `23` review frames, kept all lineage complete, and paused the roadmap on `manual_review_pending` before `manual_review_denominator_resolution`
- manual review denominator resolution attempt 1 completed; generated truth resolved all 23 items (`19` reviewed positives, `4` reviewed negatives), lifted total reviewed positives to `36`, and selected `touchline_detector_candidate_v7_training_prep`
- touchline detector candidate v7 training prep attempt 1 completed; generated truth wrote `touchline_detector_candidate_v7_training_prep_v1` with `30` clean positives, `78` negatives, `0` pending review frames, `0` missing positive boxes, `6` quarantined refuted-positive overlaps, `trainingPrepReady = true`, and selected `touchline_detector_candidate_v7_training`
- touchline detector candidate v7 training attempt 1 completed on RunPod; generated truth wrote `touchline_detector_candidate_v7` weights, `trainingCompleted = true`, `weightsReady = true`, `trainingQualityGatePassed = true`, `readyForDetectorEvaluation = true`, and selected `touchline_detector_candidate_v7_evaluation`
- touchline detector candidate v7 evaluation attempt 1 completed on RunPod; generated truth says v7 is not promotable (`screenWinningDetectorLabel = yolov10n.pt_baseline_full_detector`, `candidateBaselineProductBeatsPlateau = false`, `acceptedBallFrames = 0`, `controlledPossessionFrames = 0`, `evaluationPrimaryBlocker = candidate_baseline_did_not_beat_plateau`) and selects `touchline_detector_candidate_v7_evaluation_failure_analysis`
- touchline detector candidate v7 evaluation failure analysis attempt 1 completed; generated truth says the v7 candidate produced zero auxiliary probe signal (`candidateRawProbeObservedBallFrames = 0`, `candidateProbeObservedBallFrames = 0`), zero proposal/raw candidate frames, and zero accepted frames, so it selects `v7_probe_assist_integration_audit`
- v7 probe-assist integration audit attempt 1 completed; generated truth says `bestWeightsPathExists = true`, the proof received and invoked the v7 auxiliary model (`probeObservedPassSeconds = 34.779`), but `rawProbeObservedBallFrames = 0`, so it selects `v7_probe_threshold_preprocessing_fix`
- v7 probe threshold/preprocessing audit attempt 1 completed; generated truth says offline v7 inference detects all `30 / 30` exported positives at low confidence with class `0`, so it selects `v7_probe_threshold_contract_fix`
- runtime defaults remain frozen because broader robustness blockers still exist

Completed evaluation-cycle checklist:

- `docs/superpowers/plans/2026-04-23-touchline-detector-candidate-evaluation-v5.md`

Latest promotion checklist:

- `docs/superpowers/plans/2026-04-23-touchline-detector-candidate-promotion-v6.md`

Active post-promotion robustness checklist:

- `docs/superpowers/plans/2026-04-23-promoted-v6-failing-source-robustness-validation.md`

#### Phase 3A — V4/V5 Training-Quality Gate Remediation

Status:

- complete

Blocked v4 truth:

- `trainingCandidateName = touchline_detector_candidate_v4`
- `validationImageCount = 3`
- `validationPositiveLabelImageCount = 0`
- `validationEmptyLabelImageCount = 3`
- `validationInformative = false`
- `trainingQualityGatePassed = false`
- `trainingQualityGatePrimaryBlocker = validation_split_has_no_positive_labels`

Completed remediation truth:

- `validationGateRemediationBatchName = touchline_validation_gate_remediation_v1`
- `trainingCandidateName = touchline_detector_candidate_v5`
- `blockedCandidateName = touchline_detector_candidate_v4`
- `validationImageCount = 33`
- `validationPositiveLabelImageCount = 27`
- `validationEmptyLabelImageCount = 6`
- `validationInformative = true`
- `sourceAwareSplitLeakageDetected = false`

#### Phase 3B — Runtime-Aligned Proposal-Signal Fix

Status:

- complete

Completed v6 proposal-signal fix truth:

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

#### Phase 3C — Bounded Detector Evaluation

Status:

- complete for the active candidate lane

Latest completed bounded evaluation truth:

- `evaluationBatchName = touchline_detector_candidate_evaluation_v6`
- `trainingCandidateName = touchline_detector_candidate_v6`
- `screenCompleted = true`
- `screenWinningDetectorLabel = yolov10n.pt_baseline_full_detector`
- `candidateBaselineProofRan = true`
- `candidateBaselineProductBeatsPlateau = true`
- `baselineControlProofRan = true`
- `candidateCompoundThinProofRan = true`
- `candidateBeatsSameBatchBaselineControl = true`
- `readyForPromotion = true`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `nextRecommendedNextLever = promote_touchline_detector_candidate`

Concrete read:

- the bounded v6 batch achieved its goal under the standing failing-source contract
- the baseline still won the raw screen cell, but the always-required v6 baseline proof beat the product plateau
- the same-batch baseline control and compound-thin proof both ran because v6 earned them

#### Phase 3D — Promotion Validation

Status:

- complete

Latest completed promotion-validation truth:

- `promotionBatchName = touchline_detector_candidate_promotion_validation_v1`
- `trainingCandidateName = touchline_detector_candidate_v6`
- `promotionValidated = true`
- `promotedForControlledRuns = true`
- `runtimeDefaultChanged = false`
- `runtimeDefaultChangeAllowed = false`
- `runtimeDefaultChangeBlockers = [failing_source_not_viable]`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `nextRecommendedNextLever = promote_touchline_detector_candidate`

Plain-English read:

- `touchline_detector_candidate_v6` is now promoted for controlled/internal use
- runtime defaults remain frozen
- the broader suite still truthfully reads `baseline_not_robust`
- the promotion lever stays active because the runtime-default blocker is still visible

#### Phase 3E — Promoted Failing-Source Robustness Validation

Status:

- complete
- goal not achieved

Latest completed promoted-robustness truth:

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

Plain-English read:

- the controlled promoted arms still do not clear `failing_source_not_viable`
- edge share improved materially, but accepted and controlled retention still fail the gate
- runtime defaults remain frozen
- the promotion lane stays active, but runtime-default validation is not next

#### Phase 3F — Accepted-Signal Retention Fix

Status:

- complete
- attempts 1, 2, 3, and 4 failed honestly; the batch is exhausted

Latest generated attempt truth:

- `activeBatchName = touchline_detector_candidate_v6_accepted_signal_retention_fix_v1`
- `attemptNumber = 4`
- `approachFamily = acceptance_support_gating`
- `primaryRetentionBlockerClass = accepted_signal_retention_collapse`
- `acceptedRetentionRatio = 0.069`
- `controlledRetentionRatio = 0.102`
- `selectedClusterStepImplicated = false`
- `runtimeDefaultChanged = false`
- `itemStatus = exhausted`
- `nextQueueItem = promoted_v6_failing_source_review_refresh_v1`
- `reviewRefreshAttemptNumber = 1`
- `reviewRefreshApproachFamily = review_taxonomy_refresh`
- `reviewRefreshResult = succeeded`
- `dominantBlockerClass = proposal_signal_present_but_not_selected`
- `nextFixFamily = proposal_selection_evidence_refresh`
- `missingAcceptedFrameCount = 101`
- `windowCount = 11`
- `nextQueueItem = promoted_v6_source_manifest_and_gold_truth_refresh_v1`

Plain-English read:

- acceptance-support gating did not recover accepted signal on the failing source
- review-taxonomy refresh found that the missing accepted signal is dominated by promoted proposal signal that is present but not selected
- the promoted robustness gate is still blocked by accepted and controlled retention
- runtime-default validation remains blocked

#### Phase 3G — Source Manifest And Gold-Truth Refresh

Status:

- complete
- attempt 1, `manifest_scope_refresh`, succeeded
- attempt 2, `gold_truth_bootstrap`, succeeded

Latest generated attempt truth:

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

Plain-English read:

- the manifest refresh did not mutate the frozen source manifest
- it wrote additive proposal-selection windows and a top-5 bootstrap plan from generated evidence
- the bootstrap wrote a direct saved-artifact seed surface for the top 5 windows
- the proposal-selection admission fix used that seed surface and exhausted all 3 approaches without moving the generated blocker

#### Phase 3H — Proposal-Selection Admission Fix

Status:

- exhausted
- attempt 1, `truth_seed_guided_selection`, failed
- attempt 2, `window_local_proposal_kind_rescue`, failed
- attempt 3, `segment_level_seed_continuity`, failed

Latest generated attempt truth:

- `activeBatchName = proposal_selection_admission_fix`
- `primaryRetentionBlockerClass = accepted_signal_retention_collapse`
- `acceptedRetentionRatio = 0.069`
- `controlledRetentionRatio = 0.102`
- `winningPassedPromotionGate = false`
- `runtimeDefaultChanged = false`
- `sourceRobustnessPromotionBlockers = [failing_source_not_viable]`
- `nextCorrectiveFamily = support_viability_truth_fix`

Plain-English read:

- admitting proposal candidates from the refreshed truth seed did not raise accepted retention
- the next batch should inspect support/viability truth rather than adding another proposal-selection profile

#### Phase 3I — Support/Viability Truth Fix

Status:

- complete
- attempt 1, `support_viability_truth_analysis`, succeeded

Latest generated attempt truth:

- `activeBatchName = proposal_crop_geometry_fix`
- `attemptBudget = 3`
- `attempts = [truth_seed_crop_geometry, expanded_seed_window_geometry, seed_window_selection_followthrough]`
- `goalAchieved = false`
- `batchStatus = exhausted`
- `previousCandidateProposalGenerationBlockerClass = no_proposal_attempt_for_seed_frame`
- `dominantBlockerClass = proposal_selection_followthrough_gap`
- `proposalCandidateFrames = 110`
- `proposalWindowCount = 440`
- `proposalRawDetectedFrames = 93`
- `proposalCollapsedFrames = 93`
- `selectedFrames = 0`
- `nextCorrectiveFamily = proposal_selection_followthrough_fix`
- `classifiedSeedFrameCount = 78`
- `primaryRetentionBlockerClass = accepted_signal_retention_collapse`
- `acceptedRetentionRatio = 0.069`
- `controlledRetentionRatio = 0.102`

Plain-English read:

- proposal crop geometry attempts fixed the earlier missing-attempt/raw-detection surface enough to create 110 proposal frames and 93 raw detections
- the generated candidates still produce `selectedFrames = 0`
- the next corrective family is `proposal_selection_followthrough_fix`

#### Phase 3J — Proposal Selection Follow-Through Fix

Status:

- exhausted
- attempt 1, `selection_followthrough_diagnosis`, succeeded as diagnosis
- attempt 2, `selection_segment_viability_fix`, failed in promoted validation
- attempt 3, `profile_ranking_or_manual_review_fallback`, wrote the exhausted blocker summary

Latest generated attempt truth:

- `activeBatchName = proposal_selection_followthrough_fix`
- `attemptBudget = 3`
- `batchStatus = exhausted`
- `dominantBlockerClass = candidate_rows_collapsed_but_segment_selection_zero`
- `proposalCandidateFrames = 110`
- `proposalRawDetectedFrames = 93`
- `proposalCollapsedFrames = 93`
- `selectedFrames = 0`
- `acceptedRetentionRatio = 0.069`
- `controlledRetentionRatio = 0.102`
- `winningPassedPromotionGate = false`
- `runtimeDefaultChanged = false`
- `nextCorrectiveFamily = manual_review_required`

Plain-English read:

- the pipeline now creates and collapses proposal candidates for the seeded failing-source windows
- relaxing selected-frame segment viability under a non-default promoted profile still produced zero selected frames
- generated artifacts do not justify a selected-profile ranking fix because there are no selected proposal frames to rerank
- the next honest step is manual/review-overlay inspection of the 78 seeded follow-through items, not runtime-default validation

#### Phase 3K — Manual Review Follow-Through Package

Status:

- review package ready
- roadmap paused on manual review

Latest generated attempt truth:

- `activeBatchName = promoted_v6_manual_review_followthrough_v1`
- `attemptNumber = 1`
- `approachFamily = review_package_generation`
- `batchStatus = manual_review_pending`
- `goalAchieved = true`
- `reviewItemCount = 78`
- `pendingReviewCount = 78`
- `lineageCompleteCount = 78`
- `missingSeedBBoxCount = 0`
- `imageExtractionStatus = images_extracted`
- `extractedImageCount = 78`
- `runtimeDefaultChanged = false`
- `sourceManifestMutated = false`
- `nextCorrectiveFamily = manual_review_pending`
- `roadmapAdvanceAllowed = false`

Plain-English read:

- the next detector-side move is blocked on human/reviewer decisions
- all 78 seeded follow-through frames now have repo-native pending review items and extracted frame images
- runtime-default validation remains blocked

#### Phase 3L — Manual Review Resolution Gate

Status:

- resolved

Latest generated attempt truth:

- `activeBatchName = promoted_v6_manual_review_resolution_v1`
- `attemptNumber = 1`
- `approachFamily = review_decision_validation`
- `batchStatus = review_resolved`
- `goalAchieved = true`
- `reviewItemCount = 78`
- `pendingReviewCount = 0`
- `invalidDecisionCount = 0`
- `lineageCompleteCount = 78`
- `acceptedSeedCount = 4`
- `rejectedSeedCount = 74`
- `nextCorrectiveFamily = reviewed_followthrough_selection_fix`
- `roadmapAdvanceAllowed = true`

Plain-English read:

- the overlay is structurally valid
- the active overlay is no longer pending
- the reviewed truth is sparse: only 4 of 78 seeds survived visual review as positives

#### Phase 3M — Manual Review UI Unblock

Status:

- complete
- roadmap advanced to reviewed follow-through selection diagnosis

Latest verified implementation truth:

- `activeBatchName = promoted_v6_manual_review_ui_unblock_v1`
- `attemptNumber = 1`
- `approachFamily = local_review_ui`
- local review server: `backend/scripts/serve_promoted_v6_manual_review_ui.py`
- no-build UI: `backend/review_ui/promoted_v6_manual_review/index.html`
- initial dry-run summary: `reviewItemCount = 78`, `pendingReviewCount = 78`, `reviewedPositiveCount = 0`, `reviewedNegativeCount = 0`
- AI-assisted visual review result: `pendingReviewCount = 0`, `acceptedSeedCount = 4`, `rejectedSeedCount = 74`
- focused pytest: `22 passed`
- runtime defaults unchanged
- frozen source manifest unchanged

Plain-English read:

- the bottleneck is no longer lack of a review surface
- the bottleneck is now using the sparse reviewed-positive truth to choose a detector-side follow-through fix
- do not treat the rejected bootstrap seeds as positive training or acceptance evidence

#### Phase 3N — Reviewed Follow-Through Selection Fix

Status:

- complete

Latest generated attempt truth:

- `reviewedPositiveSeedCount = 4`
- `reviewedNegativeSeedCount = 74`
- `dominantBlockerClass = reviewed_positive_evidence_too_sparse`
- `nextCorrectiveFamily = gold_truth_seed_refuted_refresh`
- `weakEvidenceReasons = [reviewed_positive_seed_count_below_detector_fix_floor, bootstrap_seed_surface_mostly_refuted_by_review]`
- `primaryRetentionBlockerClass = accepted_signal_retention_collapse`
- `acceptedRetentionRatio = 0.069`
- `controlledRetentionRatio = 0.102`
- `sourceRobustnessPromotionBlockers = [failing_source_not_viable]`

Plain-English read:

- the next batch should diagnose why the 4 visually accepted reviewed seed frames do not become selected/accepted follow-through signal
- the batch did say so: 4 positives are too sparse for a detector-side follow-through profile

#### Phase 3O — Gold-Truth Seed Refuted Refresh

Status:

- complete

Latest generated attempt truth:

- `batchStatus = succeeded`
- `goalAchieved = true`
- `dominantBlockerClass = reviewed_positive_truth_too_sparse`
- `reviewedPositiveSeedCount = 4`
- `rejectedSeedCount = 74`
- `reviewedPositiveFrames = [260, 290, 295, 300]`
- `nextCorrectiveFamily = manual_review_expansion`
- `primaryRetentionBlockerClass = accepted_signal_retention_collapse`
- `acceptedRetentionRatio = 0.069`
- `controlledRetentionRatio = 0.102`
- `sourceRobustnessPromotionBlockers = [failing_source_not_viable]`

Plain-English read:

- the refuted 78-frame bootstrap premise has been replaced with a smaller reviewed-positive/refutation truth surface
- only frames `260`, `290`, `295`, and `300` are positive truth seeds
- the 74 rejected seeds are negative/refutation evidence only

#### Phase 3P — Manual Review Expansion

Status:

- complete

Latest generated attempt truth:

- `batchStatus = manual_review_pending`
- `goalAchieved = true`
- `successfulApproach = A_reviewed_positive_window_expansion`
- `reviewItemCount = 17`
- `acceptedSeedCount = 4`
- `pendingReviewCount = 13`
- `lineageCompleteCount = 4`
- `imageExtractionStatus = images_extracted`
- `extractedImageCount = 17`
- `nextCorrectiveFamily = manual_review_pending`
- `primaryRetentionBlockerClass = accepted_signal_retention_collapse`
- `acceptedRetentionRatio = 0.069`
- `controlledRetentionRatio = 0.102`

Plain-English read:

- the repo now has a review-ready expanded truth surface around frames 260, 290, 295, and 300
- 13 expansion frames still need review before another detector-side move is justified

#### Phase 3Q — Manual Review Expansion Resolution

Status:

- complete

Latest generated attempt truth:

- `batchStatus = review_resolved`
- `goalAchieved = true`
- `reviewItemCount = 17`
- `acceptedSeedCount = 4`
- `adjustedBBoxCount = 13`
- `pendingReviewCount = 0`
- `invalidDecisionCount = 0`
- `reviewedPositiveCount = 17`
- `reviewedNegativeCount = 0`
- `nextCorrectiveFamily = reviewed_positive_micro_validation`
- `primaryRetentionBlockerClass = accepted_signal_retention_collapse`
- `acceptedRetentionRatio = 0.069`
- `controlledRetentionRatio = 0.102`

Plain-English read:

- the expanded review gate is resolved and there are now 17 positive reviewed frames for a tiny validation pass

#### Phase 3R — Reviewed Positive Micro Validation

Status:

- complete

Precondition truth:

- `manual_review_expansion_resolution_v1` selected `reviewed_positive_micro_validation`
- generated expansion-resolution truth says `reviewedPositiveCount = 17`
- runtime defaults remain frozen

Plain-English read:

- the batch validated the 17 reviewed-positive frames against existing promoted-v6 proof artifacts, but the proof bundle does not contain frame-level proposal/selection fields for those reviewed positives
- generated result: `dominantBlockerClass = reviewed_positive_artifact_coverage_gap`, `dominantBlockerFrameCount = 17`, `perFrameProofCoverageAvailable = false`, `weakEvidenceReasons = [reviewed_positive_frame_level_proposal_selection_fields_partial]`, `nextCorrectiveFamily = proof_diagnostic_instrumentation_refresh`

#### Phase 3S — Proof Diagnostic Instrumentation Refresh

Status:

- complete

Precondition truth:

- `reviewed_positive_micro_validation_v1` selected `proof_diagnostic_instrumentation_refresh`
- generated missing field: `reviewed_positive_frame_level_proposal_selection_fields_partial`
- runtime defaults remain frozen

Plain-English read:

- the batch added proof-only frame-level diagnostics to the recovery-profile matrix surface and generated a bridge audit
- the current saved proof still has `coveredReviewedFrameCount = 0`, so it cannot yet choose a detector-side family
- generated result: `dominantBlockerClass = reviewed_positive_frame_diagnostics_missing`, `dominantBlockerFrameCount = 17`, `currentProofCanSelectDetectorFamily = false`, `nextCorrectiveFamily = proof_runtime_frame_diagnostics`

#### Phase 3T — Proof Runtime Frame Diagnostics

Status:

- complete

Precondition truth:

- `proof_diagnostic_instrumentation_refresh_v1` selected `proof_runtime_frame_diagnostics`
- generated proof-diagnostic truth says `coveredReviewedFrameCount = 0`
- runtime defaults remain frozen

Plain-English read:

- the batch reran promoted-v6 failing-source proof locally at `backend/storage/matches/094a9974d01b447b93ec7ba43981f6c8`
- the fresh proof populated recovery-profile frame diagnostics; `proposal_windows_075` selected 4 frames, but none of the 17 reviewed-positive frames had matching promoted proposal evidence
- generated result: `dominantBlockerClass = reviewed_positive_no_promoted_proposal`, `dominantBlockerFrameCount = 17`, `classifiedReviewedFrameCount = 17`, `nextCorrectiveFamily = reviewed_positive_proposal_generation_fix`

#### Phase 3U — Reviewed Positive Proposal Generation Fix

Status:

- next batch

Precondition truth:

- `proof_runtime_frame_diagnostics_v1` selected `reviewed_positive_proposal_generation_fix`
- generated runtime diagnostic truth says all 17 reviewed-positive frames are classified as `reviewed_positive_no_promoted_proposal`
- runtime defaults remain frozen

Plain-English read:

- the next batch should make promoted-v6 generate proposal windows for the 17 reviewed-positive frames, using reviewed boxes as anchors only and not as direct accepted balls

## Immediate Next Move

- The repo should not rerun v6 evaluation and should not flip runtime defaults.

- resolve `v7_1_positive_candidate_mining_expansion_v1/corrected_label_overlay.json` in `v7_1_positive_diversity_manual_review_expansion_v2`
- start from `v7_1_positive_candidate_mining_expansion_v1`, which converted the low-yield review into a correction-ready package: `previousReviewedPositiveSourceCount = 34`, `previousReviewCandidateCount = 149`, `previousAcceptedPositiveCount = 4`, `previousDeferredUnclearCount = 102`, `salvageCorrectionQueueCount = 102`, `newMinedCandidateCount = 240`, `totalCandidateReviewCount = 342`, `knownCropValidationMissesCarriedForward = 9`, `knownFullPipelineMissesCarriedForward = 2`, `distinctCandidateSplitGroupCount = 4`, `trainingExecuted = false`, `promotionReady = false`, `candidateReadyForEvaluation = false`, `runtimeDefaultMutationAllowed = false`, `primaryBlocker = null`, and `nextRecommendedNextLever = v7_1_positive_diversity_manual_review_expansion_v2`
- use `v7_1_positive_diversity_manual_review_resolution_v2` as the strict gate after decisions are filled; its current generated truth is intentionally pending with `reviewCandidateCount = 342`, `pendingReviewItemCount = 342`, `previousReviewedPositiveSourceCount = 34`, `primaryBlocker = v7_1_positive_diversity_manual_review_still_pending`, and `nextRecommendedNextLever = v7_1_positive_diversity_manual_review_resolution_v2`
- keep the previous low-yield review as the reason for the correction package: `pendingReviewItemCount = 0`, `newReviewedPositiveSourceCount = 4`, `totalReviewedPositiveSourceCount = 34`, `reviewDeferredUnclearCount = 102`, `reviewedNotBallCount = 36`, `duplicateOrNearDuplicateCount = 7`, and `primaryBlocker = v7_1_positive_diversity_review_yield_insufficient`
- keep `v7_1_positive_diversity_refresh_v1` as the candidate-queue prep truth: `positiveReviewQueueCandidateCount = 89`, `knownCropValidationMissesIncluded = 9`, `knownFullPipelineMissesIncluded = 2`, and `primaryBlocker = v7_1_positive_diversity_insufficient_reviewed_count`
- keep `v7_1_full_pipeline_non_promotion_eval_v1` as the pipeline safety proof: `candidateCropCoverageRate = 1.0`, `cropDetectorConditionalLocalizationRate = 0.933333`, `sourceFrameLocalizationHitRate = 0.933333`, `observedBallAcceptanceRate = 0.933333`, `projectionAuditPassed = true`, zero canary/top-left/sample flood regressions, and `secondaryConcern = v7_1_validation_positive_recall_limited`
- keep `v7_1_export_label_overlay_audit_v1` as the trusted physical export surface: `90` positive crop labels, `180` empty hard-negative labels, `20` empty held-out canary labels, `positiveLabelRoundTripMaxErrorPx = 0.5`, `splitLeakageCount = 0`, and `canaryLeakageCount = 0`
- carry forward `positiveLocalizationHitRate = 0.0`, `topLeftBoxShare = 1.0`, and `hardNegativeCandidateCount = 304` as v7.1 data-quality guardrails
- preserve refuted examples as negative-only evidence; resolve positive diversity manual review next, but still do not promote or mutate runtime defaults
- keep `promote_touchline_detector_candidate` as the active-lane lever until the remaining blocker is cleared
- keep `suiteVerdict = baseline_not_robust` and `sourceRobustnessPromotionBlockers = [failing_source_not_viable]` visible
- keep the active todo source pinned to `docs/superpowers/plans/2026-04-23-promoted-v6-failing-source-robustness-validation.md`
- use the checklist’s new mega-queue rule:
  - `3` distinct approaches for the current big-task family unless the active checklist says otherwise
  - if exhausted, advance to the next queued batch in this same lane
- latest attempt truth: `support_viability_admission_fix` attempts 1, 2, and 3 (`support_evidence_lift`, `source_space_support_neighborhood`, `viability_neutral_seed_window`) failed with `acceptedRetentionRatio = 0.069`, `controlledRetentionRatio = 0.102`, `primaryRetentionBlockerClass = accepted_signal_retention_collapse`, and `winningPassedPromotionGate = false`
- `support_viability_admission_fix` is exhausted; the selected next corrective family is `candidate_proposal_generation_fix`
- `candidate_proposal_generation_fix` attempt 1 succeeded with `dominantBlockerClass = no_proposal_attempt_for_seed_frame`, `dominantGapFrameCount = 46`, `probe_model_no_raw_detection = 32`, and selected `proposal_crop_geometry_fix`
- `proposal_crop_geometry_fix` exhausted 3 attempts; it improved proposal-window/raw-detection evidence but still left `selectedFrames = 0` and selected `proposal_selection_followthrough_fix`
- `proposal_selection_followthrough_fix` exhausted 3 attempts; it left `selectedFrames = 0` and selected `manual_review_required`
- `promoted_v6_manual_review_followthrough_v1` attempt 1 generated the manual review package and paused on `manual_review_pending`
- `promoted_v6_manual_review_ui_unblock_v1` added a reviewer UI and AI-assisted visual review resolved the labels with 4 positives and 74 rejected seeds
- `gold_truth_seed_refuted_refresh_v1` completed and selected `manual_review_expansion`
- `manual_review_expansion_v1` completed and paused on `manual_review_pending` with 13 pending expansion frames
- `manual_review_expansion_resolution_v1` completed and selected `reviewed_positive_micro_validation`
- `reviewed_positive_micro_validation_v1` completed and selected `proof_diagnostic_instrumentation_refresh`
- `proof_diagnostic_instrumentation_refresh_v1` completed and selected `proof_runtime_frame_diagnostics`
- `proof_runtime_frame_diagnostics_v1` completed and selected `reviewed_positive_proposal_generation_fix`

## Accepted Research Sequence

Useful suggestions that are now folded into the roadmap:

1. keep the milestone order strict: trustworthy extraction first, then team/owner attribution, then possession/event semantics, then analysis outputs
2. keep stage-wise detector evaluation and stronger truth gates as part of the extraction lane
3. treat pitch-homography hardening as conditional, not automatic
4. treat failure taxonomy, source-manifest expansion, and a small gold set as the next extraction-quality lane after the current promotion blocker is explicitly handled
5. keep later semantics in the order `team assignment -> owner assignment -> possession chains -> event layer`


Verification passed for this cycle: focused pytest `35 passed in 5.40s`, py_compile passed, JSON sanity passed, disk remained `52G` free, and RunPod pods were `[]`.


Verification passed for this cycle: focused pytest `35 passed in 5.38s`, py_compile passed, JSON sanity passed, disk remained `52G` free, and RunPod pods were `[]`.


Verification passed for this continuation: focused pytest `35 passed in 5.39s`, py_compile passed, JSON sanity passed, disk remained `52G` free, and RunPod pods were `[]`.
