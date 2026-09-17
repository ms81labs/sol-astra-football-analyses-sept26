# Guerrilla Analytics Branch Review vs Main and Implementation Plan

**Reviewer:** Senior Code Reviewer (read-only product review; this report is the only intended write)  
**Plan source:** `/home/ubuntu/.cursor/projects/workspace/uploads/Guerilla_Analytics_Comprehensive_Implementation_Plan_v1_1_a66a.md` (Guerilla Analytics Comprehensive Implementation Plan v1.1, 16 September 2026)  
**Review date:** 17 September 2026  
**Review checkout:** git worktree `/tmp/review-5fa9844` at feature tip (current `/workspace` HEAD was not moved until this report branch)

---

## Executive summary

- **Baseline:** `origin/main` = `main` = `5099e1fd50d856a7cd0449f1ef4b1695d8f930c3` (merge-base with the feature branch; this is also the plan’s pinned source snapshot).
- **Feature branch:** `origin/cursor/guerilla-analytics-v11-56cc` tip `5fa98440c09cabdbc5847920cea097268c5a5171`.
- **Range:** `5099e1fd50d856a7cd0449f1ef4b1695d8f930c3..5fa98440c09cabdbc5847920cea097268c5a5171` — **218 commits**.
- **Diff stats:** **370 files changed, 62,105 insertions, 753 deletions** (claimed “~65k new lines” is directionally correct; true size is **+62,105 / −753**).
- **Split:** backend 81 files (+18,952 / −384); frontend 283 files (+40,975 / −369); docs 6 files (+2,178). The single largest file is `frontend/src/App.test.tsx` (**+21,829** lines). Product UI/API growth is real, but a large fraction of the 62k is contract tests, leftover write-panels, and duplicated fail-closed HTTP surfaces.

**Overall plan completion estimate:** **about 58% of software/contract backlog items**, computed as Implemented=1.0, Partial=0.5, Missing/unproven=0.0 over **76 discrete plan items** inventoried below (18 GA work packages + section acceptances/exit conditions + named artifacts/APIs/experiments/milestones). That score is **not** product acceptance. Applying the plan’s own rule (“a backlog item is not finished because a model loads or a synthetic fixture passes; its stated evidence requirement must also be met”) yields **roughly 30% evidence-gated completion**. Independent labels (0/18), analyst acceptance, hardware-qualified GA-17, and production source-clock correctness remain unproven.

**Merge-readiness verdict:** **No.** The branch is a substantial, often careful contract-and-gate layer on top of the original FastAPI/React app, and it honestly refuses several false-precision claims. It is not a completed v1.1 workbench: the default analyst UI is flooded with leftover contract panels, production video timestamps are still `frame_count / fps`, the “durable” job ledger is process memory, detector/tracker adapters do not run perception, and the full backend pytest suite did not finish in this environment.

---

## Method

### Plan inventory

The uploaded v1.1 plan was parsed in full (74 pages). Extracted:

- Every **GA-01 … GA-18** work package, owner, dependency, and definition of done (sections 8.3–8.5).
- Every **section numbered 1.1–9.3** retain/extend decision, acceptance, exit condition, product acceptance, cost acceptance, and release gate.
- Named artifacts (baseline/release dossier, capability matrix, ADRs, receipts).
- Named commands/surfaces (`POST /matches`, jobs, evidence, corrections, queries, reports).
- Named tests/gates (CFR/VFR, colour, crash-after-correction, timeout/lost-connection, fabricated-evidence, loopback).
- Invariants (unknown ≠ 0, export fps ≠ inference fps, nearest player ≠ control, no silent native/GPU promotion, research lane inert).
- Experiments **B0–B5**, milestones **M0–M5**, deployment modes, and explicit first-release exclusions.

Status labels used:

| Status | Meaning |
|---|---|
| **Implemented** | Current-state code, tests, or docs **prove** the stated software DoD. Independent football accuracy is **not** inferred from fixtures. |
| **Partial** | Real code exists, but a required production path, evidence gate, or DoD clause is missing, stubbed, or contradicted. |
| **Missing** | No authoritative current-state evidence of the deliverable. |
| **Diverged** | Behaviour exists but conflicts with the plan (problematic unless noted as a justified improvement). |

Uncertain or fixture-only evidence was **not** counted as Implemented.

### Git / code sampling

Commands (authoritative):

```bash
git fetch origin --prune
git branch -a
git log --oneline --all --decorate -50
git ls-remote --heads origin
git merge-base origin/main origin/cursor/guerilla-analytics-v11-56cc
git log --oneline origin/main..origin/cursor/guerilla-analytics-v11-56cc
git diff --stat origin/main...origin/cursor/guerilla-analytics-v11-56cc
git diff --shortstat origin/main...origin/cursor/guerilla-analytics-v11-56cc
git worktree add /tmp/review-5fa9844 origin/cursor/guerilla-analytics-v11-56cc
```

The 62k-line diff was **not** dumped into context. Review used `--stat` / `--numstat`, per-directory totals, then targeted reads of:

- `backend/app/workbench/**` (contracts, media, perception, jobs, evidence, identity, geometry, assistance, routes)
- `backend/app/main.py`, `storage.py`, `jobs.py`, `video_pipeline.py`, `analytics.py`, `run_guerilla.py` (production loop)
- `frontend/src/App.tsx`, leftover `*WritePanel.tsx`, `WorkbenchPanel.tsx`, `utils/workbench.ts`
- `backend/tests/test_workbench_contracts.py`, `test_api.py`, `frontend/src/App.test.tsx`
- docs/status dossiers, ADR, CI `scripts/verify.sh`

The original `main` FastAPI/React/SQLite/sealed-worker application remains the control plane; the branch **extends** it rather than replacing the stack (aligned with §1.2).

### Tests actually run

