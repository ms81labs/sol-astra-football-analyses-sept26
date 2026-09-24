# Backend quality follow-up — implementation and acceptance map

Source reviewed: `20c6a2b5443390414d32d368f3d183abdf15af2a`. Implementation candidate: `1d99f9e835446edfd5fe68e5534fc44fa89658c3`. Detailed findings and evidence are in `docs/superpowers/audits/2026-09-24-backend-quality-follow-up.md`.

## Implemented scope

- [x] Reproduce selected-cluster metric loss and prompt interpretation gaps with failing tests; add all ten fields, targeted summary strictness, and legacy direction explanations.
- [x] Remove unused bindings while retaining publication, validation, fixture, and required-load operations.
- [x] Add failure-injection regressions before adding sixteen safe lifecycle warnings and deliberate exception chaining/suppression.
- [x] Preserve stable event identifier bytes while explicitly marking that hash non-security; retain scorer-source integrity hashing unchanged.
- [x] Run the targeted contract, storage/runtime, remote-contract, and Daytona fake-client batches; final new-regression preflight: 40 passing cases.
- [x] Measure pinned Ruff and scoped mypy; retain exact diagnostic baselines rather than broad file ignores or success overrides.
- [x] Exercise the actual Pydantic mypy constructor check with a misspelled-field canary; verify the baseline checker rejects new, duplicate, stale, malformed, and failed-tool outcomes.
- [x] Recheck locked quality baselines on GitHub Actions and compare all 31 implementation candidate blobs with the reviewed local source.
- [x] Confirm actual import-graph and packaging dependencies before considering structural moves.

## Publication and acceptance

Publish the candidate implementation unchanged, add the reviewed permanent CI gates, and remove the temporary audit workflow through the authorized GitHub connector. Remain on the existing `main` line: no new remote branch, merge, force-push, deployment, live-store mutation, or paid provider/GPU execution.

Candidate verification is bound to workflow run `36024815707`. Final acceptance is bound to the published commit's normal CI: complete CPU backend, canonical code-only verification, expanded Python quality gate, and applicable profile/media/integration checks. Read the completed checks and retained receipts; a queued/running job or a baseline containing legacy debt is not a passing result. The current-head CI records acceptance without requiring a self-referential documentation commit.

## Deliberately open structural work

1. Reduce the retained scoped mypy and broader Ruff debt without widening ignores or weakening constructor checks.
2. Extract route responsibilities behind route/auth/OpenAPI equivalence and two-app isolation tests; preserve dependency injection and the Storage facade.
3. Split remaining pipeline/storage responsibilities behind artifact-publication and generation-boundary characterization tests.
4. Extract runtime evaluator/validator utilities from the two script modules imported by `evaluation_verifier.py`; preserve CLI wrappers and test installed-wheel execution before relocating/excluding research scripts.
5. Review other Pydantic contracts individually for compatible strictness; do not blanket-forbid historical extras.

## Invariants

Preserve compatibility re-exports and module entry points. Keep calls with persistence or validation effects even when returns are unused. Do not log raw provider exceptions, secrets, tracebacks, or transport payloads. Do not replace per-app factory closures with mutable global routers solely to lower complexity. Do not call architectural or typing debt closed merely because a baseline now exists.
