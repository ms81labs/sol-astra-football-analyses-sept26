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
DEFAULT_SCHEMA_PROBE_DIR_NAME = "football_external_soccertrack_sample_schema_probe_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccertrack_schema_doc_fetch_approval_v1"

BLOCKER_SCHEMA_PROBE_MISSING = "football_external_soccertrack_sample_schema_probe_missing"
BLOCKER_SCHEMA_DOC_PATH_UNSAFE = "football_external_soccertrack_schema_doc_path_unsafe"

NEXT_SCHEMA_PROBE = "football_external_soccertrack_sample_schema_probe"
NEXT_SCHEMA_DOC_FETCH = "football_external_soccertrack_schema_doc_fetch"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccertrack_schema_doc_fetch_approval",
            "successCriteria": [
                "approve only schema documentation paths from the prior schema probe",
                "reject unsafe paths before fetch",
                "keep dataset/sample download, training, promotion, and runtime mutation disabled",
            ],
            "failureAdaptation": "If approval cannot validate paths, route back to sample schema probe.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccertrack_schema_doc_access_contract_repair",
            "successCriteria": [
                "repair schema-doc access metadata from saved probe artifacts only",
                "preserve schema-doc-only fetch scope",
            ],
            "failureAdaptation": "If unsafe paths remain, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccertrack_schema_doc_approval_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "stop before any schema-doc fetch",
            ],
            "failureAdaptation": "Route to sample schema probe or schema-doc access repair.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    probe_root = candidate_root / DEFAULT_SCHEMA_PROBE_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "probeRoot": probe_root,
        "probeSummary": _load_json(probe_root / "soccertrack_sample_schema_probe_summary.json"),
        "docPlan": _load_json(probe_root / "soccertrack_schema_doc_fetch_plan.json"),
        "schemaContract": _load_json(probe_root / "soccertrack_sample_schema_contract.json"),
    }


def _schema_probe_ready(inputs: dict[str, Any]) -> bool:
    summary = inputs.get("probeSummary")
    doc_plan = inputs.get("docPlan")
    contract = inputs.get("schemaContract")
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("sampleSchemaProbeReady") is True
        and summary.get("schemaDocFetchExecuted") is False
        and summary.get("datasetDownloadExecuted") is False
        and summary.get("sampleDownloadExecuted") is False
        and summary.get("trainingExecuted") is False
        and isinstance(doc_plan, dict)
        and doc_plan.get("selectedResourceId") == "soccertrack_v2"
        and doc_plan.get("fetchApprovalRequired") is True
        and doc_plan.get("schemaDocFetchExecuted") is False
        and doc_plan.get("datasetDownloadExecuted") is False
        and isinstance(contract, dict)
        and contract.get("schemaDocFetchApprovalRequired") is True
        and contract.get("datasetDownloadApproved") is False
        and contract.get("sampleDownloadApproved") is False
    )


def _schema_doc_paths(doc_plan: dict[str, Any] | None) -> list[str]:
    raw = (doc_plan or {}).get("schemaDocPaths")
    if not isinstance(raw, list):
        return []
    return [str(path) for path in raw if str(path).strip()]


def _path_audit(paths: list[str]) -> dict[str, Any]:
    unsafe: list[str] = []
    approved: list[str] = []
    for path in paths:
        is_safe = (
            path.startswith("docs/")
            and ".." not in Path(path).parts
            and not path.startswith("/")
            and not path.endswith(".zip")
            and not path.endswith(".mp4")
            and not path.endswith(".tar")
            and not path.endswith(".gz")
        )
        if is_safe:
            approved.append(path)
        else:
            unsafe.append(path)
    return {
        "schemaVersion": "soccertrack_schema_doc_access_evidence_audit_v1",
        "generatedAt": _utc_now_iso(),
        "requestedSchemaDocPaths": paths,
        "approvedSchemaDocPaths": approved,
        "unsafeSchemaDocPaths": unsafe,
        "allSchemaDocPathsSafe": bool(paths) and not unsafe,
        "schemaDocApprovedPathCount": len(approved),
        "datasetDownloadExecuted": False,
        "sampleDownloadExecuted": False,
        "trainingExecuted": False,
    }


