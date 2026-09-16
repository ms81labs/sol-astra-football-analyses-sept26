# Football External SoccerNet Video Analysis Dry Run Product Bridge Smoke

## Batch

- Active batch: `football_external_soccernet_video_analysis_dry_run_product_bridge_smoke`
- Attempt budget: `3`
- Attempt 1 family: `soccernet_dry_run_product_bridge_smoke`

## Goal

Prove the bounded SoccerNet dry-run artifact manifest can be consumed as a product-facing payload. Do not run full analysis, training, promotion, candidate evaluation readiness, or runtime-default mutation.

## Failsafes

1. `soccernet_dry_run_product_bridge_smoke`
   - Load the dry-run manifest.
   - Verify every referenced sampled frame exists.
   - Write the product-facing dry-run payload with `fullAnalysisReady = false`.
2. `soccernet_dry_run_product_bridge_manifest_repair`
   - Repair only sampled-frame path or bridge-payload fields from dry-run truth.
3. `soccernet_dry_run_product_bridge_blocker_summary`
   - Select exactly one next family and stop if bridge smoke is unsafe.

## Generated Truth

- `goalAchieved = true`
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

## Artifacts

- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_soccernet_video_analysis_dry_run_product_bridge_smoke_v1/dry_run_product_bridge_smoke_summary.json`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_soccernet_video_analysis_dry_run_product_bridge_smoke_v1/sampled_frame_existence_audit.json`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_soccernet_video_analysis_dry_run_product_bridge_smoke_v1/dry_run_product_bridge_payload.json`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_soccernet_video_analysis_dry_run_product_bridge_smoke_v1/decision_matrix.json`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_soccernet_video_analysis_dry_run_product_bridge_smoke_v1/failsafe_attempt_plan.json`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_soccernet_video_analysis_dry_run_product_bridge_smoke_v1/batch_outcome_analysis.json`

## Next

Run `football_external_soccernet_bounded_analysis_execution_approval` before any more analysis. Full analysis remains unapproved.
