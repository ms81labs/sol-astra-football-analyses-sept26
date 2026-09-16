# Verifier-Bound Release Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make canonical release evidence use the manifest's frozen source commit and prove its local gate claims came from one successful canonical verifier run.

**Architecture:** `scripts/verify.sh` clears stale success state, runs the twelve local gates, and asks the existing evidence utility to atomically record one untracked receipt containing the clean metadata commit plus exact log hashes/timestamps. The evidence writer consumes that receipt, records `sourceCommit=S` and `verificationCommit=M`, and canonical preflight verifies both bindings. The rejected release chain stays in history and is superseded by a newly frozen `S -> M -> E0` chain.

**Tech Stack:** Bash, Python 3.12 standard library, dataclasses, JSON Schema, pytest, Git.

---

## File responsibilities

- `scripts/verify.sh`: owns gate execution and creates a success receipt only after every required local gate passes.
- `backend/scripts/write_verification_evidence.py`: securely records/parses the untracked verifier receipt and publishes receipt-backed evidence.
- `backend/release/evidence.py`: strictly parses the committed evidence contract.
- `backend/release/verification_schema.json`: machine-readable schema for the same contract.
- `backend/release/preflight.py`: binds the manifest source, verification commit, manifest bytes, and current metadata/evidence ancestry.
- `backend/tests/test_verify_script.py`: verifier receipt lifecycle and failure behavior.
- `backend/tests/test_release_evidence.py`: receipt/evidence writer behavior and schema semantics.
- `backend/tests/test_release_preflight.py`: end-to-end source/verification commit binding.

## Task 1: Add receipt-backed evidence contract

**Files:**

- Modify: `backend/release/evidence.py`
- Modify: `backend/release/verification_schema.json`
- Modify: `backend/tests/test_release_evidence.py`

- [ ] **Step 1: Write failing parser/schema tests**

Add cases requiring top-level `verificationCommit` to be an exact lower-case 40-character SHA and requiring every gate to contain `logSha256`: a 64-character lower-case digest for passed/failed gates and `null` for pending gates. Add hostile unknown/missing/type/case values and round-trip assertions.

- [ ] **Step 2: Run RED**

Run:

```bash
python3 -m pytest -q backend/tests/test_release_evidence.py -k 'verification_commit or log_sha or schema'
```

Expected: failures because the current strict parser rejects the new fields.

- [ ] **Step 3: Implement the minimal contract change**

Add `verification_commit: str` to `VerificationEvidence` and `log_sha256: str | None` to `VerificationGate`. Reuse `SOURCE_COMMIT_RE` and `SHA256_RE`; do not add a new validator. Update `to_mapping()` and the JSON schema exact required/property sets. Keep schema version 2 because no valid Daytona v2 evidence has shipped.

- [ ] **Step 4: Run GREEN**

```bash
python3 -m pytest -q backend/tests/test_release_evidence.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/release/evidence.py backend/release/verification_schema.json backend/tests/test_release_evidence.py
git commit -m "feat: bind verification provenance in release evidence"
```

## Task 2: Record one successful verifier receipt

**Files:**

- Modify: `backend/scripts/write_verification_evidence.py`
- Modify: `scripts/verify.sh`
- Modify: `backend/tests/test_verify_script.py`
- Modify: `backend/tests/test_release_evidence.py`

- [ ] **Step 1: Write failing receipt lifecycle tests**

Require `scripts/verify.sh` to remove `.verification/receipt.json` before its first gate. A simulated failed gate must leave no receipt. A fully simulated successful run must create canonical JSON containing:

```json
{
  "schemaVersion": 1,
  "repositoryCommit": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "manifestSha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
  "createdAt": "2026-09-08T21:30:00Z",
  "toolVersions": {"python": "3.12.3"},
  "gates": [
    {
      "name": "backend",
      "command": "python3 -m pytest -q backend/tests",
      "completedAt": "2026-09-08T21:29:00Z",
      "logSha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
    }
  ]
}
```

The final list must contain exactly the first twelve entries from `REQUIRED_GATE_COMMANDS` in order. Quiet-command logs may be empty. Reject missing, symlinked, non-regular, escaped, reordered, or post-receipt logs; a dirty tracked worktree; a missing/untracked manifest; and overwrite attempts.

