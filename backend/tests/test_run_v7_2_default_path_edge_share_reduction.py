from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_v7_2_default_path_edge_share_reduction as edge_reduction


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _ball_rows(*, edge_rows: int, non_edge_rows: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    frame_id = 0
    for _ in range(edge_rows):
        rows.append({"Frame_ID": frame_id, "Entity_Type": "ball", "X": 2.0, "Y": 50.0, "Conf": 0.9})
        frame_id += 5
    for _ in range(non_edge_rows):
        rows.append({"Frame_ID": frame_id, "Entity_Type": "ball", "X": 50.0, "Y": 50.0, "Conf": 0.9})
        frame_id += 5
    return rows


def _write_match_truth(tmp_path: Path, match_id: str, *, edge_rows: int, non_edge_rows: int) -> None:
    _write_json(
        tmp_path / "matches" / match_id / "ball_truth_layers.json",
        {
            "acceptedBall": {"rows": _ball_rows(edge_rows=edge_rows, non_edge_rows=non_edge_rows)},
            "probeObservedBall": {"filteredRows": [], "rawRows": []},
            "sampleInterval": 5,
        },
    )


def _write_suite_truth(
    tmp_path: Path,
    *,
    passed_gate: bool = False,
    missing_audits: bool = False,
) -> None:
    suite_root = tmp_path / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
    blockers = [] if passed_gate else ["failing_source_not_viable"]
    _write_json(
        suite_root / "suite_summary.json",
        {
            "passedPromotionGate": passed_gate,
            "sourceRobustnessPromotionBlockers": blockers,
            "sourceRobustnessRecommendedNextLever": (
                "v7_2_runtime_default_change_validation" if passed_gate else "promoted_v7_2_source_robustness_validation"
            ),
            "sourceRobustnessBestConfigName": "source_robustness_shadow_edge_run_keep_every_2_min10",
            "sourceRobustnessBestExploratoryConfigName": "source_robustness_shadow_edge_run_keep_every_3_min10",
        },
    )
    _write_json(
        suite_root / "v7_2_source_robustness_default_blocker_analysis_v1" / "default_blocker_analysis_summary.json",
        {
            "primaryBlocker": None if passed_gate else "v7_2_default_path_performance_blocker",
            "realDefaultPerformanceFailureProven": not passed_gate,
            "nextRecommendedNextLever": (
                "v7_2_runtime_default_change_validation" if passed_gate else "v7_2_default_path_edge_share_reduction"
            ),
        },
    )
    if missing_audits:
        return

    configs = {
        "source_robustness_baseline_current": {
            "sourceSummaries": {
                "trimed-5min.mp4": {
                    "medianBallTrackEdgeFrameShare": 0.822,
                    "medianAcceptedRetentionRatio": 1.0,
                    "medianControlledRetentionRatio": 1.0,
                    "sourceViable": False,
                }
            },
            "configOutcome": "source_robustness_weak",
        },
        "source_robustness_shadow_edge_run_keep_every_2_min10": {
            "sourceSummaries": {
                "trimed-5min.mp4": {
                    "medianBallTrackEdgeFrameShare": 0.714,
                    "medianAcceptedRetentionRatio": 0.624,
                    "medianControlledRetentionRatio": 0.612,
                    "sourceViable": False,
                }
            },
            "configOutcome": "source_robustness_partial",
        },
        "source_robustness_shadow_edge_run_keep_every_3_min10": {
            "sourceSummaries": {
                "trimed-5min.mp4": {
                    "medianBallTrackEdgeFrameShare": 0.647,
                    "medianAcceptedRetentionRatio": 0.505,
                    "medianControlledRetentionRatio": 0.5,
                    "sourceViable": False,
                }
            },
            "configOutcome": "source_robustness_weak",
        },
    }
    _write_json(suite_root / "primary_source_robustness_source_audit.json", {"configs": configs})
    _write_json(
        suite_root / "primary_source_robustness_matrix.json",
        {
            "configs": {
                "source_robustness_shadow_edge_run_keep_every_2_min10": {
                    "configOutcome": "source_robustness_partial",
                    "passedPromotionGate": False,
                    "promotionBlockers": ["failing_source_not_viable"],
                    "failingSourceEdgeShareImprovement": 0.108,
                },
                "source_robustness_shadow_edge_run_keep_every_3_min10": {
                    "configOutcome": "source_robustness_weak",
                    "passedPromotionGate": False,
                    "promotionBlockers": [
                        "accepted_retention_below_guardrail",
                        "controlled_retention_below_guardrail",
                    ],
                    "failingSourceEdgeShareImprovement": 0.175,
                },
            }
        },
    )
    _write_json(
        suite_root / "primary_source_robustness_failure_audit.json",
        {
            "selectedConfigName": "source_robustness_shadow_edge_run_keep_every_2_min10",
            "configs": {
                "source_robustness_baseline_current": {
                    "sliceDiagnostics": [
                        {"matchId": "edge-heavy-a", "ballTrackEdgeFrameShare": 0.82},
                        {"matchId": "already-better-b", "ballTrackEdgeFrameShare": 0.55},
                    ]
                },
                "source_robustness_shadow_edge_run_keep_every_2_min10": {
                    "sliceDiagnostics": [
                        {
                            "matchId": "edge-heavy-a",
                            "ballTrackEdgeFrameShare": 0.714,
                            "acceptedRetentionRatio": 0.624,
                            "controlledRetentionRatio": 0.612,
                        },
                        {
                            "matchId": "already-better-b",
                            "ballTrackEdgeFrameShare": 0.52,
                            "acceptedRetentionRatio": 0.75,
                            "controlledRetentionRatio": 0.75,
                        },
                    ]
                },
                "source_robustness_shadow_edge_run_keep_every_3_min10": {
                    "sliceDiagnostics": [
                        {
                            "matchId": "edge-heavy-a",
                            "ballTrackEdgeFrameShare": 0.647,
                            "acceptedRetentionRatio": 0.505,
                            "controlledRetentionRatio": 0.5,
                        },
                    ]
                },
            },
        },
    )
    _write_match_truth(tmp_path, "edge-heavy-a", edge_rows=82, non_edge_rows=18)
    _write_match_truth(tmp_path, "already-better-b", edge_rows=36, non_edge_rows=24)


def test_edge_only_reduction_infeasible_routes_to_inboard_recovery(tmp_path: Path) -> None:
    _write_suite_truth(tmp_path)

    payload = edge_reduction.run_v7_2_default_path_edge_share_reduction(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_2_default_path_inboard_ball_recovery_required"
    assert payload["nextRecommendedNextLever"] == "v7_2_default_path_inboard_ball_recovery"
    assert payload["edgeOnlyReductionCanClearNearViableGate"] is False
    assert payload["minimumAdditionalInboardFramesNeededForNearViable"] >= 3
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationExecuted"] is False


def test_clear_source_gate_routes_to_default_change_validation(tmp_path: Path) -> None:
    _write_suite_truth(tmp_path, passed_gate=True)

    payload = edge_reduction.run_v7_2_default_path_edge_share_reduction(storage_root=tmp_path)

    assert payload["primaryBlocker"] is None
    assert payload["goalAchieved"] is True
    assert payload["nextRecommendedNextLever"] == "v7_2_runtime_default_change_validation"


def test_missing_audits_fail_to_instrumentation(tmp_path: Path) -> None:
    _write_suite_truth(tmp_path, missing_audits=True)

    payload = edge_reduction.run_v7_2_default_path_edge_share_reduction(storage_root=tmp_path)

    assert payload["primaryBlocker"] == "v7_2_default_path_edge_share_artifacts_missing"
    assert payload["nextRecommendedNextLever"] == "v7_2_default_path_edge_share_instrumentation"


def test_writes_required_artifacts(tmp_path: Path) -> None:
    _write_suite_truth(tmp_path)

    edge_reduction.run_v7_2_default_path_edge_share_reduction(storage_root=tmp_path)

    output_root = (
        tmp_path
        / "benchmark_suites"
        / "frozen-viable-baseline-slice-suite"
        / "v7_2_default_path_edge_share_reduction_v1"
    )
    for name in [
        "edge_share_reduction_summary.json",
        "edge_share_feasibility_audit.json",
        "edge_thinning_tradeoff_audit.json",
        "inboard_recovery_requirement.json",
        "decision_matrix.json",
        "batch_outcome_analysis.json",
        "batch_outcome_analysis.md",
    ]:
        assert (output_root / name).exists()
