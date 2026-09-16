# Daytona Worker Runtime Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the Daytona worker's OpenCV runtime, retain bounded and redacted failed-command evidence after confirmed cleanup, rebuild the verifier-bound release chain, and finish gate 13 only after separate authorization for one third sandbox.

**Architecture:** Keep the existing `opencv-python` and worker lock, adding only the Ubuntu shared libraries and offscreen Qt setting needed by the actual worker imports. Extend the existing smoke runner with one private command-error type whose sanitized payload is emitted only after the existing cleanup path confirms absence; keep release evidence success-only. Reuse the current manifest, verifier, evidence writer, and preflight flows to create a fresh `S4 -> M4 -> E04` chain.

**Tech Stack:** Python 3.12, pytest, Docker Buildx, Ubuntu 22.04 packages, OpenCV, PyTorch, Daytona SDK/CLI 0.207.0, Git, jq, Bash.

---

## File map and boundaries

- `backend/daytona_worker/Dockerfile` — install the three missing system libraries and set Qt to offscreen mode; leave the immutable base and Python lock sequence intact.
- `backend/scripts/run_daytona_gpu_smoke.py` — mirror the exact Dockerfile, capture only bounded/redacted nonzero command results, and emit failure JSON after cleanup.
- `backend/tests/test_run_daytona_gpu_smoke.py` — prove exact image policy, diagnostic safety, cleanup precedence, and CLI output.
- `backend/tests/test_release_evidence.py` — characterize rejection of failed-smoke JSON by final evidence publication.
- `backend/release/v7.3.json` — regenerate from the final corrected source commit.
- `docs/recovery/2026-08-19/current-tree-inventory.json` — update only the replacement manifest's source identity and timestamp.
- `backend/release/verification/v7.3-pre-cloud.json` — regenerate from a fresh canonical verifier receipt with gate 13 pending.
- `backend/release/verification/v7.3.json` — create only after a separately authorized successful third smoke.
- `docs/recovery/2026-08-24/daytona-gpu-smoke.md` — preserve attempts 1 and 2 byte-for-byte and append attempt 3 truthfully.
- `docs/recovery/2026-08-24/final-verification-report.md` and `docs/status/current.md` — create/update only after final evidence and deploy preflight pass.

Do not modify `backend/app/daytona.py`, `backend/app/remote_contracts.py`, either worker requirements file, `backend/release/evidence.py`, either JSON schema, or the Daytona SDK pin. Do not push an image or use RunPod.

### Task 1: Close the worker's OpenCV runtime dependencies

**Files:**

- Modify: `backend/tests/test_run_daytona_gpu_smoke.py:154`
- Modify: `backend/daytona_worker/Dockerfile:1`
- Modify: `backend/scripts/run_daytona_gpu_smoke.py:62`

- [ ] **Step 1: Add the failing exact-image test**

Add immediately after `test_worker_image_removes_incompatible_base_audio_before_locked_install`:

```python
def test_worker_image_closes_opencv_headless_runtime():
    dockerfile = (ROOT / "backend/daytona_worker/Dockerfile").read_text()
    expected = (
        "RUN apt-get update \\\n"
        " && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \\\n"
        "      libgl1 libglib2.0-0 libxcb1 \\\n"
        " && rm -rf /var/lib/apt/lists/*\n"
        "ENV QT_QPA_PLATFORM=offscreen\n"
    )
    assert expected in dockerfile
    assert smoke.expected_dockerfile() == dockerfile
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```bash
python3 -m pytest -q \
  backend/tests/test_run_daytona_gpu_smoke.py::test_worker_image_closes_opencv_headless_runtime
