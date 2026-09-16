# Full Project Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close every confirmed High/Important finding not already owned by the two active result/progress plans, using deletion or existing boundaries before adding code.

**Architecture:** Keep the current Python/SQLite/filesystem and React design. Remove unsafe generic paths and duplicate state; harden the existing mutation boundaries; add only small shared primitives where three actual consumers already exist. Keep historical data, provider authorization, and measured pipeline capacity as explicit gates rather than hiding them in a refactor.

**Tech stack:** Existing Python standard library, SQLite, FastAPI/Starlette, React/TypeScript, pytest, Vitest, and existing testing-library/jsdom. No new framework, service, queue, browser transport, or dependency.

**Spec:** docs/superpowers/specs/2026-09-12-full-project-remediation-design.md.

## Source reports and current ownership

Prefixes below disambiguate overlapping IDs:

- B = docs/superpowers/audits/2026-09-12/backend-runtime-audit.md.
- F = docs/superpowers/audits/2026-09-12/frontend-audit.md.
- O = docs/superpowers/audits/2026-09-12/tests-ops-docs-audit.md.
- CP-RESULTS = docs/superpowers/plans/2026-09-10-streamed-full-match-results.md, Tasks 1–5.
- CP-PROGRESS = docs/superpowers/plans/2026-09-10-live-daytona-progress.md, Tasks 1–5.

The reports describe the audited 0504370f-era snapshot; the execution branch is now at `a0cf6596` after the reviewed ResultBundle v2 and live-progress work. Active implementation may already have changed result contracts/tests. This synthesis does not review, overwrite, or claim completion of that concurrent work. Each task must recheck its finding against the integrated current branch before producing a failing regression.

Parent ruling already recorded in the live-progress SDD ledger: stdout write/flush failure is telemetry loss only; it must not invalidate sealed progress/results. The contradictory consecutive Step 3 sentences in CP-PROGRESS do not create another remediation task; the implementer follows that ruling.

## Global constraints carried from the approved spec/plans

- Keep exactly two result artifacts and the existing completion-to-result-to-artifact SHA-256 chain.
- V2 format is exactly jsonl-v1; processor filename is exactly result.processor-result.jsonl.
- Shared processor maximum is 1 GiB; metadata line maximum is 64 MiB; row line maximum is 64 KiB.
- V1 remains capped at 64 MiB and is never guessed to be v2.
- Do not add a dependency, cloud call, or Daytona smoke.
- All local publication remains temp-file, file-fsync, replace, and parent-fsync protected.
- Any v2 import or analytics failure must roll back through Storage.remote_result_import.
- Use Daytona SDK sessions; do not add a sandbox service, queue, dependency, websocket client, or cloud smoke.
- Poll provider command state and frontend job state approximately every two seconds.
- Map worker 0–100 progress into host 0.10–0.85; reserve 0.90 for import and 1.0 for terminal completion.
- Provider logs are untrusted; only complete, canonical, bounded, credential-safe, matching-job, monotonic marked lines may update state.
- Live telemetry never authorizes result acceptance; the sealed final progress artifact remains authoritative.
- Session cleanup does not weaken the existing confirmed sandbox and local-staging cleanup rules.

Additional synthesis constraints: preserve normal public payloads and existing trust gates; no automatic production cleanup; no history rewriting; no automatic dispatch retry when a child may already exist. Dependency upgrades/removals and image/source changes require fresh release binding. Historical smoke evidence remains historical.

## Complete High/Important accounting

This table covers all 22 severity-qualified IDs: six backend, seven frontend, and nine tests/ops IDs. “High confidence” on a Medium/Low finding or on an optional Ponytail cut is not a High severity and is not silently promoted.

