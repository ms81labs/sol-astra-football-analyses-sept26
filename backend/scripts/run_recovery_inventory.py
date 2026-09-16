from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from typing import Any, Mapping, Sequence


ALLOWED_CLASSIFICATIONS = (
    "product_source",
    "reusable_workflow",
    "one_shot_batch_entrypoint",
    "essential_release_truth",
    "regenerable_truth",
    "large_local_artifact",
    "editor_or_cache_material",
    "manual_review",
    "tracked_deletion",
)

_KNOWN_STATUS_CODES = {
    " M",
    " T",
    " D",
    "M ",
    "MM",
    "MT",
    "MD",
    "A ",
    "AM",
    "AT",
    "AD",
    "T ",
    "TM",
    "TT",
    "TD",
    "D ",
    "DM",
    "DT",
    "DD",
    "AA",
    "AU",
    "UA",
    "UD",
    "DU",
    "UU",
    "??",
}
_UNMERGED_STATUS_CODES = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
_LARGE_ARTIFACT_SUFFIXES = {
    ".7z",
    ".avi",
    ".bin",
    ".ckpt",
    ".gz",
    ".mov",
    ".mp4",
    ".npy",
    ".npz",
    ".onnx",
    ".pt",
    ".pth",
    ".tar",
    ".tgz",
    ".zip",
}
_EDITOR_OR_CACHE_PARTS = {
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".vscode",
    "__pycache__",
    "node_modules",
}
_DEFAULTS = {
    "product_source": ("preserve_commit", "product-source"),
    "reusable_workflow": ("preserve_commit", "workflow"),
    "one_shot_batch_entrypoint": ("preserve_or_archive", "one-shot-batches"),
    "essential_release_truth": ("preserve_commit", "release-truth"),
    "regenerable_truth": ("retain_external", "generated-truth"),
    "large_local_artifact": ("retain_external", "external-artifacts"),
    "editor_or_cache_material": ("review_before_ignore", "local-material"),
    "manual_review": ("manual_review", "manual-review"),
    "tracked_deletion": ("manual_review", "tracked-deletions"),
}
_ALLOWED_DISPOSITIONS = {
    "product_source": frozenset({"preserve_commit"}),
    "reusable_workflow": frozenset({"preserve_commit"}),
    "one_shot_batch_entrypoint": frozenset({"preserve_or_archive"}),
    "essential_release_truth": frozenset({"preserve_commit"}),
    "regenerable_truth": frozenset({"retain_external"}),
    "large_local_artifact": frozenset({"retain_external"}),
    "editor_or_cache_material": frozenset({"review_before_ignore"}),
    "manual_review": frozenset({"manual_review"}),
    "tracked_deletion": frozenset({"manual_review", "accept_deletion"}),
}
_PRESERVING_CLASSIFICATIONS = {
    "product_source",
    "reusable_workflow",
    "essential_release_truth",
}
_BLOB_ID = re.compile(r"^[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?$")
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


class InventoryError(ValueError):
    """Raised when frozen inventory evidence cannot be reconciled safely."""


def _safe_path(value: str, *, allow_directory_marker: bool = False) -> str:
    if not value or "\0" in value or "\\" in value:
        raise InventoryError(f"unsafe path: {value!r}")
    directory_marker = value.endswith("/")
    normalized_source = value[:-1] if directory_marker else value
    candidate = PurePosixPath(normalized_source)
    if (
        not normalized_source
        or candidate.is_absolute()
        or any(part in {"", ".", ".."} for part in candidate.parts)
        or str(candidate) != normalized_source
        or (directory_marker and not allow_directory_marker)
    ):
        raise InventoryError(f"unsafe path: {value!r}")
    return value


