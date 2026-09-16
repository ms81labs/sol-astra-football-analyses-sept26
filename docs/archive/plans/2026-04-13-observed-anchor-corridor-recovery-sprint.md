# Observed-Anchor Corridor Recovery Sprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow truthful 5-minute coverage by generating better recovery candidates in gap frames using observed-ball source anchors plus player-window crops, then rerun the same selected-cluster local and remote proofs.

**Architecture:** Keep `observedBall`, `inferredBall`, `acceptedBall`, truth gates, and selected-cluster promotion unchanged. Improve only the recovery-generation path in `backend/run_guerilla.py` by adding an observed-anchor corridor crop mode, exposing corridor diagnostics in recovery summaries, and rerunning the normal local + managed-remote proof loop to see whether cleaner candidate generation can grow inferred continuity beyond the current `20` selected recovered frames.

**Tech Stack:** Python 3.12, OpenCV / Ultralytics YOLO, existing backend proof scripts, pytest, Ruff, Runpod serverless

---

## Why This Next

Fresh grounded evidence from the latest serverless proof match `e23846e0141145dea3941ecb05b7c7b9` says:

- selected cluster recommendation is still `1`
- post-selection truth is still effectively stuck at:
  - `acceptedBallFrames=101`
  - `controlledPossessionFrames=98`
  - `ballTrackEdgeFrameShare=0.812`
  - `ballTrackViable=false`
- recovery still only contributes `20` selected inferred frames
- the winning recovery profile is still `width_cap_075`
- continuity diagnostics are now visible and still show fragmentation:
  - `collapsedCandidateFrames=220`
  - `collapsedSegmentCount=73`
  - `collapsedLongestSegmentFrames=12`

That means the next best lever is no longer scoring or selector tuning. It is candidate generation that can search the right source-space corridor inside gaps between already-observed ball anchors.

## Recommended Approach

### Option A: More recovery scoring tweaks

- Keep the current recovery profiles and change only ranking.
- Low upside because the current anchor-weighted scorer is already selecting the cleanest profile it sees.
- Rejected for this batch.

### Option B: Add generic wider / narrower crop variants only

- Extend `build_ball_recovery_quality_matrix_profiles()` with a few more width / edge / upper-band combinations.
- Safer than new logic, but likely too shallow because the current matrix already explored several static crop shapes and still settled on `width_cap_075`.
- Useful fallback, but not recommended as the main batch.

### Option C: Add observed-anchor corridor crop windows

- Build recovery crop windows for gap frames using neighboring observed-ball source anchors, then intersect or fall back with the player window.
- This stays detector-side, targets truthful mid-field candidate generation directly, and preserves the existing scoring/truth contract.
- **Recommended**.

## File Map

### Core detector work

- Modify: `backend/run_guerilla.py`
  - add observed-anchor source extraction
  - add anchor-corridor crop-window builder
  - allow `recover_ball_rows(...)` to use per-frame crop windows from a provider
  - add new recovery profiles that use anchor-corridor crop windows
  - extend recovery candidate summaries with corridor diagnostics

### Summary surfaces

- Modify: `backend/app/run_benchmarks.py`
  - expose additive recovery-corridor fields in compact benchmark summaries
- Modify: `backend/scripts/run_local_app_path_proof.py`
  - include the new summary fields in compact proof JSON
- Modify: `backend/scripts/run_remote_app_path_proof.py`
  - include the new summary fields in compact proof JSON

### Tests

- Modify: `backend/tests/test_run_guerilla.py`
  - add unit coverage for anchor-corridor crop generation and recovery integration
- Modify: `backend/tests/test_run_benchmarks.py`
  - add summary-field coverage
- Modify: `backend/tests/test_run_local_app_path_proof.py`
  - add compact-proof field coverage
- Modify: `backend/tests/test_run_remote_app_path_proof.py`
  - add compact-proof field coverage

