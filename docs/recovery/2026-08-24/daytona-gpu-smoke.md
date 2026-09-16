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

## Attempt 2 — failed during remote execution

- Date: 2026-09-09 UTC
- Command: `VERIFY_DAYTONA=1 ALLOW_DAYTONA_MUTATION=1 DAYTONA_API_KEY=<redacted> /tmp/fotball-analyst-task11-venv/bin/python -m backend.scripts.run_daytona_gpu_smoke --real-smoke` redirected to `/tmp/fotball-analyst-daytona-corrective-smoke.json`
- Source commit (S3): `f0a28c649aa4de25f67880a414a94d7136e573ac`
- Verification commit (M3): `71397d1456514d353c93855429a66d725e17ec1d`
- Pre-cloud commit (E03): `660b7d5eb01a0c78d3116422427b1877dd22f914`
- Manifest SHA-256: `4578b5a332428ced4d449286805189551107c28270f3f31cfd7d209a488e1141`
- Local result: the process exited 2 with `Daytona smoke command failed`. The redirected output exists with mode `0600` but is zero bytes, so no final JSON evidence or report exists.
- Daytona audit: sandbox `bff48578-0084-47ab-803d-1075b1a1974d` was created successfully at `2026-09-09T19:20:09.099Z` and deleted successfully at `2026-09-09T19:21:33.851Z` through the Python SDK; both requests returned HTTP 200. An independent CLI listing at `2026-09-09T19:35:11Z` returned zero sandboxes.
- Missing telemetry: the deleted sandbox control endpoint returned HTTP 403 because analytics is configured, while the analytics endpoint returned HTTP 404 because the sandbox was not found. The exact remote command boundary and stderr are therefore unrecoverable.
- Local reproduction: in the exact proof image `c4f79f16fc565fcbef27a09367cf13b000037e4ecc74d3c533fc7ba385270ce5`, the mandatory import command cannot pass because importing `cv2` raises `ImportError: libxcb.so.1: cannot open shared object file`. `ldd` also reports `libGL.so.1`, `libgthread-2.0.so.0`, and `libglib-2.0.so.0` missing. This confirms a worker-image runtime defect but does not prove which remote command failed.
- Release status: gate 13 remains incomplete; no final JSON evidence or report exists, and no third sandbox is authorized.
- External mutations: no RunPod or registry mutation was invoked by this attempt; the runner contains no such action. No success report exists.

This failed attempt is recovery history only. It must not be represented as a successful `remoteExecution` object.

## Attempt 3 — failed before sandbox allocation

- Date: 2026-09-10 UTC
- Command: `VERIFY_DAYTONA=1 ALLOW_DAYTONA_MUTATION=1 DAYTONA_API_KEY=<redacted> python3 -m backend.scripts.run_daytona_gpu_smoke --real-smoke` redirected to `/tmp/fotball-analyst-daytona-third-smoke.json`
- Source commit (S4): `4112517a96630b46dcb501806849ad6c928cac47`
- Verification commit (M4): `c3d7329b55a49fcf59c35490e4846b43ba763f7e`
- Pre-cloud commit (E04): `e03f99d0522c3be926d20bb09ada4e57edd1e4da`
- Manifest SHA-256: `0493a97703d9b55df0007325e3dfcc0435ed28a5afedbf4bdc0ba9877f7d806f`
- Preflight: the credential profile was available without disclosure, Daytona listed zero sandboxes, the release worktree and S4/M4/E04 ancestry were unchanged, the dry-run passed, and build-only preflight accepted the exact manifest and pre-cloud evidence.
- Local result: `/usr/bin/python3` exited 2 before client construction with the fixed stderr `Daytona client construction failed`. The redirected result exists with mode `0600` and is zero bytes, so no failure or success JSON report exists.
- Root cause: the authorized host interpreter cannot import the pinned `daytona==0.207.0` SDK. A non-mutating direct factory reproduction with a dummy key raises `ModuleNotFoundError: No module named 'daytona'`.
- Allocation and cleanup: failure occurred while importing the SDK, before a Daytona client or sandbox existed. No image build, upload, smoke command, or football workload ran. The pre-attempt and independent post-attempt CLI listings both returned zero sandboxes, so there is no sandbox identifier or lifecycle timestamp to record and no cleanup action was required.
- Release status: gate 13 remains incomplete; success-only final evidence and the final verification report were not generated. The single authorized third attempt was consumed, and no fourth attempt is authorized.
- External mutations: no RunPod or registry mutation occurred.

