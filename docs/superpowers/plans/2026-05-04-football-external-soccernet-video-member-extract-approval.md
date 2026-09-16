# Football External SoccerNet Video Member Extract Approval

## Batch

- Batch: `football_external_soccernet_video_member_extract_approval`
- Attempt budget: `3`
- Attempt 1: `scoped_video_member_extract_approval`
- Source batch: `football_external_soccernet_video_sample_probe`

## Generated Truth

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
- `promotionReady = false`
- `candidateReadyForEvaluation = false`
- `runtimeDefaultMutationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_video_member_extract`

## Artifacts

- `video_member_extract_approval_summary.json`
- `video_member_extract_approval_contract.json`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`
- `batch_outcome_analysis.json/md`

## Interpretation

The lane now approves extraction of exactly one encrypted SoccerNet video member:
the selected `224p.mp4`. Extraction still requires runtime-only credential
handling and must not persist the credential. This does not approve full archive
download, training, promotion, candidate evaluation, or runtime-default mutation.

## Next

`football_external_soccernet_video_member_extract`
