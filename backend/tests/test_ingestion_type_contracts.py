"""Compatibility for typed observation, projection and reference containers."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from backend.app import coordinates, observation_inputs
from backend.app.coordinate_contracts import CoordinateConvention
from backend.app.report_contracts import validate_declared_references
from backend.app.semantic_commands import SemanticCommandError
from backend.app.workbench.contracts import CalibrationRevision
from backend.app.workbench.geometry import CalibrationProfile


@pytest.mark.parametrize("payload", [[], {}, None, True, 3, "plain", [{"frameId": 0}]])
def test_observation_reader_preserves_json_payload_and_exact_byte_binding(tmp_path, payload):
    raw = json.dumps(payload, ensure_ascii=False).encode() + b"\n"
    path = tmp_path / "observations.json"
    path.write_bytes(raw)
    result, binding, signature = observation_inputs._read(path, parse=True)
    assert result == payload
    assert binding == {"sha256": hashlib.sha256(raw).hexdigest(), "byteSize": len(raw)}
    assert signature == observation_inputs._signature(path.stat())
    assert path.read_bytes() == raw


@pytest.mark.parametrize("raw", [b"", b"[", b"\xff", b"[NaN]", b"Infinity", b"-Infinity"])
def test_observation_reader_retains_invalid_json_refusal(tmp_path, raw):
    path = tmp_path / "observations.json"
    path.write_bytes(raw)
    with pytest.raises(SemanticCommandError) as error:
        observation_inputs._read(path, parse=True)
    assert error.value.code == "INVALID_OBSERVATIONS"
    assert error.value.status_code == 409
    assert path.read_bytes() == raw


def test_hash_only_reader_does_not_parse_or_accumulate_media(tmp_path):
    path = tmp_path / "input.mp4"
    block = b"\xffnot-json" * 131072
    digest = hashlib.sha256()
    with path.open("wb") as handle:
        for _ in range(12):
            handle.write(block)
            digest.update(block)
    # Isolate the allocation measurement from other suites' worker threads.
    script = """
import json, runpy, sys, tracemalloc
from pathlib import Path
runpy.run_path('backend/tests/conftest.py')
from backend.app import observation_inputs
from backend.app.storage_remote import open_regular_file

def forbidden_parse(*args, **kwargs):
    raise AssertionError('hash-only read parsed media')

observation_inputs.json.loads = forbidden_parse
tracemalloc.start()
try:
    payload, binding, _ = observation_inputs._read(Path(sys.argv[1]))
    _, peak = tracemalloc.get_traced_memory()
finally:
    tracemalloc.stop()
print(json.dumps({'payload': payload, 'binding': binding, 'peak': peak}))
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(path)],
        cwd=Path(__file__).resolve().parents[2], text=True, capture_output=True,
        timeout=30, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    measured = json.loads(result.stdout)
    assert measured["payload"] is None
    assert measured["binding"] == {"sha256": digest.hexdigest(), "byteSize": path.stat().st_size}
    # Two overlapping one-megabyte read buffers are normal; retaining the whole file is not.
    assert measured["peak"] < 4 * 1024 * 1024


@pytest.mark.parametrize("kind, code", [("missing", "CACHE_MISS"), ("directory", "INVALID_OBSERVATIONS"), ("symlink", "INVALID_OBSERVATIONS")])
def test_observation_reader_retains_regular_file_boundary(tmp_path, kind, code):
    path = tmp_path / "observations.json"
    if kind == "directory":
        path.mkdir()
    elif kind == "symlink":
        target = tmp_path / "target.json"
        target.write_text("[]")
        path.symlink_to(target)
    with pytest.raises(SemanticCommandError) as error:
        observation_inputs._read(path, parse=True)
    assert error.value.code == code
    assert error.value.status_code == 409


@pytest.mark.parametrize("parse", [False, True])
def test_observation_read_mutation_is_refused_and_descriptor_closed(tmp_path, monkeypatch, parse):
    path = tmp_path / "observations.json"
    path.write_bytes(b"[]")
    fdopen = os.fdopen
    observed = []

    class MutatingReader:
        def __init__(self, descriptor, *args, **kwargs):
            self.handle = fdopen(descriptor, *args, **kwargs)
            self.descriptor = descriptor
            self.changed = False
            observed.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.handle.close()

        def fileno(self):
            return self.handle.fileno()

        def read(self, size):
            value = self.handle.read(size)
            if not self.changed:
                self.changed = True
                with path.open("ab") as writer:
                    writer.write(b" ")
            return value

    monkeypatch.setattr(observation_inputs.os, "fdopen", MutatingReader)
    with pytest.raises(SemanticCommandError) as error:
        observation_inputs._read(path, parse=parse)
    assert error.value.code == "OBSERVATIONS_CHANGED_DURING_READ"
    assert len(observed) == 1 and observed[0].handle.closed
    with pytest.raises(OSError):
        os.fstat(observed[0].descriptor)


@pytest.mark.parametrize("payload, code", [
    (None, "INVALID_TRACKING_ENVELOPE"),
    (3, "INVALID_TRACKING_ENVELOPE"),
    ({}, "COORDINATE_CONVENTION_REQUIRED"),
    ({"schemaVersion": 2, "format": "guerilla_tracking_v2", "frames": [], "rows": []}, "INVALID_TRACKING_ENVELOPE"),
    ({"schemaVersion": 2, "format": "guerilla_tracking_v2", "rows": None}, "INVALID_TRACKING_ENVELOPE"),
    ({"schemaVersion": 2, "format": "guerilla_tracking_v2", "rows": []}, "COORDINATE_CONVENTION_REQUIRED"),
    ([{"x": 0, "y": 0}], "COORDINATE_CONVENTION_REQUIRED"),
])
def test_tracking_import_refuses_before_invalid_rows_can_be_normalized(payload, code):
    before = copy.deepcopy(payload)
    with pytest.raises(SemanticCommandError) as error:
        coordinates.import_tracking(payload)
    assert error.value.code == code
    assert error.value.status_code == 409
    assert payload == before


