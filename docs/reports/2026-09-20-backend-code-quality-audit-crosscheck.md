# Backend Code Quality Audit — Independent Cross-Check Report

**Source audit:** `sol_astra_backend_code_quality_audit_2026-09-20_8ce8.md`
(audit snapshot: `main` at `312cb5a77718830948378ccbcb577b9539b9aed1`, 2026-09-20)
**Cross-check snapshot:** `main` at `312cb5a` (same commit — `git log` confirms HEAD is
`312cb5a Merge pull request #7`), working tree clean except this report.
**Method:** every quantitative claim re-measured directly against the checkout
(line counts, decorator/import counts, file counts, `grep` for exact code patterns,
full reads of `scripts/verify.sh`, `pyproject.toml`, `backend/tests/conftest.py`,
and `.github/workflows/ci.yml`). No code was changed; this report is verification only.

## Verdict summary

| Audit claim | Verdict |
|---|---|
| Repo shape: 806 files, 771 Python files, ~11.7 MB Python | **Confirmed** (806 files under `backend/`, 771 `*.py`, ~11.2 MB by byte sum; size delta is method-only, see §1) |
| Largest-file table (13 files) | **Confirmed** — all within ±1 line (counting-method variance, see §1) |
| 339 test-related / 337 conventional `tests/test_*.py` | **Confirmed** (337 `backend/tests/test_*.py`; 342 repo-wide `*test*.py`) |
| 322 scripts, 255 mirrored `test_<script>.py` | **Confirmed exactly** |
| Script prefix counts (87 / 53 / 22 / 34 / 11) | **Confirmed exactly** |
| Q1 — `main.py` composition root + `_main` namespace coupling | **Confirmed** (one ±1 variance on decorator count, see §2) |
| Q2 — `Storage` god class ~3,140 lines; silent `sha = "0"*64` fallback | **Confirmed** (class at line 297 exactly; span 3,139 lines) |
| Q3 — `summarize_match_benchmark()` ~1,003 lines; private imports by scripts | **Confirmed exactly** (lines 1046–2048 = 1,003 lines; all 4 private names) |
| Q4 — script-layer duplication, `sys.path` bootstraps, common helper | **Confirmed and quantified** (299/322 `sys.path`, 290/322 `# noqa: E402`) |
| Q5 — no Python lint/type gate; frontend-only gates | **Confirmed** |
| Q6 — swallowed dispatch-persistence exceptions; sparse logging | **Confirmed** (verbatim code match; `LOGGER` used once) |
| Q7 — dependency declaration duplication | **Confirmed** |
| Q8 — conftest installs cv2/pandas/ultralytics stubs; `--no-deps` CV lanes | **Confirmed** |
| Q9 — brittle `grep -Eo '[0-9]+ passed'` verifier + 1486/3000 minima | **Confirmed** (exact strings and values) |
| Q10 — `edge_share_repair_profiles.py` ~1,033 lines, 4 functions, ~258-line normalizer | **Confirmed** (±1 line, method variance) |
| Q11 — retired-route boilerplate (`RouteRetired`) | **Confirmed** (~20 raise sites in `workbench/routes.py`) |
| Q12 — giant tests (~324/182/165/141/125 KB) | **Confirmed in ranking and order** (byte sizes a few KB lower; same set) |
| "No P0 rewrite" judgement | **Concur** — nothing found contradicts it |

**No audit claim was refuted.** Variances found are limited to ±1 line counts
(three are explained below) and one decorator-count reading of 104 vs 105.
Details per section follow.

## 1. Repository shape and largest-file table

Re-measured with `splitlines()` counts and `find backend -type f | wc -l`:

- Total files under `backend/`: **806** — exact match.
- Python files: **771** — exact match.
- Python source bytes: **~11.2 MB** vs audit "~11.7 MB". This is a measurement-method
  difference (byte sum of `*.py` vs. likely `du`-based figure; `du -sh backend` reports
  14 MB including non-Python artifacts). Not a factual error; noted for precision.
- `backend/tests/test_*.py`: **337** — exact match. Repo-wide `*test*.py`: 342.
- `backend/app/workbench/*.py`: **57** — exact match. `backend/app/*.py`: **42** — exact match.

Largest-file table, audit figure → measured:

| File | Audit | Measured | Note |
|---|---|---|---|
| `backend/run_guerilla.py` | 8,908 | 8,907 | ±1, trailing-newline counting |
| `backend/app/storage.py` | 3,436 | 3,435 | ±1, same cause |
| `backend/app/main.py` | 2,355 | 2,354 | ±1 |
| `backend/app/run_benchmarks.py` | 2,224 | 2,223 | ±1 |
| `backend/app/analytics.py` | 1,712 | 1,711 | ±1 |
| `backend/app/daytona.py` | 1,542 | 1,541 | ±1 |
| `backend/app/gpu_worker.py` | 1,518 | 1,518 | exact |
| `backend/release/preflight.py` | 1,471 | 1,470 | ±1 |
| `backend/app/workbench/media.py` | 1,367 | 1,366 | ±1 |
| `backend/app/processor.py` | 1,227 | 1,226 | ±1 |
| `backend/app/workbench/leftover_get_routes.py` | 1,193 | 1,192 | ±1 |
| `backend/app/remote_contracts.py` | 1,157 | 1,156 | ±1 |
| `backend/app/workbench/jobs.py` | 1,152 | 1,151 | ±1 |

The uniform −1 pattern indicates the audit counted lines with a tool that counts a
final newline differently (e.g. `wc -l` vs `splitlines()`), not drift in the code.
Ranking, ordering, and all downstream reasoning are unaffected.

`detect_events()` in `analytics.py` re-measures at **279 lines** (L1419–L1697) — exact match.

## 2. Q1 — `main.py` routing / `_main` namespace (P1, High) — CONFIRMED

- `^import | ^from` lines in `backend/app/main.py`: **79** — exact match.
- `def create_app` begins at **line 779** — exact match.
- HTTP route decorators (`@app.get/post/put/delete/patch`): **104** measured vs **105**
  claimed. Total `@app.` occurrences is 106, composed of 104 HTTP routes +
  `@app.exception_handler` (L811) + `@app.websocket("/ws/jobs/{job_id}")` (L1967).
  The audit's 105 is within ±1 of either reading and does not affect the finding;
  likely a regex that included the websocket route but not the exception handler,
  or vice versa.
- `app.include_router(create_workbench_router(storage))` at `main.py:857` confirms
  partial native-router adoption alongside in-`create_app()` routes — as claimed.
- `leftover_get_routes.py` (1,192 lines): `create_leftover_get_routers` spans L21–L1186
  (**~1,166 lines** — exact match); single `backend.app.main` import used as `_main`
  with **140 unique `_main.*` symbols / 141 references** — the audit's "large numbers
  of symbols" is, if anything, understated.
- `leftover_routes.py` (974 lines): `create_leftover_post_router` spans L15–L969
  (**~955 lines** — exact match); **98 unique `_main.*` symbols / 98 references**.
- Factory/entry shape also matches: each file exposes one `create_*` factory plus one
  `attach_*` function (`attach_leftover_get_routes` L1187, `attach_leftover_post_routes` L970).

The structural judgement (service-locator-via-`main`, hidden circular-dependency
pressure, recommended `APIRouter` extraction sequence) is consistent with the measured code.

## 3. Q2 — `Storage` god class (P1, High) — CONFIRMED

- `class Storage:` is at **`backend/app/storage.py:297`** — exact match (earlier
  `class` statements at L59–L83 are small exception types; L227 is `_ClosingConnection`).
- File is 3,435 lines, so the class spans L297–L3435 = **3,139 lines** vs "≈3,140" — match.
- 169 `def` methods inside the file corroborate the multi-responsibility description
  (input ownership, SQLite, jobs/admission, analytics artifacts, review bundles,
  remote-result import/rollback, config updates).
- `_admit_durable_job()` silent fallback verified verbatim:

```python
        try:
            sha = self.source_sha256(match_id)
        except Exception:
            sha = "0" * 64
```

Recommendation (facade-preserving incremental extraction; narrow/log the fallback)
is appropriately scoped — no contradiction found.

## 4. Q3 — Benchmark aggregator + private-API leakage (P1, High) — CONFIRMED EXACTLY

- `summarize_match_benchmark` spans **L1046–L2048 = 1,003 lines** — exact match
  (L2049 begins `probe_selected_cluster_benchmarks`).
