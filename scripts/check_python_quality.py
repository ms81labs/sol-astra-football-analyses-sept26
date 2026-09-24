"""Check exact legacy diagnostics; never rewrite the baseline during CI."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import sys
import tomllib

COMMANDS = {
    "ruff": ["ruff", "check", "backend", "scripts/check_python_quality.py", "--select", "F,B,BLE,S110,B904,C901", "--output-format=json"],
    "mypy": [sys.executable, "-m", "mypy", "--config-file", "pyproject.toml", "--output=json", "--no-incremental"],
}


def compare_baseline(expected: list[str], actual: list[str]) -> tuple[list[str], list[str]]:
    old, new = Counter(expected), Counter(actual)
    return sorted((new - old).elements()), sorted((old - new).elements())


def _scope(node: ast.AST, line: int, parents: tuple[str, ...] = ()) -> str:
    if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        parents += (node.name,)
    for child in ast.iter_child_nodes(node):
        if getattr(child, "lineno", 0) <= line <= getattr(child, "end_lineno", -1):
            return _scope(child, line, parents)
    return ".".join(parents) or "<module>"


def normalise_diagnostics(tool: str, output: str, root: Path) -> list[str]:
    rows = json.loads(output) if tool == "ruff" else [json.loads(line) for line in output.splitlines() if line.strip()]
    if not isinstance(rows, list):
        raise ValueError("diagnostics must be a list")
    sources: dict[Path, tuple[list[str], ast.AST]] = {}
    result = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("diagnostic must be an object")
        if tool == "mypy":
            if row.get("severity") == "note":
                continue
            if row.get("severity") != "error":
                raise ValueError("unrecognised mypy severity")
        raw_path = row["filename"] if tool == "ruff" else row["file"]
        path = (root / raw_path).resolve()
        relative = path.relative_to(root.resolve()).as_posix()
        line = row["location"]["row"] if tool == "ruff" else row["line"]
        code, message = row["code"], row["message"]
        if type(line) is not int or line < 1 or not isinstance(code, str) or not code or not isinstance(message, str):
            raise ValueError("invalid diagnostic identity")
        if path not in sources:
            text = path.read_text(encoding="utf-8")
            sources[path] = text.splitlines(), ast.parse(text)
        lines, tree = sources[path]
        if line > len(lines):
            raise ValueError("diagnostic line is outside source")
        result.append(json.dumps([relative, _scope(tree, line), code, lines[line - 1].strip(), message], ensure_ascii=False))
    return sorted(result)


def run_tool(tool: str, root: Path) -> list[str]:
    result = subprocess.run(COMMANDS[tool], cwd=root, capture_output=True, text=True, timeout=300, check=False)
    if result.returncode not in (0, 1) or result.stderr.strip():
        raise RuntimeError(f"{tool} failed ({result.returncode}): {result.stderr.strip()}")
    diagnostics = normalise_diagnostics(tool, result.stdout, root)
    if bool(result.returncode) != bool(diagnostics):
        raise RuntimeError(f"{tool} exit status disagrees with diagnostics")
    return diagnostics


def _metadata(tool: str, root: Path) -> dict:
    config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["tool"]
    relevant = {key: config[key] for key in (["ruff"] if tool == "ruff" else ["mypy", "pydantic-mypy"])}
    return {
        "schema": 1,
        "tool": tool,
        "version": version(tool),
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "pydantic": version("pydantic") if tool == "mypy" else None,
        "arguments": COMMANDS[tool][1:] if tool == "ruff" else COMMANDS[tool][3:],
        "configSha256": hashlib.sha256(json.dumps(relevant, sort_keys=True).encode()).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tool", choices=COMMANDS)
    parser.add_argument("--write-baseline", action="store_true", help="Explicit maintainer-only refresh; review the diff before committing")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        actual = run_tool(args.tool, root)
        metadata = _metadata(args.tool, root)
        path = root / "backend" / "quality" / f"{args.tool}-baseline.json"
        if args.write_baseline:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"metadata": metadata, "diagnostics": actual}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"Wrote {args.tool} baseline: {len(actual)} legacy diagnostics; review before committing")
            return 0
        expected = json.loads(path.read_text(encoding="utf-8"))
        if expected["metadata"] != metadata:
            raise ValueError("baseline tool/configuration metadata changed; review and regenerate explicitly")
        if not isinstance(expected["diagnostics"], list) or any(not isinstance(item, str) for item in expected["diagnostics"]):
            raise ValueError("invalid baseline diagnostics")
        added, removed = compare_baseline(expected["diagnostics"], actual)
        for label, entries in (("NEW", added), ("STALE", removed)):
            for entry in entries:
                print(f"{label}: {entry}")
        print(f"{args.tool}: {len(actual)} legacy diagnostics; {len(added)} new, {len(removed)} stale")
        return int(bool(added or removed))
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, SyntaxError, subprocess.SubprocessError) as exc:
        print(f"Quality gate failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
