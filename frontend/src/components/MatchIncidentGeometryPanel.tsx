import { useEffect, useState } from 'react';

import { fetchMatchIncidentGeometry } from '../utils/workbench';

interface MatchIncidentGeometryPanelProps {
  matchId?: string;
}

export default function MatchIncidentGeometryPanel({ matchId }: MatchIncidentGeometryPanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMatchIncidentGeometry(matchId)
      .then((payload) => {
        if (cancelled) return;
        const reasons = payload.reasonCodes ?? [];
        if (
          payload.decision == null
          && payload.validatedMeasurement === false
          && reasons.includes('IFAB_LAW_11_NOT_APPLIED')
        ) {
          setNote('Stored incident geometry is not a validated measurement. IFAB_LAW_11_NOT_APPLIED. Decision is unpublished.');
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
    <section aria-label="Incident geometry" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Incident geometry</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
