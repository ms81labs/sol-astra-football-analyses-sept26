# Backend quality close-out checkpoint

## Current accepted base and next bounded batch

BQ00 is accepted at `ef714ca0bf839b9d67dc0ea5664ada329b8d6c41`, source tree
`2f3a635ee78d1f87b47e270db536b9284d373baf`. Normal CI `36064523152` completed
successfully: 4,604 complete-backend passes / 18 skips; canonical verification
4,010 backend passes / 18 skips, 100 sidecar passes and 441 frontend passes,
with all remaining canonical gates successful. C05 `36064523157` and C06
`36064523108` also passed on that revision. GPU acceptance stayed skipped.
Do not reapply or reopen its CI-contract, packaging-test or WAL-startup repairs.

This continuation migrates the eight dependencies in `artifact_routes.py` to
`Annotated` without changing handler bodies. Eager annotations intentionally bind
each factory invocation's callback; no global dependency or application state is
introduced. The original complete OpenAPI hash in the unpublished draft depended
on FastAPI-generated validation schemas: 0.128.2 includes input/context properties
not in locked 0.121.0. A readable route-path fixture replaces that version-specific
hash. Pinned validation must additionally compare the complete original and
candidate schemas in the same environment; do not refresh expected data from the
modified implementation.

The 32 new cases cover all eight callback identities/defaults, unchanged OpenAPI
paths, interleaved two-app authorization/overrides, optional generation values,
missing artifacts in a genuinely initialized but unprocessed Storage, and four
fixture/model keyword boundaries. The four fixture keywords were silently ignored:
three ShotAnalytics `onTarget=True` inputs and one MatchConfig `inputMode="video"`.
Only those fixture inputs are removed; model fields and extra-field policy stay
unchanged. The tests-only pre-repair run yields 12 expected failures / 20 passes.

Only eight B008 identities are removed from the Ruff baseline, leaving 496:
235 C901, 175 BLE001 and 86 B008. The existing mypy scope remains zero. Locks,
quality configuration/metadata, scorer pins and all existing suite selections are
unchanged. Local diagnostics use isolated quality tools; exposing sandbox NumPy
stubs instead adds two pre-existing perception array-shape diagnostics, which are
not hidden with source changes or added to the canonical baseline.

The candidate's pinned and final normal-CI receipts are the acceptance authority
for this new batch. Do not infer full-head acceptance from focused tests, this
checkpoint, or a running workflow. Author self-review is not independent review.
The single-use validation workflow must be absent from the final published tree.

## Historical source and acceptance boundary

The resumed CI-contract repair is `d37a9b942378e9039c6f5488165edc4accd01249`.
Its child `0cad959eb1592c5719cfd3f1148068262aa177cc` deliberately aligned the
installed-wheel startup tests with the research-free runtime package. This batch
preserves that change; it does not restore scripts to the installed wheel.

Normal CI run `36058851736` at `0cad959` completed canonical verification:
3,984 backend passes / 18 skips; 100 sidecar passes; 441 frontend passes; lint,
both TypeScript checks, build, startup and production audit all passed. Its
complete-backend lane instead recorded 4,577 passes / 18 skips / one failure.
The result is not full-head acceptance. The retained artifacts bind both results
to source tree `343cc525f24f573a94a2cd8a0abba30239d860c3`.

## BQ00 repair: CI failures must propagate

`d37a9b9` strengthened `test_verify_script.py` without changing workflow commands.
The previous checker assumed `bash -e`, checked only the first logged pipeline,
tracked jobs instead of both quality gates, and exempted steps when `--exit-zero`
appeared even in comments. Fourteen regression cases cover shell precedence,
missing gates, later pipelines, failure masking and additional protected steps.
They produced 12 failures / two passes before repair; the repaired workflow and
quality selection passed 73 cases under both pytest entry points.

The checker runs only bounded shell-option probes with an inert failing producer.
It never executes workflow installers, provider operations or artifact paths.
Unsupported shell/control-flow forms require explicit test review, not exemption.

## BQ00 repair: transient SQLite WAL startup contention

The remaining complete-backend failure was
`test_audit_v2_h04_jobs.py::test_t11_multiple_processes_share_authority_and_respect_leases`.
A spawned child's import of `backend.app.main` opened the shared default Storage;
`PRAGMA journal_mode=WAL` raised `sqlite3.OperationalError: database is locked`.
The entire failed test lasted 2.780 seconds despite the configured 30-second
connection timeout. The same test passed in the separate integration and verifier
lanes. It was not removed, retried by pytest, or given a longer join timeout.

