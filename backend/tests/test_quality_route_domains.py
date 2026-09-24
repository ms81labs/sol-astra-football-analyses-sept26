"""Pin route order, authorization, and per-application dependencies during extraction."""
import ast
import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from backend.app.main import create_app
from backend.app.schemas import MatchConfig
from backend.app.settings import ProcessingSettings

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).with_name("fixtures") / "leftover-route-contract.json"


@pytest.mark.parametrize("enabled", ["0", "1"])
def test_ordered_route_contract_is_unchanged(tmp_path, monkeypatch, enabled):
    monkeypatch.setenv("GA_FLAG_LEFTOVER_HTTP", enabled)
    app = create_app(storage_root=tmp_path, settings=ProcessingSettings())
    try:
        routes = [(r.path, sorted(r.methods), r.name) for r in app.routes if getattr(r, "methods", None)]
        fingerprint = hashlib.sha256(json.dumps(routes, separators=(",", ":")).encode()).hexdigest()
        expected = json.loads(FIXTURE.read_text())[enabled]
        assert fingerprint == expected["routesSha256"]
        assert len(app.openapi()["paths"]) == expected["pathCount"]
    finally:
        app.state.storage.close()


def test_match_dependencies_keep_stores_and_authorization_isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("GA_FLAG_LEFTOVER_HTTP", "0")
    apps = [create_app(storage_root=tmp_path / name, settings=ProcessingSettings()) for name in ("first", "second")]
    first, second = apps
    try:
        match = first.state.storage.create_match("First only", "tracking_json", "input.json", tmp_path / "input.json", MatchConfig())
        route = f"/api/workbench/dev/matches/{match.id}/players"
        first_client = TestClient(first, base_url="http://127.0.0.1")
        second_client = TestClient(second, base_url="http://127.0.0.1")
        first_response = first_client.post(route, json={})
        second_response = second_client.post(route, json={})
        assert first_response.status_code == second_response.status_code == 404
        assert first_response.json() == {"detail": "Frames not ready"}
        assert second_response.json() == {"detail": "Match not found"}
        denied = first_client.post(route, json={}, headers={"x-deployment-boundary": "hosted"})
        assert denied.status_code == 403 and not denied.json()["detail"]["allowed"]
        assert second.state.storage.list_matches() == []
    finally:
        for app in apps:
            app.state.storage.close()


def test_root_factories_only_assemble_route_domains():
    for name, factory in (("leftover_routes.py", "create_leftover_post_router"), ("leftover_get_routes.py", "create_leftover_get_routers")):
        tree = ast.parse((ROOT / "backend/app/workbench" / name).read_text())
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == factory)
        assert not any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in node.body), factory
