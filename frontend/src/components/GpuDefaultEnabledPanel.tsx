import { useEffect, useState } from 'react';

import { fetchGpuDefaultEnabled } from '../utils/workbench';

export default function GpuDefaultEnabledPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchGpuDefaultEnabled()
      .then((payload) => {
        if (cancelled) return;
        if (payload.name === 'gpu_default' && payload.enabled === false) {
          setNote('Stored GPU default enabled flag keeps enabled false. Client enabled true is not sent. A GET flag is not GPU promotion.');
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
    <section aria-label="Stored GPU default enabled flag" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored GPU default enabled flag</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
