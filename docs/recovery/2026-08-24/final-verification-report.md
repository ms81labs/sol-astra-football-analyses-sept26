# Daytona worker recovery final verification

## Accepted release identities

- Source freeze (S6): `43c9c2e3e9d9260f6b7abb35fc979517b6e81e50`
- Release manifest commit (M6): `42f242b4c252ee40316c222d9967b35f67aab2a4`
- Pre-cloud evidence commit (E06): `d5a5d8ab828c84ac936cba26560c3554946cb9da`
- Final evidence and chronology commit: `5bac1b18ae0fbac3f1eb7e1fd194ab17c6a7b8c0`
- Manifest SHA-256: `62cd12f4db317507b55c45a805351ca610031d6817f2210bb84adc966603b192`
- Final-evidence SHA-256: `087d27d55ba3fde4eeed8a469d78437be8ad0c5348e8e16e19b86548b3f5d785`

Deploy preflight accepted the tracked final evidence for image tag `v7.3-43c9c2e3e9d9260f6b7abb35fc979517b6e81e50-62cd12f4db31`.

## Local verification

The SDK-ready Python environment imported `daytona==0.207.0`. With `VERIFY_DAYTONA=0` and `ALLOW_DAYTONA_MUTATION=0`, the final verifier passed: backend `2817 passed, 1 skipped`; sidecar `37 passed`; frontend `46 passed`; lint, both TypeScript checks, production build, and backend startup passed; manifest tests `129 passed`; runtime-option tests `67 passed`; preflight negative tests `105 passed, 33 deselected`; and the production audit found zero vulnerabilities. The operational-document suite passed `56` tests.

The verifier deliberately skipped the Daytona smoke. Its fresh receipt and logs remain under the designated untracked `.verification/` directory.

## Worker image runtime proof

The preserved local proof built image `sha256:b1b005d796d42d7c52f604cba78f3009f439a954f4caf8c249b815a436cf301d` from the immutable PyTorch/CUDA base. A network-isolated container reported no broken requirements, imported `boto3`, `cv2`, `numpy`, `pandas`, `pydantic`, `torch`, `ultralytics`, and the worker application modules, completed a CPU tensor check, and found no unresolved `ldd` dependency. It also proved `QT_QPA_PLATFORM=offscreen` and the installed `libgl1`, `libglib2.0-0`, and `libxcb1` packages. The successful remote execution bound worker-context SHA-256 `3dace1c8ef524894fc238eb26e4b000a0c0e300195149683195f19ffc2400e84`.

## Daytona attempt chronology

- Attempt 1 failed during image build. Its allocated sandbox was manually deleted and the independent listing returned zero.
- Attempt 2 failed during remote execution. The exact failed command was not recoverable after deletion; local reproduction identified missing OpenCV runtime libraries. The sandbox was deleted and the independent listing returned zero.
- Attempt 3 failed before allocation because the selected host Python could not import `daytona==0.207.0`. No sandbox existed and both listings were zero.
- Attempt 4 passed on 2026-09-10. It is the only successful attempt and completed gate 13.

The complete failure details and identifiers remain append-only in `docs/recovery/2026-08-24/daytona-gpu-smoke.md`.

## Remote execution and deletion

Attempt 4 used SDK `0.207.0`, target `us`, the immutable image `docker.io/pytorch/pytorch@sha256:417bd75df6365104c283ea4c1651fb3530d9eb5a4c2fafa51943cff2a94e6385`, and requested `RTX-PRO-6000` before `H100`. Daytona supplied `RTX-PRO-6000`. `nvidia-smi`, `worker-import`, and `bounded-fixture` all exited `0`; the bounded upload and both result downloads were hash-checked. Cleanup succeeded on its first attempt, deletion was confirmed, and the current independent `daytona list --format json` response contains zero sandboxes.

All 13 release gates passed. The final evidence records `runpodMutationOccurred: false` and `registryMutationOccurred: false`.

## Provider retirement and preserved data

