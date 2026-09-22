from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_full_analysis_product_integration_v1"

BLOCKER_CLOSEOUT_MISSING = "football_external_soccernet_full_analysis_lane_closeout_missing"
BLOCKER_PRODUCT_CONTRACT_GAP = "football_external_soccernet_full_analysis_product_contract_gap"

NEXT_CLOSEOUT = "football_external_soccernet_full_analysis_lane_closeout"
NEXT_PRODUCT_REPAIR = "football_external_soccernet_full_analysis_product_contract_repair"
NEXT_PRODUCT_API_SMOKE = "football_external_soccernet_analysis_product_api_smoke"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_full_analysis_product_payload",
            "successCriteria": [
                "turn the full extracted 224p analysis report into a product-facing payload",
                "preserve limitations and safe readiness flags",
                "do not train, promote, mark candidate evaluation ready, or mutate runtime defaults",
            ],
            "failureAdaptation": "If payload is incomplete, repair only the product contract from saved report/closeout truth.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_full_analysis_product_contract_repair",
            "successCriteria": [
                "repair missing UI/readiness fields without altering analysis truth",
                "keep candidate evaluation, training, promotion, and runtime mutation false",
            ],
            "failureAdaptation": "If the lane closeout dependency is unsafe, route back to closeout.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_full_analysis_product_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before product API smoke if the integration contract is unsafe",
            ],
            "failureAdaptation": "Route to closeout or product contract repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    return {
        "candidateRoot": candidate_root,
        "closeoutSummary": _load_json(candidate_root / "football_external_soccernet_full_analysis_lane_closeout_v1/full_analysis_lane_closeout_summary.json"),
        "contractPrep": _load_json(candidate_root / "football_external_soccernet_full_analysis_lane_closeout_v1/full_analysis_product_integration_contract_prep.json"),
        "gapAnalysis": _load_json(candidate_root / "football_external_soccernet_full_analysis_lane_closeout_v1/remaining_gap_analysis.json"),
        "reportPayload": _load_json(candidate_root / "football_external_soccernet_full_analysis_report_smoke_v1/full_analysis_report_payload.json"),
        "executionPayload": _load_json(candidate_root / "football_external_soccernet_full_analysis_execution_v1/full_analysis_product_payload.json"),
        "renderedReportPath": candidate_root / "football_external_soccernet_full_analysis_report_smoke_v1/full_analysis_report.md",
    }


def _closeout_ready(summary: dict[str, Any] | None, prep: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("fullAnalysisLaneClosed") is True
        and summary.get("fullAnalysisProductIntegrationReady") is True
        and int(summary.get("reportedFrameCount") or 0) > 0
        and int(summary.get("segmentCount") or 0) > 0
        and summary.get("trainingExecuted") is False
        and summary.get("promotionReady") is False
        and summary.get("candidateReadyForEvaluation") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(prep, dict)
        and prep.get("schemaVersion") == "soccernet_external_full_analysis_product_integration_prep_v1"
        and prep.get("fullAnalysisProductIntegrationReady") is True
        and prep.get("trainingAllowed") is False
        and prep.get("promotionAllowed") is False
        and prep.get("candidateEvaluationReadinessAllowed") is False
        and prep.get("runtimeDefaultMutationAllowed") is False
    )


