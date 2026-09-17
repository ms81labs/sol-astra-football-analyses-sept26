import { useEffect, useState } from 'react';

import { fetchBoundedNextSampleReport } from '../utils/workbench';

export default function BoundedNextSampleReportPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchBoundedNextSampleReport()
      .then((payload) => {
        if (cancelled) return;
        if (payload.schemaVersion === 'video_to_analysis_bounded_next_sample_report_view_model_v1') {
          setNote('Stored bounded next-sample report is historical. Historical bounded-next-sample-report is not current-source sealed inference. Next sample stays bounded and unlabeled.');
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
    <section aria-label="Stored bounded next-sample report" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored bounded next-sample report</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