def _decode_nul(data: bytes, label: str, *, allow_directory_marker: bool = False) -> list[str]:
    if not isinstance(data, bytes):
        raise InventoryError(f"{label} must be bytes")
    if data and not data.endswith(b"\0"):
        raise InventoryError(f"{label} must be NUL terminated")
    raw_values = data[:-1].split(b"\0") if data else []
    try:
        values = [raw.decode("utf-8") for raw in raw_values]
    except UnicodeDecodeError as exc:
        raise InventoryError(f"{label} contains a non-UTF-8 path") from exc
    for value in values:
        _safe_path(value, allow_directory_marker=allow_directory_marker)
    if len(values) != len(set(values)):
        raise InventoryError(f"{label} contains duplicate paths")
    return values


def _parse_status(data: bytes) -> list[tuple[str, str]]:
    if data and not data.endswith(b"\0"):
        raise InventoryError("status input must be NUL terminated")
    raw_rows = data[:-1].split(b"\0") if data else []
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw in raw_rows:
        try:
            row = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InventoryError("status input contains a non-UTF-8 path") from exc
        if len(row) < 4 or row[2] != " ":
            raise InventoryError(f"invalid porcelain status row: {row!r}")
        code, path = row[:2], row[3:]
        if code not in _KNOWN_STATUS_CODES:
            raise InventoryError(f"unknown status code: {code!r}")
        if code in _UNMERGED_STATUS_CODES:
            raise InventoryError(f"unmerged status is not safe to inventory: {code!r}")
        _safe_path(path, allow_directory_marker=True)
        if path in seen:
            raise InventoryError(f"status input contains duplicate path: {path}")
        seen.add(path)
        rows.append((code, path))
    return rows


def _reconcile_status(
    status_rows: Sequence[tuple[str, str]],
    canonical_paths: Sequence[str],
    tracked_paths: Sequence[str],
    untracked_paths: Sequence[str],
) -> tuple[dict[str, str], list[dict[str, str]]]:
    canonical = set(canonical_paths)
    tracked = set(tracked_paths)
    untracked = set(untracked_paths)
    if tracked & untracked or tracked | untracked != canonical:
        raise InventoryError("tracked/untracked path lists do not exactly partition the canonical path list")
    if len(status_rows) != len(canonical_paths):
        raise InventoryError("status/path-list count mismatch")

    reconciled: dict[str, str] = {}
    replacements: list[dict[str, str]] = []
    unmatched = set(canonical)
    for code, status_path in status_rows:
        if status_path in unmatched:
            canonical_path = status_path
        elif code == "??" and status_path.endswith("/"):
            contained = sorted(path for path in unmatched & untracked if path.startswith(status_path))
            if len(contained) != 1:
                raise InventoryError(
                    f"collapsed directory {status_path!r} does not prove a one-for-one contained path"
                )
            canonical_path = contained[0]
            replacements.append({"statusPath": status_path, "canonicalPath": canonical_path})
        else:
            raise InventoryError(f"status/path-list mismatch at {status_path!r}")
        if (code == "??") != (canonical_path in untracked):
            raise InventoryError(f"status tracked/untracked mismatch at {canonical_path!r}")
        reconciled[canonical_path] = code
        unmatched.remove(canonical_path)
    if unmatched or set(reconciled) != canonical:
        raise InventoryError("status/path-list mismatch")
    return reconciled, sorted(replacements, key=lambda row: (row["statusPath"], row["canonicalPath"]))


