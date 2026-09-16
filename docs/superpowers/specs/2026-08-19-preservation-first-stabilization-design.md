# Preservation-First Project Stabilization Design

**Date:** 2026-08-19

**Status:** Approved design

## Purpose

Recover the current v7.3 football-analysis milestone after a three-month pause, preserve all unique work, and make the project reproducible from a clean checkout before any new training, data acquisition, deployment, or broad architectural refactoring.

The recovery is successful only when the preserved source state, release identity, required artifacts, startup path, verification commands, and deployment preflight no longer depend on undocumented state in the current workstation.

## Current Baseline

The 2026-08-19 audit established this baseline:

- Branch: `recovery-history-batch-current`
- Starting commit: `bc4f4e30`
- Working tree: 30 modified, 14 deleted, and 443 untracked paths
- Tracked diff: 15,628 insertions and 19,668 deletions across 44 paths
- Backend verification: 1,486 tests passed
- Frontend verification: 46 tests passed; lint, typecheck, and production build passed
- Research sidecar: 35 of 37 tests pass from the normal root environment; all 37 pass only when `research-addon` is manually added to `PYTHONPATH`
- Repository footprint: approximately 17 GB
- Backend storage: approximately 9.4 GB
- Git packs: approximately 4.79 GB, dominated by a historically committed Python virtual environment and GPU libraries
- Worktrees: five total; three report roughly 32,974 tracked deletions and one contains 32 meaningful dirty entries
- Locally cached branch relationship: 67 commits ahead and 2 behind `origin/main`; remote freshness is unverified

The current application is functionally healthy, but the repository is not reproducible or safe to deploy. The working runtime registry declares v7.3 while the committed head predates that state. The RunPod image build uses dirty working-tree content while labeling the image with the committed head. The v7.3 model contract also contains an absolute workstation path that is unavailable inside the image.

## Scope

### Included

1. Inventory and classify every dirty path and paused-worktree change.
2. Preserve unique source, tests, documentation, release metadata, and essential small truth artifacts in coherent commits.
3. Define a portable v7.3 release manifest with model identity and checksums.
4. Repair backend and research-sidecar packaging and documented startup.
5. Make local and RunPod runtime options share one serializable contract.
6. Add deployment preflight that fails on dirty source, mismatched provenance, missing artifacts, invalid checksums, absolute workstation paths, or mutable tags.
7. Add one local/CI verification entrypoint for backend, sidecar, frontend, startup, release-manifest, and container checks.
8. Address critical and high production dependency findings through compatible, staged changes.
9. Replace append-only current-state documentation with one concise authoritative status and runbook.
10. Produce a final clean-checkout verification and recovery report.

### Excluded

- Rewriting Git history
- Deleting multi-gigabyte datasets, videos, model weights, or unresolved generated evidence
- Model training or new data acquisition
- Broad decomposition of the CV engine, FastAPI application, or frontend
- Pushing branches or opening a pull request
- Updating a live RunPod template or endpoint
- Any other external deployment mutation

The excluded work may be proposed separately after stabilization.

## Recovery Architecture

The recovery proceeds through six ordered stages.

### Stage 1: Freeze and Inventory

Record the exact current state before changing it:

- Git head, branch, status, tracked diff, ignored files, and tracked-but-ignored files
- Local branch and worktree heads and status counts
- Meaningful tracked patches and untracked-file archives for paused worktrees
- File size and SHA-256 for large artifacts and model weights
- Reference relationships between product source, tests, workflow scripts, generated truth, and docs
- A proposed disposition and commit group for every dirty path

Inventory is read-only by default. Ambiguous paths receive `manual_review`; they are never inferred to be disposable.

### Stage 2: Preserve the v7.3 Source State

Convert the current working state into small, dependency-safe commits. Source and its required tests must be staged together. Files imported or referenced by a commit must already be tracked in the same or an earlier commit.

The intended commit sequence is:

1. Recovery inventory, artifact policy, and repository guardrails
2. Product and API changes, including `main.py` with `match_bundle.py`
3. Local and RunPod runtime-contract changes
4. Reusable workflow foundations and shared helpers
5. Workflow source and tests grouped by coherent functional lane
6. Portable v7.3 release manifest and essential truth fixtures
7. Packaging, startup, dependency, and CI repairs
8. Authoritative status documentation and archived chronology

The 14 tracked deletions must be reviewed individually. A deletion is accepted only when its replacement or retirement evidence is recorded.

### Stage 3: Establish a Clean Stabilization Worktree

Create a new stabilization worktree only after the source state is preserved. All subsequent fixes and verification run there so hidden files in the original recovery worktree cannot satisfy dependencies accidentally.

The clean worktree must install and run using repository instructions and declared artifacts only. The original recovery worktree remains available as evidence until final verification completes.

### Stage 4: Repair Release and Deployment Reproducibility

Introduce a tracked v7.3 release manifest as the durable release contract. It contains:

- Manifest schema version
- Product release version
- Detector candidate and runtime version
- Source commit
- Runtime-options payload
- Model artifact identifier
- Model SHA-256 and expected size
- Expected resolved local and container paths
- Required product/report contracts
- Provenance timestamps

Absolute workstation paths are invalid in the portable manifest. Local and remote artifact resolvers map the identifier to an environment-specific path and verify the checksum before model loading.

The deploy preflight and tests use the same validator. Preflight rejects:

- A dirty working tree
- A source commit that differs from the manifest
- An absolute workstation path in portable release data
- A missing or checksum-mismatched model artifact
- An unverified required contract
- A mutable image tag
- An image label that differs from the committed source

Building an image is allowed during verification. Pushing it or mutating RunPod infrastructure is not part of this recovery.

### Stage 5: Harden Packaging, Verification, and Documentation

The backend and research sidecar become installable and importable from the repository root without manual path injection. The documented backend startup command must work from a clean checkout.

A single verification entrypoint is shared by developers and CI. It runs:

- Backend tests
- Research-sidecar tests
- Frontend tests
- Frontend lint and typecheck
- Frontend production build
- Backend import and startup smoke
- Release-manifest validation
- Runtime-options local/remote round-trip tests
- Deployment negative-path tests
- Docker build and handler-startup smoke when the required local artifact is available

One concise current-state document replaces multiple competing current sections. Historical handoff entries move to dated archives without discarding chronology.

### Stage 6: Clean-Checkout Acceptance

Run the complete verification process in the stabilization worktree. Compare the result with the original baseline and publish a final report describing preserved commits, artifact dispositions, worktree salvage, dependency status, deployment readiness, deferred work, and before/after repository state.

## Classification and Preservation Policy

Every dirty path receives one of these classifications:

| Classification | Disposition |
| --- | --- |
| Product source | Commit with required tests |
| Reusable workflow | Commit by functional lane |
| One-shot batch entrypoint | Commit only if needed for reproduction; otherwise archive with provenance |
| Essential release truth | Commit as a small portable fixture or release contract |
| Regenerable truth | Keep outside Git after generator and restore procedure are verified |
| Large local artifact | Keep outside Git and record identifier, checksum, size, origin, and retention class |
| Editor or cache material | Ignore only after unique-work checks |
| Ambiguous | Retain and require manual review |
| Tracked deletion | Accept only with explicit replacement or retirement evidence |

`backend/storage` will no longer have an implicit split personality. Small durable fixtures and release contracts move to an explicitly tracked location. Runtime state, generated reports, datasets, virtual environments, and model binaries remain ignored and are represented by manifests where needed.

## Paused Worktree Salvage

Before any worktree or branch cleanup:

1. Record the worktree path, branch, head, and status counts.
2. Capture a binary-capable patch of meaningful tracked changes.
3. Archive untracked files with a checksum manifest.
4. Compare meaningful paths with the preserved v7.3 tree.
5. Classify each path as integrated, superseded with evidence, or unique and unresolved.
6. Keep unresolved content outside the active stabilization branch.

Pruning is included only for worktrees whose inventory proves that all meaningful content is preserved, integrated, or superseded with evidence. The implementation step must name each exact worktree path before removal and verify its salvage archive immediately beforehand. Branch deletion and any worktree containing unresolved unique material remain excluded without separate approval.

