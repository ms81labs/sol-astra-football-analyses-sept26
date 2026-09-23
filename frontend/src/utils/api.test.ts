import { afterEach, describe, expect, it, vi } from 'vitest';

import type { ProcessingJob } from '../types';
import {
  buildMatchReportExportUrl,
  buildMatchVideoUrl,
  createMatchUpload,
  fetchMatchEvidence,
  fetchMatchWorkspace,
  fetchTrustCrops,
  mapBackendEventsToTags,
  updateMatchConfig,
  waitForJobCompletion,
} from './api';

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

function okJob(status: string, progress: number, message: string): Response {
  return {
    ok: true,
    json: async () => ({ id: 'job-1', matchId: 'match-1', status, progress, message }),
  } as Response;
}

describe('waitForJobCompletion', () => {
  it('reports intermediate jobs and waits two seconds between requests', async () => {
    vi.useFakeTimers();
    const updates: ProcessingJob[] = [];
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(okJob('queued', 0, 'Queued'))
      .mockResolvedValueOnce(okJob('processing', 0.5, 'Tracking players'))
      .mockResolvedValueOnce(okJob('completed', 1, 'Complete')));

    const completion = waitForJobCompletion('job-1', undefined, 60_000, undefined, (job) => updates.push(job));

    expect(fetch).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1_999);
    expect(fetch).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(fetch).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(1_999);
    expect(fetch).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(1);

    await expect(completion).resolves.toMatchObject({ status: 'completed' });
    expect(updates.map((job) => job.status)).toEqual(['queued', 'processing', 'completed']);
    expect(fetch).toHaveBeenCalledTimes(3);
  });

  it('cancels an in-flight job request immediately', async () => {
    const controller = new AbortController();
    vi.stubGlobal('fetch', vi.fn((_url: string, init?: RequestInit) => new Promise<Response>((resolve) => {
      (init?.signal as AbortSignal | undefined)?.addEventListener(
        'abort',
        () => resolve(okJob('completed', 1, 'Complete')),
        { once: true },
      );
    })));

    const updates: ProcessingJob[] = [];
    const completion = waitForJobCompletion('job-1', undefined, 60_000, controller.signal, (job) => updates.push(job));
    controller.abort();

    await expect(completion).rejects.toThrow('Job polling was cancelled.');
    expect(updates).toEqual([]);
  });

  it('cancels while waiting for the next job request', async () => {
    vi.useFakeTimers();
    const controller = new AbortController();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okJob('queued', 0, 'Queued')));

    const completion = waitForJobCompletion('job-1', undefined, 60_000, controller.signal);
    let failure: string | undefined;
    void completion.catch((error: Error) => {
      failure = error.message;
    });
    await vi.advanceTimersByTimeAsync(0);

    try {
      controller.abort();
      await Promise.resolve();
      await Promise.resolve();

      expect(failure).toBe('Job polling was cancelled.');
      expect(vi.getTimerCount()).toBe(0);
    } finally {
      await vi.advanceTimersByTimeAsync(2_000);
      await completion.catch(() => undefined);
    }
  });

  it('times out at the exact job polling deadline', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(0));
    const controller = new AbortController();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okJob('queued', 0, 'Queued')));

    const completion = waitForJobCompletion('job-1', 100, 100, controller.signal);
    let failure: string | undefined;
    void completion.catch((error: Error) => {
      failure = error.message;
    });

    try {
      await vi.advanceTimersByTimeAsync(100);

      expect(fetch).toHaveBeenCalledTimes(1);
      expect(failure).toBe('Timed out waiting for job to complete.');
    } finally {
      controller.abort();
      await vi.advanceTimersByTimeAsync(100);
      await completion.catch(() => undefined);
    }
  });
});


describe('fetchTrustCrops', () => {
  it('rejects a response from a different generation', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        matchId: 'match-1', generationId: 'gen-1', ballTeleportGeometryAvailable: true,
        ballTeleportReasonCodes: [], totalFrames: 0, crops: [],
      }),
    }));

    await expect(fetchTrustCrops('match-1', 20, 'gen-2')).rejects.toMatchObject({
      status: 409,
      code: 'GENERATION_RESPONSE_MISMATCH',
    });
  });

  it('preserves structured generation errors from the backend', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({ error: 'GENERATION_RECOVERY_REQUIRED', message: 'Recovery required.' }),
    }));

    await expect(fetchTrustCrops('match-1', 20, 'gen-2')).rejects.toMatchObject({
      status: 503,
      code: 'GENERATION_RECOVERY_REQUIRED',
      message: 'Recovery required.',
    });
  });
});

