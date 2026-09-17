import { useState } from 'react';

import { postIdentityPromote } from '../utils/workbench';

export default function IdentityPromoteWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestPromote() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postIdentityPromote();
      if (payload.kind === 'tracklet' && payload.rosterId == null) {
        setNote('Posted identity promote keeps kind tracklet. Client reviewed true is not sent. Tracklets stay off the roster.');
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
    <section aria-label="Unforced identity promote" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced identity promote</h4>
      <button
        type="button"
        aria-label="Request identity promote"
        onClick={() => void requestPromote()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request identity promote
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
