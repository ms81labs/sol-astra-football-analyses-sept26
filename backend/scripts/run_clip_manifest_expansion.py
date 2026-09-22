from __future__ import annotations
from backend.scripts.football_external_real_eval_chain_common import write_json_unsorted_no_newline as _write_json


import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.proof_runtime import (  # noqa: E402
    DEFAULT_PRIMARY_ACQUISITION_MODE,
    DEFAULT_PROOF_BASELINE_MODEL_PATH,
)
from backend.app.run_benchmarks import (  # noqa: E402
    DEFAULT_STORAGE_ROOT,
    canonicalize_benchmark_video_path,
    derive_saved_match_source_clip_id,
    discover_saved_match_slice_suite_entries,
    run_remote_video_benchmark,
)
from backend.app.schemas import HomographyPoint  # noqa: E402
from backend.app.settings import ProcessingSettings  # noqa: E402
import backend.scripts.run_benchmark_suite as run_benchmark_suite  # noqa: E402

DEFAULT_SOURCE_MANIFEST_PATH = (
    REPO_ROOT / "backend" / "benchmark_suites" / "frozen_viable_baseline_source_manifest.json"
)
DEFAULT_SLICE_SUITE_MANIFEST_PATH = (
    REPO_ROOT / "backend" / "benchmark_suites" / "frozen_viable_baseline_slice_suite.json"
)
DEFAULT_MAX_SUCCESSFUL_IMPORTS = 2
DEFAULT_MAX_TOTAL_ATTEMPTS = 3
FROZEN_BASELINE_FINGERPRINT = {
    "detectorModelPath": DEFAULT_PROOF_BASELINE_MODEL_PATH,
    "primaryMode": DEFAULT_PRIMARY_ACQUISITION_MODE,
    "keptCleanupLane": "recent_ball_plus_inward_anchor_center_bias35_960",
}
IMPORT_ROW_FIELDNAMES = [
    "clipId",
    "localPath",
    "sourceClipId",
    "status",
    "attemptIndex",
    "savedMatchId",
    "acceptedBallFrames",
    "controlledPossessionFrames",
    "ballTrackViable",
    "ballTrackEdgeFrameShare",
    "fiveMinuteTruthReady",
    "error",
]


def clip_manifest_expansion_outcome(
    *,
    successful_imports: int,
    refreshed_suite_distinct_source_clip_count: int,
) -> str:
    if successful_imports >= 2 and refreshed_suite_distinct_source_clip_count >= 3:
        return "clip_manifest_expansion_strong"
    if successful_imports >= 1:
        return "clip_manifest_expansion_partial"
    return "clip_manifest_expansion_blocked"


def clip_manifest_expansion_recommended_next_lever(
    *,
    outcome: str,
    suite_verdict: str,
) -> str:
    if outcome != "clip_manifest_expansion_strong":
        return "expand_clip_manifest"
    if suite_verdict == "baseline_not_robust":
        return "multi_match_robustness_repair"
    if suite_verdict == "viable_but_coverage_limited":
        return "batch_safe_proof_loop_runner"
    if suite_verdict == "truth_ready_on_suite":
        return "analysis_ready_match_data_contract"
    return "expand_clip_manifest"


def _load_manifest(manifest_path: Path) -> dict[str, object]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Manifest at {manifest_path} must be a JSON object")
    return payload


def _manifest_entries(manifest: dict[str, object]) -> list[dict[str, object]]:
    entries = manifest.get("entries", [])
    if not isinstance(entries, list):
        raise ValueError("Manifest entries must be a list")
    return [entry for entry in entries if isinstance(entry, dict)]


def _parse_manual_points(raw_points: object) -> list[HomographyPoint] | None:
    if raw_points is None:
        return None
    if not isinstance(raw_points, list):
        raise ValueError("manualPoints must be a list")
    parsed: list[HomographyPoint] = []
    for point in raw_points:
        if isinstance(point, dict):
            x = point.get("x")
            y = point.get("y")
        elif isinstance(point, (list, tuple)) and len(point) == 2:
            x, y = point
        else:
            raise ValueError("manualPoints entries must be {x,y} objects or [x,y] pairs")
        parsed.append(HomographyPoint(x=float(x), y=float(y)))
    return parsed


