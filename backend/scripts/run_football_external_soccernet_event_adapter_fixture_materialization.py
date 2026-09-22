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
DEFAULT_SCHEMA_DIR_NAME = "football_external_soccernet_label_schema_ingestion_probe_v1"
DEFAULT_EXTRACT_DIR_NAME = "football_external_soccernet_zip_label_member_extract_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_event_adapter_fixture_materialization_v1"

BLOCKER_SCHEMA_MISSING = "football_external_soccernet_label_schema_ingestion_missing"
BLOCKER_FIXTURE_INVALID = "football_external_soccernet_event_adapter_fixture_invalid"

NEXT_SCHEMA_PROBE = "football_external_soccernet_label_schema_ingestion_probe"
NEXT_FIXTURE_REPAIR = "football_external_soccernet_event_adapter_fixture_contract_repair"
NEXT_SMOKE = "football_external_soccernet_event_adapter_smoke_test"



def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_event_adapter_fixture_materialization",
            "successCriteria": [
                "materialize parsed SoccerNet annotations as canonical event timeline fixture",
                "preserve source labels and provenance",
                "do not train, promote, mutate runtime defaults, or fetch videos",
            ],
            "failureAdaptation": "If fixture quality fails, repair the adapter fixture contract.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_event_adapter_fixture_contract_repair",
            "successCriteria": [
                "repair event id, timing, taxonomy, or provenance mapping",
                "keep source labels read-only",
            ],
            "failureAdaptation": "If fixture remains invalid, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_event_adapter_fixture_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "avoid broadening data access",
            ],
            "failureAdaptation": "Stop before downstream adapter smoke.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    schema_root = candidate_root / DEFAULT_SCHEMA_DIR_NAME
    extract_root = candidate_root / DEFAULT_EXTRACT_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "extractRoot": extract_root,
        "schemaSummary": _load_json(schema_root / "soccernet_label_schema_ingestion_summary.json"),
        "schemaAudit": _load_json(schema_root / "label_schema_audit.json"),
        "taxonomyAudit": _load_json(schema_root / "event_taxonomy_audit.json"),
        "extractedInventory": _load_json(extract_root / "extracted_label_inventory.json"),
    }


def _schema_ready(summary: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and int(summary.get("annotationCount") or 0) > 0
        and summary.get("requiredAnnotationFieldsPresent") is True
        and summary.get("positionParseRate") == 1.0
        and summary.get("gameTimeParseRate") == 1.0
        and summary.get("adapterReadyForFixtureMaterialization") is True
        and summary.get("trainingExecuted") is False
    )


def _parse_game_time(value: Any) -> dict[str, Any]:
    text = str(value)
    if " - " not in text or ":" not in text:
        return {"raw": text, "parsed": False}
    half_text, clock = text.split(" - ", 1)
    minute_text, second_text = clock.split(":", 1)
    try:
        half = int(half_text)
        minute = int(minute_text)
        second = int(second_text)
    except ValueError:
        return {"raw": text, "parsed": False}
    return {"raw": text, "parsed": True, "period": half, "clock": clock, "secondsInPeriod": minute * 60 + second}


def _load_source_labels(extract_root: Path, inventory: dict[str, Any] | None) -> list[dict[str, Any]]:
    files = (inventory or {}).get("extractedLabelFiles")
    if not isinstance(files, list):
        return []
    sources = []
    for row in files:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("relativePath") or "")
        path = extract_root / rel
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        sources.append({"relativePath": rel, "memberPath": row.get("memberPath"), "payload": payload})
    return sources


