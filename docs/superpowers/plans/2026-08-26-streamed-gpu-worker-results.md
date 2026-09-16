# Streamed GPU Worker Results Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish complete full-match processor and progress outputs as sealed streamed sidecars while making GPU worker validation and rollback non-destructive and bounded.

**Architecture:** Extend the Task 3 file contract with an output-only `result_artifact` role, then keep the `ResultBundle` envelope small by binding deterministic processor JSON and progress JSONL sidecars. Validate all sealed inputs and every output collision before cleanup; publish all four outputs as one rollback domain using incremental canonical writers with explicit ceilings.

**Tech Stack:** Python 3.12 standard library, dataclasses, canonical JSON/JSONL contracts, pytest, tracemalloc.

---

### Task 1: Separate sealed input and result artifact roles

**Files:**
- Modify: `backend/app/remote_contracts.py`
- Test: `backend/tests/test_remote_contracts.py`

- [ ] **Step 1: Write failing role-domain and path-binding tests**

Add tests proving `FileEntry("result_artifact", ...)` is valid, `JobReceipt` rejects it, `ResultBundle` rejects `runtime_artifact`, accepts exactly two distinct `result_artifact` entries, and requires `processorResultPath` plus `progressPath` to select those entries exactly.

```python
processor = entry("result_artifact", "outputs/result.processor-result.json", b"{}\n")
progress = entry("result_artifact", "outputs/result.progress.jsonl", b"")
result = result_for(artifacts=(processor, progress), result={
    "processorResultPath": processor.relative_path.as_posix(),
    "progressPath": progress.relative_path.as_posix(),
    "progressEventCount": 0,
})
validate_result(req, rec, result, output_root=tmp_path)
```

- [ ] **Step 2: Run the contract tests and verify RED**

Run: `python3 -m pytest backend/tests/test_remote_contracts.py -q -k 'result_artifact or result_path_binding'`

Expected: failures because the role is unsupported and ResultBundle still requires `runtime_artifact`.

- [ ] **Step 3: Implement exact role domains and result bindings**

Define separate `_INPUT_ROLES` and `_FILE_ROLES`, keep receipt validation restricted to `_INPUT_ROLES`, require every result artifact to use `result_artifact`, and require the envelope mapping:

```python
{
    "processorResultPath": "outputs/result.processor-result.json",
    "progressPath": "outputs/result.progress.jsonl",
    "progressEventCount": 0,
}
```

Both paths must be distinct and exactly equal the two artifact paths. Keep existing bounded canonical envelope validation.

- [ ] **Step 4: Run Task 1 tests and verify GREEN**

Run: `python3 -m pytest backend/tests/test_remote_contracts.py -q`

- [ ] **Step 5: Commit the contract change**

```bash
git add backend/app/remote_contracts.py backend/tests/test_remote_contracts.py
git commit -m "feat: bind streamed worker result artifacts"
```

### Task 2: Reject output collisions before cleanup

**Files:**
- Modify: `backend/app/gpu_worker.py`
- Test: `backend/tests/test_gpu_worker.py`

- [ ] **Step 1: Write failing preservation tests**

Parameterize outputs over request, receipt, manifest, evidence, video, source archive, and every runtime artifact. Test malformed request and malformed receipt with pre-existing output files. Assert the worker raises and every original byte remains unchanged.

```python
before = {path: path.read_bytes() for path in sealed_paths}
with pytest.raises(Exception):
    run_worker(request_path, overlapping_result, completion_path)
assert {path: path.read_bytes() for path in sealed_paths} == before
```

Also derive processor/progress paths and reject collisions among all four outputs and all sealed paths.

- [ ] **Step 2: Run preservation tests and verify RED**

Run: `python3 -m pytest backend/tests/test_gpu_worker.py -q -k 'overlap or malformed_preserves'`

Expected: sealed output targets are deleted by the current early `_remove_publication` call.

- [ ] **Step 3: Move cleanup behind complete input validation**

Load the request and receipt, validate receipt files, bind the request path, derive four collision-safe output paths, and reject all overlaps before calling `_remove_publication`. Generalize rollback to an arbitrary tuple of paths without changing the indeterminate error.

- [ ] **Step 4: Run preservation tests and verify GREEN**

Run: `python3 -m pytest backend/tests/test_gpu_worker.py -q -k 'overlap or malformed_preserves'`

### Task 3: Stream processor and progress sidecars transactionally

**Files:**
- Modify: `backend/app/gpu_worker.py`
- Test: `backend/tests/test_gpu_worker.py`

- [ ] **Step 1: Write failing streaming and transaction tests**

Add a 10,000-row production-shaped processor result. Use `tracemalloc` to assert peak writer overhead remains bounded relative to encoded size and validate exact sidecar SHA-256. Add cycle, NaN, hostile mapping/list subclass, excessive depth/node/string, 1 GiB ceiling (with a lowered test override), write, flush/fsync, rename, directory-fsync, validation, and rollback-indeterminate cases.

