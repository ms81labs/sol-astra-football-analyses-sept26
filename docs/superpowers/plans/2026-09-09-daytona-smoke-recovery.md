# Daytona Smoke Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the Daytona worker image and failed-create cleanup path, rebuild verifier-bound release evidence, run the one authorized corrective GPU smoke, and finish the paused-project stabilization with no orphaned cloud resources.

**Architecture:** Keep the provider-neutral football-analysis pipeline unchanged. Fix the two defects at their shared boundaries: remove the unused incompatible base-image package before installing the locked worker environment, and give every SDK creation an exact random name/label ownership pair that permits safe recovery after the SDK allocates and then raises. Re-freeze the corrected source before the one authorized cloud attempt and publish final evidence only from a successful, deleted sandbox.

**Tech Stack:** Python 3.12, pytest, Daytona Python SDK 0.207.0 and CLI, OCI/Docker, immutable PyTorch/CUDA base image, Bash, Git, JSON Schema.

---

## Fixed boundaries

- Work only in `/root/WorkSpace/fotball-analyst/.worktrees/preservation-stabilization` on branch `preservation-stabilization`.
- Preserve `.verification/receipt.json` until the canonical verifier replaces it; never stage `.verification/`.
- Never print, inspect, persist, or upload the Daytona API key. The host process is its only consumer.
- Do not change the PyTorch base digest, worker requirements, evidence schema, or RunPod archive.
- Keep `--require-hashes`, `--no-deps`, and `pip check` in the image build.
- The corrective smoke is exactly one create call with no creation retry. A third sandbox is not authorized.
- Never delete a Daytona resource unless both its generated name and ownership label match the current attempt, or its exact identifier is already bound in that attempt's evidence.
- Keep final evidence success-only. Record failed attempts in Markdown.

## File responsibility map

**Create:**

- `docs/recovery/2026-08-24/daytona-gpu-smoke.md` — immutable chronology for failed attempt 1 and corrected attempt 2.

**Modify:**

- `docs/status/current.md` — truthful current migration/release status.
- `backend/app/daytona.py` — shared SDK allocation ownership, recovery, and cleanup.
- `backend/tests/test_daytona.py` — adversarial allocation-recovery coverage.
- `backend/daytona_worker/Dockerfile` — remove inherited torchaudio before locked installation.
- `backend/scripts/run_daytona_gpu_smoke.py` — exact Dockerfile identity expected by preflight.
- `backend/tests/test_run_daytona_gpu_smoke.py` — image-sequence regression test.
- `backend/release/v7.3.json` — regenerated manifest bound to corrected source.
- `docs/recovery/2026-08-19/current-tree-inventory.json` — corrected release replacement identity.
- `backend/release/verification/v7.3-pre-cloud.json` — fresh receipt-derived pre-cloud evidence.
- `docs/recovery/2026-08-24/final-verification-report.md` — final requirement-by-requirement evidence.

**Create only after successful cloud execution:**

- `backend/release/verification/v7.3.json` — schema-v2 final evidence generated from the corrective smoke report.

## Task 1: Record failed attempt 1 truthfully

**Files:**

- Create: `docs/recovery/2026-08-24/daytona-gpu-smoke.md`
- Modify: `docs/status/current.md`
- Test: `backend/tests/test_operational_docs.py`

- [ ] **Step 1: Write the failed-attempt report**

Create `docs/recovery/2026-08-24/daytona-gpu-smoke.md` with this factual content, wrapping the command without a credential value:

