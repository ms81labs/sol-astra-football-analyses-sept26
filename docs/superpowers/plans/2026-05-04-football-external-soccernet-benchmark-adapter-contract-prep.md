# Football External SoccerNet Benchmark Adapter Contract Prep

## Batch Contract

- Batch: `football_external_soccernet_benchmark_adapter_contract_prep`
- Attempt budget: `3`
- Source truth:
  - `football_external_soccernet_event_adapter_smoke_test_v1/soccernet_event_adapter_smoke_summary.json`
  - `football_external_soccernet_event_adapter_smoke_test_v1/benchmark_adapter_prep_contract.json`
  - `football_external_soccernet_event_adapter_fixture_materialization_v1/canonical_event_timeline.json`
  - `football_external_benchmark_harness_prep_v1/dataset_adapter_contract.json`
  - `football_external_benchmark_harness_prep_v1/stage_gate_contract.json`

## Result

- `goalAchieved = true`
- `primaryBlocker = null`
- `eventStreamRowCount = 1604`
- `ballActionEventRowCount = 1604`
- `coveredStageIds = [possession_event_semantics]`
- `uncoveredStageIds = [camera_shot_gate, calibration, tracking, ball_localization, tactical_reporting]`
- `fullBenchmarkExecutionReady = false`
- `eventBenchmarkSmokeReady = true`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_event_benchmark_smoke`

## Next Batch

`football_external_soccernet_event_benchmark_smoke`

Goal:

- Run an event-only benchmark smoke over the SoccerNet event fixture.
- Validate event distribution, timing coverage, stage coverage, and report-friendly summary metrics.
- Do not train, promote, fetch video, or mutate runtime defaults.
