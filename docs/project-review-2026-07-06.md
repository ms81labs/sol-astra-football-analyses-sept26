# Project Review - 2026-07-06

## Scope

This review rehydrates the `fotball-analyst` project after roughly two months away. It checks live generated truth, roadmap docs, memorybank state, git/worktree health, storage, RunPod hygiene, and focused verification.

## Executive State

The active project state is terminal for the current milestone:

```text
video_to_analysis_manual_operator_release_decision_v1
-> video_to_analysis_current_milestone_done
```

Authoritative heartbeat:

```text
backend/storage/automation/unattended_roadmap_loop_status.json
```

Authoritative generated truth:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_manual_operator_release_decision_v1/
    manual_operator_release_decision_summary.json
```

Key truth values:

```text
goalAchieved = true
primaryBlocker = null
selectedOperatorDecision = declare_current_milestone_done
v7_3CurrentMilestoneDeclaredDone = true
optionalCoverageLoopDeferred = true
nextRecommendedNextLever = video_to_analysis_current_milestone_done
releasedRuntimeVersion = v7.3
activeRuntimeDefaultVersion = v7.3
```

Interpretation:

```text
The current v7.3 product/runtime milestone is done.
Do not auto-resume source-pool replenishment.
Treat more source sampling, new real-source acquisition, or future training as separate operator-approved work.
```

## What Was Finished

The project moved from detector/data work into a packaged product/runtime milestone:

- v7.3 became the active runtime default.
- Current release truth was archived.
- Steady-state monitoring passed.
- Operator dashboard polish passed.
- Real-source consolidation was attempted deliberately.
- The source-pool loop was proven to be optional coverage work, not a required finish-line blocker.
- A manual operator decision was recorded to declare the milestone done.

The final closeout artifact is:

```text
video_to_analysis_manual_operator_release_decision_v1
```

It writes:

- `manual_operator_release_decision_summary.json`
- `current_milestone_closeout.json`
- `manual_next_choices.json`
- `operator_release_decision_readout.md`
- `decision_matrix.json`
- `failsafe_attempt_plan.json`

## Guardrails

The terminal batch preserved these current-batch guardrails:

```text
trainingExecuted = false
promotionMutationExecuted = false
runtimeDefaultMutationExecuted = false
videoDownloadExecuted = false
dataDownloadExecuted = false
normalMatchStorageMutationExecuted = false
cleanupDeletionExecuted = false
candidateReadyForEvaluation = false
promotionReady = false
```

Historical note:

```text
backend/storage/runtime/promoted_touchline_detector_candidate.json
```

shows the earlier runtime default mutation did execute and close for v7.3. The terminal manual-decision batch itself did not perform a new runtime mutation.

## Current Verification

Commands run during this review:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  backend/tests/test_run_video_to_analysis_manual_operator_release_decision.py \
  backend/tests/test_run_video_to_analysis_current_release_acceptance_decision_surface.py \
  backend/tests/test_run_video_to_analysis_roadmap_state_reconciliation.py -q

python3 -m py_compile \
  backend/scripts/run_video_to_analysis_manual_operator_release_decision.py \
  backend/scripts/run_video_to_analysis_current_release_acceptance_decision_surface.py \
  backend/scripts/run_video_to_analysis_roadmap_state_reconciliation.py

runpodctl pod list --all -o json
```

Results:

```text
focused pytest: 8 passed in 2.27s
py_compile: passed
heartbeat/truth consistency: passed
RunPod pods: []
disk: 65G free, 56% used
```

## Git And Worktree Health

Current branch:

```text
recovery-history-batch-current
```

Current HEAD:

```text
bc4f4e30 2026-05-04 15:14:21 +0000 Review external dataset access for v7.2
```

Worktree status summary:

```text
modified files: 30
deleted tracked files: 14
untracked files: 440
```

Most untracked files are generated scripts/tests/docs from the later roadmap work:

```text
201 backend/scripts
163 backend/tests
67 docs/superpowers
```

Risk:

```text
The generated truth says the project reached a v7.3 milestone closeout,
but most of the machinery and artifacts that prove that state are not committed.
```

This is the main operational risk now. The code may work locally, but a clean checkout will not necessarily have the same roadmap machinery unless those files are intentionally committed or archived.

## Storage

Current local storage:

```text
/dev/sda1: 150G total, 80G used, 65G free, 56% used
backend/storage: 9.4G
touchline_detector_candidate_v7: 7.8G
```

Largest artifacts found:

