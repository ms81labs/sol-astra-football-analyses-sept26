import { useState } from 'react';

import { postLeftoverRosterPromotion } from '../utils/workbench';

export default function LeftoverRosterPromotionWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestRosterPromotion() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postLeftoverRosterPromotion();
      if (payload.promoted === false && (payload.reasonCodes ?? []).includes('INDEPENDENT_ACCEPTANCE_MISSING')) {
        setNote('Posted leftover roster promotion keeps promoted false. Client POST independentAccepted true is not sent. Leftover POST is not stored GET promotion gate.');
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
    <section aria-label="Unforced leftover roster promotion" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced leftover roster promotion</h4>
      <button
        type="button"
        aria-label="Request leftover roster promotion"
        onClick={() => void requestRosterPromotion()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request leftover roster promotion
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
