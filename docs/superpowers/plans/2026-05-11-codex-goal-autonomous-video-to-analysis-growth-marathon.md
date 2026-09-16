# Codex Goal: Autonomous Video-To-Analysis Growth Marathon

Created: 2026-05-11

This file is written for Codex CLI `/goal`. It is intentionally broader than a single batch. The point is to let Codex keep working while the operator is away, but only inside deterministic/generated-truth lanes that do not require human labeling, manual approval, destructive cleanup, full dataset downloads, training, promotion, or runtime-default mutation.

Reference pattern: https://developers.openai.com/codex/use-cases/follow-goals

## Goal

Advance the video-to-analysis roadmap as far as possible through the autonomous scaleout and bounded next-sample growth lane, starting from:

```text
video_to_analysis_real_video_scaleout_execution_approval
```

Continue through every generated next lever that is safe and deterministic until a real stop condition is reached, then write/refresh the closeout truth, heartbeat, roadmap docs, and verification evidence.

## Why This Goal Exists

The current repo state says the operational surface is healthy:

```text
v7.3 is active and steady-state healthy.
operator dashboard is polished and route-smoked.
storage hygiene policy is ready.
growth lane decision snapshot selected bounded real-video scaleout execution approval.
```

The next work is not more planning. It is controlled execution of the generated roadmap chain.

## Current Authoritative Starting Point

Workspace:

```text
/root/WorkSpace/fotball-analyst
```

Heartbeat:

```text
backend/storage/automation/unattended_roadmap_loop_status.json
```

Current final generated truth:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_growth_lane_decision_snapshot_v1/
    growth_lane_decision_snapshot_summary.json
