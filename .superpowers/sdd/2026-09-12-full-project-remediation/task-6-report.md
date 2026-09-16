# Task 6 / R06: canonical bundle names and confined ZIP publication

Base: `335e70199ad540a349054816cf9afaceb529f86a`.
Worktree: `/root/WorkSpace/fotball-analyst/.worktrees/batch-1-data-safety`.
Requirements: `task-6-brief.md` in this directory.

## Implemented behavior

The builder validates `bundle_date` with `date.fromisoformat(...).isoformat()` as its first operation, before even resolving the repository or archive path. Missing/empty dates retain the existing today default. Accepted basic ISO dates such as `20260423` become `2026-04-23` in both profile names, both top-level output paths, manifests, ZIP member prefixes, and README text. Invalid dates and slash/backslash/parent components fail before output creation.

The archive path is made absolute without following symlinks. A small local context manager walks and pins every archive ancestor with `O_DIRECTORY | O_NOFOLLOW`, creates missing ordinary directories, and retains their inode identities for validation. Archive paths containing parent traversal are rejected. The existing owning-root reset pattern from `football_external_real_eval_chain_common.reset_output` is applied locally: no-follow classification, descriptor-relative `shutil.rmtree`, and descriptor-relative `mkdir`. Keeping that pattern local allows the same archive descriptor to remain open across reset and publication; calling the existing helper would close its owning descriptor before publication.

The newly created bundle directory is also pinned. Its Linux `/proc/self/fd/<fd>` path keeps the existing Path-based copy, README, manifest and ZIP traversal logic bound to that directory during ancestor or bundle-name swaps. The proc-fd path must identify the opened directory. This guard runs on the archive descriptor before resetting an existing bundle and again on the opened bundle descriptor. The parent agent explicitly approved this minimal Linux bridge and its availability/identity test; no second copier abstraction was added.

ZIP publication creates an exclusive, random, same-directory private file with mode `0600`. It writes and closes the ZIP, flushes the underlying stream, reopens the candidate through the same handle for ZIP/CRC validation, and fsyncs the candidate. Immediately before publication it checks the archive chain, bundle identity, prior final ZIP identity, and private candidate identity. `os.replace` then replaces only the canonical final basename relative to the pinned archive descriptor, followed by fsync of that descriptor. A pre-replace failure removes the private name and preserves the previous ZIP bytes. There is no initial unlink of the previous ZIP.

The full/core file plans, source exclusions, manifest schema, README content apart from date normalization, member layout, and returned fields are unchanged. Historical sibling directories and archives are preserved. R05's review writer was inspected but not reused: its JSON serialization, process lock, backup link and post-publication rollback contract are different from this ZIP builder's bounded requirements.

## Caller trace

Repository-wide searches for `build_parallel_research_bundle` and `_zip_bundle_root` found the CLI `main`, the two pre-existing profile tests, and documentation references. `build_parallel_research_bundle` is the sole production caller of `_zip_bundle_root`. The actual flow was traced through file-plan collection, truth reads, copy, README/manifest writes, and ZIP creation before editing production code. No other production callers require adaptation.

## RED/GREEN evidence

Tests were written against real pytest temporary directories, real symlinks and renames, and real ZIP files before production edits. Fault injection wraps the relevant real filesystem/ZIP operation and preserves its useful side effects.

Initial RED: `python3 -m pytest -q backend/tests/test_build_parallel_research_bundle.py` produced **32 failed, 6 passed**. Failures showed acceptance of invalid/path-bearing dates, noncanonical names, followed archive symlinks, replaced ZIP symlinks, destroyed prior ZIPs, and redirected output or archive loss during copy/ZIP namespace swaps. The close-fault injector initially also raised from `ZipFile.__del__`; it was corrected to fail only while the ZIP was actually open, removing that test warning before production changes.

Expanded preproduction RED: the same command with `--tb=no` produced **35 failed, 6 passed in 1.07s**, adding ordinary-directory/ZIP inode replacement and the missing file-fsync/replace/directory-fsync sequence. The separately added proc-fd guard cases produced **2 failed, 41 deselected in 0.16s** before implementation.

First GREEN after the production change: **43 passed in 0.80s**.

