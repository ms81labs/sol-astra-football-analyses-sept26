**TECHNICAL STRATEGY  /  PRODUCT DELIVERY** 

# **Guerilla Analytics** 

_Python-first football analysis_ 

Comprehensive implementation plan | Version 1.1 

An evidence-led analyst workbench with a Python foundation, a profiled native video layer, specialist models and selectively routed frontier AI. 

##### **FOUNDATION** 

Python orchestration, geometry, metrics and validation 

##### **INTELLIGENCE** 

Task-specific perception and optional grounded assistance 

##### **ECONOMICS** 

Reusable evidence, bounded computation and measured review effort 

<u>ms81labs / sol-astra-football-analyses-sept26</u> 

Source snapshot: 5099e1fd50d856a7cd0449f1ef4b1695d8f930c3 

Planning revision 1.1: 16 September 2026 

Source-level findings, proposed designs and illustrative budgets are explicitly separated. No application code, cloud jobs or account balances were changed or tested for this document. 

Repository-specific planning document  •  Version 1.1 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **Version 1.1 — what changes** 

Decision: keep the product strategy; strengthen the media/performance implementation. This replaces the original edition as the working plan without replacing its Python foundation or relaxing any football-accuracy gate. 

|**Area**|**Revision**|**What remains unchanged**|
|---|---|---|
|Sampling and<br>clocks|Separate decoded frames, inference inputs,<br>tracker updates and exported samples. Audit<br>the inspected result-filtering loop.|Frozen source identities and<br>evaluation cadence.|
|Video architecture|Introduce a FrameSource / preprocessing<br>boundary and benchmark native libraries<br>before custom code.|FastAPI, React, evidence-led analytics<br>and the sealed-worker contract.|
|Acceleration|Compare CPU/native decode, GPU-resident<br>decode and optimised inference<br>independently.|No assumed speedup, no automatic<br>increase in cloud spending.|
|Rust and C++|Keep gated extension/worker options, not<br>mandatory application languages.|The first analyst workbench can ship<br>without either.|
|Delivery and cost|Add GA-15 to GA-18; require<br>timing/cost/quality receipts and safe fallback.|Original GA-01 to GA-14, independent<br>labels and review-first release<br>strategy.|



### **Where to read** 

Section 4.5 corrects the sampling baseline. Sections 4.5A-D specify technology choices, frame/GPU contracts, benchmarks and native-code gates. Sections 6-9 integrate cache keys, costs, milestones, packaging and operational checks; section 8.5 adds the executable work packages. 

### **Evidence and scope** 

The primary tracking call in the pinned source returns model results before the exportsampling condition is applied, with no explicit vid_stride at that call site. This is a verified source observation, not a measured runtime or saving. Effective settings, invocation counts and tracking quality still require an authorised benchmark. [R10, V01] 

Original references and section numbering are retained. New suffix sections avoid breaking existing references. The repository has not been edited, and no Daytona job was launched. Revision sources are listed in Source registers V- VI. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

2 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **Executive brief** 

Recommendation. Evolve Guerilla Analytics into an evidence-led football analyst's workbench. Retain Python orchestration, geometry, state estimation, metrics and validation. Use native media/inference libraries through replaceable adapters; add custom Rust or C++ only after profiling. Keep compact task models and bounded frontier-model assistance optional. Do not rebuild around a video chatbot or a language rewrite. 

The first product promise should be: **upload supported footage, find useful passages, correct uncertain observations, and publish analysis whose claims lead back to evidence** . Automated player totals, physical performance, offside judgments and general-camera support are separate capabilities with separate acceptance gates. 

### **What changes first** 

|**Priority**|**Deliverable**|**Reason**|
|---|---|---|
|P0|Independent labels, source/team<br>declarations and sampling audit|Accuracy and actual inference cost<br>both need evidence; saved fps is not<br>inference fps.|
|P0|Versioned evidence and metric-<br>availability contracts|Prevent estimates, unknowns and<br>reviewed facts from being mixed.|
|P1|One declared-camera workflow with<br>calibration and correction tools|Constrain the problem and make the<br>product useful before full automation.|
|P1|Measured player/ball coverage and<br>identity improvements|Downstream analytics depend on<br>these observations.|
|P2|Budget-controlled language assistance|Add convenience after the evidence<br>layer is dependable.|



### **Basis and limits** 

This plan expands the nine areas of the original repository review at snapshot 5099e1fd50d856a7cd0449f1ef4b1695d8f930c3. Version 1.1 rechecks selected video-loop spans at that same commit and adds primary video/runtime sources. It is not a fresh audit of the moving main branch. Original findings and historical execution records remain attributed, not reproduced. [R01-R10] 

No application tests, inference, deployments, cloud jobs, repository edits or account checks were performed for this revision. Document generation and layout checks are not application validation. The update targets video/native engineering; other original model, price and rights references are retained, not independently refreshed. Verify them before procurement or release. 

**Interpretation rule.** “Current” means present in the inspected source or reported by its status record. “Proposed” means an implementation recommendation. Numerical acceptance targets and cost scenarios introduced here are planning assumptions, not measured results, contracts, or replacements for the repository's frozen evaluation protocol. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

3 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **Reading map and decision hierarchy** 

The document follows the previous review, but separates large topics into implementationsized workstreams. Section numbers identify topics rather than maturity: a later-numbered data-contract change may be a prerequisite for an earlier-numbered product feature. 

|**Previous review point**|**Expanded**<br>**sections**|**Primary output**|
|---|---|---|
|1. What exists and should be kept|**1.1-1.2**|Retain/extend/defer decisions and build-versus-buy<br>choices|
|2. Target architecture|**2.1-2.2**|Runtime boundaries, job lifecycle and deployment<br>modes|
|3. Analyst's workbench|**3.1-3.2**|User journey, screens, corrections and product<br>acceptance|
|4. Fix the measurements first|4.1-4.8, including<br>4.5A-D|Media, native runtime, benchmarking, geometry,<br>perception, metrics and incident review|
|5. Small models and frontier<br>models|**5.1-5.4**|Model roster, routing, grounding and training plan|
|6. Data contract|**6.1-6.3**|Evidence schema, persistence, APIs and migration|
|7. Economics|**7.1-7.3**|Cost equations, scale scenarios and credit allocation|
|8. Roadmap and validation|8.1-8.5|Independent evaluation, milestones and backlog<br>GA-01 through GA-18|
|9. Deployment and licensing|**9.1-9.3**|Rights, security, operational readiness and risks|



### **Order of authority** 

The repository's current safety gates, frozen evaluation protocol, source manifests and authorisation boundaries remain authoritative for existing work. This document does not authorise a new cloud run, change a locked label, relax a truth gate, enable an inert research track, or retire a compatibility reader. Any such change needs its own reviewed decision. [R01, <u>R02, R07]</u> 

Use the plan in three passes. First, select the initial camera profile and product deliverable. Second, implement the evidence, review and evaluation prerequisites. Third, choose each model or infrastructure upgrade against those acceptance requirements and its total cost. A more capable model is a candidate, not an architectural dependency. 

### **A practical definition of success** 

A successful pilot produces a reviewed match package containing source-linked clips, explicit coverage, reproducible metrics, retained corrections and an understandable limitations statement. Its cost includes processing, retained storage, retries and analyst effort. It still works when every language-model endpoint is disabled. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

4 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

The defensible advantage is not “we call the latest model.” It is a workflow that turns imperfect footage into auditable, useful coaching evidence with less effort. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

5 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **1.1 Repository baseline and evidence classes** 

The application already owns upload, orchestration, analytics, persistence and presentation. Its documented remote boundary is a private, ephemeral Daytona worker; RunPod is retired from active execution. The README explicitly limits the current API to a trusted, loopback deployment. [R01] 

The status record distinguishes five evidence classes. Preserve that separation in project reporting and the release dashboard instead of collapsing everything into one green “ready” badge. [R02] 

|**Evidence class**|**What the repository reports**|**Planning consequence**|
|---|---|---|
|Software verification|Provider-disabled gates pass for a<br>recorded release source; the latest<br>documented source binding is not<br>identical to the inspected main SHA.|Keep source-bound receipts. Do not<br>claim this document reran<br>verification.|
|Pipeline execution|Earlier-source sealed local CPU runs<br>completed short clips.|Prove the exact candidate source<br>before a product acceptance claim.|
|Independent accuracy|No acceptance-qualified tracking, ball,<br>pitch, possession or event score.|Keep automatic outputs review-only.|
|Capacity|Historical intact-half executions<br>completed in 8,378.199 and 8,145.772<br>seconds.|Use as historical diagnostics, not<br>current throughput or billing.|
|Analyst acceptance|No declared-camera pilot accepted by<br>the intended analyst.|Run a real workflow study in addition<br>to model scoring.|



### **Work package: baseline dossier** 

Create a small release dossier containing the selected commit, model hashes, dependency/environment manifests, supported camera declaration, test receipt, input identities, evaluation protocol version and unresolved gates. Link large artifacts rather than copying them into multiple status pages. Record whether each result was reproduced, imported from historical evidence, or merely proposed. 

Add an operator-readable capability matrix: manual review; team-level tactical estimates; event suggestions; player attribution; physical metrics; incident review. Each capability has an independently visible status and evidence link. An application can be usable for manual tagging while tracking acceptance remains pending. 

### **Keep the research lane contained** 

The inspected addon architecture is explicitly a parallel, isolated research lane. Only its declared supported-coverage track is executable; planned tracks must remain inert until separately enabled. Its append-only trial history and path guards are useful foundations, not permission for autonomous production changes. [R07] 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

6 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

**Exit condition:** a new contributor can identify exactly what is implemented, what was measured on which source, what remains unproven, and what actions are permitted without opening historical runbooks or guessing from a test count. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

7 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **1.2 Retain, extend and buy selectively** 

Retain the FastAPI/Pydantic application boundary, the React/TypeScript frontend, local-first persistence and the sealed-worker interface. The inspected frontend uses React, Vite, TypeScript and Tailwind; the backend schemas already represent match state, events, jobs and review bundles. A Python foundation does not require replacing that interface with a Python dashboard framework. [R01, R03, R09] 

|**Component**|**Decision**|**Implementation boundary**|
|---|---|---|
|FastAPI and Pydantic|Retain and extend|Validate commands and evidence;<br>keep expensive jobs outside request<br>handlers.|
|React/TypeScript|Retain|Reuse existing screens; add quality,<br>provenance and correction<br>interactions.|
|NumPy/Python analytics|Retain|Pure, versioned functions; no<br>language-model arithmetic.|
|SQLite and artifact files|Retain initially|Improve transactional metadata and<br>immutable run artifacts before scaling<br>out.|
|Vision runtime|Profile first; native adapters|Separate decoding, sampling,<br>preprocessing and model runtime. No<br>whole-application rewrite.|
|Language-model<br>integration|Refactor into an optional capability|Explicit model policy, structured<br>responses, budgets and deterministic<br>fallback.|



### **Build-versus-buy choices** 

Use established libraries for generic infrastructure and retain ownership of football semantics. Kloppy provides vendor-independent event/tracking models and transformations; evaluate it at import/export boundaries rather than replacing internal provenance. Socceraction provides SPADL, xT and VAEP building blocks; use them only after your events map correctly to their definitions. TrackEval is a reference implementation for tracking metrics. [E01-E03] 

Use the existing CVAT setup for independent labelling instead of building a second annotation platform. Build the smaller correction interface needed by your analyst inside the application. Corrections and blind evaluation labels are different products, even when both contain coordinates. 

Commercial products are useful workflow references, not evidence that your pipeline has equivalent accuracy. Hudl Sportscode describes customised coding, timelines and video-linked reports. Veo describes integrated match analytics, radar and player-level workflows with product-specific requirements. The proposed differentiation is camera-explicit, local-first, evidence-linked analysis, not an unsupported claim to outperform either vendor. [E04, E05] 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

8 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

### **Adoption rule** 

For every new dependency, record its exact version, code and weight licences, maintenance status at selection, required hardware, test coverage and removal path. An adapter must be replaceable without changing event definitions or rewriting stored evidence. Avoid adding a vector database, distributed broker or orchestration framework until a measured workload needs it. 

**Exit condition:** every addition has a concrete job, an owner, a benchmark or workflow justification, and a rollback path. No dependency is included merely because it is fashionable. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

9 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **2.1 Target architecture: evidence before interpretation** 

Use a modular application with separately executed heavy workers, not a premature fleet of microservices. The application remains the control plane: it accepts user intent, applies rights and budget policy, creates jobs, validates results and publishes accepted artifacts. A worker performs only the bounded work described by its job manifest. 

|**Layer**|**Responsibilities**|**Must not do**|
|---|---|---|
|Analyst workspace|Video, timelines, pitch view, review,<br>reports|Treat a generated claim as a<br>measurement.|
|Application/control plane|Authentication when deployed,<br>configuration, queues, permissions,<br>costs|Run GPU inference inside an HTTP<br>request.|
|Media and perception|Native decode/preprocess/inference;<br>timestamped tracking and calibration|Decide that uncertain observations are<br>accepted facts.|
|Evidence and analytics|Version state, apply quality gates,<br>compute metrics/events|Hide missing coverage or silently<br>reuse stale results.|
|Optional assistance|Search translation, synthesis,<br>explanations, suggestions|Alter evidence, unlock labels, launch<br>jobs or publish autonomously.|



