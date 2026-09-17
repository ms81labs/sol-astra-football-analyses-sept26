import { useEffect, useState } from 'react';

import { fetchIncidentResponse } from '../utils/workbench';

export default function IncidentResponsePanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchIncidentResponse()
      .then((payload) => {
        if (cancelled) return;
        if (payload.faceRecognition === false && payload.crossSeasonIdentity === false) {
          setNote('Stored incident response keeps faceRecognition false. crossSeasonIdentity stays false. Incident restore does not enable face recognition.');
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
    <section aria-label="Stored incident response" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored incident response</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
