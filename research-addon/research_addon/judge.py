"""Explicit developer-tool execution boundary for supported-coverage judging."""

from __future__ import annotations

import argparse
from collections.abc import Iterator
from contextlib import contextmanager
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from research_addon.path_guards import PathResolutionError, resolve_run_root


_DELEGATED_SCRIPT = Path("backend/scripts/run_local_app_path_proof.py")


class JudgeExecutionError(Exception):
    """A controlled configuration, delegation, or result-contract failure."""

    def __init__(self, message: str, *, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code if 1 <= exit_code <= 255 else 1


@contextmanager
def _controlled_path_errors() -> Iterator[None]:
    try:
        yield
    except (JudgeExecutionError, PathResolutionError):
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        raise JudgeExecutionError(
            f"Configured path could not be resolved: {exc}"
        ) from exc


class JudgeContract:
    """Stable input, delegate, and result field declarations."""

    TRACK_ID = "supported-coverage"
    REQUIRED_OUTPUT_FIELDS = [
        "acceptedBallFrames",
        "supportedAcceptedBallRatio",
        "controlledPossessionFrames",
        "eventFamilyCount",
        "truthGateReasons",
    ]

    @classmethod
    def input_contract(cls) -> dict[str, Any]:
        return {
            "track_id": cls.TRACK_ID,
            "manifest": "explicit corpus manifest path",
            "entry_index": "zero-based integer (default: 0)",
            "repo_root": "validated football-analyst repository",
            "python": "validated Python interpreter",
            "storage_root": "addon or validated temporary directory",
        }

    @classmethod
    def delegated_target(cls) -> Path:
        return _DELEGATED_SCRIPT

    @classmethod
    def required_summary_fields(cls) -> list[str]:
        return list(cls.REQUIRED_OUTPUT_FIELDS)


def _source_checkout_root() -> Path | None:
    package_root = Path(__file__).resolve().parent
    addon_root = package_root.parent
    if addon_root.name != "research-addon" or package_root.name != "research_addon":
        return None
    repository = addon_root.parent.resolve()
    if (repository / "research-addon" / "research_addon").resolve() != package_root:
        return None
    script = repository / _DELEGATED_SCRIPT
    if script.is_symlink() or not script.is_file() or script.resolve() != script:
        return None
    return repository


def _resolve_repository(repo_root: Path | str | None) -> tuple[Path, Path]:
    checkout_root = _source_checkout_root()
    if repo_root is None:
        if checkout_root is None:
            raise JudgeExecutionError(
                "Repository root is required outside a source checkout"
            )
        repository = checkout_root
    else:
        repository = Path(repo_root).expanduser().resolve()
    if not repository.is_dir():
        raise JudgeExecutionError(f"Repository root is not a directory: {repository}")
    script = repository / _DELEGATED_SCRIPT
    if script.is_symlink() or not script.is_file() or script.resolve() != script:
        raise JudgeExecutionError(f"Delegated script is not a regular file: {script}")
    return repository, script


def _resolve_python(python: Path | str | None) -> Path:
    if python is None:
        if _source_checkout_root() is None:
            raise JudgeExecutionError(
                "Python interpreter is required outside a source checkout"
            )
        candidate = Path(sys.executable)
    else:
        candidate = Path(python).expanduser()
    interpreter = candidate.resolve()
    if not interpreter.is_file() or not os.access(interpreter, os.X_OK):
        raise JudgeExecutionError(
            f"Python interpreter is not an executable regular file: {interpreter}"
        )
    return interpreter


def _load_manifest_entry(
    manifest_path: Path | str | None,
    entry_index: int,
    repository: Path,
) -> tuple[dict[str, Any], Path]:
    from research_addon.corpus import CorpusManifest

    if manifest_path is None:
        raise JudgeExecutionError("Corpus manifest is required for execution")
    manifest_file = Path(manifest_path).expanduser().resolve()
    if not manifest_file.is_file():
        raise JudgeExecutionError(f"Corpus manifest is not a regular file: {manifest_file}")
    try:
        manifest = CorpusManifest.from_file(manifest_file)
    except (OSError, ValueError, TypeError, AttributeError, json.JSONDecodeError) as exc:
        raise JudgeExecutionError(f"Corpus manifest is malformed: {exc}") from exc
    if isinstance(entry_index, bool) or not isinstance(entry_index, int) or entry_index < 0:
        raise JudgeExecutionError(f"Corpus manifest entry {entry_index!r} is invalid")
    try:
        entry = manifest.entries[entry_index]
    except IndexError as exc:
        raise JudgeExecutionError(
            f"Corpus manifest entry {entry_index} does not exist"
        ) from exc
    if not isinstance(entry, dict):
        raise JudgeExecutionError(f"Corpus manifest entry {entry_index} is not an object")
    raw_video = entry.get("video_path")
    if not isinstance(raw_video, str) or not raw_video:
        raise JudgeExecutionError(
            f"Corpus manifest entry {entry_index} has no valid video_path"
        )
    declared_video = Path(raw_video).expanduser()
    candidate_video = (
        declared_video if declared_video.is_absolute() else repository / declared_video
    )
    if candidate_video.is_symlink():
        raise JudgeExecutionError(f"Video file is not a regular file: {candidate_video}")
    video_path = candidate_video.resolve()
    if not declared_video.is_absolute() and not video_path.is_relative_to(repository):
        raise JudgeExecutionError(
            f"Video file escapes the repository: {declared_video}"
        )
    if video_path.is_symlink() or not video_path.is_file():
        raise JudgeExecutionError(f"Video file is not a regular file: {video_path}")
    return entry, video_path


def _normalize_entry_index(entry_index: int | str) -> int:
    if isinstance(entry_index, bool):
        raise JudgeExecutionError(f"Corpus manifest entry {entry_index!r} is invalid")
    if isinstance(entry_index, int):
        normalized = entry_index
    elif isinstance(entry_index, str):
        try:
            normalized = int(entry_index, 10)
        except ValueError as exc:
            raise JudgeExecutionError(
                f"Corpus manifest entry {entry_index!r} is invalid"
            ) from exc
    else:
        raise JudgeExecutionError(f"Corpus manifest entry {entry_index!r} is invalid")
    if normalized < 0:
        raise JudgeExecutionError(f"Corpus manifest entry {entry_index!r} is invalid")
    return normalized


def _resolve_execution_inputs(
    manifest_path: Path | str | None,
    *,
    repo_root: Path | str | None,
    python: Path | str | None,
    entry_index: int | str,
) -> tuple[dict[str, Any], Path, Path, Path, Path]:
    with _controlled_path_errors():
        repository, script = _resolve_repository(repo_root)
        interpreter = _resolve_python(python)
        normalized_index = _normalize_entry_index(entry_index)
        entry, video_path = _load_manifest_entry(
            manifest_path, normalized_index, repository
        )
    return entry, video_path, repository, interpreter, script


def judge_is_ready(
    manifest_path: Path | str | None,
    *,
    repo_root: Path | str | None = None,
    python: Path | str | None = None,
    entry_index: int | str = 0,
    storage_root: Path | str | None = None,
) -> bool:
    """Return whether all non-mutating execution checks currently pass."""
    try:
        with _controlled_path_errors():
            resolve_run_root(storage_root)
            _resolve_execution_inputs(
                manifest_path,
                repo_root=repo_root,
                python=python,
                entry_index=entry_index,
            )
    except (JudgeExecutionError, PathResolutionError):
        return False
    return True


def _run_proof_via_script(
    video_path: Path,
    storage_root: Path,
    *,
    repo_root: Path,
    python: Path,
    poll_interval: float = 2.0,
    timeout: float = 600.0,
) -> Any:
    """Revalidate execution paths, invoke the delegate, and decode its JSON."""
    with _controlled_path_errors():
        storage_root = resolve_run_root(storage_root)
        repository, script = _resolve_repository(repo_root)
        interpreter = _resolve_python(python)
        video_path = video_path.resolve()
        if video_path.is_symlink() or not video_path.is_file():
            raise JudgeExecutionError(f"Video file is not a regular file: {video_path}")
    command = [
        str(interpreter),
        str(script),
        "--storage-root",
        str(storage_root),
        "--video-path",
        str(video_path),
        "--poll-interval-seconds",
        str(poll_interval),
        "--timeout-seconds",
        str(timeout),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=repository,
            timeout=timeout + 30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise JudgeExecutionError(f"Proof script could not complete: {exc}") from exc
    if result.returncode != 0:
        raise JudgeExecutionError(
            f"Proof script exited with {result.returncode}: {result.stderr.strip()}",
            exit_code=result.returncode,
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise JudgeExecutionError(f"Proof script produced non-JSON output: {exc}") from exc


def _validate_output(output: Any) -> dict[str, Any]:
    if not isinstance(output, dict):
        raise JudgeExecutionError("Proof output must be a JSON object")
    missing = [field for field in JudgeContract.REQUIRED_OUTPUT_FIELDS if field not in output]
    if missing:
        raise JudgeExecutionError(f"Proof output missing required fields: {missing}")
    for field in ("acceptedBallFrames", "controlledPossessionFrames", "eventFamilyCount"):
        value = output[field]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise JudgeExecutionError(f"Proof output {field} must be a non-negative integer")
    ratio = output["supportedAcceptedBallRatio"]
    if (
        isinstance(ratio, bool)
        or not isinstance(ratio, (int, float))
        or not math.isfinite(ratio)
        or not 0 <= ratio <= 1
    ):
        raise JudgeExecutionError(
            "Proof output supportedAcceptedBallRatio must be finite and within 0..1"
        )
    reasons = output["truthGateReasons"]
    if not isinstance(reasons, list) or not all(isinstance(reason, str) for reason in reasons):
        raise JudgeExecutionError("Proof output truthGateReasons must be a list of strings")
    return {field: output[field] for field in JudgeContract.REQUIRED_OUTPUT_FIELDS}


def run_judge(
    manifest_path: Path | str | None,
    storage_root: Path | str | None,
    *,
    repo_root: Path | str | None = None,
    python: Path | str | None = None,
    entry_index: int | str = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run one explicit manifest entry in one validated local context."""
    with _controlled_path_errors():
        resolved_storage_root = resolve_run_root(storage_root)
    if dry_run:
        return {
            "_dry_run": True,
            "track_id": JudgeContract.TRACK_ID,
            "delegated_target": str(JudgeContract.delegated_target()),
            "input_contract": JudgeContract.input_contract(),
            "required_output_fields": JudgeContract.required_summary_fields(),
            "required_configuration": ["manifest", "repo_root", "python"],
            "storage_root": str(resolved_storage_root),
        }
    _, video_path, repository, interpreter, _ = _resolve_execution_inputs(
        manifest_path,
        repo_root=repo_root,
        python=python,
        entry_index=entry_index,
    )
    output = _run_proof_via_script(
        video_path,
        resolved_storage_root,
        repo_root=repository,
        python=interpreter,
    )
    return _validate_output(output)


def emit_judge_summary(output: dict[str, Any]) -> str:
    """Emit a compact summary line for valid judge output."""
    output = _validate_output(output)
    return (
        f"acceptedBallFrames={output['acceptedBallFrames']}, "
        f"supportedAcceptedBallRatio={output['supportedAcceptedBallRatio']}, "
        f"controlledPossessionFrames={output['controlledPossessionFrames']}, "
        f"eventFamilyCount={output['eventFamilyCount']}, "
        f"truthGateReasons={output['truthGateReasons']}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="research_addon.judge",
        description="Judge wrapper for supported-coverage lane",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--storage-root", default=None)
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--python", default=None)
    parser.add_argument("--entry-index", default="0")
    args = parser.parse_args()
    try:
        result = run_judge(
            args.manifest,
            args.storage_root,
            repo_root=args.repo_root,
            python=args.python,
            entry_index=args.entry_index,
            dry_run=args.dry_run,
        )
    except (JudgeExecutionError, PathResolutionError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return getattr(exc, "exit_code", 1)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
