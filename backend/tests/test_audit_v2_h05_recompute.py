from __future__ import annotations

import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.processor import process_match, reprocess_video_match
from backend.app.schemas import MatchConfig
from backend.app.storage import Storage
from backend.app.video_pipeline import process_video_input
from backend.app.workbench.cache import (
    DetectionIdentity,
    ProjectionIdentity,
    ReportIdentity,
    ReviewedIdentity,
    TrackingIdentity,
)
from backend.app.domain_types import Interval
from backend.app.workbench.executables import resolve_trusted_executable
from backend.app.workbench.media import FfmpegFrameSource


FIXTURE = Path(__file__).parent / "fixtures" / "raw_rows_two_teams.json"
TRACKING_FIXTURE = Path(__file__).parent / "fixtures" / "sample_tracking.json"


def _detection(**changes) -> DetectionIdentity:
    values = {
        "source_sha256": "a" * 64,
        "stream_index": 0,
        "interval": Interval(start=0.25, end=5.0),
        "weights_sha256": "b" * 64,
        "preprocessing_id": "letterbox-v2",
        "class_map_id": "football-v1",
        "precision": "fp32",
        "runtime_build": "ffmpeg-8|torch-2|ultralytics-9",
    }
    values.update(changes)
    return DetectionIdentity(**values)


def test_t09_layered_identities_invalidate_only_their_layer_and_downstream() -> None:
    detection = _detection()
    tracking = TrackingIdentity(detection, "botsort-v1")
    projection = ProjectionIdentity(tracking, "cal-1")
    reviewed = ReviewedIdentity(projection, "correction-1")
    report = ReportIdentity(reviewed, "report-v1")

    assert _detection().digest() == detection.digest()
    changed_detection = _detection(weights_sha256="c" * 64)
    assert changed_detection.digest() != detection.digest()
    assert ProjectionIdentity(tracking, "cal-2").tracking.digest() == tracking.digest()
    assert ProjectionIdentity(tracking, "cal-2").digest() != projection.digest()
    assert ReviewedIdentity(projection, "correction-2").projection.digest() == projection.digest()
    assert ReportIdentity(reviewed, "report-v2").reviewed.digest() == reviewed.digest()
    assert not _detection(source_sha256=None).reusable
    assert _detection(source_sha256=None).digest() != _detection(source_sha256=None).digest()
    assert report.reusable


def test_t09_generation_wires_projection_review_and_report_identities(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "storage")
    source = tmp_path / "tracking.json"
    source.write_text("[]", encoding="utf-8")
    match = storage.create_match("identity layers", "tracking_json", source.name, source, MatchConfig())
    detection = _detection()
    tracking = TrackingIdentity(detection, "botsort-v1")
    storage.save_analysis_artifact(
        match.id,
        "detection_identity",
        {"digest": detection.digest(), "reusable": True, "components": detection.components()},
    )
    storage.save_analysis_artifact(
        match.id,
        "tracking_identity",
        {"digest": tracking.digest(), "reusable": True, "components": tracking.components()},
    )

    first = storage._generation_layer_identities(
        match.id, calibration_revision="cal-1", correction_head="correction-1"
    )
    calibrated = storage._generation_layer_identities(
        match.id, calibration_revision="cal-2", correction_head="correction-1"
    )
    reviewed = storage._generation_layer_identities(
        match.id, calibration_revision="cal-2", correction_head="correction-2"
    )
    assert first["detection"]["digest"] == calibrated["detection"]["digest"]
    assert first["tracking"]["digest"] == calibrated["tracking"]["digest"]
    assert first["projection"]["digest"] != calibrated["projection"]["digest"]
    assert calibrated["projection"]["digest"] == reviewed["projection"]["digest"]
    assert calibrated["reviewed"]["digest"] != reviewed["reviewed"]["digest"]
    assert calibrated["report"]["digest"] != reviewed["report"]["digest"]


def _install_video_match(storage: Storage, tmp_path: Path) -> str:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"source")
    match = storage.create_match("recompute", "video", source.name, source, MatchConfig(myTeamCluster=0))
    storage.save_raw_rows(match.id, json.loads(FIXTURE.read_text(encoding="utf-8")))
    reprocess_video_match(storage, match.id)
    return match.id


