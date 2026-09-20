# Sol Astra Football Analyses — Backend Code Quality Audit

**Repository:** `ms81labs/sol-astra-football-analyses-sept26`  
**Scope:** `backend/` only, with root packaging/CI files inspected only where they directly govern backend quality  
**Snapshot:** `main` at merge commit `312cb5a77718830948378ccbcb577b9539b9aed1` (2026-09-20)  
**Review lens:** code quality, maintainability, correctness-risk, testability, tooling, dependency hygiene, error handling, and unnecessary complexity. **No product-direction changes.**  
**Methods:** GitHub repository tree inspection, targeted full-file/range reads, structural metrics, Superpowers evidence-first review, and Ponytail whole-repo simplification audit.

---

## 1. Executive summary

The backend is **well-tested and unusually defensive around filesystem, remote-execution, and release-boundary code**, but it has accumulated a second kind of complexity: very large orchestration modules, route factories that act as namespaces, a huge population of milestone/approval scripts, and no Python static-quality gate in CI.

This is not a case where the codebase needs a rewrite. The highest-value work is **behavior-preserving extraction and consolidation** around a few hotspots while preserving the existing public contracts and security semantics.

### Overall assessment

| Area | Assessment | Notes |
|---|---|---|
| Runtime correctness discipline | Strong | Extensive pytest suite, explicit uncertainty states, release/preflight checks |
| Security/FS defensive coding | Strong | descriptor-based no-follow patterns, atomic/durable publication logic, fail-closed validation |
| API/module cohesion | Weak | `main.py` and legacy router factories own too much wiring |
| Storage cohesion | Weak | one `Storage` class spans ~3,140 lines |
| Benchmark/analysis aggregation | Weak | one benchmark summary function is ~1,003 lines |
| Script maintainability | Weak | 322 Python scripts; 255 have exact mirrored `test_<script>.py` files |
| Python lint/type tooling | Missing | no Ruff/Flake8/Pylint/Black/Mypy/Pyright in backend dev locks or CI |
| Dependency reproducibility | Strong | hash-locked profiles and dry-run CI checks |
| Dependency declaration hygiene | Mixed | `pyproject.toml` duplicates API/CV/CUDA declarations already present in requirement inputs |
| Observability of degraded states | Mixed | some important exceptions are deliberately swallowed or converted without logging |

### Priority order

1. **Add one Python static-quality gate (Ruff) and make it parse the whole backend.**
2. **Decompose FastAPI routing using native `APIRouter`; stop using `backend.app.main` as a service-locator namespace.**
3. **Reduce the `Storage` class and `summarize_match_benchmark()` change radius without changing their public behavior.**
4. **Consolidate the operational script surface into reusable library functions + thin runners; remove `sys.path` bootstraps.**
5. **Fix silent operational-error handling and clarify test-stub/CI profile fidelity.**
6. **Remove configuration duplication and brittle verifier bookkeeping.**

No P0 “rewrite now” issue was established from this review.

---

## 2. Repository shape and objective metrics

The backend tree currently contains approximately:

- **806 files** total
- **771 Python files**
- **~11.7 MB of Python source**
- **339 test-related Python files** by broad filename/path detection (337 conventional `tests/test_*.py` files)
- **322 Python scripts** under `backend/scripts/`
- **57 modules** in `backend/app/workbench/`
- **42 modules** directly under `backend/app/`

The quantity of tests is a major strength, but the ratio also exposes a structural issue: the operational-script surface is almost as large as the test suite.

### Largest production Python files observed

| File | Approx. lines | Quality implication |
|---|---:|---|
| `backend/run_guerilla.py` | 8,908 | very high change radius; central algorithm/runtime file |
| `backend/app/storage.py` | 3,436 | `Storage` class alone spans ~3,140 lines |
| `backend/app/main.py` | 2,355 | 105 FastAPI route decorators; ~79 imports |
| `backend/app/run_benchmarks.py` | 2,224 | contains a ~1,003-line function |
| `backend/app/analytics.py` | 1,712 | event detection function ~279 lines |
| `backend/app/daytona.py` | 1,542 | remote lifecycle + cleanup + contract translation |
| `backend/app/gpu_worker.py` | 1,519 | worker filesystem/publication lifecycle |
| `backend/release/preflight.py` | 1,471 | large but cohesive release validation boundary |
| `backend/app/workbench/media.py` | 1,367 | multiple decode backends and media concerns |
| `backend/app/processor.py` | 1,227 | orchestration layer |
| `backend/app/workbench/leftover_get_routes.py` | 1,193 | router factory spans ~1,166 lines |
| `backend/app/remote_contracts.py` | 1,157 | strict remote contract parser/validator |
| `backend/app/workbench/jobs.py` | 1,152 | workbench job behavior |

