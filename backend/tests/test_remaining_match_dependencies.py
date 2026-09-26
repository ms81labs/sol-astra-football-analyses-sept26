"""Remaining match callbacks: real routing with local test-only dependency ports."""

import inspect
import json
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Annotated, get_args, get_origin, get_type_hints

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from backend.app.insight_routes import create_insight_router
from backend.app.job_routes import create_job_router
from backend.app.match_runtime_routes import create_match_runtime_router
from backend.app.review_routes import create_review_router
from backend.app.schemas import MatchConfig, MatchRecord
from backend.app.workbench.leftover_match_routes import register_match_post_routes

ENDPOINTS = [
    ("insight", "get_match_themes", "GET", "/api/matches/{match_id}/themes"),
    ("jobs", "get_match_cost", "GET", "/api/matches/{match_id}/cost"),
    ("jobs", "post_match_job", "POST", "/api/matches/{match_id}/jobs"),
    ("runtime", "get_match", "GET", "/api/matches/{match_id}"),
    ("runtime", "get_match_video", "GET", "/api/matches/{match_id}/video"),
    ("runtime", "get_frames", "GET", "/api/matches/{match_id}/frames"),
    ("runtime", "get_match_evidence", "GET", "/api/matches/{match_id}/evidence"),
    ("runtime", "get_analytics", "GET", "/api/matches/{match_id}/analytics"),
    ("runtime", "post_match_correction", "POST", "/api/matches/{match_id}/corrections"),
    (
        "runtime",
        "recover_match_correction",
        "POST",
        "/api/matches/{match_id}/corrections/{correction_id}/recover",
    ),
    (
        "runtime",
        "undo_match_correction",
        "POST",
        "/api/matches/{match_id}/corrections/{correction_id}/undo",
    ),
    ("runtime", "list_match_corrections", "GET", "/api/matches/{match_id}/corrections"),
    ("runtime", "get_mask_overlay", "GET", "/api/matches/{match_id}/mask-overlay"),
    ("review", "list_annotations", "GET", "/api/matches/{match_id}/annotations"),
    ("review", "create_annotation", "POST", "/api/matches/{match_id}/annotations"),
    (
        "review",
        "delete_annotation",
        "DELETE",
        "/api/matches/{match_id}/annotations/{annotation_id}",
    ),
    ("review", "list_issues", "GET", "/api/matches/{match_id}/issues"),
    ("review", "create_issue", "POST", "/api/matches/{match_id}/issues"),
    ("review", "delete_issue", "DELETE", "/api/matches/{match_id}/issues/{issue_id}"),
    ("review", "get_trust_crops", "GET", "/api/matches/{match_id}/trust-crops"),
    ("workbench", "post_match_heatmap", "POST", "/matches/{match_id}/heatmap"),
    ("workbench", "post_match_players", "POST", "/matches/{match_id}/players"),
    ("workbench", "post_match_ownership", "POST", "/matches/{match_id}/ownership"),
    ("workbench", "post_match_package", "POST", "/matches/{match_id}/package"),
    (
        "workbench",
        "post_match_incident_geometry",
        "POST",
        "/matches/{match_id}/incidents/geometry",
    ),
    ("workbench", "post_match_metrics", "POST", "/matches/{match_id}/metrics"),
    (
        "workbench",
        "post_match_incident_package",
        "POST",
        "/matches/{match_id}/incidents/package",
    ),
    (
        "workbench",
        "post_match_incident_review",
        "POST",
        "/matches/{match_id}/incidents/review",
    ),
    (
        "workbench",
        "post_match_assistance_fallback",
        "POST",
        "/matches/{match_id}/assistance/fallback",
    ),
    ("workbench", "post_match_identity", "POST", "/matches/{match_id}/identity"),
    ("workbench", "post_match_cache", "POST", "/matches/{match_id}/cache"),
    (
        "workbench",
        "post_match_legacy_migrate",
        "POST",
        "/matches/{match_id}/records/migrate",
    ),
    ("workbench", "post_match_formation", "POST", "/matches/{match_id}/formation"),
    (
        "workbench",
        "post_match_event_partition",
        "POST",
        "/matches/{match_id}/events/partition",
    ),
    (
        "workbench",
        "post_match_report_provenance",
        "POST",
        "/matches/{match_id}/reports/provenance",
    ),
    (
        "workbench",
        "post_match_shot_quality",
        "POST",
        "/matches/{match_id}/shots/quality",
    ),
    (
        "workbench",
        "post_match_write_alongside",
        "POST",
        "/matches/{match_id}/artifacts/alongside",
    ),
    ("workbench", "post_match_tracklets", "POST", "/matches/{match_id}/tracklets"),
    (
        "workbench",
        "post_match_shot_features",
        "POST",
        "/matches/{match_id}/shots/features",
    ),
]
GROUPS = ["insight", "jobs", "runtime", "review", "workbench"]


