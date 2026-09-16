from __future__ import annotations

from pathlib import Path

from backend.scripts.run_video_to_analysis_source_pool_replenishment_approval import (
    run_video_to_analysis_source_pool_replenishment_approval,
)


def test_source_pool_replenishment_approval_preserves_relative_storage_root(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    summary = run_video_to_analysis_source_pool_replenishment_approval(
        storage_root=Path("storage"),
        candidate_name="candidate",
        output_dir_name="approval",
    )

    assert summary["goalAchieved"] is False
    assert (
        Path("storage")
        / "trained_detector_candidates"
        / "candidate"
        / "approval"
        / "source_pool_replenishment_approval_summary.json"
    ).is_file()
