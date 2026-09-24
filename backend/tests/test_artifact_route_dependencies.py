"""Pin the eight artifact dependencies before modernizing their annotations."""

import inspect
import json
from types import SimpleNamespace
from pathlib import Path
from typing import Annotated, get_args, get_origin, get_type_hints

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from backend.app.artifact_routes import create_artifact_router
from backend.app.schemas import MatchRecord

ENDPOINTS = [
    ("get_events", "events"),
    ("export_frames_csv", "export/frames.csv"),
    ("export_events_csv", "export/events.csv"),
    ("export_metrics_csv", "export/metrics.csv"),
    ("export_match_json", "export/match.json"),
    ("get_generation_reports", "reports"),
    ("get_legacy_report", "reports/legacy/tactical_report"),
    ("get_match_report_html", "report/html"),
]


def _application(label, *, deny=True):
    calls = []
    storage = SimpleNamespace(label=label)

    def require_match(match_id: str) -> MatchRecord:
        calls.append(match_id)
        if deny:
            raise HTTPException(status_code=403, detail=label)
        return MatchRecord.model_construct(id=match_id)

    def bundle_builder(passed_storage, match_id, *, generation_id=None):
        assert passed_storage is storage
        return {"store": label, "match": match_id, "generation": generation_id}

    router = create_artifact_router(storage, require_match, bundle_builder)
    app = FastAPI()
    app.include_router(router)
    return app, router, require_match, calls


@pytest.mark.parametrize("name,_suffix", ENDPOINTS)
def test_artifact_dependencies_are_resolved_annotated_metadata(name, _suffix):
    _app, router, require_match, _calls = _application("first")
    endpoint = next(route.endpoint for route in router.routes if route.name == name)
    annotation = get_type_hints(endpoint, include_extras=True)["match"]
    assert get_origin(annotation) is Annotated
    match_type, dependency = get_args(annotation)
    assert match_type is MatchRecord and dependency.dependency is require_match
    assert (
        inspect.signature(endpoint).parameters["match"].default
        is inspect.Parameter.empty
    )


def test_artifact_openapi_contract_is_unchanged():
    app, _router, _require_match, _calls = _application("first")
    # Route-owned paths from the original router, not FastAPI-version-specific
    # validation-error components. Pinned full schemas are also compared before
    # and after this migration by the source-bound validation run.
    fixture = Path(__file__).parent / "fixtures" / "artifact_route_openapi_paths.json"
    assert app.openapi()["paths"] == json.loads(fixture.read_text(encoding="utf-8"))


@pytest.mark.parametrize("_name,suffix", ENDPOINTS)
def test_artifact_authorization_and_overrides_are_app_local(_name, suffix):
    first, _r1, require_first, calls_first = _application("first")
    second, _r2, _require_second, calls_second = _application("second")
    url = "/api/matches/shared/" + suffix

    def deny_override():
        raise HTTPException(status_code=401, detail="first-override")

    with TestClient(first) as a, TestClient(second) as b:
        for client, label in [(a, "first"), (b, "second"), (a, "first")]:
            response = client.get(url)
            assert response.status_code == 403 and response.json() == {"detail": label}
        first.dependency_overrides[require_first] = deny_override
        overridden = a.get(url)
        unchanged = b.get(url)
        assert overridden.status_code == 401 and overridden.json() == {
            "detail": "first-override"
        }
        assert unchanged.status_code == 403 and unchanged.json() == {"detail": "second"}
    assert calls_first == ["shared", "shared"]
    assert calls_second == ["shared", "shared"]


@pytest.mark.parametrize("generation", [None, "generation-a", ""])
def test_artifact_bundle_keeps_store_and_optional_generation(generation):
    first, _r1, _d1, _c1 = _application("first", deny=False)
    second, _r2, _d2, _c2 = _application("second", deny=False)
    params = {} if generation is None else {"generationId": generation}
    with TestClient(first) as a, TestClient(second) as b:
        for client, label in [(a, "first"), (b, "second"), (a, "first")]:
            response = client.get(
                "/api/matches/shared/export/match.json", params=params
            )
            assert response.status_code == 200
            assert response.json() == {
                "store": label,
                "match": "shared",
                "generation": generation,
            }


@pytest.mark.parametrize(
    "_name,suffix,detail",
    [
        ("get_events", "events", "Events not ready"),
        ("export_frames_csv", "export/frames.csv", "Match artifacts not ready"),
        ("export_events_csv", "export/events.csv", "Match artifacts not ready"),
        ("export_metrics_csv", "export/metrics.csv", "Match artifacts not ready"),
        ("export_match_json", "export/match.json", "Match artifacts not ready"),
        ("get_generation_reports", "reports", "Reports not ready"),
        (
            "get_legacy_report",
            "reports/legacy/tactical_report",
            "Legacy report unavailable",
        ),
        ("get_match_report_html", "report/html", "Analytics not ready"),
    ],
)
def test_missing_artifacts_keep_the_existing_http_error(
    tmp_path, _name, suffix, detail
):
    from backend.app.match_bundle import build_match_bundle
    from backend.app.storage import Storage

    from backend.app.schemas import MatchConfig

    storage = Storage(tmp_path / "empty-store")
    source = Path(__file__).parent / "fixtures" / "sample_tracking.json"
    match = storage.create_match(
        "Not processed", "tracking_json", source.name, source, MatchConfig()
    )

    def require_match(match_id: str) -> MatchRecord:
        assert match_id == match.id
        return match

    app = FastAPI()
    app.include_router(
        create_artifact_router(storage, require_match, build_match_bundle)
    )
    try:
        with TestClient(app) as client:
            response = client.get("/api/matches/" + match.id + "/" + suffix)
        assert response.status_code == 404
        assert response.json() == {"detail": detail}
    finally:
        storage.close()