def _canonical_local_path(local_path: str) -> str:
    resolved = Path(local_path).expanduser().resolve(strict=False)
    return canonicalize_benchmark_video_path(str(resolved)) or str(resolved)


def _source_clip_id_from_local_path(local_path: str) -> str:
    return derive_saved_match_source_clip_id(_canonical_local_path(local_path))


def _duplicate_enabled_source_clip_ids(entries: list[dict[str, object]]) -> set[str]:
    counts: dict[str, int] = {}
    for entry in entries:
        if not bool(entry.get("enabled", True)):
            continue
        local_path = str(entry.get("localPath", "")).strip()
        if not local_path:
            continue
        source_clip_id = _source_clip_id_from_local_path(local_path)
        counts[source_clip_id] = counts.get(source_clip_id, 0) + 1
    return {
        source_clip_id
        for source_clip_id, count in counts.items()
        if source_clip_id.strip() and count > 1
    }


def _load_current_covered_source_clip_ids(
    *,
    storage_root: Path,
    suite_manifest_path: Path,
) -> set[str]:
    covered_ids: set[str] = set()
    if suite_manifest_path.exists():
        try:
            manifest = _load_manifest(suite_manifest_path)
        except (OSError, ValueError, json.JSONDecodeError, TypeError):
            manifest = {}
        for entry in _manifest_entries(manifest):
            source_clip_id = entry.get("sourceClipId")
            if isinstance(source_clip_id, str) and source_clip_id.strip():
                covered_ids.add(source_clip_id.strip())
    for entry in discover_saved_match_slice_suite_entries(storage_root, max_entries=10000):
        source_clip_id = entry.get("sourceClipId")
        if isinstance(source_clip_id, str) and source_clip_id.strip():
            covered_ids.add(source_clip_id.strip())
    return covered_ids


def _build_slice_suite_manifest(storage_root: Path, *, max_entries: int = 10) -> dict[str, object]:
    return {
        "suiteName": "frozen-viable-baseline-slice-suite",
        "suiteType": "saved_match_slice_suite",
        "baselineFingerprint": dict(FROZEN_BASELINE_FINGERPRINT),
        "entries": discover_saved_match_slice_suite_entries(storage_root, max_entries=max_entries),
    }




