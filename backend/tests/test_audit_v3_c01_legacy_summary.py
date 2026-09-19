"""C01 legacy migration keeps all summary surfaces generation-coherent.

Fixtures intentionally bypass save_analytics to reproduce historical stored
50-percent defaults. There is no model inference or live data in these tests.
"""
from __future__ import annotations

import hashlib
import json

import pytest

from backend.app.schemas import MatchConfig, MatchSummary
from backend.app.storage import Storage

pytestmark = pytest.mark.integration


def _legacy(tmp_path, *, possession=50, team=None, mode="tracking_json"):
    storage = Storage(tmp_path / "store")
    source = tmp_path / "source.json"
    source.write_text("[]")
    match = storage.create_match("Legacy", mode, source.name, source, MatchConfig())
    root = storage.generations.root(match.id)
    summary = MatchSummary(
        possession=possession, myTeamDistance=None, enemyDistance=None,
        myTeamTopSpeed=None, enemyTopSpeed=None, myTeamSprints=None,
        enemySprints=None,
    )
    assignments = [] if team is None else [{
        "frameId": 0, "timestamp": 0.0, "team": team, "trackId": None,
    }]
    for name, value in {
        "frames.json": [], "events.json": [],
        "analytics.json": {"summary": summary.model_dump(mode="json"),
                           "ballAssignments": assignments,
                           "formationTimeline": [], "shots": []},
    }.items():
        (root / name).write_text(json.dumps(value))
    storage.update_match_status(match.id, status="ready")
    return storage, match.id, root


def _hashes(root):
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in ("frames.json", "events.json", "analytics.json")}


@pytest.mark.parametrize("team,possession,expected", [
    (None, 50, None), ("unassigned", 50, None), ("contested", 50, None),
    ("enemy", 0, 0), ("my_team", 55, 55),
])
def test_v3t07_v3t09_migration_normalises_candidate_not_originals(
    tmp_path, monkeypatch, team, possession, expected,
):
    storage, mid, root = _legacy(tmp_path, possession=possession, team=team)
    originals = _hashes(root)
    receipt = storage.recover_generations(mid)
    ref = storage.current_generation(mid)
    assert storage.load_analytics(mid)[0].possession == expected
    assert storage.list_matches_with_analytics()[0]["summary"]["possession"] == expected
    assert storage.get_match_summary_for_search(mid)["summary"]["possession"] == expected
    with storage._connect() as connection:
        row = connection.execute(
            "SELECT analytics_summary_json, analytical_generation_id FROM matches WHERE id=?", (mid,)
        ).fetchone()
    assert json.loads(row[0])["possession"] == expected
    assert row[1] == ref.generationId
    assert _hashes(root) == originals
    assert receipt["legacyArtifactDigests"] == originals

    reopened = Storage(storage.storage_root)
    assert reopened.current_generation(mid).generationId == ref.generationId
    assert _hashes(root) == originals
    # Migrated-v3 compact summaries need neither trajectories nor full analytics.
    read_json = reopened._read_json
    def compact_read(path):
        if path.name in {"analytics.json", "frames.json"}:
            raise AssertionError("Dashboard loaded full legacy analytics/trajectories")
        return read_json(path)
    monkeypatch.setattr(reopened, "_read_json", compact_read)
    monkeypatch.setattr(reopened, "_write_json", lambda *_: pytest.fail("GET wrote storage"))
    monkeypatch.setattr(reopened, "_sha256_file", lambda *_: pytest.fail("GET rehashed artifacts"))
    assert reopened.list_matches_with_analytics()[0]["summary"]["possession"] == expected


def test_v3t09_video_migration_does_not_promote_unverified_ball_signal(tmp_path):
    storage, mid, root = _legacy(tmp_path, mode="video", team="my_team")
    originals = _hashes(root)
    storage.recover_generations(mid)
    ref = storage.current_generation(mid)
    directory = root / "generations" / ref.generationId
    assert json.loads((directory / "summary.json").read_text())["ballSignalStatus"] == "untrusted"
    assert storage.load_analytics(mid)[0].ballSignalStatus == "untrusted"
    assert _hashes(root) == originals


def test_v3t07_earlier_migrated_generation_keeps_read_contract_without_mutation(tmp_path, monkeypatch):
    storage, mid, root = _legacy(tmp_path)
    storage.recover_generations(mid)
    ref = storage.current_generation(mid)
    manifest, directory = storage.generations.manifest(mid, ref.generationId)
    # Construct the precise earlier C01 format, then explicitly re-admit it.
    analytics = json.loads((root / "analytics.json").read_text())
    storage._write_json(directory / "analytics.json", analytics)
    storage._write_json(directory / "summary.json", analytics["summary"])
    manifest.algorithmVersions["legacy_import"] = "2"
    for name in ("analytics.json", "summary.json"):
        manifest.files[name] = storage._sha256_file(directory / name)
        manifest.fileMetadata[name]["byteSize"] = (directory / name).stat().st_size
    storage._write_json(directory / "manifest.json", manifest.model_dump(mode="json"))
    digest = storage._sha256_file(directory / "manifest.json")
    # Fixture edits are deliberately offline; production getters never do this.
    pointer = json.loads((root / "current_generation.json").read_text())
    pointer["manifestSha256"] = digest
    storage._write_json(root / "current_generation.json", pointer)
    storage.recover_generations(mid)
    before = {str(p): p.read_bytes() for p in root.rglob("*.json")}
    with storage._connect() as connection:
        indexed = json.loads(connection.execute(
            "SELECT analytics_summary_json FROM matches WHERE id=?", (mid,)
        ).fetchone()[0])
    assert indexed["possession"] is None
    monkeypatch.setattr(storage, "_write_json", lambda *_: pytest.fail("GET wrote storage"))
    monkeypatch.setattr(storage, "_sha256_file", lambda *_: pytest.fail("GET rehashed artifacts"))
    assert storage.list_matches_with_analytics()[0]["summary"]["possession"] is None
    assert storage.load_analytics(mid, generation_id=ref.generationId)[0].possession is None
    assert before == {str(p): p.read_bytes() for p in root.rglob("*.json")}
