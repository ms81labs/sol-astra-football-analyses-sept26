# Astra: Catapult-style football analyst workbench — proposed design

**Date:** 22 September 2026  
**Repository anchor:** `c685640a897c16669e3b1848d77bf9e6e5d7e8cf`  
**Status:** Reviewable product/architecture proposal. Not implemented, not a claim of football accuracy, and not authorization for paid execution.  
**Companion:** `astra-catapult-style-implementation-plan-2026-09-22.md`

## 1. Decision

Build a video-first football analyst workbench around the existing Python application. Use specialist perception to produce observations, Python to compute measurements and retrieve evidence, SAM 3.1 to improve selected difficult observations, and GPT-6 Astra to interpret approved evidence. The analyst remains responsible for accepting corrections and publishing conclusions.

The product target is the workflow represented by Catapult Pro Video / MatchTracker: synchronize video and data, find passages, inspect players and events, annotate, prepare presentations, and carry evidence across sessions. Catapult describes Focus as multi-angle capture, MatchTracker as integrated analysis across datasets/sessions, and Hub as sharing. Those are useful product references, not proof that our own automatic measurements match Catapult. [E1]

Initial positioning: **an affordable, evidence-linked post-match assistant for a football analyst or coach using authorized footage**. Start with one declared camera profile, preferably an elevated wide tactical view. Broadcast footage remains useful for clip review, but statistical coverage must reflect what the camera actually shows.

Three approaches were considered:

| Approach | What it gives | Why choose or reject it |
|---|---|---|
| Add an AI report button | Smallest change; readable summaries | Insufficient as the main product: does not solve finding, checking, correcting, or presenting evidence. |
| Extend the existing analyst workbench | Search → video → correction → playlist → explanation | **Recommended.** Builds on the actual repo and delivers value before every model is qualified. |
| Replace perception with a foundation-model platform | Broad model experimentation | Reject for the first release: increases cost and uncertainty, duplicates existing infrastructure, and makes debugging responsibility harder. |

This is not initially a wearable replacement, a fully autonomous coach, a certified officiating system, or a public multi-tenant service.

## 2. What was inspected

The repository's current `main` resolved to the same commit as the attached research. Inspection covered the README, current-status document, backend/frontend structure, video orchestration, provider gateway and adapters, LLM evidence sampling, frontend composition, playlist behavior, and geometry contracts. This was source inspection, not a new execution of application tests or football inference. [R1–R8]

**Already present:** local/private-Daytona execution boundaries; source clocks and layered perception identities; calibration and analytical coordinates; generations and review concepts; provider policy/budget/evidence machinery; video, pitch, timeline, typed search, player detail and review UI components; source-linked playlist/report behavior. [R1–R8]

**Important limitations in the inspected source:**

- `provider_adapters.py` deliberately refuses cloud execution with `CLOUD_SPEND_BOUND_UNQUALIFIED`. Its existing local adapter calls the text model `deepseek-r1:1.5b`; it is not an existing visual analyst. [R4]
- The provider's `frameSamples` are serialized `FrameData`, not actual video images. Multimodal evidence transport and its cost bound must be added. [R3, R5]
- The current-status page records no acceptance-qualified independent football accuracy and an incomplete frozen labeling corpus. Earlier successful software and capacity runs are explicitly source-bound. These are recorded statuses, not a fresh inspection of the user's live annotation service. [R2]
- `PlaylistBuilder` distinguishes prepared intervals from media rendering that actually ran. A successful UI response must not be treated as proof of a playable exported video. [R7]

Do not rebuild the workbench or reopen the completed code-quality audit. Extend the smallest existing paths needed for the product.

## 3. Assessment of the attached research

### Keep its central architecture

The report's strongest recommendation is correct for this project: preserve the lightweight API, separate the SAM runtime, retain base tracking, attach masks as source-bound image-space artifacts, and make segmentation an optional, abstaining enhancement. Its insistence on separating mask, tracking and downstream analytical evaluation should become a release requirement. [U1, research lines 5–39, 159–310, 1066–1097]

### Amend its implementation examples and sequencing

