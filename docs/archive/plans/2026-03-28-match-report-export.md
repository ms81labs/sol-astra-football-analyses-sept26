# Match Report Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** add a backend-owned, print-friendly HTML match report export that persists the latest tactical report and drills per match and lets the frontend open the export in a new tab.

**Architecture:** keep export generation on the backend so the document is built from persisted match artifacts, not transient frontend state. Extend the existing analysis flow to save the latest `tactical_report` and `drills` payloads, add a lightweight HTML renderer and export route, then add one frontend trigger button in the coach insights surface.

**Tech Stack:** FastAPI, Pydantic, SQLite/filesystem storage, React, Vitest, Testing Library, pytest

---

### File Structure

**Backend**
- Modify: `/root/WorkSpace/fotball-analyst/backend/app/storage.py`
  - persist and load analysis artifacts such as `tactical_report` and `drills`
- Modify: `/root/WorkSpace/fotball-analyst/backend/app/main.py`
  - save analysis results after generation and expose the HTML export route
- Create: `/root/WorkSpace/fotball-analyst/backend/app/report_export.py`
  - build the export view model and render deterministic HTML
- Modify: `/root/WorkSpace/fotball-analyst/backend/tests/test_api.py`
  - add API coverage for stored analysis export and fallback behavior
- Create: `/root/WorkSpace/fotball-analyst/backend/tests/test_report_export.py`
  - unit coverage for HTML rendering and fallback sections

**Frontend**
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/utils/api.ts`
  - add export URL helper
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/utils/api.test.ts`
  - cover the export URL helper
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/components/CoachInsights.tsx`
  - add the export trigger in the report/drills UI
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/components/CoachInsights.test.tsx`
  - cover export button behavior
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/App.tsx`
  - pass the active match id into `CoachInsights`

### Task 1: Persist Latest Analysis Artifacts

**Files:**
- Modify: `/root/WorkSpace/fotball-analyst/backend/app/storage.py`
- Modify: `/root/WorkSpace/fotball-analyst/backend/app/main.py`
- Test: `/root/WorkSpace/fotball-analyst/backend/tests/test_api.py`

- [ ] **Step 1: Write the failing persistence/API test**

```python
def test_analysis_route_persists_latest_report_payload(tmp_path: Path, monkeypatch):
    storage_root = tmp_path / "storage"
    app = create_app(storage_root=storage_root, run_jobs_inline=True)
    client = TestClient(app)

    fixture_path = Path(__file__).parent / "fixtures" / "sample_tracking.json"
    with fixture_path.open("rb") as fixture_file:
        response = client.post(
            "/api/matches",
            data={
                "name": "Sample Match",
                "inputMode": "tracking_json",
                "config": json.dumps(
                    {
                        "attackDirection": "right_to_left",
                        "manualHomographyPoints": [
                            {"x": 0.0, "y": 0.0},
                            {"x": 100.0, "y": 0.0},
                            {"x": 100.0, "y": 100.0},
                            {"x": 0.0, "y": 100.0},
                        ],
                    }
                ),
            },
            files={"file": ("sample_tracking.json", fixture_file, "application/json")},
        )

    match_id = response.json()["matchId"]

    monkeypatch.setattr(
        "backend.app.main.run_analysis",
        lambda *args, **kwargs: {
            "summary": "Positive attacking output",
            "rating": 8,
            "attacking": "Strong wide progression",
            "defensive": "Compact block",
            "pressing": "Aggressive counterpress",
            "weaknesses": "Rest defense after turnovers",
            "key_player": 7,
        },
    )

    analysis_response = client.post(
        f"/api/matches/{match_id}/analysis/tactical_report",
        json={"provider": "local", "currentFrameIndex": 1},
    )

    assert analysis_response.status_code == 200

    storage = app.state.storage
    assert storage.load_analysis_artifact(match_id, "tactical_report")["rating"] == 8
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests/test_api.py::test_analysis_route_persists_latest_report_payload -q
```

Expected: FAIL because `load_analysis_artifact` does not exist and the analysis route does not persist the payload.

- [ ] **Step 3: Write the minimal storage and route implementation**

```python
# backend/app/storage.py
def save_analysis_artifact(self, match_id: str, analysis_type: str, payload: dict) -> None:
    self._write_json(self._match_dir(match_id) / f"{analysis_type}.json", payload)


