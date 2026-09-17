import { useEffect, useState } from 'react';

import { fetchAnalystWorkflow } from '../utils/workbench';

export default function AnalystWorkflowPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchAnalystWorkflow()
      .then((payload) => {
        if (cancelled) return;
        const reasons = payload.reasonCodes ?? [];
        if (
          payload.measured === false
          && payload.analystCompletedReviewedMatch === false
          && reasons.includes('ANALYST_ACCEPTANCE_MISSING')
        ) {
          setNote('Analyst workflow measures remain unmeasured. ANALYST_ACCEPTANCE_MISSING. This is not a completed reviewed match.');
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
    <section aria-label="Analyst workflow" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Analyst workflow</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
