import { useState } from 'react';

import { postCleanupComplete } from '../utils/workbench';

export default function CleanupCompleteWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestCleanup() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postCleanupComplete();
      if (payload.complete === false && payload.cleanupResult === 'failed') {
        setNote('Posted cleanup complete keeps complete false. Client complete true is not sent. Failed cleanup stays incomplete.');
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
    <section aria-label="Unforced cleanup complete" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced cleanup complete</h4>
      <button
        type="button"
        aria-label="Request cleanup complete"
        onClick={() => void requestCleanup()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request cleanup complete
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
