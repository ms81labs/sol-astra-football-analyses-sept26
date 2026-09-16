# Gap Analysis Report: Research vs Implementation

## Executive Summary

This report compares the comprehensive technical research documented in `Football Video Analysis Technical Research.md` against the actual implementation in the `fotball-analyst` codebase. The research outlines a state-of-the-art football analysis pipeline covering 8 major domains, while the current implementation provides a functional foundation with significant trust-hardening infrastructure already in place.

**Overall Implementation Status: ~65-70% of Research Scope**

> **Note on Trust Hardening**: The codebase has a mature trust infrastructure (see Section 8) that was not present when this analysis was first created. The percentage reflects current shipped code, not theoretical completeness.

---

## 1. Ball Detection & Tracking

### Research Requirements
| Component | Specification |
|-----------|---------------|
| **Detector** | YOLOv10/YOLOv11 with low confidence threshold (0.05) for maximum recall |
| **Distractor Suppression** | Spatial filtering via pitch polygon masking |
| **Temporal Filtering** | 3rd-order polynomial smoothing over 51-frame sliding window |
| **Occlusion Handling** | TOTNet-style 3D temporal convolutions |
| **3D Trajectory** | LSTM + physics-based parabolic modeling for airborne ball parallax correction |

### Current Implementation
```python
# backend/run_guerilla.py
TARGET_FPS = 5
# Basic homography-based projection
px, py = point_to_pitch(H, cx, cy)
# Simple bottom-of-bbox for pitch projection
cy = y2  # Use bottom of bounding box (feet) for pitch projection
```

**Status: PARTIAL (~50%)**
- Uses YOLO (YOLOv10n via Ultralytics) with BoT-SORT tracking
- Basic homography projection (4-point manual calibration)
- **Fallback ball recovery seam exists** - triggers when primary pass returns zero ball rows
  - Narrows search to player envelope
  - Retries after suppressing dominant static cluster
  - Rejects quasi-static clusters without meaningful motion
- **Pitch polygon spatial filtering is the RESEARCH solution** (not missing from research) - described as the fix for sideline ball projection
- No 3D ball trajectory estimation
- No TOTNet-style occlusion handling
- No physics-based trajectory refinement

### Gap Analysis
1. **Research Solution Exists**: Pitch polygon masking via homography (the research doc describes this)
2. **In Research, Not Shipped**: 3D ball trajectory estimation for airborne balls
3. **In Research, Not Shipped**: Temporal occlusion modeling (TOTNet-style)
4. **In Research, Not Shipped**: Physics-based trajectory refinement (Magnus effect, drag)
5. **Unresolved**: Prove fallback ball recovery works on canonical clip

---

## 2. Homography & Camera Calibration

### Research Requirements
| Component | Specification |
|-----------|---------------|
| **Method** | PnLCalib (Points + Lines) or NBJW (No Bells Just Whistles) |
| **Features** | Line segments, vanishing points, conic sections (center circle, penalty arcs) |
| **Refinement** | Levenberg-Marquardt non-linear optimization |
| **Temporal Smoothing** | Savitzky-Golay filtering or EKF for camera parameters |
| **Lens Distortion** | Integrated distortion parameters for wide-angle/fisheye |

### Current Implementation
```python
# backend/pitch_detector.py - Auto detection (primary)
detect_pitch_corners(frame)  # edge detection + Hough lines + intersection scoring
detect_and_compute_homography(frame)  # auto-first pipeline
# → fallback: run_guerilla.py manual 4-point selection

# Periodic recalculation every 150 frames during tracking
```

**Status: PARTIAL (~50%)**
- **Automatic field line detection** via edge detection + Hough lines + intersection scoring ✅
- **Two-strategy fallback**: primary (general pitch outline) + penalty-box pattern match
- Manual 4-point selection as fallback when auto confidence < 0.3
- Periodic recalculation every 150 frames during tracking ✅
- No line/conic-based calibration (advanced)
- No vanishing point estimation (advanced)
- No temporal smoothing of camera parameters (E.2 pending)
- No lens distortion correction (advanced)

### Gap Analysis
1. **Needs validation**: Auto-detection accuracy on diverse camera angles (fisheye, cropped pitch)
2. **Missing**: Line clustering + vanishing-point estimation for wide-angle robustness
3. **Missing**: Levenberg-Marquardt non-linear refinement
4. **Missing**: Lens distortion parameters

---

## 3. Multi-Object Tracking (MOT)

