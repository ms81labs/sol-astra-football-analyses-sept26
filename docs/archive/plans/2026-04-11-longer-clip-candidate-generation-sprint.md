# Longer-Clip Candidate Generation Sprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve longer-clip ball candidate generation so the 5-minute local calibration stops returning only edge-dominated, non-viable tracks.

**Architecture:** Keep the current bounded profile selector intact and move one layer upstream. The sprint should add candidate-source diagnostics, suppress repeated edge-anchor junk before profile scoring, and prefer temporally coherent in-field ball candidates near the active player window. Local 1-minute and 5-minute calibration remain the truth loop; remote Runpod proof stays blocked until the 5-minute local matrix yields at least one viable profile.

**Tech Stack:** Python, OpenCV, Ultralytics YOLO, pytest, ruff, existing `backend/run_guerilla.py` recovery harness, benchmark CLI scripts, markdown handoff docs.

---

## Scope And Guardrails

- This sprint does **not** change the frontend.
- This sprint does **not** add new detector families, training, Runpod images, or 45-minute proofs.
- This sprint does **not** widen the quality-matrix profile family again.
- Success means the 5-minute **local** matrix yields at least one viable profile.
- Honest failure means the 5-minute local matrix still returns `recommendedProfile = "no_viable_profile"`, but the new diagnostics clearly show which candidate families are poisoning the track.

## File Map

- Modify: `backend/run_guerilla.py`
  - Add richer candidate diagnostics and upstream suppression/filtering.
- Modify: `backend/tests/test_run_guerilla.py`
  - Add targeted unit coverage for candidate-family suppression and temporal candidate filtering.
- Modify: `backend/app/run_benchmarks.py`
  - Surface any newly useful high-signal recovery debug fields in the benchmark summary.
- Modify: `backend/tests/test_run_benchmarks.py`
  - Lock compact summary expectations for the new recovery debug fields.
- Modify: `backend/scripts/run_trimmed_ball_recovery_matrix.py`
  - Print the extra diagnostic summary cleanly for local sprint runs.
- Modify: `SESSION-HANDOFF.md`
  - Capture the sprint result and whether local 5-minute viability improved.
- Modify: `docs/superpowers/plans/2026-04-11-active-now-systematic-roadmap.md`
  - Record the result and whether Runpod remained blocked.

---

### Task 1: Add Candidate-Family Diagnostics

**Files:**
- Modify: `backend/run_guerilla.py`
- Test: `backend/tests/test_run_guerilla.py`

- [ ] **Step 1: Write the failing tests for candidate diagnostics**

```python
def test_summarize_recovered_ball_candidates_reports_anchor_and_center_bias():
    rows = [
        {
            "Frame_ID": 0,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 36.9,
            "Y": 96.8,
            "Conf": 0.31,
            "Source_X1": 100.0,
            "Source_Y1": 100.0,
            "Source_X2": 110.0,
            "Source_Y2": 110.0,
        },
        {
            "Frame_ID": 5,
            "Entity_Type": "ball",
            "Track_ID": -1,
            "X": 36.9,
            "Y": 96.8,
            "Conf": 0.33,
            "Source_X1": 101.0,
            "Source_Y1": 101.0,
            "Source_X2": 111.0,
            "Source_Y2": 111.0,
        },
    ]

    summary = run_guerilla.summarize_recovered_ball_candidates(rows, player_windows=None)

    assert summary["dominantAnchorCoord"] == [36.9, 96.8]
    assert summary["dominantAnchorShare"] == 1.0
    assert "meanSourceCenterY" in summary


def test_recovery_debug_payload_carries_candidate_family_summary():
    candidate_summary = run_guerilla.summarize_recovered_ball_candidates([], player_windows=None)
    assert "dominantAnchorCoord" in candidate_summary
    assert "dominantAnchorShare" in candidate_summary
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest backend/tests/test_run_guerilla.py -q -k 'anchor_and_center_bias or candidate_family_summary'`

Expected: FAIL because the new keys are not present yet.

