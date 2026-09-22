"""Historical evaluation recipe, retired with its RunPod execution path."""

from __future__ import annotations
from backend.scripts.football_external_real_eval_chain_common import load_json_object_strict as _load_json


from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

if __name__ == "__main__":
    from backend.scripts.runpod_session import require_retired_runpod_disabled

    require_retired_runpod_disabled()

from datetime import datetime, timezone
from pathlib import Path
import shlex

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
import backend.scripts.run_detector_breadth_batch as run_detector_breadth_batch  # noqa: E402
import backend.scripts.run_source_robustness_batch as run_source_robustness_batch  # noqa: E402
import backend.scripts.runpod_session as runpod_session  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v5"
DEFAULT_SUITE_NAME = "frozen-viable-baseline-slice-suite"
PROFILE_MODE_DETECTOR_BREADTH_SCREEN = run_detector_breadth_batch.PROFILE_MODE_DETECTOR_BREADTH_SCREEN
BEST_THIN_REFERENCE_PROFILE = run_detector_breadth_batch.BEST_THIN_REFERENCE_PROFILE
BASELINE_DETECTOR_MODEL_PATH = "yolov10n.pt"
BASELINE_DETECTOR_LABEL = "yolov10n.pt_baseline_full_detector"
AUXILIARY_BALL_MODEL_PROFILE = "ball_probe_only_v1"
LOW_CONF_AUXILIARY_BALL_MODEL_PROFILE = "ball_probe_only_v1_low_conf_001"
NEXT_LEVER_PROMOTE_CANDIDATE = "promote_touchline_detector_candidate"
NEXT_LEVER_PROMOTE_CANDIDATE_PLUS_THIN = "promote_touchline_detector_candidate_plus_best_thin_candidate"
NEXT_LEVER_EVALUATE = "evaluate_touchline_detector_candidate"


def _safe_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default




def _candidate_version(candidate_name: object) -> int:
    raw_name = str(candidate_name or "").strip()
    marker = "_v"
    if marker not in raw_name:
        return 0
    suffix = raw_name.rsplit(marker, 1)[-1]
    digits: list[str] = []
    for char in suffix:
        if not char.isdigit():
            break
        digits.append(char)
    return int("".join(digits)) if digits else 0


def _candidate_detector_label(candidate_name: str) -> str:
    return f"{candidate_name}_probe_assist"


def _evaluation_batch_name(candidate_name: str) -> str:
    version = _candidate_version(candidate_name)
    if version > 0:
        return f"touchline_detector_candidate_evaluation_v{version}"
    return "touchline_detector_candidate_evaluation"


def _resolve_active_candidate_name(storage_root: Path) -> str:
    candidates_root = storage_root / "trained_detector_candidates"
    ranked_candidates: list[tuple[int, str]] = []
    if candidates_root.exists():
        for child in candidates_root.iterdir():
            if not child.is_dir():
                continue
            training_run_summary_path = child / "training_run_summary.json"
            if not training_run_summary_path.exists():
                continue
            try:
                training_run_summary = _load_json(training_run_summary_path)
            except Exception:
                continue
            quality_gate_summary_path = child / "training_quality_gate_v1" / "quality_gate_summary.json"
            try:
                quality_gate_summary = (
                    _load_json(quality_gate_summary_path) if quality_gate_summary_path.exists() else {}
                )
            except Exception:
                quality_gate_summary = {}
            if not bool(training_run_summary.get("trainingCompleted")):
                continue
            if not bool(training_run_summary.get("weightsReady")):
                continue
            if not bool(training_run_summary.get("evaluationContractReady")):
                continue
            if not bool(training_run_summary.get("readyForDetectorEvaluation")):
                continue
            if quality_gate_summary and not bool(quality_gate_summary.get("trainingQualityGatePassed")):
                continue
            if not quality_gate_summary and training_run_summary.get("trainingQualityGatePassed") is False:
                continue
            ranked_candidates.append((_candidate_version(child.name), child.name))
    ranked_candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    if ranked_candidates:
        return ranked_candidates[0][1]
    return DEFAULT_CANDIDATE_NAME


