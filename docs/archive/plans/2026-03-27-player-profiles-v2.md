# Player Profiles V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** enrich the existing player-profile layer with creator/finisher/ball-winner signals, shot-quality context, and coach-readable summaries without changing the backend contract.

**Architecture:** keep this slice frontend-owned. Extend `buildPlayerProfiles(...)` in `frontend/src/utils/analytics.ts` to consume backend events plus shot markers, expand the shared profile types, and upgrade the existing `StatsPanel` cards to surface the stronger metrics and highlight leaders. No API changes and no new backend work are required.

**Tech Stack:** React 19, TypeScript, Vite, Vitest, Testing Library.

---

## File Structure

- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/types/index.ts`
  Purpose: extend `PlayerContribution` and `PlayerProfile` with Player Profiles v2 fields
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/utils/analytics.ts`
  Purpose: derive richer player metrics, xG attribution, labels, summaries, and ranking
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/utils/analytics.test.ts`
  Purpose: regression coverage for v2 profile derivation
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/App.tsx`
  Purpose: pass shot analytics into `buildPlayerProfiles(...)`
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/components/StatsPanel.tsx`
  Purpose: render richer player-profile cards and top-of-match highlights
- Create: `/root/WorkSpace/fotball-analyst/frontend/src/components/StatsPanel.test.tsx`
  Purpose: verify the richer profile UI and empty states

## Task 1: Add Failing Analytics Tests For V2 Profile Fields

**Files:**
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/utils/analytics.test.ts`

- [ ] **Step 1: Write the failing derivation test**

```ts
it('builds richer player profiles from event output and shot quality', () => {
  const profiles = buildPlayerProfiles(
    [
      {
        Frame_ID: 0,
        Timestamp: 0,
        Ball: { x: 48, y: 50, conf: 0.9 },
        My_Team: [
          { id: 7, x: 30, y: 40, conf: 0.9 },
          { id: 9, x: 82, y: 49, conf: 0.9 },
        ],
        Enemies: [{ enemy_id: 18, x: 58, y: 44, conf: 0.9 }],
      },
      {
        Frame_ID: 1,
        Timestamp: 0.5,
        Ball: { x: 82, y: 49, conf: 0.9 },
        My_Team: [
          { id: 7, x: 33, y: 40, conf: 0.9 },
          { id: 9, x: 84, y: 49, conf: 0.9 },
        ],
        Enemies: [{ enemy_id: 18, x: 56, y: 44, conf: 0.9 }],
      },
    ],
    [
      { type: 'through_ball', frameId: 1, timestamp: 0.5, team: 'my_team', fromTrackId: 7, toTrackId: 9, description: 'Through ball played' },
      { type: 'shot', frameId: 1, timestamp: 0.5, team: 'my_team', fromTrackId: 9, description: 'Shot attempted' },
      { type: 'interception', frameId: 1, timestamp: 0.5, team: 'enemy', toTrackId: 18, description: 'Interception won' },
    ],
    [
      { frameId: 1, timestamp: 0.5, team: 'my_team', playerId: 9, x: 84, y: 49, inBox: true, xg: 0.38 },
    ],
  );

  expect(profiles).toEqual([
    expect.objectContaining({
      team: 'my_team',
      playerId: 7,
      throughBalls: 1,
      interceptions: 0,
      ballWins: 0,
      xgCreated: 0.38,
      xgTaken: 0,
      profileLabel: 'Primary Creator',
      summaryLine: '1 through ball, 0.38 xG created',
    }),
    expect.objectContaining({
      team: 'my_team',
      playerId: 9,
      shots: 1,
      xgTaken: 0.38,
      profileLabel: 'Shot Threat',
      summaryLine: '1 shot, 0.38 xG taken',
    }),
    expect.objectContaining({
      team: 'enemy',
      playerId: 18,
      interceptions: 1,
      ballWins: 1,
      profileLabel: 'Ball Winner',
      summaryLine: '1 ball win, 1 interception',
    }),
  ]);
});
```

- [ ] **Step 2: Run the test to verify RED**

Run:
```bash
npm test -- src/utils/analytics.test.ts
```

Expected: FAIL because `buildPlayerProfiles(...)` does not yet accept shot markers or emit the richer fields.

- [ ] **Step 3: Add a conservative ranking/label regression test**

```ts
it('prefers xg and role signals when sorting tied impact profiles', () => {
  const profiles = buildPlayerProfiles(
    [],
    [
      { type: 'pass', frameId: 1, timestamp: 0.2, team: 'my_team', fromTrackId: 7, toTrackId: 11, description: 'Pass' },
      { type: 'shot', frameId: 2, timestamp: 0.4, team: 'my_team', fromTrackId: 11, description: 'Shot' },
    ],
    [
      { frameId: 2, timestamp: 0.4, team: 'my_team', playerId: 11, x: 90, y: 50, inBox: true, xg: 0.42 },
    ],
  );

  expect(profiles[0]).toEqual(
    expect.objectContaining({
      playerId: 11,
      profileLabel: 'Shot Threat',
    }),
  );
});
```

- [ ] **Step 4: Run the test file again**

Run:
```bash
npm test -- src/utils/analytics.test.ts
```

Expected: FAIL for the new behavior, not due to syntax errors.

## Task 2: Implement V2 Profile Derivation

**Files:**
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/types/index.ts`
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/utils/analytics.ts`
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/App.tsx`

- [ ] **Step 1: Extend shared types**

Add the new fields to the shared interfaces:

```ts
export interface PlayerContribution {
  team: 'my_team' | 'enemy';
  playerId: number;
  passes: number;
  crosses: number;
  throughBalls: number;
  shots: number;
  tacklesWon: number;
  recoveries: number;
  interceptions: number;
  ballWins: number;
  involvements: number;
  xgCreated: number;
  xgTaken: number;
  impactScore: number;
}

