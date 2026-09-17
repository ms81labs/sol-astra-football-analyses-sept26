import { useState } from 'react';

import { postCacheRecompute } from '../utils/workbench';

export default function CacheRecomputeWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestRecompute() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postCacheRecompute();
      if (payload.reuse === false && payload.reason === 'cache_identity_changed') {
        setNote('Posted cache recompute keeps reuse false. Client reuse true is not sent. cache_identity_changed rebuilds observations.');
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
    <section aria-label="Unforced cache recompute" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced cache recompute</h4>
      <button
        type="button"
        aria-label="Request cache recompute"
        onClick={() => void requestRecompute()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request cache recompute
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
