# Release artifact restore

Release artifacts are outside Git. Restore only the exact object recorded by `artifactId`, `sha256`, `sizeBytes`, and `localRelativePath` in `backend/release/v7.3.json`. Fetch the recorded object into a private staging directory, then verify it before installation:

```bash
umask 077
mkdir -p .artifact-restore
ARTIFACT_SOURCE=.artifact-restore/downloaded-object
ARTIFACT_DEST=artifacts/model.pt
EXPECTED_SHA256=replace-with-manifest-sha256
EXPECTED_SIZE=replace-with-manifest-sizeBytes
test "$(wc -c < "$ARTIFACT_SOURCE")" -eq "$EXPECTED_SIZE"
printf '%s  %s\n' "$EXPECTED_SHA256" "$ARTIFACT_SOURCE" | sha256sum -c -
install -D -m 0600 "$ARTIFACT_SOURCE" "$ARTIFACT_DEST"
```

Use the manifest's actual destination rather than assuming `artifacts/model.pt`. After all objects are restored, run the provider-neutral release preflight documented by `python3 -m backend.release.preflight validate --help`. Never substitute a same-named local file whose identity was not recorded.
