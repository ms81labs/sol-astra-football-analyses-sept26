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

Accepted application source: `efcc3e1193428c554449bf3d5c5f671635f1b235`, tree `416f8762c2e9845f8fdbbf03178d6a60723f587e`. Its report-store typing batch and accumulated source passed the applicable existing CI. There were no pending acceptance jobs for that SHA. [ACCEPTANCE.json](ACCEPTANCE.json) records the completed results and qualifications.

The next task is **not yet implemented in application source**: [unpublished/report-store-extraction.patch](unpublished/report-store-extraction.patch). Committing this patch as a documentation attachment does not apply it. The proposed Ruff reduction from 405 to 402 is not published remediation or accepted work.

The commit adding this handoff changes documentation only. The accepted application SHA above deliberately stays fixed: do not relabel old CI as acceptance of a newer SHA, and do not create another docs-only commit merely to replace a self-referential head. Inspect intervening changes; preserve these handoff files when applying the draft. Its recorded candidate tree is the original base plus the two-file draft, not a full-tree expectation after this documentation commit.

## Where the rest lives

Live source, tests, locks and baselines are already in this repository. The active checkpoint is [the audit checkpoint](../../audits/2026-09-24-backend-quality-closeout-checkpoint.md). Earlier history remains in Git; the accepted source's parent is `aa97f25285cfc2d343cf7e7d76359a18862ca6ab`.

The original close-out direction is recorded in [the follow-up plan](../../plans/2026-09-24-backend-quality-follow-up.md), [the next-stage plan](../../plans/2026-09-24-backend-quality-next.md) and [its specification](../../specs/2026-09-24-backend-quality-next.md). Historical checkboxes and counts are not authority to replay completed work.

Full historical logs remain in the original downloadable handoff backup and GitHub Actions artifacts while retained. They are not required to start the next task. Artifact expiration must be reported as missing historical evidence, not guessed around or treated as proof of failure. Current acceptance always needs fresh evidence for the newly published application source.
