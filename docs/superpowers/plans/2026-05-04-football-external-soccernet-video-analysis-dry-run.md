# Football External SoccerNet Video Analysis Dry Run

## Batch

- Active batch: `football_external_soccernet_video_analysis_dry_run`
- Attempt budget: `3`
- Attempt 1 family: `soccernet_video_bounded_frame_dry_run`

## Goal

Execute only the approved bounded dry run on the extracted SoccerNet `224p.mp4` member by sampling the approved 300 frames. Do not run full analysis, training, promotion, candidate evaluation readiness, or runtime-default mutation.

## Failsafes

1. `soccernet_video_bounded_frame_dry_run`
   - Open the approved video path.
   - Sample only the approved bounded frame count.
   - Write dry-run artifacts and stop.
2. `soccernet_video_dry_run_sampling_repair`
   - Repair only stride, max-frame, or selected-video linkage from approval truth.
   - Do not broaden the scope beyond the approval contract.
3. `soccernet_video_dry_run_blocker_summary`
   - Select exactly one next family if bounded sampling is unsafe.

## Generated Truth

- `goalAchieved = true`
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

## Artifacts

- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_soccernet_video_analysis_dry_run_v1/video_analysis_dry_run_summary.json`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_soccernet_video_analysis_dry_run_v1/bounded_frame_sample_audit.json`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_soccernet_video_analysis_dry_run_v1/dry_run_artifact_manifest.json`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_soccernet_video_analysis_dry_run_v1/sampled_frames/`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_soccernet_video_analysis_dry_run_v1/decision_matrix.json`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_soccernet_video_analysis_dry_run_v1/failsafe_attempt_plan.json`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_soccernet_video_analysis_dry_run_v1/batch_outcome_analysis.json`

## Next

Run `football_external_soccernet_video_analysis_dry_run_product_bridge_smoke` to prove the bounded dry-run artifact manifest can be consumed by a product-facing bridge. Full analysis remains unapproved.
