from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_promoted_v6_source_manifest_and_gold_truth_refresh as manifest_refresh


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _proposal_window(
    start_frame: int,
    end_frame: int,
    *,
    frame_count: int,
    bucket: str = manifest_refresh.BUCKET_PROPOSAL_NOT_SELECTED,
) -> dict[str, object]:
    return {
        "startFrame": start_frame,
        "endFrame": end_frame,
        "frameCount": frame_count,
        "frameIds": list(range(start_frame, end_frame + 1, 5)),
        "taxonomyBucket": bucket,
        "evidence": ["synthetic evidence"],
    }


def test_build_manifest_windows_filters_and_pads_proposal_selection_windows() -> None:
    taxonomy = {
        "failingSourceClipId": "trimed-5min.mp4",
        "sampleInterval": 5,
        "windows": [
            _proposal_window(0, 0, frame_count=1),
            _proposal_window(255, 300, frame_count=10),
            _proposal_window(
                500,
                520,
                frame_count=5,
                bucket="support_or_viability_filter_loss",
            ),
        ],
    }

    windows = manifest_refresh.build_proposal_selection_window_manifest(
        taxonomy=taxonomy,
        source_manifest={"entries": [{"clipId": "trimed-5min.mp4", "localPath": "/video.mp4"}]},
        validation_root=Path("/validation"),
        failing_source_clip_id="trimed-5min.mp4",
    )["windows"]

    assert [window["windowId"] for window in windows] == [
        "trimed-5min.mp4-proposal-selection-0000-0000",
        "trimed-5min.mp4-proposal-selection-0255-0300",
    ]
    assert windows[0]["paddedStartFrame"] == 0
    assert windows[0]["paddedEndFrame"] == 10
    assert windows[1]["paddedStartFrame"] == 245
    assert windows[1]["paddedEndFrame"] == 310
    assert {window["taxonomyBucket"] for window in windows} == {
        manifest_refresh.BUCKET_PROPOSAL_NOT_SELECTED
    }


def test_bootstrap_plan_ranks_top_five_windows_by_frame_count_then_start_frame() -> None:
    windows = [
        {"windowId": "late-30", "startFrame": 3295, "frameCount": 30},
        {"windowId": "early-19", "startFrame": 2940, "frameCount": 19},
        {"windowId": "late-11", "startFrame": 6300, "frameCount": 11},
        {"windowId": "early-10", "startFrame": 255, "frameCount": 10},
        {"windowId": "mid-8", "startFrame": 3115, "frameCount": 8},
        {"windowId": "small-7", "startFrame": 4665, "frameCount": 7},
    ]

    plan = manifest_refresh.build_gold_truth_bootstrap_plan(
        proposal_windows={"windows": windows},
        target_window_count=5,
    )

    assert [window["windowId"] for window in plan["bootstrapWindows"]] == [
        "late-30",
        "early-19",
        "late-11",
        "early-10",
        "mid-8",
    ]
    assert plan["selectedWindowCount"] == 5
    assert plan["selectedMissingAcceptedFrameCount"] == 78


