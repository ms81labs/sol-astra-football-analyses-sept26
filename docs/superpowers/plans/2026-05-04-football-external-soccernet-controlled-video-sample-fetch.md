# Football External SoccerNet Controlled Video Sample Fetch

## Batch

- Batch: `football_external_soccernet_controlled_video_sample_fetch`
- Attempt budget: `3`
- Attempt 1: `controlled_video_member_byte_sample_fetch`
- Source batch: `football_external_soccernet_video_sample_download_approval`

## Generated Truth

- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `primaryBlocker = null`
- `selectedVideoMemberPath = england_efl/2019-2020/2019-10-01 - Middlesbrough - Preston North End/224p.mp4`
- `requestedByteCount = 50000000`
- `sampleBytesFetched = 50000000`
- `sampleSha256 = b97472f103b0f9e7f355034e2ebb1c8af89c0037530a39aedb03c75614cd7c80`
- `videoSampleFetchExecuted = true`
- `videoMemberDownloadExecuted = true`
- `videoMemberFullDownloadExecuted = false`
- `fullArchiveDownloadApproved = false`
- `archiveDownloadExecuted = false`
- `trainingExecuted = false`
- `promotionReady = false`
- `candidateReadyForEvaluation = false`
- `runtimeDefaultMutationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_video_sample_probe`

## Artifacts

- `controlled_video_sample_fetch_summary.json`
- `controlled_video_sample_fetch_audit.json`
- `video_member_sample_bytes.bin`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`
- `batch_outcome_analysis.json/md`

## Interpretation

The batch fetched only the approved 50 MB byte sample from the selected ZIP video
member range. It did not fetch the full video member or full archive and did not
train, promote, evaluate a candidate, or mutate runtime defaults.

## Next

`football_external_soccernet_video_sample_probe`
