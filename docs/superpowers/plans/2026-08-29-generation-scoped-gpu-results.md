# Generation-Scoped GPU Results Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace four independently committed GPU-worker outputs with one uniquely named, verifiable result generation whose completion receipt is the sole commit marker.

**Architecture:** The worker derives a reserved `<logical-result-name>.generations/` namespace, creates one exclusive 128-bit generation, streams the processor, progress, and result bundle inside it, validates and seals that generation, then publishes the requested completion receipt last. Consumers ignore generation directories and enter only through `validate_completion`, which verifies the completion-to-result-to-artifact hash chain from bounded descriptor snapshots.

**Tech Stack:** Python 3.12 standard library, dataclasses, descriptor-relative filesystem operations, canonical JSON/JSONL, SHA-256, pytest, tracemalloc.

---

### Task 1: Seal generation topology in the remote contracts

**Files:**
- Modify: `backend/app/remote_contracts.py`
- Test: `backend/tests/test_remote_contracts.py`

- [ ] **Step 1: Add failing generation-path contract tests**

Add a fixture that builds one valid generation and update result/completion helpers to use it:

```python
GENERATION_ID = "0123456789abcdef0123456789abcdef"


def generation_paths(name: str = "result.json") -> tuple[str, str, str]:
    root = f"outputs/{name}.generations/{GENERATION_ID}"
    return (
        f"{root}/result.json",
        f"{root}/result.processor-result.json",
        f"{root}/result.progress.jsonl",
    )
```

Cover valid construction and each rejection independently. The cross-generation regression is:

```python
def test_result_rejects_cross_generation_processor_path():
    value = result_for().to_mapping()
    old_path = value["result"]["processorResultPath"]
    new_path = old_path.replace(GENERATION_ID, "f" * 32)
    value["result"]["processorResultPath"] = new_path
    for artifact in value["artifacts"]:
        if artifact["relativePath"] == old_path:
            artifact["relativePath"] = new_path
    with pytest.raises(RemoteContractError):
        ResultBundle.from_mapping(value)
```

Add separate, directly mutated tests for a malformed/uppercase generation identifier, wrong namespace suffix, cross-generation progress path, and each wrong fixed filename so every failure names one violated invariant.

Add completion tests proving `resultPath` must select `result.json` in the same exact `<name>.json.generations/<32-lower-hex>/` shape. Keep normalized-path, bounded-string, mapping/direct-constructor, and hostile-subclass coverage.

- [ ] **Step 2: Run the new contract tests and verify RED**

Run:

```bash
python3 -m pytest backend/tests/test_remote_contracts.py -q \
  -k 'generation or cross_generation or result_topology'
```

Expected: the current suffix-only contract accepts cross-generation and non-generation paths.

- [ ] **Step 3: Implement one shared generation-topology parser**

Add exact constants and a private parser used by both dataclasses:

```python
_GENERATION_ID = re.compile(r"[0-9a-f]{32}\Z")
_GENERATION_NAMESPACE_SUFFIX = ".json.generations"
_GENERATION_RESULT_NAME = "result.json"
_GENERATION_PROCESSOR_NAME = "result.processor-result.json"
_GENERATION_PROGRESS_NAME = "result.progress.jsonl"


def _generation_file(path: PurePosixPath, expected_name: str, label: str) -> PurePosixPath:
    path = _relative(path, label)
    if path.name != expected_name or len(path.parts) < 3:
        raise RemoteContractError(f"{label} is not a generation file")
    generation = path.parent
    if _GENERATION_ID.fullmatch(generation.name) is None:
        raise RemoteContractError(f"{label} has an invalid generation identifier")
    if not generation.parent.name.endswith(_GENERATION_NAMESPACE_SUFFIX):
        raise RemoteContractError(f"{label} has an invalid generation namespace")
    return generation
```

In `ResultBundle.__post_init__`, require the processor and progress files to have their exact fixed names and require both `_generation_file` calls to return the same parent. In `CompletionReceipt.__post_init__`, require `resultPath` to select the fixed result filename in a valid generation.

- [ ] **Step 4: Bind completion, result, and artifacts to one generation**