def _classify(path: str, status: str) -> tuple[str, str]:
    if "D" in status:
        return "tracked_deletion", "porcelain status records a tracked deletion"
    candidate = PurePosixPath(path)
    parts = candidate.parts
    suffix = candidate.suffix.lower()
    if any(part in _EDITOR_OR_CACHE_PARTS for part in parts) or suffix in {".pyc", ".swp"}:
        return "editor_or_cache_material", "path is editor or cache material"
    if suffix in _LARGE_ARTIFACT_SUFFIXES:
        return "large_local_artifact", "path suffix identifies a local binary or archive artifact"
    if path.startswith("backend/tests/") or path.startswith("frontend/tests/"):
        return "product_source", "path is product test source"
    if path.startswith(".github/workflows/") or path.startswith("docs/superpowers/plans/"):
        return "reusable_workflow", "path defines a reusable workflow or implementation plan"
    if path.startswith("backend/scripts/") and candidate.name.endswith("_common.py"):
        return "reusable_workflow", "script is a shared workflow module"
    if path.startswith("backend/scripts/run_") and suffix == ".py":
        return "one_shot_batch_entrypoint", "script is a run-prefixed batch entrypoint"
    if (
        path.startswith("backend/release/")
        or path.startswith("docs/recovery/")
        or path.startswith("docs/runbooks/")
        or path.startswith("docs/status/")
        or path in {"README.md", "SESSION-HANDOFF.md"}
        or path.startswith("memorybank/")
    ):
        return "essential_release_truth", "path records current release or recovery truth"
    if path.startswith("backend/storage/") and suffix in {".json", ".md", ".html", ".csv"}:
        return "regenerable_truth", "path is generated storage truth"
    if (
        path.startswith("backend/app/")
        or path.startswith("backend/daytona_worker/")
        or path.startswith("frontend/src/")
    ) and suffix in {".py", ".js", ".jsx", ".ts", ".tsx", ".css", ".html"}:
        return "product_source", "path is product implementation source"
    return "manual_review", "no unambiguous classification rule matched"


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise InventoryError(f"{label} must be a JSON object")
    return value