describe('createMatchUpload', () => {
  it('posts a multipart payload with serialized config', async () => {
    const controller = new AbortController();
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ matchId: 'match-1', jobId: 'job-1', status: 'queued' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const file = new File(['[]'], 'sample_tracking.json', { type: 'application/json' });
    const response = await createMatchUpload({
      name: 'Sample Match',
      inputMode: 'tracking_json',
      file,
      config: {
        attackDirection: 'right_to_left',
        manualHomographyPoints: [
          { x: 0, y: 0 },
          { x: 100, y: 0 },
          { x: 100, y: 100 },
          { x: 0, y: 100 },
        ],
      },
      signal: controller.signal,
    });

    expect(response.matchId).toBe('match-1');
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe('/api/matches');
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe('POST');
    expect(init.signal).toBe(controller.signal);
    controller.abort();
    expect(init.signal?.aborted).toBe(true);
    const formData = init.body as FormData;
    expect(formData.get('name')).toBe('Sample Match');
    expect(formData.get('inputMode')).toBe('tracking_json');
    expect(formData.get('config')).toContain('"attackDirection":"right_to_left"');
  });
});

describe('fetchMatchWorkspace', () => {
  it('loads match detail, frames, analytics, and events in one call', async () => {
    const controller = new AbortController();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ generationId: 'g1', id: 'match-1', name: 'Sample Match', status: 'ready', inputMode: 'tracking_json' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ generationId: 'g1',
          matchId: 'match-1',
          frames: [
            {
              frameId: 0,
              timestamp: 0,
              ball: { x: 50, y: 50, confidence: 0.9 },
              myTeam: [{ id: 7, x: 48, y: 50, confidence: 0.9 }],
              enemies: [{ id: 18, x: 60, y: 50, confidence: 0.9 }],
              possession: { frameId: 0, timestamp: 0, team: 'my_team', trackId: 7, distance: 2 },
            },
          ],
          nextCursor: '240',
          frameCount: 27000,
          intervalEndpoint: 'half_open',
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ generationId: 'g1',
          matchId: 'match-1',
          summary: {
            possession: 67,
            myTeamDistance: 20,
            enemyDistance: 18,
            myTeamAvgPos: { x: 48, y: 50 },
            enemyAvgPos: { x: 60, y: 50 },
            myTeamTopSpeed: 20.1,
            enemyTopSpeed: 18.4,
            myTeamSprints: 0,
            enemySprints: 0,
            myTeamXg: 0.42,
            enemyXg: 0.11,
            myTeamDefensiveLineHeight: 21,
            enemyDefensiveLineHeight: 27,
            myTeamDefensiveTeamLength: 37,
            enemyDefensiveTeamLength: 41,
            myTeamPpda: 1.8,
            enemyPpda: 7.2,
            myTeamHighPressRegains: 4,
            enemyHighPressRegains: 1,
            myTeamCounterpressRecoverySeconds: 3.4,
            enemyCounterpressRecoverySeconds: 5.8,
            formation: '-',
          },
          formationTimeline: [
            {
              formation: '4-4-2',
              startFrameId: 0,
              endFrameId: 12,
              startTimestamp: 0,
              endTimestamp: 2.4,
            },
          ],
          shots: [
            {
              frameId: 2,
              timestamp: 0.4,
              team: 'my_team',
              playerId: 9,
              x: 91,
              y: 50,
              inBox: true,
              xg: 0.42,
              distanceToGoal: 9.5,
              angleDegrees: 32.1,
            },
          ],
          ballAssignments: [],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ generationId: 'g1',
          matchId: 'match-1',
          events: [{ type: 'turnover', frameId: 1, timestamp: 0.2, team: 'enemy', description: 'Possession changed' }],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ generationId: 'g1',
          matchId: 'match-1',
          jobId: 'job-1',
          inputMode: 'tracking_json',
          matchStatus: 'ready',
          jobStatus: 'completed',
          requiresTeamSelection: false,
          rawRowCount: 3,
          frameCount: 1,
          playerFrames: 1,
          withBallFrames: 1,
          withBallRatio: 1,
          trackedPossessionFrames: 1,
          trackedPossessionRatio: 1,
          controlledPossessionFrames: 1,
          controlledPossessionRatio: 1,
          eventCount: 1,
          eventTypes: { turnover: 1 },
          eventFamilyCount: 1,
          dominantEventShare: 1,
          shotCount: 1,
          ballSignalStatus: 'trusted',
          ballTrackPathLength: 0,
          ballTrackEdgeFrameShare: 0,
          ballTrackShowsMeaningfulMotion: false,
          ballTrackViable: false,
          fiveMinuteTruthReady: false,
          fortyFiveMinuteTruthReady: false,
          truthGateReasons: ['Need at least 3 event families'],
          artifactPresence: { frames: true, analytics: true, events: true, rawRows: true },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ generationId: 'g1',
          matchId: 'match-1',
          items: [
            {
              evidenceId: 'frame:0',
              schemaVersion: 'evidence_v1',
              observationSource: 'observed',
              reviewStatus: 'unreviewed',
              intervalStart: 0,
              intervalEnd: 0.2,
              payload: { kind: 'frame', coordinateSpace: 'pitch', definitionVersion: '1' },
            },
          ],
          nextCursor: null,
          intervalEndpoint: 'half_open',
          coordinateSpace: 'pitch',
          definitionVersion: '1',
        }),
      });
    vi.stubGlobal('fetch', fetchMock);

    const workspace = await fetchMatchWorkspace('match-1', controller.signal);

    expect(workspace.detail.id).toBe('match-1');
    expect(workspace.frames[0].possession?.team).toBe('my_team');
    expect(workspace.frameCount).toBe(27000);
    expect(workspace.nextCursor).toBe('240');
    expect(workspace.analytics.summary.possession).toBe(67);
    expect(workspace.analytics.summary.myTeamXg).toBe(0.42);
    expect(workspace.analytics.summary.myTeamDefensiveLineHeight).toBe(21);
    expect(workspace.analytics.summary.myTeamPpda).toBe(1.8);
    expect(workspace.analytics.formationTimeline[0].formation).toBe('4-4-2');
    expect(workspace.analytics.shots[0].xg).toBe(0.42);
    expect(workspace.events[0].type).toBe('turnover');
    expect(workspace.benchmark?.truthGateReasons).toEqual(['Need at least 3 event families']);
    expect(workspace.evidence?.coordinateSpace).toBe('pitch');
    expect(workspace.evidence?.definitionVersion).toBe('1');
    expect(fetchMock).toHaveBeenCalledTimes(6);
    expect(String(fetchMock.mock.calls[1][0])).toContain('/api/matches/match-1/frames?limit=240');
    expect(String(fetchMock.mock.calls[5][0])).toContain('/api/matches/match-1/evidence?limit=100');
    expect(fetchMock.mock.calls.map(([, init]) => (init as RequestInit).signal)).toEqual([
      controller.signal,
      controller.signal,
      controller.signal,
      controller.signal,
      controller.signal,
      controller.signal,
    ]);
    controller.abort();
    expect(fetchMock.mock.calls.every(([, init]) => (init as RequestInit).signal?.aborted)).toBe(true);
  });
});