- [ ] **Step 2: Run RED**

```bash
python3 -m pytest -q backend/tests/test_verify_script.py backend/tests/test_release_evidence.py -k receipt
```

- [ ] **Step 3: Implement receipt recording with existing primitives**

Add a mutually exclusive `--record-verifier-success` CLI mode to `backend.scripts.write_verification_evidence`. It uses fixed repository paths `.verification/logs` and `.verification/receipt.json`, the existing canonical gate mapping, `hashlib`, `os.stat(..., follow_symlinks=False)`, Git porcelain/HEAD checks, exact manifest bytes, and the existing safe exclusive atomic publisher. Do not create a new script or dependency.

Update `scripts/verify.sh` to remove the exact receipt path after validating `.verification/`, then invoke:

```bash
python3 -m backend.scripts.write_verification_evidence --record-verifier-success
```

immediately after `prod-audit` succeeds and before the optional Daytona gate.

- [ ] **Step 4: Run GREEN and syntax checks**

```bash
python3 -m pytest -q backend/tests/test_verify_script.py backend/tests/test_release_evidence.py
bash -n scripts/verify.sh
git diff --check
```

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/write_verification_evidence.py scripts/verify.sh backend/tests/test_verify_script.py backend/tests/test_release_evidence.py
git commit -m "fix: require canonical verifier receipt"
```

## Task 3: Consume the receipt and enforce both commit bindings

**Files:**

- Modify: `backend/scripts/write_verification_evidence.py`
- Modify: `backend/release/preflight.py`
- Modify: `backend/tests/test_release_evidence.py`
- Modify: `backend/tests/test_release_preflight.py`

- [ ] **Step 1: Write failing writer/preflight tests**

Prove that normal evidence generation fails before output creation when the receipt is missing, stale, malformed, for a different manifest/commit, has a changed log digest/timestamp, or contains noncanonical gates. Prove pre-cloud output uses manifest `sourceCommit`, receipt `repositoryCommit` as `verificationCommit`, actual receipt gate times/hashes, and a pending Daytona gate with null time/hash.

Add an end-to-end build-only preflight case where `S != M`: manifest/evidence source both equal `S`, verification commit equals `M`, manifest bytes at `M` match, and preflight passes. Reject non-ancestor verification commits and manifest bytes that differ at that commit.

- [ ] **Step 2: Run RED**

```bash
python3 -m pytest -q backend/tests/test_release_evidence.py backend/tests/test_release_preflight.py -k 'receipt or verification_commit or source_commit'
```

- [ ] **Step 3: Implement minimal receipt consumption**

Normal writer mode loads the fixed receipt, re-hashes every named log, validates timestamps/order/freshness, and reads the manifest through the existing strict manifest parser. Set `sourceCommit` from `manifest.sourceCommit`; never infer it from current `HEAD`. Set `verificationCommit` from the receipt.

For `pre_cloud`, require `HEAD == verificationCommit`. For `final`, require `verificationCommit` to be an ancestor of `HEAD`. Reuse the twelve receipt gates. For final evidence, set gate 13 `completedAt` to `remoteExecution.deletedAt` and `logSha256` to the SHA-256 of the canonical remote-execution input file; for pre-cloud it remains pending with both fields null.

In preflight, require the verification commit to be an ancestor of current `HEAD`. Read `backend/release/v7.3.json` from that validated commit with `git show` and require its digest to equal `manifestSha256`. Keep the existing frozen-source allowlist and cleanliness checks.

- [ ] **Step 4: Run GREEN**

```bash
python3 -m pytest -q backend/tests/test_release_evidence.py backend/tests/test_release_preflight.py backend/tests/test_verify_script.py
bash -n scripts/verify.sh
git diff --check
```

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/write_verification_evidence.py backend/release/preflight.py backend/tests/test_release_evidence.py backend/tests/test_release_preflight.py
git commit -m "fix: bind release evidence to verified source"
```

## Task 4: Reject the invalid chain and create a new source freeze

**Files:**

- Delete: `backend/release/v7.3.json`
- Delete: `backend/release/verification/v7.3-pre-cloud.json`
- Modify: `docs/status/current.md` only if needed to identify the rejected evidence chronology

