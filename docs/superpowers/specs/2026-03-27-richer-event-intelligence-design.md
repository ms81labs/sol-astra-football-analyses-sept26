# Richer Event Intelligence Design

## Goal

Add a narrow first expansion to the derived event engine by detecting `through_ball` and `interception` on top of the existing event types, without redesigning the broader event taxonomy.

## Scope

In scope:

- backend detection for `through_ball`
- backend detection for `interception`
- persistence and API support through the existing event payload
- frontend visibility for the new event types in timeline/report flows
- regression tests for the heuristics and event mapping

Out of scope:

- `clearance`
- `forced_recovery`
- wholesale event taxonomy redesign
- player-profile scoring changes beyond preserving the new events
- UI redesign for events

## Why This Slice

The current event layer already supports possession transitions, passes, crosses, shots, tackles, recoveries, and turnovers. The highest-value next additions are the ones that strengthen tactical interpretation without requiring new models:

- `through_ball` improves attacking-pattern analysis
- `interception` separates “won the ball in the lane” from “won the ball in a duel”

This gives better raw material for later player-profile, opponent-analysis, and LLM-report work, while keeping the heuristics understandable and testable.

## Current Constraints

- The event engine lives in [backend/app/analytics.py](/root/WorkSpace/fotball-analyst/backend/app/analytics.py).
- Events are derived from ownership segments plus frame-local positions.
- The frontend treats backend events as canonical and preserves visible types through [frontend/src/utils/api.ts](/root/WorkSpace/fotball-analyst/frontend/src/utils/api.ts).
- The timeline and downstream analytics can already tolerate new event types as long as the payload shape stays stable.

## Design

### 1. `through_ball`

`through_ball` remains a subtype-like derived event emitted in addition to the existing `pass` event.

Detection rule:

- only evaluate on successful same-team possession changes that already produce a `pass`
- require a strong forward progression:
  - `my_team`: receiver `x - passer x >= 12`
  - `enemy`: passer `x - receiver x >= 12`
- require the receiver to end in advanced space:
  - `my_team`: receiver `x >= 70`
  - `enemy`: receiver `x <= 30`
- require lane-breaking behavior:
  - count opponents whose `x` lies between passer and receiver
  - emit `through_ball` only if at least one opponent line is broken

This makes the heuristic intentionally narrow. Not every progressive pass is a through ball.

### 2. `interception`

`interception` is emitted on top of `turnover` when the win looks like a passing-lane read rather than a tackle.

Detection rule:

- only evaluate on team-to-team possession flips that already produce a `turnover`
- do not emit if the same possession change already qualifies for `tackle`
- compare the previous ball-holder position and the winner position
- require a moderate collection distance rather than direct-contact duel:
  - winner-to-loser distance must be `> 6` and `<= 18`
- require the winner to sit plausibly in the ball path:
  - the ball or winner position must be close to the path between the last same-team passer and target area when available
  - fallback: use turnover distance band only when no pass-path evidence exists

This keeps `interception` conservative and avoids relabeling obvious tackles.

## Data Contract

No new API endpoint is required.

The existing `DetectedEvent` payload remains unchanged:

- `type`
- `frameId`
- `timestamp`
- `team`
- `fromTrackId`
- `toTrackId`
- `description`

The only change is that `type` can now include:

- `through_ball`
- `interception`

Frontend type unions and visible event mapping must be updated accordingly.

## Backend Changes

Files expected to change:

- [backend/app/analytics.py](/root/WorkSpace/fotball-analyst/backend/app/analytics.py)
- [backend/app/schemas.py](/root/WorkSpace/fotball-analyst/backend/app/schemas.py) only if event-type docs/comments need refresh
- [backend/tests/test_analytics.py](/root/WorkSpace/fotball-analyst/backend/tests/test_analytics.py)

Implementation notes:

- keep the new heuristics near existing `pass` / `turnover` / `tackle` detection logic
- avoid adding a second event pass unless it clearly improves readability
- prefer helper functions for:
  - forward progression
  - broken-line count
  - interception-vs-tackle classification

## Frontend Changes

Files expected to change:

- [frontend/src/types/index.ts](/root/WorkSpace/fotball-analyst/frontend/src/types/index.ts)
- [frontend/src/utils/api.ts](/root/WorkSpace/fotball-analyst/frontend/src/utils/api.ts)
- [frontend/src/utils/api.test.ts](/root/WorkSpace/fotball-analyst/frontend/src/utils/api.test.ts)

Optional display-only follow-up if needed:

- [frontend/src/components/Timeline.tsx](/root/WorkSpace/fotball-analyst/frontend/src/components/Timeline.tsx)

The first pass should only ensure the new events remain visible and do not collapse to `custom`.

## Error Handling

- if no positions are available, do not emit the richer subtype
- if the path-breaking evidence is ambiguous, prefer the simpler base event (`pass` or `turnover`)
- event derivation must remain deterministic and safe on sparse frame data

## Testing

### Backend

Add focused heuristic tests for:

- progressive lane-breaking pass emits `pass` + `through_ball`
- ordinary forward pass emits `pass` only
- turnover at distance emits `turnover` + `interception`
- close-contact turnover still emits `turnover` + `tackle`, not `interception`

### Frontend

Add/extend mapping tests for:

- `through_ball` remains visible in mapped event tags
- `interception` remains visible in mapped event tags

## Trade-Offs

### Recommended approach: narrow heuristic extension

Pros:

- fast to ship
- easy to test
- minimal payload churn
- strengthens the existing analytics stack immediately

Cons:

- conservative heuristics will miss some real football nuance
- `through_ball` and `interception` remain approximations, not model-backed truths

### Rejected approach: add `clearance` in the same slice

Reason:

- it expands scope without improving the core attacking/defensive interpretation as much
- clearance heuristics get noisy quickly without stronger defensive context

### Rejected approach: redesign event taxonomy first

Reason:

- too much scope for too little immediate product value
- risks blocking the roadmap on structure instead of shipped capability

## Acceptance Criteria

- backend emits `through_ball` for a narrow, line-breaking advanced pass
- backend emits `interception` for a non-tackle turnover that looks like a passing-lane win
- existing `pass`, `turnover`, and `tackle` behavior is preserved by tests
- frontend keeps the new events visible instead of flattening them to `custom`
- full backend/frontend verification remains green
