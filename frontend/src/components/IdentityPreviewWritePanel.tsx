import { useState } from 'react';

import { postIdentityPreview } from '../utils/workbench';

export default function IdentityPreviewWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestPreview() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postIdentityPreview();
      if (payload.committed === false && payload.visionRerun === false) {
        setNote('Posted identity preview keeps committed false. Client committed true is not sent. Vision rerun stays off.');
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
    <section aria-label="Unforced identity preview" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced identity preview</h4>
      <button
        type="button"
        aria-label="Request identity preview"
        onClick={() => void requestPreview()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request identity preview
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
