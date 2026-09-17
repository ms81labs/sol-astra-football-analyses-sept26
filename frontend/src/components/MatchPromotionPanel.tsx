import { useEffect, useState } from 'react';

import { fetchMatchPromotion } from '../utils/workbench';

interface MatchPromotionPanelProps {
  matchId?: string;
}

export default function MatchPromotionPanel({ matchId }: MatchPromotionPanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMatchPromotion(matchId)
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.completeMatchAccepted === false
          && payload.stageBenchmarkIsCompleteMatchAcceptance === false
          && payload.outputQuality === 'unproven'
        ) {
          setNote('Promotion receipt is not complete-match acceptance. Output quality is unproven.');
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
    <section aria-label="Promotion receipt" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Promotion receipt</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
