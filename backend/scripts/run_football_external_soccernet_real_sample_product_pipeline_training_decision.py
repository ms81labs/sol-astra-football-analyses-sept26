from __future__ import annotations

import hashlib
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    load_json,
    main_for,
    reset_output,
    standard_false_flags,
    utc_now_iso,
    write_outcome,
)

DEFAULT_REPORT_BINDING_DIR_NAME = "football_external_soccernet_bounded_product_validation_report_binding_v1"
DEFAULT_VIDEO_EXTRACT_DIR_NAME = "football_external_soccernet_video_member_extract_v1"
DEFAULT_LABEL_EXTRACT_DIR_NAME = "football_external_soccernet_zip_label_member_extract_v1"
DEFAULT_FULL_ANALYSIS_DIR_NAME = "football_external_soccernet_full_analysis_execution_v1"
DEFAULT_PRODUCT_API_DIR_NAME = "football_external_soccernet_analysis_product_api_smoke_v1"
DEFAULT_MISS_CAPTURE_DIR_NAME = "football_external_soccernet_detector_miss_capture_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_real_sample_product_pipeline_training_decision_v1"

BLOCKER_REPORT_BINDING_MISSING = "football_external_soccernet_bounded_product_validation_report_binding_missing"
BLOCKER_SAMPLE_MISSING = "football_external_soccernet_real_sample_materialization_missing"
BLOCKER_PRODUCT_PIPELINE_MISSING = "football_external_soccernet_product_pipeline_execution_missing"

NEXT_REPORT_BINDING = "football_external_soccernet_bounded_product_validation_report_binding"
NEXT_SAMPLE_DOWNLOAD = "football_external_soccernet_controlled_real_sample_download_execution"
NEXT_PRODUCT_PIPELINE = "football_external_soccernet_full_analysis_execution"
NEXT_MISS_CAPTURE = "football_external_soccernet_detector_miss_capture_and_label_queue"
NEXT_V7_3_MANIFEST = "v7_3_training_manifest_prep_from_soccernet_real_misses"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "soccernet_real_sample_product_pipeline_training_decision",
                "successCriteria": [
                    "verify controlled real SoccerNet sample materialization",
                    "verify actual product pipeline artifacts on the sample",
                    "decide detector training only from real reviewed miss truth",
                ],
                "failureAdaptation": "If sample and pipeline are ready but no miss truth exists, route to miss capture rather than retraining.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "soccernet_real_sample_materialization_or_pipeline_repair",
                "successCriteria": [
                    "repair only sample paths, label paths, or product-pipeline artifact references",
                    "do not synthesize detector misses or training data",
                ],
                "failureAdaptation": "If sample is missing, route to controlled sample download/materialization.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "soccernet_training_decision_blocker_summary",
                "successCriteria": ["write one blocker", "select exactly one next family"],
                "failureAdaptation": "Stop before v7.3 training unless real miss truth is present.",
            },
        ],
    }


def _load_inputs(root: Path) -> dict[str, Any]:
    return {
        "root": root,
        "reportBindingSummary": load_json(
            root
            / DEFAULT_REPORT_BINDING_DIR_NAME
            / "soccernet_bounded_product_validation_report_binding_summary.json"
        ),
        "videoInventory": load_json(root / DEFAULT_VIDEO_EXTRACT_DIR_NAME / "extracted_video_member_inventory.json"),
        "labelSchemaSummary": load_json(root / "football_external_soccernet_label_schema_ingestion_probe_v1" / "soccernet_label_schema_ingestion_summary.json"),
        "fullAnalysisSummary": load_json(root / DEFAULT_FULL_ANALYSIS_DIR_NAME / "full_analysis_execution_summary.json"),
        "productApiSmokeSummary": load_json(root / DEFAULT_PRODUCT_API_DIR_NAME / "analysis_product_api_smoke_summary.json"),
        "missCaptureSummary": load_json(root / DEFAULT_MISS_CAPTURE_DIR_NAME / "detector_miss_capture_summary.json"),
    }


