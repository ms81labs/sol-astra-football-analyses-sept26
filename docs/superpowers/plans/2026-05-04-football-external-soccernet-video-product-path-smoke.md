# Football External SoccerNet Video Product Path Smoke

## Batch

- Batch: `football_external_soccernet_video_product_path_smoke`
- Attempt budget: `3`
- Attempt 1: `soccernet_video_product_path_smoke`
- Source batch: `football_external_soccernet_video_frame_probe`

## Generated Truth

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
- `promotionReady = false`
- `candidateReadyForEvaluation = false`
- `runtimeDefaultMutationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_video_to_analysis_bridge_prep`

## Artifacts

- `video_product_path_smoke_summary.json`
- `external_video_product_bundle.json`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`
- `batch_outcome_analysis.json/md`

## Interpretation

The controlled SoccerNet 224p video can now be surfaced through a product-facing
external video bundle with sampled-frame evidence. This is still not a full
analysis result, not training truth, not promotion truth, and not candidate
evaluation readiness.

## Next

`football_external_soccernet_video_to_analysis_bridge_prep`