Self-review identified a further name-to-inode gap for the private ZIP itself. The new `test_bundle_rejects_replaced_temporary_zip` renamed its actual filesystem destination into a symlink during file fsync and failed with `DID NOT RAISE`: **1 failed, 43 deselected in 0.13s**. A three-line candidate identity check fixed that gap before replacement.

Final exact focused command:

```text
python3 -m pytest -q backend/tests/test_build_parallel_research_bundle.py
44 passed in 0.92s
```

Related ownership/reset, storage cleanup and release-archive tests:

```text
python3 -m pytest -q backend/tests/test_build_parallel_research_bundle.py backend/tests/test_football_external_real_eval_chain_common.py backend/tests/test_run_video_to_analysis_storage_cleanup_bounded_execution.py backend/tests/test_run_video_to_analysis_release_acceptance_archive.py
80 passed in 1.33s
```

Relevant operational/startup tests:

```text
env PATH=/root/.cache/fotball-analyst/daytona-smoke-0.207.0/bin:$PATH python3 -m pytest -q backend/tests/test_operational_docs.py backend/tests/test_documented_startup.py -k 'not test_root_package_builds_and_imports_documented_asgi_target_outside_checkout and not test_sidecar_package_installs_imports_and_exposes_cli_without_pythonpath'
60 passed, 2 deselected in 28.47s
```

The cached interpreter was reused for the existing installed-SDK import/version assertion. No smoke or provider command ran. The two excluded tests perform package installations, which this task forbids. `git diff --check` passed.

## Fault vectors covered

| Vector | Observed result after correction |
| --- | --- |
| Slash, backslash, parent components; absolute-looking or invalid dates, both profiles | ValueError before archive creation; outside sentinel unchanged. |
| Basic ISO date, both profiles | Canonical names/text/manifest; exact member set including README and manifest; CRC-valid ZIP; stale exact bundle removed; historical siblings preserved. |
| Archive or ancestor symlink | Rejected; outside directory and previous archive unchanged. |
| Bundle directory symlink | Rejected; outside directory and previous archive unchanged. |
| Existing or dangling final ZIP symlink | Rejected without replacing the symlink or touching its target. |
| ZIP member write or close error | Prior valid ZIP bytes preserved; private candidate removed. |
| Candidate file fsync or replacement failure | Same preservation and cleanup result. |
| Archive/ancestor/bundle swaps at reset, copy or ZIP write | Failure with outside sentinel and prior ZIP preserved; no private candidate remains in the pinned original archive. |
| Ordinary archive or final ZIP replacement during ZIP writing | Replacement sentinel untouched; retained original ZIP bytes preserved. |
| Missing or mismatched proc-fd bridge | Fails before existing bundle reset; old bundle and archive bytes preserved. |
| Private ZIP name replaced with outside symlink at file fsync | Refused before publication; prior archive and outside bytes unchanged; private symlink removed. |
| Normal publication | Real candidate ZIP is readable/CRC-valid before replacement; file fsync, replacement and pinned-directory fsync occur in order. |

## Changed files and self-review

- `backend/scripts/build_parallel_research_bundle.py`: canonical date, pinned owning archive and bundle paths, bounded reset, validated private ZIP publication.
- `backend/tests/test_build_parallel_research_bundle.py`: real-filesystem and ZIP regression cases plus full/core compatibility checks.
- This report.

Reviewed descriptor lifetime, temporary ownership after exclusive creation, pre-replace cleanup, no-follow target classification, namespace identity checks, canonical values used throughout output, and exact top-level naming. Only standard-library facilities were added. Existing R01-R05 commits and the pre-existing untracked `.verification/` directory are preserved. No repository inputs, models, videos, datasets, historical real archives, dependencies or provider state were mutated. All destructive test operations were confined to pytest temporary directories.

## Concerns and boundaries

This implementation requires Linux proc-fd and POSIX no-follow/descriptor-relative operations plus directory fsync. The proc-fd bridge is checked before bundle reset; supporting other platforms would require a descriptor-relative copier. This deliberate ceiling is marked in the code.

