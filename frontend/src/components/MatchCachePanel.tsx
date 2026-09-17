import { useEffect, useState } from 'react';

import { fetchMatchCache } from '../utils/workbench';

interface MatchCachePanelProps {
  matchId?: string;
}

export default function MatchCachePanel({ matchId }: MatchCachePanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMatchCache(matchId)
      .then((payload) => {
        if (cancelled) return;
        if (payload.namespace === 'production' && payload.compatibleWithDevelopment === false) {
          setNote('Production cache identity is not compatible with development.');
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
    <section aria-label="Cache identity" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Cache identity</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
