from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from backend.app.release_manifest import (
    Artifact,
    ManifestError,
    ReleaseManifest,
    load_release_manifest,
    resolve_artifact,
)


SOURCE_COMMIT = "a" * 40
KNOWN_CONTRACTS = ["video_to_analysis_product_api_v1", "video_to_analysis_report_v1"]


def _artifact(content: bytes = b"model") -> dict[str, object]:
    return {
        "id": "primary-model",
        "sha256": hashlib.sha256(content).hexdigest(),
        "sizeBytes": len(content),
        "localRelativePath": "artifacts/models/model.pt",
        "containerPath": "/app/models/model.pt",
        "origin": "external-recovery-archive",
        "retentionClass": "release-essential",
    }


def _manifest_mapping(content: bytes = b"model") -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "releaseVersion": "v7.3",
        "candidateVersion": "v7.3",
        "runtimeVersion": "v7.3",
        "sourceCommit": SOURCE_COMMIT,
        "createdAt": "2026-08-22T12:34:56Z",
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
        "artifacts": [_artifact(content)],
        "requiredContracts": KNOWN_CONTRACTS,
    }


@pytest.mark.parametrize("key", list(_manifest_mapping()))
def test_manifest_rejects_each_missing_top_level_key(key: str) -> None:
    payload = _manifest_mapping()
    del payload[key]

    with pytest.raises(ManifestError, match="missing keys"):
        ReleaseManifest.from_mapping(payload)


def test_manifest_rejects_unknown_top_level_key() -> None:
    payload = _manifest_mapping()
    payload["surprise"] = True

    with pytest.raises(ManifestError, match="unknown keys.*surprise"):
        ReleaseManifest.from_mapping(payload)


def test_manifest_rejects_non_string_object_keys_cleanly() -> None:
    payload = _manifest_mapping()
    payload[1] = "not-json"  # type: ignore[index]

    with pytest.raises(ManifestError, match="object keys must be strings"):
        ReleaseManifest.from_mapping(payload)


@pytest.mark.parametrize("key", list(_artifact()))
def test_artifact_rejects_each_missing_key(key: str) -> None:
    payload = _manifest_mapping()
    del payload["artifacts"][0][key]  # type: ignore[index]

    with pytest.raises(ManifestError, match="missing keys"):
        ReleaseManifest.from_mapping(payload)


def test_artifact_rejects_unknown_key() -> None:
    payload = _manifest_mapping()
    payload["artifacts"][0]["surprise"] = True  # type: ignore[index]

    with pytest.raises(ManifestError, match="unknown keys.*surprise"):
        ReleaseManifest.from_mapping(payload)


@pytest.mark.parametrize("value", [0, 2, "1", True, None])
def test_manifest_rejects_unsupported_schema_versions_and_bool(value: object) -> None:
    payload = _manifest_mapping()
    payload["schemaVersion"] = value

    with pytest.raises(ManifestError, match="schemaVersion"):
        ReleaseManifest.from_mapping(payload)


@pytest.mark.parametrize(
    "value",
    [
        "2026-08-22",
        "2026-08-22T12:34:56",
        "2026-08-22 12:34:56Z",
        "2026-08-22T12:34:56z",
        "2026-13-22T12:34:56Z",
        123,
    ],
)
def test_manifest_rejects_non_rfc3339_timestamps(value: object) -> None:
    payload = _manifest_mapping()
    payload["createdAt"] = value

    with pytest.raises(ManifestError, match="createdAt"):
        ReleaseManifest.from_mapping(payload)


@pytest.mark.parametrize(
    "key,value",
    [
        ("releaseVersion", "7.3"),
        ("candidateVersion", "v7"),
        ("runtimeVersion", "v7.3/dirty"),
        ("runtimeVersion", True),
    ],
)
def test_manifest_rejects_invalid_versions(key: str, value: object) -> None:
    payload = _manifest_mapping()
    payload[key] = value

    with pytest.raises(ManifestError, match=key):
        ReleaseManifest.from_mapping(payload)


@pytest.mark.parametrize("value", ["a" * 39, "A" * 40, "g" * 40, True])
def test_manifest_rejects_invalid_source_commit(value: object) -> None:
    payload = _manifest_mapping()
    payload["sourceCommit"] = value

    with pytest.raises(ManifestError, match="sourceCommit"):
        ReleaseManifest.from_mapping(payload)


@pytest.mark.parametrize("value", ["a" * 63, "A" * 64, "g" * 64, True])
def test_artifact_rejects_invalid_sha256(value: object) -> None:
    payload = _manifest_mapping()
    payload["artifacts"][0]["sha256"] = value  # type: ignore[index]

    with pytest.raises(ManifestError, match="sha256"):
        ReleaseManifest.from_mapping(payload)


