# Astra Catapult-style Workbench Implementation Plan

> **For agentic workers:** Execute one reviewed unit at a time using Superpowers' executing-plans workflow, or an explicitly selected subagent-driven workflow. Re-read the companion design and the current repository checkpoint before changing code. This plan does not authorize cloud spend or additional branches.

**Goal:** Deliver an evidence-linked post-match analyst workflow, then qualify optional SAM 3.1 perception enhancement and GPT-6 Astra assistance without replacing the Python analytical core.

**Architecture:** Extend the existing React workbench, Python orchestration, generation store, private-Daytona workers and provider gateway. SAM runs in a separate environment and initially produces shadow artifacts. Astra receives approved structured evidence and bounded timestamped images; its output remains an interpretation or correction proposal.

**Tech stack:** Existing Python/FastAPI, React/TypeScript, storage/job machinery and media tooling; isolated Python 3.12+/PyTorch/CUDA SAM runtime; existing Pydantic-style contracts and tests; one optional OpenAI API adapter.

**Spec:** `astra-catapult-style-design-2026-09-22.md` (travels with this plan).

**Anchor:** `c685640a897c16669e3b1848d77bf9e6e5d7e8cf`, inspected 22 September 2026.  
**Status:** Proposed implementation sequence, with unexecuted acceptance tests. Suggested new paths and interfaces below are proposals, not existing functionality. Reconcile them with the current tree before each unit. No code or remote execution was performed to create this plan.

## Global constraints

- Preserve the existing Python 3.11/API dependency boundary; no SAM/CUDA requirement in the normal API profile.
- Keep local processing the default. No remote GPU or API request without source permission, valid policy and explicit budget authorization.
- Reuse existing jobs, leases, storage, generations, hashes, provider gateway, billing and export behavior.
- Preserve base detector/tracker outputs and identities. SAM is disabled by default and starts in shadow mode.
- Preserve image-space versus analytical pitch-space semantics. Dense masks never become analytical `FrameData` coordinates.
- Keep track IDs, team clusters and roster/player identities distinct. Unknown identity remains representable.
- A generated answer cannot publish new measurements, silently approve an event or mutate a reviewed track.
- Historical verification does not qualify a new source/model. Independent test labels are not generated from model predictions.
- Work on one user-approved integration target. Do not create a branch per task, rewrite history, reopen unrelated audit work or alter the live store.
- No calendar delivery promises. Each promotion depends on the gate below it.

## Review focus

| Failure class | Expected behavior | Owning units |
|---|---|---|
| Variable frame rate, off-grid clips, replay/camera cuts | Source-clock mapping stays explicit; no cross-cut memory; exported intervals refer to actual source media. | W01, W02, W03, W05 |
| Two similar players overlap, disappear and reappear | Ambiguity remains visible; no duplicate identity assignments or invisible track deletion to improve metrics. | W02, W04, W05 |
| Rights or generation changes while a model request is running | No newly forbidden dispatch; stale output is not published; billing outcome is retained. | W02, W06, W07 |
| Timeout/OOM/cancellation/provider outcome unknown | Base review workflow remains usable; no hidden substitution or automatic billed retry. | W03, W06, W09 |
| A report has valid citations but an unsupported conclusion | Referential validation is separated from entailment; exact numeric claims require matching metrics; interpretation stays labeled. | W06, W07, W08 |

## Milestones and dependencies

| Milestone | Units | Deliverable | Promotion gate |
|---|---|---|---|
| A — Product baseline | W00–W01 | One complete analyst workflow, no new model required | Source-linked search/review/clip/export/reopen works on a retained fixture |
| B — Segmentation evidence | W02–W04 | Bounded SAM shadow results and an independently scored comparison | Real model receipt plus reproducible independent evaluation |
| C — Optional perception improvement | W05 | ID-only enhancement; geometry remains a separate candidate | Accuracy and coverage gates pass |
| D — Evidence-grounded assistant | W06–W08 | Bounded Astra explanations, visible query translation and review proposals | Policy, budget, citations, stale-state and analyst tests pass |
| E — Declared-camera pilot | W09 | Whole-match workflow and resource/analyst evidence | Current-source pilot accepted within stated scope |

