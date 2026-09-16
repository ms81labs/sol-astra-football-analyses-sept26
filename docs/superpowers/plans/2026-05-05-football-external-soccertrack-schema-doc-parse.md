# Football External SoccerTrack Schema Doc Parse

## Batch

- Active batch: `football_external_soccertrack_schema_doc_parse`
- Attempt budget: `3`
- Attempt 1 family: `soccertrack_schema_doc_parse`

## Goal

Parse the fetched SoccerTrack schema documentation into a bounded adapter contract for later sample ingestion planning. Do not download datasets or samples.

## Attempt Plan

1. `soccertrack_schema_doc_parse`
   - Parse fetched docs only.
   - Extract field-level GSR and BAS contracts.
   - Extract MOT task-level contract without overclaiming a dedicated format schema.
   - Write a sample adapter mapping plan.

2. `soccertrack_schema_doc_parse_repair`
   - Repair parser patterns while keeping the fetch/download scope unchanged.

3. `soccertrack_schema_doc_parse_blocker_summary`
   - Write blocker truth if docs cannot support a sample ingestion contract.

## Completed

- [x] Added schema-doc parse tests.
- [x] Added schema-doc parse script.
- [x] Parsed GSR, BAS, and MOT docs from the fetched schema-doc artifact set.
- [x] Wrote parsed schema contract, task parse audits, adapter mapping plan, decision matrix, and failsafe plan.
- [x] Preserved no dataset/sample download, no training, no promotion, and no runtime mutation.

## Result

- `goalAchieved = true`
- `primaryBlocker = null`
- `schemaDocParseReady = true`
- `parsedTaskIds = [gsr, bas, mot]`
- `fieldLevelParsedTaskIds = [gsr, bas]`
- `gsrParsedFieldCount = 10`
- `basParsedFieldCount = 9`
- `motParsedFieldCount = 6`
- `datasetDownloadExecuted = false`
- `sampleDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationAllowed = false`
- `nextRecommendedNextLever = football_external_soccertrack_sample_ingestion_contract_prep`
