from __future__ import annotations

import anyio
import httpx
import multiprocessing
from pathlib import Path

from backend.app import review_routes
from backend.app.main import create_app
from backend.app.schemas import BallOwnership, FrameData, MatchConfig, MatchSummary
from backend.app.storage import Storage


def _summary(value: int) -> MatchSummary:
    return MatchSummary(
        possession=None,
        myTeamXg=value / 100,
        myTeamDistance=None,
        enemyDistance=None,
        myTeamTopSpeed=None,
        enemyTopSpeed=None,
        myTeamSprints=None,
        enemySprints=None,
    )


def _publish(
    storage: Storage,
    match_id: str,
    value: int,
    *,
    frames=None,
    assignments=None,
    config: MatchConfig | None = None,
):
    return storage.publish_generation(
        match_id,
        frames=frames or [FrameData(frameId=value, timestamp=float(value))],
        summary=_summary(value),
        assignments=assignments or [
            BallOwnership(
                frameId=value,
                timestamp=float(value),
                team="my_team",
                trackId=value,
            )
        ],
        formation_timeline=[],
        shots=[],
        events=[],
        correction_head="none",
        effective_config=config or MatchConfig(),
    )


def _publish_in_child(root: str, match_id: str, connection) -> None:
    try:
        assert connection.recv() == "publish"
        ref = _publish(Storage(Path(root)), match_id, 2)
        connection.send(("published", ref.generationId))
    except BaseException as exc:
        connection.send(("error", repr(exc)))
        raise
    finally:
        connection.close()


def test_trust_crop_request_keeps_frames_and_assignments_on_one_generation(
    tmp_path, monkeypatch
) -> None:
    anyio.run(_assert_one_generation, tmp_path, monkeypatch)


async def _assert_one_generation(tmp_path, monkeypatch) -> None:
    app = create_app(storage_root=tmp_path / "store", run_jobs_inline=True)
    storage = app.state.storage
    source = tmp_path / "tracking.json"
    source.write_text("[]", encoding="utf-8")
    match = storage.create_match(
        "snapshot", "tracking_json", source.name, source, MatchConfig()
    )
    old = _publish(storage, match.id, 1)
    storage.update_match_status(match.id, status="ready")
    writer = Storage(storage.storage_root)
    original_load_frames = storage.load_frames
    observed: dict[str, list[int]] = {}

    def load_then_publish(match_id: str, *, generation_id=None):
        frames = original_load_frames(match_id, generation_id=generation_id)
        if "published" not in observed:
            observed["published"] = [1]
            _publish(writer, match_id, 2)
        return frames

    def observe(frames, assignments, max_crops=20, **_kwargs):
        observed["frames"] = [frame["frameId"] for frame in frames]
        observed["assignments"] = [item["frameId"] for item in assignments]
        return []

    monkeypatch.setattr(storage, "load_frames", load_then_publish)
    monkeypatch.setattr(review_routes, "compute_trust_crops", observe)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        response = await client.get(f"/api/matches/{match.id}/trust-crops")

    assert response.status_code == 200, response.text
    assert observed["frames"] == observed["assignments"] == [1]
    assert response.json()["generationId"] == old.generationId


def test_trust_crop_pin_allows_separate_writer_process_and_keeps_old_view(
    tmp_path, monkeypatch
) -> None:
    anyio.run(_assert_process_interleaving, tmp_path, monkeypatch)


async def _assert_process_interleaving(tmp_path, monkeypatch) -> None:
    app = create_app(storage_root=tmp_path / "store", run_jobs_inline=True)
    storage = app.state.storage
    source = tmp_path / "tracking.json"
    source.write_text("[]", encoding="utf-8")
    match = storage.create_match("process", "tracking_json", source.name, source, MatchConfig())
    old = _publish(storage, match.id, 1)
    storage.update_match_status(match.id, status="ready")
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(
        target=_publish_in_child,
        args=(str(storage.storage_root), match.id, child),
    )
    process.start()
    child.close()
    original_load_frames = storage.load_frames
    observed: dict[str, list[int]] = {}

    def load_then_release_writer(match_id: str, *, generation_id=None):
        frames = original_load_frames(match_id, generation_id=generation_id)
        parent.send("publish")
        assert parent.poll(20), "writer did not publish while reader held a snapshot"
        result = parent.recv()
        assert result[0] == "published", result
        return frames

    def observe(frames, assignments, max_crops=20, **_kwargs):
        observed["frames"] = [frame["frameId"] for frame in frames]
        observed["assignments"] = [item["frameId"] for item in assignments]
        return []

    monkeypatch.setattr(storage, "load_frames", load_then_release_writer)
    monkeypatch.setattr(review_routes, "compute_trust_crops", observe)
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
            response = await client.get(f"/api/matches/{match.id}/trust-crops")
    finally:
        process.join(20)
        if process.is_alive():
            process.kill()
            process.join(20)
        parent.close()

    assert process.exitcode == 0
    assert response.status_code == 200, response.text
    assert response.json()["generationId"] == old.generationId
    assert observed["frames"] == observed["assignments"] == [1]