```

It must currently report:

```text
goalAchieved = true
primaryBlocker = null
roadmapAdvanceAllowed = true
selectedGrowthLever = video_to_analysis_real_video_scaleout_execution_approval
nextRecommendedNextLever = video_to_analysis_real_video_scaleout_execution_approval
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
```

If that is not true, stop and repair the heartbeat/generated truth alignment before doing any further work.

## Durable End State

Stop only when one of these conditions is reached.

### Success: Autonomous Lane Advanced And Closed

The goal is complete if:

- At least one full real-video scaleout chain has been executed from current truth:

```text
video_to_analysis_real_video_scaleout_execution_approval
-> video_to_analysis_real_video_scaleout_bounded_execution
-> video_to_analysis_real_video_scaleout_report_route_binding
-> video_to_analysis_real_video_scaleout_lane_closeout
-> video_to_analysis_next_sample_selection_snapshot
```

- All bounded next-sample candidates selected by the latest snapshot have been consumed through:

```text
video_to_analysis_bounded_next_sample_execution_approval
-> video_to_analysis_bounded_next_sample_execution
-> video_to_analysis_bounded_next_sample_report_route_binding
-> video_to_analysis_bounded_next_sample_closeout
-> video_to_analysis_scaleout_or_backlog_decision_snapshot
-> video_to_analysis_source_and_artifact_cleanup_map
```

- If the bounded next-sample pool exhausts, at least one autonomous recovery path has been attempted:

```text
video_to_analysis_real_video_scaleout_plan_refresh
```

and, if selected by generated truth:

```text
video_to_analysis_real_video_scaleout_source_sampling_expansion
-> video_to_analysis_real_video_scaleout_plan_refresh
```

- If generated truth routes to source-pool replenishment and the existing scripts are non-download/non-mutating, execute:

```text
video_to_analysis_source_pool_replenishment_plan
-> video_to_analysis_source_pool_replenishment_approval
-> video_to_analysis_real_video_scaleout_plan_refresh
```

- A final snapshot/closeout artifact states the lane position and next lever.
- `backend/storage/automation/unattended_roadmap_loop_status.json` and roadmap docs are refreshed from final generated truth.
- Verification commands pass.

### Valid Stop: Non-Autonomous Gate Reached

The goal is also complete if generated truth reaches a next lever that is not safe to execute unattended, such as:

```text
manual_strategic_lane_selection_required
manual_review_required
human_label_review_required
dataset_access_human_approval_required
full_dataset_download_approval_required
training_approval_required
promotion_review_manual_approval_required
runtime_default_mutation_manual_approval_required
```

In that case:

- Do not bypass the gate.
- Write/refresh a final generated truth or closeout summary naming the blocker/gate.
- Update heartbeat/docs.
- Run verification for the code and truth surfaces touched.

### Valid Stop: Generated Blocker

If any batch fails with `goalAchieved = false` and a specific `primaryBlocker`, do not thrash blindly.

Use up to 3 attempts:

1. Reproduce and inspect the generated truth.
2. Repair only the scoped issue if it is code/artifact plumbing.
3. Re-run focused tests and the failed batch.

If still blocked, write a blocker summary with exactly one `nextRecommendedNextLever`, refresh heartbeat/docs, and stop.

### Valid Stop: Safety Boundary

Stop if any next step would require:

- full dataset download
- new detector training
- promotion mutation
- runtime-default mutation
- destructive cleanup
- normal match storage mutation
- auto-labeling model detections as truth
- external paid/long-running resource creation not already encoded by generated truth

## Timebox

The intended operator-away window is about 3 hours.

Work until one of the stop conditions above, or until either:

```text
30 generated batch scripts have executed successfully
```

or:

```text
available disk drops below 25G
```

If the cap is reached while the chain is still safe and deterministic, write a progress closeout artifact and select the next exact lever for the next session.

## Read First

Read these before changing code or running the chain:

```text
backend/storage/automation/unattended_roadmap_loop_status.json
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/video_to_analysis_growth_lane_decision_snapshot_v1/growth_lane_decision_snapshot_summary.json
SESSION-HANDOFF.md
memorybank/activeContext.md
memorybank/currentRoadmap.md
memorybank/progress.md
docs/video-to-analysis-finish-line-roadmap-guide.md
```

Then inspect these scripts and tests:

```text
backend/scripts/run_video_to_analysis_real_video_scaleout_execution_approval.py
backend/scripts/run_video_to_analysis_real_video_scaleout_bounded_execution.py
backend/scripts/run_video_to_analysis_real_video_scaleout_report_route_binding.py
backend/scripts/run_video_to_analysis_real_video_scaleout_lane_closeout.py
backend/scripts/run_video_to_analysis_next_sample_selection_snapshot.py
backend/scripts/run_video_to_analysis_bounded_next_sample_execution_approval.py
backend/scripts/run_video_to_analysis_bounded_next_sample_execution.py
backend/scripts/run_video_to_analysis_bounded_next_sample_report_route_binding.py
backend/scripts/run_video_to_analysis_bounded_next_sample_closeout.py
backend/scripts/run_video_to_analysis_scaleout_or_backlog_decision_snapshot.py
backend/scripts/run_video_to_analysis_source_and_artifact_cleanup_map.py
backend/scripts/run_video_to_analysis_real_video_scaleout_plan_refresh.py
backend/scripts/run_video_to_analysis_real_video_scaleout_source_sampling_expansion.py
backend/scripts/run_video_to_analysis_source_pool_replenishment_plan.py
backend/scripts/run_video_to_analysis_source_pool_replenishment_approval.py
backend/scripts/run_video_to_analysis_next_roadmap_direction_snapshot.py
backend/tests/test_run_video_to_analysis_real_video_scaleout_execution_chain.py
backend/tests/test_run_video_to_analysis_bounded_next_sample_execution_chain.py
backend/tests/test_run_video_to_analysis_source_pool_replenishment_plan.py
```

## Versioning Rule

Do not overwrite old generated artifacts.

Before each batch, find the highest existing version for that batch prefix and write the next version with `--output-dir-name`.

Example:

```bash
python3 backend/scripts/run_video_to_analysis_real_video_scaleout_execution_approval.py \
  --output-dir-name video_to_analysis_real_video_scaleout_execution_approval_v64