def _revision(*, end=None):
    profile = CalibrationProfile(
        calibrationId="typed-source-fixture", cameraModel="planar_homography",
        cameraSide="touchline_north", pitchLengthM=100., pitchWidthM=60.,
        sourceWidth=1000, sourceHeight=600, sourceStreamId="video:0",
        homography=[[.1, 0., 0.], [0., .1, 0.], [0., 0., 1.]],
    )
    return CalibrationRevision(
        revisionId="revision-a", profile=profile.model_dump(mode="json"), evaluation={},
        accepted=True, measured=True, sourceSha256="a" * 64,
        validInterval={"start": 0., "end": end}, createdAt="2026-09-25T00:00:00Z",
        pitchLengthM=100., pitchWidthM=60.,
    )


def _row(fid=0):
    return {
        "Frame_ID": fid, "Timestamp": fid / 25, "PTS": fid, "TimeBaseNum": 1, "TimeBaseDen": 25,
        "Entity_Type": "player", "Track_ID": 7, "Team": "my_team", "X": 9., "Y": 9., "Conf": .9,
        "Source_X1": 100., "Source_Y1": 100., "Source_X2": 140., "Source_Y2": 180.,
        "Source_Width": 1000, "Source_Height": 600,
    }


def test_projection_provenance_keeps_per_frame_clock_dimensions_and_interval(tmp_path):
    rows = [_row(0), _row(1)]
    before = copy.deepcopy(rows)
    revision = _revision(end=1 / 25)
    frames = coordinates.project_video_rows(rows, revision)
    assert [(f.frameId, f.timestamp, f.geometryAvailable) for f in frames] == [(0, 0., True), (1, 1 / 25, False)]
    first, second = [f.coordinateProvenance for f in frames]
    assert first["sourceClock"] == {"PTS": 0, "TimeBaseNum": 1, "TimeBaseDen": 25}
    assert second["sourceClock"]["PTS"] == 1
    assert first["sourceDimensions"] == {"width": 1000, "height": 600}
    assert "sourceDimensions" not in second
    assert first["calibrationRevision"] == second["calibrationRevision"] == "revision-a"
    assert first["migration"] == "guerilla_video_source_boxes_v1"
    assert first["reasonCodes"] == []
    assert second["reasonCodes"] == ["CALIBRATION_INTERVAL_UNAVAILABLE"]
    assert frames[1].myTeam == frames[1].enemies == frames[1].unassignedPlayers == []
    assert rows == before
    first["reasonCodes"].append("independence-probe")
    assert second["reasonCodes"] == ["CALIBRATION_INTERVAL_UNAVAILABLE"]


def test_provenance_dictionaries_remain_independent_and_json_serializable():
    convention = CoordinateConvention(space="pitch_normalized_0_100")
    a = coordinates._provenance(convention, migration="legacy")
    b = coordinates._provenance(convention, migration="legacy")
    assert json.loads(json.dumps(a)) == {
        "schemaVersion": 1, "inputConvention": convention.model_dump(mode="json"),
        "outputConvention": "pitch_normalized_0_100", "calibrationRevision": None,
        "migration": "legacy", "reasonCodes": [],
    }
    a["reasonCodes"].append("probe")
    a["inputConvention"]["space"] = "unknown"
    assert b["reasonCodes"] == []
    assert b["inputConvention"]["space"] == convention.space


@pytest.mark.parametrize("field", ["evidence", "evidenceIds", "references", "claimedEvidenceIds", "knownEvidenceIds"])
def test_declared_reference_collection_keeps_order_duplicates_and_scope(field):
    ref = {"matchId": "m", "generationId": "g", "kind": "frame", "localId": "7"}
    package = SimpleNamespace(match_id="m", generation_id="g", aliases={"e0": ref})
    payload = {"prose": "event:unverified", "nested": [{field: ["e0", ref, "e0"]}]}
    before = copy.deepcopy(payload)
    found = validate_declared_references(payload, package)
    assert found == [ref, ref, ref]
    assert payload == before
    found[0]["localId"] = "changed-copy"
    assert package.aliases["e0"]["localId"] == "7"
    assert found[1]["localId"] == found[2]["localId"] == "7"


@pytest.mark.parametrize("value, code", [
    ({"evidence": "e0"}, "MALFORMED_EVIDENCE_REFERENCE"),
    ({"nested": {"references": ["missing"]}}, "UNKNOWN_EVIDENCE_REFERENCE"),
    ({"evidence": [{"matchId": "other", "generationId": "g", "kind": "frame", "localId": "7"}]}, "EVIDENCE_SCOPE_MISMATCH"),
])
def test_invalid_declared_reference_never_becomes_an_empty_collection(value, code):
    ref = {"matchId": "m", "generationId": "g", "kind": "frame", "localId": "7"}
    package = SimpleNamespace(match_id="m", generation_id="g", aliases={"e0": ref})
    with pytest.raises(ValueError, match=code):
        validate_declared_references(value, package)


def test_reference_free_prose_stays_reference_free():
    package = SimpleNamespace(match_id="m", generation_id="g", aliases={})
    assert validate_declared_references({"summary": "frame:7", "anything": [7, None, "event:3"]}, package) == []
