from __future__ import annotations

import ast
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def test_scripts_do_not_bootstrap_sys_path_or_redefine_utc_helper() -> None:
    violations: list[str] = []
    for path in sorted(SCRIPTS.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                owner = node.func.value
                if (
                    isinstance(owner, ast.Attribute)
                    and isinstance(owner.value, ast.Name)
                    and owner.value.id == "sys"
                    and owner.attr == "path"
                    and node.func.attr in {"insert", "append"}
                ):
                    violations.append(f"{path.name}:{node.lineno}: sys.path.{node.func.attr}")
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "_utc_now_iso":
                violations.append(f"{path.name}:{node.lineno}: local _utc_now_iso")
    assert violations == [], "\n".join(violations)
