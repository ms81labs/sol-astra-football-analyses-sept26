# Guerilla Analytics — Post-Remediation Code Audit v3.0

**Review of H01–H07 implementation, B01–B35 disposition, production-path integration and current CI evidence**

**Repository:** `ms81labs/sol-astra-football-analyses-sept26`  
**Reviewed main:** `b3fbe78c51f9a30891e939b610fa292da7f05bf9`  
**Previous audit baseline:** `d881d1eaf7a0898897bd9a1a1ae46306606c904d`  
**Review date:** 18 September 2026  
**Changes made by this review:** none to the repository, deployments, model providers or paid workers.

> **Decision: the hardening programme has produced substantial real improvements. Do not roll it back. However, “all phases implemented” is not yet equivalent to “all closure conditions satisfied.” This review identifies ten focused follow-up items, with explicit scope and tests. It does not reopen all 35 original findings or propose another architecture rewrite.**

## 1. Executive assessment

The current code is materially better than the prior audited revision. There is a shared review service, a durable correction lifecycle, generation-based output publication, transactional job admission, leases and conditional transitions, a provider gateway, stronger calibration/scoring checks, layered cache identities, bounded hashing, a substantially improved FFmpeg reader and multiple CI profiles. The main ref was rechecked at the end of source inspection and still pointed to the reviewed commit. The comparison with the old baseline reports 32 commits ahead. [S01–S05, S07–S17, S23–S28]

The strongest old counterexamples have received targeted work. Missing homographies no longer obtain a convenient zero residual. Reordering holdouts is covered by the 40-point regression. Wrong-class detections cannot receive player true-positive credit. Team shot-quality values are separately scoped. The raw-row-backed team swap now has a process-level regression instead of being tested only on a tracking-JSON substitute. The provider route enforces match cloud permission rather than merely accepting a requested provider name. [S02, S05, S10–S11, S17, S26–S27]

**The remaining weakness is cross-component consistency.** Some operations publish one generation while other readers use mutable side artifacts. A read can prune previously published generations. Accepted calibration metadata is not consistently applied to video coordinates. Identity approval can survive a later identity-changing edit in one consumer but not another. Returned model references still have a validation hole. Public cost summaries disagree with the richer job receipt about unknown spend. The FFmpeg challenger’s default work limits do not describe a full-match envelope. [S02–S07, S14–S15]

These are not reasons to abandon Python, install another model or restart the project. They are reasons to complete one more deliberately bounded integration pass, supported by the tests in this report.

### Practical release disposition

| Use | Decision at this snapshot |
|---|---|
| Local development and controlled evaluation on permitted data | Continue. Preserve backups and the reviewed commit. |
| Routine analyst edits where historical snapshots and reports must remain dependable | Do not give final sign-off before R01–R05 pass. |
| Physical statistics after a new calibration or identity repair | Withhold from authoritative publication until the real video and identity paths in R03–R04 are correct. |
| Optional cloud assistance | Consent gating is improved; keep publication and spending claims limited until R06–R07 are resolved. |
| Unattended paid execution | Do not use an `actualTotal=0` cost response as evidence of zero exposure. Require consistent unsettled-cost handling and provider reconciliation. |
| FFmpeg as the default full-match decoder | Not yet qualified with the present defaults; R09 applies specifically to this challenger. |
| Public multi-tenant hosting | Requires its own deployment/security acceptance, even though new authentication wiring exists. |
| Claims of football accuracy or professional analyst acceptance | No new independent accuracy or analyst result was verified in this review. |

## 2. What was actually checked

The attached v2 report supplied the original IDs, seven work packages and closure criteria. Current code was then read through the connected GitHub source at one pinned revision. This included the review service, generation storage, processing/reprocessing, provider gateway and adapters, job ledger, calibration, domain schemas, metrics, media/identity helpers, perception/scoring, typed search, evaluation, training and CI definitions. Selected frontend workbench API calls and types were inspected for integration. Relevant new regression tests were read. [S01–S32]

This is a **risk-based, cross-component source audit**, not a claim that every historical script, test or frontend line was individually reviewed. Older source-bound remote-worker code was not exhaustively re-audited. A fresh full local checkout could not be obtained through the available direct network/archive path; source access through the connector worked. Consequently, this review did not run the repository’s full pytest suite or start the application/browser locally.

There is nevertheless stronger execution evidence than in the original audit: the actual CI artifact archives for the reviewed commit were downloaded and inspected. Their receipts and logs are included in the evidence pack. Six additional isolated checks executed the transcribed provider-validation function bodies; these are explicitly not full repository/API reproductions.

### Evidence terminology

**Source-supported defect** means the relevant implementation/call path is visible at the pinned commit. **Conditional failure** means a specific concurrency, crash or operating-envelope condition is required, and no production incident is alleged. **CI-observed** means the downloaded GitHub artifact reports the result at this commit; it is not a local rerun by this reviewer. **Isolated check** means only the stated source excerpts and simple fixtures ran. **Verification gate** means the relevant acceptance evidence remains missing; it is not necessarily a remaining coding bug.

## 3. Current CI evidence — independent of the closure prose

Reviewed GitHub run: **35391149730**, source **b3fbe78c…**. Three artifact archives were downloaded: `verify-evidence`, `integration-evidence` and `real-media-evidence`.

| Lane/check | Evidence inspected | Result | Qualification |
|---|---|---|---|
| Backend code-only | Receipt plus backend log | **3,433 passed; 4 skipped** | Receipt records the Ultralytics stub as active. |
| Research sidecar | Receipt plus sidecar log | **100 passed** | A software test result, not a football benchmark. |
| Frontend | Receipt plus test log | **370 passed** | Component/unit tests; no live end-to-end analyst session was run by this review. |
| Lint, two TypeScript checks, frontend build, backend startup, production npm audit | Verification logs and receipt | **Passed** | Does not establish Python dependency security or ML accuracy. |
| Integration | Downloaded receipt and log | **11 passed; 1 skipped** | Marker selection is `integration or real_media`; Ultralytics stub active. |
| Generated real media | Downloaded receipt and log | **3 passed; 1 skipped** | Actual FFmpeg is exercised; the pipeline receipt test uses a detector spy. |
| API profile | CI job metadata plus workflow definition | **Success** | Actual locked install and app import with Ultralytics absent. |
| macOS profile | CI job metadata plus workflow definition | **Success** | `pip --dry-run` dependency resolution, not a macOS installation/video run. |
| GPU acceptance | Workflow definition / reviewed automatic run | **Not executed in this run** | Separate manually approved self-hosted lane. |

