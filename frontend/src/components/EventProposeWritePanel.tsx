import { useState } from 'react';

import { postEventPropose } from '../utils/workbench';

export default function EventProposeWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestPropose() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postEventPropose();
      if (payload.accepted === false && payload.status === 'withheld') {
        setNote('Posted event propose keeps accepted false. Client accepted true is not sent. MISSING_RELEASE_OR_RECEIPT stays withheld.');
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
    <section aria-label="Unforced event propose" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced event propose</h4>
      <button
        type="button"
        aria-label="Request event propose"
        onClick={() => void requestPropose()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request event propose
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