### Runtime closeout

- Modify: `SESSION-HANDOFF.md`
- Modify: `docs/superpowers/plans/2026-04-11-active-now-systematic-roadmap.md`

## Execution Topology

Use `superpowers:subagent-driven-development`, sequentially on the critical path.

1. Task 1 implementer subagent
   Add observed-anchor corridor crop generation and recovery candidate diagnostics in `backend/run_guerilla.py`
2. Task 1 spec reviewer subagent
3. Task 1 code-quality reviewer subagent

4. Task 2 implementer subagent
   Wire benchmark/proof summary fields and tests in:
   - `backend/app/run_benchmarks.py`
   - `backend/scripts/run_local_app_path_proof.py`
   - `backend/scripts/run_remote_app_path_proof.py`
   - backend tests
5. Task 2 spec reviewer subagent
6. Task 2 code-quality reviewer subagent

7. Task 3 implementer subagent
   Run local proof, managed remote proof, selected-cluster promotions, compare traces, update docs
8. Task 3 spec reviewer subagent
9. Task 3 quality/reality reviewer subagent

No parallel implementers before Task 1 is settled. The summary field names and crop-window contract must lock first.

### Task 1: Observed-Anchor Corridor Candidate Generation

**Files:**
- Modify: `backend/run_guerilla.py`
- Test: `backend/tests/test_run_guerilla.py`

- [ ] **Step 1: Write the failing tests for anchor-corridor crop generation**

Add tests like:

```python
def test_build_anchor_corridor_window_interpolates_between_neighboring_observed_source_boxes():
    observed_anchors = {
        100: {"sourceCenter": (200.0, 120.0)},
        110: {"sourceCenter": (280.0, 140.0)},
    }
    player_window = (140, 60, 360, 260)

    window = build_anchor_corridor_crop_window(
        frame_shape=(720, 1280, 3),
        frame_id=105,
        observed_source_anchors=observed_anchors,
        player_window=player_window,
        corridor_half_width_px=80,
        corridor_padding_px=32,
    )

    assert window is not None
    left, top, right, bottom = window
    assert left < 240 < right
    assert top < 130 < bottom
    assert right - left <= 320
```

```python
def test_build_anchor_corridor_window_falls_back_to_player_window_when_only_one_anchor_exists():
    observed_anchors = {
        100: {"sourceCenter": (200.0, 120.0)},
    }
    player_window = (160, 80, 340, 240)

    window = build_anchor_corridor_crop_window(
        frame_shape=(720, 1280, 3),
        frame_id=105,
        observed_source_anchors=observed_anchors,
        player_window=player_window,
        corridor_half_width_px=80,
        corridor_padding_px=32,
    )

    assert window is not None
    left, top, right, bottom = window
    assert left >= 0
    assert top >= 0
    assert right <= 1280
    assert bottom <= 720
```

```python
def test_profile_recovery_cache_key_distinguishes_anchor_corridor_mode():
    player_window_profile = {
        "name": "width_cap_075",
        "settings": {"imgsz": 1600, "conf": 0.08},
        "usePlayerWindows": True,
        "maxCropWidthRatio": 0.75,
    }
    anchor_corridor_profile = {
        "name": "anchor_corridor_075",
        "settings": {"imgsz": 1600, "conf": 0.08},
        "usePlayerWindows": True,
        "cropMode": "anchor_corridor",
        "maxCropWidthRatio": 0.75,
    }

    assert _profile_recovery_cache_key(player_window_profile) != _profile_recovery_cache_key(anchor_corridor_profile)
```

- [ ] **Step 2: Run the focused detector tests and verify RED**

Run:

```bash
cd /root/WorkSpace/fotball-analyst
PYTHONPATH=/root/WorkSpace/fotball-analyst python3 -m pytest backend/tests/test_run_guerilla.py -q
```

Expected: FAIL on missing corridor helper / missing `observed_source_anchors` support.

