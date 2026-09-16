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
        assert analytics_payload["summary"]["possession"] == 67

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
            "backend.app.main.compute_trust_crops",
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

        def fake_run_analysis(  # noqa: ANN001
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
        ):
            captured["analysis_type"] = analysis_type
            captured["provider"] = provider
            captured["attack_direction"] = attack_direction
            captured["current_frame_index"] = current_frame_index
            captured["summary"] = summary
            captured["events"] = events
            captured["formation_timeline"] = formation_timeline
            captured["shots"] = shots
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
        assert captured["summary"].possession == 67
        assert captured["events"] is not None
        assert len(captured["events"]) >= 1
        assert captured["formation_timeline"] is not None
        assert captured["shots"] is not None
        assert isinstance(captured["shots"], list)


def test_analysis_route_persists_latest_report_payload(tmp_path: Path, monkeypatch):
    _run(_test_analysis_route_persists_latest_report_payload, tmp_path, monkeypatch)


async def _test_analysis_route_persists_latest_report_payload(tmp_path: Path, monkeypatch):
    async with api_client(tmp_path) as (app, client):
        response = await _upload_tracking_match(client)
        match_id = response.json()["matchId"]

        monkeypatch.setattr(
            "backend.app.main.run_analysis",
            lambda *args, **kwargs: {
                "summary": "Positive attacking output",
                "rating": 8,
                "attacking": "Strong wide progression",
                "defensive": "Compact block",
                "pressing": "Aggressive counterpress",
                "weaknesses": "Rest defense after turnovers",
                "key_player": 7,
            },
        )

        analysis_response = await client.post(
            f"/api/matches/{match_id}/analysis/tactical_report",
            json={"provider": "local", "currentFrameIndex": 1},
        )

        assert analysis_response.status_code == 200

        storage = app.state.storage
        assert storage.load_analysis_artifact(match_id, "tactical_report")["rating"] == 8


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
        assert "Positive attacking output" in export_response.text
        assert "Wave Press" in export_response.text


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
        assert [probe["clusterId"] for probe in benchmark_payload["selectedClusters"]] == [0, 1]
        assert benchmark_payload["recommendedCluster"]["clusterId"] == selected_cluster
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
        assert bundle["analytics"]["summary"]["possession"] == 67
        assert bundle["events"][0]["type"] == "turnover"
        assert bundle["artifactAvailability"]["frames"] is True
        assert bundle["artifactAvailability"]["analytics"] is True
        assert bundle["artifactAvailability"]["events"] is True
        assert bundle["artifactAvailability"]["acceptedMatchState"] is True
        assert bundle["provenance"]["deterministicCore"] is True
        assert bundle["exports"]["framesCsv"] == f"/api/matches/{match_id}/export/frames.csv"
        assert bundle["exports"]["eventsCsv"] == f"/api/matches/{match_id}/export/events.csv"
        assert bundle["exports"]["reportHtml"] == f"/api/matches/{match_id}/report/html"


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
        assert spoofed.json()["detail"]["sessionTenant"] == "club-b"

        admitted = await client.get(
            f"/api/matches/{match_id}/analytics",
            headers={
                "authorization": "club-a",
                "x-object-scope": match_id,
                "x-deployment-boundary": "hosted",
                "x-tenant-id": "club-b",
            },
        )
        assert admitted.status_code == 200
        assert admitted.json()["matchId"] == match_id


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
            item["evidenceId"]
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
