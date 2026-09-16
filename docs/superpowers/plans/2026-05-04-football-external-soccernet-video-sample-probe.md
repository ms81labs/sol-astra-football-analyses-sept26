# Football External SoccerNet Video Sample Probe

## Batch

- Batch: `football_external_soccernet_video_sample_probe`
- Attempt budget: `3`
- Attempt 1: `controlled_video_sample_signature_probe`
- Source batch: `football_external_soccernet_controlled_video_sample_fetch`

## Generated Truth

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
- `promotionReady = false`
- `candidateReadyForEvaluation = false`
- `runtimeDefaultMutationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_video_member_extract_approval`

## Artifacts

- `video_sample_probe_summary.json`
- `video_sample_probe_audit.json`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`
- `batch_outcome_analysis.json/md`

## Interpretation

The bounded sample is not directly playable video. It is an encrypted ZIP local
file header/member sample for the selected `224p.mp4`, so frame probing requires
a separate scoped member extraction approval. This still does not approve the
full archive, training, promotion, candidate evaluation, or runtime-default
mutation.

## Next

`football_external_soccernet_video_member_extract_approval`
