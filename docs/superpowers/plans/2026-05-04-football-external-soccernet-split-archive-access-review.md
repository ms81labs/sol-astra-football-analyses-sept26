# Football External SoccerNet Split Archive Access Review

## Batch Contract

- Batch: `football_external_soccernet_split_archive_access_review`
- Attempt budget: `3`
- Attempt 1 family: `soccernet_split_archive_surface_review`
- Source truth:
  - `football_external_soccernet_label_fetch_contract_repair_v1/label_fetch_contract_repair_summary.json`
  - `football_external_soccernet_label_fetch_contract_repair_v1/repaired_access_contract_plan.json`
  - `football_external_soccernet_api_metadata_probe_v1/soccernet_api_package_audit.json`

## Goal

Confirm whether the repaired SoccerNet ball-label access path should move from unsupported per-game `Labels.json` fetches to package-supported split archive surfaces, without downloading any archive bytes.

## Failsafe Attempts

1. `soccernet_split_archive_surface_review`
   - Inspect repaired access truth and installed SoccerNet downloader source.
   - Select a metadata-first split archive target if one is package-supported.
   - Keep archive/video/feature/training/runtime mutation guardrails closed.

2. `soccernet_split_archive_contract_repair`
   - Use only if the surface exists but task/split/access-mode fields need normalization.
   - Do not broaden access or approve downloads.

3. `soccernet_split_archive_blocker_summary`
   - If no safe archive surface is visible, write blocker truth and route to one corrective family.

## Success Truth

- `goalAchieved = true`
- `primaryBlocker = null`
- `selectedArchiveTask = spotting-ball-2025`
- `selectedSplit = valid`
- `selectedAccessMode = huggingface_snapshot_allow_pattern`
- `selectedArchiveFileOrPattern = *valid.zip`
- `splitArchiveDownloadApproved = false`
- `datasetDownloadExecuted = false`
- `fullOriginalVideoDownloadExecuted = false`
- `trainingExecuted = false`
- `runtimeDefaultMutationExecuted = false`
- `nextRecommendedNextLever = football_external_soccernet_split_archive_size_probe`

## Verification

- Focused red-to-green test:
  - `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests/test_run_football_external_soccernet_split_archive_access_review.py -q`
- Artifact generation:
  - `python3 backend/scripts/run_football_external_soccernet_split_archive_access_review.py`
- Broader external-lane verification and hygiene run after roadmap updates.
