# Touchline Detector Candidate Promotion v6

## History

- `touchline_detector_candidate_evaluation_v6` already achieved its bounded evaluation goal and marked `touchline_detector_candidate_v6` as `readyForPromotion = true`.
- The completed evaluation-cycle checklist is `docs/superpowers/plans/2026-04-23-touchline-detector-candidate-evaluation-v5.md`.
- The active todo source has now moved to `docs/superpowers/plans/2026-04-23-promoted-v6-failing-source-robustness-validation.md`.

## Unattended Loop Contract

- The canonical start point is the first unchecked task in this checklist.
- The latest completed batch is `touchline_detector_candidate_promotion_validation_v1`.
- This lane is `Validation First`: promotion for controlled/internal use does not equal a runtime-default switch.
- Do not ask for approval; make reasonable assumptions from repo truth.
- Complete one batch fully before moving to the next truthful step.
- Stop only after verified batch completion or a real unresolved blocker that cannot be resolved from repo truth.
- Update memorybank and `SESSION-HANDOFF.md` only from generated artifacts.
- Do not make any success claim without fresh verification evidence.
- If this checklist has no unchecked tasks left, stop and write the next strict plan before continuing.
- Do not change phases, invent new lanes, or privilege speculative docs over generated artifacts.
- This contract supports unattended continuation inside a live session only; it does not self-wake after the session ends without an external re-invocation source.

## Acceptance Criteria

- [x] One new strict promotion-validation checklist exists for the v6 lane.
- [x] Promotion validation reads only existing generated truth from the v6 training, evaluation, and suite surfaces.
- [x] Candidate-local promotion artifacts exist under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v6/promotion_v1/`.
- [x] A suite-level promotion artifact exists under `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/`.
- [x] An internal promoted-candidate registry exists under `backend/storage/runtime/`.
- [x] `touchline_detector_candidate_v6` is promoted for controlled/internal runs.
- [x] `runtimeDefaultChanged = false` and `runtimeDefaultChangeAllowed = false`.
- [x] `suiteVerdict = baseline_not_robust` remains visible after the batch.
- [x] The next lane after this batch is not another v6 evaluation rerun.

## Ordered Tasks

- [x] Create one promotion-validation batch driver that reads only generated v6 truth.
- [x] Validate the promotion gate from the existing v6 evaluation, evaluation contract, training summary, and suite surfaces.
- [x] Write candidate-local `promotion_v1` artifacts, one suite-level promotion artifact, and one promoted-candidate registry artifact.
- [x] Preserve the runtime contract for controlled runs without changing runtime defaults.
- [x] Extend suite truth ingestion with `detectorCandidatePromotionDiagnosis`.
- [x] Update memorybank, handoff, and unattended-loop surfaces from generated promotion truth only.

## Iteration Rule

- Promotion validation does not authorize a runtime-default flip by itself.
- If runtime defaults are ever going to change, that must happen in a later strict checklist backed by generated evidence that clears the remaining promotion blockers.
- Do not reopen bounded v6 evaluation or invent a new detector-training lane without generated truth that requires it.

## Latest Generated Truth

- `promotionBatchName = touchline_detector_candidate_promotion_validation_v1`
- `trainingCandidateName = touchline_detector_candidate_v6`
- `promotionValidated = true`
- `promotedForControlledRuns = true`
- `runtimeDefaultChanged = false`
- `runtimeDefaultChangeAllowed = false`
- `runtimeDefaultChangeBlockers = [failing_source_not_viable]`
- `candidateBaselineProductBeatsPlateau = true`
- `baselineControlProofRan = true`
- `candidateBeatsSameBatchBaselineControl = true`
- `goalAchieved = true`
- `roadmapAdvanceAllowed = true`
- `nextRecommendedNextLever = promote_touchline_detector_candidate`
- `suiteVerdict = baseline_not_robust`

## Completed History Note

- This validation-first promotion lane achieved its goal.
- `touchline_detector_candidate_v6` is now promoted for controlled/internal runs only.
- Runtime defaults remain frozen because `failing_source_not_viable` is still visible in the suite truth.
- Post-promotion robustness follow-through now lives in `docs/superpowers/plans/2026-04-23-promoted-v6-failing-source-robustness-validation.md`.
