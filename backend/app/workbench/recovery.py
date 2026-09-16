"""9.2 failure and recovery operations. A cancelled status is not billing proof."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .artifacts import ArtifactStore


def corrupted_import(*, expected_sha256: str, actual_sha256: str) -> dict[str, Any]:
    return {
        "accepted": expected_sha256 == actual_sha256,
        "reasonCodes": [] if expected_sha256 == actual_sha256 else ["CORRUPTED_ARTIFACT"],
    }


def full_disk() -> dict[str, Any]:
    return {"status": "failed", "error": "disk_exhaustion", "acceptedPartial": False}


def interrupted_upload(path: Path) -> dict[str, Any]:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"partial")
    quarantine = target.with_suffix(target.suffix + ".quarantine")
    target.replace(quarantine)
    return {"accepted": False, "quarantined": True, "path": str(quarantine)}


def restore_exercise(source: Path, destination: Path) -> dict[str, Any]:
    src = Path(source)
    dest = Path(destination)
    src.mkdir(parents=True, exist_ok=True)
    store = ArtifactStore(src)
    digest = store.put(b"restore-fixture", namespace="production")
    restored = store.restore_to(dest)
    return {
        "tested": (restored / digest).exists(),
        "source": str(src.resolve()),
        "destination": str(dest.resolve()),
        "digest": digest,
    }


def support_bundle(*, consented: bool, ttl_seconds: float, now: float) -> dict[str, Any]:
    if not consented:
        return {"released": False, "reasonCodes": ["CONSENT_REQUIRED"]}
    expires_at = now + ttl_seconds

    def expired(at: float) -> bool:
        return at >= expires_at

    expired_fn: Callable[[float], bool] = expired
    return {"released": True, "scoped": True, "expired": expired_fn, "expiresAt": expires_at}


def unresolved_incidents() -> dict[str, Any]:
    return {
        "items": [],
        "operatorVisible": True,
        "enterpriseUptimePromised": False,
        "syntheticTestsAreNotDeploymentAssessment": True,
    }


def recovery_objectives(*, data_volume_measured: bool, disruption_measured: bool) -> dict[str, Any]:
    defined = data_volume_measured and disruption_measured
    return {
        "defined": defined,
        "enterpriseUptimePromised": False,
        "reasonCodes": [] if defined else ["RECOVERY_OBJECTIVES_UNMEASURED"],
    }
