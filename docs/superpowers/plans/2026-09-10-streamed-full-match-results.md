# Streamed Full-Match Results Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import a production-sized Daytona tracking result without materializing the complete encoded artifact or complete raw-row graph on the host.

**Architecture:** ResultBundle v2 keeps the existing two-artifact generation and hash chain, but represents the processor artifact as one bounded canonical metadata line followed by bounded canonical row lines. The host consumes that file once through a validated iterator, streams raw rows into atomic storage, and retains only frame-level state and compact ball/counter data; ResultBundle v1 remains readable under its existing 64 MiB limit.

**Tech Stack:** Python 3.12 standard library (`json`, file descriptors, iterators), Pydantic models already in the repository, pytest.

**Spec:** `docs/superpowers/specs/2026-09-10-streamed-full-match-results-and-live-progress-design.md`

## Global Constraints

- Keep exactly two result artifacts and the existing completion-to-result-to-artifact SHA-256 chain.
- V2 format is exactly `jsonl-v1`; processor filename is exactly `result.processor-result.jsonl`.
- Shared processor maximum is 1 GiB; metadata line maximum is 64 MiB; row line maximum is 64 KiB.
- V1 remains capped at 64 MiB and is never guessed to be v2.
- Do not add a dependency, cloud call, or Daytona smoke.
- All local publication remains temp-file, file-fsync, replace, and parent-fsync protected.
- Any v2 import or analytics failure must roll back through `Storage.remote_result_import`.

---

### Task 1: Version and bind the processor-result contract

**Files:**
- Modify: `backend/app/remote_contracts.py`
- Test: `backend/tests/test_remote_contracts.py`

**Interfaces:**
- Consumes: existing `FileEntry`, generation-path validation, `ResultBundle.from_mapping()`.
- Produces: `MAX_PROCESSOR_RESULT_BYTES`, `MAX_PROCESSOR_METADATA_LINE_BYTES`, `MAX_PROCESSOR_ROW_LINE_BYTES`, and ResultBundle properties `processor_format: str` and `processor_row_count: int | None`.

- [ ] **Step 1: Write failing v1/v2 contract tests**

```python
def test_result_bundle_v2_binds_line_framed_processor_artifact():
    result = ResultBundle(
        2, JOB, MATCH, COMMIT, MANIFEST_SHA, RECEIPT_SHA, {},
        {
            "processorResultPath": f"{GEN}/result.processor-result.jsonl",
            "processorResultFormat": "jsonl-v1",
            "processorRowCount": 2,
            "progressPath": f"{GEN}/result.progress.jsonl",
            "progressEventCount": 1,
        },
        (processor_entry, progress_entry),
    )
    assert ResultBundle.from_mapping(result.to_mapping()) == result

def test_result_bundle_v2_rejects_unknown_format(valid_v2_mapping):
    valid_v2_mapping["result"]["processorResultFormat"] = "unknown"
    with pytest.raises(RemoteContractError):
        ResultBundle.from_mapping(valid_v2_mapping)

def test_result_bundle_v1_rejects_v2_fields(valid_v1_mapping):
    valid_v1_mapping["result"]["processorRowCount"] = 2
    with pytest.raises(RemoteContractError):
        ResultBundle.from_mapping(valid_v1_mapping)
```

- [ ] **Step 2: Run the contract tests and confirm the v2 case fails**

Run: `python3 -m pytest -q backend/tests/test_remote_contracts.py -k 'result_bundle_v2 or result_bundle_versions'`

Expected: FAIL because schema version 2 and the v2 fields are rejected.

- [ ] **Step 3: Implement conditional v1/v2 parsing with one shared size constant**

```python
MAX_PROCESSOR_RESULT_BYTES = 1 << 30
MAX_PROCESSOR_METADATA_LINE_BYTES = 64 * 1024 * 1024
MAX_PROCESSOR_ROW_LINE_BYTES = 64 * 1024
PROCESSOR_RESULT_FORMAT = "jsonl-v1"

def _result_schema(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in (1, 2):
        raise RemoteContractError("result schemaVersion must be integer 1 or 2")
    return value
```

In `ResultBundle.__post_init__`, preserve the exact v1 keys/name and require the exact five v2 keys, `jsonl-v1`, non-negative bounded row count, the `.jsonl` fixed name, two same-generation artifacts, and canonical mapping round-trip.

- [ ] **Step 4: Run the complete remote-contract suite**

Run: `python3 -m pytest -q backend/tests/test_remote_contracts.py`

Expected: PASS, including unchanged v1 round trips.

- [ ] **Step 5: Commit the contract**

