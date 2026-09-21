from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
from collections import Counter
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402

DEFAULT_SUITE_ROOT = DEFAULT_STORAGE_ROOT / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
DEFAULT_ANALYSIS_ROOT = DEFAULT_SUITE_ROOT / "support_viability_truth_fix_v1"
DEFAULT_PROPOSAL_BLOCKER_ROOT = DEFAULT_SUITE_ROOT / "proposal_selection_admission_fix"
DEFAULT_GOLD_TRUTH_ROOT = (
    DEFAULT_SUITE_ROOT
    / "promoted_v6_source_manifest_and_gold_truth_refresh_v1"
    / "gold_truth_bootstrap_attempt_v1"
)
DEFAULT_VALIDATION_ROOT = DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_robustness_validation_v1"
DEFAULT_RETENTION_DELTA_ROOT = (
    DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
)
DEFAULT_FAILING_SOURCE_CLIP_ID = "trimed-5min.mp4"

NEXT_SUPPORT_VIABILITY = "support_viability_admission_fix"
NEXT_PROOF_PLUMBING = "proof_runtime_plumbing_fix"
NEXT_MANUAL_REVIEW = "manual_review_required"
NEXT_CANDIDATE_GENERATION = "candidate_proposal_generation_fix"

MIN_CLASSIFIED_SEED_FRAMES = 50
MIN_BOOTSTRAP_WINDOWS = 5


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


