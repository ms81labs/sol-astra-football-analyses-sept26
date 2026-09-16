# Detector Fallback Quality Sprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve trimmed-clip ball coverage honestly by making fallback candidate selection segment-aware and edge-noise resistant, without reopening downstream analytics hacks.

**Architecture:** Keep the benchmark clip, analytics layer, and export surfaces stable. Work only in the detector/fallback seam in `backend/run_guerilla.py`, using the trimmed clip as the single truth benchmark. Add bounded helper functions, prove them with `test_run_guerilla.py`, then validate by rerunning the trimmed manual benchmark and selected-cluster probe.

**Tech Stack:** Python, pytest, YOLO/Ultralytics, local trimmed benchmark CLI, existing storage artifacts

---

## Status Update — Diagnostic Harness Landed

This plan's original segment-aware selector direction has been partially superseded.

What is now true in the root repo:

- the aggressive segment-aware selector variant was tested and reverted because it regressed coverage from `45 / 360` to `36 / 360`
- the root repo now has a bounded recovery-profile experiment harness in `backend/run_guerilla.py`
- fresh verification for the detector file now stands at:
  - `PYTHONPATH=. python3 -m pytest backend/tests/test_run_guerilla.py -q` -> `28 passed`

Newest detector takeaway:

- pre-edge-penalty profile probes showed that high-res full-frame recovery can inflate frame count while still being dominated by lower-boundary junk
- because of that, `summarize_ball_track_rows(...)` now reports `edgeFrameShare`
- `score_ball_track_summary(...)` now penalizes edge-dominated motion explicitly
- `ball_track_summary_is_viable(...)` now disqualifies edge-dominated profiles outright

Current viability read from the captured first probe:

- `baseline` -> viable
- `highres_same_conf` -> not viable
- `highres_low_conf` -> not viable
- `highres_player_window` -> not viable

Current best next move inside this sprint:

- do not reopen the reverted selector branch
- do not promote any of the first high-res variants into production
- move upstream to candidate-generation quality on the same trimmed clip

---

## Current Truth

Latest fresh manual rerun:

- clip: `/root/WorkSpace/fotball-analyst/.worktrees/videos/trimed-football-2-1minute.mp4`
- match: `1736b72a36ca4fb7913632adb5a88a92`
- `rawRowCount: 2290`
- `frameCount: 360`
- `withBallFrames: 45`
- `withBallRatio: 0.125`
- unresolved event mix: `{"recovery": 4}`

Selected-cluster probe on that same fresh rerun:

- cluster `0`:
  - `controlledPossessionFrames: 33`
  - `eventTypes: {"carry": 1, "pass": 2, "recovery": 4}`
  - `fiveMinuteTruthReady: false`
- cluster `1`:
  - `controlledPossessionFrames: 33`
  - `eventTypes: {"pass": 2, "recovery": 4}`

Root-cause evidence from the detector seam:

- recovered candidate rows: `85`
- recovered candidate unique frames: `57`
- selected recovered unique frames: `50`
- current selector is still dropping recoverable sampled frames
- dropped frames observed so far:
  - `150`, `380`, `390`, `460`, `1430`, `1435`, `1440`
- many dropped rows are still noisy edge-biased candidates, so this sprint must improve quality, not just inflate counts

Success criteria for this sprint:

- trimmed clip `withBallFrames` increases honestly from the current fresh floor of `45`
- resolved cluster `0` does not lose current event richness (`carry + pass + recovery`)
- no new analytics-only heuristics are introduced
- benchmark remains below `fiveMinuteTruthReady` unless the coverage ratios actually justify it

Non-goals:

- no longer clip validation yet
- no Runpod infrastructure work
- no frontend/export scope expansion
- no downstream possession/event hacks to compensate for detector weakness

---

### Task 1: Add Detector-Side Segment Diagnostics

**Files:**
- Modify: `backend/run_guerilla.py`
- Test: `backend/tests/test_run_guerilla.py`

- [ ] **Step 1: Write the failing test for recovered-frame segmentation**

Add a unit test to `backend/tests/test_run_guerilla.py` for a new helper named `split_ball_rows_into_segments(...)`.

Use this exact test shape:

```python
def test_split_ball_rows_into_segments_breaks_on_large_frame_gap():
    rows = [
        {"Frame_ID": 100, "Entity_Type": "ball", "Track_ID": -1, "X": 30.0, "Y": 40.0, "Conf": 0.20},
        {"Frame_ID": 105, "Entity_Type": "ball", "Track_ID": -1, "X": 32.0, "Y": 41.0, "Conf": 0.22},
        {"Frame_ID": 110, "Entity_Type": "ball", "Track_ID": -1, "X": 35.0, "Y": 42.0, "Conf": 0.24},
        {"Frame_ID": 220, "Entity_Type": "ball", "Track_ID": -1, "X": 80.0, "Y": 90.0, "Conf": 0.21},
        {"Frame_ID": 225, "Entity_Type": "ball", "Track_ID": -1, "X": 82.0, "Y": 91.0, "Conf": 0.23},
    ]

    segments = split_ball_rows_into_segments(rows, max_frame_gap=20)

    assert len(segments) == 2
    assert [row["Frame_ID"] for row in segments[0]] == [100, 105, 110]
    assert [row["Frame_ID"] for row in segments[1]] == [220, 225]
```

