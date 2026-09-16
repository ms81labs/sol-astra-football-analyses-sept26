# Video Analysis Enhancement Playbook

This document turns the current research and code analysis into a practical guide for improving this project without losing the useful parts of the existing pipeline.

It is intentionally written as an internal implementation guide, not a research summary. The goal is to answer:

- what should change,
- what should stay,
- where those changes belong in the code,
- what order to build them in,
- and how to judge whether each step actually improved the product.

---

## 1. Purpose

The project already does a lot:

- uploads a single-camera football video,
- runs tracking and homography projection,
- produces raw rows, frames, analytics, events, and trust artifacts,
- supports explicit team-cluster selection,
- and renders the result in a coach-facing frontend.

The current blocker is not “the app does not work.” The blocker is:

> the best 5-minute outputs still do not produce a truthful enough football state for reliable possession, event, and tactical interpretation.

The codebase has already evolved beyond naive tracking. It now includes:

- `observedBall`
- `inferredBall`
- `acceptedBall`
- probe suppression
- continuity-biased collapsing
- anchor-corridor recovery
- player-proposal recovery
- benchmark truth gates

Even with all of that, the system still tends to alternate between:

1. sparse-but-clean accepted ball,
2. dense-but-false accepted ball.

This playbook assumes the research conclusion is correct:

> the next major improvement should not be “another ball retry trick,” but a shift from ball-first truth to football-state truth.

---

## 2. Code-Verified Current Baseline

This section is based on the current code, not memory.

## What exists today

### Truth layers
`backend/run_guerilla.py` builds and returns:

- `observedBall`
- `inferredBall`
- `acceptedBall`

`backend/app/processor.py` persists those layers as artifacts and keeps them aligned with saved rows/frames.

### Benchmark gate
`backend/app/run_benchmarks.py` currently decides truth readiness mainly through:

- `acceptedBallFrames`
- `acceptedBallRatio`
- `acceptedFromObservedRatio`
- `ballTrackViable`
- `controlledPossessionFrames`
- event-family count and event presence
- `requiresTeamSelection`

### Team identity
The current team-selection flow is explicit and reprocessable:

- `backend/app/schemas.py` exposes `myTeamCluster`
- `backend/app/team_classification.py` clusters track colors
- `backend/app/processor.py` reclassifies rows during reprocessing

### Analytics contract
The current analytics flow is still frame-centric and ball-centric:

- raw rows -> `FrameData`
- possession assignment uses ball-to-player proximity logic
- events are derived from possession/player transitions

### Coordinate contract
The frontend and most backend contracts still assume:

- normalized pitch coordinates in `0..100`

This should not be broken casually.

---

## 3. Core Design Shift

## Current design

Today, the primary truth token is effectively:

- accepted ball rows

Those rows then drive:

- possession,
- event extraction,
- trust evaluation,
- tactical interpretation.

## Proposed design

The new primary truth token should become:

- `acceptedMatchState`

That means the system stops asking one ball coordinate stream to carry the whole product.

Instead, the system should explicitly represent the football situation per frame (or per sampled frame window), even when the visible ball is weak.

### Proposed state fields

At minimum, `acceptedMatchState` should contain:

- `frameId`
- `timestamp`
- `mode`
  - `controlled_possession`
  - `loose_ball`
  - `aerial_transit`
  - `restart_or_out`
  - `unknown`
- `controllingTeam`
  - `my_team | enemy | unassigned | contested | none`
- `controllingTrackId`
  - nullable
- `ballVisibility`
  - `visible | partially_visible | inferred | hidden`
- `ballEstimate`
  - position if available
  - optionally a bounded region or radius instead of fake point certainty
- `source`
  - `observed_ball`
  - `inferred_ball`
  - `player_conditioned`
  - `event_constrained`
  - `restart_rule`
- `confidence`
- `notes` or `reasonCodes`

### Why this is the right shift

This allows the system to say:

- “ball is not cleanly visible, but player #7 likely still controls possession”
- “ball is likely in aerial transit after a kick”
- “play is likely stopped / out / restarting”

instead of forcing every situation into:

- “there is definitely one clean ball point here.”

That is the key change needed to break the sparse-vs-false tradeoff.

---

## 4. What Should Stay

This is not a rewrite-from-scratch document.

The following parts of the current system should stay:

### Keep the current truth layers
Do not delete:

- `observedBall`
- `inferredBall`
- `acceptedBall`

They are still useful evidence layers.  
`acceptedMatchState` should sit above them, not replace them.

### Keep explicit team-cluster selection
The `myTeamCluster` flow is good product behavior and should remain.

