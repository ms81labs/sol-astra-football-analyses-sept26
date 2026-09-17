import { useEffect, useState } from 'react';

import { fetchPromotedRuntimeMonitoring } from '../utils/workbench';

export default function PromotedRuntimeMonitoringPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchPromotedRuntimeMonitoring()
      .then((payload) => {
        if (cancelled) return;
        if (payload.schemaVersion === 'video_to_analysis_promoted_runtime_monitoring_view_model_v1') {
          setNote('Stored promoted-runtime monitoring is historical. Historical promoted-runtime-monitoring is not current-source sealed inference. Promoted runtime stays unproven.');
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
    <section aria-label="Stored promoted-runtime monitoring" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored promoted-runtime monitoring</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