def _artifact_paths(storage_root: Path, candidate_name: str) -> dict[str, Path]:
    suite_root = storage_root / "benchmark_suites" / DEFAULT_SUITE_NAME
    candidate_root = storage_root / "trained_detector_candidates" / candidate_name
    evaluation_root = candidate_root / "evaluation_v1"
    return {
        "suiteRoot": suite_root,
        "suiteSummaryPath": suite_root / "suite_summary.json",
        "activeLaneSnapshotPath": suite_root / "active_lane_snapshot.json",
        "candidateRoot": candidate_root,
        "trainingRunSummaryPath": candidate_root / "training_run_summary.json",
        "trainingConfigPath": candidate_root / "training_config.json",
        "evaluationContractPath": candidate_root / "evaluation_contract.json",
        "batchOutcomePath": candidate_root / "batch_outcome_analysis.json",
        "evaluationRoot": evaluation_root,
    }


def _detector_entries(
    candidate_best_weights_path: str,
    *,
    candidate_name: str,
    auxiliary_ball_model_profile: str = AUXILIARY_BALL_MODEL_PROFILE,
) -> tuple[dict[str, str], ...]:
    return (
        {
            "label": _candidate_detector_label(candidate_name),
            "primary_model_path": BASELINE_DETECTOR_MODEL_PATH,
            "auxiliary_ball_model_path": candidate_best_weights_path,
            "auxiliary_ball_model_profile": auxiliary_ball_model_profile,
        },
        {
            "label": BASELINE_DETECTOR_LABEL,
            "primary_model_path": BASELINE_DETECTOR_MODEL_PATH,
        },
    )


def _validate_evaluation_inputs(
    *,
    training_run_summary: dict[str, object],
    training_config: dict[str, object],
    evaluation_contract: dict[str, object],
) -> Path:
    if not bool(training_run_summary.get("trainingCompleted")):
        raise ValueError("Detector candidate training is not marked complete")
    if not bool(training_run_summary.get("weightsReady")):
        raise ValueError("Detector candidate weights are not marked ready")
    if not bool(training_run_summary.get("evaluationContractReady")):
        raise ValueError("Detector candidate evaluation contract is not marked ready")
    if not bool(training_run_summary.get("readyForDetectorEvaluation")):
        raise ValueError("Detector candidate is not marked readyForDetectorEvaluation")
    if not bool(evaluation_contract.get("candidateReadyForEvaluation")):
        raise ValueError("Evaluation contract does not mark the candidate ready for evaluation")
    best_weights_path = Path(str(training_run_summary.get("bestWeightsPath") or "")).expanduser()
    if not best_weights_path.exists():
        raise FileNotFoundError(f"Detector candidate best weights not found at {best_weights_path}")
    if not isinstance(training_config.get("trainingRecipe"), dict):
        raise ValueError("Training config is missing trainingRecipe")
    return best_weights_path


def _screen_cell_sort_key(cell: dict[str, object]) -> tuple[object, ...]:
    return (
        0 if bool(cell.get("screenSucceeded")) else 1,
        0 if bool(cell.get("viable")) else 1,
        -_safe_float(cell.get("selectedScore"), 0.0),
        _safe_float(cell.get("selectedEdgeFrameShare"), 1.0),
        -_safe_float(cell.get("dominantAnchorShare"), 0.0),
        _safe_int(cell.get("inputOrder"), 0),
        str(cell.get("detectorLabel") or ""),
    )


