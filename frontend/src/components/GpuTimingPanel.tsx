import { useEffect, useState } from 'react';

import { fetchGpuTiming } from '../utils/workbench';

export default function GpuTimingPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchGpuTiming()
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.admitted === false
          && payload.usesSubmissionAsCompletedWork === false
          && (payload.completedMs === null || payload.completedMs === undefined)
        ) {
          setNote('Stored GPU timing stays unadmitted. Submission milliseconds are not completed work. completedMs stays unknown.');
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
    <section aria-label="Stored GPU timing" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored GPU timing</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