@pytest.mark.parametrize("value", [0, -1, 1.5, "5", True])
def test_artifact_rejects_non_positive_integer_sizes_and_bool(value: object) -> None:
    payload = _manifest_mapping()
    payload["artifacts"][0]["sizeBytes"] = value  # type: ignore[index]

    with pytest.raises(ManifestError, match="sizeBytes"):
        ReleaseManifest.from_mapping(payload)


def test_manifest_rejects_duplicate_artifact_ids() -> None:
    payload = _manifest_mapping()
    payload["artifacts"] = [_artifact(), {**_artifact(), "localRelativePath": "other.pt", "containerPath": "/app/models/other.pt"}]

    with pytest.raises(ManifestError, match="duplicate artifact id"):
        ReleaseManifest.from_mapping(payload)


@pytest.mark.parametrize("field", ["localRelativePath", "containerPath"])
def test_manifest_rejects_duplicate_artifact_paths(field: str) -> None:
    first = _artifact()
    second = {
        **_artifact(b"other"),
        "id": "secondary-model",
        "localRelativePath": "artifacts/models/other.pt",
        "containerPath": "/app/models/other.pt",
    }
    second[field] = first[field]
    payload = _manifest_mapping()
    payload["artifacts"] = [first, second]

    with pytest.raises(ManifestError, match=f"duplicate artifact {field}"):
        ReleaseManifest.from_mapping(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("localRelativePath", "../model.pt"),
        ("localRelativePath", "artifacts/../model.pt"),
        ("localRelativePath", "./model.pt"),
        ("localRelativePath", "artifacts\\model.pt"),
        ("localRelativePath", "/root/WorkSpace/model.pt"),
        ("containerPath", "/app/models/../secrets"),
        ("containerPath", "/app/release-inputs/../../root/secret"),
        ("containerPath", "/root/WorkSpace/model.pt"),
        ("containerPath", "/app/other/model.pt"),
    ],
)
def test_artifact_rejects_traversal_and_forbidden_paths(field: str, value: str) -> None:
    payload = _manifest_mapping()
    payload["artifacts"][0][field] = value  # type: ignore[index]

    with pytest.raises(ManifestError, match=field):
        ReleaseManifest.from_mapping(payload)


@pytest.mark.parametrize("container_path", ["/app/models/model.pt", "/app/release-inputs/truth.json"])
def test_artifact_accepts_declared_container_namespaces(container_path: str) -> None:
    payload = _manifest_mapping()
    payload["artifacts"][0]["containerPath"] = container_path  # type: ignore[index]

    assert ReleaseManifest.from_mapping(payload).artifacts[0].container_path == container_path


def test_manifest_rejects_unknown_required_contract() -> None:
    payload = _manifest_mapping()
    payload["requiredContracts"] = ["unknown_contract_v1"]

    with pytest.raises(ManifestError, match="unknown required contract"):
        ReleaseManifest.from_mapping(payload)


def test_v73_manifest_requires_both_product_and_report_contracts() -> None:
    payload = _manifest_mapping()
    payload["requiredContracts"] = ["video_to_analysis_product_api_v1"]

    with pytest.raises(ManifestError, match="requiredContracts.*exactly"):
        ReleaseManifest.from_mapping(payload)


@pytest.mark.parametrize("field", ["candidateVersion", "runtimeVersion"])
def test_v73_manifest_rejects_version_skew(field: str) -> None:
    payload = _manifest_mapping()
    payload[field] = "v7.2"

    with pytest.raises(ManifestError, match="releaseVersion.*candidateVersion.*runtimeVersion"):
        ReleaseManifest.from_mapping(payload)


def test_manifest_rejects_runtime_option_artifact_reference_not_declared() -> None:
    payload = _manifest_mapping()
    payload["runtimeOptions"]["primary_model"] = {"artifactId": "undeclared-model"}  # type: ignore[index]

    with pytest.raises(ManifestError, match="runtimeOptions.*undeclared artifact.*undeclared-model"):
        ReleaseManifest.from_mapping(payload)


def test_manifest_rejects_arbitrary_or_incomplete_runtime_option_shape() -> None:
    payload = _manifest_mapping()
    payload["runtimeOptions"]["arbitrary"] = True  # type: ignore[index]

    with pytest.raises(ManifestError, match="runtimeOptions"):
        ReleaseManifest.from_mapping(payload)


