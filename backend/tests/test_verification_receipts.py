from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from backend.tests import conftest as verification_plugin
from backend.scripts.write_lane_receipt import build_pytest_receipt


def _git_repo(root: Path) -> str:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Receipt Tests"], cwd=root, check=True)
    (root / "tracked.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _config(root: Path, *, args: tuple[str, ...] = ("-q",)) -> SimpleNamespace:
    return SimpleNamespace(
        rootpath=root,
        invocation_params=SimpleNamespace(args=args),
        stash={verification_plugin._STUBS_KEY: ()},
    )


def test_pytest_receipt_does_not_carry_old_counts_into_new_invocation(
    tmp_path, monkeypatch
) -> None:
    _git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GA_VERIFICATION_RUN", "1")
    receipt_path = tmp_path / ".verification" / "receipt.json"
    receipt_path.parent.mkdir()
    receipt_path.write_text(
        json.dumps(
            {
                "commit": "old-source",
                "profile": "old-profile",
                "tests": {"passed": 100, "failed": 0, "skipped": 0},
            }
        ),
        encoding="utf-8",
    )
    reporter = SimpleNamespace(
        stats={"passed": [SimpleNamespace(nodeid="test_example.py::test_one")]},
        write_line=lambda _line: None,
    )
    config = _config(tmp_path)

    verification_plugin.pytest_terminal_summary(reporter, 0, config)

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["tests"]["passed"] == 1


def test_repeated_pytest_runs_are_separate_and_latest_is_not_a_sum(
    tmp_path, monkeypatch
) -> None:
    _git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GA_VERIFICATION_RUN", "1")
    monkeypatch.delenv("GA_VERIFICATION_PROFILE", raising=False)
    monkeypatch.delenv("VERIFY_CODE_ONLY", raising=False)
    config = _config(tmp_path, args=("-q", "test_example.py"))

    verification_plugin.pytest_terminal_summary(
        SimpleNamespace(stats={"passed": [SimpleNamespace(nodeid="test_example.py::test_one")]}, write_line=lambda _line: None),
        0,
        config,
    )
    verification_plugin.pytest_terminal_summary(
        SimpleNamespace(
            stats={
                "passed": [
                    SimpleNamespace(nodeid="test_example.py::test_one"),
                    SimpleNamespace(nodeid="test_example.py::test_two"),
                ]
            },
            write_line=lambda _line: None,
        ),
        0,
        config,
    )

    runs = sorted((tmp_path / ".verification" / "pytest-runs").glob("*.json"))
    latest = json.loads((tmp_path / ".verification" / "receipt.json").read_text(encoding="utf-8"))
    assert len(runs) == 2
    assert len({json.loads(path.read_text())["runId"] for path in runs}) == 2
    assert latest["tests"]["passed"] == 2
    assert latest["profile"] == "local"
    assert latest["stubsActive"] == []


def test_latest_run_uses_its_own_profile_and_stubs(tmp_path, monkeypatch) -> None:
    _git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GA_VERIFICATION_RUN", "1")
    monkeypatch.setenv("GA_VERIFICATION_PROFILE", "changed-profile")
    config = _config(tmp_path)
    config.stash[verification_plugin._STUBS_KEY] = ("ultralytics",)

    verification_plugin.pytest_terminal_summary(
        SimpleNamespace(stats={"passed": [SimpleNamespace(nodeid="test_one.py::test_one")]}, write_line=lambda _line: None),
        0,
        config,
    )

    receipt = json.loads((tmp_path / ".verification" / "receipt.json").read_text())
    assert receipt["profile"] == "changed-profile"
    assert receipt["stubsActive"] == ["ultralytics"]


def test_receipt_binds_checkout_not_event_sha_and_records_dirty_identity(
    tmp_path, monkeypatch
) -> None:
    commit = _git_repo(tmp_path)
    (tmp_path / "tracked.txt").write_text("changed\n", encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setenv("GA_VERIFICATION_RUN", "1")
    monkeypatch.setenv("GITHUB_SHA", "f" * 40)

    verification_plugin.pytest_terminal_summary(
        SimpleNamespace(stats={"passed": [SimpleNamespace(nodeid="test_one.py::test_one")]}, write_line=lambda _line: None),
        0,
        _config(tmp_path, args=("test_one.py",)),
    )

    receipt = json.loads((tmp_path / ".verification" / "receipt.json").read_text())
    assert receipt["commit"] == commit
    assert receipt["eventCommit"] == "f" * 40
    assert receipt["dirty"] is True
    assert len(receipt["diffSha256"]) == 64


def test_dirty_identity_includes_untracked_file_bytes(tmp_path) -> None:
    _git_repo(tmp_path)
    untracked = tmp_path / "candidate-test.py"
    untracked.write_text("first", encoding="utf-8")
    kwargs = dict(
        repo_root=tmp_path, run_id="run", session_id=None, args=("-q",),
        profile="local", stubs=(), exit_code=0, counts={}, selected_node_ids=[],
    )
    first = build_pytest_receipt(**kwargs)
    untracked.write_text("second", encoding="utf-8")
    second = build_pytest_receipt(**kwargs)

    assert first["diffSha256"] != second["diffSha256"]


def test_real_child_pytest_records_nonzero_exit_and_selected_nodes(tmp_path) -> None:
    _git_repo(tmp_path)
    test_file = tmp_path / "test_child.py"
    test_file.write_text(
        "def test_pass(): pass\n\ndef test_fail(): assert False\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update({"GA_VERIFICATION_RUN": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[2])})

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "backend.tests.conftest", str(test_file)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    receipt = json.loads((tmp_path / ".verification" / "receipt.json").read_text())
    assert result.returncode == 1
    assert receipt["exitCode"] == 1
    assert receipt["tests"]["passed"] == 1
    assert receipt["tests"]["failed"] == 1
    assert receipt["selectedNodeIds"] == [
        "test_child.py::test_pass",
        "test_child.py::test_fail",
    ]


def test_selected_nodes_come_from_collection_even_when_x_stops_execution(tmp_path) -> None:
    _git_repo(tmp_path)
    test_file = tmp_path / "test_child.py"
    test_file.write_text(
        "def test_fail(): assert False\n\ndef test_not_run(): assert True\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update({"GA_VERIFICATION_RUN": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[2])})

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-x", "-p", "backend.tests.conftest", str(test_file)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    receipt = json.loads((tmp_path / ".verification" / "receipt.json").read_text())
    assert result.returncode == 1
    assert receipt["selectedNodeIds"] == [
        "test_child.py::test_fail",
        "test_child.py::test_not_run",
    ]


@pytest.mark.parametrize(
    ("content", "extra_args", "exit_code", "outcome", "count"),
    [
        ("import missing_receipt_dependency\n", (), 2, "error", 1),
        ("import pytest\n@pytest.mark.skip(reason='no')\ndef test_skip(): pass\n@pytest.mark.xfail(reason='known')\ndef test_xfail(): assert False\n", (), 0, "xfailed", 1),
        ("def test_exists(): pass\n", ("-k", "missing_name"), 5, "passed", 0),
    ],
)
def test_real_child_pytest_records_nonpassing_outcomes(
    tmp_path, content, extra_args, exit_code, outcome, count
) -> None:
    _git_repo(tmp_path)
    test_file = tmp_path / "test_child.py"
    test_file.write_text(content, encoding="utf-8")
    env = os.environ.copy()
    env.update({"GA_VERIFICATION_RUN": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[2])})

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "backend.tests.conftest", str(test_file), *extra_args],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    receipt = json.loads((tmp_path / ".verification" / "receipt.json").read_text())
    assert result.returncode == exit_code
    assert receipt["exitCode"] == exit_code
    assert receipt["tests"][outcome] == count
    if exit_code == 5:
        assert receipt["selectedCount"] == 0


def test_malformed_previous_receipt_is_explicitly_replaced(tmp_path, monkeypatch) -> None:
    _git_repo(tmp_path)
    verification = tmp_path / ".verification"
    verification.mkdir()
    (verification / "receipt.json").write_text("not json", encoding="utf-8")
    monkeypatch.setenv("GA_VERIFICATION_RUN", "1")

    verification_plugin.pytest_terminal_summary(
        SimpleNamespace(stats={}, write_line=lambda _line: None),
        5,
        _config(tmp_path),
    )

    receipt = json.loads((verification / "receipt.json").read_text())
    assert receipt["priorReceiptStatus"] == "malformed"


def test_pytest_receipt_rejects_symlinked_run_directory(tmp_path, monkeypatch) -> None:
    _git_repo(tmp_path)
    verification = tmp_path / ".verification"
    verification.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    (verification / "pytest-runs").symlink_to(external, target_is_directory=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GA_VERIFICATION_RUN", "1")

    with pytest.raises(OSError, match="pytest-runs"):
        verification_plugin.pytest_terminal_summary(
            SimpleNamespace(stats={}, write_line=lambda _line: None), 0, _config(tmp_path)
        )

    assert list(external.iterdir()) == []
