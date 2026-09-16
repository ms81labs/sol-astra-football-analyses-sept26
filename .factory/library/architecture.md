# Architecture

High-level architecture for the isolated autoresearch addon lane.

**What belongs here:** major components, relationships, data flow, invariants, and safety boundaries.
**What does NOT belong here:** per-feature task lists, validator results, or low-level implementation trivia.

---

## System Shape

The mission adds a **parallel research lane** rooted at `research-addon/`. It is an orchestration layer around existing proof and diagnosis surfaces, not a rewrite of the football-analyst product.

Repo path names and Python import names may differ: the filesystem root is `research-addon/`, while the importable package may be `research_addon`. Workers must document that mapping explicitly in the addon CLI/package structure so operators know which entrypoint to invoke.

The addon should be structured around five cooperating areas:

1. **Track registry**
   - Declares executable vs planned tracks.
   - Only `supported-coverage` is executable in this mission.
   - Deferred tracks (`possession/events`, `trust-crops`, `gpu-bounded-loops`, `later-training`) remain inert metadata.

2. **Frozen corpus manifest**
   - Explicit list of supported-coverage proof inputs.
   - Stable ordering/fingerprint so repeated reads produce the same corpus membership without live scanning.
   - This is the only executable corpus input surface for the addon.

3. **Judge wrapper layer**
   - Wraps existing read-only repo surfaces:
     - `backend/scripts/run_local_app_path_proof.py`
     - `backend/scripts/compare_local_remote_proof.py`
     - `backend/scripts/compare_ball_pipeline_trace.py`
   - Exposes addon-owned commands with a stable judge contract while surfacing the delegated target and propagating exit status.
   - May support help/dry-run mode without starting app services.
   - Real execution consumes one explicit manifest entry plus a physically
     validated repository and Python interpreter. A source checkout may supply
     repository/interpreter defaults only from the exact
     `research-addon/research_addon` layout with the sibling proof script;
     installed wheels require both paths explicitly.

4. **Trial ledger and backlog**
   - Append-only history of each run attempt.
   - Stores run metadata: track, corpus fingerprint, judge target, decision (`kept`, `discarded`, `failed`), and artifact pointers.
   - Separate append-only backlog for future ideas so deferred work does not mutate past trial outcomes.

5. **Safety and path-guard layer**
   - Resolves every output/state/artifact path into addon-owned or temp roots.
   - Rejects or constrains unsafe overrides before execution.
   - Prevents addon-level truth-gate relaxation, service startup, and remote-job submission by default.

## Data Flow

1. Operator selects a track via the addon CLI.
2. Registry verifies the track is executable.
3. Addon loads the frozen corpus manifest and computes a stable corpus fingerprint.
4. Path guard resolves an isolated run root.
5. Judge wrapper delegates to an existing proof or diagnosis script.
6. Addon captures compact metrics and decision metadata.
7. Trial ledger appends the terminal result.
8. Optional ideas/backlog entry is appended without mutating prior results.

## Stable Contracts

### Supported-Coverage Judge Contract

The supported-coverage lane must preserve these sprint-relevant result fields end-to-end:

- `acceptedBallFrames`
- `supportedAcceptedBallRatio`
- `controlledPossessionFrames`
- `eventFamilyCount`
- `truthGateReasons`

The addon may reformat these into a compact summary, but it must not invent alternate semantics for them.

`research-addon judge supported-coverage` requires `--manifest` for execution
and accepts `--repo-root`, `--python`, and an optional zero-based
`--entry-index`. Relative manifest video paths resolve only against the
validated repository. The selected interpreter runs the repository's regular
`backend/scripts/run_local_app_path_proof.py` with that repository as its
working directory; output storage remains independently confined by the path
guard. `tracks list` reports `available-with-config` until this context
validates and `executable-now` afterward. Help and dry-run remain non-mutating.

### Diagnosis Replay Contract

Diagnosis replay is based on **saved artifacts**, not fresh remote execution. The addon should be able to replay the same frozen inputs twice and report the same key diagnosis fields (for example `firstDivergingStage` or saved-proof diagnosis classification).

## Non-Negotiable Invariants

- Core product code remains read-only.
- No addon command may widen the corpus by scanning live storage.
- No addon command may weaken or bypass the existing truth-gate behavior.
- No planned track may become executable through backlog updates or ad hoc flags.
- No default execution may start dev servers, browser tooling, or remote jobs.
- Trial history is append-only, including failure cases.

## Validation Boundaries

- Validation surface is CLI/shell only.
- Representative proof/diagnosis behavior is exercised via backend script wrappers and targeted pytest coverage.
- Evidence is gathered through command output, filesystem audits, and process/listener snapshots rather than browser flows.
