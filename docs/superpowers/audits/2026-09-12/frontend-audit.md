# Frontend full-sweep audit

Audit date: 2026-09-10 UTC
Scope: every tracked file under `frontend/` in the `batch-1-data-safety` worktree
Mode: read-only source review; this report is the only file created
Criteria: Ponytail deletion/simplification audit, followed separately by correctness, security, performance, and accessibility review

## Executive result

The frontend is small enough to keep direct and has a healthy type/lint/test baseline, but it has several concrete behavior gaps hidden by the current tests. The highest-confidence product defects are: enemy passes can be drawn as home-team network edges, review range/drawing state survives a match switch, the UI enables a cloud provider that its own runtime capabilities say is unavailable, and the initial coach tab points at a view that does not exist. The dominant scaling problem is eager hydration of every ready match (five requests and all frames per match), followed by 250 ms job polling that can issue 14,400 requests over the configured one-hour timeout without exposing intermediate progress.

No direct production dependency advisory or confirmed DOM-XSS sink was found. `npm audit --omit=dev` reports zero vulnerabilities. The full development tree reports 11 advisory-affected packages, including direct `vitest@3.2.4`; the risk is toolchain/dev-server exposure rather than shipped browser code. Browser security headers are not visible in this frontend and must be verified at the serving edge.

Verification performed without changing tracked frontend files:

- `npm test -- --reporter=dot`: **18 test files passed, 54 tests passed**.
- `npm run lint`: **passed, no findings**.
- `npx tsc -p tsconfig.app.json --noEmit --incremental false && npx tsc -p tsconfig.node.json --noEmit --incremental false`: **passed**.
- `npm audit --omit=dev --json`: **0 production vulnerabilities**.
- `npm audit --json`: **11 affected packages** (1 critical, 6 high, 3 moderate, 1 low); all are currently dev-only paths.
- `git status --short -- frontend` was clean before the report was written.

## Ranked cross-category findings

| Rank | ID | Area | Severity | Confidence | Summary |
|---:|---|---|---|---|---|
| 1 | COR-01 | Correctness | High | High | Passing-network aggregation ignores event team and can project enemy passes onto home-player IDs. |
| 2 | COR-02 | Correctness | High | High | Review range and drawing state survive match changes and can be saved against the wrong match/window. |
| 3 | COR-03 | Correctness | High | High | A local-only capability declaration still exposes an enabled Cloud control. |
| 4 | COR-12 | Correctness | High | High | App and review hook maintain separate drawing modes that diverge immediately after a successful save. |
| 5 | PERF-01 | Performance | High | High | Startup loads every ready match, all frames, and five endpoints per match in one all-or-nothing `Promise.all`. |
| 6 | SEC-01 | Security | High (toolchain) | High | Direct `vitest@3.2.4` is covered by a critical dev-server advisory and a moderate mocker path-traversal advisory. |
| 7 | COR-04 | Correctness | Medium | High | Initial coach tab is `events`, but the app renders only analysis/report/drills, producing a blank initial panel. |
| 8 | COR-05 | Correctness | Medium | High | Player hit-testing uses season/match average coordinates while markers are drawn at the current frame. |
| 9 | PERF-02 | Performance/UX | Medium | High | Upload polling is fixed at 250 ms, has no caller cancellation, and throws away progress/message updates. |
| 10 | A11Y-01 | Accessibility | High | High | Core pitch selection/drawing and calibration point placement are pointer-only canvas/video interactions. |
| 11 | A11Y-02 | Accessibility | Medium | High | Five modal surfaces lack dialog semantics, focus containment/restoration, and Escape handling. |
| 12 | COR-06 | Correctness | Medium | High | Player detail remains selected across match changes and combines the old player with new-match events. |
| 13 | COR-07 | Correctness | Medium | Medium | Native video play/pause controls do not update application playback state. |
| 14 | COR-08 | Correctness | Medium | High | A rejected bundle deletion escapes the click boundary as an unhandled promise rejection. |
| 15 | COR-09 | Correctness | Medium | High | Annotation/issue load failures are logged and replaced with empty lists without visible feedback. |
| 16 | COR-13 | Correctness | Medium | High | Every saved pitch annotation is drawn on every frame, ignoring its captured frame range. |
| 17 | SEC-02 | Security | Medium (conditional) | Medium | CSP/clickjacking/referrer protections are not present in frontend config; edge configuration is unknown. |
| 18 | A11Y-03 | Accessibility | Medium | High | Dashboard match bars and rows are clickable `div`s and cannot be operated by keyboard. |

## Import and caller trace

The complete runtime chain is:

