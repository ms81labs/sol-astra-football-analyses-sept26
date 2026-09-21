from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.jobs import JobRunner  # noqa: E402
from backend.app.proof_summary import build_canonical_proof_summary  # noqa: E402
from backend.app.proof_summary import save_canonical_proof_summary  # noqa: E402
from backend.app.run_benchmarks import (  # noqa: E402
    DEFAULT_MANUAL_POINTS,
    DEFAULT_STORAGE_ROOT,
    build_selected_cluster_payload,
    summarize_match_benchmark,
)
from backend.app.proof_runtime import save_proof_runtime_options  # noqa: E402
from backend.app.schemas import MatchConfig  # noqa: E402
from backend.app.settings import ProcessingSettings  # noqa: E402
from backend.app.storage import Storage  # noqa: E402

DEFAULT_PROOF_CLIP_PATH = REPO_ROOT / "videos" / "trimed-5min.mp4"
def _proof_payload(storage: Storage, model: object, *, include_selected_clusters: bool = False) -> dict[str, object]:
    payload = build_canonical_proof_summary(model)
    if not include_selected_clusters:
        return payload

    match_id = getattr(model, "matchId", None)
    if isinstance(match_id, str):
        payload.update(build_selected_cluster_payload(storage, match_id))
    return payload


def _wait_for_job_completion(
    storage: Storage,
    job_id: str,
    *,
    poll_interval_seconds: float,
    timeout_seconds: float,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while True:
        job = storage.get_job(job_id)
        if job.status == "completed":
            return
        if job.status in {"failed", "cancelled", "canceled"}:
            error_message = job.error or job.message or f"Job {job_id} failed"
            raise RuntimeError(error_message)
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Timed out waiting for local app-path proof job {job_id}.")
        time.sleep(poll_interval_seconds)


def run_local_app_path_proof(
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    clip_path: Path = DEFAULT_PROOF_CLIP_PATH,
    manual_points: list[list[float]] | None = None,
    settings: ProcessingSettings | None = None,
    name: str | None = None,
    model_path: str | None = None,
    primary_model_path: str | None = None,
    auxiliary_ball_model_path: str | None = None,
    auxiliary_ball_model_profile: str | None = None,
    edge_share_repair_profile: str | None = None,
    baseline_guided_rescue_reference_path: str | None = None,
    proposal_selection_truth_seed_path: str | None = None,
    reviewed_positive_anchor_seed_path: str | None = None,
    *,
    poll_interval_seconds: float = 5.0,
    timeout_seconds: float = 1800.0,
) -> object:
    local_settings = settings or ProcessingSettings(processing_backend="local")
    storage = Storage(storage_root)
    config = MatchConfig(
        attackDirection="left_to_right",
        manualHomographyPoints=manual_points or DEFAULT_MANUAL_POINTS,
        autoHomography=False,
    )
    match = storage.create_match(
        name=name or f"{clip_path.stem}-local-app-path-proof",
        input_mode="video",
        original_filename=clip_path.name,
        input_path=clip_path,
        config=config,
    )
    save_proof_runtime_options(
        storage,
        match.id,
        model_path=model_path,
        primary_model_path=primary_model_path,
        auxiliary_ball_model_path=auxiliary_ball_model_path,
        auxiliary_ball_model_profile=auxiliary_ball_model_profile,
        edge_share_repair_profile=edge_share_repair_profile,
        baseline_guided_rescue_reference_path=baseline_guided_rescue_reference_path,
        proposal_selection_truth_seed_path=proposal_selection_truth_seed_path,
        reviewed_positive_anchor_seed_path=reviewed_positive_anchor_seed_path,
    )
    job = storage.create_job(match.id)

    runner = JobRunner(storage.storage_root, settings=local_settings)
    runner.start(job.id)
    _wait_for_job_completion(
        storage,
        job.id,
        poll_interval_seconds=poll_interval_seconds,
        timeout_seconds=timeout_seconds,
    )
    summary = summarize_match_benchmark(storage, match.id)
    save_canonical_proof_summary(storage, match.id, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a normal local app-path proof and summarize the saved match.")
    parser.add_argument("--storage-root", default=str(DEFAULT_STORAGE_ROOT))
    parser.add_argument("--video-path", default=str(DEFAULT_PROOF_CLIP_PATH))
    parser.add_argument("--name", default=None)
    parser.add_argument("--model-path", default=None)
    parser.add_argument("--primary-model-path", default=None)
    parser.add_argument("--auxiliary-ball-model-path", default=None)
    parser.add_argument("--auxiliary-ball-model-profile", default=None)
    parser.add_argument("--edge-share-repair-profile", default=None)
    parser.add_argument("--baseline-guided-rescue-reference-path", default=None)
    parser.add_argument("--proposal-selection-truth-seed-path", default=None)
    parser.add_argument("--reviewed-positive-anchor-seed-path", default=None)
    parser.add_argument("--poll-interval-seconds", type=float, default=5.0)
    parser.add_argument("--timeout-seconds", type=float, default=1800.0)
    parser.add_argument("--include-selected-clusters", action="store_true")
    args = parser.parse_args()

    storage_root = Path(args.storage_root)
    summary = run_local_app_path_proof(
        storage_root=storage_root,
        clip_path=Path(args.video_path),
        name=args.name,
        model_path=args.model_path,
        primary_model_path=args.primary_model_path,
        auxiliary_ball_model_path=args.auxiliary_ball_model_path,
        auxiliary_ball_model_profile=args.auxiliary_ball_model_profile,
        edge_share_repair_profile=args.edge_share_repair_profile,
        baseline_guided_rescue_reference_path=args.baseline_guided_rescue_reference_path,
        proposal_selection_truth_seed_path=args.proposal_selection_truth_seed_path,
        reviewed_positive_anchor_seed_path=args.reviewed_positive_anchor_seed_path,
        poll_interval_seconds=args.poll_interval_seconds,
        timeout_seconds=args.timeout_seconds,
    )
    payload = _proof_payload(
        Storage(storage_root),
        summary,
        include_selected_clusters=args.include_selected_clusters,
    )
    print(json.dumps(payload, separators=(",", ":")))


if __name__ == "__main__":
    main()
