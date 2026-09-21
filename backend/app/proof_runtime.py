from __future__ import annotations

import json
import os
from pathlib import Path

import boto3
from botocore.config import Config

from .release_manifest import load_release_manifest
from .runtime_options import (
    ArtifactReference,
    ObjectLoader,
    ProofRuntimeOptions,
    RuntimeOptionsError,
    configured_object_store_allowed_origins,
    materialize_artifact_reference,
    validate_primary_acquisition_mode,
)
from .storage import Storage

DEFAULT_PROOF_BASELINE_MODEL_PATH = "yolov10n.pt"
DEFAULT_PRIMARY_ACQUISITION_MODE = "anchored_player_ranked_context_960"
DEFAULT_EDGE_SHARE_REPAIR_PROFILE = None
DEFAULT_AUXILIARY_BALL_MODEL_PROFILE = None
RUNTIME_DEFAULT_REGISTRY_FILENAME = "promoted_touchline_detector_candidate.json"


def local_boto3_object_loader(reference: ArtifactReference):
    """Open a bounded-by-materializer S3 object stream for local execution."""

    if reference.kind != "object_store":
        raise RuntimeOptionsError("local object loader requires an object-store reference")
    allowed_origins = configured_object_store_allowed_origins()
    if not allowed_origins or reference.endpoint_url not in allowed_origins:
        raise RuntimeOptionsError(
            f"objectStore.endpointUrl is not present in the configured allowlist: {reference.endpoint_url}"
        )
    access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    if not access_key_id or not secret_access_key:
        raise RuntimeOptionsError(
            "object-store credentials are unavailable: AWS_ACCESS_KEY_ID and "
            "AWS_SECRET_ACCESS_KEY are required"
        )
    client_kwargs: dict[str, object] = {
        "endpoint_url": reference.endpoint_url,
        "region_name": reference.region,
        "aws_access_key_id": access_key_id,
        "aws_secret_access_key": secret_access_key,
        "config": Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    }
    session_token = os.environ.get("AWS_SESSION_TOKEN")
    if session_token:
        client_kwargs["aws_session_token"] = session_token
    try:
        client = boto3.client("s3", **client_kwargs)
        response = client.get_object(Bucket=reference.bucket, Key=reference.key)
        body = response.get("Body") if isinstance(response, dict) else None
        if body is None or not callable(getattr(body, "read", None)):
            raise RuntimeOptionsError("object-store response did not provide a readable body")
        return body
    except RuntimeOptionsError:
        raise
    except Exception as exc:
        raise RuntimeOptionsError(f"object-store reference is unavailable: {exc}") from exc


def _portable_reference(value: str | None, *, default: str | None = None) -> ArtifactReference | None:
    normalized = normalize_model_path(value) or default
    if normalized is None:
        return None
    try:
        return ArtifactReference.from_mapping({"artifactId": normalized})
    except RuntimeOptionsError as exc:
        raise RuntimeOptionsError("legacy runtime values must be portable artifact identifiers") from exc


def _typed_runtime_options_from_legacy(
    *,
    model_path: str | None,
    primary_model_path: str | None = None,
    auxiliary_ball_model_path: str | None = None,
    auxiliary_ball_model_profile: str | None = None,
    primary_acquisition_mode: str | None = None,
    edge_share_repair_profile: str | None = None,
    baseline_guided_rescue_reference_path: str | None = None,
    proposal_selection_truth_seed_path: str | None = None,
    reviewed_positive_anchor_seed_path: str | None = None,
) -> ProofRuntimeOptions:
    primary = _portable_reference(
        normalize_model_path(primary_model_path) or normalize_model_path(model_path),
        default="primary-model",
    )
    assert primary is not None
    return ProofRuntimeOptions(
        primary_model=primary,
        auxiliary_ball_model=_portable_reference(auxiliary_ball_model_path),
        auxiliary_ball_model_profile=normalize_auxiliary_ball_model_profile(auxiliary_ball_model_profile),
        primary_acquisition_mode=normalize_primary_acquisition_mode(primary_acquisition_mode),
        edge_share_repair_profile=normalize_edge_share_repair_profile(edge_share_repair_profile),
        baseline_guided_rescue_reference=_portable_reference(baseline_guided_rescue_reference_path),
        proposal_selection_truth_seed=_portable_reference(proposal_selection_truth_seed_path),
        reviewed_positive_anchor_seed=_portable_reference(reviewed_positive_anchor_seed_path),
    )


