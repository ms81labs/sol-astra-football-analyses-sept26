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
DEFAULT_OUTPUT_ROOT = DEFAULT_SUITE_ROOT / "global_reachable_acceptance_probe_v1"
DEFAULT_GLOBAL_GAP_ROOT = DEFAULT_SUITE_ROOT / "global_accepted_gap_audit_v1"
DEFAULT_PROMOTED_PROOF_ROOT = (
    DEFAULT_STORAGE_ROOT / "pod_cycles" / "promoted_v6_baseline-trimed-5min.mp4-robustness-validation"
)
DEFAULT_RETENTION_DELTA_ROOT = (
    DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
)

BUCKET_PROFILE_RANKING = "global_reachable_selected_profile_ranking_rejected"
BUCKET_SEGMENT_LENGTH = "global_reachable_segment_length_rejected"
BUCKET_EDGE_SHARE = "global_reachable_edge_share_rejected"
BUCKET_CONTINUITY = "global_reachable_continuity_rejected"
BUCKET_REPEATED_ANCHOR = "global_reachable_repeated_anchor_rejected"
BUCKET_SELECTED_NOT_ACCEPTED = "global_reachable_selected_not_accepted"
BUCKET_ACCEPTED = "global_reachable_already_accepted"
BUCKET_ARTIFACT_GAP = "global_reachable_selection_artifact_gap"

PROFILE_NAME = "source_robustness_shadow_promoted_v6_global_reachable_acceptance_probe_v1"


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


def _list_dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _frame_id(row: dict[str, Any]) -> int | None:
    for key in ("frameIndex", "Frame_ID", "frameId", "frame"):
        if key in row:
            frame_id = _safe_int(row.get(key), -1)
            if frame_id >= 0:
                return frame_id
    return None


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


def _accepted_frames(ball_truth_layers: dict[str, Any]) -> set[int]:
    layer = ball_truth_layers.get("acceptedBall")
    if not isinstance(layer, dict):
        return set()
    frames: set[int] = set()
    for row in _list_dicts(layer.get("rows")):
        frame_id = _frame_id(row)
        if frame_id is not None:
            frames.add(frame_id)
    return frames


def _reachable_frame_ids(global_gap_manifest: dict[str, Any]) -> list[int]:
    rows = _list_dicts(global_gap_manifest.get("frames"))
    frame_ids = [
        _safe_int(row.get("frameIndex"), -1)
        for row in rows
        if row.get("gapClass") == "baseline_accepted_collapsed_not_selected"
    ]
    frame_ids = [frame_id for frame_id in frame_ids if frame_id >= 0]
    if frame_ids:
        return sorted(frame_ids)
    recovered_frame_ids = [
        _safe_int(row.get("frameIndex"), -1)
        for row in rows
        if row.get("gapClass") == "baseline_accepted_already_accepted_in_promoted"
    ]
    return sorted(frame_id for frame_id in recovered_frame_ids if frame_id >= 0)


def _classify_diagnostic(diagnostic: dict[str, Any], accepted_frames: set[int]) -> str:
    frame_id = _safe_int(diagnostic.get("frameIndex"), -1)
    if frame_id in accepted_frames or bool(diagnostic.get("accepted")):
        return BUCKET_ACCEPTED
    if bool(diagnostic.get("selected")):
        return BUCKET_SELECTED_NOT_ACCEPTED
    trace = diagnostic.get("selectionGateTrace")
    if not isinstance(trace, dict) or not trace:
        return BUCKET_ARTIFACT_GAP
    if bool(trace.get("selectedProfileRankingRejected")):
        return BUCKET_PROFILE_RANKING
    if bool(trace.get("segmentLengthRejected")):
        return BUCKET_SEGMENT_LENGTH
    if bool(trace.get("edgeShareRejected")):
        return BUCKET_EDGE_SHARE
    if bool(trace.get("continuityRejected")):
        return BUCKET_CONTINUITY
    if bool(trace.get("repeatedAnchorRejected")):
        return BUCKET_REPEATED_ANCHOR
    return BUCKET_ARTIFACT_GAP


