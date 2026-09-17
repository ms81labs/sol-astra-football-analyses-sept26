import { useEffect, useState } from 'react';

import { fetchEvaluationHota } from '../utils/workbench';

export default function EvaluationHotaPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchEvaluationHota()
      .then((payload) => {
        if (cancelled) return;
        const reasons = payload.reasonCodes ?? [];
        if (
          payload.scored === false
          && payload.hota == null
          && payload.idf1 == null
          && reasons.includes('INCOMPATIBLE_HOTA_LABEL_SPACE')
          && reasons.includes('NATIVE_PREDICTIONS_REQUIRED')
        ) {
          setNote('Stored HOTA/IDF1 remains unscored. Official pitch positions are not image-space labels. NATIVE_PREDICTIONS_REQUIRED.');
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
    <section aria-label="Stored HOTA measures" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored HOTA measures</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
