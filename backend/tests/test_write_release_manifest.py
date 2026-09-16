from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import stat
import sys

import pytest

from backend.app.release_manifest import ManifestError, load_release_manifest
from backend.scripts.write_release_manifest import write_release_manifest


SOURCE_COMMIT = "a" * 40
CREATED_AT = "2026-08-22T12:34:56Z"


def _template(content: bytes = b"model") -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "releaseVersion": "v7.3",
        "candidateVersion": "v7.3",
        "runtimeVersion": "v7.3",
        "runtimeOptions": {
            "primary_model": {"artifactId": "primary-model"},
            "auxiliary_ball_model": None,
            "auxiliary_ball_model_profile": None,
            "primary_acquisition_mode": "anchored-player-ranked-context-960",
            "edge_share_repair_profile": None,
            "baseline_guided_rescue_reference": None,
            "proposal_selection_truth_seed": None,
            "reviewed_positive_anchor_seed": None,
        },
        "artifacts": [
            {
                "id": "primary-model",
                "sha256": hashlib.sha256(content).hexdigest(),
                "sizeBytes": len(content),
                "localRelativePath": "artifacts/model.pt",
                "containerPath": "/app/models/model.pt",
                "origin": "external-recovery-archive",
                "retentionClass": "release-essential",
            }
        ],
        "requiredContracts": [
            "video_to_analysis_product_api_v1",
            "video_to_analysis_report_v1",
        ],
    }


def _write_artifact(root: Path, content: bytes = b"model") -> None:
    path = root / "artifacts/model.pt"
    path.parent.mkdir(parents=True)
    path.write_bytes(content)


def test_writer_requires_explicit_source_and_timestamp(tmp_path: Path) -> None:
    _write_artifact(tmp_path)
    output = tmp_path / "release.json"

    with pytest.raises(TypeError):
        write_release_manifest(output, _template(), artifact_root=tmp_path)  # type: ignore[call-arg]


def test_writer_injects_explicit_values_validates_artifacts_and_writes_stable_json(tmp_path: Path) -> None:
    _write_artifact(tmp_path)
    output = tmp_path / "release.json"

    manifest = write_release_manifest(
        output,
        _template(),
        source_commit=SOURCE_COMMIT,
        created_at=CREATED_AT,
        artifact_root=tmp_path,
    )

    assert manifest.source_commit == SOURCE_COMMIT
    assert manifest.created_at == CREATED_AT
    assert output.read_text(encoding="utf-8") == json.dumps(manifest.to_mapping(), indent=2, sort_keys=True) + "\n"
    assert load_release_manifest(output) == manifest


@pytest.mark.parametrize(
    "mutation,error",
    [
        (lambda template: template["runtimeOptions"].update({"arbitrary": True}), "runtimeOptions"),
        (
            lambda template: template["runtimeOptions"].update(
                {"primary_model": {"artifactId": "missing-model"}}
            ),
            "undeclared artifact",
        ),
        (lambda template: template.update({"runtimeVersion": "v7.2"}), "releaseVersion"),
        (
            lambda template: template.update(
                {"requiredContracts": ["video_to_analysis_product_api_v1"]}
            ),
            "requiredContracts.*exactly",
        ),
    ],
)
def test_writer_rejects_semantically_invalid_release_manifest(tmp_path: Path, mutation, error: str) -> None:
    _write_artifact(tmp_path)
    template = _template()
    mutation(template)

    with pytest.raises(ManifestError, match=error):
        write_release_manifest(
            tmp_path / "release.json",
            template,
            source_commit=SOURCE_COMMIT,
            created_at=CREATED_AT,
            artifact_root=tmp_path,
        )


@pytest.mark.parametrize("field,explicit", [("sourceCommit", "b" * 40), ("createdAt", "2026-08-23T00:00:00Z")])
def test_writer_rejects_template_values_that_mismatch_explicit_values(tmp_path: Path, field: str, explicit: str) -> None:
    _write_artifact(tmp_path)
    template = _template()
    template[field] = explicit

    with pytest.raises(ManifestError, match=f"{field} mismatch"):
        write_release_manifest(
            tmp_path / "release.json",
            template,
            source_commit=SOURCE_COMMIT,
            created_at=CREATED_AT,
            artifact_root=tmp_path,
        )


