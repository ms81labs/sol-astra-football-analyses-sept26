# BQ01 numeric typing / BQ03 required upload — 25 September 2026

Accepted parent: `df85fb95ac2e276e4cc32dbb07f13747f081cb3b` (tree `0459dd443f80ffd97d5914b0eb37a86ee1a24869`). Parent CI `36076462690` completed with 4,857 full-backend passes / 18 skips and 4,263 canonical backend passes / 18 skips. Do not reapply the 85 match-bound or eight artifact dependency migrations, or the SQLite WAL repair.

This bounded continuation applies the retained five-file numeric/cancellation typing patch without changing its source bytes. The exact builtin-number predicate still excludes bool and subclasses; each reader keeps its own availability/finiteness policy. `CancellationChargeView` preserves unknown incurred amounts as `None`, not zero. The same explicit five-route-module mypy command must move from four diagnostics to zero; the established scoped gate remains zero.

The required multipart upload is handled separately: name the `File(...)` marker **inside each router factory**, then use the same marker as the function default. This preserves parameter order, positional and keyword direct calls, the Python File default, HTTP requiredness, and independent marker ownership across applications. Converting it into a keyword-only or reordered required argument, or introducing a shared module-level mutable marker, would change compatibility; neither is done. The handler body is unchanged. Twelve characterization cases exercise signature/defaults, independent markers, required multipart schema, rejected missing/non-file inputs with no admission, exact persisted bytes/idempotent replay, and positional/keyword direct calls.

Exactly the final B008 identity is retired. The wider Ruff baseline now has 410 entries (235 C901, 175 BLE001), no B008 and no added diagnostic identities or configuration/lock changes. Zero B008 is enforced by the existing broader exact-baseline gate, without a blanket suppression. The 57 numeric/cancellation cases and 12 upload cases must pass against original and modified source. Supplemental local tests do not replace pinned acceptance.

## Acceptance and resume

Pinned preflight must install the unchanged dev and isolated quality locks under Python 3.11, reproduce the four type diagnostics plus one upload B008, compare full original/modified OpenAPI documents, pass the broader numeric/admission selection and both pytest entry points, and check exact Ruff/mypy metadata. Final acceptance additionally requires all normal CI lanes plus C05/C06 on the actually published commit, not the parent or this document.

Review is author self-review, not independent approval. CPU stubs and skipped GPU acceptance are not model-quality verification. No new remote branch, force push, live data mutation, deployment, paid provider call or GPU execution is part of this work. Any temporary preflight workflow is removed in the final tree.

Exact next action: inspect the published head's completed CI and retain source-bound evidence. After acceptance, continue BQ03 by extracting route-factory responsibilities behind the existing contract/isolation tests, or resolve the recorded typing/exception debt in bounded batches. BQ03 structural extraction, broader typing, Pydantic compatibility, storage/pipeline refactors and research/operational-command separation remain open. Do not redo completed declaration-only migrations.

---

# BQ03 remaining match dependencies — 25 September 2026

## Current bounded scope

Parent production source: `5c6570e3202f031cf5691066b8ac5ca0f363d489` (47 match-detail dependencies). Its pinned preflight is run `36074041909`; normal acceptance is run `36074390891`. Consult the completed, source-bound receipts rather than inferring acceptance from this checkpoint.

This continuation migrates 38 `match` dependency declarations in `insight_routes.py` (1), `job_routes.py` (2), `match_runtime_routes.py` (9), `review_routes.py` (7), and `workbench/leftover_match_routes.py` (19). All corresponding handler bodies and decorators remain unchanged. Each factory retains its own dependency callback and storage binding. The standalone required multipart upload marker is intentionally unchanged.

The new 99-case suite covers local callback identity, all 38 routes' access denial and interleaved two-app dependency overrides, five original route-contract fixtures, and successful/missing-data/default-value paths. Locally it produced 38 expected annotation-metadata failures and 61 behavior passes against unmodified production, then 99 passes after migration. Pinned validation must repeat the full cycle and compare complete test-app OpenAPI documents before publication.

