# Player-Biased Seed Context Geometry Sprint

## Summary

Keep the roadmap on the detector lane and target the next direct-seed seam: `direct_seed_context` now activates on many seeded frames, but its crop geometry still loses where `player_ranked` windows hit.

Grounded state from the latest fresh pod proof:
- promoted result is still stuck at:
  - `acceptedBallFrames=101`
  - `controlledPossessionFrames=98`
  - `ballTrackEdgeFrameShare=0.812`
  - `ballTrackViable=false`
- best proposal profile is still `proposal_windows_075`
- proposal activation is no longer the bottleneck:
  - `proposalDirectSeedContextWindowFrames=90`
  - `proposalDirectSeedContextEligibleFrames=90`
  - `proposalDirectSeedContextMeanSeedToBoxDistance=71.74`
- but the direct-seed hit rate is still dead:
  - `bestProposalDirectSeedDetectedFrames=0`
  - `bestProposalDirectSeedContextDetectedFrames=0`
  - `bestProposalPlayerRankedDetectedFrames=9`

Chosen bias: `Balanced`. Improve direct-seed context hit rate by changing crop geometry, not detector passes, ranking policy, truth gates, or clip length.

## Key Changes

### 1. Replace union-centered context geometry with player-biased expansion
In `backend/run_guerilla.py`, replace the current direct-seed context crop construction that uses the union of:
- the true seed point
- the chosen player source box

with a new helper that starts from the normal player-ranked crop window and only expands toward the seed as needed.

Target behavior:
- build the base player crop from the chosen player source box using the existing proposal crop builder
- if the true seed already lies inside that crop, keep the base crop geometry
- otherwise, asymmetrically expand only the edges needed to include the seed
- preserve the current width/height caps and frame clamping rules
- keep the crop centered closer to the player box than the current midpoint-style union crop

This should preserve the player context that already yields proposal hits while still honoring the observed-anchor seed.

### 2. Keep activation, ranking, and truth semantics unchanged
Do not change:
- `direct_seed_context` eligibility
- proposal pre-collapse ranking
- `observedBall`, `inferredBall`, or `acceptedBall` semantics
- `acceptedMatchState v1`
- explicit selected-cluster promotion
- detector family
- clip length
- truth-gate thresholds

The only intended behavior change is the shape/placement of `direct_seed_context` windows.

### 3. Add geometry diagnostics
Extend `recovery_profile_matrix.json`, selected-profile recovery debug, and compact proof summaries with additive geometry fields:

Per proposal profile:
- `proposalDirectSeedContextExpandedFrames`
- `proposalDirectSeedContextMeanExpansionPx`

Compact best-proposal summary:
- `bestProposalDirectSeedContextExpandedFrames`
- `bestProposalDirectSeedContextMeanExpansionPx`

Counting rules:
- `ExpandedFrames` counts context windows whose final crop differs from the unexpanded player-ranked base crop
- `MeanExpansionPx` is the average total one-dimensional expansion applied across the changed edges for expanded context windows only

### 4. Validate on the pod-first lane
Run this exact loop:
1. one fresh 5-minute pod proof with storage rooted at `/workspace/fotball-analyst/backend/storage`
2. one explicit selected-cluster promotion on the fresh match
3. pull back:
   - proof summary
   - selected-cluster delta
   - `recovery_profile_matrix.json`
4. update roadmap and handoff immediately

Skip serverless unless the pod result clearly clears the success bar.

## Test Plan

Add focused coverage for:
- direct-seed context crop expands toward the seed when the seed lies outside the base player-ranked crop
- direct-seed context crop does not expand when the seed already lies inside the base crop
- expansion is asymmetric and remains player-biased rather than recentering to the midpoint union
- frame clamping and existing width/height caps still hold
- per-frame proposal cap remains `3`
- duplicate context/player-ranked windows are still deduped before recovery
- geometry diagnostics persist correctly in `recovery_profile_matrix.json`
- compact proof summaries expose the new best-proposal geometry fields without breaking selected-cluster output
- pod proof + selected-cluster promotion still run end to end on the 5-minute clip

## Success Bar

Mechanism success:
- `bestProposalDirectSeedContextDetectedFrames > 0`

Count the sprint as a product win if, after selected-cluster promotion, any of these happen:
- winning recovery profile becomes a proposal profile and `bestProposalSelectedFrames >= 15`
- `acceptedBallFrames >= 110` without increasing `ballTrackEdgeFrameShare`
- `controlledPossessionFrames >= 105`
- `ballTrackViable == true`

Record exactly one binary outcome:
- `player-biased seed context geometry materially improved truthful coverage`
- `player-biased seed context geometry did not materially improve the 5-minute truth gates`

## Assumptions

- keep the pod as the primary heavy-proof lane
- keep `acceptedMatchState v1` in place, but do not expand it in this batch
- keep the current 5-minute clip and explicit selected-cluster promotion flow
- do not add detector sweeps or a wider proposal geometry ladder in this batch
- treat the main remaining problem as direct-seed context crop placement, not runtime, team selection, or threshold strictness

## Outcome

This sprint is now closed from a fresh valid pod proof.

Fresh pod proof:
- pod id `37n9f2lf2uq390`
- proof match `81f9bcda1cf74379b3417499f50501da`
- proof job `6b93b29dba014defbcc3740c291cd20f`
- selected cluster `1`

Verification:
- focused backend suite: `145 passed`
- Ruff on touched files: clean

Pulled-back artifacts:
- `backend/storage/pod_artifacts/player-biased-seed-context-geometry-pod-local-proof.json`
- `backend/storage/pod_artifacts/player-biased-seed-context-geometry-pod-selected-cluster-delta.json`
- `backend/storage/pod_artifacts/player-biased-seed-context-geometry-recovery-profile-matrix.json`

Mechanism result:
- `bestProposalDirectSeedContextWindowFrames=90`
- `bestProposalDirectSeedContextEligibleFrames=90`
- `bestProposalDirectSeedContextExpandedFrames=80`
- `bestProposalDirectSeedContextMeanExpansionPx=57.71`
- `bestProposalDirectSeedDetectedFrames=0`
- `bestProposalDirectSeedContextDetectedFrames=0`
- `bestProposalPlayerRankedDetectedFrames=9`

Product result after explicit selected-cluster promotion:
- `acceptedBallFrames=101`
- `controlledPossessionFrames=98`
- `eventFamilyCount=5`
- `ballTrackEdgeFrameShare=0.812`
- `ballTrackViable=false`

Binary outcome:
- `player-biased seed context geometry did not materially improve the 5-minute truth gates`

Interpretation:
- the geometry change is live and measurable
- direct-seed context windows are now expanding on the clip, but they still do not produce detections
- all surviving proposal hits still come from `player_ranked`
- the winning recovery profile stayed `width_cap_075`
