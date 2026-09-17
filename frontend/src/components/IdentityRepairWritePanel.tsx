import { useState } from 'react';

import { postIdentityRepair } from '../utils/workbench';

export default function IdentityRepairWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestRepair() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postIdentityRepair();
      if (payload.committed === false && payload.trackId == null) {
        setNote('Posted identity repair keeps committed false. Client trackId is not sent. Unscoped repair stays uncommitted.');
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
    <section aria-label="Unforced identity repair" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced identity repair</h4>
      <button
        type="button"
        aria-label="Request identity repair"
        onClick={() => void requestRepair()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request identity repair
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
