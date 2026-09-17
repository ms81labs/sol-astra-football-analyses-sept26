import { useState } from 'react';

import { postGpuDefaultFlag } from '../utils/workbench';

export default function GpuDefaultFlagWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestFlag() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postGpuDefaultFlag();
      if (payload.name === 'gpu_default' && payload.enabled === false) {
        setNote('Posted GPU default flag keeps enabled false. Client POST enabled true is not sent. Posted flag stays off GPU promotion.');
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
    <section aria-label="Unforced GPU default flag" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced GPU default flag</h4>
      <button
        type="button"
        aria-label="Request GPU default flag"
        onClick={() => void requestFlag()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request GPU default flag
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
