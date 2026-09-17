import { useState } from 'react';

import { postDecodeWrap } from '../utils/workbench';

export default function DecodeWrapWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestWrap() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postDecodeWrap();
      if (payload.lifetime === 'borrowed' && payload.gpuPromoted === false) {
        setNote('Posted decode wrap keeps lifetime borrowed. Client payload cuda is not sent. Borrowed wrap stays unpromoted.');
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
    <section aria-label="Unforced decode wrap" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced decode wrap</h4>
      <button
        type="button"
        aria-label="Request decode wrap"
        onClick={() => void requestWrap()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request decode wrap
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
