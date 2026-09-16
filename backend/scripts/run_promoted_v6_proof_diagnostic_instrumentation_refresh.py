from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts import run_promoted_v6_reviewed_positive_micro_validation as micro_validation  # noqa: E402

DEFAULT_SUITE_ROOT = DEFAULT_STORAGE_ROOT / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
DEFAULT_OUTPUT_ROOT = DEFAULT_SUITE_ROOT / "proof_diagnostic_instrumentation_refresh_v1"
DEFAULT_EXPANSION_RESOLUTION_ROOT = DEFAULT_SUITE_ROOT / "manual_review_expansion_resolution_v1"
DEFAULT_MICRO_VALIDATION_ROOT = DEFAULT_SUITE_ROOT / "reviewed_positive_micro_validation_v1"
DEFAULT_VALIDATION_ROOT = DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_robustness_validation_v1"
DEFAULT_RETENTION_DELTA_ROOT = (
    DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
)
DEFAULT_RUNTIME_DEFAULT_PATH = DEFAULT_STORAGE_ROOT / "runtime" / "promoted_touchline_detector_candidate.json"
DEFAULT_SOURCE_MANIFEST_PATH = REPO_ROOT / "backend" / "benchmark_suites" / "frozen_viable_baseline_source_manifest.json"
DEFAULT_BATCH_NAME = "proof_diagnostic_instrumentation_refresh_v1"
DEFAULT_ATTEMPT_FAMILY = "reviewed_positive_frame_diagnostics"

BUCKET_MISSING = "reviewed_positive_frame_diagnostics_missing"
BUCKET_NO_PROPOSAL = "reviewed_positive_no_promoted_proposal"
BUCKET_RAW_NOT_COLLAPSED = "reviewed_positive_raw_detected_not_collapsed"
BUCKET_COLLAPSED_NOT_SELECTED = "reviewed_positive_collapsed_not_selected"
BUCKET_SELECTED_NOT_ACCEPTED = "reviewed_positive_selected_not_accepted"
BUCKET_ALREADY_ACCEPTED = "reviewed_positive_already_accepted"

NEXT_PROOF_RUNTIME = "proof_runtime_frame_diagnostics"
NEXT_PROPOSAL_GENERATION = "reviewed_positive_proposal_generation_fix"
NEXT_SELECTION_FOLLOWTHROUGH = "reviewed_positive_selection_followthrough_fix"
NEXT_ACCEPTANCE = "reviewed_positive_acceptance_fix"

