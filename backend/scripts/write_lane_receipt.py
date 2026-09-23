"""Summarize all code-only verification gates in one source-bound receipt."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import uuid


from backend.app.remote_contracts import atomic_write_json, confined_path, RemoteContractError
from backend.app.storage_remote import open_regular_file


def _git(repo_root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def source_identity(repo_root: Path) -> dict[str, object]:
    """Identify source bytes, excluding only this writer's generated evidence."""
    status = _git(repo_root, "status", "--porcelain=v1", "--untracked-files=all", "--", ".", ":(exclude).verification")
    diff = _git(repo_root, "diff", "--binary", "HEAD", "--", ".", ":(exclude).verification")
    untracked = _git(repo_root, "ls-files", "--others", "--exclude-standard", "-z", "--", ".", ":(exclude).verification")
    dirty = hashlib.sha256()
    dirty.update(status.encode())
    dirty.update(b"\0")
    dirty.update(diff.encode())
    for relative in sorted(filter(None, untracked.split("\0"))):
        path = repo_root / relative
        mode = path.lstat().st_mode
        dirty.update(relative.encode())
        dirty.update(b"\0")
        if stat.S_ISREG(mode):
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(64 * 1024), b""):
                    dirty.update(chunk)
        elif stat.S_ISLNK(mode):
            dirty.update(os.readlink(path).encode())
        dirty.update(b"\0")
    return {
        "commit": _git(repo_root, "rev-parse", "HEAD").strip(),
        "tree": _git(repo_root, "rev-parse", "HEAD^{tree}").strip(),
        "dirty": bool(status),
        "diffSha256": dirty.hexdigest(),
    }


def build_pytest_receipt(
    *, repo_root: Path, run_id: str, session_id: str | None,
    args: tuple[str, ...], profile: str, stubs: tuple[str, ...],
    exit_code: int, counts: dict[str, int], selected_node_ids: list[str], source_start: dict[str, object] | None = None,
) -> dict[str, object]:
    source = source_identity(repo_root)
    return {
        "schemaVersion": 2,
        "kind": "pytestInvocation",
        "runId": run_id,
        "sessionId": session_id,
        **source,
        "sourceStart": source if source_start is None else source_start,
        "gate": os.environ.get("GA_VERIFICATION_GATE"),
        "eventCommit": os.environ.get("GITHUB_SHA"),
        "profile": profile,
        "stubsActive": list(stubs),
        "args": list(args),
        "exitCode": exit_code,
        "tests": counts,
        "selectedCount": len(selected_node_ids),
        "selectedNodeIds": selected_node_ids,
    }


def _evidence_path(root: Path, relative: str) -> Path:
    try:
        path = confined_path(root, relative)
    except RemoteContractError as exc:
        raise OSError(f"unsafe verification path: {relative}") from exc
    if path.exists() and not path.is_file():
        raise OSError(f"verification evidence is not a regular file: {relative}")
    return path


