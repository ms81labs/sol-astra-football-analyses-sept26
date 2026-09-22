"""Historical detector recipe, retired with its RunPod execution path."""

from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso

if __name__ == "__main__":
    from backend.scripts.runpod_session import require_retired_runpod_disabled

    require_retired_runpod_disabled()

from datetime import datetime, timezone
import json
from pathlib import Path
import shlex

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
import backend.scripts.run_source_robustness_batch as run_source_robustness_batch  # noqa: E402
import backend.scripts.runpod_session as runpod_session  # noqa: E402

DETECTOR_BREADTH_MODELS = ("yolov10n.pt", "yolo11s.pt", "yolov8n.pt", "yolov8s.pt")
BEST_THIN_REFERENCE_PROFILE = "source_robustness_shadow_edge_run_keep_every_2_min10"
PROFILE_MODE_DETECTOR_BREADTH_SCREEN = "detector_breadth_screen"
SCREEN_EXECUTION_MODE_LOCAL_CPU = "local_cpu"
SCREEN_EXECUTION_MODE_REMOTE_GPU = "remote_gpu"
FAILING_SOURCE_REMOTE_REFERENCE = {
    "acceptedBallFrames": 101,
    "controlledPossessionFrames": 98,
    "ballTrackViable": False,
    "ballTrackEdgeFrameShare": 0.812,
}



