from __future__ import annotations
from backend.scripts.football_external_real_eval_chain_common import write_json_sorted_no_newline as _write_json


from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_SUITE_ROOT = DEFAULT_STORAGE_ROOT / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
DEFAULT_EXPANSION_RESOLUTION_ROOT = DEFAULT_SUITE_ROOT / "manual_review_expansion_resolution_v1"
DEFAULT_REFUTATION_ROOT = DEFAULT_SUITE_ROOT / "gold_truth_seed_refuted_refresh_v1"
DEFAULT_OUTPUT_ROOT = DEFAULT_SUITE_ROOT / "reviewed_positive_proposal_generation_fix_v1"
DEFAULT_BATCH_NAME = "reviewed_positive_proposal_generation_fix_v1"
DEFAULT_ATTEMPT_FAMILY = "reviewed_positive_seed_proposal_windows"


def _load_json_dict(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload




def _safe_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _list_dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _valid_bbox(value: object) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    try:
        x1 = float(value["x1"])
        y1 = float(value["y1"])
        x2 = float(value["x2"])
        y2 = float(value["y2"])
    except (KeyError, TypeError, ValueError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


def _source_center(bbox: dict[str, float]) -> dict[str, float]:
    return {
        "x": round((float(bbox["x1"]) + float(bbox["x2"])) / 2.0, 3),
        "y": round((float(bbox["y1"]) + float(bbox["y2"])) / 2.0, 3),
    }


def _reviewed_positive_anchor_rows(truth_seed: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in _list_dicts(truth_seed.get("reviewedPositiveSeedRows")):
        bbox = _valid_bbox(row.get("reviewedBBox"))
        frame_id = _safe_int(row.get("frameIndex"), -1)
        if bbox is None or frame_id < 0:
            continue
        rows.append(
            {
                "reviewItemId": row.get("reviewItemId"),
                "candidateFrameId": row.get("candidateFrameId"),
                "windowId": row.get("windowId"),
                "sourceClipId": row.get("sourceClipId"),
                "frameIndex": frame_id,
                "timestampSeconds": _safe_float(row.get("timestampSeconds"), 0.0),
                "reviewDecision": row.get("reviewDecision"),
                "reviewedBBox": bbox,
                "sourceCenter": _source_center(bbox),
                "lineage": dict(row.get("lineage") or {}),
                "provenance": {
                    "sourceArtifact": "manual_review_expansion_resolution_v1/expanded_reviewed_truth_seed.json",
                    "sourceTruthUse": row.get("truthUse"),
                    "reviewedBy": row.get("reviewedBy"),
                    "reviewMethod": row.get("reviewMethod"),
                },
                "truthUse": "reviewed_positive_proposal_anchor",
            }
        )
    return sorted(rows, key=lambda item: (_safe_int(item.get("frameIndex"), -1), str(item.get("reviewItemId") or "")))


def _refuted_rows(truth_seed: dict[str, Any], refutation_manifest: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    rows = []
    source_rows = _list_dicts(truth_seed.get("reviewedNegativeSeedRows"))
    if not source_rows and isinstance(refutation_manifest, dict):
        source_rows = _list_dicts(refutation_manifest.get("rejectedSeeds"))
    for row in source_rows:
        rows.append(
            {
                "reviewItemId": row.get("reviewItemId"),
                "candidateFrameId": row.get("candidateFrameId"),
                "sourceClipId": row.get("sourceClipId"),
                "frameIndex": _safe_int(row.get("frameIndex"), -1),
                "reviewDecision": row.get("reviewDecision"),
                "truthUse": "refutation_only",
            }
        )
    return sorted(rows, key=lambda item: (_safe_int(item.get("frameIndex"), -1), str(item.get("reviewItemId") or "")))


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Reviewed Positive Proposal Generation Fix",
            "",
            f"- batchStatus: {summary.get('batchStatus')}",
            f"- reviewedPositiveAnchorFrameCount: {summary.get('reviewedPositiveAnchorFrameCount')}",
            f"- refutedSeedCount: {summary.get('refutedSeedCount')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            "",
        ]
    )


def run_promoted_v6_reviewed_positive_anchor_seed(
    *,
    expansion_resolution_root: Path = DEFAULT_EXPANSION_RESOLUTION_ROOT,
    refutation_root: Path = DEFAULT_REFUTATION_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> dict[str, Any]:
    expansion_resolution_root = Path(expansion_resolution_root)
    refutation_root = Path(refutation_root)
    output_root = Path(output_root)
    truth_seed_path = expansion_resolution_root / "expanded_reviewed_truth_seed.json"
    truth_seed = _load_json_dict(truth_seed_path)
    refutation_manifest_path = refutation_root / "rejected_seed_refutation_manifest.json"
    refutation_manifest = _load_json_dict(refutation_manifest_path) if refutation_manifest_path.exists() else {}
    anchor_rows = _reviewed_positive_anchor_rows(truth_seed)
    refuted_rows = _refuted_rows(truth_seed, refutation_manifest)
    generated_at = _utc_now_iso()
    anchor_seed = {
        "generatedAt": generated_at,
        "truthStatus": "reviewed_positive_anchor_seed",
        "reviewedPositiveAnchorFrameCount": len(anchor_rows),
        "reviewedPositiveAnchorRows": anchor_rows,
        "refutedSeedCount": len(refuted_rows),
        "refutedSeeds": refuted_rows,
    }
    summary = {
        "generatedAt": generated_at,
        "batchName": DEFAULT_BATCH_NAME,
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptApproachFamily": DEFAULT_ATTEMPT_FAMILY,
        "batchStatus": "succeeded" if anchor_rows else "weak_evidence",
        "goalAchieved": bool(anchor_rows),
        "roadmapAdvanceAllowed": bool(anchor_rows),
        "reviewedPositiveAnchorFrameCount": len(anchor_rows),
        "reviewedPositiveAnchorFrames": [int(row["frameIndex"]) for row in anchor_rows],
        "refutedSeedCount": len(refuted_rows),
        "nextCorrectiveFamily": "reviewed_positive_seed_proposal_windows",
        "reviewedPositiveAnchorSeedPath": str(output_root / "reviewed_positive_anchor_seed.json"),
        "runtimeDefaultChanged": False,
        "frozenSourceManifestChanged": False,
    }
    decision = {
        "goalAchieved": summary["goalAchieved"],
        "roadmapAdvanceAllowed": summary["roadmapAdvanceAllowed"],
        "selectedApproach": "A_reviewed_positive_anchor_seed_generation",
        "nextCorrectiveFamily": summary["nextCorrectiveFamily"],
        "rationale": "Reviewed-positive boxes are now available as proposal anchors only.",
    }
    batch_outcome = {
        **summary,
        "decisionMatrix": decision,
    }
    _write_json(output_root / "reviewed_positive_anchor_seed.json", anchor_seed)
    _write_json(output_root / "reviewed_positive_anchor_seed_summary.json", summary)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return {
        "reviewedPositiveAnchorSeed": anchor_seed,
        "reviewedPositiveAnchorSeedSummary": summary,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate reviewed-positive proposal anchor seed artifacts.")
    parser.add_argument("--expansion-resolution-root", default=str(DEFAULT_EXPANSION_RESOLUTION_ROOT))
    parser.add_argument("--refutation-root", default=str(DEFAULT_REFUTATION_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args()
    payload = run_promoted_v6_reviewed_positive_anchor_seed(
        expansion_resolution_root=Path(args.expansion_resolution_root),
        refutation_root=Path(args.refutation_root),
        output_root=Path(args.output_root),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
