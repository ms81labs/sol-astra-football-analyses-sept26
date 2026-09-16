# Generation-Scoped GPU Result Publication Design

## Status and scope

This design replaces the four-independent-output publication model in the provider-neutral GPU worker. It preserves streamed processor and progress sidecars, but changes their visibility and commit semantics so a completed match analysis is one verifiable generation.

This work is local and provider-neutral. It does not add Daytona SDK calls, cloud resources, persistence integration, or background garbage collection.

## Why the publication model changes

A mutable filesystem cannot provide a stable snapshot by hashing four public files one after another. A file checked first can change while a later file is being checked. Repeating the sweep only narrows the window; it cannot close it.

The worker therefore stops treating four paths as four independently committed outputs. It writes one private generation and publishes one completion receipt as the commit marker. A successful worker run means that a sealed generation was committed. Readers prove integrity by validating the completion-to-result-to-artifact hash chain at read time.

## Generation layout

The caller still supplies a confined logical result path and a confined completion-receipt path. For a logical result path such as `outputs/result.json`, the worker creates a unique sibling generation:

```text
outputs/
  result.json.generations/
    <32-lowercase-hex-generation-id>/
      result.json
      result.processor-result.json
      result.progress.jsonl
      completion.json
  completion.json
```

The logical result path is a namespace anchor; it is not itself published as a file. Its parent and complete filename deterministically select `result.json.generations/`, avoiding collisions between names that share a stem. The logical filename must end in `.json`. The generation identifier is 128 bits from the operating-system cryptographic random source and is injected in tests. Creation is exclusive and no-follow beneath the trusted bundle root.

The four generation files have fixed names:

- `result.processor-result.json` is the streamed canonical processor result.
- `result.progress.jsonl` is the streamed canonical progress sequence.
- `result.json` is the small canonical `ResultBundle` containing the two artifact paths and progress count.
- `completion.json` is the private source inode for the public completion marker.

`CompletionReceipt.resultPath` points to the generation's `result.json`. The requested completion-receipt path is a hard link to the generation's `completion.json` and is the only externally committed name. The private source remains in the generation; the worker never removes it after linking.

## Sealed contracts

The existing hash chain remains authoritative:

1. `CompletionReceipt` seals the generation `result.json` path, size, and SHA-256.
2. `ResultBundle` seals the exact processor and progress paths, sizes, and SHA-256 values.
3. Progress validation additionally seals canonical JSONL, job identity, monotonicity, credential safety, and event count.
4. Processor output remains identity-validated as a bounded streamed artifact and is not loaded into the small result envelope.

Generation paths must be normalized, confined, and share one exact generation directory. The result bundle must select the fixed processor and progress filenames in that directory. A completion receipt pointing outside the generation namespace, across generations, or to a non-fixed result filename is rejected. No sealed input may equal or descend from the reserved generation namespace, and the completion path must remain outside it.

`validate_completion` remains the consumer entry point. It loads and validates the published result bundle and both artifacts from their recorded paths. Consumers must not use a generation merely because its directory exists.

## Writer and commit protocol

The worker performs these phases in order:

1. Load and validate the request, receipt, sealed files, match configuration, logical result namespace, and completion path without mutation.
2. Create one exclusive generation directory through trusted no-follow directory descriptors. Synchronize every newly created parent entry.
3. Stream processor JSON and progress JSONL directly into their final generation filenames using exclusive no-follow creation. Flush and file-fsync each file, then directory-fsync the generation. A write failure may leave a partial file, but the generation remains uncommitted and invisible to consumers.
4. Build `ResultBundle` with bundle-root-relative artifact paths that all select the same generation, write `result.json` through the same exclusive direct writer, and run `validate_result(request, receipt, result, output_root=root)`.
5. Validate the complete generation through the same descriptor-confined hash chain before commit.
6. Build the completion receipt and write it as the generation's `completion.json`. Validate those exact bytes, make all four generation files read-only, make the generation directory non-writable for normal application processes, then synchronize the directory and containing generation namespace. These permissions express the application ownership rule; they are not claimed as protection against a privileged process.
7. Atomically hard-link the generation's `completion.json` to the requested completion path with descriptor-relative no-clobber semantics. The link operation is the visibility commit point; the containing completion directory is then synchronized.
8. Return success after confirming that the public completion path is the same inode as the private completion source and its containing directory is durably synchronized.