```text
index.html
  -> src/main.tsx
     -> src/index.css
     -> src/App.tsx
        -> components/{AnnotationList,DrawingToolbar,ReviewToolbar,TacticalPitch,
                       CoachInsights,DashboardPanel,DemoMatchIssuePanel,MatchVideoPanel,
                       PlayerDetailPanel,StatsPanel,TeamSelectionBanner,Timeline,
                       TrustCropPanel,UploadCalibrationPanel}
        -> hooks/useCoachAnalysis
        -> features/review/useReviewSurface
        -> utils/{analytics,api,uploadConfig,uploadErrors,videoSync}

CoachInsights -> SaveBundleButton -> /api/bundles
CoachInsights -> BundleListPanel -> hooks/useReviewBundles -> utils/api
DashboardPanel -> hooks/useDashboardData -> utils/api
UploadCalibrationPanel -> CalibrationFramePicker -> utils/calibrationPoints
MatchVideoPanel -> utils/videoSync
TacticalPitch -> utils/analytics
all domain modules -> types/index.ts
```

Per-module direct production callers/importers:

| Module | Production caller(s) |
|---|---|
| `src/main.tsx` | Vite entry from `index.html` |
| `src/App.tsx` | `src/main.tsx` |
| `src/index.css` | `src/main.tsx` |
| `src/components/AnnotationList.tsx` | `src/App.tsx` |
| `src/components/BundleListPanel.tsx` | `src/components/CoachInsights.tsx` |
| `src/components/CalibrationFramePicker.tsx` | `src/components/UploadCalibrationPanel.tsx` |
| `src/components/CoachInsights.tsx` | `src/App.tsx`; its playlist helper is also imported by its test |
| `src/components/DashboardPanel.tsx` | `src/App.tsx` |
| `src/components/DemoMatchIssuePanel.tsx` | `src/App.tsx` |
| `src/components/DrawingToolbar.tsx` | `src/App.tsx` |
| `src/components/MatchVideoPanel.tsx` | `src/App.tsx` |
| `src/components/PlayerDetailPanel.tsx` | `src/App.tsx` |
| `src/components/ReviewToolbar.tsx` | `src/App.tsx` |
| `src/components/SaveBundleButton.tsx` | `src/components/CoachInsights.tsx` |
| `src/components/StatsPanel.tsx` | `src/App.tsx` |
| `src/components/TacticalPitch.tsx` | `src/App.tsx`; `DrawingToolbar` imports only its `DrawingMode` type |
| `src/components/TeamSelectionBanner.tsx` | `src/App.tsx` |
| `src/components/Timeline.tsx` | `src/App.tsx` |
| `src/components/TrustCropPanel.tsx` | `src/App.tsx` |
| `src/components/UploadCalibrationPanel.tsx` | `src/App.tsx` |
| `src/features/review/useReviewSurface.ts` | `src/App.tsx` |
| `src/hooks/useCoachAnalysis.ts` | `src/App.tsx` |
| `src/hooks/useDashboardData.ts` | `src/components/DashboardPanel.tsx` |
| `src/hooks/useReviewBundles.ts` | `src/components/BundleListPanel.tsx` |
| `src/utils/analytics.ts` | `src/App.tsx`, `src/components/TacticalPitch.tsx`, unit test |
| `src/utils/api.ts` | `src/App.tsx`, `CoachInsights`, `SaveBundleButton` bypasses it, three hooks, `TrustCropPanel`, unit tests |
| `src/utils/calibrationPoints.ts` | `CalibrationFramePicker`, unit test |
| `src/utils/uploadConfig.ts` | `src/App.tsx`, `CalibrationFramePicker` (type), `UploadCalibrationPanel` (type), unit test |
| `src/utils/uploadErrors.ts` | `src/App.tsx`, unit test |
| `src/utils/videoSync.ts` | `src/App.tsx`, `MatchVideoPanel`, unit test |
| `src/types/index.ts` | All domain components/hooks/utilities; duplicate coach types remain in `useCoachAnalysis.ts` |

Important non-callers/dead paths discovered by the trace:

- `buildShotMarkers` is imported only by `analytics.test.ts`; runtime consumes backend-provided `analytics.shots` (`api.ts:167-184`, `App.tsx:270-274`).
- `useReviewBundles` exposes `selectedBundle`, `loadBundle`, `addBundle`, `editBundle`, and `clearError`, but its only production caller destructures none of them (`BundleListPanel.tsx:11-15`).
- `useDashboardData` stores/returns opponent rollups, player trend snapshots, and an external `setTrends`, but `DashboardPanel.tsx:26-28` uses none of them.
- `resetReviewSurface` is returned but not called anywhere (`useReviewSurface.ts:55-59,356-375`). It should become an internal match-change reset rather than simply being deleted.
- `supportsCloudProvider` is returned but ignored (`useCoachAnalysis.ts:77,137-150`); this is a correctness bug, not a safe deletion candidate.
- `src/assets/react.svg` has no importer.

## Correctness findings

### COR-01 — Enemy passes can be drawn as home-team edges

