import { useState } from 'react';

import { postDecodeFirst } from '../utils/workbench';

export default function DecodeFirstWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestFirst() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postDecodeFirst();
      if (payload.backend === 'fixture' && payload.sourceFrameIndex === 0 && payload.gpuPromoted === false) {
        setNote('Posted decode first keeps sourceFrameIndex 0. Client torchcodec index 7 is not sent. First-frame decode is not GPU promotion.');
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
    <section aria-label="Unforced decode first" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced decode first</h4>
      <button
        type="button"
        aria-label="Request decode first"
        onClick={() => void requestFirst()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request decode first
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
