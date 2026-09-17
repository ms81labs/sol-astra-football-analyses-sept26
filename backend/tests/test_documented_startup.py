from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import tomllib
from urllib.request import urlopen
import zipfile

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SIDECAR_ROOT = REPOSITORY_ROOT / "research-addon"
_ENSUREPIP_AVAILABLE = __import__("importlib.util").util.find_spec("ensurepip") is not None


def _host_pytest_site_packages() -> str:
    return str(Path(pytest.__file__).resolve().parents[1])


def _environment_without_pythonpath() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONNOUSERSITE"] = "1"
    return environment


def _run(
    *command: str | Path,
    cwd: Path,
    env_updates: dict[str, str] | None = None,
    env_removals: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    environment = _environment_without_pythonpath()
    if env_updates:
        environment.update(env_updates)
    for name in env_removals:
        environment.pop(name, None)
    return subprocess.run(
        [str(part) for part in command],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _assert_succeeded(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, (
        f"command failed with exit code {result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def _create_venv(venv_root: Path) -> Path:
    command = [sys.executable, "-m", "venv"]
    command.append(str(venv_root))
    result = _run(*command, cwd=venv_root.parent)
    _assert_succeeded(result)
    return venv_root / "bin" / "python"


def _build_wheel(source_root: Path, wheel_root: Path) -> Path:
    build_source = wheel_root.parent / f"{wheel_root.name}-source"
    shutil.copytree(
        source_root,
        build_source,
        ignore=shutil.ignore_patterns(
            ".git",
            ".worktrees",
            ".pytest_cache",
            "__pycache__",
            "*.egg-info",
            "build",
            "node_modules",
            "storage",
        ),
    )
    wheel_root.mkdir()
    result = _run(
        sys.executable,
        "-m",
        "pip",
        "wheel",
        "--no-build-isolation",
        "--no-deps",
        "--wheel-dir",
        wheel_root,
        build_source,
        cwd=wheel_root.parent,
    )
    _assert_succeeded(result)
    wheels = list(wheel_root.glob("*.whl"))
    assert len(wheels) == 1, wheels
    return wheels[0]


def _install_wheel(
    python: Path,
    wheel: Path,
    cwd: Path,
    *,
    with_dependencies: bool = True,
) -> None:
    command: list[str | Path] = [python, "-m", "pip", "install"]
    if not with_dependencies:
        command.append("--no-deps")
    command.append(wheel)
    result = _run(*command, cwd=cwd)
    _assert_succeeded(result)


def _install_dev_requirements(python: Path, cwd: Path) -> None:
    result = _run(
        python,
        "-m",
        "pip",
        "install",
        "-r",
        REPOSITORY_ROOT / "backend" / "requirements-dev.txt",
        cwd=cwd,
    )
    _assert_succeeded(result)


def _storage_snapshot() -> dict[str, tuple[int, int]]:
    storage_root = REPOSITORY_ROOT / "backend" / "storage"
    if not storage_root.exists():
        return {}
    return {
        str(path.relative_to(storage_root)): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in storage_root.rglob("*")
        if path.is_file()
    }


def _tree_snapshot(root: Path) -> dict[str, tuple[int, int, int, str | None]]:
    snapshot: dict[str, tuple[int, int, int, str | None]] = {}
    for path in sorted(root.rglob("*")):
        stat = path.stat()
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        snapshot[str(path.relative_to(root))] = (
            stat.st_mode,
            stat.st_size,
            stat.st_mtime_ns,
            digest,
        )
    return snapshot


def _make_tree_read_only(root: Path) -> dict[Path, int]:
    original_modes: dict[Path, int] = {}
    for path in [root, *root.rglob("*")]:
        original_modes[path] = path.stat().st_mode
        path.chmod(original_modes[path] & ~0o222)
    return original_modes


def _restore_tree_modes(original_modes: dict[Path, int]) -> None:
    for path, mode in original_modes.items():
        if path.exists():
            path.chmod(mode)


def _start_asgi_server(python: Path, cwd: Path, environment: dict[str, str]) -> None:
    with socket.socket() as port_socket:
        port_socket.bind(("127.0.0.1", 0))
        port = port_socket.getsockname()[1]

    process = subprocess.Popen(
        [
            str(python),
            "-m",
            "uvicorn",
            "backend.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 20
        while True:
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                raise AssertionError(
                    f"uvicorn exited with {process.returncode}\n"
                    f"stdout:\n{stdout}\nstderr:\n{stderr}"
                )
            try:
                with urlopen(f"http://127.0.0.1:{port}/docs", timeout=1) as response:
                    assert response.status == 200
                    break
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.2)
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def test_readme_installs_and_starts_backend_from_repository_root() -> None:
    readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")

    assert "python -m pip install . -r backend/requirements-dev.txt\n" in readme
    assert "export GUERILLA_STORAGE_ROOT=" in readme
    assert "python -m pip install -r backend/requirements-ml.txt" in readme
    assert "python -m uvicorn backend.app.main:app" in readme
    assert "python -m uvicorn app.main:app" not in readme


def test_root_package_metadata_declares_release_data_without_runtime_storage() -> None:
    with (REPOSITORY_ROOT / "pyproject.toml").open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)

    assert pyproject["project"]["requires-python"] == ">=3.11"
    assert pyproject["tool"]["setuptools"]["packages"]["find"]["include"] == [
        "backend*"
    ]
    assert pyproject["tool"]["setuptools"]["packages"]["find"]["exclude"] == [
        "backend.storage*",
        "backend.tests*",
    ]
    assert pyproject["tool"]["setuptools"]["package-data"]["backend"] == [
        "release/*.json",
        "release/verification/*.json",
    ]
    assert pyproject["tool"]["setuptools"]["exclude-package-data"]["backend"] == [
        "storage/*",
        "storage/**/*",
    ]


def test_storage_root_precedence_uses_explicit_then_environment_then_safe_default(
    monkeypatch,
    tmp_path: Path,
) -> None:
    environment_root = tmp_path / "environment-storage"
    default_data_home = tmp_path / "default-data-home"
    explicit_root = tmp_path / "explicit-storage"
    monkeypatch.setenv("GUERILLA_STORAGE_ROOT", str(environment_root))
    monkeypatch.setenv("XDG_DATA_HOME", str(default_data_home))

    from backend.app import main

    explicit_app = main.create_app(storage_root=explicit_root)
    environment_app = main.create_app()
    monkeypatch.delenv("GUERILLA_STORAGE_ROOT")
    default_app = main.create_app()

    assert explicit_app.state.storage.storage_root == explicit_root
    assert environment_app.state.storage.storage_root == environment_root
    assert default_app.state.storage.storage_root == default_data_home / "guerilla-analytics"
    assert not default_app.state.storage.storage_root.is_relative_to(
        Path(main.__file__).resolve().parents[1]
    )


def test_collect_only_uses_and_removes_pytest_owned_storage(tmp_path: Path) -> None:
    home_root = tmp_path / "home"
    data_root = tmp_path / "xdg-data"
    temporary_root = tmp_path / "temporary"
    plugin_root = tmp_path / "plugin"
    observed_storage_root = tmp_path / "observed-storage-root"
    for path in (home_root, data_root, temporary_root, plugin_root):
        path.mkdir()
    (plugin_root / "pytest_storage_observer.py").write_text(
        "import os\n"
        "from pathlib import Path\n"
        "def pytest_collection_finish(session):\n"
        "    Path(os.environ['GUERILLA_PYTEST_STORAGE_OBSERVER']).write_text(\n"
        "        os.environ['GUERILLA_STORAGE_ROOT'], encoding='utf-8'\n"
        "    )\n",
        encoding="utf-8",
    )

    result = _run(
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "pytest_storage_observer",
        "--collect-only",
        "-q",
        "backend/tests/test_api.py",
        cwd=REPOSITORY_ROOT,
        env_updates={
            "HOME": str(home_root),
            "XDG_DATA_HOME": str(data_root),
            "TMPDIR": str(temporary_root),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "PYTHONPATH": os.pathsep.join((str(plugin_root), _host_pytest_site_packages())),
            "GUERILLA_PYTEST_STORAGE_OBSERVER": str(observed_storage_root),
        },
        env_removals=("GUERILLA_STORAGE_ROOT",),
    )

    _assert_succeeded(result)
    assert "backend/tests/test_api.py::test_match_import_lifecycle_from_tracking_json" in result.stdout
    assert not (data_root / "guerilla-analytics").exists()
    pytest_storage_root = Path(observed_storage_root.read_text(encoding="utf-8"))
    assert pytest_storage_root.parent == temporary_root
    assert pytest_storage_root.name.startswith("guerilla-pytest-storage-")
    assert not pytest_storage_root.exists()


@pytest.mark.skipif(not _ENSUREPIP_AVAILABLE, reason="environment has no ensurepip/python3-venv")
def test_root_package_builds_and_imports_documented_asgi_target_outside_checkout(
    tmp_path: Path,
    request,
) -> None:
    before_storage = _storage_snapshot()
    wheel = _build_wheel(REPOSITORY_ROOT, tmp_path / "root-wheels")
    with zipfile.ZipFile(wheel) as archive:
        packaged_paths = archive.namelist()
    assert not any(path.startswith("backend/tests/") for path in packaged_paths)
    assert "backend/app/main.py" in packaged_paths
    assert "backend/scripts/run_daytona_gpu_smoke.py" in packaged_paths
    assert "backend/release/v7.3.json" in packaged_paths
    python = _create_venv(tmp_path / "root-venv")
    _install_wheel(python, wheel, tmp_path)
    _install_dev_requirements(python, tmp_path)

    outside_checkout = tmp_path / "outside-checkout"
    outside_checkout.mkdir()
    backend_location = _run(
        python,
        "-c",
        (
            "from importlib.util import find_spec; "
            "from pathlib import Path; "
            "spec = find_spec('backend'); "
            "print(Path(next(iter(spec.submodule_search_locations))).resolve())"
        ),
        cwd=outside_checkout,
    )
    _assert_succeeded(backend_location)
    installed_backend_root = Path(backend_location.stdout.strip())
    original_modes = _make_tree_read_only(installed_backend_root)
    request.addfinalizer(lambda: _restore_tree_modes(original_modes))
    before_package = _tree_snapshot(installed_backend_root)
    configured_storage = tmp_path / "configured-storage"
    environment_updates = {
        "GUERILLA_STORAGE_ROOT": str(configured_storage),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    result = _run(
        python,
        "-c",
        (
            "from backend.app.main import app; "
            "from importlib.util import find_spec; "
            "from pathlib import Path; "
            "import lap; "
            "import sys; "
            "import backend.app.main as main; "
            "import backend.app.run_benchmarks; "
            "assert app.title == 'Guerilla Analytics API'; "
            f"assert app.state.storage.storage_root == Path({str(configured_storage)!r}); "
            f"assert not Path(lap.__file__).resolve().is_relative_to(Path({str(REPOSITORY_ROOT)!r})); "
            "assert find_spec('torch') is None; "
            "assert find_spec('ultralytics') is None; "
            "assert 'backend.app.processor' not in sys.modules; "
            "assert 'backend.run_guerilla' not in sys.modules; "
            f"assert not Path(main.__file__).resolve().is_relative_to(Path({str(REPOSITORY_ROOT)!r})); "
            "print('backend.app.main:app imported')"
        ),
        cwd=outside_checkout,
        env_updates=environment_updates,
    )

    _assert_succeeded(result)
    assert result.stdout == "backend.app.main:app imported\n"
    assert result.stderr == ""
    server_environment = _environment_without_pythonpath()
    server_environment.update(environment_updates)
    _start_asgi_server(python, outside_checkout, server_environment)
    assert (configured_storage / "guerilla.sqlite3").is_file()
    assert not (installed_backend_root / "storage").exists()
    assert _tree_snapshot(installed_backend_root) == before_package
    assert _storage_snapshot() == before_storage


@pytest.mark.skipif(not _ENSUREPIP_AVAILABLE, reason="environment has no ensurepip/python3-venv")
def test_sidecar_package_installs_imports_and_exposes_cli_without_pythonpath(
    tmp_path: Path,
    request,
) -> None:
    wheel = _build_wheel(SIDECAR_ROOT, tmp_path / "sidecar-wheels")
    venv_root = tmp_path / "sidecar-venv"
    python = _create_venv(venv_root)
    _install_wheel(python, wheel, tmp_path, with_dependencies=False)

    outside_checkout = tmp_path / "outside-sidecar-checkout"
    outside_checkout.mkdir()
    import_result = _run(
        python,
        "-c",
        "import research_addon; print(research_addon.__name__)",
        cwd=outside_checkout,
    )
    _assert_succeeded(import_result)
    assert import_result.stdout == "research_addon\n"
    assert import_result.stderr == ""

    package_location = _run(
        python,
        "-c",
        (
            "from pathlib import Path; import research_addon; "
            "print(Path(research_addon.__file__).resolve().parent)"
        ),
        cwd=outside_checkout,
        env_updates={"PYTHONDONTWRITEBYTECODE": "1"},
    )
    # Keep the installed package itself inert during readiness checks and execution.
    _assert_succeeded(package_location)
    installed_package = Path(package_location.stdout.strip())
    original_modes = _make_tree_read_only(installed_package)
    request.addfinalizer(lambda: _restore_tree_modes(original_modes))
    before_package = _tree_snapshot(installed_package)

    cli_result = _run(
        venv_root / "bin" / "research-addon",
        "tracks",
        "list",
        cwd=outside_checkout,
        env_updates={"PYTHONDONTWRITEBYTECODE": "1"},
    )
    _assert_succeeded(cli_result)
    assert cli_result.stdout == (
        "Available tracks:\n"
        "  supported-coverage  [available-with-config]  Active research track\n"
        "\n"
        "Planned tracks (not executable):\n"
        "  possession/events    [planned]     Future track\n"
        "  trust-crops          [planned]     Future track\n"
        "  gpu-bounded-loops    [planned]     Future track\n"
        "  later-training       [planned]     Future track\n"
    )
    assert cli_result.stderr == ""

    fixture_repository = tmp_path / "fixture-repository"
    delegate = fixture_repository / "backend" / "scripts" / "run_local_app_path_proof.py"
    delegate.parent.mkdir(parents=True)
    video = fixture_repository / "fixture.mp4"
    video.write_bytes(b"fixture-video")
    storage = tmp_path / "sidecar-storage"
    storage.mkdir()
    manifest = tmp_path / "sidecar-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "video_id": "fixture",
                        "video_path": "fixture.mp4",
                        "ground_truth_path": None,
                        "tags": ["test"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    selected_python = python.resolve()
    delegate.write_text(
        (
            "import argparse, json, sys\n"
            "from pathlib import Path\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--storage-root')\n"
            "parser.add_argument('--video-path')\n"
            "parser.add_argument('--poll-interval-seconds')\n"
            "parser.add_argument('--timeout-seconds')\n"
            "args = parser.parse_args()\n"
            f"assert Path(sys.executable).resolve() == Path({str(selected_python)!r})\n"
            f"assert Path.cwd() == Path({str(fixture_repository.resolve())!r})\n"
            f"assert Path(args.storage_root) == Path({str(storage.resolve())!r})\n"
            f"assert Path(args.video_path) == Path({str(video.resolve())!r})\n"
            "print(json.dumps({"
            "'acceptedBallFrames': 1, 'supportedAcceptedBallRatio': 1.0, "
            "'controlledPossessionFrames': 1, 'eventFamilyCount': 1, "
            "'truthGateReasons': []}))\n"
        ),
        encoding="utf-8",
    )
    context = (
        "--manifest",
        str(manifest),
        "--repo-root",
        str(fixture_repository),
        "--python",
        str(selected_python),
    )
    ready_result = _run(
        venv_root / "bin" / "research-addon",
        "tracks",
        "list",
        *context,
        cwd=outside_checkout,
        env_updates={"PYTHONDONTWRITEBYTECODE": "1"},
    )
    _assert_succeeded(ready_result)
    assert "supported-coverage  [executable-now]" in ready_result.stdout

    judge_result = _run(
        venv_root / "bin" / "research-addon",
        "judge",
        "supported-coverage",
        *context,
        "--storage-root",
        str(storage),
        cwd=outside_checkout,
        env_updates={"PYTHONDONTWRITEBYTECODE": "1"},
    )
    _assert_succeeded(judge_result)
    assert json.loads(judge_result.stdout) == {
        "acceptedBallFrames": 1,
        "supportedAcceptedBallRatio": 1.0,
        "controlledPossessionFrames": 1,
        "eventFamilyCount": 1,
        "truthGateReasons": [],
    }

    delegate.write_text("import sys\nsys.exit(7)\n", encoding="utf-8")
    nonzero_result = _run(
        venv_root / "bin" / "research-addon",
        "judge",
        "supported-coverage",
        *context,
        "--storage-root",
        str(storage),
        cwd=outside_checkout,
        env_updates={"PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert nonzero_result.returncode == 7
    assert "Proof script exited with 7" in nonzero_result.stderr
    assert "Traceback" not in nonzero_result.stderr

    delegate.write_text("print('not-json')\n", encoding="utf-8")
    malformed_result = _run(
        venv_root / "bin" / "research-addon",
        "judge",
        "supported-coverage",
        *context,
        "--storage-root",
        str(storage),
        cwd=outside_checkout,
        env_updates={"PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert malformed_result.returncode == 1
    assert "non-JSON output" in malformed_result.stderr
    assert "Traceback" not in malformed_result.stderr
    assert _tree_snapshot(installed_package) == before_package