| Report ID | Reported issue | Disposition | Exact owner / closure gate |
|---|---|---|---|
| B:S1 | Legacy review arbitrary reads, unbounded bodies, exposed binding | New remediation | R02; overlaps O:I02. Host/Origin restrictions included; public hosting remains G-NETWORK. |
| B:S2 | 1 GiB worker / 64 MiB host mismatch and whole-result copies | Current plan | CP-RESULTS Tasks 1–5; verify the >64 MiB / 621,000-row acceptance, not merely contract parsing. |
| B:P1-runtime | GPU producer retains full match graph; frame-level copies remain | Explicit deferred measurement | G-CAPACITY. CP-RESULTS removes host raw-row copies only; the approved spec deliberately permits the current GPU result graph. |
| B:P2-runtime | Synchronous work blocks async API handlers | New remediation | R15, after current storage/remote-worker owners finish. |
| B:C1 | Upload/match/job/dispatch admission is not transactional | New remediation | R10, with its explicit admission/dispatch outcome contract approved before code. |
| B:C2 | Wildcard origins on unauthenticated mutation/compute routes | New remediation + deployment gate | R04 for the local browser boundary; G-NETWORK for any multi-user/LAN/public service. CORS alone is not authentication or CSRF protection. |
| F:COR-01 | Enemy passes projected as home-team edges | New remediation | R13; preserve the existing home-team-only overlay and filter enemy events. |
| F:COR-02 | Review range/partial drawing survives match changes | New remediation | R12; same state owner/lifecycle as F:COR-12. |
| F:COR-03 | Unsupported Cloud control remains enabled | New remediation | R14; use the existing capability field, do not invent a capability service. |
| F:COR-12 | Duplicate drawing modes diverge after save | New remediation | R12; remove App's duplicate state. |
| F:PERF-01 | Startup hydrates every match and fails all-or-nothing | New remediation | R16; load list plus selected workspace and isolate per-match failure. |
| F:SEC-01 | Advisory-affected Vitest/dev dependency tree | New remediation | R11; refresh existing direct tools, rerun both audit modes, no new dependency. |
| F:A11Y-01 | Pitch/calibration core interactions are pointer-only | New remediation | R17a and R17b, independently reviewable keyboard alternatives. |
| O:I01 | Cleanup can delete root/latest descendants | New remediation | R01; deletion must not call reset_output, which recreates a directory. |
| O:I02 | Legacy review arbitrary file serving | New remediation | R02; same defect as B:S1. |
| O:I03 | Concurrent successful review decisions overwrite one another | New remediation | R05; lock the whole overlay transaction. |
| O:I04 | Sidecar execution bypasses path policy | New remediation | R08; includes default-root, extra-argument and manifest-write boundaries. |
| O:I05 | Installed sidecar cannot resolve advertised executable backend | New remediation | R09, after R08's root policy. |
| O:I06 | Legacy review pending saves overwrite newer drafts | New remediation | R07; pending transaction guards cover navigation and shortcuts too. |
| O:I07 | Review metadata reaches innerHTML | New remediation | R03; remove HTML parsing for plain metadata. |
| O:I08 | Bundle-date traversal escapes archive output | New remediation | R06; canonical date + owned-root publication. |
| O:I09 | GPU infrastructure smoke is not real product acceptance | Existing spec gate, not another smoke | G-PRODUCT, required after both current plans and fresh release evidence. |

## Execution sequence and safe concurrency

Risk takes precedence over line savings. “Deletion-first” means remove an unsafe unnecessary behavior before constructing a replacement, not delete provenance or delay a data-loss fix to chase a line-count target.

| Wave | Units | Why now / dependencies |
|---|---|---|
| 0 | Finish CP-RESULTS and CP-PROGRESS in their current ownership lanes | Do not edit backend/app/remote_contracts.py, gpu_worker.py, remote_worker.py, storage.py, analytics.py, processor.py, daytona.py or their active tests, or frontend App/api progress files, concurrently with those owners. |
| 1 | R01, R02, R03, R04 | Root-deletion/file-disclosure/browser-origin boundaries. R01/R02 can run independently of current protocol work; R03 shares legacy HTML only; R04 waits for the main/settings file owner. |
| 2 | R05, R06, R07, R08, R09, R10 | Persisted/draft data safety and operator-tool correctness. R05 follows R02 on server files; R07 follows R03 on HTML; R09 follows R08; R10 waits for CP-RESULTS storage changes. |
| 3 | R11, R12, R13, R14, R15, R16, R17a, R17b | Toolchain, tactical correctness, responsiveness, selected-match loading, keyboard access. R11 must not replace the test environment mid-SDD. Serialize R12/R14/R16 on App.tsx after CP-PROGRESS Task 4. R13 is independent. R17a follows R12; R17b is independent of the pitch. |
| 4 | G-PRODUCT, then G-CAPACITY | Fresh source-bound acceptance first, representative full-match measurement second. No implicit provider authorization. |
| Optional housekeeping | D01, D02, G-RETENTION | Small proven cuts can be separate reviewed commits; broad archive/model decisions never block the urgent boundary fixes. |

Every R unit follows one reviewable TDD cycle:

- [ ] Confirm the current implementation still exhibits the named failure; preserve another owner's work.
- [ ] Add the named regression/fault vectors below and run the focused command; confirm the expected failure.
- [ ] Apply only the specified local correction, keeping all sibling callers consistent.
- [ ] Rerun the focused command and relevant existing suites; inspect the diff for payload/authority expansion.
- [ ] Independently review and commit only this unit when authorized; do not roll unrelated tasks into that commit.

These five checkboxes are the required steps for every numbered task below. Each task supplies its exact files, failure vectors, implementation boundary, and focused command; its SDD brief carries this shared cycle and the task-specific text together.

## Fix-now units

### Task 1: R01 — Confine approved cleanup deletion

