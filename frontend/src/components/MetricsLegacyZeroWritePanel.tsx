import { useState } from 'react';

import { postMetricsLegacyZero } from '../utils/workbench';

export default function MetricsLegacyZeroWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestLegacyZero() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postMetricsLegacyZero();
      if (payload.value == null && (payload.reasonCodes ?? []).includes('LEGACY_ZERO_DEFAULT')) {
        setNote('Posted metrics legacy-zero keeps value None. Client measured true is not sent. Legacy zero stays unmeasured.');
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
    <section aria-label="Unforced metrics legacy-zero" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced metrics legacy-zero</h4>
      <button
        type="button"
        aria-label="Request metrics legacy-zero"
        onClick={() => void requestLegacyZero()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request metrics legacy-zero
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
