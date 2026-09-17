import { useState } from 'react';

import { postReportsTemplate } from '../utils/workbench';

export default function ReportsTemplateWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestTemplate() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postReportsTemplate();
      if (payload.kind === 'deterministic_template' && payload.eventCount === 0) {
        setNote('Posted reports template keeps kind deterministic_template. Client metrics are not sent. Empty template stays eventCount 0.');
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
    <section aria-label="Unforced reports template" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced reports template</h4>
      <button
        type="button"
        aria-label="Request reports template"
        onClick={() => void requestTemplate()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request reports template
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
