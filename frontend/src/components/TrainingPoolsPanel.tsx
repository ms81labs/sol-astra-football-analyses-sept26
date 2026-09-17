import { useEffect, useState } from 'react';

import { fetchTrainingPools } from '../utils/workbench';

export default function TrainingPoolsPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchTrainingPools()
      .then((payload) => {
        if (cancelled) return;
        if (payload.pools?.includes('locked_evaluation')) {
          setNote('Stored training pools keep locked_evaluation isolated. Locked evaluation is not a training source.');
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
    <section aria-label="Stored training pools" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored training pools</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
