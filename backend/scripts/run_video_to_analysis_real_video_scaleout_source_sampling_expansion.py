from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import main_for  # noqa: E402
from backend.scripts.video_to_analysis_operational_sprint_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    guarded_summary,
    latest_versioned_dir,
    load_json,
    reset_output,
    utc_now_iso,
    write_outcome,
)

DEFAULT_INSUFFICIENT_REFRESH_DIR_NAME = "video_to_analysis_real_video_scaleout_plan_refresh_v3"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_real_video_scaleout_source_sampling_expansion_v1"
BLOCKER_INSUFFICIENT_REFRESH_MISSING = "video_to_analysis_source_sampling_insufficient_refresh_missing"
BLOCKER_SOURCE_SAMPLING_POOL_EXHAUSTED = "video_to_analysis_real_video_scaleout_source_sampling_pool_exhausted"
NEXT_REFRESH = "video_to_analysis_real_video_scaleout_execution_approval"
NEXT_PLAN_REFRESH = "video_to_analysis_real_video_scaleout_plan_refresh"
NEXT_ROADMAP_DIRECTION = "video_to_analysis_next_roadmap_direction_snapshot"


def _attempt_plan() -> dict[str, Any]:
    return {"attemptBudget": 3, "attempts": [
        {"attemptNumber": 1, "attemptApproachFamily": "real_video_source_sampling_expansion"},
        {"attemptNumber": 2, "attemptApproachFamily": "real_video_source_sampling_scope_repair"},
        {"attemptNumber": 3, "attemptApproachFamily": "real_video_source_sampling_blocker_summary"},
    ]}


_ORDINAL_WORDS = {
    1: "first",
    2: "second",
    3: "third",
    4: "fourth",
    5: "fifth",
    6: "sixth",
    7: "seventh",
    8: "eighth",
    9: "ninth",
    10: "tenth",
    11: "eleventh",
    12: "twelfth",
    13: "thirteenth",
    14: "fourteenth",
    15: "fifteenth",
    16: "sixteenth",
    17: "seventeenth",
    18: "eighteenth",
    19: "nineteenth",
}


