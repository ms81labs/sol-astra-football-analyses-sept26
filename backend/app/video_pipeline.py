from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from .schemas import MatchConfig
from .workbench.cache import cache_identity, recompute_plan
from .workbench.media import FrameSource, OpenCvFrameSource, SamplingAudit, four_rates_receipt

# Exposed at module level so tests can patch this name directly.
from backend.run_guerilla import TARGET_FPS, process_video as _process_video_impl


def _probe_source_clock(video_path: Path, frame_source: FrameSource | None) -> dict[str, object]:
    adapter = frame_source or OpenCvFrameSource()
    try:
        identity = adapter.probe(video_path)
        return identity.model_dump(mode="json")
    except Exception as exc:
        return {
            "sourceSha256": "",
            "byteSize": 0,
            "decodeErrors": ["probe_unavailable", type(exc).__name__],
        }


def process_video_input(
    video_path: Path,
    config: MatchConfig,
    *,
    model_path: str | None = None,
    primary_model_path: str | None = None,
    auxiliary_ball_model_path: str | None = None,
    auxiliary_ball_model_profile: str | None = None,
    edge_share_repair_profile: str | None = None,
    baseline_guided_rescue_reference_path: str | None = None,
    proposal_selection_truth_seed_path: str | None = None,
    reviewed_positive_anchor_seed_path: str | None = None,
    progress_callback=None,
    match_id: str | None = None,
    job_id: str | None = None,
    primary_acquisition_mode: str = "anchored_player_ranked_context_960",
    frame_source: FrameSource | None = None,
) -> dict[str, object]:
    adapter = frame_source or OpenCvFrameSource()
    if config.autoHomography:
        # Auto-detect: backend tries pitch_detector.py first, fallback to manual
        homography_points = None
        auto_homography = True
    elif len(config.manualHomographyPoints) == 4:
        homography_points = [[point.x, point.y] for point in config.manualHomographyPoints]
        auto_homography = False
    else:
        raise RuntimeError(
            f"manualHomographyPoints must contain exactly 4 points (got {len(config.manualHomographyPoints)}). "
            "Set autoHomography=True to use automatic pitch detection instead."
        )

    result = _process_video_impl(
        str(video_path),
        output_parquet=None,
        model_path=model_path or "yolov10n.pt",
        primary_model_path=primary_model_path,
        primary_acquisition_mode=primary_acquisition_mode,
        auxiliary_ball_model_path=auxiliary_ball_model_path,
        auxiliary_ball_model_profile=auxiliary_ball_model_profile,
        edge_share_repair_profile=edge_share_repair_profile,
        baseline_guided_rescue_reference_path=baseline_guided_rescue_reference_path,
        proposal_selection_truth_seed_path=proposal_selection_truth_seed_path,
        reviewed_positive_anchor_seed_path=reviewed_positive_anchor_seed_path,
        homography_points=homography_points,
        return_rows=True,
        auto_homography=auto_homography,
        progress_callback=progress_callback,
        match_id=match_id,
        job_id=job_id,
        frame_source=adapter,
    )
    if not result:
        raise RuntimeError("Video pipeline did not return any tracking rows.")
    payload = result if isinstance(result, dict) else {"rows": result, "trackColors": {}}
    source_clock = _probe_source_clock(Path(video_path), adapter)
    payload["sourceClock"] = source_clock
    payload.update(_sampling_and_cache(source_clock, adapter))
    return payload


def _sampling_and_cache(source_clock: dict[str, object], adapter: FrameSource) -> dict[str, object]:
    source_sha = str(source_clock.get("sourceSha256") or "")
    nominal = source_clock.get("nominalFps")
    try:
        nominal_fps = float(nominal) if nominal not in {None, ""} else None
    except (TypeError, ValueError):
        nominal_fps = None
    interval = 1
    if nominal_fps and nominal_fps > TARGET_FPS:
        interval = int(nominal_fps / TARGET_FPS)
    audit = SamplingAudit(
        source_sha256=source_sha,
        declared_target_fps=float(TARGET_FPS),
        nominal_fps=nominal_fps,
        frame_interval=interval,
        selected_backend=f"{getattr(adapter, 'name', 'opencv')}+ultralytics_track",
        temporal_policy="clip_local_index_modulo",
    )
    rates = four_rates_receipt(audit)
    identity = cache_identity(
        source_sha256=source_sha or "0" * 64,
        interval_start=0.0,
        interval_end=0.0,
        decoder_version=str(getattr(adapter, "name", "opencv")),
        model_hash="unspecified",
        temporal_policy=audit.temporal_policy,
        output_schema="evidence_v1",
    )
    return {
        "sampling": audit.receipt().model_dump(mode="json"),
        "fourRates": asdict(rates),
        "cacheIdentity": identity,
        "exportFpsEqualsInferenceFps": False,
    }


def reprocess_for_change(
    *,
    change: str,
    previous_identity: str | None,
    current_identity: str,
    vision,
) -> dict[str, object]:
    plan = recompute_plan(
        previous_identity=previous_identity,
        current_identity=current_identity,
        change=change,
    )
    if change == "report" or plan["reuse"]:
        return {
            "visionInvoked": False,
            "rebuild": list(plan["rebuild"]),
            "reused": True,
            "reason": "report_text_or_identical_cache_identity",
        }
    payload = vision()
    if not isinstance(payload, dict):
        payload = {"rows": payload}
    payload["visionInvoked"] = True
    payload["rebuild"] = list(plan["rebuild"])
    payload["reused"] = False
    return payload
