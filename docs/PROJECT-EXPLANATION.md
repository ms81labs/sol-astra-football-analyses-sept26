# Guerilla Analytics v1 — Plain English Explanation

## What Is This Project?

**Guerilla Analytics** is a do-it-yourself football (soccer) video analysis system that runs 100% on your own computer — no expensive subscriptions, no cloud services, no sending your data to anyone else.

Think of it as building your own version of what professional sports analytics companies like Opta or Hawk-Eye sell for thousands of dollars per month — but for grassroots teams, academies, and amateur leagues who can't afford those prices.

The core idea: **point a camera at a football match, and get back structured tactical data** — player positions, heat maps, passing networks, event timelines, AI-generated tactical reports — all without paying for anything beyond a consumer-grade camera and a standard laptop.

---

## The Problem Being Solved

Professional football analytics systems are expensive. Teams like those in the Premier League pay massive fees for:

- **Video tracking systems** (camera rigs + software) that cost £10,000–£100,000+
- **Subscription analytics platforms** (Hudl, Metrica Sports) at £500–£2,000/month
- **Hardware cameras** with multiple lenses and proprietary stitching software

For a grassroots team, a Sunday league, or a small academy, this is simply not affordable.

**Guerilla Analytics** says: you already have a GoPro or smartphone. You already have a laptop. What if you could process that video yourself and get 80% of the insights at 0% of the cost?

---

## What Does the System Actually Do?

### Step 1: Video Capture
You mount a single wide-angle camera (like a GoPro on a tall tripod) at the sideline or center of the pitch. The camera records the entire game from above at 30fps in 4K or 1080p.

### Step 2: AI Processing (runs overnight on your laptop)
A Python pipeline processes the video:

1. **Object Detection**: Uses YOLOv10 (a fast, accurate AI model) to find all players, the ball, and referees in every frame
2. **Tracking**: Uses BoT-SORT to follow each player across frames, keeping their identity (ID number) consistent even when they cluster together
3. **Team Classification**: Clusters detected players by jersey color to separate your team (blue shirts) from the opposition (red shirts)
4. **Ball Tracking**: Follows the ball separately, even when it's partially hidden behind players
5. **Homography Mapping**: You click 4 points on the first frame to tell the system where the pitch corners are. The system uses this to convert 2D camera coordinates into a 2D top-down pitch view (like looking at the pitch from directly above)
6. **Event Detection**: Identifies discrete events — passes, shots, tackles, turnovers, offsides — based on ball and player movement patterns
7. **Analytics Generation**: Computes:
   - Possession statistics
   - Passing networks (who passes to whom)
   - Shot maps with xG (expected goals)
   - Player speed and sprint data
   - Defensive line heights
   - Pressing intensity (PPDA)

The output is a set of **JSON files** (structured data) — NOT a new video. The raw numbers, timestamps, and coordinates.

### Step 3: Interactive Review (React Frontend)
A web-based tactical panel lets coaches and analysts:

- **Play back the match** as an animated 2D pitch (players as dots moving on a pitch graphic)
- **Click any frame** to see exact positions
- **Toggle layers**: heat maps, passing networks, shot markers, defensive zones
- **Search by tactical theme**: "show me counter-attacks from this match" or "find high press regains"
- **Ask an AI assistant**: "Why did we concede from the left side?" — powered by a local LLM (Llama 3.1 or DeepSeek-R1 running via Ollama)
- **Generate drill suggestions** based on detected weaknesses
- **Create review bundles**: annotate specific moments, save them to a playlist, export for later
- **Flag uncertain frames**: if the AI is unsure about a tracking decision, it surfaces those frames for human review

### Step 4: Human-in-the-Loop Improvement
The system identifies frames where tracking confidence is low (ball teleport, player occlusion, team flip). These "trust crops" get queued for human review. Corrections get fed back into the system to improve future accuracy.

---

## Key Technologies

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Object Detection** | YOLOv10 | Find players, ball, referees in video frames |
| **Multi-Object Tracking** | BoT-SORT | Keep track of which player is which across frames |
| **Homography** | Manual 4-point calibration + OpenCV | Convert camera view → top-down pitch view |
| **Backend API** | FastAPI (Python) | Serves processed data to frontend |
| **Frontend** | React + TypeScript + Tailwind CSS | Interactive tactical panel |
| **Canvas Rendering** | HTML5 Canvas | 2D pitch animation |
| **Local AI** | Ollama + Llama 3.1 / DeepSeek-R1 | Tactical report generation, drill suggestions |
| **Data Storage** | SQLite + JSON files | Match metadata and processed artifacts |
| **Cloud AI (optional)** | Gemini via toggle | Alternative AI provider |

---

## What the Code Actually Does (Technical Summary)

The codebase has two main parts:

### Backend (`/backend/app/`)
A FastAPI Python server that:

