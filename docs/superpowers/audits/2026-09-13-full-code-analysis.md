# Full code analysis — 2026-09-13

Audited source: `3cf566d6`, branch `recovery-history-batch-current`. Method: Superpowers flow tracing, independent backend/frontend/pipeline review, targeted reproductions, and verification; Ponytail review for proven deletions and reuse. This is an analysis, with no production fixes applied.

**Outcome: 23 findings — 5 P1, 17 P2, 1 P3.** The most consequential problems affect the promoted detector, calibration, directional analytics, tracking assignments, and frontend stability. Fix these before treating current analytics as product acceptance evidence. P1 means high impact on a supported flow; P2 means a material correctness, reliability, or accessibility defect; P3 means lower-impact consistency debt. These are current findings, not a claim that all were introduced since the previous audit.

**Verification and scope**

| Check | Fresh result |
|---|---|
| Tracked-tree inventory | 4,822 paths; all 666 tracked Python files parsed successfully |
| `python3 -m pytest -q backend/tests` | **3,477 passed, 1 failed, 1 skipped**, 298.19 seconds |
| Isolated rerun of the failed backend test | Same failure: installed Daytona 0.211.2, expected pinned 0.207.0 |
| `python3 -m pytest -q research-addon/tests` | **100 passed** |
| `npm --prefix frontend test -- --run` | **115 passed**, 22 files |
| Frontend lint and production build | Passed; build includes `tsc -b` |
| `npm --prefix frontend audit --omit=dev --audit-level=high` | 0 vulnerabilities reported |
| Targeted frontend reproductions | 7 checks confirmed current broken behavior |
| Targeted API/storage reproductions | Confirmed failed-update persistence, invalid-config 500, orphan issue, report injection, and abandoned websocket polling |
| Targeted pipeline reproductions | Confirmed release profile mismatch, dropped acquisition option, mirrored shot loss, sample-dependent sprint count, and calibration scale mismatch |

The failing test is `backend/tests/test_operational_docs.py:138`, `test_daytona_runbook_has_credential_free_pinned_readiness_command`. This is an environment/pin mismatch, not evidence of a new application regression. The global environment was not changed to conceal it. Consequently this audit does **not** claim the full verifier passes or issue a new release receipt. The pre-existing untracked `.verification/` directory was preserved.

Semantic review covered upload/admission → dispatch → local/remote processing → result import → analytics/storage → frontend review, plus the research addon, packaging, CI, and verification scripts. The tracked source includes approximately 119,000 lines across 311 operational scripts. Script families were inventoried and sampled, including an AST duplicate-function scan; every historical script and every line of the 8,619-line tracking pipeline was not manually audited. A successful parse is structural coverage, not proof of correctness.

No real video inference, model download, provider allocation, GPU acceptance, browser video decoding, or full-match capacity benchmark was performed. Frontend behavior reproductions use jsdom and mocked media/canvas APIs. Existing G-PRODUCT/G-CAPACITY gates in `docs/status/current.md` remain open. No independent provider cleanup defect was established in the sampled remote lifecycle review.

**Priority findings**

1. **P1 — The current release's auxiliary detector is interpreted as the wrong model class family.** `backend/release/v7.3.json:60` selects `ball_probe_only_v7_3_crop_256`, but `backend/run_guerilla.py:103` recognizes only two v1 profiles and silently falls back to `coco_tracking_full`. The manifest profile resolves to ball class **32**, while the trained candidate's dataset declares class **0: ball**. Recovery passes the wrong filter to inference (`run_guerilla.py:4858`, `:5101`). Both local and GPU materializers preserve the unsupported name. **Smallest remedy:** implement the selected profile's actual class/preprocessing contract and reject unknown names. Check the real manifest against detector configuration, not just manifest shape. Reproduction required no inference.

2. **P1 — Automatic and manual calibration use different coordinate systems.** `backend/pitch_detector.py:361` maps corners into **68×105** coordinates; `backend/run_guerilla.py:228` accepts this matrix unchanged. The shared manual builder and analytics expect **100×100**. With identical square corners, automatic calibration maps the center to `(34,52.5)` and the far corner to `(68,105)`; manual gives `(50,50)` and `(100,100)`. This distorts distances and positioning, clips y coordinates, and prevents valid on-pitch my-team x coordinates from reaching the shooting-zone threshold of 84. **Smallest remedy:** reuse canonical 100×100 geometry in both initial and periodic automatic calibration. Verify identical-corner parity.

