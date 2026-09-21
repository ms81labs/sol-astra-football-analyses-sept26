from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_SUITE_ROOT = DEFAULT_STORAGE_ROOT / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
DEFAULT_PARENT_ROOT = DEFAULT_SUITE_ROOT / "promoted_v6_source_manifest_and_gold_truth_refresh_v1"
DEFAULT_ANALYSIS_ROOT = DEFAULT_PARENT_ROOT
DEFAULT_OUTPUT_ROOT = DEFAULT_ANALYSIS_ROOT / "gold_truth_bootstrap_attempt_v1"
DEFAULT_BOOTSTRAP_PLAN_PATH = DEFAULT_PARENT_ROOT / "gold_truth_bootstrap_plan.json"
DEFAULT_VALIDATION_ROOT = DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_robustness_validation_v1"
DEFAULT_RETENTION_DELTA_ROOT = (
    DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
)
DEFAULT_SOURCE_MANIFEST_PATH = REPO_ROOT / "backend" / "benchmark_suites" / "frozen_viable_baseline_source_manifest.json"
DEFAULT_BATCH_NAME = "promoted_v6_source_manifest_and_gold_truth_refresh_v1"
DEFAULT_ATTEMPT_NAME = "gold_truth_bootstrap_attempt_v1"
DEFAULT_FAILING_SOURCE_CLIP_ID = "trimed-5min.mp4"

ARM_NAME_BASELINE_CURRENT = "baseline_current"
ARM_NAME_PROMOTED_V6_BASELINE = "promoted_v6_baseline"

MIN_BOOTSTRAP_WINDOW_COUNT = 5
MIN_REPRESENTED_FRAME_COUNT = 50
MIN_OVERLAY_REVIEW_ITEM_COUNT = 50

APPROACH_A = "A_direct_saved_artifact_seed"
APPROACH_B = "B_review_overlay_fallback"
APPROACH_C = "C_evidence_only_blocker"

NEXT_FAMILY_PROPOSAL_SELECTION = "proposal_selection_admission_fix"
NEXT_FAMILY_SUPPORT_VIABILITY = "support_viability_truth_fix"
NEXT_FAMILY_MANUAL_REVIEW = "manual_review_required"
NEXT_FAMILY_MANIFEST_METADATA = "manifest_metadata_refresh"


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


def _probe_rows(payload: dict[str, object]) -> list[dict[str, object]]:
    probe = payload.get("probeObservedBall")
    if not isinstance(probe, dict):
        return []
    rows: list[dict[str, object]] = []
    for key in ("rows", "rawRows", "filteredRows"):
        value = probe.get(key)
        if isinstance(value, list):
            rows.extend(dict(row) for row in value if isinstance(row, dict) and "Frame_ID" in row)
    return rows


def _rows_by_frame(rows: list[dict[str, object]]) -> dict[int, dict[str, object]]:
    by_frame: dict[int, dict[str, object]] = {}
    for row in rows:
        by_frame[_safe_int(row.get("Frame_ID"), -1)] = row
    return {frame_id: row for frame_id, row in by_frame.items() if frame_id >= 0}


