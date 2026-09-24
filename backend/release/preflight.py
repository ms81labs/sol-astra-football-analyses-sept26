"""Provider-neutral fail-closed validation for reproducible releases."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import tempfile
from typing import BinaryIO, Iterator, Mapping, Sequence

from backend.app.release_manifest import (
    ManifestError,
    ReleaseManifest,
    load_json_mapping,
    resolve_artifact,
)
from backend.release.evidence import (
    REMOTE_GATE_NAME,
    MAX_EVIDENCE_AGE_SECONDS,
    REQUIRED_GATE_COMMANDS,
    SCHEMA_VERSION,
    SHA256_RE,
    SOURCE_COMMIT_RE,
    PreflightError,
    VerificationEvidence,
    VerificationGate,
    _PHASES,
    _exact_keys,
    _git_environment,
    _nonempty_string,
    _reject_hidden_index_entries,
    _timestamp,
    load_verification_evidence,
    validate_evidence_freshness as _validate_freshness,
    validate_evidence_phase as _validate_phase,
    validate_evidence_validity_window,
)


IMMUTABLE_TAG_RE = re.compile(r"^v7\.3-[0-9a-f]{40}-[0-9a-f]{12}$")
METADATA_ALLOWLIST = frozenset(
    {
        "backend/release/v7.3.json",
        "backend/release/verification/v7.3-pre-cloud.json",
        "backend/release/verification/v7.3.json",
        "docs/recovery/2026-08-19/current-tree-inventory.json",
        "docs/recovery/2026-08-24/daytona-gpu-smoke.md",
        "docs/recovery/2026-08-24/final-verification-report.md",
        "docs/status/current.md",
    }
)
def _git(repo_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=check,
            capture_output=True,
            text=True,
            env=_git_environment(),
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PreflightError(f"git {' '.join(args)} failed: {exc}") from exc


def _git_bytes(repo_root: Path, *args: str) -> bytes:
    try:
        return subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=True,
            capture_output=True,
            env=_git_environment(),
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PreflightError(f"git {' '.join(args)} failed: {exc}") from exc


def _reject_git_parent_overrides(root: Path) -> None:
    replacements = _git(root, "replace", "-l").stdout.splitlines()
    if replacements:
        raise PreflightError("git replace objects are forbidden: " + ", ".join(replacements))
    common_dir = Path(
        _git(root, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
    ).resolve()
    grafts_path = Path(
        _git(
            root,
            "rev-parse",
            "--path-format=absolute",
            "--git-path",
            "info/grafts",
        ).stdout.strip()
    ).resolve()
    if not grafts_path.is_relative_to(common_dir):
        raise PreflightError(f"git grafts path escapes common directory: {grafts_path}")
    if grafts_path.is_file() and grafts_path.stat().st_size > 0:
        raise PreflightError(f"legacy grafts are forbidden: {grafts_path}")


@dataclass(frozen=True, slots=True)
class _RawCommit:
    tree: str
    parents: tuple[str, ...]


def _raw_commit(root: Path, commit_id: str) -> _RawCommit:
    if SOURCE_COMMIT_RE.fullmatch(commit_id) is None:
        raise PreflightError(f"invalid raw commit object ID: {commit_id}")
    content = _git_bytes(root, "cat-file", "-p", commit_id)
    header, separator, _message = content.partition(b"\n\n")
    if not separator:
        raise PreflightError(f"raw commit {commit_id} has no header terminator")
    trees: list[str] = []
    parents: list[str] = []
    for line in header.splitlines():
        if line.startswith(b"tree "):
            trees.append(line.removeprefix(b"tree ").decode("ascii", errors="strict"))
        elif line.startswith(b"parent "):
            parents.append(line.removeprefix(b"parent ").decode("ascii", errors="strict"))
    if len(trees) != 1 or SOURCE_COMMIT_RE.fullmatch(trees[0]) is None:
        raise PreflightError(f"raw commit {commit_id} must declare exactly one SHA-1 tree")
    if any(SOURCE_COMMIT_RE.fullmatch(parent) is None for parent in parents):
        raise PreflightError(f"raw commit {commit_id} declares an invalid parent")
    return _RawCommit(tree=trees[0], parents=tuple(parents))


def _raw_reachable_commits(
    root: Path,
    start: str,
    cache: dict[str, _RawCommit],
) -> set[str]:
    reachable: set[str] = set()
    pending = [start]
    while pending:
        commit_id = pending.pop()
        if commit_id in reachable:
            continue
        commit = cache.get(commit_id)
        if commit is None:
            commit = _raw_commit(root, commit_id)
            cache[commit_id] = commit
        reachable.add(commit_id)
        pending.extend(parent for parent in commit.parents if parent not in reachable)
    return reachable


def _changed_tree_paths(root: Path, parent_tree: str, commit_tree: str) -> tuple[str, ...]:
    output = _git(
        root,
        "diff-tree",
        "--no-commit-id",
        "--name-only",
        "-r",
        "-z",
        parent_tree,
        commit_tree,
    ).stdout
    return tuple(path for path in output.split("\0") if path)


def validate_git_source(
    repo_root: Path | str,
    source_commit: str,
    *,
    required_tracked_paths: Sequence[str] = (),
) -> None:
    root = Path(repo_root).resolve()
    if not root.is_dir():
        raise PreflightError(f"repository root is not a directory: {root}")
    _reject_git_parent_overrides(root)
    _reject_hidden_index_entries(_git(root, "ls-files", "-v", "-z").stdout)
    status = _git(root, "status", "--porcelain", "--untracked-files=all").stdout
    dirty = [
        line for line in status.splitlines()
        if line != "?? .verification/receipt.json"
    ]
    if dirty:
        paths = ", ".join(line[3:] for line in dirty)
        raise PreflightError(f"worktree is dirty: {paths}")
    head = _git(root, "rev-parse", "--verify", "HEAD^{commit}").stdout.strip()
    for path in required_tracked_paths:
        tracked = _git(root, "ls-files", "--error-unmatch", "--", path, check=False)
        if tracked.returncode != 0:
            raise PreflightError(f"release input is not tracked at HEAD: {path}")
    cache: dict[str, _RawCommit] = {}
    head_reachable = _raw_reachable_commits(root, head, cache)
    if source_commit not in head_reachable:
        raise PreflightError(f"sourceCommit {source_commit} is not an ancestor of HEAD {head}")
    source_reachable = _raw_reachable_commits(root, source_commit, cache)
    commits = sorted(head_reachable - source_reachable)
    violations: list[tuple[str, str]] = []
    for commit in commits:
        raw = cache[commit]
        parent_trees = (
            tuple(cache[parent].tree for parent in raw.parents)
            if raw.parents
            else ("4b825dc642cb6eb9a060e54bf8d69288fbee4904",)
        )
        for parent_tree in parent_trees:
            changed = _changed_tree_paths(root, parent_tree, raw.tree)
            violations.extend(
                (commit, path)
                for path in changed
                if path and path not in METADATA_ALLOWLIST
            )
    if violations:
        details = ", ".join(
            f"{commit[:12]}:{path}" for commit, path in sorted(set(violations))
        )
        raise PreflightError(f"commit history touches paths not permitted after sourceCommit: {details}")
    _reject_hidden_index_entries(_git(root, "ls-files", "-v", "-z").stdout)
    _reject_git_parent_overrides(root)


def validate_verification_binding(
    repo_root: Path | str,
    verification_commit: str,
    manifest_relative: str,
    manifest_sha256: str,
) -> None:
    root = Path(repo_root).resolve()
    if SOURCE_COMMIT_RE.fullmatch(verification_commit) is None:
        raise PreflightError("verificationCommit must be a lower-case 40-character SHA")
    _reject_git_parent_overrides(root)
    head = _git(root, "rev-parse", "--verify", "HEAD^{commit}").stdout.strip()
    if verification_commit not in _raw_reachable_commits(root, head, {}):
        raise PreflightError(
            f"verificationCommit {verification_commit} is not an ancestor of HEAD {head}"
        )
    try:
        manifest_bytes = _git_bytes(
            root, "show", f"{verification_commit}:{manifest_relative}"
        )
    except PreflightError as exc:
        raise PreflightError("manifest at verificationCommit cannot be read") from exc
    if hashlib.sha256(manifest_bytes).hexdigest() != manifest_sha256:
        raise PreflightError("manifest at verificationCommit does not match manifestSha256")
    _reject_git_parent_overrides(root)


def validate_image_tag(image_tag: str, manifest: ReleaseManifest, manifest_sha256: str) -> None:
    if IMMUTABLE_TAG_RE.fullmatch(image_tag) is None:
        raise PreflightError(
            "immutable image tag must match ^v7\\.3-[0-9a-f]{40}-[0-9a-f]{12}$"
        )
    expected = f"v7.3-{manifest.source_commit}-{manifest_sha256[:12]}"
    if image_tag != expected:
        raise PreflightError(
            f"image tag does not bind source and manifest identity: expected {expected}"
        )


def validate_image_labels(
    *,
    expected_source_commit: str,
    expected_manifest_sha256: str,
    source_label: str | None,
    manifest_label: str | None,
) -> None:
    if source_label is None or not source_label:
        raise PreflightError("source revision label is missing")
    if manifest_label is None or not manifest_label:
        raise PreflightError("manifest digest label is missing")
    if source_label != expected_source_commit:
        raise PreflightError(
            f"source revision label mismatch: expected {expected_source_commit}, got {source_label}"
        )
    if manifest_label != expected_manifest_sha256:
        raise PreflightError(
            f"manifest digest label mismatch: expected {expected_manifest_sha256}, got {manifest_label}"
        )


def _json_bytes_mapping(content: bytes, label: str) -> dict[str, object]:
    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise PreflightError(f"{label} contains duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(content.decode("utf-8"), object_pairs_hook=reject_duplicate_keys)
    except PreflightError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PreflightError(f"{label} is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise PreflightError(f"{label} must be a JSON object")
    return value


def _file_identity(path: Path, label: str) -> tuple[str, int]:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest(), path.stat().st_size
    except OSError as exc:
        raise PreflightError(f"cannot read {label} at {path}: {exc}") from exc


def _require_identity(
    path: Path,
    *,
    expected_sha256: str,
    expected_size: int | None,
    label: str,
) -> None:
    actual_sha256, actual_size = _file_identity(path, label)
    if expected_size is not None and actual_size != expected_size:
        raise PreflightError(
            f"{label} size mismatch: expected {expected_size}, got {actual_size}"
        )
    if actual_sha256 != expected_sha256:
        raise PreflightError(
            f"{label} digest mismatch: expected {expected_sha256}, got {actual_sha256}"
        )


@dataclass(frozen=True, slots=True)
class PreflightResult:
    source_commit: str
    manifest_sha256: str
    manifest_path: Path
    evidence_path: Path
    evidence_phase: str
    evidence_sha256: str
    artifacts: tuple[tuple[str, Path, str], ...]
    artifact_metadata: tuple[tuple[str, str, int], ...]

    def to_mapping(self) -> dict[str, object]:
        metadata = {artifact_id: (digest, size) for artifact_id, digest, size in self.artifact_metadata}
        return {
            "sourceCommit": self.source_commit,
            "manifestSha256": self.manifest_sha256,
            "manifestPath": str(self.manifest_path),
            "evidencePath": str(self.evidence_path),
            "evidencePhase": self.evidence_phase,
            "evidenceSha256": self.evidence_sha256,
            "artifacts": [
                {
                    "id": artifact_id,
                    "localPath": str(local_path),
                    "containerPath": container_path,
                    "sha256": metadata[artifact_id][0],
                    "sizeBytes": metadata[artifact_id][1],
                }
                for artifact_id, local_path, container_path in self.artifacts
            ],
        }


_RECEIPT_KEYS = frozenset(
    {
        "sourceCommit",
        "manifestSha256",
        "manifestPath",
        "evidencePath",
        "evidencePhase",
        "evidenceSha256",
        "artifacts",
    }
)
_RECEIPT_ARTIFACT_KEYS = frozenset(
    {"id", "localPath", "containerPath", "sha256", "sizeBytes"}
)


def _receipt_container_path(value: object) -> str:
    raw = _nonempty_string(value, "receipt artifact containerPath")
    if not raw.startswith(("/app/models/", "/app/release-inputs/")):
        raise PreflightError(
            "receipt artifact containerPath must be under /app/models/ or /app/release-inputs/"
        )
    parts = raw.removeprefix("/").split("/")
    if any(part in {"", ".", ".."} for part in parts) or PurePosixPath(raw).as_posix() != raw:
        raise PreflightError("receipt artifact containerPath must be normalized and traversal-free")
    return raw


@dataclass(frozen=True, slots=True)
class ReceiptArtifact:
    id: str
    local_path: Path
    container_path: str
    sha256: str
    size_bytes: int

    @classmethod
    def from_mapping(cls, value: object) -> "ReceiptArtifact":
        if not isinstance(value, Mapping):
            raise PreflightError("receipt artifact must be an object")
        _exact_keys(value, _RECEIPT_ARTIFACT_KEYS, "receipt artifact")
        artifact_id = _nonempty_string(value["id"], "receipt artifact id")
        local_path = Path(_nonempty_string(value["localPath"], "receipt artifact localPath"))
        if not local_path.is_absolute():
            raise PreflightError("receipt artifact localPath must be absolute")
        digest = _nonempty_string(value["sha256"], "receipt artifact sha256")
        if SHA256_RE.fullmatch(digest) is None:
            raise PreflightError("receipt artifact sha256 must be a lower-case SHA-256")
        size = value["sizeBytes"]
        if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
            raise PreflightError("receipt artifact sizeBytes must be a positive integer")
        return cls(
            id=artifact_id,
            local_path=local_path.resolve(),
            container_path=_receipt_container_path(value["containerPath"]),
            sha256=digest,
            size_bytes=size,
        )


@dataclass(frozen=True, slots=True)
class PreflightReceipt:
    source_commit: str
    manifest_sha256: str
    manifest_path: Path
    evidence_path: Path
    evidence_phase: str
    evidence_sha256: str
    artifacts: tuple[ReceiptArtifact, ...]

    @classmethod
    def from_mapping(cls, value: object) -> "PreflightReceipt":
        if not isinstance(value, Mapping):
            raise PreflightError("preflight receipt must be an object")
        _exact_keys(value, _RECEIPT_KEYS, "preflight receipt")
        source_commit = _nonempty_string(value["sourceCommit"], "receipt sourceCommit")
        if SOURCE_COMMIT_RE.fullmatch(source_commit) is None:
            raise PreflightError("receipt sourceCommit must be a lower-case 40-character SHA")
        manifest_sha256 = _nonempty_string(
            value["manifestSha256"], "receipt manifestSha256"
        )
        if SHA256_RE.fullmatch(manifest_sha256) is None:
            raise PreflightError("receipt manifestSha256 must be a lower-case SHA-256")
        evidence_sha256 = _nonempty_string(
            value["evidenceSha256"], "receipt evidenceSha256"
        )
        if SHA256_RE.fullmatch(evidence_sha256) is None:
            raise PreflightError("receipt evidenceSha256 must be a lower-case SHA-256")
        manifest_path = Path(_nonempty_string(value["manifestPath"], "receipt manifestPath"))
        evidence_path = Path(_nonempty_string(value["evidencePath"], "receipt evidencePath"))
        if not manifest_path.is_absolute() or not evidence_path.is_absolute():
            raise PreflightError("receipt manifestPath and evidencePath must be absolute")
        phase = _nonempty_string(value["evidencePhase"], "receipt evidencePhase")
        if phase not in _PHASES:
            raise PreflightError("receipt evidencePhase must be pre_cloud or final")
        raw_artifacts = value["artifacts"]
        if not isinstance(raw_artifacts, list) or not raw_artifacts:
            raise PreflightError("receipt artifacts must be a non-empty list")
        artifacts = tuple(ReceiptArtifact.from_mapping(item) for item in raw_artifacts)
        for attribute, label in (
            ("id", "id"),
            ("local_path", "localPath"),
            ("container_path", "containerPath"),
        ):
            values = [getattr(artifact, attribute) for artifact in artifacts]
            if len(values) != len(set(values)):
                raise PreflightError(f"duplicate receipt artifact {label}")
        return cls(
            source_commit=source_commit,
            manifest_sha256=manifest_sha256,
            manifest_path=manifest_path.resolve(),
            evidence_path=evidence_path.resolve(),
            evidence_phase=phase,
            evidence_sha256=evidence_sha256,
            artifacts=artifacts,
        )


@dataclass(frozen=True, slots=True)
class StagedContextResult:
    source_commit: str
    manifest_sha256: str
    evidence_sha256: str
    evidence_phase: str

    def to_mapping(self) -> dict[str, object]:
        return {
            "stagedContextValid": True,
            "sourceCommit": self.source_commit,
            "manifestSha256": self.manifest_sha256,
            "evidenceSha256": self.evidence_sha256,
            "evidencePhase": self.evidence_phase,
        }


def _context_file(context: Path, relative: str, label: str) -> Path:
    candidate = context.joinpath(*PurePosixPath(relative).parts).resolve(strict=False)
    if not candidate.is_relative_to(context):
        raise PreflightError(f"{label} escapes staged context")
    if not candidate.is_file():
        raise PreflightError(f"{label} is missing at {candidate}")
    return candidate


def validate_staged_context(
    *,
    context_root: Path | str,
    receipt: Mapping[str, object] | PreflightReceipt,
) -> StagedContextResult:
    parsed = receipt if isinstance(receipt, PreflightReceipt) else PreflightReceipt.from_mapping(receipt)
    context = Path(context_root).resolve(strict=True)
    if not context.is_dir():
        raise PreflightError(f"staged context root is not a directory: {context}")

    expected_manifest_suffix = Path("backend/release/v7.3.json")
    if tuple(parsed.manifest_path.parts[-3:]) != tuple(expected_manifest_suffix.parts):
        raise PreflightError("receipt manifestPath must end with backend/release/v7.3.json")
    repo_root = parsed.manifest_path.parents[2]
    expected_evidence_relative = (
        "backend/release/verification/v7.3-pre-cloud.json"
        if parsed.evidence_phase == "pre_cloud"
        else "backend/release/verification/v7.3.json"
    )
    expected_evidence_path = (repo_root / expected_evidence_relative).resolve()
    if parsed.evidence_path != expected_evidence_path:
        raise PreflightError(f"receipt evidencePath must be {expected_evidence_path}")

    _require_identity(
        parsed.manifest_path,
        expected_sha256=parsed.manifest_sha256,
        expected_size=None,
        label="live manifest",
    )
    _require_identity(
        parsed.evidence_path,
        expected_sha256=parsed.evidence_sha256,
        expected_size=None,
        label="live evidence",
    )
    staged_manifest_path = _context_file(
        context, "backend/release/v7.3.json", "staged manifest"
    )
    staged_evidence_path = _context_file(
        context, expected_evidence_relative, "staged evidence"
    )
    _require_identity(
        staged_manifest_path,
        expected_sha256=parsed.manifest_sha256,
        expected_size=None,
        label="staged manifest",
    )
    _require_identity(
        staged_evidence_path,
        expected_sha256=parsed.evidence_sha256,
        expected_size=None,
        label="staged evidence",
    )

    staged_manifest_bytes = staged_manifest_path.read_bytes()
    staged_evidence_bytes = staged_evidence_path.read_bytes()
    if hashlib.sha256(staged_manifest_bytes).hexdigest() != parsed.manifest_sha256:
        raise PreflightError("staged manifest changed while it was being validated")
    if hashlib.sha256(staged_evidence_bytes).hexdigest() != parsed.evidence_sha256:
        raise PreflightError("staged evidence changed while it was being validated")
    try:
        manifest = ReleaseManifest.from_mapping(
            _json_bytes_mapping(staged_manifest_bytes, "staged manifest")
        )
    except ManifestError as exc:
        raise PreflightError(f"staged manifest contract is invalid: {exc}") from exc
    evidence = VerificationEvidence.from_mapping(
        _json_bytes_mapping(staged_evidence_bytes, "staged evidence")
    )
    if manifest.source_commit != parsed.source_commit:
        raise PreflightError("staged manifest sourceCommit does not match receipt")
    if evidence.source_commit != parsed.source_commit:
        raise PreflightError("staged evidence sourceCommit does not match receipt")
    if evidence.manifest_sha256 != parsed.manifest_sha256:
        raise PreflightError("staged evidence manifestSha256 does not match receipt")
    if evidence.phase != parsed.evidence_phase:
        raise PreflightError("staged evidence phase does not match receipt")
    _validate_phase(
        evidence,
        "build-only" if parsed.evidence_phase == "pre_cloud" else "deploy",
    )

    manifest_artifacts = {artifact.id: artifact for artifact in manifest.artifacts}
    receipt_artifacts = {artifact.id: artifact for artifact in parsed.artifacts}
    if set(manifest_artifacts) != set(receipt_artifacts):
        raise PreflightError("staged manifest artifact IDs do not match receipt")
    for artifact_id, receipt_artifact in receipt_artifacts.items():
        manifest_artifact = manifest_artifacts[artifact_id]
        expected_live_path = (repo_root / manifest_artifact.local_relative_path).resolve()
        if receipt_artifact.local_path != expected_live_path:
            raise PreflightError(f"receipt artifact {artifact_id} localPath does not match manifest")
        if (
            receipt_artifact.sha256 != manifest_artifact.sha256
            or receipt_artifact.size_bytes != manifest_artifact.size_bytes
            or receipt_artifact.container_path != manifest_artifact.container_path
        ):
            raise PreflightError(f"receipt artifact {artifact_id} identity does not match manifest")
        _require_identity(
            receipt_artifact.local_path,
            expected_sha256=receipt_artifact.sha256,
            expected_size=receipt_artifact.size_bytes,
            label=f"live artifact {artifact_id}",
        )
        staged_relative = receipt_artifact.container_path.removeprefix("/app/")
        staged_artifact_path = _context_file(
            context, staged_relative, f"staged artifact {artifact_id}"
        )
        _require_identity(
            staged_artifact_path,
            expected_sha256=receipt_artifact.sha256,
            expected_size=receipt_artifact.size_bytes,
            label=f"staged artifact {artifact_id}",
        )
    return StagedContextResult(
        source_commit=parsed.source_commit,
        manifest_sha256=parsed.manifest_sha256,
        evidence_sha256=parsed.evidence_sha256,
        evidence_phase=parsed.evidence_phase,
    )


@dataclass(frozen=True, slots=True)
class _TarFingerprint:
    kind: str
    mode: int
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class _InjectionSource:
    size: int
    sha256: str
    content: bytes | None = None
    snapshot_path: Path | None = None

    @contextmanager
    def open(self) -> Iterator[BinaryIO]:
        if (self.content is None) == (self.snapshot_path is None):
            raise PreflightError("injection source must contain exactly one backing store")
        if self.content is not None:
            with io.BytesIO(self.content) as stream:
                yield stream
            return
        assert self.snapshot_path is not None
        try:
            with self.snapshot_path.open("rb") as stream:
                yield stream
        except OSError as exc:
            raise PreflightError(f"artifact snapshot cannot be opened: {exc}") from exc


@contextmanager
def _git_archive_stream(repo_root: Path, source_commit: str) -> Iterator[BinaryIO]:
    error_output = tempfile.TemporaryFile()
    try:
        process = subprocess.Popen(
            ["git", "-C", str(repo_root), "archive", "--format=tar", source_commit],
            stdout=subprocess.PIPE,
            stderr=error_output,
            env=_git_environment(),
        )
    except OSError as exc:
        error_output.close()
        raise PreflightError(f"git archive failed for {source_commit}: {exc}") from exc
    assert process.stdout is not None
    consumer_failed = False
    try:
        yield process.stdout
        # Tar readers stop at end markers before git writes record padding.
        # Drain the bounded commit archive so a successful read does not SIGPIPE git.
        while process.stdout.read(1024 * 1024):
            pass
    except BaseException:
        consumer_failed = True
        raise
    finally:
        process.stdout.close()
        return_code = process.wait()
        error_output.seek(0)
        stderr = error_output.read().decode("utf-8", errors="replace").strip()
        error_output.close()
        if return_code != 0 and not consumer_failed:
            raise PreflightError(
                f"git archive failed for {source_commit}: {stderr or f'exit {return_code}'}"
            )


def _safe_tar_name(name: str) -> str:
    if not name or "\\" in name or name.startswith(("/", "~")):
        raise PreflightError(f"unsafe tar member path: {name!r}")
    normalized = name.removesuffix("/")
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise PreflightError(f"unsafe tar member path: {name!r}")
    if PurePosixPath(normalized).as_posix() != normalized:
        raise PreflightError(f"non-normalized tar member path: {name!r}")
    return normalized


def _stream_digest(stream: BinaryIO) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        size += len(chunk)
        digest.update(chunk)
    return digest.hexdigest(), size


def _canonical_member_mode(member: tarfile.TarInfo) -> int:
    if member.isdir():
        return 0o755
    return 0o755 if member.mode & 0o111 else 0o644


def _raw_tar_layout_error(label: str, detail: str) -> PreflightError:
    return PreflightError(f"{label} has noncanonical raw tar layout: {detail}")


def _read_raw_tar_bytes(stream: BinaryIO, size: int, label: str, detail: str) -> bytes:
    content = stream.read(size)
    if len(content) != size:
        raise _raw_tar_layout_error(label, detail)
    return content


def _validate_raw_tar_layout(stream: BinaryIO, label: str) -> None:
    """Reject byte layouts other than the exact record-padded USTAR form we emit."""
    zero_block = b"\0" * tarfile.BLOCKSIZE
    offset = 0
    while True:
        header = _read_raw_tar_bytes(
            stream,
            tarfile.BLOCKSIZE,
            label,
            "missing complete end markers",
        )
        offset += tarfile.BLOCKSIZE
        if header == zero_block:
            second_marker = _read_raw_tar_bytes(
                stream,
                tarfile.BLOCKSIZE,
                label,
                "missing second end marker",
            )
            offset += tarfile.BLOCKSIZE
            if second_marker != zero_block:
                raise _raw_tar_layout_error(label, "second end marker is not zero-filled")

            record_padding_size = (-offset) % tarfile.RECORDSIZE
            record_padding = _read_raw_tar_bytes(
                stream,
                record_padding_size,
                label,
                "truncated record padding",
            )
            if record_padding != b"\0" * record_padding_size:
                raise _raw_tar_layout_error(label, "record padding is not zero-filled")
            if stream.read(1) != b"":
                raise _raw_tar_layout_error(label, "trailing data after final record")
            return

        try:
            member = tarfile.TarInfo.frombuf(header, "utf-8", "surrogateescape")
        except (tarfile.HeaderError, UnicodeError, ValueError) as exc:
            raise _raw_tar_layout_error(label, f"invalid member header: {exc}") from exc
        if member.type in {
            tarfile.XHDTYPE,
            tarfile.XGLTYPE,
            tarfile.SOLARIS_XHDTYPE,
            tarfile.GNUTYPE_LONGNAME,
            tarfile.GNUTYPE_LONGLINK,
        }:
            raise PreflightError(f"{label} contains noncanonical PAX or global header")
        if member.type not in {tarfile.REGTYPE, tarfile.DIRTYPE}:
            raise PreflightError(
                f"{label} contains forbidden symlink or special member "
                "(noncanonical tar header type)"
            )
        name = _safe_tar_name(member.name)
        canonical_header = _canonical_tar_info(
            name,
            mode=_canonical_member_mode(member),
            size=member.size,
            directory=member.isdir(),
        ).tobuf(
            format=tarfile.USTAR_FORMAT,
            encoding="utf-8",
            errors="surrogateescape",
        )
        if header != canonical_header:
            raise _raw_tar_layout_error(label, f"noncanonical member header: {name}")

        member_size = member.size
        remaining = member_size
        while remaining:
            chunk_size = min(remaining, 1024 * 1024)
            _read_raw_tar_bytes(
                stream,
                chunk_size,
                label,
                "truncated member data",
            )
            offset += chunk_size
            remaining -= chunk_size

        member_padding_size = (-member_size) % tarfile.BLOCKSIZE
        member_padding = _read_raw_tar_bytes(
            stream,
            member_padding_size,
            label,
            "truncated member padding",
        )
        offset += member_padding_size
        if member_padding != b"\0" * member_padding_size:
            raise _raw_tar_layout_error(label, "member padding is not zero-filled")


def _tar_fingerprints(
    stream: BinaryIO,
    label: str,
    *,
    require_canonical_headers: bool = False,
) -> dict[str, _TarFingerprint]:
    entries: dict[str, _TarFingerprint] = {}
    try:
        with tarfile.open(fileobj=stream, mode="r|*") as archive:
            for member in archive:
                name = _safe_tar_name(member.name)
                if require_canonical_headers:
                    if archive.pax_headers or member.pax_headers:
                        raise PreflightError(
                            f"{label} contains noncanonical PAX or global header: {name}"
                        )
                    if member.type not in {tarfile.REGTYPE, tarfile.DIRTYPE}:
                        raise PreflightError(
                            f"{label} contains forbidden symlink or special member "
                            f"(noncanonical tar header type): {name}"
                        )
                    if (
                        member.uid != 0
                        or member.gid != 0
                        or member.uname != ""
                        or member.gname != ""
                        or member.mtime != 0
                        or member.linkname != ""
                    ):
                        raise PreflightError(f"{label} contains noncanonical tar header: {name}")
                    if member.mode != _canonical_member_mode(member):
                        raise PreflightError(f"{label} contains noncanonical tar mode: {name}")
                if name in entries:
                    raise PreflightError(f"{label} contains duplicate member: {name}")
                if member.isdir():
                    entry = _TarFingerprint(
                        kind="directory",
                        mode=_canonical_member_mode(member),
                        size=0,
                        sha256="",
                    )
                elif member.isfile():
                    member_stream = archive.extractfile(member)
                    if member_stream is None:
                        raise PreflightError(f"{label} cannot read member: {name}")
                    digest, size = _stream_digest(member_stream)
                    if size != member.size:
                        raise PreflightError(f"{label} member size mismatch: {name}")
                    entry = _TarFingerprint(
                        kind="file",
                        mode=_canonical_member_mode(member),
                        size=size,
                        sha256=digest,
                    )
                else:
                    raise PreflightError(
                        f"{label} contains forbidden symlink or special member: {name}"
                    )
                entries[name] = entry
    except (tarfile.TarError, OSError) as exc:
        raise PreflightError(f"{label} is not a valid tar archive: {exc}") from exc
    return entries


def _read_receipt_metadata(
    *,
    repo_root: Path,
    receipt: PreflightReceipt,
    now: datetime | None = None,
) -> tuple[bytes, bytes, str, tuple[ReceiptArtifact, ...]]:
    if receipt.manifest_path != (repo_root / "backend/release/v7.3.json").resolve():
        raise PreflightError("receipt manifestPath does not belong to repository root")
    expected_evidence_relative = (
        "backend/release/verification/v7.3-pre-cloud.json"
        if receipt.evidence_phase == "pre_cloud"
        else "backend/release/verification/v7.3.json"
    )
    if receipt.evidence_path != (repo_root / expected_evidence_relative).resolve():
        raise PreflightError("receipt evidencePath does not belong to repository root")
    validate_git_source(
        repo_root,
        receipt.source_commit,
        required_tracked_paths=("backend/release/v7.3.json", expected_evidence_relative),
    )
    manifest_bytes = receipt.manifest_path.read_bytes()
    evidence_bytes = receipt.evidence_path.read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != receipt.manifest_sha256:
        raise PreflightError("live manifest digest mismatch while building tar context")
    if hashlib.sha256(evidence_bytes).hexdigest() != receipt.evidence_sha256:
        raise PreflightError("live evidence digest mismatch while building tar context")
    try:
        manifest = ReleaseManifest.from_mapping(
            _json_bytes_mapping(manifest_bytes, "release manifest")
        )
    except ManifestError as exc:
        raise PreflightError(f"release manifest contract is invalid: {exc}") from exc
    evidence = VerificationEvidence.from_mapping(
        _json_bytes_mapping(evidence_bytes, "verification evidence")
    )
    if manifest.source_commit != receipt.source_commit:
        raise PreflightError("live manifest sourceCommit does not match receipt")
    if evidence.source_commit != receipt.source_commit:
        raise PreflightError("live evidence sourceCommit does not match receipt")
    if evidence.manifest_sha256 != receipt.manifest_sha256:
        raise PreflightError("live evidence manifestSha256 does not match receipt")
    validate_verification_binding(
        repo_root,
        evidence.verification_commit,
        "backend/release/v7.3.json",
        receipt.manifest_sha256,
    )
    if evidence.phase != receipt.evidence_phase:
        raise PreflightError("live evidence phase does not match receipt")
    mode = "build-only" if receipt.evidence_phase == "pre_cloud" else "deploy"
    _validate_phase(evidence, mode)
    _validate_freshness(evidence, now or datetime.now(timezone.utc), MAX_EVIDENCE_AGE_SECONDS)

    manifest_artifacts = {artifact.id: artifact for artifact in manifest.artifacts}
    receipt_artifacts = {artifact.id: artifact for artifact in receipt.artifacts}
    if set(manifest_artifacts) != set(receipt_artifacts):
        raise PreflightError("manifest artifact IDs do not match receipt")
    for artifact_id, receipt_artifact in receipt_artifacts.items():
        manifest_artifact = manifest_artifacts[artifact_id]
        expected_local = (repo_root / manifest_artifact.local_relative_path).resolve()
        if receipt_artifact.local_path != expected_local:
            raise PreflightError(f"receipt artifact {artifact_id} localPath does not match manifest")
        if (
            receipt_artifact.sha256 != manifest_artifact.sha256
            or receipt_artifact.size_bytes != manifest_artifact.size_bytes
            or receipt_artifact.container_path != manifest_artifact.container_path
        ):
            raise PreflightError(f"receipt artifact {artifact_id} identity does not match manifest")
    return manifest_bytes, evidence_bytes, expected_evidence_relative, receipt.artifacts


def _expected_injection_fingerprints(
    *,
    manifest_bytes: bytes,
    evidence_bytes: bytes,
    evidence_relative: str,
    artifacts: Sequence[ReceiptArtifact],
) -> dict[str, _TarFingerprint]:
    expected = {
        "backend/release/v7.3.json": _TarFingerprint(
            kind="file",
            mode=0o644,
            size=len(manifest_bytes),
            sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        ),
        evidence_relative: _TarFingerprint(
            kind="file",
            mode=0o644,
            size=len(evidence_bytes),
            sha256=hashlib.sha256(evidence_bytes).hexdigest(),
        ),
    }
    for artifact in artifacts:
        expected[artifact.container_path.removeprefix("/app/")] = _TarFingerprint(
            kind="file",
            mode=0o644,
            size=artifact.size_bytes,
            sha256=artifact.sha256,
        )
    return expected


@contextmanager
def _snapshot_injections(
    *,
    repo_root: Path,
    receipt: PreflightReceipt,
    workspace_parent: Path,
    now: datetime | None,
) -> Iterator[dict[str, _InjectionSource]]:
    manifest_bytes, evidence_bytes, evidence_relative, artifacts = _read_receipt_metadata(
        repo_root=repo_root,
        receipt=receipt,
        now=now,
    )
    with tempfile.TemporaryDirectory(prefix=".release-inputs-", dir=workspace_parent) as raw_workspace:
        workspace = Path(raw_workspace)
        workspace.chmod(0o700)
        injections: dict[str, _InjectionSource] = {
            "backend/release/v7.3.json": _InjectionSource(
                size=len(manifest_bytes),
                sha256=hashlib.sha256(manifest_bytes).hexdigest(),
                content=manifest_bytes,
            ),
            evidence_relative: _InjectionSource(
                size=len(evidence_bytes),
                sha256=hashlib.sha256(evidence_bytes).hexdigest(),
                content=evidence_bytes,
            ),
        }
        try:
            for index, artifact in enumerate(artifacts):
                snapshot_path = workspace / f"artifact-{index:04d}.snapshot"
                digest = hashlib.sha256()
                size = 0
                try:
                    with artifact.local_path.open("rb") as source:
                        descriptor = os.open(
                            snapshot_path,
                            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                            0o600,
                        )
                        with os.fdopen(descriptor, "wb") as snapshot:
                            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                                size += len(chunk)
                                digest.update(chunk)
                                snapshot.write(chunk)
                            snapshot.flush()
                            os.fsync(snapshot.fileno())
                except OSError as exc:
                    raise PreflightError(f"live artifact {artifact.id} cannot snapshot: {exc}") from exc
                if size != artifact.size_bytes:
                    raise PreflightError(f"live artifact {artifact.id} size mismatch")
                if digest.hexdigest() != artifact.sha256:
                    raise PreflightError(f"live artifact {artifact.id} digest mismatch")
                injections[artifact.container_path.removeprefix("/app/")] = _InjectionSource(
                    size=size,
                    sha256=digest.hexdigest(),
                    snapshot_path=snapshot_path,
                )
            yield injections
        finally:
            # TemporaryDirectory performs the actual bounded cleanup; clearing
            # references first prevents accidental reuse after this boundary.
            injections.clear()


def _canonical_tar_info(name: str, *, mode: int, size: int = 0, directory: bool = False) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name + ("/" if directory else ""))
    info.mode = mode
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    if directory:
        info.type = tarfile.DIRTYPE
    else:
        info.size = size
    return info


def _write_streamed_tar_context(
    *,
    repo_root: Path,
    source_commit: str,
    injections: Mapping[str, _InjectionSource],
    destination: Path,
) -> None:
    seen: set[str] = set()
    try:
        with _git_archive_stream(repo_root, source_commit) as source_stream:
            with tarfile.open(fileobj=source_stream, mode="r|*") as source_archive:
                with destination.open("wb") as raw_output:
                    with tarfile.open(
                        fileobj=raw_output,
                        mode="w|",
                        format=tarfile.USTAR_FORMAT,
                    ) as output_archive:
                        for member in source_archive:
                            name = _safe_tar_name(member.name)
                            if name in seen:
                                raise PreflightError(
                                    f"source archive contains duplicate member: {name}"
                                )
                            seen.add(name)
                            if name in injections:
                                continue
                            if member.isdir():
                                output_archive.addfile(
                                    _canonical_tar_info(name, mode=0o755, directory=True)
                                )
                            elif member.isfile():
                                member_stream = source_archive.extractfile(member)
                                if member_stream is None:
                                    raise PreflightError(
                                        f"source archive cannot read member: {name}"
                                    )
                                output_archive.addfile(
                                    _canonical_tar_info(
                                        name,
                                        mode=_canonical_member_mode(member),
                                        size=member.size,
                                    ),
                                    member_stream,
                                )
                            else:
                                raise PreflightError(
                                    "source archive contains forbidden symlink or special member: "
                                    f"{name}"
                                )
                        for name in sorted(injections):
                            injection = injections[name]
                            with injection.open() as content:
                                output_archive.addfile(
                                    _canonical_tar_info(
                                        name,
                                        mode=0o644,
                                        size=injection.size,
                                    ),
                                    content,
                                )
                    raw_output.flush()
                    os.fsync(raw_output.fileno())
    except (tarfile.TarError, OSError) as exc:
        raise PreflightError(f"cannot write final build context: {exc}") from exc


def validate_tar_context(
    *,
    repo_root: Path | str,
    receipt: Mapping[str, object] | PreflightReceipt,
    tar_path: Path | str,
    now: datetime | None = None,
) -> None:
    root = Path(repo_root).resolve()
    parsed = receipt if isinstance(receipt, PreflightReceipt) else PreflightReceipt.from_mapping(receipt)
    manifest_bytes, evidence_bytes, evidence_relative, artifacts = _read_receipt_metadata(
        repo_root=root, receipt=parsed, now=now
    )
    injections = _expected_injection_fingerprints(
        manifest_bytes=manifest_bytes,
        evidence_bytes=evidence_bytes,
        evidence_relative=evidence_relative,
        artifacts=artifacts,
    )
    with _git_archive_stream(root, parsed.source_commit) as source_stream:
        source_entries = _tar_fingerprints(source_stream, "source archive")
    try:
        with Path(tar_path).open("rb") as raw_stream:
            _validate_raw_tar_layout(raw_stream, "final build context")
        with Path(tar_path).open("rb") as final_stream:
            final_entries = _tar_fingerprints(
                final_stream,
                "final build context",
                require_canonical_headers=True,
            )
    except OSError as exc:
        raise PreflightError(f"final build context cannot be opened: {exc}") from exc
    expected_names = (set(source_entries) - set(injections)) | set(injections)
    if set(final_entries) != expected_names:
        missing = sorted(expected_names - set(final_entries))
        extra = sorted(set(final_entries) - expected_names)
        raise PreflightError(
            f"final build context member mismatch; missing={missing}, extra={extra}"
        )
    for name, source_entry in source_entries.items():
        if name in injections:
            continue
        if final_entries[name] != source_entry:
            raise PreflightError(f"final build context source member mismatch: {name}")
    for name, expected_entry in injections.items():
        entry = final_entries[name]
        if entry != expected_entry:
            raise PreflightError(f"final build context injected member mismatch: {name}")


def build_validated_tar_context(
    *,
    repo_root: Path | str,
    receipt: Mapping[str, object] | PreflightReceipt,
    output_path: Path | str,
    now: datetime | None = None,
) -> Path:
    root = Path(repo_root).resolve()
    parsed = receipt if isinstance(receipt, PreflightReceipt) else PreflightReceipt.from_mapping(receipt)
    destination = Path(output_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".release-context-", suffix=".tar", dir=destination.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with _snapshot_injections(
            repo_root=root,
            receipt=parsed,
            workspace_parent=destination.parent,
            now=now,
        ) as injections:
            _write_streamed_tar_context(
                repo_root=root,
                source_commit=parsed.source_commit,
                injections=injections,
                destination=temporary,
            )
        validate_tar_context(
            repo_root=root,
            receipt=parsed,
            tar_path=temporary,
            now=now,
        )
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def validate_release_preflight(
    *,
    repo_root: Path | str,
    manifest_path: Path | str,
    evidence_path: Path | str,
    mode: str,
    image_tag: str,
    now: datetime | None = None,
    max_evidence_age_seconds: int = MAX_EVIDENCE_AGE_SECONDS,
) -> PreflightResult:
    if mode not in {"build-only", "deploy"}:
        raise PreflightError("mode must be build-only or deploy")
    if isinstance(max_evidence_age_seconds, bool) or max_evidence_age_seconds <= 0:
        raise PreflightError("max evidence age must be a positive integer")
    root = Path(repo_root).resolve()
    resolved_manifest_path = Path(manifest_path).resolve()
    resolved_evidence_path = Path(evidence_path).resolve()
    expected_manifest_relative = "backend/release/v7.3.json"
    expected_evidence_relative = (
        "backend/release/verification/v7.3-pre-cloud.json"
        if mode == "build-only"
        else "backend/release/verification/v7.3.json"
    )
    try:
        manifest_relative = resolved_manifest_path.relative_to(root).as_posix()
    except ValueError as exc:
        raise PreflightError(
            f"manifest path must be {expected_manifest_relative} below the repository root"
        ) from exc
    if manifest_relative != expected_manifest_relative:
        raise PreflightError(f"manifest path must be {expected_manifest_relative}")
    try:
        evidence_relative = resolved_evidence_path.relative_to(root).as_posix()
    except ValueError as exc:
        raise PreflightError(
            f"evidence path must be {expected_evidence_relative} below the repository root"
        ) from exc
    if evidence_relative != expected_evidence_relative:
        raise PreflightError(f"evidence path must be {expected_evidence_relative}")
    try:
        manifest_bytes = resolved_manifest_path.read_bytes()
    except OSError as exc:
        raise PreflightError(f"invalid release manifest: cannot read {resolved_manifest_path}: {exc}") from exc
    try:
        manifest = ReleaseManifest.from_mapping(
            _json_bytes_mapping(manifest_bytes, "release manifest")
        )
    except (ManifestError, PreflightError) as exc:
        raise PreflightError(f"invalid release manifest: {exc}") from exc
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    try:
        evidence_bytes = resolved_evidence_path.read_bytes()
    except OSError as exc:
        raise PreflightError(
            f"verification evidence cannot load from {resolved_evidence_path}: {exc}"
        ) from exc
    evidence_sha256 = hashlib.sha256(evidence_bytes).hexdigest()
    evidence = VerificationEvidence.from_mapping(
        _json_bytes_mapping(evidence_bytes, "verification evidence")
    )
    if evidence.source_commit != manifest.source_commit:
        raise PreflightError(
            "evidence sourceCommit mismatch: "
            f"manifest has {manifest.source_commit}, evidence has {evidence.source_commit}"
        )
    if evidence.manifest_sha256 != manifest_sha256:
        raise PreflightError(
            "evidence manifestSha256 mismatch: "
            f"expected {manifest_sha256}, got {evidence.manifest_sha256}"
        )
    _validate_phase(evidence, mode)
    _validate_freshness(
        evidence,
        now or datetime.now(timezone.utc),
        max_evidence_age_seconds,
    )
    validate_image_tag(image_tag, manifest, manifest_sha256)
    validate_git_source(
        root,
        manifest.source_commit,
        required_tracked_paths=(manifest_relative, evidence_relative),
    )
    validate_verification_binding(
        root,
        evidence.verification_commit,
        manifest_relative,
        manifest_sha256,
    )
    if evidence.remote_execution is not None:
        from backend.app.daytona_worker_image import repository_worker_context_sha256

        expected_context = repository_worker_context_sha256(root)
        if evidence.remote_execution.value["workerContextSha256"] != expected_context:
            raise PreflightError(
                "remoteExecution workerContextSha256 does not match release context"
            )
    artifacts: list[tuple[str, Path, str]] = []
    artifact_metadata: list[tuple[str, str, int]] = []
    for artifact in manifest.artifacts:
        try:
            path = resolve_artifact(manifest, artifact.id, root, "local")
        except ManifestError as exc:
            raise PreflightError(str(exc)) from exc
        artifacts.append((artifact.id, path, artifact.container_path))
        artifact_metadata.append((artifact.id, artifact.sha256, artifact.size_bytes))
    return PreflightResult(
        source_commit=manifest.source_commit,
        manifest_sha256=manifest_sha256,
        manifest_path=resolved_manifest_path,
        evidence_path=resolved_evidence_path,
        evidence_phase=evidence.phase,
        evidence_sha256=evidence_sha256,
        artifacts=tuple(artifacts),
        artifact_metadata=tuple(artifact_metadata),
    )


def _parse_now(value: str) -> datetime:
    return _timestamp(value, "--now")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate source, manifest, evidence, and artifacts")
    validate.add_argument("--repo-root", required=True, type=Path)
    validate.add_argument("--manifest", required=True, type=Path)
    validate.add_argument("--evidence", required=True, type=Path)
    validate.add_argument("--mode", required=True, choices=("build-only", "deploy"))
    validate.add_argument("--image-tag", required=True)
    validate.add_argument("--now", type=_parse_now)
    validate.add_argument(
        "--max-evidence-age-seconds",
        type=int,
        default=MAX_EVIDENCE_AGE_SECONDS,
    )
    freshness = subparsers.add_parser(
        "check-freshness", help="fail before release evidence enters its renewal window"
    )
    freshness.add_argument("--evidence", required=True, type=Path)
    freshness.add_argument("--mode", required=True, choices=("build-only", "deploy"))
    freshness.add_argument("--minimum-validity-seconds", type=int, default=4 * 60 * 60)
    freshness.add_argument("--max-evidence-age-seconds", type=int, default=MAX_EVIDENCE_AGE_SECONDS)
    freshness.add_argument("--now", type=_parse_now)
    labels = subparsers.add_parser("validate-labels", help="validate built image provenance labels")
    labels.add_argument("--expected-source-commit", required=True)
    labels.add_argument("--expected-manifest-sha256", required=True)
    labels.add_argument("--source-label", required=True)
    labels.add_argument("--manifest-label", required=True)
    staged = subparsers.add_parser(
        "validate-staged",
        help="revalidate exact live and staged bytes against a preflight receipt",
    )
    staged.add_argument("--context-root", required=True, type=Path)
    staged.add_argument("--receipt", required=True, type=Path)
    build_context = subparsers.add_parser(
        "build-context", help="create and validate an immutable tar build context"
    )
    build_context.add_argument("--repo-root", required=True, type=Path)
    build_context.add_argument("--receipt", required=True, type=Path)
    build_context.add_argument("--output", required=True, type=Path)
    validate_context = subparsers.add_parser(
        "validate-context", help="validate an existing immutable tar build context"
    )
    validate_context.add_argument("--repo-root", required=True, type=Path)
    validate_context.add_argument("--receipt", required=True, type=Path)
    validate_context.add_argument("--tar", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "check-freshness":
            evidence = load_verification_evidence(args.evidence)
            _validate_phase(evidence, args.mode)
            remaining = validate_evidence_validity_window(
                evidence,
                args.now or datetime.now(timezone.utc),
                args.max_evidence_age_seconds,
                args.minimum_validity_seconds,
            )
            print(json.dumps({
                "evidenceFresh": True,
                "minimumValiditySeconds": args.minimum_validity_seconds,
                "remainingValiditySeconds": remaining,
            }, sort_keys=True))
            return 0
        if args.command == "validate-labels":
            validate_image_labels(
                expected_source_commit=args.expected_source_commit,
                expected_manifest_sha256=args.expected_manifest_sha256,
                source_label=args.source_label,
                manifest_label=args.manifest_label,
            )
            print(json.dumps({"labelsValid": True}, sort_keys=True))
            return 0
        if args.command == "validate-staged":
            try:
                receipt = load_json_mapping(args.receipt)
            except ManifestError as exc:
                raise PreflightError(f"preflight receipt cannot load: {exc}") from exc
            staged = validate_staged_context(
                context_root=args.context_root,
                receipt=receipt,
            )
            print(json.dumps(staged.to_mapping(), indent=2, sort_keys=True))
            return 0
        if args.command in {"build-context", "validate-context"}:
            try:
                receipt = load_json_mapping(args.receipt)
            except ManifestError as exc:
                raise PreflightError(f"preflight receipt cannot load: {exc}") from exc
            if args.command == "build-context":
                output = build_validated_tar_context(
                    repo_root=args.repo_root,
                    receipt=receipt,
                    output_path=args.output,
                )
                print(json.dumps({"contextTar": str(output), "contextValid": True}, sort_keys=True))
            else:
                validate_tar_context(
                    repo_root=args.repo_root,
                    receipt=receipt,
                    tar_path=args.tar,
                )
                print(json.dumps({"contextValid": True}, sort_keys=True))
            return 0
        result = validate_release_preflight(
            repo_root=args.repo_root,
            manifest_path=args.manifest,
            evidence_path=args.evidence,
            mode=args.mode,
            image_tag=args.image_tag,
            now=args.now,
            max_evidence_age_seconds=args.max_evidence_age_seconds,
        )
        print(json.dumps(result.to_mapping(), indent=2, sort_keys=True))
        return 0
    except PreflightError as exc:
        print(f"preflight failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover - exercised by the deployment script
    raise SystemExit(main())