- [ ] **Step 3: Implement minimal observed-anchor corridor generation**

Add these helpers in `backend/run_guerilla.py`:

```python
def collect_observed_source_anchors(rows):
    anchors = {}
    for row in rows:
        if row.get("Entity_Type") != "ball":
            continue
        if not all(key in row for key in ("Source_X1", "Source_Y1", "Source_X2", "Source_Y2")):
            continue
        frame_id = int(row["Frame_ID"])
        center_x = (float(row["Source_X1"]) + float(row["Source_X2"])) / 2.0
        center_y = (float(row["Source_Y1"]) + float(row["Source_Y2"])) / 2.0
        anchors[frame_id] = {
            "sourceCenter": (center_x, center_y),
            "sourceBox": (
                float(row["Source_X1"]),
                float(row["Source_Y1"]),
                float(row["Source_X2"]),
                float(row["Source_Y2"]),
            ),
        }
    return anchors


def build_anchor_corridor_crop_window(
    frame_shape,
    frame_id,
    observed_source_anchors,
    player_window,
    *,
    corridor_half_width_px,
    corridor_padding_px,
):
    frame_height, frame_width = frame_shape[:2]
    previous_anchor = max((fid for fid in observed_source_anchors if fid < frame_id), default=None)
    next_anchor = min((fid for fid in observed_source_anchors if fid > frame_id), default=None)
    if previous_anchor is None and next_anchor is None:
        return ball_recovery_crop_window(frame_shape, player_window)
    if previous_anchor is None or next_anchor is None:
        anchor_frame = previous_anchor if previous_anchor is not None else next_anchor
        center_x, center_y = observed_source_anchors[anchor_frame]["sourceCenter"]
    else:
        left_center = observed_source_anchors[previous_anchor]["sourceCenter"]
        right_center = observed_source_anchors[next_anchor]["sourceCenter"]
        span = max(next_anchor - previous_anchor, 1)
        position = (frame_id - previous_anchor) / span
        center_x = left_center[0] + ((right_center[0] - left_center[0]) * position)
        center_y = left_center[1] + ((right_center[1] - left_center[1]) * position)
    left = max(0, int(round(center_x - corridor_half_width_px - corridor_padding_px)))
    right = min(frame_width, int(round(center_x + corridor_half_width_px + corridor_padding_px)))
    top = max(0, int(round(center_y - corridor_half_width_px)))
    bottom = min(frame_height, int(round(center_y + corridor_half_width_px + corridor_padding_px)))
    return (left, top, right, bottom)
```

Update `recover_ball_rows(...)` to support:

```python
def recover_ball_rows(
    video_path,
    model,
    H,
    pitch_points,
    fps,
    frame_interval,
    player_windows=None,
    recovery_imgsz=None,
    recovery_conf=None,
    crop_edge_margin=0,
    max_crop_center_y_ratio=0.0,
    max_crop_width_ratio=0.0,
    crop_windows_by_frame=None,
):
    if crop_windows_by_frame is not None:
        crop_window = crop_windows_by_frame.get(frame_count)
    elif player_windows is not None:
        crop_window = ball_recovery_crop_window(
            frame.shape,
            player_windows.get(frame_count),
            max_crop_width_ratio=max_crop_width_ratio,
        )
    else:
        crop_window = None
```

Update `run_ball_recovery_experiment(...)` signature to accept:

```python
def run_ball_recovery_experiment(
    video_path,
    model,
    H,
    pitch_points,
    fps,
    frame_interval,
    imgsz,
    conf,
    player_windows=None,
    player_rows=None,
    profiles=None,
    observed_source_anchors=None,
):
```

Add a new internal profile toggle such as:

```python
"cropMode": "anchor_corridor"
```

and use it to build `crop_windows_by_frame` from the observed anchors + player windows.

- [ ] **Step 4: Add candidate diagnostics for the new corridor mode**