### Research Requirements
| Component | Specification |
|-----------|---------------|
| **Algorithm** | ByteTrack (two-stage association) or BoT-SORT with CMC |
| **Low-Confidence Boxes** | Utilize to sustain tracklets during blur |
| **Camera Motion Compensation** | BoT-SORT with optical flow/ORB feature matching |
| **Interpolation** | Gaussian Process Smoothing for short occlusions |
| **ID Merge** | AFLink (Appearance-Free Linking) for fragmented tracks |
| **Player ID** | Temporal ReID + Tracklet OCR for jersey numbers |

### Current Implementation
```python
# backend/run_guerilla.py
results = model.track(source=video_path, stream=True, persist=True, tracker="botsort.yaml")
# Uses BoT-SORT tracker from Ultralytics
```

**Status: PARTIAL (~40%)**
- BoT-SORT configured via Ultralytics (default settings)
- Team assignment via color clustering
- No camera motion compensation tuning
- No Gaussian Process interpolation
- No AFLink for track merging
- No OCR-based player identification (see Section 4)

### Gap Analysis
1. **Missing**: Camera motion compensation tuning
2. **Missing**: Tracklet interpolation for occlusions
3. **Missing**: Appearance-free ID linking (AFLink)
4. **Dependency**: OCR for jersey numbers (see Team Assignment section)

---

## 4. Team Assignment & Player Classification

### Research Requirements
| Component | Specification |
|-----------|---------------|
| **Method** | Convolutional autoencoders for color latent space |
| **Clustering** | K-Means/DBSCAN for Team A, Team B, Referees |
| **Player ID** | OSNet ReID embeddings + Spatial Transformer Networks for OCR |
| **Verification** | Multimodal autoregressive (Vision-Language Models like LLAMA-3.2-Vision) |

### Current Implementation
```python
# backend/app/team_classification.py
def cluster_track_colors(track_colors, cluster_count=2):
    # Simple k-means clustering on RGB means
    centroids = _initialize_centroids(vectors, cluster_count)
    # ... iterative assignment
    return ColorClusterResult(...)
```

**Status: PARTIAL (~45%)**
- Basic RGB color clustering implemented
- Manual team selection required (`requiresTeamSelection` flag)
- **Jersey OCR exists but is synthetic-gated**:
  - Synthetic golden set: 35 samples
  - OCR gate: 85.7% (12/14) vs 80.0% threshold
  - Real-footage OCR: 66.7% (weakest bucket - medium-difficulty reads)
  - Team gate: 96.3% (26/27) vs 85.0% threshold
- No deep ReID embeddings (OSNet or similar)
- No Vision-Language Model verification

### Gap Analysis
1. **Weakest Bucket**: Real-footage OCR at 66.7% needs improvement
2. **Missing**: Deep appearance features (OSNet, etc.)
3. **Missing**: Referee/goalkeeper automatic separation
4. **Missing**: Multimodal identity verification

---

## 5. Event Detection

### Research Requirements
| Component | Specification |
|-----------|---------------|
| **Pass Detection** | Ball possession continuity analysis |
| **Shot Detection** | Shooting zone detection + xG modeling |
| **Through Ball** | Line-breaking pass detection |
| **Cross Detection** | Wide-to-box passing patterns |
| **Tackle/Interception** | Turnover detection with proximity |
| **Offside** | 3D-aware offside line calculation |

### Current Implementation
```python
# backend/app/analytics.py
def detect_events(frames, assignments):
    # Pass, shot, through_ball, cross, turnover, tackle, interception, recovery
    # Basic zone-based detection (is_shooting_zone, is_attacking_wide, etc.)
    # xG calculation with distance + angle factors
```

**Status: GOOD (~70%)**
- Comprehensive event types implemented
- xG modeling with distance, angle, and in-box factors
- Basic tactical event classification
- Formation timeline building
- Bounded event repair for short contested/unassigned gaps

### Gap Analysis
1. **Missing**: 3D-aware offside detection (parallax correction)
2. **Missing**: Advanced pass quality metrics (progressive passes, etc.)
3. **Missing**: Set piece detection (corners, free kicks, penalties)
4. **Missing**: Event confidence scoring

---

## 6. Analytics & Metrics

### Research Requirements
| Component | Specification |
|-----------|---------------|
| **Possession** | Distance-based or time-based with contested state |
| **xG** | Physics-informed with goalkeeper position |
| **Pressing** | PPDA, high-press regains, counter-press recovery |
| **Defensive Shape** | Block height classification, regain zones |
| **Physical Metrics** | Sprint detection, top speed, acceleration |

### Current Implementation
```python
# backend/app/analytics.py
class MatchSummary(BaseModel):
    # Possession, distance, speed, sprints, xG
    # Defensive metrics: line height, team length
    # Pressing: PPDA, high-press regains, counter-press recovery
    # Defensive context: block height, regain zones, transition exposure
```

