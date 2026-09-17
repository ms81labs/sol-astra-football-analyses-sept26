import { useEffect, useState } from 'react';

import { fetchMetricRoundTrip } from '../utils/workbench';

export default function MetricRoundTripPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchMetricRoundTrip()
      .then((payload) => {
        if (cancelled) return;
        if (payload.availability === 'unknown' && payload.publishedValue === null) {
          setNote('Stored metric round-trip keeps availability unknown. publishedValue stays null. Unknown metrics do not acquire a published value.');
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
    <section aria-label="Stored metric round-trip" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored metric round-trip</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
