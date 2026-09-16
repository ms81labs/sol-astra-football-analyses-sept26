# PDF Report Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** add a backend-generated PDF match report that reuses the existing HTML export source and exposes a new downloadable PDF route plus a frontend trigger button.

**Architecture:** keep the HTML report as the canonical source and derive PDF from it at request time. Implement a small backend PDF renderer adapter that writes the report HTML to a temp file, invokes headless `google-chrome` to print it to PDF, and returns the bytes through a FastAPI route; then add one frontend button that opens the canonical PDF URL.

**Tech Stack:** FastAPI, Python `subprocess`, temporary files, headless `google-chrome`, React, Vitest, Testing Library, pytest

---

### File Structure

**Backend**
- Create: `/root/WorkSpace/fotball-analyst/backend/app/pdf_export.py`
  - render PDF bytes from existing HTML using headless Chrome
- Modify: `/root/WorkSpace/fotball-analyst/backend/app/main.py`
  - expose `GET /api/matches/{match_id}/report/pdf`
- Modify: `/root/WorkSpace/fotball-analyst/backend/app/report_export.py`
  - add a report filename helper shared by HTML and PDF export responses
- Modify: `/root/WorkSpace/fotball-analyst/backend/tests/test_api.py`
  - add route tests for PDF export success/fallback/not-found
- Create: `/root/WorkSpace/fotball-analyst/backend/tests/test_pdf_export.py`
  - unit tests for the PDF renderer adapter

**Frontend**
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/utils/api.ts`
  - add a PDF export URL helper
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/utils/api.test.ts`
  - cover the PDF helper
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/components/CoachInsights.tsx`
  - add `Export PDF Report`
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/components/CoachInsights.test.tsx`
  - cover PDF button behavior

### Task 1: Add a Backend PDF Renderer Adapter

**Files:**
- Create: `/root/WorkSpace/fotball-analyst/backend/app/pdf_export.py`
- Test: `/root/WorkSpace/fotball-analyst/backend/tests/test_pdf_export.py`

- [ ] **Step 1: Write the failing renderer tests**

```python
from pathlib import Path

import pytest

from backend.app.pdf_export import render_html_to_pdf_bytes


def test_render_html_to_pdf_bytes_returns_pdf_bytes(monkeypatch, tmp_path: Path):
    captured = {}

    def fake_run(cmd, check):  # noqa: ANN001
        captured["cmd"] = cmd
        output_arg = next(part for part in cmd if part.startswith("--print-to-pdf="))
        output_path = Path(output_arg.split("=", 1)[1])
        output_path.write_bytes(b"%PDF-1.7\\nmock-pdf")
        return None

    monkeypatch.setattr("backend.app.pdf_export.subprocess.run", fake_run)
    monkeypatch.setattr("backend.app.pdf_export.tempfile.mkdtemp", lambda prefix: str(tmp_path / "pdf-job"))

    pdf_bytes = render_html_to_pdf_bytes("<html><body><h1>Match Report</h1></body></html>")

    assert pdf_bytes.startswith(b"%PDF")
    assert any(part.startswith("--print-to-pdf=") for part in captured["cmd"])
    assert any(part.startswith("file://") for part in captured["cmd"])
```

```python
def test_render_html_to_pdf_bytes_raises_clear_error_when_chrome_fails(monkeypatch, tmp_path: Path):
    def fake_run(cmd, check):  # noqa: ANN001
        raise subprocess.CalledProcessError(returncode=1, cmd=cmd)

    monkeypatch.setattr("backend.app.pdf_export.subprocess.run", fake_run)
    monkeypatch.setattr("backend.app.pdf_export.tempfile.mkdtemp", lambda prefix: str(tmp_path / "pdf-job"))

    with pytest.raises(RuntimeError, match="PDF export failed"):
        render_html_to_pdf_bytes("<html><body>Broken</body></html>")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests/test_pdf_export.py -q
```

Expected: FAIL because `pdf_export.py` and `render_html_to_pdf_bytes` do not exist.

- [ ] **Step 3: Write the minimal renderer implementation**

```python
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def render_html_to_pdf_bytes(html: str) -> bytes:
    chrome_path = shutil.which("google-chrome")
    if not chrome_path:
        raise RuntimeError("PDF export failed: google-chrome is not installed.")

    temp_dir = Path(tempfile.mkdtemp(prefix="guerilla-pdf-"))
    html_path = temp_dir / "report.html"
    pdf_path = temp_dir / "report.pdf"
    html_path.write_text(html, encoding="utf-8")

    try:
        subprocess.run(
            [
                chrome_path,
                "--headless",
                "--disable-gpu",
                "--no-sandbox",
                f"--print-to-pdf={pdf_path}",
                html_path.resolve().as_uri(),
            ],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("PDF export failed while rendering the match report.") from exc

    return pdf_path.read_bytes()
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests/test_pdf_export.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add /root/WorkSpace/fotball-analyst/backend/app/pdf_export.py /root/WorkSpace/fotball-analyst/backend/tests/test_pdf_export.py
git commit -m "feat: add backend PDF renderer adapter"
```

### Task 2: Expose the PDF Export Route

**Files:**
- Modify: `/root/WorkSpace/fotball-analyst/backend/app/main.py`
- Modify: `/root/WorkSpace/fotball-analyst/backend/app/report_export.py`
- Modify: `/root/WorkSpace/fotball-analyst/backend/tests/test_api.py`

- [ ] **Step 1: Write the failing PDF route tests**

