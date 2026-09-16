# Player Profiles V2 Design

**Goal:** upgrade the existing player-profile layer from a simple ranked contribution list into a coach-readable tactical summary built from the richer derived event stream.

**Status:** approved design, ready for implementation planning after user review.

## Why This Slice Next

The repo already has a working profile seam in the frontend through `buildPlayerProfiles(...)`, and the event layer now includes `pass`, `cross`, `shot`, `tackle`, `recovery`, `turnover`, `through_ball`, and `interception`. That makes player-profile enrichment the cleanest next step: we can turn those events into clearer player-level outputs without changing the API surface or adding a new subsystem.

This slice is intentionally narrower than a full player-detail experience. It improves the tactical value of the existing workspace while preserving the current backend/frontend contract and leaving interactive drilldowns for a later coach-workflow phase.

## Scope

### In Scope

- Extend the existing frontend-derived player profile model with richer tactical metrics.
- Use the current backend event stream plus backend shot analytics as the source material.
- Add coach-readable summary labels for each player.
- Upgrade the existing Stats panel player-profile area to surface the stronger metrics.
- Keep the implementation additive to the current match workspace flow.

### Out Of Scope

- New API endpoints for player profiles.
- Click-to-open player detail drawers or pitch interactions.
- Persisted annotations tied to individual players.
- OCR-based jersey identity or roster names.
- Rebuilding the profile layer in the backend.

## Recommended Approach

Keep player-profile derivation in the frontend for this slice and deepen the existing `buildPlayerProfiles(...)` path rather than moving ownership to the backend.

This is the right tradeoff for now because:

- the repo already derives profiles on the frontend;
- the richer event stream is already available there;
- the UI surface already exists in `StatsPanel`;
- we get faster delivery without widening the API contract.

If the product later needs exported reports, multi-match aggregation, or stronger backend authority, we can migrate the same profile logic into the backend analytics payload in a later phase.

## Architecture

### Current Shape

- Backend provides frames, derived events, shot analytics, and match summary.
- Frontend maps the workspace into app state.
- `buildPlayerProfiles(...)` combines movement metrics with a simple contribution score.
- `StatsPanel` renders the top profiles as compact cards.

### Proposed Shape

- Keep backend unchanged for this slice.
- Extend frontend analytics derivation in `frontend/src/utils/analytics.ts`.
- Pass `shotAnalytics` into profile derivation so profiles can include shot-quality context.
- Extend the `PlayerContribution` / `PlayerProfile` types in `frontend/src/types/index.ts`.
- Render richer player-profile cards and top-category summaries in `frontend/src/components/StatsPanel.tsx`.

## Data Model Changes

### `PlayerContribution`

Add:

- `throughBalls: number`
- `interceptions: number`
- `ballWins: number`
- `involvements: number`
- `xgCreated: number`
- `xgTaken: number`

Definitions:

- `throughBalls`: count of `through_ball` events created by the player.
- `interceptions`: count of `interception` events won by the player.
- `ballWins`: `tacklesWon + recoveries + interceptions`.
- `involvements`: total meaningful on-ball/defensive contributions used for quick ranking context.
- `xgTaken`: sum of shot xG values for shots taken by the player.
- `xgCreated`: sum of shot xG values the player creates via a recent assist-style action.

### `PlayerProfile`

Add:

- `profileLabel: string`
- `summaryLine: string`

Definitions:

- `profileLabel`: short role-style label such as `Primary Creator`, `Ball Winner`, `Shot Threat`, or `Box Threat`.
- `summaryLine`: one concise sentence fragment summarizing why the player matters in the current match sample.

## Derivation Rules

### Event Attribution

The existing event attribution rules remain intact:

- `pass`, `cross`, `shot`, and `through_ball` credit the acting player from `fromTrackId`.
- `tackle`, `recovery`, and `interception` credit the winning player from `toTrackId`.

### New Contribution Fields

- `throughBalls` increments on `through_ball`.
- `interceptions` increments on `interception`.
- `ballWins` is derived, not stored independently during event iteration.
- `involvements` is derived from the sum of positive actions:
  - `passes`
  - `crosses`
  - `throughBalls`
  - `shots`
  - `tacklesWon`
  - `recoveries`
  - `interceptions`