### **End-to-end flow** 

```
Upload and rights declaration
```

```
    -> immutable source identity and media probe
```

```
    -> camera/period/team configuration
```

```
    -> bounded perception job
```

```
    -> validated observations and coordinate transforms
```

- <mark>`-> state estimation, event candidates and quality gates`</mark> 

- <mark>`-> analyst correction and reviewed evidence bundle`</mark> 

```
    -> deterministic metrics, playlists and template report
```

- <mark>`-> optional small-model draft / selected stronger-model review`</mark> 

```
    -> validated, analyst-approved publication
```

Measurement, calculation and interpretation remain separate. A detector outputs a player box. A calibration maps a suitable ground-contact point to the pitch with uncertainty. Python derives a distance from accepted positions. A language model may explain a reviewed passage, but it cannot promote guessed positions into observations. 

### **Dependency graph** 

Store stage outputs so the system knows what must be recomputed. A report-template edit changes only the report. A team-selection correction may affect possession, events and team summaries. A homography correction affects pitch-space positions and dependent metrics but should reuse compatible image-space detections. A detector change invalidates its downstream tracking and state results. 

The existing storage manifest already distinguishes raw rows, match state, analytics, events and reporting files; extend that boundary rather than create a competing source of truth. [R08] 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

10 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

**Acceptance:** with AI endpoints unavailable, an analyst can still upload supported media, review it, edit tags, inspect valid measurements, create a playlist and export a deterministic report. No network failure can silently replace missing metrics with generated numbers. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

11 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **2.2 Jobs, deployment modes and operational boundaries** 

Model long-running work as durable jobs with explicit states: submitted, validating, waitingfor-capacity, running, importing, complete, failed, cancelling and cancelled. A provider timeout during submission creates an **outcome-unknown** condition requiring reconciliation; it must not trigger a blind duplicate allocation. 

### **Job contract** 

A job manifest identifies source bytes, interval, time mapping, camera profile, model/config hashes, output schema, limits, expiry and authorised location. Add decoder/backend versions, pixel format, precision, temporal policy and fallback policy. Declare development, production, validation or held-out evaluation. Record the selected backend and actual hardware in the execution receipt, not just the requested profile. 

Separate an idempotent job request from each execution attempt. Retried attempts share the original request identity but have distinct attempt records. Import a completed attempt atomically only after hash, schema, frame-scope and completeness checks. Quarantine partial artifacts. Checkpoint chunks only where a model's temporal state can be preserved or restarted correctly. 

|**Deployment mode**|**Intended use**|**Required controls**|
|---|---|---|
|Local-only|Private pilot, manual review, offline<br>operation|Loopback binding, protected local<br>storage, no silent cloud fallback.|
|Local app plus burst GPU|Heavier vision workloads with an<br>approved burst-compute budget|Host-only provider credentials,<br>bounded worker, receipt validation,<br>verified cleanup.|
|Hosted collaboration|Multiple clubs or analysts|Separate network/security gate, tenant<br>isolation, access control, managed<br>backups and processor review.|



### **Daytona integration** 

Keep the current private, ephemeral worker boundary. Do not re-run the retired infrastructure smoke; future candidate evaluation requires the repository's current authorisation and source-bound procedure. Historical sandbox listings are not proof of present state. This document did not inspect live provider resources. [R01, R02] 

Reserve budget before allocation; use a lease and a cancellation flag; reconcile remote state before retry; retrieve permitted artifacts; then verify deletion or the declared terminal lifecycle state. Record cleanup failure as an operational incident, not as successful completion. Never place the host provider credential inside the worker environment. 

Daytona's documentation says GPU region requests are ignored by default, so a region-specific processing requirement must be confirmed separately. Billed reservation and lifecycle state matter more than observed utilisation; capture actual account charges during an authorised benchmark. [E06, E07] 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

12 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

**Acceptance:** exercise timeout-before-response, lost connection, partial upload, corrupt output, disk exhaustion and cleanup failure with mocks or local fixtures first. Each scenario has an unambiguous recovery state and cannot exceed the declared spend through unlimited retries. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

13 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **3.1 The analyst's workbench: complete user journey** 

Begin with post-match analysis for one explicitly supported camera profile. Offer manual review for other media, but do not imply that their automated metrics are accepted. For your existing panoramic material, “fixed panoramic/tactical camera” is a sensible candidate profile only after its distortion and coverage have been characterised; it is not automatically the easiest source. 

### **From upload to reviewed match** 

The analyst creates a match, selects footage, records ownership/permission, chooses teams and periods, and declares pitch dimensions or leaves them unknown. The app probes the media and shows a support assessment. A rejected automation profile should still offer permitted manual tagging, with an explanation of what cannot be measured. 

Next, the analyst confirms camera calibration and team mapping. Team colour clusters are suggestions, not semantic home/away labels. The application then estimates the work and cost, obtains the necessary processing authorisation, and creates a bounded job. Existing independent-evaluation declarations follow their stricter pre-prediction process rather than this ordinary production workflow. [R02, R03] 

After processing, the workspace presents candidate events and a quality timeline. The analyst reviews high-impact uncertainty first: incorrect team selection, calibration drift, identity switches and ambiguous possession around a shot. Corrections are saved as edits with provenance, never as destructive overwrites of raw observations. 

Finally, the analyst builds a playlist and report. Each factual claim has a time interval or metric reference. A report may say that a pattern occurred in three reviewed passages; it must not silently imply those passages establish a whole-match frequency. 

### **Evidence status in the interface** 

Use separate visual indicators for **observation source** and **review status** . An inferred ball location can be reviewed and still remain inferred. A visible detector observation can remain unreviewed. Use text and icons as well as colour so the distinction remains accessible. 

|**User action**|**Immediate response**|**Deferred consequence**|
|---|---|---|
|Correct a team<br>assignment|Show the new mapping and affected<br>intervals|Recompute dependent team metrics<br>under a new version.|
|Split or join a track|Preview identity changes|Invalidate affected player totals and<br>events.|
|Reject an event|Remove it from accepted views|Retain the candidate and rejection<br>reason.|
|Correct calibration|Preview landmark fit|Rebuild dependent pitch-space<br>artifacts.|



**Product acceptance:** an intended analyst completes a real reviewed match without developer intervention. Measure correction time, missed useful passages, export usefulness and trust— not only whether every button responds. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

14 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **3.2 Screens, interactions and MVP boundaries** 

The core screen is a synchronised video, event timeline and pitch view with an evidence inspector. The same selected time interval drives all panels. The player should use source presentation time, while the UI may display match time through an explicit mapping. Do not confuse a timestamp overlay with frame-accurate alignment. 

|**Surface**|**MVP behaviour**|**Later enhancement**|
|---|---|---|
|Match library|Search, source identity, configuration,<br>processing status and review status|Cross-match comparisons with<br>compatible definitions.|
|Setup wizard|Periods, dimensions, camera profile,<br>team mapping, calibration and rights|Assisted landmark selection and saved<br>camera profiles.|
|Review workspace|Frame stepping, variable playback<br>speed, candidate tags, uncertainty<br>shading|Multi-angle synchronisation and<br>temporal model suggestions.|
|Evidence inspector|Observation source, model/config<br>version, uncertainty and edits|Side-by-side model comparison for<br>development material.|
|Playlist/report builder|Time-bounded clips, notes, stable<br>metric references and template export|Optional grounded narrative drafting.|
|Operations view|Job phase, estimated/actual cost, retries<br>and cleanup result|Multi-user quotas and fleet scheduling.|



### **Interaction requirements** 

Use keyboard shortcuts for play/pause, previous/next candidate, marking in/out, accepting/rejecting a suggestion and undo. Provide an undoable change history. Autosave accepted edits transactionally and show whether an edit is saved, pending or conflicted. Do not silently replace another analyst's correction; hosted collaboration needs optimistic concurrency or explicit locking. 

For a selected player, show interval-limited observations until identity continuity is validated. For a selected metric, show its unit, denominator, eligible duration, exclusions and definition version. Unknown should render as unavailable, not zero. The inspected schemas contain several zero-valued metric defaults; migration must preserve old readers while introducing explicit availability. [R03] 

### **What the first release deliberately excludes** 

Exclude automatic official offside/foul rulings, inferred whole-match distance from fragmented tracks, guaranteed live latency, arbitrary-camera accuracy, player identity across seasons and autonomous publication. Keep basic telestration and a 2D pitch view ahead of expensive 3D work. These exclusions reduce both cost and misleading output. 

### **Suggested workflow targets** 

Before the pilot, agree task-based targets with the analyst: locating a known passage, correcting a team, repairing an identity, explaining a withheld metric and creating a training 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

15 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

playlist. Proposed technical targets are p95 metadata/API reads below 500 ms on the declared local test setup and a usable timeline without loading all frame records at once. These are planning targets, not current measurements or a promise about video decode latency. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

16 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **4.1 Media ingestion, clocks and camera profiles** 

**Objective:** every observation and clip must point to the correct source moment. A good detector evaluated against the wrong frames is not a valid system. 

Store the original upload as an immutable asset with a SHA-256 digest, byte size and media metadata. Probe codec, dimensions, duration, frame timing, rotation, audio tracks and decode errors. FFprobe exposes stream and frame information suitable for this ingestion step. Probing is not sufficient: sample-decode the beginning, middle and end, and record any discontinuities discovered during full processing. [E20] 

Keep source presentation timestamps and the rational time base. Do not calculate every timestamp as frame number divided by nominal frame rate; variable-frame-rate footage, dropped frames and edited video need explicit mapping. Preserve separate identifiers for source frame, decoded presentation time, processing sample and displayed match clock. 

### **Source and camera admission** 

|**Profile**|**Initial supported workflow**|**Measurement restrictions**|
|---|---|---|
|Stable elevated wide|Candidate for team-shape and event|Validate far-side visibility, calibration|
|view|review|and ball size before automation.|
|Stitched panoramic view|Camera-specific development profile|Check seams and distortion; a single<br>global homography may be<br>inadequate.|
|Broadcast with cuts and<br>zoom|Shot-segmented event indexing and<br>manual review|Do not claim continuous full-team<br>tracking or distance totals.|
|Handheld or low-angle<br>view|Manual tagging first|Withhold physical and full-team<br>metrics until separately qualified.|



These are proposed admission categories, not certifications of the current implementation. The first automatic profile should be selected from footage you can lawfully obtain repeatedly and label consistently, not from a generic model demo. 

Create a lower-resolution browsing proxy, thumbnails and waveform as derived assets, retaining the original for small-object work. Record original-to-proxy presentation-time mapping. FFmpeg stream copy avoids re-encoding where applicable; arbitrary frame-exact exports require a validated decode/re-encode path rather than assuming keyframe seeks are exact. [V02] 

### **Evaluation and operational safeguards** 

The repository already documents source-global sampling alignment problems in its frozen corpus. Preserve the declared source start, prefix frames and clip identity when running those tasks. The fixed evaluator and protocol, not a new generic ingestion convenience, determine the permitted scoring grid. [R02] 

Reject unsafe or unsupported media before allocation. Test variable frame rate, rotation, missing audio, interrupted files, duplicate content, cuts and cancellation. Original, proxy and export must resolve to the same declared source intervals. A decoder change must preserve 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

17 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

colour order, geometry and frame identity; hardware fallback must be visible and stay within the budget. See 4.5B-C. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

18 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **4.2 Calibration and pitch-space geometry** 

**Objective:** distinguish an image location from a defensible position on a football pitch. Calibration quality is a prerequisite for distances, tactical shape and geometric incident analysis. 

The inspected wrapper accepts exactly four manual homography points or an automaticcalibration path. Keep that compatibility, but introduce a versioned calibration object that can hold additional landmarks, line observations, distortion parameters, camera segments and residual diagnostics. A migration should not reinterpret existing four-point configurations silently. [R06] 

For a new camera profile, identify known pitch landmarks and fit the mapping using geometrically valid correspondences. More well-distributed observations help diagnose poor fits; four nearly collinear or tightly clustered points do not provide reassuring whole-pitch coverage. Reserve independent landmarks for checking rather than reporting only the fit residual on the points used to estimate the transform. 

### **Calibration workflow** 

|**Step**|**Implementation**|**Reject or withhold when**|
|---|---|---|
|Define the field|Record dimensions, units, origin and<br>period-specific attacking directions|Dimensions are assumed but a metric<br>requires measured metres.|
|Select the camera model|Test planar, distortion-corrected or<br>segmented mappings|A stitched seam or zoom change<br>breaks the chosen model.|
|Fit and inspect|Overlay projected pitch lines and<br>independent landmarks|Residuals or line alignment are<br>unacceptable in an eligible region.|
|Monitor|Detect cuts, movement and persistent<br>residual drift|The active transform no longer<br>matches the video.|
|Publish|Store transform, validity interval,<br>diagnostics and review|The result lacks source/version<br>provenance.|



Report errors by pitch region and image scale, including the far touchline. A low average error can hide a bad corner of the field. Define the supported region explicitly; a result outside it should be unknown rather than extrapolated without warning. 

Use player ground-contact estimates for pitch projection. A box centre is not a foot position. A visible airborne ball is not on the ground plane; its homography projection must not be treated as a measured ground location. Mark aerial transit separately and use a suitable model only when the available views support it. 