```markdown
# Daytona GPU smoke recovery

## Attempt 1 — failed during image build

- Date: 2026-09-09 UTC
- Command: `VERIFY_DAYTONA=1 ALLOW_DAYTONA_MUTATION=1 DAYTONA_API_KEY=<redacted> python3 -m backend.scripts.run_daytona_gpu_smoke --real-smoke`
- Source commit: `6d5c7536487ea026289cdd1420efaeef6232d2a5`
- Verification commit: `b5a0112b06be53b04ca3e0b4dce6ab08d4769fd6`
- Manifest SHA-256: `75f3fedfcc91a44b2f00c7f10f2970a74adb7770836c769e1d09ee4882f75a99`
- Sandbox: `9c489f49-a57d-46c2-963b-3b5dc33bb475`
- Result: Daytona reached the combined locked-dependency installation and `pip check` image-build step, then reported `build_failed`. No smoke command or football workload ran.
- Missing evidence: redirected smoke output was empty; exact build-stage timestamps and complete remote build logs were not captured.
- Cleanup: SDK 0.207.0 raised after allocation without returning the sandbox. The exact sandbox was deleted manually, and a subsequent independent Daytona listing returned zero sandboxes.
- Release status: gate 13 failed; no final verification evidence exists for this attempt.
- External mutations: no RunPod or registry mutation occurred.

The failed attempt is recovery history only. It must not be represented as a successful `remoteExecution` object.
```

- [ ] **Step 2: Correct the current-status claim**

Replace the sentence claiming no sandbox was created with:

```markdown
The first authorized Daytona smoke on 2026-09-09 created one private sandbox, but the worker image build failed before any smoke command ran. The exact sandbox was deleted manually and a subsequent independent listing confirmed zero sandboxes. Gate 13 remains incomplete while the corrected recovery design is implemented and locally verified.
```

- [ ] **Step 3: Verify the docs and commit**

Run:

```bash
python3 -m pytest -q backend/tests/test_operational_docs.py
git diff --check
git add docs/recovery/2026-08-24/daytona-gpu-smoke.md docs/status/current.md
git commit -m "docs: record failed Daytona smoke"
```

Expected: operational documentation tests pass; the commit contains exactly the two documentation paths.

## Task 2: Recover SDK allocations by exact ownership

**Files:**

- Modify: `backend/tests/test_daytona.py:1490-1535`
- Modify: `backend/tests/test_daytona.py:2050-2200`
- Modify: `backend/app/daytona.py:35-220`

- [ ] **Step 1: Add failing owned-recovery tests**

Add this deterministic raw-SDK fixture and the five complete recovery cases:

```python
def _sdk_failure_case(monkeypatch, mode):
    from backend.app.daytona import DaytonaSandboxSpec, _SdkClient
    token = "ab" * 16
    monkeypatch.setattr("backend.app.daytona.os.urandom", lambda size: bytes.fromhex(token))
    class Resources:
        def __init__(self, **values): self.values = values
    class Params:
        def __init__(self, **values): self.values = values
    class GpuType:
        RTX_PRO_6000 = "rtx"
        H100 = "h100"
    class NotFound(Exception): pass
    SDK = SimpleNamespace(
        Resources=Resources,
        CreateSandboxFromImageParams=Params,
        GpuType=GpuType,
        DaytonaNotFoundError=NotFound,
    )
    candidate = SimpleNamespace(
        id="sandbox-1",
        name="other" if mode == "wrong-name" else f"fa-{token}",
        labels={"football-analyst-owner": "other" if mode == "wrong-label" else token},
    )
    create_error = RuntimeError("provider create failure")
    class Raw:
        def __init__(self): self.params = None; self.gets = []; self.deletes = []
        def create(self, params, *, timeout):
            self.params = params
            raise create_error
        def get(self, name, *, request_timeout):
            self.gets.append((name, request_timeout))
            if mode == "lookup-error":
                raise RuntimeError("provider-secret")
            if mode == "absent" or len(self.gets) > 1:
                raise NotFound()
            return candidate
        def delete(self, target, *, timeout, wait):
            self.deletes.append((target, timeout, wait))
    raw = Raw()
    spec = DaytonaSandboxSpec(
        "image", False, True, False, 45, True, (), 4, 8, 10, 1,
        ("RTX-PRO-6000", "H100"),
    )
    return _SdkClient(raw, SDK), raw, spec, create_error, token, candidate


def test_sdk_create_recovers_and_deletes_exact_owned_allocation(monkeypatch):
    adapter, raw, spec, create_error, token, sandbox = _sdk_failure_case(
        monkeypatch, "owned"
    )
    with pytest.raises(RuntimeError) as raised:
        adapter.create(spec, 600)
    assert raised.value is create_error
    assert raw.params.values["name"] == f"fa-{token}"
    assert raw.params.values["labels"] == {"football-analyst-owner": token}
    assert raw.deletes == [(sandbox, 600, True)]


def test_sdk_create_confirmed_absent_preserves_original_failure(monkeypatch):
    adapter, raw, spec, create_error, _, _ = _sdk_failure_case(monkeypatch, "absent")
    with pytest.raises(RuntimeError) as raised:
        adapter.create(spec, 600)
    assert raised.value is create_error
    assert raw.deletes == []


@pytest.mark.parametrize("mode", ["wrong-label", "wrong-name"])
def test_sdk_create_refuses_unowned_recovery(monkeypatch, mode):
    from backend.app.daytona import DaytonaExecutionError
    adapter, raw, spec, _, _, _ = _sdk_failure_case(monkeypatch, mode)
    with pytest.raises(DaytonaExecutionError) as raised:
        adapter.create(spec, 600)
    assert str(raised.value) == "create: sandbox cleanup was not confirmed"
    assert raw.deletes == []


def test_sdk_create_inconclusive_lookup_is_secret_safe(monkeypatch):
    from backend.app.daytona import DaytonaExecutionError
    adapter, raw, spec, _, _, _ = _sdk_failure_case(monkeypatch, "lookup-error")
    with pytest.raises(DaytonaExecutionError) as raised:
        adapter.create(spec, 600)
    assert str(raised.value) == "create: sandbox cleanup was not confirmed"
    assert "secret" not in str(raised.value)
    assert raw.deletes == []
```

