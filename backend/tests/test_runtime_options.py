from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest
import backend.app.runtime_options as runtime_options_module

from backend.app.release_manifest import ReleaseManifest
from backend.app.runtime_options import (
    ArtifactReference,
    HARD_MAX_RUNTIME_ARTIFACT_BYTES,
    ProofRuntimeOptions,
    RuntimeOptionsError,
    configured_object_store_allowed_origins,
    materialize_artifact_reference,
    proof_runtime_options_from_http_payload,
)
from backend.app.proof_runtime import (
    local_boto3_object_loader,
    load_proof_runtime_options,
    materialize_proof_runtime_options,
    resolve_proof_runtime_options,
    save_proof_runtime_options,
)
from backend.app.schemas import MatchConfig
from backend.app.storage import Storage


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _artifact(artifact_id: str, relative_path: str, container_path: str, content: bytes) -> dict[str, object]:
    return {
        "id": artifact_id,
        "sha256": _digest(content),
        "sizeBytes": len(content),
        "localRelativePath": relative_path,
        "containerPath": container_path,
        "origin": "test-fixture",
        "retentionClass": "release-essential",
    }


def _manifest(artifacts: list[dict[str, object]]) -> ReleaseManifest:
    return ReleaseManifest.from_mapping(
        {
            "schemaVersion": 1,
            "releaseVersion": "v7.3",
            "candidateVersion": "v7.3",
            "runtimeVersion": "v7.3",
            "sourceCommit": "a" * 40,
            "createdAt": "2026-08-22T12:34:56Z",
            "runtimeOptions": {
                "primary_model": {"artifactId": "primary-model"},
                "auxiliary_ball_model": None,
                "auxiliary_ball_model_profile": None,
                "primary_acquisition_mode": "anchored_player_ranked_context_960",
                "edge_share_repair_profile": None,
                "baseline_guided_rescue_reference": None,
                "proposal_selection_truth_seed": None,
                "reviewed_positive_anchor_seed": None,
            },
            "artifacts": artifacts,
            "requiredContracts": [
                "video_to_analysis_product_api_v1",
                "video_to_analysis_report_v1",
            ],
        }
    )


def _inline(name: str, content: bytes) -> dict[str, object]:
    return {
        "inline": {
            "name": name,
            "contentBase64": base64.b64encode(content).decode("ascii"),
            "sha256": _digest(content),
            "sizeBytes": len(content),
        }
    }


def _object_store(content: bytes) -> dict[str, object]:
    return {
        "objectStore": {
            "bucket": "release-inputs",
            "key": "v7.3/proposal-truth.json",
            "endpointUrl": "https://objects.example.test",
            "region": "eu-test-1",
            "sha256": _digest(content),
            "sizeBytes": len(content),
        }
    }


def _object_store_with_endpoint(content: bytes, endpoint_url: str) -> dict[str, object]:
    descriptor = _object_store(content)
    descriptor["objectStore"]["endpointUrl"] = endpoint_url  # type: ignore[index]
    return descriptor


def _options_mapping() -> dict[str, object]:
    return {
        "primary_model": {"artifactId": "primary-model"},
        "auxiliary_ball_model": {"artifactId": "auxiliary-ball-model"},
        "auxiliary_ball_model_profile": "touchline-v7-3",
        "primary_acquisition_mode": "anchored-proof-v7-3",
        "edge_share_repair_profile": "edge-share-v7-3",
        "baseline_guided_rescue_reference": _inline("baseline.json", b"baseline-reference"),
        "proposal_selection_truth_seed": _object_store(b"proposal-seed"),
        "reviewed_positive_anchor_seed": {"artifactId": "reviewed-anchor-seed"},
    }


def test_all_eight_non_default_fields_round_trip_mapping_and_json() -> None:
    expected = _options_mapping()

    options = ProofRuntimeOptions.from_mapping(expected)

    assert options.to_mapping() == expected
    assert ProofRuntimeOptions.from_json(options.to_json()) == options
    assert json.loads(options.to_json()) == expected
    with pytest.raises((AttributeError, TypeError)):
        options.primary_acquisition_mode = "changed"  # type: ignore[misc]
    assert not hasattr(options, "get")


