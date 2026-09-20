import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import MatchCosts from './MatchCosts';

const pending = {schemaVersion:2,currency:'USD',authorisedBudget:1,attemptCount:1,settledTotal:.2,
  outstandingReserved:0,unsettledTotal:.8,unsettledAttemptCount:1,reservedTotal:.8,billingComplete:false,
  actualTotal:null,reasonCodes:['PROVIDER_OUTCOME_UNKNOWN']};
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('renders live match/provider billing even when no report was published', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({matchId:'m',byCurrency:{USD:pending}}))));
  render(<MatchCosts matchId="m" />);
  expect(await screen.findByText(/Confirmed subtotal USD 0.20/)).toBeTruthy();
  expect(screen.getByText(/Final cost unknown/)).toBeTruthy();
});

it('keeps currencies separate, including final zero', async () => {
  const euro = {...pending, currency:'EUR',actualTotal:0,settledTotal:0,unsettledTotal:0,
    reservedTotal:0,unsettledAttemptCount:0,billingComplete:true};
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({matchId:'m',byCurrency:{USD:pending,EUR:euro}}))));
  render(<MatchCosts matchId="m" />);
  expect(await screen.findByText(/Final cost EUR 0.00/)).toBeTruthy();
  expect(screen.getByText(/Unsettled exposure USD 0.80/)).toBeTruthy();
});

it('rejects foreign match cost instead of displaying it as current', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({matchId:'other',byCurrency:{USD:pending}}))));
  render(<MatchCosts matchId="m" />);
  expect(await screen.findByText(/Billing unavailable/)).toBeTruthy();
  expect(screen.queryByText(/Confirmed subtotal USD/)).toBeNull();
});

it('ignores a delayed response for the previously selected match', async () => {
  let finish!: (response: Response) => void;
  const fetch = vi.fn().mockImplementationOnce(() => new Promise<Response>(resolve => {finish=resolve;}))
    .mockResolvedValue(new Response(JSON.stringify({matchId:'new',byCurrency:{}})));
  vi.stubGlobal('fetch', fetch);
  const view = render(<MatchCosts matchId="old" />);
  view.rerender(<MatchCosts matchId="new" />);
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  finish(new Response(JSON.stringify({matchId:'old',byCurrency:{USD:pending}})));
  await waitFor(() => expect(screen.getByText(/No billing evidence/)).toBeTruthy());
  expect(screen.queryByText(/Confirmed subtotal USD/)).toBeNull();
});
