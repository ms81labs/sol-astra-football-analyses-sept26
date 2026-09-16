# Task 2 — R02 legacy review HTTP boundaries

Status: complete, scoped implementation and regression tests verified.
Base: `7787a9fd`.
Worktree: `/root/WorkSpace/fotball-analyst/.worktrees/batch-1-data-safety`.

## Result

Removed the generic filesystem fallback from all three legacy review servers. The promoted-v6 image route now looks up the requested filename in its frame manifest. The two candidate review servers preserve their existing `/source-image?path=...` URLs but require exact membership in their own review-item image fields. No prefix containment test or normalized caller path grants access. Image routes require an image MIME extension.

Approved files and the fixed index are opened through directory descriptors with `O_NOFOLLOW` on every ancestor and the final component. The final descriptor must be a regular file; `O_NONBLOCK` prevents a listed FIFO from hanging the handler. Parent components are refused. Missing, symlinked, unlisted, directory, FIFO, and non-image targets return errors without returning the outside sentinel.

POST requests validate a single local Host and, when supplied, a matching local HTTP Origin before reading the body or dispatching either mutation route. Transfer-Encoding and duplicate Content-Length are refused. Missing Content-Length returns 411; malformed, negative, zero and otherwise invalid lengths return 400; lengths above exactly 65,536 bytes return 413 before any body read. A five-second socket read timeout applies to handlers, and a stalled body returns 408. JSON must be a UTF-8 object and must completely match the declared bounded length.

CLI host validation runs during argument parsing, before artifact reads or binding. It permits loopback IPs and pins localhost to 127.0.0.1; other names, wildcard binds, and non-loopback IPs are refused. Native IPv4/IPv6 server sockets remain in use, with correctly bracketed IPv6 startup URLs.

Review decisions, bbox validation, lineage, summary schemas, and the three existing resolution functions remain separate and unchanged. SoccerNet test image writes now live under pytest's tmp_path.

## Files changed

- `backend/scripts/serve_promoted_v6_manual_review_ui.py`
- `backend/scripts/serve_v7_1_positive_diversity_review_ui.py`
- `backend/scripts/serve_football_external_soccernet_detector_miss_review_ui.py`
- `backend/scripts/review_http.py` — small shared file/body/bind-validation functions and HTTP error type, extracted only after the three corrected inline implementations passed together.
- `backend/tests/test_serve_promoted_v6_manual_review_ui.py` — raw HTTP boundary matrix parameterized across the three actual handler modules, plus promoted URL compatibility.
- `backend/tests/test_serve_v7_1_positive_diversity_review_ui.py` — candidate URL escaping regression.
- `backend/tests/test_serve_football_external_soccernet_detector_miss_review_ui.py` — tmp_path image fixtures and URL escaping regression.
- This report.

The existing untracked `.verification/` directory was preserved. ResultBundle/live-progress code and unrelated files were not edited.

## Regression design

The tests name these production breaks before exercising the actual handler:

| Regression | Production break caught |
| --- | --- |
| Raw absolute, parent, encoded parent, sibling-prefix, private static, unlisted image requests | Generic static fallback or arbitrary caller-controlled path access |
| Listed symlink, internal symlink, parent-directory symlink, directory, FIFO, non-image | Following symlinks or serving something other than an owned regular image |
| Replace an approved image with a symlink during descriptor open | Check-then-open filesystem race |
| Fixed index and legitimate owned image | Security change accidentally hiding normal UI/evidence |
| Missing, -1, malformed, 65,537, zero, signed and comma-joined lengths | Invalid/unbounded reads or validation after read/mutation |
| Duplicate Host/length, foreign Host/Origin, null Origin, wrong Origin port, Transfer-Encoding | Browser-origin or ambiguous framing bypass |
| Normal payload and exactly 65,536 bytes | Off-by-one rejection or local save regression; returned and persisted fields are both asserted |
| Incomplete body | No socket read timeout, or mutation after a partial read |
| Non-loopback CLI refusal | Public unauthenticated listener or artifact loading before bind validation |
| IPv4, localhost and IPv6 real binds | Valid local startup or printed URL regression |
| Reserved image filename characters | Query/fragment/percent characters corrupting legitimate image URLs |

