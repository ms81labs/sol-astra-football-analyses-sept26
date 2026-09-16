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
DEFAULT_OUTPUT_ROOT = DEFAULT_SUITE_ROOT / "proof_runtime_frame_diagnostics_v1"
DEFAULT_EXPANSION_RESOLUTION_ROOT = DEFAULT_SUITE_ROOT / "manual_review_expansion_resolution_v1"
DEFAULT_MICRO_VALIDATION_ROOT = DEFAULT_SUITE_ROOT / "reviewed_positive_micro_validation_v1"
DEFAULT_RETENTION_DELTA_ROOT = (
    DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
)
DEFAULT_BATCH_NAME = "proof_runtime_frame_diagnostics_v1"
DEFAULT_ATTEMPT_FAMILY = "fresh_local_proof_frame_diagnostics"

BUCKET_NO_PROPOSAL = "reviewed_positive_no_promoted_proposal"
BUCKET_RAW_NOT_COLLAPSED = "reviewed_positive_raw_detected_not_collapsed"
BUCKET_COLLAPSED_NOT_SELECTED = "reviewed_positive_collapsed_not_selected"
BUCKET_SELECTED_NOT_ACCEPTED = "reviewed_positive_selected_not_accepted"
BUCKET_ALREADY_ACCEPTED = "reviewed_positive_already_accepted"
BUCKET_RUNTIME_DIAGNOSTIC_GAP = "proof_runtime_frame_diagnostics_incomplete"

NEXT_PROPOSAL_GENERATION = "reviewed_positive_proposal_generation_fix"
NEXT_SELECTION_FOLLOWTHROUGH = "reviewed_positive_selection_followthrough_fix"
NEXT_ACCEPTANCE = "reviewed_positive_acceptance_fix"
NEXT_DIAGNOSTIC_REFRESH = "proof_diagnostic_instrumentation_refresh"

BUCKET_PRIORITY = [
    BUCKET_RUNTIME_DIAGNOSTIC_GAP,
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


def _profile_diagnostics_present(recovery_profile_matrix: dict[str, Any]) -> bool:
    for profile in _list_dicts(recovery_profile_matrix.get("profiles")):
        if _list_dicts(profile.get("proposalFrameDiagnostics")):
            return True
        if (
            profile.get("proposalRawDetectedFrameIds")
            or profile.get("proposalCollapsedFrameIds")
            or profile.get("proposalSelectedFrameIds")
        ):
            return True
    return False


def _diagnostic_class(evidence: dict[str, bool] | None, *, runtime_diagnostics_present: bool) -> str:
    if not runtime_diagnostics_present:
        return BUCKET_RUNTIME_DIAGNOSTIC_GAP
    if not evidence:
        return BUCKET_NO_PROPOSAL
    if evidence.get("accepted"):
        return BUCKET_ALREADY_ACCEPTED
    if evidence.get("selected"):
        return BUCKET_SELECTED_NOT_ACCEPTED
    if evidence.get("collapsed"):
        return BUCKET_COLLAPSED_NOT_SELECTED
    if evidence.get("rawDetected") or evidence.get("proposalGenerated"):
        return BUCKET_RAW_NOT_COLLAPSED
    return BUCKET_NO_PROPOSAL


def _dominant_bucket(counts: dict[str, int]) -> tuple[str, int]:
    if not counts:
        return BUCKET_RUNTIME_DIAGNOSTIC_GAP, 0
    priority = {bucket: index for index, bucket in enumerate(BUCKET_PRIORITY)}
    return sorted(
        ((str(key), _safe_int(value)) for key, value in counts.items()),
        key=lambda item: (-item[1], priority.get(item[0], len(priority)), item[0]),
    )[0]


def _next_family(bucket: str) -> str:
    if bucket == BUCKET_NO_PROPOSAL:
        return NEXT_PROPOSAL_GENERATION
    if bucket in {BUCKET_RAW_NOT_COLLAPSED, BUCKET_COLLAPSED_NOT_SELECTED}:
        return NEXT_SELECTION_FOLLOWTHROUGH
    if bucket == BUCKET_SELECTED_NOT_ACCEPTED:
        return NEXT_ACCEPTANCE
    if bucket == BUCKET_ALREADY_ACCEPTED:
        return NEXT_SELECTION_FOLLOWTHROUGH
    return NEXT_DIAGNOSTIC_REFRESH


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Proof Runtime Frame Diagnostics",
            "",
            f"- batchStatus: {summary.get('batchStatus')}",
            f"- reviewedPositiveFrameCount: {summary.get('reviewedPositiveFrameCount')}",
            f"- classifiedReviewedFrameCount: {summary.get('classifiedReviewedFrameCount')}",
            f"- dominantBlockerClass: {summary.get('dominantBlockerClass')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            f"- freshProofRoot: {summary.get('freshProofRoot')}",
            "",
        ]
    )


