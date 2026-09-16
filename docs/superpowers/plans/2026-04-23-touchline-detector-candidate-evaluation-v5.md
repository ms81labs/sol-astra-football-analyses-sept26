# Touchline Detector Candidate Evaluation v5

## History

- This checklist is completed evaluation-cycle history, not the active todo source anymore.
- The active promotion-validation checklist is `docs/superpowers/plans/2026-04-23-touchline-detector-candidate-promotion-v6.md`.
- `touchline_detector_candidate_v4` evaluation is closed as blocked history because the training-quality gate proved its validation split was non-informative.
- The completed blocker-cycle checklist is `docs/superpowers/plans/2026-04-23-phase-3-v4-quality-gate-remediation.md`.

## Unattended Loop Contract

- The canonical start point is the first unchecked task in the current checklist.
- The latest completed bounded batch is `touchline_detector_candidate_evaluation_v6`.
- The promotion-validation follow-through is now recorded in `docs/superpowers/plans/2026-04-23-touchline-detector-candidate-promotion-v6.md`.
- Do not ask for approval; make reasonable assumptions from repo truth.
- Complete one batch fully before moving to the next unchecked batch in this same file.
- Stop only after verified batch completion or a real unresolved blocker that cannot be resolved from repo truth.
- Update memorybank and `SESSION-HANDOFF.md` only from generated artifacts.
- Do not make any success claim without fresh verification evidence.
- After one batch completes, immediately continue to the next unchecked batch in the same checklist file.
- Do not open a new todo file while this checklist still governs the lane.
- Do not change phases, invent new lanes, or privilege speculative docs over generated artifacts.
- This contract supports unattended continuation inside a live session only; it does not self-wake after the session ends without an external re-invocation source.

## Acceptance Criteria

- [x] This file now stands as completed evaluation-cycle history for the v5-to-v6 bounded detector lane.
- [x] The evaluation driver resolves or explicitly pins `touchline_detector_candidate_v5`, not `touchline_detector_candidate_v3`.
- [x] The bounded evaluation uses the standing failing-source reference `101 / 98 / false / 0.812`.
- [x] The bounded policy stays narrow: one screen, always the v5 baseline proof, extra proof legs only if earned.
- [x] Candidate-local evaluation artifacts exist under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v5/evaluation_v1/`.
- [x] Suite truth is regenerated from the evaluation artifacts.
- [x] `runpodctl pod list --all -o json` is `[]` at closeout.
- [x] v5 did not win, the roadmap stayed on `evaluate_touchline_detector_candidate`, and the next corrective sub-batch is appended to this file.

## Ordered Tasks

- [x] Fix active-candidate resolution so a gate-cleared candidate is not excluded merely because its training batch closeout had `roadmapAdvanceAllowed = false`.
- [x] Add an explicit `--candidate-name` override to the evaluation entrypoint and use `touchline_detector_candidate_v5` for the real batch.
- [x] Keep the existing bounded screen/proof policy unchanged.
- [x] Run the real bounded v5 evaluation batch and persist the generated closeout artifacts.
- [x] Regenerate suite truth surfaces from the new evaluation artifacts.
- [x] Update roadmap, memory bank, and handoff so this file becomes the only active todo source for the current evaluation cycle.

## Iteration Rule

- If the batch goal is not achieved, do not create a new free-floating todo file.
- Append the next corrective sub-batch to this file and stay inside Phase 3 until the evaluation lane produces a promotable candidate or a new generated blocker narrows the next fix.

## Latest Generated Truth

- `evaluationBatchName = touchline_detector_candidate_evaluation_v5`
- `trainingCandidateName = touchline_detector_candidate_v5`
- `screenCompleted = true`
- `screenWinningDetectorLabel = yolov10n.pt_baseline_full_detector`
- `candidateBaselineProofRan = true`
- `candidateBaselineProductBeatsPlateau = false`
- `baselineControlProofRan = false`
- `candidateCompoundThinProofRan = false`
- `executionBlockersResolved = true`
- `evaluationReachedProductComparison = true`
- `readyForPromotion = false`
- `primaryBlocker = candidate_baseline_did_not_beat_plateau`
- `goalAchieved = false`
- `roadmapAdvanceAllowed = false`
- `nextRecommendedNextLever = evaluate_touchline_detector_candidate`

## Next Corrective Sub-Batch — V5 Baseline-Proof Delta Analysis

### Purpose

- Use the generated v5 evaluation artifacts to explain why the gate-cleared candidate still produced `0 / 0 / false` in the bounded baseline proof.
- Stay in Phase 3 and keep this file as the only active todo source.

### Bounded Inputs

- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v5/evaluation_v1/`
- `backend/storage/pod_cycles/touchline-detector-candidate-v5-probe-assist-baseline-20260423150042/`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v3/evaluation_v1/`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v3/failure_analysis_v1/`
- `backend/storage/pod_cycles/yolov10n-pt-baseline-full-detector-baseline-control-20260422224502/`

