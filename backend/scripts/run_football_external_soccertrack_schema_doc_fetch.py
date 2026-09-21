from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_APPROVAL_DIR_NAME = "football_external_soccertrack_schema_doc_fetch_approval_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_soccertrack_schema_doc_fetch_v1"

BLOCKER_APPROVAL_MISSING = "football_external_soccertrack_schema_doc_fetch_approval_missing"
BLOCKER_FETCH_FAILED = "football_external_soccertrack_schema_doc_fetch_failed"

NEXT_APPROVAL = "football_external_soccertrack_schema_doc_fetch_approval"
NEXT_SCHEMA_DOC_PARSE = "football_external_soccertrack_schema_doc_parse"


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name


def _http_fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "fotball-analyst-schema-doc-fetch/1.0"})
    with urlopen(request, timeout=30) as response:  # noqa: S310 - controlled approved schema-doc URL list.
        return response.read()


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "soccertrack_schema_doc_fetch",
            "successCriteria": [
                "fetch only approved SoccerTrack schema documentation files",
                "hash every fetched file",
                "write content inventory for schema parsing",
            ],
            "failureAdaptation": "If fetch fails, return to schema-doc approval or repair stale doc paths.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "soccertrack_schema_doc_fetch_repair",
            "successCriteria": [
                "repair stale schema-doc raw URLs",
                "keep fetch scope docs-only",
            ],
            "failureAdaptation": "If docs still cannot be fetched, write blocker truth.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "soccertrack_schema_doc_fetch_blocker_summary",
            "successCriteria": [
                "select exactly one next family",
                "preserve no dataset/sample download and no training",
            ],
            "failureAdaptation": "Stop before schema parse until approved docs are available.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    approval_root = candidate_root / DEFAULT_APPROVAL_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "approvalRoot": approval_root,
        "approvalSummary": _load_json(approval_root / "schema_doc_fetch_approval_summary.json"),
        "approvalContract": _load_json(approval_root / "schema_doc_fetch_approval_contract.json"),
    }


def _approval_ready(approval_summary: dict[str, Any] | None, approval_contract: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(approval_summary, dict)
        and approval_summary.get("goalAchieved") is True
        and approval_summary.get("primaryBlocker") is None
        and approval_summary.get("schemaDocFetchApproved") is True
        and approval_summary.get("schemaDocFetchExecuted") is False
        and approval_summary.get("datasetDownloadExecuted") is False
        and approval_summary.get("sampleDownloadExecuted") is False
        and approval_summary.get("trainingExecuted") is False
        and isinstance(approval_contract, dict)
        and approval_contract.get("approvedFetchScope") == "schema_docs_only"
        and approval_contract.get("schemaDocFetchApproved") is True
        and approval_contract.get("datasetDownloadApproved") is False
        and approval_contract.get("sampleDownloadApproved") is False
        and isinstance(approval_contract.get("schemaDocPaths"), list)
        and bool(approval_contract.get("schemaDocPaths"))
    )


def _doc_paths(approval_contract: dict[str, Any] | None) -> list[str]:
    raw = (approval_contract or {}).get("schemaDocPaths")
    if not isinstance(raw, list):
        return []
    return [str(path) for path in raw if str(path).strip()]


def _raw_url(source_repository_url: str, path: str) -> str:
    if source_repository_url.rstrip("/") == "https://github.com/AtomScott/SoccerTrack-v2":
        return f"https://raw.githubusercontent.com/AtomScott/SoccerTrack-v2/main/{path}"
    return f"{source_repository_url.rstrip('/')}/raw/main/{path}"


def _safe_filename(path: str) -> str:
    return path.replace("/", "__")