def load_analysis_artifact(self, match_id: str, analysis_type: str) -> dict:
    payload = self._read_json(self._match_dir(match_id) / f"{analysis_type}.json")
    return dict(payload)
```

```python
# backend/app/main.py
app.state.storage = storage

result = run_analysis(...)
if analysis_type in {"tactical_report", "drills"} and isinstance(result, dict):
    storage.save_analysis_artifact(match_id, analysis_type, result)
return result
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests/test_api.py::test_analysis_route_persists_latest_report_payload -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add /root/WorkSpace/fotball-analyst/backend/app/storage.py /root/WorkSpace/fotball-analyst/backend/app/main.py /root/WorkSpace/fotball-analyst/backend/tests/test_api.py
git commit -m "feat: persist generated coach analyses"
```

### Task 2: Build the HTML Report Renderer

**Files:**
- Create: `/root/WorkSpace/fotball-analyst/backend/app/report_export.py`
- Test: `/root/WorkSpace/fotball-analyst/backend/tests/test_report_export.py`

- [ ] **Step 1: Write the failing renderer tests**

```python
def test_render_report_html_includes_core_match_sections():
    html = render_match_report_html(
        match_name="Sample Match",
        input_mode="tracking_json",
        exported_at="2026-03-28T00:00:00+00:00",
        summary={
            "possession": 67,
            "myTeamXg": 1.24,
            "enemyXg": 0.48,
            "formation": "4-3-3",
            "myTeamPpda": 7.1,
            "enemyPpda": 11.3,
            "myTeamDefensiveLineHeight": 24.5,
            "enemyDefensiveLineHeight": 19.8,
            "myTeamHighPressRegains": 4,
            "enemyHighPressRegains": 1,
            "myTeamCounterpressRecoverySeconds": 3.4,
            "enemyCounterpressRecoverySeconds": 5.6,
        },
        formation_timeline=[
            {"formation": "4-3-3", "startTimestamp": 0.0, "endTimestamp": 14.0},
        ],
        event_summary={"eventCounts": {"pass": 18, "shot": 4}},
        tactical_report={"summary": "Positive attacking output", "rating": 8, "attacking": "Strong wide play"},
        drills={"focus_area": "Rest defense", "drills": [{"name": "Wave Press", "objective": "Recover quickly", "setup": "6v4", "duration": "12 min"}]},
    )

    assert "Sample Match" in html
    assert "Positive attacking output" in html
    assert "Wave Press" in html
    assert "4-3-3" in html
    assert "67%" in html
```

```python
def test_render_report_html_shows_fallback_when_no_coach_outputs_exist():
    html = render_match_report_html(
        match_name="Sample Match",
        input_mode="tracking_json",
        exported_at="2026-03-28T00:00:00+00:00",
        summary={"possession": 51, "myTeamXg": 0.8, "enemyXg": 0.7, "formation": "4-4-2"},
        formation_timeline=[],
        event_summary={"eventCounts": {"turnover": 3}},
        tactical_report=None,
        drills=None,
    )

    assert "Coach report not generated yet" in html
    assert "Training drills not generated yet" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests/test_report_export.py -q
