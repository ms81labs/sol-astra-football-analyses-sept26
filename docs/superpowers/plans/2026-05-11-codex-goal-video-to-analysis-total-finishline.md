# Video-To-Analysis Total Finishline Goal

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to execute this goal from generated truth. This is a long autonomous finishline goal, not a planning exercise. Track progress with checklist syntax and close with generated artifacts, verification, and a precise next gate.

**Goal:** Push the video-to-analysis project as far as it can go autonomously, across scaleout, bounded samples, product/operator acceptance, external benchmark binding, detector-training decision gates, cleanup mapping, and release packaging, stopping only at a real generated blocker or non-autonomous gate.

**Architecture:** Generated JSON truth and the live heartbeat are authoritative. The worker follows `nextRecommendedNextLever` dynamically, executes existing batch scripts with versioned artifacts, preserves guardrails unless generated truth explicitly opens a lane, and writes a total-finishline closeout when there is no more safe autonomous work.

**Tech Stack:** Python batch scripts under `backend/scripts`, generated JSON/Markdown artifacts under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7`, product reports under generated benchmark/runtime storage, pytest, `py_compile`, RunPod CLI hygiene checks, heartbeat docs, and memorybank roadmap files.

---

## Short CLI Prompt

Use this after `/goal`:

```text
In /root/WorkSpace/fotball-analyst, follow docs/superpowers/plans/2026-05-11-codex-goal-video-to-analysis-total-finishline.md exactly. Drive every autonomous generated-truth lane to completion, starting from the live heartbeat next lever. Stop only at a real blocker, human/non-autonomous gate, unsafe guardrail, or finishline closeout. Verify and write the closeout.
```

## Current Authoritative Start

Start from the live heartbeat:

```text
backend/storage/automation/unattended_roadmap_loop_status.json
```

At goal creation time it points to:

```text
activeBatchName = video_to_analysis_bounded_chain_continuation_closeout
last closeout = backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/video_to_analysis_bounded_chain_continuation_closeout_v2/bounded_chain_continuation_closeout_summary.json
```

The closeout reports:

```text
batchName = video_to_analysis_bounded_chain_continuation_closeout
goalAchieved = true
primaryBlocker = null
stopReason = generated_batch_cap_reached
executedBatchCount = 50
latestGeneratedTruthPath = backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/video_to_analysis_real_video_scaleout_plan_refresh_v135/real_video_scaleout_plan_refresh_summary.json
nextRecommendedNextLever = video_to_analysis_real_video_scaleout_execution_approval
```

The latest verified guardrails were:

```text
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalStorageMutationExecuted = false
cleanupDeletionExecuted = false
RunPod pods = []
disk = /dev/sda1 150G total, 93G used, 52G available, 65% used
```

Refresh these values before executing. If the live heartbeat has advanced, continue from the live heartbeat and mention the drift in the closeout.

## Finish Definition

This goal is complete when one of these is true and the closeout proves it:

1. **Autonomous finishline reached**
   - All deterministic generated-truth lanes reachable from the heartbeat have been executed.
   - No remaining `nextRecommendedNextLever` can safely run without human approval, manual review, fresh credentials, large download approval, destructive cleanup approval, production release approval, or a detector-training approval/data gate.
   - The final truth artifact reports `primaryBlocker = null` or a non-technical gate such as `human_approval_required`, with an exact next human action.

2. **Real blocker reached**
   - A batch failed after the three-attempt failsafe.
   - The worker wrote a blocker closeout with one `primaryBlocker`, one `nextRecommendedNextLever`, evidence paths, and verification status.

3. **Configured cap reached**
   - The worker executed the allowed batch cap, verified the current state, refreshed heartbeat/docs, and wrote a closeout preserving the latest generated next lever.

This goal is not complete if the worker merely runs one batch, refreshes one doc, or stops after the first normal queue-exhaustion proof. Queue exhaustion is a transition signal when generated truth contains a recovery path.

## Non-Negotiable Guardrails

Keep these false unless a later generated truth artifact explicitly opens a safe lane and the plan section below allows it:

```text
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
normalStorageMutationExecuted = false
cleanupDeletionExecuted = false
```

Default to these false, but allow execution only under the explicit conditions in this goal:

```text
trainingExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
```

Do not:

```text
edit generated truth to force success
invent positive labels
accept model detections as human truth
promote a model without a generated promotion approval gate
mutate runtime defaults without a generated validation gate
delete generated artifacts outside a generated cleanup approval gate
download full external datasets unless an approval artifact explicitly authorizes the scope and storage target
train a detector unless generated truth says training is needed and an audited export/checkpoint contract exists
reuse stale RunPod paths or stale checkpoint paths
infer against remote, missing, base, or stale weights when a local trained checkpoint contract is required
```

## Big Timebox And Caps

Target runtime:

```text
targetTimebox = 6 hours
```

Batch cap:

```text
maxGeneratedBatchesToExecute = 250
checkpointCadence = every 50 generated batches
minimumFreeDiskBeforeStop = 25G
```

At each checkpoint cadence:

```text
run focused tests
run py_compile on touched scripts
run JSON sanity over latest summaries
check df -h /
check runpodctl pod list --all -o json
refresh heartbeat and docs from generated truth
```

If disk free space drops below `25G`, stop with:

```text
primaryBlocker = video_to_analysis_disk_space_guardrail
nextRecommendedNextLever = video_to_analysis_storage_cleanup_approval
```

Do not delete files in the same run unless a generated cleanup approval artifact exists.

## Three-Attempt Failsafe For Every Batch

### Attempt 1: direct generated-truth execution

- Read the current summary JSON.
- Extract `nextRecommendedNextLever`.
- Locate the existing script that owns that lever using script names, tests, and generated artifact conventions.
- Run it with a new versioned artifact directory.
- Read the new summary JSON before deciding the next lever.

### Attempt 2: scoped repair

Use this only for plumbing failures.

Allowed repairs:

```text
heartbeat path mismatch
version-number collision
missing output-dir binding
route/report binding mismatch
JSON key mismatch caused by schema drift
missing artifact lookup
stale generated pointer
RunPod staging path mismatch
checkpoint key normalization
results pullback path repair
test expectation drift around generated schema
```

Forbidden repairs:

```text
label changes
threshold tuning to manufacture pass
manual success edits
promotion criteria changes
runtime-default mutation
deleting artifacts to hide a blocker
training-data mutation outside an audited manifest/export batch
```

### Attempt 3: blocker closeout

If direct execution and scoped repair fail:

- Write one blocker truth artifact.
- Set exactly one `primaryBlocker`.
- Set exactly one `nextRecommendedNextLever`.
- Preserve all guardrail fields.
- Refresh heartbeat/docs from the blocker truth.
- Stop.

## Goal 1: Rehydrate Current State And Dynamic Script Map

Timebox: 10-20 minutes.

- [ ] Read `backend/storage/automation/unattended_roadmap_loop_status.json`.
- [ ] Read the latest generated summary path named by the heartbeat.
- [ ] Read `SESSION-HANDOFF.md`.
- [ ] Read `memorybank/activeContext.md`.
- [ ] Read `memorybank/currentRoadmap.md`.
- [ ] Read `memorybank/progress.md`.
- [ ] Read `docs/video-to-analysis-finish-line-roadmap-guide.md`.
- [ ] Build a map of batch names to scripts:

```bash
rg -n "batchName|nextRecommendedNextLever|def main|argparse" backend/scripts/run_video_to_analysis*.py
rg -n "video_to_analysis_.*" backend/tests/test_run_video_to_analysis*.py backend/tests/test_unattended_roadmap_loop.py
```

- [ ] Confirm current next lever from generated truth.
- [ ] Start with `video_to_analysis_real_video_scaleout_execution_approval` unless the live heartbeat has advanced.

Success condition:

```text
stateSource = live heartbeat
currentNextLever = <generated nextRecommendedNextLever>
scriptMapReady = true
```

## Goal 2: Drain Real-Video Scaleout Chains

Timebox: 60-120 minutes.

When the next lever is a real-video scaleout approval, execute the chain:

```text
video_to_analysis_real_video_scaleout_execution_approval
-> video_to_analysis_real_video_scaleout_bounded_execution
-> video_to_analysis_real_video_scaleout_report_route_binding
-> video_to_analysis_real_video_scaleout_lane_closeout
-> video_to_analysis_next_sample_selection_snapshot
```

Expected scripts:

```text
backend/scripts/run_video_to_analysis_real_video_scaleout_execution_approval.py
backend/scripts/run_video_to_analysis_real_video_scaleout_bounded_execution.py
backend/scripts/run_video_to_analysis_real_video_scaleout_report_route_binding.py
backend/scripts/run_video_to_analysis_real_video_scaleout_lane_closeout.py
backend/scripts/run_video_to_analysis_next_sample_selection_snapshot.py
```

For each batch:

- [ ] Use a new versioned output directory.
- [ ] Read the summary JSON after execution.
- [ ] Confirm `goalAchieved = true` unless a real blocker is expected.
- [ ] Confirm guardrails remain false.
- [ ] Continue to the next generated lever.

Success condition:

```text
scaleoutChainAdvanced = true
oldFailingSourceNotViableBlockerAbsent = true
nextRecommendedNextLever = <next generated lever>
```

## Goal 3: Drain Bounded Next-Sample Chains

Timebox: 90-180 minutes.

When the next lever is a bounded sample approval, execute the deterministic chain:

```text
video_to_analysis_bounded_next_sample_execution_approval
-> video_to_analysis_bounded_next_sample_execution
-> video_to_analysis_bounded_next_sample_report_route_binding
-> video_to_analysis_bounded_next_sample_closeout
-> video_to_analysis_scaleout_or_backlog_decision_snapshot
-> video_to_analysis_source_and_artifact_cleanup_map
-> video_to_analysis_next_sample_selection_snapshot
```

Expected scripts:

```text
backend/scripts/run_video_to_analysis_bounded_next_sample_execution_approval.py
backend/scripts/run_video_to_analysis_bounded_next_sample_execution.py
backend/scripts/run_video_to_analysis_bounded_next_sample_report_route_binding.py
backend/scripts/run_video_to_analysis_bounded_next_sample_closeout.py
backend/scripts/run_video_to_analysis_scaleout_or_backlog_decision_snapshot.py
backend/scripts/run_video_to_analysis_source_and_artifact_cleanup_map.py
backend/scripts/run_video_to_analysis_next_sample_selection_snapshot.py
```

If the generated truth reports:

```text
primaryBlocker = video_to_analysis_bounded_next_sample_pool_exhausted
remainingCandidateSampleCount = 0
```

then treat it as a valid transition and continue to the generated recovery lever.

Success condition:

```text
boundedSamplesDrainedOrRecovered = true
routeBindingsWritten = true
cleanupMapWritten = true
nextRecommendedNextLever = <next generated lever>
```

## Goal 4: Replenish Source Pools When Exhausted

Timebox: 45-120 minutes per recovery loop.

When generated truth routes to scaleout/source-pool recovery, execute:

```text
video_to_analysis_real_video_scaleout_plan_refresh
```

If plan refresh says candidates are insufficient, follow the generated recovery path:

```text
video_to_analysis_real_video_scaleout_source_sampling_expansion
-> video_to_analysis_next_roadmap_direction_snapshot
-> video_to_analysis_source_pool_replenishment_plan
-> video_to_analysis_source_pool_replenishment_approval
-> video_to_analysis_real_video_scaleout_plan_refresh
```

Expected scripts:

```text
backend/scripts/run_video_to_analysis_real_video_scaleout_plan_refresh.py
backend/scripts/run_video_to_analysis_real_video_scaleout_source_sampling_expansion.py
backend/scripts/run_video_to_analysis_next_roadmap_direction_snapshot.py
backend/scripts/run_video_to_analysis_source_pool_replenishment_plan.py
backend/scripts/run_video_to_analysis_source_pool_replenishment_approval.py
```

Success condition:

```text
sourcePoolReplenished = true
refreshedScaleoutPlanReady = true
nextRecommendedNextLever = video_to_analysis_real_video_scaleout_execution_approval
```

If no replenishable source exists, write a closeout:

```text
primaryBlocker = video_to_analysis_source_pool_exhausted
nextRecommendedNextLever = video_to_analysis_external_source_or_human_sample_approval
```

## Goal 5: Execute Product And Operator Acceptance Gates

Timebox: 60-120 minutes.

When generated truth routes to product/operator work, execute existing scripts for:

```text
operator dashboard polish
route smoke validation
analysis report route binding
product acceptance packaging
release readiness snapshots
post-runtime-default source robustness validation
decision snapshots
```

Find current scripts dynamically:

```bash
rg -n "operator|dashboard|route|acceptance|release|source_robustness|runtime_default|decision_snapshot" backend/scripts backend/tests
```

Do not add new product UX unless the generated batch explicitly requires a missing acceptance artifact.

Success condition:

```text
operatorRoutesBound = true
productReportsReachable = true
acceptanceTruthWritten = true
runtimeDefaultMutationExecuted = false unless a generated runtime validation lane explicitly approves mutation
```

If an acceptance gate requires a human product decision, stop with:

```text
primaryBlocker = video_to_analysis_product_acceptance_human_approval_required
nextRecommendedNextLever = video_to_analysis_product_acceptance_manual_decision
```

## Goal 6: Execute External Benchmark And SoccerNet Lanes Only From Local Authorized Inputs

Timebox: 60-180 minutes if local sample artifacts exist.

When generated truth routes to external benchmark/SoccerNet work:

- [ ] Read `docs/foot-soccer-deepresearch.md` if it exists.
- [ ] Read `docs/video-to-analysis-finish-line-roadmap-guide.md`.
- [ ] Inspect local authorized SoccerNet/sample artifacts before downloading anything.
- [ ] If local sample artifacts exist, run bounded materialization/evaluation/report binding.
- [ ] If generated truth explicitly approves a controlled download and storage target, execute only that bounded download.
- [ ] Do not download full external datasets under this goal without a specific generated approval artifact.

Candidate script discovery:

```bash
rg -n "soccernet|external|benchmark|real_sample|fixture|sample" backend/scripts backend/tests docs
```

Success condition:

```text
externalSampleBound = true
pipelineRanOnExternalOrRealSample = true
reportRouteBound = true
trainingNeedDecisionWritten = true
```

If credentials, browser auth, terms acceptance, or a full-data approval is required:

```text
primaryBlocker = video_to_analysis_external_data_access_human_gate
nextRecommendedNextLever = video_to_analysis_external_data_access_manual_approval
```

## Goal 7: Decide Detector Training From Evidence, Not Momentum

Timebox: 30-90 minutes for decision/audit, longer only if generated truth opens training.

When generated truth routes to detector training or v7.x/v7.3/v7.4 work:

- [ ] Confirm the latest detector decision artifact says training is needed.
- [ ] Confirm the required manifest/export overlay audit has passed.
- [ ] Confirm a local trained checkpoint contract will be enforced.
- [ ] Confirm RunPod is available and no pods are currently orphaned.
- [ ] Confirm the script reads audited physical export data, not raw model guesses.

Training is allowed only when all are true:

```text
generatedTruthTrainingAllowed = true
auditedExportPassed = true
noPendingHumanLabels = true
checkpointContractImplemented = true
runtimeDefaultMutationAllowed = false unless separate generated runtime lane approves validation
```

If training is allowed, execute the existing training batch with its own three-attempt failsafe and RunPod hygiene. If training is not allowed, write or run the training-decision closeout that explains the missing precondition.

Success condition if training executes:

```text
trainingCompleted = true
localCheckpointContractPassed = true
boundedMetricsWritten = true
promotionReady = false unless a separate promotion gate exists
nextRecommendedNextLever = <generated guardrail/evaluation/release lever>
```

Success condition if training is not allowed:

```text
trainingExecuted = false
primaryBlocker = <specific missing prerequisite>
nextRecommendedNextLever = <manifest/export/review/data gate>
```

## Goal 8: Cleanup And Storage Hygiene Without Destructive Deletes

Timebox: 30-60 minutes.

Run cleanup-map batches when generated truth routes there. These may map artifacts, summarize candidates for deletion, and report disk usage.

Allowed without extra approval:

```text
write cleanup maps
write storage manifests
write disk usage summaries
mark generated evidence as cleanup eligible
```

Forbidden without generated approval:

```text
delete generated artifacts
delete videos
delete model weights
delete review packages
delete benchmark reports
```

Success condition:

```text
cleanupMapWritten = true
cleanupDeletionExecuted = false
diskFreeSpaceReported = true
```

## Goal 9: Final Whole-Process Closeout

Timebox: 20-40 minutes.

Always finish by writing a final closeout artifact under:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_total_finishline_closeout_v1/
```

