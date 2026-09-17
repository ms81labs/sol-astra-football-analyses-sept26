import { useEffect, useState } from 'react';

import { fetchRecoveryDisk } from '../utils/workbench';

export default function RecoveryDiskPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchRecoveryDisk()
      .then((payload) => {
        if (cancelled) return;
        if (payload.acceptedPartial === false && payload.error === 'disk_exhaustion') {
          setNote('Stored disk recovery refuses partial acceptance. disk_exhaustion stays blocking. Partial-disk imports stay fail-closed.');
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
    <section aria-label="Stored disk recovery" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored disk recovery</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