def _sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _first_video(root: Path, inventory: dict[str, Any] | None) -> dict[str, Any]:
    extract_root = root / DEFAULT_VIDEO_EXTRACT_DIR_NAME
    files = inventory.get("extractedVideoFiles") if isinstance(inventory, dict) else []
    files = files if isinstance(files, list) else []
    for row in files:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("relativePath") or "")
        if not rel:
            continue
        path = extract_root / rel
        return {
            "inventoryRow": row,
            "path": path,
            "exists": path.exists(),
            "sizeBytes": path.stat().st_size if path.exists() else 0,
            "sha256": _sha256_file(path) if path.exists() else None,
        }
    return {"inventoryRow": None, "path": None, "exists": False, "sizeBytes": 0, "sha256": None}


def _label_candidates(root: Path, video_row: dict[str, Any] | None) -> list[Path]:
    member_path = str((video_row or {}).get("memberPath") or "")
    label_root = root / DEFAULT_LABEL_EXTRACT_DIR_NAME / "extracted_labels"
    candidates: list[Path] = []
    if member_path.endswith("/224p.mp4"):
        candidates.append(label_root / member_path.removesuffix("/224p.mp4") / "Labels-ball.json")
    candidates.extend(sorted(label_root.rglob("Labels-ball.json"))[:3])
    deduped: list[Path] = []
    for path in candidates:
        if path not in deduped:
            deduped.append(path)
    return deduped


def _sample_materialization_audit(root: Path, video_inventory: dict[str, Any] | None) -> dict[str, Any]:
    video = _first_video(root, video_inventory)
    inventory_row = video.get("inventoryRow") if isinstance(video.get("inventoryRow"), dict) else {}
    label_candidates = _label_candidates(root, inventory_row)
    label_path = next((path for path in label_candidates if path.exists()), None)
    inventory_sha = inventory_row.get("sha256") if isinstance(inventory_row, dict) else None
    return {
        "schemaVersion": "soccernet_controlled_real_sample_materialization_audit_v1",
        "generatedAt": utc_now_iso(),
        "sampleVideoPath": str(video["path"]) if video.get("path") else None,
        "sampleVideoExists": bool(video.get("exists")),
        "sampleVideoSizeBytes": int(video.get("sizeBytes") or 0),
        "sampleVideoSha256": video.get("sha256"),
        "inventorySha256": inventory_sha,
        "sampleVideoHashMatchesInventory": bool(video.get("sha256") and inventory_sha and video.get("sha256") == inventory_sha),
        "sampleLabelPath": str(label_path) if label_path else None,
        "sampleLabelExists": label_path is not None,
        "archiveDownloadExecuted": False,
        "bulkDownloadExecuted": False,
        "controlledRealSampleMaterialized": bool(video.get("exists")) and int(video.get("sizeBytes") or 0) > 0 and label_path is not None,
    }


def _product_pipeline_audit(full_summary: dict[str, Any] | None, api_summary: dict[str, Any] | None) -> dict[str, Any]:
    processed = int((full_summary or {}).get("processedFrameCount") or 0)
    reported = int((full_summary or {}).get("reportedFrameCount") or 0)
    api_frames = int((api_summary or {}).get("reportedFrameCount") or 0)
    passed = bool(
        isinstance(full_summary, dict)
        and full_summary.get("goalAchieved") is True
        and full_summary.get("primaryBlocker") is None
        and full_summary.get("fullAnalysisExecutionExecuted") is True
        and processed > 0
        and reported == processed
        and int(full_summary.get("unreadableFrameCount") or 0) == 0
        and isinstance(api_summary, dict)
        and api_summary.get("goalAchieved") is True
        and api_summary.get("primaryBlocker") is None
        and api_summary.get("productApiSmokePassed") is True
        and api_frames == processed
    )
    return {
        "schemaVersion": "soccernet_real_sample_product_pipeline_execution_binding_v1",
        "generatedAt": utc_now_iso(),
        "actualProductPipelinePassed": passed,
        "fullAnalysisExecutionPassed": bool(isinstance(full_summary, dict) and full_summary.get("goalAchieved") is True),
        "productApiSmokePassed": bool(isinstance(api_summary, dict) and api_summary.get("productApiSmokePassed") is True),
        "processedFrameCount": processed,
        "reportedFrameCount": reported,
        "apiReportedFrameCount": api_frames,
        "unreadableFrameCount": int((full_summary or {}).get("unreadableFrameCount") or 0),
    }