**Status:** Complete in commits `862080fd`, `0176d913`, and `566a6581`; final review clean under the recorded fail-closed ruling.

Files: backend/scripts/run_video_to_analysis_storage_cleanup_bounded_execution.py; backend/tests/test_run_video_to_analysis_storage_cleanup_bounded_execution.py; backend/tests/test_run_video_to_analysis_storage_cleanup_closeout.py.

The completed implementation validates candidate paths but never deletes them: it reports `video_to_analysis_storage_cleanup_automatic_deletion_disabled`, `cleanupMutationExecuted: false`, zero deleted paths, and zero reclaimed bytes. This is the required outcome because a standalone runner cannot prove that a concurrently created version is not newer at the mutation boundary. Existing path, symlink, latest-version, and ancestor-swap regressions remain as non-mutation guards.

Focused command: python3 -m pytest -q backend/tests/test_run_video_to_analysis_storage_cleanup_bounded_execution.py

Closure: 29 focused and 44 related tests passed; no real storage cleanup occurred. Any future deletion implementation is a new gated task requiring an exact retention manifest and writer coordination that makes “latest” stable for the entire transaction. It must not restore the obsolete successful-old-version deletion path in this plan.

### Task 2: R02 — Remove arbitrary file routes and bound legacy HTTP input

Files:
- backend/scripts/serve_promoted_v6_manual_review_ui.py
- backend/scripts/serve_v7_1_positive_diversity_review_ui.py
- backend/scripts/serve_football_external_soccernet_detector_miss_review_ui.py
- Their exact test counterparts: backend/tests/test_serve_promoted_v6_manual_review_ui.py, backend/tests/test_serve_v7_1_positive_diversity_review_ui.py, backend/tests/test_serve_football_external_soccernet_detector_miss_review_ui.py.

Delete the generic static fallback: these tools need their fixed index and approved evidence images, not a general filesystem server. Replace client-supplied file paths with review-item/image-role lookup, or a strictly checked membership lookup if preserving the URL shape is required. Open only approved regular image files through no-follow boundaries. Allow only loopback bind addresses for these unauthenticated tools; reject foreign Host/Origin on mutation routes. Set a small explicit JSON-body limit (64 KiB is sufficient for one decision/notes/bbox payload), reject invalid/negative/oversized lengths before read, and apply socket read timeouts.

Tests must send real raw HTTP paths: absolute paths, encoded and unencoded parents, sibling-prefix paths, symlinks, missing images, and a legitimate manifest-owned image. Assert the outside sentinel is never returned. Test Content-Length of -1, malformed text, 65,537, and a valid bounded body, plus non-loopback startup refusal. Move the SoccerNet tests' global /tmp image fixtures under tmp_path while touching them (O:M04).

Focused command: python3 -m pytest -q backend/tests/test_serve_promoted_v6_manual_review_ui.py backend/tests/test_serve_v7_1_positive_diversity_review_ui.py backend/tests/test_serve_football_external_soccernet_detector_miss_review_ui.py

A small shared serving/body-read function is justified only after two corrected call sites have exactly the same semantics. Do not merge the three different review schemas/resolvers into a configurable server framework.

### Task 3: R03 — Render legacy metadata as text

Files: backend/review_ui/promoted_v6_manual_review/index.html; backend/review_ui/v7_1_positive_diversity_review/index.html; backend/review_ui/football_external_soccernet_detector_miss_review/index.html. Create frontend/src/legacyReviewUi.test.ts to exercise these existing HTML scripts with the already-installed jsdom/Vitest environment; read the three files directly without copying their production code into tests.

Replace the three metadata innerHTML constructions with native DOM creation:

    const dt = document.createElement('dt');
    const dd = document.createElement('dd');
    dt.textContent = key;
    dd.textContent = String(value ?? '');
    metaEl.append(dt, dd);

Clear via replaceChildren before appending. No sanitizer or rich-text support is needed. Test each HTML file with an event/source ID containing markup, asserting the literal string is visible and no injected element/event handler exists.

Focused command: npm --prefix frontend test -- --run src/legacyReviewUi.test.ts

Keep this independent from pending-save work so the injection fix can be reviewed and shipped on its own.

### Task 4: R04 — Enforce a local browser-origin boundary without pretending it is authentication

Files: backend/app/main.py; backend/app/settings.py; backend/tests/test_api.py; backend/tests/test_settings.py; README.md. Create backend/tests/test_api_origins.py for HTTP/websocket origin cases.

Remove wildcard CORS. Reuse explicit configured trusted frontend origins and reject an untrusted present Origin at state-changing HTTP routes and websocket acceptance. CORS response headers alone do not stop simple multipart POSTs; the server must reject those requests before upload persistence/compute. Reject wildcard/“null” origin policy in ordinary operation. Preserve same-origin UI, configured local development frontend, and origin-less trusted CLI behavior under the local-only contract; validate Host at the serving boundary to limit rebinding.

