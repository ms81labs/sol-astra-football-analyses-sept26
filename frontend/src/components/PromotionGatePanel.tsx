import { useEffect, useState } from 'react';

import { fetchPromotionGate } from '../utils/workbench';

export default function PromotionGatePanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchPromotionGate()
      .then((payload) => {
        if (cancelled) return;
        if (payload.promoted === false && (payload.reasonCodes ?? []).includes('INDEPENDENT_ACCEPTANCE_MISSING')) {
          setNote('Stored promotion gate stays closed. INDEPENDENT_ACCEPTANCE_MISSING stays blocking. Client independentAccepted is not sent.');
        } else {
          setNote(null);
        }
      })
      .catch(() => {
        if (!cancelled) setNote(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!note) return null;
  return (
    <section aria-label="Stored promotion gate" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored promotion gate</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
