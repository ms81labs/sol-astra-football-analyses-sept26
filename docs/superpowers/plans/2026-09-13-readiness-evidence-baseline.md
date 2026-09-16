# Readiness Evidence Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a current, source-bound local release baseline that separates software verification from inference, accuracy, capacity, and analyst acceptance.

**Architecture:** Reuse the authoritative status page and existing release manifest, verifier receipt, and pre-cloud evidence writer. Freeze source changes first, then permit only the release metadata paths already enforced by `METADATA_ALLOWLIST`; remove historical final evidence from the active path until G-PRODUCT produces a current replacement.

**Tech Stack:** Markdown, pytest, Git, existing Python release writers, `scripts/verify.sh`

**Spec:** `docs/superpowers/specs/2026-09-13-football-analysis-readiness-execution-design.md`

## Global Constraints

- Do not perform a Daytona/provider operation in this plan.
- Preserve the historical fourth-smoke evidence in Git history and dated recovery documentation.
- Keep `docs/status/current.md` as the single current-status page.
- Report absent inference, labeled accuracy, capacity, and analyst acceptance as `unproven`.
- Add no dependency, schema, release helper, or parallel readiness summary.

---

### Task 1: Freeze the evidence contract and assessed source

**Files:**
- Modify: `backend/tests/test_operational_docs.py`
- Modify: `docs/status/current.md`
- Add: `docs/reports/2026-09-13-football-analysis-readiness.md`
- Add: `docs/superpowers/plans/2026-09-13-readiness-evidence-baseline.md`

**Interfaces:**
- Consumes: current verifier receipt at `.verification/receipt.json` and the five evidence classes defined by the design.
- Produces: a tracked source commit whose status page has one machine-checked evidence table.

- [x] **Step 1: Extend the existing operational-doc test and verify RED**

Add these assertions to `test_current_docs_contain_safe_executable_operations_and_retirement_record` after reading `docs/status/current.md` separately:

```python
status = (ROOT / "docs/status/current.md").read_text(encoding="utf-8")
for evidence_class in (
    "Software verification",
    "Actual pipeline inference",
    "Independently labeled accuracy",
    "Resource/capacity measurement",
    "Analyst acceptance",
):
    assert f"| {evidence_class} |" in status
assert "3,546 passed; 1 skipped" in status
assert "128 passed across 23 test files" in status
```

Run:

```bash
python3 -m pytest -q backend/tests/test_operational_docs.py::test_current_docs_contain_safe_executable_operations_and_retirement_record
```

Expected: FAIL because the evidence rows and current counts are absent.

- [x] **Step 2: Update the authoritative status page and verify GREEN**

Replace the stale local counts with the receipt-backed counts from the readiness report and add this table below them:

```markdown
| Evidence class | Current source-bound result | Readiness consequence |
|---|---|---|
| Software verification | Local gates passed at source `72f554507487652521af7002c8eb4be98a5c78bf`; exact counts are listed above. | Ready for continued development and controlled evaluation within test coverage. |
| Actual pipeline inference | No current-source unseen-video inference run is recorded by the local verifier. | Unproven for football reconstruction; G-PRODUCT remains pending. |
| Independently labeled accuracy | No current HOTA, IDF1, visible-ball precision/recall, pitch error, possession agreement, or event AP result. | Unproven; workflow and crop checks are excluded from accuracy denominators. |
| Resource/capacity measurement | No current complete-match detector/tracker host RAM, GPU RAM, wall-time, and disk measurement. | Unproven; G-CAPACITY follows G-PRODUCT. |
| Analyst acceptance | No declared-camera pilot has been reviewed against agreed thresholds by the intended analyst. | Unproven; keep outputs review-only. |
```

Run the focused test again. Expected: PASS.

- [x] **Step 3: Verify and commit the selected source**

Run:

```bash
python3 -m pytest -q backend/tests/test_operational_docs.py
git diff --check
git add backend/tests/test_operational_docs.py docs/status/current.md docs/reports/2026-09-13-football-analysis-readiness.md docs/superpowers/plans/2026-09-13-readiness-evidence-baseline.md
git commit -m "docs: establish readiness evidence baseline"
git rev-parse HEAD
```

Expected: tests pass and the printed commit becomes `SOURCE_COMMIT` for Task 2.

### Task 2: Bind v7.3 metadata to the selected source

