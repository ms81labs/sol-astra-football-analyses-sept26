from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_event_report_product_integration_v1"

BLOCKER_CLOSEOUT_MISSING = "football_external_soccernet_event_lane_closeout_missing"
BLOCKER_PRODUCT_CONTRACT_GAP = "football_external_soccernet_event_report_product_contract_gap"

NEXT_CLOSEOUT = "football_external_soccernet_event_lane_closeout"
NEXT_PRODUCT_REPAIR = "football_external_soccernet_event_report_product_contract_repair"
NEXT_VIDEO_APPROVAL = "football_external_soccernet_video_sample_download_approval"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_event_report_product_payload",
            "successCriteria": [
                "turn the event-only report into a product-facing payload",
                "include visible limitations and safe next-action metadata",
                "do not download video, train, promote, or mutate runtime defaults",
            ],
            "failureAdaptation": "If payload is incomplete, repair the product report contract from saved truth only.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_event_report_product_contract_repair",
            "successCriteria": [
                "repair missing UI copy/readiness fields without altering source event truth",
                "keep full-match analysis readiness false",
            ],
            "failureAdaptation": "If the closeout dependency is unsafe, route back to lane closeout.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_event_report_product_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before video download, training, promotion, or runtime mutation",
            ],
            "failureAdaptation": "Route to closeout or product contract repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    return {
        "candidateRoot": candidate_root,
        "closeoutSummary": _load_json(candidate_root / "football_external_soccernet_event_lane_closeout_v1/soccernet_event_lane_closeout_summary.json"),
        "gapAnalysis": _load_json(candidate_root / "football_external_soccernet_event_lane_closeout_v1/remaining_gap_analysis.json"),
        "reportSummary": _load_json(candidate_root / "football_external_soccernet_event_report_contract_prep_v1/soccernet_event_report_summary.json"),
        "renderedReportPath": candidate_root / "football_external_soccernet_event_report_smoke_v1/soccernet_event_only_report.md",
    }


def _closeout_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("eventOnlyLaneClosed") is True
        and int(summary.get("eventCount") or 0) > 0
        and summary.get("fullMatchAnalysisReady") is False
        and summary.get("trainingExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
    )


def _product_payload(report: dict[str, Any] | None, gaps: dict[str, Any] | None, rendered_report_path: Path) -> dict[str, Any]:
    report = report or {}
    remaining = gaps.get("remainingUnprovenStages") if isinstance(gaps, dict) and isinstance(gaps.get("remainingUnprovenStages"), list) else []
    top_event_types = report.get("topEventTypes") if isinstance(report.get("topEventTypes"), list) else []
    team_event_split = report.get("teamEventSplit") if isinstance(report.get("teamEventSplit"), list) else []
    return {
        "schemaVersion": "soccernet_event_report_product_payload_v1",
        "generatedAt": _utc_now_iso(),
        "sourceDataset": report.get("sourceDataset") or "SoccerNet SN-BAS-2025",
        "sourceReportPath": str(rendered_report_path),
        "readiness": {
            "eventOnlyReportReady": int(report.get("eventCount") or 0) > 0,
            "fullMatchAnalysisReady": False,
            "videoAnalysisReady": False,
            "trainingReady": False,
            "promotionReady": False,
            "runtimeDefaultMutationReady": False,
        },
        "summaryCards": [
            {"label": "Events", "value": report.get("eventCount")},
            {"label": "Event types", "value": report.get("distinctEventTypeCount")},
            {"label": "Events per minute", "value": report.get("eventRatePerMinute")},
        ],
        "topEventTypes": top_event_types,
        "teamEventSplit": team_event_split,
        "coveredStageIds": report.get("coveredStageIds") or ["possession_event_semantics"],
        "remainingUnprovenStages": remaining,
    }


def _ui_copy(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": "SoccerNet event-only match report",
        "subtitle": "Event-frequency and event-taxonomy summary from external SoccerNet labels.",
        "limitationsBanner": "This is not a full video-analysis report. It does not include pitch calibration, tracking, ball localization, tactical state, or original-video processing.",
        "safeNextAction": "Request a controlled video-sample download approval before any original-video benchmark work.",
        "emptyState": "No event-only report is ready yet.",
        "fullMatchAnalysisReady": payload["readiness"]["fullMatchAnalysisReady"],
    }