- [ ] **Step 3: Extend candidate summaries with source-family signals**

```python
def summarize_recovered_ball_candidates(rows, player_windows=None, max_frame_gap=5):
    ...
    dominant_anchor_coord = None
    dominant_anchor_count = 0
    dominant_anchor_share = 0.0
    mean_source_center_y = 0.0
    mean_source_box_area = 0.0
    ...
    return {
        "candidateRows": len(candidate_rows),
        "uniqueFrames": len({int(row["Frame_ID"]) for row in candidate_rows}),
        "meanConfidence": round(confidence_sum / len(candidate_rows), 3),
        "edgeCandidateShare": round(edge_candidate_count / len(candidate_rows), 3),
        "nearPlayerWindowShare": round(near_player_window_count / len(candidate_rows), 3),
        "dominantAnchorCoord": dominant_anchor_coord,
        "dominantAnchorCount": dominant_anchor_count,
        "dominantAnchorShare": dominant_anchor_share,
        "meanSourceCenterY": mean_source_center_y,
        "meanSourceBoxArea": mean_source_box_area,
        "confidenceBands": confidence_bands,
        "segmentCount": len(segments),
        "longestSegmentFrames": longest_segment_frames,
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest backend/tests/test_run_guerilla.py -q -k 'anchor_and_center_bias or candidate_family_summary'`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/run_guerilla.py backend/tests/test_run_guerilla.py
git commit -m "feat: add recovery candidate family diagnostics"
```

### Task 2: Suppress Repeated Edge-Anchor Junk Before Selection

**Files:**
- Modify: `backend/run_guerilla.py`
- Test: `backend/tests/test_run_guerilla.py`

- [ ] **Step 1: Write the failing suppression tests**

```python
def test_filter_recovered_ball_rows_rejects_repeated_edge_anchor_cluster():
    rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 36.9, "Y": 96.8, "Conf": 0.31},
        {"Frame_ID": 5, "Entity_Type": "ball", "Track_ID": -1, "X": 36.9, "Y": 96.8, "Conf": 0.30},
        {"Frame_ID": 10, "Entity_Type": "ball", "Track_ID": -1, "X": 36.9, "Y": 96.8, "Conf": 0.29},
    ]

    filtered = run_guerilla.suppress_repeated_false_ball_clusters(rows)

    assert filtered == []


def test_filter_recovered_ball_rows_keeps_non_anchor_motion():
    rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 42.0, "Y": 51.0, "Conf": 0.31},
        {"Frame_ID": 5, "Entity_Type": "ball", "Track_ID": -1, "X": 46.0, "Y": 49.0, "Conf": 0.34},
        {"Frame_ID": 10, "Entity_Type": "ball", "Track_ID": -1, "X": 53.0, "Y": 47.0, "Conf": 0.32},
    ]

    filtered = run_guerilla.suppress_repeated_false_ball_clusters(rows)

    assert filtered == rows
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest backend/tests/test_run_guerilla.py -q -k 'repeated_edge_anchor_cluster or keeps_non_anchor_motion'`

Expected: FAIL because `suppress_repeated_false_ball_clusters(...)` does not exist yet.

- [ ] **Step 3: Implement a bounded false-cluster suppression pass**

```python
def suppress_repeated_false_ball_clusters(rows):
    ordered_rows = _best_ball_rows_by_frame(rows)
    if not ordered_rows:
        return []

    summary = summarize_ball_track_rows(ordered_rows)
    if (
        summary["dominantAnchorShare"] >= 0.25
        and summary["edgeFrameShare"] >= 0.7
        and summary["pathLength"] < 200.0
    ):
        anchor = tuple(summary["dominantAnchorCoord"] or [])
        return [
            row
            for row in ordered_rows
            if [round(float(row["X"]), 1), round(float(row["Y"]), 1)] != list(anchor)
        ]
    return ordered_rows
