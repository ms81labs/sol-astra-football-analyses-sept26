# Code Quality Remediation — Resume Checkpoint

This file is the durable resume point for the rebuilt backend code-quality audit.
If a chat/session is refreshed, **read this file and current git/CI state before changing code**.

## Authority and scope

- Repository: `ms81labs/sol-astra-football-analyses-sept26`
- Scope: backend code quality only; no football-analysis/product-direction changes.
- Preserve endpoint contracts, filesystem/rollback safety, uncertainty semantics, and hash-locked dependency discipline.
- Work directly on `main` as explicitly requested by the user.
- Batch multi-file changes into one Git commit/ref update where practical to avoid a CI/email storm.
- Evidence before completion claims: final head must have fresh verification.

## Completed / materially addressed audit findings

- C01: masked decoder `Path` defect + permissive regression fixed.
- C02/C0C: excluded-suite failures repaired; all six code-only exclusions have an automatic CI home.
- C03: wrapped predictor capability check fixed.
- H02: leftover routers no longer use `backend.app.main` as a dynamic symbol namespace.
- H05: duplicate `MatchBenchmarkSummary` fields removed.
- H07: degraded operational states now log safe context at targeted suppression sites.
- H08 / PR2: pinned Ruff correctness gate added; RUF100/B023 debt reporting added.
- M01/M02: stale-noqa/B023 targeted debt cleared.
- M03/M04: verifier selection centralized and human pytest-summary parsing removed from the contract.
- M05/M06: dependency drift checking and real CV import smoke added.
- M07/M10: normalization/private-helper coupling reduced; regular-file helper moved to its true owner.
- H06: reopened during final closure after stale code search missed script bootstraps. A repo-wide AST regression now scans every `backend/scripts/*.py` for `sys.path.insert/append` and local `_utc_now_iso`; H06 closes only when that gate is green.
- M08: **intentionally retained**. Numerous tests explicitly assert 410 `ROUTE_RETIRED` compatibility; deletion would be a contract change.
- M09: **no forced split**. Large tests already use shared fixtures/helpers; splitting by file size alone would be cosmetic.

## Structural progress

- H01 FastAPI composition:
  - `main.py` reduced from ~2,355 lines / ~105 routes to ~637 lines and no ordinary inline API route implementations.
  - route families extracted to native `APIRouter` modules including jobs, match detail, review, insight, artifact/report, system, match runtime, and match ingest.
- H03 Storage:
  - public `Storage` facade preserved.
  - job/admission, review, correction-log, and remote-result rollback persistence extracted behind focused components/mixins.
  - `storage.py` reduced from ~3,436 to ~2,638 lines before the latest checkpoint.
- H04 benchmark summarization:
  - duplicate fields removed.
  - accepted-state, ball-truth, recovery/proposal, and remote-runtime diagnostics extracted.
  - `summarize_match_benchmark()` reduced from ~1,003 to ~446 lines while retaining one final summary assembly point.

## Current head before this checkpoint commit

`33e33aeac979a10b46d32dc5cdab93629ec6dc06`
(`CQA H03/M10: move regular-file helper to true owner`)

At that head:
- python-quality: green
- api-profile: green
- excluded-backend: green
- macOS profile: green
- integration: red
- real-media: red
- canonical verify: still running when inspected

The integration/real-media failures share one H04 regression:
`long_gap_treatment_outcome` (and its sibling controlled-possession outcome) lost their `None` defaults when the remote-runtime initialization block was extracted.
This checkpoint batch restores those defaults.

## Resume algorithm

1. Read this file.
2. Get current `main` HEAD and recent commit messages.
3. Inspect the latest CI run jobs for current HEAD.
4. If any lane is red, pull exact logs and fix the root cause first.
5. Re-scan the finding register; do not redo items above unless regression evidence says they reopened.
6. Continue only with genuinely open structural work or final verification.
7. Before saying “done”, require current-head green evidence for:
   - python-quality
   - api-profile
   - integration
   - real-media
   - excluded-backend
   - canonical verify
   - relevant profile jobs
8. Do a final audit-register pass and self-review/fresh review before closure.

## Ponytail rulings

- Do not split files only to reduce LOC.
- Do not create a dependency container/controller framework to replace native FastAPI composition.
- Do not remove hardened filesystem, rollback, fsync, bounded-read, or fail-closed behavior for simplicity.
- M08 stays until compatibility tests/callers are intentionally retired.
- M09 stays unless concrete duplicated setup is found.