describe('fetchMatchEvidence', () => {
  it('queries a bounded interval page from the production match route', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        matchId: 'match-1',
        items: [{ evidenceId: 'frame:0', schemaVersion: 'evidence_v1', payload: { coordinateSpace: 'pitch' } }],
        nextCursor: 'frame:1',
        intervalEndpoint: 'half_open',
        coordinateSpace: 'pitch',
        definitionVersion: '1',
      }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const page = await fetchMatchEvidence('match-1', { intervalStart: 0, intervalEnd: 1, limit: 2 });

    expect(page.coordinateSpace).toBe('pitch');
    expect(page.nextCursor).toBe('frame:1');
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/matches/match-1/evidence?');
    expect(String(fetchMock.mock.calls[0][0])).toContain('intervalStart=0');
    expect(String(fetchMock.mock.calls[0][0])).toContain('limit=2');
  });
});

describe('updateMatchConfig', () => {
  it('patches a match config update and returns the refreshed match detail', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 'match-1',
        name: 'Video Match',
        status: 'ready',
        inputMode: 'video',
        requiresTeamSelection: false,
        config: {
          myTeamCluster: 1,
        },
      }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const detail = await updateMatchConfig('match-1', { myTeamCluster: 1 });

    expect(detail.id).toBe('match-1');
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe('/api/matches/match-1/config');
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe('PATCH');
    expect(init.body).toBe(JSON.stringify({ myTeamCluster: 1 }));
  });
});

