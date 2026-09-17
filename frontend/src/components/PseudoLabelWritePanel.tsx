import { useState } from 'react';

import { postPseudoLabel } from '../utils/workbench';

export default function PseudoLabelWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestPseudo() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postPseudoLabel();
      if (payload.approved === false && payload.independentGroundTruth === false) {
        setNote('Posted pseudo-label keeps approved false. Client approved true is not sent. independentGroundTruth stays false.');
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
    <section aria-label="Unforced pseudo-label" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced pseudo-label</h4>
      <button
        type="button"
        aria-label="Request pseudo-label"
        onClick={() => void requestPseudo()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request pseudo-label
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