```bash
git add backend/app/remote_contracts.py backend/tests/test_remote_contracts.py
git commit -m "feat: version line-framed GPU results"
```

### Task 2: Publish processor-result v2 from the sealed GPU worker

**Files:**
- Modify: `backend/app/gpu_worker.py`
- Test: `backend/tests/test_gpu_worker.py`

**Interfaces:**
- Consumes: Task 1 constants and ResultBundle v2 constructor.
- Produces: `_processor_result_v2_chunks(processor_result) -> tuple[Iterator[bytes], int]`; worker generations containing `result.processor-result.jsonl`.

- [ ] **Step 1: Write failing serializer and publication tests**

```python
def test_processor_v2_writes_metadata_then_exact_canonical_rows():
    chunks, row_count = _processor_result_v2_chunks({"rows": [ROW_1, ROW_2], "trackColors": {}})
    assert row_count == 2
    assert b"".join(chunks) == (
        canonical_json_bytes({"schemaVersion": 1, "rowCount": 2, "metadata": {"trackColors": {}}})
        + canonical_json_bytes(ROW_1)
        + canonical_json_bytes(ROW_2)
    )

def test_worker_v2_failure_never_publishes_completion(tmp_path, monkeypatch):
    monkeypatch.setattr(gpu_worker, "MAX_PROCESSOR_RESULT_BYTES", 128)
    with pytest.raises(WorkerError, match="size limit"):
        gpu_worker._write_generation_processor(
            tmp_path, owned_generation(tmp_path),
            {"rows": [{"Frame_ID": 0, "payload": "x" * 256}]},
        )
    assert not (tmp_path / "completion.json").exists()
```

- [ ] **Step 2: Run the focused worker tests and confirm they fail**

Run: `python3 -m pytest -q backend/tests/test_gpu_worker.py -k 'processor_v2 or worker_v2_failure'`

Expected: FAIL because the v2 chunk function and `.jsonl` generation do not exist.

- [ ] **Step 3: Implement the minimal line-framed encoder**

```python
def _processor_result_v2_chunks(value: object) -> tuple[Iterator[bytes], int]:
    _validate_processor_result(value)
    metadata = dict(value)
    rows = metadata.pop("rows")
    if type(rows) is not list or not rows:
        raise WorkerError("processor result rows are invalid")
    header = _processor_json_line(
        {"schemaVersion": 1, "rowCount": len(rows), "metadata": metadata},
        maximum=MAX_PROCESSOR_METADATA_LINE_BYTES,
    )
    def chunks():
        yield header
        for row in rows:
            if type(row) is not dict:
                raise WorkerError("processor result row is invalid")
            yield _processor_json_line(row, maximum=MAX_PROCESSOR_ROW_LINE_BYTES)
    return chunks(), len(rows)

def _processor_json_line(value: object, *, maximum: int) -> bytes:
    encoded = (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    if len(encoded) > maximum:
        raise WorkerError("processor result line exceeds size limit")
    return encoded
```

Use a shallow `dict(value)` before `pop` if callers still need the original mapping. Pass the iterator to `_write_generation_stream`, publish ResultBundle schema 2 with the declared format/count, and update fixed generation names and descriptor validation.

- [ ] **Step 4: Prove exact/max-plus-one behavior and run the worker suite**

Run: `python3 -m pytest -q backend/tests/test_gpu_worker.py`

Expected: PASS; exact maximum publishes, maximum-plus-one leaves no completion marker, and existing durability/generation tests remain green.

- [ ] **Step 5: Commit the worker producer**

```bash
git add backend/app/gpu_worker.py backend/tests/test_gpu_worker.py
git commit -m "feat: publish line-framed GPU results"
```

### Task 3: Validate v2 artifacts through a one-shot host iterator

**Files:**
- Modify: `backend/app/remote_worker.py`
- Test: `backend/tests/test_remote_worker.py`

**Interfaces:**
- Consumes: Task 1 ResultBundle properties and constants; existing `_open_preflight_regular_file`.
- Produces: `ProcessorResultStream(metadata: dict[str, object], row_count: int, rows: Iterator[dict[str, object]])` as a context-managed one-shot source; `_load_processor_result_source(result, job_id, match_id)` returning v1 object or v2 source.

- [ ] **Step 1: Write failing bounded-parser tests**