- [ ] **Step 1: Preserve chronology without copying generated evidence**

Keep commits `6a484d04`, `3faaafca`, and `071c7876` in Git history. Delete the active manifest and invalid pre-cloud evidence. Add at most one concise status sentence if the rejected chain is not otherwise discoverable; do not create a new archive or duplicate the invalid JSON.

- [ ] **Step 2: Run focused and canonical non-cloud verification before freeze**

```bash
python3 -m pytest -q backend/tests/test_release_evidence.py backend/tests/test_release_preflight.py backend/tests/test_verify_script.py
VERIFY_DAYTONA=0 ALLOW_DAYTONA_MUTATION=0 scripts/verify.sh
```

The canonical verifier runs while the prior manifest still exists; delete the stale manifest/evidence only after the successful run, matching the original Task 11 staged protocol.

- [ ] **Step 3: Audit and freeze**

```bash
git diff --check
git fsck --no-reflogs --full
git add -A -- backend/release/v7.3.json backend/release/verification/v7.3-pre-cloud.json docs/status/current.md
git commit -m "feat: refreeze verifier-bound Daytona source"
git rev-parse HEAD
```

Record the new result as `S_DAYTONA_2`. The worktree must be clean and no product/runtime/dependency/verifier/CI/current-document path may change afterward.

## Task 5: Regenerate metadata and verifier-bound pre-cloud evidence

**Files:**

- Create: `backend/release/v7.3.json`
- Modify: `docs/recovery/2026-08-19/current-tree-inventory.json`
- Create: `backend/release/verification/v7.3-pre-cloud.json`

- [ ] **Step 1: Generate metadata and commit `M_DAYTONA_2`**

Use the existing manifest writer with `sourceCommit=S_DAYTONA_2`, a fresh UTC timestamp, and the authoritative Daytona template. Validate all five artifact hashes/sizes, eight runtime options, two contracts, and historical registry identity. Commit exactly manifest plus inventory as:

```bash
git commit -m "feat: rebind Daytona v7.3 release metadata"
```

- [ ] **Step 2: Run the canonical verifier from clean metadata**

```bash
VERIFY_DAYTONA=0 ALLOW_DAYTONA_MUTATION=0 scripts/verify.sh
```

Require all local gates passed, Daytona explicitly skipped, and `.verification/receipt.json` bound to exact `M_DAYTONA_2` plus the current manifest digest.

- [ ] **Step 3: Generate evidence and inspect its receipt bindings**

```bash
python3 -m backend.scripts.write_verification_evidence \
  --phase pre_cloud \
  --output backend/release/verification/v7.3-pre-cloud.json
```

Require `sourceCommit=S_DAYTONA_2`, `verificationCommit=M_DAYTONA_2`, twelve receipt-derived log hashes/times, pending Daytona gate, `overallPassed=false`, and `remoteExecution=null`.

- [ ] **Step 4: Commit only evidence, then prove canonical preflight and the final allowlist**

```bash
git add backend/release/verification/v7.3-pre-cloud.json
git commit -m "docs: record verifier-bound Daytona pre-cloud evidence"
manifest_sha256="$(sha256sum backend/release/v7.3.json | cut -d ' ' -f 1)"
source_commit="$(python3 -c 'import json; print(json.load(open("backend/release/v7.3.json"))["sourceCommit"])')"
python3 -m backend.release.preflight validate \
  --repo-root . \
  --manifest backend/release/v7.3.json \
  --evidence backend/release/verification/v7.3-pre-cloud.json \
  --mode build-only \
  --image-tag "v7.3-${source_commit}-${manifest_sha256:0:12}"
```

Canonical preflight intentionally runs after the evidence commit because it requires the evidence path to be tracked at `HEAD`. Record `E0_DAYTONA_2`. Verify clean ancestry, exact three-file `S_DAYTONA_2..E0_DAYTONA_2` allowlist, canonical build-only preflight success, and zero cloud calls.

## Final review

- [ ] Fresh specification review of the new design, implementation, rejected-chain chronology, and `S2 -> M2 -> E02` evidence.
- [ ] Fresh adversarial quality review with no open Critical, Important, or Minor findings before Task 13.
