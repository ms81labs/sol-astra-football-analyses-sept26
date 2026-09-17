import { useState } from 'react';

import { postLeftoverOwnershipHysteresis } from '../utils/workbench';

export default function LeftoverOwnershipHysteresisWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestHysteresis() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postLeftoverOwnershipHysteresis();
      if (payload.owner === 'unknown' && payload.minPersistence === 3) {
        setNote('Posted leftover ownership hysteresis keeps owner unknown. Client POST owner my_team is not sent. Posted leftover hysteresis stays unscoped.');
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
    <section aria-label="Unforced leftover ownership hysteresis" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced leftover ownership hysteresis</h4>
      <button
        type="button"
        aria-label="Request leftover ownership hysteresis"
        onClick={() => void requestHysteresis()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request leftover ownership hysteresis
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
