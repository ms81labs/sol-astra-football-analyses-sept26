import ast
from pathlib import Path
from unittest.mock import patch

import pytest

import backend.app.jobs as jobs_module
from backend.app.jobs import JobRunner
from backend.app.schemas import MatchConfig
from backend.app.settings import ProcessingSettings
from backend.app.storage import Storage
from backend.release.daytona_policy import load_daytona_policy


def test_job_runner_start_inline_uses_worker_run_job(tmp_path):
    """Inline execution should use the same worker failure/reporting path as spawned jobs."""
    with patch("backend.app.jobs.run_job") as mock_run_job:
        runner = JobRunner(tmp_path, run_jobs_inline=True)
        runner.start("job-abc-123")

        mock_run_job.assert_called_once_with(tmp_path, "job-abc-123")


def test_job_runner_start_inline_does_not_propagate_worker_failure(tmp_path):
    """Inline execution should leave failure handling to run_job rather than re-raising here."""
    with patch("backend.app.jobs.run_job") as mock_run_job:
        mock_run_job.side_effect = None

        runner = JobRunner(tmp_path, run_jobs_inline=True)
        runner.start("job-err-001")

        mock_run_job.assert_called_once_with(tmp_path, "job-err-001")


def test_job_runner_start_local_spawns_provider_clean_worker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("PYTHONPATH", "/parent/pythonpath")
    monkeypatch.setenv("RUNPOD_API_KEY", "legacy-parent-secret")
    monkeypatch.setenv("RUNPOD_CUSTOM", "legacy-parent-setting")
    monkeypatch.setenv("DAYTONA_API_KEY", "daytona-parent-secret")
    monkeypatch.setenv("DAYTONA_CUSTOM", "daytona-parent-setting")
    monkeypatch.setenv("UNRELATED_PARENT_SETTING", "preserved")

    with patch("backend.app.jobs.subprocess.Popen") as mock_popen:
        runner = JobRunner(
            tmp_path,
            settings=ProcessingSettings(),
        )
        runner.start("job-local-001")

    mock_popen.assert_called_once()
    command = mock_popen.call_args.args[0]
    assert command[0:3] == [jobs_module.sys.executable, "-m", "backend.app.worker"]
    assert command[3:] == [
        "--storage-root",
        str(tmp_path),
        "--job-id",
        "job-local-001",
    ]
    env = mock_popen.call_args.kwargs["env"]
    repo_root = str(Path(jobs_module.__file__).resolve().parents[2])
    assert env["PYTHONPATH"] == f"{repo_root}:/parent/pythonpath"
    assert env["QT_QPA_PLATFORM"] == "offscreen"
    assert env["PROCESSING_BACKEND"] == "local"
    assert env["UNRELATED_PARENT_SETTING"] == "preserved"
    assert not any(key.startswith(("RUNPOD_", "DAYTONA_")) for key in env)
    assert mock_popen.call_args.kwargs["cwd"] == repo_root
    assert mock_popen.call_args.kwargs["stderr"] is jobs_module.subprocess.STDOUT
    log_stream = mock_popen.call_args.kwargs["stdout"]
    assert Path(log_stream.name) == tmp_path / "logs" / "job_job-local-001.log"
    assert log_stream.closed


def test_job_runner_selected_daytona_runs_remote_worker_inline(tmp_path: Path) -> None:
    secret = "host-daytona-key-must-not-leak-7219"
    settings = ProcessingSettings(
        processing_backend="daytona",
        daytona_api_key=secret,
        daytona_policy=load_daytona_policy(),
    )
    runner = JobRunner(tmp_path, run_jobs_inline=True, settings=settings)
    runner.admit(
        "job-daytona-inline",
        match_id="match",
        source_sha256="a" * 64,
        budget=1.0,
    )
    with patch("backend.app.remote_worker.run_remote_job") as mock_remote:
        runner.start("job-daytona-inline")

    mock_remote.assert_called_once_with(tmp_path, "job-daytona-inline", settings=settings)


def test_job_runner_selected_daytona_spawns_clean_remote_worker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "host-daytona-key-must-not-leak-7219"
    monkeypatch.setenv("RUNPOD_API_KEY", "legacy-secret")
    monkeypatch.setenv("RUNPOD_CUSTOM", "legacy-setting")
    monkeypatch.setenv("DAYTONA_API_KEY", "inherited-wrong-secret")
    monkeypatch.setenv("DAYTONA_CUSTOM", "inherited-setting")
    monkeypatch.setenv("UNRELATED_PARENT_SETTING", "preserved")
    settings = ProcessingSettings(
        processing_backend="daytona",
        daytona_api_key=secret,
        daytona_policy=load_daytona_policy(),
    )
    runner = JobRunner(tmp_path, settings=settings)
    runner.admit(
        "job-daytona-spawned",
        match_id="match",
        source_sha256="a" * 64,
        budget=1.0,
    )
    with patch("backend.app.jobs.subprocess.Popen") as mock_popen:
        runner.start("job-daytona-spawned")

    command = mock_popen.call_args.args[0]
    assert command[0:3] == [jobs_module.sys.executable, "-m", "backend.app.remote_worker"]
    assert secret not in repr(command)
    env = mock_popen.call_args.kwargs["env"]
    assert env["PROCESSING_BACKEND"] == "daytona"
    assert env["DAYTONA_API_KEY"] == secret
    assert env["UNRELATED_PARENT_SETTING"] == "preserved"
    assert not any(key.startswith("RUNPOD_") for key in env)
    assert {key for key in env if key.startswith("DAYTONA_")} == {"DAYTONA_API_KEY"}


