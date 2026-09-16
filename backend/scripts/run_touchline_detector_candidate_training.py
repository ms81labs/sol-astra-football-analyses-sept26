"""Historical training recipe, retired with its RunPod execution path."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
import backend.scripts.runpod_session as runpod_session  # noqa: E402
import backend.train_custom as train_custom  # noqa: E402


DEFAULT_BATCH_NAME = "touchline_detector_candidate_retraining_v2"
DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v2"
DEFAULT_TRAINING_PREP_BATCH_NAME = "touchline_review_densification_v1"
DEFAULT_BASE_MODEL_PATH = "yolov10n.pt"
DEFAULT_IMGSZ = 640
DEFAULT_EPOCHS = 12
DEFAULT_BATCH_SIZE = 8
DEFAULT_DEVICE = "0"
DEFAULT_WORKERS = 4
DEFAULT_SEED = 42
DEFAULT_EXECUTION_MODE = "remote_gpu"
NEXT_LEVER_RETRAIN = "retrain_touchline_detector_candidate"
NEXT_LEVER_EVALUATE = "evaluate_touchline_detector_candidate"
PLATEAU_BASELINE = {
    "acceptedBallFrames": 101,
    "controlledPossessionFrames": 98,
    "ballTrackViable": False,
    "ballTrackEdgeFrameShare": 0.812,
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _safe_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _json_safe_metrics(metrics: object) -> dict[str, object]:
    if not isinstance(metrics, dict):
        return {}
    normalized: dict[str, object] = {}
    for key, value in metrics.items():
        if isinstance(value, bool):
            normalized[str(key)] = value
        elif isinstance(value, (int, float, str)) or value is None:
            normalized[str(key)] = value
        else:
            try:
                normalized[str(key)] = float(value)
            except (TypeError, ValueError):
                normalized[str(key)] = str(value)
    return normalized


def _artifact_paths(storage_root: Path) -> dict[str, Path]:
    suite_root = storage_root / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
    training_prep_root = storage_root / "training_prep" / DEFAULT_TRAINING_PREP_BATCH_NAME
    artifact_root = storage_root / "trained_detector_candidates" / DEFAULT_CANDIDATE_NAME
    return {
        "suiteSummaryPath": suite_root / "suite_summary.json",
        "activeLaneSnapshotPath": suite_root / "active_lane_snapshot.json",
        "datasetManifestPath": training_prep_root / "review_densification_manifest.json",
        "splitManifestPath": training_prep_root / "split_manifest.json",
        "reviewBundleReportPath": training_prep_root / "review_bundle_report.json",
        "batchOutcomeAnalysisPath": training_prep_root / "batch_outcome_analysis.json",
        "datasetYamlPath": training_prep_root / "yolo_export" / "dataset.yaml",
        "datasetExportRoot": training_prep_root / "yolo_export",
        "artifactRoot": artifact_root,
        "trainingConfigPath": artifact_root / "training_config.json",
        "trainingSummaryPath": artifact_root / "training_run_summary.json",
        "evaluationContractPath": artifact_root / "evaluation_contract.json",
        "batchOutcomeJsonPath": artifact_root / "batch_outcome_analysis.json",
        "batchOutcomeMarkdownPath": artifact_root / "batch_outcome_analysis.md",
        "remoteTrainingResultPath": artifact_root / "remote_training_result.json",
    }


def _requested_gpu_id() -> str | None:
    env_gpu_id = os.environ.get("RUNPOD_GPU_ID", "").strip()
    if env_gpu_id:
        return env_gpu_id
    loader = getattr(runpod_session, "_load_saved_runpod_gpu_id", None)
    if callable(loader):
        saved_gpu_id = str(loader()).strip()
        if saved_gpu_id:
            return saved_gpu_id
    return None


def _should_retry_without_requested_gpu(error_message: str, requested_gpu_id: str | None) -> bool:
    requested = str(requested_gpu_id or "").strip()
    if not requested:
        return False
    normalized = error_message.lower()
    return (
        f"requested gpu_id {requested!r}".lower() in normalized
        or f"requested gpu_id '{requested}'" in normalized
    ) and (
        "no longer any instances available" in normalized
        or "unable to create a runpod pod with requested gpu_id" in normalized
    )


def _create_remote_training_session(
    *,
    requested_gpu_id: str | None,
) -> tuple[dict[str, object], str | None]:
    try:
        session = runpod_session.create_runpod_session(
            local_repo_root=REPO_ROOT,
            clip_path=None,
            gpu_id=requested_gpu_id,
        )
        return session, None
    except Exception as error:
        error_message = str(error)
        if not _should_retry_without_requested_gpu(error_message, requested_gpu_id):
            raise
        session = runpod_session.create_runpod_session(
            local_repo_root=REPO_ROOT,
            clip_path=None,
            gpu_id=None,
        )
        return session, error_message


def _validate_training_inputs(
    *,
    dataset_manifest: dict[str, object],
    split_manifest: dict[str, object],
    batch_outcome_analysis: dict[str, object],
    dataset_yaml_path: Path,
) -> None:
    if not dataset_yaml_path.exists():
        raise FileNotFoundError(f"Training dataset YAML not found at {dataset_yaml_path}")
    if not bool(dataset_manifest.get("yoloExportRegenerated")):
        raise ValueError("Review densification export is not marked yoloExportRegenerated")
    if not bool(dataset_manifest.get("readyForRetraining")):
        raise ValueError("Review densification manifest is not marked readyForRetraining")
    if bool(split_manifest.get("sourceAwareSplitLeakageDetected")):
        raise ValueError("Split manifest reports source-aware split leakage")
    if not bool(batch_outcome_analysis.get("goalAchieved")) or not bool(batch_outcome_analysis.get("roadmapAdvanceAllowed")):
        raise ValueError("Phase 1B batch outcome does not allow the roadmap to advance into retraining")


def _training_recipe() -> dict[str, object]:
    return {
        "baseModelPath": DEFAULT_BASE_MODEL_PATH,
        "imgsz": DEFAULT_IMGSZ,
        "epochs": DEFAULT_EPOCHS,
        "batch": DEFAULT_BATCH_SIZE,
        "device": DEFAULT_DEVICE,
        "workers": DEFAULT_WORKERS,
        "seed": DEFAULT_SEED,
        "augmentationPolicy": dict(train_custom.DEFAULT_AUGMENTATION_POLICY),
        "patience": DEFAULT_EPOCHS,
    }


def _build_training_config(
    *,
    dataset_manifest: dict[str, object],
    split_manifest: dict[str, object],
    review_bundle_report: dict[str, object],
    phase1b_batch_outcome: dict[str, object],
    suite_summary: dict[str, object],
    active_lane_snapshot: dict[str, object],
    dataset_yaml_path: Path,
    artifact_root: Path,
    requested_gpu_id: str | None,
    execution_mode: str,
) -> dict[str, object]:
    return {
        "generatedAt": _utc_now_iso(),
        "trainingBatchName": DEFAULT_BATCH_NAME,
        "trainingCandidateName": DEFAULT_CANDIDATE_NAME,
        "artifactRoot": str(artifact_root),
        "datasetYamlPath": str(dataset_yaml_path),
        "executionMode": execution_mode,
        "requestedGpuId": requested_gpu_id,
        "datasetLineage": {
            "trainingPrepBatchName": dataset_manifest.get("batchName"),
            "failingSourceClipId": dataset_manifest.get("failingSourceClipId"),
            "comparisonSourceClipId": dataset_manifest.get("comparisonSourceClipId"),
            "representativeFailingMatchId": dataset_manifest.get("representativeFailingMatchId"),
            "representativeControlMatchId": dataset_manifest.get("representativeControlMatchId"),
            "curationUnitCount": _safe_int(dataset_manifest.get("curationUnitCount"), 0),
            "failingCurationUnitCount": _safe_int(dataset_manifest.get("failingCurationUnitCount"), 0),
            "controlCurationUnitCount": _safe_int(dataset_manifest.get("controlCurationUnitCount"), 0),
            "positiveSeedExampleCount": _safe_int(dataset_manifest.get("positiveSeedExampleCount"), 0),
            "negativeSeedExampleCount": _safe_int(dataset_manifest.get("negativeSeedExampleCount"), 0),
            "pendingFailingReviewCount": _safe_int(dataset_manifest.get("pendingFailingReviewCount"), 0),
            "pendingControlReviewCount": _safe_int(dataset_manifest.get("pendingControlReviewCount"), 0),
            "heldOutSplitAssessment": split_manifest.get("heldOutSplitAssessment"),
            "sourceAwareSplitLeakageDetected": bool(split_manifest.get("sourceAwareSplitLeakageDetected")),
            "seededIssueCount": _safe_int(review_bundle_report.get("seededIssueCount"), 0),
            "reviewBundleCount": _safe_int(review_bundle_report.get("reviewBundleCount"), 0),
            "phase1BBatchGoalAchieved": bool(phase1b_batch_outcome.get("goalAchieved")),
            "phase1BRoadmapAdvanceAllowed": bool(phase1b_batch_outcome.get("roadmapAdvanceAllowed")),
        },
        "trainingRecipe": _training_recipe(),
        "baselineReference": {
            "suiteVerdict": suite_summary.get("suiteVerdict"),
            "sourceRobustnessOutcome": suite_summary.get("sourceRobustnessOutcome"),
            "sourceRobustnessActiveConfigName": suite_summary.get("sourceRobustnessActiveConfigName"),
            "sourceRobustnessBestConfigName": suite_summary.get("sourceRobustnessBestConfigName"),
            "sourceRobustnessBestExploratoryConfigName": suite_summary.get("sourceRobustnessBestExploratoryConfigName"),
            "sourceRobustnessRecommendedNextLever": suite_summary.get("sourceRobustnessRecommendedNextLever"),
            "baselineFingerprint": active_lane_snapshot.get("baselineFingerprint", {}),
        },
        "seededLabelPolicy": "seeded_review_required",
        "validationAssessment": split_manifest.get("heldOutSplitAssessment"),
        "notes": [
            "This dataset is seeded from saved rows and is not human-verified truth.",
            "Control review items may remain pending in Phase 1B and do not block this retraining batch.",
            "Validation confidence is limited when the split manifest reports limited_single_control_source.",
        ],
    }


def _build_evaluation_contract(
    *,
    dataset_manifest: dict[str, object],
    active_lane_snapshot: dict[str, object],
    best_weights_path: str | None,
    last_weights_path: str | None,
    candidate_ready: bool,
) -> dict[str, object]:
    baseline_fingerprint = dict(active_lane_snapshot.get("baselineFingerprint") or {})
    failing_source_clip_id = str(dataset_manifest.get("failingSourceClipId") or "trimed-5min.mp4")
    return {
        "generatedAt": _utc_now_iso(),
        "trainingCandidateName": DEFAULT_CANDIDATE_NAME,
        "trainingBatchName": DEFAULT_BATCH_NAME,
        "candidateReadyForEvaluation": candidate_ready,
        "localScreenTargetClipPath": str(REPO_ROOT / "videos" / failing_source_clip_id),
        "remoteProofComparisonBaseline": dict(PLATEAU_BASELINE),
        "activeFrozenBaseline": {
            "detectorModelPath": baseline_fingerprint.get("detectorModelPath") or DEFAULT_BASE_MODEL_PATH,
            "primaryMode": baseline_fingerprint.get("primaryMode") or "anchored_player_ranked_context_960",
            "cleanupLane": baseline_fingerprint.get("cleanupLane") or "recent_ball_plus_inward_anchor_center_bias35_960",
        },
        "candidateWeights": {
            "bestWeightsPath": best_weights_path,
            "lastWeightsPath": last_weights_path,
        },
        "promotionReadySuccessMeans": [
            "candidate is good enough to enter bounded screen and proof evaluation",
            "candidate is not promoted into runtime defaults by this batch",
        ],
        "failFastConditions": [
            "training artifact missing",
            "weights unusable",
            "provenance incomplete",
            "no meaningful candidate output to evaluate",
        ],
    }


def _rewrite_dataset_yaml_for_remote(dataset_yaml_path: Path, *, remote_export_root: str) -> str:
    rewritten_lines: list[str] = []
    replaced_path = False
    for raw_line in dataset_yaml_path.read_text(encoding="utf-8").splitlines():
        if raw_line.startswith("path:"):
            rewritten_lines.append(f"path: {remote_export_root}")
            replaced_path = True
        else:
            rewritten_lines.append(raw_line)
    if not replaced_path:
        rewritten_lines.insert(0, f"path: {remote_export_root}")
    rewritten_lines.append("")
    return "\n".join(rewritten_lines)


def _stage_dataset_on_pod(
    *,
    session: dict[str, object],
    dataset_export_root: Path,
    dataset_yaml_path: Path,
) -> str:
    remote_export_root = (
        f"{session['remoteStorageRoot']}/training_prep/{DEFAULT_TRAINING_PREP_BATCH_NAME}/yolo_export"
    )
    runpod_session.copy_directory_to_pod(
        ssh_command=list(session["sshCommand"]),
        local_path=dataset_export_root,
        remote_path=remote_export_root,
    )
    rewritten_dataset_yaml = _rewrite_dataset_yaml_for_remote(
        dataset_yaml_path,
        remote_export_root=remote_export_root,
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_dataset_yaml = Path(tmpdir) / "dataset.yaml"
        temp_dataset_yaml.write_text(rewritten_dataset_yaml, encoding="utf-8")
        runpod_session.copy_file_to_pod(
            list(session["sshCommand"]),
            local_path=temp_dataset_yaml,
            remote_path=f"{remote_export_root}/dataset.yaml",
        )
    return f"{remote_export_root}/dataset.yaml"


def _build_remote_training_command(
    *,
    session: dict[str, object],
    remote_dataset_yaml_path: str,
    staged_model_path: str,
    training_recipe: dict[str, object],
    requested_gpu_id: str | None,
) -> str:
    remote_repo_root = str(session["remoteRepoRoot"])
    remote_project_root = (
        f"{session['remoteStorageRoot']}/trained_detector_candidates/{DEFAULT_CANDIDATE_NAME}/ultralytics_run"
    )
    augmentation_policy = dict(training_recipe.get("augmentationPolicy") or {})
    remote_command = f"""
