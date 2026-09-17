import { useEffect, useState } from 'react';

import { fetchDetectorEvaluationReport } from '../utils/workbench';

export default function DetectorEvaluationReportPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchDetectorEvaluationReport()
      .then((payload) => {
        if (cancelled) return;
        if (payload.schemaVersion === 'video_to_analysis_detector_evaluation_report_view_model_v1') {
          setNote('Stored detector-evaluation report is historical. Historical detector-evaluation-report is not independent detector proof. Detector scores stay unproven.');
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
    <section aria-label="Stored detector-evaluation report" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored detector-evaluation report</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
