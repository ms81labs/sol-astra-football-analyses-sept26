# Daytona Smoke Recovery Design

## Status and scope

This design recovers the Daytona GPU release lane after the first authorized real smoke failed while Daytona was building the worker image. It supersedes only the failed-smoke recovery and final-verification portions of the approved Daytona GPU execution design. The product boundary remains unchanged: the application owns match upload, preparation, orchestration, validation, analytics, persistence, and presentation; Daytona supplies one private ephemeral GPU computer for the sealed worker job.

The user authorized one corrected real smoke after this design is implemented and all local verification and independent reviews pass. No third sandbox is authorized. RunPod remains retired.

## Incident facts

The first real smoke ran on 2026-09-09 against source commit `6d5c7536487ea026289cdd1420efaeef6232d2a5`, verification commit `b5a0112b06be53b04ca3e0b4dce6ab08d4769fd6`, and manifest SHA-256 `75f3fedfcc91a44b2f00c7f10f2970a74adb7770836c769e1d09ee4882f75a99`.

Daytona allocated sandbox `9c489f49-a57d-46c2-963b-3b5dc33bb475`, but its image build failed in the combined dependency-install and `pip check` step. No football workload or smoke command ran. The SDK raised before returning the allocated sandbox object, so the existing automatic cleanup path had no handle. The exact sandbox was deleted manually and an independent Daytona listing confirmed that the account contained zero sandboxes. No RunPod or registry mutation occurred, no final release evidence was produced, and gate 13 remains failed.

The smoke output file is empty. Exact build-stage timestamps and complete remote build logs were not captured, so the failed subcommand cannot be identified conclusively after the fact.

## Root causes addressed

### Worker image dependency closure

The immutable PyTorch 2.8/CUDA 12.8 base installs `torch`, `torchvision`, and `torchaudio`. The worker lock then replaces Torch with `torch==2.10.0` and torchvision with `torchvision==0.25.0`, but leaves the inherited `torchaudio==2.8.0`. Torchaudio 2.8 requires Torch 2.8, so `pip check` must reject the resulting environment if the locked install completes.

The worker does not import or use torchaudio. The minimal correction is therefore to uninstall inherited torchaudio before installing the hash-locked worker requirements:

```dockerfile
RUN python -m pip uninstall --yes torchaudio \
 && python -m pip install --require-hashes --no-deps -r /tmp/requirements.lock \
 && python -m pip check
```

The base digest and worker lock remain unchanged. `pip check`, `--require-hashes`, and `--no-deps` remain mandatory. The smoke runner's exact Dockerfile expectation changes with the Dockerfile so policy drift still fails locally.

### Allocation ownership and cleanup

Daytona SDK 0.207.0 can allocate a sandbox and then raise while waiting for it to start. The adapter currently stores the sandbox only after `create` returns, which loses the cleanup handle in this failure mode.

The shared `_SdkClient.create` path will generate one 128-bit random ownership token using the Python standard library. It will derive a unique sandbox name from that token and apply an ownership label containing the same token before calling the SDK. If the SDK raises before returning a sandbox, the adapter will look up only that exact unique name. It may adopt the candidate for cleanup only when both the returned name and ownership label exactly match the generated values.

An exact owned candidate enters the existing bounded three-attempt delete-and-confirm loop. A confirmed not-found response means cleanup is complete. A wrong name, wrong label, ambiguous lookup, or other inconclusive result must never trigger deletion and must produce a secret-safe cleanup-not-confirmed error. Exception text is never parsed for sandbox identifiers.

This fix stays in `_SdkClient.create`, so production jobs and the release smoke share the same lifecycle behavior. No new cleanup service, registry, or background reconciler is introduced.

## Corrected smoke flow

The host validates the release binding, immutable image definition, exact hashed lock, bounded fixture, Daytona policy, and triple mutation gate before creation. The API key remains host-only and must not enter repository files, sandbox environment variables, reports, or logs.

The corrected real smoke performs exactly one create call. After the sandbox starts, it proves the requested GPU is present, imports the actual worker runtime, runs the bounded canonical fixture, downloads and validates the result and completion receipt, deletes the sandbox, and independently confirms absence. Creation is never retried inside the run.

Any failure still requires exact owned cleanup and confirmed absence before the attempt can be treated as contained. If ownership or absence cannot be established, execution fails closed and operators inspect Daytona without automatic deletion of any uncertain resource.

## Recovery record

The failed first attempt will be recorded in `docs/recovery/2026-08-24/daytona-gpu-smoke.md`. `docs/status/current.md` will be corrected so it no longer claims that no Daytona sandbox was created. The record will contain the redacted command, release identities, failed sandbox identifier, known build stage, missing evidence, manual deletion, independent zero-sandbox confirmation, and the fact that gate 13 remains incomplete.

The final verification JSON schema remains success-only. The failed attempt belongs in the Markdown recovery record and must not be synthesized into successful `remoteExecution` evidence.

## Release identity recovery

Correcting tracked source invalidates the existing source-to-manifest-to-verifier chain. After the fixes and full local verification pass, the release is rebound in this order:

1. Remove the active manifest and pre-cloud evidence, then commit the corrected source as `S3`.
2. Regenerate the release manifest and current-tree inventory from `S3`, then commit them as `M3`; `M3^` must equal `S3`.
3. Run the canonical credential-free verifier from clean `M3`, producing a fresh untracked receipt bound to `M3` and the new manifest digest.
4. Generate and commit fresh pre-cloud evidence as `E03`.
5. Run build-only preflight and two independent reviews.
6. Use the user's authorization for exactly one corrected Daytona smoke within the receipt's freshness window.
7. Independently confirm the Daytona account has zero sandboxes.
8. Generate success-only final evidence from the real report, append attempt 2 to the recovery record without changing attempt 1, and run deployment preflight.
9. Complete the final verification report and current-status page from a clean checkout without creating another sandbox.

Old release commits and evidence remain in Git history. No history is rewritten.

## Testing and acceptance

Adapter tests must prove allocation-then-raise recovery by exact name and label, confirmed absence, refusal to delete a wrong-name or wrong-label candidate, bounded cleanup attempts, and credential-safe errors. Existing successful-create cleanup behavior must remain covered.

Worker-image tests must fail before the Dockerfile expectation changes and then prove the Dockerfile contains the exact uninstall/install/check sequence. The complete image must build successfully without Daytona credentials before any second cloud mutation. If a local build is impossible for an environmental reason, the corrected smoke remains blocked; a partial dependency check is not sufficient release evidence.

Before the corrected smoke, the focused Daytona, release, evidence, preflight, and verifier tests must pass, followed by the complete credential-free verification script. The worktree must contain no unexpected tracked or untracked changes; the verifier receipt is the sole expected untracked release artifact.

The recovery is accepted only when all of the following are true:

- the worker image builds and `pip check` succeeds;
- all local suites and both independent reviews pass;
- exactly one corrected sandbox was created;
- the GPU/runtime/fixture smoke result is schema-valid and bound to the fresh release chain;
- deletion and independent absence are confirmed;
- the failed and successful attempts are documented truthfully;
- final evidence and deployment preflight pass from the corrected chain;
- Daytona is the only active remote GPU provider and the application retains ownership of all durable football-analysis results.

The exposed API key must be rotated after testing.
