# Event Richness And Scale-Up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current trimmed-clip Runpod proof from `recovery-only, no controlled possession` into a richer, export-worthy event stream focused on resolved-team event richness and controlled possession. The current lane is quality work, not a truthful `5-10 minute` or `45-minute` proof run.

**Architecture:** Keep the existing local API, storage, and Runpod job contract unchanged. Improve quality in narrow slices at the analytics/event layer first, then prove the same contract on a slightly longer segment before widening to a full half. The point is to improve the quality of the saved `JSON` artifacts without introducing fake team certainty or LLM-generated measurements.

**Tech Stack:** Python, FastAPI, SQLite, Runpod serverless, YOLO/BoT-SORT, pytest, JSON artifact storage

**Runpod Cost Rule:** Do not assume a live endpoint exists. The previous endpoint was intentionally deleted to avoid idle spend. When remote validation is needed, create or resume one small serverless endpoint, run the proof, then scale back to zero or delete it again.

---

## Current Truth

- Current saved trimmed benchmark floor:
  - `rawRowCount: 2291`
  - `frameCount: 360`
  - `withBallFrames: 46`
  - `trackedPossessionFrames: 33`
  - `controlledPossessionFrames: 33`
  - `eventCount: 7`
  - `eventTypes: {"recovery": 4, "pass": 2, "carry": 1}`
  - `fiveMinuteTruthReady: false`
  - `fortyFiveMinuteTruthReady: false`
  - `requiresTeamSelection: false`
  - `myTeamCluster: 0`
- This is enough to prove the remote pipeline and artifact contract.
- This is **not** enough yet for truthful `5-10 minute` analytics or a `45-minute` half in the app.

## Progress Update

- Neutral carry / progression guardrails were implemented locally and kept:
  - no carry on stationary or backward unresolved regain
  - no fake turnover when the same track resolves from `unassigned -> my_team/enemy`
- Resolved-team carry is now also live in narrow form:
  - same-player, multi-frame controlled segments can emit `carry`
  - only when the resolved owner advances meaningfully
  - stationary or backward resolved control stays silent
- Verification:
  - `PYTHONPATH=. python3 -m pytest backend/tests/test_analytics.py backend/tests/test_run_benchmarks.py backend/tests/test_export_flatteners.py -q` -> `40 passed`
- Honest outcome:
  - current saved match `217d5baf5cdb40dd985d8b466c126264` is now persisted with cluster selection:
    - `withBallFrames: 46`
    - `trackedPossessionFrames: 33`
    - `controlledPossessionFrames: 33`
    - `eventCount: 7`
    - `eventTypes: {"recovery": 4, "pass": 2, "carry": 1}`
    - `eventFamilyCount: 3`
    - `fiveMinuteTruthReady: false`
    - `fortyFiveMinuteTruthReady: false`
  - so the guardrail + suppression work plus short dead-ball bridging materially improved correctness and unlocked a real `recovery + pass + carry` floor
  - selected-cluster probe command now exists for the same saved match:
    - `PYTHONPATH=. python3 backend/scripts/run_trimmed_clip_benchmark.py --match-id 217d5baf5cdb40dd985d8b466c126264 --probe-clusters`
  - probe outcomes:
    - cluster `0` yields `controlledPossessionFrames: 33` and `eventTypes: {"recovery": 4, "pass": 2, "carry": 1}`
    - cluster `1` yields `controlledPossessionFrames: 33` and `eventTypes: {"recovery": 4, "pass": 2}`
  - cluster `0` now clears the event-richness gate; the remaining blockers are ball/control coverage ratios
  - so the next seam is no longer pure event taxonomy; it is coverage quality
- CSV export floor is now shipped:
  - `backend/app/export_flatteners.py`
  - `GET /api/matches/{match_id}/export/frames.csv`
  - `GET /api/matches/{match_id}/export/events.csv`
  - verified by:
    - `PYTHONPATH=. python3 -m pytest backend/tests/test_export_flatteners.py backend/tests/test_api.py -k 'test_flatten_ or test_match_import_lifecycle_from_tracking_json' -q` -> `3 passed`

## Scale-Up Rules

### What Can Scale Now

- Backend/runtime smoke runs on longer clips
- Raw artifact persistence:
  - `raw_rows.json`
  - `frames.json`
  - `events.json`
  - `analytics.json`
- Team-selection workflow after processing

### What Must Improve Before Truthful Longer Runs

- Ball coverage:
  - before truthful `5-10 minute` analytics: `withBallFrames / frameCount >= 25%`
  - before a `45-minute` half: `>= 40%`
- Controlled possession coverage after team selection:
  - before truthful `5-10 minute` analytics: `my_team|enemy possession frames / frameCount >= 20%`
  - before a `45-minute` half: `>= 30%`