**Important:** file size alone is not the finding. Some large release/security modules are internally cohesive. The concern is where a large file also mixes responsibilities or becomes an import namespace.

---

## 3. What is already good and should be preserved

### 3.1 Defensive filesystem code is intentionally verbose

`storage.py`, `daytona.py`, `gpu_worker.py`, remote contracts, and the review tooling use descriptor-level operations, `O_NOFOLLOW`, inode/size checks, fsync/rollback semantics, explicit uncertain outcomes, and fail-closed checks. Prior Superpowers remediation reports show these behaviors were added with real fault-injection and race-oriented regression tests.

**Recommendation:** do not “simplify” this code into ordinary `Path.read_text()`, `shutil.copy()`, or naive temporary-file helpers merely to reduce line count. The verbosity often represents required safety semantics.

### 3.2 Dependency reproducibility is strong

Backend CI installs hash-locked requirement files with `--require-hashes`, performs dry-run profile checks, separates API/macOS/GPU lanes, and gates GPU acceptance explicitly.

### 3.3 Contracts are generally explicit

The codebase makes heavy use of Pydantic models, dataclasses, typed literals, custom exception classes, release manifests, and explicit “uncertain” states. That is materially better than stringly-typed orchestration.

### 3.4 Testing culture is strong

The latest merge commit message records a prior full verification of **3,583 backend tests passed / 4 skipped** plus frontend and sidecar verification. I did **not** independently rerun that suite in this review; the connector exposed the commit record but no current workflow-run status, and the local analysis environment could not clone the repository because outbound DNS was unavailable.

---

# 4. High-priority findings

## Q1 — `main.py` is both API composition root and a giant symbol namespace

**Priority:** P1  
**Confidence:** High  
**Evidence:** `backend/app/main.py` ~2,355 lines, ~79 imports, 105 route decorators. `create_app()` begins around line 779 and owns the majority of the rest of the file.

Stable reference:  
`backend/app/main.py` at commit `312cb5a...`

### Why it matters

FastAPI already provides a native modularity primitive: `APIRouter`. The code partially uses it (`workbench/routes.py`) but large sections remain nested inside `create_app()`.

The more serious coupling is in:

- `backend/app/workbench/leftover_get_routes.py`
- `backend/app/workbench/leftover_routes.py`

Both dynamically import `backend.app.main as _main` and then copy large numbers of classes/functions/constants from `_main` into local names. This turns `main.py` into a de-facto service locator and creates hidden circular dependency pressure.

Examples:

- `create_leftover_get_routers()` spans ~1,166 lines.
- `create_leftover_post_router()` spans ~955 lines.
- each aliases large numbers of symbols from `backend.app.main` rather than importing the true owning module.

### Improvement

Use **native FastAPI routers**, grouped by current concern, while keeping routes, payloads, status codes, and dependencies unchanged.

A safe sequence:

1. Move one cohesive route group at a time into a router module.
2. Import its actual dependencies from their owning modules, not from `main`.
3. Keep `create_app()` as composition/wiring only.
4. Preserve all current tests and URLs.
5. Delete legacy route modules only when their compatibility flag/usage is proven obsolete.

### What not to do

Do not invent a controller framework, service container, dependency-injection library, or generic “route registry.” FastAPI’s router mechanism is enough.

---

## Q2 — `Storage` has become a 3,140-line god class

**Priority:** P1  
**Confidence:** High  
**Evidence:** `Storage` begins around line 297 of `backend/app/storage.py` and extends to the end of the ~3,436-line file.

### Why it matters

