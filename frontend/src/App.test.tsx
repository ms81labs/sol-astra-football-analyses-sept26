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
    runMatchAnalysis: vi.fn(),
    updateMatchConfig: vi.fn(),
    waitForJobCompletion: vi.fn(),
  };
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

beforeEach(() => {
  vi.mocked(api.fetchMatchAnnotations).mockResolvedValue([]);
  vi.mocked(api.fetchMatchIssues).mockResolvedValue([]);
});

type Workspace = Awaited<ReturnType<typeof api.fetchMatchWorkspace>>;

function readyMatch(id: string, name: string): MatchRecord {
  return { id, name, status: 'ready', inputMode: 'tracking_json', originalFilename: `${id}.json` };
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
      id: 'match-review',
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

  it('exposes overlay controls as pressed toggles', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));

    render(<App />);

    const zones = await screen.findByRole('button', { name: 'Zones' });
    expect(zones.getAttribute('aria-pressed')).toBe('false');
    fireEvent.click(zones);
    expect(zones.getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByRole('region', { name: /playlist builder/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /assemble report/i })).toBeTruthy();
    expect(screen.getByText(/do not establish a whole-match frequency/i)).toBeTruthy();
    expect(screen.getByRole('region', { name: /holdout calibration/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /measure holdout/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /swap teams/i })).toBeTruthy();
    expect(screen.getByRole('region', { name: /typed search/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /search evidence/i })).toBeTruthy();
    expect(screen.getByRole('region', { name: /incident review/i })).toBeTruthy();
    expect(screen.queryAllByText(/attackerX=0/)).toHaveLength(0);
    expect(screen.queryAllByText(/line=0/)).toHaveLength(0);
  });

  it('loads heatmap availability from production HTTP and ignores claimed identity continuity', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      void init;
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
    expect(heatmapCall?.[1]?.method).toBe('POST');
    expect(heatmapCall?.[1]?.body).not.toContain('"identityContinuous":true');
    expect(screen.getByText(/whole-match heatmap withheld until identity continuity/i)).toBeTruthy();
  });

  it('derives speed and player-total overlays from production identity continuity', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo, init?: RequestInit) => {
      void init;
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: true,
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
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue({
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
          json: async () => ({
            identityContinuous: true,
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
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue({
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
          json: async () => ({
            identityContinuous: true,
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
          json: async () => ({
            committed: true,
            preview: true,
            identityContinuous: false,
            silentlyReconnected: false,
            visionRerun: false,
            reasonCodes: [],
            correction: { correctionId: 'join-1', kind: 'track_join', saveState: 'saved' },
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
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue({
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
          json: async () => ({
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
          json: async () => ({
            committed: true,
            preview: true,
            identityContinuous: true,
            silentlyReconnected: false,
            visionRerun: false,
            reasonCodes: [],
            correction: { correctionId: 'validate-1', kind: 'identity_validate', saveState: 'saved' },
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
    fireEvent.click(screen.getByRole('button', { name: /validate identity/i }));
    await waitFor(() => {
      const promoteCall = fetchMock.mock.calls.find(([url]) => String(url).includes('/identity/promote'));
      expect(promoteCall?.[1]?.body).toContain('"reviewed":true');
      expect(promoteCall?.[1]?.body).not.toContain('"identityContinuous":true');
    });
  });

  it('submits independent holdout landmarks on the loaded match without client acceptance', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/calibration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            fromStoredPoints: true,
            measured: false,
            evaluation: { accepted: false },
            residualP95M: null,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/calibration') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            evaluation: { accepted: true },
            measured: true,
            residualP95M: 0.4,
            committed: true,
            visionRerun: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/geometry/distance')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            availability: 'available',
            value: 5.25,
            uncertaintyM: 0.4,
            bridged: false,
            reasonCodes: [],
          }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    fireEvent.change(screen.getByLabelText(/image x/i), { target: { value: '50' } });
    fireEvent.change(screen.getByLabelText(/image y/i), { target: { value: '50' } });
    fireEvent.change(screen.getByLabelText(/pitch x/i), { target: { value: '52.5' } });
    fireEvent.change(screen.getByLabelText(/pitch y/i), { target: { value: '34' } });
    fireEvent.click(screen.getByRole('button', { name: /measure holdout/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/calibration')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    const calibrationCall = fetchMock.mock.calls.find(([url, init]) => (
      String(url).includes('/api/matches/match-a/calibration')
      && init?.method === 'POST'
    ));
    expect(calibrationCall?.[1]?.method).toBe('POST');
    expect(calibrationCall?.[1]?.body).toContain('"independentHoldout":true');
    expect(calibrationCall?.[1]?.body).toContain('"imageX":50');
    expect(calibrationCall?.[1]?.body).toContain('"pitchX":52.5');
    expect(calibrationCall?.[1]?.body).not.toContain('"accepted":true');
    expect(calibrationCall?.[1]?.body).not.toContain('"residualP95M"');
    expect(calibrationCall?.[1]?.body).not.toContain('"measured":true');
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/geometry/landmarks'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/geometry/preview'))).toBe(false);
    expect(await screen.findByText(/holdout accepted/i)).toBeTruthy();
    expect(screen.getByText(/derived distance 5.25 m/i)).toBeTruthy();
    expect(screen.queryByText(/derived distance 0(\.0)? m/i)).toBeNull();
  });

  it('runs typed tactical search on stored match events without client-injected rows', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
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

  it('refreshes stored events after accept without rewriting the playhead or injecting event ids', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue({
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
    });
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ correctionId: 'accept-1', saveState: 'saved', kind: 'event_accept' }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/events') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
    expect(await screen.findByText('accepted')).toBeTruthy();
  });

  it('posts stored undo from keyboard z after accept without rewriting the playhead', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue({
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
    });
    let undone = false;
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ correctionId: 'undo-1', saveState: 'saved', undoOf: 'accept-1' }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && init?.method === 'POST' && !String(url).includes('/undo')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ correctionId: 'accept-1', saveState: 'saved', kind: 'event_accept' }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/events') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
    expect(await screen.findByText('unreviewed')).toBeTruthy();
  });

  it('recovers a pending event correction on the loaded match without rewriting the playhead', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue({
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
    });
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
            items: [{ correctionId: 'c-pending', kind: 'event_accept', saveState: 'pending' }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections/c-pending/recover') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ correctionId: 'c-pending', saveState: 'saved', kind: 'event_accept' }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/events') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
    expect(await screen.findByText('accepted')).toBeTruthy();
    expect(await screen.findByText('Edit saved')).toBeTruthy();
  });

  it('loads stored undoable correction history without requiring an in-session edit', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue({
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
    });
    let undone = false;
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections/accept-1/undo') && init?.method === 'POST') {
        undone = true;
        return Promise.resolve({
          ok: true,
          json: async () => ({ correctionId: 'undo-1', saveState: 'saved', undoOf: 'accept-1' }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{
              correctionId: 'accept-1',
              kind: 'event_accept',
              saveState: 'saved',
              author: 'analyst',
              undoOf: null,
            }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/events') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
    expect(await screen.findByText('unreviewed')).toBeTruthy();
  });

  it('exports the marked review range as a half-open source interval without claiming whole-match frequency', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
            sourceStartSeconds: 0,
            sourceEndSeconds: 0.2,
            sourceEndFrameExclusive: 1,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && init?.method === 'POST' && !String(url).includes('/undo') && !String(url).includes('/recover')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ correctionId: 'clip-1', saveState: 'saved', kind: 'playlist_item' }),
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
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('opens the exported playlist source interval on the review timeline', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue({
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
          json: async () => ({
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
          json: async () => ({
            sourceStartSeconds: 0,
            sourceEndSeconds: 0.2,
            sourceEndFrameExclusive: 1,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && init?.method === 'POST' && !String(url).includes('/undo') && !String(url).includes('/recover')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ correctionId: 'clip-1', saveState: 'saved', kind: 'playlist_item' }),
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
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('recovers a pending playlist clip on the loaded match without rewriting the playhead', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({ correctionId: 'clip-pending', saveState: 'saved', kind: 'playlist_item' }),
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
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls.some(([url]) => (
      String(url).includes('/api/matches/match-a/events')
      && !String(url).includes('/partition')
    ))).toBe(false);
  });

  it('undos a stored playlist clip without rewriting the playhead', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections/clip-1/undo') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ correctionId: 'undo-clip-1', saveState: 'saved', undoOf: 'clip-1' }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{
              correctionId: 'clip-1',
              kind: 'playlist_item',
              saveState: 'saved',
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
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls.some(([url]) => (
      String(url).includes('/api/matches/match-a/events')
      && !String(url).includes('/partition')
    ))).toBe(false);
  });

  it('loads stored playlist clips into the review builder without undone items', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [
              {
                correctionId: 'clip-1',
                kind: 'playlist_item',
                saveState: 'saved',
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
                saveState: 'saved',
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
                saveState: 'saved',
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
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue({
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
          json: async () => ({
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
          json: async () => ({ items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{
              correctionId: 'clip-1',
              kind: 'playlist_item',
              saveState: 'saved',
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
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
            reencodeFullMatch: false,
            renderOnDemand: true,
            intervals: [[0, 0.2]],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{
              correctionId: 'clip-1',
              kind: 'playlist_item',
              saveState: 'saved',
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
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue({
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
          json: async () => ({
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
          json: async () => ({
            sourceStartSeconds: 0,
            sourceEndSeconds: 0.2,
            sourceEndFrameExclusive: 1,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits/render') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            interval: [0, 0.2],
            reencodedFullMatch: false,
            sourceSha256: 'stored-source',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && init?.method === 'POST' && !String(url).includes('/undo') && !String(url).includes('/recover')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ correctionId: 'clip-1', saveState: 'saved', kind: 'playlist_item' }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
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
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('writes alongside stored artifacts without mutating historical output or admitting secrets', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/artifacts/alongside') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            digest: 'sha-new',
            previousDigest: 'sha-old',
            mutatedHistorical: false,
            namespace: 'match:match-a',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/artifacts/alongside')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('mutatedHistorical":true'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('DAYTONA_API_KEY'))
    ))).toBe(false);
    const artifacts = within(await screen.findByRole('region', { name: /write-alongside artifacts/i }));
    expect(artifacts.getByText(/do not mutate historical output/i)).toBeTruthy();
    expect(artifacts.getByText(/mutatedHistorical is false/i)).toBeTruthy();
    expect(artifacts.getByText(/digest is not the previous digest/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('runs report-only recompute without invoking vision or injecting perception rows', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recompute') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            visionInvoked: false,
            reused: true,
            admitted: true,
            imageSpaceDetectionsReused: true,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/artifacts/alongside') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            digest: 'sha-new',
            previousDigest: 'sha-old',
            mutatedHistorical: false,
            namespace: 'match:match-a',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/recompute')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('visionRows'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('"change":"perception"'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('"visionInvoked":true'))
    ))).toBe(false);
    const recompute = within(await screen.findByRole('region', { name: /report-only recompute/i }));
    expect(recompute.getByText(/does not invoke vision/i)).toBeTruthy();
    expect(recompute.getByText(/visionInvoked is false/i)).toBeTruthy();
    expect(recompute.getByText(/stored detections are reused/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('rejects SHA-mismatch recovery import without letting client hashes force admission', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recovery/import') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            reasonCodes: ['CORRUPTED_ARTIFACT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recompute') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            visionInvoked: false,
            reused: true,
            admitted: true,
            imageSpaceDetectionsReused: true,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/artifacts/alongside') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            digest: 'sha-new',
            previousDigest: 'sha-old',
            mutatedHistorical: false,
            namespace: 'match:match-a',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/recovery/import')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('expectedSha256'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('"accepted":true'))
    ))).toBe(false);
    const recoveryImport = within(await screen.findByRole('region', { name: /corrupted recovery import/i }));
    expect(recoveryImport.getByText(/SHA-mismatch recovery import is not accepted/i)).toBeTruthy();
    expect(recoveryImport.getByText(/CORRUPTED_ARTIFACT/)).toBeTruthy();
    expect(recoveryImport.getByText(/expectedSha256 cannot force admission/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts match assistance report without client-claimed evidence or leftover forged rows', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/assistance/report') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            factualCheck: { accepted: false, reasonCodes: ['FABRICATED_EVIDENCE'] },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recovery/import') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            reasonCodes: ['CORRUPTED_ARTIFACT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recompute') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            visionInvoked: false,
            reused: true,
            admitted: true,
            imageSpaceDetectionsReused: true,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/artifacts/alongside') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            digest: 'sha-new',
            previousDigest: 'sha-old',
            mutatedHistorical: false,
            namespace: 'match:match-a',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/assistance/report')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('claimedEvidenceIds'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('forged'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('knownEvidenceIds'))
    ))).toBe(false);
    const assistanceReport = within(await screen.findByRole('region', { name: /assistance report/i }));
    expect(assistanceReport.getByText(/does not accept client-claimed evidence/i)).toBeTruthy();
    expect(assistanceReport.getByText(/claimedEvidenceIds are not sent/i)).toBeTruthy();
    expect(assistanceReport.getByText(/FABRICATED_EVIDENCE stays unaccepted/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts tracklets without forcing a roster identity or silent reconnect', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/assistance/report') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            factualCheck: { accepted: false, reasonCodes: ['FABRICATED_EVIDENCE'] },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recovery/import') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            reasonCodes: ['CORRUPTED_ARTIFACT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recompute') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            visionInvoked: false,
            reused: true,
            admitted: true,
            imageSpaceDetectionsReused: true,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/artifacts/alongside') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            digest: 'sha-new',
            previousDigest: 'sha-old',
            mutatedHistorical: false,
            namespace: 'match:match-a',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/tracklets')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('rosterId'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('reviewed'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('silentlyReconnected'))
    ))).toBe(false);
    const posted = within(await screen.findByRole('region', { name: /unforced roster write/i }));
    expect(posted.getByText(/do not force a roster identity/i)).toBeTruthy();
    expect(posted.getByText(/rosterId and reviewed flags are not sent/i)).toBeTruthy();
    expect(posted.getByText(/silentlyReconnected stays false/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts shot features without imputing client goal rows as calibrated xG', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            recorded: true,
            missing: ['x'],
            imputedAsCalibrated: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/assistance/report') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            factualCheck: { accepted: false, reasonCodes: ['FABRICATED_EVIDENCE'] },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recovery/import') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            reasonCodes: ['CORRUPTED_ARTIFACT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recompute') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            visionInvoked: false,
            reused: true,
            admitted: true,
            imageSpaceDetectionsReused: true,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/artifacts/alongside') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            digest: 'sha-new',
            previousDigest: 'sha-old',
            mutatedHistorical: false,
            namespace: 'match:match-a',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/shots/features')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('"goal"'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('"shots"'))
    ))).toBe(false);
    const posted = within(await screen.findByRole('region', { name: /unimputed feature write/i }));
    expect(posted.getByText(/ignore client goal rows/i)).toBeTruthy();
    expect(posted.getByText(/client shots are not sent/i)).toBeTruthy();
    expect(posted.getByText(/imputedAsCalibrated stays false/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts incident review without client attackerX or an offside decision', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/review') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            level: 1,
            decision: null,
            validatedMeasurement: false,
            samples: [{ time: 0, attackerX: 21, offsideLineX: 1, indeterminate: true }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            recorded: true,
            missing: ['x'],
            imputedAsCalibrated: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/assistance/report') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            factualCheck: { accepted: false, reasonCodes: ['FABRICATED_EVIDENCE'] },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recovery/import') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            reasonCodes: ['CORRUPTED_ARTIFACT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recompute') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            visionInvoked: false,
            reused: true,
            admitted: true,
            imageSpaceDetectionsReused: true,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/artifacts/alongside') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            digest: 'sha-new',
            previousDigest: 'sha-old',
            mutatedHistorical: false,
            namespace: 'match:match-a',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/incidents/review')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('attackerX'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('offside'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('"decision"'))
    ))).toBe(false);
    const posted = within(await screen.findByRole('region', { name: /unvalidated positional write/i }));
    expect(posted.getByText(/ignores client attackerX and offside decision/i)).toBeTruthy();
    expect(posted.getByText(/decision stays unpublished/i)).toBeTruthy();
    expect(posted.getByText(/validatedMeasurement stays false/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts cache identity without mixing a client development namespace', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            namespace: 'production',
            compatibleWithDevelopment: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/review') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            level: 1,
            decision: null,
            validatedMeasurement: false,
            samples: [{ time: 0, attackerX: 21, offsideLineX: 1, indeterminate: true }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            recorded: true,
            missing: ['x'],
            imputedAsCalibrated: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/assistance/report') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            factualCheck: { accepted: false, reasonCodes: ['FABRICATED_EVIDENCE'] },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recovery/import') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            reasonCodes: ['CORRUPTED_ARTIFACT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recompute') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            visionInvoked: false,
            reused: true,
            admitted: true,
            imageSpaceDetectionsReused: true,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/artifacts/alongside') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            digest: 'sha-new',
            previousDigest: 'sha-old',
            mutatedHistorical: false,
            namespace: 'match:match-a',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/cache')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('development'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('"namespace"'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/cache/tenancy'))).toBe(false);
    const posted = within(await screen.findByRole('region', { name: /posted namespace write/i }));
    expect(posted.getByText(/ignores client namespace development/i)).toBeTruthy();
    expect(posted.getByText(/namespace stays production/i)).toBeTruthy();
    expect(posted.getByText(/compatibleWithDevelopment stays false/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts ball ownership without treating client nearestTeam as control', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            mode: 'unknown',
            reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            namespace: 'production',
            compatibleWithDevelopment: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/review') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            level: 1,
            decision: null,
            validatedMeasurement: false,
            samples: [{ time: 0, attackerX: 21, offsideLineX: 1, indeterminate: true }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            recorded: true,
            missing: ['x'],
            imputedAsCalibrated: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/assistance/report') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            factualCheck: { accepted: false, reasonCodes: ['FABRICATED_EVIDENCE'] },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recovery/import') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            reasonCodes: ['CORRUPTED_ARTIFACT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recompute') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            visionInvoked: false,
            reused: true,
            admitted: true,
            imageSpaceDetectionsReused: true,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/artifacts/alongside') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            digest: 'sha-new',
            previousDigest: 'sha-old',
            mutatedHistorical: false,
            namespace: 'match:match-a',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/ownership')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('nearestTeam'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('calibrated'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('ballVisible'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/ownership/hysteresis'))).toBe(false);
    const posted = within(await screen.findByRole('region', { name: /posted nearest-player write/i }));
    expect(posted.getByText(/ignores client nearestTeam, calibrated, and ballVisible/i)).toBeTruthy();
    expect(posted.getByText(/mode stays unknown/i)).toBeTruthy();
    expect(posted.getByText(/NEAREST_PLAYER_INSUFFICIENT remains/)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts match package without client events or secrets', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: {
              events: [],
              limitations: ['Independent labels 0/18 complete.'],
            },
            operator: {
              manifest: { schema: 'match_package_v1' },
              secretsAdmitted: true,
            },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            mode: 'unknown',
            reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            namespace: 'production',
            compatibleWithDevelopment: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/review') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            level: 1,
            decision: null,
            validatedMeasurement: false,
            samples: [{ time: 0, attackerX: 21, offsideLineX: 1, indeterminate: true }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            recorded: true,
            missing: ['x'],
            imputedAsCalibrated: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/assistance/report') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            factualCheck: { accepted: false, reasonCodes: ['FABRICATED_EVIDENCE'] },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recovery/import') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            reasonCodes: ['CORRUPTED_ARTIFACT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recompute') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            visionInvoked: false,
            reused: true,
            admitted: true,
            imageSpaceDetectionsReused: true,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/artifacts/alongside') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            digest: 'sha-new',
            previousDigest: 'sha-old',
            mutatedHistorical: false,
            namespace: 'match:match-a',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/package')
        && !String(url).includes('/incidents/')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('"events"'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('"secrets"'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('DAYTONA_API_KEY'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/reports/assemble'))).toBe(false);
    const posted = within(await screen.findByRole('region', { name: /uninjected operator write/i }));
    expect(posted.getByText(/ignores client events and secrets/i)).toBeTruthy();
    expect(posted.getByText(/client DAYTONA_API_KEY is not sent/i)).toBeTruthy();
    expect(posted.getByText(/secretsAdmitted stays true/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts match metrics without inventing identityContinuous physical totals', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics') && !url.includes('/inspect') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { events: [], limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            mode: 'unknown',
            reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            namespace: 'production',
            compatibleWithDevelopment: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/review') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            level: 1,
            decision: null,
            validatedMeasurement: false,
            samples: [{ time: 0, attackerX: 21, offsideLineX: 1, indeterminate: true }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            recorded: true,
            missing: ['x'],
            imputedAsCalibrated: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/assistance/report') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            factualCheck: { accepted: false, reasonCodes: ['FABRICATED_EVIDENCE'] },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recovery/import') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            reasonCodes: ['CORRUPTED_ARTIFACT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recompute') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            visionInvoked: false,
            reused: true,
            admitted: true,
            imageSpaceDetectionsReused: true,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/artifacts/alongside') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            digest: 'sha-new',
            previousDigest: 'sha-old',
            mutatedHistorical: false,
            namespace: 'match:match-a',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
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
        && init?.method === 'POST'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('identityContinuous'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('calibrationAccepted'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('controlledFrames'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/workbench/'))).toBe(false);
    const posted = within(await screen.findByRole('region', { name: /unforced continuity write/i }));
    expect(posted.getByText(/ignore client identityContinuous and calibrationAccepted/i)).toBeTruthy();
    expect(posted.getByText(/availability stays unknown/i)).toBeTruthy();
    expect(posted.getByText(/IDENTITY_DISCONTINUITY remains/)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts match formation without inventing a client 4-3-3', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/formation') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            availability: 'withheld',
            value: null,
            reasonCodes: ['SINGLE_FRAME_FORMATION'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics') && !url.includes('/inspect') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { events: [], limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            mode: 'unknown',
            reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            namespace: 'production',
            compatibleWithDevelopment: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/review') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            level: 1,
            decision: null,
            validatedMeasurement: false,
            samples: [{ time: 0, attackerX: 21, offsideLineX: 1, indeterminate: true }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            recorded: true,
            missing: ['x'],
            imputedAsCalibrated: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/assistance/report') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            factualCheck: { accepted: false, reasonCodes: ['FABRICATED_EVIDENCE'] },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recovery/import') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            reasonCodes: ['CORRUPTED_ARTIFACT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recompute') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            visionInvoked: false,
            reused: true,
            admitted: true,
            imageSpaceDetectionsReused: true,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/artifacts/alongside') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            digest: 'sha-new',
            previousDigest: 'sha-old',
            mutatedHistorical: false,
            namespace: 'match:match-a',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/formation')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('4-3-3'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('eligibleWindows'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('roleContext'))
    ))).toBe(false);
    const posted = within(await screen.findByRole('region', { name: /uninvented shape write/i }));
    expect(posted.getByText(/ignores client 4-3-3/i)).toBeTruthy();
    expect(posted.getByText(/availability stays withheld/i)).toBeTruthy();
    expect(posted.getByText(/value stays unpublished/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts match identity without inventing client identityContinuous', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (
        url.includes('/api/matches/match-a/identity')
        && !url.includes('/repair')
        && !url.includes('/promote')
        && init?.method === 'POST'
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            silentlyReconnected: false,
            cutCount: 0,
            reset: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/formation') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            availability: 'withheld',
            value: null,
            reasonCodes: ['SINGLE_FRAME_FORMATION'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics') && !url.includes('/inspect') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { events: [], limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            mode: 'unknown',
            reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            namespace: 'production',
            compatibleWithDevelopment: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/review') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            level: 1,
            decision: null,
            validatedMeasurement: false,
            samples: [{ time: 0, attackerX: 21, offsideLineX: 1, indeterminate: true }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            recorded: true,
            missing: ['x'],
            imputedAsCalibrated: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/assistance/report') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            factualCheck: { accepted: false, reasonCodes: ['FABRICATED_EVIDENCE'] },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recovery/import') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            reasonCodes: ['CORRUPTED_ARTIFACT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recompute') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            visionInvoked: false,
            reused: true,
            admitted: true,
            imageSpaceDetectionsReused: true,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/artifacts/alongside') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            digest: 'sha-new',
            previousDigest: 'sha-old',
            mutatedHistorical: false,
            namespace: 'match:match-a',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/identity')
        && !String(url).includes('/repair')
        && !String(url).includes('/promote')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('identityContinuous'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('silentlyReconnected'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/identity/promote'))).toBe(false);
    const posted = within(await screen.findByRole('region', { name: /posted continuity denial/i }));
    expect(posted.getByText(/ignores client identityContinuous true/i)).toBeTruthy();
    expect(posted.getByText(/identityContinuous stays false/i)).toBeTruthy();
    expect(posted.getByText(/silentlyReconnected stays false/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts player observations without injecting client rows or identityContinuous', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/players') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            intervalLimited: true,
            totalsWithheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
            rows: [{ trackId: '7' }, { trackId: '18' }],
          }),
        } as Response);
      }
      if (
        url.includes('/api/matches/match-a/identity')
        && !url.includes('/repair')
        && !url.includes('/promote')
        && init?.method === 'POST'
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            silentlyReconnected: false,
            cutCount: 0,
            reset: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/formation') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            availability: 'withheld',
            value: null,
            reasonCodes: ['SINGLE_FRAME_FORMATION'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics') && !url.includes('/inspect') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { events: [], limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            mode: 'unknown',
            reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            namespace: 'production',
            compatibleWithDevelopment: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/review') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            level: 1,
            decision: null,
            validatedMeasurement: false,
            samples: [{ time: 0, attackerX: 21, offsideLineX: 1, indeterminate: true }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            recorded: true,
            missing: ['x'],
            imputedAsCalibrated: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/assistance/report') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            factualCheck: { accepted: false, reasonCodes: ['FABRICATED_EVIDENCE'] },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recovery/import') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            reasonCodes: ['CORRUPTED_ARTIFACT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recompute') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            visionInvoked: false,
            reused: true,
            admitted: true,
            imageSpaceDetectionsReused: true,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/artifacts/alongside') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            digest: 'sha-new',
            previousDigest: 'sha-old',
            mutatedHistorical: false,
            namespace: 'match:match-a',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/players')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('"rows"'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('identityContinuous'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('forged'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/library/search'))).toBe(false);
    const posted = within(await screen.findByRole('region', { name: /uninjected observation write/i }));
    expect(posted.getByText(/ignore client rows and identityContinuous/i)).toBeTruthy();
    expect(posted.getByText(/totals stay withheld/i)).toBeTruthy();
    expect(posted.getByText(/forged trackId is not sent/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts incident geometry without client myTeam or attackDirection', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/geometry') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            decision: null,
            validatedMeasurement: false,
            attackDirection: 'right_to_left',
            mostAdvancedTeammateX: 21.0,
            reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/players') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            intervalLimited: true,
            totalsWithheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
            rows: [{ trackId: '7' }, { trackId: '18' }],
          }),
        } as Response);
      }
      if (
        url.includes('/api/matches/match-a/identity')
        && !url.includes('/repair')
        && !url.includes('/promote')
        && init?.method === 'POST'
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            silentlyReconnected: false,
            cutCount: 0,
            reset: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/formation') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            availability: 'withheld',
            value: null,
            reasonCodes: ['SINGLE_FRAME_FORMATION'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics') && !url.includes('/inspect') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { events: [], limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            mode: 'unknown',
            reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            namespace: 'production',
            compatibleWithDevelopment: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/review') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            level: 1,
            decision: null,
            validatedMeasurement: false,
            samples: [{ time: 0, attackerX: 21, offsideLineX: 1, indeterminate: true }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            recorded: true,
            missing: ['x'],
            imputedAsCalibrated: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/assistance/report') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            factualCheck: { accepted: false, reasonCodes: ['FABRICATED_EVIDENCE'] },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recovery/import') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            reasonCodes: ['CORRUPTED_ARTIFACT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recompute') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            visionInvoked: false,
            reused: true,
            admitted: true,
            imageSpaceDetectionsReused: true,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/artifacts/alongside') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            digest: 'sha-new',
            previousDigest: 'sha-old',
            mutatedHistorical: false,
            namespace: 'match:match-a',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/incidents/geometry')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('myTeam'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('attackDirection'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/workbench/'))).toBe(false);
    const posted = within(await screen.findByRole('region', { name: /uninjected origin write/i }));
    expect(posted.getByText(/ignores client myTeam and attackDirection/i)).toBeTruthy();
    expect(posted.getByText(/validatedMeasurement stays false/i)).toBeTruthy();
    expect(posted.getByText(/IFAB_LAW_11_NOT_APPLIED remains/)).toBeTruthy();
    expect(screen.queryAllByText(/attackerX=0/)).toHaveLength(0);
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts incident package without client forged-offside clips or notes', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/package') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            level: 0,
            clips: [],
            notes: [],
            decision: null,
            validatedMeasurement: false,
            reasonCodes: ['IFAB_LAW_11_NOT_APPLIED', 'MANUAL_INCIDENT_PACKAGE'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/geometry') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            decision: null,
            validatedMeasurement: false,
            attackDirection: 'right_to_left',
            mostAdvancedTeammateX: 21.0,
            reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/players') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            intervalLimited: true,
            totalsWithheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
            rows: [{ trackId: '7' }, { trackId: '18' }],
          }),
        } as Response);
      }
      if (
        url.includes('/api/matches/match-a/identity')
        && !url.includes('/repair')
        && !url.includes('/promote')
        && init?.method === 'POST'
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            silentlyReconnected: false,
            cutCount: 0,
            reset: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/formation') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            availability: 'withheld',
            value: null,
            reasonCodes: ['SINGLE_FRAME_FORMATION'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics') && !url.includes('/inspect') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { events: [], limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            mode: 'unknown',
            reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            namespace: 'production',
            compatibleWithDevelopment: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/review') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            level: 1,
            decision: null,
            validatedMeasurement: false,
            samples: [{ time: 0, attackerX: 21, offsideLineX: 1, indeterminate: true }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            recorded: true,
            missing: ['x'],
            imputedAsCalibrated: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/assistance/report') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            factualCheck: { accepted: false, reasonCodes: ['FABRICATED_EVIDENCE'] },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recovery/import') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            reasonCodes: ['CORRUPTED_ARTIFACT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recompute') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            visionInvoked: false,
            reused: true,
            admitted: true,
            imageSpaceDetectionsReused: true,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/artifacts/alongside') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            digest: 'sha-new',
            previousDigest: 'sha-old',
            mutatedHistorical: false,
            namespace: 'match:match-a',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/incidents/package')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('forged-offside'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('"clips"'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('"notes"'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/workbench/'))).toBe(false);
    const posted = within(await screen.findByRole('region', { name: /uninjected clip write/i }));
    expect(posted.getByText(/ignores client clips and notes/i)).toBeTruthy();
    expect(posted.getByText(/client forged-offside is not sent/i)).toBeTruthy();
    expect(posted.getByText(/validatedMeasurement stays false/i)).toBeTruthy();
    expect(screen.queryAllByText(/attackerX=0/)).toHaveLength(0);
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts event partition without client forged-accepted events', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/events/partition') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            rejectedRemovedFromAcceptedViews: true,
            acceptedViews: [],
            retainedCandidates: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/package') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            level: 0,
            clips: [],
            notes: [],
            decision: null,
            validatedMeasurement: false,
            reasonCodes: ['IFAB_LAW_11_NOT_APPLIED', 'MANUAL_INCIDENT_PACKAGE'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/geometry') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            decision: null,
            validatedMeasurement: false,
            attackDirection: 'right_to_left',
            mostAdvancedTeammateX: 21.0,
            reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/players') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            intervalLimited: true,
            totalsWithheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
            rows: [{ trackId: '7' }, { trackId: '18' }],
          }),
        } as Response);
      }
      if (
        url.includes('/api/matches/match-a/identity')
        && !url.includes('/repair')
        && !url.includes('/promote')
        && init?.method === 'POST'
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            silentlyReconnected: false,
            cutCount: 0,
            reset: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/formation') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            availability: 'withheld',
            value: null,
            reasonCodes: ['SINGLE_FRAME_FORMATION'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics') && !url.includes('/inspect') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { events: [], limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            mode: 'unknown',
            reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            namespace: 'production',
            compatibleWithDevelopment: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/review') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            level: 1,
            decision: null,
            validatedMeasurement: false,
            samples: [{ time: 0, attackerX: 21, offsideLineX: 1, indeterminate: true }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            recorded: true,
            missing: ['x'],
            imputedAsCalibrated: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/assistance/report') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            factualCheck: { accepted: false, reasonCodes: ['FABRICATED_EVIDENCE'] },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recovery/import') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            reasonCodes: ['CORRUPTED_ARTIFACT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recompute') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            visionInvoked: false,
            reused: true,
            admitted: true,
            imageSpaceDetectionsReused: true,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/artifacts/alongside') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            digest: 'sha-new',
            previousDigest: 'sha-old',
            mutatedHistorical: false,
            namespace: 'match:match-a',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/events/partition')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('forged-accepted'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('"events"'))
    ))).toBe(false);
    const posted = within(await screen.findByRole('region', { name: /uninjected candidate write/i }));
    expect(posted.getByText(/ignores client events/i)).toBeTruthy();
    expect(posted.getByText(/client forged-accepted is not sent/i)).toBeTruthy();
    expect(posted.getByText(/rejectedRemovedFromAcceptedViews stays true/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts legacy migrate without inventing client knownPossessionInvented', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/records/migrate') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            migrated: { possession_pct: { availability: 'unknown' } },
            rollback: { possession: null, myTeamDistance: null },
            rewrotePastOutcomes: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/events/partition') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ rejectedRemovedFromAcceptedViews: true, acceptedViews: [], retainedCandidates: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/package') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            level: 0,
            clips: [],
            notes: [],
            decision: null,
            validatedMeasurement: false,
            reasonCodes: ['IFAB_LAW_11_NOT_APPLIED', 'MANUAL_INCIDENT_PACKAGE'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/geometry') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            decision: null,
            validatedMeasurement: false,
            attackDirection: 'right_to_left',
            mostAdvancedTeammateX: 21.0,
            reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/players') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            intervalLimited: true,
            totalsWithheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
            rows: [{ trackId: '7' }, { trackId: '18' }],
          }),
        } as Response);
      }
      if (
        url.includes('/api/matches/match-a/identity')
        && !url.includes('/repair')
        && !url.includes('/promote')
        && init?.method === 'POST'
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            silentlyReconnected: false,
            cutCount: 0,
            reset: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/formation') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ availability: 'withheld', value: null, reasonCodes: ['SINGLE_FRAME_FORMATION'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics') && !url.includes('/inspect') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            metrics: [{
              metric: 'my_team_distance_m',
              availability: 'unknown',
              value: null,
              reasonCodes: ['IDENTITY_DISCONTINUITY'],
            }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { events: [], limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ mode: 'unknown', reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ namespace: 'production', compatibleWithDevelopment: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/review') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            level: 1,
            decision: null,
            validatedMeasurement: false,
            samples: [{ time: 0, attackerX: 21, offsideLineX: 1, indeterminate: true }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ recorded: true, missing: ['x'], imputedAsCalibrated: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/assistance/report') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ factualCheck: { accepted: false, reasonCodes: ['FABRICATED_EVIDENCE'] } }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recovery/import') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, reasonCodes: ['CORRUPTED_ARTIFACT'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recompute') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ visionInvoked: false, reused: true, admitted: true, imageSpaceDetectionsReused: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/artifacts/alongside') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            digest: 'sha-new',
            previousDigest: 'sha-old',
            mutatedHistorical: false,
            namespace: 'match:match-a',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/records/migrate')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('knownPossessionInvented'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('"possession":61'))
    ))).toBe(false);
    const posted = within(await screen.findByRole('region', { name: /uninvented possession write/i }));
    expect(posted.getByText(/ignores client knownPossessionInvented/i)).toBeTruthy();
    expect(posted.getByText(/client possession is not sent/i)).toBeTruthy();
    expect(posted.getByText(/rollback possession stays null/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts attack direction without sending client mapping', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/attack-direction') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ direction: 'right_to_left', fromStoredConfig: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/records/migrate') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            migrated: { possession_pct: { availability: 'unknown' } },
            rollback: { possession: null, myTeamDistance: null },
            rewrotePastOutcomes: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/events/partition') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ rejectedRemovedFromAcceptedViews: true, acceptedViews: [], retainedCandidates: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/package') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            level: 0,
            clips: [],
            notes: [],
            decision: null,
            validatedMeasurement: false,
            reasonCodes: ['IFAB_LAW_11_NOT_APPLIED', 'MANUAL_INCIDENT_PACKAGE'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/geometry') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            decision: null,
            validatedMeasurement: false,
            attackDirection: 'right_to_left',
            mostAdvancedTeammateX: 21.0,
            reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/players') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            intervalLimited: true,
            totalsWithheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
            rows: [{ trackId: '7' }, { trackId: '18' }],
          }),
        } as Response);
      }
      if (
        url.includes('/api/matches/match-a/identity')
        && !url.includes('/repair')
        && !url.includes('/promote')
        && init?.method === 'POST'
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            silentlyReconnected: false,
            cutCount: 0,
            reset: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/formation') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ availability: 'withheld', value: null, reasonCodes: ['SINGLE_FRAME_FORMATION'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics') && !url.includes('/inspect') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            metrics: [{
              metric: 'my_team_distance_m',
              availability: 'unknown',
              value: null,
              reasonCodes: ['IDENTITY_DISCONTINUITY'],
            }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { events: [], limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ mode: 'unknown', reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ namespace: 'production', compatibleWithDevelopment: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/review') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            level: 1,
            decision: null,
            validatedMeasurement: false,
            samples: [{ time: 0, attackerX: 21, offsideLineX: 1, indeterminate: true }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ recorded: true, missing: ['x'], imputedAsCalibrated: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/assistance/report') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ factualCheck: { accepted: false, reasonCodes: ['FABRICATED_EVIDENCE'] } }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recovery/import') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, reasonCodes: ['CORRUPTED_ARTIFACT'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recompute') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ visionInvoked: false, reused: true, admitted: true, imageSpaceDetectionsReused: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/artifacts/alongside') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            digest: 'sha-new',
            previousDigest: 'sha-old',
            mutatedHistorical: false,
            namespace: 'match:match-a',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/attack-direction')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('left_to_right'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('"mapping"'))
    ))).toBe(false);
    const posted = within(await screen.findByRole('region', { name: /unmapped direction write/i }));
    expect(posted.getByText(/does not send client mapping/i)).toBeTruthy();
    expect(posted.getByText(/client left_to_right is not sent/i)).toBeTruthy();
    expect(posted.getByText(/fromStoredConfig stays true/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts report provenance without client fabricated-evidence or knownEvidenceIds', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: true,
            reasonCodes: [],
            missingEvidenceIds: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/attack-direction') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ direction: 'right_to_left', fromStoredConfig: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/records/migrate') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            migrated: { possession_pct: { availability: 'unknown' } },
            rollback: { possession: null, myTeamDistance: null },
            rewrotePastOutcomes: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/events/partition') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ rejectedRemovedFromAcceptedViews: true, acceptedViews: [], retainedCandidates: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/package') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            level: 0,
            clips: [],
            notes: [],
            decision: null,
            validatedMeasurement: false,
            reasonCodes: ['IFAB_LAW_11_NOT_APPLIED', 'MANUAL_INCIDENT_PACKAGE'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/geometry') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            decision: null,
            validatedMeasurement: false,
            attackDirection: 'right_to_left',
            mostAdvancedTeammateX: 21.0,
            reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/players') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            intervalLimited: true,
            totalsWithheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
            rows: [{ trackId: '7' }, { trackId: '18' }],
          }),
        } as Response);
      }
      if (
        url.includes('/api/matches/match-a/identity')
        && !url.includes('/repair')
        && !url.includes('/promote')
        && init?.method === 'POST'
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            silentlyReconnected: false,
            cutCount: 0,
            reset: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/formation') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ availability: 'withheld', value: null, reasonCodes: ['SINGLE_FRAME_FORMATION'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics') && !url.includes('/inspect') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            metrics: [{
              metric: 'my_team_distance_m',
              availability: 'unknown',
              value: null,
              reasonCodes: ['IDENTITY_DISCONTINUITY'],
            }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { events: [], limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ mode: 'unknown', reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ namespace: 'production', compatibleWithDevelopment: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/review') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            level: 1,
            decision: null,
            validatedMeasurement: false,
            samples: [{ time: 0, attackerX: 21, offsideLineX: 1, indeterminate: true }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ recorded: true, missing: ['x'], imputedAsCalibrated: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/assistance/report') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ factualCheck: { accepted: false, reasonCodes: ['FABRICATED_EVIDENCE'] } }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recovery/import') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, reasonCodes: ['CORRUPTED_ARTIFACT'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recompute') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ visionInvoked: false, reused: true, admitted: true, imageSpaceDetectionsReused: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/artifacts/alongside') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            digest: 'sha-new',
            previousDigest: 'sha-old',
            mutatedHistorical: false,
            namespace: 'match:match-a',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/reports/provenance')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('fabricated-evidence'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('knownEvidenceIds'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/reports/assemble'))).toBe(false);
    const posted = within(await screen.findByRole('region', { name: /unclaimed evidence write/i }));
    expect(posted.getByText(/ignores client fabricated-evidence/i)).toBeTruthy();
    expect(posted.getByText(/client knownEvidenceIds are not sent/i)).toBeTruthy();
    expect(posted.getByText(/leftover \/api\/reports\/assemble stays unused/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts shot quality without imputing client goal rows as calibrated xG', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/quality') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: true, reasonCodes: [], missingEvidenceIds: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/attack-direction') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ direction: 'right_to_left', fromStoredConfig: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/records/migrate') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            migrated: { possession_pct: { availability: 'unknown' } },
            rollback: { possession: null, myTeamDistance: null },
            rewrotePastOutcomes: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/events/partition') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ rejectedRemovedFromAcceptedViews: true, acceptedViews: [], retainedCandidates: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/package') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            level: 0,
            clips: [],
            notes: [],
            decision: null,
            validatedMeasurement: false,
            reasonCodes: ['IFAB_LAW_11_NOT_APPLIED', 'MANUAL_INCIDENT_PACKAGE'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/geometry') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            decision: null,
            validatedMeasurement: false,
            attackDirection: 'right_to_left',
            mostAdvancedTeammateX: 21.0,
            reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/players') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            intervalLimited: true,
            totalsWithheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
            rows: [{ trackId: '7' }, { trackId: '18' }],
          }),
        } as Response);
      }
      if (
        url.includes('/api/matches/match-a/identity')
        && !url.includes('/repair')
        && !url.includes('/promote')
        && init?.method === 'POST'
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            silentlyReconnected: false,
            cutCount: 0,
            reset: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/formation') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ availability: 'withheld', value: null, reasonCodes: ['SINGLE_FRAME_FORMATION'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics') && !url.includes('/inspect') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            metrics: [{
              metric: 'my_team_distance_m',
              availability: 'unknown',
              value: null,
              reasonCodes: ['IDENTITY_DISCONTINUITY'],
            }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { events: [], limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ mode: 'unknown', reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ namespace: 'production', compatibleWithDevelopment: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/review') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            level: 1,
            decision: null,
            validatedMeasurement: false,
            samples: [{ time: 0, attackerX: 21, offsideLineX: 1, indeterminate: true }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ recorded: true, missing: ['x'], imputedAsCalibrated: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/assistance/report') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ factualCheck: { accepted: false, reasonCodes: ['FABRICATED_EVIDENCE'] } }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recovery/import') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, reasonCodes: ['CORRUPTED_ARTIFACT'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recompute') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ visionInvoked: false, reused: true, admitted: true, imageSpaceDetectionsReused: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/artifacts/alongside') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            digest: 'sha-new',
            previousDigest: 'sha-old',
            mutatedHistorical: false,
            namespace: 'match:match-a',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/shots/quality')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('"goal":true'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('"shots"'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/shots/tree'))).toBe(false);
    const posted = within(await screen.findByRole('region', { name: /unpublished xg write/i }));
    expect(posted.getByText(/ignores client shots and goal/i)).toBeTruthy();
    expect(posted.getByText(/client calibratedXg is not sent/i)).toBeTruthy();
    expect(posted.getByText(/publishedLabel stays experimental_shot_quality/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts analyst workflow without inventing a measured reviewed match', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            lockedLabelsPresent: false,
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/quality') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: true, reasonCodes: [], missingEvidenceIds: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/attack-direction') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ direction: 'right_to_left', fromStoredConfig: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/records/migrate') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            migrated: { possession_pct: { availability: 'unknown' } },
            rollback: { possession: null },
            rewrotePastOutcomes: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/events/partition') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ rejectedRemovedFromAcceptedViews: true, acceptedViews: [], retainedCandidates: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/package') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            level: 0,
            clips: [],
            notes: [],
            decision: null,
            validatedMeasurement: false,
            reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/geometry') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ decision: null, validatedMeasurement: false, reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/players') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ intervalLimited: true, totalsWithheld: true, reasonCodes: ['IDENTITY_DISCONTINUITY'] }),
        } as Response);
      }
      if (
        url.includes('/api/matches/match-a/identity')
        && !url.includes('/repair')
        && !url.includes('/promote')
        && init?.method === 'POST'
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ identityContinuous: false, silentlyReconnected: false, cutCount: 0 }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/formation') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ availability: 'withheld', value: null, reasonCodes: ['SINGLE_FRAME_FORMATION'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics') && !url.includes('/inspect') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ metrics: [{ metric: 'my_team_distance_m', availability: 'unknown', value: null }] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { events: [], limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ mode: 'unknown', reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ namespace: 'production', compatibleWithDevelopment: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/review') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ level: 1, decision: null, validatedMeasurement: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ recorded: true, missing: ['x'], imputedAsCalibrated: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/assistance/report') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ factualCheck: { accepted: false, reasonCodes: ['FABRICATED_EVIDENCE'] } }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recovery/import') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, reasonCodes: ['CORRUPTED_ARTIFACT'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recompute') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ visionInvoked: false, reused: true, admitted: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/artifacts/alongside') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ digest: 'sha-new', previousDigest: 'sha-old', mutatedHistorical: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/evaluation/workflow')
        && init?.method === 'POST'
        && String(init?.body) === '{}'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/evaluation/workflow')
      && Boolean(init?.body && String(init.body).includes('"measured":true'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/evaluation/workflow')
      && Boolean(init?.body && String(init.body).includes('analystCompletedReviewedMatch'))
    ))).toBe(false);
    const posted = within(await screen.findByRole('region', { name: /unmeasured workflow write/i }));
    expect(posted.getByText(/ignores client measured/i)).toBeTruthy();
    expect(posted.getByText(/client true flags are not sent/i)).toBeTruthy();
    expect(posted.getByText(/ANALYST_ACCEPTANCE_MISSING stays/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts evaluation prerequisites without inventing client completeTasks', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            lockedLabelsPresent: false,
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/quality') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ publishedLabel: 'experimental_shot_quality', calibratedXg: false, items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: true, reasonCodes: [], missingEvidenceIds: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/attack-direction') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ direction: 'right_to_left', fromStoredConfig: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/records/migrate') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            migrated: { possession_pct: { availability: 'unknown' } },
            rollback: { possession: null },
            rewrotePastOutcomes: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/events/partition') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ rejectedRemovedFromAcceptedViews: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/package') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ level: 0, decision: null, validatedMeasurement: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/geometry') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ decision: null, validatedMeasurement: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/players') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ intervalLimited: true, totalsWithheld: true }),
        } as Response);
      }
      if (
        url.includes('/api/matches/match-a/identity')
        && !url.includes('/repair')
        && !url.includes('/promote')
        && init?.method === 'POST'
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ identityContinuous: false, silentlyReconnected: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/formation') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ availability: 'withheld', value: null }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics') && !url.includes('/inspect') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ metrics: [{ metric: 'my_team_distance_m', availability: 'unknown', value: null }] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { events: [], limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ mode: 'unknown', reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ namespace: 'production', compatibleWithDevelopment: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/review') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ level: 1, decision: null, validatedMeasurement: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ recorded: true, imputedAsCalibrated: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ assignment: { kind: 'tracklet', forced: false }, silentlyReconnected: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/assistance/report') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ factualCheck: { accepted: false, reasonCodes: ['FABRICATED_EVIDENCE'] } }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recovery/import') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, reasonCodes: ['CORRUPTED_ARTIFACT'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/recompute') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ visionInvoked: false, reused: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/artifacts/alongside') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ digest: 'sha-new', previousDigest: 'sha-old', mutatedHistorical: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/evaluation/prerequisites')
        && init?.method === 'POST'
        && String(init?.body) === '{}'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/evaluation/prerequisites')
      && Boolean(init?.body && String(init.body).includes('completeTasks'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/evaluation/prerequisites')
      && Boolean(init?.body && String(init.body).includes('lockedLabelsPresent'))
    ))).toBe(false);
    const posted = within(await screen.findByRole('region', { name: /uninvented labels write/i }));
    expect(posted.getByText(/ignore client completeTasks/i)).toBeTruthy();
    expect(posted.getByText(/client 18 is not sent/i)).toBeTruthy();
    expect(posted.getByText(/lockedLabelsPresent stays false/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored frozen protocol without posting completeTasks 18', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            lockedLabelsPresent: false,
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/evaluation/protocol')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/evaluation/protocol')
      && init?.method === 'POST'
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('"completeTasks":18'))
    ))).toBe(false);
    const protocol = within(await screen.findByRole('region', { name: /stored frozen protocol/i }));
    expect(protocol.getByText(/football_analysis_pilot_labels_v3 remains unaccepted/i)).toBeTruthy();
    expect(protocol.getByText(/LABELS_INCOMPLETE/)).toBeTruthy();
    expect(protocol.getByText(/completeTasks stays 0/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored protocol prerequisites without treating locked labels as present', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            lockedLabelsPresent: false,
            nativePredictionsPresent: false,
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            lockedLabelsPresent: false,
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/evaluation/prerequisites')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    const stored = within(await screen.findByRole('region', { name: /stored protocol prerequisites/i }));
    expect(stored.getByText(/remain incomplete/i)).toBeTruthy();
    expect(stored.getByText(/lockedLabelsPresent is false/i)).toBeTruthy();
    expect(stored.getByText(/native predictions are not treated as labels/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored evaluation measures without treating TrackEval as ground truth', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            trackevalIsGroundTruth: false,
            annotationServiceHealthSatisfiesLabelGate: false,
            analystWorkflow: { measured: false },
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            lockedLabelsPresent: false,
            nativePredictionsPresent: false,
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/evaluation/measures')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    const measures = within(await screen.findByRole('region', { name: /stored evaluation measures/i }));
    expect(measures.getByText(/do not treat TrackEval as ground truth/i)).toBeTruthy();
    expect(measures.getByText(/annotation service health does not satisfy the label gate/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored HOTA measures without inventing image-space scores', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            trackevalIsGroundTruth: false,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            trackevalIsGroundTruth: false,
            annotationServiceHealthSatisfiesLabelGate: false,
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            lockedLabelsPresent: false,
            nativePredictionsPresent: false,
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/evaluation/hota')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    const hota = within(await screen.findByRole('region', { name: /stored hota measures/i }));
    expect(hota.getByText(/HOTA\/IDF1 remains unscored/i)).toBeTruthy();
    expect(hota.getByText(/official pitch positions are not image-space labels/i)).toBeTruthy();
    expect(hota.getByText(/NATIVE_PREDICTIONS_REQUIRED/)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts a durable match job only on request without inventing GPU or sealed inference', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/jobs') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            jobId: 'job-scope-1',
            status: 'queued',
            reused: false,
            costReserved: 0,
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            trackevalIsGroundTruth: false,
            annotationServiceHealthSatisfiesLabelGate: false,
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            lockedLabelsPresent: false,
            nativePredictionsPresent: false,
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => expect(screen.getByRole('button', { name: /request durable job/i })).toBeTruthy());
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/matches/match-a/jobs')
      && init?.method === 'POST'
    ))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /request durable job/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/jobs')
        && init?.method === 'POST'
        && String(init?.body) === '{}'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('"gpu"'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('completeMatch'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('DAYTONA_API_KEY'))
    ))).toBe(false);
    const posted = within(await screen.findByRole('region', { name: /unforced job write/i }));
    expect(posted.getByText(/ignores client GPU and completeMatch/i)).toBeTruthy();
    expect(posted.getByText(/client secrets are not sent/i)).toBeTruthy();
    expect(posted.getByText(/not sealed inference/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored collaboration lock without admitting hosted replacement', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            local: { silentlyReplaced: false, admitted: true },
            hosted: { admitted: false, silentlyReplaced: false },
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            trackevalIsGroundTruth: false,
            annotationServiceHealthSatisfiesLabelGate: false,
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/collaboration')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    const lock = within(await screen.findByRole('region', { name: /stored collaboration lock/i }));
    expect(lock.getByText(/hosted mode unadmitted/i)).toBeTruthy();
    expect(lock.getByText(/not silently replaced/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored media stride without treating target fps as inference fps', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            addsVidStrideAlone: false,
            targetFpsEqualsInferenceFps: false,
            explicitFrameContractRequired: true,
          }),
        } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            local: { silentlyReplaced: false },
            hosted: { admitted: false, silentlyReplaced: false },
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            trackevalIsGroundTruth: false,
            annotationServiceHealthSatisfiesLabelGate: false,
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/media/stride')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    const stride = within(await screen.findByRole('region', { name: /stored media stride/i }));
    expect(stride.getByText(/does not add vid_stride alone/i)).toBeTruthy();
    expect(stride.getByText(/target fps is not inference fps/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored job cost after a requested durable job without claiming sealed inference', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/jobs') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            jobId: 'job-scope-1',
            status: 'queued',
            reused: false,
            costReserved: 0,
          }),
        } as Response);
      }
      if (url.includes('/api/jobs/job-scope-1/cost') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ reservedTotal: 0, actualTotal: 0, p50Reserved: 0, requestId: 'job-scope-1' }),
        } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }),
        } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            trackevalIsGroundTruth: false,
            annotationServiceHealthSatisfiesLabelGate: false,
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => expect(screen.getByRole('button', { name: /request durable job/i })).toBeTruthy());
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/jobs/job-scope-1/cost'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /request durable job/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/jobs/job-scope-1/cost')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    const posted = within(await screen.findByRole('region', { name: /unforced job write/i }));
    expect(posted.getByText(/reservedTotal is not current-source sealed inference/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored credit allocation without paying for independent labels', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/credits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ authorised: false, gpuCreditsDoNotPayForLabels: true, accountBalance: null }),
        } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }) } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }) } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trackevalIsGroundTruth: false, annotationServiceHealthSatisfiesLabelGate: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/credits')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    const credits = within(await screen.findByRole('region', { name: /stored credit allocation/i }));
    expect(credits.getByText(/is unauthorised/i)).toBeTruthy();
    expect(credits.getByText(/GPU credits do not pay for independent labels/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored held-out questions without inferring fatigue', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/reports/held-out') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            questions: [
              { text: 'show our second-half turnovers followed by a shot within 10 seconds', unanswerable: false },
              { text: 'how tired was player 7 in the 89th minute', unanswerable: true },
            ],
          }),
        } as Response);
      }
      if (url.includes('/api/credits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ authorised: false, gpuCreditsDoNotPayForLabels: true }),
        } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }) } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }) } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trackevalIsGroundTruth: false, annotationServiceHealthSatisfiesLabelGate: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/reports/held-out')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    const held = within(await screen.findByRole('region', { name: /stored held-out questions/i }));
    expect(held.getByText(/keep fatigue unanswerable/i)).toBeTruthy();
    expect(held.getByText(/89th-minute tired query is not inferred/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored ground contact without treating box centre as the foot', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/geometry/contact') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ boxCentreIsFoot: false }),
        } as Response);
      }
      if (url.includes('/api/reports/held-out') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            questions: [{ text: 'how tired was player 7 in the 89th minute', unanswerable: true }],
          }),
        } as Response);
      }
      if (url.includes('/api/credits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ authorised: false, gpuCreditsDoNotPayForLabels: true }),
        } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }) } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }) } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trackevalIsGroundTruth: false, annotationServiceHealthSatisfiesLabelGate: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/geometry/contact')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/geometry/landmarks'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/geometry/preview'))).toBe(false);
    const contact = within(await screen.findByRole('region', { name: /stored ground contact/i }));
    expect(contact.getByText(/does not treat box centre as the foot/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored xT without treating socceraction import as extraction', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/xt') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, imported: false, socceractionImportDoesNotValidateExtraction: true, vaepEnabled: false }),
        } as Response);
      }
      if (url.includes('/api/geometry/contact') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ boxCentreIsFoot: false }) } as Response);
      }
      if (url.includes('/api/reports/held-out') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ questions: [{ text: 'how tired was player 7 in the 89th minute', unanswerable: true }] }),
        } as Response);
      }
      if (url.includes('/api/credits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ authorised: false, gpuCreditsDoNotPayForLabels: true }) } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }) } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }) } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trackevalIsGroundTruth: false, annotationServiceHealthSatisfiesLabelGate: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/xt')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    const xt = within(await screen.findByRole('region', { name: /stored xt plan/i }));
    expect(xt.getByText(/stays disabled/i)).toBeTruthy();
    expect(xt.getByText(/socceraction import does not validate extraction/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored rights without posting leftover evaluate', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/rights') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ uncertainCommercialPermissionBlocks: true, openSourceDoesNotMeanUnrestricted: true }),
        } as Response);
      }
      if (url.endsWith('/api/xt') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, socceractionImportDoesNotValidateExtraction: true }),
        } as Response);
      }
      if (url.includes('/api/geometry/contact') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ boxCentreIsFoot: false }) } as Response);
      }
      if (url.includes('/api/reports/held-out') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ questions: [{ text: 'how tired was player 7 in the 89th minute', unanswerable: true }] }),
        } as Response);
      }
      if (url.includes('/api/credits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ authorised: false, gpuCreditsDoNotPayForLabels: true }) } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }) } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }) } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trackevalIsGroundTruth: false, annotationServiceHealthSatisfiesLabelGate: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/rights')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/rights/evaluate'))).toBe(false);
    const rights = within(await screen.findByRole('region', { name: /stored rights register/i }));
    expect(rights.getByText(/keeps uncertain commercial permission blocking/i)).toBeTruthy();
    expect(rights.getByText(/client granted permission is ignored/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored model roster without leftover roster labels or promoting upgrades', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/roster') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [
              { task: 'player_ball', promoted: false },
              { task: 'geometry_metrics', promoted: false },
            ],
          }),
        } as Response);
      }
      if (url.endsWith('/api/rights') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ uncertainCommercialPermissionBlocks: true }) } as Response);
      }
      if (url.endsWith('/api/xt') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, socceractionImportDoesNotValidateExtraction: true }),
        } as Response);
      }
      if (url.includes('/api/geometry/contact') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ boxCentreIsFoot: false }) } as Response);
      }
      if (url.includes('/api/reports/held-out') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ questions: [{ text: 'how tired was player 7 in the 89th minute', unanswerable: true }] }),
        } as Response);
      }
      if (url.includes('/api/credits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ authorised: false, gpuCreditsDoNotPayForLabels: true }) } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }) } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }) } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trackevalIsGroundTruth: false, annotationServiceHealthSatisfiesLabelGate: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/roster')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    const roster = within(await screen.findByRole('region', { name: /stored model roster/i }));
    expect(roster.getByText(/keeps every upgrade unpromoted/i)).toBeTruthy();
    expect(roster.getByText(/leftover roster labels stay unused/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored risk register without treating service checks as locked labels', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/risks') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [
              { id: 'labels_incomplete', signal: 'service checks pass but locked labels remain incomplete', owner: 'reviewer_owner' },
              { id: 'unsupported_ai_claims', signal: 'invented evidence IDs or whole-match conclusions', owner: 'backend_analyst' },
            ],
          }),
        } as Response);
      }
      if (url.endsWith('/api/roster') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ task: 'player_ball', promoted: false }] }),
        } as Response);
      }
      if (url.endsWith('/api/rights') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ uncertainCommercialPermissionBlocks: true }) } as Response);
      }
      if (url.endsWith('/api/xt') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, socceractionImportDoesNotValidateExtraction: true }),
        } as Response);
      }
      if (url.includes('/api/geometry/contact') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ boxCentreIsFoot: false }) } as Response);
      }
      if (url.includes('/api/reports/held-out') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ questions: [{ text: 'how tired was player 7 in the 89th minute', unanswerable: true }] }),
        } as Response);
      }
      if (url.includes('/api/credits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ authorised: false, gpuCreditsDoNotPayForLabels: true }) } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }) } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }) } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trackevalIsGroundTruth: false, annotationServiceHealthSatisfiesLabelGate: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/risks')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    const risks = within(await screen.findByRole('region', { name: /stored risk register/i }));
    expect(risks.getByText(/labels_incomplete as a live risk/i)).toBeTruthy();
    expect(risks.getByText(/service checks are not locked labels/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored milestone progress without treating merged files as success', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/milestones') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            progress: {
              complete: false,
              completedAnalystTasks: 0,
              validatedCapabilityGates: 0,
              usesMergedFilesAsSuccess: false,
            },
          }),
        } as Response);
      }
      if (url.endsWith('/api/risks') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ id: 'labels_incomplete', owner: 'reviewer_owner' }] }),
        } as Response);
      }
      if (url.endsWith('/api/roster') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ task: 'player_ball', promoted: false }] }),
        } as Response);
      }
      if (url.endsWith('/api/rights') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ uncertainCommercialPermissionBlocks: true }) } as Response);
      }
      if (url.endsWith('/api/xt') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, socceractionImportDoesNotValidateExtraction: true }),
        } as Response);
      }
      if (url.includes('/api/geometry/contact') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ boxCentreIsFoot: false }) } as Response);
      }
      if (url.includes('/api/reports/held-out') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ questions: [{ text: 'how tired was player 7 in the 89th minute', unanswerable: true }] }),
        } as Response);
      }
      if (url.includes('/api/credits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ authorised: false, gpuCreditsDoNotPayForLabels: true }) } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }) } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }) } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trackevalIsGroundTruth: false, annotationServiceHealthSatisfiesLabelGate: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/milestones')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    const milestones = within(await screen.findByRole('region', { name: /stored milestone progress/i }));
    expect(milestones.getByText(/does not treat merged files as success/i)).toBeTruthy();
    expect(milestones.getByText(/completedAnalystTasks stays 0/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored network-failure metric without replacing unknown with a generated number', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/metrics/network-failure') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ availability: 'unknown', value: null, replacedWithGenerated: false }),
        } as Response);
      }
      if (url.endsWith('/api/milestones') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            progress: { complete: false, completedAnalystTasks: 0, usesMergedFilesAsSuccess: false },
          }),
        } as Response);
      }
      if (url.endsWith('/api/risks') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ id: 'labels_incomplete', owner: 'reviewer_owner' }] }),
        } as Response);
      }
      if (url.endsWith('/api/roster') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ task: 'player_ball', promoted: false }] }),
        } as Response);
      }
      if (url.endsWith('/api/rights') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ uncertainCommercialPermissionBlocks: true }) } as Response);
      }
      if (url.endsWith('/api/xt') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, socceractionImportDoesNotValidateExtraction: true }),
        } as Response);
      }
      if (url.includes('/api/geometry/contact') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ boxCentreIsFoot: false }) } as Response);
      }
      if (url.includes('/api/reports/held-out') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ questions: [{ text: 'how tired was player 7 in the 89th minute', unanswerable: true }] }),
        } as Response);
      }
      if (url.includes('/api/credits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ authorised: false, gpuCreditsDoNotPayForLabels: true }) } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }) } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }) } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trackevalIsGroundTruth: false, annotationServiceHealthSatisfiesLabelGate: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/metrics/network-failure')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/metrics/network-failure')
      && init?.method === 'POST'
    ))).toBe(false);
    const network = within(await screen.findByRole('region', { name: /stored network-failure metric/i }));
    expect(network.getByText(/stays unknown/i)).toBeTruthy();
    expect(network.getByText(/generated numbers do not replace missing values/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored metadata targets without treating planning numbers as measurements', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/targets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            planningTargetNotMeasurement: true,
            doesNotPromiseVideoDecodeLatency: true,
          }),
        } as Response);
      }
      if (url.includes('/api/metrics/network-failure') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ availability: 'unknown', value: null, replacedWithGenerated: false }),
        } as Response);
      }
      if (url.endsWith('/api/milestones') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            progress: { complete: false, completedAnalystTasks: 0, usesMergedFilesAsSuccess: false },
          }),
        } as Response);
      }
      if (url.endsWith('/api/risks') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ id: 'labels_incomplete', owner: 'reviewer_owner' }] }),
        } as Response);
      }
      if (url.endsWith('/api/roster') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ task: 'player_ball', promoted: false }] }),
        } as Response);
      }
      if (url.endsWith('/api/rights') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ uncertainCommercialPermissionBlocks: true }) } as Response);
      }
      if (url.endsWith('/api/xt') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, socceractionImportDoesNotValidateExtraction: true }),
        } as Response);
      }
      if (url.includes('/api/geometry/contact') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ boxCentreIsFoot: false }) } as Response);
      }
      if (url.includes('/api/reports/held-out') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ questions: [{ text: 'how tired was player 7 in the 89th minute', unanswerable: true }] }),
        } as Response);
      }
      if (url.includes('/api/credits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ authorised: false, gpuCreditsDoNotPayForLabels: true }) } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }) } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }) } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trackevalIsGroundTruth: false, annotationServiceHealthSatisfiesLabelGate: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/targets')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    const targets = within(await screen.findByRole('region', { name: /stored metadata targets/i }));
    expect(targets.getByText(/are planning targets, not measurements/i)).toBeTruthy();
    expect(targets.getByText(/do not promise video decode latency/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored architecture decisions without treating merged files as capability release', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/decisions') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [
              { id: 'capability_release', decision: 'independent_gates_not_merged_files', reversible: true },
            ],
          }),
        } as Response);
      }
      if (url.endsWith('/api/targets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ measured: false, doesNotPromiseVideoDecodeLatency: true }),
        } as Response);
      }
      if (url.includes('/api/metrics/network-failure') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ availability: 'unknown', value: null, replacedWithGenerated: false }),
        } as Response);
      }
      if (url.endsWith('/api/milestones') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            progress: { complete: false, completedAnalystTasks: 0, usesMergedFilesAsSuccess: false },
          }),
        } as Response);
      }
      if (url.endsWith('/api/risks') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ id: 'labels_incomplete', owner: 'reviewer_owner' }] }),
        } as Response);
      }
      if (url.endsWith('/api/roster') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ task: 'player_ball', promoted: false }] }),
        } as Response);
      }
      if (url.endsWith('/api/rights') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ uncertainCommercialPermissionBlocks: true }) } as Response);
      }
      if (url.endsWith('/api/xt') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, socceractionImportDoesNotValidateExtraction: true }),
        } as Response);
      }
      if (url.includes('/api/geometry/contact') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ boxCentreIsFoot: false }) } as Response);
      }
      if (url.includes('/api/reports/held-out') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ questions: [{ text: 'how tired was player 7 in the 89th minute', unanswerable: true }] }),
        } as Response);
      }
      if (url.includes('/api/credits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ authorised: false, gpuCreditsDoNotPayForLabels: true }) } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }) } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }) } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trackevalIsGroundTruth: false, annotationServiceHealthSatisfiesLabelGate: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/decisions')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    const decisions = within(await screen.findByRole('region', { name: /stored architecture decisions/i }));
    expect(decisions.getByText(/keep independent gates, not merged files/i)).toBeTruthy();
    expect(decisions.getByText(/capability release stays reversible/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored residency claim without treating requested region as EU proof', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/residency') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            provider: 'daytona',
            requestedRegion: 'eu',
            euProcessingProven: false,
            reasonCodes: ['REQUESTED_REGION_IS_NOT_PROOF'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/decisions') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{ id: 'capability_release', decision: 'independent_gates_not_merged_files', reversible: true }],
          }),
        } as Response);
      }
      if (url.endsWith('/api/targets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ measured: false, doesNotPromiseVideoDecodeLatency: true }),
        } as Response);
      }
      if (url.includes('/api/metrics/network-failure') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ availability: 'unknown', value: null, replacedWithGenerated: false }),
        } as Response);
      }
      if (url.endsWith('/api/milestones') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            progress: { complete: false, completedAnalystTasks: 0, usesMergedFilesAsSuccess: false },
          }),
        } as Response);
      }
      if (url.endsWith('/api/risks') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ id: 'labels_incomplete', owner: 'reviewer_owner' }] }),
        } as Response);
      }
      if (url.endsWith('/api/roster') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ task: 'player_ball', promoted: false }] }),
        } as Response);
      }
      if (url.endsWith('/api/rights') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ uncertainCommercialPermissionBlocks: true }) } as Response);
      }
      if (url.endsWith('/api/xt') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, socceractionImportDoesNotValidateExtraction: true }),
        } as Response);
      }
      if (url.includes('/api/geometry/contact') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ boxCentreIsFoot: false }) } as Response);
      }
      if (url.includes('/api/reports/held-out') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ questions: [{ text: 'how tired was player 7 in the 89th minute', unanswerable: true }] }),
        } as Response);
      }
      if (url.includes('/api/credits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ authorised: false, gpuCreditsDoNotPayForLabels: true }) } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }) } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }) } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trackevalIsGroundTruth: false, annotationServiceHealthSatisfiesLabelGate: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/residency')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    const residency = within(await screen.findByRole('region', { name: /stored residency claim/i }));
    expect(residency.getByText(/does not prove EU processing/i)).toBeTruthy();
    expect(residency.getByText(/requested region is not proof/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored distributed broker without renaming the current queue', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/broker') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, renamesCurrentQueue: false }),
        } as Response);
      }
      if (url.endsWith('/api/residency') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ euProcessingProven: false, reasonCodes: ['REQUESTED_REGION_IS_NOT_PROOF'] }),
        } as Response);
      }
      if (url.endsWith('/api/decisions') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{ id: 'capability_release', decision: 'independent_gates_not_merged_files', reversible: true }],
          }),
        } as Response);
      }
      if (url.endsWith('/api/targets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ measured: false, doesNotPromiseVideoDecodeLatency: true }),
        } as Response);
      }
      if (url.includes('/api/metrics/network-failure') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ availability: 'unknown', value: null, replacedWithGenerated: false }),
        } as Response);
      }
      if (url.endsWith('/api/milestones') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            progress: { complete: false, completedAnalystTasks: 0, usesMergedFilesAsSuccess: false },
          }),
        } as Response);
      }
      if (url.endsWith('/api/risks') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ id: 'labels_incomplete', owner: 'reviewer_owner' }] }),
        } as Response);
      }
      if (url.endsWith('/api/roster') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ task: 'player_ball', promoted: false }] }),
        } as Response);
      }
      if (url.endsWith('/api/rights') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ uncertainCommercialPermissionBlocks: true }) } as Response);
      }
      if (url.endsWith('/api/xt') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, socceractionImportDoesNotValidateExtraction: true }),
        } as Response);
      }
      if (url.includes('/api/geometry/contact') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ boxCentreIsFoot: false }) } as Response);
      }
      if (url.includes('/api/reports/held-out') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ questions: [{ text: 'how tired was player 7 in the 89th minute', unanswerable: true }] }),
        } as Response);
      }
      if (url.includes('/api/credits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ authorised: false, gpuCreditsDoNotPayForLabels: true }) } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }) } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }) } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trackevalIsGroundTruth: false, annotationServiceHealthSatisfiesLabelGate: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/broker')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    const broker = within(await screen.findByRole('region', { name: /stored distributed broker/i }));
    expect(broker.getByText(/stays unadmitted/i)).toBeTruthy();
    expect(broker.getByText(/does not rename the current queue/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored vector database without treating embeddings as tactical proof', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/vector') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, embeddingsProveTacticalWeakness: false }),
        } as Response);
      }
      if (url.endsWith('/api/broker') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, renamesCurrentQueue: false }),
        } as Response);
      }
      if (url.endsWith('/api/residency') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ euProcessingProven: false, reasonCodes: ['REQUESTED_REGION_IS_NOT_PROOF'] }),
        } as Response);
      }
      if (url.endsWith('/api/decisions') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{ id: 'capability_release', decision: 'independent_gates_not_merged_files', reversible: true }],
          }),
        } as Response);
      }
      if (url.endsWith('/api/targets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ measured: false, doesNotPromiseVideoDecodeLatency: true }),
        } as Response);
      }
      if (url.includes('/api/metrics/network-failure') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ availability: 'unknown', value: null, replacedWithGenerated: false }),
        } as Response);
      }
      if (url.endsWith('/api/milestones') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            progress: { complete: false, completedAnalystTasks: 0, usesMergedFilesAsSuccess: false },
          }),
        } as Response);
      }
      if (url.endsWith('/api/risks') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ id: 'labels_incomplete', owner: 'reviewer_owner' }] }),
        } as Response);
      }
      if (url.endsWith('/api/roster') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ task: 'player_ball', promoted: false }] }),
        } as Response);
      }
      if (url.endsWith('/api/rights') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ uncertainCommercialPermissionBlocks: true }) } as Response);
      }
      if (url.endsWith('/api/xt') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, socceractionImportDoesNotValidateExtraction: true }),
        } as Response);
      }
      if (url.includes('/api/geometry/contact') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ boxCentreIsFoot: false }) } as Response);
      }
      if (url.includes('/api/reports/held-out') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ questions: [{ text: 'how tired was player 7 in the 89th minute', unanswerable: true }] }),
        } as Response);
      }
      if (url.includes('/api/credits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ authorised: false, gpuCreditsDoNotPayForLabels: true }) } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }) } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }) } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trackevalIsGroundTruth: false, annotationServiceHealthSatisfiesLabelGate: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/vector')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/search/tactical-themes'))).toBe(false);
    const vector = within(await screen.findByRole('region', { name: /stored vector database/i }));
    expect(vector.getByText(/stays unadmitted/i)).toBeTruthy();
    expect(vector.getByText(/embeddings are not proof of tactical weakness/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored hosted deployment without silent cloud fallback', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/deployment/hosted_collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ admitted: false, silentCloudFallback: false, requiresGNetwork: true }),
        } as Response);
      }
      if (url.endsWith('/api/vector') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, embeddingsProveTacticalWeakness: false }),
        } as Response);
      }
      if (url.endsWith('/api/broker') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, renamesCurrentQueue: false }),
        } as Response);
      }
      if (url.endsWith('/api/residency') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ euProcessingProven: false, reasonCodes: ['REQUESTED_REGION_IS_NOT_PROOF'] }),
        } as Response);
      }
      if (url.endsWith('/api/decisions') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{ id: 'capability_release', decision: 'independent_gates_not_merged_files', reversible: true }],
          }),
        } as Response);
      }
      if (url.endsWith('/api/targets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ measured: false, doesNotPromiseVideoDecodeLatency: true }),
        } as Response);
      }
      if (url.includes('/api/metrics/network-failure') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ availability: 'unknown', value: null, replacedWithGenerated: false }),
        } as Response);
      }
      if (url.endsWith('/api/milestones') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            progress: { complete: false, completedAnalystTasks: 0, usesMergedFilesAsSuccess: false },
          }),
        } as Response);
      }
      if (url.endsWith('/api/risks') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ id: 'labels_incomplete', owner: 'reviewer_owner' }] }),
        } as Response);
      }
      if (url.endsWith('/api/roster') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ task: 'player_ball', promoted: false }] }),
        } as Response);
      }
      if (url.endsWith('/api/rights') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ uncertainCommercialPermissionBlocks: true }) } as Response);
      }
      if (url.endsWith('/api/xt') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, socceractionImportDoesNotValidateExtraction: true }),
        } as Response);
      }
      if (url.includes('/api/geometry/contact') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ boxCentreIsFoot: false }) } as Response);
      }
      if (url.includes('/api/reports/held-out') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ questions: [{ text: 'how tired was player 7 in the 89th minute', unanswerable: true }] }),
        } as Response);
      }
      if (url.includes('/api/credits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ authorised: false, gpuCreditsDoNotPayForLabels: true }) } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }) } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }) } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trackevalIsGroundTruth: false, annotationServiceHealthSatisfiesLabelGate: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/deployment/hosted_collaboration')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    const hosted = within(await screen.findByRole('region', { name: /stored hosted deployment/i }));
    expect(hosted.getByText(/stays unadmitted/i)).toBeTruthy();
    expect(hosted.getByText(/requires G-NETWORK/i)).toBeTruthy();
    expect(hosted.getByText(/silent cloud fallback stays off/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored handheld admission without certifying physical metrics', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/admission/handheld_low_angle') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            profile: 'handheld_low_angle',
            certified: false,
            automation: 'manual_tagging',
            withhold: ['physical_metrics', 'full_team_metrics'],
          }),
        } as Response);
      }
      if (url.includes('/api/deployment/hosted_collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ admitted: false, silentCloudFallback: false, requiresGNetwork: true }),
        } as Response);
      }
      if (url.endsWith('/api/vector') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, embeddingsProveTacticalWeakness: false }),
        } as Response);
      }
      if (url.endsWith('/api/broker') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, renamesCurrentQueue: false }),
        } as Response);
      }
      if (url.endsWith('/api/residency') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ euProcessingProven: false, reasonCodes: ['REQUESTED_REGION_IS_NOT_PROOF'] }),
        } as Response);
      }
      if (url.endsWith('/api/decisions') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{ id: 'capability_release', decision: 'independent_gates_not_merged_files', reversible: true }],
          }),
        } as Response);
      }
      if (url.endsWith('/api/targets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ measured: false, doesNotPromiseVideoDecodeLatency: true }),
        } as Response);
      }
      if (url.includes('/api/metrics/network-failure') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ availability: 'unknown', value: null, replacedWithGenerated: false }),
        } as Response);
      }
      if (url.endsWith('/api/milestones') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            progress: { complete: false, completedAnalystTasks: 0, usesMergedFilesAsSuccess: false },
          }),
        } as Response);
      }
      if (url.endsWith('/api/risks') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ id: 'labels_incomplete', owner: 'reviewer_owner' }] }),
        } as Response);
      }
      if (url.endsWith('/api/roster') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ task: 'player_ball', promoted: false }] }),
        } as Response);
      }
      if (url.endsWith('/api/rights') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ uncertainCommercialPermissionBlocks: true }) } as Response);
      }
      if (url.endsWith('/api/xt') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, socceractionImportDoesNotValidateExtraction: true }),
        } as Response);
      }
      if (url.includes('/api/geometry/contact') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ boxCentreIsFoot: false }) } as Response);
      }
      if (url.includes('/api/reports/held-out') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ questions: [{ text: 'how tired was player 7 in the 89th minute', unanswerable: true }] }),
        } as Response);
      }
      if (url.includes('/api/credits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ authorised: false, gpuCreditsDoNotPayForLabels: true }) } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }) } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }) } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trackevalIsGroundTruth: false, annotationServiceHealthSatisfiesLabelGate: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/admission/handheld_low_angle')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/workbench/admission'))).toBe(false);
    const admission = within(await screen.findByRole('region', { name: /stored handheld admission/i }));
    expect(admission.getByText(/is not certified/i)).toBeTruthy();
    expect(admission.getByText(/physical_metrics stay on the withhold list/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored research lane without executing planned tracks', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/research/lane') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            isolated: true,
            autonomousProductionChanges: false,
            tracks: [
              { id: 'supported-coverage', executable: true, inert: false },
              { id: 'possession/events', executable: false, inert: true },
            ],
          }),
        } as Response);
      }
      if (url.includes('/api/admission/handheld_low_angle') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ certified: false, withhold: ['physical_metrics'] }),
        } as Response);
      }
      if (url.includes('/api/deployment/hosted_collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ admitted: false, silentCloudFallback: false, requiresGNetwork: true }),
        } as Response);
      }
      if (url.endsWith('/api/vector') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, embeddingsProveTacticalWeakness: false }),
        } as Response);
      }
      if (url.endsWith('/api/broker') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, renamesCurrentQueue: false }),
        } as Response);
      }
      if (url.endsWith('/api/residency') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ euProcessingProven: false, reasonCodes: ['REQUESTED_REGION_IS_NOT_PROOF'] }),
        } as Response);
      }
      if (url.endsWith('/api/decisions') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{ id: 'capability_release', decision: 'independent_gates_not_merged_files', reversible: true }],
          }),
        } as Response);
      }
      if (url.endsWith('/api/targets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ measured: false, doesNotPromiseVideoDecodeLatency: true }),
        } as Response);
      }
      if (url.includes('/api/metrics/network-failure') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ availability: 'unknown', value: null, replacedWithGenerated: false }),
        } as Response);
      }
      if (url.endsWith('/api/milestones') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            progress: { complete: false, completedAnalystTasks: 0, usesMergedFilesAsSuccess: false },
          }),
        } as Response);
      }
      if (url.endsWith('/api/risks') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ id: 'labels_incomplete', owner: 'reviewer_owner' }] }),
        } as Response);
      }
      if (url.endsWith('/api/roster') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ task: 'player_ball', promoted: false }] }),
        } as Response);
      }
      if (url.endsWith('/api/rights') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ uncertainCommercialPermissionBlocks: true }) } as Response);
      }
      if (url.endsWith('/api/xt') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, socceractionImportDoesNotValidateExtraction: true }),
        } as Response);
      }
      if (url.includes('/api/geometry/contact') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ boxCentreIsFoot: false }) } as Response);
      }
      if (url.includes('/api/reports/held-out') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ questions: [{ text: 'how tired was player 7 in the 89th minute', unanswerable: true }] }),
        } as Response);
      }
      if (url.includes('/api/credits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ authorised: false, gpuCreditsDoNotPayForLabels: true }) } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }) } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }) } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trackevalIsGroundTruth: false, annotationServiceHealthSatisfiesLabelGate: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/research/lane')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    const lane = within(await screen.findByRole('region', { name: /stored research lane/i }));
    expect(lane.getByText(/keeps planned tracks inert/i)).toBeTruthy();
    expect(lane.getByText(/autonomous production changes stay blocked/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored scale scenario without treating planning totals as measured performance', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/scale/10') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            matchesPerMonth: 10,
            measuredApplicationPerformance: false,
            gbEqualsGiB: false,
            decimalGb: 5.4,
          }),
        } as Response);
      }
      if (url.endsWith('/api/research/lane') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ isolated: true, autonomousProductionChanges: false, tracks: [{ id: 'possession/events', inert: true }] }),
        } as Response);
      }
      if (url.includes('/api/admission/handheld_low_angle') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ certified: false, withhold: ['physical_metrics'] }),
        } as Response);
      }
      if (url.includes('/api/deployment/hosted_collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ admitted: false, silentCloudFallback: false, requiresGNetwork: true }),
        } as Response);
      }
      if (url.endsWith('/api/vector') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, embeddingsProveTacticalWeakness: false }),
        } as Response);
      }
      if (url.endsWith('/api/broker') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, renamesCurrentQueue: false }),
        } as Response);
      }
      if (url.endsWith('/api/residency') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ euProcessingProven: false, reasonCodes: ['REQUESTED_REGION_IS_NOT_PROOF'] }),
        } as Response);
      }
      if (url.endsWith('/api/decisions') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{ id: 'capability_release', decision: 'independent_gates_not_merged_files', reversible: true }],
          }),
        } as Response);
      }
      if (url.endsWith('/api/targets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ measured: false, doesNotPromiseVideoDecodeLatency: true }),
        } as Response);
      }
      if (url.includes('/api/metrics/network-failure') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ availability: 'unknown', value: null, replacedWithGenerated: false }),
        } as Response);
      }
      if (url.endsWith('/api/milestones') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            progress: { complete: false, completedAnalystTasks: 0, usesMergedFilesAsSuccess: false },
          }),
        } as Response);
      }
      if (url.endsWith('/api/risks') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ id: 'labels_incomplete', owner: 'reviewer_owner' }] }),
        } as Response);
      }
      if (url.endsWith('/api/roster') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ task: 'player_ball', promoted: false }] }),
        } as Response);
      }
      if (url.endsWith('/api/rights') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ uncertainCommercialPermissionBlocks: true }) } as Response);
      }
      if (url.endsWith('/api/xt') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, socceractionImportDoesNotValidateExtraction: true }),
        } as Response);
      }
      if (url.includes('/api/geometry/contact') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ boxCentreIsFoot: false }) } as Response);
      }
      if (url.includes('/api/reports/held-out') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ questions: [{ text: 'how tired was player 7 in the 89th minute', unanswerable: true }] }),
        } as Response);
      }
      if (url.includes('/api/credits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ authorised: false, gpuCreditsDoNotPayForLabels: true }) } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }) } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }) } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trackevalIsGroundTruth: false, annotationServiceHealthSatisfiesLabelGate: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/scale/10')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    const scale = within(await screen.findByRole('region', { name: /stored scale scenario/i }));
    expect(scale.getByText(/is not measured application performance/i)).toBeTruthy();
    expect(scale.getByText(/decimal GB is not GiB/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts media admit, cost estimate, and rollback without client remote URL, export fps, or gpu_default outputs', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/media/admit') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ admitted: false, reasonCodes: ['UNSUPPORTED_CODEC'] }),
        } as Response);
      }
      if (url.endsWith('/api/cost/estimate') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ exportFpsEqualsInferenceFps: false, allocatedCompute: 0, total: 0 }),
        } as Response);
      }
      if (url.endsWith('/api/rollback') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            newJobsAdmitted: false,
            artifactsPreserved: true,
            rewrotePastTrialOutcomes: false,
            staleOutputs: [],
            flagName: 'unspecified',
          }),
        } as Response);
      }
      if (url.includes('/api/scale/10') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            matchesPerMonth: 10,
            measuredApplicationPerformance: false,
            gbEqualsGiB: false,
            decimalGb: 5.4,
          }),
        } as Response);
      }
      if (url.endsWith('/api/research/lane') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ isolated: true, autonomousProductionChanges: false, tracks: [{ id: 'possession/events', inert: true }] }),
        } as Response);
      }
      if (url.includes('/api/admission/handheld_low_angle') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ certified: false, withhold: ['physical_metrics'] }),
        } as Response);
      }
      if (url.includes('/api/deployment/hosted_collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ admitted: false, silentCloudFallback: false, requiresGNetwork: true }),
        } as Response);
      }
      if (url.endsWith('/api/vector') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, embeddingsProveTacticalWeakness: false }),
        } as Response);
      }
      if (url.endsWith('/api/broker') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, renamesCurrentQueue: false }),
        } as Response);
      }
      if (url.endsWith('/api/residency') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ euProcessingProven: false, reasonCodes: ['REQUESTED_REGION_IS_NOT_PROOF'] }),
        } as Response);
      }
      if (url.endsWith('/api/decisions') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{ id: 'capability_release', decision: 'independent_gates_not_merged_files', reversible: true }],
          }),
        } as Response);
      }
      if (url.endsWith('/api/targets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ measured: false, doesNotPromiseVideoDecodeLatency: true }),
        } as Response);
      }
      if (url.includes('/api/metrics/network-failure') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ availability: 'unknown', value: null, replacedWithGenerated: false }),
        } as Response);
      }
      if (url.endsWith('/api/milestones') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            progress: { complete: false, completedAnalystTasks: 0, usesMergedFilesAsSuccess: false },
          }),
        } as Response);
      }
      if (url.endsWith('/api/risks') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ id: 'labels_incomplete', owner: 'reviewer_owner' }] }),
        } as Response);
      }
      if (url.endsWith('/api/roster') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ task: 'player_ball', promoted: false }] }),
        } as Response);
      }
      if (url.endsWith('/api/rights') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ uncertainCommercialPermissionBlocks: true }) } as Response);
      }
      if (url.endsWith('/api/xt') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, socceractionImportDoesNotValidateExtraction: true }),
        } as Response);
      }
      if (url.includes('/api/geometry/contact') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ boxCentreIsFoot: false }) } as Response);
      }
      if (url.includes('/api/reports/held-out') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ questions: [{ text: 'how tired was player 7 in the 89th minute', unanswerable: true }] }),
        } as Response);
      }
      if (url.includes('/api/credits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ authorised: false, gpuCreditsDoNotPayForLabels: true }) } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }) } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }) } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trackevalIsGroundTruth: false, annotationServiceHealthSatisfiesLabelGate: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => expect(screen.getByRole('button', { name: /request media admit/i })).toBeTruthy());
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/media/admit'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/cost/estimate'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/api/rollback'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /request media admit/i }));
    fireEvent.click(screen.getByRole('button', { name: /request cost estimate/i }));
    fireEvent.click(screen.getByRole('button', { name: /request release rollback/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/media/admit')
        && init?.method === 'POST'
        && String(init?.body) === '{}'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/cost/estimate')
      && init?.method === 'POST'
      && String(init?.body) === '{}'
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/rollback')
      && init?.method === 'POST'
      && String(init?.body) === '{}'
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/media/admit')
      && Boolean(init?.body && String(init.body).includes('sourceUrl'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/cost/estimate')
      && Boolean(init?.body && (String(init.body).includes('exportFps') || String(init.body).includes('allocatedCompute')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/rollback')
      && Boolean(init?.body && (String(init.body).includes('gpu_default') || String(init.body).includes('run-17-report')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    const admit = within(await screen.findByRole('region', { name: /unforced media admit/i }));
    expect(admit.getByText(/stays refused/i)).toBeTruthy();
    expect(admit.getByText(/client remote URL is not sent/i)).toBeTruthy();
    expect(admit.getByText(/empty codec stays unsupported/i)).toBeTruthy();
    const cost = within(screen.getByRole('region', { name: /unforced cost estimate/i }));
    expect(cost.getByText(/keeps export fps off inference cost/i)).toBeTruthy();
    expect(cost.getByText(/client export fps 5 is not sent/i)).toBeTruthy();
    expect(cost.getByText(/allocated compute stays zero/i)).toBeTruthy();
    const rolled = within(screen.getByRole('region', { name: /unforced release rollback/i }));
    expect(rolled.getByText(/keeps new jobs refused/i)).toBeTruthy();
    expect(rolled.getByText(/client gpu_default and run-17-report are not sent/i)).toBeTruthy();
    expect(rolled.getByText(/past trial outcomes stay unwritten/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored training drills, repository policy, and support bundle without inventing medical load, GPU work, or consent', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/training/drills') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{ name: 'near-side recovery 2v2', coachReviewed: true }],
            prescribesMedicalLoad: false,
            diagnosesFatigueOrInjury: false,
          }),
        } as Response);
      }
      if (url.endsWith('/api/repository') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ httpMayRunGpu: false, vectorBrokerRequired: false, replacesStorageModule: false }),
        } as Response);
      }
      if (url.endsWith('/api/support/bundle') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ released: false, reasonCodes: ['CONSENT_REQUIRED'] }),
        } as Response);
      }
      if (url.includes('/api/scale/10') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            matchesPerMonth: 10,
            measuredApplicationPerformance: false,
            gbEqualsGiB: false,
            decimalGb: 5.4,
          }),
        } as Response);
      }
      if (url.endsWith('/api/research/lane') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ isolated: true, autonomousProductionChanges: false, tracks: [{ id: 'possession/events', inert: true }] }),
        } as Response);
      }
      if (url.includes('/api/admission/handheld_low_angle') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ certified: false, withhold: ['physical_metrics'] }),
        } as Response);
      }
      if (url.includes('/api/deployment/hosted_collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ admitted: false, silentCloudFallback: false, requiresGNetwork: true }),
        } as Response);
      }
      if (url.endsWith('/api/vector') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, embeddingsProveTacticalWeakness: false }),
        } as Response);
      }
      if (url.endsWith('/api/broker') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, renamesCurrentQueue: false }),
        } as Response);
      }
      if (url.endsWith('/api/residency') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ euProcessingProven: false, reasonCodes: ['REQUESTED_REGION_IS_NOT_PROOF'] }),
        } as Response);
      }
      if (url.endsWith('/api/decisions') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{ id: 'capability_release', decision: 'independent_gates_not_merged_files', reversible: true }],
          }),
        } as Response);
      }
      if (url.endsWith('/api/targets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ measured: false, doesNotPromiseVideoDecodeLatency: true }),
        } as Response);
      }
      if (url.includes('/api/metrics/network-failure') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ availability: 'unknown', value: null, replacedWithGenerated: false }),
        } as Response);
      }
      if (url.endsWith('/api/milestones') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            progress: { complete: false, completedAnalystTasks: 0, usesMergedFilesAsSuccess: false },
          }),
        } as Response);
      }
      if (url.endsWith('/api/risks') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ id: 'labels_incomplete', owner: 'reviewer_owner' }] }),
        } as Response);
      }
      if (url.endsWith('/api/roster') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ task: 'player_ball', promoted: false }] }),
        } as Response);
      }
      if (url.endsWith('/api/rights') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ uncertainCommercialPermissionBlocks: true }) } as Response);
      }
      if (url.endsWith('/api/xt') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, socceractionImportDoesNotValidateExtraction: true }),
        } as Response);
      }
      if (url.includes('/api/geometry/contact') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ boxCentreIsFoot: false }) } as Response);
      }
      if (url.includes('/api/reports/held-out') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ questions: [{ text: 'how tired was player 7 in the 89th minute', unanswerable: true }] }),
        } as Response);
      }
      if (url.includes('/api/credits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ authorised: false, gpuCreditsDoNotPayForLabels: true }) } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }) } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }) } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trackevalIsGroundTruth: false, annotationServiceHealthSatisfiesLabelGate: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/training/drills')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/repository')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/support/bundle')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/support/bundle')
      && init?.method === 'POST'
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    const drills = within(await screen.findByRole('region', { name: /stored training drills/i }));
    expect(drills.getByText(/keep medical load unprescribed/i)).toBeTruthy();
    expect(drills.getByText(/fatigue and injury stay undiagnosed from tracking/i)).toBeTruthy();
    const repository = within(screen.getByRole('region', { name: /stored repository policy/i }));
    expect(repository.getByText(/keeps HTTP off GPU work/i)).toBeTruthy();
    expect(repository.getByText(/vector broker is not required/i)).toBeTruthy();
    expect(repository.getByText(/storage module stays unreplaced/i)).toBeTruthy();
    const bundle = within(screen.getByRole('region', { name: /stored support bundle/i }));
    expect(bundle.getByText(/stays unreleased/i)).toBeTruthy();
    expect(bundle.getByText(/client consented true is ignored/i)).toBeTruthy();
    expect(bundle.getByText(/CONSENT_REQUIRED stays blocking/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored object storage, preemptible policy, and pitch axes without inventing hosted storage or checkpoints', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/storage/object') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, mandatoryDuckDb: false, role: 'local_content_addressed' }),
        } as Response);
      }
      if (url.endsWith('/api/preemptible') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ allowed: false }),
        } as Response);
      }
      if (url.endsWith('/api/quantities/axes') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            x: 'longitudinal',
            y: 'lateral',
            origin: 'declared_calibration',
            legacyDisplay: 'transform_explicitly',
          }),
        } as Response);
      }
      if (url.endsWith('/api/training/drills') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{ name: 'near-side recovery 2v2', coachReviewed: true }],
            prescribesMedicalLoad: false,
            diagnosesFatigueOrInjury: false,
          }),
        } as Response);
      }
      if (url.endsWith('/api/repository') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ httpMayRunGpu: false, vectorBrokerRequired: false, replacesStorageModule: false }),
        } as Response);
      }
      if (url.endsWith('/api/support/bundle') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ released: false, reasonCodes: ['CONSENT_REQUIRED'] }),
        } as Response);
      }
      if (url.includes('/api/scale/10') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            matchesPerMonth: 10,
            measuredApplicationPerformance: false,
            gbEqualsGiB: false,
            decimalGb: 5.4,
          }),
        } as Response);
      }
      if (url.endsWith('/api/research/lane') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ isolated: true, autonomousProductionChanges: false, tracks: [{ id: 'possession/events', inert: true }] }),
        } as Response);
      }
      if (url.includes('/api/admission/handheld_low_angle') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ certified: false, withhold: ['physical_metrics'] }),
        } as Response);
      }
      if (url.includes('/api/deployment/hosted_collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ admitted: false, silentCloudFallback: false, requiresGNetwork: true }),
        } as Response);
      }
      if (url.endsWith('/api/vector') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, embeddingsProveTacticalWeakness: false }),
        } as Response);
      }
      if (url.endsWith('/api/broker') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, renamesCurrentQueue: false }),
        } as Response);
      }
      if (url.endsWith('/api/residency') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ euProcessingProven: false, reasonCodes: ['REQUESTED_REGION_IS_NOT_PROOF'] }),
        } as Response);
      }
      if (url.endsWith('/api/decisions') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{ id: 'capability_release', decision: 'independent_gates_not_merged_files', reversible: true }],
          }),
        } as Response);
      }
      if (url.endsWith('/api/targets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ measured: false, doesNotPromiseVideoDecodeLatency: true }),
        } as Response);
      }
      if (url.includes('/api/metrics/network-failure') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ availability: 'unknown', value: null, replacedWithGenerated: false }),
        } as Response);
      }
      if (url.endsWith('/api/milestones') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            progress: { complete: false, completedAnalystTasks: 0, usesMergedFilesAsSuccess: false },
          }),
        } as Response);
      }
      if (url.endsWith('/api/risks') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ id: 'labels_incomplete', owner: 'reviewer_owner' }] }),
        } as Response);
      }
      if (url.endsWith('/api/roster') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ task: 'player_ball', promoted: false }] }),
        } as Response);
      }
      if (url.endsWith('/api/rights') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ uncertainCommercialPermissionBlocks: true }) } as Response);
      }
      if (url.endsWith('/api/xt') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, socceractionImportDoesNotValidateExtraction: true }),
        } as Response);
      }
      if (url.includes('/api/geometry/contact') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ boxCentreIsFoot: false }) } as Response);
      }
      if (url.includes('/api/reports/held-out') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ questions: [{ text: 'how tired was player 7 in the 89th minute', unanswerable: true }] }),
        } as Response);
      }
      if (url.includes('/api/credits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ authorised: false, gpuCreditsDoNotPayForLabels: true }) } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }) } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }) } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trackevalIsGroundTruth: false, annotationServiceHealthSatisfiesLabelGate: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/storage/object')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/preemptible')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/quantities/axes')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/support/bundle')
      && init?.method === 'POST'
    ))).toBe(false);
    const storage = within(await screen.findByRole('region', { name: /stored object storage/i }));
    expect(storage.getByText(/stays local content-addressed/i)).toBeTruthy();
    expect(storage.getByText(/hosted admission stays off/i)).toBeTruthy();
    expect(storage.getByText(/mandatory DuckDB stays false/i)).toBeTruthy();
    const preemptible = within(screen.getByRole('region', { name: /stored preemptible policy/i }));
    expect(preemptible.getByText(/stays disallowed/i)).toBeTruthy();
    expect(preemptible.getByText(/missing checkpoints do not admit workers/i)).toBeTruthy();
    const axes = within(screen.getByRole('region', { name: /stored pitch axes/i }));
    expect(axes.getByText(/keep x longitudinal and y lateral/i)).toBeTruthy();
    expect(axes.getByText(/declared calibration is the origin/i)).toBeTruthy();
    expect(axes.getByText(/legacy display stays an explicit transform/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored GPU timing, experiment B2, and disk recovery without inventing completed work or hardware', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/timing/gpu') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            admitted: false,
            usesSubmissionAsCompletedWork: false,
            completedMs: null,
            reasonCodes: ['GPU_TIMING_SUBMISSION_IS_NOT_COMPLETED_WORK'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/experiments/B2') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            promoted: false,
            hardwareVerified: false,
            reasonCodes: ['HARDWARE_UNAVAILABLE'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/recovery/disk') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ acceptedPartial: false, error: 'disk_exhaustion', status: 'failed' }),
        } as Response);
      }
      if (url.endsWith('/api/storage/object') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, mandatoryDuckDb: false, role: 'local_content_addressed' }),
        } as Response);
      }
      if (url.endsWith('/api/preemptible') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ allowed: false }) } as Response);
      }
      if (url.endsWith('/api/quantities/axes') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            x: 'longitudinal',
            y: 'lateral',
            origin: 'declared_calibration',
            legacyDisplay: 'transform_explicitly',
          }),
        } as Response);
      }
      if (url.endsWith('/api/training/drills') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{ name: 'near-side recovery 2v2', coachReviewed: true }],
            prescribesMedicalLoad: false,
            diagnosesFatigueOrInjury: false,
          }),
        } as Response);
      }
      if (url.endsWith('/api/repository') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ httpMayRunGpu: false, vectorBrokerRequired: false, replacesStorageModule: false }),
        } as Response);
      }
      if (url.endsWith('/api/support/bundle') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ released: false, reasonCodes: ['CONSENT_REQUIRED'] }),
        } as Response);
      }
      if (url.includes('/api/scale/10') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            matchesPerMonth: 10,
            measuredApplicationPerformance: false,
            gbEqualsGiB: false,
            decimalGb: 5.4,
          }),
        } as Response);
      }
      if (url.endsWith('/api/research/lane') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ isolated: true, autonomousProductionChanges: false, tracks: [{ id: 'possession/events', inert: true }] }),
        } as Response);
      }
      if (url.includes('/api/admission/handheld_low_angle') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ certified: false, withhold: ['physical_metrics'] }),
        } as Response);
      }
      if (url.includes('/api/deployment/hosted_collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ admitted: false, silentCloudFallback: false, requiresGNetwork: true }),
        } as Response);
      }
      if (url.endsWith('/api/vector') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, embeddingsProveTacticalWeakness: false }),
        } as Response);
      }
      if (url.endsWith('/api/broker') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, renamesCurrentQueue: false }),
        } as Response);
      }
      if (url.endsWith('/api/residency') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ euProcessingProven: false, reasonCodes: ['REQUESTED_REGION_IS_NOT_PROOF'] }),
        } as Response);
      }
      if (url.endsWith('/api/decisions') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{ id: 'capability_release', decision: 'independent_gates_not_merged_files', reversible: true }],
          }),
        } as Response);
      }
      if (url.endsWith('/api/targets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ measured: false, doesNotPromiseVideoDecodeLatency: true }),
        } as Response);
      }
      if (url.includes('/api/metrics/network-failure') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ availability: 'unknown', value: null, replacedWithGenerated: false }),
        } as Response);
      }
      if (url.endsWith('/api/milestones') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            progress: { complete: false, completedAnalystTasks: 0, usesMergedFilesAsSuccess: false },
          }),
        } as Response);
      }
      if (url.endsWith('/api/risks') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ id: 'labels_incomplete', owner: 'reviewer_owner' }] }),
        } as Response);
      }
      if (url.endsWith('/api/roster') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ task: 'player_ball', promoted: false }] }),
        } as Response);
      }
      if (url.endsWith('/api/rights') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ uncertainCommercialPermissionBlocks: true }) } as Response);
      }
      if (url.endsWith('/api/xt') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, socceractionImportDoesNotValidateExtraction: true }),
        } as Response);
      }
      if (url.includes('/api/geometry/contact') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ boxCentreIsFoot: false }) } as Response);
      }
      if (url.includes('/api/reports/held-out') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ questions: [{ text: 'how tired was player 7 in the 89th minute', unanswerable: true }] }),
        } as Response);
      }
      if (url.includes('/api/credits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ authorised: false, gpuCreditsDoNotPayForLabels: true }) } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }) } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }) } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trackevalIsGroundTruth: false, annotationServiceHealthSatisfiesLabelGate: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/timing/gpu')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/experiments/B2')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/recovery/disk')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/experiments/B2')
      && init?.method === 'POST'
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/experiments/quality-gate'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    const timing = within(await screen.findByRole('region', { name: /stored GPU timing/i }));
    expect(timing.getByText(/stays unadmitted/i)).toBeTruthy();
    expect(timing.getByText(/submission milliseconds are not completed work/i)).toBeTruthy();
    expect(timing.getByText(/completedMs stays unknown/i)).toBeTruthy();
    const experiment = within(screen.getByRole('region', { name: /stored experiment B2/i }));
    expect(experiment.getByText(/stays unpromoted/i)).toBeTruthy();
    expect(experiment.getByText(/hardware stays unverified/i)).toBeTruthy();
    expect(experiment.getByText(/HARDWARE_UNAVAILABLE stays blocking/i)).toBeTruthy();
    const disk = within(screen.getByRole('region', { name: /stored disk recovery/i }));
    expect(disk.getByText(/refuses partial acceptance/i)).toBeTruthy();
    expect(disk.getByText(/disk_exhaustion stays blocking/i)).toBeTruthy();
    expect(disk.getByText(/partial-disk imports stay fail-closed/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored experiment B5, restore exercise, and video roster without inventing native or promotion', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/experiments/B5') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            promoted: false,
            reasonCodes: ['NATIVE_GATE_CLOSED'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/recovery/restore') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ tested: true, digest: 'restore-digest' }),
        } as Response);
      }
      if (url.endsWith('/api/roster/video') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ qwen3_5_4b: { promoted: false, role: 'compact_local_language_candidate' } }),
        } as Response);
      }
      if (url.endsWith('/api/timing/gpu') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            admitted: false,
            usesSubmissionAsCompletedWork: false,
            completedMs: null,
            reasonCodes: ['GPU_TIMING_SUBMISSION_IS_NOT_COMPLETED_WORK'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/experiments/B2') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            promoted: false,
            hardwareVerified: false,
            reasonCodes: ['HARDWARE_UNAVAILABLE'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/recovery/disk') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ acceptedPartial: false, error: 'disk_exhaustion', status: 'failed' }),
        } as Response);
      }
      if (url.endsWith('/api/storage/object') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, mandatoryDuckDb: false, role: 'local_content_addressed' }),
        } as Response);
      }
      if (url.endsWith('/api/preemptible') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ allowed: false }) } as Response);
      }
      if (url.endsWith('/api/quantities/axes') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            x: 'longitudinal',
            y: 'lateral',
            origin: 'declared_calibration',
            legacyDisplay: 'transform_explicitly',
          }),
        } as Response);
      }
      if (url.endsWith('/api/training/drills') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{ name: 'near-side recovery 2v2', coachReviewed: true }],
            prescribesMedicalLoad: false,
            diagnosesFatigueOrInjury: false,
          }),
        } as Response);
      }
      if (url.endsWith('/api/repository') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ httpMayRunGpu: false, vectorBrokerRequired: false, replacesStorageModule: false }),
        } as Response);
      }
      if (url.endsWith('/api/support/bundle') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ released: false, reasonCodes: ['CONSENT_REQUIRED'] }),
        } as Response);
      }
      if (url.includes('/api/scale/10') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            matchesPerMonth: 10,
            measuredApplicationPerformance: false,
            gbEqualsGiB: false,
            decimalGb: 5.4,
          }),
        } as Response);
      }
      if (url.endsWith('/api/research/lane') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ isolated: true, autonomousProductionChanges: false, tracks: [{ id: 'possession/events', inert: true }] }),
        } as Response);
      }
      if (url.includes('/api/admission/handheld_low_angle') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ certified: false, withhold: ['physical_metrics'] }),
        } as Response);
      }
      if (url.includes('/api/deployment/hosted_collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ admitted: false, silentCloudFallback: false, requiresGNetwork: true }),
        } as Response);
      }
      if (url.endsWith('/api/vector') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, embeddingsProveTacticalWeakness: false }),
        } as Response);
      }
      if (url.endsWith('/api/broker') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, renamesCurrentQueue: false }),
        } as Response);
      }
      if (url.endsWith('/api/residency') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ euProcessingProven: false, reasonCodes: ['REQUESTED_REGION_IS_NOT_PROOF'] }),
        } as Response);
      }
      if (url.endsWith('/api/decisions') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{ id: 'capability_release', decision: 'independent_gates_not_merged_files', reversible: true }],
          }),
        } as Response);
      }
      if (url.endsWith('/api/targets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ measured: false, doesNotPromiseVideoDecodeLatency: true }),
        } as Response);
      }
      if (url.includes('/api/metrics/network-failure') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ availability: 'unknown', value: null, replacedWithGenerated: false }),
        } as Response);
      }
      if (url.endsWith('/api/milestones') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            progress: { complete: false, completedAnalystTasks: 0, usesMergedFilesAsSuccess: false },
          }),
        } as Response);
      }
      if (url.endsWith('/api/risks') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ id: 'labels_incomplete', owner: 'reviewer_owner' }] }),
        } as Response);
      }
      if (url.endsWith('/api/roster') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ task: 'player_ball', promoted: false }] }),
        } as Response);
      }
      if (url.endsWith('/api/rights') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ uncertainCommercialPermissionBlocks: true }) } as Response);
      }
      if (url.endsWith('/api/xt') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, socceractionImportDoesNotValidateExtraction: true }),
        } as Response);
      }
      if (url.includes('/api/geometry/contact') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ boxCentreIsFoot: false }) } as Response);
      }
      if (url.includes('/api/reports/held-out') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ questions: [{ text: 'how tired was player 7 in the 89th minute', unanswerable: true }] }),
        } as Response);
      }
      if (url.includes('/api/credits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ authorised: false, gpuCreditsDoNotPayForLabels: true }) } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }) } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }) } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trackevalIsGroundTruth: false, annotationServiceHealthSatisfiesLabelGate: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/experiments/B5')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/recovery/restore')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/roster/video')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    const b5 = within(await screen.findByRole('region', { name: /stored experiment B5/i }));
    expect(b5.getByText(/stays unpromoted/i)).toBeTruthy();
    expect(b5.getByText(/NATIVE_GATE_CLOSED stays blocking/i)).toBeTruthy();
    expect(b5.getByText(/native rewrite stays unproven/i)).toBeTruthy();
    const restore = within(screen.getByRole('region', { name: /stored restore exercise/i }));
    expect(restore.getByText(/stays tested/i)).toBeTruthy();
    expect(restore.getByText(/tested restore is not current-source sealed inference/i)).toBeTruthy();
    const video = within(screen.getByRole('region', { name: /stored video roster/i }));
    expect(video.getByText(/keeps qwen3_5_4b unpromoted/i)).toBeTruthy();
    expect(video.getByText(/video models stay off the production path/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored frontier roster, promotion gate, and quality gate without inventing independent acceptance', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/roster/frontier') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ promoted: false, hardCodedModelName: false, role: 'frontier' }),
        } as Response);
      }
      if (url.endsWith('/api/roster/promotion/player_ball') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            promoted: false,
            task: 'player_ball',
            reasonCodes: ['INDEPENDENT_ACCEPTANCE_MISSING', 'LICENCE_UNREVIEWED'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/experiments/quality-gate') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            promoted: false,
            threshold: 0.8,
            reasonCodes: ['QUALITY_GATE_FAILED'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/experiments/B5') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ promoted: false, reasonCodes: ['NATIVE_GATE_CLOSED'] }),
        } as Response);
      }
      if (url.endsWith('/api/recovery/restore') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ tested: true, digest: 'restore-digest' }),
        } as Response);
      }
      if (url.endsWith('/api/roster/video') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ qwen3_5_4b: { promoted: false, role: 'compact_local_language_candidate' } }),
        } as Response);
      }
      if (url.endsWith('/api/timing/gpu') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            admitted: false,
            usesSubmissionAsCompletedWork: false,
            completedMs: null,
            reasonCodes: ['GPU_TIMING_SUBMISSION_IS_NOT_COMPLETED_WORK'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/experiments/B2') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            promoted: false,
            hardwareVerified: false,
            reasonCodes: ['HARDWARE_UNAVAILABLE'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/recovery/disk') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ acceptedPartial: false, error: 'disk_exhaustion', status: 'failed' }),
        } as Response);
      }
      if (url.endsWith('/api/storage/object') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, mandatoryDuckDb: false, role: 'local_content_addressed' }),
        } as Response);
      }
      if (url.endsWith('/api/preemptible') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ allowed: false }) } as Response);
      }
      if (url.endsWith('/api/quantities/axes') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            x: 'longitudinal',
            y: 'lateral',
            origin: 'declared_calibration',
            legacyDisplay: 'transform_explicitly',
          }),
        } as Response);
      }
      if (url.endsWith('/api/training/drills') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{ name: 'near-side recovery 2v2', coachReviewed: true }],
            prescribesMedicalLoad: false,
            diagnosesFatigueOrInjury: false,
          }),
        } as Response);
      }
      if (url.endsWith('/api/repository') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ httpMayRunGpu: false, vectorBrokerRequired: false, replacesStorageModule: false }),
        } as Response);
      }
      if (url.endsWith('/api/support/bundle') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ released: false, reasonCodes: ['CONSENT_REQUIRED'] }),
        } as Response);
      }
      if (url.includes('/api/scale/10') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            matchesPerMonth: 10,
            measuredApplicationPerformance: false,
            gbEqualsGiB: false,
            decimalGb: 5.4,
          }),
        } as Response);
      }
      if (url.endsWith('/api/research/lane') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ isolated: true, autonomousProductionChanges: false, tracks: [{ id: 'possession/events', inert: true }] }),
        } as Response);
      }
      if (url.includes('/api/admission/handheld_low_angle') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ certified: false, withhold: ['physical_metrics'] }),
        } as Response);
      }
      if (url.includes('/api/deployment/hosted_collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ admitted: false, silentCloudFallback: false, requiresGNetwork: true }),
        } as Response);
      }
      if (url.endsWith('/api/vector') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, embeddingsProveTacticalWeakness: false }),
        } as Response);
      }
      if (url.endsWith('/api/broker') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, renamesCurrentQueue: false }),
        } as Response);
      }
      if (url.endsWith('/api/residency') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ euProcessingProven: false, reasonCodes: ['REQUESTED_REGION_IS_NOT_PROOF'] }),
        } as Response);
      }
      if (url.endsWith('/api/decisions') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{ id: 'capability_release', decision: 'independent_gates_not_merged_files', reversible: true }],
          }),
        } as Response);
      }
      if (url.endsWith('/api/targets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ measured: false, doesNotPromiseVideoDecodeLatency: true }),
        } as Response);
      }
      if (url.includes('/api/metrics/network-failure') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ availability: 'unknown', value: null, replacedWithGenerated: false }),
        } as Response);
      }
      if (url.endsWith('/api/milestones') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            progress: { complete: false, completedAnalystTasks: 0, usesMergedFilesAsSuccess: false },
          }),
        } as Response);
      }
      if (url.endsWith('/api/risks') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ id: 'labels_incomplete', owner: 'reviewer_owner' }] }),
        } as Response);
      }
      if (url.endsWith('/api/roster') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ task: 'player_ball', promoted: false }] }),
        } as Response);
      }
      if (url.endsWith('/api/rights') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ uncertainCommercialPermissionBlocks: true }) } as Response);
      }
      if (url.endsWith('/api/xt') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, socceractionImportDoesNotValidateExtraction: true }),
        } as Response);
      }
      if (url.includes('/api/geometry/contact') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ boxCentreIsFoot: false }) } as Response);
      }
      if (url.includes('/api/reports/held-out') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ questions: [{ text: 'how tired was player 7 in the 89th minute', unanswerable: true }] }),
        } as Response);
      }
      if (url.includes('/api/credits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ authorised: false, gpuCreditsDoNotPayForLabels: true }) } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }) } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }) } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trackevalIsGroundTruth: false, annotationServiceHealthSatisfiesLabelGate: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/roster/frontier')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/roster/promotion/player_ball')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/experiments/quality-gate'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /request quality gate/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/experiments/quality-gate')
        && init?.method === 'POST'
        && String(init?.body) === '{}'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/experiments/quality-gate')
      && Boolean(init?.body && (String(init.body).includes('qualityPassed') || String(init.body).includes('faster')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/roster/promotion')
      && init?.method === 'POST'
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/roster/promotion')
      && Boolean(init?.body && String(init.body).includes('independentAccepted'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    const frontier = within(await screen.findByRole('region', { name: /stored frontier roster/i }));
    expect(frontier.getByText(/stays unpromoted/i)).toBeTruthy();
    expect(frontier.getByText(/hard-coded model names stay off/i)).toBeTruthy();
    expect(frontier.getByText(/frontier stays a role, not a promoted model/i)).toBeTruthy();
    const promotion = within(screen.getByRole('region', { name: /stored promotion gate/i }));
    expect(promotion.getByText(/stays closed/i)).toBeTruthy();
    expect(promotion.getByText(/INDEPENDENT_ACCEPTANCE_MISSING stays blocking/i)).toBeTruthy();
    expect(promotion.getByText(/client independentAccepted is not sent/i)).toBeTruthy();
    const gate = within(screen.getByRole('region', { name: /unforced quality gate/i }));
    expect(gate.getByText(/stays unpromoted/i)).toBeTruthy();
    expect(gate.getByText(/client faster and qualityPassed are not sent/i)).toBeTruthy();
    expect(gate.getByText(/QUALITY_GATE_FAILED stays blocking/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads posted JSON repair, assistance policy, and job budget without inventing spend or secrets', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/assistance/repair') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            admitted: false,
            attempts: 2,
            maxRepair: 1,
            reasonCodes: ['UNBOUNDED_JSON_REPAIR'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/assistance/policy') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            route: 'template',
            evidenceHash: '',
            policyVersion: '1',
            secretsExcluded: true,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/jobs') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            jobId: 'job-scope-1',
            status: 'queued',
            reused: false,
            costReserved: 0,
          }),
        } as Response);
      }
      if (url.endsWith('/api/jobs/job-scope-1/cost') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ reservedTotal: 0, actualTotal: 0, p50Reserved: 0, requestId: 'job-scope-1' }),
        } as Response);
      }
      if (url.endsWith('/api/jobs/job-scope-1/budget') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            reserve: { authorised: false, reserved: 0, estimate: 0, currency: 'USD' },
            reconcile: { reserved: 0, actual: 0, variance: 0, exceeded: false, alert: false },
            cost: { reservedTotal: 0, actualTotal: 0 },
          }),
        } as Response);
      }
      if (url.endsWith('/api/roster/frontier') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ promoted: false, hardCodedModelName: false, role: 'frontier' }),
        } as Response);
      }
      if (url.endsWith('/api/roster/promotion/player_ball') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            promoted: false,
            task: 'player_ball',
            reasonCodes: ['INDEPENDENT_ACCEPTANCE_MISSING', 'LICENCE_UNREVIEWED'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/experiments/quality-gate') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            promoted: false,
            threshold: 0.8,
            reasonCodes: ['QUALITY_GATE_FAILED'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/experiments/B5') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ promoted: false, reasonCodes: ['NATIVE_GATE_CLOSED'] }),
        } as Response);
      }
      if (url.endsWith('/api/recovery/restore') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ tested: true, digest: 'restore-digest' }),
        } as Response);
      }
      if (url.endsWith('/api/roster/video') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ qwen3_5_4b: { promoted: false, role: 'compact_local_language_candidate' } }),
        } as Response);
      }
      if (url.endsWith('/api/timing/gpu') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            admitted: false,
            usesSubmissionAsCompletedWork: false,
            completedMs: null,
            reasonCodes: ['GPU_TIMING_SUBMISSION_IS_NOT_COMPLETED_WORK'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/experiments/B2') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            promoted: false,
            hardwareVerified: false,
            reasonCodes: ['HARDWARE_UNAVAILABLE'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/recovery/disk') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ acceptedPartial: false, error: 'disk_exhaustion', status: 'failed' }),
        } as Response);
      }
      if (url.endsWith('/api/storage/object') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, mandatoryDuckDb: false, role: 'local_content_addressed' }),
        } as Response);
      }
      if (url.endsWith('/api/preemptible') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ allowed: false }) } as Response);
      }
      if (url.endsWith('/api/quantities/axes') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            x: 'longitudinal',
            y: 'lateral',
            origin: 'declared_calibration',
            legacyDisplay: 'transform_explicitly',
          }),
        } as Response);
      }
      if (url.endsWith('/api/training/drills') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{ name: 'near-side recovery 2v2', coachReviewed: true }],
            prescribesMedicalLoad: false,
            diagnosesFatigueOrInjury: false,
          }),
        } as Response);
      }
      if (url.endsWith('/api/repository') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ httpMayRunGpu: false, vectorBrokerRequired: false, replacesStorageModule: false }),
        } as Response);
      }
      if (url.endsWith('/api/support/bundle') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ released: false, reasonCodes: ['CONSENT_REQUIRED'] }),
        } as Response);
      }
      if (url.includes('/api/scale/10') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            matchesPerMonth: 10,
            measuredApplicationPerformance: false,
            gbEqualsGiB: false,
            decimalGb: 5.4,
          }),
        } as Response);
      }
      if (url.endsWith('/api/research/lane') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ isolated: true, autonomousProductionChanges: false, tracks: [{ id: 'possession/events', inert: true }] }),
        } as Response);
      }
      if (url.includes('/api/admission/handheld_low_angle') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ certified: false, withhold: ['physical_metrics'] }),
        } as Response);
      }
      if (url.includes('/api/deployment/hosted_collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ admitted: false, silentCloudFallback: false, requiresGNetwork: true }),
        } as Response);
      }
      if (url.endsWith('/api/vector') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, embeddingsProveTacticalWeakness: false }),
        } as Response);
      }
      if (url.endsWith('/api/broker') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, renamesCurrentQueue: false }),
        } as Response);
      }
      if (url.endsWith('/api/residency') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ euProcessingProven: false, reasonCodes: ['REQUESTED_REGION_IS_NOT_PROOF'] }),
        } as Response);
      }
      if (url.endsWith('/api/decisions') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{ id: 'capability_release', decision: 'independent_gates_not_merged_files', reversible: true }],
          }),
        } as Response);
      }
      if (url.endsWith('/api/targets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ measured: false, doesNotPromiseVideoDecodeLatency: true }),
        } as Response);
      }
      if (url.includes('/api/metrics/network-failure') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ availability: 'unknown', value: null, replacedWithGenerated: false }),
        } as Response);
      }
      if (url.endsWith('/api/milestones') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            progress: { complete: false, completedAnalystTasks: 0, usesMergedFilesAsSuccess: false },
          }),
        } as Response);
      }
      if (url.endsWith('/api/risks') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [{ id: 'labels_incomplete', owner: 'reviewer_owner' }] }) } as Response);
      }
      if (url.endsWith('/api/roster') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ task: 'player_ball', promoted: false }] }),
        } as Response);
      }
      if (url.endsWith('/api/rights') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ uncertainCommercialPermissionBlocks: true }) } as Response);
      }
      if (url.endsWith('/api/xt') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, socceractionImportDoesNotValidateExtraction: true }),
        } as Response);
      }
      if (url.includes('/api/geometry/contact') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ boxCentreIsFoot: false }) } as Response);
      }
      if (url.includes('/api/reports/held-out') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ questions: [{ text: 'how tired was player 7 in the 89th minute', unanswerable: true }] }),
        } as Response);
      }
      if (url.includes('/api/credits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ authorised: false, gpuCreditsDoNotPayForLabels: true }) } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }) } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }) } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trackevalIsGroundTruth: false, annotationServiceHealthSatisfiesLabelGate: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => expect(screen.getByRole('button', { name: /request json repair/i })).toBeTruthy());
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/assistance/repair'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/assistance/policy'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/jobs/job-scope-1/budget'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /request json repair/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/assistance/repair')
        && init?.method === 'POST'
        && String(init?.body) === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request assistance policy/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/assistance/policy')
        && init?.method === 'POST'
        && String(init?.body) === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request durable job/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/jobs/job-scope-1/budget')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/assistance/repair')
      && Boolean(init?.body && (String(init.body).includes('sk-live-secret') || String(init.body).includes('attempts')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/assistance/policy')
      && Boolean(init?.body && String(init.body).includes('sk-live-secret'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/support/bundle')
      && init?.method === 'POST'
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/roster/promotion')
      && init?.method === 'POST'
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/experiments/B2')
      && init?.method === 'POST'
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    const repair = within(await screen.findByRole('region', { name: /unforced json repair/i }));
    expect(repair.getByText(/stays refused/i)).toBeTruthy();
    expect(repair.getByText(/client secret and attempts are not sent/i)).toBeTruthy();
    expect(repair.getByText(/UNBOUNDED_JSON_REPAIR stays blocking/i)).toBeTruthy();
    const policy = within(screen.getByRole('region', { name: /unforced assistance policy/i }));
    expect(policy.getByText(/excludes secrets/i)).toBeTruthy();
    expect(policy.getByText(/client secret is not sent/i)).toBeTruthy();
    expect(policy.getByText(/secretsExcluded stays true/i)).toBeTruthy();
    const posted = within(screen.getByRole('region', { name: /unforced job write/i }));
    expect(posted.getByText(/job budget reserve stays unauthorised/i)).toBeTruthy();
    expect(posted.getByText(/authorised spend is not invented/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored stage timing, GPU probe, and job charges without inventing video capability or erased spend', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/timing/stages') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ overlappedStagesAreAdditive: false, wallTime: 3.0 }),
        } as Response);
      }
      if ((url === '/api/gpu' || url.endsWith('/api/gpu')) && !url.includes('/timing/') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            canPromoteDefault: false,
            videoEngine: { videoEngineCapability: false, reasonCodes: ['CUDA_VISIBILITY_IS_NOT_VIDEO_CAPABILITY'] },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/jobs') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            jobId: 'job-scope-1',
            status: 'queued',
            reused: false,
            costReserved: 0,
          }),
        } as Response);
      }
      if (url.endsWith('/api/jobs/job-scope-1/cost') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ reservedTotal: 0, actualTotal: 0, p50Reserved: 0, requestId: 'job-scope-1' }),
        } as Response);
      }
      if (url.endsWith('/api/jobs/job-scope-1/budget') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            reserve: { authorised: false, reserved: 0, estimate: 0, currency: 'USD' },
            reconcile: { reserved: 0, actual: 0, variance: 0, exceeded: false, alert: false },
            cost: { reservedTotal: 0, actualTotal: 0 },
          }),
        } as Response);
      }
      if (url.endsWith('/api/jobs/job-scope-1/charges') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            cancelled: false,
            incurred: 0,
            chargesErased: false,
            reasonCodes: [],
          }),
        } as Response);
      }
      if (url.endsWith('/api/assistance/repair') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ admitted: false, reasonCodes: ['UNBOUNDED_JSON_REPAIR'] }),
        } as Response);
      }
      if (url.endsWith('/api/assistance/policy') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ secretsExcluded: true, route: 'template' }),
        } as Response);
      }
      if (url.endsWith('/api/roster/frontier') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ promoted: false, hardCodedModelName: false, role: 'frontier' }),
        } as Response);
      }
      if (url.endsWith('/api/roster/promotion/player_ball') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            promoted: false,
            task: 'player_ball',
            reasonCodes: ['INDEPENDENT_ACCEPTANCE_MISSING', 'LICENCE_UNREVIEWED'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/experiments/B5') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ promoted: false, reasonCodes: ['NATIVE_GATE_CLOSED'] }),
        } as Response);
      }
      if (url.endsWith('/api/recovery/restore') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ tested: true, digest: 'restore-digest' }),
        } as Response);
      }
      if (url.endsWith('/api/roster/video') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ qwen3_5_4b: { promoted: false, role: 'compact_local_language_candidate' } }),
        } as Response);
      }
      if (url.endsWith('/api/timing/gpu') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            admitted: false,
            usesSubmissionAsCompletedWork: false,
            completedMs: null,
            reasonCodes: ['GPU_TIMING_SUBMISSION_IS_NOT_COMPLETED_WORK'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/experiments/B2') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            promoted: false,
            hardwareVerified: false,
            reasonCodes: ['HARDWARE_UNAVAILABLE'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/recovery/disk') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ acceptedPartial: false, error: 'disk_exhaustion', status: 'failed' }),
        } as Response);
      }
      if (url.endsWith('/api/storage/object') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, mandatoryDuckDb: false, role: 'local_content_addressed' }),
        } as Response);
      }
      if (url.endsWith('/api/preemptible') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ allowed: false }) } as Response);
      }
      if (url.endsWith('/api/quantities/axes') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            x: 'longitudinal',
            y: 'lateral',
            origin: 'declared_calibration',
            legacyDisplay: 'transform_explicitly',
          }),
        } as Response);
      }
      if (url.endsWith('/api/training/drills') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{ name: 'near-side recovery 2v2', coachReviewed: true }],
            prescribesMedicalLoad: false,
            diagnosesFatigueOrInjury: false,
          }),
        } as Response);
      }
      if (url.endsWith('/api/repository') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ httpMayRunGpu: false, vectorBrokerRequired: false, replacesStorageModule: false }),
        } as Response);
      }
      if (url.endsWith('/api/support/bundle') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ released: false, reasonCodes: ['CONSENT_REQUIRED'] }),
        } as Response);
      }
      if (url.includes('/api/scale/10') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            matchesPerMonth: 10,
            measuredApplicationPerformance: false,
            gbEqualsGiB: false,
            decimalGb: 5.4,
          }),
        } as Response);
      }
      if (url.endsWith('/api/research/lane') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ isolated: true, autonomousProductionChanges: false, tracks: [{ id: 'possession/events', inert: true }] }),
        } as Response);
      }
      if (url.includes('/api/admission/handheld_low_angle') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ certified: false, withhold: ['physical_metrics'] }),
        } as Response);
      }
      if (url.includes('/api/deployment/hosted_collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ admitted: false, silentCloudFallback: false, requiresGNetwork: true }),
        } as Response);
      }
      if (url.endsWith('/api/vector') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, embeddingsProveTacticalWeakness: false }),
        } as Response);
      }
      if (url.endsWith('/api/broker') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, admitted: false, renamesCurrentQueue: false }),
        } as Response);
      }
      if (url.endsWith('/api/residency') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ euProcessingProven: false, reasonCodes: ['REQUESTED_REGION_IS_NOT_PROOF'] }),
        } as Response);
      }
      if (url.endsWith('/api/decisions') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            items: [{ id: 'capability_release', decision: 'independent_gates_not_merged_files', reversible: true }],
          }),
        } as Response);
      }
      if (url.endsWith('/api/targets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ measured: false, doesNotPromiseVideoDecodeLatency: true }),
        } as Response);
      }
      if (url.includes('/api/metrics/network-failure') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ availability: 'unknown', value: null, replacedWithGenerated: false }),
        } as Response);
      }
      if (url.endsWith('/api/milestones') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            progress: { complete: false, completedAnalystTasks: 0, usesMergedFilesAsSuccess: false },
          }),
        } as Response);
      }
      if (url.endsWith('/api/risks') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [{ id: 'labels_incomplete', owner: 'reviewer_owner' }] }) } as Response);
      }
      if (url.endsWith('/api/roster') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [{ task: 'player_ball', promoted: false }] }),
        } as Response);
      }
      if (url.endsWith('/api/rights') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ uncertainCommercialPermissionBlocks: true }) } as Response);
      }
      if (url.endsWith('/api/xt') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ enabled: false, socceractionImportDoesNotValidateExtraction: true }),
        } as Response);
      }
      if (url.includes('/api/geometry/contact') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ boxCentreIsFoot: false }) } as Response);
      }
      if (url.includes('/api/reports/held-out') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ questions: [{ text: 'how tired was player 7 in the 89th minute', unanswerable: true }] }),
        } as Response);
      }
      if (url.includes('/api/credits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ authorised: false, gpuCreditsDoNotPayForLabels: true }) } as Response);
      }
      if (url.includes('/api/collaboration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ hosted: { admitted: false, silentlyReplaced: false } }) } as Response);
      }
      if (url.includes('/api/media/stride') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ addsVidStrideAlone: false, targetFpsEqualsInferenceFps: false }) } as Response);
      }
      if (url.includes('/api/evaluation/hota') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            scored: false,
            hota: null,
            idf1: null,
            reasonCodes: ['INCOMPATIBLE_HOTA_LABEL_SPACE', 'NATIVE_PREDICTIONS_REQUIRED'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/measures') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trackevalIsGroundTruth: false, annotationServiceHealthSatisfiesLabelGate: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/prerequisites')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, completeTasks: 0, lockedLabelsPresent: false, nativePredictionsPresent: false }),
        } as Response);
      }
      if (url.includes('/api/evaluation/protocol') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: false,
            completeTasks: 0,
            protocolVersion: 'football_analysis_pilot_labels_v3',
            reasonCodes: ['LABELS_INCOMPLETE'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/timing/stages')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      (String(url) === '/api/gpu' || String(url).endsWith('/api/gpu'))
      && !String(url).includes('/timing/')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/jobs/job-scope-1/charges'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /request durable job/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/jobs/job-scope-1/charges')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    const stages = within(await screen.findByRole('region', { name: /stored stage timing/i }));
    expect(stages.getByText(/overlapped stages non-additive/i)).toBeTruthy();
    expect(stages.getByText(/wall time is not the sum of overlapped stages/i)).toBeTruthy();
    const gpu = within(screen.getByRole('region', { name: /stored gpu probe/i }));
    expect(gpu.getByText(/cannot promote default/i)).toBeTruthy();
    expect(gpu.getByText(/CUDA visibility is not video capability/i)).toBeTruthy();
    const posted = within(screen.getByRole('region', { name: /unforced job write/i }));
    expect(posted.getByText(/job charges stay unerased/i)).toBeTruthy();
    expect(posted.getByText(/cancellation does not erase incurred charges/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored job view and rates after a requested durable job and cancels without inventing completed work', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/jobs') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            jobId: 'job-scope-1',
            status: 'queued',
            reused: false,
            costReserved: 0,
          }),
        } as Response);
      }
      if (url.endsWith('/api/jobs/job-scope-1/cost') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ reservedTotal: 0, actualTotal: 0, p50Reserved: 0, requestId: 'job-scope-1' }),
        } as Response);
      }
      if (url.endsWith('/api/jobs/job-scope-1/budget') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            reserve: { authorised: false, reserved: 0, estimate: 0, currency: 'USD' },
            reconcile: { reserved: 0, actual: 0, variance: 0, exceeded: false, alert: false },
            cost: { reservedTotal: 0, actualTotal: 0 },
          }),
        } as Response);
      }
      if (url.endsWith('/api/jobs/job-scope-1/charges') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            cancelled: false,
            incurred: 0,
            chargesErased: false,
            reasonCodes: [],
          }),
        } as Response);
      }
      if ((url === '/api/jobs/job-scope-1' || url.endsWith('/api/jobs/job-scope-1')) && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            status: 'queued',
            durablePhase: null,
            cancelRequested: false,
            costReserved: 0,
            costActual: null,
            cleanupResult: 'unknown',
          }),
        } as Response);
      }
      if (url.endsWith('/api/jobs/job-scope-1/rates') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            exportFpsEqualsInferenceFps: false,
            decodeFpsEqualsExportFps: false,
            notes: ['FOUR_RATES_UNRECORDED', 'EXPORT_FPS_IS_NOT_INFERENCE_FPS'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/jobs/job-scope-1/cancel') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            status: 'queued',
            cancelRequested: true,
            durablePhase: null,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/jobs/job-scope-1'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/matches/match-a/jobs') && init?.method === 'POST'
    ))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /request durable job/i }));
    const posted = within(await screen.findByRole('region', { name: /unforced job write/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        (String(url) === '/api/jobs/job-scope-1' || String(url).endsWith('/api/jobs/job-scope-1'))
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/jobs/job-scope-1/rates')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/jobs/job-scope-1/cancel') && init?.method === 'POST'
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/rates/four'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(screen.queryByText(/export fps is not inference fps/i)).toBeNull();
    expect(posted.getByText(/keeps cancelRequested false/i)).toBeTruthy();
    expect(posted.getByText(/a queued durable job is not completed work/i)).toBeTruthy();
    expect(posted.getByText(/keep exportFpsEqualsInferenceFps false/i)).toBeTruthy();
    expect(posted.getByText(/job sampling rates are not leftover four-rate POST/i)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /cancel durable job/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/jobs/job-scope-1/cancel')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    expect(posted.getByText(/keeps cancelRequested true/i)).toBeTruthy();
    expect(posted.getByText(/client completeMatch is not sent/i)).toBeTruthy();
    expect(posted.getByText(/a cancel flag is not completed work/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored challenger adapters and posts job timeout and lost-connection without inventing admission or completed work', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/challengers') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            kloppy: { enabled: false, replacesInternalProvenance: false, default: false },
            roboflow: { enabled: false, name: 'roboflow_trackers' },
            mcbyte: { enabled: false, default: false, name: 'mcbyte_plus_plus' },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/jobs') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            jobId: 'job-scope-1',
            status: 'queued',
            reused: false,
            costReserved: 0,
          }),
        } as Response);
      }
      if (url.endsWith('/api/jobs/job-scope-1/cost') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ reservedTotal: 0, actualTotal: 0, p50Reserved: 0, requestId: 'job-scope-1' }),
        } as Response);
      }
      if (url.endsWith('/api/jobs/job-scope-1/budget') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            reserve: { authorised: false, reserved: 0, estimate: 0, currency: 'USD' },
            reconcile: { reserved: 0, actual: 0, variance: 0, exceeded: false, alert: false },
            cost: { reservedTotal: 0, actualTotal: 0 },
          }),
        } as Response);
      }
      if (url.endsWith('/api/jobs/job-scope-1/charges') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ cancelled: false, incurred: 0, chargesErased: false, reasonCodes: [] }),
        } as Response);
      }
      if ((url === '/api/jobs/job-scope-1' || url.endsWith('/api/jobs/job-scope-1')) && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ status: 'queued', durablePhase: null, cancelRequested: false }),
        } as Response);
      }
      if (url.endsWith('/api/jobs/job-scope-1/rates') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ exportFpsEqualsInferenceFps: false, decodeFpsEqualsExportFps: false, notes: [] }),
        } as Response);
      }
      if (url.endsWith('/api/jobs/job-scope-1/timeout') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            status: 'queued',
            durablePhase: 'outcome_unknown',
            cleanupResult: 'unknown',
            cancelRequested: false,
          }),
        } as Response);
      }
      if (url.endsWith('/api/jobs/job-scope-1/lost-connection') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            status: 'queued',
            durablePhase: 'outcome_unknown',
            cleanupResult: 'unknown',
            cancelRequested: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/challengers')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/challengers') && init?.method === 'POST'
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(screen.queryByText(/kloppy, roboflow, and mcbyte stay unadmitted challengers/i)).toBeNull();
    const challengers = within(await screen.findByRole('region', { name: /stored challenger adapters/i }));
    expect(challengers.getByText(/keep kloppy.enabled false/i)).toBeTruthy();
    expect(challengers.getByText(/client kloppy true is not sent/i)).toBeTruthy();
    expect(challengers.getByText(/roboflow and MCBYTE stay unadmitted/i)).toBeTruthy();
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/jobs/job-scope-1/timeout') && init?.method === 'POST'
    ))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /request durable job/i }));
    const posted = within(screen.getByRole('region', { name: /unforced job write/i }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /timeout durable job/i })).toBeTruthy();
    });
    fireEvent.click(screen.getByRole('button', { name: /timeout durable job/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/jobs/job-scope-1/timeout')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    expect(posted.getByText(/keeps durablePhase outcome_unknown/i)).toBeTruthy();
    expect(posted.getByText(/timeout is not cancelled/i)).toBeTruthy();
    expect(posted.getByText(/cleanupResult stays unknown/i)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /mark lost connection/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/jobs/job-scope-1/lost-connection')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    expect(posted.getByText(/posted lost connection keeps durablePhase outcome_unknown/i)).toBeTruthy();
    expect(posted.getByText(/a dropped connection is not completed work/i)).toBeTruthy();
    expect(posted.getByText(/status is not cancelled/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored feature flags, capability roster, and decode challengers without leftover POST admission or published defaults', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if ((url === '/api/flags' || url.endsWith('/api/flags')) && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            experimental_shot_quality: false,
            gpu_default: false,
            native_code: false,
            experimental_ui: false,
            embeddings_search: false,
          }),
        } as Response);
      }
      if (url.endsWith('/api/capabilities') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            capabilities: [
              { id: 'manual_review', status: 'usable' },
              { id: 'player_attribution', status: 'unproven' },
              { id: 'physical_metrics', status: 'unavailable' },
            ],
          }),
        } as Response);
      }
      if (url.endsWith('/api/decode/challengers') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            pyav: { name: 'pyav', default: false, enabled: false, role: 'challenger' },
            torchcodec: { name: 'torchcodec', default: false, enabled: false, role: 'challenger' },
            ffmpeg: { name: 'ffmpeg', default: false, enabled: false, role: 'challenger' },
            selected: 'opencv',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        (String(url) === '/api/flags' || String(url).endsWith('/api/flags'))
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/capabilities')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/decode/challengers')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/decode/challengers') && init?.method === 'POST'
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/flags/gpu_default/enabled') && init?.method === 'POST'
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(screen.queryByText(/experimental shot quality: shadowed/i)).toBeNull();
    expect(screen.queryByText(/gpu default flag stays off/i)).toBeNull();
    expect(screen.queryByText(/production decode stays on the fixture FrameSource/i)).toBeNull();
    expect(screen.queryByText(/pyav and torchcodec stay challengers/i)).toBeNull();
    expect(screen.queryByText(/kloppy, roboflow, and mcbyte stay unadmitted challengers/i)).toBeNull();
    const flags = within(await screen.findByRole('region', { name: /stored feature flags/i }));
    expect(flags.getByText(/keep gpu_default false/i)).toBeTruthy();
    expect(flags.getByText(/native_code stays false/i)).toBeTruthy();
    expect(flags.getByText(/experimental_shot_quality is not a published default/i)).toBeTruthy();
    const capabilities = within(await screen.findByRole('region', { name: /stored capability roster/i }));
    expect(capabilities.getByText(/keeps player_attribution unproven/i)).toBeTruthy();
    expect(capabilities.getByText(/physical_metrics stay unavailable/i)).toBeTruthy();
    expect(capabilities.getByText(/listing a capability is not independent accuracy/i)).toBeTruthy();
    const decodeChallengers = within(await screen.findByRole('region', { name: /stored decode challengers/i }));
    expect(decodeChallengers.getByText(/keep pyav.default false/i)).toBeTruthy();
    expect(decodeChallengers.getByText(/torchcodec stays a challenger/i)).toBeTruthy();
    expect(decodeChallengers.getByText(/production selected decode is not PyAV/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored decode frames, GPU default enabled flag, and local-only deployment without leftover POST cuda frames or GPU promotion', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/decode/frames') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            backend: 'fixture',
            defaultBackend: 'opencv',
            pyavDefault: false,
            torchcodecDefault: false,
            device: 'cpu',
            gpuPromoted: false,
            indexes: [0, 1],
            firstIndex: 0,
          }),
        } as Response);
      }
      if (url.endsWith('/api/flags/gpu_default/enabled') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ name: 'gpu_default', enabled: false }),
        } as Response);
      }
      if (url.endsWith('/api/deployment/local_only') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            admitted: true,
            silentCloudFallback: false,
            requiresGNetwork: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/decode/frames')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/decode/frames') && init?.method === 'POST'
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/flags/gpu_default/enabled')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/flags/gpu_default/enabled') && init?.method === 'POST'
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/deployment/local_only')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(screen.queryByText(/gpu default flag stays off/i)).toBeNull();
    expect(screen.queryByText(/production decode stays on the fixture FrameSource/i)).toBeNull();
    expect(screen.queryByText(/pyav and torchcodec stay challengers/i)).toBeNull();
    expect(screen.queryByText(/deployment does not commit always-on GPU/i)).toBeNull();
    const decodeFrames = within(await screen.findByRole('region', { name: /stored decode frames/i }));
    expect(decodeFrames.getByText(/keep backend fixture/i)).toBeTruthy();
    expect(decodeFrames.getByText(/gpuPromoted stays false/i)).toBeTruthy();
    expect(decodeFrames.getByText(/client pyav cuda frames are not sent/i)).toBeTruthy();
    const gpuFlag = within(await screen.findByRole('region', { name: /stored GPU default enabled flag/i }));
    expect(gpuFlag.getByText(/keeps enabled false/i)).toBeTruthy();
    expect(gpuFlag.getByText(/client enabled true is not sent/i)).toBeTruthy();
    expect(gpuFlag.getByText(/a GET flag is not GPU promotion/i)).toBeTruthy();
    const localOnly = within(await screen.findByRole('region', { name: /stored local-only deployment/i }));
    expect(localOnly.getByText(/keeps admitted true/i)).toBeTruthy();
    expect(localOnly.getByText(/silentCloudFallback stays false/i)).toBeTruthy();
    expect(localOnly.getByText(/local admission is not G-NETWORK/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts worker environment, perception score, and interrupted upload without leftover host secrets or accepted true', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/worker/environment') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ REQUEST_ID: 'production', NAMESPACE: 'production' }),
        } as Response);
      }
      if (url.endsWith('/api/perception/score') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ labelsIndependent: false, notes: ['LABELS_INCOMPLETE'] }),
        } as Response);
      }
      if (url.endsWith('/api/upload/interrupt') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, quarantined: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => expect(screen.getByRole('button', { name: /request worker environment/i })).toBeTruthy());
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/worker/environment'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/perception/score'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/upload/interrupt'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /request worker environment/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/worker/environment')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request perception score/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/perception/score')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request interrupted upload/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/upload/interrupt')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/worker/environment')
      && Boolean(init?.body && (String(init.body).includes('hostSecret') || String(init.body).includes('must-not-leak')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/perception/score')
      && Boolean(init?.body && String(init.body).includes('labelsIndependent'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/upload/interrupt')
      && Boolean(init?.body && String(init.body).includes('accepted'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(screen.queryByText(/host credentials stay out of the worker environment/i)).toBeNull();
    expect(screen.queryByText(/independent labels remain incomplete for perception scoring/i)).toBeNull();
    expect(screen.queryByText(/interrupted uploads are quarantined, not accepted/i)).toBeNull();
    const worker = within(screen.getByRole('region', { name: /unforced worker environment/i }));
    expect(worker.getByText(/excludes host secrets/i)).toBeTruthy();
    expect(worker.getByText(/client hostSecret is not sent/i)).toBeTruthy();
    expect(worker.getByText(/NAMESPACE stays production/i)).toBeTruthy();
    const perception = within(screen.getByRole('region', { name: /unforced perception score/i }));
    expect(perception.getByText(/keeps labelsIndependent false/i)).toBeTruthy();
    expect(perception.getByText(/client labelsIndependent true is not sent/i)).toBeTruthy();
    expect(perception.getByText(/LABELS_INCOMPLETE stays blocking/i)).toBeTruthy();
    const interrupted = within(screen.getByRole('region', { name: /unforced interrupted upload/i }));
    expect(interrupted.getByText(/keeps accepted false/i)).toBeTruthy();
    expect(interrupted.getByText(/client accepted true is not sent/i)).toBeTruthy();
    expect(interrupted.getByText(/quarantined stays true/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts pseudo-label, event score, and deployment choice without leftover approved true, independent labels, or always-on GPU', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/training/pseudo') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ approved: false, independentGroundTruth: false }),
        } as Response);
      }
      if (url.endsWith('/api/events/score') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ labelsIndependent: false, toleranceSeconds: 0.5 }),
        } as Response);
      }
      if (url.endsWith('/api/costs/deployment') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ selected: 'local', alwaysOnGpuCommitted: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => expect(screen.getByRole('button', { name: /request pseudo-label/i })).toBeTruthy());
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/training/pseudo'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/events/score'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/costs/deployment'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /request pseudo-label/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/training/pseudo')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request event score/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/events/score')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request deployment choice/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/costs/deployment')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/training/pseudo')
      && Boolean(init?.body && (String(init.body).includes('approved') || String(init.body).includes('player')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/events/score')
      && Boolean(init?.body && String(init.body).includes('labelsIndependent'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/costs/deployment')
      && Boolean(init?.body && String(init.body).includes('alwaysOnGpuCommitted'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(screen.queryByText(/pseudo-labels are not independent ground truth/i)).toBeNull();
    expect(screen.queryByText(/event scoring does not treat labels as independent/i)).toBeNull();
    expect(screen.queryByText(/deployment does not commit always-on GPU/i)).toBeNull();
    const pseudo = within(screen.getByRole('region', { name: /unforced pseudo-label/i }));
    expect(pseudo.getByText(/keeps approved false/i)).toBeTruthy();
    expect(pseudo.getByText(/client approved true is not sent/i)).toBeTruthy();
    expect(pseudo.getByText(/independentGroundTruth stays false/i)).toBeTruthy();
    const eventScore = within(screen.getByRole('region', { name: /unforced event score/i }));
    expect(eventScore.getByText(/keeps labelsIndependent false/i)).toBeTruthy();
    expect(eventScore.getByText(/client labelsIndependent true is not sent/i)).toBeTruthy();
    expect(eventScore.getByText(/event AP stays unproven/i)).toBeTruthy();
    const deployment = within(screen.getByRole('region', { name: /unforced deployment choice/i }));
    expect(deployment.getByText(/keeps alwaysOnGpuCommitted false/i)).toBeTruthy();
    expect(deployment.getByText(/client alwaysOnGpuCommitted true is not sent/i)).toBeTruthy();
    expect(deployment.getByText(/local hardware does not commit GPU/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts training promote, training ledger, and cache recompute without leftover independentAccepted, independentGroundTruth, or reuse', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/training/promote') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            promoted: false,
            rollbackArtifact: true,
            reasonCodes: ['INDEPENDENT_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/training/ledger') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            entries: [{ run: 'exp-1', config: 'baseline' }],
            promoted: false,
            independentGroundTruth: false,
          }),
        } as Response);
      }
      if (url.endsWith('/api/cache/recompute') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            reuse: false,
            rebuild: ['observations'],
            reason: 'cache_identity_changed',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => expect(screen.getByRole('button', { name: /request training promote/i })).toBeTruthy());
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/training/promote'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/training/ledger'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/cache/recompute'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /request training promote/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/training/promote')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request training ledger/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/training/ledger')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request cache recompute/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/cache/recompute')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/training/promote')
      && Boolean(init?.body && String(init.body).includes('independentAccepted'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/training/ledger')
      && Boolean(init?.body && (String(init.body).includes('independentGroundTruth') || String(init.body).includes('promoted')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/cache/recompute')
      && Boolean(init?.body && String(init.body).includes('reuse'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/training/admit'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/cache/tenancy'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(screen.queryByText(/locked evaluation labels cannot enter training/i)).toBeNull();
    expect(screen.queryByText(/pseudo-labels are not independent ground truth/i)).toBeNull();
    const promote = within(screen.getByRole('region', { name: /unforced training promote/i }));
    expect(promote.getByText(/keeps promoted false/i)).toBeTruthy();
    expect(promote.getByText(/client independentAccepted true is not sent/i)).toBeTruthy();
    expect(promote.getByText(/training candidate stays unpromoted/i)).toBeTruthy();
    const ledger = within(screen.getByRole('region', { name: /unforced training ledger/i }));
    expect(ledger.getByText(/keeps promoted false/i)).toBeTruthy();
    expect(ledger.getByText(/client independentGroundTruth true is not sent/i)).toBeTruthy();
    expect(ledger.getByText(/ledger rows are not independent ground truth/i)).toBeTruthy();
    const recompute = within(screen.getByRole('region', { name: /unforced cache recompute/i }));
    expect(recompute.getByText(/keeps reuse false/i)).toBeTruthy();
    expect(recompute.getByText(/client reuse true is not sent/i)).toBeTruthy();
    expect(recompute.getByText(/cache_identity_changed rebuilds observations/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts cleanup complete, training cycle, and experiment pause without leftover complete true, measurableFailure, or remaining 0', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/cleanup/complete') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ complete: false, cleanupResult: 'failed' }),
        } as Response);
      }
      if (url.endsWith('/api/training/cycle') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            stage: 'diagnose',
            proceed: false,
            reason: 'no_specific_measurable_failure',
          }),
        } as Response);
      }
      if (url.endsWith('/api/pause') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ paused: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => expect(screen.getByRole('button', { name: /request cleanup complete/i })).toBeTruthy());
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/cleanup/complete'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/training/cycle'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/pause'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /request cleanup complete/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/cleanup/complete')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request training cycle/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/training/cycle')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request experiment pause/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/pause')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/cleanup/complete')
      && Boolean(init?.body && (String(init.body).includes('complete') || String(init.body).includes('cleanupResult')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/training/cycle')
      && Boolean(init?.body && (String(init.body).includes('measurableFailure') || String(init.body).includes('stage')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/pause')
      && Boolean(init?.body && (String(init.body).includes('remaining') || String(init.body).includes('terminationAndRecovery')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/training/admit'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/quota'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/cache/tenancy'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(screen.queryByText(/locked evaluation labels cannot enter training/i)).toBeNull();
    expect(screen.queryByText(/cleanupResult stays unknown/i)).toBeNull();
    const cleanupComplete = within(screen.getByRole('region', { name: /unforced cleanup complete/i }));
    expect(cleanupComplete.getByText(/keeps complete false/i)).toBeTruthy();
    expect(cleanupComplete.getByText(/client complete true is not sent/i)).toBeTruthy();
    expect(cleanupComplete.getByText(/failed cleanup stays incomplete/i)).toBeTruthy();
    const cycle = within(screen.getByRole('region', { name: /unforced training cycle/i }));
    expect(cycle.getByText(/keeps proceed false/i)).toBeTruthy();
    expect(cycle.getByText(/client measurableFailure true is not sent/i)).toBeTruthy();
    expect(cycle.getByText(/diagnose stays no_specific_measurable_failure/i)).toBeTruthy();
    const pause = within(screen.getByRole('region', { name: /unforced experiment pause/i }));
    expect(pause.getByText(/keeps paused false/i)).toBeTruthy();
    expect(pause.getByText(/client remaining 0 is not sent/i)).toBeTruthy();
    expect(pause.getByText(/remaining still exceeds termination/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored finish-line, acceptance-report, and operator-handoff without converting historical reports into current-source labels', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/video-to-analysis/finish-line') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            schemaVersion: 'video_to_analysis_finish_line_product_view_model_v1',
            accepted: true,
            completeTasks: 18,
          }),
        } as Response);
      }
      if (url.endsWith('/api/video-to-analysis/acceptance-report') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            schemaVersion: 'video_to_analysis_acceptance_report_view_model_v1',
            accepted: true,
            analystCompletedReviewedMatch: true,
          }),
        } as Response);
      }
      if (url.endsWith('/api/video-to-analysis/operator-handoff') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            schemaVersion: 'video_to_analysis_operator_handoff_view_model_v1',
            ready: true,
            currentSourceSealedInference: true,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/video-to-analysis/finish-line')
        && !init
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/video-to-analysis/acceptance-report')
      && !init
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/video-to-analysis/operator-handoff')
      && !init
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url]) => String(url) === '/video-to-analysis/finish-line')).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url) === '/video-to-analysis/acceptance-report')).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url) === '/video-to-analysis/operator-handoff')).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/quota'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/training/admit'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/receipts/promotion'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(screen.queryByText(/reservedTotal is not current-source sealed inference/i)).toBeNull();
    expect(screen.queryByText(/tested restore is not current-source sealed inference/i)).toBeNull();
    const finishLine = within(await screen.findByRole('region', { name: /stored finish-line report/i }));
    expect(finishLine.getByText(/historical finish-line is not current-source sealed inference/i)).toBeTruthy();
    expect(finishLine.getByText(/independent labels stay 0\/18/i)).toBeTruthy();
    expect(finishLine.queryByText(/completeTasks stays 0/i)).toBeNull();
    const acceptance = within(await screen.findByRole('region', { name: /stored acceptance report/i }));
    expect(acceptance.getByText(/historical acceptance-report is not analyst-accepted current-source/i)).toBeTruthy();
    expect(acceptance.getByText(/independent locked labels remain 0\/18/i)).toBeTruthy();
    const handoff = within(await screen.findByRole('region', { name: /stored operator handoff/i }));
    expect(handoff.getByText(/historical operator-handoff is not current-source sealed inference/i)).toBeTruthy();
    expect(handoff.getByText(/current-source labels stay 0 of 18/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored release-readout, post-release-monitoring, and detector-evaluation-report without converting historical reports into current-source labels', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/video-to-analysis/release-readout') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            schemaVersion: 'video_to_analysis_release_readout_view_model_v1',
            released: true,
            completeTasks: 18,
          }),
        } as Response);
      }
      if (url.endsWith('/api/video-to-analysis/post-release-monitoring') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            schemaVersion: 'video_to_analysis_post_release_monitoring_view_model_v1',
            healthy: true,
            measured: true,
          }),
        } as Response);
      }
      if (url.endsWith('/api/video-to-analysis/detector-evaluation-report') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            schemaVersion: 'video_to_analysis_detector_evaluation_report_view_model_v1',
            labelsIndependent: true,
            qualityPassed: true,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/video-to-analysis/release-readout')
        && !init
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/video-to-analysis/post-release-monitoring')
      && !init
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/video-to-analysis/detector-evaluation-report')
      && !init
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url]) => String(url) === '/video-to-analysis/release-readout')).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url) === '/video-to-analysis/post-release-monitoring')).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url) === '/video-to-analysis/detector-evaluation-report')).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/quota'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/training/admit'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/receipts/promotion'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(screen.queryByText(/historical finish-line is not current-source sealed inference/i)).toBeNull();
    expect(screen.queryByText(/reservedTotal is not current-source sealed inference/i)).toBeNull();
    const readout = within(await screen.findByRole('region', { name: /stored release readout/i }));
    expect(readout.getByText(/historical release-readout is not current-source sealed inference/i)).toBeTruthy();
    expect(readout.getByText(/independent labels stay unaccepted/i)).toBeTruthy();
    const monitoring = within(await screen.findByRole('region', { name: /stored post-release monitoring/i }));
    expect(monitoring.getByText(/historical post-release-monitoring is not current-source sealed inference/i)).toBeTruthy();
    expect(monitoring.getByText(/independent labels stay unmeasured/i)).toBeTruthy();
    const detectorEval = within(await screen.findByRole('region', { name: /stored detector-evaluation report/i }));
    expect(detectorEval.getByText(/historical detector-evaluation-report is not independent detector proof/i)).toBeTruthy();
    expect(detectorEval.getByText(/detector scores stay unproven/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored promotion-review, promoted-runtime-monitoring, and operator-dashboard without converting historical reports into current-source labels', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/video-to-analysis/promotion-review') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            schemaVersion: 'video_to_analysis_promotion_review_report_view_model_v1',
            promoted: true,
            independentAccepted: true,
          }),
        } as Response);
      }
      if (url.endsWith('/api/video-to-analysis/promoted-runtime-monitoring') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            schemaVersion: 'video_to_analysis_promoted_runtime_monitoring_view_model_v1',
            healthy: true,
            currentSourceSealedInference: true,
          }),
        } as Response);
      }
      if (url.endsWith('/api/video-to-analysis/operator-dashboard') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            schemaVersion: 'video_to_analysis_operator_dashboard_view_model_v1',
            ready: true,
            accepted: true,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/video-to-analysis/promotion-review')
        && !init
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/video-to-analysis/promoted-runtime-monitoring')
      && !init
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/video-to-analysis/operator-dashboard')
      && !init
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url]) => String(url) === '/video-to-analysis/promotion-review')).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url) === '/video-to-analysis/promoted-runtime-monitoring')).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url) === '/video-to-analysis/operator-dashboard')).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/quota'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/training/admit'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/receipts/promotion'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(screen.queryByText(/historical finish-line is not current-source sealed inference/i)).toBeNull();
    expect(screen.queryByText(/not complete-match acceptance/i)).toBeNull();
    const promotionReview = within(await screen.findByRole('region', { name: /stored promotion-review report/i }));
    expect(promotionReview.getByText(/historical promotion-review is not current-source promotion/i)).toBeTruthy();
    expect(promotionReview.getByText(/independent labels stay unreviewed/i)).toBeTruthy();
    const runtime = within(await screen.findByRole('region', { name: /stored promoted-runtime monitoring/i }));
    expect(runtime.getByText(/historical promoted-runtime-monitoring is not current-source sealed inference/i)).toBeTruthy();
    expect(runtime.getByText(/promoted runtime stays unproven/i)).toBeTruthy();
    const dashboard = within(await screen.findByRole('region', { name: /stored operator dashboard/i }));
    expect(dashboard.getByText(/historical operator-dashboard is not current-source sealed inference/i)).toBeTruthy();
    expect(dashboard.getByText(/operator dashboard stays non-accepting/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored real-video-scaleout and bounded-next-sample reports and posts decode first without leftover torchcodec frames or current-source scaleout', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/video-to-analysis/real-video-scaleout-report') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            schemaVersion: 'video_to_analysis_real_video_scaleout_report_view_model_v1',
            scaled: true,
            labelsIndependent: true,
          }),
        } as Response);
      }
      if (url.endsWith('/api/video-to-analysis/bounded-next-sample-report') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            schemaVersion: 'video_to_analysis_bounded_next_sample_report_view_model_v1',
            complete: true,
            completeTasks: 18,
          }),
        } as Response);
      }
      if (url.endsWith('/api/decode/first') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            backend: 'fixture',
            sourceFrameIndex: 0,
            device: 'cpu',
            gpuPromoted: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/video-to-analysis/real-video-scaleout-report')
        && !init
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/video-to-analysis/bounded-next-sample-report')
      && !init
    ))).toBe(true);
    await waitFor(() => expect(screen.getByRole('button', { name: /request decode first/i })).toBeTruthy());
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/decode/first'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /request decode first/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/decode/first')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/decode/first')
      && Boolean(init?.body && (String(init.body).includes('torchcodec') || String(init.body).includes('sourceFrameIndex')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url) === '/video-to-analysis/real-video-scaleout-report')).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url) === '/video-to-analysis/bounded-next-sample-report')).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/quota'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/training/admit'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/receipts/promotion'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(screen.queryByText(/decimal GB is not GiB/i)).toBeNull();
    expect(screen.queryByText(/client pyav cuda frames are not sent/i)).toBeNull();
    const scaleout = within(await screen.findByRole('region', { name: /stored real-video-scaleout report/i }));
    expect(scaleout.getByText(/historical real-video-scaleout-report is not current-source sealed inference/i)).toBeTruthy();
    expect(scaleout.getByText(/scaleout does not admit independent labels/i)).toBeTruthy();
    const nextSample = within(await screen.findByRole('region', { name: /stored bounded next-sample report/i }));
    expect(nextSample.getByText(/historical bounded-next-sample-report is not current-source sealed inference/i)).toBeTruthy();
    expect(nextSample.getByText(/next sample stays bounded and unlabeled/i)).toBeTruthy();
    const decodeFirst = within(screen.getByRole('region', { name: /unforced decode first/i }));
    expect(decodeFirst.getByText(/keeps sourceFrameIndex 0/i)).toBeTruthy();
    expect(decodeFirst.getByText(/client torchcodec index 7 is not sent/i)).toBeTruthy();
    expect(decodeFirst.getByText(/first-frame decode is not GPU promotion/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts detector, tracker, and event propose without leftover cuda, silentlyReconnected true, or accepted true', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/detector') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            requestedBackend: 'cuda',
            selectedBackend: 'cpu',
            fallback: 'cpu',
            exportFpsEqualsInferenceFps: false,
            silentlyChangedColour: false,
          }),
        } as Response);
      }
      if (url.endsWith('/api/tracker') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ tracks: [], silentlyReconnected: false }),
        } as Response);
      }
      if (url.endsWith('/api/events/propose') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            family: 'pass',
            status: 'withheld',
            accepted: false,
            reasonCodes: ['MISSING_RELEASE_OR_RECEIPT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => expect(screen.getByRole('button', { name: /request detector/i })).toBeTruthy());
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/detector'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/tracker'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/events/propose'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /request detector/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/detector')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request tracker/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/tracker')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request event propose/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/events/propose')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/detector')
      && Boolean(init?.body && (String(init.body).includes('cuda') || String(init.body).includes('videoEngineCapability')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/tracker')
      && Boolean(init?.body && (String(init.body).includes('silentlyReconnected') || String(init.body).includes('cutDetected')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/events/propose')
      && Boolean(init?.body && (String(init.body).includes('accepted') || String(init.body).includes('release')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/quota'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/training/admit'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/receipts/promotion'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(screen.queryByText(/event AP stays unproven/i)).toBeNull();
    expect(screen.queryByText(/silentlyReconnected stays false/i)).toBeNull();
    const detector = within(screen.getByRole('region', { name: /unforced detector/i }));
    expect(detector.getByText(/keeps selectedBackend cpu/i)).toBeTruthy();
    expect(detector.getByText(/client videoEngineCapability true is not sent/i)).toBeTruthy();
    expect(detector.getByText(/detector cuda request stays on cpu/i)).toBeTruthy();
    const tracker = within(screen.getByRole('region', { name: /unforced tracker/i }));
    expect(tracker.getByText(/keeps silentlyReconnected false/i)).toBeTruthy();
    expect(tracker.getByText(/client silentlyReconnected true is not sent/i)).toBeTruthy();
    expect(tracker.getByText(/cut reconnect stays off/i)).toBeTruthy();
    const propose = within(screen.getByRole('region', { name: /unforced event propose/i }));
    expect(propose.getByText(/keeps accepted false/i)).toBeTruthy();
    expect(propose.getByText(/client accepted true is not sent/i)).toBeTruthy();
    expect(propose.getByText(/MISSING_RELEASE_OR_RECEIPT stays withheld/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts decode export, decode probe, and decode pixels without leftover sourceUrl, ffmpeg default, or cuda', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/decode/export') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ admitted: false, reasonCodes: ['UNCONSTRAINED_DECODER'] }),
        } as Response);
      }
      if (url.endsWith('/api/decode/probe') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ name: 'ffmpeg', default: false, role: 'challenger' }),
        } as Response);
      }
      if (url.endsWith('/api/decode/pixels') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ shape: [1, 1, 3], gpuPromoted: false, device: 'cpu' }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => expect(screen.getByRole('button', { name: /request decode export/i })).toBeTruthy());
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/decode/export'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/decode/probe'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/decode/pixels'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /request decode export/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/decode/export')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request decode probe/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/decode/probe')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request decode pixels/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/decode/pixels')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/decode/export')
      && Boolean(init?.body && (String(init.body).includes('sourceUrl') || String(init.body).includes('admitted')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/decode/probe')
      && Boolean(init?.body && (String(init.body).includes('ffmpeg') || String(init.body).includes('default')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/decode/pixels')
      && Boolean(init?.body && (String(init.body).includes('cuda') || String(init.body).includes('device')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/quota'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/training/admit'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/receipts/promotion'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(screen.queryByText(/client pyav cuda frames are not sent/i)).toBeNull();
    expect(screen.queryByText(/torchcodec stays a challenger/i)).toBeNull();
    const decodeExport = within(screen.getByRole('region', { name: /unforced decode export/i }));
    expect(decodeExport.getByText(/keeps admitted false/i)).toBeTruthy();
    expect(decodeExport.getByText(/client sourceUrl is not sent/i)).toBeTruthy();
    expect(decodeExport.getByText(/unconstrained decoder stays refused/i)).toBeTruthy();
    const decodeProbe = within(screen.getByRole('region', { name: /unforced decode probe/i }));
    expect(decodeProbe.getByText(/keeps ffmpeg default false/i)).toBeTruthy();
    expect(decodeProbe.getByText(/client default true is not sent/i)).toBeTruthy();
    expect(decodeProbe.getByText(/ffmpeg probe is not the production decoder/i)).toBeTruthy();
    const decodePixels = within(screen.getByRole('region', { name: /unforced decode pixels/i }));
    expect(decodePixels.getByText(/keep gpuPromoted false/i)).toBeTruthy();
    expect(decodePixels.getByText(/client device cuda is not sent/i)).toBeTruthy();
    expect(decodePixels.getByText(/live pixel wrap stays on cpu/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts decode crop, decode cuts, and decode grid without leftover rotation, invented cuts, or client onGrid', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/decode/crop') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            width: 1920,
            height: 1080,
            colourOrder: 'bgr',
            rotation: 0,
            crop: [0, 0, 1920, 1080],
          }),
        } as Response);
      }
      if (url.endsWith('/api/decode/cuts') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            cuts: [],
            anchors: { beginning: null, middle: null, end: null, discontinuities: [] },
          }),
        } as Response);
      }
      if (url.endsWith('/api/decode/grid') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            clipStartSourceFrame: 0,
            evaluationStep: 1,
            onGrid: true,
            remainder: 0,
            policy: 'source_global_grid',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => expect(screen.getByRole('button', { name: /request decode crop/i })).toBeTruthy());
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/decode/crop'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/decode/cuts'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/decode/grid'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /request decode crop/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/decode/crop')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request decode cuts/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/decode/cuts')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request decode grid/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/decode/grid')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/decode/crop')
      && Boolean(init?.body && (String(init.body).includes('rotation') || String(init.body).includes('colourOrder')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/decode/cuts')
      && Boolean(init?.body && (String(init.body).includes('times') || String(init.body).includes('cuts')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/decode/grid')
      && Boolean(init?.body && (String(init.body).includes('clipStartSourceFrame') || String(init.body).includes('onGrid')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/quota'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/training/admit'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/receipts/promotion'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(screen.queryByText(/cut reconnect stays off/i)).toBeNull();
    expect(screen.queryByText(/live pixel wrap stays on cpu/i)).toBeNull();
    const decodeCrop = within(screen.getByRole('region', { name: /unforced decode crop/i }));
    expect(decodeCrop.getByText(/keeps rotation 0/i)).toBeTruthy();
    expect(decodeCrop.getByText(/client colourOrder rgb is not sent/i)).toBeTruthy();
    expect(decodeCrop.getByText(/crop stays bgr/i)).toBeTruthy();
    const decodeCuts = within(screen.getByRole('region', { name: /unforced decode cuts/i }));
    expect(decodeCuts.getByText(/keep stored times empty/i)).toBeTruthy();
    expect(decodeCuts.getByText(/client cuts array is not sent/i)).toBeTruthy();
    expect(decodeCuts.getByText(/camera-cut invention stays off/i)).toBeTruthy();
    const decodeGrid = within(screen.getByRole('region', { name: /unforced decode grid/i }));
    expect(decodeGrid.getByText(/keeps policy source_global_grid/i)).toBeTruthy();
    expect(decodeGrid.getByText(/client clipStartSourceFrame 13 is not sent/i)).toBeTruthy();
    expect(decodeGrid.getByText(/client onGrid true is not sent/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts decode wrap, decode fallback, and decode sample without leftover cuda wrap, selected cuda, or exported true', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/decode/wrap') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            device: 'cpu',
            lifetime: 'borrowed',
            syncRequired: false,
            gpuPromoted: false,
          }),
        } as Response);
      }
      if (url.endsWith('/api/decode/fallback') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ selected: 'opencv', availableIncludesCuda: false }),
        } as Response);
      }
      if (url.endsWith('/api/decode/sample') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            exported: true,
            frameInterval: 5,
            targetFpsEqualsInferenceFps: false,
            sample: { sourceFrameIndex: 0 },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => expect(screen.getByRole('button', { name: /request decode wrap/i })).toBeTruthy());
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/decode/wrap'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/decode/fallback'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/decode/sample'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /request decode wrap/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/decode/wrap')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request decode fallback/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/decode/fallback')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request decode sample/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/decode/sample')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/decode/wrap')
      && Boolean(init?.body && (String(init.body).includes('cuda') || String(init.body).includes('payload')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/decode/fallback')
      && Boolean(init?.body && (String(init.body).includes('cuda') || String(init.body).includes('selected')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/decode/sample')
      && Boolean(init?.body && (String(init.body).includes('exported') || String(init.body).includes('sourceFrameIndex')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/quota'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/training/admit'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/receipts/promotion'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/decode/proxy-pts'))).toBe(false);
    expect(screen.queryByText(/live pixel wrap stays on cpu/i)).toBeNull();
    expect(screen.queryByText(/detector cuda request stays on cpu/i)).toBeNull();
    const decodeWrap = within(screen.getByRole('region', { name: /unforced decode wrap/i }));
    expect(decodeWrap.getByText(/keeps lifetime borrowed/i)).toBeTruthy();
    expect(decodeWrap.getByText(/client payload cuda is not sent/i)).toBeTruthy();
    expect(decodeWrap.getByText(/borrowed wrap stays unpromoted/i)).toBeTruthy();
    const decodeFallback = within(screen.getByRole('region', { name: /unforced decode fallback/i }));
    expect(decodeFallback.getByText(/keeps selected opencv/i)).toBeTruthy();
    expect(decodeFallback.getByText(/client selected cuda is not sent/i)).toBeTruthy();
    expect(decodeFallback.getByText(/CUDA stays unavailable/i)).toBeTruthy();
    const decodeSample = within(screen.getByRole('region', { name: /unforced decode sample/i }));
    expect(decodeSample.getByText(/keeps targetFpsEqualsInferenceFps false/i)).toBeTruthy();
    expect(decodeSample.getByText(/client exported true is not sent/i)).toBeTruthy();
    expect(decodeSample.getByText(/sample mapping does not prove inference fps/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts decode pts, decode interval, and perception preprocess without leftover seconds, proxy mapping, or football rules', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/decode/pts') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ seconds: 0 }),
        } as Response);
      }
      if (url.endsWith('/api/decode/interval') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ interval: [0, 0] }),
        } as Response);
      }
      if (url.endsWith('/api/perception/preprocess') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            colourOrder: 'bgr',
            sourceCoordinatesUnchanged: true,
            silentlyChangedColour: false,
            footballRulesApplied: false,
            requestedColourOrder: 'rgb',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => expect(screen.getByRole('button', { name: /request decode pts/i })).toBeTruthy());
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/decode/pts'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/decode/interval'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/perception/preprocess'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /request decode pts/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/decode/pts')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request decode interval/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/decode/interval')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request perception preprocess/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/perception/preprocess')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/decode/pts')
      && Boolean(init?.body && (String(init.body).includes('pts') || String(init.body).includes('seconds')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/decode/interval')
      && Boolean(init?.body && (String(init.body).includes('proxy') || String(init.body).includes('mapping')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/perception/preprocess')
      && Boolean(init?.body && String(init.body).includes('footballRulesApplied'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/quota'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/training/admit'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/receipts/promotion'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/decode/proxy-pts'))).toBe(false);
    expect(screen.queryByText(/sample mapping does not prove inference fps/i)).toBeNull();
    expect(screen.queryByText(/LABELS_INCOMPLETE stays blocking/i)).toBeNull();
    const decodePts = within(screen.getByRole('region', { name: /unforced decode pts/i }));
    expect(decodePts.getByText(/keeps seconds 0/i)).toBeTruthy();
    expect(decodePts.getByText(/client pts 90000 is not sent/i)).toBeTruthy();
    expect(decodePts.getByText(/client seconds override is not sent/i)).toBeTruthy();
    const decodeInterval = within(screen.getByRole('region', { name: /unforced decode interval/i }));
    expect(decodeInterval.getByText(/keeps interval 0 to 0/i)).toBeTruthy();
    expect(decodeInterval.getByText(/client proxy mapping is not sent/i)).toBeTruthy();
    expect(decodeInterval.getByText(/proxy kind does not remap the interval/i)).toBeTruthy();
    const preprocess = within(screen.getByRole('region', { name: /unforced perception preprocess/i }));
    expect(preprocess.getByText(/keeps footballRulesApplied false/i)).toBeTruthy();
    expect(preprocess.getByText(/client footballRulesApplied true is not sent/i)).toBeTruthy();
    expect(preprocess.getByText(/source coordinates stay unchanged/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts perception stratum, ball-states, and identity preview without leftover labelsIndependent, inferred rows, or committed true', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/perception/stratum') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ labelsIndependent: false, byStratum: {} }),
        } as Response);
      }
      if (url.endsWith('/api/perception/ball-states') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ visible: 0, inferred: 0, unknown: 0 }),
        } as Response);
      }
      if (url.endsWith('/api/identity/preview') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            preview: true,
            committed: false,
            visionRerun: false,
            kind: 'track_split',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => expect(screen.getByRole('button', { name: /request perception stratum/i })).toBeTruthy());
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/perception/stratum'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/perception/ball-states'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/identity/preview'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /request perception stratum/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/perception/stratum')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request perception ball-states/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/perception/ball-states')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request identity preview/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/identity/preview')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/perception/stratum')
      && Boolean(init?.body && String(init.body).includes('labelsIndependent'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/perception/ball-states')
      && Boolean(init?.body && String(init.body).includes('rows'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/identity/preview')
      && Boolean(init?.body && (String(init.body).includes('committed') || String(init.body).includes('visionRerun')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/quota'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/training/admit'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/receipts/promotion'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/decode/proxy-pts'))).toBe(false);
    expect(screen.queryByText(/LABELS_INCOMPLETE stays blocking/i)).toBeNull();
    expect(screen.queryByText(/source coordinates stay unchanged/i)).toBeNull();
    const stratum = within(screen.getByRole('region', { name: /unforced perception stratum/i }));
    expect(stratum.getByText(/keeps labelsIndependent false/i)).toBeTruthy();
    expect(stratum.getByText(/client labelsIndependent true is not sent/i)).toBeTruthy();
    expect(stratum.getByText(/empty stratum stays unlabeled/i)).toBeTruthy();
    const ballStates = within(screen.getByRole('region', { name: /unforced perception ball-states/i }));
    expect(ballStates.getByText(/keep visible 0/i)).toBeTruthy();
    expect(ballStates.getByText(/client inferred rows are not sent/i)).toBeTruthy();
    expect(ballStates.getByText(/empty rows stay unknown-counted/i)).toBeTruthy();
    const preview = within(screen.getByRole('region', { name: /unforced identity preview/i }));
    expect(preview.getByText(/keeps committed false/i)).toBeTruthy();
    expect(preview.getByText(/client committed true is not sent/i)).toBeTruthy();
    expect(preview.getByText(/vision rerun stays off/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts perception tiles, sharing, and media colour without leftover productQualityPass, expired false, or convert false', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/perception/tiles') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            merged: [],
            sourceCoordinates: true,
            productQualityPass: false,
          }),
        } as Response);
      }
      if (url.endsWith('/api/sharing') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            objectId: '',
            expiresAt: 0,
            expiredAtNow: true,
            expiredAtTtl: true,
          }),
        } as Response);
      }
      if (url.endsWith('/api/media/colour') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            pixels: [30, 200, 10],
            sourceBox: [10, 20, 40, 50],
            rotationApplied: false,
            colourOrder: 'bgr',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => expect(screen.getByRole('button', { name: /request perception tiles/i })).toBeTruthy());
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/perception/tiles'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/sharing'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/media/colour'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /request perception tiles/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/perception/tiles')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request sharing/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/sharing')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request media colour/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/media/colour')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/perception/tiles')
      && Boolean(init?.body && (String(init.body).includes('detections') || String(init.body).includes('origin')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/sharing')
      && Boolean(init?.body && (String(init.body).includes('expired') || String(init.body).includes('objectId')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/media/colour')
      && Boolean(init?.body && (String(init.body).includes('convert') || String(init.body).includes('rotation')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/quota'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/training/admit'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/receipts/promotion'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/decode/proxy-pts'))).toBe(false);
    expect(screen.queryByText(/source coordinates stay unchanged/i)).toBeNull();
    expect(screen.queryByText(/empty stratum stays unlabeled/i)).toBeNull();
    const tiles = within(screen.getByRole('region', { name: /unforced perception tiles/i }));
    expect(tiles.getByText(/keep productQualityPass false/i)).toBeTruthy();
    expect(tiles.getByText(/client detections are not sent/i)).toBeTruthy();
    expect(tiles.getByText(/empty tiles stay unmerged/i)).toBeTruthy();
    const sharing = within(screen.getByRole('region', { name: /unforced sharing/i }));
    expect(sharing.getByText(/keeps expiredAtNow true/i)).toBeTruthy();
    expect(sharing.getByText(/client expired false is not sent/i)).toBeTruthy();
    expect(sharing.getByText(/empty TTL stays expired/i)).toBeTruthy();
    const colour = within(screen.getByRole('region', { name: /unforced media colour/i }));
    expect(colour.getByText(/keeps rotationApplied false/i)).toBeTruthy();
    expect(colour.getByText(/client convert false is not sent/i)).toBeTruthy();
    expect(colour.getByText(/colour round-trip stays bgr/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts geometry zoom-cut, metrics spec, and worker import without leftover changed false, identityContinuous, or qualityAccepted', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/geometry/zoom-cut') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({ changed: true }),
        } as Response);
      }
      if (url.endsWith('/api/metrics/spec') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            metric: 'my_team_distance_m',
            availability: 'withheld',
            value: null,
            reasonCodes: ['IDENTITY_DISCONTINUITY', 'CALIBRATION_UNAVAILABLE'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/worker/import') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            imported: false,
            productQualityPass: false,
            jobSucceeded: false,
            reasonCodes: ['UNRECOGNISED_WORKER_OUTPUT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => expect(screen.getByRole('button', { name: /request geometry zoom-cut/i })).toBeTruthy());
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/geometry/zoom-cut'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/metrics/spec'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/worker/import'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /request geometry zoom-cut/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/geometry/zoom-cut')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request metrics spec/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/metrics/spec')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request worker import/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/worker/import')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/geometry/zoom-cut')
      && Boolean(init?.body && String(init.body).includes('changed'))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/metrics/spec')
      && Boolean(init?.body && (String(init.body).includes('identityContinuous') || String(init.body).includes('calibrationAccepted')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/worker/import')
      && Boolean(init?.body && (String(init.body).includes('qualityAccepted') || String(init.body).includes('jobSucceeded')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/quota'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/training/admit'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/receipts/promotion'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/decode/proxy-pts'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/access/object'))).toBe(false);
    expect(screen.queryByText(/colour round-trip stays bgr/i)).toBeNull();
    expect(screen.queryByText(/empty tiles stay unmerged/i)).toBeNull();
    const zoomCut = within(screen.getByRole('region', { name: /unforced geometry zoom-cut/i }));
    expect(zoomCut.getByText(/keeps changed true/i)).toBeTruthy();
    expect(zoomCut.getByText(/client changed false is not sent/i)).toBeTruthy();
    expect(zoomCut.getByText(/homography shift stays a cut/i)).toBeTruthy();
    const spec = within(screen.getByRole('region', { name: /unforced metrics spec/i }));
    expect(spec.getByText(/keeps availability withheld/i)).toBeTruthy();
    expect(spec.getByText(/client identityContinuous true is not sent/i)).toBeTruthy();
    expect(spec.getByText(/spec value stays None/i)).toBeTruthy();
    const workerImport = within(screen.getByRole('region', { name: /unforced worker import/i }));
    expect(workerImport.getByText(/keeps imported false/i)).toBeTruthy();
    expect(workerImport.getByText(/client jobSucceeded true is not sent/i)).toBeTruthy();
    expect(workerImport.getByText(/empty kind stays unrecognised/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts assistance ground, select-evidence, and metrics legacy-zero without leftover fabricated evidence, claimedIds, or measured true', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/assistance/ground') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            route: 'template',
            reasonCodes: ['GROUNDED'],
            output: { evidence: [] },
          }),
        } as Response);
      }
      if (url.endsWith('/api/assistance/select-evidence') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: true,
            evidence: [],
            reasonCodes: ['GROUNDED'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/metrics/legacy-zero') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            metric: 'possession_pct',
            value: null,
            availability: 'unknown',
            reasonCodes: ['LEGACY_ZERO_DEFAULT', 'UNMEASURED_LEGACY_DEFAULT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => expect(screen.getByRole('button', { name: /request assistance ground/i })).toBeTruthy());
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/assistance/ground'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/assistance/select-evidence'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/metrics/legacy-zero'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /request assistance ground/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/assistance/ground')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request assistance select-evidence/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/assistance/select-evidence')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request metrics legacy-zero/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/metrics/legacy-zero')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/assistance/ground')
      && Boolean(init?.body && (String(init.body).includes('evidence') || String(init.body).includes('forged')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/assistance/select-evidence')
      && Boolean(init?.body && (String(init.body).includes('claimedIds') || String(init.body).includes('forged')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/metrics/legacy-zero')
      && Boolean(init?.body && (String(init.body).includes('measured') || String(init.body).includes('availability')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/quota'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/training/admit'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/receipts/promotion'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/decode/proxy-pts'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/access/object'))).toBe(false);
    expect(screen.queryByText(/homography shift stays a cut/i)).toBeNull();
    expect(screen.queryByText(/spec value stays None/i)).toBeNull();
    expect(screen.queryByText(/empty kind stays unrecognised/i)).toBeNull();
    const ground = within(screen.getByRole('region', { name: /unforced assistance ground/i }));
    expect(ground.getByText(/keeps route template/i)).toBeTruthy();
    expect(ground.getByText(/client evidence is not sent/i)).toBeTruthy();
    expect(ground.getByText(/empty claimed ids stay grounded/i)).toBeTruthy();
    const selected = within(screen.getByRole('region', { name: /unforced assistance select-evidence/i }));
    expect(selected.getByText(/keeps accepted true/i)).toBeTruthy();
    expect(selected.getByText(/client claimedIds are not sent/i)).toBeTruthy();
    expect(selected.getByText(/empty claimed ids stay selected/i)).toBeTruthy();
    const legacyZero = within(screen.getByRole('region', { name: /unforced metrics legacy-zero/i }));
    expect(legacyZero.getByText(/keeps value None/i)).toBeTruthy();
    expect(legacyZero.getByText(/client measured true is not sent/i)).toBeTruthy();
    expect(legacyZero.getByText(/legacy zero stays unmeasured/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('posts possession-states, reports template, and ownership invalidate without leftover invented possession, client metrics, or report change', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/metrics/possession-states') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            availability: 'insufficient_coverage',
            publishedValue: null,
            unknownSeconds: 0,
            value: null,
            reasonCodes: [],
          }),
        } as Response);
      }
      if (url.endsWith('/api/reports/template') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            kind: 'deterministic_template',
            availableMetrics: [],
            eventCount: 0,
          }),
        } as Response);
      }
      if (url.endsWith('/api/ownership/invalidate') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            change: 'track_edit',
            invalidates: ['ownership', 'player_events', 'metrics', 'report'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => expect(screen.getByRole('button', { name: /request metrics possession-states/i })).toBeTruthy());
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/metrics/possession-states'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/reports/template'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/ownership/invalidate'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: /request metrics possession-states/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/metrics/possession-states')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request reports template/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/reports/template')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    fireEvent.click(screen.getByRole('button', { name: /request ownership invalidate/i }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/ownership/invalidate')
        && init?.method === 'POST'
        && init.body === '{}'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/metrics/possession-states')
      && Boolean(init?.body && (String(init.body).includes('states') || String(init.body).includes('requestedSeconds')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/reports/template')
      && Boolean(init?.body && (String(init.body).includes('metrics') || String(init.body).includes('events')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/ownership/invalidate')
      && Boolean(init?.body && (String(init.body).includes('change') || String(init.body).includes('invalidates')))
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/quota'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/training/admit'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/receipts/promotion'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/decode/proxy-pts'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/access/object'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/ownership/hysteresis'))).toBe(false);
    expect(screen.queryByText(/empty claimed ids stay grounded/i)).toBeNull();
    expect(screen.queryByText(/empty claimed ids stay selected/i)).toBeNull();
    expect(screen.queryByText(/legacy zero stays unmeasured/i)).toBeNull();
    const possessionStates = within(screen.getByRole('region', { name: /unforced metrics possession-states/i }));
    expect(possessionStates.getByText(/keeps publishedValue null/i)).toBeTruthy();
    expect(possessionStates.getByText(/client states are not sent/i)).toBeTruthy();
    expect(possessionStates.getByText(/empty states stay insufficient_coverage/i)).toBeTruthy();
    const template = within(screen.getByRole('region', { name: /unforced reports template/i }));
    expect(template.getByText(/keeps kind deterministic_template/i)).toBeTruthy();
    expect(template.getByText(/client metrics are not sent/i)).toBeTruthy();
    expect(template.getByText(/empty template stays eventCount 0/i)).toBeTruthy();
    const invalidate = within(screen.getByRole('region', { name: /unforced ownership invalidate/i }));
    expect(invalidate.getByText(/keeps change track_edit/i)).toBeTruthy();
    expect(invalidate.getByText(/client report change is not sent/i)).toBeTruthy();
    expect(invalidate.getByText(/track edit still rebuilds ownership/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored independent reviewer, worked match flow, and decode memory without inventing acceptance or GPU residency', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/reviewer') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: false, reasonCodes: ['REVIEWER_NOT_INDEPENDENT'] }),
        } as Response);
      }
      if (url.endsWith('/api/flow') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            illustrative: true,
            jobId: 'run-17',
            correctionInvalidatesReportWithoutRerun: true,
          }),
        } as Response);
      }
      if (url.endsWith('/api/decode/memory') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            gpuResident: false,
            retainAllDecodedFrames: false,
            canPromoteDefault: false,
            videoEngineCapability: false,
            reasonCodes: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/reviewer')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/flow')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/decode/memory')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    const reviewer = within(await screen.findByRole('region', { name: /stored independent reviewer/i }));
    expect(reviewer.getByText(/stays unaccepted/i)).toBeTruthy();
    expect(reviewer.getByText(/REVIEWER_NOT_INDEPENDENT stays blocking/i)).toBeTruthy();
    expect(reviewer.getByText(/held-out predictions stay uninspected/i)).toBeTruthy();
    const flow = within(screen.getByRole('region', { name: /stored worked match flow/i }));
    expect(flow.getByText(/stays illustrative/i)).toBeTruthy();
    expect(flow.getByText(/correction invalidates the report without a rerun/i)).toBeTruthy();
    const memory = within(screen.getByRole('region', { name: /stored decode memory/i }));
    expect(memory.getByText(/stays non-resident on GPU/i)).toBeTruthy();
    expect(memory.getByText(/decoded frames are not retained/i)).toBeTruthy();
    expect(memory.getByText(/hardware decode does not promote a GPU default/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored identity policy, training pools, and shadow flag without inventing face recognition or published shot quality', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if ((url === '/api/identity' || url.endsWith('/api/identity')) && !url.includes('/matches/') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            silentlyReconnected: false,
            faceRecognition: { enabled: false },
            crossSeasonIdentity: { enabled: false },
            appearance: { everyDetection: false, cameraCutDefeatsAppearance: true },
            candidateRejoin: { autoAccepted: false },
          }),
        } as Response);
      }
      if (url.endsWith('/api/training/pools') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ pools: ['operational_corrections', 'training', 'locked_evaluation'] }),
        } as Response);
      }
      if (url.endsWith('/api/flags/shadow/experimental_shot_quality') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ default: false, shadowed: true, published: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        (String(url) === '/api/identity' || String(url).endsWith('/api/identity'))
        && !String(url).includes('/matches/')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/training/pools')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/flags/shadow/experimental_shot_quality')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/training/admit'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    const identity = within(await screen.findByRole('region', { name: /stored identity policy/i }));
    expect(identity.getByText(/keeps face recognition off/i)).toBeTruthy();
    expect(identity.getByText(/cross-season identity stays off/i)).toBeTruthy();
    expect(identity.getByText(/appearance embeddings stay off every detection/i)).toBeTruthy();
    const pools = within(screen.getByRole('region', { name: /stored training pools/i }));
    expect(pools.getByText(/keep locked_evaluation isolated/i)).toBeTruthy();
    expect(pools.getByText(/locked evaluation is not a training source/i)).toBeTruthy();
    const shadow = within(screen.getByRole('region', { name: /stored shadow flag/i }));
    expect(shadow.getByText(/keeps experimental_shot_quality unpublished/i)).toBeTruthy();
    expect(shadow.getByText(/published stays false/i)).toBeTruthy();
    expect(shadow.getByText(/the default stays off/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored legacy display, metric dictionary, and licence register without inventing calibrated measurements', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/quantities/display') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            xAxis: 'longitudinal',
            yAxis: 'lateral',
            transformedExplicitly: true,
            legacyDisplay: 'transform_explicitly',
          }),
        } as Response);
      }
      if (url.endsWith('/api/metrics/dictionary') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            metrics: {
              possession_pct: { publishedLabel: 'possession' },
              experimental_shot_quality: { publishedLabel: 'experimental_shot_quality' },
            },
          }),
        } as Response);
      }
      if (url.endsWith('/api/rights/licences') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            ultralytics: { generalisedToEveryYoloNamedModel: false, reviewExactAssets: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/quantities/display')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/metrics/dictionary')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/rights/licences')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/rights/evaluate'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    const display = within(await screen.findByRole('region', { name: /stored legacy display/i }));
    expect(display.getByText(/transform stays explicit/i)).toBeTruthy();
    expect(display.getByText(/display coordinates are not pitch metres until transformed/i)).toBeTruthy();
    const dictionary = within(screen.getByRole('region', { name: /stored metric dictionary/i }));
    expect(dictionary.getByText(/lists experimental_shot_quality/i)).toBeTruthy();
    expect(dictionary.getByText(/listing a published label is not a calibrated measurement/i)).toBeTruthy();
    const licences = within(screen.getByRole('region', { name: /stored licence register/i }));
    expect(licences.getByText(/does not generalise Ultralytics to every YOLO-named model/i)).toBeTruthy();
    expect(licences.getByText(/generalisedToEveryYoloNamedModel stays false/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored telestration, dataset rights, and metric round-trip without inventing 3D overlay, SoccerNet product, or published values', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/telestration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ blenderEnabled: false, pitchView: '2d', telestration: 'basic' }),
        } as Response);
      }
      if (url.endsWith('/api/rights/datasets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            soccernet: {
              permittedPurpose: 'research',
              commercialProduct: false,
              redistributeCopyrightedVideo: false,
            },
            statsbomb_open_data: {
              permittedPurpose: 'research_pending_licence_check',
              commercialProduct: false,
            },
          }),
        } as Response);
      }
      if (url.endsWith('/api/metrics/round-trip') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            metric: 'possession_pct',
            availability: 'unknown',
            value: null,
            publishedValue: null,
            reasonCodes: ['ZERO_DENOMINATOR'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/telestration')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/rights/datasets')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/metrics/round-trip')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/rights/evaluate'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/shots/tree'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/cache/tenancy'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/reports/assemble'))).toBe(false);
    expect(screen.queryByText(/telestration stays 2d before 3d/i)).toBeNull();
    const telestration = within(await screen.findByRole('region', { name: /stored telestration/i }));
    expect(telestration.getByText(/keeps blenderEnabled false/i)).toBeTruthy();
    expect(telestration.getByText(/pitch view stays 2d/i)).toBeTruthy();
    expect(telestration.getByText(/blender is not admitted as 3D overlay/i)).toBeTruthy();
    const datasets = within(screen.getByRole('region', { name: /stored dataset rights/i }));
    expect(datasets.getByText(/keep SoccerNet commercialProduct false/i)).toBeTruthy();
    expect(datasets.getByText(/research purpose is not a commercial product licence/i)).toBeTruthy();
    const roundTrip = within(screen.getByRole('region', { name: /stored metric round-trip/i }));
    expect(roundTrip.getByText(/keeps availability unknown/i)).toBeTruthy();
    expect(roundTrip.getByText(/publishedValue stays null/i)).toBeTruthy();
    expect(roundTrip.getByText(/unknown metrics do not acquire a published value/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored incident response, provider roster, and stale permissions without leftover POST admission', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/rights/incident') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            path: 'record, contain, notify, restore, review',
            faceRecognition: false,
            crossSeasonIdentity: false,
            supportBundles: 'scoped_consented_time_limited',
          }),
        } as Response);
      }
      if (url.endsWith('/api/providers') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            roster: { default: 'disabled', adapters: { local: 'template_fallback', cloud: 'gated' } },
            local: { route: 'disabled' },
            cloud: { route: 'disabled' },
          }),
        } as Response);
      }
      if (url.endsWith('/api/permissions/stale') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            stale: true,
            admitted: false,
            reasonCodes: ['STALE_PERMISSION'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/rights/incident')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/providers')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/permissions/stale')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/providers') && init?.method === 'POST'
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/permissions/stale') && init?.method === 'POST'
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/rights/evaluate'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(screen.queryByText(/language providers stay disabled by default/i)).toBeNull();
    expect(screen.queryByText(/stale permissions are not admitted/i)).toBeNull();
    expect(screen.queryByText(/face recognition is not enabled/i)).toBeNull();
    const incident = within(await screen.findByRole('region', { name: /stored incident response/i }));
    expect(incident.getByText(/keeps faceRecognition false/i)).toBeTruthy();
    expect(incident.getByText(/crossSeasonIdentity stays false/i)).toBeTruthy();
    expect(incident.getByText(/incident restore does not enable face recognition/i)).toBeTruthy();
    const providers = within(screen.getByRole('region', { name: /stored provider roster/i }));
    expect(providers.getByText(/keeps the default disabled/i)).toBeTruthy();
    expect(providers.getByText(/client enabled cloud is not sent/i)).toBeTruthy();
    expect(providers.getByText(/local and cloud routes stay disabled/i)).toBeTruthy();
    const stale = within(screen.getByRole('region', { name: /stored stale permissions/i }));
    expect(stale.getByText(/keep admitted false/i)).toBeTruthy();
    expect(stale.getByText(/client admitted true is not sent/i)).toBeTruthy();
    expect(stale.getByText(/STALE_PERMISSION stays blocking/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored signed object access, legacy geometry, and split scores without inventing tokens or calibration', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/access/signed') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            admitted: false,
            scoped: true,
            reasonCodes: ['UNSIGNED_OR_UNSCOPED_OBJECT_ACCESS'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/geometry/legacy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            compatibleWithFourPointV1: true,
            evaluation: { accepted: false, reasonCodes: ['CALIBRATION_UNAVAILABLE'], holdoutCount: 0 },
            withheld: { availability: 'withheld' },
            landmarks: [{ independentHoldout: false }],
          }),
        } as Response);
      }
      if (url.endsWith('/api/quantities/scores') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            detectorScore: null,
            calibratedProbability: null,
            confidenceInterval: null,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/access/signed')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/geometry/legacy')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/quantities/scores')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/access/signed') && init?.method === 'POST'
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/geometry/legacy') && init?.method === 'POST'
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/quantities/scores') && init?.method === 'POST'
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/geometry/landmarks'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/geometry/preview'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/rates/four'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(screen.queryByText(/unsigned or unscoped job access is refused/i)).toBeNull();
    expect(screen.queryByText(/four homography points do not make calibration accepted/i)).toBeNull();
    const signed = within(await screen.findByRole('region', { name: /stored signed object access/i }));
    expect(signed.getByText(/keeps admitted false/i)).toBeTruthy();
    expect(signed.getByText(/UNSIGNED_OR_UNSCOPED_OBJECT_ACCESS stays blocking/i)).toBeTruthy();
    expect(signed.getByText(/a missing token is not scoped object admission/i)).toBeTruthy();
    const geometry = within(screen.getByRole('region', { name: /stored legacy geometry/i }));
    expect(geometry.getByText(/keeps evaluation.accepted false/i)).toBeTruthy();
    expect(geometry.getByText(/four default corners do not invent calibration_accepted/i)).toBeTruthy();
    expect(geometry.getByText(/CALIBRATION_UNAVAILABLE stays blocking/i)).toBeTruthy();
    const scores = within(screen.getByRole('region', { name: /stored split scores/i }));
    expect(scores.getByText(/keep detectorScore null/i)).toBeTruthy();
    expect(scores.getByText(/calibratedProbability stays null/i)).toBeTruthy();
    expect(scores.getByText(/a detector score is not a calibrated probability/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored release dossier, training sampling, and dependencies without leftover POST native approval', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.endsWith('/api/dossier/release') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            deploymentBoundary: 'loopback',
            gNetworkRequiredForNonLocal: true,
            nativeCode: 'gated_inert',
          }),
        } as Response);
      }
      if (url.endsWith('/api/training/sampling') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            uncertaintyOnly: false,
            mix: ['difficult', 'random_representative'],
            trackPolicy: true,
          }),
        } as Response);
      }
      if (url.endsWith('/api/dependencies') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            ultralytics: { fashionableOnly: false, rollbackPath: 'pinned_previous_detector_adapter' },
            opencv: { fashionableOnly: false, rollbackPath: 'fixture_frame_source' },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).endsWith('/api/dossier/release')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/training/sampling')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/dependencies')
      && (!init?.method || init.method === 'GET')
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/dossier/release') && init?.method === 'POST'
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/api/dependencies') && init?.method === 'POST'
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/training/admit'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/capacity'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/research/tracks/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/roster/labels'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/incidents/ladder'))).toBe(false);
    expect(screen.queryByText(/release dossier keeps native code gated and loopback-only/i)).toBeNull();
    expect(screen.queryByText(/locked evaluation labels cannot enter training/i)).toBeNull();
    const dossier = within(await screen.findByRole('region', { name: /stored release dossier/i }));
    expect(dossier.getByText(/keeps nativeCode gated_inert/i)).toBeTruthy();
    expect(dossier.getByText(/deploymentBoundary stays loopback/i)).toBeTruthy();
    expect(dossier.getByText(/client nativeCode approved is not sent/i)).toBeTruthy();
    const sampling = within(screen.getByRole('region', { name: /stored training sampling/i }));
    expect(sampling.getByText(/keeps uncertaintyOnly false/i)).toBeTruthy();
    expect(sampling.getByText(/mix includes random_representative/i)).toBeTruthy();
    expect(sampling.getByText(/uncertainty sampling is not the only training source/i)).toBeTruthy();
    const dependencies = within(screen.getByRole('region', { name: /stored dependency register/i }));
    expect(dependencies.getByText(/keeps fashionableOnly false/i)).toBeTruthy();
    expect(dependencies.getByText(/client fashionableOnly true is not sent/i)).toBeTruthy();
    expect(dependencies.getByText(/OpenCV rollbackPath stays fixture_frame_source/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads derived proxy assets on the review App without replacing the original source', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            replacesOriginal: false,
            originalRetained: true,
            assets: { proxy: { kind: 'browsing_proxy', height: 720 }, thumbnails: { kind: 'thumbnails' }, waveform: { kind: 'waveform' } },
            ptsMap: [{ originalPts: 0, proxyPts: 0, originalSeconds: 0, proxySeconds: 0 }],
            frameExactExport: { keyframeSeekIsExact: false },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true, intervals: [[0, 0.2]] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/media/proxy')
        && (!init?.method || init.method === 'GET')
        && !String(url).includes('decode/proxy-pts')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/decode/proxy-pts'))).toBe(false);
    expect(await screen.findByText(/retain the original/i)).toBeTruthy();
    expect(screen.getByText(/does not replace the original/i)).toBeTruthy();
    expect(screen.getByText(/original-to-proxy presentation time/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('maps source presentation time to match clock without claiming frame-accurate overlay', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue({
      ...loadedWorkspace('match-a', 'Match A'),
      frames: [{ Frame_ID: 0, Timestamp: 0.2, Ball: null, My_Team: [], Enemies: [] }],
      frameCount: 1,
    });
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
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
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
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

  it('loads stored four rates without treating export fps as inference fps', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/rates') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            decodeCount: 3,
            detectorPrimaryCount: 3,
            detectorRecoveryCount: 0,
            trackerUpdateCount: 3,
            exportCount: 5,
            exportFpsEqualsInferenceFps: false,
            decodeFpsEqualsExportFps: false,
            notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS', 'FOUR_RATES_UNRECORDED'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/rates')
        && (!init?.method || init.method === 'GET')
        && !String(url).includes('/api/rates/four')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/rates/four'))).toBe(false);
    expect(await screen.findByText(/decode, detector, tracker and export/i)).toBeTruthy();
    expect(screen.getByText(/export fps is not inference fps/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored match setup without certifying automation', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/setup') && !url.includes('/preview') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
            exportFpsEqualsInferenceFps: false,
            notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/setup')
        && !String(url).includes('/preview')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/setup/preview'))).toBe(false);
    expect(await screen.findByText(/setup wizard/i)).toBeTruthy();
    expect(screen.getByText(/manual tagging permitted/i)).toBeTruthy();
    expect(screen.getAllByText(/not a certification/i).length).toBeGreaterThanOrEqual(1);
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('inspects stored match metrics as unavailable without inventing zero', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
            exportFpsEqualsInferenceFps: false,
            notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
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
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
            coverageAware: true,
            representsWholeMatch: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics/inspect/my_team_distance_m') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
            exportFpsEqualsInferenceFps: false,
            notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
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

  it('shows stored analyst workflow measures as unmeasured without claiming a completed review', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/coverage') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            coverageAware: true,
            representsWholeMatch: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics/inspect/my_team_distance_m') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
            exportFpsEqualsInferenceFps: false,
            notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/evaluation/workflow')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    const workflow = within(await screen.findByRole('region', { name: /analyst workflow/i }));
    expect(workflow.getByText(/remain unmeasured/i)).toBeTruthy();
    expect(workflow.getByText(/ANALYST_ACCEPTANCE_MISSING/)).toBeTruthy();
    expect(workflow.getByText(/not a completed reviewed match/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored report provenance without accepting fabricated evidence', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: true,
            reasonCodes: [],
            missingEvidenceIds: [],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/coverage') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            coverageAware: true,
            representsWholeMatch: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics/inspect/my_team_distance_m') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
            exportFpsEqualsInferenceFps: false,
            notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/reports/provenance')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/reports/assemble'))).toBe(false);
    expect(await screen.findByText(/lead back to stored evidence/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored shot quality as experimental without treating it as calibrated xG', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/quality')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: true,
            reasonCodes: [],
            missingEvidenceIds: [],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/coverage') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            coverageAware: true,
            representsWholeMatch: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics/inspect/my_team_distance_m') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
            exportFpsEqualsInferenceFps: false,
            notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/shots/quality')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/shots/tree'))).toBe(false);
    const quality = within(await screen.findByRole('region', { name: /shot quality/i }));
    expect(quality.getByText(/experimental_shot_quality/)).toBeTruthy();
    expect(quality.getByText(/not calibrated xG/i)).toBeTruthy();
    expect(quality.getByText(/EXPERIMENTAL_NOT_CALIBRATED_XG/)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored match audit trail without rewriting past outcomes', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/history') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            undoable: true,
            rewrotePastOutcomes: false,
            items: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/quality')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: true,
            reasonCodes: [],
            missingEvidenceIds: [],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/coverage') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            coverageAware: true,
            representsWholeMatch: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics/inspect/my_team_distance_m') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
            exportFpsEqualsInferenceFps: false,
            notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/history')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    const trail = within(await screen.findByRole('region', { name: /audit trail/i }));
    expect(trail.getByText(/stored audit trail is undoable/i)).toBeTruthy();
    expect(trail.getByText(/rewrotePastOutcomes is false/)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored match privacy screening without leftover generic DPIA', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/privacy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
            undoable: true,
            rewrotePastOutcomes: false,
            items: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/quality')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: true,
            reasonCodes: [],
            missingEvidenceIds: [],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/coverage') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            coverageAware: true,
            representsWholeMatch: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics/inspect/my_team_distance_m') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
            exportFpsEqualsInferenceFps: false,
            notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/privacy')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/privacy/dpia'))).toBe(false);
    const privacy = within(await screen.findByRole('region', { name: /match privacy/i }));
    expect(privacy.getByText(/local processing required/i)).toBeTruthy();
    expect(privacy.getByText(/cloud is not allowed/i)).toBeTruthy();
    expect(privacy.getByText(/face recognition is not enabled/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored tracklets without treating them as match identity', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/privacy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
            undoable: true,
            rewrotePastOutcomes: false,
            items: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/quality')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: true,
            reasonCodes: [],
            missingEvidenceIds: [],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/coverage') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            coverageAware: true,
            representsWholeMatch: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics/inspect/my_team_distance_m') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
            exportFpsEqualsInferenceFps: false,
            notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/tracklets')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    const tracklets = within(await screen.findByRole('region', { name: /tracklets/i }));
    expect(tracklets.getByText(/kind is tracklet, not match identity/i)).toBeTruthy();
    expect(tracklets.getByText(/not silently reconnected/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored production cache identity without mixing development cache', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            namespace: 'production',
            compatibleWithDevelopment: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/privacy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
            undoable: true,
            rewrotePastOutcomes: false,
            items: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/quality')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: true,
            reasonCodes: [],
            missingEvidenceIds: [],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/coverage') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            coverageAware: true,
            representsWholeMatch: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics/inspect/my_team_distance_m') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
            exportFpsEqualsInferenceFps: false,
            notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/cache')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/cache/tenancy'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/cache/tenancy'))).toBe(false);
    const cache = within(await screen.findByRole('region', { name: /cache identity/i }));
    expect(cache.getByText(/production cache identity/i)).toBeTruthy();
    expect(cache.getByText(/not compatible with development/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored promotion receipts without treating a stage benchmark as complete-match acceptance', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/promotion') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            completeMatchAccepted: false,
            stageBenchmarkIsCompleteMatchAcceptance: false,
            outputQuality: 'unproven',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            namespace: 'production',
            compatibleWithDevelopment: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/privacy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
            undoable: true,
            rewrotePastOutcomes: false,
            items: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/quality')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: true,
            reasonCodes: [],
            missingEvidenceIds: [],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/coverage') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            coverageAware: true,
            representsWholeMatch: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics/inspect/my_team_distance_m') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
            exportFpsEqualsInferenceFps: false,
            notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/promotion')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/receipts/promotion'))).toBe(false);
    const receipt = within(await screen.findByRole('region', { name: /promotion receipt/i }));
    expect(receipt.getByText(/not complete-match acceptance/i)).toBeTruthy();
    expect(receipt.getByText(/output quality is unproven/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored ball ownership without treating nearest player as control', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            mode: 'unknown',
            reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/promotion') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            completeMatchAccepted: false,
            stageBenchmarkIsCompleteMatchAcceptance: false,
            outputQuality: 'unproven',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            namespace: 'production',
            compatibleWithDevelopment: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/privacy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
            undoable: true,
            rewrotePastOutcomes: false,
            items: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/quality')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: true,
            reasonCodes: [],
            missingEvidenceIds: [],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/coverage') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            coverageAware: true,
            representsWholeMatch: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics/inspect/my_team_distance_m') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
            exportFpsEqualsInferenceFps: false,
            notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/ownership')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/ownership/hysteresis'))).toBe(false);
    const ownership = within(await screen.findByRole('region', { name: /ball ownership/i }));
    expect(ownership.getByText(/ownership mode is unknown/i)).toBeTruthy();
    expect(ownership.getByText(/NEAREST_PLAYER_INSUFFICIENT/)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored incident geometry without inventing a validated offside', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/geometry') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            decision: null,
            validatedMeasurement: false,
            reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'],
            mostAdvancedTeammateX: 21.0,
            secondLastOpponentX: 18.0,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            mode: 'unknown',
            reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/promotion') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            completeMatchAccepted: false,
            stageBenchmarkIsCompleteMatchAcceptance: false,
            outputQuality: 'unproven',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            namespace: 'production',
            compatibleWithDevelopment: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/privacy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
            undoable: true,
            rewrotePastOutcomes: false,
            items: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/quality')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: true,
            reasonCodes: [],
            missingEvidenceIds: [],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/coverage') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            coverageAware: true,
            representsWholeMatch: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics/inspect/my_team_distance_m') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
            exportFpsEqualsInferenceFps: false,
            notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/incidents/geometry')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/workbench/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('myTeam'))
    ))).toBe(false);
    const geometry = within(await screen.findByRole('region', { name: /incident geometry/i }));
    expect(geometry.getByText(/stored incident geometry is not a validated measurement/i)).toBeTruthy();
    expect(geometry.getByText(/IFAB_LAW_11_NOT_APPLIED/)).toBeTruthy();
    expect(geometry.getByText(/decision is unpublished/i)).toBeTruthy();
    expect(screen.queryAllByText(/attackerX=0/)).toHaveLength(0);
    expect(screen.queryAllByText(/line=0/)).toHaveLength(0);
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored incident package as level 0 clips without inventing an offside ruling', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/package') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            level: 0,
            clips: [{ timestampStart: 0, timestampEnd: 0.4 }],
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
          json: async () => ({
            decision: null,
            validatedMeasurement: false,
            reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            mode: 'unknown',
            reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/promotion') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            completeMatchAccepted: false,
            stageBenchmarkIsCompleteMatchAcceptance: false,
            outputQuality: 'unproven',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            namespace: 'production',
            compatibleWithDevelopment: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/privacy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
            undoable: true,
            rewrotePastOutcomes: false,
            items: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/quality')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: true,
            reasonCodes: [],
            missingEvidenceIds: [],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/coverage') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            coverageAware: true,
            representsWholeMatch: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics/inspect/my_team_distance_m') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
            exportFpsEqualsInferenceFps: false,
            notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/incidents/package')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/workbench/'))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('forged-offside'))
    ))).toBe(false);
    const incidentPackage = within(await screen.findByRole('region', { name: /incident package/i }));
    expect(incidentPackage.getByText(/level 0/i)).toBeTruthy();
    expect(incidentPackage.getByText(/synchronized source clips and notes only/i)).toBeTruthy();
    expect(incidentPackage.getByText(/IFAB_LAW_11_NOT_APPLIED/)).toBeTruthy();
    expect(incidentPackage.getByText(/decision is unpublished/i)).toBeTruthy();
    expect(screen.queryAllByText(/attackerX=0/)).toHaveLength(0);
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored match metrics without inventing zero physical totals', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
            decision: null,
            validatedMeasurement: false,
            reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            mode: 'unknown',
            reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/promotion') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            completeMatchAccepted: false,
            stageBenchmarkIsCompleteMatchAcceptance: false,
            outputQuality: 'unproven',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            namespace: 'production',
            compatibleWithDevelopment: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/privacy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
            undoable: true,
            rewrotePastOutcomes: false,
            items: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/quality')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: true,
            reasonCodes: [],
            missingEvidenceIds: [],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/coverage') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            coverageAware: true,
            representsWholeMatch: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/setup') && !url.includes('/preview') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
            exportFpsEqualsInferenceFps: false,
            notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
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
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/workbench/'))).toBe(false);
    const storedMetrics = within(await screen.findByRole('region', { name: /stored match metrics/i }));
    expect(storedMetrics.getByText(/withhold physical totals/i)).toBeTruthy();
    expect(storedMetrics.getByText(/IDENTITY_DISCONTINUITY/)).toBeTruthy();
    expect(storedMetrics.getByText(/published value is not an invented 0/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored shot features without imputing them as calibrated xG', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            recorded: true,
            missing: ['x', 'y'],
            imputedAsCalibrated: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/quality')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics/inspect/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
            decision: null,
            validatedMeasurement: false,
            reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            mode: 'unknown',
            reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/promotion') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            completeMatchAccepted: false,
            stageBenchmarkIsCompleteMatchAcceptance: false,
            outputQuality: 'unproven',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            namespace: 'production',
            compatibleWithDevelopment: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/privacy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
            undoable: true,
            rewrotePastOutcomes: false,
            items: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: true,
            reasonCodes: [],
            missingEvidenceIds: [],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/coverage') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            coverageAware: true,
            representsWholeMatch: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/setup') && !url.includes('/preview') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
            exportFpsEqualsInferenceFps: false,
            notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ items: [] }),
        } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/shots/features')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/shots/tree'))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && (String(init.body).includes('"goal":true') || String(init.body).includes('"shots"')))
    ))).toBe(false);
    const features = within(await screen.findByRole('region', { name: /shot features/i }));
    expect(features.getByText(/missing shot features are not imputed as calibrated xG/i)).toBeTruthy();
    expect(features.getByText(/imputedAsCalibrated is false/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored player observations without publishing withheld physical totals', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/players') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            intervalLimited: true,
            totalsWithheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ recorded: true, missing: ['x', 'y'], imputedAsCalibrated: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/quality')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics/inspect/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
            decision: null,
            validatedMeasurement: false,
            reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ mode: 'unknown', reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/promotion') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            completeMatchAccepted: false,
            stageBenchmarkIsCompleteMatchAcceptance: false,
            outputQuality: 'unproven',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ namespace: 'production', compatibleWithDevelopment: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/privacy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ undoable: true, rewrotePastOutcomes: false, items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: true, reasonCodes: [], missingEvidenceIds: [] }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/coverage') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ coverageAware: true, representsWholeMatch: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/setup') && !url.includes('/preview') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
            exportFpsEqualsInferenceFps: false,
            notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/players')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('"identityContinuous":true'))
    ))).toBe(false);
    const observations = within(await screen.findByRole('region', { name: /player observations/i }));
    expect(observations.getByText(/stored player observations are interval-limited/i)).toBeTruthy();
    expect(observations.getByText(/totals withheld/i)).toBeTruthy();
    expect(observations.getByText(/IDENTITY_DISCONTINUITY/)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored event partition without publishing rejected candidates as accepted views', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/events/partition') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            acceptedViews: [],
            retainedCandidates: [{ type: 'turnover', reviewStatus: 'rejected' }],
            rejectedRemovedFromAcceptedViews: true,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/players') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            intervalLimited: true,
            totalsWithheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ recorded: true, missing: ['x', 'y'], imputedAsCalibrated: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/quality')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics/inspect/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
            decision: null,
            validatedMeasurement: false,
            reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ mode: 'unknown', reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/promotion') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            completeMatchAccepted: false,
            stageBenchmarkIsCompleteMatchAcceptance: false,
            outputQuality: 'unproven',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ namespace: 'production', compatibleWithDevelopment: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/privacy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ undoable: true, rewrotePastOutcomes: false, items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: true, reasonCodes: [], missingEvidenceIds: [] }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/coverage') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ coverageAware: true, representsWholeMatch: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/setup') && !url.includes('/preview') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
            exportFpsEqualsInferenceFps: false,
            notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/events/partition')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('forged-accepted'))
    ))).toBe(false);
    const partition = within(await screen.findByRole('region', { name: /event partition/i }));
    expect(partition.getByText(/rejected candidates from accepted views/i)).toBeTruthy();
    expect(partition.getByText(/rejectedRemovedFromAcceptedViews is true/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored match identity without inventing continuity from no camera cuts', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (
        url.includes('/api/matches/match-a/identity')
        && !url.includes('/repair')
        && !url.includes('/promote')
        && (!init?.method || init.method === 'GET')
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            reset: false,
            silentlyReconnected: false,
            cutCount: 0,
            identityContinuous: false,
            reasonCodes: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/events/partition') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            acceptedViews: [],
            retainedCandidates: [{ type: 'turnover', reviewStatus: 'rejected' }],
            rejectedRemovedFromAcceptedViews: true,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/players') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            intervalLimited: true,
            totalsWithheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ recorded: true, missing: ['x', 'y'], imputedAsCalibrated: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/quality')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics/inspect/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
            decision: null,
            validatedMeasurement: false,
            reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ mode: 'unknown', reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/promotion') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            completeMatchAccepted: false,
            stageBenchmarkIsCompleteMatchAcceptance: false,
            outputQuality: 'unproven',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ namespace: 'production', compatibleWithDevelopment: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/privacy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ undoable: true, rewrotePastOutcomes: false, items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: true, reasonCodes: [], missingEvidenceIds: [] }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/coverage') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ coverageAware: true, representsWholeMatch: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/setup') && !url.includes('/preview') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
            exportFpsEqualsInferenceFps: false,
            notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/identity')
        && !String(url).includes('/repair')
        && !String(url).includes('/promote')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('"identityContinuous":true'))
    ))).toBe(false);
    const identity = within(await screen.findByRole('region', { name: /stored identity/i }));
    expect(identity.getByText(/no camera cuts do not make identity continuous/i)).toBeTruthy();
    expect(identity.getByText(/stored identityContinuous is false/i)).toBeTruthy();
    expect(identity.getByText(/not silently reconnected/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored attack direction from match config without client mapping', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/attack-direction')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            direction: 'right_to_left',
            fromStoredConfig: true,
            team: 'my_team',
            period: 1,
          }),
        } as Response);
      }
      if (
        url.includes('/api/matches/match-a/identity')
        && !url.includes('/repair')
        && !url.includes('/promote')
        && (!init?.method || init.method === 'GET')
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            reset: false,
            silentlyReconnected: false,
            cutCount: 0,
            identityContinuous: false,
            reasonCodes: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/events/partition') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            acceptedViews: [],
            retainedCandidates: [{ type: 'turnover', reviewStatus: 'rejected' }],
            rejectedRemovedFromAcceptedViews: true,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/players') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            intervalLimited: true,
            totalsWithheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ recorded: true, missing: ['x', 'y'], imputedAsCalibrated: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/quality')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics/inspect/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
            decision: null,
            validatedMeasurement: false,
            reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ mode: 'unknown', reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/promotion') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            completeMatchAccepted: false,
            stageBenchmarkIsCompleteMatchAcceptance: false,
            outputQuality: 'unproven',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ namespace: 'production', compatibleWithDevelopment: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/privacy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ undoable: true, rewrotePastOutcomes: false, items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: true, reasonCodes: [], missingEvidenceIds: [] }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/coverage') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ coverageAware: true, representsWholeMatch: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/setup') && !url.includes('/preview') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
            exportFpsEqualsInferenceFps: false,
            notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/attack-direction')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('left_to_right'))
    ))).toBe(false);
    const direction = within(await screen.findByRole('region', { name: /stored attack direction/i }));
    expect(direction.getByText(/from match config/i)).toBeTruthy();
    expect(direction.getByText(/fromStoredConfig is true/i)).toBeTruthy();
    expect(direction.getByText(/client mapping is ignored/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored legacy record migration without inventing known possession', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/records/migrate')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            migrated: { possession_pct: { availability: 'unknown' } },
            rollback: { possession: null, myTeamDistance: null },
            rewrotePastOutcomes: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/attack-direction')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            direction: 'right_to_left',
            fromStoredConfig: true,
            team: 'my_team',
            period: 1,
          }),
        } as Response);
      }
      if (
        url.includes('/api/matches/match-a/identity')
        && !url.includes('/repair')
        && !url.includes('/promote')
        && (!init?.method || init.method === 'GET')
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            reset: false,
            silentlyReconnected: false,
            cutCount: 0,
            identityContinuous: false,
            reasonCodes: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/events/partition') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            acceptedViews: [],
            retainedCandidates: [{ type: 'turnover', reviewStatus: 'rejected' }],
            rejectedRemovedFromAcceptedViews: true,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/players') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            intervalLimited: true,
            totalsWithheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ recorded: true, missing: ['x', 'y'], imputedAsCalibrated: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/quality')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics/inspect/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
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
          json: async () => ({
            decision: null,
            validatedMeasurement: false,
            reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ mode: 'unknown', reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/promotion') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            completeMatchAccepted: false,
            stageBenchmarkIsCompleteMatchAcceptance: false,
            outputQuality: 'unproven',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ namespace: 'production', compatibleWithDevelopment: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            assignment: { kind: 'tracklet', forced: false, rosterId: null },
            chunk: { silentlyReconnected: false },
            silentlyReconnected: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/privacy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ undoable: true, rewrotePastOutcomes: false, items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: true, reasonCodes: [], missingEvidenceIds: [] }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            measured: false,
            analystCompletedReviewedMatch: false,
            reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/coverage') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ coverageAware: true, representsWholeMatch: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/setup') && !url.includes('/preview') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
            exportFpsEqualsInferenceFps: false,
            notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/records/migrate')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('"possession":61'))
    ))).toBe(false);
    const records = within(await screen.findByRole('region', { name: /legacy records/i }));
    expect(records.getByText(/without inventing known possession/i)).toBeTruthy();
    expect(records.getByText(/rollback possession is null/i)).toBeTruthy();
    expect(records.getByText(/rewrotePastOutcomes is false/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored match export downloads without leftover soccertrack or whole-match certification', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/export/match.json') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            schemaVersion: 'match_bundle_v1',
            provenance: { storageArtifactsAreSourceOfTruth: true, llmGenerated: false },
            exports: {
              matchJson: '/api/matches/match-a/export/match.json',
              framesCsv: '/api/matches/match-a/export/frames.csv',
              eventsCsv: '/api/matches/match-a/export/events.csv',
              metricsCsv: '/api/matches/match-a/export/metrics.csv',
            },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/records/migrate')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            migrated: { possession_pct: { availability: 'unknown' } },
            rollback: { possession: null, myTeamDistance: null },
            rewrotePastOutcomes: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/attack-direction')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ direction: 'right_to_left', fromStoredConfig: true }),
        } as Response);
      }
      if (
        url.includes('/api/matches/match-a/identity')
        && !url.includes('/repair')
        && !url.includes('/promote')
        && (!init?.method || init.method === 'GET')
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ silentlyReconnected: false, cutCount: 0, identityContinuous: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/events/partition') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ rejectedRemovedFromAcceptedViews: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/players') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ intervalLimited: true, totalsWithheld: true, reasonCodes: ['IDENTITY_DISCONTINUITY'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ recorded: true, missing: ['x'], imputedAsCalibrated: false }) } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/quality')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ publishedLabel: 'experimental_shot_quality', calibratedXg: false, items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics/inspect/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ metrics: [{ metric: 'my_team_distance_m', availability: 'unknown', value: null, reasonCodes: ['IDENTITY_DISCONTINUITY'] }] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/package') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ level: 0, decision: null, validatedMeasurement: false, reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/geometry') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ decision: null, validatedMeasurement: false, reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ mode: 'unknown', reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/promotion') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ completeMatchAccepted: false, stageBenchmarkIsCompleteMatchAcceptance: false, outputQuality: 'unproven' }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ namespace: 'production', compatibleWithDevelopment: false }) } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ assignment: { kind: 'tracklet', forced: false }, silentlyReconnected: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/privacy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ cloudAllowed: false, localProcessingRequired: true, faceRecognition: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/history') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ undoable: true, rewrotePastOutcomes: false, items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance')) {
        return Promise.resolve({ ok: true, json: async () => ({ accepted: true, reasonCodes: [], missingEvidenceIds: [] }) } as Response);
      }
      if (url.includes('/api/evaluation/workflow')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ measured: false, analystCompletedReviewedMatch: false, reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/coverage') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ coverageAware: true, representsWholeMatch: false }) } as Response);
      }
      if (url.includes('/api/matches/match-a/setup') && !url.includes('/preview') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ certified: false, automationAdmitted: false, manualTaggingPermitted: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/rates') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ exportFpsEqualsInferenceFps: false, notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            replacesOriginal: false,
            originalRetained: true,
            assets: { proxy: { kind: 'browsing_proxy' }, thumbnails: { kind: 'thumbnails' }, waveform: { kind: 'waveform' } },
            ptsMap: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/export/match.json')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/external/soccertrack'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/matches/match-a/export/')
      && init?.method === 'POST'
    ))).toBe(false);
    const exported = within(await screen.findByRole('region', { name: /match export/i }));
    expect(exported.getByRole('link', { name: /frames.csv/i }).getAttribute('href')).toBe('/api/matches/match-a/export/frames.csv');
    expect(exported.getByRole('link', { name: /events.csv/i }).getAttribute('href')).toBe('/api/matches/match-a/export/events.csv');
    expect(exported.getByRole('link', { name: /metrics.csv/i }).getAttribute('href')).toBe('/api/matches/match-a/export/metrics.csv');
    expect(exported.getByRole('link', { name: /match.json/i }).getAttribute('href')).toBe('/api/matches/match-a/export/match.json');
    expect(exported.getByText(/match_bundle_v1/i)).toBeTruthy();
    expect(exported.getByText(/source-linked downloads/i)).toBeTruthy();
    expect(exported.getByText(/not a whole-match certification/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored tactical themes without treating them as proof of weakness', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/themes') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            matchId: 'match-a',
            detectedThemes: ['high_press'],
            themeDetails: { high_press: 40 },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/export/match.json') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            schemaVersion: 'match_bundle_v1',
            provenance: { storageArtifactsAreSourceOfTruth: true, llmGenerated: false },
            exports: {
              matchJson: '/api/matches/match-a/export/match.json',
              framesCsv: '/api/matches/match-a/export/frames.csv',
              eventsCsv: '/api/matches/match-a/export/events.csv',
              metricsCsv: '/api/matches/match-a/export/metrics.csv',
            },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/records/migrate')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            migrated: { possession_pct: { availability: 'unknown' } },
            rollback: { possession: null, myTeamDistance: null },
            rewrotePastOutcomes: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/attack-direction')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ direction: 'right_to_left', fromStoredConfig: true }),
        } as Response);
      }
      if (
        url.includes('/api/matches/match-a/identity')
        && !url.includes('/repair')
        && !url.includes('/promote')
        && (!init?.method || init.method === 'GET')
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ silentlyReconnected: false, cutCount: 0, identityContinuous: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/events/partition') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ rejectedRemovedFromAcceptedViews: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/players') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ intervalLimited: true, totalsWithheld: true, reasonCodes: ['IDENTITY_DISCONTINUITY'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ recorded: true, missing: ['x'], imputedAsCalibrated: false }) } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/quality')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ publishedLabel: 'experimental_shot_quality', calibratedXg: false, items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics/inspect/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ metrics: [{ metric: 'my_team_distance_m', availability: 'unknown', value: null, reasonCodes: ['IDENTITY_DISCONTINUITY'] }] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/package') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ level: 0, decision: null, validatedMeasurement: false, reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/geometry') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ decision: null, validatedMeasurement: false, reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ mode: 'unknown', reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/promotion') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ completeMatchAccepted: false, stageBenchmarkIsCompleteMatchAcceptance: false, outputQuality: 'unproven' }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ namespace: 'production', compatibleWithDevelopment: false }) } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ assignment: { kind: 'tracklet', forced: false }, silentlyReconnected: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/privacy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ cloudAllowed: false, localProcessingRequired: true, faceRecognition: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/history') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ undoable: true, rewrotePastOutcomes: false, items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance')) {
        return Promise.resolve({ ok: true, json: async () => ({ accepted: true, reasonCodes: [], missingEvidenceIds: [] }) } as Response);
      }
      if (url.includes('/api/evaluation/workflow')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ measured: false, analystCompletedReviewedMatch: false, reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/coverage') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ coverageAware: true, representsWholeMatch: false }) } as Response);
      }
      if (url.includes('/api/matches/match-a/setup') && !url.includes('/preview') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ certified: false, automationAdmitted: false, manualTaggingPermitted: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/rates') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ exportFpsEqualsInferenceFps: false, notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            replacesOriginal: false,
            originalRetained: true,
            assets: { proxy: { kind: 'browsing_proxy' }, thumbnails: { kind: 'thumbnails' }, waveform: { kind: 'waveform' } },
            ptsMap: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/themes')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/search/tactical-themes'))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('"detectedThemes"'))
    ))).toBe(false);
    const themes = within(await screen.findByRole('region', { name: /tactical themes/i }));
    expect(themes.getByText(/heuristic search tags/i)).toBeTruthy();
    expect(themes.getByText(/do not prove tactical weakness/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored assistance fallback as the template route without client-injected rows', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/assistance/fallback') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            route: 'template',
            reasonCodes: ['PROVIDER_DISABLED'],
            reviewOperational: true,
            output: { kind: 'deterministic_template' },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/themes') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ matchId: 'match-a', detectedThemes: ['high_press'], themeDetails: { high_press: 40 } }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/export/match.json') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            schemaVersion: 'match_bundle_v1',
            exports: {
              matchJson: '/api/matches/match-a/export/match.json',
              framesCsv: '/api/matches/match-a/export/frames.csv',
              eventsCsv: '/api/matches/match-a/export/events.csv',
              metricsCsv: '/api/matches/match-a/export/metrics.csv',
            },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/records/migrate')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            migrated: { possession_pct: { availability: 'unknown' } },
            rollback: { possession: null },
            rewrotePastOutcomes: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/attack-direction')) {
        return Promise.resolve({ ok: true, json: async () => ({ direction: 'right_to_left', fromStoredConfig: true }) } as Response);
      }
      if (
        url.includes('/api/matches/match-a/identity')
        && !url.includes('/repair')
        && !url.includes('/promote')
        && (!init?.method || init.method === 'GET')
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ silentlyReconnected: false, cutCount: 0, identityContinuous: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/events/partition') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ rejectedRemovedFromAcceptedViews: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/players') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ intervalLimited: true, totalsWithheld: true, reasonCodes: ['IDENTITY_DISCONTINUITY'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ recorded: true, missing: ['x'], imputedAsCalibrated: false }) } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/quality')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ publishedLabel: 'experimental_shot_quality', calibratedXg: false, items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics/inspect/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ metrics: [{ metric: 'my_team_distance_m', availability: 'unknown', value: null, reasonCodes: ['IDENTITY_DISCONTINUITY'] }] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/package') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ level: 0, decision: null, validatedMeasurement: false, reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/geometry') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ decision: null, validatedMeasurement: false, reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ mode: 'unknown', reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/promotion') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ completeMatchAccepted: false, stageBenchmarkIsCompleteMatchAcceptance: false, outputQuality: 'unproven' }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ namespace: 'production', compatibleWithDevelopment: false }) } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ assignment: { kind: 'tracklet', forced: false }, silentlyReconnected: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/privacy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ cloudAllowed: false, localProcessingRequired: true, faceRecognition: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/history') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ undoable: true, rewrotePastOutcomes: false, items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance')) {
        return Promise.resolve({ ok: true, json: async () => ({ accepted: true, reasonCodes: [], missingEvidenceIds: [] }) } as Response);
      }
      if (url.includes('/api/evaluation/workflow')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ measured: false, analystCompletedReviewedMatch: false, reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/coverage') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ coverageAware: true, representsWholeMatch: false }) } as Response);
      }
      if (url.includes('/api/matches/match-a/setup') && !url.includes('/preview') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ certified: false, automationAdmitted: false, manualTaggingPermitted: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/rates') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ exportFpsEqualsInferenceFps: false, notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            replacesOriginal: false,
            originalRetained: true,
            assets: { proxy: { kind: 'browsing_proxy' }, thumbnails: { kind: 'thumbnails' }, waveform: { kind: 'waveform' } },
            ptsMap: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url === '/api/assistance' || url.endsWith('/api/assistance')) {
        return Promise.resolve({ ok: true, json: async () => ({ providersEnabled: false }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/assistance/fallback')
        && init?.method === 'POST'
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('forged'))
    ))).toBe(false);
    const fallback = within(await screen.findByRole('region', { name: /assistance fallback/i }));
    expect(fallback.getByText(/template route/i)).toBeTruthy();
    expect(fallback.getByText(/PROVIDER_DISABLED/)).toBeTruthy();
    expect(fallback.getByText(/review remains operational/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('loads stored match calibration without inventing acceptance from four homography points', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            identityContinuous: false,
            wholeMatch: false,
            intervalLimited: true,
            withheld: true,
            reasonCodes: ['IDENTITY_DISCONTINUITY'],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/calibration') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            fromStoredPoints: true,
            measured: false,
            evaluation: { accepted: false },
            residualP95M: null,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/assistance/fallback') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            route: 'template',
            reasonCodes: ['PROVIDER_DISABLED'],
            reviewOperational: true,
            output: { kind: 'deterministic_template' },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/themes') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ matchId: 'match-a', detectedThemes: ['high_press'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/export/match.json') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            schemaVersion: 'match_bundle_v1',
            exports: {
              matchJson: '/api/matches/match-a/export/match.json',
              framesCsv: '/api/matches/match-a/export/frames.csv',
              eventsCsv: '/api/matches/match-a/export/events.csv',
              metricsCsv: '/api/matches/match-a/export/metrics.csv',
            },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/records/migrate')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            migrated: { possession_pct: { availability: 'unknown' } },
            rollback: { possession: null },
            rewrotePastOutcomes: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/attack-direction')) {
        return Promise.resolve({ ok: true, json: async () => ({ direction: 'right_to_left', fromStoredConfig: true }) } as Response);
      }
      if (
        url.includes('/api/matches/match-a/identity')
        && !url.includes('/repair')
        && !url.includes('/promote')
        && (!init?.method || init.method === 'GET')
      ) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ silentlyReconnected: false, cutCount: 0, identityContinuous: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/events/partition') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ rejectedRemovedFromAcceptedViews: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/players') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ intervalLimited: true, totalsWithheld: true, reasonCodes: ['IDENTITY_DISCONTINUITY'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/features') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ recorded: true, missing: ['x'], imputedAsCalibrated: false }) } as Response);
      }
      if (url.includes('/api/matches/match-a/shots/quality')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ publishedLabel: 'experimental_shot_quality', calibratedXg: false, items: [] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/metrics/inspect/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({ metrics: [{ metric: 'my_team_distance_m', availability: 'unknown', value: null, reasonCodes: ['IDENTITY_DISCONTINUITY'] }] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/package') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ level: 0, decision: null, validatedMeasurement: false, reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/incidents/geometry') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ decision: null, validatedMeasurement: false, reasonCodes: ['IFAB_LAW_11_NOT_APPLIED'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/ownership') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ mode: 'unknown', reasonCodes: ['NEAREST_PLAYER_INSUFFICIENT'] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/promotion') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ completeMatchAccepted: false, stageBenchmarkIsCompleteMatchAcceptance: false, outputQuality: 'unproven' }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/cache') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ namespace: 'production', compatibleWithDevelopment: false }) } as Response);
      }
      if (url.includes('/api/matches/match-a/tracklets') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ assignment: { kind: 'tracklet', forced: false }, silentlyReconnected: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/privacy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ cloudAllowed: false, localProcessingRequired: true, faceRecognition: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/history') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ undoable: true, rewrotePastOutcomes: false, items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance')) {
        return Promise.resolve({ ok: true, json: async () => ({ accepted: true, reasonCodes: [], missingEvidenceIds: [] }) } as Response);
      }
      if (url.includes('/api/evaluation/workflow')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ measured: false, analystCompletedReviewedMatch: false, reasonCodes: ['ANALYST_ACCEPTANCE_MISSING'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/coverage') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ coverageAware: true, representsWholeMatch: false }) } as Response);
      }
      if (url.includes('/api/matches/match-a/setup') && !url.includes('/preview') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ certified: false, automationAdmitted: false, manualTaggingPermitted: true }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/rates') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ exportFpsEqualsInferenceFps: false, notes: ['EXPORT_FPS_IS_NOT_INFERENCE_FPS'] }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/package') && !url.includes('/incidents/') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            analyst: { limitations: ['Independent labels 0/18 complete.'] },
            operator: { manifest: { schema: 'match_package_v1' }, secretsAdmitted: true },
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/clock') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ presentationTimeSeconds: 0, matchClockSeconds: 0, frameAccurateOverlay: false }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/media/proxy') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            replacesOriginal: false,
            originalRetained: true,
            assets: { proxy: { kind: 'browsing_proxy' }, thumbnails: { kind: 'thumbnails' }, waveform: { kind: 'waveform' } },
            ptsMap: [],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/edits') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ reencodeFullMatch: false, renderOnDemand: true }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && url.includes('state=pending') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      if (url === '/api/assistance' || url.endsWith('/api/assistance')) {
        return Promise.resolve({ ok: true, json: async () => ({ providersEnabled: false }) } as Response);
      }
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url, init]) => (
        String(url).includes('/api/matches/match-a/calibration')
        && (!init?.method || init.method === 'GET')
      ))).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/matches/match-a/calibration')
      && init?.method === 'POST'
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/geometry/preview'))).toBe(false);
    const calibration = within(await screen.findByRole('region', { name: /stored calibration/i }));
    expect(calibration.getByText(/four homography points do not make calibration accepted/i)).toBeTruthy();
    expect(calibration.getByText(/unmeasured/i)).toBeTruthy();
    expect(calibration.getByText(/fromStoredPoints is true/i)).toBeTruthy();
    expect(api.fetchMatchWorkspace).toHaveBeenCalledTimes(1);
  });

  it('swaps stored teams on the loaded match without a vision rerun', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
            correctionId: 'swap-1',
            saveState: 'saved',
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
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes('/api/matches/match-a/heatmap')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
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
          json: async () => ({
            correctionId: 'undo-1',
            saveState: 'saved',
            undoOf: 'swap-1',
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/corrections') && init?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            correctionId: 'swap-1',
            saveState: 'saved',
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
    await waitFor(() => expect(api.updateMatchConfig).toHaveBeenCalledWith('match-a', { myTeamCluster: 1 }));
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
    vi.stubGlobal('fetch', vi.fn((_url: string, init: RequestInit) => new Promise<Response>((_resolve, reject) => {
      const signal = init.signal as AbortSignal;
      requests.push({ signal, reject });
      signal.addEventListener('abort', () => reject(new Error('Cancelled')), { once: true });
    })));

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
    expect(requests).toHaveLength(6);

    await act(async () => requests[0].reject(new Error('Workspace unavailable')));

    expect(screen.getAllByText('Workspace unavailable').length).toBeGreaterThan(0);
    expect(input.disabled).toBe(false);
    expect(requests.slice(1).map(({ signal }) => signal.aborted)).toEqual([true, true, true, true, true]);
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
      id: 'match-review',
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
    fireEvent.click(screen.getByRole('button', { name: 'Run Check' }));

    await waitFor(() => expect(api.runMatchAnalysis).toHaveBeenCalledWith(
      'match-review',
      'offside',
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
    fireEvent.click(screen.getByRole('button', { name: 'Run Check' }));

    await waitFor(() => expect(api.runMatchAnalysis).toHaveBeenCalledWith(
      'match-review',
      'offside',
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
    fireEvent.click(screen.getByRole('button', { name: 'Run Check' }));

    await waitFor(() => expect(api.runMatchAnalysis).toHaveBeenCalledWith(
      'match-review',
      'offside',
      'local',
      0,
    ));
    expect(api.runMatchAnalysis).not.toHaveBeenCalledWith(
      'match-review',
      'offside',
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
    fireEvent.click(screen.getByRole('button', { name: 'Run Check' }));

    await waitFor(() => expect(api.runMatchAnalysis).toHaveBeenCalledWith(
      'match-review',
      'offside',
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
