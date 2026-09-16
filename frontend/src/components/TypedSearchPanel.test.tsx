import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

import TypedSearchPanel from './TypedSearchPanel';

afterEach(() => {
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
