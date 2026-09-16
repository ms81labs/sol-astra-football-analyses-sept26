# User Testing

Testing-surface guidance for the isolated supported-coverage research lane.

**What belongs here:** validation surfaces, tooling, setup expectations, and concurrency guidance.

---

## Validation Surface

### Primary surface: shell / CLI

All mission validation is CLI-only. Validators should exercise these classes of behavior:

1. Registry visibility and refusal paths
2. Frozen corpus manifest reads and fingerprints
3. Wrapper help / dry-run / delegated target disclosure
4. End-to-end supported-coverage trial execution under isolated roots
5. Diagnosis replay on saved artifacts
6. Failure handling and append-only ledger behavior

### Required tools

- Shell commands
- `python3`
- `pytest`
- Filesystem inspection (`git status --porcelain`, path listings, file diffs)

### Explicitly out of scope for validation

- Browser automation
- Frontend/backend dev-server startup
- Playwright
- Runpod job submission
- Any new listening port

## Validation Setup

- Use an explicit temp root per validation run whenever execution writes state.
- Do not point validation at `backend/storage/**`.
- Prefer targeted pytest commands around proof/diagnosis scripts plus addon-owned tests.
- Capture pre/post listener snapshots when validating no-service-start invariants.
- Capture pre/post path snapshots when validating isolation invariants.

## Validation Concurrency

### Shell / CLI surface

- **Max concurrent validators:** `2`
- **Machine facts:** 4 CPU cores, ~15.24 GB RAM total, ~6.85 GB RAM available at planning time
- **Why 2:** proof-oriented Python paths import heavy dependencies (`torch`, `opencv`, benchmark/proof fixtures). Using the 70% headroom rule yields ~4.8 GB practical RAM budget. A conservative estimate of ~2.0 GB per concurrent validation worker keeps two validators within safe headroom while leaving room for the OS and existing user work. Three concurrent validators would be too likely to saturate CPU and memory on this machine.

If a future validator round shows materially lower per-run memory/CPU cost, the concurrency cap can be revisited in a later mission.
