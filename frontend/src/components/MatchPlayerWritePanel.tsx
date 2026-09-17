import { useEffect, useState } from 'react';

import { postPlayerObservations } from '../utils/workbench';

interface MatchPlayerWritePanelProps {
  matchId?: string;
}

export default function MatchPlayerWritePanel({ matchId }: MatchPlayerWritePanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    postPlayerObservations(matchId)
      .then((payload) => {
        if (cancelled) return;
        const reasons = payload.reasonCodes ?? [];
        const trackIds = (payload.rows ?? []).map((row) => String(row.trackId ?? ''));
        if (
          payload.totalsWithheld === true
          && reasons.includes('IDENTITY_DISCONTINUITY')
          && !trackIds.includes('forged')
        ) {
          setNote('Posted player observations ignore client rows and identityContinuous. Totals stay withheld. forged trackId is not sent.');
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
    <section aria-label="Uninjected observation write" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Uninjected observation write</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