- [ ] **Step 2: Run the new test to verify it fails**

Run:

```bash
PYTHONPATH=. python3 -m pytest backend/tests/test_run_guerilla.py -k 'split_ball_rows_into_segments' -q
```

Expected:

- FAIL with `ImportError` or `NameError` because `split_ball_rows_into_segments` does not exist yet

- [ ] **Step 3: Write the minimal helper implementation**

In `backend/run_guerilla.py`, add a small helper that:

- keeps only ball rows
- orders them by `Frame_ID`
- starts a new segment whenever the frame gap exceeds `max_frame_gap`
- returns `list[list[dict]]`

Use this implementation shape:

```python
def split_ball_rows_into_segments(rows, max_frame_gap):
    ordered_rows = sorted(
        [row for row in rows if row.get("Entity_Type") == "ball"],
        key=lambda row: int(row["Frame_ID"]),
    )
    if not ordered_rows:
        return []

    segments = [[ordered_rows[0]]]
    for row in ordered_rows[1:]:
        previous_row = segments[-1][-1]
        if int(row["Frame_ID"]) - int(previous_row["Frame_ID"]) > int(max_frame_gap):
            segments.append([row])
        else:
            segments[-1].append(row)
    return segments
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
PYTHONPATH=. python3 -m pytest backend/tests/test_run_guerilla.py -k 'split_ball_rows_into_segments' -q
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add backend/run_guerilla.py backend/tests/test_run_guerilla.py
git commit -m "test: add recovered-ball segment diagnostics"
```

---

### Task 2: Make Fallback Selection Segment-Aware

**Files:**
- Modify: `backend/run_guerilla.py`
- Test: `backend/tests/test_run_guerilla.py`

- [ ] **Step 1: Write the failing test for keeping multiple meaningful segments**

Add a test to `backend/tests/test_run_guerilla.py` that proves `select_meaningful_recovered_ball_rows(...)` can keep more than one meaningful segment instead of collapsing the whole clip into one global choice.

Use this exact test shape:

```python
def test_select_meaningful_recovered_ball_rows_keeps_multiple_meaningful_segments():
    rows = [
        {"Frame_ID": 100, "Entity_Type": "ball", "X": 30.0, "Y": 40.0, "Conf": 0.21},
        {"Frame_ID": 105, "Entity_Type": "ball", "X": 34.0, "Y": 43.0, "Conf": 0.22},
        {"Frame_ID": 110, "Entity_Type": "ball", "X": 38.0, "Y": 46.0, "Conf": 0.23},
        {"Frame_ID": 220, "Entity_Type": "ball", "X": 70.0, "Y": 55.0, "Conf": 0.20},
        {"Frame_ID": 225, "Entity_Type": "ball", "X": 73.0, "Y": 58.0, "Conf": 0.21},
        {"Frame_ID": 230, "Entity_Type": "ball", "X": 77.0, "Y": 61.0, "Conf": 0.22},
    ]

    selected_rows = select_meaningful_recovered_ball_rows(rows)

    assert [row["Frame_ID"] for row in selected_rows] == [100, 105, 110, 220, 225, 230]
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
PYTHONPATH=. python3 -m pytest backend/tests/test_run_guerilla.py -k 'multiple_meaningful_segments' -q
```

Expected:

- FAIL because current selector treats the candidate set too globally

- [ ] **Step 3: Implement segment-aware recovered-ball selection**

Refactor `select_meaningful_recovered_ball_rows(...)` in `backend/run_guerilla.py` so it:

- filters by player-window proximity first
- splits candidates into segments using `split_ball_rows_into_segments(...)`
- runs the current meaningful-motion / static-cluster suppression logic per segment
- concatenates all meaningful segments in frame order

Keep the current static-cluster suppression logic, but scope it per segment instead of the whole clip.

Required behavior:

- if a segment already shows meaningful motion, keep its best-per-frame rows
- if a segment is static, try the existing alternate-cluster fallback only within that segment
- if a segment still fails meaningful motion, drop that segment

- [ ] **Step 4: Run the targeted selector tests**

Run:

```bash
PYTHONPATH=. python3 -m pytest backend/tests/test_run_guerilla.py -k 'select_meaningful_recovered_ball_rows or split_ball_rows_into_segments' -q
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add backend/run_guerilla.py backend/tests/test_run_guerilla.py
git commit -m "feat: make recovered-ball selection segment-aware"
```

---

### Task 3: Add Edge-Noise Rejection Guardrails

**Files:**
- Modify: `backend/run_guerilla.py`
- Test: `backend/tests/test_run_guerilla.py`

- [ ] **Step 1: Write the failing test for rejecting edge-hugging static junk segments**

Add a test to `backend/tests/test_run_guerilla.py` that proves a short static segment concentrated near the pitch edge gets dropped even if it has multiple frames.

Use this exact test shape:

```python
def test_select_meaningful_recovered_ball_rows_rejects_edge_hugging_static_segment():
    rows = [
        {"Frame_ID": 300, "Entity_Type": "ball", "X": 9.2, "Y": 91.5, "Conf": 0.08},
        {"Frame_ID": 305, "Entity_Type": "ball", "X": 9.3, "Y": 91.6, "Conf": 0.14},
        {"Frame_ID": 310, "Entity_Type": "ball", "X": 9.2, "Y": 91.6, "Conf": 0.09},
        {"Frame_ID": 400, "Entity_Type": "ball", "X": 40.0, "Y": 45.0, "Conf": 0.20},
        {"Frame_ID": 405, "Entity_Type": "ball", "X": 44.0, "Y": 47.0, "Conf": 0.21},
        {"Frame_ID": 410, "Entity_Type": "ball", "X": 49.0, "Y": 50.0, "Conf": 0.22},
    ]

    selected_rows = select_meaningful_recovered_ball_rows(rows)

    assert [row["Frame_ID"] for row in selected_rows] == [400, 405, 410]
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
PYTHONPATH=. python3 -m pytest backend/tests/test_run_guerilla.py -k 'edge_hugging_static_segment' -q
```

Expected:

- FAIL because current logic does not explicitly reject that edge-junk segment

- [ ] **Step 3: Implement the minimal edge-noise guard**

In `backend/run_guerilla.py`, add a small helper used only inside the recovered-ball selector that flags a segment as edge-noise when:

- the segment does not show meaningful motion
- and its average `X` or `Y` sits very near pitch bounds

Keep it deliberately narrow. For example:

```python
def recovered_segment_looks_like_edge_noise(rows, edge_margin=12.0):
    if not rows:
        return False
    if ball_rows_show_meaningful_motion(rows):
        return False
    avg_x = sum(float(row["X"]) for row in rows) / len(rows)
    avg_y = sum(float(row["Y"]) for row in rows) / len(rows)
    return (
        avg_x <= edge_margin
        or avg_x >= (PITCH_WIDTH - edge_margin)
        or avg_y <= edge_margin
        or avg_y >= (PITCH_HEIGHT - edge_margin)
    )
```

Then drop such segments before alternate-cluster promotion.

- [ ] **Step 4: Run the targeted tests**

Run:

```bash
PYTHONPATH=. python3 -m pytest backend/tests/test_run_guerilla.py -k 'edge_hugging_static_segment or select_meaningful_recovered_ball_rows' -q
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add backend/run_guerilla.py backend/tests/test_run_guerilla.py
git commit -m "feat: reject edge-hugging fallback ball noise"
```

---

### Task 4: Re-run the Trimmed Benchmark and Sync Truth Docs

**Files:**
- Modify: `SESSION-HANDOFF.md`
- Modify: `docs/superpowers/plans/2026-04-09-coverage-quality-sprint-plan.md`
- Modify: `docs/superpowers/plans/2026-04-08-event-richness-and-scale-up-plan.md`
- Modify: `docs/superpowers/plans/2026-04-08-gpu-adoption-execution-plan.md`

- [ ] **Step 1: Run the focused detector test slice**

Run:

```bash
PYTHONPATH=. python3 -m pytest backend/tests/test_run_guerilla.py -q
```

Expected:

- PASS

- [ ] **Step 2: Run a fresh trimmed manual rerun**

Run:

```bash
PYTHONPATH=. python3 backend/scripts/run_trimmed_clip_benchmark.py --rerun-manual
```

Record the fresh `matchId` and summary.

- [ ] **Step 3: Probe selected clusters on the fresh rerun**

Run:

```bash
PYTHONPATH=. python3 backend/scripts/run_trimmed_clip_benchmark.py --match-id <fresh_match_id> --probe-clusters
```

Expected:

- cluster `0` still preserves current event richness floor
- `withBallFrames` and `withBallRatio` either improve honestly, or we document that they did not

- [ ] **Step 4: Sync docs to verified truth only**

Update the docs listed above with:

- the fresh rerun match id
- the new `withBallFrames`
- the new `withBallRatio`
- selected-cluster `0` event mix
- whether `fiveMinuteTruthReady` changed
- a short statement of whether the detector sprint improved coverage materially

Do **not** claim success if the ratios stay flat.

- [ ] **Step 5: Commit**

```bash
git add SESSION-HANDOFF.md docs/superpowers/plans/2026-04-09-coverage-quality-sprint-plan.md docs/superpowers/plans/2026-04-08-event-richness-and-scale-up-plan.md docs/superpowers/plans/2026-04-08-gpu-adoption-execution-plan.md
git commit -m "docs: sync detector fallback sprint benchmark truth"
```

---

## Expected Outcome

After this sprint, one of two honest outcomes should be true:

1. The trimmed clip benchmark improves on `withBallFrames` and `withBallRatio`, while preserving the current resolved-team event richness floor.
2. The benchmark does **not** improve materially, and we can say with evidence that the next bottleneck is not selector logic anymore but candidate generation quality itself.

Either outcome is useful. What matters is that we stop guessing and keep the benchmark clip as the only truth surface.
