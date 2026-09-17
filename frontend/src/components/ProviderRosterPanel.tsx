import { useEffect, useState } from 'react';

import { fetchProviderRoster } from '../utils/workbench';

export default function ProviderRosterPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchProviderRoster()
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.roster?.default === 'disabled'
          && payload.local?.route === 'disabled'
          && payload.cloud?.route === 'disabled'
        ) {
          setNote('Stored provider roster keeps the default disabled. Client enabled cloud is not sent. Local and cloud routes stay disabled.');
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
    <section aria-label="Stored provider roster" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored provider roster</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