This failed attempt is recovery history only. It must not be represented as a successful `remoteExecution` object.

## Attempt 4 — passed

- Date: 2026-09-10 UTC
- Command: `VERIFY_DAYTONA=1 ALLOW_DAYTONA_MUTATION=1 DAYTONA_API_KEY=<redacted> /root/.cache/fotball-analyst/daytona-smoke-0.207.0/bin/python -m backend.scripts.run_daytona_gpu_smoke --real-smoke` redirected to `/tmp/fotball-analyst-daytona-fourth-smoke.json`
- Result serialization: the original 1,956-byte CLI output used escaped Unicode and passed semantic `RemoteExecution` validation. It was normalized in place to the strict writer's 1,947-byte canonical UTF-8 form before final-evidence generation. The exact runner serialization was reconstructed and preserved at mode `0600` as `/tmp/fotball-analyst-daytona-fourth-smoke.raw.json`; raw SHA-256 `e1742ddcd4567745a78ccef632b4e54fb1b0e30cdaaba5fd069230adef8951eb`, canonical SHA-256 `41aa87816aa12200a621ed3a28218befefcdb36b9358c81bbb3e8036f9e70a43`.
- Source commit (S6): `43c9c2e3e9d9260f6b7abb35fc979517b6e81e50`
- Verification commit (M6): `42f242b4c252ee40316c222d9967b35f67aab2a4`
- Pre-cloud commit (E06): `d5a5d8ab828c84ac936cba26560c3554946cb9da`
- Manifest SHA-256: `62cd12f4db317507b55c45a805351ca610031d6817f2210bb84adc966603b192`
- Worker-context SHA-256: `3dace1c8ef524894fc238eb26e4b000a0c0e300195149683195f19ffc2400e84`
- Image: `docker.io/pytorch/pytorch@sha256:417bd75df6365104c283ea4c1651fb3530d9eb5a4c2fafa51943cff2a94e6385`
- SDK: `0.207.0`
- Target: `us`
- Requested GPUs: `["RTX-PRO-6000","H100"]`
- Observed GPU: `RTX-PRO-6000`
- Sandbox: `a072ad85-ce9a-405f-90de-925613fb7cb1`
- Lifecycle timestamps: created `2026-09-10T10:16:12.626434Z`; started `2026-09-10T10:17:12.820619Z`; completed `2026-09-10T10:17:27.672128Z`; deleted `2026-09-10T10:17:28.413878Z`.
- Command result 1: `{"command":"nvidia-smi","exitCode":0,"stderr":"","stdout":"NVIDIA RTX PRO 6000 Blackwell Server Edition\n"}`
- Command result 2: `{"command":"worker-import","exitCode":0,"stderr":"","stdout":"WARNING ⚠️ user config directory '/root/.config/Ultralytics' is not writable, using '/tmp/Ultralytics'. Set YOLO_CONFIG_DIR to override.\nCreating new Ultralytics Settings v0.0.6 file ✅ \nView Ultralytics Settings with 'yolo settings' or at '/tmp/Ultralytics/settings.json'\nUpdate Settings with 'yolo settings key=value', i.e. 'yolo settings runs_dir=path/to/dir'. For help see https://docs.ultralytics.com/quickstart/#ultralytics-settings.\n"}`
- Command result 3: `{"command":"bounded-fixture","exitCode":0,"stderr":"","stdout":""}`
- Upload: `{"name":"job-request.json","sha256":"6011853fdcfcab2a37c68e355797d2cc4ea2c69b079e42d70c8c1685f7bf4700","sizeBytes":134}`
- Downloads: `{"name":"result.json","sha256":"86b6fc76f6ae67c7f6f952bfd6d522479a42a1f0d2b7c78b3981f9df4b5d7aa1","sizeBytes":64}`; `{"name":"completion.json","sha256":"79734cb58984543095a3cbc6f5daec3c1be17867d93a32e07a2ca5d60fc952c7","sizeBytes":196}`
- Cleanup: 1 attempt; deletion confirmed `true`; an independent post-attempt listing returned zero sandboxes.
- External mutations: RunPod `false`; registry `false`.
- Release status: all 13 gates passed and success-only final verification evidence was generated.
