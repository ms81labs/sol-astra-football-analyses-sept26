"""Receipt admission counterexamples use disposable repositories, never real gates."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from backend.scripts import write_lane_receipt as writer


def _repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    for key, value in (("user.name", "Receipt Test"), ("user.email", "test@example.invalid")):
        subprocess.run(["git", "-C", str(root), "config", key, value], check=True)
    (root / ".gitignore").write_text(".verification/\n")
    (root / "tracked.py").write_text("VALUE = 1\n")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)


def _receipt(root: Path, run_id: str = "a" * 32) -> dict:
    result = writer.build_pytest_receipt(
        repo_root=root, run_id=run_id, session_id="session",
        args=("-q", "backend/tests"), profile="code-only", stubs=("ultralytics",),
        exit_code=0, counts={"passed": 1, "failed": 0, "error": 0},
        selected_node_ids=["backend/tests/test_example.py::test_one"],
    )
    result["gate"] = "backend"
    return result


def _save(root: Path, run: dict) -> None:
    (root / ".verification/pytest-runs" / f'{run["runId"]}.json').write_text(json.dumps(run))


def _gates(root: Path, monkeypatch) -> dict:
    _repo(root)
    (root / ".verification/logs").mkdir(parents=True)
    (root / ".verification/pytest-runs").mkdir()
    monkeypatch.chdir(root)
    monkeypatch.setenv("GA_VERIFICATION_SESSION_ID", "session")
    monkeypatch.setenv("GA_VERIFICATION_PROFILE", "code-only")
    names = ["backend", "sidecar", "frontend-tests", "lint", "typecheck-app",
             "typecheck-node", "build", "backend-startup", "prod-audit"]
    run = _receipt(root)
    rows = []
    for name in names:
        command = "python3 -m pytest -q backend/tests" if name == "backend" else f"fixture-{name}"
        log_digest = hashlib.sha256(b"Synthetic gate fixture.\n").hexdigest()
        rows.append(f'session\t{run["commit"]}\t{name}\t0\t{log_digest}\t{command}')
        (root / ".verification/logs" / f"{name}.log").write_text("Synthetic gate fixture.\n")
    (root / ".verification/gates.tsv").write_text("\n".join(rows) + "\n")
    _save(root, run)
    return run


@pytest.mark.parametrize("dangling", [False, True])
def test_receipt_leaf_symlink_never_changes_its_target(tmp_path, dangling) -> None:
    root = tmp_path / "repo"
    _repo(root)
    (root / ".verification").mkdir()
    target = tmp_path / "outside.json"
    if not dangling:
        target.write_text("preserve me")
    (root / ".verification/receipt.json").symlink_to(target)
    with pytest.raises(OSError):
        writer.write_pytest_receipt(
            repo_root=root, output_root=root, args=("-q",), profile="test", stubs=(),
            exit_code=0, counts={"passed": 1}, selected_node_ids=["test::one"],
        )
    assert not target.exists() if dangling else target.read_text() == "preserve me"


@pytest.mark.parametrize("field,value", [
    ("tree", "f" * 40), ("profile", "different"), ("exitCode", 1),
    ("tests", {"passed": 1, "failed": 1}), ("tests", {"passed": 1, "error": 1}),
    ("args", ["-q", "research-addon/tests"]), ("selectedCount", 0),
    ("selectedNodeIds", ["research-addon/tests/test_x.py::test_x"]),
    ("diffSha256", "f" * 64), ("kind", "unrelated"), ("schemaVersion", 1),
])
def test_final_writer_rejects_misbound_backend_receipt(tmp_path, monkeypatch, field, value) -> None:
    run = _gates(tmp_path, monkeypatch)
    run[field] = value
    _save(tmp_path, run)
    with pytest.raises((RuntimeError, ValueError), match="receipt|source|profile|selection|backend"):
        writer.main()
    assert not (tmp_path / ".verification/receipt.json").exists()


def test_final_writer_rejects_post_test_source_changes(tmp_path, monkeypatch) -> None:
    _gates(tmp_path, monkeypatch)
    (tmp_path / "tracked.py").write_text("VALUE = 2\n")
    with pytest.raises(RuntimeError, match="source"):
        writer.main()


def test_final_writer_rejects_profile_relabelling(tmp_path, monkeypatch) -> None:
    _gates(tmp_path, monkeypatch)
    monkeypatch.setenv("GA_VERIFICATION_PROFILE", "another-profile")
    with pytest.raises(RuntimeError, match="profile"):
        writer.main()


def test_unrelated_invocation_cannot_erase_backend_stubs(tmp_path, monkeypatch) -> None:
    run = _gates(tmp_path, monkeypatch)
    other = {**run, "runId": "z" * 32, "gate": "sidecar", "stubsActive": []}
    _save(tmp_path, other)
    writer.main()
    result = json.loads((tmp_path / ".verification/receipt.json").read_text())
    assert result["stubsActive"] == ["ultralytics"]
    assert result["gates"][0]["pytestRunId"] == run["runId"]
    assert result["dirty"] == run["dirty"]
    assert result["diffSha256"] == run["diffSha256"]


def test_duplicate_backend_invocations_fail_instead_of_choosing_a_uuid(tmp_path, monkeypatch) -> None:
    run = _gates(tmp_path, monkeypatch)
    _save(tmp_path, {**run, "runId": "b" * 32, "stubsActive": []})
    with pytest.raises(RuntimeError, match="backend.*receipt|receipt.*backend"):
        writer.main()


@pytest.mark.parametrize("leaf", ["receipt.json", "gates.tsv", "logs/backend.log", "pytest-runs/" + "a" * 32 + ".json"])
def test_final_writer_refuses_symlinked_evidence(tmp_path, monkeypatch, leaf) -> None:
    _gates(tmp_path, monkeypatch)
    target = tmp_path / "outside"
    path = tmp_path / ".verification" / leaf
    target.write_text(path.read_text() if path.exists() else "sentinel")
    original = target.read_bytes()
    path.unlink(missing_ok=True)
    path.symlink_to(target)
    with pytest.raises((OSError, ValueError, RuntimeError)):
        writer.main()
    assert target.read_bytes() == original


def test_final_writer_rejects_source_changed_during_test_invocation(tmp_path, monkeypatch) -> None:
    run = _gates(tmp_path, monkeypatch)
    run["sourceStart"] = {**run["sourceStart"], "diffSha256": "f" * 64}
    _save(tmp_path, run)
    with pytest.raises(RuntimeError, match="source"):
        writer.main()


def test_final_writer_rejects_replaced_gate_log(tmp_path, monkeypatch) -> None:
    _gates(tmp_path, monkeypatch)
    (tmp_path / ".verification/logs/backend.log").write_text("older unrelated success")
    with pytest.raises(RuntimeError, match="log differs"):
        writer.main()


def test_unchanged_dirty_source_is_retained_not_called_clean(tmp_path, monkeypatch) -> None:
    _gates(tmp_path, monkeypatch)
    (tmp_path / "tracked.py").write_text("VALUE = 3\n")
    run = _receipt(tmp_path)
    _save(tmp_path, run)
    writer.main()
    result = json.loads((tmp_path / ".verification/receipt.json").read_text())
    assert result["dirty"] is True
    assert result["diffSha256"] == run["diffSha256"]


def test_evidence_outputs_do_not_change_the_source_digest(tmp_path) -> None:
    _repo(tmp_path)
    # Also exercise a repo without a gitignore entry for generated evidence.
    (tmp_path / ".gitignore").write_text("")
    before = writer.source_identity(tmp_path)
    (tmp_path / ".verification").mkdir()
    (tmp_path / ".verification/receipt.json").write_text("generated")
    assert writer.source_identity(tmp_path) == before


def test_gate_log_digest_preserves_carriage_returns(tmp_path, monkeypatch) -> None:
    _gates(tmp_path, monkeypatch)
    content = b"progress\rfinished\r\n"
    (tmp_path / ".verification/logs/backend.log").write_bytes(content)
    gates = tmp_path / ".verification/gates.tsv"
    lines = gates.read_text().splitlines()
    fields = lines[0].split("\t", 5)
    fields[4] = hashlib.sha256(content).hexdigest()
    lines[0] = "\t".join(fields)
    gates.write_text("\n".join(lines) + "\n")
    writer.main()
    result = json.loads((tmp_path / ".verification/receipt.json").read_text())
    assert result["gates"][0]["logSha256"] == fields[4]
