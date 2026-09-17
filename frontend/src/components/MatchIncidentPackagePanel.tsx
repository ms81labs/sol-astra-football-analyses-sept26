import { useEffect, useState } from 'react';

import { fetchMatchIncidentPackage } from '../utils/workbench';

interface MatchIncidentPackagePanelProps {
  matchId?: string;
}

export default function MatchIncidentPackagePanel({ matchId }: MatchIncidentPackagePanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMatchIncidentPackage(matchId)
      .then((payload) => {
        if (cancelled) return;
        const reasons = payload.reasonCodes ?? [];
        if (
          payload.level === 0
          && payload.decision == null
          && payload.validatedMeasurement === false
          && reasons.includes('IFAB_LAW_11_NOT_APPLIED')
        ) {
          setNote('Stored incident package is level 0: synchronized source clips and notes only. IFAB_LAW_11_NOT_APPLIED. Decision is unpublished.');
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
    <section aria-label="Incident package" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Incident package</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
