import logging

from backend.app import processor
from backend.app.schemas import MatchConfig
from backend.app.storage import Storage


def test_ownership_publication_failure_warns_without_failing_primary_result(
    tmp_path, monkeypatch, caplog
) -> None:
    storage = Storage(tmp_path)
    input_path = storage.save_upload("clip.mp4", b"video")
    match = storage.create_match(
        name="auxiliary warning",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=input_path,
        config=MatchConfig(),
    )
    job = storage.create_job(match.id)

    def fail_ownership(_match_id: str) -> None:
        raise OSError("sentinel-secret-ownership")

    monkeypatch.setattr(storage, "publish_ownership_events", fail_ownership)
    caplog.set_level(logging.WARNING, logger="backend.app.processor")
    processor.persist_remote_video_result(
        storage,
        job.id,
        {
            "rows": [
                {
                    "Frame_ID": 0,
                    "Timestamp": 0.0,
                    "Entity_Type": "ball",
                    "Track_ID": -1,
                    "X": 50.0,
                    "Y": 34.0,
                    "Conf": 0.9,
                }
            ]
        },
    )

    assert storage.get_job(job.id).status == "completed"
    assert storage.get_match(match.id).status == "ready"
    assert "optional_artifact_write_failed" in caplog.text
    assert match.id in caplog.text and job.id in caplog.text
    assert "ownership_publication" in caplog.text and "OSError" in caplog.text
    assert "sentinel-secret-ownership" not in caplog.text