export interface PlayerProfile extends PlayerContribution {
  avgX: number;
  avgY: number;
  totalDistance: number;
  topSpeed: number;
  profileLabel: string;
  summaryLine: string;
}
```

- [ ] **Step 2: Update `buildPlayerProfiles(...)` signature**

Change the signature to:

```ts
export function buildPlayerProfiles(
  frames: FrameData[],
  events: BackendEvent[],
  shotMarkers: ShotMarker[] = []
): PlayerProfile[] {
```

- [ ] **Step 3: Implement minimal helper logic**

Inside `frontend/src/utils/analytics.ts`, add small helpers for:

- `xgTaken` accumulation from `shotMarkers`
- conservative `xgCreated` attribution from `pass` / `cross` / `through_ball`
- `ballWins` and `involvements` derivation
- role-label selection
- summary-line formatting

Keep the heuristics narrow:

```ts
const CREATOR_EVENT_TYPES = new Set(['pass', 'cross', 'through_ball']);
const CREATION_FRAME_WINDOW = 12;
```

- [ ] **Step 4: Reweight impact score minimally**

Use a deterministic formula such as:

```ts
impactScore =
  passes +
  (crosses * 2) +
  (throughBalls * 3) +
  (shots * 3) +
  (tacklesWon * 2) +
  (recoveries * 2) +
  (interceptions * 2) +
  Math.round((xgTaken + xgCreated) * 10);
```

- [ ] **Step 5: Pass shot markers from `App.tsx`**

Update the existing memo:

```ts
const playerProfiles = useMemo(() => {
  if (!activeMatch) return [];
  return buildPlayerProfiles(activeMatch.data, activeMatch.backendEvents, shotMarkers);
}, [activeMatch, shotMarkers]);
```

- [ ] **Step 6: Run analytics tests to verify GREEN**

Run:
```bash
npm test -- src/utils/analytics.test.ts
```

Expected: PASS

## Task 3: Add Failing StatsPanel Rendering Tests

**Files:**
- Create: `/root/WorkSpace/fotball-analyst/frontend/src/components/StatsPanel.test.tsx`

- [ ] **Step 1: Write a failing render test for richer player profile cards**

```tsx
it('renders highlight leaders and richer player profile summaries', () => {
  render(
    <StatsPanel
      stats={baseStats}
      shotSummary={{ myTeamShots: 2, enemyShots: 1, myTeamBoxShots: 1, enemyBoxShots: 0, myTeamXg: 0.54, enemyXg: 0.08 }}
      playerProfiles={[
        {
          team: 'my_team',
          playerId: 7,
          passes: 4,
          crosses: 0,
          throughBalls: 2,
          shots: 0,
          tacklesWon: 0,
          recoveries: 0,
          interceptions: 0,
          ballWins: 0,
          involvements: 6,
          xgCreated: 0.54,
          xgTaken: 0,
          impactScore: 11,
          avgX: 42,
          avgY: 36,
          totalDistance: 105.3,
          topSpeed: 28.1,
          profileLabel: 'Primary Creator',
          summaryLine: '2 through balls, 0.54 xG created',
        },
      ]}
    />,
  );

  expect(screen.getByText('Top Creator')).toBeInTheDocument();
  expect(screen.getByText('#7')).toBeInTheDocument();
  expect(screen.getByText('Primary Creator')).toBeInTheDocument();
  expect(screen.getByText('2 through balls, 0.54 xG created')).toBeInTheDocument();
});
```

- [ ] **Step 2: Add an empty-state regression test**

```tsx
it('keeps the waiting state when there are no derived player profiles', () => {
  render(<StatsPanel stats={baseStats} shotSummary={null} playerProfiles={[]} />);
  expect(screen.getByText('Waiting for derived player profiles.')).toBeInTheDocument();
});
```

- [ ] **Step 3: Run the test file to verify RED**

Run:
```bash
npm test -- src/components/StatsPanel.test.tsx
```

Expected: FAIL because the richer highlight/profile UI is not rendered yet.

## Task 4: Implement StatsPanel Player Profiles V2 UI

**Files:**
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/components/StatsPanel.tsx`

- [ ] **Step 1: Add compact leader highlights**

Derive leaders from the incoming profiles:

```ts
const topCreator = [...playerProfiles]
  .filter((player) => player.xgCreated > 0 || player.throughBalls > 0)
  .sort((a, b) => (b.xgCreated - a.xgCreated) || (b.throughBalls - a.throughBalls) || (a.playerId - b.playerId))[0];
```

Repeat the same compact pattern for `topFinisher` and `topBallWinner`.

- [ ] **Step 2: Upgrade the card content**

Render:

- profile label
- involvement count
- through balls / interceptions / ball wins
- xG created / xG taken
- existing movement line
- summary line

Keep the existing visual language and avoid adding a new large panel.

- [ ] **Step 3: Run the component test to verify GREEN**

Run:
```bash
npm test -- src/components/StatsPanel.test.tsx
```

Expected: PASS

## Task 5: Full Frontend Verification

**Files:**
- Verify only

- [ ] **Step 1: Run the full frontend test suite**

```bash
npm test
```

Expected: PASS

- [ ] **Step 2: Run the production build**

```bash
npm run build
```

Expected: PASS

- [ ] **Step 3: Run lint**

```bash
npm run lint
```

Expected: PASS

- [ ] **Step 4: Summarize the new roadmap state**

Call out:

- Player Profiles v2 is complete
- richer event intelligence now feeds coach-readable player outputs
- likely next slice is stronger LLM analysis grounded in the fuller event/profile context
