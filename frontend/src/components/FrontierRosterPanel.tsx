import { useEffect, useState } from 'react';

import { fetchFrontierRoster } from '../utils/workbench';

export default function FrontierRosterPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchFrontierRoster()
      .then((payload) => {
        if (cancelled) return;
        if (payload.promoted === false && payload.hardCodedModelName === false) {
          setNote('Stored frontier roster stays unpromoted. Hard-coded model names stay off. Frontier stays a role, not a promoted model.');
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
    <section aria-label="Stored frontier roster" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored frontier roster</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
