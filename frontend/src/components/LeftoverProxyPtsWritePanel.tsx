import { useState } from 'react';

import { postLeftoverProxyPts } from '../utils/workbench';

export default function LeftoverProxyPtsWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestProxyPts() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postLeftoverProxyPts();
      if (Array.isArray(payload.mapping) && payload.mapping.length === 0 && payload.replacesOriginal === false) {
        setNote('Posted leftover proxy pts keeps mapping empty. Client POST originalPts is not sent. Posted leftover proxy pts keeps replacesOriginal false.');
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
    <section aria-label="Unforced leftover proxy pts" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced leftover proxy pts</h4>
      <button
        type="button"
        aria-label="Request leftover proxy pts"
        onClick={() => void requestProxyPts()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request leftover proxy pts
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
