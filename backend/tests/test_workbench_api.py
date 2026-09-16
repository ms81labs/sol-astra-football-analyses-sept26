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
            dictionary = await client.get("/api/workbench/metrics/dictionary")
            assert dictionary.status_code == 200
            assert dictionary.json()["metrics"]["experimental_shot_quality"]["publishedLabel"] == "experimental_shot_quality"
            geometry = await client.post(
                "/api/workbench/matches/m1/incidents/geometry",
                json={"myTeam": [{"id": 7, "x": 8}], "enemies": [{"id": 18, "x": 12}, {"id": 19, "x": 14}], "ball": {"x": 20}},
            )
            assert geometry.json()["validatedMeasurement"] is False
            assert geometry.json()["decision"] is None
            job_status = await client.get("/api/workbench/jobs/r1")
            assert job_status.status_code == 200
            assert job_status.json()["status"] == "outcome_unknown"
            assert job_status.json()["cacheIdentity"]
            assert job_status.json()["terminated"] is False
            cost = await client.get("/api/workbench/jobs/r1/cost")
            assert cost.status_code == 200
            assert "p50Reserved" in cost.json()
            flags = await client.get("/api/workbench/flags")
            assert flags.json()["native_code"] is False
            evidence = await client.get("/api/workbench/matches/m1/evidence?intervalStart=0&intervalEnd=30")
            assert evidence.status_code == 200
            assert evidence.json()["intervalEndpoint"] == "half_open"
            ownership = await client.post(
                "/api/workbench/matches/m1/ownership",
                json={"ballVisible": True, "nearestTeam": "my_team", "nearestDistance": 2.0, "persistenceFrames": 1},
            )
            assert ownership.json()["mode"] == "unknown"
            package = await client.post(
                "/api/workbench/matches/m1/package",
                json={"playlist": [{"start": 3, "end": 5}], "events": [], "metrics": [], "secrets": {"DAYTONA_API_KEY": "nope"}},
            )
            assert package.status_code == 200
            assert "nope" not in str(package.json())
            rights = await client.get("/api/workbench/rights")
            assert rights.json()["uncertainCommercialPermissionBlocks"] is True
            roster = await client.get("/api/workbench/roster")
            assert roster.status_code == 200
            assert all(item["promoted"] is False for item in roster.json()["items"])
            assembled = await client.post(
                "/api/workbench/matches/m1/reports/assemble",
                json={"metrics": [{"metric": "possession_pct", "availability": "unknown", "value": None}], "claimedEvidenceIds": ["missing"], "knownEvidenceIds": []},
            )
            assert assembled.json()["publication"]["accepted"] is False
            estimate = await client.post(
                "/api/workbench/cost/estimate",
                json={"allocatedCompute": 2.0, "reviewLabour": 10.0, "fixedShare": 5.0, "exportFps": 5.0},
            )
            assert estimate.json()["exportFpsEqualsInferenceFps"] is False
            incident = await client.post(
                "/api/workbench/matches/m1/incidents/package",
                json={"clips": [{"start": 1, "end": 2}], "notes": ["review"], "bookmarks": [1.2]},
            )
            assert incident.json()["decision"] is None
            credits = await client.get("/api/workbench/credits")
            assert credits.json()["authorised"] is False
            admission = await client.get("/api/workbench/admission/handheld_low_angle")
            assert "physical_metrics" in admission.json()["withhold"]
            media = await client.post(
                "/api/workbench/media/admit",
                json={"sourceSha256": "d" * 64, "byteSize": 12, "codec": "unknown_codec", "audioTracks": 0},
            )
            assert media.status_code == 200
            assert media.json()["admitted"] is False
            assert "UNSUPPORTED_CODEC" in media.json()["reasonCodes"]
            xt = await client.get("/api/workbench/xt")
            assert xt.json()["enabled"] is False
            library = await client.post(
                "/api/workbench/library/search",
                json={"query": "elevated wide", "matches": [{"id": "m1", "cameraProfile": "stable_elevated_wide", "title": "training"}]},
            )
            assert library.json()["results"][0]["id"] == "m1"
            players = await client.post(
                "/api/workbench/matches/m1/players",
                json={"rows": [{"trackId": "t-1", "t": 2.0}], "identityContinuous": False},
            )
            assert players.json()["intervalLimited"] is True
            rates = await client.get("/api/workbench/jobs/r1/rates")
            assert rates.json()["exportFpsEqualsInferenceFps"] is False
            setup = await client.post(
                "/api/workbench/setup/assess",
                json={"cameraProfile": "handheld_low_angle", "pitchLengthM": None, "rights": {"cloudPermission": False}},
            )
            assert setup.json()["manualTaggingPermitted"] is True
            assert setup.json()["automationAdmitted"] is False
            inspector = await client.get("/api/workbench/metrics/inspect/my_team_distance_m")
            assert inspector.json()["rendered"] == "unavailable"
            residency = await client.get("/api/workbench/residency")
            assert residency.json()["euProcessingProven"] is False
            created = await client.post(
                "/api/workbench/matches",
                json={"title": "training", "cameraProfile": "handheld_low_angle", "rights": {"cloudPermission": False}},
            )
            assert created.status_code == 200
            assert created.json()["processingStarted"] is False
            assert created.json()["manualTaggingPermitted"] is True
            risks = await client.get("/api/workbench/risks")
            assert any(item["id"] == "labels_incomplete" for item in risks.json()["items"])
            milestones = await client.get("/api/workbench/milestones")
            assert [item["id"] for item in milestones.json()["items"]] == ["M0", "M1", "M2", "M3", "M4", "M5"]
            drills = await client.get("/api/workbench/training/drills")
            assert drills.json()["prescribesMedicalLoad"] is False
            targets = await client.get("/api/workbench/targets")
            assert targets.json()["measured"] is False
            assert targets.json()["p95MetadataApiReadMs"] == 500
            decisions = await client.get("/api/workbench/decisions")
            assert [item["id"] for item in decisions.json()["items"]][0] == "camera_support"
            rolled = await client.post("/api/workbench/rollback", json={"flagName": "gpu_default", "affectedOutputs": ["run-17"]})
            assert rolled.json()["newJobsAdmitted"] is False
            assert rolled.json()["rewrotePastTrialOutcomes"] is False
            nested_job = await client.post(
                "/api/workbench/matches/m1/jobs",
                json={"requestId": "r-nested", "matchId": "m1", "sourceSha256": "d" * 64, "budget": 0.5},
            )
            assert nested_job.status_code == 200
            assert nested_job.json()["status"] == "submitted"
            measures = await client.get("/api/workbench/evaluation/measures")
            assert measures.json()["trackevalIsGroundTruth"] is False
            assert measures.json()["annotationServiceHealthSatisfiesLabelGate"] is False

    _run(body)


