import { useState } from 'react';

import { postEventScore } from '../utils/workbench';

export default function EventScoreWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestScore() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postEventScore();
      if (payload.labelsIndependent === false) {
        setNote('Posted event score keeps labelsIndependent false. Client labelsIndependent true is not sent. Event AP stays unproven.');
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
    <section aria-label="Unforced event score" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced event score</h4>
      <button
        type="button"
        aria-label="Request event score"
        onClick={() => void requestScore()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request event score
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
