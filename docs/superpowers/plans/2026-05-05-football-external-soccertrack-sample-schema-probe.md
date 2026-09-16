# Football External SoccerTrack Sample Schema Probe

## Batch

- Active batch: `football_external_soccertrack_sample_schema_probe`
- Attempt budget: `3`
- Attempt 1 family: `soccertrack_sample_schema_surface_probe`

## Goal

Use fetched SoccerTrack metadata only to identify public sample-schema documentation surfaces and prepare a controlled schema-doc fetch approval. Do not download datasets or samples.

## Attempt Plan

1. `soccertrack_sample_schema_surface_probe`
   - Read fetched metadata only.
   - Identify GSR, BAS, and MOT schema/task documentation surfaces.
   - Write schema-doc fetch plan and sample-schema contract.

2. `soccertrack_schema_surface_contract_repair`
   - Repair schema-doc path extraction from fetched metadata only.
   - Keep schema-doc fetch approval-only.

3. `soccertrack_sample_schema_blocker_summary`
   - If schema surfaces cannot be proven, write blocker truth and stop before schema-doc/sample fetch.

## Completed

- [x] Added schema-probe tests.
- [x] Added schema-probe script.
- [x] Generated schema surface audit.
- [x] Generated schema-doc fetch plan.
- [x] Generated sample-schema contract.
- [x] Preserved no-download, no-training, no-promotion, and no-runtime-mutation invariants.

## Result

- `goalAchieved = true`
- `primaryBlocker = null`
- `sampleSchemaProbeReady = true`
- `detectedTaskIds = [gsr, bas, mot]`
- `schemaDocCandidateCount = 5`
- `schemaDocFetchExecuted = false`
- `datasetDownloadExecuted = false`
- `sampleDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationAllowed = false`
- `nextRecommendedNextLever = football_external_soccertrack_schema_doc_fetch_approval`