**Status: GOOD (~80%)**
- Comprehensive match summary metrics
- Defensive shape analysis (block height classification)
- Pressing metrics (PPDA, high-press regains)
- Transition exposure tracking
- Zone-based regain classification
- Possession slices with `unassigned` for ball-missing frames

### Gap Analysis
1. **Missing**: Goalkeeper-aware xG adjustment
2. **Missing**: Expected threat (xT) models
3. **Missing**: Set piece success rates

---

## 7. LLM Integration & Tactical Intelligence

### Research Requirements
| Component | Specification |
|-----------|---------------|
| **Architecture** | RAG with vector database (Chroma) |
| **Models** | TacticalGPT, LLAMA-3.2-Vision, Gemini multimodal |
| **Prompting** | Structured tactical synthesis from tracking data |
| **Grounding** | Strict RAG-only response, no hallucinations |
| **RLHF** | Human feedback for adapter fine-tuning |

### Current Implementation
```typescript
// frontend/src/utils/llm.ts
export async function askLocal(prompt: string): Promise<LlmResponse> {
    // Calls local Ollama with DeepSeek-R1:1.5b
    const response = await fetch('/api/generate', {...});
}
export async function askGemini(prompt: string, schema, apiKey) {
    // Calls Gemini 2.5-flash with structured output
}
export function buildTacticalReportPrompt(frames: FrameData[]): string {
    // Basic prompt building for tactical analysis
}
```

**Status: PARTIAL (~55%)**
- Local (Ollama/DeepSeek) and Cloud (OpenRouter) toggle implemented — OpenRouter routes to any model (Claude, GPT, DeepSeek, etc.)
- Basic tactical prompting for reports and drills
- Structured output schemas defined
- **Structured context injection** — prompts receive derived match context; no vector database or RAG pipeline
- `useCoachAnalysis` hook wired into App.tsx ✅ — replaces 6 inline state vars, manages LLM provider toggle, analysis tabs, and request lifecycle
- No RLHF or adapter fine-tuning
- **Strict hallucination prevention not shipped** - outputs can include `needs_review` when trust is low

### Gap Analysis
1. **Missing**: Full RAG architecture (vector database integration)
2. **Missing**: Structured JSON artifact embedding for retrieval
3. **Dependency**: Trust infrastructure (Section 8) must be mature before LLM can safely synthesize

---

## 8. Trust Hardening & Evaluation Infrastructure

> **This section was not in the original gap analysis but represents significant shipped infrastructure.**

### Research Requirements
| Component | Specification |
|-----------|---------------|
| **Error Taxonomy** | IDSW, FP/FN, Team Misclassification, Ball Parallax |
| **Active Learning** | Uncertainty-based sampling for "trust crops" |
| **Kinematic Heuristics** | Human biomechanics limits (acceleration, max speed) |
| **Physics Validation** | Ball trajectory physics checks |

### Current Implementation
**Status: PARTIAL (~55%)**

The system has a mature trust infrastructure:

**SHIPPED:**
- Trust metrics reported by `source_type` (synthetic vs real_footage)
- Synthetic golden set: 35 samples
- Trust gates:
  - OCR: 85.7% (12/14) vs 80.0% threshold
  - Team: 96.3% (26/27) vs 85.0% threshold
  - Calibration: 100.0% (3/3) vs 80.0% threshold
- Real-footage intake path exists via `register_real_footage_sample.py`
  - Supports `demo_match` provenance fields
  - Direct crop promotion from reviewed matches
- Review issue capture via `DemoMatchIssuePanel.tsx` — ✅ **wired into App.tsx with full CRUD** (backend: `GET/POST/DELETE /api/matches/{id}/issues`)
  - Structured buckets: `team_classification_issue`, `event_layer_issue`, etc.
  - Evidence targets, frame/timestamp ranges, notes
- `needs_review` contract — ✅ **`needs_review` UI banner wired** in StatsPanel (amber warning) and CoachInsights (disabled buttons + warning note, D.1 done)
- **Trust crops API** — ✅ `GET /api/matches/{id}/trust-crops` with heuristic scoring (D.2 done)

**STILL MISSING:**
- Active learning "trust crops" prioritization (uncertainty-based sampling) — ✅ **TrustCropPanel now built** (D.2 frontend done)
- Full RLHF feedback loop
- Automated kinematic violation detection — **D.3 pending**
- First human-labeled real-footage sample in trust manifest

