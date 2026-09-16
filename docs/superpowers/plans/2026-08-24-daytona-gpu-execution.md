# Daytona GPU Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the active RunPod execution and release lane with one fail-closed, ephemeral Daytona GPU job that verifies sealed inputs, returns a validated result, proves cleanup, and completes the paused-project stabilization.

**Architecture:** Extract the existing video-processing body and release checks into provider-neutral modules, then put a narrow Daytona SDK adapter around sandbox lifecycle and streaming file transport. Ordinary CI uses fake clients and a credential-free dry run; one separately gated real smoke creates exactly one private on-demand GPU sandbox and must prove deletion before final evidence can pass.

**Tech Stack:** Python 3.11+, `daytona==0.207.0`, Daytona Cloud GPU sandboxes, PyTorch 2.8/CUDA 12.8 OCI image pinned as `docker.io/pytorch/pytorch@sha256:417bd75df6365104c283ea4c1651fb3530d9eb5a4c2fafa51943cff2a94e6385`, Pydantic/dataclasses, pytest, Bash, GitHub Actions, JSON Schema Draft 2020-12.

---

## Fixed decisions and boundaries

- Active implementation work occurs only in `.worktrees/preservation-stabilization` on branch `preservation-stabilization`.
- Preserve these aborted-release commits; never amend, squash, rebase, or drop them: `fdd677e1`, `0cda392a`, `be1a3400`, `ce8c497a`, `f143476f`, and Daytona design commit `1164d4a9`.
- The current four-file interrupted RunPod dependency experiment is rejected recovery evidence, not Daytona input.
- Daytona is the only active remote provider. Missing or invalid Daytona configuration fails the selected remote job; it never falls back to local processing or RunPod.
- The first release uses one on-demand sandbox, `gpu=1`, preference `[RTX-PRO-6000, H100]`, `spot=False`, `public=False`, `ephemeral=True`, `network_block_all=True`, `cpu=4`, `memory=8 GiB`, `disk=10 GiB`, and TTL 45 minutes.
- The host uses `daytona==0.207.0`. The sandbox base is the immutable Linux/AMD64 image above; tag-only images fail validation.
- The Daytona API key stays on the host. It is never uploaded, passed as sandbox environment, persisted, or logged.
- A real cloud mutation requires all three: `VERIFY_DAYTONA=1`, `ALLOW_DAYTONA_MUTATION=1`, and CLI flag `--real-smoke`.
- A real smoke makes exactly one create call and never retries creation. It must confirm deletion before passing.
- Keep the historical SQLite column `runpod_run_id`; public and new internal code treat it as legacy backing storage for provider-neutral `remoteRunId`.
- Keep `boto3` because portable runtime artifacts still support S3-compatible references.

## File responsibility map

**Create:**

- `backend/app/remote_contracts.py` — exact bundle, receipt, progress, result, and completion schemas plus canonical JSON and streaming identities.
- `backend/app/gpu_worker.py` — provider-free local-file worker CLI.
- `backend/app/daytona.py` — Daytona client protocol, sandbox lifecycle, streaming transport, result verification, and cleanup.
- `backend/app/remote_worker.py` — application job/storage orchestration around the Daytona adapter.
- `backend/release/preflight.py` — provider-neutral Git ancestry, manifest, evidence, artifact, tar, and receipt validation.
- `backend/release/evidence.py` — exact gate inventory and atomic evidence writer.
- `backend/release/daytona_policy.py` — immutable image and resource/mutation policy.
- `backend/release/daytona-v7.3.json` — committed provider policy with immutable image digest and SDK version.
- `backend/release/daytona_execution_schema.json` — exact provider-policy schema.
- `backend/daytona_worker/Dockerfile` — Daytona worker image definition based on the immutable PyTorch image.
- `backend/daytona_worker/requirements.txt` and `backend/daytona_worker/requirements.lock` — exact worker dependency input and hashed lock.
- `backend/scripts/run_daytona_gpu_smoke.py` — credential-free dry run and triply gated real smoke.
- `backend/scripts/write_verification_evidence.py` — atomic schema-validated pre-cloud/final evidence writer.
- `backend/tests/test_remote_contracts.py`
- `backend/tests/test_gpu_worker.py`
- `backend/tests/test_daytona.py`
- `backend/tests/test_remote_worker.py`
- `backend/tests/test_release_preflight.py`
- `backend/tests/test_release_evidence.py`
- `backend/tests/test_daytona_release_policy.py`
- `backend/tests/test_run_daytona_gpu_smoke.py`
- `backend/tests/fixtures/daytona/job-request.json`
- `docs/archive/2026-08-24/rejected-runpod-release.md`
- `docs/runbooks/daytona-gpu-execution.md`
- `docs/recovery/2026-08-24/daytona-gpu-smoke.md`

**Modify:**

