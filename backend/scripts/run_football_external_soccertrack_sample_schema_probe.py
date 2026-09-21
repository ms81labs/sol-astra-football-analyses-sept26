from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import json
from pathlib import Path
import re
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_METADATA_SMOKE_DIR_NAME = "football_external_soccertrack_metadata_adapter_smoke_v1"
DEFAULT_FETCH_DIR_NAME = "football_external_safe_source_controlled_sample_fetch_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccertrack_sample_schema_probe_v1"

BLOCKER_METADATA_SMOKE_MISSING = "football_external_soccertrack_metadata_smoke_missing"
BLOCKER_SCHEMA_DOC_SURFACE_MISSING = "football_external_soccertrack_schema_doc_surface_missing"

NEXT_METADATA_SMOKE = "football_external_soccertrack_metadata_adapter_smoke"
NEXT_SCHEMA_DOC_FETCH_APPROVAL = "football_external_soccertrack_schema_doc_fetch_approval"


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccertrack_sample_schema_surface_probe",
            "successCriteria": [
                "read fetched metadata only",
                "identify public schema/documentation surfaces for SoccerTrack sample probing",
                "write a controlled schema-doc fetch approval plan without downloading datasets",
            ],
            "failureAdaptation": "If the schema surface is absent, repair metadata or source documentation evidence.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccertrack_schema_surface_contract_repair",
            "successCriteria": [
                "repair schema-doc path extraction from fetched metadata only",
                "keep schema docs approval-only and do not fetch dataset samples",
            ],
            "failureAdaptation": "If no schema surface can be proven, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccertrack_sample_schema_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before schema-doc fetch or sample download",
            ],
            "failureAdaptation": "Route to metadata smoke or schema-doc fetch approval.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    metadata_root = candidate_root / DEFAULT_METADATA_SMOKE_DIR_NAME
    fetch_root = candidate_root / DEFAULT_FETCH_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "metadataRoot": metadata_root,
        "fetchRoot": fetch_root,
        "metadataSummary": _load_json(metadata_root / "soccertrack_metadata_adapter_smoke_summary.json"),
        "adapterAudit": _load_json(metadata_root / "soccertrack_adapter_readiness_audit.json"),
        "licenseAudit": _load_json(metadata_root / "soccertrack_license_metadata_audit.json"),
        "readmeText": _read_text(fetch_root / "sample_metadata" / "README.md"),
    }


def _metadata_ready(inputs: dict[str, Any]) -> bool:
    summary = inputs.get("metadataSummary")
    adapter_audit = inputs.get("adapterAudit")
    license_audit = inputs.get("licenseAudit")
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("soccertrackMetadataAdapterSmokePassed") is True
        and summary.get("datasetDownloadExecuted") is False
        and summary.get("trainingExecuted") is False
        and isinstance(adapter_audit, dict)
        and adapter_audit.get("metadataSupportsAdapterProbe") is True
        and isinstance(license_audit, dict)
        and license_audit.get("dataLicenseDetected") == "CC-BY-4.0"
    )


def _doc_paths(readme_text: str) -> list[str]:
    candidates = re.findall(r"(?:docs|baselines)/[A-Za-z0-9_.\\/-]+", readme_text)
    normalized = []
    for candidate in candidates:
        clean = candidate.rstrip(").,;`]")
        if clean not in normalized:
            normalized.append(clean)
    return normalized


def _surface_audit(readme_text: str, doc_paths: list[str]) -> dict[str, Any]:
    lower = readme_text.lower()
    readme_mentions_gsr = "gsr" in lower or "game state reconstruction" in lower
    readme_mentions_bas = "bas" in lower or "ball action spotting" in lower
    readme_mentions_mot = "mot" in lower or "multi-object tracking" in lower
    schema_doc_paths = [
        path
        for path in doc_paths
        if path in {"docs/format-gsr.md", "docs/format-bas.md"}
        or path.startswith("docs/format-")
        or path.startswith("docs/task-")
    ]
    detected_task_ids = []
    if readme_mentions_gsr:
        detected_task_ids.append("gsr")
    if readme_mentions_bas:
        detected_task_ids.append("bas")
    if readme_mentions_mot:
        detected_task_ids.append("mot")
    return {
        "schemaVersion": "soccertrack_sample_schema_surface_audit_v1",
        "generatedAt": _utc_now_iso(),
        "readmePresent": bool(readme_text),
        "readmeMentionsGsr": readme_mentions_gsr,
        "readmeMentionsBas": readme_mentions_bas,
        "readmeMentionsMot": readme_mentions_mot,
        "detectedTaskIds": detected_task_ids,
        "schemaDocPaths": schema_doc_paths,
        "schemaDocCandidateCount": len(schema_doc_paths),
        "sampleSchemaSurfaceDetected": bool(readme_text and detected_task_ids and schema_doc_paths),
    }


