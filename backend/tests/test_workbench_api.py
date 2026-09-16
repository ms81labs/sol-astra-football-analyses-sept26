from __future__ import annotations

from pathlib import Path

import anyio
import httpx

from backend.app.main import create_app
from backend.app.settings import ProcessingSettings


def _run(coro, *args):
    return anyio.run(coro, *args)


async def _client(tmp_path: Path):
    app = create_app(
        storage_root=tmp_path / "storage",
        run_jobs_inline=True,
        settings=ProcessingSettings.from_env(),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        yield client


def test_workbench_dossier_and_capability_routes(tmp_path: Path) -> None:
    async def body():
        async for client in _client(tmp_path):
            dossier = await client.get("/api/workbench/dossier")
            assert dossier.status_code == 200
            payload = dossier.json()
            assert payload["baseline"]["declaredCameraProfile"] == "stitched_panoramic_view"
            assert payload["evaluation"]["accepted"] is False
            assert payload["native"]["approved"] is False
            assert payload["release"]["deploymentBoundary"] == "loopback"
            capabilities = await client.get("/api/workbench/capabilities")
            ids = [item["id"] for item in capabilities.json()["capabilities"]]
            assert "manual_review" in ids
            assert "physical_metrics" in ids

    _run(body)


def test_workbench_corrections_search_jobs_and_unknown_metrics(tmp_path: Path) -> None:
    async def body():
        async for client in _client(tmp_path):
            created = await client.post(
                "/api/workbench/matches/m1/corrections",
                json={"kind": "team_mapping", "payload": {"cluster": 2}, "crashBeforeCommit": True},
            )
            assert created.status_code == 200
            assert created.json()["saveState"] == "pending"
            recovered = await client.post(
                f"/api/workbench/matches/m1/corrections/{created.json()['correctionId']}/recover"
            )
            assert recovered.json()["saveState"] == "saved"
            assert recovered.json()["rebuild"] == ["team_state", "events", "metrics", "report"]
            search = await client.post(
                "/api/workbench/search",
                json={
                    "query": "show our second-half turnovers followed by a shot within 10 seconds",
                    "matchId": "m1",
                    "events": [
                        {"id": "t1", "type": "turnover", "team": "my_team", "period": 2, "timestamp": 70, "evidenceIds": ["e1"]},
                        {"id": "s1", "type": "shot", "team": "my_team", "period": 2, "timestamp": 72, "evidenceIds": ["e2"]},
                    ],
                },
            )
            assert search.json()["query"]["unanswerable"] is False
            assert search.json()["results"][0]["eventId"] == "t1"
            assistance = await client.post(
                "/api/workbench/assistance/report",
                json={"metrics": [{"availability": "unknown", "reasonCodes": ["ZERO_DENOMINATOR"]}], "claimedEvidenceIds": ["nope"]},
            )
            assert assistance.json()["route"] == "rejected"
            job = await client.post(
                "/api/workbench/jobs",
                json={"requestId": "r1", "matchId": "m1", "sourceSha256": "c" * 64, "budget": 1.0},
            )
            assert job.json()["status"] == "submitted"
            timeout = await client.post("/api/workbench/jobs/r1/timeout")
            assert timeout.json()["status"] == "outcome_unknown"
            metrics = await client.post(
                "/api/workbench/matches/m1/metrics",
                json={"possession": None, "controlledFrames": 0, "myTeamDistance": 0},
            )
            possession = next(item for item in metrics.json()["metrics"] if item["metric"] == "possession_pct")
            assert possession["availability"] == "unknown"
            assert possession["value"] is None
            interval = await client.post(
                "/api/workbench/playlists/export-interval",
                json={"timestampStart": 3.0, "timestampEnd": 5.0, "sourceFps": 25},
            )
            assert interval.json()["sourceStartSeconds"] == 3.0
            queries = await client.post(
                "/api/workbench/matches/m1/queries",
                json={
                    "query": "show our second-half turnovers followed by a shot within 10 seconds",
                    "events": [
                        {"id": "t1", "type": "turnover", "team": "my_team", "period": 2, "timestamp": 70, "evidenceIds": ["e1"]},
                        {"id": "s1", "type": "shot", "team": "my_team", "period": 2, "timestamp": 72, "evidenceIds": ["e2"]},
                    ],
                },
            )
            assert queries.status_code == 200
            assert queries.json()["results"][0]["eventId"] == "t1"
            report = await client.post(
                "/api/workbench/matches/m1/reports",
                json={"metrics": [{"availability": "unknown", "reasonCodes": ["ZERO_DENOMINATOR"], "metric": "possession_pct"}]},
            )
            assert report.status_code == 200
            assert report.json()["route"] == "template"
            pending = await client.get("/api/workbench/matches/m1/corrections?state=pending")
            assert pending.status_code == 200
            assert pending.json()["items"] == []

    _run(body)