```

- [ ] **Step 4: Route recovered rows through suppression before profile scoring**

```python
recovered_rows = suppress_repeated_false_ball_clusters(recovered_rows)
candidate_summary = summarize_recovered_ball_candidates(
    recovered_rows,
    player_windows=profile_player_windows,
)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest backend/tests/test_run_guerilla.py -q -k 'repeated_edge_anchor_cluster or keeps_non_anchor_motion'`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/run_guerilla.py backend/tests/test_run_guerilla.py
git commit -m "feat: suppress repeated false ball anchor clusters"
```

### Task 3: Prefer Temporally Coherent Candidates Near Active Play

**Files:**
- Modify: `backend/run_guerilla.py`
- Test: `backend/tests/test_run_guerilla.py`

- [ ] **Step 1: Write the failing temporal filter tests**

```python
def test_select_meaningful_recovered_ball_rows_prefers_temporal_chain_near_player_windows():
    rows = [
        {"Frame_ID": 0, "Entity_Type": "ball", "Track_ID": -1, "X": 41.0, "Y": 52.0, "Conf": 0.28},
        {"Frame_ID": 5, "Entity_Type": "ball", "Track_ID": -1, "X": 46.0, "Y": 50.0, "Conf": 0.29},
        {"Frame_ID": 10, "Entity_Type": "ball", "Track_ID": -1, "X": 51.0, "Y": 48.0, "Conf": 0.30},
        {"Frame_ID": 15, "Entity_Type": "ball", "Track_ID": -1, "X": 36.9, "Y": 96.8, "Conf": 0.35},
    ]

    selected = run_guerilla.select_meaningful_recovered_ball_rows(rows, player_windows={})

    assert [row["Frame_ID"] for row in selected] == [0, 5, 10]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest backend/tests/test_run_guerilla.py -q -k 'temporal_chain_near_player_windows'`

Expected: FAIL because the selector does not yet prefer the coherent subchain strongly enough.

- [ ] **Step 3: Add a bounded coherence filter before final scoring**

```python
def select_meaningful_recovered_ball_rows(rows, player_windows=None):
    candidate_rows = filter_ball_rows_by_player_window_proximity(rows, player_windows)
    candidate_rows = suppress_repeated_false_ball_clusters(candidate_rows)
    segments = split_ball_rows_into_segments(candidate_rows, max_frame_gap=5)
    meaningful_segments = [
        segment for segment in segments
        if summarize_ball_track_rows(segment)["pathLength"] >= 20.0
    ]
    best_segment = max(
        meaningful_segments,
        key=lambda segment: score_ball_track_summary(summarize_ball_track_rows(segment)),
        default=[],
    )
    primary_rows = _best_ball_rows_by_frame(best_segment or candidate_rows)
    ...
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest backend/tests/test_run_guerilla.py -q -k 'temporal_chain_near_player_windows'`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/run_guerilla.py backend/tests/test_run_guerilla.py
git commit -m "feat: prefer temporally coherent recovered ball chains"
```

### Task 4: Expose The New Debug Signals In Local Benchmark Output

**Files:**
- Modify: `backend/app/run_benchmarks.py`
- Modify: `backend/tests/test_run_benchmarks.py`
- Modify: `backend/scripts/run_trimmed_ball_recovery_matrix.py`

- [ ] **Step 1: Write the failing benchmark output tests**

```python
def test_summarize_match_benchmark_includes_anchor_debug_fields(tmp_path):
    ...
    assert summary.recoveryDominantAnchorShare == 0.42
    assert summary.recoveryMeanSourceCenterY == 611.2


def test_run_trimmed_ball_recovery_matrix_serializes_anchor_debug_fields(monkeypatch, capsys):
    ...
    assert payload["profiles"][0]["candidateSummary"]["dominantAnchorShare"] == 0.42
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest backend/tests/test_run_benchmarks.py -q -k 'anchor_debug_fields'`

Expected: FAIL because the compact summary does not expose these fields yet.

- [ ] **Step 3: Surface only the high-signal new fields**

```python
class MatchBenchmarkSummary(BaseModel):
    ...
    recoveryDominantAnchorShare: float = 0.0
    recoveryMeanSourceCenterY: float = 0.0
