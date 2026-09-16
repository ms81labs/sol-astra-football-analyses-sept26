# Reordered Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** reorder the remaining `fotball-analyst` roadmap around current repo reality so we build the highest-value next slices first without blocking on research-heavy foundation work.

**Architecture:** keep the current FastAPI + SQLite/local-artifact backbone as the canonical analytics source, continue extending backend-derived metrics first, and only then deepen the UI around those trusted payloads. Split the remaining work into three lanes: immediate tactical intelligence, trust-hardening research tracks, and coach/product experience.

**Tech Stack:** FastAPI, Pydantic, SQLite, React/Vite/TypeScript, Vitest, Pytest, local LLM providers, Ultralytics-based video pipeline.

---

## Why The Old Order No Longer Fits

The original roadmap assumed we were still at the prototype stage. We are not anymore. The repo already has:

- API + persistence
- video ingestion with manual homography
- team clustering and team selection
- canonical possession, events, formations, xG, and defensive-line metrics
- API-backed frontend playback and analysis panels

That means the remaining roadmap should no longer be ordered strictly as “all foundation first, then all intelligence, then all UX.” Some “foundation” items like jersey OCR and auto-homography are still important, but they are now better treated as parallel hardening tracks rather than blockers for every next analytics feature.

## Reordered Program

### Lane A: Immediate Build Lane

This is the main execution lane. These items build directly on the backend contracts we already trust and give the fastest product value.

1. **Pressing Analytics**
   - PPDA
   - defensive actions in the attacking half
   - counterpress recovery time
   - basic press-phase detection

2. **Richer Event Intelligence**
   - through-balls
   - interceptions
   - clearances / forced recoveries
   - event-level defensive pressure tags

3. **Player Performance Profiles v2**
   - pass involvement quality
   - pressing contribution
   - shot quality contribution
   - positioning discipline / shape deviation

4. **LLM Upgrade On Derived Context**
   - prompts use event summaries, formation phases, xG, pressing, and defensive-line metrics
   - reports reference evidence rather than sampled-frame guesses

### Lane B: Coach Workflow Lane

This lane should start once Lane A has at least pressing + richer event context available.

5. **Video Synchronization**
   - side-by-side synced video and pitch
   - timeline click jumps both video and pitch

6. **Interactive Review Surface**
   - time-range selection
   - tactical annotations
   - click player for profile

7. **Match Report Export**
   - PDF/HTML report generation
   - embed metrics, events, xG, formations, defensive-shape, pressing, and LLM summaries

8. **Multi-Match Dashboard**
   - season trends
   - opponent scouting rollups
   - player development snapshots

### Lane C: Trust-Hardening Research Lane

These are important, but should run as bounded validation tracks so they do not freeze the main product lane.

9. **Auto-Homography Evaluation And Integration**
   - benchmark against manual fallback
   - only ship as default if it beats manual on validation clips

10. **Jersey OCR + Roster Linkage**
   - torso crop extraction
   - track-level aggregation
   - confidence-gated roster matching

11. **Review Queue / Active Learning**
   - collect low-confidence detections and OCR crops
   - browser review flow
   - reprocess / fine-tune loop later

### Lane D: Platform And Future Work

These should stay out of the near-term critical path.

12. **Mobile/PWA polish**
13. **Runtime optimization / TensorRT**
14. **Real-time mode**
15. **Multi-camera stitching**
16. **Voice query workflow**

## Recommended Execution Order

This is the order I recommend we actually build from here:

1. `Pressing analytics`
2. `Richer event intelligence`
3. `Player profiles v2`
4. `LLM upgrade on derived context`
5. `Video synchronization`
6. `Interactive review surface`
7. `Match report export`
8. `Auto-homography validation`
9. `Jersey OCR validation`
10. `Multi-match dashboard`
11. `Active learning queue`
12. `Performance / future initiatives`

## What We Should Build Next

The next concrete implementation plan should be:

### Pressing Analytics Plan

**Why first**

- it builds directly on the event + possession layer we already have
- it raises the value of reports immediately
- it strengthens later player profiles and opponent analysis
- it does not require OCR or auto-homography to start

**Minimal first slice**

- backend summary fields for:
  - `myTeamPpda`
  - `enemyPpda`
  - `myTeamHighPressRegains`
  - `enemyHighPressRegains`
  - `myTeamCounterpressRecoverySeconds`
  - `enemyCounterpressRecoverySeconds`
- API returns those values in the canonical analytics payload
- stats/report UI surfaces them in a coach-readable way
- LLM report prompt consumes them as evidence

## Stop Treating Everything As One Plan

The remaining work should be split into separate implementation plans, one per slice:

- `pressing-analytics`
- `richer-event-intelligence`
- `player-profiles-v2`
- `video-sync`
- `report-export`
- `auto-homography-validation`
- `jersey-ocr-validation`

That keeps each plan executable, testable, and small enough to ship cleanly.

## Immediate Decision

If we keep cooking inline, the next slice to implement should be `pressing analytics`.