```python
rows = [{"Frame_ID": i, "Timestamp": i / 25, "Ball_X": 0.5, "Ball_Y": 0.4}
        for i in range(10_000)]
worker.process_video_input = lambda *args, **kwargs: {"rows": rows, "trackColors": {}}
worker.run_worker(request_path, result_path, completion_path)
bundle = ResultBundle.from_mapping(load_canonical_json(result_path))
validate_completion(tmp_path, request, receipt, bundle, completion)
```

- [ ] **Step 2: Run streaming tests and verify RED**

Run: `python3 -m pytest backend/tests/test_gpu_worker.py -q -k 'stream or sidecar or transaction'`

Expected: the old inline result exceeds JSON node limits and no sidecars exist.

- [ ] **Step 3: Implement iterative validation and durable streamed writers**

Add constants `MAX_PROCESSOR_RESULT_ARTIFACT_BYTES = 1 << 30` and a realistic high node ceiling. Validate only exact built-in `dict`, `list`, `str`, `int`, `float`, `bool`, and `None`; track container identities for cycles; enforce depth, key/string, nodes, finite floats, and credentials without copying the graph.

Write `JSONEncoder(...).iterencode(value)` chunks to a same-directory temporary file. Count UTF-8 bytes, update SHA-256, enforce the ceiling before write, flush/fsync, replace, and fsync the directory. Return `FileEntry("result_artifact", relative, size, digest)`. Write progress lines incrementally using their existing canonical bytes.

- [ ] **Step 4: Publish and validate the four-output transaction**

Create both sidecars first, build a small result envelope referencing them, validate with `output_root`, atomically publish the bundle and completion, then call `validate_completion`. On any exception remove sidecars, bundle, and completion; if absence cannot be confirmed raise `WorkerRollbackIndeterminate`.

- [ ] **Step 5: Run streaming tests and verify GREEN**

Run: `python3 -m pytest backend/tests/test_gpu_worker.py -q -k 'stream or sidecar or transaction'`

- [ ] **Step 6: Commit the worker transaction**

```bash
git add backend/app/gpu_worker.py backend/tests/test_gpu_worker.py
git commit -m "feat: stream sealed GPU worker outputs"
```

### Task 4: Harden credential values and runtime artifact ceilings

**Files:**
- Modify: `backend/app/remote_contracts.py`
- Modify: `backend/app/gpu_worker.py`
- Test: `backend/tests/test_remote_contracts.py`
- Test: `backend/tests/test_gpu_worker.py`

- [ ] **Step 1: Write failing credential-value tests**

Cover PEM private-key headers, `sk-proj-...`, AWS access-key identifiers, and URLs containing userinfo or credential query/fragment parameters in detector, redactor, processor result, and progress. Include benign PEM prose, `sk-project`, ordinary public URLs, and non-secret query names.

- [ ] **Step 2: Write failing runtime ceiling tests**

Set `PROOF_RUNTIME_MAX_ARTIFACT_BYTES` below a declared artifact size and assert rejection before `shutil.copyfile`. Cover the hard maximum and each optional artifact reference. Assert the copied snapshot is rehashed using `stream_identity(max_bytes=selected_limit)`.

- [ ] **Step 3: Run Task 4 tests and verify RED**

Run: `python3 -m pytest backend/tests/test_remote_contracts.py backend/tests/test_gpu_worker.py -q -k 'credential_value or artifact_ceiling'`

- [ ] **Step 4: Implement value detection and size enforcement**

Add bounded string-only credential value patterns and safe URL parsing for exact built-in strings. Import and call the network-free `configured_runtime_artifact_max_bytes`, reject manifest declarations over it before any copy, and pass the limit to each destination `stream_identity` call.

- [ ] **Step 5: Run Task 4 tests and verify GREEN**

Run: `python3 -m pytest backend/tests/test_remote_contracts.py backend/tests/test_gpu_worker.py -q`

- [ ] **Step 6: Commit hardening**

```bash
git add backend/app/remote_contracts.py backend/app/gpu_worker.py \
  backend/tests/test_remote_contracts.py backend/tests/test_gpu_worker.py
git commit -m "fix: harden streamed worker boundaries"
```

### Task 5: Full verification

**Files:**
- Verify only

- [ ] **Step 1: Run Task 3 and Task 4 suites**

Run: `python3 -m pytest backend/tests/test_remote_contracts.py backend/tests/test_gpu_worker.py backend/tests/test_processor.py -q`

- [ ] **Step 2: Run runtime and release suites**

Run: `python3 -m pytest backend/tests/test_runtime_options.py backend/tests/test_release_manifest.py -q`

- [ ] **Step 3: Run the full backend suite**

Run: `python3 -m pytest backend/tests -q`

- [ ] **Step 4: Run static and scope checks**

```bash
python3 -m py_compile backend/app/gpu_worker.py backend/app/remote_contracts.py \
  backend/tests/test_gpu_worker.py backend/tests/test_remote_contracts.py
git diff --check
git status --short
```

- [ ] **Step 5: Confirm clean committed scope**

Ensure only the approved contract, worker, tests, design, and plan commits exist after `05531e3a`, and no Task 5/cloud files changed.
