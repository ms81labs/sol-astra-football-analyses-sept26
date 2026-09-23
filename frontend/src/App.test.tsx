import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { FrameData, MatchRecord, MatchStats, ProcessingJob, RuntimeCapabilities } from './types';
import * as api from './utils/api';
import App, { formatJobStatus } from './App';

vi.mock('./utils/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./utils/api')>();
  return {
    ...actual,
    createMatchUpload: vi.fn(),
    createMatchAnnotation: vi.fn(),
    fetchMatchAnnotations: vi.fn(),
    fetchMatchIssues: vi.fn(),
    fetchMatches: vi.fn(),
    fetchMatchWorkspace: vi.fn(),
    fetchMatchFrames: vi.fn(),
    runMatchAnalysis: vi.fn(),
    updateMatchConfig: vi.fn(),
    waitForJobCompletion: vi.fn(),
  };
});

afterEach(() => {
  cleanup();
  sessionStorage.removeItem('ga_leftover_panels');
  vi.resetAllMocks();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

beforeEach(() => {
  sessionStorage.setItem('ga_leftover_panels', 'off');
  vi.mocked(api.fetchMatchAnnotations).mockResolvedValue([]);
  vi.mocked(api.fetchMatchIssues).mockResolvedValue([]);
});

type Workspace = Awaited<ReturnType<typeof api.fetchMatchWorkspace>>;

function readyMatch(id: string, name: string): MatchRecord {
  return { id, name, generationId: `g-${id}`, includedCommandIds: [], status: 'ready', inputMode: 'tracking_json', originalFilename: `${id}.json` };
}

function workspace(id: string, name: string, eventLabel?: string, possession = 50): Workspace {
  return {
    detail: readyMatch(id, name),
    frames: [],
    frameCount: 0,
    nextCursor: null,
    analytics: { summary: { ...reviewStats, possession }, formationTimeline: [], shots: [], ballAssignments: [] },
    events: eventLabel
      ? [{ type: 'turnover', frameId: 0, timestamp: 0, description: eventLabel }]
      : [],
    benchmark: null,
    evidence: null,
  };
}

function stubSnapshotWorkspace(value: Workspace, reviewedEvents = false) {
  const commandIds = ['accept-1', 'undo-1', 'c-pending', 'clip-1', 'clip-2', 'clip-pending', 'undo-clip-1',
    'undo-clip-2', 'swap-1', 'swap-old', 'undo-swap-1', 'join-1', 'validate-1'];
  vi.mocked(api.fetchMatchWorkspace).mockImplementation(async (_matchId, signal, generationId) => {
    const chosen = generationId ?? value.detail.generationId;
    if (chosen !== value.detail.generationId && chosen !== 'g-match-a-next') throw new Error('Unknown fixture generation');
    const events = generationId && reviewedEvents
      ? await api.fetchMatchEvents(value.detail.id, signal, generationId) : value.events;
    return { ...value, events, generationId: chosen,
      detail: { ...value.detail, generationId: chosen, includedCommandIds: commandIds } };
  });
}

function loadedWorkspace(id: string, name: string, eventLabel?: string, possession = 50): Workspace {
  return {
    ...workspace(id, name, eventLabel, possession),
    frames: [{ Frame_ID: 0, Timestamp: 0, Ball: null, My_Team: [], Enemies: [] }],
    frameCount: 1,
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

const reviewStats: MatchStats = {
  possession: 50,
  ballSignalStatus: 'trusted',
  ballSignalMessage: null,
  myTeamDistance: null,
  enemyDistance: null,
  myTeamAvgPos: null,
  enemyAvgPos: null,
  myTeamTopSpeed: null,
  enemyTopSpeed: null,
  myTeamSprints: null,
  enemySprints: null,
  myTeamXg: null,
  enemyXg: null,
  myTeamDefensiveLineHeight: null,
  enemyDefensiveLineHeight: null,
  myTeamDefensiveTeamLength: null,
  enemyDefensiveTeamLength: null,
  myTeamPpda: null,
  enemyPpda: null,
  myTeamHighPressRegains: null,
  enemyHighPressRegains: null,
  myTeamCounterpressRecoverySeconds: null,
  enemyCounterpressRecoverySeconds: null,
  formation: null,
};

function reviewWorkspace(): Workspace {
  const frame: FrameData = {
    Frame_ID: 0,
    Timestamp: 3.5,
    Ball: null,
    My_Team: [],
    Enemies: [],
  };
  return {
    detail: {
      id: 'match-review', generationId: 'g-match-review', includedCommandIds: [],
      name: 'Review Match',
      status: 'ready',
      inputMode: 'tracking_json',
      originalFilename: 'review.json',
    },
    frames: [frame],
    frameCount: 1,
    nextCursor: null,
    analytics: { summary: reviewStats, formationTimeline: [], shots: [], ballAssignments: [] },
    events: [],
    benchmark: null,
    evidence: null,
  };
}

const localOnlyCapabilities: RuntimeCapabilities = {
  analysisProviders: ['local'],
  defaultAnalysisProvider: 'local',
  pdfExportAvailable: false,
};

const cloudCapabilities: RuntimeCapabilities = {
  analysisProviders: ['local', 'cloud'],
  defaultAnalysisProvider: 'local',
  pdfExportAvailable: false,
};

function mockReadyReviewMatch() {
  vi.mocked(api.fetchMatches).mockResolvedValue([{
    id: 'match-review',
    name: 'Review Match',
    status: 'ready',
    inputMode: 'tracking_json',
    originalFilename: 'review.json',
  }]);
  vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(reviewWorkspace());
  vi.mocked(api.runMatchAnalysis).mockResolvedValue({ verdict: 'onside' });
}

function stubPitchCanvas() {
  const context = {
    arc: vi.fn(),
    beginPath: vi.fn(),
    clearRect: vi.fn(),
    closePath: vi.fn(),
    fill: vi.fn(),
    fillRect: vi.fn(),
    fillText: vi.fn(),
    lineTo: vi.fn(),
    moveTo: vi.fn(),
    scale: vi.fn(),
    setLineDash: vi.fn(),
    stroke: vi.fn(),
    strokeRect: vi.fn(),
  };
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context as unknown as CanvasRenderingContext2D);
  vi.spyOn(HTMLCanvasElement.prototype, 'getBoundingClientRect').mockReturnValue({
    bottom: 100,
    height: 100,
    left: 0,
    right: 100,
    top: 0,
    width: 100,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  });
}

describe('formatJobStatus', () => {
  it('shows the current job message and rounded progress', () => {
    expect(formatJobStatus({ progress: 0.475, message: 'Tracking players' } as ProcessingJob)).toBe('Tracking players (48%)');
  });
});

describe('App match workspace loading', () => {
  it('hydrates only the first of 100 ready matches at startup', async () => {
    stubPitchCanvas();
    const listedMatches = Array.from({ length: 100 }, (_, index) => readyMatch(`match-${index}`, `Match ${index}`));
    vi.mocked(api.fetchMatches).mockResolvedValue(listedMatches);
    vi.mocked(api.fetchMatchWorkspace).mockImplementation((matchId) => {
      const match = listedMatches.find(({ id }) => id === matchId)!;
      return Promise.resolve(loadedWorkspace(match.id, match.name));
    });

    render(<App />);

    await screen.findByText('Match 0', { selector: 'header span' });
    expect(api.fetchMatches).toHaveBeenCalledTimes(1);
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
    expect(api.fetchMatchWorkspace).toHaveBeenCalledWith('match-0', expect.any(AbortSignal));
    expect((screen.getByRole('combobox', { name: 'Active match' }) as HTMLSelectElement).options).toHaveLength(100);
    expect(screen.getByRole('combobox', { name: 'Comparison match' })).toBeTruthy();
  });

  it('loads heatmap availability from production HTTP and ignores claimed identity continuity', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      void init;
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/api/matches/match-a/heatmap'))).toBe(true);
    });
    const heatmapCall = fetchMock.mock.calls.find(([input]) => String(input).includes('/api/matches/match-a/heatmap'));
    expect(heatmapCall?.[1]?.method ?? 'GET').toBe('GET');
    expect(String(heatmapCall?.[0])).toContain('generationId=g-match-a');
    expect(heatmapCall?.[1]?.body ?? '').not.toContain('"identityContinuous":true');
    expect(screen.getByText(/whole-match heatmap withheld until identity continuity/i)).toBeTruthy();
  });

  it('derives speed and player-total overlays from production identity continuity', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace(loadedWorkspace('match-a', 'Match A'));
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo, init?: RequestInit) => {
      void init;
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            identityContinuous: true, geometryEligible: true, pitchDimensions: { pitchLengthM: 100, pitchWidthM: 60 },
            wholeMatch: true,
            intervalLimited: false,
            withheld: false,
            reasonCodes: [],
          }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    }));

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(screen.queryByText(/whole-match heatmap withheld until identity continuity/i)).toBeNull();
    });
    expect(screen.queryByText(/derived speeds withheld until identity continuity/i)).toBeNull();
    expect(screen.queryByText(/player physical totals withheld until identity continuity/i)).toBeNull();
  });

  it('passes production identity continuity into the selected player detail panel', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace({
      ...loadedWorkspace('match-a', 'Match A'),
      frames: [{
        Frame_ID: 0,
        Timestamp: 0,
        Ball: null,
        My_Team: [{ id: 7, x: 25, y: 40, conf: 1 }],
        Enemies: [],
      }],
      events: [{
        type: 'pass',
        frameId: 0,
        timestamp: 0,
        team: 'my_team',
        fromTrackId: 7,
        toTrackId: 8,
        description: 'Pass by track 7',
      }],
    });
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo, init?: RequestInit) => {
      void init;
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            identityContinuous: true, geometryEligible: true, pitchDimensions: { pitchLengthM: 100, pitchWidthM: 60 },
            wholeMatch: true,
            intervalLimited: false,
            withheld: false,
            reasonCodes: [],
          }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    }));

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(screen.queryByText(/whole-match heatmap withheld until identity continuity/i)).toBeNull();
    });
    fireEvent.click(screen.getByRole('img'), { clientX: 25, clientY: 40 });
    expect(screen.getByText('Track 7')).toBeTruthy();
    expect(screen.queryByText(/totals withheld until identity continuity/i)).toBeNull();
  });

  it('posts match-scoped identity join through production HTTP', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace({
      ...loadedWorkspace('match-a', 'Match A'),
      frames: [{
        Frame_ID: 0,
        Timestamp: 0,
        Ball: null,
        My_Team: [{ id: 7, x: 25, y: 40, conf: 1 }],
        Enemies: [],
      }],
      events: [{
        type: 'pass',
        frameId: 0,
        timestamp: 0,
        team: 'my_team',
        fromTrackId: 7,
        toTrackId: 8,
        description: 'Pass by track 7',
      }],
    });
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            identityContinuous: true, geometryEligible: true, pitchDimensions: { pitchLengthM: 100, pitchWidthM: 60 },
            wholeMatch: true,
            intervalLimited: false,
            withheld: false,
            reasonCodes: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/identity/repair') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            committed: true,
            preview: true,
            identityContinuous: false,
            silentlyReconnected: false,
            visionRerun: false,
            reasonCodes: [],
            correction: { correctionId: 'join-1', kind: 'track_join', saveState: 'saved', applyState: 'applied', appliedGeneration: 'g-match-a-next' },
          }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(screen.queryByText(/whole-match heatmap withheld until identity continuity/i)).toBeNull();
    });
    fireEvent.click(screen.getByRole('img'), { clientX: 25, clientY: 40 });
    expect(screen.getByText('Track 7')).toBeTruthy();
    fireEvent.change(screen.getByLabelText(/join from track/i), { target: { value: '19' } });
    fireEvent.click(screen.getByRole('button', { name: /join identity/i }));
    await waitFor(() => {
      const repairCall = fetchMock.mock.calls.find(([url]) => String(url).includes('/identity/repair'));
      expect(repairCall?.[1]?.body).toContain('"kind":"track_join"');
      expect(repairCall?.[1]?.body).toContain('"leftTrackId":"7"');
      expect(repairCall?.[1]?.body).toContain('"rightTrackId":"19"');
    });
    await waitFor(() => {
      expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(2);
    });
  });

  it('posts match-scoped identity validation through production HTTP', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace({
      ...loadedWorkspace('match-a', 'Match A'),
      frames: [{
        Frame_ID: 0,
        Timestamp: 0,
        Ball: null,
        My_Team: [{ id: 7, x: 25, y: 40, conf: 1 }],
        Enemies: [],
      }, { Frame_ID: 1, Timestamp: 0.2, Ball: null, My_Team: [{ id: 7, x: 26, y: 40, conf: 1 }], Enemies: [] }],
      frameCount: 2,
      events: [{
        type: 'pass',
        frameId: 0,
        timestamp: 0,
        team: 'my_team',
        fromTrackId: 7,
        toTrackId: 8,
        description: 'Pass by track 7',
      }],
    });
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/identity/promote') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            committed: true,
            preview: true,
            identityContinuous: true, geometryEligible: true, pitchDimensions: { pitchLengthM: 100, pitchWidthM: 60 },
            silentlyReconnected: false,
            visionRerun: false,
            reasonCodes: [],
            correction: { correctionId: 'validate-1', kind: 'identity_validate', saveState: 'saved', applyState: 'applied', appliedGeneration: 'g-match-a-next' },
          }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(screen.getByText(/whole-match heatmap withheld until identity continuity/i)).toBeTruthy();
    });
    fireEvent.click(screen.getByRole('img'), { clientX: 25, clientY: 40 });
    expect(screen.getByText('Track 7')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /approve visible track interval/i }));
    await waitFor(() => {
      const promoteCall = fetchMock.mock.calls.find(([url]) => String(url).includes('/identity/promote'));
      expect(promoteCall?.[1]?.body).toContain('"reviewed":true');
      expect(promoteCall?.[1]?.body).not.toContain('"identityContinuous":true');
    });
  });

  it('runs typed tactical search on stored match events without client-injected rows', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/queries') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            query: { unanswerable: false, reason: null, eventFamily: 'turnover' },
            results: [{ eventId: 'ev-1', timestamp: 12.4, evidenceIds: ['e-1'] }],
          }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    fireEvent.change(screen.getByLabelText(/^query$/i), { target: { value: 'show our second-half turnovers followed by a shot within 10 seconds' } });
    fireEvent.click(screen.getByRole('button', { name: /search evidence/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/matches/match-a/queries'))).toBe(true);
    });
    const queryCall = fetchMock.mock.calls.find(([url]) => String(url).includes('/api/matches/match-a/queries'));
    expect(queryCall?.[1]?.method).toBe('POST');
    expect(queryCall?.[1]?.body).toContain('"query":"show our second-half turnovers followed by a shot within 10 seconds"');
    expect(queryCall?.[1]?.body).not.toContain('"events"');
    expect(queryCall?.[1]?.body).not.toContain('"rows"');
    expect(await screen.findByText(/1 evidence-linked interval/i)).toBeTruthy();
  });

  it('shares a selected search interval with evidence, timeline and playlist', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace({
      ...loadedWorkspace('match-a', 'Match A'),
      frames: [0, 1.2, 2, 2.2].map((Timestamp, Frame_ID) => ({
        Frame_ID, Timestamp, Ball: null, My_Team: [], Enemies: [],
      })),
      frameCount: 4,
    });
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo, init?: RequestInit) => {
      if (String(input).includes('/api/matches/match-a/queries') && init?.method === 'POST') {
        return Promise.resolve({ ok: true, json: async () => ({
          generationId: 'g-match-a', query: { unanswerable: false },
          results: [{ eventId: 'ev-1', matchId: 'match-a', timestamp: 1.2,
            intervalStart: 1.1, intervalEnd: 2.1, evidenceIds: ['e-1'],
            label: 'turnover', reviewStatus: 'accepted' }],
        }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${String(input)}`));
    }));
    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    fireEvent.click(screen.getByRole('button', { name: /search evidence/i }));
    fireEvent.click(await screen.findByRole('button', { name: /turnover.*1.1.*2.1/i }));
    await waitFor(() => {
      expect((screen.getByLabelText(/clip start/i) as HTMLInputElement).value).toBe('1.1');
      expect((screen.getByLabelText(/clip end/i) as HTMLInputElement).value).toBe('2.1');
    });
    expect(screen.getByText(/selected evidence: e-1/i)).toBeTruthy();
    expect(within(screen.getByRole('region', { name: 'Evidence inspector' })).getAllByText('1.2s').length).toBeGreaterThan(0);
  });

  it('seeks a search hit by source frame and restores its range after a paged frame load', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace({ ...loadedWorkspace('match-a', 'Match A'), frameCount: 10 });
    vi.mocked(api.fetchMatchFrames).mockResolvedValue({
      generationId: 'g-match-a', frameCount: 10, nextCursor: null,
      frames: [7, 8, 9].map((Frame_ID) => ({ Frame_ID, Timestamp: Frame_ID / 5,
        Ball: null, My_Team: [], Enemies: [] })),
    });
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo, init?: RequestInit) => {
      if (String(input).includes('/api/matches/match-a/queries') && init?.method === 'POST') {
        return Promise.resolve({ ok: true, json: async () => ({
          generationId: 'g-match-a', query: { unanswerable: false },
          results: [{ eventId: 'ev-7', matchId: 'match-a', frameId: 7, timestamp: 1.4,
            intervalStart: 1.4, intervalEnd: 1.8, evidenceIds: ['e-7'], label: 'turnover' }],
        }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${String(input)}`));
    }));
    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    fireEvent.click(screen.getByRole('button', { name: /search evidence/i }));
    fireEvent.click(await screen.findByRole('button', { name: /turnover.*1.4.*1.8/i }));
    await waitFor(() => expect(api.fetchMatchFrames).toHaveBeenCalledWith('match-a', expect.objectContaining({
      afterFrame: 7, generationId: 'g-match-a',
    })));
    expect(await screen.findByText('7 - 8')).toBeTruthy();
    expect((screen.getByLabelText(/clip start/i) as HTMLInputElement).value).toBe('1.4');
  });

  it('refreshes stored events after accept without rewriting the playhead or injecting event ids', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace({
      ...loadedWorkspace('match-a', 'Match A'),
      events: [{
        type: 'pass',
        frameId: 0,
        timestamp: 0,
        team: 'my_team',
        fromTrackId: 7,
        toTrackId: 8,
        description: 'Pass by track 7',
        reviewStatus: 'unreviewed',
      }],
    }, true);
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && init?.method === 'POST' && !String(url).includes('/undo')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', correctionId: 'accept-1', saveState: 'saved', applyState: 'applied', appliedGeneration: 'g-match-a-next', kind: 'event_accept' }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/events') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            events: [{
              type: 'pass',
              frameId: 0,
              timestamp: 0,
              team: 'my_team',
              fromTrackId: 7,
              toTrackId: 8,
              description: 'Pass by track 7',
              reviewStatus: 'accepted',
            }],
          }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    expect(screen.getByText('unreviewed')).toBeTruthy();
    fireEvent.keyDown(window, { key: 'a' });
    await waitFor(() => {
      const acceptCall = fetchMock.mock.calls.find(([url, init]) => (
        String(url).includes('/api/matches/match-a/corrections')
        && !String(url).includes('/undo')
        && init?.method === 'POST'
      ));
      expect(acceptCall?.[1]?.body).toContain('"kind":"event_accept"');
      expect(acceptCall?.[1]?.body).toContain('"frame":0');
      expect(acceptCall?.[1]?.body).toContain('"type":"pass"');
      expect(acceptCall?.[1]?.body).not.toContain('"eventId"');
    });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/events')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(2);
    expect(await screen.findByText('accepted')).toBeTruthy();
  });

  it('posts stored undo from keyboard z after accept without rewriting the playhead', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace({
      ...loadedWorkspace('match-a', 'Match A'),
      events: [{
        type: 'pass',
        frameId: 0,
        timestamp: 0,
        team: 'my_team',
        fromTrackId: 7,
        toTrackId: 8,
        description: 'Pass by track 7',
        reviewStatus: 'unreviewed',
      }],
    }, true);
    let undone = false;
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections/accept-1/undo') && init?.method === 'POST') {
        undone = true;
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', correctionId: 'undo-1', saveState: 'saved', applyState: 'applied', appliedGeneration: 'g-match-a-next', undoOf: 'accept-1' }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && init?.method === 'POST' && !String(url).includes('/undo')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', correctionId: 'accept-1', saveState: 'saved', applyState: 'applied', appliedGeneration: 'g-match-a-next', kind: 'event_accept' }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/events') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            events: [{
              type: 'pass',
              frameId: 0,
              timestamp: 0,
              team: 'my_team',
              fromTrackId: 7,
              toTrackId: 8,
              description: 'Pass by track 7',
              reviewStatus: undone ? 'unreviewed' : 'accepted',
            }],
          }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    fireEvent.keyDown(window, { key: 'a' });
    await screen.findByRole('button', { name: 'Undo accept-1' });
    expect(await screen.findByText('accepted')).toBeTruthy();
    fireEvent.keyDown(window, { key: 'z' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/corrections/accept-1/undo')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    await waitFor(() => {
      const eventGets = fetchMock.mock.calls.filter(([url, init]) => (
        String(url).includes('/api/matches/match-a/events')
        && (!init?.method || init.method === 'GET')
      ));
      expect(eventGets.length).toBeGreaterThanOrEqual(2);
    });
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(3);
    expect(await screen.findByText('unreviewed')).toBeTruthy();
  });

  it('recovers a pending event correction on the loaded match without rewriting the playhead', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace({
      ...loadedWorkspace('match-a', 'Match A'),
      events: [{
        type: 'pass',
        frameId: 0,
        timestamp: 0,
        team: 'my_team',
        fromTrackId: 7,
        toTrackId: 8,
        description: 'Pass by track 7',
        reviewStatus: 'unreviewed',
      }],
    }, true);
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            items: [{ correctionId: 'c-pending', kind: 'event_accept', saveState: 'pending' }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections/c-pending/recover') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', correctionId: 'c-pending', saveState: 'saved', applyState: 'applied', appliedGeneration: 'g-match-a-next', kind: 'event_accept' }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/events') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            events: [{
              type: 'pass',
              frameId: 0,
              timestamp: 0,
              team: 'my_team',
              fromTrackId: 7,
              toTrackId: 8,
              description: 'Pass by track 7',
              reviewStatus: 'accepted',
            }],
          }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    expect(screen.getByText('unreviewed')).toBeTruthy();
    fireEvent.click(await screen.findByRole('button', { name: /recover pending correction/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/corrections/c-pending/recover')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/events')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(2);
    expect(await screen.findByText('accepted')).toBeTruthy();
    expect(await screen.findByText(/^Edit applied/)).toBeTruthy();
  });

  it('loads stored undoable correction history without requiring an in-session edit', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace({
      ...loadedWorkspace('match-a', 'Match A'),
      events: [{
        type: 'pass',
        frameId: 0,
        timestamp: 0,
        team: 'my_team',
        fromTrackId: 7,
        toTrackId: 8,
        description: 'Pass by track 7',
        reviewStatus: 'accepted',
      }],
    }, true);
    let undone = false;
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections/accept-1/undo') && init?.method === 'POST') {
        undone = true;
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', correctionId: 'undo-1', saveState: 'saved', applyState: 'applied', appliedGeneration: 'g-match-a-next', undoOf: 'accept-1' }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            items: [{
              correctionId: 'accept-1',
              kind: 'event_accept',
              saveState: 'saved', applyState: 'applied', appliedGeneration: 'g-match-a-next',
              author: 'analyst',
              undoOf: null,
            }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/events') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            events: [{
              type: 'pass',
              frameId: 0,
              timestamp: 0,
              team: 'my_team',
              fromTrackId: 7,
              toTrackId: 8,
              description: 'Pass by track 7',
              reviewStatus: undone ? 'unreviewed' : 'accepted',
            }],
          }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    expect(await screen.findByRole('button', { name: 'Undo accept-1' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Undo accept-1' }).closest('li')?.textContent).toContain('analyst');
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: 'Undo accept-1' }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/corrections/accept-1/undo')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/events')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(2);
    expect(await screen.findByText('unreviewed')).toBeTruthy();
  });

  it('exports the marked review range as a half-open source interval without claiming whole-match frequency', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/playlists/export-interval') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            sourceStartSeconds: 0,
            sourceEndSeconds: 0.2,
            sourceEndFrameExclusive: 1,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && init?.method === 'POST' && !String(url).includes('/undo') && !String(url).includes('/recover')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', correctionId: 'clip-1', saveState: 'saved', applyState: 'applied', appliedGeneration: 'g-match-a-next', kind: 'playlist_item', payload: JSON.parse(String(init?.body)).payload }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    fireEvent.keyDown(window, { key: 'i' });
    fireEvent.keyDown(window, { key: 'o' });
    await waitFor(() => {
      expect((screen.getByLabelText(/clip start/i) as HTMLInputElement).value).toBe('0');
      expect((screen.getByLabelText(/clip end/i) as HTMLInputElement).value).toBe('0.2');
    });
    fireEvent.click(screen.getByRole('button', { name: /add clip/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/playlists/export-interval'))).toBe(true);
    });
    const exportCall = fetchMock.mock.calls.find(([url]) => String(url).includes('/api/playlists/export-interval'));
    expect(exportCall?.[1]?.method).toBe('POST');
    expect(exportCall?.[1]?.body).toContain('"timestampStart":0');
    expect(exportCall?.[1]?.body).toContain('"timestampEnd":0.2');
    expect(exportCall?.[1]?.body).toContain('"sourceFps":5');
    expect(exportCall?.[1]?.body).not.toContain('"sourceFps":25');
    expect(await screen.findByText(/0s to 0.2s/)).toBeTruthy();
    expect(screen.getByText(/frame 1 exclusive/i)).toBeTruthy();
    expect(screen.getByText(/do not establish a whole-match frequency/i)).toBeTruthy();
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/corrections')
        && init?.method === 'POST'
        && !String(url).includes('/undo')
      ))).toBe(true);
    });
    const clipCall = fetchMock.mock.calls.find(([url, init]) => (
      String(url).includes('/api/matches/match-a/corrections')
      && init?.method === 'POST'
      && !String(url).includes('/undo')
    ));
    expect(clipCall?.[1]?.body).toContain('"kind":"playlist_item"');
    expect(clipCall?.[1]?.body).toContain('"timestampStart":0');
    expect(clipCall?.[1]?.body).toContain('"timestampEnd":0.2');
    expect(clipCall?.[1]?.body).not.toContain('"events"');
    expect(clipCall?.[1]?.body).not.toContain('"eventId"');
    expect(await screen.findByRole('button', { name: 'Undo clip-1' })).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(2);
  });

  it('opens the exported playlist source interval on the review timeline', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace({
      ...loadedWorkspace('match-a', 'Match A'),
      frames: [0, 1, 2].map((Frame_ID) => ({
        Frame_ID,
        Timestamp: Frame_ID * 0.2,
        Ball: null,
        My_Team: [],
        Enemies: [],
      })),
      frameCount: 3,
    });
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/playlists/export-interval') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            sourceStartSeconds: 0,
            sourceEndSeconds: 0.2,
            sourceEndFrameExclusive: 1,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && init?.method === 'POST' && !String(url).includes('/undo') && !String(url).includes('/recover')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', correctionId: 'clip-1', saveState: 'saved', applyState: 'applied', appliedGeneration: 'g-match-a-next', kind: 'playlist_item', payload: JSON.parse(String(init?.body)).payload }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    fireEvent.keyDown(window, { key: 'i' });
    fireEvent.keyDown(window, { key: 'o' });
    await waitFor(() => {
      expect((screen.getByLabelText(/clip start/i) as HTMLInputElement).value).toBe('0');
      expect((screen.getByLabelText(/clip end/i) as HTMLInputElement).value).toBe('0.2');
    });
    fireEvent.change(screen.getByLabelText('Timeline scrubber'), { target: { value: '2' } });
    expect((screen.getByLabelText('Timeline scrubber') as HTMLInputElement).value).toBe('2');
    fireEvent.click(screen.getByRole('button', { name: /add clip/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/playlists/export-interval'))).toBe(true);
    });
    await waitFor(() => {
      expect((screen.getByLabelText('Timeline scrubber') as HTMLInputElement).value).toBe('0');
    });
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(2);
  });

  it('recovers a pending playlist clip on the loaded match without rewriting the playhead', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            items: [{
              correctionId: 'clip-pending',
              kind: 'playlist_item',
              saveState: 'pending',
              payload: {
                timestampStart: 0,
                timestampEnd: 0.2,
                sourceEndFrameExclusive: 1,
                notes: 'recovered clip',
              },
            }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections/clip-pending/recover') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', correctionId: 'clip-pending', saveState: 'saved', applyState: 'applied', appliedGeneration: 'g-match-a-next', kind: 'playlist_item', payload: { timestampStart: 0, timestampEnd: 0.2, sourceEndFrameExclusive: 1, notes: 'recovered clip' } }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    fireEvent.click(await screen.findByRole('button', { name: /recover pending correction/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/corrections/clip-pending/recover')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    expect(await screen.findByRole('button', { name: 'Undo clip-pending' })).toBeTruthy();
    expect(await screen.findByText(/0s to 0.2s/)).toBeTruthy();
    expect(screen.getByText(/frame 1 exclusive/i)).toBeTruthy();
    expect(screen.getByText(/recovered clip/)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls.some(([url]) => (
      String(url).includes('/api/matches/match-a/events')
      && !String(url).includes('/partition')
    ))).toBe(false);
  });

  it('undos a stored playlist clip without rewriting the playhead', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections/clip-1/undo') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', correctionId: 'undo-clip-1', saveState: 'saved', applyState: 'applied', appliedGeneration: 'g-match-a-next', undoOf: 'clip-1' }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            items: [{
              correctionId: 'clip-1',
              kind: 'playlist_item',
              saveState: 'saved', applyState: 'applied', appliedGeneration: 'g-match-a-next',
              undoOf: null,
              author: 'analyst',
            }],
          }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    fireEvent.click(await screen.findByRole('button', { name: 'Undo clip-1' }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/corrections/clip-1/undo')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    expect(await screen.findByText(/undo of clip-1/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls.some(([url]) => (
      String(url).includes('/api/matches/match-a/events')
      && !String(url).includes('/partition')
    ))).toBe(false);
  });

  it('loads stored playlist clips into the review builder without undone items', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            items: [
              {
                correctionId: 'clip-1',
                kind: 'playlist_item',
                saveState: 'saved', applyState: 'applied', appliedGeneration: 'g-match-a-next',
                undoOf: null,
                author: 'analyst',
                payload: {
                  timestampStart: 0,
                  timestampEnd: 0.2,
                  sourceEndFrameExclusive: 1,
                  notes: 'turnover then shot',
                },
              },
              {
                correctionId: 'clip-undone',
                kind: 'playlist_item',
                saveState: 'saved', applyState: 'applied', appliedGeneration: 'g-match-a-next',
                undoOf: null,
                payload: {
                  timestampStart: 12,
                  timestampEnd: 14,
                  sourceEndFrameExclusive: 70,
                },
              },
              {
                correctionId: 'undo-clip-undone',
                kind: 'playlist_item',
                saveState: 'saved', applyState: 'applied', appliedGeneration: 'g-match-a-next',
                undoOf: 'clip-undone',
                payload: { undo: { timestampStart: 12, timestampEnd: 14 } },
              },
            ],
          }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    expect(await screen.findByText(/0s to 0.2s/)).toBeTruthy();
    expect(screen.getByText(/frame 1 exclusive/i)).toBeTruthy();
    expect(screen.getByText(/turnover then shot/)).toBeTruthy();
    expect(screen.queryByText(/12s to 14s/)).toBeNull();
    expect(screen.queryByText(/frame 70 exclusive/i)).toBeNull();
    expect(screen.getByRole('button', { name: 'Undo clip-1' })).toBeTruthy();
    expect(screen.getByText(/do not establish a whole-match frequency/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('opens a stored playlist clip on the review source interval', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace({
      ...loadedWorkspace('match-a', 'Match A'),
      frames: [0, 1, 2].map((Frame_ID) => ({
        Frame_ID,
        Timestamp: Frame_ID * 0.2,
        Ball: null,
        My_Team: [],
        Enemies: [],
      })),
      frameCount: 3,
    });
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            items: [{
              correctionId: 'clip-1',
              kind: 'playlist_item',
              saveState: 'saved', applyState: 'applied', appliedGeneration: 'g-match-a-next',
              undoOf: null,
              author: 'analyst',
              payload: {
                timestampStart: 0.2,
                timestampEnd: 0.4,
                sourceEndFrameExclusive: 2,
                notes: 'second passage',
              },
            }],
          }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    expect((screen.getByLabelText('Timeline scrubber') as HTMLInputElement).value).toBe('0');
    fireEvent.click(await screen.findByRole('button', { name: /open 0\.2s to 0\.4s/i }));
    expect((screen.getByLabelText('Timeline scrubber') as HTMLInputElement).value).toBe('1');
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads the stored playlist as a source-linked edit list without re-encoding the match', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            reencodeFullMatch: false,
            renderOnDemand: true,
            intervals: [[0, 0.2]],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            items: [{
              correctionId: 'clip-1',
              kind: 'playlist_item',
              saveState: 'saved', applyState: 'applied', appliedGeneration: 'g-match-a-next',
              undoOf: null,
              payload: { timestampStart: 0, timestampEnd: 0.2, sourceEndFrameExclusive: 1 },
            }],
          }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/edits')
        && (!init?.method || init.method === 'GET')
        && !String(url).includes('/render')
      ))).toBe(true);
    });
    expect(await screen.findByText(/render on demand/i)).toBeTruthy();
    expect(screen.getByText(/does not re-encode the full match/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('renders a stored playlist interval on demand without re-encoding the full match', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace({
      ...loadedWorkspace('match-a', 'Match A'),
      frames: [0, 1, 2].map((Frame_ID) => ({
        Frame_ID,
        Timestamp: Frame_ID * 0.2,
        Ball: null,
        My_Team: [],
        Enemies: [],
      })),
      frameCount: 3,
    });
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/playlists/export-interval') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            sourceStartSeconds: 0,
            sourceEndSeconds: 0.2,
            sourceEndFrameExclusive: 1,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits/render') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            interval: [0, 0.2],
            reencodedFullMatch: false,
            sourceSha256: 'stored-source',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && init?.method === 'POST' && !String(url).includes('/undo') && !String(url).includes('/recover')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', correctionId: 'clip-1', saveState: 'saved', applyState: 'applied', appliedGeneration: 'g-match-a-next', kind: 'playlist_item', payload: JSON.parse(String(init?.body)).payload }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    fireEvent.keyDown(window, { key: 'i' });
    fireEvent.keyDown(window, { key: 'o' });
    await waitFor(() => {
      expect((screen.getByLabelText(/clip start/i) as HTMLInputElement).value).toBe('0');
      expect((screen.getByLabelText(/clip end/i) as HTMLInputElement).value).toBe('0.2');
    });
    fireEvent.click(screen.getByRole('button', { name: /add clip/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/edits/render')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    const renderCall = fetchMock.mock.calls.find(([url, init]) => (
      String(url).includes('/api/matches/match-a/edits/render')
      && init?.method === 'POST'
    ));
    expect(renderCall?.[1]?.body).toContain('"start":0');
    expect(renderCall?.[1]?.body).toContain('"end":0.2');
    expect(renderCall?.[1]?.body).not.toContain('"reencodedFullMatch":true');
    const playlist = within(await screen.findByRole('region', { name: /playlist builder/i }));
    expect(playlist.getByText(/rendered interval on demand/i)).toBeTruthy();
    expect(playlist.getByText(/reencodedFullMatch is false/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(2);
  });

  it('maps source presentation time to match clock without claiming frame-accurate overlay', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace({
      ...loadedWorkspace('match-a', 'Match A'),
      frames: [{ Frame_ID: 0, Timestamp: 0.2, Ball: null, My_Team: [], Enemies: [] }],
      frameCount: 1,
    });
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            presentationTimeSeconds: 0,
            matchClockSeconds: 45,
            explicitMapping: true,
            frameAccurateOverlay: false,
            sourceClockRecorded: true,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            replacesOriginal: false,
            originalRetained: true,
            assets: { proxy: { kind: 'browsing_proxy' }, thumbnails: { kind: 'thumbnails' }, waveform: { kind: 'waveform' } },
            ptsMap: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', items: [] }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/clock')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    const sourceLine = await screen.findByText(/source presentation time/i);
    expect(sourceLine.textContent).toContain('0.2s');
    expect(screen.getByText(/match clock/i).textContent).toContain('45.2s');
    expect(screen.getByText(/does not make a timestamp overlay frame-accurate/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads the stored match package with coverage limitations and no credentials', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            analyst: {
              playlist: [{ timestampStart: 0, timestampEnd: 0.2 }],
              events: [],
              metrics: [{ metric: 'my_team_distance_m', availability: 'unknown' }],
              coverage: { unknownMetrics: [{ metric: 'my_team_distance_m', availability: 'unknown' }] },
              limitations: [
                'Independent labels 0/18 complete.',
                'Physical metrics withheld until identity and calibration gates pass.',
              ],
            },
            operator: {
              manifest: { schema: 'match_package_v1' },
              secretsAdmitted: true,
              cleanupStatus: 'not_required',
            },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            replacesOriginal: false,
            originalRetained: true,
            assets: { proxy: { kind: 'browsing_proxy' }, thumbnails: { kind: 'thumbnails' }, waveform: { kind: 'waveform' } },
            ptsMap: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', items: [] }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/package')
        && (!init?.method || init.method === 'GET')
        && !String(url).includes('/api/reports/assemble')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/reports/assemble'))).toBe(false);
    expect(await screen.findByText(/coverage and limitations/i)).toBeTruthy();
    expect(screen.getByText(/independent labels 0\/18/i)).toBeTruthy();
    expect(screen.getByText(/versioned report match_package_v1/i)).toBeTruthy();
    expect(screen.getByText(/does not expose credentials/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('inspects stored match metrics as unavailable without inventing zero', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics/inspect/my_team_distance_m') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            metric: 'my_team_distance_m',
            unit: 'metres',
            denominator: 'identity_continuous_eligible_seconds',
            definitionVersion: '1',
            eligibleDuration: 0,
            exclusions: ['IDENTITY_DISCONTINUITY'],
            rendered: 'unavailable',
            publishedValue: null,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/setup') && !url.includes('/preview') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            cameraProfile: 'stitched_panoramic_view',
            automationAdmitted: false,
            manualTaggingPermitted: true,
            certified: false,
            cannotMeasure: ['physical_metrics'],
            pitchLengthM: null,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/rates') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            exportFpsEqualsInferenceFps: false,
            notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            replacesOriginal: false,
            originalRetained: true,
            assets: { proxy: { kind: 'browsing_proxy' }, thumbnails: { kind: 'thumbnails' }, waveform: { kind: 'waveform' } },
            ptsMap: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', items: [] }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/metrics/inspect/my_team_distance_m')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) => (
      String(url).includes('/api/metrics/inspect/')
      && !String(url).includes('/api/matches/')
    ))).toBe(false);
    expect(await screen.findByText(/metric inspector/i)).toBeTruthy();
    const inspector = within(screen.getByRole('region', { name: /metric inspector/i }));
    expect(inspector.getByText(/identity_continuous_eligible_seconds/)).toBeTruthy();
    expect(inspector.getByText('Unavailable')).toBeTruthy();
    expect(inspector.getByText(/IDENTITY_DISCONTINUITY/)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored report coverage without claiming the whole match', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/coverage') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            coverageAware: true,
            representsWholeMatch: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics/inspect/my_team_distance_m') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            metric: 'my_team_distance_m',
            unit: 'metres',
            denominator: 'identity_continuous_eligible_seconds',
            definitionVersion: '1',
            eligibleDuration: 0,
            exclusions: ['IDENTITY_DISCONTINUITY'],
            rendered: 'unavailable',
            publishedValue: null,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/setup') && !url.includes('/preview') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            cameraProfile: 'stitched_panoramic_view',
            automationAdmitted: false,
            manualTaggingPermitted: true,
            certified: false,
            cannotMeasure: ['physical_metrics'],
            pitchLengthM: null,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/rates') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            exportFpsEqualsInferenceFps: false,
            notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            replacesOriginal: false,
            originalRetained: true,
            assets: { proxy: { kind: 'browsing_proxy' }, thumbnails: { kind: 'thumbnails' }, waveform: { kind: 'waveform' } },
            ptsMap: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', items: [] }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/reports/coverage')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(await screen.findByText(/coverage-aware/i)).toBeTruthy();
    expect(screen.getByText(/does not represent the whole match/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored match metrics without inventing zero physical totals', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics/inspect/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            metric: 'my_team_distance_m',
            unit: 'metres',
            denominator: 'identity_continuous_eligible_seconds',
            definitionVersion: '1',
            eligibleDuration: 0,
            exclusions: ['IDENTITY_DISCONTINUITY'],
            rendered: 'unavailable',
            publishedValue: null,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            metrics: [{
              metric: 'my_team_distance_m',
              availability: 'unknown',
              value: null,
              reasonCodes: ['IDENTITY_DISCONTINUITY'],
              unit: 'metres',
              denominator: 'identity_continuous_eligible_seconds',
              definitionVersion: '1',
            }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/package') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            level: 0,
            clips: [],
            notes: [],
            bookmarks: [],
            decision: null,
            validatedMeasurement: false,
            reasonCodes: ['IFAB_LAW_11_NOT_APPLIED', 'MANUAL_INCIDENT_PACKAGE'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/geometry') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            decision: null,
            validatedMeasurement: false,
            reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            mode: 'unknown',
            reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/promotion') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            completeMatchAccepted: false,
            stageBenchmarkIsCompleteMatchAcceptance: false,
            outputQuality: 'unproven',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            namespace: 'production',
            compatibleWithDevelopment: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/privacy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            cloudAllowed: false,
            localProcessingRequired: true,
            faceRecognition: false,
            crossSeasonIdentity: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/history') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            undoable: true,
            rewrotePastOutcomes: false,
            items: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/quality')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            accepted: true,
            reasonCodes: [],
            missingEvidenceIds: [],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/coverage') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            coverageAware: true,
            representsWholeMatch: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/setup') && !url.includes('/preview') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            cameraProfile: 'stitched_panoramic_view',
            automationAdmitted: false,
            manualTaggingPermitted: true,
            certified: false,
            cannotMeasure: ['physical_metrics'],
            pitchLengthM: null,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/rates') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            exportFpsEqualsInferenceFps: false,
            notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            replacesOriginal: false,
            originalRetained: true,
            assets: { proxy: { kind: 'browsing_proxy' }, thumbnails: { kind: 'thumbnails' }, waveform: { kind: 'waveform' } },
            ptsMap: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a', items: [] }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/metrics')
        && !String(url).includes('/inspect')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('"identityContinuous":true'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/workbench/dev/matches/match-a/metrics'))).toBe(false);
    const storedMetrics = within(await screen.findByRole('region', { name: /stored match metrics/i }));
    expect(storedMetrics.getByText(/withhold physical totals/i)).toBeTruthy();
    expect(storedMetrics.getByText(/IDENTITY_DISCONTINUITY/)).toBeTruthy();
    expect(storedMetrics.getByText(/published value is not an invented 0/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('swaps stored teams on the loaded match without a vision rerun', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && init?.method === 'POST' && !String(url).includes('/undo')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            correctionId: 'swap-1',
            saveState: 'saved', applyState: 'applied', appliedGeneration: 'g-match-a-next',
            kind: 'team_mapping',
            rebuild: ['team_state', 'events', 'metrics', 'report'],
            visionRerun: false,
          }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    fireEvent.click(screen.getByRole('button', { name: /swap teams/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/matches/match-a/corrections'))).toBe(true);
    });
    const swapCall = fetchMock.mock.calls.find(([url, init]) => (
      String(url).includes('/api/matches/match-a/corrections')
      && !String(url).includes('/undo')
      && init?.method === 'POST'
    ));
    expect(swapCall?.[1]?.body).toContain('"kind":"team_mapping"');
    expect(swapCall?.[1]?.body).toContain('"swap":true');
    expect(swapCall?.[1]?.body).not.toContain('"visionRerun":true');
    expect(swapCall?.[1]?.body).not.toContain('"frames"');
    await waitFor(() => {
      expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(2);
    });
  });

  it('reloads stored workspace after undoing a team mapping without rewriting the original correction', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    stubSnapshotWorkspace(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections/swap-1/undo') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            correctionId: 'undo-1',
            saveState: 'saved', applyState: 'applied', appliedGeneration: 'g-match-a-next',
            undoOf: 'swap-1',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ generationId: new URL(url, 'http://localhost').searchParams.get('generationId') ?? 'g-match-a',
            correctionId: 'swap-1',
            saveState: 'saved', applyState: 'applied', appliedGeneration: 'g-match-a-next',
            kind: 'team_mapping',
            rebuild: ['team_state', 'events', 'metrics', 'report'],
            visionRerun: false,
          }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    fireEvent.click(screen.getByRole('button', { name: /swap teams/i }));
    const undo = await screen.findByRole('button', { name: 'Undo swap-1' });
    await waitFor(() => {
      expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(2);
    });
    fireEvent.click(undo);
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/corrections/swap-1/undo'))).toBe(true);
    });
    const undoCall = fetchMock.mock.calls.find(([url]) => String(url).includes('/corrections/swap-1/undo'));
    expect(undoCall?.[1]?.method).toBe('POST');
    await waitFor(() => {
      expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(3);
    });
    expect(screen.getByText(/undo of swap-1/i)).toBeTruthy();
    expect(screen.getByText(/original correction retained/i)).toBeTruthy();
  });

  it('loads a selected match once and does not reload the active match', async () => {
    stubPitchCanvas();
    const listedMatches = [readyMatch('match-a', 'Match A'), readyMatch('match-b', 'Match B')];
    vi.mocked(api.fetchMatches).mockResolvedValue(listedMatches);
    vi.mocked(api.fetchMatchWorkspace).mockImplementation((matchId) => {
      const match = listedMatches.find(({ id }) => id === matchId)!;
      return Promise.resolve(loadedWorkspace(match.id, match.name));
    });

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    const activeSelector = screen.getAllByRole('combobox')[0];

    fireEvent.change(activeSelector, { target: { value: 'match-b' } });
    await screen.findByText('Match B', { selector: 'header span' });
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(2);
    expect(api.fetchMatchWorkspace).toHaveBeenLastCalledWith('match-b', undefined);

    fireEvent.change(activeSelector, { target: { value: 'match-b' } });
    await act(async () => Promise.resolve());
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(2);
  });

  it('closes the selected player when the active match changes', async () => {
    stubPitchCanvas();
    const listedMatches = [readyMatch('match-a', 'Match A'), readyMatch('match-b', 'Match B')];
    vi.mocked(api.fetchMatches).mockResolvedValue(listedMatches);
    vi.mocked(api.fetchMatchWorkspace).mockImplementation((matchId) => {
      const match = listedMatches.find(({ id }) => id === matchId)!;
      const loaded = loadedWorkspace(match.id, match.name);
      if (matchId === 'match-b') return Promise.resolve(loaded);
      return Promise.resolve({
        ...loaded,
        frames: [{
          Frame_ID: 0,
          Timestamp: 0,
          Ball: null,
          My_Team: [{ id: 7, x: 25, y: 40, conf: 1 }],
          Enemies: [],
        }],
        events: [{
          type: 'pass',
          frameId: 0,
          timestamp: 0,
          team: 'my_team',
          fromTrackId: 7,
          toTrackId: 8,
          description: 'Pass by track 7',
        }],
      });
    });

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    fireEvent.click(screen.getByRole('img'), { clientX: 25, clientY: 40 });
    expect(screen.getByText('Track 7')).toBeTruthy();

    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: 'match-b' } });
    await screen.findByText('Match B', { selector: 'header span' });

    expect(screen.queryByText('Track 7')).toBeNull();
  });

  it('keeps the active match and choices usable after another match fails to load', async () => {
    stubPitchCanvas();
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const listedMatches = [
      readyMatch('match-a', 'Match A'),
      readyMatch('match-b', 'Match B'),
      readyMatch('match-c', 'Match C'),
    ];
    vi.mocked(api.fetchMatches).mockResolvedValue(listedMatches);
    vi.mocked(api.fetchMatchWorkspace).mockImplementation((matchId) => {
      if (matchId === 'match-b') return Promise.reject(new Error('Match B unavailable'));
      const match = listedMatches.find(({ id }) => id === matchId)!;
      return Promise.resolve(loadedWorkspace(match.id, match.name));
    });

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    const activeSelector = screen.getAllByRole('combobox')[0] as HTMLSelectElement;

    fireEvent.change(activeSelector, { target: { value: 'match-b' } });
    expect((await screen.findByRole('alert')).textContent).toContain('Match B unavailable');
    expect(screen.getByText('Match A', { selector: 'header span' })).toBeTruthy();
    expect(Array.from(activeSelector.options).map(({ value }) => value)).toEqual(['match-a', 'match-b', 'match-c']);

    fireEvent.change(activeSelector, { target: { value: 'match-c' } });
    await screen.findByText('Match C', { selector: 'header span' });
    expect(screen.queryByText('Match B unavailable')).toBeNull();
  });

  it.each(['success', 'failure'] as const)('ignores late selected-match %s and cleanup after a newer load', async (outcome) => {
    stubPitchCanvas();
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const lateB = deferred<Workspace>();
    const listedMatches = [
      readyMatch('match-a', 'Match A'),
      readyMatch('match-b', 'Match B'),
      readyMatch('match-c', 'Match C'),
    ];
    vi.mocked(api.fetchMatches).mockResolvedValue(listedMatches);
    vi.mocked(api.fetchMatchWorkspace).mockImplementation((matchId) => {
      if (matchId === 'match-b') return lateB.promise;
      const match = listedMatches.find(({ id }) => id === matchId)!;
      return Promise.resolve(loadedWorkspace(match.id, match.name, `${match.name} event`));
    });

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    const activeSelector = screen.getAllByRole('combobox')[0];
    fireEvent.change(activeSelector, { target: { value: 'match-b' } });
    fireEvent.change(activeSelector, { target: { value: 'match-c' } });

    await screen.findByText('Match C', { selector: 'header span' });
    expect(screen.getByTitle(/Match C event @ 0s/)).toBeTruthy();
    await act(async () => {
      if (outcome === 'success') lateB.resolve(loadedWorkspace('match-b', 'Match B', 'Match B event'));
      else lateB.reject(new Error('Late Match B failure'));
    });

    expect(screen.getByText('Match C', { selector: 'header span' })).toBeTruthy();
    expect(screen.getByTitle(/Match C event @ 0s/)).toBeTruthy();
    expect(screen.queryByText('Match B', { selector: 'header span' })).toBeNull();
    expect(screen.queryByText('Late Match B failure')).toBeNull();
  });

  it('loads, clears, and protects comparison workspaces independently', async () => {
    stubPitchCanvas();
    const lateB = deferred<Workspace>();
    const laterC = deferred<Workspace>();
    const listedMatches = [
      readyMatch('match-a', 'Match A'),
      readyMatch('match-b', 'Match B'),
      readyMatch('match-c', 'Match C'),
    ];
    let bLoads = 0;
    vi.mocked(api.fetchMatches).mockResolvedValue(listedMatches);
    vi.mocked(api.fetchMatchWorkspace).mockImplementation((matchId) => {
      if (matchId === 'match-a') return Promise.resolve(loadedWorkspace('match-a', 'Match A', undefined, 60));
      if (matchId === 'match-b' && bLoads++ === 0) return Promise.resolve(loadedWorkspace('match-b', 'Match B', undefined, 40));
      if (matchId === 'match-b') return lateB.promise;
      return laterC.promise;
    });

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    const comparisonSelector = screen.getAllByRole('combobox')[1];

    fireEvent.change(comparisonSelector, { target: { value: 'match-b' } });
    await screen.findByText('Match B', { selector: 'span.font-mono' });
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(2);
    fireEvent.change(comparisonSelector, { target: { value: '' } });
    expect(screen.queryByText('Compared to:')).toBeNull();

    fireEvent.change(comparisonSelector, { target: { value: 'match-b' } });
    fireEvent.change(comparisonSelector, { target: { value: 'match-c' } });
    await act(async () => laterC.resolve(loadedWorkspace('match-c', 'Match C', undefined, 35)));
    await screen.findByText('Match C', { selector: 'span.font-mono' });
    await act(async () => lateB.resolve(loadedWorkspace('match-b', 'Match B', undefined, 40)));

    expect(screen.getByText('Match C', { selector: 'span.font-mono' })).toBeTruthy();
    expect(screen.queryByText('Match B', { selector: 'span.font-mono' })).toBeNull();
  });

  it('keeps a newer selection loading when stale startup hydration settles', async () => {
    stubPitchCanvas();
    const startupA = deferred<Workspace>();
    const selectedB = deferred<Workspace>();
    vi.mocked(api.fetchMatches).mockResolvedValue([
      readyMatch('match-a', 'Match A'),
      readyMatch('match-b', 'Match B'),
    ]);
    vi.mocked(api.fetchMatchWorkspace).mockImplementation((matchId) => (
      matchId === 'match-a' ? startupA.promise : selectedB.promise
    ));

    const { container } = render(<App />);
    await waitFor(() => expect(screen.getAllByRole('combobox')).toHaveLength(4));
    const activeSelector = screen.getAllByRole('combobox')[0] as HTMLSelectElement;
    const uploadInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(activeSelector, { target: { value: 'match-b' } });

    await act(async () => startupA.resolve(loadedWorkspace('match-a', 'Match A')));
    expect(uploadInput.disabled).toBe(true);

    await act(async () => selectedB.resolve(loadedWorkspace('match-b', 'Match B')));
    await screen.findByText('Match B', { selector: 'header span' });
    expect(uploadInput.disabled).toBe(false);
  });

  it('keeps a newer selection loading when stale upload hydration settles', async () => {
    stubPitchCanvas();
    const uploadedWorkspace = deferred<Workspace>();
    const selectedB = deferred<Workspace>();
    const listedMatches = [readyMatch('match-a', 'Match A'), readyMatch('match-b', 'Match B')];
    vi.mocked(api.fetchMatches).mockResolvedValue(listedMatches);
    vi.mocked(api.createMatchUpload).mockResolvedValue({ matchId: 'match-upload', jobId: 'job-upload', status: 'queued' });
    vi.mocked(api.waitForJobCompletion).mockResolvedValue({ id: 'job-upload', matchId: 'match-upload', status: 'completed', progress: 1 });
    vi.mocked(api.fetchMatchWorkspace).mockImplementation((matchId) => {
      if (matchId === 'match-a') return Promise.resolve(loadedWorkspace('match-a', 'Match A'));
      if (matchId === 'match-upload') return uploadedWorkspace.promise;
      return selectedB.promise;
    });

    const { container } = render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    const activeSelector = screen.getAllByRole('combobox')[0];
    const uploadInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(uploadInput, { target: { files: [new File(['[]'], 'upload.json', { type: 'application/json' })] } });
    await waitFor(() => expect(api.fetchMatchWorkspace).toHaveBeenCalledWith('match-upload', expect.any(AbortSignal)));
    fireEvent.change(activeSelector, { target: { value: 'match-b' } });

    await act(async () => uploadedWorkspace.resolve(loadedWorkspace('match-upload', 'Uploaded Match')));
    expect(uploadInput.disabled).toBe(true);

    await act(async () => selectedB.resolve(loadedWorkspace('match-b', 'Match B')));
    await screen.findByText('Match B', { selector: 'header span' });
    expect(uploadInput.disabled).toBe(false);
  });

  it('does not start upload hydration after a newer match selection', async () => {
    stubPitchCanvas();
    const completedJob = deferred<ProcessingJob>();
    const unexpectedUpload = deferred<Workspace>();
    vi.mocked(api.fetchMatches).mockResolvedValue([
      readyMatch('match-a', 'Match A'),
      readyMatch('match-b', 'Match B'),
    ]);
    vi.mocked(api.createMatchUpload).mockResolvedValue({ matchId: 'match-upload', jobId: 'job-upload', status: 'queued' });
    vi.mocked(api.waitForJobCompletion).mockImplementation(() => completedJob.promise);
    vi.mocked(api.fetchMatchWorkspace).mockImplementation((matchId) => {
      if (matchId === 'match-upload') return unexpectedUpload.promise;
      return Promise.resolve(loadedWorkspace(matchId, matchId === 'match-a' ? 'Match A' : 'Match B'));
    });

    const { container } = render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    const uploadInput = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(uploadInput, { target: { files: [new File(['[]'], 'upload.json', { type: 'application/json' })] } });
    await waitFor(() => expect(api.waitForJobCompletion).toHaveBeenCalledTimes(1));
    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: 'match-b' } });
    await screen.findByText('Match B', { selector: 'header span' });

    await act(async () => completedJob.resolve({ id: 'job-upload', matchId: 'match-upload', status: 'completed', progress: 1 }));

    expect(vi.mocked(api.fetchMatchWorkspace).mock.calls.map(([matchId]) => matchId)).toEqual(['match-a', 'match-b']);
    expect(screen.getByText('Match B', { selector: 'header span' })).toBeTruthy();
  });

  it('does not reload an old match when its team relabel finishes after a new selection starts', async () => {
    stubPitchCanvas();
    const configUpdate = deferred<MatchRecord>();
    const selectedB = deferred<Workspace>();
    const unexpectedReload = deferred<Workspace>();
    const matchA = loadedWorkspace('match-a', 'Match A');
    matchA.detail.requiresTeamSelection = true;
    matchA.detail.teamClusters = [{ clusterId: 1, rgbCentroid: [20, 40, 200], trackIds: [4, 6] }];
    vi.mocked(api.fetchMatches).mockResolvedValue([
      readyMatch('match-a', 'Match A'),
      readyMatch('match-b', 'Match B'),
    ]);
    let matchALoads = 0;
    vi.mocked(api.fetchMatchWorkspace).mockImplementation((matchId) => {
      if (matchId === 'match-a' && matchALoads++ === 0) return Promise.resolve(matchA);
      if (matchId === 'match-a') return unexpectedReload.promise;
      return selectedB.promise;
    });
    vi.mocked(api.updateMatchConfig).mockImplementation(() => configUpdate.promise);

    const { container } = render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    fireEvent.click(screen.getByRole('button', { name: 'Use cluster 1' }));
    await waitFor(() => expect(api.updateMatchConfig).toHaveBeenCalledWith('match-a', expect.objectContaining({ myTeamCluster: 1, baseGeneration: 'g-match-a', commandId: expect.any(String) })));
    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: 'match-b' } });

    await act(async () => configUpdate.resolve(readyMatch('match-a', 'Match A')));
    expect(vi.mocked(api.fetchMatchWorkspace).mock.calls.map(([matchId]) => matchId)).toEqual(['match-a', 'match-b']);
    expect((container.querySelector('input[type="file"]') as HTMLInputElement).disabled).toBe(true);

    await act(async () => selectedB.resolve(loadedWorkspace('match-b', 'Match B')));
    await screen.findByText('Match B', { selector: 'header span' });
  });
});

