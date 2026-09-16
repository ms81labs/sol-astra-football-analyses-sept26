# Video-To-Analysis Strategic Lane Priority Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pick the next strategic lane after the v57 bounded-growth closeout and define a finite cascade that moves the video-to-analysis product toward a real finish instead of endless bounded queue continuation.

**Architecture:** Treat generated truth as authoritative. The v57 growth lane is closed, so the next work should first make the current product/release state operator-clear, then expand external benchmark confidence, then only resume bounded growth if a deliberate choice says more coverage is worth the artifact volume.

**Tech Stack:** Python saved-artifact batch scripts, pytest, FastAPI route bindings in `backend/app/main.py`, generated JSON truth under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/`, markdown roadmap docs under `docs/` and `memorybank/`.

---

## Current Authoritative State

The current stop gate is:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_growth_lane_closeout_readout_v57/
    growth_lane_closeout_readout_summary.json
```

Current truth:

```text
goalAchieved = true
primaryBlocker = null
growthLaneCloseoutReady = true
growthLaneClosedAtSnapshotDir = video_to_analysis_next_sample_selection_snapshot_v57
growthLaneClosedAtVersion = 57
autoContinueBoundedGrowthRecommended = false
manualStrategicChoiceRequired = true
nextRecommendedNextLever = manual_strategic_lane_selection_required
```

The strategic selector now agrees:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_next_strategic_lane_selection_v1/
    next_strategic_lane_selection_summary.json

selectedStrategicLane = manual_strategic_lane_selection_required
growthLaneCloseoutManualStrategicChoiceRequired = true
nextRecommendedNextLever = manual_strategic_lane_selection_required
```

Guardrails remain clean:

```text
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalMatchStorageMutationExecuted = false
```

## Lane Analysis

### Lane 1: Product / Operator Polish

Current evidence:

```text
video_to_analysis_operator_dashboard_polish_v1/operator_dashboard_polish_summary.json
goalAchieved = true
primaryBlocker = null
operatorDashboardRouteReady = true
apiRouteStatusCode = 200
htmlRouteStatusCode = 200
```

Related operator artifacts also passed:

```text
video_to_analysis_operator_handoff_pack_v1
video_to_analysis_operator_handoff_route_binding_v1
video_to_analysis_user_facing_release_readout_v1
video_to_analysis_release_readout_route_binding_v1
```

Strength:

- Highest user-value polish lane.
- Converts the current generated truth into something a human can trust quickly.
- Low risk because it should be route/UI/report binding over existing generated truth, not detector/training work.

Gap:

- Existing product/readout artifacts were originally built around older closeout contexts and then updated by docs. The operator-facing dashboard/readout should explicitly surface the v57 closeout and the manual strategic choice.
- The user still feels lost, so the product layer is not yet doing enough orientation.

Verdict:

```text
Priority = P0, but combine with release/acceptance packaging.
```

### Lane 2: External Benchmark / SoccerNet Lane

Current evidence:

```text
football_external_benchmark_harness_prep_v1/external_benchmark_harness_summary.json
goalAchieved = true
primaryBlocker = null

football_external_benchmark_bounded_real_execution_v1/bounded_real_execution_summary.json
goalAchieved = true
primaryBlocker = null

football_external_benchmark_real_report_and_product_binding_v1/real_report_and_product_binding_summary.json
goalAchieved = true
primaryBlocker = null
```

SoccerNet-specific lanes also have meaningful completed artifacts:

```text
football_external_soccernet_full_analysis_lane_closeout_v1
football_external_soccernet_analysis_product_lane_closeout_v1
football_external_soccernet_video_analysis_dry_run_v1
```

Strength:

- Best lane for real credibility and future model/product quality.
- Aligns with the research direction: calibration, game-state output, ball/player/team/event layers.
- Gives the product a meaningful "works beyond our trim" story.

Gap:

- Access and storage are easy to get wrong.
- Some product bridge summary naming appears drift-prone; do not assume every SoccerNet product bridge artifact is still at the path older docs mention.
- This lane needs bounded source governance first, not bulk downloading.

Verdict:

```text
Priority = P1 after the operator/release truth surface is current.
```

### Lane 3: Resume Bounded Growth Intentionally

Current evidence:

```text
video_to_analysis_next_sample_selection_snapshot_v57
candidateSampleCount = 3
nextRecommendedNextLever = video_to_analysis_bounded_next_sample_execution_approval

