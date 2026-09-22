"""Historical remediation recipe, retired with its RunPod execution path."""

from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

if __name__ == "__main__":
    from backend.scripts.runpod_session import require_retired_runpod_disabled

    require_retired_runpod_disabled()

import copy
import json
from pathlib import Path
import shlex
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.app.storage import Storage  # noqa: E402
import backend.scripts.run_touchline_detector_candidate_proposal_signal_generation_fix as proposal_signal_generation_fix  # noqa: E402
from backend.scripts import runpod_session  # noqa: E402


DEFAULT_BATCH_NAME = "touchline_validation_gate_remediation_v1"
DEFAULT_TRAINING_BATCH_NAME = "touchline_validation_gate_remediation_v1"
DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v5"
DEFAULT_BLOCKED_CANDIDATE_NAME = "touchline_detector_candidate_v4"
DEFAULT_PREVIOUS_BATCH_NAME = "touchline_model_data_quality_fix_v1"
DEFAULT_BLOCKED_EXPORT_BATCH_NAME = "touchline_proposal_signal_generation_fix_v1"
DEFAULT_FAILING_SOURCE_CLIP_ID = "trimed-5min.mp4"
DEFAULT_COMPARISON_SOURCE_CLIP_ID = "trimed-football-2-1minute.mp4"
DEFAULT_EXECUTION_MODE = proposal_signal_generation_fix.DEFAULT_EXECUTION_MODE
NEXT_LEVER_EVALUATE = "evaluate_touchline_detector_candidate"
DETECTOR_PROFILE = proposal_signal_generation_fix.DETECTOR_PROFILE
PLATEAU_BASELINE = dict(proposal_signal_generation_fix.PLATEAU_BASELINE)
CHECKLIST_RELATIVE_PATH = Path("docs") / "superpowers" / "plans" / "2026-04-23-phase-3-v4-quality-gate-remediation.md"

_ORIGINAL_VIDEO_FRAME_SHAPE = proposal_signal_generation_fix._video_frame_shape
_ORIGINAL_EXTRACT_CROP_IMAGE = proposal_signal_generation_fix._extract_crop_image


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _safe_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _json_safe_metrics(metrics: object) -> dict[str, object]:
    return proposal_signal_generation_fix._json_safe_metrics(metrics)


def _video_frame_shape(video_path: Path) -> tuple[int, int]:
    return _ORIGINAL_VIDEO_FRAME_SHAPE(video_path)


def _extract_crop_image(
    *,
    video_path: Path,
    frame_id: int,
    crop_window: tuple[int, int, int, int],
    output_path: Path,
) -> tuple[int, int]:
    return _ORIGINAL_EXTRACT_CROP_IMAGE(
        video_path=video_path,
        frame_id=frame_id,
        crop_window=crop_window,
        output_path=output_path,
    )


def _bind_export_helpers() -> None:
    proposal_signal_generation_fix._video_frame_shape = _video_frame_shape
    proposal_signal_generation_fix._extract_crop_image = _extract_crop_image


