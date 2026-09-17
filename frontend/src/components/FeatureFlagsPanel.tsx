import { useEffect, useState } from 'react';

import { fetchWorkbenchFlags } from '../utils/workbench';

export default function FeatureFlagsPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchWorkbenchFlags()
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.gpu_default === false
          && payload.native_code === false
          && payload.experimental_shot_quality === false
        ) {
          setNote('Stored feature flags keep gpu_default false. native_code stays false. experimental_shot_quality is not a published default.');
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
    <section aria-label="Stored feature flags" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored feature flags</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
