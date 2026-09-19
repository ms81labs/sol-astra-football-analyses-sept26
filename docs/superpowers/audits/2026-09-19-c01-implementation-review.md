# C01 implementation review — draft, not whole-project closure

## Source and disposition

Repository: `ms81labs/sol-astra-football-analyses-sept26`.
Historical behavioural baseline: `b3fbe78c51f9a30891e939b610fa292da7f05bf9`.
Audited main: `6606564aced84b13aff896a8173d835b3a1001e3`.
Starting review branch: `3200b85cc004d5d7d5248e1116722acf887d3caf`.
Application implementation: `704556ab748e2f91baf6f6b1e8c50e915261dae2`.
This follow-up changes test fixture admission and CI setup, not application code.

**Overall C01 disposition: still open for complete integration/merge acceptance.** Real source and focused behavioural evidence now exist. This is not a claim that the full verifier, every compatibility path or all six work packages are complete. Do not merge on the strength of the focused count alone.

## Implemented contract

`backend/app/generations.py` coordinates immutable generation publication on local POSIX filesystems. `current_generation.json` is the sole analytical commit record. The manifest is digest-bound to the pointer; content hashes and required schemas are verified during publication and explicit recovery. Stable reads check retained file metadata instead of hashing the whole generation or modifying storage.

Readers hold a shared lifetime pin but release the publication lock after resolution. A publisher can therefore commit N+1 while an existing reader finishes N. Retention is explicit, dry-run by default, and refuses while a reader/publisher holds a pin. Current, rollback and referenced generations are protected. Ordinary reads never prune history or select the newest uncommitted directory.

Publication writes and validates the candidate before the pointer commit. SQLite analytical indexes are generation-tagged rebuildable projections updated after the pointer. Post-commit index failure does not roll back the analytical commit. Startup/maintenance recovery validates committed state and repairs indexes and included-command markers without applying a team swap twice. Operational permissions are not restored from historical analytical configuration.

Storage loaders, replacement writers, review publication and local remote-result import participate in the protocol. Remote-result cleanup precedes deferred pointer activation so cleanup failure cannot undo an already committed generation. Missing/corrupt authority produces controlled recovery-required responses rather than fabricated empty analytics. Legacy import is explicit and preserves source files, marking unavailable provenance unknown.

## Behavioural evidence actually retained

Local environment: Linux, Python **3.13.5**, existing available package environment, **not** the declared Python 3.11 hash-locked profile. Existing test import stub: `ultralytics`. Actual inference is forbidden in C01 child processes. Source patch SHA256: `f321c836fd27acfe3363932a49a8746a1017d0707c2c9de04f50cff3e7454f24` (first 14 implementation files, before this API-boundary fixture follow-up).

The same baseline-compatible tests for stable reads, retained history and stale SQL summary were executed on `b3fbe78`; all three failed on the intended behavioural assertions, not import errors. Their fixed versions passed. The remaining tests are candidate acceptance evidence, not invented historical failures.

| Local selection | Recorded result | Retained log basename |
|---|---|---|
| New C01 tests, final source | 25 passed | `c01-source-final` |
| C01 plus H02/H03/H05 | 63 passed, including the 25 C01 cases | `focused` |
| Storage atomic/streaming/index | 22 passed | `storage` |
| Local remote-import suite | 80 passed, 1 opt-in capacity test skipped | `remote` |
| API, API concurrency and origins | 99 passed | `api-confirmed` |
| Annotation/issue suite | 40 passed | `annotation-final` |
| API-boundary suite after this fixture follow-up | 39 passed | `api-boundaries-final` |
| Broader integration selection | 35 passed, 1 failed | `integration-cpu` |
| Unchanged H06 memory-limit test on historical baseline | Same MemoryError/child failure reproduced | `baseline-hash-memory` |

Counts from overlapping selections must not be added as independent tests. Logs, JUnit and exit files are retained in the conversation's source/evidence package; ordinary hosted workflow artifacts retain subsequent clean-profile runs.

The C01 tests include real spawned reader/writer processes coordinated by pipes, real process kills before/after the pointer commit with and without pending commands, repeated recovery, explicit retention, provenance-preserving replacement, changed-byte detection, corrupt/missing pointers, migration and normal API reads. Synthetic football observations test software invariants, not detector accuracy.

## Hosted verification at the application commit

GitHub run `35467819947`, focused job `105963291352`, explicitly checked out `704556ab748e2f91baf6f6b1e8c50e915261dae2`. It installed the declared hash-locked `dev.lock` profile under Python **3.11.16**. Result: **62 passed, 1 failed**, `stubs_active: ultralytics`. All 25 new C01 cases passed. The sole failure was `test_t17_generated_media_receipts_reach_stored_artifact_and_api_bundle`: `FileNotFoundError: ffmpeg`. The temporary workflow omitted FFmpeg installation; it was not an analytical assertion failure. Its hidden evidence directory was also excluded by the uploader, so that run's retained job log, not a nonexistent artifact, is the evidence.

This follow-up retires the one-off write-enabled publisher and replaces it with read-only `c01-regressions.yml`: genuine FFmpeg installation, Python 3.11 locked dependencies, source/runtime records, JUnit, actual stub receipt and a non-hidden artifact directory. A workflow definition is not a passing result; inspect its new run before reporting success.

## Compatibility test changes and remaining gates

Old tests expecting GET-time migration or corruption salvage were updated to explicit migration and controlled unavailability. Old reader-blocking expectations were replaced with the required pinned-reader/concurrent-publisher assertions. Provenance fixtures now use candidate configuration/calibration rather than changing mutable live inputs after publication. Persistent control files are allowed by exact name, not a blanket permission for leaked temporary files. Remote rollback tests retain their negative cases while excluding the pointer from rollback-owned flat files.

The API-boundary follow-up explicitly publishes complete fixture generations. Its candidate-configuration test now checks that materialisation sees the requested inputs while raw SQL still holds the old configuration before commit. Provider validation, escaping, late-result rejection and rollback assertions remain intact.

The full code-only verifier was attempted but interrupted after wider failures and a stall; it did not complete. Some identified fixture incompatibilities have been repaired, but a complete rerun and classification of every remaining failure are still required. The H06 128 MiB address-space hashing subprocess failed locally on both baseline and candidate; its limit was not relaxed. Full frontend/build/security verification and complete integration acceptance are not established by this note.

C02 semantic-edit composition and source reprojection, C03 narrative/evidence publication, C04 money, C05 reuse/evaluation and C06 media policy remain outside this C01 review. Unknown legacy provenance remains unknown. No actual model inference, football accuracy evaluation, browser pilot, macOS qualification, provider execution, paid/GPU worker or deployment was performed. Main was not changed.

## Review/rollback

Review on `agent/c01-generation-hardening-20260919`, using copied or synthetic storage only. Do not point an older binary at a migrated production store or change a live user's store as part of review. Preserve pre-migration copies and immutable history. This is a draft implementation review, not the final v3.1 closure document.