def _ordinal_word(value: int) -> str:
    if value in _ORDINAL_WORDS:
        return _ORDINAL_WORDS[value]
    tens_map = {
        20: "twenty",
        30: "thirty",
        40: "forty",
        50: "fifty",
        60: "sixty",
        70: "seventy",
        80: "eighty",
        90: "ninety",
    }
    whole_tens_map = {
        20: "twentieth",
        30: "thirtieth",
        40: "fortieth",
        50: "fiftieth",
        60: "sixtieth",
        70: "seventieth",
        80: "eightieth",
        90: "ninetieth",
    }
    if 20 <= value <= 99:
        tens = (value // 10) * 10
        ones = value % 10
        if ones == 0:
            return whole_tens_map[value]
        return f"{tens_map[tens]}_{_ORDINAL_WORDS[ones]}"
    raise ValueError(f"unsupported ordinal value for bounded source sampling: {value}")


def _candidate_pool(tranche_count: int = 12) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(tranche_count):
        operator_ordinal = _ordinal_word(index + 3)
        normal_storage_ordinal = _ordinal_word(index + 3)
        soccertrack_ordinal = _ordinal_word(index + 4)
        promoted_runtime_ordinal = _ordinal_word(index + 2)
        soccernet_primary_ordinal = _ordinal_word((index * 2) + 7)
        soccernet_reserve_ordinal = _ordinal_word((index * 2) + 8)
        rows.extend([
            {
                "id": f"operator_canary_{operator_ordinal}_followup_clip",
                "executionMode": "bounded_existing_or_approved_sample_only",
                "sourceFamily": "operator",
                "samplingReason": f"operator canary followup tranche {index + 1}",
            },
            {
                "id": f"soccernet_{soccernet_primary_ordinal}_bounded_member",
                "executionMode": "bounded_existing_or_approved_sample_only",
                "sourceFamily": "soccernet",
                "samplingReason": f"SoccerNet broadcast diversity tranche {index + 1}",
            },
            {
                "id": f"normal_storage_{normal_storage_ordinal}_followup_upload",
                "executionMode": "bounded_existing_or_approved_sample_only",
                "sourceFamily": "normal_storage",
                "samplingReason": f"normal-storage product path followup tranche {index + 1}",
            },
            {
                "id": f"soccertrack_{soccertrack_ordinal}_materialized_fixture",
                "executionMode": "bounded_existing_or_approved_sample_only",
                "sourceFamily": "soccertrack",
                "samplingReason": f"SoccerTrack materialized fixture smoke tranche {index + 1}",
            },
            {
                "id": f"promoted_runtime_{promoted_runtime_ordinal}_alternate_reference_video",
                "executionMode": "bounded_existing_or_approved_sample_only",
                "sourceFamily": "promoted_runtime",
                "samplingReason": f"promoted-runtime reference diversity tranche {index + 1}",
            },
            {
                "id": f"soccernet_{soccernet_reserve_ordinal}_bounded_member",
                "executionMode": "bounded_existing_or_approved_sample_only",
                "sourceFamily": "soccernet",
                "samplingReason": f"reserve SoccerNet broadcast candidate tranche {index + 1}",
            },
        ])
    return rows


def _previous_expansion_ids(root: Path, output_dir_name: str) -> set[str]:
    current_output = root / output_dir_name
    ids: set[str] = set()
    for expansion_dir in sorted(root.glob("video_to_analysis_real_video_scaleout_source_sampling_expansion_v*")):
        if expansion_dir == current_output:
            continue
        manifest = load_json(expansion_dir / "expanded_scaleout_candidate_manifest.json")
        for row in (manifest.get("expandedScaleoutCandidates", []) if isinstance(manifest, dict) else []):
            if isinstance(row, dict) and row.get("id"):
                ids.add(str(row["id"]))
    return ids


def _expanded_candidates(root: Path, output_dir_name: str) -> list[dict[str, Any]]:
    used_ids = _previous_expansion_ids(root, output_dir_name)
    return [row for row in _candidate_pool() if row["id"] not in used_ids][:6]


def run_video_to_analysis_real_video_scaleout_source_sampling_expansion(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)
    insufficient_refresh_dir = latest_versioned_dir(
        root,
        "video_to_analysis_real_video_scaleout_plan_refresh",
        DEFAULT_INSUFFICIENT_REFRESH_DIR_NAME,
    )
    insufficient_refresh = load_json(insufficient_refresh_dir / "real_video_scaleout_plan_refresh_summary.json")
    ready = bool(
        isinstance(insufficient_refresh, dict)
        and insufficient_refresh.get("primaryBlocker") == "video_to_analysis_real_video_scaleout_candidate_pool_insufficient"
        and insufficient_refresh.get("roadmapAdvanceAllowed") is True
    )
    candidates = _expanded_candidates(root, output_dir_name) if ready else []
    pool_exhausted = bool(ready and not candidates)
    goal = bool(ready and candidates)
    primary_blocker = None
    next_lever = NEXT_REFRESH
    english = "Source sampling expansion added fresh bounded scaleout candidates."
    if not ready:
        primary_blocker = BLOCKER_INSUFFICIENT_REFRESH_MISSING
        next_lever = NEXT_PLAN_REFRESH
        english = "Candidate-pool-insufficient refresh truth is missing."
    elif pool_exhausted:
        primary_blocker = BLOCKER_SOURCE_SAMPLING_POOL_EXHAUSTED
        next_lever = NEXT_ROADMAP_DIRECTION
        english = "Generated source-sampling pool is exhausted; choose the next roadmap direction."
    manifest = {
        "schemaVersion": "video_to_analysis_real_video_scaleout_source_sampling_expansion_manifest_v1",
        "generatedAt": utc_now_iso(),
        "sourceInsufficientRefreshDir": insufficient_refresh_dir.name,
        "expandedScaleoutCandidates": candidates,
        "expandedScaleoutCandidateCount": len(candidates),
        "generatedSourceSamplingPoolExhausted": pool_exhausted,
        "fullDatasetDownloadAllowed": False,
        "videoDownloadExecuted": False,
        "normalMatchStorageMutationExecuted": False,
        "trainingExecuted": False,
    }
    summary = guarded_summary(
        batch_name="video_to_analysis_real_video_scaleout_source_sampling_expansion",
        goal=goal,
        primary_blocker=primary_blocker,
        next_lever=next_lever,
        english=english,
        attempt_families=[row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        extra={
            "sourceSamplingExpansionReady": goal,
            "sourceInsufficientRefreshDir": insufficient_refresh_dir.name,
            "expandedScaleoutCandidateCount": len(candidates),
            "generatedSourceSamplingPoolExhausted": pool_exhausted,
        },
    )
    if pool_exhausted:
        summary["roadmapAdvanceAllowed"] = True
    return write_outcome(
        output_root=output_root,
        summary_filename="real_video_scaleout_source_sampling_expansion_summary.json",
        summary=summary,
        artifacts={
            "expanded_scaleout_candidate_manifest.json": manifest,
            "decision_matrix.json": {
                "generatedAt": utc_now_iso(),
                "primaryBlocker": summary["primaryBlocker"],
                "nextRecommendedNextLever": summary["nextRecommendedNextLever"],
            },
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Real Video Scaleout Source Sampling Expansion",
    )


def main() -> None:
    main_for("Expand bounded real-video scaleout source sampling.", run_video_to_analysis_real_video_scaleout_source_sampling_expansion)


if __name__ == "__main__":
    main()
