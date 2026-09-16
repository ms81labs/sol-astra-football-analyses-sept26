"""9.2 object-level access. Do not trust a client-supplied tenant ID."""

from __future__ import annotations

from typing import Any, Callable

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
