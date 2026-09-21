from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
import backend.scripts.run_source_robustness_batch as run_source_robustness_batch  # noqa: E402

DEFAULT_SUITE_ROOT = DEFAULT_STORAGE_ROOT / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
DEFAULT_VALIDATION_ROOT = DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_robustness_validation_v1"
DEFAULT_RETENTION_DELTA_ROOT = (
    DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
)
DEFAULT_ANALYSIS_ROOT = DEFAULT_SUITE_ROOT / "promoted_v6_failing_source_review_refresh_v1"
DEFAULT_FAILING_SOURCE_CLIP_ID = "trimed-5min.mp4"
DEFAULT_ANALYSIS_BATCH_NAME = "promoted_v6_failing_source_review_refresh_v1"

ARM_NAME_BASELINE_CURRENT = "baseline_current"
ARM_NAME_PROMOTED_V6_BASELINE = "promoted_v6_baseline"

BUCKET_NO_SIGNAL = "promoted_no_observed_or_probe_signal"
BUCKET_EDGE_CLEANUP = "edge_cleanup_removed_baseline_edge_signal"
BUCKET_PROPOSAL_NOT_SELECTED = "proposal_signal_present_but_not_selected"
BUCKET_SUPPORT_OR_VIABILITY = "support_or_viability_filter_loss"
BUCKET_TEMPORAL_FRAGMENTATION = "temporal_run_fragmentation"
BUCKET_SELECTED_CLUSTER = "selected_cluster_not_primary"
BUCKET_UNRESOLVED = "unresolved_missing_evidence"

TAXONOMY_BUCKET_ORDER = (
    BUCKET_EDGE_CLEANUP,
    BUCKET_PROPOSAL_NOT_SELECTED,
    BUCKET_SUPPORT_OR_VIABILITY,
    BUCKET_TEMPORAL_FRAGMENTATION,
    BUCKET_NO_SIGNAL,
    BUCKET_SELECTED_CLUSTER,
    BUCKET_UNRESOLVED,
)

NEXT_FIX_FAMILY_BY_BUCKET = {
    BUCKET_EDGE_CLEANUP: "edge_cleanup_truth_refresh",
    BUCKET_PROPOSAL_NOT_SELECTED: "proposal_selection_evidence_refresh",
    BUCKET_SUPPORT_OR_VIABILITY: "support_viability_evidence_refresh",
    BUCKET_TEMPORAL_FRAGMENTATION: "temporal_fragmentation_evidence_refresh",
    BUCKET_NO_SIGNAL: "proposal_signal_generation_evidence_refresh",
    BUCKET_SELECTED_CLUSTER: "selected_cluster_follow_through_fix",
    BUCKET_UNRESOLVED: "manual_review_evidence_refresh",
}

RETENTION_GUARDRAIL = 0.60
EDGE_MARGIN = 3.0
PITCH_MAX = 100.0


def _load_json_dict(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def _rows_from_layer(payload: dict[str, object], layer_name: str) -> list[dict[str, object]]:
    layer = payload.get(layer_name)
    if not isinstance(layer, dict):
        return []
    rows = layer.get("rows")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict) and "Frame_ID" in row]


def _frame_ids_from_layer(payload: dict[str, object], layer_name: str) -> list[int]:
    return sorted({int(row["Frame_ID"]) for row in _rows_from_layer(payload, layer_name)})


def _rows_by_frame(rows: list[dict[str, object]]) -> dict[int, dict[str, object]]:
    by_frame: dict[int, dict[str, object]] = {}
    for row in rows:
        by_frame[int(row["Frame_ID"])] = row
    return by_frame


def _missing_accepted_frames(
    *,
    baseline_truth: dict[str, object],
    promoted_truth: dict[str, object],
) -> list[int]:
    baseline_frames = set(_frame_ids_from_layer(baseline_truth, "acceptedBall"))
    promoted_frames = set(_frame_ids_from_layer(promoted_truth, "acceptedBall"))
    return sorted(baseline_frames - promoted_frames)


