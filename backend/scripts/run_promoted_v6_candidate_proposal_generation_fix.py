from __future__ import annotations
from backend.scripts.football_external_real_eval_chain_common import write_json_unsorted_no_newline as _write_json


from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
from collections import Counter
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_SUITE_ROOT = DEFAULT_STORAGE_ROOT / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
DEFAULT_ANALYSIS_ROOT = DEFAULT_SUITE_ROOT / "candidate_proposal_generation_fix_v1"
DEFAULT_SUPPORT_BLOCKER_ROOT = DEFAULT_SUITE_ROOT / "support_viability_admission_fix"
DEFAULT_GOLD_TRUTH_ROOT = (
    DEFAULT_SUITE_ROOT
    / "promoted_v6_source_manifest_and_gold_truth_refresh_v1"
    / "gold_truth_bootstrap_attempt_v1"
)
DEFAULT_VALIDATION_ROOT = DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_robustness_validation_v1"
DEFAULT_RETENTION_DELTA_ROOT = (
    DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
)
DEFAULT_PROMOTED_PROOF_ROOT = (
    DEFAULT_STORAGE_ROOT / "pod_cycles" / "promoted_v6_baseline-trimed-5min.mp4-robustness-validation"
)
DEFAULT_FAILING_SOURCE_CLIP_ID = "trimed-5min.mp4"

NEXT_PITCH_POLYGON = "pitch_polygon_filter_fix"
NEXT_CROP_GEOMETRY = "proposal_crop_geometry_fix"
NEXT_MULTISCALE = "multiscale_seed_proposal_fix"
NEXT_PROBE_MODEL = "probe_model_generation_fix"
NEXT_MANUAL_REVIEW = "manual_review_required"

MIN_CLASSIFIED_SEED_FRAMES = 5
MIN_DOMINANT_SHARE = 0.5

BUCKET_NO_ATTEMPT = "no_proposal_attempt_for_seed_frame"
BUCKET_PITCH_POLYGON = "direct_seed_detected_but_pitch_polygon_rejected"
BUCKET_CROP_GEOMETRY = "direct_seed_detected_but_crop_geometry_rejected"
BUCKET_MULTISCALE_ONLY = "multiscale_seed_detected_only_at_nondefault_scale"
BUCKET_GENERATED_NOT_SELECTED = "proposal_candidate_generated_but_not_selected"
BUCKET_SELECTED_NOT_ACCEPTED = "proposal_candidate_selected_but_not_accepted"
BUCKET_NO_RAW_DETECTION = "probe_model_no_raw_detection"
BUCKET_UNRESOLVED = "unresolved_generation_gap"


