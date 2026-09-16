from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.scripts.football_external_real_eval_chain_common import load_json as _load_json, write_json as _write_json  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import reset_output  # noqa: E402

DEFAULT_CANDIDATE_NAME = "touchline_detector_candidate_v7"
DEFAULT_APPROVAL_DIR_NAME = "football_external_safe_source_sample_download_approval_v1"
DEFAULT_OUTPUT_DIR_NAME = "football_external_safe_source_controlled_sample_fetch_v1"

BLOCKER_APPROVAL_MISSING = "football_external_controlled_fetch_approval_missing"
BLOCKER_NOT_APPROVED = "football_external_controlled_fetch_not_approved"
BLOCKER_FETCH_FAILED = "football_external_controlled_fetch_failed"

NEXT_APPROVAL = "football_external_safe_source_sample_download_approval"
NEXT_METADATA_ADAPTER_SMOKE = "football_external_soccertrack_metadata_adapter_smoke"

SOCCERTRACK_METADATA_FILES = [
    {
        "name": "README.md",
        "url": "https://raw.githubusercontent.com/AtomScott/SoccerTrack-v2/main/README.md",
    },
    {
        "name": "LICENSE",
        "url": "https://raw.githubusercontent.com/AtomScott/SoccerTrack-v2/main/LICENSE",
    },
    {
        "name": "LICENSE-DATA",
        "url": "https://raw.githubusercontent.com/AtomScott/SoccerTrack-v2/main/LICENSE-DATA",
    },
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_root(storage_root: Path, candidate_name: str) -> Path:
    return Path(storage_root) / "trained_detector_candidates" / candidate_name






def _http_fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "fotball-analyst-controlled-metadata-fetch/1.0"})
    with urlopen(request, timeout=30) as response:  # noqa: S310 - controlled official metadata URL list.
        return response.read()


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "controlled_metadata_only_fetch",
            "successCriteria": [
                "fetch only approved SoccerTrack v2 metadata/license files",
                "hash every fetched file",
                "do not download videos, annotations archives, full datasets, train, promote, or mutate runtime defaults",
            ],
            "failureAdaptation": "If metadata fetch fails, repair source URLs or approval contract.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "controlled_fetch_contract_repair",
            "successCriteria": [
                "repair stale metadata URLs",
                "keep fetch scope metadata-only",
            ],
            "failureAdaptation": "If fetch still fails, write a controlled-fetch blocker summary.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "controlled_fetch_blocker_summary",
            "successCriteria": [
                "select exactly one next corrective family",
                "preserve no full dataset download and no training",
            ],
            "failureAdaptation": "Stop before any broader external access.",
        },
    ]


def _load_inputs(storage_root: Path, candidate_name: str) -> dict[str, Any]:
    candidate_root = _candidate_root(storage_root, candidate_name)
    approval_root = candidate_root / DEFAULT_APPROVAL_DIR_NAME
    return {
        "candidateRoot": candidate_root,
        "approvalRoot": approval_root,
        "approvalSummary": _load_json(approval_root / "sample_download_approval_summary.json"),
        "approvalContract": _load_json(approval_root / "controlled_sample_fetch_approval_contract.json"),
    }


def _approval_ready(approval_summary: dict[str, Any] | None, approval_contract: dict[str, Any] | None) -> tuple[str | None, str, bool, str]:
    if not (
        isinstance(approval_summary, dict)
        and approval_summary.get("goalAchieved") is True
        and approval_summary.get("selectedSampleResourceId") == "soccertrack_v2"
        and approval_summary.get("datasetDownloadExecuted") is False
    ):
        return (
            BLOCKER_APPROVAL_MISSING,
            NEXT_APPROVAL,
            False,
            "Controlled fetch approval is missing or does not point at SoccerTrack v2.",
        )
    if approval_summary.get("sampleDownloadApproved") is not True:
        return (
            BLOCKER_NOT_APPROVED,
            NEXT_APPROVAL,
            False,
            "Approval summary does not permit the controlled metadata fetch.",
        )
    if not (
        isinstance(approval_contract, dict)
        and approval_contract.get("sampleDownloadApproved") is True
        and approval_contract.get("approvedFetchScope") == "smallest_official_sample_or_metadata_only"
        and approval_contract.get("fullDatasetDownloadApproved") is False
    ):
        return (
            BLOCKER_NOT_APPROVED,
            NEXT_APPROVAL,
            False,
            "Approval contract does not permit even metadata-only controlled fetch.",
        )
    return (
        None,
        NEXT_METADATA_ADAPTER_SMOKE,
        True,
        "Controlled SoccerTrack v2 metadata fetch completed. Advance to metadata adapter smoke; full dataset download and training remain disallowed.",
    )


