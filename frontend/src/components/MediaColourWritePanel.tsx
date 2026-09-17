import { useState } from 'react';

import { postMediaColour } from '../utils/workbench';

export default function MediaColourWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestColour() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postMediaColour();
      if (payload.rotationApplied === false && payload.colourOrder === 'bgr') {
        setNote('Posted media colour keeps rotationApplied false. Client convert false is not sent. Colour round-trip stays bgr.');
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
    <section aria-label="Unforced media colour" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced media colour</h4>
      <button
        type="button"
        aria-label="Request media colour"
        onClick={() => void requestColour()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request media colour
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