def _paths(storage_root: Path) -> dict[str, Path]:
    suite_root = storage_root / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
    previous_root = storage_root / "training_prep" / DEFAULT_PREVIOUS_BATCH_NAME
    blocked_export_root = storage_root / "training_prep" / DEFAULT_BLOCKED_EXPORT_BATCH_NAME / "yolo_export"
    blocked_candidate_root = storage_root / "trained_detector_candidates" / DEFAULT_BLOCKED_CANDIDATE_NAME
    artifact_root = storage_root / "training_prep" / DEFAULT_BATCH_NAME
    candidate_root = storage_root / "trained_detector_candidates" / DEFAULT_CANDIDATE_NAME
    return {
        "suiteSummaryPath": suite_root / "suite_summary.json",
        "activeLaneSnapshotPath": suite_root / "active_lane_snapshot.json",
        "currentManifestPath": previous_root / "data_quality_fix_manifest.json",
        "currentOverlayPath": previous_root / "reviewed_label_overlay.json",
        "blockedDatasetYamlPath": blocked_export_root / "dataset.yaml",
        "blockedCandidateRoot": blocked_candidate_root,
        "artifactRoot": artifact_root,
        "manifestPath": artifact_root / "validation_gate_remediation_manifest.json",
        "splitManifestPath": artifact_root / "split_manifest.json",
        "batchOutcomeJsonPath": artifact_root / "batch_outcome_analysis.json",
        "batchOutcomeMarkdownPath": artifact_root / "batch_outcome_analysis.md",
        "exportRoot": artifact_root / "yolo_export",
        "candidateRoot": candidate_root,
        "trainingConfigPath": candidate_root / "training_config.json",
        "trainingSummaryPath": candidate_root / "training_run_summary.json",
        "evaluationContractPath": candidate_root / "evaluation_contract.json",
        "candidateBatchOutcomeJsonPath": candidate_root / "batch_outcome_analysis.json",
        "candidateBatchOutcomeMarkdownPath": candidate_root / "batch_outcome_analysis.md",
        "remoteTrainingResultPath": candidate_root / "remote_training_result.json",
    }


def _positive_export_counts_by_unit(
    *,
    current_manifest: dict[str, object],
    current_overlay: dict[str, object],
    storage: Storage,
) -> dict[str, int]:
    _bind_export_helpers()
    export_examples, _full_frame_area, _proposal_area = proposal_signal_generation_fix._build_export_examples(
        current_manifest=current_manifest,
        current_overlay=current_overlay,
        storage=storage,
    )
    positive_counts: dict[str, int] = {}
    for example in export_examples:
        if not str(example.get("labelLine") or "").strip():
            continue
        curation_unit_id = str(example.get("curationUnitId") or "")
        positive_counts[curation_unit_id] = positive_counts.get(curation_unit_id, 0) + 1
    return positive_counts


def _select_validation_positive_curation_unit(
    *,
    current_manifest: dict[str, object],
    current_overlay: dict[str, object],
    storage: Storage,
) -> tuple[str, int]:
    positive_counts = _positive_export_counts_by_unit(
        current_manifest=current_manifest,
        current_overlay=current_overlay,
        storage=storage,
    )
    candidates: list[tuple[int, int, str]] = []
    for unit in list(current_manifest.get("curationUnits") or []):
        if not isinstance(unit, dict):
            continue
        if str(unit.get("sourceClipId") or "") != DEFAULT_FAILING_SOURCE_CLIP_ID:
            continue
        curation_unit_id = str(unit.get("curationUnitId") or "")
        positive_count = positive_counts.get(curation_unit_id, 0)
        if positive_count <= 0:
            continue
        frame_start = _safe_int(unit.get("frameStart"), 0)
        candidates.append((positive_count, frame_start, curation_unit_id))
    if not candidates:
        raise RuntimeError("No eligible failing-source positive curation unit found for validation split remediation.")
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    positive_count, _frame_start, curation_unit_id = candidates[0]
    return curation_unit_id, positive_count


def _remapped_manifest_and_overlay(
    *,
    current_manifest: dict[str, object],
    current_overlay: dict[str, object],
    selected_validation_positive_curation_unit_id: str,
) -> tuple[dict[str, object], dict[str, object]]:
    adjusted_manifest = copy.deepcopy(current_manifest)
    adjusted_overlay = copy.deepcopy(current_overlay)
    unit_split_map: dict[str, str] = {}
    for unit in list(adjusted_manifest.get("curationUnits") or []):
        if not isinstance(unit, dict):
            continue
        curation_unit_id = str(unit.get("curationUnitId") or "")
        split_name = "train"
        if str(unit.get("sourceClipId") or "") == DEFAULT_COMPARISON_SOURCE_CLIP_ID:
            split_name = "val"
        elif curation_unit_id == selected_validation_positive_curation_unit_id:
            split_name = "val"
        unit["split"] = split_name
        unit_split_map[curation_unit_id] = split_name
        for example in list(unit.get("examples") or []):
            if isinstance(example, dict):
                example["split"] = split_name
    for review_item in list(adjusted_overlay.get("reviewItems") or []):
        if not isinstance(review_item, dict):
            continue
        review_item["split"] = unit_split_map.get(str(review_item.get("curationUnitId") or ""), "train")
    return adjusted_manifest, adjusted_overlay