```

Use the natural chain versioning already present in the repo. If a script intentionally pairs input/output versions, preserve that pairing.

If a script is designed to use the latest generated input via `latest_versioned_dir`, verify the selected `source*Dir` field in the output summary after running it.

## Autonomous Next-Lever Allowlist

Only auto-run next levers in this allowlist:

```text
video_to_analysis_real_video_scaleout_execution_approval
video_to_analysis_real_video_scaleout_bounded_execution
video_to_analysis_real_video_scaleout_report_route_binding
video_to_analysis_real_video_scaleout_lane_closeout
video_to_analysis_next_sample_selection_snapshot
video_to_analysis_bounded_next_sample_execution_approval
video_to_analysis_bounded_next_sample_execution
video_to_analysis_bounded_next_sample_report_route_binding
video_to_analysis_bounded_next_sample_closeout
video_to_analysis_scaleout_or_backlog_decision_snapshot
video_to_analysis_source_and_artifact_cleanup_map
video_to_analysis_real_video_scaleout_plan_refresh
video_to_analysis_real_video_scaleout_source_sampling_expansion
video_to_analysis_source_pool_replenishment_plan
video_to_analysis_source_pool_replenishment_approval
video_to_analysis_next_roadmap_direction_snapshot
```

If generated truth points to anything else, stop unless it is clearly a local, non-mutating route/doc/test repair needed by the current allowlisted batch.

## Command Map

Use this map for next-lever execution:

```text
video_to_analysis_real_video_scaleout_execution_approval
  python3 backend/scripts/run_video_to_analysis_real_video_scaleout_execution_approval.py --output-dir-name <next-version>

video_to_analysis_real_video_scaleout_bounded_execution
  python3 backend/scripts/run_video_to_analysis_real_video_scaleout_bounded_execution.py --output-dir-name <next-version>

video_to_analysis_real_video_scaleout_report_route_binding
  python3 backend/scripts/run_video_to_analysis_real_video_scaleout_report_route_binding.py --output-dir-name <next-version>

video_to_analysis_real_video_scaleout_lane_closeout
  python3 backend/scripts/run_video_to_analysis_real_video_scaleout_lane_closeout.py --output-dir-name <next-version>

video_to_analysis_next_sample_selection_snapshot
  python3 backend/scripts/run_video_to_analysis_next_sample_selection_snapshot.py --output-dir-name <next-version>

video_to_analysis_bounded_next_sample_execution_approval
  python3 backend/scripts/run_video_to_analysis_bounded_next_sample_execution_approval.py --output-dir-name <next-version>

video_to_analysis_bounded_next_sample_execution
  python3 backend/scripts/run_video_to_analysis_bounded_next_sample_execution.py --output-dir-name <next-version>

video_to_analysis_bounded_next_sample_report_route_binding
  python3 backend/scripts/run_video_to_analysis_bounded_next_sample_report_route_binding.py --output-dir-name <next-version>

video_to_analysis_bounded_next_sample_closeout
  python3 backend/scripts/run_video_to_analysis_bounded_next_sample_closeout.py --output-dir-name <next-version>

video_to_analysis_scaleout_or_backlog_decision_snapshot
  python3 backend/scripts/run_video_to_analysis_scaleout_or_backlog_decision_snapshot.py --output-dir-name <next-version>

video_to_analysis_source_and_artifact_cleanup_map
  python3 backend/scripts/run_video_to_analysis_source_and_artifact_cleanup_map.py --output-dir-name <next-version>

video_to_analysis_real_video_scaleout_plan_refresh
  python3 backend/scripts/run_video_to_analysis_real_video_scaleout_plan_refresh.py --output-dir-name <next-version>

video_to_analysis_real_video_scaleout_source_sampling_expansion
  python3 backend/scripts/run_video_to_analysis_real_video_scaleout_source_sampling_expansion.py --output-dir-name <next-version>

video_to_analysis_source_pool_replenishment_plan
  python3 backend/scripts/run_video_to_analysis_source_pool_replenishment_plan.py --output-dir-name <next-version>

video_to_analysis_source_pool_replenishment_approval
  python3 backend/scripts/run_video_to_analysis_source_pool_replenishment_approval.py --output-dir-name <next-version>

video_to_analysis_next_roadmap_direction_snapshot
  python3 backend/scripts/run_video_to_analysis_next_roadmap_direction_snapshot.py --output-dir-name <next-version>
