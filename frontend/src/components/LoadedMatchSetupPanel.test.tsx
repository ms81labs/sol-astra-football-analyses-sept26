import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import LoadedMatchSetupPanel from './LoadedMatchSetupPanel';
import * as api from '../utils/api';

vi.mock('../utils/api', async (importOriginal) => ({ ...await importOriginal<typeof import('../utils/api')>(), updateMatchConfig: vi.fn() }));
beforeEach(() => vi.mocked(api.updateMatchConfig).mockResolvedValue({ id: 'match-a', name: 'A', status: 'ready', inputMode: 'tracking_json', originalFilename: 'a.json',
  generationId: 'g2', correction: { correctionId: 'setup-1', saveState: 'saved', applyState: 'applied', appliedGeneration: 'g2' } }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.resetAllMocks(); });
const setup = { generationId: 'g1', cameraProfile: 'stable_elevated_wide', automationAdmitted: false,
  manualTaggingPermitted: true, cannotMeasure: ['physical_metrics'], certified: false, pitchLengthM: 100,
  homeTeam: '', awayTeam: '', cloudPermission: false, periods: [{ name: '1', startSeconds: 0, endSeconds: 600 }] };
const preview = { generationId: 'g1', residualP95M: 1.2, accepted: true, committed: false, measured: true, certified: false };
const json = (value: unknown) => new Response(JSON.stringify(value), { status: 200, headers: { 'Content-Type': 'application/json' } });

it('saves analytical settings separately from current team names and cloud permission', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo) => json(String(input).includes('/preview') ? preview : setup)));
  render(<LoadedMatchSetupPanel matchId="match-a" generationId="g1" />);
  expect(await screen.findByText(/setup wizard/i)).toBeTruthy();
  fireEvent.change(screen.getByLabelText(/pitch length/i), { target: { value: '105' } });
  fireEvent.change(screen.getByLabelText(/home team/i), { target: { value: 'Home FC' } });
  fireEvent.change(screen.getByLabelText(/away team/i), { target: { value: 'Away FC' } });
  fireEvent.click(screen.getByLabelText(/cloud permission/i));
  fireEvent.click(screen.getByRole('button', { name: /save setup/i }));
  await waitFor(() => expect(api.updateMatchConfig).toHaveBeenCalledTimes(1));
  const [, payload] = vi.mocked(api.updateMatchConfig).mock.calls[0];
  expect(payload).toEqual({ cameraProfile: 'stable_elevated_wide', pitchLengthM: 105,
    periods: setup.periods, baseGeneration: 'g1', commandId: expect.any(String) });
  expect(payload).not.toHaveProperty('rights');
  expect(payload).not.toHaveProperty('homeTeam');
  fireEvent.click(screen.getByRole('button', { name: /save team names/i }));
  await waitFor(() => expect(api.updateMatchConfig).toHaveBeenCalledWith('match-a', { homeTeam: 'Home FC', awayTeam: 'Away FC' }));
  fireEvent.click(screen.getByRole('button', { name: /save cloud permission/i }));
  await waitFor(() => expect(api.updateMatchConfig).toHaveBeenCalledWith('match-a', { rights: { cloudPermission: true, processingScope: 'hosted' } }));
});
it('does not invent a matrix and holdouts from a preview acceptance flag', async () => {
  const fetchMock = vi.fn(async (input: RequestInfo) => json(String(input).includes('/preview') ? preview : setup));
  vi.stubGlobal('fetch', fetchMock);
  render(<LoadedMatchSetupPanel matchId="match-a" generationId="g1" />);
  await screen.findByText(/setup wizard/i);
  expect(screen.queryByRole('button', { name: /commit calibration/i })).toBeNull();
  expect(screen.getByText(/no measured calibration profile/i)).toBeTruthy();
  expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/calibration/commit'))).toBe(false);
});
it('passes only the actual source profile and optimistic controls to calibration commit', async () => {
  const profile = { profileId: 'source-observations', homography: [[0.1, 0, 0], [0, 0.1, 0], [0, 0, 1]], holdout: [{ id: 'independent', x: 12, y: 18 }] };
  const fetchMock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
    if (String(input).includes('/calibration/commit')) return json({ committed: true, certified: false,
      correction: { correctionId: 'cal-1', saveState: 'saved', applyState: 'applied', appliedGeneration: 'g2' } });
    void init;
    return json(String(input).includes('/preview') ? { ...preview, profile } : setup);
  });
  vi.stubGlobal('fetch', fetchMock);
  render(<LoadedMatchSetupPanel matchId="match-a" generationId="g1" />);
  fireEvent.click(await screen.findByRole('button', { name: /commit calibration/i }));
  await waitFor(() => expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/calibration/commit'))).toBe(true));
  const call = fetchMock.mock.calls.find(([input]) => String(input).includes('/calibration/commit'))!;
  expect(JSON.parse(String(call[1]?.body))).toEqual({ ...profile, baseGeneration: 'g1', commandId: expect.any(String) });
  expect(screen.getByText(/not a certification of whole-pitch/i)).toBeTruthy();
});
it('does not report successful setup when only the command was recorded', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo) => json(String(input).includes('/preview') ? preview : setup)));
  vi.mocked(api.updateMatchConfig).mockResolvedValue({ id: 'match-a', name: 'A', status: 'ready', inputMode: 'tracking_json', originalFilename: 'a.json',
    correction: { correctionId: 'c', saveState: 'saved', applyState: 'committed' } });
  render(<LoadedMatchSetupPanel matchId="match-a" generationId="g1" />);
  fireEvent.click(await screen.findByRole('button', { name: /save setup/i }));
  expect(await screen.findByText(/setup was not applied/i)).toBeTruthy();
  expect(screen.queryByText('Setup saved')).toBeNull();
});