For derived distances, propagate or conservatively bound coordinate uncertainty. Small coordinate noise becomes large apparent speed when differentiated. Report eligible intervals, smooth only within validated limits, and never bridge camera cuts or identity gaps to create physical totals. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

19 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

**Acceptance:** blinded landmark/position checks satisfy the existing protocol for the declared camera and region. Calibration corrections invalidate all dependent pitch coordinates and metrics, but do not force image-space detection to rerun. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

20 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **4.3 Player and ball perception** 

**Objective:** improve the observations that support the product, not merely increase the number of returned boxes. Start with a frozen baseline and stratified error analysis before selecting another detector. 

For players, evaluate recall and false positives by image height, near/far side, lighting, occlusion, camera region and kit similarity. Separate players, goalkeepers, officials and people outside the playing area where the label policy supports those distinctions. A full-frame resize can make far-side players too small; increasing the model size does not necessarily repair that information loss. 

Benchmark a coarse full-frame pass against overlapping high-resolution tiles. Preserve tile-tosource transforms and merge overlapping detections deterministically. Bound tile count, image size and batch size. Compare total decoding, inference and merge cost, not only the neural network's forward pass. Current code already exposes primary-context and auxiliary ball-recovery parameters; first measure these paths before adding competing recovery logic. <u>[R06]</u> 

### **Separate the ball problem** 

The ball needs its own visibility, localisation and temporal checks. Use an initial detector and a bounded region-of-interest recovery pass near plausible locations, then test whether recovery adds genuine recall without excessive false positives. Avoid using proximity to a player as proof that a ball was observed. 

|**Observation state**|**Stored meaning**|**Permitted downstream treatment**|
|---|---|---|
|Visible and detected|Image evidence supports a ball<br>candidate|Apply acceptance rules and<br>localisation uncertainty.|
|Temporally predicted|Motion model estimates a location|Keep inference provenance; limit<br>duration and confidence.|
|Player-conditioned|A player/possession model proposes a<br>location|Never count as independent visible-<br>ball detection.|
|Hidden or unsupported|No adequate position evidence|Preserve unknown; do not draw a<br>precise dot by default.|



Use temporal consistency to reject impossible jumps, but do not enforce an oversimplified motion model that removes legitimate kicks, bounces or aerial travel. Evaluate these regimes separately. A segmentation or visual-language model may help review a selected crop; it must earn that role on labelled examples. 

For development, annotate difficult positives and representative negatives: white boots, line markings, advertising, spectators and balls outside play. Keep a random sample of easy footage so the development set does not become only unusual failures. 

**Exit condition:** publish precision/recall, localisation error, accepted coverage and cost per video minute for each camera stratum. Promote a candidate only when it improves the 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

21 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

declared product objective without breaking quality gates. Detector confidence alone is not a calibrated probability of a correct football observation. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

22 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **4.4 Tracking, team assignment and player identity** 

**Objective:** maintain useful continuity without inventing certainty about who a player is. Distinguish a short tracklet, a match-level identity and a named roster player; they are different entities. 

First compare association methods on identical detections, timestamps and camera segments. Then compare complete pipelines. This separates detection improvements from tracking improvements and prevents an apparently stronger tracker from benefiting only from different inputs. Use established tracking evaluation tooling, with the coordinate and annotation conventions required by the protocol. [E03] 

Keep the current association baseline behind an adapter. A detector-independent library such as Roboflow Trackers can simplify controlled comparisons. McByte++ is a relevant challenger for mask- and appearance-assisted tracking, but its repository notes that the EdgeTAM path loads all frames at once. Test memory and chunk behaviour before considering full matches; a short-clip success is not sufficient. [E12, E13] 

### **Identity lifecycle** 

|**State**|**Example**|**Product consequence**|
|---|---|---|
|Local tracklet|A player remains visible for several<br>seconds|Interval-level positional evidence is<br>available.|
|Candidate rejoin|Appearance and motion suggest a<br>returning player|Preserve competing hypotheses or<br>request review.|
|Reviewed match identity|Tracklets are linked with adequate<br>evidence|Permit qualified player-level<br>aggregation.|
|Roster-linked identity|An analyst confirms the player label|Display the name only within the<br>authorised match context.|



Use appearance embeddings selectively, such as after occlusion or a potential rejoin, rather than on every detection. Blend them with timing, location and camera constraints. Similar kits, substitutions and camera cuts can defeat appearance matching; never force every tracklet into a known player. 

Team assignment should use track-level colour/appearance evidence and human confirmation, with explicit treatment of goalkeepers and officials. The status record shows why numeric cluster identifiers cannot be reused as stable semantic team labels across task outputs. Preserve task-local cluster mapping and the separate source declaration required for independent evaluation. [R02] 

Chunking must carry forward a bounded tracker state and record overlap/reconciliation decisions. Reset at genuine scene discontinuities; do not silently reconnect identities across a broadcast replay. Store corrections as joins/splits with their affected intervals and author. 

**Acceptance:** report identity switches, fragmentation and HOTA/IDF1 where valid ground truth exists, alongside analyst repair time and accepted player coverage. Team-level tactical analysis 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

23 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

may be released before player totals. Distance, sprint and individual involvement statistics remain unavailable when identity continuity is not adequate. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

24 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **4.5 Multi-rate processing: establish the real baseline** 

Objective: distinguish observation cost from export cadence before optimising. In the inspected loop, primary_model.track(...) runs before frame_count % frame_interval selects saved rows; the call does not explicitly set vid_stride. TARGET_FPS = 5 is therefore not itself an inferencerate limit. The integer interval may also produce a cadence other than exactly 5 Hz. [R10] 

Ultralytics documents vid_stride = 1 as processing every video frame. Confirm the effective configuration and actual model calls in your worker; do not assume a default or promise a fivefold saving. Changing stride also affects timing, calibration intervals and temporal association. [V01] 

### **Four rates, one source clock** 

|**Rate / counter**|**Contract**|
|---|---|
|Decode / presentation|Keep original PTS and time base; count frames actually emitted by the<br>decoder.|
|Detector execution|Declare selected source frames and batch contents; count primary and<br>recovery work separately.|
|Tracker update|Preserve ordered observations and elapsed time; predictions without<br>observations stay marked inferred.|
|Export / evaluation|Select the declared output grid; never infer detector cost from exported rows<br>or renumber source frames.|



For illustration, 90 minutes at 5 Hz gives 27,000 samples; 25 Hz gives 135,000. Those counts describe a declared sampling grid, not necessarily executed inference. At 5 Hz, samples are 200 ms apart, which limits touch-time evidence. Rates are task-specific candidates, not new defaults. 

Retain the frozen evaluation grid and source-global offsets. Compare temporal policies on development material first. Candidate refinement needs random-interval audits and hard negatives to detect events that the cheap pass misses; refinement accuracy cannot substitute for discovery recall. [R02] 

### **Promotion rule** 

Instrument effective settings, decode/inference/export counts, stage times, transfers, memory, queue waits, recovery and billed allocation. Establish the unchanged baseline first (GA-15), then alter one factor per comparison (4.5C). 

Do not add vid_stride alone: replace index-derived timing with the explicit frame contract, validate tracker timing and geometry schedules, and retain compatibility with old evidence. Reuse compatible observations and batch crops before testing precision/runtime changes. [R10, <u>E16]</u> 

Accept a faster policy only when source alignment, required football quality, coverage and recovery behaviour pass. Record both cost per processed match and cost per accepted reviewed match. No detector-only fps figure or language choice establishes that result. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

25 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **4.5A Native video stack: use libraries first** 

Decision: Python owns football semantics and orchestration. Existing native libraries own commodity media work. Benchmark one alternative behind an adapter at a time, rather than installing every decoder or rewriting the application. 

|**Component**|**Planned role**|**Selection condition**|
|---|---|---|
|FFmpeg / ffprobe|Media probe, proxy, thumbnails, clip/export<br>jobs. Prefer subprocesses when a command<br>already solves the task.[E20, V02]|Validated time mapping, safe<br>arguments, cancellation and an<br>approved build.|
|PyAV|Detailed packet/frame access and a CPU-<br>compatible decoding candidate.[V03]|Accurate frame contract and<br>acceptable complete-match<br>performance.|
|TorchCodec|Tensor-oriented frame access with PTS;<br>CPU/CUDA candidate for model input.[V04]|Compatible PyTorch/FFmpeg build;<br>benchmark sequential and seek-<br>heavy workloads.|
|PyNvVideoCodec|NVIDIA hardware decode/encode with GPU<br>tensor interchange.[V05]|Actual worker codec support and a<br>genuinely useful GPU-resident<br>path.|
|ONNX Runtime /<br>TensorRT|Detector-runtime challengers, separate from<br>the decoder decision.[E16, V07, V13]|Equivalent preprocessing plus task-<br>level quality, cost and memory<br>gates.|
|GStreamer; optional<br>Rust/C++|Consider complex live capture or a measured<br>custom native operation later.[V09-V11]|A declared missing capability or<br>measured bottleneck; see 4.5D.|



### **Default implementation order** 

Keep the current runtime as the reference. Harden FFmpeg jobs and frame identity; compare one decoding backend; then test GPU residency and detector export independently. Keep a CPU path for development and unsupported media. The decoder winner may differ by camera codec, resolution, access pattern and hardware. 

### **Source and playback are different assets** 

Never replace the original with a lossy proxy merely to reduce model cost. A 720p browser view can coexist with original-resolution ball crops. Store edit lists and render final clips on demand rather than re-encoding a full annotated match for every small correction. These are proposed product choices, not measured savings. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

26 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **4.5B Frame contract and GPU-resident processing** 

Target for a qualified NVIDIA worker: minimise avoidable full-frame transfers while preserving exact provenance. PyNvVideoCodec supports DLPack interchange, but this shares a buffer; it does not make resizing, batching or colour conversion allocation-free. [V05] 

```
Compressed source -> bounded decoder -> timestamped frame
```

- `-> selected GPU colour/resize/crop operations` 

- `-> compatible detector batch -> ordered tracker updates` 

- `-> compact observations -> Python evidence and analytics Playback proxy / final export: separate derived media jobs` 

### **Required adapter outputs** 

|**Contract**|**Required fields / invariant**|
|---|---|
|Identity and time|Source hash, stream, original PTS/time base, duration, presentation-order identity<br>and decode status; no index/fps shortcut for variable-rate input.|
|Image interpretation|Dimensions, rotation, pixel format, colour order/range and source-to-model<br>crop/resize transform. Keep metric coordinates separate.|
|Ownership and device|CPU/CUDA location, shape/strides/dtype, buffer lifetime, batch membership and<br>synchronisation rules; no use after buffer reuse.|
|Execution receipt|Requested and selected backend, versions/builds, effective rate policy, fallback<br>reason, counts, transfer volumes and timing scope.|



The existing torso-colour extractor explicitly assumes BGR. An RGB decoder without a compatibility conversion would change team-colour evidence. Add colour fixtures, rotation/crop tests and source-box round trips before changing the default. [R10] 

### **Capability, fallback and bounded memory** 

CUDA visibility is insufficient: NVIDIA exposes video capability separately. Test the actual codec/profile, driver libraries, frame access and tensor hand-off in the authorised worker; NVENC is a separate need for encoding, not a condition for decode-only analysis. No Daytona video-engine capability was verified here. [V06] 

Bound queues and batches; stream or checkpoint rather than retaining all decoded frames. Offline mode applies backpressure and reports missing source evidence; live mode may drop only under a declared policy. If hardware decode fails, use a budget-approved CPU fallback with a new receipt, or fail clearly. Do not silently change colour, timing or precision. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

27 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **4.5C Benchmark matrix and acceptance gates** 

Treat acceleration as a controlled experiment. Use declared development fixtures spanning supported codecs/resolutions, variable frame rate, camera cuts, far-side players and small-ball passages. Keep blind evaluation material isolated and preserve its protocol. A short clip is insufficient for memory and lifecycle acceptance. 

|**Experiment**|**Keep fixed**|**Evidence to retain**|
|---|---|---|
|B0. Existing reference|Pinned code/weights, effective settings<br>and input manifest.|Actual frame/call counts; end-to-end,<br>cold-start and cost receipt.|
|B1. Decode backend|Source moments, preprocessing,<br>models and output grid.|PTS/colour/coordinate parity; decode<br>time, transfers and fallbacks.|
|B2. GPU residency /<br>batches|Model, temporal policy and accepted<br>output semantics.|Memory high-water mark, queue waits,<br>synchronisation, cost and quality.|
|B3. Detector runtime /<br>precision|Decode and preprocessing; equivalent<br>model/postprocessing definitions.|Ball/player errors, accepted coverage,<br>latency and numerical failures.[V08]|
|B4. Temporal policy|Camera/model configuration;<br>evaluation grid.|Discovery recall, event timing,<br>identities, unknown time and saved<br>cost.|
|B5. Custom native<br>hotspot|Already-qualified pipeline and<br>external contracts.|Net match-level gain,<br>packaging/support burden and rollback<br>evidence.|



### **Timing that represents real work** 

Separate decode, preprocessing, transfer, inference, association, recovery, serialisation and allocation lifecycle. Time completed GPU work, not only asynchronous submission; use deviceaware timing where needed. Overlapped stage durations are not additive wall time. Keep warm/cold results and a declared repeat count. [V07] 

