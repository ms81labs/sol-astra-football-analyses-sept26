import { useState } from 'react';

import { postPerceptionTiles } from '../utils/workbench';

export default function PerceptionTilesWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestTiles() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postPerceptionTiles();
      if (payload.productQualityPass === false && Array.isArray(payload.merged) && payload.merged.length === 0) {
        setNote('Posted perception tiles keep productQualityPass false. Client detections are not sent. Empty tiles stay unmerged.');
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
    <section aria-label="Unforced perception tiles" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced perception tiles</h4>
      <button
        type="button"
        aria-label="Request perception tiles"
        onClick={() => void requestTiles()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request perception tiles
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