def _dominant(counts: Counter[str]) -> tuple[str, int]:
    if not counts:
        return BUCKET_ARTIFACT_GAP, 0
    priority = {
        BUCKET_PROFILE_RANKING: 0,
        BUCKET_SEGMENT_LENGTH: 1,
        BUCKET_EDGE_SHARE: 2,
        BUCKET_CONTINUITY: 3,
        BUCKET_REPEATED_ANCHOR: 4,
        BUCKET_SELECTED_NOT_ACCEPTED: 5,
        BUCKET_ACCEPTED: 6,
        BUCKET_ARTIFACT_GAP: 7,
    }
    return sorted(counts.items(), key=lambda item: (-item[1], priority.get(item[0], 99), item[0]))[0]


def _next_family(dominant: str, *, accepted_count: int, selected_count: int) -> str:
    if accepted_count > 0:
        return "accepted_retention_delta_refresh"
    if selected_count > 0:
        return "global_reachable_acceptance_profile"
    if dominant == BUCKET_PROFILE_RANKING:
        return "global_reachable_selection_profile"
    if dominant == BUCKET_ARTIFACT_GAP:
        return "proof_selection_gate_trace_refresh"
    return "baseline_denominator_review_refresh"


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Global Reachable Acceptance Probe",
            "",
            f"- batchStatus: {summary.get('batchStatus')}",
            f"- reachableFrameIds: {summary.get('reachableFrameIds')}",
            f"- selectedFrameCount: {summary.get('selectedFrameCount')}",
            f"- acceptedFrameCount: {summary.get('acceptedFrameCount')}",
            f"- dominantBlockerClass: {summary.get('dominantBlockerClass')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            "",
        ]
    )