def _safe_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _screen_result_cell(
    *,
    detector_model_path: str,
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
    return {
        "detectorModelPath": detector_model_path,
        "detectorModelName": Path(detector_model_path).name,
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
        "screenSucceeded": True,
        "screenError": None,
    }


def _screen_failure_cell(*, detector_model_path: str, error: str) -> dict[str, object]:
    return {
        "detectorModelPath": detector_model_path,
        "detectorModelName": Path(detector_model_path).name,
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
        "screenSucceeded": False,
        "screenError": error,
    }


def _screen_cell_sort_key(cell: dict[str, object]) -> tuple[object, ...]:
    return (
        0 if bool(cell.get("screenSucceeded")) else 1,
        0 if bool(cell.get("viable")) else 1,
        -_safe_float(cell.get("selectedScore"), 0.0),
        _safe_float(cell.get("selectedEdgeFrameShare"), 1.0),
        -_safe_float(cell.get("dominantAnchorShare"), 0.0),
        _safe_int(cell.get("inputOrder"), 0),
    )


def _finalize_screen_payload(
    *,
    video_path: Path,
    detector_models: tuple[str, ...],
    cells: list[dict[str, object]],
    screen_execution_mode: str,
) -> dict[str, object]:
    ranked_cells = sorted(cells, key=_screen_cell_sort_key)
    winning_detector_model_path: str | None = None
    winning_profile_name: str | None = None
    winning_cell = next((cell for cell in ranked_cells if bool(cell.get("screenSucceeded"))), None)
    if isinstance(winning_cell, dict):
        winning_detector_model_path = str(winning_cell.get("detectorModelPath") or "") or None
        winning_profile_name = str(winning_cell.get("recommendedProfileName") or "") or None
    for rank, cell in enumerate(ranked_cells, start=1):
        cell["screenRank"] = rank
        cell["screenExecutionMode"] = screen_execution_mode
        cell["qualifiesForRemoteProof"] = (
            bool(winning_detector_model_path) and str(cell.get("detectorModelPath") or "") == winning_detector_model_path
        )
    return {
        "generatedAt": utc_now_iso(),
        "videoPath": str(video_path),
        "screenExecutionMode": screen_execution_mode,
        "detectorModels": list(detector_models),
        "screenWinningDetectorModelPath": winning_detector_model_path,
        "screenWinningRecommendedProfileName": winning_profile_name,
        "cells": ranked_cells,
    }


def run_local_detector_breadth_screen(
    *,
    video_path: Path,
    detector_models: tuple[str, ...] = DETECTOR_BREADTH_MODELS,
) -> dict[str, object]:
    runpod_session.require_retired_runpod_disabled()


def _run_remote_trimmed_ball_recovery_matrix(
    *,
    session: dict[str, object],
    detector_model_path: str,
) -> dict[str, object]:
    ssh_command = list(session["sshCommand"])
    remote_repo_root = str(session["remoteRepoRoot"])
    remote_clip_path = str(session["remoteClipPath"])
    remote_model_path = runpod_session.resolve_remote_model_path(detector_model_path)
    staged_model = runpod_session.stage_model_on_pod(
        ssh_command=ssh_command,
        model_path=detector_model_path,
        remote_model_path=remote_model_path,
        remote_repo_root=remote_repo_root,
    )
    command = [
        "python",
        "backend/scripts/run_trimmed_ball_recovery_matrix.py",
        "--video-path",
        remote_clip_path,
        "--model-path",
        str(staged_model["detectorModelPath"]),
        "--name",
        f"{Path(remote_clip_path).stem}-{Path(detector_model_path).stem}",
        "--profile-mode",
        PROFILE_MODE_DETECTOR_BREADTH_SCREEN,
    ]
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
    payload["detectorModelPath"] = staged_model["detectorModelPath"]
    payload["detectorModelName"] = staged_model["detectorModelName"]
    return payload


def run_remote_detector_breadth_screen(
    *,
    session: dict[str, object],
    clip_path: Path,
    detector_models: tuple[str, ...] = DETECTOR_BREADTH_MODELS,
) -> dict[str, object]:
    runpod_session.require_retired_runpod_disabled()


def _first_existing_failing_source_video_path(manifest_path: Path, *, failing_source_clip_id: str) -> Path | None:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return run_source_robustness_batch._first_existing_failing_source_video_path(  # type: ignore[attr-defined]
        manifest,
        failing_source_clip_id=failing_source_clip_id,
    )


def _proof_name(detector_model_path: str, proof_kind: str) -> str:
    stem = Path(detector_model_path).stem.replace(".", "-")
    return f"detector-breadth-{stem}-{proof_kind}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"


def _remote_result_from_payload(payload: dict[str, object], *, proof_kind: str) -> dict[str, object]:
    comparison = payload.get("comparison")
    summary = payload.get("summary")
    comparison = comparison if isinstance(comparison, dict) else {}
    summary = summary if isinstance(summary, dict) else {}
    return {
        "proofKind": proof_kind,
        "detectorModelPath": Path(str(payload.get("detectorModelName") or payload.get("detectorModelPath") or "")).name,
        "detectorModelName": Path(str(payload.get("detectorModelName") or payload.get("detectorModelPath") or "")).name,
        "edgeShareRepairProfile": None if proof_kind != "compound_thin" else BEST_THIN_REFERENCE_PROFILE,
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


def _remote_result_sort_key(result: dict[str, object]) -> tuple[object, ...]:
    return (
        1 if bool(result.get("productBeatsPlateau")) else 0,
        1 if bool(result.get("ballTrackViable")) else 0,
        _safe_int(result.get("acceptedBallFrames"), 0),
        _safe_int(result.get("controlledPossessionFrames"), 0),
        -_safe_float(result.get("ballTrackEdgeFrameShare"), 1.0),
        1 if str(result.get("proofKind")) == "baseline" else 0,
        str(result.get("detectorModelPath") or ""),
    )


def _determine_next_lever(
    *,
    baseline_remote_beats_plateau: bool,
    compound_thin_remote_beats_plateau: bool,
) -> str:
    if baseline_remote_beats_plateau:
        return run_source_robustness_batch.RECOMMENDED_NEXT_LEVER_PROMOTE_DETECTOR_MODEL_UPGRADE
    if compound_thin_remote_beats_plateau:
        return run_source_robustness_batch.RECOMMENDED_NEXT_LEVER_PROMOTE_DETECTOR_PLUS_BEST_THIN
    return run_source_robustness_batch.RECOMMENDED_NEXT_LEVER_PREPARE_TOUCHLINE_TRAINING_DATA


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
    baseline_guided_rescue_reference_path: str | None = None,
    proposal_selection_truth_seed_path: str | None = None,
    reviewed_positive_anchor_seed_path: str | None = None,
) -> dict[str, object]:
    runpod_session.require_retired_runpod_disabled()


def run_detector_breadth_batch(
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    *,
    manifest_path: Path = run_source_robustness_batch.DEFAULT_MANIFEST_PATH,
    canonical_proof_summary_path: Path = run_source_robustness_batch.DEFAULT_CANONICAL_PROOF_SUMMARY_PATH,
    clip_path: Path | None = None,
    failing_source_clip_id: str = "trimed-5min.mp4",
    comparison_source_clip_id: str = "trimed-football-2-1minute.mp4",
    screen_execution_mode: str = SCREEN_EXECUTION_MODE_REMOTE_GPU,
) -> dict[str, object]:
    runpod_session.require_retired_runpod_disabled()


def main() -> None:
    runpod_session.require_retired_runpod_disabled()


if __name__ == "__main__":
    main()