def test_all_eight_fields_have_content_free_provenance_identity() -> None:
    options = ProofRuntimeOptions.from_mapping(_options_mapping())

    provenance = options.to_provenance_mapping()
    serialized = json.dumps(provenance)

    assert set(provenance) == set(_options_mapping())
    assert provenance["primary_model"] == {"artifactId": "primary-model"}
    assert provenance["baseline_guided_rescue_reference"] == {
        "inline": {
            "name": "baseline.json",
            "sha256": _digest(b"baseline-reference"),
            "sizeBytes": len(b"baseline-reference"),
        }
    }
    assert provenance["proposal_selection_truth_seed"] == _object_store(b"proposal-seed")
    assert "contentBase64" not in serialized
    assert base64.b64encode(b"baseline-reference").decode("ascii") not in serialized


def test_all_eight_fields_survive_saved_provenance_without_path_flattening(tmp_path: Path) -> None:
    storage = Storage(tmp_path)
    upload = storage.save_upload("clip.mp4", b"video")
    match = storage.create_match(
        name="runtime provenance",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=upload,
        config=MatchConfig(autoHomography=True),
    )
    options = ProofRuntimeOptions.from_mapping(_options_mapping())

    save_proof_runtime_options(storage, match.id, runtime_options=options)

    assert load_proof_runtime_options(storage, match.id) == options
    persisted = storage.load_analysis_artifact(match.id, "proof_runtime_options")
    assert persisted == options.to_mapping()
    assert "Path" not in json.dumps(persisted)


@pytest.mark.parametrize(
    "payload",
    [
        "{not-json",
        "[]",
        json.dumps({"modelPath": "primary-model"}),
        json.dumps(_options_mapping() | {"unknown": True}),
        json.dumps(_options_mapping() | {"primary_model": {"artifactId": "/root/WorkSpace/model.pt"}}),
    ],
    ids=["unreadable", "non-object", "legacy-flat", "unknown-key", "host-path"],
)
def test_existing_invalid_persisted_runtime_options_fail_closed(tmp_path: Path, payload: str) -> None:
    storage = Storage(tmp_path)
    upload = storage.save_upload("clip.mp4", b"video")
    match = storage.create_match(
        name="invalid runtime provenance",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=upload,
        config=MatchConfig(autoHomography=True),
    )
    artifact_path = storage._match_dir(match.id) / "proof_runtime_options.json"
    artifact_path.write_text(payload, encoding="utf-8")

    with pytest.raises(RuntimeOptionsError, match="persisted runtime options"):
        load_proof_runtime_options(storage, match.id)


