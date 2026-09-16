# Football External SoccerTrack Schema Doc Fetch

## Batch

- Active batch: `football_external_soccertrack_schema_doc_fetch`
- Attempt budget: `3`
- Attempt 1 family: `soccertrack_schema_doc_fetch`

## Goal

Fetch only the approved SoccerTrack schema documentation files and write provenance/hashes for schema parsing. Do not download datasets or samples.

## Attempt Plan

1. `soccertrack_schema_doc_fetch`
   - Fetch only approved docs.
   - Hash every fetched file.
   - Write content inventory for schema parsing.

2. `soccertrack_schema_doc_fetch_repair`
   - Repair stale doc URLs while preserving docs-only scope.

3. `soccertrack_schema_doc_fetch_blocker_summary`
   - Write blocker truth if docs cannot be fetched.

## Completed

- [x] Added docs-fetch tests.
- [x] Added docs-fetch script.
- [x] Fetched five approved documentation files.
- [x] Wrote manifest, provenance audit, and content inventory.
- [x] Preserved no dataset/sample download, no training, no promotion, and no runtime mutation.

## Result

- `goalAchieved = true`
- `primaryBlocker = null`
- `schemaDocFetchExecuted = true`
- `fetchedSchemaDocCount = 5`
- `fetchFailureCount = 0`
- `datasetDownloadExecuted = false`
- `sampleDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationAllowed = false`
- `nextRecommendedNextLever = football_external_soccertrack_schema_doc_parse`
