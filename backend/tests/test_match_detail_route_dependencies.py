"""Characterize match-detail dependency binding without changing handler logic."""

import inspect
import json
from pathlib import Path
from typing import Annotated, get_args, get_origin, get_type_hints

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from backend.app.match_detail_routes import create_match_detail_router
from backend.app.provider_gateway import ProviderDenied
from backend.app.schemas import MatchRecord

ENDPOINTS = [
    ("post_match_query", "POST", "/api/matches/{match_id}/queries"),
    ("post_match_report", "POST", "/api/matches/{match_id}/reports"),
    ("get_match_heatmap", "GET", "/api/matches/{match_id}/heatmap"),
    ("get_match_players", "GET", "/api/matches/{match_id}/players"),
    ("get_match_ownership", "GET", "/api/matches/{match_id}/ownership"),
    ("get_match_package", "GET", "/api/matches/{match_id}/package"),
    (
        "get_match_incident_geometry",
        "GET",
        "/api/matches/{match_id}/incidents/geometry",
    ),
    ("match_setup", "GET", "/api/matches/{match_id}/setup"),
    ("match_rates", "GET", "/api/matches/{match_id}/rates"),
    ("get_match_metrics", "GET", "/api/matches/{match_id}/metrics"),
    (
        "inspect_stored_metric",
        "GET",
        "/api/matches/{match_id}/metrics/inspect/{metric}",
    ),
    ("get_match_incident_package", "GET", "/api/matches/{match_id}/incidents/package"),
    ("get_match_clock", "GET", "/api/matches/{match_id}/clock"),
    ("get_match_incident_review", "GET", "/api/matches/{match_id}/incidents/review"),
    ("get_match_privacy", "GET", "/api/matches/{match_id}/privacy"),
    ("get_match_setup_preview", "GET", "/api/matches/{match_id}/setup/preview"),
    ("commit_match_calibration", "POST", "/api/matches/{match_id}/calibration/commit"),
    ("post_match_recompute", "POST", "/api/matches/{match_id}/recompute"),
    (
        "post_match_recompute_execute",
        "POST",
        "/api/matches/{match_id}/recompute/execute",
    ),
    ("get_match_promotion", "GET", "/api/matches/{match_id}/promotion"),
    ("get_match_quality", "GET", "/api/matches/{match_id}/quality"),
    ("get_match_identity", "GET", "/api/matches/{match_id}/identity"),
    ("post_match_identity_repair", "POST", "/api/matches/{match_id}/identity/repair"),
    ("post_match_identity_promote", "POST", "/api/matches/{match_id}/identity/promote"),
    ("get_match_history", "GET", "/api/matches/{match_id}/history"),
    ("get_match_cache", "GET", "/api/matches/{match_id}/cache"),
    ("get_match_legacy_migrate", "GET", "/api/matches/{match_id}/records/migrate"),
    ("get_match_attack_direction", "GET", "/api/matches/{match_id}/attack-direction"),
    ("post_match_attack_direction", "POST", "/api/matches/{match_id}/attack-direction"),
    ("get_match_calibration", "GET", "/api/matches/{match_id}/calibration"),
    ("post_match_calibration", "POST", "/api/matches/{match_id}/calibration"),
    ("get_match_formation", "GET", "/api/matches/{match_id}/formation"),
    ("get_match_event_partition", "GET", "/api/matches/{match_id}/events/partition"),
    (
        "get_match_report_provenance",
        "GET",
        "/api/matches/{match_id}/reports/provenance",
    ),
    ("get_match_report_coverage", "GET", "/api/matches/{match_id}/reports/coverage"),
    ("get_match_shot_quality", "GET", "/api/matches/{match_id}/shots/quality"),
    ("get_match_proxy", "GET", "/api/matches/{match_id}/media/proxy"),
    ("get_match_edits", "GET", "/api/matches/{match_id}/edits"),
    ("post_match_edit_render", "POST", "/api/matches/{match_id}/edits/render"),
    ("get_match_tracklets", "GET", "/api/matches/{match_id}/tracklets"),
    ("get_match_derived_distance", "GET", "/api/matches/{match_id}/geometry/distance"),
    ("get_match_shot_features", "GET", "/api/matches/{match_id}/shots/features"),
    ("post_match_corrupted_import", "POST", "/api/matches/{match_id}/recovery/import"),
    (
        "post_match_assistance_report",
        "POST",
        "/api/matches/{match_id}/assistance/report",
    ),
    ("analyze_match", "POST", "/api/matches/{match_id}/analysis/{analysis_type}"),
    ("get_match_benchmark", "GET", "/api/matches/{match_id}/benchmark"),
    ("update_match_config", "PATCH", "/api/matches/{match_id}/config"),
    ("download_match_clip", "GET", "/api/matches/{match_id}/edits/clip"),
    ("get_event_proposal_capability", "GET", "/api/matches/{match_id}/event-proposals"),
    ("post_event_proposal", "POST", "/api/matches/{match_id}/event-proposals"),
    ("get_query_proposal_capability", "GET", "/api/matches/{match_id}/query-proposals"),
    ("post_query_proposal", "POST", "/api/matches/{match_id}/query-proposals"),
    ("prepare_provider_images", "POST", "/api/matches/{match_id}/provider-images"),
]


