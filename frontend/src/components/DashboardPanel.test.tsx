import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

import DashboardPanel from './DashboardPanel';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it('preserves an invalid source date instead of showing Invalid Date', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
    summary: {
      matchCount: 1, avgPossession: null, avgMyTeamXg: 0, avgEnemyXg: 0,
      avgXgDiff: 0, avgMyTeamSprints: 0, avgEnemySprints: 0, mostUsedFormation: '-',
    },
    comparison: null, opponentRollups: [], playerTrendSnapshots: [],
    trends: [{
      matchId: 'invalid-date', name: 'Invalid Date Match', date: 'not-a-date',
      summary: { possession: null, myTeamXg: 0, enemyXg: 0 },
    }],
  }), { status: 200, headers: { 'Content-Type': 'application/json' } })));

  render(<DashboardPanel onClose={() => undefined} />);

  expect((await screen.findAllByText('not-a-date')).length).toBeGreaterThan(0);
});

it('shows unknown rather than a percentage when possession has no controlled denominator', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
    summary: {
      matchCount: 1, avgPossession: null, avgMyTeamXg: 0, avgEnemyXg: 0,
      avgXgDiff: 0, avgMyTeamSprints: 0, avgEnemySprints: 0, mostUsedFormation: '-',
    },
    comparison: null, opponentRollups: [], playerTrendSnapshots: [],
    trends: [{
      matchId: 'unresolved', name: 'Unresolved Teams', date: '2026-09-14T00:00:00Z',
      summary: { possession: null, myTeamXg: 0, enemyXg: 0 },
    }],
  }), { status: 200, headers: { 'Content-Type': 'application/json' } })));

  render(<DashboardPanel onClose={() => undefined} />);

  const card = (await screen.findByText('Avg Possession')).parentElement;
  expect(card).not.toBeNull();
  expect(within(card as HTMLElement).getByText('Not measured')).toBeTruthy();
  expect(screen.queryByText('50%')).toBeNull();
});

it('does not publish sprint averages when physical totals are withheld', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
    summary: {
      matchCount: 1, avgPossession: 55, avgMyTeamXg: 1.2, avgEnemyXg: 0.8,
      avgXgDiff: 0.4, avgMyTeamSprints: null, avgEnemySprints: null, mostUsedFormation: '4-3-3',
    },
    comparison: {
      latestMatchId: 'a', latestMatchName: 'Latest', previousMatchId: 'b', previousMatchName: 'Previous',
      possessionDelta: 2, xgDiffDelta: 0.1, myTeamSprintsDelta: null, enemySprintsDelta: null,
    },
    opponentRollups: [], playerTrendSnapshots: [],
    trends: [],
  }), { status: 200, headers: { 'Content-Type': 'application/json' } })));

  render(<DashboardPanel onClose={() => undefined} />);

  const card = (await screen.findByText('Sprints For / Against')).parentElement;
  expect(card).not.toBeNull();
  expect(within(card as HTMLElement).getByText('Unavailable')).toBeTruthy();
  expect(card!.textContent).not.toMatch(/\b12\b/);
  expect(screen.getByText(/Sprints: Not measured/)).toBeTruthy();
});
