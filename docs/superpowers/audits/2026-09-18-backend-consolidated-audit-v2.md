# Guerilla Analytics — Consolidated Backend Audit v2.0

**Source recheck, second-review reconciliation, and implementation handoff**  
**Repository:** `ms81labs/sol-astra-football-analyses-sept26`  
**Audited commit:** `d881d1eaf7a0898897bd9a1a1ae46306606c904d`  
**Report date:** 18 September 2026  
**Status:** 35 open remediation items; no repository changes or fixes claimed.

> Use this report in place of the original B01–B32 report for remediation. The original IDs are preserved. The seven additional observations are mapped explicitly; four expand existing items and three become B33–B35. This is not a new architecture proposal or a claim of full backend certification.

## 1. Executive decision

**The second review supports the central audit conclusion: this is a substantial application with real video/analytics capability, but inconsistent data authority, incomplete execution boundaries and misleading success/measurement semantics remain.** Keep the core and harden the integration. Do not substitute a Rust rewrite, a stronger model, or more capability dictionaries for these fixes.

The strongest revised finding is B04: under the raw-row reconstruction conditions described below, a team swap can be lost **inside the same request**. B18 is also stronger than its original wording: the wrapper directly overwrites a measured `fourRates` result with counters from a fresh audit. Calibration has multiple independent negative cases, including an invented unit-square fallback, and the legacy cloud path still does not enforce the newer consent/budget policy.

The consolidated total is **35 remediation items**, not 39 independent bugs and not 35 runtime reproductions. Some items are directly visible correctness defects; others are race risks, supported-capability limitations, or release-evidence requirements. They must be prioritised by the affected workflow rather than treated as 35 universal deployment emergencies.

### Immediate disposition

| Use | Disposition until the relevant fixes pass |
|---|---|
| Local development with synthetic/permitted data | Continue; preserve the current source and failing counterexamples. |
| Analyst editing relied on as saved/rebuild-safe | Do not sign off until H02 and its integration tests pass. |
| Publishing physical or calibration-dependent measurements | Withhold until H03 and source-bound evaluation pass. |
| Cloud model calls for real match data | Centralise and prove the consent/budget boundary before enabling them. |
| Unattended paid jobs | Require H04 reconciliation, cumulative budget and cancellation evidence. |
| FFmpeg challenger on long recordings | Require real-pipe/clock/resource tests; retain a qualified fallback. |
| Public or multi-tenant hosting | Still a separate security acceptance gate, not supplied by loopback defaults. |

This does not negate existing strengths: real Ultralytics/BoTSORT execution, deterministic analytics, persisted normal-match operations, schema validation, HTML escaping, source-bound remote artifact checks, test infrastructure and local-first operation remain worth preserving. The findings concern specific guarantees, not the assertion that nothing works.

## 2. Evidence scope and provenance

Both supplied reports were read. `main` was re-resolved through the connected GitHub source and still pointed to **d881d1ea** at the recheck, so no newer revision is mixed into this consolidation. The original pinned-source inspection remains the basis for unchanged areas. This pass made targeted fresh reads of correction paths, raw-row reprocessing, calibration, jobs, compatibility routes, provider dispatch/grounding, media pipes, runtime receipts, CI configuration and test setup. It is not another line-by-line review of every historical script/test.

A local repository checkout could not be obtained in this environment: direct GitHub access failed at DNS and the archive was unavailable through the download path. Source access through the connected GitHub tool worked. This limitation changes the execution claims, not the directly visible source findings.

| Evidence class | What is actually available | What it does not establish |
|---|---|---|
| Original audit | 32 source-inspection findings bound to the same commit | Every line reviewed; every defect executed |
| Uploaded second review | Source explanations and claimed 15 reproductions; reported backend CI-profile result of 3,329 passed, 5 skipped, 0 failed | Independent access to `/tmp/audit_repro/repro.py` or its log; those files were not uploaded |
| Fresh GitHub reads | Current ref and targeted pinned-file excerpts; exact call paths and predicates | Production failure frequency or actual billing/data leakage |
| GitHub CI step metadata | Verify job `105399174965` records a successful code-only step | Full release, GPU, real-media or football-accuracy acceptance |
| Local isolated checks in this pass | Four cases using transcribed, unchanged geometry function bodies: three defect/counterexample checks and one positive control | Pydantic/API/storage integration, repository pytest or real-video behaviour |
| Deployment/ML activity | None performed in this pass | No current-footage accuracy, cloud-region, billing or security certification |

**Important:** the external report’s “15 / 15 reproduced” and “3,329 passed” are attributed claims, not test results rerun by this report. No conclusion here depends on pretending those missing artifacts were inspected. The included geometry probes are separate, narrowly scoped evidence.

### Evidence terminology used below

**Source rechecked** means the relevant code was freshly read through GitHub in this pass. **Original pinned-source inspection retained** means the original source finding remains at the same audited revision and was cross-checked against the supplied review, without pretending a second exhaustive read. **External reproduction reported** identifies what the other reviewer says it ran. **Isolated source-excerpt check** identifies the small local experiment included in the evidence pack. None of these labels means a fix has landed.

## 3. Corrections to the two reports

### 3.1 What is strengthened

**B04 — immediate ineffective team correction.** The call chain supports a same-request overwrite when raw rows are rebuilt with unchanged mapping. “A later rebuild might undo it” understates that path. Do not generalise this to every video or to deletion of raw data.

**B18 — overwritten telemetry, not merely missing telemetry.** The producer returns real counters, and the wrapper replaces their top-level dictionary. Preserve and validate that receipt instead of adding another independent audit object.

**B01/A1 — empty compatibility services.** Workbench search uses an empty event list and reports use empty data. This is an integration failure for consumers of those endpoints. Reports may also reject nonempty claimed references, so “always returns a template” is imprecise. Loading trusted match data is the fix; restoring trust in arbitrary posted arrays is not.

**B33/A2 — invented geometry.** A unit-square default is a different problem from the missing-matrix fallback. Both need negative tests even if one calibration service fixes them together.

### 3.2 What needs more careful phrasing

**Retry reservation semantics.** The second report describes a test that keeps total reservation at 1.25 after retry and suggests its intent must change. That does not necessarily follow. One logical-job reservation may legitimately remain fixed across attempts. The actual defects are inconsistent attempt accounting, lack of an explicit cumulative budget contract, and unknown actual cost becoming zero. Do not “fix” it by multiplying full-budget reservations.

**CI installation and stubs.** `.github/workflows/ci.yml` installs `pip install -e . -r backend/requirements-dev.txt`, not just the dev file. `conftest.py` installs each cv2/pandas/ultralytics stub only after a missing-import error. It is therefore incorrect to assert unconditional mocking of all three. The meaningful limitation is that the code-only profile does not establish real ML execution. The global test setup also defaults the leftover-HTTP feature flag on; add tests for the production default-off configuration. [CI workflow](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/.github/workflows/ci.yml) · [test setup](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/tests/conftest.py).

**FFmpeg failure mode.** The blocking-pipe hazard is conditional on timing/backpressure. Neither supplied artifact demonstrates a real FFmpeg deadlock. Keep it as a credible source-supported race with a required real-process test, not an always-hangs claim.

**Performance growth.** The ledger’s full-cache writes and FFmpeg’s repeated whole-log parsing have identifiable growth risks, not measured production latency figures. Retaining history is not itself wrong; rewriting all history per transition is the problem.

**Scopes and useful baselines.** A local provider preference is not itself a permission policy. Frame-count possession can be correct for equal-duration eligible samples. A declared 105×68 pitch default can be valid. A heuristic smoke check can be useful. Preserve those distinctions while preventing unsupported measurements or policy bypasses.

### 3.3 Mapping the additional observations

| Other-review ID | Consolidated item | Disposition |
|---|---|---|
| A1 Empty workbench search/report inputs | B01 | Expanded the competing-authority finding; no duplicate ticket. |
| A2 Unit-square calibration fallback | B33 | New independently testable calibration defect. |
| A3 Absolute FFmpeg/ffprobe path rejected | B34 | New configuration/guard inconsistency. |
| A4 Whole file read before `[:1]` | B16 | Another whole-file allocation site; included with hashing/I/O cleanup. |
| A5 Rewrite all ledger rows on every mutation | B11 | Added write-amplification aspect to the authoritative-state fix. |
| A6 Idempotency conflict becomes HTTP 500 | B35 | New API/domain-error mapping defect. |
| A7 Body provider overrides stored preference | B13 | Sharpened the same missing policy boundary. |

No original ID is dropped. “Retained” does not mean all subclaims are equally severe or independently executed.

## 4. System map and root causes

The normal product flow is upload/admit → local or source-bound remote processing → stored observations/frames → ownership/events/metrics → review/report/export. That flow is real. The difficulty is parallel implementations and partial projections: normal versus workbench routes; raw versus edited frames; calibration profile versus evaluation; actual versus constructed receipts; policy helpers versus legacy network calls.

| Area | Keep | Consolidate or qualify |
|---|---|---|
| API and settings | FastAPI, origin checks, typed normal-match endpoints | One service per operation; server-owned deployment/authorisation settings |
| Storage/review | Durable normal-match history, immutable source assets | Idempotent command application and consistent derived generations |
| Jobs/remote worker | Source-bound bundles, file identity/size validation, cleanup evidence | Transactional state/leases and explicit cost semantics |
| Media/vision | Real core detector/tracker; replaceable decode boundary | Actual timestamp/buffer contracts, bounded I/O, no metadata pretending to execute |
| Analytics/reporting | Deterministic baseline and unknown-state concept | Shared team/interval metric contract and review-aware dependency rebuilding |
| Evaluation/training | Tests, training wrapper, frozen-protocol preparation | Exact-checkpoint scores, corrected evaluators and independent acceptance |
| Optional AI | Replaceable provider interfaces and schema checks | One unavoidable consent/budget/evidence gateway |

The remedy is primarily a **modular Python application with authoritative services**, not a fleet of new microservices. Re-export namespaces, a new adapter class or an `admitted` boolean do not prove the operation is implemented.

## 5. Severity and release gates

**P1**: fix before relying on the affected workflow, publishing its measurements, or enabling its paid/cloud operation. **P2**: important implementation or scope work that can sometimes remain explicitly disabled/constrained. P1 “before public hosting” does not claim an immediate compromise of a properly local-only instance. B32 is an acceptance gate as well as a verification-design item.

