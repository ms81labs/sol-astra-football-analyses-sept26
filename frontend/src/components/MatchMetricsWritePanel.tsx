import { useEffect, useState } from 'react';

import { postMatchMetrics } from '../utils/workbench';

interface MatchMetricsWritePanelProps {
  matchId?: string;
}

export default function MatchMetricsWritePanel({ matchId }: MatchMetricsWritePanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    postMatchMetrics(matchId)
      .then((payload) => {
        if (cancelled) return;
        const distance = payload.metrics?.find((item) => item.metric === 'my_team_distance_m');
        const reasons = distance?.reasonCodes ?? [];
        if (distance?.availability === 'unknown' && reasons.includes('IDENTITY_DISCONTINUITY')) {
          setNote('Posted metrics ignore client identityContinuous and calibrationAccepted. Availability stays unknown. IDENTITY_DISCONTINUITY remains.');
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
    <section aria-label="Unforced continuity write" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced continuity write</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
