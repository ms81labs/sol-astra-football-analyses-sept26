# Task 5 / R05: serialized review updates with recoverable publication

Base: `2a4c7d62862e0a5b2e4f68475150ce98cacad44e`.
Worktree: `/root/WorkSpace/fotball-analyst/.worktrees/batch-1-data-safety`.
Design: the approved `task-5-brief.md` in this directory.

## Implementation and outcome contract

All three legacy tools now import one `threading.Lock` from `backend/scripts/review_io.py`. Each update holds it from overlay-path selection and load through schema validation, lookup, mutation, recount, publication, and response construction. Review schemas, status/bbox rules, and resolution functions remain in their respective server modules. The Ponytail comment explicitly limits serialization to one process and names an OS/file lock as the upgrade for multiple processes.

The three copied writers were removed and their existing `_write_json_atomic(path, payload)` names remain aliases to the common writer. The approved hard-link protocol works with real files on this Linux filesystem:

1. Open the filesystem root and walk every parent component using `O_DIRECTORY | O_NOFOLLOW`, pinning the final directory descriptor before any temporary creation.
2. Reject a non-regular or symlink destination. Create a random same-directory temporary name with `O_CREAT | O_EXCL | O_NOFOLLOW`, mode `0600`, relative to that descriptor.
3. Encode JSON, flush the stream, and fsync its file descriptor. A failed `fdopen` explicitly closes the raw descriptor.
4. If a prior destination exists, retain it through an atomically created unique hard link in that directory. Verify the retained inode matches the regular destination inspected earlier. Fsync the directory while both the original name and backup exist.
5. Replace the destination relative to the pinned descriptor, then fsync that same descriptor. No parent is opened after publication. Only after this commit succeeds is the backup unlinked.
6. Failure before replacement returns `ReviewWriteError("review_write_failed")` with prior bytes intact. Failure after replacement restores the hard-link backup, or removes a newly created destination, and attempts a directory fsync of that rollback. Even if rollback fsync also fails, the caller receives a write error with known prior bytes/absence visible.
7. If the restore/remove syscall fails, raise `ReviewWriteOutcomeUncertain("review_write_outcome_uncertain_do_not_retry")`; preserve an existing backup for manual recovery. HTTP handlers return 409 with that safe identifier. Ordinary write/read failures return 503 with `review_write_failed`. Neither response exposes paths or starts an automatic retry.

A backup-unlink error after the durable commit also rolls back while that backup still exists, avoiding an ordinary error with new bytes published. Filesystem operations during exception cleanup are attempted without replacing the primary write/outcome error. If the filesystem itself refuses cleanup, disposable evidence may remain; no successful save is reported for that failure path.

JSON loads now reject corrupt/non-object documents with a safe `ReviewUpdateError`; missing/non-list `reviewItems` and every non-object row are rejected before mutation. No malformed rows are silently filtered out. The schema check remains in each existing module. The new module also contains a small regular-byte reader sharing the pinned-parent traversal: adding secure reads exposed an existing reader's fd ownership bug, and this avoids introducing that leak into overlay updates without changing R02's HTTP/file helper.

Self-review also found an existing post-publication response failure: updates matched an item ID with `str(...)`, then used exact type equality in `next(...)` after saving. A numeric stored ID could therefore save successfully and raise `StopIteration`. Returning the already matched row preserves the response schema and eliminates that failure after publication.

## RED evidence before implementation

Production files were unchanged during the first test runs.

```text
python3 -m pytest -q backend/tests/test_review_io.py --tb=short
84 failed in 1.02s
```

The real two-thread barrier test failed for each tool: both calls were accepted, but one row remained `pending_review` in the final file. Invalid mixed rows were silently discarded; corrupt/non-object documents lacked the safe validation contract. Each copied writer leaked its raw descriptor on a failed `fdopen`. Durability fault tests either saw no exception because no fsync/backup stage ran, or exposed the unsanitized injected exception. The successful-write observation recorded `[]`, where the required actual sync stages were `[data, backup, commit]`. Symlink parent/destination cases incorrectly succeeded. The failed-rollback cases never reached any rollback because none existed.

```text
python3 -m pytest -q backend/tests/test_serve_promoted_v6_manual_review_ui.py -k distinguishes_safe_write --tb=short
9 failed, 148 deselected in 0.58s
```