W06 evidence packaging can proceed after W01 without waiting for SAM. SAM is not a dependency of the assistant. W00 independent labeling can proceed alongside CPU workflow development, but qualification cannot bypass label locking. W05 does not block shipping a useful shadow-mask review feature.

## File ownership map

| Area | Reuse / modify | Minimum additions, only when needed |
|---|---|---|
| Review/search/presentation | `frontend/src/App.tsx`, existing review hooks, `TypedSearchPanel.tsx`, `EvidenceInspector.tsx`, `MatchVideoPanel.tsx`, `PlaylistBuilder.tsx`, `CoachInsights.tsx`, existing API utilities | Focused tests and the smallest state/contract extension; no second workbench |
| Perception identity and projection | `backend/app/video_pipeline.py`, `backend/app/perception_identity.py`, `backend/app/workbench/geometry.py`, existing generation/cache paths | Proposed `backend/app/segmentation.py` for the external contract/client and conservative decisions |
| Segmentation execution | Existing remote job/receipt and Daytona image patterns | Proposed `backend/segmentation_worker/__init__.py`, `runner.py`, `Dockerfile`, and a separately locked worker dependency profile |
| Assistant | `backend/app/provider_gateway.py`, `provider_adapters.py`, `provider_billing.py`, `llm.py`, `report_contracts.py`, `report_store.py`, settings | Only a separate provider-specific adapter file if the existing adapter module becomes unwieldy |
| Evaluation | `backend/evaluation/`, `backend/benchmark_suites/`, established pilot manifests/scorers | Proposed `backend/scripts/benchmark_segmentation.py`; mask annotation manifest as an extension |
| Delivery evidence | Existing current-status/checkpoint and runbooks | Proposed feature-specific design/plan documents under `docs/superpowers/` after review |

Do not edit every listed file by default. A unit must trace its actual callers, pick the narrowest working change and leave unrelated components untouched.

---

## W00 — Freeze the product and evaluation baseline

**Effort:** Small engineering change; independent labeling is a separate material workstream.  
**Files:** Read README, `docs/status/current.md`, existing release/checkpoint documents, pilot manifests and applicable verifier entry points. Update only the feature checkpoint/evaluation manifest needed for this work.

**Inputs:** Current commit, retained development fixtures, existing pilot protocol, source permissions and actual model/configuration identities.  
**Outputs:** A declared source baseline, one first camera profile, a development/validation/test split, the chosen analyst tasks and the exact gate record.

- [ ] Resolve `main` again and record any change from the design anchor. Do not silently treat prior test results as current.
- [ ] Run the existing provider-disabled verifier in an isolated working copy with temporary storage. Retain command, source SHA and complete result.
- [ ] Record what is currently possible in the UI using a retained fixture: open video, seek evidence, correct/undo, save clip, render when available, export and reopen.
- [ ] Reuse the existing frozen labeling protocol. Confirm which independent labels and team declarations actually exist before planning any held-out inference.
- [ ] Predeclare metrics and thresholds. Keep calibration/validation data separate from held-out matches; lock labels before prediction access.
- [ ] Commit only the baseline record and any targeted regression test required to make its behavior reproducible.

**Verification command already documented by the repo:**

```bash
VERIFY_DAYTONA=0 ALLOW_DAYTONA_MUTATION=0 scripts/verify.sh
```

**Exit:** Software baseline result is source-bound; all missing accuracy evidence remains explicitly missing. A failed baseline is not bypassed by a new feature flag.

## W01 — Complete the analyst vertical slice using existing components

**Effort:** Medium.  
**Files:** Existing `App.tsx`, review hook, video/timeline/evidence/search/playlist components and their matching tests. Do not create an alternative dashboard.

**Inputs:** One match/generation, approved source media, events/frames, existing correction and edit endpoints.  
**Outputs:** A coherent selected-interval state and a retained, reopenable analyst package.

