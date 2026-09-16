# GPT-5.5 Review Report - 24 April

## Executive Summary

The current roadmap truth is coherent and appropriately conservative. `touchline_detector_candidate_v6` is promoted only for controlled/internal use, runtime defaults remain frozen, and the next honest batch is `promoted_v6_failing_source_retention_delta_analysis_v1`.

The promoted-v6 robustness validation did not clear the remaining blocker. The generated truth says the winning arm is `promoted_v6_baseline`, but it remains `source_robustness_weak` with `winningPassedPromotionGate = false`. The concrete blockers are `accepted_retention_below_guardrail` and `controlled_retention_below_guardrail`, even though failing-source edge share improved by `0.712`.

## Review Findings

### Medium: Runtime-default validation can be reached from an inconsistent promoted-robustness artifact

`resolve_source_robustness_recommended_next_lever` accepts the promoted robustness diagnosis `nextRecommendedNextLever` when it is one of the expected promotion/runtime levers and the promoted robustness candidate version is current enough.

Reference: `backend/scripts/run_source_robustness_batch.py:589`

The resolver does not also require the promoted robustness diagnosis to prove `winningPassedPromotionGate = true`, `goalAchieved = true`, and `roadmapAdvanceAllowed = true` before allowing `validate_promoted_touchline_runtime_default` or `validate_promoted_touchline_runtime_default_plus_best_thin`.

Current artifacts are safe because they consistently keep `nextRecommendedNextLever = promote_touchline_detector_candidate`. The risk is stale or partially inconsistent generated state: a future malformed validation summary could point to runtime-default validation while the gate did not actually pass.

Recommended fix:

- Gate runtime-default validation on all three success fields: `winningPassedPromotionGate`, `goalAchieved`, and `roadmapAdvanceAllowed`.
- If the promoted robustness gate failed, force the next lever to remain `promote_touchline_detector_candidate`.

### Low/Medium: `baseline_current` is sourced from the promoted runtime registry

The promoted robustness driver builds all arm specs from the promoted runtime registry. That means `baseline_current` gets `primaryDetectorModelPath` from `runtimeContract` rather than from the frozen suite baseline fingerprint.

Reference: `backend/scripts/run_promoted_touchline_detector_candidate_source_robustness_validation.py:121`

Current v6 is unaffected because the promoted registry and frozen baseline both use `yolov10n.pt`. The risk appears if a future promotion changes the primary detector path: the supposedly frozen `baseline_current` arm could silently stop being the frozen suite baseline.

Recommended fix:

- Build `baseline_current` from the suite manifest `baselineFingerprint`.
- Keep promoted arms sourced from the promoted runtime registry.
- Add a regression test where the promoted registry primary detector differs from the manifest baseline detector.

### Low: Next retention-delta batch cannot rely on raw `rows` in `arm_matrix.json`

The validation arm matrix preserves proof runs, source summaries, outcomes, and selected-cluster evidence paths, but it does not include raw row payloads in the emitted `arms[]` records.

Reference: `backend/scripts/run_promoted_touchline_detector_candidate_source_robustness_validation.py:994`

This is acceptable for the completed validation batch. It matters for the next batch because `promoted_v6_failing_source_retention_delta_analysis_v1` must explain the retention collapse. That batch should follow `proofRuns[].reusedEvidence.selectedClusterDeltaPath` and use source summaries rather than assuming row-level payloads exist in `arm_matrix.json`.

Recommended fix:

- In the retention-delta batch, load the selected-cluster deltas referenced by `proofRuns[].reusedEvidence.selectedClusterDeltaPath`.
- Treat `arm_matrix.json` as an index and summary surface, not the sole analytic substrate.

## Roadmap Position

The repo should keep the current strict roadmap posture:

- Keep `suiteVerdict = baseline_not_robust`.
- Keep `sourceRobustnessPromotionBlockers = [failing_source_not_viable]`.
- Do not rerun bounded v6 evaluation as the primary next move.
- Do not validate or switch runtime defaults yet.
- Treat `docs/superpowers/plans/2026-04-23-promoted-v6-failing-source-robustness-validation.md` as the active checklist.
- Work `promoted_v6_failing_source_retention_delta_analysis_v1` next.

## Artifact Read

The generated surfaces agree with the handoff:

- `validationBatchName = promoted_touchline_detector_candidate_robustness_validation_v1`
- `winningArmName = promoted_v6_baseline`
- `winningConfigOutcome = source_robustness_weak`
- `winningPassedPromotionGate = false`
- `winningPromotionBlockers = [accepted_retention_below_guardrail, controlled_retention_below_guardrail]`
- `winningFailingSourceEdgeShareImprovement = 0.712`
- `runtimeDefaultChanged = false`
- `nextRecommendedNextLever = promote_touchline_detector_candidate`

This supports the current conclusion: v6 improved edge-share behavior but collapsed accepted and controlled retention enough that runtime-default promotion remains blocked.

## Verification

Fresh targeted verification was run during the planning review:

```bash
python3 -m pytest backend/tests/test_run_pod_proof_cycle.py backend/tests/test_run_promoted_touchline_detector_candidate_source_robustness_validation.py backend/tests/test_run_source_robustness_batch.py backend/tests/test_unattended_roadmap_loop.py backend/tests/test_memory_bank_structure.py -q
```

Result:

```text
72 passed in 14.65s
```

The full backend suite was not re-run during this planning review.

## Final Recommendation

Do not code a new corrective mechanism yet. First run `promoted_v6_failing_source_retention_delta_analysis_v1` to explain why edge share improved from the promoted v6 evidence while accepted and controlled retention fell below guardrails. The next implementation batch should be named only after that retention collapse is classified.