- **`main.py`**: Defines all HTTP endpoints — upload video, list matches, get analytics, export CSV, search by tactical themes, manage annotations, manage issues, compute trust crops, serve dashboard aggregates, websocket for job progress
- **`processor.py`**: The main video processing pipeline — runs YOLOv10 detection, BoT-SORT tracking, team classification, homography estimation, event detection
- **`run_guerilla.py`**: The main entry point script — orchestrates the full pipeline from raw video to analytics
- **`storage.py`**: SQLite database wrapper for matches/jobs + JSON file management for frames/analytics/events
- **`llm.py`**: Interfaces with Ollama or Gemini for tactical analysis and drill generation
- **`semantic_search.py`**: Keyword-based search over match analytics to find tactical themes (high press, low block, counter-attacks)
- **`export_flatteners.py`**: Converts structured analytics into CSV format for export
- **`trust_crops.py`**: Heuristic-based quality control — flags frames with ball teleport, track switches, team flips, possession gaps
- **`run_benchmarks.py`**: Computes summary statistics about tracking quality per match
- **`schemas.py`**: Pydantic data models for all API request/response types

### Frontend (`/frontend/src/`)
A React TypeScript application that:

- **`App.tsx`**: Main application shell — manages match list, active match state, playback controls, upload flow
- **`TacticalPitch.tsx`**: Canvas-based 2D pitch renderer — draws players, ball, annotations, heat maps, passing networks, shot markers, zones
- **`Timeline.tsx`**: Video-style timeline with frame scrubbing
- **`CoachInsights.tsx`**: AI assistant panel — sends queries to backend LLM, displays tactical reports and drill suggestions
- **`DashboardPanel.tsx`**: Season aggregate statistics — possession trends, xG comparison, formation usage
- **`TrustCropPanel.tsx`**: Review interface for uncertain frames flagged by the backend
- **`AnnotationList.tsx`**: Review bundle management — save/load annotated moments
- **`useReviewSurface.ts`**: React hook managing annotations, issues, and review range state
- **`useCoachAnalysis.ts`**: React hook managing LLM interaction state
- **`api.ts`**: TypeScript API client for all backend endpoints
- **`analytics.ts`**: Computes heat maps, passing networks, player speeds, shot summaries from raw frame data

---

## The Development Workflow (How It Currently Works)

1. **Upload**: Coach selects a video file + calibration points (or enables auto-calibration) + selects attack direction
2. **Processing starts**: A job gets queued; the video is processed in the background
3. **Progress tracking**: Frontend polls `/api/jobs/{job_id}` via websocket to show progress
4. **Completion**: Match appears in the list as "ready"
5. **Analysis**: Coach watches playback, toggles layers, asks the AI for insights, creates annotations
6. **Export**: Coach can export frames.csv, events.csv, or full HTML match report
7. **Iteration**: If tracking looks wrong, coach can change team cluster (which team is "my team") and trigger reprocessing

---

## What "Semantic Search" Means

Beyond simple filtering, the system lets you search your match history using plain English:

- "high press counter-attacks" → finds matches where your team won the ball high and transitioned quickly
- "low block wing play" → finds matches where you defended deep and attacked through the flanks
- "through balls in behind" → finds matches with vertical passes breaking the defensive line

This works by checking match analytics data (PPDA, defensive line height, regain zones, etc.) against a dictionary of tactical keywords. It's not full AI interpretation — it's rule-based keyword matching against derived statistics.

---

## What "Trust Crops" Means

The AI tracking system is confident about most frames. But some frames are genuinely ambiguous — the ball teleported (jumped position), a player's ID switched with a teammate's, the team possession flipped for no reason.

The `trust_crops.py` module runs heuristics to automatically detect these uncertain windows:

- **Ball teleport**: ball moved more than 15 pitch units between frames (physically impossible)
- **Track switches**: player ID changed without an obvious explanation
- **Team flips**: possession oscillating between teams rapidly
- **Possession gaps**: long runs of "unassigned" or "contested" ball state

These windows get surfaced in the TrustCropPanel for human review. Corrections improve the training loop.

---

## Project Status

This is an active development project (version 1). The core pipeline is functional:

- Video upload + calibration → processed match with analytics ✅
- 2D pitch playback with multiple overlay layers ✅
- LLM-powered tactical reports and drill suggestions ✅
- Semantic search over match history ✅
- Annotation and issue logging ✅
- Trust crop review queue ✅
- Dashboard with season aggregates ✅
- CSV export for frames and events ✅

Known limitations (in scope for future work):

- Single-camera only (no multi-angle stitching)
- No live/realtime processing
- Ball tracking accuracy degrades with extreme camera angles or lighting
- No 3D projection (only 2D top-down)
- Team classification relies on jersey color contrast

---

## Quick Start

```bash
# Backend
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

Then open `http://localhost:5173` in your browser.