- [ ] Add failing regression cases for: a search hit opens the exact source interval; a correction changes the generation; a stale in-flight action cannot attach to the new match; undo restores the prior visible result; a saved clip reopens after reload.
- [ ] Add a generated-media test with visible frame markers. Verify clip start/end against source timing, including nonzero source starts and an exclusive end frame. Do not use only a mocked render response.
- [ ] Connect existing selected event/player/interval state so video, timeline and evidence inspector agree. Keep source time separate from analysis/export FPS.
- [ ] Display observation/review status and coverage next to answers and metrics; missing identity or calibration is not a zero.
- [ ] Persist playlist notes and annotations through existing edit/package mechanisms. A render status of `not_run` is presented as prepared, not as a playable finished export.
- [ ] Run focused frontend/backend regressions, then the provider-disabled verifier. Commit the complete workflow unit.

**Acceptance:** With both SAM and cloud AI unavailable, an analyst can find a passage, inspect it, correct an error, build a playlist, produce an allowed export and reopen the package without losing scope or provenance.

## W02 — Add the segmentation contract and a real deterministic mask stub

**Effort:** Medium.  
**Files:** Proposed `backend/app/segmentation.py`; narrow additions to existing perception identity/artifact readers; proposed `backend/tests/test_segmentation_contract.py`. No Torch dependency in the API.

**Proposed interface:** A request binds source hash, base-tracking digest, exact source frame/PTS mapping, image dimensions, versioned box/point prompts, model alias and limits. A result binds that request to per-frame masks, source-track mapping, codec, model identity, reason codes, execution class and output digest. Internal function/class names can follow the local contract conventions; the serialized field meanings must not change silently.

**Concrete initial codec test to implement:**

```python
# Proposed new helper: rectangle_rle(width, height, xyxy).
# The 2x3 image has one background column and two foreground columns.
# Counts run down columns, start with background, and sum to width*height.
assert rectangle_rle(3, 2, (1, 0, 3, 2)) == {
    "size": [2, 3],
    "counts": [2, 4],
}
```

- [ ] Write the contract and codec tests first: real decode round-trip, empty mask, edge-clipped box, invalid dimensions, nonfinite coordinates, malformed counts, duplicate object mapping and a prompt outside the requested interval.
- [ ] Add identity tests: changed source/model/prompt/crop/precision/base tracking changes the applicable digest; unchanged inputs are reusable; unknown required input prohibits reusable identity.
- [ ] Implement only the serialized contract, its validators and deterministic rectangle stub. Store masks as a side artifact; do not insert image coordinates into `FrameData`.
- [ ] Make every stub result include explicit stub execution status. Reject a stub artifact wherever a real-model acceptance receipt is required.
- [ ] Test that importing the API/contract succeeds in the normal API-only profile without SAM/Torch/CUDA installation.
- [ ] Run focused tests and the normal verifier. Commit the contract unit.

**Exit:** Valid model-neutral artifacts can be produced, validated, saved and reopened without a GPU. This is contract evidence only.

## W03 — Implement an isolated, bounded SAM 3.1 shadow worker

**Effort:** Medium to high; exact runtime qualification is hardware-dependent.  
**Files:** Proposed `backend/segmentation_worker/` runner and image; existing remote-contract/worker-image orchestration at the narrow job-kind boundary; worker tests. SAM remains outside the API profile.

**Inputs:** W02 request, approved checkpoint digest, pinned upstream source, exact worker image and a rights-approved source window.  
**Outputs:** W02 result, source-bound receipt, mask artifacts, measured timing/memory, explicit completion/failure state.

- [ ] Write tests for rejected arbitrary artifact paths/URLs, wrong source or checkpoint hashes, excessive frame/object count, missing permission, cancellation, deadline expiry, duplicate output and cross-match session reuse.
- [ ] Implement the sealed-job entry point using the existing job/lease and artifact-transfer patterns. Do not introduce an independent scheduler or long-lived public listener.
- [ ] Pin a qualified Python/PyTorch/CUDA image and Meta revision. Provision trusted model weights with their license/access requirements; do not let requests choose arbitrary checkpoints.
- [ ] Use the official SAM 3.1 video predictor/Object Multiplex example. Record the actual checkpoint and execution mode rather than inferring version from the application class name.
- [ ] Keep one active model-owning job per GPU initially. Group relevant objects within a window, cap frame/window/object counts, and destroy session memory at job/cut boundaries.
- [ ] Verify all request/receipt tests without paid calls. Only after explicit authorization, run one bounded real-video qualification and retain real masks plus hardware/latency/VRAM evidence.
- [ ] Preserve accepted artifacts in the app's retained store before confirmed sandbox cleanup. Do not automatically retry an OOM on a larger paid GPU.

