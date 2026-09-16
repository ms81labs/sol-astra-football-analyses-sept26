# Daytona GPU Execution Design

**Date:** 2026-08-24  
**Status:** Approved for planning  
**Supersedes:** RunPod deployment and container-release execution work in the active stabilization lane

## Goal

Replace the active RunPod execution path with a fail-closed Daytona GPU job that runs one football-analysis workload in an ephemeral sandbox, verifies the frozen release source and every runtime artifact before execution, returns a validated result bundle, and deletes the sandbox after success or failure.

The existing provider-neutral release manifest, portable runtime options, artifact hashes, processing logic, storage contracts, and canonical project verifier remain authoritative. Only provider-specific transport, lifecycle, packaging, verification, documentation, and configuration change.

## Non-goals

- No long-running public inference endpoint in the first Daytona release.
- No warm pool, persistent GPU volume, or reusable snapshot until the one-shot path is proven.
- No public preview URL.
- No live RunPod build, push, API call, or deployment.
- No compatibility facade that silently selects RunPod.
- No database rewrite solely to rename historical RunPod columns; existing data remains readable.

## Chosen architecture

The backend submits each remote analysis as one ephemeral Daytona GPU sandbox job. The default GPU preference is RTX PRO 6000, with H100 as an allowed fallback. The sandbox is created from an OCI image pinned by digest, with one GPU, bounded CPU/RAM/disk, `ephemeral=True`, and outbound networking blocked during workload execution.

The backend streams a sealed job bundle into the sandbox. The bundle contains:

1. a `git archive` of the exact frozen source commit;
2. the canonical release manifest and verification evidence;
3. the five manifest-declared runtime artifacts;
4. the input video and a canonical job request;
5. a receipt binding every file name, size, SHA-256 digest, source commit, manifest digest, and requested runtime options.

Daytona's streaming file API is used for large inputs so the host never retains duplicate aggregate payloads in memory. The sandbox has no Daytona credential. It validates the receipt, materializes the portable runtime options, runs the existing provider-neutral processing function, writes a canonical result bundle, and exits. The host downloads and validates the result before updating application storage.

## Components

### Provider-neutral worker boundary

The video-processing entrypoint is extracted from the RunPod handler into a provider-neutral GPU worker module. It accepts a local job-request path and produces a local result-bundle path. It has no Daytona or RunPod imports and no network dependency.

The worker owns:

- request schema validation;
- receipt and artifact verification;
- runtime-option materialization;
- video processing;
- canonical result serialization;
- bounded progress and diagnostic output.

### Daytona host adapter

A Daytona adapter owns only cloud lifecycle and transport:

- instantiate the pinned Python Daytona SDK using `DAYTONA_API_KEY`;
- create the constrained ephemeral GPU sandbox;
- stream the sealed bundle into a private sandbox directory;
- execute the worker through the sandbox process API;
- capture bounded logs and exit status;
- stream the result bundle back;
- validate the result and persist provider-neutral remote diagnostics;
- delete the sandbox in a `finally` path.

The Daytona API key remains on the host and is never placed in the job bundle, environment sent to the sandbox, logs, receipts, or persisted diagnostics.

### Application integration

`PROCESSING_BACKEND=daytona` selects the new remote worker. Missing credentials, an unverified release, an unpinned image, or an invalid resource configuration makes Daytona unavailable rather than falling back silently.

Existing `remoteRunId` API behavior stores the Daytona sandbox ID. The historical internal `runpod_run_id` database column may remain temporarily for backward compatibility, but new application code treats it as provider-neutral storage. New diagnostics use provider-neutral names; historical RunPod diagnostic files remain readable but are not produced.

### Release and verification

RunPod-specific deployment preflight is retired from the active release path. Reusable source-history, manifest, evidence, artifact, tar, and receipt validation moves under a provider-neutral release module.

The canonical gate inventory replaces the optional RunPod container gate with an optional Daytona sandbox gate. Normal CI performs a no-credential contract test and dry run. A real GPU smoke requires both `VERIFY_DAYTONA=1` and `ALLOW_DAYTONA_MUTATION=1`; it must create exactly one ephemeral sandbox, run `nvidia-smi`, import the GPU worker dependencies, process a bounded fixture, download and validate the result, and prove the sandbox was deleted.

