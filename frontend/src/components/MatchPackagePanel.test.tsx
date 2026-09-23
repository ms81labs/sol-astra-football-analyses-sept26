import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

import MatchPackagePanel from './MatchPackagePanel';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('exports and reopens the same source-bound editable package', async () => {
  const matchId = 'a'.repeat(32);
  const packageData = { schemaVersion: 'match_bundle_v1', matchId, generationId: 'g1',
    playlist: { sourceSha256: 'b'.repeat(64), intervals: [[1, 2]] }, corrections: [], annotations: [] };
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo) => ({ ok: true, json: async () => (
    String(input).includes('/export/match.json') ? packageData : { analyst: { limitations: [] } }
  ) } as Response)));
  const onReopen = vi.fn(async () => true);
  render(<MatchPackagePanel matchId={matchId} generationId="g1" onReopen={onReopen} />);
  expect(screen.getByRole('link', { name: /download editable package/i }).getAttribute('href'))
    .toBe(`/api/matches/${matchId}/export/match.json?generationId=g1`);
  const file = new File([JSON.stringify(packageData)], 'match.json', { type: 'application/json' });
  Object.defineProperty(file, 'text', { value: async () => JSON.stringify(packageData) });
  fireEvent.change(screen.getByLabelText(/reopen editable package/i), { target: { files: [file] } });
  await waitFor(() => expect(onReopen).toHaveBeenCalledWith(matchId, 'g1'));
  expect(await screen.findByText(/editable package reopened/i)).toBeTruthy();
});

it('refuses an edited file when its notes differ from retained state', async () => {
  const matchId = 'a'.repeat(32);
  const retained = { schemaVersion: 'match_bundle_v1', matchId, generationId: 'g1',
    playlist: { sourceSha256: 'b'.repeat(64), intervals: [[1, 2]] },
    corrections: [{ payload: { notes: 'Original note' } }], annotations: [] };
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => retained } as Response)));
  const onReopen = vi.fn(async () => true);
  render(<MatchPackagePanel matchId={matchId} generationId="g1" onReopen={onReopen} />);
  const file = new File([JSON.stringify(retained)], 'match.json', { type: 'application/json' });
  Object.defineProperty(file, 'text', { value: async () => JSON.stringify({
    ...retained, corrections: [{ payload: { notes: 'Changed note' } }],
  }) });
  fireEvent.change(screen.getByLabelText(/reopen editable package/i), { target: { files: [file] } });
  expect(await screen.findByText(/package contents differ from retained state/i)).toBeTruthy();
  expect(onReopen).not.toHaveBeenCalled();
});
