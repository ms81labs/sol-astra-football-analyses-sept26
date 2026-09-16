from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_v7_probe_assist_integration_audit as audit


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_audit_bundle(
    tmp_path: Path,
    *,
    include_weights: bool = True,
    include_aux_runtime: bool = True,
    include_trace: bool = True,
    probe_pass_seconds: float = 12.5,
) -> None:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    evaluation_root = candidate_root / "evaluation_v1"
    proof_root = tmp_path / "pod_cycles" / "v7-proof"
    weights_path = candidate_root / "weights" / "best.pt"
    if include_weights:
        weights_path.parent.mkdir(parents=True, exist_ok=True)
        weights_path.write_bytes(b"fake weights")
    contract: dict[str, object] = {
        "trainingCandidateName": "touchline_detector_candidate_v7",
        "candidateReadyForEvaluation": True,
        "candidateWeights": {"bestWeightsPath": str(weights_path)},
        "candidateAuxiliaryBallModelPath": str(weights_path),
        "auxiliaryBallModelProfile": "ball_probe_only_v1",
        "runtimeDefaultMutationAllowed": False,
    }
    if not include_aux_runtime:
        contract.pop("candidateAuxiliaryBallModelPath")
        contract.pop("auxiliaryBallModelProfile")
    _write_json(candidate_root / "evaluation_contract.json", contract)
    _write_json(
        candidate_root / "training_run_summary.json",
        {
            "trainingCompleted": True,
            "weightsReady": True,
            "trainingQualityGatePassed": True,
            "readyForDetectorEvaluation": True,
            "runtimeDefaultMutationAllowed": False,
        },
    )
    _write_json(
        evaluation_root / "evaluation_summary.json",
        {
            "screenCompleted": True,
            "candidateBaselineProductBeatsPlateau": False,
            "evaluationPrimaryBlocker": "candidate_baseline_did_not_beat_plateau",
        },
    )
    _write_json(
        evaluation_root / "proof_report.json",
        {
            "candidateBaselineResult": {
                "auxiliaryBallModelPath": str(weights_path) if include_aux_runtime else None,
                "auxiliaryBallModelProfile": "ball_probe_only_v1" if include_aux_runtime else None,
                "summaryPath": str(proof_root / "proof_summary.json"),
            }
        },
    )
    _write_json(
        proof_root / "proof_summary.json",
        {
            "rawProbeObservedBallFrames": 0,
            "probeObservedBallFrames": 0,
            "bestProposalRawDetectedFrames": 0,
            "acceptedBallFrames": 0,
            "runtimeDefaultMutationAllowed": False,
        },
    )
    if include_trace:
        trace_payload: dict[str, object] = {
            "auxiliaryBallModelPath": str(weights_path) if include_aux_runtime else None,
            "auxiliaryBallModelProfile": "ball_probe_only_v1" if include_aux_runtime else None,
            "probeModelPath": str(weights_path) if include_aux_runtime else None,
            "probeDetectorProfile": "ball_probe_only_v1" if include_aux_runtime else None,
            "phaseTimings": {"probeObservedPassSeconds": probe_pass_seconds},
        }
        _write_json(proof_root / "ball_pipeline_trace.json", trace_payload)


def test_audit_detects_missing_model_path(tmp_path: Path) -> None:
    _write_audit_bundle(tmp_path, include_weights=False)

    payload = audit.run_v7_probe_assist_integration_audit(storage_root=tmp_path)

    assert payload["dominantBlockerClass"] == "v7_probe_model_path_missing"
    assert payload["nextCorrectiveFamily"] == "v7_probe_assist_runtime_contract_fix"
    output_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7" / "v7_probe_assist_integration_audit_v1"
    model_audit = _load_json(output_root / "model_path_audit.json")
    assert model_audit["bestWeightsPathExists"] is False


def test_audit_detects_runtime_option_missing(tmp_path: Path) -> None:
    _write_audit_bundle(tmp_path, include_aux_runtime=False)

    payload = audit.run_v7_probe_assist_integration_audit(storage_root=tmp_path)

    assert payload["dominantBlockerClass"] == "v7_probe_runtime_option_missing"
    runtime_audit = _load_json(
        tmp_path
        / "trained_detector_candidates"
        / "touchline_detector_candidate_v7"
        / "v7_probe_assist_integration_audit_v1"
        / "runtime_option_audit.json"
    )
    assert runtime_audit["proofReportAuxiliaryBallModelPathPresent"] is False


def test_audit_detects_auxiliary_detector_not_invoked(tmp_path: Path) -> None:
    _write_audit_bundle(tmp_path, include_trace=True, probe_pass_seconds=0.0)

    payload = audit.run_v7_probe_assist_integration_audit(storage_root=tmp_path)

    assert payload["dominantBlockerClass"] == "v7_auxiliary_detector_not_invoked"
    assert payload["nextCorrectiveFamily"] == "v7_probe_assist_runtime_contract_fix"


def test_audit_selects_threshold_preprocessing_when_invoked_with_zero_signal(tmp_path: Path) -> None:
    _write_audit_bundle(tmp_path, include_trace=True, probe_pass_seconds=9.5)

    payload = audit.run_v7_probe_assist_integration_audit(storage_root=tmp_path)

    output_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7" / "v7_probe_assist_integration_audit_v1"
    summary = _load_json(output_root / "v7_probe_assist_integration_summary.json")
    decision = _load_json(output_root / "decision_matrix.json")
    outcome = _load_json(output_root / "batch_outcome_analysis.json")

    assert payload["dominantBlockerClass"] == "v7_preprocessing_or_threshold_mismatch"
    assert summary["nextCorrectiveFamily"] == "v7_probe_threshold_preprocessing_fix"
    assert decision["selectedNextCorrectiveFamily"] == "v7_probe_threshold_preprocessing_fix"
    assert outcome["runtimeDefaultMutationAllowed"] is False
    assert (output_root / "batch_outcome_analysis.md").exists()