### **Pass / hold decision** 

Pass only after timing/frame identity, eligible-region accuracy, ball/player coverage, event/identity quality, resource ceilings, cancellation and recovery satisfy predeclared gates. A candidate that is faster but fails a quality gate stays experimental. Log the failure; do not reduce the threshold after viewing results. 

A simple planning example: accelerating a stage that consumes 10% of total runtime by 10x changes 100 time units to 91, only about 1.10x overall. Choose work by its measured share of the complete job, not a microbenchmark headline. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

28 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **4.5D Rust/C++ adoption and packaging gates** 

Neither language is a release prerequisite. First prove that an existing native library, batched operation or simpler algorithm does not solve the problem. GStreamer also has Python bindings, so live media does not automatically require Rust. [V09] 

|**Option**|**Suitable scope**|**Required boundary**|
|---|---|---|
|Rust worker|Later stream lifecycle, reconnection,<br>recording and bounded media queues.|Own a complete media job; return<br>manifests/artifacts, not raw frames as<br>JSON.|
|Rust extension|A measured CPU-bound operation best<br>expressed as a batched native function.|PyO3 batch/array interface; explicit<br>ownership, cancellation and error<br>mapping.[V10]|
|C++ extension|A native vision/SDK integration or<br>custom operation not covered by<br>existing APIs.|pybind11 or the SDK boundary;<br>versioned arrays/tensors, no football-<br>rule duplication.[V11]|
|No custom native<br>code|Existing runtime meets quality, cost and<br>workflow needs.|An acceptable outcome: keep Python<br>plus native dependencies and spend<br>effort on product accuracy.|



### **Proposed repository boundaries** 

```
backend/media/        probe, frame contract, decode adapters, exports
backend/vision/       preprocessing, detector runtime, tracker adapters
backend/evaluation/   benchmark fixtures and comparison receipts
native/               absent until GA-18 is explicitly approved
```

These are proposed extraction boundaries, not directories claimed to exist. Keep video_pipeline.py as the compatibility facade and preserve local/remote job contracts. Use coarse calls and bounded buffers; do not add an RPC fleet to move full-resolution frames between languages. 

### **Release checklist and economic decision** 

Pin native dependencies and build manifests; test supported macOS and Ubuntu profiles independently. Treat native wheels and accelerator engines as qualified artifacts, not universally portable files. Include CPU fallback, crash recovery, buffer-lifetime tests and an owner for maintenance. 

Retain codec/build notices and review the exact FFmpeg configuration: enabled components affect licensing. A Rust or C++ wrapper does not remove dependency obligations. Compare development, support and licence cost with measured per-match savings; record an explicit reason when a necessary capability, rather than savings, justifies the work. [V12] 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

29 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **4.6 Python metrics, calibrated xG and later xT** 

**Objective:** compute football statistics from accepted evidence with explicit definitions, denominators and uncertainty. A persuasive label must not upgrade a heuristic into a validated metric. 

The inspected shot function combines hand-selected distance, angle, box and close-range terms. Rename its user-facing output **experimental shot quality** while preserving versioned compatibility for existing `xg` fields. The inspected pressing function returns zero when its defensive-action denominator is zero; introduce availability/null semantics rather than presenting that case as measured PPDA. [R04] 

|**Metric family**|**Required evidence**|**Withhold or qualify when**|
|---|---|---|
|Team width/length|Correct axes, team mapping, calibration<br>and sufficient team visibility|Missing players can change the<br>measured span.|
|Formation/line height|Sustained eligible windows,<br>role/goalkeeper treatment and phase<br>context|A single frame or partial view cannot<br>support a stable formation.|
|Possession/events|Accepted ball/state evidence and clear<br>event definitions|Unknown intervals are excluded and<br>disclosed, not assigned arbitrarily.|
|Distance/speed/sprints|Continuous identity, timing, metric<br>coordinates and noise control|Gaps, cuts, outliers or assumed scale<br>invalidate physical totals.|
|PPDA and pressing|Defined pitch region, event taxonomy<br>and eligible denominator|Event omissions or denominator zero<br>make comparisons misleading.|



Define pitch x as the longitudinal axis and y as lateral within the new metric contract; transform legacy/display coordinates explicitly. Attacking direction belongs to a team and period, not a permanent team label. Distinguish actual zero, not applicable, unavailable and insufficient coverage. 

### **Train a small shot-probability model** 

Use correctly labelled shots and goals from legally usable data. Start with logistic regression using pre-outcome features such as location, angle and available shot context. Compare a treebased challenger only after the simple baseline is calibrated. Do not include information observable only after the shot outcome. 

Split by match/source and time where appropriate; do not put neighbouring shots or duplicate footage across training and test. Evaluate log loss, Brier score, reliability plots and uncertainty on the target domain, not only ranking accuracy. Record missing-feature behaviour and whether a model trained on professional events transfers to the intended footage. 

Introduce xT or VAEP later, after your event schema maps consistently into an action representation. Socceraction is a useful implementation reference, but importing its code does not validate your event extraction or training data rights. [E02] 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

30 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

**Acceptance:** each metric has a versioned specification, fixtures, eligibility checks and reproducible evidence. Reports use the correct label and never turn estimated physical outputs into medical or injury conclusions. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

31 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **4.7 Ownership states and event extraction** 

**Objective:** convert observations into reviewable football events without confusing proximity, possession and a completed action. Start with an explicit state machine and add a learned temporal component only when labelled errors justify it. 

Maintain controlled possession, loose ball, aerial transit, restart/out and unknown states, building on the existing match-state representation. Ownership is a hypothesis supported by ball visibility, player proximity in a valid coordinate system, relative motion, temporal persistence and plausible transitions. The nearest player alone is not sufficient evidence of control. [R03] 

Use configurable entry/exit hysteresis and minimum persistence to avoid alternating owners on noisy frames. Express thresholds in physical units only where calibration supports them; otherwise use a camera-specific model or withhold. Threshold values must be chosen on development data and versioned, not improvised for a held-out match. 

|**Candidate event**|**Proposed evidence pattern**|**Reasons to withhold or review**|
|---|---|---|
|Pass|Accepted release from one player<br>followed by accepted control by a<br>teammate|Missing release/receipt, identity gap,<br>prolonged unknown interval or<br>ambiguous deflection.|
|Turnover/recovery|Supported transition of control<br>between opposing teams|Dead ball, contested possession or an<br>unobserved interval that prevents<br>attribution.|
|Shot|Ball/action evidence consistent with an<br>attempt toward goal, plus contextual<br>support|A clearance or cross has a similar<br>trajectory; outcome is not<br>independently established.|
|Carry|Sustained control and meaningful<br>movement of a continuous identity|Apparent movement comes from<br>camera/calibration drift or unstable<br>ownership.|
|Press/regain sequence|Reviewed defensive pressure indicators<br>followed by a qualifying regain|Proximity alone does not establish<br>pressure or causation.|



Represent events as intervals with optional anchor times and a timing uncertainty, not just an exact frame chosen for display. Keep event candidates separate from accepted events. Use a consistent taxonomy for attempted versus completed passes, blocked shots, deflections and restarts before collecting labels. 

Derive team possession percentages from declared eligible time and state rules. Disclose unknown duration; do not normalise only the known fragments and present the result as fullmatch certainty. A possession transition may support a team-level event while player attribution remains unknown. 

For temporal learning, feed short clips or structured trajectories into a small classifier and compare against the state-machine baseline. Require hard negatives and detection-boundary evaluation. A model may improve candidate ranking without being accurate enough for automatic publication. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

32 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

**Acceptance:** the event scorer uses frozen matching tolerances and definitions; precision, recall and boundary errors are reported per class. A correction to ownership or identity invalidates dependent events and derived metrics, with no unnecessary detector rerun. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

33 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **4.8 Incident review, offside and 3D visualisation** 

**Objective:** help an analyst inspect an incident without presenting unsupported precision or an automatic official ruling. This is a later, separately qualified capability—not a shortcut around tracking and calibration. 

The current offside prompt asks whether a player is behind the last opponent. Replace that task with deterministic geometric review and explicit limitations. Under IFAB Law 11, position relates to both the ball and second-last opponent, using eligible body parts at the relevant teammate play/touch moment. Position alone is not an offence; involvement matters. The timing rule normally uses first contact, with a goalkeeper-throw exception, and direct receipt from a goal kick, throw-in or corner has an exception. The implementation must use the applicable law version and competition context. [R05, E09] 

### **Incremental capability ladder** 

|**Level**|**Output**|**Evidence boundary**|
|---|---|---|
|0. Manual incident|Synchronized source clips, notes and|Useful even without automatic|
|package|frame bookmarks|geometry.|
|1. 2D positional aid|Estimated pitch positions and<br>uncertainty bands|Ground-plane player points are not<br>eligible body-part boundaries.|
|2. Schematic 3D replay|A visual explanation built from<br>accepted estimates|Label as schematic, not a recovered<br>photorealistic scene.|
|3. Measured multi-view|Calibrated views, temporal|Requires a new dataset, calibration|
|reconstruction|synchronisation and 3D observations|protocol and validation programme.|



At level 1, allow the reviewer to choose a candidate touch interval, not just one allegedly exact frame. Show how the positional conclusion changes across timing and coordinate uncertainty. If the uncertainty interval crosses the decision boundary, the result should remain indeterminate. 

Do not project an elevated shoulder or head through a ground-plane homography and call it a precise offside line. Similarly, an invisible player or ball cannot be repaired simply by asking a larger model. Multi-view reconstruction requires sufficiently synchronised views and valid camera models; broadcast replays from different times are not automatically simultaneous evidence. 

For possible fouls, a temporal classifier can rank review candidates once suitably labelled clips exist. Contact, intent, severity and the applicable interpretation require contextual review. Do not treat a video-language model's confidence as referee ground truth. 

A renderer such as Blender can consume versioned scene coordinates and camera estimates later. Its output must retain source links, uncertainty and a reconstruction disclaimer. **Acceptance:** reviewers can identify the source evidence and limitations of every overlay; no unsupported “offside/no offside” or foul decision appears as a validated measurement. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

34 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **5.1 A task-specific model roster** 

**Objective:** buy accuracy only where it creates useful evidence or saves analyst effort. “Small AI” should mean appropriately sized specialist components, not a small chatbot attached to every function. 

|**Task**|**First implementation**|**Candidate upgrade and promotion**<br>**test**|
|---|---|---|
|Geometry, counts and<br>metric calculations|Versioned Python/NumPy functions|Optimise numerics only after<br>profiling; no LLM arithmetic.|
|Player/ball observations|Existing pinned detector profiles|Benchmark camera-specific fine-<br>tuning and an RF-DETR compact<br>variant.|
|Identity association|Existing tracker through a stable<br>adapter|Compare detector-independent<br>alternatives and McByte++ on<br>identical inputs.|
|Shot probability|Calibrated logistic-regression baseline|A small boosted-tree model if held-out<br>calibration/utility improve.|
|Temporal event<br>suggestions|Rules on accepted states|Frozen video features plus a small<br>trained classifier, then fine-tuning if<br>justified.|
|Search and notes|Structured filters, keywords and<br>templates|A compact language model for<br>validated query translation and<br>drafting.|
|Complex tactical<br>comparison|Analyst-led evidence review|A configured stronger model on<br>selected, permitted evidence packages.|



RF-DETR supplies compact model variants and is a candidate worth evaluating; its public object-detection benchmarks are not football validation. The current YOLO-family integration should remain the baseline until a challenger clears your camera-specific tests and licence review. [R06, E11] 

MViTv2 and VideoMAE-v2 are reference options for pretrained video representations, not a claim to current football state of the art. A small temporal head trained on your event taxonomy can be a lower-risk first experiment than fine-tuning a large video model. Include hard negatives and temporal boundary labels rather than training only on highlight clips. [E14, <u>E15]</u> 

For local language assistance, Qwen3.5-4B is a concrete compact multimodal candidate from an official model card. Benchmark it against the current local configuration and deterministic templates. Its existence and model size do not establish football expertise, hardware fit, or acceptable latency. [R05, E10] 

“Frontier” is a provider role, not a permanently hard-coded model name. Keep model ID, snapshot/version where available, prompt, schema, price schedule and capabilities in 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

35 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

configuration. A current API model may be inexpensive enough for occasional reports that a dedicated local server is unnecessary. 

**Promotion gate:** exact artefacts and licences recorded; target-task accuracy measured; unacceptable errors analysed; latency, memory and total cost measured; fallback verified. Test on the actual Mac/CPU or GPU environment before promising local performance. Quantised weight size is not the complete runtime-memory requirement. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

36 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **5.2 Routing policy, permissions and spending controls** 

**Objective:** make every model call explainable, bounded and optional. The router should optimise a task outcome under constraints, not automatically send every difficult result to the largest model. 

The decision sequence is: identify the task; validate the evidence; check data permissions and deployment policy; choose a qualified method; reserve budget; execute with limits; validate the output; record outcome and spend. A disallowed upload or missing observation terminates the cloud route even when money is available. 

