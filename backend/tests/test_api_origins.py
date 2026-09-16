from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.app.main import create_app
from backend.app.settings import ProcessingSettings


@pytest.fixture
def local_api(tmp_path, monkeypatch):
    app = create_app(storage_root=tmp_path, settings=ProcessingSettings())
    storage = app.state.storage
    spies = [Mock(wraps=storage.save_upload_stream), Mock(wraps=storage.admit_match_job), Mock()]
    monkeypatch.setattr(storage, "save_upload_stream", spies[0])
    monkeypatch.setattr(storage, "admit_match_job", spies[1])
    # Dispatch is the external/process boundary; storage remains real and temporary.
    monkeypatch.setattr("backend.app.main.JobRunner.start", spies[2])
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        yield storage, client, spies


def upload(client, headers):
    return client.post(
        "/api/matches",
        headers=headers,
        data={"name": "Origin test", "inputMode": "tracking_json", "config": "{}"},
        files={"file": ("tracking.json", b"{}", "application/json")},
    )


@pytest.mark.parametrize("origin", [
    "https://attacker.example", "null", "*", "", "http://localhost:5173/",
    "http://localhost:5173?x", "http://localhost:5173#x",
    "http://user@localhost:5173", "http://localhost:5173, https://attacker.example",
    "http://local\thost:5173", "http://127.0.0.1:8001", "https://127.0.0.1:8000",
])
def test_foreign_origin_upload_rejected_before_storage(local_api, origin):
    storage, client, spies = local_api
    response = upload(client, {"Origin": origin})
    assert response.status_code == 403
    for spy in spies:
        spy.assert_not_called()
    assert storage.list_matches() == []
    upload_dir = storage.storage_root / "uploads"
    assert not upload_dir.exists() or list(upload_dir.iterdir()) == []
    with storage._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0


def test_foreign_origin_mutation_rejected_without_preflight(local_api):
    storage, client, spies = local_api
    response = client.post("/api/bundles", json={"name": "Untrusted"}, headers={"Origin": "https://attacker.example"})
    assert response.status_code == 403
    assert storage.list_review_bundles() == []
    for spy in spies:
        spy.assert_not_called()


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_foreign_origin_rejected_before_route_validation(local_api, method):
    _, client, _ = local_api
    response = client.request(method, "/api/bundles/missing", content=b"bad body", headers={"Origin": "https://attacker.example", "Content-Type": "text/plain"})
    assert response.status_code == 403


def test_duplicate_origins_rejected(local_api):
    _, client, spies = local_api
    headers = httpx.Headers([("Origin", "http://localhost:5173"), ("Origin", "https://attacker.example")])
    assert upload(client, headers).status_code == 403
    for spy in spies:
        spy.assert_not_called()
    with pytest.raises(WebSocketDisconnect) as caught:
        with client.websocket_connect("ws://127.0.0.1:8000/ws/jobs/missing", headers=headers):
            pytest.fail("Duplicate Origin headers were accepted")
    assert caught.value.code == 1008


@pytest.mark.parametrize("origin", [None, "http://127.0.0.1:8000", "http://localhost:5173", "http://127.0.0.1:5173", "http://[::1]:5173"])
def test_allowed_local_origin_remains_usable(local_api, origin):
    storage, client, spies = local_api
    response = upload(client, {} if origin is None else {"Origin": origin})
    assert response.status_code == 202
    assert storage.get_match(response.json()["matchId"]).name == "Origin test"
    assert storage.get_job(response.json()["jobId"]).status == "queued"
    for spy in spies:
        assert spy.call_count == 1


@pytest.mark.parametrize("origin", ["https://attacker.example", "null", "*", "http://localhost:5173/"])
def test_websocket_rejects_foreign_origin(local_api, origin):
    _, client, _ = local_api
    with pytest.raises(WebSocketDisconnect) as caught:
        with client.websocket_connect("ws://127.0.0.1:8000/ws/jobs/missing", headers={"Origin": origin}):
            pytest.fail("Foreign origin websocket was accepted")
    assert caught.value.code == 1008


@pytest.mark.parametrize("origin", [None, "http://127.0.0.1:8000", "http://localhost:5173"])
def test_websocket_allows_trusted_and_originless_clients(local_api, origin):
    _, client, _ = local_api
    with client.websocket_connect("ws://127.0.0.1:8000/ws/jobs/missing", headers={} if origin is None else {"Origin": origin}) as websocket:
        assert websocket.receive_json() == {"error": "Job not found"}


def test_trusted_websocket_preserves_job_progress_payload(local_api):
    storage, client, _ = local_api
    job_id = upload(client, {}).json()["jobId"]
    storage.update_job(job_id, status="completed", progress=100, message="Done")
    with client.websocket_connect(f"ws://127.0.0.1:8000/ws/jobs/{job_id}", headers={"Origin": "http://localhost:5173"}) as websocket:
        payload = websocket.receive_json()
        assert payload["id"] == job_id
        assert payload["status"] == "completed"
        assert payload["progress"] == 100
        assert payload["message"] == "Done"


def test_websocket_untrusted_host_is_denied(local_api):
    _, client, _ = local_api
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("ws://attacker.example/ws/jobs/missing", headers={"Origin": "http://localhost:5173"}):
            pytest.fail("Untrusted Host websocket was accepted")


@pytest.mark.parametrize("host", ["attacker.example", "testserver", "192.168.1.2", "localhost.attacker.example", "[::1]:8000"])
def test_untrusted_host_rejected_before_storage(local_api, host):
    _, client, spies = local_api
    response = upload(client, {"Host": host, "Origin": "http://localhost:5173"})
    assert response.status_code == 400
    for spy in spies:
        spy.assert_not_called()


def test_cors_is_explicit_and_rejects_unused_methods_and_headers(local_api):
    _, client, _ = local_api
    headers = {"Origin": "http://localhost:5173", "Access-Control-Request-Method": "PATCH", "Access-Control-Request-Headers": "Content-Type"}
    response = client.options("/api/matches/missing/config", headers=headers)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert set(response.headers["access-control-allow-methods"].split(", ")) == {"GET", "POST", "PUT", "PATCH", "DELETE"}
    assert "*" not in response.headers["access-control-allow-headers"]
    for changes in [{"Origin": "https://attacker.example"}, {"Access-Control-Request-Method": "TRACE"}, {"Access-Control-Request-Headers": "X-Unused"}]:
        assert client.options("/api/matches", headers=headers | changes).status_code == 400


@pytest.mark.parametrize("base_url, origin, status", [
    ("http://localhost", "http://localhost:80", 201),
    ("https://localhost", "https://localhost:443", 201),
    ("https://localhost", "http://localhost", 403),
    ("http://localhost:8000", "http://localhost", 403),
])
def test_same_origin_uses_scheme_and_effective_port(local_api, base_url, origin, status):
    _, client, _ = local_api
    client.base_url = base_url
    assert client.post("/api/bundles", json={"name": "Same origin"}, headers={"Origin": origin}).status_code == status


def test_configured_frontend_origin_replaces_defaults(tmp_path):
    app = create_app(storage_root=tmp_path, settings=ProcessingSettings(trusted_frontend_origins=("https://localhost:4443",)))
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        response = client.post("/api/bundles", json={"name": "Configured"}, headers={"Origin": "https://localhost:4443"})
        assert response.status_code == 201
        assert response.headers["access-control-allow-origin"] == "https://localhost:4443"
        assert client.post("/api/bundles", json={"name": "Old default"}, headers={"Origin": "http://localhost:5173"}).status_code == 403
