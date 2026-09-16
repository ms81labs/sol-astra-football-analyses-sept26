"""Production-boundary tests for the sidecar judge wrapper."""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


SIDECAR_PROJECT_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SIDECAR_PROJECT_DIR.parent


def _successful_output(**updates: object) -> dict[str, object]:
    output: dict[str, object] = {
        "acceptedBallFrames": 1,
        "supportedAcceptedBallRatio": 1.0,
        "controlledPossessionFrames": 1,
        "eventFamilyCount": 1,
        "truthGateReasons": [],
    }
    output.update(updates)
    return output


def _write_manifest(
    root: Path,
    *,
    video_path: str | None = "video.mp4",
    entries: list[object] | None = None,
) -> Path:
    manifest_path = root / "manifest.json"
    if entries is None:
        entries = [
            {
                "video_id": "test",
                "video_path": video_path,
                "ground_truth_path": None,
                "tags": ["test"],
            }
        ]
    manifest_path.write_text(json.dumps({"entries": entries}), encoding="utf-8")
    return manifest_path


def _write_repository(root: Path, body: str | None = None) -> Path:
    repository = root / "fixture-repository"
    script = repository / "backend" / "scripts" / "run_local_app_path_proof.py"
    script.parent.mkdir(parents=True)
    (repository / "video.mp4").write_bytes(b"fixture-video")
    script.write_text(
        textwrap.dedent(body)
        if body is not None
        else "import json\nprint(json.dumps(" + repr(_successful_output()) + "))\n",
        encoding="utf-8",
    )
    return repository


def _make_symlink_loop(root: Path, name: str) -> Path:
    first = root / f"{name}-a"
    second = root / f"{name}-b"
    first.symlink_to(second)
    second.symlink_to(first)
    return first


def _run_judge(
    manifest: Path,
    storage_root: Path,
    repository: Path,
    **kwargs: object,
) -> dict[str, object]:
    from research_addon.judge import run_judge

    return run_judge(
        manifest,
        storage_root,
        repo_root=repository,
        python=sys.executable,
        **kwargs,
    )


def test_contract_declares_relative_delegate_and_exact_required_fields():
    from research_addon.judge import JudgeContract

    assert JudgeContract.delegated_target() == Path(
        "backend/scripts/run_local_app_path_proof.py"
    )
    assert JudgeContract.required_summary_fields() == [
        "acceptedBallFrames",
        "supportedAcceptedBallRatio",
        "controlledPossessionFrames",
        "eventFamilyCount",
        "truthGateReasons",
    ]


def test_direct_run_judge_uses_manifest_repository_interpreter_cwd_and_storage(tmp_path):
    storage = tmp_path / "storage"
    storage.mkdir()
    expected_python = Path(sys.executable).resolve()
    expected_storage = storage.resolve()
    repository = _write_repository(
        tmp_path,
        f"""
        import argparse
        import json
        import sys
        from pathlib import Path

        parser = argparse.ArgumentParser()
        parser.add_argument('--storage-root')
        parser.add_argument('--video-path')
        parser.add_argument('--poll-interval-seconds')
        parser.add_argument('--timeout-seconds')
        args = parser.parse_args()
        assert Path(sys.executable).resolve() == Path({str(expected_python)!r})
        assert Path.cwd() == Path({str((tmp_path / 'fixture-repository').resolve())!r})
        assert Path(args.storage_root) == Path({str(expected_storage)!r})
        assert Path(args.video_path) == Path({str((tmp_path / 'fixture-repository' / 'video.mp4').resolve())!r})
        print(json.dumps({_successful_output()!r}))
        """,
    )
    manifest = _write_manifest(tmp_path)

    assert _run_judge(manifest, storage, repository) == _successful_output()


def test_relative_manifest_video_resolves_against_repository_only(tmp_path, monkeypatch):
    import research_addon.judge as judge

    repository = _write_repository(tmp_path)
    storage = tmp_path / "storage"
    storage.mkdir()
    manifest = _write_manifest(tmp_path)
    wrong_cwd = tmp_path / "wrong-cwd"
    wrong_cwd.mkdir()
    (wrong_cwd / "video.mp4").write_bytes(b"wrong")
    observed: dict[str, Path] = {}

    def delegate(video_path, storage_root, **kwargs):
        observed["video"] = video_path
        observed["storage"] = storage_root
        observed["repository"] = kwargs["repo_root"]
        observed["python"] = kwargs["python"]
        return _successful_output()

    monkeypatch.setattr(judge, "_run_proof_via_script", delegate)
    monkeypatch.chdir(wrong_cwd)

    assert _run_judge(manifest, storage, repository) == _successful_output()
    assert observed == {
        "video": (repository / "video.mp4").resolve(),
        "storage": storage.resolve(),
        "repository": repository.resolve(),
        "python": Path(sys.executable).resolve(),
    }