All three real HTTP handlers returned 500 instead of the safe 503 for a replace failure, and returned 200 instead of 503/409 for commit/rollback failures because their old writers never called fsync.

First implementation GREEN:

```text
python3 -m pytest -q backend/tests/test_review_io.py backend/tests/test_serve_promoted_v6_manual_review_ui.py -k 'not times_out and not cli' --tb=short
217 passed, 24 deselected in 3.41s
```

The read-descriptor issue was separately reproduced before its fix:

```text
python3 -m pytest -q backend/tests/test_review_io.py -k 'overlay_fdopen or different_server or non_regular or collision or cleanup_failure or not_reopened or parent_swap or symlink_swap' --tb=short
3 failed, 25 passed, 84 deselected in 0.68s
```

All three failures were `os.fstat(fd)` still succeeding after failed overlay `fdopen`. After adding the small byte reader with explicit descriptor ownership:

```text
python3 -m pytest -q backend/tests/test_review_io.py --tb=short
112 passed in 1.38s
```

The normalized-ID response failure was then reproduced before changing the returns:

```text
python3 -m pytest -q backend/tests/test_review_io.py -k normalized_item_lookup --tb=short
3 failed, 112 deselected in 0.43s
```

All three failures were `StopIteration` at the existing return after the edit was published. Returning the matched row produced the next full focused GREEN: `288 passed in 23.29s`.

Additional characterization checks cover component-open/stat/stream-close faults and a read failing after consuming bytes. These required no production changes and brought the direct filesystem suite to `130 passed in 1.50s`.

## Fault matrix

Tests use actual disposable files, hard links, directory descriptors, symlinks, FIFOs, threaded update calls, and local HTTP sockets. Fault injection wraps only the relevant syscall/stream operation; it does not replace publication or the filesystem with a mock. New tests do not inspect source strings.

| Fault/vector | Checked visible outcome and cleanup |
| --- | --- |
| Concurrent different-item edits in each tool | Both accepted decisions and the final recount survive. A start barrier and overlapping real reads reproduce the original lost update. |
| Two different server modules writing the same overlay | Both accepted rows survive, proving module-local locks would be insufficient. |
| Corrupt JSON, top-level list/null, missing/list-invalid `reviewItems` | Safe validation error; input bytes untouched; no extra names. |
| Valid row followed by null or integer | Whole update rejected; malformed row and original bytes preserved. |
| Root-directory open failure | Safe write error; original bytes and directory contents unchanged. |
| Intermediate parent-component open failure | Same outcome, with descriptor traversal unwound. |
| Destination stat failure | Safe error before temporary creation; original bytes preserved. |
| Temporary creation failure | Prior bytes unchanged; no owned temporary name to clean. |
| Writer `fdopen` failure | Prior bytes unchanged, temporary removed, captured raw fd closed. |
| Overlay `fdopen` failure | Prior bytes unchanged, no temporary created, captured raw fd closed. |
| Overlay read fails after a real partial read | Prior bytes unchanged, no temporary created, captured raw fd closed. |
| JSON encoding error | Partial private file removed; prior bytes unchanged; safe error. |
| Partial stream write failure | Stream closed, private file removed, prior bytes unchanged. |
| Explicit flush failure | Private file removed; no replacement; safe error. |
| Stream close failure | Prior bytes unchanged; private file removed; safe error. |
| File fsync failure | Prior bytes unchanged; private file removed; no backup/replacement. |
| Hard-link creation failure | Prior bytes unchanged; temporary removed. |
| Backup stat/verification failure | Prior bytes unchanged; owned temporary and backup removed. |
| Backup directory fsync failure | Prior bytes unchanged; temporary and backup removed. |
| Destination replacement failure | Prior bytes unchanged; temporary and backup removed. |
| Post-replacement directory fsync failure, existing destination | Prior exact bytes restored through real rename of backup; rollback fsync attempted; no leftover names. |
| Post-replacement directory fsync failure, new destination | New destination removed; rollback fsync attempted; no leftover names. |
| Rollback directory fsync also fails | The same visible prior bytes/absence and ordinary write error; no false durable-success claim. |
| Rollback restore fails | Distinct uncertain error; new bytes visible, old bytes retained in exactly one backup. |
| Rollback removal fails for new destination | Distinct uncertain error; new bytes remain visible, no false prior-state claim. |
| Backup cleanup fails after durable commit | Restore prior bytes before returning safe write error; no obsolete backup/temp left. |
| Existing temp or backup name collision | Collision sentinel never deleted or overwritten; original destination unchanged. |
| Destination, parent, or ancestor symlink | Safe rejection; outside sentinel and outside directory contents unchanged. |
| Directory or FIFO destination | Rejected without opening/blocking on the node; node inode unchanged. |
| Parent swapped for symlink before temporary creation | Temporary and publication stay in the pinned original directory; outside sentinel untouched. |
| Destination swapped for symlink immediately before link | No unowned target read/write; symlink backup rejected and cleaned. |
| Parent open becomes unavailable after publication | Save succeeds using already pinned descriptor; no late parent open occurs. |
| Normal durable publication | Actual file fsync, backup directory fsync, and commit directory fsync in order; temporary mode 0600; backup exists until commit; final JSON correct; no leftovers. |
| Normalized item ID | Successful response returns exactly the saved matched row; no post-save `StopIteration`. |
| HTTP preparation/commit/rollback failures, all tools | Exact safe 503 versus 409 error payload; ordinary error preserves prior bytes; uncertainty explicitly forbids retry. |