@pytest.mark.parametrize("value", ["not-a-list", [True], KNOWN_CONTRACTS + [KNOWN_CONTRACTS[0]]])
def test_manifest_rejects_invalid_or_duplicate_required_contracts(value: object) -> None:
    payload = _manifest_mapping()
    payload["requiredContracts"] = value

    with pytest.raises(ManifestError, match="requiredContracts"):
        ReleaseManifest.from_mapping(payload)


def test_manifest_rejects_non_json_or_non_object_runtime_options() -> None:
    for value in ([], {"bad": object()}, {1: "bad"}):
        payload = _manifest_mapping()
        payload["runtimeOptions"] = value
        with pytest.raises(ManifestError, match="runtimeOptions"):
            ReleaseManifest.from_mapping(payload)


@pytest.mark.parametrize("value", ["/root/WorkSpace/model.pt", "~/model.pt", "C:\\models\\model.pt", "file:///root/model.pt"])
def test_manifest_rejects_host_paths_nested_in_runtime_options(value: str) -> None:
    payload = _manifest_mapping()
    payload["runtimeOptions"] = {"primary_model": {"path": value}}

    with pytest.raises(ManifestError, match="runtimeOptions.*host path"):
        ReleaseManifest.from_mapping(payload)


@pytest.mark.parametrize("value", ["/root/WorkSpace/archive", "~/archive", "C:\\archive", "file:///root/archive"])
def test_manifest_rejects_host_path_artifact_origins(value: str) -> None:
    payload = _manifest_mapping()
    payload["artifacts"][0]["origin"] = value  # type: ignore[index]

    with pytest.raises(ManifestError, match="origin.*lower-case portable identifier"):
        ReleaseManifest.from_mapping(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("origin", "../../recovery/archive"),
        ("origin", "External-Recovery-Archive"),
        ("origin", "external recovery archive"),
        ("origin", "s3://release-bucket/model.pt"),
        ("retentionClass", "/root/retained"),
        ("retentionClass", "Required-Local"),
        ("retentionClass", "required/local"),
        ("retentionClass", "required local"),
    ],
)
def test_artifact_metadata_requires_lower_case_portable_identifiers(field: str, value: str) -> None:
    payload = _manifest_mapping()
    payload["artifacts"][0][field] = value  # type: ignore[index]

    with pytest.raises(ManifestError, match=f"{field}.*lower-case portable identifier"):
        ReleaseManifest.from_mapping(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("origin", "ultralytics-yolov10n"),
        ("origin", "v7-3-bounded-retrain"),
        ("retentionClass", "required-local-ignored-model"),
        ("retentionClass", "release-essential"),
    ],
)
def test_artifact_metadata_accepts_intended_task_4_identifiers(field: str, value: str) -> None:
    payload = _manifest_mapping()
    payload["artifacts"][0][field] = value  # type: ignore[index]

    artifact = ReleaseManifest.from_mapping(payload).artifacts[0]

    assert getattr(artifact, "retention_class" if field == "retentionClass" else field) == value


@pytest.mark.parametrize(
    "host_key",
    [
        "/root/WorkSpace/model.pt",
        "~/model.pt",
        "C:\\models\\model.pt",
        "file:///root/model.pt",
    ],
)
def test_manifest_rejects_host_paths_in_nested_runtime_option_keys(host_key: str) -> None:
    payload = _manifest_mapping()
    payload["runtimeOptions"] = {"primary_model": {host_key: "innocent-value"}}

    with pytest.raises(ManifestError, match="runtimeOptions.*host path"):
        ReleaseManifest.from_mapping(payload)


def test_frozen_values_round_trip_without_exposing_mutable_state() -> None:
    payload = _manifest_mapping()
    manifest = ReleaseManifest.from_mapping(payload)
    payload["runtimeOptions"]["changed"] = True  # type: ignore[index]

    assert manifest.to_mapping() == _manifest_mapping()
    with pytest.raises((AttributeError, TypeError)):
        manifest.release_version = "v9.0"  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError)):
        manifest.runtime_options["changed"] = True  # type: ignore[index]


def test_stable_json_round_trip_and_duplicate_json_key_rejection(tmp_path: Path) -> None:
    path = tmp_path / "release.json"
    path.write_text(json.dumps(_manifest_mapping()), encoding="utf-8")
    manifest = load_release_manifest(path)

    assert manifest.to_json() == json.dumps(_manifest_mapping(), indent=2, sort_keys=True) + "\n"

    path.write_text('{"schemaVersion": 1, "schemaVersion": 1}', encoding="utf-8")
    with pytest.raises(ManifestError, match="duplicate JSON key"):
        load_release_manifest(path)


def test_source_verification_rejects_mismatch() -> None:
    manifest = ReleaseManifest.from_mapping(_manifest_mapping())

    with pytest.raises(ManifestError, match="source commit mismatch"):
        manifest.validate_source_commit("b" * 40)