set -euo pipefail
cd {shlex.quote(remote_repo_root)}
source {shlex.quote(runpod_session.DEFAULT_POD_VENV_PATH)}/bin/activate
export PYTHONPATH={shlex.quote(remote_repo_root)}
export YOLO_CONFIG_DIR={shlex.quote(runpod_session.DEFAULT_POD_YOLO_CONFIG_DIR)}
mkdir -p {shlex.quote(remote_project_root)} {shlex.quote(runpod_session.DEFAULT_POD_YOLO_CONFIG_DIR)}
python - <<'PY'
import json
from pathlib import Path

import torch

import backend.train_custom as train_custom

result = train_custom.fine_tune(
    data_yaml={remote_dataset_yaml_path!r},
    model_path={staged_model_path!r},
    epochs={_safe_int(training_recipe.get("epochs"), DEFAULT_EPOCHS)},
    imgsz={_safe_int(training_recipe.get("imgsz"), DEFAULT_IMGSZ)},
    batch={_safe_int(training_recipe.get("batch"), DEFAULT_BATCH_SIZE)},
    device={str(training_recipe.get("device") or DEFAULT_DEVICE)!r},
    project={remote_project_root!r},
    name="training",
    patience={_safe_int(training_recipe.get("patience"), DEFAULT_EPOCHS)},
    workers={_safe_int(training_recipe.get("workers"), DEFAULT_WORKERS)},
    seed={_safe_int(training_recipe.get("seed"), DEFAULT_SEED)},
    augmentation_policy={augmentation_policy!r},
)
payload = dict(result)
payload["trainingCompleted"] = True
payload["remoteDatasetYamlPath"] = {remote_dataset_yaml_path!r}
payload["remoteModelPath"] = {staged_model_path!r}
payload["requestedGpuId"] = {requested_gpu_id!r}
payload["remoteDeviceName"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
payload["allocatedGpuId"] = payload["remoteDeviceName"]
print(json.dumps(payload))
PY
"""
    return f"bash -lc {shlex.quote(remote_command)}"


def _pull_remote_artifact(
    *,
    session: dict[str, object],
    remote_path: str | None,
    local_path: Path,
) -> str | None:
    runpod_session.require_retired_runpod_disabled()


def _candidate_ready_for_evaluation(
    *,
    weights_ready: bool,
    evaluation_contract_ready: bool,
    remote_training_result: dict[str, object],
) -> tuple[bool, str | None]:
    if not weights_ready:
        return False, "weights_unusable"
    if not evaluation_contract_ready:
        return False, "evaluation_contract_incomplete"
    if not str(remote_training_result.get("remoteDatasetYamlPath") or "").strip():
        return False, "training_provenance_incomplete"
    if not str(remote_training_result.get("remoteModelPath") or "").strip():
        return False, "training_provenance_incomplete"
    return True, None


def _brainstorm_fixes(primary_blocker: str | None, error_message: str | None) -> list[str]:
    if primary_blocker == "remote_training_failed":
        fixes = [
            "Inspect the remote training error and rerun the v2 batch after fixing the pod-side training command or runtime dependency issue.",
            "Confirm the densified dataset staged correctly on the pod and that the remote dataset.yaml path points at the pod copy, not the local absolute path.",
        ]
        if error_message:
            fixes.append(f"Start with the captured training error: {error_message}")
        return fixes
    if primary_blocker == "weights_unusable":
        return [
            "Verify the remote Ultralytics run actually produced best.pt and last.pt, then rerun the batch.",
            "Confirm the weight pull-back paths match the remote training output paths.",
        ]
    if primary_blocker == "training_provenance_incomplete":
        return [
            "Restore missing remote training provenance fields so the batch records the dataset path, model path, and runtime metadata cleanly.",
            "Rerun the retraining batch after the summary is provenance-complete.",
        ]
    if primary_blocker == "evaluation_contract_incomplete":
        return [
            "Regenerate the evaluation contract and confirm it targets trimed-5min.mp4 with the standing 101 / 98 / false / 0.812 reference.",
        ]
    return [
        "Inspect the latest training_run_summary.json and batch_outcome_analysis.json before rerunning the batch.",
        "Fix the primary blocker and rerun the retraining batch without moving the roadmap forward early.",
    ]


def _build_batch_outcome_analysis(
    *,
    training_completed: bool,
    weights_ready: bool,
    evaluation_contract_ready: bool,
    ready_for_detector_evaluation: bool,
    primary_blocker: str | None,
    error_message: str | None,
) -> dict[str, object]:
    goal_achieved = ready_for_detector_evaluation
    roadmap_advance_allowed = goal_achieved
    if goal_achieved:
        english_summary = (
            "This batch trained a refreshed v2 detector candidate, copied the usable weights back locally, and prepared the next bounded evaluation handoff."
        )
        english_decision = (
            "The batch achieved its goal, so the roadmap may advance to evaluating the refreshed touchline detector candidate."
        )
    else:
        blocker_text = str(primary_blocker or "unknown_blocker").replace("_", " ")
        english_summary = (
            "This batch was trying to produce a complete, evaluation-ready v2 detector candidate, but it did not get there yet."
        )
        english_decision = (
            f"The batch did not achieve its goal, so the roadmap must stay on retraining until we fix the current blocker: {blocker_text}."
        )
    return {
        "batchGoal": "Train one refreshed v2 detector candidate from the Phase 1B densified export and make it evaluation-ready.",
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": roadmap_advance_allowed,
        "englishSummary": english_summary,
        "englishDecision": english_decision,
        "primaryBlocker": primary_blocker,
        "trainingCompleted": training_completed,
        "weightsReady": weights_ready,
        "evaluationContractReady": evaluation_contract_ready,
        "readyForDetectorEvaluation": ready_for_detector_evaluation,
        "nextRecommendedNextLever": NEXT_LEVER_EVALUATE if goal_achieved else NEXT_LEVER_RETRAIN,
        "brainstormFixes": [] if goal_achieved else _brainstorm_fixes(primary_blocker, error_message),
    }


def _batch_outcome_markdown(batch_outcome_analysis: dict[str, object]) -> str:
    fixes = list(batch_outcome_analysis.get("brainstormFixes") or [])
    fix_lines = "\n".join(f"- {fix}" for fix in fixes) if fixes else "- None"
    return "\n".join(
        [
            "# Batch Outcome Analysis",
            "",
            f"Batch goal: {batch_outcome_analysis.get('batchGoal')}",
            f"Goal achieved: {batch_outcome_analysis.get('goalAchieved')}",
            f"Roadmap advance allowed: {batch_outcome_analysis.get('roadmapAdvanceAllowed')}",
            "",
            f"Summary: {batch_outcome_analysis.get('englishSummary')}",
            f"Decision: {batch_outcome_analysis.get('englishDecision')}",
            f"Primary blocker: {batch_outcome_analysis.get('primaryBlocker')}",
            "",
            f"Training completed: {batch_outcome_analysis.get('trainingCompleted')}",
            f"Weights ready: {batch_outcome_analysis.get('weightsReady')}",
            f"Evaluation contract ready: {batch_outcome_analysis.get('evaluationContractReady')}",
            f"Ready for detector evaluation: {batch_outcome_analysis.get('readyForDetectorEvaluation')}",
            f"Next recommended next lever: {batch_outcome_analysis.get('nextRecommendedNextLever')}",
            "",
            "Brainstormed fixes:",
            fix_lines,
            "",
            "Roadmap rule: the roadmap only advances when this generated batch outcome artifact says the batch goal was achieved.",
            "",
        ]
    )


def _allocated_gpu_id(session: dict[str, object], remote_training_result: dict[str, object]) -> str | None:
    for value in (
        remote_training_result.get("allocatedGpuId"),
        remote_training_result.get("remoteDeviceName"),
        (session.get("podPayload") or {}).get("gpuId") if isinstance(session.get("podPayload"), dict) else None,
    ):
        text = str(value or "").strip()
        if text:
            return text
    return None


def run_touchline_detector_candidate_training(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    execution_mode: str = DEFAULT_EXECUTION_MODE,
) -> dict[str, object]:
    runpod_session.require_retired_runpod_disabled()


def main() -> None:
    runpod_session.require_retired_runpod_disabled()


if __name__ == "__main__":
    main()
