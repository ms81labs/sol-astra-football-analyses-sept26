from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    load_json,
    main_for,
    reset_output,
    standard_false_flags,
    utc_now_iso,
    write_outcome,
)

DEFAULT_RELEASE_CLOSEOUT_DIR_NAME = "video_to_analysis_release_candidate_closeout_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_operator_handoff_pack_v1"

BLOCKER_RELEASE_CLOSEOUT_MISSING = "video_to_analysis_release_candidate_closeout_missing"
NEXT_RELEASE_CLOSEOUT = "video_to_analysis_release_candidate_closeout"
NEXT_ROUTE_BINDING = "video_to_analysis_operator_handoff_route_binding"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "video_to_analysis_operator_handoff_pack",
                "successCriteria": [
                    "package release-candidate routes and guardrails for operators",
                    "write a quickstart and route contract",
                ],
                "failureAdaptation": "If release-candidate closeout is missing, route back to closeout.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "operator_handoff_pack_scope_repair",
                "successCriteria": ["repair only handoff references, checklist, or route contract"],
                "failureAdaptation": "If handoff remains incomplete, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "operator_handoff_pack_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to release closeout, scope repair, or handoff route binding.",
            },
        ],
    }


def _release_ready(summary: dict[str, Any] | None, snapshot: dict[str, Any] | None, matrix: dict[str, Any] | None) -> bool:
    caps = matrix.get("releaseCandidateCapabilities") if isinstance(matrix, dict) else None
    guardrails = matrix.get("guardrails") if isinstance(matrix, dict) else None
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("videoToAnalysisReleaseCandidateClosed") is True
        and summary.get("videoToAnalysisProductPathReady") is True
        and summary.get("acceptanceCaseCount") == 5
        and summary.get("acceptancePassedCaseCount") == 5
        and summary.get("normalMatchStorageMutationExecuted") is False
        and summary.get("detectorEvaluationExecuted") is False
        and summary.get("candidateEvaluationExecuted") is False
        and summary.get("candidateReadyForEvaluation") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("dataDownloadExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("promotionReady") is False
        and summary.get("runtimeDefaultMutationExecuted") is True
        and summary.get("runtimeDefaultRolloutClosed") is True
        and summary.get("activeRuntimeDefaultVersion") == "v7.3"
        and summary.get("activeFailingSourceNotViableBlockerPresent") is False
        and isinstance(snapshot, dict)
        and snapshot.get("status") == "release_candidate_closed"
        and snapshot.get("primaryRoute") == "/video-to-analysis/acceptance-report"
        and snapshot.get("apiRoute") == "/api/video-to-analysis/acceptance-report"
        and snapshot.get("activeRuntimeDefaultVersion") == "v7.3"
        and snapshot.get("runtimeDefaultRolloutClosed") is True
        and isinstance(caps, dict)
        and caps.get("acceptanceReportRouteReady") is True
        and caps.get("broaderRealVideoAcceptancePassed") is True
        and caps.get("v7_3RuntimeDefaultRolloutClosed") is True
        and isinstance(guardrails, dict)
        and guardrails.get("detectorEvaluationReady") is False
        and guardrails.get("trainingReady") is False
        and guardrails.get("promotionReady") is False
        and guardrails.get("runtimeDefaultMutationReady") is True
    )


def _handoff_pack() -> dict[str, Any]:
    return {
        "schemaVersion": "video_to_analysis_operator_handoff_pack_v1",
        "generatedAt": utc_now_iso(),
        "primaryOperatorRoute": "/video-to-analysis/acceptance-report",
        "primaryApiRoute": "/api/video-to-analysis/acceptance-report",
        "handoffRoute": "/video-to-analysis/operator-handoff",
        "handoffApiRoute": "/api/video-to-analysis/operator-handoff",
        "activeRuntimeDefaultVersion": "v7.3",
        "runtimeDefaultRolloutClosed": True,
        "operatorChecklist": [
            {
                "id": "open_acceptance_report",
                "label": "Open the acceptance report",
                "route": "/video-to-analysis/acceptance-report",
            },
            {
                "id": "verify_five_case_acceptance",
                "label": "Confirm five-case acceptance passed",
                "expected": "5 / 5 acceptance cases passed",
            },
            {
                "id": "confirm_guardrails",
                "label": "Confirm detector evaluation, training, promotion, and downloads are not enabled",
                "expected": "guarded execution lanes remain false while v7.3 remains the active runtime default",
            },
        ],
        "guardrails": {
            "detectorEvaluationAllowed": False,
            "candidateEvaluationReadinessAllowed": False,
            "downloadsAllowed": False,
            "trainingAllowed": False,
            "promotionAllowed": False,
            "runtimeDefaultMutationAlreadyExecuted": True,
            "runtimeDefaultMutationAllowedFromHandoff": False,
        },
    }


