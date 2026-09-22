from __future__ import annotations

from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

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

DEFAULT_V38_SNAPSHOT_DIR_NAME = "video_to_analysis_next_sample_selection_snapshot_v38"
DEFAULT_EXTERNAL_BINDING_DIR_NAME = "football_external_benchmark_real_report_and_product_binding_v1"
DEFAULT_RUNTIME_COMPLETION_DIR_NAME = "video_to_analysis_promoted_runtime_operational_completion_summary_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_release_readout_pack_v1"

BLOCKER_GROWTH_CLOSEOUT_MISSING = "video_to_analysis_release_readout_growth_closeout_missing"
BLOCKER_EXTERNAL_BINDING_MISSING = "video_to_analysis_release_readout_external_benchmark_binding_missing"
BLOCKER_RUNTIME_COMPLETION_MISSING = "video_to_analysis_release_readout_runtime_completion_missing"

NEXT_GROWTH_CLOSEOUT = "video_to_analysis_growth_lane_closeout_readout"
NEXT_EXTERNAL_BINDING = "football_external_benchmark_real_report_and_product_binding"
NEXT_RUNTIME_COMPLETION = "video_to_analysis_promoted_runtime_operational_completion_summary"
NEXT_STRATEGIC_SELECTION = "video_to_analysis_next_strategic_lane_selection"

MUTATION_GUARDRAIL_KEYS = (
    "detectorEvaluationExecuted",
    "candidateEvaluationExecuted",
    "candidateReadyForEvaluation",
    "normalMatchStorageMutationExecuted",
    "videoDownloadExecuted",
    "dataDownloadExecuted",
    "trainingExecuted",
    "promotionMutationExecuted",
    "promotionReady",
    "runtimeDefaultMutationExecuted",
    "runtimeDefaultMutationAllowed",
    "generatedTruthDeleteAllowed",
    "cleanupMutationExecuted",
)


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "video_to_analysis_release_readout_pack",
                "successCriteria": [
                    "v38 growth-lane closeout snapshot is present and clean",
                    "external benchmark real report/product binding is present and clean",
                    "v7.2 runtime operational completion is present and clean",
                    "operator-facing readout pack and next-lane matrix are written",
                    "no training, promotion, downloads, runtime mutation, normal storage mutation, or generated-truth deletion",
                ],
                "failureAdaptation": "If a source truth surface is missing, route exactly to that prerequisite.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "release_readout_reference_repair",
                "successCriteria": ["repair only source artifact references and readout text"],
                "failureAdaptation": "If source truth remains incomplete, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "release_readout_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Stop; do not invent release readiness from missing truth.",
            },
        ],
    }


def _flag_false(payload: dict[str, Any] | None, key: str) -> bool:
    if not isinstance(payload, dict):
        return False
    if key not in payload:
        return True
    return payload.get(key) is False


def _guardrails_preserved(*payloads: dict[str, Any] | None) -> bool:
    for payload in payloads:
        if not isinstance(payload, dict):
            return False
        for key in MUTATION_GUARDRAIL_KEYS:
            if not _flag_false(payload, key):
                return False
    return True


def _v38_ready(snapshot: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(snapshot, dict)
        and snapshot.get("goalAchieved") is True
        and snapshot.get("primaryBlocker") is None
        and snapshot.get("candidateSampleCount") == 3
        and snapshot.get("candidateSampleIds")
        == [
            "operator_uploaded_local_video_replenishment_candidate_v23",
            "soccernet_bounded_224p_member_replenishment_candidate_v23",
            "existing_normal_storage_video_replenishment_candidate_v23",
        ]
        and snapshot.get("trainingExecuted") is False
        and snapshot.get("promotionMutationExecuted") is False
        and snapshot.get("runtimeDefaultMutationExecuted") is False
        and snapshot.get("videoDownloadExecuted") is False
        and snapshot.get("dataDownloadExecuted") is False
        and snapshot.get("normalMatchStorageMutationExecuted") is False
    )


def _external_binding_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("roadmapAdvanceAllowed") is True
        and summary.get("detectorEvaluationExecuted") is False
        and summary.get("dataDownloadExecuted") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("normalMatchStorageMutationExecuted") is False
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("candidateEvaluationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
    )


def _runtime_completion_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("videoToAnalysisPromotedRuntimeOperationallyComplete") is True
        and summary.get("releasedRuntimeVersion") == "v7.2"
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("dataDownloadExecuted") is False
        and summary.get("normalMatchStorageMutationExecuted") is False
    )


