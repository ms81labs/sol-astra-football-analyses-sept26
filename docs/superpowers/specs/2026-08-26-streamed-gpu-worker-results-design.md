# Streamed GPU Worker Results Design

## Scope

Task 4 publishes the complete provider-neutral processor output without placing production-scale football rows inside the bounded `ResultBundle` envelope. This design does not integrate the Task 7 persistence adapter and does not add cloud behavior.

## Contract

`FileEntry` supports `result_artifact` as an output-only role. `JobReceipt` rejects that role and continues to require the exact sealed input-role set. `ResultBundle.artifacts` accepts only `result_artifact` entries.

The worker publishes two deterministic sidecars beside the requested result bundle:

- `<result-stem>.processor-result.json` contains the full canonical processor result.
- `<result-stem>.progress.jsonl` contains the validated canonical progress events.

The small `ResultBundle.result` mapping contains `processorResultPath`, `progressPath`, and `progressEventCount`. The paths must exactly select the two `result_artifact` entries. Task 7 adapters can consume those references without assuming an inline `processorResult` or progress list.

## Streaming and limits

The processor result is validated iteratively as exact built-in JSON containers and scalar types. Validation is cycle-safe, rejects non-finite numbers, credentials, hostile subclasses/protocol objects, excessive depth, oversized strings or keys, and a high explicit node ceiling suitable for full-match output. Canonical JSON is emitted with sorted keys, compact separators, UTF-8, and `allow_nan=False` through `JSONEncoder.iterencode`.

The processor artifact ceiling is 1 GiB. This is intentionally at most one tenth of the 10 GiB Daytona disk allocation so temporary publication, the final artifact, progress, bundle, and runtime materialization retain disk headroom. Progress keeps the existing 16 MiB total and 64 KiB line ceilings.

## Transaction and validation

Before deleting or publishing anything, the worker loads and validates the request and receipt, validates every sealed file, derives all four output paths, and rejects any overlap among outputs, the request, the receipt, or any sealed receipt path.

Each sidecar is written incrementally to a same-directory temporary file while counting bytes and hashing. The worker flushes and fsyncs the file, atomically renames it, and fsyncs the parent directory. The result bundle and completion receipt use the same durable atomic publication boundary. Failure rolls back the processor sidecar, progress sidecar, result bundle, and completion receipt; inability to confirm absence raises `WorkerRollbackIndeterminate`.

`validate_result(..., output_root=...)` verifies both sidecar identities and their exact envelope path bindings. `validate_completion` verifies the result bundle identity and invokes sidecar validation.

## Runtime artifacts and credentials

Runtime artifact declarations are checked against `configured_runtime_artifact_max_bytes()` before copying, and copied snapshots are rehashed with the same ceiling. No network or provider fallback is introduced.

Credential detection and redaction additionally recognize PEM private-key headers, OpenAI project tokens, AWS access-key identifiers, and credential-bearing URLs while preserving benign lookalikes.

## Testing

Regression coverage includes every sealed-role overlap, malformed request and receipt preservation, at least 10,000 production-shaped rows with bounded peak memory and exact hashes, processor artifact size/cycle/NaN/hostile-container failures, sidecar write/fsync/rollback failures, credential-bearing values in detector/redactor/result/progress paths, and configured plus hard runtime artifact ceilings.
