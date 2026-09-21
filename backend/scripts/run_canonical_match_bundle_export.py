from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import write_json as _write_json  # noqa: E402
from backend.app.match_bundle import build_match_bundle  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.app.storage import Storage  # noqa: E402

DEFAULT_SUITE_NAME = "frozen-viable-baseline-slice-suite"
DEFAULT_OUTPUT_DIR_NAME = "canonical_match_bundle_export_v1"
NEXT_PRODUCT_SMOKE = "product_video_to_analysis_smoke_v1"
NEXT_SCHEMA_REPAIR = "canonical_match_bundle_schema_contract_repair"

BLOCKER_NO_READY_MATCH = "canonical_match_bundle_no_ready_match_artifacts"
BLOCKER_SCHEMA_GAP = "canonical_match_bundle_schema_contract_gap"





def _output_root(storage_root: Path) -> Path:
    return (
        Path(storage_root)
        / "benchmark_suites"
        / DEFAULT_SUITE_NAME
        / DEFAULT_OUTPUT_DIR_NAME
    )


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "persisted_artifact_bundle_contract",
            "successCriteria": [
                "build match bundle from persisted frames, analytics, events, and optional provenance artifacts",
                "do not recompute video analysis",
                "write sample_match_bundle.json and contract audit",
            ],
            "failureAdaptation": "If persisted artifacts are missing, route to product smoke instead of inventing data.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "bundle_schema_or_api_contract_repair",
            "successCriteria": [
                "repair route/schema mismatches while preserving deterministic artifact source of truth",
                "keep LLM analysis outside the bundle happy path",
            ],
            "failureAdaptation": "If schema remains inconsistent, stop with a bundle contract blocker.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "bundle_export_blocker_summary",
            "successCriteria": [
                "write exactly one blocker family",
                "preserve runtime defaults and training state",
            ],
            "failureAdaptation": "Route to product smoke or schema repair without training or runtime mutation.",
        },
    ]


def _ready_match_ids(storage: Storage) -> list[str]:
    ready_ids: list[str] = []
    for match in storage.list_matches():
        if match.status != "ready":
            continue
        try:
            storage.load_frames(match.id)
            storage.load_analytics(match.id)
            storage.load_events(match.id)
        except FileNotFoundError:
            continue
        ready_ids.append(match.id)
    return ready_ids


def _contract_audit(bundle: dict[str, Any] | None) -> dict[str, Any]:
    checks = {
        "bundlePresent": isinstance(bundle, dict),
        "schemaVersionPresent": bool(isinstance(bundle, dict) and bundle.get("schemaVersion") == "match_bundle_v1"),
        "matchPresent": bool(isinstance(bundle, dict) and isinstance(bundle.get("match"), dict)),
        "framesPresent": bool(isinstance(bundle, dict) and isinstance(bundle.get("frames"), list)),
        "analyticsPresent": bool(isinstance(bundle, dict) and isinstance(bundle.get("analytics"), dict)),
        "eventsPresent": bool(isinstance(bundle, dict) and isinstance(bundle.get("events"), list)),
        "artifactAvailabilityPresent": bool(
            isinstance(bundle, dict) and isinstance(bundle.get("artifactAvailability"), dict)
        ),
        "exportsPresent": bool(isinstance(bundle, dict) and isinstance(bundle.get("exports"), dict)),
        "deterministicProvenancePresent": bool(
            isinstance(bundle, dict)
            and isinstance(bundle.get("provenance"), dict)
            and bundle["provenance"].get("deterministicCore") is True
            and bundle["provenance"].get("llmGenerated") is False
        ),
    }
    return {
        "checks": checks,
        "bundleContractPassed": all(checks.values()),
    }


def _decision_matrix(*, ready_match_count: int, contract_passed: bool) -> dict[str, Any]:
    if ready_match_count <= 0:
        return {
            "goalAchieved": False,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": BLOCKER_NO_READY_MATCH,
            "nextRecommendedNextLever": NEXT_PRODUCT_SMOKE,
            "englishDecision": "No ready match with frames, analytics, and events exists to sample. Run product video-to-analysis smoke next.",
        }
    if not contract_passed:
        return {
            "goalAchieved": False,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": BLOCKER_SCHEMA_GAP,
            "nextRecommendedNextLever": NEXT_SCHEMA_REPAIR,
            "englishDecision": "A ready match exists, but the bundle contract is incomplete. Repair schema/API contract before product smoke.",
        }
    return {
        "goalAchieved": True,
        "roadmapAdvanceAllowed": True,
        "primaryBlocker": None,
        "nextRecommendedNextLever": NEXT_PRODUCT_SMOKE,
        "englishDecision": "Canonical match bundle export is ready. Advance to product video-to-analysis smoke.",
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Canonical Match Bundle Export",
        "",
        f"- goalAchieved: `{payload['goalAchieved']}`",
        f"- primaryBlocker: `{payload['primaryBlocker']}`",
        f"- readyMatchCount: `{payload['readyMatchCount']}`",
        f"- bundleExportReady: `{payload['bundleExportReady']}`",
        f"- sampleMatchId: `{payload['sampleMatchId']}`",
        f"- trainingExecuted: `{payload['trainingExecuted']}`",
        f"- runtimeDefaultMutationExecuted: `{payload['runtimeDefaultMutationExecuted']}`",
        f"- nextRecommendedNextLever: `{payload['nextRecommendedNextLever']}`",
        "",
        payload["englishDecision"],
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_canonical_match_bundle_export(*, storage_root: Path = DEFAULT_STORAGE_ROOT) -> dict[str, Any]:
    storage_root = Path(storage_root)
    output_root = _output_root(storage_root)
    output_root.mkdir(parents=True, exist_ok=True)
    storage = Storage(storage_root)
    ready_ids = _ready_match_ids(storage)
    sample_match_id = ready_ids[0] if ready_ids else None
    sample_bundle = build_match_bundle(storage, sample_match_id) if sample_match_id else None
    contract_audit = _contract_audit(sample_bundle)
    decision = _decision_matrix(
        ready_match_count=len(ready_ids),
        contract_passed=contract_audit["bundleContractPassed"],
    )
    summary = {
        "batchName": "canonical_match_bundle_export",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptApproachFamily": "persisted_artifact_bundle_contract",
        "attemptPlan": _attempt_plan(),
        "readyMatchCount": len(ready_ids),
        "sampleMatchId": sample_match_id,
        "bundleExportReady": decision["goalAchieved"],
        "trainingExecuted": False,
        "promotionMutationExecuted": False,
        "runtimeDefaultMutationExecuted": False,
        "candidateEvaluationExecuted": False,
        **decision,
    }
    if sample_bundle is not None:
        _write_json(output_root / "sample_match_bundle.json", sample_bundle)
    _write_json(output_root / "bundle_contract_audit.json", contract_audit)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "canonical_match_bundle_export_summary.json", summary)
    _write_json(output_root / "batch_outcome_analysis.json", summary)
    _write_markdown(output_root / "batch_outcome_analysis.md", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    args = parser.parse_args()
    payload = run_canonical_match_bundle_export(storage_root=args.storage_root)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
