import { useEffect, useState } from 'react';

import { fetchRecoveryRestore } from '../utils/workbench';

export default function RecoveryRestorePanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchRecoveryRestore()
      .then((payload) => {
        if (cancelled) return;
        if (payload.tested === true) {
          setNote('Stored restore exercise stays tested. Tested restore is not current-source sealed inference.');
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
    <section aria-label="Stored restore exercise" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored restore exercise</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
