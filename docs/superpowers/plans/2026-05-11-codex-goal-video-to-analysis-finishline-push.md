# Codex Goal: Video-To-Analysis Finish-Line Push

Created: 2026-05-11

This file is written for Codex CLI `/goal`. It follows the OpenAI Codex "Follow a goal" pattern: one durable objective, a verifiable stopping condition, first files to read, proof commands, checkpoint loop, and explicit pause conditions.

Reference: https://developers.openai.com/codex/use-cases/follow-goals

## Goal

Complete the next video-to-analysis finish-line push without stopping until the operator dashboard and operational sprint chain are implemented, generated, verified, and reflected in the live roadmap state.

## Verifiable End State

Stop only when one of these is true:

1. Success:
   - The following generated truth surfaces exist and each reports `goalAchieved = true`, `primaryBlocker = null`:
     - `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/video_to_analysis_operator_dashboard_polish_v1/operator_dashboard_polish_summary.json`
     - `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_real_source_path_consolidation_v1/real_source_path_consolidation_summary.json`
     - `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/video_to_analysis_real_video_scaleout_plan_v1/real_video_scaleout_plan_summary.json`
     - `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/video_to_analysis_steady_state_monitoring_recurring_schedule_v1/steady_state_monitoring_recurring_schedule_summary.json`
     - `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/video_to_analysis_operational_sprint_closeout_v1/operational_sprint_closeout_summary.json`
     - `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/video_to_analysis_growth_lane_decision_snapshot_v1/growth_lane_decision_snapshot_summary.json`
   - The final generated next lever is `video_to_analysis_real_video_scaleout_execution_approval`.
   - `backend/storage/automation/unattended_roadmap_loop_status.json`, `SESSION-HANDOFF.md`, `memorybank/activeContext.md`, `memorybank/currentRoadmap.md`, `memorybank/progress.md`, and `docs/video-to-analysis-finish-line-roadmap-guide.md` are refreshed from the final generated truth.
   - Focused tests, py_compile, JSON sanity, disk check, and RunPod pod check pass.

2. Valid blocker:
   - A generated truth artifact records a specific `primaryBlocker`.
   - Exactly one next lever is selected.
   - The blocker and next lever are reflected in the heartbeat/docs.
   - Tests/compile for the relevant scripts still pass.

Do not stop after one small task if generated truth already points to the next deterministic batch.

## Current Repo State

Workspace:

```text
/root/WorkSpace/fotball-analyst
```

Current authoritative heartbeat:

```text
backend/storage/automation/unattended_roadmap_loop_status.json
```

Current active batch:

```text
activeBatchName = video_to_analysis_storage_retention_and_artifact_hygiene
primaryBlocker = null
nextRecommendedNextLever = video_to_analysis_operator_dashboard_polish
activeRuntimeDefaultVersion = v7.3
```

Latest shipped cascade:

```text
video_to_analysis_steady_state_monitoring_cycle
-> football_external_soccernet_broader_validation_choice
-> video_to_analysis_upload_to_analysis_walkthrough
-> v7_4_training_decision_from_real_misses
-> video_to_analysis_storage_retention_and_artifact_hygiene
```

Final storage hygiene truth:

```text
goalAchieved = true
primaryBlocker = null
storageHygienePlanReady = true
artifactInventoryReady = true
retentionPolicyReady = true
cleanupExecutionReady = false
cleanupMutationExecuted = false
generatedTruthDeleteAllowed = false
nextRecommendedNextLever = video_to_analysis_operator_dashboard_polish
```

Important current interpretation:

```text
v7.3 is steady-state healthy.
Broader SoccerNet validation is optional future growth, not a blocker.
No v7.4 training is justified by current real-miss truth.
Storage hygiene is planned but did not delete or mutate artifacts.
Next concrete work is operator dashboard polish.
```

## Read First

Read these before editing code:

```text
backend/storage/automation/unattended_roadmap_loop_status.json
docs/video-to-analysis-finish-line-roadmap-guide.md
SESSION-HANDOFF.md
memorybank/activeContext.md
memorybank/currentRoadmap.md
memorybank/progress.md
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/video_to_analysis_storage_retention_and_artifact_hygiene_v1/storage_retention_and_artifact_hygiene_summary.json
```

Then inspect the scripts/tests for the chain:

```text
backend/scripts/run_video_to_analysis_operator_dashboard_polish.py
backend/scripts/run_football_external_benchmark_real_source_path_consolidation.py
backend/scripts/run_video_to_analysis_real_video_scaleout_plan.py
backend/scripts/run_video_to_analysis_steady_state_monitoring_recurring_schedule.py
backend/scripts/run_video_to_analysis_operational_sprint_closeout.py
backend/scripts/run_video_to_analysis_growth_lane_decision_snapshot.py
backend/tests/test_run_video_to_analysis_operator_dashboard_polish.py
backend/tests/test_run_video_to_analysis_operational_roadmap_sprint.py
backend/tests/test_run_video_to_analysis_real_video_scaleout_execution_chain.py
```