def _screen_result_cell(
    *,
    detector_entry: dict[str, str],
    payload: dict[str, object],
) -> dict[str, object]:
    profiles = payload.get("profiles")
    recommended_profile_name = str(payload.get("recommendedProfile") or "no_viable_profile")
    recommended_profile = None
    if isinstance(profiles, list):
        recommended_profile = next(
            (
                profile
                for profile in profiles
                if isinstance(profile, dict) and str(profile.get("name") or "") == recommended_profile_name
            ),
            None,
        )
    recommended_profile = recommended_profile if isinstance(recommended_profile, dict) else {}
    candidate_summary = recommended_profile.get("candidateSummary")
    selected_summary = recommended_profile.get("selectedSummary")
    candidate_summary = candidate_summary if isinstance(candidate_summary, dict) else {}
    selected_summary = selected_summary if isinstance(selected_summary, dict) else {}
    requested_primary_model_path = str(detector_entry["primary_model_path"])
    requested_auxiliary_ball_model_path = detector_entry.get("auxiliary_ball_model_path")
    return {
        "detectorLabel": str(detector_entry["label"]),
        "detectorModelPath": requested_primary_model_path,
        "detectorModelName": Path(requested_primary_model_path).name,
        "primaryDetectorModelPath": requested_primary_model_path,
        "primaryDetectorModelName": Path(requested_primary_model_path).name,
        "auxiliaryBallModelPath": (
            str(payload.get("auxiliaryBallModelPath"))
            if payload.get("auxiliaryBallModelPath") is not None
            else str(requested_auxiliary_ball_model_path)
            if requested_auxiliary_ball_model_path is not None
            else None
        ),
        "auxiliaryBallModelName": (
            str(payload.get("auxiliaryBallModelName"))
            if payload.get("auxiliaryBallModelName") is not None
            else Path(str(requested_auxiliary_ball_model_path)).name
            if requested_auxiliary_ball_model_path is not None
            else None
        ),
        "auxiliaryBallModelProfile": detector_entry.get("auxiliary_ball_model_profile"),
        "remoteDetectorModelPath": payload.get("primaryDetectorModelPath") or payload.get("detectorModelPath"),
        "remoteDetectorModelName": payload.get("primaryDetectorModelName") or payload.get("detectorModelName"),
        "remotePrimaryDetectorModelPath": payload.get("primaryDetectorModelPath") or payload.get("detectorModelPath"),
        "remotePrimaryDetectorModelName": payload.get("primaryDetectorModelName") or payload.get("detectorModelName"),
        "remoteAuxiliaryBallModelPath": payload.get("auxiliaryBallModelPath"),
        "remoteAuxiliaryBallModelName": payload.get("auxiliaryBallModelName"),
        "profileMode": str(payload.get("profileMode") or PROFILE_MODE_DETECTOR_BREADTH_SCREEN),
        "recommendedProfileName": recommended_profile_name,
        "selectedScore": _safe_float(recommended_profile.get("selectedScore"), 0.0),
        "viable": bool(recommended_profile.get("viable")),
        "selectedFrames": _safe_int(selected_summary.get("frames"), 0),
        "selectedEdgeFrameShare": _safe_float(selected_summary.get("edgeFrameShare"), 1.0),
        "dominantAnchorCoord": candidate_summary.get("dominantAnchorCoord"),
        "dominantAnchorShare": _safe_float(
            recommended_profile.get("dominantAnchorShare", candidate_summary.get("dominantAnchorShare")),
            0.0,
        ),
        "meanSourceCenterY": _safe_float(
            recommended_profile.get("meanSourceCenterY", candidate_summary.get("meanSourceCenterY")),
            0.0,
        ),
        "candidateSummary": candidate_summary,
        "selectedSummary": selected_summary,
        "runtimeStamp": (
            dict(payload.get("runtimeStamp")) if isinstance(payload.get("runtimeStamp"), dict) else None
        ),
        "screenSucceeded": True,
        "screenError": None,
    }


def _screen_failure_cell(*, detector_entry: dict[str, str], error: str) -> dict[str, object]:
    requested_primary_model_path = str(detector_entry["primary_model_path"])
    requested_auxiliary_ball_model_path = detector_entry.get("auxiliary_ball_model_path")
    return {
        "detectorLabel": str(detector_entry["label"]),
        "detectorModelPath": requested_primary_model_path,
        "detectorModelName": Path(requested_primary_model_path).name,
        "primaryDetectorModelPath": requested_primary_model_path,
        "primaryDetectorModelName": Path(requested_primary_model_path).name,
        "auxiliaryBallModelPath": (
            str(requested_auxiliary_ball_model_path) if requested_auxiliary_ball_model_path is not None else None
        ),
        "auxiliaryBallModelName": (
            Path(str(requested_auxiliary_ball_model_path)).name
            if requested_auxiliary_ball_model_path is not None
            else None
        ),
        "auxiliaryBallModelProfile": detector_entry.get("auxiliary_ball_model_profile"),
        "remoteDetectorModelPath": None,
        "remoteDetectorModelName": None,
        "remotePrimaryDetectorModelPath": None,
        "remotePrimaryDetectorModelName": None,
        "remoteAuxiliaryBallModelPath": None,
        "remoteAuxiliaryBallModelName": None,
        "profileMode": PROFILE_MODE_DETECTOR_BREADTH_SCREEN,
        "recommendedProfileName": "screen_failed",
        "selectedScore": 0.0,
        "viable": False,
        "selectedFrames": 0,
        "selectedEdgeFrameShare": 1.0,
        "dominantAnchorCoord": None,
        "dominantAnchorShare": 0.0,
        "meanSourceCenterY": 0.0,
        "candidateSummary": {},
        "selectedSummary": {},
        "runtimeStamp": None,
        "screenSucceeded": False,
        "screenError": error,
    }


