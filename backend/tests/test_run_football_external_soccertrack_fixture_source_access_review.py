from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccertrack_fixture_source_access_review as access_review


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_fetch_blocker_inputs(tmp_path: Path, *, blocker: str | None = "football_external_soccertrack_public_fixture_files_missing") -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    fetch_root = candidate_root / "football_external_soccertrack_controlled_sample_fetch_v1"
    _write_json(
        fetch_root / "controlled_sample_fetch_summary.json",
        {
            "batchName": "football_external_soccertrack_controlled_sample_fetch",
            "goalAchieved": blocker is None,
            "roadmapAdvanceAllowed": blocker is None,
            "primaryBlocker": blocker,
            "sourceTreeProbeExecuted": True,
            "completeOneMatchFixtureFound": False,
            "controlledSampleFetchExecuted": False,
            "downloadedFixtureFileCount": 0,
            "sampleDownloadExecuted": False,
            "datasetDownloadExecuted": False,
            "fullDatasetDownloadExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationAllowed": False,
            "nextRecommendedNextLever": "football_external_soccertrack_fixture_source_access_review",
        },
    )
    _write_json(
        fetch_root / "source_tree_fixture_audit.json",
        {
            "sourceRepositoryUrl": "https://github.com/AtomScott/SoccerTrack-v2",
            "completeOneMatchFixtureFound": False,
            "fixtureLikeRowCount": 0,
            "datasetDownloadExecuted": False,
            "trainingExecuted": False,
        },
    )
    return candidate_root


def test_fixture_source_access_review_routes_to_authenticated_fixture_access_when_hf_is_gated(tmp_path: Path) -> None:
    candidate_root = _write_fetch_blocker_inputs(tmp_path)

    payload = access_review.run_football_external_soccertrack_fixture_source_access_review(
        storage_root=tmp_path,
        hf_probe=lambda: {"statusCode": 401, "accessible": False, "authRequired": True},
    )

    output_root = candidate_root / "football_external_soccertrack_fixture_source_access_review_v1"
    source_matrix = json.loads((output_root / "fixture_source_access_matrix.json").read_text(encoding="utf-8"))
    credential_audit = json.loads((output_root / "credential_availability_audit.json").read_text(encoding="utf-8"))
    approval_plan = json.loads((output_root / "authenticated_fixture_access_approval_plan.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["fixtureSourceAccessReviewReady"] is True
    assert payload["githubPublicFixtureAvailable"] is False
    assert payload["huggingFaceAuthRequired"] is True
    assert payload["credentialRuntimeAvailable"] is False
    assert payload["sampleDownloadExecuted"] is False
    assert payload["datasetDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_authenticated_fixture_access_approval"
    assert source_matrix["recommendedAccessFamily"] == "authenticated_huggingface_or_google_drive_fixture_access"
    assert credential_audit["credentialRuntimeAvailable"] is False
    assert approval_plan["approvalRequiredBeforeAuthenticatedAccess"] is True


def test_fixture_source_access_review_blocks_without_controlled_fetch_truth(tmp_path: Path) -> None:
    _write_fetch_blocker_inputs(tmp_path, blocker=None)

    payload = access_review.run_football_external_soccertrack_fixture_source_access_review(
        storage_root=tmp_path,
        hf_probe=lambda: {"statusCode": 401, "accessible": False, "authRequired": True},
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_fixture_source_review_not_required"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_controlled_sample_fetch"


def test_fixture_source_access_review_can_route_to_public_hf_fixture_probe(tmp_path: Path) -> None:
    _write_fetch_blocker_inputs(tmp_path)

    payload = access_review.run_football_external_soccertrack_fixture_source_access_review(
        storage_root=tmp_path,
        hf_probe=lambda: {"statusCode": 200, "accessible": True, "authRequired": False, "siblingCount": 4},
    )

    assert payload["goalAchieved"] is True
    assert payload["huggingFaceAuthRequired"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_huggingface_fixture_tree_probe"


def test_fixture_source_access_review_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_fetch_blocker_inputs(tmp_path)

    payload = access_review.run_football_external_soccertrack_fixture_source_access_review(
        storage_root=tmp_path,
        hf_probe=lambda: {"statusCode": 401, "accessible": False, "authRequired": True},
    )

    assert payload["attemptPlanFamilies"] == [
        "soccertrack_fixture_source_access_review",
        "soccertrack_fixture_source_locator_repair",
        "soccertrack_fixture_access_blocker_summary",
    ]
