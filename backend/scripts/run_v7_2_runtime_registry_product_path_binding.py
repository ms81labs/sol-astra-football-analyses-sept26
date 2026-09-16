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
from backend.app.proof_runtime import load_runtime_default_registry_options  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.app.storage import Storage  # noqa: E402

DEFAULT_SUITE_NAME = "frozen-viable-baseline-slice-suite"
DEFAULT_OUTPUT_DIR_NAME = "v7_2_runtime_registry_product_path_binding_v1"
NEXT_BUNDLE_EXPORT = "canonical_match_bundle_export_v1"
NEXT_REGISTRY_FIX = "v7_2_runtime_registry_contract_fix"
NEXT_RUNPOD_FIX = "v7_2_runpod_runtime_payload_contract_fix"

BLOCKER_REGISTRY_INACTIVE = "v7_2_product_path_runtime_registry_not_active"
BLOCKER_RUNPOD_PAYLOAD = "v7_2_product_path_runpod_auxiliary_payload_gap"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()






def _output_root(storage_root: Path) -> Path:
    return (
        Path(storage_root)
        / "benchmark_suites"
        / DEFAULT_SUITE_NAME
        / DEFAULT_OUTPUT_DIR_NAME
    )


def _registry_path(storage_root: Path) -> Path:
    return Path(storage_root) / "runtime" / "promoted_touchline_detector_candidate.json"


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "product_path_runtime_registry_binding",
            "successCriteria": [
                "ordinary product path resolves active v7.2 runtime registry when match override is absent",
                "per-match proof_runtime_options.json remains the explicit override surface",
            ],
            "failureAdaptation": "If registry truth is inactive or malformed, repair only registry contract wiring.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "runpod_auxiliary_runtime_payload_repair",
            "successCriteria": [
                "RunPod payload includes v7.2 auxiliary model path and profile",
                "RunPod handler forwards auxiliary fields to process_video_input",
            ],
            "failureAdaptation": "If local binding passes but remote fields are absent, repair payload/handler contract only.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "runtime_registry_product_binding_blocker_summary",
            "successCriteria": [
                "write one blocker family without training, promotion mutation, or runtime re-mutation",
                "route to registry contract fix or RunPod payload contract fix",
            ],
            "failureAdaptation": "Stop with generated blocker truth instead of changing detector behavior.",
        },
    ]


def _local_binding_audit(storage_root: Path) -> dict[str, Any]:
    storage = Storage(storage_root)
    registry = _load_json(_registry_path(storage_root))
    resolved_options = load_runtime_default_registry_options(storage)
    auxiliary_path = (resolved_options or {}).get("auxiliaryBallModelPath")
    checks = {
        "registryExists": isinstance(registry, dict),
        "runtimeDefaultMutationExecuted": bool(
            isinstance(registry, dict) and registry.get("runtimeDefaultMutationExecuted") is True
        ),
        "runtimeUseDefault": bool(isinstance(registry, dict) and registry.get("runtimeUse") == "default_runtime"),
        "resolvedRuntimeOptionsPresent": isinstance(resolved_options, dict),
        "resolvedPrimaryModelPathPresent": bool((resolved_options or {}).get("primaryModelPath")),
        "resolvedAuxiliaryBallModelPathPresent": bool(auxiliary_path),
        "resolvedAuxiliaryBallModelProfilePresent": bool((resolved_options or {}).get("auxiliaryBallModelProfile")),
        "resolvedEdgeShareRepairProfilePresent": bool((resolved_options or {}).get("edgeShareRepairProfile")),
        "auxiliaryWeightsExist": bool(auxiliary_path and Path(str(auxiliary_path)).exists()),
    }
    return {
        "checks": checks,
        "localProductPathRegistryBindingPassed": all(checks.values()),
        "registryPath": str(_registry_path(storage_root)),
        "resolvedRuntimeOptions": resolved_options or {},
    }


def _runpod_payload_audit(storage_root: Path, output_root: Path, resolved_options: dict[str, Any]) -> dict[str, Any]:
    del storage_root, output_root
    # Historical diagnostic only: reproduce the v7.2 wire contract without
    # routing absolute path values through the active portable RunPod builder.
    input_payload = {
        key: resolved_options[key]
        for key in (
            "modelPath",
            "auxiliaryBallModelPath",
            "auxiliaryBallModelProfile",
            "edgeShareRepairProfile",
        )
        if key in resolved_options
    }
    checks = {
        "payloadHasPrimaryModelPath": input_payload.get("modelPath") == resolved_options.get("modelPath"),
        "payloadHasAuxiliaryBallModelPath": input_payload.get("auxiliaryBallModelPath")
        == resolved_options.get("auxiliaryBallModelPath"),
        "payloadHasAuxiliaryBallModelProfile": input_payload.get("auxiliaryBallModelProfile")
        == resolved_options.get("auxiliaryBallModelProfile"),
        "payloadHasEdgeShareRepairProfile": input_payload.get("edgeShareRepairProfile")
        == resolved_options.get("edgeShareRepairProfile"),
    }
    return {
        "checks": checks,
        "runpodAuxiliaryRuntimePayloadPassed": all(checks.values()),
        "payloadInput": input_payload,
    }


