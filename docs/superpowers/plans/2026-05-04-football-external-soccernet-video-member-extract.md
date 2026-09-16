# Football External SoccerNet Video Member Extract

## Batch

- Batch: `football_external_soccernet_video_member_extract`
- Attempt budget: `3`
- Attempt 1: `scoped_encrypted_video_member_extract`
- Source batch: `football_external_soccernet_video_member_extract_approval`

## Generated Truth

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
- `fullArchiveDownloadApproved = false`
- `trainingExecuted = false`
- `promotionReady = false`
- `candidateReadyForEvaluation = false`
- `runtimeDefaultMutationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_video_frame_probe`

## Artifacts

- `video_member_extract_summary.json`
- `credential_runtime_audit.json`
- `dependency_audit.json`
- `video_member_range_fetch_audit.json`
- `extracted_video_member_inventory.json`
- `extracted_video/.../224p.mp4`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`
- `batch_outcome_analysis.json/md`

## Interpretation

The approved encrypted `224p.mp4` member was extracted as a playable MP4-looking
file. The batch did not download the full archive or the 720p member and did not
train, promote, evaluate a candidate, or mutate runtime defaults.

## Next

`football_external_soccernet_video_frame_probe`