### Gap Analysis
1. **Pending**: First real-footage trust crop registration
2. **Shipped** ✅: ~~Trust crop queue~~ — ✅ DONE (D.2)
3. **Missing**: Automated kinematic validation
4. **Missing**: RLHF adapter fine-tuning
5. **Shipped** ✅: ~~`needs_review` UI banner~~ — ✅ DONE (D.1)

---

## 9. Frontend Workspace

### Research Requirements
| Component | Specification |
|-----------|---------------|
| **Video-Map Sync** | Frame-accurate synchronization |
| **Telestration** | Drawing tools for error annotation |
| **Error Reporting** | Structured failure categorization |
| **Trust Crop Queue** | Priority queue for uncertain segments — ✅ DONE (D.2)

### Current Implementation
```typescript
// frontend/src/App.tsx
// TacticalPitch canvas with player/ball overlay
// Video playback with frame synchronization
// Timeline with event markers
// Stats panel with comparison mode
```

**Status: GOOD (~85%)**
- TacticalPitch canvas with visualization + **click-player-for-stats** (`onPlayerClick` hit-test handler) ✅
- Video synchronization working ✅
- **Timeline with range selection** — `Timeline.new.tsx` swapped in as `Timeline.tsx`, review range start/end/clear buttons wired ✅
- Comparison mode for multiple matches (side-by-side stats via dropdown) ✅
- Visual overlays (heatmap, zones, passing network, shots) ✅
- Semantic search API exists (`/api/search/matches`, `/api/search/bundles`) ✅
- **Issue capture panel** (`DemoMatchIssuePanel.tsx`) — ✅ wired into App.tsx as modal, full backend CRUD
- **Annotation list + Review toolbar** — ✅ wired via `useReviewSurface` hook, backend CRUD for annotations
- **PlayerDetailPanel** — ✅ wired via TacticalPitch canvas click handler, slide-out overlay
- **useCoachAnalysis** — ✅ replaces 6 inline state vars in App.tsx
- **Trust gating UI** — ✅ **`needs_review` banner in StatsPanel + CoachInsights** (disabled buttons + warning note, D.1 done)
- **Telestration drawing** — ✅ **Arrow + Circle drawing on TacticalPitch** with DrawingToolbar wired to `useReviewSurface` (C.1 done)
- **Trust Crop Panel** — ✅ **TrustCropPanel.tsx** modal with score bars, reason tags, seek-to-frame per crop; wired to `showTrustCrop` state in App.tsx (D.2 frontend done)
- ~~Coach retrieval workspace with tactical match search~~ — ⚠️ API-only, no dedicated retrieval UI (worktree has `RetrievalWorkspacePanel.tsx`)
- ~~Longitudinal player trend snapshots~~ — ❌ zero code on any branch

### Gap Analysis
1. **Missing**: ~~Telestration/drawing tools~~ — ✅ **Arrow + Circle drawing on TacticalPitch** — DrawingToolbar with Arrow/Circle buttons, mouse handlers for live preview, saved annotations rendered after players, wired via `useReviewSurface` (C.1 done)
2. **Shipped** ✅: ~~Trust crop priority queue UI~~ — **TrustCropPanel.tsx** with score bars, reason tags, seek-to-crop, and TrustCrop API wired in App.tsx toolbar button (D.2 complete)
3. **Missing**: Annotation export for human correction pipeline
4. **Shipped** ✅: Report export button in `CoachInsights.tsx`
5. **Shipped** ✅: `DashboardPanel.tsx` — wired in App.tsx with season trends, comparison, and match list
   - `TacticalBrainPanel.tsx` — ❌ does not exist
   - `RetrievalWorkspacePanel.tsx` — ❌ does not exist (API exists, no dedicated UI)

---

## 10. Infrastructure & Data Pipeline

### Research Requirements
| Component | Specification |
|-----------|---------------|
| **Artifacts** | raw_rows.json, frames.json, events.json, analytics.json |
| **Storage** | Structured JSON/Parquet with validation |
| **Benchmark** | SoccerNet-GSR, SoccerNet-v3D evaluation |

### Current Implementation
```python
# backend/app/storage.py
# SQLite for match/job records
# JSON files for frames, analytics, events
# Parquet export available via run_guerilla.py
```

**Status: GOOD (~75%)**
- Proper schema definitions (Pydantic)
- SQLite for metadata with WAL mode ✅
- JSON artifact storage (frames, analytics, events, annotations, issues)
- Parquet export capability
- Provenance fields for trust tracking
- Annotation + Issue CRUD endpoints ✅ (6 routes: `GET/POST/DELETE` for both)
- Dashboard aggregation endpoint ✅ (`GET /api/aggregate/dashboard` + `DashboardPanel.tsx`)