def test_job_runner_rejects_unbudgeted_daytona_dispatch(tmp_path: Path) -> None:
    settings = ProcessingSettings(
        processing_backend="daytona",
        daytona_api_key="configured-secret",
        daytona_policy=load_daytona_policy(),
    )
    with pytest.raises(RuntimeError, match="positive authorised budget"):
        JobRunner(tmp_path, settings=settings).start("unbudgeted-daytona")


def test_storage_and_runner_share_daytona_admission_payload(tmp_path: Path) -> None:
    settings = ProcessingSettings(
        processing_backend="daytona",
        daytona_api_key="configured-secret",
        daytona_policy=load_daytona_policy(),
    )
    storage = Storage(tmp_path)
    match = storage.create_match(
        "daytona",
        "tracking_json",
        "tracking.json",
        tmp_path / "tracking.json",
        MatchConfig(),
    )
    storage.ensure_job(
        match.id,
        "daytona-job",
        budget=1.0,
        authorised_location="daytona",
    )
    runner = JobRunner(tmp_path, settings=settings, ledger=storage.job_ledger)

    replay = runner.admit(
        "daytona-job",
        match_id=match.id,
        source_sha256=storage.source_sha256(match.id),
        budget=1.0,
    )

    assert replay.attemptId == storage.job_ledger.latest_attempt("daytona-job").attemptId


def test_job_runner_rejects_bypassed_unknown_backend_without_dispatch(tmp_path: Path) -> None:
    unknown_backend = "hostile-provider-secret-must-not-leak-4812"

    class BypassedSettings:
        processing_backend = unknown_backend

    with (
        patch("backend.app.jobs.run_job") as mock_run_job,
        patch("backend.app.jobs.subprocess.Popen") as mock_popen,
        pytest.raises(jobs_module.JobDispatchError) as caught,
    ):
        JobRunner(
            tmp_path,
            settings=BypassedSettings(),  # type: ignore[arg-type]
        ).start("job-hostile-provider")

    rendered = f"{caught.value!s} {caught.value!r}"
    assert len(rendered) < 256
    assert unknown_backend not in rendered
    mock_run_job.assert_not_called()
    mock_popen.assert_not_called()
    assert not (tmp_path / "logs").exists()


def test_job_runner_classifies_popen_failure_as_known_no_child(tmp_path: Path) -> None:
    with (
        patch("backend.app.jobs.subprocess.Popen", side_effect=OSError("sensitive detail")),
        pytest.raises(jobs_module.JobDispatchError) as caught,
    ):
        JobRunner(tmp_path).start("job-popen-failure")

    assert caught.value.child_may_have_started is False
    assert "sensitive detail" not in str(caught.value)


def test_job_runner_classifies_inline_failure_after_start_as_uncertain(tmp_path: Path) -> None:
    with (
        patch("backend.app.jobs.run_job", side_effect=RuntimeError("sensitive detail")),
        pytest.raises(jobs_module.JobDispatchError) as caught,
    ):
        JobRunner(tmp_path, run_jobs_inline=True).start("job-inline-failure")

    assert caught.value.child_may_have_started is True
    assert "sensitive detail" not in str(caught.value)


def test_job_runner_uncertain_dispatch_records_outcome_unknown_and_blocks_retry(tmp_path: Path) -> None:
    runner = JobRunner(tmp_path, run_jobs_inline=True)
    runner.admit("job-inline-failure", match_id="m1", source_sha256="c" * 64, budget=1.0)
    with (
        patch("backend.app.jobs.run_job", side_effect=RuntimeError("sensitive detail")),
        pytest.raises(jobs_module.JobDispatchError),
    ):
        runner.start("job-inline-failure")

    receipt = runner.receipt("job-inline-failure")
    assert receipt.status == "outcome_unknown"
    assert receipt.cleanupResult == "unknown"
    with pytest.raises(RuntimeError, match="reconcile"):
        runner.retry("job-inline-failure")


def test_local_worker_confirms_requested_cancellation(tmp_path: Path) -> None:
    storage = Storage(tmp_path)
    match = storage.create_match(
        "cancel",
        "tracking_json",
        "tracking.json",
        tmp_path / "tracking.json",
        MatchConfig(),
    )
    job, _ = storage.ensure_job(match.id, "cancel-job")
    storage.job_ledger.request_cancel(job.id)
    storage.close()

    with patch("backend.app.worker.process_match") as process_match:
        from backend.app.worker import run_job as run_worker_job

        run_worker_job(tmp_path, job.id)

    process_match.assert_not_called()
    restarted = Storage(tmp_path)
    receipt = restarted.job_ledger.receipt(job.id)
    assert restarted.get_job(job.id).status == "cancelled"
    assert receipt.status == "cancelled"
    assert receipt.cleanupResult == "confirmed"


def test_jobs_module_has_no_runpod_dispatch_surface() -> None:
    source = Path(jobs_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(jobs_module.__file__))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert all("runpod_worker" not in name for name in imported_modules)
    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "run_remote_job"
        for node in ast.walk(tree)
    )
    assert "backend.app.runpod_worker" not in source