- Severity: **High**
- Confidence: **High**
- Location: `src/utils/analytics.ts:99-140`; caller `src/App.tsx:265-268`; renderer `src/components/TacticalPitch.tsx:183-195`
- Evidence: `buildPassingNetwork` accepts every `event.type === 'pass'` without checking `event.team`, and its edge model contains no team. `resolvePassingNetworkEdgesForFrame` then resolves both endpoints exclusively from `frame.My_Team`.
- Impact: if enemy and home track IDs overlap, an enemy pass is rendered as a blue home-team connection; otherwise enemy edges silently disappear. Aggregate weights can therefore be tactically false.
- Smallest fix: if the overlay is intended to be home-team-only, require `event.team === 'my_team'` during aggregation and add a regression test with overlapping enemy IDs. If both teams are intended, add `team` to `PassNetworkEdge` and resolve against the matching frame collection.

### COR-02 — Match switches retain review timing and partial drawing state

- Severity: **High**
- Confidence: **High**
- Location: `src/features/review/useReviewSurface.ts:45-59,71-127,135-148,234-270,356-375`; switch callers `src/App.tsx:327-345,456-466`
- Evidence: match changes reload annotations/issues, but never clear `reviewRange`, `reviewMode`, or `pendingArrowStart`. The only reset function is merely returned and has no caller. `buildReviewTiming` also clamps only the lower bound and does not cap frames to the new `matchData.length`.
- Impact: an old range or arrow start can be saved to the next match, potentially with out-of-range frame IDs and timestamps from the new match/fallback timestamp.
- Smallest fix: reset the three review-only states in an effect keyed by `activeMatchId`; cap timing to the available frame range. Keep the reset internal and remove the unused returned method.
- Test: render the hook, set a range/start an arrow, rerender with a different match ID and shorter frame list, then assert null placement/range and in-bounds save payload.

### COR-03 — Cloud analysis is enabled while capabilities are local-only

- Severity: **High**
- Confidence: **High**
- Location: `src/App.tsx:117-128,839-850`; `src/hooks/useCoachAnalysis.ts:71,77-81,96-135,137-150`
- Evidence: `runtimeCapabilities.analysisProviders` is hard-coded to `['local']`, yet the Cloud button is always enabled and calls `setLlmProvider('cloud')`. The hook computes `supportsCloudProvider` but App never reads it.
- Impact: users can select an unsupported provider, causing analysis/upload failures and contradicting the local-first status shown in the UI.
- Smallest fix: disable or omit Cloud unless `coach.supportsCloudProvider`; source real capabilities before advertising remote behavior.
- Test: local-only capabilities should expose a disabled/absent Cloud control and should never call analysis with `cloud`.

### COR-04 — Initial coach tab targets a nonexistent view

- Severity: **Medium**
- Confidence: **High**
- Location: `src/hooks/useCoachAnalysis.ts:46,69-75`; `src/App.tsx:853-929`
- Evidence: initial `activeTab` is `'events'`; App offers and renders only `'analysis'`, `'report'`, and `'drills'`. Initial match loading does not call `resetAnalysis`, so none of the content branches match.
- Impact: after first load the Tactical Brain content area is blank until the user selects a tab.
- Smallest fix: remove `'events'` from `CoachAnalysisTab` and initialize to `'analysis'`.
- Test: render the app/hook initial state and assert the analysis surface is selected.

### COR-12 — Duplicate drawing-mode state diverges after the first successful save

- Severity: **High**
- Confidence: **High**
- Location: App state/handlers `src/App.tsx:138,293-325,659-681,814-819`; hook completion `src/features/review/useReviewSurface.ts:234-270,341-354`
- Evidence: starting a tool sets both `App.drawingMode` and `review.reviewMode`. A successful circle/arrow save clears only the hook's `reviewMode`; App continues passing its stale non-null mode to the toolbar and canvas. The next canvas action enters `handleDrawingAnnotation`, sees `!review.reviewMode`, and returns without saving.
- Impact: after one successful drawing, the UI still looks active and accepts pointer gestures, but silently discards them until the user cancels or reselects a tool.
- Smallest fix: remove App's duplicate `drawingMode` state and render/pass `review.reviewMode` as the single source of truth; keep App handlers as thin calls into the hook.
- Test: complete one annotation, assert the tool is no longer active, then reselect and save another without an intervening manual cancel.

### COR-05 — Player marker hit-testing uses the wrong coordinates

- Severity: **Medium**
- Confidence: **High**
- Location: draw at `src/components/TacticalPitch.tsx:216-285`; hit-test at `src/components/TacticalPitch.tsx:372-395`; profile coordinates built at `src/utils/analytics.ts:376-455`
- Evidence: markers are painted from current `frameData` positions, but click distance is calculated against `PlayerProfile.avgX/avgY` over all match frames.
- Impact: clicking a visible player often does nothing or opens a different nearby player's detail, especially for players far from their average position.
- Smallest fix: hit-test current-frame home and enemy markers first, then look up the corresponding profile by `(team, playerId)`.
- Test: provide a profile whose average differs from its current marker and click the current position.

### COR-06 — Selected player leaks across match changes

