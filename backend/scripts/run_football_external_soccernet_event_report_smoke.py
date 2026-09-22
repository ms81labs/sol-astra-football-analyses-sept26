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
DEFAULT_REPORT_PREP_DIR_NAME = "football_external_soccernet_event_report_contract_prep_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_event_report_smoke_v1"

BLOCKER_REPORT_CONTRACT_MISSING = "football_external_soccernet_event_report_contract_missing"
BLOCKER_REPORT_RENDER_GAP = "football_external_soccernet_event_report_render_gap"

NEXT_REPORT_PREP = "football_external_soccernet_event_report_contract_prep"
NEXT_RENDER_REPAIR = "football_external_soccernet_event_report_render_contract_repair"
NEXT_CLOSEOUT = "football_external_soccernet_event_lane_closeout"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_event_report_smoke",
            "successCriteria": [
                "render a human-readable event-only report",
                "validate report includes metrics and limitations",
                "do not train, promote, mutate runtime defaults, or fetch videos",
            ],
            "failureAdaptation": "If rendering fails, repair report render contract.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_event_report_render_contract_repair",
            "successCriteria": [
                "repair report sections from saved report summary only",
                "preserve event-only limitations",
            ],
            "failureAdaptation": "If report remains invalid, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_event_report_smoke_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before lane closeout",
            ],
            "failureAdaptation": "Route to report contract prep or render repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    report_root = candidate_root / DEFAULT_REPORT_PREP_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "reportPrepSummary": _load_json(report_root / "soccernet_event_report_contract_prep_summary.json"),
        "eventReportSummary": _load_json(report_root / "soccernet_event_report_summary.json"),
        "limitationsAudit": _load_json(report_root / "event_report_limitations_audit.json"),
        "reportSmokeContract": _load_json(report_root / "event_report_smoke_contract.json"),
    }


def _report_contract_ready(summary: dict[str, Any] | None, report: dict[str, Any] | None, contract: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("reportContractReady") is True
        and int(summary.get("eventCount") or 0) > 0
        and summary.get("fullMatchAnalysisReady") is False
        and summary.get("trainingExecuted") is False
        and isinstance(report, dict)
        and report.get("reportSmokeReady") is True
        and isinstance(contract, dict)
        and contract.get("reportSmokeReady") is True
        and contract.get("trainingUseAllowed") is False
        and contract.get("videoDownloadAllowed") is False
    )


def _render_report(report: dict[str, Any], limitations: dict[str, Any] | None) -> str:
    lines = [
        "# SoccerNet Event-Only Report",
        "",
        f"Source: `{report.get('sourceDataset') or 'SoccerNet SN-BAS-2025'}`",
        "",
        "## Summary",
        "",
        f"- Events: `{report.get('eventCount')}`",
        f"- Distinct event types: `{report.get('distinctEventTypeCount')}`",
        f"- Event rate per minute: `{report.get('eventRatePerMinute')}`",
        f"- Full match analysis ready: `{report.get('fullMatchAnalysisReady')}`",
        "",
        "## Top Event Types",
        "",
    ]
    for row in report.get("topEventTypes") or []:
        if isinstance(row, dict):
            lines.append(f"- `{row.get('eventType')}`: `{row.get('count')}`")
    lines.extend(["", "## Team Event Split", ""])
    for row in report.get("teamEventSplit") or []:
        if isinstance(row, dict):
            lines.append(f"- `{row.get('team')}`: `{row.get('count')}` events, share `{row.get('share')}`")
    lines.extend(["", "## Coverage Limits", ""])
    plain = (limitations or {}).get("plainEnglish") or "Event-only source. Non-event stages remain uncovered."
    lines.append(str(plain))
    return "\n".join(lines) + "\n"


def _render_audit(rendered: str, report: dict[str, Any]) -> dict[str, Any]:
    required_terms = ["SoccerNet Event-Only Report", "Top Event Types", "Coverage Limits"]
    top_types = [str(row.get("eventType")) for row in report.get("topEventTypes") or [] if isinstance(row, dict)]
    rendered_lower = rendered.lower()
    return {
        "renderedReportBytes": len(rendered.encode("utf-8")),
        "requiredSectionsPresent": all(term in rendered for term in required_terms),
        "topEventTypesRendered": all(event_type in rendered for event_type in top_types[:3]),
        "eventCountRendered": str(report.get("eventCount")) in rendered,
        "limitationsRendered": "coverage limits" in rendered_lower
        and (
            "event-only" in rendered_lower
            or "event-frequency" in rendered_lower
            or "does not include" in rendered_lower
            or "uncovered" in rendered_lower
        ),
    }


def _classify(contract_ready: bool, audit: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not contract_ready:
        return (
            BLOCKER_REPORT_CONTRACT_MISSING,
            NEXT_REPORT_PREP,
            False,
            "SoccerNet event report contract truth is missing or unsafe; rerun report contract prep.",
        )
    if not all(
        [
            audit.get("requiredSectionsPresent"),
            audit.get("topEventTypesRendered"),
            audit.get("eventCountRendered"),
            audit.get("limitationsRendered"),
        ]
    ):
        return (
            BLOCKER_REPORT_RENDER_GAP,
            NEXT_RENDER_REPAIR,
            False,
            "SoccerNet event report rendering missed required sections or limitations.",
        )
    return (
        None,
        NEXT_CLOSEOUT,
        True,
        "SoccerNet event-only report smoke passed. Advance to closeout for this external event lane.",
    )


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "event_report_contract_missing", "selected": primary_blocker == BLOCKER_REPORT_CONTRACT_MISSING, "primaryBlocker": BLOCKER_REPORT_CONTRACT_MISSING, "nextRecommendedNextLever": NEXT_REPORT_PREP},
            {"condition": "event_report_render_gap", "selected": primary_blocker == BLOCKER_REPORT_RENDER_GAP, "primaryBlocker": BLOCKER_REPORT_RENDER_GAP, "nextRecommendedNextLever": NEXT_RENDER_REPAIR},
            {"condition": "event_lane_closeout_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_CLOSEOUT},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Event Report Smoke",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Report smoke passed: `{summary.get('eventReportSmokePassed')}`",
            f"- Event count: `{summary.get('eventCount')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_event_report_smoke(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_event_report_smoke",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _report_contract_ready(inputs["reportPrepSummary"], inputs["eventReportSummary"], inputs["reportSmokeContract"])
    report = inputs["eventReportSummary"] or {}
    rendered = _render_report(report, inputs["limitationsAudit"] or {})
    audit = _render_audit(rendered, report)
    primary_blocker, next_lever, goal_achieved, english = _classify(ready, audit)
    attempts = _attempt_plan()
    generated_at = utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_event_report_smoke",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_event_report_contract_prep",
        "eventReportSmokePassed": goal_achieved,
        "eventCount": report.get("eventCount"),
        "distinctEventTypeCount": report.get("distinctEventTypeCount"),
        "fullMatchAnalysisReady": False,
        "archiveDownloadExecuted": False,
        "videoMemberDownloadExecuted": False,
        "datasetDownloadAllowedByThisBatch": False,
        "datasetDownloadExecuted": False,
        "fullOriginalVideoDownloadApproved": False,
        "fullOriginalVideoDownloadExecuted": False,
        "videoDownloadAllowed": False,
        "featureDownloadAllowed": False,
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
        "reportRenderAudit": audit,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "soccernet_event_report_smoke_summary.json", summary)
    _write_json(output_root / "report_render_audit.json", audit)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "soccernet_event_only_report.md").write_text(rendered, encoding="utf-8")
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_event_report_smoke")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_event_report_smoke(
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