def _build_split_manifest(
    *,
    adjusted_manifest: dict[str, object],
    adjusted_overlay: dict[str, object],
    export_examples: list[dict[str, object]],
) -> dict[str, object]:
    curation_unit_splits: dict[str, set[str]] = {}
    unit_by_id = {
        str(unit.get("curationUnitId") or ""): dict(unit)
        for unit in list(adjusted_manifest.get("curationUnits") or [])
        if isinstance(unit, dict)
    }
    validation_positive_curation_unit_ids: set[str] = set()
    validation_control_curation_unit_ids: set[str] = set()
    for example in export_examples:
        curation_unit_id = str(example.get("curationUnitId") or "")
        split_name = str(example.get("split") or "")
        curation_unit_splits.setdefault(curation_unit_id, set()).add(split_name)
        unit = unit_by_id.get(curation_unit_id, {})
        if split_name == "val" and str(example.get("labelLine") or "").strip():
            validation_positive_curation_unit_ids.add(curation_unit_id)
        if split_name == "val" and str(unit.get("sourceClipId") or "") == DEFAULT_COMPARISON_SOURCE_CLIP_ID:
            validation_control_curation_unit_ids.add(curation_unit_id)
    validation_positive_label_image_count = 0
    for review_item in list(adjusted_overlay.get("reviewItems") or []):
        if not isinstance(review_item, dict):
            continue
        if str(review_item.get("split") or "") != "val":
            continue
        if proposal_signal_generation_fix._bbox_from_review_item(review_item) is None:
            continue
        validation_positive_label_image_count += 1
    validation_empty_label_image_count = 0
    for unit in unit_by_id.values():
        if str(unit.get("split") or "") != "val":
            continue
        for example in list(unit.get("examples") or []):
            if not isinstance(example, dict):
                continue
            if str(example.get("seedSource") or "") == "hard_negative":
                validation_empty_label_image_count += 1
    validation_image_count = validation_positive_label_image_count + validation_empty_label_image_count
    leakage_detected = any(len(splits) > 1 for splits in curation_unit_splits.values())
    return {
        "generatedAt": _utc_now_iso(),
        "batchName": DEFAULT_BATCH_NAME,
        "exportImageMode": "proposal_crops",
        "curationUnitCount": len(unit_by_id),
        "validationImageCount": validation_image_count,
        "validationPositiveCurationUnitCount": len(validation_positive_curation_unit_ids),
        "validationControlCurationUnitCount": len(validation_control_curation_unit_ids),
        "validationPositiveLabelImageCount": validation_positive_label_image_count,
        "validationEmptyLabelImageCount": validation_empty_label_image_count,
        "validationInformative": validation_image_count > 0 and validation_positive_label_image_count > 0,
        "sourceAwareSplitLeakageDetected": leakage_detected,
    }