1. **Ship the analyst workflow alongside the perception experiment.** The report is primarily a segmentation research plan, not a complete product plan. Search, correction, presentation, roster mapping and evidence-linked answers need explicit deliverables.
2. **Use the real SAM 3.1 video path.** Meta publishes a dedicated 3.1 Object Multiplex notebook and new checkpoints. A generic SAM image builder inside a class called `Sam31ImageWorker` does not establish that the 3.1 video backend ran. Receipts must identify the actual builder, code, checkpoint and mode. [E2, E3; U1 lines 479–521]
3. **Replace the fake mask fixture with valid RLE.** The example stub hashes a rectangle description into bytes; those bytes are not a decodable mask. Use a real deterministic rectangular mask encoding, and keep `stub=true` visible in its artifact and receipt. [U1 lines 695–753]
4. **Do not copy the illustrative micro-batcher.** Its queue is unbounded and the example does not establish shutdown, admission or per-session isolation. Reuse the existing job/lease machinery and put bounded inference inside the worker. [U1 lines 368–457; R3]
5. **Treat mask-derived ground contact as a hypothesis.** The lowest visible silhouette pixel is not necessarily a planted foot, especially during jumps, occlusion and cropping. Evaluate this independently of identity repair. [U1 lines 312–326; R8]
6. **Keep ID-only and geometry-changing modes separate.** The current Selective Mask Propagation repository distinguishes benchmark mode, which preserves tracker boxes, from production mode, which lets masks change geometry. Do not transfer its benchmark results to a different fusion policy. [E4]
7. **Use the existing pilot corpus first.** Finish the already established independent-label process and append a separately identified mask subset. Do not create a second benchmark system or use SAM-generated labels as held-out truth. [R2]
8. **Replace illustrative dates with evidence gates.** There is no defensible delivery schedule before camera quality, labels, GPU behavior and analyst acceptance are measured. Preserve the user's single integration target rather than creating a research-branch collection.

## 4. Product experience

The main screen should have one source video, a synchronized pitch view when geometry is eligible, an event/quality timeline, and a context pane. Models do not get separate dashboards. The context pane changes with the selected event, player, metric or question.

### Review

An analyst opens a match, declares teams and camera/source information, and sees processing status and coverage. They select a passage, inspect tracks and optional mask overlays, confirm or correct an event, link a track to a known player, or leave identity unknown. Corrections retain history and can be undone.

A review queue prioritizes ambiguous associations, missing ball evidence, calibration discontinuities and disputed event attribution. It must also sample apparently easy passages so missed difficult cases are discoverable.

### Analyze

Typed filters find events and passages without a model call. Initially support existing event vocabulary, team/player, period, source interval, pitch region when calibrated, and review status. A later natural-language wrapper translates a question into these same visible filters.

For example: “Find our right-side recoveries followed by a shot within ten seconds.” Python runs the temporal/spatial predicate against eligible events. The response exposes the predicate, reviewed/provisional status, matched clips and the coverage denominator. When ball or identity evidence is insufficient, the result is incomplete rather than silently exhaustive.

The question “Why did those recoveries work?” is an interpretation task for Astra using the retrieved passages, selected frames, computed measurements and contradictory examples. It is not an invitation for Astra to regenerate possession or player coordinates.

### Present

The analyst selects passages, edits titles/notes, adds track-linked highlights or pitch-space drawings, and assembles a coaching playlist with evidence-linked report text. Render only requested intervals. Preserve the editable package and source references; test actual playback and reopening, not only metadata creation.

Reusable opposition and player collections can span matches after player/roster identifiers and metric definitions are stable. Cross-match comparisons must expose camera/coverage differences.

## 5. Model roles and authority

| Layer | First choice | Responsibility | Excluded responsibility |
|---|---|---|---|
| Continuous perception | Existing detector/tracker and auxiliary ball path | Candidate players, ball, associations and source observations | Guaranteed whole-match identities or statistics |
| Segmentation enhancement | SAM 3.1 in an isolated GPU runtime | Masks, review silhouettes, overlap evidence and candidate identity repair | Sole ball detector, pitch calibration, roster identity or final events |
| Geometry and analytics | Existing Python code | Source-clock alignment, calibration, eligible positions, metrics and queries | Treating missing observations as measured data |
| Interpretive assistant | GPT-6 Astra via existing provider gateway | Explain selected evidence, suggest tags, draft reports and queries | Publishing unsupported counts, rewriting source tracks or autonomously approving corrections |
| Low-cost semantic challenger | Qwen3-VL-4B-Instruct, only after a measured need | Repeated bounded visual/tagging tasks | Assumed football accuracy or mandatory always-on residency |
| Optional temporal challenger | A qualified Gemini video-capable model | Cases where sampled images omit decisive motion | Initial dependency or a way around source-rights/cost controls |

