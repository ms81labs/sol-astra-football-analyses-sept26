# Project Operability and Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Make a clean checkout installable, free of known critical/high production dependency findings, verifiable through one local/CI command, and documented by one authoritative runbook.

**Architecture:** Root Python packaging declares the backend while the research sidecar keeps its own package. Dependency groups separate runtime, development, and local ML/GPU concerns. One strict verification script is the CI entrypoint. Three append-only current files are archived byte-for-byte and replaced with concise pointers to authoritative status.

**Tech Stack:** setuptools/PEP 621, pytest, npm/Vite/Vitest/ESLint/TypeScript, Bash, GitHub Actions, Docker.

---

## Prerequisite

After the clean stabilization worktree exists, execute Tasks 1-2, then release/runtime Tasks 1-3, then Task 3 here. All three must be committed before release Task 4 freezes source commit S. Execute Task 4 after manifest commit M and Task 5 after verification evidence exists. Any later packaging, dependency, verifier, CI, or product/runtime change requires a new S.

## Task 1: Declare installable backend and sidecar packages

**Files:**

- Create: `pyproject.toml`
- Create: `backend/requirements-runtime.txt`
- Create: `backend/requirements-dev.txt`
- Create: `backend/requirements-ml.txt`
- Modify: `backend/requirements.txt`
- Modify: `research-addon/pyproject.toml`
- Modify: `research-addon/tests/test_cli.py`
- Modify: `README.md`
- Create: `backend/tests/test_documented_startup.py`

- [ ] Write failing subprocess tests that build/install the root package, import `backend.app.main` from outside the checkout, install `research-addon`, import `research_addon` without `PYTHONPATH`, require CLI failures to fail tests, and import the documented ASGI target without creating storage in the checkout.
- [ ] Run `pytest -q backend/tests/test_documented_startup.py research-addon/tests/test_cli.py`; expected current failure includes sidecar import without manual path injection and the broken documented startup context.
- [ ] Define root setuptools discovery for `backend*`, require Python 3.11+, include `backend/release/*.json` and `backend/release/verification/*.json` as package data, and expose no accidental `backend/storage` package data.
- [ ] Put FastAPI, boto3, HTTPX, pandas, Pydantic, multipart, Starlette, Uvicorn, and other import-proven non-ML runtime dependencies in `requirements-runtime.txt`; put pytest/test tools in `requirements-dev.txt`; put Torch/CUDA/OpenCV/Ultralytics and local CV stack in `requirements-ml.txt`. Make `requirements.txt` an explicit compatibility aggregate of those three files.
- [ ] Keep the sidecar package independent and add its pytest configuration/CLI entrypoint. Replace vacuous conditional assertions in `research-addon/tests/test_cli.py` with checked exit codes and exact stdout/stderr assertions.
- [ ] Update README commands to install from the repository root and start `uvicorn backend.app.main:app`.
- [ ] Create fresh virtual environments outside the repository; install root runtime+dev, install sidecar, then pass documented startup tests and all 37 sidecar tests. Commit exact listed files with `git commit -m "fix: make backend and sidecar installable"`.

## Task 2: Remove unused vulnerable frontend packages

**Files:**

- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `frontend/vite.config.ts`

- [ ] Confirm `rg -n "@google/genai|apache-arrow|parquet-wasm" frontend/src frontend --glob '!package*.json' --glob '!vite.config.ts'` has no production-source match.
- [ ] Remove `@google/genai`, `apache-arrow`, and `parquet-wasm`; remove `vite-plugin-wasm`, its import, `wasm()` registration, and `optimizeDeps.exclude: ['parquet-wasm']`.
- [ ] Run `npm ci`, `npm test -- --run`, `npm run lint`, `npx tsc -p tsconfig.app.json --noEmit --incremental false`, `npx tsc -p tsconfig.node.json --noEmit --incremental false`, `npm run build`, and `npm audit --omit=dev --audit-level=high` from `frontend`.
- [ ] If the audit still reports critical/high production findings, update one direct dependency family at a time within compatible majors and repeat all gates. Do not use `npm audit fix --force`.
- [ ] Expected acceptance is at least 46 passing tests, clean lint/typecheck/build, and zero known critical/high production findings. Commit exact files with `git commit -m "fix: harden frontend production dependencies"`.

## Task 3: Add the canonical verifier and GitHub Actions workflow

**Files:**

- Create: `scripts/verify.sh`
- Create: `backend/tests/test_verify_script.py`
- Create: `.github/workflows/ci.yml`

