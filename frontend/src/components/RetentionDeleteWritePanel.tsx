import { useState } from 'react';

import { postRetentionDelete } from '../utils/workbench';

export default function RetentionDeleteWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestDelete() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postRetentionDelete();
      if (payload.mayDelete === false) {
        setNote('Posted retention delete keeps mayDelete false. Client authorisedPolicy true is not sent. Empty kind stays unauthorised.');
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
    <section aria-label="Unforced retention delete" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced retention delete</h4>
      <button
        type="button"
        aria-label="Request retention delete"
        onClick={() => void requestDelete()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request retention delete
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