### Ordered Tasks

- [x] Inspect the v5 baseline proof deltas directly against `101 / 98 / false / 0.812`.
- [x] Produce a stage-wise failing-source diff sheet for v5 vs the frozen baseline:
  proposal signal, raw probe rows, filtered probe rows, accepted ball frames, supported accepted ratio, raw edge share, unsupported edge share, and gap profile.
- [x] Inspect the auxiliary ball-probe contribution frame by frame to see whether `touchline_detector_candidate_v5` adds any useful recovered rows over the frozen baseline.
- [x] Decide from saved artifacts whether the next fix belongs in model/data quality again or in probe-integration behavior.
- [x] If the saved artifacts still expose summary-surface drift, queue `canonical_proof_summary_contract_v1` as the next implementation batch before any broader detector retraining.
- [x] If the saved artifacts point to projection/calibration mismatch rather than detector signal loss, queue `pitch_homography_hardening_v1` instead of another data-first detector batch.
- [x] Write the next generated English achieved/not-achieved closeout and keep the roadmap pinned unless a later bounded evaluation actually wins.

### Acceptance Criteria

- [x] Candidate-local failure-analysis artifacts exist under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v5/failure_analysis_v1/`.
- [x] The generated diagnosis names exactly one next implementation batch.
- [x] The diagnosis proves whether summary drift or calibration suspicion should override the default detector/probe corrective batch choice.
- [x] Suite truth is regenerated from the failure-analysis artifacts.
- [x] `runpodctl pod list --all -o json` remains `[]` at closeout.

### Latest Generated Truth

- `trainingCandidateName = touchline_detector_candidate_v5`
- `previousCandidateName = touchline_detector_candidate_v3`
- `rootCauseClass = auxiliary_probe_zero_raw_rows`
- `changeFromPreviousCandidateClass = no_observable_improvement`
- `recommendedFixClass = model_data_quality`
- `recommendedFixFocus = proposal_signal_generation`
- `summarySurfaceDriftDetected = false`
- `calibrationSuspicionDetected = false`
- `nextImplementationBatchRecommendation = touchline_detector_candidate_v5_proposal_signal_generation_fix_v1`
- `nextRecommendedNextLever = evaluate_touchline_detector_candidate`

## Next Corrective Sub-Batch — canonical_proof_summary_contract_v1

### Purpose

- Remove the confirmed summary-contract drift before another detector-side corrective batch so the pipeline, judge-facing surfaces, and suite summarization all speak the same compact proof language.
- Keep the primary extraction blocker explicit: missing proposal signal remains the underlying detector issue even though the next implementation batch is a summary-contract repair.

### Ordered Tasks

- [x] Add one canonical proof-summary builder that emits the judge-facing fields from saved proof artifacts and live pipeline output.
- [x] Make the proof summary include `eventFamilyCount` alongside the existing accepted-ball, support, possession, and truth-gate fields.
- [x] Make the evaluation lane, failure-analysis lane, and suite summarization consume the same canonical proof-summary surface instead of partially drifting objects.
- [x] Add tests that prove the canonical summary stays aligned across proof output, judge-facing fields, and suite ingestion.
- [x] Regenerate the v5 failure-analysis interpretation after the contract repair and keep this file as the only active todo source.

### Latest Generated Truth

- `trainingCandidateName = touchline_detector_candidate_v5`
- `rootCauseClass = auxiliary_probe_zero_raw_rows`
- `changeFromPreviousCandidateClass = no_observable_improvement`
- `recommendedFixClass = model_data_quality`
- `recommendedFixFocus = proposal_signal_generation`
- `summarySurfaceDriftDetected = false`
- `calibrationSuspicionDetected = false`
- `nextImplementationBatchRecommendation = touchline_detector_candidate_v5_proposal_signal_generation_fix_v1`
- `nextRecommendedNextLever = evaluate_touchline_detector_candidate`

## Next Corrective Sub-Batch — touchline_detector_candidate_v5_proposal_signal_generation_fix_v1

### Purpose

- Stay in Phase 3 and use the repaired v5 failure-analysis truth to target the actual next blocker: proposal signal generation is still flat at `0` versus the diagnostic baseline.
- Keep this file as the only active todo source and do not reopen the summary-contract lane unless generated artifacts regress again.
- Build a runtime-aligned `proposal_windows_075` export, retrain exactly one new candidate `touchline_detector_candidate_v6`, and only return to bounded evaluation if the strengthened training-quality gate passes.

### Live Blocker

- `candidateMaxProposalDetectedFramesAcrossProfiles = 0`
- `baselineMaxProposalDetectedFramesAcrossProfiles = 21`
- the previous proposal batch was crop-valid but runtime-invalid: it trained on only `111` crops with `99` positives and `12` negatives, which did not match the live proposal-window family that succeeds in the diagnostic baseline

### Bounded Inputs

- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v5/failure_analysis_v1/`
- `backend/storage/training_prep/touchline_model_data_quality_fix_v1/`
- `backend/storage/training_prep/touchline_validation_gate_remediation_v1/`
- `backend/storage/pod_cycles/yolov10n-pt-baseline-full-detector-baseline-control-20260422224502/`

