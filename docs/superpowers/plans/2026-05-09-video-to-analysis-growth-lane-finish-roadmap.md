# Video-To-Analysis Growth Lane Finish Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the current video-to-analysis growth-lane work visible, finite, and auditable, then stop the active module at a clear closeout gate instead of looping forever.

**Architecture:** The promoted v7.2 runtime and operator/product lane are already complete. The active work is a bounded generated-truth growth lane that repeatedly consumes three-sample queues, proves exhaustion, replenishes bounded source pools, executes five-case scaleouts, route-smokes outputs, and writes the next queue snapshot. This plan defines a finite continuation target and the closeout conditions for ending this module.

**Tech Stack:** Python batch scripts under `backend/scripts/`, generated truth under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/`, live heartbeat at `backend/storage/automation/unattended_roadmap_loop_status.json`, roadmap docs under `memorybank/` and `docs/`.

---

## Legend

```text
[GREEN]  Verified complete from generated artifacts and tests.
[NEXT]   Immediate next work.
[OPEN]   Planned but not run yet.
[STOP]   Required stop/check gate before continuing.
[BLOCK]  Failure route if generated truth says the path is unsafe.
```

## What This Module Is

This module is:

```text
video-to-analysis bounded real-video growth lane
```

It is not:

```text
model training
detector promotion
runtime-default mutation
bulk dataset download
normal match storage mutation
```

The product/runtime finish line is already crossed. The current module is expanding and proving more bounded real-video coverage while preserving guardrails.

## Current Live State

Authoritative live source:

```text
backend/storage/automation/unattended_roadmap_loop_status.json
```

Current generated truth as of 2026-05-09 after the finite growth tranche:

```text
activeBatchName = video_to_analysis_next_sample_selection_snapshot
itemStatus = source_pool_replenishment_v23_scaleout_v38_closed_next_sample_selection_ready
primaryBlocker = null
nextRecommendedNextLever = video_to_analysis_bounded_next_sample_execution_approval
latestSnapshot = video_to_analysis_next_sample_selection_snapshot_v38
```

Active v38 queue:

```text
operator_uploaded_local_video_replenishment_candidate_v23
soccernet_bounded_224p_member_replenishment_candidate_v23
existing_normal_storage_video_replenishment_candidate_v23
```

Current guardrails:

```text
trainingExecuted = false
detectorEvaluationExecuted = false
candidateEvaluationExecuted = false
candidateReadyForEvaluation = false
promotionMutationExecuted = false
promotionReady = false
runtimeDefaultMutationExecuted = false
runtimeDefaultMutationAllowed = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalMatchStorageMutationExecuted = false
generatedTruthDeleteAllowed = false
cleanupMutationExecuted = false
```

## Green Board

- [x] [GREEN] v7.2 promoted runtime/product lane is operationally complete.
- [x] [GREEN] Steady-state monitoring passed and old failing-source blocker stayed dead.
- [x] [GREEN] Operational backlog prioritization exists and passed.
- [x] [GREEN] Storage retention and artifact hygiene plan exists and passed.
- [x] [GREEN] Operator dashboard polish exists and passed.
- [x] [GREEN] External real-source path consolidation exists and passed.
- [x] [GREEN] Real-video scaleout plan exists and passed.
- [x] [GREEN] Recurring steady-state monitoring schedule exists and passed.
- [x] [GREEN] Operational sprint closeout exists and passed.
- [x] [GREEN] Growth-lane decision snapshot exists and selected bounded real-video scaleout execution.
- [x] [GREEN] Bounded growth lane reached `video_to_analysis_next_sample_selection_snapshot_v33`.
- [x] [GREEN] Last verified continuation consumed v32 through v125-v127, exhausted at v128, replenished v18, scaleout v33 passed `5 / 5`, and wrote v33.
- [x] [GREEN] Consume the v33 three-sample queue through v129-v131 and prove exhaustion at v132.
- [x] [GREEN] Replenish and scale out from the v33 exhaustion state to produce v34.
- [x] [GREEN] Run four more bounded growth cycles to reach a finite v38 stop gate.
- [x] [GREEN] Write the growth-lane closeout readout after v38 or earlier if a blocker/guardrail says stop.

## Finish Definition

This module ends when all of these are true:

```text
1. A finite growth tranche from v33 to v38 is complete, or generated truth blocks earlier.
2. The latest active snapshot is verified by an artifact audit.
3. Route smoke passed for every bounded next-sample report and every scaleout report in the tranche.
4. Guardrails stayed false: no training, no promotion, no runtime mutation, no downloads, no normal storage mutation, no generated-truth deletion.
5. Focused roadmap tests pass.
6. Full backend tests pass.
7. RunPod state is empty.
8. A closeout/readout section says either:
   - growth module complete, next strategic lane selected, or
   - growth module blocked, exact blocker and next family selected.
