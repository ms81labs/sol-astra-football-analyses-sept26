from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any
import xml.etree.ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_FETCH_DIR_NAME = "football_external_soccertrack_google_drive_bounded_fixture_fetch_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccertrack_sample_fixture_materialization_v1"

BLOCKER_FETCH_MISSING = "football_external_soccertrack_google_drive_bounded_fixture_fetch_missing"
BLOCKER_MATERIALIZATION_FAILED = "football_external_soccertrack_sample_fixture_materialization_failed"

NEXT_FETCH = "football_external_soccertrack_google_drive_bounded_fixture_fetch"
NEXT_REPAIR = "football_external_soccertrack_sample_fixture_materialization_repair"
NEXT_ADAPTER_SMOKE = "football_external_soccertrack_adapter_smoke_test"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccertrack_lightweight_fixture_materialization",
            "successCriteria": [
                "materialize adapter-ready index from bounded BAS/GSR/MOT fixture files",
                "avoid loading multi-GB GSR JSON files into memory",
                "write lightweight samples and file contracts for adapter smoke testing",
            ],
            "failureAdaptation": "If a required file contract is missing, repair the bounded fetch or filename mapping.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccertrack_fixture_materialization_repair",
            "successCriteria": [
                "repair selected-match file mapping or lightweight parser",
                "preserve no training, promotion, candidate evaluation, or runtime mutation",
            ],
            "failureAdaptation": "If files are too large for direct parse, keep header/index-only mode and route to streaming adapter work.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccertrack_fixture_materialization_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "do not train, promote, mutate runtime defaults, or download videos",
            ],
            "failureAdaptation": "Stop before adapter smoke until sample fixture artifacts are present.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    fetch_root = candidate_root / DEFAULT_FETCH_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "fetchRoot": fetch_root,
        "fetchSummary": _load_json(fetch_root / "google_drive_bounded_fixture_fetch_summary.json"),
        "fetchManifest": _load_json(fetch_root / "google_drive_bounded_fixture_fetch_manifest.json"),
    }


def _fetch_ready(summary: dict[str, Any] | None, manifest: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("sampleDownloadExecuted") is True
        and summary.get("datasetDownloadExecuted") is False
        and summary.get("trainingExecuted") is False
        and {"bas", "gsr", "mot"}.issubset(set(summary.get("downloadedTaskIds") or []))
        and isinstance(manifest, dict)
        and manifest.get("selectedMatchId")
        and isinstance(manifest.get("downloadedFiles"), list)
    )


def _file_by_predicate(fetch_root: Path, manifest: dict[str, Any], predicate) -> Path | None:
    for row in manifest.get("downloadedFiles") or []:
        if isinstance(row, dict) and predicate(row):
            return fetch_root / str(row.get("relativePath"))
    return None


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return payload


