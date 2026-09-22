from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
from typing import Any, Callable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"

FALSE_GUARDRAILS = (
    "detectorEvaluationExecuted",
    "candidateEvaluationExecuted",
    "candidateReadyForEvaluation",
    "normalMatchStorageMutationExecuted",
    "videoDownloadExecuted",
    "dataDownloadExecuted",
    "trainingExecuted",
    "promotionMutationExecuted",
    "promotionReady",
    "runtimeDefaultMutationExecuted",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def candidate_root(storage_root: Path, candidate_name: str = DEFAULT_CANDIDATE_NAME) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_json_sorted_no_newline(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_json_unsorted_no_newline(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_json_unsorted_newline(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def load_json_dict_or_empty_required(path: Path, *, required: bool = True) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise FileNotFoundError(str(path))
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def load_json_dict_or_empty_optional(path: Path, *, required: bool = False) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def load_json_dict_or_empty_existing(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def load_json_object_payload_strict(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object payload in {path}")
    return payload


def load_json_object_strict(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def load_json_object_at_strict(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_zip_members_with_pyzipper(
    *,
    python_executable: str,
    sparse_zip_path: Path,
    member_sizes: Mapping[str, int],
    output_dir: Path,
    env: Mapping[str, str],
    credential_env_var: str,
) -> dict[str, Any]:
    script = r'''
import json
import os
from pathlib import Path
import shutil
import tempfile
import pyzipper

class _BoundedWriter:
    def __init__(self, raw, limit):
        self.raw = raw
        self.limit = limit
        self.size = 0

    def write(self, data):
        if self.size + len(data) > self.limit:
            raise ValueError("ZIP member exceeded its approved uncompressed size")
        written = self.raw.write(data)
        if written != len(data):
            raise OSError("short output write")
        self.size += written
        return written

sparse_zip = Path(os.environ["SOCCERNET_SPARSE_ZIP"])
output_dir = Path(os.environ["SOCCERNET_OUTPUT_DIR"]).resolve()
member_sizes = json.loads(os.environ["SOCCERNET_MEMBER_SIZES"])
password = os.environ[os.environ["SOCCERNET_CREDENTIAL_ENV_VAR"]].encode()
results = []
with pyzipper.AESZipFile(sparse_zip) as zf:
    zf.pwd = password
    for member, expected_size in member_sizes.items():
        if type(expected_size) is not int or expected_size <= 0:
            raise ValueError("approved uncompressed size must be a positive integer")
        if int(zf.getinfo(member).file_size) != expected_size:
            raise ValueError("ZIP member size does not match its approval contract")
        out = (output_dir / member).resolve()
        out.relative_to(output_dir)
        out.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with zf.open(member) as source, tempfile.NamedTemporaryFile(dir=out.parent, delete=False) as target:
                temp_path = Path(target.name)
                writer = _BoundedWriter(target, expected_size)
                shutil.copyfileobj(source, writer, length=1024 * 1024)
                if writer.size != expected_size:
                    raise ValueError("ZIP member ended before its approved uncompressed size")
                target.flush()
                os.fsync(target.fileno())
            os.replace(temp_path, out)
            temp_path = None
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
        results.append({"memberPath": member, "relativePath": str(out.relative_to(output_dir)), "sizeBytes": expected_size})
print(json.dumps({"ok": True, "results": results}))
'''
    child_env = dict(env)
    child_env.update(
        {
            "SOCCERNET_SPARSE_ZIP": str(sparse_zip_path),
            "SOCCERNET_OUTPUT_DIR": str(output_dir),
            "SOCCERNET_MEMBER_SIZES": json.dumps(dict(member_sizes)),
            "SOCCERNET_CREDENTIAL_ENV_VAR": credential_env_var,
        }
    )
    completed = subprocess.run([python_executable, "-c", script], check=False, capture_output=True, text=True, env=child_env)
    parsed: dict[str, Any] | None = None
    if completed.stdout.strip():
        try:
            parsed = json.loads(completed.stdout.strip().splitlines()[-1])
        except json.JSONDecodeError:
            pass
    return {
        "returnCode": completed.returncode,
        "stdoutTail": completed.stdout[-1200:],
        "stderrTail": completed.stderr[-1200:],
        "parsedResult": parsed,
    }


def reset_output(candidate_root: Path, output_dir_name: str) -> Path:
    name = Path(output_dir_name)
    if name.is_absolute() or not name.parts or ".." in name.parts:
        raise ValueError("output_dir_name must be a relative child of candidate_root")
    root = Path(candidate_root)
    result = root / name
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    root_parts = root.parts
    start = root.anchor if root.is_absolute() else "."
    if root.is_absolute():
        root_parts = root_parts[1:]

    with ExitStack() as opened:
        parent_fd = os.open(start, flags)
        opened.callback(os.close, parent_fd)

        def descend(part: str, *, label: str) -> int:
            nonlocal parent_fd
            try:
                child_fd = os.open(part, flags, dir_fd=parent_fd)
            except FileNotFoundError:
                try:
                    os.mkdir(part, dir_fd=parent_fd)
                except FileExistsError:
                    pass
                try:
                    child_fd = os.open(part, flags, dir_fd=parent_fd)
                except OSError as exc:
                    raise ValueError(f"{label} cannot contain symlinks") from exc
            except OSError as exc:
                raise ValueError(f"{label} cannot contain symlinks") from exc
            opened.callback(os.close, child_fd)
            parent_fd = child_fd
            return child_fd

        for part in root_parts:
            descend(part, label="candidate_root")
        for part in name.parts[:-1]:
            descend(part, label="output directory")

        child = name.parts[-1]
        try:
            child_stat = os.stat(child, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            child_stat = None
        if child_stat is not None:
            if stat.S_ISLNK(child_stat.st_mode):
                raise ValueError("output directory cannot contain symlinks")
            shutil.rmtree(child, dir_fd=parent_fd)
        try:
            os.mkdir(child, dir_fd=parent_fd)
        except FileExistsError as exc:
            raise ValueError("output directory changed during reset") from exc

    return result


def guardrails_false(payload: dict[str, Any] | None) -> bool:
    payload = payload if isinstance(payload, dict) else {}
    return all(payload.get(key) is False for key in FALSE_GUARDRAILS)


def standard_false_flags() -> dict[str, bool]:
    return {
        "detectorEvaluationExecuted": False,
        "candidateEvaluationExecuted": False,
        "candidateReadyForEvaluation": False,
        "normalMatchStorageMutationExecuted": False,
        "videoDownloadExecuted": False,
        "dataDownloadExecuted": False,
        "trainingExecuted": False,
        "trainingAllowed": False,
        "promotionMutationExecuted": False,
        "promotionReady": False,
        "runtimeDefaultMutationExecuted": False,
        "runtimeDefaultMutationAllowed": False,
    }


def write_outcome(
    *,
    output_root: Path,
    summary_filename: str,
    summary: dict[str, Any],
    artifacts: dict[str, dict[str, Any]],
    markdown_title: str,
) -> dict[str, Any]:
    write_json(output_root / summary_filename, summary)
    for filename, payload in artifacts.items():
        write_json(output_root / filename, payload)
    outcome = {"summary": summary, **{filename.removesuffix(".json"): payload for filename, payload in artifacts.items()}}
    write_json(output_root / "batch_outcome_analysis.json", outcome)
    md = "\n".join(
        [
            f"# {markdown_title}",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )
    (output_root / "batch_outcome_analysis.md").write_text(md, encoding="utf-8")
    return summary


def build_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=None)
    return parser


def main_for(description: str, runner: Callable[..., dict[str, Any]]) -> None:
    parser = build_parser(description)
    args = parser.parse_args()
    kwargs: dict[str, Any] = {
        "storage_root": args.storage_root,
        "candidate_name": str(args.candidate_name),
    }
    if args.output_dir_name:
        kwargs["output_dir_name"] = str(args.output_dir_name)
    payload = runner(**kwargs)
    print(json.dumps(payload, indent=2, sort_keys=True))
