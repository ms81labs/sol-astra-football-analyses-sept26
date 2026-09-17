import { useState } from 'react';

import { postPerceptionPreprocess } from '../utils/workbench';

export default function PerceptionPreprocessWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestPreprocess() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postPerceptionPreprocess();
      if (payload.footballRulesApplied === false && payload.sourceCoordinatesUnchanged === true) {
        setNote('Posted perception preprocess keeps footballRulesApplied false. Client footballRulesApplied true is not sent. Source coordinates stay unchanged.');
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
    <section aria-label="Unforced perception preprocess" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced perception preprocess</h4>
      <button
        type="button"
        aria-label="Request perception preprocess"
        onClick={() => void requestPreprocess()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request perception preprocess
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
