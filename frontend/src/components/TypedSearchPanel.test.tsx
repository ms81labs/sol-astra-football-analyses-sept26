import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

import TypedSearchPanel from './TypedSearchPanel';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it('posts a typed query to the loaded match and refuses client event rows', async () => {
  const fetchMock = vi.fn((input: RequestInfo, init?: RequestInit) => {
    const url = String(input);
    if (url.includes('/api/matches/match-a/queries') && init?.method === 'POST') {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          query: { unanswerable: true, reason: 'refused_code_execution', eventFamily: 'pass' },
          results: [],
        }),
      } as Response);
    }
    return Promise.reject(new Error(`unexpected ${url}`));
  });
  vi.stubGlobal('fetch', fetchMock);

  render(<TypedSearchPanel matchId="match-a" />);
  fireEvent.change(screen.getByLabelText(/^query$/i), { target: { value: 'SELECT * FROM events' } });
  fireEvent.click(screen.getByRole('button', { name: /search evidence/i }));
  await waitFor(() => {
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/api/matches/match-a/queries'))).toBe(true);
  });
  const queryCall = fetchMock.mock.calls.find(([url]) => String(url).includes('/api/matches/match-a/queries'));
  expect(queryCall?.[1]?.body).toBe(JSON.stringify({ query: 'SELECT * FROM events' }));
  expect(await screen.findByText(/unanswerable: refused_code_execution/i)).toBeTruthy();
});

it('does not seek from an old search after the match or generation changes', async () => {
  let resolveRequest!: (response: Response) => void;
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>((resolve) => { resolveRequest = resolve; })));
  const onSeek = vi.fn();
  const view = render(<TypedSearchPanel matchId="match-a" generationId="g1" onSeek={onSeek} />);
  fireEvent.click(screen.getByRole('button', { name: /search evidence/i }));
  await waitFor(() => expect(resolveRequest).toBeDefined());
  view.rerender(<TypedSearchPanel matchId="match-b" generationId="g2" onSeek={onSeek} />);
  await act(async () => resolveRequest({ ok: true, json: async () => ({
    generationId: 'g1', query: { unanswerable: false }, results: [{ eventId: 'old', timestamp: 2, evidenceIds: [] }],
  }) } as Response));
  expect(onSeek).not.toHaveBeenCalled();
  expect(screen.queryByText(/1 evidence-linked interval/i)).toBeNull();
});

it('does not seek after the search panel unmounts', async () => {
  let resolveRequest!: (response: Response) => void;
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>((resolve) => { resolveRequest = resolve; })));
  const onSeek = vi.fn();
  const view = render(<TypedSearchPanel matchId="match-a" onSeek={onSeek} />);
  fireEvent.click(screen.getByRole('button', { name: /search evidence/i }));
  await waitFor(() => expect(resolveRequest).toBeDefined());
  view.unmount();
  await act(async () => resolveRequest({ ok: true, json: async () => ({
    query: { unanswerable: false }, results: [{ eventId: 'old', timestamp: 2, evidenceIds: [] }],
  }) } as Response));
  expect(onSeek).not.toHaveBeenCalled();
});

it('lets the analyst choose a source interval with its evidence and review status', async () => {
  const selected = vi.fn();
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({
    generationId: 'g1', query: { unanswerable: false }, results: [
      { eventId: 'first', matchId: 'match-a', timestamp: 2, intervalStart: 1.8, intervalEnd: 2.4,
        evidenceIds: ['e1'], label: 'pass', reviewStatus: 'unreviewed' },
      { eventId: 'second', matchId: 'match-a', timestamp: 5, intervalStart: 4.8, intervalEnd: 5.4,
        evidenceIds: ['e2'], label: 'shot', reviewStatus: 'accepted' },
    ],
  }) } as Response)));
  render(<TypedSearchPanel matchId="match-a" generationId="g1" onSelectHit={selected} />);
  fireEvent.click(screen.getByRole('button', { name: /search evidence/i }));
  fireEvent.click(await screen.findByRole('button', { name: /shot.*4.8.*5.4/i }));
  expect(selected).toHaveBeenCalledWith(expect.objectContaining({
    eventId: 'second', matchId: 'match-a', intervalStart: 4.8, intervalEnd: 5.4,
    evidenceIds: ['e2'], reviewStatus: 'accepted',
  }));
});
