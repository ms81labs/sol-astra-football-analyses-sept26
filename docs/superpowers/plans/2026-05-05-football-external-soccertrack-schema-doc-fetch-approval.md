# Football External SoccerTrack Schema Doc Fetch Approval

## Batch

- Active batch: `football_external_soccertrack_schema_doc_fetch_approval`
- Attempt budget: `3`
- Attempt 1 family: `soccertrack_schema_doc_fetch_approval`

## Goal

Approve controlled SoccerTrack schema documentation fetch from the schema-probe plan. This batch approves docs only and does not execute the fetch.

## Attempt Plan

1. `soccertrack_schema_doc_fetch_approval`
   - Validate prior schema probe.
   - Approve only safe `docs/` paths.
   - Reject unsafe archive/video/relative paths.

2. `soccertrack_schema_doc_access_contract_repair`
   - Repair schema-doc access metadata from saved probe artifacts only.

3. `soccertrack_schema_doc_approval_blocker_summary`
   - Write blocker truth and stop before schema-doc fetch if approval is unsafe.

## Completed

- [x] Added schema-doc approval tests.
- [x] Added schema-doc approval script.
- [x] Generated docs-only fetch approval contract.
- [x] Preserved no dataset/sample download, no training, no promotion, and no runtime mutation.

## Result

- `goalAchieved = true`
- `primaryBlocker = null`
- `schemaDocFetchApproved = true`
- `schemaDocApprovedPathCount = 5`
- `schemaDocFetchExecuted = false`
- `datasetDownloadExecuted = false`
- `sampleDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationAllowed = false`
- `nextRecommendedNextLever = football_external_soccertrack_schema_doc_fetch`