def _manifest(*, snapshot: dict[str, Any], external_binding: dict[str, Any], runtime_completion: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "video_to_analysis_release_readout_manifest_v1",
        "generatedAt": utc_now_iso(),
        "latestSnapshot": DEFAULT_V38_SNAPSHOT_DIR_NAME,
        "activeQueueCandidateIds": snapshot.get("candidateSampleIds") or [],
        "runtimeVersion": runtime_completion.get("releasedRuntimeVersion"),
        "runtimeOperationallyComplete": True,
        "growthLaneClosedAtV38": True,
        "externalBenchmarkProductBindingReady": True,
        "externalBenchmarkNextLever": external_binding.get("nextRecommendedNextLever"),
        "readoutPurpose": "operator_facing_release_and_next_lane_selection",
    }


def _next_lane_matrix() -> dict[str, Any]:
    return {
        "schemaVersion": "video_to_analysis_next_strategic_lane_matrix_v1",
        "generatedAt": utc_now_iso(),
        "recommendedLane": "external_benchmark_expansion_or_release_readout",
        "candidateStrategicLanes": [
            {
                "id": "external_benchmark_expansion",
                "label": "External benchmark expansion",
                "whenToChoose": "Use when broader SoccerNet/SoccerTrack-style evidence is the priority.",
                "nextLever": "football_external_benchmark_real_evaluation_design",
            },
            {
                "id": "user_facing_release_readout",
                "label": "User-facing release/readout",
                "whenToChoose": "Use when the current v7.2 state should be packaged for demo or operator handoff.",
                "nextLever": "video_to_analysis_user_facing_release_readout",
            },
            {
                "id": "operator_dashboard_polish",
                "label": "Operator dashboard polish",
                "whenToChoose": "Use when inspection ergonomics are more important than more coverage.",
                "nextLever": "video_to_analysis_operator_dashboard_polish",
            },
            {
                "id": "storage_cleanup_approval",
                "label": "Storage cleanup approval",
                "whenToChoose": "Use before more scaleout if artifact volume becomes the bottleneck.",
                "nextLever": "video_to_analysis_storage_cleanup_approval",
            },
            {
                "id": "bounded_growth_v38_continuation",
                "label": "Continue bounded growth from v38",
                "whenToChoose": "Use only if more generated real-video coverage is worth the artifact volume.",
                "nextLever": "video_to_analysis_bounded_next_sample_execution_approval",
            },
        ],
    }


def _guardrail_audit(*payloads: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "schemaVersion": "video_to_analysis_release_readout_guardrail_audit_v1",
        "generatedAt": utc_now_iso(),
        "allMutationGuardrailsPreserved": _guardrails_preserved(*payloads),
        "trainingExecuted": False,
        "promotionMutationExecuted": False,
        "runtimeDefaultMutationExecuted": False,
        "videoDownloadExecuted": False,
        "dataDownloadExecuted": False,
        "normalMatchStorageMutationExecuted": False,
        "generatedTruthDeleteAllowed": False,
        "cleanupMutationExecuted": False,
    }


def _operator_brief(manifest: dict[str, Any], matrix: dict[str, Any]) -> str:
    lanes = "\n".join(f"- `{lane['id']}`: {lane['label']}" for lane in matrix["candidateStrategicLanes"])
    queue = "\n".join(f"- `{sample_id}`" for sample_id in manifest["activeQueueCandidateIds"])
    return "\n".join(
        [
            "# Video-to-analysis release readout",
            "",
            "## Current state",
            "",
            "The v7.2 video-to-analysis runtime is operationally complete, and the bounded real-video growth lane is closed at v38.",
            "",
            "Latest growth snapshot:",
            "",
            "```text",
            str(manifest["latestSnapshot"]),
            "```",
            "",
            "Active v38 queue, if bounded growth is deliberately resumed:",
            "",
            queue,
            "",
            "## What is safe to claim",
            "",
            "- Runtime/product lane is complete enough for operator-facing readout.",
            "- External benchmark report/product binding exists as generated truth.",
            "- The v33-to-v38 growth tranche passed audit and preserved mutation guardrails.",
            "",
            "## What is not claimed",
            "",
            "- No new detector training happened in this readout.",
            "- No promotion mutation happened in this readout.",
            "- No runtime default mutation happened in this readout.",
            "- No video/data download happened in this readout.",
            "",
            "## Candidate next strategic lanes",
            "",
            lanes,
            "",
        ]
    )


