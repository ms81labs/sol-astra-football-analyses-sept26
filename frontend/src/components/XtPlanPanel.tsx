import { useEffect, useState } from 'react';

import { fetchXtPlan } from '../utils/workbench';

export default function XtPlanPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchXtPlan()
      .then((payload) => {
        if (cancelled) return;
        if (payload.enabled === false && payload.socceractionImportDoesNotValidateExtraction === true) {
          setNote('Stored xT stays disabled. Socceraction import does not validate extraction.');
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
    <section aria-label="Stored xT plan" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored xT plan</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