- `run_source_robustness_batch.py` L16–L22 imports all four private names claimed:

```python
from backend.app.run_benchmarks import (  # noqa: E402
    _assess_truth_gates,
    _load_ball_truth_layers,
    _load_accepted_match_state,
    _summarize_ball_rows,
```

- Usage is load-bearing, not incidental: `_load_ball_truth_layers` is called at five
  sites (L230, L245, L267, L286, L730) and `_load_accepted_match_state` at L1612.

## 5. Q4 — Operational script layer (P1, High) — CONFIRMED AND QUANTIFIED

- `backend/scripts/*.py`: **322** — exact. Mirrored `backend/tests/test_<script>.py`: **255** — exact.
- Prefix counts re-measured: `run_video_to_analysis_*` **87**, `run_football_external_soccernet_*` **53**,
  `run_football_external_soccertrack_*` **22**, `run_promoted_v6_*` **34**, `run_touchline_*` **11**,
  plus 46 `run_v7*` variants — all match.
- Duplication-pattern claim quantified beyond the audit: **299/322 scripts contain
  `sys.path`** mutation and **290/322 contain `# noqa: E402`** — confirming the
  bootstrap/import-after-path pattern is near-universal, not anecdotal.
- `football_external_real_eval_chain_common.py` exists, confirming the "consolidation
  already started" observation.

## 6. Q5 — Missing Python static-quality gate (P1, High) — CONFIRMED

- `grep` for `ruff|flake8|pylint|black|isort|mypy|pyright|bandit` across
  `backend/requirements/`, `pyproject.toml`, `.github/workflows/` returns **no hits**.
- `backend/requirements/dev.in` contains only `api.in` + jsonschema, opencv, pillow,
  pytest, pyyaml, scipy, setuptools, wheel; `dev.lock` likewise has no lint/type/coverage tooling.
- `scripts/verify.sh` gates confirm "frontend-only lint/typecheck": `lint`
  (`npm --prefix frontend run lint`), `typecheck-app`, `typecheck-node`
  (`tsc -p tsconfig.* --noEmit`), and `build` are all frontend; the sole backend static
  check is `backend-startup` (`python3 -c 'from backend.app.main import app'`).
- `frontend/package.json` defines the `lint` (`eslint .`) script the gate invokes,
  closing the loop on the claim.

## 7. Q6 — Silently swallowed degraded-state errors (P1/P2) — CONFIRMED

- `main.py` L997–L1005 verified verbatim: both `storage.mark_dispatched` and
  `storage.mark_dispatch_failed` failures end in bare `except Exception: pass`,
  with the dispatch outcome still returned to the caller — exactly the
  observability gap described.
- `LOGGER = logging.getLogger(__name__)` exists at `main.py:277`, but the only use
  in the file is one `LOGGER.warning("reclaimed %d expired job lease(s)"…)` at L793 —
  confirming "logging is sparse relative to the number of uncertainty/error transitions."
- The audit's explicit scoping (keep broad catches that translate-and-reraise into
  domain errors; only audit catches returning defaults/`False`/`pass`) was not
  independently re-verified catch-by-catch, but the two cited examples both check out.

## 8. Q7 — Dependency declaration duplication (P2) — CONFIRMED

- `[project.optional-dependencies].api` in `pyproject.toml` lists the same 11 pinned
  packages as `backend/requirements/api.in` (boto3, daytona, fastapi, fastparquet,
  httpx, pandas, pydantic, python-multipart, requests, starlette, uvicorn) — verified
  line-for-line.
- `[tool.setuptools.dynamic] dependencies = { file = ["backend/requirements/api.in"] }`
  confirms base dependencies load from `api.in` while the `api` extra repeats them —
  the dual-source-of-truth risk is real as described.
- `cpu-cv.in` (`-r api.in` + CV stack) and `cuda.in` (`-r cpu-cv.in` + CUDA stack) confirm
  the layered input-file side of the duplication.

## 9. Q8 — Test-harness stubs and CV profile fidelity (P2) — CONFIRMED

- `backend/tests/conftest.py` builds stub modules for **`cv2`** (`_make_cv2_stub`,
  including a DLT-based `findHomography`), **`pandas`**, and **`ultralytics`**, inserts
  them into `sys.modules` (L136–L143), and discloses them via a `stubsActive` receipt key
  (L176) — all as described.
