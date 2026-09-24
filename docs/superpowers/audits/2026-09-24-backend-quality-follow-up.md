# Backend code-quality follow-up — 24 September 2026

**Continuation:** Current remediation status is recorded in `2026-09-24-backend-quality-continuation.md`. Counts below describe the earlier pass.


## Scope and implementation

Reviewed application source at `20c6a2b5443390414d32d368f3d183abdf15af2a`. Read-only source-audit run `36020617588`, at `d369240219ca487a53ef397d4062f9906a323f91`, captured 1,157 tracked text/source files with a verified SHA-256 manifest and Ruff 0.16.8 results.

The implementation repairs the reproduced benchmark data loss, unused bindings, prompt interpretation, and silent lifecycle cleanup. It adds stricter production linting and check-only Ruff/mypy baselines. Structural and remaining typing debt is explicitly still open. All work uses the existing `main` integration line; there is no additional remote branch, merge, force-push, deployment, live-store operation, or paid GPU/provider execution.

## Reproduced and repaired

### Benchmark metrics

`SelectedClusterBenchmarkSummary` omitted ten fields already supplied by `_selected_cluster_summary_from_benchmark`: accepted match-state frames and coverage; visible, inferred, hidden, controlled, hidden-controlled, and restart/out frames; continuity-applied frames; and mode counts. All ten are now declared with the same types/defaults as `MatchBenchmarkSummary`. Both summary models explicitly forbid undeclared extra fields.

Tests exercise the actual converter, JSON serialization and revalidation, unknown-key rejection, zero defaults, and independent dictionary defaults. Runtime strictness is limited to these two verified contracts, not applied indiscriminately to historical payload models. The new contract/prompt regressions produced 17 failures and one pass before the fix; the new tests plus existing benchmark/prompt tests then passed 55 cases locally.

### Prompt direction

The supplied review overstated the omission: the legacy prompts already included `attackDirection` in JSON, and the approved-evidence branch already stated the direction. The unused `direction_context` additionally explained increasing/decreasing x and the opponent's opposite direction. That explanation now reaches both legacy prompt types. Approved-evidence behavior is unchanged.

### Unused variables without deleting required work

Removed unused processor output unpacking, the report's unused `has_drills` flag, and the identified storage/script/test bindings. Kept `ReviewService.materialize_and_publish`, `get_match`, `plan_recompute`, fixture setup, and the required JSON load: these publish artifacts or validate preconditions. Removing those calls would change behavior.

The C05 imported pytest fixture is now an explicit re-export, not deleted. Earlier compatibility re-exports and script module entry points remain intact.

### Cleanup observability and exception intent

Sixteen broad pass-only handlers in `app/` now emit fixed-message warnings covering provider cleanup/confirmation, download/artifact stream closing, progress delivery, atomic JSON rollback, storage checkpoint/rollback, admission connection cleanup, and ledger rollback. Warnings include neither raw exception values nor tracebacks, transport payloads, credentials, or inline artifacts. Existing retry counts, cleanup outcomes, callback handling, and primary exception identity are covered by failure-injection tests.

Four B904 sites now express deliberate chaining or suppression. Generation recovery and missing explicit playlist generations use `from exc`. Invalid-hostname validation and the original failed SDK create use `from None` to suppress incidental secondary context. Python already retained implicit context before these changes; the review's claim that it was simply lost was inaccurate.

The tests check uncertain cleanup outcomes, successfully materialized bytes, retained progress, original failures, and secret-safe logs. All 136 existing Daytona fake-client tests passed locally. This is not live-provider acceptance.

### SHA-1

Stable event identifiers now explicitly use `usedforsecurity=False` with identical digest bytes. The evaluator's separate SHA-1 operation checks Git blob object IDs against pinned scorer source; it participates in source-integrity admission and is deliberately unchanged. No weakened scorer verification or hash migration is included.

## Quality measurement and enforcement

The old CI claim was partly stale: main already gated F401 in app/scripts and script hygiene, in addition to F821/F822/F823. All those checks remain. A new zero-debt production gate covers all `F`, `S110`, and `B904` in app/scripts.

