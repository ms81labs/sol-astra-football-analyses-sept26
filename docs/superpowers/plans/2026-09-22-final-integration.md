# Final supported-code completion and single-main integration plan

> Execute inline with Superpowers systematic debugging, TDD, verification-before-completion and finishing-a-development-branch. Use Ponytail for the small-diff review. Do not restart completed C01–C06 work.

**Goal:** Resolve the final-CI failure, complete the supported F00–F09 evidence handoff, and consolidate preserved work into one `main` branch.

**Architecture:** Keep the existing application, immutable generations, ledger, receipt writer and scorer/media workflows. The new startup race belongs in `Storage._initialize`: acquire a SQLite write transaction before schema discovery and retain it through migration. Reuse the connection context for commit/rollback; no exception-swallowing or lock framework.

**Tech stack:** Existing SQLite/Python/pytest, locked Linux Python 3.11 CI, React/TypeScript verifier, pinned TrackEval and synthetic FFmpeg.

**Spec:** The user's current instruction authorizes completing and merging. The supplied bounded-completion IMPLEMENTATION_PLAN and REGRESSION_REGISTER remain the acceptance basis. The repository's 2026-09-22-review-fixes-checkpoint records prior work, not a current CI result. Current merge authorization supersedes historical no-merge instructions; paid/live-store/deployment limits remain.

## Constraints

Use the existing `agent/backend-bounded-completion-2026-09-22` until verified integration into `main`. Preserve all commits and unrelated files. No forced history, live-store changes, model/provider invocation, GPU/paid worker or deployment. Retire only a fully merged redundant branch after ancestry and retained-bundle checks. Never delete divergent work. Keep code/documentation SHAs, local/locked profiles and synthetic/real qualifications distinct. Do not turn plan-package validation checks into product-test results.

## Review focus

Two startup processes must not migrate from the same stale schema; a mid-migration failure must roll back; nested pytest receipts must not impersonate the outer gate; moved refs must not be overwritten; C05 rollout requires an actual main-push run, not YAML inspection. These are Tasks 1, 2 and 4 respectively.

## Task 1 — Repair the demonstrated schema race

**Files:** `backend/app/storage.py`; `backend/tests/test_storage_schema_initialization.py`.
**Input:** f6223f5; failed run 35787664136/job 106948292320/artifact 10720839129.
**Output:** atomic concurrent schema initialization and deterministic regressions.

- [x] Retain the failed artifact and verify SHA256 `6b617c8576f044ac82a8d276ce4441352157e95a99e124bc118be1282de4f75f`. Actual child failure: duplicate `analytical_generation_id` during constructor migration.
- [x] Reproduce with two real spawned initializers and pipe-ordered schema snapshots. Add partial-DDL rollback/retry control. Both fail on the original implementation, not during collection.
- [x] Add `BEGIN IMMEDIATE;` inside the existing SQL script. It must be inside because `executescript` commits a pre-existing transaction. Existing `_ClosingConnection` commits/rolls back the complete migration.
- [x] Run new controls and ledger/receipt/shell/storage neighbors: 111 passed on available Python 3.13.5. This is not locked 3.11 evidence.
- [x] Publish exact tested storage blob `11a1133a083b9a7d5c180882b9f45ed2159b3ae0`; no other production code change.

Ruling: container Git network access is unavailable. A hash-guarded one-shot native GitHub job applied only the tested replacement and deleted its own workflow in the same commit. It is not a retained framework; no extra branch or persistent write-permission workflow remains. Commit c3f0473 contains the three-line production fix.

## Task 2 — Finish canonical verification

**Files:** `.github/workflows/ci.yml`, `.github/workflows/c06-regressions.yml`, `backend/tests/test_completion_workflow_contract.py`.
**Output:** exact candidate source, full-suite JUnit, nine-gate receipt, scorer/journey/media/quality evidence.

- [x] Reproduce missing full-suite/candidate-C06 execution homes in workflow contracts, then pass those contracts without paid execution.
- [ ] Run the complete locked CPU backend using `python -m pytest -q -ra backend/tests --junitxml=.verification/backend-all.xml`; upload logs, selection receipts and JUnit even on failure.
- [ ] Preserve the original nine-gate verifier and inspect the final exact outer-invocation, source/profile/stub/log bindings.
- [ ] Run existing excluded, integration, media, pinned C05 plus V3T50, and C06 with its separate opt-in long decode. Explain each skip; do not add overlapping counts as unique coverage.
- [ ] Repair only an actually demonstrated failure and repeat affected gates. Missing external capability remains an explicit qualification.

## Task 3 — Reconcile original acceptance and compatibility

**Destination:** `docs/superpowers/audits/final-integration/`.

- [ ] Preserve original requirement text and map actual existing nodes to A01–A06, R01–R10, N01–N06, all 21 CQA findings, V3T and follow-up requirements. File hints alone are not proof; narrower supported subclaims need explicit limits.
- [ ] Retain prior historical RED/GREEN evidence under its own source. Repeat copied c685640 video/tracking store open/edit/reopen and untouched-backup restoration on this changed candidate; verify source hashes and SQLite integrity.
- [ ] Keep actual pre-v3 fixture provenance, operation-specific suppression rationale, UI contract tests and all unavailable qualification boundaries.
- [ ] Validate evidence/node references and complete execution/regression registers without retrospective invented results. Review is self-review unless another reviewer actually executes.

## Task 4 — Merge and verify main

- [ ] Refresh all branches/open PRs and prove `main` ancestry; inspect any new or divergent changes instead of overwriting them.
- [ ] After candidate verification, merge the exact candidate with preserved history and a non-skipping merge message. No force update.
- [ ] Observe actual main-push CI, C05 and C06 at the merged source. Validate their artifacts and record C05 as A04 rollout evidence.
- [ ] Fix any demonstrated post-merge defect forward; never rewrite history or pretend a running workflow passed.

## Task 5 — One-place handoff

- [ ] Publish one closure/evidence entrypoint; mark older checkpoints historical without deleting their evidence.
- [ ] Retain an exact-source bundle and the merged-branch SHA, verify ancestry/no unmerged PR work, then retire only the redundant branch reference.
- [ ] Re-read final branches and workflow state. Deliver exact main SHA, actual passed/qualified outcomes, the canonical documentation path and portable checksummed evidence.

## Stop condition

All supported follow-ups have evidence-backed dispositions, required CPU/UI/scorer/media selections are complete, compatibility/rollback is evidenced, and main-push integration is observed. Real football accuracy, representative full-match performance, real billing, unavailable browser/macOS runtime, GPU and public-hosting qualification remain separate. Stop cleanup rather than invent another architecture program.