def _fetch_metadata(output_root: Path, fetcher: Callable[[str], bytes]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    metadata_dir = output_root / "sample_metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for row in SOCCERTRACK_METADATA_FILES:
        name = row["name"]
        url = row["url"]
        try:
            content = fetcher(url)
            digest = hashlib.sha256(content).hexdigest()
            (metadata_dir / name).write_bytes(content)
            files.append(
                {
                    "name": name,
                    "url": url,
                    "relativePath": f"sample_metadata/{name}",
                    "sizeBytes": len(content),
                    "sha256": digest,
                }
            )
        except Exception as exc:  # pragma: no cover - real network failure path covered by summary shape.
            failures.append({"name": name, "url": url, "error": str(exc)})
    return files, failures


def _markdown_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Football External Safe Source Controlled Sample Fetch",
            "",
            f"- Goal achieved: `{summary.get('goalAchieved')}`",
            f"- Primary blocker: `{summary.get('primaryBlocker')}`",
            f"- Selected sample resource: `{summary.get('selectedSampleResourceId')}`",
            f"- Fetch scope: `{summary.get('fetchScope')}`",
            f"- Fetched file count: `{summary.get('fetchedFileCount')}`",
            f"- Dataset download executed: `{summary.get('datasetDownloadExecuted')}`",
            f"- Full dataset download executed: `{summary.get('fullDatasetDownloadExecuted')}`",
            f"- Training executed: `{summary.get('trainingExecuted')}`",
            f"- Runtime default mutation allowed: `{summary.get('runtimeDefaultMutationAllowed')}`",
            f"- Next: `{summary.get('nextRecommendedNextLever')}`",
            "",
            str(summary.get("englishDecision") or ""),
            "",
        ]
    )


def run_football_external_safe_source_controlled_sample_fetch(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
    attempt_number: int = 1,
    attempt_approach_family: str = "controlled_metadata_only_fetch",
    fetcher: Callable[[str], bytes] = _http_fetch,
) -> dict[str, Any]:
    inputs = _load_inputs(Path(storage_root), candidate_name)
    output_root = reset_output(inputs["candidateRoot"], output_dir_name)

    primary_blocker, next_lever, ready, english = _approval_ready(inputs["approvalSummary"], inputs["approvalContract"])
    files: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    if ready:
        files, failures = _fetch_metadata(output_root, fetcher)
        if failures:
            primary_blocker = BLOCKER_FETCH_FAILED
            next_lever = NEXT_APPROVAL
            ready = False
            english = "Controlled metadata fetch failed; repair source URLs or approval evidence before retrying."
    generated_at = _utc_now_iso()
    attempts = _attempt_plan()
    summary: dict[str, Any] = {
        "batchName": "football_external_safe_source_controlled_sample_fetch",
        "generatedAt": generated_at,
        "attemptNumber": attempt_number,
        "attemptBudget": 3,
        "attemptApproachFamily": attempt_approach_family,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in attempts],
        "goalAchieved": ready,
        "roadmapAdvanceAllowed": ready,
        "primaryBlocker": primary_blocker,
        "sourceBatch": "football_external_safe_source_sample_download_approval",
        "selectedSampleResourceId": "soccertrack_v2",
        "fetchScope": "metadata_only",
        "controlledMetadataFetchExecuted": ready,
        "fetchedFileCount": len(files),
        "fetchFailureCount": len(failures),
        "sampleDownloadExecuted": False,
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
    manifest = {
        "generatedAt": generated_at,
        "resourceId": "soccertrack_v2",
        "fetchScope": "metadata_only",
        "officialSourceUrl": "https://github.com/AtomScott/SoccerTrack-v2",
        "fullDatasetDownloadExecuted": False,
        "datasetDownloadExecuted": False,
        "files": files,
        "failures": failures,
    }
    provenance = {
        "generatedAt": generated_at,
        "sourceBatch": "football_external_safe_source_sample_download_approval",
        "files": files,
        "failures": failures,
        "sha256ByFile": {row["name"]: row["sha256"] for row in files},
    }
    decision_matrix = {
        "generatedAt": generated_at,
        "decisions": [
            {"condition": "approval_missing", "selected": primary_blocker == BLOCKER_APPROVAL_MISSING, "nextRecommendedNextLever": NEXT_APPROVAL},
            {"condition": "fetch_not_approved", "selected": primary_blocker == BLOCKER_NOT_APPROVED, "nextRecommendedNextLever": NEXT_APPROVAL},
            {"condition": "metadata_fetch_failed", "selected": primary_blocker == BLOCKER_FETCH_FAILED, "nextRecommendedNextLever": NEXT_APPROVAL},
            {"condition": "metadata_fetch_completed", "selected": ready, "nextRecommendedNextLever": NEXT_METADATA_ADAPTER_SMOKE},
        ],
    }
    batch_outcome = {
        "summary": summary,
        "controlledFetchManifest": manifest,
        "fetchProvenanceAudit": provenance,
        "decisionMatrix": decision_matrix,
        "failsafeAttemptPlan": {"attemptBudget": 3, "attempts": attempts},
    }
    _write_json(output_root / "controlled_sample_fetch_summary.json", summary)
    _write_json(output_root / "controlled_fetch_manifest.json", manifest)
    _write_json(output_root / "fetch_provenance_audit.json", provenance)
    _write_json(output_root / "decision_matrix.json", decision_matrix)
    _write_json(output_root / "failsafe_attempt_plan.json", {"attemptBudget": 3, "attempts": attempts})
    _write_json(output_root / "batch_outcome_analysis.json", batch_outcome)
    (output_root / "batch_outcome_analysis.md").write_text(_markdown_summary(summary), encoding="utf-8")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch approved SoccerTrack v2 metadata only, with hashes.")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--candidate-name", default=DEFAULT_CANDIDATE_NAME)
    parser.add_argument("--output-dir-name", default=DEFAULT_OUTPUT_DIR_NAME)
    parser.add_argument("--attempt-number", type=int, default=1)
    parser.add_argument("--attempt-approach-family", default="controlled_metadata_only_fetch")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    payload = run_football_external_safe_source_controlled_sample_fetch(
        storage_root=args.storage_root,
        candidate_name=str(args.candidate_name),
        output_dir_name=str(args.output_dir_name),
        attempt_number=int(args.attempt_number),
        attempt_approach_family=str(args.attempt_approach_family),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
