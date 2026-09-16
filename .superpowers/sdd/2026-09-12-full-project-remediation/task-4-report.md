# Task 4 report — R04 local API browser-origin and Host boundary

Base: `ca04021d2869cf42017c90bd3330cab01e348477`.
Status: complete. Focused, affected, contract and complete backend verification passed.

## Change and scope

Added one shared ASGI origin boundary in `backend/app/main.py`. Unsafe HTTP methods and websocket handshakes reject a present foreign, malformed, null, wildcard, or duplicate Origin before routing/body parsing, storage, dispatch, or websocket acceptance. Origin-less clients remain allowed. Exact scheme/host/effective-port comparison allows same-origin requests; the configured frontend tuple allows Vite origins with a different backend Host.

Native Starlette `TrustedHostMiddleware` is outermost and permits only localhost and 127.0.0.1. CORS keeps credentials enabled, replaces wildcard origins with the validated tuple, and allows only frontend GET/POST/PUT/PATCH/DELETE and Content-Type (plus Starlette's standard safelisted headers). Settings resolve once before Storage initialization and are passed unchanged to JobRunner.

`ProcessingSettings.trusted_frontend_origins` defaults exactly to the three required localhost/IPv4/IPv6 Vite origins. Environment parsing splits commas, trims, validates, canonicalizes scheme/hostname/default ports and IPv6 spelling, and deduplicates in order. Empty entries/sets, non-HTTP(S), missing hosts, userinfo, wildcard, null, paths (even /), query/fragment delimiters, control/whitespace inside origins, invalid ports, and malformed host labels fail closed. Direct construction shares validation. Public safe mappings, ResultBundle v2, job progress payloads and Daytona contracts are unchanged.

The supervising task owner explicitly approved two scope extensions after evidence exposed callers using the now-untrusted testserver Host:
1. Mechanical base URL migration in the exact existing API test helpers/call sites below (no shared cross-suite fixture covered them).
2. After the first complete backend run finished, the same one-literal migration in 22 internal ASGI probe scripts. No probe logic or artifact behavior changes.

The supervising task owner also explicitly approved retaining native Starlette's IPv6 backend limitation without an adapter or custom Host parser. README documents that IPv6 frontend Origin is usable against an admitted IPv4/localhost backend, while IPv6 backend Host fails closed.

## Files

Original task scope:
- `backend/app/main.py`
- `backend/app/settings.py`
- `backend/tests/test_api.py`
- `backend/tests/test_api_origins.py` (new)
- `backend/tests/test_settings.py`
- `README.md`
- `.superpowers/sdd/2026-09-12-full-project-remediation/task-4-report.md`

Approved test compatibility extension:
- `backend/tests/test_external_soccertrack_product_route.py`
- `backend/tests/test_run_video_to_analysis_finish_line_route_polish.py`
- `backend/tests/test_run_video_to_analysis_promoted_runtime_post_release_monitoring_chain.py`
- `backend/tests/test_run_video_to_analysis_operator_handoff_route_binding.py`
- `backend/tests/test_run_video_to_analysis_release_readout_route_binding.py`
- `backend/tests/test_gpu_contract.py`
- `backend/tests/test_run_video_to_analysis_real_video_scaleout_execution_chain.py`
- `backend/tests/test_run_video_to_analysis_operator_dashboard_polish.py`
- `backend/tests/test_run_video_to_analysis_bounded_next_sample_execution_chain.py`
- `backend/tests/test_external_soccernet_product_route.py`
- `backend/tests/test_run_video_to_analysis_finish_line_closeout_chain.py`
- `backend/tests/test_dashboard.py`
- `backend/tests/test_run_video_to_analysis_promotion_review_chain.py`
- `backend/tests/test_run_video_to_analysis_detector_evaluation_reentry_chain.py`
- `backend/tests/test_run_video_to_analysis_acceptance_report_route_binding.py`
- `backend/tests/test_run_video_to_analysis_post_release_monitoring_route_binding.py`
- `backend/tests/test_external_soccertrack_analysis_product_route.py`

Approved internal probe compatibility extension (one base_url literal each):
- `backend/scripts/run_video_to_analysis_post_release_monitoring_route_binding.py`
- `backend/scripts/run_video_to_analysis_real_video_scaleout_report_route_binding.py`
- `backend/scripts/run_video_to_analysis_broader_real_video_acceptance_execution.py`
- `backend/scripts/run_video_to_analysis_promoted_runtime_operator_acceptance_trial.py`
- `backend/scripts/run_football_external_benchmark_product_decision_surface_route_implementation.py`
- `backend/scripts/run_football_external_soccertrack_product_route_smoke.py`
- `backend/scripts/run_video_to_analysis_promoted_runtime_post_release_monitoring_route_binding.py`
- `backend/scripts/run_video_to_analysis_bounded_next_sample_report_route_binding.py`
- `backend/scripts/run_video_to_analysis_acceptance_report_route_binding.py`
- `backend/scripts/run_football_external_soccernet_analysis_product_ui_route_implementation.py`
- `backend/scripts/run_product_video_to_analysis_smoke.py`
- `backend/scripts/run_video_to_analysis_detector_evaluation_report_route_binding.py`
- `backend/scripts/run_video_to_analysis_finish_line_user_acceptance_trial.py`
- `backend/scripts/run_video_to_analysis_promotion_review_report_route_binding.py`
- `backend/scripts/run_football_external_benchmark_product_ui_route_implementation.py`
- `backend/scripts/run_football_external_soccertrack_analysis_product_ui_route_implementation.py`
- `backend/scripts/video_to_analysis_promoted_runtime_monitoring_common.py`
- `backend/scripts/run_video_to_analysis_operator_dashboard_polish.py`
- `backend/scripts/run_video_to_analysis_finish_line_route_implementation.py`
- `backend/scripts/run_video_to_analysis_release_readout_route_binding.py`
- `backend/scripts/run_product_video_to_analysis_finish_line_execution.py`
- `backend/scripts/run_video_to_analysis_operator_handoff_route_binding.py`

Additional explicitly approved test compatibility: `backend/tests/test_operational_docs.py` now permits only the three exact documented local development HTTP origins; every other HTTP URL and the existing HTTPS/provider URL checks remain rejected/unchanged.

## RED evidence

Before production edits:

```text
python3 -m pytest -q backend/tests/test_api_origins.py backend/tests/test_settings.py --tb=short
56 failed, 39 passed in 2.90s
```

Observed genuine behavioral failures included:
- `test_foreign_origin_upload_rejected_before_storage`: 202 instead of 403 for all hostile Origin cases.
- `test_foreign_origin_mutation_rejected_without_preflight`: 201 instead of 403.
- `test_websocket_rejects_foreign_origin`: “Foreign origin websocket was accepted”.
- Foreign Host upload cases: 202 instead of 400.
- Mismatched scheme/port mutations: 201 instead of 403.
- CORS advertised unused HEAD/OPTIONS under the old wildcard policy.
- Invalid environment origin policy did not raise SettingsError.
- New direct settings/default tests also exposed the absent field (TypeError/AttributeError), distinct from the behavioral RED assertions above.

Added the explicitly required IPv6 backend Host rejection case before production edits:

```text
python3 -m pytest -q backend/tests/test_api_origins.py -k untrusted_host --tb=short
5 failed, 31 deselected in 0.84s
```

Each Host case, including [::1]:8000, returned 202 instead of 400.

After the first implementation, a focused run produced `19 failed, 95 passed in 5.05s`. These were two test-harness defects exposed by correct rejection: uploads directory was never created; TestClient.websocket_connect used ws://testserver despite the client's HTTP base_url. Tests now accept an absent uploads directory and use explicit loopback websocket URLs. Production admission policy was not weakened.

Parser follow-up RED:

```text
python3 -m pytest -q backend/tests/test_settings.py -k frontend_origins_reject_invalid_environment --tb=short
1 failed, 26 passed, 36 deselected in 0.10s
```

`http://localhost..` did not raise. Changed host-label checking from removing all trailing dots to removing at most one.

Additional duplicate-Origin websocket coverage initially exposed a test-only list-versus-Headers mismatch: `1 failed, 123 passed in 5.31s`. The test now passes httpx.Headers to Starlette's websocket helper.

Compatibility RED after Host enforcement:

```text
python3 -m pytest -q backend/tests/test_dashboard.py backend/tests/test_gpu_contract.py --tb=short
10 failed in 2.10s
```

All ten failures were 400 responses to testserver where 200/202 had been expected.

After the approved test URL migration:

```sh
env PATH=/root/.cache/fotball-analyst/daytona-smoke-0.207.0/bin:$PATH python3 -m pytest -q backend/tests/test_api_origins.py backend/tests/test_api.py backend/tests/test_settings.py backend/tests/test_external_soccertrack_product_route.py backend/tests/test_run_video_to_analysis_finish_line_route_polish.py backend/tests/test_run_video_to_analysis_promoted_runtime_post_release_monitoring_chain.py backend/tests/test_run_video_to_analysis_operator_handoff_route_binding.py backend/tests/test_run_video_to_analysis_release_readout_route_binding.py backend/tests/test_gpu_contract.py backend/tests/test_run_video_to_analysis_real_video_scaleout_execution_chain.py backend/tests/test_run_video_to_analysis_operator_dashboard_polish.py backend/tests/test_run_video_to_analysis_bounded_next_sample_execution_chain.py backend/tests/test_external_soccernet_product_route.py backend/tests/test_run_video_to_analysis_finish_line_closeout_chain.py backend/tests/test_dashboard.py backend/tests/test_run_video_to_analysis_promotion_review_chain.py backend/tests/test_run_video_to_analysis_detector_evaluation_reentry_chain.py backend/tests/test_run_video_to_analysis_acceptance_report_route_binding.py backend/tests/test_run_video_to_analysis_post_release_monitoring_route_binding.py backend/tests/test_external_soccertrack_analysis_product_route.py
```

Output: `29 failed, 164 passed in 10.15s`. Failures traced to internal script probes still using testserver; their Host rejection prevented route artifact publication and cascaded into goalAchieved=False or 404. No request to an external service was made by this test command.

## GREEN evidence

Complete backend RED baseline, before internal probe migration:

```text
env PATH=/root/.cache/fotball-analyst/daytona-smoke-0.207.0/bin:$PATH python3 -m pytest -q backend/tests
48 failed, 3192 passed, 2 skipped in 261.03s (0:04:21)
```

47 failures were rejected internal ASGI probes and their downstream missing-artifact/goal assertions. One was the existing operational-doc test's blanket `http://` prohibition, which conflicted with documenting the required local defaults. The task owner approved a literal allowlist exception for precisely those three origins, without relaxing HTTPS/provider checks.

```text
python3 -m pytest -q backend/tests/test_api_origins.py backend/tests/test_api.py backend/tests/test_settings.py
124 passed in 5.37s

python3 -m pytest -q backend/tests/test_jobs.py backend/tests/test_job_metadata.py backend/tests/test_storage_streaming.py backend/tests/test_remote_contracts.py backend/tests/test_remote_worker.py
368 passed, 1 skipped in 51.18s
```

The skip is the existing opt-in full-match capacity test (`RUN_FULL_MATCH_CAPACITY` was not enabled). Remote worker tests use test doubles and temporary fixtures; no provider call was made.

The focused suite verifies zero save_upload_stream/create_match/start calls on rejected uploads, no match/job/upload state, no foreign bundle mutation, accepted trusted/CLI upload responses, rejection before route validation for POST/PUT/PATCH/DELETE, duplicate Origin rejection, websocket admission/denial, unchanged terminal job progress payload, Host admission, configured-origin replacement, default-port semantics and CORS preflights.

## Local startup check

Executed an inline Python harness that created a fresh retained temporary storage root, reserved a loopback port, and spawned only:
`python3 -m uvicorn backend.app.main:app --host 127.0.0.1 --port <ephemeral>`.

Environment overrides: GUERILLA_STORAGE_ROOT set to that temporary directory; PROCESSING_BACKEND=local; TRUSTED_FRONTEND_ORIGINS unset. The harness waited for GET /api/matches, sent one foreign-Origin POST and one foreign-Host GET, then terminated and waited for only its owned uvicorn process.

```text
LOCAL_STARTUP_OK: GET /api/matches=200 []; foreign POST=403; foreign Host=400
Temporary empty storage retained: /tmp/guerilla-r04-startup-_z393u7c
OWNED_UVICORN_EXITED: -15
```

Harness exit code 0. No upload/job was dispatched. Temporary startup storage was not deleted.

## Self-review and concerns

- Traced upload -> save_upload_stream -> create_match/create_job -> JobRunner.start; a single middleware guard covers every unsafe route and the websocket handler.
- Validated middleware order: TrustedHost, browser origin guard, CORS, then routes. The guard does not receive/parse the body on rejection.
- Uses installed Starlette Host/CORS and standard-library URL/IP parsing; no new dependency or extra middleware file.
- R02 streaming limit/thread behavior and local import lifecycle remain covered by test_api/test_storage_streaming.
- ResultBundle v2/live-progress/remote contracts remain covered by test_remote_contracts/test_remote_worker/job metadata plus websocket progress payload coverage.
- `git diff --check` passed during self-review.
- G-NETWORK remains mandatory: Origin and Host are not authentication; origin-less CLI behavior is intentional. README does not claim public/LAN safety.
- IPv6 backend Hosts remain unsupported by this installed native middleware; tested rejection and documented workaround. No adapter or custom Host parser was added.
- No cloud/provider/Daytona call, real smoke, standalone dependency installation, explicit deletion, or real-data mutation was performed. The supervising task owner explicitly retained the existing full-suite wheel/install tests: they build/install into temporary test virtual environments. No package declaration or lockfile changed. Tests used existing test-owned storage/cleanup and synthetic fixtures.
- Existing untracked `.verification/` is unrelated and will not be committed.


### Final affected-suite verification

After the script migration, the cached failing-test selection:

```text
env PATH=/root/.cache/fotball-analyst/daytona-smoke-0.207.0/bin:$PATH python3 -m pytest -q backend/tests --lf --tb=short
1 failed, 47 passed, 414 deselected in 7.27s
```

The one failure was the docs assertion already collected before its approved edit. All 47 probe-related regressions passed. Final affected/focused selection after that edit (37 files, including every previously failing module):

```sh
env PATH=/root/.cache/fotball-analyst/daytona-smoke-0.207.0/bin:$PATH python3 -m pytest -q backend/tests/test_api_origins.py backend/tests/test_api.py backend/tests/test_settings.py backend/tests/test_operational_docs.py backend/tests/test_external_soccertrack_product_route.py backend/tests/test_run_video_to_analysis_finish_line_route_polish.py backend/tests/test_run_video_to_analysis_promoted_runtime_post_release_monitoring_chain.py backend/tests/test_run_video_to_analysis_operator_handoff_route_binding.py backend/tests/test_run_video_to_analysis_release_readout_route_binding.py backend/tests/test_gpu_contract.py backend/tests/test_run_video_to_analysis_real_video_scaleout_execution_chain.py backend/tests/test_run_video_to_analysis_operator_dashboard_polish.py backend/tests/test_run_video_to_analysis_bounded_next_sample_execution_chain.py backend/tests/test_external_soccernet_product_route.py backend/tests/test_run_video_to_analysis_finish_line_closeout_chain.py backend/tests/test_dashboard.py backend/tests/test_run_video_to_analysis_promotion_review_chain.py backend/tests/test_run_video_to_analysis_detector_evaluation_reentry_chain.py backend/tests/test_run_video_to_analysis_acceptance_report_route_binding.py backend/tests/test_run_video_to_analysis_post_release_monitoring_route_binding.py backend/tests/test_external_soccertrack_analysis_product_route.py backend/tests/test_run_video_to_analysis_broader_real_video_acceptance_execution.py backend/tests/test_run_video_to_analysis_promoted_runtime_operator_acceptance_trial.py backend/tests/test_run_football_external_benchmark_product_decision_surface_route_implementation.py backend/tests/test_run_football_external_soccertrack_product_route_smoke.py backend/tests/test_run_football_external_soccernet_analysis_product_ui_route_implementation.py backend/tests/test_run_product_video_to_analysis_smoke.py backend/tests/test_run_video_to_analysis_finish_line_user_acceptance_trial.py backend/tests/test_run_football_external_benchmark_product_ui_route_implementation.py backend/tests/test_run_football_external_soccertrack_analysis_product_ui_route_implementation.py backend/tests/test_run_product_video_to_analysis_finish_line_execution.py backend/tests/test_run_product_video_to_analysis_normal_storage_smoke.py backend/tests/test_run_product_video_to_analysis_smoke_isolated.py backend/tests/test_run_video_to_analysis_operational_backlog_prioritization.py backend/tests/test_run_video_to_analysis_operational_roadmap_sprint.py backend/tests/test_run_video_to_analysis_steady_state_monitoring_cycle.py backend/tests/test_run_video_to_analysis_storage_retention_and_artifact_hygiene.py
```

Output: `292 passed in 38.27s`.

### Complete backend GREEN

```text
env PATH=/root/.cache/fotball-analyst/daytona-smoke-0.207.0/bin:$PATH python3 -m pytest -q backend/tests
3240 passed, 2 skipped in 263.54s (0:04:23)
```

Exit code 0. This includes the existing isolated wheel/install tests and all previously failing exact tests. No package declarations, lockfiles, provider configuration, ResultBundle schemas, or R02 implementation files changed.

Final staged whitespace check: `git diff --cached --check` exited 0. The 22 script migrations each have exactly one removed/one added base_url line; the test compatibility edits change only client construction/URLs except the separately approved three-origin documentation assertion. The only retained operational limitation is the documented native Starlette IPv6 backend Host rejection; G-NETWORK remains mandatory.
