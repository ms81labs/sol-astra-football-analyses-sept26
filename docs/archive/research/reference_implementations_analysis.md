# Reference Implementations: Practical Fit Analysis

This is a mirror review of `docs/reference_implementations.md`, focused on one question:

> Will these suggestions materially improve our actual football-analysis results, or are they mostly engineering improvements?

The assessment below is based on the current code in:

- `backend/run_guerilla.py`
- `backend/app/analytics.py`
- `backend/app/homography_utils.py`
- `backend/app/team_classification.py`
- `backend/app/processor.py`
- `backend/app/main.py`
- `backend/app/storage.py`
- `backend/app/video_pipeline.py`
- `frontend/src/components/TacticalPitch.tsx`

---

## 1) Modular Architecture & Caching

### Reference suggestion
Split the pipeline into orchestrated modules and add persistent `.pkl`/stub caching so detection and tracking do not rerun during development.

### Current state in our repo
- We already have partial orchestration around the pipeline:
  - `backend/app/video_pipeline.py`
  - `backend/app/processor.py`
  - `backend/app/main.py`
- We already persist raw outputs and allow reprocessing without re-running detection for team-cluster selection:
  - `backend/app/storage.py`
  - `backend/app/processor.py`
- We do **not** currently cache YOLO/BoT-SORT inference results before the main tracking pass. `run_guerilla.py` still runs `model.track(...)` directly.

### Would this improve results?
Not directly.

This would mostly improve:
- developer iteration speed,
- reproducibility during experiments,
- operational convenience.

It would **not** by itself improve:
- detection quality,
- team assignment quality,
- possession quality,
- event quality,
- pitch mapping quality.

### Verdict
**Good engineering suggestion, weak direct accuracy suggestion.**

### Fit / caveat
The reference assumes a `tracks[entity][frame][track_id]` style pipeline. Our repo is built around:
- flat raw rows,
- normalized frames,
- `FrameData`,
- reprocessing from stored rows.

So the caching idea is compatible, but the full reference architecture should **not** be copied literally.

---

## 2) Camera Movement Estimation (Optical Flow)

### Reference suggestion
Use Lucas-Kanade optical flow to estimate camera motion and subtract it before speed/distance calculations.

### Current state in our repo
- We do **not** currently have optical-flow camera compensation.
- We instead mitigate camera drift through periodic homography recalculation:
  - `backend/run_guerilla.py`
- Homography is already central to our projection path:
  - `backend/app/homography_utils.py`

### Would this improve results?
**Possibly yes, but mainly for physical-motion metrics.**

This could improve:
- speed estimates,
- sprint counts,
- total distance,
- motion-based tactical interpretation.

This is much less likely to improve:
- team classification,
- pass detection,
- possession assignment,
- event attribution.

### Risks
- Optical flow works best when the footage contains stable non-pitch background features.
- Some of our clips may not have enough reliable background structure.
- If the background is weak or noisy, this could add instability instead of reducing it.
- Our current periodic homography refresh may be a better fit for some grassroots-style footage than the reference assumes.

### Verdict
**Potentially useful, but conditional rather than a guaranteed upgrade.**

### Practical value
If the goal is “better football understanding overall,” this is probably **not** the first thing to do.  
If the goal is “more believable speed and distance outputs,” it becomes much more valuable.

---

## 3) Perspective Transformation (Homography)

### Reference suggestion
Use homography to map video pixels into tactical pitch coordinates.

### Current state in our repo
This is already one of the core strengths of the current implementation.

- Shared homography helpers exist in:
  - `backend/app/homography_utils.py`
- Video processing uses homography projection already:
  - `backend/run_guerilla.py`
- The frontend pitch expects normalized projected coordinates:
  - `frontend/src/components/TacticalPitch.tsx`

### Would this improve results?
No meaningful gain from adopting the reference version as-is, because we already do this.