def _write_import_rows_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=IMPORT_ROW_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_import_summary_markdown(path: Path, summary: dict[str, object], rows: list[dict[str, object]]) -> None:
    lines = [
        f"# {summary['batchName']}",
        "",
        f"- successfulImports: {summary['successfulImports']}",
        f"- totalAttempts: {summary['totalAttempts']}",
        f"- outcome: {summary['outcome']}",
        f"- recommendedNextLever: {summary['recommendedNextLever']}",
        f"- refreshedSuiteVerdict: {summary['refreshedSuiteVerdict']}",
        f"- refreshedSuiteDistinctSourceClipCount: {summary['refreshedSuiteDistinctSourceClipCount']}",
        "",
        "| clipId | sourceClipId | status | attemptIndex | savedMatchId | acceptedBallFrames | controlledPossessionFrames | error |",
        "| --- | --- | --- | ---: | --- | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| {clipId} | {sourceClipId} | {status} | {attemptIndex} | {savedMatchId} | {acceptedBallFrames} | {controlledPossessionFrames} | {error} |".format(
                clipId=row.get("clipId", ""),
                sourceClipId=row.get("sourceClipId", ""),
                status=row.get("status", ""),
                attemptIndex="" if row.get("attemptIndex") is None else row.get("attemptIndex"),
                savedMatchId=row.get("savedMatchId", ""),
                acceptedBallFrames=row.get("acceptedBallFrames", 0),
                controlledPossessionFrames=row.get("controlledPossessionFrames", 0),
                error=row.get("error", ""),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _base_row(
    *,
    clip_id: str,
    local_path: str,
    source_clip_id: str,
) -> dict[str, object]:
    return {
        "clipId": clip_id,
        "localPath": local_path,
        "sourceClipId": source_clip_id,
        "status": "",
        "attemptIndex": None,
        "savedMatchId": "",
        "acceptedBallFrames": 0,
        "controlledPossessionFrames": 0,
        "ballTrackViable": False,
        "ballTrackEdgeFrameShare": 0.0,
        "fiveMinuteTruthReady": False,
        "error": "",
    }


def run_clip_manifest_expansion(
    *,
    storage_root: Path,
    source_manifest_path: Path,
    suite_manifest_path: Path,
    timestamp_label: str | None = None,
    settings: ProcessingSettings | None = None,
    use_runsync: bool = False,
    max_successful_imports: int = DEFAULT_MAX_SUCCESSFUL_IMPORTS,
    max_total_attempts: int = DEFAULT_MAX_TOTAL_ATTEMPTS,
) -> dict[str, object]:
    storage_root = Path(storage_root)
    source_manifest_path = Path(source_manifest_path)
    suite_manifest_path = Path(suite_manifest_path)
    manifest = _load_manifest(source_manifest_path)
    entries = _manifest_entries(manifest)
    duplicate_enabled_source_clip_ids = _duplicate_enabled_source_clip_ids(entries)
    covered_source_clip_ids = _load_current_covered_source_clip_ids(
        storage_root=storage_root,
        suite_manifest_path=suite_manifest_path,
    )
    rows: list[dict[str, object]] = []
    successful_imports = 0
    total_attempts = 0

    for entry in entries:
        clip_id = str(entry.get("clipId", "")).strip() or "unknown-clip"
        local_path = str(entry.get("localPath", "")).strip()
        source_clip_id = _source_clip_id_from_local_path(local_path) if local_path else "unknown-source-clip"
        row = _base_row(
            clip_id=clip_id,
            local_path=local_path,
            source_clip_id=source_clip_id,
        )
        enabled = bool(entry.get("enabled", True))
        if not enabled:
            row["status"] = "disabled"
            rows.append(row)
            continue
        if successful_imports >= max_successful_imports or total_attempts >= max_total_attempts:
            row["status"] = "not_reached_attempt_cap"
            rows.append(row)
            continue
        if entry.get("sourceType") != "user_supplied_local_video":
            total_attempts += 1
            row["attemptIndex"] = total_attempts
            row["status"] = "invalid_entry"
            row["error"] = "sourceType must be user_supplied_local_video"
            rows.append(row)
            continue
        if not local_path:
            total_attempts += 1
            row["attemptIndex"] = total_attempts
            row["status"] = "invalid_entry"
            row["error"] = "localPath is required"
            rows.append(row)
            continue
        if source_clip_id in duplicate_enabled_source_clip_ids:
            row["status"] = "invalid_entry"
            row["error"] = f"Duplicate enabled sourceClipId in manifest: {source_clip_id}"
            rows.append(row)
            continue
        if source_clip_id in covered_source_clip_ids:
            row["status"] = "already_covered"
            rows.append(row)
            continue

        total_attempts += 1
        row["attemptIndex"] = total_attempts
        candidate_path = Path(local_path).expanduser().resolve(strict=False)
        if not candidate_path.exists() or not candidate_path.is_file():
            row["status"] = "missing_file"
            row["error"] = f"Missing local file: {candidate_path}"
            rows.append(row)
            continue
        try:
            manual_points = _parse_manual_points(entry.get("manualPoints"))
        except (TypeError, ValueError) as exc:
            row["status"] = "invalid_entry"
            row["error"] = str(exc)
            rows.append(row)
            continue
        try:
            summary = run_remote_video_benchmark(
                storage_root=storage_root,
                clip_path=candidate_path,
                manual_points=manual_points,
                settings=settings,
                name=f"{clip_id}-manifest-expansion",
                use_runsync=use_runsync,
                model_path=DEFAULT_PROOF_BASELINE_MODEL_PATH,
                primary_acquisition_mode=DEFAULT_PRIMARY_ACQUISITION_MODE,
            )
        except Exception as exc:  # noqa: BLE001
            row["status"] = "failed"
            row["error"] = f"{type(exc).__name__}: {exc}"
            rows.append(row)
            continue

        successful_imports += 1
        covered_source_clip_ids.add(source_clip_id)
        row.update(
            {
                "status": "success",
                "savedMatchId": summary.matchId,
                "acceptedBallFrames": int(summary.acceptedBallFrames),
                "controlledPossessionFrames": int(summary.controlledPossessionFrames),
                "ballTrackViable": bool(summary.ballTrackViable),
                "ballTrackEdgeFrameShare": round(float(summary.ballTrackEdgeFrameShare), 3),
                "fiveMinuteTruthReady": bool(summary.fiveMinuteTruthReady),
            }
        )
        rows.append(row)

    refreshed_suite_manifest = _build_slice_suite_manifest(storage_root)
    _write_json(suite_manifest_path, refreshed_suite_manifest)
    suite_result = run_benchmark_suite.run_benchmark_suite(
        storage_root=storage_root,
        manifest_path=suite_manifest_path,
    )
    suite_summary = suite_result["summary"]
    outcome = clip_manifest_expansion_outcome(
        successful_imports=successful_imports,
        refreshed_suite_distinct_source_clip_count=int(suite_summary.get("distinctSourceClipCount", 0)),
    )
    recommended_next_lever = clip_manifest_expansion_recommended_next_lever(
        outcome=outcome,
        suite_verdict=str(suite_summary.get("suiteVerdict", "dataset_too_narrow")),
    )
    timestamp = timestamp_label or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = storage_root / "benchmark_suites" / f"clip_manifest_expansion_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "batchName": f"clip_manifest_expansion_{timestamp}",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceManifestPath": str(source_manifest_path),
        "suiteManifestPath": str(suite_manifest_path),
        "successfulImports": successful_imports,
        "totalAttempts": total_attempts,
        "skippedAlreadyCoveredCount": sum(1 for row in rows if row["status"] == "already_covered"),
        "skippedDisabledCount": sum(1 for row in rows if row["status"] == "disabled"),
        "outcome": outcome,
        "recommendedNextLever": recommended_next_lever,
        "refreshedSuiteVerdict": suite_summary.get("suiteVerdict"),
        "refreshedSuiteRecommendedNextLever": suite_summary.get("suiteRecommendedNextLever"),
        "refreshedSuiteDistinctSourceClipCount": int(suite_summary.get("distinctSourceClipCount", 0)),
        "refreshedSuiteOutputDir": suite_result.get("outputDir"),
    }
    _write_json(output_dir / "import_summary.json", summary)
    _write_import_rows_csv(output_dir / "import_rows.csv", rows)
    _write_import_summary_markdown(output_dir / "import_summary.md", summary, rows)
    return {
        "summary": summary,
        "rows": rows,
        "outputDir": str(output_dir),
        "suite": suite_result,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import user-supplied source clips under a bounded cap, then refresh the slice benchmark suite.")
    parser.add_argument("--storage-root", default=str(DEFAULT_STORAGE_ROOT))
    parser.add_argument("--source-manifest-path", default=str(DEFAULT_SOURCE_MANIFEST_PATH))
    parser.add_argument("--suite-manifest-path", default=str(DEFAULT_SLICE_SUITE_MANIFEST_PATH))
    parser.add_argument("--timestamp-label")
    parser.add_argument("--runsync", action="store_true")
    parser.add_argument("--max-successful-imports", type=int, default=DEFAULT_MAX_SUCCESSFUL_IMPORTS)
    parser.add_argument("--max-total-attempts", type=int, default=DEFAULT_MAX_TOTAL_ATTEMPTS)
    args = parser.parse_args()

    result = run_clip_manifest_expansion(
        storage_root=Path(args.storage_root),
        source_manifest_path=Path(args.source_manifest_path),
        suite_manifest_path=Path(args.suite_manifest_path),
        timestamp_label=args.timestamp_label,
        settings=ProcessingSettings.from_env(),
        use_runsync=args.runsync,
        max_successful_imports=args.max_successful_imports,
        max_total_attempts=args.max_total_attempts,
    )
    print(json.dumps(result["summary"], separators=(",", ":")))


if __name__ == "__main__":
    main()