def _group_contiguous_frames(frame_ids: list[int], *, sample_interval: int) -> list[dict[str, object]]:
    if not frame_ids:
        return []
    ordered = sorted(int(frame_id) for frame_id in frame_ids)
    windows: list[dict[str, object]] = []
    current = [ordered[0]]
    for frame_id in ordered[1:]:
        if int(frame_id) - int(current[-1]) <= int(sample_interval):
            current.append(frame_id)
            continue
        windows.append(
            {
                "startFrame": int(current[0]),
                "endFrame": int(current[-1]),
                "frameIds": list(current),
                "frameCount": len(current),
            }
        )
        current = [frame_id]
    windows.append(
        {
            "startFrame": int(current[0]),
            "endFrame": int(current[-1]),
            "frameIds": list(current),
            "frameCount": len(current),
        }
    )
    return windows


def _row_is_edge(row: dict[str, object]) -> bool:
    x = _safe_float(row.get("X"), 0.0)
    y = _safe_float(row.get("Y"), 0.0)
    return (
        x <= EDGE_MARGIN
        or x >= (PITCH_MAX - EDGE_MARGIN)
        or y <= EDGE_MARGIN
        or y >= (PITCH_MAX - EDGE_MARGIN)
    )


def _selected_cluster_is_primary(
    *,
    baseline_selected_cluster_delta: dict[str, object],
    promoted_selected_cluster_delta: dict[str, object],
) -> bool:
    baseline_after = (
        dict(baseline_selected_cluster_delta.get("after"))
        if isinstance(baseline_selected_cluster_delta.get("after"), dict)
        else {}
    )
    promoted_before = (
        dict(promoted_selected_cluster_delta.get("before"))
        if isinstance(promoted_selected_cluster_delta.get("before"), dict)
        else {}
    )
    promoted_after = (
        dict(promoted_selected_cluster_delta.get("after"))
        if isinstance(promoted_selected_cluster_delta.get("after"), dict)
        else {}
    )
    baseline_accepted = _safe_int(baseline_after.get("acceptedBallFrames"), 0)
    baseline_controlled = _safe_int(baseline_after.get("controlledPossessionFrames"), 0)
    if baseline_accepted <= 0 or baseline_controlled <= 0:
        return False
    before_accepted_ratio = _safe_int(promoted_before.get("acceptedBallFrames"), 0) / baseline_accepted
    after_controlled_ratio = _safe_int(promoted_after.get("controlledPossessionFrames"), 0) / baseline_controlled
    return before_accepted_ratio >= RETENTION_GUARDRAIL and after_controlled_ratio < RETENTION_GUARDRAIL


def _rejection_counts_from_acquisition(promoted_truth: dict[str, object]) -> dict[str, int]:
    diagnostics = promoted_truth.get("sourceConditionedAcquisitionDiagnostics")
    if not isinstance(diagnostics, dict):
        return {}
    counts: dict[str, int] = {}
    for key in ("edgeStuckCandidateRejectionCounts", "zeroTouchlineCandidateReasonCounts"):
        raw_counts = diagnostics.get(key)
        if not isinstance(raw_counts, dict):
            continue
        for reason, count in raw_counts.items():
            counts[str(reason)] = counts.get(str(reason), 0) + _safe_int(count, 0)
    return counts


def _recovery_has_unselected_proposals(recovery_profile_matrix: dict[str, object]) -> bool:
    profiles = recovery_profile_matrix.get("profiles")
    if not isinstance(profiles, list):
        return False
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        proposal_frames = _safe_int(
            profile.get("proposalCandidateFrames", profile.get("candidateFrames", 0)),
            0,
        )
        selected_frames = _safe_int(profile.get("selectedFrames"), 0)
        if proposal_frames > selected_frames:
            return True
    return False


def _nearest_distance(frame_id: int, frame_ids: list[int]) -> int | None:
    if not frame_ids:
        return None
    return min(abs(int(frame_id) - int(candidate)) for candidate in frame_ids)


