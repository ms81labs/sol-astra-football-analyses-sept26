import { render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

import DashboardPanel from './DashboardPanel';

afterEach(() => vi.unstubAllGlobals());

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
