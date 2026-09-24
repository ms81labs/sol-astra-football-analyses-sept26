import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import CoachInsights, { loadPlaylistItemsForMatch } from './CoachInsights';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('CoachInsights', () => {
  it('renders player-focus leaders and evidence for tactical reports', () => {
    render(
      <CoachInsights
        activeTab="report"
        llmThinking={false}
        matchId="match-1"
        currentFrame={0}
        events={[]}
        tacticalReport={{
          attacking: 'Strong right-side progression',
          defensive: 'Compact block',
          pressing: 'Aggressive counterpress',
          key_player: 7,
          weaknesses: 'Rest defense after turnovers',
          rating: 8,
          summary: 'Positive attacking output',
          evidence: ['My team created 1.22 experimental shot quality from 2 high-value chances.'],
          event_summary: { eventCounts: { through_ball: 2 }, topPlayers: [] },
          player_focus: {
            topCreator: { trackId: 7, team: 'my_team', label: 'Primary Creator', summary: '2 through balls, 0.54 experimental shot quality created' },
          },
        }}
        drillResponse={null}
        onGenerateReport={vi.fn()}
        onGenerateDrills={vi.fn()}
      />,
    );

    expect(screen.getByText('Player Focus')).toBeTruthy();
    expect(screen.getByText('Primary Creator')).toBeTruthy();
    expect(screen.getByText('2 through balls, 0.54 experimental shot quality created')).toBeTruthy();
    expect(screen.getByText(/reviewed passages do not establish a whole-match frequency/i)).toBeTruthy();
  });

  it('renders drill evidence and player-focus context', () => {
    render(
      <CoachInsights
        activeTab="drills"
        llmThinking={false}
        matchId="match-1"
        currentFrame={0}
        events={[]}
        tacticalReport={null}
        drillResponse={{
          focus_area: 'Counterpress timing',
          drills: [
            {
              name: 'Wave Press',
              objective: 'Trigger the press earlier',
              setup: '6v4 in a narrowed middle third.',
              duration: '12 min',
            },
          ],
          evidence: ['Counterpress recovery time was 5.1s.'],
          player_focus: {
            topBallWinner: { trackId: 18, team: 'enemy', label: 'Ball Winner', summary: '3 ball wins, 2 interceptions' },
          },
        }}
        onGenerateReport={vi.fn()}
        onGenerateDrills={vi.fn()}
      />,
    );

    expect(screen.getByText('Why These Drills')).toBeTruthy();
    expect(screen.getAllByText('Player Focus').length).toBeGreaterThan(0);
    expect(screen.getByText('Ball Winner')).toBeTruthy();
  });

  it('opens the backend export URL from the report tab', () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);

    render(
      <CoachInsights
        activeTab="report"
        llmThinking={false}
        matchId="match-1"
        currentFrame={0}
        events={[]}
        tacticalReport={null}
        drillResponse={null}
        onGenerateReport={vi.fn()}
        onGenerateDrills={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText(/export html/i));

    expect(openSpy).toHaveBeenCalledWith('/api/matches/match-1/report/html', '_blank', 'noopener,noreferrer');
  });

  it('switches to a different single-match playlist before replaying events', async () => {
    const dispatchEvent = vi.fn();
    let resolveSwitch: () => void = () => {};
    const switchPromise = new Promise<void>((resolve) => {
      resolveSwitch = resolve;
    });
    const onSwitchMatch = vi.fn(() => switchPromise);

    const replayPromise = loadPlaylistItemsForMatch(
      [
        {
          annotationId: 'bundle-1',
          matchId: 'match-2',
          frameStart: 12,
          frameEnd: 12,
          timestampStart: 2.4,
          timestampEnd: 2.4,
          label: 'Switch me',
          description: 'Frame 12 - custom',
        },
        {
          annotationId: 'bundle-2',
          matchId: 'match-2',
          frameStart: 13,
          frameEnd: 13,
          timestampStart: 2.6,
          timestampEnd: 2.6,
          label: 'Replay me too',
          description: 'Frame 13 - custom',
        },
      ],
      {
        currentMatchId: 'match-1',
        onSwitchMatch,
        dispatchEvent,
      },
    );

    expect(onSwitchMatch).toHaveBeenCalledWith('match-2');
    expect(dispatchEvent).not.toHaveBeenCalled();

    resolveSwitch();
    const result = await replayPromise;

    expect(result.success).toBe(true);
    expect(dispatchEvent).toHaveBeenCalledTimes(2);
    expect(dispatchEvent.mock.calls[0][0].detail.frame).toBe(12);
    expect(dispatchEvent.mock.calls[1][0].detail.frame).toBe(13);
  });

  it('does not replay playlist events when its match switch is superseded', async () => {
    const dispatchEvent = vi.fn();

    const result = await loadPlaylistItemsForMatch(
      [
        {
          annotationId: 'bundle-1',
          matchId: 'match-b',
          frameStart: 12,
          frameEnd: 12,
          timestampStart: 2.4,
          timestampEnd: 2.4,
          label: 'Stale B event',
          description: 'Frame 12 - custom',
        },
      ],
      {
        currentMatchId: 'match-a',
        onSwitchMatch: async () => false,
        dispatchEvent,
      },
    );

    expect(result.success).toBe(false);
    expect(result.error).toMatch(/newer match/i);
    expect(dispatchEvent).not.toHaveBeenCalled();
  });

  it('rejects mixed-match playlists without dispatching events', async () => {
    const dispatchEvent = vi.fn();
    const onSwitchMatch = vi.fn();

    const result = await loadPlaylistItemsForMatch(
      [
        {
          annotationId: 'bundle-1',
          matchId: 'match-1',
          frameStart: 12,
          frameEnd: 12,
          timestampStart: 2.4,
          timestampEnd: 2.4,
          label: 'First match',
          description: 'Frame 12 - custom',
        },
        {
          annotationId: 'bundle-2',
          matchId: 'match-2',
          frameStart: 13,
          frameEnd: 13,
          timestampStart: 2.6,
          timestampEnd: 2.6,
          label: 'Second match',
          description: 'Frame 13 - custom',
        },
      ],
      {
        currentMatchId: 'match-1',
        onSwitchMatch,
        dispatchEvent,
      },
    );

    expect(result.success).toBe(false);
    expect(result.error).toMatch(/multiple matches/i);
    expect(onSwitchMatch).not.toHaveBeenCalled();
    expect(dispatchEvent).not.toHaveBeenCalled();
  });
});