def _classify_window(
    *,
    window: dict[str, object],
    baseline_rows_by_frame: dict[int, dict[str, object]],
    promoted_observed_frames: set[int],
    promoted_probe_frames: set[int],
    promoted_accepted_frames: list[int],
    selected_cluster_primary: bool,
    rejection_counts: dict[str, int],
    recovery_has_unselected_proposals: bool,
    sample_interval: int,
) -> tuple[str, list[str]]:
    frame_ids = [int(frame_id) for frame_id in list(window.get("frameIds") or [])]
    if selected_cluster_primary:
        return BUCKET_SELECTED_CLUSTER, ["selected-cluster stage is the first retained evidence boundary"]

    signal_frames = [frame_id for frame_id in frame_ids if frame_id in promoted_observed_frames or frame_id in promoted_probe_frames]
    if signal_frames:
        return BUCKET_PROPOSAL_NOT_SELECTED, [
            f"{len(signal_frames)} missing frames still have promoted observed/probe signal"
        ]

    baseline_rows = [baseline_rows_by_frame[frame_id] for frame_id in frame_ids if frame_id in baseline_rows_by_frame]
    edge_frames = [row for row in baseline_rows if _row_is_edge(row)]
    if baseline_rows and len(edge_frames) / len(baseline_rows) >= 0.5:
        return BUCKET_EDGE_CLEANUP, [
            f"{len(edge_frames)} of {len(baseline_rows)} baseline accepted rows are edge rows"
        ]

    if any("support" in reason or "viability" in reason for reason in rejection_counts):
        return BUCKET_SUPPORT_OR_VIABILITY, [
            "promoted acquisition diagnostics contain support/viability rejection evidence"
        ]

    if recovery_has_unselected_proposals:
        return BUCKET_PROPOSAL_NOT_SELECTED, [
            "recovery profile matrix has proposal candidates that were not selected"
        ]

    if promoted_accepted_frames:
        nearest = min(
            distance
            for frame_id in frame_ids
            for distance in [_nearest_distance(frame_id, promoted_accepted_frames)]
            if distance is not None
        )
        if nearest <= int(sample_interval) * 2:
            return BUCKET_TEMPORAL_FRAGMENTATION, [
                f"nearest promoted accepted frame is {nearest} frames away"
            ]

    if not signal_frames:
        return BUCKET_NO_SIGNAL, ["missing frames have no promoted observed/probe signal"]

    return BUCKET_UNRESOLVED, ["saved evidence did not match a deterministic taxonomy rule"]


