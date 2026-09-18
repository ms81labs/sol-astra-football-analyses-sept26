# Backend Audit v2 Remediation — Implementation Guide

**Source plan:** [`docs/superpowers/audits/2026-09-18-backend-consolidated-audit-v2.md`](../audits/2026-09-18-backend-consolidated-audit-v2.md) (Guerilla Analytics Consolidated Backend Audit v2.0, 35 items B01–B35, work packages H01–H07, tests T01–T28).
**Baseline commit:** `d881d1eaf7a0898897bd9a1a1ae46306606c904d` (`main` at audit time). Every file/line reference in this guide was re-read at that commit.
**Audience:** a coding agent implementing the remediation. Read this whole document once before touching code, then work package by package.

---

## 0. How to use this guide

1. Section 1 lists the non-negotiable rules. Violating one invalidates the work even if tests are green.
2. Section 2 gets the environment running and records the baseline.
3. Section 3 defines the working conventions (branches, commits, tests, closure evidence).
4. Section 4 gives the execution order and dependency graph.
5. Sections 5–11 are the per-work-package guides (H01–H07). Each contains: what the code does today (verified), the target design, ordered implementation steps, the regression tests to write **first**, acceptance criteria, and anti-patterns.
6. Section 12 defines the shared contracts (generations, metric records, job/money, receipts) that several packages depend on. Build these before the packages that need them.
7. Section 13 maps T01–T28 to concrete test files.
8. Section 14 is the handoff report template you must fill in at the end.

The audit is the authority on *what* is wrong and *what evidence closes it*. This guide is the authority on *how* to structure the fix inside this repository. If the two disagree, stop and re-read the audit entry; the audit wins on scope and acceptance.

---

## 1. Non-negotiable rules

These come straight from audit §11 and §9 "Closure rule", plus repository constraints.

1. **Regression test first, on the baseline.** For every finding, write a behavioural test that **fails on `d881d1ea` for the intended reason** before writing the fix. Record the failing output. A test that passes on the baseline is not a regression test for that finding.
2. **Test the real affected input mode.** A raw-video/raw-row defect (B04) must be tested with a raw-row-backed fixture, not only with a tracking-JSON fixture. Keep both as separate test cases.
3. **Never trust posted arrays as ground truth.** Do not "fix" empty-array bugs (B01) by using request-supplied `events`, `metrics` or `knownEvidenceIds`. Load server-owned match state.
4. **Unknown is not zero.** Never replace a missing measurement, cost, count or score with `0`/`0.0`/`True`. Use `None`/`"unknown"`/`"not_recorded"` and a reason code.
5. **Do not duplicate full budgets on retry.** The reservation model must be specified first (§12.3); a retry consumes *remaining* authorised capacity.
6. **No cloud providers, paid jobs or external deployment changes** may be enabled or invoked to obtain a passing test. Every provider test uses a spy that raises on network I/O.
7. **Preserve existing source-bound artifact validation** (remote bundle sha256/size checks, `_admit_local_decode_path`, no-shell subprocess execution, HTML escaping, TrustedHost/Origin checks). Tighten; never delete.
8. **Metadata is not implementation.** An `admitted: True`, a re-export namespace, a renamed adapter, or a `reasonCodes: []` does not close an item. Only behaviour observed by a test does.
9. **Do not weaken a failing behavioural assertion to match a helper flag.** Fix the behaviour.
10. **Small, ID-tagged commits.** One logical change per commit, message prefixed with the audit IDs (e.g. `B04 H02: persist swapped team mapping before raw-row rebuild`). No single "fixes all 35" commit.
11. **Schema/route changes require migration and compatibility evidence** (a reader for the old artifact shape plus a test that loads a pre-change fixture).
12. **Nothing you write for verification lives in the repo** unless it is a real test under `backend/tests/`. Scratch scripts go to `/tmp`.

---

## 2. Environment and baseline

### 2.1 Install

