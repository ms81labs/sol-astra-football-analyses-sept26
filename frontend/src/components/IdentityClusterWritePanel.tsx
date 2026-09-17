import { useState } from 'react';

import { postIdentityCluster } from '../utils/workbench';

export default function IdentityClusterWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestCluster() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postIdentityCluster();
      if (payload.semanticTeam == null && payload.suggestion === true) {
        setNote('Posted identity cluster keeps semanticTeam None. Client selectedSemantic my_team is not sent. Numeric cluster IDs stay suggestions.');
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
    <section aria-label="Unforced identity cluster" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced identity cluster</h4>
      <button
        type="button"
        aria-label="Request identity cluster"
        onClick={() => void requestCluster()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request identity cluster
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
