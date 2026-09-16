# Task 8 report — R08 sidecar execution-boundary path isolation

## Implemented

- Replaced hard-coded string prefixes with one physical `pathlib` containment resolver.
- Derived checkout and installed-package addon roots from the package location without embedding a workspace or username.
- Allowed only the addon root, the dedicated validated temporary root, and existing effective-user-owned temporary directories.
- Rejected protected product trees, `.factory`, sibling-prefix lookalikes, traversal, symlink escapes, `/tmp` itself, and arbitrary nonexistent temporary roots.
- Reused the resolver in the CLI, `run_judge`, the final subprocess boundary, and corpus manifest writes.
- Moved the default manifest beneath the derived addon root.
- Deleted definition-only `is_safe_path`, hard-coded prefix constants, and unused `extra_args` forwarding.
- Replaced tautological/misdirected judge assertions with real subprocess success, nonzero, malformed JSON, missing-field, and entry-point boundary tests.

## TDD evidence

### RED

Initial command:

`python3 -m pytest -q research-addon/tests`

Observed: `21 failed, 17 passed in 0.50s`. Failures showed unresolved judge roots, protected CLI roots accepted, `extra_args` reaching the delegate, missing dynamic addon/temp ownership APIs, generic temporary symlinks accepted, and unguarded/default manifest writes.

Self-review edge RED commands:

- `python3 -m pytest -q research-addon/tests/test_paths.py -k installed_package` → `1 failed, 14 deselected`; an installed package claimed shared `site-packages` as addon-owned.
- `python3 -m pytest -q research-addon/tests/test_paths.py -k protected_subtree_symlink` → `1 failed, 15 deselected`; a symlinked protected subtree could re-enter an otherwise allowed temporary directory.
- `python3 -m pytest -q research-addon/tests/test_judge_contract.py -k subprocess_boundary_rechecks` → `1 failed, 13 deselected`; the last subprocess boundary did not independently recheck its storage root.

### GREEN

`python3 -m pytest -q research-addon/tests`

Observed: `47 passed in 0.57s` with pristine output.

Additional checks:

- `git diff --check` → passed with no output.
- `python3 -m compileall -q research-addon/research_addon` → passed with no output.

## Caller trace

Repository-wide `rg` before implementation found `is_safe_path` only at its definition and `extra_args` only in forwarding between `run_judge` and `_run_proof_via_script`. After implementation, neither symbol remains in production; `extra_args` appears only in the regression that proves calls using it fail before delegation.

## Files changed

- `research-addon/research_addon/path_guards.py`
- `research-addon/research_addon/judge.py`
- `research-addon/research_addon/cli.py`
- `research-addon/research_addon/corpus.py`
- `research-addon/tests/test_paths.py`
- `research-addon/tests/test_judge_contract.py`
- `research-addon/tests/test_cli.py`
- `research-addon/tests/test_corpus_manifest.py`

## Self-review

- Confirmed every allowed entry point returns or delegates the physically resolved root.
- Confirmed rejected roots fail before manifest mutation or subprocess execution.
- Confirmed the default root remains absent-until-used and no test or implementation mutates real project data.
- Confirmed only the task's eight source/test files plus this report changed; `.verification/` was untouched.

## Remaining concern

R09 still owns explicit repository/interpreter/corpus configuration and metric type validation. This task intentionally leaves the existing three-parent repository inference and proof-video resolution unchanged.

## Fix round 1

### Review findings addressed

- Raw `..` components are now rejected before normalization, including when the resolved destination independently qualifies as an owned temporary directory. The same shared check protects manifest writes, direct judge calls, both CLIs, and the subprocess boundary.
- Checkout-root discovery requires the exact `[project]` name `research-addon` plus the expected physical `research_addon` package layout. An unrelated parent `pyproject.toml` leaves the addon root at the installed package directory.
- Corpus manifests now publish through a unique same-directory temporary file, file flush/fsync, `os.replace`, and parent-directory fsync. Any pre-replace failure removes the temporary and preserves the previous manifest.
- A parent-directory fsync failure occurs after replacement: `write` raises the OS error while the complete new manifest remains visible, with durability unconfirmed. It does not attempt the unrelated R05 backup/rollback protocol.

### Fix-round TDD evidence

RED:

- `python3 -m pytest -q research-addon/tests/test_paths.py research-addon/tests/test_corpus_manifest.py` → `7 failed, 27 passed in 0.11s` for allowed-destination traversal, unrelated-project identity, missing durable-write operations, preservation, cleanup, ordering, and post-replace outcome.

GREEN:

- `python3 -m pytest -q research-addon/tests` → `54 passed in 0.67s`.
- `git diff --check` → passed with no output.
- `python3 -m compileall -q research-addon/research_addon` → passed with no output.

### Fix-round files changed

- `research-addon/research_addon/path_guards.py`
- `research-addon/research_addon/corpus.py`
- `research-addon/tests/test_paths.py`
- `research-addon/tests/test_corpus_manifest.py`

## Fix round 2

### Review finding addressed

- Removed the optional `tomllib` branch so root derivation behaves identically on every advertised Python 3.10+ runtime.
- Added a Python 3.10 simulation (`tomllib = None`) with the whole checkout moved beneath the system temporary directory. Its real sibling `backend` remains rejected instead of qualifying as a generic owned temporary directory.

### Fix-round TDD evidence

RED:

- `python3 -m pytest -q research-addon/tests/test_paths.py -k python_310_moved_checkout` → `1 failed, 18 deselected in 0.03s`; sibling `backend` was accepted when `tomllib` was unavailable.

GREEN:

- `python3 -m pytest -q research-addon/tests/test_paths.py -k python_310_moved_checkout` → `1 passed, 18 deselected in 0.02s`.
- `python3 -m pytest -q research-addon/tests` → `55 passed in 0.62s`.
- `git diff --check` and `python3 -m compileall -q research-addon/research_addon` → passed with no output.

## Fix round 3

### Review finding addressed

- Deleted the hand-rolled TOML reader. Checkout recognition now uses only the fixed physical layout: a parent directory named `research-addon` containing the exact resolved `research_addon` package. Every other host project stays package-rooted regardless of valid, malformed, or multiline-misleading `pyproject.toml` content.
- Replaced the obsolete deleted-state monkeypatch with production-boundary cases. Each unrelated host project remains package-rooted and its sibling `backend` is rejected; the existing moved-checkout matrix still rejects all five protected product siblings beneath system temp.

### Fix-round TDD evidence

RED:

- `python3 -m pytest -q research-addon/tests/test_paths.py -k unrelated_parent_project_content` → `2 failed, 1 passed, 17 deselected in 0.03s`; malformed-after-name and multiline content fooled the parser.

GREEN:

- `python3 -m pytest -q research-addon/tests/test_paths.py -k 'unrelated_parent_project_content or moved_checkout_under_temp'` → `8 passed, 12 deselected in 0.02s`.
- `python3 -m pytest -q research-addon/tests` → `56 passed in 0.63s`.
- `git diff --check` and `python3 -m compileall -q research-addon/research_addon` → passed with no output.
