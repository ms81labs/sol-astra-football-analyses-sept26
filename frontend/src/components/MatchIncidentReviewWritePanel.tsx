import { useEffect, useState } from 'react';

import { postIncidentReview } from '../utils/workbench';

interface MatchIncidentReviewWritePanelProps {
  matchId?: string;
}

export default function MatchIncidentReviewWritePanel({ matchId }: MatchIncidentReviewWritePanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    postIncidentReview(matchId)
      .then((payload) => {
        if (cancelled) return;
        if (payload.decision == null && payload.validatedMeasurement === false) {
          setNote('Posted incident review ignores client attackerX and offside decision. Decision stays unpublished. validatedMeasurement stays false.');
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
    <section aria-label="Unvalidated positional write" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unvalidated positional write</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
