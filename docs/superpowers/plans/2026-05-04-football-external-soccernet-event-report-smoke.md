# Football External SoccerNet Event Report Smoke

## Batch Contract

- Batch: `football_external_soccernet_event_report_smoke`
- Attempt budget: `3`
- Source truth:
  - `football_external_soccernet_event_report_contract_prep_v1/soccernet_event_report_contract_prep_summary.json`
  - `football_external_soccernet_event_report_contract_prep_v1/soccernet_event_report_summary.json`
  - `football_external_soccernet_event_report_contract_prep_v1/event_report_smoke_contract.json`

## Result

- `goalAchieved = true`
- `primaryBlocker = null`
- `eventReportSmokePassed = true`
- `eventCount = 1604`
- `distinctEventTypeCount = 12`
- `fullMatchAnalysisReady = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_event_lane_closeout`

## Next Batch

`football_external_soccernet_event_lane_closeout`

Goal:

- Close out the SoccerNet event-only external data lane.
- Summarize what is now proven:
  - NDA/API access works.
  - Split archive metadata was inspected safely.
  - Label-member-only range extraction works.
  - Event schema, adapter, benchmark smoke, and report smoke pass.
- Summarize what remains unproven:
  - video ingestion
  - camera-shot gate
  - calibration
  - tracking
  - ball localization
  - full tactical reporting
