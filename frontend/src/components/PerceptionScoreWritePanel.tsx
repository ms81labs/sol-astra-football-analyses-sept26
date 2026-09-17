import { useState } from 'react';

import { postPerceptionScore } from '../utils/workbench';

export default function PerceptionScoreWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestScore() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postPerceptionScore();
      if (payload.labelsIndependent === false && (payload.notes ?? []).includes('LABELS_INCOMPLETE')) {
        setNote('Posted perception score keeps labelsIndependent false. Client labelsIndependent true is not sent. LABELS_INCOMPLETE stays blocking.');
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
    <section aria-label="Unforced perception score" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced perception score</h4>
      <button
        type="button"
        aria-label="Request perception score"
        onClick={() => void requestScore()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request perception score
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
