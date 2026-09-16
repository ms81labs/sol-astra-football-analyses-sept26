# Recovery Freeze and Salvage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Freeze the audited 487-path recovery state byte-for-byte, inventory all local and paused-worktree evidence, and produce the exact inputs for a separate preservation-commit plan.

**Architecture:** Raw Git patches and untracked archives are captured before recovery tooling is changed. Deterministic read-only tooling then classifies the frozen path set and salvages meaningful paused-worktree content. This plan intentionally stops before staging the 487 paths; its reviewed output defines exact preservation commits without guessing.

**Tech Stack:** Git plumbing, tar, SHA-256, Python 3.11, pytest, JSON, Markdown.

---

## Fixed execution order

1. Raw current-tree freeze and raw paused-worktree metadata.
2. Recovery classifier and binary-safe salvage tooling.
3. Verified inventories and exact second preservation plan.
4. Preservation commits from that reviewed second plan.
5. Clean stabilization worktree.
6. Packaging/frontend cleanup, release/runtime foundations, and canonical verifier.
7. Freeze product source commit S, then add release metadata, operational docs, and acceptance evidence.

## Task 1: Freeze the original current-tree evidence before source edits

**Outputs outside Git:**

- `archive/2026-08-19-recovery-freeze/original-tracked.patch`
- `archive/2026-08-19-recovery-freeze/original-untracked.tar.gz`
- `archive/2026-08-19-recovery-freeze/ignored-path-inventory.nul.gz`

**Tracked report created after the raw archives are verified:**

- `docs/recovery/2026-08-19/raw-freeze-manifest.json`
- `docs/recovery/2026-08-19/raw-freeze-manifest.md`

- [ ] Confirm `git rev-parse 94a48a14^` returns original audited head `bc4f4e30` and `git branch --show-current` returns `recovery-history-batch-current`.
- [ ] Capture current porcelain status and subtract only the three agent-authored `2026-08-19-*.md` plan paths. Assert the remainder is exactly 487 paths: 30 modified, 14 deleted, 443 untracked.
- [ ] Create `original-tracked.patch` using `git diff --binary --output=archive/2026-08-19-recovery-freeze/original-tracked.patch bc4f4e30 -- . ':(exclude)docs/superpowers/specs/2026-08-19-preservation-first-stabilization-design.md'`. Assert the patch contains the 44 audited tracked paths.
- [ ] Feed the NUL-delimited original untracked path list to `tar --null --files-from=- --no-recursion -czf archive/2026-08-19-recovery-freeze/original-untracked.tar.gz`, excluding only the three plan paths. Assert the archive contains 443 members and preserves symlinks without dereferencing.
- [ ] Inventory ignored local paths NUL-safely with sizes and hashes for required artifacts; do not copy the ignored tree. Exclude `.env*`, credential files, virtual environments, dependency caches, datasets, videos, and model binaries from archive payloads. Retain them in place, record retention class, and hash only required artifacts or an explicit reviewed allowlist of small unique evidence.
- [ ] Capture exact HEAD/branch, porcelain status, worktree list, all local branch heads, ignored paths, tracked-but-ignored paths, file sizes, and SHA-256 values in the manifest using observed command output. Record the four agent-authored design/plan paths separately from the original 487.
- [ ] Verify archive readability with `tar -tzf`, verify every recorded digest with `sha256sum --check`, and perform an extraction-safety check rejecting absolute names and `..` traversal. Stop on any mismatch.
- [ ] Commit only the two manifest files and three plan files with `git commit -m "docs: plan and freeze v7.3 recovery"` after review.

## Task 2: Add deterministic dirty-path classification without editing original paths

**Files:**

- Create: `backend/scripts/run_recovery_inventory.py`
- Create: `backend/tests/test_run_recovery_inventory.py`

- [ ] Add failing tests for every allowed classification, explicit `manual_review`, stable ordering, `originalStatus`, `disposition`, `commitGroup`, evidence, all 14 deletion-evidence records, and refusal to label an unknown path disposable.
- [ ] Run `pytest -q backend/tests/test_run_recovery_inventory.py`; expected failure is `ModuleNotFoundError` for the new module.
- [ ] Implement deterministic classification over an explicit frozen status input. Emit stable JSON, Markdown, reference relationships, artifact retention metadata, and per-group path manifests. Do not stage, move, delete, or commit paths.
- [ ] Re-run the focused test; expected result is all tests passing.
- [ ] Compare classifier input with the archived 487-path list byte-for-byte and stop if they differ.

## Task 3: Add bounded paused-worktree salvage

**Files:**

