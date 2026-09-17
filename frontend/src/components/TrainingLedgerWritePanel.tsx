import { useState } from 'react';

import { postTrainingLedger } from '../utils/workbench';

export default function TrainingLedgerWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestLedger() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postTrainingLedger();
      if (payload.promoted === false && payload.independentGroundTruth === false) {
        setNote('Posted training ledger keeps promoted false. Client independentGroundTruth true is not sent. Ledger rows are not independent ground truth.');
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
    <section aria-label="Unforced training ledger" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced training ledger</h4>
      <button
        type="button"
        aria-label="Request training ledger"
        onClick={() => void requestLedger()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request training ledger
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
