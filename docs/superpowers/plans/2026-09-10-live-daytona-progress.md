# Live Daytona Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show validated Daytona GPU stage progress in the existing job UI before inference completes, at a bounded request rate.

**Architecture:** The GPU worker emits its already-validated ProgressEvents as marked canonical stdout lines while preserving the sealed final JSONL. Daytona runs the worker in a native asynchronous process session and forwards only new validated events to the remote worker; the frontend keeps its existing REST polling flow at a two-second cadence and renders the returned job message/percentage.

**Tech Stack:** Daytona Python SDK 0.207.0 session API, Python standard library, existing FastAPI/storage job model, React/TypeScript/Vitest.

**Spec:** `docs/superpowers/specs/2026-09-10-streamed-full-match-results-and-live-progress-design.md`

## Global Constraints

- Use Daytona SDK sessions; do not add a sandbox service, queue, dependency, websocket client, or cloud smoke.
- Poll provider command state and frontend job state approximately every two seconds.
- Map worker 0-100 progress into host 0.10-0.85; reserve 0.90 for import and 1.0 for terminal completion.
- Provider logs are untrusted; only complete, canonical, bounded, credential-safe, matching-job, monotonic marked lines may update state.
- Live telemetry never authorizes result acceptance; the sealed final progress artifact remains authoritative.
- Session cleanup does not weaken the existing confirmed sandbox and local-staging cleanup rules.

---

### Task 1: Emit validated live progress from the GPU worker

**Files:**
- Modify: `backend/app/gpu_worker.py`
- Test: `backend/tests/test_gpu_worker.py`

**Interfaces:**
- Consumes: existing `_progress_collector(job_id)` and `ProgressEvent.to_mapping()`.
- Produces: `LIVE_PROGRESS_PREFIX = "FOOTBALL_ANALYST_PROGRESS "`; one flushed canonical event line per accepted callback.

- [ ] **Step 1: Write failing immediate-emission tests**

```python
def test_progress_collector_flushes_a_valid_event_immediately(monkeypatch):
    output = FlushSpy()
    events, state, callback = _progress_collector(JOB, output=output)
    callback({"workerStage": "trackingPass", "stageStatus": "running"})
    assert output.lines == [LIVE_PROGRESS_PREFIX + canonical_json_bytes(events[0].to_mapping()).decode()]
    assert output.flush_count == 1

def test_progress_collector_never_emits_an_unsafe_event():
    output = FlushSpy()
    _, state, callback = _progress_collector(JOB, output=output)
    callback({"message": "api_key=secret"})
    assert state["error"] is True
    assert output.lines == []
```

- [ ] **Step 2: Run the focused tests and confirm they fail**

Run: `python3 -m pytest -q backend/tests/test_gpu_worker.py -k 'collector_flushes or never_emits'`

Expected: FAIL because the collector currently only buffers.

- [ ] **Step 3: Add emission after full event validation**

```python
def _emit_live_progress(event: ProgressEvent, output: TextIO) -> None:
    output.write(LIVE_PROGRESS_PREFIX)
    output.write(canonical_json_bytes(event.to_mapping()).decode("utf-8"))
    output.flush()
```

Inject `output=sys.stdout` into `_progress_collector`, append the event, update state, then emit it. If writing fails, mark progress telemetry invalid and let final worker validation fail before publication; never emit before validation.
Inject `output=sys.stdout` into `_progress_collector`, append the event and update state before attempting emission. Ignore stdout write/flush failures as telemetry loss so the final sealed progress artifact and result can still complete; never emit before validation.

- [ ] **Step 4: Run the GPU-worker suite**

Run: `python3 -m pytest -q backend/tests/test_gpu_worker.py`

Expected: PASS and final sealed progress JSONL remains byte-equivalent to emitted event payloads without the marker.

- [ ] **Step 5: Commit worker progress emission**

```bash
git add backend/app/gpu_worker.py backend/tests/test_gpu_worker.py
git commit -m "feat: emit validated GPU progress live"
```

### Task 2: Execute through a bounded Daytona background session

