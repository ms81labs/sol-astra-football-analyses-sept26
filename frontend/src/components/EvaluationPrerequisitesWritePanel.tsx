import { useEffect, useState } from 'react';

import { postEvaluationPrerequisites } from '../utils/workbench';

export default function EvaluationPrerequisitesWritePanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    postEvaluationPrerequisites()
      .then((payload) => {
        if (cancelled) return;
        if (payload.accepted === false && payload.completeTasks === 0 && payload.lockedLabelsPresent === false) {
          setNote('Posted prerequisites ignore client completeTasks. Client 18 is not sent. lockedLabelsPresent stays false.');
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
    <section aria-label="Uninvented labels write" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Uninvented labels write</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
