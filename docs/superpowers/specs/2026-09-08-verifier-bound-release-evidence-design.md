# Verifier-Bound Release Evidence Design

**Date:** 2026-09-08
**Status:** Approved by delegated user choice
**Supersedes:** The unbound evidence-writing behavior in the current Daytona stabilization lane

## Problem

The pre-cloud evidence writer currently derives `sourceCommit` from Git `HEAD`, while the release manifest identifies the frozen source commit. At the metadata commit those values differ, so evidence produced by the documented command fails canonical preflight.

The writer also marks every local gate passed without consuming verifier output. A caller can therefore create plausible evidence without a successful `scripts/verify.sh` run, and every gate receives the writer time instead of its observed completion time.

## Chosen approach

Keep verification and evidence publication as two explicit steps. After all twelve non-cloud gates pass, `scripts/verify.sh` writes one untracked canonical success receipt under `.verification/`. The evidence writer must consume that receipt; it may no longer infer passed gates from `--phase` alone.

The receipt records:

- the clean metadata commit at which verification ran;
- the exact release-manifest digest;
- the twelve canonical gate names and commands in order;
- each gate log's SHA-256 digest and filesystem completion timestamp;
- the receipt creation timestamp and tool versions.

Receipt publication also requires a clean tracked tree with no non-ignored untracked files except the canonical verifier logs and receipt path. Tool versions are derived locally and revalidated instead of accepting caller-supplied labels. Log digests are streamed from stable regular-file descriptors whose identity includes ctime, and each successful gate log is touched only after its command exits.

The committed evidence records the manifest's frozen `sourceCommit`, the receipt's `verificationCommit`, and the receipt-derived gate timestamps and log digests. This distinguishes immutable product source from the clean metadata commit actually tested.

## Components

### Canonical verifier

`scripts/verify.sh` removes any prior success receipt before starting. A failed or interrupted gate leaves no receipt. After all twelve local gates pass, it invokes the existing evidence utility in receipt-recording mode. The receipt writer validates the exact gate inventory, log containment, regular-file identity, and manifest availability before publishing atomically.

The optional Daytona gate remains separate. A pre-cloud receipt never claims it passed.

### Evidence writer

The normal `--phase pre_cloud|final --output ...` command loads the receipt from `.verification/receipt.json` by default. It rejects a missing, malformed, stale, reordered, mismatched, dirty, or wrong-commit receipt.

For pre-cloud evidence, current `HEAD` must equal the receipt's `verificationCommit`. For final evidence, the receipt commit may be an ancestor of `HEAD`, because the pre-cloud evidence commit is allowed after verification. In both phases the manifest bytes at the receipt commit must hash to the current manifest digest.

Pre-cloud evidence uses the twelve receipt gates and one pending Daytona gate. Final evidence uses the same twelve receipt gates and derives the Daytona gate completion time and digest from the canonical remote-execution file supplied with `--remote-execution`. That remote record must exactly bind the frozen `sourceCommit`, receipt `verificationCommit`, `manifestSha256`, and a `workerContextSha256` calculated from the sealed context actually held through sandbox creation. Remote creation may not predate the verifier receipt. The evidence writer and final preflight independently rederive the expected worker-context digest.

### Evidence schema and preflight

Schema version remains 2 because no valid Daytona evidence has shipped. It adds:

- top-level `verificationCommit`;
- per-gate `logSha256`, null only for a pending gate.

Strict parsing rejects unknown or missing fields. Preflight requires evidence `sourceCommit` to equal the manifest frozen source, verifies `verificationCommit` ancestry, and confirms the manifest at that commit has the recorded digest. Existing metadata allowlists, freshness, secret scanning, and remote cleanup requirements remain unchanged.

## Data flow

1. Generate the manifest at metadata commit `M`, bound to frozen source `S`.
2. Run `scripts/verify.sh` from clean `M` with Daytona disabled.
3. The verifier writes twelve logs and a success receipt bound to `M` and the manifest digest.
4. The evidence writer reads the manifest plus receipt and writes pre-cloud evidence with `sourceCommit=S` and `verificationCommit=M`.
5. After the one authorized Daytona smoke, the final writer reuses the local receipt and binds gate 13 to the remote-execution record and confirmed deletion.

## Failure handling

- Remove the old receipt before the first gate, so failed reruns cannot reuse success.
- Refuse symlinked/non-regular receipt or log paths and path escapes.
- Refuse missing logs, incorrect commands/order, invalid hashes/timestamps, manifest mismatch, stale receipt, or non-ancestor verification commits. Empty logs remain valid for successful quiet commands such as type checks.
- Strip every inherited `GIT_*` variable from every provenance subprocess, including archive creation, and set only `GIT_NO_REPLACE_OBJECTS=1`. Reject tracked index entries marked assume-unchanged or skip-worktree in both receipt recording and canonical preflight.
- Before constructing a Daytona client, repeat the clean-tree and post-source allowlist validation against the receipt-bound manifest. If sandbox creation returns but the sealed image-context exit fails, attempt bounded synchronous deletion with provider absence checks. If still unconfirmed, carry the opaque sandbox handle in a fixed-message internal error so both execution entrypoints can continue their outer cleanup without exposing provider text.
- Record remote `deletedAt` only after the provider absence check succeeds, and normalize receipt/binding failures to the stable smoke error surface.
- Never overwrite evidence or receipts; the verifier removes its own prior untracked receipt before a new run.
- Keep the rejected `S/M/E0` commits in Git history; do not rewrite history.

## Testing and acceptance

- A failing or interrupted verifier produces no success receipt.
- A successful fake verifier run produces a canonical receipt with twelve real log hashes.
- Evidence generation without a receipt or with tampered logs, manifest, order, commands, commit, or timestamps fails before output creation.
- Generated pre-cloud evidence passes canonical build-only preflight.
- Final evidence binds gate 13 to the remote-execution file and cannot precede confirmed sandbox deletion.
- The source is re-frozen after the fix; metadata and pre-cloud evidence are regenerated into a new `S -> M -> E0` chain.

## Rejected alternatives

- Correcting only `sourceCommit` leaves unverified gate claims.
- Having `scripts/verify.sh` publish committed evidence couples routine CI verification to release state and complicates Task 11.
- Committing raw verifier logs adds noisy, large, environment-specific artifacts; hashes and timestamps provide the required binding while logs remain local audit material.