**Exit:** A real SAM 3.1 receipt and decodable masks are available for one approved window. The original tracker output is byte/semantically unchanged. Model loading alone does not pass this gate.

## W04 — Benchmark value before changing production identities

**Effort:** High because independent evidence matters.  
**Files:** Existing evaluation/scoring/manifest system; proposed `backend/scripts/benchmark_segmentation.py` and a focused test file. Extend, rather than replace, the frozen corpus.

**Inputs:** Locked independent labels, identical source frames, baseline predictions, W03 artifacts and a frozen candidate policy.  
**Outputs:** Machine-readable paired results and a human-readable error/cost comparison.

- [ ] First test that the harness rejects wrong source hashes, altered label manifests, off-grid frame scope, missing evaluated coverage, mismatched model mode and a stub presented as real inference.
- [ ] Score baseline; baseline plus shadow masks; selective ID-only candidate; optional dense SAM on the same eligible data. Keep geometry-changing candidates separate.
- [ ] Measure mask overlap/boundary error, HOTA/AssA/DetA/IDF1, ID switches, fragmentation, visible ball quality where relevant, and eligible downstream attribution.
- [ ] Measure complete end-to-end wall time, warm/cold behavior, allocated/reserved VRAM, host RAM, dispatched object-frames, cost and failure counts. Model FPS is not match processing speed.
- [ ] Break out wide/small players, occlusion, clean frames, camera transitions and reacquisition. Include easy windows so the dispatch gate's false negatives are visible.
- [ ] Freeze the selected policy after validation. Run held-out evaluation only under the existing independent-label protocol; do not tune thresholds on its results.
- [ ] Commit the evaluator and retain reproducible evidence, excluding protected media/weights from public version control.

**Exit:** There is a measured reason to keep, revise or reject segmentation. An inconclusive result leaves the feature in optional shadow/review mode.

## W05 — Promote identity-only fusion; test geometry separately

**Effort:** High.  
**Files:** Narrow perception/association seam in `video_pipeline.py` and its actual upstream tracker caller; `perception_identity.py`; proposed segmentation decision helper; existing generation/correction paths and tests. Geometry changes, if qualified, live in existing geometry policy code.

**Inputs:** Frozen base observations and W04-qualified mask evidence.  
**Outputs:** A separate enhanced-observation identity/generation or an explicit abstention, with the base preserved.

- [ ] Write tests for two-player swaps, three-player overlap, duplicate assignment, stale mask, low-confidence memory, camera cut, cropped feet, jumping player and ball out of view.
- [ ] Trace whether real association margins exist. Expose them through the smallest instrumentation seam; otherwise label overlap/reacquisition triggers as heuristic proxies and evaluate them separately.
- [ ] Implement one-to-one ID repair inside a bounded window. Preserve the baseline geometry in the first promoted policy. Insufficient evidence returns the base unchanged plus a review reason.
- [ ] Publish enhanced observations through generation/history machinery; invalidate dependent results correctly and retain undo/base inspection. Never edit frozen observations in place.
- [ ] Require the design's paired ID/coverage/HOTA/DetA gates before automatic use. Re-score ownership/event attribution; tracker improvement is not sufficient by itself.
- [ ] In a separate candidate, compare bbox ground contact with a mask/pose-supported estimate. Require eligibility, calibration validity, independent pixel/metre error and explicit abstention for airborne/occluded cases.
- [ ] Commit identity and any later geometry promotion as separately reviewable changes, with distinct policy digests and evidence.

**Exit:** The selected improvement is measurable and reversible. Failure of geometry qualification does not block ID-only or reviewer-mask use.

## W06 — Qualify the multimodal provider contract and spend bound

**Effort:** Medium to high. Can start after W01 independently of SAM.  
**Files:** `provider_gateway.py`, `provider_adapters.py`, `provider_billing.py`, `llm.py`, `report_contracts.py`, `report_store.py`, relevant settings and tests.