- `backend/app/settings.py`, `backend/app/jobs.py`, `backend/app/processor.py`, `backend/app/storage.py`, `backend/app/run_benchmarks.py`
- `backend/requirements-runtime.txt`, `backend/requirements-dev.txt`, `backend/requirements.txt`
- `backend/release/verification_schema.json`, `backend/release/v7.3.json` during the new metadata freeze
- `scripts/verify.sh`, `backend/tests/test_verify_script.py`, `.github/workflows/ci.yml`
- `backend/tests/test_settings.py`, `backend/tests/test_jobs.py`, `backend/tests/test_job_metadata.py`, `backend/tests/test_processor.py`, `backend/tests/test_run_benchmarks.py`
- `README.md`, `SESSION-HANDOFF.md`, `docs/status/current.md`, and the final verification report.

**Retire after parity is proven:**

- `backend/app/runpod.py`, `backend/app/runpod_worker.py`, `backend/runpod_handler/`
- `backend/scripts/runpod_session.py` from active entry points
- Direct RunPod application/release tests after equivalent Daytona/provider-neutral coverage exists.

## Task 1: Preserve and clear the interrupted RunPod dependency experiment

**Files:**

- Preserve on branch: `recovery/interrupted-runpod-lock-2026-08-24`
- Preserve: `backend/runpod_handler/requirements.txt`
- Preserve: `backend/tests/test_runpod_preflight.py`
- Preserve: `backend/runpod_handler/base-constraints.txt`
- Preserve: `backend/runpod_handler/requirements.lock`
- Create on recovery branch: `docs/recovery/2026-08-24/interrupted-runpod-lock-experiment.json`

- [ ] **Step 1: Verify the exact dirty scope and identities**

Run:

```bash
git status --short
sha256sum backend/runpod_handler/requirements.txt \
  backend/tests/test_runpod_preflight.py \
  backend/runpod_handler/base-constraints.txt \
  backend/runpod_handler/requirements.lock
```

Expected: exactly the four paths above; hashes match the review inventory (`bee063…d190`, `4da312…de0`, `8aa3e5…9502`, `f56939…68b`).

- [ ] **Step 2: Move the exact experiment to a recoverable branch**

Run:

```bash
git stash push -u -m "interrupted RunPod dependency experiment before Daytona pivot" -- \
  backend/runpod_handler/requirements.txt \
  backend/tests/test_runpod_preflight.py \
  backend/runpod_handler/base-constraints.txt \
  backend/runpod_handler/requirements.lock
git stash branch recovery/interrupted-runpod-lock-2026-08-24 stash@{0}
```

Expected: recovery branch checked out with the four changes restored.

- [ ] **Step 3: Record recovery metadata and commit the experiment**

Add this exact object with `apply_patch`:

```json
{
  "schemaVersion": 1,
  "baseCommit": "1164d4a9d9dc3025d2f5b76d1b5b8d1e6a91cb74",
  "disposition": "rejected_interrupted_experiment",
  "built": false,
  "pushed": false,
  "deployed": false,
  "reason": "RunPod was retired in favor of Daytona before this dependency lock experiment was completed.",
  "paths": [
    "backend/runpod_handler/requirements.txt",
    "backend/tests/test_runpod_preflight.py",
    "backend/runpod_handler/base-constraints.txt",
    "backend/runpod_handler/requirements.lock"
  ]
}
```

Run:

```bash
git add backend/runpod_handler/requirements.txt backend/tests/test_runpod_preflight.py \
  backend/runpod_handler/base-constraints.txt backend/runpod_handler/requirements.lock \
  docs/recovery/2026-08-24/interrupted-runpod-lock-experiment.json
git commit -m "docs: preserve interrupted RunPod dependency experiment"
git switch preservation-stabilization
git status --short
```

Expected: active worktree clean and recovery branch retains the exact bytes.

## Task 2: Extract provider-neutral release validation

**Files:**

- Create: `backend/release/preflight.py`
- Create: `backend/release/evidence.py`
- Create: `backend/tests/test_release_preflight.py`
- Create: `backend/tests/test_release_evidence.py`
- Modify: `backend/release/__init__.py`
- Source for migration: `backend/runpod_handler/preflight.py`
- Source test for migration: `backend/tests/test_runpod_preflight.py`

- [ ] **Step 1: Write failing import and parity tests**

Add tests that import the new modules and assert the existing canonical gate sequence remains unchanged before the Daytona gate replacement:

```python
def test_provider_neutral_preflight_exports_release_checks() -> None:
    from backend.release.preflight import validate_git_source, validate_release_preflight
    assert callable(validate_git_source)
    assert callable(validate_release_preflight)

def test_evidence_gate_inventory_has_thirteen_entries() -> None:
    from backend.release.evidence import REQUIRED_GATE_COMMANDS
    assert len(REQUIRED_GATE_COMMANDS) == 13
```

- [ ] **Step 2: Run tests and capture RED**

Run: `python3 -m pytest -q backend/tests/test_release_preflight.py backend/tests/test_release_evidence.py`

Expected: import failures because the modules do not exist.

- [ ] **Step 3: Move reusable validation without changing behavior**

Move Git raw-object ancestry, evidence parsing/freshness, manifest/artifact identity, canonical USTAR, sealed receipt, bounded snapshots, and metadata allowlist logic into `backend/release/preflight.py`. Move `VerificationGate`, `VerificationEvidence`, the thirteen-command mapping, and evidence phase rules into `backend/release/evidence.py`. Keep a temporary compatibility import in old preflight:

```python
from backend.release.evidence import REQUIRED_GATE_COMMANDS, VerificationEvidence, VerificationGate
from backend.release.preflight import *  # noqa: F403
```

Rename `validate_preflight` to `validate_release_preflight` and expose the old name only in the compatibility module.

- [ ] **Step 4: Run the full migrated adversarial suite**

Run:

```bash
python3 -m pytest -q backend/tests/test_release_preflight.py backend/tests/test_release_evidence.py
python3 -m pytest -q backend/tests/test_runpod_preflight.py
```

Expected: all migrated and compatibility tests pass with identical rejection behavior.

- [ ] **Step 5: Commit**

```bash
git add backend/release backend/tests/test_release_preflight.py \
  backend/tests/test_release_evidence.py backend/runpod_handler/preflight.py
git commit -m "refactor: extract provider-neutral release validation"
```

## Task 3: Define exact remote bundle and result contracts

**Files:**

- Create: `backend/app/remote_contracts.py`
- Create: `backend/tests/test_remote_contracts.py`

- [ ] **Step 1: Write failing exact-schema and path-boundary tests**

Cover missing/extra keys, noncanonical JSON, absolute paths, `..`, backslashes, symlink escape, duplicate paths, duplicate singleton roles, non-streaming reads, incorrect size/hash, monotonic progress, bounded progress size, result mismatch, completion mismatch, and credential redaction.

Core test shape:

```python
def test_receipt_rejects_traversal() -> None:
    payload = valid_receipt_mapping()
    payload["files"][0]["relativePath"] = "../secret"
    with pytest.raises(RemoteContractError, match="relative POSIX path"):
        JobReceipt.from_mapping(payload)

def test_stream_identity_uses_bounded_reads(tmp_path: Path) -> None:
    source = GuardedReader(b"x" * (3 * 1024 * 1024), max_read=1024 * 1024)
    identity = stream_identity(source)
    assert identity.size_bytes == 3 * 1024 * 1024
```

- [ ] **Step 2: Run tests and capture RED**

Run: `python3 -m pytest -q backend/tests/test_remote_contracts.py`

Expected: module import failure.

- [ ] **Step 3: Implement the immutable contracts**

Use frozen dataclasses with exact-key constructors:

```python
@dataclass(frozen=True, slots=True)
class FileEntry:
    role: Literal["source_archive", "manifest", "evidence", "runtime_artifact", "input_video", "job_request"]
    relative_path: PurePosixPath
    size_bytes: int
    sha256: str

@dataclass(frozen=True, slots=True)
class JobReceipt:
    schema_version: Literal[1]
    source_commit: str
    manifest_sha256: str
    evidence_sha256: str
    job_request_sha256: str
    requested_runtime_options: Mapping[str, object]
    files: tuple[FileEntry, ...]

@dataclass(frozen=True, slots=True)
class CompletionReceipt:
    schema_version: Literal[1]
    job_id: str
    match_id: str
    result_path: PurePosixPath
    result_size_bytes: int
    result_sha256: str
    source_commit: str
    manifest_sha256: str
    completed_at: datetime
```

Implement `canonical_json_bytes`, `stream_identity`, `confined_path`, `atomic_write_json`, progress JSONL validation, result validation, and `redact_remote_diagnostics`. Read and hash in chunks no larger than 1 MiB.

- [ ] **Step 4: Run tests and commit**

```bash
python3 -m pytest -q backend/tests/test_remote_contracts.py
git add backend/app/remote_contracts.py backend/tests/test_remote_contracts.py
git commit -m "feat: add sealed remote job contracts"
```

## Task 4: Extract the provider-free GPU worker

**Files:**

- Create: `backend/app/gpu_worker.py`
- Create: `backend/tests/test_gpu_worker.py`
- Modify: `backend/app/processor.py`
- Source: `backend/runpod_handler/handler.py`

- [ ] **Step 1: Write failing worker-boundary tests**

Tests must prove validation occurs before processing, all manifest artifacts materialize, runtime options equal the receipt, networking is never used, progress is bounded, success writes result and completion receipt atomically, failure exits nonzero without a success result, and temp directories are removed. Add an AST test rejecting provider/network imports:

```python
FORBIDDEN_IMPORTS = {"daytona", "runpod", "boto3", "requests", "urllib", "socket"}

def test_gpu_worker_has_no_provider_or_network_imports() -> None:
    tree = ast.parse(GPU_WORKER.read_text(encoding="utf-8"))
    imported = imported_roots(tree)
    assert imported.isdisjoint(FORBIDDEN_IMPORTS)
```

- [ ] **Step 2: Run tests and capture RED**

Run: `python3 -m pytest -q backend/tests/test_gpu_worker.py`

Expected: module import failure.

- [ ] **Step 3: Implement the fixed local-file CLI**

Expose:

```python
def run_worker(
    request_path: Path,
    result_path: Path,
    completion_receipt_path: Path,
) -> None:
    request = load_and_validate_request(request_path)
    receipt = load_and_validate_receipt(request.receipt_path)
    validate_payload_files(receipt, request_path.parent)
    materialized = materialize_verified_runtime(receipt, request)
    output = process_video_input(request.input_video_path, request.config, materialized)
    result = build_result_bundle(request, output, materialized)
    atomic_write_result_and_completion(result, result_path, completion_receipt_path)
```