The class handles many distinct responsibilities: input/file ownership, SQLite operations, jobs/admission, analytics artifacts, review bundles, remote-result import/rollback, configuration updates, and various serialization concerns.

Consequences:

- large merge-conflict surface;
- tests must often construct the whole storage object for narrow behavior;
- unrelated changes can share internal state/locks;
- readers must understand thousands of lines to establish invariants.

### Improvement

Preserve the public `Storage` facade for compatibility, but **extract cohesive implementation seams behind it** only when touched. Good candidates are already visible in method clusters (job/admission persistence, analytics artifacts, review bundles, remote-result publication).

Avoid a big-bang repository-pattern rewrite. The goal is to reduce change radius, not add architecture.

### Specific cleanup

`_admit_durable_job()` currently does:

```python
try:
    sha = self.source_sha256(match_id)
except Exception:
    sha = "0" * 64
```

At minimum, narrow/log the expected failure modes. If the all-zero sentinel is part of the existing contract, preserve it, but do not silently hide an unexpected programming or filesystem error.

---

## Q3 — `summarize_match_benchmark()` is ~1,003 lines and leaks private internals to scripts

**Priority:** P1  
**Confidence:** High  
**Evidence:** `backend/app/run_benchmarks.py`, `summarize_match_benchmark()` roughly lines 1046–2048.

### Why it matters

The function accumulates a very large number of local counters/derived fields and finally constructs one enormous result. This makes review difficult because a change to one metric can affect a function containing hundreds of unrelated metrics.

The module also exposes de-facto APIs through private functions. Example: `backend/scripts/run_source_robustness_batch.py` imports private names such as:

- `_assess_truth_gates`
- `_load_ball_truth_layers`
- `_load_accepted_match_state`
- `_summarize_ball_rows`

That means `_` naming no longer reflects real encapsulation and makes safe refactors much harder.

### Improvement

Split the benchmark calculation into a handful of **pure, domain-cohesive helpers** and keep one final `MatchBenchmarkSummary(...)` assembly point. Promote any private helper that is genuinely used across modules into a supported internal function/module.

Avoid introducing a large class hierarchy or plugin system. Plain functions are sufficient.

---

## Q4 — 322 operational scripts have become a second application layer

**Priority:** P1  
**Confidence:** High  
**Evidence:** 322 Python files in `backend/scripts/`; 255 have an exact mirrored `backend/tests/test_<script>.py` filename.

Selected prefix counts include:

- `run_video_to_analysis_*`: 87 scripts
- `run_football_external_soccernet_*`: 53
- `run_football_external_soccertrack_*`: 22
- `run_promoted_v6_*`: 34
- `run_touchline_*`: 11
- many `run_v7*` variants

### Why it matters

Many scripts encode workflow history in filenames and repeat patterns for:

- repo-root discovery;
- `sys.path.insert(0, ...)`;
- `# noqa: E402` imports;
- JSON load/write helpers;
- timestamps;
- safe numeric conversion;
- candidate-root/output-reset logic;
- approval/guardrail summaries.

Some consolidation already exists in `football_external_real_eval_chain_common.py`, which demonstrates the right direction.

### Improvement

Treat durable workflow logic as importable library code and make scripts thin argument/entry wrappers.

For scripts still meant to be run from the checkout, standardize on module execution (`python -m backend.scripts.<name>`) and remove repeated `sys.path` mutation where compatible.

**Ponytail lens:** delete boilerplate before inventing a CLI framework. One shared helper module and thin wrappers are enough.

### Archival hygiene

Some scripts appear to be one-time milestone/approval artifacts. If a script is no longer part of a repeatable operational path and exists only as historical evidence, move that evidence to reports/artifacts and remove executable code after confirming no test/CI/runtime caller remains.

Do not delete by filename alone—validate callers first.

---

## Q5 — There is no Python lint/static-quality gate

**Priority:** P1  
**Confidence:** High

Neither the backend development lock nor the API/CV/CUDA locks contain any of:

- Ruff
- Flake8
- Pylint
- Black
- isort
- Mypy
- Pyright
- Bandit
- coverage tooling

The main CI performs Python tests and an import startup check, but its explicit lint/typecheck gates are frontend-only.

### Why it matters

Tests do not reliably catch:

- unused imports and dead names;
- import-cycle smells;
- accidental shadowing;
- undefined names in unexecuted branches;
- inconsistent import ordering;
- stale `# noqa` / `type: ignore` directives;
- syntax/parsing issues in scripts not imported by tests.

### Improvement

Add **Ruff as the single first tool** and run it across `backend/`. Do not install four overlapping format/lint tools.

Start with correctness-focused rules and a baseline that can be adopted without a repo-wide style rewrite. Formatting can be a later choice.

For typing, choose **one** checker only if the team wants to maintain its annotations as a checked contract. Do not add both Mypy and Pyright.

---

## Q6 — Important degraded-state exceptions are sometimes silently swallowed

**Priority:** P1/P2  
**Confidence:** High for observability gap; medium for runtime impact

A lot of broad exception handling in `daytona.py`, `gpu_worker.py`, and `remote_contracts.py` is deliberate boundary translation and should remain broad where arbitrary protocol objects/syscalls can fail.

The concern is different cases where an operationally meaningful failure disappears.

### Example: job dispatch persistence

In `main.py` around lines 997–1005, failures from `storage.mark_dispatched(...)` and `storage.mark_dispatch_failed(...)` are caught with `except Exception: pass`.

The response still returns a dispatch outcome, but the persistence failure is invisible to logs/telemetry.

### Example: source hash fallback

`Storage._admit_durable_job()` converts any exception in `source_sha256()` to an all-zero hash.

### Improvement

Do not replace all broad catches. Instead:

- log at the point where the error is intentionally suppressed;
- narrow exceptions where the failure set is known;
- preserve current client-visible behavior and uncertainty semantics;
- never include secrets/unsafe paths in logs.

The backend already defines a logger in `main.py`, but logging is sparse relative to the number of uncertainty/error transitions.

---

# 5. Medium-priority findings

## Q7 — Dependency declarations have more than one source of truth

**Priority:** P2

`pyproject.toml` duplicates API/CV/CUDA package/version lists that also live in:

- `backend/requirements/api.in`
- `backend/requirements/cpu-cv.in`
- `backend/requirements/cuda.in`

Additionally, base project dependencies are dynamically loaded from `backend/requirements/api.in`, while `[project.optional-dependencies].api` repeats effectively the same API set.

### Risk

Version changes can drift between package metadata and locked input files.

### Improvement

Pick one canonical dependency declaration and generate/check the other representation. At minimum add a small drift test. Also decide whether the `api` extra is semantically necessary when base dependencies already represent the API profile.

No new runtime dependency is required.

---

## Q8 — Test harness globally installs dependency stubs during collection

**Priority:** P2

`backend/tests/conftest.py` inserts stub modules for missing `cv2`, `pandas`, and `ultralytics` into `sys.modules` before test modules import.

This is thoughtfully surfaced in the verification receipt (`stubsActive`), but it can still make import-time paths look healthier than a real environment.

### CI interaction worth reviewing

The `integration` / `real-media` CI jobs install `backend/requirements/dev.lock`, then run `pip install -e '.[cv]' --no-deps`. Because `--no-deps` is used, the CV extra itself does not install its declared dependencies. The dev input contains OpenCV/Pillow/Scipy, but not the full Torch/Ultralytics CV stack.

This may be intentional because those lanes exercise only media boundaries, but the profile name `cv+dev` can overstate what is actually present.

### Improvement

- keep the receipt disclosure;
- add at least one explicit real-import smoke for the intended CV environment;
- scope stubs more narrowly where possible;
- align profile naming with what is actually installed.

Do not remove stubs if they are required for code-only verification without replacing the coverage they enable.

---

## Q9 — Verifier pass-count parsing is brittle

**Priority:** P2

`scripts/verify.sh` parses human pytest output using:

```bash
grep -Eo '[0-9]+ passed'
```

and compares it to hard-coded minimums.

The thresholds are also counterintuitive: the full backend minimum is 1,486 while code-only is 3,000 even though code-only ignores several test modules. The actual suite can exceed both, but the guard is historically shaped rather than self-describing.

### Improvement

If the goal is to catch accidental mass deselection, use a collection-based guard or a generated expected-test manifest instead of parsing the presentation string from pytest output.

