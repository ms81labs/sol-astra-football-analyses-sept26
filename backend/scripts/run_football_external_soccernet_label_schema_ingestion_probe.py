from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_EXTRACT_DIR_NAME = "football_external_soccernet_zip_label_member_extract_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_label_schema_ingestion_probe_v1"

BLOCKER_EXTRACT_MISSING = "football_external_soccernet_label_extract_missing"
BLOCKER_SCHEMA_MALFORMED = "football_external_soccernet_label_schema_malformed"

NEXT_EXTRACT = "football_external_soccernet_zip_label_member_extract"
NEXT_SCHEMA_REPAIR = "football_external_soccernet_label_schema_contract_repair"
NEXT_FIXTURE = "football_external_soccernet_event_adapter_fixture_materialization"

REQUIRED_ANNOTATION_FIELDS = ["gameTime", "label", "position", "team", "visibility"]



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_label_schema_ingestion_probe",
            "successCriteria": [
                "load extracted SoccerNet label JSON",
                "validate required annotation fields and parseable temporal positions",
                "write adapter mapping plan without training or video download",
            ],
            "failureAdaptation": "If schema is malformed, repair the label schema contract.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_label_schema_contract_repair",
            "successCriteria": [
                "normalize field names and parse rules",
                "preserve source label file as read-only truth",
            ],
            "failureAdaptation": "If fields remain ambiguous, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_label_schema_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "avoid model training or runtime mutation",
            ],
            "failureAdaptation": "Stop before fixture materialization.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    extract_root = candidate_root / DEFAULT_EXTRACT_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "extractRoot": extract_root,
        "extractSummary": _load_json(extract_root / "zip_label_member_extract_summary.json"),
        "extractedInventory": _load_json(extract_root / "extracted_label_inventory.json"),
    }


def _extract_ready(summary: dict[str, Any] | None, inventory: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and int(summary.get("downloadedLabelFileCount") or 0) > 0
        and summary.get("labelJsonParseSucceeded") is True
        and summary.get("archiveDownloadExecuted") is False
        and summary.get("videoMemberDownloadExecuted") is False
        and summary.get("trainingExecuted") is False
        and isinstance(inventory, dict)
        and int(inventory.get("extractedLabelFileCount") or 0) > 0
    )


def _load_label_payloads(extract_root: Path, inventory: dict[str, Any] | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    files = (inventory or {}).get("extractedLabelFiles")
    if not isinstance(files, list):
        return [], [{"error": "extractedLabelFiles missing"}]
    payloads = []
    errors = []
    for row in files:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("relativePath") or "")
        path = extract_root / rel
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            errors.append({"relativePath": rel, "error": str(exc)})
            continue
        payloads.append({"relativePath": rel, "memberPath": row.get("memberPath"), "payload": payload})
    return payloads, errors


def _parse_game_time(value: Any) -> dict[str, Any]:
    text = str(value)
    if " - " not in text or ":" not in text:
        return {"parsed": False, "raw": text}
    half_text, clock = text.split(" - ", 1)
    minute_text, second_text = clock.split(":", 1)
    try:
        half = int(half_text)
        minute = int(minute_text)
        second = int(second_text)
    except ValueError:
        return {"parsed": False, "raw": text}
    return {"parsed": True, "raw": text, "half": half, "minute": minute, "second": second, "secondsInHalf": minute * 60 + second}