All HTTP requests use a raw socket and literal request target, avoiding client normalization of parent paths. Fixtures and mutations are confined to pytest-owned temporary files. Existing resolver tests continue to run against their existing disposable artifacts. The bind test substitutes only the indefinite serve loop after the real socket has bound.

## Genuine RED evidence

### Initial security regressions, before production edits

Command:

```sh
python3 -m pytest -q backend/tests/test_serve_promoted_v6_manual_review_ui.py backend/tests/test_serve_v7_1_positive_diversity_review_ui.py backend/tests/test_serve_football_external_soccernet_detector_miss_review_ui.py
```

Exit 1. Output excerpts:

```text
E       AssertionError: assert b'OUTSIDE_SENTINEL_DO_NOT_SERVE' not in b'OUTSIDE_SENTINEL_DO_NOT_SERVE'
E   Failed: handler failed to return a bounded HTTP response: TimeoutError
62 failed, 70 passed in 34.83s
```

The failures included promoted-v6 parent/static/unlisted disclosure, both candidate tools' arbitrary image paths, foreign browser writes, malformed or blocking length reads, incomplete-body timeouts, and unescaped candidate image URLs. Expected BrokenPipeError traces followed client timeout/closure against the original unbounded handlers. The tool truncated the large traceback output; the excerpts and terminal count above are preserved from that actual run.

### Corrected bind assertion and additional Host/missing-body RED

Self-review of the test first found that merely checking for the word “loopback” in CLI stderr also matched the pytest temporary directory name. The assertion was tightened to require an argparse error, and the single foreign Host and exact missing-length status were tested explicitly.

Command:

```sh
python3 -m pytest -q backend/tests/test_serve_promoted_v6_manual_review_ui.py -k 'cli_refuses or single_foreign_host or invalid_length' --tb=line
```

Exit 1 against the original handlers. Output excerpts:

```text
E   assert 400 == 411
E   assert 500 in {400, 411, 413}
E   Failed: handler failed to return a bounded HTTP response: TimeoutError
E   assert 'error:' in 'Traceback (most recent call last):...'
33 failed, 3 passed, 83 deselected in 13.93s
```

All twelve non-loopback CLI cases and all three single-foreign-Host cases failed as intended. The zero-length compatibility cases already returned a 400 response in the original implementation.

### Promoted image URL RED

Command:

```sh
python3 -m pytest -q backend/tests/test_serve_promoted_v6_manual_review_ui.py -k 'promoted_image_urls'
```

Exit 1, before changing promoted URL generation:

```text
E       AssertionError: assert '/review_fram...rame &#+%.jpg' == '/review_fram...%23%2B%25.jpg'
E         - /review_frames/frame%20%26%23%2B%25.jpg
E         + /review_frames/frame &#+%.jpg
1 failed, 125 deselected in 0.39s
```

### IPv6 startup URL RED

Command:

```sh
python3 -m pytest -q backend/tests/test_serve_promoted_v6_manual_review_ui.py -k 'cli_binds_loopback'
```

Exit 1, before changing the printed URLs:

```text
E       assert 'http://[::1]:' in 'Serving promoted-v6 manual review UI at http://::1:0/...'
3 failed, 6 passed, 126 deselected in 0.56s
```

The three real IPv6 binds succeeded but their startup URLs lacked brackets; IPv4 and localhost binds passed.

## GREEN evidence

The first inline implementation passed the full focused command:

```text
135 passed in 21.99s
```

Only then were identical file-open/body/bind checks extracted into `review_http.py`. The stronger internal-symlink/open-race checks and promoted URL regression then passed:

```text
142 passed in 21.98s
```

Final focused command after all changes:

```sh
python3 -m pytest -q backend/tests/test_serve_promoted_v6_manual_review_ui.py backend/tests/test_serve_v7_1_positive_diversity_review_ui.py backend/tests/test_serve_football_external_soccernet_detector_miss_review_ui.py
```

Exit 0:

```text
........................................................................ [ 47%]
........................................................................ [ 95%]
.......                                                                  [100%]
151 passed in 22.26s
```

## Existing operational / documented-startup suite

Exactly two installation tests were excluded, as agreed with the parent agent under the no-dependency-install constraint:

- `test_root_package_builds_and_imports_documented_asgi_target_outside_checkout`
- `test_sidecar_package_installs_imports_and_exposes_cli_without_pythonpath`

The other four documented-startup tests and all operational-doc tests were selected.

First command used host Python:

```sh
python3 -m pytest -q backend/tests/test_operational_docs.py backend/tests/test_documented_startup.py -k 'not test_root_package_builds_and_imports_documented_asgi_target_outside_checkout and not test_sidecar_package_installs_imports_and_exposes_cli_without_pythonpath'
```

Exit 1, environment failure:

```text
FAILED backend/tests/test_operational_docs.py::test_daytona_runbook_has_credential_free_pinned_readiness_command
E       ModuleNotFoundError: No module named 'daytona'
1 failed, 59 passed, 2 deselected in 28.91s
```

The parent supplied the already-existing pinned interpreter; no package was installed. Same selection rerun:

```sh
env PATH=/root/.cache/fotball-analyst/daytona-smoke-0.207.0/bin:$PATH python3 -m pytest -q backend/tests/test_operational_docs.py backend/tests/test_documented_startup.py -k 'not test_root_package_builds_and_imports_documented_asgi_target_outside_checkout and not test_sidecar_package_installs_imports_and_exposes_cli_without_pythonpath'
```

Exit 0:

```text
60 passed, 2 deselected in 28.44s
```

This checks the installed package version locally; no smoke or provider operation was run.

`git diff --check` also exited 0 with no output.

## Self-review and concerns

- Confirmed every image-serving caller uses the no-follow regular-file reader and every POST route reaches the shared Host/Origin/body validation before mutation dispatch.
- Confirmed one URL decode followed by exact membership in candidate tools; removed their extra unquote and encoded generated URLs. Promoted routes use exact manifest filename lookup.
- Confirmed outside sentinel bytes are never returned by the negative request matrix; legitimate UI and image bytes remain available.
- Confirmed invalid or foreign requests leave the overlay bytes unchanged; normal and maximum-sized bodies persist the original schema's fields.
- Confirmed timeout, body maximum, no-follow handling and loopback startup are exercised through the real HTTP/filesystem/socket boundaries.
- Shared helpers contain no review schema, resolver, server configuration framework, authentication system or new dependency.
- These remain unauthenticated local operator tools. Host/Origin checks protect the local browser boundary, not against another local OS user. Review-write concurrency is intentionally deferred to the later task.
- The no-follow implementation uses the existing Linux/POSIX descriptor facilities; it does not silently fall back to unsafe opens on platforms lacking them.
- Image type is checked by MIME extension; these tools do not decode or validate image contents.
- The full packaging/install tests remain unrun by explicit scope constraint. The initial host-Python dependency failure is resolved for this verification by the existing pinned environment.
- No Daytona/cloud/provider calls, smoke, deployment, dependency installation, real-data deletion, or unrelated edits occurred.

## Review follow-up — equivalent HTTP default-port authorities

Finding verified: on a server listening on port 80, the original literal Host and Origin checks rejected the browser's canonical omitted-port form. It also rejected explicit `Host: 127.0.0.1:80` with canonical `Origin: http://127.0.0.1`.

The correction is confined to `review_http.read_json_payload`: only for server port 80, permit both explicit and omitted `:80` Host spellings and the two equivalent Origin spellings for that same Host. Foreign hosts, different hostnames, other ports and HTTPS remain rejected. The shared helper is called before both save and resolution dispatch in each of the three servers.

