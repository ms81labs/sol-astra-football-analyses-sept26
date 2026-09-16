# Football External SoccerTrack Sample Ingestion Contract Prep

## Batch

- Active batch: `football_external_soccertrack_sample_ingestion_contract_prep`
- Attempt budget: `3`
- Attempt 1 family: `soccertrack_sample_ingestion_contract_prep`

## Goal

Prepare a SoccerTrack-specific sample ingestion and fixture materialization contract from parsed docs. Do not download samples or datasets.

## Attempt Plan

1. `soccertrack_sample_ingestion_contract_prep`
   - Build a fixture materialization plan for GSR, BAS, and MOT.
   - Audit schema-to-adapter mappings.
   - Require explicit approval before materialization or sample download.

2. `soccertrack_sample_ingestion_contract_repair`
   - Repair missing mapping rows while keeping downloads closed.

3. `soccertrack_sample_ingestion_blocker_summary`
   - Write blocker truth if the contract cannot safely support the next approval gate.

## Completed

- [x] Added contract-prep tests.
- [x] Added contract-prep script.
- [x] Generated SoccerTrack sample ingestion contract.
- [x] Generated fixture materialization plan for `gsr`, `bas`, and `mot`.
- [x] Wrote mapping and download-scope guardrail audits.
- [x] Preserved no dataset/sample download, no training, no promotion, and no runtime mutation.

## Result

- `goalAchieved = true`
- `primaryBlocker = null`
- `sampleIngestionContractReady = true`
- `selectedSampleResourceId = soccertrack_v2`
- `requiredTaskFixtures = [gsr, bas, mot]`
- `mappingCompletenessPassed = true`
- `sampleDownloadApprovalRequired = true`
- `sampleDownloadExecuted = false`
- `datasetDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationAllowed = false`
- `nextRecommendedNextLever = football_external_soccertrack_sample_fixture_materialization_approval`