def _training_need_audit(miss_summary: dict[str, Any] | None) -> dict[str, Any]:
    real_misses = int((miss_summary or {}).get("realDetectorMissCount") or 0)
    reviewed_misses = int((miss_summary or {}).get("reviewedRealMissPositiveCount") or 0)
    miss_truth_ready = bool(
        isinstance(miss_summary, dict)
        and miss_summary.get("goalAchieved") is True
        and miss_summary.get("primaryBlocker") is None
        and real_misses > 0
        and reviewed_misses > 0
    )
    return {
        "schemaVersion": "soccernet_detector_training_need_audit_v1",
        "generatedAt": utc_now_iso(),
        "detectorTrainingNeededFromEvidence": miss_truth_ready,
        "trainingDecision": "needed_real_detector_miss_truth_available"
        if miss_truth_ready
        else "not_justified_yet_no_real_detector_miss_truth",
        "realDetectorMissCount": real_misses,
        "reviewedRealMissPositiveCount": reviewed_misses,
        "v7_3TrainingDataReady": miss_truth_ready,
        "v7_3RetrainExecuted": False,
        "reasoning": [
            "current SoccerNet Labels-ball.json provides event/action timing, not detector bbox truth",
            "v7.3 detector training requires reviewed real miss boxes before retrain",
            "product pipeline pass alone is not detector retraining evidence",
        ],
    }


def _classify(
    report_ready: bool,
    sample_audit: dict[str, Any],
    product_audit: dict[str, Any],
    training_audit: dict[str, Any],
) -> tuple[str | None, str, bool, str]:
    if not report_ready:
        return (
            BLOCKER_REPORT_BINDING_MISSING,
            NEXT_REPORT_BINDING,
            False,
            "SoccerNet validation report binding is missing or unsafe; bind it before real-sample training decision.",
        )
    if sample_audit.get("controlledRealSampleMaterialized") is not True:
        return (
            BLOCKER_SAMPLE_MISSING,
            NEXT_SAMPLE_DOWNLOAD,
            False,
            "Controlled real SoccerNet sample is missing; materialize a bounded sample before product pipeline execution.",
        )
    if product_audit.get("actualProductPipelinePassed") is not True:
        return (
            BLOCKER_PRODUCT_PIPELINE_MISSING,
            NEXT_PRODUCT_PIPELINE,
            False,
            "Actual product pipeline artifacts are missing or failed for the controlled SoccerNet sample.",
        )
    if training_audit.get("detectorTrainingNeededFromEvidence") is True:
        return (
            None,
            NEXT_V7_3_MANIFEST,
            True,
            "Controlled SoccerNet sample and product pipeline passed, and reviewed real detector misses exist. Prepare v7.3 training data; retraining has not executed.",
        )
    return (
        None,
        NEXT_MISS_CAPTURE,
        True,
        "Controlled SoccerNet sample and product pipeline passed. Detector retraining is not justified yet because no reviewed real detector miss truth exists; capture and label real misses first.",
    )


