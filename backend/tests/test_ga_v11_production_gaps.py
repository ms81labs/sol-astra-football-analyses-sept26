"""Tests that fail on leftover stubs: clocks, ffmpeg decode, durable jobs, perception, leftover HTTP."""

from __future__ import annotations

import io
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.workbench.contracts import SourceClockIdentity
from backend.app.workbench.jobs import DurableJobLedger, JobRequest
from backend.app.workbench.media import FfmpegFrameSource, OpenCvFrameSource
from backend.app.workbench.perception import DetectorAdapter, Detection, TrackerAdapter


def _request(request_id: str = "job-restart") -> JobRequest:
    return JobRequest(
        requestId=request_id,
        matchId="match-a",
        sourceSha256="a" * 64,
        intervalStart=0.0,
        intervalEnd=12.0,
        temporalPolicy="source_global_grid",
        decoderVersion="ffmpeg",
        modelHash="weights-v1",
        outputSchema="evidence_v1",
        budget=2.5,
        authorisedLocation="local",
    )


def test_opencv_vfr_uses_decoder_pts_not_index_over_fps() -> None:
    """Plan §4.1: index/fps is not a valid presentation clock for VFR."""

    class Capture:
        CAP_PROP_FPS = 5
        CAP_PROP_POS_MSEC = 0

        def __init__(self) -> None:
            self._index = -1
            self._times_ms = [0.0, 80.0, 100.0]

        def isOpened(self) -> bool:
            return True

        def get(self, prop: int) -> float:
            if prop == self.CAP_PROP_FPS:
                return 25.0
            if prop == self.CAP_PROP_POS_MSEC:
                if self._index < 0:
                    return 0.0
                return self._times_ms[self._index]
            return 0.0

        def read(self):
            self._index += 1
            if self._index >= len(self._times_ms):
                return False, None
            image = SimpleNamespace(shape=(2, 2, 3), tobytes=lambda: b"x" * 12)
            return True, image

        def release(self) -> None:
            return None

    class Cv2:
        CAP_PROP_FPS = 5
        CAP_PROP_POS_MSEC = 0
        CAP_PROP_FRAME_WIDTH = 3
        CAP_PROP_FRAME_HEIGHT = 4
        CAP_PROP_FRAME_COUNT = 7

        @staticmethod
        def VideoCapture(_path: str) -> Capture:
            return Capture()

    frames = list(OpenCvFrameSource(cv2_module=Cv2()).iter_frames(Path("/tmp/vfr.mp4")))
    times = [frame.presentation_time_seconds for frame in frames]
    fps_shortcut = [index / 25.0 for index in range(3)]
    assert times == pytest.approx([0.0, 0.08, 0.10])
    assert times != pytest.approx(fps_shortcut)
    assert [frame.pts for frame in frames] != [0, 1, 2]


def test_ffmpeg_frame_source_decodes_the_path_instead_of_injected_frames(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"not-a-real-container-but-must-be-read")
    seen: list[list[str]] = []
    frame_bytes = bytes(range(12))

    class FakePopen:
        def __init__(self, argv, *args, **kwargs) -> None:  # noqa: ANN001
            seen.append([str(item) for item in argv])
            self.stdout = io.BytesIO(frame_bytes)
            self.stderr = io.BytesIO(b"n:0 pts:0 pts_time:0.04\n")
            self.returncode = 0

        def poll(self) -> int:
            return 0

        def wait(self, timeout: float | None = None) -> int:
            del timeout
            return 0

        def kill(self) -> None:
            return None

    monkeypatch.setattr("backend.app.workbench.media.subprocess.Popen", FakePopen)
    adapter = FfmpegFrameSource(
        identity=SourceClockIdentity(
            sourceSha256="b" * 64,
            byteSize=source.stat().st_size,
            width=2,
            height=2,
            pixelFormat="bgr24",
            timeBaseNum=1,
            timeBaseDen=25,
        )
    )
    frames = list(adapter.iter_frames(source))
    assert frames, "FFmpeg challenger must emit decoded frames from path"
    assert any(str(source) in token for argv in seen for token in argv)
    assert all(frame.backend == "ffmpeg" for frame in frames)
    assert frames[0].payload == frame_bytes
    assert frames[0].presentation_time_seconds == pytest.approx(0.04)


def test_durable_job_ledger_survives_process_restart_and_reconciles_outcome_unknown(tmp_path: Path) -> None:
    db_path = tmp_path / "jobs.sqlite3"
    first = DurableJobLedger(db_path=db_path)
    first.submit(_request())
    first.transition("job-restart", "running", selectedBackend="local")
    del first

    restarted = DurableJobLedger(db_path=db_path)
    receipt = restarted.receipt("job-restart")
    assert receipt.status == "outcome_unknown"
    assert receipt.attemptId
    assert "job-restart" in restarted.requests


def test_storage_ensure_job_writes_the_same_ledger(tmp_path: Path) -> None:
    from backend.app.schemas import MatchConfig
    from backend.app.storage import Storage

    storage = Storage(tmp_path)
    match = storage.create_match(
        name="ledger",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=tmp_path / "clip.mp4",
        config=MatchConfig(),
    )
    job, created = storage.ensure_job(match.id, "durable-1")
    assert created is True
    assert job.id == "durable-1"
    receipt = storage.job_ledger.receipt("durable-1")
    assert receipt.requestId == "durable-1"
    assert receipt.status in {"submitted", "waiting_for_capacity"}
    restarted = DurableJobLedger(db_path=storage.db_path)
    assert restarted.receipt("durable-1").requestId == "durable-1"


