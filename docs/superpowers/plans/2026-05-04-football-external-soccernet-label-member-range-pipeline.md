# Football External SoccerNet Label-Member Range Pipeline

## Batch Chain

This plan records the continuation after `football_external_soccernet_split_archive_access_review`.

Completed no-training/no-promotion batches:

1. `football_external_soccernet_split_archive_size_probe`
   - Queried HuggingFace repository metadata only.
   - Found `valid.zip` at `2042230928` bytes.
   - Classified it as `large_archive`.
   - Routed to range/index probing before any full archive download.

2. `football_external_soccernet_split_archive_range_index_probe`
   - Used HTTP range metadata bytes to parse the ZIP central directory.
   - Found 6 entries:
     - 2 video members
     - 1 `Labels-ball.json` member
   - Kept video/full-archive downloads blocked.

3. `football_external_soccernet_zip_label_member_extract_approval`
   - Approved only label-member range extraction.
   - Required runtime-only `SOCCERNET_PASSWORD` because the member uses ZIP method `99`.
   - Kept full archive and video member downloads blocked.

4. `football_external_soccernet_zip_label_member_extract`
   - Fetched only approved label-member ZIP ranges plus central-directory bytes.
   - Extracted `Labels-ball.json`.
   - Produced 1 parseable label JSON with `1604` annotations.
   - Did not fetch MP4 members or the full archive.

5. `football_external_soccernet_label_schema_ingestion_probe`
   - Validated required annotation fields:
     - `gameTime`
     - `label`
     - `position`
     - `team`
     - `visibility`
   - Found `12` distinct event labels.
   - `positionParseRate = 1.0`
   - `gameTimeParseRate = 1.0`

6. `football_external_soccernet_event_adapter_fixture_materialization`
   - Materialized a canonical event timeline fixture with `1604` events.
   - Preserved source provenance.
   - Kept training, promotion, candidate evaluation readiness, runtime mutation, full archive download, and video member download closed.

## Latest Truth

- Latest completed batch: `football_external_soccernet_event_adapter_fixture_materialization`
- `goalAchieved = true`
- `primaryBlocker = null`
- `canonicalEventCount = 1604`
- `distinctEventTypeCount = 12`
- `eventFixtureQualityPassed = true`
- `eventIdUnique = true`
- `archiveDownloadExecuted = false`
- `videoMemberDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_event_adapter_smoke_test`

## Next Batch

`football_external_soccernet_event_adapter_smoke_test`

Goal:

- Load the canonical SoccerNet event fixture through the external adapter contract.
- Verify event timeline schema, ordering, taxonomy, and benchmark-harness compatibility.
- Do not train, promote, mutate runtime defaults, or download video members.