In `validate_completion`, require:

```python
result_generation = _generation_file(
    completion.result_path, _GENERATION_RESULT_NAME, "resultPath"
)
processor_generation = _generation_file(
    PurePosixPath(result.result["processorResultPath"]),
    _GENERATION_PROCESSOR_NAME,
    "processorResultPath",
)
progress_generation = _generation_file(
    PurePosixPath(result.result["progressPath"]),
    _GENERATION_PROGRESS_NAME,
    "progressPath",
)
if {result_generation, processor_generation, progress_generation} != {result_generation}:
    raise RemoteContractError("completion generation binding mismatch")
```

Continue loading the result payload once from its bounded open descriptor and compare those exact bytes with the supplied `ResultBundle`. Continue validating processor identity and progress identity/content/count from their own bounded descriptor snapshots. Do not add a claim that multiple mutable files form a physical snapshot.

- [ ] **Step 5: Verify Task 1 and commit**

Run:

```bash
python3 -m pytest backend/tests/test_remote_contracts.py -q
python3 -m pytest backend/tests/test_runtime_options.py backend/tests/test_release_manifest.py -q
python3 -m py_compile backend/app/remote_contracts.py backend/tests/test_remote_contracts.py
git diff --check
```

Commit:

```bash
git add backend/app/remote_contracts.py backend/tests/test_remote_contracts.py
git commit -m "feat: seal GPU result generations"
```

### Task 2: Build an exclusive generation lifecycle

**Files:**
- Modify: `backend/app/gpu_worker.py`
- Test: `backend/tests/test_gpu_worker.py`

- [ ] **Step 1: Add failing namespace and generation-layout tests**

Inject deterministic generation identifiers in tests and define the expected layout:

```python
GENERATION_ID = "0123456789abcdef0123456789abcdef"


def expected_generation(result_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    generation = (
        result_path.parent
        / f"{result_path.name}.generations"
        / GENERATION_ID
    )
    return (
        generation,
        generation / "result.json",
        generation / "result.processor-result.json",
        generation / "result.progress.jsonl",
        generation / "completion.json",
    )
```

Test that the logical result path must end in `.json`; the completion path stays outside the generation namespace; the logical path, completion path, and reserved namespace cannot equal or contain a sealed request/receipt/video/manifest/evidence/source/runtime-artifact path; two generated paths cannot overlap; and non-string, short, uppercase, slash-bearing, repeated, or colliding generation identifiers fail closed.

- [ ] **Step 2: Run layout tests and verify RED**

Run:

```bash
python3 -m pytest backend/tests/test_gpu_worker.py -q \
  -k 'generation_layout or generation_namespace or generation_identifier'
```

Expected: the current worker derives four sibling public paths and has no generation lifecycle.

- [ ] **Step 3: Implement pure layout derivation before mutation**

Add an exact immutable layout and injectable identifier source:

```python
@dataclass(frozen=True, slots=True)
class _GenerationLayout:
    namespace: PurePosixPath
    generation: PurePosixPath
    result: PurePosixPath
    processor: PurePosixPath
    progress: PurePosixPath
    completion: PurePosixPath


def _new_generation_id() -> str:
    return secrets.token_hex(16)


def _generation_layout(logical_result: PurePosixPath, generation_id: str) -> _GenerationLayout:
    if logical_result.suffix != ".json":
        raise WorkerError("logical result path must end with .json")
    if type(generation_id) is not str or re.fullmatch(r"[0-9a-f]{32}", generation_id) is None:
        raise WorkerError("generation identifier is invalid")
    namespace = logical_result.with_name(f"{logical_result.name}.generations")
    generation = namespace / generation_id
    return _GenerationLayout(
        namespace,
        generation,
        generation / "result.json",
        generation / "result.processor-result.json",
        generation / "result.progress.jsonl",
        generation / "completion.json",
    )
```

Derive and validate the logical namespace and completion path only after all request/receipt/sealed-file validation, but before creating directories. Reject exact and ancestor/descendant overlap with every sealed path using path-parts comparisons, not string prefixes.

- [ ] **Step 4: Add failing exclusive-creation and durability tests**