class _Row:
    def __init__(self, values):
        self.values = values

    def model_dump(self, **_kwargs):
        return self.values


class _Store:
    def __init__(self, label, denied):
        self.label = label
        self.denied = denied
        self.calls = []

    def get_match(self, match_id):
        self.calls.append(match_id)
        if self.denied:
            raise HTTPException(status_code=403, detail=self.label)
        return MatchRecord.model_construct(
            id=match_id,
            config=MatchConfig(),
            inputMode="tracking_json",
            originalFilename="tracking.json",
        )

    def cost_summary(self, *, match_id):
        return {"store": self.label, "requestedMatch": match_id}

    def list_corrections(self, match_id, *, state=None):
        return [{"store": self.label, "match": match_id, "state": state}]

    def load_evidence_page(self, match_id, **kwargs):
        return {"store": self.label, "match": match_id, **kwargs}

    def list_annotations(self, match_id):
        return [_Row({"store": self.label, "match": match_id})]

    def list_issues(self, match_id):
        return [_Row({"store": self.label, "match": match_id})]

    def delete_annotation(self, match_id, annotation_id):
        if annotation_id == "missing":
            raise KeyError(annotation_id)

    def delete_issue(self, match_id, issue_id):
        if issue_id == "missing":
            raise KeyError(issue_id)

    def load_analytics(self, _match_id):
        raise FileNotFoundError("No processed analytics")

    def heatmap_for_match(self, match_id):
        return {"store": self.label, "match": match_id}

    def provenance_for_match(self, match_id, *, claimed_evidence_ids):
        return {"store": self.label, "match": match_id, "claimed": claimed_evidence_ids}


def _application(group, label, *, denied=True):
    store = _Store(label, denied)

    def require_match(match_id: str) -> MatchRecord:
        return store.get_match(match_id)

    def snapshot(match_id, builder, generation_id=None):
        return {"snapshotStore": label, "generation": generation_id, **builder()}

    if group == "insight":
        router = create_insight_router(store, require_match)
    elif group == "jobs":
        runner = SimpleNamespace(
            ledger=store, settings=SimpleNamespace(processing_backend="local")
        )
        router = create_job_router(store, runner, require_match)
    elif group == "runtime":
        router = create_match_runtime_router(
            store, SimpleNamespace(deployment_mode="local"), require_match, snapshot
        )
    elif group == "review":
        router = create_review_router(store, require_match)
    elif group == "workbench":
        router = APIRouter()
        register_match_post_routes(router, store)
        endpoint = next(
            route for route in router.routes if route.name == "post_match_heatmap"
        )
        require_match = endpoint.dependant.dependencies[0].call
    else:
        raise ValueError(group)
    app = FastAPI()
    app.include_router(router)
    return app, router, require_match, store


@pytest.mark.parametrize("group,name,_method,_path", ENDPOINTS)
def test_remaining_match_dependencies_bind_local_metadata(group, name, _method, _path):
    _app, router, dependency, _store = _application(group, "first")
    endpoint = next(route.endpoint for route in router.routes if route.name == name)
    annotation = get_type_hints(endpoint, include_extras=True)["match"]
    assert get_origin(annotation) is Annotated
    match_type, marker = get_args(annotation)
    assert match_type is MatchRecord and marker.dependency is dependency
    assert (
        inspect.signature(endpoint).parameters["match"].default
        is inspect.Parameter.empty
    )


@pytest.mark.parametrize("group,name,method,path", ENDPOINTS)
def test_remaining_routes_preserve_authorization_and_app_specific_overrides(
    group, name, method, path
):
    first, _r1, dependency, first_store = _application(group, "first")
    second, _r2, _d2, second_store = _application(group, "second")
    url = re.sub(r"\{[^}]+\}", "shared", path)

    def deny_override():
        raise HTTPException(status_code=401, detail="first-override")

    with TestClient(first) as a, TestClient(second) as b:
        for client, label in [(a, "first"), (b, "second"), (a, "first")]:
            response = client.request(method, url)
            assert response.status_code == 403, name
            assert response.json() == {"detail": label}
        first.dependency_overrides[dependency] = deny_override
        overridden = a.request(method, url)
        assert overridden.status_code == 401
        assert overridden.json() == {"detail": "first-override"}
        unchanged = b.request(method, url)
        assert unchanged.status_code == 403
        assert unchanged.json() == {"detail": "second"}
    assert first_store.calls == ["shared", "shared"]
    assert second_store.calls == ["shared", "shared"]


@pytest.mark.parametrize("group", GROUPS)
def test_remaining_route_paths_preserve_unmodified_contracts(group):
    app, *_rest = _application(group, "first")
    expected = json.loads(
        (
            Path(__file__).parent / "fixtures" / "remaining_match_openapi_paths.json"
        ).read_text(encoding="utf-8")
    )
    assert app.openapi()["paths"] == expected[group]


