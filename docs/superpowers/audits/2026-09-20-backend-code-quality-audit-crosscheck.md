# Backend Code Quality Audit — Cross-Check Against Source

**Reviewed commit:** `312cb5a77718830948378ccbcb577b9539b9aed1` (`main`, merge of PR #7) — identical to the audit's pinned snapshot
**Input reviewed:** `docs/superpowers/audits/2026-09-20-backend-code-quality-audit.md` (external code quality audit, Q1–Q12, tooling plan, PR series)
**Method:** local checkout at the pinned commit. Every metric in the audit was recomputed with `wc`, `find`, `rg`, and an `ast`-based span/import scanner. Every Q-finding was traced to the file and line it cites. Because the audit states it could not run tooling or the test suite (§3.4, §5), this pass additionally ran Ruff 0.16.8 over `backend/` and executed the full backend pytest suite under `backend/requirements/dev.lock`. No code was changed. No providers or paid workers were touched.
**Purpose:** confirm or correct each audit finding, add what the audit missed, and correct the proposed PR ordering where the source shows a hazard.

---

## 1. Verdict

The audit is accurate. All twelve Q-findings are **source-confirmed** at `312cb5a`. Every quantitative claim (file sizes, function spans, script counts, prefix counts, decorator counts, import counts, mirrored-test counts) reproduces to within one line or one item. None is overstated.

Where this pass differs, it is to sharpen:

- **Q5/Q6 interact into a concrete defect the audit predicted but did not find.** A production route handler references an undefined name; the resulting `NameError` is swallowed by `except Exception:` and the contract test passes on the swallowed error (N01).
- **The audit's PR 1 (Ruff, "fix only unambiguous violations") before PR 3 (remove the `_main` namespace) is unsafe in the stated order.** 173 of `main.py`'s 175 "unused" imports are consumed only through `_main.<name>` aliasing in the leftover routers, and those routers are built on every `create_app()` call. `ruff --fix` on F401 would break startup (N02).
- **Q6 understates the observability gap.** "Logging is sparse" is generous: the entire `backend/app` package contains one logging call (N03).
- **Q4 understates existing consolidation and misdiagnoses the gap.** The common helper module the audit mentions is already imported by 221 of 322 scripts; the problem is that 115 of those scripts still carry an identical local copy of a helper the module already exports (N05).
- **The "3,583 passed" figure the audit cites (§3.4) is the code-only selection, not the full suite.** The full selection collects 4,181 tests; the 594 in the six code-only-excluded modules run in no routine CI lane, and 22 of them fail at `main` under `dev.lock` — several for environment-independent reasons (N09).

Disposition: proceed with the audit's remediation direction. Reorder PR 1 and PR 3 as described in §7, and add the N09 repair as a Phase A guardrail item, since the audit's later refactors of `run_guerilla.py` and the benchmark scripts would otherwise be protected by tests that nothing runs.

## 2. Objective metrics — audit claim vs. measured

| Metric | Audit | Measured at `312cb5a` | Status |
|---|---:|---:|---|
| Files under `backend/` | 806 | 806 | exact |
| Python files | 771 | 771 | exact |
| Python source bytes | ~11.7 MB | 11,696,881 | exact |
| `tests/test_*.py` | 337 | 337 | exact |
| Test-related Python files | 339 | 342 (broad name match) | within detection variance |
| Scripts under `backend/scripts/` | 322 | 322 (excl. `__init__.py`) | exact |
| Scripts with exact `tests/test_<script>.py` mirror | 255 | 255 | exact |
| `run_video_to_analysis_*` | 87 | 87 | exact |
| `run_football_external_soccernet_*` | 53 | 53 | exact |
| `run_football_external_soccertrack_*` | 22 | 22 | exact |
| `run_promoted_v6_*` | 34 | 34 | exact |
| `run_touchline_*` | 11 | 11 | exact |
| `run_v7*` | "many" | 46 | consistent |
| Modules in `backend/app/workbench/` | 57 | 57 | exact |
| Modules directly under `backend/app/` | 42 | 42 | exact |

Largest-file table: every row reproduces within one line (`wc -l` counts newlines; the audit counted lines). `run_guerilla.py` 8,907; `storage.py` 3,435; `main.py` 2,354; `run_benchmarks.py` 2,223; `analytics.py` 1,711; `daytona.py` 1,541; `gpu_worker.py` 1,518; `release/preflight.py` 1,470; `workbench/media.py` 1,366; `processor.py` 1,226; `leftover_get_routes.py` 1,192; `remote_contracts.py` 1,156; `workbench/jobs.py` 1,151.

## 3. Q1–Q12 verification table

| Q | Audit claim | Verified at `312cb5a` | Sharpening |
|---|---|---|---|
| Q1 | `main.py` ~2,355 lines, ~79 imports, 105 route decorators; `create_app()` from ~L779 owns most of the file; leftover routers copy symbols from `backend.app.main as _main` | **Confirmed.** 79 top-level import statements. 104 `@app.<verb>` decorators + 1 `@app.websocket` = 105 (plus one programmatic `app.add_api_route` loop at L630 and one `@app.exception_handler`). `create_app()` spans L779–2351 (1,573 lines). `create_leftover_get_routers()` L21–1184 (1,164 lines); `create_leftover_post_router()` L15–967 (953 lines). Both do `import backend.app.main as _main` inside the factory (L22 / L16). | **208 distinct symbols** are aliased through `_main.` (141 references in the GET module, 98 in the POST module). The dependency is genuinely circular and only works because both sides defer their imports (`main.py` L858–860 imports the leftover modules inside `create_app()`). The routers are built unconditionally on every `create_app()` — the `leftover_http` flag only controls whether they are *also* mounted under `/api` (L1189–1191); they always mount under `/api/workbench/dev`. See N02 for the consequence. |
| Q2 | `Storage` from ~L297 to EOF (~3,140 lines); `_admit_durable_job()` converts any `source_sha256` exception to `"0"*64` | **Confirmed.** `class Storage` L297–3435 (3,139 lines, 158 methods). `_admit_durable_job` L694; the `try/except Exception: sha = "0"*64` is at L707–710. | `source_sha256()` (L731–739) already returns `"0"*64` itself when the file is missing or not a regular file, so the broad catch only adds coverage for I/O errors during hashing (`PermissionError`, `OSError`) and for programming errors. L715 `sourceSha256=sha or "0"*64` is redundant with both. Method-name clustering: 47 `*match*`, 13 `*generation*`, 11 `*review*`, 8 `*job*`, 51 unclassified — the seams the audit names are visible in the names. |
| Q3 | `summarize_match_benchmark()` ~L1046–2048, ~1,003 lines; `run_source_robustness_batch.py` imports `_assess_truth_gates`, `_load_ball_truth_layers`, `_load_accepted_match_state`, `_summarize_ball_rows` | **Confirmed.** L1046–2046, 1,001 lines. The four private imports are at `scripts/run_source_robustness_batch.py` L19–22. | Across all 322 scripts there are only **6** private-name imports from `backend.app.*`: the four above, `daytona._UnreturnedSandboxCleanupError`, and `daytona_worker_image._copy_context_member`. The leakage is real but narrow; promotion is a small, bounded change. Additionally, `MatchBenchmarkSummary` (L89–265) declares **10 fields twice** with identical definitions (L124–133 and L177–186) — see N04. |
| Q4 | 322 scripts; 255 mirrored tests; repeated repo-root discovery, `sys.path.insert`, `# noqa: E402`, JSON/time/float helpers | **Confirmed.** 299/322 scripts call `sys.path.insert`; 286 carry `# noqa: E402`; 301 define `REPO_ROOT`. Local helper copies: `_utc_now_iso` ×180, `_candidate_root` ×114, `_write_json` ×76, `_safe_float` ×51, `_load_json_dict` ×38, `_load_json` ×36. All 180 `_utc_now_iso` bodies are byte-identical. 314/322 have a `__main__` guard. | The audit says "some consolidation already exists" in `football_external_real_eval_chain_common.py`. It is more than some: **221/322 scripts import it**, and 251 scripts import at least one other script (max import chain depth 5). The module already exports `utc_now_iso`, `candidate_root`, `write_json`, `load_json`, `reset_output`, `main_for`. The gap is adoption, not absence — see N05. Only two scripts are invoked from CI/verifier (`write_lane_receipt`, `write_verification_evidence`), both via `python3 -m backend.scripts.<name>`, so the module-invocation convention the audit recommends is already the one the repo's own tooling uses. |
| Q5 | No Ruff/Flake8/Pylint/Black/isort/Mypy/Pyright/Bandit/coverage in any lock or CI; lint/typecheck gates are frontend-only | **Confirmed.** None of those names appears in `backend/requirements/*.in`, `*.lock`, `backend/requirements*.txt`, `pyproject.toml`, `.github/workflows/ci.yml`, or `scripts/verify.sh`. `verify.sh` runs `npm run lint` and two `tsc` passes; the only Python "static" gate is `python3 -c 'from backend.app.main import app'`. | Ruff run at this commit (§4): **0 syntax errors** across 771 files; **1 undefined name (F821)**, 1 redefinition (F811), 13 unused locals (F841), 235 unused imports (F401, 175 of them in `main.py`), 76 stale `# noqa` directives, 24 `try/except/pass`, ~170 blind `except Exception`. The F821 is a live defect (N01). |
| Q6 | `main.py` ~L997–1005 catches `mark_dispatched`/`mark_dispatch_failed` failures with `except Exception: pass`; logging is sparse | **Confirmed.** L997–1005 exactly as described; both are `pass`. | Stronger than stated: `backend/app` has **one** logging call in total (`LOGGER.warning(...)` at `main.py` L793, lease reclamation). Every other module in the package — `storage.py` (15 `except Exception`), `daytona.py` (28), `gpu_worker.py` (23), `remote_contracts.py` (29), `remote_worker.py` (18) — has zero log emission. Ruff S110 (`try/except/pass`) fires 24 times in production code, none in tests. See N03. |
| Q7 | `pyproject.toml` optional extras duplicate `api.in`/`cpu-cv.in`/`cuda.in`; base deps are dynamic from `api.in` so the `api` extra repeats them | **Confirmed.** `[project.optional-dependencies].api` is the same 11 pins as `api.in`; `cv` is `cpu-cv.in` minus its `-r api.in`; `cuda` is `cuda.in` with markers reformatted. `[tool.setuptools.dynamic] dependencies = { file = ["backend/requirements/api.in"] }`. No test compares the two representations (tests reference `api.in` only for release policy). | A third representation exists that the audit did not list: `backend/requirements.txt`, `requirements-dev.txt`, `requirements-ml.txt`, `requirements-runtime.txt` — one-line compatibility includes that point at the locks. They are not a drift risk (no pins), but docs still reference them (`docs/PROJECT-EXPLANATION.md`, `docs/superpowers/plans/2026-09-18-...`), so any single-source decision should say what happens to them. |
| Q8 | `conftest.py` stubs `cv2`/`pandas`/`ultralytics` into `sys.modules`; `integration`/`real-media` lanes install `dev.lock` then `pip install -e '.[cv]' --no-deps`, so the CV extra's deps are not installed; profile name `cv+dev` overstates content | **Confirmed.** Stub loop at `conftest.py` L136–144, disclosed via `stubs_active:` terminal line and `stubsActive` in the receipt (L154, L176). `ci.yml` L105 and L137 use `--no-deps`. `dev.in` pins opencv/pillow/scipy/pyyaml but no torch/torchvision/ultralytics. | Locally, with `dev.lock` installed, the suite reports `stubs_active: ultralytics` — consistent with the CI receipts the prior cross-check cited. The only "real import" of the CV stack anywhere in CI is the **negative** assertion in `api-profile` (`find_spec('ultralytics') is None`); `test_gpu_acceptance.py` does `import torch` but runs only on the manual GPU lane. The audit's "add one explicit real-import smoke" recommendation stands. |
| Q9 | `verify.sh` parses `grep -Eo '[0-9]+ passed'`; minimums 1,486 (full) vs 3,000 (code-only) are counterintuitive | **Confirmed.** `require_test_count` L86–96; `BACKEND_MINIMUM=1486` L99, raised to 3000 at L107 inside the code-only branch that also `--ignore`s six modules. | `tests/test_verify_script.py` hard-codes the same numbers (L145, L531, L539–541, L551–552) with fake pytest output. Changing or removing the count gate therefore requires touching that test too; it is not a `verify.sh`-only edit. |
| Q10 | `edge_share_repair_profiles.py` ~1,033 lines, 4 functions; `_normalized_repair_config()` ~258 lines of repeated coercion | **Confirmed.** 1,032 lines, exactly 4 functions; `_normalized_repair_config` L745–1000 (256 lines) with 81 `.get(` calls, 35 `bool(`, 17 `int(`, 14 `float(`. 732 of 1,032 lines are top-level data assignments. | — |
| Q11 | `create_workbench_router()` contains endpoints whose bodies only `raise RouteRetired`; legacy routers separately feature-gated | **Confirmed.** 19 `raise RouteRetired` sites in `workbench/routes.py` (L129–332). In addition, `main.py` L610–636 programmatically registers a retired 410 endpoint under `/api/...` for every dev-prefixed leftover route not already claimed. | The retired routes are **tested as a contract**: `tests/test_audit_v2_h02_review.py::test_t01_normal_routes_persist_and_compatibility_authorities_are_retired` asserts `410` and a fixed body for `POST /api/workbench/jobs` and `POST /api/workbench/matches/{id}/jobs`. The audit's "validate before deleting" caveat is therefore load-bearing: these are not dead boilerplate, they are the mechanism by which the H02 remediation proved the old authorities are closed. |
| Q12 | `test_run_guerilla.py` ~324 KB, `test_run_source_robustness_batch.py` ~182 KB, `test_api.py` ~165 KB, `test_gpu_worker.py` ~141 KB, `test_workbench_contracts.py` ~125 KB | **Confirmed** (audit uses KB = 1,000 bytes; in KiB: 316 / 178 / 161 / 138 / 122). `test_daytona.py` (111 KB) and `test_run_benchmarks.py` (105 KB) are the next two. | — |

Also confirmed: §3.4's citation of the merge commit message ("Full backend 3583 passed/4 skipped") is verbatim in `git log -1 312cb5a`. The audit did not rerun the suite; this pass did — see §5.

## 4. Ruff baseline at `312cb5a` (Ruff 0.16.8, no config file present)

Run from the repo root with `--no-cache`. There is no `ruff.toml`, `.ruff.toml`, or `[tool.ruff]` anywhere in the tree, so these are the tool's defaults plus explicit selections.

| Selection | Result |
|---|---|
| `E9` (syntax) | 0 — every one of the 771 files parses |
| `F` (pyflakes) | 251: F401 ×235, F841 ×13, F541 ×1, F811 ×1, F821 ×1 |
| `E402,RUF100` | 29 unsuppressed E402; 76 truly stale `# noqa` (57 in `tests/`, 15 in `scripts/`, 4 in `app/`) — e.g. `# noqa: ANN001`, `# noqa: S603`, `# noqa: BLE001` for rules that were never enabled |
| `S110` (try/except/pass) | 24, all in production modules (`daytona.py` ×5, `storage.py` ×5, `remote_contracts.py` ×3, `main.py` ×2, `remote_worker.py` ×2, `run_guerilla.py` ×2, one each in `gpu_worker.py`, `processor.py`, `runtime_options.py`, `workbench/jobs.py`, `workbench/media.py`) |
| `BLE001` (blind except) | ~170 (121 `app/`, 25 `scripts/`, 10 `app/workbench/`, 7 backend root) |
| `B` (bugbear) | 186: B008 ×91 (FastAPI `Header(default=...)` pattern — expected), B023 ×43 (closure over loop variable — needs triage, see N08), B905 ×30, B017 ×17, B904 ×3 |
| `PIE794` | 10 — all in `MatchBenchmarkSummary` (N04) |
| `PLR0124` | 6 — all `x != x` NaN idioms in `run_benchmarks.py` L505/L681 and `run_source_robustness_batch.py` L164; intentional, would need `math.isnan` or a suppression |
| Tool default rule set | 2,934 total, dominated by RUF100 ×734 (mostly `# noqa: E402` counted as unused because E402 is not in the default set), I001 ×715, UP017 ×273, F401 ×235 |

Reading: the audit's prediction that tests do not catch "undefined names in unexecuted branches" and "stale `# noqa` directives" is borne out by one F821 and 76 RUF100. The volume of mechanical findings (I001, UP017) supports the audit's advice to start with correctness rules only.

## 5. Test suite execution at `312cb5a`

Environment: Python 3.12.3, `backend/requirements/dev.lock` installed with `--require-hashes`, `pip install -e . --no-deps`, `pip install -e ./research-addon`, `QT_QPA_PLATFORM=offscreen`. `pandas` and `cv2` real; `ultralytics` stubbed (`stubs_active: ultralytics`).

Command: `python3 -m pytest -q backend/tests` (no `--ignore` flags, i.e. the *full* selection, not the code-only one)

Result: **22 failed, 4,153 passed, 6 skipped in 29m 23s.**

All 22 failures are in the six modules that `scripts/verify.sh` excludes under `VERIFY_CODE_ONLY=1`:

| Module | Failures | Observed cause |
|---|---:|---|
| `test_run_guerilla.py` | 9 | 1× `ModuleNotFoundError: ultralytics` in a subprocess import (the conftest stub does not reach child processes). 3× `AttributeError: 'FakeModel' object has no attribute 'predict'` — the test's fake defines only `track`, while `process_video` (L8364) guards on `hasattr(probe_model, "predict")` against the `_CountingPredictor` wrapper and then calls `predict` on the wrapped fake (L5224). 2× `_CountingPredictor is not FakeAuxiliary...` identity assertions, 2× heartbeat assertions, 1× `TypeError: only 0-dimensional arrays can be converted to Python scalars` at `workbench/perception.py` L206 under numpy 2.4.6 (the version `dev.lock` pins). |
| `test_operational_docs.py` | 8 | `test_historical_provider_recipe_module_cli_exits_nonzero[...]`: the CLI exits nonzero as required, but `"retired"` is absent from stderr — the script fails on an import before it reaches its retirement guard, so the test cannot distinguish "retired" from "broken". |
| `test_gpu_worker.py` | 3 | `PermissionError` on `os.rename`/`open` inside the test's own fixture setup against `tmp_path`; filesystem-sensitive, not diagnosed further. |
| `test_evaluate_football_analysis_pilot_soccertrack_events.py` | 1 | `FileNotFoundError` under `backend/storage/trained_detector_candidates/...` — needs restored artifacts. |
| `test_convert_football_analysis_pilot_cvat_labels.py` | 1 | `FileNotFoundError` under `backend/storage/cvat-manifest-test-...` — needs restored artifacts. |

Reconciliation with the merge commit message ("Full backend 3583 passed/4 skipped"): the six excluded modules collect **594** tests; 4,181 collected − 594 = **3,587 = 3,583 passed + 4 skipped**. The number the commit message labels "Full backend" is the **code-only** selection. The audit's §3.4 repeats that label. The genuinely full suite at `312cb5a` does not pass in a `dev.lock` environment — see N09.

## 6. Additional findings (not in the audit)

### N01 — `/api/decode/export` handler raises `NameError`; the contract test passes on the swallowed exception (P1 for test fidelity; low runtime impact)

**Path (verified):** `backend/app/workbench/leftover_routes.py` L654–670. The handler calls `probe.export_clip(Path(source_url), ...)`. `Path` is not imported at module level (L1–12 import only FastAPI, schemas, storage, access, leftover_http, recovery), is not among the 98 `_main.<name>` aliases in the factory, and is not a closure variable. Evaluating `Path(...)` in the handler's namespace raises `NameError: name 'Path' is not defined`. The handler's `except Exception:` (L668) converts this to `{"admitted": False, "reasonCodes": ["UNCONSTRAINED_DECODER"]}`.

`tests/test_api.py::test_production_decode_challengers_heatmap_and_grounding_surfaces` (L3367–3374) posts to `/api/decode/export` and asserts status 200, `admitted is False`, and that a reason code contains `UNCONSTRAINED`. All three assertions are satisfied by the `NameError` path. `FfmpegProbe.export_clip()` and `_admit_local_decode_path()` are never reached from this route, so the test verifies nothing about decoder admission.

Reproduced at `312cb5a` by direct `TestClient` call (returns `200 {"admitted":false,"reasonCodes":["UNCONSTRAINED_DECODER"]}`) and by evaluating `Path('x')` against `endpoint.__globals__` (raises `NameError`).

**Why it matters:** this is the exact failure class the audit predicts under Q5 ("undefined names in unexecuted branches") compounded by Q6 (broad catch hides a programming error). Ruff `F821` finds it in under a second. Runtime impact is small — the route is a leftover contract that refuses in every branch — but the test suite's green status here is unearned.

**Repair:** `from pathlib import Path` in `leftover_routes.py`; then decide whether the handler's `except Exception:` should stay. The test should be tightened to assert a reason code that only `export_clip`'s real admission path can produce, so that the handler cannot pass by accident again.

### N02 — Ruff auto-fix of F401 in `main.py` would break every `create_app()` call; PR 1 and PR 3 must be reordered (P1 for the remediation plan)

**Path (verified):** Ruff reports 175 F401 violations in `backend/app/main.py`. Cross-referencing each name against `_main\.<name>` in the two leftover router modules shows **173 of 175** are consumed only through the alias (`ground_output`, `select_evidence`, `authorize_object`, `constrained_decoder`, `deployment_encryption`, `least_privilege_storage`, ...). Only `typing.Literal` and `TrackerAdapter` are truly unused.

Because `attach_leftover_post_routes(app, storage)` and `attach_leftover_get_routes(app, storage)` run unconditionally inside `create_app()` (`main.py` L862–863) and the factories read every alias eagerly (`constrained_decoder = _main.constrained_decoder`, etc.), deleting any of those imports produces `AttributeError: module 'backend.app.main' has no attribute ...` at application construction — i.e. before any route is served. The `backend-startup` verifier gate would catch it, but only after the damage is in the branch.

**Consequence for the audit's plan:** the audit's PR 1 says "fix only unambiguous violations." F401 in `main.py` looks unambiguous to the tool and is not. The audit's PR 3 ("stop importing `backend.app.main as _main`; import real owning symbols") is the change that makes those 173 imports genuinely removable.

**Repair:** either (a) land PR 3 before any F401 cleanup of `main.py`, or (b) in PR 1 add `[tool.ruff.lint.per-file-ignores] "backend/app/main.py" = ["F401"]` with a comment pointing at the leftover routers, and remove the ignore in PR 3. Do not run `ruff --fix` on `main.py` in PR 1 under either option.

### N03 — `backend/app` has one logging call in ~50,000 lines of production Python (P2, sharpens Q6)

**Path (verified):** `rg 'LOGGER\.|getLogger' backend/app backend/run_guerilla.py` returns two lines: the logger definition (`main.py` L277) and one `LOGGER.warning` (`main.py` L793). No other module in `backend/app/` or `backend/app/workbench/` defines or uses a logger, and there are no `warnings.warn` calls. Against that: 24 `try/except/pass` sites and ~170 `except Exception` sites in production code.

The audit's framing ("logging is sparse relative to the number of uncertainty/error transitions") is correct in direction but the number is one. Every "uncertain" dispatch outcome, every rollback, every swallowed persistence error, and every suppressed filesystem exception in `storage.py`/`daytona.py`/`gpu_worker.py` currently leaves no trace outside the response body or the returned enum.

**Repair:** as the audit says — add a module logger and one `LOGGER.warning`/`LOGGER.exception` at each of the 24 S110 sites and at the `_admit_durable_job` sentinel; do not narrow or remove the catches in the same change. This is the audit's Phase A item 4 and it is smaller than it sounds: 24 sites, ~30 lines.

### N04 — `MatchBenchmarkSummary` declares ten fields twice (P3, evidence for Q3)

**Path (verified):** `backend/app/run_benchmarks.py` L124–133 and L177–186 are byte-identical: `acceptedMatchStateFrames`, `acceptedMatchStateCoverageRatio`, `visibleStateFrames`, `inferredStateFrames`, `hiddenStateFrames`, `controlledStateFrames`, `hiddenControlledStateFrames`, `restartOrOutStateFrames`, `stateContinuityAppliedFrames`, `matchStateModeCounts`. Pydantic accepts the later definition silently, so behavior is unaffected. Ruff `PIE794` reports all ten.

This is a copy-paste artefact in the model the audit says must be preserved "exactly" during the Q3 decomposition. Delete the second block before decomposing so the "exact" target is the deduplicated one.

### N05 — Script consolidation: the shared module exists and is widely imported; the duplication is unadopted exports (P2, sharpens Q4)

**Path (verified):** `backend/scripts/football_external_real_eval_chain_common.py` exports `utc_now_iso`, `candidate_root`, `write_json`, `load_json`, `sha256_file`, `reset_output`, `guardrails_false`, `standard_false_flags`, `write_outcome`, `build_parser`, `main_for`. 221 of 322 scripts import from it. Nonetheless 180 scripts define a private `_utc_now_iso` with the identical body `return datetime.now(timezone.utc).isoformat()`, and **115 of those 180 already import the common module** that exports the same function under `utc_now_iso`. The same pattern holds for `_candidate_root` (114) and `_write_json` (76).

The audit's "one shared helper module and thin wrappers are enough" is correct, and the module is already there. PR 5 should not create a new helper module; it should replace the local copies with the existing exports, one chain at a time as the audit proposes. `video_to_analysis_operational_sprint_common.py` (imported by 27 scripts) is the second consolidation point and should be checked for overlap with the first before either grows.

### N06 — `verify.sh` thresholds are also pinned in `tests/test_verify_script.py` (P3, extends Q9)

**Path (verified):** `test_verify_script.py` L145 (`1486 passed in 1.00s` in a fake pytest), L531, L539–541 (`("backend", "1485 passed in 1.00s", 1486)` boundary cases), L551–552. Any change to `BACKEND_MINIMUM`, the sidecar 37, or the frontend 46, or removal of `require_test_count`, requires updating this test in the same PR. The audit's alternative (collection-based guard or exit-status-only) should be scoped to include it.

### N07 — 76 `# noqa` directives suppress rules that have never been enabled (P3, extends Q5)

**Path (verified):** With `E402` enabled and `RUF100` selected, Ruff reports 76 unused suppressions: `# noqa: ANN001`/`ANN202` (`storage.py` L240, `proof_runtime.py` L29, `conftest.py`), `# noqa: S603` (`workbench/media.py` L389, L616), `# noqa: BLE001` (`scripts/run_benchmark_suite.py` L260), and 57 in `tests/`. These are residue from an earlier linter configuration that is no longer in the repo. They are all auto-fixable and are a safe inclusion in PR 1. Separately, 29 `E402` violations are *not* suppressed, so any E402-enabled gate needs either those fixes or per-file ignores for `scripts/`.

### N08 — 43 closures capture loop variables (B023); the `run_guerilla.py` cluster needs triage (P2, unverified as bugs)

**Path (observed, not traced):** Ruff `B023` fires 43 times; the densest cluster is `run_guerilla.py` L1986–1999 (`selected_windows`, `sampled_frame_id`, `seed_mode`, `seed_center*` captured by inner functions defined in a loop). B023 is a late-binding hazard only if the closure is called after the loop advances. At the `run_guerilla.py` cluster the inner function is a `nonlocal`-heavy per-frame helper that appears to be invoked within the same iteration that defines it, which would make the capture benign; that was not traced to completion in this pass, and it is algorithmic code the audit says not to touch casually. Recording it so PR 1's rule selection can include `B023` as a report-only rule and the algorithm owner can confirm each site.

### N09 — 594 tests in six modules are excluded from every routine CI lane, and 22 of them fail at `main` (P1 for the audit's "well-tested" premise)

**Path (verified):** `scripts/verify.sh` L100–107 `--ignore`s `test_convert_football_analysis_pilot_cvat_labels.py`, `test_evaluate_football_analysis_pilot_soccertrack_events.py`, `test_gpu_worker.py`, `test_operational_docs.py`, `test_run_guerilla.py`, `test_run_source_robustness_batch.py` when `VERIFY_CODE_ONLY=1`, which is how the CI `verify` job runs (`ci.yml` L50). The `integration` and `real-media` jobs select by marker only (`-m "integration or real_media"`, `-m real_media`). The `gpu-acceptance` job runs `test_gpu_worker.py` and `test_run_guerilla.py`, but only on `workflow_dispatch` with two approval inputs. Consequently:

- `test_operational_docs.py`, `test_run_source_robustness_batch.py`, `test_convert_football_analysis_pilot_cvat_labels.py`, `test_evaluate_football_analysis_pilot_soccertrack_events.py` are run by **no** CI lane on push or PR.
- `test_run_guerilla.py` and `test_gpu_worker.py` run only when a human dispatches the GPU lane.

Running the full selection locally under `dev.lock` (§5) shows 22 failures, all in these modules. Two are artifact-dependent by design (`backend/storage/...` restore), one is dependency-dependent (`ultralytics` in a subprocess), and eight in `test_operational_docs.py` are a test that cannot tell "retired" from "import failed". But the `FakeModel`/`predict` failures in `test_run_guerilla.py` are environment-independent: the fake and the production guard disagree, and both were introduced in the same commit (`d557702`). `test_run_source_robustness_batch.py` (the audit's Q3 example, 178 KB) happened to pass here, but nothing in CI would notice if it stopped.

**Why it matters for the audit:** the audit's overall assessment rests on "Runtime correctness discipline: Strong — extensive pytest suite". The suite is extensive, but 14% of it (594/4,181) is outside the routine gate, and the part that guards the largest production file (`run_guerilla.py`, 8,907 lines) is in that 14%. The audit's Q9 observation that the verifier's thresholds are "historically shaped" is a symptom of the same thing: the 1,486 full-mode minimum was set when the full selection was much smaller, and no lane has exercised full mode since.

**Repair (bounded, no product change):** (1) fix the `hasattr(probe_model, "predict")` guard or the three fakes so the recovery-path tests pass without ultralytics; (2) make `test_historical_provider_recipe_module_cli_exits_nonzero` assert the retirement message from a controlled import environment or skip when the module's imports are unavailable; (3) add a CI lane — or extend `integration` — that runs the four never-run modules with the artifact-dependent tests marked and skipped explicitly rather than excluded by filename; (4) relabel the verifier's output so "full" and "code-only" counts are never conflated in commit messages again.

## 7. Adjustments to the audit's PR sequence

| Audit PR | Adjustment |
|---|---|
| PR 1 — Backend static gate | Select `E9,F,B023,PIE794,RUF100` (with `E402` enabled) initially; leave `I`, `UP`, style rules off. **Per-file-ignore `F401` for `backend/app/main.py`** until PR 3 lands (N02). Fix: `leftover_routes.py` `Path` import (N01), `Literal`/`TrackerAdapter` in `main.py`, 13 F841, 76 RUF100, F541, F811 (`support_bundle` shadowing at `leftover_routes.py` L12/L108). Tighten the `/api/decode/export` test at the same time (N01). |
| PR 2 — API composition cleanup | No change. |
| PR 3 — Legacy router dependency cleanup | Move ahead of any `main.py` import cleanup. After PR 3, remove the per-file-ignore and let F401 delete the 173 re-exports. The 208-symbol alias list in §3 Q1 is the exact worklist. |
| PR 4 — Benchmark summary decomposition | Delete the duplicated field block (N04) as the first commit so that "preserve `MatchBenchmarkSummary` exactly" targets the deduplicated model. |
| PR 5 — Script bootstrap/common-helper cleanup | Do not add a helper module. Replace local `_utc_now_iso`/`_candidate_root`/`_write_json`/`_load_json` with the existing `football_external_real_eval_chain_common` exports, starting with the 115 scripts that already import it (N05). |
| PR 6 — Storage seam extraction | No change. Add the `_admit_durable_job` log line and the 5 `storage.py` S110 log lines here or in Phase A (N03). |
| Phase A item 4 (log suppressed errors) | Scope is 24 S110 sites + 1 sentinel; see N03. |
| Q9 (verifier count gate) | Include `tests/test_verify_script.py` in scope (N06). |
| Phase A (new item) | Bring the six code-only-excluded modules under a routine lane before Phase C/D touch `run_guerilla.py` or the benchmark/robustness scripts; fix the environment-independent `test_run_guerilla.py` failures first (N09). |

## 8. What this pass did not verify

- Whether any of the 43 `B023` sites is a live bug (N08 is report-only).
- The ~170 `BLE001` blind catches individually. The audit's §10 caution that most are legitimate boundary translation was spot-checked in `daytona.py` and `remote_contracts.py` and holds for the sampled sites; it was not exhaustively traced.
- The frontend and sidecar suites (audit scope is `backend/` only; the merge commit's frontend/sidecar counts were not rerun).
- Root cause of the three `test_gpu_worker.py` `PermissionError` failures and the two heartbeat/two identity-assertion failures in `test_run_guerilla.py` (§5). They are recorded as observed; only the `FakeModel`/`predict` trio was traced to a specific code/test disagreement.
- Whether the `numpy 2.4.6` `TypeError` in `workbench/perception.py` L206 also reproduces under the `cpu-cv` lock's `numpy==2.4.2`.
- The "low thousands of lines" deletion estimate in §9. The identical-helper duplication alone accounts for roughly 180×2 + 114×3 + 76×4 ≈ 1,000 lines; script archival was not assessed because it requires per-script caller validation the audit itself defers.
- CI artifact contents for `312cb5a` (the receipt's `stubsActive` was inferred from a local run with the same lock, not downloaded).