def test_trust_crop_explicit_history_never_falls_back_to_current(tmp_path) -> None:
    anyio.run(_assert_explicit_history, tmp_path)


async def _assert_explicit_history(tmp_path) -> None:
    app = create_app(storage_root=tmp_path / "store", run_jobs_inline=True)
    storage = app.state.storage
    source = tmp_path / "tracking.json"
    source.write_text("[]", encoding="utf-8")
    match = storage.create_match("history", "tracking_json", source.name, source, MatchConfig())
    old = _publish(storage, match.id, 1)
    current = _publish(storage, match.id, 2)
    storage.update_match_status(match.id, status="ready")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        old_response = await client.get(
            f"/api/matches/{match.id}/trust-crops", params={"generationId": old.generationId}
        )
        missing_response = await client.get(
            f"/api/matches/{match.id}/trust-crops", params={"generationId": "gen_missing"}
        )

    assert old_response.status_code == 200
    assert old_response.json()["generationId"] == old.generationId
    assert old_response.json()["generationId"] != current.generationId
    assert missing_response.status_code == 503
    assert missing_response.json()["error"] == "GENERATION_RECOVERY_REQUIRED"


def test_trust_crop_brand_new_match_is_not_ready(tmp_path) -> None:
    anyio.run(_assert_not_ready, tmp_path)


async def _assert_not_ready(tmp_path) -> None:
    app = create_app(storage_root=tmp_path / "store", run_jobs_inline=True)
    storage = app.state.storage
    source = tmp_path / "tracking.json"
    source.write_text("[]", encoding="utf-8")
    match = storage.create_match("new", "tracking_json", source.name, source, MatchConfig())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        response = await client.get(f"/api/matches/{match.id}/trust-crops")

    assert response.status_code == 404
    assert response.json()["detail"] == "Frames or analytics not ready"


def test_trust_crop_missing_geometry_is_disclosed_without_hiding_other_reasons(
    tmp_path,
) -> None:
    anyio.run(_assert_missing_geometry, tmp_path)


async def _assert_missing_geometry(tmp_path) -> None:
    app = create_app(storage_root=tmp_path / "store", run_jobs_inline=True)
    storage = app.state.storage
    source = tmp_path / "tracking.json"
    source.write_text("[]", encoding="utf-8")
    match = storage.create_match("geometry", "tracking_json", source.name, source, MatchConfig())
    frames = [FrameData(frameId=i, timestamp=float(i), ball={"x": i * 3 % 100, "y": 0}) for i in range(40)]
    assignments = [
        BallOwnership(frameId=i, timestamp=float(i), team="my_team", trackId=i % 2)
        for i in range(40)
    ]
    _publish(storage, match.id, 1, frames=frames, assignments=assignments)
    storage.update_match_status(match.id, status="ready")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        response = await client.get(f"/api/matches/{match.id}/trust-crops")

    payload = response.json()
    assert response.status_code == 200
    assert payload["ballTeleportGeometryAvailable"] is False
    assert "CALIBRATION_UNAVAILABLE" in payload["ballTeleportReasonCodes"]
    assert any("track_switches" in crop["reasons"] for crop in payload["crops"])


def test_historical_trust_crop_uses_its_own_declared_dimensions(tmp_path) -> None:
    anyio.run(_assert_historical_dimensions, tmp_path)


async def _assert_historical_dimensions(tmp_path) -> None:
    app = create_app(storage_root=tmp_path / "store", run_jobs_inline=True)
    storage = app.state.storage
    source = tmp_path / "tracking.json"
    source.write_text("[]", encoding="utf-8")
    match = storage.create_match("dimensions", "tracking_json", source.name, source, MatchConfig())
    frames = [
        FrameData(frameId=0, timestamp=0, ball={"x": 50, "y": 0}, geometryAvailable=True,
                  coordinateProvenance={"inputConvention": {"space": "pitch_normalized_0_100"}, "outputConvention": "pitch_normalized_0_100"}),
        FrameData(frameId=1, timestamp=1, ball={"x": 50, "y": 20}, geometryAvailable=True,
                  coordinateProvenance={"inputConvention": {"space": "pitch_normalized_0_100"}, "outputConvention": "pitch_normalized_0_100"}),
    ]
    assignments = [
        BallOwnership(frameId=i, timestamp=float(i), team="my_team", trackId=1)
        for i in range(2)
    ]
    old = _publish(
        storage,
        match.id,
        1,
        frames=frames,
        assignments=assignments,
        config=MatchConfig(pitchLengthM=105, pitchWidthM=68),
    )
    _publish(
        storage,
        match.id,
        2,
        frames=frames,
        assignments=assignments,
        config=MatchConfig(pitchLengthM=105, pitchWidthM=100),
    )
    storage.update_match_status(match.id, status="ready")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        response = await client.get(
            f"/api/matches/{match.id}/trust-crops", params={"generationId": old.generationId}
        )

    payload = response.json()
    assert payload["ballTeleportGeometryAvailable"] is True
    assert payload["ballTeleportReasonCodes"] == []
    assert all("ball_teleport" not in crop["reasons"] for crop in payload["crops"])
