import { useEffect, useState } from 'react';

import { fetchAcceptanceReport } from '../utils/workbench';

export default function AcceptanceReportPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchAcceptanceReport()
      .then((payload) => {
        if (cancelled) return;
        if (payload.schemaVersion === 'video_to_analysis_acceptance_report_view_model_v1') {
          setNote('Stored acceptance report is historical. Historical acceptance-report is not analyst-accepted current-source. Independent locked labels remain 0/18.');
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
    <section aria-label="Stored acceptance report" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored acceptance report</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