```

```python
return {
    "name": name,
    "videoPath": str(video_path),
    "profiles": profiles,
    "recommendedProfile": recommended_name,
    "diagnosticFocus": {
        "bestProfile": profiles[0]["name"] if profiles else None,
        "bestDominantAnchorShare": profiles[0]["candidateSummary"]["dominantAnchorShare"] if profiles else 0.0,
    },
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest backend/tests/test_run_benchmarks.py -q -k 'anchor_debug_fields'`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/run_benchmarks.py backend/scripts/run_trimmed_ball_recovery_matrix.py backend/tests/test_run_benchmarks.py
git commit -m "feat: expose recovery anchor debug signals"
```

### Task 5: Re-Run The Local Decision Loop And Stop Honestly

**Files:**
- Runtime input: `/root/WorkSpace/fotball-analyst/.worktrees/videos/trimed-football-2-1minute.mp4`
- Runtime input: `/root/WorkSpace/fotball-analyst/videos/trimed-5min.mp4`
- Modify: `SESSION-HANDOFF.md`
- Modify: `docs/superpowers/plans/2026-04-11-active-now-systematic-roadmap.md`

- [ ] **Step 1: Re-run the 1-minute local calibration**

Run:

```bash
QT_QPA_PLATFORM=offscreen ./backend/venv/bin/python backend/scripts/run_trimmed_ball_recovery_matrix.py \
  --video-path /root/WorkSpace/fotball-analyst/.worktrees/videos/trimed-football-2-1minute.mp4 \
  --name smoke_1min_matrix
```

Expected:
- command completes
- at least one viable profile exists
- output includes `recommendedProfile`

- [ ] **Step 2: Re-run the 5-minute local calibration**

Run:

```bash
QT_QPA_PLATFORM=offscreen ./backend/venv/bin/python backend/scripts/run_trimmed_ball_recovery_matrix.py \
  --video-path /root/WorkSpace/fotball-analyst/videos/trimed-5min.mp4 \
  --name real_5min_matrix
```

Expected:
- command completes
- output includes `recommendedProfile`
- output includes candidate diagnostics per profile

- [ ] **Step 3: Record the decision in the docs**

```markdown
## Update — 2026-04-11 Candidate Generation Sprint

- 1-minute local matrix:
  - `recommendedProfile: "..."`
- 5-minute local matrix:
  - `recommendedProfile: "..."`
- decision:
  - remote proof remains blocked
  - or one more Runpod proof is now justified
```

- [ ] **Step 4: Apply the stop rule**

If the 5-minute result still says `recommendedProfile = "no_viable_profile"`:

- do **not** run Runpod
- write clearly that the next sprint must move upstream again

If the 5-minute result yields a viable profile:

- open one small Runpod serverless endpoint
- rerun the 1-minute remote smoke
- rerun the 5-minute remote proof
- delete the endpoint immediately after capture

- [ ] **Step 5: Commit**

```bash
git add SESSION-HANDOFF.md docs/superpowers/plans/2026-04-11-active-now-systematic-roadmap.md
git commit -m "docs: record candidate generation sprint outcome"
```

---

## Self-Review

### Spec Coverage

- Upstream candidate-generation focus: covered in Tasks 1-3.
- Keep bounded profile selector intact: covered by only modifying pre-selection candidate handling.
- Local 1-minute then 5-minute decision loop: covered in Task 5.
- No automatic remote proof unless local 5-minute improves: covered by the Task 5 stop rule.
- Persist and expose enough diagnostics to explain failure honestly: covered in Tasks 1 and 4.

### Placeholder Scan

- No `TODO`, `TBD`, or “handle appropriately” placeholders remain.
- Every task includes explicit files, commands, and expected outcomes.

### Type Consistency

- Diagnostics are named consistently around `dominantAnchorShare`, `dominantAnchorCoord`, and `meanSourceCenterY`.
- The plan preserves existing `recommendedProfile` and benchmark summary naming instead of inventing a second naming scheme.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-11-longer-clip-candidate-generation-sprint.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
