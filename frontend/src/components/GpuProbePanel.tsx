import { useEffect, useState } from 'react';

import { fetchGpuProbe } from '../utils/workbench';

export default function GpuProbePanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchGpuProbe()
      .then((payload) => {
        if (cancelled) return;
        const reasons = payload.videoEngine?.reasonCodes ?? [];
        if (payload.canPromoteDefault === false && reasons.includes('CUDA_VISIBILITY_IS_NOT_VIDEO_CAPABILITY')) {
          setNote('Stored GPU probe cannot promote default. CUDA visibility is not video capability.');
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
    <section aria-label="Stored GPU probe" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored GPU probe</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