def _build_training_config(
    *,
    artifact_root: Path,
    dataset_yaml_path: Path,
    suite_summary: dict[str, object],
    active_lane_snapshot: dict[str, object],
    selected_validation_positive_curation_unit_id: str,
    blocked_v4_gate_summary: dict[str, object],
    requested_gpu_id: str | None,
    execution_mode: str,
) -> dict[str, object]:
    training_recipe = proposal_signal_generation_fix._training_recipe()
    baseline_fingerprint = dict(active_lane_snapshot.get("baselineFingerprint") or {})
    return {
        "generatedAt": _utc_now_iso(),
        "trainingBatchName": DEFAULT_TRAINING_BATCH_NAME,
        "trainingCandidateName": DEFAULT_CANDIDATE_NAME,
        "artifactRoot": str(artifact_root),
        "datasetYamlPath": str(dataset_yaml_path),
        "executionMode": execution_mode,
        "requestedGpuId": requested_gpu_id,
        "datasetLineage": {
            "validationGateRemediationBatchName": DEFAULT_BATCH_NAME,
            "blockedCandidateName": DEFAULT_BLOCKED_CANDIDATE_NAME,
            "blockedCandidateTrainingQualityGatePassed": bool(
                blocked_v4_gate_summary.get("trainingQualityGatePassed")
            ),
            "blockedCandidateTrainingQualityGatePrimaryBlocker": blocked_v4_gate_summary.get(
                "trainingQualityGatePrimaryBlocker"
            ),
            "selectedValidationPositiveCurationUnitId": selected_validation_positive_curation_unit_id,
        },
        "trainingRecipe": training_recipe,
        "baselineReference": {
            "suiteVerdict": suite_summary.get("suiteVerdict"),
            "sourceRobustnessOutcome": suite_summary.get("sourceRobustnessOutcome"),
            "sourceRobustnessRecommendedNextLever": suite_summary.get("sourceRobustnessRecommendedNextLever"),
            "baselineFingerprint": baseline_fingerprint,
        },
        "detectorProfile": DETECTOR_PROFILE,
        "notes": [
            "This batch repairs the proposal-signal validation split without changing the v4 training recipe.",
            "Bounded detector evaluation remains blocked until the training-quality gate passes.",
        ],
    }


def _rewrite_dataset_yaml_for_remote(dataset_yaml_path: Path, *, remote_export_root: str) -> str:
    return proposal_signal_generation_fix._rewrite_dataset_yaml_for_remote(
        dataset_yaml_path,
        remote_export_root=remote_export_root,
    )


