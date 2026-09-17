import { useEffect, useState } from 'react';

import { postMatchCache } from '../utils/workbench';

interface MatchCacheWritePanelProps {
  matchId?: string;
}

export default function MatchCacheWritePanel({ matchId }: MatchCacheWritePanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    postMatchCache(matchId)
      .then((payload) => {
        if (cancelled) return;
        if (payload.namespace === 'production' && payload.compatibleWithDevelopment === false) {
          setNote('Posted cache identity ignores client namespace development. Namespace stays production. compatibleWithDevelopment stays false.');
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
    <section aria-label="Posted namespace write" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Posted namespace write</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
