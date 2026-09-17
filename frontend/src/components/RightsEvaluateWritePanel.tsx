import { useState } from 'react';

import { postRightsEvaluate } from '../utils/workbench';

export default function RightsEvaluateWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestEvaluate() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postRightsEvaluate();
      if (payload.allowed === false && (payload.reasonCodes ?? []).includes('UNCERTAIN_COMMERCIAL_PERMISSION')) {
        setNote('Posted rights evaluate keeps allowed false. Client commercialPermission granted is not sent. UNCERTAIN_COMMERCIAL_PERMISSION stays blocking.');
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
    <section aria-label="Unforced rights evaluate" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced rights evaluate</h4>
      <button
        type="button"
        aria-label="Request rights evaluate"
        onClick={() => void requestEvaluate()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request rights evaluate
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
