import { useState } from 'react';

import { postDecodePts } from '../utils/workbench';

export default function DecodePtsWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestPts() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postDecodePts();
      if (payload.seconds === 0) {
        setNote('Posted decode pts keeps seconds 0. Client pts 90000 is not sent. Client seconds override is not sent.');
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
    <section aria-label="Unforced decode pts" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced decode pts</h4>
      <button
        type="button"
        aria-label="Request decode pts"
        onClick={() => void requestPts()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request decode pts
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
