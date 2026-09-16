# Daytona GPU execution

Daytona supplies disposable GPU compute only. The host seals and uploads a job bundle, the provider-neutral worker runs inside one private ephemeral sandbox, and the host verifies and imports the returned bundle. The sandbox must be deleted and deletion confirmed even when execution fails.

Set `DAYTONA_PYTHON` to the interpreter with the pinned Daytona SDK and use it for the readiness check and dry-run:

```bash
export DAYTONA_PYTHON="${DAYTONA_PYTHON:-python3}"
```

Confirm the pinned SDK is installed with this credential-free command:

```bash
"$DAYTONA_PYTHON" -c 'import daytona, importlib.metadata as metadata, sys; version=metadata.version("daytona"); sys.exit(f"expected daytona==0.207.0, got {version}") if version != "0.207.0" else None'
```

Dry validation is credential-free and creates nothing:

```bash
"$DAYTONA_PYTHON" -m backend.scripts.run_daytona_gpu_smoke --dry-run
```

Normal non-cloud verification also creates nothing:

```bash
VERIFY_DAYTONA=0 ALLOW_DAYTONA_MUTATION=0 scripts/verify.sh
```

Release evidence is intentionally valid for at most 24 hours. Monitor the checked-in
pre-cloud evidence with a four-hour renewal window; this command is read-only and
creates no provider resources:

```bash
python3 -m backend.release.preflight check-freshness \
  --evidence backend/release/verification/v7.3-pre-cloud.json \
  --mode build-only \
  --minimum-validity-seconds 14400
```

Run that check on the operator schedule and alert on its nonzero exit. If it enters the
renewal window, settle and commit the intended source, bind and commit a fresh manifest,
run the complete provider-disabled verifier above from a clean tracked tree, publish its
receipt-backed pre-cloud evidence to a new exclusive path, review/copy that exact file to
`backend/release/verification/v7.3-pre-cloud.json`, commit it, and rerun the exact
build-only preflight. Never renew evidence by editing timestamps, copying an old receipt,
reducing the maximum age, or starting a provider job. The application remains fail-closed
after expiry.

The historical infrastructure smoke is retired and must not be repeated. `scripts/verify.sh`
rejects its old mutation flags. The next provider operation is G-PRODUCT from the
approved remediation plan: rotate the exposed testing credential, build fresh
source-bound release evidence, obtain explicit authorization, then run one real football
clip through API upload, the sealed worker, validated import, coaching views, and
confirmed sandbox deletion. No general smoke command is an approved substitute.

The API credential stays on the host and must appear in evidence only as `DAYTONA_API_KEY=<redacted>`. Do not add network ingress or expose a public endpoint. A product acceptance succeeds only when its result identities validate and `deletionConfirmed` is true.
