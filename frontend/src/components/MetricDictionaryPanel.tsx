import { useEffect, useState } from 'react';

import { fetchMetricDictionary } from '../utils/workbench';

export default function MetricDictionaryPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchMetricDictionary()
      .then((payload) => {
        if (cancelled) return;
        if (payload.metrics?.experimental_shot_quality?.publishedLabel === 'experimental_shot_quality') {
          setNote('Stored metric dictionary lists experimental_shot_quality. Listing a published label is not a calibrated measurement.');
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
    <section aria-label="Stored metric dictionary" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored metric dictionary</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
