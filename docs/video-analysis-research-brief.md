# Football Video Analysis Research Brief

This document is meant to be shared with another model, researcher, or engineer so they can quickly understand:

- what this project is trying to do,
- how the current pipeline works,
- what has already been tried,
- where the real blocker is,
- and what kind of research/help is actually useful now.

No secrets are included here. If this brief is shared externally, do not attach API keys, storage credentials, or private deployment details.

---

## 1. Short Version

We are building a single-camera football video analysis system that turns one uploaded match clip into structured tracking data, possession/events, tactical overlays, and coach-facing review surfaces.

The system already works end-to-end operationally, both locally and through GPU execution paths, but the current blocker is **truth quality on 5-minute clips**. Specifically:

- ball coverage is still not trustworthy enough,
- accepted ball tracks are still too edge-heavy or too sparse,
- controlled possession is too low,
- event richness is still too weak for believable tactical analysis.

The main research question is no longer “how do we make the pipeline run?”  
It is now:

> How do we get a more truthful ball signal from difficult single-camera match video, especially across longer clips, without filling the system with edge-heavy false positives?

---

## 2. What We Are Trying To Build

The product goal is a low-cost football analytics system for grassroots / academy / amateur teams.

Input:
- one uploaded match video from a single wide camera

Output:
- tracked player + ball positions on a 2D tactical pitch
- possession assignments
- detected event families like pass / recovery / turnover / shot / tackle
- match analytics and coach-facing tactical surfaces
- uncertainty/trust feedback when the tracking quality is not good enough

The big constraint is that this is **single-camera**, not a multi-camera pro system. That means the system has to recover useful football structure from imperfect footage, occlusions, bad ball visibility, and camera drift.

---

## 3. Current Architecture

## Backend

Main files:

- `backend/run_guerilla.py`
- `backend/app/processor.py`
- `backend/app/run_benchmarks.py`
- `backend/app/analytics.py`
- `backend/app/team_classification.py`
- `backend/app/homography_utils.py`
- `backend/app/main.py`
- `backend/app/storage.py`

What they do:

- `run_guerilla.py`
  - core video-processing path
  - YOLO + BoT-SORT tracking
  - homography projection
  - torso-color extraction
  - ball recovery / proposal / suppression logic
  - emits raw tracking rows + debug artifacts

- `processor.py`
  - takes the pipeline output and persists:
    - `raw_rows.json`
    - `frames.json`
    - `analytics.json`
    - `events.json`
    - debug artifacts like `ball_truth_layers.json`, `recovery_debug.json`, `recovery_profile_matrix.json`, `ball_pipeline_trace.json`

- `run_benchmarks.py`
  - computes the trust summary for a saved match
  - exposes the truth-gate metrics that decide whether a result is analytically usable

- `analytics.py`
  - converts raw rows into frame-level structures
  - assigns ball possession
  - computes events and summary metrics

- `team_classification.py`
  - clusters torso colors into team groups
  - supports explicit selected-cluster promotion (`myTeamCluster`)

- `main.py`
  - FastAPI app
  - upload / job / match / benchmark / config / annotations / trust-crop endpoints

## Frontend

Main file:

- `frontend/src/components/TacticalPitch.tsx`

The frontend consumes normalized pitch coordinates (`0..100`) and renders:

- players
- ball
- speed overlays
- passing network
- zones
- heatmaps
- shot markers
- annotations

This is important because the system contract is currently **normalized 0..100 pitch space**, not direct meter coordinates.

---

## 4. Core Data Flow

Current flow:

1. User uploads a video
2. Backend runs `process_video(...)` from `run_guerilla.py`
3. YOLO/BoT-SORT generate raw rows for players and ball
4. Homography projects detections into pitch coordinates
5. Torso colors are collected per track for later team clustering
6. Ball-specific recovery logic tries to supplement weak ball detection
7. Raw rows are persisted
8. Rows are normalized into `FrameData`
9. Possession, events, summaries, and trust metrics are computed
10. Frontend and benchmark endpoints read from those saved artifacts