The Daytona SDK and all sandbox image/runtime dependencies are pinned. The OCI base must be recorded by immutable digest before the next source freeze; tag-only images are rejected. Release evidence records the SDK version, image digest, target, GPU type, sandbox ID, timestamps, command results, artifact hashes, cleanup result, and confirmation that no RunPod or registry mutation occurred.

## Data flow

1. The local application creates a job and resolves manifest-backed runtime options.
2. Preflight validates the clean metadata commit, frozen source ancestry, manifest, evidence phase, artifact bytes, Daytona image digest, and resource policy.
3. The host creates one private ephemeral Daytona GPU sandbox.
4. The host streams the sealed bundle to the sandbox.
5. The sandbox independently validates the receipt and all files.
6. The sandbox executes the provider-neutral worker with networking blocked.
7. The worker writes a canonical result bundle and completion receipt.
8. The host downloads and validates both outputs.
9. The application persists the result and provider-neutral diagnostics.
10. The host deletes the sandbox in all terminal paths and records cleanup evidence.

## Failure handling

- Sandbox creation failure: no job bundle is uploaded; the application records a retryable remote-capacity error.
- Upload or receipt mismatch: execution does not start; the sandbox is deleted.
- Spot eviction: the first release uses on-demand capacity. Spot execution is deferred.
- Worker timeout or nonzero exit: bounded logs are downloaded, the result is rejected, and the sandbox is deleted.
- Result schema or digest mismatch: no application result is persisted; the sandbox is deleted.
- Cleanup failure: the job remains failed with the sandbox ID recorded, cleanup is retried with a bounded policy, and the final report does not claim successful cleanup.
- Missing Daytona credentials: remote processing is unavailable; there is no automatic local or RunPod fallback.

## Security boundaries

- The Daytona credential exists only in the host process.
- The sandbox is private and exposes no preview endpoint.
- Workload networking is blocked after image provisioning; all required code and artifacts are uploaded.
- Upload and download paths are allowlisted, relative, normalized, and confined to dedicated roots.
- Source, metadata, artifacts, request, and result are all size- and SHA-256-bound.
- Commands are passed through fixed argument contracts; job data is never interpolated into a shell command.
- Logs are bounded and redact credentials, signed URLs, local absolute paths, and artifact origins.
- Resource creation is impossible unless the explicit mutation flag is present.

## Testing and acceptance

The implementation uses test-driven development and independent specification and quality review.

Acceptance requires:

- unit tests for configuration, request/receipt schemas, path containment, streaming uploads/downloads, result validation, failure classification, and guaranteed cleanup;
- adapter tests against a fake Daytona client proving exact resource requests and zero mutation on invalid configuration;
- worker tests with no provider imports and no network access;
- canonical verifier and CI updated to the exact Daytona gate contract;
- a clean disposable installation with a pinned Daytona SDK;
- one authorized real Daytona GPU smoke proving GPU visibility, worker imports, artifact materialization, bounded fixture processing, validated result download, and sandbox deletion;
- a new source/metadata/evidence freeze after all RunPod-to-Daytona product changes;
- documentation that identifies Daytona as the only active remote provider and RunPod as retired historical code;
- no RunPod call, registry push, history rewrite, model/data deletion, or unrelated architectural refactor.

## Migration sequence

1. Preserve the interrupted uncommitted RunPod dependency experiment as recovery evidence, then remove it from the active worktree.
2. Add provider-neutral worker and release-validation boundaries.
3. Add the Daytona adapter and configuration with fake-client tests.
4. Switch the application job path and diagnostics to Daytona.
5. Retire active RunPod adapter, deployment scripts, dependencies, tests, and documentation while retaining Git history and explicit retirement notes.
6. Update the canonical verifier and CI.
7. Run the full non-cloud verifier and freeze a new source commit.
8. Generate metadata and pre-cloud verification evidence.
9. Run one explicitly authorized ephemeral Daytona GPU smoke and verify deletion.
10. Publish final evidence, operational documentation, and the stabilization report.

## Deferred optimizations

After the one-shot release is proven, a separate design may add a Daytona snapshot, warm pool, volume, spot GPU policy, or token-authenticated service endpoint. None is required for the stabilization release.