def build_missing_accepted_signal_taxonomy(
    *,
    baseline_truth: dict[str, object],
    promoted_truth: dict[str, object],
    baseline_selected_cluster_delta: dict[str, object],
    promoted_selected_cluster_delta: dict[str, object],
    promoted_proof_summary: dict[str, object],
    recovery_profile_matrix: dict[str, object],
    retention_delta_summary: dict[str, object],
    failing_source_clip_id: str = DEFAULT_FAILING_SOURCE_CLIP_ID,
) -> dict[str, object]:
    del promoted_proof_summary
    sample_interval = _safe_int(promoted_truth.get("sampleInterval"), 0) or _safe_int(
        baseline_truth.get("sampleInterval"),
        5,
    )
    missing_frames = _missing_accepted_frames(
        baseline_truth=baseline_truth,
        promoted_truth=promoted_truth,
    )
    windows = _group_contiguous_frames(missing_frames, sample_interval=sample_interval)
    baseline_rows_by_frame = _rows_by_frame(_rows_from_layer(baseline_truth, "acceptedBall"))
    promoted_observed_frames = set(_frame_ids_from_layer(promoted_truth, "observedBall"))
    promoted_probe_frames = set(_frame_ids_from_layer(promoted_truth, "probeObservedBall"))
    promoted_accepted_frames = _frame_ids_from_layer(promoted_truth, "acceptedBall")
    selected_cluster_primary = _selected_cluster_is_primary(
        baseline_selected_cluster_delta=baseline_selected_cluster_delta,
        promoted_selected_cluster_delta=promoted_selected_cluster_delta,
    )
    rejection_counts = _rejection_counts_from_acquisition(promoted_truth)
    has_unselected_proposals = _recovery_has_unselected_proposals(recovery_profile_matrix)

    bucket_counts = {bucket: {"windowCount": 0, "frameCount": 0} for bucket in TAXONOMY_BUCKET_ORDER}
    classified_windows = []
    for window in windows:
        bucket, evidence = _classify_window(
            window=window,
            baseline_rows_by_frame=baseline_rows_by_frame,
            promoted_observed_frames=promoted_observed_frames,
            promoted_probe_frames=promoted_probe_frames,
            promoted_accepted_frames=promoted_accepted_frames,
            selected_cluster_primary=selected_cluster_primary,
            rejection_counts=rejection_counts,
            recovery_has_unselected_proposals=has_unselected_proposals,
            sample_interval=sample_interval,
        )
        frame_count = _safe_int(window.get("frameCount"), 0)
        bucket_counts[bucket]["windowCount"] += 1
        bucket_counts[bucket]["frameCount"] += frame_count
        classified_windows.append(
            {
                **window,
                "taxonomyBucket": bucket,
                "evidence": evidence,
            }
        )

    dominant_bucket = max(
        TAXONOMY_BUCKET_ORDER,
        key=lambda bucket: (
            int(bucket_counts[bucket]["frameCount"]),
            int(bucket_counts[bucket]["windowCount"]),
            -TAXONOMY_BUCKET_ORDER.index(bucket),
        ),
    )
    if int(bucket_counts[dominant_bucket]["frameCount"]) <= 0:
        dominant_bucket = BUCKET_UNRESOLVED

    return {
        "analysisBatchName": DEFAULT_ANALYSIS_BATCH_NAME,
        "failingSourceClipId": failing_source_clip_id,
        "sampleInterval": sample_interval,
        "baselineAcceptedFrameCount": len(_frame_ids_from_layer(baseline_truth, "acceptedBall")),
        "promotedAcceptedFrameCount": len(promoted_accepted_frames),
        "missingAcceptedFrameCount": len(missing_frames),
        "missingAcceptedFrames": missing_frames,
        "windowCount": len(classified_windows),
        "bucketCounts": bucket_counts,
        "windows": classified_windows,
        "dominantBlockerClass": dominant_bucket,
        "nextFixFamily": NEXT_FIX_FAMILY_BY_BUCKET[dominant_bucket],
        "retentionEvidence": {
            "primaryRetentionBlockerClass": retention_delta_summary.get("primaryRetentionBlockerClass"),
            "acceptedRetentionRatio": round(_safe_float(retention_delta_summary.get("acceptedRetentionRatio"), 0.0), 3),
            "controlledRetentionRatio": round(
                _safe_float(retention_delta_summary.get("controlledRetentionRatio"), 0.0),
                3,
            ),
        },
    }


def _find_arm_payload(arm_matrix: dict[str, object], arm_name: str) -> dict[str, object]:
    for arm_payload in arm_matrix.get("arms", []):
        if isinstance(arm_payload, dict) and str(arm_payload.get("armName") or "") == arm_name:
            return dict(arm_payload)
    raise KeyError(f"Could not find arm payload for {arm_name}")


def _find_failing_source_proof_root(
    *,
    validation_root: Path,
    arm_name: str,
    failing_source_clip_id: str,
) -> Path:
    arm_matrix = _load_json_dict(validation_root / "arm_matrix.json")
    arm_payload = _find_arm_payload(arm_matrix, arm_name)
    proof_runs = [dict(run) for run in arm_payload.get("proofRuns", []) if isinstance(run, dict)]
    for proof_run in proof_runs:
        if str(proof_run.get("sourceClipId") or "") != failing_source_clip_id:
            continue
        reused_evidence = dict(proof_run.get("reusedEvidence") or {})
        selected_cluster_delta_path = Path(str(reused_evidence.get("selectedClusterDeltaPath") or "")).expanduser()
        if selected_cluster_delta_path.exists():
            return selected_cluster_delta_path.parent
    raise FileNotFoundError(f"Could not resolve proof root for {arm_name} / {failing_source_clip_id}")


