import { useEffect, useState } from 'react';

import { fetchExperiment } from '../utils/workbench';

export default function ExperimentReceiptPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchExperiment('B2')
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.promoted === false
          && payload.hardwareVerified === false
          && (payload.reasonCodes ?? []).includes('HARDWARE_UNAVAILABLE')
        ) {
          setNote('Stored experiment B2 stays unpromoted. Hardware stays unverified. HARDWARE_UNAVAILABLE stays blocking.');
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
    <section aria-label="Stored experiment B2" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored experiment B2</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
