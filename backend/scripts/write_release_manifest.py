"""Write a validated release manifest from explicit, reproducible inputs."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping, Sequence

from backend.app.release_manifest import (
    ManifestError,
    ReleaseManifest,
    load_json_mapping,
    resolve_artifact,
)


def write_release_manifest(
    output_path: Path | str,
    template: Mapping[str, Any],
    *,
    source_commit: str,
    created_at: str,
    artifact_root: Path | str,
    environment: str = "local",
) -> ReleaseManifest:
    """Validate explicit release data and atomically write stable JSON.

    ``source_commit`` and ``created_at`` are mandatory by design. The writer
    never consults Git state or the system clock. A failure syncing the parent
    directory is reported after the complete replacement is already visible.
    """

    payload = dict(template)
    if "sourceCommit" in payload and payload["sourceCommit"] != source_commit:
        raise ManifestError("sourceCommit mismatch between template and explicit value")
    if "createdAt" in payload and payload["createdAt"] != created_at:
        raise ManifestError("createdAt mismatch between template and explicit value")
    payload["sourceCommit"] = source_commit
    payload["createdAt"] = created_at
    manifest = ReleaseManifest.from_mapping(payload)
    manifest.validate_source_commit(source_commit)
    output = Path(output_path)
    verified_artifacts: dict[Path, str] = {}
    for artifact in manifest.artifacts:
        resolved_artifact = resolve_artifact(
            manifest,
            artifact.id,
            artifact_root,
            environment,
        )
        verified_artifacts[resolved_artifact] = artifact.id
    resolved_output = output.resolve(strict=False)
    if resolved_output in verified_artifacts:
        raise ManifestError(
            "output path aliases declared artifact "
            f"{verified_artifacts[resolved_output]}: {resolved_output}"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(manifest.to_json())
            stream.flush()
            os.fchmod(stream.fileno(), 0o644)
            os.fsync(stream.fileno())
        os.replace(temporary_path, output)
        temporary_path = None
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        directory_fd = os.open(output.parent, directory_flags)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="JSON manifest template")
    parser.add_argument("--output", required=True, type=Path, help="validated manifest output")
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--environment", choices=("local", "container"), default="local")
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--created-at", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        template = load_json_mapping(args.input)
        write_release_manifest(
            args.output,
            template,
            source_commit=args.source_commit,
            created_at=args.created_at,
            artifact_root=args.artifact_root,
            environment=args.environment,
        )
    except ManifestError as exc:
        _parser().error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
