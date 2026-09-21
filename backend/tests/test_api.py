import json
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import anyio
import httpx

from backend.app.main import create_app
from backend.app.settings import ProcessingSettings

FIXTURE_DIR = Path(__file__).parent / "fixtures"
TRACKING_FIXTURE = FIXTURE_DIR / "sample_tracking.json"
MANUAL_HOMOGRAPHY_POINTS = [
    {"x": 0.0, "y": 0.0},
    {"x": 100.0, "y": 0.0},
    {"x": 100.0, "y": 100.0},
    {"x": 0.0, "y": 100.0},
]


def _run(coro, *args):
    return anyio.run(coro, *args)


def _install_verified_runtime_boundary(tmp_path: Path, monkeypatch) -> Path:
    primary_model = tmp_path / "verified-primary-model.pt"
    primary_model.write_bytes(b"verified-primary-model")
    monkeypatch.setattr(
        "backend.app.processor.materialize_proof_runtime_options",
        lambda *args, **kwargs: {
            "model_path": str(primary_model),
            "primary_model_path": str(primary_model),
            "auxiliary_ball_model_profile": None,
            "edge_share_repair_profile": None,
        },
    )
    return primary_model


@asynccontextmanager
async def api_client(tmp_path: Path, settings: ProcessingSettings | None = None):
    storage_root = tmp_path / "storage"
    app = create_app(storage_root=storage_root, run_jobs_inline=True, settings=settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        yield app, client


async def _upload_tracking_match(
    client: httpx.AsyncClient,
    *,
    name: str = "Sample Match",
    attack_direction: str = "right_to_left",
):
    with TRACKING_FIXTURE.open("rb") as fixture_file:
        return await client.post(
            "/api/matches",
            data={
                "name": name,
                "inputMode": "tracking_json",
                "config": json.dumps(
                    {
                        "attackDirection": attack_direction,
                        "manualHomographyPoints": MANUAL_HOMOGRAPHY_POINTS,
                    }
                ),
            },
            files={"file": ("sample_tracking.json", fixture_file, "application/json")},
        )


def _assert_no_ingest_state(app) -> None:
    storage = app.state.storage
    assert storage.list_matches() == []
    with storage._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
    upload_dir = storage.storage_root / "uploads"
    assert not upload_dir.exists() or list(upload_dir.iterdir()) == []


def test_match_import_rejects_unknown_input_mode_before_writes(tmp_path: Path):
    _run(_test_match_import_rejects_unknown_input_mode_before_writes, tmp_path)


async def _test_match_import_rejects_unknown_input_mode_before_writes(tmp_path: Path):
    async with api_client(tmp_path) as (app, client):
        response = await client.post(
            "/api/matches",
            data={"name": "Bad Mode", "inputMode": "archive", "config": "{}"},
            files={"file": ("sample.bin", b"payload", "application/octet-stream")},
        )

        assert response.status_code in {400, 422}
        _assert_no_ingest_state(app)


def test_match_import_maps_upload_limit_to_413_without_writes(tmp_path: Path):
    _run(_test_match_import_maps_upload_limit_to_413_without_writes, tmp_path)


async def _test_match_import_maps_upload_limit_to_413_without_writes(tmp_path: Path):
    settings = ProcessingSettings(max_upload_bytes=3)
    async with api_client(tmp_path, settings=settings) as (app, client):
        response = await client.post(
            "/api/matches",
            data={"name": "Too Large", "inputMode": "tracking_json", "config": "{}"},
            files={"file": ("sample.json", b"1234", "application/json")},
        )

        assert response.status_code == 413
        assert "3 bytes" in response.json()["detail"]
        _assert_no_ingest_state(app)


def test_match_import_does_not_read_entire_upload_on_event_loop(
    tmp_path: Path,
    monkeypatch,
):
    _run(_test_match_import_does_not_read_entire_upload_on_event_loop, tmp_path, monkeypatch)


async def _test_match_import_does_not_read_entire_upload_on_event_loop(
    tmp_path: Path,
    monkeypatch,
):
    async def fail_read(*args, **kwargs):
        raise AssertionError("UploadFile.read must not be called")

    monkeypatch.setattr("fastapi.datastructures.UploadFile.read", fail_read)
    monkeypatch.setattr("starlette.datastructures.UploadFile.read", fail_read)

    request_thread = threading.get_ident()
    storage_threads: list[int] = []
    async with api_client(tmp_path) as (app, client):
        save_upload_stream = app.state.storage.save_upload_stream

        def record_storage_thread(*args, **kwargs):
            storage_threads.append(threading.get_ident())
            return save_upload_stream(*args, **kwargs)

        monkeypatch.setattr(app.state.storage, "save_upload_stream", record_storage_thread)
        response = await _upload_tracking_match(client)

        assert response.status_code == 202
        assert storage_threads and storage_threads[0] != request_thread


def test_match_import_lifecycle_from_tracking_json(tmp_path: Path):
    _run(_test_match_import_lifecycle_from_tracking_json, tmp_path)


async def _test_match_import_lifecycle_from_tracking_json(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        response = await _upload_tracking_match(client)

        assert response.status_code == 202
        payload = response.json()
        assert payload["matchId"]
        assert payload["jobId"]

        job_response = await client.get(f"/api/jobs/{payload['jobId']}")
        assert job_response.status_code == 200
        assert job_response.json()["status"] == "completed"

        matches_response = await client.get("/api/matches")
        assert matches_response.status_code == 200
        matches = matches_response.json()
        assert matches[0]["name"] == "Sample Match"
        assert matches[0]["status"] == "ready"

        detail_response = await client.get(f"/api/matches/{payload['matchId']}")
        assert detail_response.status_code == 200
        assert detail_response.json()["inputMode"] == "tracking_json"

        frames_response = await client.get(f"/api/matches/{payload['matchId']}/frames")
        assert frames_response.status_code == 200
        frames_payload = frames_response.json()
        assert len(frames_payload["frames"]) == 3
        assert frames_payload["frames"][0]["possession"]["team"] == "my_team"

        analytics_response = await client.get(f"/api/matches/{payload['matchId']}/analytics")
        assert analytics_response.status_code == 200
        analytics_payload = analytics_response.json()
        assert analytics_payload["summary"]["possession"] == 100

        events_response = await client.get(f"/api/matches/{payload['matchId']}/events")
        assert events_response.status_code == 200
        assert events_response.json()["events"][0]["type"] == "turnover"

        frames_csv_response = await client.get(f"/api/matches/{payload['matchId']}/export/frames.csv")
        assert frames_csv_response.status_code == 200
        assert frames_csv_response.headers["content-type"].startswith("text/csv")
        assert "frameId,timestamp,ballX,ballY,ballConfidence,possessionTeam,possessionTrackId,possessionDistance" in frames_csv_response.text
        assert "0,0.0,22.0,50.0,0.95,my_team,7,1.0" in frames_csv_response.text

        events_csv_response = await client.get(f"/api/matches/{payload['matchId']}/export/events.csv")
        assert events_csv_response.status_code == 200
        assert events_csv_response.headers["content-type"].startswith("text/csv")
        assert "type,frameId,timestamp,team,fromTrackId,toTrackId,description" in events_csv_response.text
        assert "turnover,2,0.4,enemy,7,18,Possession changed to enemy" in events_csv_response.text


def test_video_import_requires_manual_homography_points(tmp_path: Path):
    _run(_test_video_import_requires_manual_homography_points, tmp_path)


async def _test_video_import_requires_manual_homography_points(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        response = await client.post(
            "/api/matches",
            data={
                "name": "Video Match",
                "inputMode": "video",
                "config": json.dumps({"attackDirection": "left_to_right"}),
            },
            files={"file": ("sample.mp4", b"not-a-real-video", "video/mp4")},
        )

        assert response.status_code == 400
        assert "manualHomographyPoints" in response.json()["detail"]


def test_video_import_surfaces_auto_homography_failure_as_failed_job(tmp_path: Path, monkeypatch):
    _run(_test_video_import_surfaces_auto_homography_failure_as_failed_job, tmp_path, monkeypatch)


async def _test_video_import_surfaces_auto_homography_failure_as_failed_job(tmp_path: Path, monkeypatch):
    async with api_client(tmp_path) as (_, client):
        verified_model = _install_verified_runtime_boundary(tmp_path, monkeypatch)
        message = (
            "Homography could not be detected automatically. "
            "Please provide manualHomographyPoints (4 corner coordinates) when uploading."
        )

        def fake_video_processor(video_path, config, **kwargs):  # noqa: ANN001
            assert config.autoHomography is True
            assert Path(kwargs["model_path"]).read_bytes() == b"verified-primary-model"
            assert kwargs["model_path"] == str(verified_model)
            raise RuntimeError(message)

        monkeypatch.setattr("backend.app.processor.process_video_input", fake_video_processor, raising=False)

        response = await client.post(
            "/api/matches",
            data={
                "name": "Auto Homography Miss",
                "inputMode": "video",
                "config": json.dumps(
                    {
                        "attackDirection": "left_to_right",
                        "autoHomography": True,
                    }
                ),
            },
            files={"file": ("sample.mp4", b"not-a-real-video", "video/mp4")},
        )

        assert response.status_code == 202
        payload = response.json()

        job_response = await client.get(f"/api/jobs/{payload['jobId']}")
        assert job_response.status_code == 200
        job_payload = job_response.json()
        assert job_payload["status"] == "failed"
        assert job_payload["error"] == message


def test_video_import_lifecycle_uses_video_processor_hook(tmp_path: Path, monkeypatch):
    _run(_test_video_import_lifecycle_uses_video_processor_hook, tmp_path, monkeypatch)


def test_trust_crops_endpoint_returns_serialized_crops(tmp_path: Path, monkeypatch):
    _run(_test_trust_crops_endpoint_returns_serialized_crops, tmp_path, monkeypatch)


async def _test_trust_crops_endpoint_returns_serialized_crops(tmp_path: Path, monkeypatch):
    async with api_client(tmp_path) as (_, client):
        response = await _upload_tracking_match(client, name="Trust Crop Match")
        assert response.status_code == 202
        match_id = response.json()["matchId"]

        monkeypatch.setattr(
            "backend.app.review_routes.compute_trust_crops",
            lambda frames, assignments, max_crops=20: [
                SimpleNamespace(
                    frameStart=3,
                    frameEnd=7,
                    timestampStart=0.6,
                    timestampEnd=1.4,
                    score=0.87,
                    reasons=["ball gap", "track switch"],
                )
            ],
        )

        trust_response = await client.get(f"/api/matches/{match_id}/trust-crops?limit=5")
        assert trust_response.status_code == 200
        payload = trust_response.json()
        assert payload["matchId"] == match_id
        assert payload["totalFrames"] == 3
        assert payload["crops"] == [
            {
                "frameStart": 3,
                "frameEnd": 7,
                "timestampStart": 0.6,
                "timestampEnd": 1.4,
                "score": 0.87,
                "reasons": ["ball gap", "track switch"],
            }
        ]


async def _test_video_import_lifecycle_uses_video_processor_hook(tmp_path: Path, monkeypatch):
    async with api_client(tmp_path) as (_, client):
        verified_model = _install_verified_runtime_boundary(tmp_path, monkeypatch)

        def fake_video_processor(video_path, config, **kwargs):  # noqa: ANN001 - simple test hook
            assert video_path.name.endswith(".mp4")
            assert len(config.manualHomographyPoints) == 4
            assert Path(kwargs["model_path"]).read_bytes() == b"verified-primary-model"
            assert kwargs["model_path"] == str(verified_model)
            return {
                "rows": [
                    {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 4, "X": 51.0, "Y": 50.0, "Conf": 0.9},
                    {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 12, "X": 61.0, "Y": 50.0, "Conf": 0.9},
                    {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 52.0, "Y": 50.0, "Conf": 0.95},
                    {"Frame_ID": 1, "Timestamp": 0.2, "Entity_Type": "player", "Track_ID": 4, "X": 52.0, "Y": 50.0, "Conf": 0.9},
                    {"Frame_ID": 1, "Timestamp": 0.2, "Entity_Type": "player", "Track_ID": 12, "X": 60.0, "Y": 50.0, "Conf": 0.9},
                    {"Frame_ID": 1, "Timestamp": 0.2, "Entity_Type": "ball", "Track_ID": -1, "X": 53.0, "Y": 50.0, "Conf": 0.95},
                ],
                "trackColors": {
                    "4": [[20, 90, 220], [24, 94, 224]],
                    "12": [[215, 45, 55], [220, 50, 60]],
                },
            }

        monkeypatch.setattr("backend.app.processor.process_video_input", fake_video_processor, raising=False)

        response = await client.post(
            "/api/matches",
            data={
                "name": "Video Match",
                "inputMode": "video",
                "config": json.dumps(
                    {
                        "attackDirection": "left_to_right",
                        "manualHomographyPoints": MANUAL_HOMOGRAPHY_POINTS,
                    }
                ),
            },
            files={"file": ("sample.mp4", b"not-a-real-video", "video/mp4")},
        )

        assert response.status_code == 202
        payload = response.json()

        job_response = await client.get(f"/api/jobs/{payload['jobId']}")
        assert job_response.status_code == 200
        assert job_response.json()["status"] == "completed"

        detail_response = await client.get(f"/api/matches/{payload['matchId']}")
        assert detail_response.status_code == 200
        detail_payload = detail_response.json()
        assert detail_payload["requiresTeamSelection"] is True
        assert len(detail_payload["teamClusters"]) == 2

        frames_response = await client.get(f"/api/matches/{payload['matchId']}/frames")
        assert frames_response.status_code == 200
        frames_payload = frames_response.json()
        assert len(frames_payload["frames"]) == 2
        assert frames_payload["frames"][0]["myTeam"] == []
        assert frames_payload["frames"][0]["enemies"] == []
        assert {player["id"] for player in frames_payload["frames"][0]["unassignedPlayers"]} == {4, 12}

        selected_cluster = next(
            cluster["clusterId"]
            for cluster in detail_payload["teamClusters"]
            if 4 in cluster["trackIds"]
        )
        patch_response = await client.patch(
            f"/api/matches/{payload['matchId']}/config",
            json={"myTeamCluster": selected_cluster},
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["config"]["myTeamCluster"] == selected_cluster
        assert patch_response.json()["requiresTeamSelection"] is False

        refreshed_frames_response = await client.get(f"/api/matches/{payload['matchId']}/frames")
        assert refreshed_frames_response.status_code == 200
        refreshed_frames = refreshed_frames_response.json()["frames"]
        assert refreshed_frames[0]["myTeam"][0]["id"] == 4


def test_analysis_route_passes_persisted_summary_and_events_to_backend(tmp_path: Path, monkeypatch):
    _run(_test_analysis_route_passes_persisted_summary_and_events_to_backend, tmp_path, monkeypatch)


async def _test_analysis_route_passes_persisted_summary_and_events_to_backend(tmp_path: Path, monkeypatch):
    async with api_client(tmp_path) as (_, client):
        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]

        captured = {}

        def fake_run_analysis(
            analysis_type,
            frames,
            *,
            provider="local",
            attack_direction="left_to_right",
            current_frame_index=None,
            summary=None,
            events=None,
            formation_timeline=None,
            shots=None,
            gateway_token=None,
            model_id=None,
            deadline_seconds=120.0,
        approved_evidence=None,
        ):
            captured["analysis_type"] = analysis_type
            captured["provider"] = provider
            captured["attack_direction"] = attack_direction
            captured["current_frame_index"] = current_frame_index
            captured["summary"] = summary
            captured["events"] = events
            captured["formation_timeline"] = formation_timeline
            captured["shots"] = shots
            captured["approved_evidence"] = approved_evidence
            return {"ok": True}

        monkeypatch.setattr("backend.app.main.run_analysis", fake_run_analysis)

        analysis_response = await client.post(
            f"/api/matches/{match_id}/analysis/tactical_report",
            json={"provider": "local", "currentFrameIndex": 1},
        )

        assert analysis_response.status_code == 200
        assert captured["analysis_type"] == "tactical_report"
        assert captured["attack_direction"] == "right_to_left"
        assert captured["summary"] is not None
        assert captured["summary"].possession == 100
        assert captured["events"] is not None
        assert len(captured["events"]) >= 1
        assert captured["formation_timeline"] is not None
        assert captured["shots"] is not None
        assert isinstance(captured["shots"], list)
        assert captured["approved_evidence"]["matchId"] == match_id
        assert analysis_response.json()["validationDisposition"] == "validation_failed"


def test_analysis_route_persists_latest_report_payload(tmp_path: Path, monkeypatch):
    _run(_test_analysis_route_persists_latest_report_payload, tmp_path, monkeypatch)


async def _test_analysis_route_persists_latest_report_payload(tmp_path: Path, monkeypatch):
    async with api_client(tmp_path) as (app, client):
        response = await _upload_tracking_match(client)
        match_id = response.json()["matchId"]

        monkeypatch.setattr(
            "backend.app.main.run_analysis",
            lambda *args, **kwargs: {
                "schemaVersion": "report_draft_v1", "taskType": "tactical_report",
                "matchId": kwargs["approved_evidence"]["matchId"],
                "generationId": kwargs["approved_evidence"]["generationId"],
                "interpretation": "Positive attacking output",
            },
        )

        analysis_response = await client.post(
            f"/api/matches/{match_id}/analysis/tactical_report",
            json={"provider": "local", "currentFrameIndex": 1},
        )

        assert analysis_response.status_code == 200

        storage = app.state.storage
        from backend.app.report_store import ReportStore
        stored = ReportStore(storage).view(match_id)["reports"]["tactical_report"]
        assert stored["payload"]["interpretation"] == "Positive attacking output"
        assert stored["payload"]["grounding"] == "interpretive"
        assert stored["generationId"] == analysis_response.json()["generationId"]
        assert not (storage._match_dir(match_id) / "tactical_report.json").exists()


def test_report_export_route_returns_html_with_stored_report_and_drills(tmp_path: Path):
    _run(_test_report_export_route_returns_html_with_stored_report_and_drills, tmp_path)


async def _test_report_export_route_returns_html_with_stored_report_and_drills(tmp_path: Path):
    async with api_client(tmp_path) as (app, client):
        response = await _upload_tracking_match(client)
        match_id = response.json()["matchId"]
        app.state.storage.save_analysis_artifact(
            match_id,
            "tactical_report",
            {
                "summary": "Positive attacking output",
                "rating": 8,
                "attacking": "Strong wide progression",
                "defensive": "Compact block",
                "pressing": "Aggressive counterpress",
                "weaknesses": "Rest defense after turnovers",
                "key_player": 7,
            },
        )
        app.state.storage.save_analysis_artifact(
            match_id,
            "drills",
            {
                "focus_area": "Rest defense",
                "drills": [
                    {
                        "name": "Wave Press",
                        "objective": "Recover quickly",
                        "setup": "6v4 in a middle third",
                        "duration": "12 min",
                    }
                ],
            },
        )

        export_response = await client.get(f"/api/matches/{match_id}/report/html")

        assert export_response.status_code == 200
        assert export_response.headers["content-type"].startswith("text/html")
        # C03: old flat documents remain accessible, but are not current facts.
        assert "Positive attacking output" not in export_response.text
        assert "Wave Press" not in export_response.text
        assert "LEGACY_REPORTS_UNVERIFIED" in export_response.text
        for task, text in (("tactical_report", "Positive attacking output"), ("drills", "Wave Press")):
            old = await client.get(f"/api/matches/{match_id}/reports/legacy/{task}")
            assert old.status_code == 200 and old.json()["validationDisposition"] == "unverified"
            assert text in old.text


def test_report_export_route_falls_back_without_stored_analyses(tmp_path: Path):
    _run(_test_report_export_route_falls_back_without_stored_analyses, tmp_path)


async def _test_report_export_route_falls_back_without_stored_analyses(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        response = await _upload_tracking_match(client)
        match_id = response.json()["matchId"]
        export_response = await client.get(f"/api/matches/{match_id}/report/html")

        assert export_response.status_code == 200
        assert "Coach report not generated yet" in export_response.text
        assert "Training drills not generated yet" in export_response.text


def test_benchmark_route_returns_saved_summary_for_completed_match(tmp_path: Path):
    _run(_test_benchmark_route_returns_saved_summary_for_completed_match, tmp_path)


async def _test_benchmark_route_returns_saved_summary_for_completed_match(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        response = await _upload_tracking_match(client)
        match_id = response.json()["matchId"]

        benchmark_response = await client.get(f"/api/matches/{match_id}/benchmark")

        assert benchmark_response.status_code == 200
        benchmark_payload = benchmark_response.json()
        assert benchmark_payload["matchId"] == match_id
        assert benchmark_payload["frameCount"] == 3
        assert benchmark_payload["withBallRatio"] == benchmark_payload["withBallFrames"] / benchmark_payload["frameCount"]
        assert benchmark_payload["trackedPossessionRatio"] == benchmark_payload["trackedPossessionFrames"] / benchmark_payload["frameCount"]
        assert benchmark_payload["eventCount"] >= 1
        assert benchmark_payload["eventFamilyCount"] >= 1
        assert benchmark_payload["artifactPresence"]["frames"] is True
        assert "selectedClusterProbe" not in benchmark_payload


def test_benchmark_route_can_include_selected_cluster_probe_without_recomputing(tmp_path: Path, monkeypatch):
    _run(_test_benchmark_route_can_include_selected_cluster_probe_without_recomputing, tmp_path, monkeypatch)


async def _test_benchmark_route_can_include_selected_cluster_probe_without_recomputing(tmp_path: Path, monkeypatch):
    async with api_client(tmp_path) as (_, client):
        verified_model = _install_verified_runtime_boundary(tmp_path, monkeypatch)

        def fake_video_processor(video_path, config, **kwargs):  # noqa: ANN001 - simple test hook
            assert Path(kwargs["model_path"]).read_bytes() == b"verified-primary-model"
            assert kwargs["model_path"] == str(verified_model)
            return {
                "rows": [
                    {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 4, "X": 51.0, "Y": 50.0, "Conf": 0.9},
                    {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 12, "X": 61.0, "Y": 50.0, "Conf": 0.9},
                    {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 52.0, "Y": 50.0, "Conf": 0.95},
                    {"Frame_ID": 1, "Timestamp": 0.2, "Entity_Type": "player", "Track_ID": 4, "X": 52.0, "Y": 50.0, "Conf": 0.9},
                    {"Frame_ID": 1, "Timestamp": 0.2, "Entity_Type": "player", "Track_ID": 12, "X": 60.0, "Y": 50.0, "Conf": 0.9},
                    {"Frame_ID": 1, "Timestamp": 0.2, "Entity_Type": "ball", "Track_ID": -1, "X": 53.0, "Y": 50.0, "Conf": 0.95},
                ],
                "trackColors": {
                    "4": [[20, 90, 220], [24, 94, 224]],
                    "12": [[215, 45, 55], [220, 50, 60]],
                },
            }

        monkeypatch.setattr("backend.app.processor.process_video_input", fake_video_processor, raising=False)

        response = await client.post(
            "/api/matches",
            data={
                "name": "Video Match",
                "inputMode": "video",
                "config": json.dumps(
                    {
                        "attackDirection": "left_to_right",
                        "manualHomographyPoints": MANUAL_HOMOGRAPHY_POINTS,
                    }
                ),
            },
            files={"file": ("sample.mp4", b"not-a-real-video", "video/mp4")},
        )

        assert response.status_code == 202
        match_id = response.json()["matchId"]

        detail_response = await client.get(f"/api/matches/{match_id}")
        assert detail_response.status_code == 200
        detail_payload = detail_response.json()
        selected_cluster = next(
            cluster["clusterId"]
            for cluster in detail_payload["teamClusters"]
            if 4 in cluster["trackIds"]
        )

        patch_response = await client.patch(
            f"/api/matches/{match_id}/config",
            json={"myTeamCluster": selected_cluster},
        )
        assert patch_response.status_code == 200

        benchmark_response = await client.get(
            f"/api/matches/{match_id}/benchmark?includeSelectedClusterProbe=true"
        )

        assert benchmark_response.status_code == 200
        benchmark_payload = benchmark_response.json()
        assert benchmark_payload["saved"]["matchId"] == match_id
        assert benchmark_payload["selectedClusterProbe"]["clusterId"] == selected_cluster
        assert [probe["clusterId"] for probe in benchmark_payload["selectedClusters"]] == [selected_cluster]
        assert benchmark_payload["recommendedCluster"] is None
        assert benchmark_payload["probeStatus"] == "not_run"
        assert "SNAPSHOT_READ_CANNOT_RUN_CLUSTER_PROBES" in benchmark_payload["reasonCodes"]
        assert benchmark_payload["selectedClusterProbe"]["withBallFrames"] == benchmark_payload["saved"]["withBallFrames"]
        assert benchmark_payload["selectedClusterProbe"]["trackedPossessionFrames"] == benchmark_payload["saved"]["trackedPossessionFrames"]
        assert benchmark_payload["selectedClusterProbe"]["controlledPossessionFrames"] == benchmark_payload["saved"]["controlledPossessionFrames"]
        assert benchmark_payload["selectedClusterProbe"]["withBallRatio"] == benchmark_payload["saved"]["withBallRatio"]
        assert benchmark_payload["selectedClusterProbe"]["trackedPossessionRatio"] == benchmark_payload["saved"]["trackedPossessionRatio"]

        refreshed_detail_response = await client.get(f"/api/matches/{match_id}")
        assert refreshed_detail_response.status_code == 200
        assert refreshed_detail_response.json()["config"]["myTeamCluster"] == selected_cluster


def test_csv_export_route_returns_flattened_saved_artifacts(tmp_path: Path):
    _run(_test_csv_export_route_returns_flattened_saved_artifacts, tmp_path)


async def _test_csv_export_route_returns_flattened_saved_artifacts(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        response = await _upload_tracking_match(client)
        match_id = response.json()["matchId"]

        events_response = await client.get(f"/api/matches/{match_id}/export/events.csv")

        assert events_response.status_code == 200
        assert events_response.headers["content-type"].startswith("text/csv")
        assert "type,frameId,timestamp,team,fromTrackId,toTrackId,description" in events_response.text
        assert "turnover" in events_response.text

        frames_response = await client.get(f"/api/matches/{match_id}/export/frames.csv")

        assert frames_response.status_code == 200
        assert frames_response.headers["content-type"].startswith("text/csv")
        assert "frameId,timestamp,ballX,ballY,ballConfidence,possessionTeam,possessionTrackId,possessionDistance" in frames_response.text
        assert "my_team" in frames_response.text


def test_match_json_export_route_returns_canonical_bundle(tmp_path: Path):
    _run(_test_match_json_export_route_returns_canonical_bundle, tmp_path)


async def _test_match_json_export_route_returns_canonical_bundle(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        response = await _upload_tracking_match(client)
        match_id = response.json()["matchId"]

        bundle_response = await client.get(f"/api/matches/{match_id}/export/match.json")

        assert bundle_response.status_code == 200
        assert bundle_response.headers["content-type"].startswith("application/json")
        bundle = bundle_response.json()
        assert bundle["schemaVersion"] == "match_bundle_v1"
        assert bundle["match"]["id"] == match_id
        assert len(bundle["frames"]) == 3
        assert bundle["analytics"]["summary"]["possession"] == 100
        assert bundle["events"][0]["type"] == "turnover"
        assert bundle["artifactAvailability"]["frames"] is True
        assert bundle["artifactAvailability"]["analytics"] is True
        assert bundle["artifactAvailability"]["events"] is True
        assert bundle["artifactAvailability"]["acceptedMatchState"] is True
        assert bundle["provenance"]["deterministicCore"] is True
        assert bundle["exports"]["framesCsv"] == f"/api/matches/{match_id}/export/frames.csv?generationId={bundle['generationId']}"
        assert bundle["exports"]["eventsCsv"] == f"/api/matches/{match_id}/export/events.csv?generationId={bundle['generationId']}"
        assert bundle["exports"]["reportHtml"] == f"/api/matches/{match_id}/report/html?generationId={bundle['generationId']}"


def test_video_route_serves_uploaded_file_for_video_matches(tmp_path: Path, monkeypatch):
    _run(_test_video_route_serves_uploaded_file_for_video_matches, tmp_path, monkeypatch)


async def _test_video_route_serves_uploaded_file_for_video_matches(tmp_path: Path, monkeypatch):
    async with api_client(tmp_path) as (app, client):
        def fake_video_processor(video_path, config, **kwargs):  # noqa: ANN001
            assert "model_path" in kwargs
            return {
                "rows": [
                    {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": 0, "X": 50.0, "Y": 50.0, "Conf": 0.9},
                ],
                "trackColors": {},
            }

        monkeypatch.setattr("backend.app.processor.process_video_input", fake_video_processor, raising=False)

        response = await client.post(
            "/api/matches",
            data={
                "name": "Video Match",
                "inputMode": "video",
                "config": json.dumps(
                    {
                        "manualHomographyPoints": MANUAL_HOMOGRAPHY_POINTS,
                    }
                ),
            },
            files={"file": ("sample.mp4", b"video-binary", "video/mp4")},
        )

        assert response.status_code == 202
        match_id = response.json()["matchId"]

        match_detail = await client.get(f"/api/matches/{match_id}")
        assert match_detail.status_code == 200
        assert match_detail.json()["inputMode"] == "video"
        assert app.state.storage.get_match_input_path(match_id).read_bytes() == b"video-binary"


def test_video_route_rejects_tracking_json_matches(tmp_path: Path):
    _run(_test_video_route_rejects_tracking_json_matches, tmp_path)


async def _test_video_route_rejects_tracking_json_matches(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        response = await _upload_tracking_match(client, name="Tracking Match")

        assert response.status_code == 202
        match_id = response.json()["matchId"]

        video_response = await client.get(f"/api/matches/{match_id}/video")

        assert video_response.status_code == 409


def test_frames_endpoint_pages_with_cursor_and_preserves_count(tmp_path: Path):
    _run(_test_frames_endpoint_pages_with_cursor_and_preserves_count, tmp_path)


async def _test_frames_endpoint_pages_with_cursor_and_preserves_count(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]

        first = await client.get(f"/api/matches/{match_id}/frames?limit=2")
        assert first.status_code == 200
        payload = first.json()
        assert len(payload["frames"]) == 2
        assert payload["frameCount"] == 3
        assert payload["nextCursor"] == "2"
        assert payload["intervalEndpoint"] == "half_open"
        assert [frame["frameId"] for frame in payload["frames"]] == [0, 1]

        second = await client.get(f"/api/matches/{match_id}/frames?cursor={payload['nextCursor']}&limit=2")
        assert second.status_code == 200
        remainder = second.json()
        assert [frame["frameId"] for frame in remainder["frames"]] == [2]
        assert remainder["frameCount"] == 3
        assert remainder["nextCursor"] is None

        after = await client.get(f"/api/matches/{match_id}/frames?afterFrame=1&limit=2")
        assert [frame["frameId"] for frame in after.json()["frames"]] == [1, 2]


def test_hosted_match_reads_require_session_tenant_not_client_tenant(tmp_path: Path):
    _run(_test_hosted_match_reads_require_session_tenant_not_client_tenant, tmp_path)


async def _test_hosted_match_reads_require_session_tenant_not_client_tenant(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        with TRACKING_FIXTURE.open("rb") as fixture_file:
            response = await client.post(
                "/api/matches",
                data={
                    "name": "Tenant Match",
                    "inputMode": "tracking_json",
                    "config": json.dumps(
                        {
                            "attackDirection": "right_to_left",
                            "manualHomographyPoints": MANUAL_HOMOGRAPHY_POINTS,
                            "rights": {"audience": "club-a"},
                        }
                    ),
                },
                files={"file": ("sample_tracking.json", fixture_file, "application/json")},
            )
        assert response.status_code == 202
        match_id = response.json()["matchId"]

        loopback = await client.get(f"/api/matches/{match_id}")
        assert loopback.status_code == 200

        hosted = await client.get(
            f"/api/matches/{match_id}",
            headers={"x-deployment-boundary": "hosted"},
        )
        assert hosted.status_code == 403
        assert "UNSIGNED_OR_UNSCOPED_OBJECT_ACCESS" in hosted.json()["detail"]["reasonCodes"]

        spoofed = await client.get(
            f"/api/matches/{match_id}/frames",
            headers={
                "authorization": "club-b",
                "x-object-scope": match_id,
                "x-deployment-boundary": "hosted",
                "x-tenant-id": "club-a",
            },
        )
        assert spoofed.status_code == 403
        assert spoofed.json()["detail"].get("sessionTenant") in {None, "club-b"}

        admitted = await client.get(
            f"/api/matches/{match_id}/analytics",
            headers={
                "authorization": "club-a",
                "x-object-scope": match_id,
                "x-deployment-boundary": "hosted",
                "x-tenant-id": "club-b",
            },
        )
        assert admitted.status_code == 403


def test_match_evidence_endpoint_returns_bounded_interval_page(tmp_path: Path):
    _run(_test_match_evidence_endpoint_returns_bounded_interval_page, tmp_path)


async def _test_match_evidence_endpoint_returns_bounded_interval_page(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]

        page = await client.get(f"/api/matches/{match_id}/evidence?intervalStart=0&intervalEnd=1&limit=2")
        assert page.status_code == 200
        payload = page.json()
        assert payload["intervalEndpoint"] == "half_open"
        assert payload["coordinateSpace"] == "pitch"
        assert payload["definitionVersion"] == "1"
        assert len(payload["items"]) == 2
        assert payload["nextCursor"]
        assert payload["items"][0]["payload"]["coordinateSpace"] == "pitch"
        assert payload["items"][0]["schemaVersion"] == "evidence_v1"

        nxt = await client.get(
            f"/api/matches/{match_id}/evidence?intervalStart=0&intervalEnd=1&cursor={payload['nextCursor']}&limit=10"
        )
        assert nxt.status_code == 200
        assert nxt.json()["items"]
        assert nxt.json()["items"][0]["evidenceId"] == payload["nextCursor"]
        assert payload["matchId"] == match_id


def test_match_corrections_persist_pending_then_recover(tmp_path: Path):
    _run(_test_match_corrections_persist_pending_then_recover, tmp_path)


async def _test_match_corrections_persist_pending_then_recover(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]

        pending = await client.post(
            f"/api/matches/{match_id}/corrections",
            json={"kind": "playlist_item", "payload": {"timestampStart": 0.0, "timestampEnd": 0.4}, "crashBeforeCommit": True},
        )
        assert pending.status_code == 200
        payload = pending.json()
        assert payload["saveState"] == "pending"
        assert payload["rebuild"] == []
        correction_id = payload["correctionId"]

        listed = await client.get(f"/api/matches/{match_id}/corrections?state=pending")
        assert listed.status_code == 200
        assert listed.json()["items"][0]["correctionId"] == correction_id

        recovered = await client.post(f"/api/matches/{match_id}/corrections/{correction_id}/recover")
        assert recovered.status_code == 200
        assert recovered.json()["saveState"] == "saved"
        assert recovered.json()["rebuild"]

        history = await client.get(f"/api/matches/{match_id}/corrections")
        assert history.status_code == 200
        assert history.json()["items"][0]["correctionId"] == correction_id
        assert history.json()["items"][0]["saveState"] == "saved"


def test_match_playlist_item_undo_omits_clip_from_package_and_edit_list(tmp_path: Path):
    _run(_test_match_playlist_item_undo_omits_clip_from_package_and_edit_list, tmp_path)


async def _test_match_playlist_item_undo_omits_clip_from_package_and_edit_list(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]

        saved = await client.post(
            f"/api/matches/{match_id}/corrections",
            json={"kind": "playlist_item", "payload": {"timestampStart": 0.0, "timestampEnd": 0.4}},
        )
        assert saved.status_code == 200
        assert saved.json()["saveState"] == "saved"
        correction_id = saved.json()["correctionId"]

        package = await client.get(f"/api/matches/{match_id}/package")
        assert package.status_code == 200
        starts = [item.get("timestampStart") for item in package.json()["analyst"]["playlist"]]
        assert 0.0 in starts
        edits = await client.get(f"/api/matches/{match_id}/edits")
        assert edits.status_code == 200
        assert (0.0, 0.4) in [tuple(item) for item in edits.json()["intervals"]]

        undone = await client.post(f"/api/matches/{match_id}/corrections/{correction_id}/undo")
        assert undone.status_code == 200
        assert undone.json()["undoOf"] == correction_id

        after = await client.get(f"/api/matches/{match_id}/package")
        assert after.status_code == 200
        after_starts = [item.get("timestampStart") for item in after.json()["analyst"]["playlist"]]
        assert 0.0 not in after_starts
        history_ids = {item["correctionId"] for item in after.json()["analyst"]["corrections"]}
        assert correction_id in history_ids
        assert undone.json()["correctionId"] in history_ids
        after_edits = await client.get(f"/api/matches/{match_id}/edits")
        assert after_edits.status_code == 200
        assert (0.0, 0.4) not in [tuple(item) for item in after_edits.json()["intervals"]]


def test_match_queries_use_stored_events_and_ignore_client_rows(tmp_path: Path):
    _run(_test_match_queries_use_stored_events_and_ignore_client_rows, tmp_path)


async def _test_match_queries_use_stored_events_and_ignore_client_rows(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]

        injected = await client.post(
            f"/api/matches/{match_id}/queries",
            json={
                "query": "shots",
                "events": [{"type": "shot", "timestamp": 0.1, "team": "my_team", "id": "forged"}],
            },
        )
        assert injected.status_code == 200
        assert injected.json()["query"]["unanswerable"] is False
        assert injected.json()["results"] == []

        turnovers = await client.post(
            f"/api/matches/{match_id}/queries",
            json={"query": "turnovers"},
        )
        assert turnovers.status_code == 200
        results = turnovers.json()["results"]
        assert results
        assert results[0]["matchId"] == match_id
        assert results[0]["label"] == "turnover"
        assert results[0]["evidenceIds"]


def test_match_queries_and_reports_omit_rejected_events(tmp_path: Path):
    _run(_test_match_queries_and_reports_omit_rejected_events, tmp_path)


async def _test_match_queries_and_reports_omit_rejected_events(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]

        events = await client.get(f"/api/matches/{match_id}/events")
        assert events.status_code == 200
        turnover = next(item for item in events.json()["events"] if item["type"] == "turnover")
        rejected = await client.post(
            f"/api/matches/{match_id}/corrections",
            json={"kind": "event_reject", "payload": {"frame": turnover["frameId"], "type": "turnover"}},
        )
        assert rejected.status_code == 200
        assert rejected.json()["saveState"] == "saved"

        turnovers = await client.post(f"/api/matches/{match_id}/queries", json={"query": "turnovers"})
        assert turnovers.status_code == 200
        assert all(item["timestamp"] != turnover["timestamp"] for item in turnovers.json()["results"])

        report = await client.post(f"/api/matches/{match_id}/reports", json={})
        assert report.status_code == 200
        published = report.json()["factPackage"]["events"]
        assert all(item.get("reviewStatus") != "rejected" for item in published)
        assert all(item.get("timestamp") != turnover["timestamp"] for item in published)
        partitioned = await client.get(f"/api/matches/{match_id}/events/partition")
        assert any(item.get("timestamp") == turnover["timestamp"] for item in partitioned.json()["retainedCandidates"])


def test_match_reports_assemble_from_stored_evidence(tmp_path: Path):
    _run(_test_match_reports_assemble_from_stored_evidence, tmp_path)


async def _test_match_reports_assemble_from_stored_evidence(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]

        events = await client.get(f"/api/matches/{match_id}/events")
        assert events.status_code == 200
        evidence_page = await client.get(f"/api/matches/{match_id}/evidence")
        assert evidence_page.status_code == 200
        evidence_id = next(
            item["reference"]
            for item in evidence_page.json()["items"]
            if item["payload"].get("kind") == "event"
        )

        report = await client.post(f"/api/matches/{match_id}/reports", json={})
        assert report.status_code == 200
        payload = report.json()
        assert payload["publication"]["requiresAnalyst"] is True
        assert payload["factualCheck"]["accepted"] is True
        assert payload["factPackage"]["template"]["kind"] == "deterministic_template"
        assert "IDENTITY_DISCONTINUITY" in {
            code
            for metric in payload["factPackage"]["metrics"]
            for code in metric.get("reasonCodes") or []
        }

        forged = await client.post(
            f"/api/matches/{match_id}/reports",
            json={"claimedEvidenceIds": ["forged-evidence"]},
        )
        assert forged.status_code == 200
        assert forged.json()["factualCheck"]["accepted"] is False
        assert "FABRICATED_EVIDENCE" in forged.json()["factualCheck"]["reasonCodes"]

        grounded = await client.post(
            f"/api/matches/{match_id}/reports",
            json={"claimedEvidenceIds": [evidence_id]},
        )
        assert grounded.status_code == 200
        assert grounded.json()["factualCheck"]["accepted"] is True
        assert evidence_id in grounded.json()["evidenceSelection"]["evidenceIds"]


def test_match_heatmap_uses_stored_identity_receipt(tmp_path: Path):
    _run(_test_match_heatmap_uses_stored_identity_receipt, tmp_path)


async def _test_match_heatmap_uses_stored_identity_receipt(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]

        heatmap = await client.post(
            f"/api/matches/{match_id}/heatmap",
            json={"identityContinuous": True, "wholeMatch": True, "withheld": False},
        )
        assert heatmap.status_code == 200
        payload = heatmap.json()
        assert payload["identityContinuous"] is False
        assert payload["wholeMatch"] is False
        assert payload["intervalLimited"] is True
        assert payload["withheld"] is True
        assert "IDENTITY_DISCONTINUITY" in payload["reasonCodes"]

        fetched = await client.get(f"/api/matches/{match_id}/heatmap")
        assert fetched.status_code == 200
        assert fetched.json()["identityContinuous"] is False


def test_match_players_follow_stored_identity_receipt(tmp_path: Path):
    _run(_test_match_players_follow_stored_identity_receipt, tmp_path)


async def _test_match_players_follow_stored_identity_receipt(tmp_path: Path):
    async with api_client(tmp_path) as (app, client):
        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]
        storage = app.state.storage
        storage.submit_correction(match_id, kind="identity_validate", payload={"reviewed": True})

        heatmap = await client.get(f"/api/matches/{match_id}/heatmap")
        assert heatmap.status_code == 200
        assert heatmap.json()["identityContinuous"] is True

        players = await client.post(
            f"/api/matches/{match_id}/players",
            json={"identityContinuous": False, "rows": [{"trackId": "forged"}]},
        )
        assert players.status_code == 200
        payload = players.json()
        assert payload["totalsWithheld"] is True
        assert payload["intervalLimited"] is True
        assert "IDENTITY_DISCONTINUITY" not in payload["reasonCodes"]
        assert "CALIBRATION_UNAVAILABLE" in payload["reasonCodes"]
        assert payload["identityContinuous"] is True
        assert "forged" not in {str(row["trackId"]) for row in payload["rows"]}

        listed = await client.get(f"/api/matches/{match_id}/players")
        assert listed.status_code == 200
        assert listed.json()["totalsWithheld"] is True
        assert "IDENTITY_DISCONTINUITY" not in listed.json()["reasonCodes"]

        metrics = await client.post(
            f"/api/matches/{match_id}/metrics",
            json={"identityContinuous": False, "calibrationAccepted": True},
        )
        assert metrics.status_code == 200
        by_name = {item["metric"]: item for item in metrics.json()["metrics"]}
        assert "IDENTITY_DISCONTINUITY" not in by_name["my_team_distance_m"]["reasonCodes"]
        assert "CALIBRATION_UNAVAILABLE" in by_name["my_team_distance_m"]["reasonCodes"]
        assert by_name["my_team_distance_m"]["availability"] != "available"


def test_match_identity_repair_commits_stored_tracks_and_invalidates_continuity(tmp_path: Path):
    _run(_test_match_identity_repair_commits_stored_tracks_and_invalidates_continuity, tmp_path)


async def _test_match_identity_repair_commits_stored_tracks_and_invalidates_continuity(tmp_path: Path):
    async with api_client(tmp_path) as (app, client):
        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]
        storage = app.state.storage
        storage.submit_correction(match_id, kind="identity_validate", payload={"reviewed": True})
        assert (await client.get(f"/api/matches/{match_id}/heatmap")).json()["identityContinuous"] is True

        leftover = await client.post(
            "/api/identity/repair",
            json={"kind": "track_split", "trackId": "7", "atFrame": 1, "committed": True, "identityContinuous": True},
        )
        assert leftover.status_code == 200
        assert leftover.json()["committed"] is False

        forged = await client.post(
            f"/api/matches/{match_id}/identity/repair",
            json={
                "kind": "track_split",
                "trackId": "forged",
                "atFrame": 1,
                "committed": True,
                "identityContinuous": True,
                "silentlyReconnected": True,
                "visionRerun": True,
            },
        )
        assert forged.status_code == 200
        payload = forged.json()
        assert payload["committed"] is False
        assert payload["preview"] is True
        assert payload["identityContinuous"] is False
        assert payload["silentlyReconnected"] is False
        assert payload["visionRerun"] is False
        assert "UNKNOWN_TRACK" in payload["reasonCodes"]
        assert (await client.get(f"/api/matches/{match_id}/heatmap")).json()["identityContinuous"] is True

        repaired = await client.post(
            f"/api/matches/{match_id}/identity/repair",
            json={
                "kind": "track_split",
                "trackId": "7",
                "atFrame": 1,
                "committed": True,
                "identityContinuous": True,
                "silentlyReconnected": True,
                "visionRerun": True,
            },
        )
        assert repaired.status_code == 200
        saved = repaired.json()
        assert saved["committed"] is True
        assert saved["preview"] is True
        assert saved["identityContinuous"] is False
        assert saved["silentlyReconnected"] is False
        assert saved["visionRerun"] is False
        assert "UNKNOWN_TRACK" not in saved["reasonCodes"]
        assert saved["correction"]["kind"] == "track_split"
        assert saved["correction"]["saveState"] == "saved"

        listed = await client.get(f"/api/matches/{match_id}/corrections")
        assert any(item["kind"] == "track_split" for item in listed.json()["items"])
        heatmap = await client.get(f"/api/matches/{match_id}/heatmap")
        assert heatmap.json()["identityContinuous"] is False
        players = await client.get(f"/api/matches/{match_id}/players")
        assert players.json()["totalsWithheld"] is True
        assert "IDENTITY_DISCONTINUITY" in players.json()["reasonCodes"]
        identity = await client.get(f"/api/matches/{match_id}/identity")
        assert identity.json()["identityContinuous"] is False
        assert identity.json()["silentlyReconnected"] is False
        new_id = str(saved["correction"]["payload"]["newTrackId"])
        assert new_id not in {"7", "18", "forged"}
        players_by_frame: dict[int, set[str]] = {}
        for row in players.json()["rows"]:
            players_by_frame.setdefault(int(row["frameId"]), set()).add(str(row["trackId"]))
        assert "7" in players_by_frame[0]
        assert new_id not in players_by_frame[0]
        assert "7" not in players_by_frame[1]
        assert new_id in players_by_frame[1]
        assert "7" not in players_by_frame[2]
        assert new_id in players_by_frame[2]
        assert saved["correction"]["rebuild"] == ["ownership", "player_events", "metrics", "report"]

        undone = await client.post(
            f"/api/matches/{match_id}/corrections/{saved['correction']['correctionId']}/undo"
        )
        assert undone.status_code == 200
        assert undone.json()["undoOf"] == saved["correction"]["correctionId"]
        restored = await client.get(f"/api/matches/{match_id}/players")
        restored_by_frame: dict[int, set[str]] = {}
        for row in restored.json()["rows"]:
            restored_by_frame.setdefault(int(row["frameId"]), set()).add(str(row["trackId"]))
        assert "7" in restored_by_frame[0]
        assert "7" in restored_by_frame[1]
        assert "7" in restored_by_frame[2]
        assert new_id not in restored_by_frame[1]
        assert new_id not in restored_by_frame[2]


def test_match_identity_join_commits_nonoverlapping_tracks_and_undo_restores(tmp_path: Path):
    _run(_test_match_identity_join_commits_nonoverlapping_tracks_and_undo_restores, tmp_path)


async def _test_match_identity_join_commits_nonoverlapping_tracks_and_undo_restores(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]

        overlapping = await client.post(
            f"/api/matches/{match_id}/identity/repair",
            json={
                "kind": "track_join",
                "leftTrackId": "7",
                "rightTrackId": "18",
                "committed": True,
                "identityContinuous": True,
                "silentlyReconnected": True,
                "visionRerun": True,
            },
        )
        assert overlapping.status_code == 200
        overlap_payload = overlapping.json()
        assert overlap_payload["committed"] is False
        assert overlap_payload["identityContinuous"] is False
        assert overlap_payload["silentlyReconnected"] is False
        assert overlap_payload["visionRerun"] is False
        assert "IDENTITY_OVERLAP" in overlap_payload["reasonCodes"]
        players = await client.get(f"/api/matches/{match_id}/players")
        by_frame = {}
        for row in players.json()["rows"]:
            by_frame.setdefault(int(row["frameId"]), set()).add(str(row["trackId"]))
        assert "7" in by_frame[0]
        assert "18" in by_frame[0]

        split = await client.post(
            f"/api/matches/{match_id}/identity/repair",
            json={"kind": "track_split", "trackId": "7", "atFrame": 1},
        )
        assert split.status_code == 200
        assert split.json()["committed"] is True
        new_id = str(split.json()["correction"]["payload"]["newTrackId"])

        joined = await client.post(
            f"/api/matches/{match_id}/identity/repair",
            json={
                "kind": "track_join",
                "leftTrackId": "7",
                "rightTrackId": new_id,
                "committed": True,
                "identityContinuous": True,
                "silentlyReconnected": True,
                "visionRerun": True,
            },
        )
        assert joined.status_code == 200
        saved = joined.json()
        assert saved["committed"] is True
        assert saved["identityContinuous"] is False
        assert saved["silentlyReconnected"] is False
        assert saved["visionRerun"] is False
        assert "IDENTITY_OVERLAP" not in saved["reasonCodes"]
        assert saved["correction"]["kind"] == "track_join"
        assert saved["correction"]["saveState"] == "saved"
        assert saved["correction"]["payload"]["rightFrameIds"] == [1, 2]
        joined_players = await client.get(f"/api/matches/{match_id}/players")
        joined_by_frame: dict[int, set[str]] = {}
        for row in joined_players.json()["rows"]:
            joined_by_frame.setdefault(int(row["frameId"]), set()).add(str(row["trackId"]))
        assert "7" in joined_by_frame[0]
        assert "7" in joined_by_frame[1]
        assert "7" in joined_by_frame[2]
        assert new_id not in joined_by_frame[1]
        assert new_id not in joined_by_frame[2]
        heatmap = await client.get(f"/api/matches/{match_id}/heatmap")
        assert heatmap.json()["identityContinuous"] is False

        undone = await client.post(
            f"/api/matches/{match_id}/corrections/{saved['correction']['correctionId']}/undo"
        )
        assert undone.status_code == 200
        assert undone.json()["undoOf"] == saved["correction"]["correctionId"]
        restored = await client.get(f"/api/matches/{match_id}/players")
        restored_by_frame: dict[int, set[str]] = {}
        for row in restored.json()["rows"]:
            restored_by_frame.setdefault(int(row["frameId"]), set()).add(str(row["trackId"]))
        assert "7" in restored_by_frame[0]
        assert new_id not in restored_by_frame[0]
        assert "7" not in restored_by_frame[1]
        assert new_id in restored_by_frame[1]
        assert "7" not in restored_by_frame[2]
        assert new_id in restored_by_frame[2]


def test_match_identity_promote_validates_stored_continuity_without_client_injection(tmp_path: Path):
    _run(_test_match_identity_promote_validates_stored_continuity_without_client_injection, tmp_path)


async def _test_match_identity_promote_validates_stored_continuity_without_client_injection(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]

        leftover = await client.post(
            "/api/identity/promote",
            json={
                "kind": "tracklet",
                "trackId": "7",
                "target": "match_identity",
                "reviewed": True,
                "identityContinuous": True,
            },
        )
        assert leftover.status_code == 200
        assert leftover.json()["kind"] == "tracklet"
        assert leftover.json()["rosterId"] is None
        assert (await client.get(f"/api/matches/{match_id}/heatmap")).json()["identityContinuous"] is False

        unreviewed = await client.post(
            f"/api/matches/{match_id}/identity/promote",
            json={"reviewed": False, "identityContinuous": True, "silentlyReconnected": True, "visionRerun": True},
        )
        assert unreviewed.status_code == 200
        assert unreviewed.json()["committed"] is False
        assert unreviewed.json()["identityContinuous"] is False
        assert unreviewed.json()["silentlyReconnected"] is False
        assert unreviewed.json()["visionRerun"] is False
        assert "REVIEW_REQUIRED" in unreviewed.json()["reasonCodes"]
        assert (await client.get(f"/api/matches/{match_id}/heatmap")).json()["identityContinuous"] is False

        pending = await client.post(
            f"/api/matches/{match_id}/identity/promote",
            json={"reviewed": True, "crashBeforeCommit": True, "identityContinuous": True},
        )
        assert pending.status_code == 200
        assert pending.json()["committed"] is False
        assert pending.json()["correction"]["saveState"] == "pending"
        assert (await client.get(f"/api/matches/{match_id}/heatmap")).json()["identityContinuous"] is False

        promoted = await client.post(
            f"/api/matches/{match_id}/identity/promote",
            json={"reviewed": True, "identityContinuous": True, "silentlyReconnected": True, "visionRerun": True},
        )
        assert promoted.status_code == 200
        saved = promoted.json()
        assert saved["committed"] is True
        assert saved["identityContinuous"] is True
        assert saved["silentlyReconnected"] is False
        assert saved["visionRerun"] is False
        assert saved["correction"]["kind"] == "identity_validate"
        assert saved["correction"]["saveState"] == "saved"
        heatmap = await client.get(f"/api/matches/{match_id}/heatmap")
        assert heatmap.json()["identityContinuous"] is True
        players = await client.get(f"/api/matches/{match_id}/players")
        # Identity approval alone is not permission to publish physical totals.
        assert players.json()["totalsWithheld"] is True
        assert players.json()["identityContinuous"] is True
        assert "CALIBRATION_UNAVAILABLE" in players.json()["reasonCodes"]
        metrics = await client.get(f"/api/matches/{match_id}/metrics")
        by_name = {item["metric"]: item for item in metrics.json()["metrics"]}
        assert "CALIBRATION_UNAVAILABLE" in by_name["my_team_distance_m"]["reasonCodes"]
        distance = await client.get(f"/api/matches/{match_id}/geometry/distance")
        assert distance.json()["availability"] == "withheld"
        assert distance.json()["value"] is None
        assert distance.json()["bridged"] is False
        assert "CALIBRATION_UNAVAILABLE" in distance.json()["reasonCodes"]
        assert "IDENTITY_DISCONTINUITY" not in distance.json()["reasonCodes"]

        undone = await client.post(
            f"/api/matches/{match_id}/corrections/{saved['correction']['correctionId']}/undo"
        )
        assert undone.status_code == 200
        restored = await client.get(f"/api/matches/{match_id}/heatmap")
        assert restored.json()["identityContinuous"] is False
        restored_players = await client.get(f"/api/matches/{match_id}/players")
        assert restored_players.json()["totalsWithheld"] is True


def test_match_calibration_holdout_measures_residual_and_ignores_client_acceptance(tmp_path: Path):
    _run(_test_match_calibration_holdout_measures_residual_and_ignores_client_acceptance, tmp_path)


async def _test_match_calibration_holdout_measures_residual_and_ignores_client_acceptance(tmp_path: Path):
    import numpy as np

    async with api_client(tmp_path) as (_, client):
        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]

        leftover = await client.post(
            "/api/geometry/preview",
            json={"residualP95M": 0.4, "accepted": True, "committed": True, "measured": True},
        )
        assert leftover.status_code == 200
        assert leftover.json()["accepted"] is False
        assert leftover.json()["measured"] is False
        assert leftover.json()["residualP95M"] is None

        four_point = await client.post(
            f"/api/matches/{match_id}/calibration",
            json={"accepted": True, "independentHoldout": True, "residualP95M": 0.4, "measured": True, "committed": True},
        )
        assert four_point.status_code == 200
        assert four_point.json()["evaluation"]["accepted"] is False
        assert four_point.json()["fromStoredPoints"] is True
        assert four_point.json().get("measured") is not True

        src = np.array([[25.0, 25.0], [75.0, 25.0], [25.0, 75.0], [75.0, 75.0]], dtype=np.float32)
        dst = np.array([[26.25, 17.0], [78.75, 17.0], [26.25, 51.0], [78.75, 51.0]], dtype=np.float32)
        calibrated_holdouts = [
            {
                "name": f"holdout-{index}",
                "imageX": float(source[0]),
                "imageY": float(source[1]),
                "pitchX": float(target[0]),
                "pitchY": float(target[1]),
                "independentHoldout": True,
            }
            for index, (source, target) in enumerate(zip(src, dst, strict=True))
        ]

        pending = await client.post(
            f"/api/matches/{match_id}/calibration",
            json={
                "accepted": True,
                "residualP95M": 0.4,
                "crashBeforeCommit": True,
                "landmarks": calibrated_holdouts,
            },
        )
        assert pending.status_code == 200
        assert pending.json()["evaluation"]["accepted"] is False
        fetched = await client.get(f"/api/matches/{match_id}/calibration")
        assert fetched.json()["evaluation"]["accepted"] is False

        forged = await client.post(
            f"/api/matches/{match_id}/calibration",
            json={
                "accepted": True,
                "residualP95M": 0.4,
                "landmarks": [
                    {
                        "name": "wrong-holdout",
                        "imageX": 50.0,
                        "imageY": 50.0,
                        "pitchX": 0.0,
                        "pitchY": 0.0,
                        "independentHoldout": True,
                    }
                ],
            },
        )
        assert forged.status_code == 200
        assert forged.json()["evaluation"]["accepted"] is False
        assert forged.json()["measured"] is True
        assert forged.json()["residualP95M"] != 0.4
        assert forged.json()["visionRerun"] is False
        await client.post(f"/api/matches/{match_id}/identity/promote", json={"reviewed": True})
        by_name = {item["metric"]: item for item in (await client.get(f"/api/matches/{match_id}/metrics")).json()["metrics"]}
        assert "CALIBRATION_UNAVAILABLE" in by_name["my_team_distance_m"]["reasonCodes"]

        measured = await client.post(
            f"/api/matches/{match_id}/calibration",
            json={
                "accepted": False,
                "residualP95M": 99.0,
                "landmarks": calibrated_holdouts,
            },
        )
        assert measured.status_code == 200
        saved = measured.json()
        assert saved["evaluation"]["accepted"] is True
        assert saved["measured"] is True
        assert saved["committed"] is True
        assert saved["residualP95M"] is not None
        assert saved["residualP95M"] <= 3.0
        assert saved["residualP95M"] != 99.0
        assert saved["visionRerun"] is False
        assert saved["correction"]["kind"] == "calibration"
        fetched = await client.get(f"/api/matches/{match_id}/calibration")
        assert fetched.json()["evaluation"]["accepted"] is True
        assert fetched.json()["measured"] is True

        by_name = {item["metric"]: item for item in (await client.get(f"/api/matches/{match_id}/metrics")).json()["metrics"]}
        assert "CALIBRATION_UNAVAILABLE" not in by_name["my_team_distance_m"]["reasonCodes"]
        assert by_name["my_team_distance_m"]["availability"] == "available"
        distance = await client.get(f"/api/matches/{match_id}/geometry/distance")
        assert distance.json()["availability"] == "available"
        assert distance.json()["value"] is not None
        assert distance.json()["value"] != 0.0
        assert distance.json()["value"] > 0.0
        assert distance.json()["bridged"] is False
        assert distance.json()["uncertaintyM"] == saved["residualP95M"]
        assert "IDENTITY_DISCONTINUITY" not in distance.json()["reasonCodes"]
        assert "CAMERA_CUT" not in distance.json()["reasonCodes"]
        assert "CALIBRATION_UNAVAILABLE" not in distance.json()["reasonCodes"]

        undone = await client.post(f"/api/matches/{match_id}/corrections/{saved['correction']['correctionId']}/undo")
        assert undone.status_code == 200
        restored = await client.get(f"/api/matches/{match_id}/calibration")
        assert restored.json()["evaluation"]["accepted"] is False
        by_name = {item["metric"]: item for item in (await client.get(f"/api/matches/{match_id}/metrics")).json()["metrics"]}
        assert "CALIBRATION_UNAVAILABLE" in by_name["my_team_distance_m"]["reasonCodes"]
        restored_distance = await client.get(f"/api/matches/{match_id}/geometry/distance")
        assert restored_distance.json()["availability"] == "withheld"
        assert restored_distance.json()["value"] is None
        assert "CALIBRATION_UNAVAILABLE" in restored_distance.json()["reasonCodes"]


def test_match_event_review_updates_stored_events_and_undo_restores_status(tmp_path: Path):
    _run(_test_match_event_review_updates_stored_events_and_undo_restores_status, tmp_path)


async def _test_match_event_review_updates_stored_events_and_undo_restores_status(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]
        listed = await client.get(f"/api/matches/{match_id}/events")
        original = listed.json()["events"]
        assert original
        target = original[0]

        forged = await client.post(
            f"/api/matches/{match_id}/corrections",
            json={"kind": "event_accept", "payload": {"eventId": "forged", "frame": 99, "reviewStatus": "accepted"}},
        )
        assert forged.status_code == 200
        listed = await client.get(f"/api/matches/{match_id}/events")
        assert listed.status_code == 200
        assert all(item["reviewStatus"] == "unreviewed" for item in listed.json()["events"])

        accepted = await client.post(
            f"/api/matches/{match_id}/corrections",
            json={"kind": "event_accept", "payload": {"frame": target["frameId"], "type": target["type"]}},
        )
        assert accepted.status_code == 200
        assert accepted.json()["saveState"] == "saved"
        listed = await client.get(f"/api/matches/{match_id}/events")
        by_id = {item["eventId"]: item for item in listed.json()["events"]}
        accepted_ids = {
            event_id
            for event_id, item in by_id.items()
            if item["frameId"] == target["frameId"] and item["type"] == target["type"]
        }
        assert accepted_ids
        assert all(by_id[event_id]["reviewStatus"] == "accepted" for event_id in accepted_ids)
        assert all(
            item["reviewStatus"] == "unreviewed"
            for event_id, item in by_id.items()
            if event_id not in accepted_ids
        )

        partitioned = await client.get(f"/api/matches/{match_id}/events/partition")
        assert any(item.get("eventId") in accepted_ids for item in partitioned.json()["acceptedViews"])
        assert all(
            item.get("eventId") not in accepted_ids
            for item in partitioned.json()["retainedCandidates"]
        )

        undone = await client.post(
            f"/api/matches/{match_id}/corrections/{accepted.json()['correctionId']}/undo"
        )
        assert undone.status_code == 200
        restored = await client.get(f"/api/matches/{match_id}/events")
        assert all(item["reviewStatus"] == "unreviewed" for item in restored.json()["events"])


def test_match_team_mapping_correction_swaps_stored_teams_without_vision(tmp_path: Path):
    _run(_test_match_team_mapping_correction_swaps_stored_teams_without_vision, tmp_path)


async def _test_match_team_mapping_correction_swaps_stored_teams_without_vision(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]

        frames = (await client.get(f"/api/matches/{match_id}/frames")).json()["frames"]
        assert frames[0]["myTeam"][0]["id"] == 7
        assert frames[0]["enemies"][0]["id"] == 18
        events = (await client.get(f"/api/matches/{match_id}/events")).json()["events"]
        assert any(
            item["type"] == "turnover" and item["team"] == "enemy" and item["fromTrackId"] == 7 and item["toTrackId"] == 18
            for item in events
        )

        forged = await client.post(
            f"/api/matches/{match_id}/corrections",
            json={
                "kind": "team_mapping",
                "payload": {
                    "cluster": 99,
                    "visionRerun": True,
                    "frames": [{"frameId": 0, "myTeam": [{"id": 999, "x": 50.0, "y": 50.0}]}],
                },
            },
        )
        # C02: a payload without a supported operation is rejected at admission,
        # rather than stored as a successful no-op. Forged observations are still
        # ignored even on the valid swap below.
        assert forged.status_code == 422
        assert forged.json()["error"] == "INVALID_TEAM_MAPPING"
        frames = (await client.get(f"/api/matches/{match_id}/frames")).json()["frames"]
        assert frames[0]["myTeam"][0]["id"] == 7
        assert frames[0]["enemies"][0]["id"] == 18
        assert all(player["id"] != 999 for player in frames[0]["myTeam"])

        pending = await client.post(
            f"/api/matches/{match_id}/corrections",
            json={"kind": "team_mapping", "payload": {"swap": True}, "crashBeforeCommit": True},
        )
        assert pending.status_code == 200
        assert pending.json()["saveState"] == "pending"
        frames = (await client.get(f"/api/matches/{match_id}/frames")).json()["frames"]
        assert frames[0]["myTeam"][0]["id"] == 7

        mapped = await client.post(
            f"/api/matches/{match_id}/corrections",
            json={
                "kind": "team_mapping",
                "payload": {
                    "swap": True,
                    "visionRerun": True,
                    "frames": [{"frameId": 0, "myTeam": [{"id": 999, "x": 50.0, "y": 50.0}]}],
                },
            },
        )
        assert mapped.status_code == 200
        assert mapped.json()["saveState"] == "saved"
        assert mapped.json()["rebuild"] == ["team_state", "events", "metrics", "report"]
        frames = (await client.get(f"/api/matches/{match_id}/frames")).json()["frames"]
        assert frames[0]["myTeam"][0]["id"] == 18
        assert frames[0]["enemies"][0]["id"] == 7
        assert all(player["id"] != 999 for player in frames[0]["myTeam"])
        events = (await client.get(f"/api/matches/{match_id}/events")).json()["events"]
        assert any(
            item["type"] == "turnover"
            and item["team"] == "my_team"
            and item["fromTrackId"] == 7
            and item["toTrackId"] == 18
            for item in events
        )

        undone = await client.post(f"/api/matches/{match_id}/corrections/{mapped.json()['correctionId']}/undo")
        assert undone.status_code == 200
        frames = (await client.get(f"/api/matches/{match_id}/frames")).json()["frames"]
        assert frames[0]["myTeam"][0]["id"] == 7
        assert frames[0]["enemies"][0]["id"] == 18
        events = (await client.get(f"/api/matches/{match_id}/events")).json()["events"]
        assert any(
            item["type"] == "turnover" and item["team"] == "enemy" and item["fromTrackId"] == 7 and item["toTrackId"] == 18
            for item in events
        )


def test_match_jobs_are_idempotent_and_cancel_is_a_request(tmp_path: Path):
    _run(_test_match_jobs_are_idempotent_and_cancel_is_a_request, tmp_path)


async def _test_match_jobs_are_idempotent_and_cancel_is_a_request(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]
        upload_job_id = response.json()["jobId"]

        uploaded = await client.get(f"/api/jobs/{upload_job_id}")
        assert uploaded.status_code == 200
        assert uploaded.json()["status"] == "completed"
        assert uploaded.json()["cancelRequested"] is False
        assert uploaded.json()["terminated"] is True
        assert uploaded.json()["cleanupResult"]
        assert uploaded.json()["costReserved"] is not None

        created = await client.post(
            f"/api/matches/{match_id}/jobs",
            json={"requestId": "job-scope-1", "budget": 1.25},
        )
        assert created.status_code == 202
        first = created.json()
        assert first["jobId"] == "job-scope-1"
        assert first["matchId"] == match_id
        assert first["reused"] is False
        assert first["costReserved"] == 1.25
        assert first["status"] in {"queued", "submitted", "dispatching"}

        replay = await client.post(
            f"/api/matches/{match_id}/jobs",
            json={"requestId": "job-scope-1", "budget": 1.25},
        )
        assert replay.status_code == 202
        assert replay.json()["reused"] is True
        assert replay.json()["jobId"] == "job-scope-1"

        conflict = await client.post(
            f"/api/matches/{match_id}/jobs",
            json={"requestId": "job-scope-1", "budget": 9.0},
        )
        assert conflict.status_code == 409

        cost = await client.get("/api/jobs/job-scope-1/cost")
        assert cost.status_code == 200
        assert cost.json()["reservedTotal"] == 1.25
        assert cost.json()["requestId"] == "job-scope-1"

        cancelled = await client.post("/api/jobs/job-scope-1/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["cancelRequested"] is True
        assert cancelled.json()["terminated"] is False
        assert cancelled.json()["status"] != "cancelled"

        done = await client.post(f"/api/jobs/{upload_job_id}/cancel")
        assert done.status_code == 200
        assert done.json()["cancelRequested"] is True
        assert done.json()["terminated"] is True
        assert done.json()["status"] == "completed"


def test_metric_dictionary_and_playlist_export_are_on_production_routes(tmp_path: Path):
    _run(_test_metric_dictionary_and_playlist_export_are_on_production_routes, tmp_path)


async def _test_metric_dictionary_and_playlist_export_are_on_production_routes(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        dictionary = await client.get("/api/metrics/dictionary")
        assert dictionary.status_code == 200
        assert "possession_pct" in dictionary.json()["metrics"]
        assert dictionary.json()["metrics"]["experimental_shot_quality"]["publishedLabel"] == "experimental_shot_quality"

        interval = await client.post(
            "/api/playlists/export-interval",
            json={"timestampStart": 3, "timestampEnd": 5, "sourceFps": 25},
        )
        assert interval.status_code == 200
        assert interval.json()["sourceStartSeconds"] == 3
        assert interval.json()["sourceEndSeconds"] == 5
        assert interval.json()["sourceEndFrameExclusive"] == 125


def test_production_flags_dossier_library_and_stored_match_surfaces(tmp_path: Path):
    _run(_test_production_flags_dossier_library_and_stored_match_surfaces, tmp_path)


async def _test_production_flags_dossier_library_and_stored_match_surfaces(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        flags = await client.get("/api/flags")
        assert flags.status_code == 200
        payload = flags.json()
        assert payload["gpu_default"] is False
        assert payload["native_code"] is False
        assert payload["experimental_shot_quality"] is False

        dossier = await client.get("/api/dossier")
        assert dossier.status_code == 200
        matrix = dossier.json()
        assert matrix["evaluation"]["accepted"] is False
        assert matrix["gpu"]["canPromoteDefault"] is False
        assert matrix["native"]["approved"] is False
        assert matrix["baseline"]["declaredCameraProfile"] == "stitched_panoramic_view"
        assert "independent_labels_0_of_18" in matrix["baseline"]["unresolvedGates"]

        capabilities = await client.get("/api/capabilities")
        assert capabilities.status_code == 200
        assert any(item["id"] == "manual_review" for item in capabilities.json()["capabilities"])

        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]

        injected_players = await client.post(
            f"/api/matches/{match_id}/players",
            json={"rows": [{"trackId": "forged", "t": 0.0}], "identityContinuous": True},
        )
        assert injected_players.status_code == 200
        players = injected_players.json()
        assert players["intervalLimited"] is True
        assert players["totalsWithheld"] is True
        assert "IDENTITY_DISCONTINUITY" in players["reasonCodes"]
        track_ids = {str(row["trackId"]) for row in players["rows"]}
        assert "7" in track_ids
        assert "18" in track_ids
        assert "forged" not in track_ids

        listed = await client.get(f"/api/matches/{match_id}/players")
        assert listed.status_code == 200
        assert listed.json()["intervalLimited"] is True
        assert {str(row["trackId"]) for row in listed.json()["rows"]} == track_ids

        library = await client.post(
            "/api/library/search",
            json={"query": "Sample", "matches": [{"id": "forged", "title": "Sample forged"}]},
        )
        assert library.status_code == 200
        library_ids = [item["id"] for item in library.json()["results"]]
        assert match_id in library_ids
        assert "forged" not in library_ids

        ownership = await client.post(
            f"/api/matches/{match_id}/ownership",
            json={
                "ballVisible": True,
                "nearestTeam": "my_team",
                "relativeMotion": "aligned",
                "persistenceFrames": 5,
                "calibrated": True,
            },
        )
        assert ownership.status_code == 200
        assert ownership.json()["mode"] == "unknown"
        assert "NEAREST_PLAYER_INSUFFICIENT" in ownership.json()["reasonCodes"]

        geometry = await client.post(
            f"/api/matches/{match_id}/incidents/geometry",
            json={
                "myTeam": [{"x": 999}],
                "enemies": [{"x": 1}, {"x": 2}],
                "ball": {"x": 0},
                "attackDirection": "left_to_right",
            },
        )
        assert geometry.status_code == 200
        assert geometry.json()["decision"] is None
        assert geometry.json()["validatedMeasurement"] is False
        assert geometry.json()["attackDirection"] == "right_to_left"
        assert geometry.json()["mostAdvancedTeammateX"] == 21.0
        assert "IFAB_LAW_11_NOT_APPLIED" in geometry.json()["reasonCodes"]

        package = await client.post(
            f"/api/matches/{match_id}/package",
            json={
                "events": [{"eventId": "forged", "id": "forged"}],
                "metrics": [],
                "playlist": [],
                "secrets": {"DAYTONA_API_KEY": "must-not-leak"},
            },
        )
        assert package.status_code == 200
        assembled = package.json()
        blob = json.dumps(assembled)
        assert "must-not-leak" not in blob
        assert "DAYTONA_API_KEY" not in blob
        assert assembled["analyst"]["limitations"]
        event_ids = {
            str(item.get("eventId") or item.get("id") or "")
            for item in assembled["analyst"]["events"]
        }
        assert "forged" not in event_ids
        assert assembled["operator"]["secretsAdmitted"] is True

        setup = await client.get(f"/api/matches/{match_id}/setup")
        assert setup.status_code == 200
        assert setup.json()["cameraProfile"] == "stitched_panoramic_view"
        assert setup.json()["certified"] is False
        assert setup.json()["manualTaggingPermitted"] is True

        rates = await client.get(f"/api/matches/{match_id}/rates")
        assert rates.status_code == 200
        assert rates.json()["exportFpsEqualsInferenceFps"] is False
        assert rates.json()["decodeFpsEqualsExportFps"] is False
        assert "EXPORT_FPS_IS_NOT_INFERENCE_FPS" in rates.json()["notes"]


def test_production_evaluation_operator_and_stored_metric_surfaces(tmp_path: Path):
    _run(_test_production_evaluation_operator_and_stored_metric_surfaces, tmp_path)


async def _test_production_evaluation_operator_and_stored_metric_surfaces(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        inspected = await client.get("/api/metrics/inspect/my_team_distance_m")
        assert inspected.status_code == 200
        assert inspected.json()["rendered"] == "unavailable"
        assert inspected.json()["publishedValue"] is None
        assert inspected.json()["denominator"] == "identity_continuous_eligible_seconds"

        measures = await client.get("/api/evaluation/measures")
        assert measures.status_code == 200
        assert measures.json()["trackevalIsGroundTruth"] is False
        assert measures.json()["annotationServiceHealthSatisfiesLabelGate"] is False
        assert measures.json()["analystWorkflow"]["measured"] is False

        lane = await client.get("/api/research/lane")
        assert lane.status_code == 200
        assert lane.json()["autonomousProductionChanges"] is False
        planned = await client.post("/api/research/tracks/possession/events/execute")
        assert planned.status_code == 200
        assert planned.json()["executed"] is False
        assert "PLANNED_TRACK_INERT" in planned.json()["reasonCodes"]
        coverage = await client.post("/api/research/tracks/supported-coverage/execute")
        assert coverage.status_code == 200
        assert coverage.json()["executed"] is False
        assert "RESEARCH_ADDON_ONLY" in coverage.json()["reasonCodes"]

        rolled = await client.post(
            "/api/rollback",
            json={"flagName": "gpu_default", "affectedOutputs": ["run-17-report"]},
        )
        assert rolled.status_code == 200
        assert rolled.json()["artifactsPreserved"] is True
        assert rolled.json()["rewrotePastTrialOutcomes"] is False
        assert rolled.json()["newJobsAdmitted"] is False
        assert rolled.json()["staleOutputs"] == ["run-17-report"]

        xt = await client.get("/api/xt")
        assert xt.status_code == 200
        assert xt.json()["enabled"] is False
        assert xt.json()["socceractionImportDoesNotValidateExtraction"] is True

        credits = await client.get("/api/credits")
        assert credits.status_code == 200
        assert credits.json()["authorised"] is False
        assert credits.json()["gpuCreditsDoNotPayForLabels"] is True

        handheld = await client.get("/api/admission/handheld_low_angle")
        assert handheld.status_code == 200
        assert handheld.json()["certified"] is False
        assert "physical_metrics" in handheld.json()["withhold"]

        remote = await client.post(
            "/api/media/admit",
            json={
                "sourceSha256": "a" * 64,
                "byteSize": 12,
                "codec": "h264",
                "sourceUrl": "https://example.com/footage.mp4",
            },
        )
        assert remote.status_code == 200
        assert remote.json()["admitted"] is False

        cost = await client.post("/api/cost/estimate", json={"allocatedCompute": 1.0, "exportFps": 5})
        assert cost.status_code == 200
        assert cost.json()["exportFpsEqualsInferenceFps"] is False
        assert cost.json()["total"] == 1.0

        drills = await client.get("/api/training/drills")
        assert drills.status_code == 200
        assert drills.json()["prescribesMedicalLoad"] is False
        assert drills.json()["diagnosesFatigueOrInjury"] is False

        rights = await client.get("/api/rights")
        assert rights.status_code == 200
        assert rights.json()["uncertainCommercialPermissionBlocks"] is True
        roster = await client.get("/api/roster")
        assert roster.status_code == 200
        assert all(item["promoted"] is False for item in roster.json()["items"])
        risks = await client.get("/api/risks")
        assert risks.status_code == 200
        assert risks.json()["items"]
        milestones = await client.get("/api/milestones")
        assert milestones.status_code == 200
        assert milestones.json()["progress"]["usesMergedFilesAsSuccess"] is False
        targets = await client.get("/api/targets")
        assert targets.status_code == 200
        assert targets.json()["measured"] is False
        decisions = await client.get("/api/decisions")
        assert decisions.status_code == 200
        assert decisions.json()["items"]
        residency = await client.get("/api/residency")
        assert residency.status_code == 200
        assert residency.json()["euProcessingProven"] is False

        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]
        job_id = response.json()["jobId"]

        metrics = await client.post(
            f"/api/matches/{match_id}/metrics",
            json={"identityContinuous": True, "calibrationAccepted": True, "controlledFrames": 999},
        )
        assert metrics.status_code == 200
        by_name = {item["metric"]: item for item in metrics.json()["metrics"]}
        assert by_name["my_team_distance_m"]["availability"] != "available"
        assert "IDENTITY_DISCONTINUITY" in by_name["my_team_distance_m"]["reasonCodes"]

        match_inspect = await client.get(f"/api/matches/{match_id}/metrics/inspect/my_team_distance_m")
        assert match_inspect.status_code == 200
        assert match_inspect.json()["rendered"] == "unavailable"
        assert "IDENTITY_DISCONTINUITY" in match_inspect.json()["exclusions"]

        package = await client.post(
            f"/api/matches/{match_id}/incidents/package",
            json={"clips": [{"id": "forged-offside", "decision": "offside"}], "notes": ["forged"]},
        )
        assert package.status_code == 200
        assert package.json()["decision"] is None
        assert package.json()["validatedMeasurement"] is False
        assert "forged-offside" not in json.dumps(package.json())
        assert "forged" not in json.dumps(package.json()["notes"])

        rates = await client.get(f"/api/jobs/{job_id}/rates")
        assert rates.status_code == 200
        assert rates.json()["exportFpsEqualsInferenceFps"] is False
        assert rates.json()["decodeFpsEqualsExportFps"] is False


def test_production_timeout_search_clock_and_incident_review_use_stored_data(tmp_path: Path):
    _run(_test_production_timeout_search_clock_and_incident_review_use_stored_data, tmp_path)


async def _test_production_timeout_search_clock_and_incident_review_use_stored_data(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        broker = await client.get("/api/broker")
        assert broker.status_code == 200
        assert broker.json()["admitted"] is False
        assert broker.json()["renamesCurrentQueue"] is False
        vectors = await client.get("/api/vector")
        assert vectors.status_code == 200
        assert vectors.json()["admitted"] is False
        hosted = await client.get("/api/deployment/hosted_collaboration")
        assert hosted.status_code == 200
        assert hosted.json()["admitted"] is False
        assert hosted.json()["requiresGNetwork"] is True
        local = await client.get("/api/deployment/local_only")
        assert local.status_code == 200
        assert local.json()["admitted"] is True
        assert local.json()["silentCloudFallback"] is False

        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]

        created = await client.post(
            f"/api/matches/{match_id}/jobs",
            json={"requestId": "timeout-scope-1", "budget": 0.5},
        )
        assert created.status_code == 202
        timed_out = await client.post("/api/jobs/timeout-scope-1/timeout")
        assert timed_out.status_code == 200
        assert timed_out.json()["durablePhase"] == "outcome_unknown"
        assert timed_out.json()["status"] != "cancelled"
        assert timed_out.json()["cleanupResult"] == "unknown"

        lost = await client.post(
            f"/api/matches/{match_id}/jobs",
            json={"requestId": "lost-scope-1", "budget": 0.25},
        )
        assert lost.status_code == 202
        disconnected = await client.post("/api/jobs/lost-scope-1/lost-connection")
        assert disconnected.status_code == 200
        assert disconnected.json()["durablePhase"] == "outcome_unknown"

        injected = await client.post(
            "/api/search",
            json={
                "query": "shots",
                "matchId": match_id,
                "events": [{"type": "shot", "timestamp": 0.1, "team": "my_team", "id": "forged"}],
            },
        )
        assert injected.status_code == 200
        assert injected.json()["results"] == []
        turnovers = await client.post("/api/search", json={"query": "turnovers", "matchId": match_id})
        assert turnovers.status_code == 200
        assert turnovers.json()["results"]
        assert turnovers.json()["results"][0]["matchId"] == match_id

        clock = await client.get(f"/api/matches/{match_id}/clock")
        assert clock.status_code == 200
        assert clock.json()["presentationTimeSeconds"] == 0.0
        assert clock.json()["frameAccurateOverlay"] is False

        review = await client.post(
            f"/api/matches/{match_id}/incidents/review",
            json={"attackerX": 999, "offsideLineX": 1, "decision": "offside"},
        )
        assert review.status_code == 200
        assert review.json()["decision"] is None
        assert review.json()["validatedMeasurement"] is False
        assert review.json()["level"] == 1
        assert review.json()["samples"] == []
        assert review.json()["indeterminate"] is True
        assert "offside" not in json.dumps(review.json()).lower().split("offside")[0] or review.json()["decision"] is None

        assistance = await client.post(
            f"/api/matches/{match_id}/assistance/report",
            json={"claimedEvidenceIds": ["forged-evidence"], "metrics": [{"metric": "possession_pct", "value": 100}]},
        )
        assert assistance.status_code == 200
        assert assistance.json()["factualCheck"]["accepted"] is False
        assert "FABRICATED_EVIDENCE" in assistance.json()["factualCheck"]["reasonCodes"]


def test_production_recovery_retention_security_native_and_recompute_surfaces(tmp_path: Path):
    _run(_test_production_recovery_retention_security_native_and_recompute_surfaces, tmp_path)


async def _test_production_recovery_retention_security_native_and_recompute_surfaces(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        recovery = await client.get("/api/recovery")
        assert recovery.status_code == 200
        body = recovery.json()
        assert body["deletion"]["available"] is False
        assert body["deletion"]["executed"] is False
        assert body["deletion"]["trackIdsDoNotAnonymise"] is True
        assert "CONTROLLER_PROCESSOR_ROLES_REQUIRED" in body["deletion"]["reasonCodes"]
        assert body["unresolvedIncidents"]["operatorVisible"] is True
        assert body["unresolvedIncidents"]["enterpriseUptimePromised"] is False
        assert body["unresolvedIncidents"]["syntheticTestsAreNotDeploymentAssessment"] is True
        assert body["recoveryObjectives"]["defined"] is False
        assert body["recoveryObjectives"]["enterpriseUptimePromised"] is False
        assert "RECOVERY_OBJECTIVES_UNMEASURED" in body["recoveryObjectives"]["reasonCodes"]
        assert body["stalePermissions"]["admitted"] is False
        assert "STALE_PERMISSION" in body["stalePermissions"]["reasonCodes"] or "PERMISSION_EXPIRY_UNRECORDED" in body["stalePermissions"]["reasonCodes"]

        forged_roles = await client.post(
            "/api/access/deletion",
            json={"requested": True, "controllerRecorded": True},
        )
        assert forged_roles.status_code == 200
        assert forged_roles.json()["executed"] is False
        assert forged_roles.json()["trackIdsDoNotAnonymise"] is True
        assert "CONTROLLER_PROCESSOR_ROLES_REQUIRED" in forged_roles.json()["reasonCodes"]

        frozen = await client.post(
            "/api/retention/delete",
            json={"kind": "frozen_evaluation", "authorisedPolicy": True},
        )
        assert frozen.status_code == 200
        assert frozen.json()["mayDelete"] is False
        originals = await client.post(
            "/api/retention/delete",
            json={"kind": "user_owned_original_media", "authorisedPolicy": True},
        )
        assert originals.status_code == 200
        assert originals.json()["mayDelete"] is False
        cache = await client.post(
            "/api/retention/delete",
            json={"kind": "working_cache", "authorisedPolicy": True},
        )
        assert cache.status_code == 200
        assert cache.json()["mayDelete"] is True

        scale = await client.get("/api/scale/10")
        assert scale.status_code == 200
        assert scale.json()["matchesPerMonth"] == 10
        assert scale.json()["measuredApplicationPerformance"] is False
        assert scale.json()["gbEqualsGiB"] is False
        assert scale.json()["decimalGb"] == 5.4
        assert abs(scale.json()["gib"] - (5.4 * 1e9 / (1024**3))) < 1e-9

        dpia = await client.get("/api/privacy/dpia")
        assert dpia.status_code == 200
        assert dpia.json()["cloudAllowed"] is False
        assert dpia.json()["faceRecognition"] is False
        assert dpia.json()["crossSeasonIdentity"] is False
        assert dpia.json()["localProcessingRequired"] is True

        gpu = await client.get("/api/gpu")
        assert gpu.status_code == 200
        assert gpu.json()["canPromoteDefault"] is False
        assert gpu.json()["videoEngine"]["videoEngineCapability"] is False
        assert "CUDA_VISIBILITY_IS_NOT_VIDEO_CAPABILITY" in gpu.json()["videoEngine"]["reasonCodes"]

        native = await client.get("/api/native")
        assert native.status_code == 200
        assert native.json()["approved"] is False
        assert "NATIVE_GATE_CLOSED" in native.json()["reasonCodes"]
        assert native.json()["pinned"]["universallyPortable"] is False
        assert native.json()["pinned"]["admitted"] is False
        assert native.json()["osProfiles"]["independentlyTested"] is False
        assert native.json()["ffmpeg"]["wrapperRemovesLicenceObligations"] is False
        assert native.json()["rpcFleet"]["enabled"] is False
        assert native.json()["customNative"]["approved"] is False

        security = await client.get("/api/security")
        assert security.status_code == 200
        assert security.json()["modelOutput"]["trusted"] is False
        assert security.json()["publicExposure"]["admitted"] is True
        assert security.json()["publicExposure"]["publicExposureAllowed"] is False
        assert security.json()["encryption"]["hostedEncryptionProven"] is False
        assert security.json()["allowlist"]["admitted"] is True
        assert security.json()["decoder"]["admitted"] is True
        assert security.json()["storage"]["admitted"] is True
        assert security.json()["secretsAdmitted"] is True
        assert security.json()["signedJobAccess"]["admitted"] is False
        assert security.json()["egress"]["defaultDeny"] is True

        public_host = await client.get("/api/security", headers={"x-deployment-boundary": "public"})
        assert public_host.status_code == 200
        assert public_host.json()["publicExposure"]["admitted"] is False
        assert "SECURITY_REVIEW_REQUIRED" in public_host.json()["publicExposure"]["reasonCodes"]

        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]

        match_dpia = await client.get(f"/api/matches/{match_id}/privacy")
        assert match_dpia.status_code == 200
        assert match_dpia.json()["cloudAllowed"] is False
        assert match_dpia.json()["faceRecognition"] is False

        preview = await client.get(f"/api/matches/{match_id}/setup/preview")
        assert preview.status_code == 200
        assert preview.json()["preview"] is True
        assert preview.json()["committed"] is False
        assert preview.json()["accepted"] is False
        assert preview.json()["visionRerun"] is False
        assert preview.json()["residualP95M"] is None
        assert preview.json()["measured"] is False
        assert "LANDMARK_RESIDUAL_UNMEASURED" in preview.json()["reasonCodes"]

        report_only = await client.post(
            f"/api/matches/{match_id}/recompute",
            json={"change": "report", "visionRows": [{"Frame_ID": 999}]},
        )
        assert report_only.status_code == 200
        assert report_only.json()["kind"] == "plan"
        assert report_only.json()["visionRequired"] is False
        assert "reused" not in report_only.json()
        assert "admitted" not in report_only.json()

        calibration = await client.post(
            f"/api/matches/{match_id}/recompute",
            json={"change": "calibration"},
        )
        assert calibration.status_code == 200
        assert calibration.json()["kind"] == "plan"
        assert calibration.json()["visionRequired"] is False
        assert "pitch_positions" in calibration.json()["rebuild"]

        perception = await client.post(
            f"/api/matches/{match_id}/recompute",
            json={"change": "perception"},
        )
        assert perception.status_code == 200
        assert perception.json()["kind"] == "plan"
        assert perception.json()["visionRequired"] is True
        assert perception.json()["requires"] == ["sealed_worker"]

        receipt = await client.get(f"/api/matches/{match_id}/promotion")
        assert receipt.status_code == 200
        assert receipt.json()["completeMatchAccepted"] is False
        assert receipt.json()["stageBenchmarkIsCompleteMatchAcceptance"] is False
        assert receipt.json()["outputQuality"] == "unproven"


def test_production_assistance_budgets_quality_timeline_and_decode_memory(tmp_path: Path):
    _run(_test_production_assistance_budgets_quality_timeline_and_decode_memory, tmp_path)


async def _test_production_assistance_budgets_quality_timeline_and_decode_memory(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        assistance = await client.get("/api/assistance")
        assert assistance.status_code == 200
        assert assistance.json()["providersEnabled"] is False
        assert assistance.json()["reviewOperational"] is True
        assert assistance.json()["metricsOperational"] is True
        assert assistance.json()["templateReportOperational"] is True
        assert assistance.json()["route"] == "template"
        assert "PROVIDER_DISABLED" in assistance.json()["reasonCodes"]
        assert assistance.json()["concealedPartialProcessing"] is False
        assert assistance.json()["budgets"]["vision"] != assistance.json()["budgets"]["language"]
        assert assistance.json()["embeddings"]["enabled"] is False
        assert assistance.json()["embeddings"]["provesTacticalWeakness"] is False
        assert assistance.json()["escalation"]["escalate"] is False
        assert "ESCALATION_REQUIRES_MEASURED_QUALITY_GAP" in assistance.json()["escalation"]["reasonCodes"]

        memory = await client.get("/api/decode/memory")
        assert memory.status_code == 200
        assert memory.json()["gpuResident"] is False
        assert memory.json()["canPromoteDefault"] is False
        assert memory.json()["retainAllDecodedFrames"] is False
        assert "CUDA_VISIBILITY_IS_NOT_VIDEO_CAPABILITY" in memory.json()["reasonCodes"] or memory.json()["videoEngineCapability"] is False

        reviewer = await client.get("/api/reviewer")
        assert reviewer.status_code == 200
        assert reviewer.json()["accepted"] is False

        flow = await client.get("/api/flow")
        assert flow.status_code == 200
        assert flow.json()["illustrative"] is True
        assert flow.json()["correctionInvalidatesReportWithoutRerun"] is True

        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]

        injected = await client.post(
            f"/api/matches/{match_id}/assistance/fallback",
            json={
                "metrics": [{"metric": "possession_pct", "availability": "available", "value": 100}],
                "events": [{"id": "forged", "reviewStatus": "accepted"}],
            },
        )
        assert injected.status_code == 200
        assert injected.json()["route"] == "template"
        assert "PROVIDER_DISABLED" in injected.json()["reasonCodes"]
        assert injected.json()["reviewOperational"] is True
        assert injected.json()["output"]["kind"] == "deterministic_template"
        blob = json.dumps(injected.json())
        assert "forged" not in blob
        assert injected.json()["output"]["eventCount"] >= 1

        quality = await client.get(f"/api/matches/{match_id}/quality")
        assert quality.status_code == 200
        assert quality.json()["reviewFirst"] is True
        assert quality.json()["accepted"] is False
        assert quality.json()["measured"] is False
        labels = {item["label"] for item in quality.json()["items"]}
        assert "identity switches" in labels
        assert "incorrect team selection" in labels
        assert "calibration drift" in labels
        assert "ambiguous possession around a shot" in labels
        assert all(item["accepted"] is False for item in quality.json()["items"])
        assert all(item["impact"] == "high" for item in quality.json()["items"] if item["id"] in {"identity", "team", "calibration", "possession"})


def test_production_identity_incident_ladder_hota_and_gated_challengers(tmp_path: Path):
    _run(_test_production_identity_incident_ladder_hota_and_gated_challengers, tmp_path)


async def _test_production_identity_incident_ladder_hota_and_gated_challengers(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        identity = await client.get("/api/identity")
        assert identity.status_code == 200
        assert identity.json()["faceRecognition"]["enabled"] is False
        assert identity.json()["crossSeasonIdentity"]["enabled"] is False
        assert identity.json()["appearance"]["everyDetection"] is False
        assert identity.json()["appearance"]["cameraCutDefeatsAppearance"] is True
        assert identity.json()["candidateRejoin"]["autoAccepted"] is False
        assert identity.json()["silentlyReconnected"] is False

        ladder = await client.get("/api/incidents/ladder")
        assert ladder.status_code == 200
        assert ladder.json()["level2"]["photorealistic"] is False
        assert ladder.json()["level2"]["decision"] is None
        assert ladder.json()["level3"]["enabled"] is False
        assert ladder.json()["vlm"]["refereeGroundTruth"] is False
        assert ladder.json()["replay"]["simultaneous"] is False
        assert ladder.json()["homography"]["preciseOffsideLine"] is False
        assert ladder.json()["invisible"]["repaired"] is False

        hota = await client.get("/api/evaluation/hota")
        assert hota.status_code == 200
        assert hota.json()["scored"] is False
        assert hota.json()["hota"] is None
        assert hota.json()["idf1"] is None
        assert hota.json()["trackevalIsGroundTruth"] is False

        shots = await client.get("/api/shots/tree")
        assert shots.status_code == 200
        assert shots.json()["tree"]["enabled"] is False
        assert shots.json()["tree"]["calibratedXg"] is False
        assert shots.json()["temporal"]["enabled"] is False
        assert shots.json()["temporal"]["replacesStateMachine"] is False

        collab = await client.get("/api/collaboration")
        assert collab.status_code == 200
        assert collab.json()["local"]["silentlyReplaced"] is False
        assert collab.json()["hosted"]["admitted"] is False
        assert collab.json()["hosted"]["silentlyReplaced"] is False

        stride = await client.get("/api/media/stride")
        assert stride.status_code == 200
        assert stride.json()["addsVidStrideAlone"] is False
        assert stride.json()["targetFpsEqualsInferenceFps"] is False

        cache = await client.get("/api/cache/tenancy")
        assert cache.status_code == 200
        assert cache.json()["crossTenant"]["allowed"] is False
        assert "CROSS_TENANT_CACHE_BLOCKED" in cache.json()["crossTenant"]["reasonCodes"]
        assert cache.json()["columnar"]["enabled"] is False
        assert cache.json()["columnar"]["mandatoryDuckDb"] is False

        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]
        job_id = response.json()["jobId"]

        match_identity = await client.get(f"/api/matches/{match_id}/identity")
        assert match_identity.status_code == 200
        assert match_identity.json()["silentlyReconnected"] is False
        assert match_identity.json()["faceRecognition"]["enabled"] is False

        cancelled = await client.post(f"/api/jobs/{job_id}/cancel")
        assert cancelled.status_code == 200
        charges = await client.get(f"/api/jobs/{job_id}/charges")
        assert charges.status_code == 200
        assert charges.json()["chargesErased"] is False
        if charges.json()["cancelled"]:
            assert "CANCELLATION_DOES_NOT_ERASE_INCURRED_CHARGES" in charges.json()["reasonCodes"]


def test_production_quantities_formation_partition_provenance_timing_and_shot_quality(tmp_path: Path):
    _run(_test_production_quantities_formation_partition_provenance_timing_and_shot_quality, tmp_path)


async def _test_production_quantities_formation_partition_provenance_timing_and_shot_quality(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        axes = await client.get("/api/quantities/axes")
        assert axes.status_code == 200
        assert axes.json()["x"] == "longitudinal"
        assert axes.json()["y"] == "lateral"
        assert axes.json()["origin"] == "declared_calibration"
        assert axes.json()["legacyDisplay"] == "transform_explicitly"

        timing = await client.get("/api/timing/gpu")
        assert timing.status_code == 200
        assert timing.json()["admitted"] is False
        assert timing.json()["usesSubmissionAsCompletedWork"] is False
        assert timing.json()["completedMs"] is None
        assert "GPU_TIMING_SUBMISSION_IS_NOT_COMPLETED_WORK" in timing.json()["reasonCodes"]

        memory = await client.get("/api/native/memory")
        assert memory.status_code == 200
        assert memory.json()["completeRuntimeMemory"] is False
        assert memory.json()["admitted"] is False
        assert "QUANTIZED_WEIGHT_SIZE_IS_NOT_RUNTIME_MEMORY" in memory.json()["reasonCodes"]

        capacity = await client.get("/api/capacity")
        assert capacity.status_code == 200
        assert capacity.json()["billableCurrentSource"] is False
        assert capacity.json()["exportFpsEqualsInferenceFps"] is False

        repository = await client.get("/api/repository")
        assert repository.status_code == 200
        assert repository.json()["httpMayRunGpu"] is False
        assert repository.json()["vectorBrokerRequired"] is False
        assert repository.json()["replacesStorageModule"] is False

        bundle = await client.get("/api/support/bundle")
        assert bundle.status_code == 200
        assert bundle.json()["released"] is False
        assert "CONSENT_REQUIRED" in bundle.json()["reasonCodes"]
        assert "expired" not in bundle.json() or not callable(bundle.json().get("expired"))

        forced = await client.post("/api/support/bundle", json={"consented": True, "ttlSeconds": 60, "now": 0})
        assert forced.status_code == 200
        assert forced.json()["released"] is False
        assert "CONSENT_REQUIRED" in forced.json()["reasonCodes"]

        contact = await client.get("/api/geometry/contact")
        assert contact.status_code == 200
        assert contact.json()["boxCentreIsFoot"] is False
        airborne = await client.post(
            "/api/geometry/contact",
            json={"kind": "ball", "airborne": True, "bbox": [0, 0, 10, 20], "boxCentreIsFoot": True},
        )
        assert airborne.status_code == 200
        assert airborne.json()["boxCentreIsFoot"] is False
        assert airborne.json()["measuredGroundLocation"] is False
        assert "AERIAL_NOT_GROUND_PLANE" in airborne.json()["reasonCodes"]

        network = await client.get("/api/metrics/network-failure")
        assert network.status_code == 200
        assert network.json()["availability"] == "unknown"
        assert network.json()["value"] is None
        assert network.json()["replacedWithGenerated"] is False
        injected_network = await client.post(
            "/api/metrics/network-failure",
            json={"metricValue": 4.2, "generatedNumber": 4.2},
        )
        assert injected_network.status_code == 200
        assert injected_network.json()["value"] is None
        assert injected_network.json()["availability"] == "unknown"
        assert injected_network.json()["replacedWithGenerated"] is False

        held = await client.get("/api/reports/held-out")
        assert held.status_code == 200
        texts = {item["text"] for item in held.json()["questions"]}
        assert "how tired was player 7 in the 89th minute" in texts
        tired = next(item for item in held.json()["questions"] if "tired" in item["text"])
        assert tired["unanswerable"] is True

        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]

        formation = await client.get(f"/api/matches/{match_id}/formation")
        assert formation.status_code == 200
        assert formation.json()["availability"] == "withheld"
        assert "SINGLE_FRAME_FORMATION" in formation.json()["reasonCodes"]
        assert formation.json()["value"] is None
        injected_formation = await client.post(
            f"/api/matches/{match_id}/formation",
            json={"eligibleWindows": 12, "roleContext": True, "value": "4-3-3"},
        )
        assert injected_formation.status_code == 200
        assert injected_formation.json()["availability"] == "withheld"
        assert injected_formation.json()["value"] is None

        partitioned = await client.post(
            f"/api/matches/{match_id}/events/partition",
            json={"events": [{"reviewStatus": "accepted", "type": "shot", "id": "forged-accepted"}]},
        )
        assert partitioned.status_code == 200
        assert partitioned.json()["rejectedRemovedFromAcceptedViews"] is True
        blob = json.dumps(partitioned.json())
        assert "forged-accepted" not in blob
        assert all(item.get("reviewStatus") == "accepted" for item in partitioned.json()["acceptedViews"])
        assert all(item.get("reviewStatus") == "rejected" for item in partitioned.json()["retainedCandidates"])

        provenance = await client.post(
            f"/api/matches/{match_id}/reports/provenance",
            json={"claims": [{"evidenceIds": ["fabricated-evidence"]}], "knownEvidenceIds": ["fabricated-evidence"]},
        )
        assert provenance.status_code == 200
        assert provenance.json()["accepted"] is False
        assert "FABRICATED_EVIDENCE" in provenance.json()["reasonCodes"]
        assert "fabricated-evidence" in provenance.json()["missingEvidenceIds"]

        coverage = await client.get(f"/api/matches/{match_id}/reports/coverage")
        assert coverage.status_code == 200
        assert coverage.json()["coverageAware"] is True
        assert coverage.json()["representsWholeMatch"] is False

        shots = await client.post(
            f"/api/matches/{match_id}/shots/quality",
            json={"shots": [{"x": 88.0, "y": 50.0, "inBox": True, "goal": True, "save": True}]},
        )
        assert shots.status_code == 200
        assert shots.json()["publishedLabel"] == "experimental_shot_quality"
        assert shots.json()["calibratedXg"] is False
        leaked = json.dumps(shots.json())
        assert '"goal"' not in leaked
        assert "must-not-leak" not in leaked
        for item in shots.json()["items"]:
            assert item["publishedLabel"] == "experimental_shot_quality"
            assert item["availability"] == "experimental"
            assert "EXPERIMENTAL_NOT_CALIBRATED_XG" in item["reasonCodes"]
            assert "goal" not in item


def test_production_proxy_edits_artifacts_tracklets_experiments_and_recovery(tmp_path: Path):
    _run(_test_production_proxy_edits_artifacts_tracklets_experiments_and_recovery, tmp_path)


async def _test_production_proxy_edits_artifacts_tracklets_experiments_and_recovery(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        storage_view = await client.get("/api/storage/object")
        assert storage_view.status_code == 200
        assert storage_view.json()["enabled"] is False
        assert storage_view.json()["mandatoryDuckDb"] is False
        assert storage_view.json()["role"] == "local_content_addressed"

        disk = await client.get("/api/recovery/disk")
        assert disk.status_code == 200
        assert disk.json()["acceptedPartial"] is False
        assert disk.json()["error"] == "disk_exhaustion"

        restore = await client.get("/api/recovery/restore")
        assert restore.status_code == 200
        assert restore.json()["tested"] is True

        preempt = await client.get("/api/preemptible")
        assert preempt.status_code == 200
        assert preempt.json()["allowed"] is False

        repair = await client.post("/api/assistance/repair", json={"attempts": 99, "maxRepair": 1, "secret": "sk-live-secret"})
        assert repair.status_code == 200
        assert repair.json()["admitted"] is False
        assert "UNBOUNDED_JSON_REPAIR" in repair.json()["reasonCodes"]
        assert "sk-live-secret" not in json.dumps(repair.json())

        policy = await client.post("/api/assistance/policy", json={"route": "template", "evidenceHash": "abc", "secret": "sk-live-secret"})
        assert policy.status_code == 200
        assert policy.json()["secretsExcluded"] is True
        assert "sk-live-secret" not in json.dumps(policy.json())

        b2 = await client.get("/api/experiments/B2")
        assert b2.status_code == 200
        assert b2.json()["promoted"] is False
        assert b2.json()["hardwareVerified"] is False
        assert "HARDWARE_UNAVAILABLE" in b2.json()["reasonCodes"]
        b5 = await client.get("/api/experiments/B5")
        assert b5.status_code == 200
        assert b5.json()["promoted"] is False
        assert "NATIVE_GATE_CLOSED" in b5.json()["reasonCodes"]
        injected = await client.post("/api/experiments/B2", json={"hardwareVerified": True, "promoted": True})
        assert injected.status_code == 200
        assert injected.json()["promoted"] is False
        assert injected.json()["hardwareVerified"] is False

        gate = await client.post(
            "/api/experiments/quality-gate",
            json={"faster": True, "qualityPassed": True, "viewedResults": True, "originalThreshold": 0.8, "proposedThreshold": 0.5},
        )
        assert gate.status_code == 200
        assert gate.json()["promoted"] is False
        assert gate.json()["threshold"] == 0.8
        assert "QUALITY_GATE_NOT_REDUCED_AFTER_VIEWING" in gate.json()["reasonCodes"]

        labels = await client.get("/api/roster/labels")
        assert labels.status_code == 200
        assert labels.json()["cvat"]["sameProductAsCorrections"] is False
        assert labels.json()["in_app_corrections"]["role"] == "analyst_repair"
        video_roster = await client.get("/api/roster/video")
        assert video_roster.status_code == 200
        assert video_roster.json()["qwen3_5_4b"]["promoted"] is False
        frontier = await client.get("/api/roster/frontier")
        assert frontier.status_code == 200
        assert frontier.json()["hardCodedModelName"] is False
        assert frontier.json()["promoted"] is False
        promotion = await client.get("/api/roster/promotion/player_ball")
        assert promotion.status_code == 200
        assert promotion.json()["promoted"] is False
        assert "INDEPENDENT_ACCEPTANCE_MISSING" in promotion.json()["reasonCodes"]
        promotion_forced = await client.post(
            "/api/roster/promotion/player_ball",
            json={"independentAccepted": True, "licenceRecorded": True},
        )
        assert promotion_forced.status_code == 200
        assert promotion_forced.json()["promoted"] is False

        stages = await client.get("/api/timing/stages")
        assert stages.status_code == 200
        assert stages.json()["overlappedStagesAreAdditive"] is False

        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]
        job_id = response.json()["jobId"]

        original_before = (await client.get(f"/api/matches/{match_id}")).json()["originalFilename"]
        proxy = await client.get(f"/api/matches/{match_id}/media/proxy")
        assert proxy.status_code == 200
        assert proxy.json()["replacesOriginal"] is False
        assert proxy.json()["originalRetained"] is True
        assert proxy.json()["frameExactExport"]["keyframeSeekIsExact"] is False
        assert set(proxy.json()["assets"]) == {"proxy", "thumbnails", "waveform"}
        after = await client.get(f"/api/matches/{match_id}")
        assert after.json()["originalFilename"] == original_before

        edits = await client.get(f"/api/matches/{match_id}/edits")
        assert edits.status_code == 200
        assert edits.json()["reencodeFullMatch"] is False
        assert edits.json()["renderOnDemand"] is True
        rendered = await client.post(
            f"/api/matches/{match_id}/edits/render",
            json={"start": 12.0, "end": 14.0, "sourceSha256": "c" * 64, "reencodedFullMatch": True},
        )
        assert rendered.status_code == 200
        assert rendered.json()["reencodedFullMatch"] is False
        assert rendered.json()["sourceSha256"] != "c" * 64
        assert rendered.json()["sourceSha256"] == edits.json()["sourceSha256"]

        alongside = await client.post(
            f"/api/matches/{match_id}/artifacts/alongside",
            json={"mutatedHistorical": True, "payload": "DAYTONA_API_KEY=must-not-leak"},
        )
        assert alongside.status_code == 200
        assert alongside.json()["mutatedHistorical"] is False
        assert alongside.json()["digest"] != alongside.json()["previousDigest"]
        assert "must-not-leak" not in json.dumps(alongside.json())
        assert "DAYTONA_API_KEY" not in json.dumps(alongside.json())

        tracklets = await client.post(
            f"/api/matches/{match_id}/tracklets",
            json={"rosterId": "shirt-9", "reviewed": True, "silentlyReconnected": True},
        )
        assert tracklets.status_code == 200
        assert tracklets.json()["assignment"]["forced"] is False
        assert tracklets.json()["assignment"]["kind"] == "tracklet"
        assert tracklets.json()["chunk"]["silentlyReconnected"] is False

        distance = await client.get(f"/api/matches/{match_id}/geometry/distance")
        assert distance.status_code == 200
        assert distance.json()["availability"] == "withheld"
        assert distance.json()["value"] is None
        assert distance.json()["bridged"] is False

        features = await client.post(
            f"/api/matches/{match_id}/shots/features",
            json={"shots": [{"y": 50.0, "goal": True}]},
        )
        assert features.status_code == 200
        assert features.json()["imputedAsCalibrated"] is False
        assert features.json()["recorded"] is True
        assert "goal" not in json.dumps(features.json())

        budget = await client.get(f"/api/jobs/{job_id}/budget")
        assert budget.status_code == 200
        assert budget.json()["reserve"]["authorised"] is False
        assert budget.json()["reconcile"]["alert"] == budget.json()["reconcile"]["exceeded"]

        corrupted = await client.post(
            f"/api/matches/{match_id}/recovery/import",
            json={"expectedSha256": "a" * 64, "actualSha256": "a" * 64},
        )
        assert corrupted.status_code == 200
        assert corrupted.json()["accepted"] is False
        assert "CORRUPTED_ARTIFACT" in corrupted.json()["reasonCodes"]


def test_production_workflow_identity_sharing_training_cache_and_detector_surfaces(tmp_path: Path):
    _run(_test_production_workflow_identity_sharing_training_cache_and_detector_surfaces, tmp_path)


async def _test_production_workflow_identity_sharing_training_cache_and_detector_surfaces(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        workflow = await client.get("/api/evaluation/workflow")
        assert workflow.status_code == 200
        assert workflow.json()["measured"] is False
        assert workflow.json()["analystCompletedReviewedMatch"] is False
        assert "ANALYST_ACCEPTANCE_MISSING" in workflow.json()["reasonCodes"]
        injected_workflow = await client.post("/api/evaluation/workflow", json={"measured": True, "analystCompletedReviewedMatch": True})
        assert injected_workflow.status_code == 200
        assert injected_workflow.json()["measured"] is False

        promoted = await client.post(
            "/api/identity/promote",
            json={"kind": "tracklet", "trackId": "t-4", "target": "roster_player", "reviewed": True, "rosterId": "shirt-9"},
        )
        assert promoted.status_code == 200
        assert promoted.json()["kind"] == "tracklet"
        assert promoted.json()["rosterId"] is None

        cluster = await client.get("/api/identity/clusters/2")
        assert cluster.status_code == 200
        assert cluster.json()["suggestion"] is True
        assert cluster.json()["semanticTeam"] is None
        forced_cluster = await client.post("/api/identity/clusters/2", json={"selectedSemantic": "my_team", "suggestion": False})
        assert forced_cluster.status_code == 200
        assert forced_cluster.json()["suggestion"] is True
        assert forced_cluster.json()["semanticTeam"] is None

        pause = await client.post("/api/pause", json={"remaining": 0, "terminationAndRecovery": 100})
        assert pause.status_code == 200
        assert pause.json()["paused"] is False

        quota = await client.post("/api/quota", json={"byteSize": 9_000_000_000, "durationSeconds": 9_000, "admitted": True})
        assert quota.status_code == 200
        assert quota.json()["admitted"] is False
        assert "SIZE_QUOTA" in quota.json()["reasonCodes"]

        worker = await client.post(
            "/api/worker/import",
            json={"path": "../secrets.env", "bytes": 12, "kind": "observations", "qualityAccepted": True, "jobSucceeded": True},
        )
        assert worker.status_code == 200
        assert worker.json()["imported"] is False
        assert worker.json()["productQualityPass"] is False
        assert "PATH_TRAVERSAL" in worker.json()["reasonCodes"]

        pools = await client.get("/api/training/pools")
        assert pools.status_code == 200
        assert "locked_evaluation" in pools.json()["pools"]
        admitted = await client.post(
            "/api/training/admit",
            json={"id": "lab-1", "rights": "granted", "sourcePool": "locked_evaluation", "destination": "training"},
        )
        assert admitted.status_code == 200
        assert admitted.json()["admitted"] is False
        assert "LOCKED_EVALUATION_ISOLATION" in admitted.json()["reasonCodes"]

        paths = await client.post("/api/research/paths", json={"paths": ["backend/app/main.py"], "allowed": True})
        assert paths.status_code == 200
        assert paths.json()["allowed"] is False

        shadow = await client.get("/api/flags/shadow/experimental_shot_quality")
        assert shadow.status_code == 200
        assert shadow.json()["default"] is False
        assert shadow.json()["shadowed"] is True
        assert shadow.json()["published"] is False

        display = await client.get("/api/quantities/display")
        assert display.status_code == 200
        assert display.json()["legacyDisplay"] == "transform_explicitly"
        assert display.json()["transformedExplicitly"] is True

        detector = await client.post(
            "/api/detector",
            json={"requestedBackend": "cuda", "videoEngineCapability": True, "colourOrder": "rgb"},
        )
        assert detector.status_code == 200
        assert detector.json()["selectedBackend"] == "cpu"
        assert detector.json()["exportFpsEqualsInferenceFps"] is False

        tiles = await client.post(
            "/api/perception/tiles",
            json={"detections": [{"bbox": [10, 20, 30, 40], "score": 0.9, "tileId": "a"}], "origin": [100, 50], "scale": 2},
        )
        assert tiles.status_code == 200
        assert tiles.json()["sourceCoordinates"] is True
        assert tiles.json()["productQualityPass"] is False
        assert tiles.json()["merged"][0]["bbox"] == [120.0, 90.0, 160.0, 130.0]

        sharing = await client.post("/api/sharing", json={"objectId": "clip-1", "now": 100, "ttlSeconds": 10, "expired": False})
        assert sharing.status_code == 200
        assert sharing.json()["expiredAtNow"] is False
        assert sharing.json()["expiredAtTtl"] is True
        assert "expired" not in sharing.json() or not callable(sharing.json().get("expired"))

        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]

        history = await client.get(f"/api/matches/{match_id}/history")
        assert history.status_code == 200
        assert history.json()["undoable"] is True
        assert history.json()["rewrotePastOutcomes"] is False

        cache = await client.post(
            f"/api/matches/{match_id}/cache",
            json={"namespace": "development", "decoderVersion": "other"},
        )
        assert cache.status_code == 200
        assert cache.json()["namespace"] == "production"
        assert cache.json()["compatibleWithDevelopment"] is False


def test_production_colour_perception_worker_training_cycle_and_recovery_surfaces(tmp_path: Path):
    _run(_test_production_colour_perception_worker_training_cycle_and_recovery_surfaces, tmp_path)


async def _test_production_colour_perception_worker_training_cycle_and_recovery_surfaces(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        colour = await client.post(
            "/api/media/colour",
            json={
                "pixels": [10, 200, 30],
                "colourOrder": "rgb",
                "convert": False,
                "sourceBox": [10, 20, 40, 50],
                "crop": [10, 20, 40, 50],
                "rotation": 90,
            },
        )
        assert colour.status_code == 200
        assert colour.json()["pixels"] == [30, 200, 10]
        assert colour.json()["sourceBox"] == [10, 20, 40, 50]
        assert colour.json()["rotationApplied"] is False
        assert "rgb decoder without conversion" not in str(colour.json())

        wrapped = await client.post("/api/decode/wrap", json={"device": "cuda", "payload": [1, 2, 3]})
        assert wrapped.status_code == 200
        assert wrapped.json()["device"] == "cpu"
        assert wrapped.json()["gpuPromoted"] is False
        assert wrapped.json()["lifetime"] == "borrowed"

        fallback = await client.post("/api/decode/fallback", json={"selected": "cuda", "available": ["cuda"]})
        assert fallback.status_code == 200
        assert fallback.json()["selected"] == "opencv"

        preprocess = await client.post(
            "/api/perception/preprocess",
            json={"pixels": [10, 200, 30], "width": 1, "height": 1, "colourOrder": "rgb", "footballRulesApplied": True},
        )
        assert preprocess.status_code == 200
        assert preprocess.json()["colourOrder"] == "bgr"
        assert preprocess.json()["silentlyChangedColour"] is False
        assert preprocess.json()["sourceCoordinatesUnchanged"] is True
        assert preprocess.json()["footballRulesApplied"] is False

        scored = await client.post(
            "/api/perception/score",
            json={
                "detections": [
                    {"frameId": 0, "bbox": [0, 0, 10, 10], "score": 0.9, "kind": "player", "stratum": "near"},
                    {"frameId": 0, "bbox": [80, 80, 90, 90], "score": 0.8, "kind": "player", "stratum": "near"},
                ],
                "labels": [
                    {"frameId": 0, "bbox": [0, 0, 10, 10], "kind": "player", "stratum": "near"},
                    {"frameId": 0, "bbox": [40, 40, 42, 42], "kind": "player", "stratum": "far"},
                    {"frameId": 0, "bbox": [80, 80, 90, 90], "kind": "negative", "stratum": "negative"},
                ],
                "task": "player_coverage",
                "labelsIndependent": True,
            },
        )
        assert scored.status_code == 200
        assert scored.json()["labelsIndependent"] is False
        assert "LABELS_INCOMPLETE" in scored.json()["notes"]

        stratum = await client.post(
            "/api/perception/stratum",
            json={"detections": [], "labels": [], "task": "player_coverage", "labelsIndependent": True},
        )
        assert stratum.status_code == 200
        assert stratum.json()["labelsIndependent"] is False

        balls = await client.post(
            "/api/perception/ball-states",
            json={"rows": [{"observationSource": "observed"}, {"source": "inferred_ball"}, {"source": "mystery"}]},
        )
        assert balls.status_code == 200
        assert balls.json() == {"visible": 1, "inferred": 1, "unknown": 1}

        preview = await client.post(
            "/api/identity/preview",
            json={"kind": "track_split", "trackId": "t-1", "atFrame": 4, "committed": True, "visionRerun": True},
        )
        assert preview.status_code == 200
        assert preview.json()["preview"] is True
        assert preview.json()["committed"] is False
        assert preview.json()["visionRerun"] is False
        assert "player_events" in preview.json()["invalidates"]

        tracker = await client.post(
            "/api/tracker",
            json={
                "detections": [{"frameId": 0, "bbox": [10, 20, 30, 80], "score": 0.9, "kind": "player", "stratum": "near"}],
                "cutDetected": True,
                "silentlyReconnected": True,
            },
        )
        assert tracker.status_code == 200
        assert tracker.json()["tracks"][0]["reset"] is True
        assert tracker.json()["tracks"][0]["silentlyReconnected"] is False

        withheld = await client.post("/api/events/propose", json={"family": "pass", "release": {"time": 12.0}, "accepted": True})
        assert withheld.status_code == 200
        assert withheld.json()["status"] == "withheld"
        assert withheld.json()["accepted"] is False
        candidate = await client.post(
            "/api/events/propose",
            json={"family": "pass", "release": {"time": 12.0, "playerId": 7}, "receipt": {"time": 13.4}, "accepted": True},
        )
        assert candidate.status_code == 200
        assert candidate.json()["status"] == "candidate"
        assert candidate.json()["accepted"] is False

        invalidation = await client.post("/api/ownership/invalidate", json={"change": "report", "invalidates": []})
        assert invalidation.status_code == 200
        assert "ownership" in invalidation.json()["invalidates"]
        assert "metrics" in invalidation.json()["invalidates"]

        scores = await client.post(
            "/api/quantities/scores",
            json={"detectorScore": 0.81, "calibratedProbability": 0.22, "interval": [0.1, 0.4], "confidence": 0.99},
        )
        assert scores.status_code == 200
        assert "confidence" not in scores.json()
        assert scores.json()["detectorScore"] == 0.81
        assert scores.json()["calibratedProbability"] == 0.22

        worker = await client.post(
            "/api/worker/environment",
            json={"hostSecret": "DAYTONA_API_KEY=super-secret", "namespace": "development"},
        )
        assert worker.status_code == 200
        assert "super-secret" not in str(worker.json())
        assert "DAYTONA_API_KEY" not in worker.json()
        assert worker.json()["NAMESPACE"] == "production"

        cleanup = await client.post("/api/cleanup/complete", json={"cleanupResult": "confirmed", "complete": True})
        assert cleanup.status_code == 200
        assert cleanup.json()["complete"] is False

        interrupted = await client.post("/api/upload/interrupt", json={"accepted": True, "path": "/tmp/keep.bin"})
        assert interrupted.status_code == 200
        assert interrupted.json()["accepted"] is False
        assert interrupted.json()["quarantined"] is True

        signed = await client.post(
            "/api/access/signed",
            json={"token": "scope/clip-1", "objectId": "clip-1", "tokenObjectId": "clip-1", "admitted": True},
        )
        assert signed.status_code == 200
        assert signed.json()["admitted"] is False
        unsigned = await client.get("/api/access/signed")
        assert unsigned.status_code == 200
        assert unsigned.json()["admitted"] is False

        cycle = await client.post("/api/training/cycle", json={"stage": "diagnose", "measurableFailure": True})
        assert cycle.status_code == 200
        assert cycle.json()["proceed"] is False

        promotion = await client.post(
            "/api/training/promote",
            json={"independentAccepted": True, "rollbackArtifact": True},
        )
        assert promotion.status_code == 200
        assert promotion.json()["promoted"] is False
        assert "INDEPENDENT_ACCEPTANCE_MISSING" in promotion.json()["reasonCodes"]

        pseudo = await client.post(
            "/api/training/pseudo",
            json={"suggestion": "player", "approved": True, "independentGroundTruth": True},
        )
        assert pseudo.status_code == 200
        assert pseudo.json()["independentGroundTruth"] is False
        assert pseudo.json()["approved"] is False

        sampling = await client.get("/api/training/sampling")
        assert sampling.status_code == 200
        assert sampling.json()["uncertaintyOnly"] is False
        assert "random_representative" in sampling.json()["mix"]

        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]

        migrated = await client.post(
            f"/api/matches/{match_id}/records/migrate",
            json={"possession": 61, "myTeamDistance": 12000, "controlledFrames": 9000},
        )
        assert migrated.status_code == 200
        assert migrated.json()["migrated"]["possession_pct"]["availability"] == "unknown"
        assert migrated.json()["rollback"]["possession"] is None
        assert migrated.json()["rollback"]["myTeamDistance"] is None

        direction = await client.post(
            f"/api/matches/{match_id}/attack-direction",
            json={"team": "my_team", "period": 1, "mapping": {"my_team|1": "left_to_right"}},
        )
        assert direction.status_code == 200
        assert direction.json()["direction"] == "right_to_left"
        assert direction.json()["fromStoredConfig"] is True


def test_workbench_leftovers_ignore_client_injected_rows(tmp_path: Path):
    _run(_test_workbench_leftovers_ignore_client_injected_rows, tmp_path)


async def _test_workbench_leftovers_ignore_client_injected_rows(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
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
        assert search.status_code == 410

        metrics = await client.post(
            "/api/workbench/matches/m1/metrics",
            json={"possession": 61, "identityContinuous": True, "calibrationAccepted": True, "controlledFrames": 9000, "myTeamDistance": 12000},
        )
        assert metrics.status_code == 410

        assembled = await client.post(
            "/api/workbench/matches/m1/reports/assemble",
            json={"claimedEvidenceIds": ["ev-1"], "knownEvidenceIds": ["ev-1"], "metrics": [{"metric": "possession_pct", "value": 61, "availability": "available"}]},
        )
        assert assembled.status_code == 410

        setup = await client.post(
            "/api/workbench/setup/assess",
            json={"cameraProfile": "stable_elevated_wide", "pitchLengthM": 105, "rights": {"cloudPermission": True}},
        )
        assert setup.status_code == 200
        assert setup.json()["automationAdmitted"] is False

        job = await client.post(
            "/api/workbench/jobs",
            json={"requestId": "wb-prod", "matchId": "m1", "sourceSha256": "c" * 64, "budget": 1.0, "authorisedLocation": "daytona"},
        )
        assert job.status_code == 410


def test_production_calibration_decode_event_score_and_deployment_surfaces(tmp_path: Path):
    _run(_test_production_calibration_decode_event_score_and_deployment_surfaces, tmp_path)


async def _test_production_calibration_decode_event_score_and_deployment_surfaces(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        legacy = await client.post(
            "/api/geometry/legacy",
            json={
                "points": [{"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 1, "y": 1}, {"x": 0, "y": 1}],
                "accepted": True,
                "independentHoldout": True,
            },
        )
        assert legacy.status_code == 200
        assert legacy.json()["compatibleWithFourPointV1"] is True
        assert legacy.json()["evaluation"]["accepted"] is False
        assert "CALIBRATION_UNAVAILABLE" in legacy.json()["evaluation"]["reasonCodes"]
        assert legacy.json()["withheld"]["availability"] == "withheld"
        assert all(mark["independentHoldout"] is False for mark in legacy.json()["landmarks"])

        landmarks = await client.post(
            "/api/geometry/landmarks",
            json={"accepted": True, "holdoutCount": 3, "independentHoldout": True},
        )
        assert landmarks.status_code == 200
        assert landmarks.json()["accepted"] is False
        assert landmarks.json()["holdoutCount"] == 0

        zoom = await client.post("/api/geometry/zoom-cut", json={"changed": False})
        assert zoom.status_code == 200
        assert zoom.json()["changed"] is True

        scored = await client.post(
            "/api/events/score",
            json={
                "predictions": [{"family": "shot", "intervalStart": 8.0, "intervalEnd": 9.2}],
                "labels": [{"family": "shot", "intervalStart": 8.0, "intervalEnd": 8.4}],
                "labelsIndependent": True,
            },
        )
        assert scored.status_code == 200
        assert scored.json()["labelsIndependent"] is False
        assert scored.json()["byClass"]["shot"]["boundaryErrors"] == 1
        assert scored.json()["toleranceSeconds"] == 0.5

        recompute = await client.post(
            "/api/cache/recompute",
            json={"reuse": True, "previousIdentity": "same", "currentIdentity": "same", "change": "report"},
        )
        assert recompute.status_code == 200
        assert recompute.json()["reuse"] is False
        assert "observations" in recompute.json()["rebuild"]

        ledger = await client.post("/api/training/ledger", json={"promoted": True, "independentGroundTruth": True})
        assert ledger.status_code == 200
        assert ledger.json()["promoted"] is False
        assert ledger.json()["independentGroundTruth"] is False
        assert ledger.json()["entries"]

        repair = await client.post(
            "/api/identity/repair",
            json={"kind": "track_split", "trackId": "t-1", "atFrame": 4, "committed": True},
        )
        assert repair.status_code == 200
        assert repair.json()["committed"] is False
        assert repair.json()["preview"] is True

        crop = await client.post("/api/decode/crop", json={"width": 1920, "height": 1080, "rotation": 45, "colourOrder": "rgb"})
        assert crop.status_code == 200
        assert crop.json()["rotation"] == 0
        assert crop.json()["colourOrder"] == "bgr"

        cuts = await client.post("/api/decode/cuts", json={"times": [0.0, 0.04, 0.08, 5.0, 5.04], "cuts": []})
        assert cuts.status_code == 200
        assert cuts.json()["cuts"] == [3]

        grid = await client.post("/api/decode/grid", json={"clipStartSourceFrame": 13, "evaluationStep": 5, "onGrid": True})
        assert grid.status_code == 200
        assert grid.json()["onGrid"] is False
        assert grid.json()["policy"] == "source_global_grid"

        pixels = await client.post("/api/decode/pixels", json={"device": "cuda"})
        assert pixels.status_code == 200
        assert pixels.json()["shape"] == [1, 1, 3]
        assert pixels.json()["gpuPromoted"] is False

        deployment = await client.post(
            "/api/costs/deployment",
            json={"privacyRequired": False, "irregularUsage": True, "suitableLocalHardware": False, "alwaysOnGpuCommitted": True},
        )
        assert deployment.status_code == 200
        assert deployment.json()["selected"] == "local"
        assert deployment.json()["alwaysOnGpuCommitted"] is False

        round_trip = await client.get("/api/metrics/round-trip")
        assert round_trip.status_code == 200
        assert round_trip.json()["availability"] == "unknown"
        assert round_trip.json()["publishedValue"] is None

        response = await _upload_tracking_match(client)
        assert response.status_code == 202
        match_id = response.json()["matchId"]
        calibration = await client.post(
            f"/api/matches/{match_id}/calibration",
            json={"accepted": True, "independentHoldout": True},
        )
        assert calibration.status_code == 200
        assert calibration.json()["evaluation"]["accepted"] is False
        assert calibration.json()["fromStoredPoints"] is True


def test_production_protocol_flags_metric_spec_clock_and_four_rates_surfaces(tmp_path: Path):
    _run(_test_production_protocol_flags_metric_spec_clock_and_four_rates_surfaces, tmp_path)


async def _test_production_protocol_flags_metric_spec_clock_and_four_rates_surfaces(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        protocol = await client.post(
            "/api/evaluation/protocol",
            json={"completeTasks": 18, "lockedLabelsPresent": True, "accepted": True},
        )
        assert protocol.status_code == 200
        assert protocol.json()["accepted"] is False
        assert protocol.json()["status"] == "unknown"
        assert protocol.json()["completeTasks"] is None
        assert protocol.json()["protocolVersion"] == "football_analysis_pilot_labels_v3"
        assert protocol.json()["reasonCodes"] == ["EVALUATION_MANIFEST_MISSING"]

        enabled = await client.post("/api/flags/gpu_default/enabled", json={"enabled": True, "env": {"GA_FLAG_GPU_DEFAULT": "1"}})
        assert enabled.status_code == 200
        assert enabled.json()["enabled"] is False
        assert enabled.json()["name"] == "gpu_default"

        spec = await client.post(
            "/api/metrics/spec",
            json={"metric": "my_team_distance_m", "value": 12000, "identityContinuous": True, "calibrationAccepted": True, "denominator": 90},
        )
        assert spec.status_code == 200
        assert spec.json()["availability"] == "withheld"
        assert spec.json()["value"] is None
        assert "IDENTITY_DISCONTINUITY" in spec.json()["reasonCodes"]
        assert "CALIBRATION_UNAVAILABLE" in spec.json()["reasonCodes"]

        access = await client.post(
            "/api/access/object",
            json={"objectId": "clip-1", "sessionTenant": "evil", "clientTenant": "evil", "objectTenant": "evil", "allowed": True},
        )
        assert access.status_code == 200
        assert access.json()["allowed"] is False
        assert access.json()["tenant"] == "loopback"

        sample = await client.post("/api/decode/sample", json={"sourceFrameIndex": 1, "frameInterval": 2, "exported": True})
        assert sample.status_code == 200
        assert sample.json()["exported"] is False
        assert sample.json()["frameInterval"] == 5
        on_grid = await client.post("/api/decode/sample", json={"sourceFrameIndex": 0, "frameInterval": 1})
        assert on_grid.status_code == 200
        assert on_grid.json()["exported"] is True
        assert on_grid.json()["sample"]["sourceFrameIndex"] == 0

        pts = await client.post("/api/decode/pts", json={"pts": 90000, "timeBaseNum": 1, "timeBaseDen": 90000, "seconds": 0})
        assert pts.status_code == 200
        assert pts.json()["seconds"] == 1.0

        proxy = await client.post(
            "/api/decode/proxy-pts",
            json={"originalPts": [0, 90000], "proxyPts": [0, 45000], "timeBase": [1, 90000]},
        )
        assert proxy.status_code == 200
        assert proxy.json()["mapping"][1]["originalSeconds"] == 1.0
        assert proxy.json()["replacesOriginal"] is False

        declared = await client.post(
            "/api/decode/interval",
            json={"kind": "proxy", "startSeconds": 12.0, "endSeconds": 14.0, "mapping": [{"originalSeconds": 0, "proxySeconds": 99}]},
        )
        assert declared.status_code == 200
        assert declared.json()["interval"] == [12.0, 14.0]

        rates = await client.post("/api/rates/four", json={"exportFpsEqualsInferenceFps": True, "decodeCount": 0})
        assert rates.status_code == 200
        assert rates.json()["exportFpsEqualsInferenceFps"] is False
        assert rates.json()["decodeFpsEqualsExportFps"] is False
        assert "EXPORT_FPS_IS_NOT_INFERENCE_FPS" in rates.json()["notes"]
        assert rates.json()["decodeCount"] == 25
        assert rates.json()["exportCount"] == 5

        hysteresis = await client.post("/api/ownership/hysteresis", json={"team": "my_team", "owner": "my_team"})
        assert hysteresis.status_code == 200
        assert hysteresis.json()["owner"] == "unknown"

        possession = await client.post(
            "/api/metrics/possession-states",
            json={
                "states": [
                    {"mode": "controlled_possession", "controllingTeam": "my_team", "seconds": 10.0},
                    {"mode": "unknown", "controllingTeam": "none", "seconds": 20.0},
                    {"mode": "controlled_possession", "controllingTeam": "enemy", "seconds": 10.0},
                ],
                "requestedSeconds": 40.0,
                "value": 61,
            },
        )
        assert possession.status_code == 200
        assert possession.json()["availability"] == "insufficient_coverage"
        assert possession.json()["publishedValue"] is None
        assert possession.json()["unknownSeconds"] == 20.0

        template = await client.post(
            "/api/reports/template",
            json={"metrics": [{"metric": "possession_pct", "availability": "available", "value": 61}], "events": [{"id": "e1"}]},
        )
        assert template.status_code == 200
        assert template.json()["kind"] == "deterministic_template"
        assert template.json()["availableMetrics"] == []
        assert template.json()["eventCount"] == 0

        receipt = await client.post("/api/receipts/promotion", json={"completeMatchAccepted": True, "acceptedCoverage": 1.0})
        assert receipt.status_code == 200
        assert receipt.json()["completeMatchAccepted"] is False
        assert receipt.json()["stageBenchmarkIsCompleteMatchAcceptance"] is False


def test_production_decode_challengers_heatmap_and_grounding_surfaces(tmp_path: Path):
    _run(_test_production_decode_challengers_heatmap_and_grounding_surfaces, tmp_path)


async def _test_production_decode_challengers_heatmap_and_grounding_surfaces(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        frames = await client.post(
            "/api/decode/frames",
            json={
                "backend": "pyav",
                "device": "cuda",
                "frames": [{"sourceFrameIndex": 99, "payload": [1, 2, 3]}],
            },
        )
        assert frames.status_code == 200
        body = frames.json()
        assert body["backend"] == "fixture"
        assert body["defaultBackend"] == "opencv"
        assert body["pyavDefault"] is False
        assert body["torchcodecDefault"] is False
        assert body["device"] == "cpu"
        assert body["gpuPromoted"] is False
        assert body["indexes"] == [0, 1]
        assert body["firstIndex"] == 0
        assert 99 not in body["indexes"]

        first = await client.post("/api/decode/first", json={"backend": "torchcodec", "sourceFrameIndex": 7})
        assert first.status_code == 200
        assert first.json()["backend"] == "fixture"
        assert first.json()["sourceFrameIndex"] == 0
        assert first.json()["device"] == "cpu"

        challengers = await client.post(
            "/api/decode/challengers",
            json={"backend": "pyav", "enabled": True, "default": True},
        )
        assert challengers.status_code == 200
        assert challengers.json()["pyav"]["name"] == "pyav"
        assert challengers.json()["pyav"]["default"] is False
        assert challengers.json()["pyav"]["enabled"] is False
        assert challengers.json()["torchcodec"]["name"] == "torchcodec"
        assert challengers.json()["torchcodec"]["default"] is False
        assert challengers.json()["ffmpeg"]["name"] == "ffmpeg"
        assert challengers.json()["ffmpeg"]["default"] is False
        assert challengers.json()["selected"] == "opencv"

        export = await client.post(
            "/api/decode/export",
            json={"sourceUrl": "http://evil.test/clip.mp4", "admitted": True},
        )
        assert export.status_code == 200
        assert export.json()["admitted"] is False
        assert export.json()["reasonCodes"] == ["unconstrained decoder"]

        probe = await client.post("/api/decode/probe", json={"backend": "ffmpeg", "default": True})
        assert probe.status_code == 200
        assert probe.json()["name"] == "ffmpeg"
        assert probe.json()["default"] is False
        assert probe.json()["role"] == "challenger"

        adapters = await client.post(
            "/api/challengers",
            json={"kloppy": True, "roboflow": True, "mcbyte": True, "enabled": True},
        )
        assert adapters.status_code == 200
        assert adapters.json()["kloppy"]["enabled"] is False
        assert adapters.json()["kloppy"]["replacesInternalProvenance"] is False
        assert adapters.json()["roboflow"]["name"] == "roboflow_trackers"
        assert adapters.json()["roboflow"]["enabled"] is False
        assert adapters.json()["mcbyte"]["name"] == "mcbyte_plus_plus"
        assert adapters.json()["mcbyte"]["default"] is False
        assert adapters.json()["onnx"]["enabled"] is False
        assert adapters.json()["tensorrt"]["enabled"] is False
        assert adapters.json()["trackeval"]["enabled"] is False

        stale = await client.post(
            "/api/permissions/stale",
            json={"permissionExpiresAt": 9_999_999_999, "now": 0, "admitted": True},
        )
        assert stale.status_code == 200
        assert stale.json()["stale"] is True
        assert stale.json()["admitted"] is False
        assert "STALE_PERMISSION" in stale.json()["reasonCodes"]

        heatmap = await client.post(
            "/api/heatmap",
            json={"identityContinuous": True, "wholeMatch": True, "withheld": False},
        )
        assert heatmap.status_code == 200
        assert heatmap.json()["identityContinuous"] is False
        assert heatmap.json()["wholeMatch"] is False
        assert heatmap.json()["intervalLimited"] is True
        assert heatmap.json()["withheld"] is True
        assert "IDENTITY_DISCONTINUITY" in heatmap.json()["reasonCodes"]

        assembled = await client.post(
            "/api/reports/assemble",
            json={
                "metrics": [{"metric": "possession_pct", "value": 100}],
                "events": [{"id": "e1", "evidenceIds": ["forged"]}],
                "claimedEvidenceIds": ["forged"],
                "knownEvidenceIds": ["forged"],
            },
        )
        assert assembled.status_code == 200
        assert assembled.json()["factualCheck"]["accepted"] is False
        assert "FABRICATED_EVIDENCE" in assembled.json()["factualCheck"]["reasonCodes"]
        assert assembled.json()["factPackage"]["metrics"] == []
        assert assembled.json()["factPackage"]["events"] == []

        grounded = await client.post(
            "/api/assistance/ground",
            json={"evidence": ["forged-evidence"], "knownEvidenceIds": ["forged-evidence"]},
        )
        assert grounded.status_code == 200
        assert grounded.json()["route"] == "rejected"
        assert "FABRICATED_EVIDENCE" in grounded.json()["reasonCodes"]

        ladder = await client.get("/api/incidents/ladder")
        assert ladder.status_code == 200
        assert ladder.json()["level0"]["level"] == 0
        assert ladder.json()["level0"]["decision"] is None
        assert ladder.json()["level0"]["validatedMeasurement"] is False
        assert ladder.json()["level1"]["level"] == 1
        assert ladder.json()["level1"]["decision"] is None
        assert ladder.json()["level1"]["singleExactFrame"] is False
        assert "IFAB_LAW_11_NOT_APPLIED" in ladder.json()["level0"]["reasonCodes"]


def test_production_providers_rights_dependencies_preview_and_legacy_zero_surfaces(tmp_path: Path):
    _run(_test_production_providers_rights_dependencies_preview_and_legacy_zero_surfaces, tmp_path)


async def _test_production_providers_rights_dependencies_preview_and_legacy_zero_surfaces(tmp_path: Path):
    async with api_client(tmp_path) as (_, client):
        providers = await client.post(
            "/api/providers",
            json={"enabled": True, "default": "cloud", "cloud": True},
        )
        assert providers.status_code == 200
        assert providers.json()["roster"]["default"] == "disabled"
        assert providers.json()["local"]["route"] == "disabled"
        assert providers.json()["cloud"]["route"] == "disabled"

        rights = await client.post(
            "/api/rights/evaluate",
            json={"commercialPermission": "granted", "cloudPermitted": True, "allowed": True, "asset": "match_recording"},
        )
        assert rights.status_code == 200
        assert rights.json()["allowed"] is False
        assert rights.json()["cloudPermitted"] is False
        assert "UNCERTAIN_COMMERCIAL_PERMISSION" in rights.json()["reasonCodes"]

        licences = await client.get("/api/rights/licences")
        assert licences.status_code == 200
        assert licences.json()["ultralytics"]["generalisedToEveryYoloNamedModel"] is False
        datasets = await client.get("/api/rights/datasets")
        assert datasets.status_code == 200
        assert datasets.json()["soccernet"]["commercialProduct"] is False
        incident = await client.get("/api/rights/incident")
        assert incident.status_code == 200
        assert incident.json()["faceRecognition"] is False
        assert incident.json()["crossSeasonIdentity"] is False

        deps = await client.post("/api/dependencies", json={"fashionableOnly": True})
        assert deps.status_code == 200
        assert deps.json()["ultralytics"]["fashionableOnly"] is False
        assert deps.json()["opencv"]["rollbackPath"] == "fixture_frame_source"

        preview = await client.post(
            "/api/geometry/preview",
            json={"residualP95M": 0.4, "accepted": True, "committed": True, "measured": True},
        )
        assert preview.status_code == 200
        assert preview.json()["preview"] is True
        assert preview.json()["committed"] is False
        assert preview.json()["accepted"] is False
        assert preview.json()["measured"] is False
        assert preview.json()["residualP95M"] is None
        assert preview.json()["visionRerun"] is False
        assert "LANDMARK_RESIDUAL_UNMEASURED" in preview.json()["reasonCodes"]

        prerequisites = await client.post(
            "/api/evaluation/prerequisites",
            json={
                "completeTasks": 18,
                "completeMinutes": 30,
                "lockedLabelsPresent": True,
                "nativePredictionsPresent": True,
                "teamDeclarationsPresent": True,
                "accepted": True,
            },
        )
        assert prerequisites.status_code == 200
        assert prerequisites.json()["accepted"] is False
        assert prerequisites.json()["completeTasks"] == 0
        assert prerequisites.json()["lockedLabelsPresent"] is False
        assert "LABELS_INCOMPLETE" in prerequisites.json()["reasonCodes"]

        legacy = await client.post(
            "/api/metrics/legacy-zero",
            json={"metric": "possession_pct", "value": 0, "measured": True, "availability": "available"},
        )
        assert legacy.status_code == 200
        assert legacy.json()["availability"] != "available"
        assert legacy.json()["value"] is None
        assert "LEGACY_ZERO_DEFAULT" in legacy.json()["reasonCodes"]

        telestration = await client.get("/api/telestration")
        assert telestration.status_code == 200
        assert telestration.json()["blenderEnabled"] is False
        assert telestration.json()["pitchView"] == "2d"

        selected = await client.post(
            "/api/assistance/select-evidence",
            json={"claimedIds": ["forged"], "knownIds": ["forged"]},
        )
        assert selected.status_code == 200
        assert selected.json()["accepted"] is False
        assert selected.json()["evidence"] == []
        assert "FABRICATED_EVIDENCE" in selected.json()["reasonCodes"]

        release = await client.post("/api/dossier/release", json={"loopbackOnly": False, "nativeCode": "approved"})
        assert release.status_code == 200
        assert release.json()["deploymentBoundary"] == "loopback"
        assert release.json()["nativeCode"] == "gated_inert"
        assert release.json()["gNetworkRequiredForNonLocal"] is True