The small-model and Gemini choices are candidates, not claimed football winners. Qwen's model card provides a concrete small multimodal baseline. Google's current video documentation offers a separate comparison path. Neither should be installed merely to make the stack look sophisticated. [E7, E8]

GPT-6 Astra's current API model is `gpt-6-astra`. It accepts text and images and supports function calling and structured outputs; the model page does **not** list native video input support. Therefore the initial integration uses timestamped source frames/crops and structured evidence, not a full-match MP4 request. [E5]

## 6. Data flow

```text
Authorized video / compatible existing tracking input
                    |
Existing ingest, source clock, jobs, storage
                    |
Existing detector + tracker + ball observations
                    |
        +-----------+-------------------------+
        |                                     |
Base observations                    Bounded ambiguity windows
        |                                     |
        |                         Isolated SAM 3.1 video worker
        |                                     |
        |                         Immutable masks + run receipt
        |                                     |
        +----------> Candidate fusion / abstention
                                      |
                    Existing calibration and Python analytics
                                      |
                    Review, correction history and generations
                                      |
                   Approved evidence for a selected question
                                      |
                   Existing gateway -> Astra -> validation
                                      |
                 Video / pitch / timeline / playlist / export
```

The actual insertion point must retain image-space boxes, exact source-frame identity and the mapping to the base tracker before projection publication. `process_video_input()` is the orchestration seam, but internal tracker assignment margins are not proved available by that wrapper. Start with explicitly named overlap/reacquisition proxies if necessary; never label such a heuristic as a calibrated probability. [R6]

### Evidence states

Keep raw model observations, proposed interpretations, analyst-reviewed records and generated reports distinguishable. A report can refer to an observation without making it independently verified. A valid evidence ID proves referential integrity, not that the prose logically follows from the evidence.

`trackId` identifies a tracker trajectory, not a person across a whole match. Team color clusters, jersey candidates, roster IDs and track IDs need distinct meanings. Player mapping can remain unknown. Camera cuts and reappearance must not silently merge identities.

### Segmentation artifact

Minimum payload: schema version; source/media hash; parent base-tracking digest; exact source interval and frame/time mapping; prompt policy and prompt-to-track mapping; image dimensions and coordinates; model/worker/checkpoint identities; masks with an explicit codec; backend/mode/stub status; rejection reasons; run usage; output digest.

Use a compact side artifact rather than dense masks inside analytical `FrameData`. A simplest portable initial codec is uncompressed column-major RLE with validated integer counts; a later compressed codec is a versioned format change, not interchangeable bytes.

Layer the new segmentation and fusion identities on top of the existing base identities. Reuse depends on all determining inputs. A review-generation change alone should not force rerunning unchanged perception, while a changed track prompt, crop, calibration-dependent input or model must invalidate the applicable result.

### Worker lifecycle

Keep Python 3.11/API dependencies separate from the SAM environment. Meta's current requirements are Python 3.12+, PyTorch 2.7+ and CUDA 12.6+; qualify an exact image rather than treating these lower bounds as a tested deployment. [E3]

Use the existing private-Daytona execution boundary and job ledger. Begin with one active segmentation job per GPU, bounded frame/object/window sizes, a job deadline and explicit cancellation. Each video window owns its session. Do not share SAM memory across matches or camera cuts. Preserve completed artifacts outside an ephemeral sandbox before cleanup; retries must not claim continuity of lost session state.

Do not add Kubernetes, a second queue service, a model-router framework or a second database. SAM plus the deterministic stub is enough to establish the interface.

## 7. Astra integration

Extend the existing `ApprovedEvidencePackage` and spend policy. Preserve source/generation aliases, availability exclusions, request idempotency, policy checks, retained billing outcomes and stale-publication rejection. [R3]

Approved visual evidence needs an allowlisted artifact identifier, source interval/frame identity, crop transform, media digest, image dimensions and byte/token limits. Resolve artifacts server-side; no arbitrary model-provided URLs or filesystem paths.

