import { useState } from 'react';

import { postPerceptionBallStates } from '../utils/workbench';

export default function PerceptionBallStatesWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestBallStates() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postPerceptionBallStates();
      if (payload.visible === 0 && payload.inferred === 0) {
        setNote('Posted perception ball-states keep visible 0. Client inferred rows are not sent. Empty rows stay unknown-counted.');
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
    <section aria-label="Unforced perception ball-states" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced perception ball-states</h4>
      <button
        type="button"
        aria-label="Request perception ball-states"
        onClick={() => void requestBallStates()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request perception ball-states
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