Daytona is the sole active remote GPU provider and is limited to private, ephemeral execution. The application owns match upload and splitting, orchestration, durable football-analysis results, validation, analytics, persistence, and presentation. RunPod remains retired; historical readers and records are compatibility evidence, not an active provider path.

No RunPod image was pushed or deployed. No registry mutation occurred, no Git history was rewritten, and no model, video, dataset, application data, worktree, proof image, or failed-attempt record was deleted.

## Independent reviews

The final S6/M6/E06 chain passed independent specification and adversarial quality/security reviews with zero Critical, Important, or Minor findings. The final-evidence and Attempt 4 chronology commit also passed its task review with zero findings. The successful result's raw/canonical normalization was reviewed as acceptable under the release contract because gate 13 binds the canonical `RemoteExecution` input.

## Remaining operational action

Before any future capture, change the smoke CLI to emit canonical UTF-8 JSON directly. Attempt 4 originally produced a 1,956-byte escaped-Unicode serialization; the canonical writer input is 1,947 bytes with SHA-256 `41aa87816aa12200a621ed3a28218befefcdb36b9358c81bbb3e8036f9e70a43`. The runner-equivalent raw serialization was reconstructed afterward at mode `0600` with SHA-256 `e1742ddcd4567745a78ccef632b4e54fb1b0e30cdaaba5fd069230adef8951eb`; it was not independently preserved at capture. The two serializations were semantically identical.

Rotate the exposed testing Daytona key before production use. Also align the Daytona CLI with the API before a future provider operation; the read-only closeout listing warned that CLI `0.207.0` and API `0.213.0` differ.

## Code sweep 2026-09-10

This follow-up audit combines Ponytail's delete/simplify review with Superpowers' evidence-based correctness review. It extends the football-analysis roadmap; the recovery acceptance recorded above remains historical evidence for its exact source and smoke. Audited source: `16c0d3edca5cd651a3fa4622e63ae480c7f67966`, now integrated into `recovery-history-batch-current`.

The product objective is a reliable path from an uploaded football match through local preparation, Daytona GPU analysis, validated local persistence, and useful coaching views. The successful fourth smoke establishes GPU/runtime/transport readiness. It does not establish full-match processing, measurement accuracy, or production capacity.

### How the skills work together

1. Trace a user-visible operation and its actual callers before choosing work. Superpowers supplies the investigation and independent review; Ponytail asks whether the work is necessary.
2. Keep correctness findings separate from complexity findings. Preserve validation, credential containment, ownership checks, rollback, and cleanup even where those require substantial code.
3. Choose deletion first for proven unreachable code, then reuse an existing helper, then use the standard library. Do not add an audit framework, another orchestration layer, or a combined plugin.
4. For each behavior change, capture the failure in a focused test, make the smallest fix, and verify its real effect. Reuse the current tests and release tooling.
5. Run focused checks while changing a component and the required complete verifier at the release boundary. Repeat a broad suite only when a new change, failure, or release requirement justifies it.
6. Keep one ordered product backlog in `docs/status/current.md`, with this report as supporting evidence. Old design documents, batch-generated success flags, and test counts are not substitutes for a working match-analysis flow.

The audit itself changes documentation only. Recommended deletions and fixes below have not been applied. No provider operation or additional smoke was performed for this sweep.

### Coverage and measurement

The four review areas were application/analysis, Daytona/release, frontend/research, and scripts/tests/operations. Every tracked Python file was parsed; inventories and exact-function comparisons covered the whole tracked script tree. Reviewers traced selected high-risk runtime paths and callers. This is a repository-wide sweep with targeted deep inspection, not a claim that every line or every stored artifact was manually examined.

| Area at the audited commit | Files | Physical lines |
| --- | ---: | ---: |
| `backend/app` | 32 | 18,251 |
| `backend/scripts` | 309 | 118,659 |
| `backend/tests` including fixtures | 295 | 80,092 |
| `frontend/src` | 47 | 7,748 |
| `research-addon` | 12 | 1,261 |
| `docs/superpowers` | 106 | 19,341 |

