# Backend-quality continuation: start here

This is the repository-native handoff. A new session needs connected GitHub access and the short prompt below, not the old chat or a ZIP attachment. Read this file from live `main`, not a remembered revision.

## Prompt for a new session

```text
@GitHub @Superpowers
Resume backend code-quality remediation in
https://github.com/ms81labs/sol-astra-football-analyses-sept26
Read docs/superpowers/handoffs/backend-quality/START_HERE.md on live main
and follow its linked state, instructions and next task. Reconcile newer
commits before editing. Continue the existing cleanup, not a new audit.
Keep the single main integration line, preserve behavior, and respect
all tool permissions and approval requirements. Do not repeat completed
repairs or work around blocked workflow writes. Finish and verify a
bounded batch, keeping the checkpoint current.
```

## Read in this order

1. [STATE.json](STATE.json): accepted application source, open debt and saved draft.
2. [RESUME_INSTRUCTIONS.md](RESUME_INSTRUCTIONS.md): live-head reconciliation, invariants and publication boundaries.
3. [NEXT_TASK.md](NEXT_TASK.md): the exact report-store structural task.
4. [VERIFICATION_RUNBOOK.md](VERIFICATION_RUNBOOK.md): test commands and acceptance requirements.
5. [COMPLETED_AND_OPEN.md](COMPLETED_AND_OPEN.md): consult to avoid repeating work or misreading old plans.

Read individual source files and evidence only as needed. Do not load the whole repository, old transcript or every CI log simply to regain context.

## Resume point

Accepted application source: `1dd6bdd9fe9bee940a8a702ddd6947383fc4a19b`, tree `e6768bccc5f1134a8f07f71b0f24690ff0912ab2`. It is the merge of PR #14, which brought `integration/catapult-workbench` onto main together with the `REPORT_STORE_STRUCTURE` slice. Normal CI `36253514511`, C05 `36253514493` and C06 `36253514457` completed successfully on that SHA (complete backend 5,578 passed / 18 skipped). [ACCEPTANCE.json](ACCEPTANCE.json) records it under `subsequentAcceptances`; the earlier `efcc3e1` record is kept.

There is **no saved draft** now. The report-store patch under `unpublished/` was applied unchanged as `e09aa99` and accepted; it stays only for provenance. Ruff is 423 at the accepted head: the slice retired 3 entries, and the catapult merge recorded 30 new ones (23 C901, 7 BLE001) and retired 9 stale ones. [NEXT_TASK.md](NEXT_TASK.md) says how to choose the next bounded batch.

main is the only integration branch. Keep it that way: short-lived PR branches are merged and then deleted.

## Where the rest lives

Live source, tests, locks and baselines are already in this repository. The active checkpoint is [the audit checkpoint](../../audits/2026-09-24-backend-quality-closeout-checkpoint.md). Earlier history remains in Git; the accepted source's parent is `aa97f25285cfc2d343cf7e7d76359a18862ca6ab`.

The original close-out direction is recorded in [the follow-up plan](../../plans/2026-09-24-backend-quality-follow-up.md), [the next-stage plan](../../plans/2026-09-24-backend-quality-next.md) and [its specification](../../specs/2026-09-24-backend-quality-next.md). Historical checkboxes and counts are not authority to replay completed work.

Full historical logs remain in the original downloadable handoff backup and GitHub Actions artifacts while retained. They are not required to start the next task. Artifact expiration must be reported as missing historical evidence, not guessed around or treated as proof of failure. Current acceptance always needs fresh evidence for the newly published application source.
