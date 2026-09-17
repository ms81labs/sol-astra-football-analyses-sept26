import { useState } from 'react';

import { postMediaAdmit } from '../utils/workbench';

export default function MediaAdmitWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestAdmit() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postMediaAdmit();
      if (payload.admitted === false && (payload.reasonCodes ?? []).includes('UNSUPPORTED_CODEC')) {
        setNote('Posted media admit stays refused. Client remote URL is not sent. Empty codec stays unsupported.');
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
    <section aria-label="Unforced media admit" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced media admit</h4>
      <button
        type="button"
        aria-label="Request media admit"
        onClick={() => void requestAdmit()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request media admit
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
