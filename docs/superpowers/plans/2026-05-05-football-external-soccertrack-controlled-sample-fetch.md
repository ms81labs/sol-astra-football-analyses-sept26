# Football External SoccerTrack Controlled Sample Fetch

## Batch

- Active batch: `football_external_soccertrack_controlled_sample_fetch`
- Attempt budget: `3`
- Attempt 1 family: `soccertrack_controlled_fixture_source_tree_fetch`

## Goal

Fetch a complete one-match GSR/BAS/MOT SoccerTrack fixture set only if the official source exposes bounded non-media fixture files. Do not fetch full datasets, large media, or training data.

## Attempt Plan

1. `soccertrack_controlled_fixture_source_tree_fetch`
   - Probe the official SoccerTrack GitHub tree.
   - Fetch only complete one-match GSR/BAS/MOT fixture files if present.
   - Skip large media and full dataset scopes.

2. `soccertrack_controlled_fixture_source_locator_repair`
   - Repair fixture path detection while preserving one-match scope.

3. `soccertrack_controlled_sample_fetch_blocker_summary`
   - Write blocker truth and select one next family if fixture files are unavailable.

## Result

- `goalAchieved = false`
- `primaryBlocker = football_external_soccertrack_public_fixture_files_missing`
- `sourceTreeProbeExecuted = true`
- `completeOneMatchFixtureFound = false`
- `controlledSampleFetchExecuted = false`
- `downloadedFixtureFileCount = 0`
- `sampleDownloadExecuted = false`
- `datasetDownloadExecuted = false`
- `fullDatasetDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationAllowed = false`
- `nextRecommendedNextLever = football_external_soccertrack_fixture_source_access_review`

## Interpretation

The official GitHub tree does not expose a complete one-match GSR/BAS/MOT fixture set. The batch intentionally refused to treat large demo media or metadata-only docs as adapter fixtures.