def test_absolute_manifest_video_remains_explicit(tmp_path, monkeypatch):
    import research_addon.judge as judge

    repository = _write_repository(tmp_path)
    explicit_video = tmp_path / "explicit.mp4"
    explicit_video.write_bytes(b"video")
    manifest = _write_manifest(tmp_path, video_path=str(explicit_video))
    storage = tmp_path / "storage"
    storage.mkdir()
    observed: dict[str, Path] = {}

    def delegate(video_path, *_args, **_kwargs):
        observed["video"] = video_path
        return _successful_output()

    monkeypatch.setattr(judge, "_run_proof_via_script", delegate)
    _run_judge(manifest, storage, repository)

    assert observed["video"] == explicit_video.resolve()


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("missing-repository", "Repository root"),
        ("repository-file", "Repository root"),
        ("missing-script", "Delegated script"),
        ("missing-interpreter", "Python interpreter"),
        ("non-executable-interpreter", "Python interpreter"),
        ("missing-manifest", "Corpus manifest"),
        ("malformed-manifest", "Corpus manifest"),
        ("empty-manifest", "entry 0"),
        ("out-of-range-entry", "entry 1"),
        ("malformed-entry", "entry 'invalid'"),
        ("missing-video", "Video file"),
        ("symlink-video", "Video file"),
        ("relative-video-escape", "Video file"),
    ],
)
def test_invalid_execution_configuration_fails_before_subprocess(
    tmp_path, monkeypatch, case, expected
):
    import research_addon.judge as judge

    repository = _write_repository(tmp_path)
    manifest = _write_manifest(tmp_path)
    storage = tmp_path / "storage"
    storage.mkdir()
    interpreter = Path(sys.executable)
    entry_index = 0

    if case == "missing-repository":
        repository = tmp_path / "missing-repository"
    elif case == "repository-file":
        repository = tmp_path / "repository-file"
        repository.write_text("not a directory", encoding="utf-8")
    elif case == "missing-script":
        (repository / "backend/scripts/run_local_app_path_proof.py").unlink()
    elif case == "missing-interpreter":
        interpreter = tmp_path / "missing-python"
    elif case == "non-executable-interpreter":
        interpreter = tmp_path / "python"
        interpreter.write_text("#!/bin/sh\n", encoding="utf-8")
        interpreter.chmod(0o644)
    elif case == "missing-manifest":
        manifest.unlink()
    elif case == "malformed-manifest":
        manifest.write_text("{broken", encoding="utf-8")
    elif case == "empty-manifest":
        manifest = _write_manifest(tmp_path, entries=[])
    elif case == "out-of-range-entry":
        entry_index = 1
    elif case == "malformed-entry":
        entry_index = "invalid"
    elif case == "missing-video":
        (repository / "video.mp4").unlink()
    elif case == "symlink-video":
        (repository / "video.mp4").unlink()
        (repository / "target.mp4").write_bytes(b"target")
        (repository / "video.mp4").symlink_to(repository / "target.mp4")
    elif case == "relative-video-escape":
        outside_video = tmp_path / "outside.mp4"
        outside_video.write_bytes(b"outside")
        manifest = _write_manifest(tmp_path, video_path="../outside.mp4")

    monkeypatch.setattr(
        judge.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("subprocess must not run")
        ),
    )

    with pytest.raises(judge.JudgeExecutionError, match=expected):
        judge.run_judge(
            manifest,
            storage,
            repo_root=repository,
            python=interpreter,
            entry_index=entry_index,
        )


def test_installed_layout_requires_explicit_repository_and_interpreter(
    tmp_path, monkeypatch
):
    import research_addon.judge as judge

    package = tmp_path / "site-packages" / "research_addon"
    package.mkdir(parents=True)
    monkeypatch.setattr(judge, "__file__", str(package / "judge.py"))
    manifest = _write_manifest(tmp_path)
    storage = tmp_path / "storage"
    storage.mkdir()

    with pytest.raises(judge.JudgeExecutionError, match="Repository root"):
        judge.run_judge(manifest, storage, python=sys.executable)
    with pytest.raises(judge.JudgeExecutionError, match="Python interpreter"):
        judge.run_judge(manifest, storage, repo_root=_write_repository(tmp_path))


def test_source_checkout_defaults_are_ready_only_with_explicit_manifest(tmp_path):
    from research_addon.judge import judge_is_ready

    manifest = _write_manifest(tmp_path, video_path="README.md")

    assert judge_is_ready(manifest)
    assert not judge_is_ready(None)


