from __future__ import annotations
from backend.scripts.football_external_real_eval_chain_common import write_json_sorted_no_newline as _write_json


from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_SUITE_ROOT = DEFAULT_STORAGE_ROOT / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
DEFAULT_OUTPUT_ROOT = DEFAULT_SUITE_ROOT / "global_accepted_gap_audit_v1"
DEFAULT_BASELINE_PROOF_ROOT = (
    DEFAULT_STORAGE_ROOT / "pod_cycles" / "yolov10n-pt-baseline-full-detector-baseline-control-20260423195330"
)
DEFAULT_PROMOTED_PROOF_ROOT = (
    DEFAULT_STORAGE_ROOT / "pod_cycles" / "promoted_v6_baseline-trimed-5min.mp4-robustness-validation"
)
DEFAULT_GUARDRAIL_ROOT = DEFAULT_SUITE_ROOT / "accepted_retention_guardrail_audit_v1"
DEFAULT_RETENTION_DELTA_ROOT = (
    DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
)
DEFAULT_REVIEWED_TRUTH_PATH = (
    DEFAULT_SUITE_ROOT / "manual_review_expansion_resolution_v1" / "expanded_reviewed_truth_seed.json"
)
DEFAULT_REFUTED_SEED_PATH = (
    DEFAULT_SUITE_ROOT / "gold_truth_seed_refuted_refresh_v1" / "rejected_seed_refutation_manifest.json"
)

BUCKET_ALREADY_ACCEPTED = "baseline_accepted_already_accepted_in_promoted"
BUCKET_SELECTED_NOT_ACCEPTED = "baseline_accepted_selected_not_accepted"
BUCKET_COLLAPSED_NOT_SELECTED = "baseline_accepted_collapsed_not_selected"
BUCKET_RAW_NOT_COLLAPSED = "baseline_accepted_raw_detected_not_collapsed"
BUCKET_WINDOW_ZERO_RAW = "baseline_accepted_window_generated_zero_raw_detect"
BUCKET_NO_PROPOSAL = "baseline_accepted_no_promoted_proposal"
BUCKET_ARTIFACT_GAP = "baseline_accepted_artifact_gap"


