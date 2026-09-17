import { useEffect, useState } from 'react';

import { fetchMilestoneProgress } from '../utils/workbench';

export default function MilestoneProgressPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchMilestoneProgress()
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.progress?.usesMergedFilesAsSuccess === false
          && payload.progress.completedAnalystTasks === 0
        ) {
          setNote('Stored milestone progress does not treat merged files as success. completedAnalystTasks stays 0.');
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
    <section aria-label="Stored milestone progress" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored milestone progress</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