def test_run_manifest_refresh_writes_expected_artifacts_and_preserves_source_manifest(tmp_path: Path) -> None:
    analysis_root = tmp_path / "analysis"
    review_root = tmp_path / "review"
    validation_root = tmp_path / "validation"
    retention_root = tmp_path / "retention"
    source_manifest_path = tmp_path / "source_manifest.json"

    source_manifest = {
        "suiteName": "frozen",
        "suiteType": "source_manifest",
        "entries": [
            {
                "clipId": "trimed-5min.mp4",
                "label": "Failing source",
                "localPath": "/videos/trimed-5min.mp4",
                "enabled": True,
            }
        ],
    }
    _write_json(source_manifest_path, source_manifest)
    _write_json(
        review_root / "review_refresh_summary.json",
        {
            "goalAchieved": True,
            "dominantBlockerClass": manifest_refresh.BUCKET_PROPOSAL_NOT_SELECTED,
            "nextFixFamily": "proposal_selection_evidence_refresh",
            "missingAcceptedFrameCount": 101,
            "windowCount": 11,
        },
    )
    _write_json(
        review_root / "missing_accepted_signal_taxonomy.json",
        {
            "failingSourceClipId": "trimed-5min.mp4",
            "sampleInterval": 5,
            "missingAcceptedFrameCount": 101,
            "windows": [
                _proposal_window(3295, 3440, frame_count=30),
                _proposal_window(2940, 3030, frame_count=19),
                _proposal_window(6300, 6350, frame_count=11),
                _proposal_window(255, 300, frame_count=10),
                _proposal_window(3115, 3150, frame_count=8),
                _proposal_window(4665, 4695, frame_count=7),
                _proposal_window(6135, 6160, frame_count=6),
                _proposal_window(6185, 6200, frame_count=4),
                _proposal_window(6215, 6225, frame_count=3),
                _proposal_window(340, 345, frame_count=2),
                _proposal_window(0, 0, frame_count=1),
            ],
        },
    )
    _write_json(
        validation_root / "arm_matrix.json",
        {
            "arms": [
                {
                    "armName": "baseline_current",
                    "proofRuns": [
                        {
                            "sourceClipId": "trimed-5min.mp4",
                            "reusedEvidence": {
                                "selectedClusterDeltaPath": str(tmp_path / "baseline" / "selected_cluster_delta.json")
                            },
                        }
                    ],
                },
                {
                    "armName": "promoted_v6_baseline",
                    "proofRuns": [
                        {
                            "sourceClipId": "trimed-5min.mp4",
                            "reusedEvidence": {
                                "selectedClusterDeltaPath": str(tmp_path / "promoted" / "selected_cluster_delta.json")
                            },
                        }
                    ],
                },
            ]
        },
    )
    _write_json(
        retention_root / "retention_delta_summary.json",
        {
            "acceptedRetentionRatio": 0.069,
            "controlledRetentionRatio": 0.102,
            "primaryRetentionBlockerClass": "accepted_signal_retention_collapse",
        },
    )

    payload = manifest_refresh.run_promoted_v6_source_manifest_and_gold_truth_refresh(
        analysis_root=analysis_root,
        review_refresh_root=review_root,
        source_manifest_path=source_manifest_path,
        validation_root=validation_root,
        retention_delta_root=retention_root,
        failing_source_clip_id="trimed-5min.mp4",
    )

    assert json.loads(source_manifest_path.read_text(encoding="utf-8")) == source_manifest
    assert payload["summary"]["goalAchieved"] is True
    assert payload["summary"]["proposalSelectionWindowCount"] == 11
    assert payload["summary"]["selectedBootstrapMissingAcceptedFrameCount"] == 78
    assert payload["summary"]["nextRecommendedAttemptFamily"] == "gold_truth_bootstrap"
    for filename in (
        "manifest_scope_refresh_summary.json",
        "proposal_selection_window_manifest.json",
        "gold_truth_bootstrap_plan.json",
        "source_manifest_delta.json",
        "decision_matrix.json",
        "batch_outcome_analysis.json",
        "batch_outcome_analysis.md",
    ):
        assert (analysis_root / filename).exists()


def test_run_manifest_refresh_marks_weak_evidence_not_achieved(tmp_path: Path) -> None:
    analysis_root = tmp_path / "analysis"
    review_root = tmp_path / "review"
    validation_root = tmp_path / "validation"
    retention_root = tmp_path / "retention"
    source_manifest_path = tmp_path / "source_manifest.json"

    _write_json(
        source_manifest_path,
        {"entries": [{"clipId": "trimed-5min.mp4", "localPath": "/videos/trimed-5min.mp4"}]},
    )
    _write_json(review_root / "review_refresh_summary.json", {"goalAchieved": True})
    _write_json(
        review_root / "missing_accepted_signal_taxonomy.json",
        {
            "failingSourceClipId": "trimed-5min.mp4",
            "sampleInterval": 5,
            "missingAcceptedFrameCount": 20,
            "windows": [
                _proposal_window(10, 20, frame_count=3),
                _proposal_window(40, 45, frame_count=2),
            ],
        },
    )
    _write_json(validation_root / "arm_matrix.json", {"arms": []})
    _write_json(retention_root / "retention_delta_summary.json", {})

    payload = manifest_refresh.run_promoted_v6_source_manifest_and_gold_truth_refresh(
        analysis_root=analysis_root,
        review_refresh_root=review_root,
        source_manifest_path=source_manifest_path,
        validation_root=validation_root,
        retention_delta_root=retention_root,
    )

    assert payload["summary"]["goalAchieved"] is False
    assert payload["summary"]["roadmapAdvanceAllowed"] is False
    assert payload["summary"]["weakEvidenceReasons"] == [
        "proposal_selection_window_count_below_3",
        "missing_accepted_frame_count_below_50",
    ]