**Files:**
- Modify: `backend/app/daytona.py`
- Test: `backend/tests/test_daytona.py`

**Interfaces:**
- Consumes: Daytona SDK 0.207.0 methods `create_session`, `execute_session_command(SessionExecuteRequest(..., run_async=True))`, `get_session_command`, `get_session_command_logs`, and `delete_session`.
- Produces: `execute_daytona_job(..., progress_callback: Callable[[ProgressEvent], None] | None = None, poll_wait: Callable[[], None] = ...)`.

- [ ] **Step 1: Replace the fake process with a session-capable fake and write failing tests**

```python
def test_session_delivers_each_valid_progress_event_before_completion(tmp_path):
    process = _Process(session_states=[
        (None, LIVE_PROGRESS_PREFIX + canonical_json_bytes(EVENT_1.to_mapping()).decode()),
        (None, LIVE_PROGRESS_PREFIX + canonical_json_bytes(EVENT_1.to_mapping()).decode() + LIVE_PROGRESS_PREFIX + canonical_json_bytes(EVENT_2.to_mapping()).decode()),
        (0, LIVE_PROGRESS_PREFIX + canonical_json_bytes(EVENT_1.to_mapping()).decode() + LIVE_PROGRESS_PREFIX + canonical_json_bytes(EVENT_2.to_mapping()).decode()),
    ])
    seen = []
    execute_daytona_job(execution(tmp_path, process), progress_callback=seen.append, poll_wait=lambda: None)
    assert seen == [EVENT_1, EVENT_2]
    assert process.deleted_sessions == ["fa-job-1"]

def test_invalid_progress_logs_do_not_abort_a_successful_command(tmp_path):
    process = _Process(session_states=[(0, "FOOTBALL_ANALYST_PROGRESS {not-json}\n")])
    seen = []
    result = execute_daytona_job(execution(tmp_path, process), progress_callback=seen.append, poll_wait=lambda: None)
    assert result.result.job_id == "job-1"
    assert seen == []
```

- [ ] **Step 2: Run the focused adapter tests and confirm they fail**

Run: `python3 -m pytest -q backend/tests/test_daytona.py -k 'session_delivers or invalid_progress_logs'`

Expected: FAIL because execution still calls blocking `process.exec`.

- [ ] **Step 3: Add the exact session methods to `_Process` and construct SDK request lazily**

```python
class _Process(Protocol):
    def create_session(self, session_id: str, request_timeout: float | None = None) -> None: ...
    def execute_session_command(self, session_id: str, req: Any, timeout: int | None = None) -> Any: ...
    def get_session_command(self, session_id: str, command_id: str, request_timeout: float | None = None) -> Any: ...
    def get_session_command_logs(self, session_id: str, command_id: str, request_timeout: float | None = None) -> Any: ...
    def delete_session(self, session_id: str, request_timeout: float | None = None) -> None: ...
```

Keep SDK imports inside the production construction path. The adapter passes a small local request object accepted by fakes and converts it to `sdk.SessionExecuteRequest` in an `_SdkProcess` wrapper.

- [ ] **Step 4: Implement deadline polling and marked-line validation**

```python
def _execute_session(process, request, timeout, progress_callback, poll_wait, monotonic):
    session_id = _session_id(request.job_id)
    process.create_session(session_id)
    try:
        command = process.execute_session_command(session_id, SessionCommand(EXECUTION_COMMAND, True), timeout=timeout)
        deadline = monotonic() + timeout
        last_sequence = -1
        while True:
            status = process.get_session_command(session_id, command.cmd_id)
            last_sequence = _forward_progress_snapshot(
                process, session_id, command.cmd_id, request.job_id, last_sequence, progress_callback
            )
            if status.exit_code is not None:
                if type(status.exit_code) is not int or status.exit_code != 0:
                    raise DaytonaExecutionError("execute: worker returned nonzero")
                return
            if monotonic() >= deadline:
                raise DaytonaExecutionError("execute: worker timed out")
            poll_wait()
    finally:
        process.delete_session(session_id)
```

Treat log fetch/parse/callback exceptions as telemetry loss; treat command/session lifecycle exceptions as execution failure. Never include provider text in errors.

