# Football External SoccerNet Full Analysis Product Integration

## Unattended Loop Contract

- Work the first unchecked task in this checklist.
- Do not ask for approval; make reasonable assumptions from generated artifacts.
- Trust generated artifacts before roadmap prose.
- Keep training, promotion, candidate evaluation readiness, and runtime-default mutation blocked.

## Next Corrective Sub-Batch — football_external_soccernet_full_analysis_product_integration

- [x] Read `football_external_soccernet_full_analysis_lane_closeout_v1`.
- [x] Add a product-facing full-analysis integration batch script.
- [x] Add focused tests for pass, closeout-missing, and three adaptive attempts.
- [x] Write product payload, UI copy, contract, decision matrix, failsafe attempts, and batch outcome artifacts.
- [x] Execute the batch against real generated truth.
- [ ] Run focused verification and pod hygiene.

## Attempt Flow

1. `soccernet_full_analysis_product_payload`
   - Build product payload from saved full-analysis report/closeout truth.
   - Preserve limitations and non-readiness flags.
2. `soccernet_full_analysis_product_contract_repair`
   - Repair UI/readiness contract fields from saved artifacts only.
   - Do not alter analysis truth.
3. `soccernet_full_analysis_product_blocker_summary`
   - Select exactly one next family if integration is unsafe.
   - Stop before API smoke.

## Success Gate

- `productFullAnalysisReady = true`
- `reportedFrameCount = 146893`
- `segmentCount = 196`
- `candidateReadyForEvaluation = false`
- `trainingExecuted = false`
- `promotionReady = false`
- `runtimeDefaultMutationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_analysis_product_api_smoke`
