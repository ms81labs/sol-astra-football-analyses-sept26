# Release and Runtime Reproducibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Make v7.3 release identity, artifacts, runtime options, verification evidence, and container provenance portable and fail-closed.

**Architecture:** Product/runtime source is frozen in commit `S`; later commits may add only enumerated release metadata. The manifest declares `S`, preflight validates metadata-only ancestry, and the image is built from `git archive S` with the validated manifest/evidence/artifacts injected. Runtime path inputs become portable artifact references materialized by the local or container resolver.

**Tech Stack:** Python 3.11, dataclasses, pytest, Bash, Docker, JSON, SHA-256.

---

## Prerequisite

Execute Tasks 1-3 only after the exact preservation plan has produced a clean `.worktrees/preservation-stabilization` worktree and its baseline passes. Before Task 4 freezes source commit S, complete operability Tasks 1-3 so packaging, dependency, verifier, and CI changes are part of S.

## Task 1: Implement a strict release manifest and artifact resolver

**Files:**

- Create: `backend/app/release_manifest.py`
- Create: `backend/tests/test_release_manifest.py`
- Create: `backend/scripts/write_release_manifest.py`
- Create: `backend/tests/test_write_release_manifest.py`

**Exact v1 keys:** `schemaVersion`, `releaseVersion`, `candidateVersion`, `runtimeVersion`, `sourceCommit`, `createdAt`, `runtimeOptions`, `artifacts`, and `requiredContracts`. Each artifact contains `id`, `sha256`, `sizeBytes`, `localRelativePath`, `containerPath`, `origin`, and `retentionClass`.

- [ ] Write failing tests for missing/unknown keys, schema version, RFC3339 timestamp, release/version formats, 40-character source SHA, lower-case 64-character hashes, positive sizes, duplicate IDs, path traversal, forbidden host absolute paths, source mismatch, missing files, wrong size/hash, and unknown required contracts.
- [ ] Test that declared container paths beginning `/app/models/` or `/app/release-inputs/` are valid while workstation paths such as `/root/WorkSpace/` are rejected.
- [ ] Run `pytest -q backend/tests/test_release_manifest.py backend/tests/test_write_release_manifest.py`; expected failure is import failure for the absent modules.
- [ ] Implement frozen dataclasses with `from_mapping`, `to_mapping`, strict unknown-key rejection, stable JSON loading/writing, streaming checksum verification, and `resolve_artifact(root, environment)`.
- [ ] Implement a writer requiring an explicit source commit and explicit timestamp. It must validate before writing and never infer dirty source content.
- [ ] Re-run focused tests; expected result is all passing. Commit these four files with `git commit -m "feat: add portable release manifest contract"`.

## Task 2: Replace runtime paths with one portable options contract

**Files:**

- Create: `backend/app/runtime_options.py`
- Create: `backend/tests/test_runtime_options.py`
- Modify: `backend/app/proof_runtime.py`
- Modify: `backend/app/processor.py`
- Modify: `backend/app/runpod.py`
- Modify: `backend/app/runpod_worker.py`
- Modify: `backend/runpod_handler/handler.py`
- Modify: `backend/tests/test_processor.py`
- Modify: `backend/tests/test_runpod.py`
- Modify: `backend/tests/test_runpod_worker.py`
- Modify: `backend/tests/test_runpod_handler.py`

**Canonical fields:** `primary_model`, `auxiliary_ball_model`, `auxiliary_ball_model_profile`, `primary_acquisition_mode`, `edge_share_repair_profile`, `baseline_guided_rescue_reference`, `proposal_selection_truth_seed`, and `reviewed_positive_anchor_seed`.

- [ ] Write a parameterized failing test proving all eight non-default fields survive mapping, JSON, RunPod request, worker, handler, and provenance boundaries. Keep `modelPath` only as an HTTP compatibility alias.
- [ ] For the two models and three seed/reference inputs, test artifact-ID/object-store-or-inline descriptors and materialization to readable verified local/container files. Equality of workstation path strings is not sufficient.
- [ ] Add failures for unknown fields, wrong types, path traversal, forbidden host paths, unavailable references, and checksum mismatch.
- [ ] Run the five focused test modules; expected failure is missing fields on the current remote path.
- [ ] Implement frozen `ArtifactReference` and `ProofRuntimeOptions` values. Translate compatibility aliases once at the HTTP boundary; pass the typed contract through all internal layers; resolve content only at the execution boundary.
- [ ] Re-run focused tests; expected result is all passing. Commit exact listed files with `git commit -m "refactor: unify portable proof runtime options"`.

## Task 3: Add verification evidence and fail-closed preflight

**Files:**

- Create: `backend/runpod_handler/preflight.py`
- Create: `backend/tests/test_runpod_preflight.py`
- Create: `backend/release/verification_schema.json`
- Modify: `backend/runpod_handler/deploy_to_runpod.sh`
- Modify: `backend/runpod_handler/Dockerfile`
- Modify: `.dockerignore`

**Verification evidence keys:** `schemaVersion`, `phase`, `sourceCommit`, `manifestSha256`, `createdAt`, `toolVersions`, `gates`, and `overallPassed`; every gate has `name`, `command`, `status`, and `completedAt`. Phase is `build_readiness` or `final`; status is `passed`, `failed`, or `pending`.

