# Streamed Full-Match Results and Live Daytona Progress Design

## Status and scope

This design closes audit findings F10 and F12 for the production football path. It replaces the host's whole-JSON processor import with a versioned line-framed result and replaces Daytona's blocking command call with the SDK's native background session command. It preserves the existing generation-scoped publication, completion receipt, artifact hashes, sandbox deletion, and local rollback rules.

This work does not create another cloud smoke, add a service inside the sandbox, or add a dependency. It does not split videos speculatively. A split-and-reassemble scheduler is required only if representative footage proves that one sealed job cannot fit the measured 1,800-second execution or 10 GiB disk envelope.

## Why the current path is insufficient

The GPU worker permits a processor artifact up to 1 GiB and Daytona streams it to private host staging. The host importer then rejects anything over 64 MiB, copies the complete encoded artifact through a `bytearray` and `bytes`, decodes the complete object graph, and the processor copies the dominant `rows` list again. A production-shaped estimate of 621,000 rows for a 90-minute match at 5 fps is already about 67.5 MiB before richer metadata.

Progress has a separate buffering defect. The football engine already emits stage heartbeats, but the GPU worker retains them in memory until inference finishes. The adapter blocks in `process.exec`, so the database and UI remain near 5% until result import begins.

The installed Daytona Python SDK, pinned at 0.207.0, already supplies the missing primitives: asynchronous session commands, command status and log snapshots, session cleanup, and streamed file downloads. No custom daemon, preview URL, queue, or websocket inside Daytona is needed.

## Considered approaches

### Raise the importer limit

Raising 64 MiB to 1 GiB would make producer and consumer constants agree, but it would retain several complete encoded and decoded copies. It is a compatibility patch, not a full-match design, and is rejected.

### Split every uploaded video first

Fixed video chunks would bound individual artifacts, but they introduce tracker identity, timestamp, homography, ball-state, event, and possession continuity problems at every boundary. They also multiply sandbox startup and transfer costs before runtime evidence says they are necessary. This remains the fallback if a representative match exceeds the sealed single-job envelope.

### Versioned line framing plus native Daytona sessions

This is the selected approach. It changes only the processor artifact representation and command execution mode. The GPU engine may continue to produce its current Python result graph; the host no longer creates complete encoded copies or retains the complete raw-row graph.

## Processor result v2

`JobRequest`, `JobReceipt`, and `CompletionReceipt` remain schema version 1 because their shapes and meaning do not change. `ResultBundle` gains schema version 2.

A v2 result contains exactly these result fields:

- `processorResultPath`
- `processorResultFormat`, fixed to `jsonl-v1`
- `processorRowCount`
- `progressPath`
- `progressEventCount`

The processor filename is fixed to `result.processor-result.jsonl`. The progress filename and the two-artifact generation layout remain unchanged. The result bundle continues to bind both artifact paths, sizes, and SHA-256 digests; all paths must select the same generation.

The processor artifact contains:

1. one canonical header line with schema version, declared row count, and all processor fields except `rows`;
2. exactly `processorRowCount` canonical row-object lines.

The header is bounded to 64 MiB, each row line to 64 KiB, the row count to the existing processor-node envelope, and the complete artifact to the shared 1 GiB processor limit. Blank lines, trailing data, duplicate keys, non-canonical JSON, unsafe values, count mismatches, and unordered frame identifiers fail closed.

The worker validates the complete in-memory result before publication, removes `rows` without copying the remaining graph, writes the header, writes each row, and publishes through the existing exclusive generation stream and completion-marker protocol. A failed v2 write never publishes completion.

The consumer continues to accept v1 results under the legacy 64 MiB whole-JSON ceiling. New workers publish v2 only. Old consumers reject v2 rather than guessing its representation.

## Streaming host import and persistence

The Daytona adapter already downloads artifacts directly to private local files. The v2 importer opens the staged processor file through the existing no-follow descriptor chain and validates its declared path, inode, size, SHA-256, total bytes, line limits, canonical form, row count, and job/match generation binding while consuming it.

The processor receives a one-shot row iterator and metadata. Team clusters are derived from header metadata before rows are consumed. In a single pass:

- each original row is streamed into an atomic `raw_rows.json` array;
- the corresponding classified row is folded into frame state;
- only ball rows and compact counters needed by later trace/truth work are retained;
- the complete raw-row list is never materialized on the host.

`Storage.save_raw_rows` is generalized to accept an iterable and uses `json.JSONEncoder.iterencode` for each item inside the existing temp-file, fsync, replace, and parent-fsync publication pattern. Existing list callers and the public `raw_rows.json` format remain supported.