### `xgTaken`

`xgTaken` comes from shot analytics, not from raw events. For each `ShotMarker`, add its `xg` to the matching player/team profile.

### `xgCreated`

`xgCreated` is a narrow assist-style heuristic:

- only consider same-team `pass`, `cross`, and `through_ball` events;
- look forward for the next same-team `shot` event within a short frame window;
- if found, attribute that shot’s `xg` to the passer/creator;
- prefer the first eligible shot after the action;
- keep the window conservative so normal build-up does not inflate creation numbers.

This should remain intentionally narrow. The goal is not a full possession-chain model yet; it is a trustworthy “created danger” signal for the current prototype.

### Impact Score V2

The current impact score should be reweighted to reflect the new event types and shot quality:

- `pass`: low value
- `cross`: moderate value
- `through_ball`: higher value than a normal pass
- `shot`: meaningful base value
- `xgTaken`: additive quality bonus
- `tacklesWon`, `recoveries`, `interceptions`: meaningful defensive value

The score should stay simple and deterministic. It is a ranking aid, not a model.

### Role Labels

Assign one primary label per player based on their strongest signal:

- `Primary Creator` for high `xgCreated` or multiple `throughBalls`
- `Shot Threat` for high `shots` or `xgTaken`
- `Ball Winner` for high `ballWins`
- `Wide Threat` for high `crosses`
- `Connector` for pass-heavy involvement without standout end-product
- fallback: `Support Option`

### Summary Line

Each player gets a compact human-readable line built from the top 1-2 strongest signals, for example:

- `2 through balls, 0.41 xG created`
- `3 ball wins and 2 recoveries high up`
- `2 shots, 0.56 xG taken`

The line should be deterministic and concise enough to fit inside the existing card layout.

## UI Changes

### Player Profile Cards

The current profile cards in `StatsPanel` should be upgraded, not replaced.

Each card should show:

- player id and team pill
- impact score
- role label
- key action totals
- xG created / xG taken where relevant
- movement line with distance and top speed
- short summary line

### Category Highlights

Above or alongside the profile list, add compact “top of match” highlights derived from the same profile array:

- Top Creator
- Top Finisher
- Top Ball Winner

These should remain compact summary chips or mini-cards, not a new dashboard section.

### Empty States

If the event sample is too thin, preserve the current empty-state behavior and avoid inventing labels or summaries from weak data.

## Error Handling And Edge Cases

- If shot analytics are missing, `xgTaken` and `xgCreated` default to `0`.
- If a player has movement data but no event contribution, they should not surface as a profile unless their score remains above the threshold.
- If two players tie on ranking, use deterministic sorting:
  - impact score
  - `xgTaken + xgCreated`
  - total distance
  - player id
- If a shot exists without a resolvable acting player, ignore it for player-profile attribution.
- If the creator window finds no valid shot, `xgCreated` remains unchanged.

## Testing Strategy

### Frontend Analytics Tests

Add test coverage for:

- `through_ball` and `interception` contribution counting
- `ballWins` and `involvements` derivation
- `xgTaken` accumulation from shot markers
- `xgCreated` attribution from assist-style precursor events
- role-label assignment for creator / finisher / ball-winner cases
- deterministic ranking and summary-line output

### Frontend Rendering Tests

Add or extend component tests to verify:

- richer profile fields render in `StatsPanel`
- highlight cards show top creator / finisher / ball winner
- empty-state behavior still works

## Implementation Notes

- Keep the slice frontend-only for now.
- Reuse the existing `shotMarkers` / `shotSummary` flow instead of duplicating shot parsing.
- Prefer extending `buildPlayerProfiles(...)` with an additional `shotMarkers` input rather than adding a parallel builder.
- Keep helper functions small and colocated in `frontend/src/utils/analytics.ts` unless the file becomes materially harder to reason about.

## Success Criteria

This slice is successful when:

- player profiles include richer event intelligence and shot-quality context;
- the UI shows clearer coach-readable player summaries;
- the derivation is fully covered by frontend tests;
- no backend contract changes are required;
- existing analytics, build, and lint checks continue to pass.
