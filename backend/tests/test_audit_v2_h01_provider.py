from __future__ import annotations

import json
import inspect
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import anyio
import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.app import llm
from backend.app.main import create_app
from backend.app.provider_gateway import ProviderDenied, ProviderGateway
from backend.app.processor import process_match
from backend.app.schemas import FrameData, MatchConfig
from backend.app.settings import ProcessingSettings
from backend.app.storage import Storage
from backend.app.workbench.access import mint_hosted_token
from backend.app.workbench.geometry import review_incident_geometry
from backend.app.workbench.assistance import AssistancePolicy, AssistanceRouter


FIXTURE = Path(__file__).parent / "fixtures" / "sample_tracking.json"


def _run(coro, *args):
    return anyio.run(coro, *args)


@asynccontextmanager
async def _client(tmp_path: Path):
    app = create_app(storage_root=tmp_path / "storage", run_jobs_inline=True)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://127.0.0.1",
    ) as client:
        yield client


async def _install_local_only_match(client: httpx.AsyncClient) -> str:
    with FIXTURE.open("rb") as source:
        response = await client.post(
            "/api/matches",
            data={
                "name": "Local-only match",
                "inputMode": "tracking_json",
                "config": json.dumps(
                    {
                        "rights": {
                            "processingScope": "local_only",
                            "cloudPermission": False,
                        }
                    }
                ),
            },
            files={"file": ("sample_tracking.json", source, "application/json")},
        )
    assert response.status_code == 202
    return response.json()["matchId"]


async def _install_cloud_permitted_match(client: httpx.AsyncClient) -> str:
    with FIXTURE.open("rb") as source:
        response = await client.post(
            "/api/matches",
            data={
                "name": "Cloud-permitted match",
                "inputMode": "tracking_json",
                "config": json.dumps(
                    {
                        "llmProvider": "cloud",
                        "rights": {
                            "processingScope": "local_plus_burst",
                            "cloudPermission": True,
                        },
                    }
                ),
            },
            files={"file": ("sample_tracking.json", source, "application/json")},
        )
    assert response.status_code == 202
    return response.json()["matchId"]


def test_t13_local_only_match_refuses_cloud_before_adapter(tmp_path: Path, monkeypatch) -> None:
    """B13 / T13: caller-selected cloud cannot bypass server-owned match policy."""
    calls: list[dict] = []

    def network_spy(*args, **kwargs):
        calls.append(str(kwargs.get("provider")))
        raise AssertionError("network reached")

    monkeypatch.setenv("OPENROUTER_API_KEY", "must-not-be-used")
    monkeypatch.setattr("backend.app.main.run_analysis", network_spy)
    _run(_assert_cloud_refused, tmp_path, calls)


async def _assert_cloud_refused(tmp_path: Path, calls: list[str]) -> None:
    async with _client(tmp_path) as client:
        match_id = await _install_local_only_match(client)
        response = await client.post(
            f"/api/matches/{match_id}/analysis/tactical_report",
            json={"provider": "cloud", "requireProvider": True},
        )

    assert response.status_code == 403, response.text
    assert response.json()["detail"]["reasonCodes"] == ["CLOUD_NOT_PERMITTED", "SCOPE_LOCAL_ONLY"]
    assert calls == []


def test_t13_authorised_cloud_call_has_budget_reservation(tmp_path: Path, monkeypatch) -> None:
    """B13 / T13 positive control: policy and reservation precede one adapter call."""
    _run(_assert_authorised_cloud_call, tmp_path, monkeypatch)