Update `test_sdk_adapter_translates_policy_to_exact_pinned_sdk_objects` so its fake constructor accepts `name` and `labels`, patch `os.urandom` to `b"\xab" * 16`, and expect `name="fa-" + "ab" * 16` plus the exact ownership label. Existing image-context cleanup tests must remain unchanged except for accepting the two new constructor keywords.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run:

```bash
python3 -m pytest -q \
  backend/tests/test_daytona.py::test_sdk_create_recovers_and_deletes_exact_owned_allocation \
  backend/tests/test_daytona.py::test_sdk_create_confirmed_absent_preserves_original_failure \
  backend/tests/test_daytona.py::test_sdk_create_refuses_unowned_recovery \
  backend/tests/test_daytona.py::test_sdk_create_inconclusive_lookup_is_secret_safe
```

Expected: failures because SDK create parameters lack the generated ownership name/label and failed creation is not recovered.

- [ ] **Step 3: Implement the shared minimal recovery**

Add constants beside the existing validation constants:

```python
_SDK_NAME_PREFIX = "fa-"
_SDK_OWNER_LABEL = "football-analyst-owner"
```

At the start of `_SdkClient.create`, generate and validate the fixed-size token:

```python
owner_token = os.urandom(16).hex()
sandbox_name = f"{_SDK_NAME_PREFIX}{owner_token}"
```

Pass ownership into `CreateSandboxFromImageParams`:

```python
name=sandbox_name,
labels={_SDK_OWNER_LABEL: owner_token},
```

Replace the existing exception body with the exact-name recovery rule:

```python
except BaseException as create_error:
    if sandbox is None:
        try:
            candidate = self.get(sandbox_name, timeout=timeout)
        except DaytonaConfirmedAbsent:
            raise create_error
        except BaseException:
            raise DaytonaExecutionError(
                "create: sandbox cleanup was not confirmed"
            ) from None
        labels = getattr(candidate, "labels", None)
        if (
            getattr(candidate, "name", None) != sandbox_name
            or type(labels) is not dict
            or labels.get(_SDK_OWNER_LABEL) != owner_token
        ):
            raise DaytonaExecutionError(
                "create: sandbox cleanup was not confirmed"
            ) from None
        sandbox = candidate
    if not self._cleanup_unreturned_sandbox(sandbox, timeout):
        raise _UnreturnedSandboxCleanupError(sandbox) from None
    raise create_error
```

Do not parse exception messages, list broad sandbox sets, or delete mismatched candidates.

- [ ] **Step 4: Run all adapter and smoke tests**

