from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from backend.scripts.football_external_real_eval_chain_common import (
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    load_json,
    reset_output,
    standard_false_flags,
    utc_now_iso,
    write_outcome,
)

__all__ = [
    "DEFAULT_CANDIDATE_NAME",
    "DEFAULT_STORAGE_ROOT",
    "candidate_root",
    "load_json",
    "reset_output",
    "standard_false_flags",
    "utc_now_iso",
    "write_outcome",
    "guarded_summary",
    "latest_versioned_dir",
    "paired_or_latest_versioned_dir",
]


def _version_suffix(path: Path) -> int:
    match = re.search(r"_v(\d+)$", path.name)
    return int(match.group(1)) if match else 0


def latest_versioned_dir(root: Path, prefix: str, default_dir_name: str) -> Path:
    dirs = [path for path in root.glob(f"{prefix}_v*") if path.is_dir()]
    if not dirs:
        return root / default_dir_name
    return max(dirs, key=_version_suffix)


def paired_or_latest_versioned_dir(root: Path, *, output_dir_name: str, input_prefix: str, default_dir_name: str) -> Path:
    match = re.search(r"_v(\d+)$", output_dir_name)
    if match:
        paired = root / f"{input_prefix}_v{match.group(1)}"
        if paired.exists():
            return paired
    return latest_versioned_dir(root, input_prefix, default_dir_name)


def guarded_summary(
    *,
    batch_name: str,
    goal: bool,
    primary_blocker: str | None,
    next_lever: str,
    english: str,
    attempt_families: list[str],
    extra: dict[str, Any],
) -> dict[str, Any]:
    return {
        "batchName": batch_name,
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": attempt_families,
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        **extra,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }


def candidate_output_root(storage_root: Path, candidate_name: str, output_dir_name: str) -> Path:
    return reset_output(candidate_root(Path(storage_root), candidate_name), output_dir_name)