def test_detector_and_tracker_adapters_wrap_production_boxes() -> None:
    box = SimpleNamespace(
        cls=[0],
        conf=[0.91],
        id=[7],
        xyxy=[[10.0, 20.0, 30.0, 50.0]],
    )
    result = SimpleNamespace(boxes=[box], orig_img=object())
    detector = DetectorAdapter()
    receipt = detector.from_ultralytics(result, frame_id=3)
    assert receipt["counts"]["primary"] == 1
    assert receipt["detections"]
    assert receipt["detections"][0]["bbox"] == (10.0, 20.0, 30.0, 50.0)
    tracks = TrackerAdapter().from_ultralytics(result, detections=receipt["detections"])
    assert tracks[0]["trackId"] == "7"
    assert tracks[0]["silentlyReconnected"] is False


def test_hosted_object_tokens_do_not_look_like_signed_access() -> None:
    from backend.app.workbench.access import object_access_decision, signed_scoped_object_access

    naive = signed_scoped_object_access(token="club-a/match-1", object_id="match-1", token_object_id="match-1")
    assert naive["admitted"] is False
    assert naive.get("hmacOrJwtImplemented") is False
    hosted = object_access_decision(
        object_id="match-1",
        object_tenant="club-a",
        authorization="club-a",
        object_scope="match-1",
        deployment_boundary="hosted",
        client_tenant="club-b",
    )
    assert hosted["allowed"] is False
    assert hosted["admitted"] is False
    reasons = " ".join(hosted["reasonCodes"])
    assert "UNSIGNED" in reasons or "UNIMPLEMENTED" in reasons


def test_opencv_refuses_network_urls_as_unconstrained_decode() -> None:
    with pytest.raises(ValueError, match="unconstrained"):
        list(OpenCvFrameSource().iter_frames(Path("https://evil.test/clip.mp4")))


def test_leftover_http_is_dev_namespaced_when_flag_off(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GA_FLAG_LEFTOVER_HTTP", "0")
    from fastapi.testclient import TestClient

    from backend.app.main import create_app

    app = create_app(storage_root=tmp_path, run_jobs_inline=True)
    client = TestClient(app, base_url="http://127.0.0.1")
    public = client.post("/api/support/bundle", json={"consented": True})
    assert public.status_code == 404
    dev = client.post("/api/workbench/dev/support/bundle", json={"consented": True})
    assert dev.status_code == 200
    assert dev.json()["released"] is False


def test_candidate_dossier_names_this_git_head_not_only_plan_snapshot() -> None:
    from backend.app.workbench.dossier import PLAN_SOURCE_SNAPSHOT, build_baseline_dossier

    dossier = build_baseline_dossier()
    assert dossier.selectedCommit != PLAN_SOURCE_SNAPSHOT
    assert len(dossier.selectedCommit) >= 7


def test_export_timestamp_uses_decoder_pts_instead_of_index_over_fps() -> None:
    from backend.app.workbench.media import export_timestamp_seconds

    assert export_timestamp_seconds(presentation_time_seconds=0.12, frame_count=1, fps=25.0) == 0.12
    assert export_timestamp_seconds(presentation_time_seconds=0.12, frame_count=1, fps=25.0) != round(1 / 25.0, 2)


def test_proxy_ffmpeg_job_runs_constrained_argv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.workbench.media import run_proxy_ffmpeg_job

    original = tmp_path / "original.mp4"
    original.write_bytes(b"orig")
    dest = tmp_path / "proxy.mp4"
    seen: list[list[str]] = []

    def runner(argv, **kwargs):  # noqa: ANN001
        seen.append([str(item) for item in argv])
        dest.write_bytes(b"proxy")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    receipt = run_proxy_ffmpeg_job(original, dest, original_sha256=__import__("hashlib").sha256(b"orig").hexdigest(), runner=runner)
    assert receipt["replacesOriginal"] is False
    assert dest.exists()
    assert seen and seen[0][0].endswith("ffmpeg") or seen[0][0] == "ffmpeg"
    joined = " ".join(seen[0])
    assert str(original) in joined
    assert "`" not in joined and "http://" not in joined


def test_ownership_publication_walks_frames_with_hysteresis(tmp_path: Path) -> None:
    from backend.app.schemas import BallData, FrameData, MatchConfig, PlayerData
    from backend.app.storage import Storage

    storage = Storage(tmp_path)
    match = storage.create_match(
        name="own",
        input_mode="tracking_json",
        original_filename="rows.json",
        input_path=tmp_path / "rows.json",
        config=MatchConfig(),
    )
    frames = [
        FrameData(frameId=i, timestamp=i * 0.2, ball=BallData(x=50, y=34, confidence=0.9), myTeam=[PlayerData(id=1, x=49, y=34)])
        for i in range(5)
    ]
    storage.save_frames(match.id, frames)
    published = storage.publish_ownership_events(match.id)
    assert published["nearestIsNotControl"] is True
    assert published["states"]
    assert published["eventsPublication"]["status"] in {"candidate", "withheld", "provisional"}
