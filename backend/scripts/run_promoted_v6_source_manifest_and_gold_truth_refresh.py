from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_SUITE_ROOT = DEFAULT_STORAGE_ROOT / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
DEFAULT_ANALYSIS_ROOT = DEFAULT_SUITE_ROOT / "promoted_v6_source_manifest_and_gold_truth_refresh_v1"
DEFAULT_REVIEW_REFRESH_ROOT = DEFAULT_SUITE_ROOT / "promoted_v6_failing_source_review_refresh_v1"
DEFAULT_VALIDATION_ROOT = DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_robustness_validation_v1"
DEFAULT_RETENTION_DELTA_ROOT = (
    DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
)
DEFAULT_SOURCE_MANIFEST_PATH = REPO_ROOT / "backend" / "benchmark_suites" / "frozen_viable_baseline_source_manifest.json"
DEFAULT_FAILING_SOURCE_CLIP_ID = "trimed-5min.mp4"
DEFAULT_BATCH_NAME = "promoted_v6_source_manifest_and_gold_truth_refresh_v1"
DEFAULT_REVIEW_BATCH_NAME = "promoted_v6_failing_source_review_refresh_v1"
DEFAULT_WINDOW_PADDING_FRAMES = 10
DEFAULT_BOOTSTRAP_WINDOW_COUNT = 5
MIN_SUCCESS_WINDOW_COUNT = 3
MIN_SUCCESS_BOOTSTRAP_FRAME_COUNT = 50

ARM_NAME_BASELINE_CURRENT = "baseline_current"
ARM_NAME_PROMOTED_V6_BASELINE = "promoted_v6_baseline"

BUCKET_PROPOSAL_NOT_SELECTED = "proposal_signal_present_but_not_selected"
NEXT_ATTEMPT_FAMILY_SUCCESS = "gold_truth_bootstrap"


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


def _manifest_entries(source_manifest: dict[str, object]) -> list[dict[str, object]]:
    entries = source_manifest.get("entries")
    if not isinstance(entries, list):
        return []
    return [dict(entry) for entry in entries if isinstance(entry, dict)]


def _find_source_entry(
    *,
    source_manifest: dict[str, object],
    failing_source_clip_id: str,
) -> dict[str, object]:
    for entry in _manifest_entries(source_manifest):
        if str(entry.get("clipId") or "") == failing_source_clip_id:
            return entry
    return {
        "clipId": failing_source_clip_id,
        "localPath": None,
        "enabled": None,
        "label": failing_source_clip_id,
    }


def _path_or_none(value: object) -> str | None:
    if value is None:
        return None
    raw_value = str(value)
    if not raw_value:
        return None
    return raw_value


def _arm_proof_reference(
    *,
    arm_matrix: dict[str, object],
    arm_name: str,
    failing_source_clip_id: str,
) -> dict[str, object]:
    arms = arm_matrix.get("arms")
    if not isinstance(arms, list):
        return {
            "armName": arm_name,
            "sourceClipId": failing_source_clip_id,
            "proofRoot": None,
            "selectedClusterDeltaPath": None,
            "ballTruthLayersPath": None,
        }
    for arm in arms:
        if not isinstance(arm, dict) or str(arm.get("armName") or "") != arm_name:
            continue
        proof_runs = arm.get("proofRuns")
        if not isinstance(proof_runs, list):
            continue
        for proof_run in proof_runs:
            if not isinstance(proof_run, dict):
                continue
            if str(proof_run.get("sourceClipId") or "") != failing_source_clip_id:
                continue
            reused_evidence = proof_run.get("reusedEvidence")
            if not isinstance(reused_evidence, dict):
                reused_evidence = {}
            selected_cluster_delta_path = _path_or_none(reused_evidence.get("selectedClusterDeltaPath"))
            proof_root = None
            ball_truth_layers_path = None
            if selected_cluster_delta_path:
                proof_root = str(Path(selected_cluster_delta_path).expanduser().parent)
                ball_truth_layers_path = str(Path(proof_root) / "ball_truth_layers.json")
            return {
                "armName": arm_name,
                "sourceClipId": failing_source_clip_id,
                "proofRoot": proof_root,
                "selectedClusterDeltaPath": selected_cluster_delta_path,
                "ballTruthLayersPath": ball_truth_layers_path,
            }
    return {
        "armName": arm_name,
        "sourceClipId": failing_source_clip_id,
        "proofRoot": None,
        "selectedClusterDeltaPath": None,
        "ballTruthLayersPath": None,
    }


