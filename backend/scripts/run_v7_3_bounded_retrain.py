"""Historical training recipe, retired with its RunPod execution path."""

from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path
import shlex
import tempfile
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402
import backend.scripts.run_v7_1_bounded_retrain as bounded_v7_1  # noqa: E402
import backend.scripts.run_v7_1_tiny_overfit_sanity_train as tiny_train  # noqa: E402
import backend.scripts.runpod_session as runpod_session  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_INPUT_BATCH_NAME = "v7_3_export_label_overlay_audit_v1"
DEFAULT_OUTPUT_DIR_NAME = "v7_3_bounded_retrain_v1"
DEFAULT_EXPORT_PREVIEW_DIR_NAME = "v7_3_export_preview"

CONF_SWEEP = bounded_v7_1.CONF_SWEEP
SELECTED_AUDIT_CONF = bounded_v7_1.SELECTED_AUDIT_CONF

PASS_MIN_TRAIN_LOCALIZATION_RATE = bounded_v7_1.PASS_MIN_TRAIN_LOCALIZATION_RATE
PASS_MIN_VAL_LOCALIZATION_RATE = bounded_v7_1.PASS_MIN_VAL_LOCALIZATION_RATE
PASS_MAX_TRAIN_NEGATIVE_FP_RATE = bounded_v7_1.PASS_MAX_TRAIN_NEGATIVE_FP_RATE
PASS_MAX_VAL_NEGATIVE_FP_RATE = bounded_v7_1.PASS_MAX_VAL_NEGATIVE_FP_RATE
PASS_MAX_CANARY_FP_RATE = bounded_v7_1.PASS_MAX_CANARY_FP_RATE
PASS_MIN_TRAIN_MEDIAN_CONFIDENCE = bounded_v7_1.PASS_MIN_TRAIN_MEDIAN_CONFIDENCE
PASS_MIN_VAL_MEDIAN_CONFIDENCE = bounded_v7_1.PASS_MIN_VAL_MEDIAN_CONFIDENCE
PASS_MAX_TOP_LEFT_SHARE = bounded_v7_1.PASS_MAX_TOP_LEFT_SHARE
PASS_MAX_GIANT_BOX_SHARE = bounded_v7_1.PASS_MAX_GIANT_BOX_SHARE
PASS_MIN_AREA_RATIO = bounded_v7_1.PASS_MIN_AREA_RATIO
PASS_MAX_AREA_RATIO = bounded_v7_1.PASS_MAX_AREA_RATIO

BLOCKER_TRAIN_FAILED = "v7_3_bounded_train_failed_to_complete"
BLOCKER_CHECKPOINT = "v7_3_bounded_checkpoint_contract_failure"
BLOCKER_LABELS = "v7_3_bounded_label_ingestion_failure"
BLOCKER_TRAIN_POSITIVE = "v7_3_bounded_positive_localization_failure"
BLOCKER_VAL_RECALL = "v7_3_bounded_validation_recall_insufficient"
BLOCKER_NEGATIVE_FLOOD = "v7_3_bounded_negative_false_positive_flood"
BLOCKER_CANARY_FLOOD = "v7_3_bounded_canary_flood"
BLOCKER_TOP_LEFT = "v7_3_bounded_top_left_artifact_regression"
BLOCKER_GIANT = "v7_3_bounded_giant_box_regression"
BLOCKER_CONFIDENCE = "v7_3_bounded_confidence_still_weak"
BLOCKER_MISSING = "v7_3_bounded_overlay_artifacts_missing"

NEXT_GUARDRAIL = "v7_3_crop_probe_precision_guardrail_audit"
NEXT_CONFIG_DEBUG = "v7_3_training_config_or_export_debug"
NEXT_POSITIVE_DIVERSITY = "v7_3_positive_diversity_refresh"
NEXT_HARD_NEGATIVE = "v7_3_hard_negative_expansion"
NEXT_SIGNAL_DEBUG = "v7_3_training_signal_regression_debug"

Trainer = Callable[..., dict[str, Any]]
Predictor = Callable[..., dict[str, Any]]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _checkpoint_path(training_result: dict[str, Any], *keys: str) -> Path | None:
    for key in keys:
        value = training_result.get(key)
        if isinstance(value, str) and value.strip():
            path = Path(value)
            if path.exists():
                return path
    return None


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "bounded_crop_retrain_verified_checkpoint",
                "successCriteria": [
                    "train from v7.3 audited physical export only",
                    "pull best.pt and last.pt locally",
                    "run inference only against verified local trained checkpoints",
                    "advance only if bounded crop metrics pass",
                ],
                "failureAdaptation": "If metrics fail after a valid training run, write blocker truth instead of thrashing.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "bounded_training_contract_repair",
                "successCriteria": [
                    "repair only dataset path, RunPod staging, checkpoint-key, results pullback, or label-ingestion plumbing",
                    "do not change labels, examples, runtime defaults, or promotion criteria",
                ],
                "failureAdaptation": "Retry only the repaired contract path.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "bounded_retrain_blocker_summary",
                "successCriteria": ["write one primary blocker", "select exactly one next family"],
                "failureAdaptation": "Stop with generated truth when the model/data signal is insufficient.",
            },
        ],
    }


