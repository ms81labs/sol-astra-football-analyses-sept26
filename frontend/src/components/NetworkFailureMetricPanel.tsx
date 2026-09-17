import { useEffect, useState } from 'react';

import { fetchNetworkFailureMetric } from '../utils/workbench';

export default function NetworkFailureMetricPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchNetworkFailureMetric()
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.availability === 'unknown'
          && payload.value == null
          && payload.replacedWithGenerated === false
        ) {
          setNote('Stored network-failure metric stays unknown. Generated numbers do not replace missing values.');
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
    <section aria-label="Stored network-failure metric" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored network-failure metric</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
