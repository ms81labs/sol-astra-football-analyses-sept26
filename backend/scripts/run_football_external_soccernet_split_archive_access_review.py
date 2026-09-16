from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_REPAIR_DIR_NAME = "football_external_soccernet_label_fetch_contract_repair_v1"
DEFAULT_METADATA_DIR_NAME = "football_external_soccernet_api_metadata_probe_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccernet_split_archive_access_review_v1"

BLOCKER_REPAIR_MISSING = "football_external_soccernet_label_fetch_contract_repair_missing"
BLOCKER_SURFACE_MISSING = "football_external_soccernet_split_archive_surface_missing"

NEXT_REPAIR = "football_external_soccernet_label_fetch_contract_repair"
NEXT_LISTING_REPAIR = "football_external_soccernet_api_listing_contract_repair"
NEXT_SIZE_PROBE = "football_external_soccernet_split_archive_size_probe"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccernet_split_archive_surface_review",
            "successCriteria": [
                "confirm the repaired contract points at package-supported SoccerNet spotting-ball split archives",
                "select one metadata-first split archive surface for a later size/content probe",
                "do not download archive contents, videos, features, or training data",
            ],
            "failureAdaptation": "If package archive support is missing, repair the SoccerNet listing/access contract before any fetch.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccernet_split_archive_contract_repair",
            "successCriteria": [
                "normalize split archive task/split/access-mode fields",
                "preserve approval gates before any archive download",
            ],
            "failureAdaptation": "If a safe package surface still cannot be identified, stop and write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccernet_split_archive_blocker_summary",
            "successCriteria": [
                "select exactly one next corrective family",
                "keep dataset/video/training/runtime mutation guardrails closed",
            ],
            "failureAdaptation": "Do not broaden SoccerNet data access without a new generated approval contract.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    repair_root = candidate_root / DEFAULT_REPAIR_DIR_NAME
    metadata_root = candidate_root / DEFAULT_METADATA_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "repairSummary": _load_json(repair_root / "label_fetch_contract_repair_summary.json"),
        "repairContract": _load_json(repair_root / "repaired_access_contract_plan.json"),
        "packageAudit": _load_json(metadata_root / "soccernet_api_package_audit.json"),
    }


def _repair_ready(repair_summary: dict[str, Any] | None, repair_contract: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(repair_summary, dict)
        and repair_summary.get("goalAchieved") is True
        and repair_summary.get("failedFetchRootCause") == "soccernet_spotting_ball_per_game_labels_json_not_served"
        and repair_summary.get("perGameLabelsJsonSupported") is False
        and repair_summary.get("labelDownloadExecuted") is False
        and repair_summary.get("datasetDownloadExecuted") is False
        and repair_summary.get("fullOriginalVideoDownloadExecuted") is False
        and isinstance(repair_contract, dict)
        and repair_contract.get("recommendedAccessSurface") == "spotting_ball_split_archive"
        and repair_contract.get("approvalRequiredBeforeDownload") is True
        and repair_contract.get("fullOriginalVideoDownloadApproved") is False
        and repair_contract.get("videoDownloadAllowed") is False
        and repair_contract.get("trainingUseAllowed") is False
    )


def _read_downloader_source(candidate_root: Path, package_audit: dict[str, Any] | None) -> tuple[str, str | None]:
    python_executable = (package_audit or {}).get("pythonExecutable") if isinstance(package_audit, dict) else None
    candidate_paths: list[Path] = []
    if python_executable:
        executable = Path(str(python_executable))
        if len(executable.parents) >= 2:
            venv_root = executable.parents[1]
            candidate_paths.extend(venv_root.glob("lib/python*/site-packages/SoccerNet/Downloader.py"))

    candidate_paths.extend(candidate_root.glob("football_external_soccernet_api_metadata_probe_v1/soccernet_api_venv/lib/python*/site-packages/SoccerNet/Downloader.py"))

    for path in candidate_paths:
        if path.exists():
            return path.read_text(encoding="utf-8", errors="replace"), str(path)
    return "", None


