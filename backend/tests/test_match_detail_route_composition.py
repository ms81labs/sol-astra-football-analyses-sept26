from pathlib import Path

from backend.app.match_detail_routes import create_match_detail_router


ROOT = Path(__file__).resolve().parents[2]


def test_match_detail_routes_are_composed_outside_main() -> None:
    source = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    assert '@app.get("/api/matches/{match_id}/heatmap")' not in source
    assert '@app.get("/api/matches/{match_id}/benchmark")' not in source
    assert "create_match_detail_router(storage, require_match, snapshot_response, provider_gateway)" in source
    assert callable(create_match_detail_router)