### Gap Analysis
1. **Missing**: SoccerNet benchmark evaluation
2. **Missing**: Formal data validation pipeline
3. **Shipped** ✅: ~~Dashboard aggregation endpoint~~ — ✅ DONE (B.2)

---

## Revised Priority Roadmap

### Phase 1: Prove Current Pipeline (Immediate)
1. **Run a dedicated detector experiment on the canonical demo clip** - fallback is now proven to improve artifacts, but the saved run still ends `ballSignalStatus = untrusted` because the recovered ball is dominated by a repeated static anchor
2. **Register first real-footage trust crop** through promotion path
3. **Expand ball-trust evaluation heuristics** with explicit coherence checks rather than reopening downstream possession/event heuristics

### Phase 2: Close Evaluation Gaps (Short-term)
1. **Active learning framework** - Confidence-based "trust crops" prioritization
2. **Real-footage OCR improvement** - Address 66.7% bucket
3. **Automated kinematic validation** - Physics-based ball trajectory checks

### Phase 3: Core Improvements (Medium-term)
1. **Automatic field calibration** - Line detection + vanishing points
2. **Temporal smoothing** - Savitzky-Golay on camera parameters
3. **3D ball trajectory** - Physics-based airborne ball tracking
4. **SQLite WAL mode** — DONE ✅ (`PRAGMA journal_mode=WAL` added to `Storage._connect()` for concurrent read/write safety)

### Phase 4: Advanced Features (Long-term)
1. **RAG architecture** - Vector database for LLM grounding
2. **TOTNet occlusion handling** - Temporal ball tracking
3. **AFLink track merging** - Appearance-free ID continuity
4. **Benchmark evaluation** - SoccerNet metrics
5. **RLHF feedback loop** - Coach preference adaptation

---

## Implementation Guidance: Closing Every Remaining Gap

> This section provides **actionable, file-level guidance** for every item that is NOT at 100%.
> Each task includes: what to build, where to put it, how to approach it, what it depends on, and how to verify.

---

### A. Frontend Wiring — Cherry-Picked Components ✅ DONE

All 5 tasks completed:

#### A.1 ~~Wire `PlayerDetailPanel.tsx`~~ ✅

TacticalPitch canvas has `onPlayerClick` hit-test handler (12px distance threshold). App.tsx renders `PlayerDetailPanel` in slide-out overlay. Verified: click player dot → stats panel appears.

#### A.2 ~~Swap Timeline~~ ✅

`Timeline.new.tsx` renamed to `Timeline.tsx` (old saved as `Timeline.legacy.tsx`). App.tsx passes `reviewRange` + `onRangeChange` via `useReviewSurface`. `CustomEvent('add-event')` bridge listener wired.

#### A.3 ~~Wire `DemoMatchIssuePanel.tsx`~~ ✅

Wired as modal overlay with `showIssuePanel` state. `onCreateIssue` calls backend `POST /api/matches/{id}/issues`. Issue list rendered inline via `useReviewSurface`.

#### A.4 ~~Wire `AnnotationList.tsx` + `ReviewToolbar.tsx`~~ ✅

`useReviewSurface` hook wired in App.tsx (manages annotations + issues state). `AnnotationList` and `ReviewToolbar` rendered in sidebar. Backend CRUD for annotations works end-to-end.

#### A.5 ~~Wire `useCoachAnalysis.ts`~~ ✅

Replaced 6 inline state vars (`llmThinking`, `llmResponse`, `llmProvider`, `tacticalReport`, `drillResponse`, `activeTab`) and `askLlm` callback with single `coach = useCoachAnalysis(...)` hook. Added `runtimeCapabilities` state. `useDashboardData` parked — no `DashboardPanel.tsx` yet.

---

### B. Backend — API Endpoints ✅ PARTIALLY DONE

#### B.1 ~~Annotation + Issue CRUD Endpoints~~ ✅

6 routes shipped: `GET/POST/DELETE` for `/api/matches/{id}/annotations` and `/api/matches/{id}/issues`. Storage uses JSON files per match (`annotations.json`, `issues.json`). 10 new tests in `test_annotations.py`. Total backend suite: **60 tests**.

#### B.2 ~~Add Dashboard Aggregation Endpoint~~ ✅ DONE