class _RouteStore:
    """Test-only port with observable values returned over real HTTP routing."""

    def __init__(self, label):
        self.label = label

    def heatmap_for_match(self, match_id):
        return {"store": self.label, "match": match_id}

    def query_match_events(self, match_id, query):
        return {"store": self.label, "match": match_id, "query": query}

    def edit_list_for_match(self, match_id, *, generation_id=None):
        return {"store": self.label, "match": match_id, "generation": generation_id}

    def calibration_for_match(self, match_id, payload=None):
        return {"store": self.label, "match": match_id, "payload": payload}

    def repair_identity_for_match(self, match_id, payload=None):
        return {"store": self.label, "match": match_id, "payload": payload}

    def attack_direction_for_match(self, match_id, *, team, period):
        return {"store": self.label, "match": match_id, "team": team, "period": period}

    def render_edit_for_match(self, match_id, *, start, end, generation_id=None):
        return {
            "store": self.label,
            "match": match_id,
            "start": start,
            "end": end,
            "generation": generation_id,
        }

    def incident_geometry_for_match(self, match_id):
        return {"store": self.label, "match": match_id, "geometry": True}


class _Gateway:
    def __init__(self, label):
        self.label = label
        self.denied = False

    def execute(self, match_id, analysis_type, *, requested_provider=None, body=None):
        if self.denied:
            raise ProviderDenied(["test-budget-denial"])
        return {
            "gateway": self.label,
            "match": match_id,
            "analysis": analysis_type,
            "provider": requested_provider,
            "body": body,
        }


def _application(label, *, deny=True):
    calls = []
    store = _RouteStore(label)
    gateway = _Gateway(label)

    def require_match(match_id: str) -> MatchRecord:
        calls.append(match_id)
        if deny:
            raise HTTPException(status_code=403, detail=label)
        return MatchRecord.model_construct(id=match_id)

    def snapshot_response(match_id, builder, generation_id=None):
        return {"snapshotStore": label, "generation": generation_id, **builder()}

    router = create_match_detail_router(
        store, require_match, snapshot_response, gateway
    )
    app = FastAPI()
    app.include_router(router)
    return app, router, require_match, calls, gateway


@pytest.mark.parametrize("name,_method,_path", ENDPOINTS)
def test_match_detail_dependencies_resolve_factory_local_callback(name, _method, _path):
    _app, router, dependency, _calls, _gateway = _application("first")
    endpoint = next(route.endpoint for route in router.routes if route.name == name)
    annotation = get_type_hints(endpoint, include_extras=True)["match"]
    assert get_origin(annotation) is Annotated
    match_type, marker = get_args(annotation)
    assert match_type is MatchRecord
    assert marker.dependency is dependency
    assert (
        inspect.signature(endpoint).parameters["match"].default
        is inspect.Parameter.empty
    )


def test_match_detail_openapi_paths_preserve_routes_parameters_and_defaults():
    app, *_rest = _application("first")
    fixture = Path(__file__).parent / "fixtures" / "match_detail_openapi_paths.json"
    expected = json.loads(fixture.read_text(encoding="utf-8"))
    assert app.openapi()["paths"] == expected
    assert len([m for path in expected.values() for m in path]) == len(ENDPOINTS)


@pytest.mark.parametrize("_name,method,path", ENDPOINTS)
def test_every_match_detail_route_keeps_authorization_and_overrides_app_local(
    _name, method, path
):
    first, _r1, require_first, calls_first, _g1 = _application("first")
    second, _r2, _d2, calls_second, _g2 = _application("second")
    url = path.format(match_id="shared", metric="distance", analysis_type="tactical")

    def deny_override():
        raise HTTPException(status_code=401, detail="first-override")

    with TestClient(first) as a, TestClient(second) as b:
        for client, label in [(a, "first"), (b, "second"), (a, "first")]:
            response = client.request(method, url)
            assert response.status_code == 403
            assert response.json() == {"detail": label}
        first.dependency_overrides[require_first] = deny_override
        assert a.request(method, url).json() == {"detail": "first-override"}
        assert a.request(method, url).status_code == 401
        unchanged = b.request(method, url)
        assert unchanged.status_code == 403 and unchanged.json() == {"detail": "second"}
    assert calls_first == ["shared", "shared"]
    assert calls_second == ["shared", "shared"]


