import { useState } from 'react';

import { postGeometryZoomCut } from '../utils/workbench';

export default function GeometryZoomCutWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestZoomCut() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postGeometryZoomCut();
      if (payload.changed === true) {
        setNote('Posted geometry zoom-cut keeps changed true. Client changed false is not sent. Homography shift stays a cut.');
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
    <section aria-label="Unforced geometry zoom-cut" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced geometry zoom-cut</h4>
      <button
        type="button"
        aria-label="Request geometry zoom-cut"
        onClick={() => void requestZoomCut()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request geometry zoom-cut
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