There is also a reprocessing path:

- raw rows are stored,
- team clusters are stored,
- if the user chooses a different `myTeamCluster`,
- the system can reclassify rows and recompute analytics without rerunning heavy tracking.

---

## 5. Important Current Design Decisions

## A. Ball truth is explicitly layered

This is one of the most important parts of the current system.

The system distinguishes:

- `observedBall`
  - directly observed ball rows from detector/probe passes

- `inferredBall`
  - recovery-selected / bridge-selected rows

- `acceptedBall`
  - only the ball rows trusted enough to drive downstream possession/events/analytics

This matters because the system is no longer pretending there is always one clean global ball track.  
It explicitly models uncertainty and gaps.

## B. The benchmark/truth gate is the real arbiter

A run is only considered analytically useful if the benchmark summary says so.

Current 5-minute gate logic in `backend/app/run_benchmarks.py` requires:

- enough accepted ball coverage
- viable ball track quality
- controlled possession ratio high enough
- enough event families
- at least one `pass` or `turnover`

The important current reasons are:

- `Accepted ball layer is still too sparse for truthful 5-10 minute analysis`
- `Need viable ball track: meaningful motion and edgeFrameShare <= 60%`
- `Need controlled possession frames/frameCount >= 20% for truthful 5-10 minute analysis`
- `Need at least 3 event families`
- `Need at least one pass or turnover event`

## C. Team selection is explicit, not implicit

The system can detect team color clusters, but the user may still need to select which cluster is “my team”.

This is good product behavior, but it means:

- team classification can improve downstream analytics a lot,
- yet team selection is no longer the main blocker in the current 5-minute proof lane.

---

## 6. Current Detection / Recovery Strategy

The current pipeline is not just “YOLO finds the ball”.

It has multiple layers trying to make the ball track more truthful:

- primary tracker pass
- direct ball-only probe pass
- recovery passes with crop windows
- player-window-bounded recovery
- continuity-biased collapsing
- edge suppression
- anchor-corridor recovery mode
- player-proposal recovery mode

The current system is therefore already doing a fair amount of specialized recovery work.  
The problem is not lack of effort. The problem is that the extra candidate-generation logic still has not produced enough truthful accepted ball coverage on the 5-minute clip.

---

## 7. What Has Already Been Tried

Below is the honest short history of the main experiments.

## 1. Segment-first accepted ball truth

Effect:
- improved from almost no accepted signal to a small but clean accepted layer

Representative result:
- `acceptedBallFrames=16`
- all accepted signal still effectively too sparse for truthful 5-minute use

Meaning:
- better structure than before
- still nowhere near enough usable coverage

## 2. Observed-ball density expansion

Effect:
- huge increase in raw/accepted ball coverage

Representative result:
- `observedBallFrames=928`
- `acceptedBallFrames=934`

But:
- this mostly created edge-heavy false signal
- event/possession quality did not become truth-ready

Meaning:
- raw coverage alone is not the answer
- we learned that “more ball frames” can still be wrong

## 3. Explicit selected-cluster promotion

Effect:
- materially improved controlled possession once the right team cluster was selected

Representative result after promotion:
- `controlledPossessionFrames` moved from `0` to around `85-98`
- event family count improved

Meaning:
- team selection mattered
- but it did **not** solve the deeper ball-truth problem

## 4. Probe false-ball suppression

Effect:
- reduced the edge-heavy flood
- produced cleaner accepted ball signal

Representative result:
- `acceptedBallFrames=97`
- `supportedAcceptedBallRatio=0.969`
- `unsupportedAcceptedEdgeFrames=1`
- but `ballTrackEdgeFrameShare=0.835`
- still `ballTrackViable=false`

Meaning:
- this was a real quality improvement
- but still not enough to pass the viability gate

## 5. Anchor-corridor recovery

Effect:
- basically no meaningful contribution on the real 5-minute proof

Representative diagnostics:
- `corridorCandidateFrames=0`
- `corridorFramesWithTwoAnchors=0`
- `corridorFramesWithSingleAnchor=0`

