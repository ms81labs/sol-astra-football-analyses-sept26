# Video-To-Analysis Bounded Chain Continuation Goal

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to follow this goal from generated truth. This is a deterministic continuation goal, not a fresh roadmap design task.

**Goal:** Continue the video-to-analysis roadmap from the current generated closeout, finish the bounded next-sample chain that stopped at the batch cap, then keep advancing through deterministic scaleout/recovery until a real blocker, non-autonomous gate, or batch cap is reached.

**Architecture:** The latest generated JSON and heartbeat are authoritative. Follow `nextRecommendedNextLever` exactly, preserve guardrails, and write a fresh closeout when the cap or a real blocker is reached.

**Tech Stack:** Python batch scripts under `backend/scripts`, generated JSON/Markdown artifacts under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7`, pytest, py_compile, RunPod CLI hygiene check, heartbeat and memorybank docs.

---

## Short CLI Prompt

Use this after `/goal`:

```text
In /root/WorkSpace/fotball-analyst, follow docs/superpowers/plans/2026-05-11-codex-goal-video-to-analysis-bounded-chain-continuation.md exactly. Continue from generated truth at video_to_analysis_bounded_next_sample_closeout, preserve guardrails, execute deterministic next levers until blocker/gate/cap, verify, and close out.
```

## Current Authoritative State

Start here:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_autonomous_scaleout_followup_closeout_v1/
    autonomous_scaleout_followup_closeout_summary.json
```

It currently reports:

```text
batchName = video_to_analysis_autonomous_scaleout_followup_closeout
goalAchieved = true
primaryBlocker = null
nextRecommendedNextLever = video_to_analysis_bounded_next_sample_closeout
stopReason = generated_batch_cap_reached
executedBatchCount = 50
```

Heartbeat:

```text
backend/storage/automation/unattended_roadmap_loop_status.json
```

It currently points to the same closeout and the same next lever:

```text
activeBatchName = video_to_analysis_autonomous_scaleout_followup_closeout
lastGeneratedTruthPath = backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/video_to_analysis_autonomous_scaleout_followup_closeout_v1/autonomous_scaleout_followup_closeout_summary.json
nextRecommendedNextLever = video_to_analysis_bounded_next_sample_closeout
```

## Non-Negotiable Guardrails

Keep these false unless later generated truth explicitly opens a safe validation lane:

```text
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalStorageMutationExecuted = false
cleanupDeletionExecuted = false
```

Do not:

```text
rerun already completed bounded approval/execution just because the next lever starts at closeout
invent a new roadmap path
force success by editing generated truth
train detectors
promote models
mutate runtime defaults
download full datasets
auto-label model detections
delete generated artifacts outside an explicit cleanup-map batch
```

## Attempt Budget

For any failing batch, use exactly three attempts:

1. **Attempt 1: direct continuation**
   - Run the script matching the current `nextRecommendedNextLever`.
   - Write a new versioned artifact directory.
   - Read the resulting summary JSON before choosing the next step.

2. **Attempt 2: scoped plumbing repair**
   - Allowed repairs: stale heartbeat path, missing output directory binding, version-number collision, route/report binding, JSON key mismatch, deterministic artifact lookup.
   - Forbidden repairs: label changes, training changes, threshold tuning, promotion criteria edits, runtime-default mutation, or rewriting generated truth to bypass a blocker.

3. **Attempt 3: blocker closeout**
   - If still failing, write a closeout with one `primaryBlocker` and one `nextRecommendedNextLever`.
   - Refresh heartbeat/docs from that blocker truth.
   - Stop.

## Time And Batch Caps

Target time: about 2-3 hours.

Hard cap:

```text
maxGeneratedBatchesToExecute = 50
minimumFreeDiskBeforeStop = 25G
```

If the cap is reached, write:

```text
batchName = video_to_analysis_bounded_chain_continuation_closeout
goalAchieved = true
primaryBlocker = null
stopReason = generated_batch_cap_reached
nextRecommendedNextLever = <latest generated next lever>
```

## Goal 1: Finish The In-Progress Bounded Chain

Time box: 20-40 minutes.

Current next lever:

```text
video_to_analysis_bounded_next_sample_closeout
```

Run the closeout script for the already executed bounded sample. Do not restart that sample from approval unless generated truth says the prior execution artifact is missing or invalid.

Expected continuation chain:

```text
video_to_analysis_bounded_next_sample_closeout
-> video_to_analysis_scaleout_or_backlog_decision_snapshot
-> video_to_analysis_source_and_artifact_cleanup_map
-> video_to_analysis_next_sample_selection_snapshot
```

Core scripts:

```text
backend/scripts/run_video_to_analysis_bounded_next_sample_closeout.py
backend/scripts/run_video_to_analysis_scaleout_or_backlog_decision_snapshot.py
backend/scripts/run_video_to_analysis_source_and_artifact_cleanup_map.py
backend/scripts/run_video_to_analysis_next_sample_selection_snapshot.py
```

