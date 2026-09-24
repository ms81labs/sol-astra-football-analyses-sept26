"""Tests that fail on leftover stubs: clocks, ffmpeg decode, durable jobs, perception, leftover HTTP."""

from __future__ import annotations

import io
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
    assert frames[0].presentation_time_seconds == pytest.approx(0.0)


def test_durable_job_ledger_survives_restart_until_explicit_lease_reclaim(tmp_path: Path) -> None:
    db_path = tmp_path / "jobs.sqlite3"
    first = DurableJobLedger(db_path=db_path)
    attempt = first.submit(_request())
    first.transition(
        attempt.attemptId,
        expected_revision=attempt.revision,
        owner_id="legacy",
        status="running",
        selectedBackend="local",
    )
    del first

    restarted = DurableJobLedger(db_path=db_path)
    receipt = restarted.receipt("job-restart")
    assert receipt.status == "running"
    restarted.reclaim_expired(now=float("inf"))
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
        Path(argv[-1]).write_bytes(b"proxy")  # Honour the command's staged destination.
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


def test_source_grid_export_uses_presentation_time_not_index_modulo() -> None:
    from backend.app.workbench.media import should_export_on_source_grid

    times = [0.0, 0.08, 0.10, 0.21]
    exported: list[float] = []
    last = None
    for index, presentation in enumerate(times):
        if should_export_on_source_grid(
            presentation,
            frame_count=index,
            frame_interval=1,
            last_export_presentation_time=last,
            grid_step_seconds=0.10,
        ):
            exported.append(presentation)
            last = presentation
    assert exported == [0.0, 0.10, 0.21]
    assert exported != [index / 25.0 for index in range(len(times))]


def test_detector_detect_wraps_runtime_boxes_instead_of_staying_empty() -> None:
    box = SimpleNamespace(
        cls=[0],
        conf=[0.88],
        id=[4],
        xyxy=[[1.0, 2.0, 3.0, 4.0]],
    )
    runtime_result = SimpleNamespace(boxes=[box], orig_img=object())
    receipt = DetectorAdapter().detect(
        {"colourOrder": "bgr", "frameId": 9},
        requested_backend="cpu",
        runtime=lambda _frame: runtime_result,
    )
    assert receipt["counts"]["primary"] == 1
    assert receipt["detections"][0]["bbox"] == (1.0, 2.0, 3.0, 4.0)
    assert receipt["productionPath"] == "ultralytics"


def test_detector_ingest_recovery_separates_inferred_from_visible() -> None:
    rows = [
        {"Frame_ID": 1, "Entity_Type": "ball", "observationSource": "observed_ball", "Conf": 0.9, "Source_X1": 0, "Source_Y1": 0, "Source_X2": 8, "Source_Y2": 8},
        {"Frame_ID": 2, "Entity_Type": "ball", "observationSource": "inferred_ball", "Conf": 0.4, "Source_X1": 1, "Source_Y1": 1, "Source_X2": 9, "Source_Y2": 9},
        {"Frame_ID": 3, "Entity_Type": "ball", "Conf": 0.2, "Source_X1": 2, "Source_Y1": 2, "Source_X2": 10, "Source_Y2": 10},
    ]
    receipt = DetectorAdapter().ingest_recovery_rows(rows)
    assert receipt["counts"]["primary"] == 1
    assert receipt["counts"]["recovery"] == 2
    assert receipt["states"] == {"visible": 1, "inferred": 2, "unknown": 0}
    assert receipt["labelsIndependent"] is False
    assert receipt["productionPath"] == "recover_ball_rows"


def test_commit_calibration_stays_uncertified_without_holdout() -> None:
    from backend.app.workbench.geometry import CalibrationProfile, Landmark, commit_calibration

    preview = CalibrationProfile(
        calibrationId="cal-1",
        cameraModel="planar_homography",
        landmarks=[Landmark(name="corner", imageX=0, imageY=0, pitchX=0, pitchY=0, independentHoldout=False)],
    )
    refused = commit_calibration(preview)
    assert refused["committed"] is False
    assert refused["certified"] is False
    held = CalibrationProfile(
        calibrationId="cal-2",
        cameraModel="planar_homography",
        homography=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        landmarks=[
            Landmark(name=f"holdout-{index}", imageX=x, imageY=y, pitchX=x, pitchY=y, independentHoldout=True)
            for index, (x, y) in enumerate(((10, 10), (90, 10), (10, 60), (90, 60)))
        ],
        residualP95M=0.4,
    )
    accepted = commit_calibration(held, max_p95_m=3.0)
    assert accepted["committed"] is True
    assert accepted["certified"] is False