- Severity: **Medium**
- Confidence: **High**
- Location: `src/App.tsx:134,327-345,456-466,686-700`
- Evidence: both workspace-load and selector paths reset frame/events/analysis but do not clear `selectedPlayer`. The open panel then receives the old `player` and `activeMatch.backendEvents` from the new match.
- Impact: the detail panel can present a stale identity with event evidence from another match.
- Smallest fix: `setSelectedPlayer(null)` in the shared workspace/match transition path.

### COR-07 — Native video controls and app playback state diverge

- Severity: **Medium**
- Confidence: **Medium**
- Location: `src/components/MatchVideoPanel.tsx:22-59,63-83`; `src/App.tsx:114,286,636-644,702-712`
- Evidence: the video exposes native `controls` and reports only `onTimeUpdate`; there is no `onPlay`, `onPause`, or `onEnded` callback to synchronize `App.isPlaying`.
- Impact: the timeline play icon and app logic can say paused while native video plays, or say playing after native pause/end.
- Smallest fix: report media play/pause/end state to App (or remove native play/pause affordances and keep a single controller).
- False-positive note: current frame synchronization often masks this because `timeupdate` still advances the frame; the state/UI divergence remains.

### COR-08 — Bundle delete failures escape as unhandled rejections

- Severity: **Medium**
- Confidence: **High**
- Location: `src/hooks/useReviewBundles.ts:97-114`; boundary `src/components/BundleListPanel.tsx:37-44,141-147`
- Evidence: `removeBundle` records an error and rethrows. `handleDelete` has only `try/finally`, and the click intentionally discards the returned promise with `void`.
- Impact: a failed delete creates an unhandled promise rejection in addition to the hook error state; monitoring can report false crashes and strict runtimes/tests may fail.
- Smallest fix: catch at `handleDelete` (the hook already owns display state), or stop rethrowing from the hook contract. Add a rejected-delete component test.

### COR-09 — Review list load failures are indistinguishable from empty data

- Severity: **Medium**
- Confidence: **High**
- Location: `src/features/review/useReviewSurface.ts:71-127`; visible error contract at `:16-25`
- Evidence: both fetch catches log and replace state with `[]` but never call `setLoadError`, despite save/delete failures using that existing surface.
- Impact: operators may believe a match has no annotations/issues and continue reviewing on incomplete data.
- Smallest fix: set a useful load error for the current match; clear it only after a successful relevant load according to the app's existing error convention. Tests currently cover save failures only (`useReviewSurface.test.tsx:41-116`).

### COR-13 — Saved pitch annotations ignore their frame range

- Severity: **Medium**
- Confidence: **High**
- Location: `src/components/TacticalPitch.tsx:298-326`; callers `src/App.tsx:646-662,666-682`
- Evidence: App passes the complete match annotation list and the canvas loops over every saved arrow/circle without comparing `frameStart`/`frameEnd` with `currentFrame`.
- Impact: annotations captured for one moment remain painted throughout playback, creating false tactical context and increasing clutter as the review list grows.
- Smallest fix: filter `review.annotations` in App to annotations whose stored range contains the current frame before passing them to the pitch.
- Test: render two frame-scoped annotations and assert only the annotation covering the current frame is drawn.

### COR-10 — Trust-crop save errors are labeled as load failures

- Severity: **Low**
- Confidence: **High**
- Location: `src/components/TrustCropPanel.tsx:39-43,66-85,118-121`
- Evidence: the save catch writes the same `error` used by the fixed message `Failed to load trust crops:`.
- Impact: a save failure tells the user that loading failed and hides the already-loaded list.
- Smallest fix: separate `loadError` and `saveError`, or render a neutral operation error without suppressing loaded data.

### COR-11 — Invalid date fallback never runs for ordinary invalid dates

- Severity: **Low**
- Confidence: **High**
- Location: `src/components/DashboardPanel.tsx:18-24`; duplicate at `src/components/BundleListPanel.tsx:46-56`
- Evidence: `new Date(badValue).toLocaleDateString(...)` normally returns `"Invalid Date"`; it does not throw, so the `try/catch` does not restore the source string.
- Impact: malformed API dates leak an unhelpful literal into both panels.
- Smallest fix: parse once and test `Number.isNaN(date.getTime())` before formatting; share only if duplication remains material.

## Security findings

### SEC-01 — Advisory-affected Vitest/toolchain tree

- Rule ID: **REACT-SUPPLY-001**
- Severity: **High (development toolchain; upstream advisory rates one path Critical)**
- Location: `frontend/package.json:18-37`; lock metadata for `vitest@3.2.4`, `@vitest/mocker@3.2.4`, `ws@8.19.0`, `@babel/core@7.29.0`, `@humanfs/node@0.16.7`, `baseline-browser-mapping@2.10.0`, `brace-expansion@1.1.12`, `browserslist@4.28.1`, `flatted@3.3.3`, `js-yaml@4.1.1`, and `minimatch@3.1.3`
- Evidence: `npm audit --json` reports 11 affected packages: 1 critical, 6 high, 3 moderate, 1 low. Direct `vitest@3.2.4` is affected by GHSA-5xrq-8626-4rwp (arbitrary file read/execution when the Vitest UI server listens) and GHSA-82fw-gwwq-j7x9 (mocker redirect path traversal). A fix is reported available. `npm audit --omit=dev --json` reports zero.

  ```json
  "vitest": "^3.2.4"
  ```

  Lockfile resolution: `node_modules/vitest.version = 3.2.4`, `node_modules/@vitest/mocker.version = 3.2.4`.

