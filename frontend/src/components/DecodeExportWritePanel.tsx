import { useState } from 'react';

import { postDecodeExport } from '../utils/workbench';

export default function DecodeExportWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestExport() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postDecodeExport();
      if (payload.admitted === false) {
        setNote('Posted decode export keeps admitted false. Client sourceUrl is not sent. Unconstrained decoder stays refused.');
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
    <section aria-label="Unforced decode export" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced decode export</h4>
      <button
        type="button"
        aria-label="Request decode export"
        onClick={() => void requestExport()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request decode export
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