If pytest exit status is sufficient for the desired guarantee, delete the count gate entirely.

---

## Q10 — `edge_share_repair_profiles.py` is configuration history mixed with normalization logic

**Priority:** P2

The file is ~1,033 lines but has only four functions. Much of it is configuration data, followed by `_normalized_repair_config()` at ~258 lines of repeated feature-flag/key coercion.

### Improvement

Keep the profile data explicit, but separate normalization by coherent feature family or use a very small field-spec helper for repeated “if key/enabled -> coerce/default” patterns.

Avoid moving this into a new configuration framework or adding YAML just to reduce Python lines. Python data is fine; the issue is one long conditional normalizer.

---

## Q11 — Large route factories contain retired endpoints as executable boilerplate

**Priority:** P2

`create_workbench_router()` contains multiple endpoints whose bodies only raise `RouteRetired`. Legacy GET/POST routers are separately feature-gated.

### Improvement

Where a retired route must remain for explicit compatibility, retain the minimal handler. Where no caller/contract requires it, remove the route rather than carrying permanent boilerplate.

This requires usage/contract validation; it is not a blanket deletion recommendation.

---

## Q12 — Giant tests and script/test one-to-one mirroring raise maintenance cost

**Priority:** P2

Examples:

- `tests/test_run_guerilla.py` ~324 KB
- `tests/test_run_source_robustness_batch.py` ~182 KB
- `tests/test_api.py` ~165 KB
- `tests/test_gpu_worker.py` ~141 KB
- `tests/test_workbench_contracts.py` ~125 KB

Large tests are not inherently bad when they encode critical contracts, but they become hard to navigate and often duplicate seeding/I/O helpers.

### Improvement

Extract only **proven repeated** test fixtures/builders. Avoid a generic mega-fixture framework. Keep contract tests close to the behavior they protect.

---

# 6. Targeted file-by-file recommendations

## `backend/app/main.py`

**Keep:** middleware security, origin/host validation, explicit HTTP error mapping.  
**Change:** route grouping and dependency ownership.  
**Target state:** `create_app()` mostly creates shared objects, mounts middleware, includes routers, and wires lifecycle.

Suggested extraction seams based on current route responsibilities:

- match upload/admission/jobs;
- analytics/events/frames/report export;
- review bundles/issues;
- semantic search/themes;
- workbench/legacy compatibility.

Do not change URLs or request/response schemas during extraction.

## `backend/app/storage.py`

**Keep:** low-level no-follow/atomic safety functions.  
**Change:** class responsibility concentration.  
**Target state:** stable `Storage` API delegating cohesive subareas internally, or method groups moved to private modules while preserving call sites.

## `backend/app/run_benchmarks.py`

**Keep:** final typed summary contract.  
**Change:** 1,003-line aggregator and private cross-module API leakage.  
**Target state:** small pure summarizers whose outputs assemble into the same `MatchBenchmarkSummary`.

## `backend/run_guerilla.py`

At ~8,908 lines it is the largest production file. Unlike `main.py`, the work here is algorithmic and likely has strong internal coupling, so do not split by arbitrary line count.

Recommended rule: when a section has a stable input/output contract and is independently tested, move it to a named module. Good candidates are repeated recovery/profile/evaluation blocks, not tiny utility functions.

## `backend/app/daytona.py`, `gpu_worker.py`, `remote_contracts.py`, `remote_worker.py`

These contain many broad catches, but most reviewed examples are legitimate translation of low-level/provider/protocol failures into bounded domain errors.

Recommendation: audit only catches that **return a default, `False`, or `pass`**. Keep broad catches that immediately translate and re-raise with a safe domain exception.

## `backend/app/workbench/leftover_get_routes.py` / `leftover_routes.py`

Highest-value cleanup after `main.py`: remove `_main` namespace dependency. Direct imports from owning modules are clearer and make circular dependencies visible.

## `backend/scripts/*`

Prefer:

```text
library function -> tiny CLI runner -> focused test of library behavior
```

instead of:

```text
large script -> mirrored large test -> next milestone script copying prior helpers
```

Reuse the already-existing common chain helpers rather than creating another orchestration framework.

---