@pytest.mark.parametrize("field", ["repo_root", "python", "manifest_path"])
def test_supplied_looping_paths_are_controlled_before_execution(tmp_path, field):
    import research_addon.judge as judge

    repository = _write_repository(tmp_path)
    manifest = _write_manifest(tmp_path)
    storage = tmp_path / "storage"
    storage.mkdir()
    values = {
        "manifest_path": manifest,
        "repo_root": repository,
        "python": sys.executable,
    }
    values[field] = _make_symlink_loop(tmp_path, field)

    with pytest.raises(judge.JudgeExecutionError, match="could not be resolved"):
        judge.run_judge(
            values["manifest_path"],
            storage,
            repo_root=values["repo_root"],
            python=values["python"],
        )


def test_readiness_is_false_for_looping_repository_path(tmp_path):
    from research_addon.judge import judge_is_ready

    manifest = _write_manifest(tmp_path, video_path="README.md")
    loop = _make_symlink_loop(tmp_path, "repository")

    assert not judge_is_ready(manifest, repo_root=loop, python=sys.executable)


@pytest.mark.parametrize("bad_name", ["x" * 4096, "invalid\0path"])
def test_supplied_path_os_error_is_controlled(tmp_path, bad_name):
    import research_addon.judge as judge

    manifest = _write_manifest(tmp_path)
    storage = tmp_path / "storage"
    storage.mkdir()
    invalid_repository = tmp_path / bad_name

    with pytest.raises(judge.JudgeExecutionError, match="could not be resolved"):
        judge.run_judge(
            manifest,
            storage,
            repo_root=invalid_repository,
            python=sys.executable,
        )


@pytest.mark.parametrize("entrypoint", ["cli", "module"])
def test_judge_clis_control_looping_repository_path(tmp_path, entrypoint):
    manifest = _write_manifest(tmp_path)
    storage = tmp_path / "storage"
    storage.mkdir()
    loop = _make_symlink_loop(tmp_path, "repository")
    common = [
        "--manifest",
        str(manifest),
        "--repo-root",
        str(loop),
        "--python",
        sys.executable,
        "--storage-root",
        str(storage),
    ]
    command = (
        [sys.executable, "-m", "research_addon.cli", "judge", "supported-coverage", *common]
        if entrypoint == "cli"
        else [sys.executable, "-m", "research_addon.judge", *common]
    )

    result = subprocess.run(
        command,
        cwd=SIDECAR_PROJECT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stderr.startswith("ERROR:")
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("entry_index", ["invalid", "-1", "2"])
def test_tracks_list_treats_invalid_entry_index_as_unavailable(tmp_path, entry_index):
    repository = _write_repository(tmp_path)
    manifest = _write_manifest(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "research_addon.cli",
            "tracks",
            "list",
            "--manifest",
            str(manifest),
            "--repo-root",
            str(repository),
            "--python",
            sys.executable,
            "--entry-index",
            entry_index,
        ],
        cwd=SIDECAR_PROJECT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "supported-coverage  [available-with-config]" in result.stdout
    assert result.stderr == ""


@pytest.mark.parametrize("entrypoint", ["cli", "module"])
@pytest.mark.parametrize("entry_index", ["invalid", "-1", "2"])
def test_judge_clis_control_invalid_entry_index(tmp_path, entrypoint, entry_index):
    repository = _write_repository(tmp_path)
    manifest = _write_manifest(tmp_path)
    storage = tmp_path / "storage"
    storage.mkdir()
    common = [
        "--manifest",
        str(manifest),
        "--repo-root",
        str(repository),
        "--python",
        sys.executable,
        "--entry-index",
        entry_index,
        "--storage-root",
        str(storage),
    ]
    command = (
        [sys.executable, "-m", "research_addon.cli", "judge", "supported-coverage", *common]
        if entrypoint == "cli"
        else [sys.executable, "-m", "research_addon.judge", *common]
    )

    result = subprocess.run(
        command,
        cwd=SIDECAR_PROJECT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stderr.startswith("ERROR:")
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ([], "JSON object"),
        ({}, "missing required fields"),
        (_successful_output(acceptedBallFrames=True), "acceptedBallFrames"),
        (_successful_output(acceptedBallFrames=-1), "acceptedBallFrames"),
        (_successful_output(controlledPossessionFrames=1.5), "controlledPossessionFrames"),
        (_successful_output(eventFamilyCount=False), "eventFamilyCount"),
        (_successful_output(supportedAcceptedBallRatio=True), "supportedAcceptedBallRatio"),
        (_successful_output(supportedAcceptedBallRatio=float("nan")), "supportedAcceptedBallRatio"),
        (_successful_output(supportedAcceptedBallRatio=float("inf")), "supportedAcceptedBallRatio"),
        (_successful_output(supportedAcceptedBallRatio=-0.1), "supportedAcceptedBallRatio"),
        (_successful_output(supportedAcceptedBallRatio=1.1), "supportedAcceptedBallRatio"),
        (_successful_output(truthGateReasons="none"), "truthGateReasons"),
        (_successful_output(truthGateReasons=["ok", 1]), "truthGateReasons"),
    ],
)
def test_run_judge_rejects_malformed_result_values(
    tmp_path, monkeypatch, output, expected
):
    import research_addon.judge as judge

    repository = _write_repository(tmp_path)
    manifest = _write_manifest(tmp_path)
    storage = tmp_path / "storage"
    storage.mkdir()
    monkeypatch.setattr(judge, "_run_proof_via_script", lambda *_args, **_kwargs: output)

    with pytest.raises(judge.JudgeExecutionError, match=expected):
        _run_judge(manifest, storage, repository)