- Event richness:
  - before truthful `5-10 minute` analytics: at least `3` event families with at least one of `pass` or `turnover`
  - no single event type should exceed `80%` of the total
  - before a `45-minute` half: require `pass + turnover + one of shot/tackle/interception`
- Player/team coverage:
  - before truthful `5-10 minute` analytics: average `8-10` classified players per frame
  - before a `45-minute` half: average `10-12+`
- Derived metric sanity:
  - both teams must have non-zero defensive-line / team-length style metrics
  - formation output must be non-degenerate

### What Must Wait

- Coach-facing tactical reports
- Drills / LLM recommendations grounded in match metrics
- Passing network / shot map conclusions
- Full `45-minute` app-open validation

### Task 1: Freeze The Current Trimmed-Clip Truth

**Files:**
- Modify: `SESSION-HANDOFF.md`
- Modify: `docs/superpowers/plans/2026-04-08-gpu-adoption-execution-plan.md`
- Test: `backend/tests/test_run_benchmarks.py`

- [ ] **Step 1: Replace stale 9-recovery language with the current benchmark truth**

Document the live baseline from match `217d5baf5cdb40dd985d8b466c126264`:

```text
rawRowCount: 2291
frameCount: 360
withBallFrames: 46
trackedPossessionFrames: 41
controlledPossessionFrames: 0
eventCount: 4
eventTypes: {"recovery": 4}
shotCount: 0
requiresTeamSelection: true
endpoint: k7lorgvsa017bv
image: docker.io/ms81vs/fotball-analyst-runpod-handler:neutral-events-v1
```

Treat any earlier `9`-recovery wording in this plan as stale.

- [ ] **Step 2: Verify benchmark tests still pass before building on this baseline**

Run: `cd /root/WorkSpace/fotball-analyst && PYTHONPATH=. python3 -m pytest backend/tests/test_run_benchmarks.py -q`

Expected: `2 passed`

- [ ] **Step 3: Commit the baseline truth sync**

```bash
git add SESSION-HANDOFF.md docs/superpowers/plans/2026-04-08-gpu-adoption-execution-plan.md
git commit -m "docs: freeze remote trimmed clip event baseline"
```

### Task 2: Convert Recovery-Only Into Resolved-Team Event Richness First

**Files:**
- Modify: `backend/app/analytics.py`
- Modify: `backend/tests/test_analytics.py`
- Test: `backend/tests/test_analytics.py`

- [ ] **Step 1: Write the failing tests for controlled possession and resolved-team event richness**

Add tests for these exact behaviors:

```python
def test_detect_events_emits_neutral_carry_after_short_loose_gap_for_same_unassigned_track():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 24.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [
                {"id": 7, "x": 23.0, "y": 50.0, "confidence": 0.92},
                {"id": 11, "x": 40.0, "y": 50.0, "confidence": 0.92},
            ],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": None,
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [
                {"id": 7, "x": 29.0, "y": 50.0, "confidence": 0.92},
            ],
        },
        {
            "frameId": 2,
            "timestamp": 0.4,
            "ball": {"x": 42.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [],
            "enemies": [],
            "unassignedPlayers": [
                {"id": 7, "x": 42.0, "y": 50.0, "confidence": 0.92},
            ],
        },
    ]

    assignments = assign_ball_possession(frames)
    events = detect_events(frames, assignments)

    assert [event.type for event in events] == ["recovery", "carry"]
    assert events[0].team == "unassigned"
    assert events[0].toTrackId == 7
    assert events[1].team == "unassigned"
    assert events[1].fromTrackId == 7


def test_detect_events_does_not_emit_neutral_carry_for_stationary_or_backward_signal():
    ...
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `cd /root/WorkSpace/fotball-analyst && PYTHONPATH=. python3 -m pytest backend/tests/test_analytics.py -k "controlled_possession or resolved_team_richness" -q`

Expected: `FAIL` because the current benchmark still has `controlledPossessionFrames: 0` and needs richer resolved-team events

- [ ] **Step 3: Implement the smallest safe neutral chain-stitching logic**

Constrain changes to neutral unresolved-player cases only:

```python
# sketch only - keep final implementation aligned with existing segment logic
PLAYER_CONTROL_TEAMS = {"my_team", "enemy", "unassigned"}

