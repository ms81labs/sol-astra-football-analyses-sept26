import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
STORAGE = APP / "storage.py"
CALIBRATION = APP / "storage_calibration.py"
METHODS = {
    "preview_landmark_for_match",
    "commit_calibration_for_match",
    "calibration_for_match",
    "_load_calibration_evaluation",
    "_save_calibration_evaluation",
    "_restore_calibration_evaluation",
    "calibration_revision",
    "_legacy_calibration_revision",
    "_save_calibration_revision",
    "_new_calibration_revision",
    "_restore_calibration_revision",
}


def _class_methods(path: Path, class_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    return {node.name for node in cls.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def test_calibration_persistence_is_behind_storage_facade() -> None:
    assert CALIBRATION.exists()
    storage_tree = ast.parse(STORAGE.read_text(encoding="utf-8"))
    storage_class = next(node for node in storage_tree.body if isinstance(node, ast.ClassDef) and node.name == "Storage")
    assert any(isinstance(base, ast.Name) and base.id == "_CalibrationStorageMixin" for base in storage_class.bases)
    assert METHODS.isdisjoint(_class_methods(STORAGE, "Storage"))
    assert METHODS <= _class_methods(CALIBRATION, "_CalibrationStorageMixin")
