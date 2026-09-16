from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_video_to_analysis_operational_backlog_prioritization as backlog
import backend.scripts.run_video_to_analysis_steady_state_monitoring_cycle as steady_state
from backend.tests.test_run_video_to_analysis_promoted_runtime_post_release_monitoring_chain import _candidate_root, _seed_route
import backend.scripts.run_video_to_analysis_promoted_runtime_operational_completion_summary as completion


def _seed_steady_state(storage_root: Path) -> None:
    _seed_route(storage_root)
    completion.run_video_to_analysis_promoted_runtime_operational_completion_summary(storage_root=storage_root)
    steady_state.run_video_to_analysis_steady_state_monitoring_cycle(storage_root=storage_root)


def test_operational_backlog_prioritization_selects_storage_hygiene_from_steady_state(tmp_path: Path) -> None:
    _seed_steady_state(tmp_path)

    payload = backlog.run_video_to_analysis_operational_backlog_prioritization(storage_root=tmp_path)

    output_root = _candidate_root(tmp_path) / "video_to_analysis_operational_backlog_prioritization_v1"
    backlog_payload = json.loads((output_root / "operational_backlog_prioritization.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["operationalBacklogPrioritized"] is True
    assert payload["selectedOperationalLever"] == "video_to_analysis_storage_retention_and_artifact_hygiene"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_storage_retention_and_artifact_hygiene"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
    assert payload["dataDownloadExecuted"] is False
    assert payload["videoDownloadExecuted"] is False
    assert backlog_payload["priorityOrder"][:5] == [
        "storage_retention_and_artifact_hygiene",
        "operator_dashboard_polish",
        "external_benchmark_real_source_path_consolidation",
        "real_video_scaleout_plan",
        "steady_state_monitoring_recurring_schedule",
    ]
    assert backlog_payload["backlogItems"][0]["nextLever"] == "video_to_analysis_storage_retention_and_artifact_hygiene"


def test_operational_backlog_prioritization_blocks_without_steady_state_truth(tmp_path: Path) -> None:
    payload = backlog.run_video_to_analysis_operational_backlog_prioritization(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "video_to_analysis_operational_backlog_steady_state_missing"
    assert payload["nextRecommendedNextLever"] == "video_to_analysis_steady_state_monitoring_cycle"
    assert payload["trainingExecuted"] is False
    assert payload["promotionMutationExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False
