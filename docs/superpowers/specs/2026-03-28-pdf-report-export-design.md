# PDF Report Export Design

**Goal:** add a true backend-owned PDF export for a processed match by rendering the existing HTML report source into a downloadable PDF artifact.

## Why This Slice

The product now has a backend-owned HTML report export built from persisted analytics and stored coach outputs. That gives the system a single report source of truth, but coaches still need a portable artifact they can send, archive, and print without relying on browser print steps.

This slice adds a server-generated PDF download while preserving the current HTML report as the canonical report source. The PDF path should extend the report system, not fork it.

## Scope

### In Scope

- Add a backend PDF export route for one match
- Reuse the existing backend HTML report as the PDF source
- Return a downloadable `application/pdf` response
- Add a frontend `Export PDF Report` action alongside the HTML export action
- Keep fallback behavior consistent with HTML export when stored coach outputs are missing

### Out of Scope

- Redesigning the report layout specifically for PDF
- Multi-match PDF exports
- Background PDF generation during processing
- Cover pages, branding systems, or custom themes
- PDF annotations or embedded clips

## Recommended Approach

Render the existing export HTML to PDF on the backend.

This is the best fit because:

- HTML export already exists and is backend-owned
- one report structure stays canonical across HTML and PDF
- the PDF route can share the same persisted analytics and coach-output loading path
- later layout improvements automatically benefit both formats unless explicitly diverged

The PDF route should generate the PDF on request, not precompute it during processing. That keeps the slice small and ensures the latest stored `tactical_report` and `drills` content is reflected in the download.

## User Flow

1. The user opens a processed match.
2. The user optionally generates `tactical_report` and/or `drills`.
3. The user clicks `Export PDF Report`.
4. The frontend opens the backend PDF route.
5. The backend builds the current report HTML, converts it to PDF, and returns it as a downloadable response.
6. The user saves or opens the PDF.

If no report or drills were generated yet, the PDF should still succeed and contain the same fallback sections the HTML export already shows.

## Architecture

### Backend Responsibilities

The backend should remain the only PDF generator.

It should:

- load the same persisted match state used by the HTML report route
- reuse the existing report-export builder to produce the HTML document
- convert the HTML document to PDF through one rendering adapter
- return the PDF bytes with the correct content type and filename

The backend should not create a second, separate report view model for PDF.

### Frontend Responsibilities

The frontend should only trigger export.

It should:

- add an `Export PDF Report` button next to the existing HTML export button
- build the canonical PDF route from the active match id
- open the backend route in a new tab or downloadable browser request

The frontend should not attempt client-side PDF generation.

## Rendering Strategy

The PDF should be produced from the same HTML document structure already used for HTML export.

Expected rendering pipeline:

1. build the report HTML using the existing export builder
2. send that HTML to one server-side PDF renderer
3. return the resulting PDF bytes

The renderer choice should be pragmatic and deterministic. The implementation should prefer a tool that can reliably turn modern HTML/CSS into a PDF in the current local-first backend environment.

The important constraint is architectural, not library-specific:

- HTML remains the report source of truth
- PDF is derived from that HTML at request time

## Route Contract

Add:

- `GET /api/matches/{match_id}/report/pdf`

Behavior:

- success returns `application/pdf`
- response should include a useful filename such as `<match-name>-report.pdf`
- `404` if match does not exist
- error when analytics are not ready should follow the existing API style used by export and analytics routes

## Data Rules

The PDF should use the same fallback rules as HTML export:

- if analytics exist but no stored report exists, generate a valid analytics-first PDF
- if drills do not exist, the drills section should show the same fallback note
- if stored payloads are partial, omit missing fields rather than failing the document

There should be no PDF-only content logic for this slice.

## UI Direction

The report area should now expose two export actions:

- `Export HTML Report`
- `Export PDF Report`

The PDF button should sit with the existing export controls and feel like the same family of actions.

The user should not need to generate the LLM report first to export the PDF.

## Testing

### Backend Tests

- PDF export route returns `200`
- response content type starts with `application/pdf`
- response body begins with PDF bytes signature such as `%PDF`
- stored tactical report and drills can be reflected in the rendered PDF path
- missing stored coach outputs still produce a valid PDF
- unknown match returns `404`

### Frontend Tests

- the coach insights surface renders an `Export PDF Report` button
- clicking the button opens the canonical PDF export URL
- HTML and PDF export buttons can coexist without breaking existing report/drill actions

## Success Criteria

This slice is successful when:

- one processed match can be downloaded as a backend-generated PDF;
- the PDF is produced from the same canonical HTML report source as the HTML export;
- fallback export behavior remains intact even without generated coach outputs;
- the frontend remains a lightweight trigger surface rather than a document renderer.

## Follow-On Path

Once this slice is stable, later improvements can stay incremental:

- refine print/PDF CSS for better pagination
- add saved artifact caching if generation time becomes an issue
- add branded cover pages or club templates if that becomes a real product need

Those are extensions to the same report system, not a reason to split it.