Required files:

```text
total_finishline_closeout_summary.json
total_finishline_closeout.md
executed_batch_chain.json
guardrail_audit.json
verification_audit.json
next_action_contract.json
```

The JSON summary must include:

```json
{
  "batchName": "video_to_analysis_total_finishline_closeout",
  "goalAchieved": true,
  "primaryBlocker": null,
  "stopReason": "autonomous_finishline_reached_or_generated_batch_cap_reached_or_real_blocker",
  "executedBatchCount": 0,
  "latestGeneratedTruthPath": "",
  "nextRecommendedNextLever": "",
  "trainingExecuted": false,
  "promotionMutationExecuted": false,
  "runtimeDefaultMutationExecuted": false,
  "videoDownloadExecuted": false,
  "dataDownloadExecuted": false,
  "normalStorageMutationExecuted": false,
  "cleanupDeletionExecuted": false,
  "englishDecision": ""
}
```

Use the actual executed count and actual guardrail values. If training or download executes because generated truth explicitly approved it, record that separately with the approval artifact path and reason.

Refresh:

```text
backend/storage/automation/unattended_roadmap_loop_status.json
SESSION-HANDOFF.md
memorybank/activeContext.md
memorybank/currentRoadmap.md
memorybank/progress.md
docs/video-to-analysis-finish-line-roadmap-guide.md
```