def test_t09_recompute_plan_execute_and_cache_miss_are_truthful(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "storage")
    match_id = _install_video_match(storage, tmp_path)

    plan = storage.recompute_for_match(match_id, "calibration")
    assert plan["kind"] == "plan"
    assert plan["visionRequired"] is False
    assert "admitted" not in plan and "reused" not in plan

    before = storage.current_generation(match_id).generationId
    receipt = storage.execute_recompute(match_id, "calibration").model_dump(mode="json")
    assert receipt["kind"] == "executed"
    assert receipt["detectorCalls"] == 0
    assert receipt["outputGeneration"] != before
    assert storage.current_generation(match_id).generationId == receipt["outputGeneration"]
    assert (storage._match_dir(match_id) / "generations" / receipt["outputGeneration"] / "manifest.json").is_file()

    (storage._match_dir(match_id) / "raw_rows.json").unlink()
    current = storage.current_generation(match_id).generationId
    refusal = storage.execute_recompute(match_id, "calibration").model_dump(mode="json")
    assert refusal == {"kind": "refused", "reasonCodes": ["CACHE_MISS"]}
    assert storage.current_generation(match_id).generationId == current


def test_t09_calibration_execution_reprojects_immutable_tracking_observations(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "storage")
    fixture = Path(__file__).parent / "fixtures" / "sample_tracking.json"
    match = storage.create_match("tracking recompute", "tracking_json", fixture.name, fixture, MatchConfig())
    process_match(storage, storage.create_job(match.id).id)
    before_x = storage.load_frames(match.id)[0].myTeam[0].x
    profile = {
        "calibrationId": "shift-five",
        "cameraModel": "planar_homography",
        "pitchLengthM": 105.0,
        "pitchWidthM": 68.0,
        "homography": [[1.0, 0.0, 5.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
    }
    revision = storage._new_calibration_revision(
        match.id,
        profile=profile,
        evaluation={"accepted": True, "measured": True},
    )
    # C01 stages calibration explicitly; a mutable flat file may not override
    # the committed generation. Keep the original geometric/detector assertions.
    with storage.generations.candidate(match.id, storage.get_match(match.id).config, revision):
        receipt = storage.execute_recompute(match.id, "calibration").model_dump(mode="json")
    assert receipt["kind"] == "executed"
    assert receipt["detectorCalls"] == 0
    assert storage.load_frames(match.id)[0].myTeam[0].x != before_x
    assert storage.current_generation(match.id).generationId == receipt["outputGeneration"]


def test_t17_process_video_preserves_producer_receipts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rates = {
        "decodeCount": 250,
        "detectorPrimaryCount": 12,
        "detectorRecoveryCount": 3,
        "trackerUpdateCount": 50,
        "exportCount": 50,
    }
    anchors = {"beginning": 0.0, "middle": 2.5, "end": 5.0}
    producer = {
        "rows": [{"Frame_ID": 0}],
        "trackColors": {},
        "fourRates": rates,
        "samplingReceipt": {"sourceSha256": "a" * 64},
        "decodeAnchors": anchors,
    }
    monkeypatch.setattr("backend.app.video_pipeline._process_video_impl", lambda *args, **kwargs: producer)

    class Source:
        name = "fixture"

        def probe(self, path):
            from backend.app.workbench.contracts import SourceClockIdentity

            return SourceClockIdentity(sourceSha256="a" * 64, byteSize=path.stat().st_size, codec="h264")

    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    result = process_video_input(video, MatchConfig(autoHomography=True), frame_source=Source())
    assert result["fourRates"] == rates
    assert result["samplingReceipt"] == producer["samplingReceipt"]
    assert result["decodeAnchors"] == anchors
    assert result["policy"]["requestedBackend"] == "fixture+ultralytics_track"


def test_t09_video_identity_uses_resolved_weights_and_actual_interval(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    producer = {
        "rows": [{"Frame_ID": 0}],
        "fourRates": {
            "decodeCount": 2,
            "detectorPrimaryCount": 2,
            "detectorRecoveryCount": 0,
            "trackerUpdateCount": 2,
            "exportCount": 2,
        },
        "samplingReceipt": {},
        "decodeAnchors": {"beginning": 0.25, "middle": None, "end": 1.25},
        "precision": "float32",
    }
    monkeypatch.setattr("backend.app.video_pipeline._process_video_impl", lambda *args, **kwargs: dict(producer))
    monkeypatch.setattr("backend.app.video_pipeline.importlib.metadata.version", lambda package: "1.0")

    class Source:
        name = "fixture-decoder"
        runtime_build = "fixture-decoder-1.0"

        def probe(self, path):
            from backend.app.workbench.contracts import SourceClockIdentity

            return SourceClockIdentity(sourceSha256="a" * 64, byteSize=path.stat().st_size, codec="h264")

    video = tmp_path / "clip.mp4"
    weights = tmp_path / "model.pt"
    video.write_bytes(b"video")
    weights.write_bytes(b"weights-v1")
    first = process_video_input(
        video,
        MatchConfig(autoHomography=True),
        primary_model_path=str(weights),
        frame_source=Source(),
    )
    weights.write_bytes(b"weights-v2")
    second = process_video_input(
        video,
        MatchConfig(autoHomography=True),
        primary_model_path=str(weights),
        frame_source=Source(),
    )
    assert first["detectionIdentity"]["reusable"] is True
    assert first["detectionIdentity"]["components"]["interval"] == {"start": 0.25, "end": 1.25}
    assert (
        first["detectionIdentity"]["components"]["weights_sha256"]
        != second["detectionIdentity"]["components"]["weights_sha256"]
    )
    assert first["detectionIdentity"]["digest"] != second["detectionIdentity"]["digest"]


def test_t17_missing_or_non_integer_producer_counts_fail_loudly(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "backend.app.video_pipeline._process_video_impl",
        lambda *args, **kwargs: {"rows": [{"Frame_ID": 0}], "fourRates": {"decodeCount": 1}},
    )
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    with pytest.raises(RuntimeError, match="fourRates"):
        process_video_input(video, MatchConfig(autoHomography=True))


def test_t17_recovery_counter_wraps_each_model_invocation() -> None:
    from backend.run_guerilla import _CountingPredictor

    calls = []

    class Model:
        def predict(self, value):
            return value

    wrapped = _CountingPredictor(Model(), lambda: calls.append(1))
    assert [wrapped.predict(1), wrapped.predict(2), wrapped.predict(3)] == [1, 2, 3]
    assert len(calls) == 3


@pytest.mark.real_media
def test_t17_generated_media_receipts_reach_stored_artifact_and_api_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ffmpeg = resolve_trusted_executable("ffmpeg")
    clip = tmp_path / "five-seconds.mp4"
    subprocess.run(
        [
            str(ffmpeg), "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
            "color=c=green:duration=5:size=96x64:rate=3", "-pix_fmt", "yuv420p", "-y", str(clip),
        ],
        check=True,
        timeout=30,
    )

    class Values(list):
        def tolist(self):
            return list(self)

    class Box:
        cls = [32]
        conf = [0.9]
        id = [7]
        xyxy = [Values([40.0, 25.0, 48.0, 33.0])]

    class PlayerBox:
        cls = [0]
        conf = [0.9]
        id = [8]
        xyxy = [Values([20.0, 15.0, 35.0, 55.0])]

    class Boxes(list):
        data = SimpleNamespace(device="cpu")

    class SpyModel:
        def __init__(self):
            self.track_calls = 0
            self.model = SimpleNamespace(
                parameters=lambda: iter([SimpleNamespace(dtype="float32")])
            )

        def track(self, **kwargs):
            self.track_calls += 1
            return [SimpleNamespace(boxes=Boxes([PlayerBox(), Box()]), orig_img=kwargs["source"])]

        def predict(self, *_args, **_kwargs):
            return [SimpleNamespace(boxes=Boxes([Box()]))]

    spy = SpyModel()
    monkeypatch.setattr("backend.run_guerilla.YOLO", lambda _path: spy)
    result = process_video_input(
        clip,
        MatchConfig(
            manualHomographyPoints=[
                {"x": 0, "y": 0}, {"x": 95, "y": 0}, {"x": 95, "y": 63}, {"x": 0, "y": 63},
            ]
        ),
        frame_source=FfmpegFrameSource(),
    )

    rates = result["fourRates"]
    anchors = result["decodeAnchors"]
    assert rates["detectorPrimaryCount"] == spy.track_calls
    assert anchors["beginning"] < anchors["middle"] < anchors["end"]

    storage_root = tmp_path / "storage"
    storage = Storage(storage_root)
    monkeypatch.setattr("backend.app.processor.process_video_input", lambda *_args, **_kwargs: result)
    monkeypatch.setattr("backend.app.processor.materialize_proof_runtime_options", lambda *_args, **_kwargs: {})
    match = storage.create_match(
        "receipt bundle", "video", clip.name, clip,
        MatchConfig(
            manualHomographyPoints=[
                {"x": 0, "y": 0}, {"x": 95, "y": 0}, {"x": 95, "y": 63}, {"x": 0, "y": 63},
            ]
        ),
    )
    process_match(storage, storage.create_job(match.id).id)
    assert storage.load_analysis_artifact(match.id, "four_rates") == rates

    response = TestClient(create_app(storage_root=storage_root), base_url="http://127.0.0.1").get(
        f"/api/matches/{match.id}/export/match.json"
    )
    assert response.status_code == 200
    assert response.json()["fourRates"] == rates
    assert response.json()["decodeAnchors"] == anchors