CLI arguments are exactly `--request`, `--result`, and `--completion-receipt`. Change `process_remote_video_payload` to `persist_remote_video_result` with `processing_backend="remote"` and `worker_path="gpu_worker"`.

- [ ] **Step 4: Run focused processing tests and commit**

```bash
python3 -m pytest -q backend/tests/test_gpu_worker.py backend/tests/test_processor.py
git add backend/app/gpu_worker.py backend/app/processor.py \
  backend/tests/test_gpu_worker.py backend/tests/test_processor.py
git commit -m "refactor: extract provider-neutral GPU worker"
```

## Task 5: Add pinned Daytona policy, SDK, and settings

**Files:**

- Create: `backend/release/daytona_policy.py`
- Create: `backend/release/daytona-v7.3.json`
- Create: `backend/release/daytona_execution_schema.json`
- Create: `backend/tests/test_daytona_release_policy.py`
- Modify: `backend/app/settings.py`
- Modify: `backend/requirements-runtime.txt`
- Modify: `backend/tests/test_settings.py`

- [ ] **Step 1: Write failing policy and configuration tests**

Test local default, valid Daytona config, unknown backend, missing key, tag-only image, wrong digest syntax, GPU count not one, altered preference/order, spot/public/non-ephemeral configuration, open network, resource overrun, invalid timeouts/TTL, and secret-free serialization.

```python
def test_daytona_backend_requires_complete_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROCESSING_BACKEND", "daytona")
    monkeypatch.delenv("DAYTONA_API_KEY", raising=False)
    with pytest.raises(SettingsError, match="DAYTONA_API_KEY"):
        ProcessingSettings.from_env()
```

- [ ] **Step 2: Run tests and capture RED**

Run: `python3 -m pytest -q backend/tests/test_settings.py backend/tests/test_daytona_release_policy.py`

- [ ] **Step 3: Add exact policy and SDK pin**

Add `daytona==0.207.0` to runtime requirements. Commit this policy JSON:

```json
{
  "schemaVersion": 1,
  "sdkVersion": "0.207.0",
  "image": "docker.io/pytorch/pytorch@sha256:417bd75df6365104c283ea4c1651fb3530d9eb5a4c2fafa51943cff2a94e6385",
  "target": "us",
  "cpu": 4,
  "memoryGiB": 8,
  "diskGiB": 10,
  "gpu": 1,
  "gpuTypes": ["RTX-PRO-6000", "H100"],
  "spot": false,
  "public": false,
  "ephemeral": true,
  "networkBlockAll": true,
  "ttlMinutes": 45,
  "createTimeoutSeconds": 600,
  "executionTimeoutSeconds": 1800,
  "transferTimeoutSeconds": 1800,
  "deleteTimeoutSeconds": 120,
  "cleanupAttempts": 3
}
```

`ProcessingSettings` accepts only `Literal["local", "daytona"]`; `from_env()` raises on invalid selected Daytona configuration instead of returning a disabled remote flag.

- [ ] **Step 4: Verify clean SDK import and tests**

```bash
python3 -m pip install --dry-run -e . -r backend/requirements-dev.txt
python3 -m pytest -q backend/tests/test_settings.py backend/tests/test_daytona_release_policy.py
python3 -c 'from daytona import Daytona, CreateSandboxFromImageParams, Resources, GpuType'
python3 -m pip check
```

Expected: imports and tests pass; no sandbox is created.

- [ ] **Step 5: Commit**

```bash
git add backend/release/daytona_policy.py backend/release/daytona-v7.3.json \
  backend/release/daytona_execution_schema.json backend/tests/test_daytona_release_policy.py \
  backend/app/settings.py backend/requirements-runtime.txt backend/tests/test_settings.py
git commit -m "feat: define Daytona GPU execution policy"
```

## Task 6: Implement the Daytona adapter with a fake-client seam

**Files:**

- Create: `backend/app/daytona.py`
- Create: `backend/tests/test_daytona.py`

- [ ] **Step 1: Write failing lifecycle and zero-mutation tests**

Cover exact create parameters, zero client construction on invalid preflight, streaming upload order, constant command/cwd, empty sandbox environment, sandbox ID capture, nonzero exit, timeout, bounded/redacted logs, corrupt downloads, cleanup on every failure stage, cleanup retries, and cleanup failure overriding otherwise valid results.

```python
def test_invalid_release_causes_zero_daytona_mutation(fake_factory: FakeFactory) -> None:
    with pytest.raises(DaytonaExecutionError, match="release_unverified"):
        execute_daytona_job(invalid_execution_request(), client_factory=fake_factory)
    assert fake_factory.construct_calls == 0
    assert fake_factory.create_calls == 0
```

- [ ] **Step 2: Run tests and capture RED**

Run: `python3 -m pytest -q backend/tests/test_daytona.py`

- [ ] **Step 3: Implement protocols and lifecycle**

Define narrow protocols and inject the production factory. Construct exactly:

```python
CreateSandboxFromImageParams(
    image=policy.image,
    public=False,
    ephemeral=True,
    spot=False,
    ttl_minutes=45,
    network_block_all=True,
    env_vars={},
    resources=Resources(
        cpu=4,
        memory=8,
        disk=10,
        gpu=1,
        gpu_type=[GpuType.RTX_PRO_6000, GpuType.H100],
    ),
)
```

Upload with `sandbox.fs.upload_file_stream(local_path, remote_path, timeout=1800)`. Execute the constant command:

```text
python -m backend.app.gpu_worker --request /home/daytona/job/input/job-request.json --result /home/daytona/job/output/result-bundle.json --completion-receipt /home/daytona/job/output/completion-receipt.json
```

Download via streaming, validate before return, then call delete with bounded retries in `finally`. Treat confirmed absence as cleanup success. Do not return a result until cleanup is confirmed.

- [ ] **Step 4: Run tests and commit**

```bash
python3 -m pytest -q backend/tests/test_daytona.py
git add backend/app/daytona.py backend/tests/test_daytona.py
git commit -m "feat: add fail-closed Daytona GPU adapter"
```

## Task 7: Integrate Daytona with application jobs and preserve old data

**Files:**

- Create: `backend/app/remote_worker.py`
- Create: `backend/tests/test_remote_worker.py`
- Modify: `backend/app/jobs.py`
- Modify: `backend/app/storage.py`
- Modify: `backend/app/run_benchmarks.py`
- Modify: `backend/tests/test_jobs.py`
- Modify: `backend/tests/test_job_metadata.py`
- Modify: `backend/tests/test_run_benchmarks.py`

- [ ] **Step 1: Write failing orchestration and compatibility tests**

Prove sandbox ID is persisted as `remoteRunId`; neutral progress/debug artifacts are written; output is imported only after validated result and cleanup; failure never persists rows; missing credentials fail the selected job without local execution; legacy DB rows in `runpod_run_id` remain readable/writable; benchmark readers prefer neutral files and fall back to historical RunPod files.

- [ ] **Step 2: Run tests and capture RED**

Run:

```bash
python3 -m pytest -q backend/tests/test_remote_worker.py backend/tests/test_jobs.py \
  backend/tests/test_job_metadata.py backend/tests/test_run_benchmarks.py
```

- [ ] **Step 3: Add the provider-neutral orchestration**

Expose:

```python
def run_remote_job(
    storage_root: Path,
    job_id: str,
    settings: ProcessingSettings | None = None,
    *,
    client_factory: DaytonaClientFactory | None = None,
) -> None:
    settings = settings or ProcessingSettings.from_env()
    storage = Storage(storage_root)
    request = build_execution_request(storage, job_id, settings)
    result = execute_daytona_job(request, client_factory=client_factory)
    persist_remote_video_result(storage, request.match_id, result.output)
```

`JobRunner` explicitly branches `local` or `daytona` and spawns `backend.app.remote_worker`. Project only validated `DAYTONA_*` host settings into the child. New artifacts are `remote_transport_debug.json` and `remote_worker_progress.json`; old names are read-only fallbacks.

- [ ] **Step 4: Run focused/API tests and commit**

```bash
python3 -m pytest -q backend/tests/test_remote_worker.py backend/tests/test_jobs.py \
  backend/tests/test_job_metadata.py backend/tests/test_processor.py \
  backend/tests/test_run_benchmarks.py backend/tests/test_api.py
git add backend/app/remote_worker.py backend/app/jobs.py backend/app/storage.py \
  backend/app/run_benchmarks.py backend/tests/test_remote_worker.py \
  backend/tests/test_jobs.py backend/tests/test_job_metadata.py \
  backend/tests/test_run_benchmarks.py
git commit -m "feat: route remote analysis through Daytona"
```

## Task 8: Replace release evidence and canonical gate 13

**Files:**

- Modify: `backend/release/evidence.py`
- Modify: `backend/release/verification_schema.json`
- Create: `backend/scripts/write_verification_evidence.py`
- Create: `backend/tests/test_release_evidence.py`
- Modify: `scripts/verify.sh`
- Modify: `backend/tests/test_verify_script.py`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Write failing schema/gate/mutation tests**

Require exactly thirteen ordered gates. Gate 11 becomes provider-neutral preflight negatives. Gate 13 is:

```text
python3 -m backend.scripts.run_daytona_gpu_smoke --real-smoke
```

Phases are `pre_cloud` (gates 1–12 passed, gate 13 pending, overall false, `remoteExecution=null`) and `final` (all passed, overall true, exact `remoteExecution`). Test all flag combinations and invalid values prove zero client construction.

- [ ] **Step 2: Run tests and capture RED**

Run: `python3 -m pytest -q backend/tests/test_release_evidence.py backend/tests/test_verify_script.py`

- [ ] **Step 3: Implement schema v2 and verifier behavior**

`remoteExecution` final object must include SDK version, image digest, requested target/GPU order, observed GPU, sandbox ID, create/start/complete/delete timestamps, bounded command results, upload/download identities, cleanup attempts, `deletionConfirmed=true`, `runpodMutationOccurred=false`, and `registryMutationOccurred=false`.