describe('buildMatchVideoUrl', () => {
  it('returns the canonical backend route for synced playback', () => {
    expect(buildMatchVideoUrl('match-1')).toBe('/api/matches/match-1/video');
  });
});

describe('buildMatchReportExportUrl', () => {
  it('returns the canonical report export URL', () => {
    expect(buildMatchReportExportUrl('match-1')).toBe('/api/matches/match-1/report/html');
  });
});

describe('mapBackendEventsToTags', () => {
  it('keeps supported derived event types visible in the timeline', () => {
    const tags = mapBackendEventsToTags([
      { type: 'pass', frameId: 2, timestamp: 0.4, team: 'my_team', description: 'Pass completed' },
      { type: 'cross', frameId: 3, timestamp: 0.6, team: 'my_team', description: 'Cross delivered' },
      { type: 'shot', frameId: 4, timestamp: 0.8, team: 'my_team', description: 'Shot attempted' },
      { type: 'tackle', frameId: 5, timestamp: 1.0, team: 'enemy', description: 'Tackle won' },
      { type: 'recovery', frameId: 3, timestamp: 0.6, team: 'enemy', description: 'Ball recovered' },
      { type: 'turnover', frameId: 4, timestamp: 0.8, team: 'enemy', description: 'Turnover won' },
      { type: 'through_ball', frameId: 6, timestamp: 1.2, team: 'my_team', description: 'Through ball played' },
      { type: 'interception', frameId: 8, timestamp: 1.6, team: 'enemy', description: 'Interception won' },
    ], []);

    expect(tags.map((tag) => tag.type)).toEqual([
      'pass',
      'cross',
      'shot',
      'tackle',
      'recovery',
      'turnover',
      'through_ball',
      'interception',
    ]);
    expect(tags.every((tag) => tag.reviewStatus === 'unreviewed')).toBe(true);
    expect(tags.every((tag) => tag.heuristicName === 'provisional_event_suggestion')).toBe(true);
  });
});


it('maps source event IDs to displayed indices with a timestamp fallback', () => {
  const frames = [100, 150].map((Frame_ID, index) => ({ Frame_ID, Timestamp: index * 2, Ball: null, My_Team: [], Enemies: [] }));
  expect(mapBackendEventsToTags([
    { type: 'shot', frameId: 100, timestamp: 0, description: 'First' },
    { type: 'shot', frameId: 999, timestamp: 1.9, description: 'Nearest' },
  ], frames).map(tag => tag.frame)).toEqual([100, 999]);
});

it('C03 report export URL is explicitly bound to the displayed generation', () => {
  expect(buildMatchReportExportUrl('m', 'gen_N')).toBe('/api/matches/m/report/html?generationId=gen_N');
});

it('C03 sends report generation provenance and reads the same report snapshot', async () => {
  const { runMatchAnalysis, fetchGenerationReports } = await import('./api');
  const response = { matchId: 'm', generationId: 'N', status: 'current', reports: {}, notices: [] };
  const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(response), { status: 200, headers: { 'content-type': 'application/json' } }));
  vi.stubGlobal('fetch', fetcher);
  await runMatchAnalysis('m', 'tactical_report', 'local', 0, 'N');
  expect(JSON.parse(fetcher.mock.calls[0][1].body).generationId).toBe('N');
  fetcher.mockResolvedValue(new Response(JSON.stringify(response), { status: 200 }));
  await fetchGenerationReports('m', 'N');
  expect(fetcher.mock.calls[1][0]).toBe('/api/matches/m/reports?generationId=N');
});