# in detect_events(...)
# 1. stitch very short dead_ball/contested gaps when the same unresolved track regains control
# 2. emit a neutral carry/progression event only when the stitched chain advances meaningfully
# 3. keep neutral event extras narrow: no cross / through-ball / tackle / interception inflation
# 4. keep team labels unresolved; do not map these to my_team or enemy
```

- [ ] **Step 4: Run the targeted analytics tests again**

Run: `cd /root/WorkSpace/fotball-analyst && PYTHONPATH=. python3 -m pytest backend/tests/test_analytics.py -k "neutral_carry or neutral_progression or neutral_events_for_unassigned" -q`

Expected: `PASS`

- [ ] **Step 5: Run the full analytics suite**

Run: `cd /root/WorkSpace/fotball-analyst && PYTHONPATH=. python3 -m pytest backend/tests/test_analytics.py -q`

Expected: full analytics suite passes

- [ ] **Step 6: Commit the bounded neutral progression slice**

```bash
git add backend/app/analytics.py backend/tests/test_analytics.py
git commit -m "feat: stitch neutral unresolved control into progression events"
```

### Task 3: Re-run The Trimmed Clip And Record The Next Event Floor

**Files:**
- Modify: `SESSION-HANDOFF.md`
- Modify: `docs/superpowers/plans/2026-04-08-gpu-adoption-execution-plan.md`
- Test: `backend/scripts/run_trimmed_clip_benchmark.py`

- [ ] **Step 1: Reprocess the latest local trimmed benchmark if only analytics changed**

Run:

```bash
cd /root/WorkSpace/fotball-analyst
PYTHONPATH=. python3 - <<'PY'
from backend.app.storage import Storage
from backend.app.processor import reprocess_video_match
storage = Storage('/root/WorkSpace/fotball-analyst/backend/storage')
reprocess_video_match(storage, '7cf0f28d0b7946fc8362d816fca7553b')
print('reprocessed')
PY
```

Expected: `reprocessed`

- [ ] **Step 2: If trimmed local result improves, build and push a new Runpod image**

Use a fresh tag, for example:

```bash
docker build -t docker.io/ms81vs/fotball-analyst-runpod-handler:event-bridge-v1 -f /root/WorkSpace/fotball-analyst/backend/runpod_handler/Dockerfile /root/WorkSpace/fotball-analyst
docker push docker.io/ms81vs/fotball-analyst-runpod-handler:event-bridge-v1
```

- [ ] **Step 3: Point the active template at the new image**

Run:

```bash
HOME=/tmp/runpod-home RUNPOD_API_KEY='...' ~/.local/bin/runpodctl template update aw37g71srz --image 'docker.io/ms81vs/fotball-analyst-runpod-handler:event-bridge-v1' --env '{"MODE_TO_RUN":"serverless","AWS_ACCESS_KEY_ID":"...","AWS_SECRET_ACCESS_KEY":"...","RUNPOD_OBJECT_STORAGE_BUCKET":"c7d2d4q0ik","RUNPOD_OBJECT_STORAGE_ENDPOINT_URL":"https://s3api-eur-is-1.runpod.io","RUNPOD_OBJECT_STORAGE_REGION":"eur-is-1"}'
```

- [ ] **Step 4: Run one real remote `/api/matches` upload of the trimmed clip**

Use the same manual calibration payload and the same endpoint `k7lorgvsa017bv`.

Expected success floor:

```text
withBallFrames >= 46
eventCount > 9
jobStatus = completed
matchStatus = ready
requiresTeamSelection = true
```

- [ ] **Step 5: Sync the new remote baseline in the handoff docs**

Capture:
- match id
- job id
- run id
- raw rows
- frames
- with-ball frames
- event count
- event types

- [ ] **Step 6: Commit the baseline upgrade**

```bash
git add SESSION-HANDOFF.md docs/superpowers/plans/2026-04-08-gpu-adoption-execution-plan.md
git commit -m "docs: update trimmed clip event-rich remote baseline"
```

### Task 4: Add A Flattened Export Floor For The App And CSV Consumers

**Files:**
- Create: `backend/app/export_flatteners.py`
- Create: `backend/tests/test_export_flatteners.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_export_flatteners.py`
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: Write the failing flattener tests**

Add tests for two exports:

```python
def test_flatten_frames_for_csv_export():
    frames = [
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 40.0, "y": 50.0, "confidence": 0.9},
            "possession": {"team": "unassigned", "trackId": 11, "distance": 3.1},
        }
    ]

    rows = flatten_frames_for_csv(frames)

    assert rows == [
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ballX": 40.0,
            "ballY": 50.0,
            "ballConfidence": 0.9,
            "possessionTeam": "unassigned",
            "possessionTrackId": 11,
        }
    ]


def test_flatten_events_for_csv_export():
    events = [
        {
            "type": "pass",
            "frameId": 10,
            "timestamp": 2.0,
            "team": "unassigned",
            "fromTrackId": 7,
            "toTrackId": 11,
            "description": "Pass from #7 to #11",
        }
    ]

    rows = flatten_events_for_csv(events)
    assert rows[0]["type"] == "pass"
    assert rows[0]["team"] == "unassigned"
