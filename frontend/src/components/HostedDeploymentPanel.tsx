import { useEffect, useState } from 'react';

import { fetchHostedDeployment } from '../utils/workbench';

export default function HostedDeploymentPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchHostedDeployment()
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.admitted === false
          && payload.requiresGNetwork === true
          && payload.silentCloudFallback === false
        ) {
          setNote('Stored hosted collaboration deployment stays unadmitted. It requires G-NETWORK. Silent cloud fallback stays off.');
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
    <section aria-label="Stored hosted deployment" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored hosted deployment</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
