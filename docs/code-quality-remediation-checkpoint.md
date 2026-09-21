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