def _archive_surfaces(source_text: str) -> list[dict[str, Any]]:
    surfaces: list[dict[str, Any]] = []
    if all(token in source_text for token in ["spotting-ball-2025", "SN-BAS-2025", "snapshot_download"]):
        surfaces.append(
            {
                "task": "spotting-ball-2025",
                "split": "valid",
                "accessMode": "huggingface_snapshot_allow_pattern",
                "archiveFileOrPattern": "*valid.zip",
                "remoteSurface": "huggingface_dataset_snapshot",
                "metadataProbePreferred": True,
                "reason": "Package source exposes HuggingFace snapshot_download with split zip allow_patterns.",
            }
        )
    if all(token in source_text for token in ["spotting-ball-2024", "valid.zip"]):
        surfaces.append(
            {
                "task": "spotting-ball-2024",
                "split": "valid",
                "accessMode": "owncloud_split_zip",
                "archiveFileOrPattern": "valid.zip",
                "remoteSurface": "owncloud_split_zip",
                "metadataProbePreferred": False,
                "reason": "Package source exposes OwnCloud valid.zip for spotting-ball-2024.",
            }
        )
    if all(token in source_text for token in ["spotting-ball-2023", "valid.zip"]):
        surfaces.append(
            {
                "task": "spotting-ball-2023",
                "split": "valid",
                "accessMode": "owncloud_split_zip",
                "archiveFileOrPattern": "valid.zip",
                "remoteSurface": "owncloud_split_zip",
                "metadataProbePreferred": False,
                "reason": "Package source exposes OwnCloud valid.zip for spotting-ball-2023.",
            }
        )
    return surfaces


def _select_surface(surfaces: list[dict[str, Any]]) -> dict[str, Any] | None:
    preferred_order = ["spotting-ball-2025", "spotting-ball-2024", "spotting-ball-2023"]
    by_task = {str(row.get("task")): row for row in surfaces}
    for task in preferred_order:
        if task in by_task:
            return by_task[task]
    return surfaces[0] if surfaces else None


def _surface_audit(
    *,
    source_text: str,
    source_path: str | None,
    repair_contract: dict[str, Any] | None,
) -> dict[str, Any]:
    surfaces = _archive_surfaces(source_text)
    selected = _select_surface(surfaces)
    planned_tasks = repair_contract.get("candidatePackageTasks") if isinstance(repair_contract, dict) else []
    return {
        "downloaderSourcePath": source_path,
        "sourceTextAvailable": bool(source_text),
        "repairPlannedCandidateTasks": planned_tasks if isinstance(planned_tasks, list) else [],
        "detectedArchiveSurfaces": surfaces,
        "packageSupportedArchiveSurfaceReady": selected is not None,
        "selectedArchiveTask": selected.get("task") if selected else None,
        "selectedSplit": selected.get("split") if selected else None,
        "selectedAccessMode": selected.get("accessMode") if selected else None,
        "selectedArchiveFileOrPattern": selected.get("archiveFileOrPattern") if selected else None,
        "selectionReason": selected.get("reason") if selected else "No package-supported SoccerNet spotting-ball split archive surface was detected.",
    }


def _risk_audit(surface_audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "archiveContentsUnknown": True,
        "sizeProbeRequired": surface_audit.get("packageSupportedArchiveSurfaceReady") is True,
        "splitArchiveDownloadApproved": False,
        "downloadAllowedByThisBatch": False,
        "datasetDownloadAllowedByThisBatch": False,
        "fullOriginalVideoDownloadApproved": False,
        "videoDownloadAllowed": False,
        "featureDownloadAllowed": False,
        "trainingUseAllowed": False,
        "credentialRequiredForThisBatch": False,
        "credentialPersisted": False,
        "riskDecision": "Review split archive size and contents in a separate metadata-only probe before any archive download.",
    }


def _size_probe_contract(surface_audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "contractName": NEXT_SIZE_PROBE,
        "sourceBatch": "football_external_soccernet_split_archive_access_review",
        "selectedArchiveTask": surface_audit.get("selectedArchiveTask"),
        "selectedSplit": surface_audit.get("selectedSplit"),
        "selectedAccessMode": surface_audit.get("selectedAccessMode"),
        "selectedArchiveFileOrPattern": surface_audit.get("selectedArchiveFileOrPattern"),
        "approvalRequiredBeforeArchiveDownload": True,
        "downloadAllowedByThisBatch": False,
        "metadataOnly": True,
        "fullOriginalVideoDownloadApproved": False,
        "videoDownloadAllowed": False,
        "trainingUseAllowed": False,
        "expectedProbe": "Inspect remote split archive size and, where possible, listing/contents metadata before fetching any archive bytes.",
    }


