import { useState } from 'react';

import { postExperimentPause } from '../utils/workbench';

export default function ExperimentPauseWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestPause() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postExperimentPause();
      if (payload.paused === false) {
        setNote('Posted experiment pause keeps paused false. Client remaining 0 is not sent. Remaining still exceeds termination.');
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
    <section aria-label="Unforced experiment pause" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced experiment pause</h4>
      <button
        type="button"
        aria-label="Request experiment pause"
        onClick={() => void requestPause()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request experiment pause
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
