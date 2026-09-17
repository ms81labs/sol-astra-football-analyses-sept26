import { useState } from 'react';

import { postMetricsPossessionStates } from '../utils/workbench';

export default function MetricsPossessionStatesWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestPossessionStates() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postMetricsPossessionStates();
      if (payload.availability === 'insufficient_coverage' && payload.publishedValue == null) {
        setNote('Posted metrics possession-states keeps publishedValue null. Client states are not sent. Empty states stay insufficient_coverage.');
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
    <section aria-label="Unforced metrics possession-states" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced metrics possession-states</h4>
      <button
        type="button"
        aria-label="Request metrics possession-states"
        onClick={() => void requestPossessionStates()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request metrics possession-states
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