The remediation queue should begin with the policy boundary, immediate correction loss and invalid calibration/scoring/metric publication. Job safety must be complete before unattended spending. Video optimisation follows reliable telemetry, not the other way around.

## 6. Consolidated finding register

Each entry includes its original/additional IDs, affected behaviour, evidence strength, required fix and acceptance test. All remain open at the pinned reference. Source links identify the inspected revision, not a moving branch.

### B01 — Normal and workbench APIs disagree; workbench queries and reports are disconnected

**Priority:** P1  
**Origin:** B01, A1  
**Work package:** H02  
**Status:** OPEN — no fix verified

**Finding.** The normal /api/matches interfaces use persisted match operations, but /api/workbench still has independent process-global correction/evidence objects. Its correction path appends history without applying the normal match effects. Its query/search handlers call execute_typed_query([],...); its report handlers pass empty metrics/events and an empty known-evidence set rather than loading the stored match. The problem is disconnected server-owned data, not merely discarded request arrays.

**Evidence and limits.** Targeted source recheck in this pass. Source rechecked in workbench/routes.py:150–290 and the normal Storage correction path. The external report claims an executable demonstration for B01 and A1, but its executable artifact was not supplied here. Report routes can return either empty templates or rejection for claimed references; “always a template” is too broad.

**Consolidation note.** P1 for clients using these routes; this does not establish that all frontend search/report features are empty. Some normal match routes already work. A1 is merged here, not counted again.

**Required change.** Retire unsupported compatibility routes with a documented response, or delegate both route families to the same Match/Review/Report services. Resolve events, metrics and evidence from authorised server-owned match generations. Do not “fix” the empty arrays by trusting caller-supplied ground truth. Scope service instances to the application/storage context rather than module-global mutable objects.

**Acceptance test.** For each supported route family, use two stored matches. Query known accepted events, generate an evidence-linked report, submit a correction, restart a separate process, then read through both interfaces. Results, revision numbers and effective effects must agree. Explicitly test that posted fake events/knownEvidenceIds cannot override server truth.