```text
2575.6 MB soccertrack selected_match_117092 gsr 2nd JSON
2570.4 MB soccertrack selected_match_117092 gsr 1st JSON
303.4 MB soccertrack raw tracker XML
226.6 MB SoccerNet extracted video
58.9 MB Soccernet API probe venv artifact
```

Storage is currently fine. If external-source work resumes, the first non-product task should be storage policy and artifact packaging, not more blind data fetching.

## Current Product/Runtime State

The v7.3 runtime default is active in:

```text
backend/storage/runtime/promoted_touchline_detector_candidate.json
```

The release archive confirms v7.3:

```text
video_to_analysis_release_acceptance_archive_v2
```

The current milestone closeout confirms:

```text
v7.3 is the active packaged runtime for the current milestone
source-pool replenishment remains available only as optional coverage
```

## Main Findings

### Finding 1 - The milestone is done, but the repo is not clean

Generated truth is coherent and says the current v7.3 milestone is complete. Git state is very dirty, with hundreds of untracked files and many generated artifacts.

Impact:

```text
Clean-session reproducibility is weak until the useful scripts/tests/docs/artifacts are either committed, archived, or intentionally ignored.
```

### Finding 2 - Optional coverage was correctly stopped

The previous source-pool replenishment loops were not failures; they were optional coverage loops that repeatedly exhausted candidate pools. The final decision surface correctly prevented another blind `continue`.

Impact:

```text
Do not resume source-pool replenishment unless the explicit goal is more coverage, not finish-line completion.
```

### Finding 3 - Training is not the next default move

The project already reached a v7.3 runtime milestone. Training should only reopen from new, reviewed real miss truth.

Impact:

```text
The honest training lane is v7_4_training_decision_from_real_misses, not another automatic retrain.
```

### Finding 4 - External-source data exists but should be bounded

There is already real external-source material locally, including large SoccerTrack and SoccerNet artifacts. Disk is okay now, but another uncontrolled fetch could make the repo hard to operate.

Impact:

```text
If external benchmarking resumes, start with inventory, sample selection, and retention policy.
```

## Recommended Next Decisions

### Option A - Package And Commit The Milestone

Recommended if the goal is to preserve the work and stop losing state between sessions.

Tasks:

1. classify changed/untracked files into source, tests, docs, generated truth, large data, local-only junk
2. commit source/tests/docs/essential generated truth
3. move or ignore bulky generated/data artifacts as policy requires
4. run focused tests and a smoke route check

### Option B - Product Smoke And Operator Walkthrough

Recommended if the goal is to verify the app from an operator perspective after two months.

Tasks:

1. start the app
2. open the operator dashboard / release readout / acceptance report routes
3. verify v7.3 is shown as active
4. run one bounded product smoke against existing storage

### Option C - Resume Optional Coverage

Only choose this if more source coverage is desired.

Tasks:

1. run source-pool replenishment as optional coverage
2. keep storage limits explicit
3. stop at exhaustion instead of treating it as a blocker

### Option D - Reopen Training From Real Misses

Only choose this if new reviewed miss truth exists.

Tasks:

1. collect real miss cases
2. review labels
3. decide whether v7.4 training is actually needed
4. retrain only from evidence

## Best Next Move

The best next move is:

```text
project_housekeeping_and_release_packaging
```

Reason:

```text
The milestone is logically complete, but the repository is too dirty to trust as a durable handoff.
Before new model/data work, preserve the result cleanly.
```

Suggested first batch:

```text
video_to_analysis_v7_3_release_packaging_and_worktree_triage
```

Success criteria:

```text
essential source/test/docs/truth files identified
large/generated artifacts classified
no accidental data deletion
focused tests pass
runtime heartbeat still points to video_to_analysis_current_milestone_done
clear commit or archive plan written
```

## Update - Packaging Triage Executed

The first no-GPU readiness batch has now run:

```text
video_to_analysis_v7_3_release_packaging_and_worktree_triage_v1
-> video_to_analysis_v7_3_release_packaging_commit_plan
```

Authoritative truth:

```text
backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_v7_3_release_packaging_and_worktree_triage_v1/
    release_packaging_worktree_triage_summary.json
```

Result:

```text
goalAchieved = true
primaryBlocker = null
gpuRequired = false
worktreeTriageReady = true
totalDirtyPathCount = 487
sourceOrTestCandidateCount = 458
generatedTruthCandidateCount = 25
deletedTrackedPathCount = 14
largeArtifactCount = 5
nextRecommendedNextLever = video_to_analysis_v7_3_release_packaging_commit_plan
```

Verification:

```text
focused pytest = 10 passed in 1.31s
py_compile = passed
json sanity = passed
disk = 65G free, 56% used
RunPod pods = []
```