def _approval_contract(path_audit: dict[str, Any], approved: bool) -> dict[str, Any]:
    return {
        "schemaVersion": "soccertrack_schema_doc_fetch_approval_contract_v1",
        "generatedAt": _utc_now_iso(),
        "selectedResourceId": "soccertrack_v2",
        "sourceRepositoryUrl": "https://github.com/AtomScott/SoccerTrack-v2",
        "approvedFetchScope": "schema_docs_only" if approved else None,
        "schemaDocFetchApproved": approved,
        "schemaDocFetchExecuted": False,
        "schemaDocPaths": path_audit.get("approvedSchemaDocPaths") or [],
        "sampleDownloadApproved": False,
        "sampleDownloadExecuted": False,
        "datasetDownloadApproved": False,
        "datasetDownloadExecuted": False,
        "trainingUseApproved": False,
        "requiredFetchMetadata": [
            "sourceRepositoryUrl",
            "schemaDocPaths",
            "sourceCommitOrVersion",
            "licenseFilePath",
            "sha256ByFile",
        ],
    }


def _classify(schema_probe_ready: bool, path_audit: dict[str, Any]) -> tuple[str | None, str, bool, str]:
    if not schema_probe_ready:
        return (
            BLOCKER_SCHEMA_PROBE_MISSING,
            NEXT_SCHEMA_PROBE,
            False,
            "SoccerTrack sample schema probe is missing or unsafe; rerun schema probe before schema-doc fetch approval.",
        )
    if path_audit.get("allSchemaDocPathsSafe") is not True:
        return (
            BLOCKER_SCHEMA_DOC_PATH_UNSAFE,
            NEXT_SCHEMA_PROBE,
            False,
            "SoccerTrack schema-doc fetch approval refused unsafe or empty schema document paths.",
        )
    return (
        None,
        NEXT_SCHEMA_DOC_FETCH,
        True,
        "SoccerTrack schema-doc fetch is approved for documentation files only. Do not download datasets, samples, train, promote, or mutate runtime defaults.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "sample_schema_probe_missing", "selected": primary_blocker == BLOCKER_SCHEMA_PROBE_MISSING, "primaryBlocker": BLOCKER_SCHEMA_PROBE_MISSING, "nextRecommendedNextLever": NEXT_SCHEMA_PROBE},
            {"condition": "schema_doc_path_unsafe", "selected": primary_blocker == BLOCKER_SCHEMA_DOC_PATH_UNSAFE, "primaryBlocker": BLOCKER_SCHEMA_DOC_PATH_UNSAFE, "nextRecommendedNextLever": NEXT_SCHEMA_PROBE},
            {"condition": "schema_doc_fetch_approved", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_SCHEMA_DOC_FETCH},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerTrack Schema Doc Fetch Approval",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Schema-doc fetch approved: `{summary.get('schemaDocFetchApproved')}`",
            f"- Approved path count: `{summary.get('schemaDocApprovedPathCount')}`",
            f"- Schema-doc fetch executed: `{summary.get('schemaDocFetchExecuted')}`",
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


def run_football_external_soccertrack_schema_doc_fetch_approval(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccertrack_schema_doc_fetch_approval",
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    paths = _schema_doc_paths(inputs.get("docPlan") if isinstance(inputs.get("docPlan"), dict) else None)
    path_audit = _path_audit(paths)
    probe_ready = _schema_probe_ready(inputs)
    primary_blocker, next_lever, goal_achieved, english = _classify(probe_ready, path_audit)
    contract = _approval_contract(path_audit, goal_achieved)
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccertrack_schema_doc_fetch_approval",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccertrack_sample_schema_probe",
        "schemaDocFetchApproved": goal_achieved,
        "schemaDocApprovedPathCount": path_audit["schemaDocApprovedPathCount"],
        "schemaDocFetchExecuted": False,
        "sampleDownloadApproved": False,
        "sampleDownloadExecuted": False,
        "datasetDownloadApproved": False,
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
        "schemaDocAccessEvidenceAudit": path_audit,
        "schemaDocFetchApprovalContract": contract,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "schema_doc_fetch_approval_summary.json", summary)
    _write_json(output_root / "schema_doc_fetch_approval_contract.json", contract)
    _write_json(output_root / "schema_doc_access_evidence_audit.json", path_audit)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Approve controlled SoccerTrack schema-doc fetch without dataset/sample downloads.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccertrack_schema_doc_fetch_approval")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccertrack_schema_doc_fetch_approval(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