def _product_payload(
    report_payload: dict[str, Any] | None,
    execution_payload: dict[str, Any] | None,
    gaps: dict[str, Any] | None,
    rendered_report_path: Path,
) -> dict[str, Any]:
    report_payload = report_payload or {}
    execution_payload = execution_payload or {}
    signals = report_payload.get("aggregateFrameSignals") if isinstance(report_payload.get("aggregateFrameSignals"), dict) else {}
    remaining_gaps = gaps.get("remainingGaps") if isinstance(gaps, dict) and isinstance(gaps.get("remainingGaps"), list) else []
    frame_count = int(report_payload.get("reportedFrameCount") or execution_payload.get("frameCount") or 0)
    segment_count = int(report_payload.get("segmentCount") or execution_payload.get("segmentCount") or 0)
    return {
        "schemaVersion": "soccernet_external_full_analysis_product_payload_v1",
        "generatedAt": utc_now_iso(),
        "sourceBatch": "football_external_soccernet_full_analysis_lane_closeout",
        "sourceReportPath": str(rendered_report_path),
        "sourceVideoPath": execution_payload.get("videoPath"),
        "frameCount": frame_count,
        "segmentCount": segment_count,
        "aggregateFrameSignals": signals,
        "summaryCards": [
            {"label": "Frames analyzed", "value": frame_count},
            {"label": "Timeline segments", "value": segment_count},
            {"label": "Resolution", "value": f"{signals.get('width')}x{signals.get('height')}"},
            {"label": "Median motion delta", "value": signals.get("motionDeltaP50")},
        ],
        "readiness": {
            "productFullAnalysisReady": frame_count > 0 and segment_count > 0,
            "full224pAnalysisReady": True,
            "videoPlaybackReady": bool(execution_payload.get("videoPath")),
            "trainingReady": False,
            "promotionReady": False,
            "candidateEvaluationReady": False,
            "runtimeDefaultMutationReady": False,
        },
        "limitations": [
            "full extracted 224p member only",
            "lightweight frame-statistics analysis only",
            "not detector evaluation",
            "not ball-localization truth",
            "not training evidence",
            "not promotion evidence",
            "does not mutate runtime defaults",
        ],
        "remainingGaps": remaining_gaps,
    }


def _ui_copy(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": "SoccerNet full 224p analysis",
        "subtitle": "Full extracted SoccerNet video summarized with lightweight frame-signal timelines.",
        "limitationsBanner": "This is a full extracted 224p frame-statistics report, not detector evaluation, tracking, ball-localization truth, training evidence, promotion evidence, or runtime-default mutation evidence.",
        "safeNextAction": "Run product API smoke for this full-analysis payload before any detector evaluation, training, 720p processing, or promotion lane.",
        "emptyState": "No full-analysis product payload is ready yet.",
        "productFullAnalysisReady": payload["readiness"]["productFullAnalysisReady"],
        "candidateEvaluationReady": payload["readiness"]["candidateEvaluationReady"],
    }


def _contract(payload: dict[str, Any], copy: dict[str, Any]) -> dict[str, Any]:
    return {
        "contractName": "football_external_soccernet_full_analysis_product_integration",
        "productFullAnalysisReady": payload["readiness"]["productFullAnalysisReady"] is True,
        "requiresTraining": False,
        "allowsPromotion": False,
        "allowsCandidateEvaluationReadiness": False,
        "allowsRuntimeDefaultMutation": False,
        "requiresLimitationsBanner": True,
        "mustShowLimitationsBanner": bool(copy.get("limitationsBanner")),
        "nextSmokeRequiredBeforeUserFacingApi": True,
    }


