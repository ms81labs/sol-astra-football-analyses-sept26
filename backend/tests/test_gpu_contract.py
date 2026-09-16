import json
from contextlib import asynccontextmanager
from pathlib import Path

import anyio
import httpx

from backend.app.main import create_app

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
async def api_client(tmp_path: Path):
    storage_root = tmp_path / "storage"
    app = create_app(storage_root=storage_root, run_jobs_inline=True)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        yield client


def test_gpu_handoff_contract_exposes_upload_and_terminal_job_fields(tmp_path: Path):
    _run(_test_gpu_handoff_contract_exposes_upload_and_terminal_job_fields, tmp_path)


async def _test_gpu_handoff_contract_exposes_upload_and_terminal_job_fields(tmp_path: Path):
    async with api_client(tmp_path) as client:
        with TRACKING_FIXTURE.open("rb") as fixture_file:
            response = await client.post(
                "/api/matches",
                data={
                    "name": "Contract Match",
                    "inputMode": "tracking_json",
                    "config": json.dumps(
                        {
                            "attackDirection": "right_to_left",
                            "manualHomographyPoints": MANUAL_HOMOGRAPHY_POINTS,
                        }
                    ),
                },
                files={"file": ("sample_tracking.json", fixture_file, "application/json")},
            )

        assert response.status_code == 202
        upload_payload = response.json()
        assert set(upload_payload) == {
            "matchId",
            "jobId",
            "status",
            "admissionToken",
            "dispatchOutcome",
            "reused",
        }
        assert upload_payload["status"] == "completed"
        assert upload_payload["admissionToken"]
        assert upload_payload["dispatchOutcome"] == "started"
        assert upload_payload["reused"] is False

        job_response = await client.get(f"/api/jobs/{upload_payload['jobId']}")
        assert job_response.status_code == 200
        job_payload = job_response.json()
        assert set(job_payload) >= {
            "id",
            "matchId",
            "status",
            "progress",
            "message",
            "error",
            "logPath",
            "startedAt",
            "completedAt",
            "durationSeconds",
            "createdAt",
            "updatedAt",
        }
        assert job_payload["status"] == "completed"
        assert job_payload["logPath"].endswith(f"job_{upload_payload['jobId']}.log")
        assert job_payload["startedAt"] is not None
        assert job_payload["completedAt"] is not None
        assert job_payload["durationSeconds"] is not None


def test_gpu_handoff_contract_preserves_unresolved_team_review_fields(tmp_path: Path, monkeypatch):
    _run(_test_gpu_handoff_contract_preserves_unresolved_team_review_fields, tmp_path, monkeypatch)


async def _test_gpu_handoff_contract_preserves_unresolved_team_review_fields(tmp_path: Path, monkeypatch):
    async with api_client(tmp_path) as client:
        verified_model = _install_verified_runtime_boundary(tmp_path, monkeypatch)

        def fake_video_processor(video_path, config, **kwargs):  # noqa: ANN001
            assert Path(kwargs["model_path"]).read_bytes() == b"verified-primary-model"
            assert kwargs["model_path"] == str(verified_model)
            return {
                "rows": [
                    {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 4, "X": 51.0, "Y": 50.0, "Conf": 0.9},
                    {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 12, "X": 61.0, "Y": 50.0, "Conf": 0.9},
                    {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 52.0, "Y": 50.0, "Conf": 0.95},
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
                "name": "Contract Video Match",
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

        detail_response = await client.get(f"/api/matches/{payload['matchId']}")
        assert detail_response.status_code == 200
        detail_payload = detail_response.json()
        assert detail_payload["requiresTeamSelection"] is True
        assert isinstance(detail_payload["teamClusters"], list)
        assert len(detail_payload["teamClusters"]) == 2

        frames_response = await client.get(f"/api/matches/{payload['matchId']}/frames")
        assert frames_response.status_code == 200
        frame = frames_response.json()["frames"][0]
        assert frame["myTeam"] == []
        assert frame["enemies"] == []
        assert isinstance(frame["unassignedPlayers"], list)
        assert {player["id"] for player in frame["unassignedPlayers"]} == {4, 12}