def _stage_dataset_on_pod(
    *,
    session: dict[str, object],
    dataset_export_root: Path,
    dataset_yaml_path: Path,
) -> str:
    remote_export_root = f"{session['remoteStorageRoot']}/training_prep/{DEFAULT_BATCH_NAME}/yolo_export"
    proposal_signal_generation_fix.runpod_session.copy_directory_to_pod(
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
        proposal_signal_generation_fix.runpod_session.copy_file_to_pod(
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
source {shlex.quote(proposal_signal_generation_fix.runpod_session.DEFAULT_POD_VENV_PATH)}/bin/activate
export PYTHONPATH={shlex.quote(remote_repo_root)}
export YOLO_CONFIG_DIR={shlex.quote(proposal_signal_generation_fix.runpod_session.DEFAULT_POD_YOLO_CONFIG_DIR)}
mkdir -p {shlex.quote(remote_project_root)} {shlex.quote(proposal_signal_generation_fix.runpod_session.DEFAULT_POD_YOLO_CONFIG_DIR)}
python - <<'PY'
import json
import torch

import backend.train_custom as train_custom

result = train_custom.fine_tune(
    data_yaml={remote_dataset_yaml_path!r},
    model_path={staged_model_path!r},
    epochs={_safe_int(training_recipe.get("epochs"), proposal_signal_generation_fix.DEFAULT_EPOCHS)},
    imgsz={_safe_int(training_recipe.get("imgsz"), proposal_signal_generation_fix.DEFAULT_IMGSZ)},
    batch={_safe_int(training_recipe.get("batch"), proposal_signal_generation_fix.DEFAULT_BATCH_SIZE)},
    device={str(training_recipe.get("device") or proposal_signal_generation_fix.DEFAULT_DEVICE)!r},
    project={remote_project_root!r},
    name="training",
    patience={_safe_int(training_recipe.get("patience"), proposal_signal_generation_fix.DEFAULT_EPOCHS)},
    workers={_safe_int(training_recipe.get("workers"), proposal_signal_generation_fix.DEFAULT_WORKERS)},
    seed={_safe_int(training_recipe.get("seed"), proposal_signal_generation_fix.DEFAULT_SEED)},
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


def _build_evaluation_contract(
    *,
    active_lane_snapshot: dict[str, object],
    best_weights_path: str | None,
    last_weights_path: str | None,
    candidate_ready: bool,
) -> dict[str, object]:
    baseline_fingerprint = dict(active_lane_snapshot.get("baselineFingerprint") or {})
    return {
        "generatedAt": _utc_now_iso(),
        "trainingCandidateName": DEFAULT_CANDIDATE_NAME,
        "trainingBatchName": DEFAULT_TRAINING_BATCH_NAME,
        "candidateReadyForEvaluation": candidate_ready,
        "localScreenTargetClipPath": str(REPO_ROOT / "videos" / DEFAULT_FAILING_SOURCE_CLIP_ID),
        "remoteProofComparisonBaseline": dict(PLATEAU_BASELINE),
        "activeFrozenBaseline": {
            "detectorModelPath": baseline_fingerprint.get("detectorModelPath")
            or proposal_signal_generation_fix.DEFAULT_BASE_MODEL_PATH,
            "primaryMode": baseline_fingerprint.get("primaryMode") or "anchored_player_ranked_context_960",
            "cleanupLane": baseline_fingerprint.get("cleanupLane")
            or "recent_ball_plus_inward_anchor_center_bias35_960",
        },
        "candidateWeights": {
            "bestWeightsPath": best_weights_path,
            "lastWeightsPath": last_weights_path,
        },
        "auxiliaryBallModelProfile": DETECTOR_PROFILE,
        "promotionReadySuccessMeans": [
            "candidate is allowed to enter bounded detector evaluation",
            "candidate is still not promoted into runtime defaults by this batch",
        ],
        "failFastConditions": [
            "training artifact missing",
            "weights unusable",
            "training-quality gate failed",
        ],
    }


def _candidate_brainstorm_fixes(primary_blocker: str | None) -> list[str]:
    if primary_blocker == "validation_split_has_no_positive_labels":
        return [
            "Repair the proposal-signal validation split so it contains at least one positive failing-source curation unit.",
            "Keep the roadmap on evaluate_touchline_detector_candidate and do not spend GPU evaluation time until the gate passes.",
        ]
    if primary_blocker == "zero_validation_metrics":
        return [
            "Inspect the repaired validation split and training results together before bounded evaluation.",
            "Confirm the saved metrics move off zero before treating the candidate as evaluation-ready.",
        ]
    if primary_blocker == "local_positive_sanity_zero_detections":
        return [
            "Run a local crop-level sanity check on positive proposal images and inspect why the detector still returns zero detections.",
            "Iterate inside the same Phase 3 checklist until the local positive sanity gate passes.",
        ]
    if primary_blocker == "weights_unusable":
        return [
            "Recover the missing best.pt artifact or rerun the remediation training batch.",
        ]
    if primary_blocker == "remote_training_failed":
        return [
            "Inspect the remote training error and rerun the same remediation batch without advancing the roadmap.",
        ]
    return [
        "Inspect the latest training_quality_gate_v1 and batch_outcome_analysis artifacts before rerunning this remediation batch.",
        "Append the next corrective sub-batch to the same Phase 3 checklist until the gate passes.",
    ]


def _build_candidate_batch_outcome(
    *,
    training_completed: bool,
    weights_ready: bool,
    evaluation_contract_ready: bool,
    training_quality_gate_passed: bool,
    ready_for_detector_evaluation: bool,
    primary_blocker: str | None,
) -> dict[str, object]:
    goal_achieved = ready_for_detector_evaluation
    if goal_achieved:
        english_summary = (
            "This batch retrained a new v5 candidate on the repaired validation split and the training-quality gate passed."
        )
        english_decision = (
            "The batch achieved its goal. The roadmap stays in Phase 3, but bounded detector evaluation is now allowed to resume with v5."
        )
    else:
        blocker_text = str(primary_blocker or "unknown_blocker").replace("_", " ")
        english_summary = (
            "This batch was trying to produce a gate-clean v5 candidate, but the training-quality remediation is still blocked."
        )
        english_decision = (
            f"The batch did not achieve its goal, so bounded evaluation must stay blocked while we fix the current blocker: {blocker_text}."
        )
    return {
        "batchGoal": "Repair the proposal-signal validation split, retrain one v5 candidate, and require the training-quality gate to pass before bounded evaluation.",
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": False,
        "englishSummary": english_summary,
        "englishDecision": english_decision,
        "primaryBlocker": primary_blocker,
        "trainingCompleted": training_completed,
        "weightsReady": weights_ready,
        "evaluationContractReady": evaluation_contract_ready,
        "trainingQualityGatePassed": training_quality_gate_passed,
        "readyForDetectorEvaluation": ready_for_detector_evaluation,
        "nextRecommendedNextLever": NEXT_LEVER_EVALUATE,
        "brainstormFixes": [] if goal_achieved else _candidate_brainstorm_fixes(primary_blocker),
    }


def _candidate_batch_outcome_markdown(batch_outcome_analysis: dict[str, object]) -> str:
    fixes = list(batch_outcome_analysis.get("brainstormFixes") or [])
    fix_lines = "\n".join(f"- {fix}" for fix in fixes) if fixes else "- None"
    return "\n".join(
        [
            "# Candidate Batch Outcome Analysis",
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
            f"Training-quality gate passed: {batch_outcome_analysis.get('trainingQualityGatePassed')}",
            f"Ready for detector evaluation: {batch_outcome_analysis.get('readyForDetectorEvaluation')}",
            "",
            "Brainstormed fixes:",
            fix_lines,
            "",
        ]
    )


def _build_batch_outcome_analysis(
    *,
    validation_informative: bool,
    source_aware_split_leakage_detected: bool,
    yolo_export_ready: bool,
    training_completed: bool,
    weights_ready: bool,
    training_quality_gate_passed: bool,
    ready_for_detector_evaluation: bool,
    primary_blocker: str | None,
) -> dict[str, object]:
    goal_achieved = (
        validation_informative
        and not source_aware_split_leakage_detected
        and yolo_export_ready
        and training_completed
        and weights_ready
        and training_quality_gate_passed
        and ready_for_detector_evaluation
    )
    if goal_achieved:
        english_summary = (
            "This remediation batch repaired the validation split, retrained v5, and cleared the training-quality gate without leaving Phase 3."
        )
        english_decision = (
            "The batch achieved its goal. The roadmap stays on evaluate_touchline_detector_candidate, and the next honest move is bounded detector evaluation of v5."
        )
        fixes: list[str] = []
    else:
        blocker_text = str(primary_blocker or "unknown_blocker").replace("_", " ")
        english_summary = (
            "This remediation batch was trying to unblock bounded detector evaluation, but the training-quality gate is still not cleared."
        )
        english_decision = (
            f"The batch did not achieve its goal, so the roadmap stays pinned inside Phase 3 while we fix the current blocker: {blocker_text}."
        )
        fixes = _candidate_brainstorm_fixes(primary_blocker)
    return {
        "batchGoal": "Repair the proposal-signal validation split and retrain a gate-clean v5 candidate before bounded detector evaluation.",
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": False,
        "englishSummary": english_summary,
        "englishDecision": english_decision,
        "primaryBlocker": primary_blocker,
        "validationInformative": validation_informative,
        "yoloExportReady": yolo_export_ready,
        "trainingCompleted": training_completed,
        "weightsReady": weights_ready,
        "trainingQualityGatePassed": training_quality_gate_passed,
        "readyForDetectorEvaluation": ready_for_detector_evaluation,
        "nextRecommendedNextLever": NEXT_LEVER_EVALUATE,
        "brainstormFixes": fixes,
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
            f"Validation informative: {batch_outcome_analysis.get('validationInformative')}",
            f"YOLO export ready: {batch_outcome_analysis.get('yoloExportReady')}",
            f"Training completed: {batch_outcome_analysis.get('trainingCompleted')}",
            f"Weights ready: {batch_outcome_analysis.get('weightsReady')}",
            f"Training-quality gate passed: {batch_outcome_analysis.get('trainingQualityGatePassed')}",
            f"Ready for detector evaluation: {batch_outcome_analysis.get('readyForDetectorEvaluation')}",
            "",
            "Brainstormed fixes:",
            fix_lines,
            "",
        ]
    )


def _write_checklist(
    *,
    checklist_path: Path,
    blocked_v4_gate_summary: dict[str, object],
    selected_validation_positive_curation_unit_id: str,
    split_manifest: dict[str, object],
    batch_outcome_analysis: dict[str, object],
    candidate_batch_outcome: dict[str, object],
) -> None:
    goal_achieved = bool(batch_outcome_analysis.get("goalAchieved"))
    training_quality_gate_passed = bool(candidate_batch_outcome.get("trainingQualityGatePassed"))
    content = "\n".join(
        [
            "# Phase 3 V4 Quality-Gate Remediation",
            "",
            "## Blocker",
            f"- `touchline_detector_candidate_v4` is blocked by the training-quality gate: `{blocked_v4_gate_summary.get('trainingQualityGatePrimaryBlocker')}`.",
            f"- Validation images: `{blocked_v4_gate_summary.get('validationImageCount')}`",
            f"- Validation positive label images: `{blocked_v4_gate_summary.get('validationPositiveLabelImageCount')}`",
            f"- Validation empty label images: `{blocked_v4_gate_summary.get('validationEmptyLabelImageCount')}`",
            "",
            "## Acceptance Criteria",
            f"- [x] Strict checklist exists at `{checklist_path.relative_to(checklist_path.parents[3])}`." if len(checklist_path.parents) >= 4 else f"- [x] Strict checklist exists at `{checklist_path}`.",
            f"- [{'x' if bool(split_manifest.get('validationInformative')) else ' '}] Repaired validation split is informative.",
            f"- [{'x' if not bool(split_manifest.get('sourceAwareSplitLeakageDetected')) else ' '}] Repaired split is leakage-safe at the curation-unit level.",
            f"- [{'x' if training_quality_gate_passed else ' '}] New v5 candidate passes the training-quality gate.",
            f"- [{'x' if goal_achieved else ' '}] Bounded detector evaluation may remain blocked until the gate passes.",
            "",
            "## Ordered Tasks",
            "- [x] Reclassify v4 with a candidate-local training-quality gate artifact.",
            f"- [x] Repair the proposal-signal validation split by moving `{selected_validation_positive_curation_unit_id}` into val beside the control negative unit.",
            "- [x] Retrain one new candidate lineage `touchline_detector_candidate_v5`.",
            f"- [{'x' if training_quality_gate_passed else ' '}] Require the training-quality gate to pass before treating v5 as evaluation-ready.",
            "- [x] Keep the roadmap pinned to `evaluate_touchline_detector_candidate`.",
            "",
            "## Iteration Rule",
            "- If any blocker remains, append the next corrective sub-batch to this file and stay inside Phase 3 until the gate passes.",
            "",
        ]
    )
    _write_markdown(checklist_path, content)


def run_touchline_validation_gate_remediation(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    repo_root: Path = REPO_ROOT,
    checklist_path: Path | None = None,
    execution_mode: str = DEFAULT_EXECUTION_MODE,
) -> dict[str, object]:
    runpod_session.require_retired_runpod_disabled()


def main(argv: list[str] | None = None) -> int:
    runpod_session.require_retired_runpod_disabled()


if __name__ == "__main__":
    raise SystemExit(main())
