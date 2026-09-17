import { useState } from 'react';

import { postTrainingPromote } from '../utils/workbench';

export default function TrainingPromoteWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestPromote() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postTrainingPromote();
      if (payload.promoted === false && (payload.reasonCodes ?? []).includes('INDEPENDENT_ACCEPTANCE_MISSING')) {
        setNote('Posted training promote keeps promoted false. Client independentAccepted true is not sent. Training candidate stays unpromoted.');
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
    <section aria-label="Unforced training promote" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced training promote</h4>
      <button
        type="button"
        aria-label="Request training promote"
        onClick={() => void requestPromote()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request training promote
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
