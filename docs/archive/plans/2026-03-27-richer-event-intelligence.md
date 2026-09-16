# Richer Event Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** extend the existing derived event engine with `through_ball` and `interception` while preserving the current event contract and timeline/report visibility.

**Architecture:** keep the backend event engine in `backend/app/analytics.py` as the single source of truth, add narrow helper heuristics near the existing `pass` / `turnover` / `tackle` logic, and allow the frontend to consume the new event types through the existing API mapping path. This slice is intentionally additive: no new endpoint, no event-payload redesign, no UI rebuild.

**Tech Stack:** FastAPI, Pydantic, SQLite/local JSON artifacts, React/Vite/TypeScript, Pytest, Vitest.

---

## File Structure

- Modify: `/root/WorkSpace/fotball-analyst/backend/app/analytics.py`
  Purpose: add narrow heuristics for `through_ball` and `interception`
- Modify: `/root/WorkSpace/fotball-analyst/backend/tests/test_analytics.py`
  Purpose: backend regression coverage for the new event heuristics
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/types/index.ts`
  Purpose: extend the visible event type union
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/utils/api.ts`
  Purpose: preserve the new backend event types when mapping to timeline tags
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/utils/api.test.ts`
  Purpose: frontend regression coverage for the visible event mapping

## Task 1: Add Backend Tests For `through_ball`

**Files:**
- Modify: `/root/WorkSpace/fotball-analyst/backend/tests/test_analytics.py`

- [ ] **Step 1: Write the failing test**

```python
def test_detect_events_emits_through_ball_for_progressive_line_breaking_pass():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 48.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [
                {"id": 8, "x": 48.0, "y": 50.0, "confidence": 0.92},
                {"id": 11, "x": 76.0, "y": 52.0, "confidence": 0.92},
            ],
            "enemies": [
                {"id": 3, "x": 58.0, "y": 45.0, "confidence": 0.9},
                {"id": 4, "x": 63.0, "y": 55.0, "confidence": 0.9},
            ],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 76.0, "y": 52.0, "confidence": 0.95},
            "myTeam": [
                {"id": 8, "x": 50.0, "y": 50.0, "confidence": 0.92},
                {"id": 11, "x": 76.0, "y": 52.0, "confidence": 0.92},
            ],
            "enemies": [
                {"id": 3, "x": 59.0, "y": 45.0, "confidence": 0.9},
                {"id": 4, "x": 64.0, "y": 55.0, "confidence": 0.9},
            ],
        },
    ]

    assignments = assign_ball_possession(frames)
    events = detect_events(frames, assignments)

    assert [event.type for event in events] == ["pass", "through_ball"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests/test_analytics.py::test_detect_events_emits_through_ball_for_progressive_line_breaking_pass -q
```

Expected: FAIL because `through_ball` is not emitted yet.

- [ ] **Step 3: Write minimal implementation**

Add helper logic in `/root/WorkSpace/fotball-analyst/backend/app/analytics.py`:

```python
def _is_forward_progression(team: str, start_x: float, end_x: float, minimum_progress: float = 12.0) -> bool:
    if team == "my_team":
        return (end_x - start_x) >= minimum_progress
    return (start_x - end_x) >= minimum_progress


def _is_advanced_target(team: str, x: float) -> bool:
    if team == "my_team":
        return x >= 70
    return x <= 30


def _count_broken_lines(team: str, passer_x: float, receiver_x: float, opponents: list[PlayerData]) -> int:
    if team == "my_team":
        lower, upper = sorted((passer_x, receiver_x))
        return sum(1 for player in opponents if lower < player.x < upper)
    lower, upper = sorted((receiver_x, passer_x))
    return sum(1 for player in opponents if lower < player.x < upper)
```

Then inside the existing same-team pass branch:

```python
opponents = current_frame.enemies if current_segment.start.team == "my_team" else current_frame.myTeam
if (
    previous_position is not None
    and current_position is not None
    and _is_forward_progression(current_segment.start.team, previous_position[0], current_position[0])
    and _is_advanced_target(current_segment.start.team, current_position[0])
    and _count_broken_lines(current_segment.start.team, previous_position[0], current_position[0], opponents) >= 1
):
    events.append(
        DetectedEvent(
            type="through_ball",
            frameId=current_segment.start.frameId,
            timestamp=current_segment.start.timestamp,
            team=current_segment.start.team,
            fromTrackId=previous_segment.end.trackId,
            toTrackId=current_segment.start.trackId,
            description=f"Through ball from #{previous_segment.end.trackId} to #{current_segment.start.trackId}",
        )
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests/test_analytics.py::test_detect_events_emits_through_ball_for_progressive_line_breaking_pass -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /root/WorkSpace/fotball-analyst add backend/app/analytics.py backend/tests/test_analytics.py
git -C /root/WorkSpace/fotball-analyst commit -m "feat: detect through ball events"
```

## Task 2: Add Backend Regression Test For Ordinary Passes

**Files:**
- Modify: `/root/WorkSpace/fotball-analyst/backend/tests/test_analytics.py`

- [ ] **Step 1: Write the failing/guard test**

```python
def test_detect_events_does_not_mark_regular_forward_pass_as_through_ball():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 40.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [
                {"id": 8, "x": 40.0, "y": 50.0, "confidence": 0.92},
                {"id": 11, "x": 49.0, "y": 52.0, "confidence": 0.92},
            ],
            "enemies": [{"id": 3, "x": 70.0, "y": 45.0, "confidence": 0.9}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 49.0, "y": 52.0, "confidence": 0.95},
            "myTeam": [
                {"id": 8, "x": 41.0, "y": 50.0, "confidence": 0.92},
                {"id": 11, "x": 49.0, "y": 52.0, "confidence": 0.92},
            ],
            "enemies": [{"id": 3, "x": 70.0, "y": 45.0, "confidence": 0.9}],
        },
    ]

    assignments = assign_ball_possession(frames)
    events = detect_events(frames, assignments)

    assert [event.type for event in events] == ["pass"]
