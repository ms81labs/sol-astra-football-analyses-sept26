import { useState } from 'react';

import { postResearchPaths } from '../utils/workbench';

export default function ResearchPathsWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestPaths() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postResearchPaths();
      if (payload.allowed === true) {
        setNote('Posted research paths keeps allowed true. Client product paths are not sent. Empty paths stay non-product.');
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
    <section aria-label="Unforced research paths" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced research paths</h4>
      <button
        type="button"
        aria-label="Request research paths"
        onClick={() => void requestPaths()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request research paths
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