def test_valid_result_returns_only_the_five_contract_fields(tmp_path, monkeypatch):
    import research_addon.judge as judge

    repository = _write_repository(tmp_path)
    manifest = _write_manifest(tmp_path)
    storage = tmp_path / "storage"
    storage.mkdir()
    output = _successful_output(extra="not part of the judge contract")
    monkeypatch.setattr(judge, "_run_proof_via_script", lambda *_args, **_kwargs: output)

    assert _run_judge(manifest, storage, repository) == _successful_output()


def test_controlled_delegate_nonzero_is_exposed_by_direct_api(tmp_path):
    import research_addon.judge as judge

    repository = _write_repository(tmp_path, "import sys\nsys.exit(7)\n")
    manifest = _write_manifest(tmp_path)
    storage = tmp_path / "storage"
    storage.mkdir()

    with pytest.raises(judge.JudgeExecutionError, match="exited with 7") as raised:
        _run_judge(manifest, storage, repository)

    assert raised.value.exit_code == 7


@pytest.mark.parametrize("entrypoint", ["cli", "module"])
def test_controlled_delegate_nonzero_is_preserved_by_both_clis(tmp_path, entrypoint):
    repository = _write_repository(tmp_path, "import sys\nsys.exit(7)\n")
    manifest = _write_manifest(tmp_path)
    storage = tmp_path / "storage"
    storage.mkdir()
    common = [
        "--manifest",
        str(manifest),
        "--repo-root",
        str(repository),
        "--python",
        sys.executable,
        "--storage-root",
        str(storage),
    ]
    command = (
        [sys.executable, "-m", "research_addon.cli", "judge", "supported-coverage", *common]
        if entrypoint == "cli"
        else [sys.executable, "-m", "research_addon.judge", *common]
    )

    result = subprocess.run(
        command,
        cwd=SIDECAR_PROJECT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 7
    assert "exited with 7" in result.stderr


def test_dry_run_without_configuration_reads_nothing_runs_nothing_and_writes_nothing(
    tmp_path, monkeypatch
):
    import research_addon.judge as judge
    from research_addon.path_guards import get_addon_root

    before = {
        str(path.relative_to(get_addon_root())): path.read_bytes()
        for path in get_addon_root().rglob("*")
        if path.is_file()
    }
    monkeypatch.setattr(
        judge.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("subprocess must not run")
        ),
    )

    before_temp = sorted(path.name for path in tmp_path.iterdir())
    result = judge.run_judge(None, tmp_path, dry_run=True)

    after = {
        str(path.relative_to(get_addon_root())): path.read_bytes()
        for path in get_addon_root().rglob("*")
        if path.is_file()
    }
    assert result["_dry_run"] is True
    assert result["required_configuration"] == ["manifest", "repo_root", "python"]
    assert sorted(path.name for path in tmp_path.iterdir()) == before_temp
    assert after == before


def test_judge_module_rejects_protected_storage_root_before_dry_run():
    protected = REPOSITORY_ROOT / "backend"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "research_addon.judge",
            "--dry-run",
            "--storage-root",
            str(protected),
        ],
        capture_output=True,
        text=True,
        cwd=SIDECAR_PROJECT_DIR,
        check=False,
    )
    assert result.returncode == 1
    assert "Rejected" in result.stderr


def test_judge_subcommand_help_exposes_execution_context():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "research_addon.cli",
            "judge",
            "supported-coverage",
            "--help",
        ],
        capture_output=True,
        text=True,
        cwd=SIDECAR_PROJECT_DIR,
        check=False,
    )
    assert result.returncode == 0
    assert "--manifest" in result.stdout
    assert "--repo-root" in result.stdout
    assert "--python" in result.stdout
    assert "--entry-index" in result.stdout