**Implemented** (`GET /api/aggregate/dashboard` + `DashboardPanel.tsx`):
- Backend: `GET /api/aggregate/dashboard` aggregates from existing `list_matches_with_analytics()` — no new schema, no storage changes
- Returns `DashboardSummary` (matchCount, avgPossession, avgMyTeamXg, avgEnemyXg, avgXgDiff, avgMyTeamSprints, avgEnemySprints, mostUsedFormation), `DashboardComparison` (last match vs previous, deltas for possession/xG/sprints), `trends[]` (one `SeasonTrendPoint` per match)
- Uses existing `useDashboardData` hook + `fetchDashboardData()` (path: `/api/aggregate/dashboard`)
- Frontend: `DashboardPanel.tsx` — modal with season summary cards, possession trend chart (last 12 matches), all-matches list, and last-match comparison with delta badges
- Last-N comparison mode (not rolling averages) — simpler and more interpretable per user guidance
- 5 new tests in `test_dashboard.py` (107 total backend tests)

**Verify**: Load 2+ completed matches → Dashboard button appears in toolbar → panel shows aggregated stats and trend chart

---

### C. Telestration / Drawing Tools on TacticalPitch ~~(Priority: MEDIUM)~~ ✅ DONE

This is the biggest missing UX feature — currently TacticalPitch is render-only with zero mouse interaction.

#### C.1 ~~Add Canvas Drawing Mode~~ ✅

**Implemented**:
- `TacticalPitch.tsx`: Added `DrawingMode` type, `drawingMode`/`savedAnnotations`/`onAnnotationCreate` props; mouse `onMouseDown/Move/Up` handlers for live preview; saved arrow (orange) + circle (cyan) annotations rendered after players; cursor changes to crosshair in draw mode
- `DrawingToolbar.tsx` (new): Arrow/Circle toggle buttons + Cancel; wired to `review.startArrowPlacement`/`startCirclePlacement`/`cancelPlacement`
- `App.tsx`: `drawingMode` state wired to TacticalPitch props; `handleDrawingStart`/`handleDrawingCancel`; DrawingToolbar rendered in sidebar
- `useReviewSurface`: `pitchAnnotationPlacementMode` used to distinguish arrow first-click (start) from second-click (end) for correct annotation creation

**Verify**: Select "Arrow" tool → click-drag on pitch → arrow renders → persists across frame changes ✅

---

### D. Trust Hardening — Remaining Gaps ~~(Priority: MEDIUM)~~ ✅ PARTIALLY DONE

#### D.1 ~~Wire `needs_review` Contract to Main~~ ✅ DONE

**Implemented**:
- `StatsPanel.tsx`: Amber warning banner at top when `stats.ballSignalStatus === 'untrusted'`
- `CoachInsights.tsx`: New `ballSignalStatus?: string | null` prop; disabled Generate Report + Training Drills buttons when untrusted; warning note
- `App.tsx`: Wired `matchStats?.ballSignalStatus` → CoachInsights prop

#### D.2 ~~Active Learning "Trust Crops" Prioritization~~ ✅ DONE

**Implemented** (`backend/app/trust_crops.py` + `GET /api/matches/{id}/trust-crops`):
- Heuristic-only scoring: ball teleport distance, track ID switch frequency, team flip rate, possession gaps
- No new schema fields needed — operates on existing `frames.json` + `ballAssignments` data
- Returns top-N uncertain windows sorted by score, with reason tags per crop
- 12 new unit tests (103 total backend tests)

**Backend API**: `GET /api/matches/{match_id}/trust-crops?limit=20` → `TrustCropsResponse` with `TrustCropSchema` entries containing `frameStart`, `frameEnd`, `timestampStart`, `timestampEnd`, `score`, `reasons[]`

**Verify**: Load a completed match → `GET /api/matches/{id}/trust-crops` returns scored crop windows

#### D.3 Automated Kinematic Validation

**How to approach**:
1. Add `backend/app/kinematic_validation.py` (~80 lines):
   - `validate_player_kinematics(frames)` — flag frames where:
     - Player speed exceeds 12 m/s (Usain Bolt threshold)
     - Player acceleration exceeds 4 m/s² sustained over 3+ frames
     - Player teleports > 5m between consecutive frames
   - `validate_ball_physics(frames)` — flag frames where:
     - Ball speed exceeds 50 m/s (hardest recorded shot ~51 m/s)
     - Ball changes direction > 90° without a player within 3m
2. Run as post-processing step after `detect_events()` in the pipeline
3. Violations get attached to the match as `MatchIssue` records with `bucket: 'kinematic_violation'`

**Files to create**: `backend/app/kinematic_validation.py` (~80 lines)
**Tests**: Add test with synthetic frame data containing impossible speeds

---

### E. Computer Vision Pipeline Gaps (Priority: LOW — Research-Heavy)