Run:

```bash
python3 -m pytest -q backend/tests/test_daytona.py backend/tests/test_run_daytona_gpu_smoke.py
```

Expected: all tests pass; the fake smoke still makes exactly one create call and all secret-safety assertions remain green.

- [ ] **Step 5: Commit the lifecycle fix**

Run:

```bash
git add backend/app/daytona.py backend/tests/test_daytona.py
git commit -m "fix: recover Daytona allocations after create failure"
```

Expected: exactly two files committed.

## Task 3: Make the worker image dependency closure consistent

**Files:**

- Modify: `backend/tests/test_run_daytona_gpu_smoke.py:90-125`
- Modify: `backend/daytona_worker/Dockerfile`
- Modify: `backend/scripts/run_daytona_gpu_smoke.py:55-70`

- [ ] **Step 1: Add a failing exact-sequence test**

Add:

```python
def test_worker_image_removes_incompatible_base_audio_before_locked_install():
    dockerfile = (ROOT / "backend/daytona_worker/Dockerfile").read_text()
    expected = (
        "RUN python -m pip uninstall --yes torchaudio \\\n"
        " && python -m pip install --require-hashes --no-deps -r /tmp/requirements.lock \\\n"
        " && python -m pip check\n"
    )
    assert expected in dockerfile
    assert smoke.expected_dockerfile() == dockerfile
```

- [ ] **Step 2: Run the test and confirm RED**

Run:

```bash
python3 -m pytest -q backend/tests/test_run_daytona_gpu_smoke.py::test_worker_image_removes_incompatible_base_audio_before_locked_install
```

Expected: failure because the current Dockerfile does not uninstall inherited torchaudio.

- [ ] **Step 3: Change the Dockerfile and its exact identity**

Use this complete Dockerfile:

```dockerfile
FROM docker.io/pytorch/pytorch@sha256:417bd75df6365104c283ea4c1651fb3530d9eb5a4c2fafa51943cff2a94e6385
WORKDIR /workspace
COPY backend/daytona_worker/requirements.lock /tmp/requirements.lock
RUN python -m pip uninstall --yes torchaudio \
 && python -m pip install --require-hashes --no-deps -r /tmp/requirements.lock \
 && python -m pip check
COPY backend /workspace/backend
```

Make `expected_dockerfile()` return these exact bytes. Do not change either requirements file or its expected SHA-256.

- [ ] **Step 4: Run focused release/image tests**

Run:

```bash
python3 -m pytest -q \
  backend/tests/test_run_daytona_gpu_smoke.py \
  backend/tests/test_daytona_release_policy.py \
  backend/tests/test_release_evidence.py \
  backend/tests/test_release_preflight.py
```

Expected: all tests pass and the dry-run still rejects any Dockerfile deviation.

- [ ] **Step 5: Commit the image fix**

Run:

```bash
git add backend/daytona_worker/Dockerfile backend/scripts/run_daytona_gpu_smoke.py backend/tests/test_run_daytona_gpu_smoke.py
git commit -m "fix: make Daytona worker image build reproducible"
```

Expected: exactly three files committed.

## Task 4: Prove the corrected image and local release behavior

**Files:** None.

- [ ] **Step 1: Prove no Daytona resource exists before local work**

Run:

```bash
daytona list --format json
```

Expected: `items` is an empty array. This is read-only.

- [ ] **Step 2: Run the focused recovery suite**

Run:

```bash
python3 -m pytest -q \
  backend/tests/test_daytona.py \
  backend/tests/test_run_daytona_gpu_smoke.py \
  backend/tests/test_daytona_release_policy.py \
  backend/tests/test_release_evidence.py \
  backend/tests/test_release_preflight.py \
  backend/tests/test_verify_script.py \
  backend/tests/test_operational_docs.py
```

Expected: all pass with zero cloud creation calls.

- [ ] **Step 3: Build the complete worker image locally**

First require a usable local builder and adequate free space:

```bash
docker info >/dev/null
df -h . /var/lib/docker
```

Then run:

```bash
docker build \
  --progress=plain \
  --file backend/daytona_worker/Dockerfile \
  --tag fotball-analyst-daytona-recovery:local \
  .
docker run --rm fotball-analyst-daytona-recovery:local python -m pip check
```

Expected: the full image builds and `pip check` reports no broken requirements. If the builder or disk cannot complete this exact proof, stop before any Daytona mutation and report the environmental blocker; do not substitute a partial dependency check.

- [ ] **Step 4: Run the canonical credential-free verifier**

Run:

```bash
VERIFY_DAYTONA=0 ALLOW_DAYTONA_MUTATION=0 scripts/verify.sh
```

Expected: all local gates pass, Daytona is explicitly skipped, and a fresh `.verification/receipt.json` is produced. Do not stage it.

## Task 5: Refreeze corrected source as S3

**Files:**

- Delete: `backend/release/v7.3.json`
- Delete: `backend/release/verification/v7.3-pre-cloud.json`

- [ ] **Step 1: Audit the pre-freeze tree**

Run:

```bash
git status --short
git diff --check
git fsck --no-reflogs --full
rg -n "RUNPOD_API_KEY|PROCESSING_BACKEND.?runpod|deploy_to_runpod" backend scripts .github README.md docs/status docs/runbooks
```

Expected: only `.verification/` is untracked, Git object checks pass, and no active RunPod execution path is found.

- [ ] **Step 2: Remove stale active release bindings**

Delete only:

```text
backend/release/v7.3.json
backend/release/verification/v7.3-pre-cloud.json
```

Keep every older release commit in history and preserve `.verification/` untracked.

- [ ] **Step 3: Commit and record S3**

Run:

```bash
git add -u -- backend/release/v7.3.json backend/release/verification/v7.3-pre-cloud.json
git commit -m "feat: refreeze corrected Daytona source"
git rev-parse HEAD
git status --short
```

Expected: record the 40-character HEAD as `S3`; only `.verification/` remains untracked. No product, dependency, verifier, CI, or current-status path changes after S3.

## Task 6: Rebind metadata, receipt, and pre-cloud evidence

**Files:**

- Create: `backend/release/v7.3.json`
- Modify: `docs/recovery/2026-08-19/current-tree-inventory.json`
- Create: `backend/release/verification/v7.3-pre-cloud.json`

- [ ] **Step 1: Regenerate the manifest from the accepted release data**

Create a temporary template mechanically from the last accepted manifest while deleting only its generated identity fields:

```bash
release_template="$(mktemp)"
git show f42c3cd4:backend/release/v7.3.json \
  | jq 'del(.sourceCommit, .createdAt)' > "$release_template"
s3="$(git rev-parse HEAD)"
created_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 -m backend.scripts.write_release_manifest \
  --input "$release_template" \
  --output backend/release/v7.3.json \
  --artifact-root . \
  --source-commit "$s3" \
  --created-at "$created_at"
```

Update only `recordedAt` and `sourceCommit` in the existing `retirementEvidence` record for `backend/storage/runtime/promoted_touchline_detector_candidate.json` to the same `$created_at` and `$s3` values. Preserve every other inventory byte and field.

- [ ] **Step 2: Validate and commit M3**

Run:

```bash
python3 -m pytest -q backend/tests/test_release_manifest.py backend/tests/test_write_release_manifest.py
git add backend/release/v7.3.json docs/recovery/2026-08-19/current-tree-inventory.json
git commit -m "feat: rebind corrected Daytona v7.3 release metadata"
m3="$(git rev-parse HEAD)"
test "$(git rev-parse HEAD^)" = "$s3"
git diff-tree --no-commit-id --name-only -r HEAD
```

Expected: tests pass; record HEAD as `M3`; `M3^ == S3`; exactly the manifest and inventory are committed.

- [ ] **Step 3: Create a fresh verifier receipt bound to M3**

Run:

```bash
VERIFY_DAYTONA=0 ALLOW_DAYTONA_MUTATION=0 scripts/verify.sh
jq -e --arg commit "$m3" '.repositoryCommit == $commit' .verification/receipt.json
```

Expected: all twelve local gates pass and the receipt is bound to M3 plus the current manifest SHA-256.