video_to_analysis_growth_lane_closeout_readout_v57
autoContinueBoundedGrowthRecommended = false
manualStrategicChoiceRequired = true
```

Strength:

- The chain is proven and repeatable.
- The v57 queue remains valid optional input.

Gap:

- It no longer answers a high-value unknown.
- Running more bounded queues creates more artifacts and can look like progress while not changing the finish-line answer.

Verdict:

```text
Priority = P3. Only resume if the operator explicitly chooses coverage growth as the goal.
```

### Lane 4: Release / Acceptance Packaging

Current evidence:

```text
video_to_analysis_release_candidate_closeout_v1
video_to_analysis_release_completion_summary_v1
video_to_analysis_acceptance_report_route_binding_v1
video_to_analysis_user_facing_release_readout_v1
video_to_analysis_post_release_monitoring_closeout_v1
```

Strength:

- This is the fastest path to making the project feel finished.
- It can consolidate all done lanes into one current, route-bound acceptance/readout surface.
- It gives a clean yes/no answer: "Can a user supply/select a video and get a trustworthy analysis report without manual debugging?"

Gap:

- Needs a current final package that explicitly includes v57 closeout and the manual strategic decision point.
- The release/readout route should not tell an older v38 story while generated truth says v57.

Verdict:

```text
Priority = P0. Do this first, paired with product/operator polish.
```

## Recommended Priority

```text
P0: Current Release/Acceptance + Operator Decision Surface
P1: External Benchmark / SoccerNet Bounded Product Validation
P2: Product Intelligence Roadmap From Research Notes
P3: Optional Bounded Growth Continuation
```

Why this order:

```text
1. The system already works; the user confidence gap is now product/readout clarity.
2. External/SoccerNet is the next source of real credibility, but only after the current product surface is unambiguous.
3. The research-driven intelligence roadmap matters, but it should be designed after the current release truth is packaged.
4. Bounded growth is proven and optional; more loops are not the finish line.
```

## Finite Cascade Plan

### Task 1: Current Release/Acceptance + Operator Decision Surface

**Purpose:** Create a current v57-aware product/release surface that tells the operator exactly where the project is and what decisions remain.

**Files:**

- Create: `backend/scripts/run_video_to_analysis_current_release_acceptance_decision_surface.py`
- Create: `backend/tests/test_run_video_to_analysis_current_release_acceptance_decision_surface.py`
- Write artifacts under:
  - `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/video_to_analysis_current_release_acceptance_decision_surface_v1/`
- Modify if needed:
  - `backend/app/main.py`
  - `backend/tests/test_api.py`
  - `SESSION-HANDOFF.md`
  - `memorybank/activeContext.md`
  - `memorybank/currentRoadmap.md`
  - `memorybank/progress.md`
  - `docs/video-to-analysis-finish-line-roadmap-guide.md`

**Inputs:**

```text
video_to_analysis_growth_lane_closeout_readout_v57/growth_lane_closeout_readout_summary.json
video_to_analysis_next_strategic_lane_selection_v1/next_strategic_lane_selection_summary.json
video_to_analysis_release_completion_summary_v1/release_completion_summary.json
video_to_analysis_operator_dashboard_polish_v1/operator_dashboard_polish_summary.json
video_to_analysis_acceptance_report_route_binding_v1/acceptance_report_route_binding_summary.json
video_to_analysis_release_readout_route_binding_v1/release_readout_route_binding_summary.json
video_to_analysis_post_release_monitoring_closeout_v1/post_release_monitoring_closeout_summary.json
```

**Outputs:**

```text
current_release_acceptance_decision_surface_summary.json
current_operator_decision_model.json
current_route_readiness_audit.json
current_guardrail_audit.json
decision_matrix.json
batch_outcome_analysis.json
batch_outcome_analysis.md
```

**Pass gates:**

```text
goalAchieved = true
primaryBlocker = null
releaseRuntimeComplete = true
operatorDashboardRouteReady = true
acceptanceReportRouteReady = true
releaseReadoutRouteReady = true
growthLaneClosedAtVersion = 57
selectedStrategicLane = manual_strategic_lane_selection_required
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
```

**Failsafes:**

```text
Attempt 1: current_release_acceptance_decision_surface
  Build the current decision surface from generated truth.

Attempt 2: route_truth_reference_repair
  If routes point at stale readout context, repair route bindings or view model references only.

Attempt 3: release_acceptance_blocker_summary
  If current acceptance cannot be packaged, stop with one blocker:
    video_to_analysis_current_release_route_stale
    video_to_analysis_current_acceptance_truth_missing
    video_to_analysis_current_operator_decision_surface_gap