#### E.1 Automatic Field Calibration (§2 — currently ~50%)

**Status**: `pitch_detector.py` exists (~15KB) and is wired into `run_guerilla.py` with auto-first + manual-fallback. Auto-detection is attempted first; falls back to manual 4-point if detection confidence is low. GAP report was outdated on this item.

**Code review result**: PASS — the two-strategy approach (general pitch outline + penalty box fallback) is sound. The 0.3 score threshold is conservative and appropriate for a fallback system. Known failure modes: fisheye distortion, cropped pitch (only penalty area), and poor contrast. Verification requires test footage which is outside the scope of code review.

**Remaining work**: Verify auto-detection accuracy on diverse camera angles; consider adding line clustering + vanishing-point estimation for robustness on wide-angle footage.

#### E.2 Temporal Camera Smoothing (§2)

**How to approach**:
1. After computing homography per-frame (if doing per-frame recalibration), apply Savitzky-Golay filter to the 8 homography matrix elements across the time axis
2. `scipy.signal.savgol_filter(H_series, window=51, polyorder=3)` for each matrix element
3. Only relevant if/when per-frame recalibration is implemented (not needed for static camera)

**Files to modify**: `run_guerilla.py` (+20 lines)
**Dependency**: Requires automatic field calibration (E.1) first

#### E.3 3D Ball Trajectory (§1)

**How to approach**:
1. When ball is detected with high confidence across 10+ consecutive frames, fit a parabolic trajectory: `z(t) = z0 + v0*t - 0.5*g*t²`
2. Residuals from parabolic fit indicate whether ball is on ground (residual ≈ 0) or airborne
3. For airborne balls, project back through the inverse homography to correct for parallax
4. Use `scipy.optimize.curve_fit` with the parabolic model

**Files to create**: `backend/app/ball_trajectory.py` (~100 lines)
**Dependency**: Reliable ball detection across consecutive frames (§1 must be proven first)

#### E.4 OCR Improvement for Jersey Numbers (§4 — 66.7% bucket)

**How to approach**:
1. Crop tighter around detected player bounding boxes (top 40% = torso area)
2. Pre-process: convert to grayscale, apply CLAHE histogram equalization, threshold
3. Run PaddleOCR or EasyOCR on the processed crop
4. Filter: only accept 1-2 digit numeric results, reject if confidence < 0.7
5. Temporal voting: across a tracklet, take the mode of all OCR readings for that track ID

**Files to modify**: `run_guerilla.py` — expand the OCR section with preprocessing + temporal voting
**Verify**: Run on golden set → measure accuracy improvement on the 66.7% bucket

#### E.5 Deep ReID Embeddings for Team Assignment (§4)

**How to approach**:
1. Replace RGB clustering with OSNet-based appearance features:
   - Extract 512-dim embedding per player crop using `torchreid`
   - Cluster embeddings with K-Means (k=3: team A, team B, referee)
2. Fine-tune on a small set of labeled crops from the trust golden set
3. Use cosine similarity for re-identification across ID switches

**Libraries**: `torchreid` (pip install torchreid), or use `timm` with a pre-trained model
**Files to create**: `backend/app/appearance_reid.py` (~120 lines)
**Dependency**: GPU recommended; CPU inference possible but slow

---

### F. LLM & Intelligence Gaps (Priority: LOW)

#### F.1 RAG Architecture with Vector Database

**How to approach**:
1. Use ChromaDB (lightweight, embedded, Python-native):
   ```python
   import chromadb
   client = chromadb.PersistentClient(path=str(storage_root / "chroma"))
   collection = client.get_or_create_collection("match_context")
   ```
2. After each match analysis, embed the tactical report + event summary as documents
3. When generating new reports, query the collection for similar past matches as context
4. Add retrieved context to the LLM prompt as "Historical Reference" section

**Files to create**: `backend/app/vector_store.py` (~80 lines)
**Files to modify**: `llm.py` — add retrieval step before prompt building
**Dependency**: `pip install chromadb` (~50MB)

#### F.2 Hallucination Prevention

**How to approach**:
1. Post-process LLM output: validate that every player `trackId` referenced exists in the frame data
2. Validate that xG values cited match the computed values within ±0.05
3. Validate that formation strings match the `formationTimeline` data
4. If any validation fails, add `"needs_review": true` + `"validation_failures": [...]` to the response

**Files to modify**: `llm.py` — add `validate_llm_response(response, frames, analytics)` after LLM call

---

### G. Missing Tests ~~(Priority: ONGOING)~~ — **#1 Priority**

