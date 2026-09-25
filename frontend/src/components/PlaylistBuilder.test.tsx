import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

import PlaylistBuilder from './PlaylistBuilder';

afterEach(() => {
  cleanup();
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

  render(<PlaylistBuilder sourceFps={25} />);
  fireEvent.change(screen.getByLabelText(/clip start/i), { target: { value: '12' } });
  fireEvent.change(screen.getByLabelText(/clip end/i), { target: { value: '14' } });
  fireEvent.change(screen.getByLabelText(/^title$/i), { target: { value: 'Second-half recovery' } });
  fireEvent.change(screen.getByLabelText(/notes/i), { target: { value: 'second-half turnover then shot' } });
  fireEvent.click(screen.getByRole('button', { name: /add clip/i }));
  await waitFor(() => {
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/api/playlists/export-interval'))).toBe(true);
  });
  const exportCall = fetchMock.mock.calls.find(([input]) => String(input).includes('/api/playlists/export-interval'));
  expect(exportCall?.[1]?.method).toBe('POST');
  expect(exportCall?.[1]?.body).toContain('"timestampStart":12');
  expect(exportCall?.[1]?.body).toContain('"timestampEnd":14');
  expect(exportCall?.[1]?.body).toContain('"sourceFps":25');
  expect(await screen.findByText(/12s to 14s/)).toBeTruthy();
  expect(screen.getByText(/frame 350 exclusive/i)).toBeTruthy();
  expect(screen.getByText(/Second-half recovery/)).toBeTruthy();
  expect(screen.getByText(/second-half turnover then shot/)).toBeTruthy();
  expect(screen.getByText(/do not establish a whole-match frequency/i)).toBeTruthy();
});

it('offers exact saved video intervals as source-bound playable downloads', () => {
  render(<PlaylistBuilder matchId="match-a" generationId="g1" videoAvailable storedClips={[
    { generationId: 'g1', start: 1.1, end: 2.1, title: 'Pressing cue', notes: 'Key moment', sourceEndFrameExclusive: 11 },
  ]} />);
  expect(screen.getByText(/Pressing cue/)).toBeTruthy();
  const link = screen.getByRole('link', { name: /download rendered clip/i });
  expect(link.getAttribute('href')).toBe('/api/matches/match-a/edits/clip?generationId=g1&start=1.1&end=2.1');
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


it.each(['match', 'generation'])('C03 ignores a pending clip after the %s changes', async (change) => {
  let resolve!: (response: Response) => void;
  const pending = new Promise<Response>((done) => { resolve = done; });
  const fetchMock = vi.fn((input: RequestInfo) => {
    if (String(input).includes('/api/playlists/export-interval')) return pending;
    return Promise.resolve({ ok: true, json: async () => ({ intervals: [], reencodeFullMatch: false, renderOnDemand: true }) } as Response);
  });
  vi.stubGlobal('fetch', fetchMock);
  const save = vi.fn(); const open = vi.fn();
  const { rerender } = render(<PlaylistBuilder matchId="a" generationId="N" onClipSaved={save} onOpenInterval={open} />);
  fireEvent.click(screen.getByRole('button', { name: /add clip/i }));
  rerender(<PlaylistBuilder matchId={change === 'match' ? 'b' : 'a'} generationId={change === 'generation' ? 'N1' : 'N'} onClipSaved={save} onOpenInterval={open} />);
  await act(async () => resolve({ ok: true, json: async () => ({ sourceStartSeconds: 12, sourceEndSeconds: 14, sourceEndFrameExclusive: 350 }) } as Response));
  expect(save).not.toHaveBeenCalled(); expect(open).not.toHaveBeenCalled();
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/edits/render'))).toBe(false);
});