```

**Expected next lever on pass:**

```text
football_external_soccernet_bounded_product_validation_plan
```

### Task 2: External Benchmark / SoccerNet Bounded Product Validation

**Purpose:** Use SoccerNet/external artifacts to prove the product handles real external-style sources without bulk download or storage chaos.

**Files:**

- Create: `backend/scripts/run_football_external_soccernet_bounded_product_validation_plan.py`
- Create: `backend/tests/test_run_football_external_soccernet_bounded_product_validation_plan.py`
- Write artifacts under:
  - `football_external_soccernet_bounded_product_validation_plan_v1/`

**Inputs:**

```text
football_external_benchmark_real_report_and_product_binding_v1/real_report_and_product_binding_summary.json
football_external_soccernet_analysis_product_lane_closeout_v1/analysis_product_lane_closeout_summary.json
football_external_soccernet_full_analysis_lane_closeout_v1/full_analysis_lane_closeout_summary.json
docs/foot-soccer-deepresearch.md
```

**Outputs:**

```text
soccernet_bounded_product_validation_plan.json
soccernet_source_governance_audit.json
soccernet_existing_artifact_inventory.json
soccernet_storage_budget_audit.json
soccernet_product_gap_matrix.json
decision_matrix.json
batch_outcome_analysis.json/md
```

**Pass gates:**

```text
no bulk download
existingArtifactReusePlanned = true
sourceGovernanceReady = true
storageBudgetReady = true
productValidationSlices >= 3
nextRecommendedNextLever = football_external_soccernet_bounded_product_validation_execution_approval
```

**Failsafes:**

```text
Attempt 1: soccernet_bounded_product_validation_plan
  Plan validation from existing bounded artifacts and approved source handles.

Attempt 2: soccernet_source_inventory_repair
  If artifact paths drift, rebuild inventory and route only from existing local truth.

Attempt 3: soccernet_validation_blocker_summary
  Stop with exactly one blocker:
    soccernet_existing_artifact_inventory_gap
    soccernet_source_governance_gap
    soccernet_storage_budget_gap
    soccernet_product_validation_slice_gap
```

### Task 3: Product Intelligence Roadmap From Research Notes

**Purpose:** Convert `docs/foot-soccer-deepresearch.md` into a practical next-generation product roadmap without mixing it into the v7.2 runtime finish.

**Files:**

- Create: `backend/scripts/run_video_to_analysis_research_to_product_intelligence_roadmap.py`
- Create: `backend/tests/test_run_video_to_analysis_research_to_product_intelligence_roadmap.py`
- Write artifacts under:
  - `video_to_analysis_research_to_product_intelligence_roadmap_v1/`

**Outputs:**

```text
research_capability_map.json
metric_pitch_coordinate_gap_audit.json
game_state_output_contract_plan.json
calibration_tracking_event_lane_plan.json
decision_matrix.json
batch_outcome_analysis.json/md
```

**Pass gates:**

```text
currentV72RuntimeScopePreserved = true
futureCapabilityLanesDefined >= 4
gameStateParquetContractDrafted = true
metricPitchCoordinateGapIdentified = true
noTrainingExecuted = true
noRuntimeMutationExecuted = true
```

**Failsafes:**

```text
Attempt 1: research_to_product_intelligence_roadmap
Attempt 2: research_scope_repair
Attempt 3: research_lane_blocker_summary
```

### Task 4: Optional Bounded Growth Continuation

**Purpose:** Resume bounded growth only if the operator explicitly chooses more coverage after Tasks 1-3.

**Inputs:**

```text
video_to_analysis_next_sample_selection_snapshot_v57/next_sample_selection_snapshot_summary.json
```

**Required operator decision:**

```text
operatorStrategicLaneChoice = resume_bounded_growth_intentionally
```

**Pass gates:**

```text
manualStrategicChoiceRecorded = true
growthLaneClosedAtVersion = 57
newBoundedGrowthGoalDeclared = true
storageBudgetStillSafe = true
```

**Failsafes:**

```text
Attempt 1: bounded_growth_intent_recording
Attempt 2: bounded_growth_storage_and_queue_recheck
Attempt 3: bounded_growth_blocker_summary
```

Do not run this lane just because the queue exists.

## Recommended First Batch To Execute

```text
video_to_analysis_current_release_acceptance_decision_surface
```

This is the right first batch because it resolves the human confusion problem, locks the v57 closeout into product-facing truth, and gives the next worker one clear decision surface instead of a pile of historical lanes.

## Stop Conditions

Stop and ask for an operator choice only after Task 1 writes a current decision surface with:

```text
primaryBlocker = null
selectedStrategicLane = manual_strategic_lane_selection_required
availableStrategicChoices = [
  product_operator_polish,
  external_benchmark_soccernet_lane,
  resume_bounded_growth_intentionally,
  release_acceptance_packaging
]
recommendedStrategicChoice = external_benchmark_soccernet_lane
```

If Task 1 cannot write that, do not proceed to SoccerNet, bounded growth, or release mutation. Fix the product/readout truth first.

