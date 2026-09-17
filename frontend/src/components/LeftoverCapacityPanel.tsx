import { useState } from 'react';

import { fetchLeftoverCapacity } from '../utils/workbench';

export default function LeftoverCapacityPanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestCapacity() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await fetchLeftoverCapacity();
      if (payload.billableCurrentSource === false && payload.exportFpsEqualsInferenceFps === false) {
        setNote('Requested leftover capacity keeps billableCurrentSource false. Client exportFps as inference is not sent. Leftover historical two-half seconds stay unbillable.');
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
    <section aria-label="Unforced leftover capacity" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced leftover capacity</h4>
      <button
        type="button"
        aria-label="Request leftover capacity"
        onClick={() => void requestCapacity()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request leftover capacity
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
