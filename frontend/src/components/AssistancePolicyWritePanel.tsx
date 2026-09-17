import { useState } from 'react';

import { postAssistancePolicy } from '../utils/workbench';

export default function AssistancePolicyWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestPolicy() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postAssistancePolicy();
      if (payload.secretsExcluded === true) {
        setNote('Posted assistance policy excludes secrets. Client secret is not sent. secretsExcluded stays true.');
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
    <section aria-label="Unforced assistance policy" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced assistance policy</h4>
      <button
        type="button"
        aria-label="Request assistance policy"
        onClick={() => void requestPolicy()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request assistance policy
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