```python
def test_report_pdf_route_returns_pdf_bytes(tmp_path: Path, monkeypatch):
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
    monkeypatch.setattr("backend.app.main.render_html_to_pdf_bytes", lambda html: b"%PDF-1.7\\nreport")

    pdf_response = client.get(f"/api/matches/{match_id}/report/pdf")

    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"].startswith("application/pdf")
    assert pdf_response.content.startswith(b"%PDF")
    assert "sample-match-report.pdf" in pdf_response.headers["content-disposition"]
```

```python
def test_report_pdf_route_falls_back_without_stored_analyses(tmp_path: Path, monkeypatch):
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
    captured = {}

    def fake_render(html: str) -> bytes:
        captured["html"] = html
        return b"%PDF-1.7\\nfallback"

    monkeypatch.setattr("backend.app.main.render_html_to_pdf_bytes", fake_render)

    pdf_response = client.get(f"/api/matches/{match_id}/report/pdf")

    assert pdf_response.status_code == 200
    assert "Coach report not generated yet" in captured["html"]
    assert "Training drills not generated yet" in captured["html"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests/test_api.py::test_report_pdf_route_returns_pdf_bytes /root/WorkSpace/fotball-analyst/backend/tests/test_api.py::test_report_pdf_route_falls_back_without_stored_analyses -q
```

Expected: FAIL because the PDF route and shared filename helper do not exist.

- [ ] **Step 3: Write the minimal route implementation**

```python
# backend/app/report_export.py
import re


def build_report_filename(match_name: str, suffix: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", match_name.lower()).strip("-") or "match"
    return f"{slug}-report.{suffix}"
```

```python
# backend/app/main.py
from fastapi.responses import FileResponse, HTMLResponse, Response

from .pdf_export import render_html_to_pdf_bytes
from .report_export import build_match_report_export, build_report_filename


@app.get("/api/matches/{match_id}/report/pdf")
def get_match_report_pdf(match_id: str) -> Response:
    try:
        match = storage.get_match(match_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Match not found") from exc

    try:
        summary, _, formation_timeline, shots = storage.load_analytics(match_id)
        events = storage.load_events(match_id)
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
    pdf_bytes = render_html_to_pdf_bytes(html)
    filename = build_report_filename(match.name, "pdf")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests/test_api.py::test_report_pdf_route_returns_pdf_bytes /root/WorkSpace/fotball-analyst/backend/tests/test_api.py::test_report_pdf_route_falls_back_without_stored_analyses -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add /root/WorkSpace/fotball-analyst/backend/app/main.py /root/WorkSpace/fotball-analyst/backend/app/report_export.py /root/WorkSpace/fotball-analyst/backend/tests/test_api.py
git commit -m "feat: expose PDF match report export route"
```

### Task 3: Add the Frontend PDF Export Trigger

**Files:**
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/utils/api.ts`
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/utils/api.test.ts`
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/components/CoachInsights.tsx`
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/components/CoachInsights.test.tsx`

- [ ] **Step 1: Write the failing frontend tests**

```ts
it('returns the canonical PDF export URL', () => {
  expect(buildMatchReportPdfUrl('match-1')).toBe('/api/matches/match-1/report/pdf');
});
```

```tsx
it('opens the backend PDF export URL from the report tab', () => {
  const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);

  render(
    <CoachInsights
      activeTab="report"
      llmThinking={false}
      matchId="match-1"
      tacticalReport={null}
      drillResponse={null}
      onGenerateReport={vi.fn()}
      onGenerateDrills={vi.fn()}
    />,
  );

  fireEvent.click(screen.getByText(/export pdf report/i));

  expect(openSpy).toHaveBeenCalledWith('/api/matches/match-1/report/pdf', '_blank', 'noopener,noreferrer');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /root/WorkSpace/fotball-analyst/frontend && npm test -- src/components/CoachInsights.test.tsx src/utils/api.test.ts
```

Expected: FAIL because the PDF helper and button do not exist.

- [ ] **Step 3: Write the minimal frontend implementation**

```ts
// frontend/src/utils/api.ts
export function buildMatchReportPdfUrl(matchId: string): string {
  return `/api/matches/${matchId}/report/pdf`;
}
```

```tsx
// frontend/src/components/CoachInsights.tsx
import { buildMatchReportExportUrl, buildMatchReportPdfUrl } from '../utils/api';

const pdfHref = matchId ? buildMatchReportPdfUrl(matchId) : null;

<button
  disabled={!pdfHref}
  onClick={() => {
    if (pdfHref) {
      window.open(pdfHref, '_blank', 'noopener,noreferrer');
    }
  }}
>
  Export PDF Report
</button>
```

Place it alongside the existing HTML export button in both the `report` and `drills` tab action rows.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd /root/WorkSpace/fotball-analyst/frontend && npm test -- src/components/CoachInsights.test.tsx src/utils/api.test.ts
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add /root/WorkSpace/fotball-analyst/frontend/src/utils/api.ts /root/WorkSpace/fotball-analyst/frontend/src/utils/api.test.ts /root/WorkSpace/fotball-analyst/frontend/src/components/CoachInsights.tsx /root/WorkSpace/fotball-analyst/frontend/src/components/CoachInsights.test.tsx
git commit -m "feat: add PDF report export trigger"
```

### Task 4: Full Verification

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

- [ ] **Step 6: Smoke-check a generated PDF route locally**

Run:

```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests/test_pdf_export.py -q
```

Expected: PASS with the adapter producing PDF-signature bytes in tests.

- [ ] **Step 7: Commit**

```bash
git add /root/WorkSpace/fotball-analyst/docs/superpowers/plans/2026-03-28-pdf-report-export.md
git commit -m "docs: add PDF report export implementation plan"
```