An answer contains bounded claims with evidence references, explicit interpretation status, limitations and proposed clips. Numerical claims must be tied to the exact approved metric and units. Missing metrics stay unavailable. New tags remain proposals until accepted through the normal correction path.

Start with one request over already selected evidence. Add question-to-filter translation only after that works. The model proposes a validated typed query, Python executes it, and the UI displays it. Do not give the model arbitrary SQL, a shell, general browsing, write access or control over cloud policy. Bound any later tool loop and authorize every billed continuation.

Recorded image content, subtitles, OCR and analyst notes are untrusted data, not instructions to override the assistant's tool permissions. Returned evidence aliases and source generations must be validated even when the JSON schema passes.

## 8. Evaluation and release policy

There are separate gates for software correctness, model accuracy, analytical reliability and analyst usefulness. Passing one cannot substitute for another.

Use the existing frozen football protocol and source alignment. Split and tune by parent match/source, not nearby frames. Finish independent labels before accessing held-out predictions. A small rights-cleared mask subset supplements tracking/ball/pitch labels; teacher-generated masks are training proposals, not independent test truth.

Compare the unchanged baseline, baseline plus masks without fusion, selective ID-only fusion, and optional dense SAM. Geometry-changing fusion is a separate experiment. Freeze every evaluated model, checkpoint, prompt, source and fusion configuration.

Starting promotion targets for identity fusion, adapted from the attached report, are **at least two absolute AssA points or a 20% reduction in verified ID switches**, with no more than 0.5 points degradation in HOTA/DetA and no loss of evaluated coverage used to game the result. These are proposed project gates, not published industry standards or a promise of achievable improvement. Report absolute counts, coverage, hard/easy subsets and uncertainty at match level. [U1 lines 1099–1135]

Ground-contact refinement must improve independently labeled error in its eligible subset without hiding failures in abstention. Team/roster mapping, ball visibility, possession and event attribution need their own evaluation. Existing experimental shot-quality estimates must not be relabeled as calibrated xG.

For workflow value, predeclare a small set of analyst tasks: find a passage, correct an identity, produce a player playlist, explain a supported pattern and reopen an exported package. A proposed pilot target is at least 20% less analyst time than the same app without the new assistance, with no reduction in required review accuracy. Measure the result; do not assume it.

## 9. Cost, rights and deployment

The previously reported approximately $1,200 Daytona credit is a planning constraint, not a verified current balance. Do not spend it all on training. Propose an initial capped experiment, for example $75 GPU and a separate $25 API budget, and release any further budget only after measured results. These numbers are approval proposals, not authorization.

Measure complete cost per finished match: allocated GPU/CPU/RAM time, startup and checkpoint loading, decode and transfer, storage, provider tokens, billed/unknown retries and final artifact preservation. Report detector/tracker throughput separately from exported FPS and model-only throughput.

OpenAI lists standard Astra token prices of $10/million input and $50/million output at this research date. Image accounting, reasoning, caching, tools and service modes must be covered by the actual admission bound. ChatGPT subscription billing and API billing are separate. [E5, E6]

SAM uses the SAM License rather than assuming Apache-style distribution; checkpoint access and distribution terms must be reviewed for the deployment. Audit detector and dataset licenses too. The plan does not make a legal determination. [E3]

Remote processing must use existing source-rights controls. Daytona currently documents shared GPU placement in its global `earth` region, ignoring a requested shared-region target. Do not promise EU-only processing by setting `target='eu'`; a qualified locality arrangement is needed for such a promise. [E9]

The app is currently documented as a trusted loopback tool. Before club-wide hosted collaboration, implement and verify authentication, authorization, tenant/media isolation, retention, deletion and deployment hardening under the existing network gate. Public sharing is not bundled into the first model experiment. [R1]

## 10. Explicit non-goals and later triggers

**No full SAM fine-tuning first.** Add adapters, LoRA or distillation only after a repeatable football error class survives prompting/fusion and a untouched evaluation split exists.

**No new primary tracker first.** Benchmark a challenger only when identity evidence shows the baseline limits progress. SoccerNet Game State Reconstruction is a useful reference for separate calibration, athlete identity and tracking components, not a second application to adopt wholesale. [E10]

