"""Pin upload HTTP and direct-call compatibility before retiring its B008."""
from contextlib import contextmanager
import inspect
from io import BytesIO
from pathlib import Path

import anyio
from fastapi import FastAPI, Request, UploadFile
from fastapi.params import File, Form, Header
from fastapi.testclient import TestClient
import pytest

from backend.app.jobs import JobRunner
from backend.app.match_ingest_routes import create_match_ingest_router
from backend.app.settings import ProcessingSettings
from backend.app.storage import Storage


def _endpoint(app):
    return next(route.endpoint for route in app.routes if route.path == "/api/matches")


@contextmanager
def _application(root: Path):
    settings = ProcessingSettings()
    storage = Storage(root)
    runner = JobRunner(root, settings=settings)
    app = FastAPI()
    app.include_router(create_match_ingest_router(storage, runner, settings))
    try:
        with TestClient(app) as client:
            yield app, client, storage
    finally:
        runner.ledger.close()
        storage.close()


@pytest.fixture
def ingest_app(tmp_path, monkeypatch):
    # Dispatch is an external process boundary; admission and upload I/O stay real.
    monkeypatch.setattr(JobRunner, "start", lambda self, job_id: None)
    with _application(tmp_path / "ingest") as parts:
        yield parts


def test_upload_signature_retains_positional_order_and_marker_defaults(ingest_app):
    app, _, _ = ingest_app
    parameters = inspect.signature(_endpoint(app)).parameters
    assert list(parameters) == [
        "request", "name", "inputMode", "config", "budget", "file", "idempotency_key"
    ]
    assert all(p.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD for p in parameters.values())
    for name in ("name", "inputMode"):
        assert isinstance(parameters[name].default, Form)
        assert parameters[name].default.is_required()
    assert parameters["config"].default.default == "{}"
    assert parameters["budget"].default.default == 0.0
    assert isinstance(parameters["file"].default, File)
    assert parameters["file"].default.is_required()
    assert isinstance(parameters["idempotency_key"].default, Header)
    assert parameters["idempotency_key"].default.default is None
    assert parameters["idempotency_key"].default.alias == "Idempotency-Key"


def test_required_upload_marker_is_owned_by_each_router(tmp_path):
    settings = ProcessingSettings()
    # Router construction does not touch these collaborators; fail loudly if it starts to.
    first = create_match_ingest_router(None, None, settings)
    second = create_match_ingest_router(None, None, settings)
    one = inspect.signature(first.routes[0].endpoint).parameters["file"].default
    two = inspect.signature(second.routes[0].endpoint).parameters["file"].default
    assert isinstance(one, File) and isinstance(two, File)
    assert one is not two
    assert one.is_required() and two.is_required()
    one.description = "first-router-only"
    assert two.description is None


def test_upload_openapi_preserves_required_multipart_fields(ingest_app):
    app, _, _ = ingest_app
    document = app.openapi()
    operation = document["paths"]["/api/matches"]["post"]
    assert operation["operationId"] == "create_match_api_matches_post"
    assert operation["requestBody"]["required"] is True
    content = operation["requestBody"]["content"]
    assert set(content) == {"multipart/form-data"}
    ref = content["multipart/form-data"]["schema"]["$ref"].split("/")[-1]
    body = document["components"]["schemas"][ref]
    assert body["required"] == ["name", "inputMode", "file"]
    assert body["properties"]["file"] == {"type": "string", "format": "binary", "title": "File"}
    assert body["properties"]["config"]["default"] == "{}"
    assert body["properties"]["budget"]["default"] == 0.0
    assert operation["parameters"][0]["name"] == "Idempotency-Key"
    assert operation["parameters"][0]["required"] is False
    assert set(operation["responses"]) == {"202", "422"}


@pytest.mark.parametrize("kind", ["absent", "wrong-key", "form-string", "json"])
def test_missing_or_non_file_upload_never_admits_a_job(ingest_app, kind):
    _, client, storage = ingest_app
    data = {"name": "Upload", "inputMode": "tracking_json"}
    if kind == "wrong-key":
        result = client.post("/api/matches", data=data, files={"not_file": ("x.json", b"[]")})
    elif kind == "form-string":
        result = client.post("/api/matches", data={**data, "file": "not-an-upload"})
    elif kind == "json":
        result = client.post("/api/matches", json={**data, "file": "[]"})
    else:
        result = client.post("/api/matches", data=data)
    assert result.status_code == 422
    assert any(error["loc"] == ["body", "file"] for error in result.json()["detail"])
    with storage._connect() as connection:
        assert connection.execute("SELECT count(*) FROM matches").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM jobs").fetchone()[0] == 0
    assert not list((storage.storage_root / "uploads").glob("*"))


@pytest.mark.parametrize("payload", [b"[]", b"", b'{"frames": []}'])
def test_http_upload_keeps_bytes_defaults_and_idempotent_replay(ingest_app, payload):
    _, client, storage = ingest_app
    request = {
        "data": {"name": "Upload", "inputMode": "tracking_json"},
        "files": {"file": ("source.json", payload, "application/json")},
        "headers": {"Idempotency-Key": "required-upload:test"},
    }
    result = client.post("/api/matches", **request)
    assert result.status_code == 202, result.text
    view = result.json()
    assert view["dispatchOutcome"] == "started" and view["reused"] is False
    assert storage.get_match_input_path(view["matchId"]).read_bytes() == payload
    assert storage.get_match(view["matchId"]).name == "Upload"
    replay = client.post("/api/matches", **request)
    assert replay.status_code == 202
    assert replay.json()["matchId"] == view["matchId"]
    assert replay.json()["jobId"] == view["jobId"]
    assert replay.json()["reused"] is True
    assert len(list((storage.storage_root / "uploads").glob("*"))) == 1


@pytest.mark.parametrize("positional", [True, False])
def test_direct_upload_call_keeps_argument_binding(ingest_app, positional):
    app, _, storage = ingest_app
    handler = _endpoint(app)
    upload = UploadFile(filename="direct.json", file=BytesIO(b"[]"))
    request = Request({"type": "http", "method": "POST", "path": "/api/matches", "headers": []})

    async def invoke():
        try:
            if positional:
                return await handler(request, "Direct", "tracking_json", "{}", 0.0, upload, None)
            return await handler(request=request, name="Direct", inputMode="tracking_json", config="{}", budget=0.0, file=upload, idempotency_key=None)
        finally:
            await upload.close()

    result = anyio.run(invoke)
    assert result["dispatchOutcome"] == "started"
    assert storage.get_match_input_path(result["matchId"]).read_bytes() == b"[]"