### Keep the normalized frontend contract for now
The frontend can keep using `0..100` pitch coordinates while backend analytics gradually move toward real metres internally.

### Keep current proof infrastructure
Do not derail into infra work unless it directly blocks proof reliability.

### Keep existing debug artifacts
The repo already has useful artifacts and summaries. New work should extend them, not erase them.

---

## 5. What Should Change First

## Priority 1: Add `acceptedMatchState` as a new persisted artifact

### Goal
Introduce state-of-play truth without breaking the current ball-layer pipeline.

### Where it belongs

- `backend/run_guerilla.py`
  - produce the first version of match-state hypotheses
- `backend/app/processor.py`
  - persist the new artifact
- `backend/app/schemas.py`
  - add schemas if exposed over API
- `backend/app/main.py`
  - expose the artifact if needed

### First version should be modest
Do not wait for a perfect probabilistic model.  
Version 1 can be rule-driven and should focus on:

- possession mode,
- controlling player/team,
- visible vs inferred ball,
- out/restart windows,
- confidence/provenance.

### Deliverable
A new artifact, for example:

- `accepted_match_state.json`

or:

- `match_state_layers.json`

with stable per-frame records.

---

## Priority 2: Make invisible-ball windows player-conditioned

### Goal
When visible ball evidence is weak, infer the football situation from players first instead of forcing another weak ball coordinate.

### Where it belongs

- `backend/run_guerilla.py`
  - candidate generation and state inference
- `backend/app/analytics.py`
  - possession logic should learn to consume state, not just point distance

### Required shift
Today the logic is still too close to:

- “find ball point, then assign nearest player.”

We need a path that can instead do:

- “likely holder remains player X”
- “likely receiver is player Y”
- “ball is in transition after an action”
- “ball is temporarily hidden but possession is still stable”

### Immediate heuristic sources
Use:

- recent accepted holder continuity
- player spacing and likely receiver geometry
- support from accepted/inferred ball windows
- restart/out-of-play cues
- event hypotheses

---

## Priority 3: Redesign the benchmark from ball quality to state quality

## Current issue
The current gate is useful, but still heavily anchored on accepted-ball frame counts and viability.

## New benchmark structure

Keep the existing fields for backwards compatibility, but add five higher-level gates:

### 1. Visible-ball quality
- when ball is visible, how often is it plausible and stable?

### 2. Occluded-possession continuity
- when ball is not clearly visible, does the possession path remain believable?

### 3. Restart / out-of-play quality
- does the system correctly identify stoppages, restarts, and dead-ball segments?

### 4. Player truth quality
- player continuity
- team identity stability
- track reliability

### 5. Event consistency
- are passes / turnovers / recoveries / shots structurally plausible relative to the inferred state?

### Where it belongs

- `backend/app/run_benchmarks.py`

### Result
Instead of a single mostly ball-centric truth gate, the benchmark should produce:

- a per-dimension trust report
- an overall trust grade
- specific failure modes

This will let the system remain analytically useful even when visible-ball density is imperfect.

---

## Priority 4: Move analytics into metres and smooth calibration over time

## Why
Kinematic and workload-style outputs are only believable if:

- projection is stable,
- calibration does not jitter,
- speed/acceleration are computed in real units.

## Practical rule

- keep frontend display in `0..100`
- move backend physical analytics toward metres/seconds internally

## Where it belongs

- `backend/app/homography_utils.py`
- `backend/run_guerilla.py`
- `backend/app/analytics.py`

## Scope for first pass

Do not start with “full camera model rewrite.”

Start with:

- a stable internal metres representation,
- temporal smoothing on camera/homography estimates,
- smoothed velocity/acceleration estimation,
- explicit labeling of outputs as video-derived estimates.

### Important product rule
Do **not** market these as accelerometer-equivalent Catapult metrics.

Safe wording:

- estimated kinematics
- video-derived workload
- speed / acceleration proxies

Unsafe wording:

- PlayerLoad
- impact load
- wearable-equivalent workload

---

## Priority 5: Upgrade player truth and off-ball value

## Why
Long-term product value will not come only from perfect ball visibility. It will also come from:

- stable player tracks,
- better team identity,
- interpretable off-ball patterns.

## Where it belongs

- `backend/run_guerilla.py`
- `backend/app/team_classification.py`
- `backend/app/analytics.py`

## Near-term player improvements

### Team identity
Current torso sampling is useful but simple. The next likely gain is:

- more robust torso/jersey extraction,
- stronger color-space features,
- better background rejection.

### Player continuity
If future effort goes here, it should focus on:

- better tracklet stability,
- temporal smoothing,
- track confidence,
- explicit handling of low-confidence identity switches.

## Off-ball outputs to build

