import { useState } from 'react';

import { postTracker } from '../utils/workbench';

export default function TrackerWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestTracker() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postTracker();
      if (payload.silentlyReconnected === false) {
        setNote('Posted tracker keeps silentlyReconnected false. Client silentlyReconnected true is not sent. Cut reconnect stays off.');
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
    <section aria-label="Unforced tracker" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced tracker</h4>
      <button
        type="button"
        aria-label="Request tracker"
        onClick={() => void requestTracker()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request tracker
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