def test_absent_persisted_runtime_options_require_manifest_without_consuming_legacy_registry(tmp_path: Path) -> None:
    storage = Storage(tmp_path)
    upload = storage.save_upload("clip.mp4", b"video")
    match = storage.create_match(
        name="default runtime provenance",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=upload,
        config=MatchConfig(autoHomography=True),
    )
    registry = tmp_path / "runtime/promoted_touchline_detector_candidate.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(
        json.dumps(
            {
                "runtimeDefaultMutationExecuted": True,
                "runtimeDefaultProfileName": "legacy-profile",
                "runtimeContract": {
                    "primaryDetectorModelPath": "yolov10n.pt",
                    "auxiliaryBallModelPath": "/root/WorkSpace/legacy.pt",
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeOptionsError, match="release manifest path is required"):
        load_proof_runtime_options(storage, match.id)


def test_http_model_alias_overrides_only_manifest_primary_model() -> None:
    manifest_defaults = ProofRuntimeOptions.from_mapping(
        {
            "primary_model": {"artifactId": "release-primary-model"},
            "auxiliary_ball_model": {"artifactId": "release-ball-model"},
            "auxiliary_ball_model_profile": "release-ball-profile",
            "primary_acquisition_mode": "release-acquisition",
            "edge_share_repair_profile": "release-repair",
            "baseline_guided_rescue_reference": {"artifactId": "release-baseline"},
            "proposal_selection_truth_seed": {"artifactId": "release-proposal"},
            "reviewed_positive_anchor_seed": {"artifactId": "release-anchor"},
        }
    )

    options, aliases = proof_runtime_options_from_http_payload(
        {"modelPath": "request-primary-model"}, default_options=manifest_defaults
    )

    assert options.primary_model.artifact_id == "request-primary-model"
    assert options.auxiliary_ball_model == manifest_defaults.auxiliary_ball_model
    assert options.primary_acquisition_mode == manifest_defaults.primary_acquisition_mode
    assert options.reviewed_positive_anchor_seed == manifest_defaults.reviewed_positive_anchor_seed
    assert aliases == ("modelPath",)


def test_absent_persisted_runtime_options_load_validated_manifest_and_materialize(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "storage")
    upload = storage.save_upload("clip.mp4", b"video")
    match = storage.create_match(
        name="manifest runtime default",
        input_mode="video",
        original_filename="clip.mp4",
        input_path=upload,
        config=MatchConfig(autoHomography=True),
    )
    content = b"manifest-model"
    artifact_root = tmp_path / "artifact-root"
    model_path = artifact_root / "artifacts/models/model.pt"
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(content)
    manifest = _manifest(
        [_artifact("primary-model", "artifacts/models/model.pt", "/app/models/model.pt", content)]
    )
    manifest_path = tmp_path / "release.json"
    manifest_path.write_text(manifest.to_json(), encoding="utf-8")

    options = load_proof_runtime_options(storage, match.id, manifest_path=manifest_path)
    materialized = materialize_proof_runtime_options(
        options,
        storage_root=storage.storage_root,
        environment="local",
        manifest_path=manifest_path,
        resolver_root=artifact_root.resolve(),
    )

    assert options == ProofRuntimeOptions.from_mapping(manifest.runtime_options)
    assert options.primary_acquisition_mode == "anchored_player_ranked_context_960"
    assert Path(materialized["model_path"]).read_bytes() == content


def test_http_payload_without_options_uses_validated_manifest_defaults() -> None:
    manifest_defaults = ProofRuntimeOptions.from_mapping(
        {
            "primary_model": {"artifactId": "release-primary-model"},
            "auxiliary_ball_model": None,
            "auxiliary_ball_model_profile": None,
            "primary_acquisition_mode": "manifest-default-acquisition",
            "edge_share_repair_profile": None,
            "baseline_guided_rescue_reference": None,
            "proposal_selection_truth_seed": None,
            "reviewed_positive_anchor_seed": None,
        }
    )

    options, aliases = proof_runtime_options_from_http_payload(
        {}, default_options=manifest_defaults
    )

    assert options == manifest_defaults
    assert aliases == ()
    assert options.primary_model.artifact_id != "primary-model"


@pytest.mark.parametrize(
    "payload",
    [
        {"runtimeOptions": None},
        {"runtimeOptions": None, "modelPath": "primary-model"},
        {"runtimeOptions": [], "modelPath": "primary-model"},
    ],
)
def test_http_runtime_options_key_presence_rejects_null_and_wrong_types(payload: dict[str, object]) -> None:
    with pytest.raises(RuntimeOptionsError, match="runtimeOptions"):
        proof_runtime_options_from_http_payload(payload)


def test_materialization_requires_caller_provided_manifest_path(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="manifest_path"):
        materialize_proof_runtime_options(  # type: ignore[call-arg]
            ProofRuntimeOptions.defaults(),
            storage_root=tmp_path,
            environment="local",
            resolver_root=tmp_path,
        )


def test_materialization_rejects_missing_caller_provided_manifest(tmp_path: Path) -> None:
    missing_manifest = tmp_path / "missing-v7.3.json"

    with pytest.raises(RuntimeOptionsError, match="release manifest is unavailable"):
        materialize_proof_runtime_options(
            ProofRuntimeOptions.defaults(),
            storage_root=tmp_path,
            environment="local",
            manifest_path=missing_manifest,
            resolver_root=tmp_path,
        )


def test_legacy_runtime_resolver_emits_canonical_references_and_rejects_host_paths() -> None:
    resolved = resolve_proof_runtime_options(
        model_path="primary-model",
        auxiliary_ball_model_path="auxiliary-model",
        auxiliary_ball_model_profile="aux-profile",
        primary_acquisition_mode="acquisition-v2",
        edge_share_repair_profile="repair-v2",
        baseline_guided_rescue_reference_path="baseline-reference",
        proposal_selection_truth_seed_path="proposal-seed",
        reviewed_positive_anchor_seed_path="anchor-seed",
    )

    assert resolved == {
        "primary_model": {"artifactId": "primary-model"},
        "auxiliary_ball_model": {"artifactId": "auxiliary-model"},
        "auxiliary_ball_model_profile": "aux-profile",
        "primary_acquisition_mode": "acquisition-v2",
        "edge_share_repair_profile": "repair-v2",
        "baseline_guided_rescue_reference": {"artifactId": "baseline-reference"},
        "proposal_selection_truth_seed": {"artifactId": "proposal-seed"},
        "reviewed_positive_anchor_seed": {"artifactId": "anchor-seed"},
    }
    with pytest.raises(RuntimeOptionsError, match="portable artifact identifiers"):
        resolve_proof_runtime_options(model_path="/root/WorkSpace/model.pt")


@pytest.mark.parametrize("unknown_key", ["model_path", "modelPath", "surprise"])
def test_options_reject_unknown_fields(unknown_key: str) -> None:
    payload = _options_mapping()
    payload[unknown_key] = "bad"

    with pytest.raises(RuntimeOptionsError, match="unknown fields"):
        ProofRuntimeOptions.from_mapping(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("primary_model", "model.pt"),
        ("auxiliary_ball_model", True),
        ("auxiliary_ball_model_profile", 1),
        ("primary_acquisition_mode", False),
        ("edge_share_repair_profile", []),
        ("baseline_guided_rescue_reference", "/root/WorkSpace/baseline.json"),
        ("proposal_selection_truth_seed", 1),
        ("reviewed_positive_anchor_seed", False),
    ],
)
def test_options_reject_wrong_types_and_bool_traps(field: str, value: object) -> None:
    payload = _options_mapping()
    payload[field] = value

    with pytest.raises(RuntimeOptionsError, match=field):
        ProofRuntimeOptions.from_mapping(payload)


@pytest.mark.parametrize(
    "descriptor",
    [
        {"artifactId": "primary-model", "inline": {"name": "x", "contentBase64": "eA==", "sha256": _digest(b"x"), "sizeBytes": 1}},
        {"artifactId": "../model"},
        {"artifactId": "/root/WorkSpace/model.pt"},
        _inline("../truth.json", b"truth"),
        _inline("/root/WorkSpace/truth.json", b"truth"),
        {"objectStore": {**_object_store(b"truth")["objectStore"], "key": "../truth.json"}},  # type: ignore[index]
        {"objectStore": {**_object_store(b"truth")["objectStore"], "endpointUrl": "file:///root/truth"}},  # type: ignore[index]
    ],
)
def test_reference_rejects_ambiguity_traversal_and_host_paths(descriptor: dict[str, object]) -> None:
    with pytest.raises(RuntimeOptionsError):
        ArtifactReference.from_mapping(descriptor)


@pytest.mark.parametrize(
    "endpoint_url",
    [
        "https://127.0.0.1",
        "https://[::1]",
        "https://169.254.169.254",
        "https://localhost",
        "https://objects.example.test/private",
        "https://objects.example.test?query=1",
        "https://objects.example.test#fragment",
        "https://user:secret@objects.example.test",
    ],
)
def test_object_store_endpoint_rejects_ssrf_and_non_origin_urls(endpoint_url: str) -> None:
    with pytest.raises(RuntimeOptionsError, match="endpointUrl"):
        ArtifactReference.from_mapping(_object_store_with_endpoint(b"truth", endpoint_url))


def test_object_store_endpoint_normalizes_clean_https_origin() -> None:
    reference = ArtifactReference.from_mapping(
        _object_store_with_endpoint(b"truth", "https://OBJECTS.EXAMPLE.TEST:443/")
    )

    assert reference.endpoint_url == "https://objects.example.test"


def test_configured_object_store_origins_include_explicit_runtime_origins(monkeypatch) -> None:
    monkeypatch.setenv(
        "PROOF_RUNTIME_OBJECT_STORE_ALLOWED_ORIGINS",
        "https://objects.example.test, https://release.example.test:8443/",
    )
    assert configured_object_store_allowed_origins() == frozenset(
        {
            "https://objects.example.test",
            "https://release.example.test:8443",
        }
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("sizeBytes", True),
        ("sizeBytes", 0),
        ("sha256", "A" * 64),
        ("contentBase64", "not-base64"),
    ],
)
def test_inline_reference_rejects_invalid_integrity_fields(field: str, value: object) -> None:
    descriptor = _inline("truth.json", b"truth")
    descriptor["inline"][field] = value  # type: ignore[index]

    with pytest.raises(RuntimeOptionsError):
        ArtifactReference.from_mapping(descriptor)