Goal 1 success looks like one of:

```text
nextRecommendedNextLever = video_to_analysis_bounded_next_sample_execution_approval
```

or:

```text
primaryBlocker = video_to_analysis_bounded_next_sample_pool_exhausted
nextRecommendedNextLever = video_to_analysis_real_video_scaleout_plan_refresh
```

The second case is a valid recovery transition, not a failed goal.

## Goal 2: Continue Bounded Drain Or Recovery

Time box: 60-90 minutes.

If the next snapshot has another bounded sample, execute:

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

If the bounded sample pool exhausts:

```text
primaryBlocker = video_to_analysis_bounded_next_sample_pool_exhausted
remainingCandidateSampleCount = 0
```

then execute generated recovery:

```text
video_to_analysis_real_video_scaleout_plan_refresh
```

If plan refresh has insufficient candidates:

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

## Goal 3: Execute A New Real-Video Scaleout Chain If Replenishment Produces One

Time box: 60-90 minutes.

If recovery produces:

```text
nextRecommendedNextLever = video_to_analysis_real_video_scaleout_execution_approval
primaryBlocker = null
```

then execute:

```text
video_to_analysis_real_video_scaleout_execution_approval
-> video_to_analysis_real_video_scaleout_bounded_execution
-> video_to_analysis_real_video_scaleout_report_route_binding
-> video_to_analysis_real_video_scaleout_lane_closeout
-> video_to_analysis_next_sample_selection_snapshot
```

Core scripts:

```text
backend/scripts/run_video_to_analysis_real_video_scaleout_execution_approval.py
backend/scripts/run_video_to_analysis_real_video_scaleout_bounded_execution.py
backend/scripts/run_video_to_analysis_real_video_scaleout_report_route_binding.py
backend/scripts/run_video_to_analysis_real_video_scaleout_lane_closeout.py
backend/scripts/run_video_to_analysis_next_sample_selection_snapshot.py
```

## Goal 4: Close Out And Verify

Time box: 30 minutes.

Create or refresh a final closeout artifact under:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
```

Suggested directory:

```text
video_to_analysis_bounded_chain_continuation_closeout_v1
```

The closeout summary must include:

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
normalStorageMutationExecuted = false
cleanupDeletionExecuted = false
englishDecision
```

Refresh from generated truth only:

```text
backend/storage/automation/unattended_roadmap_loop_status.json
SESSION-HANDOFF.md
memorybank/activeContext.md
memorybank/currentRoadmap.md
memorybank/progress.md
docs/video-to-analysis-finish-line-roadmap-guide.md
```

## Verification Commands

Run focused tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  backend/tests/test_run_video_to_analysis_real_video_scaleout_execution_chain.py \
  backend/tests/test_run_video_to_analysis_bounded_next_sample_execution_chain.py \
  backend/tests/test_run_video_to_analysis_source_pool_replenishment_plan.py \
  backend/tests/test_unattended_roadmap_loop.py -q
```

If roadmap-direction snapshot is touched, run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  backend/tests/test_run_video_to_analysis_detector_evaluation_reentry_chain.py -q
```

Compile relevant scripts:

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

status = json.loads(Path("backend/storage/automation/unattended_roadmap_loop_status.json").read_text())
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
    "normalStorageMutationExecuted",
    "cleanupDeletionExecuted",
]:
    if data.get(key) is not False:
        raise SystemExit(f"{key} is not false: {data.get(key)}")
PY
```

Operational hygiene:

```bash
df -h .
runpodctl pod list --all -o json
git status --short | sed -n '1,180p'
```

## Final Answer Required

Report:

```text
1. final generated truth path
2. final batch name
3. executed batch count
4. stop reason
5. primaryBlocker
6. nextRecommendedNextLever
7. all guardrail flags
8. pytest result
9. py_compile result
10. JSON sanity result
11. disk free
12. RunPod state
13. whether another autonomous goal is useful
14. short next /goal prompt if useful
```

## Completion Checklist

- [ ] Started from `video_to_analysis_bounded_next_sample_closeout`, not a stale earlier lever.
- [ ] Finished the in-progress bounded chain or wrote a blocker.
- [ ] Continued bounded drain/recovery while generated truth allowed it.
- [ ] Executed a new real-video scaleout chain only if replenishment/refresh produced one.
- [ ] Wrote a final closeout or blocker summary.
- [ ] Updated heartbeat/docs/memorybank from final generated truth.
- [ ] Kept training/promotion/runtime/download/storage-mutation guardrails false.
- [ ] Ran focused pytest.
- [ ] Ran py_compile.
- [ ] Ran JSON sanity.
- [ ] Checked disk and RunPod.