def _finalize_screen_payload(
    *,
    clip_path: Path,
    detector_entries: tuple[dict[str, str], ...],
    cells: list[dict[str, object]],
) -> dict[str, object]:
    ranked_cells = sorted(cells, key=_screen_cell_sort_key)
    winning_cell = next((cell for cell in ranked_cells if bool(cell.get("screenSucceeded"))), None)
    winning_label = str(winning_cell.get("detectorLabel") or "") if isinstance(winning_cell, dict) else None
    winning_primary_model_path = (
        str(winning_cell.get("primaryDetectorModelPath") or "") if isinstance(winning_cell, dict) else None
    )
    winning_auxiliary_ball_model_path = (
        str(winning_cell.get("auxiliaryBallModelPath") or "") if isinstance(winning_cell, dict) else None
    )
    for rank, cell in enumerate(ranked_cells, start=1):
        cell["screenRank"] = rank
        cell["screenExecutionMode"] = run_detector_breadth_batch.SCREEN_EXECUTION_MODE_REMOTE_GPU
        cell["qualifiesForRemoteProof"] = bool(winning_label) and str(cell.get("detectorLabel") or "") == winning_label
    return {
        "generatedAt": _utc_now_iso(),
        "videoPath": str(clip_path),
        "screenExecutionMode": run_detector_breadth_batch.SCREEN_EXECUTION_MODE_REMOTE_GPU,
        "detectorEntries": [dict(entry) for entry in detector_entries],
        "screenWinningDetectorLabel": winning_label,
        "screenWinningDetectorModelPath": winning_primary_model_path,
        "screenWinningPrimaryDetectorModelPath": winning_primary_model_path,
        "screenWinningAuxiliaryBallModelPath": winning_auxiliary_ball_model_path,
        "cells": ranked_cells,
    }


def _run_remote_trimmed_ball_recovery_matrix(
    *,
    session: dict[str, object],
    detector_entry: dict[str, str],
) -> dict[str, object]:
    ssh_command = list(session["sshCommand"])
    remote_repo_root = str(session["remoteRepoRoot"])
    remote_clip_path = str(session["remoteClipPath"])
    staged_primary_model = runpod_session.stage_model_on_pod(
        ssh_command=ssh_command,
        model_path=str(detector_entry["primary_model_path"]),
        remote_model_path=runpod_session.resolve_remote_model_path(str(detector_entry["primary_model_path"])),
        remote_repo_root=remote_repo_root,
    )
    staged_auxiliary_ball_model = None
    auxiliary_ball_model_path = detector_entry.get("auxiliary_ball_model_path")
    if auxiliary_ball_model_path:
        staged_auxiliary_ball_model = runpod_session.stage_model_on_pod(
            ssh_command=ssh_command,
            model_path=str(auxiliary_ball_model_path),
            remote_model_path=runpod_session.resolve_remote_model_path(str(auxiliary_ball_model_path)),
            remote_repo_root=remote_repo_root,
        )
    command = [
        f"{runpod_session.DEFAULT_POD_VENV_PATH}/bin/python",
        "backend/scripts/run_trimmed_ball_recovery_matrix.py",
        "--video-path",
        remote_clip_path,
        "--name",
        str(detector_entry["label"]),
        "--primary-model-path",
        str(staged_primary_model["detectorModelPath"]),
        "--model-path",
        str(staged_primary_model["detectorModelPath"]),
        "--profile-mode",
        PROFILE_MODE_DETECTOR_BREADTH_SCREEN,
    ]
    if staged_auxiliary_ball_model is not None:
        command.extend(
            [
                "--auxiliary-ball-model-path",
                str(staged_auxiliary_ball_model["detectorModelPath"]),
            ]
        )
        auxiliary_ball_model_profile = detector_entry.get("auxiliary_ball_model_profile")
        if auxiliary_ball_model_profile:
            command.extend(
                [
                    "--auxiliary-ball-model-profile",
                    str(auxiliary_ball_model_profile),
                ]
            )
    remote_command = f"""
cd {shlex.quote(remote_repo_root)}
source {shlex.quote(runpod_session.DEFAULT_POD_VENV_PATH)}/bin/activate
export PYTHONPATH={shlex.quote(remote_repo_root)}
export QT_QPA_PLATFORM=offscreen
export YOLO_CONFIG_DIR={shlex.quote(runpod_session.DEFAULT_POD_YOLO_CONFIG_DIR)}
{shlex.join(command)}
"""
    payload = runpod_session.run_json_command_over_ssh(
        ssh_command,
        f"bash -lc {shlex.quote(remote_command)}",
    )
    payload["detectorModelPath"] = staged_primary_model["detectorModelPath"]
    payload["detectorModelName"] = staged_primary_model["detectorModelName"]
    payload["primaryDetectorModelPath"] = staged_primary_model["detectorModelPath"]
    payload["primaryDetectorModelName"] = staged_primary_model["detectorModelName"]
    payload["auxiliaryBallModelPath"] = (
        staged_auxiliary_ball_model["detectorModelPath"] if staged_auxiliary_ball_model is not None else None
    )
    payload["auxiliaryBallModelName"] = (
        staged_auxiliary_ball_model["detectorModelName"] if staged_auxiliary_ball_model is not None else None
    )
    payload["auxiliaryBallModelProfile"] = detector_entry.get("auxiliary_ball_model_profile")
    return payload


