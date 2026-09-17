import { useEffect, useState } from 'react';

import { fetchPostReleaseMonitoring } from '../utils/workbench';

export default function PostReleaseMonitoringPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchPostReleaseMonitoring()
      .then((payload) => {
        if (cancelled) return;
        if (payload.schemaVersion === 'video_to_analysis_post_release_monitoring_view_model_v1') {
          setNote('Stored post-release monitoring is historical. Historical post-release-monitoring is not current-source sealed inference. Independent labels stay unmeasured.');
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
    <section aria-label="Stored post-release monitoring" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored post-release monitoring</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
