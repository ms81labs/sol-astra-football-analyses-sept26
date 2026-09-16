# Daytona Worker Runtime Recovery Design

## Status and scope

This design recovers the Daytona GPU release lane after the second authorized real smoke failed during remote execution. It replaces only the worker-runtime and failed-command-diagnostic portions of the existing recovery design. The product boundary is unchanged: the application owns match upload, video preparation, orchestration, validation, analytics, persistence, and presentation; Daytona supplies one private, ephemeral GPU computer for the sealed worker job.

Design approval does not authorize another Daytona sandbox. Implementation, complete credential-free verification, a fresh release chain, and two independent reviews must finish before the user is asked separately to authorize exactly one third real smoke. RunPod remains retired.

## Established incident facts

The second smoke used source commit `f0a28c649aa4de25f67880a414a94d7136e573ac`, verification commit `71397d1456514d353c93855429a66d725e17ec1d`, evidence commit `660b7d5eb01a0c78d3116422427b1877dd22f914`, and manifest SHA-256 `4578b5a332428ced4d449286805189551107c28270f3f31cfd7d209a488e1141`.

Daytona created private sandbox `bff48578-0084-47ab-803d-1075b1a1974d` at `2026-09-09T19:20:09.099Z` and deleted it at `2026-09-09T19:21:33.851Z`. An independent listing confirmed that no sandbox remained. The smoke command exited with status 2 and wrote only the generic error `Daytona smoke command failed`; its redirected JSON output file is empty.

Deleted-sandbox telemetry cannot recover the exact failed command, exit status, or output: the control endpoint reports telemetry disabled when the Analytics API is configured, while the Analytics endpoint reports that the deleted sandbox is not found. The second attempt therefore remains documented as an unknown remote command failure. The recovery must not rewrite it as a conclusively identified boundary.

The exact locally built proof image is `fotball-analyst-daytona-recovery:local`, image digest `sha256:c4f79f16fc565fcbef27a09367cf13b000037e4ecc74d3c533fc7ba385270ce5`. In a fresh container, importing `cv2` fails with `ImportError: libxcb.so.1: cannot open shared object file`. Dynamic-link inspection also reports `libGL.so.1`, `libgthread-2.0.so.0`, and `libglib-2.0.so.0` missing. The image is Ubuntu 22.04 Jammy amd64 and does not set `QT_QPA_PLATFORM`.

This is a confirmed worker-image defect and a high-confidence explanation for the remote failure because the worker imports the video-processing path that imports OpenCV. It is not proof of the exact remote command boundary.

## Worker image correction

The existing `opencv-python` dependency remains. `ultralytics` declares that distribution as a dependency, so replacing it globally with `opencv-python-headless` makes `pip check` fail. Installing both distributions creates overlapping `cv2` files and is already rejected by repository policy. The desktop/manual paths also retain their current OpenCV behavior.

The Daytona worker image will install only the missing Ubuntu runtime libraries and select Qt's offscreen platform:

```dockerfile
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      libgl1 libglib2.0-0 libxcb1 \
 && rm -rf /var/lib/apt/lists/*
ENV QT_QPA_PLATFORM=offscreen
```

On Ubuntu 22.04, `libglib2.0-0` supplies both the GLib and GThread shared libraries. `libgl1` and `libxcb1` supply the other missing runtime links. No new Python dependency, compatibility shim, display server, or alternate image is introduced.

The immutable PyTorch base digest, hash-locked worker requirements, `--require-hashes`, `--no-deps`, and `pip check` remain mandatory. The smoke runner's exact Dockerfile expectation changes with the Dockerfile so policy drift still fails before cloud execution.

Ubuntu packages are not pinned with the same artifact hashes as the Python lock. That accepted limitation is bounded by building the full image locally, recording the installed package versions in local proof output, and testing runtime imports and dynamic links before any cloud resource is requested. No image is pushed to a registry as part of this recovery.

## Failed-command diagnostics

The current smoke runner discards command output because its execution helper raises on a nonzero status before reading the response's stdout and stderr. The minimal correction stays in `backend/scripts/run_daytona_gpu_smoke.py` and its tests.

A private `SmokeCommandError` subtype will carry one sanitized `commandResult`. The shared execution helper will:

1. require an actual integer exit code;
2. accept stdout and stderr only when each is an actual string, avoiding arbitrary object stringification;
3. bound both strings to a small fixed maximum;
4. remove the exact host `DAYTONA_API_KEY` value as defense in depth;
5. apply the existing `redact_remote_diagnostics` credential-family redaction;
6. retain only a fixed command-stage label, exit code, stdout, and stderr; and
7. never retain the raw shell command.

The commands remain fixed by the runner and execute with an empty remote environment. No user-supplied command or environment is added.

`run_real_smoke` retains the command exception while its existing `finally` path deletes the exact owned sandbox and independently confirms absence. Only after cleanup is confirmed may `main()` emit a compact failure object to stdout, for example:

```json
{
  "commandResult": {
    "exitCode": 1,
    "stage": "worker-runtime-import",
    "stderr": "redacted and bounded",
    "stdout": "bounded"
  },
  "error": "Daytona smoke command failed",
  "mode": "real-smoke",
  "status": "failed"
}
```