```

The end artifact for this module should be:

```text
docs/video-to-analysis-growth-lane-closeout-readout-2026-05-09.md
```

That closeout readout should not invent new truth. It should summarize generated artifacts and verification only.

## Planned Tranche To Finish This Module

### Task 1: Consume Current v33 Queue

**Files:**
- Read: `backend/storage/automation/unattended_roadmap_loop_status.json`
- Read: `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/video_to_analysis_next_sample_selection_snapshot_v33/next_sample_selection_snapshot_summary.json`
- Write artifacts under: `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/`

- [x] [GREEN] Run `video_to_analysis_bounded_next_sample_execution_approval_v129`.
- [x] [GREEN] Run `video_to_analysis_bounded_next_sample_execution_v129`.
- [x] [GREEN] Run `video_to_analysis_bounded_next_sample_report_route_binding_v129`.
- [x] [GREEN] Run `video_to_analysis_bounded_next_sample_closeout_v129`.
- [x] [GREEN] Run `video_to_analysis_scaleout_or_backlog_decision_snapshot_v129`.
- [x] [GREEN] Repeat the same chain for v130.
- [x] [GREEN] Repeat the same chain for v131.
- [x] [GREEN] Run `video_to_analysis_bounded_next_sample_execution_approval_v132` and require:

```text
primaryBlocker = video_to_analysis_bounded_next_sample_pool_exhausted
remainingCandidateSampleCount = 0
```

Failure adaptation:

```text
route smoke failure -> route repair, stop before continuing
guardrail mutation -> stop and write blocker
sample mismatch -> inspect latest snapshot and execution history before rerun
```

### Task 2: Replenish From v33 Exhaustion And Produce v34

**Files:**
- Write artifacts under: `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/`
- Update after verification:
  - `backend/storage/automation/unattended_roadmap_loop_status.json`
  - `SESSION-HANDOFF.md`
  - `memorybank/activeContext.md`
  - `memorybank/currentRoadmap.md`
  - `memorybank/progress.md`
  - `docs/video-to-analysis-finish-line-roadmap-guide.md`
  - `docs/video-to-analysis-finish-line-roadmap-completion-report-2026-05-08.md`

- [x] [GREEN] Run `video_to_analysis_source_and_artifact_cleanup_map_v131`.
- [x] [GREEN] Run insufficient refresh `video_to_analysis_real_video_scaleout_plan_refresh_v64`.
- [x] [GREEN] Run source sampling expansion `video_to_analysis_real_video_scaleout_source_sampling_expansion_v31`.
- [x] [GREEN] Run roadmap direction snapshot `video_to_analysis_next_roadmap_direction_snapshot_v19`.
- [x] [GREEN] Run source-pool replenishment plan `video_to_analysis_source_pool_replenishment_plan_v19`.
- [x] [GREEN] Run source-pool replenishment approval `video_to_analysis_source_pool_replenishment_approval_v19`.
- [x] [GREEN] Run refreshed scaleout plan `video_to_analysis_real_video_scaleout_plan_refresh_v65`.
- [x] [GREEN] Run scaleout approval `video_to_analysis_real_video_scaleout_execution_approval_v34`.
- [x] [GREEN] Run bounded scaleout `video_to_analysis_real_video_scaleout_bounded_execution_v34`.
- [x] [GREEN] Run report route binding `video_to_analysis_real_video_scaleout_report_route_binding_v34`.
- [x] [GREEN] Run lane closeout `video_to_analysis_real_video_scaleout_lane_closeout_v34`.
- [x] [GREEN] Run next sample snapshot `video_to_analysis_next_sample_selection_snapshot_v34`.

Success criteria:

```text
scaleoutPassedCaseCount = 5
apiRouteStatusCode = 200
htmlRouteStatusCode = 200
candidateSampleCount = 3
primaryBlocker = null
```

Failure adaptation:

```text
fresh source pool insufficient after replenishment -> route to source-pool blocker summary
scaleout pass count below 5 -> write exact scaleout blocker and stop
storage pressure -> run storage hygiene decision before more growth
```

### Task 3: Repeat Four More Growth Cycles To v38

**Files:**
- Same generated artifact root and living docs as Task 2.

- [x] [GREEN] v34 -> v35:

```text
sample executions v133-v135
exhaustion v136
cleanup v135
insufficient refresh v66
source sampling v32
roadmap v20
replenishment v20
scaleout refresh v67
scaleout v35
snapshot v35
```

- [x] [GREEN] v35 -> v36:

```text
sample executions v137-v139
exhaustion v140
cleanup v139
insufficient refresh v68
source sampling v33
roadmap v21
replenishment v21
scaleout refresh v69
scaleout v36
snapshot v36
```

- [x] [GREEN] v36 -> v37:

```text
sample executions v141-v143
exhaustion v144
cleanup v143
insufficient refresh v70
source sampling v34
roadmap v22
replenishment v22
scaleout refresh v71
scaleout v37
snapshot v37
```

- [x] [GREEN] v37 -> v38:

```text
sample executions v145-v147
exhaustion v148
cleanup v147
insufficient refresh v72
source sampling v35
roadmap v23
replenishment v23
scaleout refresh v73
scaleout v38
snapshot v38
```

Stop condition after each cycle:

```text
If any route smoke fails, if any guardrail flips, if scaleout pass count is not 5 / 5, or if generated truth selects a blocker other than the expected exhaustion transition, stop and write the blocker truth instead of forcing the next cycle.
```

### Task 4: Audit The Finite Tranche

**Files:**
- Read all generated artifacts from v129-v148 and scaleouts v34-v38.
- Write closeout readout:
  - `docs/video-to-analysis-growth-lane-closeout-readout-2026-05-09.md`

- [x] [GREEN] Audit each bounded next-sample execution:

```text
goalAchieved = true
primaryBlocker = null
apiRouteStatusCode = 200
htmlRouteStatusCode = 200
```

- [x] [GREEN] Audit each exhaustion proof:

```text
primaryBlocker = video_to_analysis_bounded_next_sample_pool_exhausted
remainingCandidateSampleCount = 0
```

- [x] [GREEN] Audit each scaleout:

```text
scaleoutPassedCaseCount = 5
scaleoutResultRowCount = 5
apiRouteStatusCode = 200
htmlRouteStatusCode = 200
```

- [x] [GREEN] Audit final heartbeat:

```text
latestSnapshot = video_to_analysis_next_sample_selection_snapshot_v38
primaryBlocker = null
nextRecommendedNextLever = video_to_analysis_bounded_next_sample_execution_approval
```

- [x] [GREEN] Confirm all guardrails stayed false.

### Task 5: Verification And Closeout

**Files:**
- Read/verify scripts and tests.
- Update closeout readout.

- [x] [GREEN] Run compile:

```bash
python3 -m py_compile \
  backend/scripts/run_video_to_analysis_bounded_next_sample_execution_approval.py \
  backend/scripts/run_video_to_analysis_bounded_next_sample_execution.py \
  backend/scripts/run_video_to_analysis_bounded_next_sample_report_route_binding.py \
  backend/scripts/run_video_to_analysis_bounded_next_sample_closeout.py \
  backend/scripts/run_video_to_analysis_scaleout_or_backlog_decision_snapshot.py \
  backend/scripts/run_video_to_analysis_source_and_artifact_cleanup_map.py \
  backend/scripts/run_video_to_analysis_next_roadmap_direction_snapshot.py \
  backend/scripts/run_video_to_analysis_source_pool_replenishment_plan.py \
  backend/scripts/run_video_to_analysis_source_pool_replenishment_approval.py \
  backend/scripts/run_video_to_analysis_real_video_scaleout_plan_refresh.py \
  backend/scripts/run_video_to_analysis_real_video_scaleout_execution_approval.py \
  backend/scripts/run_video_to_analysis_real_video_scaleout_bounded_execution.py \
  backend/scripts/run_video_to_analysis_real_video_scaleout_report_route_binding.py \
  backend/scripts/run_video_to_analysis_real_video_scaleout_lane_closeout.py \
  backend/scripts/run_video_to_analysis_next_sample_selection_snapshot.py
