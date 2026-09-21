from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY_SCRIPT = REPO_ROOT / "scripts" / "verify.sh"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
DEV_REQUIREMENTS = REPO_ROOT / "backend" / "requirements-dev.txt"
DEV_LOCK = REPO_ROOT / "backend" / "requirements" / "dev.lock"
COMPATIBILITY_REQUIREMENTS = REPO_ROOT / "backend" / "requirements.txt"
REQUIRED_GATE_COMMANDS = {
    "backend": "python3 -m pytest -q backend/tests",
    "sidecar": "python3 -m pytest -q research-addon/tests",
    "frontend-tests": "npm --prefix frontend test -- --run",
    "lint": "npm --prefix frontend run lint",
    "typecheck-app": (
        "cd frontend && npx tsc -p tsconfig.app.json --noEmit --incremental false"
    ),
    "typecheck-node": (
        "cd frontend && npx tsc -p tsconfig.node.json --noEmit --incremental false"
    ),
    "build": "npm --prefix frontend run build",
    "backend-startup": "python3 -c 'from backend.app.main import app'",
    "manifest": (
        "python3 -m pytest -q backend/tests/test_release_manifest.py "
        "backend/tests/test_write_release_manifest.py"
    ),
    "runtime-options": "python3 -m pytest -q backend/tests/test_runtime_options.py",
    "preflight-negatives": (
        "python3 -m pytest -q backend/tests/test_release_preflight.py -k reject"
    ),
    "prod-audit": "npm --prefix frontend audit --omit=dev --audit-level=high",
    "daytona-gpu-smoke": (
        "python3 -m backend.scripts.run_daytona_gpu_smoke --real-smoke"
    ),
}


def _requirement_names(requirements_path: Path) -> set[str]:
    allowed_root = requirements_path.parent.resolve(strict=True)

    def collect(path: Path, stack: tuple[Path, ...]) -> set[str]:
        resolved = path.resolve(strict=True)
        try:
            resolved.relative_to(allowed_root)
        except ValueError as exc:
            raise ValueError(
                f"requirement include escapes allowed root {allowed_root}: {resolved}"
            ) from exc
        if resolved in stack:
            cycle_start = stack.index(resolved)
            cycle = (*stack[cycle_start:], resolved)
            raise ValueError(
                "requirement include cycle: " + " -> ".join(str(item) for item in cycle)
            )

        names: set[str] = set()
        next_stack = (*stack, resolved)
        for raw_line in resolved.read_text(encoding="utf-8").splitlines():
            raw_line = raw_line.strip()
            if raw_line.endswith("\\"):
                raw_line = raw_line[:-1]
            tokens = shlex.split(raw_line, comments=True)
            if not tokens:
                continue
            if tokens[0].startswith("--hash="):
                continue
            include: str | None = None
            if tokens[0] in {"-r", "--requirement"}:
                if len(tokens) != 2:
                    raise ValueError(f"invalid requirement include in {resolved}: {raw_line}")
                include = tokens[1]
            elif tokens[0].startswith("--requirement="):
                if len(tokens) != 1:
                    raise ValueError(f"invalid requirement include in {resolved}: {raw_line}")
                include = tokens[0].partition("=")[2]
            elif tokens[0].startswith("--requirement"):
                raise ValueError(f"invalid requirement include in {resolved}: {raw_line}")
            elif tokens[0].startswith("-r"):
                if len(tokens) != 1:
                    raise ValueError(f"invalid requirement include in {resolved}: {raw_line}")
                include = tokens[0][2:]
            if include is not None:
                if not include.strip():
                    raise ValueError(f"invalid requirement include in {resolved}: {raw_line}")
                names.update(collect(resolved.parent / include, next_stack))
                continue

            match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)", tokens[0])
            if match is not None:
                names.add(re.sub(r"[-_.]+", "-", match.group(1)).lower())
        return names

    return collect(requirements_path, ())