Before the source freeze, narrow `METADATA_ALLOWLIST` to exactly:

```text
backend/release/v7.3.json
backend/release/verification/v7.3-pre-cloud.json
backend/release/verification/v7.3.json
docs/recovery/2026-08-19/current-tree-inventory.json
docs/recovery/2026-08-24/daytona-gpu-smoke.md
docs/recovery/2026-08-24/final-verification-report.md
docs/status/current.md
```

Add adversarial tests proving every other path, including README, CI, source, dependencies, and runbooks, invalidates the frozen-source protocol.

Default `scripts/verify.sh` runs all non-cloud gates and prints the Daytona skip. Only both exact environment flags run gate 13; either flag alone or any non-`0|1` value fails before Python client construction. CI sets both to `0`, invokes only the verifier, and never receives `DAYTONA_API_KEY`.

- [ ] **Step 4: Run tests and commit**

```bash
python3 -m pytest -q backend/tests/test_release_evidence.py backend/tests/test_verify_script.py
bash -n scripts/verify.sh
git add backend/release/evidence.py backend/release/verification_schema.json \
  backend/scripts/write_verification_evidence.py backend/tests/test_release_evidence.py \
  scripts/verify.sh backend/tests/test_verify_script.py .github/workflows/ci.yml
git commit -m "ci: replace RunPod gate with Daytona verification"
```

## Task 9: Add credential-free and real Daytona smoke runner

**Files:**

- Create: `backend/scripts/run_daytona_gpu_smoke.py`
- Create: `backend/tests/test_run_daytona_gpu_smoke.py`
- Create: `backend/tests/fixtures/daytona/job-request.json`
- Create: `backend/daytona_worker/Dockerfile`
- Create: `backend/daytona_worker/requirements.txt`
- Create: `backend/daytona_worker/requirements.lock`

- [ ] **Step 1: Write failing dry-run and fake-real-smoke tests**

Test dry run validates everything without importing/constructing Daytona; exactly one fake create call; ordered GPU list; `nvidia-smi`; worker import; bounded fixture; streamed inputs/output; completion validation; deletion in every path; absence after deletion; no create retry; and no final evidence when deletion is unconfirmed.

- [ ] **Step 2: Run tests and capture RED**

Run: `python3 -m pytest -q backend/tests/test_run_daytona_gpu_smoke.py`

- [ ] **Step 3: Implement the CLI and immutable worker environment**

CLI modes are mutually exclusive: default `--dry-run`, explicit `--real-smoke`. Call `validate_mutation_authorization` before client construction. The worker Dockerfile starts from:

```dockerfile
FROM docker.io/pytorch/pytorch@sha256:417bd75df6365104c283ea4c1651fb3530d9eb5a4c2fafa51943cff2a94e6385
WORKDIR /workspace
COPY backend/daytona_worker/requirements.lock /tmp/requirements.lock
RUN python -m pip install --require-hashes --no-deps -r /tmp/requirements.lock \
 && python -m pip check
```

Generate the lock from exact direct requirements and preserve all hashes. The dry run rejects an empty hash, unpinned line, duplicate OpenCV provider, changed base digest, or SDK mismatch.

- [ ] **Step 4: Run fake smoke tests and commit**

```bash
python3 -m pytest -q backend/tests/test_run_daytona_gpu_smoke.py
VERIFY_DAYTONA=0 ALLOW_DAYTONA_MUTATION=0 \
  python3 -m backend.scripts.run_daytona_gpu_smoke --dry-run
git add backend/scripts/run_daytona_gpu_smoke.py backend/tests/test_run_daytona_gpu_smoke.py \
  backend/tests/fixtures/daytona backend/daytona_worker
git commit -m "feat: add gated Daytona GPU smoke"
```

## Task 10: Retire the active RunPod surface and publish active Daytona docs

**Files:**

- Delete: `backend/app/runpod.py`, `backend/app/runpod_worker.py`, `backend/runpod_handler/`
- Delete after migrated parity: direct RunPod application/handler/deployment tests
- Move: `SESSION-HANDOFF.md` to `docs/archive/2026-08-19/SESSION-HANDOFF.md`
- Move: `memorybank/activeContext.md` to `docs/archive/2026-08-19/activeContext.md`
- Move: `memorybank/currentRoadmap.md` to `docs/archive/2026-08-19/currentRoadmap.md`
- Create concise compatibility pointers at the three original paths
- Create: `docs/archive/2026-08-19/checksums.json`
- Modify: `README.md`, `docs/status/current.md`
- Create: `docs/runbooks/artifact-restore.md`
- Replace active deployment runbook with: `docs/runbooks/daytona-gpu-execution.md`
- Create: `docs/archive/2026-08-24/rejected-runpod-release.md`
- Create/modify: operational documentation tests

- [ ] **Step 1: Write failing active-surface and documentation tests**

Before moving the three chronology files, record byte sizes and SHA-256 values. Require exact digest equality after the move and record those identities in `docs/archive/2026-08-19/checksums.json`. Require concise original-path pointers, one authoritative current status, Daytona-only current startup/configuration, explicit RunPod retirement chronology, executable verification/dry-run/real-smoke/artifact-restore commands, no workstation absolute paths, no public endpoint, credential redaction, and statements that no RunPod push/deployment, history rewrite, or model/data deletion occurred.