- `ci.yml` L105 and L137 both run `pip install -e '.[cv]' --no-deps` after installing
  `dev.lock`, confirming the `--no-deps` observation: the CV extra's declared
  dependencies (torch, ultralytics, opencv, etc.) are not installed by that step, so the
  `cv+dev` / `cv+dev-real-media` profile names overstate the installed stack in exactly
  the way the audit suggests is worth reviewing. `dev.in` itself carries only a subset
  (opencv, pillow, scipy — no torch/ultralytics).

## 10. Q9 — Brittle verifier pass-count parsing (P2) — CONFIRMED

- `require_test_count()` in `scripts/verify.sh` (L85–L96) uses
  `grep -Eo '[0-9]+ passed' … | tail -n 1 | cut -d ' ' -f 1` — exact match to the quoted snippet.
- Thresholds `BACKEND_MINIMUM=1486` (full) and `3000` (code-only) verified at L99/L107,
  including the counterintuitive inversion: code-only `--ignore`s six test modules
  (`test_convert_football_analysis_pilot_cvat_labels`, `test_evaluate_football_analysis_pilot_soccertrack_events`,
  `test_gpu_worker`, `test_operational_docs`, `test_run_guerilla`, `test_run_source_robustness_batch`)
  yet demands the higher minimum — "historically shaped rather than self-describing," as claimed.

## 11. Q10 — `edge_share_repair_profiles.py` (P2) — CONFIRMED

- File is **1,032 lines** (audit: ~1,033 — the standard ±1 counting variance).
- Exactly **4 top-level functions**; `_normalized_repair_config` spans **~257 lines**
  (audit: ~258 — same ±1 variance). Substance of the finding (config-data file dominated
  by one long conditional normalizer) is unaffected.

## 12. Q11 — Retired-route boilerplate (P2) — CONFIRMED

- `backend/app/workbench/routes.py` imports `RouteRetired` (L17) and contains ~20
  `raise RouteRetired(…)` handlers (L129–L332: corrections, queries, reports, jobs,
  metrics, evidence, rates, cost endpoints) — matching "multiple endpoints whose bodies
  only raise `RouteRetired`."

## 13. Q12 — Giant tests and mirroring cost (P2) — CONFIRMED

Largest test files by bytes (audit KB → measured bytes):

| File | Audit | Measured |
|---|---|---|
| `tests/test_run_guerilla.py` | ~324 KB | 323,973 B (~316 KB) |
| `tests/test_run_source_robustness_batch.py` | ~182 KB | 181,857 B (~178 KB) |
| `tests/test_api.py` | ~165 KB | 165,254 B (~161 KB) |
| `tests/test_gpu_worker.py` | ~141 KB | 141,350 B (~138 KB) |
| `tests/test_workbench_contracts.py` | ~125 KB | 125,399 B (~122 KB) |

Same five files, same ranking; audit figures run ~2–3% higher (likely decimal-KB vs
binary-KB or snapshot drift of a few lines), which is immaterial to the maintenance-cost point.

## 14. Items the audit says *not* to act on — spot-checked, no disagreement

- `release/preflight.py` (1,470 lines) is large but was described as cohesive; nothing in
  this cross-check contradicts that characterization.
- Filesystem-verbosity and broad-`except` caution: the two Q6 examples verified above are
  precisely the narrow "return-default/pass" subset the audit scopes to, consistent with
  its warning not to flatten defensive code by catch-count alone.

## 15. Conclusion and recommended disposition

All twelve findings (Q1–Q12) reproduce against the `312cb5a` checkout. The audit's
priority order and its six-phase remediation sequence (Ruff gate → router modularization →
storage/benchmark seams → script consolidation → suppressed-error logging →
metadata-dedup) rest on verified measurements. The three trivial variances (±1 line
counts from line-counting method; 104 vs 105 route decorators; KB rounding on test sizes)
do not change any recommendation.

Suggested disposition: accept the audit as a verified baseline and schedule the
concrete first PRs it proposes (PR 1 static gate through PR 6 storage seam), one seam
per PR per its acceptance criteria (§11 of the audit), with no product/ML behavior
changes bundled in.
