# Backend quality continuation — design

**Request:** Plan and execute the remaining code-quality cleanup with Superpowers and
Ponytail, preserving application behavior and the single existing integration line.

**Source:** `3dbb46acf43dda666c835f996def7ff5b95e76da`; the source/tool snapshot at
`8240a240b47e7ed66fd2e7816ad06babf0181362` changes only the temporary snapshot workflow.

## Required outcome

Repair the final-head CI contract regression; retire the 108 diagnostics in the existing
mypy scope without weakening its configuration; remove the runtime dependency on pilot
research scripts before excluding those scripts from the wheel; split the two root
leftover route factories without changing route order, OpenAPI or per-app dependencies;
and remove unambiguous lint debt with explicit compatibility decisions.

## Boundaries

Keep application factories, the Storage facade, command entry points, persisted formats,
scorer pins, authorization, provider policy and runtime dependency locks unchanged.
Unknown timestamps must stay unknown, not become invented times. An unused result does
not justify deleting validation or persistence. Zip operations retain their existing
truncation behavior. Expected failure tests assert specific observed exceptions.

Use no new runtime dependency, global mutable router/storage, blanket type/lint ignore,
force-push, additional remote branch, deployment, live store or paid provider/GPU call.
Work locally in an isolated source workspace and publish through the authorized connector.

## Acceptance

Require failing-then-passing regressions for actual defects, source/AST equivalence for
moved code, two-app storage/auth tests, both route-flag snapshots, and a real built-wheel
runtime evaluation probe outside the source tree. Keep source-bound quality baselines
and verify their pinned Python 3.11 metadata on CI. Final acceptance requires completed
normal CI on the published commit; local subsets or running jobs do not establish it.

Full storage/run_guerilla decomposition, physical relocation of every research command,
and the remaining broad-catch/complexity/dependency-style debt are not implied by this
bounded continuation. Record them explicitly rather than marking the entire audit closed.
