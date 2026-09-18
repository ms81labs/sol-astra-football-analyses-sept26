# Backend Post-Remediation Cross-Check (v3 review verified against source)

**Reviewed commit:** `b3fbe78c51f9a30891e939b610fa292da7f05bf9` (`main`, after PR #5)
**Input reviewed:** `docs/superpowers/audits/2026-09-18-backend-post-remediation-audit-v3.md` (external v3 review, R01–R10)
**Method:** local checkout at the pinned commit; every R-finding traced to the actual call path; additional issues found while tracing. No tests were run, no code was changed, no providers or paid workers were touched. This is a source cross-check, not a re-execution of the suite.
**Purpose:** confirm or correct the v3 findings, add what it missed, and give the implementing agent a single continuation brief.

---

## 1. Verdict on the v3 review

The v3 review is accurate. All ten R-findings are **source-confirmed** at `b3fbe78`; none is overstated. Where I differ, it is only to sharpen severity (R01/R02/R05 interact into a worse failure than any one alone; R04 is more directly reproducible than described; R09 has a second, harder cap it did not mention).

I agree with the disposition: keep the remediation, do not roll back, do not accept "35 closed" at this snapshot, and finish with one bounded integration pass.

## 2. R01–R10 verification table

| R | v3 claim | Verified at `b3fbe78` | Sharpening |
|---|---|---|---|
| R01 | Ordinary read prunes non-current generations; readers not pinned | **Confirmed.** `Storage._current_generation_unlocked` (storage.py ~L1194–1240) writes the pointer and `shutil.rmtree`s every `gen_*` dir not in `{current} ∪ {appliedGeneration of commands in "applying"}`. Called from `current_generation()`/`generation_snapshot()`, which `load_frames`/`load_events`/`load_analytics` reach via `_generation_payload_path` on **every** call. The file read itself happens after the lock is released. | Reads are also expensive: `_complete_generations` re-hashes every file of every generation on every read (`_sha256_file` per file). For a full match, each `load_frames` is O(total generation bytes). |
| R02 | DB summary commits before pointer; `os._exit` leaves them inconsistent | **Confirmed.** `_publish_generation_unlocked` (~L1369–1490): `UPDATE matches SET analytics_summary_json` → `_review_test_fault("before_pointer_publish")` → pointer write, with restore only in a Python `except`. | Interaction with R01: after a kill at that point, the next read keeps the old pointer and **deletes the new complete directory**, while SQLite (dashboard/list views) keeps the new summary. The summary now describes a generation that no longer exists on disk. |
| R03 | Video materialisation does not reproject; tracking branch does | **Confirmed.** `ReviewService._materialize` (review_service.py ~L231–288): `inputMode == "video"` → `reprocess_video_match(..., persist=False)` with no projection; `else` branch → `project_tracking_frames(...)`. Same asymmetry in `processor._publish_outputs` (~L804–868), which projects only when `inputMode == "tracking_json"`. | — |
| R04 | Identity approval and config PATCH not composed with commands | **Confirmed and stronger — see N01.** `identity_continuous=any(kind == "identity_validate")` at review_service.py ~L174 regardless of later split/join. `_effective_config` (~L299–317) resets `myTeamCluster` to a frozen `review_base_config.json` then replays swaps. | The PATCH route produces a same-request config/frames divergence (N01). |
| R05 | Stale narratives/auxiliary state not generation-bound | **Confirmed.** `GET /api/matches/{id}/report/html` (main.py ~L1846–1885) loads `tactical_report`/`drills` via flat `load_analysis_artifact` with no manifest `stale` check. `acceptedMatchState` returned by `_materialize` is not among generation files; processor writes it as a flat artifact. | `load_events(match.id, generation_id=...)` runs **after** the `generation_snapshot` context exits and swallows `FileNotFoundError` into `events = []`. Combined with R01, a concurrent publish yields an HTML report with zero events, silently. |
| R06 | Grounding validator ignores unprefixed references; missing `evidence` passes | **Confirmed.** `validate_output` (provider_gateway.py ~L271–308): references collected only if `startswith(("ev_", "event:", "frame:"))`; `raw.get("evidence", [])` defaults to empty; no per-reference generation scoping. | Numeric checks are sound for the declared shapes (`{"metric","value"}` and direct metric-name keys) and correctly reject claims about metrics whose known value is `None`. |
| R07 | Receipt says `actualTotal=None` when unsettled; `cost_for`/`cost_summary` say settled subtotal | **Confirmed.** jobs.py L949 vs L1007 and L1026. Frontend `JobCostSummary.actualTotal: number` (workbench.ts L65). | — |
| R08 | Layered identities use fixed strings / filenames | **Confirmed.** video_pipeline.py L198–203: `preprocessing_id="bgr24-source-grid-v1"`, `class_map_id="coco-football-v1"`, `tracker_config_id="botsort.yaml"`. Not independently traced: recovery/auxiliary weights binding. | — |
| R09 | 8 GiB cumulative raw-output cap and 300 s wall timeout bound full-match work | **Confirmed.** media.py L315–316 defaults; L472 compares cumulative `output_bytes`; L442 wall timeout spans the iterator lifetime. | **A second, harder cap exists — see N02.** |
| R10 | Manifest structural completeness treated as acceptance | **Confirmed.** evaluation.py L143 `accepted = status == "scored"`; `status = "scored"` (L210) is set from manifest fields, not from artifact replay or thresholds. | — |

**Not re-verified in this pass** (v3 dispositions taken as read): B10/B11 ledger transaction details beyond the budget totals, H06 adapter pixel tests, B19 grid arithmetic, training gate epoch binding, CI artifact contents. v3 downloaded the CI artifacts; I did not.

## 3. Additional findings (not in v3)

### N01 — Config PATCH on a reviewed match publishes the old team mapping and persists the new one (P1)

**Path (verified):** `PATCH /api/matches/{id}/config` (main.py ~L1904–1940) → when `myTeamCluster` changes on a video match: `reprocess_video_match(storage, match_id, config=config_model)` **then** `storage.update_match_config(match_id, config_model)`.
`reprocess_video_match` computes frames with the new config, then calls `_publish_outputs` (processor.py ~L804). `_publish_outputs` checks `any(applyState == "applied")` and, if **any** correction has ever been applied, discards the freshly computed outputs and calls `ReviewService.rebuild_generation(match_id, reason="processing")`. That rebuild reads `_effective_config`, which starts from `storage.get_match(match_id).config` — still the **pre-PATCH** config, because `update_match_config` has not run yet — resets `myTeamCluster` to `review_base_config.json`, and replays swap commands.

**Result:** the published generation carries the base-plus-swaps mapping; the match config then records the PATCHed cluster. Config and frames disagree at the end of one request. The next `rebuild_generation` (any correction) keeps ignoring the PATCH because it is not a command and the base file is frozen. This is the B04 shape again, one layer up (explicit selection instead of swap).

**Regression:** raw-row video match with two clusters → apply and accept one `event_accept` (so `applied` exists) → `PATCH config {"myTeamCluster": <other>}` → assert `get_match().config.myTeamCluster == other` **and** the majority team label in `load_frames()` for a known track corresponds to `other`; then submit an unrelated correction and re-assert; then restart a fresh process and re-assert. Fails at `b3fbe78` on the first frame assertion.

**Repair:** route semantic config changes through `ReviewService` as a command (`config_set`), or have `_effective_config` rebase on the *requested* config rather than a frozen base; never call `reprocess_video_match`+`update_match_config` in that order from a route.

### N02 — Every FFmpeg/ffprobe child runs under `RLIMIT_CPU=300 s` and `RLIMIT_AS=4 GiB` (P1 before FFmpeg on full matches)

**Path (verified):** `_sandbox_kwargs` (media.py L78–96) installs a `preexec_fn` that sets `RLIMIT_AS=4 GiB`, `RLIMIT_CPU=300` (hard and soft), `RLIMIT_FSIZE=max_file_bytes`. Used at L391 (decode) and L621 (proxy/export).

**Why it matters beyond R09:** R09's caps are Python-side and configurable per `FfmpegFrameSource`. These are kernel hard limits applied to every child regardless of caller arguments. Decoding a 90-minute 1080p stream costs far more than 300 CPU-seconds, so the child is killed with `SIGXCPU` and surfaces as a nonzero exit (`DecoderFailed`), not as a limit the caller can raise. `RLIMIT_AS=4 GiB` can also fail allocations for multi-threaded software decode or hwaccel contexts that reserve large virtual ranges, producing spurious decoder failures unrelated to media content.

**Regression:** `@real_media` — generate a 10-minute 1080p clip (`testsrc`), decode with the FFmpeg source; assert completion. Then a synthetic child that busy-loops >300 CPU-s must be killed and reported as a resource limit, not as a generic decoder failure. Assert the limits are parameters of an admitted mode (short clip / offline full match / live), not module constants.

**Repair:** make the rlimits part of the same declared execution policy v3 asks for in R09; size CPU and address-space limits from the admitted source duration/resolution; keep `RLIMIT_FSIZE`/protocol whitelist as-is.

### N03 — Generation read path is destructive, unpinned, and O(all generation bytes) per read (P1, extends R01)

Three separate consequences of one design choice (resolution + GC + pointer rewrite inside the read path):

1. **Destructive read** (R01).
2. **Unpinned multi-artifact reads:** `load_frames` and `load_events` each take and release the lock independently; a request that reads both can straddle a publish and combine generation N frames with N+1 events (or hit a pruned N). The HTML report route (§2 R05 row) is one concrete instance.
3. **Cost:** `_complete_generations` hashes every file of every generation (`files` digests) on each resolution, and the pointer file is rewritten on each read. For a full-match `frames.json` this turns every API read into a full-file hash plus a write.

**Regression:** count `_sha256_file` calls and pointer writes during one `GET /api/matches/{id}/frames` — expected 0 hashes and 0 writes when nothing changed. Two-reader test: reader A opens snapshot N and reads frames+events while B publishes N+1; A's frames and events must carry the same `generationId`.

**Repair:** resolve once per request into a `GenerationRef` and pass `generation_id` explicitly to every loader (the parameter already exists); verify manifests only on publish and on explicit `verify`/recovery; move GC to an explicit retention command that skips generations referenced by any correction (`applied` or `applying`) or by any persisted report/evidence.

### N04 — Team-swap semantics differ between video and tracking branches for ≥3 clusters (P2)

`_effective_config` swaps by choosing `alternatives[0]` (lowest-sorted cluster ≠ current); `_materialize`'s tracking branch swaps by parity (`swaps % 2` → `apply_team_swap`). With clusters `{0,1,2}` and base `2`: two swaps yield `0 → 1`, not back to `2`; the tracking branch would be back at base. Undo of a swap therefore does not restore the original mapping on a three-cluster video match.

**Regression:** raw-row fixture with three clusters, base `2`; swap, swap (or swap, undo); assert `myTeamCluster == 2` and frames match base. Fails at `b3fbe78`.

**Repair:** make `team_mapping` carry an explicit target (`{"myTeamCluster": X}` or `{"swap": true, "from": A, "to": B}`) and replay deterministically; treat bare `swap` on ≥3 clusters as a validation error.

### N05 — Closure report evidence does not meet the guide's own bar (process, P2)

`docs/superpowers/audits/2026-09-18-backend-audit-v2-closure.md`:

- The "Baseline failure (assertion)" column contains prose descriptions, not the captured assertion output the guide (§3.4) required. The baseline failures cannot be checked from the document.
- Header says `HEAD at start: 1397ce8; pre-existing delta 70 files` — i.e. the closure session began after most H-packages had merged. "Baseline verify → 3,331 passed" does not state which commit produced that count.
- "Stubs active in code-only: none" is a local statement; the CI receipts for `b3fbe78` list `ultralytics` under `stubsActive` (per v3, which downloaded them). Counts must always be paired with source commit and stub state.
- `Fixed revision: 9ac3685` is not the reviewed `main` (`b3fbe78`); three later commits (`11fcd05`, `6b68064`, `fcef323`) are not covered.

**Repair:** regenerate the closure table from the worktree procedure (guide §15) with pasted assertion lines, one row per sub-claim, at the actual `main` head; record stub state from the CI receipt, not from a local run.

### N06 — Wasted compute and dropped outputs in `_publish_outputs` (P2, hygiene)

When any correction is applied, `_publish_outputs` discards the outputs just computed by the caller (`reprocess_video_match` or the worker persistence path) and recomputes everything via `rebuild_generation`. For a worker result import this doubles the analytics pass on the largest inputs. Fold into the N01 repair: processing should produce the immutable observation layer and hand off to one materialiser, not compute outputs twice.

## 4. Where I would adjust v3's finishing plan

v3's six bounded changes stand. Adjustments:

| v3 change | Add |
|---|---|
| 1. Generation lifetime and crash consistency (R01–R02) | N03 (resolve-once-per-request, verify-on-publish, explicit retention). Make this the **first** change; several later regressions cannot be written reliably while reads are destructive. |
| 2. Real video reprojection and edit composition (R03–R04) | N01 (PATCH-as-command) and N04 (explicit swap targets). N01 is the highest-value new regression: it is the audit's original B04 pattern reappearing on the explicit-selection path. |
| 3. Generation-bound reports and evidence validation (R05–R06) | The report route must read all artifacts under one `generation_id` and must not swallow `FileNotFoundError` into `[]`. |
| 4. One cost contract (R07) | Frontend `JobCostSummary.actualTotal: number | null`. |
| 5. Artifact identity and evaluation acceptance (R08, R10) | — |
| 6. Declared video/platform envelope (R09) | N02 (rlimits as policy). Do not remove the rlimits; parameterise them. |
| — | N05: regenerate the closure report at the real `main` head with captured baseline output. |

Dependency: change 1 before 2, 3 and 5. Changes 4 and 6 are independent.

## 5. Status vocabulary for the continuation

Per item, the agent must report one of: `fixed` (commit, test, pasted baseline assertion, fixed pass with profile), `safely deferred/disabled`, `still open`, `not reproduced`. v3's A/P/R/V labels are useful for reading the current state, but the closure table must use the four fixed statuses.

## 6. Continuation brief for the implementing agent

```text
You are continuing the backend remediation for ms81labs/sol-astra-football-analyses-sept26 from main = b3fbe78c51f9a30891e939b610fa292da7f05bf9.

Read, in this order:
1. docs/superpowers/audits/2026-09-18-backend-post-remediation-crosscheck-v3.md   (this file: verified findings R01–R10 + N01–N06, adjusted plan)
2. docs/superpowers/audits/2026-09-18-backend-post-remediation-audit-v3.md        (the external v3 review; required repairs and regressions per R item)
3. docs/superpowers/plans/2026-09-18-backend-audit-v2-remediation-implementation-guide.md  (rules §1, conventions §3, contracts §12 still apply)

Do NOT reopen B01–B35 wholesale. Work the six bounded changes in §4 of file 1, in dependency order: change 1 (R01, R02, N03) first; then 2 (R03, R04, N01, N04), 3 (R05, R06), 5 (R08, R10); 4 (R07) and 6 (R09, N02) may run in parallel with the rest.

For every R/N item: write the regression against b3fbe78 first (worktree recipe, guide §15), capture the failing assertion line, then fix. The regression fixtures must include the raw-row video fixture already at backend/tests/fixtures/raw_rows_two_teams.json plus a three-cluster variant (N04) and a source-pixel-coordinate fixture with two known homographies (R03).

Specific requirements:
- Reads never delete or rewrite anything. Resolve a GenerationRef once per request and pass generation_id to every loader. Verify manifests on publish and on explicit recovery only. Garbage collection is an explicit retention command that protects any generation referenced by a correction or a persisted report.
- Publication order: complete directory + manifest → pointer → derived SQLite indexes; treat SQLite summary as a rebuildable cache reconciled on read if it disagrees with the pointer.
- Config changes from PATCH become commands (or rebase the overlay on the requested config). The route must never call reprocess_video_match before update_match_config. Team mapping commands carry explicit targets.
- identity_continuous is bound to the identity revision; any later split/join invalidates it until re-validated.
- Video materialisation applies the accepted calibration revision to source-image observations; tracking imports declare their coordinate space and are refused if undeclared when a projection is requested.
- Report/export routes read every artifact under one pinned generation_id and never convert FileNotFoundError into empty data.
- validate_output validates every entry of declared reference fields regardless of prefix, requires references for factual output, and scopes references to (matchId, generationId).
- One cost contract: settledTotal, outstandingReserved, unsettledTotal, actualTotal: number|null on receipt, cost_for, cost_summary and the frontend type.
- FFmpeg limits (max_output_bytes, wall timeout, RLIMIT_CPU, RLIMIT_AS) are parameters of a declared execution mode sized from the admitted source; keep RLIMIT_FSIZE and the protocol whitelist.
- Evaluation: separate inventory / executed / scored / accepted; accepted requires verified artifact digests and an explicit threshold policy.

Finish by regenerating docs/superpowers/audits/<date>-backend-audit-v2-closure.md at the final main head: one row per R/N sub-claim, pasted baseline assertion lines, fixed pass with profile, stub state taken from the CI receipt. Statuses are exactly: fixed | safely deferred/disabled | still open | not reproduced.

Do not enable cloud providers, launch paid jobs, or change deployment state. Do not weaken any existing behavioural assertion.
```
