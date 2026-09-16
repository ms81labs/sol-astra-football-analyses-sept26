# LLM Report Context Upgrade Design

**Goal:** upgrade the `tactical_report` and `drills` analysis flow so the backend prompt context and frontend rendering use the richer derived event and player-profile intelligence already present in the product.

**Status:** approved design, ready for implementation planning after user review.

## Why This Slice Next

The project now has a stronger tactical backbone than the current report/drill pipeline is using. The backend already has match summary, event summary, formation segments, xG, defensive-line data, pressing analytics, and richer player-profile signals available across the app, but the LLM layer still relies on a relatively thin derived context.

This slice improves the quality of coach-facing outputs without changing the overall UX pattern. It keeps the current analysis endpoints and tabs in place while making the report and drill suggestions materially more grounded in football-specific evidence.

## Scope

### In Scope

- Upgrade backend prompt context for `tactical_report` and `drills`
- Enrich the backend analysis payload with clearer player- and event-level evidence
- Improve frontend rendering of report/drill evidence using the richer payload
- Preserve the current endpoint structure and request flow

### Out Of Scope

- Reworking `offside` analysis
- Reworking `spacing` analysis
- Adding new analysis endpoints
- Replacing the current provider model
- Full cloud-provider implementation
- A generic analysis-context refactor shared by every analysis type

## Recommended Approach

Keep the current report/drill pipeline and make it smarter by enriching the derived match context passed into the backend LLM prompt builder.

This is the right tradeoff because:

- the backend already owns the report/drill prompt assembly;
- the API contract already supports these analysis flows;
- the frontend already has report/drill tabs and evidence rendering patterns;
- the richer tactical data is already available and only needs to be surfaced more clearly.

This keeps the slice focused on improving the outputs users care about most while avoiding a broader redesign of the whole LLM subsystem.

## Architecture

### Current Shape

- Frontend calls `POST /api/matches/{match_id}/analysis/{analysis_type}`
- Backend gathers match frames and derived analytics
- `backend/app/llm.py` builds a prompt from sampled frames, summary, events, and formation timeline
- The response is shown in the `report` and `drills` tabs

### Proposed Shape

- Keep the same API route in `backend/app/main.py`
- Expand `_build_match_context(...)` in `backend/app/llm.py`
- Add richer derived summaries to the context sent to the LLM
- Preserve the current top-level report/drill response shape, but enrich nested evidence sections
- Upgrade frontend rendering in `frontend/src/App.tsx` so the stronger evidence is visible, not just hidden inside JSON

## Backend Context Design

### Existing Context To Keep

- sampled frames
- match summary
- event summary
- recent events
- formation timeline

### New Context To Add

#### Player Focus Summary

Add a compact `playerFocus` block derived from events and shot-quality context. This should identify:

- top creator
- top finisher
- top ball winner
- supporting top-involvement players

Each entry should stay compact and coach-readable. Suggested fields:

- `trackId`
- `team`
- `label`
- `summary`
- `involvements`
- `xgCreated`
- `xgTaken`
- `ballWins`

This should be derived server-side for report/drill prompt quality, even though the frontend also has profile logic for normal UI rendering.

#### Match Signals

Add a `matchSignals` block that lifts the most actionable summary metrics into explicit coaching cues, for example:

- possession balance
- xG balance
- pressing edge
- defensive-line edge
- recent formation shifts

The goal is not to replace the raw summary object, but to give the LLM a more explicit tactical snapshot that is easier to reason over consistently.

#### Event Pattern Summary

Extend the existing event summary with higher-value tactical pattern signals such as:

- through-ball count by team
- shot count and xG concentration by team
- recovery / interception / turnover balance
- pass-volume leaders and shot-volume leaders

This should remain derived and deterministic.

## Response Shape

### Tactical Report

Keep the current top-level fields:

- `attacking`
- `defensive`
- `pressing`
- `key_player`
- `weaknesses`
- `rating`
- `summary`
- `evidence`
- `event_summary`

Add an optional compact `player_focus` section for the frontend:

- `topCreator`
- `topFinisher`
- `topBallWinner`
- `otherKeyPlayers`

This section should use the same compact player summaries the backend generated for prompt context.

### Drills

Keep the current top-level fields:

- `drills`
- `focus_area`
- `evidence`

Add an optional `player_focus` section here too, so suggested drills can point to the players or roles that need attention.

## Prompting Strategy

### Tactical Report Prompt

The prompt should explicitly instruct the model to:

- treat derived analytics as the primary source of truth
- use sampled frames only as supporting context
- cite concrete evidence from player-focus, event-pattern, and match-signal data
- identify one key player from the derived player-focus summary when possible

### Drills Prompt

The prompt should explicitly instruct the model to:

- propose drills from the tactical issues in the derived context
- tie each drill to a concrete weakness or player/role need
- use the richer event and player-focus context instead of generic football advice

## Frontend Rendering Design

### Tactical Report Tab

Keep the current report layout but add clearer evidence sections for:

- key event counts
- player-focus leaders
- evidence lines

The report should continue to show the core narrative fields first, then the supporting evidence.

### Drills Tab

Keep the drill cards, but add supporting context beneath or beside them:

- why this drill was suggested
- which player/role focus it addresses
- which match signals triggered it

This should stay compact and readable, not turn into a debugging dump.

## Error Handling And Compatibility

- If enriched player-focus data cannot be derived, the backend should still return a valid report/drill response without that section.
- If the model omits `player_focus`, the frontend should gracefully hide that block.
- Existing analysis consumers must continue working with the previous response shape.
- `offside` and `spacing` should remain untouched in this slice.

## Testing Strategy

### Backend Tests

Add or extend tests to verify:

- prompt context includes richer player-focus and match-signal data
- tactical report prompt still includes summary/events context
- drill prompt includes the enriched derived context
- analysis endpoint still passes the correct derived analytics into `run_analysis(...)`

### Frontend Tests

Add or extend tests to verify:

- tactical report rendering shows player-focus summaries when present
- drills rendering shows the new supporting evidence blocks
- frontend still renders correctly if `player_focus` is absent

## Implementation Notes

- Keep the slice backend-led, because prompt quality should be owned where prompts are built.
- Reuse existing derived analytics instead of duplicating event/profile calculations in a new place.
- Keep the new backend context compact and deterministic; avoid dumping full raw objects unnecessarily.
- Do not widen this into a general LLM-system redesign.

## Success Criteria

This slice is successful when:

- tactical reports and drill suggestions are visibly grounded in richer event and player context;
- the backend prompt context includes explicit player-focus and match-signal summaries;
- the frontend surfaces the better evidence clearly;
- existing analysis routes and flows remain intact;
- backend and frontend verification continue to pass.
