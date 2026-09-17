import { useState } from 'react';

import { fetchLeftoverDpia } from '../utils/workbench';

export default function LeftoverDpiaPanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestDpia() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await fetchLeftoverDpia();
      if (payload.cloudAllowed === false && payload.faceRecognition === false) {
        setNote('Requested leftover DPIA keeps cloudAllowed false. Client faceRecognition true is not sent. Leftover DPIA is not match-scoped privacy.');
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
    <section aria-label="Unforced leftover DPIA" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced leftover DPIA</h4>
      <button
        type="button"
        aria-label="Request leftover DPIA"
        onClick={() => void requestDpia()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request leftover DPIA
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
