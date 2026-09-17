import { useState } from 'react';

import { fetchLeftoverShotTree } from '../utils/workbench';

export default function LeftoverShotTreePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestShotTree() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await fetchLeftoverShotTree();
      if (payload.tree?.enabled === false && payload.tree?.calibratedXg === false) {
        setNote('Requested leftover shot tree keeps enabled false. Client calibratedXg true is not sent. Leftover shot tree stays a challenger, not production xG.');
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
    <section aria-label="Unforced leftover shot tree" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced leftover shot tree</h4>
      <button
        type="button"
        aria-label="Request leftover shot tree"
        onClick={() => void requestShotTree()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request leftover shot tree
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