@pytest.mark.parametrize(
    "mutate,error",
    [
        (lambda template, root: template.update({"unknown": True}), "unknown keys"),
        (lambda template, root: None, "missing artifact"),
        (lambda template, root: _write_artifact(root, b"wrong"), "sha256 mismatch"),
    ],
)
def test_writer_validation_failure_never_creates_partial_output(tmp_path: Path, mutate, error: str) -> None:
    template = _template()
    mutate(template, tmp_path)
    output = tmp_path / "release.json"

    with pytest.raises(ManifestError, match=error):
        write_release_manifest(
            output,
            template,
            source_commit=SOURCE_COMMIT,
            created_at=CREATED_AT,
            artifact_root=tmp_path,
        )

    assert not output.exists()


def test_writer_validation_failure_preserves_existing_output(tmp_path: Path) -> None:
    output = tmp_path / "release.json"
    output.write_text("previous\n", encoding="utf-8")

    with pytest.raises(ManifestError, match="missing artifact"):
        write_release_manifest(
            output,
            _template(),
            source_commit=SOURCE_COMMIT,
            created_at=CREATED_AT,
            artifact_root=tmp_path,
        )

    assert output.read_text(encoding="utf-8") == "previous\n"
    assert list(tmp_path.glob(".*.tmp")) == []


def test_writer_failed_atomic_replace_preserves_output_and_cleans_temporary_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_artifact(tmp_path)
    output = tmp_path / "release.json"
    original_bytes = b"previous release bytes\x00must remain exact\n"
    output.write_bytes(original_bytes)
    replace_calls: list[tuple[Path, Path]] = []

    def fail_publication(source: str | Path, destination: str | Path) -> None:
        replace_calls.append((Path(source), Path(destination)))
        raise OSError("injected atomic publication failure")

    monkeypatch.setattr("backend.scripts.write_release_manifest.os.replace", fail_publication)

    with pytest.raises(OSError, match="injected atomic publication failure"):
        write_release_manifest(
            output,
            _template(),
            source_commit=SOURCE_COMMIT,
            created_at=CREATED_AT,
            artifact_root=tmp_path,
        )

    assert len(replace_calls) == 1
    temporary_path, destination = replace_calls[0]
    assert destination == output
    assert temporary_path.parent == output.parent
    assert temporary_path.name.startswith(f".{output.name}.")
    assert temporary_path.name.endswith(".tmp")
    assert output.read_bytes() == original_bytes
    assert not temporary_path.exists()
    assert list(tmp_path.glob(".*.tmp")) == []


@pytest.mark.parametrize("alias_kind", ["direct", "symlink"])
def test_writer_rejects_output_that_aliases_a_declared_artifact_without_mutation(
    tmp_path: Path,
    alias_kind: str,
) -> None:
    artifact = tmp_path / "artifacts/model.pt"
    _write_artifact(tmp_path)
    original_bytes = artifact.read_bytes()
    output = artifact if alias_kind == "direct" else tmp_path / "release.json"
    if alias_kind == "symlink":
        output.symlink_to(artifact)

    with pytest.raises(ManifestError, match="output path aliases declared artifact.*primary-model"):
        write_release_manifest(
            output,
            _template(),
            source_commit=SOURCE_COMMIT,
            created_at=CREATED_AT,
            artifact_root=tmp_path,
        )

    assert artifact.read_bytes() == original_bytes
    assert list(tmp_path.glob(".*.tmp")) == []


def test_writer_publishes_mode_0644_and_fsyncs_file_then_parent_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_artifact(tmp_path)
    output = tmp_path / "release.json"
    original_fsync = os.fsync
    fsync_kinds: list[str] = []

    def recording_fsync(file_descriptor: int) -> None:
        mode = os.fstat(file_descriptor).st_mode
        fsync_kinds.append("directory" if stat.S_ISDIR(mode) else "file")
        original_fsync(file_descriptor)

    monkeypatch.setattr("backend.scripts.write_release_manifest.os.fsync", recording_fsync)

    write_release_manifest(
        output,
        _template(),
        source_commit=SOURCE_COMMIT,
        created_at=CREATED_AT,
        artifact_root=tmp_path,
    )

    assert stat.S_IMODE(output.stat().st_mode) == 0o644
    assert fsync_kinds == ["file", "directory"]


