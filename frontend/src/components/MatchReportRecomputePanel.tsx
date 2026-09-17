import { useEffect, useState } from 'react';

import { recomputeMatchReport } from '../utils/workbench';

interface MatchReportRecomputePanelProps {
  matchId?: string;
}

export default function MatchReportRecomputePanel({ matchId }: MatchReportRecomputePanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    recomputeMatchReport(matchId)
      .then((payload) => {
        if (cancelled) return;
        if (payload.visionInvoked === false && payload.reused === true) {
          setNote('Report-only recompute does not invoke vision. visionInvoked is false. Stored detections are reused.');
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
    <section aria-label="Report-only recompute" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Report-only recompute</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