**Inputs:** Existing generation snapshot, approved metric/event aliases, approved source image artifacts, model policy and a caller-authorized spend limit.  
**Outputs:** A bounded provider request/receipt and validated draft, or an explicit local/unavailable disposition.

- [ ] Add failing tests for local-only source, missing cloud permission, forbidden model, no spend contract, changed rights before dispatch, stale generation before publication and duplicate request IDs.
- [ ] Extend visual evidence with exact source frame/time identity, crop transform, image dimensions and bytes/digest limits. Plain `FrameData` is not an image. Resolve only approved artifacts.
- [ ] Update request bounding to cover the actual API's image accounting, total input/output limits, reasoning and any configured tools/service mode. Keep the adapter disabled when a defensible bound cannot be established.
- [ ] Implement one `gpt-6-astra` adapter using the supported API with strict structured output. Start with a single request over selected evidence; no autonomous tool loop.
- [ ] Preserve existing admission/idempotency and uncertain-billing behavior. A timeout after possible dispatch retains an unknown outcome; explicit retry is linked to the original receipt and separately admitted.
- [ ] Reject nonexistent/cross-generation aliases and numerical claims inconsistent with the approved metric. Label interpretations; schema validity alone is not a factuality check.
- [ ] Test malicious instructions embedded in OCR/notes, missing visuals and unavailable metrics. The model never receives permission to bypass source policy or write measurements.
- [ ] Run fixture-only tests first; conduct a paid smoke only under a separately approved API budget and a rights-cleared evidence package.

**Exit:** One selected passage can receive an evidence-linked draft with a retained request/cost receipt. The current `CLOUD_SPEND_BOUND_UNQUALIFIED` guard is not removed until these requirements pass.

## W07 — Add natural-language retrieval and event-review proposals

**Effort:** Medium.  
**Files:** Existing typed-search/evidence query paths, `llm.py`/gateway task definitions, current search and insight UI, matching tests. Add no vector database initially.

**Inputs:** Analyst question plus match/generation scope and the existing event taxonomy.  
**Outputs:** A visible, validated query/filter object; Python-executed evidence results; optional interpretive answer or suggested event tags.

- [ ] Define the first supported predicates exactly: existing event type, team/player, period/time interval, review status, and calibrated pitch region. Add temporal follow-up predicates only where both events and timing are eligible.
- [ ] Write golden query cases: direct typed and natural-language versions return identical evidence; unsupported vocabulary returns a clarification/unsupported state; no result is distinguished from insufficient coverage.
- [ ] Let the model propose a typed query, never SQL or code. Validate scope, ranges and supported operations, then execute through the existing query layer.
- [ ] Show the interpreted filter in the UI. A request such as “all recoveries” cannot conceal partial camera coverage or unresolved identity.
- [ ] Route new visual event labels into existing review proposals. Save the original model/version/evidence alongside the accepted correction; rejected proposals never become metric inputs.
- [ ] Start without an autonomous loop. If a second evidence request is later permitted, cap total calls and reapply rights/budget checks before each dispatch.
- [ ] Run query, policy, generation and UI tests; commit the integrated retrieval unit.

**Exit:** Natural language improves access to the same trustworthy data without creating a separate statistical engine.

## W08 — Integrate assistant, review and presentation into one journey

**Effort:** Medium.  
**Files:** Existing `CoachInsights`, video, evidence inspector, review and playlist components; existing report/export contracts and tests.

**Inputs:** W01 selected interval, optional W03/W05 masks, W06/W07 drafts, analyst edits and the current generation.  
**Outputs:** A coherent coach-facing view and an editable evidence-linked presentation package.