### Ordered Tasks

- [x] Replace the old placeholder with this decision-complete corrective batch and keep this checklist as the only active todo source.
- [x] Build `backend/storage/training_prep/touchline_proposal_signal_generation_fix_v2/` from the live `proposal_windows_075` runtime window family instead of repeating the old tight-crop export.
- [x] Export positives only from trusted reviewed or accepted-ball-backed boxes whose runtime proposal windows overlap the trusted ball box.
- [x] Regenerate confirmed and mined negatives through the same runtime proposal-window builder and materially exceed the old `12`-negative export.
- [x] Preserve the repaired curation-unit split: keep the control negative unit in `val`, keep the selected positive failing-source unit in `val`, and inherit split from parent units for all proposal-window examples.
- [x] Retrain exactly one new candidate `touchline_detector_candidate_v6` with the same v5 recipe so export alignment is the intended variable.
- [x] Extend the authoritative training-quality gate with a proposal-window sanity pass and require it for `readyForDetectorEvaluation`.
- [x] Regenerate suite truth, memorybank, and handoff from the generated v6 artifacts only.
- [x] Keep the roadmap pinned on `evaluate_touchline_detector_candidate` unless a later bounded evaluation actually wins.

### Acceptance Criteria

- [x] Non-empty `backend/storage/training_prep/touchline_proposal_signal_generation_fix_v2/` exists.
- [x] Export truth proves `windowFamily = proposal_windows_075`.
- [x] Proposal-window negatives materially exceed the old `12`-negative batch.
- [x] Non-empty `backend/storage/trained_detector_candidates/touchline_detector_candidate_v6/` exists with `weights/best.pt`.
- [x] The strengthened training-quality gate passes for v6, including non-zero proposal-window sanity detections.
- [x] Suite truth is regenerated from the latest proposal-signal fix artifact instead of hardcoded `v1`.
- [x] `runpodctl pod list --all -o json` is `[]` at closeout.

