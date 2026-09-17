import { useEffect, useState } from 'react';

import { fetchEvaluationPrerequisites } from '../utils/workbench';

export default function EvaluationPrerequisitesPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchEvaluationPrerequisites()
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.accepted === false
          && payload.completeTasks === 0
          && payload.lockedLabelsPresent === false
          && payload.nativePredictionsPresent === false
        ) {
          setNote('Stored protocol prerequisites remain incomplete. lockedLabelsPresent is false. Native predictions are not treated as labels.');
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
    <section aria-label="Stored protocol prerequisites" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored protocol prerequisites</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