def run_remote_detector_candidate_screen(
    *,
    session: dict[str, object],
    clip_path: Path,
    detector_entries: tuple[dict[str, str], ...],
) -> dict[str, object]:
    runpod_session.require_retired_runpod_disabled()


def _proof_name(detector_label: str, proof_kind: str) -> str:
    label = detector_label.replace(".", "-").replace("/", "-").replace("_", "-")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{label}-{proof_kind}-{timestamp}"


def _proof_result_from_payload(
    *,
    payload: dict[str, object],
    detector_label: str,
    primary_detector_model_path: str,
    auxiliary_ball_model_path: str | None,
    auxiliary_ball_model_profile: str | None,
    proof_kind: str,
) -> dict[str, object]:
    comparison = payload.get("comparison")
    summary = payload.get("summary")
    comparison = comparison if isinstance(comparison, dict) else {}
    summary = summary if isinstance(summary, dict) else {}
    edge_share_repair_profile = payload.get("edgeShareRepairProfile")
    return {
        "proofKind": proof_kind,
        "detectorLabel": detector_label,
        "detectorModelPath": primary_detector_model_path,
        "detectorModelName": Path(primary_detector_model_path).name,
        "primaryDetectorModelPath": primary_detector_model_path,
        "primaryDetectorModelName": Path(primary_detector_model_path).name,
        "auxiliaryBallModelPath": auxiliary_ball_model_path,
        "auxiliaryBallModelName": (
            Path(str(auxiliary_ball_model_path)).name if auxiliary_ball_model_path is not None else None
        ),
        "auxiliaryBallModelProfile": auxiliary_ball_model_profile,
        "edgeShareRepairProfile": edge_share_repair_profile,
        "mechanismSuccess": bool(comparison.get("mechanismSuccess")),
        "productSuccess": bool(comparison.get("productSuccess")),
        "productBeatsPlateau": bool(comparison.get("productBeatsPlateau")),
        "mechanismBeatsPlateau": bool(comparison.get("mechanismBeatsPlateau")),
        "beatsPlateau": bool(comparison.get("beatsPlateau")),
        "acceptedBallFrames": _safe_int(summary.get("acceptedBallFrames"), 0),
        "controlledPossessionFrames": _safe_int(summary.get("controlledPossessionFrames"), 0),
        "ballTrackViable": bool(summary.get("ballTrackViable")),
        "ballTrackEdgeFrameShare": _safe_float(summary.get("ballTrackEdgeFrameShare"), 1.0),
        "summaryPath": str(payload.get("summaryPath")) if payload.get("summaryPath") is not None else None,
        "selectedClusterDeltaPath": (
            str(payload.get("selectedClusterDeltaPath"))
            if payload.get("selectedClusterDeltaPath") is not None
            else None
        ),
        "ballTruthLayersPath": (
            str(payload.get("ballTruthLayersPath")) if payload.get("ballTruthLayersPath") is not None else None
        ),
    }


def _failed_proof_result(
    *,
    detector_label: str,
    primary_detector_model_path: str,
    auxiliary_ball_model_path: str | None,
    auxiliary_ball_model_profile: str | None,
    proof_kind: str,
    error: Exception,
    edge_share_repair_profile: str | None = None,
) -> dict[str, object]:
    return {
        "proofKind": proof_kind,
        "detectorLabel": detector_label,
        "detectorModelPath": primary_detector_model_path,
        "detectorModelName": Path(primary_detector_model_path).name,
        "primaryDetectorModelPath": primary_detector_model_path,
        "primaryDetectorModelName": Path(primary_detector_model_path).name,
        "auxiliaryBallModelPath": auxiliary_ball_model_path,
        "auxiliaryBallModelName": (
            Path(str(auxiliary_ball_model_path)).name if auxiliary_ball_model_path is not None else None
        ),
        "auxiliaryBallModelProfile": auxiliary_ball_model_profile,
        "edgeShareRepairProfile": edge_share_repair_profile,
        "proofFailed": True,
        "proofError": str(error),
        "mechanismSuccess": False,
        "productSuccess": False,
        "productBeatsPlateau": False,
        "mechanismBeatsPlateau": False,
        "beatsPlateau": False,
        "acceptedBallFrames": 0,
        "controlledPossessionFrames": 0,
        "ballTrackViable": False,
        "ballTrackEdgeFrameShare": 1.0,
        "summaryPath": None,
        "selectedClusterDeltaPath": None,
        "ballTruthLayersPath": None,
    }


