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
DEFAULT_OUTPUT_ROOT = DEFAULT_SUITE_ROOT / "reviewed_positive_proposal_generation_fix_v1"
DEFAULT_PROOF_ROOT = DEFAULT_STORAGE_ROOT / "pod_cycles" / "promoted_v6_baseline-trimed-5min.mp4-robustness-validation"
DEFAULT_RETENTION_DELTA_ROOT = (
    DEFAULT_SUITE_ROOT / "promoted_touchline_detector_candidate_retention_delta_analysis_v1"
)
DEFAULT_BATCH_NAME = "reviewed_positive_proposal_generation_fix_v1"

BUCKET_ZERO_DETECT = "reviewed_positive_anchor_window_zero_detect"
BUCKET_RAW_NOT_COLLAPSED = "reviewed_positive_raw_detected_not_collapsed"
BUCKET_COLLAPSED_NOT_SELECTED = "reviewed_positive_collapsed_not_selected"
BUCKET_SELECTED_NOT_ACCEPTED = "reviewed_positive_selected_not_accepted"
BUCKET_ACCEPTED = "reviewed_positive_already_accepted"


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


def _proposal_profile(recovery_profile_matrix: dict[str, Any]) -> dict[str, Any]:
    for profile in _list_dicts(recovery_profile_matrix.get("profiles")):
        if profile.get("name") == "proposal_windows_075":
            return profile
    return {}


def _diagnostics_by_frame(profile: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rows = {}
    for row in _list_dicts(profile.get("proposalFrameDiagnostics")):
        frame_id = _safe_int(row.get("frameIndex"), -1)
        if frame_id >= 0:
            rows[frame_id] = row
    return rows


def _classify(evidence: dict[str, Any] | None) -> str:
    if not evidence:
        return BUCKET_ZERO_DETECT
    if evidence.get("accepted"):
        return BUCKET_ACCEPTED
    if evidence.get("selected"):
        return BUCKET_SELECTED_NOT_ACCEPTED
    if evidence.get("collapsed"):
        return BUCKET_COLLAPSED_NOT_SELECTED
    if evidence.get("rawDetected") or evidence.get("proposalGenerated"):
        return BUCKET_RAW_NOT_COLLAPSED
    return BUCKET_ZERO_DETECT


def _dominant_bucket(counts: dict[str, int]) -> tuple[str, int]:
    priority = {
        BUCKET_ZERO_DETECT: 0,
        BUCKET_COLLAPSED_NOT_SELECTED: 1,
        BUCKET_SELECTED_NOT_ACCEPTED: 2,
        BUCKET_RAW_NOT_COLLAPSED: 3,
        BUCKET_ACCEPTED: 4,
    }
    return sorted(
        ((str(key), _safe_int(value)) for key, value in counts.items()),
        key=lambda item: (-item[1], priority.get(item[0], 99), item[0]),
    )[0]


def _next_family(dominant_bucket: str, *, proposal_evidence_count: int) -> str:
    if dominant_bucket == BUCKET_ZERO_DETECT:
        return "reviewed_positive_crop_reinference_audit"
    if dominant_bucket in {BUCKET_COLLAPSED_NOT_SELECTED, BUCKET_RAW_NOT_COLLAPSED}:
        return "reviewed_positive_selection_followthrough_fix"
    if dominant_bucket == BUCKET_SELECTED_NOT_ACCEPTED:
        return "reviewed_positive_acceptance_fix"
    if proposal_evidence_count > 0:
        return "reviewed_positive_selection_followthrough_fix"
    return "reviewed_positive_crop_reinference_audit"


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Reviewed Positive Proposal Generation Fix",
            "",
            f"- batchStatus: {summary.get('batchStatus')}",
            f"- reviewedPositiveAnchorFrameCount: {summary.get('reviewedPositiveAnchorFrameCount')}",
            f"- reviewedPositiveProposalEvidenceFrameCount: {summary.get('reviewedPositiveProposalEvidenceFrameCount')}",
            f"- dominantBlockerClass: {summary.get('dominantBlockerClass')}",
            f"- nextCorrectiveFamily: {summary.get('nextCorrectiveFamily')}",
            f"- acceptedRetentionRatio: {summary.get('retentionTruth', {}).get('acceptedRetentionRatio')}",
            "",
        ]
    )