## Final verification

Final focused command:

```text
python3 -m pytest -q backend/tests/test_review_io.py backend/tests/test_serve_promoted_v6_manual_review_ui.py backend/tests/test_serve_v7_1_positive_diversity_review_ui.py backend/tests/test_serve_football_external_soccernet_detector_miss_review_ui.py
303 passed in 23.58s
```

Relevant operational/startup and existing resolver tests:

```text
env PATH=/root/.cache/fotball-analyst/daytona-smoke-0.207.0/bin:$PATH python3 -m pytest -q backend/tests/test_operational_docs.py backend/tests/test_documented_startup.py backend/tests/test_run_promoted_v6_manual_review_resolution_batch.py backend/tests/test_run_v7_1_positive_diversity_manual_review_resolution.py backend/tests/test_run_football_external_soccernet_detector_miss_manual_review_resolution.py -k 'not test_root_package_builds_and_imports_documented_asgi_target_outside_checkout and not test_sidecar_package_installs_imports_and_exposes_cli_without_pythonpath'
82 passed, 2 deselected in 28.95s
```

The existing cached interpreter satisfies the operational suite's installed-SDK import/version check. No provider API or smoke command ran. The two deselected tests install packages and are excluded under this task's explicit no-install boundary. Existing operational tests include their established documentation assertions; new R05 tests are behavioral.

`git diff --check` passed. No dependencies, UI files, R02 HTTP helper, R04 application/origin code, resolver modules, or real data were changed. Existing R02 HTTP boundary cases (including default-port authority, body bounds, timeouts, no-follow image access, and loopback CLI behavior) pass in the full focused suite. R03 DOM assets are untouched.

## Changed files and self-review

- `backend/scripts/review_io.py`: the single permitted shared module, holding the process-wide lock, durable writer/errors, pinned-parent traversal, and descriptor-safe byte reader.
- The three `backend/scripts/serve_*review_ui.py` consumers named in the brief: shared transaction/write/read use, local strict schema validation, safe HTTP write outcomes, and return of the matched row.
- `backend/tests/test_review_io.py`: filesystem/concurrency/fault tests parameterized over all three real consumers.
- `backend/tests/test_serve_promoted_v6_manual_review_ui.py`: real HTTP outcome tests using its existing fixture that covers all three handlers.
- This report.

Reviewed every caller of the replaced writers and update functions. Existing `Storage._atomic_text_destination`, `remote_contracts.atomic_write_json`, and runtime materialization helpers do not preserve prior destination bytes through this required hard-link rollback contract; they cannot substitute for this writer. No second shared production module was added. The implementation uses only the standard library.

Reviewed all success/error exits against the approved durable-new/success versus visible-prior/error distinction, including the two newly discovered fd/response failure paths. Confirmed backup ownership is set only after successful link creation, temporary ownership only after successful exclusive creation, and uncertain rollback retains recovery bytes. The fault tests exercise each publication stage and all three HTTP consumers. Changes belonging to the pre-existing untracked `.verification/` directory were left alone.