describe('App upload polling', () => {
  it('aborts pending workspace siblings when one request fails', async () => {
    const actual = await vi.importActual<typeof api>('./utils/api');
    vi.mocked(api.fetchMatchWorkspace).mockImplementation(actual.fetchMatchWorkspace);
    vi.mocked(api.fetchMatches).mockResolvedValue([]);
    vi.mocked(api.createMatchUpload).mockResolvedValue({ matchId: 'match-1', jobId: 'job-1', status: 'queued' });
    vi.mocked(api.waitForJobCompletion).mockResolvedValue({ id: 'job-1', matchId: 'match-1', status: 'completed', progress: 1 });
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const requests: { signal: AbortSignal; reject: (reason: Error) => void }[] = [];
    vi.stubGlobal('fetch', vi.fn((_url: string, init: RequestInit) => {
      if (_url === '/api/matches/match-1') return Promise.resolve(new Response(JSON.stringify({ ...readyMatch('match-1', 'Match 1') }), { status: 200 }));
      return new Promise<Response>((_resolve, reject) => {
      const signal = init.signal as AbortSignal;
      requests.push({ signal, reject });
      signal.addEventListener('abort', () => reject(new Error('Cancelled')), { once: true });
    }); }));

    let container: HTMLElement;
    await act(async () => {
      ({ container } = render(<App />));
    });
    const input = container!.querySelector('input[type="file"]') as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, {
        target: { files: [new File(['[]'], 'match.json', { type: 'application/json' })] },
      });
    });
    expect(requests).toHaveLength(5);

    await act(async () => requests[0].reject(new Error('Workspace unavailable')));

    expect(screen.getAllByText('Workspace unavailable').length).toBeGreaterThan(0);
    expect(input.disabled).toBe(false);
    expect(requests.slice(1).map(({ signal }) => signal.aborted)).toEqual([true, true, true, true]);
  });

  it('aborts terminal-poll workspace hydration on unmount', async () => {
    vi.mocked(api.fetchMatches).mockResolvedValue([]);
    let uploadSignal: AbortSignal | undefined;
    vi.mocked(api.createMatchUpload).mockImplementation((input) => {
      uploadSignal = input.signal;
      return Promise.resolve({ matchId: 'match-1', jobId: 'job-1', status: 'queued' });
    });
    vi.mocked(api.waitForJobCompletion).mockResolvedValue({ id: 'job-1', matchId: 'match-1', status: 'completed', progress: 1 });
    let workspaceSignal: AbortSignal | undefined;
    let resolveWorkspace: (value: Workspace) => void;
    vi.mocked(api.fetchMatchWorkspace).mockImplementation((_matchId, signal) => new Promise<Workspace>((resolve) => {
      workspaceSignal = signal;
      resolveWorkspace = resolve;
    }));

    const { container, unmount } = render(<App />);
    await waitFor(() => expect(api.fetchMatches).toHaveBeenCalledTimes(1));

    fireEvent.change(container.querySelector('input[type="file"]') as HTMLInputElement, {
      target: { files: [new File(['[]'], 'match.json', { type: 'application/json' })] },
    });
    await waitFor(() => expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1));
    unmount();

    expect(uploadSignal?.aborted).toBe(true);
    expect(workspaceSignal?.aborted).toBe(true);
    await act(async () => resolveWorkspace!(workspace('match-1', 'Stale Match')));
  });

  it('does not apply a replaced upload workspace after its terminal poll', async () => {
    vi.mocked(api.fetchMatches).mockResolvedValue([]);
    vi.mocked(api.createMatchUpload)
      .mockResolvedValueOnce({ matchId: 'match-1', jobId: 'job-1', status: 'queued' })
      .mockResolvedValueOnce({ matchId: 'match-2', jobId: 'job-2', status: 'queued' });
    vi.mocked(api.waitForJobCompletion).mockResolvedValue({ id: 'job-1', matchId: 'match-1', status: 'completed', progress: 1 });
    let resolveFirstWorkspace: (value: Workspace) => void;
    let resolveSecondWorkspace: (value: Workspace) => void;
    vi.mocked(api.fetchMatchWorkspace)
      .mockImplementationOnce(() => new Promise<Workspace>((resolve) => {
        resolveFirstWorkspace = resolve;
      }))
      .mockImplementationOnce(() => new Promise<Workspace>((resolve) => {
        resolveSecondWorkspace = resolve;
      }));

    const { container } = render(<App />);
    await waitFor(() => expect(api.fetchMatches).toHaveBeenCalledTimes(1));
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(['[]'], 'first.json', { type: 'application/json' })] } });
    await waitFor(() => expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1));

    input.disabled = false;
    fireEvent.change(input, { target: { files: [new File(['[]'], 'second.json', { type: 'application/json' })] } });
    await waitFor(() => expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(2));

    await act(async () => resolveFirstWorkspace!(workspace('match-1', 'Stale Match')));
    expect(screen.queryByText('Stale Match')).toBeNull();

    await act(async () => resolveSecondWorkspace!(workspace('match-2', 'Fresh Match')));
    await waitFor(() => expect(screen.getByText('Fresh Match')).toBeTruthy());

  });
});

