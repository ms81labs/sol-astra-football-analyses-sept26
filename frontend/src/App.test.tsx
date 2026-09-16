import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
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
  myTeamAvgPos: { x: 50, y: 50 },
  enemyAvgPos: { x: 50, y: 50 },
  myTeamTopSpeed: null,
  enemyTopSpeed: null,
  myTeamSprints: null,
  enemySprints: null,
  myTeamXg: 0,
  enemyXg: 0,
  myTeamDefensiveLineHeight: 0,
  enemyDefensiveLineHeight: 0,
  myTeamDefensiveTeamLength: 0,
  enemyDefensiveTeamLength: 0,
  myTeamPpda: null,
  enemyPpda: null,
  myTeamHighPressRegains: 0,
  enemyHighPressRegains: 0,
  myTeamCounterpressRecoverySeconds: 0,
  enemyCounterpressRecoverySeconds: 0,
  formation: '-',
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
  });

  it('loads heatmap availability from production HTTP and ignores claimed identity continuity', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue(loadedWorkspace('match-a', 'Match A'));
    const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
      void init;
      const url = String(input);
      if (url.includes('/api/heatmap')) {
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
      expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/api/heatmap'))).toBe(true);
    });
    const heatmapCall = fetchMock.mock.calls.find(([input]) => String(input).includes('/api/heatmap'));
    expect(heatmapCall?.[1]?.method).toBe('POST');
    expect(heatmapCall?.[1]?.body).toContain('identityContinuous');
    expect(screen.getByText(/whole-match heatmap withheld until identity continuity/i)).toBeTruthy();
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