## Residual ceiling

Serialization applies only to participating updates in one Python process. Concurrent processes, external in-place writers, and external replacement of the directory namespace are not coordinated; add an OS/file lock before operating multiple writer processes against one overlay. Symlink-race tests establish confinement, not isolation from an external actor deliberately replacing the overlay itself.

An unsuccessful rollback fsync guarantees the observed prior state, not crash durability of that rollback; this is the approved visible-state error contract. A failed restore has a distinct uncertain outcome and keeps recovery bytes when available. Process termination, power failure, or a filesystem refusing cleanup can leave recovery/private names; no crash-recovery scanner or automatic retry was added. Platforms/filesystems must support the tested POSIX directory descriptors, no-follow operations, hard links, and directory fsync; failure to prepare those operations returns a safe error before replacement.

## Review fix round 1: preserve the primary outcome during parent close

Review base: `d51d2ed87d7fdf72c625a05d0af36e44498a96ba`.

Confirmed finding: the final `os.close(parent)` was outside protected handling. After a successful directory fsync it could raise a raw `OSError` with the new bytes durable and backup removed. During failed rollback it could mask `ReviewWriteOutcomeUncertain`, producing a generic 500 instead of the required safe 409.

The approved correction treats only this final parent-directory descriptor close failure as cleanup noise. The close is attempted once and an `OSError` there is suppressed: durable success remains success, and a pending primary safe write/uncertainty error remains that same error. File fsync, backup fsync, commit fsync, and rollback failures keep their existing handling. No close retry is attempted because a failed close may already have released the descriptor.

Regressions use the real write/link/replace/fsync path and real HTTP handlers. The injected close wrapper calls the actual `os.close` and then raises the fault. Coverage includes durable success, prepublication failure, successful rollback, and uncertain rollback in all three HTTP handlers, plus direct durable-success and both existing/new-destination uncertain rollback cases. Tests verify final bytes, retained recovery evidence, safe response bodies, and 200/503/409 status selection.

The first RED run with `--tb=short` reported `21 failed, 18 passed, 272 deselected in 1.07s`. Direct uncertain-outcome tests saw `OSError` instead of `ReviewWriteOutcomeUncertain`; durable-success tests raised `OSError: private-path/parent-close` at the unguarded final close; all twelve HTTP close-failure combinations returned 500 instead of the required 200/503/409. Production remained unchanged until this RED result.

Full compact RED command and output (rerun before the production fix):

```text
python3 -m pytest -q backend/tests/test_review_io.py backend/tests/test_serve_promoted_v6_manual_review_ui.py -k 'parent_close_failure or failed_rollback_has_distinct or distinguishes_safe_write' --tb=line --no-summary
..FF..FF..FFFFF....FFFF....FFFF....FFFF                                  [100%]
21 failed, 18 passed, 272 deselected in 0.89s
```

Full GREEN command and output after the five-line close guard:

```text
python3 -m pytest -q backend/tests/test_review_io.py backend/tests/test_serve_promoted_v6_manual_review_ui.py -k 'parent_close_failure or failed_rollback_has_distinct or distinguishes_safe_write' --tb=line --no-summary
.......................................                                  [100%]
39 passed, 272 deselected in 0.86s
```

Final full focused command and output:

```text
python3 -m pytest -q backend/tests/test_review_io.py backend/tests/test_serve_promoted_v6_manual_review_ui.py backend/tests/test_serve_v7_1_positive_diversity_review_ui.py backend/tests/test_serve_football_external_soccernet_detector_miss_review_ui.py
........................................................................ [ 22%]
........................................................................ [ 44%]
........................................................................ [ 66%]
........................................................................ [ 88%]
.......................................                                  [100%]
327 passed in 23.97s
```

Round 1 changes are restricted to the final close guard in `review_io.py`, the two existing R05 test files, and this report. Self-review confirms final close cannot override either known durable success or the primary safe exception, and no durability error handling was weakened. The process-local serialization/recovery ceilings above are unchanged. No cloud/provider/smoke/install action or real-data deletion occurred.
