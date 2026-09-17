import { useState } from 'react';

import { postTrainingCycle } from '../utils/workbench';

export default function TrainingCycleWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestCycle() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postTrainingCycle();
      if (payload.proceed === false && payload.reason === 'no_specific_measurable_failure') {
        setNote('Posted training cycle keeps proceed false. Client measurableFailure true is not sent. Diagnose stays no_specific_measurable_failure.');
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
    <section aria-label="Unforced training cycle" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced training cycle</h4>
      <button
        type="button"
        aria-label="Request training cycle"
        onClick={() => void requestCycle()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request training cycle
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
