import { useEffect, useState } from 'react';

import { postMatchAssistanceReport } from '../utils/workbench';

interface MatchAssistanceReportPanelProps {
  matchId?: string;
}

export default function MatchAssistanceReportPanel({ matchId }: MatchAssistanceReportPanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    postMatchAssistanceReport(matchId)
      .then((payload) => {
        if (cancelled) return;
        const reasons = payload.factualCheck?.reasonCodes ?? [];
        if (payload.factualCheck?.accepted === false && reasons.includes('FABRICATED_EVIDENCE')) {
          setNote('Match assistance report does not accept client-claimed evidence. claimedEvidenceIds are not sent. FABRICATED_EVIDENCE stays unaccepted.');
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
    <section aria-label="Assistance report" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Assistance report</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
