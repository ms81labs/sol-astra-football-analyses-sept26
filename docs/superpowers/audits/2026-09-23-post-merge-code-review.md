# Post-merge code review — 23 September 2026

**Reviewed source:** `3efcfc1126f849f595633ba02685bf4b64174550`  
**Reviewed tree:** `dad5e61cad840cb654d70019af934b4ef9145676`  
**Merge:** PR #12, merged to `main` on 2026-09-23  
**Baseline for changed-code review:** `c685640a897c16669e3b1848d77bf9e6e5d7e8cf`  
**Review identity:** ChatGPT/Superpowers correctness review plus Ponytail small-diff review; not an independent human review.

## Verdict

The merged implementation is materially stronger than the September 22 baseline. I found **no Critical/P1 issue** and did not reproduce a new backend storage, receipt-integrity, generation-pinning, billing, or media-safety failure in the modified code.

There are **two Important/P2 gaps** worth fixing and **three Minor/P3 cleanup issues**. Neither Important finding invalidates the successful post-merge C05/C06 execution already observed, but both weaken the intended long-term generation/evidence guarantees.

## Findings

### CR-01 — P2 Important — Trust-crop client does not enforce response generation

**Location:** `frontend/src/utils/api.ts:456-463`; compare `frontend/src/utils/request.ts:39-50`.

`fetchTrustCrops()` now sends `generationId`, and the response schema now carries `generationId`, but the client returns the parsed response without calling the existing `assertGeneration()` guard. The other generation-aware read helpers validate that the server returned the generation that was requested.

The component-level cancellation logic only protects an older in-flight promise after the prop changes. It does **not** protect a same-request stale/misbound `200` response. If a cache, proxy, or future backend regression returned generation N for a request for N+1, the panel would accept and render N.

The same function also manually throws a generic `Error` for non-2xx responses before `parseJson()` can preserve the backend's structured error code. That turns states such as generation recovery/refusal into only `Failed to load trust crops: 503`.

**Recommended fix:**

```ts
const payload = await parseJson<TrustCropsResponse>(response);
assertGeneration(payload, generationId);
return payload;
```

Remove the manual `!response.ok` branch and import/use the already-existing `assertGeneration`. Add a test for requested `gen-2` / returned `gen-1`, and one structured generation-error response.

### CR-02 — P2 Important — Dedicated C06 workflow can miss changes that affect its evidence

**Location:** `.github/workflows/c06-regressions.yml:3-12`.

The C06 workflow's path filter names `media.py`, `media_execution.py`, `_media_launcher.py`, `storage.py`, the C06 tests, and the workflow itself. But `media.py` directly imports and depends on at least:

- `backend/app/workbench/contracts.py`
- `backend/app/workbench/hashing.py`
- `backend/app/workbench/executables.py`
- `backend/app/workbench/media_execution.py`

The workflow also installs `backend/requirements/dev.lock`, but that lock and `pyproject.toml` are absent from its trigger paths.

The ordinary `CI` workflow helps: it runs the normal media/integration/full-backend selections on every push. However, the special opt-in >8 GiB synthetic decode is executed only by the dedicated C06 workflow. A change to one of the omitted shared dependencies or the lock can therefore change media behavior without producing a new source-bound long-decode C06 artifact.

**Recommended fix:** make the C06 trigger match its dependency boundary. The simplest durable form is `backend/**` plus `pyproject.toml` and the workflow path (or remove the path filter on `main`). If a narrow filter is retained, include all direct media dependencies and the lock inputs explicitly.

### CR-03 — P3 Minor — Trust-crop saved state survives a generation change

**Location:** `frontend/src/components/TrustCropPanel.tsx:42-68`.

On `matchId` / `generationId` changes, the effect clears data, loading state, and load errors. It does not clear `savedCropKeys` or `savingCropKey`.

The component is not keyed by generation in `App.tsx`, so it can remain mounted while the active generation changes. A crop with the same frame bounds in N+1 can therefore be shown as **Saved for training set** because the matching bounds were saved in N, and the save button remains disabled.

**Recommended fix:** scope the saved/saving state to `matchId + generationId`, or clear it in the same generation-change effect. Add a regression that saves a crop in N, rerenders N+1 with the same range, and verifies the N+1 crop is not marked saved.

### CR-04 — P3 Minor — Workflow filters still name retired branches

**Locations:** `.github/workflows/c05-regressions.yml:4`, `.github/workflows/c06-regressions.yml:4`.

After PR #12, the repository branch inventory contains only `main`, but C05 still names `agent/c05-identity-evaluation` and `agent/backend-bounded-completion-2026-09-22`, while C06 still names the latter.

This does not break current execution, but it is dead configuration after the requested single-main consolidation and makes the workflow contract look broader than the actual branch topology.

**Recommended fix:** reduce these branch lists to the branches that are intentionally supported now; currently that is `main`.