A focused table exercises the real shared helper with standard-library header and byte-stream objects; it does not reserve privileged port 80. It covers four IPv4 default-port combinations, localhost and IPv6, the ordinary 8765 case, and foreign-host/different-host/different-port/different-scheme refusals. Rejected requests must leave the body unread.

### RED before the correction

Command:

```sh
python3 -m pytest -q backend/tests/test_serve_promoted_v6_manual_review_ui.py -k default_port_authority_equivalence --tb=line
```

Exit 1; exact output:

```text
FFF.FF.......                                                            [100%]
=================================== FAILURES ===================================
E   backend.scripts.review_http.HttpRequestError: foreign_host
/root/WorkSpace/fotball-analyst/.worktrees/batch-1-data-safety/backend/scripts/review_http.py:61: backend.scripts.review_http.HttpRequestError: foreign_host
E   backend.scripts.review_http.HttpRequestError: foreign_origin
/root/WorkSpace/fotball-analyst/.worktrees/batch-1-data-safety/backend/scripts/review_http.py:64: backend.scripts.review_http.HttpRequestError: foreign_origin
E   backend.scripts.review_http.HttpRequestError: foreign_host
/root/WorkSpace/fotball-analyst/.worktrees/batch-1-data-safety/backend/scripts/review_http.py:61: backend.scripts.review_http.HttpRequestError: foreign_host
E   backend.scripts.review_http.HttpRequestError: foreign_host
/root/WorkSpace/fotball-analyst/.worktrees/batch-1-data-safety/backend/scripts/review_http.py:61: backend.scripts.review_http.HttpRequestError: foreign_host
E   backend.scripts.review_http.HttpRequestError: foreign_origin
/root/WorkSpace/fotball-analyst/.worktrees/batch-1-data-safety/backend/scripts/review_http.py:64: backend.scripts.review_http.HttpRequestError: foreign_origin
=========================== short test summary info ============================
FAILED backend/tests/test_serve_promoted_v6_manual_review_ui.py::test_local_json_default_port_authority_equivalence[80-127.0.0.1-http://127.0.0.1-True]
FAILED backend/tests/test_serve_promoted_v6_manual_review_ui.py::test_local_json_default_port_authority_equivalence[80-127.0.0.1:80-http://127.0.0.1-True]
FAILED backend/tests/test_serve_promoted_v6_manual_review_ui.py::test_local_json_default_port_authority_equivalence[80-127.0.0.1-http://127.0.0.1:80-True]
FAILED backend/tests/test_serve_promoted_v6_manual_review_ui.py::test_local_json_default_port_authority_equivalence[80-localhost-http://localhost:80-True]
FAILED backend/tests/test_serve_promoted_v6_manual_review_ui.py::test_local_json_default_port_authority_equivalence[80-[::1]:80-http://[::1]-True]
5 failed, 8 passed, 135 deselected in 0.37s
```

### GREEN after the shared correction

Commands (run together):

```sh
python3 -m pytest -q backend/tests/test_serve_promoted_v6_manual_review_ui.py -k default_port_authority_equivalence --tb=line && python3 -m pytest -q backend/tests/test_serve_promoted_v6_manual_review_ui.py backend/tests/test_serve_v7_1_positive_diversity_review_ui.py backend/tests/test_serve_football_external_soccernet_detector_miss_review_ui.py
```

Exit 0; exact output:

```text
.............                                                            [100%]
13 passed, 135 deselected in 0.28s
........................................................................ [ 43%]
........................................................................ [ 87%]
....................                                                     [100%]
164 passed in 22.23s
```

`git diff --check` exited 0 with no output.

Follow-up files: `backend/scripts/review_http.py`, `backend/tests/test_serve_promoted_v6_manual_review_ui.py`, and this report. No changes to individual schemas/resolvers, the body/file boundaries or startup binding rules. No new concerns; the earlier installation-test exclusions and deferred concurrency scope remain unchanged. No provider/cloud/smoke operation or data deletion was performed.
