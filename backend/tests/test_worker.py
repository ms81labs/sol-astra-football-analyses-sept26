from unittest.mock import MagicMock, patch

from backend.app.worker import run_job


def test_run_job_happy_path_updates_job_completed(tmp_path):
    """run_job on success calls process_match and leaves the job as-is (completed by process_match)."""
    mock_job = MagicMock()
    mock_job.status = "running"
    mock_job.matchId = "match-xyz"

    with patch("backend.app.worker.Storage") as mock_storage_cls, \
         patch("backend.app.worker.process_match") as mock_process:

        mock_storage = MagicMock()
        mock_storage_cls.return_value = mock_storage
        mock_storage.get_job.return_value = mock_job

        run_job(tmp_path, "job-ok-001")

        mock_process.assert_called_once_with(mock_storage, "job-ok-001")


def test_run_job_failure_updates_job_and_match_failed(tmp_path):
    """run_job on exception marks job and match as failed with error message."""
    mock_job = MagicMock()
    mock_job.status = "running"
    mock_job.matchId = "match-err"

    with patch("backend.app.worker.Storage") as mock_storage_cls, \
         patch("backend.app.worker.process_match") as mock_process:

        mock_storage = MagicMock()
        mock_storage_cls.return_value = mock_storage
        mock_storage.get_job.return_value = mock_job
        mock_process.side_effect = ValueError("detector unavailable")

        run_job(tmp_path, "job-fail-002")

        mock_storage.update_job.assert_called_once_with(
            "job-fail-002",
            status="failed",
            progress=1.0,
            message="detector unavailable",
            error="detector unavailable",
        )
        mock_storage.update_match_status.assert_called_once_with("match-err", status="failed")


def test_run_job_failure_preserves_homography_message(tmp_path):
    """run_job should surface the auto-homography failure message verbatim."""
    mock_job = MagicMock()
    mock_job.status = "running"
    mock_job.matchId = "match-homography"

    message = (
        "Homography could not be detected automatically. "
        "Please provide manualHomographyPoints (4 corner coordinates) when uploading."
    )

    with patch("backend.app.worker.Storage") as mock_storage_cls, \
         patch("backend.app.worker.process_match") as mock_process:

        mock_storage = MagicMock()
        mock_storage_cls.return_value = mock_storage
        mock_storage.get_job.return_value = mock_job
        mock_process.side_effect = RuntimeError(message)

        run_job(tmp_path, "job-homography-001")

        mock_storage.update_job.assert_called_once_with(
            "job-homography-001",
            status="failed",
            progress=1.0,
            message=message,
            error=message,
        )
