from __future__ import annotations

import errno
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.storage import Storage
from backend.app.schemas import CreateAnnotationRequest, CreateIssueRequest, MatchConfig


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    return Storage(tmp_path)


@pytest.fixture
def match_id(storage: Storage) -> str:
    input_path = storage.save_upload("tracking.json", b"[]")
    return storage.create_match(
        "Annotation test", "tracking_json", "tracking.json", input_path, MatchConfig()
    ).id


def annotation_request() -> CreateAnnotationRequest:
    return CreateAnnotationRequest(
        type="note",
        frameStart=10,
        frameEnd=20,
        timestampStart=2.0,
        timestampEnd=4.0,
        text="Test note",
    )


def issue_request() -> CreateIssueRequest:
    return CreateIssueRequest(
        frameStart=15,
        frameEnd=30,
        timestampStart=3.0,
        timestampEnd=6.0,
        bucket="tracking_failure",
        note="Ball jumps across frame.",
    )


def test_write_json_closes_temporary_fd_when_fdopen_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "records.json"
    temporary_fd = -1

    def fail_fdopen(fd: int, *args: object, **kwargs: object) -> None:
        nonlocal temporary_fd
        temporary_fd = fd
        raise OSError("injected fdopen failure")

    monkeypatch.setattr(os, "fdopen", fail_fdopen)

    with pytest.raises(OSError, match="injected fdopen failure"):
        Storage._write_json(path, [])

    with pytest.raises(OSError) as closed:
        os.fstat(temporary_fd)
    assert closed.value.errno == errno.EBADF
    assert list(tmp_path.iterdir()) == []


def test_write_json_rolls_back_and_closes_directory_fd_when_fsync_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "records.json"
    directory_fd = -1
    fsync_calls = 0
    fsync = os.fsync

    def fail_directory_fsync(fd: int) -> None:
        nonlocal directory_fd, fsync_calls
        fsync_calls += 1
        if fsync_calls == 2:
            directory_fd = fd
            raise OSError("injected directory fsync failure")
        fsync(fd)

    monkeypatch.setattr(os, "fsync", fail_directory_fsync)

    with pytest.raises(OSError, match="injected directory fsync failure"):
        Storage._write_json(path, {"new": True})

    assert not path.exists()
    with pytest.raises(OSError) as closed:
        os.fstat(directory_fd)
    assert closed.value.errno == errno.EBADF
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("kind", ["annotation", "issue"])
@pytest.mark.parametrize(
    ("content", "expected_error"),
    [
        (b'{"broken":', json.JSONDecodeError),
        (b"{}", TypeError),
        (b'[{"id":"incomplete"}]', ValidationError),
    ],
)
@pytest.mark.parametrize("operation", ["list", "create", "delete"])
def test_invalid_existing_records_raise_without_changing_file(
    storage: Storage,
    match_id: str,
    kind: str,
    content: bytes,
    expected_error: type[Exception],
    operation: str,
) -> None:
    path = storage.storage_root / "matches" / match_id / f"{kind}s.json"
    path.parent.mkdir(parents=True, exist_ok=True)  # C01 controls are initialised on admission.
    path.write_bytes(content)

    with pytest.raises(expected_error):
        if operation == "list":
            getattr(storage, f"list_{kind}s")(match_id)
        elif operation == "create":
            getattr(storage, f"create_{kind}")(
                match_id, annotation_request() if kind == "annotation" else issue_request()
            )
        else:
            getattr(storage, f"delete_{kind}")(match_id, "missing-id")

    assert path.read_bytes() == content