it('C03 displays scoped zero, experimental and unavailable facts without inventing a rating', () => {
  render(<CoachInsights activeTab="report" llmThinking={false} matchId="m" generationId="N" currentFrame={0}
    events={[]} tacticalReport={{ matchId: 'm', generationId: 'N', status: 'historical', grounding: 'interpretive',
      metricClaims: [{ metric: 'shot_quality', value: 0, unit: 'score', availability: 'experimental', teamScope: 'my_team' }],
      metrics: [{ metric: 'distance', value: null, unit: 'm', availability: 'withheld' }],
      interpretation: '<script>unsafe()</script>',
      evidence: [{ matchId: 'm', generationId: 'N', kind: 'event', localId: '0' }],
    }} drillResponse={null} onGenerateReport={vi.fn()} onGenerateDrills={vi.fn()} />);
  expect(screen.getByText(/shot_quality/).textContent).toContain('0');
  expect(screen.getByText(/distance/).textContent).toContain('unavailable');
  expect(screen.getByText(/experimental/)).toBeTruthy();
  expect(document.querySelector('script')).toBeNull();
  expect(screen.getByText(/unsafe\(\)/)).toBeTruthy();
  expect(screen.queryByText(/out of 10/i)).toBeNull();
});

it('opens current claim evidence and leaves historical, metric and prose references noninteractive', () => {
  const onSelectEvidence = vi.fn();
  render(<CoachInsights activeTab="report" llmThinking={false} matchId="m" generationId="N" currentFrame={0}
    events={[]} tacticalReport={{ matchId: 'm', generationId: 'N',
      observations: [{ text: 'Turnover led to a shot', grounding: 'referenced', evidence: [
        { matchId: 'm', generationId: 'N', kind: 'event', localId: '12:turnover:2.4' },
        { matchId: 'm', generationId: 'old', kind: 'frame', localId: '12' },
        { matchId: 'm', generationId: 'N', kind: 'metric', localId: '0:shots' },
        'legacy reference',
      ] }],
    }} drillResponse={null} onSelectEvidence={onSelectEvidence}
    onGenerateReport={vi.fn()} onGenerateDrills={vi.fn()} />);
  fireEvent.click(screen.getByRole('button', { name: /event:12:turnover:2.4/i }));
  expect(onSelectEvidence).toHaveBeenCalledWith({ matchId: 'm', generationId: 'N', kind: 'event', localId: '12:turnover:2.4' });
  expect(screen.queryByRole('button', { name: /frame:12/i })).toBeNull();
  expect(screen.queryByRole('button', { name: /metric:0:shots/i })).toBeNull();
  expect(screen.queryByRole('button', { name: /legacy reference/i })).toBeNull();
});

it('C03 refuses silent loading of a playlist from another generation', async () => {
  const dispatchEvent = vi.fn();
  const result = await loadPlaylistItemsForMatch([{ annotationId: 'a', matchId: 'm', generationId: 'old',
    frameStart: 0, frameEnd: 0, timestampStart: 0, timestampEnd: 1, label: 'Old clip', description: '' }],
    { currentMatchId: 'm', currentGenerationId: 'N', dispatchEvent });
  expect(result.success).toBe(false);
  expect(result.error).toContain('historical or unverified');
  expect(dispatchEvent).not.toHaveBeenCalled();
});