- [ ] **Step 2: Migrate remaining active imports before deletion**

Run:

```bash
rg -n "backend\.app\.runpod|runpod_worker|PROCESSING_BACKEND.?runpod|RUNPOD_API_KEY|deploy_to_runpod" \
  backend scripts .github README.md docs/status docs/runbooks
```

Change application/release/CI/current-doc hits to Daytona/provider-neutral names. Historical archive hits remain unchanged and truthful. Legacy research scripts must be disconnected from active dispatch and labeled historical/fail-closed.

- [ ] **Step 3: Delete obsolete active code only after parity tests pass**

Delete exact RunPod adapter, handler, deployment scripts, requirements, and direct provider-only tests. Preserve Git history and the recovery branch. Keep historical diagnostic readers and the SQLite column.

- [ ] **Step 4: Run docs/import/audit tests and commit**

```bash
python3 -m pytest -q backend/tests/test_operational_docs.py backend/tests/test_jobs.py \
  backend/tests/test_remote_worker.py backend/tests/test_release_preflight.py
git diff --check
git add -A -- backend/app backend/runpod_handler backend/tests README.md SESSION-HANDOFF.md \
  memorybank/activeContext.md memorybank/currentRoadmap.md docs/archive/2026-08-19 \
  docs/archive/2026-08-24 docs/runbooks docs/status/current.md
git commit -m "chore: retire active RunPod execution"
```

## Task 11: Run non-cloud acceptance and freeze Daytona source

**Files:**

- Modify before freeze only if verification exposes a defect: product/runtime/tests/dependencies/verifier/CI/current docs
- Delete before freeze: obsolete `backend/release/v7.3.json` and rejected active evidence tied to earlier source commits

- [ ] **Step 1: Run focused Daytona/release tests**

```bash
python3 -m pytest -q \
  backend/tests/test_remote_contracts.py \
  backend/tests/test_gpu_worker.py \
  backend/tests/test_daytona.py \
  backend/tests/test_remote_worker.py \
  backend/tests/test_release_preflight.py \
  backend/tests/test_release_evidence.py \
  backend/tests/test_daytona_release_policy.py \
  backend/tests/test_run_daytona_gpu_smoke.py \
  backend/tests/test_verify_script.py \
  backend/tests/test_release_manifest.py \
  backend/tests/test_write_release_manifest.py \
  backend/tests/test_runtime_options.py
```

Expected: all pass; zero Daytona creation calls.

- [ ] **Step 2: Run the canonical non-cloud verifier**

Run: `VERIFY_DAYTONA=0 ALLOW_DAYTONA_MUTATION=0 scripts/verify.sh`

Expected: backend, sidecar, frontend, lint, both typechecks, build, startup, manifest, runtime, provider-neutral preflight negatives, and production audit pass; Daytona sandbox gate is skipped explicitly.

- [ ] **Step 3: Perform freeze audit**

```bash
git status --short
git diff --check
rg -n "RUNPOD_API_KEY|PROCESSING_BACKEND.?runpod|deploy_to_runpod" backend scripts .github README.md docs/status docs/runbooks
git fsck --no-reflogs --full
```

Expected: clean tree, no active RunPod entry point, recovery branch reachable, no grafts/replacement refs.

- [ ] **Step 4: Freeze source**

Commit any final pre-freeze changes as:

```bash
git commit -m "feat: freeze Daytona GPU execution source"
git rev-parse HEAD
```

Record the exact 40-character result as `S_DAYTONA`. After this command, no product/runtime/dependency/verifier/CI/current-document file may change.

## Task 12: Bind metadata and pre-cloud evidence

**Files:**

- Create: `backend/release/v7.3.json`
- Modify: `docs/recovery/2026-08-19/current-tree-inventory.json` only for truthful replacement evidence
- Create: `backend/release/verification/v7.3-pre-cloud.json`

- [ ] **Step 1: Generate and validate metadata against `S_DAYTONA`**

Keep the five accepted artifact identities and eight runtime options. Set `sourceCommit` to `S_DAYTONA`, use a fresh UTC timestamp, validate all local sizes/SHA-256 values, both required contracts, and tracked historical registry blob/hash.

- [ ] **Step 2: Commit only metadata**

```bash
git add backend/release/v7.3.json docs/recovery/2026-08-19/current-tree-inventory.json
git commit -m "feat: bind Daytona v7.3 release metadata"
```

Record HEAD as `M_DAYTONA`; verify `M_DAYTONA^ == S_DAYTONA` and the diff has exactly the two files.

- [ ] **Step 3: Run non-cloud gates from clean metadata and write pre-cloud evidence**

```bash
VERIFY_DAYTONA=0 ALLOW_DAYTONA_MUTATION=0 scripts/verify.sh
python3 -m backend.scripts.write_verification_evidence \
  --phase pre_cloud \
  --output backend/release/verification/v7.3-pre-cloud.json
```

Expected: gates 1–12 passed, Daytona gate pending, `overallPassed=false`, `remoteExecution=null`.

