# Football External SoccerNet Event Benchmark Smoke

## Batch Contract

- Batch: `football_external_soccernet_event_benchmark_smoke`
- Attempt budget: `3`
- Source truth:
  - `football_external_soccernet_benchmark_adapter_contract_prep_v1/soccernet_benchmark_adapter_contract_prep_summary.json`
  - `football_external_soccernet_benchmark_adapter_contract_prep_v1/soccernet_event_stream_fixture.json`
  - `football_external_soccernet_benchmark_adapter_contract_prep_v1/soccernet_stage_coverage_audit.json`

## Result

- `goalAchieved = true`
- `primaryBlocker = null`
- `eventBenchmarkSmokePassed = true`
- `eventCount = 1604`
- `distinctEventTypeCount = 12`
- `eventRatePerMinute = 16.393666`
- `coveredStageIds = [possession_event_semantics]`
- `uncoveredStageIds = [camera_shot_gate, calibration, tracking, ball_localization, tactical_reporting]`
- `fullBenchmarkExecutionReady = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_event_report_contract_prep`

## Next Batch

`football_external_soccernet_event_report_contract_prep`

Goal:

- Turn SoccerNet event-only benchmark smoke metrics into report-facing event summaries.
- Keep non-event stages explicitly uncovered.
- Do not train, promote, fetch video, or mutate runtime defaults.