def _classify(repair_ready: bool, surface_audit: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not repair_ready:
        return (
            BLOCKER_REPAIR_MISSING,
            NEXT_REPAIR,
            False,
            "SoccerNet label-fetch contract repair truth is missing or unsafe; rerun the repair batch before reviewing split archives.",
        )
    if surface_audit.get("packageSupportedArchiveSurfaceReady") is not True:
        return (
            BLOCKER_SURFACE_MISSING,
            NEXT_LISTING_REPAIR,
            False,
            "No package-supported SoccerNet spotting-ball split archive surface was detected; repair the API listing/access contract before any archive fetch.",
        )
    return (
        None,
        NEXT_SIZE_PROBE,
        True,
        "Package-supported SoccerNet split archive access is identified. Advance to a metadata-only size/content probe; do not download the archive yet.",
    )


def _decision_matrix(primary_blocker: str | None, next_lever: str, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {
                "condition": "label_fetch_contract_repair_missing",
                "selected": primary_blocker == BLOCKER_REPAIR_MISSING,
                "primaryBlocker": BLOCKER_REPAIR_MISSING,
                "nextRecommendedNextLever": NEXT_REPAIR,
            },
            {
                "condition": "split_archive_surface_missing",
                "selected": primary_blocker == BLOCKER_SURFACE_MISSING,
                "primaryBlocker": BLOCKER_SURFACE_MISSING,
                "nextRecommendedNextLever": NEXT_LISTING_REPAIR,
            },
            {
                "condition": "split_archive_size_probe_ready",
                "selected": goal_achieved,
                "primaryBlocker": None,
                "nextRecommendedNextLever": next_lever,
            },
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerNet Split Archive Access Review",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Selected archive task: `{summary.get('selectedArchiveTask')}`",
            f"- Selected split: `{summary.get('selectedSplit')}`",
            f"- Selected access mode: `{summary.get('selectedAccessMode')}`",
            f"- Split archive download approved: `{summary.get('splitArchiveDownloadApproved')}`",
            f"- Dataset download executed: `{summary.get('datasetDownloadExecuted')}`",
            f"- Full original video download executed: `{summary.get('fullOriginalVideoDownloadExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccernet_split_archive_access_review(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    downloader_source_text: str | None = None,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccernet_split_archive_surface_review",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    repair_ready = _repair_ready(inputs["repairSummary"], inputs["repairContract"])
    source_path: str | None = None
    source_text = downloader_source_text
    if source_text is None:
        source_text, source_path = _read_downloader_source(inputs["candidateRoot"], inputs["packageAudit"])
    else:
        source_path = "injected_test_downloader_source"

    surface_audit = _surface_audit(
        source_text=source_text or "",
        source_path=source_path,
        repair_contract=inputs["repairContract"],
    )
    risk_audit = _risk_audit(surface_audit)
    size_contract = _size_probe_contract(surface_audit)
    primary_blocker, next_lever, goal_achieved, english = _classify(repair_ready, surface_audit)
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()

    summary: dict[str, Any] = {
        "batchName": "football_external_soccernet_split_archive_access_review",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccernet_label_fetch_contract_repair",
        "failedFetchRootCause": "soccernet_spotting_ball_per_game_labels_json_not_served" if repair_ready else None,
        "packageSupportedArchiveSurfaceReady": surface_audit.get("packageSupportedArchiveSurfaceReady"),
        "selectedArchiveTask": surface_audit.get("selectedArchiveTask") if goal_achieved else None,
        "selectedSplit": surface_audit.get("selectedSplit") if goal_achieved else None,
        "selectedAccessMode": surface_audit.get("selectedAccessMode") if goal_achieved else None,
        "selectedArchiveFileOrPattern": surface_audit.get("selectedArchiveFileOrPattern") if goal_achieved else None,
        "splitArchiveDownloadApproved": False,
        "labelDownloadExecuted": False,
        "sampleDownloadExecuted": False,
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
        "splitArchiveSurfaceAudit": surface_audit,
        "splitArchiveRiskAudit": risk_audit,
        "splitArchiveSizeProbeContract": size_contract,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "split_archive_access_review_summary.json", summary)
    _write_json(output_root / "split_archive_surface_audit.json", surface_audit)
    _write_json(output_root / "split_archive_risk_audit.json", risk_audit)
    _write_json(output_root / "split_archive_size_probe_contract.json", size_contract)
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
    parser.add_argument("--attempt-approach-family", default="soccernet_split_archive_surface_review")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = run_football_external_soccernet_split_archive_access_review(
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
