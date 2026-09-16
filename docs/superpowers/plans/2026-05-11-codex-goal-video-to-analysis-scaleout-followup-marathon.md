# Video-To-Analysis Scaleout Followup Marathon Goal

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Continue the video-to-analysis autonomous growth lane from the current generated closeout, execute the refreshed five-case scaleout plan, recover through deterministic source-pool logic if needed, and leave an audited closeout or exact blocker.

**Architecture:** Generated JSON truth is the authority. The worker should follow `nextRecommendedNextLever` from the latest generated artifact, execute only deterministic/non-human steps, and refresh heartbeat/docs after verification. This is a marathon continuation, not a single-script patch.

**Tech Stack:** Python batch scripts under `backend/scripts`, generated JSON/Markdown artifacts under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7`, pytest, RunPod CLI hygiene check, memorybank and SESSION-HANDOFF docs.

---

## Short CLI Prompt

Use this after `/goal`:

```text
In /root/WorkSpace/fotball-analyst, follow docs/superpowers/plans/2026-05-11-codex-goal-video-to-analysis-scaleout-followup-marathon.md exactly. Execute the next autonomous video-to-analysis scaleout marathon from generated truth. Stop only at a real blocker, non-autonomous gate, or the batch cap. Verify and close out.
```

## Authoritative Current State

Start from the generated truth, not prose:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_autonomous_growth_marathon_closeout_v1/
    autonomous_growth_marathon_closeout_summary.json
```

Current confirmed state:

```text
batchName = video_to_analysis_autonomous_growth_marathon_closeout
goalAchieved = true
primaryBlocker = null
nextRecommendedNextLever = video_to_analysis_real_video_scaleout_execution_approval
stopReason = generated_batch_cap_reached
executedBatchCount = 30
refreshedScaleoutCaseCount = 5
sourcePoolReplenishmentApprovalDir = video_to_analysis_source_pool_replenishment_approval_v36
```

Current refreshed scaleout plan:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_real_video_scaleout_plan_refresh_v125/
    real_video_scaleout_plan_refresh_summary.json