**Do not add the integration and real-media counts together as independent tests.** The integration selector includes real-media tests. Also, do not describe a real FFmpeg test with a detector spy as end-to-end football perception. It usefully tests decoding and telemetry plumbing, but not learned ball/player accuracy. [S25, S28–S29; CI artifacts in the evidence pack]

The repository’s closure document lists another verification source (`9ac36856…`) and different counts. Its local statement that no stubs were active is not evidence that the current hosted CI used real Ultralytics. The downloaded current receipts explicitly name `ultralytics` under `stubsActive`. These are different environments/results; the source and profile should always accompany a count. [S01, S25]

The conditional GPU smoke checks CUDA availability and a tensor allocation. The optional workflow also selects existing worker/core/evaluation test files, but a job name or test-file selection is not a substitute for retained source-bound inference, label and scorer artifacts. No such current football-accuracy evidence was supplied to this review. [S25, S29]

## 4. H01–H07 disposition

| Work package | What is genuinely implemented | Why final acceptance remains qualified |
|---|---|---|
| **H01 — provider/deployment policy** | Provider gateway, permission checks, model allowlist, reservations, server-owned deployment settings, authentication middleware and deterministic incident routing. | Returned-reference hole, incomplete generation binding and billed-cost assurance; deployment isolation still needs live qualification. |
| **H02 — corrections/review** | Shared service, retired duplicate authorities, command states, locks, replay over base observations, generation publication and raw-row/process tests. | Generation retention/read races, publication crash boundary, compound config/identity changes and stale side artifacts. |
| **H03 — calibration/metrics** | Invalid/missing matrix checks, paired residuals, minimum holdout support, unified revision concept, team-scoped metrics, finite fields and improved scoring. | Video recalibration does not consistently transform the coordinates being published; approval invalidation and coordinate spaces remain problematic. |
| **H04 — jobs/budgets** | SQLite is now authoritative for transitions; leases, revisions, idempotent submit/retry distinction and separate charge states exist. | Cost response surfaces do not consistently distinguish settled-only cost from total actual cost. Remote/provider billing needs explicit evidence. |
| **H05 — recompute/receipts/search** | Planner/executor distinction, generation receipts, layered identities, preserved producer counts and stricter typed queries. | A changed generation is not proof of correct video reprojection; recovery/cache dependencies and evaluation acceptance semantics remain incomplete. |
| **H06 — media/adapters** | Streaming hashes, shared executable resolver, concurrent stderr parsing, cancellation, integer PTS/rational time bases, real pixel preprocessing and separate CUDA capabilities. | Short generated tests do not establish full-match work limits, all process-entry isolation or arbitrary-source timing behaviour. |
| **H07 — evidence/environments** | Locked profiles, API/macOS/integration/media/GPU workflow definitions, artifact upload and better training metadata. | Actual GPU/football/analyst acceptance is missing; macOS proof is a dry-run; exact chosen-checkpoint metrics need retained training artifacts. |

All seven have received implementation work. It would be inaccurate to call them empty placeholders. It is also inaccurate to use the existence of those implementations as blanket closure of every end-to-end invariant.

## 5. Original B01–B35 disposition register

**A — original source-level counterexample addressed in the inspected implementation.** This is not a claim of independent reproduction of every baseline failure and fixed pass.  
**P — partial: a material fix exists, but a remaining path or contract prevents full sign-off.**  
**R — competing/broken interface safely retired, with a supported replacement.**  
**V — implementation/evidence infrastructure exists; platform or release acceptance remains outstanding.**

There is deliberately no percentage labelled “professional-ready.” These statuses are about the specific original finding and its supported scope.

