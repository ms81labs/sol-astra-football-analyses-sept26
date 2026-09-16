from __future__ import annotations

import json
from pathlib import Path

import backend.scripts.run_v7_probe_threshold_contract_fix as contract_fix


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_candidate_bundle(
    storage_root: Path,
    *,
    raw_frames: int,
    filtered_frames: int = 0,
    proposal_frames: int = 0,
    selected_frames: int = 0,
    accepted_frames: int = 0,
) -> Path:
    candidate_root = storage_root / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    evaluation_root = candidate_root / "evaluation_v1"
    proof_summary_path = storage_root / "proof_summary.json"
    trace_path = storage_root / "ball_pipeline_trace.json"
    _write_json(
        evaluation_root / "evaluation_contract.json",
        {
            "auxiliaryBallModelProfile": "ball_probe_only_v1_low_conf_001",
            "candidateAuxiliaryBallModelPath": str(candidate_root / "weights" / "best.pt"),
        },
    )
    _write_json(
        proof_summary_path,
        {
            "rawProbeObservedBallFrames": raw_frames,
            "probeObservedBallFrames": filtered_frames,
            "proposalCandidateFrames": proposal_frames,
            "recoveredSelectedFrames": selected_frames,
            "acceptedBallFrames": accepted_frames,
        },
    )
    _write_json(
        trace_path,
        {
            "probeDetectorProfile": "ball_probe_only_v1_low_conf_001",
            "probeRecoveryConf": 0.01,
            "probeRecoveryImgsz": 960,
        },
    )
    _write_json(
        evaluation_root / "proof_report.json",
        {
            "candidateBaselineResult": {
                "summaryPath": str(proof_summary_path),
                "ballPipelineTracePath": str(trace_path),
            }
        },
    )
    return candidate_root


def test_threshold_contract_selects_proposal_integration_when_raw_signal_recovers(tmp_path: Path) -> None:
    candidate_root = _write_candidate_bundle(tmp_path, raw_frames=6, filtered_frames=4)

    payload = contract_fix.run_v7_probe_threshold_contract_fix(storage_root=tmp_path)

    output_root = candidate_root / "v7_probe_threshold_contract_fix_v1"
    summary = _load_json(output_root / "threshold_contract_summary.json")
    coverage = _load_json(output_root / "v7_probe_threshold_contract_coverage.json")
    outcome = _load_json(output_root / "batch_outcome_analysis.json")
    assert payload["dominantBlockerClass"] == "v7_probe_raw_signal_recovered"
    assert summary["nextCorrectiveFamily"] == "v7_probe_proposal_window_integration_fix"
    assert coverage["rawProbeObservedBallFrames"] == 6
    assert outcome["runtimeDefaultMutationAllowed"] is False
    assert (output_root / "batch_outcome_analysis.md").exists()


def test_threshold_contract_selects_selection_followthrough_when_proposals_recover(tmp_path: Path) -> None:
    _write_candidate_bundle(tmp_path, raw_frames=6, filtered_frames=4, proposal_frames=3)

    payload = contract_fix.run_v7_probe_threshold_contract_fix(storage_root=tmp_path)

    assert payload["dominantBlockerClass"] == "v7_probe_proposals_recovered"
    assert payload["nextCorrectiveFamily"] == "v7_probe_selection_followthrough_fix"


def test_threshold_contract_selects_acceptance_followthrough_when_selected_recover(tmp_path: Path) -> None:
    _write_candidate_bundle(tmp_path, raw_frames=6, filtered_frames=4, proposal_frames=3, selected_frames=2)

    payload = contract_fix.run_v7_probe_threshold_contract_fix(storage_root=tmp_path)

    assert payload["dominantBlockerClass"] == "v7_probe_selected_recovered"
    assert payload["nextCorrectiveFamily"] == "v7_probe_acceptance_followthrough_fix"


def test_threshold_contract_selects_preprocessing_path_when_raw_signal_still_zero(tmp_path: Path) -> None:
    _write_candidate_bundle(tmp_path, raw_frames=0)

    payload = contract_fix.run_v7_probe_threshold_contract_fix(storage_root=tmp_path)

    assert payload["dominantBlockerClass"] == "v7_probe_zero_raw_signal_after_low_conf_contract"
    assert payload["nextCorrectiveFamily"] == "v7_probe_preprocessing_path_fix"