```

## Work Algorithm

Use this loop:

1. Read `backend/storage/automation/unattended_roadmap_loop_status.json`.
2. Determine `nextRecommendedNextLever`.
3. If it is in the allowlist, run the matching command with the next versioned output dir.
4. Read the generated summary.
5. If `goalAchieved = true` and `primaryBlocker = null`, append it to the execution ledger and continue.
6. If `goalAchieved = false` and the next lever is an allowlisted recovery path, run the recovery path.
7. If a non-allowlisted or human gate appears, stop and write final closeout.
8. Every 5 generated batches, run focused tests and disk check.
9. At the end, run the full required verification set and refresh docs.

## Expected High-Value Cascade

From the current state, the first expected chain is:

```text
video_to_analysis_real_video_scaleout_execution_approval
-> video_to_analysis_real_video_scaleout_bounded_execution
-> video_to_analysis_real_video_scaleout_report_route_binding
-> video_to_analysis_real_video_scaleout_lane_closeout
-> video_to_analysis_next_sample_selection_snapshot
-> video_to_analysis_bounded_next_sample_execution_approval
-> video_to_analysis_bounded_next_sample_execution
-> video_to_analysis_bounded_next_sample_report_route_binding
-> video_to_analysis_bounded_next_sample_closeout
-> video_to_analysis_scaleout_or_backlog_decision_snapshot
-> video_to_analysis_source_and_artifact_cleanup_map
```

Then repeat bounded next-sample approval/execution for remaining candidates until:

```text
primaryBlocker = video_to_analysis_bounded_next_sample_pool_exhausted
nextRecommendedNextLever = video_to_analysis_real_video_scaleout_plan_refresh
```

Then refresh scaleout plan and continue if possible.

## Repair Rules

Allowed repairs:

- stale runtime version in operator/product view models
- wrong generated artifact path in heartbeat/docs
- stale output-dir reference
- route smoke binding bug
- summary field mismatch
- missing focused regression test for a bug found during this goal
- safe generated-truth script plumbing

Not allowed repairs:

- changing detector thresholds to make metrics pass
- deleting generated truth to hide failures
- modifying labels or review outputs
- creating positive truth from model detections
- starting training to improve results
- changing runtime default
- full dataset download
- destructive cleanup

## Heartbeat And Docs Refresh

After final stop, update:

```text
backend/storage/automation/unattended_roadmap_loop_status.json
SESSION-HANDOFF.md
memorybank/activeContext.md
memorybank/currentRoadmap.md
memorybank/progress.md
docs/video-to-analysis-finish-line-roadmap-guide.md
```

The refresh must include:

- final batch name
- final generated truth path
- final `goalAchieved`
- final `primaryBlocker`
- final `nextRecommendedNextLever`
- number of generated batches shipped in this goal
- mutation flags
- verification commands and results

## Required Verification

Run this focused test set:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  backend/tests/test_run_video_to_analysis_real_video_scaleout_execution_chain.py \
  backend/tests/test_run_video_to_analysis_bounded_next_sample_execution_chain.py \
  backend/tests/test_run_video_to_analysis_source_pool_replenishment_plan.py \
  backend/tests/test_unattended_roadmap_loop.py -q
```

Run py_compile:

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
  backend/scripts/run_video_to_analysis_source_pool_replenishment_plan.py \
  backend/scripts/run_video_to_analysis_source_pool_replenishment_approval.py \
  backend/scripts/run_video_to_analysis_next_roadmap_direction_snapshot.py
```

Run JSON sanity over the final generated truth path and every batch generated by this goal:

```bash
python3 - <<'PY'
import json
from pathlib import Path
status = json.loads(Path("backend/storage/automation/unattended_roadmap_loop_status.json").read_text())
print("activeBatchName =", status.get("activeBatchName"))
print("primaryBlocker =", status.get("primaryBlocker"))
print("nextRecommendedNextLever =", status.get("nextRecommendedNextLever"))
print("lastGeneratedTruthPath =", status.get("lastGeneratedTruthPath"))
final_path = Path(status["lastGeneratedTruthPath"])
final = json.loads(final_path.read_text())
print("final goalAchieved =", final.get("goalAchieved"))
print("final primaryBlocker =", final.get("primaryBlocker"))
print("final next =", final.get("nextRecommendedNextLever"))
for key in ["trainingExecuted", "promotionMutationExecuted", "runtimeDefaultMutationExecuted", "videoDownloadExecuted", "dataDownloadExecuted"]:
    print(key, "=", final.get(key))
PY
```

Run system hygiene:

```bash
df -h .
runpodctl pod list --all -o json
git status --short
```

## Final Report Required

Final response must include:

- final generated truth path
- final batch name
- final `primaryBlocker`
- final `nextRecommendedNextLever`
- count and names of batches executed in this goal
- whether any recovery loops were needed
- whether any source pool exhaustion occurred
- exact verification results
- disk and RunPod state
- list of files changed by this goal

Do not say "done" unless the verification commands above were run after the final artifact/doc refresh.
