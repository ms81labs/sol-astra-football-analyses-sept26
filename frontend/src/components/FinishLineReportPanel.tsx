import { useEffect, useState } from 'react';

import { fetchFinishLineReport } from '../utils/workbench';

export default function FinishLineReportPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchFinishLineReport()
      .then((payload) => {
        if (cancelled) return;
        if (payload.schemaVersion === 'video_to_analysis_finish_line_product_view_model_v1') {
          setNote('Stored finish-line report is historical. Historical finish-line is not current-source sealed inference. Independent labels stay 0/18.');
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
    <section aria-label="Stored finish-line report" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored finish-line report</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