## Required Verification

Run these at every 50-batch checkpoint and at the final closeout:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  backend/tests/test_run_video_to_analysis_real_video_scaleout_execution_chain.py \
  backend/tests/test_run_video_to_analysis_bounded_next_sample_execution_chain.py \
  backend/tests/test_run_video_to_analysis_source_pool_replenishment_plan.py \
  backend/tests/test_run_video_to_analysis_detector_evaluation_reentry_chain.py \
  backend/tests/test_unattended_roadmap_loop.py -q
```

Run reentry tests when heartbeat/docs are refreshed:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  backend/tests/test_run_video_to_analysis_detector_evaluation_reentry_chain.py \
  backend/tests/test_unattended_roadmap_loop.py -q
```

Run compile checks:

```bash
python3 -m py_compile $(rg --files backend/scripts | rg 'run_video_to_analysis|run_source_robustness|run_v7_')
```

Run JSON sanity:

```bash
python3 - <<'PY'
import json
from pathlib import Path

root = Path("backend/storage/trained_detector_candidates/touchline_detector_candidate_v7")
summaries = sorted(root.glob("video_to_analysis_*_v*/**/*summary.json"))
if not summaries:
    raise SystemExit("no video_to_analysis summaries found")
latest = max(summaries, key=lambda p: p.stat().st_mtime)
data = json.loads(latest.read_text())
print("latest", latest)
print("batchName", data.get("batchName"))
print("goalAchieved", data.get("goalAchieved"))
print("primaryBlocker", data.get("primaryBlocker"))
print("nextRecommendedNextLever", data.get("nextRecommendedNextLever"))
for key in [
    "trainingExecuted",
    "promotionMutationExecuted",
    "runtimeDefaultMutationExecuted",
    "videoDownloadExecuted",
    "dataDownloadExecuted",
    "normalStorageMutationExecuted",
    "cleanupDeletionExecuted",
]:
    print(key, data.get(key, False))
PY
```

