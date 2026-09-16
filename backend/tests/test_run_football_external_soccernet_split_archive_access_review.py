from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_split_archive_access_review as access_review


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_review_inputs(tmp_path: Path, *, repair_goal: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    repair_root = candidate_root / "football_external_soccernet_label_fetch_contract_repair_v1"
    metadata_root = candidate_root / "football_external_soccernet_api_metadata_probe_v1"
    _write_json(
        repair_root / "label_fetch_contract_repair_summary.json",
        {
            "batchName": "football_external_soccernet_label_fetch_contract_repair",
            "goalAchieved": repair_goal,
            "primaryBlocker": None if repair_goal else "football_external_soccernet_label_fetch_failure_missing",
            "failedFetchRootCause": "soccernet_spotting_ball_per_game_labels_json_not_served",
            "perGameLabelsJsonSupported": False,
            "labelDownloadExecuted": False,
            "datasetDownloadExecuted": False,
            "fullOriginalVideoDownloadExecuted": False,
            "trainingExecuted": False,
            "nextRecommendedNextLever": "football_external_soccernet_split_archive_access_review",
        },
    )
    _write_json(
        repair_root / "repaired_access_contract_plan.json",
        {
            "recommendedAccessSurface": "spotting_ball_split_archive",
            "candidatePackageTasks": ["spotting-ball-2023", "spotting-ball-2024", "spotting-ball-2025"],
            "candidateFilesOrSplits": ["valid.zip", "train.zip", "test.zip", "challenge.zip"],
            "approvalRequiredBeforeDownload": True,
            "fullOriginalVideoDownloadApproved": False,
            "videoDownloadAllowed": False,
            "trainingUseAllowed": False,
        },
    )
    _write_json(
        metadata_root / "soccernet_api_package_audit.json",
        {
            "packageImportReady": True,
            "downloaderImportReady": True,
            "pythonExecutable": str(tmp_path / "fake-venv" / "bin" / "python"),
        },
    )
    return candidate_root


def _downloader_source_with_archives() -> str:
    return '''
        elif task == "spotting-ball-2025":
            if source == "HuggingFace":
                snapshot_download(repo_id="SoccerNet/SN-BAS-2025",
                                repo_type="dataset", revision="main",
                                local_dir=os.path.join(self.LocalDirectory, task),
                                allow_patterns=["*"+s+".zip" for s in split])
        elif task == "spotting-ball-2024":
            if "valid" in split:
                res = self.downloadFile(path_local=os.path.join(self.LocalDirectory, task, "valid.zip"),
                                        user="5yhG5AtySHFNU4T",
                                        password=password)
        elif task == "spotting-ball-2023":
            if "valid" in split:
                res = self.downloadFile(path_local=os.path.join(self.LocalDirectory, task, "valid.zip"),
                                        user="A1ncJfjV31lPSTa",
                                        password=password)
    '''


def test_split_archive_access_review_selects_huggingface_valid_size_probe(tmp_path: Path) -> None:
    candidate_root = _write_review_inputs(tmp_path)

    payload = access_review.run_football_external_soccernet_split_archive_access_review(
        storage_root=tmp_path,
        downloader_source_text=_downloader_source_with_archives(),
    )

    output_root = candidate_root / "football_external_soccernet_split_archive_access_review_v1"
    surface_audit = json.loads((output_root / "split_archive_surface_audit.json").read_text(encoding="utf-8"))
    size_contract = json.loads((output_root / "split_archive_size_probe_contract.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["selectedArchiveTask"] == "spotting-ball-2025"
    assert payload["selectedSplit"] == "valid"
    assert payload["selectedAccessMode"] == "huggingface_snapshot_allow_pattern"
    assert payload["splitArchiveDownloadApproved"] is False
    assert payload["datasetDownloadExecuted"] is False
    assert payload["fullOriginalVideoDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_split_archive_size_probe"
    assert surface_audit["packageSupportedArchiveSurfaceReady"] is True
    assert size_contract["approvalRequiredBeforeArchiveDownload"] is True
    assert size_contract["downloadAllowedByThisBatch"] is False


def test_split_archive_access_review_blocks_without_repair_truth(tmp_path: Path) -> None:
    _write_review_inputs(tmp_path, repair_goal=False)

    payload = access_review.run_football_external_soccernet_split_archive_access_review(
        storage_root=tmp_path,
        downloader_source_text=_downloader_source_with_archives(),
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_label_fetch_contract_repair_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_label_fetch_contract_repair"
    assert payload["datasetDownloadExecuted"] is False


def test_split_archive_access_review_blocks_without_supported_archive_surface(tmp_path: Path) -> None:
    _write_review_inputs(tmp_path)

    payload = access_review.run_football_external_soccernet_split_archive_access_review(
        storage_root=tmp_path,
        downloader_source_text='elif task == "spotting": pass',
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_split_archive_surface_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_api_listing_contract_repair"
    assert payload["splitArchiveDownloadApproved"] is False


def test_split_archive_access_review_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_review_inputs(tmp_path)

    payload = access_review.run_football_external_soccernet_split_archive_access_review(
        storage_root=tmp_path,
        downloader_source_text=_downloader_source_with_archives(),
    )

    assert payload["attemptPlanFamilies"] == [
        "soccernet_split_archive_surface_review",
        "soccernet_split_archive_contract_repair",
        "soccernet_split_archive_blocker_summary",
    ]