There are 4,787 tracked paths and 654 tracked Python files. The table counts complete file contents, including comments and blank lines; it is not a unique-code or executable-lines metric. The separate 8,619-line `backend/run_guerilla.py` engine was inventoried and sampled at its processing boundary, not audited line by line. Its domain heuristics must be evaluated against football footage before removal.

The 3,839 tracked `backend/storage` paths total 130,926,148 bytes. These include reference and recovery material, so their size is not a deletion recommendation. Model weights, videos, datasets, accepted artifacts, existing worktrees, and prior smoke records remain outside the deletion list.

### Correctness and product findings

Severity describes the stated trigger and impact; it does not assert that the hosted application was exploited or that a failure occurred in the fourth smoke.

**F1 — High: match uploads are read entirely into API memory.** `backend/app/main.py:758` calls `await file.read()` before `backend/app/storage.py:347` saves the bytes. A large football recording therefore needs an additional in-memory copy before processing begins. Existing tiny upload fixtures do not establish full-match capacity. Stream into an owned temporary file in bounded chunks, enforce a configured size limit, and publish the completed upload only after success. Acceptance: bounded memory on a large synthetic stream, identical output bytes, and cleanup of a failed upload. Validate `inputMode` before writing anything as part of this boundary fix; currently `main.py:739` accepts any string and `processor.py:1052` rejects it only after records exist. A temporary-directory reproduction of `inputMode=typo` returned 202 with a failed match/job.

**F2 — High: a corrupt annotation/issue file is treated as empty, then overwritten.** `backend/app/storage.py:678` and `:716` catch all read, parse, and validation errors and return `[]`; the create/delete methods then write that list back. A temporary-directory reproduction showed malformed annotation JSON returning an empty list and being replaced by the next annotation. `_write_json` at `:584` also writes directly to the destination. Treat only an absent file as empty; surface and preserve corrupt data. Use the existing storage layer to publish JSON atomically, and verify read-modify-write concurrency separately. Acceptance: malformed annotations/issues remain unchanged with an explicit error, and an interrupted write retains the previous valid artifact. Keep the separate remote-import rollback protections.

**F3 — High: workflow output reset can delete an unintended directory.** `backend/scripts/football_external_real_eval_chain_common.py:55` calls `shutil.rmtree(path)` without an ownership/root check. There are 99 direct `reset_output` call sites in 99 scripts. The shared parser at `:113` accepts arbitrary candidate/output names; for example, `run_video_to_analysis_roadmap_state_reconciliation.py:232` joins the output name and deletes before reading its inputs. An absolute output name replaces the candidate prefix. Other scripts duplicate the deletion inline, including `run_football_external_benchmark_product_decision_surface_route_implementation.py:276`. This is a local operator/automation data-loss risk, not an established public API exploit. A fake-path probe recorded the deletion call without touching the filesystem. Fix the owning path/reset boundary, require containment and explicit ownership, reject absolute/parent/root targets, and validate inputs before replacement. Acceptance: sentinel input and unrelated directories survive invalid names, symlinks, missing inputs, and failed runs.

**F4 — High at season-sized datasets: opening the app fetches every ready match in full.** `frontend/src/App.tsx:194` loads all ready workspaces through one `Promise.all` at `:208`. `frontend/src/utils/api.ts:156` performs five requests per match, including all frames and analytics. One failed workspace rejects initialization for the entire list. Load list metadata first, then the selected/comparison match on demand, with per-match errors. Acceptance: 100 listed matches fetch artifacts only for the selected match, and one broken historical match does not prevent another from opening.

**F5 — Medium: local verification can use a different frontend installation from the lockfile.** The audited main checkout has Vite `7.3.1` versus locked `7.3.6`, and PostCSS `8.5.6` versus locked `8.5.26`. `scripts/verify.sh:103` runs whatever is already installed; receipt tool versions at `backend/scripts/write_verification_evidence.py:259` record only Python. CI already uses `npm ci --prefix frontend` at `.github/workflows/ci.yml:43`. Reuse that clean-install path for release verification, or fail early on an inconsistent installation. Acceptance: verify after a lock-consistent installation and reject a deliberately mismatched one. This finding does not assert a new vulnerability; a zero production audit does not prove installed build-tool parity.

