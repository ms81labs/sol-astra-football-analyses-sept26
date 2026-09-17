import { useState } from 'react';

import { postLeftoverExperimentB2 } from '../utils/workbench';

export default function LeftoverExperimentB2WritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestExperimentB2() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postLeftoverExperimentB2();
      if (payload.promoted === false && payload.hardwareVerified === false) {
        setNote('Posted leftover experiment B2 keeps promoted false. Client POST hardwareVerified true is not sent. Leftover POST is not stored GET experiment B2.');
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
    <section aria-label="Unforced leftover experiment B2" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced leftover experiment B2</h4>
      <button
        type="button"
        aria-label="Request leftover experiment B2"
        onClick={() => void requestExperimentB2()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request leftover experiment B2
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