Regression names: test_foreign_origin_upload_rejected_before_storage; test_foreign_origin_mutation_rejected_without_preflight; test_allowed_local_origin_remains_usable; test_websocket_rejects_foreign_origin. Assert zero calls to save_upload_stream/create_match/start on rejection.

Focused command: python3 -m pytest -q backend/tests/test_api_origins.py backend/tests/test_api.py backend/tests/test_settings.py

G-NETWORK remains mandatory for non-local deployment: neither an origin allowlist nor CORS authorizes arbitrary non-browser clients. Do not add home-grown accounts/tokens as an incidental patch.

### Task 5: R05 — Serialize legacy review updates and preserve durable outcome

Files: the three server/test pairs listed in R02. If no existing helper satisfies the required failure semantics after CP-RESULTS is integrated, create only backend/scripts/review_io.py and backend/tests/test_review_io.py for these three real consumers.

First add one lock covering load, schema validation, item mutation and final publication; atomic replace alone is not a transaction. A process-wide lock for these low-throughput operator tools is sufficient, with a Ponytail comment recording that ceiling. Do not invent a multi-tenant lock registry.

Remove the three copied fd-ownership bugs. Ensure an fdopen failure closes the raw fd; temporary files are cleaned on read/encode/write/replace failure. Define post-replace durability failure explicitly before sharing an atomic writer: merely deleting the new overlay cannot recover the old one (B:C3). For updates, retain the old file through a recoverable backup until publication is durable, or return an explicit committed outcome without inviting a non-idempotent retry. The parent must approve the chosen outcome contract; never silently swallow a disk failure.

Regression: use a barrier to start different-item edits together; both accepted decisions must remain. Add corrupt/schema-invalid input preservation, fdopen failure, write/replace failure, and post-publication parent-open/fsync failure with an unambiguous visible outcome. Keep caller signatures and review schemas unchanged.

Focused command: python3 -m pytest -q backend/tests/test_review_io.py backend/tests/test_serve_promoted_v6_manual_review_ui.py backend/tests/test_serve_v7_1_positive_diversity_review_ui.py backend/tests/test_serve_football_external_soccernet_detector_miss_review_ui.py

If no shared module is created, omit only test_review_io.py from that command and place the same fault vectors in the existing three tests. This is an explicit alternative, not a missing test.

### Task 6: R06 — Canonicalize bundle names and confine archive publication

Files: backend/scripts/build_parallel_research_bundle.py; backend/tests/test_build_parallel_research_bundle.py.

Delete support for arbitrary bundle-date strings:

    bundle_date = date.fromisoformat(bundle_date).isoformat() if bundle_date else date.today().isoformat()

Perform validation before any reset/mkdir/copy/ZIP open. Reuse the existing owning-root reset pattern for the bundle directory; keep the owning archive/root descriptor pinned or reject path identity changes before ZIP publication. Write the ZIP to an owned temporary and replace only its validated output name. Do not unlink an old ZIP before a new one is safely complete.

Tests: dates containing slash/backslash/parents, invalid dates, archive/bundle/ZIP symlinks and parent swaps must preserve outside sentinels and prior ZIP bytes; a normal ISO date must produce the same member layout. Name the cases test_bundle_date_rejects_path_components and test_bundle_failure_preserves_previous_archive.

Focused command: python3 -m pytest -q backend/tests/test_build_parallel_research_bundle.py

### Task 7: R07 — Guard the whole pending legacy review form

Files: the three HTML files in R03; frontend/src/legacyReviewUi.test.ts.

Add one pending flag per review page. While true, disable notes/reason/bbox edits, next/previous, filtering, shortcuts and resolver actions; duplicate save entry returns immediately. Catch fetch/JSON/load-after-save rejection at the event boundary, keep the draft if persistence failed, and unlock in finally. Do not add a draft store or asynchronous action framework.

Tests against all three real scripts: defer the save response, attempt field/navigation/shortcut changes, assert one submitted decision and no draft overwrite, then resolve and check reload; reject network/JSON and assert an error plus unchanged draft with no unhandled rejection.

Focused command: npm --prefix frontend test -- --run src/legacyReviewUi.test.ts

This protects the same form throughout the request; disabling only the Save button is insufficient.

### Task 8: R08 — Make sidecar isolation an execution-boundary invariant

Files: research-addon/research_addon/path_guards.py; research-addon/research_addon/judge.py; research-addon/research_addon/cli.py; research-addon/research_addon/corpus.py; research-addon/tests/test_paths.py; research-addon/tests/test_judge_contract.py; research-addon/tests/test_cli.py; research-addon/tests/test_corpus_manifest.py.

