import { useEffect, useState } from 'react';

import { fetchChallengerAdapters } from '../utils/workbench';

export default function ChallengerAdaptersPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchChallengerAdapters()
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.kloppy?.enabled === false
          && payload.roboflow?.enabled === false
          && payload.mcbyte?.enabled === false
        ) {
          setNote('Stored challenger adapters keep kloppy.enabled false. Client kloppy true is not sent. Roboflow and MCBYTE stay unadmitted.');
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
    <section aria-label="Stored challenger adapters" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored challenger adapters</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