- [ ] Write failing tests for dirty source, non-ancestor source, product/runtime changes after source commit, absent/failed/stale evidence, commit or manifest-digest mismatch, missing/corrupt artifact, invalid contract, mutable tag, image-label mismatch, and valid metadata-only descendants. Build-only mode accepts clean `build_readiness` evidence only when every pre-container gate passed and only the container gate is pending; deployment mode requires clean `final` evidence with every gate passed and `overallPassed: true`.
- [ ] Define immutable tag syntax by regex `^v7\.3-[0-9a-f]{40}-[0-9a-f]{12}$` and reject `latest`, release-only tags, or shortened source identity.
- [ ] Run `pytest -q backend/tests/test_runpod_preflight.py`; expected failure is import failure for the absent module.
- [ ] Implement pure checks plus a CLI. Permit descendants of declared source commit only when every changed path is one of these release-metadata/documentation paths: `backend/release/v7.3.json`, `backend/release/verification/v7.3-build-readiness.json`, `backend/release/verification/v7.3.json`, `docs/recovery/2026-08-19/current-tree-inventory.json`, `docs/recovery/2026-08-19/container-verification.md`, `docs/recovery/2026-08-19/final-verification-report.md`, `docs/status/current.md`, `docs/runbooks/artifact-restore.md`, `docs/runbooks/deployment-preflight.md`, `docs/archive/2026-08-19/SESSION-HANDOFF.md`, `docs/archive/2026-08-19/activeContext.md`, `docs/archive/2026-08-19/currentRoadmap.md`, `docs/archive/2026-08-19/checksums.json`, `SESSION-HANDOFF.md`, `memorybank/activeContext.md`, `memorybank/currentRoadmap.md`, and `README.md`.
- [ ] Modify deployment so preflight/build-only requires no `RUNPOD_API_KEY`. Export the declared source with `git archive`, inject only the two validated metadata files and verified artifact files, and label source revision plus manifest digest. Require a separate explicit mutation flag before registry push or RunPod API access.
- [ ] Pin the Docker base by digest, explicitly exclude `backend/.env*`, consume `/app/models/` and `/app/release-inputs/`, and scope temporary cleanup to a validated directory created by the script.
- [ ] Re-run focused tests, `bash -n backend/runpod_handler/deploy_to_runpod.sh`, and `shellcheck` when installed. Commit exact listed files with `git commit -m "feat: add reproducible RunPod preflight"`.

## Task 4: Freeze product source commit S and add metadata commit M

**Files:**

- Create in metadata commit: `backend/release/v7.3.json`
- Modify before source commit S: `backend/app/proof_runtime.py`
- Record retirement in recovery inventory: `backend/storage/runtime/promoted_touchline_detector_candidate.json`
- Modify: `backend/tests/test_run_v7_2_runtime_registry_product_path_binding.py`

- [ ] Before commit S, make `proof_runtime.py` load the portable manifest path generically and use test-provided manifests; record the ignored-storage registry as replaced, not as durable release truth.
- [ ] Confirm operability Tasks 1-3 are committed, run manifest/runtime/preflight plus canonical non-Docker verification, then commit all remaining product/runtime code. Capture the resulting exact 40-character commit as S. Do not make product/runtime, packaging, dependency, verifier, or CI edits after S.
- [ ] Generate `backend/release/v7.3.json` with explicit timestamp and S. Record `yolov10n.pt` as size `5860383`, SHA-256 `11287ed0735678e7ba1ac2a9b3098c049155b3fde123992e724c1264bcc16b6f`; record touchline v7.3 as size `5711162`, SHA-256 `e7724403223429691e051ef946af1808413808349d6730bdca935da743d79cc0`.
- [ ] Use artifact IDs for both models and all required seeds/references; use relative local paths and declared `/app/...` container paths. Include required product/report contract identifiers.
- [ ] Validate the manifest against S and local artifacts, then commit only `backend/release/v7.3.json` and recorded retirement evidence as M with `git commit -m "feat: bind portable v7.3 release metadata"`.
- [ ] Verify `git diff --name-only S..M` contains only `backend/release/v7.3.json` plus the recorded recovery-inventory retirement evidence.

## Task 5: Produce verification commit V and prove the container locally

**Files:**

- Create: `backend/release/verification/v7.3-build-readiness.json`
- Create: `backend/release/verification/v7.3.json`
- Create: `docs/recovery/2026-08-19/container-verification.md`

- [ ] Run canonical non-container gates from clean metadata commit M and write `build_readiness` evidence E0 bound to S and the exact v7.3 manifest digest. Mark every pre-container gate passed, the container gate pending, and `overallPassed: false`.
- [ ] Commit only `backend/release/verification/v7.3-build-readiness.json` as E0 with `git commit -m "docs: record v7.3 build readiness"`; confirm the worktree is clean.
- [ ] Run build-only preflight at clean E0 with the immutable tag, build the image from archived S plus injected verified metadata/artifacts, and inspect its OCI revision/manifest labels. Build-only preflight must not accept a failed pre-container gate.
- [ ] Run no-network handler import/health smoke and verify all referenced artifacts materialize and pass checksum before use. Do not push or call RunPod.
- [ ] Create final evidence with every gate passed and `overallPassed: true`; commit it with container documentation as V using `git commit -m "docs: record v7.3 release verification"`. Keep E0 as immutable chronology.
- [ ] Run deployment-mode preflight at clean V. It must accept S as build source, accept only enumerated metadata changes in S..V, reject pending evidence, and reject any product/runtime change.

## Acceptance

- Durable runtime truth lives under `backend/release/`, not ignored storage.
- All eight options carry portable references and materialize to accessible verified content.
- Source S, metadata M, and verification V obey the enumerated metadata-only protocol.
- Preflight binds clean status, source, manifest, evidence, artifacts, immutable tag, and image labels.
- Local build and handler smoke pass without image push or RunPod mutation.