Delete the raw-string is_safe_path export after confirming its definition-only status and remove hard-coded checkout prefixes. Resolve the configured addon root and explicit temporary roots physically and use Path containment. Enforce the same resolver inside run_judge and manifest writes, including defaults; no entry point may bypass it. Reject protected duplicate flags in extra_args (storage/video/repository roots), or remove that argument if the caller trace still proves it unused.

Draft policy: allow the actual addon-owned root and explicit owned temporary execution roots; retain compatibility for a caller-created temporary directory only after validating it is not a symlink or a relocated core-product subtree. Do not allow every pathname merely because it starts with /tmp. The parent must confirm this policy before changing existing public path expectations. Default corpus output moves beneath the validated addon execution root.

Tests: direct run_judge and both CLIs, exact allowed root, sibling prefix, moved checkout, traversal, default-root symlink, extra-argument override, and default manifest write. Replace the tautological O:M02 checks with actual delegate-boundary assertions while touching these files.

Focused command: python3 -m pytest -q research-addon/tests

### Task 9: R09 — Declare the sidecar's real execution context instead of inferring a repository

Files: research-addon/research_addon/judge.py; research-addon/research_addon/cli.py; research-addon/research_addon/corpus.py; research-addon/pyproject.toml; research-addon/tests/test_cli.py; research-addon/tests/test_judge_contract.py; backend/tests/test_documented_startup.py; .factory/library/architecture.md.

Deletion-first draft choice: keep the sidecar a developer orchestration tool; do not add a backend package dependency or ship videos/models in its wheel. Require an explicit validated repository root and explicit corpus manifest for executable judging, with a checkout default only when an actual backend/scripts/run_local_app_path_proof.py and expected addon layout are present. Wheel “tracks list” must distinguish available-with-config from executable-now. Remove the unconditional three-parent REPO_ROOT inference and hard-coded proof-video discovery.

Run the delegated script with the interpreter/cwd explicitly associated with that validated repository. Propagate a controlled nonzero child result and reject malformed/missing metric fields. The root choice cannot override R08's output confinement.

Installed-outside-checkout tests must reach a controlled backend delegate using an explicit fixture repo/manifest, exercise nonzero and malformed output, and confirm no-configuration output is honest and does not write under site-packages. This is not satisfied by a static tracks-list string.

Focused command: python3 -m pytest -q research-addon/tests backend/tests/test_documented_startup.py -k 'sidecar or judge or corpus or paths'

Alternative archival of the entire sidecar requires G-RETENTION/owner approval; do not silently remove an advertised supported research workflow.

### Task 10: R10 — Make match/job admission compensatable and dispatch outcomes visible

Files: backend/app/main.py; backend/app/storage.py; backend/app/jobs.py; backend/tests/test_uploads.py; backend/tests/test_api.py; backend/tests/test_jobs.py. Create backend/tests/test_match_admission.py for the end-to-end failure matrix.

This is a required design-first unit after CP-RESULTS Task 4, not permission to build a general transaction/outbox framework. Approve these exact outcome rules before code:

1. Before admission is durably committed, any upload/publication/match-insert/job-insert/commit failure leaves no accepted match/job and removes only this operation's unique upload.
2. Match and job inserts use one SQLite transaction and preallocated IDs; there is no committed match-without-job state.
3. After the pair is committed, dispatch failure never blindly deletes the accepted upload or records. A known no-child-start outcome is persisted as failed with a safe cause and stable IDs; uncertainty remains visible and must not trigger an automatic second process.
4. Any retry of the same admitted operation reuses its identity rather than creating a second match/job. If this requires a new admission token/response field, approve that small API contract explicitly before implementation rather than smuggling it into cleanup.

Tests inject every boundary, including DB commit, response/dispatch failure and a dispatch that started before a later error. Assert filesystem/SQLite state and stable identity, not merely HTTP status. A process-crash/power-loss guarantee is not established by exception compensation; if it is required, record the operation state in the existing SQLite database and test restart reconciliation before claiming it.

Focused command: python3 -m pytest -q backend/tests/test_match_admission.py backend/tests/test_uploads.py backend/tests/test_api.py backend/tests/test_jobs.py

Deletion-first action: remove repeated independent commits/ad-hoc route orchestration only after the single bounded admission operation proves equivalent on success. No background queue, scheduler, service, or cloud operation.

### Task 11: R11 — Refresh the affected existing frontend toolchain

Files: frontend/package.json; frontend/package-lock.json. Tests/config only if an actual existing-tool upgrade requires adjustment; scripts/verify.sh and .github/workflows/ci.yml only for the resulting bounded dev-audit gate.