## First Coding Fix To Check

The operator dashboard path may still contain stale v7.2 fallback/test expectations even though the current active runtime is v7.3.

Before running the chain, verify and fix if needed:

- `operator_dashboard_view_model.json` should use `releasedRuntimeVersion = v7.3` when steady-state truth says v7.3.
- HTML/API dashboard output should show v7.3, not v7.2.
- Tests should not hard-code v7.2 for the current runtime path unless they are explicitly testing a legacy fixture.

Keep backward-compatible field names only where existing code/tests require them, but the current operator-facing dashboard must describe the active v7.3 release truth.

## Execution Plan

Work in checkpoints. After each checkpoint:

- Run the focused tests for that checkpoint.
- Run the batch script against real artifacts.
- Inspect the generated JSON summary.
- Continue if `goalAchieved = true` and the next lever is deterministic.
- If a blocker appears, repair only the indicated scope up to 3 attempts, then write blocker truth and stop.

### Checkpoint 1: Operator Dashboard Polish

Target script:

```bash
python3 backend/scripts/run_video_to_analysis_operator_dashboard_polish.py
```

Expected generated truth:

```text
video_to_analysis_operator_dashboard_polish_v1/operator_dashboard_polish_summary.json
goalAchieved = true
operatorDashboardRouteReady = true
apiRouteStatusCode = 200
htmlRouteStatusCode = 200
nextRecommendedNextLever = football_external_benchmark_real_source_path_consolidation
```

Failsafe attempts:

1. `operator_dashboard_polish`: bind current runtime health and storage truth.
2. `operator_dashboard_route_repair`: repair only view model, route contract, or HTML/API binding.
3. `operator_dashboard_blocker_summary`: write blocker truth and stop.

### Checkpoint 2: External Real Source Path Consolidation

Target script:

```bash
python3 backend/scripts/run_football_external_benchmark_real_source_path_consolidation.py
```

Expected generated truth:

```text
football_external_benchmark_real_source_path_consolidation_v1/real_source_path_consolidation_summary.json
goalAchieved = true
sourcePathConsolidationReady = true
sourcePathCount = 2
nextRecommendedNextLever = video_to_analysis_real_video_scaleout_plan
```

Failsafe attempts:

1. `real_source_path_consolidation`: consolidate SoccerNet/SoccerTrack bounded source paths.
2. `source_path_scope_repair`: repair only source references and manifest binding.
3. `source_path_blocker_summary`: write one blocker and one next family.

### Checkpoint 3: Real Video Scaleout Plan

Target script:

```bash
python3 backend/scripts/run_video_to_analysis_real_video_scaleout_plan.py
```

Expected generated truth:

```text
video_to_analysis_real_video_scaleout_plan_v1/real_video_scaleout_plan_summary.json
goalAchieved = true
realVideoScaleoutPlanReady = true
scaleoutCaseCount = 5
nextRecommendedNextLever = video_to_analysis_steady_state_monitoring_recurring_schedule
```

Failsafe attempts:

1. `real_video_scaleout_plan`: build bounded plan from consolidated sources.
2. `scaleout_scope_repair`: repair only plan references or case manifest.
3. `scaleout_blocker_summary`: write blocker truth and stop.

### Checkpoint 4: Recurring Steady-State Monitoring Schedule

Target script:

```bash
python3 backend/scripts/run_video_to_analysis_steady_state_monitoring_recurring_schedule.py
```

Expected generated truth:

```text
video_to_analysis_steady_state_monitoring_recurring_schedule_v1/steady_state_monitoring_recurring_schedule_summary.json
goalAchieved = true
recurringScheduleReady = true
nextRecommendedNextLever = video_to_analysis_operational_sprint_closeout
```

Failsafe attempts:

1. `steady_state_monitoring_recurring_schedule`: write cadence/failure routing.
2. `recurring_schedule_scope_repair`: repair only cadence/failure-route artifacts.
3. `recurring_schedule_blocker_summary`: write blocker truth and stop.

### Checkpoint 5: Operational Sprint Closeout

Target script:

```bash
python3 backend/scripts/run_video_to_analysis_operational_sprint_closeout.py
```

Expected generated truth:

```text
video_to_analysis_operational_sprint_closeout_v1/operational_sprint_closeout_summary.json
goalAchieved = true
operationalSprintClosed = true
completedOperationalItemCount = 4
nextRecommendedNextLever = video_to_analysis_growth_lane_decision_snapshot
```

Failsafe attempts:

1. `operational_sprint_closeout`: close the operational sprint from four completed items.
2. `operational_sprint_evidence_repair`: repair only missing/stale artifact references.
3. `operational_sprint_blocker_summary`: write blocker truth and stop.

### Checkpoint 6: Growth Lane Decision Snapshot

Target script:

```bash
python3 backend/scripts/run_video_to_analysis_growth_lane_decision_snapshot.py
```

Expected generated truth:

```text
video_to_analysis_growth_lane_decision_snapshot_v1/growth_lane_decision_snapshot_summary.json
goalAchieved = true
growthLaneDecisionSnapshotReady = true
selectedGrowthLever = video_to_analysis_real_video_scaleout_execution_approval
nextRecommendedNextLever = video_to_analysis_real_video_scaleout_execution_approval
```

Failsafe attempts:

1. `growth_lane_decision_snapshot`: select the next growth lane from closed operational sprint truth.
2. `growth_lane_decision_repair`: repair only missing sprint closeout references.
3. `growth_lane_blocker_summary`: write blocker truth and stop.

## Optional Continuation If Time Remains

If Checkpoint 6 passes and time remains, continue one bounded scaleout approval/execution tranche only if the generated truth selects it and the existing scripts support it.

Likely next chain:

```text
video_to_analysis_real_video_scaleout_execution_approval
-> video_to_analysis_real_video_scaleout_bounded_execution
-> video_to_analysis_real_video_scaleout_report_route_binding
-> video_to_analysis_real_video_scaleout_lane_closeout
-> video_to_analysis_next_sample_selection_snapshot
```

Stop after a clean snapshot, a generated blocker, or any command requiring human/manual approval not already encoded in generated truth.

## Guardrails

The repo is dirty and contains many existing modified/untracked/generated files. Do not revert unrelated changes. Do not use `git reset --hard` or checkout-away files.

Do not manually invent success. Generated JSON truth is authoritative.

Allowed:

- Code fixes needed to make the current chain truthful.
- Focused tests.
- Generated truth artifacts under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/`.
- Heartbeat/doc refreshes from generated truth.
- Bounded scaleout continuation if selected by generated truth and already supported by scripts.

Not allowed unless a generated approval artifact explicitly selects it and the script enforces safety:

- Full dataset download.
- New detector training.
- Promotion mutation.
- Runtime-default mutation.
- Destructive cleanup.
- Normal match storage mutation.
- Auto-accepting model detections as labels.

If any such action becomes genuinely needed, write a generated approval/blocker artifact and stop.

## Required Verification

Run these before final completion claim:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  backend/tests/test_run_video_to_analysis_operator_dashboard_polish.py \
  backend/tests/test_run_video_to_analysis_operational_roadmap_sprint.py \
  backend/tests/test_run_video_to_analysis_real_video_scaleout_execution_chain.py \
  backend/tests/test_unattended_roadmap_loop.py -q

python3 -m py_compile \
  backend/scripts/run_video_to_analysis_operator_dashboard_polish.py \
  backend/scripts/run_football_external_benchmark_real_source_path_consolidation.py \
  backend/scripts/run_video_to_analysis_real_video_scaleout_plan.py \
  backend/scripts/run_video_to_analysis_steady_state_monitoring_recurring_schedule.py \
  backend/scripts/run_video_to_analysis_operational_sprint_closeout.py \
  backend/scripts/run_video_to_analysis_growth_lane_decision_snapshot.py

python3 - <<'PY'
import json
from pathlib import Path
root = Path("backend/storage/trained_detector_candidates/touchline_detector_candidate_v7")
paths = [
    root / "video_to_analysis_operator_dashboard_polish_v1/operator_dashboard_polish_summary.json",
    root / "football_external_benchmark_real_source_path_consolidation_v1/real_source_path_consolidation_summary.json",
    root / "video_to_analysis_real_video_scaleout_plan_v1/real_video_scaleout_plan_summary.json",
    root / "video_to_analysis_steady_state_monitoring_recurring_schedule_v1/steady_state_monitoring_recurring_schedule_summary.json",
    root / "video_to_analysis_operational_sprint_closeout_v1/operational_sprint_closeout_summary.json",
    root / "video_to_analysis_growth_lane_decision_snapshot_v1/growth_lane_decision_snapshot_summary.json",
]
for path in paths:
    data = json.loads(path.read_text())
    print(path, data.get("goalAchieved"), data.get("primaryBlocker"), data.get("nextRecommendedNextLever"))
PY

df -h .
runpodctl pod list --all -o json
git status --short
```

If tests fail, debug systematically:

1. Reproduce exactly.
2. Identify whether the failure is stale expected runtime version, missing generated truth, route binding, or script logic.
3. Fix the smallest scope.
4. Re-run focused tests.
5. Re-run the affected generated batch.

## Documentation Refresh

After final generated truth:

- Update `backend/storage/automation/unattended_roadmap_loop_status.json`.
- Prepend a latest section to:
  - `SESSION-HANDOFF.md`
  - `memorybank/activeContext.md`
  - `memorybank/currentRoadmap.md`
  - `memorybank/progress.md`
  - `docs/video-to-analysis-finish-line-roadmap-guide.md`

The doc refresh must name:

- final batch
- final `primaryBlocker`
- final `nextRecommendedNextLever`
- any mutation flags
- exact verification commands and results

## Final Response Required

When done, report:

- files changed
- batches executed
- final generated truth path
- final next lever
- verification commands and results
- any remaining blocker or manual next action

Keep the summary concrete. Do not claim finish if verification did not run.
