# Platform And Research Brief

Date: 2026-04-11

This document is a plain-English snapshot of what the platform is, what parts are working, and which issues are currently the hardest and most worth researching.

It is not the live execution roadmap. For current task sequencing, use:

- `SESSION-HANDOFF.md`
- `docs/superpowers/plans/2026-04-11-active-now-systematic-roadmap.md`

## 1. What Platform We Are Building

We are building a local-first football video analysis platform.

The core pipeline is:

1. Upload a football match video.
2. Detect players and the ball frame by frame.
3. Track those detections across time.
4. Map camera coordinates into pitch coordinates.
5. Infer possession, events, and tactical summaries.
6. Review the result in a React app.
7. Export structured outputs like JSON, CSV, and HTML reports.

The important product idea is not "AI commentary." The real product is trustworthy structured football data extracted from a single-camera video workflow.

## 2. Main Platform Components

### Backend

- FastAPI API server
- Python video-processing pipeline
- YOLO-style detection for players and ball
- tracking and team classification
- match storage in SQLite plus JSON artifacts
- benchmark and trust-gate layer
- optional LLM layer for tactical text, but only after detector data exists

### Frontend

- React + TypeScript + Vite
- upload flow
- tactical pitch playback
- trust/review surfaces
- operator panels for annotations, issues, and benchmark-gated insights

### Remote GPU Path

- Runpod serverless worker image
- Runpod S3-compatible object storage for larger uploads
- app path can submit remote jobs and import results back into the local app workspace

### Data/Trust Layer

- benchmark summaries
- truth gates for 5-10 minute usefulness
- recovery debug artifacts
- trust crops for future human review and active learning

## 3. What Is Actually Working Right Now

These parts are real and already proven:

- local processing and review flow exists
- Runpod app-path submission works
- normal remote app path now uses `runsync` by default
- remote results import back into the app workspace works
- benchmark summaries and truth gates are wired
- local 1-minute calibration matrix finds viable ball-recovery profiles
- local 5-minute calibration matrix also finds viable profiles
- proof-diff tooling now compares local viability against remote imported truth

Important recent proof result:

- 5-minute normal app-path remote proof match id:
  - `dc49216600004d6a95c63528b4eccacb`
- outcome:
  - `rawRows: 12577`
  - `frameCount: 1516`
  - `playerFrames: 1516`
  - `ballFrames: 0`
  - `controlledPossessionFrames: 0`
  - `eventTypes: {}`
  - `fiveMinuteTruthReady: false`
- current diagnosis:
  - `local_viable_but_remote_ball_missing`

That diagnosis is the most important truth in the project right now.

## 4. The Biggest Tricky Issues

These are the hardest current issues, ordered by importance.

### Issue 1: Local Recovery Looks Viable, But Remote Imported Ball Data Collapses

Why it matters:

- Locally, the 5-minute recovery matrix can find a viable in-field ball chain.
- Remotely, the same 5-minute clip imports back with `ballFrames: 0`.
- This means the platform is not failing in only one place. It is failing in the transition between candidate generation, remote execution, and imported final match truth.

Why this is tricky:

- It is easy to get fooled by local diagnostics and think the system is healthy.
- It is also easy to blame Runpod infrastructure, but the job completes and player rows come back fine.
- The failure is likely deeper in the ball data path than simple transport or worker uptime.

Research questions:

- Where can a viable local recovered ball chain disappear before or during remote final import?
- Is the remote worker using the exact same recovery and selection behavior as local calibration?
- Are recovered rows being generated but later filtered out by downstream merge, normalization, or benchmark import logic?
- Is there any difference between matrix/debug execution and normal full-pipeline execution that explains the missing ball rows?

### Issue 2: Longer Clips Still Lose Ball Coverage And Possession Activation

Why it matters:

- Even when player tracking remains present across the clip, the system loses the ball and then loses possession and event activation.
- Without ball coverage, tactical outputs are not trustworthy.

Why this is tricky:

- The 1-minute proof is good enough to look promising.
- The 5-minute proof is long enough to expose collapse.
- That suggests we may have a temporal stability problem, not just a raw detection problem.

