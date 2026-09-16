interface OperationsViewProps {
  phase?: string;
  estimatedCost?: number;
  actualCost?: number;
  retries?: number;
  cleanupResult?: string;
  cancelRequested?: boolean;
}

export default function OperationsView({
  phase = 'submitted',
  estimatedCost = 0,
  actualCost = 0,
  retries = 0,
  cleanupResult = 'unknown',
  cancelRequested = false,
}: OperationsViewProps) {
  return (
    <section aria-label="Operations" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Operations</h4>
      <p className="text-xs text-slate-300">Phase {phase}</p>
      <p className="text-xs text-slate-300">Estimated {estimatedCost}</p>
      <p className="text-xs text-slate-300">Actual {actualCost}</p>
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