def _fetch_docs(
    output_root: Path,
    source_repository_url: str,
    paths: list[str],
    fetcher: Callable[[str], bytes],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    docs_dir = output_root / "schema_docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for path in paths:
        url = _raw_url(source_repository_url, path)
        try:
            content = fetcher(url)
            digest = hashlib.sha256(content).hexdigest()
            relative_path = f"schema_docs/{_safe_filename(path)}"
            (output_root / relative_path).write_bytes(content)
            files.append(
                {
                    "sourcePath": path,
                    "url": url,
                    "relativePath": relative_path,
                    "sizeBytes": len(content),
                    "sha256": digest,
                }
            )
        except Exception as exc:  # pragma: no cover - real network failure path covered by tests via injected fetcher.
            failures.append({"sourcePath": path, "url": url, "error": str(exc)})
    return files, failures


def _content_inventory(output_root: Path, files: list[dict[str, Any]]) -> dict[str, Any]:
    field_mentions: list[dict[str, Any]] = []
    for row in files:
        text = (output_root / str(row["relativePath"])).read_text(encoding="utf-8", errors="replace")
        for token in ["frameIndex", "timestampMs", "track", "ball", "team", "event", "position", "bbox", "x", "y"]:
            if token.lower() in text.lower():
                field_mentions.append({"sourcePath": row["sourcePath"], "token": token})
    return {
        "schemaVersion": "soccertrack_schema_doc_content_inventory_v1",
        "generatedAt": _utc_now_iso(),
        "schemaDocContentInventoryReady": bool(files),
        "schemaDocCount": len(files),
        "fieldMentionCount": len(field_mentions),
        "fieldMentions": field_mentions,
        "datasetDownloadExecuted": False,
        "sampleDownloadExecuted": False,
        "trainingExecuted": False,
    }


def _classify(approval_ready: bool, files: list[dict[str, Any]], failures: list[dict[str, Any]]) -> tuple[str | None, str, bool, str]:
    if not approval_ready:
        return (
            BLOCKER_APPROVAL_MISSING,
            NEXT_APPROVAL,
            False,
            "SoccerTrack schema-doc fetch approval is missing or unsafe; rerun approval before fetching docs.",
        )
    if failures or not files:
        return (
            BLOCKER_FETCH_FAILED,
            NEXT_APPROVAL,
            False,
            "SoccerTrack schema-doc fetch failed; repair approval paths or source URLs before schema parsing.",
        )
    return (
        None,
        NEXT_SCHEMA_DOC_PARSE,
        True,
        "SoccerTrack schema docs fetched with provenance. Advance to docs parsing; datasets, samples, training, promotion, and runtime mutation remain blocked.",
    )


def _decision_matrix(primary_blocker: str | None, goal_achieved: bool) -> dict[str, Any]:
    return {
        "generatedAt": _utc_now_iso(),
        "decisions": [
            {"condition": "schema_doc_fetch_approval_missing", "selected": primary_blocker == BLOCKER_APPROVAL_MISSING, "primaryBlocker": BLOCKER_APPROVAL_MISSING, "nextRecommendedNextLever": NEXT_APPROVAL},
            {"condition": "schema_doc_fetch_failed", "selected": primary_blocker == BLOCKER_FETCH_FAILED, "primaryBlocker": BLOCKER_FETCH_FAILED, "nextRecommendedNextLever": NEXT_APPROVAL},
            {"condition": "schema_doc_fetch_succeeded", "selected": goal_achieved, "primaryBlocker": None, "nextRecommendedNextLever": NEXT_SCHEMA_DOC_PARSE},
        ],
    }


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External SoccerTrack Schema Doc Fetch",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Schema-doc fetch executed: `{summary.get('schemaDocFetchExecuted')}`",
            f"- Fetched schema-doc count: `{summary.get('fetchedSchemaDocCount')}`",
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


def run_football_external_soccertrack_schema_doc_fetch(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "soccertrack_schema_doc_fetch",
    fetcher: Callable[[str], bytes] = _http_fetch,
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    approval_contract = inputs.get("approvalContract") if isinstance(inputs.get("approvalContract"), dict) else {}
    ready = _approval_ready(inputs.get("approvalSummary"), approval_contract)
    paths = _doc_paths(approval_contract)
    source_repository_url = str(approval_contract.get("sourceRepositoryUrl") or "https://github.com/AtomScott/SoccerTrack-v2")
    files: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    if ready:
        files, failures = _fetch_docs(output_root, source_repository_url, paths, fetcher)
    inventory = _content_inventory(output_root, files)
    primary_blocker, next_lever, goal_achieved, english = _classify(ready, files, failures)
    attempts = _attempt_plan()
    generated_at = _utc_now_iso()
    summary: dict[str, Any] = {
        "batchName": "football_external_soccertrack_schema_doc_fetch",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": goal_achieved,
        "roadmapAdvanceAllowed": goal_achieved,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_soccertrack_schema_doc_fetch_approval",
        "schemaDocFetchExecuted": goal_achieved,
        "fetchedSchemaDocCount": len(files),
        "fetchFailureCount": len(failures),
        "datasetDownloadAllowedByThisBatch": False,
        "datasetDownloadExecuted": False,
        "sampleDownloadApproved": False,
        "sampleDownloadExecuted": False,
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
    manifest = {
        "schemaVersion": "soccertrack_schema_doc_fetch_manifest_v1",
        "generatedAt": generated_at,
        "sourceRepositoryUrl": source_repository_url,
        "files": files,
        "datasetDownloadExecuted": False,
        "sampleDownloadExecuted": False,
        "trainingExecuted": False,
    }
    provenance = {
        "schemaVersion": "soccertrack_schema_doc_fetch_provenance_audit_v1",
        "generatedAt": generated_at,
        "files": files,
        "failures": failures,
        "fetchFailureCount": len(failures),
        "sha256ByPath": {str(row["sourcePath"]): row["sha256"] for row in files},
        "datasetDownloadExecuted": False,
        "sampleDownloadExecuted": False,
        "trainingExecuted": False,
    }
    decision_matrix = _decision_matrix(primary_blocker, goal_achieved)
    batch_outcome = {
        "summary": summary,
        "schemaDocFetchManifest": manifest,
        "schemaDocFetchProvenanceAudit": provenance,
        "schemaDocContentInventory": inventory,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }

    _write_json(output_root / "schema_doc_fetch_summary.json", summary)
    _write_json(output_root / "schema_doc_fetch_manifest.json", manifest)
    _write_json(output_root / "schema_doc_fetch_provenance_audit.json", provenance)
    _write_json(output_root / "schema_doc_content_inventory.json", inventory)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch approved SoccerTrack schema docs only.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="soccertrack_schema_doc_fetch")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_soccertrack_schema_doc_fetch(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