A native SQLite comparison reproduced two immediate SQLITE_BUSY failures in 30
original-code cold concurrent connection attempts; the repaired connector had
zero failures in the same 30-attempt probe. This is a bounded reproduction, not
a guarantee that every SQLite operation is contention-free.

`backend/app/sqlite_connections.py` now owns the shared setup for Storage and
DurableJobLedger. It retries only SQLITE_BUSY-family results from WAL setup,
closes each failed connection before another attempt, and uses one monotonic
30-second budget rather than granting each retry another 30 seconds. It does
not retry transactions, other SQLite errors, unknown error codes, or later
configuration errors. An elapsed budget prevents opening another connection.
Successful connections preserve sqlite3.Row, check_same_thread=False, the
5,000-ms operational busy timeout, and the ledger's foreign-key setting.
Ownership transfers to the caller only after successful setup.

Twenty-two initial failure-injection cases failed on the old implementation;
two additional deadline cases failed before the strict between-retries deadline
check. The final module also exercises genuine simultaneous cold SQLite opens
for both callers and checks database integrity. The final focused suite contains
129 passing cases: new setup regressions, existing schema/multiprocess ledger
regressions, lifecycle checks, quality gates and verifier contracts.

SQLite documents both immediate BUSY responses when invoking a busy handler could
deadlock and transient BUSY during last-WAL-connection cleanup. References:
`https://www.sqlite.org/c3ref/busy_handler.html` and
`https://www.sqlite.org/wal.html`, section 9.

## Verification and publication rules

Local tests used Python 3.13, not the normal CI Python 3.11 profile, and reported
the ultralytics stub. Both recorded diagnostic inventories are unchanged:
Ruff 504, zero added / zero stale; scoped mypy zero. The new shared connector
also passes explicit mypy. Local metadata retains the Python-version mismatch;
no baseline, runtime lock, test selection, football algorithm, HTTP contract,
transaction or schema policy was changed to obtain these results.

The targeted pinned-profile repair run and the final normal CI results must be
inspected before acceptance. Only the final published revision's completed
complete-backend, canonical verification, quality and applicable dedicated lanes
close BQ00. Running jobs, earlier subsets, or a successful canonical verifier
with a failed complete-backend job do not close it. CPU tests do not establish
GPU or model-quality acceptance. Review so far was author self-review, not an
independent reviewer or agent.

The earlier candidate `1de8ea4f3e78aecac3929752914632464dea8c36` restored scripts
packaging but was never published. A concurrent explicit checkout-only command
policy arrived before its publication; that alternative was discarded rather
than overwriting current work. Its passing tests are not current-source evidence.

## Remaining work and exact resume action

BQ00 is closed by the accepted-base evidence above. Resume by inspecting the
normal CI of the revision containing this artifact-route migration. A pending or
failed required lane is not acceptance; diagnose its retained evidence first.
After acceptance, continue with the next dependency group, starting with the
next match-bound group in `backend/app/match_detail_routes.py`. Capture original
OpenAPI/authorization/generation behavior before changing annotations; keep
factory-local dependencies eager and preserve registration order.

BQ01: the initial 108 scoped typing findings were retired by the preceding
continuation, not by this SQLite batch. Other model compatibility policies and
broader runtime typing remain open. A separate read-only local full-app inventory
reports 326 diagnostics across 35 files; it is not the configured CI scope, not
a locked-Python-3.11 baseline, and not comparable to the old 596-error inventory.

BQ02 after this batch: 235 C901, 175 BLE001 and 86 B008 entries remain. No blanket suppressions.
BQ03: root leftover assemblers were split earlier; other routes/domain complexity
remain. BQ04/BQ05: storage and pipeline/CLI responsibility extraction remain.
BQ06: runtime evaluator extraction and a script-free wheel are present; physical
research relocation and supported operational/maintenance command compatibility
still require review. Source/editable commands remain distinct from installed
runtime APIs. BQ07: expanded typing and finding-by-finding final acceptance remain.

Use the existing main integration line, re-read its HEAD before every publication,
and never force-push or overwrite concurrent changes. No new remote branch,
deployment, live-store mutation or paid provider/GPU execution is part of this work.
Any single-use source-transfer machinery must be absent from the final tree.