## Resume update — 2026-09-21 after `6f846f3`

Current observed head before this repair: `6f846f371736f6c659bfcd69db3a399588cc9b28`.

That CI run failed for one shared root cause plus targeted F401 cleanup:
- canonical verify / integration / real-media all failed during collection because
  `backend/tests/test_audit_v2_h03_calibration.py` intentionally imports
  `_dashboard_average` from `backend.app.main`;
- targeted `main.py` F401 found three genuinely dead imports:
  `StaleGeneration`, `GenerationRecoveryRequired`, and `deployment_mode`.

Ruling:
- retain `_dashboard_average` as an explicit compatibility export pointing at
  `insight_routes._dashboard_average`;
- remove the three truly dead imports;
- do not restore the historical broad import surface.

After this repair, the next action is **CI verification only**. Do not start a new
structural refactor unless the final-head lanes are green and the finding register
shows a concrete remaining issue.


## Resume update — final cleanup after `0eb9258`

The compatibility-export repair on `0eb9258` restored
`backend.app.main._dashboard_average` explicitly and removed the remaining dead
top-level imports. During final Ponytail review, three private ingest constants
(`_IDEMPOTENCY_KEY`, `_DISPATCH_FAILED`, `_DISPATCH_UNCERTAIN`) were found
stranded in `main.py` after ingest routing moved to `match_ingest_routes.py`.
They and the now-unused `re` import are removed in the next commit.

Next action after a fresh resume: inspect the latest HEAD CI only. No new structural
refactor is planned unless a red lane or final register check provides concrete
evidence.


## Resume update — H06 script hygiene safeguard

Base head: `bfcfb9af0708d2b4361e981a1dc8e0ad251ad92f`.

Direct source inspection disproved the stale zero-bootstrap claim. Confirmed offenders:
- `backend/scripts/run_source_robustness_batch.py`
- `backend/scripts/football_external_real_eval_chain_common.py`

Both used `sys` only for repo-root `sys.path` bootstrapping. The robustness regression imports the former as a package module, and the common helper has no CLI entrypoint.

This batch:
- removes both known bootstraps;
- adds `backend/tests/test_script_hygiene.py`, which AST-scans all Python files directly under `backend/scripts`;
- fails with every offending filename/line if any `sys.path.insert/append` or local `_utc_now_iso` remains.

Resume rule: inspect the latest HEAD CI first. If `test_script_hygiene.py` fails, fix every path reported before any other work. Do not trust GitHub code-search counts for H06.


## Resume update — dashboard compatibility sibling

Inherited integration evidence from `bfcfb9a` showed one remaining compatibility import:
`backend/tests/test_audit_v3_c02_ui_contract.py` imports both
`_dashboard_average` and `_dashboard_difference` from `backend.app.main`.

Ruling:
- retain both names as explicit aliases to their implementations in `insight_routes`;
- do not restore any other legacy `main.py` import surface.

After this commit, priorities remain: H06 hygiene gate first, then exact current-head CI closure.


## Resume update — fast H06 gate

The script-hygiene AST regression now also runs directly in the `python-quality` job via:
`python backend/tests/test_script_hygiene.py`.

This keeps H06 failures in the fast lane instead of waiting for the full canonical verifier.


## Resume update — H06 bulk consolidation checkpoint

Bulk H06 codemod is being applied from the authoritative python-quality offender list:
- total violations: 477
- unique offending scripts: 297
- `sys.path.insert/append`: 297
- local `_utc_now_iso`: 180

Progress persisted in this commit:
- scripts with unique-offender indexes `0..83` have been rewritten;
- next index is `84`;
- transform removes only actual `sys.path.insert/append` bootstrap statements;
- canonical `_utc_now_iso() -> datetime.now(timezone.utc).isoformat()` definitions are replaced by the existing shared `football_external_real_eval_chain_common.utc_now_iso` helper;
- noncanonical helper bodies are not silently rewritten.

Resume algorithm:
1. inspect current HEAD CI;
2. fetch python-quality job log from the H06 gate if needed;
3. derive the ordered unique offender list from that log;
4. continue from offender index 84;
5. after all 297 scripts are transformed, require the fast Script hygiene gate to pass before closure.

