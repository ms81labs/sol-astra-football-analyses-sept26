# Source-bound release dossier (GA-14)

Candidate checkout: git HEAD of `cursor/finish-ga-v11-todos-bf09` (feature base `5fa98440c09cabdbc5847920cea097268c5a5171`).
Plan source snapshot: `5099e1fd50d856a7cd0449f1ef4b1695d8f930c3`.

Deployment boundary: **loopback only**. Origin/Host checks and CORS are browser boundaries, not authentication. G-NETWORK remains required for any non-local deployment. Hosted HMAC/JWT object tokens are **not implemented**; hosted access stays fail-closed.

## Rights and processing

| Asset | Control |
|---|---|
| Match recording | Source rights record required before share |
| Code and weights | Review Ultralytics and exact weight licences before commercial use |
| Cloud inference | Host credentials never enter the worker |
| Youth footage | Club permission and safeguarding required |
| Native builds | Gated inert (`GA18_NATIVE_APPROVAL`) |

## Operations

- Restore: `docs/runbooks/artifact-restore.md`
- Current gates: `docs/status/current.md`
- Rollback: revert the active manifest/feature flag, stop admitting affected jobs, preserve artifacts, report stale outputs
- Independent evaluation remains fail-closed at 0 / 18 complete tasks

This document does not authorise a provider mutation, revive historical smokes, or claim football accuracy.
