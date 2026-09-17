import { useEffect, useState } from 'react';

import { fetchPlayerObservations } from '../utils/workbench';

interface MatchPlayerObservationsPanelProps {
  matchId?: string;
}

export default function MatchPlayerObservationsPanel({ matchId }: MatchPlayerObservationsPanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchPlayerObservations(matchId)
      .then((payload) => {
        if (cancelled) return;
        const reasons = payload.reasonCodes ?? [];
        if (
          payload.intervalLimited === true
          && payload.totalsWithheld === true
          && reasons.includes('IDENTITY_DISCONTINUITY')
        ) {
          setNote('Stored player observations are interval-limited. Totals withheld. IDENTITY_DISCONTINUITY.');
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
    <section aria-label="Player observations" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Player observations</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
