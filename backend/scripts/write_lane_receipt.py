"""Summarize all code-only verification gates in one source-bound receipt."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import uuid


def _git(repo_root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def build_pytest_receipt(
    *, repo_root: Path, run_id: str, session_id: str | None,
    args: tuple[str, ...], profile: str, stubs: tuple[str, ...],
    exit_code: int, counts: dict[str, int], selected_node_ids: list[str],
) -> dict[str, object]:
    status = _git(repo_root, "status", "--porcelain=v1", "--untracked-files=all")
    diff = _git(repo_root, "diff", "--binary", "HEAD")
    return {
        "schemaVersion": 2,
        "kind": "pytestInvocation",
        "runId": run_id,
        "sessionId": session_id,
        "commit": _git(repo_root, "rev-parse", "HEAD").strip(),
        "tree": _git(repo_root, "rev-parse", "HEAD^{tree}").strip(),
        "eventCommit": os.environ.get("GITHUB_SHA"),
        "dirty": bool(status),
        "diffSha256": hashlib.sha256((status + "\0" + diff).encode()).hexdigest(),
        "profile": profile,
        "stubsActive": list(stubs),
        "args": list(args),
        "exitCode": exit_code,
        "tests": counts,
        "selectedCount": len(selected_node_ids),
        "selectedNodeIds": selected_node_ids,
    }


def write_pytest_receipt(
    *, repo_root: Path, output_root: Path, args: tuple[str, ...],
    profile: str, stubs: tuple[str, ...], exit_code: int,
    counts: dict[str, int], selected_node_ids: list[str],
) -> dict[str, object]:
    verification = output_root / ".verification"
    if verification.is_symlink():
        raise OSError("verification directory must not be a symlink")
    runs = verification / "pytest-runs"
    runs.mkdir(parents=True, exist_ok=True)
    latest = verification / "receipt.json"
    if not latest.exists():
        prior_status = "absent"
    else:
        try:
            prior = json.loads(latest.read_text(encoding="utf-8"))
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
    )
    receipt["priorReceiptStatus"] = prior_status
    encoded = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    (runs / f"{run_id}.json").write_text(encoded, encoding="utf-8")
    latest.write_text(encoded, encoding="utf-8")
    return receipt


def _passed(log: str) -> int | None:
    matches = re.findall(r"(?:Tests\s+)?(\d+) passed", log)
    return int(matches[-1]) if matches else None


def main() -> None:
    receipt_path = Path(".verification/receipt.json")
    session_id = os.environ.get("GA_VERIFICATION_SESSION_ID")
    if not session_id:
        raise RuntimeError("GA_VERIFICATION_SESSION_ID is required")
    gates: list[dict[str, object]] = []
    for line in Path(".verification/gates.tsv").read_text(encoding="utf-8").splitlines():
        name, raw_exit, command = line.split("\t", 2)
        if Path(name).name != name:
            raise RuntimeError(f"invalid gate name: {name}")
        exit_code = int(raw_exit)
        if exit_code != 0:
            raise RuntimeError(f"gate {name} did not pass")
        path = Path(".verification/logs") / f"{name}.log"
        content = path.read_text(encoding="utf-8")
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
    root = Path.cwd()
    commit = _git(root, "rev-parse", "HEAD").strip()
    tree = _git(root, "rev-parse", "HEAD^{tree}").strip()
    stubs: list[str] = []
    for path in sorted(Path(".verification/pytest-runs").glob("*.json"), reverse=True):
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if run.get("sessionId") == session_id and run.get("commit") == commit:
            stubs = list(run.get("stubsActive", []))
            break
    receipt = {
        "schemaVersion": 2,
        "kind": "verificationSession",
        "sessionId": session_id,
        "commit": commit,
        "tree": tree,
        "eventCommit": os.environ.get("GITHUB_SHA"),
        "profile": os.environ.get("GA_VERIFICATION_PROFILE", "code-only"),
        "stubsActive": stubs,
        "totalPassed": None,
        "countSemantics": "Per-gate reported outcomes may overlap and are non-authoritative display data.",
        "status": "passed",
        "gates": gates,
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
