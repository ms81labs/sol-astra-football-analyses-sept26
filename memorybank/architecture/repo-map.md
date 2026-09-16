# Repo Map

## Main Product Tree

### `backend/`

- `app/`: FastAPI app, storage, schemas, processors, helpers
- `scripts/`: batch entrypoints, proof runners, benchmark drivers, remote helpers
- `tests/`: backend verification
- `benchmark_suites/`: saved manifest inputs for suite tooling
- `runpod_handler/`: remote worker packaging support

### `frontend/`

- `src/`: React application and review surfaces
- `package.json`: frontend scripts and dependencies

### `docs/`

- live operating docs
- specs and plans
- archive references

### `archive/`

- retired cleanup-era material
- reference-only, not active product direction

### `research-addon/`

- isolated research sidecar
- useful for bounded experiments, not the default product path

## Important Generated-State Roots

### `backend/storage/matches/`

Per-match artifacts such as:

- `proof_summary.json`
- `ball_truth_layers.json`
- `ball_pipeline_trace.json`
- `selected_cluster_delta.json`

### `backend/storage/pod_cycles/`

Per-run remote proof bundles and lifecycle/debug outputs.

### `backend/storage/benchmark_suites/`

Suite-level truth surfaces, diagnosis files, and lane snapshots.

## Context Shortcut

If you are returning cold:

1. read `memorybank/activeContext.md`
2. inspect the latest benchmark-suite snapshot
3. inspect the latest relevant pod cycle if the task is remote-proof related
