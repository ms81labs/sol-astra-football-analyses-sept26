import { useState } from 'react';

import { postDecodeCrop } from '../utils/workbench';

export default function DecodeCropWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestCrop() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postDecodeCrop();
      if (payload.rotation === 0 && payload.colourOrder === 'bgr') {
        setNote('Posted decode crop keeps rotation 0. Client colourOrder rgb is not sent. Crop stays bgr.');
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
    <section aria-label="Unforced decode crop" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced decode crop</h4>
      <button
        type="button"
        aria-label="Request decode crop"
        onClick={() => void requestCrop()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request decode crop
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
