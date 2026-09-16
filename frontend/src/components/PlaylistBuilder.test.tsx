import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

import PlaylistBuilder from './PlaylistBuilder';

afterEach(() => {
  vi.unstubAllGlobals();
});

it('exports time-bounded clips with notes and refuses whole-match frequency claims', async () => {
  const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
    void init;
    const url = String(input);
    if (url.includes('/api/playlists/export-interval')) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          sourceStartSeconds: 12,
          sourceEndSeconds: 14,
          sourceEndFrameExclusive: 350,
        }),
      } as Response);
    }
    return Promise.reject(new Error(`unexpected ${url}`));
  });
  vi.stubGlobal('fetch', fetchMock);

  render(<PlaylistBuilder />);
  fireEvent.change(screen.getByLabelText(/clip start/i), { target: { value: '12' } });
  fireEvent.change(screen.getByLabelText(/clip end/i), { target: { value: '14' } });
  fireEvent.change(screen.getByLabelText(/notes/i), { target: { value: 'second-half turnover then shot' } });
  fireEvent.click(screen.getByRole('button', { name: /add clip/i }));
  await waitFor(() => {
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/api/playlists/export-interval'))).toBe(true);
  });
  const exportCall = fetchMock.mock.calls.find(([input]) => String(input).includes('/api/playlists/export-interval'));
  expect(exportCall?.[1]?.method).toBe('POST');
  expect(exportCall?.[1]?.body).toContain('"timestampStart":12');
  expect(exportCall?.[1]?.body).toContain('"timestampEnd":14');
  expect(await screen.findByText(/12s to 14s/)).toBeTruthy();
  expect(screen.getByText(/frame 350 exclusive/i)).toBeTruthy();
  expect(screen.getByText(/second-half turnover then shot/)).toBeTruthy();
  expect(screen.getByText(/do not establish a whole-match frequency/i)).toBeTruthy();
});

it('assembles a deterministic match report that does not claim whole-match frequency', async () => {
  const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
    void init;
    const url = String(input);
    if (url.includes('/api/matches/match-a/reports')) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          factualCheck: { accepted: true, reasonCodes: ['GROUNDED'] },
          publication: { accepted: true, requiresAnalyst: true, wholeMatchFrequency: false, frequencyRequiresDenominator: true },
        }),
      } as Response);
    }
    return Promise.reject(new Error(`unexpected ${url}`));
  });
  vi.stubGlobal('fetch', fetchMock);

  render(<PlaylistBuilder matchId="match-a" />);
  fireEvent.click(screen.getByRole('button', { name: /assemble report/i }));
  await waitFor(() => {
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/api/matches/match-a/reports'))).toBe(true);
  });
  const reportCall = fetchMock.mock.calls.find(([input]) => String(input).includes('/api/matches/match-a/reports'));
  expect(reportCall?.[1]?.method).toBe('POST');
  expect(await screen.findByText(/does not claim whole-match frequency/i)).toBeTruthy();
  expect(screen.getByText(/frequency requires a denominator/i)).toBeTruthy();
});
