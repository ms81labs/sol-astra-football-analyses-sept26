import { useEffect, useState } from 'react';

import { fetchScaleScenario } from '../utils/workbench';

export default function ScaleScenarioPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchScaleScenario()
      .then((payload) => {
        if (cancelled) return;
        if (payload.measuredApplicationPerformance === false && payload.gbEqualsGiB === false) {
          setNote('Stored scale scenario is not measured application performance. Decimal GB is not GiB.');
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
    <section aria-label="Stored scale scenario" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored scale scenario</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