def _canonical_events(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for source_index, source in enumerate(sources):
        payload = source.get("payload")
        if not isinstance(payload, dict):
            continue
        game_id = str(payload.get("UrlLocal") or source.get("memberPath") or f"soccernet-game-{source_index}")
        annotations = payload.get("annotations")
        if not isinstance(annotations, list):
            continue
        for annotation_index, annotation in enumerate(annotations):
            if not isinstance(annotation, dict):
                continue
            parsed_time = _parse_game_time(annotation.get("gameTime"))
            try:
                position_ms = int(str(annotation.get("position")))
            except (TypeError, ValueError):
                continue
            events.append(
                {
                    "eventId": f"soccernet-{source_index:03d}-{annotation_index:06d}",
                    "sourceDataset": "SoccerNet SN-BAS-2025",
                    "sourceGameId": game_id,
                    "sourceLabelPath": source.get("relativePath"),
                    "sourceAnnotationIndex": annotation_index,
                    "period": parsed_time.get("period"),
                    "gameTime": annotation.get("gameTime"),
                    "clock": parsed_time.get("clock"),
                    "secondsInPeriod": parsed_time.get("secondsInPeriod"),
                    "positionMs": position_ms,
                    "eventType": annotation.get("label"),
                    "team": annotation.get("team"),
                    "visibility": annotation.get("visibility"),
                }
            )
    return events


def _quality_audit(events: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [str(row.get("eventId")) for row in events]
    positions = [int(row["positionMs"]) for row in events if isinstance(row.get("positionMs"), int)]
    labels = Counter(str(row.get("eventType") or "<missing>") for row in events)
    return {
        "canonicalEventCount": len(events),
        "eventIdUnique": len(ids) == len(set(ids)),
        "positionMsMonotonicNonDecreasing": positions == sorted(positions),
        "positionMsMin": min(positions) if positions else None,
        "positionMsMax": max(positions) if positions else None,
        "distinctEventTypeCount": len(labels),
        "eventTypeCounts": dict(sorted(labels.items())),
        "trainingUseAllowed": False,
    }


def _fixture_manifest(output_root: Path, events: list[dict[str, Any]], quality: dict[str, Any]) -> dict[str, Any]:
    return {
        "fixtureName": "soccernet_ball_action_spotting_valid_label_fixture",
        "sourceDataset": "SoccerNet SN-BAS-2025",
        "canonicalEventTimelinePath": str((output_root / "canonical_event_timeline.json").relative_to(output_root)),
        "canonicalEventCount": len(events),
        "qualityPassed": quality.get("eventIdUnique") is True and len(events) > 0,
        "trainingUseAllowed": False,
    }


def _classify(schema_ready: bool, quality: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not schema_ready:
        return (
            BLOCKER_SCHEMA_MISSING,
            NEXT_SCHEMA_PROBE,
            False,
            "SoccerNet label schema probe truth is missing or unsafe; rerun schema ingestion before fixture materialization.",
        )
    if quality.get("eventIdUnique") is not True or int(quality.get("canonicalEventCount") or 0) <= 0:
        return (
            BLOCKER_FIXTURE_INVALID,
            NEXT_FIXTURE_REPAIR,
            False,
            "Canonical SoccerNet event fixture is invalid; repair adapter fixture contract.",
        )
    return (
        None,
        NEXT_SMOKE,
        True,
        "Materialized SoccerNet ball-action annotations into a canonical event timeline fixture for adapter smoke testing.",
    )


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": utc_now_iso(),
        "decisions": [
            {"condition": "schema_ingestion_missing", "selected": primary_blocker == BLOCKER_SCHEMA_MISSING, "primaryBlocker": BLOCKER_SCHEMA_MISSING, "nextRecommendedNextLever": NEXT_SCHEMA_PROBE},
            {"condition": "event_fixture_invalid", "selected": primary_blocker == BLOCKER_FIXTURE_INVALID, "primaryBlocker": BLOCKER_FIXTURE_INVALID, "nextRecommendedNextLever": NEXT_FIXTURE_REPAIR},
            {"condition": "event_adapter_smoke_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_SMOKE},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Event Adapter Fixture Materialization",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Canonical event count: `{summary.get('canonicalEventCount')}`",
            f"- Distinct event types: `{summary.get('distinctEventTypeCount')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_event_adapter_fixture_materialization(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_event_adapter_fixture_materialization",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _schema_ready(inputs["schemaSummary"])
    sources = _load_source_labels(inputs["extractRoot"], inputs["extractedInventory"])
    events = _canonical_events(sources)
    quality = _quality_audit(events)
    manifest = _fixture_manifest(output_root, events, quality)
    primary_blocker, next_lever, goal_achieved, english = _classify(ready, quality)
    attempts = _attempt_plan()
    generated_at = utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_event_adapter_fixture_materialization",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_label_schema_ingestion_probe",
        "canonicalEventCount": quality.get("canonicalEventCount"),
        "distinctEventTypeCount": quality.get("distinctEventTypeCount"),
        "eventIdUnique": quality.get("eventIdUnique"),
        "eventFixtureQualityPassed": manifest.get("qualityPassed"),
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
    timeline = {"sourceDataset": "SoccerNet SN-BAS-2025", "eventCount": len(events), "events": events}
    decision_matrix = _decision_matrix(primary_blocker, next_lever, goal_achieved)
    batch_outcome = {
        "summary": summary,
        "soccernetEventFixtureManifest": manifest,
        "eventFixtureQualityAudit": quality,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "soccernet_event_fixture_materialization_summary.json", summary)
    _write_json(output_root / "soccernet_event_fixture_manifest.json", manifest)
    _write_json(output_root / "canonical_event_timeline.json", timeline)
    _write_json(output_root / "event_fixture_quality_audit.json", quality)
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
    parser.add_argument("--attempt-approach-family", default="soccernet_event_adapter_fixture_materialization")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_event_adapter_fixture_materialization(
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