- [ ] **Step 4: Generate and commit E03**

Run:

```bash
python3 -m backend.scripts.write_verification_evidence \
  --phase pre_cloud \
  --output backend/release/verification/v7.3-pre-cloud.json
jq -e --arg source "$s3" --arg verification "$m3" \
  '.sourceCommit == $source and .verificationCommit == $verification and
   .overallPassed == false and .remoteExecution == null' \
  backend/release/verification/v7.3-pre-cloud.json
git add backend/release/verification/v7.3-pre-cloud.json
git commit -m "docs: record corrected Daytona pre-cloud verification"
```

Expected: record HEAD as `E03`; only the pre-cloud evidence is committed.

- [ ] **Step 5: Run tracked build-only preflight**

Run:

```bash
manifest_sha256="$(sha256sum backend/release/v7.3.json | cut -d ' ' -f 1)"
python3 -m backend.release.preflight validate \
  --repo-root . \
  --manifest backend/release/v7.3.json \
  --evidence backend/release/verification/v7.3-pre-cloud.json \
  --mode build-only \
  --image-tag "v7.3-${s3}-${manifest_sha256:0:12}"
```

Expected: preflight succeeds, the evidence is tracked, and `S3..E03` contains only the manifest, inventory, and pre-cloud evidence.

- [ ] **Step 6: Obtain two independent pre-cloud approvals**

Dispatch one specification reviewer and one adversarial quality reviewer. Give both the recovery spec, this plan, `S3`, `M3`, `E03`, the focused test results, local image-build result, canonical verifier logs, and build-only preflight output. Resolve every Critical, Important, and Minor finding with another tested source correction and a new S/M/E chain; do not waive findings.

Expected: both reviewers return approval with zero open findings.

## Task 7: Run the one authorized corrective Daytona smoke

**Files:**

- Create: `/tmp/fotball-analyst-daytona-corrective-smoke.json` outside Git.
- Create after success: `backend/release/verification/v7.3.json`
- Modify after success: `docs/recovery/2026-08-24/daytona-gpu-smoke.md`

- [ ] **Step 1: Revalidate authorization, credentials, binding, and zero resources**

Run without printing the credential:

```bash
test -n "${DAYTONA_API_KEY:-}"
daytona list --format json
git status --short
python3 -m backend.scripts.run_daytona_gpu_smoke --dry-run
```

Expected: credential is available to the host process; Daytona lists zero sandboxes; only `.verification/` is untracked; dry-run reports SDK 0.207.0, target `us`, the immutable image, and GPU preference `RTX-PRO-6000,H100`.

- [ ] **Step 2: Run exactly one corrective smoke**

Ensure the private output path does not already exist, then run once:

```bash
test ! -e /tmp/fotball-analyst-daytona-corrective-smoke.json
umask 077
VERIFY_DAYTONA=1 ALLOW_DAYTONA_MUTATION=1 \
  python3 -m backend.scripts.run_daytona_gpu_smoke --real-smoke \
  > /tmp/fotball-analyst-daytona-corrective-smoke.json
```

Expected: exactly one private ephemeral sandbox is created; the image starts; GPU detection, production imports, bounded fixture, result/completion validation, deletion, and in-process absence confirmation pass. Never rerun this command. On failure, inspect and contain only the exact owned resource, document attempt 2 as failed, and stop because no third sandbox is authorized.

- [ ] **Step 3: Independently prove deletion**

Run:

```bash
daytona list --format json
jq -e '.deletionConfirmed == true and .cleanupAttempts >= 1 and
       .runpodMutationOccurred == false and .registryMutationOccurred == false' \
  /tmp/fotball-analyst-daytona-corrective-smoke.json
```

Expected: Daytona lists zero sandboxes and the report is valid. Do not delete any other resource if the listing is non-empty; stop for exact ownership review.

- [ ] **Step 4: Generate success-only final evidence**

Run:

```bash
python3 -m backend.scripts.write_verification_evidence \
  --phase final \
  --remote-execution /tmp/fotball-analyst-daytona-corrective-smoke.json \
  --output backend/release/verification/v7.3.json
jq -e '.phase == "final" and .overallPassed == true and
       .remoteExecution.deletionConfirmed == true' \
  backend/release/verification/v7.3.json
```