The advisory counts are a report snapshot, not a promise about today's registry. Re-run npm audit, identify patched versions through the existing direct tools, and upgrade the affected direct package(s), beginning with Vitest. Do not use npm audit fix --force or nested overrides as a substitute for understanding compatibility. Never expose Vite/Vitest UI to an untrusted network.

Before upgrading, remove only traced unused direct dev declarations (@testing-library/jest-dom, autoprefixer, direct postcss) if the current import/config scan and clean build still prove they are unnecessary; this is optional and must not delay the security upgrade. No new package is needed.

Commands: npm --prefix frontend audit --json; npm --prefix frontend audit --omit=dev --json; then, after the approved lock update, npm ci --prefix frontend; npm --prefix frontend test -- --run; npm --prefix frontend run lint; npm --prefix frontend run build.

Closure: the specific reported Critical/High paths are gone or an exact remaining advisory/exposure exception is approved; all tests/types/build pass from a clean install. A zero production-only audit is not evidence that the development finding is fixed.

### Task 12: R12 — One match-scoped review mode and reset boundary

Files: frontend/src/App.tsx; frontend/src/features/review/useReviewSurface.ts; frontend/src/features/review/useReviewSurface.test.tsx; frontend/src/App.test.tsx; frontend/src/components/DrawingToolbar.tsx only if its prop call changes.

Remove App.drawingMode and derive canvas/toolbar mode from review.reviewMode. Move reviewRange, reviewMode and pendingArrowStart reset into an internal activeMatchId lifecycle boundary; remove the unused exported reset seam. Clamp range endpoints to the new match's available frame range; refuse an annotation save when no valid frame exists. Keep async save completion keyed to the originating match so a late success cannot reset a new match's gesture.

Tests: begin a range/arrow on match A, switch to shorter B, and assert cleared mode/start/range and valid B timing; complete one drawing and assert the toolbar/canvas both exit drawing mode; reselect and save another; deliver A's delayed completion after B starts drawing and preserve B state.

Focused command: npm --prefix frontend test -- --run src/features/review/useReviewSurface.test.tsx src/App.test.tsx

Do not mix passing-network math or workspace hydration into this state-lifecycle commit.

### Task 13: R13 — Exclude enemy passes from the home-only network

Files: frontend/src/utils/analytics.ts; frontend/src/utils/analytics.test.ts. No edge-model or renderer expansion is required for the currently home-only overlay.

Add the smallest filter at aggregation:

    if (event.type !== 'pass' || event.team !== 'my_team'
        || event.fromTrackId == null || event.toTrackId == null) continue;

Regression: one home pass 7→11 and one enemy pass 7→11 must produce a single home edge with count 1; enemy-only events produce no network. Preserve ordering/count behavior for existing home passes.

Focused command: npm --prefix frontend test -- --run src/utils/analytics.test.ts

A both-teams network is a separate feature, not the fix for this incorrect home overlay.

### Task 14: R14 — Stop offering unsupported cloud analysis

Files: frontend/src/App.tsx; frontend/src/hooks/useCoachAnalysis.ts; frontend/src/App.test.tsx. Create frontend/src/hooks/useCoachAnalysis.test.ts only if the existing App test cannot directly exercise provider calls.

Use coach.supportsCloudProvider to omit/disable Cloud and guard the action itself. If capabilities remove the currently selected provider, return to a supported provider before analysis/upload. Remove the hard-coded appearance of Cloud availability, not the existing capability check.

Tests must render the actual control with local-only capabilities, attempt selection, and assert no cloud analysis request; then supply supported cloud capability and assert the existing action works. A formatter/string-only test is not acceptance.

Focused command: npm --prefix frontend test -- --run src/App.test.tsx

Do not add another capabilities endpoint or new provider; source real capabilities only through an already-supported contract.

### Task 15: R15 — Move blocking API work off the event loop

Files: backend/app/main.py; backend/app/llm.py only if the handler boundary cannot contain the synchronous call; backend/tests/test_api.py. Create backend/tests/test_api_concurrency.py.

Delete async from handlers that perform only synchronous work, allowing FastAPI's existing threadpool behavior. Keep upload/websocket handlers async and offload only their blocking storage/dispatch segments. Do not make a wholesale AsyncClient migration: threadpooling the existing bounded synchronous LLM call is sufficient. Preserve timeout/error mapping.

Test using an actual asynchronous ASGI client: hold a synchronous frames or LLM operation on a threading.Event while a lightweight request and websocket progress remain responsive, then release it. Use an outer timeout so the failing event-loop case cannot hang the suite. Confirm the blocked operation's thread identity differs from the event-loop thread.

Focused command: python3 -m pytest -q backend/tests/test_api_concurrency.py backend/tests/test_api.py

A streaming HTTP response or analytics caching layer is not necessary for this unit.

### Task 16: R16 — Hydrate only the selected match

