import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

import PlayerDetailPanel from './PlayerDetailPanel';
import type { BackendEvent, PlayerProfile } from '../types';

afterEach(cleanup);

const player: PlayerProfile = {
  team: 'my_team',
  playerId: 7,
  jerseyNumber: 7,
  passes: 12,
  crosses: 3,
  throughBalls: 1,
  shots: 2,
  tacklesWon: 0,
  recoveries: 4,
  interceptions: 1,
  ballWins: 5,
  involvements: 20,
  xgCreated: 0.1,
  xgTaken: 0.2,
  impactScore: 8,
  avgX: 25,
  avgY: 40,
  totalDistance: 1200,
  topSpeed: 28,
  profileLabel: 'Selected player',
  summaryLine: 'Interval observations only until identity is continuous.',
};

const events: BackendEvent[] = [
  {
    type: 'pass',
    frameId: 4,
    timestamp: 0.8,
    team: 'my_team',
    fromTrackId: 7,
    toTrackId: 11,
    description: 'Pass from 7',
  },
];

it('shows interval-limited observations instead of match totals without identity continuity', () => {
  render(<PlayerDetailPanel player={player} events={events} identityContinuous={false} />);
  expect(screen.getByText(/interval-limited/i)).toBeTruthy();
  expect(screen.getByText(/totals withheld/i)).toBeTruthy();
  expect(screen.queryByText('12')).toBeNull();
  expect(screen.getByText('Pass from 7')).toBeTruthy();
});

it('shows match totals only after identity continuity is validated', () => {
  render(<PlayerDetailPanel player={player} events={events} identityContinuous />);
  expect(screen.getByText('12')).toBeTruthy();
  expect(screen.queryByText(/totals withheld/i)).toBeNull();
});

it('offers match-scoped identity split without treating the click as continuity', () => {
  const onSplitIdentity = vi.fn();
  render(
    <PlayerDetailPanel
      player={player}
      events={events}
      identityContinuous
      onSplitIdentity={onSplitIdentity}
    />,
  );
  fireEvent.click(screen.getByRole('button', { name: /split identity/i }));
  expect(onSplitIdentity).toHaveBeenCalledTimes(1);
});
