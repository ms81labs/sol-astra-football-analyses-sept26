# Football External SoccerTrack Sample Fixture Materialization Approval

## Batch

- Active batch: `football_external_soccertrack_sample_fixture_materialization_approval`
- Attempt budget: `3`
- Attempt 1 family: `soccertrack_sample_fixture_materialization_approval`

## Goal

Approve only a bounded SoccerTrack fixture/materialization sample scope. Do not execute the fetch in this batch.

## Attempt Plan

1. `soccertrack_sample_fixture_materialization_approval`
   - Approve a one-match maximum SoccerTrack sample fixture scope.
   - Keep full dataset download, training, promotion, candidate evaluation, and runtime mutation closed.
   - Route to controlled sample fetch.

2. `soccertrack_sample_fixture_approval_contract_repair`
   - Repair missing approval contract fields from generated truth.

3. `soccertrack_sample_fixture_approval_blocker_summary`
   - Write blocker truth if approval cannot stay bounded.

## Completed

- [x] Added approval tests.
- [x] Added approval script.
- [x] Wrote bounded materialization approval contract.
- [x] Wrote approved sample scope and guardrail audit.
- [x] Preserved no sample/dataset download, no training, no promotion, and no runtime mutation.

## Result

- `goalAchieved = true`
- `primaryBlocker = null`
- `sampleFixtureMaterializationApproved = true`
- `sampleDownloadApproved = true`
- `sampleDownloadExecuted = false`
- `datasetDownloadApproved = false`
- `datasetDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationAllowed = false`
- `nextRecommendedNextLever = football_external_soccertrack_controlled_sample_fetch`