def run_football_external_soccernet_real_sample_product_pipeline_training_decision(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    output_root = reset_output(root, output_dir_name)
    inputs = _load_inputs(root)
    report_ready = bool(
        isinstance(inputs["reportBindingSummary"], dict)
        and inputs["reportBindingSummary"].get("goalAchieved") is True
        and inputs["reportBindingSummary"].get("primaryBlocker") is None
        and inputs["reportBindingSummary"].get("reportBindingReady") is True
    )
    sample_audit = _sample_materialization_audit(root, inputs["videoInventory"])
    product_audit = _product_pipeline_audit(inputs["fullAnalysisSummary"], inputs["productApiSmokeSummary"])
    training_audit = _training_need_audit(inputs["missCaptureSummary"])
    primary_blocker, next_lever, goal, english = _classify(report_ready, sample_audit, product_audit, training_audit)
    decision_matrix = {
        "schemaVersion": "soccernet_real_sample_training_decision_matrix_v1",
        "generatedAt": utc_now_iso(),
        "decisions": [
            {
                "condition": "report_binding_missing",
                "selected": primary_blocker == BLOCKER_REPORT_BINDING_MISSING,
                "primaryBlocker": BLOCKER_REPORT_BINDING_MISSING,
                "nextRecommendedNextLever": NEXT_REPORT_BINDING,
            },
            {
                "condition": "controlled_real_sample_missing",
                "selected": primary_blocker == BLOCKER_SAMPLE_MISSING,
                "primaryBlocker": BLOCKER_SAMPLE_MISSING,
                "nextRecommendedNextLever": NEXT_SAMPLE_DOWNLOAD,
            },
            {
                "condition": "product_pipeline_missing",
                "selected": primary_blocker == BLOCKER_PRODUCT_PIPELINE_MISSING,
                "primaryBlocker": BLOCKER_PRODUCT_PIPELINE_MISSING,
                "nextRecommendedNextLever": NEXT_PRODUCT_PIPELINE,
            },
            {
                "condition": "reviewed_real_misses_available",
                "selected": goal and training_audit.get("detectorTrainingNeededFromEvidence") is True,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_V7_3_MANIFEST,
            },
            {
                "condition": "capture_real_detector_misses_before_training",
                "selected": goal and training_audit.get("detectorTrainingNeededFromEvidence") is False,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_MISS_CAPTURE,
            },
        ],
    }
    v7_3_decision = {
        "schemaVersion": "soccernet_v7_3_training_data_decision_v1",
        "generatedAt": utc_now_iso(),
        "v7_3TrainingDataReady": training_audit.get("v7_3TrainingDataReady") is True,
        "v7_3RetrainExecuted": False,
        "trainingDataSource": "reviewed_soccernet_real_detector_misses"
        if training_audit.get("v7_3TrainingDataReady") is True
        else None,
        "nextIfReady": NEXT_V7_3_MANIFEST,
        "nextIfNotReady": NEXT_MISS_CAPTURE,
    }
    summary = {
        "batchName": "football_external_soccernet_real_sample_product_pipeline_training_decision",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": goal,
        "roadmapAdvanceAllowed": goal,
        "primaryBlocker": primary_blocker,
        "reportBindingReady": report_ready,
        "controlledRealSampleMaterialized": sample_audit.get("controlledRealSampleMaterialized") is True,
        "actualProductPipelinePassed": product_audit.get("actualProductPipelinePassed") is True,
        "processedFrameCount": product_audit.get("processedFrameCount"),
        "reportedFrameCount": product_audit.get("reportedFrameCount"),
        "detectorTrainingNeededFromEvidence": training_audit.get("detectorTrainingNeededFromEvidence") is True,
        "realDetectorMissCount": training_audit.get("realDetectorMissCount"),
        "reviewedRealMissPositiveCount": training_audit.get("reviewedRealMissPositiveCount"),
        "v7_3TrainingDataReady": training_audit.get("v7_3TrainingDataReady") is True,
        "v7_3RetrainExecuted": False,
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="soccernet_real_sample_product_pipeline_training_decision_summary.json",
        summary=summary,
        artifacts={
            "controlled_real_sample_materialization_audit.json": sample_audit,
            "product_pipeline_execution_binding.json": product_audit,
            "detector_training_need_audit.json": training_audit,
            "v7_3_training_data_decision.json": v7_3_decision,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Football External SoccerNet Real Sample Product Pipeline Training Decision",
    )


def main() -> None:
    main_for(
        "Decide whether v7.3 training is needed from controlled SoccerNet real sample evidence.",
        run_football_external_soccernet_real_sample_product_pipeline_training_decision,
    )


if __name__ == "__main__":
    main()
