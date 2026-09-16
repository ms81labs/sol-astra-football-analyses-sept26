# Football External SoccerNet Video Sample Download Approval

## Batch

- Batch: `football_external_soccernet_video_sample_download_approval`
- Attempt budget: `3`
- Attempt 1: `controlled_video_sample_download_approval`
- Source batch: `football_external_soccernet_event_report_product_integration`

## Generated Truth

- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `videoSampleDownloadApproved = true`
- `selectedVideoMemberPath = england_efl/2019-2020/2019-10-01 - Middlesbrough - Preston North End/224p.mp4`
- `selectedCompressedSizeBytes = 236289867`
- `selectedUncompressedSizeBytes = 237589445`
- `maxApprovedBytes = 50000000`
- `fullArchiveDownloadApproved = false`
- `archiveDownloadExecuted = false`
- `videoMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionReady = false`
- `candidateReadyForEvaluation = false`
- `runtimeDefaultMutationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_controlled_video_sample_fetch`

## Artifacts

- `video_sample_download_approval_summary.json`
- `video_sample_download_approval_contract.json`
- `video_member_selection_audit.json`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`
- `batch_outcome_analysis.json/md`

## Interpretation

The next video lane is approved only for a controlled sample fetch from the
smallest available video member. This does not approve full archive download,
full member download beyond the byte cap, training, promotion, candidate
evaluation readiness, or runtime-default mutation.

## Next

`football_external_soccernet_controlled_video_sample_fetch`