**Pinned sources:** [backend/app/main.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/main.py) · [backend/app/workbench/routes.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/routes.py) · [backend/app/storage.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/storage.py) · [backend/app/workbench/review.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/review.py) · [backend/app/workbench/routes.py:150–290](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/routes.py#L150-L290)

### B02 — Saved corrections and their effects are not committed as one recoverable operation

**Priority:** P1  
**Origin:** B02  
**Work package:** H02  
**Status:** OPEN — no fix verified

**Finding.** Storage.submit_correction saves the correction log and then applies the effect outside that commit. Undo follows a similar log-first/effect-later structure. A crash or exception between these steps leaves a durable saved edit whose effect is missing or incomplete. Recovery can replay operations such as a team swap without a durable effect-application marker.

**Evidence and limits.** Targeted source recheck in this pass. Source rechecked: storage.py:1105–1173 persists the command log before applying effects, and application occurs after releasing the per-instance lock. A real crash or concurrent request was not run in this pass; the vulnerable ordering is directly present.

**Consolidation note.** “Saved” can describe the history record while application is incomplete. Do not claim an observed production data-loss incident. Model received/recorded/applying/applied separately and make retries idempotent.

**Required change.** Use a durable command/outbox plus idempotent materialisation, or publish a complete new match generation atomically. Record received, committed, applying and applied separately. Never equate saved history with successful downstream rebuilding.

**Acceptance test.** Kill a subprocess after log commit and during each artifact write. Restart, reconcile, and prove each edit has exactly one effective application. Repeat recovery and undo requests.

**Pinned sources:** [backend/app/storage.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/storage.py) · [backend/app/workbench/review.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/review.py) · [backend/app/storage.py:1105–1173](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/storage.py#L1105-L1173)

### B03 — Event rejection does not invalidate all dependent statistics

**Priority:** P1  
**Origin:** B03  
**Work package:** H02  
**Status:** OPEN — no fix verified

**Finding.** The event-accept/reject branch of _apply_saved_correction updates saved events. It does not rebuild the stored shots, summary or previously generated narrative. A report can therefore exclude a rejected event from its event list while retaining a statistic derived from it.

**Evidence and limits.** Targeted source recheck in this pass. Source rechecked: _apply_saved_correction saves reviewed events and returns without rebuilding shot/summary/narrative dependants. The exact numerical consequence depends on whether the rejected event fed the affected metric.

**Consolidation note.** Keeping original automated metrics is legitimate only as an explicitly separate, versioned view. The defect is silently combining different review generations, not the existence of unreviewed candidate data.

**Required change.** Define a dependency graph and a single reviewed-event projection. Rebuild or mark stale all dependent shot, summary, player and report outputs. Preserve unreviewed candidates separately rather than treating every unreviewed event as accepted truth.

**Acceptance test.** Reject a previously detected shot and compare event lists, shot-quality totals, player summaries, HTML, JSON and CSV. Accept it again and undo it; all views must reconcile.

**Pinned sources:** [backend/app/storage.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/storage.py) · [backend/app/analytics.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/analytics.py) · [backend/app/report_export.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/report_export.py)

### B04 — A team swap can be undone inside the same request; identity edits are not rebuild-safe

**Priority:** P1  
**Origin:** B04  
**Work package:** H02  
**Status:** OPEN — no fix verified

**Finding.** For the team_mapping swap path, _apply_team_mapping saves swapped derived frames and immediately invokes reprocess_video_match(self, match_id) without a changed configuration. If nonempty raw rows are present, reprocessing rebuilds and saves frames from those rows with the unchanged stored team mapping. A meaningful swap can therefore disappear within the same submit_correction request, not only during a later rebuild. Identity repair similarly alters derived frames/references without making the edit an overlay applied to raw-row reconstruction.

**Evidence and limits.** Targeted source recheck in this pass. The immediate call chain was rechecked in storage.py:1249–1260 and processor.py:805–858. The external reviewer reports a raw-row-backed reproduction with saveState=saved and unchanged final frames. That complete application reproduction was not independently rerun here.

**Consolidation note.** Stronger than the original audit, but avoid “every video match”: the relevant conditions are nonempty raw rows, an effective swap, and unchanged source mapping. No deletion of the original video or raw observations was demonstrated.

**Required change.** Make semantic team assignment and identity repair versioned commands over immutable observations. Rebuild all derived artifacts through those overlays. Persist a new team mapping before constructing the new generation, or include it explicitly in the command projection. Give regenerated events stable identity/reconciliation rules so accepted/rejected decisions also survive.

**Acceptance test.** Create a raw-row-backed video fixture with known distinct teams and clusters, then swap teams. Assert the final result differs before the request returns and remains changed after a second rebuild and a fresh-process restart. Add the corresponding no-raw-row tracking fixture as a separate case. Repeat for identity split/join and undo; verify every event/shot/ownership reference.

**Pinned sources:** [backend/app/storage.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/storage.py) · [backend/app/processor.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/processor.py) · [backend/app/workbench/identity.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/identity.py) · [backend/app/storage.py:1249–1260](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/storage.py#L1249-L1260) · [backend/app/processor.py:805–858](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/processor.py#L805-L858)

### B05 — Calibration can pass with no valid projection

**Priority:** P1  
**Origin:** B05  
**Work package:** H03  
**Status:** OPEN — no fix verified

**Finding.** _project returns the first landmark's pitch position when homography is absent. With a single holdout that is also the first landmark, evaluate_landmarks can obtain zero residual without any camera projection. Matrix shape, invertibility, finite values and independent landmark coverage are not established by the profile's field declarations.

**Evidence and limits.** Targeted source recheck in this pass. Fresh source recheck plus isolated execution of the transcribed _project/evaluate_landmarks functions: with no homography and one holdout, the helper returns accepted=True and p95M=0.0. This did not execute the Pydantic API, storage or commit endpoint. The external report separately claims that the full commit helper returns committed=True.

**Consolidation note.** The isolated test establishes the mathematical fallback defect, not a real-match calibration incident. See evidence G1. A separate defect, B33, covers inventing a unit-square transform when manual points are missing.

**Required change.** Fail closed when the selected camera model is unavailable. Validate the matrix and landmarks, minimum independent support, spatial coverage and interval validity. Never substitute an arbitrary pitch point for an unavailable transform.

**Acceptance test.** No matrix plus one holdout must fail. Singular, malformed and non-finite matrices must fail. Valid independently checked transforms must pass on declared regions only.

**Pinned sources:** [backend/app/workbench/geometry.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/geometry.py) · [backend/app/workbench/geometry.py:88–122](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/geometry.py#L88-L122) · [backend/app/workbench/geometry.py:304–316](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/geometry.py#L304-L316)

### B06 — Calibration regional errors are associated with the wrong landmarks

**Priority:** P1  
**Origin:** B06  
**Work package:** H03  
**Status:** OPEN — no fix verified

**Finding.** evaluate_landmarks sorts the residual values, then zips those sorted values with holdouts in their original order when computing far-side error. Sorting has broken the landmark-to-error association, so the regional acceptance decision can use another point's residual.

**Evidence and limits.** Targeted source recheck in this pass. Fresh source recheck and isolated source-excerpt checks G2/G3. With two holdouts, reversing their order changes farSideMaxM from 10 to 0 while both configurations still fail overall p95. A stronger 40-holdout fixture changes accepted from True to False solely by reordering the same observations: the actual far-side error is 100 in both cases.

**Consolidation note.** The second report’s two-point example proves the regional-statistic error but not an acceptance flip by itself. G3 independently demonstrates that an acceptance flip is possible. These are isolated function checks, not full deployment or CV validation.

**Required change.** Keep (landmark, residual) pairs intact. Compute percentile statistics from a separate list and regional statistics from the original paired data. Define what near/far means for the actual camera rather than only a fixed pitch-Y threshold.

**Acceptance test.** Use near/far landmarks with deliberately different errors and shuffle input order. Regional errors and the acceptance decision must not change.

**Pinned sources:** [backend/app/workbench/geometry.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/geometry.py) · [backend/app/workbench/geometry.py:88–111](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/geometry.py#L88-L111)

### B07 — Calibration commit, calibration acceptance and metric publication are separate inconsistent paths

**Priority:** P1  
**Origin:** B07  
**Work package:** H03  
**Status:** OPEN — no fix verified

**Finding.** commit_calibration_for_match saves calibration_profile and marks configuration committed, whereas _stored_calibration_accepted reads calibration_evaluation. In addition, _summary_metric_availability makes physical metrics available based on identity_continuous alone. The identity-promotion flow calls that summariser without establishing a valid calibration.

**Evidence and limits.** Targeted source recheck in this pass. Calibration commit writes calibration_profile in the freshly rechecked storage.py:1661–1673; the original pinned-source inspection shows _stored_calibration_accepted reads calibration_evaluation. The physical-summary availability path independently uses identity_continuous. The external reviewer reports reproducing committed=True with the other reader still returning False.

**Consolidation note.** There are two issues to close together: consumers disagree about the accepted calibration revision, and identity review alone can unlock physical metrics. A successful commit response is not proof that downstream positions were reprojected.

**Required change.** Use one calibration revision and evaluation record. Publish physical measurements only when both identity and geometric prerequisites hold for the measured interval. Mark dependent generations stale when the calibration changes.

**Acceptance test.** Promoting identity without an accepted calibration must not publish metres or speeds. Committing a calibration must update every consumer consistently and require valid downstream projection.

**Pinned sources:** [backend/app/storage.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/storage.py) · [backend/app/analytics.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/analytics.py) · [backend/app/workbench/geometry.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/geometry.py) · [backend/app/storage.py:1661–1673](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/storage.py#L1661-L1673)

### B08 — Recompute endpoint can report admission without doing the rebuild

**Priority:** P1  
**Origin:** B08  
**Work package:** H05  
**Status:** OPEN — no fix verified

**Finding.** Storage.recompute_for_match constructs illustrative identities and calls a helper that returns a rebuild list. It then marks the result admitted. The helper does not load a verified reusable detection artifact or execute that downstream rebuilding; several safe-change branches report reuse even without previous evidence.

**Evidence and limits.** Targeted source recheck in this pass. Fresh source recheck of storage.py:1675–1723 confirms only plan construction plus admitted=True; no materialised result is committed by this method. The external report claims a no-detections fixture still reports admitted/reused. The separate legacy reprocess_video_match does perform work.

**Consolidation note.** A planner endpoint may legitimately calculate dependencies without executing. Its response must explicitly be a plan and must not claim artifact reuse or rebuilding that never occurred.

**Required change.** Distinguish plan_recompute from execute_recompute. An executed receipt must identify the input artifact actually reused and the output generation actually committed. Missing cache material must produce a miss or an explicit refusal, never success metadata.

**Acceptance test.** Change calibration and assert output pitch positions change without detector calls. Remove the cache artifact and verify that reuse is not reported. Check returned generation IDs against stored artifacts.

**Pinned sources:** [backend/app/storage.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/storage.py) · [backend/app/video_pipeline.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/video_pipeline.py) · [backend/app/workbench/cache.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/cache.py) · [backend/app/storage.py:1675–1723](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/storage.py#L1675-L1723)

### B09 — Cache identities contain placeholder inputs

**Priority:** P1  
**Origin:** B09  
**Work package:** H05  
**Status:** OPEN — no fix verified

**Finding.** Several runtime identities use interval 0..0, model identifiers such as unspecified or weights-v1, and a decoder name rather than a build/version identity. Probe failure can substitute an all-zero source digest. These do not distinguish the full set of inputs that determine detections.

**Evidence and limits.** Targeted source recheck in this pass. Freshly rechecked placeholder fields in Storage.recompute_for_match and video_pipeline._sampling_and_cache. This establishes an incomplete identity contract, not an observed wrong-cache import.

**Consolidation note.** Do not put calibration in the immutable image-detection key simply to force invalidation. Use separate detection, tracking, projection, reviewed-event and report identities with their actual dependencies.

**Required change.** Build identities from verified source hash, source stream/interval, weights digest, preprocessing/class map, precision, decoder/runtime build and temporal policy. Keep calibration out of image-detection identity but include it in projected-position identity. An unknown identity must disable reuse.

**Acceptance test.** Changing each relevant input must invalidate its own layer. A report-only change must preserve detection identity. Missing source/model identity must never collide with another admitted run.

**Pinned sources:** [backend/app/video_pipeline.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/video_pipeline.py) · [backend/app/storage.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/storage.py) · [backend/app/workbench/cache.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/cache.py) · [backend/app/video_pipeline.py:94–130](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/video_pipeline.py#L94-L130)

### B10 — Repeated job submission bypasses retry and unknown-outcome safeguards

**Priority:** P1  
**Origin:** B10  
**Work package:** H04  
**Status:** OPEN — no fix verified

**Finding.** retry() rejects unknown outcomes and applies a maximum-attempt limit. submit() can create another attempt when the prior state is failed, cancelled or outcome_unknown, without applying the same restrictions. Public routes and runner admission use submit(), making it an alternate path around the retry rules.

**Evidence and limits.** Targeted source recheck in this pass. Fresh source recheck: workbench/jobs.py:198–218 admits another terminal/unknown attempt through submit(), whereas retry():257–273 blocks unknown outcomes and checks MAX_ATTEMPTS. The external report claims seven attempts despite a configured maximum of three. No remote dispatch or duplicate charge was reproduced in this pass.

**Consolidation note.** Separate the demonstrated ledger admission defect from a billed remote incident. An ordinary idempotent repeat should return the existing request; an authorised retry should be an explicit transition after reconciliation.

**Required change.** One atomic admission operation must handle new submission, idempotent replay and approved retry. Unknown outcomes require provider reconciliation. Enforce attempt and cumulative cost limits before any dispatch.

**Acceptance test.** Repeat the same request after every lifecycle state, including an unknown remote outcome. Verify the existing attempt is returned or admission is refused; no new worker is dispatched without explicit reconciliation.

**Pinned sources:** [backend/app/workbench/jobs.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/jobs.py) · [backend/app/jobs.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/jobs.py)

### B11 — SQLite durability does not eliminate stale in-memory job state

**Priority:** P1  
**Origin:** B11, A5  
**Work package:** H04  
**Status:** OPEN — no fix verified

**Finding.** The SQLite ledger retains mutable in-memory snapshots per instance and _persist writes every cached request, attempt and cost entry back using INSERT OR REPLACE. Constructor reconciliation can classify a live owner’s running job as outcome_unknown without a lease check. Another stale instance can overwrite newer state. In addition, every mutation performs work proportional to loaded historical rows, so the persistence cost grows with history.

**Evidence and limits.** Targeted source recheck in this pass. Freshly rechecked _persist, reconcile_after_restart and transition. The external reviewer reports a live-job reclassification followed by a stale overwrite. O(N) writes per transition follows from the loops; no throughput benchmark or long-running deployment measurement was performed.

**Consolidation note.** A5 is an operational extension of this finding. Retaining an audit trail is not a defect; repeatedly rewriting it is. Adding a SQLite file did not solve concurrency ownership.

**Required change.** Make the database authoritative for each transactional transition. Use conditional updates with expected revision, unique request/attempt sequence constraints, owner leases and heartbeat expiry. Persist only changed rows. Keep historical records for provenance with an explicit retention/archival policy; do not delete history merely to hide write amplification.

**Acceptance test.** Run two actual processes against one ledger. Opening another connection must not mark a live job abandoned. Stale updates must fail predictably, and request IDs must remain unique under contention. Instrument SQL writes: a single transition must not rewrite unrelated historical rows. Exercise orphan recovery only after lease expiry.

**Pinned sources:** [backend/app/workbench/jobs.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/jobs.py) · [backend/app/storage.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/storage.py) · [backend/app/workbench/jobs.py:165–226](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/jobs.py#L165-L226)

### B12 — Attempt and cost ledgers can disagree

**Priority:** P1  
**Origin:** B12  
**Work package:** H04  
**Status:** OPEN — no fix verified

**Finding.** retry() adds an attempt but no corresponding CostEntry; submit() adds a full-budget reservation again on some resubmissions. Summaries derive attempt counts from cost entries and turn an all-unknown actual-cost set into actualTotal=0.0. The ledger therefore mixes logical-job reservation, attempt history and settled charges without a consistent accounting contract.

**Evidence and limits.** Targeted source recheck in this pass. The attempt/cost divergence is directly visible in the rechecked submit/retry methods. The external reviewer reports two attempts with one cost entry and names a test asserting reservedTotal remains 1.25 after retry. That test body and the external log were not independently retrieved in this pass.

**Consolidation note.** Correction to the second review’s proposed test change: reservedTotal staying constant is not inherently an incorrect assertion. Rewrite the accounting model and tests around explicit semantics, not around mechanically charging the full budget for each retry.

**Required change.** First specify the unit of reservation: one logical-job budget or per-attempt allocation. A fixed total reservation across retries can be correct; do not automatically reserve the whole budget again. Track each attempt and its uncertain/settled charge separately, enforce the cumulative authorisation atomically, and represent unsettled actual spend as unknown rather than zero. Release reservations only when safe.

**Acceptance test.** Assert a logical job never exceeds its authorised cumulative spend; every attempted execution is represented; unknown spend stays unknown; cancellation does not erase incurred cost; repeating an idempotency key does not duplicate reservation. A retry can consume only remaining authorised capacity. Test both settled failures and outcome-unknown failures.

**Pinned sources:** [backend/app/workbench/jobs.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/jobs.py) · [backend/app/main.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/main.py)

### B13 — Legacy LLM analysis bypasses the new policy layer

**Priority:** P1  
**Origin:** B13, A7  
**Work package:** H01  
**Status:** OPEN — no fix verified

**Finding.** The legacy /api/matches/{id}/analysis/{type} handler selects body.provider before the stored llmProvider preference and calls run_analysis directly. The cloud adapter requires a configured key but this path does not enforce match cloudPermission, processing scope, allowed models or a cost reservation through the newer assistance policy. A request selecting cloud can consequently enter that path for a local-preference match when credentials and the provider are available.

**Evidence and limits.** Targeted source recheck in this pass. Fresh source recheck of main.py:1571–1619 confirms the override and direct call. The provider implementation was inspected in the original pinned audit. No API key was accessed and no cloud call was made. A7 is the same policy-bypass path, not another independently counted defect.

**Consolidation note.** Overriding a UI/provider preference is not intrinsically a security defect. Bypassing authoritative consent and spending policy is. This is conditional on reachable endpoint/runtime credentials, not a demonstrated remote attack or expenditure.

**Required change.** Make a single provider-execution service the unavoidable boundary for all callers. Resolve server-owned consent, processing scope, model allowlist, approved evidence, budget and deadline before any network call. Treat a request provider field only as a preference. Deny disallowed processing before serialization/upload and enforce the same rule for CLI/worker paths.

**Acceptance test.** Inject a provider spy that cannot perform network I/O. A local-only, cloudPermission=False match must never reach it even with body.provider=cloud and fake credentials. Test every public analysis entry point, authorised positive control, unknown provider, exhausted budget and stale evidence.

**Pinned sources:** [backend/app/main.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/main.py) · [backend/app/llm.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/llm.py) · [backend/app/provider_adapters.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/provider_adapters.py) · [backend/app/schemas.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/schemas.py) · [backend/app/main.py:1571–1619](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/main.py#L1571-L1619)

### B14 — Provider response is labelled grounded without validating its evidence

**Priority:** P1 before enabling providers  
**Origin:** B14  
**Work package:** H01  
**Status:** OPEN — no fix verified

**Finding.** AssistanceRouter validates supplied evidence IDs before provider execution, but not the IDs in the actual returned payload. It attaches GROUNDED when that payload merely contains an evidence key. Removing top-level metric-name keys does not validate numbers embedded in narrative or nested structures.

**Evidence and limits.** Targeted source recheck in this pass. Fresh source recheck of assistance.py:277–329 confirms that only top-level metric keys are stripped after execution and an evidence key triggers GROUNDED. The external report claims fabricated and cross-match IDs were accepted. The in-process workbench router’s provider-disabled default does not protect the separate legacy execution path.

**Consolidation note.** ID existence is necessary but not sufficient for grounding. Verify generation/match scope and structured numerical consistency; label interpretive narrative separately. Full semantic correctness of free text is not established by a JSON-schema check.

**Required change.** Validate the returned schema and resolve each reference against the exact permitted match generation. Reject nonexistent, cross-match, superseded or disallowed evidence. Verify structured numeric claims; label tactical interpretation separately from measurements.

**Acceptance test.** Return a fabricated ID, an ID from another match, a wrong number and a stale ID from a fake provider. None may become an accepted grounded report.

**Pinned sources:** [backend/app/workbench/assistance.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/assistance.py) · [backend/app/ai_policy.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/ai_policy.py) · [backend/app/workbench/assistance.py:277–329](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/assistance.py#L277-L329)

### B15 — Legacy offside and spacing still delegate measurement to an LLM

**Priority:** P2  
**Origin:** B15  
**Work package:** H01  
**Status:** OPEN — no fix verified

**Finding.** The legacy prompt still asks the model for a boolean offside answer based on the last defender and for a numeric spacing width. The disclaimer is valuable but does not make this a reliable measurement path. An existing deterministic geometry review helper offers a better boundary.

**Evidence and limits.** Original pinned-source inspection retained; second-review cross-check. Confirmed prompt and provider dispatch behaviour; no officiating accuracy is claimed or established.

**Consolidation note.** Keep this P2 while explicitly limited to review-only illustration and disabled as a ruling. It becomes a release blocker for any advertised authoritative officiating/measurement feature. The original deterministic helper also remains review-only, not a certified replacement.

**Required change.** Calculate spacing from explicitly defined pitch axes in Python. Return offside-position review evidence with uncertainty and no official-decision boolean. Use models only to explain accepted geometry and visible limitations.

**Acceptance test.** Disable all providers and verify geometry/spacing review still works. Insufficient opponents, missing ball/touch timing and unknown calibration must yield unknown or review-only output.

**Pinned sources:** [backend/app/llm.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/llm.py) · [backend/app/main.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/main.py) · [backend/app/workbench/geometry.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/geometry.py)

### B16 — Video identity probes load entire files into memory

**Priority:** P1 for long recordings  
**Origin:** B16, A4  
**Work package:** H06  
**Status:** OPEN — no fix verified

**Finding.** OpenCV/FFprobe probing and proxy identity checks hash complete path.read_bytes() buffers. Probes can run repeatedly. The injected-frame FFmpeg branch additionally uses path.read_bytes()[:1], which still reads the entire file before slicing one byte. These are avoidable allocations; the test/injected branch and production probe paths should be distinguished.

**Evidence and limits.** Targeted source recheck in this pass. The injected branch and probe hashing were freshly rechecked in media.py:208–217; additional production hashing sites remain supported by the original source inspection. A4 is an instance of B16, not another root finding. The external reviewer reports repeated proxy hashing; no memory benchmark was run here.

**Consolidation note.** Reading a file into memory does not prove an out-of-memory failure happened. Peak overhead is source-size dependent; measure the real pipeline after the change. Preserve verification of source immutability while removing duplicate I/O.

**Required change.** Hash using bounded streaming reads with stable file identity checks; reuse the content-addressed result for immutable sources. Remove the injected branch’s unnecessary read or use an actual one-byte stream read if it has a documented purpose. Apply one implementation to probe/proxy/cache callers and retain the existing secure remote hashing patterns.

**Acceptance test.** Hash and probe a large synthetic/local file under a strict resident-memory cap. Peak additional memory should be bounded independently of file size.

**Pinned sources:** [backend/app/workbench/media.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/media.py) · [backend/app/video_pipeline.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/video_pipeline.py) · [backend/app/remote_worker.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/remote_worker.py) · [backend/app/workbench/media.py:208–217](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/media.py#L208-L217)

### B17 — FFmpeg stdout/stderr handling risks deadlock and unbounded memory

**Priority:** P1 for the FFmpeg challenger  
**Origin:** B17  
**Work package:** H06  
**Status:** OPEN — no fix verified

**Finding.** The real FFmpeg decoding path drains raw stdout while parsing showinfo from stderr. If the current timestamp is missing, a fallback calls stderr.read() to EOF while the child can still be producing stdout. This can deadlock through pipe backpressure. Diagnostic bytes accumulate without a bound and are repeatedly re-joined/re-parsed, creating potentially quadratic total work. Decoder exit status is not validated before accepting the end of the stream.

**Evidence and limits.** Targeted source recheck in this pass. Fresh source recheck of media.py:228–307 confirms the blocking read, accumulation and process-finalisation behaviour. Neither this pass nor the supplied report demonstrates a real-FFmpeg deadlock. The supplied review correctly calls it a race, not a guaranteed outcome.

**Consolidation note.** A fast successful short decode would not refute this race. O(N²) is a source-level growth risk under accumulation, not a measured whole-match performance result.

**Required change.** Use bounded concurrent stdout/stderr draining with explicit frame/timestamp correlation and prompt cancellation, or a decoder binding with structured timestamps. Parse incrementally, retain bounded diagnostics, check normal exit versus partial/truncated output, and ensure killed processes are reaped and resources closed.

**Acceptance test.** Run actual FFmpeg on small generated CFR/VFR clips and controlled stalled/failed processes. Delay stderr, fill stdout, cancel during blocking I/O, truncate input and force nonzero exit. Establish timeouts, bounded memory and exact frame/PTS correspondence without relying only on BytesIO.

**Pinned sources:** [backend/app/workbench/media.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/media.py) · [backend/tests/test_ga_v11_production_gaps.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/tests/test_ga_v11_production_gaps.py) · [backend/app/workbench/media.py:228–307](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/media.py#L228-L307)

### B18 — The wrapper overwrites measured run counters with a fresh zero audit

**Priority:** P1 for performance claims  
**Origin:** B18  
**Work package:** H05  
**Status:** OPEN — no fix verified

**Finding.** run_guerilla returns a populated fourRates dictionary from its live sampling audit. process_video_input then payload.update()s the result of _sampling_and_cache(), which creates a new SamplingAudit with untouched counters and returns another fourRates. The measured top-level counts are overwritten. Other adapter counters count boxes rather than model invocations, and declared CPU/backend labels are not reliable measurements of actual execution.

**Evidence and limits.** Targeted source recheck in this pass. Fresh source recheck links run_guerilla.py:8779–8800 to video_pipeline.py:83–128. The external reviewer reports a 250-decoded/50-exported fixture published as 0/0. This full wrapper reproduction was not rerun here. An additional directly visible issue in the same receipt family assigns decodeAnchors.middle and .end the same last-export timestamp.

**Consolidation note.** This is more specific than “counts may be inaccurate”: the top-level overwrite is directly present. It does not establish that all underlying counters were fully correct before overwriting; recovery invocations and box counts still need validation.

**Required change.** Publish one measured receipt per actual run and validate it against its producer. Keep declared policy metadata in a separate object that cannot overwrite measurements. Define and instrument frame counts, model calls, batch sizes, tracker updates, hardware and source anchors independently. Use null/not-recorded rather than synthetic zero values.

**Acceptance test.** A wrapper around a known producer result must preserve every measured count and provenance field. On a real short video, instrument primary/recovery model invocations and reconcile all API/artifact views. Check that beginning/middle/end anchors are real selected timestamps, not duplicate placeholders.

**Pinned sources:** [backend/app/video_pipeline.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/video_pipeline.py) · [backend/run_guerilla.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/run_guerilla.py) · [backend/app/processor.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/processor.py) · [backend/app/workbench/perception.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/perception.py) · [backend/run_guerilla.py:8779–8806](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/run_guerilla.py#L8779-L8806) · [backend/app/video_pipeline.py:83–150](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/video_pipeline.py#L83-L150)

### B19 — PTS support is improved but source-clock fidelity is incomplete

**Priority:** P1 for evaluation alignment  
**Origin:** B19  
**Work package:** H06  
**Status:** OPEN — no fix verified

**Finding.** The code now prefers decoder timestamps, including OpenCV presentation times. Remaining issues include rounding exported seconds to two decimals, constructing FFmpeg integer PTS using the denominator without the numerator, and defining a so-called source grid relative to the previously exported frame rather than an explicit absolute grid origin.

**Evidence and limits.** Targeted source recheck in this pass. Fresh recheck of media.py:290 confirms PTS reconstruction uses only the time-base denominator. The original audit inspected two-decimal export rounding and last-export-relative sampling. The external reviewer gives time_base=1001/30000, PTS=30: t=1.001 seconds is converted back to 30030 rather than 30.

**Consolidation note.** The arithmetic relation is t=PTS*num/den and PTS=t*den/num. Preserve original integer PTS where possible. Rounding is acceptable for display only. Constant-rate short clips can look correct while VFR/fractional and aligned-evaluation cases fail.

**Required change.** Retain original integer PTS plus rational time base and source-global frame identity. Define the sampling grid origin and tie-breaking policy. Separate display rounding from canonical time. Missing timestamps must carry an explicit unmeasured state.

**Acceptance test.** Use fractional-rate, VFR, non-unit time-base numerator, duplicate/missing PTS and off-grid clip fixtures. Exported identities must match independently specified expected source timestamps.

**Pinned sources:** [backend/app/workbench/media.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/media.py) · [backend/run_guerilla.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/run_guerilla.py)

### B20 — Perception adapters mix real wrapping with metadata-only behaviour

**Priority:** P2  
**Origin:** B20  
**Work package:** H06  
**Status:** OPEN — no fix verified

**Finding.** PreprocessorAdapter returns crop/resize metadata without performing those operations. Its RGB swap loops over bytes in Python. TrackerAdapter.associate is a simple optional-IoU association, not BoTSORT; when invoked without prior tracks its IDs incorporate each frame. The core has genuine Ultralytics/BoTSORT tracking, but some newly produced adapter objects do not preserve its semantics.

**Evidence and limits.** Original pinned-source inspection retained; second-review cross-check. Confirmed adapter behaviour. Do not conclude that the whole application lacks real tracking.

**Consolidation note.** Do not describe the actual core tracker as fake: its Ultralytics/BoTSORT calls are real. Rename metadata-only planning adapters or implement their promised operations, and preserve the core track identities rather than inventing a conflicting second stream.

**Required change.** Expose actual native preprocessing and the real tracker output through a stable adapter. Name implementations honestly and test pixel values, geometry and identity continuity rather than descriptor flags. Keep fixture-only adapters outside production output.

**Acceptance test.** Feed a tracked player through multiple frames and assert stable source track IDs. Compare crop/resize pixels and inverse box transforms with a reference implementation.

**Pinned sources:** [backend/app/workbench/perception.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/perception.py) · [backend/app/video_pipeline.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/video_pipeline.py) · [backend/run_guerilla.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/run_guerilla.py)

### B21 — GPU decode capability is incorrectly coupled to detector inference capability

**Priority:** P2  
**Origin:** B21  
**Work package:** H06  
**Status:** OPEN — no fix verified

**Finding.** DetectorAdapter selects CPU when CUDA is requested but video_engine_capability is false. Hardware video decoding and CUDA tensor inference are separate capabilities; this policy can disable valid GPU inference on CPU-decoded frames. The memory contracts are presently CPU byte buffers, not proof of a GPU-resident zero-copy chain.

**Evidence and limits.** Original pinned-source inspection retained; second-review cross-check. Confirmed policy coupling; no performance result was measured.

**Consolidation note.** Validate decoder, tensor-runtime and encoder capability separately. CPU decode plus GPU inference is a legitimate supported configuration. A host-to-device copy may be acceptable before a GPU-resident pipeline is justified.

**Required change.** Probe decode, preprocessing, inference and encode independently. Support CPU decode plus GPU inference. Add a GPU-resident path only when an end-to-end benchmark establishes its benefit and actual capability.

**Acceptance test.** Test capability combinations independently and verify selected runtime execution, not just a returned backend string.

**Pinned sources:** [backend/app/workbench/perception.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/perception.py) · [backend/app/workbench/media.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/media.py)

### B22 — Detection scorer can credit a wrong-class prediction

**Priority:** P1 before using benchmark scores  
**Origin:** B22  
**Work package:** H03  
**Status:** OPEN — no fix verified

**Finding.** score_detections filters ground-truth labels by task but does not enforce matching detection kind. A ball detection can overlap and match a player label in a player-coverage test. The localisationErrorPx field is the mean of 1-IoU, which is dimensionless rather than pixels.

**Evidence and limits.** Original pinned-source inspection retained; second-review cross-check. Confirmed scorer defects in the new workbench helper. This is not an assertion that every other evaluation script uses the same implementation.

**Consolidation note.** Scope this defect to the inspected workbench scorer; do not claim every evaluator or existing score in the repository is corrupt. Decide whether non-task detections are ignored or counted as errors, but never allow them to match a different-class label. 1−IoU can remain a named dimensionless diagnostic, not a pixel error.

**Required change.** Match by class and frame with a declared confidence/matching protocol. Compute genuine pixel localisation error or rename the metric. Test score invariance and compare to an independent evaluator. Group tiled suppression by frame and compatible class.

**Acceptance test.** A perfectly overlapping wrong-class detection must produce zero true positives. Known centre offsets must produce the expected pixel error. Mixed-frame/class tiled detections must not suppress one another.

**Pinned sources:** [backend/app/workbench/perception.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/perception.py)

### B23 — Combined shot quality can be published as one team's value

**Priority:** P1 for report correctness  
**Origin:** B23  
**Work package:** H03  
**Status:** OPEN — no fix verified

**Finding.** _summary_metric_availability stores experimental_shot_quality as the sum of both teams' values. The HTML fallback summary calls _format_available_metric with this record while describing the result as my team's shot quality. With values 0.4 and 0.6, that path can present 1.0 for my team. An aggregate score is also labelled with unit probability despite potentially exceeding one.

**Evidence and limits.** Original pinned-source inspection retained; second-review cross-check. Confirmed producer/consumer mismatch. The numerical example is illustrative, not a measured match.

**Consolidation note.** The demonstrated producer/consumer mismatch is independent of model accuracy. A sum of shot probabilities would normally be an expected-count quantity, not one probability; these particular handcrafted values are not calibrated probabilities in the first place. Use explicit team/interval scope and experimental-score units.

**Required change.** Use team-scoped metric IDs and explicit aggregation units. Keep per-shot heuristic scores separate from sums. Have every export consume the same typed metric record instead of mixing a shared record with a legacy field fallback.

**Acceptance test.** With distinct team values, assert correct values across HTML, JSON, CSV, dashboard and provider context. Test one team unmeasured and both teams unmeasured.

**Pinned sources:** [backend/app/analytics.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/analytics.py) · [backend/app/report_export.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/report_export.py)

### B24 — Several football metrics remain heuristics without complete eligibility semantics

**Priority:** P2  
**Origin:** B24  
**Work package:** H03  
**Status:** OPEN — no fix verified

**Finding.** Possession uses controlled-frame counts rather than elapsed eligible time. Formation segmentation can bridge skipped unknown frames. Defensive-line logic makes player-role/visibility assumptions; line-breaking counts opponents passed in X rather than establishing defensive lines. Physical distances use fixed pitch dimensions despite configurable dimensions. These may be useful provisional signals but are not automatically validated professional measurements.

**Evidence and limits.** Original pinned-source inspection retained; second-review cross-check. Confirmed definitions and modelling limitations, not evidence that every estimate is wrong.

**Consolidation note.** Frame-count possession is a valid equivalent of time-share only when eligible samples carry equal duration. A 105×68 default is legitimate when declared and applicable; ignoring configured dimensions is the defect. Treat this item as explicit metric/camera scope work, not proof that every current heuristic is useless.

**Required change.** Specify each metric's units, denominator, interval eligibility, player visibility and role requirements. Use time-weighted possession where sampling varies. Break formation segments across unknown periods. Keep candidate/provisional labels and withhold physical values when prerequisites fail.

**Acceptance test.** Use unequal frame durations, missing defenders, unknown intervals, nonstandard pitch sizes and period changes. Verify definitions and coverage before comparing values to football reference labels.

**Pinned sources:** [backend/app/analytics.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/analytics.py) · [backend/app/schemas.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/schemas.py) · [backend/app/workbench/evidence.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/evidence.py)

### B25 — Tactical search relaxes explicitly requested filters

**Priority:** P2  
**Origin:** B25  
**Work package:** H05  
**Status:** OPEN — no fix verified

**Finding.** The typed query executor allows missing team values to satisfy an explicit team filter and missing/zero periods to satisfy a requested half. Successor search does not establish the successor team/period required by richer questions. The regex searches for a recognised substring, so unsupported qualifications can be silently omitted.

**Evidence and limits.** Original pinned-source inspection retained; second-review cross-check. Confirmed query semantics. Rejected events are now excluded, which is an improvement.

**Consolidation note.** Exact filters must exclude unknown team/period values unless the caller explicitly requests unknowns. More advanced successor queries require their own team/period scope. Do not silently simplify unsupported natural-language qualifiers into a broader query.

**Required change.** Return the interpreted filter visibly, reject unsupported constraints and treat unknown fields as non-matches by default for explicit filters. Represent successor team, period and time-window constraints structurally.

**Acceptance test.** Ask for our second-half turnovers followed by opponent shots. Unknown-half events, wrong-team successors and first-half successors must not appear as exact matches.

**Pinned sources:** [backend/app/workbench/assistance.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/assistance.py) · [backend/app/storage.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/storage.py)

### B26 — Local trust assumptions are not hosted authentication

**Priority:** P1 before public hosting  
**Origin:** B26  
**Work package:** H01  
**Status:** OPEN — no fix verified

**Finding.** The application has useful origin and host checks and an explicitly unimplemented signed-access path. Local access decisions can default to the object's tenant when no authorization is supplied. Deployment-boundary headers and policy helper outputs are not proof that the process is safely bound or that a remote caller is authenticated.

**Evidence and limits.** Original pinned-source inspection retained; second-review cross-check. Deployment limitation, not a demonstrated breach of a correctly loopback-bound installation.

**Consolidation note.** This is a boundary/release limitation, not an observed breach of a correctly loopback-bound private deployment. TrustedHost and Origin checks remain useful but cannot replace server-owned deployment configuration, authentication and per-object authorisation for hosting.

**Required change.** Keep local-only binding enforced by server configuration. Before hosting, add real authentication, server-derived tenant identity, authorization on all object/list/export/WebSocket routes, quotas and audit records. Move diagnostic endpoints behind an internal boundary.

**Acceptance test.** Run an explicit deployment-mode matrix. Test no-token, forged boundary/tenant headers, cross-match access, exports and WebSocket paths. Public startup must refuse insecure configuration.

**Pinned sources:** [backend/app/main.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/main.py) · [backend/app/workbench/access.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/access.py) · [backend/app/settings.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/settings.py)

### B27 — Decoder command checks do not establish a decoder sandbox

**Priority:** P2  
**Origin:** B27  
**Work package:** H01  
**Status:** OPEN — no fix verified

**Finding.** Argument and protocol-string checks are useful, but passing network_enabled=False into a policy helper does not disable networking in the launched process. File content and decoder resource consumption remain separate trust concerns. Clip export checks cancellation before a blocking subprocess call, not throughout the operation.

**Evidence and limits.** Targeted source recheck in this pass. Missing assurance boundary; no malicious media was executed in this audit.

**Consolidation note.** The proposed protection is real process/container resource and network isolation where required, not a larger list of shell characters. No decoder exploit was tested. A3’s executable-path inconsistency is separately tracked as B34.

**Required change.** For untrusted uploads, constrain decoder protocols and process/network capabilities, filesystem scope, CPU/memory/time and output sizes. Implement cancellation and inspect exit status. Distinguish fast stream-copy exports from a separately validated frame-exact export path.

**Acceptance test.** Use controlled malformed/truncated media, excessive-output scenarios and cancellation. Verify actual process termination and allowed filesystem/network behaviour, not only an admitted flag.

**Pinned sources:** [backend/app/workbench/access.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/access.py) · [backend/app/workbench/media.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/media.py)

### B28 — Configured schema fields exceed the guarantees enforced by the runtime

**Priority:** P2  
**Origin:** B28  
**Work package:** H03  
**Status:** OPEN — no fix verified

**Finding.** The main schemas and workbench schemas duplicate concepts but do not impose the same restrictions. Core coordinates, periods, metric status strings and matrices lack some necessary finite/range/order checks. A configuration field for pitch size or periods does not mean every analytics consumer uses it.

**Evidence and limits.** Original pinned-source inspection retained; second-review cross-check. Confirmed design gap in the inspected declarations and consumers; not a comprehensive fuzzing result.

**Consolidation note.** Tighten contracts with versioned migration: reject non-finite coordinates, malformed transforms and reversed/overlapping periods where prohibited without silently changing legacy coordinate semantics. Validation must be applied at the actual execution boundary, not just in an unused model class.

**Required change.** Consolidate shared domain types with explicit coordinate space and units. Validate finite values, interval order, matrix shape, status enums and cross-field prerequisites. Keep permissive compatibility parsing at the import boundary, not in canonical data.

**Acceptance test.** Property-test NaN/infinity, reversed intervals, unknown enum values, malformed matrices and impossible dimensions. Verify invalid imports cannot become accepted canonical evidence.

**Pinned sources:** [backend/app/schemas.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/schemas.py) · [backend/app/workbench/contracts.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/contracts.py) · [backend/app/workbench/geometry.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/geometry.py)

### B29 — Evaluation readiness helpers are not live evaluation results

**Priority:** P1 for promotion claims  
**Origin:** B29  
**Work package:** H05  
**Status:** OPEN — no fix verified

**Finding.** current_repository_evaluation_gate hardcodes zero complete tasks. score_hota_idf1 can return scored=True with HOTA and IDF1 still None when prerequisite booleans pass. Several promotion/quality receipts are constructed from placeholder timing, hardware or coverage fields. These are planning/checking helpers, not measured results.

**Evidence and limits.** Original pinned-source inspection retained; second-review cross-check. Confirmed metadata semantics. The inspected status record also reports missing independent labels, but no private annotation service was queried to verify external progress.

**Consolidation note.** A hardcoded zero gate is conservative but not a live label inventory. A boolean prerequisite pass cannot be called scored while scores are null. Do not infer the current external CVAT/database state from this helper or from historical status prose.

**Required change.** Use distinct prerequisite, executed and scored states. Derive current readiness from versioned artifact manifests and actual scorer outputs. Never mark a task scored merely because the arguments are admissible. Publish unknown performance as null.

**Acceptance test.** Prerequisites present but scorer not executed must remain unscored. A real score requires prediction/label digests, scorer version, source identity and numeric results reproducible from those artifacts.

**Pinned sources:** [backend/app/workbench/evaluation.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/evaluation.py) · [backend/app/storage.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/storage.py) · [docs/status/current.md](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/docs/status/current.md)

### B30 — Training support is useful but not yet a complete model-promotion workflow

**Priority:** P2  
**Origin:** B30  
**Work package:** H07  
**Status:** OPEN — no fix verified

**Finding.** fine_tune is a real Ultralytics training wrapper with seeds, validation and saved weights. Its function and CLI choose different default base models. The quality gate uses a simple line-based YAML parser and takes separate maxima across epochs for validation metrics; those maxima need not describe the checkpoint that is promoted. A nonzero detection on a positive image is a smoke check, not localisation accuracy.

**Evidence and limits.** Original pinned-source inspection retained; second-review cross-check. Confirmed implementation details. The gate's own text appropriately describes a nonzero-signal check; it should not be promoted into a production-accuracy claim.

**Consolidation note.** Independent maxima across epochs can be labelled a training-progress diagnostic; they must not be published as the chosen checkpoint’s joint performance. The nonzero-positive detector check remains a useful smoke gate, not a calibrated accuracy or localisation test.

**Required change.** Unify model defaults; validate structured dataset manifests and split independence; bind metrics to the exact checkpoint; hash data, configuration and outputs. Evaluate the candidate on held-out camera-stratified data before changing production weights.

**Acceptance test.** Verify train/validation source separation, identical configuration under CLI/API, reproducible metadata and promotion metrics bound to the exact saved weights rather than unrelated best epochs.

**Pinned sources:** [backend/train_custom.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/train_custom.py) · [backend/app/training_quality_gate.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/training_quality_gate.py)

### B31 — Environment separation is good but platform installation needs explicit profiles

**Priority:** P2  
**Origin:** B31  
**Work package:** H07  
**Status:** OPEN — no fix verified

**Finding.** Runtime and ML dependencies are split and pinned. The ML file includes unconditionally listed NVIDIA CUDA libraries and Triton, so it should not be treated as a single portable installation recipe for both a Mac workstation and Linux GPU workers. Direct version pins alone are not a complete transitive environment lock.

**Evidence and limits.** Targeted source recheck in this pass. Original dependency-file assessment retained. This pass freshly read tests/conftest.py and .github/workflows/ci.yml. The workflow installs the editable project plus requirements-dev.txt, not only the dev file. The stubs are installed only after ModuleNotFoundError, not unconditionally for installed pandas/cv2.

**Consolidation note.** Correct the second review’s overstatement about CI. Conditional stubs still mean a passing profile need not execute the real ML stack, but it is not accurate to assert that all three packages are always mocked. No clean platform install, package vulnerability scan or transitive-lock reproduction was performed here.

**Required change.** Maintain small API, CPU-CV/macOS and Linux-CUDA profiles, with tested locks and container/build identities. Audit licences and vulnerabilities separately. Do not upgrade the whole stack as a substitute for fixing logic.

**Acceptance test.** Clean-install and startup tests per supported platform/profile. Ensure the API can operate without loading the training/GPU stack and that worker locks reproduce the admitted runtime.

**Pinned sources:** [backend/requirements-runtime.txt](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/requirements-runtime.txt) · [backend/requirements-ml.txt](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/requirements-ml.txt) · [backend/daytona_worker/requirements.lock](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/daytona_worker/requirements.lock) · [backend/tests/conftest.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/tests/conftest.py) · [.github/workflows/ci.yml](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/.github/workflows/ci.yml)

### B32 — Current CI success does not cover full video/GPU acceptance

**Priority:** P1 acceptance gate  
**Origin:** B32  
**Work package:** H07  
**Status:** OPEN — no fix verified

**Finding.** The pinned main's code-only verification job passed. That mode excludes test_run_guerilla.py, test_gpu_worker.py and several artifact-dependent suites, and exits before release gates. The inspected production-gap tests use fake frames/subprocesses and in-process reconstruction for several checks. Those are useful unit tests but do not establish pipe behaviour, genuine process-crash recovery or real-footage accuracy.

**Evidence and limits.** Targeted source recheck in this pass. The GitHub verify-job step metadata was re-fetched and reports success for the code-only step. The externally reported 3329 passed / 5 skipped / 0 failed backend run and 15 reproductions are preserved as external claims because their /tmp scripts/logs were not supplied. No local full repository suite was executed in this consolidation pass.

**Consolidation note.** Do not dismiss thousands of tests as worthless or assume the whole suite only tests helpers. The defensible conclusion is that important real-media, cross-component and multi-process invariants are not established by this green profile. conftest also defaults GA_FLAG_LEFTOVER_HTTP to 1; test default-off deployment behaviour explicitly.

**Required change.** Keep fast CI, add an artifact-enabled integration lane and a small real-media lane, then a separately authorised GPU/football acceptance lane. Use independent behavioural assertions, not only assertions that metadata flags exist.

**Acceptance test.** Record exactly which suite/profile passed at which commit. Require real subprocess restart, actual FFmpeg fixtures, cross-process ledger tests, end-to-end corrections and independent football evaluation before expanding claims.

**Pinned sources:** [scripts/verify.sh](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/scripts/verify.sh) · [backend/tests/test_ga_v11_production_gaps.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/tests/test_ga_v11_production_gaps.py) · [.github/workflows/ci.yml](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/.github/workflows/ci.yml) · [backend/tests/conftest.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/tests/conftest.py)

### B33 — Missing manual points are replaced with an invented unit-square calibration

**Priority:** P1 for calibration/publication  
**Origin:** A2  
**Work package:** H03  
**Status:** OPEN — no fix verified

**Finding.** Storage.calibration_for_match replaces any non-four-point manual configuration with (0,0),(1,0),(1,1),(0,1), builds a pitch homography from those placeholder image points, then evaluates supplied holdouts and can persist calibration review state. There is no explicit source-camera calibration backing that fallback. This is distinct from B05: here a matrix exists, but it was invented rather than established from the recording.

**Evidence and limits.** Targeted source recheck in this pass. Fresh source recheck of storage.py:2399–2465. The second reviewer identifies the same branch. A full endpoint reproduction was not performed in this pass; the placeholder construction and its downstream evaluation are directly present.

**Consolidation note.** Do not weaken the holdout requirement to make this pass. B05, B06, B07 and B33 should be fixed in one calibration work package but remain separately testable counterexamples.

**Required change.** Require a validated source-bound manual or automatic calibration revision before holdout evaluation. Missing/invalid points must produce calibration-unavailable or a setup error. Any explicitly supported normalised-coordinate convention must be declared and transformed to source pixels, not assumed from a default unit square.

**Acceptance test.** A match with no manual points and no accepted automatic transform must reject commit/publication even if supplied holdouts agree with the unit-square fallback. Test genuine source-pixel points, an explicitly declared normalised-input positive case if supported, custom pitch size, invalid point counts and transformed/rotated video.

**Pinned sources:** [backend/app/storage.py:2399–2465](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/storage.py#L2399-L2465) · [backend/app/workbench/geometry.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/geometry.py)

### B34 — Decoder guards disagree on absolute executable paths

**Priority:** P2  
**Origin:** A3  
**Work package:** H06  
**Status:** OPEN — no fix verified

**Finding.** constrained_decoder accepts argv[0] only when it is exactly ffmpeg or ffprobe, while _assert_safe_ffmpeg_argv accepts a configured path whose basename is one of those names. FfmpegProbe supports configured binary paths, but a valid /usr/bin/ffmpeg path is rejected by operations that call both guards.

**Evidence and limits.** Targeted source recheck in this pass. Fresh source recheck of workbench/access.py:153–160 and the FFmpeg invocation path. The basename-aware helper was read in the original pinned audit. The error outcome is inferred from the direct predicate; no system-binary invocation was made.

**Consolidation note.** This is a usability/configuration defect, not proof of a security compromise. It must not be fixed by deleting all decoder admission checks.

**Required change.** Use one trusted-executable resolution/validation service. Resolve a vetted configured binary and pass the approved absolute path consistently. Preserve no-shell execution and any binary provenance requirements. Accepting arbitrary files merely because their basename is ffmpeg is not an adequate security fix.

**Acceptance test.** Default resolved executable and explicitly configured approved absolute path should behave consistently. Reject unapproved locations, look-alike names, missing binaries and disallowed protocols. Test configured ffmpeg and ffprobe separately.

**Pinned sources:** [backend/app/workbench/access.py:153–160](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/access.py#L153-L160) · [backend/app/workbench/media.py](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/media.py)

### B35 — Workbench idempotency conflicts escape as internal-server errors

**Priority:** P2  
**Origin:** A6  
**Work package:** H02  
**Status:** OPEN — no fix verified

**Finding.** The workbench /jobs handler directly calls DurableJobLedger.submit(). A repeated request ID with a different payload raises ValueError, and this handler does not translate it into a declared client/conflict response. Under the standard error path this becomes HTTP 500 instead of a controlled idempotency conflict. Other normal-match routes already catch related conflicts.

**Evidence and limits.** Targeted source recheck in this pass. Fresh source recheck of workbench/routes.py:221–252 and workbench/jobs.py:198–201. No full HTTP request was executed here; the external reviewer also presents A6 as a source finding, not one of its explicitly labelled executable cases.

**Consolidation note.** This handler is also subject to B01’s consolidation. Fix the ledger’s B10 admission semantics as well; returning 409 alone does not prevent duplicate terminal-state submissions.

**Required change.** Translate typed domain conflicts into a stable 409 response through the shared service/router exception mapping. Validate request fields separately. Preserve the original job untouched, do not expose tracebacks or secrets, and do not silently convert a conflict into success.

**Acceptance test.** POST a valid request, then the same ID with a different payload: expect 409, a documented error code, no extra attempt/reservation and the original request unchanged. An exact idempotent repeat should return the original job. Cover both route families.

**Pinned sources:** [backend/app/workbench/routes.py:221–252](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/routes.py#L221-L252) · [backend/app/workbench/jobs.py:198–218](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend/app/workbench/jobs.py#L198-L218)

## 7. Consolidated implementation programme

These seven work packages are the execution plan for the findings, not another seven defects. Their boundary is intentionally smaller than the feature roadmap. One package can close several findings only when each independent counterexample is covered.

### H01 — One provider and deployment-policy boundary

**Items:** B13–B15, B26–B27. **Owner role:** backend/security. **First action:** disable legacy provider execution for real data until it uses the shared guard.

Resolve match rights, authorisation, source generation, allowed provider/model, time limit and budget on the server. Produce an immutable approved evidence package; only that package may reach an adapter. Keep review-only incident illustration separate from numeric/referee decisions. Add a network-denied provider-spy test before implementation so no test can accidentally spend credit.

Deploy locally until hosting is independently accepted. Boundary identity must not be derived from a caller’s declaration that it is loopback. Keep host/origin defences, and require every hosted list/object/export/WebSocket path to enforce the same identity model. Decoder isolation belongs to the process deployment, not merely to an argument validator.

**Exit evidence:** forbidden cloud selection causes zero adapter invocations; authorised selection has a reservation and traceable evidence; unknown/stale/cross-match returned references are rejected; no authoritative offside number comes from a language model.

### H02 — Shared review services and crash-safe corrections

**Items:** B01–B04, B35. **Owner role:** backend/data. **Highest-priority regression:** the same-request raw-row team swap.

Both supported API families must call one review service or the obsolete path must be retired. A durable correction command carries match ID, base generation, expected revision, immutable edit payload, author/provenance and command ID. Do not mark its effects complete merely because history was written.

Materialise edits idempotently over immutable detections, then rebuild a complete derived generation. Reject stale/conflicting edits predictably. Make undo a new command with a defined inverse/base revision; do not mutate the historical decision. Translate conflicts to stable API responses. Preserve raw-row-backed and tracking-input test fixtures as separate product cases.

**Exit evidence:** correction → raw-row rebuild → fresh-process restart → undo → export is consistent, and killing the worker during application leaves either the old valid generation or the new valid one, never a mixed state. Repeating recovery does not apply a swap twice.

### H03 — Calibration, scoring and metric publication

**Items:** B05–B07, B22–B24, B28, B33. **Owner role:** vision/analytics.

Fix the no-transform and invented-transform branches first. Validate finite dimensions, matrix shape and usable transformation, source binding, validity interval and independent landmark support. Preserve paired residuals through sorting/statistics. A calibration revision and its acceptance record must be one coherent entity consumed by every metric.

Define team/player/interval-scoped metric IDs and units. A total across teams cannot be rendered as one team. Keep raw automated and reviewed-event analytics separate if both are needed. Conditions for physical publication include valid geometry, identity continuity and eligible time—not one boolean alone. Correct the workbench evaluator before using it to select models.

**Exit evidence:** every negative calibration case fails for the correct reason; shuffled labels leave regional results unchanged; wrong-class predictions do not match; all exports agree on team-scoped values/unknown states; custom pitch dimensions and unsupported intervals are handled explicitly.

### H04 — Authoritative jobs, leases and budgets

**Items:** B10–B12. **Owner role:** backend/operations.

Keep SQLite for the local product, but treat it as the state authority. Use transactional admission, conditional transitions and an owner lease. A new reader is not a process-crash detector. Make ordinary repeated submissions idempotent and retries explicit; unknown outcomes require reconciliation with the actual worker/provider.

Choose one logical-job budget contract. Track per-attempt state and charges without repeatedly reserving the whole job allowance by default. Unknown charges remain unknown. Separate cancel_requested, termination_confirmed and cleanup_confirmed. Write only changed rows while retaining immutable history.

**Exit evidence:** two real processes cannot overwrite one another’s newer state; an active job is not abandoned by construction of another object; retries respect cumulative authorisation; unknown remote outcomes cannot allocate duplicate attempts; ledger work per update does not scale with all history.

### H05 — Real recomputation, evidence identity and truthful receipts

**Items:** B08–B09, B18, B25, B29. **Owner role:** backend/analytics.

Separate planning, scheduling, execution and publication. A recompute plan identifies dependencies but cannot claim completed output. An execution must resolve actual input artifacts, preserve appropriate observation identity, apply corrections and commit a new generation. Remove placeholder source/model/interval identities from reuse decisions.

Preserve the producer’s measured runtime receipt. Policy intent, requested hardware and measured execution belong in separate fields. Bind generated reports and accepted metrics to the generation that supports them. Typed search must honour exact filters and visibly reject unsupported natural-language qualifications. Evaluation status must come from actual artifact inventories and executed scorers, not readiness booleans masquerading as scores.

**Exit evidence:** a geometry change produces changed projected coordinates without detector calls when valid detections exist; a cache miss is reported as a miss; counts survive wrappers/export; unsupported filters are not broadened silently; no score is called executed while its values and run receipt are absent.

### H06 — Bounded media and truthful adapters

**Items:** B16–B17, B19–B21, B34. **Owner role:** video/CV.

Centralise streaming source hashing and trusted executable resolution. Preserve the original recording, integer PTS/time base and crop/rotation transforms. Drain FFmpeg pipes concurrently with bounded buffers and explicit termination. A proxy/export must declare its timing/accuracy contract rather than claiming exact cuts by implication.

Adapters must either execute the advertised operation or be explicitly named planning/configuration objects. Preserve core track IDs. Test CPU decode/GPU inference independently from hardware video decode/encode support. Do not promote any GPU-resident or zero-copy claim until actual memory ownership/transfers have been measured.

**Exit evidence:** real generated media completes and cancels correctly; missing timestamps and nonzero exits are visible; large-file hash overhead is bounded; exact timestamp/rate fixtures align; crop/resize changes actual pixels; approved absolute executable paths work consistently.

### H07 — Reproducible environments and acceptance lanes

**Items:** B30–B32. **Owner role:** QA/ML/release.

Maintain distinct API, CPU-CV/macOS and Linux-CUDA installation profiles with tested dependencies. Record when conditional stubs are used. Test the production-default feature flags as well as development surfaces. Bind evaluation to the exact checkpoint, configuration and split—not a set of best values from different epochs.

Retain fast code-only CI. Add artifact-enabled integration, real-media and explicitly authorised GPU/football evaluation lanes. Require source-bound logs and fixtures, not just passing-count summaries. A failed behavioural regression should be fixed by meeting its invariant, not by weakening its expected result to match a helper flag.

**Exit evidence:** clean setup per declared platform, reproducible exact-checkpoint validation, separate reports of software correctness/football accuracy/analyst usefulness, and a reviewed-match pilot completed by the intended analyst without hidden developer intervention.

### Dependencies and order

H01’s provider guard and H03’s false-acceptance/metric fixes can start immediately in parallel with H02’s failing raw-row regression. H04 must finish before unattended paid execution. H05 depends on the shared revision semantics established in H02/H03. H06 can fix bounded hashing and executable validation early, but performance promotion depends on H05 receipts. H07 runs throughout and supplies closure evidence for every package.

Avoid a single unreviewable change that claims all 35 items closed. Prefer small commits tied to explicit IDs, with a final integration PR containing no unrelated feature expansion.

## 8. Target data and execution contracts

### 8.1 Immutable observations plus reviewed generations

```text
Original source / immutable image-space observations
                         |
            versioned analyst commands
                         |
             projection generation N
       calibration → identity/team → ownership
                 → events → metrics
                         |
             evidence-linked report N
```

A generation carries source/observation digests, calibration revision, correction-log head and algorithm/model identities. Frames, reviewed events and metrics published together must refer to that generation. Readers should resolve one active generation at request start.

One practical local design is to write a candidate generation into a new immutable directory, validate it, durably flush its files, then publish its database/pointer revision. Because filesystem and database operations are not one distributed transaction, define recovery for orphaned unpublished directories and pointer/file mismatches. Do not merely rename a file and call every multi-file update atomic. A persistent command/outbox can drive reconciliation idempotently.

### 8.2 Metric contract

Each metric needs its metric ID and definition version; team/player/interval scope; source generation; value or null; units; availability; observed/estimated/reviewed status; eligible/requested duration; exclusions; algorithm/calibration revisions; and uncertainty where supported.

Unknown is not zero. Experimental is not calibrated. Available data is not necessarily scientifically validated. One reviewed player identity is not whole-match identity continuity. A report cannot silently use a legacy numeric field to bypass a withheld canonical record.

### 8.3 Job and money contract

A logical job has a stable request identity, authorisation envelope and budget. Each attempt has its own ID, worker lease, input/output revision, lifecycle and charge state. The API must distinguish reserved, estimated, unsettled, settled and cancelled-with-charges states.

For a chosen reservation model, enforce a documented invariant such as settled cost plus outstanding authorised reservations not exceeding the job authorisation. Define how unknown remote cost conservatively consumes capacity. That is stronger than either “always add a reservation on retry” or “never add one.”

### 8.4 Runtime and evidence receipts

Separate requested policy from observed runtime. A measured receipt must identify the actual source/model/runtime, decoded frames, inference calls and batch sizes, recovery calls, tracker updates, exported samples, timestamp policy, timing boundaries, memory/transfer measurements and committed outputs. Unknown hardware/time/cost remains unknown.

An evidence ID must identify match and generation as well as an observation/event. Reference existence alone does not establish the meaning of a claim. Structured quantities should be independently checked; tactical interpretation remains explicitly interpretive and analyst-reviewable.

## 9. Regression and acceptance matrix

These are required future tests. Except for the separately documented G1–G4 excerpt checks, they were not executed in this consolidation pass.

| ID | Case | Expected invariant | Relevant findings |
|---|---|---|---|
| T01 | Same stored match through both API families | Same data authority or explicit retired-route response | B01, B35 |
| T02 | Raw-row-backed team swap | Changed teams persist before response and after rebuild/restart | B04 |
| T03 | Kill after correction log commit | Recoverable command; no mixed generation or duplicate effect | B02 |
| T04 | Reject/accept/undo a shot | Events, shots, metrics and reports agree on reviewed generation | B03, B23 |
| T05 | Split/join identity then rebuild/undo | Edits and all references remain consistent | B04, B07 |
| T06 | Missing/singular/invented transform | No accepted geometric measurement | B05, B33 |
| T07 | Reorder identical holdouts | Same regional error and acceptance | B06 |
| T08 | Promote identity without calibration | Physical metrics remain unavailable | B07 |
| T09 | Remove or change cache material | No false reuse; only correct layers rebuilt | B08, B09 |
| T10 | Duplicate terminal/unknown submissions | No reconciliation/attempt-limit bypass | B10 |
| T11 | Two processes, live lease, stale write | No lost update or false abandonment | B11 |
| T12 | Retry/cancel with unknown billing | Complete attempt history; cumulative budget; unknown not zero | B12 |
| T13 | Body provider=cloud on local-only match | Zero cloud-adapter invocations | B13 |
| T14 | Fabricated/cross-match/stale model references | Rejected or analyst-review fallback; never GROUNDED | B14 |
| T15 | Large-file hash/probe | Bounded memory and stable source identity | B16 |
| T16 | Real FFmpeg pipe delays/failure/cancel | Bounded completion or explicit error; child reaped | B17, B27 |
| T17 | Producer counters through wrapper/export | Exact measured values preserved; anchors genuine | B18 |
| T18 | VFR, fractional time base, off-grid clips | Exact source identity and declared sampling alignment | B19 |
| T19 | Crop/resize/track adapter contract | Pixels/state actually transformed; core IDs preserved | B20 |
| T20 | CPU decode with GPU tensor runtime | GPU inference not blocked by absent hardware decoder | B21 |
| T21 | Wrong-class and known-offset detections | No cross-class TP; correct localisation units | B22 |
| T22 | Custom pitch and unequal-duration samples | Metric units/duration/eligibility remain consistent | B24, B28 |
| T23 | Unknown fields under explicit search filters | Unknowns excluded unless requested; no silent broadening | B25 |
| T24 | Hosted and production-default configuration | Server-owned auth/deployment policy; route isolation | B26, B32 |
| T25 | Exact checkpoint/split replay | Same evaluation artifact, not per-epoch maxima | B30 |
| T26 | Clean install and actual acceptance lanes | Distinct software, runtime, scientific and analyst results | B29–B32 |
| T27 | Vetted absolute ffmpeg/ffprobe paths | Consistent admission; unapproved binaries refused | B34 |
| T28 | Idempotency payload mismatch | Stable 409, no extra attempt or reservation | B35 |

### Closure rule

A finding is closed only with the fix commit, a behavioural regression that fails on the audited revision for the intended reason, and a pass on the fixed revision in the declared environment. For conditional risks, retain the explicit tested scenario and any remaining platform limits. Changes to schemas/routes require migration and compatibility evidence. A disabled feature can be safely deferred, but is not therefore implemented.

For a mathematical defect, isolated function tests are useful. For application atomicity, use actual processes and persisted artifacts. For a pipe race, use actual subprocess I/O. For ML accuracy, use independent labels. Do not let one evidence class substitute for another.

## 10. Isolated checks actually executed in this pass

The evidence pack contains `geometry_excerpt_probe.py` and its JSON output. It transcribes only `_project` and `evaluate_landmarks` from the pinned source with unchanged function bodies. The surrounding Pydantic objects are replaced with simple fixtures. It performs no repository imports, HTTP requests, GPU work or model calls.

| Case | Observation | Interpretation |
|---|---|---|
| G1 | Missing homography + one holdout → accepted=True, p95M=0 | Confirms the helper’s missing-transform false acceptance. |
| G2 | Reversing two holdouts changes farSideMaxM 10 → 0; p95M remains 10 | Confirms broken association; this particular two-point example does not flip acceptance. |
| G3 | Same 40 holdouts: bad far-side point first → accepted=True; last → accepted=False | Confirms input order can change the actual acceptance gate. True far-side error is 100 in both cases. |
| G4 | Correct identity transform and matching point → accepted=True, p95M=0 | Positive control for the excerpt execution, not an endorsement of a one-point calibration policy. |

These four cases are **not** four full backend reproductions and must not be added to the external reviewer’s 15 as a combined integration-test total. They support B05/B06 at the function level. Full endpoint and generation-publication tests remain necessary.

## 11. Instructions for the implementation agent

> Work from the consolidated IDs in this report. Before changing code, record the actual HEAD and compare it with the audited commit. Reproduce the affected invariant on that baseline or mark the item already changed with evidence. Keep the work on a reviewable branch. Do not enable cloud providers, launch paid jobs or change external deployment state merely to obtain a green report. Write regression tests for the real affected route/input mode; do not repair a raw-video bug only in a tracking-JSON fixture. Do not trust posted evidence arrays, duplicate full budgets on retry, or replace missing measurements with zero. Preserve existing source-bound artifact validation. At handoff, list each ID as fixed with evidence, safely deferred/disabled, still open, or not reproduced with a reason. Include both the baseline failure and fixed pass, the test profile and the code revision. Do not claim completion from helper metadata or a passing-count total alone.

The original 47-page v1.1 plan remains the long-term product direction. This report is a hardening checkpoint for the current implementation, not permission to expand scope before the correctness contracts are working.

## 12. Final assessment

**Proceed with the project, but treat this as integration hardening rather than cosmetic polishing.** The most valuable next deliverable is a reviewed match whose corrections, measurements, provenance, costs and exports remain consistent through a failure and restart.

The second review is useful corroboration, not proof by model agreement. Preserve its reported evidence, apply the corrections above, and close each item with reproducible source-bound behaviour. The architecture can remain Python-first and specialist-model-first. None of the highest-priority issues requires a wholesale language rewrite.

## Appendix A — Evidence manifest

The following input hashes identify the supplied files used in this consolidation. They do not authenticate the other reviewer’s missing external scripts/logs. Pinned GitHub links in each finding identify the source revision.

- `Guerilla_Backend_Audit_d881d1e.md` — SHA-256 `4fb11341c18cddf291242c8255bc70a4b073c63dbae3d4ad04b1818b9ac72382`
- `Pasted markdown.md` — SHA-256 `70b29acc04cdc578a50dc290b140838ad4ec81c093e658b72472d4ca19a8e87f`

**Repository/CI references:**

- [Audited source tree](https://github.com/ms81labs/sol-astra-football-analyses-sept26/tree/d881d1eaf7a0898897bd9a1a1ae46306606c904d/backend)
- [Verification run 35279899115, job 105399174965](https://github.com/ms81labs/sol-astra-football-analyses-sept26/actions/runs/35279899115/job/105399174965)
- [Code-only verification script](https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/d881d1eaf7a0898897bd9a1a1ae46306606c904d/scripts/verify.sh)

**Fresh-read scope in this pass:** `backend/app/storage.py` (selected correction, recompute and calibration sections), `backend/app/processor.py` (reprocessing), `backend/app/workbench/routes.py`, `backend/app/workbench/jobs.py`, `backend/app/workbench/geometry.py`, `backend/app/workbench/media.py` (decode loop), `backend/app/workbench/access.py` (decoder guard), `backend/app/workbench/assistance.py` (returned output), `backend/app/main.py` (provider route), `backend/run_guerilla.py` (receipt output), `backend/app/video_pipeline.py` (wrapper), `backend/tests/conftest.py`, `.github/workflows/ci.yml`, main-ref metadata and CI job-step metadata. Other original pinned-source findings are retained, not presented as freshly re-executed.

**Not available:** the external reviewer’s `/tmp/audit_repro/repro.py`, `/tmp/audit_repro/pytest_code_only.log`, actual footage, deployed configuration, private billing or a local full repository checkout.