def _proof_references(
    *,
    validation_root: Path,
    failing_source_clip_id: str,
) -> dict[str, object]:
    arm_matrix_path = validation_root / "arm_matrix.json"
    arm_matrix = _load_json_dict(arm_matrix_path) if arm_matrix_path.exists() else {"arms": []}
    return {
        "validationRoot": str(validation_root),
        "armMatrixPath": str(arm_matrix_path),
        "baselineCurrent": _arm_proof_reference(
            arm_matrix=arm_matrix,
            arm_name=ARM_NAME_BASELINE_CURRENT,
            failing_source_clip_id=failing_source_clip_id,
        ),
        "promotedV6Baseline": _arm_proof_reference(
            arm_matrix=arm_matrix,
            arm_name=ARM_NAME_PROMOTED_V6_BASELINE,
            failing_source_clip_id=failing_source_clip_id,
        ),
    }


def _window_id(
    *,
    failing_source_clip_id: str,
    start_frame: int,
    end_frame: int,
) -> str:
    return f"{failing_source_clip_id}-proposal-selection-{start_frame:04d}-{end_frame:04d}"


def _proposal_windows_from_taxonomy(
    *,
    taxonomy: dict[str, object],
) -> list[dict[str, object]]:
    windows = taxonomy.get("windows")
    if not isinstance(windows, list):
        return []
    proposal_windows = []
    for window in windows:
        if not isinstance(window, dict):
            continue
        if str(window.get("taxonomyBucket") or "") != BUCKET_PROPOSAL_NOT_SELECTED:
            continue
        proposal_windows.append(dict(window))
    return proposal_windows


def build_proposal_selection_window_manifest(
    *,
    taxonomy: dict[str, object],
    source_manifest: dict[str, object],
    validation_root: Path,
    failing_source_clip_id: str = DEFAULT_FAILING_SOURCE_CLIP_ID,
    padding_frames: int = DEFAULT_WINDOW_PADDING_FRAMES,
) -> dict[str, object]:
    source_entry = _find_source_entry(
        source_manifest=source_manifest,
        failing_source_clip_id=failing_source_clip_id,
    )
    sample_interval = _safe_int(taxonomy.get("sampleInterval"), 5)
    proof_references = _proof_references(
        validation_root=Path(validation_root),
        failing_source_clip_id=failing_source_clip_id,
    )
    manifest_windows: list[dict[str, object]] = []
    for window in _proposal_windows_from_taxonomy(taxonomy=taxonomy):
        start_frame = _safe_int(window.get("startFrame"), 0)
        end_frame = _safe_int(window.get("endFrame"), start_frame)
        frame_count = _safe_int(window.get("frameCount"), 0)
        frame_ids = window.get("frameIds")
        if not isinstance(frame_ids, list):
            frame_ids = []
        evidence = window.get("evidence")
        if not isinstance(evidence, list):
            evidence = []
        manifest_windows.append(
            {
                "windowId": _window_id(
                    failing_source_clip_id=failing_source_clip_id,
                    start_frame=start_frame,
                    end_frame=end_frame,
                ),
                "sourceClipId": failing_source_clip_id,
                "sourceLabel": source_entry.get("label"),
                "sourceLocalPath": source_entry.get("localPath"),
                "sourceManifestEnabled": source_entry.get("enabled"),
                "taxonomyBucket": BUCKET_PROPOSAL_NOT_SELECTED,
                "startFrame": start_frame,
                "endFrame": end_frame,
                "frameCount": frame_count,
                "frameIds": [int(frame_id) for frame_id in frame_ids],
                "paddedStartFrame": max(0, start_frame - int(padding_frames)),
                "paddedEndFrame": end_frame + int(padding_frames),
                "sampleInterval": sample_interval,
                "evidence": [str(item) for item in evidence],
                "proofReferences": proof_references,
            }
        )
    manifest_windows.sort(key=lambda item: (_safe_int(item.get("startFrame"), 0), _safe_int(item.get("endFrame"), 0)))
    return {
        "analysisBatchName": DEFAULT_BATCH_NAME,
        "sourceReviewBatchName": DEFAULT_REVIEW_BATCH_NAME,
        "failingSourceClipId": failing_source_clip_id,
        "sourceManifestEntry": source_entry,
        "sampleInterval": sample_interval,
        "paddingFrames": int(padding_frames),
        "windowCount": len(manifest_windows),
        "missingAcceptedFrameCount": sum(_safe_int(window.get("frameCount"), 0) for window in manifest_windows),
        "windows": manifest_windows,
    }


