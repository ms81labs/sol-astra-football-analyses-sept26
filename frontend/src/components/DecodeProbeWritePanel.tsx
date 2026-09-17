import { useState } from 'react';

import { postDecodeProbe } from '../utils/workbench';

export default function DecodeProbeWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestProbe() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postDecodeProbe();
      if (payload.name === 'ffmpeg' && payload.default === false && payload.role === 'challenger') {
        setNote('Posted decode probe keeps ffmpeg default false. Client default true is not sent. FFmpeg probe is not the production decoder.');
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
    <section aria-label="Unforced decode probe" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced decode probe</h4>
      <button
        type="button"
        aria-label="Request decode probe"
        onClick={() => void requestProbe()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request decode probe
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