## Resume update — H06 bulk consolidation checkpoint #2

Base durable checkpoint was `e8cc02fc54c91ee1983259eeb4eabcf0ea1f39a8`.

Authoritative fast-gate remainder at that checkpoint:
- remaining offending scripts: 213
- these correspond to original offender indexes `84..296`

Progress persisted in this commit:
- original unique-offender indexes `0..147` are now rewritten and durable;
- newly completed in this tranche: original indexes `84..147` (64 scripts);
- next original offender index: `148`;
- remaining scripts after this checkpoint: 149.

Transform remains guarded:
- remove only actual `sys.path.insert/append` bootstrap statements (and their empty guard);
- remove `import sys` only when no other `sys.*` use remains;
- replace only canonical local `_utc_now_iso() -> datetime.now(timezone.utc).isoformat()` with
  `football_external_real_eval_chain_common.utc_now_iso as _utc_now_iso`;
- noncanonical UTC helper bodies must be left for manual review, never silently rewritten.

Resume algorithm:
1. inspect current HEAD and this checkpoint;
2. use the python-quality script-hygiene gate as authority;
3. continue from original offender index `148` (equivalently remainder offset `64`);
4. do not redo `0..147`;
5. after the final offender is transformed, require the fast H06 gate green before audit closure.

## Resume update — H06 bulk consolidation checkpoint #3

Progress persisted in this commit:
- original unique-offender indexes `0..211` are now rewritten and durable;
- newly completed in this tranche: original indexes `148..211` (64 scripts);
- next original offender index: `212`;
- remaining scripts: 85.

The same guarded transform remains in force. On resume, do not redo `0..211`.
Continue from original index `212` (equivalently authoritative remainder offset `128`),
then require the fast python-quality script-hygiene gate to report zero offenders.

## Resume update — H06 bulk consolidation checkpoint #4

Progress persisted in this commit:
- original unique-offender indexes `0..251` are now rewritten and durable;
- newly completed in this tranche: original indexes `212..251` (40 scripts);
- next original offender index: `252`;
- remaining scripts: 45.

Resume from original index `252` only. After the final 45 are transformed,
run the fast python-quality script-hygiene gate and treat its output as authoritative.

## Resume update — H06 transformation complete

All original H06 unique-offender indexes `0..296` (297 scripts) have now been transformed.

The authoritative source that originally reported the debt had:
- 297 scripts with `sys.path.insert/append`;
- 180 canonical local `_utc_now_iso` copies;
- 477 total violations.

State after this commit:
- transformation phase: complete;
- next action: **verification only**;
- run/inspect the fast `python-quality` job and its `test_script_hygiene.py` gate;
- if the gate reports any offender, fix exactly the reported residuals;
- do not restart the bulk codemod or redo already transformed scripts.

H06 is not declared closed until the fast hygiene gate is green on this exact head.


## Resume update — H06 verified; canonical verifier regression repair

Exact H06 completion head: `99cfbd4ae85884064d24d4370eaea27bbe973546`.

Fresh CI evidence on that head:
- `python-quality`: green;
- `Script hygiene gate`: green;
- integration / real-media / api-profile / macOS / excluded-backend: green;
- canonical `verify`: red with 16 failures.

Therefore H06's dedicated acceptance criterion is satisfied: all 297 unique script offenders
(477 original violations: 297 `sys.path` bootstraps + 180 canonical local UTC helpers)
are transformed and the repo-wide AST regression is green.

The canonical verifier failures are separate structural-extraction regressions. Root causes identified:
1. `match_ingest_routes._IDEMPOTENCY_KEY` was written as a raw pattern ending in
   `\\\\Z`, matching a literal backslash-Z instead of the regex end anchor; valid caller
   tokens were rejected with HTTP 400 before upload/admission.
2. `test_t24_every_frontend_api_path_resolves_with_default_flags` still hard-coded the
   pre-H01 endpoint module allowlist, so routes correctly moved to new `APIRouter` modules
   were reported as unresolved.
3. `test_remote_worker` still asserted private `_REMOTE_RESULT_FILENAMES` through
   `storage.py` after H03 moved that private constant to its true owner,
   `storage_remote.py`.

This repair changes only those three roots. Next action: inspect CI on the new head; do not
restart H06 or begin another structural refactor while any current-head lane is red.

## Resume update — H03 calibration seam

