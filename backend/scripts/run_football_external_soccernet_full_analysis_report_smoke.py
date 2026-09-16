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
DEFAULT_EXECUTION_DIR_NAME = "football_external_soccernet_full_analysis_execution_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_full_analysis_report_smoke_v1"

BLOCKER_EXECUTION_MISSING = "football_external_soccernet_full_analysis_execution_missing"
BLOCKER_REPORT_GAP = "football_external_soccernet_full_analysis_report_gap"

NEXT_EXECUTION = "football_external_soccernet_full_analysis_execution"
NEXT_REPORT_REPAIR = "football_external_soccernet_full_analysis_report_payload_repair"
NEXT_LANE_CLOSEOUT = "football_external_soccernet_full_analysis_lane_closeout"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_full_analysis_report_smoke",
            "successCriteria": [
                "load full-analysis product payload",
                "render a human-readable report",
                "keep training, promotion, candidate readiness, and runtime mutation blocked",
            ],
            "failureAdaptation": "If report fields are incomplete, repair only from full-analysis execution truth.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_full_analysis_report_payload_repair",
            "successCriteria": [
                "repair report payload fields from full-analysis output",
                "do not rerun full analysis or broaden scope",
            ],
            "failureAdaptation": "If execution artifacts are missing, route back to full-analysis execution.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_full_analysis_report_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before lane closeout if report smoke is unsafe",
            ],
            "failureAdaptation": "Route to full-analysis execution or report payload repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str, execution_dir_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    execution_root = candidate_root / execution_dir_name
    return {
        "candidateRoot": candidate_root,
        "executionSummary": _load_json(execution_root / "full_analysis_execution_summary.json"),
        "productPayload": _load_json(execution_root / "full_analysis_product_payload.json"),
    }


def _execution_ready(summary: dict[str, Any] | None, payload: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("fullAnalysisExecutionExecuted") is True
        and int(summary.get("processedFrameCount") or 0) > 0
        and int(summary.get("unreadableFrameCount") or 0) == 0
        and summary.get("trainingExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and isinstance(payload, dict)
        and payload.get("schemaVersion") == "soccernet_external_full_analysis_product_payload_v1"
        and int(payload.get("frameCount") or 0) == int(summary.get("processedFrameCount") or 0)
        and payload.get("readiness", {}).get("fullAnalysisExecutionReady") is True
        and payload.get("readiness", {}).get("candidateEvaluationReady") is False
    )


def _report_payload(source_payload: dict[str, Any] | None) -> dict[str, Any]:
    source_payload = source_payload or {}
    signals = source_payload.get("aggregateFrameSignals") if isinstance(source_payload.get("aggregateFrameSignals"), dict) else {}
    return {
        "schemaVersion": "soccernet_external_full_analysis_report_payload_v1",
        "generatedAt": _utc_now_iso(),
        "sourceBatch": "football_external_soccernet_full_analysis_execution",
        "reportedFrameCount": source_payload.get("frameCount"),
        "segmentCount": source_payload.get("segmentCount"),
        "aggregateFrameSignals": signals,
        "readiness": {
            "fullAnalysisReportReady": source_payload.get("readiness", {}).get("fullAnalysisExecutionReady") is True,
            "trainingReady": False,
            "promotionReady": False,
            "candidateEvaluationReady": False,
            "runtimeDefaultMutationReady": False,
        },
        "limitations": [
            "full extracted 224p member only",
            "lightweight frame-statistics report only",
            "not detector evaluation",
            "not training evidence",
            "does not mutate runtime defaults",
        ],
    }


def _report_markdown(payload: dict[str, Any]) -> str:
    signals = payload.get("aggregateFrameSignals", {})
    return "\n".join(
        [
            "# SoccerNet Full 224p Analysis Report",
            "",
            f"- Reported frame count: `{payload.get('reportedFrameCount')}`",
            f"- Segment count: `{payload.get('segmentCount')}`",
            f"- Median brightness: `{signals.get('meanBrightnessP50')}`",
            f"- Median green-dominant pixel ratio: `{signals.get('greenDominantPixelRatioP50')}`",
            f"- Median motion delta: `{signals.get('motionDeltaP50')}`",
            f"- Candidate evaluation ready: `{payload.get('readiness', {}).get('candidateEvaluationReady')}`",
            "",
            "This report summarizes the full extracted SoccerNet 224p member with lightweight frame statistics. It is not detector evaluation, training evidence, promotion evidence, or runtime-default mutation evidence.",
            "",
        ]
    )


def _classify(execution_ready: bool, payload: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not execution_ready:
        return (
            BLOCKER_EXECUTION_MISSING,
            NEXT_EXECUTION,
            False,
            "SoccerNet full-analysis execution artifacts are missing or unsafe; rerun full-analysis execution before report smoke.",
        )
    if int(payload.get("reportedFrameCount") or 0) <= 0 or payload.get("readiness", {}).get("fullAnalysisReportReady") is not True:
        return (
            BLOCKER_REPORT_GAP,
            NEXT_REPORT_REPAIR,
            False,
            "SoccerNet full-analysis report payload is incomplete; repair report payload before lane closeout.",
        )
    return (
        None,
        NEXT_LANE_CLOSEOUT,
        True,
        "SoccerNet full-analysis report smoke passed. Advance to full-analysis lane closeout; training and promotion remain blocked.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "full_analysis_execution_missing", "selected": primary_blocker == BLOCKER_EXECUTION_MISSING, "primaryBlocker": BLOCKER_EXECUTION_MISSING, "nextRecommendedNextLever": NEXT_EXECUTION},
            {"condition": "full_analysis_report_gap", "selected": primary_blocker == BLOCKER_REPORT_GAP, "primaryBlocker": BLOCKER_REPORT_GAP, "nextRecommendedNextLever": NEXT_REPORT_REPAIR},
            {"condition": "full_analysis_lane_closeout_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_LANE_CLOSEOUT},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Full Analysis Report Smoke",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Full analysis report ready: `{summary.get('fullAnalysisReportReady')}`",
            f"- Reported frame count: `{summary.get('reportedFrameCount')}`",
            f"- Segment count: `{summary.get('segmentCount')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation executed: `{summary.get('runtimeDefaultMutationExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_full_analysis_report_smoke(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    execution_dir_name: str = DEFAULT_EXECUTION_DIR_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_full_analysis_report_smoke",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name, execution_dir_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _execution_ready(inputs["executionSummary"], inputs["productPayload"])
    report_payload = _report_payload(inputs["productPayload"])
    primary_blocker, next_lever, goal_achieved, english = _classify(ready, report_payload)
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_full_analysis_report_smoke",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_full_analysis_execution",
        "fullAnalysisReportReady": goal_achieved,
        "reportedFrameCount": report_payload.get("reportedFrameCount"),
        "segmentCount": report_payload.get("segmentCount"),
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
        "fullAnalysisReportPayload": report_payload,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "full_analysis_report_smoke_summary.json", summary)
    _write_json(output_root / "full_analysis_report_payload.json", report_payload)
    (output_root / "full_analysis_report.md").write_text(_report_markdown(report_payload), encoding="utf-8")
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--execution-dir-name", default=DEFAULT_EXECUTION_DIR_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_full_analysis_report_smoke")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_full_analysis_report_smoke(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        execution_dir_name=args.execution_dir_name,
        output_dir_name=args.output_dir_name,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("goalAchieved") else 1


if __name__ == "__main__":
    raise SystemExit(main())
