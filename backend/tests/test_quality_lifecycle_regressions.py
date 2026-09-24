"""Cleanup diagnostics must not change outcomes or disclose provider payloads."""
from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest

from backend.app import daytona, remote_contracts, runtime_options
from backend.app.gpu_worker import _progress_collector
from backend.app.storage import _ClosingConnection
from backend.app.storage_review import ReviewStorage
from backend.app.generations import GenerationRecoveryRequired
from backend.app.workbench.jobs import DurableJobLedger

SECRET = "provider-token=do-not-log-this"


def fail(*args, **kwargs):
    raise RuntimeError(SECRET)


def assert_safe_warning(caplog, fragment):
    assert fragment in caplog.text
    assert SECRET not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.parametrize("kind", ["storage", "ledger"])
def test_rollback_warning_preserves_original_failure(kind, caplog):
    closed = []
    connection = SimpleNamespace(rollback=fail, close=lambda: closed.append(True))
    original = ValueError("original transaction failure")
    if kind == "storage":
        context = _ClosingConnection(connection)
    else:
        ledger = object.__new__(DurableJobLedger)
        ledger._open_connection = lambda: connection
        context = ledger._connect()
    with pytest.raises(ValueError) as raised:
        with context:
            raise original
    assert raised.value is original
    assert closed == [True]
    assert_safe_warning(caplog, "rollback failed")


def test_failed_json_rollback_retains_uncertain_outcome(tmp_path, monkeypatch, caplog):
    destination = tmp_path / "receipt.json"
    destination.write_text("published")
    monkeypatch.setattr(type(destination), "unlink", fail)
    monkeypatch.setattr(remote_contracts, "_fsync_directory", fail)
    assert remote_contracts._rollback_published_json(destination) is False
    assert destination.read_text() == "published"
    assert_safe_warning(caplog, "published JSON rollback")


def test_sdk_unreturned_cleanup_logs_without_claiming_absence(caplog):
    adapter = object.__new__(daytona._SdkClient)
    calls = []
    def failure(operation):
        def run(*args, **kwargs):
            calls.append(operation)
            raise RuntimeError(SECRET)
        return run
    adapter.delete = failure("delete")
    adapter.get = failure("get")
    assert adapter._cleanup_unreturned_sandbox(SimpleNamespace(id="test"), 1) is False
    assert calls == ["delete", "get"] * 3
    assert_safe_warning(caplog, "sandbox cleanup")


def test_cleanup_retry_failure_keeps_all_attempts(caplog):
    attempts = []
    def delete(*args, **kwargs):
        attempts.append(True)
        fail()
    policy = SimpleNamespace(cleanup_attempts=3, delete_timeout_seconds=1)
    assert daytona._cleanup(SimpleNamespace(delete=delete), object(), policy, fail) is False
    assert len(attempts) == 3
    assert_safe_warning(caplog, "cleanup retry wait failed")


def test_progress_output_failure_keeps_validated_event(caplog):
    events, state, callback = _progress_collector("quality-job", output=SimpleNamespace(write=fail))
    callback({"stage": "tracking", "progress": 0.4, "message": "processed"})
    assert len(events) == 1
    assert state["error"] is False
    assert state["progress"] == 0.4
    assert_safe_warning(caplog, "live progress output failed")


def test_stream_close_failure_keeps_verified_artifact(tmp_path, caplog):
    content = b"verified artifact"
    class Stream:
        def __iter__(self):
            return iter([content])
        close = staticmethod(fail)
    reference = runtime_options.ArtifactReference(
        kind="object_store", sha256=hashlib.sha256(content).hexdigest(), size_bytes=len(content),
    )
    destination = tmp_path / "artifact.bin"
    assert runtime_options._atomic_materialize(reference, destination, Stream(), max_artifact_bytes=100) == destination
    assert destination.read_bytes() == content
    assert_safe_warning(caplog, "artifact stream close failed")


def test_invalid_hostname_suppresses_incidental_ip_parse_failure():
    with pytest.raises(runtime_options.RuntimeOptionsError, match="valid hostname") as raised:
        runtime_options.normalize_object_store_origin("https://invalid_host.example")
    assert raised.value.__suppress_context__ is True


def test_missing_explicit_playlist_generation_preserves_cause():
    owner = SimpleNamespace(get_match=fail)
    cause = KeyError("missing match")
    def missing(mid):
        raise cause
    owner.get_match = missing
    review = ReviewStorage(owner, corrupt_error=RuntimeError, uncertain_delete_error=OSError)
    item = {"annotationId": "a", "matchId": "m", "generationId": "g", "frameStart": 0,
            "frameEnd": 1, "timestampStart": 0, "timestampEnd": 1, "label": "clip"}
    with pytest.raises(GenerationRecoveryRequired) as raised:
        with review.bound_bundle_items([item]):
            pytest.fail("missing generation must not produce a bundle")
    assert raised.value.__cause__ is cause


def test_incomplete_legacy_snapshot_preserves_missing_pointer_cause(tmp_path):
    from backend.app.generations import GenerationStore
    store = GenerationStore(SimpleNamespace(storage_root=tmp_path))
    store.prepare("legacy")
    (store.root("legacy") / "frames.json").write_text("[]")
    with pytest.raises(GenerationRecoveryRequired, match="Incomplete legacy snapshot") as raised:
        store.recover("legacy")
    assert isinstance(raised.value.__cause__, FileNotFoundError)


def test_event_identifier_digest_stays_stable_and_declares_nonsecurity_use(monkeypatch):
    from backend.app.workbench.events import with_stable_event_id
    original_sha1 = hashlib.sha1
    expected = "ev_" + original_sha1(b"pass|my_team|1.2|7").hexdigest()[:16]
    options = []
    def sha1(data, **kwargs):
        options.append(kwargs)
        return original_sha1(data, **kwargs)
    monkeypatch.setattr(hashlib, "sha1", sha1)
    event = SimpleNamespace(fromTrackId=7, toTrackId=None, type="pass", team="my_team", timestamp=1.2,
                            model_copy=lambda *, update: update)
    assert with_stable_event_id(event)["eventId"] == expected
    assert options == [{"usedforsecurity": False}]