### Important mismatch
The reference examples use real-world meter coordinates directly. Our system is built around:
- `0..100` normalized pitch coordinates in backend processing,
- frontend mapping based on percentages,
- analytics thresholds written around that normalized contract and converted where needed.

Replacing our current approach with the reference contract would create unnecessary breakage.

### Verdict
**Already implemented. Not a real improvement opportunity.**

---

## 4) Team Assignment via K-Means Clustering

### Reference suggestion
Cluster jersey colors using the top half of the player crop, preferably in HSV, with dominant-color extraction.

### Current state in our repo
We already do torso-color sampling and clustering:
- `backend/run_guerilla.py` extracts torso patches
- `backend/app/team_classification.py` clusters track color vectors
- `backend/app/processor.py` and `backend/app/main.py` support cluster-based reprocessing

But our current feature extraction is relatively simple:
- mean torso RGB sample,
- no dominant-color isolation,
- no explicit background/grass rejection beyond the crop itself.

### Would this improve results?
**Yes — this is the strongest suggestion in the document.**

Team-label quality has a large downstream effect on:
- possession summaries,
- pass attribution,
- turnovers,
- PPDA / regain metrics,
- tactical summaries,
- any “my team vs enemy” analytics.

If team clustering is wrong, many downstream outputs look plausible but are structurally wrong.

### Why this reference is better than what we have
The reference approach is stronger because it tries to:
- focus on jersey area only,
- reduce contamination from shorts / socks / grass,
- separate background from player color,
- cluster in a color space that is usually more stable for jersey separation.

### Risks
- Similar kit colors can still fail.
- Lighting, shadows, compression, and goalkeeper/referee colors remain difficult.
- We should keep our current user-controlled `myTeamCluster` mapping behavior even if the clustering features improve.

### Verdict
**Best candidate here for materially better real-world results.**

---

## 5) Speed and Distance Estimation

### Reference suggestion
Compute speed and distance over a rolling window and attach smoothed per-track metrics.

### Current state in our repo
We already compute distance and top speed in the analytics layer:
- `backend/app/analytics.py`

The frontend also displays speed overlays:
- `frontend/src/components/TacticalPitch.tsx`

But the current approach is still relatively direct:
- frame-to-frame movement,
- limited smoothing,
- not attached as a persistent rolling metric per track in the reference style.

### Would this improve results?
**Moderately, but mostly presentation and metric stability.**

This could help:
- reduce noisy speed spikes,
- reduce false sprint inflation,
- improve visual credibility of speed overlays.

But without stronger camera-motion handling, the gains are limited.

### Verdict
**Useful second-order improvement, not a top-priority results upgrade.**

---

## Overall Ranking

## Strongest candidate for better results
1. **Team assignment robustness**

## Conditional / medium-value candidates
2. **Camera movement compensation**
3. **Smoothed speed and distance estimation**

## Mostly engineering / workflow value
4. **Modular orchestration + inference stub caching**

## Already effectively covered
5. **Perspective transform / homography**

---

## Bottom Line

If the goal is to improve **actual football-analysis quality**, the reference document is **not equally valuable across all suggestions**.

### Worth serious attention
- **Team assignment improvements** are the most likely to improve final output quality in a meaningful way.

### Worth exploring carefully
- **Camera compensation** could help motion metrics, but only if our footage quality and framing support it.

### Helpful but not transformative
- **Smoothed speed/distance** can make metrics more stable.

### Mostly non-result improvements
- **Architecture cleanup and caching** are good for workflow, but they will not meaningfully improve results by themselves.

### Not needed
- **Replacing our homography approach** with the reference version is unnecessary; we already have that capability in place.

---

## Final Recommendation

If we use this reference document to improve the system, the most rational interpretation is:

1. **Take the team-assignment ideas seriously.**
2. **Treat optical-flow camera compensation as an experiment, not an assumption.**
3. **Treat caching/orchestration as engineering hygiene, not as a results fix.**
4. **Do not rework homography just because the reference includes it.**
