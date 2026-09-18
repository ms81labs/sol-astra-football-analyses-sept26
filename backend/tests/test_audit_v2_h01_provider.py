from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

import anyio
import httpx
import pytest

from backend.app import llm
from backend.app.main import create_app
from backend.app.schemas import FrameData
from backend.app.settings import ProcessingSettings
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
    reservations: list[dict] = []

    class Ledger:
        def reserve(self, **values):
            reservations.append(values)
            return values["amount"]

    def adapter(*args, **kwargs):
        calls.append(kwargs)
        return {"evidence": [], "summary": "grounded"}

    monkeypatch.setattr("backend.app.main.run_analysis", adapter)
    settings = ProcessingSettings(
        cloud_provider_enabled=True,
        cloud_provider_api_key="test-only",
        allowed_model_ids=("test-model",),
        cloud_model_id="test-model",
        provider_call_reservation=0.25,
    )
    app = create_app(storage_root=tmp_path / "authorised", run_jobs_inline=True, settings=settings)
    app.state.provider_gateway.budget_ledger = Ledger()
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
    assert reservations == [{"match_id": match_id, "task_type": "tactical_report", "amount": 0.25}]


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


def test_t14_returned_evidence_and_numbers_are_validated() -> None:
    """B14 / T14: returned references and numeric claims must match the approved package."""
    policy = AssistancePolicy(
        taskType="report",
        maxCalls=4,
        spendCap=4.0,
        reservedCallCost=1.0,
        allowedModelIds=["test-model"],
    )
    metrics = [{"metric": "possession_pct", "value": 61.0, "availability": "available"}]
    events = [{"id": "event:current", "type": "turnover"}]

    fabricated = AssistanceRouter(
        providers_enabled=True,
        provider=lambda **_: {"evidence": ["event:fabricated"], "summary": "claim"},
    ).run(
        policy=policy,
        metrics=metrics,
        events=events,
        known_evidence_ids={"event:current"},
    )
    nested_fabricated = AssistanceRouter(
        providers_enabled=True,
        provider=lambda **_: {"claims": [{"evidence": ["event:other-match"]}]},
    ).run(
        policy=policy,
        metrics=metrics,
        events=events,
        known_evidence_ids={"event:current"},
    )
    wrong_number = AssistanceRouter(
        providers_enabled=True,
        provider=lambda **_: {
            "evidence": ["event:current"],
            "measurements": [{"metric": "possession_pct", "value": 99.0}],
        },
    ).run(
        policy=policy,
        metrics=metrics,
        events=events,
        known_evidence_ids={"event:current"},
    )
    valid = AssistanceRouter(
        providers_enabled=True,
        provider=lambda **_: {
            "evidence": ["event:current"],
            "measurements": [{"metric": "possession_pct", "value": 61.0}],
            "interpretation": "Review the press timing.",
        },
    ).run(
        policy=policy,
        metrics=metrics,
        events=events,
        known_evidence_ids={"event:current"},
    )

    assert fabricated.route == "template"
    assert fabricated.reasonCodes == ["UNKNOWN_EVIDENCE_REFERENCE"]
    assert nested_fabricated.route == "template"
    assert nested_fabricated.reasonCodes == ["UNKNOWN_EVIDENCE_REFERENCE"]
    assert wrong_number.route == "template"
    assert wrong_number.reasonCodes == ["NUMERIC_CLAIM_MISMATCH"]
    assert valid.route == "local"
    assert valid.reasonCodes == ["GROUNDED"]


def test_b13_direct_llm_execution_requires_gateway_token(monkeypatch) -> None:
    """B13: all provider execution routes through the server-owned gateway."""
    monkeypatch.setattr(llm, "execute_local", lambda *args, **kwargs: {"ok": True})
    with pytest.raises(PermissionError, match="provider gateway token required"):
        llm.run_analysis("tactical_report", [FrameData(frameId=0, timestamp=0)])
