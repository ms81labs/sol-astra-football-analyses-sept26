from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_FETCH_DIR_NAME = "football_external_safe_source_controlled_sample_fetch_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccertrack_metadata_adapter_smoke_v1"

BLOCKER_FETCH_MISSING = "football_external_soccertrack_metadata_fetch_missing"
BLOCKER_DATA_LICENSE_MISSING = "football_external_soccertrack_data_license_missing"
BLOCKER_METADATA_INCOMPLETE = "football_external_soccertrack_metadata_incomplete"

NEXT_FETCH = "football_external_safe_source_controlled_sample_fetch"
NEXT_APPROVAL = "football_external_safe_source_sample_download_approval"
NEXT_SCHEMA_PROBE = "football_external_soccertrack_sample_schema_probe"


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccertrack_metadata_adapter_smoke",
            "successCriteria": [
                "read fetched SoccerTrack v2 metadata only",
                "detect code and data license classes",
                "confirm metadata is enough to plan a sample schema probe",
            ],
            "failureAdaptation": "If metadata is incomplete, repair source metadata or approval evidence.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccertrack_metadata_contract_repair",
            "successCriteria": [
                "repair missing license metadata from controlled metadata files",
                "keep dataset download and training disallowed",
            ],
            "failureAdaptation": "If metadata still cannot prove sample-use terms, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccertrack_metadata_blocker_summary",
            "successCriteria": [
                "select exactly one next corrective family",
                "stop before any dataset/sample schema fetch",
            ],
            "failureAdaptation": "Return to approval or controlled fetch depending on missing evidence.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    fetch_root = candidate_root / DEFAULT_FETCH_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "fetchRoot": fetch_root,
        "fetchSummary": _load_json(fetch_root / "controlled_sample_fetch_summary.json"),
        "provenanceAudit": _load_json(fetch_root / "fetch_provenance_audit.json"),
        "metadataDir": fetch_root / "sample_metadata",
    }


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _detect_code_license(text: str) -> str | None:
    return "MIT" if "MIT License" in text or "MIT" in text[:500] else None


def _detect_data_license(text: str) -> str | None:
    normalized = text.lower()
    if "creative commons attribution 4.0" in normalized or "cc by 4.0" in normalized:
        return "CC-BY-4.0"
    return None


def _metadata_audits(metadata_dir: Path, provenance_audit: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    readme = _read_text(metadata_dir / "README.md")
    license_text = _read_text(metadata_dir / "LICENSE")
    data_license_text = _read_text(metadata_dir / "LICENSE-DATA")
    code_license = _detect_code_license(license_text)
    data_license = _detect_data_license(data_license_text)
    files = (provenance_audit or {}).get("files")
    file_names = [str(row.get("name")) for row in files if isinstance(row, dict)] if isinstance(files, list) else []
    license_audit = {
        "metadataFileNames": sorted(file_names),
        "readmePresent": bool(readme),
        "codeLicensePresent": bool(license_text),
        "dataLicensePresent": bool(data_license_text),
        "codeLicenseDetected": code_license,
        "dataLicenseDetected": data_license,
        "licenseMetadataComplete": bool(readme and code_license and data_license),
    }
    adapter_audit = {
        "metadataSupportsAdapterProbe": bool(readme and data_license),
        "readmeMentionsAnnotations": "annotation" in readme.lower(),
        "readmeMentionsTracking": "track" in readme.lower(),
        "readmeMentionsBall": "ball" in readme.lower(),
        "datasetDownloadExecuted": False,
        "trainingExecuted": False,
    }
    return license_audit, adapter_audit


def _classify(
    *,
    fetch_summary: dict[str, Any] | None,
    license_audit: dict[str, Any],
    adapter_audit: dict[str, Any],
) -> tuple[str | None, str, bool, str]:
    if not (
        isinstance(fetch_summary, dict)
        and fetch_summary.get("goalAchieved") is True
        and fetch_summary.get("controlledMetadataFetchExecuted") is True
        and fetch_summary.get("datasetDownloadExecuted") is False
    ):
        return (
            BLOCKER_FETCH_MISSING,
            NEXT_FETCH,
            False,
            "Controlled SoccerTrack metadata fetch is missing or failed.",
        )
    if not license_audit["dataLicenseDetected"]:
        return (
            BLOCKER_DATA_LICENSE_MISSING,
            NEXT_APPROVAL,
            False,
            "SoccerTrack metadata does not include a data license file; return to approval evidence before sample schema probing.",
        )
    if not (license_audit["licenseMetadataComplete"] and adapter_audit["metadataSupportsAdapterProbe"]):
        return (
            BLOCKER_METADATA_INCOMPLETE,
            NEXT_FETCH,
            False,
            "SoccerTrack metadata is incomplete for adapter schema probing.",
        )
    return (
        None,
        NEXT_SCHEMA_PROBE,
        True,
        "SoccerTrack metadata adapter smoke passed. Advance to sample schema probe; do not train, promote, or mutate runtime defaults.",
    )


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerTrack Metadata Adapter Smoke",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Code license: `{summary.get('codeLicenseDetected')}`",
            f"- Data license: `{summary.get('dataLicenseDetected')}`",
            f"- Metadata adapter smoke passed: `{summary.get('soccertrackMetadataAdapterSmokePassed')}`",
            f"- Dataset download executed: `{summary.get('datasetDownloadExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_soccertrack_metadata_adapter_smoke(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccertrack_metadata_adapter_smoke",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    license_audit, adapter_audit = _metadata_audits(inputs["metadataDir"], inputs["provenanceAudit"])
    primary_blocker, next_lever, goal_achieved, english = _classify(
        fetch_summary=inputs["fetchSummary"],
        license_audit=license_audit,
        adapter_audit=adapter_audit,
    )
    generated_at = _utc_now_iso()
    attempts = _attempt_plan()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccertrack_metadata_adapter_smoke",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_safe_source_controlled_sample_fetch",
        "soccertrackMetadataAdapterSmokePassed": goal_achieved,
        "codeLicenseDetected": license_audit["codeLicenseDetected"],
        "dataLicenseDetected": license_audit["dataLicenseDetected"],
        "metadataSupportsAdapterProbe": adapter_audit["metadataSupportsAdapterProbe"],
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
    decision_matrix = {
        "generatedAt": generated_at,
        "decisions": [
            {"condition": "metadata_fetch_missing", "selected": primary_blocker == BLOCKER_FETCH_MISSING, "nextRecommendedNextLever": NEXT_FETCH},
            {"condition": "data_license_missing", "selected": primary_blocker == BLOCKER_DATA_LICENSE_MISSING, "nextRecommendedNextLever": NEXT_APPROVAL},
            {"condition": "metadata_incomplete", "selected": primary_blocker == BLOCKER_METADATA_INCOMPLETE, "nextRecommendedNextLever": NEXT_FETCH},
            {"condition": "metadata_adapter_smoke_passed", "selected": goal_achieved, "nextRecommendedNextLever": NEXT_SCHEMA_PROBE},
        ],
    }
    batch_outcome = {
        "summary": summary,
        "soccertrackLicenseMetadataAudit": license_audit,
        "soccertrackAdapterReadinessAudit": adapter_audit,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }
    _write_json(output_root / "soccertrack_metadata_adapter_smoke_summary.json", summary)
    _write_json(output_root / "soccertrack_license_metadata_audit.json", license_audit)
    _write_json(output_root / "soccertrack_adapter_readiness_audit.json", adapter_audit)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse SoccerTrack v2 controlled metadata for adapter readiness.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccertrack_metadata_adapter_smoke")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccertrack_metadata_adapter_smoke(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
