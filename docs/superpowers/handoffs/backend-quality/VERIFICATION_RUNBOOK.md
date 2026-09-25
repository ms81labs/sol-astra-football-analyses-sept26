# Verification runbook

Run from a complete source checkout. Read current workflow/locks if main advanced. These are instructions for the implementation session, not tests run during documentation publication.

## Environment

Recorded CI: Linux x86-64 / CPython 3.11; dev lock FastAPI 0.121.0, Pydantic 2.13.5, AnyIO 4.15.1; isolated quality locks Ruff 0.16.8 and mypy 2.3.1. Source lock files outrank these recorded versions. Do not substitute a Python 3.13 sandbox and label it pinned acceptance.

With Python 3.11 and ffmpeg/ffprobe available:

```sh
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r backend/requirements/dev.lock
python -m pip install -e . --no-deps
python -m pip install -e ./research-addon
command -v ffmpeg
command -v ffprobe
python --version
python3.11 -m venv .quality-tools
.quality-tools/bin/python -m pip install --require-hashes \
  -r backend/requirements/quality-linux.lock \
  -r backend/requirements/typing-linux.lock
export VERIFY_DAYTONA=0 ALLOW_DAYTONA_MUTATION=0 PYTHON_DOTENV_DISABLED=1
```

The research-addon install mirrors CI but is not a separately hash-locked profile. The environment flags do not authorize live provider operations. Use fake/temp-store tests. If setup is unavailable, report the actual limitation; do not modify workflows to bypass it.

## Before and after the structural patch

Keep separate logs, exit statuses and JUnit for original and candidate:

```sh
python -m pytest -q backend/tests/test_report_store_contract.py backend/tests/test_quality_gate.py
pytest -q backend/tests/test_report_store_contract.py
python -m pytest -q \
  backend/tests/test_report_store_contract.py \
  backend/tests/test_audit_v3_c03_reports.py \
  backend/tests/test_audit_v3_c03_report_envelopes.py \
  backend/tests/test_audit_v3_c03_integrity.py \
  backend/tests/test_audit_v3_c03_publication.py \
  backend/tests/test_audit_v3_c03_final_consistency.py \
  backend/tests/test_audit_v3_c03_journey.py \
  backend/tests/test_api.py \
  backend/tests/test_audit_v3_final_journey.py
(
  export PATH="$PWD/.quality-tools/bin:$PATH"
  ruff check backend --select F,S110,B904,B008
  python scripts/check_python_quality.py ruff
  python scripts/check_python_quality.py mypy
  python -m mypy --config-file pyproject.toml backend/app/report_store.py
)
```

The committed contract suite has 59 cases at the recorded base. Do not infer the combined count. Baselines reject new and stale findings, tool errors and metadata mismatch; do not regenerate them to accept new debt. Imported-module/stub coverage remains a qualification of scoped mypy.

## Full project verification

```sh
set -euo pipefail
mkdir -p .verification/logs
GA_VERIFICATION_RUN=1 GA_VERIFICATION_PROFILE=complete-cpu \
  python -m pytest -q -ra backend/tests \
  --junitxml=.verification/backend-all.xml \
  2>&1 | tee .verification/logs/backend-all.log
# With Node 22, as in existing CI:
npm ci --prefix frontend
VERIFY_CODE_ONLY=1 VERIFY_DAYTONA=0 ALLOW_DAYTONA_MUTATION=0 scripts/verify.sh
```

Canonical has intentional exclusions; it does not replace complete-backend or excluded-backend. Preserve existing workflow selections. Applicable acceptance jobs are verify, complete-backend, python-quality, integration, real-media, excluded-backend, api-profile, macos-profile, plus dedicated C05/C06. GPU remains unrequested/skipped. A running, missing or old-parent check is not acceptance of a new application SHA.

Check workflow head SHA/tree, environment and lock identity, exits, JUnit and per-invocation receipts. Check all nine canonical log hashes and its nested backend receipt hash. Keep overlapping counts separate and report skips, stubs and dirty-source flags. Historical run/artifact IDs are in ACCEPTANCE.json; they are not evidence for future code changes. Actions artifacts may expire; do not depend on an old signed download URL.

## Known traps

Earlier Python 3.13 local runs had AnyIO without `gather`, and a child test's 128 MiB address-space limit was below already-mapped sandbox memory. Both failed on unchanged source; do not relax limits or exclude the tests. Missing ffmpeg/ffprobe caused another setup failure. Verify console pytest and `python -m pytest`; do not edit sys.path or package developer tooling to mask import setup issues.

CPU runs use the ultralytics stub. Synthetic media is not model-quality acceptance. The macOS lane is a dependency dry run. Dirty flags, including differing C05 source-diff hashes, are not pristine-checkout certificates. Author self-review is not independent review.