Run environment hygiene:

```bash
df -h /
runpodctl pod list --all -o json
git status --short
```

If a verification command fails, use the three-attempt failsafe. Do not claim completion until verification passes or the closeout explicitly records the failed verification and blocker.

## Final Response Contract For Codex CLI

The final CLI response must include:

```text
final closeout summary path
batchName
goalAchieved
primaryBlocker
stopReason
executedBatchCount
latestGeneratedTruthPath
nextRecommendedNextLever
guardrail truth
verification commands and pass/fail result
disk status
RunPod status
files changed
exact next short /goal prompt if autonomous work remains
```

If autonomous work remains only because of the configured cap, provide a short next prompt that points back to the latest closeout summary and says to continue from `nextRecommendedNextLever`.

If the process is blocked on human/non-autonomous work, say exactly what the human must do and which file or UI to use.

## Priority Order

Execute in this priority order whenever multiple generated levers are possible:

1. Continue from the live heartbeat `nextRecommendedNextLever`.
2. Finish active real-video scaleout chains.
3. Drain bounded sample chains.
4. Run source-pool recovery and plan refresh when exhaustion is proven.
5. Run product/operator acceptance and report-route binding gates.
6. Run external benchmark/SoccerNet bounded lanes only from local authorized or explicitly approved inputs.
7. Run detector-training decision gates, and train only when generated truth authorizes audited training.
8. Write cleanup maps and storage hygiene reports without destructive deletion.
9. Write the total finishline closeout and refresh heartbeat/docs.

## Self-Review Checklist

Before marking the goal complete:

- [ ] The latest generated truth path exists.
- [ ] The heartbeat points at the final closeout or latest generated truth.
- [ ] The final closeout names the actual next lever.
- [ ] Guardrails are recorded and any true value has an approval artifact path.
- [ ] Focused tests passed or a verification blocker is recorded.
- [ ] `py_compile` passed or a verification blocker is recorded.
- [ ] Disk status is recorded.
- [ ] RunPod status is recorded.
- [ ] Dirty worktree state is described without reverting unrelated user changes.
- [ ] The final answer includes the exact next human or CLI action.