async def _assert_authorised_cloud_call(tmp_path: Path, monkeypatch) -> None:
    calls: list[dict] = []
    evidence_generations: list[str] = []

    def adapter(*args, **kwargs):
        calls.append(kwargs)
        return {"evidence": [], "summary": "grounded"}

    monkeypatch.setattr("backend.app.main.run_analysis", adapter)
    from backend.tests.provider_billing_fixtures import fake_spend_policy
    adapter.billing_contract_id = 'synthetic-byte-token-v1'
    settings = ProcessingSettings(
        provider_spend_policy=fake_spend_policy(),
        cloud_provider_enabled=True,
        cloud_provider_api_key="test-only",
        allowed_model_ids=("test-model",),
        cloud_model_id="test-model",
        provider_call_reservation=0.25,
        provider_budget_limit=1.0,
    )
    app = create_app(storage_root=tmp_path / "authorised", run_jobs_inline=True, settings=settings)
    build_evidence = app.state.provider_gateway.build_evidence

    def record_generation(match_id: str, generation_id: str, task_type=None):
        evidence_generations.append(generation_id)
        return build_evidence(match_id, generation_id, task_type)

    app.state.provider_gateway.build_evidence = record_generation
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://127.0.0.1",
    ) as client:
        match_id = await _install_cloud_permitted_match(client)
        response = await client.post(
            f"/api/matches/{match_id}/analysis/tactical_report",
            json={"provider": "cloud", "requireProvider": True},
        )

    assert response.status_code == 200, response.text
    assert response.json()["policy"] == {"provider": "cloud", "reasonCodes": []}
    assert len(calls) == 1
    assert calls[0]["provider"] == "cloud"
    assert calls[0]["model_id"] == "test-model"
    assert calls[0]["deadline_seconds"] == 30.0
    assert app.state.provider_gateway.budget_ledger.reservations() == [
        {"matchId": match_id, "taskType": "tactical_report", "amount": 0.25}
    ]
    assert evidence_generations == [app.state.storage.current_generation(match_id).generationId]


def test_t13_cloud_preference_falls_back_with_policy_reasons(tmp_path: Path, monkeypatch) -> None:
    """B13 / T13: a non-required cloud preference falls back visibly to local."""
    calls: list[str] = []

    def adapter(*args, **kwargs):
        calls.append(kwargs["provider"])
        return {"evidence": [], "summary": "local fallback"}

    monkeypatch.setattr("backend.app.main.run_analysis", adapter)
    _run(_assert_cloud_fallback, tmp_path, calls)