Test one and nested namespace creation, existing generation directories, symlink components, changed parent identities, `mkdirat` failure, containing-parent fsync failure, child-open failure, and descriptor closure. Assert that an existing stale generation with a different identifier is preserved.

Use an injected identifier sequence to prove retry behavior:

```python
ids = iter(("0" * 32, "1" * 32))
monkeypatch.setattr(worker, "_new_generation_id", lambda: next(ids))
```

- [ ] **Step 5: Implement descriptor-confined generation creation and retained-failure semantics**

Create namespace and generation components relative to the trusted root descriptor with `O_DIRECTORY | O_NOFOLLOW`. After every successful `mkdir`, fsync the containing parent before opening the child. Record root, namespace, and generation device/inode identities.

Represent the owned lifecycle explicitly:

```python
@dataclass(frozen=True, slots=True)
class _OwnedGeneration:
    layout: _GenerationLayout
    root_identity: tuple[int, int]
    namespace_identity: tuple[int, int]
    generation_identity: tuple[int, int]
```

Do not add generation deletion or rollback helpers. A failed attempt retains its exclusive generation and every partial file exactly as written. Remove the unsafe `_cleanup_owned_generation`, `_rollback_generation_attempt`, and generation-cleanup tests introduced by the earlier Task 2 draft. Keep creation identity records for validation and permission sealing in Task 3.

Add tests proving a simulated failure after generation creation leaves the generation present, never calls `unlink`, `rmdir`, or `chmod`, and does not alter another generation. Stale generations are ignored because no requested completion marker references them.

- [ ] **Step 6: Verify Task 2 and commit**

Run:

```bash
python3 -m pytest backend/tests/test_gpu_worker.py -q \
  -k 'generation_layout or generation_namespace or generation_identifier or generation_creation or retained_generation'
python3 -m pytest backend/tests/test_gpu_worker.py -q -k 'overlap or malformed_preserves'
python3 -m py_compile backend/app/gpu_worker.py backend/tests/test_gpu_worker.py
git diff --check
```

Commit:

```bash
git add backend/app/gpu_worker.py backend/tests/test_gpu_worker.py
git commit -m "refactor: retain uncommitted GPU generations"
```

### Task 3: Make completion the sole commit marker

**Files:**
- Modify: `backend/app/gpu_worker.py`
- Test: `backend/tests/test_gpu_worker.py`

- [ ] **Step 1: Add failing success and discovery tests**

Update successful worker tests so they never load the logical result path. They must load completion first, then follow its result path:

```python
worker.run_worker(request_path, logical_result_path, completion_path)
assert not logical_result_path.exists()
completion = CompletionReceipt.from_mapping(load_canonical_json(completion_path))
result = ResultBundle.from_mapping(load_canonical_json(tmp_path / completion.result_path))
validate_completion(tmp_path, request, receipt, result, completion)
```

Assert the completion points to the injected generation, all four generation files have their fixed names, the result artifact paths select that same generation, the private `completion.json` and public completion path are the same inode, and no other public marker exists.

- [ ] **Step 2: Add failing pre-commit transaction tests**

Parameterize failures across processor write/flush/file-fsync/dir-fsync, progress equivalents, result write, generation validation, completion-source write, permission sealing, and public hard-link creation. Before the completion link succeeds:

```python
with pytest.raises(Exception):
    worker.run_worker(request_path, logical_result_path, completion_path)
assert not completion_path.exists()
assert generation_path.exists()
```

Assert no `unlink`, `rmdir`, or permission restoration occurs. Partial generation contents stay in place. Cover identity changes, unexpected extra generation entries, and simultaneous primary plus temporary-directory-exit errors. Separately inject completion-directory fsync and final identity-confirmation failures after link creation: each raises `WorkerRollbackIndeterminate` and leaves both the generation and created marker untouched.

- [ ] **Step 3: Add failing commit and retry tests**

Prove these distinct outcomes:

- an existing completion is never overwritten and its referenced generation stays byte-for-byte unchanged;
- a failed attempt with generation `0…0` remains uncommitted and a retry with `1…1` commits only the second generation;
- a stale uncommitted generation is ignored by `validate_completion` and does not block a fresh generation;
- once completion publication and containing-directory fsync succeed, the worker returns without post-commit rollback;
- a stable post-commit artifact modification makes a later consumer `validate_completion` fail;
- the worker does not claim that same-privilege concurrent mutation is physically impossible.

- [ ] **Step 4: Migrate `run_worker` to the generation protocol**

Replace the current four-sibling path derivation, early `_remove_publication`, four-file public transaction, and final sequential confirmation with this state machine. Finish the `TemporaryDirectory` processing phase before the public completion commit so no context-manager exit occurs after commit:

```python
# Request, receipt, every sealed byte, config, namespace, and completion
# path are validated before this first mutation.
layout = _generation_layout(logical_result_relative, _new_generation_id())
owned_generation = _create_generation(root, layout)

processor_entry = _write_generation_processor(
    root, owned_generation, processor_result
)
progress_entry, progress_count = _write_generation_progress(
    root, owned_generation, validated_events, request.job_id
)
result = ResultBundle(
    1, request.job_id, request.match_id, receipt.source_commit,
    receipt.manifest_sha256, receipt_sha,
    receipt.requested_runtime_options,
    {
        "processorResultPath": layout.processor.as_posix(),
        "progressPath": layout.progress.as_posix(),
        "progressEventCount": progress_count,
    },
    (processor_entry, progress_entry),
)
result_identity = _write_generation_json(
    root, owned_generation, layout.result, result.to_mapping()
)
validate_result(request, receipt, result, output_root=root)

completion = CompletionReceipt(
    1, request.job_id, request.match_id, layout.result,
    result_identity.size_bytes, result_identity.sha256,
    receipt.source_commit, receipt.manifest_sha256, datetime.now(timezone.utc),
)
validate_completion(root, request, receipt, result, completion)
_write_generation_json(
    root, owned_generation, layout.completion, completion.to_mapping()
)
_seal_generation_read_only(root, owned_generation)
_commit_completion_link(root, owned_generation, completion_relative)
```

The `_write_generation_*` helpers open each fixed final filename directly with `O_CREAT | O_EXCL | O_NOFOLLOW`, stream and hash bytes, file-fsync, and generation-directory-fsync. The generic writer returns `StreamIdentity`; processor/progress wrappers construct only their two `result_artifact` entries. They never create temporary names and never unlink on error. `_commit_completion_link` uses descriptor-relative `os.link(..., follow_symlinks=False)` from the private completion source to the public path, never overwrites, fsyncs the public parent, and confirms both names are the same inode. It never deletes on failure. No generation file is created at the caller's logical result path. After `_commit_completion_link` returns, return success without more fallible work.

- [ ] **Step 5: Seal permissions before commit**

Through held generation descriptors, set the four files to read-only (`0o400`) and the generation directory to read/execute for its owner (`0o500`), fsync the generation directory, and fsync its namespace. Reopen and validate the generation after permission changes and before linking completion. Treat permissions as the application ownership rule, not protection from a privileged process.

On a pre-commit error, do not restore permissions or mutate the retained generation.

- [ ] **Step 6: Remove superseded four-file assumptions**

Delete or replace tests and production branches that require:

- the logical result path to exist;
- processor/progress files beside that logical path;
- rollback of a committed completion;
- `_confirm_owned_publications` as a transaction-wide snapshot claim.
- generation cleanup, permission restoration, and identity-conditional deletion in the hot worker.

Keep the bounded streaming validator, Task 2 input preservation, and completion CLI argument. Remove superseded hot-path `_remove_publication`, `_remove_owned_publications`, `_confirm_owned_publications`, and their deletion-race tests after the generation protocol no longer calls them.

- [ ] **Step 7: Verify Task 3 and commit**

Run:

```bash
python3 -m pytest backend/tests/test_gpu_worker.py -q \
  -k 'generation or commit_marker or retry or streamed_transaction or sidecar'
python3 -m pytest backend/tests/test_gpu_worker.py -q
python3 -m pytest backend/tests/test_remote_contracts.py backend/tests/test_gpu_worker.py backend/tests/test_processor.py -q
python3 -m py_compile backend/app/gpu_worker.py backend/tests/test_gpu_worker.py
git diff --check
```