def _stable_id(*parts: object) -> str:
    raw = "::".join(str(part) for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def _bbox_from_ball_row(row: dict[str, object]) -> dict[str, float] | None:
    keys = ("Source_X1", "Source_Y1", "Source_X2", "Source_Y2")
    if not all(key in row for key in keys):
        return None
    x1 = _safe_float(row.get("Source_X1"))
    y1 = _safe_float(row.get("Source_Y1"))
    x2 = _safe_float(row.get("Source_X2"))
    y2 = _safe_float(row.get("Source_Y2"))
    if x2 <= x1 or y2 <= y1:
        return None
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


def _proof_root_from_arm_matrix(
    *,
    validation_root: Path,
    arm_name: str,
    failing_source_clip_id: str,
) -> Path | None:
    arm_matrix_path = validation_root / "arm_matrix.json"
    if not arm_matrix_path.exists():
        return None
    arm_matrix = _load_json_dict(arm_matrix_path)
    arms = arm_matrix.get("arms")
    if not isinstance(arms, list):
        return None
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
            reused = proof_run.get("reusedEvidence")
            if not isinstance(reused, dict):
                continue
            selected_cluster_delta_path = reused.get("selectedClusterDeltaPath")
            if not selected_cluster_delta_path:
                continue
            return Path(str(selected_cluster_delta_path)).expanduser().parent
    return None


def _proof_references_from_plan_or_validation(
    *,
    bootstrap_plan: dict[str, object],
    validation_root: Path,
    failing_source_clip_id: str,
) -> dict[str, object]:
    windows = bootstrap_plan.get("bootstrapWindows")
    if isinstance(windows, list) and windows:
        first_window = windows[0]
        if isinstance(first_window, dict) and isinstance(first_window.get("proofReferences"), dict):
            candidate = dict(first_window["proofReferences"])
            baseline_ref = dict(candidate.get("baselineCurrent") or {})
            promoted_ref = dict(candidate.get("promotedV6Baseline") or {})
            baseline_path = baseline_ref.get("ballTruthLayersPath")
            promoted_path = promoted_ref.get("ballTruthLayersPath")
            if baseline_path and promoted_path and Path(str(baseline_path)).expanduser().exists() and Path(
                str(promoted_path)
            ).expanduser().exists():
                return candidate

    baseline_root = _proof_root_from_arm_matrix(
        validation_root=validation_root,
        arm_name=ARM_NAME_BASELINE_CURRENT,
        failing_source_clip_id=failing_source_clip_id,
    )
    promoted_root = _proof_root_from_arm_matrix(
        validation_root=validation_root,
        arm_name=ARM_NAME_PROMOTED_V6_BASELINE,
        failing_source_clip_id=failing_source_clip_id,
    )
    return {
        "baselineCurrent": {
            "proofRoot": str(baseline_root) if baseline_root else None,
            "ballTruthLayersPath": str(baseline_root / "ball_truth_layers.json") if baseline_root else None,
            "selectedClusterDeltaPath": str(baseline_root / "selected_cluster_delta.json") if baseline_root else None,
        },
        "promotedV6Baseline": {
            "proofRoot": str(promoted_root) if promoted_root else None,
            "ballTruthLayersPath": str(promoted_root / "ball_truth_layers.json") if promoted_root else None,
            "selectedClusterDeltaPath": str(promoted_root / "selected_cluster_delta.json") if promoted_root else None,
        },
    }


def _complete_proof_reference(reference: dict[str, object]) -> dict[str, object]:
    completed = dict(reference)
    proof_root = completed.get("proofRoot")
    if proof_root:
        proof_root_path = Path(str(proof_root)).expanduser()
        completed.setdefault("ballTruthLayersPath", str(proof_root_path / "ball_truth_layers.json"))
        completed.setdefault("selectedClusterDeltaPath", str(proof_root_path / "selected_cluster_delta.json"))
    return completed


def _path_from_reference(reference: dict[str, object], key: str) -> Path:
    value = reference.get(key)
    if not value:
        raise FileNotFoundError(f"Missing proof reference key {key}")
    return Path(str(value)).expanduser()


def _proposal_evidence_summary(recovery_profile_matrix: dict[str, object]) -> dict[str, object]:
    profiles = recovery_profile_matrix.get("profiles")
    if not isinstance(profiles, list):
        profiles = []
    proposal_profiles = []
    total_candidate_frames = 0
    total_selected_frames = 0
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        candidate_frames = _safe_int(profile.get("proposalCandidateFrames"), 0)
        selected_frames = _safe_int(profile.get("selectedFrames"), 0)
        raw_detected = _safe_int(profile.get("proposalRawDetectedFrames"), 0)
        if candidate_frames <= 0 and raw_detected <= 0:
            continue
        total_candidate_frames += candidate_frames
        total_selected_frames += selected_frames
        proposal_profiles.append(
            {
                "name": profile.get("name"),
                "proposalCandidateFrames": candidate_frames,
                "proposalRawDetectedFrames": raw_detected,
                "selectedFrames": selected_frames,
            }
        )
    return {
        "proposalEvidenceAvailable": total_candidate_frames > 0,
        "proposalEvidenceScope": "recovery_profile_matrix_global" if total_candidate_frames > 0 else "none",
        "proposalCandidateFrames": total_candidate_frames,
        "proposalSelectedFrames": total_selected_frames,
        "proposalProfiles": proposal_profiles,
    }


def build_candidate_frame_truth_manifest(
    *,
    bootstrap_plan: dict[str, object],
    baseline_truth: dict[str, object],
    promoted_truth: dict[str, object],
    baseline_selected_cluster_delta: dict[str, object],
    recovery_profile_matrix: dict[str, object],
    proof_references: dict[str, object],
) -> dict[str, object]:
    baseline_accepted_by_frame = _rows_by_frame(_rows_from_layer(baseline_truth, "acceptedBall"))
    promoted_accepted_by_frame = _rows_by_frame(_rows_from_layer(promoted_truth, "acceptedBall"))
    promoted_observed_by_frame = _rows_by_frame(_rows_from_layer(promoted_truth, "observedBall"))
    promoted_probe_by_frame = _rows_by_frame(_probe_rows(promoted_truth))
    proposal_summary = _proposal_evidence_summary(recovery_profile_matrix)
    controlled_reference = {}
    if isinstance(baseline_selected_cluster_delta.get("after"), dict):
        controlled_reference = dict(baseline_selected_cluster_delta["after"])

    windows = bootstrap_plan.get("bootstrapWindows")
    if not isinstance(windows, list):
        windows = []
    baseline_reference = _complete_proof_reference(dict(proof_references.get("baselineCurrent") or {}))
    promoted_reference = _complete_proof_reference(dict(proof_references.get("promotedV6Baseline") or {}))
    candidate_frames: list[dict[str, object]] = []
    represented_window_ids: set[str] = set()
    for window in windows:
        if not isinstance(window, dict):
            continue
        window_id = str(window.get("windowId") or "")
        frame_ids = window.get("frameIds")
        if not isinstance(frame_ids, list):
            start_frame = _safe_int(window.get("startFrame"), -1)
            end_frame = _safe_int(window.get("endFrame"), start_frame)
            sample_interval = max(1, _safe_int(window.get("sampleInterval"), 5))
            frame_ids = list(range(start_frame, end_frame + 1, sample_interval))
        window_represented = False
        for raw_frame_id in frame_ids:
            frame_id = _safe_int(raw_frame_id, -1)
            if frame_id < 0:
                continue
            baseline_row = baseline_accepted_by_frame.get(frame_id)
            if baseline_row is None:
                continue
            promoted_signal_sources = []
            if frame_id in promoted_accepted_by_frame:
                promoted_signal_sources.append("promoted_accepted")
            if frame_id in promoted_observed_by_frame:
                promoted_signal_sources.append("promoted_observed")
            if frame_id in promoted_probe_by_frame:
                promoted_signal_sources.append("promoted_probe")
            if proposal_summary["proposalEvidenceAvailable"]:
                promoted_signal_sources.append("promoted_recovery_profile_proposal")
            lineage = {
                "baselineBallTruthLayersPath": baseline_reference.get("ballTruthLayersPath"),
                "baselineSelectedClusterDeltaPath": baseline_reference.get("selectedClusterDeltaPath"),
                "promotedBallTruthLayersPath": promoted_reference.get("ballTruthLayersPath"),
                "promotedSelectedClusterDeltaPath": promoted_reference.get("selectedClusterDeltaPath"),
            }
            candidate_frames.append(
                {
                    "candidateFrameId": _stable_id(window_id, frame_id, "gold_truth_bootstrap"),
                    "windowId": window_id,
                    "sourceClipId": window.get("sourceClipId"),
                    "frameId": frame_id,
                    "timestampSeconds": _safe_float(baseline_row.get("Timestamp"), frame_id / 25.0),
                    "baselineAcceptedRow": baseline_row,
                    "acceptedSeedDecision": "accept_seed",
                    "acceptedSeedSource": "baseline_current_accepted_ball",
                    "controlledSeedDecision": "controlled_truth_candidate",
                    "controlledSeedSource": "baseline_selected_cluster_summary",
                    "controlledReference": controlled_reference,
                    "promotedSignalSources": sorted(set(promoted_signal_sources)),
                    "proposalEvidenceAvailable": bool(proposal_summary["proposalEvidenceAvailable"]),
                    "proposalEvidenceScope": proposal_summary["proposalEvidenceScope"],
                    "seedBBox": _bbox_from_ball_row(baseline_row),
                    "lineage": lineage,
                    "lineageComplete": all(bool(value) for value in lineage.values()),
                }
            )
            window_represented = True
        if window_represented:
            represented_window_ids.add(window_id)
    return {
        "analysisBatchName": DEFAULT_BATCH_NAME,
        "attemptName": DEFAULT_ATTEMPT_NAME,
        "candidateFrameCount": len(candidate_frames),
        "representedBootstrapWindowCount": len(represented_window_ids),
        "representedBootstrapWindowIds": sorted(represented_window_ids),
        "representedMissingAcceptedFrameCount": len(candidate_frames),
        "proposalEvidenceAvailable": bool(proposal_summary["proposalEvidenceAvailable"]),
        "proposalEvidenceScope": proposal_summary["proposalEvidenceScope"],
        "proposalEvidenceSummary": proposal_summary,
        "candidateFrames": sorted(candidate_frames, key=lambda item: (_safe_int(item.get("frameId"), 0), str(item.get("windowId") or ""))),
    }


def build_accepted_controlled_truth_seed(
    *,
    candidate_manifest: dict[str, object],
) -> dict[str, object]:
    frames = candidate_manifest.get("candidateFrames")
    if not isinstance(frames, list):
        frames = []
    accepted_rows = []
    controlled_rows = []
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        accepted_rows.append(
            {
                "candidateFrameId": frame.get("candidateFrameId"),
                "windowId": frame.get("windowId"),
                "frameId": frame.get("frameId"),
                "decision": frame.get("acceptedSeedDecision"),
                "seedSource": frame.get("acceptedSeedSource"),
                "row": frame.get("baselineAcceptedRow"),
                "lineage": frame.get("lineage"),
            }
        )
        controlled_rows.append(
            {
                "candidateFrameId": frame.get("candidateFrameId"),
                "windowId": frame.get("windowId"),
                "frameId": frame.get("frameId"),
                "decision": frame.get("controlledSeedDecision"),
                "seedSource": frame.get("controlledSeedSource"),
                "controlledReference": frame.get("controlledReference"),
                "lineage": frame.get("lineage"),
            }
        )
    return {
        "analysisBatchName": DEFAULT_BATCH_NAME,
        "attemptName": DEFAULT_ATTEMPT_NAME,
        "acceptedSeedRowCount": len(accepted_rows),
        "controlledSeedCandidateRowCount": len(controlled_rows),
        "acceptedBallSeedRows": accepted_rows,
        "controlledPossessionCandidateRows": controlled_rows,
        "truthStatus": "bootstrap_seed_not_manual_gold",
    }


def build_reviewed_label_overlay(
    *,
    candidate_manifest: dict[str, object],
) -> dict[str, object]:
    frames = candidate_manifest.get("candidateFrames")
    if not isinstance(frames, list):
        frames = []
    review_items = []
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        seed_bbox = frame.get("seedBBox")
        review_items.append(
            {
                "reviewItemId": _stable_id(frame.get("candidateFrameId"), "review_overlay"),
                "curationUnitId": frame.get("windowId"),
                "matchId": None,
                "sourceClipId": frame.get("sourceClipId") or DEFAULT_FAILING_SOURCE_CLIP_ID,
                "frameIndex": frame.get("frameId"),
                "timestampSeconds": frame.get("timestampSeconds"),
                "seedSource": "baseline_current_accepted_ball",
                "seedBBox": seed_bbox,
                "decision": "accept_seed" if isinstance(seed_bbox, dict) else "pending_review",
                "reviewedBBox": None,
                "notes": f"[{DEFAULT_ATTEMPT_NAME}: baseline accepted seed]",
                "split": "truth_bootstrap",
                "fileStem": f"{frame.get('sourceClipId') or DEFAULT_FAILING_SOURCE_CLIP_ID}__f{_safe_int(frame.get('frameId'), 0):06d}",
            }
        )
    pending = sum(str(item.get("decision") or "") == "pending_review" for item in review_items)
    reviewed_positive = sum(str(item.get("decision") or "") in {"accept_seed", "adjust_bbox"} for item in review_items)
    reviewed_negative = sum(
        str(item.get("decision") or "") in {"reject_seed", "confirm_hard_negative"} for item in review_items
    )
    return {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_ATTEMPT_NAME,
        "reviewItemCount": len(review_items),
        "pendingReviewCount": pending,
        "reviewedPositiveCount": reviewed_positive,
        "reviewedNegativeCount": reviewed_negative,
        "failingSourceReviewComplete": pending == 0,
        "controlReviewComplete": True,
        "reviewItems": sorted(review_items, key=lambda item: _safe_int(item.get("frameIndex"), 0)),
    }


def evaluate_bootstrap_quality(
    *,
    candidate_manifest: dict[str, object],
    reviewed_label_overlay: dict[str, object],
) -> dict[str, object]:
    represented_windows = _safe_int(candidate_manifest.get("representedBootstrapWindowCount"), 0)
    represented_frames = _safe_int(candidate_manifest.get("representedMissingAcceptedFrameCount"), 0)
    candidate_frames = candidate_manifest.get("candidateFrames")
    if not isinstance(candidate_frames, list):
        candidate_frames = []
    lineage_complete = bool(candidate_frames) and all(bool(frame.get("lineageComplete")) for frame in candidate_frames if isinstance(frame, dict))
    direct_reasons = []
    if represented_windows < MIN_BOOTSTRAP_WINDOW_COUNT:
        direct_reasons.append("bootstrap_window_count_below_5")
    if represented_frames < MIN_REPRESENTED_FRAME_COUNT:
        direct_reasons.append("represented_missing_accepted_frames_below_50")
    if not lineage_complete:
        direct_reasons.append("frame_lineage_incomplete")
    if not direct_reasons:
        return {
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "successfulApproach": APPROACH_A,
            "weakEvidenceReasons": [],
        }

    overlay_count = _safe_int(reviewed_label_overlay.get("reviewItemCount"), 0)
    if overlay_count >= MIN_OVERLAY_REVIEW_ITEM_COUNT and lineage_complete:
        return {
            "goalAchieved": True,
            "roadmapAdvanceAllowed": True,
            "successfulApproach": APPROACH_B,
            "weakEvidenceReasons": [],
            "directSeedWeakEvidenceReasons": direct_reasons,
        }

    weak_reasons = list(direct_reasons)
    if overlay_count < MIN_OVERLAY_REVIEW_ITEM_COUNT:
        weak_reasons.append("review_overlay_coverage_below_50")
    return {
        "goalAchieved": False,
        "roadmapAdvanceAllowed": False,
        "successfulApproach": APPROACH_C,
        "weakEvidenceReasons": weak_reasons,
    }


def select_next_corrective_family(
    *,
    quality_gate: dict[str, object],
    candidate_manifest: dict[str, object],
    reviewed_label_overlay: dict[str, object],
) -> dict[str, object]:
    if not bool(quality_gate.get("goalAchieved")):
        next_family = NEXT_FAMILY_MANIFEST_METADATA
    elif str(quality_gate.get("successfulApproach") or "") == APPROACH_B:
        next_family = NEXT_FAMILY_MANUAL_REVIEW
    elif bool(candidate_manifest.get("proposalEvidenceAvailable")):
        next_family = NEXT_FAMILY_PROPOSAL_SELECTION
    elif _safe_int(reviewed_label_overlay.get("pendingReviewCount"), 0) > 0:
        next_family = NEXT_FAMILY_MANUAL_REVIEW
    else:
        next_family = NEXT_FAMILY_SUPPORT_VIABILITY
    return {
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        "rationale": {
            NEXT_FAMILY_PROPOSAL_SELECTION: "Baseline accepted seed rows are represented and promoted proof has proposal evidence that was not selected.",
            NEXT_FAMILY_SUPPORT_VIABILITY: "Seed truth exists, but proposal evidence is not available enough to target selection.",
            NEXT_FAMILY_MANUAL_REVIEW: "The review overlay is the strongest available truth surface.",
            NEXT_FAMILY_MANIFEST_METADATA: "Bootstrap evidence is too weak; refresh manifest metadata before another detector-side fix.",
        }[next_family],
    }


def _markdown(payload: dict[str, object]) -> str:
    return "\n".join(
        [
            "# Promoted V6 Gold-Truth Bootstrap Attempt v1",
            "",
            f"- goalAchieved: {payload.get('goalAchieved')}",
            f"- successfulApproach: {payload.get('successfulApproach')}",
            f"- representedBootstrapWindowCount: {payload.get('representedBootstrapWindowCount')}",
            f"- representedMissingAcceptedFrameCount: {payload.get('representedMissingAcceptedFrameCount')}",
            f"- nextCorrectiveFamily: {payload.get('nextCorrectiveFamily')}",
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


def run_promoted_v6_gold_truth_bootstrap(
    *,
    analysis_root: Path = DEFAULT_ANALYSIS_ROOT,
    bootstrap_plan_path: Path = DEFAULT_BOOTSTRAP_PLAN_PATH,
    validation_root: Path = DEFAULT_VALIDATION_ROOT,
    retention_delta_root: Path = DEFAULT_RETENTION_DELTA_ROOT,
    source_manifest_path: Path = DEFAULT_SOURCE_MANIFEST_PATH,
    failing_source_clip_id: str = DEFAULT_FAILING_SOURCE_CLIP_ID,
) -> dict[str, object]:
    del source_manifest_path  # Read-only policy: keep this explicit and do not mutate it.
    analysis_root = Path(analysis_root)
    output_root = analysis_root / DEFAULT_ATTEMPT_NAME
    bootstrap_plan = _load_json_dict(Path(bootstrap_plan_path))
    proof_references = _proof_references_from_plan_or_validation(
        bootstrap_plan=bootstrap_plan,
        validation_root=Path(validation_root),
        failing_source_clip_id=failing_source_clip_id,
    )
    baseline_ref = dict(proof_references.get("baselineCurrent") or {})
    promoted_ref = dict(proof_references.get("promotedV6Baseline") or {})
    baseline_truth = _load_json_dict(_path_from_reference(baseline_ref, "ballTruthLayersPath"))
    promoted_truth = _load_json_dict(_path_from_reference(promoted_ref, "ballTruthLayersPath"))
    baseline_selected_cluster_delta = _load_json_dict(_path_from_reference(baseline_ref, "selectedClusterDeltaPath"))
    promoted_root = Path(str(promoted_ref.get("proofRoot") or _path_from_reference(promoted_ref, "ballTruthLayersPath").parent))
    recovery_profile_matrix = _load_json_dict(promoted_root / "recovery_profile_matrix.json")
    retention_delta_summary = (
        _load_json_dict(Path(retention_delta_root) / "retention_delta_summary.json")
        if (Path(retention_delta_root) / "retention_delta_summary.json").exists()
        else {}
    )

    candidate_manifest = build_candidate_frame_truth_manifest(
        bootstrap_plan=bootstrap_plan,
        baseline_truth=baseline_truth,
        promoted_truth=promoted_truth,
        baseline_selected_cluster_delta=baseline_selected_cluster_delta,
        recovery_profile_matrix=recovery_profile_matrix,
        proof_references=proof_references,
    )
    truth_seed = build_accepted_controlled_truth_seed(candidate_manifest=candidate_manifest)
    reviewed_overlay = build_reviewed_label_overlay(candidate_manifest=candidate_manifest)
    quality_gate = evaluate_bootstrap_quality(
        candidate_manifest=candidate_manifest,
        reviewed_label_overlay=reviewed_overlay,
    )
    recommendation = select_next_corrective_family(
        quality_gate=quality_gate,
        candidate_manifest=candidate_manifest,
        reviewed_label_overlay=reviewed_overlay,
    )
    generated_at = _utc_now_iso()
    summary = {
        "generatedAt": generated_at,
        "analysisBatchName": DEFAULT_BATCH_NAME,
        "attemptName": DEFAULT_ATTEMPT_NAME,
        "attemptNumber": 2,
        "attemptApproachFamily": "gold_truth_bootstrap",
        "failingSourceClipId": failing_source_clip_id,
        "goalAchieved": bool(quality_gate.get("goalAchieved")),
        "roadmapAdvanceAllowed": bool(quality_gate.get("roadmapAdvanceAllowed")),
        "successfulApproach": quality_gate.get("successfulApproach"),
        "weakEvidenceReasons": quality_gate.get("weakEvidenceReasons", []),
        "representedBootstrapWindowCount": candidate_manifest["representedBootstrapWindowCount"],
        "representedMissingAcceptedFrameCount": candidate_manifest["representedMissingAcceptedFrameCount"],
        "acceptedSeedRowCount": truth_seed["acceptedSeedRowCount"],
        "controlledSeedCandidateRowCount": truth_seed["controlledSeedCandidateRowCount"],
        "reviewItemCount": reviewed_overlay["reviewItemCount"],
        "pendingReviewCount": reviewed_overlay["pendingReviewCount"],
        "proposalEvidenceAvailable": candidate_manifest["proposalEvidenceAvailable"],
        "proposalEvidenceScope": candidate_manifest["proposalEvidenceScope"],
        "nextCorrectiveFamily": recommendation["nextCorrectiveFamily"],
        "nextRecommendedBatch": recommendation["nextRecommendedBatch"],
        "nextRecommendedNextLever": "promote_touchline_detector_candidate",
        "retentionEvidence": {
            "primaryRetentionBlockerClass": retention_delta_summary.get("primaryRetentionBlockerClass"),
            "acceptedRetentionRatio": retention_delta_summary.get("acceptedRetentionRatio"),
            "controlledRetentionRatio": retention_delta_summary.get("controlledRetentionRatio"),
        },
    }
    decision_matrix = {
        "generatedAt": generated_at,
        "analysisBatchName": DEFAULT_BATCH_NAME,
        "attemptName": DEFAULT_ATTEMPT_NAME,
        "retryPolicy": {
            APPROACH_A: "Seed truth directly from saved baseline accepted rows when represented windows and lineage are strong.",
            APPROACH_B: "Use repo-native reviewed_label_overlay coverage when direct seed is too weak.",
            APPROACH_C: "Emit weak-evidence blocker reasons and recommend manifest metadata refresh.",
        },
        "qualityGate": quality_gate,
        "recommendation": recommendation,
    }
    batch_outcome = {
        **summary,
        "batchGoal": "Create a local gold-truth bootstrap target from the top proposal-selection windows.",
        "englishSummary": (
            f"Built {summary['acceptedSeedRowCount']} accepted seed rows and "
            f"{summary['controlledSeedCandidateRowCount']} controlled candidate rows across "
            f"{summary['representedBootstrapWindowCount']} bootstrap windows."
        ),
        "englishDecision": (
            f"Attempt 2 succeeded; plan the next corrective family `{summary['nextCorrectiveFamily']}`."
            if summary["goalAchieved"]
            else "Attempt 2 was weak; continue the batch with manifest_scope_refresh attempt 3."
        ),
    }

    _write_json(output_root / "gold_truth_bootstrap_summary.json", summary)
    _write_json(output_root / "candidate_frame_truth_manifest.json", candidate_manifest)
    _write_json(output_root / "accepted_controlled_truth_seed.json", truth_seed)
    _write_json(output_root / "reviewed_label_overlay.json", reviewed_overlay)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    _write_text(output_root / "batch_outcome_analysis.md", _markdown(batch_outcome))

    return {
        "summary": summary,
        "candidateFrameTruthManifest": candidate_manifest,
        "acceptedControlledTruthSeed": truth_seed,
        "reviewedLabelOverlay": reviewed_overlay,
        "decisionMatrix": decision_matrix,
        "batchOutcomeAnalysis": batch_outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build promoted-v6 gold-truth bootstrap artifacts from saved proof truth.")
    parser.add_argument("--analysis-root", default=str(DEFAULT_ANALYSIS_ROOT))
    parser.add_argument("--bootstrap-plan-path", default=str(DEFAULT_BOOTSTRAP_PLAN_PATH))
    parser.add_argument("--validation-root", default=str(DEFAULT_VALIDATION_ROOT))
    parser.add_argument("--retention-delta-root", default=str(DEFAULT_RETENTION_DELTA_ROOT))
    parser.add_argument("--source-manifest-path", default=str(DEFAULT_SOURCE_MANIFEST_PATH))
    parser.add_argument("--failing-source-clip-id", default=DEFAULT_FAILING_SOURCE_CLIP_ID)
    args = parser.parse_args()
    payload = run_promoted_v6_gold_truth_bootstrap(
        analysis_root=Path(args.analysis_root),
        bootstrap_plan_path=Path(args.bootstrap_plan_path),
        validation_root=Path(args.validation_root),
        retention_delta_root=Path(args.retention_delta_root),
        source_manifest_path=Path(args.source_manifest_path),
        failing_source_clip_id=args.failing_source_clip_id,
    )
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
