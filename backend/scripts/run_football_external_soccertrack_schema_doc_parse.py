from __future__ import annotations

import argparse
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import re
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_FETCH_DIR_NAME = "football_external_soccertrack_schema_doc_fetch_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccertrack_schema_doc_parse_v1"

BLOCKER_FETCH_MISSING = "football_external_soccertrack_schema_doc_fetch_missing"
BLOCKER_PARSE_INSUFFICIENT = "football_external_soccertrack_schema_doc_parse_insufficient"

NEXT_SCHEMA_DOC_FETCH = "football_external_soccertrack_schema_doc_fetch"
NEXT_PARSE_REPAIR = "football_external_soccertrack_schema_doc_parse_repair"
NEXT_SAMPLE_INGESTION_CONTRACT = "football_external_soccertrack_sample_ingestion_contract_prep"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccertrack_schema_doc_parse",
            "successCriteria": [
                "parse fetched SoccerTrack docs into a local adapter schema contract",
                "separate field-level GSR/BAS parse from MOT task-level parse",
                "write next ingestion-contract mapping without downloading samples",
            ],
            "failureAdaptation": "If docs parse incompletely, preserve fetch artifacts and run parser repair.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccertrack_schema_doc_parse_repair",
            "successCriteria": [
                "repair doc parser patterns without expanding fetch or download scope",
                "keep schema-doc provenance as source of truth",
            ],
            "failureAdaptation": "If field extraction remains insufficient, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccertrack_schema_doc_parse_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "preserve no dataset/sample download and no training",
            ],
            "failureAdaptation": "Stop before sample ingestion contract until docs are parseable.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    fetch_root = candidate_root / DEFAULT_FETCH_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "fetchRoot": fetch_root,
        "fetchSummary": _load_json(fetch_root / "schema_doc_fetch_summary.json"),
        "fetchManifest": _load_json(fetch_root / "schema_doc_fetch_manifest.json"),
    }


def _fetch_ready(fetch_summary: dict[str, Any] | None, fetch_manifest: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(fetch_summary, dict)
        and fetch_summary.get("goalAchieved") is True
        and fetch_summary.get("primaryBlocker") is None
        and fetch_summary.get("schemaDocFetchExecuted") is True
        and fetch_summary.get("datasetDownloadExecuted") is False
        and fetch_summary.get("sampleDownloadExecuted") is False
        and fetch_summary.get("trainingExecuted") is False
        and isinstance(fetch_manifest, dict)
        and isinstance(fetch_manifest.get("files"), list)
        and bool(fetch_manifest.get("files"))
    )


def _manifest_files(fetch_manifest: dict[str, Any] | None) -> list[dict[str, Any]]:
    raw = (fetch_manifest or {}).get("files")
    if not isinstance(raw, list):
        return []
    return [row for row in raw if isinstance(row, dict)]


