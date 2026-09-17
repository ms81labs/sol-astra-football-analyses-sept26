import { useEffect, useState } from 'react';

import { postMatchIncidentPackage } from '../utils/workbench';

interface MatchIncidentPackageWritePanelProps {
  matchId?: string;
}

export default function MatchIncidentPackageWritePanel({ matchId }: MatchIncidentPackageWritePanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    postMatchIncidentPackage(matchId)
      .then((payload) => {
        if (cancelled) return;
        const notes = JSON.stringify(payload.notes ?? []);
        const clips = JSON.stringify(payload.clips ?? []);
        if (
          payload.validatedMeasurement === false
          && !notes.includes('forged')
          && !clips.includes('forged-offside')
        ) {
          setNote('Posted incident package ignores client clips and notes. Client forged-offside is not sent. validatedMeasurement stays false.');
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
  }, [matchId]);

  if (!note) return null;
  return (
    <section aria-label="Uninjected clip write" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Uninjected clip write</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