```python
def test_v2_loader_yields_rows_once_without_legacy_whole_read(result_v2, monkeypatch):
    monkeypatch.setattr(remote_worker, "_read_result_artifact", lambda *_a, **_k: pytest.fail("whole read"))
    with remote_worker._load_processor_result_source(result_v2, job_id=JOB, match_id=MATCH) as source:
        assert source.metadata == {"trackColors": {}}
        assert list(source.rows) == [ROW_1, ROW_2]
        with pytest.raises(RuntimeError, match="already consumed"):
            list(source.rows)

def test_v2_loader_rejects_wrong_row_count(result_v2):
    result_v2.result["processorRowCount"] = 3
    with pytest.raises(RuntimeError, match="Daytona processor result is invalid"):
        with remote_worker._load_processor_result_source(result_v2, job_id=JOB, match_id=MATCH) as source:
            list(source.rows)
```

- [ ] **Step 2: Run the focused importer tests and confirm they fail**

Run: `python3 -m pytest -q backend/tests/test_remote_worker.py -k 'v2_loader'`

Expected: FAIL because only the legacy whole-JSON loader exists.

- [ ] **Step 3: Implement descriptor-bound line parsing**

```python
@dataclass(slots=True)
class ProcessorResultStream:
    metadata: dict[str, object]
    row_count: int
    rows: Iterator[dict[str, object]]

def _canonical_line(handle, maximum: int) -> tuple[bytes, object]:
    raw = handle.readline(maximum + 1)
    if not raw.endswith(b"\n") or len(raw) > maximum:
        raise ValueError
    value = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    if _processor_json_bytes(value, maximum=maximum) != raw:
        raise ValueError
    return raw, value
```

Open once with no-follow, check declared entry before reading, hash every raw line, enforce exact count and non-decreasing `Frame_ID`, then compare bytes/hash and fd/named inode snapshots at EOF. Convert every internal failure to the existing secret-safe `RuntimeError`.

- [ ] **Step 4: Run legacy and v2 importer tests**

Run: `python3 -m pytest -q backend/tests/test_remote_worker.py`

Expected: PASS; v1 still calls `_load_processor_result` and remains capped at 64 MiB.

- [ ] **Step 5: Commit the streaming source**

```bash
git add backend/app/remote_worker.py backend/tests/test_remote_worker.py
git commit -m "feat: stream validated GPU result rows"
```

### Task 4: Stream raw rows into storage and fold frames locally

**Files:**
- Modify: `backend/app/storage.py`
- Modify: `backend/app/analytics.py`
- Modify: `backend/app/processor.py`
- Modify: `backend/app/remote_worker.py`
- Create: `backend/tests/test_storage_streaming.py`
- Test: `backend/tests/test_processor.py`
- Test: `backend/tests/test_remote_worker.py`

**Interfaces:**
- Consumes: Task 3 `ProcessorResultStream`.
- Produces: `Storage.save_raw_rows(match_id: str, rows: Iterable[dict])`; `normalize_tracking_rows(rows: Iterable[dict])`; `persist_remote_video_result_stream(storage, job_id, source)`.

- [ ] **Step 1: Write failing one-shot persistence and rollback tests**

```python
def test_save_raw_rows_streams_a_one_shot_iterable(storage, match):
    class OneShotRows:
        def __init__(self):
            self.iterations = 0
        def __iter__(self):
            self.iterations += 1
            if self.iterations > 1:
                raise AssertionError("rows iterated twice")
            yield ROW_1
            yield ROW_2
    rows = OneShotRows()
    storage.save_raw_rows(match.id, rows)
    assert storage.load_raw_rows(match.id) == [ROW_1, ROW_2]
    assert rows.iterations == 1

def test_remote_stream_persists_the_same_rows_and_frames(storage, ready_job):
    rows = [
        {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 50.0, "Y": 34.0, "Conf": 0.9},
        {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 7, "X": 48.0, "Y": 34.0, "Conf": 0.8},
    ]
    source = ProcessorResultStream({"trackColors": {}}, len(rows), iter(rows))
    persist_remote_video_result_stream(storage, ready_job.id, source)
    assert storage.load_raw_rows(ready_job.matchId) == rows
    frame = storage.load_frames(ready_job.matchId)[0]
    assert (frame.frameId, frame.ball.x, frame.unassignedPlayers[0].id) == (0, 50.0, 7)

def test_remote_stream_failure_restores_existing_outputs(storage, ready_job):
    frames_path = storage._match_dir(ready_job.matchId) / "frames.json"
    before = frames_path.read_bytes()
    def broken_rows():
        yield {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 50.0, "Y": 34.0, "Conf": 0.9}
        raise RuntimeError("stream failed")
    with pytest.raises(RuntimeError), storage.remote_result_import(ready_job.matchId):
        persist_remote_video_result_stream(
            storage, ready_job.id, ProcessorResultStream({"trackColors": {}}, 2, broken_rows())
        )
    assert frames_path.read_bytes() == before
```

