from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccertrack_authenticated_fixture_access_approval as auth_approval


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_source_review_inputs(tmp_path: Path, *, ready: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    review_root = candidate_root / "football_external_soccertrack_fixture_source_access_review_v1"
    _write_json(
        review_root / "fixture_source_access_review_summary.json",
        {
            "batchName": "football_external_soccertrack_fixture_source_access_review",
            "goalAchieved": ready,
            "roadmapAdvanceAllowed": ready,
            "primaryBlocker": None if ready else "football_external_soccertrack_fixture_source_review_not_required",
            "fixtureSourceAccessReviewReady": ready,
            "githubPublicFixtureAvailable": False,
            "huggingFaceAccessible": False,
            "huggingFaceAuthRequired": True,
            "huggingFaceStatusCode": 401,
            "credentialRuntimeAvailable": False,
            "sampleDownloadExecuted": False,
            "datasetDownloadExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationAllowed": False,
            "nextRecommendedNextLever": "football_external_soccertrack_authenticated_fixture_access_approval",
        },
    )
    _write_json(
        review_root / "authenticated_fixture_access_approval_plan.json",
        {
            "approvalRequiredBeforeAuthenticatedAccess": True,
            "huggingFaceAuthRequired": True,
            "allowedFutureScope": "one_match_gsr_bas_mot_fixture_locator_or_fetch_only",
            "sampleDownloadExecuted": False,
            "datasetDownloadExecuted": False,
            "trainingExecuted": False,
        },
    )
    return candidate_root


def test_authenticated_fixture_access_approval_passes_with_runtime_hf_token(tmp_path: Path, monkeypatch) -> None:
    candidate_root = _write_source_review_inputs(tmp_path)
    monkeypatch.setenv("HF_TOKEN", "fake-token")

    payload = auth_approval.run_football_external_soccertrack_authenticated_fixture_access_approval(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccertrack_authenticated_fixture_access_approval_v1"
    contract = json.loads((output_root / "authenticated_fixture_access_approval_contract.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["authenticatedFixtureAccessApproved"] is True
    assert payload["credentialRuntimeAvailable"] is True
    assert payload["credentialPersisted"] is False
    assert payload["sampleDownloadExecuted"] is False
    assert payload["datasetDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_authenticated_fixture_tree_probe"
    assert contract["approvedCredentialEnvVar"] == "HF_TOKEN"
    assert contract["approvedUse"] == "one_match_fixture_tree_probe_only"


def test_authenticated_fixture_access_approval_blocks_without_runtime_credential(tmp_path: Path, monkeypatch) -> None:
    _write_source_review_inputs(tmp_path)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_TOKEN", raising=False)
    monkeypatch.delenv("HUGGING_FACE_HUB_TOKEN", raising=False)

    payload = auth_approval.run_football_external_soccertrack_authenticated_fixture_access_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_authenticated_fixture_credential_missing"
    assert payload["roadmapAdvanceAllowed"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_authenticated_fixture_credential_setup"
    assert payload["sampleDownloadExecuted"] is False


def test_authenticated_fixture_access_approval_blocks_without_source_review(tmp_path: Path) -> None:
    _write_source_review_inputs(tmp_path, ready=False)

    payload = auth_approval.run_football_external_soccertrack_authenticated_fixture_access_approval(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_fixture_source_access_review_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_fixture_source_access_review"


def test_authenticated_fixture_access_approval_contains_three_adaptive_attempts(tmp_path: Path, monkeypatch) -> None:
    _write_source_review_inputs(tmp_path)
    monkeypatch.delenv("HF_TOKEN", raising=False)

    payload = auth_approval.run_football_external_soccertrack_authenticated_fixture_access_approval(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccertrack_authenticated_fixture_access_approval",
        "soccertrack_authenticated_credential_contract_repair",
        "soccertrack_authenticated_access_blocker_summary",
    ]
