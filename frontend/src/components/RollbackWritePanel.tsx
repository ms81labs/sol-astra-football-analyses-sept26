import { useState } from 'react';

import { postRollback } from '../utils/workbench';

export default function RollbackWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestRollback() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postRollback();
      if (
        payload.newJobsAdmitted === false
        && payload.artifactsPreserved === true
        && payload.rewrotePastTrialOutcomes === false
      ) {
        setNote('Posted rollback keeps new jobs refused. Client gpu_default and run-17-report are not sent. Past trial outcomes stay unwritten.');
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
    <section aria-label="Unforced release rollback" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced release rollback</h4>
      <button
        type="button"
        aria-label="Request release rollback"
        onClick={() => void requestRollback()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request release rollback
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