# 7. Python tooling plan with minimum new machinery

## Step 1 — Ruff only

Add Ruff to dev tooling and run it across `backend/`.

Initial goals:

- parse every Python file;
- undefined names / unused imports;
- import hygiene;
- obvious bugbear-style issues;
- stale suppressions where practical.

Do **not** immediately enable a huge stylistic rule set that produces thousands of mechanical changes.

## Step 2 — Optional typing checker

Only after current annotation boundaries are defined, choose one of Mypy/Pyright. Start with contract-heavy modules rather than blocking all 771 Python files on day one.

## Step 3 — Complexity reporting, not complexity policing

Use function/file metrics as a trend signal. Do not add arbitrary “50 lines max” rules; security and protocol functions can justifiably be longer.

---

# 8. Refactoring sequence that minimizes regression risk

### Phase A — Zero-behavior-change guardrails

1. Add Ruff with conservative rules.
2. Add dependency-declaration drift check.
3. Add/clarify CV real-import smoke.
4. Add logging for intentionally suppressed dispatch/persistence errors.
5. Remove stale suppressions exposed by the linter.

### Phase B — Native FastAPI modularization

1. Extract one route family to `APIRouter`.
2. Run focused API tests.
3. Repeat family by family.
4. Refactor legacy routers to import true owners instead of `_main`.
5. Keep `create_app()` wiring stable throughout.

### Phase C — Storage and benchmark change-radius reduction

1. Identify method/function clusters with existing focused tests.
2. Extract one cluster at a time.
3. Preserve public function/class signatures.
4. Do not combine these refactors with product changes.

### Phase D — Script consolidation

1. Classify scripts as durable/repeatable vs historical one-off.
2. For durable chains, extract common I/O/guardrail logic already duplicated.
3. Convert runners to thin wrappers.
4. Standardize module-style invocation and remove path bootstraps.
5. Delete historical executable code only after caller/test/CI confirmation.

---

# 9. Ponytail audit — ranked “cut/simplify” findings

1. **native:** split `main.py` route groups with FastAPI `APIRouter`; no custom routing framework. [`backend/app/main.py`]
2. **shrink:** stop legacy routers copying dozens of `_main` symbols; import true owners or delete obsolete routes after validation. [`backend/app/workbench/leftover_get_routes.py`, `leftover_routes.py`]
3. **shrink:** break the 1,003-line benchmark summary into pure section helpers; keep one final model assembly. [`backend/app/run_benchmarks.py`]
4. **shrink:** preserve the `Storage` facade but move cohesive internals behind it incrementally. [`backend/app/storage.py`]
5. **delete:** remove per-script `sys.path` bootstraps when scripts can be invoked as modules. [`backend/scripts/*`]
6. **shrink:** reuse existing JSON/time/output helpers across durable scripts instead of local copies. [`backend/scripts/*`]
7. **yagni:** avoid duplicate API dependency declaration when base dependencies already use `api.in`; establish one source of truth. [`pyproject.toml`, `backend/requirements/*`]
8. **shrink:** replace repeated profile-normalization blocks with small family helpers, not a new config framework. [`backend/app/edge_share_repair_profiles.py`]
9. **delete:** retired route boilerplate only after compatibility tests prove no caller requires it. [`backend/app/workbench/routes.py`, leftover routers]
10. **delete:** historical one-off executable scripts after evidence/caller validation; keep reports/artifacts as history instead of executable code.

**Net potential:** no runtime dependency needs to be added for the structural refactors. Ruff would be one dev-only dependency. The code-deletion opportunity is likely in the low thousands of lines if obsolete scripts/routes are proven removable, but an exact deletion count would require call-site/deprecation validation rather than guessing from filenames.

---

# 10. Findings I would *not* act on blindly

- **Broad `except Exception` count alone.** Many reviewed occurrences correctly translate arbitrary provider/syscall/object failures into domain errors.
- **Low-level filesystem verbosity.** It encodes safety semantics and fault recovery.
- **File size alone.** `release/preflight.py` is large but substantially more cohesive than `main.py` or `Storage`.
- **Splitting every helper into a file.** That would worsen navigation.
- **Adding a DI framework/repository framework/event bus.** None is justified by the quality problems found.
- **Replacing explicit profile dictionaries with YAML/config frameworks.** This moves complexity rather than removing it.

