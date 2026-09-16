# Tests, operations, scripts, research add-on, docs, and artifact audit

Audit date: 2026-09-10. Worktree: /root/WorkSpace/fotball-analyst/.worktrees/batch-1-data-safety. Source snapshot: 0504370fab85f7b380879cf83712a48814e83b14.

Snapshot boundary: a separate implementation task began changing backend/tests/test_remote_contracts.py while this report was being finalized. Per the parent auditor, that in-progress work is outside this review. File hashes, inventory statistics, findings, and test results here describe the audited 0504370f snapshot, not that subsequent implementation diff. This reviewer made no tracked-file changes.

## Outcome and scope

This slice is **not ready for an unqualified whole-project safety/readiness sign-off**. Important issues remain in destructive cleanup, legacy review servers, and research-add-on execution. The recent annotation/upload/reset/tracker fixes are not being rejected here; these findings identify other paths outside their bounded scope.

No Critical-severity remote compromise is asserted: the review servers bind to loopback by default, and cleanup is an operator workflow. Several Important findings nevertheless permit loss or disclosure of local data. No production code, tracked artifacts, releases, provider state, or dependencies were changed during this audit. Only this report was authored.

The Ponytail audit criteria were applied to simplification opportunities, separately from correctness/security/performance findings. Security review guidance informed the legacy vanilla-JavaScript review UI checks; there is no skill reference specifically for Python's http.server, so those server findings are based on the actual handlers and focused reproductions.

The assigned slice contains 4,695 of 4,798 tracked files: 143,965,118 bytes; 2,839 UTF-8-readable files with 1,227,112 newline-delimited lines; 1,856 binary files. All assigned files were read in full by the static pass. All 618 assigned Python files were parsed as ASTs, all 136 JSON files parsed, all 1,854 JPEGs were verified with Pillow, all 1,842 YOLO label files were checked for five finite normalized numeric fields and class 0, and both tracked PT archives were inspected as ZIP metadata without unpickling.

Coverage is not a claim of line-by-line human-equivalent semantic review of 1.2 million lines. The complete manifest below distinguishes static/text inspection, binary metadata inspection, and delegated files. Manual semantic review concentrated on mutation, network/subprocess, packaging/release, review UI, and test-assertion boundaries; no file is silently excluded.

Assigned areas include all backend/scripts, backend/tests, research-addon, backend/review_ui, backend non-Python metadata/configuration, root scripts/manifests, CI, .factory, tracked storage artifacts, docs, and repository memorybank documents. Backend runtime Python and frontend are separately assigned to other auditors; they are explicitly listed as delegated in the manifest. Root tests/ and compose files are absent from the tracked inventory.

## Important correctness, security, and readiness findings

### I01 — Destructive cleanup accepts the candidate root and protected descendants

Category: correctness / data loss / confinement. Location: backend/scripts/run_video_to_analysis_storage_cleanup_bounded_execution.py:140, :145, :151, :164.

The final runner resolves each approved relativePath and checks only containment, exact equality with the latest top-level version directory, and existence. It accepts "." (the candidate root itself), descendants of the latest directory, unversioned files, absolute paths that happen to lie inside the root, and rows whose approvedAction says "keep". It does not independently establish that a target is an approved old-version generated-truth directory. It then uses pathname-based rmtree/unlink after validation, leaving an ancestor-swap race.

Read-only reproduction against the tracked candidate root: both "." and "v7_2_bounded_retrain_v1/train_run/weights/best.pt" were accepted with approvedAction="keep", no path errors, and no latest-version errors. No deletion was invoked. The first target can erase the entire candidate tree; the second defeats the advertised latest-version preservation rule.

Exact fix: validate a nonempty relative top-level versioned directory name, forbid root/absolute/parent components, require the exact approved action, reject every protected latest-version subtree, and bind deletion to an opened no-follow owning directory. Revalidate target identity at deletion. Reuse the existing FD-pinned containment pattern, but do not call reset_output because this operation must not recreate deleted targets.

Tests: backend/tests/test_run_video_to_analysis_storage_cleanup_bounded_execution.py covers only successful old-version deletion, absent approval, and exact latest-directory deletion. Add root/absolute/parent/nested-latest/unversioned/action-mismatch/symlink and ancestor-swap cases with sentinels proving no mutation.

### I02 — Legacy review HTTP servers disclose arbitrary local files

Category: security. Locations: backend/scripts/serve_football_external_soccernet_detector_miss_review_ui.py:288 and :290; backend/scripts/serve_v7_1_positive_diversity_review_ui.py:321 and :323; backend/scripts/serve_promoted_v6_manual_review_ui.py:293.

The first two handlers pass the path query parameter directly to file serving. All three generic static fallbacks join ui_root with a request path without confinement. "/source-image?path=/absolute/file" reads any accessible file; a raw "/../../pyproject.toml" reaches outside backend/review_ui. No image membership or extension check prevents it.

Focused handler reproductions intercepted the serving boundary and demonstrated that an unrelated repository manifest was selected; no secret file was opened. Loopback binding limits network exposure but is not a file authorization boundary, and --host permits wider exposure. Imported-metadata XSS described in I07 compounds the risk.

Exact fix: serve images by opaque review-item ID resolved through the approved manifest, not arbitrary client paths; serve only known static files or enforce physical containment beneath ui_root; reject symlinks/outside paths. Keep loopback as the default and require a separate authenticated design before public binding. Add real HTTP traversal/absolute-path/symlink tests and verify that the sentinel outside the allowed root is never returned.

### I03 — Atomic review writes still lose concurrent successful decisions

Category: correctness / data loss. Locations: backend/scripts/serve_promoted_v6_manual_review_ui.py:207 and :224; backend/scripts/serve_v7_1_positive_diversity_review_ui.py:219 and :253; backend/scripts/serve_football_external_soccernet_detector_miss_review_ui.py:200 and :230.

Each handler performs an unlocked load-modify-replace of the entire overlay, while the server uses ThreadingHTTPServer. Two concurrent edits to different items can read the same old overlay and overwrite each other; both return success. Atomic replacement prevents partial JSON, not lost updates.

A deterministic two-thread barrier reproduction with in-memory read/write boundaries returned two successful updates, but each published payload contained only one accepted decision and the other item's old state. This is not hypothetical multi-process locking: the current server explicitly handles requests concurrently.

Exact fix: serialize the entire read/validate/modify/publish transaction with a lock shared by requests for the same overlay. Reuse one proven atomic JSON writer with clear FD ownership, file fsync and parent-directory fsync. The three copied _write_json_atomic implementations currently omit durability fsync and can leak the original descriptor if fdopen fails.

Tests: add concurrent edits to different records, read/write/replace/fdopen failure cleanup, and non-mutation of corrupt/schema-invalid overlays. Existing 22 review-server tests pass without exercising these boundaries.

### I04 — Research-add-on path isolation is bypassed at execution

Category: security / correctness. Locations: research-addon/research_addon/judge.py:125, :161, :217; research-addon/research_addon/path_guards.py:15, :24, :69, :85; research-addon/research_addon/corpus.py:16 and :88.

The main cli.py entry validates a storage root, but public run_judge and the separately executable judge module do not. A direct run_judge call passed storage_root="backend" through to the delegated proof boundary in the reproduction. The low-level wrapper also appends extra_args after its own --storage-root, permitting a later duplicate flag to override the validated value. The default /tmp root bypasses resolution, so an existing symlink there is not checked.

The guards additionally hard-code one developer checkout. They reject this worktree's legitimate research-addon path and even reject the exact configured addon root because the prefixes include a trailing slash. is_safe_path accepts unresolved "/tmp/.../../../etc". CorpusManifest's default file is actually at the repository root, not inside the addon, contrary to its comment and isolation contract.

Exact fix: enforce resolution in the execution/write boundary, including default paths; derive addon-owned roots from configuration/package context rather than one absolute checkout; use Path containment on resolved paths rather than raw string prefixes; reject/limit overriding extra_args; put the default manifest beneath a validated addon-owned root. Decide explicitly whether general /tmp is allowed and make help/tests match that policy.

Tests: exercise both module entry points and the public API, default-root symlinks, traversal, worktree/moved checkouts, exact allowed roots, protected duplicate arguments, and default manifest writes. Current path tests cover only the hard-coded main checkout and do not test the execution boundary.

### I05 — Installed research-add-on advertises an executable track that cannot resolve its backend

Category: correctness / packaging closure. Locations: research-addon/research_addon/judge.py:20; research-addon/research_addon/cli.py:129; research-addon/pyproject.toml:10; backend/tests/test_documented_startup.py:385.

The judge derives REPO_ROOT by walking three parents above its own file and constructs a backend/scripts filename there. In an installed wheel this is a Python library directory, not a repository or the installed backend package. The sidecar package has no backend dependency or configurable repository/input root. Its default proof-video location is likewise checkout-relative.

Verified in the wheel-install test's actual sidecar virtual environment: the delegated target resolved beneath sidecar-venv/lib/python3.12/backend/scripts and did not exist. The install test checks import and a static "tracks list" output, not execution, while the output says supported-coverage is executable.

Exact fix: either declare this an explicitly checkout-bound developer tool and require a validated --repo-root/manifest, or invoke the installed backend as a module with an explicit dependency and explicit corpus paths. Do not infer a checkout from site-packages. Add an installed-outside-checkout delegation test that actually reaches the backend boundary.

### I06 — Legacy review UIs discard edits made while a save is pending

Category: correctness / user data loss. Locations: backend/review_ui/promoted_v6_manual_review/index.html:382 and :403; backend/review_ui/v7_1_positive_diversity_review/index.html:203 and :223; backend/review_ui/football_external_soccernet_detector_miss_review/index.html:197 and :214.

Save captures the current notes/bounding box, but inputs, next/previous, filters and keyboard shortcuts remain active while fetch is pending. Successful completion reloads state and re-renders fields, overwriting any new edits made after the request started or edits on an item navigated to during the request. Concurrent clicks can submit conflicting decisions. Rejected fetch/JSON promises have no catch in these event paths; only initial loadState has an error handler.

Exact fix: maintain a pending state for each save transaction, lock all editing/navigation/shortcut paths during it, catch rejected requests, and preserve drafts on failure. Alternatively use per-item drafts with request-version guards if continuing edits is required. Add delayed-save/navigation and network-rejection browser/DOM tests. The new React coaching-editor tests do not cover these independent HTML tools.

### I07 — Persisted review metadata is interpolated into HTML

Category: security; JS-XSS-001. Locations: backend/review_ui/promoted_v6_manual_review/index.html:320; backend/review_ui/v7_1_positive_diversity_review/index.html:133; backend/review_ui/football_external_soccernet_detector_miss_review/index.html:135.

Metadata from JSON/API records is inserted with innerHTML without escaping, including source IDs, event labels, gameTime and other string fields. A crafted imported/review artifact can place active markup in the review origin. There is no sanitization at these sinks; the corresponding handlers do not emit a CSP. Exploitability requires attacker-influenced artifacts or equivalent local data influence, not merely a remote unauthenticated upload to the main API.

Exact fix: create dt/dd nodes and assign textContent. No sanitizer dependency is needed because this is plain text metadata. Add a regression containing angle brackets and an image-event payload, checking literal text and no created active elements. Keep I02's file-serving fix independent: neither fix substitutes for the other.

### I08 — Research bundle date can escape the archive output namespace

Category: correctness / destructive-path confinement. Location: backend/scripts/build_parallel_research_bundle.py:548, :550, :558; CLI at :609.

bundle_date is an arbitrary CLI string interpolated into the directory and ZIP filename. Separators and parent components can escape archive_root after the prefixed first component. If the resulting directory exists, it is recursively removed; otherwise recursive mkdir/copy and ZIP publication can still write outside the intended archive. Collecting the input file plan before the reset does not establish output containment.

Exact fix: parse bundle_date with date.fromisoformat and render its canonical isoformat value, reject separators/parent components, and use an owned-root no-follow output reset/publication boundary. Add malicious-date and symlink tests proving existing outside sentinels remain unchanged. Do not generalize this into an output-framework rewrite.

### I09 — The release GPU smoke is not a real football-worker acceptance test

Category: readiness / production-path coverage, already acknowledged in docs/status/current.md:27. Locations: backend/scripts/run_daytona_gpu_smoke.py:35, :47, :318; backend/tests/test_run_daytona_gpu_smoke.py:150.

The bounded smoke imports dependencies, runs a one-element CUDA tensor operation, and executes a separate python -c fixture that writes job/match/status JSON. It does not invoke backend.app.gpu_worker with a sealed football input or validate real tracking/artifact import. It can pass when the actual worker's path, inference, result-size or split/reassembly behavior is broken. The recently added real-worker-to-adapter local integration test closes an important path-shape gap but still mocks inference/runtime preparation.

Exact next step: retain this as a cheap infrastructure smoke, but add a separately authorized, bounded product acceptance run through API upload, the actual sealed worker, validated result import, and confirmed cleanup using an approved short clip. Keep source/manifest/evidence binding intact. Do not reinterpret historical smoke evidence as acceptance of newer runtime commits. No cloud run was attempted by this audit.

## Minor findings and test-quality gaps

### M01 — Active repository memory documents contradict the retired-provider policy

Category: maintainability / operational correctness. Locations: memorybank/projectbrief.md:13 and :33; memorybank/architecture/repo-map.md:11; memorybank/operations/runpod-proof-workflow.md:1; memorybank/operations/verification-workflow.md:39; memorybank/README.md:19.

These still describe RunPod as an optional current execution path and refer to the removed runpod_handler directory. Current README/status/runbooks correctly name Daytona, and retired recipe entry points fail closed. The defect is contradictory active instructions, not historical mentions in archived plans or chronology.

Exact fix: archive or explicitly mark these operation pages as historical and replace the active entry points with links to docs/status/current.md and docs/runbooks/daytona-gpu-execution.md. Extend backend/tests/test_operational_docs.py:83 beyond its current narrow file list. The separate unattended-loop tests still demand the obsolete April checklist and RunPod instructions; coordinate their retirement with the backend-runtime owner rather than deleting historical source records.

### M02 — Several sidecar tests cannot fail when the described behavior is broken

Category: test quality. Locations: research-addon/tests/test_corpus_manifest.py:139; research-addon/tests/test_judge_contract.py:92, :133, :188.

The corpus "required output fields" test constructs a local literal list and asserts properties of that same list, without reading production code. The judge "required fields verification" test checks only the declaration. The "script exit status" tests fail on a missing video or argparse invalid choice, before any delegated process runs. Together with the installed-package list-only test, these inflate confidence in an untested execution contract.

Exact fix: replace tautological assertions with controlled delegated success/malformed-output/nonzero-exit tests against run_judge and both installed CLI paths. Test wrong field types as well as missing keys. Counts are useful collection guards, not behavioral acceptance evidence.

### M03 — Corpus fingerprint is stale after supported public mutation

Category: correctness / contract clarity. Locations: research-addon/research_addon/corpus.py:62, :79, :92, :103.

entries is a shallow copied public list of mutable dicts; iteration and indexing expose those dicts. The fingerprint is cached once and write emits that old fingerprint after mutation. reload replaces the object's state before raising that it changed. A read-only in-memory reproduction changed video_id and showed the stored fingerprint no longer matched the entries.

Exact fix: choose one small contract: either immutable/copy-on-access entries with transactional reload, or recompute the fingerprint from current entries at write/read boundaries and stop calling the object frozen. Validate the top-level object and entry shapes. Preserve the ordering property already covered by tests.

### M04 — Review tests use shared global /tmp files

Category: test isolation / maintainability. Location: backend/tests/test_serve_football_external_soccernet_detector_miss_review_ui.py:25.

_item writes predictable /tmp/soccernet-full-N.jpg and crop-N.jpg files outside tmp_path and leaves them behind. Parallel runs or unrelated local files can collide; the test does not need global paths.

Exact fix: pass tmp_path into the fixture helper and place images beneath that owned directory. Assert URL generation against that path instead of a machine-global literal.

### M05 — The factory “typecheck” is syntax-only and its install is much heavier than its tests

Category: verification clarity / performance. Location: .factory/services.yaml:2 and :4.

The install command includes all backend/requirements.txt layers, including the full CUDA/ML stack, for a CLI-only sidecar workflow. The named typecheck only calls ast.parse, while the test command omits research-addon/tests entirely.

Exact fix: align install with root runtime + dev requirements + editable sidecar, add the sidecar tests, and rename the syntax gate to syntax or run an actual type checker if there is a justified type-checking goal. No new dependency is required for the minimal correction.

## Ponytail simplification opportunities, ranked separately

These are optional cuts, not additional correctness blockers. Savings are estimates scoped as stated; do not sum overlapping numbers.

1. **[delete] Exclude tests from the production wheel.** pyproject.toml:23 excludes storage but not backend.tests. The inspected current-test wheel contains 298 backend/tests files totaling 3,377,244 uncompressed bytes (about 3.22 MiB), alongside 309 script files totaling 5,296,555 bytes. No backend runtime or script imports backend.tests were found. Exclude backend.tests* while preserving source tests and operational scripts. Expected installed-size saving: 3.22 MiB and about 80k packaged test lines; repository source-line saving: zero; dependencies removed: zero. Do not exclude every script indiscriminately because release and research entry points use them.

2. **[delete] Remove unreachable tails after fail-closed retired-provider guards.** For example backend/scripts/run_promoted_touchline_detector_candidate_source_robustness_validation.py:1028 and backend/scripts/run_touchline_detector_candidate_model_data_quality_fix.py:1263. AST inspection found 38 functions whose first effective statement unconditionally calls require_retired_runpod_disabled and whose remaining tails total 3,868 lines. Keep compatibility signatures, exported analysis helpers, and the explicit retirement exception; cut only unreachable tails after caller/test inspection. The 14 files mentioning the guard total 13,482 lines, but that is NOT a justified whole-file deletion estimate.

3. **[shrink] Import existing shared JSON/time/root helpers instead of copying them.** Examples: backend/scripts/run_football_external_benchmark_harness_smoke.py:30, :34, :38, :43. Exact AST clone groups contain 97 identical _load_json functions, 180 _utc_now_iso functions, 101 same-shape _write_json functions, and 108 _candidate_root functions. Those four groups alone contain 1,544 redundant function lines, already replaceable by helpers in football_external_real_eval_chain_common.py with local aliases where compatibility matters. Total exact-function duplicate excess across scripts is 4,977 lines in 151 groups, an upper bound rather than a safe bulk-delete target. Do not replace the many workflow contracts with a new generic framework.

4. **[shrink] Deduplicate historical artifact payloads only after preserving provenance and consumers.** All assigned files contain 509 exact-byte duplicate groups, 3,197 redundant copies, and 49,819,917 redundant working-tree bytes (47.51 MiB). Within storage, repeated JPEGs account for 43,785,800 bytes and repeated JSON for 5,935,229 bytes. Examples: v7_2_crop_probe_precision_guardrail_audit_v1/confidence_sweep_audit.json duplicates the full_pipeline_non_promotion_eval_v1 file (4,870,476 bytes); candidate_crop_coverage_audit.json duplicates reviewed_positive_pipeline_audit.json in the latter directory (901,529 bytes). Prefer one canonical payload with manifest references or move historical snapshots to an existing artifact store after an approved retention decision. This is not permission to delete data. Git already deduplicates identical blobs: the estimate is checkout/working-tree saving, NOT equivalent Git-history saving.

5. **[delete] Replace the duplicate research report with a pointer.** docs/deep-research-report.md and docs/foot-soccer-deepresearch.md are byte-identical: 44,883 bytes / 694 lines each. Keep one canonical document and update references or use a short pointer. Estimated saving: about 44 KiB / 690 net lines, no dependencies.

6. **[native] Avoid the unnecessary factory GPU install.** .factory/services.yaml:2 can use the existing lightweight runtime/dev split. backend/requirements-ml.txt declares 30 pinned packages; 27 package names are ML-only relative to the runtime/dev direct declarations. Removing that layer from this sidecar-only install avoids those 27 explicit ML-only declarations in this workflow, not from the product. Exact transitive disk savings depend on wheel/platform caches and were not measured; do not claim a fabricated GB value.

7. **[shrink] Share the three review servers' small safety primitives after fixing I02/I03.** Their file-serving, JSON response, overlay transaction and status UI code substantially repeats. Extract only proven identical safe primitives or remove a retired UI if its consumers are actually gone. Do not add a review-framework abstraction. Line savings not estimated because the three review schemas and resolver contracts differ.

No external dependency was proven globally removable by this slice. The recent lap/scipy packaging closure should remain until a separate equivalence and installed-tracker audit establishes a replacement. Historical models, recovery .nul manifests, archived checksums, and current source-bound release evidence are retention-sensitive, not disposable clutter.

## Verification and evidence

- Full assigned-file byte read, Python AST parse, JSON parse, duplicate hashing, declaration/call scans, doc contradiction scans, and test-assertion shape scan completed. No Python/JSON parse errors.
- All 1,854 tracked JPEGs verified; all 1,842 YOLO labels met basic numeric/schema checks. This does not prove labeling correctness or dataset independence. Repeated images are expected across snapshots and were counted for deduplication, not automatically classified as train/validation leakage.
- Both 5,709,306-byte tracked PT archives have 605 ZIP entries and 5,628,242 uncompressed bytes; each contains data.pkl. Neither was unpickled or executed. No model-origin/security guarantee is inferred from ZIP validity.
- Focused cleanup + Daytona-smoke + sidecar tests: 83 passed in 1.50 seconds.
- Three legacy review-server test modules: 22 passed in 1.35 seconds.
- Bash syntax check of scripts/verify.sh and .factory/init.sh passed; both pyproject TOML files parsed.
- Credential-free run_daytona_gpu_smoke --dry-run passed with pinned SDK policy 0.207.0 and the configured immutable image/GPU policy.
- Read-only/mocked reproductions confirmed I01, I02, I03, I04, I05 and M03 without deleting artifacts, reading secrets, invoking inference, or contacting a provider.
- CI inspection confirms read-only GitHub permissions and no-cloud verification flags. Worker Dockerfile, exact requirements lock checks, context whitelist implications, PYTHONPATH and YOLO_AUTOINSTALL settings were reviewed. No container image was built or deployed in this audit.
- Test AST survey: 300 Python files containing tests, 2,068 test functions, 9,581 assertions, 620 mock-related calls, 373 string-membership assertions. These are inventory statistics, not a grading heuristic; mocks and contract-text assertions are appropriate when paired with boundary tests.
- The only discovered explicit pytest.skip is the absent raw recovery freeze archive case in backend/tests/test_run_recovery_inventory.py:718. It is an intentional environment-dependent preservation test, not a reason to delete the archive contract.
- Full backend/frontend suites were not rerun by this slice; the parent owns integrated verification. Browser interaction, real video inference, real provider acceptance, vulnerable-package/CVE scanning, external links, artifact restoration, and semantic image annotation review were not performed. Docs were read for internal contradictions, stale provider guidance, and architecture claims, not externally fact-checked research content.
- Existing source-bound v7.3 release metadata targets source 43c9c2e3, not this runtime snapshot. Current docs explicitly require a fresh source/manifest/evidence chain for these newer changes; preserve that distinction.

## Complete tracked-file coverage manifest

Each directory heading plus basename is an exact repository-relative path. Every tracked path appears once, including delegated exclusions. Columns are basename, bytes, UTF-8 line count (or "-" for binary), SHA-256 prefix, and inspection mode. Modes: PY = fully read and AST-inspected; JSON = fully read and parsed; DOC = fully read and contradiction/staleness scanned; TEXT = fully read and configuration/static inspected; JPEG = fully read, hashed, dimensions/header verified; PT = fully read, hashed, ZIP metadata inspected without unpickling; DELEGATED-RUNTIME / DELEGATED-FRONTEND = semantic review assigned to the corresponding other auditor (listed for accounting, not claimed reviewed here). Focused semantic review and reproductions are identified above.

### .

```text
basename | bytes | lines | sha256-prefix | inspection
.dockerignore | 373 | 24 | 092060704745 | TEXT
.gitignore | 2191 | 56 | 9cd7a0371977 | TEXT
README.md | 1624 | 42 | 9dcb8b1c1af9 | DOC
SESSION-HANDOFF.md | 104 | 3 | 43685cab5db8 | DOC
gbt5.5report_1_24april.md | 6064 | 97 | 263133e1971f | DOC
lap.py | 1874 | 60 | ff9a5785bb0d | DELEGATED-RUNTIME
pyproject.toml | 750 | 36 | b75405cbda63 | TEXT
```

### .factory

```text
basename | bytes | lines | sha256-prefix | inspection
init.sh | 336 | 15 | f3e5847e6911 | TEXT
services.yaml | 2167 | 59 | 5bab62dbe9f5 | TEXT
```

### .factory/library

```text
basename | bytes | lines | sha256-prefix | inspection
architecture.md | 4290 | 88 | 148e92219c11 | DOC
environment.md | 1800 | 35 | 938a69b899de | DOC
user-testing.md | 2109 | 53 | 95de103c7c4d | DOC
```

### .factory/skills/research-addon-worker

```text
basename | bytes | lines | sha256-prefix | inspection
SKILL.md | 6549 | 120 | b8087dff685d | DOC
```

### .github/workflows

```text
basename | bytes | lines | sha256-prefix | inspection
ci.yml | 1413 | 58 | 3299d44b2763 | TEXT
```

### backend

```text
basename | bytes | lines | sha256-prefix | inspection
__init__.py | 46 | 1 | 7ade59bfd0f8 | DELEGATED-RUNTIME
pitch_detector.py | 15827 | 450 | 884d698fe217 | DELEGATED-RUNTIME
requirements-dev.txt | 195 | 8 | a381f5b0b7dc | TEXT
requirements-ml.txt | 788 | 31 | 6e1af0c07cc4 | TEXT
requirements-runtime.txt | 268 | 12 | 0ac6e1ea24fc | TEXT
requirements.txt | 146 | 4 | 7057509eb1ac | TEXT
run_guerilla.py | 388337 | 8619 | af5fd97e6333 | DELEGATED-RUNTIME
train_custom.py | 4245 | 126 | b468755e0c5f | DELEGATED-RUNTIME
```

### backend/app

```text
basename | bytes | lines | sha256-prefix | inspection
__init__.py | 61 | 1 | f082b29dbe53 | DELEGATED-RUNTIME
analytics.py | 59297 | 1415 | e820beda276c | DELEGATED-RUNTIME
daytona.py | 56614 | 1363 | 0058d4df35b5 | DELEGATED-RUNTIME
daytona_worker_image.py | 6133 | 149 | 154f2f514791 | DELEGATED-RUNTIME
edge_share_repair.py | 39630 | 1030 | 7966b881aa2d | DELEGATED-RUNTIME
edge_share_repair_profiles.py | 57922 | 1032 | aa70e1b659ca | DELEGATED-RUNTIME
export_flatteners.py | 2308 | 83 | ee4960b809d2 | DELEGATED-RUNTIME
gpu_worker.py | 55603 | 1465 | 11d3be45e18e | DELEGATED-RUNTIME
homography_utils.py | 2655 | 78 | c55280420708 | DELEGATED-RUNTIME
jobs.py | 3334 | 101 | 79464bffd05a | DELEGATED-RUNTIME
llm.py | 15639 | 404 | 11afcfca8f6f | DELEGATED-RUNTIME
main.py | 68975 | 1352 | 5dc2d11e09cd | DELEGATED-RUNTIME
match_bundle.py | 3357 | 78 | eed560b0be1c | DELEGATED-RUNTIME
processor.py | 43180 | 1071 | 4ce71f3c26f7 | DELEGATED-RUNTIME
proof_runtime.py | 18401 | 427 | 8aa914f6a289 | DELEGATED-RUNTIME
proof_summary.py | 16727 | 230 | 5c73b8ad42b7 | DELEGATED-RUNTIME
release_manifest.py | 17937 | 450 | 66302c7a248d | DELEGATED-RUNTIME
remote_contracts.py | 51492 | 1114 | fed3a1fdd103 | DELEGATED-RUNTIME
remote_worker.py | 20443 | 574 | cd356e4a2100 | DELEGATED-RUNTIME
report_export.py | 13875 | 303 | 533d3d181e03 | DELEGATED-RUNTIME
run_benchmarks.py | 107391 | 2219 | 195f3f9b3ead | DELEGATED-RUNTIME
runtime_options.py | 30320 | 723 | a2d65ccb84b6 | DELEGATED-RUNTIME
schemas.py | 12200 | 434 | 85ed999f0f7e | DELEGATED-RUNTIME
semantic_search.py | 14275 | 415 | 2dd2f562205c | DELEGATED-RUNTIME
settings.py | 3410 | 88 | 74394540e229 | DELEGATED-RUNTIME
storage.py | 33591 | 878 | 82dcb5bf34d2 | DELEGATED-RUNTIME
team_classification.py | 3641 | 96 | 45d381a9920f | DELEGATED-RUNTIME
training_quality_gate.py | 17152 | 396 | 780a64a09c8a | DELEGATED-RUNTIME
trust_crops.py | 6052 | 158 | d537765547a2 | DELEGATED-RUNTIME
unattended_roadmap_loop.py | 5376 | 148 | 9f08358ed442 | DELEGATED-RUNTIME
video_pipeline.py | 2458 | 62 | 890a833d1d85 | DELEGATED-RUNTIME
worker.py | 1041 | 32 | f3e492bc6235 | DELEGATED-RUNTIME
```

### backend/benchmark_suites

```text
basename | bytes | lines | sha256-prefix | inspection
frozen_viable_baseline_slice_suite.json | 5187 | 151 | d4a2e6c46ec4 | JSON
frozen_viable_baseline_source_manifest.json | 2132 | 62 | 99af103cc77a | JSON
```

### backend/daytona_worker

```text
basename | bytes | lines | sha256-prefix | inspection
Dockerfile | 657 | 15 | d787d612252a | TEXT
requirements.lock | 104091 | 63 | 2fdb83df878b | TEXT
requirements.txt | 937 | 37 | d12d96be5d52 | TEXT
```

### backend/release

```text
basename | bytes | lines | sha256-prefix | inspection
__init__.py | 53 | 1 | 992b02b158dd | DELEGATED-RUNTIME
daytona-v7.3.json | 462 | 1 | 4102f0f59a1b | JSON
daytona_execution_schema.json | 2294 | 64 | 906406125e7e | JSON
daytona_policy.py | 10252 | 280 | f40bae6c0357 | DELEGATED-RUNTIME
evidence.py | 21404 | 445 | a360267042d6 | DELEGATED-RUNTIME
preflight.py | 58642 | 1446 | 05a0a5340bdb | DELEGATED-RUNTIME
v7.3.json | 3537 | 79 | 62cd12f4db31 | JSON
verification_schema.json | 11747 | 166 | 5c201159f8e4 | JSON
```

### backend/release/verification

```text
basename | bytes | lines | sha256-prefix | inspection
v7.3-pre-cloud.json | 3309 | 1 | 9ad98d9733f4 | JSON
v7.3.json | 5332 | 1 | 087d27d55ba3 | JSON
```

### backend/review_ui/football_external_soccernet_detector_miss_review

```text
basename | bytes | lines | sha256-prefix | inspection
index.html | 15226 | 239 | 605eac1b00fe | TEXT
```

### backend/review_ui/promoted_v6_manual_review

```text
basename | bytes | lines | sha256-prefix | inspection
index.html | 14776 | 485 | d7eb0b290fcc | TEXT
```

### backend/review_ui/v7_1_positive_diversity_review

```text
basename | bytes | lines | sha256-prefix | inspection
index.html | 17397 | 274 | eed08a772f8c | TEXT
```

### backend/scripts

```text
basename | bytes | lines | sha256-prefix | inspection
build_parallel_research_bundle.py | 30622 | 624 | 9bf68fedd746 | PY
compare_ball_pipeline_trace.py | 4280 | 126 | ce29ffaff5c0 | PY
compare_local_remote_proof.py | 5598 | 136 | 79bef2c51e5d | PY
football_external_real_eval_chain_common.py | 6395 | 184 | 85d734c74343 | PY
promote_selected_cluster_for_proof.py | 1395 | 48 | 88cd069c33a9 | PY
run_benchmark_suite.py | 14765 | 358 | d70feaa33ca3 | PY
run_canonical_match_bundle_export.py | 8654 | 211 | bca6702a5f49 | PY
run_clip_manifest_expansion.py | 16986 | 425 | 1e1d335e1d0c | PY
run_daytona_gpu_smoke.py | 19294 | 404 | 51dfd39c87bf | PY
run_detector_breadth_batch.py | 34937 | 746 | d44eca375f73 | PY
run_football_external_benchmark_bounded_execution_smoke.py | 17439 | 387 | ba6dba226393 | PY
run_football_external_benchmark_bounded_real_execution.py | 10792 | 226 | 28cbb04f3e7e | PY
run_football_external_benchmark_dataset_governance_plan.py | 8209 | 184 | be60093fac21 | PY
run_football_external_benchmark_execution_approval.py | 15447 | 329 | 2fa03c51d6c6 | PY
run_football_external_benchmark_harness_prep.py | 19158 | 428 | 282d34ba9ce2 | PY
run_football_external_benchmark_harness_smoke.py | 19097 | 407 | 0180ecf0cc50 | PY
run_football_external_benchmark_lane_closeout.py | 20541 | 424 | c1bf2bc1335a | PY
run_football_external_benchmark_operationalization_plan.py | 24250 | 493 | 2252e59bd768 | PY
run_football_external_benchmark_product_decision_surface.py | 26102 | 522 | eee50206767d | PY
run_football_external_benchmark_product_decision_surface_route_implementation.py | 17927 | 366 | 777567b58ee5 | PY
run_football_external_benchmark_product_ui_binding.py | 18259 | 395 | 55c9affc42a1 | PY
run_football_external_benchmark_product_ui_route_implementation.py | 16440 | 348 | 92510a7d3cfc | PY
run_football_external_benchmark_real_evaluation_approval.py | 7324 | 165 | 33e7658484cc | PY
run_football_external_benchmark_real_evaluation_design.py | 22325 | 484 | 687aba8b2bb3 | PY
run_football_external_benchmark_real_report_and_product_binding.py | 7750 | 180 | b154f07c2edd | PY
run_football_external_benchmark_real_source_path_consolidation.py | 4814 | 118 | d57650217a19 | PY
run_football_external_benchmark_report_smoke.py | 14099 | 325 | 820c39383437 | PY
run_football_external_dataset_access_review.py | 17767 | 416 | e52ccf63bc8f | PY
run_football_external_safe_adapter_fixture_implementation.py | 16782 | 380 | aa706245c086 | PY
run_football_external_safe_source_adapter_smoke_test.py | 21285 | 467 | f67e86870325 | PY
run_football_external_safe_source_controlled_sample_fetch.py | 13823 | 326 | 96fabb23c9d1 | PY
run_football_external_safe_source_sample_download_approval.py | 13155 | 291 | 217f28d256f8 | PY
run_football_external_safe_source_sample_ingestion_plan.py | 16723 | 372 | 6a83f6982440 | PY
run_football_external_soccernet_analysis_product_api_smoke.py | 16681 | 358 | 20bdfd063053 | PY
run_football_external_soccernet_analysis_product_lane_closeout.py | 14077 | 302 | 3a2a4df5c746 | PY
run_football_external_soccernet_analysis_product_ui_binding.py | 18797 | 400 | a7467f0ce5d9 | PY
run_football_external_soccernet_analysis_product_ui_route_implementation.py | 16101 | 344 | 733b3355da72 | PY
run_football_external_soccernet_api_listing_probe.py | 16053 | 376 | a68d9ebcb39c | PY
run_football_external_soccernet_api_metadata_probe.py | 17875 | 420 | 426ff905e234 | PY
run_football_external_soccernet_benchmark_adapter_contract_prep.py | 17594 | 391 | 0fccaa7af7f8 | PY
run_football_external_soccernet_bounded_analysis_execution.py | 19224 | 418 | 15bf921a705c | PY
run_football_external_soccernet_bounded_analysis_execution_approval.py | 15183 | 332 | cc45a09ccb6a | PY
run_football_external_soccernet_bounded_analysis_lane_closeout.py | 14193 | 322 | 2694a2be781d | PY
run_football_external_soccernet_bounded_analysis_report_smoke.py | 13750 | 302 | e9c08147131b | PY
run_football_external_soccernet_bounded_product_validation_execution.py | 16827 | 381 | c2b3e6dc10dc | PY
run_football_external_soccernet_bounded_product_validation_execution_approval.py | 13703 | 302 | 77bdfbd8285b | PY
run_football_external_soccernet_bounded_product_validation_plan.py | 16217 | 384 | 5599958257a4 | PY
run_football_external_soccernet_bounded_product_validation_report_binding.py | 13812 | 298 | 847166c073d7 | PY
run_football_external_soccernet_broader_validation_choice.py | 7251 | 172 | 5982b941d4ae | PY
run_football_external_soccernet_controlled_label_metadata_probe.py | 14859 | 335 | 603ed217105f | PY
run_football_external_soccernet_controlled_label_sample_fetch.py | 17325 | 399 | aed05c70f210 | PY
run_football_external_soccernet_controlled_label_sample_fetch_approval.py | 13522 | 307 | bc2228e890fe | PY
run_football_external_soccernet_controlled_video_sample_fetch.py | 17661 | 384 | c0e73041cc2f | PY
run_football_external_soccernet_detector_miss_capture_and_label_queue.py | 25443 | 598 | 8bab2ff7a896 | PY
run_football_external_soccernet_detector_miss_manual_review_resolution.py | 17529 | 423 | 5f2be34e64a4 | PY
run_football_external_soccernet_event_adapter_fixture_materialization.py | 16015 | 361 | ff640e572d3e | PY
run_football_external_soccernet_event_adapter_smoke_test.py | 14364 | 318 | 49c35ea9eeee | PY
run_football_external_soccernet_event_benchmark_smoke.py | 13977 | 311 | 23790f46138e | PY
run_football_external_soccernet_event_lane_closeout.py | 17949 | 391 | b87421e3258f | PY
run_football_external_soccernet_event_report_contract_prep.py | 15632 | 350 | 8115da20b3dd | PY
run_football_external_soccernet_event_report_product_integration.py | 15470 | 336 | 168ab7017a1d | PY
run_football_external_soccernet_event_report_smoke.py | 13645 | 315 | 8fb9ad472601 | PY
run_football_external_soccernet_full_analysis_execution.py | 19817 | 434 | 3936056c217c | PY
run_football_external_soccernet_full_analysis_execution_approval.py | 16044 | 357 | 9b035569a489 | PY
run_football_external_soccernet_full_analysis_lane_closeout.py | 13647 | 314 | 397dced28253 | PY
run_football_external_soccernet_full_analysis_product_integration.py | 17726 | 370 | 3ed70026e753 | PY
run_football_external_soccernet_full_analysis_report_smoke.py | 13739 | 300 | ef1e11fbab59 | PY
run_football_external_soccernet_label_fetch_contract_repair.py | 12292 | 280 | 23f0707caa2d | PY
run_football_external_soccernet_label_schema_ingestion_probe.py | 18483 | 423 | 6857f8502a10 | PY
run_football_external_soccernet_nda_api_access_approval.py | 11919 | 274 | 364dd03dd060 | PY
run_football_external_soccernet_real_sample_product_pipeline_training_decision.py | 17826 | 375 | 3993e0d4ff6b | PY
run_football_external_soccernet_split_archive_access_review.py | 19540 | 424 | 847c30337397 | PY
run_football_external_soccernet_split_archive_range_index_probe.py | 26279 | 603 | 583fc06e60b9 | PY
run_football_external_soccernet_split_archive_size_probe.py | 21670 | 474 | c901a5f7d90c | PY
run_football_external_soccernet_video_analysis_dry_run.py | 16245 | 371 | 2aac2f9f0539 | PY
run_football_external_soccernet_video_analysis_dry_run_approval.py | 15474 | 350 | f45a6270100f | PY
run_football_external_soccernet_video_analysis_dry_run_product_bridge_smoke.py | 13714 | 308 | f06450592a95 | PY
run_football_external_soccernet_video_frame_probe.py | 13864 | 321 | 7bbb2407bece | PY
run_football_external_soccernet_video_member_extract.py | 25598 | 570 | f462951d579a | PY
run_football_external_soccernet_video_member_extract_approval.py | 12032 | 267 | 806f0e89ae2f | PY
run_football_external_soccernet_video_product_path_smoke.py | 13018 | 302 | 05d95788ae92 | PY
run_football_external_soccernet_video_sample_download_approval.py | 13649 | 295 | d69157db0cb0 | PY
run_football_external_soccernet_video_sample_probe.py | 14629 | 336 | 305e610881e9 | PY
run_football_external_soccernet_video_to_analysis_bridge_prep.py | 13225 | 297 | eb704b0574c7 | PY
run_football_external_soccernet_zip_label_member_extract.py | 27963 | 614 | e78dd2cbdebe | PY
run_football_external_soccernet_zip_label_member_extract_approval.py | 14923 | 320 | 70717824eebe | PY
run_football_external_soccertrack_adapter_smoke_test.py | 22885 | 503 | 813d63b3bb13 | PY
run_football_external_soccertrack_analysis_product_lane_closeout.py | 14912 | 312 | 40f0bb11e328 | PY
run_football_external_soccertrack_analysis_product_ui_binding.py | 19347 | 405 | 11459f5cfc7a | PY
run_football_external_soccertrack_analysis_product_ui_route_implementation.py | 17135 | 356 | da42dbf6ce9f | PY
run_football_external_soccertrack_analysis_report_smoke.py | 19033 | 408 | 0269e3cc84f6 | PY
run_football_external_soccertrack_authenticated_fixture_access_approval.py | 13349 | 295 | 6db9ef285347 | PY
run_football_external_soccertrack_controlled_sample_fetch.py | 21459 | 458 | ddfc7c77da01 | PY
run_football_external_soccertrack_fixture_source_access_review.py | 16074 | 350 | 2e7f03a909a6 | PY
run_football_external_soccertrack_google_drive_bounded_fixture_fetch.py | 20917 | 481 | b4b87c8d28a4 | PY
run_football_external_soccertrack_google_drive_fixture_access_probe.py | 20389 | 478 | 7219eab7d46c | PY
run_football_external_soccertrack_lane_closeout.py | 19972 | 419 | ca67640998c2 | PY
run_football_external_soccertrack_match_bundle_bridge_smoke.py | 17646 | 400 | 10bb42ea22d6 | PY
run_football_external_soccertrack_metadata_adapter_smoke.py | 12830 | 298 | f656799f58b9 | PY
run_football_external_soccertrack_product_route_smoke.py | 15628 | 334 | 5331bf0e9510 | PY
run_football_external_soccertrack_sample_fixture_materialization.py | 18401 | 417 | 023055b8397c | PY
run_football_external_soccertrack_sample_fixture_materialization_approval.py | 15251 | 331 | 73003690eafb | PY
run_football_external_soccertrack_sample_ingestion_contract_prep.py | 17911 | 382 | fb75da6664b3 | PY
run_football_external_soccertrack_sample_schema_probe.py | 16021 | 361 | c6e72d98fb7f | PY
run_football_external_soccertrack_schema_doc_fetch.py | 15810 | 363 | f3af61822725 | PY
run_football_external_soccertrack_schema_doc_fetch_approval.py | 14251 | 330 | e4296c13b742 | PY
run_football_external_soccertrack_schema_doc_parse.py | 22446 | 500 | 5d63acb2ced8 | PY
run_local_app_path_proof.py | 6581 | 161 | 1b0ea9bd6e35 | PY
run_pod_proof_cycle.py | 2300 | 56 | 3211eed81187 | PY
run_product_video_to_analysis_finish_line_execution.py | 12896 | 266 | c2521b523236 | PY
run_product_video_to_analysis_normal_storage_smoke.py | 9401 | 201 | df413dcb39df | PY
run_product_video_to_analysis_smoke.py | 11446 | 264 | 71f4109137fe | PY
run_product_video_to_analysis_smoke_isolated.py | 10632 | 245 | 66d10ceb7457 | PY
run_promoted_touchline_detector_candidate_retention_delta_analysis.py | 22582 | 489 | 38490dd6baf8 | PY
run_promoted_touchline_detector_candidate_source_robustness_validation.py | 68318 | 1514 | bcd908e95a71 | PY
run_promoted_v6_accepted_retention_guardrail_audit.py | 18137 | 408 | 0e4315fbd35a | PY
run_promoted_v6_baseline_denominator_review_refresh.py | 15932 | 360 | 8d3506613900 | PY
run_promoted_v6_candidate_proposal_generation_fix.py | 26751 | 594 | 8d301222e397 | PY
run_promoted_v6_failing_source_review_refresh.py | 25124 | 590 | 6f912c3f93fc | PY
run_promoted_v6_global_accepted_gap_audit.py | 20331 | 457 | b2a972c14fa8 | PY
run_promoted_v6_global_reachable_acceptance_probe.py | 14613 | 344 | d45349da0042 | PY
run_promoted_v6_gold_truth_bootstrap.py | 31542 | 693 | b4d4f83882e2 | PY
run_promoted_v6_gold_truth_seed_refuted_refresh.py | 18866 | 438 | 3912a4363ab8 | PY
run_promoted_v6_manual_review_denominator_expansion.py | 19463 | 468 | 416fcd260ba2 | PY
run_promoted_v6_manual_review_denominator_resolution.py | 14190 | 349 | 14b1a844b4f2 | PY
run_promoted_v6_manual_review_expansion.py | 27477 | 643 | d60db9968398 | PY
run_promoted_v6_manual_review_expansion_resolution.py | 18123 | 437 | 5b0940cae45b | PY
run_promoted_v6_manual_review_followthrough_batch.py | 23048 | 541 | 0c332f8c613c | PY
run_promoted_v6_manual_review_resolution_batch.py | 17963 | 434 | 91cc9dc4cfa9 | PY
run_promoted_v6_proof_diagnostic_instrumentation_refresh.py | 15917 | 363 | 6a7fc3c49b0a | PY
run_promoted_v6_proof_runtime_frame_diagnostics.py | 14617 | 337 | 1a0ae0f20ed3 | PY
run_promoted_v6_proposal_selection_followthrough_fix.py | 27047 | 580 | f607ffc1b631 | PY
run_promoted_v6_refuted_denominator_filter_plan.py | 7282 | 176 | f69c84d60fef | PY
run_promoted_v6_residual_segment_selection_microfix.py | 15504 | 364 | 7dacdd000796 | PY
run_promoted_v6_reviewed_followthrough_selection_fix.py | 19352 | 453 | 43a755bcbbb7 | PY
run_promoted_v6_reviewed_positive_acceptance_fix.py | 20752 | 465 | 9ec8b36f5e88 | PY
run_promoted_v6_reviewed_positive_anchor_seed.py | 9441 | 230 | 03739aa8837b | PY
run_promoted_v6_reviewed_positive_crop_geometry_scale_fix.py | 15988 | 355 | bdec6c654c71 | PY
run_promoted_v6_reviewed_positive_crop_reinference_audit.py | 19325 | 479 | 70eb24144299 | PY
run_promoted_v6_reviewed_positive_micro_validation.py | 28612 | 648 | 9f8cecf2cd41 | PY
run_promoted_v6_reviewed_positive_proposal_generation_fix.py | 13122 | 297 | 3e176a47af38 | PY
run_promoted_v6_reviewed_positive_residual_proposal_generation_fix.py | 25546 | 551 | cc4849c9d862 | PY
run_promoted_v6_reviewed_positive_selection_followthrough_fix.py | 35316 | 744 | fe123b77a08e | PY
run_promoted_v6_source_manifest_and_gold_truth_refresh.py | 21555 | 526 | 1c3d1cf60382 | PY
run_promoted_v6_support_viability_truth_fix.py | 18491 | 450 | 410c8cc6371d | PY
run_promoted_v6_touchline_detector_candidate_v7_training.py | 35143 | 872 | ac159e065af2 | PY
run_promoted_v6_touchline_detector_candidate_v7_training_data_refresh.py | 15200 | 351 | b9e729274189 | PY
run_promoted_v6_touchline_detector_candidate_v7_training_prep.py | 18186 | 429 | bdaa81f26bb0 | PY
run_promoted_v6_v7_training_data_lane.py | 8246 | 186 | 303d171b6ad3 | PY
run_promoted_v7_2_source_robustness_validation.py | 14642 | 334 | a609ec23c548 | PY
run_recovery_inventory.py | 32882 | 791 | 43de7d36d418 | PY
run_recovery_worktree_salvage.py | 65836 | 1678 | 038ae7dfa4de | PY
run_remote_video_benchmark.py | 5047 | 112 | 10f4b49d60cf | PY
run_source_robustness_batch.py | 218806 | 4467 | 0cad0398eb3a | PY
run_touchline_detector_candidate_evaluation.py | 52551 | 1142 | 5c7214273c2e | PY
run_touchline_detector_candidate_failure_analysis.py | 69173 | 1417 | ec24859fabb9 | PY
run_touchline_detector_candidate_model_data_quality_fix.py | 75144 | 1708 | 3d311804208a | PY
run_touchline_detector_candidate_promotion_validation.py | 14744 | 309 | 359f89338ded | PY
run_touchline_detector_candidate_proposal_signal_generation_fix.py | 58224 | 1353 | 677e4d7703d4 | PY
run_touchline_detector_candidate_training.py | 32519 | 742 | c9809513667f | PY
run_touchline_detector_candidate_v5_proposal_signal_generation_fix.py | 76308 | 1743 | 0cb8f51dc9f3 | PY
run_touchline_detector_candidate_v7_evaluation_failure_analysis.py | 18103 | 387 | d22da65a6669 | PY
run_touchline_review_densification_batch.py | 49995 | 1170 | e75b770004de | PY
run_touchline_training_data_curation_batch.py | 30504 | 716 | d52dc0885d39 | PY
run_touchline_validation_gate_remediation.py | 48137 | 1028 | c22a208592c5 | PY
run_trimmed_ball_recovery_matrix.py | 6355 | 164 | 88649d73343c | PY
run_trimmed_clip_benchmark.py | 2294 | 67 | 59354c98c60f | PY
run_v7_1_bounded_retrain.py | 32155 | 681 | db12e84d14fa | PY
run_v7_1_crop_manifest_consistency_refresh.py | 21489 | 505 | 2e1577af4a20 | PY
run_v7_1_crop_probe_precision_guardrail_audit.py | 28744 | 568 | 666969b2a4a7 | PY
run_v7_1_export_label_overlay_audit.py | 29115 | 658 | 79bd6ec5b8e5 | PY
run_v7_1_full_pipeline_non_promotion_eval.py | 24913 | 478 | d7080be81731 | PY
run_v7_1_positive_candidate_mining_expansion.py | 20760 | 462 | 9470c7eaff6a | PY
run_v7_1_positive_candidate_mining_expansion_v3_pitch_filtered.py | 11146 | 221 | 7ce10180858c | PY
run_v7_1_positive_diversity_manual_review_expansion.py | 20053 | 392 | 76d016daeff1 | PY
run_v7_1_positive_diversity_manual_review_resolution.py | 21240 | 426 | 318c16adc6e5 | PY
run_v7_1_positive_diversity_refresh.py | 18646 | 372 | 985b33d99b43 | PY
run_v7_1_positive_diversity_review_evidence_package.py | 9062 | 227 | 2fe83b1c6db7 | PY
run_v7_1_tiny_overfit_retry_with_verified_config.py | 19342 | 407 | fecb78bf9c91 | PY
run_v7_1_tiny_overfit_sanity_train.py | 33470 | 776 | a77b15623e1c | PY
run_v7_1_training_config_or_export_debug.py | 17508 | 404 | 2bfe54a3a6da | PY
run_v7_1_training_manifest_prep.py | 15180 | 368 | 8dd1de8d03c5 | PY
run_v7_2_bounded_retrain.py | 26502 | 547 | 93f91956b14d | PY
run_v7_2_crop_probe_precision_guardrail_audit.py | 17040 | 342 | 72ad1de72d15 | PY
run_v7_2_default_path_edge_share_reduction.py | 26254 | 591 | 0c7ba60250b0 | PY
run_v7_2_default_path_inboard_ball_recovery.py | 26129 | 568 | c082fac78679 | PY
run_v7_2_export_label_overlay_audit.py | 30621 | 690 | c3634286b1c4 | PY
run_v7_2_full_pipeline_non_promotion_eval.py | 23988 | 442 | 0c57dfe5d387 | PY
run_v7_2_post_runtime_default_source_robustness_validation.py | 18719 | 412 | f33d6112c04b | PY
run_v7_2_promotion_readiness_validation.py | 29396 | 620 | fa89bf34c15a | PY
run_v7_2_runtime_default_change_validation.py | 21734 | 476 | a26789663cfb | PY
run_v7_2_runtime_default_rollout_closeout.py | 20101 | 467 | 41e5723bcdea | PY
run_v7_2_runtime_registry_product_path_binding.py | 10536 | 243 | 232ca3eeee34 | PY
run_v7_2_source_robustness_default_blocker_analysis.py | 14582 | 343 | 26af884dddbc | PY
run_v7_2_source_robustness_route_contract_fix.py | 11330 | 271 | a10b07e6dd83 | PY
run_v7_2_training_manifest_prep.py | 15512 | 364 | 7e48fc4e7950 | PY
run_v7_3_bounded_retrain.py | 28531 | 585 | ed029d73d8ee | PY
run_v7_3_crop_probe_precision_guardrail_audit.py | 18882 | 378 | e8cbc68597d0 | PY
run_v7_3_export_label_overlay_audit.py | 28599 | 596 | 3307d9a5d86b | PY
run_v7_3_full_pipeline_non_promotion_eval.py | 18294 | 317 | 30cf42940364 | PY
run_v7_3_post_runtime_default_source_robustness_validation.py | 18335 | 407 | b4555d3f555f | PY
run_v7_3_promotion_readiness_validation.py | 31143 | 658 | 75c19a35654f | PY
run_v7_3_runtime_default_change_validation.py | 21299 | 461 | a08a91bd9806 | PY
run_v7_3_runtime_default_rollout_closeout.py | 19442 | 456 | d7c02ca2e916 | PY
run_v7_3_training_manifest_prep_from_soccernet_real_misses.py | 25854 | 552 | 18424d8df008 | PY
run_v7_4_training_decision_from_real_misses.py | 7582 | 171 | 3ff24e9cdd4f | PY
run_v7_negative_crop_conversion_plan.py | 11847 | 290 | 2998cd1cbba1 | PY
run_v7_negative_semantics_review.py | 17032 | 394 | fa5b8ed2558f | PY
run_v7_probe_assist_integration_audit.py | 15857 | 365 | ead7bada8bc4 | PY
run_v7_probe_precision_guardrail_audit.py | 29597 | 710 | 929f5076aac3 | PY
run_v7_probe_threshold_contract_fix.py | 14882 | 377 | 09d60655bb78 | PY
run_v7_probe_threshold_preprocessing_fix.py | 15464 | 391 | ba064e352707 | PY
run_v7_training_data_quality_refresh.py | 20852 | 489 | 83bab30400ba | PY
run_video_to_analysis_acceptance_report_product_backlog.py | 9945 | 222 | a46f7fa030fb | PY
run_video_to_analysis_acceptance_report_route_binding.py | 13717 | 315 | 992d58bcba28 | PY
run_video_to_analysis_bounded_next_sample_closeout.py | 3809 | 89 | 0ef63e103cf6 | PY
run_video_to_analysis_bounded_next_sample_execution.py | 4901 | 114 | 21673490fc7c | PY
run_video_to_analysis_bounded_next_sample_execution_approval.py | 6379 | 138 | cb15f275982b | PY
run_video_to_analysis_bounded_next_sample_report_route_binding.py | 7355 | 161 | 9cc6cf2909ba | PY
run_video_to_analysis_broader_real_video_acceptance_approval.py | 7418 | 171 | 26544136763e | PY
run_video_to_analysis_broader_real_video_acceptance_closeout.py | 8962 | 209 | 994091995251 | PY
run_video_to_analysis_broader_real_video_acceptance_execution.py | 7795 | 170 | 44c9f134562b | PY
run_video_to_analysis_broader_real_video_acceptance_suite_prep.py | 6888 | 163 | 5e22887ffd1e | PY
run_video_to_analysis_current_release_acceptance_decision_surface.py | 25486 | 544 | 47e02c20d2b4 | PY
run_video_to_analysis_detector_evaluation_bounded_existing_artifact_execution.py | 9736 | 213 | 69c5482197a3 | PY
run_video_to_analysis_detector_evaluation_chain_common.py | 3163 | 102 | ec2c29ba2485 | PY
run_video_to_analysis_detector_evaluation_lane_closeout.py | 6451 | 162 | 9d8ec67f94a1 | PY
run_video_to_analysis_detector_evaluation_reentry_approval.py | 6428 | 156 | 5156b6c9c185 | PY
run_video_to_analysis_detector_evaluation_reentry_plan.py | 6851 | 167 | 0da4d4f52e99 | PY
run_video_to_analysis_detector_evaluation_report_binding.py | 8057 | 192 | abf260c51622 | PY
run_video_to_analysis_detector_evaluation_report_route_binding.py | 8924 | 199 | 48645ab3070d | PY
run_video_to_analysis_finish_line_closeout.py | 6547 | 134 | 661fff9d9906 | PY
run_video_to_analysis_finish_line_completion_summary.py | 7871 | 179 | baa9e335abb2 | PY
run_video_to_analysis_finish_line_execution_approval.py | 9120 | 192 | 2447c93091fc | PY
run_video_to_analysis_finish_line_integration_plan.py | 7503 | 159 | 1324bff8059c | PY
run_video_to_analysis_finish_line_normal_storage_closeout.py | 9032 | 195 | 0cfb127c8dce | PY
run_video_to_analysis_finish_line_normal_storage_execution_approval.py | 8620 | 184 | 482d8ca3ed4a | PY
run_video_to_analysis_finish_line_operational_readiness.py | 8377 | 189 | 6b3782518446 | PY
run_video_to_analysis_finish_line_product_acceptance_closeout.py | 8587 | 187 | 8802e6fc19f6 | PY
run_video_to_analysis_finish_line_product_binding.py | 6433 | 143 | a9783759b950 | PY
run_video_to_analysis_finish_line_product_execution_approval.py | 9882 | 202 | cb3cf26ccd35 | PY
run_video_to_analysis_finish_line_product_execution_plan.py | 6243 | 134 | 3e13e2cb9fb1 | PY
run_video_to_analysis_finish_line_route_implementation.py | 6935 | 146 | 1b706e9be0d5 | PY
run_video_to_analysis_finish_line_route_polish.py | 8754 | 205 | f21eb792ceb3 | PY
run_video_to_analysis_finish_line_user_acceptance_trial.py | 9369 | 207 | ec0275e2f896 | PY
run_video_to_analysis_growth_lane_closeout_readout.py | 14865 | 336 | 42aaa5b36da4 | PY
run_video_to_analysis_growth_lane_decision_snapshot.py | 4072 | 94 | 5eb9afc39e0d | PY
run_video_to_analysis_manual_operator_release_decision.py | 12237 | 283 | 62bc6c473703 | PY
run_video_to_analysis_next_roadmap_direction_snapshot.py | 10335 | 224 | 6fb39cd8592f | PY
run_video_to_analysis_next_sample_selection_snapshot.py | 6563 | 134 | 874ae75741b4 | PY
run_video_to_analysis_next_strategic_lane_selection.py | 18624 | 408 | c19e8389cea2 | PY
run_video_to_analysis_operational_backlog_prioritization.py | 11197 | 238 | 11bba1cdd16c | PY
run_video_to_analysis_operational_sprint_closeout.py | 4074 | 98 | d8dee50d2dac | PY
run_video_to_analysis_operator_dashboard_polish.py | 12536 | 283 | c689d9ec9bfc | PY
run_video_to_analysis_operator_handoff_pack.py | 11656 | 268 | 4df14ba1f6a7 | PY
run_video_to_analysis_operator_handoff_route_binding.py | 11493 | 262 | d3687f36bf63 | PY
run_video_to_analysis_post_release_monitoring_closeout.py | 7396 | 175 | 454c012cae6a | PY
run_video_to_analysis_post_release_monitoring_plan.py | 8999 | 207 | c9c31dfc5c29 | PY
run_video_to_analysis_post_release_monitoring_route_binding.py | 11374 | 254 | 964fb53c0c19 | PY
run_video_to_analysis_product_hardening_backlog.py | 7394 | 183 | 262edcc85eba | PY
run_video_to_analysis_product_lane_closeout.py | 7498 | 186 | f2cb1c505af6 | PY
run_video_to_analysis_promoted_runtime_operational_completion_summary.py | 5779 | 143 | 506cb844b798 | PY
run_video_to_analysis_promoted_runtime_operator_acceptance_trial.py | 13464 | 292 | e230e900f27b | PY
run_video_to_analysis_promoted_runtime_post_release_monitoring_execution.py | 7095 | 169 | 9c2876fe6ffc | PY
run_video_to_analysis_promoted_runtime_post_release_monitoring_plan.py | 6183 | 146 | c74b9a1f47ba | PY
run_video_to_analysis_promoted_runtime_post_release_monitoring_route_binding.py | 9722 | 220 | 88a168546578 | PY
run_video_to_analysis_promoted_runtime_release_closeout.py | 7300 | 166 | a1862f9cfe8f | PY
run_video_to_analysis_promotion_review_closeout.py | 5650 | 143 | 210b07c85e4c | PY
run_video_to_analysis_promotion_review_design.py | 7919 | 185 | 9124422250f2 | PY
run_video_to_analysis_promotion_review_execution.py | 8318 | 192 | e7cb3754785f | PY
run_video_to_analysis_promotion_review_report_binding.py | 7301 | 182 | d78d2d5601a4 | PY
run_video_to_analysis_promotion_review_report_route_binding.py | 8019 | 184 | 227dcbe817e2 | PY
run_video_to_analysis_real_video_scaleout_bounded_execution.py | 4842 | 104 | 42698d62489e | PY
run_video_to_analysis_real_video_scaleout_execution_approval.py | 7154 | 154 | 58ee0846c516 | PY
run_video_to_analysis_real_video_scaleout_lane_closeout.py | 3514 | 71 | b34d41193eea | PY
run_video_to_analysis_real_video_scaleout_plan.py | 4716 | 110 | 1c524a6e5aa3 | PY
run_video_to_analysis_real_video_scaleout_plan_refresh.py | 11691 | 228 | 3526a1dcedc1 | PY
run_video_to_analysis_real_video_scaleout_report_route_binding.py | 7345 | 153 | b0225e95e7eb | PY
run_video_to_analysis_real_video_scaleout_source_sampling_expansion.py | 10002 | 247 | 92a2ea1674f7 | PY
run_video_to_analysis_release_acceptance_archive.py | 10237 | 237 | eea0ad822e23 | PY
run_video_to_analysis_release_candidate_closeout.py | 12012 | 259 | 20e37c3e66fd | PY
run_video_to_analysis_release_completion_summary.py | 6170 | 150 | 6cb453709cc4 | PY
run_video_to_analysis_release_readout_pack.py | 17754 | 407 | bf8c12b6ba0c | PY
run_video_to_analysis_release_readout_route_binding.py | 12820 | 301 | f18f8d0e28cf | PY
run_video_to_analysis_roadmap_state_reconciliation.py | 16791 | 328 | 99afa783b35f | PY
run_video_to_analysis_scaleout_or_backlog_decision_snapshot.py | 4302 | 95 | 3d42255fdec8 | PY
run_video_to_analysis_source_and_artifact_cleanup_map.py | 5049 | 123 | 8babb278b4c4 | PY
run_video_to_analysis_source_pool_replenishment_approval.py | 14974 | 361 | 093cb18df367 | PY
run_video_to_analysis_source_pool_replenishment_plan.py | 27768 | 639 | 34f05c6c9056 | PY
run_video_to_analysis_steady_state_monitoring_cycle.py | 11316 | 254 | 8e95a8957c63 | PY
run_video_to_analysis_steady_state_monitoring_recurring_schedule.py | 4149 | 95 | d55a4239b625 | PY
run_video_to_analysis_storage_cleanup_approval.py | 18170 | 427 | 1835e44a9501 | PY
run_video_to_analysis_storage_cleanup_bounded_execution.py | 14552 | 361 | f6ffe954ef99 | PY
run_video_to_analysis_storage_cleanup_closeout.py | 8153 | 186 | 027703069498 | PY
run_video_to_analysis_storage_cleanup_dry_run_execution.py | 10955 | 253 | 2833d486cf49 | PY
run_video_to_analysis_storage_cleanup_execution_approval.py | 11126 | 254 | 94e8b05c19c1 | PY
run_video_to_analysis_storage_retention_and_artifact_hygiene.py | 11435 | 283 | 13bb99578f41 | PY
run_video_to_analysis_upload_to_analysis_walkthrough.py | 6789 | 179 | 27b131adffe2 | PY
run_video_to_analysis_user_facing_release_readout.py | 14047 | 328 | 7c61e084be5a | PY
run_video_to_analysis_v7_3_release_packaging_and_worktree_triage.py | 13867 | 331 | f6aa1f67059b | PY
runpod_session.py | 1277 | 45 | d5ddd7ac9a44 | PY
serve_football_external_soccernet_detector_miss_review_ui.py | 14929 | 370 | f71a45d7bff1 | PY
serve_promoted_v6_manual_review_ui.py | 14763 | 383 | 4ab179ac8bfb | PY
serve_v7_1_positive_diversity_review_ui.py | 16809 | 405 | 84cfd4a4199c | PY
update_unattended_roadmap_loop_status.py | 2784 | 75 | 7848431ff67e | PY
video_to_analysis_operational_sprint_common.py | 2246 | 81 | 2f2b99820af8 | PY
video_to_analysis_promoted_runtime_monitoring_common.py | 5991 | 122 | 1e0d54945e20 | PY
write_release_manifest.py | 4132 | 120 | 0725dca9738c | PY
write_verification_evidence.py | 20796 | 439 | d4de2520d59f | PY
```

### backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite

```text
basename | bytes | lines | sha256-prefix | inspection
detector_candidate_promotion.json | 3058 | 48 | 6b8b723211f6 | JSON
v7_2_detector_candidate_promotion_readiness.json | 7559 | 153 | c06836224a27 | JSON
```

### backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/promoted_v7_2_source_robustness_validation_v1

```text
basename | bytes | lines | sha256-prefix | inspection
batch_outcome_analysis.json | 2601 | 62 | 2d38a807b37a | JSON
batch_outcome_analysis.md | 525 | 12 | abb18bf35456 | DOC
controlled_registry_audit.json | 271 | 9 | 0a502933d7a5 | JSON
decision_matrix.json | 2693 | 63 | cce4f8ab443a | JSON
failsafe_attempt_plan.json | 1334 | 35 | 4aaee770c5b9 | JSON
promoted_v7_2_source_robustness_validation_summary.json | 1260 | 28 | f2b47b81415d | JSON
runtime_default_blocker_audit.json | 366 | 10 | 9cffb9dbe665 | JSON
source_robustness_gate_audit.json | 23447 | 467 | 0c8f367435f7 | JSON
```

### backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/v7_2_source_robustness_default_blocker_analysis_v1

```text
basename | bytes | lines | sha256-prefix | inspection
batch_outcome_analysis.json | 2051 | 47 | 9c9b512d337f | JSON
batch_outcome_analysis.md | 501 | 12 | fda7f4bb4cee | DOC
decision_matrix.json | 2582 | 62 | f38660115c66 | JSON
default_blocker_analysis_summary.json | 1311 | 29 | c9b478736f66 | JSON
default_mutation_evidence_audit.json | 261 | 9 | 4c0860b97363 | JSON
failsafe_attempt_plan.json | 1170 | 33 | 443f48d8f5d4 | JSON
route_mismatch_audit.json | 318 | 7 | e33a63c1c0a3 | JSON
source_robustness_delta_audit.json | 24679 | 488 | 2f4a936b8408 | JSON
```

### backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/v7_2_source_robustness_route_contract_fix_v1

```text
basename | bytes | lines | sha256-prefix | inspection
batch_outcome_analysis.json | 2028 | 45 | 3237ffebe682 | JSON
batch_outcome_analysis.md | 405 | 11 | 6d969df8e6cd | DOC
decision_matrix.json | 2490 | 60 | a133e3d7fe0f | JSON
default_gate_after_route_fix_audit.json | 332 | 8 | ee209e0f2401 | JSON
failsafe_attempt_plan.json | 1230 | 33 | 26840f737938 | JSON
route_contract_audit.json | 375 | 8 | 85ae7d80baa4 | JSON
route_contract_fix_summary.json | 1163 | 27 | ba83144e48ae | JSON
```

### backend/storage/runtime

```text
basename | bytes | lines | sha256-prefix | inspection
promoted_touchline_detector_candidate.json | 5376 | 63 | 78be8add9a8a | JSON
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v1

```text
basename | bytes | lines | sha256-prefix | inspection
batch_outcome_analysis.json | 1048 | 25 | 8c23d3610dc3 | JSON
batch_outcome_analysis.md | 185 | 3 | fc88fa439c8b | DOC
corrected_label_overlay.json | 398480 | 9142 | fbaa2fb6b348 | JSON
correction_review_index.html | 106182 | 346 | 84a5a6bd68b1 | TEXT
decision_matrix.json | 1101 | 26 | 04ed4061f97a | JSON
new_mined_candidate_manifest.json | 182436 | 5285 | 8564a4e4f917 | JSON
salvage_candidate_summary.json | 156859 | 3269 | 9dbf1062efe7 | JSON
v7_1_positive_candidate_mining_expansion_summary.json | 987 | 23 | 55c95c4d6c92 | JSON
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v2

```text
basename | bytes | lines | sha256-prefix | inspection
batch_outcome_analysis.json | 1099 | 26 | 21e3e33869d2 | JSON
batch_outcome_analysis.md | 185 | 3 | fc88fa439c8b | DOC
corrected_label_overlay.json | 328824 | 6015 | a861e9e27d3a | JSON
correction_review_index.html | 179218 | 244 | 97fc12a47505 | TEXT
decision_matrix.json | 1152 | 27 | d2404e45fb2b | JSON
new_mined_candidate_manifest.json | 162247 | 4085 | 5695a481571d | JSON
v7_1_positive_candidate_mining_expansion_summary.json | 1036 | 24 | fa436ad7824e | JSON
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v3_pitch_filtered_v1

```text
basename | bytes | lines | sha256-prefix | inspection
batch_outcome_analysis.json | 1038 | 25 | 321885f0d765 | JSON
batch_outcome_analysis.md | 136 | 3 | b3b5fc1c8d66 | DOC
corrected_label_overlay.json | 404836 | 7212 | 1b26d75c70a0 | JSON
decision_matrix.json | 1091 | 26 | 381f94307304 | JSON
new_group_candidate_manifest.json | 162247 | 4085 | 5695a481571d | JSON
pitch_filtered_candidate_summary.json | 977 | 23 | ccb1bdc606e3 | JSON
pitch_filtered_corrected_label_overlay.json | 377589 | 6727 | 4fa4a362d8b0 | JSON
pitch_region_candidate_audit.json | 377476 | 6725 | 0f9f8f10bdba | JSON
replacement_ball_filter_audit.json | 57 | 4 | 2142ca205e02 | JSON
review_index.html | 119208 | 1444 | 2c8a2763b497 | TEXT
v7_1_positive_candidate_mining_expansion_summary.json | 977 | 23 | ccb1bdc606e3 | JSON
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_diversity_manual_review_expansion_v1

```text
basename | bytes | lines | sha256-prefix | inspection
reviewed_label_overlay.json | 253021 | 4623 | 15ad14a17313 | JSON
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_diversity_manual_review_resolution_v1

```text
basename | bytes | lines | sha256-prefix | inspection
batch_outcome_analysis.json | 1777 | 39 | 54ad5c6df740 | JSON
batch_outcome_analysis.md | 465 | 12 | 4c544836a8a1 | DOC
decision_matrix.json | 1830 | 40 | c22342dc043d | JSON
reviewed_positive_resolution_counts.json | 721 | 20 | ebf20d5ace30 | JSON
reviewed_positive_truth_additions.json | 6769 | 137 | b07bb9ab07e5 | JSON
v7_1_positive_diversity_manual_review_resolution_summary.json | 1688 | 37 | 94b61a9fb941 | JSON
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_diversity_manual_review_resolution_v2

```text
basename | bytes | lines | sha256-prefix | inspection
batch_outcome_analysis.json | 1728 | 39 | b5dcd65b80be | JSON
batch_outcome_analysis.md | 392 | 12 | d19d4d0115d5 | DOC
decision_matrix.json | 1781 | 40 | 3fbcbb6ace2d | JSON
positive_split_group_audit.json | 43 | 4 | abf5c65a1ec1 | JSON
reviewed_positive_invalid_bbox_audit.json | 41 | 4 | b9c7e88e1e87 | JSON
reviewed_positive_label_quality_audit.json | 45 | 4 | 965369257f1e | JSON
reviewed_positive_resolution_counts.json | 664 | 20 | 72ad62ef6587 | JSON
reviewed_positive_truth_additions.json | 100514 | 1805 | f85493889a58 | JSON
v7_1_positive_diversity_manual_review_resolution_summary.json | 1639 | 37 | 271b7c497f9b | JSON
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_bounded_retrain_v1

```text
basename | bytes | lines | sha256-prefix | inspection
artifact_family_prediction_audit.json | 18818 | 364 | ca8a86b9ad17 | JSON
batch_outcome_analysis.json | 8507627 | 156983 | 87f6aa3f50e4 | JSON
batch_outcome_analysis.md | 623 | 17 | 0658c6ac7357 | DOC
bounded_train_prediction_audit.json | 544873 | 12356 | 983bff96fd7a | JSON
bounded_val_prediction_audit.json | 108075 | 2468 | 61cac66f8749 | JSON
canary_prediction_overlay_contact_sheet.jpg | 50476 | - | a2caa28d93c7 | JPEG
checkpoint_hash_audit.json | 808 | 14 | e34b4ff30e8d | JSON
confidence_sweep_audit.json | 8504569 | 156918 | 74574a0b9022 | JSON
decision_matrix.json | 3108 | 68 | 5eb69bb7e3a7 | JSON
heldout_canary_prediction_audit.json | 18458 | 364 | 0d2e104eaeef | JSON
negative_prediction_overlay_contact_sheet.jpg | 75636 | - | 8b99d4d446a4 | JPEG
positive_prediction_overlay_contact_sheet.jpg | 607557 | - | dc8d6fec71d9 | JPEG
remote_cleanup_result.json | 83 | 5 | bc81bc3975bf | JSON
results_csv_audit.json | 450 | 12 | e057f91ed416 | JSON
trainer_label_ingestion_audit.json | 206 | 9 | 350c60d50d5f | JSON
training_config.json | 520 | 25 | 25174ad1ebef | JSON
training_run_summary.json | 2510 | 50 | 4787327b6217 | JSON
v7_2_bounded_retrain_summary.json | 2910 | 65 | 28259e75146c | JSON
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_bounded_retrain_v1/bounded_dataset_snapshot

```text
basename | bytes | lines | sha256-prefix | inspection
data.yaml | 222 | 6 | 3879e8ec3e69 | TEXT
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_bounded_retrain_v1/bounded_dataset_snapshot/images/canary

```text
basename | bytes | lines | sha256-prefix | inspection
v7-1-hard-negative-top-left-4500-180.jpg | 1407 | - | 3d45f26c1a77 | JPEG
v7-1-hard-negative-top-left-4525-181.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4550-182.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4575-183.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4600-184.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4625-185.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4650-186.jpg | 1407 | - | 3d45f26c1a77 | JPEG
v7-1-hard-negative-top-left-4675-187.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4700-188.jpg | 1407 | - | 3f4ee99d81ff | JPEG
v7-1-hard-negative-top-left-4725-189.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-4750-190.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4775-191.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4800-192.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-4825-193.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4850-194.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-4875-195.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-4900-196.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-4925-197.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-4950-198.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-4975-199.jpg | 1407 | - | 898be37f7ba4 | JPEG
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_bounded_retrain_v1/bounded_dataset_snapshot/images/train

```text
basename | bytes | lines | sha256-prefix | inspection
v7-1-hard-negative-top-left-0-0.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-100-4.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1000-40.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1025-41.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-1050-42.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1075-43.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1100-44.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1125-45.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1200-48.jpg | 1407 | - | 3d45f26c1a77 | JPEG
v7-1-hard-negative-top-left-1225-49.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-125-5.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-1250-50.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1275-51.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1300-52.jpg | 1407 | - | 3d45f26c1a77 | JPEG
v7-1-hard-negative-top-left-1325-53.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1350-54.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1375-55.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1400-56.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-1425-57.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-150-6.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-1500-60.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1525-61.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1550-62.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1575-63.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1600-64.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1625-65.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1650-66.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1675-67.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1700-68.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1725-69.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-175-7.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1800-72.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1825-73.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1850-74.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1875-75.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1900-76.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1925-77.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1950-78.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1975-79.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-200-8.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-2000-80.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2025-81.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2100-84.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-2125-85.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-2150-86.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-2175-87.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2200-88.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2225-89.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-225-9.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2250-90.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-2275-91.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-2300-92.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-2325-93.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-2400-96.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-2425-97.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-2450-98.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2475-99.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-25-1.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2500-100.jpg | 1407 | - | 3d45f26c1a77 | JPEG
v7-1-hard-negative-top-left-2525-101.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2550-102.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2575-103.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2600-104.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-2625-105.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2700-108.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-2725-109.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2750-110.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-2775-111.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2800-112.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2825-113.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2850-114.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2875-115.jpg | 1407 | - | b993da7aef92 | JPEG
v7-1-hard-negative-top-left-2900-116.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2925-117.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-300-12.jpg | 1407 | - | 098fe82c84e7 | JPEG
v7-1-hard-negative-top-left-3000-120.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3025-121.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3050-122.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-3075-123.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-3100-124.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3125-125.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3150-126.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-3175-127.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-3200-128.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3225-129.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-325-13.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-3300-132.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3325-133.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-3350-134.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3375-135.jpg | 1407 | - | 098fe82c84e7 | JPEG
v7-1-hard-negative-top-left-3400-136.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-3425-137.jpg | 1407 | - | 098fe82c84e7 | JPEG
v7-1-hard-negative-top-left-3450-138.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3475-139.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-350-14.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-3500-140.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3525-141.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3600-144.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3625-145.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3650-146.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-3675-147.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3700-148.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-3725-149.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-375-15.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3750-150.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3775-151.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3800-152.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3825-153.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3900-156.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3925-157.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3950-158.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-3975-159.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-400-16.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4000-160.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-4025-161.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-4050-162.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4075-163.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4100-164.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-4125-165.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-4200-168.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4225-169.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-425-17.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4250-170.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4275-171.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4300-172.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4325-173.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4350-174.jpg | 1407 | - | 3d45f26c1a77 | JPEG
v7-1-hard-negative-top-left-4375-175.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4400-176.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4425-177.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-450-18.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-475-19.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-50-2.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-500-20.jpg | 1407 | - | 73e1a8c8f323 | JPEG
v7-1-hard-negative-top-left-525-21.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-600-24.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-625-25.jpg | 1407 | - | 2e6df316da82 | JPEG
v7-1-hard-negative-top-left-650-26.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-675-27.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-700-28.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-725-29.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-75-3.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-750-30.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-775-31.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-800-32.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-825-33.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-900-36.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-925-37.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-950-38.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-975-39.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-positive-crop-trimed-5min.mp4-125-192.jpg | 26148 | - | 23dd7da2abe3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-125-256.jpg | 40609 | - | 222cc34a51c8 | JPEG
v7-1-positive-crop-trimed-5min.mp4-125-384.jpg | 75284 | - | c006ee9e45c2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-130-192.jpg | 23849 | - | ffb25cbf8f20 | JPEG
v7-1-positive-crop-trimed-5min.mp4-130-256.jpg | 42774 | - | a710980df1ca | JPEG
v7-1-positive-crop-trimed-5min.mp4-130-384.jpg | 96431 | - | a7ea985dddb2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-135-192.jpg | 24591 | - | 5e5772b66041 | JPEG
v7-1-positive-crop-trimed-5min.mp4-135-256.jpg | 43410 | - | 759e68ddfaff | JPEG
v7-1-positive-crop-trimed-5min.mp4-135-384.jpg | 98435 | - | 540515c47f16 | JPEG
v7-1-positive-crop-trimed-5min.mp4-140-192.jpg | 24945 | - | 5669da4f5d03 | JPEG
v7-1-positive-crop-trimed-5min.mp4-140-256.jpg | 43647 | - | 181fb4e19854 | JPEG
v7-1-positive-crop-trimed-5min.mp4-140-384.jpg | 97928 | - | a2fde93b973f | JPEG
v7-1-positive-crop-trimed-5min.mp4-1815-192.jpg | 21927 | - | 283cb02748a1 | JPEG
v7-1-positive-crop-trimed-5min.mp4-1815-256.jpg | 39022 | - | 124bfe8267ff | JPEG
v7-1-positive-crop-trimed-5min.mp4-1815-384.jpg | 90674 | - | 31cd6fd5bb06 | JPEG
v7-1-positive-crop-trimed-5min.mp4-195-192.jpg | 24287 | - | a85ac06d458e | JPEG
v7-1-positive-crop-trimed-5min.mp4-195-256.jpg | 41479 | - | 99232c3791f5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-195-384.jpg | 91603 | - | fca05656e9f3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-210-192.jpg | 23929 | - | 0328f9f3f34b | JPEG
v7-1-positive-crop-trimed-5min.mp4-210-256.jpg | 41365 | - | bd668ca1afd6 | JPEG
v7-1-positive-crop-trimed-5min.mp4-210-384.jpg | 91363 | - | b130deceb000 | JPEG
v7-1-positive-crop-trimed-5min.mp4-220-192.jpg | 24688 | - | 90c6016831d1 | JPEG
v7-1-positive-crop-trimed-5min.mp4-220-256.jpg | 42341 | - | 03c0e46cfaa4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-220-384.jpg | 94348 | - | 591e7d8e266b | JPEG
v7-1-positive-crop-trimed-5min.mp4-225-192.jpg | 24979 | - | 5a9c53cc9bce | JPEG
v7-1-positive-crop-trimed-5min.mp4-225-256.jpg | 42805 | - | 77e00d1f2d03 | JPEG
v7-1-positive-crop-trimed-5min.mp4-225-384.jpg | 94779 | - | 8506bb776194 | JPEG
v7-1-positive-crop-trimed-5min.mp4-230-192.jpg | 24048 | - | 4a15ff07dbba | JPEG
v7-1-positive-crop-trimed-5min.mp4-230-256.jpg | 42169 | - | 0c237f26c163 | JPEG
v7-1-positive-crop-trimed-5min.mp4-230-384.jpg | 95330 | - | 89fc69e9b723 | JPEG
v7-1-positive-crop-trimed-5min.mp4-235-192.jpg | 23732 | - | 472b6913fc34 | JPEG
v7-1-positive-crop-trimed-5min.mp4-235-256.jpg | 41892 | - | ac925b9f9084 | JPEG
v7-1-positive-crop-trimed-5min.mp4-235-384.jpg | 95239 | - | 93d33f9964aa | JPEG
v7-1-positive-crop-trimed-5min.mp4-2457-192.jpg | 24811 | - | 1e154aed4062 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2457-256.jpg | 43402 | - | 44a294cfc9c4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2457-384.jpg | 95307 | - | 95e0ce79a30c | JPEG
v7-1-positive-crop-trimed-5min.mp4-2460-192.jpg | 25555 | - | c30ca2ab718a | JPEG
v7-1-positive-crop-trimed-5min.mp4-2460-256.jpg | 44589 | - | 230bcf328408 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2460-384.jpg | 96224 | - | 0bf5b382082a | JPEG
v7-1-positive-crop-trimed-5min.mp4-2463-192.jpg | 25632 | - | 6fd899906c9c | JPEG
v7-1-positive-crop-trimed-5min.mp4-2463-256.jpg | 44072 | - | ca718e8d2220 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2463-384.jpg | 96195 | - | 7d6b0b34a5fb | JPEG
v7-1-positive-crop-trimed-5min.mp4-2528-192.jpg | 25961 | - | 95dcd49a891e | JPEG
v7-1-positive-crop-trimed-5min.mp4-2528-256.jpg | 45491 | - | 112792778a5d | JPEG
v7-1-positive-crop-trimed-5min.mp4-2528-384.jpg | 103133 | - | 53311eb5e1b3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2531-192.jpg | 25899 | - | 557d29a2fa27 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2531-256.jpg | 45482 | - | cac1ef95801c | JPEG
v7-1-positive-crop-trimed-5min.mp4-2531-384.jpg | 103031 | - | 009de1309676 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2534-192.jpg | 25583 | - | 8e1e3293160f | JPEG
v7-1-positive-crop-trimed-5min.mp4-2534-256.jpg | 44980 | - | 67622d276235 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2534-384.jpg | 101978 | - | a124030eb493 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2886-192.jpg | 21801 | - | 86b44306ba3a | JPEG
v7-1-positive-crop-trimed-5min.mp4-2886-256.jpg | 39051 | - | 96e53b91f010 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2886-384.jpg | 92144 | - | 58882b9a6aab | JPEG
v7-1-positive-crop-trimed-5min.mp4-2889-192.jpg | 21709 | - | c850dfd95041 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2889-256.jpg | 38862 | - | c89effd19f0b | JPEG
v7-1-positive-crop-trimed-5min.mp4-2889-384.jpg | 92314 | - | 91b514e07683 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2892-192.jpg | 21371 | - | 568eefabfa10 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2892-256.jpg | 38871 | - | 348f4289c23c | JPEG
v7-1-positive-crop-trimed-5min.mp4-2892-384.jpg | 91725 | - | 19e4b939390b | JPEG
v7-1-positive-crop-trimed-5min.mp4-300-192.jpg | 25302 | - | 2f461f5a8d02 | JPEG
v7-1-positive-crop-trimed-5min.mp4-300-256.jpg | 44833 | - | 9399711cb48e | JPEG
v7-1-positive-crop-trimed-5min.mp4-300-384.jpg | 89578 | - | 18aa23df2116 | JPEG
v7-1-positive-crop-trimed-5min.mp4-305-192.jpg | 24836 | - | d8775db03135 | JPEG
v7-1-positive-crop-trimed-5min.mp4-305-256.jpg | 43477 | - | 4b5fd8db5cc5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-305-384.jpg | 83911 | - | 3288323cb5bc | JPEG
v7-1-positive-crop-trimed-5min.mp4-310-192.jpg | 25567 | - | a8ca9053a0df | JPEG
v7-1-positive-crop-trimed-5min.mp4-310-256.jpg | 43306 | - | 5edfeb30abe7 | JPEG
v7-1-positive-crop-trimed-5min.mp4-310-384.jpg | 80143 | - | 585ab4eea98f | JPEG
v7-1-positive-crop-trimed-5min.mp4-315-192.jpg | 23910 | - | 7a2fc6d1dc73 | JPEG
v7-1-positive-crop-trimed-5min.mp4-315-256.jpg | 42096 | - | 482b49a3e2f7 | JPEG
v7-1-positive-crop-trimed-5min.mp4-315-384.jpg | 82793 | - | 1cea401418c3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-320-192.jpg | 23368 | - | e4a38b78a3a3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-320-256.jpg | 41120 | - | 5d8e5b49c7a9 | JPEG
v7-1-positive-crop-trimed-5min.mp4-320-384.jpg | 83870 | - | 19a5eab85934 | JPEG
v7-1-positive-crop-trimed-5min.mp4-325-192.jpg | 21246 | - | 531f781bee75 | JPEG
v7-1-positive-crop-trimed-5min.mp4-325-256.jpg | 38978 | - | 0deb531e9385 | JPEG
v7-1-positive-crop-trimed-5min.mp4-325-384.jpg | 90272 | - | f9869d2bcefd | JPEG
v7-1-positive-crop-trimed-5min.mp4-330-192.jpg | 20835 | - | b5a319fdfe56 | JPEG
v7-1-positive-crop-trimed-5min.mp4-330-256.jpg | 39150 | - | ff7bd02b3469 | JPEG
v7-1-positive-crop-trimed-5min.mp4-330-384.jpg | 91418 | - | a72d6baf7c21 | JPEG
v7-1-positive-crop-trimed-5min.mp4-335-192.jpg | 23464 | - | 963f7bd071e1 | JPEG
v7-1-positive-crop-trimed-5min.mp4-335-256.jpg | 41016 | - | 3a2d2f41b4df | JPEG
v7-1-positive-crop-trimed-5min.mp4-335-384.jpg | 93352 | - | 5026ec61f113 | JPEG
v7-1-positive-crop-trimed-5min.mp4-340-192.jpg | 24990 | - | 4dbec6f32923 | JPEG
v7-1-positive-crop-trimed-5min.mp4-340-256.jpg | 43346 | - | 8a5954cfc112 | JPEG
v7-1-positive-crop-trimed-5min.mp4-340-384.jpg | 95176 | - | 41db55f59eeb | JPEG
v7-1-positive-crop-trimed-5min.mp4-345-192.jpg | 23560 | - | 3d9303491e46 | JPEG
v7-1-positive-crop-trimed-5min.mp4-345-256.jpg | 41788 | - | 3fab1aada2fe | JPEG
v7-1-positive-crop-trimed-5min.mp4-345-384.jpg | 92516 | - | 73ae3842f119 | JPEG
v7-1-positive-crop-trimed-5min.mp4-350-192.jpg | 22742 | - | 5d2b1d4da4b8 | JPEG
v7-1-positive-crop-trimed-5min.mp4-350-256.jpg | 38348 | - | 46ae324e5943 | JPEG
v7-1-positive-crop-trimed-5min.mp4-350-384.jpg | 89146 | - | 032607012a3c | JPEG
v7-1-positive-crop-trimed-5min.mp4-355-192.jpg | 22612 | - | d3f48a429d69 | JPEG
v7-1-positive-crop-trimed-5min.mp4-355-256.jpg | 38270 | - | 3745205db9d4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-355-384.jpg | 89167 | - | b121318f4b94 | JPEG
v7-1-positive-crop-trimed-5min.mp4-360-192.jpg | 22732 | - | 606c2c9fe831 | JPEG
v7-1-positive-crop-trimed-5min.mp4-360-256.jpg | 38713 | - | 059edb43c59a | JPEG
v7-1-positive-crop-trimed-5min.mp4-360-384.jpg | 89246 | - | 29e68ac9cc70 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3602-192.jpg | 21897 | - | 53086ffea29f | JPEG
v7-1-positive-crop-trimed-5min.mp4-3602-256.jpg | 39519 | - | 079015e0793c | JPEG
v7-1-positive-crop-trimed-5min.mp4-3602-384.jpg | 92666 | - | 2b844ff65db5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3605-192.jpg | 22046 | - | 442e5ab76fb8 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3605-256.jpg | 39706 | - | 233d9c47563f | JPEG
v7-1-positive-crop-trimed-5min.mp4-3605-384.jpg | 92767 | - | 226b63f68c0c | JPEG
v7-1-positive-crop-trimed-5min.mp4-365-192.jpg | 23794 | - | c33af2bb7459 | JPEG
v7-1-positive-crop-trimed-5min.mp4-365-256.jpg | 40202 | - | 0e1c943d9c6e | JPEG
v7-1-positive-crop-trimed-5min.mp4-365-384.jpg | 89658 | - | 0e4c1676ab77 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3670-192.jpg | 21444 | - | 9b8a4aa8076a | JPEG
v7-1-positive-crop-trimed-5min.mp4-3670-256.jpg | 38312 | - | 41c5ced57be4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3670-384.jpg | 90487 | - | 9fbd5a1c1cbb | JPEG
v7-1-positive-crop-trimed-5min.mp4-3673-192.jpg | 21269 | - | 6f89e7c6af8d | JPEG
v7-1-positive-crop-trimed-5min.mp4-3673-256.jpg | 38531 | - | b6a90c9da4df | JPEG
v7-1-positive-crop-trimed-5min.mp4-3673-384.jpg | 90782 | - | 5e17c191b296 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3676-192.jpg | 21500 | - | fb19c2e60419 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3676-256.jpg | 38571 | - | 4e5287cd0c44 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3676-384.jpg | 90491 | - | 7b493ada36a7 | JPEG
v7-1-positive-crop-trimed-5min.mp4-370-192.jpg | 24477 | - | 26fb399c7901 | JPEG
v7-1-positive-crop-trimed-5min.mp4-370-256.jpg | 41886 | - | 4a80663fbbbe | JPEG
v7-1-positive-crop-trimed-5min.mp4-370-384.jpg | 90156 | - | 93812bd91d18 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3744-192.jpg | 22220 | - | 25c03166b469 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3744-256.jpg | 38061 | - | c56fd52b9f68 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3744-384.jpg | 84925 | - | 3e935fc32eab | JPEG
v7-1-positive-crop-trimed-5min.mp4-3747-192.jpg | 22451 | - | 0d8ceb387073 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3747-256.jpg | 38498 | - | 92dd8f11da6c | JPEG
v7-1-positive-crop-trimed-5min.mp4-3747-384.jpg | 85314 | - | c171b0d8c0e2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-375-192.jpg | 24366 | - | c1586ab959bd | JPEG
v7-1-positive-crop-trimed-5min.mp4-375-256.jpg | 41904 | - | a24c4c5ea1bf | JPEG
v7-1-positive-crop-trimed-5min.mp4-375-384.jpg | 90864 | - | 84e63b1bd24b | JPEG
v7-1-positive-crop-trimed-5min.mp4-3750-192.jpg | 21996 | - | e568c45d384a | JPEG
v7-1-positive-crop-trimed-5min.mp4-3750-256.jpg | 37662 | - | ff2ae7ddedca | JPEG
v7-1-positive-crop-trimed-5min.mp4-3750-384.jpg | 83703 | - | 683f89b37943 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3821-192.jpg | 20160 | - | 63ed4661e05b | JPEG
v7-1-positive-crop-trimed-5min.mp4-3821-256.jpg | 36892 | - | 43f4a402e0b4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3821-384.jpg | 88622 | - | f3bea2622733 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3960-192.jpg | 22512 | - | f57d7d4f995b | JPEG
v7-1-positive-crop-trimed-5min.mp4-3960-256.jpg | 40661 | - | cb97a173c167 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3960-384.jpg | 95043 | - | 26738f962d23 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3963-192.jpg | 22151 | - | 2e6500431415 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3963-256.jpg | 40555 | - | 57e6304191c4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3963-384.jpg | 95417 | - | b5667360864c | JPEG
v7-1-positive-crop-trimed-5min.mp4-4099-192.jpg | 21146 | - | 31326f74f0d5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4099-256.jpg | 36420 | - | bb472d67cfe3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4099-384.jpg | 83228 | - | 4cbc36334bf0 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4102-192.jpg | 20888 | - | ce1251d18fc7 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4102-256.jpg | 36263 | - | eaf83810537b | JPEG
v7-1-positive-crop-trimed-5min.mp4-4102-384.jpg | 81752 | - | 40b279df450b | JPEG
v7-1-positive-crop-trimed-5min.mp4-4105-192.jpg | 21536 | - | 28db2e71286a | JPEG
v7-1-positive-crop-trimed-5min.mp4-4105-256.jpg | 36905 | - | b257b6f4e9e6 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4105-384.jpg | 83101 | - | 6571f6d2a42c | JPEG
v7-1-positive-crop-trimed-5min.mp4-4247-192.jpg | 27731 | - | 93d98df517d3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4247-256.jpg | 47990 | - | d69e6ef0a0b2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4247-384.jpg | 104674 | - | 71c5aea54a93 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4250-192.jpg | 26768 | - | 335a67cdb215 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4250-256.jpg | 46810 | - | 9bc57b8163be | JPEG
v7-1-positive-crop-trimed-5min.mp4-4250-384.jpg | 102455 | - | 9378e8906473 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4315-192.jpg | 23388 | - | b40daa8ec4d4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4315-256.jpg | 40612 | - | f88a608359dc | JPEG
v7-1-positive-crop-trimed-5min.mp4-4315-384.jpg | 89656 | - | 373850b1bb7f | JPEG
v7-1-positive-crop-trimed-5min.mp4-4318-192.jpg | 23083 | - | eb7d57436247 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4318-256.jpg | 40144 | - | 1981a4297d27 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4318-384.jpg | 89556 | - | a95a656bd35b | JPEG
v7-1-positive-crop-trimed-5min.mp4-4321-192.jpg | 22709 | - | 3a128588cc6e | JPEG
v7-1-positive-crop-trimed-5min.mp4-4321-256.jpg | 39431 | - | 42680ad8b3f1 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4321-384.jpg | 89457 | - | 395e4495dcdc | JPEG
v7-1-positive-crop-trimed-5min.mp4-4665-192.jpg | 27391 | - | 97e07b0f6f1d | JPEG
v7-1-positive-crop-trimed-5min.mp4-4665-256.jpg | 47333 | - | bf377e747d3c | JPEG
v7-1-positive-crop-trimed-5min.mp4-4665-384.jpg | 104081 | - | 8574f9df68da | JPEG
v7-1-positive-crop-trimed-5min.mp4-4670-192.jpg | 27527 | - | a1cec5761fa9 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4670-256.jpg | 47668 | - | 18187b4b68f2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4670-384.jpg | 104362 | - | 007dad6e4e74 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4675-192.jpg | 27500 | - | 7a493c7702e4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4675-256.jpg | 48009 | - | 2b1baa041267 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4675-384.jpg | 105263 | - | 3e4384929658 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4680-192.jpg | 27372 | - | 59298817eaa7 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4680-256.jpg | 47627 | - | ab743c56df84 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4680-384.jpg | 105056 | - | ecf5bcb5e160 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4685-192.jpg | 27260 | - | 46a749bc2e7b | JPEG
v7-1-positive-crop-trimed-5min.mp4-4685-256.jpg | 47648 | - | 38fef9d8c0d6 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4685-384.jpg | 104767 | - | 71570be564fc | JPEG
v7-1-positive-crop-trimed-5min.mp4-4690-192.jpg | 27002 | - | 2eb71dd5c1e4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4690-256.jpg | 47286 | - | 14727b01c3ad | JPEG
v7-1-positive-crop-trimed-5min.mp4-4690-384.jpg | 104027 | - | dad5ffe8aa56 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4695-192.jpg | 27185 | - | dff0d5d96839 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4695-256.jpg | 47528 | - | c20694a9e218 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4695-384.jpg | 104136 | - | 5be06c14835a | JPEG
v7-1-positive-crop-trimed-5min.mp4-5-192.jpg | 23294 | - | 15b5430546e8 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5-256.jpg | 41865 | - | 389e03321fe2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5-384.jpg | 88689 | - | 18af621ab415 | JPEG
v7-1-positive-crop-trimed-5min.mp4-50-192.jpg | 21013 | - | 36187764f60b | JPEG
v7-1-positive-crop-trimed-5min.mp4-50-256.jpg | 38119 | - | a8f3d23476df | JPEG
v7-1-positive-crop-trimed-5min.mp4-50-384.jpg | 91674 | - | fecec41ceba8 | JPEG
v7-1-positive-crop-trimed-5min.mp4-55-192.jpg | 21161 | - | 46f3e1d6c139 | JPEG
v7-1-positive-crop-trimed-5min.mp4-55-256.jpg | 38298 | - | 5ef874c2577d | JPEG
v7-1-positive-crop-trimed-5min.mp4-55-384.jpg | 91428 | - | 0d09f42f9f4d | JPEG
v7-1-positive-crop-trimed-5min.mp4-5920-192.jpg | 26010 | - | 360f1f5e017d | JPEG
v7-1-positive-crop-trimed-5min.mp4-5920-256.jpg | 45115 | - | 194f1a932a5f | JPEG
v7-1-positive-crop-trimed-5min.mp4-5920-384.jpg | 99151 | - | 24b346c983a9 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5945-192.jpg | 20787 | - | 8915e9ff2fdd | JPEG
v7-1-positive-crop-trimed-5min.mp4-5945-256.jpg | 38110 | - | a91d2ae4f6b9 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5945-384.jpg | 86510 | - | 315120fb2087 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5950-192.jpg | 24635 | - | 3cc007fa0c88 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5950-256.jpg | 43218 | - | 7d289b42b477 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5950-384.jpg | 96266 | - | a577f41e3909 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5965-192.jpg | 24280 | - | 6e2b189e2251 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5965-256.jpg | 42533 | - | 6e38d09c8583 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5965-384.jpg | 95583 | - | 627946757882 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5970-192.jpg | 23945 | - | 0f903aabb9c1 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5970-256.jpg | 42066 | - | 673420d48508 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5970-384.jpg | 94751 | - | bb4190368e39 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5975-192.jpg | 23641 | - | 422a0c573aad | JPEG
v7-1-positive-crop-trimed-5min.mp4-5975-256.jpg | 41211 | - | 4a95f9cd0c21 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5975-384.jpg | 93389 | - | 731515bab321 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5980-192.jpg | 23516 | - | 115f08555e67 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5980-256.jpg | 41019 | - | 9396569c8c60 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5980-384.jpg | 92203 | - | 068cd8d9425c | JPEG
v7-1-positive-crop-trimed-5min.mp4-60-192.jpg | 23591 | - | 7d3206820bcd | JPEG
v7-1-positive-crop-trimed-5min.mp4-60-256.jpg | 42697 | - | 143402ab3101 | JPEG
v7-1-positive-crop-trimed-5min.mp4-60-384.jpg | 94191 | - | 4e3a3abdd614 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6110-192.jpg | 19972 | - | 7311dce4cb5a | JPEG
v7-1-positive-crop-trimed-5min.mp4-6110-256.jpg | 31601 | - | 59ce61dc9cda | JPEG
v7-1-positive-crop-trimed-5min.mp4-6110-384.jpg | 61668 | - | 71ffe4727e42 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6115-192.jpg | 18658 | - | 179294c1c844 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6115-256.jpg | 30219 | - | 056b5df52584 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6115-384.jpg | 59376 | - | c8d65052b3c0 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6120-192.jpg | 19328 | - | 2e3e9659d621 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6120-256.jpg | 31179 | - | 82d713d5dd06 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6120-384.jpg | 59852 | - | 61387329450f | JPEG
v7-1-positive-crop-trimed-5min.mp4-6125-192.jpg | 18212 | - | 35e7d034cf31 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6125-256.jpg | 30382 | - | 9091255579cc | JPEG
v7-1-positive-crop-trimed-5min.mp4-6125-384.jpg | 62742 | - | 46d7c27ac946 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6135-192.jpg | 23778 | - | 5d4fd291318c | JPEG
v7-1-positive-crop-trimed-5min.mp4-6135-256.jpg | 41641 | - | 97b9319290c9 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6135-384.jpg | 85115 | - | c459b76fdd32 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6140-192.jpg | 23296 | - | 3ba900340242 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6140-256.jpg | 41296 | - | a118ad5297d2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6140-384.jpg | 92883 | - | 45fa102f322c | JPEG
v7-1-positive-crop-trimed-5min.mp4-6145-192.jpg | 24361 | - | a5246e9f1673 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6145-256.jpg | 41271 | - | e0ea56358f34 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6145-384.jpg | 90649 | - | 2d93eb44bb1e | JPEG
v7-1-positive-crop-trimed-5min.mp4-6150-192.jpg | 22677 | - | d2e3075aef45 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6150-256.jpg | 41449 | - | fab10f1eb6b0 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6150-384.jpg | 89771 | - | cea12dc6098e | JPEG
v7-1-positive-crop-trimed-5min.mp4-6155-192.jpg | 23645 | - | d1f2400d82ca | JPEG
v7-1-positive-crop-trimed-5min.mp4-6155-256.jpg | 41979 | - | 89cbaaac8984 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6155-384.jpg | 86961 | - | 3bdeb6cc76be | JPEG
v7-1-positive-crop-trimed-5min.mp4-6160-192.jpg | 24032 | - | 5342744c1e55 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6160-256.jpg | 42313 | - | dca097829bb6 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6160-384.jpg | 93683 | - | 8b4e23f424e6 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6165-192.jpg | 23940 | - | 690ce2141034 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6165-256.jpg | 41237 | - | 7ecc8ef3873a | JPEG
v7-1-positive-crop-trimed-5min.mp4-6165-384.jpg | 91783 | - | ab144599f992 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6170-192.jpg | 24204 | - | ff3041ec3c90 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6170-256.jpg | 41885 | - | f8bda3f4754d | JPEG
v7-1-positive-crop-trimed-5min.mp4-6170-384.jpg | 92941 | - | 4bce3eaf2774 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6175-192.jpg | 24255 | - | 65424c10f76a | JPEG
v7-1-positive-crop-trimed-5min.mp4-6175-256.jpg | 42280 | - | 0aa58f835c7b | JPEG
v7-1-positive-crop-trimed-5min.mp4-6175-384.jpg | 94802 | - | 7bd19d8b0ad2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6180-192.jpg | 24753 | - | 9964a072b9f4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6180-256.jpg | 42534 | - | b576dd0c10cb | JPEG
v7-1-positive-crop-trimed-5min.mp4-6180-384.jpg | 85277 | - | cdc90de9c2d8 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6185-192.jpg | 24923 | - | 43e07df38941 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6185-256.jpg | 43411 | - | f861320a23c9 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6185-384.jpg | 88009 | - | 3376427126e3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6190-192.jpg | 24944 | - | 6116a04fe1ac | JPEG
v7-1-positive-crop-trimed-5min.mp4-6190-256.jpg | 44146 | - | fde574613557 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6190-384.jpg | 98265 | - | a9734bcef381 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6195-192.jpg | 25732 | - | 9f41bd24f163 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6195-256.jpg | 45551 | - | 988720cd33dc | JPEG
v7-1-positive-crop-trimed-5min.mp4-6195-384.jpg | 101214 | - | ee0ef67614a1 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6200-192.jpg | 25341 | - | 3bcd97a4f379 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6200-256.jpg | 44265 | - | 69740a9e5e05 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6200-384.jpg | 100091 | - | 7e3820694466 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6205-192.jpg | 25366 | - | dc81d5f50d64 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6205-256.jpg | 44168 | - | df4f4c1831af | JPEG
v7-1-positive-crop-trimed-5min.mp4-6205-384.jpg | 98518 | - | 9b5917dc95db | JPEG
v7-1-positive-crop-trimed-5min.mp4-6210-192.jpg | 25575 | - | 0cbbd3842d8a | JPEG
v7-1-positive-crop-trimed-5min.mp4-6210-256.jpg | 44928 | - | e8a68d343b26 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6210-384.jpg | 99956 | - | e585aa43f6ab | JPEG
v7-1-positive-crop-trimed-5min.mp4-6215-192.jpg | 26244 | - | 6dd03d07190e | JPEG
v7-1-positive-crop-trimed-5min.mp4-6215-256.jpg | 45843 | - | e749ca3a2dc5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6215-384.jpg | 100916 | - | c441785dc070 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6220-192.jpg | 25963 | - | 6fe8234d00e9 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6220-256.jpg | 45359 | - | e38c3fa59cf2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6220-384.jpg | 100987 | - | d36b8f743fc4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6225-192.jpg | 25751 | - | 0445b8acc732 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6225-256.jpg | 45141 | - | afb228fc1885 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6225-384.jpg | 99424 | - | d01f6f6f1da4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6230-192.jpg | 24773 | - | af9c5645eaac | JPEG
v7-1-positive-crop-trimed-5min.mp4-6230-256.jpg | 43030 | - | 4ae753f1442e | JPEG
v7-1-positive-crop-trimed-5min.mp4-6230-384.jpg | 95231 | - | 436d07689c17 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6892-192.jpg | 21835 | - | e0675418998e | JPEG
v7-1-positive-crop-trimed-5min.mp4-6892-256.jpg | 39442 | - | d544789e6203 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6892-384.jpg | 91593 | - | 9c2fa7a58773 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6960-192.jpg | 22917 | - | 2efbdf391277 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6960-256.jpg | 40492 | - | 30117f260dae | JPEG
v7-1-positive-crop-trimed-5min.mp4-6960-384.jpg | 91061 | - | 6056f4f40d77 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6963-192.jpg | 23618 | - | 02f88fafe658 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6963-256.jpg | 40995 | - | 6decb7a008b2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6963-384.jpg | 91890 | - | 7f2d5335967f | JPEG
v7-1-positive-crop-trimed-5min.mp4-7099-192.jpg | 21444 | - | 6690e40a3fb5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7099-256.jpg | 36704 | - | 2ad16fa63e9e | JPEG
v7-1-positive-crop-trimed-5min.mp4-7099-384.jpg | 80471 | - | 7ed9a382de00 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7102-192.jpg | 21400 | - | ae2e4b38d2cb | JPEG
v7-1-positive-crop-trimed-5min.mp4-7102-256.jpg | 36564 | - | 30f75bc0a793 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7102-384.jpg | 79287 | - | d8f52ac5df94 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7105-192.jpg | 21396 | - | 8b6a1f3aa11c | JPEG
v7-1-positive-crop-trimed-5min.mp4-7105-256.jpg | 37054 | - | a391355a223a | JPEG
v7-1-positive-crop-trimed-5min.mp4-7105-384.jpg | 79367 | - | d14b0e1bae97 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7170-192.jpg | 23424 | - | 8124e4f2ce25 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7170-256.jpg | 40019 | - | c94087535086 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7170-384.jpg | 88050 | - | 61343c7f2c71 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7173-192.jpg | 23029 | - | 4d15003d294d | JPEG
v7-1-positive-crop-trimed-5min.mp4-7173-256.jpg | 39950 | - | 006baf39ece5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7173-384.jpg | 88391 | - | c2fcbeb9d6bd | JPEG
v7-1-positive-crop-trimed-5min.mp4-7176-192.jpg | 21163 | - | 92e220f14946 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7176-256.jpg | 37832 | - | dc02c0ff5b38 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7176-384.jpg | 86405 | - | ce54d7cc7e5d | JPEG
v7-1-positive-crop-trimed-5min.mp4-7315-192.jpg | 20184 | - | d51f067b9793 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7315-256.jpg | 37472 | - | 0b355fc3de12 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7315-384.jpg | 87101 | - | 4a5b93f2e05f | JPEG
v7-1-positive-crop-trimed-5min.mp4-7318-192.jpg | 20998 | - | 9e04119ed006 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7318-256.jpg | 37941 | - | 48c047bebdc4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7318-384.jpg | 88239 | - | fb9bd3faf1df | JPEG
v7-1-positive-crop-trimed-5min.mp4-7457-192.jpg | 20295 | - | 1f2f507e07ff | JPEG
v7-1-positive-crop-trimed-5min.mp4-7457-256.jpg | 36378 | - | 3dee1041d7fc | JPEG
v7-1-positive-crop-trimed-5min.mp4-7457-384.jpg | 86656 | - | 3230f78f9406 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7460-192.jpg | 20198 | - | cb9b94b7ea39 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7460-256.jpg | 36079 | - | 9ddfc0e25be2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7460-384.jpg | 86147 | - | 37ec76a33b13 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7463-192.jpg | 20210 | - | 8e94a7378a19 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7463-256.jpg | 35996 | - | 913c3a702603 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7463-384.jpg | 86067 | - | 01a11d1aee5d | JPEG
v7-1-positive-crop-trimed-5min.mp4-7528-192.jpg | 20547 | - | 6f9bb45e792d | JPEG
v7-1-positive-crop-trimed-5min.mp4-7528-256.jpg | 36374 | - | f4529b4fc008 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7528-384.jpg | 84900 | - | 091f34a31fcc | JPEG
v7-1-positive-crop-trimed-5min.mp4-7531-192.jpg | 20359 | - | 5079f63defb4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7531-256.jpg | 35882 | - | b57b94d2d9c6 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7531-384.jpg | 83775 | - | 78573e86869e | JPEG
v7-1-positive-crop-trimed-5min.mp4-7534-192.jpg | 20399 | - | 63c8e8e790dc | JPEG
v7-1-positive-crop-trimed-5min.mp4-7534-256.jpg | 35874 | - | e37daef9ad40 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7534-384.jpg | 84018 | - | f030ba093682 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7579-192.jpg | 19819 | - | 22c7263cf2b5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7579-256.jpg | 34576 | - | 8f2d8bda099f | JPEG
v7-1-positive-crop-trimed-5min.mp4-7579-384.jpg | 85426 | - | 754dcd38f057 | JPEG
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_bounded_retrain_v1/bounded_dataset_snapshot/images/val

```text
basename | bytes | lines | sha256-prefix | inspection
v7-1-hard-negative-top-left-1150-46.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1175-47.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1450-58.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1475-59.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1750-70.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1775-71.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2050-82.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2075-83.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2350-94.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2375-95.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-250-10.jpg | 1407 | - | 3d45f26c1a77 | JPEG
v7-1-hard-negative-top-left-2650-106.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2675-107.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-275-11.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-2950-118.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-2975-119.jpg | 1407 | - | c2f2ce425a97 | JPEG
v7-1-hard-negative-top-left-3250-130.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3275-131.jpg | 1407 | - | 248674746bdc | JPEG
v7-1-hard-negative-top-left-3550-142.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3575-143.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3850-154.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-3875-155.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4150-166.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4175-167.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4450-178.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4475-179.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-550-22.jpg | 1407 | - | 73e1a8c8f323 | JPEG
v7-1-hard-negative-top-left-575-23.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-850-34.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-875-35.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2386-192.jpg | 21914 | - | c2e160e31d59 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2386-256.jpg | 38006 | - | 3db73e73c1a7 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2386-384.jpg | 86661 | - | 0e8c272a6553 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2392-192.jpg | 21395 | - | 349e5376c687 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2392-256.jpg | 37861 | - | b50a0f43f157 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2392-384.jpg | 85465 | - | 3d22f65e9a8d | JPEG
v7-1-positive-crop-trimed-5min.mp4-240-192.jpg | 23224 | - | 0605773b2238 | JPEG
v7-1-positive-crop-trimed-5min.mp4-240-256.jpg | 41667 | - | 23a06cf607b5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-240-384.jpg | 86651 | - | e8a440e49c75 | JPEG
v7-1-positive-crop-trimed-5min.mp4-245-192.jpg | 23372 | - | 7f95f524a384 | JPEG
v7-1-positive-crop-trimed-5min.mp4-245-256.jpg | 41963 | - | a4fc9a3f880c | JPEG
v7-1-positive-crop-trimed-5min.mp4-245-384.jpg | 88386 | - | 95a3d54019cc | JPEG
v7-1-positive-crop-trimed-5min.mp4-250-192.jpg | 23099 | - | 2cd8f503c934 | JPEG
v7-1-positive-crop-trimed-5min.mp4-250-256.jpg | 41333 | - | fb6b06571fde | JPEG
v7-1-positive-crop-trimed-5min.mp4-250-384.jpg | 89558 | - | c785deb6282c | JPEG
v7-1-positive-crop-trimed-5min.mp4-260-192.jpg | 23443 | - | d3dbe7b499a6 | JPEG
v7-1-positive-crop-trimed-5min.mp4-260-256.jpg | 41304 | - | 617714662f77 | JPEG
v7-1-positive-crop-trimed-5min.mp4-260-384.jpg | 91478 | - | 8cbd4853b1bf | JPEG
v7-1-positive-crop-trimed-5min.mp4-2670-192.jpg | 21709 | - | a62f22678a36 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2670-256.jpg | 37969 | - | 1c5b36fa4bdd | JPEG
v7-1-positive-crop-trimed-5min.mp4-2670-384.jpg | 90216 | - | 22aa5884b896 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2673-192.jpg | 21005 | - | 759215dee518 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2673-256.jpg | 38030 | - | b281e016d5f4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2673-384.jpg | 90993 | - | 7eb81ddef1bc | JPEG
v7-1-positive-crop-trimed-5min.mp4-2676-192.jpg | 20924 | - | ba4316a46949 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2676-256.jpg | 38010 | - | 1b7ea4941d84 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2676-384.jpg | 92344 | - | daa5b8b7b6ca | JPEG
v7-1-positive-crop-trimed-5min.mp4-275-192.jpg | 23707 | - | 274e44387512 | JPEG
v7-1-positive-crop-trimed-5min.mp4-275-256.jpg | 42092 | - | c14075dee061 | JPEG
v7-1-positive-crop-trimed-5min.mp4-275-384.jpg | 95863 | - | 89f761a1ce00 | JPEG
v7-1-positive-crop-trimed-5min.mp4-280-192.jpg | 23711 | - | 5f403b279275 | JPEG
v7-1-positive-crop-trimed-5min.mp4-280-256.jpg | 42039 | - | 113a038f6f73 | JPEG
v7-1-positive-crop-trimed-5min.mp4-280-384.jpg | 95531 | - | 7776d8e75e6f | JPEG
v7-1-positive-crop-trimed-5min.mp4-290-192.jpg | 23204 | - | e90b3155ff13 | JPEG
v7-1-positive-crop-trimed-5min.mp4-290-256.jpg | 42043 | - | 18d265f9f5f0 | JPEG
v7-1-positive-crop-trimed-5min.mp4-290-384.jpg | 96833 | - | 7afaea6ecef0 | JPEG
v7-1-positive-crop-trimed-5min.mp4-295-192.jpg | 23973 | - | 5407de13a14f | JPEG
v7-1-positive-crop-trimed-5min.mp4-295-256.jpg | 43594 | - | d434360b1770 | JPEG
v7-1-positive-crop-trimed-5min.mp4-295-384.jpg | 96376 | - | 601bda1e3c36 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4170-192.jpg | 23217 | - | 220fb0660ce0 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4170-256.jpg | 39732 | - | 37f525ea91c8 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4170-384.jpg | 89897 | - | ac439862e409 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4173-192.jpg | 23707 | - | 5d26ce0b8619 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4173-256.jpg | 41033 | - | 13b8d431e084 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4173-384.jpg | 91486 | - | 4579f1fe9058 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4176-192.jpg | 24932 | - | 46badd5813af | JPEG
v7-1-positive-crop-trimed-5min.mp4-4176-256.jpg | 42976 | - | 0bac115149e5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4176-384.jpg | 91295 | - | 1bfd85539235 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4457-192.jpg | 21649 | - | 8e67b09a1c34 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4457-256.jpg | 38166 | - | 63fd89a7a196 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4457-384.jpg | 89114 | - | 62ca3d46af2f | JPEG
v7-1-positive-crop-trimed-5min.mp4-4460-192.jpg | 20474 | - | 01ed92be7887 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4460-256.jpg | 37520 | - | d21d516e06bc | JPEG
v7-1-positive-crop-trimed-5min.mp4-4460-384.jpg | 88859 | - | 8d920adc1453 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4463-192.jpg | 20054 | - | bd2ef6b649c2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4463-256.jpg | 36962 | - | 981e82c06405 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4463-384.jpg | 89039 | - | 66c1ef1a376f | JPEG
v7-1-positive-crop-trimed-5min.mp4-6005-192.jpg | 23163 | - | af80de9063d7 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6005-256.jpg | 39906 | - | 3525f09198b3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6005-384.jpg | 89039 | - | 10368e6acca4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6010-192.jpg | 23254 | - | 6ee968f6eca8 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6010-256.jpg | 39924 | - | d6f77bf036ab | JPEG
v7-1-positive-crop-trimed-5min.mp4-6010-384.jpg | 89084 | - | 6686c9e7fdca | JPEG
v7-1-positive-crop-trimed-5min.mp4-6957-192.jpg | 22643 | - | 3f6a30a754e2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6957-256.jpg | 40421 | - | f5e7f822f64a | JPEG
v7-1-positive-crop-trimed-5min.mp4-6957-384.jpg | 91143 | - | dc4916a2c27e | JPEG
v7-1-positive-crop-trimed-5min.mp4-7321-192.jpg | 21486 | - | 09e73f2b9a0e | JPEG
v7-1-positive-crop-trimed-5min.mp4-7321-256.jpg | 38066 | - | 261ef40a06f2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7321-384.jpg | 88613 | - | 435ca98d4a2e | JPEG
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_bounded_retrain_v1/bounded_dataset_snapshot/labels/canary

```text
basename | bytes | lines | sha256-prefix | inspection
v7-1-hard-negative-top-left-4500-180.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4525-181.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4550-182.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4575-183.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4600-184.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4625-185.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4650-186.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4675-187.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4700-188.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4725-189.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4750-190.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4775-191.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4800-192.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4825-193.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4850-194.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4875-195.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4900-196.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4925-197.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4950-198.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4975-199.txt | 0 | 0 | e3b0c44298fc | TEXT
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_bounded_retrain_v1/bounded_dataset_snapshot/labels/train

```text
basename | bytes | lines | sha256-prefix | inspection
v7-1-hard-negative-top-left-0-0.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-100-4.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1000-40.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1025-41.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1050-42.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1075-43.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1100-44.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1125-45.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1200-48.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1225-49.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-125-5.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1250-50.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1275-51.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1300-52.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1325-53.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1350-54.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1375-55.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1400-56.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1425-57.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-150-6.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1500-60.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1525-61.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1550-62.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1575-63.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1600-64.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1625-65.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1650-66.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1675-67.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1700-68.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1725-69.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-175-7.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1800-72.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1825-73.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1850-74.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1875-75.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1900-76.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1925-77.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1950-78.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1975-79.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-200-8.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2000-80.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2025-81.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2100-84.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2125-85.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2150-86.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2175-87.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2200-88.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2225-89.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-225-9.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2250-90.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2275-91.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2300-92.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2325-93.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2400-96.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2425-97.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2450-98.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2475-99.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-25-1.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2500-100.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2525-101.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2550-102.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2575-103.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2600-104.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2625-105.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2700-108.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2725-109.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2750-110.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2775-111.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2800-112.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2825-113.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2850-114.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2875-115.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2900-116.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2925-117.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-300-12.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3000-120.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3025-121.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3050-122.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3075-123.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3100-124.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3125-125.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3150-126.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3175-127.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3200-128.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3225-129.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-325-13.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3300-132.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3325-133.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3350-134.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3375-135.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3400-136.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3425-137.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3450-138.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3475-139.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-350-14.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3500-140.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3525-141.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3600-144.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3625-145.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3650-146.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3675-147.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3700-148.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3725-149.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-375-15.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3750-150.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3775-151.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3800-152.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3825-153.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3900-156.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3925-157.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3950-158.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3975-159.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-400-16.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4000-160.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4025-161.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4050-162.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4075-163.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4100-164.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4125-165.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4200-168.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4225-169.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-425-17.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4250-170.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4275-171.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4300-172.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4325-173.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4350-174.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4375-175.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4400-176.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4425-177.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-450-18.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-475-19.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-50-2.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-500-20.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-525-21.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-600-24.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-625-25.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-650-26.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-675-27.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-700-28.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-725-29.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-75-3.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-750-30.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-775-31.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-800-32.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-825-33.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-900-36.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-925-37.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-950-38.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-975-39.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-positive-crop-trimed-5min.mp4-125-192.txt | 46 | 1 | f01178699dcc | TEXT
v7-1-positive-crop-trimed-5min.mp4-125-256.txt | 46 | 1 | a2549d904591 | TEXT
v7-1-positive-crop-trimed-5min.mp4-125-384.txt | 46 | 1 | ec03264d1586 | TEXT
v7-1-positive-crop-trimed-5min.mp4-130-192.txt | 46 | 1 | 35f97f79179b | TEXT
v7-1-positive-crop-trimed-5min.mp4-130-256.txt | 46 | 1 | 980a547161cb | TEXT
v7-1-positive-crop-trimed-5min.mp4-130-384.txt | 46 | 1 | d69ecf57c9c3 | TEXT
v7-1-positive-crop-trimed-5min.mp4-135-192.txt | 46 | 1 | 493cc3155c84 | TEXT
v7-1-positive-crop-trimed-5min.mp4-135-256.txt | 46 | 1 | 4495ff564d37 | TEXT
v7-1-positive-crop-trimed-5min.mp4-135-384.txt | 46 | 1 | 008b49ae7b13 | TEXT
v7-1-positive-crop-trimed-5min.mp4-140-192.txt | 46 | 1 | d21c9ac1d314 | TEXT
v7-1-positive-crop-trimed-5min.mp4-140-256.txt | 46 | 1 | e144ee2b762d | TEXT
v7-1-positive-crop-trimed-5min.mp4-140-384.txt | 46 | 1 | 3053af3f2a9c | TEXT
v7-1-positive-crop-trimed-5min.mp4-1815-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-1815-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-1815-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-195-192.txt | 46 | 1 | 493cc3155c84 | TEXT
v7-1-positive-crop-trimed-5min.mp4-195-256.txt | 46 | 1 | 4495ff564d37 | TEXT
v7-1-positive-crop-trimed-5min.mp4-195-384.txt | 46 | 1 | 008b49ae7b13 | TEXT
v7-1-positive-crop-trimed-5min.mp4-210-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-210-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-210-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-220-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-220-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-220-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-225-192.txt | 46 | 1 | f1ce88b9fd79 | TEXT
v7-1-positive-crop-trimed-5min.mp4-225-256.txt | 46 | 1 | bfb941c2e0f7 | TEXT
v7-1-positive-crop-trimed-5min.mp4-225-384.txt | 46 | 1 | 5a4310422215 | TEXT
v7-1-positive-crop-trimed-5min.mp4-230-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-230-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-230-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-235-192.txt | 46 | 1 | f1ce88b9fd79 | TEXT
v7-1-positive-crop-trimed-5min.mp4-235-256.txt | 46 | 1 | bfb941c2e0f7 | TEXT
v7-1-positive-crop-trimed-5min.mp4-235-384.txt | 46 | 1 | 5a4310422215 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2457-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2457-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2457-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2460-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2460-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2460-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2463-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2463-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2463-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2528-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2528-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2528-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2531-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2531-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2531-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2534-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2534-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2534-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2886-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2886-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2886-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2889-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2889-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2889-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2892-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2892-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2892-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-300-192.txt | 46 | 1 | 4219f8b4b148 | TEXT
v7-1-positive-crop-trimed-5min.mp4-300-256.txt | 46 | 1 | 216df81d3d4d | TEXT
v7-1-positive-crop-trimed-5min.mp4-300-384.txt | 46 | 1 | 395aca61096d | TEXT
v7-1-positive-crop-trimed-5min.mp4-305-192.txt | 46 | 1 | 9dcb3d67f47f | TEXT
v7-1-positive-crop-trimed-5min.mp4-305-256.txt | 46 | 1 | 801623bb0d92 | TEXT
v7-1-positive-crop-trimed-5min.mp4-305-384.txt | 46 | 1 | a8ab4e7f417c | TEXT
v7-1-positive-crop-trimed-5min.mp4-310-192.txt | 46 | 1 | 4219f8b4b148 | TEXT
v7-1-positive-crop-trimed-5min.mp4-310-256.txt | 46 | 1 | 216df81d3d4d | TEXT
v7-1-positive-crop-trimed-5min.mp4-310-384.txt | 46 | 1 | 395aca61096d | TEXT
v7-1-positive-crop-trimed-5min.mp4-315-192.txt | 46 | 1 | 9dcb3d67f47f | TEXT
v7-1-positive-crop-trimed-5min.mp4-315-256.txt | 46 | 1 | 801623bb0d92 | TEXT
v7-1-positive-crop-trimed-5min.mp4-315-384.txt | 46 | 1 | 70dcbf0a02db | TEXT
v7-1-positive-crop-trimed-5min.mp4-320-192.txt | 46 | 1 | 4219f8b4b148 | TEXT
v7-1-positive-crop-trimed-5min.mp4-320-256.txt | 46 | 1 | 216df81d3d4d | TEXT
v7-1-positive-crop-trimed-5min.mp4-320-384.txt | 46 | 1 | 8853e221657d | TEXT
v7-1-positive-crop-trimed-5min.mp4-325-192.txt | 46 | 1 | 9dcb3d67f47f | TEXT
v7-1-positive-crop-trimed-5min.mp4-325-256.txt | 46 | 1 | 801623bb0d92 | TEXT
v7-1-positive-crop-trimed-5min.mp4-325-384.txt | 46 | 1 | a8ab4e7f417c | TEXT
v7-1-positive-crop-trimed-5min.mp4-330-192.txt | 46 | 1 | 89e3fd4d012a | TEXT
v7-1-positive-crop-trimed-5min.mp4-330-256.txt | 46 | 1 | df22fc1d2902 | TEXT
v7-1-positive-crop-trimed-5min.mp4-330-384.txt | 46 | 1 | 7acc6be8e3f0 | TEXT
v7-1-positive-crop-trimed-5min.mp4-335-192.txt | 46 | 1 | f01178699dcc | TEXT
v7-1-positive-crop-trimed-5min.mp4-335-256.txt | 46 | 1 | a2549d904591 | TEXT
v7-1-positive-crop-trimed-5min.mp4-335-384.txt | 46 | 1 | ec03264d1586 | TEXT
v7-1-positive-crop-trimed-5min.mp4-340-192.txt | 46 | 1 | 35f97f79179b | TEXT
v7-1-positive-crop-trimed-5min.mp4-340-256.txt | 46 | 1 | 980a547161cb | TEXT
v7-1-positive-crop-trimed-5min.mp4-340-384.txt | 46 | 1 | d69ecf57c9c3 | TEXT
v7-1-positive-crop-trimed-5min.mp4-345-192.txt | 46 | 1 | 493cc3155c84 | TEXT
v7-1-positive-crop-trimed-5min.mp4-345-256.txt | 46 | 1 | 4495ff564d37 | TEXT
v7-1-positive-crop-trimed-5min.mp4-345-384.txt | 46 | 1 | 008b49ae7b13 | TEXT
v7-1-positive-crop-trimed-5min.mp4-350-192.txt | 46 | 1 | d21c9ac1d314 | TEXT
v7-1-positive-crop-trimed-5min.mp4-350-256.txt | 46 | 1 | e144ee2b762d | TEXT
v7-1-positive-crop-trimed-5min.mp4-350-384.txt | 46 | 1 | 3053af3f2a9c | TEXT
v7-1-positive-crop-trimed-5min.mp4-355-192.txt | 46 | 1 | d8713f055b33 | TEXT
v7-1-positive-crop-trimed-5min.mp4-355-256.txt | 46 | 1 | eb04fc2545dc | TEXT
v7-1-positive-crop-trimed-5min.mp4-355-384.txt | 46 | 1 | dc37df8bc73f | TEXT
v7-1-positive-crop-trimed-5min.mp4-360-192.txt | 46 | 1 | d8713f055b33 | TEXT
v7-1-positive-crop-trimed-5min.mp4-360-256.txt | 46 | 1 | eb04fc2545dc | TEXT
v7-1-positive-crop-trimed-5min.mp4-360-384.txt | 46 | 1 | dc37df8bc73f | TEXT
v7-1-positive-crop-trimed-5min.mp4-3602-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3602-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3602-384.txt | 46 | 1 | 7f895c7ba26a | TEXT
v7-1-positive-crop-trimed-5min.mp4-3605-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3605-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3605-384.txt | 46 | 1 | df78bf8a76bb | TEXT
v7-1-positive-crop-trimed-5min.mp4-365-192.txt | 46 | 1 | d8713f055b33 | TEXT
v7-1-positive-crop-trimed-5min.mp4-365-256.txt | 46 | 1 | eb04fc2545dc | TEXT
v7-1-positive-crop-trimed-5min.mp4-365-384.txt | 46 | 1 | dc37df8bc73f | TEXT
v7-1-positive-crop-trimed-5min.mp4-3670-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3670-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3670-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-3673-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3673-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3673-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-3676-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3676-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3676-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-370-192.txt | 46 | 1 | d8713f055b33 | TEXT
v7-1-positive-crop-trimed-5min.mp4-370-256.txt | 46 | 1 | eb04fc2545dc | TEXT
v7-1-positive-crop-trimed-5min.mp4-370-384.txt | 46 | 1 | dc37df8bc73f | TEXT
v7-1-positive-crop-trimed-5min.mp4-3744-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3744-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3744-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-3747-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3747-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3747-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-375-192.txt | 46 | 1 | d8713f055b33 | TEXT
v7-1-positive-crop-trimed-5min.mp4-375-256.txt | 46 | 1 | eb04fc2545dc | TEXT
v7-1-positive-crop-trimed-5min.mp4-375-384.txt | 46 | 1 | dc37df8bc73f | TEXT
v7-1-positive-crop-trimed-5min.mp4-3750-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3750-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3750-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-3821-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3821-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3821-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-3960-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3960-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3960-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-3963-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3963-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3963-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4099-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4099-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4099-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4102-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4102-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4102-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4105-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4105-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4105-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4247-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4247-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4247-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4250-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4250-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4250-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4315-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4315-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4315-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4318-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4318-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4318-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4321-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4321-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4321-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4665-192.txt | 46 | 1 | bb241df7e236 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4665-256.txt | 46 | 1 | 6525f724d01c | TEXT
v7-1-positive-crop-trimed-5min.mp4-4665-384.txt | 46 | 1 | b3d2ae2c0c5a | TEXT
v7-1-positive-crop-trimed-5min.mp4-4670-192.txt | 46 | 1 | 67017b5b9acb | TEXT
v7-1-positive-crop-trimed-5min.mp4-4670-256.txt | 46 | 1 | 1283d6f187f1 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4670-384.txt | 46 | 1 | 0dabf71ae6b9 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4675-192.txt | 46 | 1 | bb241df7e236 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4675-256.txt | 46 | 1 | 6525f724d01c | TEXT
v7-1-positive-crop-trimed-5min.mp4-4675-384.txt | 46 | 1 | b3d2ae2c0c5a | TEXT
v7-1-positive-crop-trimed-5min.mp4-4680-192.txt | 46 | 1 | 67017b5b9acb | TEXT
v7-1-positive-crop-trimed-5min.mp4-4680-256.txt | 46 | 1 | 1283d6f187f1 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4680-384.txt | 46 | 1 | 0dabf71ae6b9 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4685-192.txt | 46 | 1 | 3f5b800bf10c | TEXT
v7-1-positive-crop-trimed-5min.mp4-4685-256.txt | 46 | 1 | 3626e81053f4 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4685-384.txt | 46 | 1 | b9f5262d5845 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4690-192.txt | 46 | 1 | 3481e7245ba6 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4690-256.txt | 46 | 1 | e6f50d8bc10a | TEXT
v7-1-positive-crop-trimed-5min.mp4-4690-384.txt | 46 | 1 | e751b11f1fe8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4695-192.txt | 46 | 1 | 12ebb6c8b369 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4695-256.txt | 46 | 1 | 292aa7fcd4da | TEXT
v7-1-positive-crop-trimed-5min.mp4-4695-384.txt | 46 | 1 | c091724be964 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5-192.txt | 46 | 1 | f1ce88b9fd79 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5-256.txt | 46 | 1 | bfb941c2e0f7 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5-384.txt | 46 | 1 | 5a4310422215 | TEXT
v7-1-positive-crop-trimed-5min.mp4-50-192.txt | 46 | 1 | 4219f8b4b148 | TEXT
v7-1-positive-crop-trimed-5min.mp4-50-256.txt | 46 | 1 | 216df81d3d4d | TEXT
v7-1-positive-crop-trimed-5min.mp4-50-384.txt | 46 | 1 | 395aca61096d | TEXT
v7-1-positive-crop-trimed-5min.mp4-55-192.txt | 46 | 1 | 9dcb3d67f47f | TEXT
v7-1-positive-crop-trimed-5min.mp4-55-256.txt | 46 | 1 | 801623bb0d92 | TEXT
v7-1-positive-crop-trimed-5min.mp4-55-384.txt | 46 | 1 | a8ab4e7f417c | TEXT
v7-1-positive-crop-trimed-5min.mp4-5920-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5920-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5920-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-5945-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5945-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5945-384.txt | 46 | 1 | 20a31e365aa0 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5950-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5950-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5950-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-5965-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5965-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5965-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-5970-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5970-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5970-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-5975-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5975-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5975-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-5980-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5980-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5980-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-60-192.txt | 46 | 1 | 89e3fd4d012a | TEXT
v7-1-positive-crop-trimed-5min.mp4-60-256.txt | 46 | 1 | df22fc1d2902 | TEXT
v7-1-positive-crop-trimed-5min.mp4-60-384.txt | 46 | 1 | 092506d7a208 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6110-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6110-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6110-384.txt | 46 | 1 | d65f988e2c6b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6115-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6115-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6115-384.txt | 46 | 1 | 01c5f904beb6 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6120-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6120-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6120-384.txt | 46 | 1 | 4e009442a968 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6125-192.txt | 46 | 1 | fab066afaaca | TEXT
v7-1-positive-crop-trimed-5min.mp4-6125-256.txt | 46 | 1 | 18c49173aed6 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6125-384.txt | 46 | 1 | cfb1b8c831ed | TEXT
v7-1-positive-crop-trimed-5min.mp4-6135-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6135-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6135-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6140-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6140-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6140-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6145-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6145-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6145-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6150-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6150-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6150-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6155-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6155-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6155-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6160-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6160-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6160-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6165-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6165-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6165-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6170-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6170-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6170-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6175-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6175-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6175-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6180-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6180-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6180-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6185-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6185-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6185-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6190-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6190-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6190-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6195-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6195-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6195-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6200-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6200-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6200-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6205-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6205-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6205-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6210-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6210-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6210-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6215-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6215-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6215-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6220-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6220-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6220-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6225-192.txt | 46 | 1 | d838216cbc7c | TEXT
v7-1-positive-crop-trimed-5min.mp4-6225-256.txt | 46 | 1 | 1ef540a5ef39 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6225-384.txt | 46 | 1 | ba2e02a1f88c | TEXT
v7-1-positive-crop-trimed-5min.mp4-6230-192.txt | 46 | 1 | 70d1cde32bd4 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6230-256.txt | 46 | 1 | d03151821eb7 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6230-384.txt | 46 | 1 | f073397e7172 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6892-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6892-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6892-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-6960-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6960-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6960-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-6963-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6963-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6963-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7099-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7099-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7099-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7102-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7102-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7102-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7105-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7105-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7105-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7170-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7170-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7170-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7173-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7173-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7173-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7176-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7176-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7176-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7315-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7315-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7315-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7318-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7318-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7318-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7457-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7457-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7457-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7460-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7460-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7460-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7463-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7463-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7463-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7528-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7528-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7528-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7531-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7531-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7531-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7534-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7534-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7534-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7579-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7579-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7579-384.txt | 46 | 1 | e035c36c63ea | TEXT
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_bounded_retrain_v1/bounded_dataset_snapshot/labels/val

```text
basename | bytes | lines | sha256-prefix | inspection
v7-1-hard-negative-top-left-1150-46.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1175-47.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1450-58.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1475-59.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1750-70.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1775-71.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2050-82.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2075-83.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2350-94.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2375-95.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-250-10.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2650-106.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2675-107.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-275-11.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2950-118.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2975-119.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3250-130.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3275-131.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3550-142.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3575-143.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3850-154.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3875-155.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4150-166.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4175-167.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4450-178.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4475-179.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-550-22.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-575-23.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-850-34.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-875-35.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-positive-crop-trimed-5min.mp4-2386-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2386-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2386-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2392-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2392-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2392-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-240-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-240-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-240-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-245-192.txt | 46 | 1 | f1ce88b9fd79 | TEXT
v7-1-positive-crop-trimed-5min.mp4-245-256.txt | 46 | 1 | bfb941c2e0f7 | TEXT
v7-1-positive-crop-trimed-5min.mp4-245-384.txt | 46 | 1 | 5a4310422215 | TEXT
v7-1-positive-crop-trimed-5min.mp4-250-192.txt | 46 | 1 | cad00e349fa6 | TEXT
v7-1-positive-crop-trimed-5min.mp4-250-256.txt | 46 | 1 | 466eb6125f7b | TEXT
v7-1-positive-crop-trimed-5min.mp4-250-384.txt | 46 | 1 | bb1baabc0c7c | TEXT
v7-1-positive-crop-trimed-5min.mp4-260-192.txt | 46 | 1 | fd51077cfdae | TEXT
v7-1-positive-crop-trimed-5min.mp4-260-256.txt | 46 | 1 | 908e247de6c4 | TEXT
v7-1-positive-crop-trimed-5min.mp4-260-384.txt | 46 | 1 | 579dbc1795c4 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2670-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2670-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2670-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2673-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2673-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2673-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2676-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2676-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2676-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-275-192.txt | 46 | 1 | f1ce88b9fd79 | TEXT
v7-1-positive-crop-trimed-5min.mp4-275-256.txt | 46 | 1 | bfb941c2e0f7 | TEXT
v7-1-positive-crop-trimed-5min.mp4-275-384.txt | 46 | 1 | 5a4310422215 | TEXT
v7-1-positive-crop-trimed-5min.mp4-280-192.txt | 46 | 1 | cad00e349fa6 | TEXT
v7-1-positive-crop-trimed-5min.mp4-280-256.txt | 46 | 1 | 466eb6125f7b | TEXT
v7-1-positive-crop-trimed-5min.mp4-280-384.txt | 46 | 1 | bb1baabc0c7c | TEXT
v7-1-positive-crop-trimed-5min.mp4-290-192.txt | 46 | 1 | fd51077cfdae | TEXT
v7-1-positive-crop-trimed-5min.mp4-290-256.txt | 46 | 1 | 908e247de6c4 | TEXT
v7-1-positive-crop-trimed-5min.mp4-290-384.txt | 46 | 1 | 579dbc1795c4 | TEXT
v7-1-positive-crop-trimed-5min.mp4-295-192.txt | 46 | 1 | f01178699dcc | TEXT
v7-1-positive-crop-trimed-5min.mp4-295-256.txt | 46 | 1 | a2549d904591 | TEXT
v7-1-positive-crop-trimed-5min.mp4-295-384.txt | 46 | 1 | ec03264d1586 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4170-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4170-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4170-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4173-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4173-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4173-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4176-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4176-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4176-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4457-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4457-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4457-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4460-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4460-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4460-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4463-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4463-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4463-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-6005-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6005-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6005-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6010-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6010-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6010-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6957-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6957-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6957-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7321-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7321-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7321-384.txt | 46 | 1 | e035c36c63ea | TEXT
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_bounded_retrain_v1/train_run

```text
basename | bytes | lines | sha256-prefix | inspection
results.csv | 9722 | 81 | 5f9d4c63f851 | TEXT
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_bounded_retrain_v1/train_run/weights

```text
basename | bytes | lines | sha256-prefix | inspection
best.pt | 5709306 | - | 47df22d2958d | PT
last.pt | 5709306 | - | 86947a1c3538 | PT
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_crop_probe_precision_guardrail_audit_v1

```text
basename | bytes | lines | sha256-prefix | inspection
artifact_family_breakdown.json | 169 | 8 | a3a2d9aa82be | JSON
batch_outcome_analysis.json | 5062744 | 94353 | 0efb3c6ac046 | JSON
batch_outcome_analysis.md | 673 | 17 | 769c6823fb56 | DOC
checkpoint_contract_audit.json | 5325 | 117 | 81100089a720 | JSON
confidence_sweep_audit.json | 4870476 | 94261 | 9fdca1b89995 | JSON
decision_matrix.json | 2312 | 53 | 8689e0edcea4 | JSON
hard_negative_prediction_audit.json | 172004 | 3260 | f2b7a888e949 | JSON
heldout_canary_prediction_audit.json | 19372 | 370 | 6c4b6d97ad63 | JSON
old_top_left_artifact_prediction_audit.json | 19732 | 370 | df8c8fbe0cd0 | JSON
top_left_artifact_contact_sheet.jpg | 50476 | - | a2caa28d93c7 | JPEG
train_positive_prediction_audit.json | 420500 | 9654 | 8b652b8ff65a | JSON
v7_2_crop_probe_precision_guardrail_summary.json | 2144 | 50 | 980ecadd63d0 | JSON
val_positive_prediction_audit.json | 83341 | 1926 | b6c93e7406d5 | JSON
validation_positive_miss_analysis.json | 1358 | 40 | bb61aeab0325 | JSON
worst_false_positives_contact_sheet.jpg | 50515 | - | 8c28a891173c | JPEG
worst_positive_misses_contact_sheet.jpg | 41040 | - | a3ca6ed5583e | JPEG
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_crop_probe_precision_guardrail_audit_v1/audit_dataset_snapshot/images/canary

```text
basename | bytes | lines | sha256-prefix | inspection
v7-1-hard-negative-top-left-4500-180.jpg | 1407 | - | 3d45f26c1a77 | JPEG
v7-1-hard-negative-top-left-4525-181.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4550-182.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4575-183.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4600-184.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4625-185.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4650-186.jpg | 1407 | - | 3d45f26c1a77 | JPEG
v7-1-hard-negative-top-left-4675-187.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4700-188.jpg | 1407 | - | 3f4ee99d81ff | JPEG
v7-1-hard-negative-top-left-4725-189.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-4750-190.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4775-191.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4800-192.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-4825-193.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4850-194.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-4875-195.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-4900-196.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-4925-197.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-4950-198.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-4975-199.jpg | 1407 | - | 898be37f7ba4 | JPEG
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_crop_probe_precision_guardrail_audit_v1/audit_dataset_snapshot/images/train

```text
basename | bytes | lines | sha256-prefix | inspection
v7-1-hard-negative-top-left-0-0.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-100-4.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1000-40.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1025-41.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-1050-42.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1075-43.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1100-44.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1125-45.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1200-48.jpg | 1407 | - | 3d45f26c1a77 | JPEG
v7-1-hard-negative-top-left-1225-49.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-125-5.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-1250-50.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1275-51.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1300-52.jpg | 1407 | - | 3d45f26c1a77 | JPEG
v7-1-hard-negative-top-left-1325-53.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1350-54.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1375-55.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1400-56.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-1425-57.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-150-6.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-1500-60.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1525-61.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1550-62.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1575-63.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1600-64.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1625-65.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1650-66.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1675-67.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1700-68.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1725-69.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-175-7.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1800-72.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1825-73.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1850-74.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1875-75.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1900-76.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1925-77.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1950-78.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1975-79.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-200-8.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-2000-80.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2025-81.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2100-84.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-2125-85.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-2150-86.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-2175-87.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2200-88.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2225-89.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-225-9.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2250-90.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-2275-91.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-2300-92.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-2325-93.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-2400-96.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-2425-97.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-2450-98.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2475-99.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-25-1.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2500-100.jpg | 1407 | - | 3d45f26c1a77 | JPEG
v7-1-hard-negative-top-left-2525-101.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2550-102.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2575-103.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2600-104.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-2625-105.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2700-108.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-2725-109.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2750-110.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-2775-111.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2800-112.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2825-113.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2850-114.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2875-115.jpg | 1407 | - | b993da7aef92 | JPEG
v7-1-hard-negative-top-left-2900-116.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2925-117.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-300-12.jpg | 1407 | - | 098fe82c84e7 | JPEG
v7-1-hard-negative-top-left-3000-120.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3025-121.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3050-122.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-3075-123.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-3100-124.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3125-125.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3150-126.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-3175-127.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-3200-128.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3225-129.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-325-13.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-3300-132.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3325-133.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-3350-134.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3375-135.jpg | 1407 | - | 098fe82c84e7 | JPEG
v7-1-hard-negative-top-left-3400-136.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-3425-137.jpg | 1407 | - | 098fe82c84e7 | JPEG
v7-1-hard-negative-top-left-3450-138.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3475-139.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-350-14.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-3500-140.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3525-141.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3600-144.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3625-145.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3650-146.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-3675-147.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3700-148.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-3725-149.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-375-15.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3750-150.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3775-151.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3800-152.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3825-153.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3900-156.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3925-157.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3950-158.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-3975-159.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-400-16.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4000-160.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-4025-161.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-4050-162.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4075-163.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4100-164.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-4125-165.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-4200-168.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4225-169.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-425-17.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4250-170.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4275-171.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4300-172.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4325-173.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4350-174.jpg | 1407 | - | 3d45f26c1a77 | JPEG
v7-1-hard-negative-top-left-4375-175.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4400-176.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4425-177.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-450-18.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-475-19.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-50-2.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-500-20.jpg | 1407 | - | 73e1a8c8f323 | JPEG
v7-1-hard-negative-top-left-525-21.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-600-24.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-625-25.jpg | 1407 | - | 2e6df316da82 | JPEG
v7-1-hard-negative-top-left-650-26.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-675-27.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-700-28.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-725-29.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-75-3.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-750-30.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-775-31.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-800-32.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-825-33.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-900-36.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-925-37.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-950-38.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-975-39.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-positive-crop-trimed-5min.mp4-125-192.jpg | 26148 | - | 23dd7da2abe3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-125-256.jpg | 40609 | - | 222cc34a51c8 | JPEG
v7-1-positive-crop-trimed-5min.mp4-125-384.jpg | 75284 | - | c006ee9e45c2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-130-192.jpg | 23849 | - | ffb25cbf8f20 | JPEG
v7-1-positive-crop-trimed-5min.mp4-130-256.jpg | 42774 | - | a710980df1ca | JPEG
v7-1-positive-crop-trimed-5min.mp4-130-384.jpg | 96431 | - | a7ea985dddb2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-135-192.jpg | 24591 | - | 5e5772b66041 | JPEG
v7-1-positive-crop-trimed-5min.mp4-135-256.jpg | 43410 | - | 759e68ddfaff | JPEG
v7-1-positive-crop-trimed-5min.mp4-135-384.jpg | 98435 | - | 540515c47f16 | JPEG
v7-1-positive-crop-trimed-5min.mp4-140-192.jpg | 24945 | - | 5669da4f5d03 | JPEG
v7-1-positive-crop-trimed-5min.mp4-140-256.jpg | 43647 | - | 181fb4e19854 | JPEG
v7-1-positive-crop-trimed-5min.mp4-140-384.jpg | 97928 | - | a2fde93b973f | JPEG
v7-1-positive-crop-trimed-5min.mp4-1815-192.jpg | 21927 | - | 283cb02748a1 | JPEG
v7-1-positive-crop-trimed-5min.mp4-1815-256.jpg | 39022 | - | 124bfe8267ff | JPEG
v7-1-positive-crop-trimed-5min.mp4-1815-384.jpg | 90674 | - | 31cd6fd5bb06 | JPEG
v7-1-positive-crop-trimed-5min.mp4-195-192.jpg | 24287 | - | a85ac06d458e | JPEG
v7-1-positive-crop-trimed-5min.mp4-195-256.jpg | 41479 | - | 99232c3791f5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-195-384.jpg | 91603 | - | fca05656e9f3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-210-192.jpg | 23929 | - | 0328f9f3f34b | JPEG
v7-1-positive-crop-trimed-5min.mp4-210-256.jpg | 41365 | - | bd668ca1afd6 | JPEG
v7-1-positive-crop-trimed-5min.mp4-210-384.jpg | 91363 | - | b130deceb000 | JPEG
v7-1-positive-crop-trimed-5min.mp4-220-192.jpg | 24688 | - | 90c6016831d1 | JPEG
v7-1-positive-crop-trimed-5min.mp4-220-256.jpg | 42341 | - | 03c0e46cfaa4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-220-384.jpg | 94348 | - | 591e7d8e266b | JPEG
v7-1-positive-crop-trimed-5min.mp4-225-192.jpg | 24979 | - | 5a9c53cc9bce | JPEG
v7-1-positive-crop-trimed-5min.mp4-225-256.jpg | 42805 | - | 77e00d1f2d03 | JPEG
v7-1-positive-crop-trimed-5min.mp4-225-384.jpg | 94779 | - | 8506bb776194 | JPEG
v7-1-positive-crop-trimed-5min.mp4-230-192.jpg | 24048 | - | 4a15ff07dbba | JPEG
v7-1-positive-crop-trimed-5min.mp4-230-256.jpg | 42169 | - | 0c237f26c163 | JPEG
v7-1-positive-crop-trimed-5min.mp4-230-384.jpg | 95330 | - | 89fc69e9b723 | JPEG
v7-1-positive-crop-trimed-5min.mp4-235-192.jpg | 23732 | - | 472b6913fc34 | JPEG
v7-1-positive-crop-trimed-5min.mp4-235-256.jpg | 41892 | - | ac925b9f9084 | JPEG
v7-1-positive-crop-trimed-5min.mp4-235-384.jpg | 95239 | - | 93d33f9964aa | JPEG
v7-1-positive-crop-trimed-5min.mp4-2457-192.jpg | 24811 | - | 1e154aed4062 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2457-256.jpg | 43402 | - | 44a294cfc9c4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2457-384.jpg | 95307 | - | 95e0ce79a30c | JPEG
v7-1-positive-crop-trimed-5min.mp4-2460-192.jpg | 25555 | - | c30ca2ab718a | JPEG
v7-1-positive-crop-trimed-5min.mp4-2460-256.jpg | 44589 | - | 230bcf328408 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2460-384.jpg | 96224 | - | 0bf5b382082a | JPEG
v7-1-positive-crop-trimed-5min.mp4-2463-192.jpg | 25632 | - | 6fd899906c9c | JPEG
v7-1-positive-crop-trimed-5min.mp4-2463-256.jpg | 44072 | - | ca718e8d2220 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2463-384.jpg | 96195 | - | 7d6b0b34a5fb | JPEG
v7-1-positive-crop-trimed-5min.mp4-2528-192.jpg | 25961 | - | 95dcd49a891e | JPEG
v7-1-positive-crop-trimed-5min.mp4-2528-256.jpg | 45491 | - | 112792778a5d | JPEG
v7-1-positive-crop-trimed-5min.mp4-2528-384.jpg | 103133 | - | 53311eb5e1b3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2531-192.jpg | 25899 | - | 557d29a2fa27 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2531-256.jpg | 45482 | - | cac1ef95801c | JPEG
v7-1-positive-crop-trimed-5min.mp4-2531-384.jpg | 103031 | - | 009de1309676 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2534-192.jpg | 25583 | - | 8e1e3293160f | JPEG
v7-1-positive-crop-trimed-5min.mp4-2534-256.jpg | 44980 | - | 67622d276235 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2534-384.jpg | 101978 | - | a124030eb493 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2886-192.jpg | 21801 | - | 86b44306ba3a | JPEG
v7-1-positive-crop-trimed-5min.mp4-2886-256.jpg | 39051 | - | 96e53b91f010 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2886-384.jpg | 92144 | - | 58882b9a6aab | JPEG
v7-1-positive-crop-trimed-5min.mp4-2889-192.jpg | 21709 | - | c850dfd95041 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2889-256.jpg | 38862 | - | c89effd19f0b | JPEG
v7-1-positive-crop-trimed-5min.mp4-2889-384.jpg | 92314 | - | 91b514e07683 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2892-192.jpg | 21371 | - | 568eefabfa10 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2892-256.jpg | 38871 | - | 348f4289c23c | JPEG
v7-1-positive-crop-trimed-5min.mp4-2892-384.jpg | 91725 | - | 19e4b939390b | JPEG
v7-1-positive-crop-trimed-5min.mp4-300-192.jpg | 25302 | - | 2f461f5a8d02 | JPEG
v7-1-positive-crop-trimed-5min.mp4-300-256.jpg | 44833 | - | 9399711cb48e | JPEG
v7-1-positive-crop-trimed-5min.mp4-300-384.jpg | 89578 | - | 18aa23df2116 | JPEG
v7-1-positive-crop-trimed-5min.mp4-305-192.jpg | 24836 | - | d8775db03135 | JPEG
v7-1-positive-crop-trimed-5min.mp4-305-256.jpg | 43477 | - | 4b5fd8db5cc5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-305-384.jpg | 83911 | - | 3288323cb5bc | JPEG
v7-1-positive-crop-trimed-5min.mp4-310-192.jpg | 25567 | - | a8ca9053a0df | JPEG
v7-1-positive-crop-trimed-5min.mp4-310-256.jpg | 43306 | - | 5edfeb30abe7 | JPEG
v7-1-positive-crop-trimed-5min.mp4-310-384.jpg | 80143 | - | 585ab4eea98f | JPEG
v7-1-positive-crop-trimed-5min.mp4-315-192.jpg | 23910 | - | 7a2fc6d1dc73 | JPEG
v7-1-positive-crop-trimed-5min.mp4-315-256.jpg | 42096 | - | 482b49a3e2f7 | JPEG
v7-1-positive-crop-trimed-5min.mp4-315-384.jpg | 82793 | - | 1cea401418c3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-320-192.jpg | 23368 | - | e4a38b78a3a3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-320-256.jpg | 41120 | - | 5d8e5b49c7a9 | JPEG
v7-1-positive-crop-trimed-5min.mp4-320-384.jpg | 83870 | - | 19a5eab85934 | JPEG
v7-1-positive-crop-trimed-5min.mp4-325-192.jpg | 21246 | - | 531f781bee75 | JPEG
v7-1-positive-crop-trimed-5min.mp4-325-256.jpg | 38978 | - | 0deb531e9385 | JPEG
v7-1-positive-crop-trimed-5min.mp4-325-384.jpg | 90272 | - | f9869d2bcefd | JPEG
v7-1-positive-crop-trimed-5min.mp4-330-192.jpg | 20835 | - | b5a319fdfe56 | JPEG
v7-1-positive-crop-trimed-5min.mp4-330-256.jpg | 39150 | - | ff7bd02b3469 | JPEG
v7-1-positive-crop-trimed-5min.mp4-330-384.jpg | 91418 | - | a72d6baf7c21 | JPEG
v7-1-positive-crop-trimed-5min.mp4-335-192.jpg | 23464 | - | 963f7bd071e1 | JPEG
v7-1-positive-crop-trimed-5min.mp4-335-256.jpg | 41016 | - | 3a2d2f41b4df | JPEG
v7-1-positive-crop-trimed-5min.mp4-335-384.jpg | 93352 | - | 5026ec61f113 | JPEG
v7-1-positive-crop-trimed-5min.mp4-340-192.jpg | 24990 | - | 4dbec6f32923 | JPEG
v7-1-positive-crop-trimed-5min.mp4-340-256.jpg | 43346 | - | 8a5954cfc112 | JPEG
v7-1-positive-crop-trimed-5min.mp4-340-384.jpg | 95176 | - | 41db55f59eeb | JPEG
v7-1-positive-crop-trimed-5min.mp4-345-192.jpg | 23560 | - | 3d9303491e46 | JPEG
v7-1-positive-crop-trimed-5min.mp4-345-256.jpg | 41788 | - | 3fab1aada2fe | JPEG
v7-1-positive-crop-trimed-5min.mp4-345-384.jpg | 92516 | - | 73ae3842f119 | JPEG
v7-1-positive-crop-trimed-5min.mp4-350-192.jpg | 22742 | - | 5d2b1d4da4b8 | JPEG
v7-1-positive-crop-trimed-5min.mp4-350-256.jpg | 38348 | - | 46ae324e5943 | JPEG
v7-1-positive-crop-trimed-5min.mp4-350-384.jpg | 89146 | - | 032607012a3c | JPEG
v7-1-positive-crop-trimed-5min.mp4-355-192.jpg | 22612 | - | d3f48a429d69 | JPEG
v7-1-positive-crop-trimed-5min.mp4-355-256.jpg | 38270 | - | 3745205db9d4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-355-384.jpg | 89167 | - | b121318f4b94 | JPEG
v7-1-positive-crop-trimed-5min.mp4-360-192.jpg | 22732 | - | 606c2c9fe831 | JPEG
v7-1-positive-crop-trimed-5min.mp4-360-256.jpg | 38713 | - | 059edb43c59a | JPEG
v7-1-positive-crop-trimed-5min.mp4-360-384.jpg | 89246 | - | 29e68ac9cc70 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3602-192.jpg | 21897 | - | 53086ffea29f | JPEG
v7-1-positive-crop-trimed-5min.mp4-3602-256.jpg | 39519 | - | 079015e0793c | JPEG
v7-1-positive-crop-trimed-5min.mp4-3602-384.jpg | 92666 | - | 2b844ff65db5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3605-192.jpg | 22046 | - | 442e5ab76fb8 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3605-256.jpg | 39706 | - | 233d9c47563f | JPEG
v7-1-positive-crop-trimed-5min.mp4-3605-384.jpg | 92767 | - | 226b63f68c0c | JPEG
v7-1-positive-crop-trimed-5min.mp4-365-192.jpg | 23794 | - | c33af2bb7459 | JPEG
v7-1-positive-crop-trimed-5min.mp4-365-256.jpg | 40202 | - | 0e1c943d9c6e | JPEG
v7-1-positive-crop-trimed-5min.mp4-365-384.jpg | 89658 | - | 0e4c1676ab77 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3670-192.jpg | 21444 | - | 9b8a4aa8076a | JPEG
v7-1-positive-crop-trimed-5min.mp4-3670-256.jpg | 38312 | - | 41c5ced57be4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3670-384.jpg | 90487 | - | 9fbd5a1c1cbb | JPEG
v7-1-positive-crop-trimed-5min.mp4-3673-192.jpg | 21269 | - | 6f89e7c6af8d | JPEG
v7-1-positive-crop-trimed-5min.mp4-3673-256.jpg | 38531 | - | b6a90c9da4df | JPEG
v7-1-positive-crop-trimed-5min.mp4-3673-384.jpg | 90782 | - | 5e17c191b296 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3676-192.jpg | 21500 | - | fb19c2e60419 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3676-256.jpg | 38571 | - | 4e5287cd0c44 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3676-384.jpg | 90491 | - | 7b493ada36a7 | JPEG
v7-1-positive-crop-trimed-5min.mp4-370-192.jpg | 24477 | - | 26fb399c7901 | JPEG
v7-1-positive-crop-trimed-5min.mp4-370-256.jpg | 41886 | - | 4a80663fbbbe | JPEG
v7-1-positive-crop-trimed-5min.mp4-370-384.jpg | 90156 | - | 93812bd91d18 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3744-192.jpg | 22220 | - | 25c03166b469 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3744-256.jpg | 38061 | - | c56fd52b9f68 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3744-384.jpg | 84925 | - | 3e935fc32eab | JPEG
v7-1-positive-crop-trimed-5min.mp4-3747-192.jpg | 22451 | - | 0d8ceb387073 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3747-256.jpg | 38498 | - | 92dd8f11da6c | JPEG
v7-1-positive-crop-trimed-5min.mp4-3747-384.jpg | 85314 | - | c171b0d8c0e2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-375-192.jpg | 24366 | - | c1586ab959bd | JPEG
v7-1-positive-crop-trimed-5min.mp4-375-256.jpg | 41904 | - | a24c4c5ea1bf | JPEG
v7-1-positive-crop-trimed-5min.mp4-375-384.jpg | 90864 | - | 84e63b1bd24b | JPEG
v7-1-positive-crop-trimed-5min.mp4-3750-192.jpg | 21996 | - | e568c45d384a | JPEG
v7-1-positive-crop-trimed-5min.mp4-3750-256.jpg | 37662 | - | ff2ae7ddedca | JPEG
v7-1-positive-crop-trimed-5min.mp4-3750-384.jpg | 83703 | - | 683f89b37943 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3821-192.jpg | 20160 | - | 63ed4661e05b | JPEG
v7-1-positive-crop-trimed-5min.mp4-3821-256.jpg | 36892 | - | 43f4a402e0b4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3821-384.jpg | 88622 | - | f3bea2622733 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3960-192.jpg | 22512 | - | f57d7d4f995b | JPEG
v7-1-positive-crop-trimed-5min.mp4-3960-256.jpg | 40661 | - | cb97a173c167 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3960-384.jpg | 95043 | - | 26738f962d23 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3963-192.jpg | 22151 | - | 2e6500431415 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3963-256.jpg | 40555 | - | 57e6304191c4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3963-384.jpg | 95417 | - | b5667360864c | JPEG
v7-1-positive-crop-trimed-5min.mp4-4099-192.jpg | 21146 | - | 31326f74f0d5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4099-256.jpg | 36420 | - | bb472d67cfe3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4099-384.jpg | 83228 | - | 4cbc36334bf0 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4102-192.jpg | 20888 | - | ce1251d18fc7 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4102-256.jpg | 36263 | - | eaf83810537b | JPEG
v7-1-positive-crop-trimed-5min.mp4-4102-384.jpg | 81752 | - | 40b279df450b | JPEG
v7-1-positive-crop-trimed-5min.mp4-4105-192.jpg | 21536 | - | 28db2e71286a | JPEG
v7-1-positive-crop-trimed-5min.mp4-4105-256.jpg | 36905 | - | b257b6f4e9e6 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4105-384.jpg | 83101 | - | 6571f6d2a42c | JPEG
v7-1-positive-crop-trimed-5min.mp4-4247-192.jpg | 27731 | - | 93d98df517d3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4247-256.jpg | 47990 | - | d69e6ef0a0b2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4247-384.jpg | 104674 | - | 71c5aea54a93 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4250-192.jpg | 26768 | - | 335a67cdb215 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4250-256.jpg | 46810 | - | 9bc57b8163be | JPEG
v7-1-positive-crop-trimed-5min.mp4-4250-384.jpg | 102455 | - | 9378e8906473 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4315-192.jpg | 23388 | - | b40daa8ec4d4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4315-256.jpg | 40612 | - | f88a608359dc | JPEG
v7-1-positive-crop-trimed-5min.mp4-4315-384.jpg | 89656 | - | 373850b1bb7f | JPEG
v7-1-positive-crop-trimed-5min.mp4-4318-192.jpg | 23083 | - | eb7d57436247 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4318-256.jpg | 40144 | - | 1981a4297d27 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4318-384.jpg | 89556 | - | a95a656bd35b | JPEG
v7-1-positive-crop-trimed-5min.mp4-4321-192.jpg | 22709 | - | 3a128588cc6e | JPEG
v7-1-positive-crop-trimed-5min.mp4-4321-256.jpg | 39431 | - | 42680ad8b3f1 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4321-384.jpg | 89457 | - | 395e4495dcdc | JPEG
v7-1-positive-crop-trimed-5min.mp4-4665-192.jpg | 27391 | - | 97e07b0f6f1d | JPEG
v7-1-positive-crop-trimed-5min.mp4-4665-256.jpg | 47333 | - | bf377e747d3c | JPEG
v7-1-positive-crop-trimed-5min.mp4-4665-384.jpg | 104081 | - | 8574f9df68da | JPEG
v7-1-positive-crop-trimed-5min.mp4-4670-192.jpg | 27527 | - | a1cec5761fa9 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4670-256.jpg | 47668 | - | 18187b4b68f2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4670-384.jpg | 104362 | - | 007dad6e4e74 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4675-192.jpg | 27500 | - | 7a493c7702e4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4675-256.jpg | 48009 | - | 2b1baa041267 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4675-384.jpg | 105263 | - | 3e4384929658 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4680-192.jpg | 27372 | - | 59298817eaa7 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4680-256.jpg | 47627 | - | ab743c56df84 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4680-384.jpg | 105056 | - | ecf5bcb5e160 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4685-192.jpg | 27260 | - | 46a749bc2e7b | JPEG
v7-1-positive-crop-trimed-5min.mp4-4685-256.jpg | 47648 | - | 38fef9d8c0d6 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4685-384.jpg | 104767 | - | 71570be564fc | JPEG
v7-1-positive-crop-trimed-5min.mp4-4690-192.jpg | 27002 | - | 2eb71dd5c1e4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4690-256.jpg | 47286 | - | 14727b01c3ad | JPEG
v7-1-positive-crop-trimed-5min.mp4-4690-384.jpg | 104027 | - | dad5ffe8aa56 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4695-192.jpg | 27185 | - | dff0d5d96839 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4695-256.jpg | 47528 | - | c20694a9e218 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4695-384.jpg | 104136 | - | 5be06c14835a | JPEG
v7-1-positive-crop-trimed-5min.mp4-5-192.jpg | 23294 | - | 15b5430546e8 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5-256.jpg | 41865 | - | 389e03321fe2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5-384.jpg | 88689 | - | 18af621ab415 | JPEG
v7-1-positive-crop-trimed-5min.mp4-50-192.jpg | 21013 | - | 36187764f60b | JPEG
v7-1-positive-crop-trimed-5min.mp4-50-256.jpg | 38119 | - | a8f3d23476df | JPEG
v7-1-positive-crop-trimed-5min.mp4-50-384.jpg | 91674 | - | fecec41ceba8 | JPEG
v7-1-positive-crop-trimed-5min.mp4-55-192.jpg | 21161 | - | 46f3e1d6c139 | JPEG
v7-1-positive-crop-trimed-5min.mp4-55-256.jpg | 38298 | - | 5ef874c2577d | JPEG
v7-1-positive-crop-trimed-5min.mp4-55-384.jpg | 91428 | - | 0d09f42f9f4d | JPEG
v7-1-positive-crop-trimed-5min.mp4-5920-192.jpg | 26010 | - | 360f1f5e017d | JPEG
v7-1-positive-crop-trimed-5min.mp4-5920-256.jpg | 45115 | - | 194f1a932a5f | JPEG
v7-1-positive-crop-trimed-5min.mp4-5920-384.jpg | 99151 | - | 24b346c983a9 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5945-192.jpg | 20787 | - | 8915e9ff2fdd | JPEG
v7-1-positive-crop-trimed-5min.mp4-5945-256.jpg | 38110 | - | a91d2ae4f6b9 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5945-384.jpg | 86510 | - | 315120fb2087 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5950-192.jpg | 24635 | - | 3cc007fa0c88 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5950-256.jpg | 43218 | - | 7d289b42b477 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5950-384.jpg | 96266 | - | a577f41e3909 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5965-192.jpg | 24280 | - | 6e2b189e2251 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5965-256.jpg | 42533 | - | 6e38d09c8583 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5965-384.jpg | 95583 | - | 627946757882 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5970-192.jpg | 23945 | - | 0f903aabb9c1 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5970-256.jpg | 42066 | - | 673420d48508 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5970-384.jpg | 94751 | - | bb4190368e39 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5975-192.jpg | 23641 | - | 422a0c573aad | JPEG
v7-1-positive-crop-trimed-5min.mp4-5975-256.jpg | 41211 | - | 4a95f9cd0c21 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5975-384.jpg | 93389 | - | 731515bab321 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5980-192.jpg | 23516 | - | 115f08555e67 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5980-256.jpg | 41019 | - | 9396569c8c60 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5980-384.jpg | 92203 | - | 068cd8d9425c | JPEG
v7-1-positive-crop-trimed-5min.mp4-60-192.jpg | 23591 | - | 7d3206820bcd | JPEG
v7-1-positive-crop-trimed-5min.mp4-60-256.jpg | 42697 | - | 143402ab3101 | JPEG
v7-1-positive-crop-trimed-5min.mp4-60-384.jpg | 94191 | - | 4e3a3abdd614 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6110-192.jpg | 19972 | - | 7311dce4cb5a | JPEG
v7-1-positive-crop-trimed-5min.mp4-6110-256.jpg | 31601 | - | 59ce61dc9cda | JPEG
v7-1-positive-crop-trimed-5min.mp4-6110-384.jpg | 61668 | - | 71ffe4727e42 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6115-192.jpg | 18658 | - | 179294c1c844 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6115-256.jpg | 30219 | - | 056b5df52584 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6115-384.jpg | 59376 | - | c8d65052b3c0 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6120-192.jpg | 19328 | - | 2e3e9659d621 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6120-256.jpg | 31179 | - | 82d713d5dd06 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6120-384.jpg | 59852 | - | 61387329450f | JPEG
v7-1-positive-crop-trimed-5min.mp4-6125-192.jpg | 18212 | - | 35e7d034cf31 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6125-256.jpg | 30382 | - | 9091255579cc | JPEG
v7-1-positive-crop-trimed-5min.mp4-6125-384.jpg | 62742 | - | 46d7c27ac946 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6135-192.jpg | 23778 | - | 5d4fd291318c | JPEG
v7-1-positive-crop-trimed-5min.mp4-6135-256.jpg | 41641 | - | 97b9319290c9 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6135-384.jpg | 85115 | - | c459b76fdd32 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6140-192.jpg | 23296 | - | 3ba900340242 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6140-256.jpg | 41296 | - | a118ad5297d2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6140-384.jpg | 92883 | - | 45fa102f322c | JPEG
v7-1-positive-crop-trimed-5min.mp4-6145-192.jpg | 24361 | - | a5246e9f1673 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6145-256.jpg | 41271 | - | e0ea56358f34 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6145-384.jpg | 90649 | - | 2d93eb44bb1e | JPEG
v7-1-positive-crop-trimed-5min.mp4-6150-192.jpg | 22677 | - | d2e3075aef45 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6150-256.jpg | 41449 | - | fab10f1eb6b0 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6150-384.jpg | 89771 | - | cea12dc6098e | JPEG
v7-1-positive-crop-trimed-5min.mp4-6155-192.jpg | 23645 | - | d1f2400d82ca | JPEG
v7-1-positive-crop-trimed-5min.mp4-6155-256.jpg | 41979 | - | 89cbaaac8984 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6155-384.jpg | 86961 | - | 3bdeb6cc76be | JPEG
v7-1-positive-crop-trimed-5min.mp4-6160-192.jpg | 24032 | - | 5342744c1e55 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6160-256.jpg | 42313 | - | dca097829bb6 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6160-384.jpg | 93683 | - | 8b4e23f424e6 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6165-192.jpg | 23940 | - | 690ce2141034 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6165-256.jpg | 41237 | - | 7ecc8ef3873a | JPEG
v7-1-positive-crop-trimed-5min.mp4-6165-384.jpg | 91783 | - | ab144599f992 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6170-192.jpg | 24204 | - | ff3041ec3c90 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6170-256.jpg | 41885 | - | f8bda3f4754d | JPEG
v7-1-positive-crop-trimed-5min.mp4-6170-384.jpg | 92941 | - | 4bce3eaf2774 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6175-192.jpg | 24255 | - | 65424c10f76a | JPEG
v7-1-positive-crop-trimed-5min.mp4-6175-256.jpg | 42280 | - | 0aa58f835c7b | JPEG
v7-1-positive-crop-trimed-5min.mp4-6175-384.jpg | 94802 | - | 7bd19d8b0ad2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6180-192.jpg | 24753 | - | 9964a072b9f4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6180-256.jpg | 42534 | - | b576dd0c10cb | JPEG
v7-1-positive-crop-trimed-5min.mp4-6180-384.jpg | 85277 | - | cdc90de9c2d8 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6185-192.jpg | 24923 | - | 43e07df38941 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6185-256.jpg | 43411 | - | f861320a23c9 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6185-384.jpg | 88009 | - | 3376427126e3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6190-192.jpg | 24944 | - | 6116a04fe1ac | JPEG
v7-1-positive-crop-trimed-5min.mp4-6190-256.jpg | 44146 | - | fde574613557 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6190-384.jpg | 98265 | - | a9734bcef381 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6195-192.jpg | 25732 | - | 9f41bd24f163 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6195-256.jpg | 45551 | - | 988720cd33dc | JPEG
v7-1-positive-crop-trimed-5min.mp4-6195-384.jpg | 101214 | - | ee0ef67614a1 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6200-192.jpg | 25341 | - | 3bcd97a4f379 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6200-256.jpg | 44265 | - | 69740a9e5e05 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6200-384.jpg | 100091 | - | 7e3820694466 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6205-192.jpg | 25366 | - | dc81d5f50d64 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6205-256.jpg | 44168 | - | df4f4c1831af | JPEG
v7-1-positive-crop-trimed-5min.mp4-6205-384.jpg | 98518 | - | 9b5917dc95db | JPEG
v7-1-positive-crop-trimed-5min.mp4-6210-192.jpg | 25575 | - | 0cbbd3842d8a | JPEG
v7-1-positive-crop-trimed-5min.mp4-6210-256.jpg | 44928 | - | e8a68d343b26 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6210-384.jpg | 99956 | - | e585aa43f6ab | JPEG
v7-1-positive-crop-trimed-5min.mp4-6215-192.jpg | 26244 | - | 6dd03d07190e | JPEG
v7-1-positive-crop-trimed-5min.mp4-6215-256.jpg | 45843 | - | e749ca3a2dc5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6215-384.jpg | 100916 | - | c441785dc070 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6220-192.jpg | 25963 | - | 6fe8234d00e9 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6220-256.jpg | 45359 | - | e38c3fa59cf2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6220-384.jpg | 100987 | - | d36b8f743fc4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6225-192.jpg | 25751 | - | 0445b8acc732 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6225-256.jpg | 45141 | - | afb228fc1885 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6225-384.jpg | 99424 | - | d01f6f6f1da4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6230-192.jpg | 24773 | - | af9c5645eaac | JPEG
v7-1-positive-crop-trimed-5min.mp4-6230-256.jpg | 43030 | - | 4ae753f1442e | JPEG
v7-1-positive-crop-trimed-5min.mp4-6230-384.jpg | 95231 | - | 436d07689c17 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6892-192.jpg | 21835 | - | e0675418998e | JPEG
v7-1-positive-crop-trimed-5min.mp4-6892-256.jpg | 39442 | - | d544789e6203 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6892-384.jpg | 91593 | - | 9c2fa7a58773 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6960-192.jpg | 22917 | - | 2efbdf391277 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6960-256.jpg | 40492 | - | 30117f260dae | JPEG
v7-1-positive-crop-trimed-5min.mp4-6960-384.jpg | 91061 | - | 6056f4f40d77 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6963-192.jpg | 23618 | - | 02f88fafe658 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6963-256.jpg | 40995 | - | 6decb7a008b2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6963-384.jpg | 91890 | - | 7f2d5335967f | JPEG
v7-1-positive-crop-trimed-5min.mp4-7099-192.jpg | 21444 | - | 6690e40a3fb5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7099-256.jpg | 36704 | - | 2ad16fa63e9e | JPEG
v7-1-positive-crop-trimed-5min.mp4-7099-384.jpg | 80471 | - | 7ed9a382de00 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7102-192.jpg | 21400 | - | ae2e4b38d2cb | JPEG
v7-1-positive-crop-trimed-5min.mp4-7102-256.jpg | 36564 | - | 30f75bc0a793 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7102-384.jpg | 79287 | - | d8f52ac5df94 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7105-192.jpg | 21396 | - | 8b6a1f3aa11c | JPEG
v7-1-positive-crop-trimed-5min.mp4-7105-256.jpg | 37054 | - | a391355a223a | JPEG
v7-1-positive-crop-trimed-5min.mp4-7105-384.jpg | 79367 | - | d14b0e1bae97 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7170-192.jpg | 23424 | - | 8124e4f2ce25 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7170-256.jpg | 40019 | - | c94087535086 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7170-384.jpg | 88050 | - | 61343c7f2c71 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7173-192.jpg | 23029 | - | 4d15003d294d | JPEG
v7-1-positive-crop-trimed-5min.mp4-7173-256.jpg | 39950 | - | 006baf39ece5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7173-384.jpg | 88391 | - | c2fcbeb9d6bd | JPEG
v7-1-positive-crop-trimed-5min.mp4-7176-192.jpg | 21163 | - | 92e220f14946 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7176-256.jpg | 37832 | - | dc02c0ff5b38 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7176-384.jpg | 86405 | - | ce54d7cc7e5d | JPEG
v7-1-positive-crop-trimed-5min.mp4-7315-192.jpg | 20184 | - | d51f067b9793 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7315-256.jpg | 37472 | - | 0b355fc3de12 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7315-384.jpg | 87101 | - | 4a5b93f2e05f | JPEG
v7-1-positive-crop-trimed-5min.mp4-7318-192.jpg | 20998 | - | 9e04119ed006 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7318-256.jpg | 37941 | - | 48c047bebdc4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7318-384.jpg | 88239 | - | fb9bd3faf1df | JPEG
v7-1-positive-crop-trimed-5min.mp4-7457-192.jpg | 20295 | - | 1f2f507e07ff | JPEG
v7-1-positive-crop-trimed-5min.mp4-7457-256.jpg | 36378 | - | 3dee1041d7fc | JPEG
v7-1-positive-crop-trimed-5min.mp4-7457-384.jpg | 86656 | - | 3230f78f9406 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7460-192.jpg | 20198 | - | cb9b94b7ea39 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7460-256.jpg | 36079 | - | 9ddfc0e25be2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7460-384.jpg | 86147 | - | 37ec76a33b13 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7463-192.jpg | 20210 | - | 8e94a7378a19 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7463-256.jpg | 35996 | - | 913c3a702603 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7463-384.jpg | 86067 | - | 01a11d1aee5d | JPEG
v7-1-positive-crop-trimed-5min.mp4-7528-192.jpg | 20547 | - | 6f9bb45e792d | JPEG
v7-1-positive-crop-trimed-5min.mp4-7528-256.jpg | 36374 | - | f4529b4fc008 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7528-384.jpg | 84900 | - | 091f34a31fcc | JPEG
v7-1-positive-crop-trimed-5min.mp4-7531-192.jpg | 20359 | - | 5079f63defb4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7531-256.jpg | 35882 | - | b57b94d2d9c6 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7531-384.jpg | 83775 | - | 78573e86869e | JPEG
v7-1-positive-crop-trimed-5min.mp4-7534-192.jpg | 20399 | - | 63c8e8e790dc | JPEG
v7-1-positive-crop-trimed-5min.mp4-7534-256.jpg | 35874 | - | e37daef9ad40 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7534-384.jpg | 84018 | - | f030ba093682 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7579-192.jpg | 19819 | - | 22c7263cf2b5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7579-256.jpg | 34576 | - | 8f2d8bda099f | JPEG
v7-1-positive-crop-trimed-5min.mp4-7579-384.jpg | 85426 | - | 754dcd38f057 | JPEG
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_crop_probe_precision_guardrail_audit_v1/audit_dataset_snapshot/images/val

```text
basename | bytes | lines | sha256-prefix | inspection
v7-1-hard-negative-top-left-1150-46.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1175-47.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1450-58.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1475-59.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1750-70.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1775-71.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2050-82.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2075-83.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2350-94.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2375-95.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-250-10.jpg | 1407 | - | 3d45f26c1a77 | JPEG
v7-1-hard-negative-top-left-2650-106.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2675-107.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-275-11.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-2950-118.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-2975-119.jpg | 1407 | - | c2f2ce425a97 | JPEG
v7-1-hard-negative-top-left-3250-130.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3275-131.jpg | 1407 | - | 248674746bdc | JPEG
v7-1-hard-negative-top-left-3550-142.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3575-143.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3850-154.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-3875-155.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4150-166.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4175-167.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4450-178.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4475-179.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-550-22.jpg | 1407 | - | 73e1a8c8f323 | JPEG
v7-1-hard-negative-top-left-575-23.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-850-34.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-875-35.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2386-192.jpg | 21914 | - | c2e160e31d59 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2386-256.jpg | 38006 | - | 3db73e73c1a7 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2386-384.jpg | 86661 | - | 0e8c272a6553 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2392-192.jpg | 21395 | - | 349e5376c687 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2392-256.jpg | 37861 | - | b50a0f43f157 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2392-384.jpg | 85465 | - | 3d22f65e9a8d | JPEG
v7-1-positive-crop-trimed-5min.mp4-240-192.jpg | 23224 | - | 0605773b2238 | JPEG
v7-1-positive-crop-trimed-5min.mp4-240-256.jpg | 41667 | - | 23a06cf607b5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-240-384.jpg | 86651 | - | e8a440e49c75 | JPEG
v7-1-positive-crop-trimed-5min.mp4-245-192.jpg | 23372 | - | 7f95f524a384 | JPEG
v7-1-positive-crop-trimed-5min.mp4-245-256.jpg | 41963 | - | a4fc9a3f880c | JPEG
v7-1-positive-crop-trimed-5min.mp4-245-384.jpg | 88386 | - | 95a3d54019cc | JPEG
v7-1-positive-crop-trimed-5min.mp4-250-192.jpg | 23099 | - | 2cd8f503c934 | JPEG
v7-1-positive-crop-trimed-5min.mp4-250-256.jpg | 41333 | - | fb6b06571fde | JPEG
v7-1-positive-crop-trimed-5min.mp4-250-384.jpg | 89558 | - | c785deb6282c | JPEG
v7-1-positive-crop-trimed-5min.mp4-260-192.jpg | 23443 | - | d3dbe7b499a6 | JPEG
v7-1-positive-crop-trimed-5min.mp4-260-256.jpg | 41304 | - | 617714662f77 | JPEG
v7-1-positive-crop-trimed-5min.mp4-260-384.jpg | 91478 | - | 8cbd4853b1bf | JPEG
v7-1-positive-crop-trimed-5min.mp4-2670-192.jpg | 21709 | - | a62f22678a36 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2670-256.jpg | 37969 | - | 1c5b36fa4bdd | JPEG
v7-1-positive-crop-trimed-5min.mp4-2670-384.jpg | 90216 | - | 22aa5884b896 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2673-192.jpg | 21005 | - | 759215dee518 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2673-256.jpg | 38030 | - | b281e016d5f4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2673-384.jpg | 90993 | - | 7eb81ddef1bc | JPEG
v7-1-positive-crop-trimed-5min.mp4-2676-192.jpg | 20924 | - | ba4316a46949 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2676-256.jpg | 38010 | - | 1b7ea4941d84 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2676-384.jpg | 92344 | - | daa5b8b7b6ca | JPEG
v7-1-positive-crop-trimed-5min.mp4-275-192.jpg | 23707 | - | 274e44387512 | JPEG
v7-1-positive-crop-trimed-5min.mp4-275-256.jpg | 42092 | - | c14075dee061 | JPEG
v7-1-positive-crop-trimed-5min.mp4-275-384.jpg | 95863 | - | 89f761a1ce00 | JPEG
v7-1-positive-crop-trimed-5min.mp4-280-192.jpg | 23711 | - | 5f403b279275 | JPEG
v7-1-positive-crop-trimed-5min.mp4-280-256.jpg | 42039 | - | 113a038f6f73 | JPEG
v7-1-positive-crop-trimed-5min.mp4-280-384.jpg | 95531 | - | 7776d8e75e6f | JPEG
v7-1-positive-crop-trimed-5min.mp4-290-192.jpg | 23204 | - | e90b3155ff13 | JPEG
v7-1-positive-crop-trimed-5min.mp4-290-256.jpg | 42043 | - | 18d265f9f5f0 | JPEG
v7-1-positive-crop-trimed-5min.mp4-290-384.jpg | 96833 | - | 7afaea6ecef0 | JPEG
v7-1-positive-crop-trimed-5min.mp4-295-192.jpg | 23973 | - | 5407de13a14f | JPEG
v7-1-positive-crop-trimed-5min.mp4-295-256.jpg | 43594 | - | d434360b1770 | JPEG
v7-1-positive-crop-trimed-5min.mp4-295-384.jpg | 96376 | - | 601bda1e3c36 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4170-192.jpg | 23217 | - | 220fb0660ce0 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4170-256.jpg | 39732 | - | 37f525ea91c8 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4170-384.jpg | 89897 | - | ac439862e409 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4173-192.jpg | 23707 | - | 5d26ce0b8619 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4173-256.jpg | 41033 | - | 13b8d431e084 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4173-384.jpg | 91486 | - | 4579f1fe9058 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4176-192.jpg | 24932 | - | 46badd5813af | JPEG
v7-1-positive-crop-trimed-5min.mp4-4176-256.jpg | 42976 | - | 0bac115149e5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4176-384.jpg | 91295 | - | 1bfd85539235 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4457-192.jpg | 21649 | - | 8e67b09a1c34 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4457-256.jpg | 38166 | - | 63fd89a7a196 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4457-384.jpg | 89114 | - | 62ca3d46af2f | JPEG
v7-1-positive-crop-trimed-5min.mp4-4460-192.jpg | 20474 | - | 01ed92be7887 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4460-256.jpg | 37520 | - | d21d516e06bc | JPEG
v7-1-positive-crop-trimed-5min.mp4-4460-384.jpg | 88859 | - | 8d920adc1453 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4463-192.jpg | 20054 | - | bd2ef6b649c2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4463-256.jpg | 36962 | - | 981e82c06405 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4463-384.jpg | 89039 | - | 66c1ef1a376f | JPEG
v7-1-positive-crop-trimed-5min.mp4-6005-192.jpg | 23163 | - | af80de9063d7 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6005-256.jpg | 39906 | - | 3525f09198b3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6005-384.jpg | 89039 | - | 10368e6acca4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6010-192.jpg | 23254 | - | 6ee968f6eca8 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6010-256.jpg | 39924 | - | d6f77bf036ab | JPEG
v7-1-positive-crop-trimed-5min.mp4-6010-384.jpg | 89084 | - | 6686c9e7fdca | JPEG
v7-1-positive-crop-trimed-5min.mp4-6957-192.jpg | 22643 | - | 3f6a30a754e2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6957-256.jpg | 40421 | - | f5e7f822f64a | JPEG
v7-1-positive-crop-trimed-5min.mp4-6957-384.jpg | 91143 | - | dc4916a2c27e | JPEG
v7-1-positive-crop-trimed-5min.mp4-7321-192.jpg | 21486 | - | 09e73f2b9a0e | JPEG
v7-1-positive-crop-trimed-5min.mp4-7321-256.jpg | 38066 | - | 261ef40a06f2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7321-384.jpg | 88613 | - | 435ca98d4a2e | JPEG
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_crop_probe_precision_guardrail_audit_v1/audit_dataset_snapshot/labels/canary

```text
basename | bytes | lines | sha256-prefix | inspection
v7-1-hard-negative-top-left-4500-180.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4525-181.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4550-182.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4575-183.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4600-184.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4625-185.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4650-186.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4675-187.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4700-188.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4725-189.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4750-190.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4775-191.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4800-192.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4825-193.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4850-194.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4875-195.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4900-196.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4925-197.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4950-198.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4975-199.txt | 0 | 0 | e3b0c44298fc | TEXT
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_crop_probe_precision_guardrail_audit_v1/audit_dataset_snapshot/labels/train

```text
basename | bytes | lines | sha256-prefix | inspection
v7-1-hard-negative-top-left-0-0.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-100-4.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1000-40.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1025-41.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1050-42.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1075-43.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1100-44.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1125-45.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1200-48.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1225-49.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-125-5.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1250-50.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1275-51.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1300-52.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1325-53.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1350-54.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1375-55.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1400-56.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1425-57.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-150-6.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1500-60.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1525-61.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1550-62.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1575-63.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1600-64.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1625-65.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1650-66.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1675-67.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1700-68.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1725-69.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-175-7.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1800-72.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1825-73.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1850-74.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1875-75.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1900-76.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1925-77.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1950-78.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1975-79.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-200-8.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2000-80.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2025-81.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2100-84.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2125-85.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2150-86.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2175-87.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2200-88.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2225-89.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-225-9.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2250-90.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2275-91.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2300-92.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2325-93.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2400-96.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2425-97.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2450-98.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2475-99.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-25-1.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2500-100.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2525-101.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2550-102.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2575-103.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2600-104.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2625-105.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2700-108.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2725-109.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2750-110.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2775-111.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2800-112.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2825-113.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2850-114.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2875-115.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2900-116.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2925-117.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-300-12.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3000-120.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3025-121.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3050-122.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3075-123.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3100-124.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3125-125.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3150-126.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3175-127.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3200-128.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3225-129.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-325-13.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3300-132.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3325-133.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3350-134.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3375-135.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3400-136.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3425-137.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3450-138.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3475-139.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-350-14.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3500-140.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3525-141.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3600-144.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3625-145.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3650-146.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3675-147.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3700-148.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3725-149.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-375-15.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3750-150.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3775-151.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3800-152.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3825-153.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3900-156.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3925-157.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3950-158.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3975-159.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-400-16.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4000-160.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4025-161.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4050-162.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4075-163.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4100-164.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4125-165.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4200-168.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4225-169.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-425-17.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4250-170.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4275-171.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4300-172.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4325-173.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4350-174.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4375-175.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4400-176.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4425-177.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-450-18.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-475-19.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-50-2.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-500-20.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-525-21.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-600-24.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-625-25.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-650-26.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-675-27.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-700-28.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-725-29.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-75-3.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-750-30.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-775-31.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-800-32.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-825-33.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-900-36.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-925-37.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-950-38.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-975-39.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-positive-crop-trimed-5min.mp4-125-192.txt | 46 | 1 | f01178699dcc | TEXT
v7-1-positive-crop-trimed-5min.mp4-125-256.txt | 46 | 1 | a2549d904591 | TEXT
v7-1-positive-crop-trimed-5min.mp4-125-384.txt | 46 | 1 | ec03264d1586 | TEXT
v7-1-positive-crop-trimed-5min.mp4-130-192.txt | 46 | 1 | 35f97f79179b | TEXT
v7-1-positive-crop-trimed-5min.mp4-130-256.txt | 46 | 1 | 980a547161cb | TEXT
v7-1-positive-crop-trimed-5min.mp4-130-384.txt | 46 | 1 | d69ecf57c9c3 | TEXT
v7-1-positive-crop-trimed-5min.mp4-135-192.txt | 46 | 1 | 493cc3155c84 | TEXT
v7-1-positive-crop-trimed-5min.mp4-135-256.txt | 46 | 1 | 4495ff564d37 | TEXT
v7-1-positive-crop-trimed-5min.mp4-135-384.txt | 46 | 1 | 008b49ae7b13 | TEXT
v7-1-positive-crop-trimed-5min.mp4-140-192.txt | 46 | 1 | d21c9ac1d314 | TEXT
v7-1-positive-crop-trimed-5min.mp4-140-256.txt | 46 | 1 | e144ee2b762d | TEXT
v7-1-positive-crop-trimed-5min.mp4-140-384.txt | 46 | 1 | 3053af3f2a9c | TEXT
v7-1-positive-crop-trimed-5min.mp4-1815-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-1815-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-1815-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-195-192.txt | 46 | 1 | 493cc3155c84 | TEXT
v7-1-positive-crop-trimed-5min.mp4-195-256.txt | 46 | 1 | 4495ff564d37 | TEXT
v7-1-positive-crop-trimed-5min.mp4-195-384.txt | 46 | 1 | 008b49ae7b13 | TEXT
v7-1-positive-crop-trimed-5min.mp4-210-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-210-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-210-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-220-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-220-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-220-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-225-192.txt | 46 | 1 | f1ce88b9fd79 | TEXT
v7-1-positive-crop-trimed-5min.mp4-225-256.txt | 46 | 1 | bfb941c2e0f7 | TEXT
v7-1-positive-crop-trimed-5min.mp4-225-384.txt | 46 | 1 | 5a4310422215 | TEXT
v7-1-positive-crop-trimed-5min.mp4-230-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-230-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-230-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-235-192.txt | 46 | 1 | f1ce88b9fd79 | TEXT
v7-1-positive-crop-trimed-5min.mp4-235-256.txt | 46 | 1 | bfb941c2e0f7 | TEXT
v7-1-positive-crop-trimed-5min.mp4-235-384.txt | 46 | 1 | 5a4310422215 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2457-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2457-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2457-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2460-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2460-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2460-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2463-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2463-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2463-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2528-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2528-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2528-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2531-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2531-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2531-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2534-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2534-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2534-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2886-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2886-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2886-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2889-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2889-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2889-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2892-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2892-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2892-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-300-192.txt | 46 | 1 | 4219f8b4b148 | TEXT
v7-1-positive-crop-trimed-5min.mp4-300-256.txt | 46 | 1 | 216df81d3d4d | TEXT
v7-1-positive-crop-trimed-5min.mp4-300-384.txt | 46 | 1 | 395aca61096d | TEXT
v7-1-positive-crop-trimed-5min.mp4-305-192.txt | 46 | 1 | 9dcb3d67f47f | TEXT
v7-1-positive-crop-trimed-5min.mp4-305-256.txt | 46 | 1 | 801623bb0d92 | TEXT
v7-1-positive-crop-trimed-5min.mp4-305-384.txt | 46 | 1 | a8ab4e7f417c | TEXT
v7-1-positive-crop-trimed-5min.mp4-310-192.txt | 46 | 1 | 4219f8b4b148 | TEXT
v7-1-positive-crop-trimed-5min.mp4-310-256.txt | 46 | 1 | 216df81d3d4d | TEXT
v7-1-positive-crop-trimed-5min.mp4-310-384.txt | 46 | 1 | 395aca61096d | TEXT
v7-1-positive-crop-trimed-5min.mp4-315-192.txt | 46 | 1 | 9dcb3d67f47f | TEXT
v7-1-positive-crop-trimed-5min.mp4-315-256.txt | 46 | 1 | 801623bb0d92 | TEXT
v7-1-positive-crop-trimed-5min.mp4-315-384.txt | 46 | 1 | 70dcbf0a02db | TEXT
v7-1-positive-crop-trimed-5min.mp4-320-192.txt | 46 | 1 | 4219f8b4b148 | TEXT
v7-1-positive-crop-trimed-5min.mp4-320-256.txt | 46 | 1 | 216df81d3d4d | TEXT
v7-1-positive-crop-trimed-5min.mp4-320-384.txt | 46 | 1 | 8853e221657d | TEXT
v7-1-positive-crop-trimed-5min.mp4-325-192.txt | 46 | 1 | 9dcb3d67f47f | TEXT
v7-1-positive-crop-trimed-5min.mp4-325-256.txt | 46 | 1 | 801623bb0d92 | TEXT
v7-1-positive-crop-trimed-5min.mp4-325-384.txt | 46 | 1 | a8ab4e7f417c | TEXT
v7-1-positive-crop-trimed-5min.mp4-330-192.txt | 46 | 1 | 89e3fd4d012a | TEXT
v7-1-positive-crop-trimed-5min.mp4-330-256.txt | 46 | 1 | df22fc1d2902 | TEXT
v7-1-positive-crop-trimed-5min.mp4-330-384.txt | 46 | 1 | 7acc6be8e3f0 | TEXT
v7-1-positive-crop-trimed-5min.mp4-335-192.txt | 46 | 1 | f01178699dcc | TEXT
v7-1-positive-crop-trimed-5min.mp4-335-256.txt | 46 | 1 | a2549d904591 | TEXT
v7-1-positive-crop-trimed-5min.mp4-335-384.txt | 46 | 1 | ec03264d1586 | TEXT
v7-1-positive-crop-trimed-5min.mp4-340-192.txt | 46 | 1 | 35f97f79179b | TEXT
v7-1-positive-crop-trimed-5min.mp4-340-256.txt | 46 | 1 | 980a547161cb | TEXT
v7-1-positive-crop-trimed-5min.mp4-340-384.txt | 46 | 1 | d69ecf57c9c3 | TEXT
v7-1-positive-crop-trimed-5min.mp4-345-192.txt | 46 | 1 | 493cc3155c84 | TEXT
v7-1-positive-crop-trimed-5min.mp4-345-256.txt | 46 | 1 | 4495ff564d37 | TEXT
v7-1-positive-crop-trimed-5min.mp4-345-384.txt | 46 | 1 | 008b49ae7b13 | TEXT
v7-1-positive-crop-trimed-5min.mp4-350-192.txt | 46 | 1 | d21c9ac1d314 | TEXT
v7-1-positive-crop-trimed-5min.mp4-350-256.txt | 46 | 1 | e144ee2b762d | TEXT
v7-1-positive-crop-trimed-5min.mp4-350-384.txt | 46 | 1 | 3053af3f2a9c | TEXT
v7-1-positive-crop-trimed-5min.mp4-355-192.txt | 46 | 1 | d8713f055b33 | TEXT
v7-1-positive-crop-trimed-5min.mp4-355-256.txt | 46 | 1 | eb04fc2545dc | TEXT
v7-1-positive-crop-trimed-5min.mp4-355-384.txt | 46 | 1 | dc37df8bc73f | TEXT
v7-1-positive-crop-trimed-5min.mp4-360-192.txt | 46 | 1 | d8713f055b33 | TEXT
v7-1-positive-crop-trimed-5min.mp4-360-256.txt | 46 | 1 | eb04fc2545dc | TEXT
v7-1-positive-crop-trimed-5min.mp4-360-384.txt | 46 | 1 | dc37df8bc73f | TEXT
v7-1-positive-crop-trimed-5min.mp4-3602-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3602-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3602-384.txt | 46 | 1 | 7f895c7ba26a | TEXT
v7-1-positive-crop-trimed-5min.mp4-3605-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3605-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3605-384.txt | 46 | 1 | df78bf8a76bb | TEXT
v7-1-positive-crop-trimed-5min.mp4-365-192.txt | 46 | 1 | d8713f055b33 | TEXT
v7-1-positive-crop-trimed-5min.mp4-365-256.txt | 46 | 1 | eb04fc2545dc | TEXT
v7-1-positive-crop-trimed-5min.mp4-365-384.txt | 46 | 1 | dc37df8bc73f | TEXT
v7-1-positive-crop-trimed-5min.mp4-3670-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3670-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3670-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-3673-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3673-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3673-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-3676-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3676-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3676-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-370-192.txt | 46 | 1 | d8713f055b33 | TEXT
v7-1-positive-crop-trimed-5min.mp4-370-256.txt | 46 | 1 | eb04fc2545dc | TEXT
v7-1-positive-crop-trimed-5min.mp4-370-384.txt | 46 | 1 | dc37df8bc73f | TEXT
v7-1-positive-crop-trimed-5min.mp4-3744-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3744-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3744-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-3747-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3747-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3747-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-375-192.txt | 46 | 1 | d8713f055b33 | TEXT
v7-1-positive-crop-trimed-5min.mp4-375-256.txt | 46 | 1 | eb04fc2545dc | TEXT
v7-1-positive-crop-trimed-5min.mp4-375-384.txt | 46 | 1 | dc37df8bc73f | TEXT
v7-1-positive-crop-trimed-5min.mp4-3750-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3750-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3750-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-3821-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3821-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3821-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-3960-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3960-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3960-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-3963-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3963-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3963-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4099-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4099-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4099-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4102-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4102-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4102-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4105-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4105-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4105-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4247-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4247-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4247-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4250-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4250-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4250-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4315-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4315-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4315-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4318-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4318-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4318-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4321-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4321-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4321-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4665-192.txt | 46 | 1 | bb241df7e236 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4665-256.txt | 46 | 1 | 6525f724d01c | TEXT
v7-1-positive-crop-trimed-5min.mp4-4665-384.txt | 46 | 1 | b3d2ae2c0c5a | TEXT
v7-1-positive-crop-trimed-5min.mp4-4670-192.txt | 46 | 1 | 67017b5b9acb | TEXT
v7-1-positive-crop-trimed-5min.mp4-4670-256.txt | 46 | 1 | 1283d6f187f1 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4670-384.txt | 46 | 1 | 0dabf71ae6b9 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4675-192.txt | 46 | 1 | bb241df7e236 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4675-256.txt | 46 | 1 | 6525f724d01c | TEXT
v7-1-positive-crop-trimed-5min.mp4-4675-384.txt | 46 | 1 | b3d2ae2c0c5a | TEXT
v7-1-positive-crop-trimed-5min.mp4-4680-192.txt | 46 | 1 | 67017b5b9acb | TEXT
v7-1-positive-crop-trimed-5min.mp4-4680-256.txt | 46 | 1 | 1283d6f187f1 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4680-384.txt | 46 | 1 | 0dabf71ae6b9 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4685-192.txt | 46 | 1 | 3f5b800bf10c | TEXT
v7-1-positive-crop-trimed-5min.mp4-4685-256.txt | 46 | 1 | 3626e81053f4 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4685-384.txt | 46 | 1 | b9f5262d5845 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4690-192.txt | 46 | 1 | 3481e7245ba6 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4690-256.txt | 46 | 1 | e6f50d8bc10a | TEXT
v7-1-positive-crop-trimed-5min.mp4-4690-384.txt | 46 | 1 | e751b11f1fe8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4695-192.txt | 46 | 1 | 12ebb6c8b369 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4695-256.txt | 46 | 1 | 292aa7fcd4da | TEXT
v7-1-positive-crop-trimed-5min.mp4-4695-384.txt | 46 | 1 | c091724be964 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5-192.txt | 46 | 1 | f1ce88b9fd79 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5-256.txt | 46 | 1 | bfb941c2e0f7 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5-384.txt | 46 | 1 | 5a4310422215 | TEXT
v7-1-positive-crop-trimed-5min.mp4-50-192.txt | 46 | 1 | 4219f8b4b148 | TEXT
v7-1-positive-crop-trimed-5min.mp4-50-256.txt | 46 | 1 | 216df81d3d4d | TEXT
v7-1-positive-crop-trimed-5min.mp4-50-384.txt | 46 | 1 | 395aca61096d | TEXT
v7-1-positive-crop-trimed-5min.mp4-55-192.txt | 46 | 1 | 9dcb3d67f47f | TEXT
v7-1-positive-crop-trimed-5min.mp4-55-256.txt | 46 | 1 | 801623bb0d92 | TEXT
v7-1-positive-crop-trimed-5min.mp4-55-384.txt | 46 | 1 | a8ab4e7f417c | TEXT
v7-1-positive-crop-trimed-5min.mp4-5920-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5920-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5920-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-5945-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5945-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5945-384.txt | 46 | 1 | 20a31e365aa0 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5950-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5950-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5950-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-5965-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5965-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5965-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-5970-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5970-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5970-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-5975-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5975-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5975-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-5980-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5980-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5980-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-60-192.txt | 46 | 1 | 89e3fd4d012a | TEXT
v7-1-positive-crop-trimed-5min.mp4-60-256.txt | 46 | 1 | df22fc1d2902 | TEXT
v7-1-positive-crop-trimed-5min.mp4-60-384.txt | 46 | 1 | 092506d7a208 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6110-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6110-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6110-384.txt | 46 | 1 | d65f988e2c6b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6115-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6115-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6115-384.txt | 46 | 1 | 01c5f904beb6 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6120-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6120-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6120-384.txt | 46 | 1 | 4e009442a968 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6125-192.txt | 46 | 1 | fab066afaaca | TEXT
v7-1-positive-crop-trimed-5min.mp4-6125-256.txt | 46 | 1 | 18c49173aed6 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6125-384.txt | 46 | 1 | cfb1b8c831ed | TEXT
v7-1-positive-crop-trimed-5min.mp4-6135-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6135-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6135-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6140-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6140-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6140-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6145-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6145-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6145-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6150-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6150-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6150-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6155-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6155-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6155-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6160-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6160-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6160-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6165-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6165-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6165-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6170-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6170-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6170-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6175-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6175-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6175-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6180-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6180-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6180-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6185-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6185-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6185-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6190-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6190-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6190-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6195-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6195-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6195-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6200-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6200-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6200-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6205-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6205-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6205-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6210-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6210-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6210-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6215-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6215-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6215-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6220-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6220-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6220-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6225-192.txt | 46 | 1 | d838216cbc7c | TEXT
v7-1-positive-crop-trimed-5min.mp4-6225-256.txt | 46 | 1 | 1ef540a5ef39 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6225-384.txt | 46 | 1 | ba2e02a1f88c | TEXT
v7-1-positive-crop-trimed-5min.mp4-6230-192.txt | 46 | 1 | 70d1cde32bd4 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6230-256.txt | 46 | 1 | d03151821eb7 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6230-384.txt | 46 | 1 | f073397e7172 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6892-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6892-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6892-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-6960-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6960-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6960-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-6963-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6963-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6963-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7099-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7099-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7099-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7102-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7102-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7102-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7105-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7105-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7105-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7170-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7170-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7170-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7173-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7173-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7173-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7176-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7176-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7176-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7315-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7315-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7315-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7318-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7318-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7318-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7457-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7457-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7457-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7460-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7460-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7460-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7463-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7463-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7463-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7528-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7528-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7528-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7531-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7531-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7531-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7534-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7534-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7534-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7579-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7579-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7579-384.txt | 46 | 1 | e035c36c63ea | TEXT
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_crop_probe_precision_guardrail_audit_v1/audit_dataset_snapshot/labels/val

```text
basename | bytes | lines | sha256-prefix | inspection
v7-1-hard-negative-top-left-1150-46.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1175-47.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1450-58.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1475-59.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1750-70.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1775-71.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2050-82.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2075-83.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2350-94.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2375-95.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-250-10.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2650-106.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2675-107.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-275-11.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2950-118.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2975-119.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3250-130.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3275-131.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3550-142.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3575-143.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3850-154.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3875-155.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4150-166.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4175-167.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4450-178.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4475-179.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-550-22.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-575-23.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-850-34.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-875-35.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-positive-crop-trimed-5min.mp4-2386-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2386-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2386-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2392-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2392-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2392-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-240-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-240-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-240-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-245-192.txt | 46 | 1 | f1ce88b9fd79 | TEXT
v7-1-positive-crop-trimed-5min.mp4-245-256.txt | 46 | 1 | bfb941c2e0f7 | TEXT
v7-1-positive-crop-trimed-5min.mp4-245-384.txt | 46 | 1 | 5a4310422215 | TEXT
v7-1-positive-crop-trimed-5min.mp4-250-192.txt | 46 | 1 | cad00e349fa6 | TEXT
v7-1-positive-crop-trimed-5min.mp4-250-256.txt | 46 | 1 | 466eb6125f7b | TEXT
v7-1-positive-crop-trimed-5min.mp4-250-384.txt | 46 | 1 | bb1baabc0c7c | TEXT
v7-1-positive-crop-trimed-5min.mp4-260-192.txt | 46 | 1 | fd51077cfdae | TEXT
v7-1-positive-crop-trimed-5min.mp4-260-256.txt | 46 | 1 | 908e247de6c4 | TEXT
v7-1-positive-crop-trimed-5min.mp4-260-384.txt | 46 | 1 | 579dbc1795c4 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2670-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2670-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2670-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2673-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2673-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2673-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2676-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2676-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2676-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-275-192.txt | 46 | 1 | f1ce88b9fd79 | TEXT
v7-1-positive-crop-trimed-5min.mp4-275-256.txt | 46 | 1 | bfb941c2e0f7 | TEXT
v7-1-positive-crop-trimed-5min.mp4-275-384.txt | 46 | 1 | 5a4310422215 | TEXT
v7-1-positive-crop-trimed-5min.mp4-280-192.txt | 46 | 1 | cad00e349fa6 | TEXT
v7-1-positive-crop-trimed-5min.mp4-280-256.txt | 46 | 1 | 466eb6125f7b | TEXT
v7-1-positive-crop-trimed-5min.mp4-280-384.txt | 46 | 1 | bb1baabc0c7c | TEXT
v7-1-positive-crop-trimed-5min.mp4-290-192.txt | 46 | 1 | fd51077cfdae | TEXT
v7-1-positive-crop-trimed-5min.mp4-290-256.txt | 46 | 1 | 908e247de6c4 | TEXT
v7-1-positive-crop-trimed-5min.mp4-290-384.txt | 46 | 1 | 579dbc1795c4 | TEXT
v7-1-positive-crop-trimed-5min.mp4-295-192.txt | 46 | 1 | f01178699dcc | TEXT
v7-1-positive-crop-trimed-5min.mp4-295-256.txt | 46 | 1 | a2549d904591 | TEXT
v7-1-positive-crop-trimed-5min.mp4-295-384.txt | 46 | 1 | ec03264d1586 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4170-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4170-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4170-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4173-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4173-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4173-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4176-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4176-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4176-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4457-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4457-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4457-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4460-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4460-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4460-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4463-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4463-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4463-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-6005-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6005-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6005-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6010-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6010-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6010-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6957-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6957-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6957-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7321-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7321-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7321-384.txt | 46 | 1 | e035c36c63ea | TEXT
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_export_label_overlay_audit_v1

```text
basename | bytes | lines | sha256-prefix | inspection
batch_outcome_analysis.json | 2072029 | 52450 | 52f887072216 | JSON
batch_outcome_analysis.md | 417 | 12 | e567efb3f0e9 | DOC
decision_matrix.json | 1159 | 45 | e684ebbedce0 | JSON
v7_2_crop_label_transform_audit.json | 580053 | 16158 | 47a624ab79f6 | JSON
v7_2_export_manifest_consistency_audit.json | 740580 | 18961 | d527de5a8ab2 | JSON
v7_2_label_overlay_audit.json | 1700 | 47 | 4e0a1142e7d0 | JSON
v7_2_overlay_contact_sheet_canary.jpg | 51029 | - | 81c2ff48fd4d | JPEG
v7_2_overlay_contact_sheet_negative.jpg | 153961 | - | 604df8d1eb26 | JPEG
v7_2_overlay_contact_sheet_positive.jpg | 8072570 | - | a707896449f5 | JPEG
v7_2_overlay_review_manifest.json | 644716 | 17282 | 10ae9cc02668 | JSON
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_export_label_overlay_audit_v1/v7_2_export_preview

```text
basename | bytes | lines | sha256-prefix | inspection
data.yaml | 228 | 6 | 8ef2a7238b50 | TEXT
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_export_label_overlay_audit_v1/v7_2_export_preview/images/canary

```text
basename | bytes | lines | sha256-prefix | inspection
v7-1-hard-negative-top-left-4500-180.jpg | 1407 | - | 3d45f26c1a77 | JPEG
v7-1-hard-negative-top-left-4525-181.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4550-182.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4575-183.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4600-184.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4625-185.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4650-186.jpg | 1407 | - | 3d45f26c1a77 | JPEG
v7-1-hard-negative-top-left-4675-187.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4700-188.jpg | 1407 | - | 3f4ee99d81ff | JPEG
v7-1-hard-negative-top-left-4725-189.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-4750-190.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4775-191.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4800-192.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-4825-193.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4850-194.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-4875-195.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-4900-196.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-4925-197.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-4950-198.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-4975-199.jpg | 1407 | - | 898be37f7ba4 | JPEG
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_export_label_overlay_audit_v1/v7_2_export_preview/images/train

```text
basename | bytes | lines | sha256-prefix | inspection
v7-1-hard-negative-top-left-0-0.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-100-4.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1000-40.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1025-41.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-1050-42.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1075-43.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1100-44.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1125-45.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1200-48.jpg | 1407 | - | 3d45f26c1a77 | JPEG
v7-1-hard-negative-top-left-1225-49.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-125-5.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-1250-50.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1275-51.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1300-52.jpg | 1407 | - | 3d45f26c1a77 | JPEG
v7-1-hard-negative-top-left-1325-53.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1350-54.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1375-55.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1400-56.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-1425-57.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-150-6.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-1500-60.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1525-61.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1550-62.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1575-63.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1600-64.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1625-65.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1650-66.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1675-67.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1700-68.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1725-69.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-175-7.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1800-72.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1825-73.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1850-74.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1875-75.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1900-76.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1925-77.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1950-78.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1975-79.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-200-8.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-2000-80.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2025-81.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2100-84.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-2125-85.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-2150-86.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-2175-87.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2200-88.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2225-89.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-225-9.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2250-90.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-2275-91.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-2300-92.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-2325-93.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-2400-96.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-2425-97.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-2450-98.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2475-99.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-25-1.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2500-100.jpg | 1407 | - | 3d45f26c1a77 | JPEG
v7-1-hard-negative-top-left-2525-101.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2550-102.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2575-103.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2600-104.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-2625-105.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2700-108.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-2725-109.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2750-110.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-2775-111.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2800-112.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2825-113.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2850-114.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2875-115.jpg | 1407 | - | b993da7aef92 | JPEG
v7-1-hard-negative-top-left-2900-116.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2925-117.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-300-12.jpg | 1407 | - | 098fe82c84e7 | JPEG
v7-1-hard-negative-top-left-3000-120.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3025-121.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3050-122.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-3075-123.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-3100-124.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3125-125.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3150-126.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-3175-127.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-3200-128.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3225-129.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-325-13.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-3300-132.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3325-133.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-3350-134.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3375-135.jpg | 1407 | - | 098fe82c84e7 | JPEG
v7-1-hard-negative-top-left-3400-136.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-3425-137.jpg | 1407 | - | 098fe82c84e7 | JPEG
v7-1-hard-negative-top-left-3450-138.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3475-139.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-350-14.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-3500-140.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3525-141.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3600-144.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3625-145.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3650-146.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-3675-147.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3700-148.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-3725-149.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-375-15.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3750-150.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3775-151.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3800-152.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3825-153.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3900-156.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3925-157.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3950-158.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-3975-159.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-400-16.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4000-160.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-4025-161.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-4050-162.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4075-163.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4100-164.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-4125-165.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-4200-168.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4225-169.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-425-17.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4250-170.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4275-171.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4300-172.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4325-173.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4350-174.jpg | 1407 | - | 3d45f26c1a77 | JPEG
v7-1-hard-negative-top-left-4375-175.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4400-176.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4425-177.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-450-18.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-475-19.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-50-2.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-500-20.jpg | 1407 | - | 73e1a8c8f323 | JPEG
v7-1-hard-negative-top-left-525-21.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-600-24.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-625-25.jpg | 1407 | - | 2e6df316da82 | JPEG
v7-1-hard-negative-top-left-650-26.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-675-27.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-700-28.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-725-29.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-75-3.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-750-30.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-775-31.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-800-32.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-825-33.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-900-36.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-925-37.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-950-38.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-975-39.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-positive-crop-trimed-5min.mp4-125-192.jpg | 26148 | - | 23dd7da2abe3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-125-256.jpg | 40609 | - | 222cc34a51c8 | JPEG
v7-1-positive-crop-trimed-5min.mp4-125-384.jpg | 75284 | - | c006ee9e45c2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-130-192.jpg | 23849 | - | ffb25cbf8f20 | JPEG
v7-1-positive-crop-trimed-5min.mp4-130-256.jpg | 42774 | - | a710980df1ca | JPEG
v7-1-positive-crop-trimed-5min.mp4-130-384.jpg | 96431 | - | a7ea985dddb2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-135-192.jpg | 24591 | - | 5e5772b66041 | JPEG
v7-1-positive-crop-trimed-5min.mp4-135-256.jpg | 43410 | - | 759e68ddfaff | JPEG
v7-1-positive-crop-trimed-5min.mp4-135-384.jpg | 98435 | - | 540515c47f16 | JPEG
v7-1-positive-crop-trimed-5min.mp4-140-192.jpg | 24945 | - | 5669da4f5d03 | JPEG
v7-1-positive-crop-trimed-5min.mp4-140-256.jpg | 43647 | - | 181fb4e19854 | JPEG
v7-1-positive-crop-trimed-5min.mp4-140-384.jpg | 97928 | - | a2fde93b973f | JPEG
v7-1-positive-crop-trimed-5min.mp4-1815-192.jpg | 21927 | - | 283cb02748a1 | JPEG
v7-1-positive-crop-trimed-5min.mp4-1815-256.jpg | 39022 | - | 124bfe8267ff | JPEG
v7-1-positive-crop-trimed-5min.mp4-1815-384.jpg | 90674 | - | 31cd6fd5bb06 | JPEG
v7-1-positive-crop-trimed-5min.mp4-195-192.jpg | 24287 | - | a85ac06d458e | JPEG
v7-1-positive-crop-trimed-5min.mp4-195-256.jpg | 41479 | - | 99232c3791f5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-195-384.jpg | 91603 | - | fca05656e9f3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-210-192.jpg | 23929 | - | 0328f9f3f34b | JPEG
v7-1-positive-crop-trimed-5min.mp4-210-256.jpg | 41365 | - | bd668ca1afd6 | JPEG
v7-1-positive-crop-trimed-5min.mp4-210-384.jpg | 91363 | - | b130deceb000 | JPEG
v7-1-positive-crop-trimed-5min.mp4-220-192.jpg | 24688 | - | 90c6016831d1 | JPEG
v7-1-positive-crop-trimed-5min.mp4-220-256.jpg | 42341 | - | 03c0e46cfaa4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-220-384.jpg | 94348 | - | 591e7d8e266b | JPEG
v7-1-positive-crop-trimed-5min.mp4-225-192.jpg | 24979 | - | 5a9c53cc9bce | JPEG
v7-1-positive-crop-trimed-5min.mp4-225-256.jpg | 42805 | - | 77e00d1f2d03 | JPEG
v7-1-positive-crop-trimed-5min.mp4-225-384.jpg | 94779 | - | 8506bb776194 | JPEG
v7-1-positive-crop-trimed-5min.mp4-230-192.jpg | 24048 | - | 4a15ff07dbba | JPEG
v7-1-positive-crop-trimed-5min.mp4-230-256.jpg | 42169 | - | 0c237f26c163 | JPEG
v7-1-positive-crop-trimed-5min.mp4-230-384.jpg | 95330 | - | 89fc69e9b723 | JPEG
v7-1-positive-crop-trimed-5min.mp4-235-192.jpg | 23732 | - | 472b6913fc34 | JPEG
v7-1-positive-crop-trimed-5min.mp4-235-256.jpg | 41892 | - | ac925b9f9084 | JPEG
v7-1-positive-crop-trimed-5min.mp4-235-384.jpg | 95239 | - | 93d33f9964aa | JPEG
v7-1-positive-crop-trimed-5min.mp4-2457-192.jpg | 24811 | - | 1e154aed4062 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2457-256.jpg | 43402 | - | 44a294cfc9c4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2457-384.jpg | 95307 | - | 95e0ce79a30c | JPEG
v7-1-positive-crop-trimed-5min.mp4-2460-192.jpg | 25555 | - | c30ca2ab718a | JPEG
v7-1-positive-crop-trimed-5min.mp4-2460-256.jpg | 44589 | - | 230bcf328408 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2460-384.jpg | 96224 | - | 0bf5b382082a | JPEG
v7-1-positive-crop-trimed-5min.mp4-2463-192.jpg | 25632 | - | 6fd899906c9c | JPEG
v7-1-positive-crop-trimed-5min.mp4-2463-256.jpg | 44072 | - | ca718e8d2220 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2463-384.jpg | 96195 | - | 7d6b0b34a5fb | JPEG
v7-1-positive-crop-trimed-5min.mp4-2528-192.jpg | 25961 | - | 95dcd49a891e | JPEG
v7-1-positive-crop-trimed-5min.mp4-2528-256.jpg | 45491 | - | 112792778a5d | JPEG
v7-1-positive-crop-trimed-5min.mp4-2528-384.jpg | 103133 | - | 53311eb5e1b3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2531-192.jpg | 25899 | - | 557d29a2fa27 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2531-256.jpg | 45482 | - | cac1ef95801c | JPEG
v7-1-positive-crop-trimed-5min.mp4-2531-384.jpg | 103031 | - | 009de1309676 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2534-192.jpg | 25583 | - | 8e1e3293160f | JPEG
v7-1-positive-crop-trimed-5min.mp4-2534-256.jpg | 44980 | - | 67622d276235 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2534-384.jpg | 101978 | - | a124030eb493 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2886-192.jpg | 21801 | - | 86b44306ba3a | JPEG
v7-1-positive-crop-trimed-5min.mp4-2886-256.jpg | 39051 | - | 96e53b91f010 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2886-384.jpg | 92144 | - | 58882b9a6aab | JPEG
v7-1-positive-crop-trimed-5min.mp4-2889-192.jpg | 21709 | - | c850dfd95041 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2889-256.jpg | 38862 | - | c89effd19f0b | JPEG
v7-1-positive-crop-trimed-5min.mp4-2889-384.jpg | 92314 | - | 91b514e07683 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2892-192.jpg | 21371 | - | 568eefabfa10 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2892-256.jpg | 38871 | - | 348f4289c23c | JPEG
v7-1-positive-crop-trimed-5min.mp4-2892-384.jpg | 91725 | - | 19e4b939390b | JPEG
v7-1-positive-crop-trimed-5min.mp4-300-192.jpg | 25302 | - | 2f461f5a8d02 | JPEG
v7-1-positive-crop-trimed-5min.mp4-300-256.jpg | 44833 | - | 9399711cb48e | JPEG
v7-1-positive-crop-trimed-5min.mp4-300-384.jpg | 89578 | - | 18aa23df2116 | JPEG
v7-1-positive-crop-trimed-5min.mp4-305-192.jpg | 24836 | - | d8775db03135 | JPEG
v7-1-positive-crop-trimed-5min.mp4-305-256.jpg | 43477 | - | 4b5fd8db5cc5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-305-384.jpg | 83911 | - | 3288323cb5bc | JPEG
v7-1-positive-crop-trimed-5min.mp4-310-192.jpg | 25567 | - | a8ca9053a0df | JPEG
v7-1-positive-crop-trimed-5min.mp4-310-256.jpg | 43306 | - | 5edfeb30abe7 | JPEG
v7-1-positive-crop-trimed-5min.mp4-310-384.jpg | 80143 | - | 585ab4eea98f | JPEG
v7-1-positive-crop-trimed-5min.mp4-315-192.jpg | 23910 | - | 7a2fc6d1dc73 | JPEG
v7-1-positive-crop-trimed-5min.mp4-315-256.jpg | 42096 | - | 482b49a3e2f7 | JPEG
v7-1-positive-crop-trimed-5min.mp4-315-384.jpg | 82793 | - | 1cea401418c3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-320-192.jpg | 23368 | - | e4a38b78a3a3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-320-256.jpg | 41120 | - | 5d8e5b49c7a9 | JPEG
v7-1-positive-crop-trimed-5min.mp4-320-384.jpg | 83870 | - | 19a5eab85934 | JPEG
v7-1-positive-crop-trimed-5min.mp4-325-192.jpg | 21246 | - | 531f781bee75 | JPEG
v7-1-positive-crop-trimed-5min.mp4-325-256.jpg | 38978 | - | 0deb531e9385 | JPEG
v7-1-positive-crop-trimed-5min.mp4-325-384.jpg | 90272 | - | f9869d2bcefd | JPEG
v7-1-positive-crop-trimed-5min.mp4-330-192.jpg | 20835 | - | b5a319fdfe56 | JPEG
v7-1-positive-crop-trimed-5min.mp4-330-256.jpg | 39150 | - | ff7bd02b3469 | JPEG
v7-1-positive-crop-trimed-5min.mp4-330-384.jpg | 91418 | - | a72d6baf7c21 | JPEG
v7-1-positive-crop-trimed-5min.mp4-335-192.jpg | 23464 | - | 963f7bd071e1 | JPEG
v7-1-positive-crop-trimed-5min.mp4-335-256.jpg | 41016 | - | 3a2d2f41b4df | JPEG
v7-1-positive-crop-trimed-5min.mp4-335-384.jpg | 93352 | - | 5026ec61f113 | JPEG
v7-1-positive-crop-trimed-5min.mp4-340-192.jpg | 24990 | - | 4dbec6f32923 | JPEG
v7-1-positive-crop-trimed-5min.mp4-340-256.jpg | 43346 | - | 8a5954cfc112 | JPEG
v7-1-positive-crop-trimed-5min.mp4-340-384.jpg | 95176 | - | 41db55f59eeb | JPEG
v7-1-positive-crop-trimed-5min.mp4-345-192.jpg | 23560 | - | 3d9303491e46 | JPEG
v7-1-positive-crop-trimed-5min.mp4-345-256.jpg | 41788 | - | 3fab1aada2fe | JPEG
v7-1-positive-crop-trimed-5min.mp4-345-384.jpg | 92516 | - | 73ae3842f119 | JPEG
v7-1-positive-crop-trimed-5min.mp4-350-192.jpg | 22742 | - | 5d2b1d4da4b8 | JPEG
v7-1-positive-crop-trimed-5min.mp4-350-256.jpg | 38348 | - | 46ae324e5943 | JPEG
v7-1-positive-crop-trimed-5min.mp4-350-384.jpg | 89146 | - | 032607012a3c | JPEG
v7-1-positive-crop-trimed-5min.mp4-355-192.jpg | 22612 | - | d3f48a429d69 | JPEG
v7-1-positive-crop-trimed-5min.mp4-355-256.jpg | 38270 | - | 3745205db9d4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-355-384.jpg | 89167 | - | b121318f4b94 | JPEG
v7-1-positive-crop-trimed-5min.mp4-360-192.jpg | 22732 | - | 606c2c9fe831 | JPEG
v7-1-positive-crop-trimed-5min.mp4-360-256.jpg | 38713 | - | 059edb43c59a | JPEG
v7-1-positive-crop-trimed-5min.mp4-360-384.jpg | 89246 | - | 29e68ac9cc70 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3602-192.jpg | 21897 | - | 53086ffea29f | JPEG
v7-1-positive-crop-trimed-5min.mp4-3602-256.jpg | 39519 | - | 079015e0793c | JPEG
v7-1-positive-crop-trimed-5min.mp4-3602-384.jpg | 92666 | - | 2b844ff65db5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3605-192.jpg | 22046 | - | 442e5ab76fb8 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3605-256.jpg | 39706 | - | 233d9c47563f | JPEG
v7-1-positive-crop-trimed-5min.mp4-3605-384.jpg | 92767 | - | 226b63f68c0c | JPEG
v7-1-positive-crop-trimed-5min.mp4-365-192.jpg | 23794 | - | c33af2bb7459 | JPEG
v7-1-positive-crop-trimed-5min.mp4-365-256.jpg | 40202 | - | 0e1c943d9c6e | JPEG
v7-1-positive-crop-trimed-5min.mp4-365-384.jpg | 89658 | - | 0e4c1676ab77 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3670-192.jpg | 21444 | - | 9b8a4aa8076a | JPEG
v7-1-positive-crop-trimed-5min.mp4-3670-256.jpg | 38312 | - | 41c5ced57be4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3670-384.jpg | 90487 | - | 9fbd5a1c1cbb | JPEG
v7-1-positive-crop-trimed-5min.mp4-3673-192.jpg | 21269 | - | 6f89e7c6af8d | JPEG
v7-1-positive-crop-trimed-5min.mp4-3673-256.jpg | 38531 | - | b6a90c9da4df | JPEG
v7-1-positive-crop-trimed-5min.mp4-3673-384.jpg | 90782 | - | 5e17c191b296 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3676-192.jpg | 21500 | - | fb19c2e60419 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3676-256.jpg | 38571 | - | 4e5287cd0c44 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3676-384.jpg | 90491 | - | 7b493ada36a7 | JPEG
v7-1-positive-crop-trimed-5min.mp4-370-192.jpg | 24477 | - | 26fb399c7901 | JPEG
v7-1-positive-crop-trimed-5min.mp4-370-256.jpg | 41886 | - | 4a80663fbbbe | JPEG
v7-1-positive-crop-trimed-5min.mp4-370-384.jpg | 90156 | - | 93812bd91d18 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3744-192.jpg | 22220 | - | 25c03166b469 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3744-256.jpg | 38061 | - | c56fd52b9f68 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3744-384.jpg | 84925 | - | 3e935fc32eab | JPEG
v7-1-positive-crop-trimed-5min.mp4-3747-192.jpg | 22451 | - | 0d8ceb387073 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3747-256.jpg | 38498 | - | 92dd8f11da6c | JPEG
v7-1-positive-crop-trimed-5min.mp4-3747-384.jpg | 85314 | - | c171b0d8c0e2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-375-192.jpg | 24366 | - | c1586ab959bd | JPEG
v7-1-positive-crop-trimed-5min.mp4-375-256.jpg | 41904 | - | a24c4c5ea1bf | JPEG
v7-1-positive-crop-trimed-5min.mp4-375-384.jpg | 90864 | - | 84e63b1bd24b | JPEG
v7-1-positive-crop-trimed-5min.mp4-3750-192.jpg | 21996 | - | e568c45d384a | JPEG
v7-1-positive-crop-trimed-5min.mp4-3750-256.jpg | 37662 | - | ff2ae7ddedca | JPEG
v7-1-positive-crop-trimed-5min.mp4-3750-384.jpg | 83703 | - | 683f89b37943 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3821-192.jpg | 20160 | - | 63ed4661e05b | JPEG
v7-1-positive-crop-trimed-5min.mp4-3821-256.jpg | 36892 | - | 43f4a402e0b4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3821-384.jpg | 88622 | - | f3bea2622733 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3960-192.jpg | 22512 | - | f57d7d4f995b | JPEG
v7-1-positive-crop-trimed-5min.mp4-3960-256.jpg | 40661 | - | cb97a173c167 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3960-384.jpg | 95043 | - | 26738f962d23 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3963-192.jpg | 22151 | - | 2e6500431415 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3963-256.jpg | 40555 | - | 57e6304191c4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-3963-384.jpg | 95417 | - | b5667360864c | JPEG
v7-1-positive-crop-trimed-5min.mp4-4099-192.jpg | 21146 | - | 31326f74f0d5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4099-256.jpg | 36420 | - | bb472d67cfe3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4099-384.jpg | 83228 | - | 4cbc36334bf0 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4102-192.jpg | 20888 | - | ce1251d18fc7 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4102-256.jpg | 36263 | - | eaf83810537b | JPEG
v7-1-positive-crop-trimed-5min.mp4-4102-384.jpg | 81752 | - | 40b279df450b | JPEG
v7-1-positive-crop-trimed-5min.mp4-4105-192.jpg | 21536 | - | 28db2e71286a | JPEG
v7-1-positive-crop-trimed-5min.mp4-4105-256.jpg | 36905 | - | b257b6f4e9e6 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4105-384.jpg | 83101 | - | 6571f6d2a42c | JPEG
v7-1-positive-crop-trimed-5min.mp4-4247-192.jpg | 27731 | - | 93d98df517d3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4247-256.jpg | 47990 | - | d69e6ef0a0b2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4247-384.jpg | 104674 | - | 71c5aea54a93 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4250-192.jpg | 26768 | - | 335a67cdb215 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4250-256.jpg | 46810 | - | 9bc57b8163be | JPEG
v7-1-positive-crop-trimed-5min.mp4-4250-384.jpg | 102455 | - | 9378e8906473 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4315-192.jpg | 23388 | - | b40daa8ec4d4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4315-256.jpg | 40612 | - | f88a608359dc | JPEG
v7-1-positive-crop-trimed-5min.mp4-4315-384.jpg | 89656 | - | 373850b1bb7f | JPEG
v7-1-positive-crop-trimed-5min.mp4-4318-192.jpg | 23083 | - | eb7d57436247 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4318-256.jpg | 40144 | - | 1981a4297d27 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4318-384.jpg | 89556 | - | a95a656bd35b | JPEG
v7-1-positive-crop-trimed-5min.mp4-4321-192.jpg | 22709 | - | 3a128588cc6e | JPEG
v7-1-positive-crop-trimed-5min.mp4-4321-256.jpg | 39431 | - | 42680ad8b3f1 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4321-384.jpg | 89457 | - | 395e4495dcdc | JPEG
v7-1-positive-crop-trimed-5min.mp4-4665-192.jpg | 27391 | - | 97e07b0f6f1d | JPEG
v7-1-positive-crop-trimed-5min.mp4-4665-256.jpg | 47333 | - | bf377e747d3c | JPEG
v7-1-positive-crop-trimed-5min.mp4-4665-384.jpg | 104081 | - | 8574f9df68da | JPEG
v7-1-positive-crop-trimed-5min.mp4-4670-192.jpg | 27527 | - | a1cec5761fa9 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4670-256.jpg | 47668 | - | 18187b4b68f2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4670-384.jpg | 104362 | - | 007dad6e4e74 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4675-192.jpg | 27500 | - | 7a493c7702e4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4675-256.jpg | 48009 | - | 2b1baa041267 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4675-384.jpg | 105263 | - | 3e4384929658 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4680-192.jpg | 27372 | - | 59298817eaa7 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4680-256.jpg | 47627 | - | ab743c56df84 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4680-384.jpg | 105056 | - | ecf5bcb5e160 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4685-192.jpg | 27260 | - | 46a749bc2e7b | JPEG
v7-1-positive-crop-trimed-5min.mp4-4685-256.jpg | 47648 | - | 38fef9d8c0d6 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4685-384.jpg | 104767 | - | 71570be564fc | JPEG
v7-1-positive-crop-trimed-5min.mp4-4690-192.jpg | 27002 | - | 2eb71dd5c1e4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4690-256.jpg | 47286 | - | 14727b01c3ad | JPEG
v7-1-positive-crop-trimed-5min.mp4-4690-384.jpg | 104027 | - | dad5ffe8aa56 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4695-192.jpg | 27185 | - | dff0d5d96839 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4695-256.jpg | 47528 | - | c20694a9e218 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4695-384.jpg | 104136 | - | 5be06c14835a | JPEG
v7-1-positive-crop-trimed-5min.mp4-5-192.jpg | 23294 | - | 15b5430546e8 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5-256.jpg | 41865 | - | 389e03321fe2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5-384.jpg | 88689 | - | 18af621ab415 | JPEG
v7-1-positive-crop-trimed-5min.mp4-50-192.jpg | 21013 | - | 36187764f60b | JPEG
v7-1-positive-crop-trimed-5min.mp4-50-256.jpg | 38119 | - | a8f3d23476df | JPEG
v7-1-positive-crop-trimed-5min.mp4-50-384.jpg | 91674 | - | fecec41ceba8 | JPEG
v7-1-positive-crop-trimed-5min.mp4-55-192.jpg | 21161 | - | 46f3e1d6c139 | JPEG
v7-1-positive-crop-trimed-5min.mp4-55-256.jpg | 38298 | - | 5ef874c2577d | JPEG
v7-1-positive-crop-trimed-5min.mp4-55-384.jpg | 91428 | - | 0d09f42f9f4d | JPEG
v7-1-positive-crop-trimed-5min.mp4-5920-192.jpg | 26010 | - | 360f1f5e017d | JPEG
v7-1-positive-crop-trimed-5min.mp4-5920-256.jpg | 45115 | - | 194f1a932a5f | JPEG
v7-1-positive-crop-trimed-5min.mp4-5920-384.jpg | 99151 | - | 24b346c983a9 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5945-192.jpg | 20787 | - | 8915e9ff2fdd | JPEG
v7-1-positive-crop-trimed-5min.mp4-5945-256.jpg | 38110 | - | a91d2ae4f6b9 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5945-384.jpg | 86510 | - | 315120fb2087 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5950-192.jpg | 24635 | - | 3cc007fa0c88 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5950-256.jpg | 43218 | - | 7d289b42b477 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5950-384.jpg | 96266 | - | a577f41e3909 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5965-192.jpg | 24280 | - | 6e2b189e2251 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5965-256.jpg | 42533 | - | 6e38d09c8583 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5965-384.jpg | 95583 | - | 627946757882 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5970-192.jpg | 23945 | - | 0f903aabb9c1 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5970-256.jpg | 42066 | - | 673420d48508 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5970-384.jpg | 94751 | - | bb4190368e39 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5975-192.jpg | 23641 | - | 422a0c573aad | JPEG
v7-1-positive-crop-trimed-5min.mp4-5975-256.jpg | 41211 | - | 4a95f9cd0c21 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5975-384.jpg | 93389 | - | 731515bab321 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5980-192.jpg | 23516 | - | 115f08555e67 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5980-256.jpg | 41019 | - | 9396569c8c60 | JPEG
v7-1-positive-crop-trimed-5min.mp4-5980-384.jpg | 92203 | - | 068cd8d9425c | JPEG
v7-1-positive-crop-trimed-5min.mp4-60-192.jpg | 23591 | - | 7d3206820bcd | JPEG
v7-1-positive-crop-trimed-5min.mp4-60-256.jpg | 42697 | - | 143402ab3101 | JPEG
v7-1-positive-crop-trimed-5min.mp4-60-384.jpg | 94191 | - | 4e3a3abdd614 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6110-192.jpg | 19972 | - | 7311dce4cb5a | JPEG
v7-1-positive-crop-trimed-5min.mp4-6110-256.jpg | 31601 | - | 59ce61dc9cda | JPEG
v7-1-positive-crop-trimed-5min.mp4-6110-384.jpg | 61668 | - | 71ffe4727e42 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6115-192.jpg | 18658 | - | 179294c1c844 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6115-256.jpg | 30219 | - | 056b5df52584 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6115-384.jpg | 59376 | - | c8d65052b3c0 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6120-192.jpg | 19328 | - | 2e3e9659d621 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6120-256.jpg | 31179 | - | 82d713d5dd06 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6120-384.jpg | 59852 | - | 61387329450f | JPEG
v7-1-positive-crop-trimed-5min.mp4-6125-192.jpg | 18212 | - | 35e7d034cf31 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6125-256.jpg | 30382 | - | 9091255579cc | JPEG
v7-1-positive-crop-trimed-5min.mp4-6125-384.jpg | 62742 | - | 46d7c27ac946 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6135-192.jpg | 23778 | - | 5d4fd291318c | JPEG
v7-1-positive-crop-trimed-5min.mp4-6135-256.jpg | 41641 | - | 97b9319290c9 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6135-384.jpg | 85115 | - | c459b76fdd32 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6140-192.jpg | 23296 | - | 3ba900340242 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6140-256.jpg | 41296 | - | a118ad5297d2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6140-384.jpg | 92883 | - | 45fa102f322c | JPEG
v7-1-positive-crop-trimed-5min.mp4-6145-192.jpg | 24361 | - | a5246e9f1673 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6145-256.jpg | 41271 | - | e0ea56358f34 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6145-384.jpg | 90649 | - | 2d93eb44bb1e | JPEG
v7-1-positive-crop-trimed-5min.mp4-6150-192.jpg | 22677 | - | d2e3075aef45 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6150-256.jpg | 41449 | - | fab10f1eb6b0 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6150-384.jpg | 89771 | - | cea12dc6098e | JPEG
v7-1-positive-crop-trimed-5min.mp4-6155-192.jpg | 23645 | - | d1f2400d82ca | JPEG
v7-1-positive-crop-trimed-5min.mp4-6155-256.jpg | 41979 | - | 89cbaaac8984 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6155-384.jpg | 86961 | - | 3bdeb6cc76be | JPEG
v7-1-positive-crop-trimed-5min.mp4-6160-192.jpg | 24032 | - | 5342744c1e55 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6160-256.jpg | 42313 | - | dca097829bb6 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6160-384.jpg | 93683 | - | 8b4e23f424e6 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6165-192.jpg | 23940 | - | 690ce2141034 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6165-256.jpg | 41237 | - | 7ecc8ef3873a | JPEG
v7-1-positive-crop-trimed-5min.mp4-6165-384.jpg | 91783 | - | ab144599f992 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6170-192.jpg | 24204 | - | ff3041ec3c90 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6170-256.jpg | 41885 | - | f8bda3f4754d | JPEG
v7-1-positive-crop-trimed-5min.mp4-6170-384.jpg | 92941 | - | 4bce3eaf2774 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6175-192.jpg | 24255 | - | 65424c10f76a | JPEG
v7-1-positive-crop-trimed-5min.mp4-6175-256.jpg | 42280 | - | 0aa58f835c7b | JPEG
v7-1-positive-crop-trimed-5min.mp4-6175-384.jpg | 94802 | - | 7bd19d8b0ad2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6180-192.jpg | 24753 | - | 9964a072b9f4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6180-256.jpg | 42534 | - | b576dd0c10cb | JPEG
v7-1-positive-crop-trimed-5min.mp4-6180-384.jpg | 85277 | - | cdc90de9c2d8 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6185-192.jpg | 24923 | - | 43e07df38941 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6185-256.jpg | 43411 | - | f861320a23c9 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6185-384.jpg | 88009 | - | 3376427126e3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6190-192.jpg | 24944 | - | 6116a04fe1ac | JPEG
v7-1-positive-crop-trimed-5min.mp4-6190-256.jpg | 44146 | - | fde574613557 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6190-384.jpg | 98265 | - | a9734bcef381 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6195-192.jpg | 25732 | - | 9f41bd24f163 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6195-256.jpg | 45551 | - | 988720cd33dc | JPEG
v7-1-positive-crop-trimed-5min.mp4-6195-384.jpg | 101214 | - | ee0ef67614a1 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6200-192.jpg | 25341 | - | 3bcd97a4f379 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6200-256.jpg | 44265 | - | 69740a9e5e05 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6200-384.jpg | 100091 | - | 7e3820694466 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6205-192.jpg | 25366 | - | dc81d5f50d64 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6205-256.jpg | 44168 | - | df4f4c1831af | JPEG
v7-1-positive-crop-trimed-5min.mp4-6205-384.jpg | 98518 | - | 9b5917dc95db | JPEG
v7-1-positive-crop-trimed-5min.mp4-6210-192.jpg | 25575 | - | 0cbbd3842d8a | JPEG
v7-1-positive-crop-trimed-5min.mp4-6210-256.jpg | 44928 | - | e8a68d343b26 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6210-384.jpg | 99956 | - | e585aa43f6ab | JPEG
v7-1-positive-crop-trimed-5min.mp4-6215-192.jpg | 26244 | - | 6dd03d07190e | JPEG
v7-1-positive-crop-trimed-5min.mp4-6215-256.jpg | 45843 | - | e749ca3a2dc5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6215-384.jpg | 100916 | - | c441785dc070 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6220-192.jpg | 25963 | - | 6fe8234d00e9 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6220-256.jpg | 45359 | - | e38c3fa59cf2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6220-384.jpg | 100987 | - | d36b8f743fc4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6225-192.jpg | 25751 | - | 0445b8acc732 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6225-256.jpg | 45141 | - | afb228fc1885 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6225-384.jpg | 99424 | - | d01f6f6f1da4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6230-192.jpg | 24773 | - | af9c5645eaac | JPEG
v7-1-positive-crop-trimed-5min.mp4-6230-256.jpg | 43030 | - | 4ae753f1442e | JPEG
v7-1-positive-crop-trimed-5min.mp4-6230-384.jpg | 95231 | - | 436d07689c17 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6892-192.jpg | 21835 | - | e0675418998e | JPEG
v7-1-positive-crop-trimed-5min.mp4-6892-256.jpg | 39442 | - | d544789e6203 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6892-384.jpg | 91593 | - | 9c2fa7a58773 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6960-192.jpg | 22917 | - | 2efbdf391277 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6960-256.jpg | 40492 | - | 30117f260dae | JPEG
v7-1-positive-crop-trimed-5min.mp4-6960-384.jpg | 91061 | - | 6056f4f40d77 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6963-192.jpg | 23618 | - | 02f88fafe658 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6963-256.jpg | 40995 | - | 6decb7a008b2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6963-384.jpg | 91890 | - | 7f2d5335967f | JPEG
v7-1-positive-crop-trimed-5min.mp4-7099-192.jpg | 21444 | - | 6690e40a3fb5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7099-256.jpg | 36704 | - | 2ad16fa63e9e | JPEG
v7-1-positive-crop-trimed-5min.mp4-7099-384.jpg | 80471 | - | 7ed9a382de00 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7102-192.jpg | 21400 | - | ae2e4b38d2cb | JPEG
v7-1-positive-crop-trimed-5min.mp4-7102-256.jpg | 36564 | - | 30f75bc0a793 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7102-384.jpg | 79287 | - | d8f52ac5df94 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7105-192.jpg | 21396 | - | 8b6a1f3aa11c | JPEG
v7-1-positive-crop-trimed-5min.mp4-7105-256.jpg | 37054 | - | a391355a223a | JPEG
v7-1-positive-crop-trimed-5min.mp4-7105-384.jpg | 79367 | - | d14b0e1bae97 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7170-192.jpg | 23424 | - | 8124e4f2ce25 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7170-256.jpg | 40019 | - | c94087535086 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7170-384.jpg | 88050 | - | 61343c7f2c71 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7173-192.jpg | 23029 | - | 4d15003d294d | JPEG
v7-1-positive-crop-trimed-5min.mp4-7173-256.jpg | 39950 | - | 006baf39ece5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7173-384.jpg | 88391 | - | c2fcbeb9d6bd | JPEG
v7-1-positive-crop-trimed-5min.mp4-7176-192.jpg | 21163 | - | 92e220f14946 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7176-256.jpg | 37832 | - | dc02c0ff5b38 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7176-384.jpg | 86405 | - | ce54d7cc7e5d | JPEG
v7-1-positive-crop-trimed-5min.mp4-7315-192.jpg | 20184 | - | d51f067b9793 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7315-256.jpg | 37472 | - | 0b355fc3de12 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7315-384.jpg | 87101 | - | 4a5b93f2e05f | JPEG
v7-1-positive-crop-trimed-5min.mp4-7318-192.jpg | 20998 | - | 9e04119ed006 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7318-256.jpg | 37941 | - | 48c047bebdc4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7318-384.jpg | 88239 | - | fb9bd3faf1df | JPEG
v7-1-positive-crop-trimed-5min.mp4-7457-192.jpg | 20295 | - | 1f2f507e07ff | JPEG
v7-1-positive-crop-trimed-5min.mp4-7457-256.jpg | 36378 | - | 3dee1041d7fc | JPEG
v7-1-positive-crop-trimed-5min.mp4-7457-384.jpg | 86656 | - | 3230f78f9406 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7460-192.jpg | 20198 | - | cb9b94b7ea39 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7460-256.jpg | 36079 | - | 9ddfc0e25be2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7460-384.jpg | 86147 | - | 37ec76a33b13 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7463-192.jpg | 20210 | - | 8e94a7378a19 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7463-256.jpg | 35996 | - | 913c3a702603 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7463-384.jpg | 86067 | - | 01a11d1aee5d | JPEG
v7-1-positive-crop-trimed-5min.mp4-7528-192.jpg | 20547 | - | 6f9bb45e792d | JPEG
v7-1-positive-crop-trimed-5min.mp4-7528-256.jpg | 36374 | - | f4529b4fc008 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7528-384.jpg | 84900 | - | 091f34a31fcc | JPEG
v7-1-positive-crop-trimed-5min.mp4-7531-192.jpg | 20359 | - | 5079f63defb4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7531-256.jpg | 35882 | - | b57b94d2d9c6 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7531-384.jpg | 83775 | - | 78573e86869e | JPEG
v7-1-positive-crop-trimed-5min.mp4-7534-192.jpg | 20399 | - | 63c8e8e790dc | JPEG
v7-1-positive-crop-trimed-5min.mp4-7534-256.jpg | 35874 | - | e37daef9ad40 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7534-384.jpg | 84018 | - | f030ba093682 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7579-192.jpg | 19819 | - | 22c7263cf2b5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7579-256.jpg | 34576 | - | 8f2d8bda099f | JPEG
v7-1-positive-crop-trimed-5min.mp4-7579-384.jpg | 85426 | - | 754dcd38f057 | JPEG
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_export_label_overlay_audit_v1/v7_2_export_preview/images/val

```text
basename | bytes | lines | sha256-prefix | inspection
v7-1-hard-negative-top-left-1150-46.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1175-47.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1450-58.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-1475-59.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-1750-70.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-1775-71.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2050-82.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2075-83.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2350-94.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-2375-95.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-250-10.jpg | 1407 | - | 3d45f26c1a77 | JPEG
v7-1-hard-negative-top-left-2650-106.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-2675-107.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-275-11.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-2950-118.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-2975-119.jpg | 1407 | - | c2f2ce425a97 | JPEG
v7-1-hard-negative-top-left-3250-130.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3275-131.jpg | 1407 | - | 248674746bdc | JPEG
v7-1-hard-negative-top-left-3550-142.jpg | 1407 | - | b331bb32630f | JPEG
v7-1-hard-negative-top-left-3575-143.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-hard-negative-top-left-3850-154.jpg | 1407 | - | 793285c8add0 | JPEG
v7-1-hard-negative-top-left-3875-155.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4150-166.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4175-167.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-4450-178.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-4475-179.jpg | 1407 | - | 161b2067ac1d | JPEG
v7-1-hard-negative-top-left-550-22.jpg | 1407 | - | 73e1a8c8f323 | JPEG
v7-1-hard-negative-top-left-575-23.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-850-34.jpg | 1407 | - | c217c97442e9 | JPEG
v7-1-hard-negative-top-left-875-35.jpg | 1407 | - | 898be37f7ba4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2386-192.jpg | 21914 | - | c2e160e31d59 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2386-256.jpg | 38006 | - | 3db73e73c1a7 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2386-384.jpg | 86661 | - | 0e8c272a6553 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2392-192.jpg | 21395 | - | 349e5376c687 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2392-256.jpg | 37861 | - | b50a0f43f157 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2392-384.jpg | 85465 | - | 3d22f65e9a8d | JPEG
v7-1-positive-crop-trimed-5min.mp4-240-192.jpg | 23224 | - | 0605773b2238 | JPEG
v7-1-positive-crop-trimed-5min.mp4-240-256.jpg | 41667 | - | 23a06cf607b5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-240-384.jpg | 86651 | - | e8a440e49c75 | JPEG
v7-1-positive-crop-trimed-5min.mp4-245-192.jpg | 23372 | - | 7f95f524a384 | JPEG
v7-1-positive-crop-trimed-5min.mp4-245-256.jpg | 41963 | - | a4fc9a3f880c | JPEG
v7-1-positive-crop-trimed-5min.mp4-245-384.jpg | 88386 | - | 95a3d54019cc | JPEG
v7-1-positive-crop-trimed-5min.mp4-250-192.jpg | 23099 | - | 2cd8f503c934 | JPEG
v7-1-positive-crop-trimed-5min.mp4-250-256.jpg | 41333 | - | fb6b06571fde | JPEG
v7-1-positive-crop-trimed-5min.mp4-250-384.jpg | 89558 | - | c785deb6282c | JPEG
v7-1-positive-crop-trimed-5min.mp4-260-192.jpg | 23443 | - | d3dbe7b499a6 | JPEG
v7-1-positive-crop-trimed-5min.mp4-260-256.jpg | 41304 | - | 617714662f77 | JPEG
v7-1-positive-crop-trimed-5min.mp4-260-384.jpg | 91478 | - | 8cbd4853b1bf | JPEG
v7-1-positive-crop-trimed-5min.mp4-2670-192.jpg | 21709 | - | a62f22678a36 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2670-256.jpg | 37969 | - | 1c5b36fa4bdd | JPEG
v7-1-positive-crop-trimed-5min.mp4-2670-384.jpg | 90216 | - | 22aa5884b896 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2673-192.jpg | 21005 | - | 759215dee518 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2673-256.jpg | 38030 | - | b281e016d5f4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2673-384.jpg | 90993 | - | 7eb81ddef1bc | JPEG
v7-1-positive-crop-trimed-5min.mp4-2676-192.jpg | 20924 | - | ba4316a46949 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2676-256.jpg | 38010 | - | 1b7ea4941d84 | JPEG
v7-1-positive-crop-trimed-5min.mp4-2676-384.jpg | 92344 | - | daa5b8b7b6ca | JPEG
v7-1-positive-crop-trimed-5min.mp4-275-192.jpg | 23707 | - | 274e44387512 | JPEG
v7-1-positive-crop-trimed-5min.mp4-275-256.jpg | 42092 | - | c14075dee061 | JPEG
v7-1-positive-crop-trimed-5min.mp4-275-384.jpg | 95863 | - | 89f761a1ce00 | JPEG
v7-1-positive-crop-trimed-5min.mp4-280-192.jpg | 23711 | - | 5f403b279275 | JPEG
v7-1-positive-crop-trimed-5min.mp4-280-256.jpg | 42039 | - | 113a038f6f73 | JPEG
v7-1-positive-crop-trimed-5min.mp4-280-384.jpg | 95531 | - | 7776d8e75e6f | JPEG
v7-1-positive-crop-trimed-5min.mp4-290-192.jpg | 23204 | - | e90b3155ff13 | JPEG
v7-1-positive-crop-trimed-5min.mp4-290-256.jpg | 42043 | - | 18d265f9f5f0 | JPEG
v7-1-positive-crop-trimed-5min.mp4-290-384.jpg | 96833 | - | 7afaea6ecef0 | JPEG
v7-1-positive-crop-trimed-5min.mp4-295-192.jpg | 23973 | - | 5407de13a14f | JPEG
v7-1-positive-crop-trimed-5min.mp4-295-256.jpg | 43594 | - | d434360b1770 | JPEG
v7-1-positive-crop-trimed-5min.mp4-295-384.jpg | 96376 | - | 601bda1e3c36 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4170-192.jpg | 23217 | - | 220fb0660ce0 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4170-256.jpg | 39732 | - | 37f525ea91c8 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4170-384.jpg | 89897 | - | ac439862e409 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4173-192.jpg | 23707 | - | 5d26ce0b8619 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4173-256.jpg | 41033 | - | 13b8d431e084 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4173-384.jpg | 91486 | - | 4579f1fe9058 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4176-192.jpg | 24932 | - | 46badd5813af | JPEG
v7-1-positive-crop-trimed-5min.mp4-4176-256.jpg | 42976 | - | 0bac115149e5 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4176-384.jpg | 91295 | - | 1bfd85539235 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4457-192.jpg | 21649 | - | 8e67b09a1c34 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4457-256.jpg | 38166 | - | 63fd89a7a196 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4457-384.jpg | 89114 | - | 62ca3d46af2f | JPEG
v7-1-positive-crop-trimed-5min.mp4-4460-192.jpg | 20474 | - | 01ed92be7887 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4460-256.jpg | 37520 | - | d21d516e06bc | JPEG
v7-1-positive-crop-trimed-5min.mp4-4460-384.jpg | 88859 | - | 8d920adc1453 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4463-192.jpg | 20054 | - | bd2ef6b649c2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4463-256.jpg | 36962 | - | 981e82c06405 | JPEG
v7-1-positive-crop-trimed-5min.mp4-4463-384.jpg | 89039 | - | 66c1ef1a376f | JPEG
v7-1-positive-crop-trimed-5min.mp4-6005-192.jpg | 23163 | - | af80de9063d7 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6005-256.jpg | 39906 | - | 3525f09198b3 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6005-384.jpg | 89039 | - | 10368e6acca4 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6010-192.jpg | 23254 | - | 6ee968f6eca8 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6010-256.jpg | 39924 | - | d6f77bf036ab | JPEG
v7-1-positive-crop-trimed-5min.mp4-6010-384.jpg | 89084 | - | 6686c9e7fdca | JPEG
v7-1-positive-crop-trimed-5min.mp4-6957-192.jpg | 22643 | - | 3f6a30a754e2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-6957-256.jpg | 40421 | - | f5e7f822f64a | JPEG
v7-1-positive-crop-trimed-5min.mp4-6957-384.jpg | 91143 | - | dc4916a2c27e | JPEG
v7-1-positive-crop-trimed-5min.mp4-7321-192.jpg | 21486 | - | 09e73f2b9a0e | JPEG
v7-1-positive-crop-trimed-5min.mp4-7321-256.jpg | 38066 | - | 261ef40a06f2 | JPEG
v7-1-positive-crop-trimed-5min.mp4-7321-384.jpg | 88613 | - | 435ca98d4a2e | JPEG
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_export_label_overlay_audit_v1/v7_2_export_preview/labels/canary

```text
basename | bytes | lines | sha256-prefix | inspection
v7-1-hard-negative-top-left-4500-180.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4525-181.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4550-182.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4575-183.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4600-184.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4625-185.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4650-186.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4675-187.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4700-188.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4725-189.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4750-190.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4775-191.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4800-192.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4825-193.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4850-194.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4875-195.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4900-196.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4925-197.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4950-198.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4975-199.txt | 0 | 0 | e3b0c44298fc | TEXT
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_export_label_overlay_audit_v1/v7_2_export_preview/labels/train

```text
basename | bytes | lines | sha256-prefix | inspection
v7-1-hard-negative-top-left-0-0.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-100-4.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1000-40.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1025-41.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1050-42.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1075-43.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1100-44.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1125-45.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1200-48.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1225-49.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-125-5.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1250-50.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1275-51.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1300-52.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1325-53.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1350-54.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1375-55.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1400-56.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1425-57.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-150-6.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1500-60.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1525-61.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1550-62.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1575-63.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1600-64.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1625-65.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1650-66.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1675-67.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1700-68.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1725-69.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-175-7.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1800-72.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1825-73.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1850-74.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1875-75.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1900-76.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1925-77.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1950-78.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1975-79.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-200-8.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2000-80.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2025-81.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2100-84.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2125-85.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2150-86.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2175-87.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2200-88.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2225-89.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-225-9.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2250-90.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2275-91.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2300-92.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2325-93.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2400-96.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2425-97.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2450-98.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2475-99.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-25-1.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2500-100.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2525-101.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2550-102.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2575-103.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2600-104.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2625-105.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2700-108.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2725-109.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2750-110.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2775-111.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2800-112.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2825-113.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2850-114.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2875-115.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2900-116.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2925-117.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-300-12.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3000-120.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3025-121.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3050-122.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3075-123.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3100-124.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3125-125.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3150-126.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3175-127.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3200-128.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3225-129.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-325-13.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3300-132.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3325-133.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3350-134.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3375-135.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3400-136.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3425-137.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3450-138.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3475-139.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-350-14.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3500-140.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3525-141.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3600-144.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3625-145.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3650-146.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3675-147.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3700-148.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3725-149.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-375-15.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3750-150.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3775-151.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3800-152.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3825-153.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3900-156.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3925-157.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3950-158.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3975-159.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-400-16.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4000-160.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4025-161.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4050-162.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4075-163.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4100-164.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4125-165.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4200-168.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4225-169.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-425-17.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4250-170.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4275-171.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4300-172.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4325-173.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4350-174.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4375-175.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4400-176.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4425-177.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-450-18.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-475-19.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-50-2.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-500-20.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-525-21.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-600-24.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-625-25.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-650-26.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-675-27.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-700-28.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-725-29.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-75-3.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-750-30.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-775-31.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-800-32.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-825-33.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-900-36.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-925-37.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-950-38.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-975-39.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-positive-crop-trimed-5min.mp4-125-192.txt | 46 | 1 | f01178699dcc | TEXT
v7-1-positive-crop-trimed-5min.mp4-125-256.txt | 46 | 1 | a2549d904591 | TEXT
v7-1-positive-crop-trimed-5min.mp4-125-384.txt | 46 | 1 | ec03264d1586 | TEXT
v7-1-positive-crop-trimed-5min.mp4-130-192.txt | 46 | 1 | 35f97f79179b | TEXT
v7-1-positive-crop-trimed-5min.mp4-130-256.txt | 46 | 1 | 980a547161cb | TEXT
v7-1-positive-crop-trimed-5min.mp4-130-384.txt | 46 | 1 | d69ecf57c9c3 | TEXT
v7-1-positive-crop-trimed-5min.mp4-135-192.txt | 46 | 1 | 493cc3155c84 | TEXT
v7-1-positive-crop-trimed-5min.mp4-135-256.txt | 46 | 1 | 4495ff564d37 | TEXT
v7-1-positive-crop-trimed-5min.mp4-135-384.txt | 46 | 1 | 008b49ae7b13 | TEXT
v7-1-positive-crop-trimed-5min.mp4-140-192.txt | 46 | 1 | d21c9ac1d314 | TEXT
v7-1-positive-crop-trimed-5min.mp4-140-256.txt | 46 | 1 | e144ee2b762d | TEXT
v7-1-positive-crop-trimed-5min.mp4-140-384.txt | 46 | 1 | 3053af3f2a9c | TEXT
v7-1-positive-crop-trimed-5min.mp4-1815-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-1815-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-1815-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-195-192.txt | 46 | 1 | 493cc3155c84 | TEXT
v7-1-positive-crop-trimed-5min.mp4-195-256.txt | 46 | 1 | 4495ff564d37 | TEXT
v7-1-positive-crop-trimed-5min.mp4-195-384.txt | 46 | 1 | 008b49ae7b13 | TEXT
v7-1-positive-crop-trimed-5min.mp4-210-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-210-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-210-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-220-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-220-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-220-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-225-192.txt | 46 | 1 | f1ce88b9fd79 | TEXT
v7-1-positive-crop-trimed-5min.mp4-225-256.txt | 46 | 1 | bfb941c2e0f7 | TEXT
v7-1-positive-crop-trimed-5min.mp4-225-384.txt | 46 | 1 | 5a4310422215 | TEXT
v7-1-positive-crop-trimed-5min.mp4-230-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-230-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-230-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-235-192.txt | 46 | 1 | f1ce88b9fd79 | TEXT
v7-1-positive-crop-trimed-5min.mp4-235-256.txt | 46 | 1 | bfb941c2e0f7 | TEXT
v7-1-positive-crop-trimed-5min.mp4-235-384.txt | 46 | 1 | 5a4310422215 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2457-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2457-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2457-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2460-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2460-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2460-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2463-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2463-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2463-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2528-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2528-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2528-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2531-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2531-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2531-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2534-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2534-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2534-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2886-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2886-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2886-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2889-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2889-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2889-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2892-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2892-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2892-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-300-192.txt | 46 | 1 | 4219f8b4b148 | TEXT
v7-1-positive-crop-trimed-5min.mp4-300-256.txt | 46 | 1 | 216df81d3d4d | TEXT
v7-1-positive-crop-trimed-5min.mp4-300-384.txt | 46 | 1 | 395aca61096d | TEXT
v7-1-positive-crop-trimed-5min.mp4-305-192.txt | 46 | 1 | 9dcb3d67f47f | TEXT
v7-1-positive-crop-trimed-5min.mp4-305-256.txt | 46 | 1 | 801623bb0d92 | TEXT
v7-1-positive-crop-trimed-5min.mp4-305-384.txt | 46 | 1 | a8ab4e7f417c | TEXT
v7-1-positive-crop-trimed-5min.mp4-310-192.txt | 46 | 1 | 4219f8b4b148 | TEXT
v7-1-positive-crop-trimed-5min.mp4-310-256.txt | 46 | 1 | 216df81d3d4d | TEXT
v7-1-positive-crop-trimed-5min.mp4-310-384.txt | 46 | 1 | 395aca61096d | TEXT
v7-1-positive-crop-trimed-5min.mp4-315-192.txt | 46 | 1 | 9dcb3d67f47f | TEXT
v7-1-positive-crop-trimed-5min.mp4-315-256.txt | 46 | 1 | 801623bb0d92 | TEXT
v7-1-positive-crop-trimed-5min.mp4-315-384.txt | 46 | 1 | 70dcbf0a02db | TEXT
v7-1-positive-crop-trimed-5min.mp4-320-192.txt | 46 | 1 | 4219f8b4b148 | TEXT
v7-1-positive-crop-trimed-5min.mp4-320-256.txt | 46 | 1 | 216df81d3d4d | TEXT
v7-1-positive-crop-trimed-5min.mp4-320-384.txt | 46 | 1 | 8853e221657d | TEXT
v7-1-positive-crop-trimed-5min.mp4-325-192.txt | 46 | 1 | 9dcb3d67f47f | TEXT
v7-1-positive-crop-trimed-5min.mp4-325-256.txt | 46 | 1 | 801623bb0d92 | TEXT
v7-1-positive-crop-trimed-5min.mp4-325-384.txt | 46 | 1 | a8ab4e7f417c | TEXT
v7-1-positive-crop-trimed-5min.mp4-330-192.txt | 46 | 1 | 89e3fd4d012a | TEXT
v7-1-positive-crop-trimed-5min.mp4-330-256.txt | 46 | 1 | df22fc1d2902 | TEXT
v7-1-positive-crop-trimed-5min.mp4-330-384.txt | 46 | 1 | 7acc6be8e3f0 | TEXT
v7-1-positive-crop-trimed-5min.mp4-335-192.txt | 46 | 1 | f01178699dcc | TEXT
v7-1-positive-crop-trimed-5min.mp4-335-256.txt | 46 | 1 | a2549d904591 | TEXT
v7-1-positive-crop-trimed-5min.mp4-335-384.txt | 46 | 1 | ec03264d1586 | TEXT
v7-1-positive-crop-trimed-5min.mp4-340-192.txt | 46 | 1 | 35f97f79179b | TEXT
v7-1-positive-crop-trimed-5min.mp4-340-256.txt | 46 | 1 | 980a547161cb | TEXT
v7-1-positive-crop-trimed-5min.mp4-340-384.txt | 46 | 1 | d69ecf57c9c3 | TEXT
v7-1-positive-crop-trimed-5min.mp4-345-192.txt | 46 | 1 | 493cc3155c84 | TEXT
v7-1-positive-crop-trimed-5min.mp4-345-256.txt | 46 | 1 | 4495ff564d37 | TEXT
v7-1-positive-crop-trimed-5min.mp4-345-384.txt | 46 | 1 | 008b49ae7b13 | TEXT
v7-1-positive-crop-trimed-5min.mp4-350-192.txt | 46 | 1 | d21c9ac1d314 | TEXT
v7-1-positive-crop-trimed-5min.mp4-350-256.txt | 46 | 1 | e144ee2b762d | TEXT
v7-1-positive-crop-trimed-5min.mp4-350-384.txt | 46 | 1 | 3053af3f2a9c | TEXT
v7-1-positive-crop-trimed-5min.mp4-355-192.txt | 46 | 1 | d8713f055b33 | TEXT
v7-1-positive-crop-trimed-5min.mp4-355-256.txt | 46 | 1 | eb04fc2545dc | TEXT
v7-1-positive-crop-trimed-5min.mp4-355-384.txt | 46 | 1 | dc37df8bc73f | TEXT
v7-1-positive-crop-trimed-5min.mp4-360-192.txt | 46 | 1 | d8713f055b33 | TEXT
v7-1-positive-crop-trimed-5min.mp4-360-256.txt | 46 | 1 | eb04fc2545dc | TEXT
v7-1-positive-crop-trimed-5min.mp4-360-384.txt | 46 | 1 | dc37df8bc73f | TEXT
v7-1-positive-crop-trimed-5min.mp4-3602-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3602-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3602-384.txt | 46 | 1 | 7f895c7ba26a | TEXT
v7-1-positive-crop-trimed-5min.mp4-3605-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3605-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3605-384.txt | 46 | 1 | df78bf8a76bb | TEXT
v7-1-positive-crop-trimed-5min.mp4-365-192.txt | 46 | 1 | d8713f055b33 | TEXT
v7-1-positive-crop-trimed-5min.mp4-365-256.txt | 46 | 1 | eb04fc2545dc | TEXT
v7-1-positive-crop-trimed-5min.mp4-365-384.txt | 46 | 1 | dc37df8bc73f | TEXT
v7-1-positive-crop-trimed-5min.mp4-3670-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3670-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3670-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-3673-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3673-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3673-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-3676-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3676-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3676-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-370-192.txt | 46 | 1 | d8713f055b33 | TEXT
v7-1-positive-crop-trimed-5min.mp4-370-256.txt | 46 | 1 | eb04fc2545dc | TEXT
v7-1-positive-crop-trimed-5min.mp4-370-384.txt | 46 | 1 | dc37df8bc73f | TEXT
v7-1-positive-crop-trimed-5min.mp4-3744-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3744-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3744-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-3747-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3747-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3747-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-375-192.txt | 46 | 1 | d8713f055b33 | TEXT
v7-1-positive-crop-trimed-5min.mp4-375-256.txt | 46 | 1 | eb04fc2545dc | TEXT
v7-1-positive-crop-trimed-5min.mp4-375-384.txt | 46 | 1 | dc37df8bc73f | TEXT
v7-1-positive-crop-trimed-5min.mp4-3750-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3750-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3750-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-3821-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3821-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3821-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-3960-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3960-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3960-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-3963-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3963-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-3963-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4099-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4099-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4099-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4102-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4102-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4102-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4105-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4105-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4105-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4247-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4247-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4247-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4250-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4250-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4250-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4315-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4315-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4315-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4318-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4318-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4318-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4321-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4321-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4321-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4665-192.txt | 46 | 1 | bb241df7e236 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4665-256.txt | 46 | 1 | 6525f724d01c | TEXT
v7-1-positive-crop-trimed-5min.mp4-4665-384.txt | 46 | 1 | b3d2ae2c0c5a | TEXT
v7-1-positive-crop-trimed-5min.mp4-4670-192.txt | 46 | 1 | 67017b5b9acb | TEXT
v7-1-positive-crop-trimed-5min.mp4-4670-256.txt | 46 | 1 | 1283d6f187f1 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4670-384.txt | 46 | 1 | 0dabf71ae6b9 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4675-192.txt | 46 | 1 | bb241df7e236 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4675-256.txt | 46 | 1 | 6525f724d01c | TEXT
v7-1-positive-crop-trimed-5min.mp4-4675-384.txt | 46 | 1 | b3d2ae2c0c5a | TEXT
v7-1-positive-crop-trimed-5min.mp4-4680-192.txt | 46 | 1 | 67017b5b9acb | TEXT
v7-1-positive-crop-trimed-5min.mp4-4680-256.txt | 46 | 1 | 1283d6f187f1 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4680-384.txt | 46 | 1 | 0dabf71ae6b9 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4685-192.txt | 46 | 1 | 3f5b800bf10c | TEXT
v7-1-positive-crop-trimed-5min.mp4-4685-256.txt | 46 | 1 | 3626e81053f4 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4685-384.txt | 46 | 1 | b9f5262d5845 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4690-192.txt | 46 | 1 | 3481e7245ba6 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4690-256.txt | 46 | 1 | e6f50d8bc10a | TEXT
v7-1-positive-crop-trimed-5min.mp4-4690-384.txt | 46 | 1 | e751b11f1fe8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4695-192.txt | 46 | 1 | 12ebb6c8b369 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4695-256.txt | 46 | 1 | 292aa7fcd4da | TEXT
v7-1-positive-crop-trimed-5min.mp4-4695-384.txt | 46 | 1 | c091724be964 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5-192.txt | 46 | 1 | f1ce88b9fd79 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5-256.txt | 46 | 1 | bfb941c2e0f7 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5-384.txt | 46 | 1 | 5a4310422215 | TEXT
v7-1-positive-crop-trimed-5min.mp4-50-192.txt | 46 | 1 | 4219f8b4b148 | TEXT
v7-1-positive-crop-trimed-5min.mp4-50-256.txt | 46 | 1 | 216df81d3d4d | TEXT
v7-1-positive-crop-trimed-5min.mp4-50-384.txt | 46 | 1 | 395aca61096d | TEXT
v7-1-positive-crop-trimed-5min.mp4-55-192.txt | 46 | 1 | 9dcb3d67f47f | TEXT
v7-1-positive-crop-trimed-5min.mp4-55-256.txt | 46 | 1 | 801623bb0d92 | TEXT
v7-1-positive-crop-trimed-5min.mp4-55-384.txt | 46 | 1 | a8ab4e7f417c | TEXT
v7-1-positive-crop-trimed-5min.mp4-5920-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5920-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5920-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-5945-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5945-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5945-384.txt | 46 | 1 | 20a31e365aa0 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5950-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5950-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5950-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-5965-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5965-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5965-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-5970-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5970-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5970-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-5975-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5975-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5975-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-5980-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5980-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-5980-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-60-192.txt | 46 | 1 | 89e3fd4d012a | TEXT
v7-1-positive-crop-trimed-5min.mp4-60-256.txt | 46 | 1 | df22fc1d2902 | TEXT
v7-1-positive-crop-trimed-5min.mp4-60-384.txt | 46 | 1 | 092506d7a208 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6110-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6110-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6110-384.txt | 46 | 1 | d65f988e2c6b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6115-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6115-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6115-384.txt | 46 | 1 | 01c5f904beb6 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6120-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6120-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6120-384.txt | 46 | 1 | 4e009442a968 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6125-192.txt | 46 | 1 | fab066afaaca | TEXT
v7-1-positive-crop-trimed-5min.mp4-6125-256.txt | 46 | 1 | 18c49173aed6 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6125-384.txt | 46 | 1 | cfb1b8c831ed | TEXT
v7-1-positive-crop-trimed-5min.mp4-6135-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6135-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6135-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6140-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6140-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6140-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6145-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6145-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6145-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6150-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6150-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6150-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6155-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6155-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6155-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6160-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6160-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6160-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6165-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6165-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6165-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6170-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6170-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6170-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6175-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6175-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6175-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6180-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6180-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6180-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6185-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6185-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6185-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6190-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6190-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6190-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6195-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6195-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6195-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6200-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6200-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6200-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6205-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6205-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6205-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6210-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6210-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6210-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6215-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6215-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6215-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6220-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6220-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6220-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6225-192.txt | 46 | 1 | d838216cbc7c | TEXT
v7-1-positive-crop-trimed-5min.mp4-6225-256.txt | 46 | 1 | 1ef540a5ef39 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6225-384.txt | 46 | 1 | ba2e02a1f88c | TEXT
v7-1-positive-crop-trimed-5min.mp4-6230-192.txt | 46 | 1 | 70d1cde32bd4 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6230-256.txt | 46 | 1 | d03151821eb7 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6230-384.txt | 46 | 1 | f073397e7172 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6892-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6892-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6892-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-6960-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6960-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6960-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-6963-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6963-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6963-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7099-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7099-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7099-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7102-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7102-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7102-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7105-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7105-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7105-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7170-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7170-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7170-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7173-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7173-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7173-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7176-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7176-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7176-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7315-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7315-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7315-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7318-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7318-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7318-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7457-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7457-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7457-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7460-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7460-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7460-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7463-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7463-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7463-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7528-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7528-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7528-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7531-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7531-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7531-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7534-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7534-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7534-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7579-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7579-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7579-384.txt | 46 | 1 | e035c36c63ea | TEXT
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_export_label_overlay_audit_v1/v7_2_export_preview/labels/val

```text
basename | bytes | lines | sha256-prefix | inspection
v7-1-hard-negative-top-left-1150-46.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1175-47.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1450-58.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1475-59.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1750-70.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-1775-71.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2050-82.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2075-83.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2350-94.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2375-95.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-250-10.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2650-106.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2675-107.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-275-11.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2950-118.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-2975-119.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3250-130.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3275-131.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3550-142.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3575-143.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3850-154.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-3875-155.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4150-166.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4175-167.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4450-178.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-4475-179.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-550-22.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-575-23.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-850-34.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-hard-negative-top-left-875-35.txt | 0 | 0 | e3b0c44298fc | TEXT
v7-1-positive-crop-trimed-5min.mp4-2386-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2386-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2386-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2392-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2392-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2392-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-240-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-240-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-240-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-245-192.txt | 46 | 1 | f1ce88b9fd79 | TEXT
v7-1-positive-crop-trimed-5min.mp4-245-256.txt | 46 | 1 | bfb941c2e0f7 | TEXT
v7-1-positive-crop-trimed-5min.mp4-245-384.txt | 46 | 1 | 5a4310422215 | TEXT
v7-1-positive-crop-trimed-5min.mp4-250-192.txt | 46 | 1 | cad00e349fa6 | TEXT
v7-1-positive-crop-trimed-5min.mp4-250-256.txt | 46 | 1 | 466eb6125f7b | TEXT
v7-1-positive-crop-trimed-5min.mp4-250-384.txt | 46 | 1 | bb1baabc0c7c | TEXT
v7-1-positive-crop-trimed-5min.mp4-260-192.txt | 46 | 1 | fd51077cfdae | TEXT
v7-1-positive-crop-trimed-5min.mp4-260-256.txt | 46 | 1 | 908e247de6c4 | TEXT
v7-1-positive-crop-trimed-5min.mp4-260-384.txt | 46 | 1 | 579dbc1795c4 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2670-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2670-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2670-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2673-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2673-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2673-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-2676-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2676-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-2676-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-275-192.txt | 46 | 1 | f1ce88b9fd79 | TEXT
v7-1-positive-crop-trimed-5min.mp4-275-256.txt | 46 | 1 | bfb941c2e0f7 | TEXT
v7-1-positive-crop-trimed-5min.mp4-275-384.txt | 46 | 1 | 5a4310422215 | TEXT
v7-1-positive-crop-trimed-5min.mp4-280-192.txt | 46 | 1 | cad00e349fa6 | TEXT
v7-1-positive-crop-trimed-5min.mp4-280-256.txt | 46 | 1 | 466eb6125f7b | TEXT
v7-1-positive-crop-trimed-5min.mp4-280-384.txt | 46 | 1 | bb1baabc0c7c | TEXT
v7-1-positive-crop-trimed-5min.mp4-290-192.txt | 46 | 1 | fd51077cfdae | TEXT
v7-1-positive-crop-trimed-5min.mp4-290-256.txt | 46 | 1 | 908e247de6c4 | TEXT
v7-1-positive-crop-trimed-5min.mp4-290-384.txt | 46 | 1 | 579dbc1795c4 | TEXT
v7-1-positive-crop-trimed-5min.mp4-295-192.txt | 46 | 1 | f01178699dcc | TEXT
v7-1-positive-crop-trimed-5min.mp4-295-256.txt | 46 | 1 | a2549d904591 | TEXT
v7-1-positive-crop-trimed-5min.mp4-295-384.txt | 46 | 1 | ec03264d1586 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4170-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4170-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4170-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4173-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4173-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4173-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4176-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4176-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4176-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4457-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4457-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4457-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4460-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4460-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4460-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-4463-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4463-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-4463-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-6005-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6005-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6005-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6010-192.txt | 46 | 1 | 940a06a6c091 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6010-256.txt | 46 | 1 | 6cc283a572f5 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6010-384.txt | 46 | 1 | e18f8f2baa4b | TEXT
v7-1-positive-crop-trimed-5min.mp4-6957-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6957-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-6957-384.txt | 46 | 1 | e035c36c63ea | TEXT
v7-1-positive-crop-trimed-5min.mp4-7321-192.txt | 46 | 1 | 54c407cfacc8 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7321-256.txt | 46 | 1 | f719a050b862 | TEXT
v7-1-positive-crop-trimed-5min.mp4-7321-384.txt | 46 | 1 | e035c36c63ea | TEXT
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_full_pipeline_non_promotion_eval_v1

```text
basename | bytes | lines | sha256-prefix | inspection
batch_outcome_analysis.json | 966722 | 31186 | 85aa4f8ddcb0 | JSON
batch_outcome_analysis.md | 600 | 15 | 3ef8ace42b6c | DOC
candidate_crop_coverage_audit.json | 901529 | 31114 | f5736f77df27 | JSON
checkpoint_contract_audit.json | 7713 | 174 | 5d408b73019a | JSON
confidence_sweep_audit.json | 4870476 | 94261 | 9fdca1b89995 | JSON
crop_to_source_projection_audit.json | 61 | 4 | 8f92a58ce3d3 | JSON
decision_matrix.json | 2440 | 60 | 6efc1ed27bf0 | JSON
false_positive_analysis.json | 43 | 4 | 28c1bd622b71 | JSON
heldout_canary_pipeline_audit.json | 19251 | 365 | 956512b6994c | JSON
observed_ball_acceptance_audit.json | 508881 | 16663 | 745a68c98d1c | JSON
old_top_left_artifact_contact_sheet.jpg | 50476 | - | a2caa28d93c7 | JPEG
old_top_left_artifact_pipeline_audit.json | 19611 | 365 | 119290c1b6ca | JSON
pipeline_crop_contract_audit.json | 9127 | 343 | 677722c82a02 | JSON
positive_miss_analysis.json | 36 | 4 | f4713210be45 | JSON
refuted_seed_evidence_audit.json | 171730 | 3245 | b6b373df74d4 | JSON
reviewed_positive_pipeline_audit.json | 901529 | 31114 | f5736f77df27 | JSON
sampled_frame_flood_regression_audit.json | 96 | 5 | a7c48600e7b9 | JSON
v7_2_full_pipeline_non_promotion_summary.json | 2258 | 57 | 8affc39c69fe | JSON
worst_false_positives_contact_sheet.jpg | 50515 | - | 8c28a891173c | JPEG
worst_positive_misses_contact_sheet.jpg | 41040 | - | a3ca6ed5583e | JPEG
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_promotion_readiness_validation_v1

```text
basename | bytes | lines | sha256-prefix | inspection
batch_outcome_analysis.json | 5304 | 133 | 9257800a8201 | JSON
batch_outcome_analysis.md | 659 | 18 | d9a5a1070e13 | DOC
candidate_evaluation_readiness_contract.json | 1817 | 26 | 4d53ccb15036 | JSON
controlled_runtime_registry_entry.json | 2442 | 39 | bdca560ed020 | JSON
decision_matrix.json | 4039 | 93 | 867d5d17f3de | JSON
failsafe_attempt_plan.json | 1443 | 36 | 70926c558d50 | JSON
promotion_gate_audit.json | 4917 | 123 | 9580d7f374ed | JSON
runtime_contract_audit.json | 556 | 11 | afa40715afb3 | JSON
runtime_default_mutation_audit.json | 335 | 10 | 5b9102ff0d5f | JSON
v7_2_promotion_readiness_summary.json | 2439 | 57 | 937fbfca1525 | JSON
```

### backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_2_training_manifest_prep_v1

```text
basename | bytes | lines | sha256-prefix | inspection
batch_outcome_analysis.json | 1194 | 34 | 14606b686d93 | JSON
batch_outcome_analysis.md | 213 | 8 | f6451b53ee30 | DOC
decision_matrix.json | 394 | 17 | 21eb3dabd16b | JSON
v7_2_manifest_quality_gate.json | 332 | 11 | d90769a5987b | JSON
v7_2_positive_crop_transform_audit.json | 265172 | 10855 | 77a95536d19a | JSON
v7_2_split_leakage_audit.json | 246 | 8 | 3b6f2993975d | JSON
v7_2_training_manifest.json | 631677 | 22402 | 0f902a63defe | JSON
v7_2_training_manifest_prep_summary.json | 766 | 21 | 33bb2bd5dc60 | JSON
```

### backend/tests

```text
basename | bytes | lines | sha256-prefix | inspection
conftest.py | 4863 | 154 | 72da858a01e4 | PY
runtime_manifest_fixture.py | 2712 | 66 | acbb28b169a6 | PY
test_analytics.py | 63443 | 1684 | 5ebe7c6ea754 | PY
test_annotations.py | 9061 | 264 | 4c929131f4d2 | PY
test_api.py | 32621 | 750 | 1a12dd60b9e8 | PY
test_build_parallel_research_bundle.py | 17332 | 285 | 29d3a87f5192 | PY
test_compare_ball_pipeline_trace.py | 8729 | 206 | 727863d149a9 | PY
test_compare_local_remote_proof.py | 8020 | 227 | 5da5bb7d4004 | PY
test_dashboard.py | 7269 | 163 | 7325ed827ee1 | PY
test_daytona.py | 97042 | 2457 | e24074b2f99e | PY
test_daytona_release_policy.py | 15234 | 418 | 801df26b0798 | PY
test_documented_startup.py | 14073 | 422 | dc58fe82d808 | PY
test_export_flatteners.py | 1363 | 55 | 78dfcea10306 | PY
test_export_label_overlay_audit_reset_order.py | 2182 | 67 | 164af8ec1443 | PY
test_external_soccernet_product_route.py | 4936 | 122 | 96cf44810df3 | PY
test_external_soccertrack_analysis_product_route.py | 5881 | 142 | 9efcdeec2114 | PY
test_external_soccertrack_product_route.py | 4329 | 110 | 01586856111d | PY
test_football_external_real_eval_chain_common.py | 4222 | 124 | d8540f1d60c0 | PY
test_gpu_contract.py | 6095 | 155 | ae6f40c11a08 | PY
test_gpu_worker.py | 135242 | 3448 | d0403b4d75c1 | PY
test_job_metadata.py | 2723 | 88 | b1e6a82ab364 | PY
test_jobs.py | 6412 | 164 | 19bc9f2f2b0c | PY
test_lap_shim.py | 685 | 33 | 58fd5afe9267 | PY
test_llm.py | 4578 | 118 | d27cabbcc021 | PY
test_memory_bank_structure.py | 907 | 27 | 35dc1907be57 | PY
test_operational_docs.py | 10772 | 255 | f10e2a20b18a | PY
test_processor.py | 63097 | 1597 | 809429593b23 | PY
test_promote_selected_cluster_for_proof.py | 1363 | 36 | ae4f4468c86e | PY
test_proof_summary.py | 2914 | 73 | d383b78184db | PY
test_release_evidence.py | 40326 | 882 | 2fd6a5e9f7b9 | PY
test_release_manifest.py | 18477 | 505 | 762bd2e5f28c | PY
test_release_preflight.py | 67798 | 1747 | 41bf72129900 | PY
test_remote_contracts.py | 79050 | 1809 | a84fb6fbecf2 | PY
test_remote_worker.py | 36299 | 1019 | b0dcf77db966 | PY
test_report_export.py | 3171 | 90 | 33e788b8a15c | PY
test_run_benchmark_suite.py | 17376 | 473 | 871d67ab00f3 | PY
test_run_benchmarks.py | 107295 | 2556 | 462f783392fc | PY
test_run_canonical_match_bundle_export.py | 3978 | 99 | 3b3f40a0ef02 | PY
test_run_clip_manifest_expansion.py | 17115 | 444 | 8795c0081955 | PY
test_run_daytona_gpu_smoke.py | 34791 | 813 | ebcd9b936ab1 | PY
test_run_detector_breadth_batch.py | 3361 | 98 | 7ead2c87395f | PY
test_run_football_external_benchmark_bounded_execution_smoke.py | 7192 | 164 | 73c52d667018 | PY
test_run_football_external_benchmark_execution_approval.py | 5905 | 133 | e319e1f8a19e | PY
test_run_football_external_benchmark_harness_prep.py | 6228 | 141 | 4a84095d675e | PY
test_run_football_external_benchmark_harness_smoke.py | 8486 | 204 | 6256bf39dd4f | PY
test_run_football_external_benchmark_lane_closeout.py | 8075 | 177 | f8d8e0973159 | PY
test_run_football_external_benchmark_operationalization_plan.py | 6695 | 138 | 148c98a535bb | PY
test_run_football_external_benchmark_product_decision_surface.py | 9076 | 179 | 7d66ff5f71a0 | PY
test_run_football_external_benchmark_product_decision_surface_route_implementation.py | 8181 | 173 | ca46a16306b7 | PY
test_run_football_external_benchmark_product_ui_binding.py | 5272 | 116 | b41573626020 | PY
test_run_football_external_benchmark_product_ui_route_implementation.py | 6012 | 127 | 5bd590a87b99 | PY
test_run_football_external_benchmark_real_evaluation_chain.py | 6776 | 147 | e4548394243e | PY
test_run_football_external_benchmark_real_evaluation_design.py | 5757 | 111 | 2f4165d0d93b | PY
test_run_football_external_benchmark_report_smoke.py | 4771 | 115 | 7d606cd97326 | PY
test_run_football_external_dataset_access_review.py | 8543 | 180 | 2e6f3515b880 | PY
test_run_football_external_safe_adapter_fixture_implementation.py | 6325 | 138 | 0f21bd60566b | PY
test_run_football_external_safe_source_adapter_smoke_test.py | 9501 | 222 | 63e60d136e96 | PY
test_run_football_external_safe_source_controlled_sample_fetch.py | 5230 | 117 | 1ee1ad0e6019 | PY
test_run_football_external_safe_source_sample_download_approval.py | 5355 | 111 | 54d043bcdb60 | PY
test_run_football_external_safe_source_sample_ingestion_plan.py | 7149 | 157 | d384e95fbcba | PY
test_run_football_external_soccernet_analysis_product_api_smoke.py | 6854 | 146 | 38dac63807e0 | PY
test_run_football_external_soccernet_analysis_product_lane_closeout.py | 5342 | 117 | cbf8de61bfa1 | PY
test_run_football_external_soccernet_analysis_product_ui_binding.py | 6987 | 143 | ccbfeade9382 | PY
test_run_football_external_soccernet_analysis_product_ui_route_implementation.py | 5171 | 119 | cc3d54db38fd | PY
test_run_football_external_soccernet_api_listing_probe.py | 7547 | 181 | 79b8470417d9 | PY
test_run_football_external_soccernet_api_metadata_probe.py | 6224 | 146 | 48fe1649d0bb | PY
test_run_football_external_soccernet_benchmark_adapter_contract_prep.py | 5638 | 122 | 146b2892a556 | PY
test_run_football_external_soccernet_bounded_analysis_execution.py | 5733 | 124 | 5709c41adf4f | PY
test_run_football_external_soccernet_bounded_analysis_execution_approval.py | 5508 | 120 | 7e7b1b9514b8 | PY
test_run_football_external_soccernet_bounded_analysis_lane_closeout.py | 4017 | 89 | 35b47a1b1aee | PY
test_run_football_external_soccernet_bounded_analysis_report_smoke.py | 4580 | 101 | 9afabc318a3b | PY
test_run_football_external_soccernet_bounded_product_validation_execution.py | 9247 | 228 | 627e9422b1a8 | PY
test_run_football_external_soccernet_bounded_product_validation_execution_approval.py | 7696 | 154 | 922efade503f | PY
test_run_football_external_soccernet_bounded_product_validation_plan.py | 7355 | 177 | 57ba85329c04 | PY
test_run_football_external_soccernet_bounded_product_validation_report_binding.py | 5860 | 117 | a3dd8cf45616 | PY
test_run_football_external_soccernet_broader_validation_choice.py | 2773 | 64 | 42e753ae7784 | PY
test_run_football_external_soccernet_controlled_label_metadata_probe.py | 6294 | 134 | 28f5ba08112e | PY
test_run_football_external_soccernet_controlled_label_sample_fetch.py | 7788 | 177 | d8e0eda182ef | PY
test_run_football_external_soccernet_controlled_label_sample_fetch_approval.py | 6193 | 133 | 01309d1effc5 | PY
test_run_football_external_soccernet_controlled_video_sample_fetch.py | 5270 | 113 | 4deec1ad15a7 | PY
test_run_football_external_soccernet_detector_miss_capture_and_label_queue.py | 7825 | 199 | 22649a04d32d | PY
test_run_football_external_soccernet_detector_miss_manual_review_resolution.py | 8195 | 181 | 29fdde4d2b03 | PY
test_run_football_external_soccernet_event_adapter_fixture_materialization.py | 4675 | 98 | 947037303d2e | PY
test_run_football_external_soccernet_event_adapter_smoke_test.py | 4252 | 93 | e243a7942d99 | PY
test_run_football_external_soccernet_event_benchmark_smoke.py | 4200 | 92 | 376183ed9c8c | PY
test_run_football_external_soccernet_event_lane_closeout.py | 6626 | 143 | 5aa4db20d987 | PY
test_run_football_external_soccernet_event_report_contract_prep.py | 4883 | 102 | c1356475971c | PY
test_run_football_external_soccernet_event_report_product_integration.py | 5173 | 108 | 5afe35fb111d | PY
test_run_football_external_soccernet_event_report_smoke.py | 5141 | 117 | 0975bafa87a5 | PY
test_run_football_external_soccernet_full_analysis_execution.py | 5361 | 118 | 4df9429ea885 | PY
test_run_football_external_soccernet_full_analysis_execution_approval.py | 5718 | 124 | c46025b40238 | PY
test_run_football_external_soccernet_full_analysis_lane_closeout.py | 4009 | 89 | 361920343e3d | PY
test_run_football_external_soccernet_full_analysis_product_integration.py | 6926 | 150 | 4ec9eeee42c8 | PY
test_run_football_external_soccernet_full_analysis_report_smoke.py | 4480 | 99 | b48b47a4bbf8 | PY
test_run_football_external_soccernet_label_fetch_contract_repair.py | 4388 | 94 | 8fdbda74590e | PY
test_run_football_external_soccernet_label_schema_ingestion_probe.py | 5097 | 104 | 76e52217cc7e | PY
test_run_football_external_soccernet_nda_api_access_approval.py | 4243 | 91 | c972bdf5ae31 | PY
test_run_football_external_soccernet_real_sample_product_pipeline_training_decision.py | 8098 | 187 | 582a61c537f2 | PY
test_run_football_external_soccernet_split_archive_access_review.py | 6751 | 144 | 186ec983d060 | PY
test_run_football_external_soccernet_split_archive_range_index_probe.py | 6050 | 132 | c09723a9ed72 | PY
test_run_football_external_soccernet_split_archive_size_probe.py | 6041 | 129 | 8ee0ce21bcd4 | PY
test_run_football_external_soccernet_video_analysis_dry_run.py | 4804 | 111 | 6bdee9007607 | PY
test_run_football_external_soccernet_video_analysis_dry_run_approval.py | 5626 | 116 | 08c3fe0382e3 | PY
test_run_football_external_soccernet_video_analysis_dry_run_product_bridge_smoke.py | 4185 | 89 | 7c7af846b9f9 | PY
test_run_football_external_soccernet_video_frame_probe.py | 4059 | 99 | c8417c87d3ba | PY
test_run_football_external_soccernet_video_member_extract.py | 5321 | 116 | 0f8bce6de606 | PY
test_run_football_external_soccernet_video_member_extract_approval.py | 3522 | 80 | 8392a78d16e1 | PY
test_run_football_external_soccernet_video_product_path_smoke.py | 4118 | 94 | bd4da01d0abe | PY
test_run_football_external_soccernet_video_sample_download_approval.py | 3970 | 80 | a37c02a32d24 | PY
test_run_football_external_soccernet_video_sample_probe.py | 3713 | 85 | 87c80c4f467f | PY
test_run_football_external_soccernet_video_to_analysis_bridge_prep.py | 4647 | 99 | b783a72a778b | PY
test_run_football_external_soccernet_zip_label_member_extract.py | 6419 | 144 | c1d38989ee4e | PY
test_run_football_external_soccernet_zip_label_member_extract_approval.py | 7336 | 158 | ad135438b618 | PY
test_run_football_external_soccertrack_adapter_smoke_test.py | 7117 | 161 | 8615fdc0490a | PY
test_run_football_external_soccertrack_analysis_product_lane_closeout.py | 5606 | 121 | c26c665f6b67 | PY
test_run_football_external_soccertrack_analysis_product_ui_binding.py | 5975 | 124 | c194734b9bf9 | PY
test_run_football_external_soccertrack_analysis_product_ui_route_implementation.py | 5689 | 125 | 78f57a2de169 | PY
test_run_football_external_soccertrack_analysis_report_smoke.py | 6878 | 148 | 993ae0a7db73 | PY
test_run_football_external_soccertrack_authenticated_fixture_access_approval.py | 5313 | 108 | f0634ab80ee3 | PY
test_run_football_external_soccertrack_controlled_sample_fetch.py | 7410 | 165 | e3aa46f7c7df | PY
test_run_football_external_soccertrack_fixture_source_access_review.py | 5447 | 115 | 92b6a0315854 | PY
test_run_football_external_soccertrack_google_drive_bounded_fixture_fetch.py | 8805 | 184 | 0bfbb0677d7f | PY
test_run_football_external_soccertrack_google_drive_fixture_access_probe.py | 5575 | 115 | 21fe91b69561 | PY
test_run_football_external_soccertrack_lane_closeout.py | 8733 | 179 | e5327724116c | PY
test_run_football_external_soccertrack_match_bundle_bridge_smoke.py | 5839 | 130 | 5c3828c756e7 | PY
test_run_football_external_soccertrack_metadata_adapter_smoke.py | 5183 | 106 | c22d0bf25788 | PY
test_run_football_external_soccertrack_product_route_smoke.py | 5077 | 108 | c14502f4faad | PY
test_run_football_external_soccertrack_sample_fixture_materialization.py | 5607 | 113 | df6ddc275339 | PY
test_run_football_external_soccertrack_sample_fixture_materialization_approval.py | 6627 | 136 | 7750955f2ad8 | PY
test_run_football_external_soccertrack_sample_ingestion_contract_prep.py | 7030 | 134 | 664029cfc0c0 | PY
test_run_football_external_soccertrack_sample_schema_probe.py | 6376 | 139 | 9d6be82d6134 | PY
test_run_football_external_soccertrack_schema_doc_fetch.py | 5959 | 144 | 526ce9c496c0 | PY
test_run_football_external_soccertrack_schema_doc_fetch_approval.py | 6160 | 139 | 8ca556f987ec | PY
test_run_football_external_soccertrack_schema_doc_parse.py | 8234 | 183 | c7f60142cfb0 | PY
test_run_guerilla.py | 323008 | 8761 | 09062a9593ca | PY
test_run_local_app_path_proof.py | 35096 | 763 | 8a00c0c5df69 | PY
test_run_product_video_to_analysis_finish_line_execution.py | 6194 | 139 | 7e9c058a1810 | PY
test_run_product_video_to_analysis_normal_storage_smoke.py | 4148 | 89 | c556e96ef1d2 | PY
test_run_product_video_to_analysis_smoke.py | 3758 | 96 | bad46f0fb639 | PY
test_run_product_video_to_analysis_smoke_isolated.py | 4318 | 97 | 955e109989b0 | PY
test_run_promoted_touchline_detector_candidate_retention_delta_analysis.py | 11431 | 298 | 7dda9ef9ab77 | PY
test_run_promoted_touchline_detector_candidate_source_robustness_validation.py | 24009 | 534 | bd44320c865d | PY
test_run_promoted_v6_accepted_retention_guardrail_audit.py | 6897 | 187 | 680410120d99 | PY
test_run_promoted_v6_baseline_denominator_review_refresh.py | 8424 | 173 | f8b39ed2c9da | PY
test_run_promoted_v6_candidate_proposal_generation_fix.py | 11683 | 293 | a831eef87aec | PY
test_run_promoted_v6_failing_source_review_refresh.py | 5961 | 160 | ce3c46b69601 | PY
test_run_promoted_v6_global_accepted_gap_audit.py | 6655 | 156 | 0b89c077768d | PY
test_run_promoted_v6_global_reachable_acceptance_probe.py | 4774 | 122 | 119348939a2d | PY
test_run_promoted_v6_gold_truth_bootstrap.py | 10661 | 266 | 561a9061594f | PY
test_run_promoted_v6_gold_truth_seed_refuted_refresh.py | 9822 | 239 | 2e38b5615848 | PY
test_run_promoted_v6_manual_review_denominator_expansion.py | 3728 | 92 | 9e7b0277c80c | PY
test_run_promoted_v6_manual_review_denominator_resolution.py | 4651 | 107 | 9b2451b5bb5b | PY
test_run_promoted_v6_manual_review_expansion.py | 9880 | 244 | f5f8687063a5 | PY
test_run_promoted_v6_manual_review_expansion_resolution.py | 8991 | 220 | 57c5e71fd0d1 | PY
test_run_promoted_v6_manual_review_followthrough_batch.py | 10356 | 249 | a1f5424d9f30 | PY
test_run_promoted_v6_manual_review_resolution_batch.py | 8604 | 204 | 969236dc71b3 | PY
test_run_promoted_v6_proof_diagnostic_instrumentation_refresh.py | 6982 | 179 | 8a58ee245bf3 | PY
test_run_promoted_v6_proof_runtime_frame_diagnostics.py | 5399 | 145 | 4ad762543709 | PY
test_run_promoted_v6_proposal_selection_followthrough_fix.py | 10966 | 282 | 1a4f3edbd67b | PY
test_run_promoted_v6_residual_segment_selection_microfix.py | 9447 | 243 | 15024009b8a4 | PY
test_run_promoted_v6_reviewed_followthrough_selection_fix.py | 10032 | 241 | ae701e2b4bdf | PY
test_run_promoted_v6_reviewed_positive_acceptance_fix.py | 10070 | 257 | a8f2b499e347 | PY
test_run_promoted_v6_reviewed_positive_anchor_seed.py | 3299 | 80 | 040188e01954 | PY
test_run_promoted_v6_reviewed_positive_crop_geometry_scale_fix.py | 6647 | 154 | 522071d803ea | PY
test_run_promoted_v6_reviewed_positive_crop_reinference_audit.py | 5452 | 122 | e9d36ae258c7 | PY
test_run_promoted_v6_reviewed_positive_micro_validation.py | 11536 | 291 | bd4c2a5dfcee | PY
test_run_promoted_v6_reviewed_positive_proposal_generation_fix.py | 4933 | 122 | b8abb698fa82 | PY
test_run_promoted_v6_reviewed_positive_residual_proposal_generation_fix.py | 9353 | 219 | be7fc6ef91f8 | PY
test_run_promoted_v6_reviewed_positive_selection_followthrough_fix.py | 17744 | 423 | 8d4bdba00b13 | PY
test_run_promoted_v6_source_manifest_and_gold_truth_refresh.py | 9227 | 248 | 7a2b4eb26ade | PY
test_run_promoted_v6_support_viability_truth_fix.py | 8016 | 206 | 3fc51b80d101 | PY
test_run_promoted_v6_touchline_detector_candidate_v7_training.py | 6267 | 176 | 218b7703e72b | PY
test_run_promoted_v6_touchline_detector_candidate_v7_training_data_refresh.py | 7394 | 188 | 283b52019718 | PY
test_run_promoted_v6_touchline_detector_candidate_v7_training_prep.py | 9254 | 239 | d2fe4d267dbc | PY
test_run_promoted_v7_2_source_robustness_validation.py | 6443 | 143 | a5127fdfd818 | PY
test_run_recovery_inventory.py | 26358 | 745 | 4f19b715b300 | PY
test_run_recovery_worktree_salvage.py | 36397 | 948 | b3cfdc9ba8ab | PY
test_run_source_robustness_batch.py | 181857 | 4202 | 42a3ca58bada | PY
test_run_touchline_detector_candidate_evaluation.py | 7616 | 179 | 6be612d7486f | PY
test_run_touchline_detector_candidate_failure_analysis.py | 28611 | 640 | 3ee08d27919b | PY
test_run_touchline_detector_candidate_model_data_quality_fix.py | 1215 | 35 | d8321ba20cfb | PY
test_run_touchline_detector_candidate_promotion_validation.py | 8176 | 187 | 3bd16002bbdd | PY
test_run_touchline_detector_candidate_proposal_signal_generation_fix.py | 2477 | 60 | f3a642efb302 | PY
test_run_touchline_detector_candidate_v7_evaluation_failure_analysis.py | 7720 | 190 | 08654b674b3e | PY
test_run_touchline_review_densification_batch.py | 25378 | 596 | f2359ed84364 | PY
test_run_touchline_training_data_curation_batch.py | 21408 | 558 | 32f352a511a4 | PY
test_run_v7_1_crop_manifest_consistency_refresh.py | 7289 | 164 | 7a6963e8af82 | PY
test_run_v7_1_crop_probe_precision_guardrail_audit.py | 8542 | 185 | ac0f1d27780b | PY
test_run_v7_1_export_label_overlay_audit.py | 8057 | 199 | 440d7e4d7486 | PY
test_run_v7_1_full_pipeline_non_promotion_eval.py | 7532 | 169 | 9715df0d6bcd | PY
test_run_v7_1_positive_candidate_mining_expansion.py | 7063 | 149 | 23eb7db6573a | PY
test_run_v7_1_positive_candidate_mining_expansion_v3_pitch_filtered.py | 6324 | 148 | 89948fed0d7e | PY
test_run_v7_1_positive_diversity_manual_review_expansion.py | 6372 | 131 | 85fd9da7a36d | PY
test_run_v7_1_positive_diversity_manual_review_resolution.py | 13556 | 286 | 1c2265ad6e75 | PY
test_run_v7_1_positive_diversity_refresh.py | 6566 | 154 | 50151e15253a | PY
test_run_v7_1_positive_diversity_review_evidence_package.py | 2622 | 65 | 91a3a1367a26 | PY
test_run_v7_1_tiny_overfit_retry_with_verified_config.py | 6290 | 152 | c1cc0fc72bd6 | PY
test_run_v7_1_tiny_overfit_sanity_train.py | 519 | 18 | 4e2073b95d28 | PY
test_run_v7_1_training_config_or_export_debug.py | 4953 | 105 | 77cb7d4bdf1d | PY
test_run_v7_1_training_manifest_prep.py | 5103 | 122 | 5dc9f0d37aa2 | PY
test_run_v7_2_crop_probe_precision_guardrail_audit.py | 8293 | 178 | e8a474fda3c9 | PY
test_run_v7_2_default_path_edge_share_reduction.py | 9206 | 224 | 9c49fb8fa6ca | PY
test_run_v7_2_default_path_inboard_ball_recovery.py | 8046 | 206 | 22616a840274 | PY
test_run_v7_2_export_label_overlay_audit.py | 9288 | 200 | 6fbad16a453e | PY
test_run_v7_2_full_pipeline_non_promotion_eval.py | 11765 | 268 | a80ad7dcff48 | PY
test_run_v7_2_post_runtime_default_source_robustness_validation.py | 8961 | 181 | 51efab887040 | PY
test_run_v7_2_promotion_readiness_validation.py | 10391 | 249 | ff71fd4a7537 | PY
test_run_v7_2_runtime_default_change_validation.py | 10762 | 220 | 37c2f14c1fb4 | PY
test_run_v7_2_runtime_default_rollout_closeout.py | 8867 | 188 | 7457d6a2aac1 | PY
test_run_v7_2_runtime_registry_product_path_binding.py | 4059 | 88 | 2e83d33d3b9c | PY
test_run_v7_2_source_robustness_default_blocker_analysis.py | 6616 | 144 | bded50af6bbf | PY
test_run_v7_2_source_robustness_route_contract_fix.py | 5197 | 123 | 530b17a953c1 | PY
test_run_v7_2_training_manifest_prep.py | 6205 | 131 | e2835391c0f4 | PY
test_run_v7_3_crop_probe_precision_guardrail_audit.py | 8490 | 183 | 13f1f8bf9b07 | PY
test_run_v7_3_export_label_overlay_audit.py | 7647 | 177 | 64f718425b64 | PY
test_run_v7_3_full_pipeline_non_promotion_eval.py | 8858 | 199 | d47a41fda0b7 | PY
test_run_v7_3_post_runtime_default_source_robustness_validation.py | 8200 | 170 | b4d9704064dc | PY
test_run_v7_3_promotion_readiness_validation.py | 11919 | 281 | 339c8edac427 | PY
test_run_v7_3_runtime_default_change_validation.py | 9612 | 207 | 39a1caa74f75 | PY
test_run_v7_3_runtime_default_rollout_closeout.py | 7778 | 170 | 07bcb11437b1 | PY
test_run_v7_3_training_manifest_prep_from_soccernet_real_misses.py | 8590 | 196 | 51c198b62bbf | PY
test_run_v7_4_training_decision_from_real_misses.py | 4266 | 99 | 364f2d57ca5b | PY
test_run_v7_negative_crop_conversion_plan.py | 5313 | 126 | 1f8407deba74 | PY
test_run_v7_negative_semantics_review.py | 6942 | 163 | d9ed8f06e49f | PY
test_run_v7_probe_assist_integration_audit.py | 6205 | 145 | 639ae57ee686 | PY
test_run_v7_probe_precision_guardrail_audit.py | 7407 | 189 | eb617358af45 | PY
test_run_v7_probe_threshold_contract_fix.py | 4322 | 108 | 32aa8860fce9 | PY
test_run_v7_probe_threshold_preprocessing_fix.py | 5827 | 125 | 16558106d3cb | PY
test_run_v7_training_data_quality_refresh.py | 6818 | 156 | 98122d837e07 | PY
test_run_video_to_analysis_acceptance_report_product_backlog.py | 4311 | 96 | 9c892aff2a00 | PY
test_run_video_to_analysis_acceptance_report_route_binding.py | 5141 | 108 | 92fe7d534d66 | PY
test_run_video_to_analysis_bounded_next_sample_execution_chain.py | 10534 | 188 | 553aa8a77c0a | PY
test_run_video_to_analysis_broader_real_video_acceptance_approval.py | 3718 | 80 | 51f79cded5e3 | PY
test_run_video_to_analysis_broader_real_video_acceptance_closeout.py | 3283 | 71 | 71d4e1b37ce1 | PY
test_run_video_to_analysis_broader_real_video_acceptance_execution.py | 5158 | 111 | cbff0d05783f | PY
test_run_video_to_analysis_broader_real_video_acceptance_suite_prep.py | 3489 | 80 | 1dbcce9f12b6 | PY
test_run_video_to_analysis_current_release_acceptance_decision_surface.py | 12488 | 299 | 1cc3195b8836 | PY
test_run_video_to_analysis_detector_evaluation_reentry_chain.py | 17183 | 368 | 715084ee4eb9 | PY
test_run_video_to_analysis_finish_line_closeout_chain.py | 5172 | 110 | 153634cea41d | PY
test_run_video_to_analysis_finish_line_completion_summary.py | 3408 | 78 | 7473f62e0d96 | PY
test_run_video_to_analysis_finish_line_execution_approval.py | 4537 | 99 | 21527933006a | PY
test_run_video_to_analysis_finish_line_normal_storage_closeout.py | 3506 | 80 | 5d903ec7d96d | PY
test_run_video_to_analysis_finish_line_normal_storage_execution_approval.py | 3905 | 85 | f3fff0bb5b5c | PY
test_run_video_to_analysis_finish_line_operational_readiness.py | 3629 | 82 | 75aaef6c0343 | PY
test_run_video_to_analysis_finish_line_product_acceptance_closeout.py | 3706 | 83 | 6819f4a3c58d | PY
test_run_video_to_analysis_finish_line_product_execution_approval.py | 4955 | 105 | 54cd4698e9cc | PY
test_run_video_to_analysis_finish_line_route_polish.py | 4805 | 112 | e284f5bf287d | PY
test_run_video_to_analysis_finish_line_user_acceptance_trial.py | 4961 | 109 | 01d3bf76b09e | PY
test_run_video_to_analysis_growth_lane_closeout_readout.py | 9417 | 208 | 1db6ae476c82 | PY
test_run_video_to_analysis_manual_operator_release_decision.py | 4780 | 102 | 4e7dbb40e96d | PY
test_run_video_to_analysis_next_strategic_lane_selection.py | 10527 | 239 | 3ec1587db1af | PY
test_run_video_to_analysis_operational_backlog_prioritization.py | 2935 | 54 | ce9a39fa4dd4 | PY
test_run_video_to_analysis_operational_roadmap_sprint.py | 5320 | 96 | 13f2f444d646 | PY
test_run_video_to_analysis_operator_dashboard_polish.py | 4442 | 84 | e4656855dbaa | PY
test_run_video_to_analysis_operator_handoff_pack.py | 5298 | 115 | 97277ea1abff | PY
test_run_video_to_analysis_operator_handoff_route_binding.py | 5282 | 119 | 52c98046ad5e | PY
test_run_video_to_analysis_post_release_monitoring_closeout.py | 3694 | 78 | 226a5bfdccc2 | PY
test_run_video_to_analysis_post_release_monitoring_plan.py | 4497 | 99 | 29e8e2703a2d | PY
test_run_video_to_analysis_post_release_monitoring_route_binding.py | 5148 | 114 | 12932ca278e0 | PY
test_run_video_to_analysis_product_hardening_backlog.py | 3626 | 81 | f80e04dd2140 | PY
test_run_video_to_analysis_product_lane_closeout.py | 3593 | 78 | 97ae5e5160b3 | PY
test_run_video_to_analysis_promoted_runtime_operator_acceptance_trial.py | 7579 | 174 | d012bcee5f84 | PY
test_run_video_to_analysis_promoted_runtime_post_release_monitoring_chain.py | 10688 | 238 | 7fa232eb608d | PY
test_run_video_to_analysis_promoted_runtime_release_closeout_chain.py | 5761 | 126 | 9e8135606ec9 | PY
test_run_video_to_analysis_promotion_review_chain.py | 9697 | 211 | abd035539edb | PY
test_run_video_to_analysis_real_video_scaleout_execution_chain.py | 44295 | 791 | f2c2304e6985 | PY
test_run_video_to_analysis_release_acceptance_archive.py | 3322 | 74 | 3c8083e73678 | PY
test_run_video_to_analysis_release_candidate_closeout.py | 6077 | 134 | 50e4affc64cf | PY
test_run_video_to_analysis_release_readout_pack.py | 6531 | 142 | c2ec81febbad | PY
test_run_video_to_analysis_release_readout_route_binding.py | 5059 | 110 | c00d7f8726af | PY
test_run_video_to_analysis_roadmap_state_reconciliation.py | 6615 | 145 | 2ded050cfcab | PY
test_run_video_to_analysis_source_pool_replenishment_approval.py | 802 | 29 | 5c6664f1670c | PY
test_run_video_to_analysis_source_pool_replenishment_plan.py | 20897 | 449 | 490f1d144b70 | PY
test_run_video_to_analysis_steady_state_monitoring_cycle.py | 4485 | 91 | f2f2fe53424c | PY
test_run_video_to_analysis_storage_cleanup_approval.py | 7001 | 154 | 7b5bb346370f | PY
test_run_video_to_analysis_storage_cleanup_bounded_execution.py | 5191 | 105 | 4176c25f6baa | PY
test_run_video_to_analysis_storage_cleanup_closeout.py | 2556 | 49 | 704080b21dac | PY
test_run_video_to_analysis_storage_cleanup_dry_run_execution.py | 2769 | 54 | 78b81dd4f989 | PY
test_run_video_to_analysis_storage_cleanup_execution_approval.py | 4907 | 99 | 3faaadc65f22 | PY
test_run_video_to_analysis_storage_retention_and_artifact_hygiene.py | 3599 | 65 | e4de62d3a572 | PY
test_run_video_to_analysis_upload_to_analysis_walkthrough.py | 2807 | 66 | 6c3bb7824027 | PY
test_run_video_to_analysis_user_facing_release_readout.py | 4771 | 111 | 19aa08eb1628 | PY
test_run_video_to_analysis_v7_3_release_packaging_and_worktree_triage.py | 4993 | 106 | 90c482cdd3b3 | PY
test_runtime_options.py | 34382 | 889 | dfca54a103f0 | PY
test_semantic_search.py | 5758 | 157 | c385d73c6dc8 | PY
test_serve_football_external_soccernet_detector_miss_review_ui.py | 7163 | 166 | 5e579d131d0e | PY
test_serve_promoted_v6_manual_review_ui.py | 9528 | 239 | 811ee20b82d5 | PY
test_serve_v7_1_positive_diversity_review_ui.py | 9418 | 226 | a134c6021e1d | PY
test_settings.py | 7595 | 207 | e6a2cd5d0057 | PY
test_training_quality_gate.py | 14257 | 391 | 005af3774f69 | PY
test_trust_crops.py | 4737 | 103 | dadc9dca058a | PY
test_unattended_roadmap_loop.py | 9785 | 214 | 1e449c5d1f16 | PY
test_uploads.py | 3972 | 125 | a26bed4bd844 | PY
test_verify_script.py | 23942 | 647 | 96f391b7a39e | PY
test_video_pipeline.py | 6788 | 162 | 3216a320f362 | PY
test_worker.py | 2718 | 77 | ee846773da60 | PY
test_workflow_output_reset_contract.py | 1377 | 39 | 7f11ffb845df | PY
test_write_release_manifest.py | 13378 | 397 | bc4b3f8e47e9 | PY
```

### backend/tests/fixtures/daytona

```text
basename | bytes | lines | sha256-prefix | inspection
job-request.json | 134 | 1 | 6011853fdcfc | JSON
```

### backend/tests/fixtures

```text
basename | bytes | lines | sha256-prefix | inspection
sample_tracking.json | 1038 | 11 | 655aaddf051d | JSON
```

### docs

```text
basename | bytes | lines | sha256-prefix | inspection
PROJECT-EXPLANATION.md | 10787 | 195 | 2d635b61c158 | DOC
deep-research-report.md | 44883 | 695 | f95d0aee6e1c | DOC
foot-soccer-deepresearch.md | 44883 | 695 | f95d0aee6e1c | DOC
goal-1-12april-00-1am.md | 3042 | 50 | 46d795565cb0 | DOC
project-cleanup-report-2026-04-21.md | 6286 | 101 | d54d3dd3ac40 | DOC
project-review-2026-07-06.md | 9859 | 371 | 646927b272b3 | DOC
video-analysis-enhancement-playbook.md | 15499 | 610 | 42feb08e680e | DOC
video-analysis-research-brief.md | 18255 | 534 | d59aefb863b8 | DOC
video-to-analysis-finish-line-roadmap-completion-report-2026-05-08.md | 27762 | 721 | fe53904ec89f | DOC
video-to-analysis-finish-line-roadmap-guide.md | 90617 | 2355 | ba9f8348d4cc | DOC
video-to-analysis-growth-lane-closeout-readout-2026-05-09.md | 9430 | 321 | ac15f3f75d17 | DOC
video-to-analysis-user-facing-release-readout-2026-05-09.md | 5147 | 158 | 44627c6989c6 | DOC
```

### docs/archive/2026-08-19

```text
basename | bytes | lines | sha256-prefix | inspection
SESSION-HANDOFF.md | 401136 | 4677 | e4e87f334308 | DOC
activeContext.md | 269528 | 4795 | b3f014148c8a | DOC
checksums.json | 411 | 14 | 0d721227ce6b | JSON
currentRoadmap.md | 204765 | 5106 | 4a75c90509ed | DOC
```

### docs/archive/2026-08-24

```text
basename | bytes | lines | sha256-prefix | inspection
rejected-runpod-release.md | 558 | 5 | a74400083333 | DOC
```

### docs/archive

```text
basename | bytes | lines | sha256-prefix | inspection
README.md | 566 | 17 | 0cceb6ef1775 | DOC
emergent-foot.md | 157560 | 4421 | 28a215de536a | DOC
```

### docs/archive/plans

```text
basename | bytes | lines | sha256-prefix | inspection
2026-03-27-llm-report-context-upgrade.md | 11675 | 368 | 0b69ca97916f | DOC
2026-03-27-player-profiles-v2.md | 10766 | 387 | 38dad2efc3c0 | DOC
2026-03-27-reordered-roadmap.md | 5662 | 162 | d115d7da8c7f | DOC
2026-03-27-richer-event-intelligence.md | 15332 | 472 | 2c757dba8659 | DOC
2026-03-27-synced-video-playback.md | 13164 | 434 | 10dc7637c2ac | DOC
2026-03-28-match-report-export.md | 18897 | 558 | b94f6110a090 | DOC
2026-03-28-pdf-report-export.md | 16209 | 495 | b831fbbd140c | DOC
2026-03-30-semantic-search-implementation.md | 3311 | 100 | 7f16796ea2a1 | DOC
2026-04-07-local-video-upload-reliability-plan.md | 20103 | 591 | b129b9a044e0 | DOC
2026-04-08-event-richness-and-scale-up-plan.md | 18343 | 517 | ad7aa009d760 | DOC
2026-04-08-gpu-adoption-execution-plan.md | 12796 | 245 | 78821258b157 | DOC
2026-04-08-local-proof-to-gpu-handoff.md | 11184 | 339 | 435dae224727 | DOC
2026-04-09-coverage-quality-sprint-plan.md | 5973 | 135 | 4fdba867ddfc | DOC
2026-04-09-detector-fallback-quality-sprint-plan.md | 14410 | 424 | 901300bfdaef | DOC
2026-04-11-detector-autoresearch-loop-plan.md | 5752 | 79 | 8f37e2eea6a2 | DOC
2026-04-11-longer-clip-candidate-generation-sprint.md | 16067 | 448 | a8af80ab0d74 | DOC
2026-04-13-accepted-match-state-v1-sprint.md | 4287 | 99 | 7bb761b3e2d5 | DOC
2026-04-13-bounded-anchor-seed-proposal-sprint.md | 3478 | 82 | 2580e3fd1aab | DOC
2026-04-13-candidate-hygiene-promotion-sprint.md | 7300 | 203 | 2cdbe0a5ec9e | DOC
2026-04-13-observed-anchor-corridor-recovery-sprint.md | 21169 | 660 | 84605a4e2ff1 | DOC
2026-04-13-player-proposal-expansion-sprint.md | 7556 | 167 | ff8706a64104 | DOC
2026-04-13-pod-first-proof-recovery-sprint.md | 15960 | 487 | b1489cf47399 | DOC
2026-04-13-seed-centered-proposal-funnel-sprint.md | 4337 | 101 | 42faabab228d | DOC
2026-04-13-true-seed-centered-proposal-window-sprint.md | 3676 | 82 | 6b693c8f608f | DOC
2026-04-14-normal-ssh-pod-bootstrap-yolo11s-attack-a-sprint.md | 5580 | 147 | e304381af11a | DOC
2026-04-14-player-biased-seed-context-geometry-sprint.md | 6949 | 161 | 99a69206ac61 | DOC
2026-04-14-pod-first-yolo11s-attack-a-execution-sprint.md | 3458 | 88 | abff6e31f773 | DOC
2026-04-14-seed-to-box-context-activation-sprint.md | 4057 | 88 | 7640a346288e | DOC
2026-04-14-seed-window-hit-rate-ladder-sprint.md | 3812 | 86 | ff1cbc3d2fca | DOC
2026-04-14-seeded-window-scale-audit-hires-retry-serverless-sprint.md | 4491 | 95 | 19e2b0a6c908 | DOC
```

### docs/archive/research

```text
basename | bytes | lines | sha256-prefix | inspection
2026-04-11-platform-and-research-brief.md | 9480 | 242 | 28a7efa79999 | DOC
bottleneck-exit-analysis.md | 36024 | 700 | 7de90bc4cef2 | DOC
reference_implementations.md | 12477 | 300 | 6f061890dbfa | DOC
reference_implementations_analysis.md | 8951 | 261 | 59f8c246d174 | DOC
```

### docs/archive/root-notes

```text
basename | bytes | lines | sha256-prefix | inspection
Football Video Analysis Technical Research.md | 66000 | 317 | 1515a508e11d | DOC
GAP-ANALYSIS-REPORT.md | 34441 | 695 | cc39bb54b832 | DOC
Guerilla Analytics V1 - PRD.txt | 7973 | 60 | 1f614dfa587c | DOC
Guerilla Analytics_ Future Improvements.md | 63490 | 306 | 6ab38fdb8d65 | DOC
REVIEW-FINDINGS.md | 39231 | 760 | 29f4a9ca2250 | DOC
```

### docs/recovery/2026-08-19

```text
basename | bytes | lines | sha256-prefix | inspection
artifact-manifest.json | 9300 | 153 | 8faab94c6fe9 | JSON
current-tree-inventory.json | 517576 | 10614 | 33713edfce0c | JSON
current-tree-inventory.md | 113414 | 682 | f6223bacbd41 | DOC
raw-freeze-manifest.json | 11595 | 205 | e25ac2cb3a7f | JSON
raw-freeze-manifest.md | 6224 | 55 | 78b98a8e5ed1 | DOC
worktree-salvage-manifest.json | 147796 | 3471 | 3d59d46d2319 | JSON
```

### docs/recovery/2026-08-19/commit-groups

```text
basename | bytes | lines | sha256-prefix | inspection
generated-truth.paths.nul | 1559 | 1 | 37fe89ce4f43 | DOC
local-material.paths.nul | 22 | 1 | d11783e08808 | DOC
manual-review.paths.nul | 510 | 1 | a46310773202 | DOC
one-shot-batches.paths.nul | 15157 | 1 | 1bc8e2e63b25 | DOC
product-source.paths.nul | 13280 | 1 | 1ca6d686c1ad | DOC
release-truth.paths.nul | 268 | 1 | b54359ceac4f | DOC
tracked-deletions.paths.nul | 2197 | 1 | 95944fe770c5 | DOC
workflow.paths.nul | 6294 | 1 | 74e5b44cfb5b | DOC
```

### docs/recovery/2026-08-24

```text
basename | bytes | lines | sha256-prefix | inspection
daytona-gpu-smoke.md | 8588 | 77 | 030139311df2 | DOC
final-verification-report.md | 31897 | 176 | eabd3f4a59f7 | DOC
pre-cloud-independent-reviews.md | 2019 | 22 | f4e43c7870de | DOC
```

### docs/runbooks

```text
basename | bytes | lines | sha256-prefix | inspection
artifact-restore.md | 1007 | 17 | 4e90dc93ea62 | DOC
daytona-gpu-execution.md | 1573 | 35 | 6e1c741c8870 | DOC
```

### docs/status

```text
basename | bytes | lines | sha256-prefix | inspection
current.md | 6633 | 43 | 4299f6903d7a | DOC
```

### docs/superpowers/plans

```text
basename | bytes | lines | sha256-prefix | inspection
2026-04-11-active-now-systematic-roadmap.md | 13848 | 180 | 03376809927c | DOC
2026-04-19-current-state-report.md | 16638 | 252 | 4cf7a4fd1040 | DOC
2026-04-23-phase-3-v4-quality-gate-remediation.md | 1245 | 24 | 3f2b5bec3615 | DOC
2026-04-23-promoted-v6-failing-source-robustness-validation.md | 182621 | 2377 | 862f18fe8f8c | DOC
2026-04-23-touchline-detector-candidate-evaluation-v5.md | 16608 | 261 | 04f4a7a81514 | DOC
2026-04-23-touchline-detector-candidate-promotion-v6.md | 4557 | 72 | 9ad9383c1e12 | DOC
2026-05-03-football-external-benchmark-harness-prep.md | 9903 | 235 | 087683617263 | DOC
2026-05-03-promoted-v7-2-source-robustness-validation.md | 8264 | 177 | d56fe342a63b | DOC
2026-05-03-v7-2-full-pipeline-non-promotion-eval.md | 9834 | 228 | d1b7797064df | DOC
2026-05-03-v7-2-promotion-readiness-validation.md | 11592 | 264 | e4e901eb1910 | DOC
2026-05-03-v7-2-route-contract-review-hardening.md | 3908 | 92 | f1820172847a | DOC
2026-05-03-v7-2-source-robustness-default-blocker-analysis.md | 6248 | 147 | 99bb49eac7c4 | DOC
2026-05-03-v7-2-source-robustness-route-contract-fix.md | 5972 | 145 | 5a0fe071142f | DOC
2026-05-04-canonical-match-bundle-export.md | 2196 | 47 | c53d7643700d | DOC
2026-05-04-football-external-soccernet-api-listing-probe.md | 4006 | 89 | 188131c9ed71 | DOC
2026-05-04-football-external-soccernet-benchmark-adapter-contract-prep.md | 1481 | 36 | 22e7c848b09d | DOC
2026-05-04-football-external-soccernet-bounded-analysis-execution-approval.md | 3928 | 109 | a3877464398d | DOC
2026-05-04-football-external-soccernet-bounded-analysis-execution.md | 3607 | 100 | 53768cca192e | DOC
2026-05-04-football-external-soccernet-bounded-analysis-lane-closeout.md | 2181 | 62 | 32e03edc5c01 | DOC
2026-05-04-football-external-soccernet-bounded-analysis-report-smoke.md | 2163 | 60 | f89640009de7 | DOC
2026-05-04-football-external-soccernet-controlled-label-metadata-probe.md | 2865 | 71 | 8ece72d1ab44 | DOC
2026-05-04-football-external-soccernet-controlled-video-sample-fetch.md | 1612 | 47 | 6aa8acf7991d | DOC
2026-05-04-football-external-soccernet-event-adapter-smoke-test.md | 1548 | 43 | 476874a26ea9 | DOC
2026-05-04-football-external-soccernet-event-benchmark-smoke.md | 1328 | 35 | f7336148b38d | DOC
2026-05-04-football-external-soccernet-event-lane-closeout.md | 1746 | 52 | c4e00c337f23 | DOC
2026-05-04-football-external-soccernet-event-report-product-integration.md | 1648 | 50 | 5d21fe7c5dc9 | DOC
2026-05-04-football-external-soccernet-event-report-smoke.md | 1318 | 42 | 912b733a817a | DOC
2026-05-04-football-external-soccernet-full-analysis-execution-approval.md | 3633 | 95 | 85c1ea3a5752 | DOC
2026-05-04-football-external-soccernet-full-analysis-execution.md | 2135 | 60 | d16969f217ad | DOC
2026-05-04-football-external-soccernet-full-analysis-lane-closeout.md | 1477 | 31 | 79c13c8e1449 | DOC
2026-05-04-football-external-soccernet-full-analysis-report-smoke.md | 1454 | 30 | 9f03b45da48a | DOC
2026-05-04-football-external-soccernet-label-fetch-contract-repair.md | 2831 | 73 | ec956420d583 | DOC
2026-05-04-football-external-soccernet-label-member-range-pipeline.md | 2762 | 72 | cc43ef399298 | DOC
2026-05-04-football-external-soccernet-split-archive-access-review.md | 2286 | 52 | 58ee154de8d2 | DOC
2026-05-04-football-external-soccernet-video-analysis-dry-run-approval.md | 2797 | 52 | 37f4234b63ee | DOC
2026-05-04-football-external-soccernet-video-analysis-dry-run-product-bridge-smoke.md | 2757 | 51 | ae24d069ab18 | DOC
2026-05-04-football-external-soccernet-video-analysis-dry-run.md | 2924 | 58 | d93072bb61de | DOC
2026-05-04-football-external-soccernet-video-frame-probe.md | 1378 | 48 | cf4f773b0105 | DOC
2026-05-04-football-external-soccernet-video-member-extract-approval.md | 1601 | 46 | ea85313eb88c | DOC
2026-05-04-football-external-soccernet-video-member-extract.md | 1671 | 51 | 4f9f3e921f32 | DOC
2026-05-04-football-external-soccernet-video-product-path-smoke.md | 1379 | 47 | d16fc5fec5e6 | DOC
2026-05-04-football-external-soccernet-video-sample-download-approval.md | 1626 | 47 | 4aa7de9acd82 | DOC
2026-05-04-football-external-soccernet-video-sample-probe.md | 1456 | 46 | ae083307ca26 | DOC
2026-05-04-football-external-soccernet-video-to-analysis-bridge-prep.md | 4450 | 104 | 92618575e80d | DOC
2026-05-04-product-video-to-analysis-smoke.md | 2276 | 46 | 5e14c7a59d7f | DOC
2026-05-04-v7-2-runtime-registry-product-path-binding.md | 3574 | 88 | 42e775264a53 | DOC
2026-05-05-football-external-benchmark-bounded-execution-smoke.md | 2984 | 68 | 4a7c22ad98e2 | DOC
2026-05-05-football-external-benchmark-execution-approval.md | 2870 | 66 | 4160340d8e6c | DOC
2026-05-05-football-external-benchmark-harness-prep.md | 2830 | 66 | fa8eb0e12c7d | DOC
2026-05-05-football-external-benchmark-harness-smoke.md | 2851 | 68 | 32e731233646 | DOC
2026-05-05-football-external-benchmark-lane-closeout.md | 2457 | 63 | c359099997d3 | DOC
2026-05-05-football-external-benchmark-operationalization-plan.md | 2763 | 63 | dde1046f83be | DOC
2026-05-05-football-external-benchmark-product-decision-route-implementation.md | 1634 | 27 | 99fce01fb4e6 | DOC
2026-05-05-football-external-benchmark-product-decision-surface.md | 2964 | 64 | c8b3c3c86ae7 | DOC
2026-05-05-football-external-benchmark-product-ui-binding.md | 2786 | 66 | 5f89ef63b2d9 | DOC
2026-05-05-football-external-benchmark-product-ui-route-implementation.md | 3040 | 68 | 9bf86313e759 | DOC
2026-05-05-football-external-benchmark-real-evaluation-chain.md | 1828 | 34 | 492bd0db380e | DOC
2026-05-05-football-external-benchmark-real-evaluation-design.md | 1560 | 26 | 9f325fa1158a | DOC
2026-05-05-football-external-benchmark-report-smoke.md | 2643 | 65 | 9559fe9f1663 | DOC
2026-05-05-football-external-soccernet-analysis-product-lane-closeout.md | 1629 | 47 | e3401e3413ab | DOC
2026-05-05-football-external-soccernet-analysis-product-ui-route-implementation.md | 1850 | 48 | 58350abfd0ce | DOC
2026-05-05-football-external-soccernet-full-analysis-product-integration.md | 1728 | 40 | cc7c01579bc9 | DOC
2026-05-05-football-external-soccertrack-authenticated-fixture-access-approval.md | 1457 | 38 | d372f4f68b64 | DOC
2026-05-05-football-external-soccertrack-controlled-sample-fetch.md | 1696 | 43 | f205e519b09e | DOC
2026-05-05-football-external-soccertrack-fixture-source-access-review.md | 1439 | 41 | 7cab4b5443c6 | DOC
2026-05-05-football-external-soccertrack-sample-fixture-materialization-approval.md | 1602 | 45 | 519749e4b5de | DOC
2026-05-05-football-external-soccertrack-sample-ingestion-contract-prep.md | 1765 | 48 | 38912462a243 | DOC
2026-05-05-football-external-soccertrack-sample-schema-probe.md | 1661 | 48 | 815ef2b08b03 | DOC
2026-05-05-football-external-soccertrack-schema-doc-fetch-approval.md | 1451 | 44 | 3ecdb0556d2a | DOC
2026-05-05-football-external-soccertrack-schema-doc-fetch.md | 1380 | 45 | b95febd640f0 | DOC
2026-05-05-football-external-soccertrack-schema-doc-parse.md | 1734 | 49 | b929cf8e5f48 | DOC
2026-05-05-housekeeping-direction-snapshot.md | 9192 | 233 | 02f6b7d66ef4 | DOC
2026-05-09-video-to-analysis-growth-lane-finish-roadmap.md | 15329 | 423 | 75bf56bb9d22 | DOC
2026-05-09-video-to-analysis-strategic-lane-priority-plan.md | 14978 | 465 | 71d10deb35da | DOC
2026-05-10-soccernet-real-sample-training-decision-cascade.md | 4037 | 81 | 8f2b71d11a58 | DOC
2026-05-11-codex-goal-autonomous-video-to-analysis-growth-marathon.md | 18830 | 488 | 2d5ec3ac482b | DOC
2026-05-11-codex-goal-video-to-analysis-bounded-chain-continuation.md | 14093 | 439 | a28aff941ac3 | DOC
2026-05-11-codex-goal-video-to-analysis-finishline-push.md | 15398 | 410 | f48d309a2aa1 | DOC
2026-05-11-codex-goal-video-to-analysis-scaleout-followup-marathon.md | 14469 | 442 | 379ce576b277 | DOC
2026-05-11-codex-goal-video-to-analysis-total-finishline.md | 23625 | 692 | 0b63c4d5002e | DOC
2026-08-19-exact-v7-3-preservation-commits.md | 81353 | 1387 | d90bfad77b4a | DOC
2026-08-19-project-operability-verification.md | 9944 | 111 | 8015b30da62d | DOC
2026-08-19-recovery-preservation.md | 9709 | 119 | f8456f870036 | DOC
2026-08-19-release-runtime-reproducibility.md | 11539 | 118 | da1b577a9f9a | DOC
2026-08-24-daytona-gpu-execution.md | 39703 | 883 | 19c91db57579 | DOC
2026-08-26-streamed-gpu-worker-results.md | 10112 | 208 | 5f9574c7569f | DOC
2026-08-29-generation-scoped-gpu-results.md | 22510 | 468 | f0f86ea299bf | DOC
2026-09-08-verifier-bound-release-evidence.md | 12958 | 260 | d9ead1efc62c | DOC
2026-09-09-daytona-smoke-recovery.md | 28761 | 723 | 4c57527e7664 | DOC
2026-09-09-daytona-worker-runtime-recovery.md | 44417 | 1036 | c980bcc3f8ff | DOC
2026-09-10-live-daytona-progress.md | 16340 | 363 | 07873c5a470e | DOC
2026-09-10-streamed-full-match-results.md | 18034 | 409 | 81cdef5831c0 | DOC
```

### docs/superpowers/specs

```text
basename | bytes | lines | sha256-prefix | inspection
2026-03-27-llm-report-context-upgrade-design.md | 7943 | 235 | 6a996111bedd | DOC
2026-03-27-player-profiles-v2-design.md | 9227 | 246 | 3d417e94a8bd | DOC
2026-03-27-richer-event-intelligence-design.md | 6852 | 191 | f8573a5382d3 | DOC
2026-03-27-synced-video-playback-design.md | 6597 | 215 | 9ac0568a1ccf | DOC
2026-03-28-match-report-export-design.md | 8655 | 242 | 7eee8ebf248c | DOC
2026-03-28-pdf-report-export-design.md | 6135 | 165 | 1feb0561cdc6 | DOC
2026-04-07-local-video-upload-reliability-design.md | 4860 | 145 | 3aed4504503a | DOC
2026-04-08-gpu-handoff-contract.md | 3104 | 138 | df3d5a15728c | DOC
2026-04-23-unattended-roadmap-loop.md | 8825 | 195 | 985498ee0db6 | DOC
2026-08-19-preservation-first-stabilization-design.md | 14825 | 283 | 58c49fc358c7 | DOC
2026-08-24-daytona-gpu-execution-design.md | 9800 | 145 | fc217bbce6dc | DOC
2026-08-26-streamed-gpu-worker-results-design.md | 3651 | 40 | 4a49e476478d | DOC
2026-08-29-generation-scoped-gpu-results-design.md | 11035 | 124 | 8c1c32e3954e | DOC
2026-09-08-verifier-bound-release-evidence-design.md | 7281 | 86 | 2c3b299bd14e | DOC
2026-09-09-daytona-smoke-recovery-design.md | 8555 | 92 | d71093c5d34f | DOC
2026-09-09-daytona-worker-runtime-recovery-design.md | 11802 | 139 | cc9e14b9562e | DOC
2026-09-10-streamed-full-match-results-and-live-progress-design.md | 11077 | 124 | 8397da191599 | DOC
```

### frontend

```text
basename | bytes | lines | sha256-prefix | inspection
.gitignore | 253 | 24 | fe718e7babb1 | DELEGATED-FRONTEND
README.md | 2555 | 73 | f58b5b17f83d | DELEGATED-FRONTEND
eslint.config.js | 616 | 23 | 4efe97b16d12 | DELEGATED-FRONTEND
index.html | 367 | 13 | 0ba0f15c878e | DELEGATED-FRONTEND
package-lock.json | 178900 | 5138 | 18a34360acb9 | DELEGATED-FRONTEND
package.json | 989 | 39 | 666af9c6f73f | DELEGATED-FRONTEND
tsconfig.app.json | 732 | 28 | 922bc5bfb41b | DELEGATED-FRONTEND
tsconfig.json | 119 | 7 | 770b4140bbb5 | DELEGATED-FRONTEND
tsconfig.node.json | 653 | 26 | c3dd0fb522fe | DELEGATED-FRONTEND
vite.config.ts | 618 | 32 | c61a3cd32be4 | DELEGATED-FRONTEND
```

### frontend/public

```text
basename | bytes | lines | sha256-prefix | inspection
meci_data.json | 28413 | 1 | 9d1cb0e95723 | DELEGATED-FRONTEND
vite.svg | 1497 | 1 | 4a748afd4439 | DELEGATED-FRONTEND
```

### frontend/src

```text
basename | bytes | lines | sha256-prefix | inspection
App.test.tsx | 745 | 21 | 383f9819b5d8 | DELEGATED-FRONTEND
App.tsx | 42695 | 995 | 886cfcfce946 | DELEGATED-FRONTEND
index.css | 240 | 12 | 5270a58b0e95 | DELEGATED-FRONTEND
main.tsx | 230 | 10 | 6e9e5807fcbd | DELEGATED-FRONTEND
```

### frontend/src/assets

```text
basename | bytes | lines | sha256-prefix | inspection
react.svg | 4126 | 1 | 35ef61ed53b3 | DELEGATED-FRONTEND
```

### frontend/src/components

```text
basename | bytes | lines | sha256-prefix | inspection
AnnotationList.tsx | 3692 | 71 | 6abebf38c309 | DELEGATED-FRONTEND
BundleListPanel.test.tsx | 2321 | 82 | 8ac52c213356 | DELEGATED-FRONTEND
BundleListPanel.tsx | 8579 | 191 | edaed7f7d80c | DELEGATED-FRONTEND
CalibrationFramePicker.test.tsx | 1787 | 62 | eb4f2abaa7bb | DELEGATED-FRONTEND
CalibrationFramePicker.tsx | 2871 | 75 | 0d4b64bbba17 | DELEGATED-FRONTEND
CoachInsights.test.tsx | 5757 | 190 | 7a1b8124005b | DELEGATED-FRONTEND
CoachInsights.tsx | 14891 | 365 | f67c74fa9bb4 | DELEGATED-FRONTEND
DashboardPanel.tsx | 12782 | 193 | 5e8384ddc9cb | DELEGATED-FRONTEND
DemoMatchIssuePanel.test.tsx | 3972 | 116 | 8d27bf2dfa29 | DELEGATED-FRONTEND
DemoMatchIssuePanel.tsx | 7968 | 198 | 1c15febaf6c9 | DELEGATED-FRONTEND
DrawingToolbar.tsx | 2019 | 50 | d7685a57ec2d | DELEGATED-FRONTEND
MatchVideoPanel.test.tsx | 1285 | 46 | 3b27d28a9ce0 | DELEGATED-FRONTEND
MatchVideoPanel.tsx | 2907 | 97 | 11bf14b78e0a | DELEGATED-FRONTEND
PlayerDetailPanel.tsx | 5667 | 107 | 4c464d738772 | DELEGATED-FRONTEND
ReviewToolbar.test.tsx | 2785 | 73 | c4f613279a3a | DELEGATED-FRONTEND
ReviewToolbar.tsx | 2919 | 73 | 9bbd3f6e72ae | DELEGATED-FRONTEND
SaveBundleButton.tsx | 7166 | 194 | 86485330e8d6 | DELEGATED-FRONTEND
StatsPanel.test.tsx | 5149 | 160 | c4be1b3499ac | DELEGATED-FRONTEND
StatsPanel.tsx | 25481 | 409 | 97db82ba8c8d | DELEGATED-FRONTEND
TacticalPitch.tsx | 16509 | 411 | 2645a0b85292 | DELEGATED-FRONTEND
TeamSelectionBanner.test.tsx | 1378 | 40 | 36aff5abd684 | DELEGATED-FRONTEND
TeamSelectionBanner.tsx | 2397 | 60 | 10bef4ca41c1 | DELEGATED-FRONTEND
Timeline.tsx | 8072 | 191 | d32f24067a16 | DELEGATED-FRONTEND
TrustCropPanel.test.tsx | 1952 | 62 | be5123c69e7f | DELEGATED-FRONTEND
TrustCropPanel.tsx | 10987 | 232 | 7c4efd7e70ad | DELEGATED-FRONTEND
UploadCalibrationPanel.test.tsx | 3562 | 110 | ab88b9741c21 | DELEGATED-FRONTEND
UploadCalibrationPanel.tsx | 6761 | 149 | 09fa2b8b2ddc | DELEGATED-FRONTEND
```

### frontend/src/features/review

```text
basename | bytes | lines | sha256-prefix | inspection
useReviewSurface.test.tsx | 3475 | 117 | 0f83b9c2f825 | DELEGATED-FRONTEND
useReviewSurface.ts | 11317 | 376 | 5ce805c95db3 | DELEGATED-FRONTEND
```

### frontend/src/hooks

```text
basename | bytes | lines | sha256-prefix | inspection
useCoachAnalysis.ts | 4517 | 151 | 354b01448a38 | DELEGATED-FRONTEND
useDashboardData.ts | 1881 | 48 | b13d5d19ca2a | DELEGATED-FRONTEND
useReviewBundles.ts | 4257 | 138 | ee70682234c5 | DELEGATED-FRONTEND
```

### frontend/src/types

```text
basename | bytes | lines | sha256-prefix | inspection
index.ts | 12336 | 533 | 52089be51d46 | DELEGATED-FRONTEND
```

### frontend/src/utils

```text
basename | bytes | lines | sha256-prefix | inspection
analytics.test.ts | 10550 | 331 | 5bb17517607e | DELEGATED-FRONTEND
analytics.ts | 18492 | 467 | 2413bb086afb | DELEGATED-FRONTEND
api.test.ts | 8710 | 247 | 40f4a69bd8ab | DELEGATED-FRONTEND
api.ts | 11865 | 361 | e232629c959a | DELEGATED-FRONTEND
calibrationPoints.test.ts | 1269 | 51 | 7451a8aecc25 | DELEGATED-FRONTEND
calibrationPoints.ts | 922 | 34 | 44e3d48058de | DELEGATED-FRONTEND
uploadConfig.test.ts | 1554 | 52 | 29e72212bea4 | DELEGATED-FRONTEND
uploadConfig.ts | 1540 | 62 | a48149d3f8c1 | DELEGATED-FRONTEND
uploadErrors.test.ts | 610 | 17 | 92234fdf4551 | DELEGATED-FRONTEND
uploadErrors.ts | 432 | 14 | df5e7007ff1e | DELEGATED-FRONTEND
videoSync.test.ts | 608 | 17 | a235c2a17825 | DELEGATED-FRONTEND
videoSync.ts | 792 | 27 | d950057900a8 | DELEGATED-FRONTEND
```

### memorybank

```text
basename | bytes | lines | sha256-prefix | inspection
README.md | 1178 | 36 | 76db9dff7fd2 | DOC
activeContext.md | 92 | 3 | 248f7c13f67b | DOC
currentRoadmap.md | 93 | 3 | 33e22f00d5e2 | DOC
productContext.md | 2207 | 60 | 9756d7641888 | DOC
progress.md | 226819 | 2167 | f24e33ec36a3 | DOC
projectbrief.md | 2300 | 56 | a83ddaeba478 | DOC
systemPatterns.md | 3309 | 100 | 953269716b0d | DOC
techContext.md | 2324 | 92 | 9cba08e99a2c | DOC
```

### memorybank/architecture

```text
basename | bytes | lines | sha256-prefix | inspection
repo-map.md | 1368 | 59 | e3afa6345af4 | DOC
```

### memorybank/features

```text
basename | bytes | lines | sha256-prefix | inspection
source-robustness-lane.md | 46251 | 428 | bee1754ede4f | DOC
```

### memorybank/operations

```text
basename | bytes | lines | sha256-prefix | inspection
runpod-proof-workflow.md | 1752 | 60 | b80fa3d93b08 | DOC
touchline-detector-evaluation-workflow.md | 9366 | 205 | deaef46a618f | DOC
touchline-detector-training-workflow.md | 4289 | 111 | c39b79b0c2ed | DOC
touchline-review-densification-workflow.md | 1543 | 52 | b1711eee3da6 | DOC
touchline-training-prep-workflow.md | 3670 | 132 | fd54ff5043ae | DOC
verification-workflow.md | 1300 | 51 | 64474f3ee804 | DOC
```

### research-addon

```text
basename | bytes | lines | sha256-prefix | inspection
__init__.py | 0 | 0 | e3b0c44298fc | PY
pyproject.toml | 452 | 20 | 32e883f5f71e | TEXT
```

### research-addon/research_addon

```text
basename | bytes | lines | sha256-prefix | inspection
__init__.py | 0 | 0 | e3b0c44298fc | PY
cli.py | 7504 | 219 | 9e30c265ae5b | PY
corpus.py | 4688 | 125 | 89cd2c6cf23f | PY
judge.py | 6906 | 228 | 7149d6ad3719 | PY
path_guards.py | 3129 | 100 | 95e019353501 | PY
```

### research-addon/tests

```text
basename | bytes | lines | sha256-prefix | inspection
__init__.py | 0 | 0 | e3b0c44298fc | PY
test_cli.py | 3981 | 119 | b05a7bd80c10 | PY
test_corpus_manifest.py | 6566 | 147 | 642de0ac875a | PY
test_judge_contract.py | 8867 | 205 | d3042644a19a | PY
test_paths.py | 4285 | 98 | 93f6924c42ee | PY
```

### scripts

```text
basename | bytes | lines | sha256-prefix | inspection
verify.sh | 4316 | 120 | 9ae7f297e461 | TEXT
```
