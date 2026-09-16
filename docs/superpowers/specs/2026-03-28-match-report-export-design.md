# Match Report Export Design

**Goal:** add a print-friendly HTML export for a processed match so coaches can open, print, and save a report built from persisted analytics and stored tactical insights.

## Why This Slice

The product now has a meaningful review backbone: persisted match state, tactical metrics, event intelligence, player profiles, coach-facing reports, and synced video playback. What it still lacks is a durable coach output artifact. Right now the `report` and `drills` tabs are useful in-session, but they are not exportable or reproducible outside the live UI.

This slice adds the first export path without widening into PDF generation, clip export, or multi-match reporting. The objective is to make one match exportable as a clean, print-friendly HTML document while keeping the later PDF path obvious.

## Scope

### In Scope

- Persist the latest `tactical_report` and `drills` outputs per match on the backend
- Add a backend HTML export route for one match
- Build a deterministic HTML report from:
  - persisted match identity and timestamps
  - match summary analytics
  - formation timeline
  - shot/xG summary
  - defensive-line and pressing metrics
  - detected events snapshot
  - stored tactical report content when available
  - stored drill recommendations when available
- Add a frontend export action that opens the HTML report in a new tab
- Make the HTML print-friendly with clear layout, typography, spacing, and section hierarchy

### Out of Scope

- PDF generation
- Clip export
- Multi-match or season exports
- Custom branding/themes
- Editable annotations in the export
- Requiring LLM generation before export

## Recommended Approach

Use a backend-owned export route that renders HTML from stored match artifacts.

This is the best fit for the current architecture because the backend is already the source of truth for persisted match analytics and LLM-backed coach outputs. It also avoids making export quality depend on the current browser state or whichever tab the user last visited.

The export should be generated on request, not precomputed during processing. That keeps the slice simpler and ensures the document can reflect the latest regenerated report/drills content without inventing another artifact lifecycle.

## User Flow

1. The user loads a processed match in the app.
2. The user optionally generates `tactical_report` and/or `drills`.
3. The user clicks `Export HTML Report`.
4. The frontend opens the backend export URL in a new browser tab.
5. The backend returns a print-friendly HTML document for that match.
6. The user can review, print, or save the page from the browser.

If no tactical report or drills have been generated yet, the export still works. The document should show analytics-driven sections normally and clearly mark report/drill sections as not yet generated.

## Architecture

### Backend Responsibilities

The backend remains the canonical export owner.

It should:

- persist the most recent analysis payloads for `tactical_report` and `drills`
- expose a route such as `GET /api/matches/{match_id}/report/html`
- load match detail, analytics, events, and stored analyses
- assemble a compact export view model
- render that model into a complete HTML document

The route should return `text/html` directly. No frontend HTML composition is needed for this slice.

### Frontend Responsibilities

The frontend only triggers export.

It should:

- add an `Export HTML Report` button in the coach/report experience
- build the canonical backend export URL from the active match id
- open that URL in a new tab or window

The frontend should not rebuild the report body from local state. It can trust the backend export route as the single document source.

## Persistence Changes

The app currently generates `tactical_report` and `drills` on demand but treats them as transient UI responses. This slice changes that.

For each match, persist the latest analysis result keyed by analysis type:

- `tactical_report`
- `drills`

This can live alongside the existing filesystem-backed match artifacts and does not require a separate database table if the current storage layer already persists JSON artifacts per match cleanly.

Expected behavior:

- generating a new report overwrites the previous stored report artifact for that match
- generating new drills overwrites the previous stored drill artifact for that match
- export reads the latest stored artifacts if they exist

## Export Document Structure

The HTML report should be intentionally plain and print-friendly, not app-like.

Recommended sections:

1. Header
- product name
- match name
- input mode
- export generation timestamp

2. Executive Summary
- tactical report summary if available
- fallback analytics summary sentence if no report exists

3. Tactical Analysis
- attacking
- defensive
- pressing
- weaknesses
- overall rating
- key player

If no tactical report exists, show a compact note that the coach report has not been generated yet.

4. Match Analytics Snapshot
- possession
- xG for both teams
- defensive-line height and team length
- PPDA
- high-press regains
- counterpress recovery time
- current/primary formation

5. Formation Phases
- recent rolling-window formation segments
- keep this compact, for example the latest 3 to 5 segments

6. Player Focus
- top creator
- top finisher
- top ball winner
- other key players when present

7. Event Snapshot
- event counts
- top involvements

8. Training Drills
- focus area
- drill cards with objective, setup, duration

If drills have not been generated yet, show a clear note instead of leaving the section blank.

9. Evidence
- bullet-style supporting lines from the tactical report and/or drills when present

## Data Rules

The export should be resilient to partial match state.

Rules:

- If analytics exist but no stored report exists, render analytics sections and fallback text for missing coach sections.
- If a stored tactical report exists but drills do not, render the tactical report sections and show a “drills not generated yet” note.
- If a field is missing inside a stored payload, omit that item rather than crashing the whole export.
- If the match does not exist, return `404`.
- If analytics are not ready, return a clear backend error rather than rendering a broken document.

## HTML Rendering Direction

The export should be printable on standard desktop browsers without extra client scripts.

Rendering guidance:

- inline or embedded CSS is acceptable for this slice
- use strong section hierarchy and readable spacing
- use a white page with dark text for print clarity
- keep cards/tables minimal and professional
- include print styles so the document keeps structure when printed
- avoid JS-heavy behavior

The document should look like a polished coaching handout, not a screenshot of the app.

## Interfaces

### Backend

Add:

- `GET /api/matches/{match_id}/report/html`

Behavior:

- response content type: `text/html`
- success: complete HTML document
- `404` if match does not exist
- `409` or `404` if match analytics are not ready, following the existing API style

### Frontend

Add a small helper for the export URL and wire a button in the coach insights surface.

No new frontend data-fetch contract is required beyond opening the route.

## Testing

### Backend Tests

- exporting a ready match returns `200` and `text/html`
- export contains key analytics content from persisted match summary
- export includes stored tactical report content when present
- export includes stored drills when present
- export falls back cleanly when stored coach outputs are missing
- export returns `404` for unknown matches

### Frontend Tests

- export button renders in the coach insights flow
- clicking export opens the canonical report URL for the active match
- button remains available whether or not a tactical report is already in memory, because export is backend-owned

## Success Criteria

This slice is successful when:

- a processed match can be exported as a print-friendly HTML document;
- the export is generated from backend-persisted match state rather than transient frontend memory;
- the document remains useful even before coach report/drill generation;
- the frontend only needs a lightweight trigger button to launch export.

## Follow-On Path

This design keeps the PDF upgrade simple later.

Once the HTML export exists and is stable, the next step can be:

- render the same export HTML to PDF server-side or through a print pipeline

Because the export view model and document structure will already exist, PDF becomes a rendering extension instead of a redesign.
