import { useEffect, useState } from 'react';

import { fetchRealVideoScaleoutReport } from '../utils/workbench';

export default function RealVideoScaleoutReportPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchRealVideoScaleoutReport()
      .then((payload) => {
        if (cancelled) return;
        if (payload.schemaVersion === 'video_to_analysis_real_video_scaleout_report_view_model_v1') {
          setNote('Stored real-video-scaleout report is historical. Historical real-video-scaleout-report is not current-source sealed inference. Scaleout does not admit independent labels.');
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
    <section aria-label="Stored real-video-scaleout report" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored real-video-scaleout report</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