### CR-05 — P3 Minor — The merged delta is not clean under `git diff --check`

**Location:** `docs/superpowers/audits/2026-09-22-backend-v3-1-integration-closure.md:3`.

Running:

```bash
git diff --check c685640a897c16669e3b1848d77bf9e6e5d7e8cf..3efcfc1126f849f595633ba02685bf4b64174550
```

reports the two trailing spaces after the date line. This is documentation-only and has no runtime impact, but it is avoidable noise in a program that explicitly uses diff hygiene as evidence.

**Recommended fix:** remove the trailing spaces (or use explicit Markdown markup if a hard line break is desired).

## Evidence and verification

### Merge/source identity

PR #12 merged with merge commit `3efcfc1126f849f595633ba02685bf4b64174550`. The merge tree is `dad5e61cad840cb654d70019af934b4ef9145676`, the same code tree that was verified immediately before integration. The former working branch has already been removed; the branch inventory now contains only `main`.

### Independent review-focused execution

Using the exact merged repository bundle, I ran:

```bash
PYTHONPATH="$PWD" PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 VERIFY_DAYTONA=0 ALLOW_DAYTONA_MUTATION=0 PYTHON_DOTENV_DISABLED=1 python -m pytest -q   backend/tests/test_trust_crops.py   backend/tests/test_trust_crop_snapshot.py   backend/tests/test_verification_receipts.py   backend/tests/test_verification_receipt_integrity.py   backend/tests/test_storage_schema_initialization.py   backend/tests/test_auxiliary_write_observability.py
```

Result: **75 passed**.

`python -m compileall -q backend/app backend/scripts` also completed successfully.

### Actual post-merge main-push evidence

At the reviewed merge SHA:

- **C05 main-push run 35838889015:** success.
  - pinned C05 scorer: **46 passed, 0 skipped**
  - enhanced V3T50 journey: **3 passed, 0 skipped**
  - Python 3.11.16
  - source SHA `3efcfc1126f849f595633ba02685bf4b64174550`
  - source tree `dad5e61cad840cb654d70019af934b4ef9145676`
- **C06 main-push run 35838888973:** success.
  - ordinary C06 selection: **72 passed, 1 skipped**
  - the skip is the separately opt-in >8 GiB case
  - separate long case: **1 passed**
  - long receipt: 1,500 decoded frames, 9,331,200,000 decoded bytes, bounded read buffer, child reaped
- **Main CI run 35838889060:** still in progress at report capture.
  - completed successfully so far: API profile, real-media, integration, excluded-backend, Python quality, macOS dependency dry-run
  - GPU acceptance: skipped by policy
  - still running at capture: canonical `verify` and `complete-backend`

The exact same code tree had a fully successful pre-merge canonical CI run; this report does not relabel that prior run as the post-merge run.

## Areas reviewed with no new blocking finding

- SQLite startup/schema migration transaction and its concurrent/rollback tests.
- Generation-pinned trust-crop backend reads and explicit historical selection behavior.
- Metre conversion and geometry-withholding behavior in the trust-crop scorer.
- Receipt leaf no-follow behavior, source/profile/selection binding, gate log hashing, and backend stub disclosure.
- Auxiliary-write logging: safe identifiers/type are logged without raw exception payload.
- V3T50 fresh-process recovery and fake post-dispatch billing reconciliation.
- Additive frontend trust-crop response schema and in-flight response cancellation.
- Post-merge C05/C06 source binding and no-paid-execution controls.

## Evidence-quality note

The C05 per-invocation receipts correctly record the merge commit/tree and retain repository/scorer bundles. Their working-tree `diffSha256` changes between test start and end because the workflow creates `.c05-evidence` and checks out `.deps/trackeval` inside the repository. This is expected artifact/dependency churn, not a product-source change, but it means the C05 `diffSha256` field is not itself a stable clean-source fingerprint. Keep using the commit/tree + bundles as authority, or move/exclude declared evidence roots if stable dirty-state comparison is desired.

## Ponytail / complexity review

No new runtime framework or dependency was introduced. The receipt implementation is larger, but the added complexity maps to real source/evidence and filesystem-safety requirements and reuses existing confinement/atomic-write primitives. I would not split it merely to reduce line count.

The only clear deletion-grade complexity is the retired branch names in workflow filters.

## Recommended order

1. Fix CR-01 before the next generation-aware UI change.
2. Broaden C06 trigger coverage (CR-02).
3. Scope TrustCropPanel saved state to generation (CR-03).
4. Remove retired branch filters and trailing whitespace (CR-04/CR-05).

After CR-01–CR-03, rerun the affected frontend tests/typecheck and C06 workflow contract/media lane. No backend architecture rewrite or new test framework is indicated by this review.

## Qualifications

This review is a code/integration review. It does not claim real-football model accuracy, representative full-match performance, real provider billing, GPU execution, macOS runtime qualification, browser E2E execution, or public-hosting/security certification.