def _schema_audit(payloads: list[dict[str, Any]], load_errors: list[dict[str, Any]]) -> dict[str, Any]:
    annotation_rows: list[dict[str, Any]] = []
    top_level_keys: set[str] = set()
    malformed_count = 0
    parseable_position_count = 0
    parseable_game_time_count = 0
    for wrapper in payloads:
        payload = wrapper.get("payload")
        if isinstance(payload, dict):
            top_level_keys.update(payload.keys())
            annotations = payload.get("annotations") or payload.get("Annotations")
            if isinstance(annotations, list):
                for annotation in annotations:
                    if isinstance(annotation, dict):
                        annotation_rows.append(annotation)
            else:
                malformed_count += 1
    missing_field_rows = []
    for index, annotation in enumerate(annotation_rows):
        missing = [field for field in REQUIRED_ANNOTATION_FIELDS if field not in annotation]
        if missing:
            missing_field_rows.append({"annotationIndex": index, "missingFields": missing})
        try:
            int(str(annotation.get("position")))
            parseable_position_count += 1
        except (TypeError, ValueError):
            pass
        if _parse_game_time(annotation.get("gameTime")).get("parsed"):
            parseable_game_time_count += 1
    required_present = bool(annotation_rows) and not missing_field_rows
    return {
        "labelFileCount": len(payloads),
        "loadErrorCount": len(load_errors),
        "loadErrors": load_errors,
        "topLevelKeys": sorted(top_level_keys),
        "requiredAnnotationFields": REQUIRED_ANNOTATION_FIELDS,
        "annotationCount": len(annotation_rows),
        "malformedPayloadCount": malformed_count,
        "missingRequiredFieldRowCount": len(missing_field_rows),
        "missingRequiredFieldRowsSample": missing_field_rows[:20],
        "requiredAnnotationFieldsPresent": required_present,
        "parseablePositionCount": parseable_position_count,
        "parseableGameTimeCount": parseable_game_time_count,
        "positionParseRate": (parseable_position_count / len(annotation_rows)) if annotation_rows else 0.0,
        "gameTimeParseRate": (parseable_game_time_count / len(annotation_rows)) if annotation_rows else 0.0,
    }


