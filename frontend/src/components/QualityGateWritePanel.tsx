import { useState } from 'react';

import { postQualityGate } from '../utils/workbench';

export default function QualityGateWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestGate() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postQualityGate();
      if (payload.promoted === false && (payload.reasonCodes ?? []).includes('QUALITY_GATE_FAILED')) {
        setNote('Posted quality gate stays unpromoted. Client faster and qualityPassed are not sent. QUALITY_GATE_FAILED stays blocking.');
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
    <section aria-label="Unforced quality gate" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced quality gate</h4>
      <button
        type="button"
        aria-label="Request quality gate"
        onClick={() => void requestGate()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request quality gate
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