|**Situation**|**Preferred next action**|**Action to avoid**|
|---|---|---|
|A numeric metric is<br>requested|Compute from accepted data in Python|Asking a chatbot to derive the number<br>from prose.|
|A far-side player is<br>missing|Reprocess an eligible crop or request<br>review|Treating a tactical model's guess as a<br>detection.|
|Query wording is<br>ambiguous|Offer the interpreted typed filter for<br>confirmation|Execute arbitrary generated SQL or<br>code.|
|Evidence is sufficient but<br>interpretation is complex|Use the lowest-cost qualified assistant;<br>escalate only if useful|Repeated whole-match uploads until a<br>plausible answer appears.|
|Budget or provider is<br>unavailable|Return saved evidence and a<br>deterministic report|Concealing partial processing or<br>endlessly retrying.|



### **Proposed policy contract** 

Store task type, permitted inputs, local/cloud permission, maximum calls, per-call input/output limits, timeout, allowed model IDs, retry allowance and maximum reserved spend. Keep separate budgets for vision refinement and language assistance. One failed JSON repair should not open an unbounded chain of requests. 

For an initial report task, a possible policy is one primary call plus at most one repair attempt, a fixed evidence-package size and a configured spend cap. These are defaults to validate, not provider guarantees. Reserve conservative cost including potentially billed reasoning output, then reconcile against returned usage and the invoice ledger. Cancellation does not necessarily erase charges already incurred. 

Escalation should be triggered by a measured task-quality gap, not by the model declaring itself uncertain or confident. A local model that fails schema or evidence validation may fall back to a template; a stronger model should be tried only when the task remains suitable and permission/budget still permit it. 

Log the route, policy version, evidence hash, model configuration, timings, usage, validation failures and final disposition. Exclude secrets and unnecessary raw footage from logs. Cache only within the authorised data scope and invalidate when evidence or permissions change. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

37 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

**Acceptance:** disabling all providers leaves review, metrics and template reports operational. Tests prove that caps survive concurrent requests, retries, cancellation, malformed responses and provider timeouts. No request may silently change a factual measurement. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

38 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **5.3 Grounded search, reports and training suggestions** 

**Objective:** make natural language a convenient interface to evidence, not an alternative source of match facts. Search execution and report numbers stay deterministic. 

A query such as “show our second-half turnovers followed by a shot within ten seconds” becomes a typed expression: team, period, event family, successor event and maximum gap. Validate the expression against an allowlist, show the interpretation when ambiguous, and execute a parameterised query or Python function. Return source-linked intervals with the underlying accepted events. 

Begin with structured filtering and keyword retrieval. Add embeddings only when a tested collection of analyst questions shows a material recall benefit. Embeddings retrieve candidates; they do not prove that a passage contains a press, foul or tactical weakness. Use selected event labels, notes and evidence summaries rather than repeatedly embedding every video frame. 

### **Report assembly** 

|**Stage**|**Responsibility**|**Validation**|
|---|---|---|
|Evidence selection|Python retrieves relevant<br>reviewed/eligible passages|No missing references; include<br>exclusions and coverage.|
|Fact package|Python serialises metrics, definitions<br>and events|Units, denominators and values match<br>the artifact version.|
|Narrative draft|Optional model explains or compares<br>the package|Separate observations from<br>hypotheses; require evidence IDs.|
|Factual check|Deterministic checks plus analyst<br>review|Reject invented numbers, players,<br>clips and unsupported certainty.|
|Publication|Analyst accepts a versioned report|Record author/reviewer, evidence<br>version and export time.|



The inspected provider schema validates structure, while the context builder uses a small sampled-frame set and truncated event lists. Replace ad hoc truncation with a task-specific, coverage-aware evidence selector; do not assume a few sampled frames represent a whole match. [R05] 

A useful claim is: “In three reviewed sequences, the near-side defender advanced before the supporting midfielder covered.” Its evidence links should open those sequences. A stronger claim about frequency across the match needs a defined search/evaluation denominator, not just examples selected by the assistant. 

Training suggestions should combine accepted observations with a curated, coach-reviewed drill library. The model may adapt language and propose options, but should not prescribe medical load, diagnose fatigue or infer injury from noisy tracking. 

**Evaluation plan:** create a held-out collection of realistic questions and report tasks, with known matches, expected filters, relevant intervals and deliberately unanswerable requests. Score retrieval usefulness, schema validity, factual contradictions, unsupported claims, 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

39 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

latency, cost and analyst edit time. A polished report with fabricated evidence fails regardless of writing quality. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

40 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **5.4 Training, active learning and model improvement** 

**Objective:** turn real errors into reusable improvements without contaminating independent evaluation or consuming credits on unfocused training. 

Maintain four distinct data pools: operational corrections; training examples; development/validation examples; and locked independent evaluation. A correction becomes a training example only after provenance, rights and quality checks. Locked test labels never become convenient fine-tuning material. Repeatedly choosing models against a supposedly held-out test gradually turns it into development data. 

### **Experiment cycle** 

|**Stage**|**Required artifact**|**Stop condition**|
|---|---|---|
|Diagnose|Error taxonomy and representative<br>development examples|No specific measurable failure is<br>identified.|
|Select data|Source-level split manifest, rights and<br>label policy|Duplicate/leaking footage or unclear<br>permission.|
|Establish baseline|Fixed model/config and comparable<br>scoring|Baseline cannot be reproduced.|
|Train a bounded<br>candidate|Run budget, seeds, checkpoints and<br>config|Cost cap, repeated failure, or no<br>development benefit.|
|Validate|Per-stratum quality/cost and failure<br>examples|A key safety/coverage gate regresses.|
|Promote|Reviewed evidence dossier and<br>rollback artifact|Independent acceptance or<br>deployment review is missing.|



Sample difficult cases, but also retain random and representative intervals. Uncertainty-only sampling can overrepresent one camera or one type of mistake. Track the sampling policy so later performance claims reflect how the data were selected. 

For event classification, start with frozen pretrained features and a lightweight head. For detection, compare targeted camera-domain fine-tuning against a stronger generic baseline. Record augmentation choices; transformations that alter temporal order, pitch orientation or small-ball visibility can invalidate labels or erase the task signal. 

A larger model may propose labels on training material, but those remain pseudo-labels until the chosen quality process approves them. Do not call teacher-generated labels independent ground truth. Retain the original suggestion, any human changes and the final training decision. 

Use an append-only experiment ledger and immutable checkpoints. The repository's isolated research lane already models frozen inputs and guarded execution; expand it only through an explicit reviewed change, preserving default prohibitions on remote execution and production mutation. [R07] 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

41 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

**Acceptance:** a promoted model improves the predefined task on the correct evaluation split, maintains required quality on difficult strata, fits the deployment budget and can be rolled back by changing a manifest. Do not train a general football language model merely because GPU credits exist; train the smallest component tied to a demonstrated error. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

42 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **6.1 The evidence and availability contract** 

**Objective:** one shared contract should support analytics, review, search, AI and exports. Extend the existing schemas rather than creating separate meanings for the same match in each subsystem. [R03] 

|**Contract group**|**Essential fields and meaning**|
|---|---|
|Identity|Match ID, source asset hash, camera/period, run ID and schema version.|
|Time|Source frame/PTS, time base, clip offset, sample identity and match-clock<br>mapping.|
|Geometry|Coordinate system, units, calibration version, valid region and<br>uncertainty.|
|Observation|Object/track ID, bounding box or position, observation method and raw<br>score.|
|Review|Review state, reviewer/action IDs, timestamp and superseded version.|
|Derivation|Parent evidence IDs; algorithm/model/config hashes; decoder/preprocess<br>version, precision, rate policy and effective backend.|
|Availability|Eligible interval, denominator, missingness reason and publication<br>status.|
|Rights|Processing scope, cloud permission, retention class and access policy<br>reference.|



Observation source and review status remain orthogonal. “Reviewed” means a review action occurred; it does not convert an estimated location into a directly observed one. Likewise, a detector's score, a model's calibrated probability and a metric's confidence interval are distinct quantities and must not share an unexplained `confidence` label. 

### **Illustrative metric object** 

```
{
  "metric": "team_width_m",
  "definition_version": "1",
  "value": null,
  "availability": "insufficient_coverage",
  "eligible_seconds": 0,
  "requested_seconds": 30,
  "evidence_ids": ["interval-42"],
  "reason_codes": ["TEAM_VISIBILITY_TOO_LOW"],
  "review_status": "unreviewed"
}
```

This is a proposed contract illustration, not an existing API response. Model it with strict types, finite numeric checks, bounded arrays and enums. Use interval references instead of repeating tens of thousands of frame IDs in every response. Define whether interval endpoints are inclusive or half-open and test that rule consistently. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

43 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

Introduce canonical reason codes such as calibration unavailable, insufficient team visibility, identity discontinuity, unknown ball state and permission denied. Keep the machine code stable while improving the human explanation independently. 

**Acceptance:** a stored report claim can be traced through derived metrics and accepted events to source observations and original video. A correction creates a new version, identifies affected dependants and leaves the previous evidence inspectable. A missing metric remains missing through serialization, UI display, search, provider context and export. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

44 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **6.2 Storage, caching and invalidation** 

Objective: make expensive evidence reusable without accidentally treating incompatible artifacts as equivalent. Store immutable source and run artifacts with transactional metadata. Include source interval, frame policy, decoder/preprocessing version, crop/colour transform, model/runtime/precision and postprocessing settings in cache identity; qualify any declared equivalence between backends. 

Keep SQLite for local transactional metadata and corrections. Use typed, chunked columnar artifacts for larger observation tables when measurements justify that migration. Keep original media and large derived assets in content-addressed local storage, with an object-storage adapter for an explicitly approved hosted deployment. DuckDB can be evaluated for analytical queries over Parquet later; it need not become a second mandatory service. 

### **Dependency-aware invalidation** 

|**Change**|**Reuse safely**|**Rebuild or mark stale**|
|---|---|---|
|Report wording or<br>template|Observations, accepted events and<br>metrics|Narrative/export only.|
|Team mapping|Image detections and raw tracklets|Team state, team events, metrics and<br>dependent reports.|
|Track split/join|Unaffected detections and intervals|Affected ownership, player<br>events/totals and reports.|
|Calibration|Image-space observations and source<br>media|Pitch positions and dependent<br>physical/tactical metrics.|
|Source, frame policy or<br>perception runtime|Unchanged originals; qualified<br>equivalent outputs only|Changed observations and<br>dependants; never reuse solely<br>because the model filename matches.|
|Permission/retention<br>change|Only artifacts still permitted|Access, caches, exports and deletion<br>obligations as applicable.|



A cache key should include source bytes or validated identity, frame schedule, transformation/calibration, exact model assets, relevant configuration and algorithm/schema versions. Do not hash only the file name. Separate the developer cache from production and held-out evaluation artifacts; cross-tenant cache reuse needs an explicit privacy design. 

Persist files through staging and atomic publication, then commit the metadata reference. Treat uncertain write outcomes explicitly and reconcile them rather than retrying destructive operations blindly. Backups need both database consistency and the artifact versions to which it points. Test restore on a disposable destination; do not count an untested archive as recovery evidence. 

Hash manifests establish identity/integrity relative to a retained record, not truth or reviewer independence. Protect acceptance receipts against accidental changes, retain access controls and reproduce scoring from original predictions and locked labels. A locally editable result JSON alone is not proof of accuracy. [R02] 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

45 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

**Acceptance:** changing only report text performs no vision inference; correcting a team invalidates the right descendants; interrupted publication leaves no accepted partial artifact; old schema readers remain supported during migration. Retention cleanup must not delete frozen evaluation or user-owned original media merely to free space without an authorised policy. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

46 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **6.3 API boundaries and repository migration** 

**Objective:** expose small, stable commands and queries while retaining the existing application. The endpoints below are proposed contracts, not a claim that these exact routes already exist. 

|**Proposed surface**|**Behaviour and safeguards**|
|---|---|
|`POST /matches`and media admission|Create metadata; validate upload identity, size and rights<br>separately from processing.|
|`POST /matches/{id}/jobs`|Reserve budget and create an idempotent, scoped job; return<br>an accepted job reference.|
|`GET /jobs/{id}`and cancellation|Expose durable phase, progress, spend and cleanup status;<br>cancellation is a request, not proof of termination.|
|`GET /matches/{id}/evidence`|Cursor/interval queries with bounded payloads and<br>coordinate/version metadata.|
|`POST /matches/{id}/corrections`|Append a typed edit using expected version; reject<br>stale/conflicting updates.|
|`POST /matches/{id}/queries`|Validate an allowlisted query plan and return evidence-<br>linked results.|
|`POST /matches/{id}/reports`|Build from a fixed evidence version; optional AI is governed<br>by explicit policy.|



### **Incremental code boundaries** 

Extend schemas.py with evidence/version fields; preserve legacy readers. Keep video_pipeline.py as the facade while extracting media/frame-source, preprocessing, detector, calibration and tracker adapters. Put profiling and correctness tests around boundaries before changing the default. Proposed paths and optional native gates are in 4.5D; Python football logic remains shared. 

Split provider configuration and execution out of `llm.py` into `ai_policy.py` and provider adapters. Add an evidence selector and output-grounding validator between analytics and providers. Extend `storage.py` through a repository/artifact interface rather than replacing all persistence at once. Maintain generated or tested frontend types compatible with backend schemas. [R03-R06, R08, R09] 

