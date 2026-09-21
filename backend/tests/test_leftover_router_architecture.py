from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LEFTOVER_ROUTERS = (
    REPO_ROOT / "backend/app/workbench/leftover_routes.py",
    REPO_ROOT / "backend/app/workbench/leftover_get_routes.py",
)


def test_leftover_routers_do_not_import_main_namespace() -> None:
    for path in LEFTOVER_ROUTERS:
        source = path.read_text(encoding="utf-8")
        assert "backend.app.main" not in source
        assert "_main." not in source