Files: frontend/src/App.tsx; frontend/src/utils/api.ts; frontend/src/types/index.ts only for the lightweight-list/loaded-workspace distinction; frontend/src/App.test.tsx; frontend/src/utils/api.test.ts.

Delete startup's Promise.all over every ready match. Keep the match list as lightweight metadata and load only the initial selection, then the selected or explicitly compared workspace. Retain at most the active/comparison working set; do not replace eager loading with an unbounded historical cache. Ignore stale completions by match/request identity and isolate one failed workspace from the usable list.

Tests: with 100 ready matches, startup performs one list request plus one workspace's existing five requests; selecting B loads B once; a failed B leaves A and the list usable; switching rapidly B→C cannot replace C with late B data; comparison loads only the explicitly selected comparison.

Focused command: npm --prefix frontend test -- --run src/App.test.tsx src/utils/api.test.ts

No query-cache dependency, global store, server pagination redesign, or whole-app data framework.

### Task 17: R17a — Native keyboard equivalents for pitch actions

Files: frontend/src/components/TacticalPitch.tsx; frontend/src/App.tsx only for existing callbacks. Create frontend/src/components/TacticalPitch.test.tsx.

Keep the canvas as a visual surface with an accessible name/fallback description. Provide native button/select controls for current-frame player selection and labeled bounded numeric coordinate controls for circle/arrow placement, reusing onPlayerClick and onAnnotationCreate. Do not implement a second annotation algorithm or pretend tabIndex alone makes pointer coordinates accessible. Use explicit team+player identity and existing 0–100 pitch coordinates.

Tests: operate selection and both annotation types with keyboard-driven controls only; assert the same callback payload as pointer input; invalid/out-of-range coordinates do not submit; cancel/save returns sensible focus. Integrate with R12's single mode and pending-save behavior.

Focused command: npm --prefix frontend test -- --run src/components/TacticalPitch.test.tsx src/App.test.tsx

### Task 18: R17b — Make the existing calibration inputs the named keyboard path

Files: frontend/src/components/UploadCalibrationPanel.tsx; frontend/src/components/CalibrationFramePicker.tsx; frontend/src/components/UploadCalibrationPanel.test.tsx; frontend/src/components/CalibrationFramePicker.test.tsx.

No new calibration widget is needed. Label each existing numeric input with its corner and axis (for example “Top Left X”), associate visible keyboard instructions, and ensure the click preview references that equivalent path. Preserve source-image coordinate semantics and current validation.

Tests: find all eight inputs by their accessible names; set the four corners without pointer events; assert onPointChange and submitted calibration exactly match existing behavior. The preview remains an optional faster pointer path.

Focused command: npm --prefix frontend test -- --run src/components/UploadCalibrationPanel.test.tsx src/components/CalibrationFramePicker.test.tsx

## Explicit deferred gates, not silent omissions

### G-PRODUCT — One authorized real football acceptance after local closure

Maps O:I09 and is already required by the approved spec. Do not repeat or rewrite the historical fourth infrastructure smoke.

Prerequisites: both current plans pass; R04/R10's admission/authority outcomes are decided; a short approved clip and expected outputs are selected; exposed testing credentials are rotated; a fresh source commit/manifest/verifier receipt/image-context digest/preflight exists; the user explicitly authorizes the provider run.

Execute the current API upload → actual sealed worker → v2 import → coaching UI path once, observe an intermediate live update, inspect frames/analytics/events, and confirm sandbox deletion. Record source-bound evidence in docs/status/current.md and a distinct acceptance record chosen through the existing release process. No new smoke script/framework is prescribed.

### G-CAPACITY — Measure the remaining producer before designing batches or splits

Maps B:P1-runtime. CP-RESULTS Task 5 proves host-import behavior only; its 621,000-row/256 MiB target is not a worker-memory or full-video acceptance.

After G-PRODUCT, measure a representative match's worker peak RSS, host peak RSS, execution time, and peak staging disk using the current run_guerilla.py/video_pipeline.py path and existing worker instrumentation. Keep the approved 1,800-second execution / 10 GiB disk envelope. Record the actual available worker memory limit rather than inventing one.

If the producer exceeds a supported envelope, approve a separate bounded-producer design for backend/run_guerilla.py, backend/app/video_pipeline.py, backend/app/gpu_worker.py and their test counterparts test_run_guerilla.py/test_video_pipeline.py/test_gpu_worker.py. Preserve tracking, timestamps, possession/event continuity and output equivalence. Do not introduce speculative video splitting, row queues or chunk schedulers before the measurement identifies the limiting stage.

### G-NETWORK — No unauthenticated public/LAN deployment

Maps the conditional deployment portion of B:C2 and B:S1. R02/R04 close local filesystem/browser-origin boundaries, not multi-user authentication.

