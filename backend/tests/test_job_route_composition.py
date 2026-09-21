from pathlib import Path

from backend.app.job_routes import create_job_router


ROOT = Path(__file__).resolve().parents[2]


def test_job_lifecycle_routes_are_composed_outside_main() -> None:
    source = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    assert '@app.get("/api/jobs/{job_id}")' not in source
    assert '@app.post("/api/jobs/{job_id}/cancel")' not in source
    assert "create_job_router(storage, runner, require_match)" in source
    assert callable(create_job_router)
