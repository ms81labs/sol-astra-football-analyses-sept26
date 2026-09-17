import { useState } from 'react';

import { postLeftoverSupportBundle } from '../utils/workbench';

export default function LeftoverSupportBundleWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestSupportBundle() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postLeftoverSupportBundle();
      if (payload.released === false && (payload.reasonCodes ?? []).includes('CONSENT_REQUIRED')) {
        setNote('Posted leftover support bundle keeps released false. Client POST consented true is not sent. Leftover POST is not stored GET support bundle.');
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
    <section aria-label="Unforced leftover support bundle" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced leftover support bundle</h4>
      <button
        type="button"
        aria-label="Request leftover support bundle"
        onClick={() => void requestSupportBundle()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request leftover support bundle
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