def normalize_model_path(model_path: str | None) -> str | None:
    if not isinstance(model_path, str):
        return None
    normalized = model_path.strip()
    return normalized or None


def normalize_auxiliary_ball_model_profile(auxiliary_ball_model_profile: str | None) -> str | None:
    if not isinstance(auxiliary_ball_model_profile, str):
        return DEFAULT_AUXILIARY_BALL_MODEL_PROFILE
    normalized = auxiliary_ball_model_profile.strip()
    return normalized or DEFAULT_AUXILIARY_BALL_MODEL_PROFILE


def detector_model_name(model_path: str | None) -> str | None:
    normalized = normalize_model_path(model_path)
    if normalized is None:
        return None
    return Path(normalized).name or normalized


def normalize_primary_acquisition_mode(primary_acquisition_mode: str | None) -> str:
    if not isinstance(primary_acquisition_mode, str):
        return DEFAULT_PRIMARY_ACQUISITION_MODE
    normalized = primary_acquisition_mode.strip()
    return normalized or DEFAULT_PRIMARY_ACQUISITION_MODE


def normalize_edge_share_repair_profile(edge_share_repair_profile: str | None) -> str | None:
    if not isinstance(edge_share_repair_profile, str):
        return DEFAULT_EDGE_SHARE_REPAIR_PROFILE
    normalized = edge_share_repair_profile.strip()
    return normalized or DEFAULT_EDGE_SHARE_REPAIR_PROFILE


def normalize_baseline_guided_rescue_reference_path(
    baseline_guided_rescue_reference_path: str | None,
) -> str | None:
    if not isinstance(baseline_guided_rescue_reference_path, str):
        return None
    normalized = baseline_guided_rescue_reference_path.strip()
    return normalized or None


def normalize_proposal_selection_truth_seed_path(
    proposal_selection_truth_seed_path: str | None,
) -> str | None:
    if not isinstance(proposal_selection_truth_seed_path, str):
        return None
    normalized = proposal_selection_truth_seed_path.strip()
    return normalized or None


def normalize_reviewed_positive_anchor_seed_path(
    reviewed_positive_anchor_seed_path: str | None,
) -> str | None:
    if not isinstance(reviewed_positive_anchor_seed_path, str):
        return None
    normalized = reviewed_positive_anchor_seed_path.strip()
    return normalized or None


def resolve_proof_runtime_options(
    *,
    model_path: str | None,
    primary_model_path: str | None = None,
    auxiliary_ball_model_path: str | None = None,
    auxiliary_ball_model_profile: str | None = None,
    primary_acquisition_mode: str | None = None,
    edge_share_repair_profile: str | None = None,
    baseline_guided_rescue_reference_path: str | None = None,
    proposal_selection_truth_seed_path: str | None = None,
    reviewed_positive_anchor_seed_path: str | None = None,
) -> dict[str, object]:
    """Translate the legacy call shape once, returning only canonical portable data."""

    return _typed_runtime_options_from_legacy(
        model_path=model_path,
        primary_model_path=primary_model_path,
        auxiliary_ball_model_path=auxiliary_ball_model_path,
        auxiliary_ball_model_profile=auxiliary_ball_model_profile,
        primary_acquisition_mode=primary_acquisition_mode,
        edge_share_repair_profile=edge_share_repair_profile,
        baseline_guided_rescue_reference_path=baseline_guided_rescue_reference_path,
        proposal_selection_truth_seed_path=proposal_selection_truth_seed_path,
        reviewed_positive_anchor_seed_path=reviewed_positive_anchor_seed_path,
    ).to_mapping()


def _runtime_registry_path(storage: Storage) -> Path:
    return storage.storage_root / "runtime" / RUNTIME_DEFAULT_REGISTRY_FILENAME


