# Python quality gates

CI uses CPython 3.11 on Linux x86-64. Install the isolated quality profiles:

```sh
python -m pip install --require-hashes -r backend/requirements/quality-linux.lock -r backend/requirements/typing-linux.lock
ruff check backend --select F,S110,B904
python scripts/check_python_quality.py ruff
python scripts/check_python_quality.py mypy
```

The backend-wide correctness/cleanup command permits **zero** diagnostics. The scoped mypy baseline is now empty; its existing scope and configuration are unchanged. The broader Ruff check covers `F,B,BLE,S110,B904,C901` across `backend/` and the gate itself. Mypy checks `workbench/`, `schemas.py`, `settings.py`, and `run_benchmarks.py` with the Pydantic plugin. Imported modules are analysed silently; missing third-party stubs remain `Any`. This is a bounded initial type gate, not full strict typing or a substitute for runtime tests.

`init_forbid_extra = true` makes undeclared Pydantic constructor keywords visible to mypy. `init_typed = false` deliberately retains Pydantic's supported coercion behavior. Only the two verified benchmark summary contracts change to runtime `extra="forbid"`.

Baselines identify diagnostics by repository-relative file, enclosing function/class, code, source line text, and message, with duplicate counts. Unrelated line-number shifts do not hide or fabricate debt. Added diagnostics fail. Removed diagnostics also fail until the obsolete entries are deleted. Tool crashes, unexpected standard error, malformed diagnostics, incompatible tool/configuration metadata, and missing source files fail closed.

After fixing debt or intentionally upgrading tools, a maintainer may run:

```sh
python scripts/check_python_quality.py ruff --write-baseline
python scripts/check_python_quality.py mypy --write-baseline
```

**Review every baseline diff.** CI never runs these write commands. Refreshing a baseline is not evidence that newly accepted debt was repaired. These diagnostic identities are a practical ratchet, not proof of semantic equivalence or complete static coverage. Configured ignores and dynamic `Any` payloads still require code review and runtime regression tests.

Tool pins, platform-specific wheel hashes, configuration hashes and initial diagnostic details are retained beside the source. Runtime dependency locks are unchanged.