describe('App review drawing', () => {
  it('ends drawing for both the toolbar and pitch after save and allows reselecting it', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([{
      id: 'match-review', generationId: 'g-match-review', includedCommandIds: [],
      name: 'Review Match',
      status: 'ready',
      inputMode: 'tracking_json',
      originalFilename: 'review.json',
    }]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(reviewWorkspace());
    vi.mocked(api.createMatchAnnotation)
      .mockResolvedValueOnce({
        id: 'circle-1',
        matchId: 'match-review',
        type: 'circle',
        frameStart: 0,
        frameEnd: 0,
        timestampStart: 3.5,
        timestampEnd: 3.5,
        x: 10,
        y: 20,
        createdAt: '2026-09-12T00:00:00Z',
        updatedAt: '2026-09-12T00:00:00Z',
      })
      .mockResolvedValueOnce({
        id: 'circle-2',
        matchId: 'match-review',
        type: 'circle',
        frameStart: 0,
        frameEnd: 0,
        timestampStart: 3.5,
        timestampEnd: 3.5,
        x: 30,
        y: 40,
        createdAt: '2026-09-12T00:00:00Z',
        updatedAt: '2026-09-12T00:00:00Z',
      });

    const { container } = render(<App />);
    await waitFor(() => expect(screen.getByText('Review Match')).toBeTruthy());
    const canvas = container.querySelector('canvas') as HTMLCanvasElement;
    const circle = screen.getByRole('button', { name: 'Circle' });

    fireEvent.click(circle);
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeTruthy();
    fireEvent.mouseDown(canvas, { clientX: 10, clientY: 20 });
    fireEvent.mouseUp(canvas, { clientX: 10, clientY: 20 });
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Cancel' })).toBeNull());
    expect(api.createMatchAnnotation).toHaveBeenCalledTimes(1);

    fireEvent.mouseDown(canvas, { clientX: 20, clientY: 30 });
    fireEvent.mouseUp(canvas, { clientX: 20, clientY: 30 });
    expect(api.createMatchAnnotation).toHaveBeenCalledTimes(1);

    fireEvent.click(circle);
    fireEvent.mouseDown(canvas, { clientX: 30, clientY: 40 });
    fireEvent.mouseUp(canvas, { clientX: 30, clientY: 40 });
    await waitFor(() => expect(api.createMatchAnnotation).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Cancel' })).toBeNull());
  });
});

describe('App analysis provider capabilities', () => {
  it('keeps cloud unavailable and runs locally when only local analysis is supported', async () => {
    mockReadyReviewMatch();
    stubPitchCanvas();

    render(<App runtimeCapabilities={localOnlyCapabilities} />);
    await screen.findByText('Review Match');

    const cloud = screen.getByRole('button', { name: 'Cloud' }) as HTMLButtonElement;
    expect(cloud.disabled).toBe(true);
    fireEvent.click(cloud);
    fireEvent.click(screen.getByRole('button', { name: 'Analysis' }));
    fireEvent.click(screen.getByRole('button', { name: 'Analyze Lines' }));

    await waitFor(() => expect(api.runMatchAnalysis).toHaveBeenCalledWith(
      'match-review',
      'spacing',
      'local',
      0,
    ));
  });

  it('allows cloud analysis when the runtime supports it', async () => {
    mockReadyReviewMatch();
    stubPitchCanvas();

    render(<App runtimeCapabilities={cloudCapabilities} />);
    await screen.findByText('Review Match');

    fireEvent.click(screen.getByRole('button', { name: 'Cloud' }));
    fireEvent.click(screen.getByRole('button', { name: 'Analysis' }));
    fireEvent.click(screen.getByRole('button', { name: 'Analyze Lines' }));

    await waitFor(() => expect(api.runMatchAnalysis).toHaveBeenCalledWith(
      'match-review',
      'spacing',
      'cloud',
      0,
    ));
  });

  it('uses local immediately when cloud support is removed', async () => {
    mockReadyReviewMatch();
    stubPitchCanvas();

    const { rerender } = render(<App runtimeCapabilities={cloudCapabilities} />);
    await screen.findByText('Review Match');
    fireEvent.click(screen.getByRole('button', { name: 'Cloud' }));
    fireEvent.click(screen.getByRole('button', { name: 'Analysis' }));

    rerender(<App runtimeCapabilities={localOnlyCapabilities} />);
    fireEvent.click(screen.getByRole('button', { name: 'Analyze Lines' }));

    await waitFor(() => expect(api.runMatchAnalysis).toHaveBeenCalledWith(
      'match-review',
      'spacing',
      'local',
      0,
    ));
    expect(api.runMatchAnalysis).not.toHaveBeenCalledWith(
      'match-review',
      'spacing',
      'cloud',
      0,
    );
  });

  it('does not restore a stale cloud selection when cloud support returns', async () => {
    mockReadyReviewMatch();
    stubPitchCanvas();

    const { rerender } = render(<App runtimeCapabilities={cloudCapabilities} />);
    await screen.findByText('Review Match');
    fireEvent.click(screen.getByRole('button', { name: 'Cloud' }));

    rerender(<App runtimeCapabilities={localOnlyCapabilities} />);
    rerender(<App runtimeCapabilities={cloudCapabilities} />);
    fireEvent.click(screen.getByRole('button', { name: 'Analysis' }));
    fireEvent.click(screen.getByRole('button', { name: 'Analyze Lines' }));

    await waitFor(() => expect(api.runMatchAnalysis).toHaveBeenCalledWith(
      'match-review',
      'spacing',
      'local',
      0,
    ));
  });
});


it('keeps both upload inputs keyboard focusable', async () => {
  vi.mocked(api.fetchMatches).mockResolvedValue([]);
  render(<App />);
  await screen.findByLabelText('Upload JSON or Video');
  const inputs = screen.getAllByLabelText(/^(Load Match|Upload JSON or Video)$/);
  expect(inputs).toHaveLength(2);
  for (const input of inputs) {
    expect(input.classList.contains('hidden')).toBe(false);
    input.focus();
    expect(document.activeElement).toBe(input);
  }
});

it('normalizes event and imported playlist timestamps before timeline navigation', async () => {
  stubPitchCanvas();
  vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('m', 'Sparse Match')]);
  vi.mocked(api.fetchMatchWorkspace).mockResolvedValue({ ...loadedWorkspace('m', 'Sparse Match'),
    frames: [100, 200].map((Frame_ID, index) => ({ Frame_ID, Timestamp: index * 2, Ball: null, My_Team: [], Enemies: [] })),
    frameCount: 201,
    events: [{ frameId: 200, timestamp: 2, type: 'shot', description: 'Sparse shot' }],
  });
  render(<App />);
  fireEvent.click(await screen.findByTitle(/Sparse shot @ 2s/));
  expect((screen.getByLabelText('Timeline scrubber') as HTMLInputElement).value).toBe('200');
  act(() => { window.dispatchEvent(new CustomEvent('add-event', { detail: { frame: 100, timestamp: 0, label: 'Imported playlist', type: 'custom' } })); });
  fireEvent.click(screen.getByTitle(/Imported playlist @ 0s/));
  expect((screen.getByLabelText('Timeline scrubber') as HTMLInputElement).value).toBe('100');
});