@pytest.fixture
def verifier_repo(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    (root / "frontend").mkdir()
    (root / "bin").mkdir()
    shutil.copy2(VERIFY_SCRIPT, root / "scripts" / "verify.sh")
    for relative in (
        "backend/__init__.py",
        "backend/app/__init__.py",
        "backend/app/release_manifest.py",
        "backend/app/remote_contracts.py",
        "backend/app/runtime_options.py",
        "backend/release/__init__.py",
        "backend/release/daytona_policy.py",
        "backend/release/daytona-v7.3.json",
        "backend/release/evidence.py",
        "backend/release/v7.3.json",
        "backend/scripts/write_verification_evidence.py",
        "backend/tests/code_only_exclusions.txt",
    ):
        source = REPO_ROOT / relative
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "verify@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Verify Tests"], cwd=root, check=True)
    subprocess.run(["git", "add", "scripts", "backend"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "metadata"], cwd=root, check=True, capture_output=True)
    (root / ".git/info/exclude").write_text(
        "bin/\ncalls.log\n__pycache__/\n*.pyc\n", encoding="utf-8"
    )

    stub = """#!/usr/bin/env bash
set -eu
printf '%s|%s\\n' "$(basename "$0")" "$*" >> "$VERIFY_STUB_CALLS"
case "$(basename "$0")|$*" in
  "python3|-m pytest -q backend/tests")
    printf 'QT_QPA_PLATFORM=%s\\n1486 passed in 1.00s\\n' "${QT_QPA_PLATFORM:-}"
    if [ -n "${VERIFY_BACKEND_END_MARKER:-}" ]; then touch "$VERIFY_BACKEND_END_MARKER"; sleep 0.05; fi
    ;;
  "python3|-m pytest -q research-addon/tests") printf '37 passed in 1.00s\\n' ;;
  "python3|-m backend.scripts.write_verification_evidence --record-verifier-success") exec "$REAL_PYTHON" "$@" ;;
  "npm|--prefix frontend test -- --run") printf ' Tests  46 passed (46)\\n' ;;
  *) printf 'stub success\\n' ;;
esac
"""
    for command in ("python3", "npm", "npx"):
        path = root / "bin" / command
        path.write_text(stub, encoding="utf-8")
        path.chmod(0o755)

    return root, root / "calls.log"


