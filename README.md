# Guerilla Analytics

A football match-analysis application: upload a match, store and prepare it locally, run computer-vision work locally or in a private ephemeral Daytona GPU sandbox, then validate, persist, and present the analysis in the application.

## Start locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r backend/requirements/dev.lock
python -m pip install -e . --no-deps
export GUERILLA_STORAGE_ROOT="${HOME}/.local/share/guerilla-analytics"
python -m uvicorn backend.app.main:app --reload --port 8000

cd frontend
npm install
npm run dev
```

Local processing is the default. For remote GPU processing, set `PROCESSING_BACKEND=daytona` and provide the host-only Daytona credential. Never print it; documentation and evidence use `DAYTONA_API_KEY=<redacted>`.

The API is a trusted local tool: keep the server bound to loopback. Requests must use a `localhost` or `127.0.0.1` Host. The installed Starlette Host middleware rejects IPv6 backend Hosts, so access the backend through IPv4 or localhost; an IPv6 frontend at `http://[::1]:5173` can still call that backend.

Unsafe HTTP methods and websocket handshakes with an `Origin` must match the backend's scheme, host and effective port, or a configured frontend origin. Defaults are exactly `http://localhost:5173`, `http://127.0.0.1:5173`, and `http://[::1]:5173`. Override them with a comma-separated `TRUSTED_FRONTEND_ORIGINS` value. Entries are trimmed, canonicalized and deduplicated; only HTTP(S) origins without userinfo, paths (including a trailing `/`), queries or fragments are accepted. Empty entries, wildcard and `null` origins are rejected. CORS permits credentials with explicit origins and the frontend's GET/POST/PUT/PATCH/DELETE methods and Content-Type header.

Origin-less CLI clients remain usable. Origin/Host checks and CORS are browser boundaries, not authentication: arbitrary non-browser clients can supply their own headers. **G-NETWORK remains required for any non-local deployment**; this configuration does not authorize public or LAN exposure.

Install the optional local computer-vision dependencies only on machines that execute local video jobs. Use the CUDA profile only on Linux GPU workers:

```bash
python -m pip install --require-hashes -r backend/requirements/cpu-cv-macos.lock  # Apple Silicon macOS CPU
python -m pip install -e '.[cv]' --no-deps
python -m pip install --require-hashes -r backend/requirements/cuda-linux.lock  # Linux GPU
python -m pip install -e '.[cv,cuda]' --no-deps
```

The legacy `backend/requirements-*.txt` files are compatibility includes for one release. See `docs/runbooks/dependency-profiles.md` for lock regeneration and API-only installation.

## Verify

```bash
VERIFY_DAYTONA=0 ALLOW_DAYTONA_MUTATION=0 scripts/verify.sh
python3 -m backend.scripts.run_daytona_gpu_smoke --dry-run
```

The historical infrastructure smoke is retired and must not be repeated. An earlier
source-bound one-minute G-PRODUCT run and representative two-half G-CAPACITY run passed;
neither proves football accuracy or acceptance of subsequent code changes. See
`docs/status/current.md` for the exact source and remaining gates before any new
provider operation.

See `docs/runbooks/daytona-gpu-execution.md`, `docs/runbooks/artifact-restore.md`, and `docs/status/current.md`. Historical material lives under `docs/archive/` and is not an active runbook.

RunPod was retired from active execution. No RunPod image was pushed or deployed during this migration. No Git history was rewritten. No model or application data was deleted.

## Research commands and runtime packaging

`backend/scripts/` remains available from a source or editable checkout for existing
research commands, but is excluded from the runtime wheel. Shared label validation
and tracking-evaluation functions live in `backend.app.pilot_labels` and
`backend.app.pilot_tracking`; the original command modules retain compatibility exports.