Research questions:

- What failure patterns commonly cause single-camera football ball tracking to degrade over longer windows?
- How do strong pipelines recover from long ball-occlusion stretches without hallucinating the ball?
- What heuristics are best for keeping possession state alive during brief ball uncertainty without inventing fake certainty?

### Issue 3: Event Detection Is Starved By Missing Ball Signal

Why it matters:

- Event families like pass, turnover, and recovery depend on ball ownership and ball movement.
- When ball frames go to zero, event types also go empty.
- This blocks the truth gates and makes the report/LLM layer correctly pause.

Why this is tricky:

- Event detection might look like its own problem, but right now it is probably downstream damage from the ball signal problem.
- We do not want to "fake" event richness just to satisfy gates.

Research questions:

- Which event families can be inferred robustly from partial ball signal plus player motion?
- Which event detectors should stay disabled until ball confidence crosses a threshold?
- What are good honesty-preserving fallback strategies for low-ball-signal clips?

### Issue 4: Candidate Generation Is Better, But Still Probably Too Fragile

Why it matters:

- We improved the recovery lane by suppressing edge-anchor junk and preferring coherent in-field chains.
- That was enough to make the local 5-minute matrix viable.
- It was not enough to make the real remote app-path proof truthful.

Why this is tricky:

- That usually means current candidate generation may still be too weak or too brittle outside the calibration harness.
- A local "best chain" can exist while the final production path still ends up with no accepted ball track.

Research questions:

- What are good candidate-family diagnostics for football ball tracking beyond confidence, path length, and edge share?
- How do production sports-vision systems score temporal coherence under occlusion?
- Should longer-clip recovery prefer segmented local truth instead of forcing one global track story?

### Issue 5: We Need Stronger End-To-End Equivalence Between Debug Paths And Production Paths

Why it matters:

- We now have multiple useful paths:
  - local recovery matrix
  - benchmark proof scripts
  - normal app upload path
  - remote Runpod worker path
- If those paths are not behaviorally equivalent where it matters, debugging gets misleading.

Why this is tricky:

- Each path is useful by itself.
- But each extra seam creates room for "works here, fails there" confusion.

Research questions:

- What is the best way to prove equivalence between calibration harness output and production import output?
- Which intermediate artifacts should always be saved so we can compare local and remote stages directly?
- What minimal golden dataset should be re-run on every important pipeline change?

### Issue 6: Repo Hygiene Is Manageable, But Still Adds Friction

Why it matters:

- The working tree is intentionally dirty.
- There is historical tracked cache churn under `backend/__pycache__/*.pyc`.
- There are many source and doc changes in flight at once.

Why this is tricky:

- This is not the main football-data blocker.
- But it makes review, shipping, and confidence slower than they should be.

Research questions:

- What is the safest path to de-risk repo state without destructive cleanup?
- How should we separate source-of-truth docs, experiments, generated artifacts, and historical baggage?

## 5. What Is Not The Main Problem Anymore

These used to be blockers, but they are not the primary issue right now:

- Runpod endpoint spin-up and deletion
- S3-compatible storage access
- the old async Runpod seam for the normal app path
- whether local recovery can find any viable 5-minute chain at all

Those were worth fixing, and we fixed enough of them to expose the real blocker.

## 6. Best Research Directions

If you want to research efficiently, focus here:

1. Single-camera football ball tracking failure modes on longer clips
2. Ball recovery under occlusion, clutter, and edge-anchor false positives
3. Temporal coherence scoring for sports-object tracks
4. Honest possession inference when ball observations are intermittent
5. End-to-end equivalence testing between calibration/debug harnesses and production pipelines

## 7. Current Bottom Line

The platform infrastructure is in much better shape than before.

The current hard problem is not "can we run a job remotely?" and not "can we find some promising local recovery output?" The hard problem is this:

We can produce a viable local ball-recovery story on a 5-minute clip, but the real remote app-path proof still imports zero ball frames and therefore zero possession and zero event activation.

That is the research seam most worth attacking next.