**Priority**: Should be #1, not "ongoing" — 4 modules at 0 tests is the biggest risk multiplier. `worker.py` and `jobs.py` are trivially testable (~50 lines combined).

| Module | Current Tests | What to Add |
|--------|:---:|-------------|
| `processor.py` | 18 ✅ | ~~processor unit tests~~ |
| `run_guerilla.py` | 5 ✅ | ~~build_homography_from_points~~ |
| `video_pipeline.py` | 4 ✅ | ~~Mock-based pipeline tests~~ |
| `worker.py` | 2 ✅ | ~~Job lifecycle~~ |
| `jobs.py` | 2 ✅ | ~~JobRunner~~ |
| `trust_crops.py` | 12 ✅ | ~~Trust crop heuristics~~ |

**Total backend suite: 110 tests** (18 processor + 12 trust_crops + 5 dashboard + 10 annotations + remaining modules) ✅

**Infrastructure**: `backend/tests/conftest.py` stubs cv2/pandas/ultralytics with DLT-based `findHomography` so `run_guerilla.py` can be imported in test environments without those packages.

---

### H. Remaining Stale Documentation (Priority: LOW)

All major doc issues resolved. Remaining minor items:

| Item | Location | Fix |
|------|----------|-----|
| §9 line 361: "Trust gating UI — ⚠️" | GAP-ANALYSIS §9 | ✅ Fixed — D.1 done, status updated |
| §9: "Telestration drawing missing" | GAP-ANALYSIS §9 | ✅ Fixed — C.1 done, DrawingToolbar wired |
| §8 Trust ~45% | GAP-ANALYSIS §8 | ✅ Fixed — ~55% after D.2 + TrustCropPanel |
| §9 Frontend ~75% | GAP-ANALYSIS §9 | ✅ Fixed — ~85% after C.1 |
| §G: processor.py 0 tests | GAP-ANALYSIS §G | ✅ Fixed — 18 new tests, 110 total |
| §2 Homography ~20% | GAP-ANALYSIS §2 | ✅ Fixed — ~50% after pitch_detector.py wired |
| §9 "Unmerged DashboardPanel" | GAP-ANALYSIS §9 | ✅ Fixed — DashboardPanel.tsx merged in App.tsx |
| `useDashboardData` parked note | GAP-ANALYSIS A.5 | ✅ Fixed — DashboardPanel.tsx built and wired |
| §9 "RetrievalWorkspacePanel unmerged" | GAP-ANALYSIS §9 | ✅ Fixed — documented as API-only, no UI |


---

## Conclusion

The current implementation represents a **trust-hardened, interactive football analysis system** at ~65-70% of the full research scope:

**Shipped (this session):**
- ✅ Interactive review surface — `PlayerDetailPanel` (click-to-select), `AnnotationList`, `ReviewToolbar`, `DemoMatchIssuePanel` all wired into App.tsx
- ✅ Timeline range selection — `Timeline.new.tsx` swapped in, review range start/end/clear working
- ✅ Backend annotation + issue CRUD — 6 new endpoints, 10 new tests (60 total backend)
- ✅ `useCoachAnalysis` hook — replaced 6 inline state vars and `askLlm` callback
- ✅ Full type system for review surface (ReviewRange, MatchIssue, TacticalAnnotation, RuntimeCapabilities)
- ✅ `needs_review` trust banner — amber warning in StatsPanel + disabled Generate buttons in CoachInsights (D.1)
- ✅ processor.py unit tests — 18 new tests covering `normalize_tracking_rows`, `_normalize_track_colors`, `_resolve_selected_cluster`, `_prepare_video_outputs` (78 total backend tests)
- ✅ Telestration drawing — Arrow + Circle drawing on TacticalPitch with DrawingToolbar, live preview, saved annotation rendering, wired via `useReviewSurface` (C.1)

**Remaining Gaps (ordered by impact):**
1. ~~Trust crop queue~~ — ✅ **Trust crops API + TrustCropPanel done** (D.2 complete)
2. ~~Dashboard~~ — ✅ **Dashboard API + panel done** (B.2)
3. **Camera calibration** — Code review passed; needs test footage validation (E.1)
4. **Ball tracking proof** — Fallback recovery needs canonical clip validation (Phase 1)
5. **RAG architecture** — No vector database for LLM grounding (F.1)
6. ~~Test coverage~~ — ✅ **All modules now tested** — processor (18), trust_crops (12), dashboard (7), annotations (10), run_guerilla (5), video_pipeline (4), worker (2), jobs (2), plus others — 110 total
7. **Real-footage OCR** — 66.7% bucket needs improvement (E.4)
8. **Deep ReID** — Appearance-based player matching (E.5)
