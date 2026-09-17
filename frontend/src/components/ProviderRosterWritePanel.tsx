import { useState } from 'react';

import { postProviderRoster } from '../utils/workbench';

export default function ProviderRosterWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestProviders() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postProviderRoster();
      if (
        payload.roster?.default === 'disabled'
        && payload.local?.route === 'disabled'
        && payload.cloud?.route === 'disabled'
      ) {
        setNote('Posted provider roster keeps the default disabled. Client POST enabled cloud is not sent. Posted local and cloud routes stay disabled.');
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
    <section aria-label="Unforced provider roster" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced provider roster</h4>
      <button
        type="button"
        aria-label="Request provider roster"
        onClick={() => void requestProviders()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request provider roster
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