def _load_optional_json_dict(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return _load_json_dict(path)


def _write_batch_outcome_markdown(path: Path, payload: dict[str, object]) -> None:
    text = "\n".join(
        [
            "# Promoted V6 Failing-Source Review Refresh v1",
            "",
            f"- batchGoal: {payload.get('batchGoal')}",
            f"- goalAchieved: {payload.get('goalAchieved')}",
            f"- dominantBlockerClass: {payload.get('dominantBlockerClass')}",
            f"- nextFixFamily: {payload.get('nextFixFamily')}",
            f"- nextRecommendedNextLever: {payload.get('nextRecommendedNextLever')}",
            "",
            "## English Summary",
            "",
            str(payload.get("englishSummary") or ""),
            "",
            "## English Decision",
            "",
            str(payload.get("englishDecision") or ""),
        ]
    )
    _write_text(path, text)


def run_promoted_v6_failing_source_review_refresh(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    validation_root: Path = DEFAULT_VALIDATION_ROOT,
    analysis_root: Path = DEFAULT_ANALYSIS_ROOT,
    retention_delta_root: Path = DEFAULT_RETENTION_DELTA_ROOT,
    baseline_proof_root: Path | None = None,
    promoted_proof_root: Path | None = None,
    failing_source_clip_id: str = DEFAULT_FAILING_SOURCE_CLIP_ID,
) -> dict[str, object]:
    del storage_root
    validation_root = Path(validation_root)
    analysis_root = Path(analysis_root)
    retention_delta_root = Path(retention_delta_root)
    baseline_proof_root = Path(baseline_proof_root) if baseline_proof_root is not None else _find_failing_source_proof_root(
        validation_root=validation_root,
        arm_name=ARM_NAME_BASELINE_CURRENT,
        failing_source_clip_id=failing_source_clip_id,
    )
    promoted_proof_root = Path(promoted_proof_root) if promoted_proof_root is not None else _find_failing_source_proof_root(
        validation_root=validation_root,
        arm_name=ARM_NAME_PROMOTED_V6_BASELINE,
        failing_source_clip_id=failing_source_clip_id,
    )

    baseline_truth = _load_json_dict(baseline_proof_root / "ball_truth_layers.json")
    promoted_truth = _load_json_dict(promoted_proof_root / "ball_truth_layers.json")
    baseline_selected_cluster_delta = _load_json_dict(baseline_proof_root / "selected_cluster_delta.json")
    promoted_selected_cluster_delta = _load_json_dict(promoted_proof_root / "selected_cluster_delta.json")
    promoted_proof_summary = _load_optional_json_dict(promoted_proof_root / "proof_summary.json")
    recovery_profile_matrix = _load_optional_json_dict(promoted_proof_root / "recovery_profile_matrix.json")
    retention_delta_summary = _load_json_dict(retention_delta_root / "retention_delta_summary.json")

    taxonomy = build_missing_accepted_signal_taxonomy(
        baseline_truth=baseline_truth,
        promoted_truth=promoted_truth,
        baseline_selected_cluster_delta=baseline_selected_cluster_delta,
        promoted_selected_cluster_delta=promoted_selected_cluster_delta,
        promoted_proof_summary=promoted_proof_summary,
        recovery_profile_matrix=recovery_profile_matrix,
        retention_delta_summary=retention_delta_summary,
        failing_source_clip_id=failing_source_clip_id,
    )
    generated_at = _utc_now_iso()
    goal_achieved = taxonomy["dominantBlockerClass"] != BUCKET_UNRESOLVED
    summary = {
        "generatedAt": generated_at,
        "analysisBatchName": DEFAULT_ANALYSIS_BATCH_NAME,
        "failingSourceClipId": failing_source_clip_id,
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "dominantBlockerClass": taxonomy["dominantBlockerClass"],
        "nextFixFamily": taxonomy["nextFixFamily"],
        "missingAcceptedFrameCount": taxonomy["missingAcceptedFrameCount"],
        "windowCount": taxonomy["windowCount"],
        "nextRecommendedNextLever": run_source_robustness_batch.RECOMMENDED_NEXT_LEVER_PROMOTE_TOUCHLINE_DETECTOR_CANDIDATE,
        "nextRecommendedBatch": "promoted_v6_source_manifest_and_gold_truth_refresh_v1"
        if goal_achieved
        else DEFAULT_ANALYSIS_BATCH_NAME,
    }
    decision_matrix = {
        "generatedAt": generated_at,
        "analysisBatchName": DEFAULT_ANALYSIS_BATCH_NAME,
        "classificationRules": {
            BUCKET_EDGE_CLEANUP: "missing baseline accepted rows are mostly edge rows absent from promoted v6",
            BUCKET_PROPOSAL_NOT_SELECTED: "promoted observed/probe or proposal evidence exists but did not become accepted signal",
            BUCKET_SUPPORT_OR_VIABILITY: "support or viability rejection diagnostics dominate saved evidence",
            BUCKET_TEMPORAL_FRAGMENTATION: "missing window is adjacent to promoted accepted signal but fragmented",
            BUCKET_NO_SIGNAL: "promoted v6 has no observed/probe signal for the missing baseline window",
            BUCKET_SELECTED_CLUSTER: "accepted signal is adequate before selected-cluster follow-through",
            BUCKET_UNRESOLVED: "saved evidence is insufficient for a sharper blocker class",
        },
        "resolvedDecision": {
            "dominantBlockerClass": taxonomy["dominantBlockerClass"],
            "nextFixFamily": taxonomy["nextFixFamily"],
            "nextRecommendedBatch": summary["nextRecommendedBatch"],
        },
        "bucketCounts": taxonomy["bucketCounts"],
    }
    batch_outcome_analysis = {
        "batchGoal": "Refresh failing-source accepted-signal blocker taxonomy from saved artifacts.",
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "dominantBlockerClass": taxonomy["dominantBlockerClass"],
        "nextFixFamily": taxonomy["nextFixFamily"],
        "nextRecommendedBatch": summary["nextRecommendedBatch"],
        "nextRecommendedNextLever": summary["nextRecommendedNextLever"],
        "englishSummary": (
            f"{DEFAULT_ANALYSIS_BATCH_NAME} classified {taxonomy['missingAcceptedFrameCount']} missing accepted "
            f"frames across {taxonomy['windowCount']} windows; dominant class is {taxonomy['dominantBlockerClass']}."
        ),
        "englishDecision": (
            "Do not spend another detector-side accepted-signal attempt. Move to manifest/gold-truth refresh with this blocker evidence."
            if goal_achieved
            else "Evidence remains weak; repeat review taxonomy refresh before changing detector behavior."
        ),
    }

    frame_window_taxonomy = {
        "generatedAt": generated_at,
        "analysisBatchName": DEFAULT_ANALYSIS_BATCH_NAME,
        "failingSourceClipId": failing_source_clip_id,
        "windows": taxonomy["windows"],
    }
    missing_accepted_signal_taxonomy = {
        "generatedAt": generated_at,
        **taxonomy,
    }

    analysis_root.mkdir(parents=True, exist_ok=True)
    _write_json(analysis_root / "review_refresh_summary.json", summary)
    _write_json(analysis_root / "missing_accepted_signal_taxonomy.json", missing_accepted_signal_taxonomy)
    _write_json(analysis_root / "frame_window_taxonomy.json", frame_window_taxonomy)
    _write_json(analysis_root / "decision_matrix.json", decision_matrix)
    _write_json(analysis_root / "batch_outcome_analysis.json", batch_outcome_analysis)
    _write_batch_outcome_markdown(analysis_root / "batch_outcome_analysis.md", batch_outcome_analysis)
    return {
        **summary,
        "batchOutcomeAnalysis": batch_outcome_analysis,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run promoted-v6 failing-source accepted-signal review refresh from saved artifacts."
    )
    parser.add_argument("--storage-root", default=str(DEFAULT_STORAGE_ROOT))
    parser.add_argument("--validation-root", default=str(DEFAULT_VALIDATION_ROOT))
    parser.add_argument("--analysis-root", default=str(DEFAULT_ANALYSIS_ROOT))
    parser.add_argument("--retention-delta-root", default=str(DEFAULT_RETENTION_DELTA_ROOT))
    parser.add_argument("--baseline-proof-root", default=None)
    parser.add_argument("--promoted-proof-root", default=None)
    parser.add_argument("--failing-source-clip-id", default=DEFAULT_FAILING_SOURCE_CLIP_ID)
    args = parser.parse_args()

    payload = run_promoted_v6_failing_source_review_refresh(
        storage_root=Path(args.storage_root),
        validation_root=Path(args.validation_root),
        analysis_root=Path(args.analysis_root),
        retention_delta_root=Path(args.retention_delta_root),
        baseline_proof_root=Path(args.baseline_proof_root) if args.baseline_proof_root else None,
        promoted_proof_root=Path(args.promoted_proof_root) if args.promoted_proof_root else None,
        failing_source_clip_id=args.failing_source_clip_id,
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