- [ ] **Step 5: Test timeout, nonzero, session cleanup, and sandbox cleanup**

Run: `python3 -m pytest -q backend/tests/test_daytona.py`

Expected: PASS; every path attempts session deletion, and existing sandbox cleanup failures retain precedence.

- [ ] **Step 6: Commit session execution**

```bash
git add backend/app/daytona.py backend/tests/test_daytona.py
git commit -m "feat: stream Daytona session progress"
```

### Task 3: Persist remote progress into the existing job channel

**Files:**
- Modify: `backend/app/remote_worker.py`
- Test: `backend/tests/test_remote_worker.py`

**Interfaces:**
- Consumes: Task 2 `execute_daytona_job(..., progress_callback=...)` and `ProgressEvent`.
- Produces: `_persist_remote_progress(storage, job_id, match_id) -> Callable[[ProgressEvent], None]`.

- [ ] **Step 1: Write a failing pre-completion job-update test**

```python
def test_remote_progress_is_persisted_before_adapter_returns(storage, job, monkeypatch):
    observed = []
    def execute(_request, *, progress_callback, **_kwargs):
        progress_callback(EVENT_TRACKING)
        observed.append(storage.get_job(job.id))
        return _execution_result(tmp_path, job_id=job.id, match_id=job.matchId)
    monkeypatch.setattr(remote_worker, "execute_daytona_job", execute)
    run_remote_job(storage.storage_root, job.id, settings=DAYTONA_SETTINGS)
    assert observed[0].status == "processing"
    assert observed[0].progress == pytest.approx(0.475)
    assert storage.load_analysis_artifact(job.matchId, "remote_worker_progress")["sequence"] == EVENT_TRACKING.sequence
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run: `python3 -m pytest -q backend/tests/test_remote_worker.py -k remote_progress_is_persisted_before_adapter_returns`

Expected: FAIL because no progress callback is passed.

- [ ] **Step 3: Implement the monotonic host mapping with existing messages**

```python
def _persist_remote_progress(storage: Storage, job_id: str, match_id: str):
    last = {"sequence": -1, "progress": 0.0}
    def callback(event: ProgressEvent) -> None:
        mapped = min(0.85, 0.10 + 0.75 * float(event.progress) / 100.0)
        if event.sequence <= last["sequence"] or mapped < last["progress"]:
            return
        storage.save_analysis_artifact(match_id, "remote_worker_progress", event.to_mapping())
        storage.update_job(job_id, status="processing", progress=mapped, message=event.message)
        last.update(sequence=event.sequence, progress=mapped)
    return callback
```

Pass this callback into `execute_daytona_job`. Keep 0.90 before import and the final sealed progress artifact overwrite after result validation.

- [ ] **Step 4: Run the remote-worker suite**

Run: `python3 -m pytest -q backend/tests/test_remote_worker.py`

Expected: PASS for progress, success, failure, and rollback paths.

- [ ] **Step 5: Commit host progress persistence**

```bash
git add backend/app/remote_worker.py backend/tests/test_remote_worker.py
git commit -m "feat: persist live remote worker progress"
```

### Task 4: Show progress in the current upload UI at a bounded poll rate

**Files:**
- Modify: `frontend/src/utils/api.ts`
- Modify: `frontend/src/utils/api.test.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: existing `ProcessingJob` and `fetchJob`.
- Produces: `waitForJobCompletion(jobId, intervalMs = 2000, maxDurationMs, signal, onUpdate?)` and visible job message/percentage.

- [ ] **Step 1: Write failing polling callback/cadence tests**

```typescript
it('reports intermediate jobs and waits two seconds between requests', async () => {
  vi.useFakeTimers();
  const updates: ProcessingJob[] = [];
  vi.stubGlobal('fetch', vi.fn()
    .mockResolvedValueOnce(okJob('queued', 0, 'Queued'))
    .mockResolvedValueOnce(okJob('processing', 0.5, 'Tracking players'))
    .mockResolvedValueOnce(okJob('completed', 1, 'Complete')));
  const completion = waitForJobCompletion('job-1', undefined, 60_000, undefined, (job) => updates.push(job));
  await vi.advanceTimersByTimeAsync(4_000);
  await expect(completion).resolves.toMatchObject({ status: 'completed' });
  expect(updates.map((job) => job.status)).toEqual(['queued', 'processing', 'completed']);
  expect(fetch).toHaveBeenCalledTimes(3);
});
```

