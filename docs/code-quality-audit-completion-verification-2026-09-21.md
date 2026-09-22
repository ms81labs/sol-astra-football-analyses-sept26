# Backend Code-Quality Audit — Independent Completion Verification (2026-09-21)

**Audit under review:** `sol_astra_backend_code_quality_audit_rebuilt_2026-09-20` (baseline `312cb5a`)  
**Remediation closure under review:** `docs/code-quality-remediation-closure-2026-09-21.md` (verified head `c64fb87`, docs commit `f99802f`)  
**Verified against:** `main` at `f99802f3178ed0e3c5d310543c8beb6368f67c36`  
**Method:** every finding, PR step, and acceptance criterion in the audit was re-checked against source, Git history, and fresh local tooling. Where a claim depended on a number, the number was re-measured here rather than copied from the closure document. The audit snapshot `312cb5a` was extracted alongside HEAD so before/after figures use one measurement method.

## 1. Verdict

**The remediation program is substantially complete. 20 of 23 register items are verifiably closed, 2 are intentionally retained with defensible rulings (M08, M09), and 1 (M01) is closed under a reinterpretation of the audit's metric that should be stated explicitly. Every acceptance criterion in audit §13 holds except #11 (separate refactor/product PRs), which was deliberately waived by working directly on `main`.**

Three residues were found that the closure document does not mention. None is a correctness defect; all are hygiene left behind by the remediation itself:

1. The H06 script codemod replaced local `_utc_now_iso` bodies but left `from datetime import datetime, timezone` behind in **64 scripts**; unused imports in `backend/scripts` rose from 40 to 175 across the program.
2. PR 3C ("clean actual unused imports after `_main` is gone") was applied only to `main.py`. **18 real unused imports remain in `backend/app`** (e.g. `shutil`/`ValidationError` in `storage.py`, `json` in `leftover_routes.py`, `deque`/`constrained_decoder` in `media.py`).
3. C03 has no dedicated regression asserting that a wrapped model lacking `predict` skips the probe pass; coverage is indirect through the pre-existing `FakeModel` tests that used to fail.

## 2. Fresh evidence gathered for this verification

