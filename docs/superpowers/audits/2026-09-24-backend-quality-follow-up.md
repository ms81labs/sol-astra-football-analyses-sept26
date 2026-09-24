# Backend code-quality follow-up — 24 September 2026

## Source and decision

Reviewed application source at `20c6a2b5443390414d32d368f3d183abdf15af2a`. The read-only source-audit commit was `d369240219ca487a53ef397d4062f9906a323f91`; audit run `36020617588` captured 1,157 tracked text/source files with SHA-256 manifest verification and Ruff 0.16.8 results. Production repairs remain on the single existing integration line. No deployment, live-store modification, provider invocation, or paid GPU run is part of this work.

The supplied review identified a real data-loss defect. Several other findings were accurate but needed qualification before editing. This pass repairs the verified contract, unused-binding, and lifecycle-observability defects and introduces enforceable quality ratchets. It does **not** claim that all typing or structural debt has disappeared.

## Verified and repaired

### Selected-cluster match-state metrics

`SelectedClusterBenchmarkSummary` omitted ten fields already supplied by `_selected_cluster_summary_from_benchmark`. They are now declared with the same types/defaults as `MatchBenchmarkSummary`. Both benchmark summary contracts forbid undeclared fields. Existing historical payloads missing the new optional/defaulted fields remain valid; unknown extra keys are intentionally rejected for these two contracts only.

Tests exercise every metric through the actual conversion and JSON round-trip, typo rejection, zero defaults, and independent mutable dictionaries. Before the fix, the contract/prompt regressions produced 17 failures and one pass; afterwards the new tests plus existing benchmark/prompt tests produced 55 passes locally.

### Prompt direction

The original audit overstated the omission: both legacy prompts already included `attackDirection` in JSON, and the approved-evidence prompt already stated the direction. The unused `direction_context` additionally explained increasing/decreasing x and the opponent's opposite direction. That explanation now reaches both legacy prompt types. The approved-evidence branch is unchanged.

### Unused variables without deleting required work

Removed unused processor result unpacking, the report's unused `has_drills` flag, and the identified unused storage/script bindings. Kept `ReviewService.materialize_and_publish`, `get_match`, `plan_recompute`, fixture setup, and the required JSON load. Those calls publish artifacts or validate preconditions; deleting them merely because their return values were unused would be a behavior regression.

The C05 imported pytest fixture is now an explicit re-export, not deleted. Earlier compatibility re-exports and module entry points are preserved.

### Cleanup observability and exception chaining

Sixteen broad pass-only handlers in `app/` now emit fixed-message warnings covering provider cleanup/confirmation, download and artifact stream closing, progress delivery, atomic JSON rollback, storage checkpoint/rollback, admission connection cleanup, and ledger rollback. Messages contain neither raw exception values nor tracebacks, transport payloads, credentials, or inline artifacts. Existing retries, callback behavior, absence confirmation, indeterminate outcomes, and propagation remain unchanged.

The four reported B904 sites now make intent explicit: generation recovery and missing explicit playlist generations retain a cause with `from exc`; invalid hostname validation and the original failed SDK create deliberately suppress incidental secondary context with `from None`. Python already retained implicit exception context before these changes; the original report's claim that it was simply lost was inaccurate.

Failure-injection tests verify primary-error identity, retry counts, uncertain cleanup outcomes, successfully materialized bytes, progress retention, and secret-safe logs. All 136 existing Daytona fake-client tests passed locally after the changes.

### SHA-1

Stable event identifiers explicitly use `usedforsecurity=False` and retain identical digest bytes. The evaluator's separate SHA-1 operation checks Git blob object IDs against pinned scorer source. It participates in source-integrity admission, not just an incidental display identifier; it is deliberately unchanged. No weakened scorer verification or hash migration is bundled into this cleanup.

## Tooling verification and new enforcement