**F6 — Medium: unattended continuation still chooses an obsolete checklist.** `backend/app/unattended_roadmap_loop.py:9` defaults to the April v6 plan. A read-only evaluation of its existing selector returns `v7_1_positive_diversity_manual_review_expansion_v2`, while the current objective is Daytona-backed product readiness. This helper selects/writes status; the audit does not claim it launched a job. Retire its active default or require the current checklist to be passed explicitly. Acceptance: default invocation cannot silently steer work back into the old training lane. Historical checklists stay archived.

**F7 — Medium: an uncertainty gap ending at the final frame is omitted from review crops.** `backend/app/trust_crops.py:94` only scores an open possession gap when a later assignment closes it. Twenty-five terminal `dead_ball` assignments produced zero crops; appending a controlled frame produced one. Finalize a qualifying open gap after the loop. Acceptance: paired middle-gap and terminal-gap tests with the same scoring semantics.

**F8 — Medium, already documented: successful smoke output is not canonical for Unicode.** `backend/scripts/run_daytona_gpu_smoke.py:394` uses the default escaped-Unicode JSON serializer while the evidence writer expects canonical UTF-8 bytes. The fourth attempt needed the explicitly recorded normalization above. Reuse the existing canonical serializer at the output boundary and add one Unicode regression check before any future capture. Do not rewrite the accepted fourth-attempt record or relabel it as a later source's GPU proof.

**F9 — High operational design gap: production job admission expires with release evidence.** `_build_execution_request` calls deploy preflight for every job at `backend/app/remote_worker.py:138`. `backend/release/preflight.py:1295` applies the 24-hour freshness limit from `backend/release/evidence.py:20` to the evidence, individual gates, and remote timestamps. Consequently, a release can stop admitting new jobs even when its code has not changed. The earliest relevant timestamp controls expiry, not simply the report's creation time. This is deliberate enforcement of the current design, not a guard to disable. Define a supported renewal/admission workflow in the next release design, preserving immutable acceptance evidence and all source/hash/cleanup checks. Acceptance: time-controlled tests establish useful operator diagnostics and an approved renewal path at T+24h; tampered or unrenewed evidence still fails before allocation.

**F10 — High integration defect: worker and importer support different result sizes.** `backend/app/gpu_worker.py:68` allows a processor artifact up to 1 GiB; the Daytona download path uses that ceiling. `backend/app/remote_worker.py:44` caps import at 64 MiB, then `:336` decodes the whole result into memory. A structurally valid 65 MiB worker result can be transferred and subsequently rejected by the application. Choose one measured supported envelope, then either implement bounded streaming/chunk import or have the producer reject output beyond the actual import limit before publication. Acceptance: the same maximum-size production-shaped artifact passes worker, transfer, and importer; maximum+1 fails at the earliest supported boundary. Raising an allocation limit alone is not a full-match solution.

**F11 — High acceptance gap: the production football path has not been proved by the live smoke.** `backend/scripts/run_daytona_gpu_smoke.py:35` creates a small job/match/status result with `python -c`; `:308` uploads only the request fixture. The live run does not invoke the production `gpu_worker`, decode a football video, or import its analysis into the app. The real path is implemented through `jobs.py:27`, `remote_worker.py:450`, the adapter, and `persist_remote_video_result`; important tests substitute the builder, transport, or importer (`backend/tests/test_remote_worker.py:174` and `:560`). Preserve the valid bounded smoke result and add a distinct product acceptance test: a short real football clip uploaded through the API must run the actual sealed worker, return a validated generation, reach ready/completed, and expose frames, analytics, and events in the UI. Then measure a representative full match. The current upload/job flow passes one input video per job; a resumable split-and-reassemble match scheduler is not established by that flow or its smoke. Decide the smallest required chunking scheme from measured limits and test timestamp/player continuity at boundaries.