async def _assert_cloud_fallback(tmp_path: Path, calls: list[str]) -> None:
    async with _client(tmp_path) as client:
        match_id = await _install_local_only_match(client)
        response = await client.post(
            f"/api/matches/{match_id}/analysis/tactical_report",
            json={"provider": "cloud"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["policy"] == {
        "provider": "local",
        "reasonCodes": ["CLOUD_NOT_PERMITTED", "SCOPE_LOCAL_ONLY"],
    }
    assert calls == ["local"]


def test_t13_budget_rejection_falls_back_unless_cloud_is_required() -> None:
    from backend.tests.provider_billing_fixtures import fake_spend_policy
    class ExhaustedLedger:
        def admit(self, **_values):
            return None

    gateway = ProviderGateway(
        None,
        ProcessingSettings(
            provider_spend_policy=fake_spend_policy(),
            cloud_provider_enabled=True,
            cloud_provider_api_key="test-only",
            allowed_model_ids=("test-model",),
            cloud_model_id="test-model",
            provider_call_reservation=0.25,
            provider_budget_limit=1.0,
        ),
        adapter_factory=lambda: SimpleNamespace(billing_contract_id='synthetic-byte-token-v1'),
        budget_ledger=ExhaustedLedger(),
    )
    match = SimpleNamespace(
        id="match-1",
        config=MatchConfig(
            llmProvider="cloud",
            rights={"processingScope": "local_plus_burst", "cloudPermission": True},
        ),
    )

    policy = gateway.resolve_policy(
        match,
        requested_provider="cloud",
        task_type="report",
        generation_id="gen_1",
        prompt="test-only bounded request",
        require_provider=False,
    )
    assert policy.provider == "local"
    assert policy.reason_codes == ("BUDGET_EXHAUSTED",)
    with pytest.raises(ProviderDenied, match="BUDGET_EXHAUSTED"):
        gateway.resolve_policy(
            match,
            requested_provider="cloud",
            task_type="report",
            generation_id="gen_1",
            prompt="test-only bounded request",
            require_provider=True,
        )


def test_t14_returned_evidence_and_numbers_are_validated() -> None:
    """B14 / T14: returned references and numeric claims must match the approved package."""
    policy = AssistancePolicy(
        taskType="report",
        maxCalls=4,
        spendCap=4.0,
        reservedCallCost=1.0,
        allowedModelIds=["test-model"],
    )
    # C03: the positive numeric control supplies the exact scope and metric
    # reference. Its old unscoped measurement is no longer a grounded claim.
    scope = {"metric": "possession_pct", "definitionVersion": "1", "teamScope": "my_team",
             "intervalStart": 0.0, "intervalEnd": 10.0, "unit": "percent"}
    metric_ref = {"matchId": "assistance", "generationId": "current", "kind": "metric", "localId": "possession"}
    metrics = [{**scope, "value": 61.0, "availability": "available", "reference": metric_ref}]
    events = [{"id": "event:current", "type": "turnover"}]

    fabricated = AssistanceRouter(
        providers_enabled=True,
        provider=lambda **_: {"evidence": ["event:fabricated"], "summary": "claim"},
    ).run(
        policy=policy,
        metrics=metrics,
        events=events,
        known_evidence_ids={"event:current", "metric:possession"},
    )
    nested_fabricated = AssistanceRouter(
        providers_enabled=True,
        provider=lambda **_: {"claims": [{"evidence": ["event:other-match"]}]},
    ).run(
        policy=policy,
        metrics=metrics,
        events=events,
        known_evidence_ids={"event:current", "metric:possession"},
    )
    wrong_number = AssistanceRouter(
        providers_enabled=True,
        provider=lambda **_: {
            "evidence": ["event:current"],
            "measurements": [{**scope, "value": 99.0, "evidence": ["metric:possession"]}],
        },
    ).run(
        policy=policy,
        metrics=metrics,
        events=events,
        known_evidence_ids={"event:current", "metric:possession"},
    )
    valid = AssistanceRouter(
        providers_enabled=True,
        provider=lambda **_: {
            "evidence": ["event:current"],
            "measurements": [{**scope, "value": 61.0, "evidence": ["metric:possession"]}],
            "interpretation": "Review the press timing.",
        },
    ).run(
        policy=policy,
        metrics=metrics,
        events=events,
        known_evidence_ids={"event:current", "metric:possession"},
    )

    assert fabricated.route == "template"
    assert fabricated.reasonCodes == ["UNKNOWN_EVIDENCE_REFERENCE"]
    assert nested_fabricated.route == "template"
    assert nested_fabricated.reasonCodes == ["UNKNOWN_EVIDENCE_REFERENCE"]
    assert wrong_number.route == "template"
    assert wrong_number.reasonCodes == ["NUMERIC_CLAIM_MISMATCH"]
    assert valid.route == "local"
    assert valid.reasonCodes == ["INTERPRETIVE"]
    assert valid.output["measurements"][0]["grounding"] == "grounded"

    top_level_mismatch = AssistanceRouter(
        providers_enabled=True,
        provider=lambda **_: {"evidence": [], "possession_pct": 99.0},
    ).run(
        policy=policy,
        metrics=metrics,
        events=events,
        known_evidence_ids={"event:current", "metric:possession"},
    )
    assert top_level_mismatch.route == "template"
    assert top_level_mismatch.reasonCodes == ["STRUCTURED_REPORT_SCHEMA_REQUIRED"]


def test_b13_direct_llm_execution_requires_gateway_token(monkeypatch) -> None:
    """B13: all provider execution routes through the server-owned gateway."""
    monkeypatch.setattr(llm, "execute_local", lambda *args, **kwargs: {"ok": True})
    with pytest.raises(PermissionError, match="provider gateway token required"):
        llm.run_analysis("tactical_report", [FrameData(frameId=0, timestamp=0)])


def test_b15_geometry_is_provider_free_and_fails_closed_without_prerequisites() -> None:
    unknown = review_incident_geometry(
        my_team=[{"x": 70.0}, {"x": 40.0}],
        enemies=[{"x": 60.0}],
        ball=None,
        attack_direction="left_to_right",
    )
    reviewed = review_incident_geometry(
        my_team=[{"x": 70.0}, {"x": 40.0}],
        enemies=[{"x": 60.0}, {"x": 65.0}],
        ball={"x": 55.0},
        attack_direction="left_to_right",
        calibration_accepted=True,
        touch_timing_known=True,
        pitch_length_m=105.0,
        uncertainty_m=0.4,
    )

    assert unknown["status"] == "unknown"
    assert unknown["spacingWidthM"] is None
    assert reviewed["status"] == "review_only"
    assert reviewed["spacingWidthM"] == 31.5
    assert reviewed["attackerBeyondSecondLastDefender"] is True
    assert reviewed["marginM"] == 10.5
    assert reviewed["uncertaintyM"] == 0.4
    assert "isOffside" not in reviewed
    assert '"offside": boolean' not in inspect.getsource(llm)


def test_t24_hosted_mode_requires_auth_and_ignores_forged_tenant_headers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GA_FLAG_LEFTOVER_HTTP", raising=False)
    with pytest.raises(ValueError, match="authentication backend"):
        create_app(
            storage_root=tmp_path / "invalid",
            settings=ProcessingSettings(deployment_mode="hosted"),
        )

    root = tmp_path / "hosted"
    storage = Storage(root)
    match = storage.create_match(
        "club a",
        "tracking_json",
        FIXTURE.name,
        FIXTURE,
        MatchConfig(rights={"audience": "club-a"}),
    )
    job_id = storage.create_job(match.id).id
    process_match(storage, job_id)
    storage.close()

    secret = "test-hosted-secret"
    app = create_app(
        storage_root=root,
        settings=ProcessingSettings(
            deployment_mode="hosted",
            auth_backend="hmac",
            auth_secret=secret,
        ),
    )
    club_a = mint_hosted_token(secret, "club-a")
    club_b = mint_hosted_token(secret, "club-b")
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert client.get(f"/api/matches/{match.id}").status_code == 401
        denied = client.get(
            f"/api/matches/{match.id}",
            headers={"Authorization": f"Bearer {club_b}", "X-Tenant-Id": "club-a"},
        )
        assert denied.status_code == 403
        assert client.get(
            f"/api/matches/{match.id}", headers={"Authorization": f"Bearer {club_a}"}
        ).status_code == 200
        assert client.get(
            f"/api/matches/{match.id}/export/match.json",
            headers={"Authorization": f"Bearer {club_b}", "X-Tenant-Id": "club-a"},
        ).status_code == 403
        assert client.get(
            "/api/workbench/dev/security", headers={"Authorization": f"Bearer {club_a}"}
        ).status_code == 403
        assert client.get(
            "/api/bundles", headers={"Authorization": f"Bearer {club_a}"}
        ).status_code == 403
        assert client.get(
            "/api/capabilities", headers={"Authorization": f"Bearer {club_a}"}
        ).status_code == 403
        assert client.get(
            "/api/workbench/dossier", headers={"Authorization": f"Bearer {club_a}"}
        ).status_code == 403
        assert client.post(
            f"/api/workbench/matches/{match.id}/incidents/geometry",
            headers={"Authorization": f"Bearer {club_b}"},
            json={},
        ).status_code == 403
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(f"/ws/jobs/{job_id}"):
                pass
