# Next task: report-store structural decomposition

**Saved draft only. Not applied to application code and not accepted.**

Base: `efcc3e1193428c554449bf3d5c5f671635f1b235`.
Patch: [unpublished/report-store-extraction.patch](unpublished/report-store-extraction.patch).
Manifest: [unpublished/MANIFEST.json](unpublished/MANIFEST.json).
SHA-256: `8ba72cfb2dde0ff31f5747e1e1688bf0fed1e134f52137c34dea7962ca31d651`.

The saved delta changes only `backend/app/report_store.py` and `backend/quality/ruff-baseline.json`. Its original candidate tree is `eaffc7f8ff8a53b5f61cd3b0283a6030c17c24cd`. That tree excludes this later handoff documentation: preserve later documents and verify the two expected file blobs from the manifest rather than resetting to the old tree.

## Initial reading

Read current `backend/app/report_store.py`, `backend/app/report_contracts.py`, `backend/tests/test_report_store_contract.py`, `backend/tests/test_quality_gate.py`, `pyproject.toml`, and `backend/quality/README.md`. The 59 report-store cases and two typing repairs are already committed. Do not re-add them.

## Intended extraction

Extract `_validate_record_metadata`, `_validate_deterministic_payload`, `_narrative_draft_base`, `_strip_claim_metadata`, and `ReportStore._verified_candidates`. Preserve `validate_record`, narrative validation, `publish` and `view` as compatible entry points. No new persisted schema or policy.

Only three C901 entries should be retired: `validate_record` (18), `_validate_narrative_payload` (17), and `ReportStore.view` (11). Expected Ruff is 405 to 402, with no added diagnostics. Scoped mypy must stay clean. Verify helpers against the existing complexity threshold, not a raised limit.

## Invariants to test

Preserve identity, digest, timestamp and scope checks in their exact failure order, including the first error when multiple fields are malformed. Keep review requirements, claim availability and disposition unchanged. Reject unresolved evidence aliases, other matches and other generations in every reference collection.

Preserve native, legacy-referenced and deterministic payload shapes and failures. Strip claim metadata from the adapted copy, never from persisted input. Keep notice keys and order, latest-valid selection despite a newer invalid report, task order, and the original catch boundary around optional invalid records.

Generation snapshots, selection, lock ownership, writes, fsync and atomic publication remain at their original boundaries. Preserve symlink/member refusal, content digests and conditional filesystem calls. Moving side effects into an unprotected helper is not acceptable.

## Execution and acceptance

1. Reconcile live main and confirm the saved patch hash. Confirm it is not already applied.
2. Run original report-store/quality and broader C03/API/journey contracts from VERIFICATION_RUNBOOK.md. Preserve original logs separately.
3. Review then apply the two-file delta to the reconciled checkout. `git apply --check` must succeed. If source has changed, adapt deliberately and record a new base/hash rather than overwriting.
4. Run candidate contracts, both pytest entry points, quality ratchets and explicit report-store typing. Add regression tests for uncovered invariants. Characterization may be green on both versions; mutation/differential checks should demonstrate sensitivity to unintended changes.
5. Review the baseline identity delta: exactly three intended removals, unchanged metadata, no new allowances. Run the full applicable project suite; retain failures honestly.
6. Publish through permitted ordinary Git operations on the existing integration line, with required approvals. Do not recreate a preflight workflow. Obtain completed existing normal CI and C05/C06 on the newly published application SHA.
7. Record exact evidence and mark only this structural slice accepted. Keep broader audit work open.

Earlier local work on the exact extracted code reported 181 selected passes/two skips, console59 and 3,016 validator comparisons, plus helper-reconstruction equivalence. These are historical supplemental observations, not fresh pinned acceptance or a proof over arbitrary custom objects/concurrent mutation. The previous handoff only rechecked patch application and candidate hashes. Re-run behavior checks in the new session.