**F12 — Medium: frequent UI polling does not provide live GPU progress.** `frontend/src/utils/api.ts:201` polls every 250 ms for up to an hour and discards intermediate job messages. That is roughly 14,400 polls at negligible request latency. `backend/app/remote_worker.py:444` reports 5% before a blocking execution and 90% after it returns; `gpu_worker.py:1254` collects progress in memory and writes it after processing at `:1379`. The execution policy is fixed at 1,800 seconds (`backend/release/daytona_policy.py:144`). Reuse slower polling with an update callback or the existing `/ws/jobs/{job_id}` channel, and add a bounded host-visible worker heartbeat if required. Changing the UI transport alone does not make buffered GPU progress live. Acceptance: visible in-progress state before completion, bounded request rate, terminal errors, and measured runtime/headroom for representative footage.

**F13 — High for user-entered work: failed note/issue saves clear the input.** `frontend/src/features/review/useReviewSurface.ts:150` and `:172` catch persistence errors and return `null`; `ReviewToolbar.tsx:11` and `DemoMatchIssuePanel.tsx:126` clear the text immediately without awaiting success. Keep the draft until an acknowledged save, surface the failure, and allow retry. Acceptance: rejected annotation and issue POSTs preserve typed text and never show a successful submission state. Combine with F2 to protect both frontend drafts and stored coaching notes.

**F14 — Medium: the coaching panel starts on a tab that is never rendered.** `frontend/src/hooks/useCoachAnalysis.ts:74` defaults to `'events'`; `frontend/src/App.tsx:854` and `:868` render only analysis/report/drills. Startup loading does not reset this tab. Default to an existing tab and remove the dead variant. Acceptance: opening an existing processed match immediately displays coaching content without an extra tab click.

**F15 — Medium: UI capabilities and processing provenance are hard-coded.** `frontend/src/App.tsx:118` never updates local-only capabilities, its Cloud LLM button is always selectable at `:845`, and issue records use `processingBackend="unknown"` at `:944`. The empty state also says "Process Locally" at `:626`. Use safe backend capability information and actual job provenance; gate the existing Cloud control on supported LLM configuration. Daytona GPU execution and Cloud LLM analysis are separate choices and must not be conflated. Acceptance: the UI accurately describes the configured processing backend without exposing secrets, and an unavailable LLM provider is not selectable.

**F16 — Medium packaging gap requiring an isolated runtime check: the local tracker shim is checkout-dependent.** `lap.py:13` depends on NumPy/SciPy, but `pyproject.toml:21` discovers only `backend*`; the root shim is not declared as a packaged module. SciPy is supplied by ML/dev requirements, not the minimal API package. The worker Dockerfile likewise copies only `backend`. This proves a packaging gap, not that every environment fails: an installed upstream `lap` could satisfy tracking instead. Choose one explicit tracker dependency strategy and test an actual tracking invocation from the installed package/worker outside the repository with network access disabled. Avoid adding both a fallback shim and a second tracker package without a demonstrated need.

### Ponytail simplification findings

Ranked by demonstrated potential reduction. Savings are estimates for future patches, not deletions already performed. Exact duplicate detection used Python ASTs with location fields excluded; different loader error contracts were kept separate.

