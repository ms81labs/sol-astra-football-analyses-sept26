import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

import LoadedMatchSetupPanel from './LoadedMatchSetupPanel';
import * as api from '../utils/api';

vi.mock('../utils/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../utils/api')>();
  return {
    ...actual,
    updateMatchConfig: vi.fn().mockResolvedValue({ id: 'match-a' }),
  };
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it('persists periods, pitch, camera, teams and rights through updateMatchConfig', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
    cameraProfile: 'handheld_low_angle',
    automationAdmitted: false,
    manualTaggingPermitted: true,
    cannotMeasure: ['physical_metrics'],
    certified: false,
    pitchLengthM: null,
    homeTeam: '',
    awayTeam: '',
  }), { status: 200, headers: { 'Content-Type': 'application/json' } })));

  render(<LoadedMatchSetupPanel matchId="match-a" />);
  expect(await screen.findByText(/setup wizard/i)).toBeTruthy();
  fireEvent.change(screen.getByLabelText(/periods/i), { target: { value: '1,2' } });
  fireEvent.change(screen.getByLabelText(/pitch length/i), { target: { value: '105' } });
  fireEvent.change(screen.getByLabelText(/camera profile/i), { target: { value: 'stable_elevated_wide' } });
  fireEvent.change(screen.getByLabelText(/home team/i), { target: { value: 'Home FC' } });
  fireEvent.change(screen.getByLabelText(/away team/i), { target: { value: 'Away FC' } });
  fireEvent.click(screen.getByLabelText(/cloud permission/i));
  fireEvent.click(screen.getByRole('button', { name: /save setup/i }));
  await waitFor(() => expect(api.updateMatchConfig).toHaveBeenCalledTimes(1));
  expect(api.updateMatchConfig).toHaveBeenCalledWith('match-a', expect.objectContaining({
    cameraProfile: 'stable_elevated_wide',
    pitchLengthM: 105,
    homeTeam: 'Home FC',
    awayTeam: 'Away FC',
    rights: expect.objectContaining({ cloudPermission: true }),
  }));
});

it('commits live calibration over HTTP without certifying whole-pitch coverage', async () => {
  const fetchMock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith('/setup/preview')) {
      return new Response(JSON.stringify({
        residualP95M: 1.2,
        accepted: true,
        committed: false,
        measured: true,
        certified: false,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }
    if (url.endsWith('/calibration/commit') && init?.method === 'POST') {
      return new Response(JSON.stringify({ committed: true, certified: false }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    return new Response(JSON.stringify({
      cameraProfile: 'stable_elevated_wide',
      automationAdmitted: true,
      manualTaggingPermitted: true,
      cannotMeasure: [],
      certified: false,
      pitchLengthM: 105,
      homeTeam: 'Home FC',
      awayTeam: 'Away FC',
      calibrationCommitted: false,
    }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  });
  vi.stubGlobal('fetch', fetchMock);

  render(<LoadedMatchSetupPanel matchId="match-a" />);
  fireEvent.click(await screen.findByRole('button', { name: /commit calibration/i }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    '/api/matches/match-a/calibration/commit',
    expect.objectContaining({ method: 'POST' }),
  ));
  expect(await screen.findByText(/committed/i)).toBeTruthy();
  expect(screen.queryByText(/certification of whole-pitch/i)).toBeTruthy();
});
