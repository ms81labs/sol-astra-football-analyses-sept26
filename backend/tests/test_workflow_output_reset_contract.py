from __future__ import annotations

import ast
from pathlib import Path


SCRIPTS_ROOT = Path(__file__).resolve().parents[1] / "scripts"


def _script_trees() -> list[tuple[Path, ast.AST]]:
    return [
        (path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
        for path in sorted(SCRIPTS_ROOT.glob("*.py"))
    ]


def test_workflow_outputs_use_shared_two_argument_reset_boundary() -> None:
    inline_resets: list[str] = []
    invalid_shared_calls: list[str] = []
    for path, tree in _script_trees():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "shutil"
                and node.func.attr == "rmtree"
                and node.args
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "output_root"
            ):
                inline_resets.append(f"{path.name}:{node.lineno}")
            if isinstance(node.func, ast.Name) and node.func.id == "reset_output":
                if len(node.args) != 2 or node.keywords:
                    invalid_shared_calls.append(f"{path.name}:{node.lineno}")

    assert inline_resets == []
    assert invalid_shared_calls == []