def build_gold_truth_bootstrap_plan(
    *,
    proposal_windows: dict[str, object],
    target_window_count: int = DEFAULT_BOOTSTRAP_WINDOW_COUNT,
) -> dict[str, object]:
    windows = proposal_windows.get("windows")
    if not isinstance(windows, list):
        windows = []
    ranked_windows = sorted(
        [dict(window) for window in windows if isinstance(window, dict)],
        key=lambda window: (-_safe_int(window.get("frameCount"), 0), _safe_int(window.get("startFrame"), 0)),
    )
    selected_windows = ranked_windows[: int(target_window_count)]
    return {
        "analysisBatchName": DEFAULT_BATCH_NAME,
        "attemptFamily": NEXT_ATTEMPT_FAMILY_SUCCESS,
        "targetWindowCount": int(target_window_count),
        "candidateWindowCount": len(ranked_windows),
        "selectedWindowCount": len(selected_windows),
        "selectedMissingAcceptedFrameCount": sum(_safe_int(window.get("frameCount"), 0) for window in selected_windows),
        "bootstrapWindows": selected_windows,
        "reviewInstructions": [
            "Label accepted ball visibility for each sampled frame in the padded window.",
            "Label controlled possession only where accepted ball and player support are visible enough.",
            "Preserve generated proof references so detector-side fixes can map labels back to proposal selection evidence.",
        ],
    }


def build_source_manifest_delta(
    *,
    proposal_windows: dict[str, object],
    gold_truth_bootstrap_plan: dict[str, object],
) -> dict[str, object]:
    windows = proposal_windows.get("windows")
    if not isinstance(windows, list):
        windows = []
    return {
        "analysisBatchName": DEFAULT_BATCH_NAME,
        "mutationPolicy": "proposal_only_do_not_rewrite_frozen_source_manifest",
        "proposedEntryCount": len(windows),
        "proposedGoldTruthBootstrapEntryCount": _safe_int(
            gold_truth_bootstrap_plan.get("selectedWindowCount"),
            0,
        ),
        "proposedEntries": [
            {
                "windowId": window.get("windowId"),
                "clipId": window.get("sourceClipId"),
                "localPath": window.get("sourceLocalPath"),
                "startFrame": window.get("paddedStartFrame"),
                "endFrame": window.get("paddedEndFrame"),
                "taxonomyBucket": window.get("taxonomyBucket"),
                "purpose": "proposal_selection_missing_accepted_signal_review",
                "enabled": False,
            }
            for window in windows
            if isinstance(window, dict)
        ],
    }


def _weak_evidence_reasons(
    *,
    proposal_selection_window_count: int,
    selected_bootstrap_frame_count: int,
) -> list[str]:
    reasons = []
    if int(proposal_selection_window_count) < MIN_SUCCESS_WINDOW_COUNT:
        reasons.append("proposal_selection_window_count_below_3")
    if int(selected_bootstrap_frame_count) < MIN_SUCCESS_BOOTSTRAP_FRAME_COUNT:
        reasons.append("missing_accepted_frame_count_below_50")
    return reasons