def run_promoted_v6_global_reachable_acceptance_probe(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    global_gap_root: Path = DEFAULT_GLOBAL_GAP_ROOT,
    promoted_proof_root: Path = DEFAULT_PROMOTED_PROOF_ROOT,
    retention_delta_root: Path = DEFAULT_RETENTION_DELTA_ROOT,
    attempt_number: int = 1,
    attempt_approach_family: str = "reachable_collapsed_selection_trace",
) -> dict[str, Any]:
    output_root = Path(output_root)
    global_gap_manifest = _load_json_dict(Path(global_gap_root) / "accepted_gap_frame_manifest.json")
    recovery_profile_matrix = _load_json_dict(Path(promoted_proof_root) / "recovery_profile_matrix.json")
    ball_truth_layers = _load_json_dict(Path(promoted_proof_root) / "ball_truth_layers.json")
    proof_summary = _load_optional_json_dict(Path(promoted_proof_root) / "proof_summary.json")
    retention_summary = _load_optional_json_dict(Path(retention_delta_root) / "retention_delta_summary.json")

    profile = _selected_profile(recovery_profile_matrix)
    diagnostics = _diagnostics_by_frame(profile)
    accepted_frames = _accepted_frames(ball_truth_layers)
    reachable_ids = _reachable_frame_ids(global_gap_manifest)
    frame_rows: list[dict[str, Any]] = []
    for frame_id in reachable_ids:
        diagnostic = dict(diagnostics.get(frame_id) or {"frameIndex": frame_id})
        gap_class = _classify_diagnostic(diagnostic, accepted_frames)
        trace = diagnostic.get("selectionGateTrace") if isinstance(diagnostic.get("selectionGateTrace"), dict) else {}
        frame_rows.append(
            {
                "frameIndex": frame_id,
                "proposalGenerated": bool(diagnostic.get("proposalGenerated")),
                "rawDetected": bool(diagnostic.get("rawDetected")),
                "collapsed": bool(diagnostic.get("collapsed")),
                "selected": bool(diagnostic.get("selected")),
                "accepted": frame_id in accepted_frames or bool(diagnostic.get("accepted")),
                "gapClass": gap_class,
                "proposalWindowKinds": list(diagnostic.get("proposalWindowKinds") or []),
                "selectionGateTrace": dict(trace),
                "acceptanceGateTrace": dict(diagnostic.get("acceptanceGateTrace") or {}),
            }
        )

    counts = Counter(str(row["gapClass"]) for row in frame_rows)
    dominant, dominant_count = _dominant(counts)
    selected_count = sum(1 for row in frame_rows if bool(row.get("selected")))
    accepted_count = sum(1 for row in frame_rows if bool(row.get("accepted")))
    next_family = _next_family(dominant, accepted_count=accepted_count, selected_count=selected_count)
    generated_at = _utc_now_iso()
    summary = {
        "generatedAt": generated_at,
        "batchName": "global_reachable_acceptance_probe",
        "attemptNumber": int(attempt_number),
        "attemptBudget": 3,
        "attemptApproachFamily": str(attempt_approach_family),
        "batchStatus": "succeeded" if frame_rows else "needs_next_attempt",
        "goalAchieved": bool(frame_rows),
        "roadmapAdvanceAllowed": bool(frame_rows),
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
        "reachableFrameIds": reachable_ids,
        "reachableFrameCount": len(reachable_ids),
        "classifiedFrameCount": len(frame_rows),
        "selectedFrameCount": selected_count,
        "acceptedFrameCount": accepted_count,
        "dominantBlockerClass": dominant,
        "dominantBlockerFrameCount": dominant_count,
        "gapClassCounts": dict(sorted(counts.items())),
        "proofTruth": {
            "acceptedBallFrames": proof_summary.get("acceptedBallFrames"),
            "bestProposalRawDetectedFrames": proof_summary.get("bestProposalRawDetectedFrames"),
            "bestProposalAfterSeedCollapseFrames": proof_summary.get("bestProposalAfterSeedCollapseFrames"),
            "bestProposalSelectedFrames": proof_summary.get("bestProposalSelectedFrames"),
            "selectedProfileName": profile.get("name"),
        },
        "retentionTruth": {
            "acceptedRetentionRatio": retention_summary.get("acceptedRetentionRatio"),
            "controlledRetentionRatio": retention_summary.get("controlledRetentionRatio"),
            "primaryRetentionBlockerClass": retention_summary.get("primaryRetentionBlockerClass"),
        },
        "profileCandidate": PROFILE_NAME if next_family == "global_reachable_selection_profile" else None,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
    }
    trace_artifact = {
        "generatedAt": generated_at,
        "reachableFrameIds": reachable_ids,
        "frameGateTrace": frame_rows,
        "dominantBlockerClass": dominant,
        "dominantBlockerFrameCount": dominant_count,
        "gapClassCounts": summary["gapClassCounts"],
    }
    decision = {
        "goalAchieved": summary["goalAchieved"],
        "roadmapAdvanceAllowed": summary["roadmapAdvanceAllowed"],
        "dominantBlockerClass": dominant,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        "profileCandidate": summary["profileCandidate"],
        "runtimeDefaultChanged": False,
        "rationale": (
            "Reachable baseline-accepted frames are collapsed but discarded by selected-profile ranking."
            if dominant == BUCKET_PROFILE_RANKING
            else "Reachable frame trace does not currently justify a selected-profile ranking probe."
        ),
    }
    batch_outcome = {
        **summary,
        "frameGateTrace": trace_artifact,
        "decisionMatrix": decision,
    }
    _write_json(output_root / "global_reachable_acceptance_summary.json", summary)
    _write_json(output_root / "global_reachable_frame_gate_trace.json", trace_artifact)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return {
        "summary": summary,
        "globalReachableFrameGateTrace": trace_artifact,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--global-gap-root", type=Path, default=DEFAULT_GLOBAL_GAP_ROOT)
    parser.add_argument("--promoted-proof-root", type=Path, default=DEFAULT_PROMOTED_PROOF_ROOT)
    parser.add_argument("--retention-delta-root", type=Path, default=DEFAULT_RETENTION_DELTA_ROOT)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="reachable_collapsed_selection_trace")
    args = parser.parse_args()
    payload = run_promoted_v6_global_reachable_acceptance_probe(
        output_root=args.output_root,
        global_gap_root=args.global_gap_root,
        promoted_proof_root=args.promoted_proof_root,
        retention_delta_root=args.retention_delta_root,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