def _attempt_remote_proof(
    *,
    session: dict[str, object],
    storage_root: Path,
    proof_name: str,
    detector_label: str,
    primary_detector_model_path: str,
    auxiliary_ball_model_path: str | None = None,
    auxiliary_ball_model_profile: str | None = None,
    proof_kind: str,
    edge_share_repair_profile: str | None = None,
) -> dict[str, object]:
    runpod_session.require_retired_runpod_disabled()


def _product_score(result: dict[str, object] | None) -> tuple[object, ...]:
    if not isinstance(result, dict):
        return (0, 0, 0, 0, -1.0)
    return (
        1 if bool(result.get("productBeatsPlateau")) else 0,
        1 if bool(result.get("ballTrackViable")) else 0,
        _safe_int(result.get("acceptedBallFrames"), 0),
        _safe_int(result.get("controlledPossessionFrames"), 0),
        -_safe_float(result.get("ballTrackEdgeFrameShare"), 1.0),
    )


def _candidate_beats_control(
    candidate_result: dict[str, object] | None,
    control_result: dict[str, object] | None,
) -> bool:
    if not isinstance(candidate_result, dict):
        return False
    if not isinstance(control_result, dict):
        return bool(candidate_result.get("productBeatsPlateau"))
    return _product_score(candidate_result) > _product_score(control_result)


def _determine_next_lever(
    *,
    candidate_baseline_result: dict[str, object] | None,
    candidate_compound_result: dict[str, object] | None,
    baseline_control_result: dict[str, object] | None,
) -> str:
    baseline_can_promote = bool(candidate_baseline_result and candidate_baseline_result.get("productBeatsPlateau")) and _candidate_beats_control(
        candidate_baseline_result,
        baseline_control_result,
    )
    if baseline_can_promote:
        return NEXT_LEVER_PROMOTE_CANDIDATE
    compound_can_promote = bool(candidate_compound_result and candidate_compound_result.get("productBeatsPlateau")) and _candidate_beats_control(
        candidate_compound_result,
        baseline_control_result,
    )
    if compound_can_promote:
        return NEXT_LEVER_PROMOTE_CANDIDATE_PLUS_THIN
    return NEXT_LEVER_EVALUATE


def _evaluation_primary_blocker(
    *,
    screen_completed: bool,
    candidate_baseline_result: dict[str, object] | None,
    candidate_compound_result: dict[str, object] | None,
    baseline_control_result: dict[str, object] | None,
    next_lever: str,
) -> str | None:
    if next_lever in {NEXT_LEVER_PROMOTE_CANDIDATE, NEXT_LEVER_PROMOTE_CANDIDATE_PLUS_THIN}:
        return None
    if not screen_completed:
        return "candidate_screen_failed"
    if not isinstance(candidate_baseline_result, dict):
        return "candidate_baseline_proof_missing"
    if bool(candidate_baseline_result.get("proofFailed")):
        return "candidate_baseline_proof_failed"
    if not bool(candidate_baseline_result.get("productBeatsPlateau")):
        return "candidate_baseline_did_not_beat_plateau"
    if isinstance(baseline_control_result, dict) and bool(baseline_control_result.get("proofFailed")):
        return "baseline_control_proof_failed"
    if isinstance(baseline_control_result, dict) and not _candidate_beats_control(candidate_baseline_result, baseline_control_result):
        if not isinstance(candidate_compound_result, dict):
            return "candidate_not_better_than_same_batch_baseline_control"
        if bool(candidate_compound_result.get("proofFailed")):
            return "candidate_compound_thin_proof_failed"
        if not _candidate_beats_control(candidate_compound_result, baseline_control_result):
            return "candidate_not_better_than_same_batch_baseline_control"
    if isinstance(candidate_compound_result, dict) and not bool(candidate_compound_result.get("productBeatsPlateau")):
        return "candidate_compound_thin_did_not_beat_plateau"
    return "evaluation_did_not_find_promotable_candidate"