- Create: `backend/scripts/run_recovery_worktree_salvage.py`
- Create: `backend/tests/test_run_recovery_worktree_salvage.py`

- [ ] Write failing temporary-repository tests for exact branch/head/status capture, meaningful binary patches, NUL-safe untracked tar creation, symlink preservation, extraction safety, canonical source/output validation, checksum verification, and zero source mutation.
- [ ] Add tests proving environment/venv deletions are recorded as path plus reachable blob ID instead of embedded binary data. Default every comparison to `unique_unresolved`; allow `integrated` only on byte/blob equality and `superseded` only with an explicit replacement commit and path.
- [ ] Run `pytest -q backend/tests/test_run_recovery_worktree_salvage.py`; expected failure is `ModuleNotFoundError` for the new module.
- [ ] Implement the read-only CLI. Reject repository-root sources, output inside the source worktree, unresolved globs, missing worktrees, unsafe archive names, and failed checksum verification.
- [ ] Emit `metadata.json`, `meaningful-tracked.patch`, `environment-deletions.json`, `untracked.tar.gz`, `checksums.json`, and `comparison.json` for each exact worktree.
- [ ] Re-run the focused test; expected result is all tests passing.

## Task 4: Salvage all four paused worktrees and publish inventories

**Exact source worktrees:**

- `.worktrees/recovery-history-batch`
- `.worktrees/hybrid-staged-recovery`
- `.worktrees/reusable-pod-lane`
- `.worktrees/proposal-support-bridge`

**Outputs:**

- Outside every registered worktree: `/root/WorkSpace/fotball-analyst-recovery-archive/2026-08-19-worktree-salvage/recovery-history-batch/`
- Outside every registered worktree: `/root/WorkSpace/fotball-analyst-recovery-archive/2026-08-19-worktree-salvage/hybrid-staged-recovery/`
- Outside every registered worktree: `/root/WorkSpace/fotball-analyst-recovery-archive/2026-08-19-worktree-salvage/reusable-pod-lane/`
- Outside every registered worktree: `/root/WorkSpace/fotball-analyst-recovery-archive/2026-08-19-worktree-salvage/proposal-support-bridge/`
- Tracked: `docs/recovery/2026-08-19/current-tree-inventory.json`
- Tracked: `docs/recovery/2026-08-19/current-tree-inventory.md`
- Tracked: `docs/recovery/2026-08-19/worktree-salvage-manifest.json`
- Tracked: `docs/recovery/2026-08-19/artifact-manifest.json`

- [ ] Run salvage separately for each exact source path and verify every output digest and extraction-safety rule.
- [ ] Inventory current and paused-worktree branch/head/status, meaningful references, all original dirty paths, ignored and tracked-but-ignored paths, and all large retained artifacts.
- [ ] For each artifact record identifier, origin, byte size, SHA-256, retention class, local location, and documented restore source. Keep ambiguous data as `manual_review`.
- [ ] Record replacement or retirement evidence plus last reachable blob ID for each of the 14 tracked deletions.
- [ ] Run `pytest -q backend/tests/test_run_recovery_inventory.py backend/tests/test_run_recovery_worktree_salvage.py` and `git diff --check`.
- [ ] Confirm the original untracked triage script and test remain byte-identical to their raw-freeze archive members.
- [ ] Commit only the newly authored inventory/salvage tools, their tests, and tracked reports with `git commit -m "feat: inventory and salvage v7.3 recovery state"`. Do not stage any of the original 487 paths.

## Task 5: Write the exact preservation-commit plan

**File:**

- Create: `docs/superpowers/plans/2026-08-19-exact-v7-3-preservation-commits.md`

- [ ] Generate the plan from reviewed inventory output, then manually verify every group.
- [ ] Name every path in every commit, every deletion disposition, each exact `git add --` command with its literal path list, focused test command, expected result, and commit subject.
- [ ] Enforce dependency order: product importer and imported files together; runtime contract before consumers; shared workflow helpers before entrypoints; release truth after source; documentation last.
- [ ] Include a final reconciliation proving all 487 original paths are committed, archived with verified checksums, or intentionally ignored with evidence.
- [ ] End that second plan by creating `.worktrees/preservation-stabilization` only after the preservation branch is clean. Verify `.worktrees` is ignored and run the full preserved baseline before continuing.
- [ ] Obtain independent specification and quality approval for the second plan before staging any of the 487 original paths.

## Acceptance

- The original 487 paths are recoverable from verified raw archives.
- All four paused worktrees have safe, verified salvage outputs.
- No unique content is classified as integrated/superseded without objective evidence.
- Every artifact and deletion has the required provenance.
- No original recovery path is staged until an exact path-by-path preservation plan is approved.