After the source reaches validated EOF, the existing frame-level analytics, event, formation, shot, match-state, and coaching persistence runs unchanged. Frame state remains resident because it is the semantic input to those algorithms; for a 90-minute match at 5 fps this is about 27,000 frames rather than roughly 621,000 raw detections.

All v2 import and writes remain inside `Storage.remote_result_import`. Any parse, identity, persistence, or analytics failure restores the previous match outputs and removes temporary files. The staged result and bundle cleanup rules remain unchanged.

## Live progress protocol

The GPU worker converts each engine heartbeat into the existing validated `ProgressEvent`. Immediately after validation, it writes and flushes one stdout line with a fixed non-secret marker followed by canonical event JSON. It still records the same events in the final sealed progress JSONL; live logs are telemetry, while the sealed artifact is authoritative.

The adapter creates one fixed, job-scoped Daytona process session and starts `EXECUTION_COMMAND` with `run_async=True`. Approximately every two seconds it:

1. obtains the command status;
2. reads the cumulative stdout snapshot;
3. extracts only complete marked lines;
4. validates job identity, canonical JSON, credential safety, sequence monotonicity, and progress monotonicity;
5. invokes the optional host progress callback once for each new valid sequence.

Malformed, foreign-job, duplicate, regressing, oversized, or partial lines are ignored as untrusted telemetry and never become job state. Log-read failures do not abort GPU work. Command-status failures, timeout, or a nonzero exit use the existing execution failure path. The session is deleted in `finally`; confirmed sandbox deletion remains the authoritative cleanup boundary.

The remote worker persists the latest event and maps worker progress into the reserved host interval from 10% through 85%. It keeps 90% for validated result import and 100% for terminal completion. Existing stage messages are reused.

## Frontend behavior

The existing REST polling path remains the primary client transport. Its interval changes from 250 ms to two seconds, and `waitForJobCompletion` gains an optional update callback. The upload flow stores each returned job record and renders its current message and rounded percentage.

The existing backend job websocket remains available but is not wired into this flow. Adding reconnect, ordering, and REST fallback logic would not improve GPU visibility once two-second polling is sufficient.

## Limits, failure semantics, and trust

- One processor maximum is defined in `remote_contracts.py` and imported by worker, adapter, and v2 importer.
- V1 remains capped at 64 MiB and is never silently treated as v2.
- V2 line and count limits fail at the earliest component able to prove the violation.
- Live progress never authorizes result acceptance; only the sealed completion-to-result-to-artifact hash chain does.
- Provider stdout and exceptions remain redacted. Only validated progress fields may cross into storage or UI.
- Local publication remains atomic and rollback-protected.
- Session cleanup does not replace sandbox cleanup. A sandbox whose destruction cannot be confirmed remains a lifecycle failure.

## Acceptance evidence

Automated tests must prove:

- v1 result contracts and their 64 MiB import boundary remain compatible;
- v2 accepts only the fixed format, fields, filenames, generation, row count, and artifact identities;
- the worker emits exact canonical header/row lines and publishes no completion at maximum-plus-one or malformed input;
- the adapter streams a maximum-size artifact to disk without a complete in-memory copy;
- the importer performs bounded reads, consumes rows once, rejects count/order/line/canonical/digest/inode faults, and rolls back partial local writes;
- a production-shaped 621,000-row import has peak host memory dominated by frame state rather than serialized artifact size;
- worker progress reaches the host before command completion, is delivered once in order, and invalid telemetry cannot update the job;
- timeout, nonzero command, log failure, session cleanup, sandbox cleanup, and local cleanup retain their current fail-closed behavior;
- frontend polling runs at the two-second cadence, exposes intermediate message/percentage, and preserves terminal error handling;
- the full backend and frontend verification suites remain green.

Product acceptance then uses one short real football clip through the API, actual sealed Daytona worker, validated v2 import, and coaching UI. It must show at least one live progress update before completion and expose frames, analytics, and events. Only after that capture may a representative full match be measured. If it exceeds the execution, disk, or worker-memory envelope, a separate chunk design must preserve overlap, global timestamps, track reconciliation, and event/possession continuity before parallel chunk execution is introduced.

## Release impact

The implementation changes worker source, image context, result contract, and frontend assets. Existing v7.3 evidence cannot certify it. A new source commit, manifest binding, clean verifier receipt, image/context digest, preflight, and distinct product acceptance capture are required. The historical successful fourth smoke remains attributed to its original source and must not be repeated or rewritten.
