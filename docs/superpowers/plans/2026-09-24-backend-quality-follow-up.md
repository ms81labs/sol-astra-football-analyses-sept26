# Backend quality follow-up implementation plan

> For agentic workers: use Superpowers executing-plans; resume from source and recorded evidence, not a historical summary.

**Goal:** Verify the supplied audit and repair confirmed defects without reopening completed C01–C06 work or changing product direction.

**Source:** Application source at `20c6a2b5443390414d32d368f3d183abdf15af2a`; source-only audit workflow at `d369240219ca487a53ef397d4062f9906a323f91`.

**Architecture:** Retain native FastAPI composition, the Storage facade, module/import compatibility, generation publication, rollback, and provider-budget boundaries. Make local contract/observability repairs before introducing check-only quality gates.

**Tech stack:** Python 3.11, Pydantic 2, pytest, existing hash-locked Ruff, GitHub Actions CPU verification.

## Global constraints

- Existing `main` only; no new remote branch, merge, force-push, paid GPU/API execution, deployment, or live-store operation.
- Preserve prior explicit re-exports and script module entry points.
- Do not turn historical payload compatibility into runtime failures by blanket-forbidding extras.
- Keep calls that validate state or persist published artifacts, even when their return values are unused.
- Never log raw provider errors, credentials, transport payloads, or inline artifacts.
- Require regression failures before fixes and current-source verification afterwards.
- Remove the temporary source-audit workflow from the final source tree.

## Review focus

- All ten match-state values survive selected-cluster conversion and JSON round-trip, including zeros and independent mutable defaults.
- Unexpected summary keys fail loudly; no existing legitimate summary construction becomes invalid.
- Both attack directions reach both legacy prompt types with correct coordinate interpretation; approved-evidence behavior remains unchanged.
- Cleanup/logging changes preserve return values, retry counts, original failures, and redaction.
- Wider quality checks reject new diagnostics rather than concealing entire legacy files or disabling existing gates.

## Task 1 — Benchmark and prompt regressions

Files: `backend/app/run_benchmarks.py`, `backend/app/llm.py`, `backend/tests/test_quality_contract_regressions.py`.

- [x] Add real model/conversion/serialization and prompt tests; run `python -m pytest -q backend/tests/test_quality_contract_regressions.py` and record the expected failures.
- [x] Declare all ten missing selected-cluster metrics with the same defaults/types as the match summary. Forbid extras on these two verified summary contracts.
- [x] Include the already-built direction explanation in both legacy prompt strings without changing the approved-evidence path.
- [ ] Run the new tests and existing `test_run_benchmarks.py`, `test_llm.py`, and report/generation tests.

## Task 2 — Unused bindings and safe lifecycle diagnostics

Files: the exact F841/B904/S110 sites in the source-bound Ruff report; tests in `backend/tests/`.

- [x] Trace each expression/caller before editing. Keep `get_match`, `plan_recompute`, publication, and cleanup operations.
- [x] Add regression assertions for safe static diagnostics and exception propagation before changing lifecycle handling.
- [x] Remove only unused local bindings and pure dead expressions. Make non-security SHA-1 intent explicit while preserving digest bytes.
- [x] Add deliberate exception chaining or deliberate suppression as appropriate to each boundary, not an automated global rewrite.
- [ ] Run processor, storage, report, runtime-contract, and Daytona fake-client suites; no real provider execution.

## Task 3 — Measurable quality gates

Files: `pyproject.toml`, `.github/workflows/ci.yml`, isolated quality requirements, a small baseline checker and its tests.

- [ ] Record exact Ruff version/commands/counts and reproduce mypy under a pinned, documented configuration.
- [ ] Enforce clean correctness rules immediately where feasible; retain all existing gates.
- [ ] Baseline remaining requested diagnostics with explicit diagnostic identity; fail on additions, stale entries, tool failures, or incompatible baseline metadata.
- [ ] Enable the Pydantic mypy plugin so constructor field omissions are visible statically; introduce a clearly scoped type baseline, not an assertion that all legacy typing debt is fixed.
- [ ] Add mutation-style tests demonstrating that a new diagnostic fails the gate and a tool crash cannot pass.

## Task 4 — Structural/packaging assessment and closure

- [x] Inventory local imports and actual dependency edges; do not equate every local import with an import cycle.
- [x] Inspect factory closure isolation before any router move. Do not replace per-app state with module-level mutable singletons.
- [x] Check imports, packaging tests, runtime modules, release tools, and module entry points before excluding or relocating scripts.
- [x] Record genuinely open structural work and its acceptance criteria in the follow-up report; no closure by renaming files or suppressing diagnostics.
- [ ] Run complete CPU backend and canonical code-only verification on final source, inspect the exact published diff, then confirm current-head CI.

## Execution rulings

- Preserve required computation/publication and validation calls; remove only unused bindings.
- Keep strict runtime extras limited to the two reproduced benchmark contracts; use the mypy plugin for broader constructor checking.
- Preserve Git scorer source-integrity hashing. Only stable event IDs are explicitly non-security SHA-1.
- Defer wholesale router/script relocation: per-app closure isolation and runtime imports from scripts require separate characterization-backed extraction.
- Verification status is tied to the exact candidate commit and retained GitHub Actions evidence, not to an uncommitted source snapshot.