Before binding beyond the declared trusted local environment, choose the actual trusted serving edge and authorization mechanism, verify HTTP and websocket identity enforcement, allowed origins/Host, request limits and actual response security headers. Use an existing supported reverse proxy/auth boundary if available; no custom accounts/auth framework is authorized by this draft. Until that decision and tests are complete, keep the legacy review tools loopback-only and do not advertise the API as a public service.

### G-RETENTION — Decide history/artifact ownership before broad deletion

This gate owns optional B:P1/P9 and O artifact-dedup recommendations, not an unresolved High runtime fix. The backend report's 60k–90k historical-script estimate is a retention-dependent upper range, not a deletion manifest.

Require an exact kept/archived/deleted path list, active caller/import/CLI check, source-evidence retention check, model/artifact provenance, canonical duplicate mapping and recovery procedure. Preserve the tracked PT weights, recovery .nul manifests, archived checksums and source-bound evidence unless the retention owner explicitly approves otherwise. The measured 47.51 MiB duplicate estimate is working-tree bytes; Git already deduplicates identical blobs.

Do not convert 309 scripts into a new generic workflow engine. Archive only superseded units with no supported consumers. Removing source/source.tar from receipts requires a separately approved versioned protocol/attestation decision and is outside both current plans.

## Optional small deletion-only units

D01 — Packaging-only exclusion: modify pyproject.toml and backend/tests/test_documented_startup.py to exclude backend.tests* from built wheels while keeping source tests and required release/scripts. Rebuild/install outside checkout and assert API, lap and required release data still import. Estimated 3.22 MiB uncompressed installed test payload removed; repository tests remain.

D02 — Retired fail-closed tails: in the 13 exact recipe files listed under B:P2, retain public rejection signatures and independently imported analysis helpers; delete only statements after an unconditional retirement guard. Verify backend/tests/test_operational_docs.py plus affected recipe tests and imports. O measured 3,868 tail lines versus B's approximate 3,880; do not sum them. Any broader historical deletion goes through G-RETENTION.

D03 — Exact helper copies: use existing football_external_real_eval_chain_common.py readers/writers only where semantics and failure behavior truly match. Keep atomic overlay/admission code out of a bulk mechanical dedup. No neutral utility module is needed merely to rename an existing helper.

Do these as separate optional commits, not prerequisites that delay a security/data-loss fix. No global dependency removal is assumed; requests/httpx and optional Parquet changes must be separately verified against lock/image/release consumers.

## Adjacent non-High work remains visible

This draft is not a promise that all Medium/Low findings are fixed. The following already touch the high-priority units and should be reconciled without silently widening them:

- B:C5 and F:PERF-02's cadence/message visibility and caller cancellation are closed by CP-PROGRESS commits `5e8494cc`, `7d764721`, and `2a010ba8`: progress persists and renders, polling uses the two-second cadence, and upload/poll/workspace/unmount requests share an abortable lifecycle. No additional generic cancellation follow-up remains.
- B:C3 (post-publication durability outcome) is a design prerequisite for R05/R10 if sharing atomic writers; CP-RESULTS explicitly preserves existing _write_json behavior and does not independently close it.
- B:C7 duplicates O:I04 and is covered by R08. O:M02/M04 improve alongside their real execution/fixture boundaries.
- B:C4 terminal possession gaps; B:C6 bundle corruption/concurrency; B:C8 evidence renewal policy; B:C9 import-time GUI probing; B:P3-runtime archive-member buffering; B:P4-runtime search scaling remain separate Medium/Low follow-ups. Do not weaken evidence freshness to make acceptance run.
- F:COR-04/05/06/07/08/09/10/11/13, F:A11Y-02/03/04/05, F:SEC-02/03, F:PERF-03 and O:M01/M03/M05 remain as reported unless an R task's actual reviewed diff deliberately closes one. Core keyboard access in R17 must not be claimed to fix every modal/focus/status issue.
- B/F Ponytail estimates overlap O's helper/artifact/dead-code estimates; no combined savings total is justified.

## Validation and handoff rules

- No unit closes solely because a count threshold, source-string check, static formatter or mock declaration passes. The regression must exercise the actual boundary named in its audit finding.
- Review the real installed sidecar path, real HTTP handlers and real App rendering in the relevant units; retain controlled mocks only at expensive/external boundaries.
- For each completed task record its exact tests, fault vectors, changed files, residual assumptions and source commit. Refresh source-bound release evidence only after the intended source settles.
- Run integrated local verification with VERIFY_DAYTONA=0 ALLOW_DAYTONA_MUTATION=0 scripts/verify.sh after integrating the bounded units, not concurrently against a mutating SDD checkout.
- This draft's coverage check is structural: every High/Important ID has an owner or an explicit gate. It is not evidence that the proposed fixes have been implemented, accepted, or deployed.