def _run_verifier(
    verifier_repo: tuple[Path, Path],
    *,
    verify_daytona: str | None = None,
    allow_daytona_mutation: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    root, calls = verifier_repo
    env = os.environ.copy()
    env.pop("QT_QPA_PLATFORM", None)
    env.pop("VERIFY_DAYTONA", None)
    env.pop("ALLOW_DAYTONA_MUTATION", None)
    env.pop("VERIFY_CODE_ONLY", None)
    env.update(
        {
            "PATH": f"{root / 'bin'}:{env['PATH']}",
            "VERIFY_STUB_CALLS": str(calls),
            "REAL_PYTHON": sys.executable,
        }
    )
    if verify_daytona is not None:
        env["VERIFY_DAYTONA"] = verify_daytona
    if allow_daytona_mutation is not None:
        env["ALLOW_DAYTONA_MUTATION"] = allow_daytona_mutation
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", "scripts/verify.sh"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _calls(verifier_repo: tuple[Path, Path]) -> list[str]:
    calls = verifier_repo[1]
    return calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []


def test_verifier_runs_required_gates_in_canonical_order(verifier_repo: tuple[Path, Path]) -> None:
    result = _run_verifier(verifier_repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _calls(verifier_repo) == [
        "python3|-m pytest -q backend/tests",
        "python3|-m pytest -q research-addon/tests",
        "npm|--prefix frontend test -- --run",
        "npm|--prefix frontend run lint",
        "npx|tsc -p tsconfig.app.json --noEmit --incremental false",
        "npx|tsc -p tsconfig.node.json --noEmit --incremental false",
        "npm|--prefix frontend run build",
        "python3|-c from backend.app.main import app",
        "python3|-m pytest -q backend/tests/test_release_manifest.py backend/tests/test_write_release_manifest.py",
        "python3|-m pytest -q backend/tests/test_runtime_options.py",
        "python3|-m pytest -q backend/tests/test_release_preflight.py -k reject",
        "npm|--prefix frontend audit --omit=dev --audit-level=high",
        "python3|-m backend.scripts.write_verification_evidence --record-verifier-success",
    ]
    assert "Daytona provider operation skipped" in result.stdout


def test_successful_verifier_records_canonical_receipt_with_twelve_real_log_hashes(
    verifier_repo: tuple[Path, Path],
) -> None:
    import hashlib

    result = _run_verifier(verifier_repo)
    receipt_path = verifier_repo[0] / ".verification/receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert result.returncode == 0, result.stdout + result.stderr
    assert receipt_path.read_text() == json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n"
    assert receipt["repositoryCommit"] == subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=verifier_repo[0], check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    assert [(gate["name"], gate["command"]) for gate in receipt["gates"]] == list(
        REQUIRED_GATE_COMMANDS.items()
    )[:-1]
    for gate in receipt["gates"]:
        log = verifier_repo[0] / ".verification/logs" / f"{gate['name']}.log"
        assert gate["logSha256"] == hashlib.sha256(log.read_bytes()).hexdigest()


def test_gate_timestamp_is_touched_after_the_command_finishes(
    verifier_repo: tuple[Path, Path], tmp_path: Path
) -> None:
    marker = tmp_path / "backend-command-nearly-finished"
    result = _run_verifier(
        verifier_repo, extra_env={"VERIFY_BACKEND_END_MARKER": str(marker)}
    )

    assert result.returncode == 0, result.stdout + result.stderr
    backend_log = verifier_repo[0] / ".verification/logs/backend.log"
    assert backend_log.stat().st_mtime_ns > marker.stat().st_mtime_ns


def test_verifier_commands_match_preflight_evidence_contract() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json; "
                "from backend.release.evidence import REQUIRED_GATE_COMMANDS; "
                "print(json.dumps(dict(REQUIRED_GATE_COMMANDS)))"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert json.loads(result.stdout) == REQUIRED_GATE_COMMANDS


@pytest.mark.parametrize(
    ("extra_env", "expected"),
    [({}, "offscreen"), ({"QT_QPA_PLATFORM": "caller-choice"}, "caller-choice")],
)
def test_verifier_sets_safe_opencv_default_without_overriding_caller(
    verifier_repo: tuple[Path, Path], extra_env: dict[str, str], expected: str
) -> None:
    result = _run_verifier(verifier_repo, extra_env=extra_env)

    assert result.returncode == 0, result.stdout + result.stderr
    backend_log = verifier_repo[0] / ".verification" / "logs" / "backend.log"
    assert f"QT_QPA_PLATFORM={expected}" in backend_log.read_text(encoding="utf-8")


def test_dev_requirements_declare_clean_ci_dependencies() -> None:
    requirements = DEV_REQUIREMENTS.read_text(encoding="utf-8").splitlines()
    locked = DEV_LOCK.read_text(encoding="utf-8").splitlines()

    assert requirements[-1] == "-r requirements/dev.lock"
    for dependency in (
        "opencv-python==4.13.0.92 \\",
        "pillow==12.1.1 \\",
        "scipy==1.17.0 \\",
        "setuptools==68.1.2 \\",
        "jsonschema==4.10.3 \\",
        "wheel==0.42.0 \\",
    ):
        assert dependency in locked


def test_compatibility_aggregate_uses_only_one_opencv_distribution() -> None:
    names = _requirement_names(COMPATIBILITY_REQUIREMENTS)

    assert "opencv-python" in names
    assert "opencv-python-headless" not in names


def test_requirement_names_follow_nested_includes_relative_to_each_file(
    tmp_path: Path,
) -> None:
    root = tmp_path / "requirements.txt"
    nested = tmp_path / "groups" / "dev.txt"
    leaf = tmp_path / "shared" / "opencv.txt"
    nested.parent.mkdir()
    leaf.parent.mkdir()
    root.write_text("--requirement groups/dev.txt\n", encoding="utf-8")
    nested.write_text("-r ../shared/opencv.txt\npytest==8.4.2\n", encoding="utf-8")
    leaf.write_text("opencv_python==4.13.0.92\n", encoding="utf-8")

    assert _requirement_names(root) == {"opencv-python", "pytest"}


def test_requirement_names_reject_include_cycles_with_chain(tmp_path: Path) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "nested" / "second.txt"
    second.parent.mkdir()
    first.write_text("-r nested/second.txt\n", encoding="utf-8")
    second.write_text("--requirement ../first.txt\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"requirement include cycle: .*first\.txt.*second\.txt.*first\.txt"):
        _requirement_names(first)


@pytest.mark.parametrize("escape_kind", ["traversal", "absolute", "symlink"])
def test_requirement_names_reject_includes_outside_initial_root(
    tmp_path: Path, escape_kind: str
) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    external = tmp_path / "external.txt"
    external.write_text("outside-package==1.0\n", encoding="utf-8")
    root = allowed / "requirements.txt"
    if escape_kind == "traversal":
        directive = "-r ../external.txt"
    elif escape_kind == "absolute":
        directive = f"--requirement {external}"
    else:
        link = allowed / "linked.txt"
        link.symlink_to(external)
        directive = "-rlinked.txt"
    root.write_text(f"{directive}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="requirement include escapes allowed root"):
        _requirement_names(root)


@pytest.mark.parametrize(
    "directive",
    [
        "-r",
        "--requirement",
        '-r ""',
        "--requirement=",
        "-r child.txt extra",
        "--requirement child.txt extra",
        "-rchild.txt extra",
        "--requirement=child.txt extra",
        "--requirementchild.txt",
    ],
)
def test_requirement_names_reject_malformed_include_directives(
    tmp_path: Path, directive: str
) -> None:
    root = tmp_path / "requirements.txt"
    (tmp_path / "child.txt").write_text("child-package==1.0\n", encoding="utf-8")
    root.write_text(f"{directive}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid requirement include"):
        _requirement_names(root)


@pytest.mark.parametrize("directive", ["-rchild.txt", "--requirement=child.txt"])
def test_requirement_names_accept_compact_include_syntax(
    tmp_path: Path, directive: str
) -> None:
    root = tmp_path / "requirements.txt"
    (tmp_path / "child.txt").write_text("child_package==1.0\n", encoding="utf-8")
    root.write_text(f"{directive}\n", encoding="utf-8")

    assert _requirement_names(root) == {"child-package"}


def test_missing_ultralytics_uses_versioned_test_stub() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import runpy; "
                "namespace = runpy.run_path('backend/tests/conftest.py'); "
                "stub = namespace['_make_ultralytics_stub'](); "
                "print(stub.__version__)"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "0.0.0-test-stub"


def test_verifier_stops_at_first_failure_and_prints_correction(
    verifier_repo: tuple[Path, Path],
) -> None:
    npm = verifier_repo[0] / "bin" / "npm"
    npm.write_text(
        """#!/usr/bin/env bash
set -eu
printf 'npm|%s\\n' "$*" >> "$VERIFY_STUB_CALLS"
if [ "$*" = "--prefix frontend run lint" ]; then
  printf 'lint failed\\n'
  exit 9
fi
printf ' Tests  46 passed (46)\\n'
""",
        encoding="utf-8",
    )
    npm.chmod(0o755)

    result = _run_verifier(verifier_repo)

    assert result.returncode != 0
    assert _calls(verifier_repo)[-1] == "npm|--prefix frontend run lint"
    assert "FAILED gate: lint" in result.stderr
    assert f"Corrective command: {REQUIRED_GATE_COMMANDS['lint']}" in result.stderr
    assert not (verifier_repo[0] / ".verification/receipt.json").exists()


def test_verifier_clears_stale_receipt_before_first_gate(
    verifier_repo: tuple[Path, Path],
) -> None:
    receipt = verifier_repo[0] / ".verification/receipt.json"
    receipt.parent.mkdir(); receipt.write_text("stale\n")
    python = verifier_repo[0] / "bin/python3"
    python.write_text("#!/usr/bin/env bash\nexit 9\n", encoding="utf-8")
    python.chmod(0o755)

    result = _run_verifier(verifier_repo)

    assert result.returncode != 0
    assert not receipt.exists()


def test_verifier_fails_when_log_writer_fails(verifier_repo: tuple[Path, Path]) -> None:
    tee = verifier_repo[0] / "bin" / "tee"
    tee.write_text(
        "#!/usr/bin/env bash\ncat >/dev/null\nexit 7\n",
        encoding="utf-8",
    )
    tee.chmod(0o755)

    result = _run_verifier(verifier_repo)

    assert result.returncode != 0
    assert _calls(verifier_repo) == ["python3|-m pytest -q backend/tests"]
    assert "FAILED gate: backend (log writer exit 7)" in result.stderr
    assert f"Corrective command: {REQUIRED_GATE_COMMANDS['backend']}" in result.stderr


@pytest.mark.parametrize("symlink_component", ["verification", "logs"])
def test_verifier_rejects_symlinked_log_components_without_touching_external_files(
    verifier_repo: tuple[Path, Path], tmp_path: Path, symlink_component: str
) -> None:
    root = verifier_repo[0]
    external = tmp_path / "external"
    external.mkdir()
    if symlink_component == "verification":
        (external / "logs").mkdir()
        sentinel = external / "logs" / "sentinel.log"
        (root / ".verification").symlink_to(external, target_is_directory=True)
    else:
        (root / ".verification").mkdir()
        sentinel = external / "sentinel.log"
        (root / ".verification" / "logs").symlink_to(
            external, target_is_directory=True
        )
    sentinel.write_text("preserve me", encoding="utf-8")

    result = _run_verifier(verifier_repo)

    assert result.returncode != 0
    assert "unsafe verification log path" in result.stderr
    assert sentinel.read_text(encoding="utf-8") == "preserve me"
    assert _calls(verifier_repo) == []


def test_verifier_writes_one_log_per_started_gate(verifier_repo: tuple[Path, Path]) -> None:
    result = _run_verifier(verifier_repo)

    assert result.returncode == 0, result.stdout + result.stderr
    logs = sorted(
        path.name for path in (verifier_repo[0] / ".verification" / "logs").glob("*.log")
    )
    assert logs == [
        "backend-startup.log",
        "backend.log",
        "build.log",
        "frontend-tests.log",
        "lint.log",
        "manifest.log",
        "preflight-negatives.log",
        "prod-audit.log",
        "runtime-options.log",
        "sidecar.log",
        "typecheck-app.log",
        "typecheck-node.log",
    ]
    assert "1486 passed" in (
        verifier_repo[0] / ".verification" / "logs" / "backend.log"
    ).read_text(encoding="utf-8")


def test_verifier_rejects_retired_real_smoke_flags_before_any_gate(
    verifier_repo: tuple[Path, Path],
) -> None:
    result = _run_verifier(
        verifier_repo, verify_daytona="1", allow_daytona_mutation="1"
    )

    assert result.returncode != 0
    assert "G-PRODUCT" in result.stderr
    assert "credential rotation" in result.stderr
    assert _calls(verifier_repo) == []


@pytest.mark.parametrize(
    ("verify_daytona", "allow_daytona_mutation"),
    [("1", None), (None, "1"), ("1", "0"), ("0", "1")],
)
def test_daytona_gate_rejects_mismatched_flags_before_any_gate(
    verifier_repo: tuple[Path, Path],
    verify_daytona: str | None,
    allow_daytona_mutation: str | None,
) -> None:
    result = _run_verifier(
        verifier_repo,
        verify_daytona=verify_daytona,
        allow_daytona_mutation=allow_daytona_mutation,
    )

    assert result.returncode != 0
    assert "must both be 0 or both be 1" in result.stderr
    assert _calls(verifier_repo) == []


@pytest.mark.parametrize(
    ("verify_daytona", "allow_daytona_mutation"),
    [("yes", "0"), ("0", "false"), ("2", "2"), ("", "0")],
)
def test_daytona_gate_rejects_non_binary_flags_before_any_gate(
    verifier_repo: tuple[Path, Path],
    verify_daytona: str,
    allow_daytona_mutation: str,
) -> None:
    result = _run_verifier(
        verifier_repo,
        verify_daytona=verify_daytona,
        allow_daytona_mutation=allow_daytona_mutation,
    )

    assert result.returncode != 0
    assert "must be exactly 0 or 1" in result.stderr
    assert _calls(verifier_repo) == []


def test_verifier_and_ci_do_not_contain_external_mutation_commands() -> None:
    combined = VERIFY_SCRIPT.read_text(encoding="utf-8") + CI_WORKFLOW.read_text(
        encoding="utf-8"
    )

    for forbidden in (
        "docker push",
        "runpod",
        "--allow-remote-mutation",
        "run_daytona_gpu_smoke --real-smoke",
    ):
        assert forbidden not in combined


def test_ci_keeps_canonical_verifier_and_declares_acceptance_lanes() -> None:
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "pull_request:" in workflow
    assert "push:" in workflow
    assert "ubuntu-latest" in workflow
    assert "python-version: '3.11'" in workflow
    assert "node-version: '22'" in workflow
    for dependency_file in (
        "pyproject.toml",
        "backend/requirements/api.lock",
        "backend/requirements/dev.lock",
        "backend/requirements/quality-linux.lock",
        "backend/requirements/cpu-cv-macos.lock",
        "backend/requirements/cuda-linux.lock",
        "research-addon/pyproject.toml",
        "frontend/package-lock.json",
    ):
        assert dependency_file in workflow
    assert workflow.count("pip install --require-hashes -r backend/requirements/dev.lock") == 4
    assert workflow.count("sudo apt-get update && sudo apt-get install -y ffmpeg") == 4
    assert "pip install --require-hashes -r backend/requirements/cuda-linux.lock" in workflow
    assert workflow.count("pip install -e . --no-deps") == 2
    assert workflow.count("pip install -e '.[cv]' --no-deps") == 3
    assert "pip install -e '.[cv,cuda]' --no-deps" in workflow
    assert not re.search(r"pip install -e [^\n]+ -r ", workflow)
    assert "pip install -e ./research-addon" in workflow
    assert "opencv-python-headless==4.13.0.92" not in workflow
    assert "opencv-python==4.13.0.92" not in workflow
    assert "pillow==12.1.1" not in workflow
    assert "scipy==1.17.0" not in workflow
    assert "Install backend test CV dependencies" not in workflow
    assert "npm ci --prefix frontend" in workflow
    assert "run: scripts/verify.sh" in workflow
    assert "backend/tests/code_only_exclusions.txt" in workflow
    assert "VERIFY_DAYTONA: '0'" in workflow
    assert "ALLOW_DAYTONA_MUTATION: '0'" in workflow
    assert "DAYTONA_API_KEY" not in workflow
    assert "if: always()" in workflow
    assert ".verification/logs/" in workflow
    assert 'pytest -m "integration or real_media" backend/tests' in workflow
    assert "pytest -m real_media backend/tests" in workflow
    assert workflow.count("set -o pipefail") == 4
    assert "ruff check backend --select F821,F822,F823" in workflow
    assert "ruff check backend --select RUF100,B023,ANN001,ANN002,ANN003,ANN201,ANN202,ARG002,BLE001,E402,F401,N802,N803,S310 --exit-zero" in workflow
    assert "pip install --require-hashes -r backend/requirements/quality-linux.lock" in workflow
    assert "github.event_name == 'workflow_dispatch'" in workflow
    assert "npm test" not in workflow


def test_code_only_exclusion_manifest_is_shared_by_verifier_and_ci() -> None:
    manifest = REPO_ROOT / "backend" / "tests" / "code_only_exclusions.txt"
    entries = [
        line.strip()
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert entries == [
        "backend/tests/test_convert_football_analysis_pilot_cvat_labels.py",
        "backend/tests/test_evaluate_football_analysis_pilot_soccertrack_events.py",
        "backend/tests/test_gpu_worker.py",
        "backend/tests/test_operational_docs.py",
        "backend/tests/test_run_guerilla.py",
        "backend/tests/test_run_source_robustness_batch.py",
    ]
    assert "code_only_exclusions.txt" in VERIFY_SCRIPT.read_text(encoding="utf-8")
    assert "code_only_exclusions.txt" in CI_WORKFLOW.read_text(encoding="utf-8")
