# Football External SoccerNet Video Analysis Dry Run Approval

## Batch

- Active batch: `football_external_soccernet_video_analysis_dry_run_approval`
- Attempt budget: `3`
- Attempt 1 family: `soccernet_video_analysis_dry_run_approval`

## Goal

Approve a tightly bounded analysis dry run on the extracted SoccerNet `224p.mp4` member without executing analysis in this batch.

## Failsafes

1. `soccernet_video_analysis_dry_run_approval`
   - Use the generated bridge-prep artifacts.
   - Approve only a bounded next-batch dry run.
   - Keep analysis execution, training, promotion, candidate readiness, and runtime mutation unexecuted.
2. `soccernet_video_analysis_dry_run_scope_repair`
   - If the bridge exists but the scope is incomplete, repair only selected-video, frame-limit, and allowed-stage fields.
   - Do not run analysis.
3. `soccernet_video_analysis_dry_run_approval_blocker_summary`
   - If approval cannot be made safe, write blocker truth and route back to bridge prep or scope repair.

## Generated Truth

- `goalAchieved = true`
- `primaryBlocker = null`
- `analysisDryRunApproved = true`
- `analysisExecutionApproved = true`
- `analysisExecutionExecuted = false`
- `maxDryRunFrames = 300`
- `estimatedSampledFrameCount = 300`
- `archiveDownloadExecuted = false`
- `video720pMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `candidateEvaluationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_video_analysis_dry_run`

## Artifacts

- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_soccernet_video_analysis_dry_run_approval_v1/video_analysis_dry_run_approval_summary.json`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_soccernet_video_analysis_dry_run_approval_v1/video_analysis_dry_run_contract.json`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_soccernet_video_analysis_dry_run_approval_v1/dry_run_scope_audit.json`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_soccernet_video_analysis_dry_run_approval_v1/decision_matrix.json`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_soccernet_video_analysis_dry_run_approval_v1/failsafe_attempt_plan.json`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_soccernet_video_analysis_dry_run_approval_v1/batch_outcome_analysis.json`

## Next

Run `football_external_soccernet_video_analysis_dry_run` using the approved 300-frame bounded scope. Do not run full analysis, training, promotion, candidate evaluation readiness, or runtime-default mutation.
