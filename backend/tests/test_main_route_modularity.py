from pathlib import Path


MAIN = Path(__file__).resolve().parents[1] / "app/main.py"


def test_main_delegates_review_and_insight_route_families() -> None:
    source = MAIN.read_text(encoding="utf-8")

    assert "create_review_router(storage, require_match)" in source
    assert "create_insight_router(storage, require_match)" in source
    assert '@app.get("/api/bundles")' not in source
    assert '@app.get("/api/aggregate/dashboard")' not in source
    assert '@app.get("/api/search/matches")' not in source