Commit:

```bash
git add backend/app/gpu_worker.py backend/tests/test_gpu_worker.py
git commit -m "refactor: commit GPU result generations atomically"
```

### Task 4: Prove consumer integrity and full-match bounds

**Files:**
- Modify: `backend/tests/test_remote_contracts.py`
- Modify: `backend/tests/test_gpu_worker.py`
- Modify only if a failing test requires it: `backend/app/remote_contracts.py`
- Modify only if a failing test requires it: `backend/app/gpu_worker.py`

- [ ] **Step 1: Add post-commit consumer integrity tests**

For result, processor, and progress, mutate stable bytes after worker success and assert a fresh consumer validation fails. Test same-size replacement, truncation, growth, changed path binding, changed generation identifier, and a completion copied from another job. Load completion first in every consumer test.

Add a controlled concurrent-change stream that alters an artifact while its one descriptor snapshot is being read; validation must either validate the original open snapshot or fail closed, never combine identity from one open with content from another.

- [ ] **Step 2: Re-run production-scale streaming evidence**

Retain the exact 10,000-row canonical result and tracemalloc test:

```python
assert artifact_size == 1_140_116
assert artifact_sha256 == "4cc5b10599d8b8e09d0a99ed0c8e6dc7e5bd080a9965d0c3cbcadc026faeef37"
assert peak_traced_bytes < int(artifact_size * 0.90)
```

Retain the 20,000,000-node production-capacity derivation and real lowered boundary test. Confirm processor validation and generation publication never materialize the complete encoded artifact a second time.

- [ ] **Step 3: Run full local verification**

Run:

```bash
python3 -m pytest backend/tests/test_remote_contracts.py backend/tests/test_gpu_worker.py backend/tests/test_processor.py -q
python3 -m pytest backend/tests/test_runtime_options.py backend/tests/test_release_manifest.py \
  backend/tests/test_release_evidence.py backend/tests/test_release_preflight.py -q
python3 -m pytest backend/tests -q
python3 -m compileall -q backend/app backend/tests
git diff --check
git status --short
find . -type f \( -name '*.tmp' -o -name 'result.processor-result.json' -o -name 'result.progress.jsonl' \) -print
```

Expected: all suites pass, the worktree is clean after commits, and no generated test artifacts remain.

- [ ] **Step 4: Commit any test-only acceptance additions**

If Step 1 or Step 2 added coverage not already committed with Task 3:

```bash
git add backend/tests/test_remote_contracts.py backend/tests/test_gpu_worker.py \
  backend/app/remote_contracts.py backend/app/gpu_worker.py
git commit -m "test: verify committed GPU result generations"
```

Do not create an empty commit. Any production change requires a demonstrated RED test and another focused GREEN run.

### Task 5: Review and close the streamed-worker checkpoint

**Files:**
- Verify only

- [ ] **Step 1: Run a specification review**

Review the cumulative generation implementation against:

- `docs/superpowers/specs/2026-08-29-generation-scoped-gpu-results-design.md`;
- the still-applicable streaming and limit requirements in `docs/superpowers/specs/2026-08-26-streamed-gpu-worker-results-design.md`;
- Tasks 1–4 above.

Require exact evidence for every namespace, commit-marker, retry, retained-failure, consumer-validation, streaming, capacity, and no-provider requirement. Fix every blocking finding through the same implementer and re-review.

- [ ] **Step 2: Run a code-quality review**

Independently probe descriptor lifecycle, no-follow confinement, no-clobber publication, marker durability, absence of hot-path deletion, retained partial generations, stale generations, retry behavior, bounded validation, canonical bytes, concurrency semantics, and exception chaining. Fix every blocking finding and re-review until approved.

- [ ] **Step 3: Confirm the committed checkpoint**

Run the full Task 4 verification again from the final reviewed HEAD. Confirm that commits after `1657fbaf` contain only the approved design, plan, contract, worker, and test changes. Do not add Daytona SDK, credentials, cloud resources, or Task 4 runtime-ceiling work in this checkpoint.
