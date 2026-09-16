# Pilot Reference Interval Materialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Materialize bounded official pitch-position and ball-state references for the frozen `117092` and `117093` validation intervals without loading full XML files or overstating them as image-box/manual truth.

**Architecture:** A single standard-library CLI reads the pilot manifest, streams official SoccerTrack XML with `ElementTree.iterparse`, and writes gzip JSON Lines plus a canonical summary. It selects rows by absolute `matchTime`, enriches player IDs from the official metadata XML, and records hashes/counts back in the readiness inventory.

**Tech Stack:** Python 3.12 standard library, pytest, JSON Lines, gzip, XML iterparse.

**Spec:** `docs/reports/2026-09-13-football-analysis-readiness.md`

## Global Constraints

- Use only the two validation matches; do not open `118575` labels.
- Do not count pitch-position references as visible-ball boxes, image-space MOT truth, or completed manual-label minutes.
- Keep memory bounded with `ElementTree.iterparse` and `elem.clear()`.
- Add no dependency and no runtime-default change.

---

### Task 1: Bounded reference extractor

**Files:**
- Create: `backend/scripts/materialize_football_analysis_pilot_reference_intervals.py`
- Test: `backend/tests/test_materialize_football_analysis_pilot_reference_intervals.py`

**Interfaces:**
- Consumes: `materialize_reference_intervals(source_id: str, tracker_xml: Path, metadata_xml: Path, intervals: list[list[float]], output_path: Path) -> dict[str, object]`
- Produces: gzip JSON Lines with one frame object per selected XML frame and a summary containing frame/entity/ball counts and SHA-256.

- [x] **Step 1: Write the failing tests**

Test a miniature XML containing first-half, second-half, outside-window, malformed-location, and extra-period frames. Assert interval boundary behavior, metadata enrichment, ball preservation, extra-period exclusion, deterministic gzip payload content after decompression, and rejected overlapping/invalid intervals.

- [x] **Step 2: Run RED**

Run: `python3 -m pytest -q backend/tests/test_materialize_football_analysis_pilot_reference_intervals.py`

Expected: import failure because the extractor does not exist.

- [x] **Step 3: Implement the minimum extractor**

Use `ET.parse(metadata_xml)` only for the small metadata file. Validate sorted non-overlapping positive intervals. Stream `tracker_xml`; accept only `FIRST_HALF` and `SECOND_HALF`; include frames where `start <= matchTime / 1000 < end`; parse finite `[x,y]` locations; attach player metadata; write canonical compact JSON records through `gzip.GzipFile(..., mtime=0)`; return counts and the compressed-file SHA-256.

- [x] **Step 4: Run GREEN**

Run: `python3 -m pytest -q backend/tests/test_materialize_football_analysis_pilot_reference_intervals.py`

Expected: all tests pass.

### Task 2: Materialize and publish evidence

**Files:**
- Modify: `backend/benchmark_suites/football_analysis_pilot_corpus.json`
- Modify: `docs/reports/2026-09-13-football-analysis-readiness.md`
- Modify: `docs/status/current.md`

**Interfaces:**
- Consumes: Task 1 CLI and the frozen intervals for `soccertrack-v2-117092` and `soccertrack-v2-117093`.
- Produces: two ignored `.jsonl.gz` reference files and tracked hashes/counts/limitations.

- [x] **Step 1: Run the extractor for both validation sources**

Write outputs below each source's ignored pilot storage directory. Require exactly 300 selected seconds per source, no held-out source access, and nonzero player and ball rows.

- [x] **Step 2: Record exact evidence**

Add source file IDs/hashes, output hashes, frame/entity/ball counts, `manualLabelMinutesCompleted: 0`, `imageBoundingBoxesPresent: false`, and `heldOutLabelsAccessed: false` to the pilot inventory. Correct the report/status to explain that raw tracker XML is pitch-coordinate truth, not MOT boxes.

- [x] **Step 3: Verify and commit**

Run the focused extractor test, JSON validation, manifest assertions, canonical verifier, evidence writer, operational-doc tests, and build-only preflight. Commit a fresh source → metadata → evidence chain.