Python ≥ 3.11 (CI uses 3.11; the workspace may have 3.12). From the repo root:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e . -r backend/requirements-dev.txt
pip install -e ./research-addon
# Optional for the real-media lane (H06/H07):
sudo apt-get install -y ffmpeg
```

`pyproject.toml` pulls runtime deps from `backend/requirements-runtime.txt`. `backend/requirements-ml.txt` (Ultralytics/torch/CUDA) is **not** needed for the code-only profile and should not be installed on a Mac by default (B31).

### 2.2 Understand the test profiles before running anything

- `scripts/verify.sh` is the CI entrypoint. With `VERIFY_CODE_ONLY=1` it runs `python3 -m pytest -q backend/tests` **ignoring** `test_convert_football_analysis_pilot_cvat_labels.py`, `test_evaluate_football_analysis_pilot_soccertrack_events.py`, `test_gpu_worker.py`, `test_operational_docs.py`, `test_run_guerilla.py`, `test_run_source_robustness_batch.py`, and requires ≥ 3000 tests (`BACKEND_MINIMUM`).
- `backend/tests/conftest.py`:
  - sets `GA_FLAG_LEFTOVER_HTTP=1` via `os.environ.setdefault` — production default is `False` (`backend/app/workbench/flags.py` `DEFAULT_FLAGS["leftover_http"] = False`). You must add tests for the default-off configuration (B32).
  - installs `cv2` / `pandas` / `ultralytics` stubs **only** when the real import raises `ModuleNotFoundError`. Do not describe this as "everything is mocked". Do record which stubs were active (H07).
  - redirects `GUERILLA_STORAGE_ROOT` to a temp dir.
- API tests use `create_app(storage_root=..., run_jobs_inline=True, settings=...)` with `httpx.ASGITransport` (see `backend/tests/test_api.py` `api_client`). Reuse that pattern.
- Fixtures live in `backend/tests/fixtures/` (`sample_tracking.json` is the tracking-JSON fixture). There is **no** raw-row-backed video fixture yet; H02 must create one.

### 2.3 Record the baseline

```bash
git rev-parse HEAD                      # must be d881d1ea... or note the delta
VERIFY_CODE_ONLY=1 scripts/verify.sh 2>&1 | tee /tmp/baseline-verify.log
python3 -m pytest -q backend/tests -p no:cacheprovider 2>&1 | tail -5 | tee /tmp/baseline-pytest.txt
```

Save the exact pass/skip/fail counts and the commit into your handoff report (§14). If HEAD is not `d881d1ea`, diff each pinned file (`git diff d881d1ea..HEAD -- <path>`) and mark any item already changed with evidence before proceeding.

### 2.4 Repository map (backend)

| Area | Files |
|---|---|
| FastAPI app, normal-match routes, legacy LLM route | `backend/app/main.py` (`create_app`, `analyze_match` at ~L1571) |
| Normal-match review routes (used by the frontend) | `backend/app/main.py` ~L1257–1460 (`/api/matches/{id}/corrections`, `/queries`, `/reports`, `/metrics`, `/calibration`, `/recompute`, `/identity/*`) → `Storage` |
| Compatibility/workbench routes (`/api/workbench`, not used by the frontend) | `backend/app/workbench/routes.py` (`create_workbench_router` at ~L133; module globals at L42–44) |
| Leftover routers (`/api/workbench/dev`, plus `/api` when `GA_FLAG_LEFTOVER_HTTP=1`) | `backend/app/workbench/leftover_routes.py`, `leftover_get_routes.py`, `leftover_http.py` |
| Match persistence, corrections, calibration, recompute | `backend/app/storage.py` (`Storage`) |
| Rebuild from raw rows | `backend/app/processor.py` (`reprocess_video_match` ~L808) |
| Correction log model | `backend/app/workbench/review.py` (`Correction`, `CorrectionLog`) |
| Event review application | `backend/app/workbench/events.py` |
| Identity edits / team swap | `backend/app/workbench/identity.py` |
| Calibration | `backend/app/workbench/geometry.py` (`_project`, `evaluate_landmarks`, `commit_calibration`) |
| Analytics & metric availability | `backend/app/analytics.py` (`_summary_metric_availability` ~L1227) |
| Report export | `backend/app/report_export.py` (`_format_available_metric` ~L56) |
| Job ledger | `backend/app/workbench/jobs.py` (`DurableJobLedger`, `MAX_ATTEMPTS = 3`) |
| Legacy job runner | `backend/app/jobs.py` |
| Provider/LLM | `backend/app/llm.py` (`run_analysis` ~L474), `backend/app/provider_adapters.py`, `backend/app/ai_policy.py`, `backend/app/workbench/assistance.py` (`AssistanceRouter.run`) |
| Media decode/probe | `backend/app/workbench/media.py` |
| Decoder/deployment guards | `backend/app/workbench/access.py` (`constrained_decoder` ~L153) |
| Perception adapters & scorer | `backend/app/workbench/perception.py` (`score_detections` ~L58) |
| Wrapper receipts | `backend/app/video_pipeline.py` (`_sampling_and_cache` ~L94), `backend/run_guerilla.py` (~L8779 return dict) |
| Cache identity | `backend/app/workbench/cache.py` (`cache_identity`) |
| Evaluation helpers | `backend/app/workbench/evaluation.py` |
| Schemas | `backend/app/schemas.py` (`MatchConfig`: `processingScope`, `cloudPermission`, `llmProvider`, `pitchLengthM`, `pitchWidthM`, `manualHomographyPoints`), `backend/app/workbench/contracts.py` |
| Feature flags | `backend/app/workbench/flags.py` |
| Training | `backend/train_custom.py`, `backend/app/training_quality_gate.py` |
| CI | `.github/workflows/ci.yml`, `scripts/verify.sh` |

---

## 3. Working conventions

### 3.1 Branching and PRs

- One branch per work package: `cursor/h01-provider-boundary-<suffix>`, `cursor/h02-review-service-<suffix>`, … Base each on `main`. Where a package depends on another (see §4), branch from the dependency's branch or wait for it to merge.
- Open a draft PR per package. PR description lists each audit ID touched, with links to the regression test(s) and the baseline-failure evidence.
- A final small integration PR may reconcile conflicts. It must contain **no** feature expansion.

### 3.2 Commit format

```
<IDs> <package>: <imperative summary>

Baseline: <test> fails on d881d1ea with <reason>
Fix: <one paragraph>
Evidence: pytest backend/tests/<file>::<test> passes; profile=<code-only|integration|real-media>
```

### 3.3 Test file naming and markers

- New regression tests go in `backend/tests/test_audit_v2_<package>.py` (e.g. `test_audit_v2_h02_review.py`). The repo already uses `test_audit_*.py` for prior audits; keep that pattern.
- Register pytest markers in `pyproject.toml` (currently no `[tool.pytest.ini_options]` exists — add it):

```toml
[tool.pytest.ini_options]
markers = [
  "integration: real subprocesses, multi-process, filesystem crash tests",
  "real_media: requires ffmpeg/ffprobe on PATH and generated media",
  "gpu: requires CUDA; never run in default CI",
]
```

- Tests requiring ffmpeg use `pytest.importorskip`-style guards: `pytest.mark.skipif(shutil.which("ffmpeg") is None, reason=...)`. Never fake a subprocess for a test whose purpose is pipe behaviour (B17).
- Each regression test docstring names the audit ID and the T-row: `"""B04 / T02: raw-row team swap persists before the request returns."""`.

### 3.4 Closure evidence per item

An item moves to **fixed** only with all of:

1. Fix commit SHA(s).
2. Regression test path that fails on the baseline for the intended reason (paste the assertion message).
3. Pass on the fixed revision, naming the profile (code-only / integration / real-media / gpu).
4. For conditional risks (B17, B26, B27): the explicit scenario tested and the remaining platform limits, stated.

Other allowed statuses: **safely deferred/disabled** (feature is refused at runtime with a documented response and a test proving the refusal), **still open** (with reason), **not reproduced** (with the exact attempt and why).

"Fails on the baseline for the intended reason" means the assertion about *behaviour* fails — e.g. `assert frames_after_swap != frames_before` or `assert response.status_code == 409`. An `ImportError`/`AttributeError` because the test imports a symbol you are about to create does **not** count. Structure regression tests so the baseline run reaches the behavioural assertion: import new symbols lazily inside the test behind `pytest.importorskip`-style guards only for *helpers*, and phrase the core assertion against public behaviour (HTTP response, persisted artifact, returned dict) that exists at both revisions. Where a new type is unavoidable (e.g. `CalibrationUnavailable`), write the baseline check against the observable result (`accepted is False`) rather than the exception class.

---

## 4. Execution order and dependencies

```
Phase 0  Shared contracts scaffolding (§12) — types only, no behaviour change
Phase 1  H01 provider guard (B13, B14)      ─┐
         H03 calibration false-accepts      ─┼─ independent; start in parallel
         (B05, B06, B33) and B22, B23        │
         H02 failing raw-row regression T02 ─┘
Phase 2  H02 review service + generations + outbox (B01–B04, B35)
         H03 remainder (B07, B24, B28)
         H04 ledger (B10–B12)                — must finish before any unattended paid execution
         H06 bounded hashing + trusted executable (B16, B34)
Phase 3  H05 recompute/identities/receipts (B08, B09, B18, B25, B29) — needs H02 generations + H03 calibration revision
         H06 decode loop, PTS, adapters, capability probes (B17, B19, B20, B21)
         H01 remainder (B15, B26, B27)
Phase 4  H07 profiles + CI lanes (B30–B32) — runs throughout; closes evidence for every package
```

Hard dependencies:

- H05 `execute_recompute` depends on the H02 generation model and the H03 `CalibrationRevision`.
- H05 receipt validation must land **before** any performance optimisation in H06 (audit §5: "Video optimisation follows reliable telemetry").
- H04 must be complete before enabling unattended paid jobs. Until then keep remote dispatch disabled by default.
- B35 (409 mapping) needs the H04 `IdempotencyConflict` exception type, but can ship earlier with a temporary catch of the current `ValueError("idempotent request payload mismatch")`.

---

## 5. H01 — One provider and deployment-policy boundary

**Items:** B13 (P1), B14 (P1 before enabling providers), B15 (P2), B26 (P1 before hosting), B27 (P2).
**First action (audit):** disable legacy provider execution for real data until it goes through the shared guard.

### 5.1 What the code does today (verified)

- `backend/app/main.py` ~L1571–1619 `analyze_match`: `provider = body.get("provider") or snapshot.config.llmProvider`, then calls `run_analysis(analysis_type, frames, provider=provider, ...)` directly. No check of `snapshot.config.cloudPermission`, `processingScope`, model allowlist, budget or deadline.
- `backend/app/ai_policy.py` contains only `select_evidence(claimed_ids, known_ids)` and `ground_output(payload, known_ids)`.
- `backend/app/workbench/assistance.py` ~L277–329 `AssistanceRouter.run`: after the provider returns, strips only top-level keys that equal metric names, then sets `reasonCodes=["GROUNDED"] if "evidence" in sanitized`. Returned evidence IDs are never resolved.
- `backend/app/workbench/access.py` ~L153 `constrained_decoder(argv, network_enabled)` is a string predicate; nothing about the launched process changes.
- `backend/app/llm.py` prompts still ask the model for a boolean offside and a numeric spacing width (B15).
- `backend/app/schemas.py` `MatchConfig`: `processingScope: Literal["local_only","local_plus_burst","hosted"] = "local_only"`, `cloudPermission: bool = False`, `llmProvider: Literal["local","cloud"] = "local"`.

### 5.2 Target design

Create `backend/app/provider_gateway.py` (single module; do not scatter):

```python
@dataclass(frozen=True)
class ExecutionPolicy:
    match_id: str
    generation_id: str
    provider: Literal["local", "cloud"]        # resolved by the server, not the caller
    model_id: str
    processing_scope: str
    cloud_permitted: bool
    budget_reserved: float | None
    deadline_seconds: float
    reason_codes: list[str]

@dataclass(frozen=True)
class ApprovedEvidencePackage:
    match_id: str
    generation_id: str
    evidence_ids: frozenset[str]              # the only IDs the model may cite
    metrics: tuple[MetricRecord, ...]
    events: tuple[dict, ...]
    digest: str                               # sha256 of canonical JSON

class ProviderDenied(Exception): ...          # maps to HTTP 403 with reasonCodes
class ProviderGateway:
    def __init__(self, storage, settings, adapters, budget_ledger, clock): ...
    def resolve_policy(self, match, *, requested_provider, task_type) -> ExecutionPolicy: ...
    def build_evidence(self, match_id, generation_id, task_type) -> ApprovedEvidencePackage: ...
    def execute(self, match_id, task_type, *, requested_provider=None, body=None) -> GatewayResult: ...
```

Rules inside `resolve_policy` (server-owned; request `provider` is a *preference* only):

- `provider = "cloud"` only if **all** hold: `match.config.cloudPermission is True`, `match.config.processingScope != "local_only"`, `settings` has cloud enabled and a key configured, `model_id in settings.allowed_model_ids`, a budget reservation succeeds in the H04 ledger (or a dedicated assistance budget ledger), and evidence generation is current. Otherwise `provider = "local"` with reason codes (`CLOUD_NOT_PERMITTED`, `SCOPE_LOCAL_ONLY`, `MODEL_NOT_ALLOWLISTED`, `BUDGET_EXHAUSTED`, `EVIDENCE_STALE`).
- If the caller *requires* cloud (e.g. `body.provider == "cloud"` and `body.requireProvider is True`) and it is not permitted → raise `ProviderDenied` **before** any serialization/upload. Otherwise fall back to local with the reasons in the response.

`execute` is the **only** code path that may call `run_analysis` / `provider_adapters`. Enforce it mechanically:

- Rename `llm.run_analysis` → `llm._run_analysis_unguarded` and make the module-level `run_analysis` a thin wrapper that requires a `GatewayToken` (an object only `ProviderGateway` can construct). Grep for every caller (`rg "run_analysis\(" backend/`) and route each through the gateway, including CLI/worker paths (`backend/app/worker.py`, `backend/app/remote_worker.py`, `backend/app/gpu_worker.py`, `backend/run_guerilla.py`).
- Add a test-only hook `ProviderGateway.adapter_factory` so tests inject a spy.

Post-execution validation (B14) in `backend/app/provider_gateway.py` `validate_output(raw, package) -> ValidatedOutput`:

1. JSON schema validation of the task's output shape (fail → `MALFORMED_PROVIDER_OUTPUT`, fall back to template).
2. Walk the whole payload recursively; collect every string matching the evidence-ID pattern (define one, e.g. `^ev_[a-z0-9]+$` or whatever `EvidenceStore` emits — check `backend/app/workbench/evidence.py`). Each must be in `package.evidence_ids`. Any miss → `UNKNOWN_EVIDENCE_REFERENCE`, not grounded. Cross-match, superseded-generation, and fabricated IDs all fail this check because the package is generation-scoped.
3. Walk for numeric claims that are keyed by a known metric ID (`{"metric": "possession_pct", "value": 61}` or similar declared shape). Compare to `package.metrics` within tolerance; mismatch → `NUMERIC_CLAIM_MISMATCH`, not grounded.
4. Label output sections: `measurements` (must all pass 2–3) vs `interpretation` (free text; labelled `interpretive`, never `grounded`).
5. Only if every referenced ID resolves and every structured number matches: `grounding = "grounded"`. Otherwise `"ungrounded"` with reasons; the route returns the template/analyst-review fallback.

Wire `AssistanceRouter.run` to call the same `validate_output`; delete the `"evidence" in sanitized` heuristic.

B15: remove offside boolean and spacing numeric from prompts and output schemas in `llm.py`. Implement in Python (`backend/app/workbench/geometry.py` already has `review_incident_geometry`; extend it): `spacing_width_m` from pitch-projected x-extent of the declared team on a declared axis, only when the H03 calibration revision is accepted for the interval; `offside_position_review` returns `{status: "review_only", attackerBeyondSecondLastDefender: bool|None, marginM: float|None, uncertaintyM: float|None, reasonCodes}` with no `isOffside` field. When opponents < 2 visible, ball/touch timing unknown, or calibration unavailable → `status: "unknown"`. The model may only be asked to *explain* an accepted geometry result.

B26: in `backend/app/settings.py` add `deployment_mode: Literal["local", "hosted"]` (env `GA_DEPLOYMENT_MODE`, default `local`). `create_app` in `hosted` mode must refuse to start unless: bind host is not `0.0.0.0` without TLS termination declared, an authentication backend is configured (`GA_AUTH_BACKEND` ≠ unset), and `GA_FLAG_LEFTOVER_HTTP` is off. Add a FastAPI dependency `require_principal()` that in `local` mode yields the local principal and in `hosted` mode requires a verified token (implement a minimal HMAC/JWT verifier or a pluggable interface; do not ship a "trust the header" path). Apply it to every object/list/export/WebSocket route (grep `@app.get\|@app.post\|@app.websocket\|@router.` and enumerate in the PR). Tenant identity comes from the principal, never from a request header. Move diagnostics (`/api/workbench/dossier`, `/capabilities`, health internals) behind `GA_INTERNAL_ROUTES=1` or an internal router.

B27: in `media.py` FFmpeg launch sites (decode loop, probe, clip export): add `-nostdin`, `-protocol_whitelist file,pipe`, `-threads N` bound, run with `cwd` set to a scratch dir, `preexec_fn` applying `resource.setrlimit` for `RLIMIT_AS`/`RLIMIT_CPU`/`RLIMIT_FSIZE` on POSIX (guard for platform), a wall-clock timeout, and an output-byte cap. Check `returncode` after every run. Make clip export poll `cancel_event` while the child runs (use `Popen` + `poll()` loop, not a blocking `run`). Document clearly in code and the handoff that **network isolation requires OS-level sandboxing (container/netns)**; `network_enabled=False` remains a policy declaration only, and the guide records that as a remaining platform limit.

### 5.3 Implementation steps

1. Write the provider spy and the T13 test (§5.4) — confirm it fails on baseline (spy is reached).
2. Add `provider_gateway.py` with `resolve_policy`, `build_evidence`, `execute`, `validate_output`.
3. Gate `llm.run_analysis` behind `GatewayToken`; route `analyze_match` through `ProviderGateway.execute`. Response gains `policy: {provider, reasonCodes}` and `grounding`.
4. Route `AssistanceRouter.run` output through `validate_output`.
5. Grep and route every other `run_analysis`/adapter caller (workers, CLI). Where a path cannot be routed yet, make it raise `ProviderDenied` for real match data (audit "first action").
6. B15 geometry helpers and prompt changes.
7. B26 deployment mode + `require_principal` + startup refusal + internal router.
8. B27 subprocess hardening + cancellation polling + exit-code checks.
9. Update `docs/` runbook for deployment modes and provider policy (short).

### 5.4 Regression tests (write first)

`backend/tests/test_audit_v2_h01_provider.py`:

- **T13 / B13:** create a tracking match via the API with `cloudPermission=False`, `processingScope="local_only"`, `llmProvider="local"`. Inject a spy adapter that raises `AssertionError("network reached")` on any call and set fake credentials in env. POST `/api/matches/{id}/analysis/tactical_report` with `{"provider": "cloud"}`. Assert the spy call count is 0, response is 200-with-local-fallback **or** 403 `CLOUD_NOT_PERMITTED` (choose one, document), and no reservation exists. Repeat for every public analysis entry point (`rg "analysis" backend/app/main.py backend/app/workbench/routes.py`). Positive control: `cloudPermission=True`, `processingScope="local_plus_burst"`, allowlisted model → spy is called exactly once and a reservation exists. Negative controls: unknown provider string, exhausted budget, stale generation.
- **T14 / B14:** fake provider returns (a) a fabricated evidence ID, (b) an ID from a second stored match, (c) a correct ID but a wrong `possession_pct`, (d) an ID from a superseded generation. Assert none yield `grounding == "grounded"`; assert reason codes name the failure. Positive control with all-correct references yields `grounded`.
- **B15:** with all providers disabled, `POST /api/workbench/matches/{id}/incidents/geometry` (or the new normal-route equivalent) returns spacing/offside review output; with <2 opponents or no calibration, returns `unknown`. Assert no `isOffside` key exists anywhere in llm output schemas (`rg -n "offside" backend/app/llm.py`).
- **T24 / B26:** `create_app(settings=hosted-mode-without-auth)` raises at startup. Hosted mode with auth: no-token → 401; forged `X-Tenant`/boundary header → ignored (403 for foreign match); cross-match export → 403; WebSocket without token → closed. Local mode unchanged.
- **B27:** `@integration` — run the real decoder on a truncated file and on an oversized-output scenario (e.g. `-f rawvideo` to a capped sink); assert nonzero exit is raised as a typed error, output cap triggers termination, and `cancel_event` set mid-export kills the child within the timeout (`process.poll() is not None`).

### 5.5 Anti-patterns

- Checking `body.provider` anywhere except to pass it as `requested_provider`.
- Stripping metric keys from the top level and calling the rest grounded.
- Adding more shell-character checks to `constrained_decoder` and calling it a sandbox.
- Deriving tenant from a request header in hosted mode.

---

## 6. H02 — Shared review services and crash-safe corrections

**Items:** B01 (P1), B02 (P1), B03 (P1), B04 (P1), B35 (P2).
**Highest-priority regression (audit):** the same-request raw-row team swap (T02).

### 6.1 What the code does today (verified)

- `storage.py` L1105–1133 `Storage.submit_correction`: under `self._annotation_issue_lock`, loads the correction log, `log.submit(...)`, `_save_correction_log`; **after releasing the lock**, `if saved.saveState == "saved": self._apply_saved_correction(match_id, saved)`. `recover_correction` and `undo_correction` (L1135–1173) follow the same log-first/effect-later shape. No durable record of whether the effect was applied.
- `storage.py` L1224–1248 `_apply_saved_correction`: for `event_accept/reject` it saves events and returns (no shots/summary/narrative rebuild — B03); for `team_mapping` calls `_apply_team_mapping`; for `identity_validate` calls `_recompute_identity_continuity`; for `calibration` saves `calibration_evaluation`.
- `storage.py` L1258–1269 `_apply_team_mapping`: `self.save_frames(match_id, apply_team_swap(frames))` then `reprocess_video_match(self, match_id)`.
- `processor.py` L808–858 `reprocess_video_match(storage, match_id, config=None)`: `config = config or match.config`; if `raw_rows` non-empty → `_classify_video_rows(raw_rows, config, match.teamClusters)` → `normalize_tracking_rows` → `save_frames`. Because `config` is the stored (unswapped) config, the swap written one line earlier is overwritten **in the same request** (B04).
- `main.py` L1257–1310: the normal family (`post_match_correction`, `recover_match_correction`, `undo_match_correction`, `post_match_query`, `post_match_report`) calls `storage.submit_correction` / `storage.query_match_events` / `storage.assemble_match_report`, i.e. persisted match state. This is the family the frontend uses.
- `workbench/routes.py` L42–44: module globals `_correction_log = CorrectionLog()`, `_router_assistance = AssistanceRouter(providers_enabled=False)`, `_evidence_store = EvidenceStore()`. L150–160 `post_correction` appends to that in-memory log + `store.append_correction` without applying match effects — a second, disconnected authority for the same match. L185–189 `match_queries` and L204–208 `typed_search` call `execute_typed_query([], ...)`. L191–202 `match_reports` and L210–220 `assistance_report` pass `metrics=[], events=[], known_evidence_ids=set()`. L262–272 `match_metrics` summarises `{}`. L279–290 `get_evidence` ignores `match_id`.
- `workbench/routes.py` L221–243 `create_job` calls `job_ledger.submit(request)`; `jobs.py` L198–201 raises `ValueError("idempotent request payload mismatch")` → uncaught → HTTP 500 (B35).
- Writes use `Storage._write_json` → `_atomic_text_destination` (temp file + rename): individual files are atomic, multi-file updates are not.

### 6.2 Target design

#### 6.2.1 Correction command with explicit application state

Extend `backend/app/workbench/review.py` `Correction` with:

```python
applyState: Literal["received", "committed", "applying", "applied", "failed"] = "received"
baseGeneration: str | None = None       # generation the analyst was looking at
appliedGeneration: str | None = None    # generation produced by applying this command
commandId: str                          # == correctionId; stable across retries
attempts: int = 0
lastError: str | None = None
```

Provide a migration: `CorrectionLog.from_payload` must accept old records (missing fields → `applyState="applied"` if `saveState=="saved"` else `"received"`, with a note; add a fixture test loading a pre-change `corrections.json`).

`submit_correction` becomes:

1. Under lock: validate `expected_version`, append command with `applyState="committed"`, save log. Return point A.
2. Call `ReviewService.apply_pending(match_id)` (idempotent, see 6.2.3). This sets `applying` → builds generation → publishes → `applied`.
3. Response includes `saveState`, `applyState`, `appliedGeneration`. **`saveState == "saved"` no longer implies applied.**

Undo is a *new* command (`kind="undo", payload={"of": correction_id}`) with its own application; the original record is never mutated except `supersededBy`.

#### 6.2.2 Generation model (see §12.1 for the shared contract)

Directory per generation under the match root: `matches/<match_id>/generations/<gen_id>/` containing `frames.json`, `events.json`, `analytics.json`, `shots.json`, `summary.json`, `manifest.json`. A single pointer file `matches/<match_id>/current_generation.json` = `{"generationId": ..., "publishedAt": ..., "correctionHead": ..., "calibrationRevision": ...}` written atomically.

`Storage.load_frames/load_events/load_analytics/...` resolve the pointer once per call (or accept a `generation_id` argument for readers that must be consistent within a request; add `Storage.current_generation(match_id) -> GenerationRef` and thread it through report/export code paths).

Publishing: write all files into a new directory → `os.fsync` each → fsync the directory → write pointer (atomic rename) → fsync parent. Recovery on startup/read: any generation directory without a pointer reference and without a command in `applying` state pointing to it is an orphan → delete (log it). A pointer referencing a missing directory → fall back to the newest complete manifest and mark `recoveryRequired`.

Keep `Storage.save_frames/save_events/...` as thin writers **into a generation build dir**; do not leave them writing to the legacy flat paths once migration is done. Legacy flat layout: on first access, import as generation `gen_legacy_<sha>` so existing storage keeps working (compatibility evidence required).

#### 6.2.3 ReviewService and materialisation

New `backend/app/review_service.py`:

```python
class ReviewService:
    def __init__(self, storage: Storage): ...
    def submit(self, match_id, *, kind, payload, author, expected_version, base_generation) -> CorrectionResult
    def undo(self, match_id, correction_id, *, author) -> CorrectionResult
    def recover(self, match_id, correction_id) -> CorrectionResult
    def apply_pending(self, match_id) -> list[CorrectionResult]     # idempotent outbox drain
    def rebuild_generation(self, match_id, *, reason) -> GenerationRef
    def query_events(self, match_id, query) -> list[SearchHit]       # reviewed projection
    def report_inputs(self, match_id) -> ReportInputs                # metrics, events, known evidence ids
```

`apply_pending` algorithm (idempotent):

1. Load log; select commands with `applyState in {"committed", "applying"}` in order.
2. If none → return.
3. Mark all `applying` (durable write).
4. Compute the **overlay set** = all applied+applying commands for the match, in order.
5. `rebuild_generation`:
   - Load immutable observations: `load_raw_rows` if present, else the imported tracking frames (the "no-raw-row" product case). Both paths are supported and tested separately.
   - Compute the effective `MatchConfig` by folding `team_mapping` commands (swap `myTeamCluster` etc.) — **persist this config before classification** (`update_match_config`) so `_classify_video_rows(raw_rows, effective_config, clusters)` sees the swap. Never call `reprocess_video_match` without the effective config.
   - Apply identity overlays (`track_split`, `track_join`, and their undos) as a track-id remap table on the normalised frames (extend `backend/app/workbench/identity.py` with `build_identity_remap(commands) -> Remap` and `apply_remap(frames, remap)`).
   - Run `_compute_outputs_and_match_state(...)` (from `processor.py`) to derive events/shots/summary.
   - Reconcile event review decisions: assign each generated event a **stable `eventId`** = sha1 of `(kind, teamId, round(timestamp, 1), primaryTrackId after remap)` (adjust granularity; document). Apply `event_accept/event_reject` commands by `eventId`; decisions that no longer match any event go to `manifest.orphanedDecisions` (visible, not dropped).
   - Build the **reviewed-event projection** (`accepted` events only; `candidate` events kept separately) and recompute shots/summary/player summaries from it (B03). Narrative/report artifacts derived from the old generation are marked `stale` in the manifest; report routes refuse or label stale content.
   - Write generation dir, publish pointer.
6. Mark commands `applied` with `appliedGeneration`; durable write. If anything raises: mark `failed` with `lastError`, leave the old pointer intact (old generation remains valid), re-raise as `CorrectionApplicationError` (HTTP 500 with commandId so the client can call recover).

Concurrency: hold a per-match file lock (`fcntl.flock` on `matches/<id>/.review.lock`, falling back to `threading.Lock` on non-POSIX) across steps 1–6 so two processes cannot publish overlapping generations. Recovery on `Storage.__init__`/first read: call `apply_pending` for matches with `applying` commands; because step 5 is a pure function of (observations, overlay set), replaying is idempotent — a swap applied twice is impossible because the *set* of commands, not a sequence of mutations, defines the result.

#### 6.2.4 Route consolidation (B01)

Verified consumer map at the baseline (re-run these greps before deciding):

- `rg -n "api/workbench" frontend/src` → **zero** production call sites. `frontend/src/utils/workbench.ts` calls the **normal** family only: `/api/matches/{id}/queries`, `/api/matches/{id}/corrections[...]`, `/api/matches/{id}/reports`, `/api/matches/{id}/metrics`, `/api/matches/{id}/jobs`, `/api/jobs/{id}/...`, `/api/dossier`, `/api/flags`, `/api/library/search`, … Frontend tests assert that `/api/workbench/` is never fetched.
- Those normal routes live in `backend/app/main.py` (~L1257–1460) and already delegate to `Storage` (`submit_correction`, `query_match_events`, `assemble_match_report`, …). They are the authoritative family and will call `ReviewService` after 6.2.3.
- `backend/app/workbench/routes.py` (`/api/workbench/...`) is the compatibility family with the module-global objects; it is referenced only by 3 backend test files (`rg -l "api/workbench" backend/tests`).
- The "leftover" routers (`leftover_routes.py`, `leftover_get_routes.py`) are always mounted at `/api/workbench/dev` and **additionally at `/api`** when `GA_FLAG_LEFTOVER_HTTP` is on (default off in production, on in `conftest.py`). Some normal-looking paths (e.g. `/api/search`, a second `/api/matches/{id}/metrics`) may therefore be served by leftover code in tests but not in production — this is the B32 default-off concern; test both.

Decision rule:

- **Default: retire** the `/api/workbench` compatibility handlers for corrections, recover, undo, list, queries, search, reports, assistance/report, metrics, evidence and jobs. Respond `410 Gone` with `{"error": "ROUTE_RETIRED", "replacement": "/api/matches/{match_id}/..."}` and update the 3 test files to exercise the normal routes (or to assert the 410 contract). Keep only routes that have no normal-family equivalent and no server-owned data problem (e.g. `dossier`, `capabilities`, `metrics/dictionary`, `playlists/export-interval`), moved onto the shared `Storage`.
- **Alternative (only if a consumer is found):** make each workbench handler a thin alias that calls the same `ReviewService`/`Storage` method as its normal-route twin, with identical response shape. Never a third implementation.

Either way: delete the module-global `_correction_log`, `_router_assistance`, `_evidence_store`; anything that remains is constructed inside `create_workbench_router(storage, ...)` from the `Storage`/`ReviewService` instance that `create_app` already owns (`main.py` ~L675 currently passes `storage.storage_root` and `storage.job_ledger`; pass the `Storage` itself). For the normal family, `assemble_match_report` must treat `claimedEvidenceIds` as a filter over server-known evidence, never as truth; `query_match_events` must read the reviewed projection of the current generation.

#### 6.2.5 Conflict mapping (B35)

Define in `backend/app/workbench/errors.py` (new): `DomainError`, `IdempotencyConflict(DomainError)`, `StaleRevision(DomainError)`, `RouteRetired(DomainError)`. Register one exception handler in `create_app` mapping: `IdempotencyConflict → 409 {"error": "IDEMPOTENCY_CONFLICT", "requestId": ...}`, `StaleRevision → 409 {"error": "STALE_REVISION", "expected": ..., "actual": ...}`, `RouteRetired → 410`. Never include tracebacks or payloads with secrets. `DurableJobLedger` raises `IdempotencyConflict` instead of `ValueError` (H04 keeps this). `create_job` validates body fields with Pydantic (422) separately from the conflict path.

### 6.3 Implementation steps

1. Build the **raw-row-backed video fixture** (§6.4 T02 prerequisites) and write T02; confirm it fails on baseline (final frames unchanged after swap).
2. Add `errors.py` + exception handler; make `create_job` return 409 (T28). Small early commit.
3. Extend `Correction` with `applyState` fields + migration reader + fixture test.
4. Introduce generation directories + pointer + legacy import + orphan recovery (`Storage.current_generation`, `publish_generation`). Migrate readers.
5. Add `ReviewService.rebuild_generation` with effective-config fold, identity remap, stable `eventId`, reviewed projection, dependant rebuild (B03/B04).
6. Rewrite `submit_correction`/`undo_correction`/`recover_correction` to go through `ReviewService` + `apply_pending` (B02). Add fault-injection hook for crash tests (env `GA_TEST_FAULT_POINT=after_log_commit|during_generation_write|before_pointer_publish`, honoured only when `GA_TEST_FAULTS=1`).
7. Startup/first-read reconciliation via `apply_pending`.
8. Consolidate/retire workbench routes; remove module globals (B01).
9. Update frontend calls only if a retired route was in use (coordinate; keep out of backend PR if possible).

### 6.4 Regression tests (write first)

Fixture: `backend/tests/fixtures/raw_rows_two_teams.json` — ≥ 2 clusters with clearly separable colours, ≥ 40 frames, a ball track, and rows shaped as `Storage.load_raw_rows` expects (inspect `save_raw_rows` and `_classify_video_rows` in `processor.py` to build it). Provide a helper `install_raw_row_match(storage, tmp_path) -> match_id` that creates a `video` input-mode match with `teamClusters` and stores the raw rows. Keep a parallel `install_tracking_match` using `sample_tracking.json`.

`backend/tests/test_audit_v2_h02_review.py`:

- **T02 / B04 (raw-row):** record team of a known track; `submit_correction(kind="team_mapping", payload={"swap": True})`; **before** any further call, assert the persisted frames show the swapped team; then `reprocess_video_match(storage, match_id)` again and assert still swapped; then construct a **new `Storage`** on the same root (fresh process semantics; also run one variant in a real `subprocess`) and assert still swapped. Baseline: fails at the first assertion.
- **T02 variant (no raw rows):** same with `install_tracking_match`.
- **T05 / B04:** `track_split` then `track_join`, rebuild, undo each; assert every event/shot/ownership reference resolves to an existing track ID and the remap is consistent.
- **T03 / B02:** `@integration` — child `subprocess` runs a script that sets `GA_TEST_FAULTS=1 GA_TEST_FAULT_POINT=<point>` and calls `submit_correction`, exiting via `os._exit(1)` at the fault point. Parent constructs `Storage`, asserts the pointer references a **complete** generation (old or new, never mixed: manifest present and all files listed in it exist), calls `apply_pending`, asserts exactly one `applied` command and that the swap is applied exactly once (compare to expected frames). Run `apply_pending` twice; result identical. Repeat for each fault point and for `undo`.
- **T04 / B03:** reject a detected shot via `event_reject`; assert the shot list, shot-quality totals, player summaries, HTML, JSON and CSV exports no longer include it and `manifest.stale` is empty after rebuild (or report route labels stale). Accept again; undo; all views reconcile.
- **T01 / B01:** two stored matches; through `/api/matches/...`: query accepted events (must return the stored accepted events, not `[]`), generate an evidence-linked report (evidence IDs must be the server's), submit a correction, restart (new `Storage`/app), read again — results, revision numbers and effects agree. Post fake `events`/`claimedEvidenceIds`/`knownEvidenceIds` — assert none appear in output. For every `/api/workbench/...` compatibility route: either assert `410` with the documented body (retired) or assert byte-identical responses to the normal twin for the same match (alias). Run once with `GA_FLAG_LEFTOVER_HTTP` unset to prove the normal handlers, not leftover ones, served the requests.
- **T28 / B35:** POST valid job; POST same `requestId` with different payload → 409 `IDEMPOTENCY_CONFLICT`, attempts and reservations unchanged, original request unchanged; exact repeat → 200 with the original attempt. Cover `/api/workbench/jobs` and `/api/workbench/matches/{id}/jobs`.

### 6.5 Anti-patterns

- Calling `reprocess_video_match(self, match_id)` with the stored (pre-edit) config.
- Marking anything applied because `saveState == "saved"`.
- Mutating derived frames in place and hoping a later rebuild agrees.
- Fixing `execute_typed_query([], ...)` by passing `body.events`.
- Deleting raw rows to "protect" an edit.

---

## 7. H03 — Calibration, scoring and metric publication

**Items:** B05, B06, B07, B33 (calibration; P1), B22 (scorer; P1 before benchmark use), B23 (P1 report correctness), B24 (P2), B28 (P2).

### 7.1 What the code does today (verified)

- `geometry.py` L304–316 `_project`: no homography → returns `profile.landmarks[0]` pitch position, or `(0.0, 0.0)`. (B05)
- `geometry.py` L88–111 `evaluate_landmarks`: `residuals.sort()` then `zip(holdout, residuals)` for `far` (B06); far side = `mark.pitchY >= 45` fixed.
- `geometry.py` L114–123 `commit_calibration`: `committed = accepted`.
- `storage.py` L1661–1673 `commit_calibration_for_match`: saves artifact `calibration_profile` + `calibrationCommitted=True`; L1815–1820 `_stored_calibration_accepted` reads artifact `calibration_evaluation` (B07 split).
- `storage.py` L2399–2465 `calibration_for_match`: `if len(points) != 4: points = unit square`; builds homography from it; evaluates supplied holdouts; can `submit_correction(kind="calibration")` (B33).
- `analytics.py` L1227–1280 `_summary_metric_availability`: physical metrics `available` iff `identity_continuous` (B07); `experimental_shot_quality.value = round(sum(myTeamXg, enemyXg), 2)`, `unit="probability"` (B23). Sole caller: `analytics.py` ~L1196.
- `report_export.py` L56–66 `_format_available_metric(summary, "experimental_shot_quality", "myTeamXg", 2)` labelled "My Team experimental shot quality" (L166, L248); falls back to legacy key when record value is None and availability is `experimental`.
- `perception.py` L58–118 `score_detections`: filters labels by task, not detections by class; `localisationErrorPx = mean(1 - IoU)` (B22). `merge_tiled_detections` at L193.
- `schemas.py` `MatchConfig.pitchLengthM/pitchWidthM` exist but analytics use fixed dimensions (B24).

### 7.2 Target design

#### 7.2.1 Fail-closed projection and validated transforms (B05, B33)

```python
class CalibrationUnavailable(Exception): ...

def validate_homography(h) -> list[str]:  # reason codes; empty == valid
    # shape 3x3, all finite, abs(det) > 1e-9, cond < 1e8, h[2][2] != 0, inverse finite
def validate_fit_points(points, *, width, height) -> list[str]:
    # exactly 4 (or >=4 for auto), finite, inside source frame, not collinear (area > eps), distinct
def validate_holdouts(holdouts, fit_points, *, pitch_length, pitch_width) -> list[str]:
    # >= MIN_HOLDOUTS (default 4), not coincident with fit points, finite, inside pitch,
    # spatial coverage: at least one holdout in each pitch half (Y) and each X half
def _project(profile, x, y) -> tuple[float, float]:
    if not profile.homography: raise CalibrationUnavailable("NO_TRANSFORM")
    ...  # denom == 0 -> CalibrationUnavailable("DEGENERATE_POINT")
```

`evaluate_landmarks` catches `CalibrationUnavailable` → `accepted=False, reasonCodes=[code]`. Remove the landmark-0 and `(0,0)` fallbacks entirely.

`calibration_for_match`: if `len(manualHomographyPoints) != 4` and no accepted automatic transform → return `{"availability": "calibration_unavailable", "reasonCodes": ["MANUAL_POINTS_MISSING"], "committed": False}` **without** evaluating or submitting a correction. If a normalised-coordinate input is a real product need, add `MatchConfig.manualHomographyPointSpace: Literal["source_pixels", "normalized"] = "source_pixels"` and transform normalised points by the probed `width/height` — declared, not assumed.

#### 7.2.2 Paired residuals and camera-relative regions (B06)

```python
pairs = [(mark, residual(mark)) for mark in holdout]
sorted_residuals = sorted(r for _, r in pairs)
p95 = percentile(sorted_residuals, 0.95)      # keep current index formula or use numpy; document
far = [r for m, r in pairs if is_far_side(m, profile)]
```

`is_far_side`: use `profile.cameraSide` if declared (`"touchline_north" | "touchline_south" | "goal_east" | ...`); otherwise infer from the fit points (far = larger pitch distance from the camera-side touchline, computed via the transform's image-Y ordering); if inference fails, fall back to the fixed threshold **and** add `reasonCodes += ["FAR_SIDE_HEURISTIC"]`. Always return `farSideCount`.

#### 7.2.3 One calibration revision (B07)

New artifact `calibration_revision`:

```json
{"revisionId": "cal_<sha>", "profile": {...}, "evaluation": {...}, "accepted": true, "measured": true,
 "sourceSha256": "...", "validInterval": {"start": 0.0, "end": null}, "createdAt": "...",
 "fitPointSpace": "source_pixels", "pitchLengthM": 105.0, "pitchWidthM": 68.0}
```

- `commit_calibration_for_match`, `calibration_for_match`, `_stored_calibration_accepted`, `withhold_if_invalid` callers, and the H05 projection identity all read/write **only** this record via `Storage.calibration_revision(match_id) -> CalibrationRevision | None`.
- Migration reader: if only `calibration_profile`/`calibration_evaluation` exist, synthesise a revision with `migrated=True` (accepted only if the evaluation record says `accepted and measured`).
- Committing a new revision marks dependent generation outputs stale (`pitch_positions`, `physical_metrics`, `tactical_metrics`, `report`) via the H02 manifest and triggers `ReviewService.rebuild_generation(reason="calibration")`.
- `_summary_metric_availability(..., identity_continuous, calibration_accepted, eligible_seconds)`: physical metrics available **only if** `identity_continuous and calibration_accepted and eligible_seconds > 0`; otherwise `withheld` with the specific missing prerequisite(s) in `reasonCodes`. Update the caller at `analytics.py` ~L1196 and `_recompute_identity_continuity` to pass `calibration_accepted=storage.calibration_revision(match_id) is accepted`.

#### 7.2.4 Team-scoped metric records (B23)

Replace the single `experimental_shot_quality` record with:

- `my_team_experimental_shot_quality_sum` and `enemy_experimental_shot_quality_sum`: `unit="expected_shots_heuristic"`, `denominator="labelled_shots"`, `availability="experimental"`, `teamScope="my_team"|"enemy"`.
- Per-shot heuristic scores stay in `shots.json` (already produced by `workbench/shot_model.py`).
- `report_export.py`: add `_format_metric_record(summary, metric_id, digits)` with **no legacy-key fallback when a canonical record exists** (fallback allowed only when the record is absent entirely — legacy artifacts). Replace both call sites (L166, L248). Update `main.py` dashboard averages (~L1876–1877), `llm.py` context (~L374), `workbench/evidence.py` (~L265, ~L318, ~L429), CSV/JSON flatteners (`export_flatteners.py`) to consume the same typed records.
- Keep the old `experimental_shot_quality` ID emitted as `deprecated: true` for one release if the frontend reads it (`rg experimental_shot_quality frontend/src`).

#### 7.2.5 Scorer correctness (B22)

In `score_detections`:

```python
task_kind = "player" if task == "player_coverage" else "ball"
in_task = [d for d in detections if d.kind == task_kind]
other = [d for d in detections if d.kind != task_kind]
# matching loop over in_task only
# other: ignored by default, counted in `ignoredOtherClass`; if count_other_class_as_fp=True -> FP
```

Add `centreOffsetPx = mean(hypot(cx_d-cx_l, cy_d-cy_l))` for matched pairs; rename current field to `meanOneMinusIou`; keep `localisationErrorPx` **only** if it now holds the pixel value (update `BenchmarkReceipt` and every reader — `rg localisationErrorPx backend frontend`). In `merge_tiled_detections`, group suppression by `(frameId, kind)`.

#### 7.2.6 Metric eligibility semantics (B24)

Create `backend/app/workbench/metric_definitions.py` registry (`MetricDefinition(id, version, unit, denominator, scope, prerequisites, aggregation)`), used by `_summary_metric_availability` and the report. Then:

- Possession: time-weighted — `sum(frame_duration_s for controlled frames of team) / sum(frame_duration_s for eligible frames)`, where `frame_duration_s` = PTS delta to the next sampled frame (from H06 `DecodedFrame`/frame timestamps; if unavailable, fall back to equal weights **and** set `reasonCodes += ["EQUAL_DURATION_ASSUMED"]`).
- Formation segmentation: break a segment when an `unknown`/skipped interval exceeds a declared gap (`FORMATION_MAX_GAP_S`), never bridge.
- Defensive line / line-breaking: define required visibility (≥ N defenders visible in the frame) and role assumptions in the definition; when unmet → `unknown`.
- Physical distances: use `match.config.pitchLengthM/pitchWidthM` (default 105×68 **declared** in the metric record `pitchDimensions`), via the calibration revision's pitch size.

#### 7.2.7 Shared domain types (B28)

`backend/app/domain_types.py`: `FiniteFloat` (Annotated with `AfterValidator(math.isfinite)`), `Interval` (`start <= end`, finite), `Homography3x3` (validated via `validate_homography`), `Period` (non-overlapping, ordered), status `Literal`s. Apply in `MatchConfig`, `CalibrationProfile`, `Landmark`, `FrameData` coordinates, `MetricAvailabilityRecord.availability`. Keep permissive parsing only in `from_legacy_*` import functions; canonical artifacts must validate.

### 7.3 Implementation steps

1. Tests T06, T07, T21 first (pure functions; fail on baseline).
2. `_project` fail-closed + validators + `evaluate_landmarks` pairing + camera-side (B05, B06).
3. `calibration_for_match` unit-square removal (B33).
4. `CalibrationRevision` artifact + migration + single reader (B07 part 1).
5. `_summary_metric_availability` prerequisites (B07 part 2) + T08.
6. Team-scoped shot quality + export consumers (B23) + T04 metric assertions.
7. Scorer fix + tiled grouping (B22).
8. Metric definitions registry + possession/formation/pitch-size changes (B24) + T22.
9. Domain types applied at boundaries (B28) + property tests (use `hypothesis` if in dev requirements; otherwise parametrised NaN/inf/reversed cases).

### 7.4 Regression tests (write first)

`backend/tests/test_audit_v2_h03_calibration.py`:

- **T06 / B05:** profile with `homography=None` and one holdout equal to the first landmark → `accepted is False`, `reasonCodes == ["NO_TRANSFORM"]`. Singular (`det=0`), malformed (2×3), non-finite (`nan`) matrices → rejected with their codes. Positive control: identity transform, 4 valid holdouts with coverage → accepted, `p95M == 0`.
- **T06 / B33:** match with `manualHomographyPoints=[]`; POST calibration with holdouts that fit the unit square perfectly → `committed False`, `availability calibration_unavailable`, **no** correction in the log, `_stored_calibration_accepted` False. Positive: real source-pixel points; if normalised space is supported, declared `manualHomographyPointSpace="normalized"` case; custom pitch size; 3-point and 5-point inputs rejected; rotated video (`rotation=90`) handled.
- **T07 / B06:** 40 holdouts, one far-side point with residual 100; shuffle order across 10 seeds → `farSideMaxM == 100` and `accepted` identical every time. Baseline: acceptance flips (audit G3).
- **T08 / B07:** promote identity (`identity_validate`) without an accepted calibration → physical metrics `withheld`, `reasonCodes` include `CALIBRATION_UNAVAILABLE`. Commit calibration → `_stored_calibration_accepted`, `calibration_for_match`, and metric availability all agree; changing calibration marks dependants stale and rebuild changes projected coordinates.
- **T21 / B22:** a `ball` detection perfectly overlapping a `player` label in `player_coverage` → 0 TP, 1 FN (and 0 FP by default, `ignoredOtherClass == 1`); detection offset by (3,4) px → `centreOffsetPx == 5.0`; tiled detections in different frames/classes are not suppressed.
- **T04 / B23:** `myTeamXg=0.4`, `enemyXg=0.6` → HTML shows 0.40 for my team, JSON/CSV/dashboard/provider context carry `my_team_...=0.4`, `enemy_...=0.6`; one team unmeasured → that record `unknown`, other unaffected; both unmeasured → both `unknown`, HTML "Unavailable".
- **T22 / B24, B28:** unequal frame durations change time-weighted possession vs frame-count possession as expected; formation segments break across an unknown gap; `pitchLengthM=100, pitchWidthM=64` changes distance outputs; `MatchConfig(pitchLengthM=float("nan"))`, reversed periods, 2×3 homography → validation errors; a legacy fixture still imports via `from_legacy_*`.

### 7.5 Anti-patterns

- Lowering the holdout requirement so the unit square passes.
- Putting calibration in the immutable detection cache key to force invalidation (belongs in projection identity, H05).
- Adding a `calibrationAccepted` boolean to summary without reading the revision.
- Keeping `unit="probability"` on a sum.

---

## 8. H04 — Authoritative jobs, leases and budgets

**Items:** B10, B11 (+A5), B12 — all P1. Must be complete before unattended paid execution.

### 8.1 What the code does today (verified)

`backend/app/workbench/jobs.py` `DurableJobLedger`:

- In-memory `self.requests`, `self.attempts`, `self.costs`, `self.cancel_flags`; `_load` reads everything; `_persist` (L165–192) rewrites **every** request/attempt/cost row with `INSERT OR REPLACE` on every mutation (O(history) writes; stale instance overwrites newer state).
- `reconcile_after_restart` (L194–199): any attempt whose status is running → `timeout_before_response` → `outcome_unknown`, with no lease/owner check (a live job in another process is marked unknown by merely constructing a ledger).
- `submit` (L201–222): payload mismatch → `ValueError`; if latest attempt `failed|cancelled|outcome_unknown` → creates a **new attempt** with `reservedCost=request.budget` and a new `CostEntry` — bypassing `retry`'s `MAX_ATTEMPTS=3` and its unknown-outcome block (B10), and re-reserving the full budget (B12).
- `retry` (L257–273): blocks unknown, enforces `MAX_ATTEMPTS`, appends attempt **without** a `CostEntry` (B12 divergence).
- `transition` (L224–231): unconditional last-attempt update.
- `cancel`/`request_cancel`/`confirm_cleanup`: flags only; no `termination_confirmed` state.
- `storage.py` L274 constructs `DurableJobLedger(db_path=self.db_path)` and `main.py` ~L675 passes it into `create_workbench_router(..., ledger=storage.job_ledger)`, so the app has one instance today; but `routes.py` L134 still has a fallback that constructs a second ledger on the same file when `ledger` is `None`, and any worker/CLI process constructing its own `Storage` gets its own in-memory mirror — which is exactly the multi-instance case B11 describes.

### 8.2 Target design

Rewrite `DurableJobLedger` so **SQLite is the authority** and the object holds no mutable mirror.

Schema (migration from the current `job_ledger_*` tables: import rows into the new tables once, keep old tables read-only for provenance):

```sql
CREATE TABLE job_requests (
  request_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
  authorised_budget REAL NOT NULL, revision INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE job_attempts (
  attempt_id TEXT PRIMARY KEY, request_id TEXT NOT NULL REFERENCES job_requests(request_id),
  sequence INTEGER NOT NULL, status TEXT NOT NULL, owner_id TEXT, lease_expires_at REAL,
  revision INTEGER NOT NULL DEFAULT 0, reconciled INTEGER NOT NULL DEFAULT 0,
  payload_json TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(request_id, sequence));
CREATE TABLE job_charges (
  charge_id TEXT PRIMARY KEY, request_id TEXT NOT NULL, attempt_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('reserved','estimated','unsettled','settled','released')),
  amount REAL, recorded_at TEXT NOT NULL);
CREATE TABLE job_cancels (
  request_id TEXT PRIMARY KEY, requested_at TEXT NOT NULL,
  termination_confirmed_at TEXT, cleanup_confirmed_at TEXT, cleanup_result TEXT);
```

Connection: `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000; PRAGMA foreign_keys=ON;` every transactional method uses `BEGIN IMMEDIATE`.

API:

```python
class DurableJobLedger:
    def admit(self, request: JobRequest, *, mode: Literal["submit", "retry"], owner_id: str,
              lease_seconds: float) -> JobAttempt
    def transition(self, attempt_id: str, *, expected_revision: int, owner_id: str,
                   status: JobStatus, **updates) -> JobAttempt          # raises StaleTransition / NotOwner
    def heartbeat(self, attempt_id: str, *, owner_id: str, lease_seconds: float) -> None
    def reclaim_expired(self, *, now: float) -> list[JobAttempt]        # lease-expired running -> outcome_unknown
    def reconcile_attempt(self, attempt_id: str, *, provider_outcome: Literal["complete","failed","not_found"],
                          settled_cost: float | None) -> JobAttempt      # clears the unknown state
    def record_charge(self, attempt_id: str, *, kind, amount) -> None
    def request_cancel / confirm_termination / confirm_cleanup(...)
    def receipt(self, request_id: str) -> JobPhase                       # read-only projection
```

`admit` (one transaction):

1. `SELECT ... FROM job_requests WHERE request_id=?`. If absent → insert request; go to 6.
2. If present and `payload_sha256` differs → raise `IdempotencyConflict` (H02 maps to 409).
3. Load latest attempt. If status non-terminal → return it (idempotent replay).
4. If terminal `complete` → return it.
5. If `failed|cancelled` and `mode == "submit"` → return latest (no new attempt: ordinary repeats are idempotent). If `outcome_unknown` → require `reconciled == 1` else raise `ReconciliationRequired` regardless of mode. Only `mode == "retry"` (explicit route/operator action) proceeds.
6. Enforce `sequence + 1 <= MAX_ATTEMPTS` (`RetryBudgetExhausted`) and the money invariant (§12.3): `settled + outstanding_reserved + new_reservation <= authorised_budget`, where `new_reservation = min(estimate, authorised_budget - settled - outstanding_reserved)`; if that is `<= 0` → `BudgetExhausted`.
7. Insert attempt (`status="submitted"`, `owner_id`, `lease_expires_at`) and a `reserved` charge in the same transaction.

`transition`: `UPDATE job_attempts SET ..., revision = revision + 1 WHERE attempt_id=? AND revision=? AND (owner_id=? OR lease_expires_at < ?)`; `rowcount == 0` → read the row and raise `StaleTransition(expected, actual)` or `NotOwner`. Cancel flag check as today but via the `job_cancels` table.

`reclaim_expired`: only attempts with `status IN running AND lease_expires_at < now` → `outcome_unknown` with `error="lease_expired"`. **Constructor does not reconcile.** Remove `reconcile_after_restart` or make it call `reclaim_expired(now)` explicitly from the app's startup task with a clear log line.

Charges: `retry` (admit mode retry) always writes a `reserved` charge; completion writes `settled` and `released` (reserved − settled); unknown outcome converts the reservation to `unsettled` (still consumes capacity); `reconcile_attempt` settles or releases it. `receipt()` computes `attemptCount` from `job_attempts`, `reservedTotal`, `settledTotal`, `unsettledTotal`, and `actualTotal = None if unsettledTotal > 0 else settledTotal`.

Single authority: because SQLite becomes authoritative, multiple `DurableJobLedger` objects (API process, worker process, CLI) on the same file are now safe by design — that is the point of T11. Still remove the fallback construction at `routes.py` L134 so the router cannot silently open a different `db_path` than `Storage`.

### 8.3 Implementation steps

1. Tests T10, T11, T12 first (T11 needs two real processes — see below); confirm baseline failures.
2. New schema + one-shot migration from `job_ledger_*` tables + `errors.py` exceptions.
3. `admit`/`transition`/`heartbeat`/`reclaim_expired`/`reconcile_attempt`/charges.
4. Replace all `submit(`/`retry(`/`transition(` callers (`rg "job_ledger\.\|ledger\." backend/app`): routes, `Storage`, workers. Retry becomes an explicit route `POST /jobs/{id}/retry` (or existing if present) calling `admit(mode="retry")`.
5. Worker heartbeats where jobs run (`backend/app/worker.py`, `jobs.py` `JobRunner`, `remote_worker.py`).
6. Startup task: `reclaim_expired` + log.
7. Document the budget contract in `docs/runbooks/` (one page) and in the receipt schema.

### 8.4 Regression tests (write first)

`backend/tests/test_audit_v2_h04_jobs.py`:

- **T10 / B10:** for each prior state (`submitted`, `running`, `complete`, `failed`, `cancelled`, `outcome_unknown`) call `admit(mode="submit")` with the same request → existing attempt returned or `ReconciliationRequired`; assert attempt count unchanged and no dispatch hook called. `admit(mode="retry")` after `failed` × 3 → `RetryBudgetExhausted` (baseline: 7 attempts possible). `outcome_unknown` + `mode="retry"` → `ReconciliationRequired`; after `reconcile_attempt(..., "failed")` → retry allowed if budget remains.
- **T11 / B11:** `@integration` — parent creates ledger on `tmp_path/ledger.sqlite3`, admits and transitions attempt A to `running` with `owner_id="p1"`, lease 60 s. Spawn a real `subprocess` (or `multiprocessing` with `spawn`) that opens **a new ledger on the same file**: assert A is still `running` (no false abandonment). Child attempts `transition(A, expected_revision=stale)` → `StaleTransition`; child attempts transition with `owner_id="p2"` before lease expiry → `NotOwner`. Advance a fake clock past the lease; `reclaim_expired` → `outcome_unknown`. Contention: two processes each admit 200 distinct request IDs concurrently; all 400 present, no `UNIQUE` violations, no lost rows. Write amplification: wrap the connection with `sqlite3.Connection.set_trace_callback` counting statements during one `transition` with 1,000 historical rows → statements touch only that attempt (≤ a small constant), not 1,000 rows.
- **T12 / B12:** authorised budget 1.25; first attempt reserves 1.25; fail with settled 0.5 → outstanding 0, settled 0.5; retry reserves `min(estimate, 0.75)`; a third retry after another settled 0.5 reserves ≤ 0.25; sum(settled)+outstanding never exceeds 1.25; `outcome_unknown` keeps `unsettledTotal > 0` and `actualTotal is None`; cancel after partial charge keeps settled cost; repeat idempotency key does not add a charge; every attempt has ≥ 1 charge row.

### 8.5 Anti-patterns

- Keeping `self.attempts` as a mirror and "syncing" it.
- `INSERT OR REPLACE` of unrelated rows in any transition.
- Marking `outcome_unknown` on construction.
- Reserving `request.budget` again on each retry.
- Deleting history to reduce writes.

---

## 9. H05 — Real recomputation, evidence identity and truthful receipts

**Items:** B08 (P1), B09 (P1), B18 (P1 for performance claims), B25 (P2), B29 (P1 for promotion claims). Depends on H02 generations and H03 `CalibrationRevision`.

### 9.1 What the code does today (verified)

- `storage.py` L1675–1723 `recompute_for_match`: builds `previous`/`current` via `cache_identity(... interval 0.0..0.0, decoder_version="opencv", model_hash="weights-v1", ...)`, calls `reprocess_for_change(...)` with a vision callable that raises, then `result["admitted"] = True` and returns — **no artifact is loaded or committed** (B08, B09).
- `video_pipeline.py` L83–90 `process_video_input`: `payload.update(_sampling_and_cache(source_clock, adapter))`; L94–150 `_sampling_and_cache` builds a **fresh** `SamplingAudit` (zero counters), returns `"fourRates": asdict(four_rates_receipt(audit))` plus `cache_identity(source_sha256=source_sha or "0"*64, interval 0..0, decoder_version=adapter.name, model_hash="unspecified", ...)` and metadata-only `PreprocessorAdapter().transform(pixels=b"", ...)` / `DetectorAdapter().detect(...)`. This overwrites the producer's measured `fourRates` (B18).
- `run_guerilla.py` L8779–8806 returns real `fourRates` from `sampling_audit.four_rates()` and `decodeAnchors` with `middle == end == last_export_presentation_time`.
- `workbench/assistance.py` L114 `execute_typed_query`: missing team/period satisfy explicit filters (B25).
- `workbench/evaluation.py` L66 `current_repository_evaluation_gate` hardcodes `complete_tasks=0`; L104 `score_hota_idf1` returns `scored = not reasons` with `hota=None, idf1=None` (B29).

### 9.2 Target design

#### 9.2.1 Plan vs execute (B08)

```python
class RecomputePlan(StrictModel):      kind: Literal["plan"]; change: str; rebuild: list[str]; requires: list[str]; visionRequired: bool
class RecomputeReceipt(StrictModel):   kind: Literal["executed"]; change: str; inputArtifacts: dict[str, str]  # layer -> digest
                                       outputGeneration: str; rebuilt: list[str]; detectorCalls: int  # must be 0 for image-space-safe
class RecomputeRefusal(StrictModel):   kind: Literal["refused"]; reasonCodes: list[str]  # e.g. CACHE_MISS, VISION_REQUIRES_SEALED_WORKER
```

- `Storage.plan_recompute(match_id, change) -> RecomputePlan` (what `recompute_for_match` does today, minus `admitted`).
- `Storage.execute_recompute(match_id, change) -> RecomputeReceipt | RecomputeRefusal`: resolve the current generation; load the immutable observation artifact for the required layer (raw rows / detections with their `DetectionIdentity`); if missing → `RecomputeRefusal(CACHE_MISS)`; apply overlays (H02), project with the current `CalibrationRevision`, recompute dependants, publish a new generation; return the receipt with the **real** input digests and output generation ID; assert `detectorCalls == 0` for image-space-safe changes.
- Routes: existing recompute endpoint returns the plan (`kind: "plan"`, no `admitted`, no `reused`); add `.../recompute/execute` for execution. Update the frontend only if it reads `admitted` (`rg admitted frontend/src`).

#### 9.2.2 Layered identities (B09)

In `backend/app/workbench/cache.py` replace the single `cache_identity` with typed, layered identities:

```python
DetectionIdentity(source_sha256, stream_index, interval: Interval, weights_sha256, preprocessing_id, class_map_id,
                  precision, runtime_build)                     # decoder/runtime build string incl. versions
TrackingIdentity(detection: DetectionIdentity, tracker_config_id)
ProjectionIdentity(tracking: TrackingIdentity, calibration_revision)
ReviewedIdentity(projection: ProjectionIdentity, correction_head)
ReportIdentity(reviewed: ReviewedIdentity, report_template_version)
```

Each has `.digest()` and `.reusable` (False if any component is `None`/unknown). Delete the `"0"*64`, `"unspecified"`, `"weights-v1"`, `0.0..0.0` placeholders; source the real values: `source_sha256` from H06 streaming hash, `weights_sha256` from the resolved model file (`materialize_proof_runtime_options` in `processor.py`), `runtime_build` from `ultralytics.__version__`/`torch.__version__`/decoder build (probe), `interval` from the actual processed interval. Calibration lives only in `ProjectionIdentity`.

#### 9.2.3 Truthful receipts (B18)

- In `process_video_input`, **do not** `payload.update(...)` over producer keys. Split: `payload["policy"] = declared_sampling_policy(source_clock)` (declared intent: target fps, interval, temporal policy, requested backend), and leave `payload["fourRates"]`, `payload["samplingReceipt"]`, `payload["decodeAnchors"]` as produced. Add `validate_producer_receipt(payload)` that fails loudly if `fourRates` is missing or has non-int counts.
- Remove the metadata-only `preprocessor`/`detector` objects from the payload (or move to `policy.requested`).
- In `run_guerilla.py`: `decodeAnchors.middle` = the exported frame nearest the median exported PTS; `end` = last exported PTS; `beginning` = first exported PTS. If fewer than 3 exports → `None` for the missing anchors.
- Counter semantics: `detectorPrimaryCount`/`detectorRecoveryCount` increment **per model invocation** (wrap the `model.track/predict` calls), `boxCount` is separate; `trackerUpdateCount` per tracker update; `decodeCount` per decoded frame; `exportCount` per exported sample. Add `hardware: {declaredBackend, observedDevice | None}` where `observedDevice` comes from the actual tensor device when available, else `None`.
- Every downstream view (API bundle, artifact, export) must carry these values unchanged — one test compares them end-to-end.

#### 9.2.4 Exact typed search (B25)

In `execute_typed_query`: for each explicit filter (`team`, `period`, `kind`, time window), events with `None`/unknown values are excluded unless `query.includeUnknown is True`. `parse_typed_query` returns `TypedQuery(..., interpreted: dict, unsupportedTerms: list[str])`; the route returns `interpreted` and `unsupportedTerms` and, if `strict=True`, 422 when `unsupportedTerms` is non-empty. Successor constraints become structured `SuccessorConstraint(kind, team: Literal["same","opponent",...]|None, period: int|None, withinSeconds: float|None)` and are evaluated against the successor's own fields.

#### 9.2.5 Evaluation states (B29)

`EvaluationStatus = Literal["prerequisites_unmet", "prerequisites_ok", "executed", "scored"]`. `score_hota_idf1` returns `status="prerequisites_ok"` (never `scored=True`) unless it actually ran a scorer and has numeric `hota`/`idf1`; an executed scorer with null values is `executed`, not `scored`. `current_repository_evaluation_gate` reads a versioned manifest (`backend/evaluation/manifest.json` or the existing release-evidence location — `rg -n "evaluation" backend/app/release_manifest.py backend/release`) listing artifacts, digests, scorer version and results; missing manifest → `status="unknown"` with `reasonCodes=["EVALUATION_MANIFEST_MISSING"]`, not zeros. Promotion/quality receipts constructed from placeholders (`rg -n "placeholder\|latencyMs=None\|peakMemoryMb=None" backend/app/workbench/receipts.py backend/app/workbench/evaluation.py`) must publish `None` and a `notRecorded` list.

### 9.3 Implementation steps

1. Tests T09, T17, T23 first.
2. Layered identities + real component sourcing (B09).
3. `plan_recompute`/`execute_recompute` + routes (B08).
4. Receipt preservation + anchors + counter semantics (B18).
5. Typed search exactness (B25).
6. Evaluation statuses + manifest reader (B29).

### 9.4 Regression tests (write first)

`backend/tests/test_audit_v2_h05_recompute.py`:

- **T09 / B08:** raw-row match with accepted calibration; change calibration revision; `execute_recompute(change="calibration")` → projected pitch positions differ, `detectorCalls == 0`, `outputGeneration` exists on disk and equals the pointer. Delete the observation artifact → `RecomputeRefusal(CACHE_MISS)`, no generation created, no `reused`/`admitted` keys anywhere in the response. Plan route response has `kind == "plan"` and no `admitted`.
- **T09 / B09:** changing each identity component (weights digest, interval, class map, calibration revision, correction head, template version) invalidates exactly its layer and downstream layers; a report-only change preserves `DetectionIdentity.digest()`; any `None` component → `reusable is False`; two matches with unknown source identity never share a digest.
- **T17 / B18:** stub the producer (`run_guerilla` entry used by `process_video_input`) to return known `fourRates` (250 decoded / 50 exported / 12 primary / 3 recovery) and anchors; assert `process_video_input` output carries the identical values and that `policy` is a separate key. `@real_media`: on a generated 5-second clip, assert `detectorPrimaryCount` equals the number of wrapped model invocations counted by a spy, `decodeAnchors.beginning < middle < end`, and the same values appear in the stored artifact and the API bundle.
- **T23 / B25:** events with `team=None`, `period=0`, and successors from the wrong team/half; query "our second-half turnovers followed by opponent shots" → only exact matches; `interpreted` and `unsupportedTerms` returned; `strict=True` with an unsupported qualifier → 422.
- **B29:** prerequisites satisfied but scorer not run → `status == "prerequisites_ok"`, `hota is None`; a scored fixture requires prediction/label digests, scorer version, source identity and numbers; missing manifest → `unknown`, not `0`.

### 9.5 Anti-patterns

- `result["admitted"] = True` on a plan.
- `payload.update(...)` over producer keys.
- `source_sha256 or "0" * 64`.
- Broadening a query when a qualifier is not understood.

---

## 10. H06 — Bounded media and truthful adapters

**Items:** B16 (+A4; P1 for long recordings), B17 (P1 for the FFmpeg challenger), B19 (P1 for evaluation alignment), B20 (P2), B21 (P2), B34 (P2).

### 10.1 What the code does today (verified)

- `media.py` L208–212 `probe`: `hashlib.sha256(path.read_bytes())` when an injected identity is present; L214–222 `iter_frames`: injected-frames branch does `path.read_bytes()[:1]` (reads the whole file). Other whole-file hashing sites: `rg -n "read_bytes()" backend/app/workbench/media.py backend/app/video_pipeline.py backend/app/remote_worker.py backend/app/storage.py`.
- `media.py` L228–307 `_iter_ffmpeg_decode`: `Popen(stdout=PIPE, stderr=PIPE)`; main loop `process.stdout.read(frame_size)` (a short read is treated as EOF); non-blocking `select` drain of stderr into `stderr_chunks`; `_pts_time_from_showinfo(b"".join(stderr_chunks), index)` **re-joins and re-parses the whole log per frame**; when no pts is found, `process.stderr.read()` **blocks to EOF** while the child may be blocked writing stdout (deadlock risk); `pts = int(round(t * timeBaseDen))` (ignores the numerator, B19); `returncode` never checked; `finally` kills and waits 5 s.
- `media.py` L444–449 `_assert_safe_ffmpeg_argv` accepts basename `ffmpeg|ffprobe`; `access.py` L153–160 `constrained_decoder` accepts only the exact strings `ffmpeg|ffprobe` → a configured `/usr/bin/ffmpeg` is rejected by the decode path that calls both (B34).
- `media.py` L491 `export_timestamp_seconds` rounds to 2 decimals; `should_export_on_source_grid` (L499) defines the grid relative to the last export rather than an absolute origin (B19).
- `perception.py` L211 `PreprocessorAdapter` returns crop/resize metadata without transforming pixels and swaps RGB in a Python byte loop; L350 `TrackerAdapter.associate` is IoU-only and not BoTSORT (B20); L245 `DetectorAdapter` selects CPU when CUDA requested but `video_engine_capability` is False (B21).

### 10.2 Target design

#### 10.2.1 Streaming hash service (B16)

`backend/app/workbench/hashing.py`:

```python
@dataclass(frozen=True)
class FileIdentity: sha256: str; size: int; mtime_ns: int; inode: int | None
def stream_sha256(path: Path, *, chunk_size: int = 1 << 20) -> FileIdentity
class HashCache:  # keyed by (resolved path, size, mtime_ns, inode); persisted JSON under storage root
    def identity(self, path: Path) -> FileIdentity
```

Replace every `read_bytes()` hashing site with `HashCache.identity(path).sha256`. Delete `path.read_bytes()[:1]`; if the injected branch must assert the file is readable, use `with path.open("rb") as fh: fh.read(1)`. Keep `remote_worker.py`'s existing secure hashing semantics (same digest algorithm; only the I/O pattern changes).

#### 10.2.2 Concurrent, bounded FFmpeg decode (B17, B19)

Rewrite `_iter_ffmpeg_decode`:

- Command adds `-nostdin -protocol_whitelist file,pipe` and uses the trusted resolved executable (10.2.3). Prefer `-vf showinfo` output parsed for `n:`, `pts:` and `pts_time:` fields so integer PTS is available directly.
- Start a **stderr reader thread** that reads `read1(65536)` chunks, feeds an **incremental** parser (carry-over of the partial last line only), stores `pts_by_index[n] = (pts_int, pts_time)`, keeps a bounded `collections.deque(maxlen=256)` of raw diagnostic lines, and signals a `threading.Condition`.
- Main thread reads **exactly** `frame_size` bytes per frame (loop on short reads; EOF mid-frame → `TruncatedStream`), then waits on the condition (with a timeout, e.g. 5 s) for `pts_by_index[index]`; missing after timeout → `presentation_clock="missing"`, `pts=None` (never `0.0`).
- Cancel: `process.kill()`, `process.wait(timeout)`, close pipes, `thread.join(timeout)`; raise `DecodeCancelled`.
- End: after EOF `returncode = process.wait(timeout)`; nonzero → `DecoderFailed(code, tail=list(diagnostics))`; zero with truncated output → `TruncatedStream`.
- `DecodedFrame` gains `time_base: tuple[int, int]` and its existing `pts` field holds the **decoder's integer PTS** (from showinfo `pts:`), not `round(t * den)`; `presentation_time_seconds` is derived as `Fraction(pts * num, den)` (float only at the API edge). `SourceClockIdentity` already carries `timeBaseNum` and `timeBaseDen` (populated at `media.py` ~L403–404 from ffprobe `time_base=1001/30000` → num 1001, den 30000); the defect is that the decode loop at L290 uses only `timeBaseDen`. Use both, everywhere PTS is converted.
- Sampling grid (`should_export_on_source_grid` and friends): define `grid_origin_pts` (first frame's PTS, or the stream `start_pts`) and `grid_step_pts = den / (num * target_fps)` as a `Fraction`; export the first frame whose `pts >= origin + k*step` for each `k`; ties/duplicates: first occurrence wins, duplicates flagged. Display rounding (`round(..., 2)`) is applied only in serialisers; canonical artifacts store `pts` + `time_base`.

#### 10.2.3 Trusted executable resolution (B34)

`backend/app/workbench/executables.py`:

```python
def resolve_trusted_executable(name: Literal["ffmpeg", "ffprobe"], *, configured: str | None, settings) -> Path
```

Rules: if `configured` is set it must be absolute, exist, be a regular file, be executable, not be world-writable, have basename `name` (or `name.exe`), and either reside in `settings.trusted_bin_dirs` (default: `/usr/bin`, `/usr/local/bin`, `/opt/homebrew/bin`, plus `GA_TRUSTED_BIN_DIRS`) or match `settings.ffmpeg_sha256`/`ffprobe_sha256` if configured; otherwise `shutil.which(name)` resolved to an absolute path with the same checks. Both `constrained_decoder` and `_assert_safe_ffmpeg_argv` accept `argv[0]` only if `Path(argv[0]) == resolve_trusted_executable(...)`. `FfmpegProbe` stores the resolved absolute path and passes it consistently.

#### 10.2.4 Honest adapters (B20, B21)

- Rename `PreprocessorAdapter` → `PreprocessPlan` if it stays metadata-only and keep it out of production payloads; implement a real `Preprocessor.transform(frame) -> (np.ndarray, InverseTransform)` using numpy (`np.frombuffer(payload, np.uint8).reshape(h, w, 3)`, `[..., ::-1]` for colour swap, slicing for crop, `cv2.resize` when available with a pure-numpy nearest fallback) and test pixels + inverse box mapping against a reference.
- `TrackerAdapter` → wrap the **core** Ultralytics/BoTSORT output (`results.boxes.id`) preserving IDs; rename the IoU helper to `IouAssociationFallback` and never emit its IDs into production artifacts.
- `DetectorAdapter`: replace the coupled decision with `probe_capabilities() -> Capabilities(hw_decode: bool|None, cuda_inference: bool|None, hw_encode: bool|None, notes)` (CUDA inference via `torch.cuda.is_available()` when torch is importable, else `None`); `select_inference_device(requested, caps)` uses only `cuda_inference`. `decode_memory_policy` uses only `hw_decode`. Add `observedDevice` to receipts (H05). No GPU-resident/zero-copy claims in any payload until an end-to-end benchmark artifact exists (keep `zeroCopy: False`/`None`).

### 10.3 Implementation steps

1. Tests T15, T27 first (pure/unit), then T16/T18 (`@real_media`).
2. `hashing.py` + replace all sites (B16).
3. `executables.py` + both guards + `FfmpegProbe` (B34).
4. Decode loop rewrite + `DecodedFrame`/`SourceClockIdentity` PTS fields + grid definition + display rounding at the edge (B17, B19). Update `export_timestamp_seconds` callers and `run_guerilla.py` sampling to consume `pts`/`time_base`.
5. Adapters and capability probes (B20, B21).
6. Generated-media fixtures: `ffmpeg -f lavfi -i testsrc=duration=5:size=320x240:rate=30000/1001` (fractional), `-vf setpts` variants for VFR/duplicate PTS, and a truncated copy (`head -c`).

### 10.4 Regression tests (write first)

`backend/tests/test_audit_v2_h06_media.py`:

- **T15 / B16:** create a 300 MB sparse/random file in `tmp_path`; hash via `stream_sha256` under `resource.setrlimit(RLIMIT_AS, ...)` in a child process (POSIX; skip elsewhere) sized well below the file size; assert digest equals `hashlib.sha256` streamed reference and the process does not die; assert `HashCache` returns the cached identity without re-reading (count `open` calls via monkeypatch). Assert no `read_bytes()` remains at hashing sites (`rg` in test is acceptable as a guard).
- **T16 / B17:** `@real_media` — (a) real ffmpeg on a generated CFR clip: frame count and PTS sequence match `ffprobe -show_frames`; (b) wrap the child in a shim script that delays stderr by 2 s while streaming stdout: decode completes without deadlock within a timeout; (c) a shim that never prints showinfo: frames yield with `presentation_clock == "missing"`, `pts is None`; (d) set `cancel_event` mid-decode: generator stops, `process.poll() is not None`, reader thread joined; (e) truncated input → `TruncatedStream` or `DecoderFailed`, never a silent clean end; (f) `exit 1` shim → `DecoderFailed(code=1)` with bounded diagnostics (`len(tail) <= 256`).
- **T18 / B19:** `time_base=(1001, 30000)`, `pts=30` → `presentation_time_seconds == Fraction(30030, 30000)` and round-trip `pts == 30` (baseline: 30030); VFR fixture with duplicate PTS → duplicates flagged; off-grid clip → selected frames equal an independently computed expected list; display value rounded only in the API serialiser.
- **T19 / B20:** track a synthetic moving box through 10 frames via the wrapped tracker → stable ID; crop/resize on a known image → pixel equality with the reference and inverse box mapping within 0.5 px.
- **T20 / B21:** `Capabilities(hw_decode=False, cuda_inference=True)` + `requested="cuda"` → inference device `cuda`; `cuda_inference=None` → `cpu` with `reasonCodes=["CUDA_UNPROBED"]`.
- **T27 / B34:** configured `/usr/bin/ffmpeg` (or the `which` result) passes both guards and the decode path; `/tmp/ffmpeg` (untrusted dir), `ffmpegx`, a missing path, and `http://` inputs are refused; ffmpeg and ffprobe configured separately.

### 10.5 Anti-patterns

- `process.stderr.read()` anywhere in the frame loop.
- `b"".join(stderr_chunks)` per frame.
- `pts = round(t * den)`.
- Accepting any path whose basename is `ffmpeg`.
- Renaming a metadata adapter and leaving its output in production payloads.

---

## 11. H07 — Reproducible environments and acceptance lanes

**Items:** B30 (P2), B31 (P2), B32 (P1 acceptance gate).

### 11.1 What the code does today (verified)

- `.github/workflows/ci.yml`: one `verify` job, Python 3.11, `pip install -e . -r backend/requirements-dev.txt`, `pip install -e ./research-addon`, `npm ci`, `VERIFY_CODE_ONLY=1 scripts/verify.sh`.
- `scripts/verify.sh`: code-only ignores listed in §2.2; `BACKEND_MINIMUM=3000`; frontend lint/typecheck/build; backend import smoke; release gates only in the non-code-only mode.
- `conftest.py`: `GA_FLAG_LEFTOVER_HTTP=1` default; conditional stubs.
- `backend/requirements-ml.txt` lists NVIDIA CUDA libraries and Triton unconditionally; `daytona_worker/requirements.lock` is the only lock.
- `train_custom.py` function default base model ≠ CLI default; `training_quality_gate.py` uses a line-based YAML parser and takes per-metric maxima across epochs.

### 11.2 Target design

- **Profiles:** `backend/requirements/api.in`, `cpu-cv.in`, `cuda.in` (+ `dev.in`), compiled with `pip-compile --generate-hashes` to `api.lock`, `cpu-cv-macos.lock`, `cuda-linux.lock`. Add `pyproject.toml` extras `[project.optional-dependencies] api = [...], cv = [...], cuda = [...]`. CUDA/Triton packages carry `; sys_platform == "linux"` markers and live only in `cuda.in`. Keep the existing `requirements-*.txt` as thin includes for one release, then remove.
- **Stub visibility:** in `conftest.py`, record which stubs were installed into `request.config.stash` and print a one-line summary in `pytest_terminal_summary` (`stubs_active: cv2,pandas`). Write it to `.verification/receipt.json` if `verify.sh` is running.
- **Default-flag lane:** a test module that builds `create_app` after `monkeypatch.delenv("GA_FLAG_LEFTOVER_HTTP")` (or spawns `python -m pytest ... -q` in a subprocess with the variable removed from the inherited env) and asserts: leftover routers are **not** mounted at `/api` (only at `/api/workbench/dev`), every path the frontend calls (`frontend/src/utils/workbench.ts`) still resolves to a `main.py` handler, and the H01–H05 regression tests pass unchanged (B32). This matters because `attach_leftover_*_routes` mount the leftover routers at `/api` when the flag is on, so a test that passes under `conftest.py` may be exercising leftover code, not the production handler.
- **CI lanes** in `ci.yml`:
  - `verify` (unchanged, code-only).
  - `integration`: `apt-get install ffmpeg`, `pip install -e .[cv] -r backend/requirements/dev.lock`, `pytest -m "integration or real_media" backend/tests`. Runs on PRs.
  - `real-media`: generated clips only (no licensed footage), `pytest -m real_media`.
  - `gpu-acceptance`: `workflow_dispatch` only, self-hosted/Daytona runner, runs `test_gpu_worker.py`, `test_run_guerilla.py`, and the football evaluation with explicit approval; uploads source-bound logs and receipts.
  - Each lane uploads `.verification/logs/` and a `receipt.json` naming commit, profile, stubs active, and counts.
- **B30:** one `DEFAULT_BASE_MODEL` constant in `train_custom.py` used by both the function and the CLI; `training_quality_gate.py` uses `yaml.safe_load` (confirm `pyyaml` is a dependency; if not, add to `cpu-cv.in`) and reads Ultralytics `results.csv` to bind metrics to the **epoch of the promoted checkpoint** (`best.pt` epoch from `results.csv`/`best_fitness`), publishing per-epoch maxima only under `trainingProgressDiagnostics`; hashes dataset manifest, config and weights into the gate output; validates split independence (no shared image hashes between train/val).

### 11.3 Implementation steps

1. Add pytest markers (§3.3) and the stub-summary hook.
2. Default-off flag test (B32).
3. Requirements profiles + locks; update README/runbook install sections.
4. CI lanes.
5. B30 changes + T25.
6. Ensure every H01–H06 `@integration`/`@real_media` test is collected by the new lanes (grep markers in CI logs).

### 11.4 Regression tests (write first)

- **T24 / B32:** default-off flag lane (above). Also a unit test that `feature_flags({})["leftover_http"] is False`.
- **T25 / B30:** synthetic `results.csv` where mAP peaks at epoch 7 but `best.pt` is epoch 9 → gate reports epoch-9 metrics as the checkpoint result and epoch-7 only under diagnostics; CLI and function defaults identical (`test_train_custom_defaults`); train/val overlap fixture → rejected.
- **T26 / B31:** `pip install` dry-run per lock in CI (`pip install --dry-run -r backend/requirements/api.lock`); `python -c "from backend.app.main import app"` succeeds with only the `api` profile (no torch/ultralytics importable — assert via `importlib.util.find_spec("ultralytics") is None` in that job).

### 11.5 Anti-patterns

- Upgrading the whole dependency stack as a substitute for the logic fixes.
- Raising `BACKEND_MINIMUM` as evidence of anything.
- Marking the GPU lane green because it was skipped.

---

## 12. Shared contracts (build before dependants)

### 12.1 Generation (H02, H03, H05)

```python
class GenerationManifest(StrictModel):
    generationId: str                      # "gen_" + sha256 of the inputs below
    matchId: str
    observationDigest: str                 # raw rows / imported frames digest
    detectionIdentity: str | None
    trackingIdentity: str | None
    calibrationRevision: str | None
    correctionHead: str                    # last applied commandId
    algorithmVersions: dict[str, str]      # analytics, events, shots, report
    files: dict[str, str]                  # relative path -> sha256
    stale: list[str]                       # dependants not rebuilt (must be empty when published by ReviewService)
    orphanedDecisions: list[str]
    publishedAt: str
```

Readers resolve one generation per request; writers publish via the H02 procedure (dir → fsync → pointer → fsync).

### 12.2 Metric record (H03, H05, reports)

Extend `MetricAvailabilityRecord` (`schemas.py` ~L101) to:

```python
metric: str; definitionVersion: str; scope: {"team": "my_team"|"enemy"|None, "player": str|None, "interval": Interval|None}
generationId: str; value: float | None; unit: str; availability: Literal["available","experimental","withheld","unknown"]
status: Literal["observed","estimated","reviewed"]; eligibleSeconds: float | None; requestedSeconds: float | None
exclusions: list[str]; algorithmRevision: str; calibrationRevision: str | None; uncertainty: float | None; reasonCodes: list[str]
```

Rules: unknown ≠ zero; experimental ≠ calibrated; one reviewed identity ≠ whole-match continuity; no legacy numeric fallback when a canonical record exists.

### 12.3 Job and money (H04)

- Logical job: `requestId`, authorisation envelope, `authorisedBudget B`.
- Attempt: own ID, owner lease, input/output revision, lifecycle, charge state.
- Charge kinds: `reserved`, `estimated`, `unsettled`, `settled`, `released`.
- **Invariant (documented and tested):** `Σ settled + Σ outstanding reserved/unsettled ≤ B` for every request at all times. Unknown remote cost keeps its reservation as `unsettled` (consumes capacity) until reconciled. `actualTotal` is `None` while any charge is `unsettled`.
- Cancellation states: `cancel_requested`, `termination_confirmed`, `cleanup_confirmed` are separate timestamps.

### 12.4 Runtime and evidence receipts (H05, H06)

Separate `policy` (requested/declared) from `measured` (observed). Measured receipt fields: source identity, model identity (weights sha256), runtime build, decoded frames, inference calls, batch sizes, recovery calls, tracker updates, exported samples, timestamp policy + `time_base`, timing boundaries, memory/transfer measurements (or `None`), committed output generation. Evidence IDs are `(matchId, generationId, observation/event id)`; reference existence is necessary, not sufficient, for grounding.

---

## 13. Test matrix → files

| T | Findings | Test file(s) | Profile |
|---|---|---|---|
| T01 | B01, B35 | `test_audit_v2_h02_review.py` | code-only |
| T02 | B04 | `test_audit_v2_h02_review.py` (raw-row + tracking variants; one subprocess restart) | code-only + integration |
| T03 | B02 | `test_audit_v2_h02_review.py` (fault injection, child process) | integration |
| T04 | B03, B23 | `test_audit_v2_h02_review.py`, `test_audit_v2_h03_calibration.py` | code-only |
| T05 | B04, B07 | `test_audit_v2_h02_review.py` | code-only |
| T06 | B05, B33 | `test_audit_v2_h03_calibration.py` | code-only |
| T07 | B06 | `test_audit_v2_h03_calibration.py` | code-only |
| T08 | B07 | `test_audit_v2_h03_calibration.py` | code-only |
| T09 | B08, B09 | `test_audit_v2_h05_recompute.py` | code-only |
| T10 | B10 | `test_audit_v2_h04_jobs.py` | code-only |
| T11 | B11 | `test_audit_v2_h04_jobs.py` (two processes, SQL trace) | integration |
| T12 | B12 | `test_audit_v2_h04_jobs.py` | code-only |
| T13 | B13 | `test_audit_v2_h01_provider.py` | code-only |
| T14 | B14 | `test_audit_v2_h01_provider.py` | code-only |
| T15 | B16 | `test_audit_v2_h06_media.py` (rlimit child) | integration |
| T16 | B17, B27 | `test_audit_v2_h06_media.py`, `test_audit_v2_h01_provider.py` | real_media |
| T17 | B18 | `test_audit_v2_h05_recompute.py` | code-only + real_media |
| T18 | B19 | `test_audit_v2_h06_media.py` | code-only + real_media |
| T19 | B20 | `test_audit_v2_h06_media.py` | code-only |
| T20 | B21 | `test_audit_v2_h06_media.py` | code-only |
| T21 | B22 | `test_audit_v2_h03_calibration.py` | code-only |
| T22 | B24, B28 | `test_audit_v2_h03_calibration.py` | code-only |
| T23 | B25 | `test_audit_v2_h05_recompute.py` | code-only |
| T24 | B26, B32 | `test_audit_v2_h01_provider.py`, `test_audit_v2_h07_lanes.py` | code-only |
| T25 | B30 | `test_audit_v2_h07_lanes.py` | code-only |
| T26 | B29–B32 | CI lanes + `test_audit_v2_h07_lanes.py` | integration / manual gpu |
| T27 | B34 | `test_audit_v2_h06_media.py` | code-only |
| T28 | B35 | `test_audit_v2_h02_review.py` | code-only |

B15 has no T-row; test it in `test_audit_v2_h01_provider.py` as described in §5.4.

---

## 14. Handoff report template

Produce `docs/superpowers/audits/<date>-backend-audit-v2-closure.md` with:

```markdown
# Backend Audit v2 closure report

Baseline: d881d1ea…  (HEAD at start: <sha>; delta: none | <files>)
Baseline verify: VERIFY_CODE_ONLY=1 -> <passed>/<skipped>/<failed>
Fixed revision: <sha>
Profiles run: code-only (<counts>), integration (<counts>), real_media (<counts>|not run: reason), gpu (not run: reason)
Stubs active in code-only: <cv2,pandas,ultralytics|none>

| ID | Status | Fix commit(s) | Regression test | Baseline failure (assertion) | Fixed pass (profile) | Remaining limits |
|----|--------|---------------|-----------------|------------------------------|----------------------|------------------|
| B01 | fixed | … | test_audit_v2_h02_review.py::test_t01_… | "workbench search returned 0 hits for 3 accepted events" | code-only | — |
| …  | safely deferred | … | test asserting 410 / ProviderDenied | … | … | route retired; frontend does not call it |
| …  | still open | — | — | — | — | reason |
| …  | not reproduced | — | attempted: … | — | — | reason |

Contracts documented: generation (§12.1) at <path>; metric record at <path>; job/money at <path>; receipts at <path>.
Schema/route migrations: <list with compatibility tests>.
Platform limits retained: network isolation for decoders requires OS sandbox; hosted auth backend pluggable, not deployed; GPU lane manual.
```

Status vocabulary is fixed: `fixed`, `safely deferred/disabled`, `still open`, `not reproduced`. Do not add a status like "partially fixed"; split the item's sub-claims into rows instead.

---

## 15. Quick command reference

```bash
# Baseline / full code-only profile
VERIFY_CODE_ONLY=1 scripts/verify.sh

# One package's regression tests
python3 -m pytest -q backend/tests/test_audit_v2_h02_review.py -x

# Integration and real-media lanes locally
python3 -m pytest -q -m integration backend/tests
python3 -m pytest -q -m real_media backend/tests           # needs ffmpeg/ffprobe on PATH

# Prove a regression fails on the baseline without touching your branch (use a worktree)
git worktree add /tmp/ga-baseline d881d1ea
cp backend/tests/test_audit_v2_h03_calibration.py /tmp/ga-baseline/backend/tests/
cp -r backend/tests/fixtures/raw_rows_two_teams.json /tmp/ga-baseline/backend/tests/fixtures/   # any new fixtures
(cd /tmp/ga-baseline && python3 -m pytest -q backend/tests/test_audit_v2_h03_calibration.py::test_t06_no_transform_fails 2>&1 | tee /tmp/baseline-t06.log)
git worktree remove --force /tmp/ga-baseline

# Find every caller before changing a contract
rg -n "run_analysis\(" backend/
rg -n "job_ledger\.|ledger\." backend/app
rg -n "read_bytes\(\)" backend/app
rg -n "experimental_shot_quality|localisationErrorPx|admitted" backend/app frontend/src
```