def _load_json_dict(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _load_optional_json_dict(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return _load_json_dict(path)




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


def _list_dicts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _seed_rows(seed_payload: dict[str, object]) -> list[dict[str, object]]:
    rows = _list_dicts(seed_payload.get("acceptedBallSeedRows"))
    return sorted(rows, key=lambda row: (_safe_int(row.get("frameId"), -1), str(row.get("candidateFrameId") or "")))


def _candidate_frames_by_frame(candidate_manifest: dict[str, object]) -> dict[int, dict[str, object]]:
    frames = _list_dicts(candidate_manifest.get("candidateFrames"))
    by_frame: dict[int, dict[str, object]] = {}
    for frame in frames:
        frame_id = _safe_int(frame.get("frameId"), -1)
        if frame_id >= 0:
            by_frame[frame_id] = frame
    return by_frame


def _frame_ids_from_rows(rows: object) -> set[int]:
    return {
        _safe_int(row.get("Frame_ID"), -1)
        for row in _list_dicts(rows)
        if _safe_int(row.get("Frame_ID"), -1) >= 0
    }


def _accepted_frame_ids(ball_truth_layers: dict[str, object]) -> set[int]:
    accepted = ball_truth_layers.get("acceptedBall")
    if not isinstance(accepted, dict):
        return set()
    return _frame_ids_from_rows(accepted.get("rows"))


def _probe_raw_frame_ids(ball_truth_layers: dict[str, object]) -> set[int]:
    probe = ball_truth_layers.get("probeObservedBall")
    if not isinstance(probe, dict):
        return set()
    return _frame_ids_from_rows(probe.get("rawRows"))


def _bool(candidate: dict[str, object], *keys: str) -> bool:
    return any(bool(candidate.get(key)) for key in keys)


def _signal_sources(candidate: dict[str, object]) -> list[str]:
    value = candidate.get("promotedSignalSources")
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _classify_candidate_frame(
    *,
    seed_row: dict[str, object],
    candidate: dict[str, object] | None,
    accepted_frames: set[int],
    probe_raw_frames: set[int],
) -> str | None:
    frame_id = _safe_int(seed_row.get("frameId"), -1)
    if candidate is None:
        return None
    if frame_id in accepted_frames or bool(candidate.get("acceptedInPromoted")):
        return None
    explicit_diagnostic_keys = {
        "proposalAttempted",
        "directSeedDetected",
        "pitchPolygonRejected",
        "cropGeometryRejected",
        "cropEdgeRejected",
        "cropCenterYRejected",
        "nonDefaultScaleDetected",
        "proposalCandidateGenerated",
        "selectedInPromoted",
        "acceptedInPromoted",
    }
    if not any(key in candidate for key in explicit_diagnostic_keys):
        return None
    if _bool(candidate, "proposalAttempted") is False and candidate.get("proposalAttempted") is False:
        return BUCKET_NO_ATTEMPT
    if _bool(candidate, "directSeedDetected") and _bool(candidate, "pitchPolygonRejected"):
        return BUCKET_PITCH_POLYGON
    if _bool(candidate, "directSeedDetected") and _bool(candidate, "cropGeometryRejected", "cropEdgeRejected", "cropCenterYRejected"):
        return BUCKET_CROP_GEOMETRY
    if _bool(candidate, "nonDefaultScaleDetected") and not _bool(candidate, "directSeedDetected"):
        return BUCKET_MULTISCALE_ONLY
    selected = _bool(candidate, "selectedInPromoted") or "promoted_selected" in _signal_sources(candidate)
    generated = (
        _bool(candidate, "proposalCandidateGenerated")
        or bool(candidate.get("proposalEvidenceAvailable"))
        or "promoted_recovery_profile_proposal" in _signal_sources(candidate)
    )
    if selected:
        return BUCKET_SELECTED_NOT_ACCEPTED
    if generated:
        return BUCKET_GENERATED_NOT_SELECTED
    if frame_id not in probe_raw_frames:
        return BUCKET_NO_RAW_DETECTION
    return BUCKET_UNRESOLVED


def _aggregate_bucket_sequence(
    *,
    seed_count: int,
    proof_summary: dict[str, object],
    recovery_profile_matrix: dict[str, object],
) -> list[str]:
    attempted = max(
        _safe_int(proof_summary.get("bestProposalDirectSeedContextWindowFrames"), 0),
        _max_profile_int(recovery_profile_matrix, "proposalDirectSeedContextWindowFrames"),
    )
    zero_detect = max(
        _safe_int(proof_summary.get("bestProposalDirectSeedZeroDetectFrames"), 0),
        _max_profile_int(recovery_profile_matrix, "proposalDirectSeedZeroDetectFrames"),
    )
    pitch_rejected = max(
        _safe_int(proof_summary.get("bestProposalDirectSeedPitchPolygonRejectedFrames"), 0),
        _max_profile_int(recovery_profile_matrix, "proposalDirectSeedPitchPolygonRejectedFrames"),
    )
    crop_rejected = max(
        _safe_int(proof_summary.get("bestProposalDirectSeedCropEdgeRejectedFrames"), 0)
        + _safe_int(proof_summary.get("bestProposalDirectSeedCropCenterYRejectedFrames"), 0),
        _max_profile_int(recovery_profile_matrix, "proposalDirectSeedCropEdgeRejectedFrames")
        + _max_profile_int(recovery_profile_matrix, "proposalDirectSeedCropCenterYRejectedFrames"),
    )
    default_detect = max(
        _safe_int(proof_summary.get("bestProposalDirectSeedDetectedFrames"), 0),
        _max_profile_int(recovery_profile_matrix, "proposalDirectSeedDetectedFrames"),
    )
    nondefault_detect = max(
        _safe_int(proof_summary.get("bestProposalDirectSeedScale960RawDetectionFrames"), 0)
        + _safe_int(proof_summary.get("bestProposalDirectSeedScale1920RawDetectionFrames"), 0),
        _max_profile_int(recovery_profile_matrix, "proposalDirectSeedScale960RawDetectionFrames")
        + _max_profile_int(recovery_profile_matrix, "proposalDirectSeedScale1920RawDetectionFrames"),
    )
    candidate_frames = max(
        _safe_int(proof_summary.get("bestProposalCandidateFrames"), 0),
        _max_profile_int(recovery_profile_matrix, "proposalCandidateFrames"),
    )
    selected_frames = max(
        _safe_int(proof_summary.get("bestProposalSelectedFrames"), 0),
        _max_profile_int(recovery_profile_matrix, "selectedFrames"),
    )

    buckets: list[str] = []
    buckets.extend([BUCKET_PITCH_POLYGON] * min(pitch_rejected, seed_count - len(buckets)))
    buckets.extend([BUCKET_CROP_GEOMETRY] * min(crop_rejected, seed_count - len(buckets)))
    if nondefault_detect > 0 and default_detect == 0:
        buckets.extend([BUCKET_MULTISCALE_ONLY] * min(nondefault_detect, seed_count - len(buckets)))
    buckets.extend([BUCKET_NO_RAW_DETECTION] * min(zero_detect, seed_count - len(buckets)))
    already_explained_attempted = zero_detect + pitch_rejected + crop_rejected
    if nondefault_detect > 0 and default_detect == 0:
        already_explained_attempted += nondefault_detect
    generated_not_selected = max(candidate_frames - selected_frames - already_explained_attempted, 0)
    buckets.extend([BUCKET_GENERATED_NOT_SELECTED] * min(generated_not_selected, seed_count - len(buckets)))
    selected_not_accepted = selected_frames
    buckets.extend([BUCKET_SELECTED_NOT_ACCEPTED] * min(selected_not_accepted, seed_count - len(buckets)))
    not_attempted = max(seed_count - max(attempted, len(buckets)), 0)
    buckets.extend([BUCKET_NO_ATTEMPT] * min(not_attempted, seed_count - len(buckets)))
    if len(buckets) < seed_count:
        buckets.extend([BUCKET_UNRESOLVED] * (seed_count - len(buckets)))
    return buckets[:seed_count]


def _max_profile_int(recovery_profile_matrix: dict[str, object], key: str) -> int:
    values = [_safe_int(profile.get(key), 0) for profile in _list_dicts(recovery_profile_matrix.get("profiles"))]
    return max(values, default=0)


def build_seed_frame_proposal_generation_matrix(
    *,
    seed_payload: dict[str, object],
    candidate_manifest: dict[str, object],
    proof_summary: dict[str, object],
    ball_truth_layers: dict[str, object],
    recovery_profile_matrix: dict[str, object],
) -> dict[str, object]:
    seed_rows = _seed_rows(seed_payload)
    candidates_by_frame = _candidate_frames_by_frame(candidate_manifest)
    accepted_frames = _accepted_frame_ids(ball_truth_layers)
    probe_raw_frames = _probe_raw_frame_ids(ball_truth_layers)
    aggregate_buckets = _aggregate_bucket_sequence(
        seed_count=len(seed_rows),
        proof_summary=proof_summary,
        recovery_profile_matrix=recovery_profile_matrix,
    )

    frames: list[dict[str, object]] = []
    for index, seed_row in enumerate(seed_rows):
        frame_id = _safe_int(seed_row.get("frameId"), -1)
        candidate = candidates_by_frame.get(frame_id)
        gap_class = _classify_candidate_frame(
            seed_row=seed_row,
            candidate=candidate,
            accepted_frames=accepted_frames,
            probe_raw_frames=probe_raw_frames,
        )
        evidence_source = "candidate_manifest"
        if gap_class is None:
            gap_class = aggregate_buckets[index] if index < len(aggregate_buckets) else BUCKET_UNRESOLVED
            evidence_source = "aggregate_proof_fallback"
        frames.append(
            {
                "frameId": frame_id,
                "candidateFrameId": seed_row.get("candidateFrameId"),
                "windowId": seed_row.get("windowId"),
                "gapClass": gap_class,
                "evidenceSource": evidence_source,
                "lineageComplete": bool(seed_row.get("lineage")) or bool(candidate and candidate.get("lineageComplete")),
            }
        )

    counts = Counter(str(frame.get("gapClass") or BUCKET_UNRESOLVED) for frame in frames)
    return {
        "generatedAt": _utc_now_iso(),
        "seedFrameCount": len(seed_rows),
        "classifiedSeedFrameCount": len(frames),
        "representedBootstrapWindowCount": _safe_int(candidate_manifest.get("representedBootstrapWindowCount"), 0),
        "representedMissingAcceptedFrameCount": _safe_int(candidate_manifest.get("representedMissingAcceptedFrameCount"), len(frames)),
        "gapClassCounts": dict(sorted(counts.items())),
        "frames": frames,
    }


def build_proposal_generation_gap_taxonomy(*, matrix: dict[str, object]) -> dict[str, object]:
    counts = {str(key): _safe_int(value) for key, value in dict(matrix.get("gapClassCounts") or {}).items()}
    dominant_class = BUCKET_UNRESOLVED
    dominant_count = 0
    if counts:
        dominant_class, dominant_count = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
    classified = _safe_int(matrix.get("classifiedSeedFrameCount"), 0)
    dominant_share = round(dominant_count / classified, 3) if classified else 0.0
    return {
        "generatedAt": _utc_now_iso(),
        "classifiedSeedFrameCount": classified,
        "dominantGapClass": dominant_class,
        "dominantGapFrameCount": dominant_count,
        "dominantGapShare": dominant_share,
        "gapClassCounts": counts,
    }


def build_seed_crop_failure_audit(
    *,
    proof_summary: dict[str, object],
    recovery_profile_matrix: dict[str, object],
) -> dict[str, object]:
    return {
        "generatedAt": _utc_now_iso(),
        "bestProposalDirectSeedContextWindowFrames": max(
            _safe_int(proof_summary.get("bestProposalDirectSeedContextWindowFrames"), 0),
            _max_profile_int(recovery_profile_matrix, "proposalDirectSeedContextWindowFrames"),
        ),
        "bestProposalDirectSeedZeroDetectFrames": max(
            _safe_int(proof_summary.get("bestProposalDirectSeedZeroDetectFrames"), 0),
            _max_profile_int(recovery_profile_matrix, "proposalDirectSeedZeroDetectFrames"),
        ),
        "bestProposalDirectSeedDetectedFrames": max(
            _safe_int(proof_summary.get("bestProposalDirectSeedDetectedFrames"), 0),
            _max_profile_int(recovery_profile_matrix, "proposalDirectSeedDetectedFrames"),
        ),
        "bestProposalDirectSeedPitchPolygonRejectedFrames": max(
            _safe_int(proof_summary.get("bestProposalDirectSeedPitchPolygonRejectedFrames"), 0),
            _max_profile_int(recovery_profile_matrix, "proposalDirectSeedPitchPolygonRejectedFrames"),
        ),
        "bestProposalDirectSeedCropGeometryRejectedFrames": max(
            _safe_int(proof_summary.get("bestProposalDirectSeedCropEdgeRejectedFrames"), 0)
            + _safe_int(proof_summary.get("bestProposalDirectSeedCropCenterYRejectedFrames"), 0),
            _max_profile_int(recovery_profile_matrix, "proposalDirectSeedCropEdgeRejectedFrames")
            + _max_profile_int(recovery_profile_matrix, "proposalDirectSeedCropCenterYRejectedFrames"),
        ),
        "bestProposalCandidateFrames": max(
            _safe_int(proof_summary.get("bestProposalCandidateFrames"), 0),
            _max_profile_int(recovery_profile_matrix, "proposalCandidateFrames"),
        ),
        "bestProposalSelectedFrames": max(
            _safe_int(proof_summary.get("bestProposalSelectedFrames"), 0),
            _max_profile_int(recovery_profile_matrix, "selectedFrames"),
        ),
    }


def _next_corrective_family(dominant_gap_class: str) -> str:
    if dominant_gap_class == BUCKET_PITCH_POLYGON:
        return NEXT_PITCH_POLYGON
    if dominant_gap_class in {BUCKET_CROP_GEOMETRY, BUCKET_NO_ATTEMPT}:
        return NEXT_CROP_GEOMETRY
    if dominant_gap_class == BUCKET_MULTISCALE_ONLY:
        return NEXT_MULTISCALE
    if dominant_gap_class == BUCKET_NO_RAW_DETECTION:
        return NEXT_PROBE_MODEL
    if dominant_gap_class in {BUCKET_GENERATED_NOT_SELECTED, BUCKET_SELECTED_NOT_ACCEPTED}:
        return NEXT_MANUAL_REVIEW
    return NEXT_MANUAL_REVIEW


def _weak_evidence_reasons(matrix: dict[str, object], taxonomy: dict[str, object]) -> list[str]:
    reasons: list[str] = []
    classified_count = _safe_int(matrix.get("classifiedSeedFrameCount"), 0)
    if classified_count < MIN_CLASSIFIED_SEED_FRAMES:
        reasons.append("classified_seed_frame_count_below_5")
    if classified_count < MIN_CLASSIFIED_SEED_FRAMES or _safe_float(taxonomy.get("dominantGapShare"), 0.0) <= MIN_DOMINANT_SHARE:
        reasons.append("no_dominant_generation_gap_above_half")
    return reasons


def build_decision_matrix(
    *,
    matrix: dict[str, object],
    taxonomy: dict[str, object],
) -> dict[str, object]:
    weak_reasons = _weak_evidence_reasons(matrix, taxonomy)
    if weak_reasons:
        return {
            "goalAchieved": False,
            "dominantBlockerClass": "weak_or_insufficient_generation_evidence",
            "nextCorrectiveFamily": NEXT_MANUAL_REVIEW,
            "successfulApproach": "C_evidence_only_blocker",
            "weakEvidenceReasons": weak_reasons,
            "rationale": "Saved artifacts do not contain enough proposal generation evidence to name a dominant generation blocker.",
        }
    dominant_gap_class = str(taxonomy.get("dominantGapClass") or BUCKET_UNRESOLVED)
    return {
        "goalAchieved": True,
        "dominantBlockerClass": dominant_gap_class,
        "nextCorrectiveFamily": _next_corrective_family(dominant_gap_class),
        "successfulApproach": "A_saved_artifact_proposal_generation_diagnosis",
        "weakEvidenceReasons": [],
        "rationale": "Seeded missing accepted frames have enough generated proposal evidence to name a dominant next corrective family.",
    }


def _promoted_runtime_options(validation_root: Path) -> dict[str, object]:
    arm_matrix_path = validation_root / "arm_matrix.json"
    if not arm_matrix_path.exists():
        return {}
    arms = _list_dicts(_load_json_dict(arm_matrix_path).get("arms"))
    for arm in arms:
        if str(arm.get("armName") or "") == "promoted_v6_baseline":
            runtime_options = arm.get("runtimeOptions")
            if isinstance(runtime_options, dict):
                return dict(runtime_options)
    return {}


def _markdown_summary(summary: dict[str, object], taxonomy: dict[str, object]) -> str:
    return "\n".join(
        [
            "# Candidate Proposal Generation Fix",
            "",
            f"- goalAchieved: {summary.get('goalAchieved')}",
            f"- dominantBlockerClass: {summary.get('dominantBlockerClass')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            f"- classifiedSeedFrameCount: {summary.get('classifiedSeedFrameCount')}",
            f"- gapClassCounts: {json.dumps(taxonomy.get('gapClassCounts') or {}, sort_keys=True)}",
            "",
        ]
    )


def run_promoted_v6_candidate_proposal_generation_fix(
    *,
    analysis_root: Path = DEFAULT_ANALYSIS_ROOT,
    support_blocker_root: Path = DEFAULT_SUPPORT_BLOCKER_ROOT,
    gold_truth_root: Path = DEFAULT_GOLD_TRUTH_ROOT,
    validation_root: Path = DEFAULT_VALIDATION_ROOT,
    retention_delta_root: Path = DEFAULT_RETENTION_DELTA_ROOT,
    suite_root: Path = DEFAULT_SUITE_ROOT,
    promoted_proof_root: Path = DEFAULT_PROMOTED_PROOF_ROOT,
    failing_source_clip_id: str = DEFAULT_FAILING_SOURCE_CLIP_ID,
) -> dict[str, object]:
    analysis_root = Path(analysis_root)
    support_blocker_root = Path(support_blocker_root)
    gold_truth_root = Path(gold_truth_root)
    validation_root = Path(validation_root)
    retention_delta_root = Path(retention_delta_root)
    suite_root = Path(suite_root)
    promoted_proof_root = Path(promoted_proof_root)

    support_blocker = _load_json_dict(support_blocker_root / "blocker_summary.json")
    seed_payload = _load_json_dict(gold_truth_root / "accepted_controlled_truth_seed.json")
    candidate_manifest = _load_json_dict(gold_truth_root / "candidate_frame_truth_manifest.json")
    retention_summary = _load_json_dict(retention_delta_root / "retention_delta_summary.json")
    suite_summary_path = suite_root / "suite_summary.json"
    suite_summary = _load_json_dict(suite_summary_path) if suite_summary_path.exists() else {}
    proof_summary = _load_optional_json_dict(promoted_proof_root / "proof_summary.json")
    ball_truth_layers = _load_optional_json_dict(promoted_proof_root / "ball_truth_layers.json")
    recovery_profile_matrix = _load_optional_json_dict(promoted_proof_root / "recovery_profile_matrix.json")

    matrix = build_seed_frame_proposal_generation_matrix(
        seed_payload=seed_payload,
        candidate_manifest=candidate_manifest,
        proof_summary=proof_summary,
        ball_truth_layers=ball_truth_layers,
        recovery_profile_matrix=recovery_profile_matrix,
    )
    taxonomy = build_proposal_generation_gap_taxonomy(matrix=matrix)
    crop_audit = build_seed_crop_failure_audit(
        proof_summary=proof_summary,
        recovery_profile_matrix=recovery_profile_matrix,
    )
    decision = build_decision_matrix(matrix=matrix, taxonomy=taxonomy)
    runtime_options = _promoted_runtime_options(validation_root)

    summary = {
        "generatedAt": _utc_now_iso(),
        "batchName": "candidate_proposal_generation_fix",
        "attemptNumber": 1,
        "attemptApproachFamily": "proposal_generation_diagnosis",
        "failingSourceClipId": failing_source_clip_id,
        "supportViabilityAdmissionStatus": support_blocker.get("batchStatus"),
        "retentionTruth": {
            "primaryRetentionBlockerClass": retention_summary.get("primaryRetentionBlockerClass"),
            "acceptedRetentionRatio": retention_summary.get("acceptedRetentionRatio"),
            "controlledRetentionRatio": retention_summary.get("controlledRetentionRatio"),
        },
        "suiteTruth": {
            "sourceRobustnessOutcome": suite_summary.get("sourceRobustnessOutcome"),
            "sourceRobustnessRecommendedNextLever": suite_summary.get("sourceRobustnessRecommendedNextLever"),
            "sourceRobustnessPromotionBlockers": suite_summary.get("sourceRobustnessPromotionBlockers"),
        },
        "runtimeOptions": runtime_options,
        "classifiedSeedFrameCount": matrix.get("classifiedSeedFrameCount"),
        "representedBootstrapWindowCount": matrix.get("representedBootstrapWindowCount"),
        "dominantGapFrameCount": taxonomy.get("dominantGapFrameCount"),
        "dominantGapShare": taxonomy.get("dominantGapShare"),
        **decision,
    }
    batch_outcome = {
        "batchName": "candidate_proposal_generation_fix",
        "attemptNumber": 1,
        "approachFamily": "proposal_generation_diagnosis",
        "goalAchieved": summary["goalAchieved"],
        "dominantBlockerClass": summary["dominantBlockerClass"],
        "nextCorrectiveFamily": summary["nextCorrectiveFamily"],
        "nextRecommendedBatch": summary["nextCorrectiveFamily"],
        "primaryRetentionBlockerClass": retention_summary.get("primaryRetentionBlockerClass"),
        "acceptedRetentionRatio": retention_summary.get("acceptedRetentionRatio"),
        "controlledRetentionRatio": retention_summary.get("controlledRetentionRatio"),
        "runtimeDefaultChanged": False,
        "artifacts": {
            "candidateProposalGenerationSummaryPath": str(analysis_root / "candidate_proposal_generation_summary.json"),
            "seedFrameProposalGenerationMatrixPath": str(analysis_root / "seed_frame_proposal_generation_matrix.json"),
            "proposalGenerationGapTaxonomyPath": str(analysis_root / "proposal_generation_gap_taxonomy.json"),
            "seedCropFailureAuditPath": str(analysis_root / "seed_crop_failure_audit.json"),
        },
    }

    _write_json(analysis_root / "candidate_proposal_generation_summary.json", summary)
    _write_json(analysis_root / "seed_frame_proposal_generation_matrix.json", matrix)
    _write_json(analysis_root / "proposal_generation_gap_taxonomy.json", taxonomy)
    _write_json(analysis_root / "seed_crop_failure_audit.json", crop_audit)
    _write_json(analysis_root / "decision_matrix.json", decision)
    _write_json(analysis_root / "batch_outcome_analysis.json", batch_outcome)
    _write_text(analysis_root / "batch_outcome_analysis.md", _markdown_summary(summary, taxonomy))

    return {
        "summary": summary,
        "seedFrameProposalGenerationMatrix": matrix,
        "gapTaxonomy": taxonomy,
        "seedCropFailureAudit": crop_audit,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-root", type=Path, default=DEFAULT_ANALYSIS_ROOT)
    parser.add_argument("--support-blocker-root", type=Path, default=DEFAULT_SUPPORT_BLOCKER_ROOT)
    parser.add_argument("--gold-truth-root", type=Path, default=DEFAULT_GOLD_TRUTH_ROOT)
    parser.add_argument("--validation-root", type=Path, default=DEFAULT_VALIDATION_ROOT)
    parser.add_argument("--retention-delta-root", type=Path, default=DEFAULT_RETENTION_DELTA_ROOT)
    parser.add_argument("--suite-root", type=Path, default=DEFAULT_SUITE_ROOT)
    parser.add_argument("--promoted-proof-root", type=Path, default=DEFAULT_PROMOTED_PROOF_ROOT)
    parser.add_argument("--failing-source-clip-id", default=DEFAULT_FAILING_SOURCE_CLIP_ID)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_promoted_v6_candidate_proposal_generation_fix(
        analysis_root=args.analysis_root,
        support_blocker_root=args.support_blocker_root,
        gold_truth_root=args.gold_truth_root,
        validation_root=args.validation_root,
        retention_delta_root=args.retention_delta_root,
        suite_root=args.suite_root,
        promoted_proof_root=args.promoted_proof_root,
        failing_source_clip_id=args.failing_source_clip_id,
    )
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