3. **P1 — Selecting right-to-left attack has no analytical effect.** `backend/app/schemas.py:16` accepts `attackDirection`; runtime searches find no reads. The common processing boundary at `backend/app/processor.py:461` does not receive it, and `backend/app/analytics.py:140` assumes my team attacks toward increasing x. A possession-loss sequence at x=90 yields a shot with xG 0.71; its mirrored x=10 sequence yields neither. **Smallest remedy:** carry direction through the common analytical boundary and consistently apply it to goals, progression, pressing, and defensive calculations while keeping display coordinates coherent. Cover local, remote, imported tracking, and team reprocessing.

4. **P1 — The LAP compatibility shim discards valid tracking assignments.** `lap.py:42` solves a forced square assignment and only rejects expensive pairs afterward at `:54`. For `[[0.1,0.51],[0.51,1.0]]` with `cost_limit=0.5`, it returns both tracks unmatched despite the valid cost-0.1 pair. Ultralytics' installed `trackers/utils/matching.py:45` calls this shim with a threshold, so this affects tracking identity continuity. **Smallest remedy:** represent unmatched choices in the optimization itself; filtering the finished assignment is insufficient. Keep SciPy if it can provide the correct augmented formulation; no new tracking abstraction is needed.

5. **P1 — A negative player x coordinate crashes the frontend workspace.** `frontend/src/utils/analytics.ts:37` clamps only the upper heatmap index. An API-accepted x=-0.1 produces `grid[-1][row]` and throws. `frontend/src/App.tsx:242` computes heatmaps unconditionally, even when the layer is hidden. Backend player coordinates are unrestricted floats and tracking normalization preserves them. **Smallest remedy:** validate finite coordinates and clamp both bounds, or explicitly discard off-pitch samples. A targeted check reproduces the TypeError.

**Further correctness and reliability findings**

6. **P2 — Camera recalibration mixes geometry from different times.** `backend/run_guerilla.py:7999` replaces H but retains the initial pitch polygon. The whole-video recovery pass at `:8112` then receives the final H with that initial polygon. A pan can cause legitimate new ball locations to be rejected, and earlier frames can be projected through a later transform. The reviewer reproduced this with mocked camera motion. **Remedy:** retain matching H/polygon pairs by frame or segment and use them in each processing pass; updating only the polygon leaves the recovery problem.

7. **P2 — Unknown team membership is treated as the opponent.** `backend/app/team_classification.py:91` maps every player not matching the selected cluster to `enemy`, including missing cluster membership. Track 99 with mappings `{1:0,2:1}` becomes enemy when cluster 0 is selected. Color extraction can legitimately fail. **Remedy:** keep missing membership unassigned and preserve that uncertainty through possession assignment.

8. **P2 — Acquisition mode is recorded but dropped before execution.** `backend/app/proof_runtime.py:412` and `backend/app/gpu_worker.py:1197` omit `primary_acquisition_mode` from materialized arguments. The current release requests `anchored_player_ranked_context_960`, but neither execution dictionary contains it, and video processing does not accept it. **Remedy:** wire genuinely supported modes through, or validate the sole supported behavior and stop advertising this as a runtime choice. Do not infer execution parity from a serialized option alone.

9. **P2 — Sprint totals count samples instead of runs.** `backend/app/analytics.py:1070` and `:1082` increment for every interval above 25 km/h. The same continuous two-second, 8m/s run produces **10 sprints at 5Hz and 20 at 10Hz**, with identical 16m distance and 28.8km/h top speed. **Remedy:** count per-track transitions into sprint state with a defined rule for missing frames; verify sampling-rate invariance.

10. **P2 — Tactical search reverses PPDA interpretation.** `backend/app/semantic_search.py:104`, `:229`, and `:254` classify high PPDA as aggressive pressing and low PPDA as passive. The actual metric in `backend/app/analytics.py:323` is passes allowed divided by pressing actions. With otherwise identical summaries, searching `high press` returns PPDA 20 while dropping PPDA 5. **Remedy:** align thresholds, score boosts, and explanatory labels with the metric's denominator; handle unavailable/zero-action data separately.