| ID | Disposition | Current assessment | Evidence |
|---|---|---|---|
| B01 | **R** | **Competing authorities retired.** Old workbench operations return a retired-route response; normal match services and frontend query/correction URLs are used. This is safe retirement, not completion of the old implementation. | [S23](#appendix-a--pinned-source-register), [S26](#appendix-a--pinned-source-register), [S30](#appendix-a--pinned-source-register) |
| B02 | **P** | **Recoverable commands added; atomicity incomplete.** Commands, locks and generation publication are substantial fixes. Retention/read races and the database/pointer crash boundary remain (R01–R02). | [S02](#appendix-a--pinned-source-register), [S03](#appendix-a--pinned-source-register), [S26](#appendix-a--pinned-source-register) |
| B03 | **P** | **Reviewed metrics rebuilt; stale outputs remain.** Accepted/rejected events now feed regenerated shots/metrics. Stored narratives and auxiliary match-state artifacts are not fully generation-bound (R05). | [S02](#appendix-a--pinned-source-register), [S03](#appendix-a--pinned-source-register), [S23](#appendix-a--pinned-source-register), [S26](#appendix-a--pinned-source-register) |
| B04 | **P** | **Original raw-row swap fixed; edit composition incomplete.** The raw-row-backed same-request regression has a real-process test. Later config changes, identity approval invalidation and compound edit paths still need R04. | [S02](#appendix-a--pinned-source-register), [S04](#appendix-a--pinned-source-register), [S26](#appendix-a--pinned-source-register) |
| B05 | **A** | **Missing/invalid transform false acceptance addressed.** Missing matrix, shape, singularity and non-finite cases are checked. This is calibration validation logic, not measured camera accuracy. | [S11](#appendix-a--pinned-source-register), [S13](#appendix-a--pinned-source-register), [S27](#appendix-a--pinned-source-register) |
| B06 | **A** | **Landmark/residual pairing addressed.** Region statistics preserve landmark associations; the 40-holdout reordering regression is present. | [S11](#appendix-a--pinned-source-register), [S27](#appendix-a--pinned-source-register) |
| B07 | **P** | **Unified revision exists; downstream use incomplete.** Physical publication checks identity and calibration, but video reprojection and identity-review invalidation remain inconsistent (R03–R04). | [S02](#appendix-a--pinned-source-register), [S03](#appendix-a--pinned-source-register), [S04](#appendix-a--pinned-source-register), [S10](#appendix-a--pinned-source-register) |
| B08 | **P** | **Plan/execution split implemented.** Execution publishes a generation and checks cache presence. A new generation ID alone does not prove video coordinates were recalibrated (R03). | [S03](#appendix-a--pinned-source-register), [S04](#appendix-a--pinned-source-register), [S28](#appendix-a--pinned-source-register) |
| B09 | **P** | **Layered identities added.** Real primary-weight/source identities replace several placeholders. Recovery, runtime configuration and artifact-scope dependencies remain incomplete (R08). | [S15](#appendix-a--pinned-source-register), [S16](#appendix-a--pinned-source-register), [S28](#appendix-a--pinned-source-register) |
| B10 | **A** | **Ordinary resubmission no longer substitutes for retry.** Transactional admission distinguishes replay/retry and rejects unknown outcomes. This does not by itself certify remote billing. | [S14](#appendix-a--pinned-source-register), [S23](#appendix-a--pinned-source-register) |
| B11 | **A** | **Authoritative database transitions implemented.** Live database reads, conditional revisions and leases replace full-cache rewrites and constructor abandonment. Generation storage has separate remaining issues. | [S14](#appendix-a--pinned-source-register) |
| B12 | **P** | **Accounting model improved; public semantics inconsistent.** Receipt represents unsettled cost, while cost_for/cost_summary publish settled-only totals as actualTotal (R07). | [S14](#appendix-a--pinned-source-register), [S23](#appendix-a--pinned-source-register), [S30](#appendix-a--pinned-source-register) |
| B13 | **P** | **Consent/provider bypass addressed; cost assurance incomplete.** Normal analysis now uses the gateway. Static reservations do not establish a billed-cost ceiling without bounded usage and settlement (R07). | [S05](#appendix-a--pinned-source-register), [S06](#appendix-a--pinned-source-register), [S23](#appendix-a--pinned-source-register), [S24](#appendix-a--pinned-source-register) |
| B14 | **P** | **Returned-output validation added but bypassable.** Unrecognised reference formats are ignored and missing evidence can still be labelled grounded; generation scoping is incomplete (R06). | [S05](#appendix-a--pinned-source-register), [S19](#appendix-a--pinned-source-register) |
| B15 | **A** | **LLM removed from authoritative geometry path.** Legacy analysis routing now uses deterministic review geometry for spacing/offside-type requests. It remains a review aid, not an officiating product. | [S11](#appendix-a--pinned-source-register), [S23](#appendix-a--pinned-source-register) |
| B16 | **A** | **Whole-file hashing replaced in inspected media paths.** Chunked hashing and a metadata-validated cache are implemented; injected-frame probe reads one byte, not the whole file. | [S07](#appendix-a--pinned-source-register), [S08](#appendix-a--pinned-source-register) |
| B17 | **P** | **Old pipe hazard repaired; full-match envelope not qualified.** Concurrent stderr handling, cancellation and exit checks exist. Cumulative raw-output and whole-iterator timeout defaults restrict long clips (R09). | [S07](#appendix-a--pinned-source-register) |
| B18 | **A** | **Producer telemetry preserved.** Wrapper validates and retains actual counters/anchors instead of overwriting them with a fresh audit. Generated-media plumbing tests use a detector spy. | [S15](#appendix-a--pinned-source-register), [S28](#appendix-a--pinned-source-register) |
| B19 | **A** | **Original timestamp arithmetic defects addressed.** Canonical export rounding is removed; integer PTS/rational time bases and explicit grid-origin options exist. This does not certify every VFR/rotation/camera stream. | [S07](#appendix-a--pinned-source-register) |
| B20 | **A** | **Executable adapter path and original IDs supported.** A real pixel-transform implementation exists and wrapper tracks retain source Track_ID values. Legacy metadata helpers are not proof of acceleration. | [S15](#appendix-a--pinned-source-register), [S17](#appendix-a--pinned-source-register) |
| B21 | **A** | **Decoder and inference capabilities separated.** CUDA inference is selected independently of hardware video-decoder availability. Actual GPU throughput remains unmeasured here. | [S17](#appendix-a--pinned-source-register) |
| B22 | **A** | **Wrong-class matching and pixel-error defect addressed.** Predictions are task-class filtered; pixel centre offset and dimensionless IoU diagnostics are separate. | [S17](#appendix-a--pinned-source-register), [S27](#appendix-a--pinned-source-register) |
| B23 | **A** | **Team-scoped shot-quality contract implemented.** Distinct team sums replace the ambiguous aggregate; regression covers separate values and exports. Heuristic scores remain uncalibrated. | [S10](#appendix-a--pinned-source-register), [S27](#appendix-a--pinned-source-register) |
| B24 | **P** | **Metric definitions/eligibility improved.** Time-weighted possession, physical prerequisites and team scopes are improved. Period/configuration propagation and camera/identity eligibility still need qualification (R03–R04). | [S02](#appendix-a--pinned-source-register), [S10](#appendix-a--pinned-source-register), [S12](#appendix-a--pinned-source-register), [S23](#appendix-a--pinned-source-register) |
| B25 | **A** | **Original unknown-filter relaxation addressed.** Exact team/period matching and structured successors replace permissive matching; interpretation/unsupported-term metadata is exposed. UI contract coverage remains needed. | [S18](#appendix-a--pinned-source-register), [S30](#appendix-a--pinned-source-register) |
| B26 | **V** | **Hosted controls added, deployment not accepted.** Server-side mode validation and authentication middleware are now wired. No live multi-tenant deployment or security assessment was performed. | [S23](#appendix-a--pinned-source-register), [S24](#appendix-a--pinned-source-register) |
| B27 | **P** | **Some real process controls; not a complete isolation boundary.** Decoder path has protocol/resource controls. The proxy helper still has a separate ordinary subprocess path; actual filesystem/network containment is not certified (R09). | [S07](#appendix-a--pinned-source-register), [S24](#appendix-a--pinned-source-register) |
| B28 | **P** | **Core domain checks strengthened, not fully consolidated.** Finite coordinates, period ordering and matrix validation exist; some canonical quantities remain plain floats and coordinate-space meaning is not explicit everywhere (R03). | [S12](#appendix-a--pinned-source-register), [S13](#appendix-a--pinned-source-register) |
| B29 | **P** | **Readiness states improved, acceptance still overstated.** Absent manifest now means unknown; null scores do not become scored. Result metadata is still not verified artifact replay or threshold acceptance (R10). | [S20](#appendix-a--pinned-source-register) |
| B30 | **P** | **Training defaults and joint metric selection improved.** YAML parsing and model defaults are unified; joint epoch metrics are separated from diagnostic maxima. Exact checkpoint and split-quality acceptance still require real artifacts. | [S21](#appendix-a--pinned-source-register), [S22](#appendix-a--pinned-source-register) |
| B31 | **V** | **Locked profiles exist; evidence differs by platform.** API install/startup passed; macOS job is a resolution dry-run; CUDA lane was not executed in the reviewed automatic run. | [S25](#appendix-a--pinned-source-register) |
| B32 | **V** | **CI lanes implemented; football acceptance not established.** Current logs prove software/integration/generated-media checks. They do not prove independent football accuracy or analyst acceptance. | [S25](#appendix-a--pinned-source-register), [S28](#appendix-a--pinned-source-register), [S29](#appendix-a--pinned-source-register) |
| B33 | **A** | **Invented unit-square calibration rejected.** The regression calls the public storage calibration path with missing/malformed source points and verifies no calibration commit. | [S27](#appendix-a--pinned-source-register) |
| B34 | **A** | **Executable resolution centralised.** Approved absolute executable resolution is supported through one resolver. Actual installation layouts and trust policy must be tested on each supported platform. | [S07](#appendix-a--pinned-source-register), [S09](#appendix-a--pinned-source-register) |
| B35 | **R** | **Broken workbench admission retired; normal conflicts mapped.** Retired route returns 410; active normal service maps typed idempotency conflicts to 409. | [S23](#appendix-a--pinned-source-register), [S26](#appendix-a--pinned-source-register) |


## 6. Focused follow-up findings

The R identifiers below are **follow-up groups**, not another independent set to add arithmetically to the 35 original IDs. Several cover different residual symptoms of one cross-component boundary. Priorities apply to the affected workflow: a P1 for publishing measurements is not a claim of an immediate breach of a local development machine.

### R01 — Reading current state deletes published generations and does not pin all readers

**Priority:** P1 for reliable review/history. **Related:** B02, B04, B08.  
**Locations:** `Storage._current_generation_unlocked`, `_complete_generations`, `_generation_payload_path`; snapshot consumers in `main.py`. [S03, S23]

`_current_generation_unlocked()` validates available generations, resolves a current reference and writes the pointer. It then protects only the selected generation and certain `appliedGeneration` references belonging to commands still in `applying`. It recursively deletes every other `gen_*` directory. A previously published generation belonging to an already `applied` correction is not protected merely because it is recorded in history.

This is not just cleanup of incomplete temporary work. It removes complete older output snapshots on an ordinary read. The original video and correction log are not deleted by this loop, and some state can be reconstructed by replay, but historical generation IDs, evidence references and rollback targets can lose their materialisation.

Separately, a reader can resolve a generation path under the lock and open the file after that lock has been released. A concurrent writer/read that publishes/prunes can remove the chosen directory in between. Some composite consumers also release a snapshot before reading all its artifacts. This creates a source-supported race; no production occurrence was reproduced here.

**Required repair:** make ordinary reads non-destructive. Retain published generations according to a separate explicit policy, preserve referenced generations, and pin the complete read lifetime or use immutable handles/reference leases. Recovery should distinguish unpublished incomplete staging directories from valid historical snapshots. Move garbage collection out of read resolution.

**Regression:** read generation N while another process publishes N+1; both readers finish consistently. Reopen a generation referenced by an applied correction. Verify no automatic read removes it. Exercise explicit retention only after readers/references are released. Instrument reads so they do not repeatedly hash/rewrite/delete unrelated generations.

### R02 — Generation publication does not atomically reconcile database, pointer and auxiliary state

**Priority:** P1 for crash consistency. **Related:** B02, B03, B07–B08.  
**Locations:** `Storage._publish_generation_unlocked`, `_publish_replacement`; `ReviewService.rebuild_generation`; processing persistence. [S02–S04]

The publisher writes and flushes a new directory and manifest, then commits `matches.analytics_summary_json` to SQLite **before** publishing `current_generation.json`. A fault-injection point exists precisely between those operations. The exception handler can restore the database summary for a Python exception while writing the pointer; it does not run after `os._exit` or an external process kill.

When the old pointer remains valid, generation resolution keeps it and can delete the new complete directory under R01. That alone does not reconcile the database summary. Pending correction replay can repair some review-command crash cases; it does not prove all direct worker/publisher cases recover. Test a publication without a pending correction so that repair is not accidentally supplied by an unrelated outbox.

The review service also changes effective configuration and calibration state before it publishes the generation. Only Python exception handling restores them. A legacy replacement publication does not preserve every original manifest field by default. Finally, the generated directory includes frames/events/analytics/shots/summary but not every auxiliary state consumed elsewhere.

**Required repair:** select one authoritative active-generation record. Publish its indexed summary/configuration/calibration revision coherently, or treat database indexes as explicitly rebuildable caches and reconcile them before serving. Use committed generation manifests/outbox state to recover every failure boundary, not only selected correction paths. Carry forward valid provenance when replacing one artifact.

**Regression:** kill before/after database commit, manifest completion and pointer switch, with and without pending commands. After restart, compare dashboard, match configuration, frames, events and metrics: all must identify the same active generation or explicitly report recovery. No reader should see a new summary paired with old frame data.

### R03 — Video recalibration can change metadata without reprojecting the video observations

**Priority:** P1 for geometric/physical output. **Related:** B07–B09, B24, B28.  
**Locations:** `ReviewService._materialize`, `processor.reprocess_video_match`, `_publish_outputs`, `project_tracking_frames`. [S02–S04, S11–S13, S28]

The new execution endpoint does real work and publishes a generation. However, its input-mode branches differ. Video materialisation calls `reprocess_video_match(..., persist=False)`, which rebuilds frames by classifying and normalising stored rows. That path does not apply the accepted new calibration matrix to source-image detections before producing the new coordinates. The separate tracking-input branch explicitly calls `project_tracking_frames()`.

Therefore, a new `generationId` or calibration revision is insufficient evidence that the actual video coordinates changed correctly. The inspected video recomputation regression checks generation publication/cache behaviour; the regression that asserts changed coordinates uses `tracking_json`, not a raw-video observation fixture. This repeats the kind of input-mode coverage gap the original swap audit found, although the swap itself is now much better tested.

There is a related coordinate-space problem: `FrameData.x/y` are used throughout the app as normalised pitch/display coordinates, whereas `project_tracking_frames()` feeds them into a homography as image coordinates. An imported stream that truly contains source pixels needs an explicit declaration; an already normalised pitch stream must not silently undergo an image-to-pitch transform again. The current core frame schema does not encode that distinction.

**Required repair:** preserve typed source-image observations, with stream/frame identity and ground-contact anchors. Apply the selected calibration revision to those observations, then derive canonical pitch positions. For tracking imports, require and validate the input coordinate convention. Refuse geometry-dependent recomputation when the necessary source observations are unavailable; do not promote the old coordinates using new acceptance metadata.

**Regression:** one raw-video fixture with real source-pixel boxes and two known homographies must produce the expected different pitch coordinates with zero new detector calls. Separately test already normalised tracking data, metric-coordinate tracking data and explicitly pixel-coordinate data. Validate downstream distances/ownership, not only generation IDs.

### R04 — Identity approval and configuration edits are not composed consistently

**Priority:** P1 for edited player/physical analysis. **Related:** B04, B07, B24.  
**Locations:** `ReviewService.rebuild_generation`, `_active_commands`, `_effective_config`; `Storage._stored_identity_continuous`; configuration PATCH. [S02–S03, S10, S23]

The review service sets `identity_continuous` when **any** active command is `identity_validate`. Another storage consumer bases continuity on the latest relevant identity operation. Thus a validation followed by a split/join can leave the summariser using an old approval while another consumer treats continuity as invalidated. Publication also depends on accepted calibration and eligible duration, so this does not automatically publish physical values on every match; under those additional valid conditions the disagreement matters.

Configuration has a second authority path. The service stores a base configuration and repeatedly resets `myTeamCluster` to that base before replaying swap commands. A subsequent normal configuration PATCH is not necessarily represented as a command in that history. The normal route also performs reprocessing before persisting the requested configuration, while a correction-aware rebuild may independently fetch the still-old stored configuration. The original standalone team swap can be fixed while a later sequence of legitimate edits still yields inconsistent effective state.

**Required repair:** bind identity approval to the exact identity revision and covered interval. Any relevant split/join invalidates it until re-review. Route semantic configuration changes through the same revision/command service, or rebase the command overlay explicitly. Define supported undo/redo semantics instead of treating every undo target as permanently suppressed.

**Regression:** validate → split → rebuild → read all physical/identity views → revalidate → undo. Also run team swap → explicit cluster selection → unrelated correction → rebuild → restart. Compare the effective configuration with the actual teams and references in every published artifact. Include stale expected revision rejection.

### R05 — Reviewed outputs and stored narratives/auxiliary match state can belong to different generations

**Priority:** P1 for truthful reports. **Related:** B03, B07, B14.  
**Locations:** review publication, `save_analysis_artifact`, `load_analysis_artifact`, HTML export and provider-result persistence. [S02–S05, S23, S26]

Event accept/reject now rebuilds shots and summary values. That is a real fix. However, marking `tactical_report`, `drills` or `report` as stale in a generation manifest does not itself prevent the HTML endpoint from loading the old flat JSON artifacts. The inspected export route loads those saved reports independently and does not itself enforce a matching generation/stale check; a coherent end-to-end reader contract must be demonstrated, not inferred from the manifest flag.

The materialiser returns `acceptedMatchState`, but the review publisher does not include it among the new generation’s files. The processing path has a separate flat accepted-match-state artifact. It needs explicit binding or invalidation as well; otherwise one output can describe the new reviewed state while another retains a previous state.

The analysis route’s optimistic check is against match `updatedAt`, not the exact executed evidence generation. Review rebuilds do update configuration timestamps, so it would be too broad to claim they always evade this check. Nonetheless, timestamp equality is not a complete substitute for a generation comparison across all publication paths. The provider response should retain its generation identity regardless.

**Required repair:** store narratives and auxiliary state with their source generation/digest. Exports must resolve a coherent snapshot and withhold stale artifacts, or clearly label them as historical. Regeneration should never silently combine new metrics with an old narrative. Keep all reads for one export under the same pinned generation lifetime.

**Regression:** create a report, reject the shot it discusses, export HTML/JSON/CSV and reopen the match. The old report must be withheld or explicitly historical. Repeat for team and calibration changes, then simulate a generation advancing during provider execution. Assert returned/persisted evidence generation and all match-state views agree.

### R06 — The new grounding validator ignores some invented references

**Priority:** P1 before treating model output as grounded. **Related:** B14.  
**Locations:** `provider_gateway.validate_output`, `build_evidence`; `records_from_match`. [S05, S19]

The old unconditional “evidence key means grounded” behaviour was replaced by real checks, including structured numerical comparison. But references are collected only when a string starts with `ev_`, `event:` or `frame:`. An explicit list such as `evidence: ["made-up-reference"]` therefore contributes no references to the subset check and receives `grounding="grounded"`. An absent evidence key also defaults to an empty list and can pass.

**This particular predicate was executed in isolation during this review.** The transcribed unchanged function accepted the unprefixed invented reference and missing-evidence example, rejected a recognised-prefix unknown reference, rejected a wrong structured number and accepted positive controls. This is a function-level counterexample, not a live provider call or a full API reproduction.

Reference scoping also remains incomplete. The evidence builder creates frame IDs such as `frame:0`; the package carries match/generation context, but the validator does not validate that context as part of every reference. A colliding unqualified ID cannot prove which generation a claim means. Numerical checks also do not establish arbitrary free-text meaning, and no such semantic guarantee is claimed here.

**Required repair:** validate every entry in declared reference fields, regardless of prefix. Require appropriate references for grounded factual output; allow unreferenced interpretations only under an explicit different disposition. Use server-resolved match/generation-scoped IDs. Verify allowed metric availability as well as numerical equality. Expose generation identity in the persisted response.

**Regression:** arbitrary invented string, mixed valid/invalid list, absent evidence, cross-match colliding frame ID, stale generation reference, unavailable metric and wrong numerical claim. Include valid grounded and explicitly interpretive positive cases so the fix is not simply “reject all model output.”

### R07 — Costs have richer storage but inconsistent public/settlement semantics

**Priority:** P1 for spending reports/unattended operation. **Related:** B12–B13.  
**Locations:** `DurableJobLedger.receipt`, `cost_for`, `cost_summary`; provider reservation ledger and outbound adapter. [S05–S06, S14, S23–S24, S30]

The job receipt correctly reports `actualTotal=None` when unsettled exposure remains. `cost_for()` and `cost_summary()` instead return the settled subtotal under the same `actualTotal` name. For a job with no settled charge and positive unsettled exposure, the receipt says unknown while the cost endpoint says zero. The current frontend cost type also requires a number.

This is a remaining public-contract inconsistency, not evidence that the new transactional ledger is useless. The actual worker path contains explicit handling for unsettled remote cost; preserve that safeguard. Do not “fix” this by forcing all unknown costs to zero or by charging the entire logical budget again on every retry.

The model-provider ledger is another scope. It atomically accumulates configured fixed reservations, but the inspected outbound request has no output-token ceiling or returned-usage billing reconciliation that proves each request stays within that reservation. That controls call admission under an assumed amount; it does not establish the actual provider bill is capped at that amount. No expenditure or overcharge was observed in this review.

**Required repair:** one cost response contract with settled subtotal, outstanding reservation, unsettled exposure and nullable total actual charge. Require explicit evidence for zero cost. Bound provider usage conservatively and reconcile actual usage; retain uncertainty/reservation when the outcome is unknown. Use a single documented logical-job budget model.

**Regression:** submit, run, timeout, settle, cancel, retry and reopen the same job. Compare every API/UI/receipt. Inject provider usage above the estimate and an unknown bill. There must be no silent zero, duplicate reservation or unsupported “hard spending cap” claim.

### R08 — Layered cache keys still omit outcome-changing dependencies

**Priority:** P1 before cross-run reuse/promotion; otherwise controlled local scope. **Related:** B09, B18.  
**Locations:** `video_pipeline._layered_identities`, generation layer identities and recovery-enabled processing inputs. [S03, S15–S16, S28]

The new identity types and verified primary-weight hash are an improvement. However, the emitted identity uses fixed preprocessing/class-map strings and a tracker configuration filename; it does not bind all recovery/auxiliary weights, thresholds/acquisition settings, selection profiles and relevant configuration bytes that determine the returned rows.

A primary-detector artifact can legitimately exclude later recovery/calibration dependencies. The correct repair is not to stuff every input into one universal key. The problem is claiming reusable identity for the actual combined artifact without separately identifying those later dependencies. A raw-file digest can distinguish materialised output bytes, but it does not retroactively make an incomplete input cache key safe for reuse.

**Required repair:** define exactly what each artifact contains and derive its key from the inputs that determine it. Hash the effective tracker/preprocessing/recovery configurations rather than their filenames. Keep primary observations, association, ball recovery, projection and reviewed metrics separate where reuse benefits justify that boundary. Unknown components disable reuse.

**Regression:** change auxiliary weights, recovery profile, acquisition mode, tracker contents under the same filename and relevant thresholds. The affected layer’s key must change while unaffected upstream keys remain stable. Then demonstrate one real cache hit and one real invalidation, not only digest inequality on an isolated class.

### R09 — FFmpeg’s defaults bound cumulative raw work, not just memory

**Priority:** P1 before promoting FFmpeg for full matches; P2 while it remains a bounded challenger. **Related:** B17, B19, B27, B31.  
**Locations:** `FfmpegFrameSource.__init__`, `_iter_ffmpeg_decode`, process wrappers and `run_proxy_ffmpeg_job`. [S07–S09]

The old stdout/stderr hazard has been substantially repaired. But the default `max_output_bytes=8*1024**3` is applied to **cumulative decoded raw bytes**, and the 300-second wall timeout spans the iterator lifetime, including time the caller spends doing inference between frames.

A 1920×1080 BGR frame contains 6,220,800 bytes. At 25 fps, 8 GiB is only about **55.23 seconds of video**, before accounting for a possible earlier wall-time limit. This is arithmetic from the source configuration, not a throughput measurement. Streaming a full match through a small bounded buffer can be memory-safe while exceeding that cumulative total many times over. The default OpenCV path is not subject to this particular FFmpeg cap.

The fixed timeout also risks classifying slow downstream inference as a decoder stall. Separately, the proxy helper still directly calls `subprocess.run` with a 120-second timeout and does not share every bounded decoder control. Protocol allowlisting/resource limits are useful but should not be described as full network/filesystem isolation.

**Required repair:** declare and enforce the admitted mode: short diagnostic clip versus offline full match versus live stream. Separate resident queue limits, total work/duration budget, decoder-stall timeout and whole-job deadline. Size total limits from the admitted source and account for consumer backpressure. Apply a common execution policy to proxy/export paths. Preserve limits; do not remove all safeguards just to make long files pass.

**Regression:** representative full-half media, slow consumers, cancellation during blocked I/O, nonzero exit, malformed/truncated streams and configured absolute executables. Test the real macOS executable layout rather than relying on dependency dry-run success. Retain the small generated-media CI lane as a fast regression.

### R10 — Evaluation metadata completeness is still conflated with acceptance

**Priority:** P1 for promotion claims; otherwise an acceptance gate. **Related:** B29–B32.  
**Locations:** `current_repository_evaluation_gate`, `score_hota_idf1`, training metadata and GPU workflow. [S20–S22, S25, S29]

The old hardcoded zero inventory and null-but-scored behaviour are improved. Missing manifest means unknown; numeric scores and provenance fields are now required. However, the current gate accepts a manifest as `scored` from supplied finite numbers, digest-shaped strings and booleans, then sets `accepted` according to that state. It does not by itself read/hash the referenced prediction/label artifacts, replay the scorer, enforce a declared score scale or check model-acceptance thresholds.

A manifest reader is useful. It should say “record present/structurally complete” unless its provenance is trusted and its results meet an explicit acceptance policy. For example, merely obtaining a finite score is not equivalent to exceeding the product’s required accuracy. This is not an accusation of fabricated current evaluation results; none were supplied or verified in this review.

Training now chooses joint metrics from one selected epoch and uses a shared default base model. Still, an epoch inferred from CSV fitness is not conclusive evidence that its record describes the exact promoted weight bytes. Retain the actual checkpoint metadata/validation output and dataset split identities.

**Required repair:** separate artifact inventory, execution, scoring and threshold acceptance. Bind a scorer receipt to verified source/label/prediction/checkpoint identities and declare score units. Keep software tests, genuine perception inference, independent accuracy and analyst workflow as separate acceptance results.

**Regression:** a structurally valid but missing-artifact manifest, modified prediction bytes, out-of-range score, a valid below-threshold score and an actual verified passing evaluation. Only the final applicable case should count as model acceptance. Run the independent evaluator on retained artifacts; do not replace this with test metadata.

## 7. Frontend and API integration assessment

The inspected frontend query/correction helpers now call the normal `/api/matches/...` routes. That is an important improvement: retiring the duplicate workbench authorities is accompanied by a client-side route migration. The current frontend build, lint and TypeScript checks pass. [S23, S25–S26, S30]

The inspected client contracts still largely describe correction `saveState` and identifiers rather than the full `applyState`, base/output generation and conflict/recovery state. Cost summary types require a numeric actual total. The typed-search return type exposes a smaller subset than the backend’s interpreted/unsupported-condition response. These are integration requirements for the next patch, not proof that every rendered component is currently broken. [S30–S31]

An actual browser workflow should show the difference between command recorded, application pending, application failed and new generation published. It should reload affected views together, display unknown cost as unknown and make unsupported query interpretation visible. A passing mocked component test cannot prove that a tab open during another edit remains on a coherent generation.

No live browser session or full manual frontend review was performed here. The source tree contains a large diagnostic/experimental surface; keeping it namespaced is preferable to treating every helper panel as a production capability. Do not make the next step a UI rewrite. Fix the contract, then test the one user journey end to end.

## 8. Architecture and implementation quality

### Keep these changes

Keep Python/FastAPI and the existing detector/tracker pipeline. Keep the shared review service, stricter domain models, immutable-observation approach, explicit null/unknown concept, generation manifests, transactional ledger, source-bound worker checks, provider gateway and environment separation. The tests added for actual raw-row team correction and real FFmpeg behaviour are valuable. [S02–S17, S23–S29]

### The remaining architectural adjustment

Use one authority for a match’s active generation and its complete dependency set:

```text
Source and immutable observations
              |
Revisioned calibration + semantic configuration + analyst commands
              |
Complete candidate generation
              |
Validate + durably publish one active-generation reference
              |
Snapshot-bound API / reports / evidence / derived indexes
```

This is a refinement of the architecture already implemented, not a new fleet of services. Reads must not delete snapshots. Materialisation must consume the same revision that publication claims. Reports and auxiliary match state must either belong to that generation or be explicitly historical. Cost and evaluation metadata must distinguish known facts from declarations.

### Do not optimise before the receipts and semantics agree

The new producer-counter preservation is a proper foundation for performance work. Measure decoding, preprocessing, inference, recovery, serialization, publication and full-job allocation separately. The generation reader’s full-file integrity work and repeated publication can become CPU/I/O costs; no latency figure is asserted without profiling. None of R01–R10 is solved merely by porting orchestration to Rust or C++.

### Scope of security/dependency assurance

New server-owned deployment settings and authentication middleware are present. This review did not inspect a deployed reverse proxy, secrets management, TLS termination, tenant administration or actual process/container network isolation. The successful production npm audit is not a Python vulnerability audit. No dependency CVE research, licence clearance or private billing inspection was performed. Keep claims limited to the tested local/product configuration.

## 9. Consolidated finishing plan — six bounded changes

These are targeted follow-up changes within the existing H01–H07 programme, not six new feature phases.

| Change | Scope | Required evidence before merge |
|---|---|---|
| **1. Generation lifetime and crash consistency** | R01–R02 | Concurrent pinned readers; old-generation history; process kill around database/pointer publication, including non-correction publication. |
| **2. Real video reprojection and edit composition** | R03–R04 | Raw-video pixel fixture with known transforms; validate→split→revalidate; swap→config PATCH→rebuild; interval/units checks. |
| **3. Generation-bound reports and exhaustive evidence validation** | R05–R06 | Existing narrative becomes stale correctly; reject every invalid explicit reference format; foreign/stale IDs; generation advances during a fake provider call. |
| **4. One cost contract** | R07 | Same nullable totals on all routes/UI; settled versus unsettled; bounded model usage and actual-cost reconciliation. |
| **5. Correct artifact identity and evaluation acceptance** | R08, R10 | Effective configuration invalidation, verified artifact replay and explicit score thresholds. |
| **6. Declared video/platform operating envelope** | R09 plus H07 gates | Full-half/slow-consumer real-media tests, common process policy, real supported-platform install/run; separately authorised actual perception evaluation. |

For each change, first write the counterexample against this pinned revision. Preserve the failed baseline and fixed result with test profile, source commit and artifact hashes. A disabled capability can be an acceptable interim disposition, but it must be reported as disabled/deferred rather than implemented and accepted.

### Minimum end-to-end acceptance journey

Use both a raw-video-backed fixture and an imported-tracking fixture. Create a baseline match, retain its generation, review/alter team and identity state, commit a supported calibration, accept/reject a shot, regenerate the report, force a recoverable interruption, restart a fresh process and reopen the match. Undo/rebuild, export through each supported format, and compare every artifact’s generation and metric definitions. Repeat with a second simultaneous reader.

Then perform a separate actual perception run on permitted representative footage with the admitted model/runtime. Independent football labels and analyst usefulness are separate stages; do not merge them into a single “CI green” result.

## 10. Evidence created by this review

### 10.1 Isolated provider validator checks

`probes/provider_validation_excerpt_probe.py` transcribes `_walk`, `validate_output` and the two simple value dataclasses from `provider_gateway.py`. It imports no repository application, opens no provider connection and uses no credentials.

| Check | Observed result | Meaning |
|---|---|---|
| P01 valid `frame:0` | Grounded | Positive reference control. |
| P02 unknown `frame:999` | Ungrounded | Recognised-prefix rejection works. |
| P03 invented `made-up-reference` | **Grounded** | Prefix filtering misses an explicit invalid reference. |
| P04 missing evidence field | **Grounded** | No requirement for reference-backed factual output in this function. |
| P05 mismatched structured number | Ungrounded | Numerical mismatch control works. |
| P06 matching structured number | Grounded | Positive numerical control. |

These are six cases of one validation component, not six independent backend bugs, and not full API or provider reproductions. Upstream output-schema validation was not executed. The invented-string reference remains relevant to a string-list schema; numeric/malformed list fixtures were deliberately not used to overstate reachability.

### 10.2 CI artifact validation

The pack preserves the downloaded archives and extracted receipts/logs. Verification-log digests are compared with the digests in the verify receipt. That is an integrity consistency check on the downloaded evidence, not a cryptographic attestation of every production property. The receipt’s commit matches the pinned reviewed source.

### 10.3 Arithmetic-only media capacity check

The pack records the 8-GiB/BGR calculation. It assumes 1920×1080, three bytes per pixel and 25 frames per second. It is not an observed FFmpeg speed or memory benchmark. It demonstrates that a cumulative-output limit must not be confused with a resident-memory bound for streaming full matches.

## 11. Final decision

**Accept the direction and retain the remediation. Do not accept an unconditional “35 findings closed / all phases production-ready” statement at this snapshot.**

The current implementation is a much stronger engineering base than the earlier code. The next deliverable should be a coherent reviewed match that survives edit composition, generation changes, failure and restart—not another collection of capability flags or a new model integration.

Close the ten follow-up groups through the six bounded changes above. Report software correctness, actual video/ML execution, independent football accuracy and analyst acceptance separately. This keeps the project moving without either dismissing substantial progress or overselling what the current evidence proves.

## Appendix A — Pinned source register

References identify the reviewed revision. “Inspected” means selected relevant contents/call paths, not necessarily every line of each large file. The prior report remains the source of the B01–B35 terminology and original closure requirements. The cache types are supported by their use and new tests as well as the source identity design; the entire historical research tree was not re-reviewed.

- **S01** — [docs/superpowers/audits/2026-09-18-backend-audit-v2-closure.md](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/docs/superpowers/audits/2026-09-18-backend-audit-v2-closure.md)
- **S02** — [backend/app/review_service.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/app/review_service.py)
- **S03** — [backend/app/storage.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/app/storage.py)
- **S04** — [backend/app/processor.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/app/processor.py)
- **S05** — [backend/app/provider_gateway.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/app/provider_gateway.py)
- **S06** — [backend/app/provider_adapters.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/app/provider_adapters.py)
- **S07** — [backend/app/workbench/media.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/app/workbench/media.py)
- **S08** — [backend/app/workbench/hashing.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/app/workbench/hashing.py)
- **S09** — [backend/app/workbench/executables.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/app/workbench/executables.py)
- **S10** — [backend/app/analytics.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/app/analytics.py)
- **S11** — [backend/app/workbench/geometry.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/app/workbench/geometry.py)
- **S12** — [backend/app/schemas.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/app/schemas.py)
- **S13** — [backend/app/domain_types.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/app/domain_types.py)
- **S14** — [backend/app/workbench/jobs.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/app/workbench/jobs.py)
- **S15** — [backend/app/video_pipeline.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/app/video_pipeline.py)
- **S16** — [backend/app/workbench/cache.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/app/workbench/cache.py)
- **S17** — [backend/app/workbench/perception.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/app/workbench/perception.py)
- **S18** — [backend/app/workbench/assistance.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/app/workbench/assistance.py)
- **S19** — [backend/app/workbench/evidence.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/app/workbench/evidence.py)
- **S20** — [backend/app/workbench/evaluation.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/app/workbench/evaluation.py)
- **S21** — [backend/app/training_quality_gate.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/app/training_quality_gate.py)
- **S22** — [backend/train_custom.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/train_custom.py)
- **S23** — [backend/app/main.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/app/main.py)
- **S24** — [backend/app/settings.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/app/settings.py)
- **S25** — [.github/workflows/ci.yml](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/.github/workflows/ci.yml)
- **S26** — [backend/tests/test_audit_v2_h02_review.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/tests/test_audit_v2_h02_review.py)
- **S27** — [backend/tests/test_audit_v2_h03_calibration.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/tests/test_audit_v2_h03_calibration.py)
- **S28** — [backend/tests/test_audit_v2_h05_recompute.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/tests/test_audit_v2_h05_recompute.py)
- **S29** — [backend/tests/test_gpu_acceptance.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/tests/test_gpu_acceptance.py)
- **S30** — [frontend/src/utils/workbench.ts](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/frontend/src/utils/workbench.ts)
- **S31** — [frontend/src/components/WorkbenchPanel.tsx](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/frontend/src/components/WorkbenchPanel.tsx)
- **S32** — [backend/app/workbench/review.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/b3fbe78c51f9a30891e939b610fa292da7f05bf9/backend/app/workbench/review.py)

**Revision/CI records:**

- [Reviewed main source](https://github.com/ms81labs/sol-astra-football-analyses-sept26/tree/b3fbe78c51f9a30891e939b610fa292da7f05bf9)
- [Baseline comparison](https://github.com/ms81labs/sol-astra-football-analyses-sept26/compare/d881d1eaf7a0898897bd9a1a1ae46306606c904d...b3fbe78c51f9a30891e939b610fa292da7f05bf9)
- [Reviewed CI run 35391149730](https://github.com/ms81labs/sol-astra-football-analyses-sept26/actions/runs/35391149730)

**Not performed:** full local repository pytest, live browser workflow, paid Daytona allocation, external model requests, current real-footage accuracy scoring, live deployment security audit, clean macOS/CUDA execution by this reviewer, or exhaustive review of every historical script. No repository fixes are claimed by this report.