def _annotation_rows(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for wrapper in payloads:
        payload = wrapper.get("payload")
        annotations = payload.get("annotations") if isinstance(payload, dict) else None
        if isinstance(annotations, list):
            rows.extend([row for row in annotations if isinstance(row, dict)])
    return rows


def _event_taxonomy_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels = Counter(str(row.get("label") or "<missing>") for row in rows)
    teams = Counter(str(row.get("team") or "<missing>") for row in rows)
    visibility = Counter(str(row.get("visibility") or "<missing>") for row in rows)
    return {
        "distinctLabelCount": len(labels),
        "labelCounts": dict(sorted(labels.items())),
        "teamCounts": dict(sorted(teams.items())),
        "visibilityCounts": dict(sorted(visibility.items())),
    }


def _temporal_coverage_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_half: dict[int, list[int]] = {}
    positions = []
    for row in rows:
        parsed = _parse_game_time(row.get("gameTime"))
        if parsed.get("parsed"):
            by_half.setdefault(int(parsed["half"]), []).append(int(parsed["secondsInHalf"]))
        try:
            positions.append(int(str(row.get("position"))))
        except (TypeError, ValueError):
            pass
    return {
        "halfCoverageSeconds": {
            str(half): {"min": min(values), "max": max(values), "count": len(values)}
            for half, values in sorted(by_half.items())
            if values
        },
        "positionMsMin": min(positions) if positions else None,
        "positionMsMax": max(positions) if positions else None,
        "positionCount": len(positions),
    }


def _mapping_plan(schema: dict[str, Any], taxonomy: dict[str, Any]) -> dict[str, Any]:
    ready = bool(
        schema.get("requiredAnnotationFieldsPresent")
        and schema.get("positionParseRate") == 1.0
        and schema.get("gameTimeParseRate") == 1.0
    )
    return {
        "adapterName": "soccernet_ball_action_spotting_event_adapter",
        "sourceDataset": "SoccerNet SN-BAS-2025",
        "sourceLabelFileKind": "Labels-ball.json",
        "adapterReadyForFixtureMaterialization": ready,
        "fieldMapping": {
            "eventTimeMs": "int(annotation.position)",
            "period": "parse annotation.gameTime before separator",
            "clock": "parse annotation.gameTime after separator",
            "eventType": "annotation.label",
            "team": "annotation.team",
            "visibility": "annotation.visibility",
        },
        "distinctLabelCount": taxonomy.get("distinctLabelCount"),
        "trainingUseAllowed": False,
    }


def _classify(extract_ready: bool, schema: dict[str, Any], mapping: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not extract_ready:
        return (
            BLOCKER_EXTRACT_MISSING,
            NEXT_EXTRACT,
            False,
            "Extracted SoccerNet label truth is missing or unsafe; rerun label-member extraction.",
        )
    if mapping.get("adapterReadyForFixtureMaterialization") is not True:
        return (
            BLOCKER_SCHEMA_MALFORMED,
            NEXT_SCHEMA_REPAIR,
            False,
            "SoccerNet label schema is not ready for adapter fixtures; repair the schema contract.",
        )
    return (
        None,
        NEXT_FIXTURE,
        True,
        "SoccerNet ball-action label schema is parseable and ready for event adapter fixture materialization.",
    )


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "label_extract_missing", "selected": primary_blocker == BLOCKER_EXTRACT_MISSING, "primaryBlocker": BLOCKER_EXTRACT_MISSING, "nextRecommendedNextLever": NEXT_EXTRACT},
            {"condition": "label_schema_malformed", "selected": primary_blocker == BLOCKER_SCHEMA_MALFORMED, "primaryBlocker": BLOCKER_SCHEMA_MALFORMED, "nextRecommendedNextLever": NEXT_SCHEMA_REPAIR},
            {"condition": "event_adapter_fixture_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_FIXTURE},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Label Schema Ingestion Probe",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Annotation count: `{summary.get('annotationCount')}`",
            f"- Distinct event labels: `{summary.get('distinctLabelCount')}`",
            f"- Required fields present: `{summary.get('requiredAnnotationFieldsPresent')}`",
            f"- Adapter ready: `{summary.get('adapterReadyForFixtureMaterialization')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_label_schema_ingestion_probe(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_label_schema_ingestion_probe",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _extract_ready(inputs["extractSummary"], inputs["extractedInventory"])
    payloads, load_errors = _load_label_payloads(inputs["extractRoot"], inputs["extractedInventory"])
    rows = _annotation_rows(payloads)
    schema = _schema_audit(payloads, load_errors)
    taxonomy = _event_taxonomy_audit(rows)
    temporal = _temporal_coverage_audit(rows)
    mapping = _mapping_plan(schema, taxonomy)
    primary_blocker, next_lever, goal_achieved, english = _classify(ready, schema, mapping)
    attempts = _attempt_plan()
    generated_at = utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_label_schema_ingestion_probe",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_zip_label_member_extract",
        "annotationCount": schema.get("annotationCount"),
        "distinctLabelCount": taxonomy.get("distinctLabelCount"),
        "requiredAnnotationFieldsPresent": schema.get("requiredAnnotationFieldsPresent"),
        "positionParseRate": schema.get("positionParseRate"),
        "gameTimeParseRate": schema.get("gameTimeParseRate"),
        "adapterReadyForFixtureMaterialization": mapping.get("adapterReadyForFixtureMaterialization"),
        "archiveDownloadExecuted": False,
        "videoMemberDownloadExecuted": False,
        "datasetDownloadAllowedByThisBatch": False,
        "datasetDownloadExecuted": False,
        "fullOriginalVideoDownloadApproved": False,
        "fullOriginalVideoDownloadExecuted": False,
        "videoDownloadAllowed": False,
        "featureDownloadAllowed": False,
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
    decision_matrix = _decision_matrix(primary_blocker, next_lever, goal_achieved)
    batch_outcome = {
        "summary": summary,
        "labelSchemaAudit": schema,
        "eventTaxonomyAudit": taxonomy,
        "temporalCoverageAudit": temporal,
        "adapterMappingPlan": mapping,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "soccernet_label_schema_ingestion_summary.json", summary)
    _write_json(output_root / "label_schema_audit.json", schema)
    _write_json(output_root / "event_taxonomy_audit.json", taxonomy)
    _write_json(output_root / "temporal_coverage_audit.json", temporal)
    _write_json(output_root / "adapter_mapping_plan.json", mapping)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccernet_label_schema_ingestion_probe")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_label_schema_ingestion_probe(
        storage_root=args.storage_root,
        candidate_name=args.candidate_name,
        output_dir_name=args.output_dir_name,
        attempt_number=args.attempt_number,
        attempt_approach_family=args.attempt_approach_family,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("goalAchieved") else 1


if __name__ == "__main__":
    raise SystemExit(main())
