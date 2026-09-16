# Football External SoccerNet Video Frame Probe

## Batch

- Batch: `football_external_soccernet_video_frame_probe`
- Attempt budget: `3`
- Attempt 1: `soccernet_extracted_video_frame_probe`
- Source batch: `football_external_soccernet_video_member_extract`

## Generated Truth

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
- `promotionReady = false`
- `candidateReadyForEvaluation = false`
- `runtimeDefaultMutationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_video_product_path_smoke`

## Artifacts

- `video_frame_probe_summary.json`
- `video_frame_probe_audit.json`
- `sampled_frames/*.jpg`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`
- `batch_outcome_analysis.json/md`

## Interpretation

The scoped SoccerNet `224p.mp4` member opens locally and can produce sampled
frames. This proves a controlled original-video sample path without downloading
the full archive or 720p member and without training, promotion, candidate
evaluation, or runtime-default mutation.

## Next

`football_external_soccernet_video_product_path_smoke`
