# Environment

Environment variables, external dependencies, and setup notes for the isolated research lane.

**What belongs here:** required env vars, external dependency expectations, local setup notes, and mission-specific environment constraints.
**What does NOT belong here:** service ports/commands (use `.factory/services.yaml`).

---

## Current Mission Assumptions

- Python `3.12.x` is available locally.
- Backend Python dependencies are installed from `backend/requirements.txt`.
- Frontend tooling exists in the repo but is out of scope for this mission.
- The research lane is harness-only and must not require browser tooling, dev servers, or remote GPU infrastructure.
- In this headless environment, proof/diagnosis commands that import `backend/run_guerilla.py` must run with `QT_QPA_PLATFORM=offscreen`.

## External Dependencies

- No new credentials are required for this mission.
- No Runpod submission, remote endpoint creation, or live backend/frontend startup is allowed by default.
- Existing proof and diagnosis scripts under `backend/scripts/` are read-only dependencies and must be wrapped, not modified.

## Path and Storage Constraints

- Default execution must resolve state and artifacts into `research-addon/**`, `.factory/**`, or an explicit temp root.
- `backend/storage/**` is read-only for this mission.
- Core product code under `backend/**` and `frontend/**` is read-only unless the user explicitly widens scope in a later mission.

## Known Repo Surfaces Used By The Addon

- Proof wrapper target: `backend/scripts/run_local_app_path_proof.py`
- Saved-proof comparison target: `backend/scripts/compare_local_remote_proof.py`
- Trace diagnosis target: `backend/scripts/compare_ball_pipeline_trace.py`
- Proof-oriented test fixtures live under `backend/tests/`
