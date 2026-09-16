from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_football_external_soccertrack_schema_doc_parse as schema_parse


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_fetch_inputs(tmp_path: Path, *, fetched: bool = True, docs_have_fields: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    fetch_root = candidate_root / "football_external_soccertrack_schema_doc_fetch_v1"
    docs_root = fetch_root / "schema_docs"
    docs_root.mkdir(parents=True, exist_ok=True)

    gsr_text = (
        """
# GSR annotation format
| Field | Type | Required | Description |
|---|---|---|---|
| `image_id` | integer | yes | Zero-indexed frame number. |
| `track_id` | integer | yes | Per-half track identifier. |
| `player_id` | string or integer or null | no | Stable player id. |
| `role` | string | yes | player, goalkeeper, referee, other. |
| `jersey_number` | integer or null | yes | Visible jersey number. |
| `team_side` | string or null | yes | left or right. |
| `x`, `y` | float | yes | Player position on the pitch, in metres. |
| `bbox_image` | `[x, y, w, h]` of ints | no | Bounding box in image pixels. |
| `bbox_pitch` | `[x, y, w, h]` of floats | no | Bounding box projected to pitch plane. |
25 fps. Pitch dimensions 105 m × 68 m. image_id = round(t_ms / 40).
"""
        if docs_have_fields
        else "# GSR annotation format\nNo field table here.\n"
    )
    bas_text = (
        """
# BAS annotation format
| Field | Type | Required | Description |
|---|---|---|---|
| `gameTime` | string | yes | Format <half> - <mm:ss>. |
| `position` | string of integer ms | yes | Milliseconds from kickoff. |
| `label` | string | yes | One of the 12 classes. |
| `team` | string | yes | left or right. |
| `player_id` | string or integer or null | no | Actor player ID. |
| `visibility` | string | no | visible or not shown. |
| `Pass` | semantic | n/a | Intentional ground pass. |
| `Drive` | semantic | n/a | Player carries the ball. |
| `Shot` | semantic | n/a | Attempt on goal. |
Video frame rate for alignment: 25 fps.
"""
        if docs_have_fields
        else "# BAS annotation format\nNo field table here.\n"
    )
    mot_text = (
        """
<h1>Multi-Object Tracking</h1>
<strong>Output:</strong> Per-frame bounding boxes + persistent track IDs for all players
<td><code>frame</code></td><td>int</td>
<td><code>player_id</code></td><td>int</td>
<td><code>bbox</code></td><td>[x,y,w,h]</td>
"""
        if docs_have_fields
        else "<h1>Multi-Object Tracking</h1>"
    )

    files = [
        ("docs/format-gsr.md", "schema_docs/docs__format-gsr.md", gsr_text),
        ("docs/format-bas.md", "schema_docs/docs__format-bas.md", bas_text),
        ("docs/task-mot.html", "schema_docs/docs__task-mot.html", mot_text),
    ]
    manifest_files: list[dict[str, object]] = []
    for source_path, relative_path, text in files:
        if fetched:
            (fetch_root / relative_path).write_text(text, encoding="utf-8")
        manifest_files.append(
            {
                "sourcePath": source_path,
                "relativePath": relative_path,
                "sizeBytes": len(text.encode("utf-8")),
                "sha256": "fixture",
            }
        )

    _write_json(
        fetch_root / "schema_doc_fetch_summary.json",
        {
            "batchName": "football_external_soccertrack_schema_doc_fetch",
            "goalAchieved": fetched,
            "roadmapAdvanceAllowed": fetched,
            "primaryBlocker": None if fetched else "football_external_soccertrack_schema_doc_fetch_failed",
            "schemaDocFetchExecuted": fetched,
            "fetchedSchemaDocCount": len(files) if fetched else 0,
            "fetchFailureCount": 0 if fetched else len(files),
            "datasetDownloadExecuted": False,
            "sampleDownloadExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationAllowed": False,
            "nextRecommendedNextLever": "football_external_soccertrack_schema_doc_parse",
        },
    )
    _write_json(
        fetch_root / "schema_doc_fetch_manifest.json",
        {
            "schemaVersion": "soccertrack_schema_doc_fetch_manifest_v1",
            "files": manifest_files if fetched else [],
            "datasetDownloadExecuted": False,
            "sampleDownloadExecuted": False,
            "trainingExecuted": False,
        },
    )
    return candidate_root


def test_schema_doc_parse_extracts_gsr_bas_and_mot_contract_without_downloads(tmp_path: Path) -> None:
    candidate_root = _write_fetch_inputs(tmp_path)

    payload = schema_parse.run_football_external_soccertrack_schema_doc_parse(storage_root=tmp_path)

    output_root = candidate_root / "football_external_soccertrack_schema_doc_parse_v1"
    contract = json.loads((output_root / "soccertrack_parsed_schema_contract.json").read_text(encoding="utf-8"))
    mapping = json.loads((output_root / "sample_adapter_mapping_plan.json").read_text(encoding="utf-8"))
    gsr_audit = json.loads((output_root / "gsr_schema_parse_audit.json").read_text(encoding="utf-8"))
    bas_audit = json.loads((output_root / "bas_schema_parse_audit.json").read_text(encoding="utf-8"))
    mot_audit = json.loads((output_root / "mot_schema_parse_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["schemaDocParseReady"] is True
    assert payload["parsedTaskIds"] == ["gsr", "bas", "mot"]
    assert payload["fieldLevelParsedTaskIds"] == ["gsr", "bas"]
    assert payload["datasetDownloadExecuted"] is False
    assert payload["sampleDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False
    assert payload["candidateReadyForEvaluation"] is False
    assert payload["runtimeDefaultMutationAllowed"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_sample_ingestion_contract_prep"
    assert "FrameState" in contract["requiredAdapterSchemaNames"]
    assert "BallActionEvent" in contract["requiredAdapterSchemaNames"]
    assert "TrackFrame" in contract["requiredAdapterSchemaNames"]
    assert "image_id" in gsr_audit["parsedFieldNames"]
    assert "bbox_image" in gsr_audit["parsedFieldNames"]
    assert "gameTime" in bas_audit["parsedFieldNames"]
    assert "Shot" in bas_audit["labelSet"]
    assert mot_audit["taskLevelParsed"] is True
    assert mapping["nextRequiredArtifact"] == "soccertrack_sample_fixture_materialization_plan"


def test_schema_doc_parse_blocks_without_fetch_truth(tmp_path: Path) -> None:
    _write_fetch_inputs(tmp_path, fetched=False)

    payload = schema_parse.run_football_external_soccertrack_schema_doc_parse(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_schema_doc_fetch_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_schema_doc_fetch"
    assert payload["datasetDownloadExecuted"] is False
    assert payload["trainingExecuted"] is False


def test_schema_doc_parse_blocks_when_docs_do_not_expose_fields(tmp_path: Path) -> None:
    _write_fetch_inputs(tmp_path, docs_have_fields=False)

    payload = schema_parse.run_football_external_soccertrack_schema_doc_parse(storage_root=tmp_path)

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccertrack_schema_doc_parse_insufficient"
    assert payload["nextRecommendedNextLever"] == "football_external_soccertrack_schema_doc_parse_repair"


def test_schema_doc_parse_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_fetch_inputs(tmp_path)

    payload = schema_parse.run_football_external_soccertrack_schema_doc_parse(storage_root=tmp_path)

    assert payload["attemptPlanFamilies"] == [
        "soccertrack_schema_doc_parse",
        "soccertrack_schema_doc_parse_repair",
        "soccertrack_schema_doc_parse_blocker_summary",
    ]
