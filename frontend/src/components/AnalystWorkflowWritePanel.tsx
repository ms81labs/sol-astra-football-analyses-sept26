import { useEffect, useState } from 'react';

import { postAnalystWorkflow } from '../utils/workbench';

export default function AnalystWorkflowWritePanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    postAnalystWorkflow()
      .then((payload) => {
        if (cancelled) return;
        const reasons = payload.reasonCodes ?? [];
        if (
          payload.measured === false
          && payload.analystCompletedReviewedMatch === false
          && reasons.includes('ANALYST_ACCEPTANCE_MISSING')
        ) {
          setNote('Posted workflow ignores client measured. Client true flags are not sent. ANALYST_ACCEPTANCE_MISSING stays.');
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
    <section aria-label="Unmeasured workflow write" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unmeasured workflow write</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
