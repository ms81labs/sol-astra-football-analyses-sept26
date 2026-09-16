from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccertrack_controlled_sample_fetch as controlled_fetch


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_approval_inputs(tmp_path: Path, *, approved: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    approval_root = candidate_root / "football_external_soccertrack_sample_fixture_materialization_approval_v1"
    _write_json(
        approval_root / "sample_fixture_materialization_approval_summary.json",
        {
            "batchName": "football_external_soccertrack_sample_fixture_materialization_approval",
            "goalAchieved": approved,
            "roadmapAdvanceAllowed": approved,
            "primaryBlocker": None if approved else "football_external_soccertrack_sample_fixture_approval_guardrail_failed",
            "sampleFixtureMaterializationApproved": approved,
            "sampleDownloadApproved": approved,
            "sampleDownloadExecuted": False,
            "datasetDownloadApproved": False,
            "datasetDownloadExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationAllowed": False,
            "nextRecommendedNextLever": "football_external_soccertrack_controlled_sample_fetch",
        },
    )
    _write_json(
        approval_root / "soccertrack_sample_fixture_materialization_approval_contract.json",
        {
            "schemaVersion": "soccertrack_sample_fixture_materialization_approval_contract_v1",
            "selectedSampleResourceId": "soccertrack_v2",
            "approvedUse": "adapter_fixture_materialization_only",
            "sampleFixtureMaterializationApproved": approved,
            "sampleDownloadApproved": approved,
            "sampleDownloadExecuted": False,
            "datasetDownloadApproved": False,
            "datasetDownloadExecuted": False,
            "fullDatasetDownloadApproved": False,
            "trainingUseApproved": False,
            "trainingExecuted": False,
        },
    )
    _write_json(
        approval_root / "approved_sample_scope.json",
        {
            "schemaVersion": "soccertrack_approved_sample_scope_v1",
            "selectedSampleResourceId": "soccertrack_v2",
            "maxSampleMatches": 1,
            "requiredTaskFixtures": ["gsr", "bas", "mot"],
            "sampleDownloadExecuted": False,
            "datasetDownloadExecuted": False,
            "trainingExecuted": False,
        },
    )
    return candidate_root


def _tree_with_fixtures() -> dict[str, object]:
    return {
        "tree": [
            {"type": "blob", "path": "gsr/117093/117093_1st.json", "size": 200},
            {"type": "blob", "path": "bas/117093/117093_12_class_events.json", "size": 220},
            {"type": "blob", "path": "mot/117093/gt/gt.txt", "size": 240},
            {"type": "blob", "path": "docs/matches.json", "size": 120},
            {"type": "blob", "path": "docs/assets/demo-gsr_and_bas.mp4", "size": 30_184_340},
        ]
    }


def _tree_without_fixtures() -> dict[str, object]:
    return {
        "tree": [
            {"type": "blob", "path": "docs/matches.json", "size": 120},
            {"type": "blob", "path": "docs/leaderboards/gsr.json", "size": 40},
            {"type": "blob", "path": "docs/assets/demo-gsr_and_bas.mp4", "size": 30_184_340},
        ]
    }


def test_controlled_sample_fetch_downloads_one_match_fixture_files_when_publicly_exposed(tmp_path: Path) -> None:
    candidate_root = _write_approval_inputs(tmp_path)

    def fetcher(url: str) -> bytes:
        return f"fixture from {url}".encode("utf-8")

    payload = controlled_fetch.run_football_external_soccertrack_controlled_sample_fetch(
        storage_root=tmp_path,
        tree_fetcher=lambda: _tree_with_fixtures(),
        fetcher=fetcher,
    )

    output_root = candidate_root / "football_external_soccertrack_controlled_sample_fetch_v1"
    manifest = json.loads((output_root / "controlled_sample_fetch_manifest.json").read_text(encoding="utf-8"))
    provenance = json.loads((output_root / "sample_fetch_provenance_audit.json").read_text(encoding="utf-8"))
    guardrail = json.loads((output_root / "sample_fetch_guardrail_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["controlledSampleFetchExecuted"] is True
    assert payload["selectedMatchId"] == "117093"
    assert payload["downloadedFixtureFileCount"] == 3
    assert payload["downloadedTaskIds"] == ["bas", "gsr", "mot"]
    assert payload["datasetDownloadExecuted"] is False
    assert payload["fullDatasetDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_sample_fixture_materialization"
    assert len(manifest["downloadedFiles"]) == 3
    assert provenance["fetchFailureCount"] == 0
    assert guardrail["largeMediaFileSkippedCount"] == 1
    assert all((output_root / row["relativePath"]).exists() for row in manifest["downloadedFiles"])


def test_controlled_sample_fetch_reports_public_fixture_gap_without_fetching_media(tmp_path: Path) -> None:
    _write_approval_inputs(tmp_path)

    payload = controlled_fetch.run_football_external_soccertrack_controlled_sample_fetch(
        storage_root=tmp_path,
        tree_fetcher=lambda: _tree_without_fixtures(),
        fetcher=lambda url: b"unused",
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_public_fixture_files_missing"
    assert payload["controlledSampleFetchExecuted"] is False
    assert payload["sampleDownloadExecuted"] is False
    assert payload["datasetDownloadExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_fixture_source_access_review"


def test_controlled_sample_fetch_blocks_without_approval(tmp_path: Path) -> None:
    _write_approval_inputs(tmp_path, approved=False)

    payload = controlled_fetch.run_football_external_soccertrack_controlled_sample_fetch(
        storage_root=tmp_path,
        tree_fetcher=lambda: _tree_with_fixtures(),
        fetcher=lambda url: b"unused",
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_controlled_sample_fetch_approval_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_sample_fixture_materialization_approval"


def test_controlled_sample_fetch_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_approval_inputs(tmp_path)

    payload = controlled_fetch.run_football_external_soccertrack_controlled_sample_fetch(
        storage_root=tmp_path,
        tree_fetcher=lambda: _tree_without_fixtures(),
        fetcher=lambda url: b"unused",
    )

    assert payload["attemptPlanFamilies"] == [
        "soccertrack_controlled_fixture_source_tree_fetch",
        "soccertrack_controlled_fixture_source_locator_repair",
        "soccertrack_controlled_sample_fetch_blocker_summary",
    ]