- Impact: an exposed test/UI server or hostile test/mock input can reach local files or code paths in developer/CI environments. These packages are not in the production browser dependency result.
- Fix: update Vitest and refresh the lockfile to fixed versions, then rerun tests and both audit modes. Address transitive fixes through direct tool upgrades rather than pinning nested packages ad hoc.
- Mitigation: never expose Vite/Vitest development servers to untrusted networks; run CI from trusted test sources with least-privilege filesystem credentials.
- False-positive notes: the repository script is `vitest run`, not Vitest UI, and all reported affected nodes are dev-only in this lockfile. This sharply reduces deployed-app risk but does not erase developer/CI risk.

### SEC-02 — Browser security headers are not visible in frontend configuration

- Rule ID: **REACT-CSP-001 / REACT-HEADERS-001**
- Severity: **Medium (conditional on deployment edge)**
- Location: `frontend/index.html:1-13`; `frontend/vite.config.ts:6-32`
- Evidence: the app shell contains charset, favicon, viewport, title, and a same-origin module script, but no CSP. Vite config contains development proxies/build/test settings and no production header policy.

  ```html
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <script type="module" src="/src/main.tsx"></script>
  ```

- Impact: if the deployment server/edge also omits these headers, the app lacks defense-in-depth against injection, framing/clickjacking, MIME confusion, and excess referrer disclosure.
- Fix: set CSP, `frame-ancestors`/`X-Frame-Options`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, and an appropriate `Permissions-Policy` at the production server/edge. Prefer header delivery over a meta CSP.
- Mitigation: current React rendering uses JSX escaping and no dangerous HTML sink was found, which materially lowers XSS likelihood.
- False-positive notes: headers may be configured by the backend/CDN outside `frontend/`; verify actual production response headers before treating this as confirmed missing protection.

### SEC-03 — Conditional CSRF check for future cookie authentication

- Rule ID: **REACT-CSRF-001**
- Severity: **Low / conditional**
- Location: state-changing calls in `src/utils/api.ts:101-118,145-153,223-237,252-280,302-320,342-360`; direct duplicate in `src/components/SaveBundleButton.tsx:64-76`
- Evidence: same-origin POST/PATCH/PUT/DELETE calls contain no CSRF header/token. Fetch sends same-origin cookies by default if such cookies exist.

  ```ts
  fetch('/api/bundles', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
  ```

- Impact: only if the backend authenticates these actions with ambient cookies, another origin could attempt state-changing requests.
- Fix: if cookie auth exists, add a server-validated CSRF strategy and centralize state-changing requests; keep SameSite as defense in depth.
- Mitigation: fixed same-origin request paths prevent arbitrary-origin credential exfiltration.
- False-positive notes: no frontend auth/session flow, token storage, `credentials: 'include'`, or authorization gate is present. If the app is unauthenticated/local-only or uses explicit authorization headers, this is not a CSRF vulnerability.

Security-negative evidence (checked, no finding):