def _contract(payload: dict[str, Any], copy: dict[str, Any]) -> dict[str, Any]:
    return {
        "contractName": "football_external_soccernet_event_report_product_integration",
        "productEventReportReady": payload["readiness"]["eventOnlyReportReady"] is True,
        "requiresVideoPlayback": False,
        "requiresTraining": False,
        "allowsPromotion": False,
        "allowsRuntimeDefaultMutation": False,
        "mustShowLimitationsBanner": bool(copy.get("limitationsBanner")),
        "nextApprovalRequiredBeforeVideoUse": True,
    }


def _classify(closeout_ready: bool, payload: dict[str, Any], contract: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not closeout_ready:
        return (
            BLOCKER_CLOSEOUT_MISSING,
            NEXT_CLOSEOUT,
            False,
            "SoccerNet event lane closeout is missing or unsafe; rerun closeout before product integration.",
        )
    if (
        payload.get("readiness", {}).get("eventOnlyReportReady") is not True
        or payload.get("readiness", {}).get("fullMatchAnalysisReady") is not False
        or contract.get("mustShowLimitationsBanner") is not True
    ):
        return (
            BLOCKER_PRODUCT_CONTRACT_GAP,
            NEXT_PRODUCT_REPAIR,
            False,
            "SoccerNet event-only product payload is incomplete or overclaims readiness.",
        )
    return (
        None,
        NEXT_VIDEO_APPROVAL,
        True,
        "SoccerNet event-only report product payload is ready. To move toward full video analysis, open a separate controlled video-sample download approval lane.",
    )


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "event_lane_closeout_missing", "selected": primary_blocker == BLOCKER_CLOSEOUT_MISSING, "primaryBlocker": BLOCKER_CLOSEOUT_MISSING, "nextRecommendedNextLever": NEXT_CLOSEOUT},
            {"condition": "event_report_product_contract_gap", "selected": primary_blocker == BLOCKER_PRODUCT_CONTRACT_GAP, "primaryBlocker": BLOCKER_PRODUCT_CONTRACT_GAP, "nextRecommendedNextLever": NEXT_PRODUCT_REPAIR},
            {"condition": "event_report_product_payload_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_VIDEO_APPROVAL},
        ],
    }


def _markdown_report(payload: dict[str, Any], copy: dict[str, Any]) -> str:
    lines = [
        "# SoccerNet Event-Only Product Report",
        "",
        str(copy["limitationsBanner"]),
        "",
        "## Summary",
        "",
    ]
    for card in payload.get("summaryCards") or []:
        if isinstance(card, dict):
            lines.append(f"- {card.get('label')}: `{card.get('value')}`")
    lines.extend(["", "## Top Event Types", ""])
    for row in payload.get("topEventTypes") or []:
        if isinstance(row, dict):
            lines.append(f"- `{row.get('eventType')}`: `{row.get('count')}`")
    lines.extend(["", "## Remaining Unproven Stages", ""])
    for stage in payload.get("remainingUnprovenStages") or []:
        lines.append(f"- `{stage}`")
    lines.append("")
    return "\n".join(lines)


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Event Report Product Integration",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Product event report ready: `{summary.get('productEventReportReady')}`",
            f"- Event count: `{summary.get('eventCount')}`",
            f"- Full match analysis ready: `{summary.get('fullMatchAnalysisReady')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_event_report_product_integration(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_event_report_product_payload",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _closeout_ready(inputs["closeoutSummary"])
    payload = _product_payload(inputs["reportSummary"], inputs["gapAnalysis"], inputs["renderedReportPath"])
    copy = _ui_copy(payload)
    contract = _contract(payload, copy)
    primary_blocker, next_lever, goal_achieved, english = _classify(ready, payload, contract)
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_event_report_product_integration",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_event_lane_closeout",
        "productEventReportReady": goal_achieved,
        "eventCount": payload["summaryCards"][0]["value"],
        "distinctEventTypeCount": payload["summaryCards"][1]["value"],
        "fullMatchAnalysisReady": False,
        "archiveDownloadExecuted": False,
        "videoMemberDownloadExecuted": False,
        "datasetDownloadExecuted": False,
        "fullOriginalVideoDownloadExecuted": False,
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
    decision_matrix = _decision_matrix(primary_blocker, next_lever, goal_achieved)
    batch_outcome = {
        "summary": summary,
        "productEventReportPayload": payload,
        "productUiCopy": copy,
        "productIntegrationContract": contract,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "soccernet_event_report_product_integration_summary.json", summary)
    _write_json(output_root / "product_event_report_payload.json", payload)
    _write_json(output_root / "product_ui_copy.json", copy)
    _write_json(output_root / "product_integration_contract.json", contract)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "product_event_report.md").write_text(_markdown_report(payload, copy), encoding="utf-8")
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_event_report_product_payload")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_event_report_product_integration(
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
