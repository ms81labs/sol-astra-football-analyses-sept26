# Dependency profiles

Install the smallest profile needed by the host:

```bash
# API only: no Torch or Ultralytics
python -m pip install --require-hashes -r backend/requirements/api.lock
python -m pip install -e . --no-deps

# Developer/test environment
python -m pip install --require-hashes -r backend/requirements/dev.lock
python -m pip install -e . --no-deps

# Apple Silicon macOS local CPU vision
python -m pip install --require-hashes -r backend/requirements/cpu-cv-macos.lock
python -m pip install -e '.[cv]' --no-deps

# Linux GPU worker
python -m pip install --require-hashes -r backend/requirements/cuda-linux.lock
python -m pip install -e '.[cv,cuda]' --no-deps
```

The source profiles are `backend/requirements/{api,cpu-cv,cuda,dev}.in`. Use CPython 3.11 and regenerate each lock on its named platform with pip-tools:

```bash
python -m piptools compile --generate-hashes --allow-unsafe --strip-extras \
  --output-file backend/requirements/api.lock backend/requirements/api.in
```

Repeat for `dev.lock`, on macOS for `cpu-cv-macos.lock`, and on Linux for `cuda-linux.lock`. Review the diff and run `python -m pip install --dry-run --require-hashes -r LOCK` before publishing it. CUDA and Triton dependencies must remain Linux-marked and confined to `cuda.in`.

When regenerating the Apple Silicon lock away from a Mac, use the equivalent cross-platform resolver command recorded in the lock header; the macOS CI lane remains the installation authority.

The legacy `backend/requirements-*.txt` files include these locks for one compatibility release; new automation must use the profile locks directly.

## Decoder isolation boundary

Local FFmpeg children use protocol allowlists, bounded threads, a scratch working directory, POSIX CPU/memory/file limits, wall-clock deadlines, output caps, exit-status checks, and cancellation polling. These controls do not provide network-namespace isolation: untrusted-media deployments still require an OS container or network namespace with networking disabled.