The historical virtual-environment objects remain reachable and are not rewritten. The final report may document a future coordinated history rewrite.

## Components and Responsibilities

### Recovery Inventory

Produces deterministic JSON and Markdown reports. It knows Git/worktree state and file classifications but does not stage, commit, delete, or move files.

### Release Manifest Validator

Parses and validates the portable release contract. It rejects unknown schema versions, absolute portable paths, missing required fields, invalid hashes, source-commit mismatches, and unresolved required artifacts.

### Artifact Resolver

Maps a portable artifact identifier to a local or container path. It verifies file size and SHA-256 before returning the path. It never treats an unchecked path as a valid model.

### Runtime Options Contract

Represents all supported model, acquisition, repair, rescue, proposal-seed, and reviewed-positive-seed options. The same serialized structure passes through local processing, RunPod request construction, handler execution, and provenance output.

### Deployment Preflight

Checks source cleanliness, commit identity, release manifest, artifact resolution, image tag, verification evidence, and container inputs. It performs no push or remote mutation.

### Verification Entrypoint

Runs the canonical local and CI checks in a fixed order and returns a nonzero status at the first failed required gate. It prints the failing command and corrective action.

### Current-State Runbook

Documents one release, one startup procedure, one verification command, one artifact restore procedure, current deployment readiness, and one next-action section.

## Error Handling

- Inventory uncertainty is retained as `manual_review`.
- Missing optional reports produce an explicit not-found result.
- Malformed required release data stops startup or preflight.
- Missing and corrupt artifacts report the identifier, expected hash, and resolved path.
- Deployment preflight fails closed and performs no external mutation.
- Verification failures preserve logs and name the exact failed gate.
- Cleanup operations require an inventory-approved exact path; broad recursive targets and unresolved globs are invalid.
- No error path may automatically delete or replace the original recovery data.

## Verification and Acceptance Criteria

### Preservation Gate

- All 487 original dirty paths have an inventory disposition.
- Every paused worktree has a verified salvage archive and comparison result.
- No unique work or material artifact has been deleted.
- Large artifacts have checksummed manifests.

### Commit Gate

- Each commit represents one coherent concern.
- Required source and tests are staged together.
- Focused tests pass before the next group.
- No import or required reference points to an unstaged path.
- Large or generated files do not enter Git accidentally.

### Clean-Checkout Gate

- Backend and sidecar install from declared manifests.
- The documented FastAPI import and startup smoke pass.
- At least the audited baseline of 1,486 backend tests, 37 sidecar tests, and 46 frontend tests pass.
- Frontend lint, typecheck, and production build pass.
- Release-manifest validation succeeds without the original absolute workspace path.
- Required artifacts can be restored using only documented identifiers and instructions.

### Release and Deployment Gate

- Portable release data contains no absolute workstation paths.
- Model identity, size, and SHA-256 match the resolved artifact.
- Local and RunPod runtime-option round-trip coverage includes every supported option.
- Image provenance matches committed source.
- Dirty-tree, missing-artifact, checksum-mismatch, source-mismatch, and mutable-tag tests fail safely.
- Docker build and handler smoke pass when local artifact prerequisites are present.
- No live RunPod mutation occurs.

### Quality Gate

- CI uses the canonical verification entrypoint.
- The production dependency audit reports no known critical or high findings.
- Python environment consistency passes in a clean environment.
- Startup, verification, restore, and deployment-preflight commands are executable as documented.
- The authoritative status document has one current release and one next-action section.

## Completion Report

The final report records:

- Preservation commits and remaining intentional local artifacts
- Disposition of all original dirty paths
- Worktree and branch salvage results
- Full test, lint, typecheck, build, import, and container evidence
- Dependency and vulnerability status
- Release-manifest and model-artifact verification
- Deployment readiness and external prerequisites
- Deferred architectural and Git-history work
- Before/after Git status and storage footprint

Passing tests alone is insufficient. Completion requires clean-checkout reproducibility and an explicit disposition for all original work.
