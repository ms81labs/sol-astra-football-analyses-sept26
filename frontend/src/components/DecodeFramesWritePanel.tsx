import { useState } from 'react';

import { postDecodeFrames } from '../utils/workbench';

export default function DecodeFramesWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestFrames() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postDecodeFrames();
      if (payload.backend === 'fixture' && payload.gpuPromoted === false) {
        setNote('Posted decode frames keep backend fixture. Client POST pyav cuda frames are not sent. Posted gpuPromoted stays false.');
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
    <section aria-label="Unforced decode frames" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced decode frames</h4>
      <button
        type="button"
        aria-label="Request decode frames"
        onClick={() => void requestFrames()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request decode frames
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