The original expanded Ruff inventory contained 626 diagnostics, including four UP045 findings from an auxiliary inventory rule. Under the comparable requested rules, the total fell from 622 to **581**, eliminating **41** diagnostics. The remaining baseline is explicit: C901 228; BLE001 175; B008 94; B905 31; F401 31; B017 17; B009 2; S110 2; F541 1. The two remaining S110 sites are in `run_guerilla.py`, outside the clean app/scripts gate.

Pinned mypy 2.3.1 with Pydantic 2.13.5, under the new Python 3.11 configuration, records **108 diagnostics in 17 files**. The scope is workbench, schemas, settings, and the benchmark module. This is not an apples-to-apples reduction from the supplied 596/53 figure: that result's exact configuration/environment was not supplied, and full-app strict typing is not claimed. Missing third-party stubs and dynamic mappings still limit coverage.

`backend/quality/*-baseline.json` records tool/configuration identity and exact diagnostic paths, enclosing scopes, source anchors, messages, and occurrence counts. CI fails on additions, stale entries, incompatible metadata, invalid output, and tool failures. CI never regenerates baselines. The Pydantic plugin was exercised with a real misspelled constructor-field canary, which correctly failed with `call-arg`.

The typing tools have an isolated, hash-locked Python 3.11 Linux requirements profile. Runtime dependency locks are unchanged. A baseline is a no-new-debt gate, not closure of the retained findings.

## Structural assessment and open work

The original inventory confirms app: 125 files / 41,442 lines; scripts: 322 / 116,395; tests: 380 / 108,244; and `run_guerilla.py`: 8,938 lines. Additional Python files elsewhere in backend are outside those four subtotals.

The AST import scan found 213 local import statements and three strongly connected groups of 17, two, and two app modules when lazy runtime imports are included. Excluding function-local and TYPE_CHECKING edges, it found no import-time cycle. This is static evidence, not a guarantee about dynamic imports or justification for moving every local import to module scope.

Large route factories, storage responsibilities, analytical branches, and `run_guerilla.py` remain maintainability debt. Factory complexity includes nested handlers. Their extraction needs route/auth/OpenAPI equivalence tests and two-app isolation checks; replacing per-app closures with mutable global routers merely to reduce a score is not an acceptable shortcut. Preserve the Storage facade and generation boundaries during extraction.

Do not exclude or relocate all scripts from packaging yet. `app/evaluation_verifier.py` imports runtime symbols from `backend.scripts.validate_football_analysis_pilot_labels` and `backend.scripts.evaluate_football_analysis_pilot` at three sites. First extract shared runtime evaluator/validator utilities, preserve command wrappers, and verify installed-wheel evaluation outside the source tree. Then relocate and exclude research-only scripts with CLI/release compatibility tests.

Remaining work is therefore explicit: reduce retained mypy/BLE/B/C901 debt; perform characterization-backed route/storage/pipeline extraction; separate runtime evaluator utilities before research packaging changes; and review other Pydantic contracts for compatible strictness.

## Verification and publication evidence

Local preflight used Python 3.13 / Pydantic 2.13.4 with the repository's `ultralytics` test stub. Completed batches include 55 benchmark/prompt tests, 345 storage/runtime/remote-contract tests, 136 Daytona tests, and 11 quality-gate tests. These overlap and must not be summed as unique coverage. The combined new-regression/Daytona batch passed 176 cases; a final run of all three new regression modules passed **40 cases**. A separate locally time-limited pipeline run is not counted as passing.

Detached implementation candidate: `1d99f9e835446edfd5fe68e5534fc44fa89658c3`, parent `4ba5d487e4cadd50ff4995f11d7aa3f216e2c9ea`. All 31 candidate file blobs were checked against the locally reviewed contents. Candidate workflow `36024815707` rechecked both locked quality baselines and runs complete CPU backend and canonical code-only verification on that exact candidate. Candidate artifact `10818423181` binds the commit, tree, paths, and blobs.

The publication commit retains those implementation bytes and adds the reviewed CI workflow while removing the temporary source-audit/repair workflow. The workflow write is performed through the authorized GitHub connector, separately from the Actions token's content-only candidate creation. The temporary workflow therefore existed in the implementation candidate but is absent from the published tree.

Final acceptance is the published commit's normal GitHub Actions results and retained complete-backend/verify/quality evidence. Do not infer final-head success from the earlier local batches or a running workflow. This document records implementation and evidence locations; the source-bound CI receipts record the completed acceptance result. CPU verification does not imply GPU/model-quality acceptance.