```

- [ ] **Step 2: Run the flattener tests to verify they fail**

Run: `cd /root/WorkSpace/fotball-analyst && PYTHONPATH=. python3 -m pytest backend/tests/test_export_flatteners.py -q`

Expected: failure because file/functions do not exist yet

- [ ] **Step 3: Implement a narrow export helper**

Create:

```python
def flatten_frames_for_csv(frames: list[dict]) -> list[dict]:
    ...

def flatten_events_for_csv(events: list[dict]) -> list[dict]:
    ...
```

Keep it schema-driven and dumb. No analytics logic inside export helpers.

- [ ] **Step 4: Add one API route to download flattened events or frames**

Example shape:

```python
@app.get("/api/matches/{match_id}/export/events.csv")
async def export_match_events_csv(match_id: str):
    ...
```

Use existing local storage artifacts as the source, not recomputation.

- [ ] **Step 5: Run flattener and targeted API tests**

Run:
- `cd /root/WorkSpace/fotball-analyst && PYTHONPATH=. python3 -m pytest backend/tests/test_export_flatteners.py -q`
- `cd /root/WorkSpace/fotball-analyst && PYTHONPATH=. python3 -m pytest backend/tests/test_api.py -k "export.*csv or matches.*export" -q`

Expected: both pass

- [ ] **Step 6: Commit the export floor**

```bash
git add backend/app/export_flatteners.py backend/tests/test_export_flatteners.py backend/app/main.py backend/tests/test_api.py
git commit -m "feat: add flattened csv export floor for match artifacts"
```

### Task 5: Prove A 5–10 Minute Segment Before Any 45-Minute Half

**Files:**
- Modify: `backend/app/run_benchmarks.py`
- Modify: `backend/scripts/run_trimmed_clip_benchmark.py`
- Modify: `SESSION-HANDOFF.md`
- Test: `backend/tests/test_run_benchmarks.py`

- [ ] **Step 1: Extend the benchmark helper to support named benchmark clips**

Add a simple benchmark pack contract:

```python
class BenchmarkClip(BaseModel):
    name: str
    path: str
    mode: str
```

Start with:
- current trimmed clip
- one manually selected 5–10 minute segment

- [ ] **Step 2: Add a saved summary command for the longer segment**

Expected output fields stay:
- `rawRowCount`
- `frameCount`
- `withBallFrames`
- `eventCount`
- `eventTypes`
- `shotCount`
- `requiresTeamSelection`

- [ ] **Step 3: Define the go/no-go gates for running the longer segment**

Do not run the longer segment as a truthful analytics proof unless the trimmed clip remote proof reaches at least:

```text
withBallFrames / frameCount >= 25%
eventCount >= 12
at least 3 event families
at least one of pass or turnover present
no single event type > 80% of events
no remote job contract regressions
```

Operational smoke runs are allowed before those gates if the goal is runtime / artifact persistence only.

- [ ] **Step 4: Run benchmark tests**

Run: `cd /root/WorkSpace/fotball-analyst && PYTHONPATH=. python3 -m pytest backend/tests/test_run_benchmarks.py -q`

Expected: pass

- [ ] **Step 5: Commit the scale-up gate**

```bash
git add backend/app/run_benchmarks.py backend/scripts/run_trimmed_clip_benchmark.py backend/tests/test_run_benchmarks.py SESSION-HANDOFF.md
git commit -m "feat: add benchmark pack and scale-up gates"
```

### Task 6: Explicit 45-Minute Half Decision

**Files:**
- Modify: `SESSION-HANDOFF.md`
- Modify: `docs/superpowers/plans/2026-04-08-gpu-adoption-execution-plan.md`

- [ ] **Step 1: Record the decision rule**

Only greenlight a `45-minute` half when all are true:

```text
trimmed clip remote result has 3+ event families
trimmed clip remote result has non-zero pass or turnover events
trimmed clip remote result has withBallFrames / frameCount >= 40%
trimmed clip remote result has controlled my_team|enemy possession / frameCount >= 30%
5–10 minute segment completes successfully
5–10 minute segment keeps non-zero ball and event output
5–10 minute segment keeps event diversity above the same trimmed-clip gates
CSV/JSON export floor is working from saved artifacts
```

- [ ] **Step 2: Record the anti-goal**

Do not run a `45-minute` half merely because serverless works. Running a longer segment with weak event richness is just producing bigger weak JSON.

- [ ] **Step 3: Commit the decision gate**

```bash
git add SESSION-HANDOFF.md docs/superpowers/plans/2026-04-08-gpu-adoption-execution-plan.md
git commit -m "docs: add 45 minute half decision gate"
```
