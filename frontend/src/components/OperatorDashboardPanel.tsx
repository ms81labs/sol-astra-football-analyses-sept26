import { useEffect, useState } from 'react';

import { fetchOperatorDashboard } from '../utils/workbench';

export default function OperatorDashboardPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchOperatorDashboard()
      .then((payload) => {
        if (cancelled) return;
        if (payload.schemaVersion === 'video_to_analysis_operator_dashboard_view_model_v1') {
          setNote('Stored operator dashboard is historical. Historical operator-dashboard is not current-source sealed inference. Operator dashboard stays non-accepting.');
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
    <section aria-label="Stored operator dashboard" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored operator dashboard</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
