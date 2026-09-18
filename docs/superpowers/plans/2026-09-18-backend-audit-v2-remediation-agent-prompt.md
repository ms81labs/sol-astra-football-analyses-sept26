# Backend Audit v2 Remediation — Agent Prompt

Copy the block below verbatim into the implementing coding agent. It references the guide and audit committed alongside this file.

```text
You are implementing the backend remediation for the Guerilla Analytics repository (ms81labs/sol-astra-football-analyses-sept26).

Read these two files in full before doing anything else:
1. docs/superpowers/plans/2026-09-18-backend-audit-v2-remediation-implementation-guide.md  — your operating manual (how to structure every change in this repo)
2. docs/superpowers/audits/2026-09-18-backend-consolidated-audit-v2.md  — the authority on WHAT is wrong (items B01–B35) and WHAT evidence closes each item (acceptance tests, T01–T28)

If the two disagree on scope or acceptance, the audit wins.

## Baseline
Audited commit: d881d1eaf7a0898897bd9a1a1ae46306606c904d. Before changing code, run `git rev-parse HEAD`, record it, and if it differs from the audited commit, diff each file the guide pins and mark any item already changed with evidence. Install per guide §2.1, run `VERIFY_CODE_ONLY=1 scripts/verify.sh`, and save the exact passed/skipped/failed counts. This baseline goes in your final handoff report.

## Scope and order
Implement the seven work packages in the order given in guide §4:
- Phase 0: shared contracts (§12) — types only
- Phase 1 (parallel): H01 provider guard (B13, B14); H03 false-accept fixes (B05, B06, B33) + B22, B23; H02 failing raw-row regression T02
- Phase 2: H02 review service + generations (B01–B04, B35); H03 remainder (B07, B24, B28); H04 job ledger (B10–B12); H06 hashing + trusted executables (B16, B34)
- Phase 3: H05 (B08, B09, B18, B25, B29); H06 remainder (B17, B19, B20, B21); H01 remainder (B15, B26, B27)
- Phase 4: H07 (B30–B32), running throughout

Work one package at a time on its own branch (`cursor/h0N-<name>`), open a draft PR per package, and keep commits small and tagged with audit IDs (guide §3.2). Do not open one PR that claims all 35 items.

## Non-negotiable rules (guide §1 — read them all; these are the ones most often broken)
1. Regression test FIRST. For every item, write a behavioural test that fails on d881d1ea for the intended reason (use the worktree recipe in guide §15). An ImportError on a symbol you are about to create does not count as a baseline failure. Paste the failing assertion message into the commit body.
2. Test the real input mode. B04 must be tested with a raw-row-backed video fixture (you must create it — guide §6.4), with the tracking-JSON case as a separate test.
3. Never trust posted arrays (events, metrics, claimedEvidenceIds, knownEvidenceIds) as ground truth. Load server-owned match state.
4. Unknown is not zero. Never substitute 0 / 0.0 / True for a missing measurement, cost, count or score. Use None plus a reason code.
5. Do not reserve the full budget again on retry; a retry consumes remaining authorised capacity (guide §12.3 invariant).
6. Never enable a cloud provider, launch a paid job, or change deployment state to get a green test. All provider tests use a spy that raises on network I/O.
7. Preserve existing source-bound artifact validation, no-shell subprocess execution, HTML escaping, TrustedHost/Origin checks. Tighten; never delete.
8. Metadata is not implementation. `admitted: True`, a renamed adapter, or an empty reasonCodes list closes nothing.
9. Never weaken a failing behavioural assertion to match a helper flag.
10. Scratch scripts live in /tmp. Only real tests under backend/tests/ go in the repo.

## Repository facts you must respect
- The frontend calls only the /api/matches/... family in backend/app/main.py (backed by Storage). It never calls /api/workbench/*. Default for B01 is to retire the workbench compatibility handlers with 410 and update the 3 backend tests that use them (guide §6.2.4).
- backend/tests/conftest.py sets GA_FLAG_LEFTOVER_HTTP=1; production default is off, and leftover routers mount at /api only when it is on. Run your regression tests with the flag unset at least once to prove production handlers served them (B32).
- The code-only CI profile ignores several suites and installs cv2/pandas/ultralytics stubs only when the real package is missing. Record which stubs were active in every test report.
- Add pytest markers `integration`, `real_media`, `gpu` to pyproject.toml (guide §3.3) and mark tests accordingly; multi-process, crash-recovery and FFmpeg pipe tests must use real subprocesses, never fakes.

## Definition of done
An item is `fixed` only with: fix commit SHA(s); regression test path; the baseline failure assertion; the pass on the fixed revision naming the profile (code-only / integration / real_media / gpu); remaining platform limits stated. Other allowed statuses are exactly: `safely deferred/disabled` (runtime refusal with a test proving it), `still open` (with reason), `not reproduced` (with the exact attempt). No "partially fixed" — split the item into rows.

At the end, write docs/superpowers/audits/<date>-backend-audit-v2-closure.md using the template in guide §14, covering all 35 IDs, and ensure `VERIFY_CODE_ONLY=1 scripts/verify.sh` plus the integration lane pass on the final revision.

Start now with guide §2 (baseline), then Phase 0, then Phase 1. Report progress per package as you go; do not wait until the end.
```