**No native-video provider fleet first.** Add one temporal challenger only when an evaluation demonstrates that frame sampling loses important evidence.

**No live multi-camera promise first.** Later live mode requires clock mapping, camera synchronization, identity linking, backpressure and late-result semantics. A replay is not automatically a synchronized second viewpoint.

**No wearable or refereeing claims from monocular masks.** Video-based position estimates are not GNSS/IMU measurements, full off-screen workloads or precise 3D officiating evidence. Blender can later visualize qualified geometry; rendering does not improve measurement certainty.

## 11. Definition of the first useful release

A user opens an authorized match, selects or searches a passage, inspects its evidence, corrects an error, creates a source-linked playlist, requests an evidence-grounded explanation when cloud use is allowed, and exports/reopens the result. The workflow works with SAM disabled and with the API unavailable. Optional SAM and Astra results are clearly identified and cannot overwrite reviewed truth silently.

The smallest starting implementation is this workflow on a retained development fixture, accompanied by the existing independent-label work. The first GPU integration is bounded SAM shadow mode, not an all-match tracker replacement.

## Sources and inspection anchors

**U1 — User-supplied research:** `deep-research-report (2)(1).md`, “Integrating SAM 3.1 and State-of-the-Art Video Segmentation into Astra.” SHA-256: `3b90d5470e314e8288b7aa6a4719995c3ee1287b804ea22426181cf0e82d05c8`. Line references above refer to the supplied, line-numbered research rendering.

Repository references below are pinned to `c685640a897c16669e3b1848d77bf9e6e5d7e8cf`. Source inspection establishes what the files contain; it does not establish runtime performance or current live-service state.

- **R1:** README — https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/c685640a897c16669e3b1848d77bf9e6e5d7e8cf/README.md
- **R2:** Recorded current status — https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/c685640a897c16669e3b1848d77bf9e6e5d7e8cf/docs/status/current.md
- **R3:** Existing policy, evidence, budget and publication gateway — https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/c685640a897c16669e3b1848d77bf9e6e5d7e8cf/backend/app/provider_gateway.py
- **R4:** Current provider adapters — https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/c685640a897c16669e3b1848d77bf9e6e5d7e8cf/backend/app/provider_adapters.py
- **R5:** LLM payloads and structured frame sampling — https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/c685640a897c16669e3b1848d77bf9e6e5d7e8cf/backend/app/llm.py
- **R6:** Perception orchestration and projection seam — https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/c685640a897c16669e3b1848d77bf9e6e5d7e8cf/backend/app/video_pipeline.py
- **R7:** Existing frontend composition and playlist behavior — https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/c685640a897c16669e3b1848d77bf9e6e5d7e8cf/frontend/src/App.tsx ; https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/c685640a897c16669e3b1848d77bf9e6e5d7e8cf/frontend/src/components/PlaylistBuilder.tsx
- **R8:** Existing calibration contracts and holdouts — https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/c685640a897c16669e3b1848d77bf9e6e5d7e8cf/backend/app/workbench/geometry.py

External primary sources were checked on 22 September 2026. Availability, APIs, prices and licenses should be rechecked when their implementation task begins.

- **E1:** Catapult Pro Video — https://www.catapult.com/pro-video
- **E2:** Meta SAM 3.1 release notes — https://github.com/facebookresearch/sam3/blob/main/RELEASE_SAM3p1.md
- **E3:** Meta SAM source, prerequisites and license reference — https://github.com/facebookresearch/sam3
- **E4:** Selective Mask Propagation, original implementation — https://github.com/holma91/selective-mask-propagation
- **E5:** OpenAI GPT-6 Astra model documentation — https://developers.openai.com/api/docs/models/gpt-6-astra
- **E6:** OpenAI separate ChatGPT/API billing — https://help.openai.com/en/articles/9039756
- **E7:** Qwen3-VL-4B-Instruct model card — https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct
- **E8:** Google video capability reference — https://blog.google/innovation-and-ai/models-and-research/gemini-models/introducing-agentic-video-in-gemini/
- **E9:** Daytona GPU sandbox and region behavior — https://www.daytona.io/docs/sandboxes ; https://www.daytona.io/docs/regions
- **E10:** SoccerNet Game State Reconstruction — https://github.com/soccernet/sn-gamestate
