import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

import HoldoutCalibrationPanel from './HoldoutCalibrationPanel';

afterEach(() => {
  vi.unstubAllGlobals();
});

it('posts independent holdout landmarks to the loaded match and does not invent client acceptance', async () => {
  const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
    const url = String(input);
    if (url.includes('/api/matches/match-a/calibration') && init?.method === 'POST') {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          evaluation: { accepted: false },
          measured: true,
          residualP95M: 12.4,
          committed: true,
          visionRerun: false,
        }),
      } as Response);
    }
    if (url.includes('/api/matches/match-a/geometry/distance')) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          availability: 'withheld',
          value: null,
          uncertaintyM: 12.4,
          bridged: false,
          reasonCodes: ['CALIBRATION_UNAVAILABLE'],
        }),
      } as Response);
    }
    return Promise.reject(new Error(`unexpected ${url}`));
  });
  vi.stubGlobal('fetch', fetchMock);

  render(<HoldoutCalibrationPanel matchId="match-a" />);
  fireEvent.change(screen.getByLabelText(/image x/i), { target: { value: '50' } });
  fireEvent.change(screen.getByLabelText(/image y/i), { target: { value: '50' } });
  fireEvent.change(screen.getByLabelText(/pitch x/i), { target: { value: '0' } });
  fireEvent.change(screen.getByLabelText(/pitch y/i), { target: { value: '0' } });
  fireEvent.click(screen.getByRole('button', { name: /measure holdout/i }));
  await waitFor(() => {
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/matches/match-a/calibration'))).toBe(true);
  });
  const calibrationCall = fetchMock.mock.calls.find(([url]) => String(url).includes('/api/matches/match-a/calibration'));
  expect(calibrationCall?.[1]?.method).toBe('POST');
  expect(calibrationCall?.[1]?.body).toContain('"independentHoldout":true');
  expect(calibrationCall?.[1]?.body).not.toContain('"accepted":true');
  expect(calibrationCall?.[1]?.body).not.toContain('"residualP95M"');
  expect(await screen.findByText(/holdout not accepted/i)).toBeTruthy();
  expect(screen.getByText(/derived distance withheld/i)).toBeTruthy();
  expect(screen.queryByText(/derived distance 0(\.0)? m/i)).toBeNull();
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/geometry/landmarks'))).toBe(false);
});