There is deliberately no sequential post-commit attempt to prove that mutable files stayed unchanged. Integrity after commit is established by read-time `validate_completion`.

## Failure and retry semantics

Before completion publication, the generation is uncommitted and invisible to consumers. A failure leaves that unique generation in place exactly as written. The hot worker never unlinks generation files, removes generation directories, restores permissions, or attempts identity-conditional cleanup. Consumers ignore it because the requested completion path is absent.

If completion publication encounters an existing destination, the worker preserves it and fails closed. It never overwrites a prior completed run.

If the public completion link is created but its containing-directory synchronization or final identity confirmation fails, the worker does not delete the marker or generation. It raises `WorkerRollbackIndeterminate`; the marker is either absent or points to a fully written, prevalidated, read-only generation, and an operator can reconcile it through normal consumer validation.

After the completion receipt is durably published, the generation is committed and the worker does not roll it back. A retry with the same completion path fails without modifying the committed generation. A retry after a pre-commit failure creates a new generation identifier, so stale uncommitted directories cannot be mistaken for the new attempt.

Automatic scavenging of stale generations is a later operational concern. Removal requires a separately designed, coordinated cleanup tool that excludes concurrent writers and readers. This task only guarantees that stale generations are uncommitted, ignored, and retained without destructive hot-path races.

## Concurrency and trust model

Only the GPU worker writes inside its generation. Other application components treat generation contents as immutable and access them through `validate_completion`. Validation must read each artifact from one bounded descriptor snapshot so identity and content cannot be mixed across separate opens. No design on a shared mutable filesystem can prevent a privileged or same-owner process from deliberately changing bytes; stable changes are detected by the sealed hashes when consumed, while active concurrent modification makes validation fail closed.

The completion marker provides atomic visibility, not magical filesystem immutability. This distinction is part of the public contract and must be reflected in tests and adapter documentation.

## Limits and streaming guarantees

The current streamed-output bounds remain:

- processor artifact: at most 1 GiB;
- progress artifact: at most 16 MiB total and 64 KiB per canonical line;
- progress events: existing contract maximum;
- processor graph: exact built-in JSON types, finite numbers, bounded depth/keys/strings, cycle safety, and a 20,000,000-node ceiling.

The node ceiling covers the base production estimate of 621,000 rows for 90 minutes at 5 fps and 23 tracked entities. At twelve nodes per basic row, that is at least 7,452,002 nodes; 20 million retains more than twice that base plus additional result structures while the byte ceiling remains the final storage bound.

Processor serialization remains incremental through `JSONEncoder.iterencode`; neither generation publication nor validation may materialize a second complete encoded artifact in memory.

## Testing and acceptance

Tests must prove:

- completion is absent at every pre-commit failure stage;
- incomplete generation directories are never accepted by `validate_completion`;
- completion is published only after all four generation files are durable, read-only, and contract-valid;
- a committed completion validates the exact result and both sidecars;
- cross-generation paths, malformed generation identifiers, wrong fixed filenames, and namespace escapes are rejected;
- retries preserve an existing completion and committed generation;
- pre-commit retries use a fresh generation and cannot confuse stale files with current output;
- pre-commit failures retain their unique generation without any unlink, rmdir, or permission restoration;
- the public completion marker is a no-clobber hard link to the private completion source;
- a post-link durability or identity uncertainty raises `WorkerRollbackIndeterminate` without deletion;
- modifications after commit are detected by consumer validation rather than claimed to be impossible;
- 10,000-row canonical streaming retains bounded traced overhead and exact SHA-256;
- the production capacity, graph, artifact, progress, durability, descriptor-leak, import, and no-network tests remain green.

The full worker, remote-contract, processor, runtime, release, and backend suites must pass before this redesign is considered complete.

## Migration impact

Existing worker tests and contracts that assume the logical `--result` path is a published file must change to follow `CompletionReceipt.resultPath`. Future Daytona and application adapters must download or persist the committed completion receipt first, then resolve and validate the referenced generation.

The previous streamed-result design remains correct for serialization and size limits but is superseded by this document for publication, rollback, retry, and consumer-discovery semantics.