def test_runtime_reference_rejects_declared_size_above_hard_limit() -> None:
    descriptor = _inline("truth.json", b"truth")
    descriptor["inline"]["sizeBytes"] = HARD_MAX_RUNTIME_ARTIFACT_BYTES + 1  # type: ignore[index]

    with pytest.raises(RuntimeOptionsError, match="safe maximum"):
        ArtifactReference.from_mapping(descriptor)


@pytest.mark.parametrize("declared_size", [4, 6])
def test_inline_reference_rejects_encoded_length_that_cannot_match_declared_size(declared_size: int) -> None:
    descriptor = _inline("truth.json", b"truth")
    descriptor["inline"]["sizeBytes"] = declared_size  # type: ignore[index]

    with pytest.raises(RuntimeOptionsError, match="decoded length"):
        ArtifactReference.from_mapping(descriptor)


def test_inline_content_is_decoded_once_only_at_bounded_materialization(tmp_path: Path, monkeypatch) -> None:
    content = b"truth"
    decode_calls = 0
    real_decode = base64.b64decode

    def counting_decode(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        nonlocal decode_calls
        decode_calls += 1
        return real_decode(*args, **kwargs)

    monkeypatch.setattr(runtime_options_module.base64, "b64decode", counting_decode)
    reference = ArtifactReference.from_mapping(_inline("truth.json", content))
    assert decode_calls == 0

    resolved = materialize_artifact_reference(
        reference,
        _manifest(
            [_artifact("primary-model", "artifacts/model.pt", "/app/models/model.pt", b"model")]
        ),
        tmp_path,
        "local",
        destination_root=tmp_path / "materialized",
    )

    assert resolved.read_bytes() == content
    assert decode_calls == 1


def test_artifact_id_materializes_via_release_manifest_for_local_and_container_roots(tmp_path: Path) -> None:
    content = b"portable-model"
    artifact = _artifact(
        "primary-model",
        "release-assets/models/primary.pt",
        "/app/models/primary.pt",
        content,
    )
    manifest = _manifest([artifact])
    local_root = tmp_path / "local"
    container_root = tmp_path / "container"
    local_path = local_root / "release-assets/models/primary.pt"
    container_path = container_root / "app/models/primary.pt"
    local_path.parent.mkdir(parents=True)
    container_path.parent.mkdir(parents=True)
    local_path.write_bytes(content)
    container_path.write_bytes(content)
    reference = ArtifactReference.from_mapping({"artifactId": "primary-model"})

    resolved_local = materialize_artifact_reference(reference, manifest, local_root.resolve(), "local")
    resolved_container = materialize_artifact_reference(reference, manifest, container_root.resolve(), "container")

    assert resolved_local.read_bytes() == content
    assert resolved_container.read_bytes() == content


@pytest.mark.parametrize("descriptor_kind", ["inline", "objectStore"])
def test_inline_and_object_store_materialize_to_verified_readable_content(
    tmp_path: Path,
    descriptor_kind: str,
) -> None:
    placeholder = b"manifest-placeholder"
    manifest = _manifest(
        [_artifact("primary-model", "artifacts/model.pt", "/app/models/model.pt", placeholder)]
    )
    content = b"portable-reference"
    descriptor = _inline("reference.json", content) if descriptor_kind == "inline" else _object_store(content)
    reference = ArtifactReference.from_mapping(descriptor)
    destination_root = tmp_path / "materialized"

    def object_loader(_reference: ArtifactReference):  # noqa: ANN202
        return iter((content,))

    resolved = materialize_artifact_reference(
        reference,
        manifest,
        tmp_path.resolve(),
        "local",
        destination_root=destination_root,
        object_loader=object_loader if descriptor_kind == "objectStore" else None,
        allowed_object_store_origins={"https://objects.example.test"},
    )

    assert resolved.is_file()
    assert resolved.read_bytes() == content
    assert resolved.is_relative_to(destination_root)


def test_materialization_rejects_unknown_artifact_unavailable_object_and_integrity_mismatch(tmp_path: Path) -> None:
    content = b"model"
    manifest = _manifest(
        [_artifact("primary-model", "artifacts/model.pt", "/app/models/model.pt", content)]
    )

    with pytest.raises(RuntimeOptionsError, match="unknown artifact"):
        materialize_artifact_reference(
            ArtifactReference.from_mapping({"artifactId": "unavailable"}),
            manifest,
            tmp_path.resolve(),
            "local",
        )

    with pytest.raises(RuntimeOptionsError, match="object loader"):
        materialize_artifact_reference(
            ArtifactReference.from_mapping(_object_store(b"truth")),
            manifest,
            tmp_path.resolve(),
            "local",
            destination_root=tmp_path / "materialized",
            allowed_object_store_origins={"https://objects.example.test"},
        )

    bad_inline = _inline("truth.json", b"truth")
    bad_inline["inline"]["sha256"] = _digest(b"different")  # type: ignore[index]
    with pytest.raises(RuntimeOptionsError, match="sha256 mismatch"):
        materialize_artifact_reference(
            ArtifactReference.from_mapping(bad_inline),
            manifest,
            tmp_path.resolve(),
            "local",
            destination_root=tmp_path / "materialized",
        )


def test_materialization_rejects_object_size_mismatch(tmp_path: Path) -> None:
    content = b"truth"
    manifest = _manifest(
        [_artifact("primary-model", "artifacts/model.pt", "/app/models/model.pt", b"model")]
    )
    reference = ArtifactReference.from_mapping(_object_store(content))

    def corrupt_loader(_reference: ArtifactReference):  # noqa: ANN202
        return iter((content + b"-corrupt",))

    with pytest.raises(RuntimeOptionsError, match="exceeds declared size"):
        materialize_artifact_reference(
            reference,
            manifest,
            tmp_path.resolve(),
            "container",
            destination_root=tmp_path / "materialized",
            object_loader=corrupt_loader,
            allowed_object_store_origins={"https://objects.example.test"},
        )


def test_object_store_materialization_fails_closed_without_allowlist_or_on_origin_mismatch(tmp_path: Path) -> None:
    content = b"truth"
    reference = ArtifactReference.from_mapping(_object_store(content))
    loader_called = False

    def object_loader(_reference: ArtifactReference):  # noqa: ANN202
        nonlocal loader_called
        loader_called = True
        return iter((content,))

    manifest = _manifest(
        [_artifact("primary-model", "artifacts/model.pt", "/app/models/model.pt", b"model")]
    )
    for allowed in (None, {"https://different.example.test"}):
        with pytest.raises(RuntimeOptionsError, match="allowlist"):
            materialize_artifact_reference(
                reference,
                manifest,
                tmp_path,
                "local",
                destination_root=tmp_path / "materialized",
                object_loader=object_loader,
                allowed_object_store_origins=allowed,
            )

    assert loader_called is False


def test_local_object_loader_fails_clearly_without_explicit_credentials(monkeypatch) -> None:
    monkeypatch.setenv("PROOF_RUNTIME_OBJECT_STORE_ALLOWED_ORIGINS", "https://objects.example.test")
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

    with pytest.raises(RuntimeOptionsError, match="credentials are unavailable"):
        local_boto3_object_loader(ArtifactReference.from_mapping(_object_store(b"truth")))


def test_object_store_materialization_streams_atomically_and_stops_before_oversize_write(tmp_path: Path) -> None:
    content = b"truth"
    reference = ArtifactReference.from_mapping(_object_store(content))
    destination_root = tmp_path / "materialized"
    chunks_requested: list[int] = []
    manifest = _manifest(
        [_artifact("primary-model", "artifacts/model.pt", "/app/models/model.pt", b"model")]
    )

    def oversized_loader(_reference: ArtifactReference):  # noqa: ANN202
        chunks_requested.append(1)
        yield b"tr"
        chunks_requested.append(2)
        yield b"uth-overflow"
        chunks_requested.append(3)
        yield b"must-not-be-read"

    with pytest.raises(RuntimeOptionsError, match="exceeds declared size"):
        materialize_artifact_reference(
            reference,
            manifest,
            tmp_path,
            "local",
            destination_root=destination_root,
            object_loader=oversized_loader,
            allowed_object_store_origins={"https://objects.example.test"},
        )

    assert chunks_requested == [1, 2]
    assert list(destination_root.iterdir()) == []


def test_object_store_materialization_cleans_partial_temp_and_corrupt_cache_on_loader_failure(tmp_path: Path) -> None:
    content = b"truth"
    reference = ArtifactReference.from_mapping(_object_store(content))
    destination_root = tmp_path / "materialized"
    destination_root.mkdir()
    expected_final = destination_root / f"{_digest(content)}-proposal-truth.json"
    expected_final.write_bytes(b"corrupt-cache")
    manifest = _manifest(
        [_artifact("primary-model", "artifacts/model.pt", "/app/models/model.pt", b"model")]
    )

    def failing_loader(_reference: ArtifactReference):  # noqa: ANN202
        yield b"tr"
        raise OSError("stream failed")

    with pytest.raises(RuntimeOptionsError, match="stream failed"):
        materialize_artifact_reference(
            reference,
            manifest,
            tmp_path,
            "local",
            destination_root=destination_root,
            object_loader=failing_loader,
            allowed_object_store_origins={"https://objects.example.test"},
        )

    assert not expected_final.exists()
    assert list(destination_root.iterdir()) == []


def test_materialization_enforces_downward_execution_limit_and_reuses_only_verified_final(tmp_path: Path) -> None:
    content = b"truth"
    reference = ArtifactReference.from_mapping(_object_store(content))
    destination_root = tmp_path / "materialized"
    manifest = _manifest(
        [_artifact("primary-model", "artifacts/model.pt", "/app/models/model.pt", b"model")]
    )

    with pytest.raises(RuntimeOptionsError, match="configured maximum"):
        materialize_artifact_reference(
            reference,
            manifest,
            tmp_path,
            "local",
            destination_root=destination_root,
            object_loader=lambda _reference: iter((content,)),
            allowed_object_store_origins={"https://objects.example.test"},
            max_artifact_bytes=len(content) - 1,
        )
    assert list(destination_root.iterdir()) == []

    resolved = materialize_artifact_reference(
        reference,
        manifest,
        tmp_path,
        "local",
        destination_root=destination_root,
        object_loader=lambda _reference: iter((content,)),
        allowed_object_store_origins={"https://objects.example.test"},
    )
    assert resolved.name == f"{_digest(content)}-proposal-truth.json"
    assert resolved.read_bytes() == content
    assert resolved.stat().st_mode & 0o777 == 0o600

    with pytest.raises(RuntimeOptionsError, match="allowlist"):
        materialize_artifact_reference(
            reference,
            manifest,
            tmp_path,
            "local",
            destination_root=destination_root,
            object_loader=lambda _reference: iter((content,)),
        )

    def must_not_reload(_reference: ArtifactReference):  # noqa: ANN202
        raise AssertionError("verified final should be reused")

    assert materialize_artifact_reference(
        reference,
        manifest,
        tmp_path,
        "local",
        destination_root=destination_root,
        object_loader=must_not_reload,
        allowed_object_store_origins={"https://objects.example.test"},
    ) == resolved


def test_execution_limit_can_be_configured_downward_by_operator_env(tmp_path: Path, monkeypatch) -> None:
    content = b"truth"
    monkeypatch.setenv("PROOF_RUNTIME_MAX_ARTIFACT_BYTES", str(len(content) - 1))

    with pytest.raises(RuntimeOptionsError, match="configured maximum"):
        materialize_artifact_reference(
            ArtifactReference.from_mapping(_object_store(content)),
            _manifest(
                [_artifact("primary-model", "artifacts/model.pt", "/app/models/model.pt", b"model")]
            ),
            tmp_path,
            "local",
            destination_root=tmp_path / "materialized",
            object_loader=lambda _reference: iter((content,)),
            allowed_object_store_origins={"https://objects.example.test"},
        )


@pytest.mark.parametrize("environment", ["local", "container"])
def test_all_five_runtime_references_materialize_verified_readable_files(
    tmp_path: Path,
    environment: str,
) -> None:
    primary_content = b"primary-model-content"
    auxiliary_content = b"auxiliary-model-content"
    baseline_content = b"baseline-reference-content"
    proposal_content = b"proposal-seed-content"
    anchor_content = b"reviewed-anchor-content"
    manifest = _manifest(
        [
            _artifact(
                "primary-model",
                "release-assets/models/primary.pt",
                "/app/models/primary.pt",
                primary_content,
            ),
            _artifact(
                "reviewed-anchor-seed",
                "release-assets/inputs/anchor.json",
                "/app/release-inputs/anchor.json",
                anchor_content,
            ),
        ]
    )
    manifest_path = tmp_path / "v7.3.json"
    manifest_path.write_text(manifest.to_json(), encoding="utf-8")
    resolver_root = tmp_path / f"{environment}-root"
    if environment == "local":
        primary_path = resolver_root / "release-assets/models/primary.pt"
        anchor_path = resolver_root / "release-assets/inputs/anchor.json"
    else:
        primary_path = resolver_root / "app/models/primary.pt"
        anchor_path = resolver_root / "app/release-inputs/anchor.json"
    primary_path.parent.mkdir(parents=True)
    anchor_path.parent.mkdir(parents=True)
    primary_path.write_bytes(primary_content)
    anchor_path.write_bytes(anchor_content)
    options = ProofRuntimeOptions.from_mapping(
        {
            "primary_model": {"artifactId": "primary-model"},
            "auxiliary_ball_model": _inline("auxiliary.pt", auxiliary_content),
            "auxiliary_ball_model_profile": "aux-profile",
            "primary_acquisition_mode": "anchored_player_ranked_context_960",
            "edge_share_repair_profile": "repair-v2",
            "baseline_guided_rescue_reference": _object_store(baseline_content),
            "proposal_selection_truth_seed": _inline("proposal.json", proposal_content),
            "reviewed_positive_anchor_seed": {"artifactId": "reviewed-anchor-seed"},
        }
    )

    def object_loader(_reference: ArtifactReference):  # noqa: ANN202
        return iter((baseline_content,))

    kwargs = materialize_proof_runtime_options(
        options,
        storage_root=tmp_path,
        environment=environment,
        manifest_path=manifest_path,
        resolver_root=resolver_root.resolve(),
        destination_root=tmp_path / f"{environment}-materialized",
        object_loader=object_loader,
        allowed_object_store_origins={"https://objects.example.test"},
    )

    assert Path(kwargs["model_path"]).read_bytes() == primary_content
    assert Path(kwargs["primary_model_path"]).read_bytes() == primary_content
    assert Path(kwargs["auxiliary_ball_model_path"]).read_bytes() == auxiliary_content
    assert Path(kwargs["baseline_guided_rescue_reference_path"]).read_bytes() == baseline_content
    assert Path(kwargs["proposal_selection_truth_seed_path"]).read_bytes() == proposal_content
    assert Path(kwargs["reviewed_positive_anchor_seed_path"]).read_bytes() == anchor_content
    assert kwargs["auxiliary_ball_model_profile"] == "aux-profile"
    assert kwargs["edge_share_repair_profile"] == "repair-v2"
    assert kwargs["primary_acquisition_mode"] == "anchored_player_ranked_context_960"
    assert options.primary_acquisition_mode == kwargs["primary_acquisition_mode"]
