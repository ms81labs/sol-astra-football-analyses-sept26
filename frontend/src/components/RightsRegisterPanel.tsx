import { useEffect, useState } from 'react';

import { fetchRightsRegister } from '../utils/workbench';

export default function RightsRegisterPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchRightsRegister()
      .then((payload) => {
        if (cancelled) return;
        if (payload.uncertainCommercialPermissionBlocks === true) {
          setNote('Stored rights register keeps uncertain commercial permission blocking. Client granted permission is ignored.');
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
    <section aria-label="Stored rights register" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored rights register</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