### Latest Generated Truth

- `proposalSignalFixBatchName = touchline_proposal_signal_generation_fix_v2`
- `trainingCandidateName = touchline_detector_candidate_v6`
- `windowFamily = proposal_windows_075`
- `proposalPositiveExampleCount = 164`
- `proposalNegativeExampleCount = 220`
- `proposalWindowValidationPositiveImageCount = 44`
- `proposalWindowSanityDetectedImageCount = 31`
- `trainingCompleted = true`
- `weightsReady = true`
- `trainingQualityGatePassed = true`
- `readyForDetectorEvaluation = true`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = false`
- `nextRecommendedNextLever = evaluate_touchline_detector_candidate`

## Completed Bounded Sub-Batch — touchline_detector_candidate_evaluation_v6

### Purpose

- Run the first bounded evaluation for the runtime-window-aligned, gate-cleared `touchline_detector_candidate_v6`.
- Keep this file as the only active todo source and stay in Phase 3 unless the generated v6 evaluation actually earns promotion.

### Ordered Tasks

- [x] Evaluate `touchline_detector_candidate_v6` as the active candidate under the standing bounded contract `101 / 98 / false / 0.812`.
- [x] Reuse the existing narrow screen/proof policy with the frozen runtime baseline unchanged.
- [x] Persist candidate-local v6 evaluation artifacts and regenerate suite truth from them.
- [x] Update memorybank and handoff from generated evaluation truth only.
- [x] Allow the roadmap to advance only because the generated v6 evaluation closeout says the goal was achieved.

### Acceptance Criteria

- [x] Candidate-local evaluation artifacts exist under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v6/evaluation_v1/`.
- [x] The real batch evaluates `touchline_detector_candidate_v6`, not an older candidate.
- [x] `runpodctl pod list --all -o json` is `[]` at closeout.
- [x] Roadmap advance happened only because the generated v6 evaluation closeout says the goal was achieved.

### Latest Generated Truth

- `evaluationBatchName = touchline_detector_candidate_evaluation_v6`
- `trainingCandidateName = touchline_detector_candidate_v6`
- `screenCompleted = true`
- `screenWinningDetectorLabel = yolov10n.pt_baseline_full_detector`
- `candidateBaselineProofRan = true`
- `candidateBaselineProductBeatsPlateau = true`
- `baselineControlProofRan = true`
- `candidateCompoundThinProofRan = true`
- `candidateBeatsSameBatchBaselineControl = true`
- `readyForPromotion = true`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `nextRecommendedNextLever = promote_touchline_detector_candidate`

### Next Lane Trigger

- This checklist completed its bounded-evaluation goal with a promotable v6 result.
- The next honest move was to open the promotion-validation lane from generated truth, not to rerun bounded detector evaluation.
- That follow-through now lives in `docs/superpowers/plans/2026-04-23-touchline-detector-candidate-promotion-v6.md`.

## Research Suggestions Absorbed

- Accepted now:
  use stage-wise evaluation, not only end-state promotion flags
- Accepted now:
  tighten future viability/truth gates around supported signal, unsupported edge-heavy frames, and gap profile instead of raw edge share alone
- Accepted conditionally:
  add `canonical_proof_summary_contract_v1` if the v5 delta analysis shows contract drift between pipeline, judge, and suite surfaces
- Accepted conditionally:
  add `pitch_homography_hardening_v1` only if the v5 delta analysis implicates calibration/projection rather than detector proposal loss
- Accepted later:
  build a reviewed failure taxonomy, source-manifest expansion, and a small gold set after the current corrective batch narrows the actual extraction blocker
- Accepted later:
  start semantics in order `team assignment -> owner assignment -> possession chains -> event layer`
- Not accepted as the next move:
  another v4 evaluation, a rewind to Phase 1B as the primary lane, or downstream football semantics before extraction robustness improves