def _route_contract() -> dict[str, Any]:
    return {
        "schemaVersion": "video_to_analysis_operator_handoff_route_contract_v1",
        "generatedAt": utc_now_iso(),
        "apiRoutePath": "/api/video-to-analysis/operator-handoff",
        "htmlRoutePath": "/video-to-analysis/operator-handoff",
        "operatorHandoffRouteReady": True,
        "allowsDetectorEvaluation": False,
        "allowsCandidateEvaluationReadiness": False,
        "allowsDownloads": False,
        "allowsTraining": False,
        "allowsPromotion": False,
        "allowsRuntimeDefaultMutation": False,
        "activeRuntimeDefaultVersion": "v7.3",
    }


def _quickstart() -> str:
    return "\n".join(
        [
            "# Video-to-analysis operator handoff",
            "",
            "## Primary route",
            "",
            "- `/video-to-analysis/acceptance-report`",
            "- `/api/video-to-analysis/acceptance-report`",
            "",
            "## Checklist",
            "",
            "1. Open the acceptance report route.",
            "2. Confirm `5 / 5` broader real-video acceptance cases passed.",
            "3. Confirm v7.3 is the active runtime default.",
            "4. Confirm detector evaluation, downloads, training, promotion, and candidate readiness remain blocked.",
            "",
        ]
    )


def run_video_to_analysis_operator_handoff_pack(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    release_root = root / DEFAULT_RELEASE_CLOSEOUT_DIR_NAME
    output_root = reset_output(root, output_dir_name)
    closeout_summary = load_json(release_root / "release_candidate_closeout_summary.json")
    operator_snapshot = load_json(release_root / "release_candidate_operator_snapshot.json")
    capability_matrix = load_json(release_root / "release_candidate_capability_matrix.json")
    ready = _release_ready(closeout_summary, operator_snapshot, capability_matrix)

    if ready:
        primary_blocker = None
        next_lever = NEXT_ROUTE_BINDING
        goal = True
        english = "Operator handoff pack is ready. Bind the operator handoff route next."
    else:
        primary_blocker = BLOCKER_RELEASE_CLOSEOUT_MISSING
        next_lever = NEXT_RELEASE_CLOSEOUT
        goal = False
        english = "Release-candidate closeout is missing or unsafe; close the release candidate before operator handoff."

    pack = _handoff_pack() if ready else {"schemaVersion": "video_to_analysis_operator_handoff_pack_v1", "generatedAt": utc_now_iso(), "operatorChecklist": []}
    contract = _route_contract() if ready else {"schemaVersion": "video_to_analysis_operator_handoff_route_contract_v1", "generatedAt": utc_now_iso(), "operatorHandoffRouteReady": False}
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "operator_quickstart.md").write_text(_quickstart() if ready else "# Video-to-analysis operator handoff\n\nBlocked.\n", encoding="utf-8")

    false_flags = standard_false_flags()
    false_flags["runtimeDefaultMutationExecuted"] = ready
    false_flags["runtimeDefaultMutationAllowed"] = ready
    summary = {
        "batchName": "video_to_analysis_operator_handoff_pack",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "operatorHandoffPackReady": goal,
        "videoToAnalysisProductPathReady": goal,
        "acceptanceCaseCount": 5 if goal else 0,
        "acceptancePassedCaseCount": 5 if goal else 0,
        **false_flags,
        "activeRuntimeDefaultVersion": "v7.3" if goal else None,
        "runtimeDefaultRolloutClosed": goal,
        "activeFailingSourceNotViableBlockerPresent": False if goal else None,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {
                "condition": "release_candidate_closeout_missing",
                "selected": primary_blocker == BLOCKER_RELEASE_CLOSEOUT_MISSING,
                "primaryBlocker": BLOCKER_RELEASE_CLOSEOUT_MISSING,
                "nextRecommendedNextLever": NEXT_RELEASE_CLOSEOUT,
            },
            {
                "condition": "operator_handoff_pack_ready",
                "selected": goal,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_ROUTE_BINDING,
            },
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="operator_handoff_pack_summary.json",
        summary=summary,
        artifacts={
            "operator_handoff_pack.json": pack,
            "operator_handoff_route_contract.json": contract,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Operator Handoff Pack",
    )


def main() -> None:
    main_for("Build video-to-analysis operator handoff pack.", run_video_to_analysis_operator_handoff_pack)


if __name__ == "__main__":
    main()