- **C1 — `delete:`** remove unreachable tails after the retirement guard in 38 functions across 13 historical recipes: **3,880 physical lines**. Keep signatures, fail-closed guards, compatibility renderers, and independently consumed helpers. Evidence: `backend/scripts/runpod_session.py:12` always raises; examples include `run_touchline_detector_candidate_training.py:545`, `run_touchline_detector_candidate_model_data_quality_fix.py:1263`, and `run_detector_breadth_batch.py:593`. `backend/tests/test_operational_docs.py:24` enumerates all 13 recipes and tests their rejection behavior. Preserve historical implementations through the existing Git history; check recipe exports before deleting anything beyond the guarded tails.
- **C2 — `shrink:`** replace 97 identical seven-line `_load_json` definitions with aliases to the already equivalent `football_external_real_eval_chain_common.load_json` at `:46`. AST comparison confirmed identical definitions after normalizing only the function name. Example copy: `run_football_external_benchmark_harness_prep.py:43`. Removing 679 definition lines and adding 97 one-line imports gives an estimated **582-line net reduction**. Keep missing-file, non-object, malformed-JSON, and encoding behavior unchanged; do not merge the other loader variants blindly.
- **C3 — `shrink:`** consolidate the repeated saved-report loaders in `backend/app/main.py:281` through a small existing-pattern helper/binding table. The repeated loader and route regions total 401 physical lines; this is a review target, not a claimed net deletion. Retain explicit routes where they aid introspection and keep every route's contract checks and error behavior. Avoid building a generic report framework.
- **C4 — `delete:`** remove the unused search-schema block at `backend/app/schemas.py:234` through `:299`: **66 lines**. Symbol searches found no consumers outside that block; search endpoints currently return dictionaries. Keep the implemented search behavior and run its API tests.
- **C5 — `delete:`** remove the first all-zero `eventTypes` construction at `backend/app/processor.py:893`: **7 lines**. It is overwritten unconditionally at `:903` by actual counts. Preserve trace output with the processor tests.
- **C6 — `shrink:`** import the existing `TacticalReport`/`DrillResponse` types from `frontend/src/types/index.ts:479`, remove their duplicates in `hooks/useCoachAnalysis.ts:8`, and remove the unused `resetReviewSurface` callback/export in `features/review/useReviewSurface.ts:55`. Together with F14's dead tab variant, the conservative estimated reduction is **about 43 lines**. Keep the actual review/analysis state reset behavior and its consumers.
- **C7 — `delete:`** remove three unused direct dependency declarations from `frontend/package.json`: `@testing-library/jest-dom`, `autoprefixer`, and direct `postcss`. No source imports, custom matchers, or PostCSS configuration were found; Tailwind is integrated through its Vite plugin. Regenerate the lockfile and verify tests/build before accepting the deletion. PostCSS remains a Vite transitive dependency; do not claim three installed packages disappear. There are two package-removal candidates and three direct declarations to cut.

Higher-risk simplifications belong in a later protocol change, not the immediate deletion patch:

- **C8 — `delete/shrink:`** eliminate the per-job source archive if the worker's executed source remains independently bound to the accepted worker image/context. `backend/app/remote_worker.py:151` builds a full source tar and `:201` includes it in every job. The worker verifies its bytes but does not unpack or execute it; manifest/evidence/runtime artifacts are also transferred separately. The review measured **149,432,320 bytes** from `git archive` at the frozen source before artifact injection. `JobReceipt` currently requires `source_archive` (`remote_contracts.py:563`), so removal requires a versioned contract change and tamper tests, not merely skipping the upload. This is a transfer-volume opportunity, excluded from line savings.
- **C9 — `shrink:`** reuse one explicit mapping/iterator for the five runtime artifact references across `runtime_options.py:21`, `release_manifest.py:298`, `gpu_worker.py:1141`, and local materialization. Do not confuse scalar options with artifact fields. Acceptance: a reference is consistently enumerated, manifest-validated, and materialized on both local and remote paths; unknown/unsealed references still fail.

The 1,261-line research sidecar is optional product scope, not proven dead code. Its current consumers include verification and the research-bundle builder. Keep it while supported-coverage research is required; reconsider it as a whole only when that requirement is retired. The three review UIs also have distinct server-script callers and are not deletion candidates merely because they look similar.

Additional measured duplication, excluded from the net estimate: 57 identical `_safe_int` helpers and 39 `_safe_float` helpers contain 658 excess definition lines before replacement imports. Preserve the bool/nonfinite/error semantics and prove caller compatibility before consolidation. Likewise, the 309 workflow scripts are not all dead: several feed current API reports, and shared helpers still serve active consumers. Review dependency groups before archiving entire script families.

**net: approximately -4,578 lines, -3 direct dependency declarations possible.** This combines C1/C2/C4/C5/C6 and excludes the unquantified route/protocol changes, optional sidecar retirement, test cleanup, and transitive dependency effects. It does not measure reclaimed disk space or faster GPU analysis.