def _read_docs(fetch_root: Path, files: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    docs: dict[str, dict[str, Any]] = {}
    for row in files:
        source_path = str(row.get("sourcePath") or "")
        relative_path = str(row.get("relativePath") or "")
        local_path = fetch_root / relative_path
        if not source_path or not relative_path or not local_path.exists():
            continue
        docs[source_path] = {
            "sourcePath": source_path,
            "relativePath": relative_path,
            "text": local_path.read_text(encoding="utf-8", errors="replace"),
        }
    return docs


def _extract_markdown_table_fields(text: str) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "`" not in stripped:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 3 or cells[0].lower() in {"field", "---"}:
            continue
        names = re.findall(r"`([^`]+)`", cells[0])
        if not names:
            continue
        split_names: list[str] = []
        for name in names:
            parts = [part.strip() for part in name.split(",")]
            split_names.extend(part for part in parts if part)
        for name in split_names:
            if name in seen:
                continue
            seen.add(name)
            fields.append(
                {
                    "name": name,
                    "type": cells[1] if len(cells) > 1 else "",
                    "required": cells[2] if len(cells) > 2 else "",
                    "description": cells[3] if len(cells) > 3 else "",
                }
            )
    return fields


def _strip_html(text: str) -> str:
    text = re.sub(r"<script\b.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def _extract_html_code_fields(text: str) -> list[str]:
    fields: list[str] = []
    seen: set[str] = set()
    for field in re.findall(r"<code>(.*?)</code>", text, flags=re.IGNORECASE | re.DOTALL):
        clean = html.unescape(re.sub(r"<[^>]+>", "", field)).strip()
        if "\n" in clean or len(clean) > 80:
            continue
        if clean and clean not in seen and not clean.endswith(".mp4"):
            seen.add(clean)
            fields.append(clean)
    return fields


def _parse_gsr_doc(doc: dict[str, Any] | None) -> dict[str, Any]:
    text = str((doc or {}).get("text") or "")
    fields = _extract_markdown_table_fields(text)
    field_names = [field["name"] for field in fields]
    return {
        "schemaVersion": "soccertrack_gsr_schema_parse_audit_v1",
        "taskId": "gsr",
        "sourcePath": (doc or {}).get("sourcePath"),
        "fieldLevelParsed": {"image_id", "track_id", "x", "y"}.issubset(set(field_names)),
        "parsedFieldCount": len(field_names),
        "parsedFieldNames": field_names,
        "fields": fields,
        "frameRateFps": 25 if "25 fps" in text.lower() else None,
        "pitchCoordinateSystemDetected": "pitch" in text.lower() and "metres" in text.lower(),
        "pitchDimensionsMeters": {"length": 105, "width": 68} if "105" in text and "68" in text else None,
        "timeAlignmentRule": "image_id = round(position_ms / 40)" if "round" in text and "/ 40" in text else None,
        "datasetDownloadExecuted": False,
        "sampleDownloadExecuted": False,
        "trainingExecuted": False,
    }


def _parse_bas_doc(doc: dict[str, Any] | None) -> dict[str, Any]:
    text = str((doc or {}).get("text") or "")
    fields = _extract_markdown_table_fields(text)
    field_names = [field["name"] for field in fields]
    label_candidates = [
        "Pass",
        "Drive",
        "Header",
        "High Pass",
        "Out",
        "Cross",
        "Throw In",
        "Shot",
        "Ball Player Block",
        "Player Successful Tackle",
        "Free Kick",
        "Goal",
    ]
    labels = [label for label in label_candidates if label in text]
    return {
        "schemaVersion": "soccertrack_bas_schema_parse_audit_v1",
        "taskId": "bas",
        "sourcePath": (doc or {}).get("sourcePath"),
        "fieldLevelParsed": {"gameTime", "position", "label", "team"}.issubset(set(field_names)),
        "parsedFieldCount": len(field_names),
        "parsedFieldNames": field_names,
        "fields": fields,
        "labelSet": labels,
        "labelSetComplete": len(labels) == 12,
        "frameRateFps": 25 if "25 fps" in text.lower() else None,
        "timeAlignmentRule": "image_id = round(position_ms / 40)" if "round" in text and "/ 40" in text else None,
        "datasetDownloadExecuted": False,
        "sampleDownloadExecuted": False,
        "trainingExecuted": False,
    }


def _parse_mot_doc(doc: dict[str, Any] | None) -> dict[str, Any]:
    text = str((doc or {}).get("text") or "")
    plain = _strip_html(text)
    code_fields = _extract_html_code_fields(text)
    task_level = "multi-object tracking" in plain.lower() or "bounding boxes" in plain.lower()
    return {
        "schemaVersion": "soccertrack_mot_schema_parse_audit_v1",
        "taskId": "mot",
        "sourcePath": (doc or {}).get("sourcePath"),
        "taskLevelParsed": task_level,
        "fieldLevelParsed": False,
        "fieldLevelParseNote": "MOT was fetched as a task page, not a dedicated format contract; parsed code fields are advisory until sample fixture materialization.",
        "parsedFieldCount": len(code_fields),
        "parsedFieldNames": code_fields,
        "inputSummary": "panoramic full-match video" if "panoramic" in plain.lower() else None,
        "outputSummary": "per-frame bounding boxes plus persistent track IDs" if "bounding boxes" in plain.lower() else None,
        "datasetDownloadExecuted": False,
        "sampleDownloadExecuted": False,
        "trainingExecuted": False,
    }


def _build_contract(gsr: dict[str, Any], bas: dict[str, Any], mot: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "soccertrack_parsed_schema_contract_v1",
        "generatedAt": _utc_now_iso(),
        "contractSource": "fetched_schema_docs_only",
        "taskContracts": {
            "gsr": {
                "sourcePath": gsr.get("sourcePath"),
                "recordShape": "per_entity_per_frame_flat_json_object",
                "requiredFields": [field["name"] for field in gsr.get("fields", []) if str(field.get("required")).lower() == "yes"],
                "allParsedFields": gsr.get("parsedFieldNames", []),
                "coordinateSystem": "pitch_metres_center_origin",
                "frameRateFps": gsr.get("frameRateFps"),
            },
            "bas": {
                "sourcePath": bas.get("sourcePath"),
                "recordShape": "top_level_annotations_array",
                "requiredFields": [field["name"] for field in bas.get("fields", []) if str(field.get("required")).lower() == "yes"],
                "allParsedFields": bas.get("parsedFieldNames", []),
                "labelSet": bas.get("labelSet", []),
                "frameRateFps": bas.get("frameRateFps"),
            },
            "mot": {
                "sourcePath": mot.get("sourcePath"),
                "recordShape": "task_level_mot_bounding_box_tracks",
                "allParsedFields": mot.get("parsedFieldNames", []),
                "taskLevelParsed": mot.get("taskLevelParsed"),
            },
        },
        "requiredAdapterSchemaNames": [
            "FrameState",
            "GameState",
            "TrackFrame",
            "TrackedEntity",
            "BallActionEvent",
            "EventStream",
        ],
        "datasetDownloadExecuted": False,
        "sampleDownloadExecuted": False,
        "trainingExecuted": False,
    }


def _mapping_plan(gsr: dict[str, Any], bas: dict[str, Any], mot: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "soccertrack_sample_adapter_mapping_plan_v1",
        "generatedAt": _utc_now_iso(),
        "nextRequiredArtifact": "soccertrack_sample_fixture_materialization_plan",
        "mappingRows": [
            {"taskId": "gsr", "sourceField": "image_id", "targetField": "FrameState.frameIndex"},
            {"taskId": "gsr", "sourceField": "track_id", "targetField": "TrackedEntity.trackId"},
            {"taskId": "gsr", "sourceField": "x,y", "targetField": "TrackedEntity.pitchPositionMeters"},
            {"taskId": "gsr", "sourceField": "bbox_image", "targetField": "TrackedEntity.imageBboxXywh"},
            {"taskId": "bas", "sourceField": "gameTime,position", "targetField": "BallActionEvent.timestampMs"},
            {"taskId": "bas", "sourceField": "label", "targetField": "BallActionEvent.label"},
            {"taskId": "bas", "sourceField": "team", "targetField": "BallActionEvent.teamSide"},
            {"taskId": "mot", "sourceField": "frame,bbox,player_id", "targetField": "TrackFrame.entities"},
        ],
        "parseReadiness": {
            "gsrFieldLevelParsed": gsr.get("fieldLevelParsed") is True,
            "basFieldLevelParsed": bas.get("fieldLevelParsed") is True,
            "motTaskLevelParsed": mot.get("taskLevelParsed") is True,
        },
        "sampleDownloadApproved": False,
        "sampleDownloadExecuted": False,
        "datasetDownloadExecuted": False,
        "trainingExecuted": False,
    }


def _classify(fetch_ready: bool, gsr: dict[str, Any], bas: dict[str, Any], mot: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not fetch_ready:
        return (
            BLOCKER_FETCH_MISSING,
            NEXT_SCHEMA_DOC_FETCH,
            False,
            "SoccerTrack schema-doc fetch truth is missing or failed; fetch approved schema docs before parsing.",
        )
    enough = gsr.get("fieldLevelParsed") is True and bas.get("fieldLevelParsed") is True and mot.get("taskLevelParsed") is True
    if not enough:
        return (
            BLOCKER_PARSE_INSUFFICIENT,
            NEXT_PARSE_REPAIR,
            False,
            "Fetched SoccerTrack docs were not parseable enough for a sample ingestion contract; repair parser patterns before sample work.",
        )
    return (
        None,
        NEXT_SAMPLE_INGESTION_CONTRACT,
        True,
        "SoccerTrack schema docs parsed into a bounded adapter contract. Advance to sample ingestion contract prep; no samples, datasets, training, promotion, or runtime mutation were executed.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "schema_doc_fetch_missing", "selected": primary_blocker == BLOCKER_FETCH_MISSING, "primaryBlocker": BLOCKER_FETCH_MISSING, "nextRecommendedNextLever": NEXT_SCHEMA_DOC_FETCH},
            {"condition": "schema_doc_parse_insufficient", "selected": primary_blocker == BLOCKER_PARSE_INSUFFICIENT, "primaryBlocker": BLOCKER_PARSE_INSUFFICIENT, "nextRecommendedNextLever": NEXT_PARSE_REPAIR},
            {"condition": "schema_doc_parse_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_SAMPLE_INGESTION_CONTRACT},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerTrack Schema Doc Parse",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Parsed task IDs: `{summary.get('parsedTaskIds')}`",
            f"- Field-level parsed task IDs: `{summary.get('fieldLevelParsedTaskIds')}`",
            f"- Dataset download executed: `{summary.get('datasetDownloadExecuted')}`",
            f"- Sample download executed: `{summary.get('sampleDownloadExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation allowed: `{summary.get('runtimeDefaultMutationAllowed')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccertrack_schema_doc_parse(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccertrack_schema_doc_parse",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    fetch_ready = _fetch_ready(inputs.get("fetchSummary"), inputs.get("fetchManifest"))
    docs = _read_docs(inputs["fetchRoot"], _manifest_files(inputs.get("fetchManifest"))) if fetch_ready else {}
    gsr = _parse_gsr_doc(docs.get("docs/format-gsr.md"))
    bas = _parse_bas_doc(docs.get("docs/format-bas.md"))
    mot = _parse_mot_doc(docs.get("docs/task-mot.html"))
    primary_blocker, next_lever, goal_achieved, english = _classify(fetch_ready, gsr, bas, mot)
    parsed_task_ids = [task_id for task_id, audit in [("gsr", gsr), ("bas", bas), ("mot", mot)] if audit.get("fieldLevelParsed") is True or audit.get("taskLevelParsed") is True]
    field_level_task_ids = [task_id for task_id, audit in [("gsr", gsr), ("bas", bas), ("mot", mot)] if audit.get("fieldLevelParsed") is True]
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    contract = _build_contract(gsr, bas, mot)
    mapping_plan = _mapping_plan(gsr, bas, mot)
    decision_matrix = _decision_matrix(primary_blocker, goal_achieved)
    summary: dict[str, Any] = {
        "batchName": "football_external_soccertrack_schema_doc_parse",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccertrack_schema_doc_fetch",
        "schemaDocParseReady": goal_achieved,
        "parsedTaskIds": parsed_task_ids,
        "fieldLevelParsedTaskIds": field_level_task_ids,
        "gsrParsedFieldCount": gsr.get("parsedFieldCount", 0),
        "basParsedFieldCount": bas.get("parsedFieldCount", 0),
        "motParsedFieldCount": mot.get("parsedFieldCount", 0),
        "schemaDocFetchExecuted": fetch_ready,
        "schemaDocParseExecuted": fetch_ready,
        "datasetDownloadAllowedByThisBatch": False,
        "datasetDownloadExecuted": False,
        "sampleDownloadApproved": False,
        "sampleDownloadExecuted": False,
        "fullDatasetDownloadExecuted": False,
        "trainingAllowed": False,
        "trainingExecuted": False,
        "promotionReady": False,
        "candidateReadyForEvaluation": False,
        "runtimeDefaultMutationAllowed": False,
        "runtimeDefaultMutationExecuted": False,
        "promotionMutationExecuted": False,
        "candidateEvaluationExecuted": False,
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    batch_outcome = {
        "summary": summary,
        "soccertrackParsedSchemaContract": contract,
        "gsrSchemaParseAudit": gsr,
        "basSchemaParseAudit": bas,
        "motSchemaParseAudit": mot,
        "sampleAdapterMappingPlan": mapping_plan,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "schema_doc_parse_summary.json", summary)
    _write_json(output_root / "soccertrack_parsed_schema_contract.json", contract)
    _write_json(output_root / "gsr_schema_parse_audit.json", gsr)
    _write_json(output_root / "bas_schema_parse_audit.json", bas)
    _write_json(output_root / "mot_schema_parse_audit.json", mot)
    _write_json(output_root / "sample_adapter_mapping_plan.json", mapping_plan)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse fetched SoccerTrack schema docs into a bounded adapter contract.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccertrack_schema_doc_parse")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccertrack_schema_doc_parse(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