@pytest.mark.parametrize("generation", [None, "generation-old", ""])
@pytest.mark.parametrize("suffix", ["heatmap", "edits"])
def test_match_detail_reads_preserve_optional_generation_and_store(generation, suffix):
    first, *_rest1 = _application("first", deny=False)
    second, *_rest2 = _application("second", deny=False)
    params = {} if generation is None else {"generationId": generation}
    with TestClient(first) as a, TestClient(second) as b:
        for client, label in [(a, "first"), (b, "second"), (a, "first")]:
            response = client.get("/api/matches/shared/" + suffix, params=params)
            assert response.status_code == 200
            expected = {"store": label, "match": "shared", "generation": generation}
            if suffix == "heatmap":
                expected["snapshotStore"] = label
            assert response.json() == expected


@pytest.mark.parametrize(
    "payload", [None, {}, {"query": "passes", "generationId": "generation-old"}]
)
def test_match_detail_query_preserves_body_defaults_and_snapshot(payload):
    app, *_rest = _application("query-store", deny=False)
    kwargs = {} if payload is None else {"json": payload}
    with TestClient(app) as client:
        response = client.post("/api/matches/shared/queries", **kwargs)
    body = payload or {}
    assert response.status_code == 200
    assert response.json() == {
        "store": "query-store",
        "snapshotStore": "query-store",
        "match": "shared",
        "query": body.get("query", ""),
        "generation": body.get("generationId"),
    }


@pytest.mark.parametrize("suffix", ["calibration", "identity/repair"])
@pytest.mark.parametrize("payload", [None, {}, {"approved": True}])
def test_match_detail_commands_keep_none_distinct_from_empty_body(suffix, payload):
    app, *_rest = _application("commands", deny=False)
    kwargs = {} if payload is None else {"json": payload}
    with TestClient(app) as client:
        response = client.post("/api/matches/shared/" + suffix, **kwargs)
    assert response.status_code == 200
    assert response.json() == {
        "store": "commands",
        "match": "shared",
        "payload": payload,
    }


@pytest.mark.parametrize(
    "payload,team,period",
    [
        (None, "my_team", 1),
        ({}, "my_team", 1),
        ({"team": "opponent", "period": 2}, "opponent", 2),
        ({"team": "", "period": 0}, "my_team", 1),
    ],
)
def test_match_detail_attack_direction_keeps_existing_falsy_defaults(
    payload, team, period
):
    app, *_rest = _application("direction", deny=False)
    kwargs = {} if payload is None else {"json": payload}
    with TestClient(app) as client:
        response = client.post("/api/matches/shared/attack-direction", **kwargs)
    assert response.status_code == 200
    assert response.json() == {
        "store": "direction",
        "match": "shared",
        "team": team,
        "period": period,
    }


@pytest.mark.parametrize(
    "payload,start,end,generation",
    [
        (None, 0.0, 0.0, None),
        ({}, 0.0, 0.0, None),
        (
            {"start": "1.25", "end": 4, "generationId": "generation-old"},
            1.25,
            4.0,
            "generation-old",
        ),
    ],
)
def test_match_detail_render_keeps_numeric_conversion_and_generation(
    payload, start, end, generation
):
    app, *_rest = _application("edit", deny=False)
    kwargs = {} if payload is None else {"json": payload}
    with TestClient(app) as client:
        response = client.post("/api/matches/shared/edits/render", **kwargs)
    assert response.status_code == 200
    assert response.json() == {
        "store": "edit",
        "match": "shared",
        "start": start,
        "end": end,
        "generation": generation,
    }


@pytest.mark.parametrize("kind", ["offside", "spacing"])
def test_match_detail_geometry_uses_local_store_not_denied_provider(kind):
    app, _router, _dependency, _calls, gateway = _application("local", deny=False)
    gateway.denied = True
    with TestClient(app) as client:
        response = client.post("/api/matches/shared/analysis/" + kind)
    assert response.status_code == 200
    assert response.json() == {"store": "local", "match": "shared", "geometry": True}


@pytest.mark.parametrize(
    "payload", [None, {}, {"provider": "local", "question": "shape"}]
)
def test_match_detail_analysis_preserves_gateway_arguments_and_policy_error(payload):
    first, _r1, _d1, _c1, gateway = _application("first", deny=False)
    second, *_rest2 = _application("second", deny=False)
    kwargs = {} if payload is None else {"json": payload}
    with TestClient(first) as a, TestClient(second) as b:
        for client, label in [(a, "first"), (b, "second"), (a, "first")]:
            response = client.post("/api/matches/shared/analysis/tactical", **kwargs)
            assert response.status_code == 200
            assert response.json() == {
                "gateway": label,
                "match": "shared",
                "analysis": "tactical",
                "provider": (payload or {}).get("provider"),
                "body": payload or {},
            }
        gateway.denied = True
        denied = a.post("/api/matches/shared/analysis/tactical", **kwargs)
        assert denied.status_code == 403
        assert denied.json() == {"detail": {"reasonCodes": ["test-budget-denial"]}}
        assert (
            b.post("/api/matches/shared/analysis/tactical", **kwargs).status_code == 200
        )
