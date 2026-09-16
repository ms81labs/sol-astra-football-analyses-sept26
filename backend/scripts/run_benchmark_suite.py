from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from statistics import median
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.run_benchmarks import (  # noqa: E402
    DEFAULT_STORAGE_ROOT,
    build_benchmark_suite_source_summaries,
    diagnose_benchmark_suite_robustness,
    summarize_match_benchmark,
)
from backend.app.storage import Storage  # noqa: E402

DEFAULT_MANIFEST_PATH = REPO_ROOT / "backend" / "benchmark_suites" / "frozen_viable_baseline_slice_suite.json"
ROW_FIELDNAMES = [
    "entryId",
    "matchId",
    "label",
    "sourceClipId",
    "videoPath",
    "artifactOnly",
    "status",
    "acceptedBallFrames",
    "acceptedBallRatio",
    "controlledPossessionFrames",
    "controlledPossessionRatio",
    "ballTrackViable",
    "ballTrackEdgeFrameShare",
    "fiveMinuteTruthReady",
    "truthGateReasons",
    "longGapTreatmentOutcome",
    "controlledPossessionAssignmentOutcome",
    "detectorModelName",
    "error",
]
SOURCE_ROW_FIELDNAMES = [
    "sourceClipId",
    "entryCount",
    "viableEntryCount",
    "truthReadyEntryCount",
    "medianAcceptedBallRatio",
    "medianControlledPossessionRatio",
    "medianBallTrackEdgeFrameShare",
    "minAcceptedBallRatio",
    "maxAcceptedBallRatio",
    "minControlledPossessionRatio",
    "maxControlledPossessionRatio",
    "sourceViable",
    "sourceFailureSignal",
]
REQUIRED_SAVED_MATCH_ARTIFACTS = (
    "ball_pipeline_trace.json",
    "ball_truth_layers.json",
    "selected_cluster_delta.json",
    "frames.json",
)


def _load_manifest(manifest_path: Path) -> dict[str, object]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Manifest at {manifest_path} must be a JSON object")
    return payload


def _validate_saved_match_artifact_entry(storage_root: Path, match_id: str) -> str | None:
    match_dir = Path(storage_root) / "matches" / match_id
    missing = [name for name in REQUIRED_SAVED_MATCH_ARTIFACTS if not (match_dir / name).exists()]
    if missing:
        return "Missing required artifacts: " + ", ".join(missing)
    return None


def _safe_ratio_stats(values: list[float]) -> tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    return round(float(median(values)), 3), round(min(values), 3), round(max(values), 3)


def _suite_verdict(
    *,
    successful_entry_count: int,
    distinct_source_clip_count: int,
    viable_entry_count: int,
    truth_ready_entry_count: int,
) -> str:
    if successful_entry_count < 5 or distinct_source_clip_count < 2:
        return "dataset_too_narrow"
    if viable_entry_count / successful_entry_count < 0.6:
        return "baseline_not_robust"
    if truth_ready_entry_count == 0:
        return "viable_but_coverage_limited"
    return "truth_ready_on_suite"


def _recommended_next_lever(verdict: str) -> str:
    if verdict == "dataset_too_narrow":
        return "expand_clip_manifest"
    if verdict == "baseline_not_robust":
        return "multi_match_robustness_repair"
    if verdict == "viable_but_coverage_limited":
        return "batch_safe_proof_loop_runner"
    return "analysis_ready_match_data_contract"


def _suite_row_from_summary(entry: dict[str, object], summary: object) -> dict[str, object]:
    return {
        "entryId": entry.get("entryId"),
        "matchId": entry.get("matchId"),
        "label": entry.get("label"),
        "sourceClipId": entry.get("sourceClipId"),
        "videoPath": summary.videoPath or entry.get("videoPath"),
        "artifactOnly": bool(summary.artifactOnly),
        "status": "success",
        "acceptedBallFrames": int(summary.acceptedBallFrames),
        "acceptedBallRatio": round(float(summary.acceptedBallRatio), 3),
        "controlledPossessionFrames": int(summary.controlledPossessionFrames),
        "controlledPossessionRatio": round(float(summary.controlledPossessionRatio), 3),
        "ballTrackViable": bool(summary.ballTrackViable),
        "ballTrackEdgeFrameShare": round(float(summary.ballTrackEdgeFrameShare), 3),
        "fiveMinuteTruthReady": bool(summary.fiveMinuteTruthReady),
        "truthGateReasons": list(summary.truthGateReasons),
        "longGapTreatmentOutcome": summary.longGapTreatmentOutcome,
        "controlledPossessionAssignmentOutcome": summary.controlledPossessionAssignmentOutcome,
        "detectorModelName": summary.detectorModelName,
        "error": "",
    }


