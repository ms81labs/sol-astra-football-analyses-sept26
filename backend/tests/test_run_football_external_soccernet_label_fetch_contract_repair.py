from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_label_fetch_contract_repair as repair


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_repair_inputs(tmp_path: Path, *, fetch_failed: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    fetch_root = candidate_root / "football_external_soccernet_controlled_label_sample_fetch_v1"
    _write_json(
        fetch_root / "controlled_label_fetch_summary.json",
        {
            "batchName": "football_external_soccernet_controlled_label_sample_fetch",
            "goalAchieved": not fetch_failed,
            "primaryBlocker": "football_external_soccernet_label_fetch_failed" if fetch_failed else None,
            "downloadedLabelFileCount": 0 if fetch_failed else 1,
            "fetchFailureCount": 1 if fetch_failed else 0,
            "labelDownloadExecuted": not fetch_failed,
            "fullOriginalVideoDownloadExecuted": False,
            "datasetDownloadExecuted": False,
            "trainingExecuted": False,
            "nextRecommendedNextLever": "football_external_soccernet_label_fetch_contract_repair" if fetch_failed else "football_external_soccernet_label_schema_probe",
        },
    )
    _write_json(
        fetch_root / "label_fetch_provenance_audit.json",
        {
            "fetchExecuted": True,
            "files": [],
            "failures": [
                {
                    "name": "Labels.json",
                    "gameRef": "england_efl/2019-2020/2019-10-01 - Middlesbrough - Preston North End",
                    "returncode": 0,
                    "stdoutTail": "HTTP Error 404: Not Found\n",
                    "exists": False,
                }
            ],
        },
    )
    return candidate_root


def test_label_fetch_contract_repair_diagnoses_per_game_label_mismatch(tmp_path: Path) -> None:
    candidate_root = _write_repair_inputs(tmp_path)

    payload = repair.run_football_external_soccernet_label_fetch_contract_repair(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_label_fetch_contract_repair_v1"
    diagnosis = json.loads((output_root / "label_fetch_failure_diagnosis.json").read_text(encoding="utf-8"))
    repair_contract = json.loads((output_root / "repaired_access_contract_plan.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["failedFetchRootCause"] == "soccernet_spotting_ball_per_game_labels_json_not_served"
    assert payload["perGameLabelsJsonSupported"] is False
    assert payload["labelDownloadExecuted"] is False
    assert payload["datasetDownloadExecuted"] is False
    assert payload["fullOriginalVideoDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_split_archive_access_review"
    assert diagnosis["http404Observed"] is True
    assert repair_contract["recommendedAccessSurface"] == "spotting_ball_split_archive"
    assert repair_contract["approvalRequiredBeforeDownload"] is True


def test_label_fetch_contract_repair_blocks_without_failed_fetch_truth(tmp_path: Path) -> None:
    _write_repair_inputs(tmp_path, fetch_failed=False)

    payload = repair.run_football_external_soccernet_label_fetch_contract_repair(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_label_fetch_failure_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_controlled_label_sample_fetch"
    assert payload["labelDownloadExecuted"] is False


def test_label_fetch_contract_repair_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_repair_inputs(tmp_path)

    payload = repair.run_football_external_soccernet_label_fetch_contract_repair(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_label_fetch_failure_root_cause",
        "soccernet_split_archive_contract_plan",
        "soccernet_label_fetch_contract_blocker_summary",
    ]