def _schema_doc_fetch_plan(surface_audit: dict[str, Any]) -> dict[str, Any]:
    schema_doc_paths = list(surface_audit.get("schemaDocPaths") or [])
    prioritized = [path for path in ["docs/format-gsr.md", "docs/format-bas.md"] if path in schema_doc_paths]
    for path in schema_doc_paths:
        if path not in prioritized:
            prioritized.append(path)
    return {
        "schemaVersion": "soccertrack_schema_doc_fetch_plan_v1",
        "generatedAt": _utc_now_iso(),
        "selectedResourceId": "soccertrack_v2",
        "sourceRepositoryUrl": "https://github.com/AtomScott/SoccerTrack-v2",
        "schemaDocPaths": prioritized,
        "fetchApprovalRequired": True,
        "schemaDocFetchExecuted": False,
        "datasetDownloadExecuted": False,
        "trainingUseAllowed": False,
        "intendedUse": "schema documentation only for adapter/sample contract probing",
    }


def _sample_schema_contract(surface_audit: dict[str, Any], doc_plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "soccertrack_sample_schema_contract_v1",
        "generatedAt": _utc_now_iso(),
        "selectedResourceId": "soccertrack_v2",
        "detectedTaskIds": surface_audit.get("detectedTaskIds") or [],
        "schemaDocFetchApproved": False,
        "schemaDocFetchApprovalRequired": True,
        "schemaDocFetchExecuted": False,
        "sampleDownloadApproved": False,
        "sampleDownloadExecuted": False,
        "datasetDownloadApproved": False,
        "datasetDownloadExecuted": False,
        "trainingUseApproved": False,
        "requiredBeforeSampleIngestion": [
            "fetch schema docs under explicit schema-doc approval",
            "parse field-level GSR/BAS/MOT sample schema",
            "materialize a tiny schema fixture before any real sample ingestion",
        ],
        "schemaDocPaths": doc_plan.get("schemaDocPaths") or [],
    }


def _classify(metadata_ready: bool, surface_audit: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not metadata_ready:
        return (
            BLOCKER_METADATA_SMOKE_MISSING,
            NEXT_METADATA_SMOKE,
            False,
            "SoccerTrack metadata adapter smoke is missing or unsafe; rerun metadata smoke before schema probing.",
        )
    if surface_audit.get("sampleSchemaSurfaceDetected") is not True:
        return (
            BLOCKER_SCHEMA_DOC_SURFACE_MISSING,
            NEXT_METADATA_SMOKE,
            False,
            "Fetched SoccerTrack metadata does not expose enough schema/documentation surface for a controlled sample schema probe.",
        )
    return (
        None,
        NEXT_SCHEMA_DOC_FETCH_APPROVAL,
        True,
        "SoccerTrack sample schema surface is identified from metadata. Advance to schema-doc fetch approval; do not download datasets, train, promote, or mutate runtime defaults.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "metadata_smoke_missing", "selected": primary_blocker == BLOCKER_METADATA_SMOKE_MISSING, "primaryBlocker": BLOCKER_METADATA_SMOKE_MISSING, "nextRecommendedNextLever": NEXT_METADATA_SMOKE},
            {"condition": "schema_doc_surface_missing", "selected": primary_blocker == BLOCKER_SCHEMA_DOC_SURFACE_MISSING, "primaryBlocker": BLOCKER_SCHEMA_DOC_SURFACE_MISSING, "nextRecommendedNextLever": NEXT_METADATA_SMOKE},
            {"condition": "sample_schema_probe_ready", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_SCHEMA_DOC_FETCH_APPROVAL},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerTrack Sample Schema Probe",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Sample schema probe ready: `{summary.get('sampleSchemaProbeReady')}`",
            f"- Detected task ids: `{summary.get('detectedTaskIds')}`",
            f"- Schema doc candidates: `{summary.get('schemaDocCandidateCount')}`",
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


def run_football_external_soccertrack_sample_schema_probe(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccertrack_sample_schema_surface_probe",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    doc_paths = _doc_paths(str(inputs.get("readmeText") or ""))
    surface_audit = _surface_audit(str(inputs.get("readmeText") or ""), doc_paths)
    doc_plan = _schema_doc_fetch_plan(surface_audit)
    contract = _sample_schema_contract(surface_audit, doc_plan)
    metadata_ready = _metadata_ready(inputs)
    primary_blocker, next_lever, goal_achieved, english = _classify(metadata_ready, surface_audit)
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccertrack_sample_schema_probe",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccertrack_metadata_adapter_smoke",
        "sampleSchemaProbeReady": goal_achieved,
        "detectedTaskIds": surface_audit["detectedTaskIds"],
        "schemaDocCandidateCount": surface_audit["schemaDocCandidateCount"],
        "schemaDocFetchApprovalRequired": True,
        "schemaDocFetchExecuted": False,
        "sampleDownloadApproved": False,
        "sampleDownloadExecuted": False,
        "datasetDownloadAllowedByThisBatch": False,
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
        "schemaSurfaceAudit": surface_audit,
        "schemaDocFetchPlan": doc_plan,
        "sampleSchemaContract": contract,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "soccertrack_sample_schema_probe_summary.json", summary)
    _write_json(output_root / "soccertrack_schema_surface_audit.json", surface_audit)
    _write_json(output_root / "soccertrack_schema_doc_fetch_plan.json", doc_plan)
    _write_json(output_root / "soccertrack_sample_schema_contract.json", contract)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe SoccerTrack sample schema surfaces from fetched metadata only.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccertrack_sample_schema_surface_probe")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccertrack_sample_schema_probe(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