def _failed_suite_row(entry: dict[str, object], error: str) -> dict[str, object]:
    return {
        "entryId": entry.get("entryId"),
        "matchId": entry.get("matchId"),
        "label": entry.get("label"),
        "sourceClipId": entry.get("sourceClipId"),
        "videoPath": entry.get("videoPath"),
        "artifactOnly": False,
        "status": "failed",
        "acceptedBallFrames": 0,
        "acceptedBallRatio": 0.0,
        "controlledPossessionFrames": 0,
        "controlledPossessionRatio": 0.0,
        "ballTrackViable": False,
        "ballTrackEdgeFrameShare": 0.0,
        "fiveMinuteTruthReady": False,
        "truthGateReasons": [],
        "longGapTreatmentOutcome": None,
        "controlledPossessionAssignmentOutcome": None,
        "detectorModelName": None,
        "error": error,
    }


def _write_suite_rows_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            serialized = dict(row)
            serialized["truthGateReasons"] = json.dumps(serialized.get("truthGateReasons", []))
            writer.writerow(serialized)


def _write_suite_source_rows_csv(path: Path, source_summaries: dict[str, dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SOURCE_ROW_FIELDNAMES)
        writer.writeheader()
        for source_clip_id in sorted(source_summaries):
            writer.writerow(source_summaries[source_clip_id])


def _write_suite_summary_markdown(
    path: Path,
    summary: dict[str, object],
    rows: list[dict[str, object]],
    source_summaries: dict[str, dict[str, object]],
    robustness_diagnosis: dict[str, object],
) -> None:
    lines = [
        f"# {summary['suiteName']}",
        "",
        f"- suiteType: {summary['suiteType']}",
        f"- suiteEntryCount: {summary['suiteEntryCount']}",
        f"- successfulEntryCount: {summary['successfulEntryCount']}",
        f"- failedEntryCount: {summary['failedEntryCount']}",
        f"- distinctSourceClipCount: {summary['distinctSourceClipCount']}",
        f"- viableEntryCount: {summary['viableEntryCount']}",
        f"- truthReadyEntryCount: {summary['truthReadyEntryCount']}",
        f"- suiteVerdict: {summary['suiteVerdict']}",
        f"- suiteRecommendedNextLever: {summary['suiteRecommendedNextLever']}",
        "",
        "## Robustness Diagnosis",
        "",
        f"- robustnessOutcome: {robustness_diagnosis.get('robustnessOutcome')}",
        f"- robustnessDominantFailureSignal: {robustness_diagnosis.get('robustnessDominantFailureSignal')}",
        f"- robustnessRecommendedNextLever: {robustness_diagnosis.get('robustnessRecommendedNextLever')}",
        "",
        "| entryId | sourceClipId | status | acceptedBallFrames | controlledPossessionFrames | ballTrackViable | fiveMinuteTruthReady |",
        "| --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {entryId} | {sourceClipId} | {status} | {acceptedBallFrames} | {controlledPossessionFrames} | {ballTrackViable} | {fiveMinuteTruthReady} |".format(
                **row,
            )
        )
    lines.extend(
        [
            "",
            "## Source-Level Summary",
            "",
            "| sourceClipId | entryCount | viableEntryCount | truthReadyEntryCount | medianAcceptedBallRatio | medianControlledPossessionRatio | medianBallTrackEdgeFrameShare | sourceViable | sourceFailureSignal |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for source_clip_id in sorted(source_summaries):
        source_summary = source_summaries[source_clip_id]
        lines.append(
            "| {sourceClipId} | {entryCount} | {viableEntryCount} | {truthReadyEntryCount} | {medianAcceptedBallRatio} | {medianControlledPossessionRatio} | {medianBallTrackEdgeFrameShare} | {sourceViable} | {sourceFailureSignal} |".format(
                **source_summary,
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_benchmark_suite(*, storage_root: Path, manifest_path: Path) -> dict[str, object]:
    storage_root = Path(storage_root)
    storage = Storage(storage_root)
    manifest = _load_manifest(Path(manifest_path))
    entries = manifest.get("entries", [])
    if not isinstance(entries, list):
        raise ValueError("Manifest entries must be a list")

    rows: list[dict[str, object]] = []
    for raw_entry in entries:
        entry = raw_entry if isinstance(raw_entry, dict) else {}
        match_id = entry.get("matchId")
        if not isinstance(match_id, str) or not match_id.strip():
            rows.append(_failed_suite_row(entry, "Manifest entry missing matchId"))
            continue
        source_type = entry.get("sourceType")
        if source_type == "saved_match_artifacts":
            artifact_error = _validate_saved_match_artifact_entry(storage_root, match_id)
            if artifact_error is not None:
                rows.append(_failed_suite_row(entry, artifact_error))
                continue
        try:
            summary = summarize_match_benchmark(storage, match_id)
        except Exception as exc:  # noqa: BLE001
            rows.append(_failed_suite_row(entry, f"{type(exc).__name__}: {exc}"))
            continue
        rows.append(_suite_row_from_summary(entry, summary))

    successful_rows = [row for row in rows if row["status"] == "success"]
    successful_accepted_ratios = [float(row["acceptedBallRatio"]) for row in successful_rows]
    successful_controlled_ratios = [float(row["controlledPossessionRatio"]) for row in successful_rows]
    successful_edge_shares = [float(row["ballTrackEdgeFrameShare"]) for row in successful_rows]
    median_accepted_ball_ratio, min_accepted_ball_ratio, max_accepted_ball_ratio = _safe_ratio_stats(
        successful_accepted_ratios
    )
    (
        median_controlled_possession_ratio,
        min_controlled_possession_ratio,
        max_controlled_possession_ratio,
    ) = _safe_ratio_stats(successful_controlled_ratios)
    median_ball_track_edge_frame_share, _, _ = _safe_ratio_stats(successful_edge_shares)
    viable_entry_count = sum(1 for row in successful_rows if row["ballTrackViable"])
    truth_ready_entry_count = sum(1 for row in successful_rows if row["fiveMinuteTruthReady"])
    distinct_source_clip_count = len(
        {
            row["sourceClipId"]
            for row in successful_rows
            if isinstance(row.get("sourceClipId"), str) and row["sourceClipId"]
        }
    )
    suite_verdict = _suite_verdict(
        successful_entry_count=len(successful_rows),
        distinct_source_clip_count=distinct_source_clip_count,
        viable_entry_count=viable_entry_count,
        truth_ready_entry_count=truth_ready_entry_count,
    )
    source_summaries = build_benchmark_suite_source_summaries(rows)
    suite_summary = {
        "suiteName": manifest.get("suiteName", "benchmark-suite"),
        "suiteType": manifest.get("suiteType", "saved_match_slice_suite"),
        "baselineFingerprint": manifest.get("baselineFingerprint", {}),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "suiteEntryCount": len(rows),
        "successfulEntryCount": len(successful_rows),
        "failedEntryCount": len(rows) - len(successful_rows),
        "distinctSourceClipCount": distinct_source_clip_count,
        "viableEntryCount": viable_entry_count,
        "truthReadyEntryCount": truth_ready_entry_count,
        "medianAcceptedBallRatio": median_accepted_ball_ratio,
        "medianControlledPossessionRatio": median_controlled_possession_ratio,
        "medianBallTrackEdgeFrameShare": median_ball_track_edge_frame_share,
        "minAcceptedBallRatio": min_accepted_ball_ratio,
        "maxAcceptedBallRatio": max_accepted_ball_ratio,
        "minControlledPossessionRatio": min_controlled_possession_ratio,
        "maxControlledPossessionRatio": max_controlled_possession_ratio,
        "suiteVerdict": suite_verdict,
        "suiteRecommendedNextLever": _recommended_next_lever(suite_verdict),
        "sourceSummaries": source_summaries,
    }
    robustness_diagnosis = diagnose_benchmark_suite_robustness(
        suite_summary=suite_summary,
        source_summaries=source_summaries,
    )

    output_dir = storage_root / "benchmark_suites" / str(suite_summary["suiteName"])
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "suite_summary.json").write_text(
        json.dumps(suite_summary, indent=2),
        encoding="utf-8",
    )
    _write_suite_rows_csv(output_dir / "suite_rows.csv", rows)
    _write_suite_source_rows_csv(output_dir / "suite_source_rows.csv", source_summaries)
    (output_dir / "suite_robustness_diagnosis.json").write_text(
        json.dumps(robustness_diagnosis, indent=2),
        encoding="utf-8",
    )
    _write_suite_summary_markdown(output_dir / "suite_summary.md", suite_summary, rows, source_summaries, robustness_diagnosis)

    return {
        "summary": suite_summary,
        "rows": rows,
        "sourceRows": [source_summaries[source_clip_id] for source_clip_id in sorted(source_summaries)],
        "robustnessDiagnosis": robustness_diagnosis,
        "outputDir": str(output_dir),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local saved-match benchmark suite from artifact-backed summaries.")
    parser.add_argument("--storage-root", default=str(DEFAULT_STORAGE_ROOT))
    parser.add_argument("--manifest-path", default=str(DEFAULT_MANIFEST_PATH))
    args = parser.parse_args()

    result = run_benchmark_suite(
        storage_root=Path(args.storage_root),
        manifest_path=Path(args.manifest_path),
    )
    print(json.dumps(result["summary"], separators=(",", ":")))


if __name__ == "__main__":
    main()