Extend candidate summaries with additive fields:

```python
candidate_summary.update(
    {
        "corridorCandidateFrames": len(
            {int(row["Frame_ID"]) for row in recovered_rows if row.get("RecoveryCropMode") == "anchor_corridor"}
        ),
        "corridorFramesWithTwoAnchors": int(corridor_debug["framesWithTwoAnchors"]),
        "corridorFramesWithSingleAnchor": int(corridor_debug["framesWithSingleAnchor"]),
        "corridorMeanWidth": float(corridor_debug["meanCorridorWidth"]),
    }
)
```

Keep the current fields intact:
- `collapsedCandidateFrames`
- `collapsedSegmentCount`
- `collapsedLongestSegmentFrames`
- `continuityPreferredFrames`
- `continuityRejectedFrames`
- `midfieldCollapsedFrames`

- [ ] **Step 5: Run the focused detector tests and verify GREEN**

Run:

```bash
cd /root/WorkSpace/fotball-analyst
PYTHONPATH=/root/WorkSpace/fotball-analyst python3 -m pytest backend/tests/test_run_guerilla.py -q
```

Expected: PASS

- [ ] **Step 6: Commit Task 1**

```bash
cd /root/WorkSpace/fotball-analyst
git add backend/run_guerilla.py backend/tests/test_run_guerilla.py
git commit -m "feat: add observed-anchor corridor recovery generation"
```

### Task 2: Proof Summary Surfaces

**Files:**
- Modify: `backend/app/run_benchmarks.py`
- Modify: `backend/scripts/run_local_app_path_proof.py`
- Modify: `backend/scripts/run_remote_app_path_proof.py`
- Test: `backend/tests/test_run_benchmarks.py`
- Test: `backend/tests/test_run_local_app_path_proof.py`
- Test: `backend/tests/test_run_remote_app_path_proof.py`

- [ ] **Step 1: Write the failing summary-field tests**

Add tests like:

```python
def test_match_benchmark_summary_exposes_anchor_corridor_fields():
    summary = summarize_match_benchmark(storage, match_id)
    assert summary.corridorCandidateFrames == 42
    assert summary.corridorFramesWithTwoAnchors == 16
    assert summary.corridorFramesWithSingleAnchor == 8
    assert summary.corridorMeanWidth == 184.0
```

```python
def test_remote_compact_summary_includes_anchor_corridor_fields():
    payload = _compact_summary(summary_model)
    assert payload["corridorCandidateFrames"] == 42
    assert payload["corridorFramesWithTwoAnchors"] == 16
```

- [ ] **Step 2: Run the summary tests and verify RED**

Run:

```bash
cd /root/WorkSpace/fotball-analyst
PYTHONPATH=/root/WorkSpace/fotball-analyst python3 -m pytest \
  backend/tests/test_run_benchmarks.py \
  backend/tests/test_run_local_app_path_proof.py \
  backend/tests/test_run_remote_app_path_proof.py -q
```

Expected: FAIL on missing benchmark / compact-summary fields.

- [ ] **Step 3: Implement the additive summary fields**

In `backend/app/run_benchmarks.py`, add the corridor fields to the summary model and benchmark builder:

```python
corridorCandidateFrames: int = 0
corridorFramesWithTwoAnchors: int = 0
corridorFramesWithSingleAnchor: int = 0
corridorMeanWidth: float = 0.0
```

In both proof scripts, extend `_compact_summary(...)` with:

```python
"corridorCandidateFrames": payload.get("corridorCandidateFrames", 0),
"corridorFramesWithTwoAnchors": payload.get("corridorFramesWithTwoAnchors", 0),
"corridorFramesWithSingleAnchor": payload.get("corridorFramesWithSingleAnchor", 0),
"corridorMeanWidth": payload.get("corridorMeanWidth", 0.0),
```

- [ ] **Step 4: Run the summary tests and verify GREEN**

