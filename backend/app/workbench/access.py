"""9.2 object-level access. Do not trust a client-supplied tenant ID."""

from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlparse

SIZE_QUOTA_BYTES = 5_368_709_120
DURATION_QUOTA_SECONDS = 8_000


def authorize_object(
    *,
    object_id: str,
    session_tenant: str,
    client_tenant: str | None = None,
    object_tenant: str | None = None,
) -> dict[str, Any]:
    del client_tenant, object_id
    tenant = session_tenant
    allowed = object_tenant is None or object_tenant == session_tenant
    return {"allowed": allowed, "tenant": tenant}


def signed_scoped_object_access(*, token: str | None, object_id: str, token_object_id: str | None) -> dict[str, Any]:
    del token, object_id, token_object_id
    return {
        "admitted": False,
        "scoped": False,
        "hmacOrJwtImplemented": False,
        "reasonCodes": ["HOSTED_SIGNED_ACCESS_UNIMPLEMENTED", "UNSIGNED_OR_UNSCOPED_OBJECT_ACCESS"],
    }


def object_access_decision(
    *,
    object_id: str,
    object_tenant: str | None,
    authorization: str | None,
    object_scope: str | None,
    deployment_boundary: str | None,
    client_tenant: str | None = None,
) -> dict[str, Any]:
    del client_tenant
    boundary = (deployment_boundary or "loopback").lower()
    if boundary == "loopback" and not authorization:
        session_tenant = object_tenant or "loopback"
        decision = authorize_object(object_id=object_id, session_tenant=session_tenant, object_tenant=object_tenant)
        return {
            "allowed": decision["allowed"],
            "admitted": decision["allowed"],
            "sessionTenant": session_tenant,
            "reasonCodes": [] if decision["allowed"] else ["OBJECT_ACCESS_DENIED"],
        }
    scoped = signed_scoped_object_access(token=authorization, object_id=object_id, token_object_id=object_scope)
    return {
        "allowed": False,
        "admitted": False,
        "sessionTenant": None,
        "reasonCodes": list(scoped["reasonCodes"]),
    }


def mint_sharing_link(*, object_id: str, now: float, ttl_seconds: float) -> dict[str, Any]:
    expires_at = now + ttl_seconds

    def expired(at: float) -> bool:
        return at >= expires_at

    expired_fn: Callable[[float], bool] = expired
    return {"objectId": object_id, "expiresAt": expires_at, "expired": expired_fn}


def upload_quota(*, byte_size: int, duration_seconds: float) -> dict[str, Any]:
    reasons: list[str] = []
    if byte_size > SIZE_QUOTA_BYTES:
        reasons.append("SIZE_QUOTA")
    if duration_seconds > DURATION_QUOTA_SECONDS:
        reasons.append("DURATION_QUOTA")
    return {"admitted": not reasons, "reasonCodes": reasons}


def access_deletion_procedure(*, requested: bool, controller_recorded: bool) -> dict[str, Any]:
    available = controller_recorded
    executed = bool(requested and controller_recorded)
    reasons: list[str] = []
    if not controller_recorded:
        reasons.append("CONTROLLER_PROCESSOR_ROLES_REQUIRED")
    return {
        "available": available,
        "executed": executed,
        "trackIdsDoNotAnonymise": True,
        "reasonCodes": reasons,
    }


def stale_permissions(*, permission_expires_at: float, now: float) -> dict[str, Any]:
    stale = now >= permission_expires_at
    return {
        "stale": stale,
        "admitted": not stale,
        "reasonCodes": ["STALE_PERMISSION"] if stale else [],
    }


def untrusted_model_output(
    *,
    claimed_actions: list[str],
    allowed_actions: frozenset[str],
    evidence_ids: list[str],
    known_ids: set[str],
) -> dict[str, Any]:
    reasons = ["UNTRUSTED_MODEL_OUTPUT"]
    illegal = [action for action in claimed_actions if action not in allowed_actions]
    unknown_refs = [item for item in evidence_ids if item not in known_ids]
    if illegal:
        reasons.append("ACTION_NOT_ALLOWLISTED")
    if unknown_refs:
        reasons.append("UNKNOWN_EVIDENCE_REFERENCE")
    return {
        "trusted": False,
        "admitted": not illegal and not unknown_refs,
        "reasonCodes": reasons,
    }


def deployment_encryption(*, boundary: str) -> dict[str, Any]:
    hosted = boundary != "loopback"
    return {
        "boundary": boundary,
        "atRestRequiredForHosted": True,
        "loopbackLocalFilesystem": not hosted,
        "hostedEncryptionProven": False,
        "reasonCodes": ["HOSTED_ENCRYPTION_UNPROVEN"] if hosted else [],
    }


_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def protocol_network_allowlist(*, url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").lower()
    if scheme == "file" or (scheme in {"http", "https"} and host in _LOOPBACK_HOSTS):
        return {"admitted": True, "reasonCodes": []}
    return {
        "admitted": False,
        "reasonCodes": ["PROTOCOL_OR_NETWORK_NOT_ALLOWLISTED"],
    }


def constrained_decoder(*, argv: list[str], network_enabled: bool) -> dict[str, Any]:
    joined = " ".join(argv)
    networked = network_enabled or any(
        token.startswith(("http:", "https:", "ftp:", "rtmp:", "rtsp:")) or "://" in token for token in argv
    ) or "http://" in joined or "https://" in joined
    if not argv or argv[0] not in {"ffmpeg", "ffprobe"} or networked:
        return {"admitted": False, "reasonCodes": ["UNCONSTRAINED_DECODER"]}
    return {"admitted": True, "reasonCodes": []}


def least_privilege_storage(*, credential_scope: str) -> dict[str, Any]:
    admitted = credential_scope == "object"
    return {
        "admitted": admitted,
        "reasonCodes": [] if admitted else ["LEAST_PRIVILEGE_REQUIRED"],
    }


def public_exposure_gate(*, security_review_accepted: bool, bound: str) -> dict[str, Any]:
    public_ok = bool(security_review_accepted) and bound != "loopback"
    admitted = bound == "loopback" or bool(security_review_accepted)
    return {
        "admitted": admitted,
        "publicExposureAllowed": public_ok,
        "reasonCodes": [] if admitted else ["SECURITY_REVIEW_REQUIRED"],
    }