def _complete_deletion_evidence(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    decision = value.get("decision")
    blob_id = value.get("lastReachableBlobId")
    reason = value.get("reason")
    if decision not in {"replacement", "retirement"}:
        return False
    if not isinstance(blob_id, str) or not _BLOB_ID.fullmatch(blob_id):
        return False
    if not isinstance(reason, str) or not reason.strip():
        return False
    return decision != "replacement" or (
        isinstance(value.get("replacementPath"), str) and bool(value["replacementPath"].strip())
    )


def _normalize_disposition(value: object, classification: str, path: str) -> str:
    if not isinstance(value, str):
        raise InventoryError(f"invalid disposition for {path}")
    normalized = value.strip().lower()
    if normalized not in _ALLOWED_DISPOSITIONS[classification]:
        raise InventoryError(
            f"invalid or disposable disposition for {classification} path {path}: {value!r}"
        )
    return normalized


def _artifact_record(path: str, value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise InventoryError(f"artifact retention record missing for {path}")
    required_strings = ("identifier", "sha256", "origin", "retentionClass")
    if any(not isinstance(value.get(key), str) or not value[key].strip() for key in required_strings):
        raise InventoryError(f"artifact retention record is incomplete for {path}")
    if not _SHA256.fullmatch(value["sha256"]):
        raise InventoryError(f"artifact retention record has invalid sha256 for {path}")
    size = value.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise InventoryError(f"artifact retention record has invalid size for {path}")
    return {
        "path": path,
        "identifier": value["identifier"],
        "sha256": value["sha256"].lower(),
        "size": size,
        "origin": value["origin"],
        "retentionClass": value["retentionClass"],
        "disposition": "retain_external",
    }


def _derived_references(paths: set[str]) -> list[dict[str, str]]:
    relationships: list[dict[str, str]] = []
    for path in sorted(paths):
        if not path.startswith("backend/tests/test_") or not path.endswith(".py"):
            continue
        stem = PurePosixPath(path).name.removeprefix("test_")
        candidates = (f"backend/scripts/{stem}", f"backend/app/{stem}")
        for target in candidates:
            if target in paths:
                relationships.append(
                    {
                        "source": path,
                        "target": target,
                        "relationship": "tests",
                        "evidence": "matching dirty test and source path names",
                    }
                )
                break
    return relationships


def _references(
    paths: set[str], explicit: Sequence[Mapping[str, Any]] | None
) -> list[dict[str, str]]:
    relationships = _derived_references(paths)
    if explicit is not None:
        if not isinstance(explicit, Sequence) or isinstance(explicit, (str, bytes)):
            raise InventoryError("reference relationships must be a JSON array")
        for value in explicit:
            if not isinstance(value, Mapping):
                raise InventoryError("reference relationship must be an object")
            source, target = value.get("source"), value.get("target")
            relationship, evidence = value.get("relationship"), value.get("evidence")
            if source not in paths or target not in paths:
                raise InventoryError("reference relationship names a path outside the frozen inventory")
            if source == target:
                raise InventoryError("reference relationship cannot refer to itself")
            if not isinstance(relationship, str) or not relationship.strip():
                raise InventoryError("reference relationship is missing its type")
            if not isinstance(evidence, str) or not evidence.strip():
                raise InventoryError("reference relationship is missing evidence")
            relationships.append(
                {
                    "source": source,
                    "target": target,
                    "relationship": relationship,
                    "evidence": evidence,
                }
            )
    unique = {
        (row["source"], row["target"], row["relationship"], row["evidence"]): row
        for row in relationships
    }
    return [unique[key] for key in sorted(unique)]


def _render_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Recovery inventory",
        "",
        f"Total paths: {payload['totalPathCount']}",
        "",
        "## Inventory",
        "",
        "| Path | Original status | Classification | Disposition | Commit group |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['path']}` | `{row['originalStatus']}` | `{row['classification']}` "
            f"| `{row['disposition']}` | `{row['commitGroup']}` |"
        )
    lines.extend(["", "## Reference relationships", ""])
    if payload["referenceRelationships"]:
        for row in payload["referenceRelationships"]:
            lines.append(
                f"- `{row['source']}` {row['relationship']} `{row['target']}` "
                f"({row['evidence']})"
            )
    else:
        lines.append("- None discoverable from the explicit frozen evidence.")
    lines.extend(["", "## Artifact retention", ""])
    if payload["artifactRetentionRecords"]:
        for row in payload["artifactRetentionRecords"]:
            lines.append(
                f"- `{row['path']}`: `{row['identifier']}`, {row['size']} bytes, "
                f"SHA-256 `{row['sha256']}`, retention `{row['retentionClass']}`"
            )
    else:
        lines.append("- No large local artifacts occur in this inventory.")
    lines.extend(["", "## Tracked deletions", ""])
    for row in payload["deletionEvidence"]:
        lines.append(f"- `{row['path']}`: `{row['disposition']}`")
    if not payload["deletionEvidence"]:
        lines.append("- None.")
    return "\n".join(lines) + "\n"


def _nul_digest(values: Sequence[str]) -> str:
    data = b"".join(value.encode("utf-8") + b"\0" for value in sorted(values))
    return hashlib.sha256(data).hexdigest()


def build_inventory(
    *,
    status_data: bytes,
    path_list_data: bytes,
    tracked_path_list_data: bytes,
    untracked_path_list_data: bytes,
    decisions: Mapping[str, Mapping[str, Any]] | None = None,
    deletion_evidence: Mapping[str, Mapping[str, Any]] | None = None,
    reference_relationships: Sequence[Mapping[str, Any]] | None = None,
    artifact_records: Mapping[str, Mapping[str, Any]] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic inventory using only explicit frozen input bytes."""
    status_rows = _parse_status(status_data)
    canonical_paths = _decode_nul(path_list_data, "canonical path list")
    tracked_paths = _decode_nul(tracked_path_list_data, "tracked path list")
    untracked_paths = _decode_nul(untracked_path_list_data, "untracked path list")
    status_by_path, reconciliations = _reconcile_status(
        status_rows, canonical_paths, tracked_paths, untracked_paths
    )
    decision_map = _mapping(decisions, "decisions")
    deletion_map = _mapping(deletion_evidence, "deletion evidence")
    artifact_map = _mapping(artifact_records, "artifact records")
    canonical_set = set(canonical_paths)
    for label, values in (
        ("decision", decision_map),
        ("deletion evidence", deletion_map),
        ("artifact record", artifact_map),
    ):
        unknown = set(values) - canonical_set
        if unknown:
            raise InventoryError(f"{label} names paths outside the frozen inventory: {sorted(unknown)!r}")

    relationships = _references(canonical_set, reference_relationships)
    related: dict[str, set[str]] = {path: set() for path in canonical_paths}
    for relationship in relationships:
        related[relationship["source"]].add(relationship["target"])
        related[relationship["target"]].add(relationship["source"])

    rows: list[dict[str, Any]] = []
    deletion_rows: list[dict[str, Any]] = []
    retention_rows: list[dict[str, Any]] = []
    consumed_deletion_evidence: set[str] = set()
    consumed_artifact_records: set[str] = set()
    for path in sorted(canonical_paths):
        status = status_by_path[path]
        inferred_classification, classification_reason = _classify(path, status)
        decision = decision_map.get(path, {})
        if not isinstance(decision, Mapping):
            raise InventoryError(f"decision for {path} must be an object")
        requested_classification = decision.get("classification", inferred_classification)
        if requested_classification not in ALLOWED_CLASSIFICATIONS:
            raise InventoryError(f"invalid classification for {path}: {requested_classification!r}")
        is_deleted = "D" in status
        if is_deleted != (requested_classification == "tracked_deletion"):
            raise InventoryError(
                f"tracked_deletion classification must exactly match deleted status for {path}"
            )
        classification_overridden = requested_classification != inferred_classification
        override_reason: str | None = None
        if classification_overridden:
            raw_override_reason = decision.get("overrideEvidence")
            if not isinstance(raw_override_reason, str) or not raw_override_reason.strip():
                raise InventoryError(f"classification override evidence is required for {path}")
            override_reason = raw_override_reason.strip()
            if (
                inferred_classification in _PRESERVING_CLASSIFICATIONS
                and requested_classification not in _PRESERVING_CLASSIFICATIONS | {"manual_review"}
            ):
                raise InventoryError(
                    f"unsafe classification override from {inferred_classification} "
                    f"to {requested_classification} for {path}"
                )
        classification = requested_classification
        disposition, commit_group = _DEFAULTS[classification]
        evidence: list[Any] = [
            {
                "kind": "inferred_classification_rule",
                "classification": inferred_classification,
                "detail": classification_reason,
            }
        ]
        if classification_overridden:
            evidence.append(
                {
                    "kind": "classification_override",
                    "from": inferred_classification,
                    "to": classification,
                    "reason": override_reason,
                }
            )
        supplied_evidence = decision.get("evidence", [])
        if not isinstance(supplied_evidence, list):
            raise InventoryError(f"decision evidence for {path} must be an array")
        evidence.extend(supplied_evidence)
        if "disposition" in decision:
            disposition = _normalize_disposition(decision["disposition"], classification, path)
        if "commitGroup" in decision:
            if not isinstance(decision["commitGroup"], str) or not re.fullmatch(
                r"[a-z0-9]+(?:-[a-z0-9]+)*", decision["commitGroup"]
            ):
                raise InventoryError(f"invalid commit group for {path}")
            commit_group = decision["commitGroup"]
        disposition = _normalize_disposition(disposition, classification, path)

        deletion_value = deletion_map.get(path)
        if classification == "tracked_deletion":
            if deletion_value is not None:
                consumed_deletion_evidence.add(path)
            if isinstance(deletion_value, Mapping) and isinstance(
                deletion_value.get("replacementPath"), str
            ):
                _safe_path(deletion_value["replacementPath"])
            accepted = _complete_deletion_evidence(deletion_value)
            disposition = "accept_deletion" if accepted else "manual_review"
            if deletion_value is not None:
                evidence.append({"kind": "deletion_review", "detail": dict(deletion_value)})
            deletion_row = {
                "path": path,
                "originalStatus": status,
                "disposition": disposition,
                "decision": deletion_value.get("decision") if isinstance(deletion_value, Mapping) else None,
                "lastReachableBlobId": (
                    deletion_value.get("lastReachableBlobId")
                    if isinstance(deletion_value, Mapping)
                    else None
                ),
                "reason": deletion_value.get("reason") if isinstance(deletion_value, Mapping) else None,
            }
            if isinstance(deletion_value, Mapping) and deletion_value.get("replacementPath") is not None:
                deletion_row["replacementPath"] = deletion_value["replacementPath"]
            deletion_rows.append(deletion_row)

        if classification == "large_local_artifact":
            retention_rows.append(_artifact_record(path, artifact_map.get(path)))
            consumed_artifact_records.add(path)

        rows.append(
            {
                "path": path,
                "originalStatus": status,
                "inferredClassification": inferred_classification,
                "classification": classification,
                "classificationOverridden": classification_overridden,
                "classificationOverrideReason": override_reason,
                "disposition": disposition,
                "commitGroup": commit_group,
                "evidence": evidence,
                "references": sorted(related[path]),
            }
        )

    unconsumed_deletions = set(deletion_map) - consumed_deletion_evidence
    if unconsumed_deletions:
        raise InventoryError(
            f"deletion evidence is inapplicable or unconsumed: {sorted(unconsumed_deletions)!r}"
        )
    unconsumed_artifacts = set(artifact_map) - consumed_artifact_records
    if unconsumed_artifacts:
        raise InventoryError(
            f"artifact record is inapplicable or unconsumed: {sorted(unconsumed_artifacts)!r}"
        )

    payload: dict[str, Any] = {
        "schemaVersion": "recovery-inventory-v1",
        "totalPathCount": len(rows),
        "inputDigests": {
            "statusSha256": hashlib.sha256(status_data).hexdigest(),
            "pathListSha256": hashlib.sha256(path_list_data).hexdigest(),
            "trackedPathListSha256": hashlib.sha256(tracked_path_list_data).hexdigest(),
            "untrackedPathListSha256": hashlib.sha256(untracked_path_list_data).hexdigest(),
        },
        "normalizedDigests": {
            "statusSha256": _nul_digest(
                [f"{status_by_path[path]} {path}" for path in canonical_paths]
            ),
            "pathListSha256": _nul_digest(canonical_paths),
            "trackedPathListSha256": _nul_digest(tracked_paths),
            "untrackedPathListSha256": _nul_digest(untracked_paths),
        },
        "classificationCounts": {
            name: sum(row["classification"] == name for row in rows)
            for name in ALLOWED_CLASSIFICATIONS
        },
        "rows": rows,
        "reconciliations": reconciliations,
        "referenceRelationships": relationships,
        "artifactRetentionRecords": retention_rows,
        "deletionEvidence": deletion_rows,
    }
    if generated_at is not None:
        if not isinstance(generated_at, str) or not generated_at.strip():
            raise InventoryError("generated_at must be a non-empty explicit string")
        payload["generatedAt"] = generated_at
    payload["markdown"] = _render_markdown(payload)
    return payload


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _commit_group_filename(group: object) -> str:
    if not isinstance(group, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", group):
        raise InventoryError(f"invalid commit group: {group!r}")
    filename = f"{group}.paths.nul"
    if len(filename.encode("utf-8")) > 255:
        raise InventoryError(f"commit group filename is too long: {group!r}")
    return filename


def _render_output_files(payload: Mapping[str, Any]) -> dict[str, bytes]:
    json_payload = dict(payload)
    markdown = json_payload.pop("markdown", None)
    if not isinstance(markdown, str):
        raise InventoryError("rendered Markdown payload must be a string")
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise InventoryError("inventory rows must be an array")
    groups: dict[str, list[str]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise InventoryError("inventory row must be an object")
        path, group = row.get("path"), row.get("commitGroup")
        if not isinstance(path, str):
            raise InventoryError("inventory row path must be a string")
        _safe_path(path)
        filename = _commit_group_filename(group)
        groups.setdefault(filename, []).append(path)
    rendered = {
        "inventory.json": _json_bytes(json_payload),
        "inventory.md": markdown.encode("utf-8"),
    }
    for filename in sorted(groups):
        rendered[f"commit-groups/{filename}"] = b"".join(
            path.encode("utf-8") + b"\0" for path in sorted(groups[filename])
        )
    return rendered


def write_inventory_output(payload: Mapping[str, Any], output_dir: Path) -> None:
    output_dir = Path(output_dir)
    rendered = _render_output_files(payload)
    if output_dir.is_symlink() or (
        output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir()))
    ):
        raise InventoryError(f"output directory must be absent or empty: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.inventory-tmp-", dir=output_dir.parent)
    )
    backup_dir: Path | None = None
    try:
        for relative_path, data in rendered.items():
            destination = staging_dir / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        if output_dir.exists():
            backup_dir = Path(
                tempfile.mkdtemp(
                    prefix=f".{output_dir.name}.empty-backup-", dir=output_dir.parent
                )
            )
            backup_dir.rmdir()
            os.replace(output_dir, backup_dir)
        try:
            os.replace(staging_dir, output_dir)
        except BaseException:
            if backup_dir is not None and backup_dir.exists() and not output_dir.exists():
                os.rename(backup_dir, output_dir)
                backup_dir = None
            raise
        if backup_dir is not None:
            backup_dir.rmdir()
            backup_dir = None
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)


def _validate_output_location(output_dir: Path, input_paths: Sequence[Path]) -> None:
    output = output_dir.resolve(strict=False)
    input_parents = {path.resolve(strict=True).parent for path in input_paths}
    for parent in input_parents:
        if output == parent or parent in output.parents:
            raise InventoryError(f"output directory cannot be inside an input archive: {parent}")


def _read_json(path: Path | None, default: object) -> object:
    if path is None:
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InventoryError(f"cannot read JSON input {path}: {exc}") from exc


def run_recovery_inventory(
    *,
    status_input: Path,
    path_list_input: Path,
    tracked_path_list_input: Path,
    untracked_path_list_input: Path,
    output_dir: Path,
    decisions_input: Path | None = None,
    deletion_evidence_input: Path | None = None,
    reference_input: Path | None = None,
    artifact_input: Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    mandatory_inputs = [
        Path(status_input),
        Path(path_list_input),
        Path(tracked_path_list_input),
        Path(untracked_path_list_input),
    ]
    optional_inputs = [
        Path(path)
        for path in (decisions_input, deletion_evidence_input, reference_input, artifact_input)
        if path is not None
    ]
    for path in mandatory_inputs + optional_inputs:
        if not path.is_file():
            raise InventoryError(f"explicit input is not a file: {path}")
    _validate_output_location(Path(output_dir), mandatory_inputs + optional_inputs)
    payload = build_inventory(
        status_data=mandatory_inputs[0].read_bytes(),
        path_list_data=mandatory_inputs[1].read_bytes(),
        tracked_path_list_data=mandatory_inputs[2].read_bytes(),
        untracked_path_list_data=mandatory_inputs[3].read_bytes(),
        decisions=_read_json(Path(decisions_input) if decisions_input else None, {}),
        deletion_evidence=_read_json(
            Path(deletion_evidence_input) if deletion_evidence_input else None, {}
        ),
        reference_relationships=_read_json(Path(reference_input) if reference_input else None, []),
        artifact_records=_read_json(Path(artifact_input) if artifact_input else None, {}),
        generated_at=generated_at,
    )
    write_inventory_output(payload, Path(output_dir))
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a deterministic, read-only inventory from an explicit frozen Git status."
    )
    parser.add_argument("--status-input", type=Path, required=True)
    parser.add_argument("--path-list-input", type=Path, required=True)
    parser.add_argument("--tracked-path-list-input", type=Path, required=True)
    parser.add_argument("--untracked-path-list-input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--decisions-input", type=Path)
    parser.add_argument("--deletion-evidence-input", type=Path)
    parser.add_argument("--reference-input", type=Path)
    parser.add_argument("--artifact-input", type=Path)
    parser.add_argument("--generated-at")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    run_recovery_inventory(
        status_input=args.status_input,
        path_list_input=args.path_list_input,
        tracked_path_list_input=args.tracked_path_list_input,
        untracked_path_list_input=args.untracked_path_list_input,
        output_dir=args.output_dir,
        decisions_input=args.decisions_input,
        deletion_evidence_input=args.deletion_evidence_input,
        reference_input=args.reference_input,
        artifact_input=args.artifact_input,
        generated_at=args.generated_at,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