```

Expected: one failure because the current Dockerfile has neither the apt block nor `QT_QPA_PLATFORM`.

- [ ] **Step 3: Apply the minimal Dockerfile correction**

Make `backend/daytona_worker/Dockerfile` exactly:

```dockerfile
FROM docker.io/pytorch/pytorch@sha256:417bd75df6365104c283ea4c1651fb3530d9eb5a4c2fafa51943cff2a94e6385
WORKDIR /workspace
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      libgl1 libglib2.0-0 libxcb1 \
 && rm -rf /var/lib/apt/lists/*
ENV QT_QPA_PLATFORM=offscreen
COPY backend/daytona_worker/requirements.lock /tmp/requirements.lock
RUN python -m pip uninstall --yes torchaudio \
 && python -m pip install --require-hashes --no-deps -r /tmp/requirements.lock \
 && python -m pip check
COPY backend /workspace/backend
```

Make `expected_dockerfile()` return the same bytes:

```python
def expected_dockerfile() -> str:
    return (
        f"FROM {IMAGE}\n"
        "WORKDIR /workspace\n"
        "RUN apt-get update \\\n"
        " && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \\\n"
        "      libgl1 libglib2.0-0 libxcb1 \\\n"
        " && rm -rf /var/lib/apt/lists/*\n"
        "ENV QT_QPA_PLATFORM=offscreen\n"
        "COPY backend/daytona_worker/requirements.lock /tmp/requirements.lock\n"
        "RUN python -m pip uninstall --yes torchaudio \\\n"
        " && python -m pip install --require-hashes --no-deps -r /tmp/requirements.lock \\\n"
        " && python -m pip check\n"
        "COPY backend /workspace/backend\n"
    )
```

Do not change the base digest, requirements, lock hashes, or torchaudio removal.

- [ ] **Step 4: Run the image-policy tests to verify GREEN**

Run:

```bash
python3 -m pytest -q backend/tests/test_run_daytona_gpu_smoke.py
VERIFY_DAYTONA=0 ALLOW_DAYTONA_MUTATION=0 \
  python3 -m backend.scripts.run_daytona_gpu_smoke --dry-run
```

Expected: the smoke test file passes, and dry-run emits the immutable image, SDK `0.207.0`, target `us`, and GPU order `RTX-PRO-6000,H100` without loading the SDK or creating a sandbox.

- [ ] **Step 5: Commit only the image correction**

Run:

```bash
git add \
  backend/daytona_worker/Dockerfile \
  backend/scripts/run_daytona_gpu_smoke.py \
  backend/tests/test_run_daytona_gpu_smoke.py
git diff --cached --check
git commit -m "fix: close Daytona worker OpenCV runtime"
git diff-tree --no-commit-id --name-only -r HEAD
```

Expected: exactly the three listed files are committed.

### Task 2: Preserve safe failed-command diagnostics after cleanup

**Files:**

- Modify: `backend/tests/test_run_daytona_gpu_smoke.py:165-325`
- Modify: `backend/scripts/run_daytona_gpu_smoke.py:27-190,219-339`

- [ ] **Step 1: Extend the fake response and add diagnostic tests**

Change `_Response` to:

```python
class _Response:
    def __init__(self, result="", exit_code=0, stderr=""):
        self.result, self.exit_code, self.stderr = result, exit_code, stderr
```

Replace `test_fake_real_smoke_deletes_on_failure_and_emits_no_report` with these tests:

```python
def test_nonzero_remote_command_preserves_bounded_sanitized_diagnostics_after_confirmed_cleanup():
    api_key = "opaque-host-key-sentinel"
    client = _Client()
    original = client.sandbox.process.exec

    def fail_import(command, **kwargs):
        if command == smoke.WORKER_IMPORT_COMMAND:
            return _Response(api_key + "x" * 10_000, 9, "Bearer provider-secret")
        return original(command, **kwargs)

    client.sandbox.process.exec = fail_import
    with pytest.raises(smoke.SmokeCommandError) as raised:
        smoke.run_real_smoke(
            ROOT,
            env={"VERIFY_DAYTONA": "1", "ALLOW_DAYTONA_MUTATION": "1",
                 "DAYTONA_API_KEY": api_key},
            client_factory=lambda *_: client,
        )

    result = raised.value.command_result
    rendered = json.dumps(result, sort_keys=True, separators=(",", ":"))
    assert result["stage"] == "worker-import"
    assert result["exitCode"] == 9
    assert len(rendered) <= smoke.MAX_FAILURE_DIAGNOSTIC_CHARS
    assert "[REDACTED]" in rendered and "[TRUNCATED]" in rendered
    assert api_key not in rendered and "provider-secret" not in rendered
    assert api_key not in repr(raised.value) and "provider-secret" not in repr(raised.value)
    assert client.deleted


def test_unconfirmed_deletion_suppresses_remote_command_diagnostics():
    client = _Client(absent=False)
    client.sandbox.process.exec = lambda *args, **kwargs: _Response(
        "opaque-host-key-sentinel", 9, "Bearer provider-secret"
    )

    with pytest.raises(smoke.SmokeError) as raised:
        smoke.run_real_smoke(
            ROOT,
            env={"VERIFY_DAYTONA": "1", "ALLOW_DAYTONA_MUTATION": "1",
                 "DAYTONA_API_KEY": "opaque-host-key-sentinel"},
            client_factory=lambda *_: client,
        )

    assert type(raised.value) is smoke.SmokeError
    assert str(raised.value) == "Daytona sandbox deletion was not confirmed"
    assert "sentinel" not in repr(raised.value) and "provider-secret" not in repr(raised.value)


def test_cli_command_failure_emits_one_canonical_json_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    command_result = {
        "stage": "worker-import", "exitCode": 9,
        "stdout": "[REDACTED]", "stderr": "ImportError: missing library",
    }
    monkeypatch.setattr(
        smoke, "run_real_smoke",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            smoke.SmokeCommandError(command_result)
        ),
    )

    assert smoke.main(["--real-smoke"]) == 2
    captured = capsys.readouterr()
    expected = {
        "mode": "real-smoke", "status": "failed",
        "error": "Daytona smoke command failed", "commandResult": command_result,
    }
    assert captured.out == json.dumps(expected, sort_keys=True, separators=(",", ":")) + "\n"
    assert captured.err == "Daytona smoke command failed\n"
    assert "Traceback" not in captured.err
```

- [ ] **Step 2: Run the diagnostic tests to verify RED and the cleanup guard**

Run:

```bash
python3 -m pytest -q \
  backend/tests/test_run_daytona_gpu_smoke.py::test_nonzero_remote_command_preserves_bounded_sanitized_diagnostics_after_confirmed_cleanup \
  backend/tests/test_run_daytona_gpu_smoke.py::test_failed_command_rejects_hostile_string_subclass_without_invoking_it_after_cleanup \
  backend/tests/test_run_daytona_gpu_smoke.py::test_oversized_exit_code_is_generic_after_cleanup_and_emits_no_failure_json \
  backend/tests/test_run_daytona_gpu_smoke.py::test_unconfirmed_deletion_suppresses_remote_command_diagnostics \
  backend/tests/test_run_daytona_gpu_smoke.py::test_cli_command_failure_emits_one_canonical_json_line
```

Expected before implementation: the new command-error and CLI tests fail because `SmokeCommandError` does not exist and nonzero output is discarded. The deletion-precedence assertion remains the required safety guard.

- [ ] **Step 3: Add the minimal private diagnostic helpers**

Extend the existing remote-contract import:

```python
from backend.app.remote_contracts import (
    JobRequest, canonical_json_bytes, redact_remote_diagnostics,
)
```

Add immediately after `SmokeError`:

```python
MAX_FAILURE_DIAGNOSTIC_CHARS = 2048


class SmokeCommandError(SmokeError):
    def __init__(self, command_result: dict[str, object]):
        super().__init__("Daytona smoke command failed")
        self.command_result = command_result


def _without_api_key(value: object, api_key: str) -> object:
    if type(value) is not str:
        return "[UNAVAILABLE]"
    return str.replace(value, api_key, "[REDACTED]")


def _failed_command_result(
    response: object, label: str, exit_code: int, api_key: str
) -> dict[str, object]:
    clean = redact_remote_diagnostics(
        {
            "stdout": _without_api_key(getattr(response, "result", ""), api_key),
            "stderr": _without_api_key(getattr(response, "stderr", ""), api_key),
        },
        max_output_chars=MAX_FAILURE_DIAGNOSTIC_CHARS,
        max_depth=1,
        max_items=2,
    )
    if type(clean) is not dict:
        clean = {"stdout": "[REDACTED]", "stderr": "[REDACTED]"}
    stdout = clean.get("stdout", "[REDACTED]")
    stderr = clean.get("stderr", "[REDACTED]")
    if type(stdout) is not str or type(stderr) is not str:
        stdout = stderr = "[REDACTED]"
    return {
        "stage": label, "exitCode": exit_code,
        "stdout": stdout, "stderr": stderr,
    }
```

This reuses the existing hostile-object-safe redactor. The exact host key is removed before truncation so an unlabeled opaque credential cannot survive.

- [ ] **Step 4: Capture nonzero results without changing success evidence**

Replace `_exec` with:

```python
def _exec(
    sandbox, command: str, label: str, timeout: int, *, api_key: str
) -> tuple[str, dict[str, object]]:
    response = sandbox.process.exec(command, cwd="/workspace", env={}, timeout=timeout)
    exit_code = getattr(response, "exit_code", None)
    if type(exit_code) is not int or not 0 <= exit_code <= 255:
        raise SmokeError("Daytona smoke command response is invalid")
    if exit_code != 0:
        raise SmokeCommandError(
            _failed_command_result(response, label, exit_code, api_key)
        )
    stdout = getattr(response, "result", "")
    stderr = getattr(response, "stderr", "")
    if (
        type(stdout) is not str
        or type(stderr) is not str
        or len(stdout) > 4096
        or len(stderr) > 4096
        or "\0" in stdout
        or "\0" in stderr
    ):
        raise SmokeError("Daytona smoke command output is not bounded")
    return stdout, {
        "command": label, "exitCode": 0, "stdout": stdout, "stderr": stderr,
    }
```

Pass `api_key=key` to each of the four existing `_exec` calls in `run_real_smoke`. Keep the remote `env={}` and fixed commands unchanged.

The regression set must also prove that a hostile `str` subclass is never invoked and is rendered as `[UNAVAILABLE]`, and that an enormous integer exit code is rejected generically after cleanup without emitting failure JSON.

- [ ] **Step 5: Emit failure JSON only after cleanup has completed**

Catch the subtype before the existing `SmokeError` branch in `main()`:

```python
    except SmokeCommandError as exc:
        failure = {
            "mode": "real-smoke",
            "status": "failed",
            "error": str(exc),
            "commandResult": exc.command_result,
        }
        print(json.dumps(failure, sort_keys=True, separators=(",", ":")))
        print(str(exc), file=os.sys.stderr)
        return 2
    except SmokeError as exc:
        print(str(exc), file=os.sys.stderr)
        return 2
```

Do not alter `run_real_smoke`'s `pending`/`finally` structure. It re-raises the command error only after confirmed absence; an unconfirmed deletion raises the generic cleanup error from `finally` and suppresses failure JSON.

- [ ] **Step 6: Verify GREEN and commit the runner change**

Run:

```bash
python3 -m pytest -q backend/tests/test_run_daytona_gpu_smoke.py
git add backend/scripts/run_daytona_gpu_smoke.py backend/tests/test_run_daytona_gpu_smoke.py
git diff --cached --check
git commit -m "fix: retain safe Daytona command failures"
git diff-tree --no-commit-id --name-only -r HEAD
```

Expected: the complete smoke-runner suite passes and exactly the two listed files are committed.

### Task 3: Prove failure JSON cannot become release evidence

**Files:**

- Modify: `backend/tests/test_release_evidence.py:631`

- [ ] **Step 1: Add the success-contract characterization test**

Add before the existing final-writer tests:

```python
def test_final_writer_rejects_failed_smoke_report(
    receipt_repo: Path, tmp_path: Path
) -> None:
    from backend.app.remote_contracts import canonical_json_bytes
    from backend.scripts.write_verification_evidence import write_verification_evidence

    _record_receipt(receipt_repo)
    failure = {
        "mode": "real-smoke",
        "status": "failed",
        "error": "Daytona smoke command failed",
        "commandResult": {
            "stage": "worker-import", "exitCode": 9,
            "stdout": "", "stderr": "ImportError: missing library",
        },
    }
    remote = tmp_path / "failed-smoke.json"
    remote.write_bytes(canonical_json_bytes(failure))
    output = tmp_path / "final-evidence.json"

    with pytest.raises(PreflightError):
        write_verification_evidence(
            output,
            phase="final",
            repo_root=receipt_repo,
            remote_execution_path=remote,
            now=datetime(2026, 8, 22, 12, 31, tzinfo=timezone.utc),
        )

    assert not output.exists()
```

- [ ] **Step 2: Run the characterization test**

Run:

```bash
python3 -m pytest -q \
  backend/tests/test_release_evidence.py::test_final_writer_rejects_failed_smoke_report
```

Expected: pass immediately because the existing strict `RemoteExecution` parser rejects the failure shape before publication. If it fails, repair the test assumption rather than weakening the success schema.

- [ ] **Step 3: Run focused evidence regressions and commit only the test**

Run:

```bash
python3 -m pytest -q \
  backend/tests/test_remote_contracts.py \
  backend/tests/test_release_evidence.py
git add backend/tests/test_release_evidence.py
git diff --cached --check
git commit -m "test: reject failed Daytona smoke as release evidence"
git diff-tree --no-commit-id --name-only -r HEAD
```

Expected: both suites pass and the commit contains only the characterization test. No evidence implementation or schema changes are needed.

### Task 4: Prove the complete corrected image and local release behavior

**Files:**

- Create: `.verification/daytona-worker-image-build.log` outside Git
- Create: `.verification/daytona-worker-runtime.log` outside Git
- Create: `.verification/daytona-task4-focused-provenance.log` outside Git
- Create: `.verification/daytona-worker-image-provenance.log` outside Git
- Create: `.verification/daytona-worker-runtime-provenance.log` outside Git
- Create: `.verification/daytona-task4-verifier-provenance.log` outside Git
- Create: `.verification/daytona-task4-verifier-provenance-rerun.log` outside Git
- Create: `.verification/daytona-task4-final-provenance.log` outside Git

- [x] **Step 1: Confirm local prerequisites and zero Daytona resources**

Run:

```bash
docker info >/dev/null
docker buildx version
df -h . /var/lib/docker
daytona list --format json
git status --short
```

Expected: Docker and Buildx are available, disk is adequate for the existing 13.6 GB-class proof image, Daytona lists zero sandboxes, and tracked source is clean. This listing is read-only.

- [x] **Step 2: Run the focused recovery suite without credentials**

Run:

```bash
python3 -m pytest -q \
  backend/tests/test_daytona.py \
  backend/tests/test_run_daytona_gpu_smoke.py \
  backend/tests/test_daytona_release_policy.py \
  backend/tests/test_remote_contracts.py \
  backend/tests/test_release_evidence.py \
  backend/tests/test_release_preflight.py \
  backend/tests/test_verify_script.py \
  backend/tests/test_operational_docs.py
VERIFY_DAYTONA=0 ALLOW_DAYTONA_MUTATION=0 \
  python3 -m backend.scripts.run_daytona_gpu_smoke --dry-run
```

Expected: all focused tests pass, dry-run succeeds, and no cloud mutation occurs.

- [x] **Step 3: Build the exact image locally**

Run:

```bash
mkdir -p .verification
set -o pipefail
docker buildx build \
  --progress=plain \
  --load \
  --file backend/daytona_worker/Dockerfile \
  --tag fotball-analyst-daytona-recovery:local \
  . 2>&1 | tee .verification/daytona-worker-image-build.log
```

Expected: exit 0. Do not substitute a partial wheel installation or a different Dockerfile if the full build fails.

- [x] **Step 4: Prove imports, package closure, environment, and dynamic links**

Run:

```bash
set -o pipefail
docker run --rm --network none \
  fotball-analyst-daytona-recovery:local \
  bash -lc '
    set -euo pipefail
    python -m pip check
    test "$QT_QPA_PLATFORM" = offscreen
    python -c "import boto3,cv2,numpy,pandas,pydantic,torch,ultralytics; import backend.app.processor,backend.app.proof_runtime; value=torch.ones(1); assert float(value.item())==1.0"
    cv2_so="$(python -c "import cv2; from pathlib import Path; print(next(Path(cv2.__file__).parent.glob(\"*.so\")))")"
    ldd "$cv2_so" | tee /tmp/cv2-ldd.txt
    ! grep -F "not found" /tmp/cv2-ldd.txt
    dpkg-query -W -f="\${Package}=\${Version}\n" libgl1 libglib2.0-0 libxcb1
  ' 2>&1 | tee .verification/daytona-worker-runtime.log
```

Expected: `pip check` reports no broken requirements; all imports and the CPU tensor pass; `ldd` contains no `not found`; the three installed Ubuntu package versions are printed. CUDA remains intentionally unproved locally.

- [x] **Step 5: Run and retain the complete credential-free proof**

Task 4 is complete. The successful verifier receipt and its twelve gate logs were preserved before later diagnostic reruns. They bind behavior commit `2829132dc63aa0c030540794ef3c87160ceca9bd`; subsequent commits through `dac6ae39e3ee43c1bed0833dcc38833d5d676341` change only this plan. The later strict-umask run is retained as a diagnosed harness failure, and its two affected tests passed under scoped `umask 022`. A second later run passed every gate and stopped only because the receipt writer correctly rejected auxiliary untracked proof files. Do not relabel either failed transcript as successful evidence.

The retained proof is:

- `.verification/daytona-task4-prior-verifier/receipt.json` and its twelve logs: successful canonical verifier evidence for `2829132`.
- `.verification/daytona-task4-focused-provenance.log`: 849 focused tests and credential-free dry-run.
- `.verification/daytona-worker-image-provenance.log`: exact Buildx inputs, worker-context digest, local image inspection, and zero statuses.
- `.verification/daytona-worker-runtime-provenance.log`: `--network none` runtime, dependency/import/CPU/offscreen/linkage proof, and zero statuses.
- `.verification/daytona-task4-verifier-provenance*.log`: the two later, explicitly failed diagnostic runs.
- `.verification/daytona-task4-final-provenance.log`: receipt/hash/image/container/Daytona/status validation and the exact reason each later diagnostic stopped.
- `.verification/daytona-task4-post-list.json`: read-only Daytona listing with zero sandboxes.

Validate without moving, overwriting, or relabeling any artifact:

```bash
set -euo pipefail
behavior=2829132dc63aa0c030540794ef3c87160ceca9bd
receipt=.verification/daytona-task4-prior-verifier/receipt.json
test -f "$receipt" && test ! -L "$receipt" && test "$(stat -c %a "$receipt")" = 600
test "$(sha256sum "$receipt" | cut -d ' ' -f 1)" = \
  dd8448a7f7333e7a07a530a845e6a4003893589b1d796cd61b5a53aa5b9b7f1d
test "$(jq -r .repositoryCommit "$receipt")" = "$behavior"
manifest_sha="$(git show "${behavior}:backend/release/v7.3.json" | sha256sum | cut -d ' ' -f 1)"
test "$(jq -r .manifestSha256 "$receipt")" = "$manifest_sha"
test "$(sha256sum backend/release/v7.3.json | cut -d ' ' -f 1)" = "$manifest_sha"
test "$(git diff --name-only "$behavior"..HEAD)" = \
  docs/superpowers/plans/2026-09-09-daytona-worker-runtime-recovery.md
test -f .verification/daytona-task4-post-list.json
test ! -L .verification/daytona-task4-post-list.json
test "$(stat -c %a .verification/daytona-task4-post-list.json)" = 600
jq -e 'type == "object" and (.items | type == "array") and (.items | length == 0)' \
  .verification/daytona-task4-post-list.json >/dev/null
jq -e '(.gates | type == "array") and ([.gates[].name] == [
  "backend", "sidecar", "frontend-tests", "lint", "typecheck-app",
  "typecheck-node", "build", "backend-startup", "manifest",
  "runtime-options", "preflight-negatives", "prod-audit"
])' "$receipt" >/dev/null
for index in $(seq 0 11); do
  name="$(jq -er ".gates[$index].name | select(type == \"string\")" "$receipt")"
  expected="$(jq -er ".gates[$index].logSha256 | select(type == \"string\")" "$receipt")"
  log=".verification/daytona-task4-prior-verifier/logs/$name.log"
  test -f "$log" && test ! -L "$log" && test "$(stat -c %a "$log")" = 600
  test "$(sha256sum "$log" | cut -d ' ' -f 1)" = "$expected"
done
proof_files=(
  .verification/daytona-worker-image-build.log
  .verification/daytona-worker-runtime.log
  .verification/daytona-task4-focused-provenance.log
  .verification/daytona-worker-image-provenance.log
  .verification/daytona-worker-runtime-provenance.log
  .verification/daytona-task4-verifier-provenance.log
  .verification/daytona-task4-verifier-provenance-rerun.log
  .verification/daytona-task4-final-audit.log
  .verification/daytona-task4-final-provenance.log
)
for proof in "${proof_files[@]}"; do
  test -s "$proof" && test ! -L "$proof" && test "$(stat -c %a "$proof")" = 600
done
sha256sum -c <<'EOF'
9b061661d059404807679f9adc90a293bc13121f758ca5a24a604eaf5cffb1ac  .verification/daytona-worker-image-build.log
c7cd4ee5753b9833ea776b7a55f7e4e4069567e92a1c26c9038ad9082f98066e  .verification/daytona-worker-runtime.log
b59fab0d07347958a9a99493094d84430fda7376440d0b7748f90c1c50a8bf49  .verification/daytona-task4-focused-provenance.log
39e394130b4f32586516c7ba58f739ab3412458647b234f81d4d2369f6c3112d  .verification/daytona-worker-image-provenance.log
61ae067647e1de4577cb63bf514f2da81af7e752cf9193fe33689be73d0037b9  .verification/daytona-worker-runtime-provenance.log
583f8637a549caa5e0781105590fc9805e84a9ae3d1d6f956dba6d6d2e4ce231  .verification/daytona-task4-verifier-provenance.log
d0989c588e7f24229afb2ceef5412f0fb3798119ec8529a3d31aa1f43e06d5cd  .verification/daytona-task4-verifier-provenance-rerun.log
74c63bb2441231728ac16078ce674c43d473fc8e8b137ca90d57a70dc9556d33  .verification/daytona-task4-final-audit.log
34821b17e5ff6fd60ec63ee5b0b744732e390af12c7b7268fc0c80a02c1d0330  .verification/daytona-task4-final-provenance.log
458ff8cca9ebe47caa207dd92757ad604f740357269324f8f3e80c9190e61471  .verification/daytona-task4-post-list.json
EOF
scan_files=("${proof_files[@]}" "$receipt" \
  .verification/daytona-task4-post-list.json \
  .verification/daytona-task4-prior-verifier/logs/*.log)
if rg -q -i 'DAYTONA_API_KEY[[:space:]]*=|dtn_[[:alnum:]]{20,}' \
  "${scan_files[@]}"; then
  exit 1
else
  test "$?" -eq 1
fi
container_ids="$(docker ps -aq)"
test -z "$container_ids"
test "$(docker image inspect --format '{{.Id}}|{{.Size}}|{{json .RepoDigests}}' \
  fotball-analyst-daytona-recovery:local)" = \
  'sha256:b1b005d796d42d7c52f604cba78f3009f439a954f4caf8c249b815a436cf301d|13794247541|[]'
git diff --quiet
git diff --cached --quiet
```

Expected: every command exits zero. All proof files are mode `0600` and credential scans are clean. No CUDA execution is claimed. A fresh current-commit verifier receipt is deliberately deferred to M4 in Task 6, where the canonical release chain requires it.

### Task 5: Refreeze the final corrected source as S4

**Files:**

- Delete: `backend/release/v7.3.json`
- Delete: `backend/release/verification/v7.3-pre-cloud.json`

- [ ] **Step 1: Audit the pre-freeze tree**

Run:

```bash
git status --short
git diff --check
git fsck --no-reflogs --full
rg -n "RUNPOD_API_KEY|PROCESSING_BACKEND.?runpod|deploy_to_runpod" \
  backend scripts .github README.md docs/status docs/runbooks
```

Expected: tracked files are clean, Git object checks pass, only `.verification/` is untracked, and no active RunPod execution path is found. Historical/archive references are not active code.

- [ ] **Step 2: Remove only the stale active bindings**

Use `apply_patch` to delete exactly:

```text
backend/release/v7.3.json
backend/release/verification/v7.3-pre-cloud.json
```

Do not remove old Git history, attempt records, `.verification/`, models, videos, or the local proof image.

- [ ] **Step 3: Commit and record S4**

Run:

```bash
git add -u -- backend/release/v7.3.json backend/release/verification/v7.3-pre-cloud.json
git diff --cached --check
git commit -m "feat: refreeze Daytona worker runtime recovery source"
s4="$(git rev-parse HEAD)"
git diff-tree --no-commit-id --name-only -r HEAD
git status --short
```

Expected: record the 40-character HEAD as `S4`; exactly the two stale bindings were deleted; only `.verification/` remains untracked. No tracked source, test, plan, or status file changes after S4.

### Task 6: Build M4, the verifier receipt, and E04

**Files:**

- Create: `backend/release/v7.3.json`
- Modify: `docs/recovery/2026-08-19/current-tree-inventory.json`
- Create: `backend/release/verification/v7.3-pre-cloud.json`

- [ ] **Step 1: Regenerate the manifest from S4's parent copy**

Run:

```bash
s4="$(git rev-parse HEAD)"
release_template="$(mktemp)"
git show "${s4}^:backend/release/v7.3.json" \
  | jq 'del(.sourceCommit, .createdAt)' > "$release_template"
created_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 -m backend.scripts.write_release_manifest \
  --input "$release_template" \
  --output backend/release/v7.3.json \
  --artifact-root . \
  --source-commit "$s4" \
  --created-at "$created_at"
rm -f -- "$release_template"
```

Expected: the manifest is regenerated from the last active manifest's accepted data with only generated identity fields replaced.

- [ ] **Step 2: Update only the inventory replacement identity**

Run:

```bash
inventory_tmp="$(mktemp)"
jq --arg source "$s4" --arg recorded "$created_at" '
  (.retirementEvidence[]
    | select(.path == "backend/storage/runtime/promoted_touchline_detector_candidate.json")
    | .sourceCommit) = $source
  | (.retirementEvidence[]
    | select(.path == "backend/storage/runtime/promoted_touchline_detector_candidate.json")
    | .recordedAt) = $recorded
' docs/recovery/2026-08-19/current-tree-inventory.json > "$inventory_tmp"
mv -- "$inventory_tmp" docs/recovery/2026-08-19/current-tree-inventory.json
git diff -- backend/release/v7.3.json docs/recovery/2026-08-19/current-tree-inventory.json
```

Expected: the inventory diff changes only `sourceCommit` and `recordedAt` in the one replacement record; every other record remains semantically unchanged.

- [ ] **Step 3: Validate and commit M4**

Run:

```bash
python3 -m pytest -q \
  backend/tests/test_release_manifest.py \
  backend/tests/test_write_release_manifest.py
git add backend/release/v7.3.json docs/recovery/2026-08-19/current-tree-inventory.json
git diff --cached --check
git commit -m "feat: bind Daytona worker runtime recovery release"
m4="$(git rev-parse HEAD)"
test "$(git rev-parse HEAD^)" = "$s4"
git diff-tree --no-commit-id --name-only -r HEAD
```

Expected: tests pass; record HEAD as `M4`; `M4^ == S4`; exactly the manifest and inventory are committed.

- [ ] **Step 4: Create a fresh canonical receipt bound to M4**

Run:

```bash
VERIFY_DAYTONA=0 ALLOW_DAYTONA_MUTATION=0 scripts/verify.sh
jq -e --arg commit "$m4" '.repositoryCommit == $commit' .verification/receipt.json
manifest_sha256="$(sha256sum backend/release/v7.3.json | cut -d ' ' -f 1)"
jq -e --arg digest "$manifest_sha256" '.manifestSha256 == $digest' \
  .verification/receipt.json
```

Expected: all twelve local gates pass and the fresh untracked receipt binds M4 and the current manifest digest.

- [ ] **Step 5: Generate and commit E04**

Run:

```bash
python3 -m backend.scripts.write_verification_evidence \
  --phase pre_cloud \
  --output backend/release/verification/v7.3-pre-cloud.json
jq -e --arg source "$s4" --arg verification "$m4" '
  .sourceCommit == $source
  and .verificationCommit == $verification
  and .overallPassed == false
  and .remoteExecution == null
  and (.gates[-1].name == "daytona-gpu-smoke")
  and (.gates[-1].status == "pending")
' backend/release/verification/v7.3-pre-cloud.json
git add backend/release/verification/v7.3-pre-cloud.json
git diff --cached --check
git commit -m "docs: record Daytona worker recovery pre-cloud verification"
e04="$(git rev-parse HEAD)"
test "$(git rev-parse HEAD^)" = "$m4"
git diff-tree --no-commit-id --name-only -r HEAD
```

Expected: record HEAD as `E04`; `E04^ == M4`; only the pre-cloud evidence is committed.

- [ ] **Step 6: Run tracked build-only preflight**

Run:

```bash
manifest_sha256="$(sha256sum backend/release/v7.3.json | cut -d ' ' -f 1)"
python3 -m backend.release.preflight validate \
  --repo-root . \
  --manifest backend/release/v7.3.json \
  --evidence backend/release/verification/v7.3-pre-cloud.json \
  --mode build-only \
  --image-tag "v7.3-${s4}-${manifest_sha256:0:12}"
git diff --name-only "$s4..$e04"
```

Expected: preflight succeeds. The range contains only `backend/release/v7.3.json`, `docs/recovery/2026-08-19/current-tree-inventory.json`, and `backend/release/verification/v7.3-pre-cloud.json`.

- [ ] **Step 7: Obtain two independent zero-finding reviews**

Dispatch one specification-compliance reviewer and one adversarial quality/security reviewer. Give each the approved spec, this plan, S4/M4/E04 identities, focused results, both local image proof logs, canonical verifier logs, build-only preflight output, current zero-sandbox listing, and the complete diff from `4bc5a519` through E04.

Expected: both reviewers independently return zero Critical, Important, or Minor findings. Any source correction invalidates S4/M4/E04: test the correction, rebuild the entire chain, and repeat both reviews rather than waiving a finding.

### Task 7: Stop at the cloud-authorization boundary

**Files:** None.

- [ ] **Step 1: Recheck readiness without mutation**

Run:

```bash
git status --short --branch
daytona list --format json
python3 -m backend.scripts.run_daytona_gpu_smoke --dry-run
jq -e '.gates[-1].status == "pending" and .remoteExecution == null' \
  backend/release/verification/v7.3-pre-cloud.json
```

Expected: only designated `.verification/` artifacts are untracked, Daytona lists zero sandboxes, dry-run passes, and gate 13 is still pending.

- [ ] **Step 2: Ask for separate authorization and stop**

Report the exact S4, M4, E04, manifest digest, test totals, local image proof, two review results, and zero-sandbox listing. Ask the user to authorize exactly one third Daytona sandbox while the receipt is fresh.

Do not run `VERIFY_DAYTONA=1`, `ALLOW_DAYTONA_MUTATION=1`, `--real-smoke`, `daytona create`, or any equivalent cloud mutation in this task. Spec approval and plan execution are not cloud authorization.

### Task 8: Run exactly one third smoke only after explicit authorization

**Files:**

- Create outside Git: `/tmp/fotball-analyst-daytona-third-smoke.json`
- Create after success: `backend/release/verification/v7.3.json`
- Modify after success or contained failure: `docs/recovery/2026-08-24/daytona-gpu-smoke.md`
- Modify after contained failure: `docs/status/current.md`

- [ ] **Step 1: Revalidate the authorization window and host credential**

Only after the user explicitly authorizes the third sandbox, run without printing the credential:

```bash
test -n "${DAYTONA_API_KEY:-}"
test ! -e /tmp/fotball-analyst-daytona-third-smoke.json
daytona list --format json
git status --short
python3 -m backend.scripts.run_daytona_gpu_smoke --dry-run
jq -e --arg commit "$(git rev-parse HEAD^)" '.verificationCommit == $commit' \
  backend/release/verification/v7.3-pre-cloud.json
manifest_sha256="$(sha256sum backend/release/v7.3.json | cut -d ' ' -f 1)"
source_commit="$(jq -r '.sourceCommit' backend/release/v7.3.json)"
python3 -m backend.release.preflight validate \
  --repo-root . \
  --manifest backend/release/v7.3.json \
  --evidence backend/release/verification/v7.3-pre-cloud.json \
  --mode build-only \
  --image-tag "v7.3-${source_commit}-${manifest_sha256:0:12}"
```

Expected: the host key exists without being displayed; zero sandboxes exist; only `.verification/` is untracked; dry-run passes; the receipt and E04 chain remain fresh and unchanged. If any check fails, do not create a sandbox.

- [ ] **Step 2: Execute the real-smoke command exactly once**

Run this command once and record its status without retrying:

```bash
umask 077
set +e
VERIFY_DAYTONA=1 ALLOW_DAYTONA_MUTATION=1 \
  python3 -m backend.scripts.run_daytona_gpu_smoke --real-smoke \
  > /tmp/fotball-analyst-daytona-third-smoke.json
smoke_status="$?"
set -e
chmod 600 /tmp/fotball-analyst-daytona-third-smoke.json
printf 'third smoke exit status: %s\n' "$smoke_status"
```

Expected on success: status 0 and one canonical `RemoteExecution` JSON line. Expected on contained command failure: status 2 and one canonical failure JSON line. Never run the command a second time.

- [ ] **Step 3: Independently prove absence and branch on the one result**

Run:

```bash
daytona list --format json
jq -e . /tmp/fotball-analyst-daytona-third-smoke.json >/dev/null
```

Expected: Daytona lists zero sandboxes and the private result parses as JSON.

If `smoke_status` is nonzero, require:

```bash
jq -e '
  .mode == "real-smoke"
  and .status == "failed"
  and .error == "Daytona smoke command failed"
  and (.commandResult.exitCode != 0)
' /tmp/fotball-analyst-daytona-third-smoke.json
```

Append `## Attempt 3 — failed` to the recovery record with E04 identities, sandbox lifecycle evidence, the fixed failed stage, exit code, bounded/redacted output, cleanup confirmation, independent zero listing, and the fact that gate 13 remains incomplete. Update `docs/status/current.md` to identify attempt 3 as the latest contained failure, zero remaining sandboxes, and no authorized fourth attempt. Commit only those two documentation paths and stop. Do not generate final evidence or imply a fourth attempt.

If `smoke_status` is zero, require:

```bash
jq -e '
  .deletionConfirmed == true
  and .cleanupAttempts >= 1
  and .runpodMutationOccurred == false
  and .registryMutationOccurred == false
  and ([.commandResults[].exitCode] | all(. == 0))
' /tmp/fotball-analyst-daytona-third-smoke.json
```

Expected: all assertions pass before final evidence is written.

- [ ] **Step 4: Generate success-only final evidence**

Run only for `smoke_status == 0`:

```bash
python3 -m backend.scripts.write_verification_evidence \
  --phase final \
  --remote-execution /tmp/fotball-analyst-daytona-third-smoke.json \
  --output backend/release/verification/v7.3.json
jq -e '
  .phase == "final"
  and .overallPassed == true
  and .remoteExecution.deletionConfirmed == true
  and (.gates[-1].status == "passed")
' backend/release/verification/v7.3.json
```

Expected: all thirteen gates pass and the final evidence binds the exact S4, M4, manifest, worker-context digest, and successful remote report.

- [ ] **Step 5: Append attempt 3 without rewriting attempts 1 or 2**

Append `## Attempt 3 — passed` to `docs/recovery/2026-08-24/daytona-gpu-smoke.md`. Copy exact values from the private report for source commit, verification commit, manifest SHA-256, worker-context SHA-256, image, SDK, target, requested/observed GPU, sandbox ID, four lifecycle timestamps, three command results, upload/download hashes and sizes, cleanup attempts, deletion confirmation, and zero RunPod/registry mutation. Render the credential only as `DAYTONA_API_KEY=<redacted>`.

- [ ] **Step 6: Commit final evidence and chronology**

Run:

```bash
git add \
  backend/release/verification/v7.3.json \
  docs/recovery/2026-08-24/daytona-gpu-smoke.md
git diff --cached --check
git commit -m "docs: record Daytona worker recovery verification"
git diff-tree --no-commit-id --name-only -r HEAD
```

Expected: exactly the two listed paths are committed.

### Task 9: Complete stabilization acceptance after a successful smoke

**Files:**

- Create: `docs/recovery/2026-08-24/final-verification-report.md`
- Modify: `docs/status/current.md`

- [ ] **Step 1: Run deploy preflight against tracked final evidence**

Run:

```bash
manifest_sha256="$(sha256sum backend/release/v7.3.json | cut -d ' ' -f 1)"
source_commit="$(jq -r '.sourceCommit' backend/release/v7.3.json)"
python3 -m backend.release.preflight validate \
  --repo-root . \
  --manifest backend/release/v7.3.json \
  --evidence backend/release/verification/v7.3.json \
  --mode deploy \
  --image-tag "v7.3-${source_commit}-${manifest_sha256:0:12}"
```

Expected: deploy preflight accepts the tracked final evidence without a sandbox, registry push, or RunPod call.

- [ ] **Step 2: Re-run clean acceptance without cloud mutation**

Run:

```bash
VERIFY_DAYTONA=0 ALLOW_DAYTONA_MUTATION=0 scripts/verify.sh
python3 -m pytest -q backend/tests/test_operational_docs.py
daytona list --format json
git status --short
```

Expected: all local gates and documentation tests pass, Daytona lists zero sandboxes, and only designated `.verification/` artifacts remain untracked.

- [ ] **Step 3: Write the final report and current status from evidence**

Create the final report with these exact sections: `Accepted release identities`, `Local verification`, `Worker image runtime proof`, `Daytona attempt chronology`, `Remote execution and deletion`, `Provider retirement and preserved data`, `Independent reviews`, and `Remaining operational action`. Populate them only from Git, verifier logs, image proof logs, the final evidence, the recovery record, and the current Daytona listing.

Update `docs/status/current.md` to state that Daytona is the sole remote GPU provider, attempt 3 passed, gate 13 is complete, zero sandboxes remain, no registry/RunPod mutation occurred, the application owns durable football-analysis results, and the exposed testing key must be rotated before production use. Remove the old statement that no further smoke is authorized; do not erase the two failed attempts.

- [ ] **Step 4: Test and commit final documentation**

Run:

```bash
python3 -m pytest -q backend/tests/test_operational_docs.py
git add \
  docs/recovery/2026-08-24/final-verification-report.md \
  docs/status/current.md
git diff --cached --check
git commit -m "docs: complete Daytona worker recovery"
git diff-tree --no-commit-id --name-only -r HEAD
```

Expected: documentation tests pass and exactly the two documentation paths are committed.

- [ ] **Step 5: Obtain final independent reviews and verify the goal**

Dispatch a fresh specification reviewer and a fresh adversarial quality/security reviewer. Require each to inspect the final commit, approved spec and plan, source/release ancestry, test and verifier logs, local image proof, all three attempt records, success-only final evidence, deploy preflight, current zero-sandbox listing, Daytona-only active path, preserved project data, and worktree state.

After both return zero findings, run:

```bash
VERIFY_DAYTONA=0 ALLOW_DAYTONA_MUTATION=0 scripts/verify.sh
python3 -m backend.release.preflight validate \
  --repo-root . \
  --manifest backend/release/v7.3.json \
  --evidence backend/release/verification/v7.3.json \
  --mode deploy \
  --image-tag "v7.3-$(jq -r '.sourceCommit' backend/release/v7.3.json)-$(sha256sum backend/release/v7.3.json | cut -c1-12)"
daytona list --format json
git status --short --branch
git log -15 --oneline --decorate
```

Expected: every local gate and deploy preflight passes, zero Daytona sandboxes remain, the `preservation-stabilization` branch contains the complete S4/M4/E04/final chain, and only designated `.verification/` artifacts are untracked. Remind the user to rotate the exposed testing key before any production use, then complete the active goal only if the full original cleanup/review objective and every acceptance item are proven.

## Plan self-review checklist

- The OpenCV image change is limited to `libgl1`, `libglib2.0-0`, `libxcb1`, and `QT_QPA_PLATFORM=offscreen`; requirements and immutable base policy stay fixed.
- Failed-command output is fixed-stage, integer-exit, bounded, exact-key-filtered, credential-family-redacted, and emitted only after confirmed cleanup.
- Cleanup failure overrides and suppresses command diagnostics.
- Failure JSON remains separate from and rejected by success-only release evidence.
- Full local image build, `pip check`, imports, CPU tensor, `ldd`, and package-version proof occur before any cloud authorization request.
- Every tracked source change precedes S4; M4 and E04 are generated in strict parent order with a fresh canonical receipt.
- Two independent reviews precede the separate third-sandbox request; spec approval does not authorize the cloud run.
- Exactly one cloud command is allowed after explicit authorization, with no retry and truthful success/failure branches.
- Attempts 1 and 2, Git history, `.verification/`, models, videos, product data, and the local proof image remain preserved.
- No adapter, schema, SDK pin, failure framework, registry push, RunPod path, or unrelated refactor is added.
