import { useEffect, useState } from 'react';

import { fetchLocalOnlyDeployment } from '../utils/workbench';

export default function LocalOnlyDeploymentPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchLocalOnlyDeployment()
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.admitted === true
          && payload.silentCloudFallback === false
          && payload.requiresGNetwork === false
        ) {
          setNote('Stored local-only deployment keeps admitted true. silentCloudFallback stays false. Local admission is not G-NETWORK.');
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
    <section aria-label="Stored local-only deployment" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored local-only deployment</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