---

# 11. Suggested acceptance criteria for a quality-remediation PR series

A refactor should be accepted only if:

1. No endpoint URL/schema/status behavior changes unless separately requested.
2. Existing backend tests pass unchanged.
3. Security/fault-boundary tests remain intact.
4. No new runtime dependency is introduced for structural cleanup.
5. Ruff passes for the touched scope, with suppressions justified locally.
6. Each PR targets one quality seam (routes, storage, benchmark summary, script common code, etc.).
7. No product/ML heuristic or model-selection behavior is changed in the same PR.
8. `git diff --check` remains clean.
9. Any deleted script/route has caller/CI/test evidence proving it is unused or formally retired.

---

# 12. Concrete first PRs I would make

## PR 1 — Backend static gate

- add Ruff dev dependency/config;
- lint backend for correctness/import issues;
- fix only unambiguous violations;
- add CI gate.

## PR 2 — API composition cleanup, no behavior changes

- extract semantic-search/theme endpoints and one analytics group to routers;
- `create_app()` includes routers;
- same tests, same API.

## PR 3 — Legacy router dependency cleanup

- stop importing `backend.app.main as _main` as a namespace;
- import real owning symbols;
- no route changes.

## PR 4 — Benchmark summary decomposition

- extract pure metric-section helpers;
- preserve `MatchBenchmarkSummary` exactly;
- promote any private helper currently imported by scripts into a stable internal location.

## PR 5 — Script bootstrap/common-helper cleanup

- pick one durable chain (`video_to_analysis` or SoccerNet);
- remove repeated `sys.path` mutation by standardizing module invocation;
- reuse existing common JSON/output/time helpers;
- do not touch other chains in the same PR.

## PR 6 — Storage seam extraction

- choose one cohesive cluster with strong existing tests;
- preserve `Storage` public API;
- move implementation only.

---

# 13. Final conclusion

The backend is **not low-quality code**; it is a codebase with strong correctness/security discipline that has accumulated **orchestration and historical-workflow complexity faster than it has accumulated maintainability tooling**.

The highest return does not come from changing algorithms, models, architecture direction, or adding frameworks. It comes from:

- enforcing basic Python static quality;
- using FastAPI’s native router composition;
- reducing the two biggest change-radius hotspots (`Storage`, benchmark aggregation);
- turning workflow scripts into thin runners over reusable code;
- removing hidden coupling through `main`;
- making intentionally suppressed errors observable;
- eliminating duplicate metadata and verifier bookkeeping.

That path improves readability, reviewability, refactor safety, and onboarding while preserving the current football-analysis direction and runtime contracts.

---

## Source references

Repository snapshot:  
https://github.com/ms81labs/sol-astra-football-analyses-sept26/tree/312cb5a77718830948378ccbcb577b9539b9aed1/backend

Key files:

- https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/312cb5a77718830948378ccbcb577b9539b9aed1/backend/app/main.py
- https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/312cb5a77718830948378ccbcb577b9539b9aed1/backend/app/storage.py
- https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/312cb5a77718830948378ccbcb577b9539b9aed1/backend/app/run_benchmarks.py
- https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/312cb5a77718830948378ccbcb577b9539b9aed1/backend/run_guerilla.py
- https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/312cb5a77718830948378ccbcb577b9539b9aed1/backend/app/workbench/leftover_get_routes.py
- https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/312cb5a77718830948378ccbcb577b9539b9aed1/backend/app/workbench/leftover_routes.py
- https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/312cb5a77718830948378ccbcb577b9539b9aed1/backend/app/edge_share_repair_profiles.py
- https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/312cb5a77718830948378ccbcb577b9539b9aed1/backend/tests/conftest.py
- https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/312cb5a77718830948378ccbcb577b9539b9aed1/pyproject.toml
- https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/312cb5a77718830948378ccbcb577b9539b9aed1/.github/workflows/ci.yml
- https://github.com/ms81labs/sol-astra-football-analyses-sept26/blob/312cb5a77718830948378ccbcb577b9539b9aed1/scripts/verify.sh
