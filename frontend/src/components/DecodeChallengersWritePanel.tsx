import { useState } from 'react';

import { postDecodeChallengers } from '../utils/workbench';

export default function DecodeChallengersWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestChallengers() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postDecodeChallengers();
      if (payload.pyav?.enabled === false && payload.selected === 'opencv') {
        setNote('Posted decode challengers keep pyav enabled false. Client pyav default true is not sent. Selected decode stays opencv.');
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
    <section aria-label="Unforced decode challengers" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced decode challengers</h4>
      <button
        type="button"
        aria-label="Request decode challengers"
        onClick={() => void requestChallengers()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request decode challengers
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
