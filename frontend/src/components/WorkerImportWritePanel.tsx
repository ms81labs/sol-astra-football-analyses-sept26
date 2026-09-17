import { useState } from 'react';

import { postWorkerImport } from '../utils/workbench';

export default function WorkerImportWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestImport() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postWorkerImport();
      if (payload.imported === false && payload.jobSucceeded === false) {
        setNote('Posted worker import keeps imported false. Client jobSucceeded true is not sent. Empty kind stays unrecognised.');
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
    <section aria-label="Unforced worker import" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced worker import</h4>
      <button
        type="button"
        aria-label="Request worker import"
        onClick={() => void requestImport()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request worker import
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