def _training_recipe(*, device: str, epochs: int) -> dict[str, Any]:
    recipe = bounded_v7_1._training_recipe(device=device, epochs=epochs)
    recipe["trainingBatchName"] = "v7_3_bounded_retrain"
    recipe["sourceExportBatchName"] = DEFAULT_INPUT_BATCH_NAME
    return recipe


def _run_runpod_training_v7_3(
    *,
    dataset_root: Path,
    data_yaml_path: Path,
    output_root: Path,
    training_recipe: dict[str, Any],
) -> dict[str, Any]:
    session: dict[str, Any] | None = None
    try:
        session = runpod_session.create_runpod_session(
            clip_path=None,
            pod_name=f"{DEFAULT_CANDIDATE_NAME}-v7-3-bounded-retrain",
            gpu_id=None,
        )
        remote_dataset_root = (
            f"{session['remoteStorageRoot']}/trained_detector_candidates/{DEFAULT_CANDIDATE_NAME}/"
            f"{DEFAULT_OUTPUT_DIR_NAME}/bounded_dataset_snapshot"
        )
        runpod_session.copy_directory_to_pod(
            ssh_command=list(session["sshCommand"]),
            local_path=dataset_root,
            remote_path=remote_dataset_root,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_yaml = Path(tmpdir) / "data.yaml"
            temp_yaml.write_text(
                tiny_train._rewrite_dataset_yaml(data_yaml_path, remote_dataset_root=remote_dataset_root),
                encoding="utf-8",
            )
            runpod_session.copy_file_to_pod(
                list(session["sshCommand"]),
                local_path=temp_yaml,
                remote_path=f"{remote_dataset_root}/data.yaml",
            )
        staged_model = runpod_session.stage_model_on_pod(
            ssh_command=list(session["sshCommand"]),
            model_path=str(training_recipe["baseModelPath"]),
            remote_model_path=runpod_session.resolve_remote_model_path(str(training_recipe["baseModelPath"])),
            remote_repo_root=str(session["remoteRepoRoot"]),
        )
        remote_project_root = (
            f"{session['remoteStorageRoot']}/trained_detector_candidates/{DEFAULT_CANDIDATE_NAME}/"
            f"{DEFAULT_OUTPUT_DIR_NAME}/train_run"
        )
        remote_command = f"""
set -euo pipefail
cd {shlex.quote(str(session['remoteRepoRoot']))}
source {shlex.quote(runpod_session.DEFAULT_POD_VENV_PATH)}/bin/activate
export PYTHONPATH={shlex.quote(str(session['remoteRepoRoot']))}
export YOLO_CONFIG_DIR={shlex.quote(runpod_session.DEFAULT_POD_YOLO_CONFIG_DIR)}
mkdir -p {shlex.quote(remote_project_root)} {shlex.quote(runpod_session.DEFAULT_POD_YOLO_CONFIG_DIR)}
python - <<'PY'
import json
import torch
import backend.train_custom as train_custom
result = train_custom.fine_tune(
    data_yaml={f"{remote_dataset_root}/data.yaml"!r},
    model_path={str(staged_model["detectorModelPath"])!r},
    epochs={int(training_recipe["epochs"])},
    imgsz={int(training_recipe["imgsz"])},
    batch={int(training_recipe["batch"])},
    device={str(training_recipe["device"])!r},
    project={remote_project_root!r},
    name="training",
    patience={int(training_recipe["patience"])},
    workers={int(training_recipe["workers"])},
    seed={int(training_recipe["seed"])},
    augmentation_policy={dict(training_recipe["augmentationPolicy"])!r},
)
payload = dict(result)
payload["trainingCompleted"] = True
payload["remoteDeviceName"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
print(json.dumps(payload))
PY
"""
        training_result = runpod_session.run_json_command_over_ssh(
            list(session["sshCommand"]),
            f"bash -lc {shlex.quote(remote_command)}",
        )
        weights_dir = output_root / "train_run" / "weights"
        pulled: dict[str, str] = {}
        for key, name in (("bestWeightsPath", "best.pt"), ("lastWeightsPath", "last.pt")):
            remote_path = str(training_result.get(key) or "")
            if remote_path:
                local_path = weights_dir / name
                runpod_session.pull_pod_file(
                    ssh_command=list(session["sshCommand"]),
                    remote_path=remote_path,
                    local_path=local_path,
                )
                pulled[f"{key}Local"] = str(local_path)
        results_remote = str(training_result.get("resultsCsvPath") or "")
        if results_remote:
            local_results = output_root / "train_run" / "results.csv"
            runpod_session.pull_pod_file(
                ssh_command=list(session["sshCommand"]),
                remote_path=results_remote,
                local_path=local_results,
            )
            pulled["resultsCsvLocalPath"] = str(local_results)
        training_result.update(pulled)
        return training_result
    finally:
        if session is not None:
            cleanup = runpod_session.cleanup_runpod_session(session, stop_pod=True, delete_pod=True)
            _write_json(output_root / "remote_cleanup_result.json", cleanup)


def _classify_selected(selected: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if selected["boundedTrainPositiveLocalizationHitRate"] < PASS_MIN_TRAIN_LOCALIZATION_RATE:
        return (
            BLOCKER_TRAIN_POSITIVE,
            NEXT_SIGNAL_DEBUG,
            False,
            "v7.3 bounded crop training did not localize enough training positives; stay in training/config debug.",
        )
    if selected["boundedValPositiveLocalizationHitRate"] < PASS_MIN_VAL_LOCALIZATION_RATE:
        return (
            BLOCKER_VAL_RECALL,
            NEXT_POSITIVE_DIVERSITY,
            False,
            "v7.3 train positives localize, but validation recall is too low; positive diversity is the next constraint.",
        )
    if selected["boundedTrainNegativeFalsePositiveFrameRate"] > PASS_MAX_TRAIN_NEGATIVE_FP_RATE:
        return (
            BLOCKER_NEGATIVE_FLOOD,
            NEXT_HARD_NEGATIVE,
            False,
            "v7.3 detector fires on too many training hard negatives; expand and rebalance hard negatives.",
        )
    if selected["boundedValNegativeFalsePositiveFrameRate"] > PASS_MAX_VAL_NEGATIVE_FP_RATE:
        return (
            BLOCKER_NEGATIVE_FLOOD,
            NEXT_HARD_NEGATIVE,
            False,
            "v7.3 detector fires on too many validation hard negatives; expand and rebalance hard negatives.",
        )
    if selected["heldoutCanaryFalsePositiveFrameRate"] > PASS_MAX_CANARY_FP_RATE:
        return (
            BLOCKER_CANARY_FLOOD,
            NEXT_HARD_NEGATIVE,
            False,
            "v7.3 detector floods heldout top-left canaries; expand the hard-negative lane.",
        )
    if selected["topLeftArtifactShare"] > PASS_MAX_TOP_LEFT_SHARE:
        return (
            BLOCKER_TOP_LEFT,
            NEXT_HARD_NEGATIVE,
            False,
            "The old top-left artifact signature reappeared during v7.3 bounded retrain.",
        )
    area_ratio = selected.get("medianDetectedBoxAreaToGtBoxAreaRatio")
    if selected["giantBoxShare"] > PASS_MAX_GIANT_BOX_SHARE or (
        area_ratio is not None and (area_ratio < PASS_MIN_AREA_RATIO or area_ratio > PASS_MAX_AREA_RATIO)
    ):
        return (
            BLOCKER_GIANT,
            NEXT_SIGNAL_DEBUG,
            False,
            "v7.3 bounded retrain produced badly scaled boxes relative to reviewed ball labels.",
        )
    if (selected["medianTrainPositiveConfidence"] or 0.0) <= PASS_MIN_TRAIN_MEDIAN_CONFIDENCE or (
        selected["medianValPositiveConfidence"] or 0.0
    ) <= PASS_MIN_VAL_MEDIAN_CONFIDENCE:
        return (
            BLOCKER_CONFIDENCE,
            NEXT_SIGNAL_DEBUG,
            False,
            "v7.3 bounded retrain localizes but confidence remains too weak for a useful crop detector gate.",
        )
    return (
        None,
        NEXT_GUARDRAIL,
        True,
        "v7.3 bounded crop retrain passed. Advance to crop probe precision guardrail audit; do not promote.",
    )


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# V7.3 Bounded Retrain",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Checkpoint contract passed: `{summary.get('checkpointContractPassed')}`",
            f"- Selected checkpoint: `{summary.get('selectedCheckpointForVerdict')}`",
            f"- Selected confidence: `{summary.get('selectedAuditConf')}`",
            f"- Train positive localization: `{summary.get('boundedTrainPositiveLocalizationHitRate')}`",
            f"- Validation positive localization: `{summary.get('boundedValPositiveLocalizationHitRate')}`",
            f"- Train negative false-positive rate: `{summary.get('boundedTrainNegativeFalsePositiveFrameRate')}`",
            f"- Validation negative false-positive rate: `{summary.get('boundedValNegativeFalsePositiveFrameRate')}`",
            f"- Canary false-positive rate: `{summary.get('heldoutCanaryFalsePositiveFrameRate')}`",
            f"- Median train confidence: `{summary.get('medianTrainPositiveConfidence')}`",
            f"- Median validation confidence: `{summary.get('medianValPositiveConfidence')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_v7_3_bounded_retrain(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    use_runpod: bool = False,
    trainer: Trainer | None = None,
    predictor: Predictor | None = None,
    attempt_number: int = 1,
    attempt_approach_family: str = "bounded_crop_retrain_verified_checkpoint",
    training_device: str = "0",
    training_epochs: int = 80,
) -> dict[str, Any]:
    runpod_session.require_retired_runpod_disabled()


def main() -> None:
    runpod_session.require_retired_runpod_disabled()


if __name__ == "__main__":
    main()