Exactly 38 matching B008 identities are removed from the existing Ruff baseline. The remaining total is 411 (235 C901, 175 BLE001, 1 B008). Existing tool/configuration metadata and the scoped mypy baseline are unchanged. The scoped mypy gate remains zero; separately checking these five files reports four pre-existing typing diagnostics locally, unchanged before and after this patch. Do not suppress them or mislabel the expanded scope as clean.

## Verification qualifications

The sandbox runtime is Python 3.13.5 / AnyIO 4.13.0 / FastAPI 0.128.2 / Pydantic 2.13.4, not the pinned acceptance profile. A broader supplemental run completed 212 passes and one failure in `test_workbench_concurrent_requests_do_not_change_factual_measurements`: local AnyIO lacks `gather`. The unchanged original source fails in the same place. This local failure is retained; no shim or test exclusion is part of this repair. CI uses the unchanged AnyIO 4.15.1 lock and must run the original concurrency test successfully.

Published acceptance requires the normal complete-backend, canonical verify, quality, integration, generated-media, excluded-backend and profile checks plus C05/C06 on the final source. CPU stubs do not establish GPU/model-quality acceptance. Review is author self-review, not an independent review.

## Exact next action

Inspect and retain the final published source's completed normal CI results. Then address the one required upload B008 separately without silently changing requiredness, body shape, callable compatibility or defaults. BQ03 structural route extraction, broader typing, exception boundary review, storage/pipeline refactors and research-command separation remain open. Do not redo the completed 8 artifact / 47 match-detail migrations or the SQLite WAL repair.

---

# Backend quality close-out checkpoint

## Match-detail dependency continuation — 25 September 2026

The artifact-route batch is accepted at `2d8cf998b39c67a34e4cff88f68f81d758cb203c`
(tree `5daa12d8aafc62660ffa619bb0ab3bfcbf68ef8b`). Its normal CI `36070192303`
completed with 4,636 complete-backend passes / 18 skips, 4,042 canonical backend
passes / 18 skips, 100 sidecar passes, 441 frontend passes, and all other canonical
gates successful. Integration was 360 passed / 15 skipped; generated media 23
passed / 4 skipped. C05 `36070192457` and C06 `36070192275` also passed. The GPU
lane stayed intentionally skipped. Do not reapply the artifact batch.

This next bounded batch changes exactly 47 match-bound dependency declarations in
`backend/app/match_detail_routes.py` to eager `Annotated` metadata. The factory,
callback identity, handler bodies, registration order, defaults, storage/snapshot
operations and provider policy remain unchanged. Removing postponed annotations
is intentional: each invocation must retain its own callback in runtime metadata,
not resolve a factory-local name from module globals. No global state is added.

The 122 new cases pin 47 callback bindings and 75 behavioral/contract cases:
authorization and overrides for all routes, interleaved application instances,
optional generations, omitted versus empty request bodies, existing falsy defaults,
render argument conversion, local geometry bypass and provider denial. The path
fixture came from unchanged source. Pinned validation must compare the full original
and modified test-application OpenAPI documents, not refresh expectations from the
candidate. Tests-only RED must produce exactly 47 named metadata failures and
75 passes; focused GREEN 258 passes and console pytest 122 passes.

Only the 47 corresponding B008 identities are retired; Ruff is 449 (235 C901,
175 BLE001, 39 B008). All baseline metadata, existing mypy scope, locks, scorer pins,
HTTP contracts and test selections remain unchanged. Scoped and explicit
match-detail mypy must both remain zero. This does not close the wider BQ03 route
extraction or full-application typing effort.

Acceptance is this batch's completed pinned validation and final published-head
normal CI, not this checkpoint or the accepted parent's results. No new remote
branch, force push, deployment, live-store mutation or paid provider/GPU execution
is authorized by this continuation. Any temporary validation workflow is removed
from the final source tree. Review is author self-review, not an independent agent.

Exact resume action: inspect normal CI on the revision containing this 47-dependency
migration. After all applicable lanes complete successfully, continue the remaining
39 B008 declarations by module with original-contract tests. Do not redo BQ00 or
the eight artifact dependencies. BQ01 broader typing/contracts, BQ02 exception and
complexity work, BQ03 structural extraction, BQ04/BQ05 storage and pipeline work,
BQ06 research/command separation and BQ07 final closure remain open.

The older sections below retain history; the current counts and resume instruction
in this section supersede older current-batch paragraphs.

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
