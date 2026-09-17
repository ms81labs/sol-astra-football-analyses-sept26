import { useState } from 'react';

import { postDecodeFallback } from '../utils/workbench';

export default function DecodeFallbackWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestFallback() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postDecodeFallback();
      if (payload.selected === 'opencv' && payload.availableIncludesCuda === false) {
        setNote('Posted decode fallback keeps selected opencv. Client selected cuda is not sent. CUDA stays unavailable.');
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
    <section aria-label="Unforced decode fallback" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced decode fallback</h4>
      <button
        type="button"
        aria-label="Request decode fallback"
        onClick={() => void requestFallback()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request decode fallback
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
