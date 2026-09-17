import { useState } from 'react';

import { postMetricsSpec } from '../utils/workbench';

export default function MetricsSpecWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestSpec() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postMetricsSpec();
      if (payload.availability === 'withheld' && payload.value == null) {
        setNote('Posted metrics spec keeps availability withheld. Client identityContinuous true is not sent. Spec value stays None.');
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
    <section aria-label="Unforced metrics spec" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced metrics spec</h4>
      <button
        type="button"
        aria-label="Request metrics spec"
        onClick={() => void requestSpec()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request metrics spec
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