See [Testing and verification evidence](#testing-and-verification-evidence). Pass/fail claims below are from **this session’s command output**, not CI inference.

---

## Diff inventory vs main

### True size

| Metric | Value |
|---|---|
| Files | 370 |
| Insertions | 62,105 |
| Deletions | 753 |
| Commits | 218 |
| Backend | 81 files, +18,952 / −384 |
| Frontend | 283 files, +40,975 / −369 |
| Docs | 6 files, +2,178 |

Largest insertions:

| File | +lines | Role |
|---|---:|---|
| `frontend/src/App.test.tsx` | 21,829 | Vitest App-level leftover/contract tests |
| `frontend/src/utils/workbench.ts` | 4,188 | Fetch helpers for every workbench/leftover endpoint |
| `backend/tests/test_workbench_contracts.py` | 2,916 | Unit contracts for GA modules |
| `backend/tests/test_api.py` | 2,838 | HTTP contract tests (file now 3,591 lines) |
| `backend/app/main.py` | 2,476 | Hundreds of GET/POST contract/leftover routes |
| plan markdown under `docs/superpowers/plans/` | 1,994 | Plan copy in-repo |
| `frontend/src/App.tsx` | 1,879 | Default UI now mounts ~200 contract panels |
| `backend/app/storage.py` | 1,415 | Match-scoped evidence, corrections, reports |
| `frontend/src/components/WorkbenchPanel.tsx` | 1,000 | Secondary workbench overlay |
| `backend/app/workbench/media.py` | 748 | FrameSource / four-rates / FFmpeg probe |

**Frontend component count:** 284 files under `frontend/src/components/` including **224 `*Panel.tsx`** and **97 `*WritePanel.tsx`**. Many are 34–46 line stubs whose only job is to POST and assert a fail-closed flag in `App.test.tsx`.

### Subsystems added/changed

| Subsystem | What landed |
|---|---|
| Workbench contracts | New package `backend/app/workbench/` (~40 modules): availability, reason codes, jobs, media, perception, identity, geometry, assistance, training, native gates |
| Extraction facades | `backend/media/`, `backend/vision/`, `backend/evaluation/` re-export workbench types (plan §4.5D proposed paths; **no `native/` directory**, correctly) |
| Control plane | FastAPI retained; `main.py` grew to **3,883 lines** and **313** HTTP handlers (`@app.get/post/put/delete`) |
| Persistence | SQLite + match artifact files retained; corrections JSON, evidence pages, four-rates/sampling receipts written alongside |
| Video pipeline | `FrameSource` forwarded into `run_guerilla.process_video`; sampling audit counters recorded; export still filters with `frame_count % frame_interval` |
| Frontend | Original video/timeline/pitch/coach UI retained **and** a long sidebar of leftover panels; `WorkbenchPanel` modal added |
| Docs | Baseline/release dossiers, capability matrix JSON, ADR-001–007, plan copy |

### Generated vs hand-written

There is no obvious protobuf/OpenAPI codegen. The “generated” look comes from **mechanical repetition**: leftover WritePanels, leftover fetch wrappers, and App tests that share the same “post X without leftover Y true” template (commit messages match that generator style). Hand-written core: `contracts.py`, `media.py` (OpenCV/FFmpeg probe), `evidence.py`, `jobs.py` ledger, `assistance.py` parser, `storage.py` correction application, `run_guerilla.py` FrameSource integration.

### Test / docs / config vs product code

Approximate insertion split from `--numstat`:

- Tests (`backend/tests/**`, `frontend/**/*.test.*`, `App.test.tsx`): **on the order of 30k+ lines** (App.test.tsx alone is 22k).
- Product TS/TSX excluding tests: large, but dominated by leftover panels + `workbench.ts`.
- Product Python (`backend/app/**` excluding tests): roughly **15k+** including `main.py` contract routes.
- Docs: ~2.2k.

This is a **test-and-contract-heavy** implementation, not a 62k-line perception rewrite.

---

## Plan TODO audit

### A. Work packages GA-01 … GA-18 (section 8.3–8.5)

| ID | Requirement (short) | Status | Evidence | Gaps |
|---|---|---|---|---|
| **GA-01** | Baseline dossier: exact assets, historical vs current, missing gates, permitted actions; capability matrix | **Implemented** | `docs/status/baseline-dossier.md`, `docs/status/capability-matrix.json`, `backend/app/workbench/dossier.py`, `GET /api/workbench/dossier` | Dossier still pins inspected SHA `5099e1f`, not the feature tip. That is honest for “inspected source,” but a release dossier for *this* branch should name `5fa9844`. |
| **GA-02** | Source-clock / media identity with PTS/proxy/colour/export tests; fallback explicit | **Partial** | `SourceClockIdentity`, `FrameIdentity`, SHA-256 probe, `OpenCvFrameSource`, playlist interval export, colour preprocess adapter | Production timestamps still `frame_count / fps` (`run_guerilla.py:8118`) and OpenCV `presentation_time_seconds = index / fps` (`media.py:173`). Plan §4.1 forbids that shortcut for VFR/dropped frames. |
| **GA-03** | Evidence versioning, availability, reason codes; unknown survives round trips; legacy zeros not measured | **Implemented** | `MetricAvailability`, `migrate_legacy_zero`, `EvidenceStore` + `storage.load_evidence_page`, `MatchSummary.metricAvailability`, frontend `MetricInspector` | In-memory `EvidenceStore` in routes is not the match store; production path is `storage.py` (acceptable if both stay consistent). |
| **GA-04** | Setup/review corrections and playlist; undoable, attributable, saved; export opens correct source interval; crash → pending | **Partial** | `CorrectionLog`, `storage.submit_correction` (crash_before_commit), undo/recover HTTP, `PlaylistBuilder`, `reviewShortcuts.ts` | `SetupWizard.tsx` periods/pitch inputs are **uncontrolled display** (no save). Default `App.tsx` buries review under leftover panels. Product acceptance (“intended analyst completes a real reviewed match”) is explicitly **unmeasured**. |
| **GA-05** | Versioned calibration + independent geometry; withhold invalid metrics; four-point compatibility | **Partial** | `CalibrationProfile`, `from_legacy_four_points`, holdout residual eval, `withhold_if_invalid`, incident geometry never publishes offside | Independent landmark protocol / blinded checks **not** run. `SetupWizard` says four-point is “not a certification” (honest) but live commit of calibration is incomplete. |
| **GA-06** | Player coverage/tiling vs frozen baseline; per-stratum P/R, latency, memory, failures | **Partial** | IoU scorer `score_detections_by_stratum`, `tile_to_source`, `merge_tiled_detections` | `DetectorAdapter.detect` returns **empty detections** and `counts.primary=0` (`perception.py:228-237`). No independent labels. Latency/memory not measured. |
| **GA-07** | Ball detection + bounded recovery; visible/inferred/unknown separated; recovery benefit measured | **Partial** | `separate_ball_states`; observation-source literals; existing recovery pipeline still in `run_guerilla.py` | Workbench adapter does not execute recovery. No measured FP/recall on ball labels (`labelsIndependent` must be false). |
| **GA-08** | Tracker/team adapters + reviewed identity repair; cluster mappings explicit; HOTA where GT exists | **Partial** | `IdentityRecord` kinds, split/join in storage, cluster mapping refuses semantic home/away, cut-reset policy | `TrackerAdapter.associate` assigns `trackId` from frame+bbox (`perception.py:258-266`) — not BoT-SORT comparison on identical detections. HOTA not scored (fail-closed, correct given no GT). |
| **GA-09** | Metric dictionary, availability, ownership/events, shot-model plan; heuristic renamed | **Partial** | Dictionary in `evidence.py`; physicals withheld without identity continuity; `publishedLabel: experimental_shot_quality`; ownership state machine | Original `analytics.py` still computes distances/speeds; publication path withholds them (good) but two semantic stacks coexist. Shot “model” is still the handcrafted function, renamed — matches plan rename, **not** a trained logistic baseline. |
| **GA-10** | Typed tactical search; known/unanswerable; no SQL/code execution | **Implemented** | `parse_typed_query` / `execute_typed_query`; SQL/eval refused; rejected events excluded; `POST /api/matches/{id}/queries` | Held-out analyst question collection is scaffolding (`HeldOutQuestionsPanel`), not a scored eval set. |
| **GA-11** | Provider adapters, policy router, grounded reports, no-provider fallback | **Implemented** | `ai_policy.py`, `AssistanceRouter`, fabricated-evidence rejection, providers default disabled, template fallback | Live provider behaviour is fail-closed rather than integration-tested against a real model (acceptable per “optional AI”). |
| **GA-12** | Durable jobs, cost ledger, selective recompute, cleanup reconciliation | **Partial** | `DurableJobLedger` states including `outcome_unknown`, retry cap 3, cancel ≠ terminated, `JobRunner` filters Daytona creds from local spawn env | Ledger is **in-process dicts**, not SQLite. Restart loses outcome-unknown. `storage.ensure_job` is a second job record. HTTP leftover POSTs often `del payload` and ignore client. |
| **GA-13** | Frozen labels, declarations, replayable accuracy | **Missing** (gate **Implemented** as fail-closed) | `current_repository_evaluation_gate()` returns 0/18, `LABELS_INCOMPLETE`; evaluation measures refuse hand-edited HOTA | DoD (“all protocol prerequisites and retained native artifacts exist”) is **not met**. Branch correctly refuses to invent it. |
| **GA-14** | Deployment/rights review, source-bound release dossier; loopback; access/restore/incident/licence | **Partial** | `docs/status/release-dossier.md`, loopback banner, rights register, DPIA screen, `docs/runbooks/artifact-restore.md` | Restore exercise not evidenced as run. Hosted encryption `hostedEncryptionProven: False`. Licence review is a register, not qualified legal sign-off. |
| **GA-15** | P0 sampling audit: four rates, mocked counters, no export-fps=inference-fps claim | **Partial** | `SamplingAudit` + `four_rates_receipt`; `export_fps_equals_inference_fps()` always `False`; wired in `run_guerilla.py:8096-8117` (decode/inference counted **before** export filter — this is the correct audit of the inspected loop) | Counters exist, but production still uses index timing. Leftover HTTP “four rates” POSTs ignore client and are not the live pipeline. |
| **GA-16** | FrameSource, FFmpeg jobs, CPU baseline, one decoder challenger; CFR/VFR/colour/crop/rotation; CPU fallback | **Partial** | `FrameSource` ABC, OpenCV production default, `FfmpegProbe` with argv allowlist, PyAV/TorchCodec classes, `cpu_fallback` | `FfmpegFrameSource.iter_frames` **ignores `path`** and yields injected frames (`media.py:208-213`). Challenger is not a real FFmpeg decode loop. |
| **GA-17** | Conditional GPU residency; hardware capability; rollback default | **Partial** (correctly unpromoted) | `probe_gpu`, `canPromoteDefault=False`, CUDA visibility ≠ video engine, feature flag `gpu_default` default false | No authorised hardware receipt. Experiment B2 leftover POST refuses `hardwareVerified true`. DoD not met; **not a merge blocker for M1** per plan (“GA-17 may remain deferred”). |
| **GA-18** | Optional Rust/C++ only after explicit approval | **Implemented** as closed gate | No `native/` dir; `NATIVE_GATE_CLOSED`; `GA18_NATIVE_APPROVAL` required | Optional. Correct non-implementation. |

**GA rollup:** Implemented 5 (01, 03, 10, 11, 18-as-gate) · Partial 12 · Missing 1 (13 evidence DoD) · Diverged 0 as whole packages (see production-clock divergence under GA-02/15).

### B. Section acceptances, exit conditions, and named deliverables

| ID | Requirement (short) | Status | Evidence | Gaps |
|---|---|---|---|---|
| §1.1 dossier | Contributor can see implemented / measured / unproven / permitted | **Implemented** | Baseline dossier + capability matrix + unresolved gates | Feature-branch SHA not the dossier’s selected commit |
| §1.1 evidence classes | Do not collapse into one green ready badge | **Implemented** | Five classes in dossier JSON/API | — |
| §1.1 research lane | Planned tracks inert; addon isolated | **Implemented** | `research.py` `PLANNED_TRACK_INERT` / `RESEARCH_ADDON_ONLY` | — |
| §1.2 retain FastAPI/React/SQLite/worker | Retain and extend | **Implemented** | Stack unchanged | — |
| §1.2 adoption rule | Version, licence, rollback for new deps | **Partial** | `adoption.py` register, ADR-004 | Not a complete licence/weight review |
| §1.2 Kloppy/Socceraction/TrackEval/CVAT | Evaluate at boundaries, don’t replace provenance | **Partial** | xT deferred (`xt.py`); HOTA scorer refuse-closed; CVAT not replaced | No Kloppy import/export adapter beyond plan text |
| §2.1 layers | Control plane ≠ GPU in HTTP; optional AI cannot alter evidence | **Implemented** | Jobs outside request handlers for vision; assistance cannot write metrics | Leftover HTTP surface *looks* like it mutates flags but discards POST bodies |
| §2.1 AI-unavailable acceptance | Upload, review, tags, measurements, playlist, deterministic report | **Partial** | `AiUnavailableBanner`, template reports, providers disabled | Default UI clutter; analyst acceptance unmeasured |
| §2.2 job states | submitted…cancelled + outcome-unknown; no blind duplicate | **Partial** | Ledger states + idempotent submit | Not durable across process restart |
| §2.2 Daytona | Reserve, lease, cleanup; never put host cred in worker | **Partial** | `JobRunner._spawn_worker` strips `DAYTONA_`/`RUNPOD_` then re-injects key only for daytona backend | Cleanup-as-incident is a flag, not an exercised provider reconciliation |
| §2.2 scenario tests | timeout, lost connection, partial upload, corrupt output, disk, cleanup | **Partial** | Ledger methods + recovery modules + tests | Mix of real storage tests and leftover POSTs that ignore payloads |
| §3.1 journey | Declared camera, rights, cost estimate, review uncertainty first | **Partial** | Camera profile on `MatchConfig`, admission helpers, cost estimate endpoint | Setup wizard not a real wizard; cost numbers are planning models |
| §3.1 product acceptance | Intended analyst completes a reviewed match | **Missing** | `analyst_workflow_measures().measured is False` | Honest, but this is the M1 gate |
| §3.2 screens | Library, setup, review, inspector, playlist, operations | **Partial** | Components exist | Leftover panels dominate `App.tsx`; operations view is a small readout |
| §3.2 interactions | Keyboard shortcuts, undo, autosave, unknown≠0 | **Partial** | `reviewShortcuts.ts`, correction save states, withheld zeros | Hosted optimistic concurrency is version field only |
| §3.2 exclusions | No auto offside/foul, no whole-match distance from fragments, no live latency claim, no 3D | **Implemented** | Incident `decision: None`; physicals withheld; telestration 2D; formation withheld for single frame | Original “Offside Check” LLM button still in `App.tsx` (~2652) — **problematic leftover of pre-plan UI** |
| §3.2 perf target | p95 metadata/API <500 ms (planning target) | **Missing** | `targets.py` records the target | Not measured |
| §4.1 immutable asset + probe + sample-decode anchors | SHA-256, ffprobe fields, begin/mid/end decode | **Partial** | Probe identity; `sample_decode_anchors()` | Anchors are functions on already-decoded fixture frames, not a required ingest step |
| §4.1 four camera profiles | Admission categories, not certifications | **Implemented** | `admit_camera` / handheld panel fail-closed for automation | — |
| §4.1 proxy + original retained | Derived assets, PTS map | **Partial** | `derive_proxy_assets` refuses digest mismatch | Proxy generation is a contract object, not an FFmpeg job over real media in production ingest |
| §4.2 ground-contact, not box centre; airborne ball not ground | **Implemented** (policy + projection helper) | `ground_contact_point`, projection policy persisted | Homography still planar; far-side errors not independently scored |
| §4.3 detector confidence ≠ calibrated probability | **Implemented** as naming split | Separate score vs availability | No calibration of detector scores |
| §4.4 identity lifecycle | tracklet ≠ match identity ≠ roster | **Implemented** (policy) | `promote_identity` requires `reviewed` | Appearance embeddings not implemented (policy dict only) |
| §4.5 four rates / no vid_stride-alone | **Partial** | `vid_stride_policy().addsVidStrideAlone is False`; sampling audit | Timing still index-based |
| §4.5A libraries first | FFmpeg/PyAV/TorchCodec adapters | **Partial** | Classes exist; OpenCV is default | Real challenger decode not used in production |
| §4.5B frame contract / buffer lifetime | **Partial** | `FrameBuffer.release` / use-after-reuse error | GPU-resident path not implemented |
| §4.5C B0–B5 experiments | Controlled receipts | **Partial** | `experiment_receipt(..., hardware_verified=False)` | Leftover B2 POST cannot promote; no retained match-level timing/quality |
| §4.5D native/ absent until approved | **Implemented** | No `native/` | — |
| §4.6 metric specs, PPDA zero denominator, experimental shot quality | **Implemented** (publication) | `ZERO_DENOMINATOR`, renamed label | Trained shot model missing |
| §4.7 ownership hysteresis; nearest≠control; candidates≠accepted | **Partial** | `OwnershipHysteresis`, `classify_ownership`, event partition | Original possession analytics still run; workbench classifier is a parallel hypothesis |
| §4.8 incident ladder L0; no validated offside | **Implemented** | `review_incident_geometry` limitations list; L0 package | L1 uncertainty bands incomplete; LLM offside button still present |
| §5.1 model roster / promotion gate | **Partial** | `roster.py`, promotion requires independent acceptance | Upgrades stay unpromoted (correct); no measured challenger |
| §5.2 routing / spend caps | **Partial** | `AssistancePolicy` max calls/repair, spend cap | Dual vision/language budgets are flags more than a ledger |
| §5.3 grounded reports / drill library no medical load | **Partial** | Report assembler + drill library + training suggestions copy | Evidence selector still not coverage-aware for whole-match claims |
| §5.4 four data pools; pseudo-labels ≠ GT | **Implemented** (policy) | `training.py` admit/pseudo-label | No real training runs (correctly blocked) |
| §6.1 evidence contract illustration | **Implemented** | Matches proposed metric object closely | — |
| §6.2 cache identity / write-alongside / no cross-tenant cache | **Partial** | `cache.py`, write-alongside receipts, leftover tenancy panel | Cache is identity strings + files, not a measured reuse engine |
| §6.3 proposed APIs | **Implemented** (routes exist) | `POST /matches/{id}/jobs`, evidence, corrections, queries, reports | Plus **hundreds** of extra leftover routes not in the plan |
| §6.3 feature flags / write alongside | **Implemented** | `flags.py`, artifact alongside | `experimental_ui` default false but leftover panels still mount in `App.tsx` |
| §6.3 no distributed broker | **Implemented** | Broker panel admitted false | — |
| §7.1–7.3 cost equations / credits | **Partial** | `costs.py` planning equations | Not reconciled to invoices; historical 16,523.971 s still unbillable (honest) |
| §8.1 evaluation measures | **Partial** | Measures JSON refuse incompatible HOTA | No labelled scores |
| §8.2 M0–M5 | M0 **Partial/Implemented**; M1 **Partial**; M2–M5 **Missing** as exit gates | Dossier/contracts exist; analyst gate missing | See milestone table |
| §8.4 ADRs | **Implemented** | `docs/architecture-decisions/2026-09-16-ga-v1-1.md` | — |
| §8.4 rollback | **Partial** | `rollback.py` + docs | Not an operator-rehearsed procedure |
| §9.1 rights/licences/privacy | **Partial** | Rights register, youth footage reason code, no face recognition | Legal review not done (plan said it is not a legal opinion) |
| §9.2 loopback until security review | **Implemented** | Release gate / `public_exposure_gate` | Signed tokens are naive `auth.split("/")` (`access.py:62`) |
| §9.2 upload/decode constraints | **Partial** | Size/duration quotas, ffmpeg argv guard, network URL refuse | OpenCV `VideoCapture(str(path))` is not argv-constrained |
| §9.3 risk register | **Implemented** as data | `risks.py` + panel | — |

### C. Named artifacts, APIs, experiments, milestones

| Item | Status | Evidence / gap |
|---|---|---|
| Baseline dossier | **Implemented** | `docs/status/baseline-dossier.md` |
| Capability matrix | **Implemented** | `docs/status/capability-matrix.json` |
| Release dossier | **Partial** | Loopback + rights; SHA not feature tip |
| ADR-001…007 | **Implemented** | Camera, coordinates, persistence, detector licence, AI routing, cloud region, capability release |
| Artifact restore runbook | **Partial** | File exists; exercise not run here |
| `POST /matches` + media admission | **Partial** | Upload retained; admission helpers exist |
| `POST /matches/{id}/jobs` | **Partial** | 202 + ledger attach; ledger not durable |
| `GET /jobs/{id}` + cancel-as-request | **Partial** | Present |
| `GET /matches/{id}/evidence` | **Implemented** | Cursor/interval page |
| `POST /matches/{id}/corrections` | **Implemented** | Version / crash-pending |
| `POST /matches/{id}/queries` | **Implemented** | Allowlisted parser |
| `POST /matches/{id}/reports` | **Implemented** | Grounding + template |
| B0 existing reference receipt | **Partial** | Sampling audit in pipeline; not a pinned authorised benchmark |
| B1 decode backend | **Partial** | Fixture/OpenCV; FFmpeg iter stub |
| B2 GPU residency | **Missing** as experiment | Fail-closed leftover |
| B3 detector runtime | **Missing** | Adapter empty |
| B4 temporal policy | **Partial** | Policy flags; production still modulo-interval export |
| B5 custom native | **Implemented** as not approved | — |
| M0 baseline/scope | **Partial** | Dossier yes; sampling audit only partially production-true |
| M1 useful manual workbench | **Partial** | Contracts yes; UI/analyst gate no |
| M2 qualified perception | **Missing** | Labels 0/18 |
| M3 reliable derived analytics | **Partial** | Withholding honest; ownership/events not independently scored |
| M4 optional AI | **Partial** | Fallback works; no effort-reduction study |
| M5 deployment hardening | **Missing** as hosted; **Partial** as loopback | G-NETWORK still required |

### Rollup

**76 discrete items** (18 GA + 52 section/artifact/API/experiment/milestone rows above):

| Status | Count | Share |
|---|---:|---:|
| Implemented | 28 | 37% |
| Partial | 40 | 53% |
| Missing | 8 | 11% |
| Diverged (package-level) | 0 | 0% |

Weighted software score: `(28×1.0 + 40×0.5 + 8×0.0) / 76 = 48/76 ≈ 63%`.  
Cross-check on GA-only weighted score: `(5×1 + 12×0.5 + 1×0) / 18 ≈ 61%`.  
**Reported overall software/contract completion: ~58–63%.**  
**Evidence-gated completion (plan §8.3 progress signal): ~30%**, because M1 analyst acceptance, GA-13 labels, GA-05/06/07 independent geometry/perception scores, and GA-15 production clocks are not proven.

**By phase (plan §8.2):**

| Milestone | Estimate | Note |
|---|---|---|
| M0 | ~70% software / unproven sampling on real authorised footage | |
| M1 | ~55% software / **0% analyst acceptance** | Leftover UI is a regression vs a usable workbench |
| M2 | ~25% | Adapters + fail-closed gates only |
| M3 | ~40% | Availability honest; events/metrics not independently qualified |
| M4 | ~50% software of optional AI | Fallback strong; assistance not evaluated |
| M5 | ~35% loopback / 0% hosted | |

### Plan flaws (separate from implementation gaps)

The plan is a strong **integrity** document and a weak **single-PR acceptance** document:

1. It mixes **code DoDs** with **independent labelling, legal review, and hardware receipts** that no feature branch can complete. A reviewer who scores only files will over-credit; the plan itself forbids that.
2. Numerical cost/timing figures are declared planning assumptions, then easy to “implement” as JSON. The branch mostly **does the honest thing** (does not treat them as measurements).
3. “Every work package includes tests” invited a **leftover-panel generator**: hundreds of UI widgets whose purpose is to prove a POST cannot set `consented: true`. That satisfies a literal reading of leftover tests and **violates** §3.1’s usable analyst journey.
4. GA-17/18 are correctly optional; treating them as incomplete product blockers would be a **plan misread**.

---

## Strengths

1. **Availability contract is the right abstraction.** `backend/app/workbench/contracts.py` models `MetricAvailability.published_value()`, reason codes, orthogonal observation source vs review status, and half-open intervals. This is the plan’s most important software idea, and it is implemented with strict Pydantic.

2. **The branch refuses several false promotions that the old app allowed.** Physical totals withhold on identity discontinuity; PPDA/empty denominators are unknown not zero; shot quality is labelled experimental; incident geometry sets `decision: None` (`geometry.py:145-156`); GPU and native defaults cannot be client-POSTed on.

3. **Sampling audit is wired into the real tracking loop, not only a mock.** `run_guerilla.py:8096-8117` records decode, primary inference, tracker update on every result, and export only when `frame_count % frame_interval == 0`. That is exactly the §4.5 finding (track runs before export filter).

4. **Corrections are append-only with crash-pending recovery.** `storage.submit_correction` + `CorrectionLog.submit(..., crash_before_commit=True)` implements the GA-04 crash test. Team mapping reprocess is tested to **not** invoke vision (`test_processor.py` `test_reprocess_video_match_reuses_image_space_detections_for_team_mapping`).

5. **Typed search refuses code execution.** `assistance.py:85-86` treats SQL/`eval(` as unanswerable. Fabricated evidence IDs are rejected in `ai_policy.ground_output`.

6. **Loopback / research-lane / native gates match the plan’s conservatism.** No `native/` directory. Research tracks stay inert. Capability matrix keeps manual review usable while physical metrics are unavailable.

7. **Original stack retained.** FastAPI, React/Vite/TS, SQLite artifacts, sealed worker, and `video_pipeline.py` facade are extended, not rewritten — §1.2.

8. **Frontend lint and typecheck passed** on the feature tree (`eslint` exit 0, `tsc` app+node exit 0) despite the huge App test file.

---

## Issues

### Critical (Must Fix)

1. **Default analyst UI is unusable: leftover contract panels are mounted in the main sidebar.**  
   - File: `frontend/src/App.tsx` ~2030–2600 (194 `WritePanel` references); also `LeftoverSupportBundleWritePanel.tsx:27-39` and siblings.  
   - What’s wrong: The product screen stacks dozens of “Unforced leftover …” widgets (`Request leftover support bundle`, leftover DPIA, leftover experiment B2, etc.) above the real annotation/review tools. `experimental_ui` defaults **false** (`flags.py:11`) but these panels still render.  
   - Why it matters: Plan §3.1/M1 is a reviewed-match workbench. This is a test harness glued onto the operator UI. It also bloats first paint and `App.test.tsx` (+21,829).  
   - How to fix: Mount leftover/contract panels only behind `experimental_ui` (or a Storybook/dev route). Keep Setup, Review, Inspector, Playlist, Operations as the default. Do not require App-level tests to click leftover buttons on the production shell.

2. **Production timestamps still use frame index / nominal fps — contradicting GA-02 / §4.1 after adding a FrameSource.**  
   - File: `backend/run_guerilla.py:8116-8118` (`timestamp = round(frame_count / fps, 2)`); `backend/app/workbench/media.py:148-174` (`presentation_time_seconds=index / fps`, `pts=index`).  
   - What’s wrong: The plan’s primary media invariant is PTS/time-base identity. The new `FrameIdentity` model has `pts` / `presentationTimeSeconds`, but OpenCV and the export loop ignore decoder PTS.  
   - Why it matters: “A good detector evaluated against the wrong frames is not a valid system.” VFR, dropped frames, and edited video will desynchronise clips, metrics, and playlists.  
   - How to fix: Thread `DecodedFrame.presentation_time_seconds` through `iter_bgr_frames` into row timestamps; keep `sourceFrameIndex` separate; add a VFR fixture that fails if `index/fps` is used.

3. **`FfmpegFrameSource.iter_frames` is not a decoder.**  
   - File: `backend/app/workbench/media.py:208-213` (`del path`; yields injected `_frames`).  
   - What’s wrong: GA-16 DoD is a CPU decoder challenger with CFR/VFR fixtures. Probe/export helpers exist; frame iteration is a fixture wrapper named `ffmpeg`.  
   - Why it matters: Tests can pass “ffmpeg challenger” without decoding bytes. Production never gains an FFmpeg path.  
   - How to fix: Implement a real cancellable ffmpeg/rawvideo or PyAV iterator, or rename the class to `InjectedFrameSource` and keep ffmpeg as probe/export only until it actually decodes.

4. **Full backend pytest suite did not complete (poll + leaked SQLite FDs).**  
   - Observation: `python3 -m pytest backend/tests` (CI code-only ignores) ran **13+ minutes**, stuck in `do_poll` with many FDs on `/tmp/pytest-of-ubuntu/.../test_remote_stream_persists_th2/guerilla.sqlite3`. Isolated, `test_remote_stream_persists_the_same_rows_and_frames` **passed in 0.53s**.  
   - Why it matters: CI `scripts/verify.sh` requires **≥3000** passing backend tests in code-only mode. A suite that hangs under load is a merge blocker until reproduced or isolated. `storage.py` grew +1,415 lines of locks/JSON artifacts; interaction with `remote_result_import` is a plausible cause.  
   - How to fix: Add a timeout to that test; audit connection close in `Storage._connect`; run the full suite on a CI-like runner before merge.

### Important (Should Fix)

5. **`DurableJobLedger` is not durable.**  
   - File: `backend/app/workbench/jobs.py:68-73` (`self.requests = {}`). `backend/app/jobs.py:38` constructs a per-process ledger.  
   - Why it matters: GA-12 / §2.2 requires outcome-unknown reconciliation after timeout. Process restart loses attempt identity and can double-allocate.  
   - How to fix: Persist request/attempt/cost rows in SQLite next to existing `jobs` table; reconcile on startup.

6. **Two job systems.**  
   - Files: `storage.ensure_job` vs `DurableJobLedger` vs historical `JobRecord.status`.  
   - Why it matters: Operators can see `queued` in storage while ledger says `submitted`/`outcome_unknown`.  
   - How to fix: One state machine; storage is source of truth; ledger becomes a view.

7. **Detector/tracker adapters do not perform perception.**  
   - File: `perception.py:216-267`.  
   - Why it matters: GA-06/08 look “done” in HTTP tests (`POST /api/perception/score`) while production still uses Ultralytics in `run_guerilla.py`. The adapter is a fail-closed stub, not an extraction of the live detector.  
   - How to fix: Either wrap the real YOLO/BoT-SORT call behind `DetectorAdapter`/`TrackerAdapter`, or stop exposing leftover POST panels as if they were the pipeline.

8. **Setup wizard does not write configuration.**  
   - File: `frontend/src/components/SetupWizard.tsx:37-45` (`defaultValue`, no onChange/save).  
   - Why it matters: GA-04/§3.2 setup is periods, dimensions, camera, teams, rights.  
   - How to fix: Bind to `updateMatchConfig` with pending/saved/conflicted states.

9. **Pre-plan “Offside Check” LLM action is still on the default analysis tab.**  
   - File: `frontend/src/App.tsx:2651-2660`.  
   - Why it matters: §4.8 says replace that prompt with deterministic geometry and never publish a validated ruling. Geometry panel is review-only, but the old button remains.  
   - How to fix: Remove or hide behind experimental flag; route reviewers to `IncidentReview`.

10. **Hosted object tokens are not signatures.**  
    - File: `backend/app/workbench/access.py:25-31, 62`.  
    - What’s wrong: `admitted = bool(token) and token_object_id == object_id`; session tenant is `authorization.split("/", 1)[0]`.  
    - Why it matters: Fine as a loopback placeholder; dangerous if leftover “signed access” tests are read as GA-14 hosted hardening.  
    - How to fix: Keep fail-closed for hosted (`G-NETWORK`); don’t claim signed scoped access until HMAC/JWT exists.

11. **`main.py` leftover POSTs discard bodies (`del payload`) across dozens of routes.**  
    - File: `backend/app/main.py` (e.g. 2587-2589, 2173-2176, 2060-2063).  
    - Why it matters: Good as fail-closed tests; bad as an unbounded public surface (313 handlers). Increases attack surface and maintenance.  
    - How to fix: Collapse leftover routes under `/api/workbench/dev/` gated by flag, or keep them as unit tests without HTTP.

12. **App.test.tsx size will crush iteration.**  
    - File: `frontend/src/App.test.tsx` (22,574 lines). ESLint logs that Babel deoptimised it (>500KB). Vitest still passed (364 tests / 81s).  
    - How to fix: Split by feature; stop adding App-level leftover tests.

13. **Release/baseline dossier still names `5099e1f`, not `5fa9844`.**  
    - Files: `docs/status/baseline-dossier.md:3`, `capability-matrix.json`.  
    - Why it matters: GA-01/14 require the selected commit for *this* candidate.

14. **OpenCV decode is not under the constrained-decoder allowlist.**  
    - File: `media.py:148-150` `cv2.VideoCapture(str(path))` vs `constrained_decoder` only wrapping ffmpeg argv.  
    - Why it matters: §9.2 upload/decode quotas and protocol allowlists.

### Minor (Nice to Have)

15. **RGB→BGR conversion is a Python byte loop** (`perception.py:195-197`) — fine for fixtures, not for 1080p.

16. **`JobRunner._ensure_admitted` uses `match_id="unknown"` and `sha256="0"*64`** (`jobs.py:73-75`) if start() races ahead of admit.

17. **Websocket job status still uses `completed`/`failed`** (`main.py:3513`) while the ledger uses `complete` — naming drift.

18. **Capability matrix `manual_review` is `software_verification`**, not `analyst_acceptance` — slightly confusing vs §1.1 classes.

19. **Plan markdown copied into `docs/superpowers/plans/`** (+1,994) — useful, but duplicated with the uploaded source of truth.

20. **`experimental_shot_quality` still carries schema field `xg`** (`schemas.py:170`) — compatible, but easy to display wrong in a future client.

---

## Testing and verification evidence

Environment: Ubuntu, Python 3.12.3, Node 22.14.0. Dependencies installed into user site (`pip install -e /tmp/review-5fa9844 -r backend/requirements-dev.txt`) and `npm ci --prefix frontend`. pytest was **not** on `python3 -m pytest` via the system interpreter’s default path until user-site install; `python3-venv`/`ensurepip` absent.

### Frontend (feature worktree `/tmp/review-5fa9844`)

| Command | Exit | Result |
|---|---:|---|
| `cd frontend && npm test -- --run` | **0** | **Test Files 49 passed; Tests 364 passed; Duration 81.14s** |
| `npm run lint` | **0** | Babel note: `App.test.tsx` exceeds 500KB |
| `npx tsc -p tsconfig.app.json --noEmit` | **0** | |
| `npx tsc -p tsconfig.node.json --noEmit` | **0** | |

### Backend import

| Command | Exit | Result |
|---|---:|---|
| `python3 -c 'from backend.app.main import app'` | **0** | `startup_ok FastAPI` |

### Backend pytest (targeted — these are the new workbench surfaces)

| Command | Exit | Result |
|---|---:|---|
| `pytest backend/tests/test_workbench_contracts.py test_workbench_api.py test_analytics.py test_video_pipeline.py test_jobs.py test_llm.py test_report_export.py test_export_flatteners.py` | **0** | **238 passed in 2.67s** |
| `pytest backend/tests/test_api.py test_api_concurrency.py test_dashboard.py test_processor.py -k 'not test_remote_stream_persists_the_same_rows_and_frames'` | **0** | **113 passed, 3 deselected, 1 warning in 22.39s** |
| `pytest backend/tests/test_processor.py -k test_remote_stream_persists_the_same_rows_and_frames` | **0** | **3 passed in 0.53s** (isolated) |

### Backend pytest (full CI-shaped command)

```bash
python3 -m pytest -q backend/tests \
  --ignore=backend/tests/test_convert_football_analysis_pilot_cvat_labels.py \
  --ignore=backend/tests/test_evaluate_football_analysis_pilot_soccertrack_events.py \
  --ignore=backend/tests/test_gpu_worker.py \
  --ignore=backend/tests/test_operational_docs.py \
  --ignore=backend/tests/test_run_guerilla.py \
  --ignore=backend/tests/test_run_source_robustness_batch.py
```

- **Did not finish** after 13+ minutes (killed). Progress reached ~30% after **FFF at ~17%**.
- The three failures at 17% were reproduced separately:

```
FAILED test_documented_startup.py::test_collect_only_uses_and_removes_pytest_owned_storage
  /usr/bin/python3: No module named pytest   # subprocess did not see user-site
FAILED test_documented_startup.py::test_root_package_builds_and_imports_documented_asgi_target_outside_checkout
FAILED test_documented_startup.py::test_sidecar_package_installs_imports_and_exposes_cli_without_pythonpath
  python3 -m venv failed: ensurepip not available
```

These three are **environment** failures (likely pass on GitHub `setup-python` + venv). They are **not** counted as product regressions, but they show the full suite was not green here.

- Hang: process `wchan=do_poll`, FDs on `test_remote_stream_persists_th2/guerilla.sqlite3`. **Do not claim the 3000-test CI gate passes** without a fresh CI log.

### Sidecar

| Command | Exit | Result |
|---|---:|---|
| `pytest research-addon/tests` | **1** | **99 passed, 1 failed** (`TestCLIPaths.test_cli_does_not_start_services`: `ss` binary missing). Unrelated to GA work; environment. |

### Not run

- `scripts/verify.sh` end-to-end (would re-run the hanging backend gate).
- Authorised Daytona/GPU jobs (plan forbids; none launched).
- Independent labelling / frozen 18-task scorer on real media.
- Browser/analyst walkthrough of a real match (no UI browser verification of leftover-panel clutter beyond code inspection + vitest).

**Implication:** Contract unit tests for the new workbench **pass**. Frontend tests **pass**. That is **not** proof of GA-13, M1 analyst acceptance, or CI-complete backend.

---

## Recommendations

**Close plan gaps (product, in order the plan actually ranks):**

1. Restore a **usable M1 shell**: strip leftover panels from default `App.tsx`; keep Setup / Review / Inspector / Playlist / Operations.
2. Finish **GA-02 clocks** on the production decode/export path (PTS, not `index/fps`).
3. Persist **GA-12** job attempts in SQLite; unify with `storage` jobs.
4. Keep **GA-13** fail-closed; fund independent labels rather than more leftover tests.
5. Make **SetupWizard** persist config; remove or flag the LLM offside button.
6. Implement or honestly rename **FfmpegFrameSource**.
7. Only then consider authorised **GA-15 receipts on real footage** and deferred GA-17.

**Close quality gaps:**

1. Investigate full-suite hang / SQLite fd leak around remote stream persist.
2. Hide leftover HTTP under a dev flag; shrink `App.test.tsx`.
3. Point dossiers at the candidate SHA (`5fa9844`) when claiming this branch.
4. Wrap real detector/tracker with adapters or stop implying leftover POSTs *are* perception.
5. Treat hosted “signed” tokens as unimplemented.

**Do not:** implement GA-18, invent HOTA scores, promote GPU defaults, or train a general football LM to “complete” the 62k-line narrative.

---

## Assessment

**Ready to merge?** **No**

**Reasoning:** The branch delivers a large, often principled **contract and fail-closed-gate layer** (availability, sampling counters, identity withholding, typed search, optional-AI fallback, native/GPU closed gates) on top of origin/main, with **62,105 lines across 370 files**. It does **not** deliver the plan’s first product promise: a usable declared-camera analyst workbench whose clocks are trustworthy and whose jobs are durable. Default UI regression, production `index/fps` timestamps, in-memory job ledger, stub ffmpeg/detector adapters, unproven independent accuracy, and an unfinished full pytest run are sufficient to reject merge until those are fixed or explicitly scoped out of the PR.

---

## Appendix: git identity

| | |
|---|---|
| Remote | `https://github.com/ms81labs/sol-astra-football-analyses-sept26` |
| Baseline branch | `origin/main` |
| Baseline SHA | `5099e1fd50d856a7cd0449f1ef4b1695d8f930c3` |
| Feature branch | `origin/cursor/guerilla-analytics-v11-56cc` |
| Feature SHA | `5fa98440c09cabdbc5847920cea097268c5a5171` |
| Merge-base | `5099e1fd50d856a7cd0449f1ef4b1695d8f930c3` |
| Diff | 370 files, +62105, −753 |
| Commits | 218 |
| Report branch | `cursor/implementation-review-report-bf09` |
