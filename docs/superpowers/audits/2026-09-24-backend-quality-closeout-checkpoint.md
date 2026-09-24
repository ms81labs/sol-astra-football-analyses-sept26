# Backend quality close-out checkpoint

## Resume from source, not the earlier chat totals

This batch starts from `240eae5dd84e89234ad0a67eb5a87e2d69e929cd` (tree
`88df37bf4209fbe362476cf20f4533dcb24ec921`). The local reconstruction was checked
against that exact Git tree, including file modes. It preserves the 81-file
continuation in `e90cc8d31258a7dd58c606ffb55b91133a1cb618`; none is reapplied.

The approved close-out sequence is BQ00 acceptance, BQ01 contracts/types, BQ02
lint/exception policies, BQ03 routes, BQ04 storage, BQ05 pipeline/CLI, BQ06
research separation, then BQ07 whole-scope acceptance. The existing design,
implementation record and limitations remain in the `backend-quality-next`
spec/plan and `backend-quality-continuation` audit beside this checkpoint.

## BQ00: strengthened CI failure-propagation regression

The prior continuation already removed the stale global pipefail count. Its
replacement, however, assumed `bash -e`, examined only the first logged pipeline,
tracked job names rather than both independent quality gates, and exempted an
entire step whenever `--exit-zero` appeared anywhere in its text.

This batch changes only `backend/tests/test_verify_script.py` and this checkpoint.
It does not modify application code, workflow commands, test selection, dependency
locks, packaging, or either diagnostic baseline.

Fourteen added cases cover nine masked/removed-gate mutations, two spellings for
an additional protected step, and three effective Bash-default scopes. Before the
checker repair, 12 cases failed and two passed. The repaired checker resolves
step > job > workflow shell settings, tests every logged gate pipeline, requires
the seven named acceptance steps, rejects continue-on-error and pipeline masking,
and does not interpret comments as report exemptions. Only the explicitly named
legacy-debt report is exempt.

Probes execute shell options and `(exit 23) | tee /dev/null`, followed by a harmless
successful command. They never execute workflow installers, actual tests, provider
commands or artifact paths. Supported shell/options and straight-line guard syntax
are deliberately bounded: future unsupported shell/control-flow forms require a
review of this regression, not an automatic exemption. The default-shell mapping
follows GitHub's workflow-syntax documentation.

## Verification obtained before publication

- Baseline workflow/quality tests on unchanged reconstructed source: 59 passed.
- Added regressions before repair: 12 failed, 2 passed (expected RED).
- Repaired workflow/quality tests: 73 passed under `python -m pytest`.
- Same workflow/quality selection under the console `pytest` entry point: 73 passed.
- Benchmark/prompt and lifecycle regression modules: 29 passed.
- Ruff diagnostic identities: 504, zero added and zero removed.
- Mypy in its existing explicit scope: zero, zero added and zero removed.

Local execution used Python 3.13, Ruff 0.16.8, mypy 2.3.1 and Pydantic 2.13.5.
The metadata comparison correctly identifies Python 3.13 versus CI's 3.11; these
local diagnostic comparisons are NOT a successful pinned CI baseline invocation.
No baseline metadata was rewritten. Runtime tests reported the ultralytics test
stub. Review was a separate author self-review, not an independent agent review.

Full-backend and canonical verification at the starting SHA were still running
when this patch was prepared. The other current CI lanes and dedicated C05/C06
runs had succeeded. Final acceptance of this batch must come from completed normal
CI on the revision containing these exact test bytes, not those earlier subsets.

## Remaining work and next action

BQ00: implementation and focused verification recorded above; inspect completed
full-backend, canonical and quality checks at this batch's published revision.
A queued/running/failed/cancelled required check is not acceptance. If successful,
resume the remaining packages without recreating this patch or another branch.

BQ01: the preceding continuation retired the initial 108 diagnostics; other model
compatibility policies and broader runtime typing are still open.
BQ02: preceding simple-rule repairs are preserved. The remaining baseline is
235 C901, 175 BLE001 and 94 B008 findings. This batch does not reduce those totals.
BQ03: root leftover factories were split into domains; other route factories and
remaining domain complexity are not closed.
BQ04/BQ05: storage and pipeline/CLI responsibility extraction remains open.
BQ06: shared runtime evaluation was extracted and research scripts excluded from
the wheel; physical relocation and supported-command compatibility review remain.
BQ07: wider runtime typing and full finding-by-finding acceptance remain open.

After BQ00 acceptance, the next code batch should address B008 dependency
annotations in one route domain, guarded by parameter/OpenAPI, authorization and
two-application isolation tests. Do not blindly narrow broad cleanup catches,
remove public re-exports, change algorithms, or claim that a baseline is closure.

Use one writer and the existing main integration line. Re-read remote HEAD before
publishing; never force-push or overwrite concurrent work. No deployment, live
store mutation, paid provider execution or GPU acceptance is authorized here.