**Files:**
- Modify: `backend/release/v7.3.json`
- Delete: `backend/release/verification/v7.3-pre-cloud.json`
- Delete: `backend/release/verification/v7.3.json`

**Interfaces:**
- Consumes: `SOURCE_COMMIT` from Task 1 and the five existing artifact identities/runtime options.
- Produces: a metadata-only commit with a manifest validated against all local artifacts and no active stale evidence.

- [ ] **Step 1: Replace only manifest source identity and timestamp**

Set `sourceCommit` to `git rev-parse HEAD`, set `createdAt` to the current RFC3339 UTC time, and leave every other manifest value byte-for-value equivalent. Validate the edited file through the existing writer:

```bash
python3 -m backend.scripts.write_release_manifest \
  --input backend/release/v7.3.json \
  --output backend/release/v7.3.json \
  --artifact-root "$PWD" \
  --source-commit "$(jq -r .sourceCommit backend/release/v7.3.json)" \
  --created-at "$(jq -r .createdAt backend/release/v7.3.json)"
```

Expected: exit 0 after streaming hash validation of all five declared artifacts.

- [ ] **Step 2: Remove evidence bound to the historical source**

Delete both active evidence files. The historical final result remains in Git history and `docs/recovery/2026-08-24/daytona-gpu-smoke.md`.

- [ ] **Step 3: Run focused release checks and commit only metadata**

Run:

```bash
python3 -m pytest -q backend/tests/test_release_manifest.py backend/tests/test_write_release_manifest.py backend/tests/test_release_evidence.py backend/tests/test_release_preflight.py
git diff --check
git diff --name-only
git add backend/release/v7.3.json
git add -u backend/release
git commit -m "release: bind v7.3 readiness baseline"
```

Expected: all focused tests pass; the pre-commit diff names only the three release metadata paths.

### Task 3: Publish fresh pre-cloud evidence and current status

**Files:**
- Create: `backend/release/verification/v7.3-pre-cloud.json`
- Modify: `docs/status/current.md`
- Generated, untracked: `.verification/receipt.json`, `.verification/logs/*.log`

**Interfaces:**
- Consumes: clean metadata commit from Task 2 and canonical gates 1-12.
- Produces: receipt-backed pre-cloud evidence with G-PRODUCT pending and an authoritative status page naming the selected source.

- [ ] **Step 1: Run the canonical mutation-disabled verifier**

Run:

```bash
VERIFY_DAYTONA=0 ALLOW_DAYTONA_MUTATION=0 scripts/verify.sh
```

Expected: gates 1-12 pass, the provider operation is explicitly skipped, and `.verification/receipt.json` binds the clean metadata commit and current manifest digest.

- [ ] **Step 2: Write pre-cloud evidence before changing status**

Run:

```bash
python3 -m backend.scripts.write_verification_evidence \
  --phase pre_cloud \
  --output backend/release/verification/v7.3-pre-cloud.json
```

Expected: schema-v2 evidence has `overallPassed=false`, a pending `daytona-gpu-smoke` gate, and `remoteExecution=null`.

- [ ] **Step 3: Update status with the new binding**

Replace the evidence table's old source SHA with `jq -r .sourceCommit backend/release/v7.3.json`. State that `backend/release/verification/v7.3-pre-cloud.json` is the current local release evidence and that no active final evidence exists until G-PRODUCT succeeds. Keep the historical fourth smoke explicitly historical.

- [ ] **Step 4: Commit and validate the complete baseline**

Run:

```bash
git add backend/release/verification/v7.3-pre-cloud.json docs/status/current.md
git commit -m "docs: publish readiness pre-cloud evidence"
manifest_sha="$(sha256sum backend/release/v7.3.json | cut -d ' ' -f 1)"
source_commit="$(jq -r .sourceCommit backend/release/v7.3.json)"
python3 -m backend.release.preflight validate \
  --repo-root . \
  --manifest backend/release/v7.3.json \
  --evidence backend/release/verification/v7.3-pre-cloud.json \
  --mode build-only \
  --image-tag "v7.3-${source_commit}-${manifest_sha:0:12}"
python3 -m pytest -q backend/tests/test_operational_docs.py backend/tests/test_release_manifest.py backend/tests/test_release_evidence.py backend/tests/test_release_preflight.py
git diff --check
git status --short
```

Expected: preflight and focused tests pass. Git status shows only the allowed untracked `.verification/` directory and no active `backend/release/verification/v7.3.json`.