def _write_artifact(root: Path, content: bytes = b"model") -> Path:
    path = root / "artifacts/models/model.pt"
    path.parent.mkdir(parents=True)
    path.write_bytes(content)
    return path


def test_local_resolver_requires_an_absolute_unambiguous_root(tmp_path: Path) -> None:
    manifest = ReleaseManifest.from_mapping(_manifest_mapping())

    with pytest.raises(ManifestError, match="root must be absolute"):
        resolve_artifact(manifest, "primary-model", Path("relative-root"), "local")


def test_local_resolver_returns_verified_file(tmp_path: Path) -> None:
    expected = _write_artifact(tmp_path)
    manifest = ReleaseManifest.from_mapping(_manifest_mapping())

    assert resolve_artifact(manifest, "primary-model", tmp_path, "local") == expected.resolve()


def test_container_resolver_maps_both_allowed_namespaces_under_root(tmp_path: Path) -> None:
    payload = _manifest_mapping()
    payload["artifacts"][0]["containerPath"] = "/app/release-inputs/model.pt"  # type: ignore[index]
    path = tmp_path / "app/release-inputs/model.pt"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"model")

    assert resolve_artifact(ReleaseManifest.from_mapping(payload), "primary-model", tmp_path, "container") == path.resolve()


def test_resolver_rejects_unknown_environment_and_artifact(tmp_path: Path) -> None:
    manifest = ReleaseManifest.from_mapping(_manifest_mapping())
    with pytest.raises(ManifestError, match="unknown environment"):
        resolve_artifact(manifest, "primary-model", tmp_path, "workstation")
    with pytest.raises(ManifestError, match="unknown artifact"):
        resolve_artifact(manifest, "missing", tmp_path, "local")


@pytest.mark.parametrize(
    "mutation,error",
    [
        (lambda path: None, "missing artifact"),
        (lambda path: path.write_bytes(b"x"), "size mismatch"),
        (lambda path: path.write_bytes(b"other"), "sha256 mismatch"),
    ],
)
def test_resolver_rejects_missing_wrong_size_and_wrong_hash(tmp_path: Path, mutation, error: str) -> None:
    expected = tmp_path / "artifacts/models/model.pt"
    expected.parent.mkdir(parents=True)
    mutation(expected)
    manifest = ReleaseManifest.from_mapping(_manifest_mapping())

    with pytest.raises(ManifestError, match=error) as raised:
        resolve_artifact(manifest, "primary-model", tmp_path, "local")

    message = str(raised.value)
    assert "primary-model" in message
    assert _artifact()["sha256"] in message
    assert str(expected.resolve()) in message


def test_resolver_rejects_symlink_escape_after_filesystem_resolution(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside-model.pt"
    outside.write_bytes(b"model")
    link = tmp_path / "artifacts/models/model.pt"
    link.parent.mkdir(parents=True)
    link.symlink_to(outside)
    manifest = ReleaseManifest.from_mapping(_manifest_mapping())

    try:
        with pytest.raises(ManifestError, match="escapes resolver root"):
            resolve_artifact(manifest, "primary-model", tmp_path, "local")
    finally:
        outside.unlink()


def test_streaming_hash_uses_repeated_bounded_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = b"m" * (2 * 1024 * 1024 + 1)
    expected = _write_artifact(tmp_path, content)
    manifest = ReleaseManifest.from_mapping(_manifest_mapping(content))
    original_open = Path.open
    read_sizes: list[int] = []

    class BoundedReader:
        def __init__(self, stream) -> None:
            self._stream = stream

        def __enter__(self):
            return self

        def __exit__(self, exception_type, exception, traceback) -> None:
            self._stream.close()

        def read(self, size: int = -1) -> bytes:
            assert size is not None and size > 0, "checksum reader requested an unbounded read"
            read_sizes.append(size)
            return self._stream.read(size)

    def probing_open(path: Path, mode: str = "r", *args, **kwargs):
        stream = original_open(path, mode, *args, **kwargs)
        return BoundedReader(stream) if path == expected.resolve() and mode == "rb" else stream

    monkeypatch.setattr(Path, "open", probing_open)

    assert resolve_artifact(manifest, "primary-model", tmp_path, "local") == expected.resolve()
    assert len(read_sizes) >= 4
    assert set(read_sizes) == {1024 * 1024}


def test_artifact_dataclass_is_frozen() -> None:
    artifact = Artifact.from_mapping(_artifact())
    with pytest.raises((AttributeError, TypeError)):
        artifact.id = "changed"  # type: ignore[misc]