```

- [x] [GREEN] Run focused tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  backend/tests/test_run_video_to_analysis_source_pool_replenishment_plan.py \
  backend/tests/test_run_video_to_analysis_detector_evaluation_reentry_chain.py \
  backend/tests/test_run_video_to_analysis_real_video_scaleout_execution_chain.py \
  backend/tests/test_run_video_to_analysis_bounded_next_sample_execution_chain.py \
  backend/tests/test_run_video_to_analysis_steady_state_monitoring_cycle.py \
  backend/tests/test_run_video_to_analysis_operational_roadmap_sprint.py -q
```

- [x] [GREEN] Run full backend tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest backend/tests -q
```

- [x] [GREEN] Run hygiene checks:

```bash
du -sh backend/storage . 2>/dev/null
runpodctl pod list --all -o json
```

- [x] [GREEN] Declare module closeout only if all commands pass and the closeout readout names the next strategic lever.

## End State We Are Trying To Reach

The desired finish state for this module is:

```text
latestSnapshot = video_to_analysis_next_sample_selection_snapshot_v38
growthLaneTrancheAuditPassed = true
focusedTestsPassed = true
fullBackendTestsPassed = true
runpodPodList = []
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalMatchStorageMutationExecuted = false
generatedTruthDeleteAllowed = false
```

Then the next conversation should not ask "where are we?" again. It should read:

```text
docs/video-to-analysis-growth-lane-closeout-readout-2026-05-09.md
backend/storage/automation/unattended_roadmap_loop_status.json
```

and choose one of:

```text
continue bounded growth from v38
switch to external benchmark expansion
switch to operator dashboard/product polish
switch to storage cleanup approval
pause growth and prepare a user-facing release/readout
```

## Non-Negotiable Guardrails

- [x] [GREEN] Do not train in this module.
- [x] [GREEN] Do not promote in this module.
- [x] [GREEN] Do not mutate runtime defaults in this module.
- [x] [GREEN] Do not download full datasets in this module.
- [x] [GREEN] Do not mutate normal match storage in this module.
- [x] [GREEN] Do not delete generated truth in this module.
- [x] [GREEN] Do not call a queue-exhausted artifact a failure when it has `remainingCandidateSampleCount = 0`; treat it as the expected transition.

## Current Honest Answer

We are not debugging the detector anymore. We are operating a bounded growth lane over the already-working v7.2 video-to-analysis runtime.

The old product finish line is green. The current module ends when we stop the growth loop at a finite verified snapshot and write the closeout readout. The planned stop gate is v38.