Expected: all thirteen gates pass and the final evidence is bound to S3, M3, the fresh manifest, worker-context digest, and successful remote report.

- [ ] **Step 5: Append attempt 2 without altering attempt 1**

Append a `## Attempt 2 — passed` section containing the exact source, verification, manifest, worker-context, image, SDK, target, requested and observed GPU, sandbox, creation/start/completion/deletion timestamps, command results, upload/download hashes and sizes, cleanup-attempt count, deletion proof, and explicit zero RunPod/registry mutation values read from the generated report. Render the API key only as `<redacted>`.

- [ ] **Step 6: Commit only final evidence and the smoke chronology**

Run:

```bash
git add backend/release/verification/v7.3.json docs/recovery/2026-08-24/daytona-gpu-smoke.md
git commit -m "docs: record corrected Daytona GPU release verification"
git diff-tree --no-commit-id --name-only -r HEAD
```

Expected: exactly the two listed files are committed.

## Task 8: Complete stabilization acceptance

**Files:**

- Create/modify: `docs/recovery/2026-08-24/final-verification-report.md`
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

Expected: deployment preflight accepts the final evidence and recorded sandbox deletion without creating a sandbox.

- [ ] **Step 2: Re-run clean acceptance without cloud mutation**

Run:

```bash
VERIFY_DAYTONA=0 ALLOW_DAYTONA_MUTATION=0 scripts/verify.sh
python3 -m pytest -q backend/tests/test_operational_docs.py
daytona list --format json
git status --short
```

Expected: all local gates pass, documentation tests pass, Daytona lists zero sandboxes, and only the regenerated `.verification/` directory is untracked.

- [ ] **Step 3: Write the final report and status**

The final report must enumerate the accepted commits, exact test counts and durations from the fresh logs, dependency/image proof, S3/M3/E03 identities, final manifest and evidence hashes, Daytona sandbox and GPU identities, deletion confirmation, archive and compatibility checks, retained branches/worktrees, and zero RunPod/registry mutation. `docs/status/current.md` must state that Daytona is the only active remote GPU provider, the corrective smoke passed, zero sandboxes remain, and the application owns durable football-analysis results.

- [ ] **Step 4: Commit final documentation**

Run:

```bash
git add docs/recovery/2026-08-24/final-verification-report.md docs/status/current.md
git commit -m "docs: complete Daytona stabilization verification"
git diff-tree --no-commit-id --name-only -r HEAD
```

Expected: exactly the two documentation paths are committed.

- [ ] **Step 5: Obtain final independent approval**

Dispatch a fresh specification reviewer and a fresh adversarial quality reviewer. Require them to inspect the final commit, recovery spec and plan, tests and verifier logs, release ancestry, failed/successful smoke chronology, final schema-v2 evidence, deployment preflight, current Daytona listing, Daytona-only active path, and worktree cleanliness.

Expected: both reviewers approve with zero open findings. Re-run any evidence affected by a correction before accepting it.

- [ ] **Step 6: Finish the goal only from current evidence**

Verify:

```bash
git status --short --branch
daytona list --format json
git log -12 --oneline --decorate
```

Expected: branch `preservation-stabilization`; only `.verification/` untracked; zero Daytona sandboxes; complete corrective commit chain present. Rotate the exposed Daytona API key, then mark the active goal complete only after every acceptance item above is proven.

## Plan self-review result

- Every recovery-spec requirement maps to Tasks 1–8.
- The only product-code change is the shared SDK ownership recovery; the only image change is removing unused inherited torchaudio.
- The requirements lock, immutable base digest, final evidence schema, provider-neutral worker, and football-analysis product boundary remain unchanged.
- Failed attempt 1 is preserved as history; final JSON evidence is generated only from successful attempt 2.
- The release chain is regenerated after all tracked source changes and before the only authorized corrective smoke.
- No cloud creation can occur before local image proof, canonical verification, tracked pre-cloud evidence, and two independent approvals.
