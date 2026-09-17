import { useEffect, useState } from 'react';

import { fetchMatchHistory } from '../utils/workbench';

interface MatchAuditTrailPanelProps {
  matchId?: string;
}

export default function MatchAuditTrailPanel({ matchId }: MatchAuditTrailPanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMatchHistory(matchId)
      .then((payload) => {
        if (cancelled) return;
        if (payload.undoable === true && payload.rewrotePastOutcomes === false) {
          setNote('Stored audit trail is undoable. rewrotePastOutcomes is false.');
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
    <section aria-label="Audit trail" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Audit trail</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
