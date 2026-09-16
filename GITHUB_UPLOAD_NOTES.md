# GitHub code-only handoff

This repository is a code-and-documentation export of local commit
`969578f7d657bbd8870915d417e068547c9b3c92`. It deliberately excludes Git
history, ignored files, `backend/storage/`, videos, model weights, databases,
archives, generated build/cache directories, and binary media.

## Current stage

- All R01-R18 remediation units are complete.
- The latest provider-disabled verifier passed 3,682 backend tests (1 skipped),
  100 research-sidecar tests, 144 frontend tests, lint, both TypeScript checks,
  production build, backend startup, release/runtime gates, negative preflight,
  and the production dependency audit.
- The software is ready for a controlled analyst pilot, not production or an
  arbitrary-video accuracy claim.
- The independent-label gate remains 0/18 tasks, 0/9,297 evaluation frames,
  and 0/30 minutes. No held-out inference has been opened.
- Historical Daytona product and representative capacity runs are preserved in
  the documentation, but exact-current-source Daytona acceptance is pending.

The deliberate pause is immediately before the human-truth phase. A named
independent reviewer must make prediction-free source declarations, complete
and lock the 18 CVAT tasks, and only then allow held-out inference and scoring.
Do not generate labels or team declarations from pipeline output.

## Important export limitation

This copy is intentionally small and cannot reproduce the complete release
verifier until the omitted artifacts are restored. Their identities remain in
`backend/release/v7.3.json`; restoration guidance is in
`docs/runbooks/artifact-restore.md`. The authoritative readiness narrative is
`docs/reports/2026-09-13-football-analysis-readiness.md`, and the concise live
handoff is `docs/status/current.md`.

No credential is required or included in this export. Keep provider and GitHub
tokens outside the repository.
