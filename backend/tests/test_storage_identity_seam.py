import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
STORAGE = APP / "storage.py"
IDENTITY = APP / "storage_identity.py"
METHODS = {
    "identity_eligibility",
    "_stored_identity_continuous",
    "_stored_calibration_accepted",
    "repair_identity_for_match",
    "promote_identity_for_match",
    "_recompute_identity_continuity",
    "_apply_identity_edit",
    "_invalidate_stored_identity_continuity",
}


def _class_methods(path: Path, class_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    return {node.name for node in cls.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def test_identity_state_is_behind_storage_facade() -> None:
    assert IDENTITY.exists()
    storage_tree = ast.parse(STORAGE.read_text(encoding="utf-8"))
    storage_class = next(node for node in storage_tree.body if isinstance(node, ast.ClassDef) and node.name == "Storage")
    assert any(isinstance(base, ast.Name) and base.id == "_IdentityStorageMixin" for base in storage_class.bases)
    assert METHODS.isdisjoint(_class_methods(STORAGE, "Storage"))
    assert METHODS <= _class_methods(IDENTITY, "_IdentityStorageMixin")