Meaning:
- not the winning lane for this clip

## 6. Player-proposal expansion

Effect:
- also failed to produce meaningful proposal opportunity on the real clip

Representative diagnostics:
- `proposalCandidateFrames=0`
- `proposalWindowCount=0`

Representative post-promotion result:
- `acceptedBallFrames=101`
- `controlledPossessionFrames=98`
- `eventFamilyCount=5`
- `ballTrackEdgeFrameShare=0.812`
- `ballTrackViable=false`

Meaning:
- this experiment is effectively closed as a miss on the current clip

---

## 8. Current State Of The Problem

The current 5-minute lane is no longer blocked by infrastructure first.

We already proved:

- local path works
- remote/serverless path can work
- pod GPU path works
- local/remote parity can be reached
- selected-cluster promotion works
- benchmark artifacts and debug artifacts are being persisted

So the main blocker is now **model/pipeline truth quality**, especially around the ball.

### The practical blocker

We still do not get enough accepted ball coverage that is simultaneously:

- in-field / not edge-dominated
- motion-plausible
- close enough to players often enough to support possession
- continuous enough to produce believable events

### The current failure pattern

The system tends to oscillate between two bad states:

1. **Too sparse**
   - accepted ball layer is too small to drive possession/events

2. **Too dense but false**
   - lots of ball frames appear, but they hug edges, fail viability, and do not become trustworthy football state

That tradeoff is the real research problem.

---

## 9. Current Best Read On The Root Cause

The most likely current root problem is:

> We still do not have a strong enough candidate-generation and suppression strategy for the ball on difficult single-camera footage.

More specifically:

- primary ball detections are weak or intermittent
- recovery can generate candidates, but many are not football-truthful
- suppression improves quality, but often collapses coverage too far
- proposal/corridor expansions have not added enough new truthful signal
- possession and event logic are downstream consumers, so they can only be as good as the accepted ball layer

This means the current bottleneck is probably **before** event logic and **before** fancy analytics.  
It is upstream in ball candidate generation, filtering, and acceptance.

---

## 10. What Probably Is *Not* The Main Problem Right Now

These are important, but they do not look like the primary blocker:

- frontend rendering
- analytics formulas
- storage/persistence architecture
- selected-cluster promotion mechanics
- local/remote parity
- report generation

Also from the recent reference-analysis pass:

- homography is already present and is not the main missing piece
- stub caching/orchestration would help engineering speed, not result quality
- team assignment could still be improved, but it is not the main blocker in the current 5-minute truth lane

---

## 11. What Research Would Be Most Useful Now

The most useful research/help would target **single-camera football ball-truth recovery**, not generic app architecture.

Best topics to research:

## A. Ball candidate generation under sparse direct detection

Research questions:
- How do strong systems recover ball state when direct detections are intermittent?
- What seed-based recovery methods work best with sparse trusted observations?
- How do people expand from observed anchors without flooding the system with false candidates?

## B. False-positive suppression for edge-heavy ball detections

Research questions:
- What are the best heuristics or models for suppressing edge-hugging false ball detections?
- How do existing sports-tracking pipelines reject boundary artifacts?
- Are there good motion/plausibility filters for ball candidates on a projected pitch?

## C. Player-supported ball plausibility

Research questions:
- How should player proximity, continuity, and ball speed jointly determine candidate trust?
- What support heuristics are used in sports tracking when the ball is partially occluded?
- How do systems distinguish “true loose ball” from “random bright false positive near the edge”?

## D. Single-camera football tracking references

Especially useful:
- open-source football tracking projects that explicitly discuss ball recovery
- papers/blogs/repos about broadcast or sideline single-camera sports tracking
- methods that separate direct observation from inferred state

## E. Team clustering robustness

This is secondary, but still potentially valuable:
- jersey-color extraction from torso crops
- HSV / dominant-color methods
- background rejection in kit clustering

---

## 12. What Kind Of Advice Would Actually Help

Useful help:

- concrete algorithm ideas for ball candidate generation
- ways to score ball candidates using pitch-space plausibility
- ideas for anchor-seeded recovery when direct detections are sparse
- better suppression approaches for edge-dominated false positives
- references to football/sports tracking work that specifically handles weak ball visibility

Less useful help right now:

- generic UI/product suggestions
- generic “use a better model” advice without a concrete path
- recommendations to scale to longer clips before the 5-minute truth gates pass
- infrastructure-only advice unless it directly affects proof reliability

---

## 13. Suggested External Research Questions

If this brief is given to another model or engineer, these are the best questions to ask:

1. **How should a single-camera football pipeline recover ball state when direct ball detections are intermittent and false positives are edge-heavy?**
2. **What candidate-generation strategies outperform naive crop expansion from player windows or anchor corridors?**
3. **What are strong heuristics or learned signals for rejecting false ball detections near touchlines / frame edges / high-contrast clutter?**
4. **How should observed, inferred, and accepted ball layers be scored so downstream possession/events stay truthful?**
5. **Are there open-source football tracking repos or papers with better ball-recovery logic than simple YOLO + crop retries?**
6. **Given a pipeline already using homography and normalized pitch space, what additions most improve ball-track truth without a full rewrite?**
7. **What torso-color / jersey-clustering techniques are meaningfully better than mean RGB torso sampling in this context?**

---

## 14. Representative Current Numbers

These numbers are useful because they show the shape of the problem:

### Cleaner but still failing proof lane
- `acceptedBallFrames ≈ 97-101`
- `controlledPossessionFrames ≈ 94-98`
- `supportedAcceptedBallRatio ≈ 0.969`
- `ballTrackEdgeFrameShare ≈ 0.812-0.835`
- `ballTrackViable = false`

### Failed dense lane
- `acceptedBallFrames ≈ 934`
- but still not truth-ready because signal quality was too false / edge-heavy

### Key interpretation
- we can get **more** ball frames
- we can get **cleaner** ball frames
- but we still cannot get enough **truthful, viable, downstream-usable** ball signal on the 5-minute clip

---

## 15. Current Recommendation

The next research/implementation batch should focus on:

1. better ball candidate generation before recovery scoring
2. better false-negative suppression / anchor-seeding logic
3. better edge-heavy false-positive rejection

And should **not** focus first on:

1. longer clips
2. frontend redesign
3. homography rewrites
4. orchestration refactors
5. reopening team-selection tuning as the main explanation

---

## 16. File Guide For Anyone Investigating

If someone wants to inspect the real implementation, these are the best entry points:

### Most important
- `backend/run_guerilla.py`
- `backend/app/run_benchmarks.py`
- `backend/app/processor.py`
- `backend/app/analytics.py`

### Important supporting files
- `backend/app/team_classification.py`
- `backend/app/homography_utils.py`
- `backend/app/main.py`
- `frontend/src/components/TacticalPitch.tsx`

### Context docs
- `SESSION-HANDOFF.md`
- `docs/superpowers/plans/2026-04-11-active-now-systematic-roadmap.md`
- `docs/superpowers/plans/2026-04-13-player-proposal-expansion-sprint.md`
- `docs/superpowers/plans/2026-04-13-pod-first-proof-recovery-sprint.md`
- `docs/reference_implementations_analysis.md`

---

## 17. Final One-Paragraph Summary

We are building a single-camera football analytics pipeline that converts uploaded match video into tracked players/ball, possession, events, and tactical review surfaces. The system now runs end-to-end and has explicit trust gates, but the current 5-minute clip still fails because the accepted ball layer is either too sparse or too edge-heavy to support believable possession and event extraction. We have already tried segment-first acceptance, observed-density expansion, selected-cluster promotion, probe false-ball suppression, anchor-corridor recovery, and player-proposal expansion; the best recent lane reaches roughly `97-101` accepted ball frames and `94-98` controlled possession frames, but still fails viability because edge share remains too high and the ball truth is not robust enough. The next useful research should focus on better ball candidate generation, better edge-heavy false-positive rejection, and better anchor-seeded recovery for single-camera football footage, not on frontend work or general infrastructure changes.