- [ ] **Step 4: Commit only pre-cloud evidence**

```bash
git add backend/release/verification/v7.3-pre-cloud.json
git commit -m "docs: record Daytona pre-cloud verification"
```

Record HEAD as `E0_DAYTONA`; verify the worktree is clean and `S_DAYTONA..E0_DAYTONA` contains only the exact metadata/evidence allowlist.

## Task 13: Run one real Daytona GPU smoke and publish final evidence

**Files:**

- Create: `backend/release/verification/v7.3.json`
- Create: `docs/recovery/2026-08-24/daytona-gpu-smoke.md`

- [ ] **Step 1: Verify credentials without exposing them**

```bash
test -n "${DAYTONA_API_KEY:-}"
daytona list
git status --short
```

Expected: API key present for the Python SDK, authenticated read succeeds, clean worktree. If the key is absent, stop before mutation and ask the user to export it from the Daytona dashboard; never read or copy CLI credential storage.

- [ ] **Step 2: Run exactly one authorized real smoke**

```bash
VERIFY_DAYTONA=1 \
ALLOW_DAYTONA_MUTATION=1 \
python3 -m backend.scripts.run_daytona_gpu_smoke --real-smoke
```

Expected: exactly one private on-demand sandbox; observed GPU recorded; `nvidia-smi`, imports, artifact verification, bounded fixture processing, result/completion download, and deletion confirmation pass. No preview, snapshot, volume, registry push, RunPod call, or create retry occurs.

- [ ] **Step 3: Independently verify cleanup**

```bash
daytona list
```

Expected: the recorded sandbox ID is absent. If it remains, resolve only the evidence-bound ID and run one exact cleanup action:

```bash
daytona_sandbox_id="$(jq -r '.remoteExecution.sandboxId' backend/release/verification/v7.3.json)"
test -n "$daytona_sandbox_id" && test "$daytona_sandbox_id" != "null"
daytona delete "$daytona_sandbox_id"
```

Record that recovery action and keep the smoke failed until absence is confirmed.

- [ ] **Step 4: Generate and validate final evidence/report**

Write schema-v2 final evidence with all thirteen gates passed, `overallPassed=true`, exact remote execution identities/timestamps, cleanup attempts, and deletion confirmation. Write a redacted report with commands, durations, SDK/image/source/manifest/evidence hashes, requested/observed GPU, transfer identities, result identity, cleanup proof, and explicit zero RunPod/registry mutation.

- [ ] **Step 5: Commit only final evidence and report**

```bash
git add backend/release/verification/v7.3.json docs/recovery/2026-08-24/daytona-gpu-smoke.md
git commit -m "docs: record Daytona GPU release verification"
```

Run final provider-neutral preflight against the clean commit and require acceptance of only enumerated post-freeze paths.

## Task 14: Complete stabilization documentation and bounded cleanup

**Files:**

- Create/modify: `docs/recovery/2026-08-24/final-verification-report.md`
- Modify: `docs/status/current.md`

- [ ] **Step 1: Reconcile the original stabilization plan against current evidence**

Audit every item in the preservation, release/runtime, operability, and Daytona plans. Record exact commits, test counts, durations, dependency findings, Daytona identities, skipped gates, archive checksum verification, compatibility-pointer verification, and retained worktrees/branches.

- [ ] **Step 2: Verify the recovery/salvage inventory and bounded worktree decision**

Recheck the exact salvage metadata and `unique_unresolved` count for `.worktrees/recovery-history-batch`. Remove that one worktree without `--force` only if the existing approved cleanup condition is proven; retain its branch and all other named worktrees/branches.

- [ ] **Step 3: Run final clean-checkout acceptance**

Create disposable Python/Node environments from committed manifests, restore artifacts only through recorded identifiers, run the canonical verifier plus the already-recorded Daytona smoke evidence validation, and capture exact results. Do not create a second Daytona sandbox.

- [ ] **Step 4: Commit the final report/status**

```bash
git add docs/recovery/2026-08-24/final-verification-report.md docs/status/current.md
git commit -m "docs: complete Daytona stabilization verification"
```

- [ ] **Step 5: Independent completion review**

Dispatch a fresh specification reviewer and a fresh adversarial quality reviewer. Require both to approve the exact final commit, clean worktree, original recovery accounting, Daytona-only active path, final evidence, and zero unapproved external mutation before marking the active goal complete.

## Plan self-review result

- Every approved design requirement maps to Tasks 1–14.
- The migration remains one dependent subsystem: contracts → worker → policy → adapter → application → evidence/CI → retirement → freeze → real smoke.
- Types and names are consistent: `JobReceipt`, `CompletionReceipt`, `remoteRunId`, `remote_transport_debug`, `remote_worker_progress`, `S_DAYTONA`, `M_DAYTONA`, and `E0_DAYTONA` retain the same meaning throughout.
- No product changes are scheduled after `S_DAYTONA`.
- The only billable mutation is the single triply gated smoke in Task 13, followed by independently verified deletion.
- The plan preserves aborted RunPod chronology and the interrupted lock experiment without carrying them into the active Daytona tree.