### Backlog merged into the football-analysis objective

These are ordered implementation batches, not completed work or a new automatic cloud-run authorization. Each batch needs its smallest behavioral acceptance check and review. Batch 1 can run locally; prepare later batches locally before considering paid execution.

| Order | Work tied to findings | Done when |
| --- | --- | --- |
| 1 | Protect coaching data and workflow outputs: F2, F3, F13 | Corrupt files and failed saves retain data; invalid output targets cannot delete input/unrelated data; focused failure tests pass. |
| 2 | Make the supported input/output envelope explicit: F1, F10, F12, F16 | Uploads stream with a limit; worker/importer agree on result size; installed tracking works offline; progress and timeout behavior are measured. |
| 3 | Prepare the next release and admission lifecycle: F5, F8, F9 | Lock-consistent verification, canonical capture bytes, preserved old acceptance evidence, and an explicit tested policy for evidence renewal. |
| 4 | Prove one real clip through the product, then representative match/chunk behavior: F11 | API upload runs the real worker, imports the committed generation, shows useful frames/events/analytics, and confirms cleanup; capacity and accuracy limits are recorded. |
| 5 | Make the coaching workspace dependable: F4, F7, F14, F15 | Lazy match loading, visible supported controls, usable initial panel, and complete uncertainty review including final frames. |
| 6 | Delete proven waste in small reviewed patches: C1, C2, C4-C7; fix F6 | Measured reductions land without changing contracts or reviving retired execution; the current checklist is explicit. |
| Later | C3, C8, C9; optional research retirement | Benefits are measured and route/protocol consumers and evidence bindings are preserved. |

After batches 1-3, the next meaningful product checkpoint is a short football clip through the actual application. A fresh source/manifest/evidence chain is required for runtime changes; an old GPU success must not be reused as proof of changed worker code. Keep the same lifecycle and cleanup controls. The broader Catapult-like aim additionally needs representative accuracy checks for calibration, player/ball tracking, event quality, and any claimed physical metrics.

The report is appended to an already permitted release-document path, and the backlog is linked from `docs/status/current.md`. This respects the existing metadata allowlist (`backend/release/preflight.py:50`) without weakening source integrity or starting another design-document chain. No installed Ponytail or Superpowers plugin was modified.

### Evidence and limits of the sweep

- All 654 tracked Python files parsed successfully. The inventory, duplicate-function comparison, and retirement-tail counts were computed against Git-tracked paths only.
- All 12 log hashes in the existing verifier receipt were independently checked. It binds source `16c0d3ed` and was created at `2026-09-10T11:19:41.457131Z`; its backend result is `2818 passed`. These are preserved prior-run results, not a new full-suite run performed by this audit.
- The application reviewer ran the existing annotation and trust-crop suites: **22 passed**. The corrupt-annotation, invalid-mode, and terminal-gap probes demonstrate cases those green tests do not cover.
- After integrating the report, the controller ran the operational-document, annotation, and trust-crop suites together: **78 passed in 26.24 seconds**. The prior acceptance report remains byte-for-byte intact as the prefix of this document.
- The script-deletion probe used an extracted function with fake filesystem objects. No workflow was launched and no directory was deleted.
- Dependency parity was checked from installed `package.json` files and the tracked lockfile, without an installation or network lookup.
- Additional local probes confirmed that evidence at creation+86,401 seconds is rejected, a 65 MiB result lies between the producer and importer limits, and a Unicode CLI result differs from canonical bytes. Streaming `git archive` to a byte counter independently confirmed the 149,432,320-byte source archive. No provider was involved.

Frontend findings are based on source/caller review; no interactive browser journey was run. This sweep does not certify full-match accuracy, multi-user load, GPU cost, long-recording capacity, or every research heuristic. Those require representative footage and measured acceptance criteria. It also makes no fresh claim about the Daytona account inventory; the last recorded zero-sandbox evidence remains the recovery evidence above.
