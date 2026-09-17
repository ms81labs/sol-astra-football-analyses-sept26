import { useEffect, useState } from 'react';

import { fetchShadowMetric } from '../utils/workbench';

export default function ShadowMetricPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchShadowMetric('experimental_shot_quality')
      .then((payload) => {
        if (cancelled) return;
        if (payload.published === false && payload.default === false) {
          setNote('Stored shadow flag keeps experimental_shot_quality unpublished. published stays false. The default stays off.');
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
    <section aria-label="Stored shadow flag" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored shadow flag</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
