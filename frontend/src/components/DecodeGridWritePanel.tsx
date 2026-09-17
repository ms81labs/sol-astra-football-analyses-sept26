import { useState } from 'react';

import { postDecodeGrid } from '../utils/workbench';

export default function DecodeGridWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestGrid() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postDecodeGrid();
      if (payload.policy === 'source_global_grid') {
        setNote('Posted decode grid keeps policy source_global_grid. Client clipStartSourceFrame 13 is not sent. Client onGrid true is not sent.');
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
    <section aria-label="Unforced decode grid" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced decode grid</h4>
      <button
        type="button"
        aria-label="Request decode grid"
        onClick={() => void requestGrid()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request decode grid
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