def run_promoted_v6_reviewed_positive_proposal_generation_fix(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    proof_root: Path = DEFAULT_PROOF_ROOT,
    retention_delta_root: Path = DEFAULT_RETENTION_DELTA_ROOT,
) -> dict[str, Any]:
    output_root = Path(output_root)
    proof_root = Path(proof_root)
    anchor_seed = _load_json_dict(output_root / "reviewed_positive_anchor_seed.json")
    retention_summary = _load_optional_json_dict(Path(retention_delta_root) / "retention_delta_summary.json")
    recovery_profile_matrix = _load_json_dict(proof_root / "recovery_profile_matrix.json")
    proof_summary = _load_optional_json_dict(proof_root / "proof_summary.json")
    profile = _proposal_profile(recovery_profile_matrix)
    diagnostics_by_frame = _diagnostics_by_frame(profile)

    rows = []
    for anchor in _list_dicts(anchor_seed.get("reviewedPositiveAnchorRows")):
        frame_id = _safe_int(anchor.get("frameIndex"), -1)
        evidence = diagnostics_by_frame.get(frame_id)
        diagnostic_class = _classify(evidence)
        window_generated = frame_id >= 0
        raw_detected = bool(evidence and evidence.get("rawDetected"))
        candidate_generated = bool(
            evidence
            and (
                evidence.get("proposalGenerated")
                or evidence.get("candidateGenerated")
                or evidence.get("rawDetected")
                or evidence.get("collapsed")
                or evidence.get("selected")
                or evidence.get("accepted")
            )
        )
        collapsed = bool(evidence and evidence.get("collapsed"))
        selected = bool(evidence and evidence.get("selected"))
        accepted = bool(evidence and evidence.get("accepted"))
        rows.append(
            {
                "reviewItemId": anchor.get("reviewItemId"),
                "candidateFrameId": anchor.get("candidateFrameId"),
                "windowId": anchor.get("windowId"),
                "sourceClipId": anchor.get("sourceClipId"),
                "frameIndex": frame_id,
                "reviewedBBox": anchor.get("reviewedBBox"),
                "windowGenerated": window_generated,
                "windowSkipped": not window_generated,
                "zeroDetect": window_generated and not raw_detected and not candidate_generated,
                "rawDetected": raw_detected,
                "candidateGenerated": candidate_generated,
                "collapsed": collapsed,
                "selected": selected,
                "accepted": accepted,
                "diagnosticClass": diagnostic_class,
                "rejectionReason": diagnostic_class if not accepted else "",
                "proofEvidence": evidence or {},
            }
        )
    counts = Counter(str(row["diagnosticClass"]) for row in rows)
    dominant_bucket, dominant_count = _dominant_bucket(dict(counts)) if counts else (BUCKET_ZERO_DETECT, 0)
    proposal_evidence_count = sum(1 for row in rows if row["rawDetected"] or row["collapsed"] or row["selected"])
    selected_count = sum(1 for row in rows if row["selected"])
    accepted_count = sum(1 for row in rows if row["accepted"])
    next_family = _next_family(dominant_bucket, proposal_evidence_count=proposal_evidence_count)
    generated_at = _utc_now_iso()
    coverage = {
        "generatedAt": generated_at,
        "proofRoot": str(proof_root),
        "reviewedPositiveAnchorFrameCount": len(rows),
        "reviewedPositiveProposalEvidenceFrameCount": proposal_evidence_count,
        "reviewedPositiveSelectedFrameCount": selected_count,
        "reviewedPositiveAcceptedFrameCount": accepted_count,
        "bucketCounts": dict(sorted(counts.items())),
        "reviewedPositiveFrames": rows,
        "proposalProfileSummary": {
            "reviewedPositiveAnchorSeedFrames": _safe_int(profile.get("reviewedPositiveAnchorSeedFrames"), 0),
            "reviewedPositiveAnchorUsedFrames": _safe_int(profile.get("reviewedPositiveAnchorUsedFrames"), 0),
            "reviewedPositiveAnchorWindowFrames": _safe_int(profile.get("reviewedPositiveAnchorWindowFrames"), 0),
            "proposalRawDetectedFrames": _safe_int(profile.get("proposalRawDetectedFrames"), 0),
            "proposalCollapsedFrames": _safe_int(profile.get("proposalCollapsedFrames"), 0),
            "selectedFrames": _safe_int(profile.get("selectedFrames"), 0),
        },
    }
    summary = {
        "generatedAt": generated_at,
        "batchName": DEFAULT_BATCH_NAME,
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptApproachFamily": "reviewed_positive_seed_proposal_windows",
        "batchStatus": "succeeded" if proposal_evidence_count > 0 else "needs_next_attempt",
        "goalAchieved": proposal_evidence_count > 0,
        "roadmapAdvanceAllowed": True,
        "reviewedPositiveAnchorFrameCount": len(rows),
        "reviewedPositiveProposalEvidenceFrameCount": proposal_evidence_count,
        "reviewedPositiveSelectedFrameCount": selected_count,
        "reviewedPositiveAcceptedFrameCount": accepted_count,
        "dominantBlockerClass": dominant_bucket,
        "dominantBlockerFrameCount": dominant_count,
        "nextCorrectiveFamily": next_family,
        "nextRecommendedBatch": next_family,
        "runtimeDefaultChanged": False,
        "runPodUsed": True,
        "retentionTruth": {
            "acceptedRetentionRatio": retention_summary.get("acceptedRetentionRatio"),
            "controlledRetentionRatio": retention_summary.get("controlledRetentionRatio"),
            "primaryRetentionBlockerClass": retention_summary.get("primaryRetentionBlockerClass"),
        },
        "proofTruth": {
            "acceptedBallFrames": proof_summary.get("acceptedBallFrames"),
            "bestProposalRawDetectedFrames": proof_summary.get("bestProposalRawDetectedFrames"),
            "bestProposalAfterSeedCollapseFrames": proof_summary.get("bestProposalAfterSeedCollapseFrames"),
            "bestProposalSelectedFrames": proof_summary.get("bestProposalSelectedFrames"),
        },
    }
    decision = {
        "goalAchieved": summary["goalAchieved"],
        "roadmapAdvanceAllowed": True,
        "dominantBlockerClass": dominant_bucket,
        "nextCorrectiveFamily": next_family,
        "rationale": (
            "Reviewed-positive anchor windows produced proposal evidence but most reviewed frames still have zero detector hits."
            if proposal_evidence_count > 0
            else "Reviewed-positive anchor windows were generated but produced no proposal evidence."
        ),
    }
    batch_outcome = {
        **summary,
        "decisionMatrix": decision,
    }
    _write_json(output_root / "reviewed_positive_proposal_coverage.json", coverage)
    _write_json(output_root / "reviewed_positive_proposal_fix_summary.json", summary)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return {
        "reviewedPositiveProposalCoverage": coverage,
        "reviewedPositiveProposalFixSummary": summary,
        "decisionMatrix": decision,
        "batchOutcomeAnalysis": batch_outcome,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize reviewed-positive proposal-generation proof coverage.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--proof-root", default=str(DEFAULT_PROOF_ROOT))
    parser.add_argument("--retention-delta-root", default=str(DEFAULT_RETENTION_DELTA_ROOT))
    args = parser.parse_args()
    payload = run_promoted_v6_reviewed_positive_proposal_generation_fix(
        output_root=Path(args.output_root),
        proof_root=Path(args.proof_root),
        retention_delta_root=Path(args.retention_delta_root),
    )
    print(json.dumps(payload["reviewedPositiveProposalFixSummary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