def _brainstorm_fixes(
    *,
    candidate_name: str,
    screen_completed: bool,
    candidate_baseline_result: dict[str, object] | None,
    candidate_compound_result: dict[str, object] | None,
    baseline_control_result: dict[str, object] | None,
    primary_blocker: str | None,
    execution_blockers_resolved: bool,
    evaluation_reached_product_comparison: bool,
) -> list[str]:
    if primary_blocker is None:
        return []
    fixes: list[str] = []
    if not execution_blockers_resolved:
        fixes.append(
            "Keep the evaluation lane active and fix the remaining execution blocker before interpreting product performance."
        )
    if not screen_completed:
        fixes.append(
            "Inspect the remote detector screen stderr and rerun the bounded screen after fixing the remote model or launch failure."
        )
    if primary_blocker == "candidate_baseline_proof_failed":
        proof_error = ""
        if isinstance(candidate_baseline_result, dict):
            proof_error = str(candidate_baseline_result.get("proofError") or "").strip()
        if proof_error:
            fixes.append(
                f"Fix the candidate baseline proof blocker and rerun bounded evaluation. Observed failure: {proof_error}"
            )
        else:
            fixes.append(
                f"Fix the candidate baseline proof failure and rerun bounded evaluation on the same {candidate_name} weights."
            )
    if primary_blocker == "candidate_baseline_did_not_beat_plateau":
        fixes.append(
            f"Inspect the {candidate_name} baseline proof deltas against 101 / 98 / false / 0.812 and focus the next fix batch on the specific failing-source weakness."
        )
    if primary_blocker == "candidate_not_better_than_same_batch_baseline_control":
        fixes.append(
            f"Compare the {candidate_name} proof directly against the same-batch yolov10n.pt control and target only the gap that prevented a same-batch win."
        )
    if primary_blocker == "candidate_compound_thin_proof_failed":
        fixes.append(
            "Debug the v2 + 2_min10 proof path before trying any broader experiment so the compound lane can be evaluated truthfully."
        )
    if primary_blocker == "candidate_compound_thin_did_not_beat_plateau":
        fixes.append(
            "Keep the evaluation lane active and inspect whether the remaining blocker is detector quality or thin-lane interaction before planning another batch."
        )
    if isinstance(candidate_compound_result, dict) and bool(candidate_compound_result.get("proofFailed")):
        fixes.append("Preserve the current v2 artifact and rerun only after the compound proof path captures actionable remote stderr.")
    if isinstance(baseline_control_result, dict) and bool(baseline_control_result.get("proofFailed")):
        fixes.append("Repair the same-batch baseline control proof path so future promotion decisions are based on a truthful control comparison.")
    if execution_blockers_resolved and evaluation_reached_product_comparison:
        fixes.append(
            "Treat this as a truthful product loss and focus the next fix batch on model or data quality instead of runtime plumbing."
        )
    if execution_blockers_resolved and primary_blocker == "candidate_baseline_did_not_beat_plateau":
        fixes.append(
            f"Inspect the auxiliary ball-probe contribution frame by frame to see whether {candidate_name} adds useful recovered ball rows over the baseline."
        )
    if not fixes:
        fixes.append("Inspect the generated evaluation artifacts, identify the concrete blocker, and rerun the same bounded evaluation without opening a new research lane.")
    seen: set[str] = set()
    deduped: list[str] = []
    for fix in fixes:
        if fix in seen:
            continue
        seen.add(fix)
        deduped.append(fix)
    return deduped