Stderr remains generic. The existing private host redirection pattern, using a restrictive umask and a file outside the repository, captures this object as incident evidence. If cleanup or independent absence cannot be confirmed, the cleanup error overrides the command failure and diagnostic JSON is suppressed so uncertain lifecycle state cannot look like a contained attempt.

Arbitrary process output cannot be preserved verbatim while guaranteeing removal of every unknowable secret. The security boundary is therefore the fixed command set, empty remote environment, exact host-key removal, existing credential-pattern redaction, strict output bounds, and generic host stderr.

## Evidence boundary

Failed-command JSON is incident evidence, not release evidence. The existing `RemoteExecution` schema remains success-only and unchanged. The final evidence generator must reject the failure object and every nonzero `exitCode`.

No failure/success union schema, new evidence model, output-path option, background reconciler, or atomic file writer is added. The Markdown recovery record remains the durable chronological record for failed attempts.

## Local verification gates

Implementation begins test-first. A focused failing test will establish each changed behavior before its implementation is edited.

Worker-image tests must prove the checked-in Dockerfile and the smoke runner's `expected_dockerfile()` remain exactly aligned. The complete image must then build locally without Daytona credentials. In a fresh container, the proof will:

- run `python -m pip check`;
- assert `QT_QPA_PLATFORM=offscreen`;
- import `boto3`, `cv2`, `numpy`, `pandas`, `pydantic`, `torch`, and `ultralytics`;
- import `backend.app.processor` and `backend.app.proof_runtime`;
- execute a CPU-safe tensor operation; and
- run `ldd` against the imported OpenCV shared object and fail on any `not found` dependency.

The proof log may also record installed versions of `libgl1`, `libglib2.0-0`, and `libxcb1`. CUDA execution remains a remote-smoke responsibility; local verification does not pretend a CPU host proves GPU availability.

Runner tests must prove that a nonzero response produces only the bounded, redacted structured failure after confirmed cleanup, that non-string output is not coerced, and that cleanup failure suppresses the command diagnostic. Existing success and cleanup tests must continue to pass. A focused release-evidence test must prove that failure JSON cannot become final evidence.

After focused Daytona, release, evidence, preflight, verifier, and documentation tests pass, the complete `scripts/verify.sh` suite and dry-run smoke must pass without credentials or cloud access. If the full local image proof cannot pass, the third smoke remains blocked.

## Fresh release identity chain

The metadata-only second-attempt documentation commit does not by itself invalidate the current release identities. The tracked Dockerfile, runner, and test corrections will invalidate them, so recovery creates a fresh chain only after all source, tests, and documentation are final:

1. Remove the active manifest and pre-cloud evidence, then commit the corrected source and documentation as `S4`.
2. Regenerate only the release manifest and current-tree inventory from `S4`, then commit them as `M4`; `M4^` must equal `S4`.
3. Run the canonical credential-free verifier from clean `M4`, producing a fresh untracked receipt bound to `M4` and the new manifest digest.
4. Generate and commit fresh pre-cloud evidence as `E04`; `E04^` must equal `M4`, its source must be `S4`, its verification commit must be `M4`, `remoteExecution` must be null, and gate 13 must remain pending.
5. Run build-only preflight and obtain two independent zero-finding reviews.
6. Ask the user separately for explicit authorization for exactly one third Daytona sandbox while the verifier receipt remains fresh.

The first and second attempt records remain unchanged. Old commits and evidence remain in Git history; no history is rewritten.

## Authorized third-smoke behavior

If separately authorized, the third smoke performs exactly one sandbox creation and no internal create retry. It validates the fresh release binding and mutation gate before creation, proves GPU and runtime availability, executes the bounded fixture, downloads and validates its result and completion receipt, deletes the exact owned sandbox, and independently confirms account absence.

On success, the workflow generates success-only final evidence, appends attempt 3 to the recovery record without altering attempts 1 or 2, runs deployment preflight, and completes the final report and status page without creating another sandbox.

On failure, it preserves the bounded and redacted command result only after exact owned cleanup and independent absence, appends attempt 3 truthfully, and stops. No fourth attempt is implied or authorized.

The Daytona Python client/CLI version 0.207 warning against API 0.213 is noncausal for this incident: create and delete succeeded, while the runtime defect reproduces in the exact local image. An SDK compatibility upgrade is deferred to a separate task after gate 13 unless Daytona declares 0.207 unsupported or local contract tests fail.

## Acceptance criteria

The recovery is ready to request third-smoke authorization only when all of the following are true:

- the exact worker image builds locally and `pip check` succeeds;
- OpenCV and the actual worker runtime import in a fresh container with no unresolved shared libraries;
- command failure evidence is bounded, redacted, and emitted only after confirmed cleanup;
- failure JSON is rejected by the success-only final evidence path;
- focused suites, the complete verifier, dry-run, and build-only preflight pass;
- the `S4 -> M4 -> E04` chain is internally consistent and gate 13 remains pending;
- two independent reviews report no findings;
- Daytona lists zero sandboxes; and
- the worktree has no unexpected changes beyond the verifier's designated untracked artifacts.

The exposed Daytona API key must be rotated before any future production use.
