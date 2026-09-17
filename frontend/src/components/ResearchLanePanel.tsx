import { useEffect, useState } from 'react';

import { fetchResearchLane } from '../utils/workbench';

export default function ResearchLanePanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchResearchLane()
      .then((payload) => {
        if (cancelled) return;
        const plannedInert = (payload.tracks ?? []).some((track) => track.inert === true);
        if (payload.autonomousProductionChanges === false && plannedInert) {
          setNote('Stored research lane keeps planned tracks inert. Autonomous production changes stay blocked.');
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
    <section aria-label="Stored research lane" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored research lane</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
