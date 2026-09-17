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
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/matches/match-a/calibration'))).toBe(true);
    });
    const calibrationCall = fetchMock.mock.calls.find(([url]) => String(url).includes('/api/matches/match-a/calibration'));
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
      if (url.includes('/api/evaluation/workflow') && (!init?.method || init.method === 'GET')) {
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
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/evaluation/workflow')
      && init?.method === 'POST'
    ))).toBe(false);
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
      if (url.includes('/api/matches/match-a/reports/provenance') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: true,
            reasonCodes: [],
            missingEvidenceIds: [],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && (!init?.method || init.method === 'GET')) {
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
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/matches/match-a/reports/provenance')
      && init?.method === 'POST'
    ))).toBe(false);
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
      if (url.includes('/api/matches/match-a/shots/quality') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: true,
            reasonCodes: [],
            missingEvidenceIds: [],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && (!init?.method || init.method === 'GET')) {
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
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/matches/match-a/shots/quality')
      && init?.method === 'POST'
    ))).toBe(false);
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
      if (url.includes('/api/matches/match-a/shots/quality') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: true,
            reasonCodes: [],
            missingEvidenceIds: [],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && (!init?.method || init.method === 'GET')) {
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
      if (url.includes('/api/matches/match-a/shots/quality') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: true,
            reasonCodes: [],
            missingEvidenceIds: [],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && (!init?.method || init.method === 'GET')) {
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
      if (url.includes('/api/matches/match-a/shots/quality') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: true,
            reasonCodes: [],
            missingEvidenceIds: [],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && (!init?.method || init.method === 'GET')) {
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
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/matches/match-a/tracklets')
      && init?.method === 'POST'
    ))).toBe(false);
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
      if (url.includes('/api/matches/match-a/shots/quality') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: true,
            reasonCodes: [],
            missingEvidenceIds: [],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && (!init?.method || init.method === 'GET')) {
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
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/matches/match-a/cache')
      && init?.method === 'POST'
    ))).toBe(false);
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
      if (url.includes('/api/matches/match-a/shots/quality') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: true,
            reasonCodes: [],
            missingEvidenceIds: [],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && (!init?.method || init.method === 'GET')) {
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
      if (url.includes('/api/matches/match-a/shots/quality') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: true,
            reasonCodes: [],
            missingEvidenceIds: [],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && (!init?.method || init.method === 'GET')) {
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
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/matches/match-a/ownership')
      && init?.method === 'POST'
    ))).toBe(false);
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
      if (url.includes('/api/matches/match-a/shots/quality') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: true,
            reasonCodes: [],
            missingEvidenceIds: [],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && (!init?.method || init.method === 'GET')) {
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
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/matches/match-a/incidents/geometry')
      && init?.method === 'POST'
    ))).toBe(false);
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
      if (url.includes('/api/matches/match-a/shots/quality') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: true,
            reasonCodes: [],
            missingEvidenceIds: [],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && (!init?.method || init.method === 'GET')) {
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
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/matches/match-a/incidents/package')
      && init?.method === 'POST'
    ))).toBe(false);
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
      if (url.includes('/api/matches/match-a/shots/quality') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            publishedLabel: 'experimental_shot_quality',
            calibratedXg: false,
            items: [{ publishedLabel: 'experimental_shot_quality', availability: 'experimental', reasonCodes: ['EXPERIMENTAL_NOT_CALIBRATED_XG'] }],
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/reports/provenance') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: true,
            reasonCodes: [],
            missingEvidenceIds: [],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && (!init?.method || init.method === 'GET')) {
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
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/matches/match-a/metrics')
      && !String(url).includes('/inspect')
      && init?.method === 'POST'
    ))).toBe(false);
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
      if (url.includes('/api/matches/match-a/shots/quality') && (!init?.method || init.method === 'GET')) {
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
      if (url.includes('/api/matches/match-a/reports/provenance') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            accepted: true,
            reasonCodes: [],
            missingEvidenceIds: [],
          }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && (!init?.method || init.method === 'GET')) {
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
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/matches/match-a/shots/features')
      && init?.method === 'POST'
    ))).toBe(false);
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
      if (url.includes('/api/matches/match-a/shots/quality') && (!init?.method || init.method === 'GET')) {
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
      if (url.includes('/api/matches/match-a/reports/provenance') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: true, reasonCodes: [], missingEvidenceIds: [] }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && (!init?.method || init.method === 'GET')) {
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
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/matches/match-a/players')
      && init?.method === 'POST'
    ))).toBe(false);
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
      if (url.includes('/api/matches/match-a/shots/quality') && (!init?.method || init.method === 'GET')) {
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
      if (url.includes('/api/matches/match-a/reports/provenance') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: true, reasonCodes: [], missingEvidenceIds: [] }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && (!init?.method || init.method === 'GET')) {
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
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/matches/match-a/events/partition')
      && init?.method === 'POST'
    ))).toBe(false);
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
      if (url.includes('/api/matches/match-a/shots/quality') && (!init?.method || init.method === 'GET')) {
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
      if (url.includes('/api/matches/match-a/reports/provenance') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: true, reasonCodes: [], missingEvidenceIds: [] }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && (!init?.method || init.method === 'GET')) {
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
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/matches/match-a/identity')
      && !String(url).includes('/repair')
      && !String(url).includes('/promote')
      && init?.method === 'POST'
    ))).toBe(false);
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
      if (url.includes('/api/matches/match-a/attack-direction') && (!init?.method || init.method === 'GET')) {
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
      if (url.includes('/api/matches/match-a/shots/quality') && (!init?.method || init.method === 'GET')) {
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
      if (url.includes('/api/matches/match-a/reports/provenance') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: true, reasonCodes: [], missingEvidenceIds: [] }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && (!init?.method || init.method === 'GET')) {
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
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/matches/match-a/attack-direction')
      && init?.method === 'POST'
    ))).toBe(false);
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
      if (url.includes('/api/matches/match-a/records/migrate') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            migrated: { possession_pct: { availability: 'unknown' } },
            rollback: { possession: null, myTeamDistance: null },
            rewrotePastOutcomes: false,
          }),
        } as Response);
      }
      if (url.includes('/api/matches/match-a/attack-direction') && (!init?.method || init.method === 'GET')) {
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
      if (url.includes('/api/matches/match-a/shots/quality') && (!init?.method || init.method === 'GET')) {
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
      if (url.includes('/api/matches/match-a/reports/provenance') && (!init?.method || init.method === 'GET')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ accepted: true, reasonCodes: [], missingEvidenceIds: [] }),
        } as Response);
      }
      if (url.includes('/api/evaluation/workflow') && (!init?.method || init.method === 'GET')) {
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
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).includes('/api/matches/match-a/records/migrate')
      && init?.method === 'POST'
    ))).toBe(false);
    expect(fetchMock.mock.calls.some(([, init]) => (
      Boolean(init?.body && String(init.body).includes('"possession":61'))
    ))).toBe(false);
    const records = within(await screen.findByRole('region', { name: /legacy records/i }));
    expect(records.getByText(/without inventing known possession/i)).toBeTruthy();
    expect(records.getByText(/rollback possession is null/i)).toBeTruthy();
    expect(records.getByText(/rewrotePastOutcomes is false/i)).toBeTruthy();
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
