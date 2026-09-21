import logging

from backend.app.storage import Storage


def test_durable_job_hash_fallback_is_observable(tmp_path, caplog, monkeypatch) -> None:
    storage = Storage(tmp_path)
    admitted = []

    monkeypatch.setattr(storage.job_ledger, "has_request", lambda _request_id: False)
    monkeypatch.setattr(
        storage.job_ledger,
        "admit",
        lambda request, **_kwargs: admitted.append(request),
    )

    def fail_hash(_match_id: str) -> str:
        raise OSError("synthetic hash failure")

    monkeypatch.setattr(storage, "source_sha256", fail_hash)
    caplog.set_level(logging.WARNING, logger="backend.app.storage")

    storage._admit_durable_job("match-observe", "job-observe")

    assert admitted[0].sourceSha256 == "0" * 64
    assert "source hash unavailable; admitting fallback identity" in caplog.text
    assert "match-observe" in caplog.text
    assert "job-observe" in caplog.text
    assert "OSError" in caplog.text
