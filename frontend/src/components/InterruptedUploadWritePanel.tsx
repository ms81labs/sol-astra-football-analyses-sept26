import { useState } from 'react';

import { postInterruptedUpload } from '../utils/workbench';

export default function InterruptedUploadWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestInterrupt() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postInterruptedUpload();
      if (payload.accepted === false && payload.quarantined === true) {
        setNote('Posted interrupted upload keeps accepted false. Client accepted true is not sent. quarantined stays true.');
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
    <section aria-label="Unforced interrupted upload" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced interrupted upload</h4>
      <button
        type="button"
        aria-label="Request interrupted upload"
        onClick={() => void requestInterrupt()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request interrupted upload
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
