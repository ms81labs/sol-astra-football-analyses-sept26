import { useState } from 'react';

import { postWorkerEnvironment } from '../utils/workbench';

export default function WorkerEnvironmentWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestEnvironment() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postWorkerEnvironment();
      if (payload.NAMESPACE === 'production') {
        setNote('Posted worker environment excludes host secrets. Client hostSecret is not sent. NAMESPACE stays production.');
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
    <section aria-label="Unforced worker environment" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced worker environment</h4>
      <button
        type="button"
        aria-label="Request worker environment"
        onClick={() => void requestEnvironment()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request worker environment
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