def run_video_to_analysis_release_readout_pack(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)

    snapshot = load_json(root / DEFAULT_V38_SNAPSHOT_DIR_NAME / "next_sample_selection_snapshot_summary.json")
    external_binding = load_json(
        root / DEFAULT_EXTERNAL_BINDING_DIR_NAME / "real_report_and_product_binding_summary.json"
    )
    runtime_completion = load_json(
        root / DEFAULT_RUNTIME_COMPLETION_DIR_NAME / "promoted_runtime_operational_completion_summary.json"
    )

    snapshot_ready = _v38_ready(snapshot)
    external_ready = _external_binding_ready(external_binding)
    runtime_ready = _runtime_completion_ready(runtime_completion)
    guardrails_ready = _guardrails_preserved(snapshot, external_binding, runtime_completion)
    goal = snapshot_ready and external_ready and runtime_ready and guardrails_ready

    if not snapshot_ready:
        primary_blocker = BLOCKER_GROWTH_CLOSEOUT_MISSING
        next_lever = NEXT_GROWTH_CLOSEOUT
        english = "Growth-lane v38 closeout truth is missing or unsafe; close out the growth lane before release readout."
    elif not external_ready:
        primary_blocker = BLOCKER_EXTERNAL_BINDING_MISSING
        next_lever = NEXT_EXTERNAL_BINDING
        english = "External benchmark product binding truth is missing or unsafe; bind benchmark report before release readout."
    elif not runtime_ready:
        primary_blocker = BLOCKER_RUNTIME_COMPLETION_MISSING
        next_lever = NEXT_RUNTIME_COMPLETION
        english = "Runtime operational completion truth is missing or unsafe; complete runtime summary before release readout."
    elif not guardrails_ready:
        primary_blocker = "video_to_analysis_release_readout_guardrail_regression"
        next_lever = "video_to_analysis_release_readout_guardrail_repair"
        english = "A mutation guardrail regressed in source truth; repair the source truth before release readout."
    else:
        primary_blocker = None
        next_lever = NEXT_STRATEGIC_SELECTION
        english = "Release/readout pack is ready. Choose the next strategic lane deliberately instead of continuing the bounded growth loop automatically."

    manifest = (
        _manifest(snapshot=snapshot or {}, external_binding=external_binding or {}, runtime_completion=runtime_completion or {})
        if goal
        else {
            "schemaVersion": "video_to_analysis_release_readout_manifest_v1",
            "generatedAt": utc_now_iso(),
            "latestSnapshot": None,
            "activeQueueCandidateIds": [],
            "runtimeOperationallyComplete": False,
            "growthLaneClosedAtV38": False,
            "externalBenchmarkProductBindingReady": False,
        }
    )
    matrix = _next_lane_matrix()
    guardrail_audit = _guardrail_audit(snapshot, external_binding, runtime_completion)

    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "operator_release_brief.md").write_text(
        _operator_brief(manifest, matrix) if goal else "# Video-to-analysis release readout\n\nBlocked.\n",
        encoding="utf-8",
    )

    summary = {
        "batchName": "video_to_analysis_release_readout_pack",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "releaseReadoutPackReady": goal,
        "growthLaneCloseoutSnapshot": DEFAULT_V38_SNAPSHOT_DIR_NAME if snapshot_ready else None,
        "externalBenchmarkProductBindingReady": external_ready,
        "runtimeOperationallyComplete": runtime_ready,
        **standard_false_flags(),
        "generatedTruthDeleteAllowed": False,
        "cleanupMutationExecuted": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "schemaVersion": "video_to_analysis_release_readout_decision_matrix_v1",
        "generatedAt": utc_now_iso(),
        "decisions": [
            {
                "condition": "growth_closeout_missing_or_unsafe",
                "selected": primary_blocker == BLOCKER_GROWTH_CLOSEOUT_MISSING,
                "primaryBlocker": BLOCKER_GROWTH_CLOSEOUT_MISSING,
                "nextRecommendedNextLever": NEXT_GROWTH_CLOSEOUT,
            },
            {
                "condition": "external_benchmark_binding_missing_or_unsafe",
                "selected": primary_blocker == BLOCKER_EXTERNAL_BINDING_MISSING,
                "primaryBlocker": BLOCKER_EXTERNAL_BINDING_MISSING,
                "nextRecommendedNextLever": NEXT_EXTERNAL_BINDING,
            },
            {
                "condition": "runtime_completion_missing_or_unsafe",
                "selected": primary_blocker == BLOCKER_RUNTIME_COMPLETION_MISSING,
                "primaryBlocker": BLOCKER_RUNTIME_COMPLETION_MISSING,
                "nextRecommendedNextLever": NEXT_RUNTIME_COMPLETION,
            },
            {
                "condition": "release_readout_pack_ready",
                "selected": goal,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_STRATEGIC_SELECTION,
            },
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="release_readout_pack_summary.json",
        summary=summary,
        artifacts={
            "release_readout_manifest.json": manifest,
            "next_strategic_lane_matrix.json": matrix,
            "guardrail_audit.json": guardrail_audit,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Release Readout Pack",
    )


def main() -> None:
    main_for("Build video-to-analysis release/readout pack.", run_video_to_analysis_release_readout_pack)


if __name__ == "__main__":
    main()