- [ ] **Step 2: Run the focused storage/processor tests and confirm they fail**

Run: `python3 -m pytest -q backend/tests/test_storage_streaming.py backend/tests/test_processor.py backend/tests/test_remote_worker.py -k 'one_shot or remote_stream'`

Expected: FAIL because list materialization and the stream entry point remain.

- [ ] **Step 3: Generalize the existing atomic JSON writer for an iterable array**

```python
def _write_json_array(path: Path, values: Iterable[object]) -> None:
    with _atomic_text_destination(path) as handle:
        handle.write("[")
        first = True
        for value in values:
            if not first:
                handle.write(",")
            first = False
            for chunk in json.JSONEncoder(separators=(",", ":")).iterencode(value):
                handle.write(chunk)
        handle.write("]")
```

Extract only the current temp/fd/fsync/replace sequence into `_atomic_text_destination`; keep `_write_json` behavior and all failure cleanup tests unchanged. `save_raw_rows` routes iterable rows through `_write_json_array`.

- [ ] **Step 4: Fold classified rows into frame state during the storage pass**

```python
def persisted_rows():
    for raw in source.rows:
        classified = classify_one_video_row(raw, cluster_result, selected_cluster)
        add_tracking_row(grouped_frames, classified)
        if raw.get("Entity_Type") == "ball":
            ball_rows.append(dict(raw))
        counters.observe(raw)
        yield raw

storage.save_raw_rows(match_id, persisted_rows())
frames = [grouped_frames[key] for key in sorted(grouped_frames)]
```

Reuse the existing classification and normalization rules by extracting their single-row bodies; do not create a parallel algorithm. Feed compact ball rows into truth normalization, then run existing frame analytics and persistence unchanged.

- [ ] **Step 5: Route v2 through streaming persistence and run affected suites**

Run: `python3 -m pytest -q backend/tests/test_storage_streaming.py backend/tests/test_analytics.py backend/tests/test_processor.py backend/tests/test_remote_worker.py`

Expected: PASS with semantic parity and rollback coverage.

- [ ] **Step 6: Commit host persistence**

```bash
git add backend/app/storage.py backend/app/analytics.py backend/app/processor.py backend/app/remote_worker.py backend/tests/test_storage_streaming.py backend/tests/test_analytics.py backend/tests/test_processor.py backend/tests/test_remote_worker.py
git commit -m "feat: persist remote rows without host materialization"
```

### Task 5: Prove capacity and close F10 documentation

**Files:**
- Modify: `backend/tests/test_gpu_worker.py`
- Modify: `backend/tests/test_remote_worker.py`
- Modify: `docs/status/current.md`

**Interfaces:**
- Consumes: completed Tasks 1-4.
- Produces: measured 621,000-row serialization/import evidence and current-status acceptance record.

- [ ] **Step 1: Add an opt-in full-scale capacity test and a default proportional-memory guard**

```python
@pytest.mark.skipif(os.getenv("RUN_FULL_MATCH_CAPACITY") != "1", reason="opt-in capacity test")
def test_621000_rows_round_trip_with_bounded_host_memory(tmp_path):
    peak = import_production_shaped_rows(tmp_path, row_count=621_000)
    assert peak < 256 * 1024 * 1024

def test_streaming_import_peak_does_not_scale_with_encoded_copies(tmp_path):
    small = measured_import_peak(tmp_path, 10_000)
    large = measured_import_peak(tmp_path, 100_000)
    assert large - small < 96 * 1024 * 1024
```

- [ ] **Step 2: Run default capacity and all backend tests**

Run: `python3 -m pytest -q backend/tests/test_gpu_worker.py backend/tests/test_remote_worker.py`

Run: `python3 -m pytest -q backend/tests`

Expected: PASS with the full-scale test explicitly skipped unless enabled.

- [ ] **Step 3: Run the opt-in 621,000-row measurement**

Run: `RUN_FULL_MATCH_CAPACITY=1 python3 -m pytest -q backend/tests/test_remote_worker.py -k 621000`

Expected: PASS and peak memory below 256 MiB on the host importer path.

- [ ] **Step 4: Record the exact result in current status**

```markdown
- F10 is locally closed: ResultBundle v2 line-frames processor rows, v1 remains bounded at 64 MiB, and the opt-in 621,000-row host import passed below the 256 MiB peak-memory ceiling with exact count/hash validation.
```

- [ ] **Step 5: Commit capacity evidence and status**

```bash
git add backend/tests/test_gpu_worker.py backend/tests/test_remote_worker.py docs/status/current.md
git commit -m "test: prove full-match result capacity"
```