Run:

```bash
cd /root/WorkSpace/fotball-analyst
PYTHONPATH=/root/WorkSpace/fotball-analyst python3 -m pytest \
  backend/tests/test_run_benchmarks.py \
  backend/tests/test_run_local_app_path_proof.py \
  backend/tests/test_run_remote_app_path_proof.py -q
```

Expected: PASS

- [ ] **Step 5: Lint touched files**

Run:

```bash
cd /root/WorkSpace/fotball-analyst
./backend/venv/bin/python -m ruff check \
  backend/run_guerilla.py \
  backend/app/run_benchmarks.py \
  backend/scripts/run_local_app_path_proof.py \
  backend/scripts/run_remote_app_path_proof.py \
  backend/tests/test_run_guerilla.py \
  backend/tests/test_run_benchmarks.py \
  backend/tests/test_run_local_app_path_proof.py \
  backend/tests/test_run_remote_app_path_proof.py
```

Expected: `All checks passed!`

- [ ] **Step 6: Commit Task 2**

```bash
cd /root/WorkSpace/fotball-analyst
git add \
  backend/app/run_benchmarks.py \
  backend/scripts/run_local_app_path_proof.py \
  backend/scripts/run_remote_app_path_proof.py \
  backend/tests/test_run_benchmarks.py \
  backend/tests/test_run_local_app_path_proof.py \
  backend/tests/test_run_remote_app_path_proof.py
git commit -m "feat: surface anchor corridor recovery diagnostics"
```

### Task 3: Runtime Proof Loop And Closeout

**Files:**
- Modify: `SESSION-HANDOFF.md`
- Modify: `docs/superpowers/plans/2026-04-11-active-now-systematic-roadmap.md`

- [ ] **Step 1: Run the fresh local proof**

Run:

```bash
cd /root/WorkSpace/fotball-analyst
LOCAL_SUMMARY="$(QT_QPA_PLATFORM=offscreen ./backend/venv/bin/python \
  backend/scripts/run_local_app_path_proof.py \
  --include-selected-clusters)"
echo "$LOCAL_SUMMARY"
export LOCAL_SUMMARY
LOCAL_MATCH_ID="$(python3 - <<'PY'
import json
import os
print(json.loads(os.environ["LOCAL_SUMMARY"])["savedMatchId"])
PY
)"
```

Expected: emits compact proof JSON with the new corridor fields and a saved local match id.

- [ ] **Step 2: Run selected-cluster promotion on the fresh local match**

Run:

```bash
cd /root/WorkSpace/fotball-analyst
QT_QPA_PLATFORM=offscreen ./backend/venv/bin/python \
  backend/scripts/promote_selected_cluster_for_proof.py \
  --match-id "$LOCAL_MATCH_ID"
```

Expected: recommended cluster applies cleanly and emits updated benchmark summary.

- [ ] **Step 3: Run the fresh managed remote proof**

Run:

```bash
cd /root/WorkSpace/fotball-analyst
export RUNPOD_API_KEY="$(python3 - <<'PY'
import tomllib
from pathlib import Path
cfg = tomllib.loads(Path('/root/.runpod/config.toml').read_text())
print(cfg['api_key'])
PY
)"
export AWS_ACCESS_KEY_ID='user_3BaoU7L715q2H6lTCM3S07kjQtL'
export AWS_SECRET_ACCESS_KEY='rps_YDDKQF2M4QJ9XER6BUL7X53Y8IKI7QTBL891XEO21x0igt'
export RUNPOD_OBJECT_STORAGE_BUCKET='c7d2d4q0ik'
export RUNPOD_OBJECT_STORAGE_ENDPOINT_URL='https://s3api-eur-is-1.runpod.io'
export RUNPOD_OBJECT_STORAGE_REGION='eur-is-1'
REMOTE_SUMMARY="$(QT_QPA_PLATFORM=offscreen ./backend/venv/bin/python \
  backend/scripts/run_managed_remote_app_path_proof.py \
  --transport auto \
  --gpu-id 'NVIDIA H100 80GB HBM3' \
  --workers-min 1 \
  --workers-max 1 \
  --poll-interval-seconds 5 \
  --timeout-seconds 7200)"
echo "$REMOTE_SUMMARY"
export REMOTE_SUMMARY
REMOTE_MATCH_ID="$(python3 - <<'PY'
import json
import os
print(json.loads(os.environ["REMOTE_SUMMARY"])["savedMatchId"])
PY
)"
```

