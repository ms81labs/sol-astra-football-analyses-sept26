import { useEffect, useState } from 'react';

import { fetchMatchAssistanceFallback } from '../utils/workbench';

interface MatchAssistanceFallbackPanelProps {
  matchId?: string;
}

export default function MatchAssistanceFallbackPanel({ matchId }: MatchAssistanceFallbackPanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMatchAssistanceFallback(matchId)
      .then((payload) => {
        if (cancelled) return;
        const reasons = payload.reasonCodes ?? [];
        if (payload.route === 'template' && payload.reviewOperational === true && reasons.includes('PROVIDER_DISABLED')) {
          setNote('Stored assistance fallback is the template route. PROVIDER_DISABLED. Review remains operational.');
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
    <section aria-label="Assistance fallback" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Assistance fallback</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