The old CI claim was partly stale. In addition to F821/F822/F823, current main already gated F401 in app/scripts and script hygiene. Those gates remain. The new clean production gate covers all `F` plus `S110` and `B904` in app/scripts. Expanded Ruff and scoped mypy use explicit diagnostic baselines rather than whole-file ignores or an `--exit-zero` success shortcut.

The original expanded Ruff measurement found 626 diagnostics: C901 228, BLE001 175, B008 94, F401 32, B905 31, S110 18, B017 17, F841 15, F811 5, B904 4, UP045 4, B009 2, F541 1. The new baseline omits UP045, which was an extra inventory rule outside the requested rollout, and records the actual post-repair output. Exact versions, configuration identity, paths, source anchors and messages are in `backend/quality/*-baseline.json`.

The supplied “596 errors in 53 files” cannot be treated as a reproducible current result without its mypy version/configuration/environment. This pass introduces a pinned Python 3.11 mypy/Pydantic configuration and records its own measured diagnostics. The starting scope includes the requested workbench/schemas/settings plus the benchmark module that contained the concrete bug. It is not a claim of full-app strict typing. Missing third-party stubs and dynamic mappings still limit static coverage.

The gate's tests verify new errors, duplicate occurrences, stale entries, line movement, function identity, invalid diagnostic output and tool failure. Baseline generation is an explicit maintainer operation; CI only checks. Runtime dependency locks are untouched.

## Structure: confirmed debt, not blindly rewritten

The source inventory confirms 125 app Python files / 41,442 lines; 322 scripts / 116,395 lines; 380 tests / 108,244 lines; and 8,938 lines in `run_guerilla.py`. Additional Python files elsewhere in `backend/` are not included in those four subtotals.

An AST import graph found 213 local import statements. With lazy runtime imports included, it found strongly connected groups of 17, two, and two app modules. Excluding function-local and TYPE_CHECKING edges, it found **no import-time cycle**. This is static evidence, not a guarantee about dynamic imports or a reason to move every lazy import to module scope.

Large closure-based route factories, remaining storage responsibilities, analytical branches and `run_guerilla.py` remain maintainability debt. Their aggregate complexity includes nested handlers; moving them to module-level mutable routers merely to reduce a score can break per-app isolation. Remaining work requires endpoint-level ownership, characterization tests for route/auth/OpenAPI equivalence, two-app isolation, and incremental extraction preserving the Storage facade and generation boundaries.

Do not exclude or move all scripts from packaging yet. `app/evaluation_verifier.py` imports symbols from `backend.scripts.validate_football_analysis_pilot_labels` and `backend.scripts.evaluate_football_analysis_pilot` at three sites, including runtime tracking evaluation. First extract the shared runtime evaluator/validator core, preserve command wrappers, and test installed-wheel evaluation without the source tree. Only then exclude research-only scripts and relocate them with CLI/release compatibility tests. This dependency is a concrete blocker to the blanket packaging change, not a reason to leave the debt untracked.

## Verification record and remaining work

Local checks used Python 3.13 and Pydantic 2.13.4 with the repository's `ultralytics` test stub; they are preflight evidence, not proof of the pinned production environment. Recorded completed batches include 55 benchmark/prompt tests, 345 storage/runtime/remote-contract tests, 136 Daytona tests, and 11 gate tests. These batches overlap; do not sum them as unique coverage. The combined new contract/lifecycle/gate plus Daytona batch passed 176 tests. A larger combined pipeline run was stopped by the local command time limit; that truncated run is not counted as a pass.

The authoritative CPU verification uses the exact detached candidate commit, locked dependencies, the complete backend suite, and canonical code-only verifier in GitHub Actions. The final workflow run and its retained logs/receipt are the source-bound status record; no GPU/model-quality acceptance is implied by CPU tests. The temporary audit/repair workflow is absent from the candidate source tree.

Remaining items are explicit: reduce the retained mypy/BLE/B/C901 debt; complete route and pipeline decomposition behind characterization tests; separate runtime evaluator utilities before research packaging changes; review other Pydantic contracts for compatible strictness. Do not mark these closed merely because a baseline now exists.
