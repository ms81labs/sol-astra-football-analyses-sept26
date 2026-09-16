"""GA-12 content-addressed artifacts, restore, and worker-output admission."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

ALLOWED_WORKER_KINDS = frozenset({"observations", "metrics", "receipts"})
MAX_WORKER_BYTES = 1_073_741_824


class ArtifactStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, payload: bytes, *, namespace: str) -> str:
        digest = hashlib.sha256(payload).hexdigest()
        path = self.root / namespace / digest
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(payload)
        return digest

    def get(self, digest: str, *, namespace: str) -> bytes:
        path = self.root / namespace / digest
        if not path.exists():
            raise KeyError(digest)
        return path.read_bytes()

    def restore_to(self, destination: Path) -> Path:
        dest = Path(destination)
        dest.mkdir(parents=True, exist_ok=True)
        production = self.root / "production"
        if production.exists():
            for item in production.iterdir():
                if item.is_file():
                    (dest / item.name).write_bytes(item.read_bytes())
        return dest


def object_storage_adapter(*, hosted_approved: bool) -> dict[str, Any]:
    return {
        "enabled": hosted_approved,
        "mandatoryDuckDb": False,
        "role": "hosted_object_storage" if hosted_approved else "local_content_addressed",
    }


def cross_tenant_cache_reuse(
    *,
    source_tenant: str,
    requester_tenant: str,
    explicit_privacy_design: bool,
) -> dict[str, Any]:
    same = source_tenant == requester_tenant
    allowed = same or explicit_privacy_design
    return {
        "allowed": allowed,
        "reasonCodes": [] if allowed else ["CROSS_TENANT_CACHE_BLOCKED"],
        "sourceTenant": source_tenant,
        "requesterTenant": requester_tenant,
    }


def columnar_observation_store() -> dict[str, Any]:
    return {
        "enabled": False,
        "mandatoryDuckDb": False,
        "justifiedByMeasurement": False,
    }


def import_worker_output(item: dict[str, Any], *, quality_accepted: bool = False) -> dict[str, Any]:
    reasons: list[str] = []
    path = str(item.get("path") or "")
    parts = Path(path).parts
    if ".." in parts or path.startswith("/") or "\\" in path:
        reasons.append("PATH_TRAVERSAL")
    kind = str(item.get("kind") or "")
    if kind not in ALLOWED_WORKER_KINDS:
        reasons.append("UNRECOGNISED_WORKER_OUTPUT")
    if int(item.get("bytes") or 0) > MAX_WORKER_BYTES:
        reasons.append("OVERSIZED_ARCHIVE")
    imported = not reasons
    return {
        "imported": imported,
        "productQualityPass": bool(imported and quality_accepted),
        "jobSucceeded": bool(item.get("jobSucceeded")),
        "reasonCodes": reasons,
    }


def write_alongside(
    store: ArtifactStore,
    *,
    previous_digest: str,
    payload: bytes,
    namespace: str,
) -> dict[str, Any]:
    """Write a new version beside the retained previous artifact. Never mutate history."""

    digest = store.put(payload, namespace=namespace)
    return {
        "digest": digest,
        "previousDigest": previous_digest,
        "mutatedHistorical": False,
        "namespace": namespace,
    }