def _batch_outcome_markdown(payload: dict[str, object]) -> str:
    return "\n".join(
        [
            "# Promoted V6 Source Manifest And Gold-Truth Refresh v1",
            "",
            f"- goalAchieved: {payload.get('goalAchieved')}",
            f"- proposalSelectionWindowCount: {payload.get('proposalSelectionWindowCount')}",
            f"- selectedBootstrapMissingAcceptedFrameCount: {payload.get('selectedBootstrapMissingAcceptedFrameCount')}",
            f"- nextRecommendedAttemptFamily: {payload.get('nextRecommendedAttemptFamily')}",
            f"- nextRecommendedBatch: {payload.get('nextRecommendedBatch')}",
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


def run_promoted_v6_source_manifest_and_gold_truth_refresh(
    *,
    analysis_root: Path = DEFAULT_ANALYSIS_ROOT,
    review_refresh_root: Path = DEFAULT_REVIEW_REFRESH_ROOT,
    source_manifest_path: Path = DEFAULT_SOURCE_MANIFEST_PATH,
    validation_root: Path = DEFAULT_VALIDATION_ROOT,
    retention_delta_root: Path = DEFAULT_RETENTION_DELTA_ROOT,
    failing_source_clip_id: str = DEFAULT_FAILING_SOURCE_CLIP_ID,
) -> dict[str, object]:
    analysis_root = Path(analysis_root)
    review_refresh_root = Path(review_refresh_root)
    source_manifest_path = Path(source_manifest_path)
    validation_root = Path(validation_root)
    retention_delta_root = Path(retention_delta_root)

    review_summary = _load_json_dict(review_refresh_root / "review_refresh_summary.json")
    taxonomy = _load_json_dict(review_refresh_root / "missing_accepted_signal_taxonomy.json")
    source_manifest = _load_json_dict(source_manifest_path)
    retention_delta_summary = _load_json_dict(retention_delta_root / "retention_delta_summary.json")

    proposal_window_manifest = build_proposal_selection_window_manifest(
        taxonomy=taxonomy,
        source_manifest=source_manifest,
        validation_root=validation_root,
        failing_source_clip_id=failing_source_clip_id,
    )
    gold_truth_bootstrap_plan = build_gold_truth_bootstrap_plan(
        proposal_windows=proposal_window_manifest,
        target_window_count=DEFAULT_BOOTSTRAP_WINDOW_COUNT,
    )
    source_manifest_delta = build_source_manifest_delta(
        proposal_windows=proposal_window_manifest,
        gold_truth_bootstrap_plan=gold_truth_bootstrap_plan,
    )

    proposal_selection_window_count = _safe_int(proposal_window_manifest.get("windowCount"), 0)
    selected_bootstrap_frame_count = _safe_int(
        gold_truth_bootstrap_plan.get("selectedMissingAcceptedFrameCount"),
        0,
    )
    weak_evidence_reasons = _weak_evidence_reasons(
        proposal_selection_window_count=proposal_selection_window_count,
        selected_bootstrap_frame_count=selected_bootstrap_frame_count,
    )
    goal_achieved = not weak_evidence_reasons
    generated_at = _utc_now_iso()
    summary = {
        "generatedAt": generated_at,
        "analysisBatchName": DEFAULT_BATCH_NAME,
        "attemptNumber": 1,
        "attemptApproachFamily": "manifest_scope_refresh",
        "failingSourceClipId": failing_source_clip_id,
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "weakEvidenceReasons": weak_evidence_reasons,
        "dominantBlockerClass": review_summary.get("dominantBlockerClass"),
        "nextFixFamily": review_summary.get("nextFixFamily"),
        "proposalSelectionWindowCount": proposal_selection_window_count,
        "proposalSelectionMissingAcceptedFrameCount": _safe_int(
            proposal_window_manifest.get("missingAcceptedFrameCount"),
            0,
        ),
        "selectedBootstrapWindowCount": _safe_int(gold_truth_bootstrap_plan.get("selectedWindowCount"), 0),
        "selectedBootstrapMissingAcceptedFrameCount": selected_bootstrap_frame_count,
        "sourceManifestPath": str(source_manifest_path),
        "sourceManifestMutationPolicy": "not_mutated_delta_only",
        "nextRecommendedAttemptFamily": NEXT_ATTEMPT_FAMILY_SUCCESS,
        "nextRecommendedBatch": DEFAULT_BATCH_NAME,
        "retentionEvidence": {
            "primaryRetentionBlockerClass": retention_delta_summary.get("primaryRetentionBlockerClass"),
            "acceptedRetentionRatio": round(_safe_float(retention_delta_summary.get("acceptedRetentionRatio"), 0.0), 3),
            "controlledRetentionRatio": round(
                _safe_float(retention_delta_summary.get("controlledRetentionRatio"), 0.0),
                3,
            ),
        },
    }
    decision_matrix = {
        "generatedAt": generated_at,
        "analysisBatchName": DEFAULT_BATCH_NAME,
        "inputTruth": {
            "reviewRefreshRoot": str(review_refresh_root),
            "sourceManifestPath": str(source_manifest_path),
            "validationRoot": str(validation_root),
            "retentionDeltaRoot": str(retention_delta_root),
        },
        "successThresholds": {
            "minProposalSelectionWindowCount": MIN_SUCCESS_WINDOW_COUNT,
            "minSelectedBootstrapMissingAcceptedFrameCount": MIN_SUCCESS_BOOTSTRAP_FRAME_COUNT,
        },
        "resolvedDecision": {
            "goalAchieved": goal_achieved,
            "weakEvidenceReasons": weak_evidence_reasons,
            "nextRecommendedAttemptFamily": NEXT_ATTEMPT_FAMILY_SUCCESS,
            "nextRecommendedBatch": DEFAULT_BATCH_NAME,
        },
    }
    batch_outcome_analysis = {
        **summary,
        "batchGoal": "Refresh the failing-source manifest scope and gold-truth bootstrap target from proposal-selection evidence.",
        "englishSummary": (
            f"Built {proposal_selection_window_count} proposal-selection evidence windows from the review taxonomy and "
            f"selected {summary['selectedBootstrapWindowCount']} windows covering {selected_bootstrap_frame_count} missing "
            "accepted frames for the next gold-truth bootstrap attempt."
        ),
        "englishDecision": (
            "Advance to gold_truth_bootstrap in the same batch."
            if goal_achieved
            else "Evidence is weak; keep the batch active and use gold_truth_bootstrap to resolve the missing truth surface."
        ),
    }

    _write_json(analysis_root / "manifest_scope_refresh_summary.json", summary)
    _write_json(analysis_root / "proposal_selection_window_manifest.json", proposal_window_manifest)
    _write_json(analysis_root / "gold_truth_bootstrap_plan.json", gold_truth_bootstrap_plan)
    _write_json(analysis_root / "source_manifest_delta.json", source_manifest_delta)
    _write_json(analysis_root / "decision_matrix.json", decision_matrix)
    _write_json(analysis_root / "batch_outcome_analysis.json", batch_outcome_analysis)
    _write_text(analysis_root / "batch_outcome_analysis.md", _batch_outcome_markdown(batch_outcome_analysis))

    return {
        "summary": summary,
        "proposalSelectionWindowManifest": proposal_window_manifest,
        "goldTruthBootstrapPlan": gold_truth_bootstrap_plan,
        "sourceManifestDelta": source_manifest_delta,
        "decisionMatrix": decision_matrix,
        "batchOutcomeAnalysis": batch_outcome_analysis,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build promoted-v6 source manifest and gold-truth refresh artifacts from saved proof truth.",
    )
    parser.add_argument("--analysis-root", default=str(DEFAULT_ANALYSIS_ROOT))
    parser.add_argument("--review-refresh-root", default=str(DEFAULT_REVIEW_REFRESH_ROOT))
    parser.add_argument("--source-manifest-path", default=str(DEFAULT_SOURCE_MANIFEST_PATH))
    parser.add_argument("--validation-root", default=str(DEFAULT_VALIDATION_ROOT))
    parser.add_argument("--retention-delta-root", default=str(DEFAULT_RETENTION_DELTA_ROOT))
    parser.add_argument("--failing-source-clip-id", default=DEFAULT_FAILING_SOURCE_CLIP_ID)
    args = parser.parse_args()

    payload = run_promoted_v6_source_manifest_and_gold_truth_refresh(
        analysis_root=Path(args.analysis_root),
        review_refresh_root=Path(args.review_refresh_root),
        source_manifest_path=Path(args.source_manifest_path),
        validation_root=Path(args.validation_root),
        retention_delta_root=Path(args.retention_delta_root),
        failing_source_clip_id=args.failing_source_clip_id,
    )
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
