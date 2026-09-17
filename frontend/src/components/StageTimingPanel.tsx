import { useEffect, useState } from 'react';

import { fetchStageTiming } from '../utils/workbench';

export default function StageTimingPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchStageTiming()
      .then((payload) => {
        if (cancelled) return;
        if (payload.overlappedStagesAreAdditive === false) {
          setNote('Stored stage timing keeps overlapped stages non-additive. Wall time is not the sum of overlapped stages.');
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
    <section aria-label="Stored stage timing" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored stage timing</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
