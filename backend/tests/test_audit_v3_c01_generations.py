"""C01 storage regressions. Synthetic observations, no providers or workers."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.schemas import FrameData, MatchConfig, MatchSummary
from backend.app.storage import Storage

pytestmark = pytest.mark.integration


def summary(value: int = 1) -> MatchSummary:
    return MatchSummary(possession=None, myTeamDistance=value, enemyDistance=None,
                        myTeamTopSpeed=None, enemyTopSpeed=None,
                        myTeamSprints=None, enemySprints=None)


def publish(storage, match_id, value=1, **kwargs):
    return storage.publish_generation(
        match_id, frames=[FrameData(frameId=value, timestamp=float(value))],
        summary=summary(value), assignments=[], formation_timeline=[], shots=[],
        events=[], correction_head="none", **kwargs)


def seed(tmp_path):
    storage = Storage(tmp_path / "store")
    source = tmp_path / "source.json"
    source.write_text("[]")
    match = storage.create_match("C01", "tracking_json", source.name, source, MatchConfig())
    ref = publish(storage, match.id)
    storage.update_match_status(match.id, status="ready")
    return storage, match.id, ref


def test_v3t01_reads_never_write_hash_or_prune(tmp_path, monkeypatch):
    storage, mid, _ = seed(tmp_path)
    calls = []
    original_write = storage._write_json
    original_hash = storage._sha256_file
    def write(*args, **kwargs):
        calls.append("write")
        return original_write(*args, **kwargs)
    def digest(*args, **kwargs):
        calls.append("hash")
        return original_hash(*args, **kwargs)
    monkeypatch.setattr(storage, "_write_json", write)
    monkeypatch.setattr(storage, "_sha256_file", digest)
    for _ in range(3):
        storage.current_generation(mid)
        storage.load_frames(mid)
        storage.load_events(mid)
        storage.load_analytics(mid)
    assert calls == [], f"Routine reads performed mutation/hash operations: {calls}"


def test_v3t03_history_is_not_deleted_by_read_or_restart(tmp_path):
    storage, mid, old = seed(tmp_path)
    publish(storage, mid, 2)
    storage.load_frames(mid)
    reopened = Storage(storage.storage_root)
    assert reopened.load_frames(mid, generation_id=old.generationId)[0].frameId == 1


def test_v3t07_stale_sql_summary_is_not_current_truth(tmp_path):
    storage, mid, ref = seed(tmp_path)
    with storage._connect() as connection:
        connection.execute("UPDATE matches SET analytics_summary_json=? WHERE id=?",
                           (summary(999).model_dump_json(), mid))
    result = storage.list_matches_with_analytics()
    assert result[0]["summary"]["myTeamDistance"] == 1
    with storage._connect() as connection:
        row = connection.execute("SELECT analytics_summary_json FROM matches WHERE id=?", (mid,)).fetchone()
    assert json.loads(row[0])["myTeamDistance"] == 999, "GET secretly repaired SQL"

# New contract tests use independent interpreters and pipe barriers. They never
# launch perception, workers or providers; only the existing analytical code.
import hashlib
import multiprocessing
import os
import sys
import types
from dataclasses import dataclass

from backend.app.generations import GenerationRecoveryRequired, RetentionBusy, StaleGeneration


def _child_setup():
    for key in list(os.environ):
        if any(word in key.upper() for word in ("API_KEY", "ACCESS_TOKEN", "SECRET", "DAYTONA", "RUNPOD")):
            os.environ.pop(key, None)
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    os.environ["VERIFY_DAYTONA"] = "0"
    os.environ["ALLOW_DAYTONA_MUTATION"] = "0"
    # An import stub only. Inference itself is forbidden, not faked as success.
    m = types.ModuleType("ultralytics")
    class NoModel:
        def __init__(self, *_a, **_k):
            raise AssertionError("C01 must not instantiate a model")
    m.YOLO = NoModel
    sys.modules["ultralytics"] = m


def _reader(root, mid, conn):
    _child_setup()
    try:
        storage = Storage(Path(root))
        with storage.generation_snapshot(mid) as ref:
            conn.send(("pinned", ref.generationId))
            assert conn.recv() == "read"
            conn.send({"generation": ref.generationId,
                       "frame": storage.load_frames(mid)[0].frameId,
                       "events": len(storage.load_events(mid)),
                       "distance": storage.load_analytics(mid)[0].myTeamDistance,
                       "direction": storage.get_match(mid).config.attackDirection})
    except BaseException as exc:
        conn.send(("error", repr(exc)))
        raise
    finally:
        conn.close()


def _writer(root, mid, conn, fault=None, correction=False):
    _child_setup()
    storage = Storage(Path(root))
    def barrier(point):
        if point == fault:
            conn.send(("fault", point))
            conn.recv()  # Parent sends a real SIGKILL while the child is paused.
    if fault:
        storage._review_test_fault = barrier
    try:
        if correction:
            from backend.app.review_service import ReviewService
            ReviewService._test_fault = staticmethod(barrier)
            result = storage.submit_correction(mid, kind="team_mapping", payload={"swap": True})
            conn.send(("done", result.appliedGeneration))
        else:
            result = publish(storage, mid, 2, effective_config=MatchConfig(attackDirection="right_to_left"))
            conn.send(("done", result.generationId))
    finally:
        conn.close()


@dataclass
class Process:
    process: object
    pipe: object

    def receive(self):
        assert self.pipe.poll(20), "Child did not reach its deterministic barrier"
        value = self.pipe.recv()
        assert not (isinstance(value, tuple) and value[0] == "error"), value
        return value

    def finish(self):
        self.process.join(20)
        assert not self.process.is_alive(), "Child did not terminate"
        assert self.process.exitcode == 0


@pytest.fixture
def children():
    active = []
    def start(target, *args, **kwargs):
        ctx = multiprocessing.get_context("spawn")
        parent, child = ctx.Pipe()
        process = ctx.Process(target=target, args=(*args, child), kwargs=kwargs)
        process.start()
        child.close()
        pair = Process(process, parent)
        active.append(pair)
        return pair
    yield start
    for pair in active:
        if pair.process.is_alive():
            pair.process.kill()
        pair.process.join(10)
        pair.pipe.close()


def test_v3t02_two_process_reader_keeps_n_while_writer_commits(tmp_path, children):
    storage, mid, old = seed(tmp_path)
    reader = children(_reader, str(storage.storage_root), mid)
    assert reader.receive() == ("pinned", old.generationId)
    writer = children(_writer, str(storage.storage_root), mid)
    kind, new_id = writer.receive()
    assert kind == "done" and new_id != old.generationId
    writer.finish()  # Publication must finish before the old reader is released.
    reader.pipe.send("read")
    assert reader.receive() == {"generation": old.generationId, "frame": 1, "events": 0,
                                "distance": 1, "direction": "left_to_right"}
    reader.finish()
    with storage.generation_snapshot(mid) as current:
        assert current.generationId == new_id
        assert storage.load_frames(mid)[0].frameId == 2
        assert storage.get_match(mid).config.attackDirection == "right_to_left"


def test_v3t04_retention_dry_run_reference_rollback_and_active_pin(tmp_path, children):
    storage, mid, oldest = seed(tmp_path)
    referenced = publish(storage, mid, 2)
    rollback = publish(storage, mid, 3)
    current = publish(storage, mid, 4)
    report = storage.generations.root(mid) / "reports" / "historical.json"
    report.parent.mkdir()
    report.write_text(json.dumps({"generationId": referenced.generationId}))
    plan = storage.retain_generations(mid)
    assert plan["dryRun"] and not plan["removed"]
    assert plan["eligible"] == [oldest.generationId]
    assert set(plan["protected"]) >= {referenced.generationId, rollback.generationId, current.generationId}
    reader = children(_reader, str(storage.storage_root), mid)
    assert reader.receive()[0] == "pinned"
    with pytest.raises(RetentionBusy):
        storage.retain_generations(mid, apply=True)
    assert storage.load_frames(mid, generation_id=oldest.generationId)[0].frameId == 1
    reader.pipe.send("read")
    reader.receive()
    reader.finish()
    applied = storage.retain_generations(mid, apply=True, generation_ids=[oldest.generationId])
    assert applied["removed"] == [oldest.generationId]
    assert not (storage.generations.root(mid) / "generations" / oldest.generationId).exists()
    assert storage.load_frames(mid, generation_id=referenced.generationId)[0].frameId == 2
    assert storage.current_generation(mid).generationId == current.generationId


@pytest.mark.parametrize("fault", ["during_generation_write", "before_pointer_publish", "after_pointer_publish"])
def test_v3t05_sigkill_without_pending_commands_recovers_pointer_only(tmp_path, children, fault):
    storage, mid, old = seed(tmp_path)
    writer = children(_writer, str(storage.storage_root), mid, fault=fault)
    assert writer.receive() == ("fault", fault)
    writer.process.kill()
    writer.process.join(10)
    assert writer.process.exitcode != 0
    root = storage.generations.root(mid)
    dirs_before = {p.name for p in (root / "generations").iterdir()}
    assert len(dirs_before) == 2
    restarted = Storage(storage.storage_root)
    first = restarted.recover_generations(mid)
    second = restarted.recover_generations(mid)
    assert first == second
    ref = restarted.current_generation(mid)
    after_commit = fault == "after_pointer_publish"
    assert (ref.generationId != old.generationId) is after_commit
    assert restarted.load_frames(mid)[0].frameId == (2 if after_commit else 1)
    assert restarted.get_match(mid).config.attackDirection == ("right_to_left" if after_commit else "left_to_right")
    with restarted._connect() as connection:
        row = connection.execute("SELECT analytical_generation_id,analytics_summary_json FROM matches WHERE id=?", (mid,)).fetchone()
    assert row[0] == ref.generationId
    assert json.loads(row[1])["myTeamDistance"] == (2 if after_commit else 1)
    assert {p.name for p in (root / "generations").iterdir()} == dirs_before
    assert restarted.list_corrections(mid) == []


@pytest.mark.parametrize("fault", ["after_log_commit", "during_generation_write", "after_pointer_publish", "before_applied_marker"])
def test_v3t06_sigkill_pending_swap_recovers_once(tmp_path, children, fault):
    from backend.tests.test_audit_v2_h02_review import install_raw_row_match, _team_for_track
    storage = Storage(tmp_path / "store")
    mid = install_raw_row_match(storage, tmp_path)
    assert _team_for_track(storage, mid, 7) == "my_team"
    writer = children(_writer, str(storage.storage_root), mid, fault=fault, correction=True)
    assert writer.receive() == ("fault", fault)
    pointer_at_kill = json.loads((storage.generations.root(mid) / "current_generation.json").read_text())
    writer.process.kill()
    writer.process.join(10)
    assert writer.process.exitcode != 0
    restarted = Storage(storage.storage_root)
    assert _team_for_track(restarted, mid, 7) == "enemy"
    ref = restarted.current_generation(mid)
    if fault in {"after_pointer_publish", "before_applied_marker"}:
        assert ref.generationId == pointer_at_kill["generationId"]
    history = restarted.list_corrections(mid)
    assert len(history) == 1 and history[0]["applyState"] == "applied"
    assert history[0]["appliedGeneration"] == ref.generationId
    manifest, _ = restarted.generations.manifest(mid, ref.generationId)
    assert manifest.includedCommandIds == [history[0]["commandId"]]
    assert manifest.commandSetDigest == restarted.generations.command_metadata(mid)[1]
    paths_before = sorted(p.name for p in (restarted.generations.root(mid) / "generations").iterdir())
    restarted.recover_generations(mid)
    second = Storage(storage.storage_root)
    assert second.current_generation(mid).generationId == ref.generationId
    assert _team_for_track(second, mid, 7) == "enemy"
    assert sorted(p.name for p in (second.generations.root(mid) / "generations").iterdir()) == paths_before


def test_v3t07_post_commit_index_error_does_not_roll_back_or_restore_consent(tmp_path, monkeypatch):
    storage, mid, old = seed(tmp_path)
    def fail(*_args):
        raise OSError("SQL unavailable")
    monkeypatch.setattr(storage.generations, "refresh_index", fail)
    ref = publish(storage, mid, 2, effective_config=MatchConfig(attackDirection="right_to_left"))
    assert ref.recoveryRequired and ref.generationId != old.generationId
    with storage._connect() as connection:
        row = connection.execute("SELECT config_json, analytical_generation_id FROM matches WHERE id=?", (mid,)).fetchone()
        config = json.loads(row[0])
        config["rights"]["cloudPermission"] = False
        connection.execute("UPDATE matches SET config_json=? WHERE id=?", (json.dumps(config), mid))
    assert row[1] == old.generationId
    assert storage.get_match(mid).config.attackDirection == "right_to_left"
    assert storage.load_analytics(mid)[0].myTeamDistance == 2
    monkeypatch.undo()
    storage.recover_generations(mid)
    assert storage.current_generation(mid).generationId == ref.generationId
    assert storage.get_match(mid).config.rights.cloudPermission is False
    with storage._connect() as connection:
        repaired = connection.execute("SELECT analytical_generation_id FROM matches WHERE id=?", (mid,)).fetchone()
    assert repaired[0] == ref.generationId


@pytest.mark.parametrize("writer", ["frames", "events", "analytics"])
def test_v3t08_replacement_preserves_provenance_and_invalidates_derived_identity(tmp_path, writer):
    storage, mid, _ = seed(tmp_path)
    # Non-null synthetic provenance, not a vacuous None-preservation test.
    root = storage.generations.root(mid)
    observations = root / "review_base_frames.json"
    observations.write_text("[]")
    initial, _ = storage.generations.manifest(mid, storage.current_generation(mid).generationId)
    upstream = initial.model_copy(update={
        "identityRevision": "synthetic-identity-revision",
        "observationDigest": hashlib.sha256(observations.read_bytes()).hexdigest(),
        "detectionIdentity": hashlib.sha256(b"synthetic-detector").hexdigest(),
        "trackingIdentity": hashlib.sha256(b"synthetic-association").hexdigest(),
        "algorithmVersions": {"synthetic_fixture": "1"},
    })
    calibration = storage._new_calibration_revision(mid, profile={
        "calibrationId": "synthetic", "cameraModel": "planar_homography",
        "pitchLengthM": 100.0, "pitchWidthM": 60.0,
        "homography": [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]],
    }, evaluation={"accepted": False, "measured": False})
    old = publish(storage, mid, 2, stale=["tactical_report", "drills"],
                  provenance=upstream, calibration_data=calibration)
    manifest, directory = storage.generations.manifest(mid, old.generationId)
    before = manifest.model_dump(mode="json")
    if writer == "frames":
        storage.save_frames(mid, [FrameData(frameId=33, timestamp=33)])
    elif writer == "events":
        from backend.app.schemas import DetectedEvent
        storage.save_events(mid, [DetectedEvent(type="pass", frameId=2, timestamp=2,
                                               team="my_team", description="Synthetic fixture")])
    else:
        _, assignments, formations, shots = storage.load_analytics(mid)
        storage.save_analytics(mid, summary(3), assignments, formations, shots)
    new = storage.current_generation(mid)
    after, _ = storage.generations.manifest(mid, new.generationId)
    assert new.generationId != old.generationId and after.parentGenerationId == old.generationId
    for field in ("effectiveConfig", "semanticConfigRevision", "calibrationRevision", "calibrationData",
                  "observationDigest", "sourceIdentity", "stale", "includedCommandIds", "commandSetDigest",
                  "identityRevision", "detectionIdentity", "trackingIdentity", "algorithmVersions"):
        assert getattr(after, field) == before[field]
    assert after.artifactStates["tactical_report"] == "stale"
    assert after.projectionIdentity is None and after.reviewedIdentity is None and after.reportIdentity is None
    assert directory.exists()


@pytest.mark.parametrize("corruption", ["missing_pointer", "malformed_pointer", "missing_events", "changed_events"])
def test_v3t09_corruption_never_guesses_or_returns_empty_events(tmp_path, corruption):
    storage, mid, old = seed(tmp_path)
    publish(storage, mid, 2)
    ref = storage.current_generation(mid)
    root = storage.generations.root(mid)
    directory = root / "generations" / ref.generationId
    if corruption == "missing_pointer":
        (root / "current_generation.json").unlink()
    elif corruption == "malformed_pointer":
        (root / "current_generation.json").write_text("{")
    elif corruption == "missing_events":
        (directory / "events.json").unlink()
    else:
        (directory / "events.json").write_text('[{"bad":true}]')
    with pytest.raises(GenerationRecoveryRequired):
        storage.load_events(mid)
    restarted = Storage(storage.storage_root)
    with pytest.raises(GenerationRecoveryRequired):
        restarted.load_events(mid)
    assert (root / "generations" / old.generationId).exists()
    assert (root / "generations" / ref.generationId).exists()


def test_v3t09_explicit_legacy_migration_preserves_originals(tmp_path):
    storage = Storage(tmp_path / "store")
    source = tmp_path / "input.json"
    source.write_text("[]")
    match = storage.create_match("Legacy", "tracking_json", source.name, source, MatchConfig())
    root = storage.generations.root(match.id)
    storage.save_frames(match.id, [FrameData(frameId=1, timestamp=1)])
    storage.save_events(match.id, [])
    storage.save_analytics(match.id, summary(), [], [], [])
    paths = [root / name for name in ("frames.json", "events.json", "analytics.json")]
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    with pytest.raises(FileNotFoundError):
        storage.current_generation(match.id)
    assert not (root / "generations").exists()
    receipt = storage.recover_generations(match.id)
    assert receipt["status"] == "migrated"
    ref = storage.current_generation(match.id)
    manifest, _ = storage.generations.manifest(match.id, ref.generationId)
    assert manifest.effectiveConfig is None and manifest.observationDigest is None
    assert manifest.artifactStates["analytical_configuration"] == "unknown"
    assert before == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    assert Storage(storage.storage_root).current_generation(match.id).generationId == ref.generationId


def test_v3t09_incomplete_legacy_and_stale_parent_refuse_without_mutation(tmp_path):
    storage, mid, old = seed(tmp_path)
    new = publish(storage, mid, 2)
    root = storage.generations.root(mid)
    before = sorted(p.name for p in (root / "generations").iterdir())
    with pytest.raises(StaleGeneration):
        publish(storage, mid, 3, expected_parent=old.generationId)
    assert sorted(p.name for p in (root / "generations").iterdir()) == before
    assert storage.current_generation(mid).generationId == new.generationId
    legacy = "unpublished"
    storage.generations.prepare(legacy)
    (storage.generations.root(legacy) / "frames.json").write_text("[]")
    with pytest.raises(GenerationRecoveryRequired):
        storage.recover_generations(legacy)
    assert not (storage.generations.root(legacy) / "current_generation.json").exists()


def test_v3t01_api_read_provenance_and_history_are_read_only(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.main import create_app
    storage, mid, first = seed(tmp_path)
    second = publish(storage, mid, 2)
    app = create_app(storage_root=storage.storage_root, run_jobs_inline=False)
    def unexpected(*_a, **_k):
        raise AssertionError("GET must not write or hash artifacts")
    monkeypatch.setattr(app.state.storage, "_write_json", unexpected)
    monkeypatch.setattr(app.state.storage, "_sha256_file", unexpected)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        for endpoint in ("frames", "events", "analytics"):
            current = client.get(f"/api/matches/{mid}/{endpoint}")
            assert current.status_code == 200
            assert current.json()["generationId"] == second.generationId
            historical = client.get(f"/api/matches/{mid}/{endpoint}", params={"generationId": first.generationId})
            assert historical.status_code == 200
            assert historical.json()["generationId"] == first.generationId
        missing = app.state.storage.generations.root(mid) / "generations" / second.generationId / "events.json"
        missing.unlink()  # Deliberate corruption; read must fail, not return [].
        assert client.get(f"/api/matches/{mid}/events").status_code == 503


def test_v3t05_import_cleanup_failure_does_not_commit_or_rollback_a_pointer(tmp_path):
    storage, mid, before = seed(tmp_path)
    with pytest.raises(OSError, match="cleanup"):
        with storage.remote_result_import(mid):
            candidate = publish(storage, mid, 2)
            assert storage.current_generation(mid).generationId == before.generationId
            raise OSError("cleanup failed")
    assert storage.current_generation(mid).generationId == before.generationId
    assert (storage.generations.root(mid) / "generations" / candidate.generationId).exists()
    with storage.remote_result_import(mid):
        candidate = publish(storage, mid, 3)
        assert storage.current_generation(mid).generationId == before.generationId
    assert storage.current_generation(mid).generationId == candidate.generationId
    assert storage.load_frames(mid)[0].frameId == 3


def test_v3t09_identifiers_and_immutable_mutations_fail_closed(tmp_path):
    storage, mid, ref = seed(tmp_path)
    for bad in ("../escape", "/etc/passwd", "gen/../../escape", "gen\\escape"):
        with pytest.raises(GenerationRecoveryRequired):
            storage.load_frames(mid, generation_id=bad)
    with storage.generation_snapshot(mid):
        path = storage.generations.root(mid) / "generations" / ref.generationId / "events.json"
        before = path.stat()
        path.write_bytes(b"{}")  # Same size as []; restore mtime to test ctime/inode seal.
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        with pytest.raises(GenerationRecoveryRequired):
            storage.load_events(mid)
    # Corrupt authority must not turn compatibility writers back into flat-file writers.
    (storage.generations.root(mid) / "current_generation.json").unlink()
    with pytest.raises(GenerationRecoveryRequired):
        storage.save_events(mid, [])
    assert not (storage.generations.root(mid) / "events.json").exists()
