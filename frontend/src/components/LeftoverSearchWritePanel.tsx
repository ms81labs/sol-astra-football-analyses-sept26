import { useState } from 'react';

import { postLeftoverSearch } from '../utils/workbench';

export default function LeftoverSearchWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestSearch() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postLeftoverSearch();
      if (payload.ok === false && payload.status === 400) {
        setNote('Posted leftover search without matchId stays rejected. Client POST events are not sent. Posted leftover search is not match-scoped queries.');
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
    <section aria-label="Unforced leftover search" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced leftover search</h4>
      <button
        type="button"
        aria-label="Request leftover search"
        onClick={() => void requestSearch()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request leftover search
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