def _load_json_dict(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _load_optional_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _load_json_dict(path)




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


def _frame_id(row: dict[str, Any]) -> int | None:
    for key in ("Frame_ID", "frameIndex", "frameId", "frame"):
        if key in row:
            frame_id = _safe_int(row.get(key), -1)
            if frame_id >= 0:
                return frame_id
    return None


def _truth_rows_by_frame(ball_truth_layers: dict[str, Any], layer_name: str = "acceptedBall") -> dict[int, dict[str, Any]]:
    layer = ball_truth_layers.get(layer_name)
    if not isinstance(layer, dict):
        return {}
    rows: dict[int, dict[str, Any]] = {}
    for row in _list_dicts(layer.get("rows")):
        frame_id = _frame_id(row)
        if frame_id is not None:
            rows[frame_id] = row
    return rows


def _selected_profile(recovery_profile_matrix: dict[str, Any]) -> dict[str, Any]:
    selected_name = str(recovery_profile_matrix.get("selectedProfileName") or "")
    profiles = _list_dicts(recovery_profile_matrix.get("profiles"))
    for profile in profiles:
        if selected_name and profile.get("name") == selected_name:
            return profile
    for profile in profiles:
        if profile.get("name") == "proposal_windows_075":
            return profile
    return profiles[-1] if profiles else {}


def _diagnostics_by_frame(profile: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    for row in _list_dicts(profile.get("proposalFrameDiagnostics")):
        frame_id = _frame_id(row)
        if frame_id is not None:
            rows[frame_id] = row
    return rows


def _int_set(value: object) -> set[int]:
    if not isinstance(value, list):
        return set()
    return {_safe_int(item, -1) for item in value if _safe_int(item, -1) >= 0}


def _review_truth_sets(reviewed_truth: dict[str, Any], refuted_seed: dict[str, Any]) -> tuple[set[int], set[int]]:
    reviewed_positive = {
        _safe_int(row.get("frameIndex"), -1)
        for row in _list_dicts(reviewed_truth.get("reviewedPositiveSeedRows"))
        if _safe_int(row.get("frameIndex"), -1) >= 0
    }
    refuted = {
        _safe_int(row.get("frameIndex"), -1)
        for row in _list_dicts(refuted_seed.get("rejectedSeeds"))
        if _safe_int(row.get("frameIndex"), -1) >= 0
    }
    return reviewed_positive, refuted


def _review_truth_class(frame_id: int, reviewed_positive: set[int], refuted: set[int]) -> str:
    if frame_id in reviewed_positive and frame_id in refuted:
        return "reviewed_positive_with_refuted_seed_context"
    if frame_id in reviewed_positive:
        return "reviewed_positive"
    if frame_id in refuted:
        return "refuted_bootstrap_seed"
    return "unreviewed"


def _classify_frame(
    *,
    frame_id: int,
    promoted_accepted: set[int],
    raw_frames: set[int],
    collapsed_frames: set[int],
    selected_frames: set[int],
    diagnostics_by_frame: dict[int, dict[str, Any]],
) -> str:
    if frame_id in promoted_accepted:
        return BUCKET_ALREADY_ACCEPTED
    if frame_id in selected_frames:
        return BUCKET_SELECTED_NOT_ACCEPTED
    if frame_id in collapsed_frames:
        return BUCKET_COLLAPSED_NOT_SELECTED
    if frame_id in raw_frames:
        return BUCKET_RAW_NOT_COLLAPSED
    diagnostic = diagnostics_by_frame.get(frame_id)
    if isinstance(diagnostic, dict) and bool(diagnostic.get("proposalGenerated")):
        return BUCKET_WINDOW_ZERO_RAW
    if diagnostic is None:
        return BUCKET_NO_PROPOSAL
    return BUCKET_ARTIFACT_GAP


def _dominant_gap(counts: Counter[str]) -> tuple[str, int]:
    if not counts:
        return BUCKET_ARTIFACT_GAP, 0
    priority = {
        BUCKET_NO_PROPOSAL: 0,
        BUCKET_WINDOW_ZERO_RAW: 1,
        BUCKET_RAW_NOT_COLLAPSED: 2,
        BUCKET_COLLAPSED_NOT_SELECTED: 3,
        BUCKET_SELECTED_NOT_ACCEPTED: 4,
        BUCKET_ALREADY_ACCEPTED: 5,
        BUCKET_ARTIFACT_GAP: 6,
    }
    return sorted(counts.items(), key=lambda item: (-item[1], priority.get(item[0], 99), item[0]))[0]


def _next_family(*, dominant: str, reachable_count: int, refuted_only_count: int, missing_count: int) -> str:
    if reachable_count > 0:
        return "global_reachable_acceptance_probe"
    if refuted_only_count >= max(1, missing_count // 2):
        return "baseline_denominator_review_refresh"
    if dominant in {BUCKET_NO_PROPOSAL, BUCKET_WINDOW_ZERO_RAW}:
        return "reviewed_positive_training_data_lane"
    return "v7_training_data_lane"


def _baseline_row_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "timestamp": row.get("Timestamp"),
        "x": row.get("X"),
        "y": row.get("Y"),
        "confidence": row.get("Conf"),
        "sourceBBox": {
            "x1": row.get("Source_X1"),
            "y1": row.get("Source_Y1"),
            "x2": row.get("Source_X2"),
            "y2": row.get("Source_Y2"),
        },
        "proposalInferenceMode": row.get("ProposalInferenceMode"),
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Global Accepted Gap Audit",
            "",
            f"- batchStatus: {summary.get('batchStatus')}",
            f"- baselineAcceptedFrameCount: {summary.get('baselineAcceptedFrameCount')}",
            f"- promotedAcceptedFrameCount: {summary.get('promotedAcceptedFrameCount')}",
            f"- overlappingAcceptedFrameCount: {summary.get('overlappingAcceptedFrameCount')}",
            f"- missingBaselineAcceptedFrameCount: {summary.get('missingBaselineAcceptedFrameCount')}",
            f"- dominantGapClass: {summary.get('dominantGapClass')}",
            f"- reachableFrameCount: {summary.get('reachableFrameCount')}",
            f"- refutedOnlyMissingFrameCount: {summary.get('refutedOnlyMissingFrameCount')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            "",
        ]
    )


def run_promoted_v6_global_accepted_gap_audit(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    baseline_proof_root: Path = DEFAULT_BASELINE_PROOF_ROOT,
    promoted_proof_root: Path = DEFAULT_PROMOTED_PROOF_ROOT,
    guardrail_root: Path = DEFAULT_GUARDRAIL_ROOT,
    retention_delta_root: Path = DEFAULT_RETENTION_DELTA_ROOT,
    reviewed_truth_path: Path = DEFAULT_REVIEWED_TRUTH_PATH,
    refuted_seed_path: Path = DEFAULT_REFUTED_SEED_PATH,
) -> dict[str, Any]:
    output_root = Path(output_root)
    baseline_layers = _load_json_dict(Path(baseline_proof_root) / "ball_truth_layers.json")
    promoted_layers = _load_json_dict(Path(promoted_proof_root) / "ball_truth_layers.json")
    recovery_profile_matrix = _load_json_dict(Path(promoted_proof_root) / "recovery_profile_matrix.json")
    promoted_proof_summary = _load_optional_json_dict(Path(promoted_proof_root) / "proof_summary.json")
    baseline_proof_summary = _load_optional_json_dict(Path(baseline_proof_root) / "proof_summary.json")
    guardrail_summary = _load_optional_json_dict(Path(guardrail_root) / "accepted_retention_guardrail_summary.json")
    retention_summary = _load_optional_json_dict(Path(retention_delta_root) / "retention_delta_summary.json")
    reviewed_truth = _load_optional_json_dict(Path(reviewed_truth_path))
    refuted_seed = _load_optional_json_dict(Path(refuted_seed_path))

    baseline_accepted_rows = _truth_rows_by_frame(baseline_layers)
    promoted_accepted_rows = _truth_rows_by_frame(promoted_layers)
    baseline_frames = set(baseline_accepted_rows)
    promoted_frames = set(promoted_accepted_rows)
    profile = _selected_profile(recovery_profile_matrix)
    diagnostics = _diagnostics_by_frame(profile)
    raw_frames = _int_set(profile.get("proposalRawDetectedFrameIds"))
    collapsed_frames = _int_set(profile.get("proposalCollapsedFrameIds"))
    selected_frames = _int_set(profile.get("proposalSelectedFrameIds"))
    reviewed_positive, refuted = _review_truth_sets(reviewed_truth, refuted_seed)

    frame_rows: list[dict[str, Any]] = []
    for frame_id in sorted(baseline_frames):
        gap_class = _classify_frame(
            frame_id=frame_id,
            promoted_accepted=promoted_frames,
            raw_frames=raw_frames,
            collapsed_frames=collapsed_frames,
            selected_frames=selected_frames,
            diagnostics_by_frame=diagnostics,
        )
        diagnostic = diagnostics.get(frame_id, {})
        review_class = _review_truth_class(frame_id, reviewed_positive, refuted)
        missing = gap_class != BUCKET_ALREADY_ACCEPTED
        frame_rows.append(
            {
                "frameIndex": frame_id,
                "missingFromPromotedAccepted": missing,
                "gapClass": gap_class,
                "reviewTruthClass": review_class,
                "baselineAccepted": True,
                "promotedAccepted": frame_id in promoted_frames,
                "promotedRawDetected": frame_id in raw_frames,
                "promotedCollapsed": frame_id in collapsed_frames,
                "promotedSelected": frame_id in selected_frames,
                "baselineRow": _baseline_row_summary(baseline_accepted_rows[frame_id]),
                "proposalWindowKinds": list(diagnostic.get("proposalWindowKinds") or []),
                "selectionGateTrace": dict(diagnostic.get("selectionGateTrace") or {}),
                "acceptanceGateTrace": dict(diagnostic.get("acceptanceGateTrace") or {}),
            }
        )

    missing_rows = [row for row in frame_rows if bool(row["missingFromPromotedAccepted"])]
    gap_counts = Counter(str(row["gapClass"]) for row in missing_rows)
    review_counts = Counter(str(row["reviewTruthClass"]) for row in missing_rows)
    dominant, dominant_count = _dominant_gap(gap_counts)
    reachable_rows = [
        row
        for row in missing_rows
        if row["gapClass"] in {BUCKET_RAW_NOT_COLLAPSED, BUCKET_COLLAPSED_NOT_SELECTED, BUCKET_SELECTED_NOT_ACCEPTED}
        and row["reviewTruthClass"] != "refuted_bootstrap_seed"
    ]
    refuted_only_count = sum(1 for row in missing_rows if row["reviewTruthClass"] == "refuted_bootstrap_seed")
    next_family = _next_family(
        dominant=dominant,
        reachable_count=len(reachable_rows),
        refuted_only_count=refuted_only_count,
        missing_count=len(missing_rows),
    )
    generated_at = _utc_now_iso()
    summary = {
        "generatedAt": generated_at,
        "batchName": "global_accepted_gap_audit",
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptApproachFamily": "accepted_gap_manifest_refresh",
        "batchStatus": "succeeded" if frame_rows else "needs_next_attempt",
        "goalAchieved": bool(frame_rows),
        "roadmapAdvanceAllowed": bool(frame_rows),
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
        "baselineAcceptedFrameCount": len(baseline_frames),
        "promotedAcceptedFrameCount": len(promoted_frames),
        "overlappingAcceptedFrameCount": len(baseline_frames & promoted_frames),
        "missingBaselineAcceptedFrameCount": len(missing_rows),
        "dominantGapClass": dominant,
        "dominantGapFrameCount": dominant_count,
        "gapClassCounts": dict(sorted(gap_counts.items())),
        "reviewTruthClassCounts": dict(sorted(review_counts.items())),
        "reachableFrameCount": len(reachable_rows),
        "reachableFrameIds": [int(row["frameIndex"]) for row in reachable_rows],
        "refutedOnlyMissingFrameCount": refuted_only_count,
        "acceptedRetentionGuardrailTruth": {
            "bestRetentionArmName": guardrail_summary.get("bestRetentionArmName"),
            "bestAcceptedRetentionRatio": guardrail_summary.get("bestAcceptedRetentionRatio"),
            "bestControlledRetentionRatio": guardrail_summary.get("bestControlledRetentionRatio"),
            "acceptedFramesShortOfGuardrail": guardrail_summary.get("acceptedFramesShortOfGuardrail"),
            "controlledFramesShortOfGuardrail": guardrail_summary.get("controlledFramesShortOfGuardrail"),
        },
        "proofTruth": {
            "baselineAcceptedBallFrames": baseline_proof_summary.get("acceptedBallFrames"),
            "promotedAcceptedBallFrames": promoted_proof_summary.get("acceptedBallFrames"),
            "promotedBestProposalRawDetectedFrames": promoted_proof_summary.get("bestProposalRawDetectedFrames"),
            "promotedBestProposalAfterSeedCollapseFrames": promoted_proof_summary.get(
                "bestProposalAfterSeedCollapseFrames"
            ),
            "promotedBestProposalSelectedFrames": promoted_proof_summary.get("bestProposalSelectedFrames"),
            "selectedProfileName": profile.get("name"),
        },
        "retentionTruth": {
            "acceptedRetentionRatio": retention_summary.get("acceptedRetentionRatio"),
            "controlledRetentionRatio": retention_summary.get("controlledRetentionRatio"),
            "primaryRetentionBlockerClass": retention_summary.get("primaryRetentionBlockerClass"),
        },
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
    }
    taxonomy = {
        "generatedAt": generated_at,
        "gapClassCounts": summary["gapClassCounts"],
        "reviewTruthClassCounts": summary["reviewTruthClassCounts"],
        "dominantGapClass": dominant,
        "dominantGapFrameCount": dominant_count,
        "taxonomyDefinitions": {
            BUCKET_NO_PROPOSAL: "Baseline accepted frame has no promoted proposal-frame diagnostic or raw hit.",
            BUCKET_WINDOW_ZERO_RAW: "Promoted proof created a window but detector produced no raw hit.",
            BUCKET_RAW_NOT_COLLAPSED: "Promoted proof saw raw detection but it did not survive collapse.",
            BUCKET_COLLAPSED_NOT_SELECTED: "Promoted proof collapsed a candidate but did not select it.",
            BUCKET_SELECTED_NOT_ACCEPTED: "Promoted proof selected a row but it did not enter accepted truth.",
            BUCKET_ALREADY_ACCEPTED: "Baseline accepted frame is also accepted by promoted proof.",
        },
    }
    reachable_manifest = {
        "generatedAt": generated_at,
        "reachableFrameCount": len(reachable_rows),
        "reachableFrames": reachable_rows,
        "nextAttemptCandidate": "reachable_global_acceptance_probe" if reachable_rows else None,
    }
    decision = {
        "goalAchieved": summary["goalAchieved"],
        "roadmapAdvanceAllowed": summary["roadmapAdvanceAllowed"],
        "dominantBlockerClass": dominant,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        "runtimeDefaultChanged": False,
        "rationale": (
            "The best promoted proof accepts zero of the baseline-accepted frame IDs; most missing frames have "
            "no promoted proposal evidence, so the next step must audit global proposal/generation coverage."
            if dominant == BUCKET_NO_PROPOSAL
            else "The global accepted gap has reachable promoted evidence worth probing before runtime validation."
        ),
    }
    batch_outcome = {
        **summary,
        "acceptedGapClassTaxonomy": taxonomy,
        "decisionMatrix": decision,
    }

    _write_json(output_root / "global_accepted_gap_summary.json", summary)
    _write_json(output_root / "accepted_gap_frame_manifest.json", {"generatedAt": generated_at, "frames": frame_rows})
    _write_json(output_root / "accepted_gap_class_taxonomy.json", taxonomy)
    _write_json(output_root / "reachable_global_acceptance_manifest.json", reachable_manifest)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return {
        "summary": summary,
        "acceptedGapFrameManifest": {"frames": frame_rows},
        "acceptedGapClassTaxonomy": taxonomy,
        "reachableGlobalAcceptanceManifest": reachable_manifest,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--baseline-proof-root", type=Path, default=DEFAULT_BASELINE_PROOF_ROOT)
    parser.add_argument("--promoted-proof-root", type=Path, default=DEFAULT_PROMOTED_PROOF_ROOT)
    parser.add_argument("--guardrail-root", type=Path, default=DEFAULT_GUARDRAIL_ROOT)
    parser.add_argument("--retention-delta-root", type=Path, default=DEFAULT_RETENTION_DELTA_ROOT)
    parser.add_argument("--reviewed-truth-path", type=Path, default=DEFAULT_REVIEWED_TRUTH_PATH)
    parser.add_argument("--refuted-seed-path", type=Path, default=DEFAULT_REFUTED_SEED_PATH)
    args = parser.parse_args()
    payload = run_promoted_v6_global_accepted_gap_audit(
        output_root=args.output_root,
        baseline_proof_root=args.baseline_proof_root,
        promoted_proof_root=args.promoted_proof_root,
        guardrail_root=args.guardrail_root,
        retention_delta_root=args.retention_delta_root,
        reviewed_truth_path=args.reviewed_truth_path,
        refuted_seed_path=args.refuted_seed_path,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