def load_runtime_default_registry_options(storage: Storage) -> dict[str, str] | None:
    """Load the historical v7.2 registry shape for its diagnostic script only.

    Active runtime selection must use :func:`load_proof_runtime_options` and never
    consume this path-based legacy registry.
    """

    registry_path = _runtime_registry_path(storage)
    if not registry_path.exists():
        return None
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or payload.get("runtimeDefaultMutationExecuted") is not True:
        return None
    runtime_contract = payload.get("runtimeContract")
    if not isinstance(runtime_contract, dict):
        return None
    primary = normalize_model_path(
        runtime_contract.get("primaryDetectorModelPath")
        or runtime_contract.get("primaryModelPath")
        or runtime_contract.get("modelPath")
    )
    if primary is None:
        return None
    resolved = {
        "modelPath": primary,
        "primaryModelPath": primary,
        "detectorModelName": detector_model_name(primary) or primary,
        "primaryDetectorModelName": detector_model_name(primary) or primary,
        "primaryAcquisitionMode": normalize_primary_acquisition_mode(
            runtime_contract.get("primaryAcquisitionMode")
        ),
    }
    for source_key, target_key in (
        ("auxiliaryBallModelPath", "auxiliaryBallModelPath"),
        ("auxiliaryBallModelProfile", "auxiliaryBallModelProfile"),
        ("baselineGuidedRescueReferencePath", "baselineGuidedRescueReferencePath"),
        ("proposalSelectionTruthSeedPath", "proposalSelectionTruthSeedPath"),
        ("reviewedPositiveAnchorSeedPath", "reviewedPositiveAnchorSeedPath"),
    ):
        value = runtime_contract.get(source_key)
        if isinstance(value, str) and value.strip():
            resolved[target_key] = value.strip()
    edge_profile = payload.get("runtimeDefaultProfileName") or runtime_contract.get("edgeShareRepairProfile")
    if isinstance(edge_profile, str) and edge_profile.strip():
        resolved["edgeShareRepairProfile"] = edge_profile.strip()
    auxiliary_path = resolved.get("auxiliaryBallModelPath")
    if auxiliary_path:
        resolved["auxiliaryBallModelName"] = detector_model_name(auxiliary_path) or auxiliary_path
    return resolved


def save_proof_runtime_options(
    storage: Storage,
    match_id: str,
    *,
    runtime_options: ProofRuntimeOptions | None = None,
    model_path: str | None = None,
    primary_model_path: str | None = None,
    auxiliary_ball_model_path: str | None = None,
    auxiliary_ball_model_profile: str | None = None,
    primary_acquisition_mode: str | None = None,
    edge_share_repair_profile: str | None = None,
    baseline_guided_rescue_reference_path: str | None = None,
    proposal_selection_truth_seed_path: str | None = None,
    reviewed_positive_anchor_seed_path: str | None = None,
) -> None:
    if runtime_options is not None:
        if any(
            value is not None
            for value in (
                model_path,
                primary_model_path,
                auxiliary_ball_model_path,
                auxiliary_ball_model_profile,
                primary_acquisition_mode,
                edge_share_repair_profile,
                baseline_guided_rescue_reference_path,
                proposal_selection_truth_seed_path,
                reviewed_positive_anchor_seed_path,
            )
        ):
            raise RuntimeOptionsError("runtime_options cannot be combined with legacy runtime arguments")
        storage.save_analysis_artifact(match_id, "proof_runtime_options", runtime_options.to_mapping())
        return
    normalized_model_path = normalize_model_path(model_path)
    normalized_primary_model_path = normalize_model_path(primary_model_path)
    normalized_auxiliary_ball_model_path = normalize_model_path(auxiliary_ball_model_path)
    normalized_edge_share_repair_profile = normalize_edge_share_repair_profile(edge_share_repair_profile)
    normalized_baseline_guided_rescue_reference_path = normalize_baseline_guided_rescue_reference_path(
        baseline_guided_rescue_reference_path
    )
    normalized_proposal_selection_truth_seed_path = normalize_proposal_selection_truth_seed_path(
        proposal_selection_truth_seed_path
    )
    normalized_reviewed_positive_anchor_seed_path = normalize_reviewed_positive_anchor_seed_path(
        reviewed_positive_anchor_seed_path
    )
    normalized_auxiliary_ball_model_profile = normalize_auxiliary_ball_model_profile(auxiliary_ball_model_profile)
    if (
        normalized_model_path is None
        and normalized_primary_model_path is None
        and normalized_auxiliary_ball_model_path is None
        and primary_acquisition_mode is None
        and normalized_edge_share_repair_profile is None
        and normalized_baseline_guided_rescue_reference_path is None
        and normalized_proposal_selection_truth_seed_path is None
        and normalized_reviewed_positive_anchor_seed_path is None
        and normalized_auxiliary_ball_model_profile is None
    ):
        return
    options = _typed_runtime_options_from_legacy(
        model_path=normalized_model_path,
        primary_model_path=normalized_primary_model_path,
        auxiliary_ball_model_path=normalized_auxiliary_ball_model_path,
        auxiliary_ball_model_profile=normalized_auxiliary_ball_model_profile,
        primary_acquisition_mode=primary_acquisition_mode,
        edge_share_repair_profile=normalized_edge_share_repair_profile,
        baseline_guided_rescue_reference_path=normalized_baseline_guided_rescue_reference_path,
        proposal_selection_truth_seed_path=normalized_proposal_selection_truth_seed_path,
        reviewed_positive_anchor_seed_path=normalized_reviewed_positive_anchor_seed_path,
    )
    storage.save_analysis_artifact(
        match_id,
        "proof_runtime_options",
        options.to_mapping(),
    )