Use feature flags to shadow new metrics or models on development material before changing defaults. Write new-version artifacts alongside retained old ones; do not silently mutate historical match reports. Migration tests must cover legacy records, absent fields, null values and rollback readers. 

Keep local and remote workers on the same sealed input/output contract. A remote-specific shortcut must not change numerical semantics. Reject unrecognised worker outputs, path traversal and oversized archives before import; distinguish a job execution success from a product-quality pass. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

47 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

**Acceptance:** contract tests exercise valid, invalid, duplicate and concurrent requests; UI tests verify pending/stale/unavailable states; integration tests prove end-to-end provenance and selective reprocessing. Public or LAN access remains blocked until the separate network/security workstream is accepted. Do not add a distributed broker solely to rename the current queue. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

48 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **7.1 Cost equations and pricing assumptions** 

**Objective:** optimise total cost per useful reviewed match. A GPU price, token price or detector fps is only one component. 

```
Match cost = allocated compute + retained storage + transfer
           + model/API usage + retry overhead + review labour
           + an allocated share of fixed operations and licences
```

For compute, use allocated seconds multiplied by the applicable GPU, CPU, memory and storage rates. Separate staging, startup, execution, idle and cleanup intervals. Daytona's billing documentation describes resource-based charging; do not equate measured model execution time with the complete billable lifecycle. [E07] 

The original status record reports two-half end-to-end times totalling 16,523.971 seconds (about 4.59 hours) on earlier source. They are not verified current billable duration. A five-Hz export setting does not establish a five-Hz inference cost model; refresh the baseline through GA-15 before projecting savings. [R02, R10] 

|**Allocated worker time**|**Assumed $1/hour total**|**Assumed $2/hour total**|**Assumed $4/hour total**|
|---|---|---|---|
|30 minutes|$0.50|$1.00|$2.00|
|1 hour|$1.00|$2.00|$4.00|
|4.59 hours|$4.59|$9.18|$18.36|



These are **all-in worker-rate scenarios** , not Daytona quotations. Retrieved public pricing representations exposed both preemptible/on-demand choices and different displayed GPU rates without a reliably selected mode. Confirm the exact allocation class, region, resource bundle and rate in the account/provider contract before approving a budget. Do not treat the cheapest displayed GPU component as the full worker price. [E08] 

### **Example language-model arithmetic** 

Google's published Gemini 3.8 Flash standard rates are $0.75 per million input tokens and $3.75 per million output tokens, including thinking, through 31 December 2026. The listed rates become $1.50/$7.50 on 1 January 2027. A task using 10,000 input and 2,000 total billed output tokens therefore costs $0.015 at the introductory rate or $0.030 at the listed 2027 rate, before tools, caching, retries and other charges. [E17] 

This does not establish football quality or a fixed cost for video analysis. Video tokenisation and reasoning volume can change the bill. A selected evidence report can be cheap while continuous full-match visual prompting is wasteful. 

**Budget control:** store the rate-card date and currency with every estimate; reserve a conservative maximum; reconcile usage; alert on variance. Exclude taxes, foreign-exchange differences and licence fees only when they are explicitly listed as exclusions—not hidden assumptions. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

49 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **7.2 Usage-scale scenarios and storage economics** 

The following is a transparent **planning model** , not measured application performance or a supplier quote. Assume one allocated worker hour at $2, a $0.10 language-assistance allowance, 12 GB of retained assets per match for 30 days at an assumed $0.02/GB-month, and 30 minutes of analyst review valued at $20/hour. Fixed operations are assumed at $50/month. 

That gives $2.34 variable technical cost per match and $10 review labour. The 30-minute review assumption is a productivity target for illustration; present tracking quality may require substantially more effort. 

|**Matches per month**|**Variable technical cost**|**Review labour**|**Total including $50**<br>**fixed**|
|---|---|---|---|
|10|$23.40|$100|$173.40|
|100|$234.00|$1,000|$1,284.00|
|1,000|$2,340.00|$10,000|$12,390.00|



The totals exclude development, independent labelling, transfer/egress, backups beyond the assumed 12 GB, taxes, payment processing, commercial licences and support beyond the fixed allowance. This is not a SaaS pricing recommendation. At scale, replace every assumption with observed distributions and the actual service contract. 

### **Retention and bandwidth** 

A 90-minute video at an assumed 8 Mb/s is approximately 5.4 GB in decimal units; at 16 Mb/s it is 10.8 GB. Proxies, alternate views, thumbnails, exports and backups add to that. Do not confuse GB with GiB when mapping these estimates onto a provider bill. 

Thirty-day retention at steady intake limits the active collection approximately to one month's volume. Keeping every match for a season accumulates storage; ten months of identical intake would retain roughly ten times the originals before deletion, excluding growth from derivatives. Provide explicit retention classes and avoid exporting another full video copy when an authorised source-linked playlist is sufficient. 

### **Local versus cloud** 

Local inference is attractive with existing suitable hardware, privacy constraints or sustained utilisation. Cloud bursts are attractive when usage is irregular and idle hardware would dominate. Compare hardware amortisation, electricity, maintenance and operator time against the complete cloud rate—not just electricity against GPU rental. 

A dedicated local language-model server may cost more than occasional API reports. Conversely, moving a large protected video to the cloud for a tiny query can cost more in transfer, governance and delay than local processing. **Decision rule:** select deployment by measured workload, privacy and utilisation; reassess after the pilot rather than committing to always-on GPU infrastructure now. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

50 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **7.3 Credit allocation and optimisation programme** 

Treat compute credits as an experiment budget, not free capacity that should be exhausted. The table uses an **illustrative $1,200 credit envelope** ; it is not a verified account balance, current entitlement or authorisation to run jobs. GPU credits do not automatically pay for independent annotators, external model APIs, licences or cash-only services. 

|**Allocation**|**Illustrative amount**|**Release condition**|
|---|---|---|
|Baseline and video<br>profiling|$180|GA-15/16 development tests only after<br>input, source and spend approval; no<br>new authorisation implied.|
|Player/ball detector<br>experiments|$420|Specific development errors and<br>legally usable labels.|
|Tracking/calibration<br>challengers|$240|Fixed comparison inputs and valid<br>evaluation conventions.|
|Runtime integration and<br>capacity checks|$120|GA-17 only after baseline/local gates<br>and hardware capability checks; leave<br>native-code work uncommitted.|
|Reserve for failures and<br>high-value follow-up|$240|Explicit approval; no automatic<br>spending of the remainder.|



Do not book all experiments at once. Use small development pilots to estimate training time, output quality and actual billing, then release the next allocation. Reconcile reserved versus consumed credits and record any expiry or eligibility restrictions from the account before relying on them. 

### **Labelling is a separate bottleneck** 

The repository reports 18 frozen tasks and 9,297 sampled frames with independent labels incomplete. As a workload illustration—not a quote—2 to 6 annotator hours per task would be 36 to 108 hours, or 45 to 135 hours with 25% review overhead. Actual effort depends on the label specification, object density, visibility and tools. Time a representative non-held-out training task before budgeting; do not reduce the frozen label requirements to fit an arbitrary estimate. [R02] 

### **Order of optimisation** 

First establish effective inference/export counts and correct clocks (GA-15). Next reuse compatible results, remove repeated media/model work, benchmark a decoder adapter (GA-16), then evaluate GPU residency and detector runtimes separately (GA-17). Custom Rust/C++ is the final optional step (GA-18), not the first optimisation. 

Preemptible capacity is a candidate only when checkpoints, input access, restart semantics and current project policy permit it. A lower hourly rate can be more expensive after repeated restarts. No optimisation may silently increase runtime/TTL limits, weaken truth gates or invoke a retired infrastructure smoke. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

51 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

**Cost acceptance:** every production job has a bounded estimate, stage timings, usage receipt and cleanup outcome. Track p50/p95 cost and review time, not only averages. Pause an experiment when its remaining budget cannot cover a safe termination and artifact recovery. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

52 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **8.1 Independent evaluation and product evidence** 

**Objective:** establish what works on which footage, without confusing software checks, validation diagnostics and independent accuracy. The frozen repository protocol remains authoritative; new targets must not quietly replace it. [R02] 

The current record describes 18 frozen 100-second tasks and 9,297 sampled frames, with independent labelling incomplete. Preserve source/team declarations made before prediction access, the permitted frame grid, clip/parent hashes and locked-label publication process. Annotation-service health or successful media loading does not satisfy the label gate. [R02] 

### **Evaluation measures** 

|**Layer**|**Score and denominator**|**Essential companion evidence**|
|---|---|---|
|Players/tracking|Detection precision/recall; HOTA and<br>IDF1 where compatible labels exist|Visibility strata, identity switches,<br>fragmentation and accepted coverage.|
|Ball|Visible-ball precision/recall and<br>localisation error|False positions when hidden; observed<br>versus inferred counts.|
|Calibration|Position/landmark error on eligible<br>independent points|Region-wise errors, units, camera<br>profile and excluded areas.|
|Ownership|Agreement over protocol-eligible<br>states/intervals|Unknown duration, contested/restart<br>handling and team-mapping<br>provenance.|
|Events|Precision/recall/AP under declared<br>matching/timing rules|Missed events, false events, class<br>support and temporal boundary<br>errors.|
|Product|Task completion, useful passages and<br>correction time|Intended-analyst review, limitations<br>understood and export usefulness.|



Use image-space tracking labels for image-space tracking metrics. Official pitch positions or incompatible sampling cannot be substituted into HOTA/IDF1 without a validated common representation. Retain the native predictions and re-run the scorer; do not accept a handedited summary file as the result. TrackEval supplies reference evaluation implementations, not missing ground truth. [R02, E03] 

Report results by camera/source and difficult strata, not only a pooled average. Adjacent frames are correlated; uncertainty estimation should respect source/match grouping where possible. With few independent sources, confidence intervals may be wide and generalisation claims must remain narrow. A low-coverage system can be precise on accepted frames while being unhelpful across a whole match. 

### **Human process and test isolation** 

Use an independent reviewer who has not inspected held-out predictions, following the existing attestation/declaration workflow. Resolve label ambiguity through a defined adjudication process and retain changes. Do not use evaluation access to choose camera- 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

53 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

specific thresholds repeatedly without acknowledging that the split has become development material. 

**Acceptance:** complete labels and declarations; reproduce exact-source predictions under an authorised plan; run the unchanged eligible scorer; document all failures; obtain analyst acceptance for the declared capability. Release manual review independently where appropriate, but keep unqualified automatic metrics marked experimental or unavailable. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

54 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **8.2 Delivery milestones, ownership and effort** 

Plan by evidence gates rather than a fixed launch date. The effort ranges below are **planning estimates** , not repository measurements or delivery commitments. They assume familiarity with the existing code, a backend/CV engineer, frontend engineering capacity and access to an independent analyst/reviewer. Labelling, footage rights and model iteration can dominate the critical path. 

|**Milestone**|**Main deliverable**|**Indicative**<br>**engineering**<br>**effort**|**Exit gate**|
|---|---|---|---|
|M0. Baseline and<br>scope|Scope/source dossier,<br>rights/evaluation plan and<br>sampling audit|1-2 person-<br>weeks|Scope, authorised actions<br>and baseline counters are<br>explicit.|
|M1. Useful manual<br>workbench|Evidence contract, setup,<br>correction, playlist and template<br>export|4-7 person-<br>weeks|Analyst completes a<br>reviewed match without<br>LLM dependence.|
|M2. Qualified<br>perception|Qualified camera/perception plus<br>selected runtime benchmarks|6-12 person-<br>weeks|Accuracy/coverage, timing,<br>fallback and cost gates pass;<br>GA-17 may remain deferred.|
|M3. Reliable derived<br>analytics|Ownership/events, availability,<br>metric definitions and shot model|4-8 person-<br>weeks|Metrics reproduce and<br>remain honest under<br>missing data.|
|M4. Optional AI<br>assistance|Typed query translation, grounded<br>drafts and spending policy|3-5 person-<br>weeks|Lower analyst effort without<br>unacceptable factual errors.|
|M5. Deployment<br>hardening|Network/authentication, access<br>control, recovery and operations|3-6 person-<br>weeks|Required security and<br>operational acceptance<br>completed.|



The ranges sum to approximately 21-40 engineering person-weeks before independently budgeted labelling, legal review and advanced 3D/live work. They are not calendar weeks; parallel work and specialist availability change elapsed time. Re-estimate after M0 and a measured labelling pilot instead of treating the range as a quote. 

### **Dependency and ownership model** 

Assign named owners for backend/media, frontend, CV, independent evaluation and operations. A small team may combine roles, but preserve blind-label independence and explicit reviews. GA-15/16 start with M0/M1; GA-17 runs only after the baseline; GA-18 is separately approved and estimated. Re-estimate affected milestone ranges after GA-15 rather than assuming native integration is free. 

M1 can deliver value while M2 is still being developed. M4 can use reviewed manual events, but must not make unqualified perception look accepted. Hosted M5 can be deferred for a loopback-only pilot; required data-rights and upload-safety work cannot. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

55 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

**Next proposed work package:** establish the baseline dossier, select the declared initial workflow, complete the independent annotation/declaration plan and implement the availability contract plus review-critical UI. No new model training or GPU deployment is needed merely to start those tasks. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

56 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **8.3 Implementation backlog: foundation and perception** 

