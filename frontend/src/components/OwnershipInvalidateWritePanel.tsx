import { useState } from 'react';

import { postOwnershipInvalidate } from '../utils/workbench';

export default function OwnershipInvalidateWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestInvalidate() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postOwnershipInvalidate();
      if (payload.change === 'track_edit' && (payload.invalidates ?? []).includes('ownership')) {
        setNote('Posted ownership invalidate keeps change track_edit. Client report change is not sent. Track edit still rebuilds ownership.');
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
    <section aria-label="Unforced ownership invalidate" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced ownership invalidate</h4>
      <button
        type="button"
        aria-label="Request ownership invalidate"
        onClick={() => void requestInvalidate()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request ownership invalidate
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
