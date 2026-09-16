# Football External SoccerNet Event Adapter Smoke Test

## Batch Contract

- Batch: `football_external_soccernet_event_adapter_smoke_test`
- Attempt budget: `3`
- Source truth:
  - `football_external_soccernet_event_adapter_fixture_materialization_v1/soccernet_event_fixture_materialization_summary.json`
  - `football_external_soccernet_event_adapter_fixture_materialization_v1/soccernet_event_fixture_manifest.json`
  - `football_external_soccernet_event_adapter_fixture_materialization_v1/canonical_event_timeline.json`

## Goal

Load the canonical SoccerNet event timeline through a benchmark-adapter smoke contract and prove the fixture is structurally usable before benchmark adapter prep.

## Guardrails

- No full archive download.
- No video member download.
- No training.
- No promotion.
- No candidate evaluation readiness.
- No runtime-default mutation.

## Failsafe Attempts

1. `soccernet_event_adapter_smoke`
   - Validate required fields, event IDs, position ordering, and taxonomy counts.
2. `soccernet_event_adapter_contract_repair`
   - Repair fixture mapping from saved truth only if contract fails.
3. `soccernet_event_adapter_smoke_blocker_summary`
   - Write blocker truth and route to one corrective family.

## Result

- `goalAchieved = true`
- `primaryBlocker = null`
- `adapterSmokePassed = true`
- `canonicalEventCount = 1604`
- `distinctEventTypeCount = 12`
- `eventIdUnique = true`
- `positionMsMonotonicNonDecreasing = true`
- `nextRecommendedNextLever = football_external_soccernet_benchmark_adapter_contract_prep`