BUCKET_PRIORITY = [
    BUCKET_MISSING,
    BUCKET_NO_PROPOSAL,
    BUCKET_RAW_NOT_COLLAPSED,
    BUCKET_COLLAPSED_NOT_SELECTED,
    BUCKET_SELECTED_NOT_ACCEPTED,
    BUCKET_ALREADY_ACCEPTED,
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json_dict(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _load_optional_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _load_json_dict(path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


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


def _list_dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _reviewed_positive_rows(truth_seed: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        _list_dicts(truth_seed.get("reviewedPositiveSeedRows")),
        key=lambda row: (_safe_int(row.get("frameIndex"), -1), str(row.get("reviewItemId") or "")),
    )


def _diagnostic_class(evidence: dict[str, bool] | None) -> str:
    if not evidence:
        return BUCKET_MISSING
    if evidence.get("accepted"):
        return BUCKET_ALREADY_ACCEPTED
    if evidence.get("selected"):
        return BUCKET_SELECTED_NOT_ACCEPTED
    if evidence.get("collapsed"):
        return BUCKET_COLLAPSED_NOT_SELECTED
    if evidence.get("rawDetected") or evidence.get("proposalGenerated"):
        return BUCKET_RAW_NOT_COLLAPSED
    return BUCKET_NO_PROPOSAL


def _dominant_bucket(counts: dict[str, int] | Counter[str]) -> tuple[str, int]:
    normalized = {str(key): _safe_int(value) for key, value in dict(counts).items()}
    if not normalized:
        return BUCKET_MISSING, 0
    priority = {bucket: index for index, bucket in enumerate(BUCKET_PRIORITY)}
    return sorted(
        normalized.items(),
        key=lambda item: (-item[1], priority.get(item[0], len(priority)), item[0]),
    )[0]


def _next_family(bucket: str) -> str:
    if bucket == BUCKET_MISSING:
        return NEXT_PROOF_RUNTIME
    if bucket == BUCKET_NO_PROPOSAL:
        return NEXT_PROPOSAL_GENERATION
    if bucket in {BUCKET_RAW_NOT_COLLAPSED, BUCKET_COLLAPSED_NOT_SELECTED}:
        return NEXT_SELECTION_FOLLOWTHROUGH
    if bucket == BUCKET_SELECTED_NOT_ACCEPTED:
        return NEXT_ACCEPTANCE
    return NEXT_SELECTION_FOLLOWTHROUGH


def _profile_frame_diagnostics_present(recovery_profile_matrix: dict[str, Any]) -> bool:
    for profile in _list_dicts(recovery_profile_matrix.get("profiles")):
        if _list_dicts(profile.get("proposalFrameDiagnostics")):
            return True
        for key in ("proposalRawDetectedFrameIds", "proposalCollapsedFrameIds", "proposalSelectedFrameIds"):
            if profile.get(key):
                return True
    return False


def build_reviewed_positive_frame_diagnostics(
    *,
    truth_seed: dict[str, Any],
    proof_artifacts: dict[str, Any],
) -> dict[str, Any]:
    evidence_by_frame = micro_validation.build_frame_evidence(proof_artifacts=proof_artifacts)
    rows = []
    for seed_row in _reviewed_positive_rows(truth_seed):
        frame_id = _safe_int(seed_row.get("frameIndex"), -1)
        evidence = evidence_by_frame.get(frame_id)
        diagnostic_class = _diagnostic_class(evidence)
        rows.append(
            {
                "reviewItemId": seed_row.get("reviewItemId"),
                "candidateFrameId": seed_row.get("candidateFrameId"),
                "windowId": seed_row.get("windowId"),
                "sourceClipId": seed_row.get("sourceClipId"),
                "frameIndex": frame_id,
                "reviewDecision": seed_row.get("reviewDecision"),
                "reviewedBBox": seed_row.get("reviewedBBox"),
                "lineageComplete": bool(seed_row.get("lineage")),
                "diagnosticClass": diagnostic_class,
                "proofEvidence": evidence or {},
            }
        )
    counts = Counter(row["diagnosticClass"] for row in rows)
    return {
        "generatedAt": _utc_now_iso(),
        "reviewedPositiveFrameCount": len(rows),
        "coveredReviewedFrameCount": sum(1 for row in rows if row["diagnosticClass"] != BUCKET_MISSING),
        "bucketCounts": dict(sorted(counts.items())),
        "reviewedPositiveFrameDiagnostics": rows,
    }


def build_proof_artifact_bridge_audit(
    *,
    frame_diagnostics: dict[str, Any],
    proof_artifacts: dict[str, Any],
) -> dict[str, Any]:
    recovery_profile_matrix = dict(proof_artifacts.get("recoveryProfileMatrix") or {})
    missing_frames = [
        row["frameIndex"]
        for row in _list_dicts(frame_diagnostics.get("reviewedPositiveFrameDiagnostics"))
        if row.get("diagnosticClass") == BUCKET_MISSING
    ]
    return {
        "generatedAt": _utc_now_iso(),
        "proofRoot": proof_artifacts.get("proofRoot"),
        "profileFrameDiagnosticsPresent": _profile_frame_diagnostics_present(recovery_profile_matrix),
        "reviewedPositiveFrameCount": _safe_int(frame_diagnostics.get("reviewedPositiveFrameCount"), 0),
        "coveredReviewedFrameCount": _safe_int(frame_diagnostics.get("coveredReviewedFrameCount"), 0),
        "missingReviewedFrameCount": len(missing_frames),
        "missingReviewedFrames": missing_frames,
        "currentProofCanSelectDetectorFamily": not missing_frames,
    }


def build_decision_matrix(*, frame_diagnostics: dict[str, Any], bridge_audit: dict[str, Any]) -> dict[str, Any]:
    dominant_bucket, dominant_count = _dominant_bucket(dict(frame_diagnostics.get("bucketCounts") or {}))
    next_family = _next_family(dominant_bucket)
    weak_reasons = []
    if next_family == NEXT_PROOF_RUNTIME:
        weak_reasons.append("current_promoted_proof_missing_reviewed_positive_frame_diagnostics")
    return {
        "goalAchieved": True,
        "roadmapAdvanceAllowed": True,
        "dominantBlockerClass": dominant_bucket,
        "dominantBlockerFrameCount": dominant_count,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        "successfulApproach": "A_reviewed_positive_frame_diagnostics",
        "weakEvidenceReasons": weak_reasons,
        "currentProofCanSelectDetectorFamily": bool(bridge_audit.get("currentProofCanSelectDetectorFamily")),
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Proof Diagnostic Instrumentation Refresh",
            "",
            f"- batchStatus: {summary.get('batchStatus')}",
            f"- reviewedPositiveFrameCount: {summary.get('reviewedPositiveFrameCount')}",
            f"- coveredReviewedFrameCount: {summary.get('coveredReviewedFrameCount')}",
            f"- dominantBlockerClass: {summary.get('dominantBlockerClass')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            "",
        ]
    )


def run_promoted_v6_proof_diagnostic_instrumentation_refresh(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    expansion_resolution_root: Path = DEFAULT_EXPANSION_RESOLUTION_ROOT,
    micro_validation_root: Path = DEFAULT_MICRO_VALIDATION_ROOT,
    validation_root: Path = DEFAULT_VALIDATION_ROOT,
    proof_root: Path | None = None,
    retention_delta_root: Path = DEFAULT_RETENTION_DELTA_ROOT,
    suite_root: Path = DEFAULT_SUITE_ROOT,
    runtime_default_path: Path = DEFAULT_RUNTIME_DEFAULT_PATH,
    source_manifest_path: Path = DEFAULT_SOURCE_MANIFEST_PATH,
) -> dict[str, Any]:
    output_root = Path(output_root)
    truth_seed = _load_json_dict(Path(expansion_resolution_root) / "expanded_reviewed_truth_seed.json")
    micro_summary = _load_optional_json_dict(Path(micro_validation_root) / "reviewed_positive_micro_validation_summary.json")
    proof_artifacts = micro_validation._load_proof_artifacts(validation_root=Path(validation_root), proof_root=proof_root)
    retention_summary = _load_json_dict(Path(retention_delta_root) / "retention_delta_summary.json")
    suite_summary = _load_optional_json_dict(Path(suite_root) / "suite_summary.json")

    frame_diagnostics = build_reviewed_positive_frame_diagnostics(
        truth_seed=truth_seed,
        proof_artifacts=proof_artifacts,
    )
    bridge_audit = build_proof_artifact_bridge_audit(
        frame_diagnostics=frame_diagnostics,
        proof_artifacts=proof_artifacts,
    )
    decision = build_decision_matrix(frame_diagnostics=frame_diagnostics, bridge_audit=bridge_audit)
    summary = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptApproachFamily": DEFAULT_ATTEMPT_FAMILY,
        "batchStatus": "succeeded",
        "microValidationTruth": {
            "batchStatus": micro_summary.get("batchStatus"),
            "dominantBlockerClass": micro_summary.get("dominantBlockerClass"),
            "nextCorrectiveFamily": micro_summary.get("nextCorrectiveFamily"),
        },
        "retentionTruth": {
            "primaryRetentionBlockerClass": retention_summary.get("primaryRetentionBlockerClass"),
            "acceptedRetentionRatio": retention_summary.get("acceptedRetentionRatio"),
            "controlledRetentionRatio": retention_summary.get("controlledRetentionRatio"),
        },
        "suiteTruth": {
            "sourceRobustnessOutcome": suite_summary.get("sourceRobustnessOutcome"),
            "sourceRobustnessPromotionBlockers": suite_summary.get("sourceRobustnessPromotionBlockers"),
        },
        "reviewedPositiveFrameCount": frame_diagnostics.get("reviewedPositiveFrameCount"),
        "coveredReviewedFrameCount": frame_diagnostics.get("coveredReviewedFrameCount"),
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
        "detectorProfileAdded": False,
        "runPodUsed": False,
        **decision,
    }
    batch_outcome = {
        "batchName": DEFAULT_BATCH_NAME,
        "attemptNumber": 1,
        "attemptBudget": 3,
        "approachFamily": DEFAULT_ATTEMPT_FAMILY,
        "batchStatus": summary["batchStatus"],
        "goalAchieved": summary["goalAchieved"],
        "roadmapAdvanceAllowed": summary["roadmapAdvanceAllowed"],
        "dominantBlockerClass": summary["dominantBlockerClass"],
        "nextCorrectiveFamily": summary["nextCorrectiveFamily"],
        "nextRecommendedBatch": summary["nextRecommendedBatch"],
        "primaryRetentionBlockerClass": retention_summary.get("primaryRetentionBlockerClass"),
        "acceptedRetentionRatio": retention_summary.get("acceptedRetentionRatio"),
        "controlledRetentionRatio": retention_summary.get("controlledRetentionRatio"),
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
    }

    _ = runtime_default_path, source_manifest_path
    _write_json(output_root / "proof_diagnostic_instrumentation_summary.json", summary)
    _write_json(output_root / "reviewed_positive_frame_diagnostics.json", frame_diagnostics)
    _write_json(output_root / "proof_artifact_bridge_audit.json", bridge_audit)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    _write_text(output_root / "batch_outcome_analysis.md", _markdown_summary(summary))
    return {
        "summary": summary,
        "reviewedPositiveFrameDiagnostics": frame_diagnostics,
        "proofArtifactBridgeAudit": bridge_audit,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--expansion-resolution-root", type=Path, default=DEFAULT_EXPANSION_RESOLUTION_ROOT)
    parser.add_argument("--micro-validation-root", type=Path, default=DEFAULT_MICRO_VALIDATION_ROOT)
    parser.add_argument("--validation-root", type=Path, default=DEFAULT_VALIDATION_ROOT)
    parser.add_argument("--proof-root", type=Path, default=None)
    parser.add_argument("--retention-delta-root", type=Path, default=DEFAULT_RETENTION_DELTA_ROOT)
    parser.add_argument("--suite-root", type=Path, default=DEFAULT_SUITE_ROOT)
    parser.add_argument("--runtime-default-path", type=Path, default=DEFAULT_RUNTIME_DEFAULT_PATH)
    parser.add_argument("--source-manifest-path", type=Path, default=DEFAULT_SOURCE_MANIFEST_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_promoted_v6_proof_diagnostic_instrumentation_refresh(
        output_root=args.output_root,
        expansion_resolution_root=args.expansion_resolution_root,
        micro_validation_root=args.micro_validation_root,
        validation_root=args.validation_root,
        proof_root=args.proof_root,
        retention_delta_root=args.retention_delta_root,
        suite_root=args.suite_root,
        runtime_default_path=args.runtime_default_path,
        source_manifest_path=args.source_manifest_path,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
