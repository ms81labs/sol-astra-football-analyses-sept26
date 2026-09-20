import { useEffect, useState } from 'react';
import OperationsView from './OperationsView';
import { normaliseCostSummary, type CostSummary } from '../utils/costs';

interface MatchCostView {
  matchId: string;
  costs: CostSummary[];
  unavailable: boolean;
}

/** Costs are current operational state, never rolled back with a match generation. */
export default function MatchCosts({ matchId }: { matchId?: string | null }) {
  const [view, setView] = useState<MatchCostView | null>(null);
  useEffect(() => {
    if (!matchId) return;
    const controller = new AbortController();
    let inFlight = false;
    let previous = '';
    async function refresh() {
      if (inFlight || controller.signal.aborted) return;
      inFlight = true;
      let next: MatchCostView;
      try {
        const response = await fetch(`/api/matches/${encodeURIComponent(matchId!)}/cost`, { signal: controller.signal });
        if (!response.ok) throw new Error('Cost read failed');
        const payload: unknown = await response.json();
        if (!payload || typeof payload !== 'object' || !('matchId' in payload) || payload.matchId !== matchId
          || !('byCurrency' in payload) || !payload.byCurrency || typeof payload.byCurrency !== 'object'
          || Array.isArray(payload.byCurrency)) throw new Error('Cost scope unavailable');
        const costs = Object.entries(payload.byCurrency).map(([currency, value]) => {
          const summary = normaliseCostSummary(value);
          if (summary.currency !== currency) throw new Error('Currency scope mismatch');
          return summary;
        });
        next = { matchId: matchId!, costs, unavailable: false };
      } catch {
        next = { matchId: matchId!, costs: [], unavailable: true };
      } finally {
        inFlight = false;
      }
      if (controller.signal.aborted) return;
      const serialized = JSON.stringify(next);
      if (previous !== serialized) { previous = serialized; setView(next); }
    }
    void refresh();
    // Read-only polling continues across final reports and pending invoices. No retry dispatch.
    const timer = window.setInterval(() => void refresh(), 2000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [matchId]);
  const current = view?.matchId === matchId ? view : null;
  if (!matchId) return <OperationsView />;
  return <section aria-label="Match billing" className="space-y-2">
    <h4 className="text-xs font-semibold text-slate-300">Match costs — all jobs and provider requests</h4>
    {!current && <p className="text-xs text-slate-400">Billing pending — loading ledger</p>}
    {current?.unavailable && <p className="text-xs text-amber-200">Billing unavailable — no final cost can be confirmed</p>}
    {current && !current.unavailable && current.costs.length === 0 && <p className="text-xs text-slate-400">No billing evidence — final cost unknown</p>}
    {(!current || current.unavailable || current.costs.length === 0) && <OperationsView
      phase={!current ? 'billing pending' : current.unavailable ? 'billing unavailable' : 'no billing evidence'} />}
    {current?.costs.map(cost => <OperationsView key={cost.currency} phase="billing summary" cost={cost}
      estimatedCost={cost.reservedTotal} />)}
  </section>;
}
