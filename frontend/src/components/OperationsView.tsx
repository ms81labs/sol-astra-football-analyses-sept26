import { formatMoney, normaliseCostSummary, type CostSummary } from '../utils/costs';

interface OperationsViewProps {
  phase?: string;
  estimatedCost?: number | null;
  cost?: CostSummary | null;
  actualCost?: number | null;
  retries?: number;
  cleanupResult?: string;
  cancelRequested?: boolean;
}

export default function OperationsView({
  phase = 'submitted',
  estimatedCost = null,
  actualCost = null,
  cost,
  retries = 0,
  cleanupResult = 'unknown',
  cancelRequested = false,
}: OperationsViewProps) {
  const billing = normaliseCostSummary(cost);
  return (
    <section aria-label="Operations" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Operations</h4>
      <p className="text-xs text-slate-300">Phase {phase}</p>
      <p className="text-xs text-slate-300">Estimated {estimatedCost ?? 'unavailable'}</p>
      <p className="text-xs text-slate-300">
        Final cost {billing.billingComplete && billing.actualTotal !== null
          ? `${billing.currency} ${formatMoney(billing.actualTotal)}` : 'unknown — billing pending'}
      </p>
      {cost && <>
        <p className="text-xs text-slate-300">Execution attempts {billing.attemptCount}</p>
        <p className="text-xs text-slate-300">Confirmed subtotal {billing.currency} {formatMoney(billing.settledTotal)}</p>
        <p className="text-xs text-slate-300">Outstanding reservation {billing.currency} {formatMoney(billing.outstandingReserved)}</p>
        <p className="text-xs text-slate-300">Unsettled exposure {billing.currency} {formatMoney(billing.unsettledTotal)} ({billing.unsettledAttemptCount} uncertain attempts)</p>
        {billing.reasonCodes.length > 0 && <p className="text-xs text-amber-200">Billing: {billing.reasonCodes.join(', ')}</p>}
      </>}
      {!cost && actualCost !== null && <p className="text-xs text-amber-200">Legacy reported charge {actualCost} (unverified)</p>}
      <p className="text-xs text-slate-300">Retries {retries}</p>
      <p className="text-xs text-slate-300">Cleanup {cleanupResult}</p>
      {cancelRequested && <p className="text-xs text-amber-200">Cancel requested</p>}
      <p className="text-xs text-slate-400">
        Job cancellation is a request, not proof of termination. Cancellation does not erase incurred charges.
        Escalation requires a measured task-quality gap. GPU default and native code remain gated.
        Cleanup is unknown until confirmed. GPU inference does not run inside an HTTP request.
      </p>
    </section>
  );
}
