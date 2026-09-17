import { useState } from 'react';

import { postCostEstimate } from '../utils/workbench';

export default function CostEstimateWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestEstimate() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postCostEstimate();
      if (payload.exportFpsEqualsInferenceFps === false && payload.allocatedCompute === 0) {
        setNote('Posted cost estimate keeps export fps off inference cost. Client export fps 5 is not sent. Allocated compute stays zero.');
      } else {
        setNote(null);
      }
    } catch {
      setNote(null);
    } finally {
      setPending(false);
    }
  }

  return (
    <section aria-label="Unforced cost estimate" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced cost estimate</h4>
      <button
        type="button"
        aria-label="Request cost estimate"
        onClick={() => void requestEstimate()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request cost estimate
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