The backlog below is designed to become repository issues after review. IDs are proposed planning identifiers, not existing tickets. Each change should include tests, a source-bound receipt and a rollback path. 

|**ID / owner**|**Work and dependencies**|**Definition of done**|
|---|---|---|
|GA-01 / lead +<br>analyst|Capture baseline, scope, camera and<br>capability matrix. No new inference<br>required.|Dossier names exact assets, historical<br>results, missing gates and permitted next<br>actions.|
|GA-02 / backend|Source-clock/media identity contract with<br>GA-15/16. Depends on GA-01.|Frame/PTS/proxy/colour/export tests<br>pass; source alignment and fallback<br>remain explicit.|
|GA-03 / backend|Add evidence versioning, availability and<br>reason codes. Depends on GA-01.|Unknown survives storage, API, UI and<br>report round trips; legacy readers<br>remain supported.|
|GA-04 / frontend +<br>backend|Build setup/review corrections and<br>playlist workflow. Depends on GA-02/03.|Analyst edits are undoable, attributable<br>and saved; export opens the correct<br>source interval.|
|GA-05 / CV + analyst|Add calibrated camera profile and<br>independent geometry checks. Depends<br>on GA-02/03.|Eligible-region errors and drift tests<br>satisfy the declared protocol; invalid<br>metrics are withheld.|
|GA-06 / CV|Benchmark player coverage and tiling<br>against fixed baseline. Depends on GA-02<br>and lawful development labels.|Per-stratum precision/recall, latency,<br>memory and failure examples are<br>retained.|
|GA-07 / CV|Benchmark ball detection and bounded<br>recovery. Depends on GA-02/03 and ball<br>labels.|Visible/inferred/unknown are separated;<br>recovery benefit and false positives are<br>measured.|



### **Test design and rollout** 

For GA-02, include variable-rate video, an off-grid clip start and a source with a camera cut. For GA-03, seed a legacy record with zero defaults and verify that migration does not turn missing evidence into a measured zero. For GA-04, simulate a crash after a correction is submitted and show a recoverable saved/pending state. 

For GA-05, test near/far pitch regions, a deliberately wrong landmark and a zoom/cut. For GA-06/07, score representative negatives and observations near the detection-size limit. Compare fixed configurations; do not tune against held-out examples discovered during scoring. 

Release new schemas through additive readers, then new writers, then a reviewed migration of old data if necessary. Use feature flags for experimental UI and models. Retain the previous pinned configuration so an unsuccessful candidate can be disabled without deleting evidence. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

57 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

**Progress signal:** count completed analyst tasks and validated capability gates, not just merged files. A backlog item is not finished because a model loads or a synthetic fixture passes; its stated evidence requirement must also be met. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

58 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **8.4 Implementation backlog: analytics and release** 

|**ID / owner**|**Work and dependencies**|**Definition of done**|
|---|---|---|
|GA-08 / CV +<br>frontend|Tracker/team adapters and reviewed<br>identity repair. Depends on GA-04/06 and<br>camera segmentation.|Comparable detection inputs; identity<br>errors/cost scored; cluster mappings and<br>edits are explicit.|
|GA-09 / backend +<br>analyst|Metric dictionary, availability,<br>ownership/events and shot-model plan.<br>Depends on GA-03/05/07/08 as required<br>per metric.|Deterministic fixtures, valid<br>denominators and independent<br>event/metric evidence; heuristic<br>renamed.|
|GA-10 / backend +<br>frontend|Typed tactical search and evidence-linked<br>results. Depends on GA-03/04/09.|Known and unanswerable queries<br>evaluated; no arbitrary SQL/code<br>execution.|
|GA-11 / backend|Provider adapters, policy router and<br>grounded reports. Depends on GA-03/10.|Budget/permission tests, fabricated-<br>evidence rejection and no-provider<br>fallback pass.|
|GA-12 / backend +<br>operations|Durable jobs, cost ledger, selective<br>recomputation and cleanup<br>reconciliation. Depends on GA-02/03.|Duplicate/cancel/timeout/outcome-<br>unknown cases pass; receipts include<br>effective backend, temporal policy,<br>counts and safe fallback.|
|GA-13 / independent<br>reviewer + CV|Frozen labels, declarations and<br>reproducible accuracy evaluation. Runs<br>alongside development.|All protocol prerequisites and retained<br>native artifacts exist; results are<br>replayable.|
|GA-14 / security +<br>lead|Deployment/rights review and source-<br>bound release dossier. Depends on the<br>capabilities being released.|Loopback or hosted boundary is explicit;<br>access, restore, incident and licence<br>gates satisfied.|



### **Cross-cutting completion rules** 

Every completed work package includes tests, source/versioned evidence, an owner and a rollback path. GA-01 through GA-14 remain in scope; section 8.5 adds GA-15 through GA-18 without renumbering them. No work package can silently change the frozen evaluation protocol or convert a historical success into current-source acceptance. 

Maintain short architecture decisions for camera support, coordinate conventions, persistence, detector licensing, AI routing, cloud region and capability release. Each decision records alternatives, evidence, owner, reversibility and a trigger for reconsideration. 

For a release, retain the exact source and dependency/model manifests, verification receipts, migrations, independent results, cost measurements and limitations. Repeat only the currently approved acceptance process; this document does not revive historical smokes or grant provider-mutation permission. [R01, R02] 

**Rollback:** revert the active manifest/feature flag, stop admitting new affected jobs, preserve existing artifacts and report which outputs may be stale. Do not rewrite past trial outcomes to make the current release look cleaner. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

59 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **8.5 Added backlog: media and native performance** 

These four work packages integrate the video revision into delivery. Only the first two are baseline engineering priorities. Hardware/runtime optimisation and custom native code remain conditional; they do not block a useful manual analyst workbench. 

|**ID / owner**|**Work and dependencies**|**Definition of done**|
|---|---|---|
|GA-15 / backend +<br>CV|P0: audit sampling and instrument the<br>unchanged path. Depends on GA-01/02;<br>begin with fixtures and mocked<br>invocation counters.|Effective settings, primary/recovery calls,<br>frame/PTS mapping, timing and cost<br>scopes are explicit; no claim that export fps<br>equals inference fps.|
|GA-16 / media +<br>backend|P1: FrameSource adapter, FFmpeg jobs<br>and CPU baseline; one decoder<br>challenger. Depends on GA-02/15 and<br>GA-03 provenance.|CFR/VFR, BGR/RGB, crop/rotation and<br>export fixtures pass; old evidence remains<br>readable; CPU fallback and cancellation<br>are tested.|
|GA-17 / CV +<br>operations|Conditional: GPU decode/residency,<br>batching and runtime/precision<br>comparisons. Depends on GA-15/16,<br>lawful development data and GA-12<br>controls.|Capability test on actual hardware;<br>separate experiment receipts; full-match<br>memory/cost plus football quality pass;<br>default can roll back.|
|GA-18 / native<br>owner + lead|Optional: Rust worker/extension or C++<br>module only for a remaining justified<br>need. Depends on accepted baseline and<br>explicit scope/budget review.|Documented bottleneck or required<br>capability, qualified builds, failure/fallback<br>tests, maintenance owner and measurable<br>acceptance; no speculative rewrite.|



### **Dependency and approval order** 

GA-01/02 -> GA-15 -> GA-16 -> conditional GA-17 -> optional GA-18. Independent labels (GA-13) and analyst workflow work continue in parallel. Baseline profiling does not authorise a new cloud run; all remote work still uses the existing source-bound approval and budget procedure. 

### **Receipt required at each promotion** 

Record source/weights/configuration, hardware and native builds, selected backend, frame/call counts, cold/warm timing, peak memory, transferred bytes, output quality, accepted coverage, failure cases and allocated spend. Track backend fallback as an event. A stage benchmark alone is not a complete-match acceptance receipt. 

Effort and credits: the original indicative ranges remain planning placeholders. Account for GA-15/16 in the scoped milestones and re-estimate GA-17 after profiling. Estimate GA-18 separately. No new budget, saving or runtime is asserted by this revision. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

60 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **9.1 Data rights, model licences and privacy** 

**Objective:** ensure that footage, models and outputs may be used for the intended purpose before commercialising or uploading them. This is a due-diligence plan, not a legal opinion on a particular contract. 

|**Asset or activity**|**Evidence to obtain**|**Product control**|
|---|---|---|
|Match recording|Rights to capture, retain, analyse and<br>share|Source rights record and retention<br>class.|
|Training data|Permission for the intended training<br>and downstream use|Dataset manifest with permitted<br>purposes.|
|Code and weights|Exact code/weight/native-build licences,<br>codec notices and commercial<br>conditions|Dependency/weight/build register and<br>release review; see 4.5D.[V12]|
|Cloud inference|Processing terms, location,<br>subprocessors and retention|Explicit cloud policy and permitted<br>inputs.|
|Export/publication|Audience, sharing permission and<br>deletion process|Scoped links and analyst approval.|



Ultralytics offers AGPL-3.0 and Enterprise licensing and describes different obligations for commercial/private integration. Review the exact code and weight assets and the intended deployment with qualified advice; do not generalise one vendor's terms to every YOLO-named model. RF-DETR and other alternatives must also be checked at the precise version and dependency level. [E11, E23] 

SoccerNet's FAQ describes research use, restrictions on commercial business use and copyrighted-video redistribution. Do not assume a research download or NDA grants rights to ship footage, a hosted product, or every downstream training use. StatsBomb/Hudl open data is another potential research source, but its applicable licence and attribution terms must be checked before the intended use. [E18, E19] 

### **Privacy-by-design workflow** 

Video that identifies a person can be personal data; replacing names with track IDs does not necessarily anonymise it when the person remains identifiable. Regulator and Commission guidance distinguish truly anonymous data from re-identifiable/pseudonymised information. <u>[E21, E22]</u> 

Record the controller/processor roles, lawful basis, notices, retention and sharing rules for the actual use. Youth footage requires particular care with club permissions, safeguarding and any required guardian authorisation. Do not assume consent is always the only possible legal basis or that owning a recording resolves all privacy obligations. 

Minimise unnecessary names, faces and audio in cloud packages. Default to local processing where cloud permission is absent. Provide access/deletion procedures, a DPIA screening step and an incident response path. Avoid face recognition and cross-season identity inference in the initial product. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

61 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

**Acceptance:** the release dossier links to the rights and processing decisions for every data/model category. An uncertain commercial permission blocks that use; it does not get silently converted into “open source means unrestricted.” 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

62 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **9.2 Security, operations and deployment readiness** 

The README explicitly states that Host/Origin checks and CORS are not authentication and that non-local deployment requires its own network gate. Preserve loopback-only operation until a deliberate security design is accepted. [R01] 

|**Boundary**|**Required controls before expansion**|
|---|---|
|Upload and decode|Size/duration quotas; constrained decoder; safe argument vectors and<br>paths; protocol/network allowlist; cancellation, disk and memory limits.|
|Application access|Authentication, server-side authorisation and object-level access checks;<br>do not trust a client-supplied tenant ID.|
|Jobs and workers|Signed/scoped job access where implemented, minimal credentials,<br>egress policy, timeouts and confirmed cleanup.|
|Model/tool output|Treat text, JSON and retrieved instructions as untrusted; allowlist actions<br>and validate references.|
|Storage and exports|Least privilege, scoped links, encryption appropriate to the deployment<br>and audit of publication/deletion.|
|Dependencies and releases|Pinned code, native wheels/engines and codec builds; security/licence<br>review, qualified OS profiles, tested fallback and rollback.|



Keep provider credentials in the authorised host-side control plane; do not embed them into model prompts, frontend bundles, generic logs or sandbox payloads. The repository's operational documentation specifically protects the host credential boundary. [R01, R02] 

Before remote processing, confirm actual location and processing terms. Daytona documentation warns that a requested target/region is ignored by default for GPU sandboxes; an EU-facing application setting is not proof of EU GPU processing. Resolve any residency requirement through an explicit provider arrangement. [E06] 

### **Failure and recovery operations** 

Treat provider timeout, lost job response and uncertain cancellation as reconciliation cases. Query the known job/resource identity through an authorised operation instead of starting a replacement blindly. Record whether cleanup was confirmed; a local “cancelled” status alone is not evidence that billing stopped. 

Test restoration of a database plus referenced assets, corrupted artifact import, full disk, interrupted upload, stale permissions and expired sharing links. Define recovery objectives after measuring data volume and acceptable analyst disruption, rather than promising enterprise uptime from the current local application. 

Separate metrics and logs from sensitive raw video. Record resource timings, validation reasons and error categories without collecting unnecessary personal data. Access to support bundles should be scoped, consented where required and time-limited. 

**Release gate:** no public exposure before the required security review; no secrets in artifacts; successful recovery exercise; bounded failure behaviour; and an operator-visible record of 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

63 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

unresolved incidents. Passing synthetic tests is necessary but not a substitute for a deploymentspecific assessment. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

64 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **9.3 Risk register and final decisions** 

