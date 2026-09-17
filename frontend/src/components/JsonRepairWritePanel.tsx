import { useState } from 'react';

import { postJsonRepair } from '../utils/workbench';

export default function JsonRepairWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestRepair() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postJsonRepair();
      if (payload.admitted === false && (payload.reasonCodes ?? []).includes('UNBOUNDED_JSON_REPAIR')) {
        setNote('Posted JSON repair stays refused. Client secret and attempts are not sent. UNBOUNDED_JSON_REPAIR stays blocking.');
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
    <section aria-label="Unforced JSON repair" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced JSON repair</h4>
      <button
        type="button"
        aria-label="Request JSON repair"
        onClick={() => void requestRepair()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request JSON repair
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