@pytest.mark.parametrize("kind", ["annotation", "issue"])
def test_replace_failure_preserves_existing_records_and_removes_temporary_file(
    storage: Storage,
    match_id: str,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    create = getattr(storage, f"create_{kind}")
    path = storage.storage_root / "matches" / match_id / f"{kind}s.json"
    request = annotation_request() if kind == "annotation" else issue_request()
    create(match_id, request)
    original = path.read_bytes()

    def fail_replace(source: str | os.PathLike[str], destination: str | os.PathLike[str]) -> None:
        raise OSError("injected replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(OSError, match="injected replace failure"):
        create(match_id, request)

    assert path.read_bytes() == original
    assert {entry.name for entry in path.parent.iterdir()} == {
        path.name, ".review.lock", ".generation.lock", ".generation.lifetime.lock"
    }


@pytest.mark.parametrize("kind", ["annotation", "issue"])
def test_concurrent_creates_do_not_lose_records(
    storage: Storage,
    match_id: str,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    path = storage.storage_root / "matches" / match_id / f"{kind}s.json"
    path.parent.mkdir(parents=True, exist_ok=True)  # C01 controls are initialised on admission.
    path.write_text("[]", encoding="utf-8")
    read_json = storage._read_json

    def slow_read(path: Path) -> object:
        data = read_json(path)
        time.sleep(0.01)
        return data

    monkeypatch.setattr(storage, "_read_json", slow_read)
    create = getattr(storage, f"create_{kind}")
    request = annotation_request() if kind == "annotation" else issue_request()

    with ThreadPoolExecutor(max_workers=8) as executor:
        records = list(executor.map(lambda _: create(match_id, request), range(16)))

    persisted = getattr(storage, f"list_{kind}s")(match_id)
    assert {record.id for record in persisted} == {record.id for record in records}


class TestAnnotationCrud:
    def test_list_empty(self, storage: Storage, match_id: str) -> None:
        assert storage.list_annotations(match_id) == []

    def test_create_annotation(self, storage: Storage, match_id: str) -> None:
        record = storage.create_annotation(match_id, CreateAnnotationRequest(
            type="note",
            frameStart=10,
            frameEnd=20,
            timestampStart=2.0,
            timestampEnd=4.0,
            text="Test note",
        ))

        assert record.id
        assert record.matchId == match_id
        assert record.type == "note"
        assert record.text == "Test note"
        assert record.frameStart == 10
        assert record.createdAt

    def test_list_after_create_annotation(self, storage: Storage, match_id: str) -> None:
        storage.create_annotation(match_id, CreateAnnotationRequest(
            type="arrow", frameStart=0, frameEnd=0, timestampStart=0.0, timestampEnd=0.0))
        storage.create_annotation(match_id, CreateAnnotationRequest(
            type="circle", frameStart=5, frameEnd=5, timestampStart=1.0, timestampEnd=1.0))

        annotations = storage.list_annotations(match_id)
        assert len(annotations) == 2

    def test_delete_annotation(self, storage: Storage, match_id: str) -> None:
        record = storage.create_annotation(match_id, CreateAnnotationRequest(
            type="moment", frameStart=0, frameEnd=0, timestampStart=0.0, timestampEnd=0.0, label="Goal!"))
        storage.delete_annotation(match_id, record.id)

        assert storage.list_annotations(match_id) == []

    def test_delete_nonexistent_record_noop(self, storage: Storage, match_id: str) -> None:
        storage.delete_annotation(match_id, "fake-id")
        # Missing records remain a no-op on an existing match.


class TestIssueCrud:
    def test_list_empty(self, storage: Storage, match_id: str) -> None:
        assert storage.list_issues(match_id) == []

    def test_create_issue(self, storage: Storage, match_id: str) -> None:
        record = storage.create_issue(match_id, CreateIssueRequest(
            frameStart=15,
            frameEnd=30,
            timestampStart=3.0,
            timestampEnd=6.0,
            bucket="tracking_failure",
            note="Ball jumps across frame.",
        ))

        assert record.id
        assert record.matchId == match_id
        assert record.bucket == "tracking_failure"
        assert record.note == "Ball jumps across frame."
        assert record.evidenceTarget == "both"

    def test_list_after_create_issue(self, storage: Storage, match_id: str) -> None:
        storage.create_issue(match_id, CreateIssueRequest(
            frameStart=0, frameEnd=0, timestampStart=0.0, timestampEnd=0.0,
            bucket="team_classification_issue", note="Player assigned to wrong team."))
        storage.create_issue(match_id, CreateIssueRequest(
            frameStart=5, frameEnd=5, timestampStart=1.0, timestampEnd=1.0,
            bucket="ocr_issue", note="Jersey number misread."))

        issues = storage.list_issues(match_id)
        assert len(issues) == 2

    def test_delete_issue(self, storage: Storage, match_id: str) -> None:
        record = storage.create_issue(match_id, CreateIssueRequest(
            frameStart=0, frameEnd=0, timestampStart=0.0, timestampEnd=0.0,
            bucket="event_layer_issue", note="Pass counted as shot."))
        storage.delete_issue(match_id, record.id)

        assert storage.list_issues(match_id) == []

    def test_delete_nonexistent_record_noop(self, storage: Storage, match_id: str) -> None:
        storage.delete_issue(match_id, "fake-id")
        # Missing records remain a no-op on an existing match.


@pytest.mark.parametrize("kind", ["annotation", "issue"])
@pytest.mark.parametrize("operation", ["list", "create", "delete"])
def test_missing_match_rejected_without_creating_artifacts(storage: Storage, kind: str, operation: str) -> None:
    with pytest.raises(KeyError):
        if operation == "list":
            getattr(storage, f"list_{kind}s")("missing-match")
        elif operation == "create":
            getattr(storage, f"create_{kind}")(
                "missing-match", annotation_request() if kind == "annotation" else issue_request()
            )
        else:
            getattr(storage, f"delete_{kind}")("missing-match", "missing-id")
    assert not (storage.storage_root / "matches" / "missing-match").exists()