|**Risk**|**Early signal**|**Mitigation / accountable owner**|
|---|---|---|
|Useful coverage remains<br>low|Accurate accepted samples but many<br>unknown intervals|Camera-specific development and<br>capability limits / CV + analyst.|
|Labels delay valid<br>conclusions|Service checks pass but locked labels<br>remain incomplete|Independent labelling plan and<br>separate budget / reviewer + owner.|
|Identities corrupt player<br>totals|Frequent joins/splits or kit-based<br>confusion|Keep tracklets separate; withhold<br>totals / CV + backend.|
|Cost rises without<br>product gain|Miscounted inference, repeated runs,<br>transfer overhead or idle allocation|GA-15 counters, frame/cache contracts<br>and cost-gated GA-17/18 / operations +<br>media lead.|
|AI makes unsupported<br>claims|Invented evidence IDs, numbers or<br>whole-match conclusions|Grounded schemas, deterministic<br>checks and review / backend + analyst.|
|Dataset/model use is not<br>permitted|Missing licence or ambiguous<br>commercial terms|Block the affected use and obtain<br>rights / owner + legal review.|
|Hosted access exposes<br>footage|Missing object-level checks or<br>uncontrolled share links|Keep local boundary; complete<br>security workstream / security lead.|
|Advanced features imply<br>false precision|Exact-looking offside lines or 3D<br>without calibrated evidence|Separate schematic and measured<br>outputs / product + CV.|



### **Decisions to make at project start** 

Choose the initial supported camera workflow, the first analyst deliverable, and the capability boundaries that remain experimental. Name the independent reviewer and obtain the footage/label rights required for evaluation. Confirm the actual compute-credit balance, expiry, GPU availability and any regional restriction before scheduling authorised cloud work. 

Approve the evidence/availability contract before adding report complexity. Keep the existing Python application, frontend and worker separation. Do not commit to a new tracker, detector, vector database or language model until its proposed role and promotion test are defined. 

Adopt deterministic metrics and template reports as the reliable baseline. Make small and frontier AI optional, replaceable assistants. A model should be promoted because it improves a measured task at acceptable cost—not because it is newer, larger or advertised as state of the art on another benchmark. 

### **First meaningful milestone** 

Keep the first milestone a reviewed match with source-linked evidence and honest gaps, not a full native rewrite or a more impressive generated report. The video revision makes that workflow measurable and more efficient; it does not replace independent football validation or expand the initial product promise. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

65 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

That milestone creates the foundation for validated event models, better tactical interpretation and, eventually, carefully qualified multi-view/3D analysis. It also creates the data needed to reduce cost systematically. 

**Final direction:** build football-analysis software that uses AI selectively. Preserve measurement integrity, make uncertainty usable, and optimise the total effort required to produce trustworthy coaching evidence. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

66 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **Appendix A. A worked match-to-report flow** 

This fictional example shows how the proposed layers cooperate. The IDs, timings and values are illustrations, not results from your repository or a real match. 

An analyst uploads a supported wide-view recording. Admission records `asset-A` , its digest, presentation-time map and rights policy. The analyst confirms teams, period boundaries and calibration `cal-3` . Job `run-17` receives a fixed model/config manifest and a bounded processing budget. 

|**Step**|**Artifact or action**|**What the next layer may trust**|
|---|---|---|
|Detect and track|Immutable observations plus tracklets|Image evidence and scores, not<br>verified roster identities.|
|Project and assess|Pitch positions under`cal-3`, with<br>eligibility|Metric coordinates only within<br>validated regions/intervals.|
|Estimate states|Accepted and unknown ownership<br>intervals|The stated source and availability, not<br>continuous unseen possession.|
|Propose events|Candidate turnover`event-52`and shot<br>`event-53`|Hypotheses with timing/evidence<br>references.|
|Review|Analyst confirms both and corrects one<br>player link|Accepted event versions with retained<br>edit history.|
|Query|“Turnovers followed by a shot within<br>ten seconds”|Python evaluates the typed event<br>relationship.|
|Report|A linked passage and an optional<br>tactical interpretation|Factual fields are fixed; interpretation<br>remains labelled and reviewable.|



Suppose the analyst later discovers that the team mapping was reversed in one interval. Correction `edit-8` supersedes that mapping. The system retains the original video, detections and tracklets, recalculates affected team states/events/metrics, and marks the old report stale. It does not pay for another complete vision pass merely because a report's conclusion changed. 

If the optional model endpoint fails, the query still returns the reviewed interval and the template report still contains accepted events, metric definitions and limitations. If the ball disappears during the decisive transition, the system instead returns a candidate for human review and explains why the relationship cannot be accepted automatically. 

### **Required final match package** 

The analyst receives a source-linked playlist, a reviewed event timeline, eligible metrics with denominators, a coverage/limitations summary and a versioned report. The operator receives the source/model manifest, cost and timing receipt, error/cleanup status and audit links. Neither package needs to expose credentials or retain unnecessary cloud copies. 

**Why this design saves cost:** expensive observations are reused, corrections target only dependent calculations, small components handle narrow tasks, and stronger models receive 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

67 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

only the evidence needed for a specific question. The saving is architectural rather than dependent on one permanently cheap model. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

68 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **Source register I — repository evidence** 

Repository entries are pinned to the inspected commit. External entries are primary project, provider or official guidance sources reviewed on 16 September 2026. Links open the source; citation codes in the text jump to this register. 

##### **[R01]  Repository README** 

Inspected README sections. Product boundary, local setup, Daytona execution, loopback restriction and retired-smoke warning. 

##### **[R02]  Authoritative current status** 

Selected status/evidence sections. Source-bound verification, historical execution/capacity, frozen corpus, alignment and independent-label limitations. 

##### **[R03]  Backend schema definitions** 

Lines 1-260. Match configuration, observation/state types, metric defaults, jobs and review bundles. 

##### **[R04]  Python analytics implementation** 

Lines 220-345. Handcrafted shot score, defensive-shape calculations and pressing denominator behaviour. 

##### **[R05]  Language-model integration** 

Lines 1-240 and 300-470. Structured payloads, evidence/context construction, offside/spacing prompts and provider configuration. 

##### **[R06]  Video pipeline adapter** 

Inspected adapter. Manual/automatic homography selection, model fallback and recovery-profile forwarding. 

##### **[R07]  Isolated research-lane architecture** 

Inspected architecture sections. Frozen manifests, executable versus inert tracks, append-only trial ledger and execution/path safeguards. 

##### **[R08]  Storage implementation** 

Lines 1-100. SQLite/file context, separated result artifacts, video identity and regular-file handling. 

##### **[R09]  Frontend package manifest** 

Inspected in full. React, TypeScript, Vite, Tailwind and frontend verification scripts. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

69 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **Source register II — tools, products and infrastructure** 

Primary sources reviewed on 16 September 2026. Live documentation, model availability, prices and terms may change after that date. 

##### **[E01]  PySport: Kloppy** 

Primary project. Vendor-neutral event/tracking representations and import/export boundaries. 

##### **[E02]  ML-KULeuven: Socceraction** 

Primary project. SPADL and action-valuation implementations, including xT and VAEP. 

##### **[E03]  TrackEval** 

Primary evaluation implementation. HOTA and other multi-object tracking metrics; compatible ground truth remains required. 

##### **[E04]  Hudl Sportscode** 

Official product description. Coding, timelines and video-linked analysis as workflow references, not independent accuracy evidence. 

##### **[E05]  Veo Analytics 2: overview and features** 

Official product documentation. Integrated team/player analysis; eligibility and feature scope are productspecific. 

##### **[E06]  Daytona: Sandboxes** 

Official documentation. Sandbox capabilities and the GPU target/region limitation requiring explicit residency confirmation. 

##### **[E07]  Daytona: Billing** 

Official billing documentation. Resource allocation/lifecycle and usage accounting; use actual contractual rates for procurement. 

##### **[E08]  Daytona: Pricing** 

Official dynamic rate card. Retrieved representations differed and showed preemptible/on-demand choices; budget examples use explicit assumptions, not a selected GPU quote. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

70 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **Source register III — rules and model candidates** 

Primary sources reviewed on 16 September 2026. Live documentation, model availability, prices and terms may change after that date. 

##### **[E09]  IFAB Law 11: Ofsidef** 

Official law. Position, involvement, timing and exceptions. Confirm the applicable edition/competition for any deployed ruleset. 

##### **[E10]  Qwen3.5-4B model card** 

Official model card. Compact multimodal candidate; no football-specific quality or runtime benchmark is inferred. 

##### **[E11]  Roboflow: RF-DETR** 

Primary detector project. Model variants and licensing information; public generic benchmarks are not football acceptance. 

##### **[E12]  McByte++** 

Primary tracking implementation. Candidate comparison and documented all-frame EdgeTAM loading limitation. 

##### **[E13]  Roboflow: Trackers** 

Primary project. Detector-independent tracking components for adapter-based experiments. 

##### **[E14]  Torchvision: MViT video models** 

Official model documentation. Pretrained multiscale video-transformer builders as representation baselines. 

##### **[E15]  OpenGVLab: VideoMAE-v2** 

Primary research implementation. Video-representation option, not a claim to current football state of the art. 

##### **[E16]  ONNX Runtime: Quantisation** 

Official deployment documentation. Accuracy and hardware-dependent performance considerations for quantised models. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

71 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **Source register IV — pricing, data and rights** 

Primary sources reviewed on 16 September 2026. Live documentation, model availability, prices and terms may change after that date. 

##### **[E17]  Google: Gemini Developer API pricing** 

Official rate card. Gemini 3.8 Flash standard introductory rates through 31 December 2026 and listed rates from 1 January 2027; output includes thinking tokens. 

##### **[E18]  SoccerNet: FAQ** 

Official dataset guidance. Research-use scope, commercial-use restrictions, NDA and copyrighted-video redistribution limitations. 

##### **[E19]  Hudl/StatsBomb open data** 

Primary data repository. Potential research source; exact licence, attribution and intended-use permissions must be checked before adoption. 

##### **[E20]  FFmpeg: FFprobe documentation** 

Official media-probing documentation. Stream/frame inspection for source identity and time mapping. 

##### **[E21]  Irish Data Protection Commission: What is personal data?** 

Regulator guidance. Identifiability and the distinction between personal and genuinely anonymised data. 

##### **[E22]  European Commission: Data protection explained** 

Official EU guidance. General personal-data and re-identifiability principles; not a case-specific legal opinion. 

##### **[E23]  Ultralytics licensing** 

Official vendor licensing explanation. AGPL-3.0 versus Enterprise routes; assess exact code/weights and deployment obligations before commercial use. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

72 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **Source register V — video revision evidence** 

Primary sources checked for revision 1.1 on 16 September 2026. These extend, rather than replace, the original source register. Vendor capabilities are not measured performance on your application. 

#### **[R10]** <u>Pinned primary video-processing implementation</u> 

Rechecked configuration and selected spans 7500-8160. BGR assumption, primary tracking call, post-result sample filter and index-derived timestamps. Source observation only; not executed. 

#### **[V01]** <u>Ultralytics: model prediction arguments</u> 

Official vid_stride, batching and stream-buffer semantics. Runtime-effective settings still require inspection. 

**[V02]** <u>FFmpeg: command-line documentation</u> 

Primary documentation for stream copy, decoding, transcoding, filtering and seek/export behaviour. 

#### **[V03]** <u>PyAV: project documentation</u> 

Python access to native media containers, packets and frames. Select package/build versions independently of a documentation URL label. 

#### **[V04]** <u>TorchCodec: ofcial project and usagefi</u> 

Tensor decoding, CPU/CUDA options, frame PTS/durations and dependency compatibility. No performance result for this repository is inferred. 

#### **[V05]** <u>NVIDIA: PyNvVideoCodec API programming guide</u> 

Hardware media API and DLPack tensor sharing; full pipelines may still allocate, convert and transfer data. **[V06]** <u>NVIDIA Container Toolkit: specialised confgurationi</u> 

Video driver capability is distinct from compute and utility. Does not confirm availability inside the user's Daytona worker. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

73 / 74 

<u>Reading map</u> 

**GUERILLA ANALYTICS** 

## **Source register VI — runtimes and native integration** 

Primary sources checked for revision 1.1 on 16 September 2026. These extend, rather than replace, the original source register. Vendor capabilities are not measured performance on your application. 

#### **[V07]** <u>NVIDIA TensorRT: performance best practices</u> 

Benchmarking/performance guidance. Separate complete-job timing from kernel or submission timing. 

**[V08]** <u>NVIDIA TensorRT: accuracy considerations</u> 

Precision/quantisation trade-offs and numerical errors. Optimised exports require target-task validation. 

**[V09]** <u>GStreamer: language bindings</u> 

Official Python, Rust and other bindings. GStreamer adoption does not, by itself, require a language rewrite. 

#### **[V10]** <u>PyO3: user guide</u> 

Rust-to-Python extension interface. The plan recommends bounded coarse-grained calls, not a wholesale rewrite. 

#### **[V11]** <u>pybind11: project documentation</u> 

C++/Python interoperability for qualified native components. Binding support is not evidence of an application speedup. 

#### **[V12]** <u>FFmpeg: licence and legal considerations</u> 

Official explanation of build-dependent licensing and distribution obligations. Review the exact shipped build; this plan is not legal advice. 

#### **[V13]** <u>ONNX Runtime: execution providers</u> 

Official runtime-provider boundary, including CPU/GPU options. Qualify the selected provider and fallback on actual hardware. 

IMPLEMENTATION BLUEPRINT  |  V1.1  |  16 SEPTEMBER 2026 

74 / 74 

