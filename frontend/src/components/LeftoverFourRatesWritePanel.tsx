import { useState } from 'react';

import { postLeftoverFourRates } from '../utils/workbench';

export default function LeftoverFourRatesWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestFourRates() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postLeftoverFourRates();
      if (payload.exportFpsEqualsInferenceFps === false) {
        setNote('Posted leftover four rates keeps exportFpsEqualsInferenceFps false. Client POST exportFpsEqualsInferenceFps true is not sent. Posted leftover four rates is not match-scoped rates.');
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
    <section aria-label="Unforced leftover four rates" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced leftover four rates</h4>
      <button
        type="button"
        aria-label="Request leftover four rates"
        onClick={() => void requestFourRates()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request leftover four rates
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