The most valuable off-ball outputs are likely:

- line height
- width / depth / compactness
- overloads / underloads
- occupation maps
- support shapes
- off-ball run families

This is probably the best medium-term product payoff even before ball truth becomes ideal.

---

## 6. File-by-File Implementation Map

## `backend/run_guerilla.py`

Primary role:
- continue generating evidence layers
- become the first producer of `acceptedMatchState`

Should own:
- visible ball evidence
- player-conditioned hidden-ball inference
- mode detection:
  - possession
  - loose
  - aerial
  - restart/out
- provenance/confidence tagging

Should not yet own:
- final report logic
- coach-facing messaging

## `backend/app/processor.py`

Primary role:
- persist and normalize the new artifact
- keep compatibility with existing saved matches

Should own:
- artifact persistence
- artifact normalization
- compatibility bridges

## `backend/app/analytics.py`

Primary role:
- stop depending exclusively on ball point proximity
- consume `acceptedMatchState`

Should evolve:
- possession assignment becomes state-aware
- event extraction becomes state-constrained
- hidden-ball windows become valid if state continuity is strong

## `backend/app/run_benchmarks.py`

Primary role:
- become the truth-quality dashboard for the pipeline

Should own:
- multi-gate trust scoring
- state-quality evaluation
- visible vs hidden-ball evaluation
- player-truth quality signals

## `backend/app/schemas.py`

Primary role:
- formalize the new state objects for API/artifact use

Likely additions:
- `MatchStateFrame`
- `BallEstimate`
- `StateConfidence`
- `StateMode`

## `backend/app/main.py`

Primary role:
- expose any new state artifacts needed by frontend or benchmark tooling

## Frontend

### `frontend/src/components/TacticalPitch.tsx`
Should remain mostly stable in the near term.

Possible later additions:
- visibility styling
- possession-state overlays
- hidden-ball / inferred-ball visual language

But frontend changes are not the first milestone.

---

## 7. Recommended Delivery Order

This is the most important sequencing section in the document.

## Phase 1 — Add state without breaking current contracts

Ship:
- `acceptedMatchState`
- new persisted artifact
- new internal state schema

Do not yet:
- replace existing analytics
- rewrite frontend

Success condition:
- new state artifact exists and is inspectable on saved matches

## Phase 2 — Make possession and event logic state-aware

Ship:
- state-aware possession continuity
- state-aware hidden-ball handling
- event constraints from state

Success condition:
- controlled possession rises without reintroducing massive edge-heavy false signal

## Phase 3 — Split truth gates into sub-gates

Ship:
- visible-ball quality gate
- occluded-possession continuity gate
- restart/out gate
- player-truth gate
- event-consistency gate

Success condition:
- proof output becomes more diagnostic and less misleading than a single failure reason stack

## Phase 4 — Improve metres + calibration smoothing

Ship:
- internal metres pipeline for kinematics
- smoothed calibration path
- smoothed speed/acceleration outputs

Success condition:
- physical outputs become more believable and less jittery

## Phase 5 — Player truth + off-ball product layer

Ship:
- better torso/team features
- track confidence improvements
- run-type vocabulary
- more coach-useful off-ball summaries

Success condition:
- product value improves even on clips where visible ball is still imperfect

---

## 8. What Not To Do Next

These are anti-goals for the next batch.

Do not:

- open 10-minute or 45-minute proofs before the 5-minute trust path improves
- rewrite the whole detector stack first
- break the normalized frontend contract early
- overclaim Catapult-equivalent metrics
- spend the next sprint on UI polish
- treat team selection as the main remaining explanation
- replace the current truth layers before a new state layer exists

---

## 9. Immediate Next Sprint Recommendation

If only one enhancement sprint is chosen next, it should be:

## “Accepted Match State v1”

### Sprint goal
Add a new match-state artifact above `acceptedBall` and make possession logic consume it in the simplest useful way.

### Minimum implementation target

1. Produce `acceptedMatchState` in `run_guerilla.py`
2. Persist it in `processor.py`
3. Add schemas
4. Update `run_benchmarks.py` with at least:
   - visible-ball quality
   - hidden-ball continuity
   - restart/out coverage
5. Update analytics to use state continuity in possession assignment

### Minimum success bar

Compared with the current strongest clean lane, the next proof should improve at least one of:

- controlled possession continuity
- event consistency
- trust diagnosis quality
- accepted football-state coverage without inflating edge-heavy false positives

---

## 10. One-Sentence Summary

The next major improvement to this project should be to evolve from a **ball-first truth pipeline** into a **football-state-first truth pipeline**, using the existing ball layers as evidence rather than as the sole source of reality.
