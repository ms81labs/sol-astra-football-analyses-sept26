import { useState } from 'react';

import { postDeploymentChoice } from '../utils/workbench';

export default function DeploymentChoiceWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestChoice() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postDeploymentChoice();
      if (payload.alwaysOnGpuCommitted === false) {
        setNote('Posted deployment choice keeps alwaysOnGpuCommitted false. Client alwaysOnGpuCommitted true is not sent. Local hardware does not commit GPU.');
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
    <section aria-label="Unforced deployment choice" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced deployment choice</h4>
      <button
        type="button"
        aria-label="Request deployment choice"
        onClick={() => void requestChoice()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request deployment choice
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