def _build_batch_outcome_analysis(
    *,
    candidate_name: str,
    evaluation_batch_name: str,
    screen_completed: bool,
    candidate_baseline_result: dict[str, object] | None,
    baseline_control_result: dict[str, object] | None,
    candidate_compound_result: dict[str, object] | None,
    ready_for_promotion: bool,
    next_lever: str,
    primary_blocker: str | None,
    execution_blockers_resolved: bool,
    evaluation_reached_product_comparison: bool,
) -> dict[str, object]:
    goal_achieved = ready_for_promotion
    roadmap_advance_allowed = goal_achieved
    brainstorm_fixes = _brainstorm_fixes(
        candidate_name=candidate_name,
        screen_completed=screen_completed,
        candidate_baseline_result=candidate_baseline_result,
        candidate_compound_result=candidate_compound_result,
        baseline_control_result=baseline_control_result,
        primary_blocker=primary_blocker,
        execution_blockers_resolved=execution_blockers_resolved,
        evaluation_reached_product_comparison=evaluation_reached_product_comparison,
    )
    if goal_achieved:
        english_summary = (
            f"{evaluation_batch_name} achieved its goal: the {candidate_name} candidate produced a promotable evaluation result."
        )
        english_decision = (
            "The roadmap may advance because the candidate earned promotion under the bounded same-batch evaluation rules."
        )
    else:
        english_summary = (
            f"{evaluation_batch_name} did not achieve its goal: the {candidate_name} candidate is still not promotable from the bounded evaluation bundle."
        )
        english_decision = (
            "The roadmap may not advance. Stay on the evaluation lane, fix the blocker, and rerun the same bounded evaluation."
        )
    return {
        "batchGoal": f"Produce a promotable bounded evaluation result for {candidate_name}.",
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": roadmap_advance_allowed,
        "englishSummary": english_summary,
        "englishDecision": english_decision,
        "primaryBlocker": primary_blocker,
        "screenCompleted": screen_completed,
        "candidateBaselineProofRan": isinstance(candidate_baseline_result, dict),
        "candidateBaselineProductBeatsPlateau": bool(
            candidate_baseline_result and candidate_baseline_result.get("productBeatsPlateau")
        ),
        "baselineControlProofRan": isinstance(baseline_control_result, dict),
        "candidateCompoundThinProofRan": isinstance(candidate_compound_result, dict),
        "executionBlockersResolved": execution_blockers_resolved,
        "evaluationReachedProductComparison": evaluation_reached_product_comparison,
        "readyForPromotion": ready_for_promotion,
        "nextRecommendedNextLever": next_lever,
        "brainstormFixes": [] if goal_achieved else brainstorm_fixes,
    }


def _write_batch_outcome_markdown(path: Path, payload: dict[str, object]) -> None:
    brainstorm_fixes = list(payload.get("brainstormFixes") or [])
    lines = [
        "# Batch Outcome Analysis",
        "",
        f"- Batch goal: {payload.get('batchGoal')}",
        f"- Goal achieved: {bool(payload.get('goalAchieved'))}",
        f"- Roadmap advance allowed: {bool(payload.get('roadmapAdvanceAllowed'))}",
        f"- Primary blocker: {payload.get('primaryBlocker')}",
        f"- Execution blockers resolved: {bool(payload.get('executionBlockersResolved'))}",
        f"- Evaluation reached product comparison: {bool(payload.get('evaluationReachedProductComparison'))}",
        f"- Next recommended next lever: {payload.get('nextRecommendedNextLever')}",
        "",
        "## English Summary",
        "",
        str(payload.get("englishSummary") or ""),
        "",
        "## English Decision",
        "",
        str(payload.get("englishDecision") or ""),
    ]
    if brainstorm_fixes:
        lines.extend(
            [
                "",
                "## Brainstorm Fixes",
                "",
            ]
        )
        lines.extend([f"- {fix}" for fix in brainstorm_fixes])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _run_remote_proof_on_session(
    *,
    session: dict[str, object],
    storage_root: Path,
    proof_name: str,
    model_path: str,
    primary_model_path: str | None = None,
    auxiliary_ball_model_path: str | None = None,
    auxiliary_ball_model_profile: str | None = None,
    edge_share_repair_profile: str | None = None,
) -> dict[str, object]:
    return run_detector_breadth_batch._run_remote_proof_on_session(
        session=session,
        storage_root=storage_root,
        proof_name=proof_name,
        model_path=model_path,
        primary_model_path=primary_model_path,
        auxiliary_ball_model_path=auxiliary_ball_model_path,
        auxiliary_ball_model_profile=auxiliary_ball_model_profile,
        edge_share_repair_profile=edge_share_repair_profile,
    )


def run_touchline_detector_candidate_evaluation(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    manifest_path: Path = run_source_robustness_batch.DEFAULT_MANIFEST_PATH,
    canonical_proof_summary_path: Path = run_source_robustness_batch.DEFAULT_CANONICAL_PROOF_SUMMARY_PATH,
    candidate_name: str | None = None,
    auxiliary_ball_model_profile: str = AUXILIARY_BALL_MODEL_PROFILE,
) -> dict[str, object]:
    runpod_session.require_retired_runpod_disabled()


def main() -> None:
    runpod_session.require_retired_runpod_disabled()


if __name__ == "__main__":
    main()