def test_job_cost_uses_each_application_ledger():
    first, *_rest1 = _application("jobs", "first", denied=False)
    second, *_rest2 = _application("jobs", "second", denied=False)
    with TestClient(first) as a, TestClient(second) as b:
        for client, label in [(a, "first"), (b, "second"), (a, "first")]:
            response = client.get("/api/matches/shared/cost")
            assert response.status_code == 200
            assert response.json() == {
                "matchId": "shared",
                "store": label,
                "requestedMatch": "shared",
            }


@pytest.mark.parametrize("generation", [None, "old", ""])
def test_runtime_evidence_preserves_pagination_and_generation_defaults(generation):
    app, *_rest = _application("runtime", "runtime", denied=False)
    params = {} if generation is None else {"generationId": generation}
    with TestClient(app) as client:
        response = client.get("/api/matches/shared/evidence", params=params)
    assert response.status_code == 200
    assert response.json() == {
        "snapshotStore": "runtime",
        "generation": generation,
        "store": "runtime",
        "match": "shared",
        "interval_start": None,
        "interval_end": None,
        "cursor": None,
        "limit": 100,
    }


def test_runtime_video_keeps_non_video_conflict():
    app, *_rest = _application("runtime", "video", denied=False)
    with TestClient(app) as client:
        response = client.get("/api/matches/shared/video")
    assert response.status_code == 409
    assert response.json() == {
        "detail": "Video playback is only available for video-backed matches."
    }


@pytest.mark.parametrize("state", [None, "applied", ""])
def test_correction_state_default_and_explicit_value_are_preserved(state):
    app, *_rest = _application("runtime", "corrections", denied=False)
    with TestClient(app) as client:
        response = client.get(
            "/api/matches/shared/corrections",
            params={} if state is None else {"state": state},
        )
    assert response.status_code == 200
    assert response.json() == {
        "items": [{"store": "corrections", "match": "shared", "state": state}]
    }


@pytest.mark.parametrize("suffix", ["annotations", "issues"])
def test_review_lists_keep_each_app_store(suffix):
    first, *_rest1 = _application("review", "first", denied=False)
    second, *_rest2 = _application("review", "second", denied=False)
    with TestClient(first) as a, TestClient(second) as b:
        for client, label in [(a, "first"), (b, "second"), (a, "first")]:
            response = client.get("/api/matches/shared/" + suffix)
            assert response.status_code == 200
            assert response.json() == {
                "matchId": "shared",
                suffix: [{"store": label, "match": "shared"}],
            }


@pytest.mark.parametrize("suffix", ["annotations", "issues"])
def test_review_deletion_keeps_empty_204_and_missing_404(suffix):
    app, *_rest = _application("review", "delete", denied=False)
    with TestClient(app) as client:
        removed = client.delete("/api/matches/shared/" + suffix + "/existing")
        missing = client.delete("/api/matches/shared/" + suffix + "/missing")
    assert removed.status_code == 204 and removed.content == b""
    assert missing.status_code == 404 and missing.json() == {
        "detail": "Match not found"
    }


def test_insight_missing_analytics_policy_is_preserved():
    app, *_rest = _application("insight", "themes", denied=False)
    endpoint = next(
        path for group, _name, _method, path in ENDPOINTS if group == "insight"
    )
    with TestClient(app) as client:
        response = client.get(endpoint.format(match_id="shared"))
    assert response.status_code == 404 and response.json() == {
        "detail": "Analytics not ready"
    }


@pytest.mark.parametrize(
    "payload,claimed",
    [
        (None, None),
        ({}, None),
        ({"claimedEvidenceIds": ["one"]}, ["one"]),
        ({"claims": [{"evidenceIds": ["one", "two"]}, "ignored"]}, ["one", "two"]),
    ],
)
def test_workbench_provenance_preserves_claim_interpretation(payload, claimed):
    app, *_rest = _application("workbench", "proof", denied=False)
    with TestClient(app) as client:
        response = client.post(
            "/matches/shared/reports/provenance",
            **({} if payload is None else {"json": payload}),
        )
    assert response.status_code == 200
    assert response.json() == {"store": "proof", "match": "shared", "claimed": claimed}


def test_workbench_match_dependency_keeps_hosted_access_denial():
    app, *_rest = _application("workbench", "hosted", denied=False)
    with TestClient(app) as client:
        allowed = client.post("/matches/shared/heatmap")
        denied = client.post(
            "/matches/shared/heatmap", headers={"X-Deployment-Boundary": "hosted"}
        )
    assert allowed.status_code == 200 and allowed.json() == {
        "store": "hosted",
        "match": "shared",
    }
    assert denied.status_code == 403
    assert denied.json()["detail"]["reasonCodes"] == [
        "HOSTED_SIGNED_ACCESS_UNIMPLEMENTED",
        "UNSIGNED_OR_UNSCOPED_OBJECT_ACCESS",
    ]
