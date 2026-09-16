# LLM Report Context Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** enrich the `tactical_report` and `drills` analysis flow with stronger derived player-focus and match-signal context while preserving the existing API routes and overall response structure.

**Architecture:** keep prompt assembly backend-led in `backend/app/llm.py`, extend the analysis call in `backend/app/main.py` so report/drill requests receive shot analytics in addition to summary/events/formation, and render the richer evidence through a focused frontend component used by `frontend/src/App.tsx`. The slice stays additive: no new analysis endpoints and no changes to `offside` or `spacing`.

**Tech Stack:** FastAPI, Pydantic, Python, React 19, TypeScript, Vitest, Pytest.

---

## File Structure

- Modify: `/root/WorkSpace/fotball-analyst/backend/app/llm.py`
  Purpose: build richer prompt context and return enriched report/drill payload shapes
- Modify: `/root/WorkSpace/fotball-analyst/backend/app/main.py`
  Purpose: pass shot analytics into `run_analysis(...)` for report/drill requests
- Modify: `/root/WorkSpace/fotball-analyst/backend/tests/test_llm.py`
  Purpose: backend prompt-context regression coverage
- Modify: `/root/WorkSpace/fotball-analyst/backend/tests/test_api.py`
  Purpose: verify the analysis endpoint passes shot analytics into `run_analysis(...)`
- Create: `/root/WorkSpace/fotball-analyst/frontend/src/components/CoachInsights.tsx`
  Purpose: render enriched tactical report and drill evidence in a focused, testable component
- Create: `/root/WorkSpace/fotball-analyst/frontend/src/components/CoachInsights.test.tsx`
  Purpose: frontend rendering coverage for player-focus and evidence blocks
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/App.tsx`
  Purpose: wire the new insights component into the report/drills tabs and extend local interfaces

## Task 1: Add Failing Backend Prompt Tests

**Files:**
- Modify: `/root/WorkSpace/fotball-analyst/backend/tests/test_llm.py`

- [ ] **Step 1: Write a failing tactical-report prompt test**

```python
def test_tactical_report_prompt_includes_player_focus_and_match_signals():
    summary = MatchSummary(
        possession=61,
        myTeamDistance=1042,
        enemyDistance=980,
        myTeamAvgPos={"x": 57.4, "y": 48.1},
        enemyAvgPos={"x": 43.2, "y": 50.3},
        myTeamTopSpeed=31.4,
        enemyTopSpeed=29.1,
        myTeamSprints=12,
        enemySprints=9,
        myTeamXg=1.22,
        enemyXg=0.48,
        myTeamDefensiveLineHeight=24,
        enemyDefensiveLineHeight=30,
        myTeamDefensiveTeamLength=37,
        enemyDefensiveTeamLength=42,
        myTeamPpda=6.1,
        enemyPpda=8.4,
        myTeamHighPressRegains=4,
        enemyHighPressRegains=1,
        myTeamCounterpressRecoverySeconds=3.2,
        enemyCounterpressRecoverySeconds=5.1,
        formation="4-3-3",
    )
    events = [
        DetectedEvent(type="through_ball", frameId=2, timestamp=0.4, team="my_team", fromTrackId=7, toTrackId=9, description="7 through ball to 9"),
        DetectedEvent(type="shot", frameId=3, timestamp=0.6, team="my_team", fromTrackId=9, description="9 shot"),
        DetectedEvent(type="interception", frameId=4, timestamp=0.8, team="enemy", toTrackId=18, description="18 interception"),
    ]
    shots = [
        ShotMarker(frameId=3, timestamp=0.6, team="my_team", playerId=9, x=90, y=50, inBox=True, xg=0.38, distanceToGoal=10.0, angleDegrees=30.0),
    ]

    prompt = build_prompt("tactical_report", [], summary=summary, events=events, shots=shots)

    assert "playerFocus" in prompt
    assert "matchSignals" in prompt
    assert "topCreator" in prompt
    assert "topFinisher" in prompt
    assert "topBallWinner" in prompt
    assert "through_ball" in prompt
    assert "0.38" in prompt
```

- [ ] **Step 2: Write a failing drills prompt test**

```python
def test_drills_prompt_includes_player_focus_and_contextual_signals():
    prompt = build_prompt("drills", [], summary=summary, events=events, shots=shots)
    assert "playerFocus" in prompt
    assert "matchSignals" in prompt
    assert "focus_area" in prompt