def test_workbench_concurrent_requests_do_not_change_factual_measurements(tmp_path: Path) -> None:
    async def body():
        async for client in _client(tmp_path):
            async def post_search(suffix: str):
                return await client.post(
                    "/api/workbench/search",
                    json={
                        "query": "show our second-half turnovers followed by a shot within 10 seconds",
                        "matchId": f"m-{suffix}",
                        "events": [
                            {"id": f"t-{suffix}", "type": "turnover", "team": "my_team", "period": 2, "timestamp": 70, "evidenceIds": ["e1"]},
                            {"id": f"s-{suffix}", "type": "shot", "team": "my_team", "period": 2, "timestamp": 72, "evidenceIds": ["e2"]},
                        ],
                    },
                )

            first, second = await anyio.gather(post_search("a"), post_search("b"))
            assert first.status_code == 200 and second.status_code == 200
            assert first.json()["results"][0]["eventId"] == "t-a"
            assert second.json()["results"][0]["eventId"] == "t-b"
            hostile = await client.get("/api/workbench/dossier", headers={"host": "evil.example"})
            assert hostile.status_code == 400

            first_edit = await client.post(
                "/api/workbench/matches/m-conc/corrections",
                json={"kind": "event_accept", "payload": {"eventId": "e1"}},
            )
            stale, duplicate = await anyio.gather(
                client.post(
                    "/api/workbench/matches/m-conc/corrections",
                    json={"kind": "event_accept", "payload": {"eventId": "e1"}, "expectedVersion": 0},
                ),
                client.post(
                    "/api/workbench/matches/m-conc/corrections",
                    json={"kind": "event_accept", "payload": {"eventId": "e1"}, "expectedVersion": 0},
                ),
            )
            assert first_edit.json()["saveState"] == "saved"
            assert stale.json()["saveState"] == "conflicted"
            assert duplicate.json()["saveState"] == "conflicted"
            lane = await client.get("/api/workbench/research/lane")
            assert lane.status_code == 200
            assert lane.json()["autonomousProductionChanges"] is False
            inert = await client.post("/api/workbench/research/tracks/possession%2Fevents/execute")
            assert inert.status_code == 200
            assert inert.json()["executed"] is False

    _run(body)