```

- [ ] **Step 2: Run test to verify behavior**

Run:
```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests/test_analytics.py::test_detect_events_does_not_mark_regular_forward_pass_as_through_ball -q
```

Expected: PASS after Task 1 implementation remains conservative.

- [ ] **Step 3: If needed, tighten heuristics**

Keep the logic narrow. Do not lower progression or advanced-target thresholds just to increase recall.

- [ ] **Step 4: Re-run both through-ball tests**

Run:
```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests/test_analytics.py -q
```

Expected: both through-ball tests PASS

- [ ] **Step 5: Commit**

```bash
git -C /root/WorkSpace/fotball-analyst add backend/tests/test_analytics.py backend/app/analytics.py
git -C /root/WorkSpace/fotball-analyst commit -m "test: guard through ball heuristic"
```

## Task 3: Add Backend Tests For `interception`

**Files:**
- Modify: `/root/WorkSpace/fotball-analyst/backend/tests/test_analytics.py`

- [ ] **Step 1: Write the failing interception test**

```python
def test_detect_events_emits_interception_for_non_tackle_turnover():
    frames = [
        {
            "frameId": 0,
            "timestamp": 0.0,
            "ball": {"x": 58.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [{"id": 6, "x": 58.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 14, "x": 68.0, "y": 50.0, "confidence": 0.9}],
        },
        {
            "frameId": 1,
            "timestamp": 0.2,
            "ball": {"x": 68.0, "y": 50.0, "confidence": 0.95},
            "myTeam": [{"id": 6, "x": 58.0, "y": 50.0, "confidence": 0.92}],
            "enemies": [{"id": 14, "x": 68.0, "y": 50.0, "confidence": 0.9}],
        },
    ]

    assignments = assign_ball_possession(frames)
    events = detect_events(frames, assignments)

    assert [event.type for event in events] == ["turnover", "interception"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests/test_analytics.py::test_detect_events_emits_interception_for_non_tackle_turnover -q
```

Expected: FAIL because only `turnover` is emitted today.

- [ ] **Step 3: Write minimal implementation**

Add helper logic in `/root/WorkSpace/fotball-analyst/backend/app/analytics.py`:

```python
def _turnover_distance(previous_position: tuple[float, float], current_position: tuple[float, float]) -> float:
    return sqrt((previous_position[0] - current_position[0]) ** 2 + (previous_position[1] - current_position[1]) ** 2)


def _is_interception(previous_position: tuple[float, float] | None, current_position: tuple[float, float] | None) -> bool:
    if previous_position is None or current_position is None:
        return False
    distance = _turnover_distance(previous_position, current_position)
    return 6.0 < distance <= 18.0
```

Then inside the existing turnover branch, after the `tackle` check:

```python
elif _is_interception(previous_position, current_position):
    events.append(
        DetectedEvent(
            type="interception",
            frameId=current_segment.start.frameId,
            timestamp=current_segment.start.timestamp,
            team=current_segment.start.team,
            fromTrackId=previous_segment.end.trackId,
            toTrackId=current_segment.start.trackId,
            description=f"Interception by #{current_segment.start.trackId}",
        )
    )
```

- [ ] **Step 4: Run interception test**

Run:
```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests/test_analytics.py::test_detect_events_emits_interception_for_non_tackle_turnover -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /root/WorkSpace/fotball-analyst add backend/app/analytics.py backend/tests/test_analytics.py
git -C /root/WorkSpace/fotball-analyst commit -m "feat: detect interception events"
```

## Task 4: Preserve Tackle Priority Over `interception`

**Files:**
- Modify: `/root/WorkSpace/fotball-analyst/backend/tests/test_analytics.py`

- [ ] **Step 1: Add regression assertion**

Update or add a test so close-contact turnovers still produce:

```python
assert [event.type for event in events] == ["turnover", "tackle"]
```

and explicitly do not include `interception`.

- [ ] **Step 2: Run the targeted tackle test**

Run:
```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests/test_analytics.py::test_detect_events_emits_tackle_when_turnover_happens_under_pressure -q
```

Expected: PASS

- [ ] **Step 3: Tighten turnover branching if needed**

If both events fire for the same turnover, keep `tackle` precedence and suppress `interception`.

- [ ] **Step 4: Run backend analytics suite**

Run:
```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests/test_analytics.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /root/WorkSpace/fotball-analyst add backend/app/analytics.py backend/tests/test_analytics.py
git -C /root/WorkSpace/fotball-analyst commit -m "fix: preserve tackle priority over interception"
```

## Task 5: Extend Frontend Event Types And Mapping

**Files:**
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/types/index.ts`
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/utils/api.ts`
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/utils/api.test.ts`

- [ ] **Step 1: Write the failing frontend mapping test**

Add to `/root/WorkSpace/fotball-analyst/frontend/src/utils/api.test.ts`:

```ts
it('keeps richer derived event types visible in the timeline', () => {
  const tags = mapBackendEventsToTags([
    { type: 'through_ball', frameId: 6, timestamp: 1.2, team: 'my_team', description: 'Through ball played' },
    { type: 'interception', frameId: 8, timestamp: 1.6, team: 'enemy', description: 'Interception won' },
  ]);

  expect(tags.map((tag) => tag.type)).toEqual(['through_ball', 'interception']);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
npm test -- src/utils/api.test.ts
```

Expected: FAIL because the new types are not in the visible mapping yet.

- [ ] **Step 3: Write minimal frontend implementation**

Update `/root/WorkSpace/fotball-analyst/frontend/src/types/index.ts`:

```ts
export type EventType =
  | 'goal'
  | 'foul'
  | 'corner'
  | 'counter'
  | 'offside'
  | 'pass'
  | 'cross'
  | 'shot'
  | 'tackle'
  | 'recovery'
  | 'turnover'
  | 'through_ball'
  | 'interception'
  | 'custom';
```

Update `/root/WorkSpace/fotball-analyst/frontend/src/utils/api.ts`:

```ts
const supportedEventTypes = new Set<EventType>([
  'pass',
  'cross',
  'shot',
  'tackle',
  'recovery',
  'turnover',
  'through_ball',
  'interception',
]);
```

- [ ] **Step 4: Run frontend mapping test**

Run:
```bash
npm test -- src/utils/api.test.ts
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /root/WorkSpace/fotball-analyst add frontend/src/types/index.ts frontend/src/utils/api.ts frontend/src/utils/api.test.ts
git -C /root/WorkSpace/fotball-analyst commit -m "feat: expose richer derived event types"
```

## Task 6: Full Verification

**Files:**
- Verify only

- [ ] **Step 1: Run backend tests**

```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests -q
```

Expected: PASS

- [ ] **Step 2: Run frontend tests**

```bash
npm test
```

Expected: PASS

- [ ] **Step 3: Run frontend build**

```bash
npm run build
```

Expected: PASS

- [ ] **Step 4: Run frontend lint**

```bash
npm run lint
```

Expected: PASS

- [ ] **Step 5: Run Python compile verification**

```bash
python3 -m py_compile /root/WorkSpace/fotball-analyst/backend/app/*.py /root/WorkSpace/fotball-analyst/backend/run_guerilla.py /root/WorkSpace/fotball-analyst/backend/train_custom.py
```

Expected: PASS