def test_match_config_persists_teams_periods_and_rights(tmp_path: Path) -> None:
    from backend.app.schemas import MatchConfig, MatchPeriod, SourceRights
    from backend.app.storage import Storage

    storage = Storage(tmp_path)
    match = storage.create_match(
        name="setup",
        input_mode="tracking_json",
        original_filename="rows.json",
        input_path=tmp_path / "rows.json",
        config=MatchConfig(),
    )
    updated = storage.update_match_config(
        match.id,
        MatchConfig(
            cameraProfile="stable_elevated_wide",
            pitchLengthM=105,
            homeTeam="Home FC",
            awayTeam="Away FC",
            periods=[MatchPeriod(name="1", startSeconds=0, endSeconds=2700)],
            rights=SourceRights(cloudPermission=True, processingScope="hosted"),
        ),
    )
    assert updated.config.homeTeam == "Home FC"
    assert updated.config.awayTeam == "Away FC"
    setup = storage.assess_stored_match_setup(match.id)
    assert setup["homeTeam"] == "Home FC"
    assert setup["awayTeam"] == "Away FC"
    assert setup["cameraProfile"] == "stable_elevated_wide"
    assert setup["certified"] is False
    storage.close()


def test_ingest_persists_decode_anchors_from_frame_clocks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.processor import _persist_video_outputs
    from backend.app.schemas import MatchConfig, MatchSummary
    import backend.app.processor as processor
    from backend.app.storage import Storage

    storage = Storage(tmp_path)
    match = storage.create_match(
        name="anchors",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=tmp_path / "clip.mp4",
        config=MatchConfig(),
    )
    job = storage.create_job(match.id)
    (tmp_path / "clip.mp4").write_bytes(b"video")

    def fake_outputs(frames, **_kwargs):  # noqa: ANN001
        return (
            frames,
            MatchSummary(
                possession=50,
                myTeamDistance=None,
                enemyDistance=None,
                myTeamTopSpeed=None,
                enemyTopSpeed=None,
                myTeamSprints=None,
                enemySprints=None,
            ),
            [],
            [],
            [],
            [],
            {"stateContinuityAppliedFrames": 0, "frames": []},
        )

    monkeypatch.setattr(processor, "_compute_outputs_and_match_state", fake_outputs)
    _persist_video_outputs(
        storage,
        job.id,
        match.id,
        MatchConfig(),
        {
            "rows": [
                {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": -1, "X": 50.0, "Y": 34.0, "Conf": 0.9},
                {"Frame_ID": 2, "Timestamp": 0.21, "Entity_Type": "ball", "Track_ID": -1, "X": 51.0, "Y": 34.0, "Conf": 0.9},
            ],
            "trackColors": {},
            "fourRates": {"exportFpsEqualsInferenceFps": False, "decodeCount": 3, "exportCount": 2},
        },
        processing_backend="local",
        video_path=tmp_path / "clip.mp4",
        worker_path="local",
    )
    anchors = storage.load_analysis_artifact(match.id, "decode_anchors")
    assert anchors["beginning"] == 0.0
    assert anchors["end"] == 0.21
    assert anchors["source"] in {"production_decode", "persisted_frames"}
    ownership = storage.load_analysis_artifact(match.id, "ownership_publication")
    assert ownership["nearestIsNotControl"] is True
    storage.close()


def test_proxy_assets_attempt_constrained_ffmpeg_job(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.schemas import MatchConfig
    from backend.app.storage import Storage

    storage = Storage(tmp_path)
    original = tmp_path / "clip.mp4"
    original.write_bytes(b"orig-bytes")
    match = storage.create_match(
        name="proxy",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=original,
        config=MatchConfig(),
    )
    seen: list[list[str]] = []

    def runner(argv, **kwargs):  # noqa: ANN001
        seen.append([str(item) for item in argv])
        dest = tmp_path / "matches" / match.id / "proxy.mp4"
        dest.parent.mkdir(parents=True, exist_ok=True)
        Path(argv[-1]).write_bytes(b"proxy")  # Honour the command's staged destination.
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    from backend.app.workbench import media
    proxy_job = media.run_proxy_ffmpeg_job
    monkeypatch.setattr(media, "run_proxy_ffmpeg_job",
                        lambda *args, **kwargs: proxy_job(*args, runner=runner, **kwargs))
    receipt = storage.proxy_assets_for_match(match.id)
    assert receipt["replacesOriginal"] is False
    assert receipt["ranFfmpeg"] is True
    assert seen and "ffmpeg" in seen[0][0]
    storage.close()


def _sqlite_fd_count(db_path: Path) -> int:
    import os

    target = str(db_path)
    count = 0
    for descriptor in os.listdir("/proc/self/fd"):
        try:
            linked = os.readlink(f"/proc/self/fd/{descriptor}")
        except OSError:
            continue
        if linked == target or linked.startswith(f"{target}-"):
            count += 1
    return count


def test_storage_close_releases_sqlite_so_exclusive_lock_succeeds(tmp_path: Path) -> None:
    from backend.app.schemas import MatchConfig
    from backend.app.storage import Storage

    storage = Storage(tmp_path)
    match = storage.create_match(
        name="fd",
        input_mode="tracking_json",
        original_filename="rows.json",
        input_path=tmp_path / "rows.json",
        config=MatchConfig(),
    )
    storage.ensure_job(match.id, "job-fd")
    storage.close()
    connection = sqlite3.connect(str(storage.db_path), timeout=1.0)
    try:
        connection.execute("BEGIN EXCLUSIVE")
        connection.commit()
    finally:
        connection.close()


def test_storage_methods_close_sqlite_connections_without_waiting_for_gc(tmp_path: Path) -> None:
    from backend.app.schemas import MatchConfig
    from backend.app.storage import Storage

    storage = Storage(tmp_path)
    match = storage.create_match(
        name="fd-loop",
        input_mode="tracking_json",
        original_filename="rows.json",
        input_path=tmp_path / "rows.json",
        config=MatchConfig(),
    )
    storage.ensure_job(match.id, "job-loop")
    for _ in range(40):
        storage.list_matches()
        storage.get_match(match.id)
        storage.get_job("job-loop")
        storage.job_ledger.receipt("job-loop")
    assert _sqlite_fd_count(storage.db_path) <= 6
    storage.close()
    assert _sqlite_fd_count(storage.db_path) <= 3


def test_workbench_timeout_and_lost_connection_use_storage_sqlite_ledger(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from backend.app.main import create_app
    app = create_app(storage_root=tmp_path, run_jobs_inline=True)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        created = client.post(
            "/api/workbench/jobs",
            json={"requestId": "shared-timeout", "matchId": "match-a", "sourceSha256": "c" * 64, "budget": 1.0},
        )
        assert created.status_code == 410
        assert "shared-timeout" not in app.state.storage.job_ledger.requests
        timed_out = client.post("/api/workbench/jobs/shared-timeout/timeout")
        assert timed_out.status_code == 410
        lost = client.post("/api/workbench/jobs/shared-timeout/lost-connection")
        assert lost.status_code == 410


def test_storage_completed_job_marks_ledger_complete_and_websocket_closes(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from backend.app.main import create_app
    from backend.app.schemas import MatchConfig
    from backend.app.storage import Storage

    app = create_app(storage_root=tmp_path, run_jobs_inline=True)
    storage: Storage = app.state.storage
    match = storage.create_match(
        name="ws",
        input_mode="tracking_json",
        original_filename="rows.json",
        input_path=tmp_path / "rows.json",
        config=MatchConfig(),
    )
    storage.ensure_job(match.id, "ws-complete")
    storage.update_job("ws-complete", status="completed", progress=1.0, message="Processing complete")
    assert storage.job_ledger.receipt("ws-complete").status == "complete"
    with TestClient(app, base_url="http://127.0.0.1") as client:
        with client.websocket_connect("ws://127.0.0.1/ws/jobs/ws-complete") as websocket:
            payload = websocket.receive_json()
            assert payload["status"] in {"completed", "complete"}
            assert payload["ledgerStatus"] == "complete"


def test_match_calibration_commit_persists_uncertified_profile(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from backend.app.main import create_app
    from backend.app.schemas import MatchConfig
    from backend.app.storage import Storage

    app = create_app(storage_root=tmp_path, run_jobs_inline=True)
    storage: Storage = app.state.storage
    match = storage.create_match(
        name="cal",
        input_mode="tracking_json",
        original_filename="rows.json",
        input_path=tmp_path / "rows.json",
        config=MatchConfig(),
    )
    with TestClient(app, base_url="http://127.0.0.1") as client:
        refused = client.post(
            f"/api/matches/{match.id}/calibration/commit",
            json={
                "calibrationId": "cal-1",
                "cameraModel": "planar_homography",
                "landmarks": [
                    {"name": "corner", "imageX": 0, "imageY": 0, "pitchX": 0, "pitchY": 0, "independentHoldout": False}
                ],
            },
        )
        assert refused.status_code == 200
        assert refused.json()["committed"] is False
        assert refused.json()["certified"] is False
        accepted = client.post(
            f"/api/matches/{match.id}/calibration/commit",
            json={
                "calibrationId": "cal-2",
                "cameraModel": "planar_homography",
                "homography": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                "residualP95M": 0.4,
                "landmarks": [
                    {
                        "name": f"holdout-{index}",
                        "imageX": x,
                        "imageY": y,
                        "pitchX": x,
                        "pitchY": y,
                        "independentHoldout": True,
                    }
                    for index, (x, y) in enumerate(((10, 10), (90, 10), (10, 60), (90, 60)))
                ],
            },
        )
        assert accepted.json()["committed"] is True
        assert accepted.json()["certified"] is False
        setup = client.get(f"/api/matches/{match.id}/setup")
        assert setup.json()["calibrationCommitted"] is True
        preview = client.get(f"/api/matches/{match.id}/setup/preview")
        assert preview.json()["committed"] is True
        assert preview.json()["certified"] is False


def test_unwrap_ultralytics_track_result_accepts_result_list_and_iterator() -> None:
    from backend.app.workbench.perception import unwrap_ultralytics_track_result

    boxed = SimpleNamespace(boxes=["ok"])
    assert unwrap_ultralytics_track_result(boxed) is boxed
    assert unwrap_ultralytics_track_result([boxed]) is boxed
    assert unwrap_ultralytics_track_result(iter([boxed])) is boxed
    with pytest.raises(RuntimeError, match="no results"):
        unwrap_ultralytics_track_result([])


def test_opencv_stuck_pos_msec_marks_clock_missing_instead_of_collapsing_export() -> None:
    class Capture:
        def __init__(self) -> None:
            self._index = -1

        def isOpened(self) -> bool:
            return True

        def get(self, _prop: int) -> float:
            return 5.0

        def read(self):
            self._index += 1
            if self._index >= 3:
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

    frames = list(OpenCvFrameSource(cv2_module=Cv2()).iter_frames(Path("/tmp/stuck.mp4")))
    assert len(frames) == 3
    assert frames[0].presentation_clock == "decoder_pts"
    assert all(frame.presentation_clock == "missing" for frame in frames[1:])
    exported = 0
    last = None
    from backend.app.workbench.media import should_export_on_source_grid

    for index, frame in enumerate(frames):
        presentation = None if frame.presentation_clock == "missing" else frame.presentation_time_seconds
        if should_export_on_source_grid(
            presentation,
            frame_count=index,
            frame_interval=1,
            last_export_presentation_time=last,
            grid_step_seconds=0.2,
        ):
            exported += 1
            last = presentation if presentation is not None else last
    assert exported == 3


def test_tracker_associate_reuses_previous_track_id_by_iou_without_silent_cut_reconnect() -> None:
    detection = Detection(
        frameId=1,
        bbox=(10.0, 20.0, 30.0, 80.0),
        score=0.9,
        kind="player",
        stratum="near",
    )
    previous = [
        {
            "frameId": 0,
            "trackId": "iou_fallback:stable-7",
            "bbox": (11.0, 21.0, 31.0, 81.0),
            "kind": "player",
            "observationSource": "observed",
            "reset": False,
            "silentlyReconnected": False,
        }
    ]
    from backend.app.workbench.perception import IouAssociationFallback

    adapter = IouAssociationFallback()
    continuous = adapter.associate([detection], previous_tracks=previous)
    assert continuous[0]["trackId"] == "iou_fallback:stable-7"
    assert continuous[0]["silentlyReconnected"] is False
    cut = adapter.associate([detection], cut_detected=True, previous_tracks=previous)
    assert cut[0]["trackId"] != "iou_fallback:stable-7"
    assert cut[0]["reset"] is True
    assert cut[0]["silentlyReconnected"] is False



def test_should_sample_on_source_grid_prefers_pts_over_index_modulo() -> None:
    from backend.app.workbench.media import DecodedFrame, should_sample_on_source_grid

    def frame(index: int, seconds: float) -> DecodedFrame:
        return DecodedFrame(
            source_frame_index=index,
            pts=int(seconds * 1000),
            presentation_time_seconds=seconds,
            width=2,
            height=2,
            colour_order="bgr",
            rotation=0,
            payload=b"\x00" * 12,
            backend="fixture",
        )

    last = None
    sampled = []
    times = [0.0, 0.03, 0.06, 0.40]
    for index, seconds in enumerate(times):
        decoded = frame(index, seconds)
        if should_sample_on_source_grid(
            decoded,
            frame_count=index,
            frame_interval=2,
            last_sample_presentation_time=last,
            fps=30.0,
        ):
            sampled.append(index)
            last = seconds
    assert sampled == [0, 3]


def test_collect_primary_player_windows_samples_pts_grid_not_index_modulo(tmp_path: Path) -> None:
    import numpy as np

    from backend.app.workbench.media import DecodedFrame, FixtureFrameSource
    from backend import run_guerilla as pipeline

    times = [0.0, 0.03, 0.06, 0.40]
    frames = []
    for index, seconds in enumerate(times):
        image = np.zeros((16, 16, 3), np.uint8)
        frames.append(
            DecodedFrame(
                source_frame_index=index,
                pts=int(seconds * 1000),
                presentation_time_seconds=seconds,
                width=16,
                height=16,
                colour_order="bgr",
                rotation=0,
                payload=image.tobytes(),
                backend="fixture",
                image=image,
            )
        )
    identity = SourceClockIdentity(
        sourceSha256="a" * 64,
        byteSize=16,
        codec="h264",
        width=16,
        height=16,
        nominalFps=30.0,
        variableFrameRate=True,
    )
    source = FixtureFrameSource(frames, identity)
    sampled: list[int] = []

    class Model:
        def predict(self, frame, **kwargs):
            del kwargs
            sampled.append(len(sampled))
            box = SimpleNamespace(cls=[0], xyxy=[[0, 0, 4, 4]])
            return [SimpleNamespace(boxes=[box])]

    path = tmp_path / "vfr.mp4"
    path.write_bytes(b"fixture-media")
    windows = pipeline.collect_primary_player_windows(
        path,
        Model(),
        frame_interval=2,
        imgsz=32,
        conf=0.1,
        tracker=None,
        frame_source=source,
    )
    # Index modulo 2 would sample frames 0 and 2. PTS grid 2/30s samples 0 and 3.
    assert sorted(windows) == [0, 3]
    assert len(sampled) == 2


def test_production_main_does_not_define_leftover_del_payload_posts() -> None:
    source = Path("backend/app/main.py").read_text(encoding="utf-8")
    assert "del payload" not in source


def test_leftover_post_handlers_live_outside_production_main() -> None:
    from backend.app.workbench.leftover_http import LEFTOVER_POST_PATHS
    from backend.app.workbench import leftover_routes

    source = "\n".join(path.read_text(encoding="utf-8") for path in Path(leftover_routes.__file__).parent.glob("leftover*routes.py"))
    main_source = Path("backend/app/main.py").read_text(encoding="utf-8")
    assert "create_leftover_post_router" in source
    assert "@app.post(\"/api/support/bundle\")" not in main_source
    assert "/support/bundle" in source
    assert "/api/support/bundle" in LEFTOVER_POST_PATHS


def test_production_app_registers_leftover_posts_only_under_dev_prefix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GA_FLAG_LEFTOVER_HTTP", "0")
    from fastapi.testclient import TestClient

    from backend.app.main import create_app

    app = create_app(storage_root=tmp_path, run_jobs_inline=True)
    support_posts = {
        route.path: route
        for route in app.routes
        if getattr(route, "methods", None) and "POST" in route.methods
        and (route.path == "/api/support/bundle" or route.path.endswith("/support/bundle"))
    }
    assert support_posts["/api/support/bundle"].endpoint.__module__ == "backend.app.main"
    assert support_posts["/api/workbench/dev/support/bundle"].endpoint.__module__ == "backend.app.workbench.leftover_analysis_routes"

    client = TestClient(app, base_url="http://127.0.0.1")
    public = client.post("/api/support/bundle", json={"consented": True})
    assert public.status_code == 404
    detector = client.post("/api/detector", json={"requestedBackend": "cuda"})
    assert detector.status_code == 404
    dev = client.post("/api/workbench/dev/support/bundle", json={"consented": True})
    assert dev.status_code == 200
    assert dev.json()["released"] is False
    dev_detector = client.post("/api/workbench/dev/detector", json={"requestedBackend": "cuda"})
    assert dev_detector.status_code == 200
    assert dev_detector.json()["selectedBackend"] == "cpu"


def test_leftover_gets_are_dev_namespaced_when_flag_off(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GA_FLAG_LEFTOVER_HTTP", "0")
    from fastapi.testclient import TestClient

    from backend.app.main import create_app

    app = create_app(storage_root=tmp_path, run_jobs_inline=True)
    client = TestClient(app, base_url="http://127.0.0.1")
    public_bundle = client.get("/api/support/bundle")
    assert public_bundle.status_code == 404
    public_hota = client.get("/api/evaluation/hota")
    assert public_hota.status_code == 404
    public_gpu = client.get("/api/gpu")
    assert public_gpu.status_code == 404
    public_native = client.get("/api/native")
    assert public_native.status_code == 404
    public_html = client.get("/video-to-analysis/finish-line")
    assert public_html.status_code == 404

    flags = client.get("/api/flags")
    assert flags.status_code == 200
    dossier = client.get("/api/dossier")
    assert dossier.status_code == 200
    matches = client.get("/api/matches")
    assert matches.status_code == 200

    dev_bundle = client.get("/api/workbench/dev/support/bundle")
    assert dev_bundle.status_code == 200
    assert "released" in dev_bundle.json()
    assert "expired" not in dev_bundle.json()
    dev_hota = client.get("/api/workbench/dev/evaluation/hota")
    assert dev_hota.status_code == 200
    dev_gpu = client.get("/api/workbench/dev/gpu")
    assert dev_gpu.status_code == 200
    assert dev_gpu.json().get("canPromoteDefault") is False


def test_leftover_gets_absent_from_public_openapi_when_flag_off(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GA_FLAG_LEFTOVER_HTTP", "0")
    from backend.app.main import create_app

    app = create_app(storage_root=tmp_path, run_jobs_inline=True)
    paths = set(app.openapi()["paths"])
    leftover_public = {
        "/api/support/bundle",
        "/api/evaluation/hota",
        "/api/gpu",
        "/api/native",
        "/api/heatmap",
        "/api/dossier/release",
        "/video-to-analysis/finish-line",
        "/api/video-to-analysis/finish-line",
    }
    assert leftover_public.isdisjoint(paths)
    assert "/api/workbench/dev/support/bundle" in paths
    assert "/api/workbench/dev/evaluation/hota" in paths
    assert "/api/workbench/dev/gpu" in paths
    assert "/api/matches" in paths
    assert "/api/flags" in paths
    assert "/api/dossier" in paths
    assert "/api/jobs/{job_id}" in paths


def test_leftover_gets_present_on_public_api_when_flag_on(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GA_FLAG_LEFTOVER_HTTP", "1")
    from fastapi.testclient import TestClient

    from backend.app.main import create_app

    app = create_app(storage_root=tmp_path, run_jobs_inline=True)
    paths = set(app.openapi()["paths"])
    assert "/api/support/bundle" in paths
    assert "/api/evaluation/hota" in paths
    assert "/api/gpu" in paths
    client = TestClient(app, base_url="http://127.0.0.1")
    public = client.get("/api/support/bundle")
    assert public.status_code == 200
    assert "expired" not in public.json()
    hota = client.get("/api/evaluation/hota")
    assert hota.status_code == 200


def test_production_main_does_not_define_leftover_contract_gets() -> None:
    source = Path("backend/app/main.py").read_text(encoding="utf-8")
    for path in (
        "/api/support/bundle",
        "/api/evaluation/hota",
        "/api/gpu",
        "/api/native",
        "/api/heatmap",
        "/api/dossier/release",
        "/api/video-to-analysis/finish-line",
    ):
        assert f'@app.get("{path}")' not in source


def test_leftover_get_handlers_live_outside_production_main() -> None:
    from backend.app.workbench.leftover_http import LEFTOVER_GET_PATHS
    from backend.app.workbench import leftover_routes

    source = "\n".join(path.read_text(encoding="utf-8") for path in Path(leftover_routes.__file__).parent.glob("leftover*routes.py"))
    sibling = Path(leftover_routes.__file__).with_name("leftover_get_routes.py")
    sibling_source = sibling.read_text(encoding="utf-8") if sibling.exists() else ""
    combined = source + sibling_source
    assert "create_leftover_get_router" in combined or "@router.get(\"/support/bundle\")" in combined
    assert "/support/bundle" in combined
    assert "/evaluation/hota" in combined
    assert "/api/support/bundle" in LEFTOVER_GET_PATHS
    assert "/api/evaluation/hota" in LEFTOVER_GET_PATHS
    assert "/api/gpu" in LEFTOVER_GET_PATHS