def _read_evidence(root: Path, relative: str) -> str:
    with os.fdopen(open_regular_file(_evidence_path(root, relative)), "r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _publish_receipt(root: Path, relative: str, receipt: dict[str, object]) -> None:
    _evidence_path(root, relative)
    try:
        atomic_write_json(root, relative, receipt)
    except RemoteContractError as exc:
        raise OSError(f"cannot publish verification receipt: {relative}") from exc


def write_pytest_receipt(
    *, repo_root: Path, output_root: Path, args: tuple[str, ...],
    profile: str, stubs: tuple[str, ...], exit_code: int,
    counts: dict[str, int], selected_node_ids: list[str],
    source_start: dict[str, object] | None = None,
) -> dict[str, object]:
    verification = output_root / ".verification"
    if verification.is_symlink():
        raise OSError("verification directory must not be a symlink")
    runs = verification / "pytest-runs"
    if runs.is_symlink() or (runs.exists() and not runs.is_dir()):
        raise OSError("pytest-runs directory must not be a symlink")
    runs.mkdir(parents=True, exist_ok=True)
    latest = _evidence_path(output_root, ".verification/receipt.json")
    if not latest.exists():
        prior_status = "absent"
    else:
        try:
            prior = json.loads(_read_evidence(output_root, ".verification/receipt.json"))
        except (json.JSONDecodeError, OSError):
            prior_status = "malformed"
        else:
            prior_status = (
                "compatible"
                if isinstance(prior, dict)
                and prior.get("schemaVersion") == 2
                and prior.get("kind") == "pytestInvocation"
                else "incompatible"
            )
    run_id = uuid.uuid4().hex
    receipt = build_pytest_receipt(
        repo_root=repo_root,
        run_id=run_id,
        session_id=os.environ.get("GA_VERIFICATION_SESSION_ID"),
        args=args,
        profile=profile,
        stubs=stubs,
        exit_code=exit_code,
        counts=counts,
        selected_node_ids=selected_node_ids,
        source_start=source_start,
    )
    receipt["priorReceiptStatus"] = prior_status
    _publish_receipt(output_root, f".verification/pytest-runs/{run_id}.json", receipt)
    _publish_receipt(output_root, ".verification/receipt.json", receipt)
    return receipt


def _passed(log: str) -> int | None:
    matches = re.findall(r"(?:Tests\s+)?(\d+) passed", log)
    return int(matches[-1]) if matches else None


def main() -> None:
    session_id = os.environ.get("GA_VERIFICATION_SESSION_ID")
    if not session_id:
        raise RuntimeError("GA_VERIFICATION_SESSION_ID is required")
    root = Path.cwd()
    _evidence_path(root, ".verification/receipt.json")
    source = source_identity(root)
    commit = source["commit"]
    gates: list[dict[str, object]] = []
    for line in _read_evidence(root, ".verification/gates.tsv").splitlines():
        gate_session, gate_commit, name, raw_exit, log_digest, command = line.split("\t", 5)
        if gate_session != session_id or gate_commit != commit:
            raise RuntimeError(f"gate {name} has stale source or session identity")
        if Path(name).name != name:
            raise RuntimeError(f"invalid gate name: {name}")
        exit_code = int(raw_exit)
        if exit_code != 0:
            raise RuntimeError(f"gate {name} did not pass")
        content = _read_evidence(root, f".verification/logs/{name}.log")
        if hashlib.sha256(content.encode()).hexdigest() != log_digest:
            raise RuntimeError(f"gate {name} log differs from recorded evidence")
        gate: dict[str, object] = {
            "name": name,
            "command": command,
            "exitCode": exit_code,
            "status": "passed",
            "logSha256": hashlib.sha256(content.encode()).hexdigest(),
        }
        if (count := _passed(content)) is not None:
            gate["reportedPassed"] = count
            gate["reportedPassedAuthoritative"] = False
        gates.append(gate)
    if not gates:
        raise RuntimeError("current verification session has no gates")
    expected = [
        "backend", "sidecar", "frontend-tests", "lint", "typecheck-app",
        "typecheck-node", "build", "backend-startup", "prod-audit",
    ]
    if [gate["name"] for gate in gates] != expected:
        raise RuntimeError("current verification session has an incomplete or reordered gate set")
    # Nested pytest processes inherit the gate label; only the exact gate command
    # may own its receipt. Duplicate executions of that command still refuse.
    command = shlex.split(str(gates[0]["command"]))
    candidates = []
    for path in (root / ".verification/pytest-runs").glob("*.json"):
        try:
            run = json.loads(_read_evidence(root, f".verification/pytest-runs/{path.name}"))
        except (json.JSONDecodeError, UnicodeError):
            continue
        if (isinstance(run, dict) and run.get("sessionId") == session_id
                and run.get("gate") == "backend" and run.get("args") == command[3:]):
            if run.get("runId") != path.stem:
                raise RuntimeError("backend receipt run identity differs from its path")
            candidates.append(run)
    if len(candidates) != 1:
        raise RuntimeError("current verification session must have exactly one backend receipt")
    run = candidates[0]
    if run.get("schemaVersion") != 2 or run.get("kind") != "pytestInvocation":
        raise RuntimeError("incompatible backend receipt")
    if any(run.get(key) != value for key, value in source.items()) or run.get("sourceStart") != source:
        raise RuntimeError("backend receipt source identity changed before, during or after testing")
    if run.get("profile") != os.environ.get("GA_VERIFICATION_PROFILE", "code-only"):
        raise RuntimeError("backend receipt profile cannot be relabelled")
    counts = run.get("tests")
    if (type(run.get("exitCode")) is not int or run["exitCode"] != 0
            or not isinstance(counts, dict)
            or any(type(value) is not int or value < 0 for value in counts.values())
            or counts.get("failed", 0) or counts.get("error", 0)):
        raise RuntimeError("backend receipt did not pass")
    nodes = run.get("selectedNodeIds")
    if (command[:3] != ["python3", "-m", "pytest"] or run.get("args") != command[3:]
            or not isinstance(nodes, list) or not nodes
            or any(not isinstance(node, str) or not node.startswith("backend/tests/")
                   or ".." in Path(node.split("::", 1)[0]).parts for node in nodes)
            or type(run.get("selectedCount")) is not int or run["selectedCount"] != len(nodes)
            or len(set(nodes)) != len(nodes)):
        raise RuntimeError("backend receipt selection differs from its gate")
    excluded = [arg.partition("=")[2] for arg in command if arg.startswith("--ignore=")]
    if any(node.split("::", 1)[0] == path for node in nodes for path in excluded):
        raise RuntimeError("backend receipt selection includes an excluded test")
    stubs = run.get("stubsActive")
    if not isinstance(stubs, list) or any(not isinstance(stub, str) for stub in stubs):
        raise RuntimeError("backend receipt lacks valid stub disclosure")
    run_path = f".verification/pytest-runs/{run['runId']}.json"
    gates[0].update({
        "pytestRunId": run["runId"], "pytestReceiptPath": run_path,
        "pytestReceiptSha256": hashlib.sha256(_read_evidence(root, run_path).encode()).hexdigest(),
        "tests": counts, "selectedCount": run["selectedCount"], "stubsActive": stubs,
    })
    receipt = {
        "schemaVersion": 2,
        "kind": "verificationSession",
        "sessionId": session_id,
        **source,
        "eventCommit": run.get("eventCommit"),
        "profile": run["profile"],
        "stubsActive": stubs,
        "totalPassed": None,
        "countSemantics": "Per-gate reported outcomes may overlap and are non-authoritative display data.",
        "status": "passed",
        "gates": gates,
    }
    _publish_receipt(root, ".verification/receipt.json", receipt)


if __name__ == "__main__":
    main()