Base head `d0a655bed8c18dc1d038f89f34e8598cdfe373ae` completed all applicable CI lanes green before this refactor.

H03 next cohesive extraction:
- calibration preview/commit workflow;
- calibration evaluation persistence;
- calibration revision load/save/migration helpers.

The public `Storage` facade is preserved via `_CalibrationStorageMixin` in
`backend/app/storage_calibration.py`. Eleven existing methods move without behavior changes.
A focused AST seam regression asserts those methods no longer live in `Storage` and remain
owned by the calibration mixin.

Next action: inspect CI on the new head. If any lane is red, debug that exact regression before
starting another H03 extraction.

## Resume update — H03 identity state seam

Base head `7e2e374efe35f5c1b101d43912f333c526af4db0` completed all applicable CI lanes green, and the separate C06 media workflow was green, before this refactor.

The next H03 extraction moves only the undeco­rated identity state/mutation cluster behind
`_IdentityStorageMixin` in `backend/app/storage_identity.py`:
- identity eligibility / continuity helpers;
- stored calibration eligibility helper used by identity-sensitive views;
- repair and promotion commands;
- identity continuity recomputation;
- track edit application;
- physical-metric invalidation after identity discontinuity.

`heatmap_for_match` and `identity_for_match` deliberately remain in `Storage` because they use
the local `_generation_reader` decorator; moving them would require an unnecessary decorator-module refactor.
A focused AST seam regression prevents the eight extracted methods from drifting back into `Storage`.

Next action: inspect CI on this head. If any lane is red, debug that exact regression before another H03 extraction.

## Final closure checkpoint — 2026-09-21

Verified code head before this docs-only closure commit:
`c64fb87a671d88275d29991e488dad68314b72e0` (`CQA H03: extract identity state seam`).

Fresh verification on CI run 610:
- python-quality: green;
- api-profile: green;
- integration: green;
- real-media: green;
- excluded-backend: green;
- macOS profile: green;
- canonical verify: green;
- GPU acceptance: skipped as expected for a normal push.

Separate C06 media execution-evidence workflow run 11: green.

### H03 closure ruling

H03 is materially addressed and closed for this remediation program.
The audit required preserving the public `Storage` API and extracting cohesive seams incrementally,
not a repository-pattern rewrite. The resulting facade now delegates to focused seams for:
- job/admission persistence;
- review persistence;
- correction-log persistence;
- remote-result publication/rollback;
- calibration state/revisions;
- identity state/mutations.

Current structural evidence at `c64fb87a671d88275d29991e488dad68314b72e0`:
- `backend/app/storage.py`: 2,035 total lines, ~1,888 lines from `class Storage` onward;
- audit baseline: ~3,140-line `Storage` class;
- public facade preserved;
- latest calibration and identity method bodies were byte-identical to their preceding green heads;
- focused seam regressions protect job, review, calibration, and identity ownership boundaries.

Further extraction is intentionally not part of this closure because the remaining surface is dominated by
core filesystem/generation persistence and domain-facing read/assembly methods; another split without a
clear responsibility boundary would be LOC-driven rather than evidence-driven.

### Final register disposition

Closed / materially addressed:
C01, C02, C03, H01, H02, H03, H04, H05, H06, H07, H08,
M01, M02, M03, M04, M05, M06, M07, M10.

Intentionally retained with explicit rulings:
- M08: retired/compatibility routes remain because tests assert 410 `ROUTE_RETIRED` behavior; deletion would change a public compatibility contract.
- M09: no forced test-file split because no concrete duplicated setup justified a cosmetic reorganization.

Positive properties preserved:
- hardened filesystem / rollback semantics;
- hash-locked dependency profiles;
- explicit uncertainty contracts;
- extensive regression coverage, now with improved execution topology.

### Final structural snapshot

- `backend/app/main.py`: 399 lines, zero inline `@app.<method>` route decorators;
- `backend/app/run_benchmarks.py::summarize_match_benchmark`: ~448 lines, down from ~1,003;
- `backend/app/storage.py`: 2,035 lines, with focused mixin/component seams;
- `backend/tests/test_script_hygiene.py`: repo-wide AST guard for H06 bootstrap/UTC-helper regressions;
- CI has automatic homes for the formerly excluded backend tests.

No further code-quality refactor is queued by this audit. Reopen a finding only on new regression evidence
or an explicitly approved contract/product change.