11. **P2 — Search negation checks keyword spelling instead of query context.** `backend/app/semantic_search.py:168` looks for negation substrings inside the entire theme dictionary. `high press without low block` produces required `low_block` and excluded `high_press`; `without wing play` requires wing play. The letters `no` in `turnovers` help cause the reversed exclusion. **Remedy:** associate explicit negation with the following matched query phrase and use word boundaries. No language-model dependency is needed.

12. **P2 — A rejected team-selection update still commits config.** `backend/app/main.py:1096` persists config before reprocessing. A video without raw artifacts returns 409 from PATCH `{"myTeamCluster":1}`, but GET already reports cluster 1. Other reprocessing failures can leave old outputs paired with new configuration. **Remedy:** check prerequisites before mutation and coordinate config/output publication or rollback. The isolated API reproduction verifies persistence after rejection.

13. **P2 — Provider-supplied player IDs are inserted into executable report HTML.** `backend/app/report_export.py:73` interpolates `player["trackId"]` without escaping. `llm.py:376`/`:400` return unrestricted decoded JSON, which the analysis route saves. A mocked provider ID containing `<img src=x onerror="alert(1)">` survives analysis → storage → HTML export. Opening that report can execute the tag. **Remedy:** `escape(str(player["trackId"]))` at output, plus validation of provider response fields. This proves unsafe provider output handling; it does not establish a separate attacker-controlled prompt path.

14. **P2 — Disconnected job websockets retain polling tasks.** `backend/app/main.py:1109` never receives disconnect messages after accept. If the queued/processing payload remains unchanged, it sends nothing either and queries storage every 0.5 seconds indefinitely for a stuck job. The ASGI reproduction supplied disconnect immediately after connection and still observed three polls. **Remedy:** receive disconnect with a polling timeout and exit promptly.

15. **P2 — Invalid configuration produces an HTTP 500.** `backend/app/main.py:1094` runs unguarded Pydantic validation inside a plain-dict endpoint. PATCH `{"attackDirection":"invalid"}` produces a server error rather than a client validation response. **Remedy:** handle `ValidationError` as 422/400 and validate cluster value types before set membership.

16. **P2 — Event and crop navigation confuse frame IDs with array indices.** `frontend/src/utils/api.ts:194` copies source `frameId` into a timeline offset; `Timeline.tsx:104` seeks it directly and `App.tsx:270` uses it as an array index. One imported frame with ID 100 yields seek 100 despite index 0 being the only valid position. Trust crops have the same mismatch (`TrustCropPanel.tsx:180`, `App.tsx:1059`). **Remedy:** resolve IDs or timestamps to displayed indices at navigation boundaries, including playlists and crops.

17. **P2 — Video and application playback state diverge.** `frontend/src/components/MatchVideoPanel.tsx:26` ignores explicit timestamp changes while playing, so timeline scrubbing does not seek the video and its next update reverses the UI seek. Native media controls have no play/pause/ended state callbacks. A play request before metadata is also lost because readiness is only a ref. **Remedy:** synchronize media events, distinguish explicit seeks from playback ticks, and apply pending playback intent after metadata. Two targeted checks reproduce ignored seek and ignored early play.

18. **P2 — A stale frame analysis can reappear after seeking.** `frontend/src/hooks/useCoachAnalysis.ts:105` clears visible output without invalidating the outstanding request. After a seek, the old request still passes the ID check and restores its offside/spacing overlay on the new frame. **Remedy:** invalidate frame-specific requests when their frame changes and clear pending state consistently. A delayed old `{offside_x:33}` response reproduces the issue.

19. **P2 — Saved drawings render outside their review range.** `frontend/src/components/TacticalPitch.tsx:344` renders all saved arrows/circles without examining frame or timestamp bounds; both callers pass the whole list. A circle saved at timestamp 0 renders at timestamp 20. **Remedy:** filter on current timestamp or a consistently defined frame index before drawing.

20. **P2 — Clicking a displayed player tests historical average coordinates.** `frontend/src/components/TacticalPitch.tsx:428` hit-tests `profile.avgX/avgY` while rendering current-frame positions. A visible player at `(25,40)` cannot be clicked if their average is `(80,80)`. **Remedy:** hit-test current positions, then look up the profile by team and ID; reuse the current-player filtering used by the keyboard selector.