def load_manifest_runtime_options(manifest_path: Path) -> ProofRuntimeOptions:
    """Load the exact validated runtime defaults declared by a release manifest."""

    if not manifest_path.is_file():
        raise RuntimeOptionsError(f"release manifest is unavailable: {manifest_path}")
    manifest = load_release_manifest(manifest_path)
    try:
        return ProofRuntimeOptions.from_mapping(manifest.runtime_options)
    except RuntimeOptionsError as exc:  # defense in depth for alternate manifest loaders
        raise RuntimeOptionsError(f"release manifest runtimeOptions are invalid: {exc}") from exc


def load_proof_runtime_options(
    storage: Storage,
    match_id: str,
    *,
    manifest_path: Path | None = None,
) -> ProofRuntimeOptions:
    artifact_path = storage._match_dir(match_id) / "proof_runtime_options.json"
    if not artifact_path.exists():
        if manifest_path is None:
            raise RuntimeOptionsError(
                "release manifest path is required when persisted runtime options are absent"
            )
        return load_manifest_runtime_options(manifest_path)
    try:
        payload = storage.load_analysis_artifact(match_id, "proof_runtime_options")
    except (OSError, ValueError, TypeError) as exc:
        raise RuntimeOptionsError(f"persisted runtime options are unreadable: {artifact_path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeOptionsError(f"persisted runtime options must be an object: {artifact_path}")
    try:
        return ProofRuntimeOptions.from_mapping(payload)
    except RuntimeOptionsError as exc:
        raise RuntimeOptionsError(f"persisted runtime options are invalid: {artifact_path}: {exc}") from exc


def materialize_proof_runtime_options(
    options: ProofRuntimeOptions,
    *,
    storage_root: Path,
    environment: str,
    manifest_path: Path,
    resolver_root: Path | None = None,
    destination_root: Path | None = None,
    object_loader: ObjectLoader | None = None,
    allowed_object_store_origins: set[str] | frozenset[str] | None = None,
    max_artifact_bytes: int | None = None,
) -> dict[str, str | None]:
    """Resolve portable references immediately before invoking the video pipeline."""

    validate_primary_acquisition_mode(options.primary_acquisition_mode)
    if not manifest_path.is_file():
        raise RuntimeOptionsError(f"release manifest is unavailable: {manifest_path}")
    manifest = load_release_manifest(manifest_path)
    if resolver_root is None:
        resolver_root = Path("/") if environment == "container" else Path(__file__).resolve().parents[2]
    materialized_root = destination_root or storage_root / "runtime-materialized"
    selected_allowed_origins = (
        configured_object_store_allowed_origins()
        if allowed_object_store_origins is None
        else frozenset(allowed_object_store_origins)
    )

    def resolve(reference: ArtifactReference | None) -> str | None:
        if reference is None:
            return None
        return str(
            materialize_artifact_reference(
                reference,
                manifest,
                resolver_root,
                environment,
                destination_root=materialized_root,
                object_loader=object_loader,
                allowed_object_store_origins=selected_allowed_origins,
                max_artifact_bytes=max_artifact_bytes,
            )
        )

    primary = resolve(options.primary_model)
    assert primary is not None
    kwargs = {
        "model_path": primary,
        "primary_model_path": primary,
        "primary_acquisition_mode": options.primary_acquisition_mode,
        "auxiliary_ball_model_profile": options.auxiliary_ball_model_profile,
        "edge_share_repair_profile": options.edge_share_repair_profile,
    }
    for key, reference in (
        ("auxiliary_ball_model_path", options.auxiliary_ball_model),
        ("baseline_guided_rescue_reference_path", options.baseline_guided_rescue_reference),
        ("proposal_selection_truth_seed_path", options.proposal_selection_truth_seed),
        ("reviewed_positive_anchor_seed_path", options.reviewed_positive_anchor_seed),
    ):
        resolved = resolve(reference)
        if resolved is not None:
            kwargs[key] = resolved
    return kwargs
