from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_safe_source_controlled_sample_fetch as controlled_fetch


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_fetch_inputs(tmp_path: Path, *, approval_goal: bool = True, approved: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    approval_root = candidate_root / "football_external_safe_source_sample_download_approval_v1"
    _write_json(
        approval_root / "sample_download_approval_summary.json",
        {
            "batchName": "football_external_safe_source_sample_download_approval",
            "goalAchieved": approval_goal,
            "primaryBlocker": None if approval_goal else "football_external_sample_download_approval_unknown_source",
            "selectedSampleResourceId": "soccertrack_v2",
            "correctedOfficialSourceUrl": "https://github.com/AtomScott/SoccerTrack-v2",
            "sampleDownloadApproved": approved,
            "sampleDownloadExecuted": False,
            "fullDatasetDownloadApproved": False,
            "datasetDownloadExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationAllowed": False,
            "nextRecommendedNextLever": "football_external_safe_source_controlled_sample_fetch",
        },
    )
    _write_json(
        approval_root / "controlled_sample_fetch_approval_contract.json",
        {
            "selectedSampleResourceId": "soccertrack_v2",
            "approvedFetchScope": "smallest_official_sample_or_metadata_only" if approved else None,
            "sampleDownloadApproved": approved,
            "sampleDownloadExecuted": False,
            "fullDatasetDownloadApproved": False,
            "trainingUseApproved": False,
            "requiredFetchMetadata": ["sourceUrl", "sha256ByFile"],
        },
    )
    return candidate_root


def test_controlled_fetch_downloads_only_metadata_files_with_hashes(tmp_path: Path) -> None:
    candidate_root = _write_fetch_inputs(tmp_path)

    def fake_fetch(url: str) -> bytes:
        return f"content for {url}".encode("utf-8")

    payload = controlled_fetch.run_football_external_safe_source_controlled_sample_fetch(
        storage_root=tmp_path,
        fetcher=fake_fetch,
    )

    output_root = candidate_root / "football_external_safe_source_controlled_sample_fetch_v1"
    manifest = json.loads((output_root / "controlled_fetch_manifest.json").read_text(encoding="utf-8"))
    provenance = json.loads((output_root / "fetch_provenance_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["selectedSampleResourceId"] == "soccertrack_v2"
    assert payload["controlledMetadataFetchExecuted"] is True
    assert payload["fetchedFileCount"] == 3
    assert payload["datasetDownloadExecuted"] is False
    assert payload["fullDatasetDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_metadata_adapter_smoke"
    assert manifest["fetchScope"] == "metadata_only"
    assert len(provenance["files"]) == 3
    assert all(row["sha256"] for row in provenance["files"])
    assert (output_root / "sample_metadata" / "README.md").exists()
    assert (output_root / "decision_matrix.json").exists()


def test_controlled_fetch_blocks_without_approval(tmp_path: Path) -> None:
    _write_fetch_inputs(tmp_path, approval_goal=False)

    payload = controlled_fetch.run_football_external_safe_source_controlled_sample_fetch(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_controlled_fetch_approval_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_safe_source_sample_download_approval"
    assert payload["datasetDownloadExecuted"] is False


def test_controlled_fetch_blocks_when_approval_does_not_allow_fetch(tmp_path: Path) -> None:
    _write_fetch_inputs(tmp_path, approved=False)

    payload = controlled_fetch.run_football_external_safe_source_controlled_sample_fetch(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_controlled_fetch_not_approved"
    assert payload["nextRecommendedNextLever"] == "football_external_safe_source_sample_download_approval"


def test_controlled_fetch_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_fetch_inputs(tmp_path)

    def fake_fetch(url: str) -> bytes:
        return b"ok"

    payload = controlled_fetch.run_football_external_safe_source_controlled_sample_fetch(
        storage_root=tmp_path,
        fetcher=fake_fetch,
    )

    assert payload["attemptPlanFamilies"] == [
        "controlled_metadata_only_fetch",
        "controlled_fetch_contract_repair",
        "controlled_fetch_blocker_summary",
    ]
