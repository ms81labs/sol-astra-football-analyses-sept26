# Full Project Remediation Design

**Date:** 2026-09-12
**Status:** Approved synthesis of the repository-wide Ponytail and Superpowers sweep
**Product goal:** A coach uploads a football match; the application prepares and owns the video and durable state; Daytona supplies only ephemeral GPU execution; validated results return to the coaching workspace.

## Current baseline

ResultBundle v2 host import and live progress are locally complete. The current source branch contains bounded upload streaming, validated streamed result import, progress from the sealed worker through Daytona to the job record and UI, and independently reviewed lifecycle fixes. Historical Daytona smoke evidence remains bound to its original source and is not product acceptance for this branch.

The repository-wide audit accounted for every tracked path and parsed every tracked Python file. Its raw reports are tracked under `docs/superpowers/audits/2026-09-12/`. Structural coverage is not a claim of manual semantic review of every line.

## Ownership boundaries

- The application owns uploads, preparation, orchestration, validation, persistence, analytics, coaching views, and durable evidence.
- Daytona owns only private ephemeral GPU compute. No credential is sent into a sandbox unless the existing sealed protocol explicitly requires it; the exposed testing key must be rotated before another provider run.
- RunPod remains retired. Compatibility readers may remain, but no active workflow may depend on RunPod.
- Generated evidence, model weights, videos, datasets, and recovery history are retained until an exact retention decision exists.
- Local review tools stay loopback-only. Origin checks are a browser boundary, not authentication for public or LAN deployment.

## Remediation design

Work proceeds by risk and dependency:

1. Close filesystem deletion, arbitrary file serving, metadata injection, and local browser-origin boundaries.
2. Close review-write races, archive-name confinement, pending-form loss, sidecar path isolation, and match-admission outcomes.
3. Close frontend toolchain, match-scoped state, capability accuracy, event-loop blocking, selected-match hydration, and keyboard access.
4. Build fresh source-bound release evidence, run one authorized real football product acceptance, then measure producer capacity.
5. Delete only proven unreachable or duplicated code after caller, retention, and release checks.

Each behavior change is test-first: reproduce the current failure, watch the regression fail for the intended reason, apply the smallest root-cause correction, run focused and relevant suites, then obtain independent spec and quality review. Do not run multiple implementation agents against the same worktree concurrently.

## Non-negotiable contracts

- Preserve ResultBundle v1 compatibility and the reviewed v2 artifact/hash chain.
- Preserve atomic publication and rollback behavior.
- Never weaken evidence freshness, credential containment, path confinement, sandbox cleanup, or result validation to make a run pass.
- Do not add a queue, service, framework, auth system, cache, websocket transport, or dependency unless a measured requirement proves the existing platform cannot meet the product goal.
- Never repeat the historical fourth infrastructure smoke. The next provider operation is a distinct product acceptance with rotated credentials and fresh source/release evidence.
- Do not claim full-match capacity from host-import capacity alone. Measure the actual worker producer before designing video splitting or batching.

## Completion evidence

Local remediation is complete only when every required R task in the implementation plan has a reviewed completion record and the provider-neutral verifier passes on the integrated source. Product completion additionally requires one source-bound real football clip through API upload, sealed Daytona worker execution, validated v2 import, visible intermediate progress, usable coaching output, and confirmed sandbox deletion. Capacity work follows the measured result of that acceptance.