- [ ] Write failing tests with stub executables for fixed gate order, first-failure nonzero exit, printed command/correction, per-gate logs, minimum test-count enforcement, optional Docker gating, and no external mutation.
- [ ] Run `pytest -q backend/tests/test_verify_script.py`; expected failure is absence of `scripts/verify.sh`.
- [ ] Implement strict Bash functions in this order: backend tests; sidecar tests; frontend tests; lint; app/node typecheck; production build; backend import/startup; manifest validation; runtime-option round trip; preflight negative tests; production dependency audit; optional Docker build/handler smoke.
- [ ] Write logs beneath `.verification/logs/`, print the failing gate and corrective command, and stop at first required failure. Require `VERIFY_DOCKER=1` for container gates; never push images or call RunPod.
- [ ] Configure `.github/workflows/ci.yml` for pull requests and branch pushes using Ubuntu, Python 3.11, Node 22, `pip install -e . -r backend/requirements-dev.txt`, sidecar editable install, and `npm ci --prefix frontend`. Cache from the Python requirement files and `frontend/package-lock.json`, call only `scripts/verify.sh`, and upload `.verification/logs/` on failure.
- [ ] Run script unit tests, `bash -n scripts/verify.sh`, and a local non-Docker verifier pass. Commit exact files with `git commit -m "ci: add canonical project verification"`.

## Task 4: Archive chronology and publish one operational truth

**Files:**

- Move: `SESSION-HANDOFF.md` to `docs/archive/2026-08-19/SESSION-HANDOFF.md`
- Move: `memorybank/activeContext.md` to `docs/archive/2026-08-19/activeContext.md`
- Move: `memorybank/currentRoadmap.md` to `docs/archive/2026-08-19/currentRoadmap.md`
- Create concise compatibility pointers at the three original paths
- Create: `docs/archive/2026-08-19/checksums.json`
- Create: `docs/status/current.md`
- Create: `docs/runbooks/artifact-restore.md`
- Create: `docs/runbooks/deployment-preflight.md`
- Modify: `README.md`
- Create: `backend/tests/test_operational_docs.py`

- [ ] Before moving, record byte sizes and SHA-256 for all three historical files. After moving, verify exact digest equality and record it in `checksums.json`.
- [ ] Write failing documentation tests requiring one current release, one next-action heading, executable startup/verification/build-only commands, both model identifiers/hashes, no workstation absolute path, and explicit statements that live deployment, image push, history rewrite, and data/model deletion did not occur.
- [ ] Replace original current files with short pointers to `docs/status/current.md` and their exact archive destinations; do not discard chronology.
- [ ] Document v7.3 status, preservation commits, artifact restore identifiers/checksums, canonical verifier, metadata-only source protocol, deployment preflight/build-only procedure, external prerequisites, deferred CV/API/frontend/history work, and one next action.
- [ ] Run `pytest -q backend/tests/test_operational_docs.py`, command syntax checks, and archive checksum verification. Commit exact files with `git commit -m "docs: publish v7.3 operational runbook"`.

## Task 5: Run clean-checkout acceptance and bounded worktree cleanup

**Files:**

- Create: `docs/recovery/2026-08-19/final-verification-report.md`
- Modify: `docs/status/current.md`

- [ ] In `.worktrees/preservation-stabilization`, create fresh Python/Node environments from declared manifests and restore artifacts only through the documented identifiers.
- [ ] Run `VERIFY_DOCKER=1 scripts/verify.sh` when both manifest artifacts are available. Require at least 1,486 backend tests, 37 sidecar tests, and 46 frontend tests plus all lint, typecheck, build, startup, manifest, options, preflight, audit, and container gates.
- [ ] Record exact versions, commands, counts, durations, results, image digest/labels, before/after status, storage footprint, dependency findings, and every skipped optional gate with reason.
- [ ] Reverify the salvage metadata and checksums for exact path `.worktrees/recovery-history-batch`; require no `unique_unresolved` entries. If redundant, run `git worktree remove .worktrees/recovery-history-batch` without `--force` and retain its branch.
- [ ] Keep `.worktrees/hybrid-staged-recovery`, `.worktrees/reusable-pod-lane`, and `.worktrees/proposal-support-bridge` plus all branches unless a separately approved exact cleanup plan proves them redundant.
- [ ] Confirm no live RunPod mutation, registry push, history rewrite, model/data deletion, or broad architectural refactor occurred.
- [ ] Commit the report/status with `git commit -m "docs: complete v7.3 stabilization verification"`.

## Acceptance

- Clean environments install backend and sidecar without manual path injection.
- Current README startup works from the repository root.
- The verifier meets all test counts and production dependency audit requirements.
- CI and local development run the same script.
- Historical chronology is preserved byte-for-byte and one current status is authoritative.
- Cleanup is limited to one exact fully salvaged redundant worktree; its branch remains.
