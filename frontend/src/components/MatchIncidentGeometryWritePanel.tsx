import { useEffect, useState } from 'react';

import { postMatchIncidentGeometry } from '../utils/workbench';

interface MatchIncidentGeometryWritePanelProps {
  matchId?: string;
}

export default function MatchIncidentGeometryWritePanel({ matchId }: MatchIncidentGeometryWritePanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    postMatchIncidentGeometry(matchId)
      .then((payload) => {
        if (cancelled) return;
        const reasons = payload.reasonCodes ?? [];
        if (payload.validatedMeasurement === false && reasons.includes('IFAB_LAW_11_NOT_APPLIED')) {
          setNote('Posted incident geometry ignores client myTeam and attackDirection. validatedMeasurement stays false. IFAB_LAW_11_NOT_APPLIED remains.');
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
    <section aria-label="Uninjected origin write" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Uninjected origin write</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