- No `dangerouslySetInnerHTML`, `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `DOMParser`, `eval`, `new Function`, string timer, dynamic script creation, storage token, service worker, `postMessage`, untrusted redirect, or external third-party script was found.
- API/LLM/user note text is interpolated through React and escaped.
- Both export windows use `_blank` with `noopener,noreferrer` (`CoachInsights.tsx:178-184,295-301`); the target is a same-origin path built from the active match.
- Uploaded video is previewed through a browser-created blob URL and is not injected as HTML/SVG; server-side upload validation remains outside this frontend-only review.
- The lockfile is present at version 3 and captures 362 packages; only `esbuild` and optional `fsevents` declare install scripts in lock metadata.

## Performance findings

### PERF-01 — Eager, all-or-nothing hydration scales as five requests plus all frame data per match

- Severity: **High**
- Confidence: **High**
- Location: `src/App.tsx:194-221`; `src/utils/api.ts:139-189`
- Evidence: startup filters every ready match and executes `Promise.all(readyMatches.map(fetchMatchWorkspace))`. Each workspace performs five concurrent requests (detail, frames, analytics, events, benchmark), maps every frame, and all `MatchEntry` objects retain those frames in browser memory.
- Impact: `N` ready matches cause `5N + 1` startup requests, high JSON/heap cost, and delayed first paint. One failed workspace rejects the outer `Promise.all`, so otherwise healthy matches are not shown.
- Smallest reliable fix: load the list plus the initially selected workspace; lazy-load/cache another workspace only when selected or compared. If eager loading is temporarily retained, use per-match settlement so one failure does not blank all results.
- Tests: assert startup fetch count is independent of total listed matches; assert selecting an unloaded match hydrates it once and a single failed match leaves other matches usable.

### PERF-02 — Fixed 250 ms polling can issue 14,400 requests and hides progress

- Severity: **Medium**
- Confidence: **High**
- Location: `src/utils/api.ts:121-124,201-220`; caller `src/App.tsx:371-393`
- Evidence: the default interval is 250 ms and timeout is 60 minutes. The caller supplies no `AbortSignal`, ignores every intermediate `ProcessingJob.progress/message`, and displays static `Processing match...`.
- Impact: long CPU/GPU jobs generate four requests per second per browser, waste server/client capacity, cannot be cancelled on workflow exit, and provide no live feedback despite receiving progress fields.
- Smallest reliable fix: accept an `onProgress(job)` callback and update `jobStatus`; poll at 1–2 seconds with capped backoff, or use the existing `/ws` proxy when a stable job event contract is available. Create/abort an `AbortController` for the active upload on unmount/replacement.
- Failure/cleanup tests: progress callback order, abort stops further fetches/timers, terminal failed/completed behavior, timeout, and timer cleanup with fake timers.

### PERF-03 — Stable match-level leader work repeats during frame playback

- Severity: **Low**
- Confidence: **High**
- Location: `src/components/StatsPanel.tsx:81-105`; caller `src/App.tsx:113-114,276-284,777-786`
- Evidence: every App frame update rerenders `StatsPanel`, which clones and sorts `playerProfiles` three times to select leaders even though profiles change only when the active workspace changes.
- Impact: normally small (roughly one squad), but it is needless work at playback frequency and compounds with canvas drawing.
- Smallest fix: compute the three leaders once alongside `playerProfiles` or memoize the result by the `playerProfiles` reference. Do not add a generalized selector layer.

## Accessibility findings

### A11Y-01 — Core pitch and calibration workflows are pointer-only

- Severity: **High**
- Confidence: **High**
- Location: `src/components/TacticalPitch.tsx:48-86,372-410`; `src/components/CalibrationFramePicker.tsx:40-71`
- Evidence: the canvas and calibration video depend on mouse/click coordinates, have no keyboard handlers, focusability, accessible name/instructions, or equivalent coordinate controls associated with the visual action. The canvas also has no fallback text.
- Impact: keyboard-only, switch-device, and screen-reader users cannot select players, place tactical annotations, or click-to-calibrate.
- Smallest fix: keep the existing numeric calibration inputs as the keyboard path but give each an explicit corner/axis label and associate instructions. Give the pitch a named focus target and provide keyboard-operable player/annotation alternatives (for example, a compact player list and coordinate inputs), rather than attempting to make freehand pointer coordinates magically keyboard-native.

### A11Y-02 — Modal surfaces are visual overlays, not accessible dialogs

- Severity: **Medium**
- Confidence: **High**
- Location: issue overlay `src/App.tsx:935-962`; dashboard `src/components/DashboardPanel.tsx:29-43`; playlists `src/components/BundleListPanel.tsx:58-72`; save dialog `src/components/SaveBundleButton.tsx:99-190`; trust crops `src/components/TrustCropPanel.tsx:88-109`
- Evidence: none uses `role="dialog"`, `aria-modal="true"`, an associated accessible title, focus containment/restoration, or Escape handling. Background content remains in the focus order.
- Impact: screen-reader context is unclear and keyboard focus can move behind the overlay or be lost after close.
- Smallest fix: add dialog semantics/titles and a small per-dialog focus/Escape lifecycle using existing React/browser APIs; restore focus to the opener. No dependency is required.

### A11Y-03 — Dashboard selection uses non-interactive `div`s

- Severity: **Medium**
- Confidence: **High**
- Location: `src/components/DashboardPanel.tsx:126-151,161-183`
- Evidence: chart columns and match rows attach `onClick` to `div`s with no `button`, `tabIndex`, keyboard handler, or accessible label. The chart conveys values primarily through height/color and `title`.
- Impact: keyboard users cannot select a match; screen-reader users get weak/no actionable chart semantics.
- Smallest fix: use native buttons for selectable bars/rows, include match name and possession in the accessible name, and preserve the existing visual layout.

### A11Y-04 — Several controls lack programmatic names/state

- Severity: **Low**
- Confidence: **High**
- Location: match/comparison selects `src/App.tsx:507-535`; overlay toggles `:735-751`; calibration numeric inputs `src/components/UploadCalibrationPanel.tsx:108-131`; drawing toggles `src/components/DrawingToolbar.tsx:10-47`; event markers `src/components/Timeline.tsx:101-115`
- Evidence: header selects have no labels; x/y inputs rely on placeholders and a sibling paragraph; stateful overlay/drawing buttons omit `aria-pressed`; small marker buttons contain no text (only `title`).
- Impact: control purpose and toggle state are ambiguous to assistive technology, and marker targets are difficult to discover/use.
- Smallest fix: add associated labels/`aria-label`, `aria-pressed`, and explicit event-marker names; keep native elements.

### A11Y-05 — Async state and errors are not announced

- Severity: **Low**
- Confidence: **High**
- Location: upload/status `src/App.tsx:577-592`; review saves `src/components/ReviewToolbar.tsx:38-70`, `DemoMatchIssuePanel.tsx:126-153`; dashboard/bundle/trust loading and errors in their panels
- Evidence: dynamic loading, success/failure, and disabled transitions have no `role="status"`, `role="alert"`, or `aria-live` region.
- Impact: screen-reader users may receive no indication that a save started, failed, or completed.
- Smallest fix: make visible status/error containers polite status or assertive alert regions and use saving button text where already available.

## Ponytail audit — ranked cuts

These are deletion/simplification opportunities only. Correctness recommendations above take precedence where a symbol currently looks unused because it was never wired.

1. `[delete][yagni] frontend/src/hooks/useReviewBundles.ts:10-21,26-29,46-95,103-118,126-137 + frontend/src/utils/api.ts:247-271 + frontend/src/types/index.ts:312-317` — delete unused selected-bundle/load/add/edit/clear surface and the now-dead fetch/update API paths; the only caller needs list/refresh/delete. **Estimated: -75 to -90 lines; high confidence.**
2. `[delete][yagni] frontend/src/utils/analytics.ts:143-185 + frontend/src/utils/analytics.test.ts:59-97` — delete `buildShotMarkers`; production already consumes backend `analytics.shots`, so this function is test-only parallel logic. **Estimated: -80 to -83 lines; high confidence.**
3. `[delete] frontend/README.md:1-73 + frontend/src/assets/react.svg:1` — replace the untouched Vite template README with a short project-specific run/test note and remove the unimported React logo. **Estimated: -60 lines and 7 KB asset; high confidence.**
4. `[shrink] frontend/src/hooks/useCoachAnalysis.ts:3-44 + frontend/src/types/index.ts:479-533` — import the shared `TacticalReport`/`DrillResponse` definitions instead of maintaining structurally duplicated interfaces. **Estimated: -36 to -38 lines; high confidence.**
5. `[native][shrink] frontend/src/App.tsx:247-258 + frontend/src/components/Timeline.tsx:15-19,51-66,170-183 + frontend/src/components/CoachInsights.tsx:75-83,111-121` — replace the window-global `CustomEvent('add-event')` bridge with direct React callbacks through the two real call paths. **Estimated: -8 to -15 lines and less global coupling; medium confidence.**
6. `[delete][yagni] frontend/src/hooks/useDashboardData.ts:9-10,24-25,47` — stop storing/returning opponent rollups, player snapshots, and public `setTrends` until `DashboardPanel` consumes them. **Estimated: -7 to -9 lines; high confidence.**
7. `[stdlib][shrink] frontend/src/components/SaveBundleButton.tsx:64-76 + frontend/src/utils/api.ts:252-260` — call the existing `createBundle` API helper instead of duplicating `fetch`, response checking, and JSON parsing. **Estimated: -7 to -9 lines; high confidence.**
8. `[delete] frontend/src/types/index.ts:33-41` — remove `RawRow`; it has no caller/importer. **Estimated: -9 lines; high confidence.**
9. `[delete] frontend/package.json:20,26,32` — remove direct `@testing-library/jest-dom` (never imported/configured), `autoprefixer` (no PostCSS config/use), and direct `postcss` (no direct use; remains transitively available where Tailwind needs it), then refresh the lockfile. **Estimated: -3 direct dependency declarations; high confidence for jest-dom/autoprefixer, medium-high for direct postcss pending a clean `npm ci && npm run build`.**
10. `[shrink] frontend/src/App.tsx:138,309-325,659-681,814-819` — remove the duplicate App drawing-mode state and use `review.reviewMode` as the existing single source of truth (COR-12). **Estimated: -4 to -7 net lines; high confidence.**
11. `[shrink] frontend/src/features/review/useReviewSurface.ts:55-59,356-375` — after moving match-change reset behavior into an internal effect (COR-02), stop exporting `resetReviewSurface`, which has no caller. **Estimated: -1 to -2 net lines after the correctness fix; high confidence.**

Do not delete `supportsCloudProvider`: wire it into the Cloud control (COR-03). Do not simply delete review reset behavior: internalize it on match change (COR-02).

**net: -300 lines, -3 deps possible**

## Complete coverage manifest

### Fully inspected source and tests (49/49 tracked TS/TSX files)

```text
frontend/src/App.test.tsx
frontend/src/App.tsx
frontend/src/components/AnnotationList.tsx
frontend/src/components/BundleListPanel.test.tsx
frontend/src/components/BundleListPanel.tsx
frontend/src/components/CalibrationFramePicker.test.tsx
frontend/src/components/CalibrationFramePicker.tsx
frontend/src/components/CoachInsights.test.tsx
frontend/src/components/CoachInsights.tsx
frontend/src/components/DashboardPanel.tsx
frontend/src/components/DemoMatchIssuePanel.test.tsx
frontend/src/components/DemoMatchIssuePanel.tsx
frontend/src/components/DrawingToolbar.tsx
frontend/src/components/MatchVideoPanel.test.tsx
frontend/src/components/MatchVideoPanel.tsx
frontend/src/components/PlayerDetailPanel.tsx
frontend/src/components/ReviewToolbar.test.tsx
frontend/src/components/ReviewToolbar.tsx
frontend/src/components/SaveBundleButton.tsx
frontend/src/components/StatsPanel.test.tsx
frontend/src/components/StatsPanel.tsx
frontend/src/components/TacticalPitch.tsx
frontend/src/components/TeamSelectionBanner.test.tsx
frontend/src/components/TeamSelectionBanner.tsx
frontend/src/components/Timeline.tsx
frontend/src/components/TrustCropPanel.test.tsx
frontend/src/components/TrustCropPanel.tsx
frontend/src/components/UploadCalibrationPanel.test.tsx
frontend/src/components/UploadCalibrationPanel.tsx
frontend/src/features/review/useReviewSurface.test.tsx
frontend/src/features/review/useReviewSurface.ts
frontend/src/hooks/useCoachAnalysis.ts
frontend/src/hooks/useDashboardData.ts
frontend/src/hooks/useReviewBundles.ts
frontend/src/main.tsx
frontend/src/types/index.ts
frontend/src/utils/analytics.test.ts
frontend/src/utils/analytics.ts
frontend/src/utils/api.test.ts
frontend/src/utils/api.ts
frontend/src/utils/calibrationPoints.test.ts
frontend/src/utils/calibrationPoints.ts
frontend/src/utils/uploadConfig.test.ts
frontend/src/utils/uploadConfig.ts
frontend/src/utils/uploadErrors.test.ts
frontend/src/utils/uploadErrors.ts
frontend/src/utils/videoSync.test.ts
frontend/src/utils/videoSync.ts
frontend/vite.config.ts
```

### Fully inspected config, shell, style, and supporting text (9 files)

```text
frontend/.gitignore
frontend/README.md
frontend/eslint.config.js
frontend/index.html
frontend/package.json
frontend/src/index.css
frontend/tsconfig.app.json
frontend/tsconfig.json
frontend/tsconfig.node.json
```

### Inspected data/assets and controlled skips (4 files)

| File | Coverage | Skip/reason |
|---|---|---|
| `frontend/package-lock.json` | Root manifest, lockfile version, package count, exact relevant versions, install-script flags, direct/transitive dependency paths, and live `npm audit` metadata inspected. | Full 5,138-line textual review intentionally skipped per request; lockfile contents were used only for dependency analysis. |
| `frontend/public/meci_data.json` | Entire file parsed successfully; 28,413 bytes, 300 records; sampled/verified keys `Frame_ID`, `Timestamp`, `Entity_Type`, `Track_ID`, `X`, `Y`, `Conf`. | Row-by-row semantic sports-data review skipped because this is a generated/demo data fixture, not source, test, or config. |
| `frontend/public/vite.svg` | Entire static SVG inspected; referenced only as the favicon from `index.html:5`; no script/foreign content. | No skip. |
| `frontend/src/assets/react.svg` | Entire static SVG inspected; import search confirms no caller. | No behavioral review applicable; static unused template asset. |

No tracked frontend source, test, or configuration file was skipped. Counts: 62 tracked files total; 49 TS/TSX, 1 CSS, 1 JS, 6 JSON (including lockfile and demo data), 1 HTML, 1 Markdown, 1 gitignore, and 2 SVG assets. Reviewed code/config/test text excluding the lockfile totals approximately 8,353 physical lines (the one-line JSON/SVG assets additionally contain their full byte content).

## Test coverage gaps implied by findings

- No real App behavior test covers initial loading, match switching, provider capability gating, player reset, upload progress, or partial workspace failure; `App.test.tsx` tests only the array helper.
- No `TacticalPitch` component test exists for passing-team separation, frame-position hit-testing, annotation frame visibility, resizing, or keyboard alternative.
- Analytics tests omit enemy-pass ID collision, `computeHeatmap`, and `computeSpeedsForFrame` despite both being production callers.
- `useReviewSurface` tests cover save errors only; load errors, match resets, stale requests, delete failures, timing bounds, and drawing persistence are uncovered.
- `BundleListPanel` tests cover playlist loading only; delete rejection/duplicate actions and modal keyboard behavior are uncovered.
- No tests cover `useCoachAnalysis`, `useDashboardData`, `useReviewBundles`, `DashboardPanel`, `Timeline`, `DrawingToolbar`, `AnnotationList`, `PlayerDetailPanel`, or `SaveBundleButton` directly.
- Accessibility assertions are absent; tests mostly query native roles where convenient and do not exercise keyboard navigation, dialog focus, live regions, or canvas alternatives.