def _normalized_path(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    return str(Path(value).expanduser())


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


def _promoted_runtime_options(validation_payload: dict[str, object]) -> dict[str, object]:
    arms = _list_dicts(validation_payload.get("arms"))
    for arm in arms:
        if str(arm.get("armName") or "") != "promoted_v6_baseline":
            continue
        runtime_options = arm.get("runtimeOptions")
        if isinstance(runtime_options, dict):
            return dict(runtime_options)
    return {}


def build_proof_runtime_seed_path_audit(
    *,
    validation_root: Path,
    expected_seed_path: Path,
) -> dict[str, object]:
    arm_matrix_path = validation_root / "arm_matrix.json"
    if not arm_matrix_path.exists():
        return {
            "auditStatus": "failed",
            "expectedSeedPath": str(expected_seed_path),
            "observedSeedPath": None,
            "reason": "arm_matrix_missing",
        }
    runtime_options = _promoted_runtime_options(_load_json_dict(arm_matrix_path))
    observed_seed_path = runtime_options.get("proposalSelectionTruthSeedPath")
    expected = _normalized_path(str(expected_seed_path))
    observed = _normalized_path(observed_seed_path)
    if observed != expected:
        return {
            "auditStatus": "failed",
            "expectedSeedPath": expected,
            "observedSeedPath": observed or None,
            "reason": "proposal_selection_truth_seed_path_mismatch",
            "runtimeOptions": runtime_options,
        }
    return {
        "auditStatus": "passed",
        "expectedSeedPath": expected,
        "observedSeedPath": observed,
        "reason": None,
        "runtimeOptions": runtime_options,
    }


def _has_support_or_viability_evidence(candidate: dict[str, object]) -> bool:
    evidence_keys = {
        "supportStatus",
        "supportEvidence",
        "supportSource",
        "supportedByPlayer",
        "playerSupported",
        "playerSupportDistance",
        "viabilityStatus",
        "viabilityClass",
        "viabilityScore",
        "selectedCandidateViability",
    }
    return any(key in candidate for key in evidence_keys)


def _classify_seed_frame(seed_row: dict[str, object], candidate: dict[str, object] | None) -> dict[str, object]:
    frame_id = _safe_int(seed_row.get("frameId"), -1)
    if candidate is None:
        return {
            "frameId": frame_id,
            "candidateFrameId": seed_row.get("candidateFrameId"),
            "windowId": seed_row.get("windowId"),
            "proposalPresent": False,
            "selectedInPromoted": False,
            "supportOrViabilityEvidencePresent": False,
            "gapClass": "candidate_proposal_absent",
            "lineageComplete": bool(seed_row.get("lineage")),
        }

    signal_sources = [
        str(source)
        for source in candidate.get("promotedSignalSources", [])
        if isinstance(source, str)
    ] if isinstance(candidate.get("promotedSignalSources"), list) else []
    proposal_present = bool(candidate.get("proposalEvidenceAvailable")) or any(
        source in signal_sources
        for source in ("promoted_recovery_profile_proposal", "promoted_probe", "promoted_observed", "promoted_accepted")
    )
    selected = "promoted_accepted" in signal_sources or bool(candidate.get("selectedInPromoted"))
    support_or_viability_evidence_present = _has_support_or_viability_evidence(candidate)

    if selected:
        gap_class = "selected_in_promoted"
    elif not proposal_present:
        gap_class = "candidate_proposal_absent"
    elif bool(candidate.get("edgeGuardRejected")):
        gap_class = "edge_guard_loss"
    elif bool(candidate.get("continuityGuardRejected")):
        gap_class = "continuity_guard_loss"
    elif bool(candidate.get("viabilityRegressionRejected")):
        gap_class = "viability_regression_loss"
    elif not support_or_viability_evidence_present:
        gap_class = "support_viability_evidence_gap"
    else:
        gap_class = "support_viability_filter_loss"

    return {
        "frameId": frame_id,
        "candidateFrameId": candidate.get("candidateFrameId") or seed_row.get("candidateFrameId"),
        "windowId": candidate.get("windowId") or seed_row.get("windowId"),
        "proposalPresent": proposal_present,
        "selectedInPromoted": selected,
        "supportOrViabilityEvidencePresent": support_or_viability_evidence_present,
        "gapClass": gap_class,
        "promotedSignalSources": signal_sources,
        "lineageComplete": bool(candidate.get("lineageComplete")) or bool(seed_row.get("lineage")),
    }


def build_seed_frame_support_viability_matrix(
    *,
    seed_payload: dict[str, object],
    candidate_manifest: dict[str, object],
) -> dict[str, object]:
    candidates_by_frame = _candidate_frames_by_frame(candidate_manifest)
    frames = [
        _classify_seed_frame(seed_row, candidates_by_frame.get(_safe_int(seed_row.get("frameId"), -1)))
        for seed_row in _seed_rows(seed_payload)
    ]
    counts = Counter(str(frame.get("gapClass") or "unclassified") for frame in frames)
    return {
        "generatedAt": _utc_now_iso(),
        "seedFrameCount": len(_seed_rows(seed_payload)),
        "classifiedSeedFrameCount": len(frames),
        "representedBootstrapWindowCount": _safe_int(candidate_manifest.get("representedBootstrapWindowCount"), 0),
        "gapClassCounts": dict(sorted(counts.items())),
        "frames": frames,
    }


def build_support_viability_gap_taxonomy(
    *,
    matrix: dict[str, object],
) -> dict[str, object]:
    counts = {
        str(key): _safe_int(value)
        for key, value in dict(matrix.get("gapClassCounts") or {}).items()
    }
    dominant_gap_class = "unresolved_missing_evidence"
    dominant_count = 0
    if counts:
        dominant_gap_class, dominant_count = sorted(
            counts.items(),
            key=lambda item: (-item[1], item[0]),
        )[0]
    classified = _safe_int(matrix.get("classifiedSeedFrameCount"), 0)
    dominant_share = round(dominant_count / classified, 3) if classified else 0.0
    return {
        "generatedAt": _utc_now_iso(),
        "classifiedSeedFrameCount": classified,
        "dominantGapClass": dominant_gap_class,
        "dominantGapFrameCount": dominant_count,
        "dominantGapShare": dominant_share,
        "gapClassCounts": counts,
    }


def _weak_evidence_reasons(matrix: dict[str, object]) -> list[str]:
    reasons: list[str] = []
    if _safe_int(matrix.get("classifiedSeedFrameCount"), 0) < MIN_CLASSIFIED_SEED_FRAMES:
        reasons.append("classified_seed_frame_count_below_50")
    if _safe_int(matrix.get("representedBootstrapWindowCount"), 0) < MIN_BOOTSTRAP_WINDOWS:
        reasons.append("represented_bootstrap_window_count_below_5")
    return reasons


def build_decision_matrix(
    *,
    proof_runtime_seed_path_audit: dict[str, object],
    matrix: dict[str, object],
    gap_taxonomy: dict[str, object],
) -> dict[str, object]:
    weak_reasons = _weak_evidence_reasons(matrix)
    if str(proof_runtime_seed_path_audit.get("auditStatus") or "") != "passed":
        return {
            "goalAchieved": True,
            "dominantBlockerClass": "proof_runtime_seed_path_mismatch",
            "nextCorrectiveFamily": NEXT_PROOF_PLUMBING,
            "successfulApproach": "B_proof_runtime_audit_fallback",
            "weakEvidenceReasons": [],
            "rationale": "The promoted validation arm did not consume the expected proposal-selection truth seed path.",
        }
    if weak_reasons:
        return {
            "goalAchieved": False,
            "dominantBlockerClass": "weak_or_insufficient_evidence",
            "nextCorrectiveFamily": NEXT_MANUAL_REVIEW,
            "successfulApproach": "C_conservative_review_overlay_fallback",
            "weakEvidenceReasons": weak_reasons,
            "rationale": "The saved-artifact seed surface is too small to name a detector-side blocker deterministically.",
        }

    dominant_gap_class = str(gap_taxonomy.get("dominantGapClass") or "unresolved_missing_evidence")
    if dominant_gap_class == "candidate_proposal_absent":
        next_family = NEXT_CANDIDATE_GENERATION
    elif dominant_gap_class in {
        "support_viability_evidence_gap",
        "support_viability_filter_loss",
        "viability_regression_loss",
    }:
        next_family = NEXT_SUPPORT_VIABILITY
    else:
        next_family = NEXT_MANUAL_REVIEW
    return {
        "goalAchieved": True,
        "dominantBlockerClass": dominant_gap_class,
        "nextCorrectiveFamily": next_family,
        "successfulApproach": "A_saved_artifact_support_viability_attribution",
        "weakEvidenceReasons": [],
        "rationale": "Seed frames are represented with enough proposal evidence to select the next corrective family.",
    }


def _markdown_summary(summary: dict[str, object], taxonomy: dict[str, object], audit: dict[str, object]) -> str:
    return "\n".join(
        [
            "# Support/Viability Truth Fix",
            "",
            f"- goalAchieved: {summary.get('goalAchieved')}",
            f"- dominantBlockerClass: {summary.get('dominantBlockerClass')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            f"- classifiedSeedFrameCount: {summary.get('classifiedSeedFrameCount')}",
            f"- proofRuntimeSeedPathAudit: {audit.get('auditStatus')}",
            f"- gapClassCounts: {json.dumps(taxonomy.get('gapClassCounts') or {}, sort_keys=True)}",
            "",
        ]
    )


def run_promoted_v6_support_viability_truth_fix(
    *,
    analysis_root: Path = DEFAULT_ANALYSIS_ROOT,
    proposal_blocker_root: Path = DEFAULT_PROPOSAL_BLOCKER_ROOT,
    gold_truth_root: Path = DEFAULT_GOLD_TRUTH_ROOT,
    validation_root: Path = DEFAULT_VALIDATION_ROOT,
    retention_delta_root: Path = DEFAULT_RETENTION_DELTA_ROOT,
    suite_root: Path = DEFAULT_SUITE_ROOT,
    failing_source_clip_id: str = DEFAULT_FAILING_SOURCE_CLIP_ID,
) -> dict[str, object]:
    analysis_root = Path(analysis_root)
    proposal_blocker_root = Path(proposal_blocker_root)
    gold_truth_root = Path(gold_truth_root)
    validation_root = Path(validation_root)
    retention_delta_root = Path(retention_delta_root)
    suite_root = Path(suite_root)

    blocker_summary = _load_json_dict(proposal_blocker_root / "blocker_summary.json")
    seed_path = gold_truth_root / "accepted_controlled_truth_seed.json"
    seed_payload = _load_json_dict(seed_path)
    candidate_manifest = _load_json_dict(gold_truth_root / "candidate_frame_truth_manifest.json")
    retention_summary = _load_json_dict(retention_delta_root / "retention_delta_summary.json")
    suite_summary_path = suite_root / "suite_summary.json"
    suite_summary = _load_json_dict(suite_summary_path) if suite_summary_path.exists() else {}

    audit = build_proof_runtime_seed_path_audit(
        validation_root=validation_root,
        expected_seed_path=seed_path,
    )
    matrix = build_seed_frame_support_viability_matrix(
        seed_payload=seed_payload,
        candidate_manifest=candidate_manifest,
    )
    taxonomy = build_support_viability_gap_taxonomy(matrix=matrix)
    decision = build_decision_matrix(
        proof_runtime_seed_path_audit=audit,
        matrix=matrix,
        gap_taxonomy=taxonomy,
    )
    summary = {
        "generatedAt": _utc_now_iso(),
        "batchName": "support_viability_truth_fix",
        "attemptNumber": 1,
        "attemptApproachFamily": "support_viability_truth_analysis",
        "failingSourceClipId": failing_source_clip_id,
        "proposalBlockerStatus": blocker_summary.get("batchStatus"),
        "retentionTruth": {
            "primaryRetentionBlockerClass": retention_summary.get("primaryRetentionBlockerClass"),
            "acceptedRetentionRatio": retention_summary.get("acceptedRetentionRatio"),
            "controlledRetentionRatio": retention_summary.get("controlledRetentionRatio"),
        },
        "suiteVerdict": suite_summary.get("suiteVerdict"),
        "classifiedSeedFrameCount": matrix.get("classifiedSeedFrameCount"),
        "representedBootstrapWindowCount": matrix.get("representedBootstrapWindowCount"),
        "dominantGapFrameCount": taxonomy.get("dominantGapFrameCount"),
        "dominantGapShare": taxonomy.get("dominantGapShare"),
        **decision,
    }
    batch_outcome = {
        "batchName": "support_viability_truth_fix",
        "attemptNumber": 1,
        "approachFamily": "support_viability_truth_analysis",
        "goalAchieved": summary["goalAchieved"],
        "dominantBlockerClass": summary["dominantBlockerClass"],
        "nextCorrectiveFamily": summary["nextCorrectiveFamily"],
        "nextRecommendedBatch": summary["nextCorrectiveFamily"],
        "artifacts": {
            "supportViabilityTruthSummaryPath": str(analysis_root / "support_viability_truth_summary.json"),
            "seedFrameSupportViabilityMatrixPath": str(analysis_root / "seed_frame_support_viability_matrix.json"),
            "supportViabilityGapTaxonomyPath": str(analysis_root / "support_viability_gap_taxonomy.json"),
            "proofRuntimeSeedPathAuditPath": str(analysis_root / "proof_runtime_seed_path_audit.json"),
        },
    }

    _write_json(analysis_root / "support_viability_truth_summary.json", summary)
    _write_json(analysis_root / "seed_frame_support_viability_matrix.json", matrix)
    _write_json(analysis_root / "support_viability_gap_taxonomy.json", taxonomy)
    _write_json(analysis_root / "proof_runtime_seed_path_audit.json", audit)
    _write_json(analysis_root / "decision_matrix.json", decision)
    _write_json(analysis_root / "batch_outcome_analysis.json", batch_outcome)
    _write_text(analysis_root / "batch_outcome_analysis.md", _markdown_summary(summary, taxonomy, audit))

    return {
        "summary": summary,
        "seedFrameSupportViabilityMatrix": matrix,
        "gapTaxonomy": taxonomy,
        "proofRuntimeSeedPathAudit": audit,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-root", type=Path, default=DEFAULT_ANALYSIS_ROOT)
    parser.add_argument("--proposal-blocker-root", type=Path, default=DEFAULT_PROPOSAL_BLOCKER_ROOT)
    parser.add_argument("--gold-truth-root", type=Path, default=DEFAULT_GOLD_TRUTH_ROOT)
    parser.add_argument("--validation-root", type=Path, default=DEFAULT_VALIDATION_ROOT)
    parser.add_argument("--retention-delta-root", type=Path, default=DEFAULT_RETENTION_DELTA_ROOT)
    parser.add_argument("--suite-root", type=Path, default=DEFAULT_SUITE_ROOT)
    parser.add_argument("--failing-source-clip-id", default=DEFAULT_FAILING_SOURCE_CLIP_ID)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_promoted_v6_support_viability_truth_fix(
        analysis_root=args.analysis_root,
        proposal_blocker_root=args.proposal_blocker_root,
        gold_truth_root=args.gold_truth_root,
        validation_root=args.validation_root,
        retention_delta_root=args.retention_delta_root,
        suite_root=args.suite_root,
        failing_source_clip_id=args.failing_source_clip_id,
    )
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
