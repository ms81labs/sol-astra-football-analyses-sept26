from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_safe_source_sample_download_approval as approval


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_approval_inputs(tmp_path: Path, *, plan_goal: bool = True, selected: str | None = "soccertrack_v2") -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    plan_root = candidate_root / "football_external_safe_source_sample_ingestion_plan_v1"
    _write_json(
        plan_root / "safe_source_sample_ingestion_plan_summary.json",
        {
            "batchName": "football_external_safe_source_sample_ingestion_plan",
            "goalAchieved": plan_goal,
            "primaryBlocker": None if plan_goal else "football_external_sample_ingestion_fixture_missing",
            "sampleIngestionPlanReady": plan_goal,
            "selectedFirstSampleResourceId": selected,
            "sampleDownloadApprovalRequired": True,
            "sampleDownloadExecuted": False,
            "datasetDownloadExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationAllowed": False,
            "nextRecommendedNextLever": "football_external_safe_source_sample_download_approval",
        },
    )
    _write_json(
        plan_root / "sample_download_approval_checklist.json",
        {
            "approvalRequiredBeforeDownload": True,
            "selectedFirstSampleResourceId": selected,
            "resources": [
                {
                    "resourceId": "soccertrack_v2",
                    "officialSourceUrls": ["https://github.com/SoccerTrack/SoccerTrack"],
                    "approvalStatus": "manual_approval_required",
                    "downloadAllowedByThisBatch": False,
                    "trainingUseAllowed": False,
                }
            ],
        },
    )
    _write_json(
        plan_root / "sample_ingestion_guardrail_audit.json",
        {"sampleIngestionGuardrailPassed": True, "sampleDownloadExecuted": False, "datasetDownloadExecuted": False},
    )
    return candidate_root


def test_sample_download_approval_corrects_soccertrack_source_and_approves_controlled_fetch(tmp_path: Path) -> None:
    candidate_root = _write_approval_inputs(tmp_path)

    payload = approval.run_football_external_safe_source_sample_download_approval(storage_root=tmp_path)

    output_root = candidate_root / "football_external_safe_source_sample_download_approval_v1"
    source_audit = json.loads((output_root / "selected_source_access_evidence_audit.json").read_text(encoding="utf-8"))
    approval_contract = json.loads((output_root / "controlled_sample_fetch_approval_contract.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["selectedSampleResourceId"] == "soccertrack_v2"
    assert payload["officialSourceUrlCorrected"] is True
    assert payload["sampleDownloadApproved"] is True
    assert payload["sampleDownloadExecuted"] is False
    assert payload["datasetDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_safe_source_controlled_sample_fetch"
    assert source_audit["correctedOfficialSourceUrl"] == "https://github.com/AtomScott/SoccerTrack-v2"
    assert source_audit["licenseUseClass"] == "controlled_sample_allowed_with_attribution"
    assert approval_contract["approvedFetchScope"] == "smallest_official_sample_or_metadata_only"
    assert approval_contract["fullDatasetDownloadApproved"] is False


def test_sample_download_approval_blocks_without_ingestion_plan(tmp_path: Path) -> None:
    _write_approval_inputs(tmp_path, plan_goal=False)

    payload = approval.run_football_external_safe_source_sample_download_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_sample_download_approval_plan_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_safe_source_sample_ingestion_plan"
    assert payload["sampleDownloadExecuted"] is False


def test_sample_download_approval_blocks_unknown_selected_resource(tmp_path: Path) -> None:
    _write_approval_inputs(tmp_path, selected="unknown_source")

    payload = approval.run_football_external_safe_source_sample_download_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_sample_download_approval_unknown_source"
    assert payload["nextRecommendedNextLever"] == "football_external_safe_source_sample_ingestion_plan"


def test_sample_download_approval_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_approval_inputs(tmp_path)

    payload = approval.run_football_external_safe_source_sample_download_approval(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "safe_source_sample_download_approval",
        "sample_source_access_evidence_repair",
        "sample_download_approval_blocker_summary",
    ]