```

It must report:

```text
goalAchieved = true
primaryBlocker = null
nextRecommendedNextLever = video_to_analysis_real_video_scaleout_execution_approval
refreshedScaleoutCaseCount = 5
sourcePoolReplenishmentApprovalDir = video_to_analysis_source_pool_replenishment_approval_v36
```

Heartbeat:

```text
backend/storage/automation/unattended_roadmap_loop_status.json
```

It should point to:

```text
activeBatchName = video_to_analysis_autonomous_growth_marathon_closeout
lastGeneratedTruthPath = backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/video_to_analysis_autonomous_growth_marathon_closeout_v1/autonomous_growth_marathon_closeout_summary.json
nextRecommendedNextLever = video_to_analysis_real_video_scaleout_execution_approval
```

## Global Guardrails

Keep these false unless a later generated truth explicitly opens a validation path and the plan says it is safe:

```text
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
```

Do not:

```text
create or delete RunPod pods unless a generated batch explicitly requires it
perform detector training
promote a model
mutate runtime defaults
download full datasets
auto-label model detections as truth
delete large artifacts outside an explicit cleanup-map batch
ignore generated blockers
advance from prose when generated JSON disagrees
```

## Attempt Budget

Use an adaptive 3-attempt rule for any failing batch:

1. **Attempt 1: execute generated next lever as-is**
   - Read the latest summary JSON.
   - Run the script that matches `nextRecommendedNextLever`.
   - Write the next versioned artifact directory.
   - Run focused tests if code changed or if a route/smoke contract is involved.

2. **Attempt 2: scoped repair**
   - Allowed: path binding repair, stale heartbeat repair, missing generated artifact repair, deterministic version-number repair, route/report binding repair, JSON-schema/count audit repair.
   - Not allowed: changing labels, thresholds, promotion rules, runtime defaults, training inputs, or generated truth to force success.

3. **Attempt 3: blocker closeout**
   - If still failing, write a blocker summary with one exact `primaryBlocker` and one exact `nextRecommendedNextLever`.
   - Refresh heartbeat/docs from that blocker truth.
   - Stop.

## Time Boxes

Total operator-away target: about 3 hours.

Hard cap:

```text
maxGeneratedBatchesToExecute = 50
minimumFreeDiskBeforeStop = 25G
```

If the 50-batch cap is reached while work remains safe, write a closeout like:

```text
batchName = video_to_analysis_autonomous_scaleout_followup_closeout
goalAchieved = true
primaryBlocker = null
stopReason = generated_batch_cap_reached
nextRecommendedNextLever = <latest generated next lever>
```

## Goal 1: Execute The Refreshed Five-Case Scaleout Plan

Time box: 60-90 minutes.

Purpose:

```text
Consume the current v125 refreshed real-video scaleout plan and produce a new bounded execution/report/closeout/snapshot chain.
```

Start with:

```text
nextRecommendedNextLever = video_to_analysis_real_video_scaleout_execution_approval
```

Expected chain:

```text
video_to_analysis_real_video_scaleout_execution_approval
-> video_to_analysis_real_video_scaleout_bounded_execution
-> video_to_analysis_real_video_scaleout_report_route_binding
-> video_to_analysis_real_video_scaleout_lane_closeout
-> video_to_analysis_next_sample_selection_snapshot
```

Core scripts to inspect and run as generated truth requires:

```text
backend/scripts/run_video_to_analysis_real_video_scaleout_execution_approval.py
backend/scripts/run_video_to_analysis_real_video_scaleout_bounded_execution.py
backend/scripts/run_video_to_analysis_real_video_scaleout_report_route_binding.py
backend/scripts/run_video_to_analysis_real_video_scaleout_lane_closeout.py
backend/scripts/run_video_to_analysis_next_sample_selection_snapshot.py
```

Goal 1 success truth should include:

```text
primaryBlocker = null
goalAchieved = true
nextRecommendedNextLever = video_to_analysis_bounded_next_sample_execution_approval
```

If no bounded candidates are available, this is not automatically failure. It routes to Goal 2.

## Goal 2: Drain Bounded Samples And Recover If Exhausted

Time box: 60-90 minutes.

Purpose:

```text
Execute bounded next-sample chains until the snapshot queues are drained, then recover through plan refresh/source sampling/source-pool replenishment if generated truth selects it.
```

Normal bounded chain:

```text
video_to_analysis_bounded_next_sample_execution_approval
-> video_to_analysis_bounded_next_sample_execution
-> video_to_analysis_bounded_next_sample_report_route_binding
-> video_to_analysis_bounded_next_sample_closeout
-> video_to_analysis_scaleout_or_backlog_decision_snapshot
-> video_to_analysis_source_and_artifact_cleanup_map
-> video_to_analysis_next_sample_selection_snapshot
```

Core scripts:

```text
backend/scripts/run_video_to_analysis_bounded_next_sample_execution_approval.py
backend/scripts/run_video_to_analysis_bounded_next_sample_execution.py
backend/scripts/run_video_to_analysis_bounded_next_sample_report_route_binding.py
backend/scripts/run_video_to_analysis_bounded_next_sample_closeout.py
backend/scripts/run_video_to_analysis_scaleout_or_backlog_decision_snapshot.py
backend/scripts/run_video_to_analysis_source_and_artifact_cleanup_map.py
backend/scripts/run_video_to_analysis_next_sample_selection_snapshot.py
```

If bounded pool exhaustion appears:

```text
primaryBlocker = video_to_analysis_bounded_next_sample_pool_exhausted
remainingCandidateSampleCount = 0
```

then run the generated recovery path:

```text
video_to_analysis_real_video_scaleout_plan_refresh
```

If the refresh reports candidate-pool insufficiency:

```text
primaryBlocker = video_to_analysis_real_video_scaleout_candidate_pool_insufficient
```

then follow:

```text
video_to_analysis_real_video_scaleout_source_sampling_expansion
-> video_to_analysis_next_roadmap_direction_snapshot
```

If source sampling exhausts:

```text
primaryBlocker = video_to_analysis_real_video_scaleout_source_sampling_pool_exhausted
```

then follow:

```text
video_to_analysis_source_pool_replenishment_plan
-> video_to_analysis_source_pool_replenishment_approval
-> video_to_analysis_real_video_scaleout_plan_refresh
```

Recovery scripts:

```text
backend/scripts/run_video_to_analysis_real_video_scaleout_plan_refresh.py
backend/scripts/run_video_to_analysis_real_video_scaleout_source_sampling_expansion.py
backend/scripts/run_video_to_analysis_next_roadmap_direction_snapshot.py
backend/scripts/run_video_to_analysis_source_pool_replenishment_plan.py
backend/scripts/run_video_to_analysis_source_pool_replenishment_approval.py
```

Goal 2 success truth should end with either:

```text
nextRecommendedNextLever = video_to_analysis_real_video_scaleout_execution_approval
primaryBlocker = null
```

or a specific non-autonomous/human blocker.

## Goal 3: Close Out, Verify, And Prepare The Next Goal

Time box: 30-45 minutes.

Purpose:

```text
Make the final state obvious, audited, and resumable.
```

Create or refresh a final closeout artifact under:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
```

Suggested directory name:

```text
video_to_analysis_autonomous_scaleout_followup_closeout_v1
```

Closeout must report:

```text
batchName
goalAchieved
primaryBlocker
roadmapAdvanceAllowed
nextRecommendedNextLever
stopReason
executedBatchCount
latestGeneratedTruthPath
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
englishDecision
```

Refresh these from final generated truth only:

```text
backend/storage/automation/unattended_roadmap_loop_status.json
SESSION-HANDOFF.md
memorybank/activeContext.md
memorybank/currentRoadmap.md
memorybank/progress.md
docs/video-to-analysis-finish-line-roadmap-guide.md
```

## Verification Commands

Run focused tests for the scripts touched or exercised. At minimum, include:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  backend/tests/test_run_video_to_analysis_real_video_scaleout_execution_chain.py \
  backend/tests/test_run_video_to_analysis_bounded_next_sample_execution_chain.py \
  backend/tests/test_run_video_to_analysis_source_pool_replenishment_plan.py \
  backend/tests/test_unattended_roadmap_loop.py -q
```

If roadmap-direction snapshot behavior is touched, also run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  backend/tests/test_run_video_to_analysis_detector_evaluation_reentry_chain.py -q
```

Compile touched/all relevant scripts:

```bash
python3 -m py_compile \
  backend/scripts/run_video_to_analysis_real_video_scaleout_execution_approval.py \
  backend/scripts/run_video_to_analysis_real_video_scaleout_bounded_execution.py \
  backend/scripts/run_video_to_analysis_real_video_scaleout_report_route_binding.py \
  backend/scripts/run_video_to_analysis_real_video_scaleout_lane_closeout.py \
  backend/scripts/run_video_to_analysis_next_sample_selection_snapshot.py \
  backend/scripts/run_video_to_analysis_bounded_next_sample_execution_approval.py \
  backend/scripts/run_video_to_analysis_bounded_next_sample_execution.py \
  backend/scripts/run_video_to_analysis_bounded_next_sample_report_route_binding.py \
  backend/scripts/run_video_to_analysis_bounded_next_sample_closeout.py \
  backend/scripts/run_video_to_analysis_scaleout_or_backlog_decision_snapshot.py \
  backend/scripts/run_video_to_analysis_source_and_artifact_cleanup_map.py \
  backend/scripts/run_video_to_analysis_real_video_scaleout_plan_refresh.py \
  backend/scripts/run_video_to_analysis_real_video_scaleout_source_sampling_expansion.py \
  backend/scripts/run_video_to_analysis_next_roadmap_direction_snapshot.py \
  backend/scripts/run_video_to_analysis_source_pool_replenishment_plan.py \
  backend/scripts/run_video_to_analysis_source_pool_replenishment_approval.py
```

Run JSON sanity:

```bash
python3 - <<'PY'
import json
from pathlib import Path

heartbeat = Path("backend/storage/automation/unattended_roadmap_loop_status.json")
status = json.loads(heartbeat.read_text())
truth = Path(status["lastGeneratedTruthPath"])
data = json.loads(truth.read_text())

print("heartbeat active =", status.get("activeBatchName"))
print("truth =", truth)
print("batch =", data.get("batchName"))
print("goalAchieved =", data.get("goalAchieved"))
print("primaryBlocker =", data.get("primaryBlocker"))
print("next =", data.get("nextRecommendedNextLever"))

for key in [
    "trainingExecuted",
    "promotionMutationExecuted",
    "runtimeDefaultMutationExecuted",
    "videoDownloadExecuted",
    "dataDownloadExecuted",
]:
    if data.get(key) is not False:
        raise SystemExit(f"{key} is not false: {data.get(key)}")
PY
```

Run operational hygiene checks:

```bash
df -h .
runpodctl pod list --all -o json
git status --short | sed -n '1,180p'
```

## Final Answer Required Shape

The CLI final answer must include:

```text
1. final generated truth path
2. final batch name
3. executed batch count
4. stop reason
5. primaryBlocker
6. nextRecommendedNextLever
7. whether runtime/training/promotion/download flags stayed false
8. pytest result
9. py_compile result
10. JSON sanity result
11. disk free result
12. RunPod pod result
13. exact next goal prompt if more autonomous work remains
```

## Completion Checklist

- [ ] Goal 1 executed from v125 or blocked with generated truth.
- [ ] Goal 2 drained bounded samples or ran the generated recovery path.
- [ ] Goal 3 wrote/refreshed closeout, heartbeat, docs, and memorybank.
- [ ] No generated truth claims runtime mutation unless an explicit runtime validation chain actually performed it.
- [ ] No training, promotion, full dataset download, or auto-labeling occurred.
- [ ] Tests passed or a blocker artifact explains exactly why not.
- [ ] Disk remains above 25G free.
- [ ] RunPod pods are empty unless a generated artifact says a pod is intentionally active.
