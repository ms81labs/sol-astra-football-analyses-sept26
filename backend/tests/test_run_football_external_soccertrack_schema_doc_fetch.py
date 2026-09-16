from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccertrack_schema_doc_fetch as fetch_batch


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_approval_inputs(
    tmp_path: Path,
    *,
    approved: bool = True,
    paths: list[str] | None = None,
) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    approval_root = candidate_root / "football_external_soccertrack_schema_doc_fetch_approval_v1"
    doc_paths = paths or [
        "docs/format-gsr.md",
        "docs/format-bas.md",
        "docs/task-gsr.html",
        "docs/task-bas.html",
        "docs/task-mot.html",
    ]
    _write_json(
        approval_root / "schema_doc_fetch_approval_summary.json",
        {
            "batchName": "football_external_soccertrack_schema_doc_fetch_approval",
            "goalAchieved": approved,
            "roadmapAdvanceAllowed": approved,
            "primaryBlocker": None if approved else "football_external_soccertrack_schema_doc_path_unsafe",
            "schemaDocFetchApproved": approved,
            "schemaDocApprovedPathCount": len(doc_paths) if approved else 0,
            "schemaDocFetchExecuted": False,
            "datasetDownloadExecuted": False,
            "sampleDownloadExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationAllowed": False,
            "nextRecommendedNextLever": "football_external_soccertrack_schema_doc_fetch",
        },
    )
    _write_json(
        approval_root / "schema_doc_fetch_approval_contract.json",
        {
            "schemaVersion": "soccertrack_schema_doc_fetch_approval_contract_v1",
            "selectedResourceId": "soccertrack_v2",
            "sourceRepositoryUrl": "https://github.com/AtomScott/SoccerTrack-v2",
            "approvedFetchScope": "schema_docs_only" if approved else None,
            "schemaDocFetchApproved": approved,
            "schemaDocFetchExecuted": False,
            "schemaDocPaths": doc_paths,
            "sampleDownloadApproved": False,
            "sampleDownloadExecuted": False,
            "datasetDownloadApproved": False,
            "datasetDownloadExecuted": False,
            "trainingUseApproved": False,
        },
    )
    return candidate_root


def _fake_fetcher(url: str) -> bytes:
    return f"# fixture\nsource={url}\nfield: frameIndex\nfield: timestampMs\n".encode("utf-8")


def test_schema_doc_fetch_downloads_only_approved_docs_with_hashes(tmp_path: Path) -> None:
    candidate_root = _write_approval_inputs(tmp_path)

    payload = fetch_batch.run_football_external_soccertrack_schema_doc_fetch(
        storage_root=tmp_path,
        fetcher=_fake_fetcher,
    )

    output_root = candidate_root / "football_external_soccertrack_schema_doc_fetch_v1"
    manifest = json.loads((output_root / "schema_doc_fetch_manifest.json").read_text(encoding="utf-8"))
    provenance = json.loads((output_root / "schema_doc_fetch_provenance_audit.json").read_text(encoding="utf-8"))
    inventory = json.loads((output_root / "schema_doc_content_inventory.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["schemaDocFetchExecuted"] is True
    assert payload["fetchedSchemaDocCount"] == 5
    assert payload["datasetDownloadExecuted"] is False
    assert payload["sampleDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_schema_doc_parse"
    assert len(manifest["files"]) == 5
    assert all(row["relativePath"].startswith("schema_docs/") for row in manifest["files"])
    assert provenance["fetchFailureCount"] == 0
    assert len(provenance["sha256ByPath"]) == 5
    assert inventory["schemaDocContentInventoryReady"] is True
    assert inventory["fieldMentionCount"] >= 5


def test_schema_doc_fetch_blocks_without_approval(tmp_path: Path) -> None:
    _write_approval_inputs(tmp_path, approved=False)

    payload = fetch_batch.run_football_external_soccertrack_schema_doc_fetch(
        storage_root=tmp_path,
        fetcher=_fake_fetcher,
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_schema_doc_fetch_approval_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_schema_doc_fetch_approval"
    assert payload["schemaDocFetchExecuted"] is False


def test_schema_doc_fetch_blocks_on_fetch_failure(tmp_path: Path) -> None:
    _write_approval_inputs(tmp_path, paths=["docs/format-gsr.md"])

    def failing_fetcher(url: str) -> bytes:
        raise RuntimeError(f"boom {url}")

    payload = fetch_batch.run_football_external_soccertrack_schema_doc_fetch(
        storage_root=tmp_path,
        fetcher=failing_fetcher,
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_schema_doc_fetch_failed"
    assert payload["fetchedSchemaDocCount"] == 0
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_schema_doc_fetch_approval"


def test_schema_doc_fetch_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_approval_inputs(tmp_path)

    payload = fetch_batch.run_football_external_soccertrack_schema_doc_fetch(
        storage_root=tmp_path,
        fetcher=_fake_fetcher,
    )

    assert payload["attemptPlanFamilies"] == [
        "soccertrack_schema_doc_fetch",
        "soccertrack_schema_doc_fetch_repair",
        "soccertrack_schema_doc_fetch_blocker_summary",
    ]
