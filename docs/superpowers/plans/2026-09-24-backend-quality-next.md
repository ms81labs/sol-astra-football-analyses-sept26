# Backend quality continuation — implementation plan and execution record

> **For agentic workers:** Execute task-by-task with `superpowers:executing-plans`.

**Goal:** Restore final-head verification and remove concrete type, packaging and route
structure debt without changing football-analysis behavior.

**Architecture:** Preserve existing per-app factories and runtime contracts. Add fixed-shape
types only where actual data already has a fixed shape. Move shared scorer/validator
functions into app modules with explicit script re-exports. Assemble small route domains
in the original order; report readers take their Storage dependency explicitly.

**Tech stack:** Python >=3.11, Pydantic 2.13.5, FastAPI, pytest, Ruff 0.16.8, mypy 2.3.1.

**Spec:** `docs/superpowers/specs/2026-09-24-backend-quality-next.md`.

## Global constraints

One existing main integration line; no force-push, new remote branch, deployment or paid
provider/GPU execution. Runtime locks unchanged. Preserve validation/persistence and
compatibility re-exports. No broad typing/lint exemptions. Final acceptance uses locked CI.

## Review focus

Logged producer failures must propagate past tee. Unknown clocks must not invent samples.
Reservation values must reach both attempt records and charge rows. Scorer extraction must
preserve source pins and independent-label checks. Separate apps must retain separate stores.

## Task 1 — CI contract regression

- [x] Reproduce the existing exact-string-count failure: six pipefail occurrences versus four.
- [x] Keep the independent CI/profile assertions; replace the count with a per-run-block
  check that `(exit 23) | tee /dev/null` exits 23 under the actual shell guards.
- [x] Run `python -m pytest -q backend/tests/test_verify_script.py` together with the new
  typed-boundary tests: 67 passing cases in the restored workspace.

## Task 2 — Scoped typing and timestamp defects

- [x] Reproduce all 108 diagnostics with pinned mypy/Pydantic and unchanged configuration.
- [x] Add missing-clock and numeric/monetary boundary regressions. The two missing-clock
  cases fail on the original code; the other 18 characterize existing behavior.
- [x] Use fixed-shape TypedDict results, local narrowing, precise enum values, separate
  Decimal reservation locals, and explicit receipt-bearing process annotations.
- [x] Preserve unknown sample clocks and skip discontinuity comparisons across unknown times.
- [x] Rerun the same mypy command: zero diagnostics, without added ignores or config changes.
- [x] Verify job/ledger/money behavior: 86 passing cases. An existing API test caught an
  incomplete local-variable rename during workspace recovery; both charge and attempt
  records now use the same reserved amount and the entire API batch passes.

## Task 3 — Runtime evaluation and wheel packaging

- [x] Add a fresh-process test blocking every backend.scripts import; observe its original failure.
- [x] Move the shared label/scoring functions into app/pilot_labels.py and app/pilot_tracking.py.
  Preserve original function bodies, scorer pin, namespace checks and script re-exports.
- [x] Build an actual wheel from clean source with no network/dependency installation.
  Assert it excludes backend/scripts and run evaluation outside the source tree.
- [x] Exclude backend.scripts* only after that probe succeeds; retain source/editable CLI paths.
- [x] Run runtime/pilot/C05 tests: 67 passed, six needing the pinned scorer skipped locally.
  Dedicated C05 CI supplies the real pinned scorer; local skips are not acceptance evidence.

## Task 4 — Route extraction

- [x] Capture ordered route metadata and complete OpenAPI under both leftover-HTTP flag values.
- [x] Replace the two root factories with assembly calls into five focused domain modules.
  Keep all handlers, registration order, prefixes, legacy wrappers and per-app dependencies.
- [x] Lift report-reading helpers with explicit Storage parameters, not global application state.
- [x] Verify handler AST equivalence (normalizing only explicit helper Storage arguments),
  identical OpenAPI/route snapshots, and two-app authorization/storage isolation.
- [x] Rerun route/API/architecture tests: 93 passed in the restored workspace.

## Task 5 — Lint reduction and publication

- [x] Make all legacy zip truncation explicit with strict=False; retain intentional exports.
- [x] Narrow 17 broad expected-error assertions to observed concrete classes; 94 cases pass.
- [x] Remove unused imports, redundant static getattr/f-string cases, and the two remaining
  silent optional-metadata handlers. Debug messages contain no exception/secret payloads.
- [x] Review exact baseline migration: Ruff 581 -> 504; mypy 108 -> 0. Metadata and scope retained.
- [x] Extend the zero-debt F/S110/B904 command to all backend code, including tests and release.
- [ ] Verify both baselines under pinned Python 3.11, publish atomically, remove the temporary
  source/tool transfer workflow, and read completed final-head normal CI results.

## Durable handoff and limitations

The original execution workspace restarted when the full suite was launched. The source
was restored from the pinned snapshot; changes were rebuilt and focused tests rerun. Treat
only retained post-recovery logs and the final pinned CI run as acceptance evidence.

The audit report at `docs/superpowers/audits/2026-09-24-backend-quality-continuation.md`
records the implemented scope and remaining debt. Final CI receipts, not a documentation
checkbox or a running workflow, determine acceptance.