Expected: managed remote proof completes and deletes the endpoint.

- [ ] **Step 4: Run selected-cluster promotion on the fresh remote match**

Run:

```bash
cd /root/WorkSpace/fotball-analyst
QT_QPA_PLATFORM=offscreen ./backend/venv/bin/python \
  backend/scripts/promote_selected_cluster_for_proof.py \
  --match-id "$REMOTE_MATCH_ID"
```

Expected: recommended cluster applies cleanly and emits updated benchmark summary.

- [ ] **Step 5: Compare local vs remote traces**

Run:

```bash
cd /root/WorkSpace/fotball-analyst
QT_QPA_PLATFORM=offscreen ./backend/venv/bin/python \
  backend/scripts/compare_ball_pipeline_trace.py \
  --left-match-id "$LOCAL_MATCH_ID" \
  --right-match-id "$REMOTE_MATCH_ID"
```

Expected: parity drift, if any, is identified explicitly by stage.

- [ ] **Step 6: Evaluate success bar**

Count the sprint as a win if post-selection we achieve any of:

```text
acceptedBallFrames >= 120 with supportedAcceptedBallRatio >= 0.95
recoveredSelectedFrames >= 35
controlledPossessionFrames >= 110
ballTrackViable == true
```

Record exactly one binary outcome:

```text
observed-anchor corridor materially improved truthful coverage
observed-anchor corridor did not materially improve the 5-minute truth gates
```

- [ ] **Step 7: Update handoff and roadmap immediately**

Update:

- `SESSION-HANDOFF.md`
- `docs/superpowers/plans/2026-04-11-active-now-systematic-roadmap.md`

with:

- fresh local match id
- fresh remote match id
- post-selection metrics
- parity note
- binary outcome
- exact next implication

- [ ] **Step 8: Confirm cleanup**

Run:

```bash
export RUNPOD_API_KEY="$(python3 - <<'PY'
import tomllib
from pathlib import Path
cfg = tomllib.loads(Path('/root/.runpod/config.toml').read_text())
print(cfg['api_key'])
PY
)"
runpodctl serverless list -o json
```

Expected: `[]`

- [ ] **Step 9: Commit Task 3**

```bash
cd /root/WorkSpace/fotball-analyst
git add SESSION-HANDOFF.md docs/superpowers/plans/2026-04-11-active-now-systematic-roadmap.md
git commit -m "docs: record anchor corridor recovery sprint outcome"
```

## Success Bar

After selected-cluster promotion, count this sprint as a win if any of these happen:

- `acceptedBallFrames >= 120` while `supportedAcceptedBallRatio >= 0.95`
- `recoveredSelectedFrames >= 35`
- `controlledPossessionFrames >= 110`
- `ballTrackViable == true`

## Guardrails

Do not change in this batch:

- truth-gate thresholds
- detector family
- clip length
- selected-cluster promotion contract
- `observedBall` / `inferredBall` / `acceptedBall` semantics
- frontend behavior

## Assumptions

- keep the current probe suppression behavior intact
- keep the current serverless parity image line unless the batch requires a new handler image
- keep explicit selected-cluster promotion in the loop
- treat the main remaining blocker as insufficient truthful candidate generation inside mid-field gaps, not runtime, team selection, or truth-threshold strictness