def _bas_fixture(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    actions = payload.get("actions")
    actions = actions if isinstance(actions, list) else []
    labels = sorted({str(row.get("label")) for row in actions[:5000] if isinstance(row, dict) and row.get("label")})
    return {
        "schemaVersion": "soccertrack_bas_event_stream_fixture_v1",
        "sourcePath": str(path),
        "matchId": payload.get("match_id"),
        "fps": payload.get("fps"),
        "actionCount": len(actions),
        "sampleActions": actions[:10],
        "labelSetSample": labels[:50],
    }


def _event_fixture(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    annotations = payload.get("annotations")
    annotations = annotations if isinstance(annotations, list) else []
    return {
        "sourcePath": str(path),
        "annotationCount": len(annotations),
        "sampleAnnotations": annotations[:10],
    }


def _gsr_header(path: Path) -> dict[str, Any]:
    chunk = path.read_bytes()[:2_000_000].decode("utf-8", errors="replace")
    info_match = re.search(r'"info"\s*:\s*(\{.*?\})\s*,\s*"images"', chunk, flags=re.S)
    info: dict[str, Any] = {}
    if info_match:
        try:
            parsed = json.loads(info_match.group(1))
            if isinstance(parsed, dict):
                info = parsed
        except json.JSONDecodeError:
            info = {}
    image_ids = re.findall(r'"image_id"\s*:\s*"([^"]+)"', chunk)[:10]
    return {
        "sourcePath": str(path),
        "sizeBytes": path.stat().st_size,
        "info": info,
        "sampleImageIds": image_ids,
    }


def _gsr_fixture(paths: list[Path]) -> dict[str, Any]:
    return {
        "schemaVersion": "soccertrack_gsr_frame_state_fixture_v1",
        "largeFileHeaderOnly": True,
        "largeFileParsePolicy": "do_not_load_full_gsr_json_in_memory",
        "halfFiles": [_gsr_header(path) for path in paths],
    }


def _mot_xml_sample(path: Path, sample_limit: int = 20) -> dict[str, Any]:
    frames: list[dict[str, Any]] = []
    frame_count = 0
    for _event, elem in ET.iterparse(path, events=("end",)):
        if elem.tag == "frame":
            frame_count += 1
            if len(frames) < sample_limit:
                frames.append(dict(elem.attrib))
            elem.clear()
    return {
        "sourcePath": str(path),
        "frameCount": frame_count,
        "sampledFrameCount": len(frames),
        "sampleFrames": frames,
    }


def _csv_sample(path: Path, sample_limit: int = 10) -> dict[str, Any]:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            rows.append(dict(row))
            if len(rows) >= sample_limit:
                break
        return {"sourcePath": str(path), "fieldNames": reader.fieldnames or [], "sampleRows": rows}


def _mot_fixture(fetch_root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    tracker_path = _file_by_predicate(fetch_root, manifest, lambda row: str(row.get("sourcePath", "")).endswith("tracker_box_data.xml"))
    metadata_path = _file_by_predicate(fetch_root, manifest, lambda row: str(row.get("sourcePath", "")).endswith("tracker_box_metadata.xml"))
    player_nodes_path = _file_by_predicate(fetch_root, manifest, lambda row: str(row.get("sourcePath", "")).endswith("player_nodes.csv"))
    if not tracker_path or not player_nodes_path:
        raise ValueError("Missing required MOT tracker XML or player_nodes CSV")
    return {
        "schemaVersion": "soccertrack_mot_track_frame_fixture_v1",
        "trackerBoxData": _mot_xml_sample(tracker_path),
        "trackerMetadataPath": str(metadata_path) if metadata_path else None,
        "playerNodes": _csv_sample(player_nodes_path),
    }


def _materialize(fetch_root: Path, manifest: dict[str, Any], output_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    bas_path = _file_by_predicate(fetch_root, manifest, lambda row: row.get("taskId") == "bas")
    gsr_paths = [
        fetch_root / str(row.get("relativePath"))
        for row in manifest.get("downloadedFiles") or []
        if isinstance(row, dict) and row.get("taskId") == "gsr"
    ]
    if not bas_path or len(gsr_paths) < 2:
        raise ValueError("Missing required BAS or GSR fixture files")
    bas = _bas_fixture(bas_path)
    gsr = _gsr_fixture(sorted(gsr_paths))
    mot = _mot_fixture(fetch_root, manifest)
    event_path = _file_by_predicate(fetch_root, manifest, lambda row: str(row.get("sourcePath", "")).endswith("12_class_events.json") and row.get("taskId") == "mot")
    game_state = {
        "schemaVersion": "soccertrack_game_state_fixture_v1",
        "selectedMatchId": manifest.get("selectedMatchId"),
        "basSourcePath": str(bas_path),
        "motEventStream": _event_fixture(event_path) if event_path else None,
        "taskFixtures": ["bas", "gsr", "mot"],
    }
    return bas, gsr, mot, game_state


def _classify(fetch_ready: bool, materialized: bool) -> tuple[str | None, str, bool, bool, str]:
    if not fetch_ready:
        return (
            BLOCKER_FETCH_MISSING,
            NEXT_FETCH,
            False,
            False,
            "SoccerTrack sample fixture materialization requires successful Google Drive bounded fixture fetch truth.",
        )
    if not materialized:
        return (
            BLOCKER_MATERIALIZATION_FAILED,
            NEXT_REPAIR,
            False,
            True,
            "SoccerTrack bounded fixture files exist but lightweight materialization failed; repair parser or file mapping.",
        )
    return (
        None,
        NEXT_ADAPTER_SMOKE,
        True,
        True,
        "SoccerTrack sample fixture materialization passed. Advance to adapter smoke test; no training, promotion, candidate evaluation, or runtime mutation was executed.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "bounded_fetch_missing", "selected": primary_blocker == BLOCKER_FETCH_MISSING, "primaryBlocker": BLOCKER_FETCH_MISSING, "nextRecommendedNextLever": NEXT_FETCH},
            {"condition": "materialization_failed", "selected": primary_blocker == BLOCKER_MATERIALIZATION_FAILED, "primaryBlocker": BLOCKER_MATERIALIZATION_FAILED, "nextRecommendedNextLever": NEXT_REPAIR},
            {"condition": "materialization_succeeded", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_ADAPTER_SMOKE},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerTrack Sample Fixture Materialization",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Selected match ID: `{summary.get('selectedMatchId')}`",
            f"- Materialized task IDs: `{summary.get('materializedTaskIds')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation allowed: `{summary.get('runtimeDefaultMutationAllowed')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccertrack_sample_fixture_materialization(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccertrack_lightweight_fixture_materialization",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    ready = _fetch_ready(inputs.get("fetchSummary"), inputs.get("fetchManifest"))
    materialized = False
    materialization_error: str | None = None
    bas: dict[str, Any] = {}
    gsr: dict[str, Any] = {}
    mot: dict[str, Any] = {}
    game_state: dict[str, Any] = {}
    if ready and isinstance(inputs.get("fetchManifest"), dict):
        try:
            bas, gsr, mot, game_state = _materialize(inputs["fetchRoot"], inputs["fetchManifest"], output_root)
            materialized = True
        except Exception as exc:  # pragma: no cover - live parser failure path.
            materialization_error = str(exc)
    primary_blocker, next_lever, goal_achieved, roadmap_advance_allowed, english = _classify(ready, materialized)
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    selected_match_id = (inputs.get("fetchManifest") or {}).get("selectedMatchId") if isinstance(inputs.get("fetchManifest"), dict) else None
    materialized_task_ids = ["bas", "gsr", "mot"] if materialized else []
    index = {
        "schemaVersion": "soccertrack_sample_fixture_index_v1",
        "generatedAt": generated_at,
        "selectedSampleResourceId": "soccertrack_v2",
        "selectedMatchId": selected_match_id,
        "fixtureMaterializationMode": "lightweight_index_plus_samples",
        "materializedTaskIds": materialized_task_ids,
        "materializationError": materialization_error,
        "sourceFetchBatch": "football_external_soccertrack_google_drive_bounded_fixture_fetch",
        "trainingExecuted": False,
    }
    summary: dict[str, Any] = {
        "batchName": "football_external_soccertrack_sample_fixture_materialization",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": roadmap_advance_allowed,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccertrack_google_drive_bounded_fixture_fetch",
        "selectedSampleResourceId": "soccertrack_v2",
        "selectedMatchId": selected_match_id,
        "materializedTaskIds": materialized_task_ids,
        "sampleFixtureMaterialized": materialized,
        "sampleDownloadExecuted": bool((inputs.get("fetchSummary") or {}).get("sampleDownloadExecuted")) if isinstance(inputs.get("fetchSummary"), dict) else False,
        "datasetDownloadExecuted": False,
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
    decision_matrix = _decision_matrix(primary_blocker, goal_achieved)
    batch_outcome = {
        "summary": summary,
        "fixtureIndex": index,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "soccertrack_sample_fixture_materialization_summary.json", summary)
    _write_json(output_root / "soccertrack_sample_fixture_index.json", index)
    _write_json(output_root / "soccertrack_bas_event_stream_fixture.json", bas)
    _write_json(output_root / "soccertrack_gsr_frame_state_fixture.json", gsr)
    _write_json(output_root / "soccertrack_mot_track_frame_fixture.json", mot)
    _write_json(output_root / "soccertrack_game_state_fixture.json", game_state)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Materialize lightweight SoccerTrack sample fixture artifacts from bounded Drive fetch.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccertrack_lightweight_fixture_materialization")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccertrack_sample_fixture_materialization(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