```

- [ ] **Step 3: Run the backend prompt tests to verify RED**

Run:
```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests/test_llm.py -q
```

Expected: FAIL because the richer prompt context and `shots` argument are not implemented yet.

## Task 2: Add Failing API Regression For Shot Analytics Handoff

**Files:**
- Modify: `/root/WorkSpace/fotball-analyst/backend/tests/test_api.py`

- [ ] **Step 1: Extend the captured-analysis test**

Add a `shots=None` keyword to `fake_run_analysis(...)`, record it in `captured`, and assert:

```python
assert captured["shots"] is not None
assert len(captured["shots"]) >= 1
```

- [ ] **Step 2: Run the targeted API test to verify RED**

Run:
```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests/test_api.py::test_analysis_endpoint_uses_persisted_match_context -q
```

Expected: FAIL because `main.py` does not pass `shots` into `run_analysis(...)` yet.

## Task 3: Implement Backend Context Upgrade

**Files:**
- Modify: `/root/WorkSpace/fotball-analyst/backend/app/llm.py`
- Modify: `/root/WorkSpace/fotball-analyst/backend/app/main.py`

- [ ] **Step 1: Extend the LLM signatures**

Update:

```python
from .schemas import DetectedEvent, FormationSegment, FrameData, MatchSummary, ShotMarker
```

and add:

```python
shots: list[ShotMarker] | None = None
```

to `_build_match_context(...)`, `build_prompt(...)`, and `run_analysis(...)`.

- [ ] **Step 2: Add compact derived helpers in `llm.py`**

Implement small helpers for:

- player-focus summaries
- creator/finisher/ball-winner selection
- match-signal extraction from `MatchSummary`
- shot-pattern summary from `shots`

Keep them deterministic and compact. Use output shaped like:

```python
{
    "topCreator": {"trackId": 7, "team": "my_team", "label": "Primary Creator", "summary": "1 through ball, 0.38 xG created", "involvements": 1, "xgCreated": 0.38, "xgTaken": 0.0, "ballWins": 0},
    "topFinisher": {...},
    "topBallWinner": {...},
    "otherKeyPlayers": [...],
}
```

- [ ] **Step 3: Extend `_build_match_context(...)`**

Add:

```python
context["playerFocus"] = ...
context["matchSignals"] = ...
```

and enrich `eventSummary` with shot- and through-ball-related derived counts when possible.

- [ ] **Step 4: Keep the prompt wording backward-compatible**

Update the `tactical_report` prompt to ask for:

```python
'"event_summary": {"eventCounts": object, "topPlayers": array}, "player_focus": object'
```

and update the `drills` prompt to allow:

```python
'"player_focus": object'
```

- [ ] **Step 5: Pass shots from `main.py`**

Update the analysis route so report/drill requests load analytics as:

```python
summary, _, formation_timeline, shots = storage.load_analytics(match_id)
```

and pass `shots=shots` into `run_analysis(...)`.

- [ ] **Step 6: Run backend tests to verify GREEN**

Run:
```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests/test_llm.py /root/WorkSpace/fotball-analyst/backend/tests/test_api.py -q
```

Expected: PASS

## Task 4: Add Failing Frontend Rendering Tests

**Files:**
- Create: `/root/WorkSpace/fotball-analyst/frontend/src/components/CoachInsights.test.tsx`

- [ ] **Step 1: Write a failing tactical-report rendering test**

```tsx
it('renders player-focus leaders and evidence for tactical reports', () => {
  render(
    <CoachInsights
      activeTab="report"
      llmThinking={false}
      tacticalReport={{
        attacking: "Strong right-side progression",
        defensive: "Compact block",
        pressing: "Aggressive counterpress",
        key_player: 7,
        weaknesses: "Rest defense after turnovers",
        rating: 8,
        summary: "Positive attacking output",
        evidence: ["My team created 1.22 xG from 2 high-value chances."],
        event_summary: { eventCounts: { through_ball: 2 }, topPlayers: [] },
        player_focus: {
          topCreator: { trackId: 7, team: "my_team", label: "Primary Creator", summary: "2 through balls, 0.54 xG created" },
        },
      }}
      drillResponse={null}
      onGenerateReport={() => {}}
      onGenerateDrills={() => {}}
    />,
  )

  expect(screen.getByText('Player Focus')).toBeTruthy()
  expect(screen.getByText('Primary Creator')).toBeTruthy()
  expect(screen.getByText('2 through balls, 0.54 xG created')).toBeTruthy()
})
```

- [ ] **Step 2: Write a failing drills rendering test**

```tsx
it('renders drill evidence and player-focus context', () => {
  render(...);
  expect(screen.getByText('Why These Drills')).toBeTruthy()
  expect(screen.getByText('Player Focus')).toBeTruthy()
})
```

- [ ] **Step 3: Run the frontend component test to verify RED**

Run:
```bash
npm test -- src/components/CoachInsights.test.tsx
```

Expected: FAIL because the component does not exist yet.

## Task 5: Implement Frontend Rendering Upgrade

**Files:**
- Create: `/root/WorkSpace/fotball-analyst/frontend/src/components/CoachInsights.tsx`
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/App.tsx`

- [ ] **Step 1: Create a focused `CoachInsights` component**

Move the report/drills rendering out of `App.tsx` into a component that accepts:

```ts
activeTab
llmThinking
tacticalReport
drillResponse
onGenerateReport
onGenerateDrills
```

Keep the current visual style and behavior.

- [ ] **Step 2: Add enriched local interfaces in `App.tsx`**

Extend `TacticalReport` and `DrillResponse` with:

```ts
player_focus?: {
  topCreator?: { trackId: number; team: string; label?: string; summary?: string };
  topFinisher?: { trackId: number; team: string; label?: string; summary?: string };
  topBallWinner?: { trackId: number; team: string; label?: string; summary?: string };
  otherKeyPlayers?: Array<{ trackId: number; team: string; label?: string; summary?: string }>;
}
```

- [ ] **Step 3: Render stronger evidence blocks**

Inside `CoachInsights.tsx`, show:

- `Player Focus`
- top creator / finisher / ball winner cards when present
- existing `Event Snapshot` and `Evidence`
- drill evidence plus player-focus support when present

- [ ] **Step 4: Replace the inline report/drills JSX in `App.tsx`**

Use the new component instead of the current large inline block.

- [ ] **Step 5: Run the component test to verify GREEN**

Run:
```bash
npm test -- src/components/CoachInsights.test.tsx
```

Expected: PASS

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

- [ ] **Step 3: Run the frontend build**

```bash
npm run build
```

Expected: PASS

- [ ] **Step 4: Run frontend lint**

```bash
npm run lint
```

Expected: PASS

- [ ] **Step 5: Summarize roadmap progress**

Call out:

- reports and drills now consume richer derived match context
- player-focus and match-signal evidence are surfaced end-to-end
- the next strongest slice is synced video playback or report export, depending whether we want better review workflow or output packaging next
