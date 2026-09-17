import { useEffect, useState } from 'react';

import { fetchDatasetRights } from '../utils/workbench';

export default function DatasetRightsPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchDatasetRights()
      .then((payload) => {
        if (cancelled) return;
        if (payload.soccernet?.commercialProduct === false) {
          setNote('Stored dataset rights keep SoccerNet commercialProduct false. Research purpose is not a commercial product licence.');
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
    <section aria-label="Stored dataset rights" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored dataset rights</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