| Check | Result |
|---|---|
| CI run `35653434812` on `f99802f` | verify, python-quality, excluded-backend, api-profile, macos-profile, integration, real-media all **success**; gpu-acceptance skipped (manual lane) |
| CI `ruff-debt-evidence` artifact (RUF100 + B023) | **0 lines** |
| CI `excluded-backend` artifact | **594 passed** (`stubs_active: ultralytics`) |
| Local `ruff check backend --select F821,F822,F823` (ruff 0.16.8, pinned lock) | All checks passed |
| Local `ruff check backend/app/main.py --select F401` | All checks passed |
| Local `ruff check backend --select B023` | **0** (snapshot: 43) |
| Local CI-equivalent RUF100 debt command | **0** (snapshot: 13) |
| Local `ruff check backend --select RUF100,E402` (the audit's "76" metric) | **65** (snapshot: 76) — all for never-enabled ANN/S310/BLE001 rules |
| Local `ruff check backend/app --select F401` | **18** (snapshot: 178) |
| Local `ruff check backend/scripts --select F401` | **175** (snapshot: 40) |
| Local `ruff check backend/app --select S110` | **19** (snapshot: 22) |
| `git diff --check` | clean |
| FastAPI route table (`path`, `methods`) snapshot vs HEAD | **identical, 558 routes** |
| `app.openapi()` snapshot vs HEAD | **byte-identical** |
| `Storage` public member set snapshot vs HEAD | **identical, 159 members** |
| `MatchBenchmarkSummary` field order + JSON schema snapshot vs HEAD | **identical, 166 fields, 0 duplicates** |
| Runtime dependency declarations (`pyproject.toml`, `backend/requirements/*.lock`) | only additions: `[tool.ruff]` config and the isolated `quality-linux.lock` (ruff 0.16.8); no runtime dependency added |
| Full backend suite, local, no `--ignore` (`dev.lock`, Python 3.12, `ultralytics` stubbed, `cv2`/`pandas` real, `QT_QPA_PLATFORM=offscreen`) | **4,432 collected / 4,415 passed / 0 failed / 18 skipped** in 37m 32s (snapshot: 4,181 / 4,153 / 22 / 6). Skips are environmental on this VM (`ensurepip` absent, IPv6 unavailable, ffmpeg-free cases, artifact-dependent SoccerTrack/TrackEval/recovery-archive tests); none is in the six formerly excluded modules |
| Six formerly excluded modules alone, local (`GA_VERIFICATION_PROFILE=excluded-cpu`) | **594 passed, 0 skipped** in 68s — matches the CI excluded-backend artifact |

## 3. Finding-by-finding verification

Legend: **Closed** = verified in source/tooling here; **Closed*** = closed with a caveat; **Retained** = intentionally not changed, ruling checked.

### Critical

| ID | Status | Verification |
|---|---|---|
| C01 | **Closed** | `leftover_routes.py:5` imports `Path`. `/decode/export` now has a distinct `except ValueError` branch returning `[str(exc)]` before the broad catch. `test_api.py:3387` asserts `reasonCodes == ["unconstrained decoder"]` exactly, so a `NameError`/`AttributeError` falling into the broad catch (`"UNCONSTRAINED_DECODER"`) now fails the test. The outer catch is retained as the audit allowed. |
| C02 | **Closed** | All 22 snapshot failures are accounted for by targeted commits: 9 `test_run_guerilla` (C03 guard, heartbeat/wrapper assertions, subprocess `ultralytics` stub, numpy scalar fix in `perception.py`), 8 `test_operational_docs` (retired recipe CLIs now fail before optional imports), 3 `test_gpu_worker` (race tests kept adversarial under hardened modes), 1 SoccerTrack (bound to committed corpus hash), 1 CVAT (checked-in parent). The six excluded modules are listed once in `backend/tests/code_only_exclusions.txt`, consumed by both `scripts/verify.sh` and the new automatic `excluded-backend` CI job. GPU-hardware tests additionally remain in the manual `gpu-acceptance` lane. No orphan excluded module. |
| C03 | **Closed*** | `run_guerilla.py:8370-8395`: `probe_source_model = auxiliary_ball_model or primary_model`; guard is `hasattr(probe_source_model, "predict")`, i.e. on the wrapped model. Fix is minimal and matches the audit's "check the real capability" principle rather than adding `predict()` to fakes. *Caveat:* no dedicated regression exists for "wrapped model without `predict` skips the probe pass"; the fix is protected only indirectly by the `FakeModel` tests that previously failed. |

### High

| ID | Status | Verification |
|---|---|---|
| H01 | **Closed** | `main.py` is 398 lines with **0** `@app.<method>` decorators (snapshot 2,354 / ~105). Nine native `APIRouter` modules (`job_routes`, `match_detail_routes`, `match_ingest_routes`, `match_runtime_routes`, `review_routes`, `insight_routes`, `artifact_routes`, `system_routes`, workbench). No DI/controller framework introduced. Route table and OpenAPI schema unchanged. |
| H02 | **Closed** | `_main.` occurrences in both leftover routers: **0**. Shared helpers moved to `workbench/leftover_support.py` (334 lines). `test_leftover_router_architecture.py` forbids `backend.app.main` / `_main.` in either router. Three compatibility aliases (`_dashboard_average`, `_dashboard_difference`) were retained explicitly in `main.py` because tests import them; this is documented in the checkpoint. |
| H03 | **Closed** | `storage.py` 3,435 → 2,034 lines; `Storage` composes `_IdentityStorageMixin`, `_CalibrationStorageMixin`, `_RemoteResultStorageMixin`, `_JobStorageMixin` plus review/correction components in six `storage_*.py` modules. Public member set identical (159). Four AST seam regressions (`test_storage_{job_persistence,review,calibration,identity}_seam.py`) prevent drift back. The stop condition in the closure ("no further LOC-driven split") is consistent with the audit's own guidance. |
| H04 | **Closed** | `summarize_match_benchmark()` measured at **446 lines** (snapshot ~1,003). Helpers are module-level pure functions in the same file (file grew 2,223 → 2,433 lines by design). Single final assembly point retained; `MatchBenchmarkSummary` schema identical. |
| H05 | **Closed** | AST check: 166 annotated fields, **0 duplicates**. Field order and JSON schema identical to snapshot, confirming nothing relied on the accidental duplicates. |
| H06 | **Closed*** | `_utc_now_iso` local definitions in scripts: **0** (snapshot 115 byte-identical + 65 other). `sys.path.insert/append` in scripts: **0** (snapshot 297). Common helper imported by 286/322 scripts (snapshot 221). `test_script_hygiene.py` AST gate runs in both `python-quality` and the canonical verifier. Helper semantics verified identical (`datetime.now(timezone.utc).isoformat()`). *Caveats:* (a) 64 scripts keep a now-dead `from datetime import datetime, timezone`; 5 scripts import `utc_now_iso` and never use it; (b) 81 scripts still define local `_write_json`/`_load_json` in 13 variants — these differ from the common helper (trailing newline, `sort_keys`) so skipping them respects the audit's "where semantics match" rule, but the duplication itself was a named PR 7 target and remains; (c) no historical scripts were retired (322 → 322), which the audit permitted only "after caller/CI/test validation", so this is a non-action rather than a miss. |
| H07 | **Closed** | Both confirmed sites fixed: dispatch persistence failures log `LOGGER.warning(... match=%s job=%s error=%s)` (now in `match_ingest_routes.py:149-162`); `_admit_durable_job` hash fallback logs before substituting the zero SHA (now `storage_jobs.py:94`) with regression `test_storage_observability.py`. Only exception type names are logged, no payloads. The audit's broader "classify all 24 sites" step is not recorded as a written triage; Ruff S110 count moved 22 → 19 in `backend/app`. Remaining sites are in cleanup/rollback/provider-boundary code the audit explicitly said to preserve. |
| H08 | **Closed** | `python-quality` CI job installs `ruff==0.16.8` from a hash-locked, isolated `quality-linux.lock`; enforces F821/F822/F823 repo-wide and F401 on `main.py`; reports RUF100/B023 debt as an artifact. `[tool.ruff]` in `pyproject.toml` mirrors the gate. Rollout order (check-only → decouple `_main` → targeted F401) matches audit §10 exactly; no blind `--fix` was applied. Only one static tool added (no Mypy+Pyright). |

### Medium

| ID | Status | Verification |
|---|---|---|
| M01 | **Closed*** | The audit's "76 stale noqa" corresponds to `RUF100` with E402 enabled, which counts directives for never-enabled rules (ANN001, S310, BLE001 …). The remediation ran RUF100 with those rules enabled, found 13 directives that would be unused even then, and removed 11 (`# noqa` count 734 → 723). The remaining 65 would each suppress a real finding if their rule were enabled, so they are not "proven unnecessary" and the audit forbade blanket deletion. This is a defensible reinterpretation but the closure text ("cleared for intended scope") should say so explicitly. |
| M02 | **Closed** | B023: 43 → **0** on the same ruff version; CI debt artifact empty. Fixes bind loop variables (commit `3ac7a1b`), no callback abstraction introduced. |
| M03 | **Closed** | Pass-count minimums removed from `verify.sh`; selection is manifest-driven (`code_only_exclusions.txt`) and `test_verify_script.py` asserts the manifest is referenced by both `verify.sh` and `ci.yml`. Remaining literals `1486`/`37`/`46` in the test are fake pytest output in a stub fixture, not thresholds. |
| M04 | **Closed** | No `[0-9]+ passed` regex or summary parsing remains in `verify.sh`; gates fail on exit status via `PIPESTATUS`. |
| M05 | **Closed** | `test_dependency_profile_drift.py` asserts `pyproject.toml` optional profiles equal `api.in`/`cpu-cv.in`/`cuda.in` and that overlapping pins agree across `api`/`cpu-cv`/`cuda`/`dev`. |
| M06 | **Closed** | `integration` job runs `python -c "import cv2, pandas"` and `gpu-acceptance` runs `import cv2, pandas, ultralytics` before tests; excluded lane is labelled `excluded-cpu` and its receipt discloses `stubs_active: ultralytics`. Conftest stubs retained for code-only testability as the audit required. |
| M07 | **Closed** | `_normalized_repair_config` 256 → **19** lines; seven family-level `_normalize_*_fix` helpers, largest 51 lines. No YAML/DSL/config framework added. |
| M08 | **Retained** | 20 `RouteRetired` handlers in `workbench/routes.py`; tests assert 410 `ROUTE_RETIRED`. Removal would be a contract change the audit said to make only after caller validation. Ruling is consistent with audit §13 #2 and #10. |
| M09 | **Retained** | Largest test files unchanged. The audit itself said "selective extraction … not fragmenting"; no concrete duplicated setup was identified, so no action is a legitimate outcome. |
| M10 | **Closed** | `run_benchmarks.py:1035-1039` exposes `assess_truth_gates`, `load_ball_truth_layers`, `load_accepted_match_state`, `summarize_ball_rows` as a documented "supported internal API"; `run_source_robustness_batch.py` imports the public names. `_REMOTE_RESULT_FILENAMES` / regular-file helper moved to `storage_remote.py`. Minimal but matches the audit's "promote the stable helpers" option. |

### Positive findings (P01–P04)

Preserved. No diff since snapshot in `daytona.py`, `gpu_worker.py`, `analytics.py` line counts; `Storage` extraction moved methods without behavior change (public surface, OpenAPI, and suite unchanged). Hash-locked profiles untouched except the additive quality lock.

## 4. Remediation plan (audit §9) step check

| PR | Status | Note |
|---|---|---|
| 0A masked decoder defect | Done | `6a907fa` RED → `71b8af3` GREEN |
| 0B truthful full-suite baseline | Done | 22 failures classified in `docs/superpowers/audits/2026-09-20-…crosscheck.md` §5 and each repaired |
| 0C execution home for excluded tests | Done | `excluded-backend` automatic lane + manual GPU lane |
| 1 break `_main` dependency | Done | `712b610` RED → `fa6196c` |
| 2 Ruff check-only | Done | correctness rules only; debt reported not gated |
| 3A stale noqa | Done* | see M01 caveat |
| 3B B023 | Done | 43 → 0 |
| 3C real unused imports | **Partial** | `main.py` only; 18 remain in `backend/app`, 175 in `backend/scripts` (135 created by the H06 codemod) |
| 4 modularize FastAPI | Done | 9 routers, 0 inline routes |
| 5 split benchmark summarization | Done | duplicates removed first, then extraction |
| 6 reduce `Storage` change radius | Done | 6 seams, facade preserved |
| 7 consolidate scripts by adoption | Done* | UTC helper + bootstraps complete; JSON helper duplication and thin-entrypoint conversion not attempted |
| 8 degraded-state observability | Done* | confirmed sites fixed; no written classification of all sites |
| 9 verification / dependency hygiene | Done | M03–M06 |

## 5. Acceptance criteria (audit §13)

| # | Criterion | Result |
|---|---|---|
| 1 | No football-analysis direction change | Holds — `run_guerilla.py` diff since snapshot is limited to the C03 guard and B023 default-argument bindings (two commits: `7a857d4`, `3ac7a1b`); the numpy scalar fix is two lines in `workbench/perception.py` |
| 2 | No endpoint URL/schema/status change | Holds — OpenAPI byte-identical, 558 routes identical |
| 3 | No weakening of FS/rollback/security boundaries | Holds — `daytona.py`, `gpu_worker.py` unchanged; storage methods moved verbatim |
| 4 | Focused tests pass | Holds — CI green on `f99802f` |
| 5 | Complete applicable suite accounted for | Holds — excluded lane automatic; see §2 for local full run |
| 6 | Ruff passes for intended scope | Holds — F821/F822/F823 + `main.py` F401 clean |
| 7 | No broad autofix before decoupling | Holds — F401 gate added to `main.py` only after `fa6196c` |
| 8 | No new runtime dependency | Holds — only isolated Ruff lock |
| 9 | No new generic framework | Holds — native `APIRouter`, mixins, existing helper module |
| 10 | Deleted scripts/routes have evidence | N/A — nothing deleted |
| 11 | Refactors and product changes in separate PRs | **Waived** — all work landed as direct commits on `main` at the user's request (per checkpoint); C04–C06 product commits are interleaved with CQA commits in the same history |
| 12 | `git diff --check` clean | Holds |
| 13 | Suppressed failures documented or observable | Holds for the confirmed sites; remaining S110 sites are cleanup-boundary code |

## 6. Recommended follow-ups (small, optional)

These are hygiene items the remediation created or left; none blocks closure.

1. Remove the 64 dead `from datetime import datetime, timezone` lines and 5 unused `utc_now_iso` imports in `backend/scripts` (mechanical; `ruff check backend/scripts --select F401 --fix` is now safe because no dynamic re-export remains in scripts).
2. Clean the 18 `F401` findings in `backend/app`, then extend the CI F401 gate from `main.py` to `backend/app`. Do **not** autofix `storage.py` blindly: `AdmissionOutcomeUncertainError` and `JobCancellationRequested` are re-exported from `storage.py` and consumed by `worker.py`, `match_ingest_routes.py`, and `test_storage_job_persistence_seam.py`, so they must be declared explicitly (an `__all__` entry or a reasoned `# noqa: F401`) first. This is the H02 re-export trap at small scale; the remaining 16 (`shutil`, `ValidationError`, `JobRecord`, `json`, `deque`, `constrained_decoder`, `Interval`, `DetectionIdentity`, `TrackingIdentity`, `stream_sha256`, `ZERO`, `Iterable`, `Literal`, `admission_money`, `money`, `ProviderBudgetLedger`) should each be grepped for external consumers before removal.
3. Add one C03 regression: a wrapped model exposing only `track()` must not trigger the probe-observed pass and must not raise.
4. Amend the M01 line in the closure document to state the metric used ("13 directives unused with the debt rule set enabled; 65 directives for never-enabled rules retained intentionally").
5. Optionally reconcile the 13 local `_write_json`/`_load_json` variants in 81 scripts, deciding per family whether the trailing-newline / `sort_keys` difference is load-bearing for committed artifacts before adopting the common helper.

## 7. Post-verification cleanup addendum — 2026-09-22

The cleanup pass identified in §6 was executed on branch `cursor/audit-completion-verification-417d` before merge:

- `backend/scripts` F401: **175 → 0** under pinned Ruff 0.16.8; the cleanup log recorded `175 fixed, 0 remaining`.
- `backend/app` F401: the two intentional `storage.py` compatibility re-exports were made explicit; the remaining **16** true unused imports were removed, leaving **0**.
- C03 now has an explicit regression, `test_process_video_skips_probe_pass_for_track_only_model_with_output_parquet`, so the track-only wrapped-model contract is directly covered.
- The closure document now states the M01 metric precisely: 13 genuinely unused RUF100 directives were cleared under the debt rule set; 65 directives for otherwise-disabled rules remain because they suppress real findings when enabled.
- CI's F401 gate is widened from `backend/app/main.py` to all of `backend/app` and `backend/scripts`, preventing both residue classes from returning.

The JSON helper-family consolidation remains intentionally deferred: the 13 observed variants differ in newline / `sort_keys` semantics, so collapsing them without artifact-by-artifact evidence would be behavior-changing cleanup rather than mechanical hygiene.
