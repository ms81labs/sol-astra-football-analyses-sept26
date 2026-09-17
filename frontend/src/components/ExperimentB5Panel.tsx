import { useEffect, useState } from 'react';

import { fetchExperiment } from '../utils/workbench';

export default function ExperimentB5Panel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchExperiment('B5')
      .then((payload) => {
        if (cancelled) return;
        if (payload.promoted === false && (payload.reasonCodes ?? []).includes('NATIVE_GATE_CLOSED')) {
          setNote('Stored experiment B5 stays unpromoted. NATIVE_GATE_CLOSED stays blocking. Native rewrite stays unproven.');
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
    <section aria-label="Stored experiment B5" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored experiment B5</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
