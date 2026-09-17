import { useState } from 'react';

import { postDecodeCuts } from '../utils/workbench';

export default function DecodeCutsWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestCuts() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postDecodeCuts();
      if (Array.isArray(payload.cuts) && payload.cuts.length === 0) {
        setNote('Posted decode cuts keep stored times empty. Client cuts array is not sent. Camera-cut invention stays off.');
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
    <section aria-label="Unforced decode cuts" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced decode cuts</h4>
      <button
        type="button"
        aria-label="Request decode cuts"
        onClick={() => void requestCuts()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request decode cuts
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