- [ ] **Step 2: Run the API test and confirm it fails**

Run: `npm --prefix frontend test -- --run src/utils/api.test.ts`

Expected: FAIL because the default is 250 ms and no callback exists.

- [ ] **Step 3: Add the optional callback and two-second default**

```typescript
export async function waitForJobCompletion(
  jobId: string,
  intervalMs = 2_000,
  maxDurationMs = 60 * 60 * 1000,
  signal?: AbortSignal,
  onUpdate?: (job: ProcessingJob) => void,
): Promise<ProcessingJob> {
  const deadline = Date.now() + maxDurationMs;
  while (true) {
    if (signal?.aborted) throw new Error('Job polling was cancelled.');
    if (Date.now() > deadline) throw new Error('Timed out waiting for job to complete.');
    const job = await fetchJob(jobId);
    onUpdate?.(job);
    if (job.status === 'completed') return job;
    if (job.status === 'failed') throw new Error(job.error || job.message || 'Processing job failed.');
    await new Promise((resolve) => window.setTimeout(resolve, intervalMs));
  }
}
```

- [ ] **Step 4: Render the live message and percentage through existing `jobStatus`**

```typescript
await waitForJobCompletion(upload.jobId, undefined, undefined, undefined, (job) => {
  const percentage = Math.round(job.progress * 100);
  setJobStatus(`${job.message || 'Processing match'} (${percentage}%)`);
});
```

Add an App test around a small exported formatter if full upload rendering would require unrelated mocks:

```typescript
expect(formatJobStatus({ progress: 0.475, message: 'Tracking players' } as ProcessingJob))
  .toBe('Tracking players (48%)');
```

- [ ] **Step 5: Run frontend tests, lint, types, and build**

Run: `npm --prefix frontend test -- --run`

Run: `npm --prefix frontend run lint`

Run: `cd frontend && npx tsc -p tsconfig.app.json --noEmit --incremental false && npx tsc -p tsconfig.node.json --noEmit --incremental false`

Run: `npm --prefix frontend run build`

Expected: all commands PASS.

- [ ] **Step 6: Commit the UI progress path**

```bash
git add frontend/src/utils/api.ts frontend/src/utils/api.test.ts frontend/src/App.tsx frontend/src/App.test.tsx
git commit -m "feat: show live match processing progress"
```

### Task 5: Integrate, verify, and update current status

**Files:**
- Modify: `docs/status/current.md`

**Interfaces:**
- Consumes: completed Tasks 1-4.
- Produces: local verification evidence for F12 and an explicit pending live-product acceptance item.

- [ ] **Step 1: Run the provider-neutral integration test from Task 3 directly**

Run: `python3 -m pytest -q backend/tests/test_remote_worker.py -k remote_progress_is_persisted_before_adapter_returns`

Expected: PASS and the assertion captured the processing job before adapter completion.

- [ ] **Step 2: Run the full local verifier without provider mutation**

Run: `VERIFY_DAYTONA=0 ALLOW_DAYTONA_MUTATION=0 ./scripts/verify.sh`

Expected: backend, sidecar, frontend, lint, type checks, build, preflight-negative tests, and operational-document checks all PASS; Daytona mutation remains disabled.

- [ ] **Step 3: Record closure and the remaining product acceptance gate**

```markdown
- F12 is locally closed: validated worker events reach the job record before completion and the UI polls every two seconds with message/percentage. Live Daytona product acceptance remains pending key rotation and a new release evidence chain; the fourth smoke is not repeated.
```

- [ ] **Step 4: Commit integration evidence status**

```bash
git add backend/tests/test_remote_worker.py docs/status/current.md
git commit -m "test: verify live Daytona progress path"
```
