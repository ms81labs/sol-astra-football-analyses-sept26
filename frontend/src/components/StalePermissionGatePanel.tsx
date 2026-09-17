import { useEffect, useState } from 'react';

import { fetchStalePermissionGate } from '../utils/workbench';

export default function StalePermissionGatePanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchStalePermissionGate()
      .then((payload) => {
        if (cancelled) return;
        if (payload.admitted === false && payload.reasonCodes?.includes('STALE_PERMISSION')) {
          setNote('Stored stale permissions keep admitted false. Client admitted true is not sent. STALE_PERMISSION stays blocking.');
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
    <section aria-label="Stored stale permissions" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored stale permissions</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
