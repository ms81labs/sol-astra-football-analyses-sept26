from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LEFTOVER_ROUTERS = tuple((REPO_ROOT / "backend/app/workbench").glob("leftover*routes.py"))


def test_leftover_routers_do_not_import_main_namespace() -> None:
    assert len(LEFTOVER_ROUTERS) >= 7
    for path in LEFTOVER_ROUTERS:
        source = path.read_text(encoding="utf-8")
        assert "backend.app.main" not in source
        assert "_main." not in source