21. **P2 — The upload entry points are not keyboard-operable.** `frontend/src/App.tsx:603` and `:685` use nonfocusable labels around `display:none` file inputs, without an operable button/native input alternative. Drag/drop does not solve keyboard access. **Remedy:** expose a native file input or an actual button invoking the picker. Source-confirmed; no screen-reader session was run.

22. **P2 — Modal overlays lack dialog and focus behavior.** `frontend/src/components/SaveBundleButton.tsx:109`, `BundleListPanel.tsx:63`, `TrustCropPanel.tsx:88`, and `App.tsx:1008` use fullscreen divs without dialog semantics, focus containment/restoration, or Escape dismissal. Background controls remain reachable. **Remedy:** use native modal dialog behavior and explicit initial/restored focus. Source-confirmed rather than an assistive-technology test.

23. **P3 — Review writes can create orphan match artifacts.** `backend/app/main.py:1187` and `:1204` do not verify match existence before annotation/issue writes. POSTing an issue for `not-a-match` returns 201 and creates `issues.json` without a match record. **Remedy:** reuse a match-existence check and return 404 before writing.

**Ponytail cuts — largest first**

- `delete:` unused single-bundle load/create/edit state and handlers in `frontend/src/hooks/useReviewBundles.ts:46`. Its only caller consumes listing/deletion. Approximately **65–75 lines**; replacement: nothing.
- `delete:` `buildShotMarkers` at `frontend/src/utils/analytics.ts:143` and its private `isShotInBox` helper. Only tests call it; runtime already uses backend shot analytics. Approximately **52 production lines**; remove obsolete tests when deleting.
- `delete:` unused `_compute_outputs` at `backend/app/processor.py:449`. The actual flows use `_compute_outputs_and_match_state`. **10 lines**; replacement: nothing.
- `shrink:` duplicate bundle POST in `frontend/src/components/SaveBundleButton.tsx:64`. Reuse `utils/api.ts`'s existing `createBundle`. Approximately **9 lines net**.
- `delete:` first `eventTypes` construction at `backend/app/processor.py:928`. Its zero counts are immediately overwritten by real counts. **7 lines**; keep the existing counting pass.

**net: approximately -143 to -153 production lines, -0 dependencies possible.** Estimates exclude obsolete test removals and small import formatting changes. No cuts were applied. The repo-wide AST scan also found duplicate historical training/readiness functions, but their version-specific constants and provenance need checking before consolidation; they are excluded from this estimate. Sealed artifact validation, durable publication, and cleanup ownership enforce real requirements and are not deletion targets merely because they are long.

**Reproduction evidence**

Session-local checks and logs remain outside the repository:

```bash
PYTHONPATH=. python3 /tmp/football-pipeline-audit-repro.py
PYTHONPATH=. python3 /tmp/fotball_backend_audit_repro.py
cd frontend
./node_modules/.bin/vitest run --config /tmp/frontend-audit/vitest.config.mts
```

The checks deliberately assert the current defects to confirm reproduction; their passing status does not mean the defects are fixed. Sources are `/tmp/football-pipeline-audit-repro.py`, `/tmp/fotball_backend_audit_repro.py`, and `/tmp/frontend-audit/repro.test.tsx`. These are temporary session artifacts, not a committed regression suite. Full results are in `/tmp/football-audit-backend.log`, `/tmp/football-audit-sidecar.log`, `/tmp/football-audit-failure-confirmation.log`, `/tmp/football-audit-npm.log`, and `/tmp/frontend-audit-{test,lint,build}.log`.

Two compact reproductions are preserved here independently of temporary files:

```python
import lap
from backend.app.semantic_search import _parse_nl_query

print(lap.lapjv([[0.1, 0.51], [0.51, 1.0]], cost_limit=0.5))
# Actual: total 0, both assignment arrays [-1, -1]; valid 0.1 pair is lost.
print(_parse_nl_query("high press without low block"))
# Actual: (['low_block'], ['high_press']); intended inclusion/exclusion is reversed.
```

**Suggested repair order:** correct the detector/calibration/tracking contracts and frontend crash first; then direction and data integrity, followed by search, review navigation, async state, and accessibility. Each repair should carry the smallest behavioral regression check. Apply the proven deletions separately. Real football acceptance and capacity measurement still require their existing prerequisites; this analysis does not substitute for them.
