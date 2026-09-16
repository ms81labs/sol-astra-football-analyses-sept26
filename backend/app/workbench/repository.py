"""6.3 repository adapter. Extends persistence; does not replace storage.py."""

from __future__ import annotations


class RepositoryAdapter:
    backend_name = "sqlite_plus_artifacts"
    replaces_storage_module = False


def http_may_run_gpu() -> bool:
    return False


def vector_broker_required() -> bool:
    return False
