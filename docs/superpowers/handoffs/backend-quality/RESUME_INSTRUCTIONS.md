# Resume instructions

## Recover once, then execute

Use the connected GitHub tools to resolve live `main`. Read the active checkpoint and intervening commits relative to the accepted application SHA in STATE.json. Never reset main to the saved base, overwrite newer work, or reapply completed repairs. The initial handoff-publication commit is documentation-only; compare touched source blobs before deciding that the saved application patch is stale.

Read repository instructions that actually exist. Obtain an isolated local checkout through the available supported tools; a fresh session must not assume old `/mnt/data` paths, Python environments or opaque tool-response IDs survive. A new local checkout does not require a new remote branch. Keep evidence outside the source tree where practical.

The original ZIP is now an optional offline backup, not a dependency of this runbook. Source and history are in GitHub; the only active unpublished application delta is committed here as a `.patch` attachment. Do not apply older published patches from historical artifacts.

Use recorded run IDs or commit check-run/workflow-run reads. The connector's `fetch_commit_workflow_runs` wrapper may filter PR-triggered runs, and combined status alone may omit Actions checks. An empty result from either is not proof that main-push CI never ran.

## Execute the existing task

Use the relevant installed development skills. Start with NEXT_TASK.md; the draft is review input, not trusted proof of correctness. Run original contracts, inspect the exact delta, apply it only after reconciling the live base, and verify candidate behavior. Record any necessary deviation and its reason.

After a bounded batch is accepted, continue approved open work as feasible. Do not restart the broad audit, ask for already-documented requirements, or deliberately create another unfinished draft merely to hand off. Respect genuinely required publication approvals; this file is not blanket authorization.

## Preserve these boundaries

Scope is code quality, not football thresholds, model choices, metric semantics or product direction. Preserve HTTP/CLI entry points, compatibility re-exports, per-application callbacks and stores, authorization, generation isolation, validation/error ordering, transaction ownership, lock spans and artifact-publication side effects. Unknown evidence remains unknown, not invented zero or a neighboring observation.

Do not blanket-forbid extras on historical/external Pydantic inputs. Do not broaden exact builtin-number acceptance to bool or subclasses. Do not remove validation or persistence because its return value is unused. Review broad exception handlers individually; do not add secret-bearing exception text merely to quiet lint.

No paid-provider/GPU operation, deployment, live data mutation, additional remote branch, force push, changed scorer pins, runtime-lock modification, hidden test exclusion or weaker quality threshold is part of this continuation.

**A temporary preflight-workflow write was blocked. Do not retry, recreate, encode, restore from history or route around that blocked action. Use existing unchanged CI and ordinary permitted repository operations. If an operation is denied, preserve the patch and report the boundary.**

## Keep a small durable checkpoint

Update `docs/superpowers/audits/2026-09-24-backend-quality-closeout-checkpoint.md` at meaningful boundaries. Include task, base/current SHA, changed files, commands with exit results, CI IDs, failures and the exact next action. Keep statuses distinct: planned, implemented, locally verified, published, accepted. Do not label the entire audit complete because one batch or scoped baseline is green.

Preserve failures by name, including unchanged-source reproductions. Describe author self-review honestly; never invent an independent agent. Avoid re-downloading completed artifacts repeatedly or polling every few seconds. Do not change the application SHA being accepted while treating its CI as final-source acceptance.

No background-delivery promises. At a session boundary, report actual state and the precise next action. Do not keep appending the entire transcript to the active checkpoint. Git retains old checkpoints.
