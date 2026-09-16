import { render, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import StatsPanel from './StatsPanel';
import type { MatchBenchmarkSummary, MatchStats, PlayerProfile, ShotSummary } from '../types';

const baseStats: MatchStats = {
  possession: 55,
  myTeamDistance: 920,
  enemyDistance: 875,
  myTeamAvgPos: { x: 52, y: 48 },
  enemyAvgPos: { x: 47, y: 50 },
  myTeamTopSpeed: 29.4,
  enemyTopSpeed: 28.2,
  myTeamSprints: 12,
  enemySprints: 10,
  myTeamXg: 0.54,
  enemyXg: 0.08,
  myTeamDefensiveLineHeight: 24,
  enemyDefensiveLineHeight: 29,
  myTeamDefensiveTeamLength: 36,
  enemyDefensiveTeamLength: 39,
  myTeamPpda: 6.1,
  enemyPpda: 8.3,
  myTeamHighPressRegains: 4,
  enemyHighPressRegains: 1,
  myTeamCounterpressRecoverySeconds: 3.2,
  enemyCounterpressRecoverySeconds: 5.1,
  ballSignalStatus: 'trusted',
  ballSignalMessage: null,
  formation: '4-3-3',
};

const shotSummary: ShotSummary = {
  myTeamShots: 2,
  enemyShots: 1,
  myTeamBoxShots: 1,
  enemyBoxShots: 0,
  myTeamXg: 0.54,
  enemyXg: 0.08,
};

const benchmarkTruthReady: MatchBenchmarkSummary = {
  matchId: 'match-1',
  jobId: 'job-1',
  inputMode: 'video',
  matchStatus: 'ready',
  jobStatus: 'completed',
  requiresTeamSelection: false,
  rawRowCount: 300,
  frameCount: 300,
  playerFrames: 280,
  withBallFrames: 120,
  withBallRatio: 0.4,
  trackedPossessionFrames: 260,
  trackedPossessionRatio: 0.87,
  controlledPossessionFrames: 240,
  controlledPossessionRatio: 0.8,
  eventCount: 6,
  eventTypes: { pass: 3, turnover: 2, interception: 1 },
  eventFamilyCount: 3,
  dominantEventShare: 0.5,
  shotCount: 0,
  ballSignalStatus: 'trusted',
  ballTrackPathLength: 42,
  ballTrackEdgeFrameShare: 0.2,
  ballTrackShowsMeaningfulMotion: true,
  ballTrackViable: true,
  fiveMinuteTruthReady: true,
  fortyFiveMinuteTruthReady: false,
  truthGateReasons: [],
  artifactPresence: { frames: true, analytics: true, events: true, rawRows: true },
};

const sampleProfiles: PlayerProfile[] = [
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
    summaryLine: '2 through balls, 0.54 experimental shot quality created',
  },
];