def test_writer_file_fsync_failure_preserves_existing_output_and_cleans_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_artifact(tmp_path)
    output = tmp_path / "release.json"
    original_bytes = b"previous release remains authoritative\n"
    output.write_bytes(original_bytes)

    def fail_file_fsync(file_descriptor: int) -> None:
        raise OSError("injected file fsync failure")

    monkeypatch.setattr("backend.scripts.write_release_manifest.os.fsync", fail_file_fsync)

    with pytest.raises(OSError, match="injected file fsync failure"):
        write_release_manifest(
            output,
            _template(),
            source_commit=SOURCE_COMMIT,
            created_at=CREATED_AT,
            artifact_root=tmp_path,
        )

    assert output.read_bytes() == original_bytes
    assert list(tmp_path.glob(".*.tmp")) == []


def test_writer_directory_fsync_failure_reports_after_complete_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_artifact(tmp_path)
    output = tmp_path / "release.json"
    output.write_text("previous\n", encoding="utf-8")
    original_fsync = os.fsync
    fsync_call_count = 0

    def fail_directory_fsync(file_descriptor: int) -> None:
        nonlocal fsync_call_count
        fsync_call_count += 1
        if stat.S_ISDIR(os.fstat(file_descriptor).st_mode):
            raise OSError("injected directory fsync failure after publication")
        original_fsync(file_descriptor)

    monkeypatch.setattr("backend.scripts.write_release_manifest.os.fsync", fail_directory_fsync)

    with pytest.raises(OSError, match="after publication"):
        write_release_manifest(
            output,
            _template(),
            source_commit=SOURCE_COMMIT,
            created_at=CREATED_AT,
            artifact_root=tmp_path,
        )

    assert fsync_call_count == 2
    assert load_release_manifest(output).source_commit == SOURCE_COMMIT
    assert stat.S_IMODE(output.stat().st_mode) == 0o644
    assert list(tmp_path.glob(".*.tmp")) == []


def test_writer_rejects_relative_artifact_root_before_writing(tmp_path: Path) -> None:
    with pytest.raises(ManifestError, match="root must be absolute"):
        write_release_manifest(
            tmp_path / "release.json",
            _template(),
            source_commit=SOURCE_COMMIT,
            created_at=CREATED_AT,
            artifact_root=Path("ambiguous"),
        )


def test_cli_requires_source_commit_and_created_at(tmp_path: Path) -> None:
    template_path = tmp_path / "template.json"
    template_path.write_text(json.dumps(_template()), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "backend.scripts.write_release_manifest", "--input", str(template_path), "--output", str(tmp_path / "out.json"), "--artifact-root", str(tmp_path)],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "--source-commit" in result.stderr
    assert "--created-at" in result.stderr


def test_cli_writes_validated_manifest_without_git_inference(tmp_path: Path) -> None:
    _write_artifact(tmp_path)
    template_path = tmp_path / "template.json"
    output = tmp_path / "release.json"
    template_path.write_text(json.dumps(_template()), encoding="utf-8")
    git_marker = tmp_path / "git-was-called"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_git = fake_bin / "git"
    fake_git.write_text(
        f"#!{sys.executable}\nfrom pathlib import Path\nPath({str(git_marker)!r}).write_text('called')\n",
        encoding="utf-8",
    )
    fake_git.chmod(0o755)
    repo_root = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "backend.scripts.write_release_manifest",
            "--input",
            str(template_path),
            "--output",
            str(output),
            "--artifact-root",
            str(tmp_path),
            "--source-commit",
            SOURCE_COMMIT,
            "--created-at",
            CREATED_AT,
        ],
        cwd=repo_root,
        env={**os.environ, "PATH": str(fake_bin)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert load_release_manifest(output).source_commit == SOURCE_COMMIT
    assert not git_marker.exists()