- [ ] Write UI tests where selecting a report claim seeks its evidence, selecting a proposed tag opens review, accepting/rejecting creates the appropriate state, and a generation change invalidates stale suggestions.
- [ ] Add mask overlays as a display option in the existing video surface; preserve the underlying frame, scale/crop transform and track mapping. Do not create a standalone SAM tab.
- [ ] Put limitations beside claims and coverage beside statistics. A known player, an unknown track and a jersey-number candidate must not look equivalent.
- [ ] Assemble source-linked playlists from selected or reviewed passages, with editable titles, notes and existing drawing primitives. Defer a new 3D renderer.
- [ ] Verify that actual rendered clips play and an exported package reopens with the same source intervals, generation, corrections and report references.
- [ ] Verify offline behavior: existing browsing, review and presentation continue when either model backend is unavailable.
- [ ] Commit the completed experience, not disconnected model panels.

**Exit:** An analyst can explain a pattern, inspect every cited passage and turn it into a presentation without reconstructing context manually.

## W09 — Run a declared-camera, current-source product pilot

**Effort:** High evaluation/operational work; not a model-training task.  
**Files:** Existing acceptance/scoring/verification paths and feature checkpoint. Modify product code only for defects demonstrated by the pilot.

**Inputs:** The exact release candidate, approved rights and budgets, locked labels, observed GPU profile and a participating analyst.  
**Outputs:** Source-bound software/model/workflow/cost results and a decision on the declared scope.

- [ ] Run the full provider-disabled verifier at the candidate head. Preserve the old baseline for rollback; do not change gates to make the feature pass.
- [ ] Under explicit authorization, run complete declared match processing and selected SAM/Astra work. Record startup, source decode, actual inference, transfer, cleanup and any retained/unknown billing.
- [ ] Test interruption, disk pressure, worker OOM, lost session state, missing cloud service and stale evidence. No partial run is labeled a complete match.
- [ ] Execute the predeclared analyst tasks with and without assistance. Record time, correction effort, errors missed, unsupported claims and export/reopen success.
- [ ] Require independent accuracy/coverage gates for each promoted metric or model behavior. Keep unqualified outputs review-only or unavailable.
- [ ] Publish the exact accepted camera/source/model/hardware envelope, known limitations and measured cost per finished match. Do not generalize it to arbitrary broadcast footage or live multi-camera processing.
- [ ] Update the one durable status/checkpoint and close the unit only when its evidence exists.

**Exit:** A usable pilot for the declared scope, or a documented narrower release. Software completion is not reported as football accuracy qualification.

## Deferred experiments and their triggers

| Experiment | Start only when | Required comparison |
|---|---|---|
| Small VLM such as Qwen3-VL-4B | Repeated bounded Astra tasks materially dominate cost | Same independent task set, output validity and review accuracy, plus complete inference cost |
| Native-video Gemini challenger | Timestamped image sampling misses decisive motion | Identical clips/questions, source permissions, event timing and cost |
| SAM 2.1 / EfficientTAM alternative | SAM 3.1 resource limits prevent a useful deployment | Same prompts/windows and independent masks/IDs; explicit new backend identity |
| Fine-tuning / LoRA / teacher-student | A systematic error survives zero-shot prompting and fusion | Untouched parent-match test split; compare to the frozen zero-shot baseline |
| Detector / ball / calibration replacement | That specific layer is the measured limiting error | Layer-specific metrics and downstream effect, not unrelated leaderboard scores |
| Live / multi-camera | Offline analyst pilot is useful and paid demand requires it | Clock/sync error, cross-camera identity, latency/backpressure and resource admission |
| Hosted team collaboration | There is an explicit deployment/tenant requirement | Authentication, authorization, isolation, retention/deletion and media-access tests |

## Resume and verification discipline

Every unit finishes with a small durable record containing: anchor/head SHA; files actually changed; tests run and their outcomes; exact artifact/dataset/model hashes; paid calls (including none); unresolved limitations; and the next smallest action. Mark units `not_started`, `in_progress`, `blocked_on_evidence` or `accepted`; do not call a unit accepted because its code was committed.

A resumed session reads that record and the current head before acting. It does not repeat historical infrastructure smoke, regenerate a new audit, create another branch, silently change evaluation thresholds or ask for information already preserved in the checkpoint.

The implementation starts at W00/W01. It does not start by installing every candidate model, fine-tuning SAM, rewriting the tracker or opening paid cloud execution.

## Source basis

The companion design contains the pinned repository references, supplied-research hash, external primary sources and the distinction between observed facts and proposed policy. Read it alongside this plan.