describe('StatsPanel', () => {
  it('renders highlight leaders and richer player profile summaries', () => {
    const { container } = render(<StatsPanel stats={baseStats} shotSummary={shotSummary} playerProfiles={sampleProfiles} />);
    const scoped = within(container);

    expect(scoped.getByText('Top Creator')).toBeTruthy();
    expect(scoped.getAllByText('#7')).toHaveLength(2);
    expect(scoped.getByText('Primary Creator')).toBeTruthy();
    expect(scoped.getAllByText('2 through balls, 0.54 experimental shot quality created')).toHaveLength(2);
  });

  it('labels player shot quality as experimental instead of xGC/xGT', () => {
    const { container } = render(<StatsPanel stats={baseStats} shotSummary={shotSummary} playerProfiles={sampleProfiles} />);
    const scoped = within(container);

    expect(scoped.queryByText(/xGC/)).toBeNull();
    expect(scoped.queryByText(/xGT/)).toBeNull();
    expect(scoped.getByText('0.54 experimental shot quality created, 0.00 experimental shot quality taken')).toBeTruthy();
  });

  it('keeps the waiting state when there are no derived player profiles', () => {
    const { container } = render(<StatsPanel stats={baseStats} shotSummary={null} playerProfiles={[]} />);
    const scoped = within(container);

    expect(scoped.getByText('Waiting for derived player profiles.')).toBeTruthy();
  });

  it('hides tactical stat surfaces when the ball signal is untrusted', () => {
    const { container } = render(
      <StatsPanel
        stats={{ ...baseStats, ballSignalStatus: 'untrusted', ballSignalMessage: 'ball track lost' }}
        shotSummary={shotSummary}
        playerProfiles={sampleProfiles}
      />,
    );
    const scoped = within(container);

    expect(scoped.getByText('Ball signal untrusted')).toBeTruthy();
    expect(scoped.getByText(/Possession, experimental shot quality, and event analytics may be unreliable/)).toBeTruthy();
    expect(scoped.queryByText(/Possession, xG,/)).toBeNull();
    expect(scoped.queryByRole('heading', { name: 'Possession' })).toBeNull();
    expect(scoped.queryByRole('heading', { name: 'Pressing' })).toBeNull();
    expect(scoped.queryByText('Top Creator')).toBeNull();
    expect(scoped.getByText('Distance (m)')).toBeTruthy();
    expect(scoped.getByText('Speed & Sprints')).toBeTruthy();
  });

  it('hides tactical stat surfaces when benchmark truth gates fail', () => {
    const { container } = render(
      <StatsPanel
        stats={baseStats}
        benchmark={{
          ...benchmarkTruthReady,
          fiveMinuteTruthReady: false,
          withBallRatio: 0.07,
          truthGateReasons: ['Need withBallFrames/frameCount >= 25% for truthful 5-10 minute analysis'],
        }}
        shotSummary={shotSummary}
        playerProfiles={sampleProfiles}
      />,
    );
    const scoped = within(container);

    expect(scoped.getByText('Review-only: truth gates not met')).toBeTruthy();
    expect(scoped.getByText('Need withBallFrames/frameCount >= 25% for truthful 5-10 minute analysis')).toBeTruthy();
    expect(scoped.queryByRole('heading', { name: 'Possession' })).toBeNull();
    expect(scoped.queryByRole('heading', { name: 'Pressing' })).toBeNull();
    expect(scoped.queryByText('Top Creator')).toBeNull();
    expect(scoped.getByText('Distance (m)')).toBeTruthy();
    expect(scoped.getByText('Speed & Sprints')).toBeTruthy();
  });

  it('does not fabricate possession or hide an otherwise available formation', () => {
    const { container } = render(
      <StatsPanel stats={{ ...baseStats, possession: null }} benchmark={benchmarkTruthReady} shotSummary={shotSummary} />,
    );
    const scoped = within(container);
    expect(scoped.queryByRole('heading', { name: 'Possession' })).toBeNull();
    expect(scoped.getByRole('heading', { name: 'Formation' })).toBeTruthy();
  });

  it('withholds a placeholder formation and unpublished experimental shot quality', () => {
    const { container } = render(
      <StatsPanel
        stats={{ ...baseStats, formation: null, myTeamXg: null, enemyXg: null }}
        benchmark={benchmarkTruthReady}
        shotSummary={{ ...shotSummary, myTeamXg: null, enemyXg: null }}
      />,
    );
    const scoped = within(container);
    expect(scoped.getByRole('heading', { name: 'Formation' })).toBeTruthy();
    expect(scoped.getAllByText('Unavailable').length).toBeGreaterThanOrEqual(1);
    expect(container.textContent).not.toContain('0.00 experimental shot quality');
    expect(container.textContent).not.toMatch(/(?:^|[^-])4-3-3/);
  });

  it('withholds formation when stored availability is not eligible', () => {
    const { container } = render(
      <StatsPanel
        stats={baseStats}
        benchmark={benchmarkTruthReady}
        shotSummary={shotSummary}
        formationAvailability={{ availability: 'withheld', reasonCodes: ['SINGLE_FRAME_FORMATION'], value: null }}
      />,
    );
    const scoped = within(container);
    expect(scoped.getByRole('heading', { name: 'Formation' })).toBeTruthy();
    expect(scoped.getByText('Unavailable')).toBeTruthy();
    expect(container.textContent).not.toContain('4-3-3');
  });

  it('does not publish player-card distances when physical totals are withheld', () => {
    const { container } = render(
      <StatsPanel
        stats={baseStats}
        shotSummary={shotSummary}
        playerProfiles={[{ ...sampleProfiles[0], physicalTotalsWithheld: true }]}
      />,
    );
    const scoped = within(container);
    expect(container.textContent).not.toContain('105.3 m');
    expect(container.textContent).not.toContain('28.1 km/h');
    expect(scoped.getByText('Physical totals withheld')).toBeTruthy();
  });

  it('renders withheld physical metrics as unavailable rather than a measured zero', () => {
    const { container } = render(
      <StatsPanel
        stats={{ ...baseStats, myTeamDistance: null, enemyDistance: null, myTeamTopSpeed: null, enemyTopSpeed: null, myTeamSprints: null, enemySprints: null }}
        metricAvailability={[{
          metric: 'my_team_distance_m',
          definitionVersion: '1',
          value: null,
          availability: 'unknown',
          reasonCodes: ['IDENTITY_DISCONTINUITY'],
          unit: 'metres',
          denominator: 'identity_continuous_eligible_seconds',
          eligibleSeconds: 0,
        }]}
      />,
    );
    const scoped = within(container);
    expect(scoped.getAllByText('Unavailable').length).toBeGreaterThanOrEqual(1);
    expect(scoped.getByText(/metric inspector/i)).toBeTruthy();
    expect(scoped.getByText(/identity_continuous_eligible_seconds/)).toBeTruthy();
    expect(scoped.getByText(/metres/)).toBeTruthy();
  });

  it('does not publish speed and sprints when identity-continuous physical metrics are withheld', () => {
    const withheld = (metric: string, unit: string) => ({
      metric,
      definitionVersion: '1',
      value: null,
      availability: 'withheld' as const,
      reasonCodes: ['IDENTITY_DISCONTINUITY'],
      unit,
      denominator: 'identity_continuous_eligible_seconds',
      eligibleSeconds: 0,
    });
    const { container } = render(
      <StatsPanel
        stats={baseStats}
        metricAvailability={[
          withheld('my_team_distance_m', 'metres'),
          withheld('enemy_distance_m', 'metres'),
          withheld('my_team_top_speed_kmh', 'km/h'),
          withheld('enemy_top_speed_kmh', 'km/h'),
          withheld('my_team_sprints', 'sprints'),
          withheld('enemy_sprints', 'sprints'),
        ]}
      />,
    );
    const speedCard = within(container).getByText('Speed & Sprints').closest('div');
    expect(speedCard).toBeTruthy();
    expect(speedCard!.textContent).not.toContain('29.4');
    expect(speedCard!.textContent).not.toContain('28.2');
    expect(speedCard!.textContent).not.toMatch(/\b12\b/);
    expect(speedCard!.textContent).not.toMatch(/\b10\b/);
    expect(within(speedCard as HTMLElement).getByText('Unavailable')).toBeTruthy();
    expect(container.textContent).not.toContain('29.4 km/h');
    expect(container.textContent).not.toContain('28.2 km/h');
  });

  it('renders unknown PPDA as unavailable and labels shot quality as experimental', () => {
    const { container } = render(
      <StatsPanel
        stats={baseStats}
        benchmark={benchmarkTruthReady}
        shotSummary={shotSummary}
        metricAvailability={[
          {
            metric: 'my_team_ppda',
            definitionVersion: '1',
            value: null,
            availability: 'unknown',
            reasonCodes: ['ZERO_DENOMINATOR'],
          },
          {
            metric: 'enemy_ppda',
            definitionVersion: '1',
            value: null,
            availability: 'unknown',
            reasonCodes: ['ZERO_DENOMINATOR'],
          },
        ]}
      />,
    );
    const scoped = within(container);
    expect(scoped.getAllByText('Unavailable').length).toBeGreaterThanOrEqual(2);
    expect(scoped.getAllByText(/experimental shot quality/i).length).toBeGreaterThanOrEqual(1);
  });

  it('renders null PPDA without availability records as unavailable rather than a measured zero', () => {
    const { container } = render(
      <StatsPanel
        stats={{ ...baseStats, myTeamPpda: null, enemyPpda: null }}
        benchmark={benchmarkTruthReady}
        shotSummary={shotSummary}
      />,
    );
    const pressing = within(container).getByText('Pressing').closest('div');
    expect(pressing).toBeTruthy();
    expect(within(pressing as HTMLElement).getAllByText('Unavailable').length).toBeGreaterThanOrEqual(2);
    expect(pressing!.textContent).not.toContain('6.1');
  });

  it('does not recompute profile leaders when the profile array is unchanged', () => {
    const profiles = [...sampleProfiles];
    const iterate = profiles[Symbol.iterator].bind(profiles);
    let iterationCount = 0;
    Object.defineProperty(profiles, Symbol.iterator, {
      value: () => {
        iterationCount += 1;
        return iterate();
      },
    });

    const view = render(<StatsPanel stats={baseStats} playerProfiles={profiles} />);
    expect(iterationCount).toBe(3);

    view.rerender(<StatsPanel stats={{ ...baseStats }} playerProfiles={profiles} />);
    expect(iterationCount).toBe(3);
  });
});
