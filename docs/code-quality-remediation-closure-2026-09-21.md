# Backend Code-Quality Remediation Closure — 2026-09-21

**Repository:** `ms81labs/sol-astra-football-analyses-sept26`  
**Audit baseline:** `312cb5a77718830948378ccbcb577b9539b9aed1`  
**Verified implementation head:** `c64fb87a671d88275d29991e488dad68314b72e0`  
**Scope:** backend code quality only; no football-analysis/product-direction changes.

## Closure basis

The rebuilt audit required incremental, behavior-preserving remediation: keep endpoint contracts stable,
preserve hardened filesystem/rollback/security behavior, add truthful CI/static verification, and reduce
change radius without inventing a new framework or rewriting persistence wholesale.

Fresh evidence on the verified implementation head:

| Verification lane | Result |
|---|---|
| python-quality | PASS |
| api-profile | PASS |
| integration | PASS |
| real-media | PASS |
| excluded-backend | PASS |
| macOS profile | PASS |
| canonical verify | PASS |
| C06 media execution evidence | PASS |
| GPU acceptance | skipped on normal push, as designed |

## Final finding register

| ID | Disposition | Closure evidence |
|---|---|---|
| C01 | Closed | Masked `Path` defect repaired; regression distinguishes intended validation from accidental exception fallback. |
| C02 | Closed | Formerly excluded-suite failures repaired and represented by automatic CI lanes. |
| C03 | Closed | Predictor capability check repaired so wrapper attributes do not make capability detection meaningless. |
| H01 | Closed | FastAPI composition modularized; `main.py` is 399 lines with zero inline `@app.<method>` routes. |
| H02 | Closed | Leftover routers no longer use `backend.app.main` as a dynamic symbol namespace. |
| H03 | Closed | `Storage` remains the public facade while cohesive job/review/correction/remote/calibration/identity seams were extracted; `storage.py` is 2,035 lines versus the audit's ~3,140-line class baseline. |
| H04 | Closed | Benchmark summarization split by concern; final assembly remains centralized; summarizer is ~448 lines versus ~1,003. |
| H05 | Closed | Duplicate `MatchBenchmarkSummary` fields removed. |
| H06 | Closed | All 297 script offenders / 477 original violations transformed; repo-wide AST hygiene gate is in python-quality. |
| H07 | Closed | Targeted degraded states now emit safe observability instead of silent operational suppression. |
| H08 | Closed | Pinned Ruff/static correctness gate runs in CI. |
| M01 | Closed | RUF100 was evaluated with the debt rule set enabled: 13 directives were genuinely unused and cleared; 65 directives tied to otherwise-disabled rules were retained because they suppress real findings when those rules are enabled. |
| M02 | Closed | B023 late-binding debt triaged/cleared for intended scope. |
| M03 | Closed | Verifier selection/threshold logic centralized. |
| M04 | Closed | Human pytest-summary parsing removed from verifier contract. |
| M05 | Closed | Dependency drift checking added. |
| M06 | Closed | Real CV import smoke improves profile fidelity. |
| M07 | Closed | Repair-profile normalization concentration reduced. |
| M08 | Retained by contract | 410 `ROUTE_RETIRED` compatibility is asserted by tests; deleting it would be a behavior change. |
| M09 | Retained by ruling | No forced split of large tests without concrete duplicated setup; file-size-only movement would be cosmetic. |
| M10 | Closed | Private benchmark/helper coupling reduced; regular-file helper moved to true owner. |

## Structural snapshot

- `backend/app/main.py`: **399 lines**, **0 inline route decorators**.
- `backend/app/storage.py`: **2,035 lines**, `Storage` begins at line 148 and composes identity, calibration, remote-result, and job persistence mixins plus focused review/correction components.
- `backend/app/run_benchmarks.py`: **2,434 lines**; `summarize_match_benchmark()` is approximately **448 lines**.
- `backend/tests/test_script_hygiene.py`: **32-line AST regression** guarding against `sys.path.insert/append` and duplicated canonical UTC helpers in operational scripts.

## H03 stop condition

The audit said to keep the public `Storage` API stable, extract one tested concern at a time, and avoid a
repository-pattern rewrite. That condition is now met. Further decomposition is deliberately deferred until
a concrete change-radius problem identifies a real seam; splitting more solely to reduce LOC would violate
the remediation's simplification discipline.

## Preserved constraints

- No intentional football-analysis direction change.
- No intentional endpoint URL/schema/status contract change.
- No weakening of filesystem, rollback, or security boundaries.
- No new runtime framework/dependency introduced for structural refactoring.
- Compatibility-only behavior was retained where removal lacked caller/test evidence.

## Resume rule

This remediation program is closed at the verified implementation head above. Treat this document and
`docs/code-quality-remediation-checkpoint.md` as the handoff. Reopen an item only when a regression,
new evidence, or an explicitly approved contract/product change justifies it.

## Post-closure hygiene follow-through — 2026-09-22

Independent verification found non-blocking F401 residue created or exposed by the remediation. The follow-through branch removed **175/175** script F401 findings and **16/16** true app F401 findings after explicitly preserving the two `storage.py` compatibility re-exports. The dedicated C03 track-only probe regression was added, and the CI F401 gate was widened to all of `backend/app` and `backend/scripts`. JSON helper variants remain deferred because their serialization semantics are not equivalent.