```

Expected: FAIL because `report_export.py` and `render_match_report_html` do not exist.

- [ ] **Step 3: Write the minimal renderer**

```python
def render_match_report_html(...):
    return f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <title>Guerilla Analytics Report</title>
        <style>
          body {{ font-family: Arial, sans-serif; color: #0f172a; background: #ffffff; margin: 0; }}
          main {{ max-width: 960px; margin: 0 auto; padding: 32px; }}
          section {{ margin-top: 24px; page-break-inside: avoid; }}
          .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }}
          .card {{ border: 1px solid #cbd5e1; border-radius: 12px; padding: 12px; }}
          @media print {{ main {{ padding: 16px; }} }}
        </style>
      </head>
      <body>
        <main>
          ...
        </main>
      </body>
    </html>
    """
```

Use small helpers inside the same file for:
- escaping text
- formatting percentages/numbers
- rendering fallback notes
- rendering event counts and drill cards

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests/test_report_export.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add /root/WorkSpace/fotball-analyst/backend/app/report_export.py /root/WorkSpace/fotball-analyst/backend/tests/test_report_export.py
git commit -m "feat: add HTML match report renderer"
```

### Task 3: Expose the Export Route

**Files:**
- Modify: `/root/WorkSpace/fotball-analyst/backend/app/main.py`
- Modify: `/root/WorkSpace/fotball-analyst/backend/tests/test_api.py`

- [ ] **Step 1: Write the failing export-route tests**

```python
def test_report_export_route_returns_html_with_stored_report_and_drills(tmp_path: Path, monkeypatch):
    storage_root = tmp_path / "storage"
    app = create_app(storage_root=storage_root, run_jobs_inline=True)
    client = TestClient(app)

    fixture_path = Path(__file__).parent / "fixtures" / "sample_tracking.json"
    with fixture_path.open("rb") as fixture_file:
        response = client.post(
            "/api/matches",
            data={"name": "Sample Match", "inputMode": "tracking_json", "config": json.dumps({"attackDirection": "right_to_left"})},
            files={"file": ("sample_tracking.json", fixture_file, "application/json")},
        )

    match_id = response.json()["matchId"]
    app.state.storage.save_analysis_artifact(match_id, "tactical_report", {"summary": "Positive attacking output", "rating": 8})
    app.state.storage.save_analysis_artifact(
        match_id,
        "drills",
        {"focus_area": "Rest defense", "drills": [{"name": "Wave Press", "objective": "Recover quickly", "setup": "6v4", "duration": "12 min"}]},
    )

    export_response = client.get(f"/api/matches/{match_id}/report/html")

    assert export_response.status_code == 200
    assert export_response.headers["content-type"].startswith("text/html")
    assert "Positive attacking output" in export_response.text
    assert "Wave Press" in export_response.text
```

```python
def test_report_export_route_falls_back_without_stored_analyses(tmp_path: Path):
    storage_root = tmp_path / "storage"
    app = create_app(storage_root=storage_root, run_jobs_inline=True)
    client = TestClient(app)

    fixture_path = Path(__file__).parent / "fixtures" / "sample_tracking.json"
    with fixture_path.open("rb") as fixture_file:
        response = client.post(
            "/api/matches",
            data={"name": "Sample Match", "inputMode": "tracking_json", "config": json.dumps({"attackDirection": "right_to_left"})},
            files={"file": ("sample_tracking.json", fixture_file, "application/json")},
        )

    match_id = response.json()["matchId"]
    export_response = client.get(f"/api/matches/{match_id}/report/html")

    assert export_response.status_code == 200
    assert "Coach report not generated yet" in export_response.text
    assert "Training drills not generated yet" in export_response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests/test_api.py::test_report_export_route_returns_html_with_stored_report_and_drills /root/WorkSpace/fotball-analyst/backend/tests/test_api.py::test_report_export_route_falls_back_without_stored_analyses -q
```

Expected: FAIL because the export route does not exist yet.

- [ ] **Step 3: Write the minimal export-route implementation**

```python
# backend/app/main.py
@app.get("/api/matches/{match_id}/report/html")
def get_match_report_html(match_id: str):
    try:
        match = storage.get_match(match_id)
        summary, _, formation_timeline, shots = storage.load_analytics(match_id)
        events = storage.load_events(match_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Match not found") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Analytics not ready") from exc

    try:
        tactical_report = storage.load_analysis_artifact(match_id, "tactical_report")
    except FileNotFoundError:
        tactical_report = None
    try:
        drills = storage.load_analysis_artifact(match_id, "drills")
    except FileNotFoundError:
        drills = None

    html = build_match_report_export(
        match=match,
        summary=summary,
        formation_timeline=formation_timeline,
        shots=shots,
        events=events,
        tactical_report=tactical_report,
        drills=drills,
    )
    return HTMLResponse(content=html)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests/test_api.py::test_report_export_route_returns_html_with_stored_report_and_drills /root/WorkSpace/fotball-analyst/backend/tests/test_api.py::test_report_export_route_falls_back_without_stored_analyses -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add /root/WorkSpace/fotball-analyst/backend/app/main.py /root/WorkSpace/fotball-analyst/backend/tests/test_api.py
git commit -m "feat: expose HTML report export route"
```

### Task 4: Add the Frontend Export Trigger

**Files:**
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/utils/api.ts`
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/utils/api.test.ts`
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/components/CoachInsights.tsx`
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/components/CoachInsights.test.tsx`
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/App.tsx`

- [ ] **Step 1: Write the failing frontend tests**

```tsx
it('opens the backend export URL from the report tab', () => {
  const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);

  render(
    <CoachInsights
      activeTab="report"
      llmThinking={false}
      tacticalReport={null}
      drillResponse={null}
      matchId="match-1"
      onGenerateReport={vi.fn()}
      onGenerateDrills={vi.fn()}
    />,
  );

  fireEvent.click(screen.getByText(/export html report/i));

  expect(openSpy).toHaveBeenCalledWith('/api/matches/match-1/report/html', '_blank', 'noopener,noreferrer');
});
```

```ts
it('returns the canonical report export URL', () => {
  expect(buildMatchReportExportUrl('match-1')).toBe('/api/matches/match-1/report/html');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /root/WorkSpace/fotball-analyst/frontend && npm test -- src/components/CoachInsights.test.tsx src/utils/api.test.ts
```

Expected: FAIL because `matchId` and `buildMatchReportExportUrl` do not exist and there is no export button.

- [ ] **Step 3: Write the minimal frontend implementation**

```ts
// frontend/src/utils/api.ts
export function buildMatchReportExportUrl(matchId: string): string {
  return `/api/matches/${matchId}/report/html`;
}
```

```tsx
// frontend/src/components/CoachInsights.tsx
interface CoachInsightsProps {
  ...
  matchId: string | null;
}

const exportHref = matchId ? buildMatchReportExportUrl(matchId) : null;

<button
  disabled={!exportHref}
  onClick={() => {
    if (exportHref) window.open(exportHref, '_blank', 'noopener,noreferrer');
  }}
>
  Export HTML Report
</button>
```

```tsx
// frontend/src/App.tsx
<CoachInsights
  ...
  matchId={activeMatch?.id ?? null}
/>
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd /root/WorkSpace/fotball-analyst/frontend && npm test -- src/components/CoachInsights.test.tsx src/utils/api.test.ts
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add /root/WorkSpace/fotball-analyst/frontend/src/utils/api.ts /root/WorkSpace/fotball-analyst/frontend/src/utils/api.test.ts /root/WorkSpace/fotball-analyst/frontend/src/components/CoachInsights.tsx /root/WorkSpace/fotball-analyst/frontend/src/components/CoachInsights.test.tsx /root/WorkSpace/fotball-analyst/frontend/src/App.tsx
git commit -m "feat: add HTML report export trigger"
```

### Task 5: Full Verification

**Files:**
- Verify only

- [ ] **Step 1: Run backend tests**

Run:

```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests -q
```

Expected: PASS

- [ ] **Step 2: Run frontend tests**

Run:

```bash
cd /root/WorkSpace/fotball-analyst/frontend && npm test
```

Expected: PASS

- [ ] **Step 3: Run frontend build**

Run:

```bash
cd /root/WorkSpace/fotball-analyst/frontend && npm run build
```

Expected: PASS

- [ ] **Step 4: Run frontend lint**

Run:

```bash
cd /root/WorkSpace/fotball-analyst/frontend && npm run lint
```

Expected: PASS

- [ ] **Step 5: Run backend syntax verification**

Run:

```bash
python3 -m py_compile /root/WorkSpace/fotball-analyst/backend/app/*.py /root/WorkSpace/fotball-analyst/backend/run_guerilla.py /root/WorkSpace/fotball-analyst/backend/train_custom.py
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add /root/WorkSpace/fotball-analyst/docs/superpowers/plans/2026-03-28-match-report-export.md
git commit -m "docs: add match report export implementation plan"
```
