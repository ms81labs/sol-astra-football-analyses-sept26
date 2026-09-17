import { useState } from 'react';

import { postDecodePixels } from '../utils/workbench';

export default function DecodePixelsWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestPixels() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postDecodePixels();
      if (payload.gpuPromoted === false && payload.device === 'cpu') {
        setNote('Posted decode pixels keep gpuPromoted false. Client device cuda is not sent. Live pixel wrap stays on cpu.');
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
    <section aria-label="Unforced decode pixels" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced decode pixels</h4>
      <button
        type="button"
        aria-label="Request decode pixels"
        onClick={() => void requestPixels()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request decode pixels
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