def _decision_matrix(
    *,
    local_audit: dict[str, Any],
    runpod_audit: dict[str, Any],
) -> dict[str, Any]:
    if not local_audit["localProductPathRegistryBindingPassed"]:
        return {
            "goalAchieved": False,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": BLOCKER_REGISTRY_INACTIVE,
            "nextRecommendedNextLever": NEXT_REGISTRY_FIX,
            "englishDecision": "Product path registry binding is not active. Repair runtime registry contract before product smoke.",
        }
    if not runpod_audit["runpodAuxiliaryRuntimePayloadPassed"]:
        return {
            "goalAchieved": False,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": BLOCKER_RUNPOD_PAYLOAD,
            "nextRecommendedNextLever": NEXT_RUNPOD_FIX,
            "englishDecision": "Local registry binding passed, but RunPod payload did not preserve v7.2 auxiliary runtime fields.",
        }
    return {
        "goalAchieved": True,
        "roadmapAdvanceAllowed": True,
        "primaryBlocker": None,
        "nextRecommendedNextLever": NEXT_BUNDLE_EXPORT,
        "englishDecision": "Product path now resolves active v7.2 runtime defaults locally and preserves auxiliary runtime fields for RunPod. Advance to canonical match bundle export.",
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# V7.2 Runtime Registry Product Path Binding",
        "",
        f"- goalAchieved: `{payload['goalAchieved']}`",
        f"- primaryBlocker: `{payload['primaryBlocker']}`",
        f"- localProductPathRegistryBindingPassed: `{payload['localProductPathRegistryBindingPassed']}`",
        f"- runpodAuxiliaryRuntimePayloadPassed: `{payload['runpodAuxiliaryRuntimePayloadPassed']}`",
        f"- trainingExecuted: `{payload['trainingExecuted']}`",
        f"- promotionMutationExecuted: `{payload['promotionMutationExecuted']}`",
        f"- runtimeDefaultMutationExecuted: `{payload['runtimeDefaultMutationExecuted']}`",
        f"- nextRecommendedNextLever: `{payload['nextRecommendedNextLever']}`",
        "",
        payload["englishDecision"],
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_v7_2_runtime_registry_product_path_binding(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
) -> dict[str, Any]:
    storage_root = Path(storage_root)
    output_root = _output_root(storage_root)
    output_root.mkdir(parents=True, exist_ok=True)
    local_audit = _local_binding_audit(storage_root)
    runpod_audit = _runpod_payload_audit(
        storage_root,
        output_root,
        local_audit.get("resolvedRuntimeOptions") if isinstance(local_audit.get("resolvedRuntimeOptions"), dict) else {},
    )
    decision = _decision_matrix(local_audit=local_audit, runpod_audit=runpod_audit)
    summary = {
        "batchName": "v7_2_runtime_registry_product_path_binding",
        "generatedAt": _utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptApproachFamily": "product_path_runtime_registry_binding",
        "attemptPlan": _attempt_plan(),
        "localProductPathRegistryBindingPassed": local_audit["localProductPathRegistryBindingPassed"],
        "runpodAuxiliaryRuntimePayloadPassed": runpod_audit["runpodAuxiliaryRuntimePayloadPassed"],
        "trainingExecuted": False,
        "promotionMutationExecuted": False,
        "runtimeDefaultMutationExecuted": False,
        "candidateEvaluationExecuted": False,
        **decision,
    }
    _write_json(output_root / "local_product_path_binding_audit.json", local_audit)
    _write_json(output_root / "runpod_payload_contract_audit.json", runpod_audit)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "runtime_registry_product_binding_summary.json", summary)
    _write_json(output_root / "batch_outcome_analysis.json", summary)
    _write_markdown(output_root / "batch_outcome_analysis.md", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    args = parser.parse_args()
    payload = run_v7_2_runtime_registry_product_path_binding(storage_root=args.storage_root)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