def _classify(closeout_ready: bool, payload: dict[str, Any], contract: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not closeout_ready:
        return (
            BLOCKER_CLOSEOUT_MISSING,
            NEXT_CLOSEOUT,
            False,
            "SoccerNet full-analysis lane closeout is missing or unsafe; rerun closeout before product integration.",
        )
    if (
        payload.get("readiness", {}).get("productFullAnalysisReady") is not True
        or payload.get("readiness", {}).get("candidateEvaluationReady") is not False
        or contract.get("mustShowLimitationsBanner") is not True
        or contract.get("allowsCandidateEvaluationReadiness") is not False
    ):
        return (
            BLOCKER_PRODUCT_CONTRACT_GAP,
            NEXT_PRODUCT_REPAIR,
            False,
            "SoccerNet full-analysis product payload is incomplete or overclaims readiness.",
        )
    return (
        None,
        NEXT_PRODUCT_API_SMOKE,
        True,
        "SoccerNet full-analysis product payload is ready for product API smoke. Training, promotion, candidate readiness, and runtime mutation remain blocked.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "full_analysis_lane_closeout_missing", "selected": primary_blocker == BLOCKER_CLOSEOUT_MISSING, "primaryBlocker": BLOCKER_CLOSEOUT_MISSING, "nextRecommendedNextLever": NEXT_CLOSEOUT},
            {"condition": "full_analysis_product_contract_gap", "selected": primary_blocker == BLOCKER_PRODUCT_CONTRACT_GAP, "primaryBlocker": BLOCKER_PRODUCT_CONTRACT_GAP, "nextRecommendedNextLever": NEXT_PRODUCT_REPAIR},
            {"condition": "full_analysis_product_payload_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_PRODUCT_API_SMOKE},
        ],
    }


def _markdown_report(payload: dict[str, Any], copy: dict[str, Any]) -> str:
    lines = [
        "# SoccerNet Full 224p Product Analysis",
        "",
        str(copy["limitationsBanner"]),
        "",
        "## Summary",
        "",
    ]
    for card in payload.get("summaryCards") or []:
        if isinstance(card, dict):
            lines.append(f"- {card.get('label')}: `{card.get('value')}`")
    lines.extend(["", "## Aggregate Frame Signals", ""])
    for key, value in sorted((payload.get("aggregateFrameSignals") or {}).items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Remaining Gaps", ""])
    for gap in payload.get("remainingGaps") or []:
        lines.append(f"- `{gap}`")
    lines.append("")
    return "\n".join(lines)


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Full Analysis Product Integration",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Product full analysis ready: `{summary.get('productFullAnalysisReady')}`",
            f"- Reported frame count: `{summary.get('reportedFrameCount')}`",
            f"- Segment count: `{summary.get('segmentCount')}`",
            f"- Candidate ready for evaluation: `{summary.get('candidateReadyForEvaluation')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_full_analysis_product_integration(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_full_analysis_product_payload",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _closeout_ready(inputs["closeoutSummary"], inputs["contractPrep"])
    payload = _product_payload(inputs["reportPayload"], inputs["executionPayload"], inputs["gapAnalysis"], inputs["renderedReportPath"])
    copy = _ui_copy(payload)
    contract = _contract(payload, copy)
    primary_blocker, next_lever, goal_achieved, english = _classify(ready, payload, contract)
    if not goal_achieved:
        payload["readiness"]["productFullAnalysisReady"] = False
        contract["productFullAnalysisReady"] = False
    attempts = _attempt_plan()
    generated_at = utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_full_analysis_product_integration",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_full_analysis_lane_closeout",
        "productFullAnalysisReady": goal_achieved,
        "reportedFrameCount": payload.get("frameCount"),
        "segmentCount": payload.get("segmentCount"),
        "archiveDownloadExecuted": False,
        "video720pMemberDownloadExecuted": False,
        "trainingAllowed": False,
        "trainingExecuted": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationAllowed": False,
        "runtimeDefaultMutationExecuted": False,
        "promotionMutationExecuted": False,
        "candidateEvaluationExecuted": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = _decision_matrix(primary_blocker, goal_achieved)
    batch_outcome = {
        "summary": summary,
        "productFullAnalysisPayload": payload,
        "productUiCopy": copy,
        "productIntegrationContract": contract,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "full_analysis_product_integration_summary.json", summary)
    _write_json(output_root / "product_full_analysis_payload.json", payload)
    _write_json(output_root / "product_ui_copy.json", copy)
    _write_json(output_root / "product_integration_contract.json", contract)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "product_full_analysis_report.md").write_text(_markdown_report(payload, copy), encoding="utf-8")
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_full_analysis_product_payload")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_full_analysis_product_integration(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        output_dir_name=args.output_dir_name,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("goalAchieved") else 1


if __name__ == "__main__":
    raise SystemExit(main())
