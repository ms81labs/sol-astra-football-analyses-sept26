# Football External SoccerNet Analysis Product UI Route Implementation

## Batch

- Active batch: `football_external_soccernet_analysis_product_ui_route_implementation`
- Attempt budget: `3`
- Attempt 1 family: `soccernet_analysis_product_ui_route_smoke`

## Goal

Expose the saved SoccerNet full-analysis product UI binding through live product routes without changing detector evaluation, training, promotion, or runtime defaults.

## Attempt Plan

1. `soccernet_analysis_product_ui_route_smoke`
   - Serve `analysis_product_ui_view_model.json` from `/api/external/soccernet/full-analysis`.
   - Serve `analysis_product_ui_render_smoke.html` from `/external/soccernet/full-analysis`.
   - Verify both routes through the real FastAPI app.

2. `soccernet_analysis_product_ui_route_contract_repair`
   - If valid binding artifacts exist but the route smoke fails, repair only artifact lookup or route contract wiring.
   - Do not alter source analysis truth or readiness flags.

3. `soccernet_analysis_product_ui_route_blocker_summary`
   - If route binding still fails, write blocker truth and select exactly one next family.

## Completed

- [x] Added route tests.
- [x] Added live backend API route.
- [x] Added live backend HTML route.
- [x] Added route-implementation batch script.
- [x] Added route-implementation batch tests.
- [x] Generated route-implementation artifacts.
- [x] Preserved non-evaluation, non-training, non-promotion, and non-runtime-mutation flags.

## Result

- `goalAchieved = true`
- `primaryBlocker = null`
- `productUiRouteReady = true`
- `reportedFrameCount = 146893`
- `segmentCount = 196`
- `candidateReadyForEvaluation = false`
- `trainingExecuted = false`
- `promotionReady = false`
- `runtimeDefaultMutationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_analysis_product_lane_closeout`
