from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccernet_nda_api_access_approval as soccernet_approval


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_soccernet_inputs(tmp_path: Path, *, include_manual_audit: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    access_root = candidate_root / "football_external_dataset_access_review_v1"
    if include_manual_audit:
        _write_json(
            access_root / "manual_or_gated_access_audit.json",
            {
                "manualOrGatedResources": [
                    {
                        "resourceId": "soccernet_broadcast_tasks",
                        "resourceName": "SoccerNet broadcast tasks",
                        "accessDecision": "manual_or_gated",
                        "accessRiskClass": "research_gated_non_commercial",
                        "officialSourceUrls": ["https://www.soccer-net.org/"],
                        "coveredStages": [
                            "camera_shot_gate",
                            "calibration",
                            "tracking",
                            "ball_localization",
                            "possession_event_semantics",
                        ],
                        "downloadAllowedByThisBatch": False,
                        "trainingUseAllowed": False,
                    }
                ]
            },
        )
    return candidate_root


def test_soccernet_nda_access_approval_records_secretless_api_contract(tmp_path: Path) -> None:
    candidate_root = _write_soccernet_inputs(tmp_path)

    payload = soccernet_approval.run_football_external_soccernet_nda_api_access_approval(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccernet_nda_api_access_approval_v1"
    contract = json.loads((output_root / "soccernet_api_access_contract.json").read_text(encoding="utf-8"))
    credential_audit = json.loads((output_root / "credential_handling_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["soccernetNdaAccessAvailable"] is True
    assert payload["credentialPersisted"] is False
    assert payload["passwordRedacted"] is True
    assert payload["fullOriginalVideoDownloadApproved"] is False
    assert payload["controlledApiMetadataProbeReady"] is True
    assert payload["datasetDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_api_metadata_probe"
    assert contract["credentialEnvVar"] == "SOCCERNET_PASSWORD"
    assert contract["pipInstallCommand"] == "python3 -m pip install SoccerNet --upgrade"
    assert credential_audit["credentialPersisted"] is False
    assert "redacted-test-secret" not in json.dumps(contract)
    assert "redacted-test-secret" not in json.dumps(credential_audit)


def test_soccernet_nda_access_approval_blocks_without_manual_audit(tmp_path: Path) -> None:
    _write_soccernet_inputs(tmp_path, include_manual_audit=False)

    payload = soccernet_approval.run_football_external_soccernet_nda_api_access_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_manual_audit_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_dataset_access_review"
    assert payload["datasetDownloadExecuted"] is False


def test_soccernet_nda_access_approval_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_soccernet_inputs(tmp_path)

    payload = soccernet_approval.run_football_external_soccernet_nda_api_access_approval(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccernet_nda_api_access_approval",
        "soccernet_access_contract_repair",
        "soccernet_access_blocker_summary",
    ]