def run_promoted_v6_proof_runtime_frame_diagnostics(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    expansion_resolution_root: Path = DEFAULT_EXPANSION_RESOLUTION_ROOT,
    proof_root: Path,
    micro_validation_root: Path = DEFAULT_MICRO_VALIDATION_ROOT,
    retention_delta_root: Path = DEFAULT_RETENTION_DELTA_ROOT,
    suite_root: Path = DEFAULT_SUITE_ROOT,
) -> dict[str, Any]:
    output_root = Path(output_root)
    proof_root = Path(proof_root)
    truth_seed = _load_json_dict(Path(expansion_resolution_root) / "expanded_reviewed_truth_seed.json")
    micro_summary = _load_optional_json_dict(Path(micro_validation_root) / "reviewed_positive_micro_validation_summary.json")
    retention_summary = _load_json_dict(Path(retention_delta_root) / "retention_delta_summary.json")
    suite_summary = _load_optional_json_dict(Path(suite_root) / "suite_summary.json")
    proof_artifacts = {
        "proofRoot": str(proof_root),
        "recoveryProfileMatrix": _load_optional_json_dict(proof_root / "recovery_profile_matrix.json"),
        "proofSummary": _load_optional_json_dict(proof_root / "proof_summary.json"),
        "selectedClusterDelta": _load_optional_json_dict(proof_root / "selected_cluster_delta.json"),
        "ballTruthLayers": _load_optional_json_dict(proof_root / "ball_truth_layers.json"),
    }
    recovery_profile_matrix = dict(proof_artifacts.get("recoveryProfileMatrix") or {})
    runtime_diagnostics_present = _profile_diagnostics_present(recovery_profile_matrix)
    evidence_by_frame = micro_validation.build_frame_evidence(proof_artifacts=proof_artifacts)

    rows: list[dict[str, Any]] = []
    for seed_row in _reviewed_positive_rows(truth_seed):
        frame_id = _safe_int(seed_row.get("frameIndex"), -1)
        evidence = evidence_by_frame.get(frame_id)
        diagnostic_class = _diagnostic_class(
            evidence,
            runtime_diagnostics_present=runtime_diagnostics_present,
        )
        rows.append(
            {
                "reviewItemId": seed_row.get("reviewItemId"),
                "candidateFrameId": seed_row.get("candidateFrameId"),
                "windowId": seed_row.get("windowId"),
                "sourceClipId": seed_row.get("sourceClipId"),
                "frameIndex": frame_id,
                "reviewDecision": seed_row.get("reviewDecision"),
                "reviewedBBox": seed_row.get("reviewedBBox"),
                "diagnosticClass": diagnostic_class,
                "proofEvidence": evidence or {},
            }
        )

    counts = Counter(str(row["diagnosticClass"]) for row in rows)
    dominant_bucket, dominant_count = _dominant_bucket(dict(counts))
    next_family = _next_family(dominant_bucket)
    classified_count = sum(1 for row in rows if row["diagnosticClass"] != BUCKET_RUNTIME_DIAGNOSTIC_GAP)
    frame_diagnostics = {
        "generatedAt": _utc_now_iso(),
        "freshProofRoot": str(proof_root),
        "runtimeDiagnosticsPresent": runtime_diagnostics_present,
        "reviewedPositiveFrameCount": len(rows),
        "classifiedReviewedFrameCount": classified_count,
        "bucketCounts": dict(sorted(counts.items())),
        "reviewedPositiveFrameDiagnostics": rows,
    }
    audit = {
        "generatedAt": _utc_now_iso(),
        "freshProofRoot": str(proof_root),
        "runtimeDiagnosticsPresent": runtime_diagnostics_present,
        "recoveryProfileCount": len(_list_dicts(recovery_profile_matrix.get("profiles"))),
        "profilesWithFrameDiagnostics": [
            str(profile.get("name") or "")
            for profile in _list_dicts(recovery_profile_matrix.get("profiles"))
            if _list_dicts(profile.get("proposalFrameDiagnostics"))
        ],
        "microValidationBeforeRuntimeDiagnostics": {
            "dominantBlockerClass": micro_summary.get("dominantBlockerClass"),
            "nextCorrectiveFamily": micro_summary.get("nextCorrectiveFamily"),
        },
    }
    decision = {
        "goalAchieved": runtime_diagnostics_present,
        "roadmapAdvanceAllowed": runtime_diagnostics_present,
        "dominantBlockerClass": dominant_bucket,
        "dominantBlockerFrameCount": dominant_count,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        "successfulApproach": "A_fresh_local_proof_frame_diagnostics",
        "rationale": (
            "Fresh proof has runtime frame diagnostics; reviewed-positive frames have no matching promoted proposal evidence."
            if dominant_bucket == BUCKET_NO_PROPOSAL
            else "Fresh proof runtime diagnostics classify reviewed-positive frames."
        ),
    }
    summary = {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptApproachFamily": DEFAULT_ATTEMPT_FAMILY,
        "batchStatus": "succeeded" if decision["goalAchieved"] else "blocked",
        "freshProofRoot": str(proof_root),
        "reviewedPositiveFrameCount": len(rows),
        "classifiedReviewedFrameCount": classified_count,
        "runtimeDefaultChanged": False,
        "sourceManifestMutated": False,
        "detectorProfileAdded": False,
        "runPodUsed": False,
        "retentionTruth": {
            "primaryRetentionBlockerClass": retention_summary.get("primaryRetentionBlockerClass"),
            "acceptedRetentionRatio": retention_summary.get("acceptedRetentionRatio"),
            "controlledRetentionRatio": retention_summary.get("controlledRetentionRatio"),
        },
        "suiteTruth": {
            "sourceRobustnessOutcome": suite_summary.get("sourceRobustnessOutcome"),
            "sourceRobustnessPromotionBlockers": suite_summary.get("sourceRobustnessPromotionBlockers"),
        },
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
        "freshProofRoot": str(proof_root),
        "primaryRetentionBlockerClass": retention_summary.get("primaryRetentionBlockerClass"),
        "acceptedRetentionRatio": retention_summary.get("acceptedRetentionRatio"),
        "controlledRetentionRatio": retention_summary.get("controlledRetentionRatio"),
    }

    _write_json(output_root / "proof_runtime_frame_diagnostics_summary.json", summary)
    _write_json(output_root / "reviewed_positive_runtime_frame_diagnostics.json", frame_diagnostics)
    _write_json(output_root / "proof_runtime_artifact_audit.json", audit)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    _write_text(output_root / "batch_outcome_analysis.md", _markdown_summary(summary))
    return {
        "summary": summary,
        "reviewedPositiveRuntimeFrameDiagnostics": frame_diagnostics,
        "proofRuntimeArtifactAudit": audit,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify reviewed-positive frames from a fresh proof runtime diagnostic run.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--expansion-resolution-root", type=Path, default=DEFAULT_EXPANSION_RESOLUTION_ROOT)
    parser.add_argument("--proof-root", type=Path, required=True)
    parser.add_argument("--micro-validation-root", type=Path, default=DEFAULT_MICRO_VALIDATION_ROOT)
    parser.add_argument("--retention-delta-root", type=Path, default=DEFAULT_RETENTION_DELTA_ROOT)
    parser.add_argument("--suite-root", type=Path, default=DEFAULT_SUITE_ROOT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_promoted_v6_proof_runtime_frame_diagnostics(
        output_root=args.output_root,
        expansion_resolution_root=args.expansion_resolution_root,
        proof_root=args.proof_root,
        micro_validation_root=args.micro_validation_root,
        retention_delta_root=args.retention_delta_root,
        suite_root=args.suite_root,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
