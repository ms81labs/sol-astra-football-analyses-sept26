import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import App from './App';
import type { MatchRecord, MatchStats } from './types';
import * as api from './utils/api';

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

function readyMatch(id: string, name: string): MatchRecord {
  return { id, name, status: 'ready', inputMode: 'tracking_json', originalFilename: `${id}.json` };
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

describe('production analyst shell', () => {
  it('keeps leftover WritePanels and Offside Check off the default App', async () => {
    stubPitchCanvas();
    vi.mocked(api.fetchMatches).mockResolvedValue([readyMatch('match-a', 'Match A')]);
    vi.mocked(api.fetchMatchWorkspace).mockResolvedValue({
      detail: readyMatch('match-a', 'Match A'),
      frames: [{ Frame_ID: 0, Timestamp: 0, Ball: null, My_Team: [], Enemies: [] }],
      frameCount: 1,
      nextCursor: null,
      analytics: { summary: reviewStats, formationTimeline: [], shots: [], ballAssignments: [] },
      events: [],
      benchmark: null,
      evidence: null,
    });
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo) => {
      const url = String(input);
      if (url.includes('/heatmap')) {
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
      if (url.includes('/corrections') || url.includes('/edits')) {
        return Promise.resolve({ ok: true, json: async () => ({ items: [] }) } as Response);
      }
      return Promise.resolve({ ok: true, json: async () => ({}) } as Response);
    }));

    render(<App />);
    await screen.findByText('Match A', { selector: 'header span' });
    expect(await screen.findByLabelText('Operations')).toBeTruthy();
    expect(screen.getByLabelText('Playlist builder')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /request leftover support bundle/i })).toBeNull();
    expect(screen.queryByText(/unforced leftover support bundle/i)).toBeNull();
    expect(screen.queryByText(/offside check/i)).toBeNull();
    expect(screen.queryByTestId('leftover-contract-workbench')).toBeNull();
  });

  it('does not statically import leftover contract workbench into the operator bundle', async () => {
    const fs = await import('node:fs');
    const path = await import('node:path');
    const source = fs.readFileSync(path.join(__dirname, 'App.tsx'), 'utf8');
    expect(source).not.toMatch(/import LeftoverContractWorkbench from/);
    expect(source).toMatch(/lazy\(\(\) => import\('\.\/components\/LeftoverContractWorkbench'\)\)/);
  });
});