The unpacked exact-name bundle remains a reset-and-rebuild working directory, as before; a failed build can leave partial new bundle contents. The preserved recovery artifact is the prior ZIP. No bundle-directory transaction or multi-writer coordination was added. The identity checks reject observed namespace replacements, while descriptor-relative operations confine publication even if a parent changes between checks and the syscall; they are not an OS-level compare-and-swap protocol against arbitrary concurrent writers.

After a successful replacement, a directory-fsync failure propagates and the new complete ZIP may already be visible; crash durability is then unconfirmed. The task requires previous-byte preservation before replacement, not R05-style post-replace rollback. Process termination or filesystem refusal of cleanup can leave a private candidate. No crash-recovery framework was added.

## Review fix round 1: bind reset traversal to the validated bundle inode

Review base: `514ba04e1ff1e4c95c8c8af1ec35e428f27d0392`.

Confirmed finding: the original `os.stat(bundle_name, ...)` result was not bound to the subsequent `shutil.rmtree(bundle_name, dir_fd=archive_fd)`. Replacing that entry with an ordinary directory after classification caused deletion of the replacement's contents and successful ZIP publication. Pinning the archive parent protected against following outside parents but did not bind the child being deleted to the previously inspected inode.

The new regressions use real directory renames and replacements at two boundaries: immediately after returning the original entry's classification and immediately before scanning the already-open directory descriptor. Both empty and populated replacement directories are covered. The populated replacement contains `keep.txt`; the empty replacement is itself an inode sentinel and exposes the missing final identity check that a nonempty-directory error could hide. Every case requires failure, retention of the replacement inode/contents, and the exact prior ZIP bytes. The existing reset/symlink tests now inject at the real initial classification boundary instead of coupling the test to a `shutil.rmtree` call.

Exact expanded RED command and output, before production edits:

```text
python3 -m pytest -q backend/tests/test_build_parallel_research_bundle.py -k 'reset_rejects_replacement_directory or rejects_namespace_swaps' --tb=short
.........FFF.
FAILED test_bundle_reset_rejects_replacement_directory[False-classified]: DID NOT RAISE
FAILED test_bundle_reset_rejects_replacement_directory[False-traversal]: DID NOT RAISE
FAILED test_bundle_reset_rejects_replacement_directory[True-classified]: DID NOT RAISE
3 failed, 10 passed, 35 deselected in 0.45s
```

The correction opens the old bundle with `O_DIRECTORY | O_NOFOLLOW` and requires its `fstat` identity to match the original classification. It retains that descriptor and removes only contents reachable through `os.fwalk(".", topdown=False, follow_symlinks=False, dir_fd=prior_fd)`. Each leaf operation uses the yielded directory descriptor; ordinary directories are removed with `rmdir`, and symlinks/files with `unlink`. The replaceable top-level bundle name is never the root of recursive deletion. Before removing that top-level entry, the archive namespace is validated and its current no-follow stat must still match the original bundle inode. A mismatch fails before removal/recreation or ZIP publication.

Exact targeted GREEN command and output:

```text
python3 -m pytest -q backend/tests/test_build_parallel_research_bundle.py -k 'reset_rejects_replacement_directory or rejects_namespace_swaps' --tb=short
.............
13 passed, 35 deselected in 0.31s
```

The full/core successful-reset checks also cover nested old directories, directory/file/dangling symlinks, and preservation of their outside target. This verifies that the descriptor-based cleanup still removes the original working tree without following symlinks.

Final focused verification:

```text
python3 -m pytest -q backend/tests/test_build_parallel_research_bundle.py
48 passed in 0.99s
```

Related archive/ownership verification:

```text
python3 -m pytest -q backend/tests/test_football_external_real_eval_chain_common.py backend/tests/test_run_video_to_analysis_storage_cleanup_bounded_execution.py backend/tests/test_run_video_to_analysis_release_acceptance_archive.py
36 passed in 0.52s
```

`git diff --check` passed. The builder, its existing tests, and this report are the only changed files. Self-review checked classification-to-open identity matching, descriptor lifetime through traversal, bottom-up non-following cleanup, the top-level identity check before removal, and preservation of the previous ZIP on each tested replacement. The post-replace directory-fsync behavior remains unchanged and was explicitly adjudicated permissible under the pre-replace preservation contract. No cloud/provider/smoke/install action or real-data deletion occurred; `.verification/` remains untouched.
